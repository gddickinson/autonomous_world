"""Building interior furnishing -- places profession-specific furniture.

When a building is stamped without a blueprint (fallback box), this module
adds appropriate furniture tiles based on the building's kind field.

Each furnishing function receives the chunk tile array, the building dict,
and the chunk origin (x0, y0) so it can write furniture directly into the
correct local positions.
"""

import random
from game.settings import (
    FLOOR, WALL, DOOR, TABLE, BED, CHEST, FIREPLACE, BOOKSHELF, BARREL,
    ANVIL, FORGE_FIRE, ALTAR, THRONE, CARPET, MOSAIC, ARCHWAY, FOUNTAIN,
    PILLAR, WINDOW, STABLE_FLOOR,
)
from game.world.chunk import CHUNK_SIZE


# ================================================================
# Furniture layouts by building kind
# ================================================================
# Each entry is a list of (tile_type, rel_x_frac, rel_y_frac) where
# fractions are relative to the interior space (excluding walls).
# Positions are clamped to valid interior cells.

_FURNITURE_TAVERN = [
    # Common room: tables scattered
    (TABLE, 0.25, 0.25),
    (TABLE, 0.75, 0.25),
    (TABLE, 0.25, 0.55),
    (TABLE, 0.75, 0.55),
    # Bar counter near top wall
    (TABLE, 0.50, 0.10),
    # Fireplace on a wall
    (FIREPLACE, 0.10, 0.10),
    # Storage
    (BARREL, 0.90, 0.10),
    (BARREL, 0.90, 0.20),
]

_FURNITURE_BLACKSMITH = [
    # Forge area
    (FORGE_FIRE, 0.20, 0.20),
    (ANVIL, 0.40, 0.20),
    # Workbench
    (TABLE, 0.20, 0.50),
    # Storage
    (BARREL, 0.80, 0.20),
    (BARREL, 0.80, 0.35),
    (CHEST, 0.80, 0.70),
]

_FURNITURE_TEMPLE = [
    # Altar at center-front
    (ALTAR, 0.50, 0.30),
    # Benches (using tables as pews) in rows
    (TABLE, 0.30, 0.55),
    (TABLE, 0.70, 0.55),
    (TABLE, 0.30, 0.70),
    (TABLE, 0.70, 0.70),
    # Decorative carpet down the aisle
    (CARPET, 0.50, 0.50),
    (CARPET, 0.50, 0.65),
    (CARPET, 0.50, 0.80),
    # Pillar flanking altar
    (PILLAR, 0.25, 0.30),
    (PILLAR, 0.75, 0.30),
]

_FURNITURE_SHOP = [
    # Shelves along walls (bookshelves as shelving)
    (BOOKSHELF, 0.15, 0.15),
    (BOOKSHELF, 0.15, 0.35),
    (BOOKSHELF, 0.85, 0.15),
    (BOOKSHELF, 0.85, 0.35),
    # Counter near front
    (TABLE, 0.40, 0.70),
    (TABLE, 0.60, 0.70),
    # Storage in back
    (CHEST, 0.15, 0.55),
    (BARREL, 0.85, 0.55),
]

_FURNITURE_BARRACKS = [
    # Beds in rows
    (BED, 0.20, 0.20),
    (BED, 0.20, 0.45),
    (BED, 0.20, 0.70),
    (BED, 0.50, 0.20),
    (BED, 0.50, 0.45),
    (BED, 0.50, 0.70),
    # Weapon rack (chest) at end
    (CHEST, 0.80, 0.20),
    (CHEST, 0.80, 0.50),
    # Table for meals
    (TABLE, 0.80, 0.80),
]

_FURNITURE_LIBRARY = [
    # Bookshelves along walls
    (BOOKSHELF, 0.15, 0.15),
    (BOOKSHELF, 0.15, 0.35),
    (BOOKSHELF, 0.15, 0.55),
    (BOOKSHELF, 0.85, 0.15),
    (BOOKSHELF, 0.85, 0.35),
    (BOOKSHELF, 0.85, 0.55),
    # Reading tables in center
    (TABLE, 0.50, 0.35),
    (TABLE, 0.50, 0.60),
]

_FURNITURE_HOUSE = [
    (BED, 0.20, 0.20),
    (TABLE, 0.55, 0.45),
    (CHEST, 0.80, 0.20),
    (FIREPLACE, 0.80, 0.75),
]

_FURNITURE_CASTLE = [
    (THRONE, 0.50, 0.25),
    (CARPET, 0.50, 0.40),
    (CARPET, 0.50, 0.55),
    (CARPET, 0.50, 0.70),
    (PILLAR, 0.20, 0.30),
    (PILLAR, 0.80, 0.30),
    (PILLAR, 0.20, 0.60),
    (PILLAR, 0.80, 0.60),
    (TABLE, 0.30, 0.80),
    (TABLE, 0.70, 0.80),
    (FIREPLACE, 0.15, 0.15),
]

_FURNITURE_UTILITY = [
    # Generic utility: some barrels and a table
    (BARREL, 0.20, 0.25),
    (BARREL, 0.20, 0.45),
    (TABLE, 0.60, 0.40),
    (CHEST, 0.80, 0.25),
]

_FURNITURE_STORAGE = [
    (BARREL, 0.20, 0.20),
    (BARREL, 0.40, 0.20),
    (BARREL, 0.60, 0.20),
    (BARREL, 0.20, 0.45),
    (CHEST, 0.60, 0.45),
    (CHEST, 0.80, 0.45),
    (BARREL, 0.40, 0.70),
]

_FURNITURE_CIVIC = [
    (TABLE, 0.50, 0.35),
    (TABLE, 0.50, 0.55),
    (BOOKSHELF, 0.15, 0.20),
    (BOOKSHELF, 0.85, 0.20),
    (CHEST, 0.15, 0.75),
    (CARPET, 0.50, 0.45),
]

# Map building kind -> furniture list
_KIND_FURNITURE = {
    "tavern":  _FURNITURE_TAVERN,
    "shop":    _FURNITURE_SHOP,
    "temple":  _FURNITURE_TEMPLE,
    "military": _FURNITURE_BARRACKS,
    "house":   _FURNITURE_HOUSE,
    "castle":  _FURNITURE_CASTLE,
    "utility": _FURNITURE_UTILITY,
    "storage": _FURNITURE_STORAGE,
    "civic":   _FURNITURE_LIBRARY,
    "port":    _FURNITURE_UTILITY,
}


def furnish_building(tiles, bld: dict, x0: int, y0: int) -> None:
    """Place furniture tiles inside a fallback (box) building.

    Only touches tiles that are currently FLOOR inside the building
    interior (not walls, doors, or windows). Skips placements that
    fall outside the chunk or on non-floor tiles.

    Args:
        tiles: numpy chunk tile array (CHUNK_SIZE x CHUNK_SIZE)
        bld: building dict with keys 'kind', 'x', 'y', 'w', 'h'
        x0, y0: world-coordinate origin of this chunk
    """
    kind = bld.get("kind", "house")
    bx, by = bld["x"], bld["y"]
    bw, bh = bld["w"], bld["h"]

    # Interior bounds (1 tile in from walls)
    interior_w = bw - 2
    interior_h = bh - 2
    if interior_w < 2 or interior_h < 2:
        return  # building too small for furniture

    furniture = _KIND_FURNITURE.get(kind, _FURNITURE_HOUSE)

    for tile_type, fx, fy in furniture:
        # Convert fractional position to interior tile coordinate
        ix = int(fx * (interior_w - 1))
        iy = int(fy * (interior_h - 1))
        # Clamp to interior
        ix = max(0, min(interior_w - 1, ix))
        iy = max(0, min(interior_h - 1, iy))

        # World coordinate (offset by 1 for wall)
        wx = bx + 1 + ix
        wy = by + 1 + iy

        # Local chunk coordinate
        lx = wx - x0
        ly = wy - y0

        if 0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE:
            if tiles[ly, lx] == FLOOR:
                tiles[ly, lx] = tile_type
