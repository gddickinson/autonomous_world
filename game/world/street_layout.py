"""Street Layout — coherent street networks for medieval settlements.

Replaces the chaotic Voronoi ward-boundary road web with planned
streets: main roads, cross streets, ring roads, and lanes.  Buildings
are placed in lots lining each street for a realistic medieval look.
"""

import math
import random
from typing import List, Tuple, Optional, Set, Dict
from dataclasses import dataclass, field


# ================================================================
# DATA CLASSES
# ================================================================

@dataclass
class Street:
    """A named street composed of connected line segments."""
    segments: List[Tuple[int, int, int, int]]  # (x1, y1, x2, y2)
    road_type: str  # "main", "cobblestone", "dirt", "gravel"
    width: int  # 2-4 tiles


@dataclass
class BuildingLot:
    """A rectangular lot facing a street."""
    x: int
    y: int
    w: int
    h: int
    road_direction: Optional[str]  # "north","south","east","west"
    ward_type: str = ""
    road_adjacent: bool = True


# ================================================================
# CONSTANTS
# ================================================================

LOT_WIDTH_MIN = 4
LOT_WIDTH_MAX = 7
LOT_DEPTH_MIN = 5
LOT_DEPTH_MAX = 8
ROAD_HALF_WIDTH = 3  # tiles from centre to lot edge (was 2)


# ================================================================
# STREET PLANNER
# ================================================================

class StreetPlanner:
    """Generate a coherent street network scaled by settlement type."""

    # ----- public API ---------------------------------------------------

    def plan_streets(self, cx: int, cy: int, radius: int,
                     kind: str, rng: random.Random, wp) -> List[Street]:
        """Return a list of Streets for the settlement."""
        self._cx = cx
        self._cy = cy
        self._radius = radius
        self._kind = kind
        self._rng = rng
        self._wp = wp

        builders = {
            "hamlet": self._hamlet_streets,
            "village": self._village_streets,
            "town": self._town_streets,
            "city": self._city_streets,
            "castle": self._castle_streets,
        }
        streets = builders.get(kind, self._village_streets)()
        # Filter out segments crossing water / steep slopes
        streets = self._filter_streets(streets)
        return streets

    def plan_building_lots(self, streets: List[Street],
                           cx: int, cy: int, radius: int,
                           rng: random.Random, wp,
                           kind: str = "village") -> List[BuildingLot]:
        """Place building lots along streets, leaving a market square at center."""
        self._cx, self._cy = cx, cy
        self._radius, self._rng, self._wp = radius, rng, wp

        # Market square radius — open space where main streets meet
        msq_r = (rng.randint(8, 12) if kind in ("town", "city")
                 else rng.randint(4, 6) if kind == "village" else 0)

        claimed: Set[Tuple[int, int]] = set()
        road_tiles = self._rasterize_streets(streets)
        claimed.update(road_tiles)

        # Reserve circular market square at center
        if msq_r > 0:
            for dy in range(-msq_r, msq_r + 1):
                for dx in range(-msq_r, msq_r + 1):
                    if dx * dx + dy * dy <= msq_r * msq_r:
                        claimed.add((cx + dx, cy + dy))

        lots: List[BuildingLot] = []
        for street in streets:
            for seg in street.segments:
                lots.extend(self._lots_along_segment(
                    seg, claimed, road_tiles, rng))
        lots.sort(key=lambda l: (not l.road_adjacent, -(l.w * l.h)))
        return lots

    # ----- street builders by settlement type ---------------------------

    def _hamlet_streets(self) -> List[Street]:
        cx, cy, r, rng = self._cx, self._cy, self._radius, self._rng
        streets: List[Street] = []
        # One main road through centre (random primary axis)
        angle = rng.choice([0, math.pi / 2])
        streets.append(self._make_main_road(angle))
        # Maybe one short side lane
        if rng.random() < 0.5:
            perp = angle + math.pi / 2
            lane_r = r * 0.4
            ox = int(cx + rng.uniform(-r * 0.2, r * 0.2) * math.cos(angle))
            oy = int(cy + rng.uniform(-r * 0.2, r * 0.2) * math.sin(angle))
            streets.append(Street(
                segments=[self._nudged_seg(
                    ox - int(lane_r * math.cos(perp)),
                    oy - int(lane_r * math.sin(perp)),
                    ox + int(lane_r * math.cos(perp)),
                    oy + int(lane_r * math.sin(perp)))],
                road_type="dirt", width=2))
        return streets

    def _village_streets(self) -> List[Street]:
        cx, cy, r, rng = self._cx, self._cy, self._radius, self._rng
        streets: List[Street] = []
        # Main street N-S
        streets.append(self._make_main_road(math.pi / 2))
        # Cross street E-W
        streets.append(self._make_main_road(0, length_frac=0.7,
                                            road_type="cobblestone"))
        # Maybe a small market square (add short stubs)
        if r > 50 and rng.random() < 0.6:
            for ang in [math.pi / 4, 3 * math.pi / 4]:
                d = r * 0.25
                streets.append(Street(
                    segments=[self._nudged_seg(
                        cx, cy,
                        cx + int(d * math.cos(ang)),
                        cy + int(d * math.sin(ang)))],
                    road_type="dirt", width=2))
        return streets

    def _town_streets(self) -> List[Street]:
        """Town: ~6-8 streets (2 boulevards + ring road + 2-3 lanes)."""
        cx, cy, r, rng = self._cx, self._cy, self._radius, self._rng
        streets: List[Street] = []
        # Main N-S boulevard
        streets.append(self._make_main_road(math.pi / 2,
                                            road_type="cobblestone"))
        # Main E-W boulevard
        streets.append(self._make_main_road(0, road_type="cobblestone"))
        # Ring road at ~60% radius
        streets.append(self._make_ring_road(0.6, "gravel"))
        # 2-3 connecting lanes from ring to edge (was 4)
        lane_angles = rng.sample(
            [math.pi / 4, 3 * math.pi / 4,
             5 * math.pi / 4, 7 * math.pi / 4],
            k=rng.randint(2, 3))
        for base_ang in lane_angles:
            ang = base_ang + rng.uniform(-0.15, 0.15)
            inner = r * 0.6
            outer = r * 0.82
            streets.append(Street(
                segments=[self._nudged_seg(
                    cx + int(inner * math.cos(ang)),
                    cy + int(inner * math.sin(ang)),
                    cx + int(outer * math.cos(ang)),
                    cy + int(outer * math.sin(ang)))],
                road_type="dirt", width=2))
        return streets

    def _city_streets(self) -> List[Street]:
        """City: ~12-18 streets (2 boulevards + 2 rings + 4-6 lanes + 2-4 grid)."""
        cx, cy, r, rng = self._cx, self._cy, self._radius, self._rng
        streets: List[Street] = []
        # Main N-S and E-W boulevards (2 streets)
        streets.append(self._make_main_road(math.pi / 2,
                                            road_type="cobblestone",
                                            width=4))
        streets.append(self._make_main_road(0, road_type="cobblestone",
                                            width=4))
        # Inner ring road at 55% radius (1 street)
        streets.append(self._make_ring_road(0.55, "cobblestone"))
        # Outer ring at 80% (1 street)
        streets.append(self._make_ring_road(0.80, "gravel"))
        # 4-6 connecting lanes from inner ring to outer (was 4 full diagonals)
        diag_angles = [math.pi / 4, 3 * math.pi / 4,
                       5 * math.pi / 4, 7 * math.pi / 4]
        num_lanes = rng.randint(4, 6)
        # Pick from diagonals + optional extra angles
        extra_angles = [math.pi / 6, 5 * math.pi / 6,
                        7 * math.pi / 6, 11 * math.pi / 6]
        all_angles = diag_angles + rng.sample(extra_angles,
                                               k=min(2, num_lanes - 4))
        for ang in all_angles[:num_lanes]:
            a = ang + rng.uniform(-0.12, 0.12)
            inner = r * 0.55
            outer = r * 0.80
            streets.append(Street(
                segments=[self._nudged_seg(
                    cx + int(inner * math.cos(a)),
                    cy + int(inner * math.sin(a)),
                    cx + int(outer * math.cos(a)),
                    cy + int(outer * math.sin(a)))],
                road_type="dirt", width=2))
        # 2-6 grid streets in central area (was 8)
        grid_spacing = max(18, r // 5)
        grid_offsets = [-1, 1] if rng.random() < 0.4 else [-2, -1, 1]
        for offset in grid_offsets:
            d = offset * grid_spacing
            half = int(r * 0.45)
            # Vertical lane
            streets.append(Street(
                segments=[self._nudged_seg(cx + d, cy - half,
                                           cx + d, cy + half)],
                road_type="dirt", width=2))
            # Horizontal lane
            streets.append(Street(
                segments=[self._nudged_seg(cx - half, cy + d,
                                           cx + half, cy + d)],
                road_type="dirt", width=2))
        return streets

    def _castle_streets(self) -> List[Street]:
        cx, cy, r, rng = self._cx, self._cy, self._radius, self._rng
        streets: List[Street] = []
        # Main approach road from south to keep
        streets.append(Street(
            segments=[self._nudged_seg(cx, cy + int(r * 0.85),
                                       cx, cy)],
            road_type="cobblestone", width=3))
        # Second approach from east
        streets.append(Street(
            segments=[self._nudged_seg(cx + int(r * 0.85), cy,
                                       cx, cy)],
            road_type="cobblestone", width=3))
        # Inner bailey ring at 30% radius
        streets.append(self._make_ring_road(0.30, "cobblestone",
                                            n_sides=8))
        # Outer bailey ring at 60% radius
        streets.append(self._make_ring_road(0.60, "gravel", n_sides=12))
        # Connecting lanes from inner to outer ring
        for ang in [0, math.pi / 2, math.pi, 3 * math.pi / 2]:
            a = ang + rng.uniform(-0.1, 0.1)
            streets.append(Street(
                segments=[self._nudged_seg(
                    cx + int(r * 0.30 * math.cos(a)),
                    cy + int(r * 0.30 * math.sin(a)),
                    cx + int(r * 0.60 * math.cos(a)),
                    cy + int(r * 0.60 * math.sin(a)))],
                road_type="gravel", width=2))
        return streets

    # ----- helpers ------------------------------------------------------

    def _make_main_road(self, angle: float, length_frac: float = 0.85,
                        road_type: str = "cobblestone",
                        width: int = 3) -> Street:
        """Create a through-road at *angle* radians from centre."""
        cx, cy, r = self._cx, self._cy, self._radius
        half = int(r * length_frac)
        dx = math.cos(angle)
        dy = math.sin(angle)
        x1 = cx - int(half * dx)
        y1 = cy - int(half * dy)
        x2 = cx + int(half * dx)
        y2 = cy + int(half * dy)
        return Street(
            segments=[self._nudged_seg(x1, y1, x2, y2)],
            road_type=road_type, width=width)

    def _make_ring_road(self, frac: float, road_type: str,
                        n_sides: int = 0) -> Street:
        """Create a polygonal ring road at *frac* of the radius."""
        cx, cy, r = self._cx, self._cy, self._radius
        ring_r = int(r * frac)
        if n_sides <= 0:
            n_sides = max(8, ring_r // 4)
        pts = []
        for i in range(n_sides):
            a = 2 * math.pi * i / n_sides
            px = cx + int(ring_r * math.cos(a))
            py = cy + int(ring_r * math.sin(a))
            pts.append((px, py))
        segments = []
        for i in range(n_sides):
            j = (i + 1) % n_sides
            seg = self._nudged_seg(pts[i][0], pts[i][1],
                                   pts[j][0], pts[j][1])
            segments.append(seg)
        return Street(segments=segments, road_type=road_type, width=2)

    def _nudged_seg(self, x1: int, y1: int,
                    x2: int, y2: int) -> Tuple[int, int, int, int]:
        """Add random offset + terrain-aware adjustment for organic feel.

        Endpoints get +-2 jitter so roads aren't perfectly grid-aligned.
        For longer segments, the midpoint is shifted slightly downhill
        so roads follow terrain contours rather than cutting straight
        across slopes.
        """
        rng = self._rng
        wp = self._wp

        # Endpoint jitter: +-2 tiles (was +-1)
        jx1 = x1 + rng.randint(-2, 2)
        jy1 = y1 + rng.randint(-2, 2)
        jx2 = x2 + rng.randint(-2, 2)
        jy2 = y2 + rng.randint(-2, 2)

        # Terrain-aware midpoint shift for longer segments
        seg_len = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if seg_len > 20 and wp is not None:
            mx = (jx1 + jx2) // 2
            my = (jy1 + jy2) // 2
            # Sample elevation gradient around midpoint
            e_c = wp.get_elevation_fast(mx, my)
            # Check four cardinal neighbours (5 tiles out)
            best_dx, best_dy = 0, 0
            lowest = e_c
            for sdx, sdy in [(5, 0), (-5, 0), (0, 5), (0, -5)]:
                e_n = wp.get_elevation_fast(mx + sdx, my + sdy)
                if e_n < lowest:
                    lowest = e_n
                    best_dx, best_dy = sdx, sdy
            # Shift midpoint partially downhill (contour-following)
            if best_dx != 0 or best_dy != 0:
                shift = rng.randint(1, 3)
                # Nudge perpendicular to the road towards lower ground
                norm = math.sqrt(best_dx ** 2 + best_dy ** 2)
                jx1 += int(shift * best_dx / norm * 0.3)
                jy1 += int(shift * best_dy / norm * 0.3)
                jx2 += int(shift * best_dx / norm * 0.3)
                jy2 += int(shift * best_dy / norm * 0.3)

        return (jx1, jy1, jx2, jy2)

    # ----- filtering ----------------------------------------------------

    def _filter_streets(self, streets: List[Street]) -> List[Street]:
        """Remove segments that cross water or steep slopes."""
        out: List[Street] = []
        for st in streets:
            good_segs = []
            for x1, y1, x2, y2 in st.segments:
                if self._segment_ok(x1, y1, x2, y2):
                    good_segs.append((x1, y1, x2, y2))
            if good_segs:
                out.append(Street(segments=good_segs,
                                  road_type=st.road_type,
                                  width=st.width))
        return out

    def _segment_ok(self, x1: int, y1: int,
                    x2: int, y2: int) -> bool:
        """True if segment avoids water and extreme slopes."""
        wp = self._wp
        water_threshold = 0.25

        # Check endpoints
        e1 = wp.get_elevation_fast(x1, y1)
        e2 = wp.get_elevation_fast(x2, y2)
        if e1 < water_threshold or e2 < water_threshold:
            return False

        # Sample along the segment every 20 tiles (or at least midpoint)
        dist = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        num_samples = max(1, int(dist / 20))
        for i in range(1, num_samples + 1):
            t = i / (num_samples + 1)
            sx = int(x1 + (x2 - x1) * t)
            sy = int(y1 + (y2 - y1) * t)
            if wp.get_elevation_fast(sx, sy) < water_threshold:
                return False

        # Slope check
        if dist > 0 and abs(e2 - e1) / dist > 0.1:
            return False
        return True

    # ----- rasterisation ------------------------------------------------

    def _rasterize_streets(self, streets: List[Street]
                           ) -> Set[Tuple[int, int]]:
        """Turn street segments into a set of tile positions."""
        tiles: Set[Tuple[int, int]] = set()
        for st in streets:
            hw = max(1, st.width // 2)
            for x1, y1, x2, y2 in st.segments:
                dx = x2 - x1
                dy = y2 - y1
                steps = max(abs(dx), abs(dy), 1)
                for s in range(steps + 1):
                    t = s / steps
                    rx = int(x1 + dx * t)
                    ry = int(y1 + dy * t)
                    for ox in range(-hw, hw + 1):
                        for oy in range(-hw, hw + 1):
                            tiles.add((rx + ox, ry + oy))
        return tiles

    # ----- lot placement ------------------------------------------------

    def _lots_along_segment(
        self,
        seg: Tuple[int, int, int, int],
        claimed: Set[Tuple[int, int]],
        road_tiles: Set[Tuple[int, int]],
        rng: random.Random,
    ) -> List[BuildingLot]:
        """Place lots on both sides of a single segment."""
        x1, y1, x2, y2 = seg
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < LOT_WIDTH_MIN + 2:
            return []

        # Unit tangent & perpendicular
        ux, uy = dx / length, dy / length
        # Perpendicular (rotate 90 degrees)
        px, py = -uy, ux

        lots: List[BuildingLot] = []
        cursor = 0.0

        while cursor + LOT_WIDTH_MIN <= length:
            lot_w = rng.randint(LOT_WIDTH_MIN, LOT_WIDTH_MAX)
            lot_w = min(lot_w, int(length - cursor))
            if lot_w < LOT_WIDTH_MIN:
                break

            # Mid-point of this lot along the road
            t_start = cursor
            t_end = cursor + lot_w
            t_mid = (t_start + t_end) / 2

            for side in (1, -1):  # both sides of the street
                lot = self._try_place_street_lot(
                    x1, y1, ux, uy, px * side, py * side,
                    t_start, t_end, lot_w, claimed, road_tiles, rng)
                if lot is not None:
                    lots.append(lot)

            cursor += lot_w + 1  # 1-tile gap between lots

        return lots

    def _try_place_street_lot(
        self,
        ox: int, oy: int,
        ux: float, uy: float,
        px: float, py: float,
        t_start: float, t_end: float,
        lot_w: int,
        claimed: Set[Tuple[int, int]],
        road_tiles: Set[Tuple[int, int]],
        rng: random.Random,
    ) -> Optional[BuildingLot]:
        """Try to place one lot on one side of a street."""
        lot_depth = rng.randint(LOT_DEPTH_MIN, LOT_DEPTH_MAX)
        setback = ROAD_HALF_WIDTH + 2  # 2-tile gap from road centre (was +1)

        # Compute the four corners of the lot rectangle
        corners = []
        for t in (t_start, t_end):
            for d in (setback, setback + lot_depth):
                cx = int(ox + ux * t + px * d)
                cy = int(oy + uy * t + py * d)
                corners.append((cx, cy))

        min_x = min(c[0] for c in corners)
        max_x = max(c[0] for c in corners)
        min_y = min(c[1] for c in corners)
        max_y = max(c[1] for c in corners)
        w = max_x - min_x + 1
        h = max_y - min_y + 1
        if w < 3 or h < 3:
            return None

        # Check radius bounds
        dist = math.sqrt(((min_x + max_x) / 2 - self._cx) ** 2 +
                         ((min_y + max_y) / 2 - self._cy) ** 2)
        if dist > self._radius * 0.92:
            return None

        # Check elevation / water — fine-grained sampling along edges
        # to catch coastline cases the coarse 10-tile elevation cache misses
        wp = self._wp
        water_threshold = 0.25  # slightly above sea level for margin
        check_points = [
            (min_x, min_y), (max_x, min_y),
            (min_x, max_y), (max_x, max_y),
            ((min_x + max_x) // 2, (min_y + max_y) // 2),
        ]
        # Sample midpoints of each edge for finer coverage
        check_points += [
            ((min_x + max_x) // 2, min_y),  # top edge mid
            ((min_x + max_x) // 2, max_y),  # bottom edge mid
            (min_x, (min_y + max_y) // 2),  # left edge mid
            (max_x, (min_y + max_y) // 2),  # right edge mid
        ]
        # For larger lots, add quarter-points along edges
        if w > 8 or h > 8:
            qx1 = min_x + (max_x - min_x) // 4
            qx3 = min_x + 3 * (max_x - min_x) // 4
            qy1 = min_y + (max_y - min_y) // 4
            qy3 = min_y + 3 * (max_y - min_y) // 4
            check_points += [
                (qx1, min_y), (qx3, min_y),
                (qx1, max_y), (qx3, max_y),
                (min_x, qy1), (min_x, qy3),
                (max_x, qy1), (max_x, qy3),
            ]
        for ck_x, ck_y in check_points:
            if wp.get_elevation_fast(ck_x, ck_y) < water_threshold:
                return None

        # Check overlap with road tiles — reject if ANY lot tile is a road
        for ty in range(min_y, max_y + 1):
            for tx in range(min_x, max_x + 1):
                if (tx, ty) in road_tiles:
                    return None

        # Check overlap with claimed tiles (sample corners, edges, centre)
        samples = [
            (min_x, min_y), (max_x, min_y),
            (min_x, max_y), (max_x, max_y),
            ((min_x + max_x) // 2, (min_y + max_y) // 2),
            ((min_x + max_x) // 2, min_y),
            ((min_x + max_x) // 2, max_y),
            (min_x, (min_y + max_y) // 2),
            (max_x, (min_y + max_y) // 2),
        ]
        overlap = sum(1 for s in samples if s in claimed)
        if overlap > 1:
            return None

        # Claim the lot tiles
        for ty in range(min_y, max_y + 1):
            for tx in range(min_x, max_x + 1):
                claimed.add((tx, ty))

        # Determine road_direction from perpendicular
        if abs(px) > abs(py):
            road_dir = "west" if px > 0 else "east"
        else:
            road_dir = "north" if py > 0 else "south"

        return BuildingLot(
            x=min_x, y=min_y, w=w, h=h,
            road_direction=road_dir,
            road_adjacent=True)
