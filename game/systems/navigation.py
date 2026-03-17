"""
Navigation & Pathfinding — A* pathfinding with stuck detection and steering.

Provides pathfinding for all entities (NPCs, player auto-play, creatures):
- A* pathfinding on the tile grid (with search limits for performance)
- Stuck detection: if entity hasn't moved significantly in N ticks, repath
- Steering behaviors: wall sliding when direct path is blocked
- Path caching: reuse recent paths to same destination

Performance constraints:
- Max search area: 50x50 tiles (2500 nodes) per pathfind call
- Path cache: 20 entries per entity type, LRU eviction
- Pathfinding budget: max 5 pathfind calls per tick across all entities
- Fallback: if A* fails or times out, use wall-sliding heuristic

Research sources:
- A* algorithm (Hart, Nilsson, Raphael 1968)
- Steering behaviors (Craig Reynolds 1999)
- RogueBasin A* Python implementation
"""

import math
import heapq
from typing import List, Tuple, Optional, Dict


# ================================================================
# A* PATHFINDING
# ================================================================

def _heuristic(x1: int, y1: int, x2: int, y2: int) -> float:
    """Manhattan distance heuristic (admissible for 4-directional)."""
    return abs(x1 - x2) + abs(y1 - y2)


def find_path(world, start_x: int, start_y: int, end_x: int, end_y: int,
              max_search: int = 2500, ignore_buildings: bool = False) -> Optional[List[Tuple[int, int]]]:
    """A* pathfinding on the tile grid.

    Returns list of (x, y) waypoints from start to end, or None if no path.
    Limited to max_search node expansions for performance.
    Set ignore_buildings=True for NPC pathfinding (they live in buildings).
    """
    w, h = world.width, world.height

    # Clamp to world bounds
    sx = max(0, min(w - 1, start_x))
    sy = max(0, min(h - 1, start_y))
    ex = max(0, min(w - 1, end_x))
    ey = max(0, min(h - 1, end_y))

    # Already there
    if sx == ex and sy == ey:
        return [(ex, ey)]

    # Quick distance check — don't pathfind extremely long distances
    dist = abs(ex - sx) + abs(ey - sy)
    if dist > 100:
        # For long distances, find path to an intermediate point
        ratio = 50.0 / dist
        ex = int(sx + (ex - sx) * ratio)
        ey = int(sy + (ey - sy) * ratio)

    # A* search
    open_set = [(0, sx, sy)]  # (f_score, x, y)
    came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
    g_score: Dict[Tuple[int, int], float] = {(sx, sy): 0}
    expanded = 0

    # 8-directional neighbors (including diagonals)
    neighbors = [(-1, 0), (1, 0), (0, -1), (0, 1),
                 (-1, -1), (1, -1), (-1, 1), (1, 1)]
    diag_cost = 1.414

    while open_set and expanded < max_search:
        _, cx, cy = heapq.heappop(open_set)
        expanded += 1

        if cx == ex and cy == ey:
            # Reconstruct path
            path = [(cx, cy)]
            while (cx, cy) in came_from:
                cx, cy = came_from[(cx, cy)]
                path.append((cx, cy))
            path.reverse()
            # Simplify: remove collinear waypoints
            return _simplify_path(path)

        if (cx, cy) in g_score and g_score[(cx, cy)] < g_score.get((cx, cy), float('inf')) - 0.01:
            continue  # stale entry

        for dx, dy in neighbors:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            if not world.is_walkable(nx, ny, ignore_buildings=ignore_buildings):
                continue

            # Diagonal: check both cardinal tiles are walkable (no corner cutting)
            if dx != 0 and dy != 0:
                if (not world.is_walkable(cx + dx, cy, ignore_buildings=ignore_buildings) or
                    not world.is_walkable(cx, cy + dy, ignore_buildings=ignore_buildings)):
                    continue

            move_cost = diag_cost if (dx != 0 and dy != 0) else 1.0
            # Terrain cost from walk cost table
            from game.settings import TERRAIN_WALK_COST
            tile = world.tiles[ny][nx]
            terrain_cost = TERRAIN_WALK_COST.get(tile, 1.0)
            if terrain_cost >= 999:
                continue  # impassable

            new_g = g_score.get((cx, cy), float('inf')) + move_cost * terrain_cost

            if new_g < g_score.get((nx, ny), float('inf')):
                g_score[(nx, ny)] = new_g
                f = new_g + _heuristic(nx, ny, ex, ey)
                came_from[(nx, ny)] = (cx, cy)
                heapq.heappush(open_set, (f, nx, ny))

    # No path found within budget
    return None


def _simplify_path(path: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Remove collinear waypoints to reduce path length."""
    if len(path) <= 2:
        return path

    simplified = [path[0]]
    for i in range(1, len(path) - 1):
        # Check if direction changes
        dx1 = path[i][0] - path[i-1][0]
        dy1 = path[i][1] - path[i-1][1]
        dx2 = path[i+1][0] - path[i][0]
        dy2 = path[i+1][1] - path[i][1]
        if dx1 != dx2 or dy1 != dy2:
            simplified.append(path[i])
    simplified.append(path[-1])
    return simplified


# ================================================================
# PATH CACHE
# ================================================================

class PathCache:
    """LRU cache for recent pathfinding results."""

    def __init__(self, max_size: int = 30):
        self._cache: Dict[Tuple[int, int, int, int], List[Tuple[int, int]]] = {}
        self._order: List[Tuple[int, int, int, int]] = []
        self._max = max_size

    def get(self, sx: int, sy: int, ex: int, ey: int) -> Optional[List[Tuple[int, int]]]:
        key = (sx, sy, ex, ey)
        return self._cache.get(key)

    def put(self, sx: int, sy: int, ex: int, ey: int, path: List[Tuple[int, int]]):
        key = (sx, sy, ex, ey)
        if key in self._cache:
            return
        self._cache[key] = path
        self._order.append(key)
        if len(self._order) > self._max:
            evict = self._order.pop(0)
            self._cache.pop(evict, None)


# ================================================================
# STUCK DETECTION
# ================================================================

def is_stuck(entity, threshold: float = 0.3, history_attr: str = '_nav_history') -> bool:
    """Check if an entity hasn't moved significantly in recent ticks.
    Stores position history on the entity itself.
    """
    if not hasattr(entity, history_attr):
        setattr(entity, history_attr, [])

    history = getattr(entity, history_attr)
    history.append((entity.x, entity.y))

    # Keep last 10 positions
    if len(history) > 10:
        history.pop(0)

    if len(history) < 5:
        return False

    # Check if we've moved less than threshold in last 5 samples
    dx = abs(history[-1][0] - history[-5][0])
    dy = abs(history[-1][1] - history[-5][1])
    return (dx + dy) < threshold


def clear_stuck_history(entity, history_attr: str = '_nav_history'):
    """Clear movement history when entity gets a new destination."""
    if hasattr(entity, history_attr):
        setattr(entity, history_attr, [])


# ================================================================
# STEERING BEHAVIORS
# ================================================================

def wall_slide(entity, target_x: float, target_y: float,
               world, speed: float, dt: float) -> Tuple[float, float]:
    """Move toward target with wall-sliding obstacle avoidance.

    Instead of stopping at walls, slides along them.
    Returns (new_x, new_y).
    """
    dx = target_x - entity.x
    dy = target_y - entity.y
    dist = math.sqrt(dx * dx + dy * dy)

    if dist < 0.3:
        return (entity.x, entity.y)

    nx, ny = dx / dist, dy / dist
    move_x = nx * speed * dt
    move_y = ny * speed * dt

    new_x = entity.x + move_x
    new_y = entity.y + move_y

    # NPCs, creatures, and autoplay player can walk inside buildings on the overworld
    is_npc = (hasattr(entity, 'npc_skills') or hasattr(entity, 'kind')
              or getattr(entity, '_auto_target_x', None) is not None)
    def walkable(wx, wy):
        if is_npc:
            return world.is_walkable(wx, wy, ignore_buildings=True)
        return world.is_walkable(wx, wy)

    # Try full move first
    x_ok = walkable(int(new_x), int(entity.y))
    y_ok = walkable(int(entity.x), int(new_y))

    if x_ok and y_ok:
        return (new_x, new_y)
    elif x_ok:
        return (new_x, entity.y)  # slide along X
    elif y_ok:
        return (entity.x, new_y)  # slide along Y
    else:
        # Both blocked — try perpendicular directions
        # Try sliding left/right relative to movement
        perp_x = -ny * speed * dt * 0.7
        perp_y = nx * speed * dt * 0.7

        # Try positive perpendicular
        test_x = entity.x + perp_x
        test_y = entity.y + perp_y
        if walkable(int(test_x), int(test_y)):
            return (test_x, test_y)

        # Try negative perpendicular
        test_x = entity.x - perp_x
        test_y = entity.y - perp_y
        if walkable(int(test_x), int(test_y)):
            return (test_x, test_y)

        # Try 8 compass directions as last resort
        step = speed * dt * 0.5
        for angle_deg in [0, 45, 90, 135, 180, 225, 270, 315]:
            rad = math.radians(angle_deg)
            test_x = entity.x + math.cos(rad) * step
            test_y = entity.y + math.sin(rad) * step
            if walkable(int(test_x), int(test_y)):
                return (test_x, test_y)

        # Completely stuck
        return (entity.x, entity.y)


# ================================================================
# PATHFINDING NAVIGATOR — main interface for entities
# ================================================================

# Global path cache and budget tracking
_path_cache = PathCache()
_pathfind_calls_this_tick = 0
_MAX_PATHFINDS_PER_TICK = 5


def reset_pathfind_budget():
    """Call once per tick to reset the pathfinding budget."""
    global _pathfind_calls_this_tick
    _pathfind_calls_this_tick = 0


def navigate_toward(entity, target_x: float, target_y: float,
                    world, speed: float, dt: float) -> bool:
    """Smart navigation: uses A* pathfinding with fallback to wall-sliding.

    Call this instead of direct movement. Returns True if entity is still moving.
    Sets entity.x, entity.y to new position.
    """
    global _pathfind_calls_this_tick

    # NPCs, creatures, and autoplay player can walk through building interiors
    # (the autoplay AI needs to pathfind through door tiles and building footprints)
    is_npc = (hasattr(entity, 'npc_skills') or hasattr(entity, 'kind')
              or getattr(entity, '_auto_target_x', None) is not None)

    dx = target_x - entity.x
    dy = target_y - entity.y
    dist = math.sqrt(dx * dx + dy * dy)

    if dist < 0.3:
        return False  # arrived

    # Check if stuck
    stuck = is_stuck(entity)

    # Get or compute path
    path = getattr(entity, '_nav_path', None)
    path_idx = getattr(entity, '_nav_path_idx', 0)

    if stuck or path is None:
        if stuck:
            clear_stuck_history(entity)

        # Try A* if within budget
        if _pathfind_calls_this_tick < _MAX_PATHFINDS_PER_TICK and dist > 3:
            sx, sy = int(entity.x), int(entity.y)
            ex, ey = int(target_x), int(target_y)

            # Check cache first
            cached = _path_cache.get(sx, sy, ex, ey)
            if cached:
                path = cached
            else:
                path = find_path(world, sx, sy, ex, ey,
                               ignore_buildings=is_npc)
                _pathfind_calls_this_tick += 1
                if path:
                    _path_cache.put(sx, sy, ex, ey, path)

            if path:
                entity._nav_path = path
                entity._nav_path_idx = 0
                path_idx = 0
            else:
                # A* failed — use wall-sliding
                entity._nav_path = None
                new_x, new_y = wall_slide(entity, target_x, target_y, world, speed, dt)
                entity.x = new_x
                entity.y = new_y
                return True
        else:
            # Over budget or short distance — wall-slide
            new_x, new_y = wall_slide(entity, target_x, target_y, world, speed, dt)
            entity.x = new_x
            entity.y = new_y
            return True

    # Follow path waypoints
    if path and path_idx < len(path):
        wx, wy = path[path_idx]
        # Move toward current waypoint
        wx_f, wy_f = float(wx) + 0.5, float(wy) + 0.5  # center of tile
        wdx = wx_f - entity.x
        wdy = wy_f - entity.y
        wdist = math.sqrt(wdx * wdx + wdy * wdy)

        if wdist < 0.5:
            # Reached waypoint, advance to next
            entity._nav_path_idx = path_idx + 1
            if path_idx + 1 >= len(path):
                entity._nav_path = None
                return False  # path complete
        else:
            # Move toward waypoint with wall-sliding
            new_x, new_y = wall_slide(entity, wx_f, wy_f, world, speed, dt)
            entity.x = new_x
            entity.y = new_y

        # Update facing
        if wdist > 0.01:
            entity.facing = (wdx / wdist, wdy / wdist)

        return True

    # No path, use direct movement with wall-sliding
    new_x, new_y = wall_slide(entity, target_x, target_y, world, speed, dt)
    entity.x = new_x
    entity.y = new_y
    return True
