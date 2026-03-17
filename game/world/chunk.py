"""Chunked tile storage for large worlds.

The world is divided into CHUNK_SIZE x CHUNK_SIZE tile chunks. Only chunks
near the player are held in memory; others can be evicted and regenerated
deterministically from the world plan + seed.

The ChunkGrid class provides a drop-in replacement for the old
``world.tiles`` (a list-of-lists). Code that does ``world.tiles[y][x]``
continues to work transparently — the __getitem__ returns a ChunkRow proxy
that routes reads/writes through the chunk manager.

Dirty chunks (modified by gameplay) are persisted to disk as numpy .npy
files under ``data/chunks/{seed}/``. On eviction or explicit save, dirty
chunks are written out. On load, saved chunks are read back instead of
regenerating from the seed.
"""

import math
import os
import numpy as np
from typing import Dict, Optional, Tuple, Set

# Default chunk size — each chunk is CHUNK_SIZE x CHUNK_SIZE tiles
CHUNK_SIZE = 200


class Chunk:
    """A single CHUNK_SIZE x CHUNK_SIZE block of tile data."""

    __slots__ = ('cx', 'cy', 'tiles', 'dirty', 'generated')

    def __init__(self, cx: int, cy: int):
        self.cx = cx
        self.cy = cy
        self.tiles = np.zeros((CHUNK_SIZE, CHUNK_SIZE), dtype=np.int8)
        self.dirty = False      # modified since last save
        self.generated = False  # True once terrain has been stamped


class ChunkRow:
    """Proxy returned by ChunkGrid[y] so that grid[y][x] works."""

    __slots__ = ('_grid', '_y')

    def __init__(self, grid: 'ChunkGrid', y: int):
        self._grid = grid
        self._y = y

    def __getitem__(self, x: int) -> int:
        return self._grid.get_tile(x, self._y)

    def __setitem__(self, x: int, value: int):
        self._grid.set_tile(x, self._y, value)


class ChunkGrid:
    """Drop-in replacement for ``world.tiles`` backed by chunked numpy arrays.

    Supports:
        grid[y][x]        — read a tile  (returns int)
        grid[y][x] = val  — write a tile
        len(grid)          — returns height (number of rows)
        iteration          — for row in grid (yields ChunkRow proxies)

    Chunks are generated lazily the first time a tile in that chunk is
    accessed. The ``generator`` callback is responsible for filling in
    the chunk's tile data from the world plan.
    """

    def __init__(self, width: int, height: int, default_tile: int = 2,
                 save_dir: str = "data/chunks", seed: int = 0):
        self.width = width
        self.height = height
        self.default_tile = default_tile
        self.chunk_size = CHUNK_SIZE
        self.chunks_x = math.ceil(width / CHUNK_SIZE)
        self.chunks_y = math.ceil(height / CHUNK_SIZE)
        self._chunks: Dict[Tuple[int, int], Chunk] = {}

        # Set by WorldPlan after creation — generates tile data for a chunk
        self.generator = None  # callable(chunk: Chunk, world_plan) -> None

        # Reference to the world plan (set externally)
        self.world_plan = None

        # LRU tracking for cache eviction
        self._access_order: list = []
        self.max_cached_chunks = 200  # keep up to this many in memory

        # Disk persistence — dirty chunks are saved here
        self._seed = seed
        self._save_dir = os.path.join(save_dir, str(seed))
        # Track which chunk coords have a file on disk (avoids repeated
        # os.path.exists calls). Populated lazily on first miss.
        self._disk_index: Optional[Set[Tuple[int, int]]] = None

    def __len__(self):
        return self.height

    def __getitem__(self, y: int) -> ChunkRow:
        return ChunkRow(self, y)

    def __iter__(self):
        for y in range(self.height):
            yield ChunkRow(self, y)

    # ------------------------------------------------------------------
    # Core tile access
    # ------------------------------------------------------------------

    def get_tile(self, x: int, y: int) -> int:
        """Read a single tile. Out-of-bounds returns default_tile."""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return self.default_tile
        chunk = self._ensure_chunk(x // CHUNK_SIZE, y // CHUNK_SIZE)
        return int(chunk.tiles[y % CHUNK_SIZE, x % CHUNK_SIZE])

    def set_tile(self, x: int, y: int, value: int):
        """Write a single tile. Out-of-bounds is silently ignored."""
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return
        chunk = self._ensure_chunk(x // CHUNK_SIZE, y // CHUNK_SIZE)
        chunk.tiles[y % CHUNK_SIZE, x % CHUNK_SIZE] = value
        chunk.dirty = True

    # ------------------------------------------------------------------
    # Batch operations (much faster than tile-by-tile for generation)
    # ------------------------------------------------------------------

    def fill_rect(self, x: int, y: int, w: int, h: int, value: int):
        """Fill a rectangle of tiles. Handles chunk boundaries."""
        for ty in range(max(0, y), min(self.height, y + h)):
            for tx in range(max(0, x), min(self.width, x + w)):
                self.set_tile(tx, ty, value)

    def get_chunk_tiles(self, cx: int, cy: int) -> np.ndarray:
        """Get the raw numpy array for a chunk (for fast batch reads)."""
        chunk = self._ensure_chunk(cx, cy)
        return chunk.tiles

    def set_chunk_tiles(self, cx: int, cy: int, tiles: np.ndarray):
        """Set the raw numpy array for a chunk (for fast batch writes)."""
        chunk = self._ensure_chunk(cx, cy)
        chunk.tiles[:] = tiles
        chunk.dirty = True
        chunk.generated = True

    # ------------------------------------------------------------------
    # Chunk loading
    # ------------------------------------------------------------------

    def _ensure_chunk(self, cx: int, cy: int) -> Chunk:
        """Get or create a chunk, generating its tiles if needed.

        Load order:
        1. In-memory cache (fast path)
        2. Disk cache — saved dirty chunk from a previous session/eviction
        3. Procedural generation from seed + world plan
        """
        key = (cx, cy)
        if key in self._chunks:
            # Move to front of LRU
            if self._access_order and self._access_order[-1] != key:
                try:
                    self._access_order.remove(key)
                except ValueError:
                    pass
                self._access_order.append(key)
            return self._chunks[key]

        # Try loading from disk first
        chunk = self._load_chunk_from_disk(cx, cy)

        if chunk is not None:
            # Tiles came from disk cache, but settlement building metadata
            # (stored on the WorldPlan, not the chunk) may not be populated.
            # Ensure building data is generated for any settlements in this chunk.
            if self.world_plan:
                self._ensure_settlement_buildings(cx, cy)
        else:
            # Generate fresh chunk
            chunk = Chunk(cx, cy)
            chunk.tiles[:] = self.default_tile
            if self.generator and self.world_plan:
                self.generator(chunk, self.world_plan)
                chunk.generated = True

        self._chunks[key] = chunk
        self._access_order.append(key)

        # Evict old chunks if over limit
        self._evict_if_needed()

        return chunk

    def _evict_if_needed(self):
        """Remove least-recently-used chunks if cache is too large.

        Dirty chunks are saved to disk before eviction so player
        modifications are never lost.
        """
        while len(self._chunks) > self.max_cached_chunks and self._access_order:
            old_key = self._access_order.pop(0)
            if old_key in self._chunks:
                old_chunk = self._chunks[old_key]
                if old_chunk.dirty:
                    self._save_chunk_to_disk(old_chunk)
                del self._chunks[old_key]

    # ------------------------------------------------------------------
    # Disk persistence
    # ------------------------------------------------------------------

    def _chunk_path(self, cx: int, cy: int) -> str:
        """Return the file path for a chunk's .npy file."""
        return os.path.join(self._save_dir, f"{cx}_{cy}.npy")

    def _ensure_save_dir(self):
        """Create the save directory if it doesn't exist."""
        os.makedirs(self._save_dir, exist_ok=True)

    def _build_disk_index(self):
        """Scan the save directory once to learn which chunks are on disk."""
        self._disk_index = set()
        if not os.path.isdir(self._save_dir):
            return
        for fname in os.listdir(self._save_dir):
            if fname.endswith(".npy"):
                parts = fname[:-4].split("_")
                if len(parts) == 2:
                    try:
                        self._disk_index.add((int(parts[0]), int(parts[1])))
                    except ValueError:
                        pass

    def _save_chunk_to_disk(self, chunk: Chunk):
        """Write a dirty chunk's tile array to disk as a .npy file."""
        self._ensure_save_dir()
        path = self._chunk_path(chunk.cx, chunk.cy)
        np.save(path, chunk.tiles)
        chunk.dirty = False
        # Update disk index
        if self._disk_index is not None:
            self._disk_index.add((chunk.cx, chunk.cy))

    def _load_chunk_from_disk(self, cx: int, cy: int) -> Optional[Chunk]:
        """Try to load a chunk from disk. Returns None if not found."""
        if self._disk_index is None:
            self._build_disk_index()
        if (cx, cy) not in self._disk_index:
            return None
        path = self._chunk_path(cx, cy)
        if not os.path.exists(path):
            self._disk_index.discard((cx, cy))
            return None
        try:
            tiles = np.load(path)
            chunk = Chunk(cx, cy)
            chunk.tiles[:] = tiles
            chunk.generated = True
            chunk.dirty = False  # on-disk version is clean
            return chunk
        except Exception:
            # Corrupted file — discard and regenerate
            self._disk_index.discard((cx, cy))
            return None

    def save_all_dirty(self):
        """Save every dirty chunk currently in memory to disk.

        Call this on game save / quit to make sure nothing is lost.
        """
        saved = 0
        for key, chunk in self._chunks.items():
            if chunk.dirty:
                self._save_chunk_to_disk(chunk)
                saved += 1
        return saved

    def clear_disk_cache(self):
        """Delete all saved chunk files for this seed (full reset)."""
        import shutil
        if os.path.isdir(self._save_dir):
            shutil.rmtree(self._save_dir)
        self._disk_index = None

    def _ensure_settlement_buildings(self, cx: int, cy: int):
        """Ensure settlement building metadata is populated for settlements
        overlapping this chunk.

        When chunks are loaded from disk cache, the generator
        (_stamp_settlements) isn't called, so SettlementPlan.buildings
        may be empty. This generates building data for those settlements.
        """
        import random as _random
        from game.world.chunk_generator import _generate_settlement_buildings
        settlements = self.world_plan.settlements_overlapping_chunk(
            cx, cy, CHUNK_SIZE)
        for sp in settlements:
            if not sp.buildings:
                s_rng = _random.Random(self.world_plan.seed ^ hash(sp.name))
                _generate_settlement_buildings(sp, self.world_plan, s_rng)

    def preload_around(self, x: float, y: float, radius_chunks: int = 2):
        """Preload chunks in a radius around a world position."""
        cx = int(x) // CHUNK_SIZE
        cy = int(y) // CHUNK_SIZE
        for dy in range(-radius_chunks, radius_chunks + 1):
            for dx in range(-radius_chunks, radius_chunks + 1):
                ncx, ncy = cx + dx, cy + dy
                if 0 <= ncx < self.chunks_x and 0 <= ncy < self.chunks_y:
                    self._ensure_chunk(ncx, ncy)

    def loaded_chunk_keys(self) -> Set[Tuple[int, int]]:
        """Return set of currently loaded chunk coordinates."""
        return set(self._chunks.keys())

    # ------------------------------------------------------------------
    # Conversion helpers (for migration)
    # ------------------------------------------------------------------

    @classmethod
    def from_list(cls, tiles_list: list, width: int, height: int) -> 'ChunkGrid':
        """Convert a traditional list-of-lists tile array into a ChunkGrid.

        Used during migration — the old World can convert its tiles after
        generation and everything else keeps working.
        """
        grid = cls(width, height)
        for cy in range(grid.chunks_y):
            for cx in range(grid.chunks_x):
                chunk = Chunk(cx, cy)
                y_start = cy * CHUNK_SIZE
                x_start = cx * CHUNK_SIZE
                y_end = min(y_start + CHUNK_SIZE, height)
                x_end = min(x_start + CHUNK_SIZE, width)
                for ly, wy in enumerate(range(y_start, y_end)):
                    row = tiles_list[wy]
                    for lx, wx in enumerate(range(x_start, x_end)):
                        chunk.tiles[ly, lx] = row[wx]
                chunk.generated = True
                grid._chunks[(cx, cy)] = chunk
                grid._access_order.append((cx, cy))
        return grid

    def to_list(self) -> list:
        """Convert back to a list-of-lists (for compatibility/debugging)."""
        result = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                row.append(self.get_tile(x, y))
            result.append(row)
        return result
