"""
Procedural Blueprint Generator — creates high-resolution, detailed building plans.

Generates buildings by assembling rooms from templates with:
- Realistic room sizes (6-15 tiles per room dimension)
- Furniture placement based on room purpose
- Corridors, alcoves, and architectural details
- Multiple floors connected by stairs
- Culture-specific architectural styles

Each generated blueprint is a full tile grid ready for the game.
"""

import random
from typing import List, Dict, Tuple, Optional
from game.settings import (WALL, FLOOR, DOOR, TABLE, BED, CHEST, WINDOW,
                           LOCKED_DOOR, STAIRS_UP, STAIRS_DOWN, GRASS,
                           PILLAR, ALTAR, FIREPLACE, THRONE, BOOKSHELF,
                           BARREL, ANVIL, FORGE_FIRE, FOUNTAIN, CARPET,
                           MOSAIC, ARCHWAY, IRON_GATE)
from game.world.buildings import Blueprint

W=WALL; F=FLOOR; D=DOOR; T=TABLE; B=BED; C=CHEST; N=WINDOW; L=LOCKED_DOOR
S=STAIRS_UP; s=STAIRS_DOWN; P=PILLAR; A=ALTAR; H=FIREPLACE; K=THRONE
X=BOOKSHELF; R=BARREL; V=ANVIL; G=FORGE_FIRE; O=FOUNTAIN; Q=CARPET
M=MOSAIC; E=ARCHWAY; I=IRON_GATE; _=GRASS


# ================================================================
# ROOM DEFINITIONS — what to put in each room type
# ================================================================

ROOM_FURNISHINGS = {
    # room_type: [(tile, x_offset, y_offset, probability), ...]
    # Offsets are relative to room interior, placed from top-left
    "great_hall": {
        "min_w": 10, "min_h": 8,
        "features": [
            ("pillar_row", 0.9),    # rows of pillars down the hall
            ("long_tables", 0.8),   # feasting tables
            ("fireplace_wall", 0.9),# fireplace on one wall
            ("carpet_runner", 0.6), # carpet down center
        ],
    },
    "throne_room": {
        "min_w": 10, "min_h": 10,
        "features": [
            ("throne_dais", 1.0),
            ("pillar_row", 0.9),
            ("carpet_runner", 1.0),
            ("mosaic_floor", 0.5),
        ],
    },
    "bedroom_simple": {
        "min_w": 4, "min_h": 4,
        "features": [("bed", 1.0), ("chest", 0.7)],
    },
    "bedroom_noble": {
        "min_w": 6, "min_h": 6,
        "features": [
            ("large_bed", 1.0), ("chest", 1.0), ("carpet_area", 0.8),
            ("fireplace_corner", 0.6), ("bookshelf", 0.3),
        ],
    },
    "kitchen": {
        "min_w": 6, "min_h": 5,
        "features": [
            ("tables", 0.9), ("fireplace_wall", 1.0),
            ("barrel_storage", 0.7),
        ],
    },
    "library": {
        "min_w": 6, "min_h": 6,
        "features": [
            ("bookshelf_walls", 1.0), ("reading_tables", 0.8),
            ("carpet_area", 0.5),
        ],
    },
    "chapel": {
        "min_w": 6, "min_h": 8,
        "features": [
            ("altar_end", 1.0), ("pew_rows", 0.8),
            ("mosaic_floor", 0.6), ("pillar_pair", 0.4),
        ],
    },
    "forge": {
        "min_w": 6, "min_h": 5,
        "features": [
            ("anvil_center", 1.0), ("forge_fire_wall", 1.0),
            ("barrel_storage", 0.6),
        ],
    },
    "shop_front": {
        "min_w": 6, "min_h": 5,
        "features": [
            ("display_tables", 0.9), ("chest_storage", 0.7),
        ],
    },
    "storage": {
        "min_w": 4, "min_h": 4,
        "features": [("barrel_fill", 0.9), ("chest_fill", 0.7)],
    },
    "dungeon_cell": {
        "min_w": 3, "min_h": 3,
        "features": [],
    },
    "courtyard": {
        "min_w": 8, "min_h": 8,
        "features": [("fountain_center", 0.7), ("pillar_corners", 0.5)],
    },
    "guard_room": {
        "min_w": 5, "min_h": 5,
        "features": [("weapon_racks", 0.8), ("table", 0.7)],
    },
    "tavern_common": {
        "min_w": 8, "min_h": 8,
        "features": [
            ("scattered_tables", 1.0), ("fireplace_wall", 0.9),
            ("bar_counter", 0.8), ("pillar_pair", 0.4),
        ],
    },
    "tower_floor": {
        "min_w": 6, "min_h": 6,
        "features": [("bookshelf_walls", 0.6), ("table", 0.7)],
    },
}


def _furnish_room(tiles: list, rx: int, ry: int, rw: int, rh: int,
                  room_type: str, rng: random.Random):
    """Place furniture in a room based on its type."""
    spec = ROOM_FURNISHINGS.get(room_type, {})
    features = spec.get("features", [])

    for feat_name, prob in features:
        if rng.random() > prob:
            continue

        # Interior bounds (1 tile in from walls)
        ix, iy = rx + 1, ry + 1
        iw, ih = rw - 2, rh - 2
        if iw < 2 or ih < 2:
            continue

        if feat_name == "bed":
            bx = ix + rng.randint(0, max(0, iw - 1))
            by = iy + rng.randint(0, max(0, ih - 1))
            tiles[by][bx] = BED

        elif feat_name == "large_bed":
            bx = ix + 1
            by = iy + 1
            tiles[by][bx] = BED
            if bx + 1 < rx + rw - 1:
                tiles[by][bx + 1] = BED

        elif feat_name == "chest":
            cx = ix + rng.randint(0, max(0, iw - 1))
            cy = iy + rng.randint(0, max(0, ih - 1))
            if tiles[cy][cx] == FLOOR:
                tiles[cy][cx] = CHEST

        elif feat_name == "table":
            tx = ix + iw // 2
            ty = iy + ih // 2
            tiles[ty][tx] = TABLE

        elif feat_name == "tables":
            for _ in range(rng.randint(1, 3)):
                tx = ix + rng.randint(0, max(0, iw - 1))
                ty = iy + rng.randint(0, max(0, ih - 1))
                if tiles[ty][tx] == FLOOR:
                    tiles[ty][tx] = TABLE

        elif feat_name == "long_tables":
            # Two long rows of tables
            if iw >= 6:
                for x in range(ix + 2, ix + iw - 2):
                    if tiles[iy + 1][x] == FLOOR:
                        tiles[iy + 1][x] = TABLE
                    if ih > 4 and tiles[iy + ih - 2][x] == FLOOR:
                        tiles[iy + ih - 2][x] = TABLE

        elif feat_name == "scattered_tables":
            count = max(2, (iw * ih) // 8)
            for _ in range(count):
                tx = ix + rng.randint(0, max(0, iw - 1))
                ty = iy + rng.randint(0, max(0, ih - 1))
                if tiles[ty][tx] == FLOOR:
                    tiles[ty][tx] = TABLE

        elif feat_name == "pillar_row":
            if iw >= 6:
                col1 = ix + 2
                col2 = ix + iw - 3
                for y in range(iy + 1, iy + ih - 1, 3):
                    if tiles[y][col1] == FLOOR:
                        tiles[y][col1] = PILLAR
                    if tiles[y][col2] == FLOOR:
                        tiles[y][col2] = PILLAR

        elif feat_name == "pillar_pair":
            if iw >= 4 and ih >= 4:
                tiles[iy + 1][ix + 1] = PILLAR
                tiles[iy + 1][ix + iw - 2] = PILLAR

        elif feat_name == "pillar_corners":
            tiles[iy][ix] = PILLAR
            tiles[iy][ix + iw - 1] = PILLAR
            tiles[iy + ih - 1][ix] = PILLAR
            tiles[iy + ih - 1][ix + iw - 1] = PILLAR

        elif feat_name == "fireplace_wall":
            fx = ix + iw // 2
            tiles[ry + 1][fx] = FIREPLACE

        elif feat_name == "fireplace_corner":
            tiles[ry + 1][rx + 1] = FIREPLACE

        elif feat_name == "carpet_runner":
            mid = ix + iw // 2
            for y in range(iy, iy + ih):
                if tiles[y][mid] == FLOOR:
                    tiles[y][mid] = CARPET
                if mid + 1 < rx + rw - 1 and tiles[y][mid + 1] == FLOOR:
                    tiles[y][mid + 1] = CARPET

        elif feat_name == "carpet_area":
            for dy in range(1, min(4, ih - 1)):
                for dx in range(1, min(4, iw - 1)):
                    if tiles[iy + dy][ix + dx] == FLOOR:
                        tiles[iy + dy][ix + dx] = CARPET

        elif feat_name == "mosaic_floor":
            for y in range(iy, iy + ih):
                for x in range(ix, ix + iw):
                    if tiles[y][x] == FLOOR:
                        tiles[y][x] = MOSAIC

        elif feat_name == "throne_dais":
            mid_x = ix + iw // 2
            mid_y = iy + 1
            tiles[mid_y][mid_x] = THRONE
            for dx in range(-1, 2):
                if tiles[mid_y + 1][mid_x + dx] == FLOOR:
                    tiles[mid_y + 1][mid_x + dx] = CARPET

        elif feat_name == "altar_end":
            mid = ix + iw // 2
            tiles[iy + 1][mid] = ALTAR

        elif feat_name == "pew_rows":
            for y in range(iy + 3, iy + ih - 1, 2):
                for x in range(ix + 1, ix + iw - 1):
                    if tiles[y][x] == FLOOR:
                        tiles[y][x] = TABLE  # pews as tables

        elif feat_name == "bookshelf_walls":
            for x in range(ix, ix + iw):
                if tiles[iy][x] == FLOOR:
                    tiles[iy][x] = BOOKSHELF
            for y in range(iy, iy + ih):
                if tiles[y][ix] == FLOOR:
                    tiles[y][ix] = BOOKSHELF

        elif feat_name == "reading_tables":
            for _ in range(2):
                tx = ix + rng.randint(1, max(1, iw - 2))
                ty = iy + rng.randint(1, max(1, ih - 2))
                if tiles[ty][tx] == FLOOR:
                    tiles[ty][tx] = TABLE

        elif feat_name == "anvil_center":
            tiles[iy + ih // 2][ix + iw // 2] = ANVIL

        elif feat_name == "forge_fire_wall":
            tiles[ry + 1][ix + iw // 2] = FORGE_FIRE

        elif feat_name == "barrel_storage":
            count = rng.randint(2, 4)
            for _ in range(count):
                bx = ix + rng.randint(0, max(0, iw - 1))
                by = iy + rng.randint(0, max(0, ih - 1))
                if tiles[by][bx] == FLOOR:
                    tiles[by][bx] = BARREL

        elif feat_name == "barrel_fill":
            for y in range(iy, iy + ih, 2):
                for x in range(ix, ix + iw, 2):
                    if tiles[y][x] == FLOOR:
                        tiles[y][x] = BARREL

        elif feat_name == "chest_fill":
            for y in range(iy, iy + ih):
                for x in range(ix, ix + iw):
                    if tiles[y][x] == FLOOR and rng.random() < 0.3:
                        tiles[y][x] = CHEST

        elif feat_name == "chest_storage":
            for _ in range(rng.randint(2, 4)):
                cx = ix + rng.randint(0, max(0, iw - 1))
                cy = iy + rng.randint(0, max(0, ih - 1))
                if tiles[cy][cx] == FLOOR:
                    tiles[cy][cx] = CHEST

        elif feat_name == "display_tables":
            for x in range(ix + 1, ix + iw - 1, 2):
                if tiles[iy + 1][x] == FLOOR:
                    tiles[iy + 1][x] = TABLE

        elif feat_name == "fountain_center":
            tiles[iy + ih // 2][ix + iw // 2] = FOUNTAIN

        elif feat_name == "weapon_racks":
            for _ in range(2):
                wx = ix + rng.randint(0, max(0, iw - 1))
                wy = iy + rng.randint(0, max(0, ih - 1))
                if tiles[wy][wx] == FLOOR:
                    tiles[wy][wx] = CHEST  # weapon racks as chests

        elif feat_name == "bar_counter":
            # L-shaped bar counter using tables
            for x in range(ix + iw - 3, ix + iw):
                if tiles[iy + 1][x] == FLOOR:
                    tiles[iy + 1][x] = TABLE
            for y in range(iy + 1, iy + 4):
                if y < ry + rh and tiles[y][ix + iw - 3] == FLOOR:
                    tiles[y][ix + iw - 3] = TABLE


# ================================================================
# PROCEDURAL BUILDING GENERATOR
# ================================================================

def generate_building(building_type: str, seed: int = None,
                      culture: str = "medieval") -> Blueprint:
    """Generate a detailed high-resolution building procedurally.

    Args:
        building_type: castle_keep, wizard_tower, grand_tavern, cathedral,
                      manor_house, merchant_shop, barracks, farmstead, etc.
        seed: random seed for reproducibility
        culture: medieval, roman, greek, tribal, primitive

    Returns a Blueprint with detailed room layouts.
    """
    rng = random.Random(seed)

    generators = {
        "castle_keep": _gen_castle_keep,
        "wizard_tower": _gen_wizard_tower,
        "grand_tavern": _gen_grand_tavern,
        "cathedral": _gen_cathedral,
        "manor_house": _gen_manor_house,
        "merchant_shop": _gen_merchant_shop,
        "large_barracks": _gen_large_barracks,
        "grand_smithy": _gen_grand_smithy,
    }

    gen_fn = generators.get(building_type)
    if gen_fn:
        return gen_fn(rng, culture)

    # Fallback: generate a generic building
    return _gen_generic_house(rng, culture)


def _make_grid(w: int, h: int, fill=WALL) -> list:
    return [[fill for _ in range(w)] for _ in range(h)]


def _carve_room(tiles, rx, ry, rw, rh):
    """Carve a rectangular room."""
    for y in range(ry + 1, ry + rh - 1):
        for x in range(rx + 1, rx + rw - 1):
            if 0 <= y < len(tiles) and 0 <= x < len(tiles[0]):
                tiles[y][x] = FLOOR


def _add_door(tiles, x, y):
    if 0 <= y < len(tiles) and 0 <= x < len(tiles[0]):
        tiles[y][x] = DOOR


def _add_windows(tiles, rx, ry, rw, rh, rng, prob=0.4):
    """Add windows to outer walls of a room."""
    for x in range(rx + 2, rx + rw - 2, 2):
        if rng.random() < prob:
            if ry > 0 and tiles[ry][x] == WALL:
                tiles[ry][x] = WINDOW
        if rng.random() < prob:
            if ry + rh - 1 < len(tiles) and tiles[ry + rh - 1][x] == WALL:
                tiles[ry + rh - 1][x] = WINDOW
    for y in range(ry + 2, ry + rh - 2, 2):
        if rng.random() < prob:
            if rx > 0 and tiles[y][rx] == WALL:
                tiles[y][rx] = WINDOW
        if rng.random() < prob:
            if rx + rw - 1 < len(tiles[0]) and tiles[y][rx + rw - 1] == WALL:
                tiles[y][rx + rw - 1] = WINDOW


# ================================================================
# SPECIFIC BUILDING GENERATORS
# ================================================================

def _gen_castle_keep(rng, culture) -> Blueprint:
    """Generate a large castle keep: 24x28 with great hall, throne room,
    kitchen, bedrooms, library, chapel, guard room, storage, stairs."""
    w, h = 24, 28
    tiles = _make_grid(w, h)

    # Great Hall (top section, full width)
    _carve_room(tiles, 0, 0, w, 10)
    _add_windows(tiles, 0, 0, w, 10, rng)
    _furnish_room(tiles, 0, 0, w, 10, "great_hall", rng)

    # Dividing wall with archways
    for x in range(w):
        tiles[10][x] = WALL
    tiles[10][6] = ARCHWAY
    tiles[10][17] = ARCHWAY

    # Left wing: Throne Room
    _carve_room(tiles, 0, 10, 12, 10)
    _add_windows(tiles, 0, 10, 12, 10, rng)
    _furnish_room(tiles, 0, 10, 12, 10, "throne_room", rng)

    # Right wing: Library + Chapel
    _carve_room(tiles, 12, 10, 12, 5)
    _furnish_room(tiles, 12, 10, 12, 5, "library", rng)
    for x in range(12, 24):
        tiles[15][x] = WALL
    tiles[15][17] = DOOR
    _carve_room(tiles, 12, 15, 12, 5)
    _furnish_room(tiles, 12, 15, 12, 5, "chapel", rng)

    # Bottom section: bedrooms, kitchen, storage
    for x in range(w):
        tiles[20][x] = WALL
    tiles[20][4] = DOOR
    tiles[20][11] = DOOR
    tiles[20][17] = DOOR

    # Kitchen
    _carve_room(tiles, 0, 20, 8, 8)
    _furnish_room(tiles, 0, 20, 8, 8, "kitchen", rng)
    _add_windows(tiles, 0, 20, 8, 8, rng)

    # Noble bedroom
    _carve_room(tiles, 8, 20, 7, 8)
    _furnish_room(tiles, 8, 20, 7, 8, "bedroom_noble", rng)

    # Guard room + stairs
    _carve_room(tiles, 15, 20, 9, 8)
    _furnish_room(tiles, 15, 20, 9, 8, "guard_room", rng)
    tiles[22][21] = STAIRS_UP

    # Entrance at bottom
    tiles[h - 1][w // 2] = DOOR
    tiles[h - 1][w // 2 - 1] = DOOR

    return Blueprint("Castle Keep", "castle", tiles,
                    npc_class="Paladin", npc_count=10,
                    description="A grand castle keep with great hall, throne room, chapel, and library.")


def _gen_wizard_tower(rng, culture) -> Blueprint:
    """Generate a wizard's tower: 14x14 circular-ish with study,
    laboratory, library, bedroom, and observation deck."""
    w, h = 14, 18
    tiles = _make_grid(w, h)

    # Main circular room (study)
    for y in range(1, 9):
        for x in range(1, 13):
            dist = abs(x - 6.5) + abs(y - 4.5)
            if dist < 7:
                tiles[y][x] = FLOOR

    # Furnish study
    tiles[2][7] = TABLE
    tiles[3][4] = BOOKSHELF
    tiles[3][9] = BOOKSHELF
    tiles[4][3] = BOOKSHELF
    tiles[4][10] = BOOKSHELF
    tiles[5][7] = TABLE
    tiles[6][5] = PILLAR
    tiles[6][8] = PILLAR

    # Laboratory (below study)
    _carve_room(tiles, 2, 9, 10, 5)
    tiles[9][7] = DOOR
    tiles[10][4] = TABLE
    tiles[10][8] = TABLE
    tiles[11][3] = BARREL
    tiles[11][9] = BARREL
    tiles[12][6] = FIREPLACE

    # Bedroom + stairs (bottom)
    _carve_room(tiles, 2, 14, 10, 4)
    tiles[14][7] = DOOR
    tiles[15][4] = BED
    tiles[15][5] = BED
    tiles[15][9] = CHEST
    tiles[16][9] = STAIRS_UP
    tiles[16][3] = BOOKSHELF

    # Windows
    for y in [2, 4, 6, 11, 15]:
        if tiles[y][1] == WALL:
            tiles[y][1] = WINDOW
        if tiles[y][12] == WALL:
            tiles[y][12] = WINDOW

    # Entrance
    tiles[h - 1][7] = DOOR

    return Blueprint("Wizard's Tower", "tower", tiles,
                    npc_class="Wizard", npc_count=2,
                    description="A tall wizard's tower with study, laboratory, and observatory.")


def _gen_grand_tavern(rng, culture) -> Blueprint:
    """Generate a large tavern: 20x22 with common room, kitchen,
    multiple bedrooms, cellar access, and stable."""
    w, h = 20, 22
    tiles = _make_grid(w, h)

    # Main common room (top, large)
    _carve_room(tiles, 0, 0, w, 12)
    _add_windows(tiles, 0, 0, w, 12, rng, 0.5)
    _furnish_room(tiles, 0, 0, w, 12, "tavern_common", rng)

    # Dividing wall
    for x in range(w):
        tiles[12][x] = WALL
    tiles[12][5] = ARCHWAY
    tiles[12][14] = ARCHWAY

    # Kitchen (bottom left)
    _carve_room(tiles, 0, 12, 10, 6)
    _furnish_room(tiles, 0, 12, 10, 6, "kitchen", rng)

    # Guest rooms (bottom right)
    _carve_room(tiles, 10, 12, 10, 5)
    # Split into 2 rooms
    for y in range(12, 17):
        tiles[y][15] = WALL
    tiles[14][15] = DOOR
    tiles[13][12] = BED
    tiles[13][18] = BED
    tiles[14][11] = CHEST
    tiles[14][18] = CHEST

    # Storage / cellar access
    _carve_room(tiles, 0, 18, 10, 4)
    tiles[18][5] = DOOR
    for x in range(2, 8, 2):
        tiles[19][x] = BARREL
    tiles[20][3] = STAIRS_DOWN

    # More guest rooms
    _carve_room(tiles, 10, 17, 10, 5)
    tiles[17][14] = DOOR
    tiles[18][12] = BED
    tiles[18][17] = BED
    tiles[19][12] = CHEST
    tiles[20][17] = CHEST

    # Entrance
    tiles[h - 1][w // 2] = DOOR

    return Blueprint("Grand Tavern", "tavern", tiles,
                    npc_class="Bard", npc_count=6,
                    description="A grand tavern with pillared common room, kitchen, and guest rooms.")


def _gen_cathedral(rng, culture) -> Blueprint:
    """Generate a large cathedral: 20x26 with nave, transept,
    altar, side chapels, bell tower access."""
    w, h = 20, 26
    tiles = _make_grid(w, h)

    # Nave (main body)
    _carve_room(tiles, 3, 0, 14, 16)

    # Pillars down the nave
    for y in range(2, 14, 3):
        tiles[y][5] = PILLAR
        tiles[y][14] = PILLAR

    # Mosaic floor in center
    for y in range(2, 14):
        for x in range(7, 13):
            if tiles[y][x] == FLOOR:
                tiles[y][x] = MOSAIC

    # Altar area
    tiles[2][10] = ALTAR
    tiles[3][9] = CARPET
    tiles[3][10] = CARPET
    tiles[3][11] = CARPET

    # Transept (cross arms)
    _carve_room(tiles, 0, 8, 5, 6)
    tiles[11][4] = DOOR
    _carve_room(tiles, 15, 8, 5, 6)
    tiles[11][15] = DOOR

    # Side chapels in transept
    tiles[9][2] = ALTAR
    tiles[9][17] = ALTAR

    # Windows along nave
    for y in range(2, 14, 2):
        tiles[y][3] = WINDOW
        tiles[y][16] = WINDOW

    # Rose window effect at front
    tiles[1][8] = WINDOW
    tiles[1][9] = WINDOW
    tiles[1][10] = WINDOW
    tiles[1][11] = WINDOW

    # Vestry and bell tower
    _carve_room(tiles, 3, 16, 7, 5)
    tiles[16][6] = DOOR
    tiles[17][5] = BOOKSHELF
    tiles[18][5] = CHEST
    tiles[18][8] = TABLE

    _carve_room(tiles, 10, 16, 7, 5)
    tiles[16][13] = DOOR
    tiles[17][14] = STAIRS_UP  # bell tower stairs
    tiles[18][12] = CHEST

    # Narthex (entrance)
    _carve_room(tiles, 3, 21, 14, 5)
    tiles[21][10] = ARCHWAY
    for x in range(5, 15):
        if tiles[22][x] == FLOOR:
            tiles[22][x] = MOSAIC

    tiles[h - 1][10] = DOOR
    tiles[h - 1][9] = DOOR

    return Blueprint("Cathedral", "temple", tiles,
                    npc_class="Cleric", npc_count=6,
                    description="A grand cathedral with columned nave, transept, side chapels, and bell tower.")


def _gen_manor_house(rng, culture) -> Blueprint:
    """Generate a manor house: 18x20 with great hall, solar, kitchen,
    bedrooms, servants quarters, and courtyard."""
    w, h = 18, 20
    tiles = _make_grid(w, h)

    # Great Hall (top center)
    _carve_room(tiles, 2, 0, 14, 8)
    _add_windows(tiles, 2, 0, 14, 8, rng)
    _furnish_room(tiles, 2, 0, 14, 8, "great_hall", rng)

    # Dividing wall
    for x in range(w):
        tiles[8][x] = WALL
    tiles[8][5] = DOOR
    tiles[8][12] = DOOR

    # Solar (lord's private room, left)
    _carve_room(tiles, 0, 8, 9, 6)
    _furnish_room(tiles, 0, 8, 9, 6, "bedroom_noble", rng)
    _add_windows(tiles, 0, 8, 9, 6, rng)

    # Kitchen (right)
    _carve_room(tiles, 9, 8, 9, 6)
    _furnish_room(tiles, 9, 8, 9, 6, "kitchen", rng)

    # Bottom: servants quarters + storage
    for x in range(w):
        tiles[14][x] = WALL
    tiles[14][4] = DOOR
    tiles[14][9] = DOOR
    tiles[14][13] = DOOR

    _carve_room(tiles, 0, 14, 7, 6)
    tiles[15][2] = BED
    tiles[15][4] = BED
    tiles[16][2] = BED
    tiles[16][4] = BED

    _carve_room(tiles, 7, 14, 5, 6)
    tiles[16][9] = STAIRS_UP
    tiles[15][8] = CHEST

    _carve_room(tiles, 12, 14, 6, 6)
    _furnish_room(tiles, 12, 14, 6, 6, "storage", rng)

    tiles[h - 1][9] = DOOR

    return Blueprint("Manor House", "house", tiles,
                    npc_class="Fighter", npc_count=6,
                    description="A lord's manor with great hall, solar, kitchen, and servants' quarters.")


def _gen_merchant_shop(rng, culture) -> Blueprint:
    """Generate a large merchant's shop: 14x16 with shop front,
    workshop, storage, and living quarters above."""
    w, h = 14, 16
    tiles = _make_grid(w, h)

    # Shop front (open to customers)
    _carve_room(tiles, 0, 0, w, 7)
    _add_windows(tiles, 0, 0, w, 7, rng, 0.6)
    _furnish_room(tiles, 0, 0, w, 7, "shop_front", rng)

    # Workshop / back room
    for x in range(w):
        tiles[7][x] = WALL
    tiles[7][7] = DOOR

    _carve_room(tiles, 0, 7, 8, 5)
    tiles[8][2] = TABLE
    tiles[8][5] = TABLE
    tiles[9][3] = CHEST
    tiles[10][2] = BARREL

    # Storage
    _carve_room(tiles, 8, 7, 6, 5)
    tiles[7][10] = LOCKED_DOOR
    _furnish_room(tiles, 8, 7, 6, 5, "storage", rng)

    # Living quarters
    for x in range(w):
        tiles[12][x] = WALL
    tiles[12][4] = DOOR
    tiles[12][10] = DOOR

    _carve_room(tiles, 0, 12, 7, 4)
    tiles[13][2] = BED
    tiles[13][5] = CHEST
    tiles[14][2] = FIREPLACE

    _carve_room(tiles, 7, 12, 7, 4)
    tiles[13][9] = TABLE
    tiles[14][10] = BOOKSHELF
    tiles[14][12] = STAIRS_UP

    tiles[h - 1][7] = DOOR

    return Blueprint("Merchant's Emporium", "shop", tiles,
                    npc_class="Rogue", npc_count=3,
                    description="A large merchant's shop with display room, workshop, and living quarters.")


def _gen_large_barracks(rng, culture) -> Blueprint:
    """Generate a large military barracks: 18x16."""
    w, h = 18, 16
    tiles = _make_grid(w, h)

    # Drill hall
    _carve_room(tiles, 0, 0, w, 8)
    _add_windows(tiles, 0, 0, w, 8, rng)
    tiles[2][5] = PILLAR
    tiles[2][12] = PILLAR
    tiles[5][5] = PILLAR
    tiles[5][12] = PILLAR
    tiles[3][9] = TABLE  # strategy table
    tiles[4][9] = TABLE
    tiles[6][2] = FIREPLACE

    # Bunk rooms
    for x in range(w):
        tiles[8][x] = WALL
    tiles[8][4] = DOOR
    tiles[8][9] = DOOR
    tiles[8][13] = DOOR

    _carve_room(tiles, 0, 8, 7, 4)
    tiles[9][2] = BED; tiles[9][4] = BED
    tiles[10][2] = BED; tiles[10][4] = BED

    _carve_room(tiles, 7, 8, 5, 4)
    tiles[9][9] = BED; tiles[10][9] = BED; tiles[10][10] = CHEST

    _carve_room(tiles, 12, 8, 6, 4)
    tiles[9][14] = BED; tiles[10][14] = BED; tiles[10][16] = CHEST

    # Armory
    _carve_room(tiles, 0, 12, 9, 4)
    tiles[12][4] = LOCKED_DOOR
    tiles[13][2] = CHEST; tiles[13][4] = CHEST; tiles[13][6] = CHEST
    tiles[14][3] = CHEST; tiles[14][5] = CHEST

    # Storage
    _carve_room(tiles, 9, 12, 9, 4)
    tiles[12][13] = DOOR
    tiles[13][11] = BARREL; tiles[13][15] = BARREL
    tiles[14][12] = BARREL; tiles[14][14] = BARREL

    tiles[h - 1][9] = DOOR

    return Blueprint("Grand Barracks", "barracks", tiles,
                    npc_class="Fighter", npc_count=10,
                    description="A large barracks with drill hall, bunk rooms, and locked armory.")


def _gen_grand_smithy(rng, culture) -> Blueprint:
    """Generate a grand blacksmith complex: 16x14."""
    w, h = 16, 14
    tiles = _make_grid(w, h)

    # Main forge room
    _carve_room(tiles, 0, 0, 10, 8)
    _add_windows(tiles, 0, 0, 10, 8, rng)
    tiles[2][5] = ANVIL
    tiles[2][3] = ANVIL
    tiles[3][7] = FORGE_FIRE
    tiles[1][7] = FORGE_FIRE
    tiles[4][3] = TABLE  # workbench
    tiles[5][2] = BARREL  # quench barrel
    tiles[5][7] = BARREL

    # Display / sales room
    _carve_room(tiles, 10, 0, 6, 8)
    tiles[4][10] = DOOR
    tiles[1][12] = TABLE; tiles[1][14] = TABLE
    tiles[3][12] = TABLE; tiles[3][14] = TABLE
    tiles[5][12] = CHEST; tiles[5][14] = CHEST

    # Storage below
    for x in range(w):
        tiles[8][x] = WALL
    tiles[8][5] = DOOR
    tiles[8][12] = DOOR

    _carve_room(tiles, 0, 8, 8, 6)
    tiles[9][2] = BARREL; tiles[9][4] = BARREL; tiles[9][6] = BARREL
    tiles[11][2] = CHEST; tiles[11][4] = CHEST

    _carve_room(tiles, 8, 8, 8, 6)
    tiles[9][10] = BED; tiles[9][14] = FIREPLACE
    tiles[11][10] = TABLE; tiles[11][13] = BOOKSHELF

    tiles[h - 1][5] = DOOR
    tiles[h - 1][12] = DOOR

    return Blueprint("Grand Smithy", "shop", tiles,
                    npc_class="Fighter", npc_count=3,
                    description="A grand blacksmith's forge with dual anvils, sales room, and living quarters.")


def _gen_generic_house(rng, culture) -> Blueprint:
    """Generate a generic detailed house: 12x14."""
    w, h = 12, 14
    tiles = _make_grid(w, h)

    # Main living room
    _carve_room(tiles, 0, 0, w, 7)
    _add_windows(tiles, 0, 0, w, 7, rng)
    tiles[2][6] = TABLE
    tiles[3][6] = TABLE
    tiles[4][3] = FIREPLACE
    tiles[1][3] = FIREPLACE

    # Bedrooms
    for x in range(w):
        tiles[7][x] = WALL
    tiles[7][3] = DOOR
    tiles[7][8] = DOOR

    _carve_room(tiles, 0, 7, 6, 4)
    tiles[8][2] = BED; tiles[9][4] = CHEST

    _carve_room(tiles, 6, 7, 6, 4)
    tiles[8][8] = BED; tiles[9][10] = CHEST

    # Kitchen/storage
    _carve_room(tiles, 0, 11, w, 3)
    tiles[11][3] = DOOR; tiles[11][8] = DOOR
    tiles[12][2] = TABLE; tiles[12][5] = BARREL; tiles[12][9] = BARREL

    tiles[h - 1][6] = DOOR

    return Blueprint("Detailed House", "house", tiles,
                    npc_count=3,
                    description="A well-appointed house with living room, bedrooms, and kitchen.")


# ================================================================
# HISTORICAL BUILDINGS — based on real castle/building plans
# ================================================================

def _gen_dover_keep(rng, culture) -> Blueprint:
    """Based on Dover Castle's Norman Keep (~1180).
    Almost 100ft square, cross-wall divides each floor into two halls.
    Spiral stairs in opposite corners. Wall chambers for privacy/garderobes.
    Ref: timeref.com/castles/norman_square_keep_dover_castle.htm
    """
    w, h = 22, 22
    tiles = _make_grid(w, h)

    # Outer walls already WALL. Carve two great halls divided by cross-wall.
    # West Hall (dining)
    _carve_room(tiles, 0, 0, 11, h)
    # East Hall (sleeping/reception)
    _carve_room(tiles, 11, 0, 11, h)

    # Cross-wall with connecting doors
    for y in range(h):
        tiles[y][11] = WALL
    tiles[5][11] = ARCHWAY
    tiles[10][11] = DOOR
    tiles[16][11] = ARCHWAY

    # Pillar rows in both halls
    for y in range(3, h - 3, 4):
        tiles[y][4] = PILLAR
        tiles[y][7] = PILLAR
        tiles[y][15] = PILLAR
        tiles[y][18] = PILLAR

    # West Hall: dining tables
    for y in range(4, h - 4, 3):
        for x in range(3, 9):
            if tiles[y][x] == FLOOR:
                tiles[y][x] = TABLE

    # East Hall: beds for garrison, lord's area at top
    tiles[2][14] = BED; tiles[2][17] = BED
    tiles[4][14] = BED; tiles[4][17] = BED
    tiles[6][14] = BED; tiles[6][17] = BED
    # Lord's chair/throne at far end
    tiles[2][16] = THRONE
    tiles[3][15] = CARPET; tiles[3][16] = CARPET; tiles[3][17] = CARPET

    # Fireplaces on outer walls
    tiles[1][5] = FIREPLACE
    tiles[1][16] = FIREPLACE
    tiles[h-2][5] = FIREPLACE

    # Wall chambers (carved into thick walls) — garderobes/private rooms
    # NW corner: spiral stair
    tiles[1][1] = STAIRS_UP
    # SE corner: spiral stair
    tiles[h-2][w-2] = STAIRS_UP

    # Chapel in wall thickness (east wall)
    tiles[10][w-2] = ALTAR
    tiles[11][w-2] = FLOOR
    tiles[12][w-2] = FLOOR

    # Storage chests
    tiles[h-3][2] = CHEST; tiles[h-3][3] = CHEST
    tiles[h-3][14] = CHEST; tiles[h-3][15] = CHEST

    # Windows (narrow arrow-slits in thick walls)
    for y in range(3, h - 3, 3):
        tiles[y][0] = WINDOW
        tiles[y][w-1] = WINDOW
    for x in range(3, w - 3, 4):
        tiles[0][x] = WINDOW
        tiles[h-1][x] = WINDOW

    # Entrance via forebuilding (south)
    tiles[h-1][w//2] = DOOR
    tiles[h-1][w//2-1] = DOOR

    return Blueprint("Dover Keep", "castle", tiles,
                    npc_class="Paladin", npc_count=12,
                    description="A massive Norman square keep inspired by Dover Castle (c.1180). "
                                "Two great halls divided by cross-wall, spiral stairs in corners, "
                                "wall chambers, and chapel.")


def _gen_bodiam_castle(rng, culture) -> Blueprint:
    """Based on Bodiam Castle (1385) — concentric plan with courtyard.
    Great hall (24x40ft), kitchen, chapel, buttery, pantry, lord's
    chambers around a central courtyard.
    Ref: great-castles.com/bodiamplan.html, Wikipedia
    """
    w, h = 28, 28
    tiles = _make_grid(w, h)

    # Outer curtain wall is already WALL.
    # Central courtyard
    for y in range(6, 22):
        for x in range(6, 22):
            tiles[y][x] = FLOOR

    # Courtyard fountain
    tiles[14][14] = FOUNTAIN

    # SOUTH RANGE: Great Hall + Kitchen
    # Great Hall (east of center, ~8x12 tiles = 40x60ft)
    _carve_room(tiles, 10, 22, 12, 6)
    _furnish_room(tiles, 10, 22, 12, 6, "great_hall", rng)
    tiles[22][16] = ARCHWAY  # entrance from courtyard

    # Kitchen (west of hall)
    _carve_room(tiles, 1, 22, 9, 6)
    _furnish_room(tiles, 1, 22, 9, 6, "kitchen", rng)
    tiles[22][5] = DOOR  # screens passage
    # Buttery between kitchen and hall
    tiles[24][9] = DOOR
    tiles[24][10] = DOOR  # triple arch (screens passage)

    # EAST RANGE: Chapel + Lord's chambers
    _carve_room(tiles, 22, 6, 6, 8)
    tiles[10][22] = DOOR
    tiles[8][24] = ALTAR
    tiles[9][24] = CARPET
    tiles[7][23] = WINDOW; tiles[7][25] = WINDOW

    # Lord's solar above chapel area
    _carve_room(tiles, 22, 14, 6, 8)
    tiles[18][22] = DOOR
    tiles[15][24] = BED; tiles[15][25] = BED
    tiles[16][24] = CARPET; tiles[16][25] = CARPET
    tiles[17][25] = CHEST
    tiles[14][24] = FIREPLACE

    # WEST RANGE: Retainers' hall + storage
    _carve_room(tiles, 1, 6, 5, 8)
    tiles[10][5] = DOOR
    tiles[7][3] = TABLE; tiles[8][3] = TABLE
    tiles[9][2] = BED; tiles[9][3] = BED

    _carve_room(tiles, 1, 14, 5, 8)
    tiles[18][5] = DOOR
    tiles[15][2] = BARREL; tiles[15][3] = BARREL
    tiles[16][2] = BARREL; tiles[17][2] = CHEST
    tiles[17][3] = CHEST

    # NORTH RANGE: Gatehouse
    _carve_room(tiles, 8, 1, 12, 5)
    tiles[5][14] = ARCHWAY  # gate to courtyard
    tiles[1][14] = IRON_GATE; tiles[1][13] = IRON_GATE  # portcullis
    tiles[2][10] = CHEST; tiles[2][18] = CHEST  # guard stations
    tiles[3][14] = STAIRS_UP  # tower stairs

    # Corner towers (small rooms in corners)
    for cy, cx in [(1,1), (1,w-4), (h-4,1), (h-4,w-4)]:
        _carve_room(tiles, cx, cy, 3, 3)

    # Windows on outer walls
    for y in range(3, h-3, 3):
        tiles[y][0] = WINDOW; tiles[y][w-1] = WINDOW
    for x in range(3, w-3, 4):
        tiles[0][x] = WINDOW; tiles[h-1][x] = WINDOW

    # Main entrance (north)
    tiles[0][13] = DOOR; tiles[0][14] = DOOR

    return Blueprint("Bodiam Castle", "castle", tiles,
                    npc_class="Paladin", npc_count=15,
                    description="A concentric castle inspired by Bodiam Castle (1385). "
                                "Central courtyard with fountain, great hall, chapel with altar, "
                                "lord's solar, kitchen, buttery, gatehouse with portcullis, "
                                "and corner towers.")


def _gen_wizard_tower_tall(rng, culture) -> Blueprint:
    """A tall multi-level wizard's tower based on RPG tower designs.
    Ground: entrance hall + golem guardian. 1st: library.
    2nd: alchemy lab. 3rd: study + scrying. Top: observatory.
    Each floor 10x10, connected by spiral stairs.
    Ref: brehaut.net, angelamaps.com wizard tower layouts
    """
    w, h = 12, 30  # tall and narrow — 5 floors stacked
    tiles = _make_grid(w, h)

    # Floor 1: Entrance Hall (bottom)
    _carve_room(tiles, 1, 24, 10, 6)
    tiles[25][6] = TABLE  # reception desk
    tiles[26][3] = PILLAR; tiles[26][8] = PILLAR
    tiles[27][10] = STAIRS_UP
    tiles[h-1][6] = DOOR  # main entrance
    _add_windows(tiles, 1, 24, 10, 6, rng)

    # Floor 2: Library
    _carve_room(tiles, 1, 18, 10, 6)
    tiles[18][6] = ARCHWAY  # open to below
    for x in range(2, 10):
        tiles[19][x] = BOOKSHELF  # wall of books
    tiles[20][4] = TABLE; tiles[20][7] = TABLE  # reading tables
    tiles[21][3] = BOOKSHELF; tiles[21][8] = BOOKSHELF
    tiles[22][9] = STAIRS_UP
    tiles[22][2] = STAIRS_DOWN

    # Floor 3: Alchemy Laboratory
    _carve_room(tiles, 1, 12, 10, 6)
    tiles[12][6] = ARCHWAY
    tiles[13][4] = TABLE; tiles[13][7] = TABLE  # lab benches
    tiles[14][3] = BARREL; tiles[14][8] = BARREL  # reagent barrels
    tiles[15][5] = FIREPLACE  # heating apparatus
    tiles[15][6] = TABLE  # distillation table
    tiles[16][9] = STAIRS_UP
    tiles[16][2] = STAIRS_DOWN

    # Floor 4: Study + Scrying
    _carve_room(tiles, 1, 6, 10, 6)
    tiles[6][6] = ARCHWAY
    tiles[7][6] = TABLE  # writing desk
    tiles[8][3] = BOOKSHELF; tiles[8][8] = BOOKSHELF
    tiles[9][6] = ALTAR  # scrying crystal/mirror
    tiles[10][9] = STAIRS_UP
    tiles[10][2] = STAIRS_DOWN
    tiles[7][4] = CARPET; tiles[7][5] = CARPET; tiles[7][6] = CARPET; tiles[7][7] = CARPET

    # Floor 5: Observatory/Bedroom (top)
    _carve_room(tiles, 1, 0, 10, 6)
    tiles[1][4] = BED; tiles[1][5] = BED
    tiles[2][8] = CHEST
    tiles[3][6] = TABLE  # star charts
    tiles[4][2] = STAIRS_DOWN
    # Many windows at top for observation
    for x in range(2, 10):
        tiles[0][x] = WINDOW

    return Blueprint("Wizard's Spire", "tower", tiles,
                    npc_class="Wizard", npc_count=2,
                    description="A five-story wizard's tower: entrance hall, library with "
                                "bookshelves, alchemy laboratory, scrying study, and rooftop "
                                "observatory. Based on classic RPG tower designs.")


def _gen_coaching_inn(rng, culture) -> Blueprint:
    """Based on historical medieval coaching inns.
    Courtyard plan: entrance through archway into yard,
    stable on one side, taproom/kitchen on another,
    guest rooms above (simulated on ground floor for gameplay).
    Ref: sffchronicles.com, lostkingdom.net medieval inn layouts
    """
    w, h = 24, 20
    tiles = _make_grid(w, h)

    # Courtyard (center)
    for y in range(5, 15):
        for x in range(5, 19):
            tiles[y][x] = FLOOR

    # Entrance arch (south wall of courtyard)
    tiles[15][12] = ARCHWAY; tiles[15][11] = ARCHWAY

    # EAST WING: Taproom/Common Room
    _carve_room(tiles, 19, 2, 5, 16)
    tiles[10][19] = ARCHWAY  # from courtyard
    # Furnish taproom
    tiles[4][21] = TABLE; tiles[6][21] = TABLE; tiles[8][21] = TABLE
    tiles[10][21] = TABLE; tiles[12][21] = TABLE
    tiles[3][22] = BARREL; tiles[5][22] = BARREL
    tiles[14][22] = BARREL; tiles[14][21] = BARREL
    tiles[3][20] = FIREPLACE
    _add_windows(tiles, 19, 2, 5, 16, rng, 0.3)

    # WEST WING: Stable
    _carve_room(tiles, 0, 2, 5, 16)
    tiles[10][4] = ARCHWAY  # from courtyard
    # Stalls
    for y in range(4, 16, 3):
        tiles[y][2] = WALL  # stall dividers

    # NORTH WING: Kitchen + Private Dining
    _carve_room(tiles, 5, 0, 14, 5)
    tiles[4][12] = DOOR  # from courtyard
    # Kitchen area (left)
    tiles[2][7] = FIREPLACE; tiles[1][7] = FIREPLACE
    tiles[2][9] = TABLE
    tiles[3][7] = BARREL; tiles[3][8] = BARREL
    # Private dining (right)
    for y in range(1, 4):
        tiles[y][13] = WALL
    tiles[2][13] = DOOR
    tiles[2][15] = TABLE; tiles[2][16] = TABLE
    tiles[1][17] = BOOKSHELF

    # SOUTH WING: Guest rooms
    _carve_room(tiles, 5, 15, 14, 5)
    tiles[15][8] = DOOR  # from courtyard
    # Split into 4 guest rooms
    for y in range(15, 20):
        tiles[y][9] = WALL; tiles[y][13] = WALL; tiles[y][17] = WALL
    tiles[17][9] = DOOR; tiles[17][13] = DOOR; tiles[17][17] = DOOR
    tiles[16][6] = BED; tiles[17][7] = CHEST
    tiles[16][11] = BED; tiles[17][12] = CHEST
    tiles[16][15] = BED; tiles[17][16] = CHEST
    tiles[16][19] = BED; tiles[17][19] = CHEST

    # Stairs to upper floor in courtyard
    tiles[6][10] = STAIRS_UP

    # Main entrance (south)
    tiles[h-1][11] = DOOR; tiles[h-1][12] = DOOR

    return Blueprint("Coaching Inn", "tavern", tiles,
                    npc_class="Bard", npc_count=6,
                    description="A large courtyard coaching inn with taproom, stable, "
                                "kitchen with private dining, and four guest rooms. "
                                "Based on historical medieval inn plans.")


def _gen_roman_forum(rng, culture) -> Blueprint:
    """Roman forum/basilica — large public building.
    Columned hall, tribunal at one end, side aisles.
    Ref: Roman basilica architectural plans
    """
    w, h = 26, 18
    tiles = _make_grid(w, h)

    # Main nave
    _carve_room(tiles, 0, 0, w, h)

    # Colonnade (double row of pillars)
    for y in range(2, h - 2, 2):
        tiles[y][4] = PILLAR
        tiles[y][9] = PILLAR
        tiles[y][16] = PILLAR
        tiles[y][21] = PILLAR

    # Side aisles have mosaic
    for y in range(1, h - 1):
        for x in range(1, 4):
            if tiles[y][x] == FLOOR:
                tiles[y][x] = MOSAIC
        for x in range(22, w - 1):
            if tiles[y][x] == FLOOR:
                tiles[y][x] = MOSAIC

    # Central nave floor
    for y in range(2, h - 2):
        for x in range(10, 16):
            if tiles[y][x] == FLOOR:
                tiles[y][x] = CARPET

    # Tribunal/apse at far end
    tiles[1][13] = THRONE
    tiles[2][12] = CARPET; tiles[2][13] = CARPET; tiles[2][14] = CARPET
    tiles[1][10] = PILLAR; tiles[1][16] = PILLAR

    # Entrance (wide, with archways)
    tiles[h-1][10] = ARCHWAY; tiles[h-1][11] = ARCHWAY
    tiles[h-1][14] = ARCHWAY; tiles[h-1][15] = ARCHWAY

    # Fountain in center
    tiles[h // 2][w // 2] = FOUNTAIN

    # Windows along the top (clerestory)
    for x in range(5, w - 5, 2):
        tiles[0][x] = WINDOW

    return Blueprint("Roman Forum", "civic", tiles,
                    npc_count=6,
                    description="A grand Roman basilica/forum with columned nave, "
                                "side aisles with mosaics, tribunal with throne, "
                                "and central fountain.")


def _gen_apothecary_large(rng, culture) -> Blueprint:
    """A large apothecary/herbalist shop with drying room, storage,
    preparation area, and sales counter."""
    w, h = 16, 14
    tiles = _make_grid(w, h)

    # Sales room (front)
    _carve_room(tiles, 0, 0, w, 7)
    _add_windows(tiles, 0, 0, w, 7, rng, 0.5)
    # Display shelves
    tiles[1][2] = BOOKSHELF; tiles[1][4] = BOOKSHELF; tiles[1][6] = BOOKSHELF
    tiles[1][9] = BOOKSHELF; tiles[1][11] = BOOKSHELF; tiles[1][13] = BOOKSHELF
    # Counter
    tiles[4][5] = TABLE; tiles[4][6] = TABLE; tiles[4][7] = TABLE
    tiles[4][8] = TABLE; tiles[4][9] = TABLE; tiles[4][10] = TABLE
    # Samples
    tiles[3][3] = BARREL; tiles[3][12] = BARREL

    # Back room: preparation + drying
    for x in range(w):
        tiles[7][x] = WALL
    tiles[7][5] = DOOR; tiles[7][11] = DOOR

    # Preparation area (left)
    _carve_room(tiles, 0, 7, 8, 7)
    tiles[8][3] = TABLE; tiles[9][3] = TABLE  # prep tables
    tiles[8][6] = FIREPLACE  # heating
    tiles[10][2] = BARREL; tiles[10][5] = BARREL
    tiles[11][2] = CHEST; tiles[11][6] = CHEST

    # Drying/storage room (right)
    _carve_room(tiles, 8, 7, 8, 7)
    tiles[8][10] = BARREL; tiles[8][12] = BARREL; tiles[8][14] = BARREL
    tiles[10][10] = BARREL; tiles[10][12] = BARREL; tiles[10][14] = BARREL
    tiles[12][10] = CHEST; tiles[12][14] = CHEST
    tiles[9][11] = TABLE

    tiles[h-1][5] = DOOR  # back exit
    tiles[h-1][11] = DOOR

    return Blueprint("Grand Apothecary", "shop", tiles,
                    npc_class="Druid", npc_count=2,
                    description="A large apothecary with display shelves, sales counter, "
                                "preparation room with heating, and drying/storage room.")


# ================================================================
# REGISTER NEW GENERATORS
# ================================================================

# Add to the generators dict in generate_building
_EXTRA_GENERATORS = {
    "dover_keep": _gen_dover_keep,
    "bodiam_castle": _gen_bodiam_castle,
    "wizard_spire": _gen_wizard_tower_tall,
    "coaching_inn": _gen_coaching_inn,
    "roman_forum": _gen_roman_forum,
    "apothecary_large": _gen_apothecary_large,
}

# Patch the generate_building function to include new types
_orig_generate = generate_building
def generate_building(building_type: str, seed: int = None,
                      culture: str = "medieval") -> Blueprint:
    rng = random.Random(seed)
    if building_type in _EXTRA_GENERATORS:
        return _EXTRA_GENERATORS[building_type](rng, culture)
    return _orig_generate(building_type, seed, culture)


# ================================================================
# BATCH GENERATOR — create many variations
# ================================================================

def generate_blueprint_set(count: int = 50, seed: int = 42) -> List[Blueprint]:
    """Generate a diverse set of detailed blueprints."""
    rng = random.Random(seed)
    blueprints = []

    types = [
        ("castle_keep", 2), ("dover_keep", 2), ("bodiam_castle", 1),
        ("wizard_tower", 3), ("wizard_spire", 2),
        ("grand_tavern", 3), ("coaching_inn", 2),
        ("cathedral", 2), ("manor_house", 3), ("merchant_shop", 4),
        ("large_barracks", 2), ("grand_smithy", 2),
        ("roman_forum", 1), ("apothecary_large", 2),
    ]

    for btype, variations in types:
        for i in range(min(variations, count - len(blueprints))):
            bp = generate_building(btype, seed=rng.randint(0, 999999))
            bp.name = f"{bp.name} (var {i+1})"
            blueprints.append(bp)

    while len(blueprints) < count:
        bp = generate_building("generic_house", seed=rng.randint(0, 999999))
        bp.name = f"House (var {len(blueprints)})"
        blueprints.append(bp)

    return blueprints
