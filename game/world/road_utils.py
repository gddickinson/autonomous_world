"""Road utilities — rasterize road segments and compute building setback.

Shared by lot_subdivision and voronoi_layout for road-frontage building
placement.
"""

from typing import List, Tuple, Set, Optional


def rasterize_road_segments(
    road_segments: List[Tuple[int, int, int, int, str]],
) -> Set[Tuple[int, int]]:
    """Rasterize road line segments into a set of tile positions.

    Walks each (x1, y1, x2, y2, road_type) segment and expands to
    ~3-tile width for road body.
    """
    tiles: Set[Tuple[int, int]] = set()

    for x1, y1, x2, y2, _rtype in road_segments:
        dx = x2 - x1
        dy = y2 - y1
        steps = max(abs(dx), abs(dy), 1)
        for s in range(steps + 1):
            t = s / steps
            rx = int(x1 + dx * t)
            ry = int(y1 + dy * t)
            for ox in range(-1, 2):
                for oy in range(-1, 2):
                    tiles.add((rx + ox, ry + oy))

    return tiles


def compute_building_setback(
    lot_x: int, lot_y: int,
    lot_w: int, lot_h: int,
    bw: int, bh: int,
    road_direction: Optional[str],
) -> Tuple[int, int]:
    """Position a building within its lot, set back from the road edge.

    The building entrance faces road_direction; the building body is
    pushed to the far side of the lot with a 1-tile yard in front.

    Returns (bx, by) — top-left corner of the building.
    """
    setback = 1

    if road_direction == "north":
        bx = lot_x + (lot_w - bw) // 2
        by = lot_y + setback
    elif road_direction == "south":
        bx = lot_x + (lot_w - bw) // 2
        by = lot_y + lot_h - bh - setback
    elif road_direction == "west":
        bx = lot_x + setback
        by = lot_y + (lot_h - bh) // 2
    elif road_direction == "east":
        bx = lot_x + lot_w - bw - setback
        by = lot_y + (lot_h - bh) // 2
    else:
        bx = lot_x + (lot_w - bw) // 2
        by = lot_y + (lot_h - bh) // 2

    bx = max(lot_x, min(bx, lot_x + lot_w - bw))
    by = max(lot_y, min(by, lot_y + lot_h - bh))
    return bx, by
