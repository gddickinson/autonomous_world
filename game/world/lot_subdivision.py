"""Lot Subdivision — subdivide Voronoi wards into building lots along roads.

Places building lots along road frontage first for realistic medieval
street layouts, then falls back to BSP for interior lots.
"""

import math
import random
from typing import List, Tuple, Set, Optional, Dict
from dataclasses import dataclass


# ================================================================
# DATA CLASSES
# ================================================================

@dataclass
class BuildingLot:
    """A rectangular building lot within a ward."""
    x: int
    y: int
    w: int
    h: int
    road_direction: Optional[str]  # "north", "south", "east", "west"
    ward_type: str = ""
    road_adjacent: bool = False


@dataclass
class Region:
    """A rectangular region for recursive subdivision."""
    min_x: int
    min_y: int
    max_x: int
    max_y: int

    @property
    def w(self) -> int:
        return self.max_x - self.min_x

    @property
    def h(self) -> int:
        return self.max_y - self.min_y

    @property
    def area(self) -> int:
        return self.w * self.h


# ================================================================
# CONSTANTS
# ================================================================

MIN_LOT_AREA = 16       # 4x4 tiles minimum
MIN_LOT_SIDE = 4        # at least 4 tiles on each side
MAX_DEPTH = 5           # max recursion depth

# Road-front lot dimensions
ROAD_LOT_DEPTH_MIN = 5   # perpendicular to road
ROAD_LOT_DEPTH_MAX = 8
ROAD_LOT_WIDTH_MIN = 4   # along road
ROAD_LOT_WIDTH_MAX = 7


# ================================================================
# LOT SUBDIVIDER
# ================================================================

class LotSubdivider:
    """Subdivide settlement wards into building lots along roads.

    Primary strategy: place lots along road frontage.
    Fallback: recursive BSP for interior areas.
    """

    def subdivide_ward_road_frontage(
        self,
        ward_tiles: List[Tuple[int, int]],
        road_tiles: Set[Tuple[int, int]],
        rng: random.Random,
        ward_type: str = "",
    ) -> List[BuildingLot]:
        """Subdivide a ward by placing lots along road frontage first.

        1. Find road tiles within/adjacent to this ward
        2. Place building lots on both sides of each road segment
        3. BSP-subdivide remaining interior area
        4. Return all lots, road-adjacent first
        """
        if not ward_tiles:
            return []

        tile_set = set(ward_tiles)
        road_front_lots: List[BuildingLot] = []
        claimed: Set[Tuple[int, int]] = set()

        # Find road tiles that are adjacent to this ward
        ward_adjacent_roads = self._find_ward_road_tiles(
            tile_set, road_tiles)

        if ward_adjacent_roads:
            # Trace connected road segments
            segments = self._trace_road_segments(ward_adjacent_roads)

            for segment in segments:
                lots = self._place_lots_along_segment(
                    segment, tile_set, claimed, rng, ward_type)
                road_front_lots.extend(lots)

        # BSP fallback for remaining interior tiles
        remaining = [t for t in ward_tiles if t not in claimed]
        interior_lots = self._bsp_fallback(
            remaining, tile_set, road_tiles, rng, ward_type)

        # Road-adjacent lots first, then interior
        all_lots = road_front_lots + interior_lots
        all_lots.sort(key=lambda l: (not l.road_adjacent, -l.w * l.h))
        return all_lots

    # kept for backward compatibility
    def subdivide_ward(self, ward_tiles: List[Tuple[int, int]],
                       road_tiles: Set[Tuple[int, int]],
                       rng: random.Random,
                       ward_type: str = ""
                       ) -> List[BuildingLot]:
        """Legacy BSP-only subdivision (kept for compatibility)."""
        return self.subdivide_ward_road_frontage(
            ward_tiles, road_tiles, rng, ward_type)

    # ------------------------------------------------------------------
    # Road detection
    # ------------------------------------------------------------------

    def _find_ward_road_tiles(
        self,
        ward_set: Set[Tuple[int, int]],
        road_tiles: Set[Tuple[int, int]],
    ) -> Set[Tuple[int, int]]:
        """Find road tiles that border this ward."""
        result: Set[Tuple[int, int]] = set()
        for rx, ry in road_tiles:
            # Road tile is relevant if any neighbor is inside the ward
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (rx + dx, ry + dy) in ward_set:
                    result.add((rx, ry))
                    break
        return result

    # ------------------------------------------------------------------
    # Road segment tracing
    # ------------------------------------------------------------------

    def _trace_road_segments(
        self,
        road_tiles: Set[Tuple[int, int]],
    ) -> List[List[Tuple[int, int]]]:
        """Group road tiles into connected, ordered segments.

        Uses flood-fill to find connected components, then orders each
        component along its principal axis for consistent traversal.
        """
        remaining = set(road_tiles)
        segments: List[List[Tuple[int, int]]] = []

        while remaining:
            # Flood-fill one connected component
            start = next(iter(remaining))
            component: List[Tuple[int, int]] = []
            queue = [start]
            visited: Set[Tuple[int, int]] = {start}

            while queue:
                cx, cy = queue.pop()
                component.append((cx, cy))
                remaining.discard((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nb = (cx + dx, cy + dy)
                    if nb in remaining and nb not in visited:
                        visited.add(nb)
                        queue.append(nb)

            if len(component) < 2:
                continue

            # Order tiles along the principal direction
            component = self._order_segment(component)
            segments.append(component)

        return segments

    def _order_segment(
        self,
        tiles: List[Tuple[int, int]],
    ) -> List[Tuple[int, int]]:
        """Order a connected set of road tiles from one end to the other.

        Walk from the tile with the fewest neighbors (an endpoint) using
        a greedy nearest-unvisited strategy.
        """
        tile_set = set(tiles)

        # Find endpoint: tile with fewest road neighbors
        def neighbor_count(t):
            return sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                       if (t[0] + dx, t[1] + dy) in tile_set)

        start = min(tiles, key=neighbor_count)

        ordered = [start]
        visited = {start}
        current = start
        while len(ordered) < len(tiles):
            # Find nearest unvisited neighbor
            best = None
            best_dist = float('inf')
            for t in tiles:
                if t in visited:
                    continue
                d = abs(t[0] - current[0]) + abs(t[1] - current[1])
                if d < best_dist:
                    best_dist = d
                    best = t
            if best is None:
                break
            ordered.append(best)
            visited.add(best)
            current = best

        return ordered

    # ------------------------------------------------------------------
    # Lot placement along road segments
    # ------------------------------------------------------------------

    def _place_lots_along_segment(
        self,
        segment: List[Tuple[int, int]],
        ward_set: Set[Tuple[int, int]],
        claimed: Set[Tuple[int, int]],
        rng: random.Random,
        ward_type: str,
    ) -> List[BuildingLot]:
        """Place building lots on both sides of a road segment."""
        lots: List[BuildingLot] = []
        seg_len = len(segment)
        i = 0

        while i < seg_len:
            # Determine lot width along road (tiles consumed)
            lot_w = rng.randint(ROAD_LOT_WIDTH_MIN, ROAD_LOT_WIDTH_MAX)
            lot_w = min(lot_w, seg_len - i)
            if lot_w < ROAD_LOT_WIDTH_MIN:
                break

            # Segment slice for this lot
            seg_slice = segment[i:i + lot_w]

            # Compute road direction (tangent vector)
            rx0, ry0 = seg_slice[0]
            rx1, ry1 = seg_slice[-1]
            tdx = rx1 - rx0
            tdy = ry1 - ry0

            # Perpendicular directions (two sides of road)
            if abs(tdx) >= abs(tdy):
                # Road runs mostly east-west → lots go north and south
                perp_sides = [
                    ((0, -1), "south"),  # lot north of road, faces south
                    ((0,  1), "north"),  # lot south of road, faces north
                ]
            else:
                # Road runs mostly north-south → lots go east and west
                perp_sides = [
                    ((-1, 0), "east"),   # lot west of road, faces east
                    (( 1, 0), "west"),   # lot east of road, faces west
                ]

            for (pdx, pdy), road_dir in perp_sides:
                lot = self._try_place_lot(
                    seg_slice, pdx, pdy, road_dir,
                    ward_set, claimed, rng, ward_type)
                if lot is not None:
                    lots.append(lot)

            i += lot_w

        return lots

    def _try_place_lot(
        self,
        road_slice: List[Tuple[int, int]],
        perp_dx: int,
        perp_dy: int,
        road_direction: str,
        ward_set: Set[Tuple[int, int]],
        claimed: Set[Tuple[int, int]],
        rng: random.Random,
        ward_type: str,
    ) -> Optional[BuildingLot]:
        """Try to place a single lot perpendicular to a road slice.

        Returns a BuildingLot or None if it doesn't fit.
        """
        lot_depth = rng.randint(ROAD_LOT_DEPTH_MIN, ROAD_LOT_DEPTH_MAX)

        # Compute candidate rectangle from the road slice
        # Start 1 tile away from road (setback for entrance)
        xs = []
        ys = []
        for rx, ry in road_slice:
            for d in range(1, lot_depth + 1):
                tx = rx + perp_dx * d
                ty = ry + perp_dy * d
                xs.append(tx)
                ys.append(ty)

        if not xs:
            return None

        lot_x = min(xs)
        lot_y = min(ys)
        lot_x2 = max(xs) + 1
        lot_y2 = max(ys) + 1
        lot_w = lot_x2 - lot_x
        lot_h = lot_y2 - lot_y

        if lot_w < MIN_LOT_SIDE or lot_h < MIN_LOT_SIDE:
            return None

        # Verify most tiles are inside the ward and not already claimed
        total = 0
        valid = 0
        for ty in range(lot_y, lot_y2):
            for tx in range(lot_x, lot_x2):
                total += 1
                if (tx, ty) in ward_set and (tx, ty) not in claimed:
                    valid += 1

        if total == 0 or valid / total < 0.6:
            return None

        # Claim the tiles
        for ty in range(lot_y, lot_y2):
            for tx in range(lot_x, lot_x2):
                claimed.add((tx, ty))

        return BuildingLot(
            x=lot_x, y=lot_y,
            w=lot_w, h=lot_h,
            road_direction=road_direction,
            ward_type=ward_type,
            road_adjacent=True,
        )

    # ------------------------------------------------------------------
    # BSP fallback for interior lots
    # ------------------------------------------------------------------

    def _bsp_fallback(
        self,
        remaining_tiles: List[Tuple[int, int]],
        ward_set: Set[Tuple[int, int]],
        road_tiles: Set[Tuple[int, int]],
        rng: random.Random,
        ward_type: str,
    ) -> List[BuildingLot]:
        """BSP-subdivide remaining interior area not on roads."""
        if len(remaining_tiles) < MIN_LOT_AREA:
            return []

        min_x = min(t[0] for t in remaining_tiles)
        max_x = max(t[0] for t in remaining_tiles)
        min_y = min(t[1] for t in remaining_tiles)
        max_y = max(t[1] for t in remaining_tiles)

        tile_set = set(remaining_tiles)
        initial = Region(min_x, min_y, max_x + 1, max_y + 1)
        regions = self._subdivide(initial, tile_set, rng, depth=0)

        lots = []
        for region in regions:
            if region.w < MIN_LOT_SIDE or region.h < MIN_LOT_SIDE:
                continue
            if region.area < MIN_LOT_AREA:
                continue

            # Coverage check
            samples = [
                (region.min_x, region.min_y),
                (region.max_x - 1, region.min_y),
                (region.min_x, region.max_y - 1),
                (region.max_x - 1, region.max_y - 1),
                ((region.min_x + region.max_x) // 2,
                 (region.min_y + region.max_y) // 2),
            ]
            ward_hits = sum(1 for s in samples if s in tile_set)
            if ward_hits < 2:
                continue

            road_dir = self._find_road_direction(region, road_tiles)
            lots.append(BuildingLot(
                x=region.min_x, y=region.min_y,
                w=region.w, h=region.h,
                road_direction=road_dir,
                ward_type=ward_type,
                road_adjacent=road_dir is not None,
            ))

        return lots

    # ------------------------------------------------------------------
    # Recursive BSP subdivision
    # ------------------------------------------------------------------

    def _subdivide(self, region: Region,
                   tile_set: Set[Tuple[int, int]],
                   rng: random.Random,
                   depth: int = 0) -> List[Region]:
        """Recursively subdivide a region into lots."""
        if region.area < MIN_LOT_AREA * 2 or depth >= MAX_DEPTH:
            return [region]

        if region.w < MIN_LOT_SIDE * 2 and region.h < MIN_LOT_SIDE * 2:
            return [region]

        w = region.w
        h = region.h

        if w >= h and w >= MIN_LOT_SIDE * 2:
            offset = rng.randint(-max(1, w // 8), max(1, w // 8))
            split_x = (region.min_x + region.max_x) // 2 + offset
            split_x = max(region.min_x + MIN_LOT_SIDE,
                          min(region.max_x - MIN_LOT_SIDE, split_x))
            left = Region(region.min_x, region.min_y,
                          split_x, region.max_y)
            right = Region(split_x, region.min_y,
                           region.max_x, region.max_y)
            return (self._subdivide(left, tile_set, rng, depth + 1) +
                    self._subdivide(right, tile_set, rng, depth + 1))

        elif h >= MIN_LOT_SIDE * 2:
            offset = rng.randint(-max(1, h // 8), max(1, h // 8))
            split_y = (region.min_y + region.max_y) // 2 + offset
            split_y = max(region.min_y + MIN_LOT_SIDE,
                          min(region.max_y - MIN_LOT_SIDE, split_y))
            top = Region(region.min_x, region.min_y,
                         region.max_x, split_y)
            bottom = Region(region.min_x, split_y,
                            region.max_x, region.max_y)
            return (self._subdivide(top, tile_set, rng, depth + 1) +
                    self._subdivide(bottom, tile_set, rng, depth + 1))

        return [region]

    # ------------------------------------------------------------------
    # Road direction detection
    # ------------------------------------------------------------------

    def _find_road_direction(self, region: Region,
                             road_tiles: Set[Tuple[int, int]]
                             ) -> Optional[str]:
        """Determine which side of a lot faces a road."""
        if not road_tiles:
            return None

        sides = {"north": 0, "south": 0, "east": 0, "west": 0}

        for tx in range(region.min_x, region.max_x):
            if (tx, region.min_y - 1) in road_tiles:
                sides["north"] += 1
        for tx in range(region.min_x, region.max_x):
            if (tx, region.max_y) in road_tiles:
                sides["south"] += 1
        for ty in range(region.min_y, region.max_y):
            if (region.min_x - 1, ty) in road_tiles:
                sides["west"] += 1
        for ty in range(region.min_y, region.max_y):
            if (region.max_x, ty) in road_tiles:
                sides["east"] += 1

        best_dir = max(sides, key=sides.get)
        if sides[best_dir] > 0:
            return best_dir
        return None


# Re-export road utilities for convenience
from game.world.road_utils import (  # noqa: E402, F401
    rasterize_road_segments,
    compute_building_setback,
)
