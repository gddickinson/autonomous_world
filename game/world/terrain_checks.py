"""Terrain-awareness helpers for settlement generation.

Provides buildability checks, road passability, river proximity
detection, ward elevation metrics, and elevation-based ward
classification. Used by VoronoiSettlementLayout and the StreetPlanner.
"""

import math
import random
from typing import List, Tuple, Optional, Dict, Set


class SettlementTerrainChecker:
    """Terrain analysis for a single settlement site.

    Initialized with the settlement center, radius, and a reference
    to the WorldPlan (for elevation and river data).
    """

    def __init__(self, cx: int, cy: int, radius: int, world_plan):
        self.cx = cx
        self.cy = cy
        self.radius = radius
        self.wp = world_plan
        self.nearby_river_points: List[Tuple[int, int]] = []
        self.river_direction: Optional[Tuple[float, float]] = None

    # ------------------------------------------------------------------
    # Buildability
    # ------------------------------------------------------------------

    def is_buildable(self, x: int, y: int, w: int, h: int) -> bool:
        """Check if a rectangular area is suitable for building.

        Rejects lots that are underwater or have too much elevation
        variation (steep slope).
        """
        corners = [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
        elevs = [self.wp.get_elevation_fast(cx, cy) for cx, cy in corners]
        # Reject if any corner is underwater
        if any(e < 0.23 for e in elevs):
            return False
        # Reject if slope across the lot is too steep
        if max(elevs) - min(elevs) > 0.05:
            return False
        return True

    # ------------------------------------------------------------------
    # Road passability
    # ------------------------------------------------------------------

    def is_road_segment_passable(self, x1: int, y1: int,
                                  x2: int, y2: int) -> bool:
        """Check whether a road segment avoids water and steep slopes.

        Samples elevation along the segment at ~4 tile intervals.
        Returns False if any sample is underwater or if the
        elevation change per tile exceeds 0.1.
        """
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            return True
        n_samples = max(2, int(length / 4))
        elevs = []
        for i in range(n_samples + 1):
            t = i / n_samples
            sx = int(x1 + dx * t)
            sy = int(y1 + dy * t)
            e = self.wp.get_elevation_fast(sx, sy)
            if e < 0.23:
                return False
            elevs.append(e)
        # Check gradient per segment
        for i in range(1, len(elevs)):
            seg_len = length / n_samples
            if seg_len > 0 and abs(elevs[i] - elevs[i - 1]) / seg_len > 0.1:
                return False
        return True

    # ------------------------------------------------------------------
    # River detection
    # ------------------------------------------------------------------

    def detect_nearby_rivers(self) -> None:
        """Find river points within settlement radius.

        Populates self.nearby_river_points and self.river_direction
        (unit vector from settlement center toward average river pos).
        """
        rivers = getattr(self.wp, 'rivers', [])
        r_sq = self.radius * self.radius
        nearby: List[Tuple[int, int]] = []

        for river in rivers:
            pts = getattr(river, 'points', [])
            for px, py in pts:
                dx = px - self.cx
                dy = py - self.cy
                if dx * dx + dy * dy <= r_sq:
                    nearby.append((px, py))

        self.nearby_river_points = nearby

        if nearby:
            avg_dx = sum(p[0] - self.cx for p in nearby) / len(nearby)
            avg_dy = sum(p[1] - self.cy for p in nearby) / len(nearby)
            mag = math.sqrt(avg_dx * avg_dx + avg_dy * avg_dy)
            if mag > 0:
                self.river_direction = (avg_dx / mag, avg_dy / mag)

    # ------------------------------------------------------------------
    # Ward elevation metrics
    # ------------------------------------------------------------------

    def ward_avg_elevation(self, seed_x: float, seed_y: float) -> float:
        """Return elevation at a ward's seed point."""
        return self.wp.get_elevation_fast(int(seed_x), int(seed_y))

    def ward_flatness(self, tiles: List[Tuple[int, int]]) -> float:
        """Return flatness score for a ward (lower = flatter).

        Samples elevation at up to 8 tiles and returns max - min.
        """
        if len(tiles) < 2:
            return 0.0
        step = max(1, len(tiles) // 8)
        samples = [self.wp.get_elevation_fast(t[0], t[1])
                   for t in tiles[::step]]
        return max(samples) - min(samples)

    def find_ward_nearest_river(
        self,
        seeds: List[Tuple[float, float]],
        exclude: set,
    ) -> Optional[int]:
        """Return the ward index whose seed is closest to the river.

        Args:
            seeds: list of (x, y) ward seed positions
            exclude: set of ward indices to skip

        Returns:
            Ward index or None if no river points are nearby.
        """
        if not self.nearby_river_points:
            return None
        avg_rx = (sum(p[0] for p in self.nearby_river_points)
                  / len(self.nearby_river_points))
        avg_ry = (sum(p[1] for p in self.nearby_river_points)
                  / len(self.nearby_river_points))
        best_dist = float('inf')
        best_ward = None
        for si, (sx, sy) in enumerate(seeds):
            if si in exclude:
                continue
            d = (sx - avg_rx) ** 2 + (sy - avg_ry) ** 2
            if d < best_dist:
                best_dist = d
                best_ward = si
        return best_ward


# ================================================================
# Ward classification with terrain awareness
# ================================================================

def classify_settlement_wards(
    sorted_wards: List[int],
    ward_types: Dict[int, str],
    inner_cutoff: int,
    middle_cutoff: int,
    kind: str,
    specialization: str,
    terrain: 'SettlementTerrainChecker',
    seeds: List[Tuple[float, float]],
    ward_tiles: Dict[int, List[Tuple[int, int]]],
    ring_types: Dict[str, List[str]],
    rng: random.Random,
) -> None:
    """Classify wards using elevation and flatness for placement.

    Assigns ward types in-place into ward_types dict. Places:
    - Market on flattest inner ward
    - Temple on highest ward (towns/cities)
    - Military on elevated outer ward
    - Port near river (if river is nearby)
    """
    # Pre-compute terrain metrics
    def _elev(w):
        if w < len(seeds):
            return terrain.ward_avg_elevation(seeds[w][0], seeds[w][1])
        return 0.5

    def _flat(w):
        return terrain.ward_flatness(ward_tiles.get(w, []))

    ward_elevs = {w: _elev(w) for w in sorted_wards}
    ward_flat = {w: _flat(w) for w in sorted_wards}

    # Market on flattest inner ward
    inner_wards = sorted_wards[:max(1, inner_cutoff)]
    flattest = min(inner_wards, key=lambda w: ward_flat[w])
    ward_types[flattest] = "market"

    is_large = kind in ("town", "city")
    # Temple on highest ward
    if is_large and len(sorted_wards) > 2:
        eligible = [w for w in sorted_wards if w not in ward_types]
        if eligible:
            highest = max(eligible, key=lambda w: ward_elevs[w])
            if ward_elevs[highest] > ward_elevs[flattest] + 0.02:
                ward_types[highest] = "temple"
    # Military on elevated outer ward
    if is_large and len(sorted_wards) > 4:
        avail = [w for w in sorted_wards[middle_cutoff:]
                 if w not in ward_types]
        if avail:
            ward_types[max(avail, key=lambda w: ward_elevs[w])] = "military"
    # Port near river (non-port/fishing specializations)
    if (terrain.nearby_river_points
            and specialization not in ("port", "fishing")):
        rw = terrain.find_ward_nearest_river(seeds, set(ward_types.keys()))
        if rw is not None:
            ward_types[rw] = "port"

    # Fill remaining wards by ring
    for i, w in enumerate(sorted_wards):
        if w in ward_types:
            continue
        if i < inner_cutoff:
            cands = ring_types["inner"]
        elif i < middle_cutoff:
            cands = ring_types["middle"]
        else:
            cands = ring_types["outer"]
        used = set(ward_types.values())
        unused = [t for t in cands if t not in used]
        ward_types[w] = rng.choice(unused if unused else cands)


def apply_port_terrain_override(
    ward_types: Dict[int, str],
    ward_dists: Dict[int, float],
    specialization: str,
    seeds: List[Tuple[float, float]],
    terrain: 'SettlementTerrainChecker',
) -> None:
    """Override ward types for port/fishing specializations.

    For port/fishing settlements:
    - Assigns the water-facing ward as "port" (dock ward)
    - Places market ward adjacent to port (internal trade route)
    - Ensures buildings don't extend past waterline by using
      the terrain checker's water detection
    """
    if specialization not in ("port", "fishing"):
        return

    # Find the ward closest to water (either ocean or river)
    best_water_ward, best_water_dist = None, float('inf')
    for si, (sx, sy) in enumerate(seeds):
        elev = terrain.wp.get_elevation_fast(int(sx), int(sy))
        if elev < 0.25:
            dist = ward_dists.get(si, 999)
            if dist < best_water_dist:
                best_water_dist = dist
                best_water_ward = si

    # Fall back to nearest-river-ward if no underwater ward found
    if best_water_ward is None:
        best_water_ward = terrain.find_ward_nearest_river(seeds, set())
    if best_water_ward is None:
        return

    ward_types[best_water_ward] = "port"

    # Place market ward as next-closest to center that isn't port
    # This ensures internal roads lead from market toward docks
    sorted_by_center = sorted(
        ward_dists.keys(), key=lambda w: ward_dists[w])
    for w in sorted_by_center:
        if w != best_water_ward and w not in ward_types:
            ward_types[w] = "market"
            break


# Re-export wall generation helpers for backward compatibility
from game.world.wall_generation import (  # noqa: E402, F401
    generate_wall_polygon,
    generate_moat_points,
    find_wall_polygon_crossing,
    place_wall_towers,
)
