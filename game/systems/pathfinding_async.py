"""Asynchronous pathfinding: background thread for A* path computation.

Provides AsyncPathfinder that processes pathfinding requests on a
background thread, preventing the main game loop from blocking on
expensive A* searches.

Usage:
    async_pf = AsyncPathfinder(world)
    async_pf.request_path(entity_id, (sx, sy), (ex, ey))
    # ... each frame:
    completed = async_pf.get_completed_paths()
    if entity_id in completed:
        path = completed[entity_id]  # list of (x,y) or None

Features:
- Thread-safe request/result queues
- Path cache with 30-second TTL keyed by (start, end)
- NPCs continue current movement while waiting for a path
- Daemon thread auto-exits when main thread ends
"""

import threading
import queue
import time
from typing import Dict, List, Optional, Tuple

from game.systems.navigation import find_path


# ================================================================
# PATH CACHE WITH TTL
# ================================================================

class _PathCacheTTL:
    """Thread-safe path cache with time-to-live expiry.

    Keys are (start_x, start_y, end_x, end_y) tuples.
    Entries expire after `ttl` seconds.
    """

    def __init__(self, ttl: float = 30.0, max_size: int = 200):
        self._ttl = ttl
        self._max_size = max_size
        self._cache: Dict[Tuple[int, int, int, int],
                          Tuple[float, Optional[List[Tuple[int, int]]]]] = {}
        self._lock = threading.Lock()

    def get(self, sx: int, sy: int, ex: int, ey: int
            ) -> Tuple[bool, Optional[List[Tuple[int, int]]]]:
        """Look up a cached path. Returns (found, path_or_None)."""
        key = (sx, sy, ex, ey)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False, None
            ts, path = entry
            if time.monotonic() - ts > self._ttl:
                del self._cache[key]
                return False, None
            return True, path

    def put(self, sx: int, sy: int, ex: int, ey: int,
            path: Optional[List[Tuple[int, int]]]):
        """Store a path result in the cache."""
        key = (sx, sy, ex, ey)
        with self._lock:
            self._cache[key] = (time.monotonic(), path)
            # Evict oldest entries if over max size
            if len(self._cache) > self._max_size:
                self._evict_oldest()

    def _evict_oldest(self):
        """Remove the oldest 25% of entries (called while holding lock)."""
        if not self._cache:
            return
        items = sorted(self._cache.items(), key=lambda kv: kv[1][0])
        remove_count = max(1, len(items) // 4)
        for i in range(remove_count):
            del self._cache[items[i][0]]

    def clear(self):
        """Clear all cached paths."""
        with self._lock:
            self._cache.clear()


# ================================================================
# ASYNC PATHFINDER
# ================================================================

class AsyncPathfinder:
    """Background-threaded pathfinder that processes A* requests off-thread.

    The main thread submits pathfinding requests via request_path().
    The background thread computes paths and puts results in a result queue.
    The main thread polls get_completed_paths() each frame.

    Parameters:
        world: the game world object (needs .width, .height, .tiles,
               .is_walkable methods)
        max_queue_size: maximum pending requests (oldest dropped if full)
    """

    def __init__(self, world, max_queue_size: int = 200):
        self._world = world
        self._request_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._result_queue: queue.Queue = queue.Queue()
        self._cache = _PathCacheTTL(ttl=30.0, max_size=200)
        self._pending: set = set()  # entity_ids currently being processed
        self._pending_lock = threading.Lock()
        self._running = True

        self._thread = threading.Thread(
            target=self._worker, daemon=True, name="AsyncPathfinder"
        )
        self._thread.start()

    def request_path(self, entity_id: int,
                     start: Tuple[int, int],
                     end: Tuple[int, int],
                     ignore_buildings: bool = True) -> bool:
        """Submit a pathfinding request.

        Returns True if the request was queued, False if it was served
        from cache (result immediately available) or if the entity already
        has a pending request.

        Args:
            entity_id: unique identifier for the requesting entity
            start: (x, y) starting tile coordinates
            end: (x, y) destination tile coordinates
            ignore_buildings: if True, treat building tiles as walkable
        """
        sx, sy = start
        ex, ey = end

        # Check cache first (no need to queue if we have a recent result)
        found, cached_path = self._cache.get(sx, sy, ex, ey)
        if found:
            # Put result directly -- no need for background thread
            self._result_queue.put((entity_id, cached_path))
            return False

        # Don't queue duplicate requests for same entity
        with self._pending_lock:
            if entity_id in self._pending:
                return False
            self._pending.add(entity_id)

        try:
            self._request_queue.put_nowait(
                (entity_id, sx, sy, ex, ey, ignore_buildings)
            )
            return True
        except queue.Full:
            # Queue is full -- remove entity from pending
            with self._pending_lock:
                self._pending.discard(entity_id)
            return False

    def get_completed_paths(self) -> Dict[int, Optional[List[Tuple[int, int]]]]:
        """Collect all completed path results (non-blocking).

        Returns a dict mapping entity_id -> path (list of (x,y) or None).
        Call this once per frame from the main thread.
        """
        results: Dict[int, Optional[List[Tuple[int, int]]]] = {}
        while True:
            try:
                entity_id, path = self._result_queue.get_nowait()
                results[entity_id] = path
                with self._pending_lock:
                    self._pending.discard(entity_id)
            except queue.Empty:
                break
        return results

    def is_pending(self, entity_id: int) -> bool:
        """Check if an entity has a pathfinding request in progress."""
        with self._pending_lock:
            return entity_id in self._pending

    def update_world(self, world):
        """Update the world reference (e.g., after world regeneration)."""
        self._world = world
        self._cache.clear()

    def shutdown(self):
        """Signal the worker thread to stop."""
        self._running = False

    def _worker(self):
        """Background thread: process pathfinding requests."""
        while self._running:
            try:
                request = self._request_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            entity_id, sx, sy, ex, ey, ignore_buildings = request

            # Check cache again (may have been populated by another request)
            found, cached_path = self._cache.get(sx, sy, ex, ey)
            if found:
                self._result_queue.put((entity_id, cached_path))
                continue

            # Compute path using A*
            try:
                path = find_path(
                    self._world, sx, sy, ex, ey,
                    ignore_buildings=ignore_buildings
                )
            except Exception:
                # Pathfinding failed -- return None
                path = None

            # Cache the result
            self._cache.put(sx, sy, ex, ey, path)

            # Send result to main thread
            self._result_queue.put((entity_id, path))
