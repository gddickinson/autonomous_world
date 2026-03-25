"""Terrain-aware wall polygon generation for medieval settlements.

Generates irregular wall polygons that follow terrain contours:
- Pushed outward on ridgelines (exploit high ground)
- Retracted near water (natural defense replaces wall)
- Smoothed with Laplacian passes for organic medieval look
- Towers placed at corners and regular intervals
- Moat generated outside walls, skipping existing water
- Gate placement via segment-polygon intersection
"""

import math
import random
from typing import List, Tuple, Optional


def generate_wall_polygon(
    cx: int, cy: int, radius: int,
    wall_radius: int, world_plan,
    rng: random.Random,
    n_points: int = 20,
) -> List[Tuple[int, int]]:
    """Generate an irregular wall polygon that follows terrain.

    Instead of a perfect circle, sample points are pushed outward on
    high ground (ridgelines) and pulled inward or skipped near water.
    Small random jitter gives an organic medieval feel.

    Args:
        cx, cy: settlement center
        radius: full settlement radius
        wall_radius: base wall radius (~55% of settlement radius)
        world_plan: world plan with get_elevation_fast()
        rng: seeded RNG
        n_points: number of sample points around the polygon (16-24)

    Returns:
        List of (x, y) wall polygon vertices.
    """
    WATER_LEVEL = 0.25
    raw_points: List[Tuple[float, float, float]] = []  # (x, y, elev)

    for i in range(n_points):
        angle = 2 * math.pi * i / n_points
        base_r = wall_radius

        # Sample elevation at the candidate point
        px = cx + base_r * math.cos(angle)
        py = cy + base_r * math.sin(angle)
        elev = world_plan.get_elevation_fast(int(px), int(py))

        # --- Terrain adjustments ---
        # High ground (>0.45): push outward to exploit the ridge
        if elev > 0.45:
            push = wall_radius * 0.12 * min(1.0, (elev - 0.45) / 0.15)
            base_r += push
        # Low ground / near water (<0.28): pull inward — water is defense
        elif elev < 0.28:
            pull = wall_radius * 0.15 * min(1.0, (0.28 - elev) / 0.08)
            base_r -= pull

        # --- Contour following ---
        nudge_angle = 0.15  # ~8.5 degrees
        elev_left = world_plan.get_elevation_fast(
            int(cx + base_r * math.cos(angle - nudge_angle)),
            int(cy + base_r * math.sin(angle - nudge_angle)))
        elev_right = world_plan.get_elevation_fast(
            int(cx + base_r * math.cos(angle + nudge_angle)),
            int(cy + base_r * math.sin(angle + nudge_angle)))

        # Shift toward the higher neighbor (follow the ridge)
        if abs(elev_left - elev_right) > 0.02:
            shift = 0.04 if elev_left > elev_right else -0.04
            angle += shift

        # --- Organic jitter ---
        jitter = rng.uniform(-0.05, 0.05) * wall_radius
        base_r += jitter

        # Clamp: wall shouldn't go beyond 75% or inside 35% of radius
        base_r = max(radius * 0.35, min(radius * 0.75, base_r))

        fx = cx + base_r * math.cos(angle)
        fy = cy + base_r * math.sin(angle)
        raw_points.append((fx, fy, elev))

    # --- Water edge snapping ---
    # For each point in water, walk inward along the radial to find land
    snapped: List[Tuple[float, float]] = []
    for fx, fy, elev in raw_points:
        pt_elev = world_plan.get_elevation_fast(int(fx), int(fy))
        if pt_elev < WATER_LEVEL:
            # Walk inward toward center to find the water/land edge
            land_pt = _find_land_edge_inward(
                cx, cy, fx, fy, world_plan, WATER_LEVEL)
            snapped.append(land_pt)
        else:
            snapped.append((fx, fy))

    # --- Laplacian smoothing (2 passes) after water snapping ---
    coords = _smooth_polygon(snapped, passes=2, weight=0.3)

    # --- Post-smooth water safety: ensure no smoothed point is in water ---
    final: List[Tuple[float, float]] = []
    for fx, fy in coords:
        pt_elev = world_plan.get_elevation_fast(int(fx), int(fy))
        if pt_elev < WATER_LEVEL:
            land_pt = _find_land_edge_inward(
                cx, cy, fx, fy, world_plan, WATER_LEVEL)
            final.append(land_pt)
        else:
            final.append((fx, fy))

    return [(int(x), int(y)) for x, y in final]


def _find_land_edge_inward(
    cx: int, cy: int,
    wx: float, wy: float,
    world_plan,
    water_level: float = 0.25,
    max_steps: int = 40,
) -> Tuple[float, float]:
    """Walk from (wx, wy) inward toward (cx, cy) until land is found.

    Returns the first point where elevation >= water_level.
    If no land is found, returns a point close to center.
    """
    dx = cx - wx
    dy = cy - wy
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 1:
        return (float(cx), float(cy))

    step_x = dx / max_steps
    step_y = dy / max_steps

    for s in range(1, max_steps + 1):
        px = wx + step_x * s
        py = wy + step_y * s
        elev = world_plan.get_elevation_fast(int(px), int(py))
        if elev >= water_level:
            # Step back half a step for a point right at the edge
            edge_x = wx + step_x * (s - 0.5)
            edge_y = wy + step_y * (s - 0.5)
            return (edge_x, edge_y)

    # No land found — place very close to center
    return (cx + dx * 0.1, cy + dy * 0.1)


def _smooth_polygon(
    points: List[Tuple[float, float]],
    passes: int = 2,
    weight: float = 0.3,
) -> List[Tuple[float, float]]:
    """Laplacian smoothing on a closed polygon.

    Each vertex is moved toward the average of its two neighbors.
    """
    pts = list(points)
    n = len(pts)
    for _ in range(passes):
        new_pts = []
        for i in range(n):
            prev = pts[(i - 1) % n]
            curr = pts[i]
            nxt = pts[(i + 1) % n]
            avg_x = (prev[0] + nxt[0]) / 2
            avg_y = (prev[1] + nxt[1]) / 2
            nx = curr[0] + weight * (avg_x - curr[0])
            ny = curr[1] + weight * (avg_y - curr[1])
            new_pts.append((nx, ny))
        pts = new_pts
    return pts


def generate_moat_points(
    wall_points: List[Tuple[int, int]],
    cx: int, cy: int,
    world_plan,
    moat_offset: int = 4,
) -> List[Tuple[int, int]]:
    """Generate moat polygon outside the wall, skipping water areas.

    Expands each wall vertex outward by moat_offset tiles from center.
    Segments where terrain is already water (elev < 0.25) are skipped.
    """
    moat: List[Tuple[int, int]] = []
    for wx, wy in wall_points:
        # Skip if the wall vertex itself is near water — no moat needed
        wall_elev = world_plan.get_elevation_fast(wx, wy)
        if wall_elev < 0.28:
            continue
        dx = wx - cx
        dy = wy - cy
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 1:
            continue
        # Expand outward
        scale = (dist + moat_offset) / dist
        mx = int(cx + dx * scale)
        my = int(cy + dy * scale)
        # Skip if moat point is already water — no moat needed
        elev = world_plan.get_elevation_fast(mx, my)
        if elev < 0.25:
            continue
        moat.append((mx, my))
    return moat


def find_wall_polygon_crossing(
    x1: int, y1: int, x2: int, y2: int,
    wall_points: List[Tuple[int, int]],
    cx: int, cy: int,
) -> Tuple[int, int, Optional[str]]:
    """Find where a street segment crosses an irregular wall polygon.

    Tests the segment against each edge of the polygon for intersection.
    Returns (gx, gy, direction) or (0, 0, None) if no crossing.
    """
    n = len(wall_points)
    for i in range(n):
        j = (i + 1) % n
        result = _segment_intersect(
            x1, y1, x2, y2,
            wall_points[i][0], wall_points[i][1],
            wall_points[j][0], wall_points[j][1])
        if result is not None:
            gx, gy = result
            dx_v = gx - cx
            dy_v = gy - cy
            if abs(dx_v) > abs(dy_v):
                gdir = "east" if dx_v > 0 else "west"
            else:
                gdir = "south" if dy_v > 0 else "north"
            return gx, gy, gdir
    return 0, 0, None


def _segment_intersect(
    ax1: int, ay1: int, ax2: int, ay2: int,
    bx1: int, by1: int, bx2: int, by2: int,
) -> Optional[Tuple[int, int]]:
    """Return intersection point of two line segments, or None."""
    dx_a = ax2 - ax1
    dy_a = ay2 - ay1
    dx_b = bx2 - bx1
    dy_b = by2 - by1
    denom = dx_a * dy_b - dy_a * dx_b
    if abs(denom) < 1e-8:
        return None
    t = ((bx1 - ax1) * dy_b - (by1 - ay1) * dx_b) / denom
    u = ((bx1 - ax1) * dy_a - (by1 - ay1) * dx_a) / denom
    if 0 <= t <= 1 and 0 <= u <= 1:
        ix = int(ax1 + t * dx_a)
        iy = int(ay1 + t * dy_a)
        return (ix, iy)
    return None


def place_wall_towers(
    wall_points: List[Tuple[int, int]],
    gate_positions: List[Tuple[int, int, str]],
    min_spacing: int = 30,
) -> List[Tuple[int, int]]:
    """Place towers at wall corners and at regular intervals.

    Towers go where wall direction changes most (corners) and are
    spaced roughly every min_spacing tiles along the wall perimeter.
    Also places towers flanking each gate.
    """
    n = len(wall_points)
    if n < 4:
        return list((wx, wy) for wx, wy in wall_points)

    # Compute direction change at each vertex
    angles: List[float] = []
    for i in range(n):
        prev = wall_points[(i - 1) % n]
        curr = wall_points[i]
        nxt = wall_points[(i + 1) % n]
        a1 = math.atan2(curr[1] - prev[1], curr[0] - prev[0])
        a2 = math.atan2(nxt[1] - curr[1], nxt[0] - curr[0])
        turn = abs(a2 - a1)
        if turn > math.pi:
            turn = 2 * math.pi - turn
        angles.append(turn)

    # Select vertices with largest direction changes as corner towers
    indexed = sorted(enumerate(angles), key=lambda ia: -ia[1])
    towers: List[Tuple[int, int]] = []
    tower_set: set = set()

    # Top ~25% of direction-change vertices become towers
    n_corners = max(4, n // 4)
    for idx, _ in indexed[:n_corners]:
        pt = wall_points[idx]
        towers.append(pt)
        tower_set.add(idx)

    # Fill gaps: walk the perimeter and add towers every min_spacing
    accum_dist = 0.0
    last_tower_dist = 0.0
    for i in range(n):
        j = (i + 1) % n
        dx = wall_points[j][0] - wall_points[i][0]
        dy = wall_points[j][1] - wall_points[i][1]
        seg_len = math.sqrt(dx * dx + dy * dy)
        accum_dist += seg_len
        if accum_dist - last_tower_dist >= min_spacing and i not in tower_set:
            towers.append(wall_points[i])
            tower_set.add(i)
            last_tower_dist = accum_dist

    # Gate-flanking towers (slightly offset from gate positions)
    for gx, gy, gdir in gate_positions:
        towers.append((gx, gy))

    return towers
