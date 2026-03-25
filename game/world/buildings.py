"""
Building blueprint library - D&D-scale floor plans as tile arrays.

Scale: 1 tile = 5 feet. Characters are 1 tile wide.
D&D standard: rooms are 10-50ft per side (2-10 tiles interior).

Buildings are designed with:
- Walls only on the outer perimeter (1 tile thick)
- Interior walls use doors for connections between rooms
- Furniture placed realistically (beds in bedrooms, tables in dining areas)
- Multiple rooms for larger buildings
- Adequate interior space for characters to move

Sources: D&D 5e grid standard (5ft/square), DMG Appendix A room sizes,
historical medieval building proportions.
"""

import random
from typing import List, Tuple, Dict, Optional
from game.settings import (WALL, FLOOR, DOOR, TABLE, BED, CHEST,
                            STAIRS_UP, STAIRS_DOWN, ROAD, GRASS, BUILT_WALL, BUILT_FLOOR,
                            WINDOW, LOCKED_DOOR, BARREL, ANVIL, STABLE_FLOOR, FIREPLACE,
                            BRIDGE, WELL, WHEAT_FIELD, FARMLAND, FOUNTAIN, THRONE,
                            BOOKSHELF, CARPET, MOSAIC, ARCHWAY)

W = WALL
F = FLOOR
D = DOOR
T = TABLE
B = BED
C = CHEST
S = STAIRS_UP
N = WINDOW       # window - lets light through, can't walk through
L = LOCKED_DOOR  # locked door - needs key or lockpick
_ = GRASS
R = BARREL       # barrel for storage buildings
A = ANVIL        # anvil for workshops
K = STABLE_FLOOR # stable floor
P = FIREPLACE    # fireplace


class Blueprint:
    """A building blueprint with metadata."""
    __slots__ = ('name', 'kind', 'tiles', 'width', 'height', 'door_pos',
                 'npc_class', 'npc_race', 'npc_count', 'description')

    def __init__(self, name: str, kind: str, tiles: List[List[int]],
                 npc_class: str = "", npc_race: str = "", npc_count: int = 1,
                 description: str = ""):
        self.name = name
        self.kind = kind
        self.tiles = tiles
        self.height = len(tiles)
        self.width = len(tiles[0]) if tiles else 0
        self.npc_class = npc_class
        self.npc_race = npc_race
        self.npc_count = npc_count
        self.description = description
        self.door_pos = []
        for y, row in enumerate(tiles):
            for x, cell in enumerate(row):
                if cell == D:
                    self.door_pos.append((x, y))

    def rotated(self) -> 'Blueprint':
        rows = len(self.tiles)
        cols = len(self.tiles[0]) if self.tiles else 0
        new_tiles = [[self.tiles[rows - 1 - j][i] for j in range(rows)] for i in range(cols)]
        return Blueprint(self.name, self.kind, new_tiles,
                        self.npc_class, self.npc_race, self.npc_count, self.description)

    def get_floor_positions(self) -> List[Tuple[int, int]]:
        return [(x, y) for y, row in enumerate(self.tiles)
                for x, cell in enumerate(row) if cell == F]


# ================================================================
# BUILDING TEMPLATES - realistic D&D-scale layouts
# Interiors are spacious: 3x3 minimum room, most rooms 4x4+
# ================================================================

# --- Cottages (6x8 exterior, ~20x30ft) ---
COTTAGE = Blueprint("Cottage", "house", [
    [W, W, N, W, W, W, N, W],
    [W, F, F, F, W, F, B, W],
    [N, F, F, F, D, F, F, N],
    [W, F, T, F, W, F, F, W],
    [W, F, F, F, W, W, W, W],
    [W, W, W, D, W, _, _, _],
], npc_count=2, description="A cozy two-room cottage with bedroom.")

COTTAGE_2 = Blueprint("Farmhouse", "house", [
    [W, W, N, W, W, N, W, W],
    [W, F, F, F, F, F, F, W],
    [N, F, F, F, F, F, F, N],
    [W, F, T, F, W, B, F, W],
    [W, F, F, F, D, F, C, W],
    [W, W, W, D, W, W, W, W],
], npc_class="Druid", npc_count=2, description="A sturdy farmhouse.")

# --- Houses (8x10, ~35x45ft, 3 rooms) ---
HOUSE = Blueprint("House", "house", [
    [W, W, N, W, W, W, W, N, W, W],
    [W, F, F, F, F, W, B, F, F, W],
    [N, F, F, F, F, D, F, F, F, N],
    [W, F, F, T, F, W, F, F, C, W],
    [W, F, F, F, F, W, W, D, W, W],
    [W, W, W, L, W, W, F, F, F, W],
    [_, _, _, _, _, N, F, F, F, N],
    [_, _, _, _, _, W, W, W, D, W],
], npc_count=2, description="A comfortable three-room house.")

HOUSE_2 = Blueprint("Townhouse", "house", [
    [W, W, W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, F, F, W],
    [W, F, T, F, F, F, F, T, F, W],
    [W, W, W, W, D, W, W, W, W, W],
    [W, B, F, F, F, F, F, B, F, W],
    [W, F, F, C, F, F, C, F, F, W],
    [W, W, W, W, D, W, W, W, W, W],
], npc_count=3, description="A two-story townhouse.")

# --- Mansion (12x14, ~55x65ft, 6+ rooms) ---
MANSION = Blueprint("Mansion", "house", [
    [W, W, W, W, W, W, W, W, W, W, W, W, W, W],
    [W, F, F, F, F, W, F, F, F, F, F, F, F, W],
    [W, F, F, F, F, D, F, F, F, F, F, F, F, W],
    [W, F, B, F, F, W, F, F, T, F, F, T, F, W],
    [W, F, F, F, F, W, F, F, F, F, F, F, F, W],
    [W, W, W, D, W, W, F, F, F, F, F, F, F, W],
    [W, F, F, F, F, W, W, W, W, D, W, W, W, W],
    [W, F, F, F, F, D, F, F, F, F, F, F, F, W],
    [W, F, B, F, F, W, F, F, F, F, F, F, F, W],
    [W, F, F, C, F, W, F, B, F, W, F, B, F, W],
    [W, W, W, W, W, W, F, F, F, D, F, F, S, W],
    [_, _, _, _, _, W, W, W, W, W, W, W, W, W],
], npc_class="Fighter", npc_count=4, description="A grand mansion with many rooms.")

# --- Blacksmith (8x8, ~35x35ft) ---
BLACKSMITH = Blueprint("Blacksmith", "shop", [
    [W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, W],
    [W, W, W, D, W, W, W, W],
    [W, F, F, F, F, C, F, W],
    [W, F, T, F, F, F, F, W],
    [W, W, W, W, D, W, W, W],
], npc_class="Fighter", npc_count=1, description="A smithy with forge room and showroom.")

# --- General Shop (7x8, ~30x35ft) ---
SHOP = Blueprint("Shop", "shop", [
    [W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, W],
    [W, C, F, F, F, F, C, W],
    [W, W, W, D, W, W, W, W],
    [W, F, F, F, F, T, F, W],
    [W, F, F, F, F, F, B, W],
    [W, W, W, W, D, W, W, W],
], npc_class="Rogue", npc_count=1, description="A general goods shop with storage.")

# --- Tavern (10x12, ~45x55ft, common room + kitchen + 3 bedrooms) ---
TAVERN = Blueprint("Tavern", "tavern", [
    [W, N, W, W, N, W, W, N, W, W, N, W],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [N, F, F, T, F, F, F, T, F, F, F, N],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [N, F, F, T, F, F, F, T, F, F, F, N],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [W, W, W, W, W, D, W, W, W, W, W, W],
    [W, F, F, F, W, F, F, F, W, F, F, W],
    [W, F, T, C, D, F, F, F, D, F, B, N],
    [W, F, F, F, W, F, F, F, W, F, F, W],
    [W, W, D, W, W, W, D, W, W, W, W, W],
    [_, _, _, _, W, B, F, N, _, _, _, _],
    [_, _, _, _, W, F, F, W, _, _, _, _],
    [_, _, _, _, W, W, D, W, _, _, _, _],
], npc_class="Bard", npc_count=3, description="A large tavern with common room, kitchen, and lodging.")

# --- Temple (8x12, ~35x55ft, nave + altar + vestry) ---
TEMPLE = Blueprint("Temple", "temple", [
    [W, W, W, W, W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [W, F, F, F, F, T, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [W, W, W, W, W, D, W, W, W, W, W, W],
    [W, C, F, F, W, F, F, F, F, B, F, W],
    [W, F, F, F, D, F, F, F, F, F, F, W],
    [W, W, W, W, W, W, W, D, W, W, W, W],
], npc_class="Cleric", npc_count=2, description="A temple with nave, altar, and vestry.")

# --- Guard Tower (6x6, ~25x25ft) ---
GUARD_TOWER = Blueprint("Guard Tower", "military", [
    [_, W, W, W, W, _],
    [W, F, F, F, F, W],
    [W, F, F, F, S, W],
    [W, F, F, F, F, W],
    [W, F, F, F, F, W],
    [_, W, W, D, W, _],
], npc_class="Fighter", npc_count=1, description="A watchtower.")

# --- Stable (7x6) ---
STABLE = Blueprint("Stable", "utility", [
    [W, W, W, W, W, W, W],
    [W, F, F, W, F, F, W],
    [W, F, F, W, F, F, W],
    [W, F, F, D, F, F, W],
    [W, F, F, F, F, F, W],
    [W, W, W, D, W, W, W],
], npc_class="Ranger", npc_count=1, description="A stable for horses and mounts.")

# --- Market Stall (4x3, open front) ---
MARKET_STALL = Blueprint("Market Stall", "shop", [
    [W, W, W, W],
    [W, T, C, W],
    [F, F, F, F],
], npc_class="Rogue", npc_count=1, description="An open market stall.")

# --- Mill (7x7) ---
MILL = Blueprint("Mill", "utility", [
    [W, W, W, W, W, W, W],
    [W, F, F, F, F, F, W],
    [W, F, F, F, F, F, W],
    [W, F, F, T, F, F, W],
    [W, F, F, F, F, C, W],
    [W, F, F, F, F, F, W],
    [W, W, W, D, W, W, W],
], npc_count=1, description="A grain mill.")

# --- Castle Keep (20x18, ~95x85ft, great hall + throne + quarters + towers) ---
CASTLE_KEEP = Blueprint("Castle Keep", "castle", [
    [W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W],
    [W, F, F, S, W, F, F, F, F, F, F, F, F, F, F, W, F, F, S, W],
    [W, F, F, F, W, F, F, F, F, F, F, F, F, F, F, W, F, F, F, W],
    [W, F, F, F, D, F, F, F, F, F, F, F, F, F, F, D, F, F, F, W],
    [W, W, W, W, W, F, F, F, F, F, F, F, F, F, F, W, W, W, W, W],
    [W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, T, F, F, F, F, T, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, T, F, F, F, F, T, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W],
    [W, W, W, W, W, F, F, F, F, T, F, F, F, F, F, W, W, W, W, W],
    [W, B, F, F, D, F, F, F, F, F, F, F, F, F, F, D, F, F, B, W],
    [W, F, F, C, W, F, F, F, F, F, F, F, F, F, F, W, C, F, F, W],
    [W, F, F, F, W, W, W, W, W, D, W, W, W, W, W, W, F, F, F, W],
    [W, W, D, W, W, F, F, F, F, F, F, F, F, F, F, W, W, D, W, W],
    [_, _, _, _, W, F, B, F, W, F, F, W, F, B, F, W, _, _, _, _],
    [_, _, _, _, W, F, F, F, D, F, F, D, F, F, F, W, _, _, _, _],
    [_, _, _, _, W, W, W, W, W, W, D, W, W, W, W, W, _, _, _, _],
], npc_class="Paladin", npc_count=8,
   description="A grand castle keep with great hall, throne room, guard quarters, and corner towers.")

# ================================================================
# HOVEL variants (small, for hamlets)
# ================================================================
HOVEL = Blueprint("Hovel", "house", [
    [W, W, W, W, W],
    [W, F, F, F, W],
    [W, F, F, B, W],
    [W, F, T, F, W],
    [W, W, D, W, W],
], npc_count=1, description="A tiny shelter.")

HOVEL_2 = Blueprint("Shack", "house", [
    [W, W, W, W, W, W],
    [W, F, F, F, F, W],
    [W, F, F, F, B, W],
    [W, F, T, F, F, W],
    [W, W, W, D, W, W],
], npc_count=1, description="A small shack.")

# ================================================================
# STORAGE BUILDINGS — physical locations for goods
# ================================================================

# --- Granary (8x6) — food storage with barrels ---
GRANARY = Blueprint("Granary", "storage", [
    [W, W, W, W, W, W, W, W],
    [W, R, F, F, F, F, R, W],
    [W, F, R, F, F, R, F, W],
    [W, R, F, F, F, F, R, W],
    [W, F, R, F, F, R, F, W],
    [W, W, W, D, D, W, W, W],
], npc_count=0, description="A granary for food storage.")

# --- Warehouse (10x8) — general goods storage ---
WAREHOUSE = Blueprint("Warehouse", "storage", [
    [W, W, W, W, W, W, W, W, W, W],
    [W, C, F, F, F, F, F, F, C, W],
    [W, F, C, F, F, F, F, C, F, W],
    [W, C, F, F, F, F, F, F, C, W],
    [W, F, C, F, F, F, F, C, F, W],
    [W, C, F, F, F, F, F, F, C, W],
    [W, F, F, F, F, F, F, F, F, W],
    [W, W, W, W, D, D, W, W, W, W],
], npc_count=0, description="A large warehouse for bulk goods.")

# --- Armoury (8x7) — weapons and armour storage ---
ARMOURY = Blueprint("Armoury", "storage", [
    [W, W, W, W, W, W, W, W],
    [W, C, F, F, F, F, C, W],
    [W, F, F, F, F, F, F, W],
    [W, C, F, A, F, F, C, W],
    [W, F, F, F, F, F, F, W],
    [W, C, F, F, F, F, C, W],
    [W, W, W, L, W, W, W, W],
], npc_count=1, npc_class="Guard", description="A locked armoury for weapons.")

# --- Treasury (6x6) — secured gold and gem storage ---
TREASURY = Blueprint("Treasury", "storage", [
    [W, W, W, W, W, W],
    [W, C, F, F, C, W],
    [W, F, F, F, F, W],
    [W, C, F, F, C, W],
    [W, F, F, F, F, W],
    [W, W, L, W, W, W],
], npc_count=1, npc_class="Guard", description="A secured treasury vault.")

# --- Cellar / Wine Cellar (7x6) — ale, wine, preserved food ---
CELLAR = Blueprint("Cellar", "storage", [
    [W, W, W, W, W, W, W],
    [W, R, F, F, F, R, W],
    [W, F, R, F, R, F, W],
    [W, R, F, F, F, R, W],
    [W, F, F, F, F, F, W],
    [W, W, W, D, W, W, W],
], npc_count=0, description="A cool cellar for beverages and preserved food.")

# --- Workshop (7x7) — crafter's personal stock ---
WORKSHOP = Blueprint("Workshop", "shop", [
    [W, W, W, N, W, W, W],
    [W, F, F, F, F, F, W],
    [N, F, A, F, T, F, N],
    [W, F, F, F, F, F, W],
    [W, C, F, F, F, R, W],
    [W, F, F, F, F, F, W],
    [W, W, W, D, W, W, W],
], npc_count=1, npc_class="Blacksmith", description="A workshop with tools and storage.")


# ================================================================
# NEW BUILDINGS — settlement planner additions
# ================================================================

# --- Town Hall (10x10, ~45x45ft, council chamber + offices) ---
TOWN_HALL = Blueprint("Town Hall", "civic", [
    [W, W, W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, F, F, W],
    [N, F, F, F, F, F, F, F, F, N],
    [W, F, F, T, F, F, T, F, F, W],
    [W, F, F, F, F, F, F, F, F, W],
    [W, W, W, W, D, W, W, W, W, W],
    [W, F, F, F, F, F, W, C, F, W],
    [W, F, T, F, F, F, D, F, F, N],
    [W, F, F, F, F, F, W, F, F, W],
    [W, W, W, W, D, W, W, W, W, W],
], npc_class="Fighter", npc_count=3,
   description="The administrative heart of the town with council chamber.")

# --- Barracks (10x8, ~45x35ft, bunks + armoury + mess) ---
BARRACKS = Blueprint("Barracks", "military", [
    [W, W, W, W, W, W, W, W, W, W],
    [W, B, F, B, W, F, F, F, F, W],
    [W, F, F, F, D, F, T, F, F, N],
    [W, B, F, B, W, F, F, F, F, W],
    [W, W, D, W, W, F, F, F, F, W],
    [W, F, F, F, F, F, F, C, F, W],
    [W, F, F, F, F, F, F, F, F, W],
    [W, W, W, W, D, D, W, W, W, W],
], npc_class="Fighter", npc_count=4,
   description="Military barracks with bunks, mess hall, and equipment storage.")

# --- Barn (8x7, ~35x30ft, open interior with hay storage) ---
BARN = Blueprint("Barn", "utility", [
    [W, W, W, W, W, W, W, W],
    [W, R, F, F, F, F, R, W],
    [W, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, W],
    [W, R, F, F, F, F, R, W],
    [W, F, F, F, F, F, F, W],
    [W, W, W, D, D, W, W, W],
], npc_count=0, description="A large barn for crops and livestock shelter.")

# --- Tanner (7x7, smelly craft building) ---
TANNER = Blueprint("Tanner", "shop", [
    [W, W, W, W, W, W, W],
    [W, F, F, F, F, F, W],
    [N, F, F, R, F, F, N],
    [W, F, F, F, F, F, W],
    [W, F, R, F, R, F, W],
    [W, F, F, F, F, F, W],
    [W, W, W, D, W, W, W],
], npc_class="Rogue", npc_count=1,
   description="A tannery for processing hides. Best placed downwind.")

# --- Weaver (7x6, cloth production) ---
WEAVER = Blueprint("Weaver", "shop", [
    [W, W, W, N, W, W, W],
    [W, F, F, F, F, F, W],
    [N, F, T, F, T, F, N],
    [W, F, F, F, F, F, W],
    [W, C, F, F, F, C, W],
    [W, W, W, D, W, W, W],
], npc_class="Rogue", npc_count=1,
   description="A weaver's shop with looms and fabric stores.")

# --- Bakery (7x6, near center for bread distribution) ---
BAKERY = Blueprint("Bakery", "shop", [
    [W, W, W, W, W, W, W],
    [W, P, F, F, F, R, W],
    [N, F, F, F, F, F, N],
    [W, F, T, F, T, F, W],
    [W, F, F, F, F, F, W],
    [W, W, W, D, W, W, W],
], npc_class="Rogue", npc_count=1,
   description="A bakery with a large oven and bread displays.")

# --- Library (8x8, books and study) ---
LIBRARY = Blueprint("Library", "civic", [
    [W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, W],
    [W, F, T, F, F, T, F, W],
    [W, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, W],
    [W, W, W, D, D, W, W, W],
], npc_class="Cleric", npc_count=1,
   description="A library with reading desks and shelves of tomes.")

# --- Chapel (6x8, small religious building) ---
CHAPEL = Blueprint("Chapel", "temple", [
    [W, W, W, W, W, W],
    [W, F, F, F, F, W],
    [N, F, F, F, F, N],
    [W, F, F, F, F, W],
    [W, F, F, F, F, W],
    [W, F, F, T, F, W],
    [W, F, F, F, F, W],
    [W, W, D, D, W, W],
], npc_class="Cleric", npc_count=1,
   description="A small chapel for worship and meditation.")

# --- Gatehouse (6x4, passage through walls) ---
GATEHOUSE = Blueprint("Gatehouse", "military", [
    [W, W, D, D, W, W],
    [W, F, F, F, F, W],
    [W, F, F, F, F, W],
    [W, W, D, D, W, W],
], npc_class="Fighter", npc_count=1,
   description="A fortified gatehouse controlling entry to the settlement.")

# --- Lord's Chambers (8x8, luxury quarters in castle) ---
LORD_CHAMBERS = Blueprint("Lord's Chambers", "castle", [
    [W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, W],
    [N, F, B, F, F, T, F, N],
    [W, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, W],
    [N, F, C, F, F, C, F, N],
    [W, F, F, F, F, F, F, W],
    [W, W, W, D, D, W, W, W],
], npc_class="Paladin", npc_count=1,
   description="Luxurious chambers for the lord of the castle.")

# --- Great Hall (12x8, feasting and court) ---
GREAT_HALL = Blueprint("Great Hall", "castle", [
    [W, W, W, W, W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [N, F, F, T, F, F, F, F, T, F, F, N],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [N, F, F, T, F, F, F, F, T, F, F, N],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [W, P, F, F, F, F, F, F, F, F, P, W],
    [W, W, W, W, W, D, D, W, W, W, W, W],
], npc_class="Fighter", npc_count=2,
   description="A grand feasting hall with long tables and fireplaces.")

# --- Well House (3x3, small structure around a well) ---
WELL_HOUSE = Blueprint("Well", "utility", [
    [_, F, _],
    [F, F, F],
    [_, F, _],
], npc_count=0, description="A village well for drawing water.")


# ================================================================
# SPECIALIZATION-SPECIFIC BUILDINGS
# ================================================================

# Shorthand additions
G = BRIDGE       # dock/pier tile
WL = WELL        # well tile
BW = BUILT_WALL  # stone wall for mountain settlements
BF = BUILT_FLOOR # raised floor for swamp settlements
TH = THRONE      # throne
BS = BOOKSHELF   # bookshelf
CP = CARPET      # carpet
MO = MOSAIC      # mosaic
AW = ARCHWAY     # archway
FN = FOUNTAIN    # fountain

# --- Dock (10x4, extends into water) ---
DOCK = Blueprint("Dock", "port", [
    [G, G, G, G, G, G, G, G, G, G],
    [G, F, F, F, F, F, F, F, F, G],
    [G, F, F, F, F, F, F, F, F, G],
    [G, G, G, G, G, G, G, G, G, G],
], npc_count=0, description="A wooden dock extending into the water.")

# --- Fish Market (8x6, open-air market near water) ---
FISH_MARKET = Blueprint("Fish Market", "shop", [
    [W, W, W, W, W, W, W, W],
    [W, T, F, F, F, F, T, W],
    [F, F, F, F, F, F, F, F],
    [W, T, F, F, F, F, T, W],
    [W, F, F, F, F, F, F, W],
    [W, W, W, D, D, W, W, W],
], npc_class="Rogue", npc_count=2,
   description="An open-air fish market with stalls and tables.")

# --- Shipyard (12x10, large building near water) ---
SHIPYARD = Blueprint("Shipyard", "utility", [
    [W, W, W, W, W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [N, F, F, F, F, F, F, F, F, F, F, N],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [W, F, F, A, F, F, F, A, F, F, F, W],
    [W, F, R, F, F, F, F, F, R, F, F, W],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [W, W, W, W, W, D, D, W, W, W, W, W],
], npc_class="Fighter", npc_count=3,
   description="A large shipyard for building and repairing vessels.")

# --- Lighthouse (5x5, tall tower at harbor entrance) ---
LIGHTHOUSE = Blueprint("Lighthouse", "utility", [
    [_, W, W, W, _],
    [W, F, F, F, W],
    [W, F, S, F, W],
    [W, F, F, F, W],
    [_, W, D, W, _],
], npc_count=1, npc_class="Ranger",
   description="A lighthouse tower guiding ships to harbor.")

# --- Sailor's Tavern (10x10, larger tavern with nautical theme) ---
SAILOR_TAVERN = Blueprint("Sailor's Tavern", "tavern", [
    [W, N, W, W, N, W, W, N, W, W],
    [W, F, F, F, F, F, F, F, F, W],
    [N, F, T, F, F, F, T, F, F, N],
    [W, F, F, F, F, F, F, F, F, W],
    [W, F, T, F, F, F, T, F, F, W],
    [W, F, F, F, F, F, F, F, F, W],
    [W, W, W, W, D, W, W, W, W, W],
    [W, F, F, F, F, F, W, B, F, W],
    [W, F, R, R, F, F, D, F, F, N],
    [W, W, W, W, D, W, W, W, W, W],
], npc_class="Bard", npc_count=3,
   description="A rowdy dockside tavern popular with sailors.")

# --- Mine Entrance (6x6, entrance to underground mine) ---
MINE_ENTRANCE = Blueprint("Mine Entrance", "utility", [
    [BW, BW, BW, BW, BW, BW],
    [BW, F, F, F, F, BW],
    [BW, F, F, F, F, BW],
    [BW, F, STAIRS_DOWN, F, F, BW],
    [BW, F, F, F, C, BW],
    [BW, BW, BW, D, BW, BW],
], npc_count=1, npc_class="Fighter",
   description="An entrance to an underground mine with stairs leading down.")

# --- Smelter (8x7, ore processing building) ---
SMELTER = Blueprint("Smelter", "shop", [
    [BW, BW, BW, BW, BW, BW, BW, BW],
    [BW, F, F, F, F, F, F, BW],
    [BW, F, P, F, F, P, F, BW],
    [BW, F, F, F, F, F, F, BW],
    [BW, F, A, F, F, R, F, BW],
    [BW, F, F, F, F, F, F, BW],
    [BW, BW, BW, D, D, BW, BW, BW],
], npc_count=1, npc_class="Fighter",
   description="A smelter for processing raw ore into metal ingots.")

# --- Assay Office (6x6, mineral assessment) ---
ASSAY_OFFICE = Blueprint("Assay Office", "shop", [
    [BW, BW, BW, BW, BW, BW],
    [BW, F, F, F, F, BW],
    [BW, F, T, F, F, BW],
    [BW, F, F, F, C, BW],
    [BW, F, F, F, F, BW],
    [BW, BW, BW, D, BW, BW],
], npc_count=1, npc_class="Rogue",
   description="An office where miners bring ore samples for assessment.")

# --- Sawmill (9x7, lumber processing) ---
SAWMILL = Blueprint("Sawmill", "utility", [
    [W, W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, F, W],
    [N, F, F, F, F, F, F, F, N],
    [W, F, T, F, F, F, T, F, W],
    [W, F, F, F, F, F, F, F, W],
    [W, R, F, F, F, F, R, F, W],
    [W, W, W, W, D, D, W, W, W],
], npc_count=2, npc_class="Fighter",
   description="A sawmill for processing timber into planks.")

# --- Hunting Lodge (8x7, outside town) ---
HUNTING_LODGE = Blueprint("Hunting Lodge", "utility", [
    [W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, W],
    [W, F, P, F, F, T, F, W],
    [N, F, F, F, F, F, F, N],
    [W, F, F, F, F, F, F, W],
    [W, B, F, F, F, C, F, W],
    [W, W, W, D, D, W, W, W],
], npc_count=2, npc_class="Ranger",
   description="A hunting lodge with trophy room and sleeping quarters.")

# --- Charcoal Kiln (5x5, small outdoor structure) ---
CHARCOAL_KILN = Blueprint("Charcoal Kiln", "utility", [
    [W, W, W, W, W],
    [W, F, F, F, W],
    [W, F, P, F, W],
    [W, F, F, F, W],
    [W, W, D, W, W],
], npc_count=1,
   description="A kiln for producing charcoal from wood.")

# --- Windmill (7x7, grain processing on high ground) ---
WINDMILL = Blueprint("Windmill", "utility", [
    [_, _, W, W, W, _, _],
    [_, W, F, F, F, W, _],
    [W, F, F, F, F, F, W],
    [W, F, F, T, F, F, W],
    [W, F, F, F, F, R, W],
    [_, W, F, F, F, W, _],
    [_, _, W, D, W, _, _],
], npc_count=1,
   description="A windmill for grinding grain into flour.")

# --- Livestock Pen (8x6, fenced area) ---
LIVESTOCK_PEN = Blueprint("Livestock Pen", "utility", [
    [W, W, W, W, W, W, W, W],
    [W, K, K, K, K, K, K, W],
    [W, K, K, K, K, K, K, W],
    [W, K, K, K, K, K, K, W],
    [W, K, K, K, K, K, K, W],
    [W, W, W, D, D, W, W, W],
], npc_count=0, description="A fenced area for livestock.")

# --- Caravanserai (12x10, large inn for traders) ---
CARAVANSERAI = Blueprint("Caravanserai", "tavern", [
    [W, W, W, W, W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [N, F, T, F, F, F, F, F, T, F, F, N],
    [W, F, F, F, F, F, F, F, F, F, F, W],
    [W, W, W, W, D, W, W, D, W, W, W, W],
    [W, K, K, K, F, W, B, F, F, B, F, W],
    [W, K, K, K, F, D, F, F, F, F, F, N],
    [W, K, K, K, F, W, B, F, F, B, F, W],
    [W, F, F, F, F, W, F, C, F, F, C, W],
    [W, W, W, D, D, W, W, W, W, D, W, W],
], npc_class="Bard", npc_count=3,
   description="A large caravanserai with stables, dormitory, and common room.")

# --- Cistern (5x5, underground water storage) ---
CISTERN = Blueprint("Cistern", "utility", [
    [BW, BW, BW, BW, BW],
    [BW, F, F, F, BW],
    [BW, F, WL, F, BW],
    [BW, F, F, F, BW],
    [BW, BW, D, BW, BW],
], npc_count=0, description="An underground cistern for water storage.")

# --- Herbalist Hut (6x6, swamp settlement specialty) ---
HERBALIST_HUT = Blueprint("Herbalist Hut", "shop", [
    [W, W, W, W, W, W],
    [W, BF, BF, BF, BF, W],
    [N, BF, T, BF, BF, N],
    [W, BF, BF, BF, BF, W],
    [W, C, BF, BF, R, W],
    [W, W, W, D, W, W],
], npc_count=1, npc_class="Cleric",
   description="An herbalist's hut on stilts with drying racks and potions.")

# --- Raised House (6x6, swamp building on stilts) ---
RAISED_HOUSE = Blueprint("Raised House", "house", [
    [W, W, N, W, W, W],
    [W, BF, BF, BF, BF, W],
    [N, BF, BF, BF, BF, N],
    [W, BF, T, BF, BF, W],
    [W, BF, BF, BF, B, W],
    [W, W, W, D, W, W],
], npc_count=2,
   description="A house raised on stilts above the swamp water.")

# --- Peat Store (5x5, swamp resource building) ---
PEAT_STORE = Blueprint("Peat Store", "storage", [
    [W, W, W, W, W],
    [W, R, BF, R, W],
    [W, BF, BF, BF, W],
    [W, R, BF, R, W],
    [W, W, D, W, W],
], npc_count=0, description="A storage building for dried peat blocks.")

# --- Customs House (8x7, border town specialty) ---
CUSTOMS_HOUSE = Blueprint("Customs House", "civic", [
    [W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, W],
    [N, F, T, F, F, T, F, N],
    [W, F, F, F, F, F, F, W],
    [W, W, W, D, W, W, W, W],
    [W, C, F, F, F, F, C, W],
    [W, W, W, D, W, W, W, W],
], npc_class="Fighter", npc_count=2,
   description="A customs house for inspecting goods and collecting duties.")

# --- Royal Palace (16x14, capital city centerpiece) ---
ROYAL_PALACE = Blueprint("Royal Palace", "castle", [
    [W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W],
    [W, F, F, S, W, F, F, F, F, F, F, F, F, W, S, W],
    [W, F, F, F, W, F, F, F, F, F, F, F, F, W, F, W],
    [W, F, F, F, D, F, F, F, TH, F, F, F, F, D, F, W],
    [W, W, W, W, W, F, F, F, F, F, F, F, F, W, W, W],
    [W, CP, CP, CP, F, F, MO, MO, MO, MO, F, F, CP, CP, CP, W],
    [W, CP, CP, CP, F, F, MO, FN, FN, MO, F, F, CP, CP, CP, W],
    [W, CP, CP, CP, F, F, MO, MO, MO, MO, F, F, CP, CP, CP, W],
    [W, W, W, W, W, F, F, F, F, F, F, F, F, W, W, W],
    [W, B, F, C, D, F, F, T, F, T, F, F, F, D, C, W],
    [W, F, F, F, W, F, F, F, F, F, F, F, F, W, F, W],
    [W, F, B, F, W, F, F, F, F, F, F, F, F, W, B, W],
    [W, W, W, W, W, W, W, AW, AW, W, W, W, W, W, W, W],
    [_, _, _, _, _, _, _, F, F, _, _, _, _, _, _, _],
], npc_class="Paladin", npc_count=6,
   description="A grand royal palace with throne room, courtyard, and quarters.")

# --- Money Changer (6x6) ---
MONEY_CHANGER = Blueprint("Money Changer", "shop", [
    [W, W, W, W, W, W],
    [W, F, F, F, F, W],
    [N, F, T, F, F, N],
    [W, F, F, F, F, W],
    [W, C, F, F, C, W],
    [W, W, L, W, W, W],
], npc_count=1, npc_class="Rogue",
   description="A money changer and banking office.")

# --- Ore Warehouse (8x6, mining storage) ---
ORE_WAREHOUSE = Blueprint("Ore Warehouse", "storage", [
    [BW, BW, BW, BW, BW, BW, BW, BW],
    [BW, C, F, F, F, F, C, BW],
    [BW, F, R, F, F, R, F, BW],
    [BW, C, F, F, F, F, C, BW],
    [BW, F, F, F, F, F, F, BW],
    [BW, BW, BW, D, D, BW, BW, BW],
], npc_count=0, description="A stone warehouse for storing raw ore and refined metals.")

# --- Lumber Yard (10x6, open area with stump tiles) ---
LUMBER_YARD = Blueprint("Lumber Yard", "utility", [
    [W, W, W, W, W, W, W, W, W, W],
    [W, F, F, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, F, F, W],
    [W, R, F, F, F, F, F, R, F, W],
    [W, W, W, W, D, D, W, W, W, W],
], npc_count=1, description="An open lumber yard for storing and processing timber.")

# --- Carpenter Workshop (8x7, specialized woodworking) ---
CARPENTER_WORKSHOP = Blueprint("Carpenter Workshop", "shop", [
    [W, W, W, N, W, W, W, W],
    [W, F, F, F, F, F, F, W],
    [N, F, T, F, F, A, F, N],
    [W, F, F, F, F, F, F, W],
    [W, F, F, F, F, F, F, W],
    [W, R, F, F, F, R, F, W],
    [W, W, W, D, D, W, W, W],
], npc_count=1, npc_class="Rogue",
   description="A carpenter's workshop with workbench and lumber storage.")


# ================================================================
# COLLECTIONS
# ================================================================

RESIDENTIAL = [HOVEL, HOVEL_2, COTTAGE, COTTAGE_2, HOUSE, HOUSE_2]
COMMERCIAL = [SHOP, BLACKSMITH, MARKET_STALL, TANNER, WEAVER, BAKERY]
CIVIC = [TEMPLE, GUARD_TOWER, TOWN_HALL, LIBRARY, CHAPEL]
MILITARY = [BARRACKS, GUARD_TOWER, GATEHOUSE]
CASTLE_BUILDINGS = [CASTLE_KEEP, GREAT_HALL, CHAPEL, LORD_CHAMBERS]
UTILITY = [STABLE, MILL, BARN, WELL_HOUSE]
STORAGE = [GRANARY, WAREHOUSE, ARMOURY, TREASURY, CELLAR, WORKSHOP]
SPECIAL = [TAVERN, STABLE, MILL, MANSION, CASTLE_KEEP]

# Specialization-specific collections
PORT_BUILDINGS = [DOCK, FISH_MARKET, SHIPYARD, LIGHTHOUSE, SAILOR_TAVERN]
MINING_BUILDINGS = [MINE_ENTRANCE, SMELTER, ASSAY_OFFICE, ORE_WAREHOUSE]
LUMBER_BUILDINGS = [SAWMILL, HUNTING_LODGE, CHARCOAL_KILN, LUMBER_YARD,
                    CARPENTER_WORKSHOP]
AGRICULTURAL_BUILDINGS = [WINDMILL, LIVESTOCK_PEN]
DESERT_BUILDINGS = [CARAVANSERAI, CISTERN]
SWAMP_BUILDINGS = [HERBALIST_HUT, RAISED_HOUSE, PEAT_STORE]
BORDER_BUILDINGS = [CUSTOMS_HOUSE]
CAPITAL_BUILDINGS = [ROYAL_PALACE, MONEY_CHANGER]

ALL_BLUEPRINTS = (RESIDENTIAL + COMMERCIAL + CIVIC + STORAGE + SPECIAL
                  + MILITARY + CASTLE_BUILDINGS + UTILITY
                  + PORT_BUILDINGS + MINING_BUILDINGS + LUMBER_BUILDINGS
                  + AGRICULTURAL_BUILDINGS + DESERT_BUILDINGS
                  + SWAMP_BUILDINGS + BORDER_BUILDINGS + CAPITAL_BUILDINGS)


def get_building_for_settlement(settlement_type: str, rng: random.Random) -> Blueprint:
    if settlement_type == "hamlet":
        return rng.choice([HOVEL, HOVEL_2, COTTAGE, COTTAGE_2])
    elif settlement_type == "village":
        weights = [(COTTAGE, 30), (COTTAGE_2, 20), (HOUSE, 15), (HOVEL, 10),
                   (SHOP, 8), (BLACKSMITH, 5), (STABLE, 3),
                   (GRANARY, 3), (CELLAR, 2), (WORKSHOP, 2)]
        items, ws = zip(*weights)
        return rng.choices(items, weights=ws, k=1)[0]
    elif settlement_type == "town":
        weights = [(HOUSE, 25), (HOUSE_2, 20), (COTTAGE, 15), (SHOP, 10),
                   (BLACKSMITH, 8), (MANSION, 3), (STABLE, 5),
                   (GRANARY, 4), (WAREHOUSE, 4), (ARMOURY, 2),
                   (TREASURY, 1), (CELLAR, 2), (WORKSHOP, 3)]
        items, ws = zip(*weights)
        return rng.choices(items, weights=ws, k=1)[0]
    elif settlement_type == "city":
        weights = [(HOUSE, 20), (HOUSE_2, 25), (MANSION, 8), (SHOP, 12),
                   (BLACKSMITH, 6), (STABLE, 4),
                   (GRANARY, 4), (WAREHOUSE, 6), (ARMOURY, 3),
                   (TREASURY, 2), (CELLAR, 3), (WORKSHOP, 4)]
        items, ws = zip(*weights)
        return rng.choices(items, weights=ws, k=1)[0]
    return rng.choice(RESIDENTIAL)


def get_building_for_specialization(specialization: str, settlement_type: str,
                                     rng: random.Random) -> Blueprint:
    """Return a building blueprint appropriate for the settlement's specialization.

    Mixes specialization-specific buildings with normal ones based on
    settlement size. Larger settlements get more variety.
    """
    from game.world.specializations import SPECIALIZATION_BUILDINGS

    spec_data = SPECIALIZATION_BUILDINGS.get(specialization, {})
    bonus_names = spec_data.get("bonus", [])
    residential_names = spec_data.get("residential", ["cottage", "house", "hovel"])

    # Build a weighted list: specialization bonus buildings + residential
    candidates = []
    weights = []

    for bname in bonus_names:
        bp = BLUEPRINT_BY_KIND.get(bname)
        if bp:
            candidates.append(bp)
            weights.append(8)

    for rname in residential_names:
        bp = BLUEPRINT_BY_KIND.get(rname)
        if bp:
            candidates.append(bp)
            weights.append(15)

    # Add some generic variety (less weight)
    generic = get_building_for_settlement(settlement_type, rng)
    candidates.append(generic)
    weights.append(10)

    if not candidates:
        return get_building_for_settlement(settlement_type, rng)

    return rng.choices(candidates, weights=weights, k=1)[0]


# Storage building blueprints mapped by storage kind
STORAGE_BLUEPRINTS = {
    "granary": GRANARY,
    "warehouse": WAREHOUSE,
    "armoury": ARMOURY,
    "treasury": TREASURY,
    "cellar": CELLAR,
    "workshop": WORKSHOP,
    "stable": STABLE,
    "market_stall": MARKET_STALL,
}

# Blueprint lookup by building kind name (used by settlement planner)
BLUEPRINT_BY_KIND = {
    "hovel": HOVEL,
    "shack": HOVEL_2,
    "cottage": COTTAGE,
    "farmhouse": COTTAGE_2,
    "house": HOUSE,
    "townhouse": HOUSE_2,
    "mansion": MANSION,
    "blacksmith": BLACKSMITH,
    "shop": SHOP,
    "tavern": TAVERN,
    "temple": TEMPLE,
    "chapel": CHAPEL,
    "guard_tower": GUARD_TOWER,
    "stable": STABLE,
    "market_stall": MARKET_STALL,
    "mill": MILL,
    "castle_keep": CASTLE_KEEP,
    "granary": GRANARY,
    "warehouse": WAREHOUSE,
    "armoury": ARMOURY,
    "treasury": TREASURY,
    "cellar": CELLAR,
    "workshop": WORKSHOP,
    "town_hall": TOWN_HALL,
    "barracks": BARRACKS,
    "barn": BARN,
    "tanner": TANNER,
    "weaver": WEAVER,
    "bakery": BAKERY,
    "library": LIBRARY,
    "gatehouse": GATEHOUSE,
    "lord_chambers": LORD_CHAMBERS,
    "great_hall": GREAT_HALL,
    "well": WELL_HOUSE,
    # Specialization-specific
    "dock": DOCK,
    "fish_market": FISH_MARKET,
    "shipyard": SHIPYARD,
    "lighthouse": LIGHTHOUSE,
    "sailor_tavern": SAILOR_TAVERN,
    "mine_entrance": MINE_ENTRANCE,
    "smelter": SMELTER,
    "assay_office": ASSAY_OFFICE,
    "ore_warehouse": ORE_WAREHOUSE,
    "sawmill": SAWMILL,
    "hunting_lodge": HUNTING_LODGE,
    "charcoal_kiln": CHARCOAL_KILN,
    "lumber_yard": LUMBER_YARD,
    "carpenter_workshop": CARPENTER_WORKSHOP,
    "windmill": WINDMILL,
    "livestock_pen": LIVESTOCK_PEN,
    "caravanserai": CARAVANSERAI,
    "cistern": CISTERN,
    "herbalist_hut": HERBALIST_HUT,
    "raised_house": RAISED_HOUSE,
    "peat_store": PEAT_STORE,
    "customs_house": CUSTOMS_HOUSE,
    "royal_palace": ROYAL_PALACE,
    "money_changer": MONEY_CHANGER,
    # Race-specific building fallbacks (map to closest generic blueprint)
    "tree_house": COTTAGE,
    "tree_platform": MARKET_STALL,
    "garden_grove": BARN,
    "bowyer": WORKSHOP,
    "ranger_post": BARRACKS,
    "stone_house": HOUSE,
    "stone_cottage": COTTAGE,
    "mead_hall": TAVERN,
    "hut": HOVEL,
    "war_shrine": CHAPEL,
    "chieftain_hut": TOWN_HALL,
    "burrow": HOVEL,
    "idol_pit": CHAPEL,
    "boss_hut": TOWN_HALL,
    "stilted_house": COTTAGE,
    "healer_hut": HOVEL,
    "peat_shed": BARN,
    "smokehouse": WORKSHOP,
}


def stamp_blueprint(world_tiles: list, bp: Blueprint, wx: int, wy: int,
                    world_w: int, world_h: int) -> bool:
    """Stamp a building onto the world. Returns True if placed successfully."""
    if wx < 1 or wy < 1 or wx + bp.width >= world_w - 1 or wy + bp.height >= world_h - 1:
        return False

    # Check for overlap - need 2-tile buffer around buildings for streets
    for by in range(-2, bp.height + 2):
        for bx in range(-2, bp.width + 2):
            tx, ty = wx + bx, wy + by
            if 0 <= tx < world_w and 0 <= ty < world_h:
                existing = world_tiles[ty][tx]
                if existing in (WALL, FLOOR, DOOR, TABLE, BED, CHEST,
                               STAIRS_UP, STAIRS_DOWN, BUILT_WALL, BUILT_FLOOR):
                    return False

    # Stamp tiles (skip GRASS cells - they're exterior)
    for by in range(bp.height):
        for bx in range(bp.width):
            tile = bp.tiles[by][bx]
            if tile != _:
                world_tiles[wy + by][wx + bx] = tile

    return True
