"""Terrain-aware A* pathfinding for inter-settlement roads.

Works on the low-res elevation cache from WorldPlan to find paths that
avoid water and mountains, preferring flat land. Returns world-coordinate
waypoints suitable for RoadPlan.waypoints.
"""

import heapq
import math
from typing import List, Tuple, Optional


# ================================================================
# TERRAIN COST TABLE
# ================================================================

def _terrain_cost(elev: float) -> float:
    """Return movement cost for a tile at the given elevation.

    Returns float('inf') for impassable water tiles.
    """
    if elev < 0.22:
        return float('inf')   # water — impassable
    if elev < 0.28:
        return 2.0            # beach / sand
    if elev < 0.45:
        return 1.0            # flat land (cheapest)
    if elev < 0.55:
        return 3.0            # hills
    if elev < 0.65:
        return 8.0            # mountains
    return 15.0               # high mountains


# 8-directional neighbour offsets: (dx, dy, is_diagonal)
_NEIGHBORS = [
    (-1, -1, True),  (-1, 0, False), (-1, 1, True),
    ( 0, -1, False),                 ( 0, 1, False),
    ( 1, -1, True),  ( 1, 0, False), ( 1, 1, True),
]


# ================================================================
# A* PATHFINDER
# ================================================================

def _astar(elev_cache, cw: int, ch: int,
           start: Tuple[int, int],
           goal: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
    """Run A* on the elevation cache grid.

    Parameters
    ----------
    elev_cache : numpy array [ch, cw]
    cw, ch     : cache dimensions (columns, rows)
    start, goal: (col, row) in cache coordinates

    Returns
    -------
    List of (col, row) cache-coordinate waypoints, or None if no path.
    """
    sc, sr = start
    gc, gr = goal

    # Bounds check
    if not (0 <= sc < cw and 0 <= sr < ch):
        return None
    if not (0 <= gc < cw and 0 <= gr < ch):
        return None

    # Check endpoints are passable
    if _terrain_cost(float(elev_cache[sr, sc])) == float('inf'):
        return None
    if _terrain_cost(float(elev_cache[gr, gc])) == float('inf'):
        return None

    SQRT2 = math.sqrt(2)

    def heuristic(c, r):
        dc = abs(c - gc)
        dr = abs(r - gr)
        return math.sqrt(dc * dc + dr * dr)

    # Priority queue: (f_score, counter, col, row)
    counter = 0
    open_set = [(heuristic(sc, sr), counter, sc, sr)]
    g_score = {(sc, sr): 0.0}
    came_from = {}

    while open_set:
        f, _, cc, cr = heapq.heappop(open_set)

        if cc == gc and cr == gr:
            # Reconstruct path
            path = [(gc, gr)]
            node = (gc, gr)
            while node in came_from:
                node = came_from[node]
                path.append(node)
            path.reverse()
            return path

        current_g = g_score.get((cc, cr))
        if current_g is None or f - heuristic(cc, cr) > current_g + 1e-6:
            # Stale entry
            continue

        current_elev = float(elev_cache[cr, cc])

        for dc, dr, is_diag in _NEIGHBORS:
            nc, nr = cc + dc, cr + dr
            if not (0 <= nc < cw and 0 <= nr < ch):
                continue

            neighbor_elev = float(elev_cache[nr, nc])
            base_cost = _terrain_cost(neighbor_elev)
            if base_cost == float('inf'):
                continue

            # Slope penalty
            slope_penalty = abs(current_elev - neighbor_elev) * 20.0

            step_cost = base_cost + slope_penalty
            if is_diag:
                step_cost *= SQRT2

            tentative_g = current_g + step_cost
            prev_g = g_score.get((nc, nr))
            if prev_g is None or tentative_g < prev_g:
                g_score[(nc, nr)] = tentative_g
                h = heuristic(nc, nr)
                counter += 1
                heapq.heappush(open_set, (tentative_g + h, counter, nc, nr))
                came_from[(nc, nr)] = (cc, cr)

    return None  # No path found


# ================================================================
# PATH SMOOTHING
# ================================================================

def _angle_between(p0: Tuple[int, int], p1: Tuple[int, int],
                   p2: Tuple[int, int]) -> float:
    """Return the deviation angle in degrees at p1 between segments p0-p1 and p1-p2."""
    ax = p1[0] - p0[0]
    ay = p1[1] - p0[1]
    bx = p2[0] - p1[0]
    by = p2[1] - p1[1]

    dot = ax * bx + ay * by
    mag_a = math.sqrt(ax * ax + ay * ay)
    mag_b = math.sqrt(bx * bx + by * by)

    if mag_a < 1e-9 or mag_b < 1e-9:
        return 0.0

    cos_angle = max(-1.0, min(1.0, dot / (mag_a * mag_b)))
    angle_rad = math.acos(cos_angle)
    return math.degrees(angle_rad)


def _smooth_path(path: List[Tuple[int, int]],
                 angle_threshold: float = 10.0) -> List[Tuple[int, int]]:
    """Remove intermediate waypoints that are nearly collinear.

    Keeps a point only when the turn angle exceeds angle_threshold degrees.
    Always keeps the first and last points.
    """
    if len(path) <= 2:
        return list(path)

    smoothed = [path[0]]

    for i in range(1, len(path) - 1):
        deviation = 180.0 - _angle_between(smoothed[-1], path[i], path[i + 1])
        if deviation >= angle_threshold:
            smoothed.append(path[i])

    smoothed.append(path[-1])
    return smoothed


# ================================================================
# PUBLIC API
# ================================================================

def find_road_path(plan, start_x: int, start_y: int,
                   end_x: int, end_y: int) -> List[Tuple[int, int]]:
    """Find a terrain-aware road path between two world coordinates.

    Uses A* on the plan's low-res elevation cache to route around
    water and mountains. Falls back to a straight line if no path
    exists (e.g., settlements on different islands).

    Parameters
    ----------
    plan     : WorldPlan instance (needs _elev_cache, _elev_step, _elev_cw, _elev_ch)
    start_x, start_y : start world coordinates
    end_x, end_y     : end world coordinates

    Returns
    -------
    List of (x, y) world-coordinate waypoints including start and end.
    """
    # Support both WorldPlan (_elev_*) and HistorySimulation (elev_*) attrs
    step = getattr(plan, '_elev_step', None) or plan.elev_step
    cw = getattr(plan, '_elev_cw', None) or plan.elev_cw
    ch = getattr(plan, '_elev_ch', None) or plan.elev_ch
    elev = getattr(plan, '_elev_cache', None)
    if elev is None:
        elev = plan.elev_cache

    # Convert world coords to cache coords
    sc = min(start_x // step, cw - 1)
    sr = min(start_y // step, ch - 1)
    gc = min(end_x // step, cw - 1)
    gr = min(end_y // step, ch - 1)

    cache_path = _astar(elev, cw, ch, (sc, sr), (gc, gr))

    if cache_path is None:
        # Fallback: straight line (unreachable — different island)
        return [(start_x, start_y), (end_x, end_y)]

    # Convert cache coords back to world coords
    world_path = [(c * step, r * step) for c, r in cache_path]

    # Override first and last with exact settlement positions
    world_path[0] = (start_x, start_y)
    world_path[-1] = (end_x, end_y)

    # Smooth out nearly-straight segments
    world_path = _smooth_path(world_path, angle_threshold=10.0)

    return world_path
