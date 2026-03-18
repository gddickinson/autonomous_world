"""
Interior View System — separate high-resolution interior maps for buildings.

When the player enters a building (steps on a door tile), the game transitions
to an interior view showing only that building's rooms at higher detail.

Architecture:
- Each building gets an InteriorMap: a separate tile grid at 2x resolution
- The overworld view hides building interiors (roof covers them)
- Entering a door triggers a fade transition to interior view
- Interior view has its own camera, rendering, and entity tracking
- Multi-floor support via STAIRS_UP/STAIRS_DOWN connections
- Dungeons and caves use the same system with procedural generation

Building generation:
- BSP (Binary Space Partitioning) for room subdivision
- Room templates for specific building types (tavern, temple, shop)
- Furniture placement based on room purpose
- Corridor connections between rooms
- Stairwells connecting floors

Inspired by Baldur's Gate roof-reveal and separate interior maps.
"""

import random
import math
from typing import Dict, List, Optional, Tuple
from game.settings import (WALL, FLOOR, DOOR, TABLE, BED, CHEST,
                           STAIRS_UP, STAIRS_DOWN, WINDOW, LOCKED_DOOR,
                           TILE_SIZE, GRASS, ROAD, SAND, RUBBLE,
                           PILLAR, ALTAR, FIREPLACE, THRONE, BOOKSHELF,
                           BARREL, ANVIL, FORGE_FIRE, FOUNTAIN, CARPET,
                           MOSAIC, ARCHWAY, IRON_GATE)


# ================================================================
# INTERIOR TILE SIZE — higher resolution than overworld
# ================================================================

INTERIOR_TILE_SIZE = 64   # tile render size (4x overworld for detailed interiors)
INTERIOR_SCALE = 3        # each overworld floor tile becomes 3x3 interior tiles


# ================================================================
# ROOM TEMPLATES — what furniture goes in each room type
# ================================================================

ROOM_TEMPLATES = {
    # === RESIDENTIAL ROOMS — quality tiers ===
    # Squalid: bare floor, straw, no furniture (homeless, prisoners)
    # Poor: simple bed, maybe a chest (serfs, recruits, stable hands)
    # Modest: bed + chest + table (commoners, soldiers, servants)
    # Comfortable: double bed, carpet, chest, table (officers, gentry, merchants)
    # Fine: large bed, carpet, bookshelf, fireplace (nobility, commanders)
    # Luxurious: ornate bed, carpet, fireplace, pillar, bookshelf (royalty, marshals)

    "bedroom": {  # modest single (commoner)
        "furniture": [(BED, 1, 1), (CHEST, 1, 1), (TABLE, 0, 1)],
        "min_size": (3, 3), "max_size": (5, 5),
    },
    "bedroom_poor": {  # cramped, just a bed (serf, recruit)
        "furniture": [(BED, 1, 1)],
        "min_size": (2, 2), "max_size": (3, 3),
    },
    "bedroom_fine": {  # well-appointed (officer, noble, gentry)
        "furniture": [(BED, 1, 1), (CHEST, 1, 1), (TABLE, 1, 1),
                      (CARPET, 1, 2), (BOOKSHELF, 0, 1)],
        "min_size": (4, 4), "max_size": (6, 6),
    },
    "bedroom_luxurious": {  # opulent (royalty, marshal, high priest)
        "furniture": [(BED, 1, 1), (CHEST, 1, 2), (TABLE, 1, 1),
                      (CARPET, 2, 3), (BOOKSHELF, 1, 2), (FIREPLACE, 1, 1),
                      (PILLAR, 0, 2)],
        "min_size": (5, 5), "max_size": (8, 8),
    },
    "double_bedroom": {  # modest couple (commoners)
        "furniture": [(BED, 2, 2), (CHEST, 1, 2), (TABLE, 1, 1)],
        "min_size": (4, 4), "max_size": (6, 6),
    },
    "double_bedroom_fine": {  # well-appointed couple (officer, lord)
        "furniture": [(BED, 2, 2), (CHEST, 1, 2), (TABLE, 1, 1),
                      (CARPET, 2, 3), (FIREPLACE, 0, 1)],
        "min_size": (5, 5), "max_size": (7, 7),
    },
    "double_bedroom_luxurious": {  # royal chambers
        "furniture": [(BED, 2, 2), (CHEST, 1, 2), (TABLE, 1, 1),
                      (CARPET, 3, 5), (FIREPLACE, 1, 1), (BOOKSHELF, 1, 1),
                      (PILLAR, 2, 2)],
        "min_size": (6, 6), "max_size": (9, 9),
    },
    "children_room": {  # shared kids room (2-3 small beds)
        "furniture": [(BED, 2, 3), (CHEST, 1, 1)],
        "min_size": (3, 4), "max_size": (5, 6),
    },
    "nursery": {  # baby room (cot = bed tile, small)
        "furniture": [(BED, 1, 1)],
        "min_size": (2, 2), "max_size": (3, 3),
    },
    "servants_quarters": {  # small room for servants (2-4 beds packed tight)
        "furniture": [(BED, 2, 4), (CHEST, 1, 1)],
        "min_size": (4, 3), "max_size": (6, 5),
    },
    "dormitory": {  # common soldiers (4-8 beds in rows, basic)
        "furniture": [(BED, 4, 8), (CHEST, 2, 4)],
        "min_size": (6, 5), "max_size": (10, 8),
    },
    "officer_quarters": {  # NCO/sergeant (2 beds, table, nicer)
        "furniture": [(BED, 1, 2), (CHEST, 1, 2), (TABLE, 1, 1), (CARPET, 0, 1)],
        "min_size": (4, 3), "max_size": (5, 5),
    },
    "commander_quarters": {  # captain/commander (single fine room)
        "furniture": [(BED, 1, 1), (CHEST, 1, 1), (TABLE, 1, 1),
                      (CARPET, 1, 2), (BOOKSHELF, 1, 1), (FIREPLACE, 0, 1)],
        "min_size": (5, 4), "max_size": (7, 6),
    },
    "guest_room": {  # inn/tavern modest guest room
        "furniture": [(BED, 1, 2), (TABLE, 0, 1), (CHEST, 0, 1)],
        "min_size": (3, 3), "max_size": (4, 5),
    },
    "guest_suite": {  # upscale inn room
        "furniture": [(BED, 1, 2), (TABLE, 1, 1), (CHEST, 1, 1),
                      (CARPET, 1, 1), (FIREPLACE, 0, 1)],
        "min_size": (4, 4), "max_size": (6, 6),
    },
    "stable_loft": {  # sleeping above stables (straw beds)
        "furniture": [(BED, 1, 3), (BARREL, 1, 2)],
        "min_size": (4, 3), "max_size": (6, 5),
    },

    # === FUNCTIONAL ROOMS ===
    "common_room": {
        "furniture": [(TABLE, 2, 4), (BARREL, 0, 1)],
        "min_size": (4, 4), "max_size": (8, 8),
    },
    "kitchen": {
        "furniture": [(TABLE, 1, 2), (FIREPLACE, 1, 1), (BARREL, 1, 2)],
        "min_size": (3, 3), "max_size": (5, 5),
    },
    "dining_hall": {  # large eating area
        "furniture": [(TABLE, 4, 8), (BARREL, 1, 3)],
        "min_size": (6, 5), "max_size": (10, 8),
    },
    "storage": {
        "furniture": [(CHEST, 2, 4), (BARREL, 1, 3)],
        "min_size": (2, 3), "max_size": (4, 5),
    },
    "workshop": {
        "furniture": [(ANVIL, 1, 1), (FORGE_FIRE, 1, 1), (TABLE, 1, 1),
                      (CHEST, 1, 2), (BARREL, 1, 2)],
        "min_size": (4, 4), "max_size": (6, 6),
    },
    "throne_room": {
        "furniture": [(THRONE, 1, 1), (CARPET, 2, 4), (PILLAR, 2, 4)],
        "min_size": (6, 6), "max_size": (10, 10),
    },
    "library": {
        "furniture": [(BOOKSHELF, 3, 6), (TABLE, 1, 2), (CARPET, 1, 2)],
        "min_size": (4, 4), "max_size": (7, 7),
    },
    "infirmary": {  # hospital/medical room (beds + altar for healing)
        "furniture": [(BED, 2, 4), (TABLE, 1, 1), (ALTAR, 0, 1)],
        "min_size": (4, 4), "max_size": (7, 6),
    },
    "chapel": {  # small prayer room
        "furniture": [(ALTAR, 1, 1), (CARPET, 1, 2), (PILLAR, 0, 2)],
        "min_size": (3, 3), "max_size": (5, 5),
    },
    "guard_room": {  # guard post with weapons and a bed for resting
        "furniture": [(BED, 1, 2), (TABLE, 1, 1), (CHEST, 1, 2)],
        "min_size": (3, 3), "max_size": (5, 5),
    },
    "tavern_hall": {  # main tavern drinking/eating area
        "furniture": [(TABLE, 4, 8), (BARREL, 3, 6), (FIREPLACE, 1, 1)],
        "min_size": (6, 5), "max_size": (10, 8),
    },
    "shop_floor": {  # retail area with goods on display
        "furniture": [(TABLE, 2, 3), (CHEST, 2, 4), (BARREL, 1, 2)],
        "min_size": (4, 4), "max_size": (7, 6),
    },
    "stable": {  # animal stalls (barrels for feed, no furniture that blocks)
        "furniture": [(BARREL, 2, 4)],
        "min_size": (4, 4), "max_size": (8, 6),
    },

    # === STRUCTURAL ROOMS ===
    "corridor": {
        "furniture": [(BARREL, 0, 1)],
        "min_size": (2, 4), "max_size": (3, 8),
    },
    "stairwell": {
        "furniture": [],
        "min_size": (3, 3), "max_size": (4, 4),
    },
    "cellar": {
        "furniture": [(CHEST, 1, 3), (BARREL, 2, 4)],
        "min_size": (4, 4), "max_size": (8, 8),
    },
    "dungeon_cell": {
        "furniture": [(BED, 0, 1)],
        "min_size": (2, 2), "max_size": (3, 3),
    },
    "entry_hall": {
        "furniture": [(BARREL, 0, 1)],
        "min_size": (3, 3), "max_size": (5, 5),
    },
}

# ================================================================
# BUILDING ROOM SETS — what rooms each building type contains
# ================================================================
# Designed to provide adequate sleeping for inhabitants:
# - Families: double bedroom (parents) + children_room or nursery
# - Servants: servants_quarters in castles/mansions
# - Military: dormitory in barracks/guard towers
# - Guests: guest_room in taverns/inns
# - Workers: bedroom above shops (upper floor)

BUILDING_ROOM_SETS = {
    # === RESIDENTIAL ===
    "house": ["entry_hall", "common_room", "double_bedroom", "children_room",
              "kitchen"],
    "cottage": ["entry_hall", "common_room", "double_bedroom", "kitchen"],
    "hovel": ["common_room", "bedroom", "kitchen"],  # single room with bed area
    "hut": ["common_room", "bedroom"],  # primitive dwelling

    # === COMMERCIAL (with living quarters) ===
    "shop": ["entry_hall", "shop_floor", "storage", "stairwell",
             "bedroom", "kitchen"],  # upstairs living
    "tavern": ["entry_hall", "tavern_hall", "kitchen", "storage",
               "guest_room", "guest_room", "guest_room",   # 3 basic rooms
               "double_bedroom",                             # innkeeper's room
               "stairwell"],
    "inn": ["entry_hall", "tavern_hall", "kitchen",
            "guest_room", "guest_room", "guest_room",       # 3 basic rooms
            "guest_suite", "guest_suite",                    # 2 nicer rooms
            "double_bedroom",                                # innkeeper's room
            "stable_loft",                                   # stable hands
            "storage", "stairwell"],
    "blacksmith": ["entry_hall", "workshop", "storage", "stairwell",
                   "bedroom", "kitchen"],  # living above the forge

    # === RELIGIOUS ===
    "temple": ["entry_hall", "chapel", "library",
               "bedroom_fine",                     # high priest's quarters
               "bedroom", "bedroom",               # acolyte rooms
               "infirmary", "storage", "stairwell"],
    "monastery": ["entry_hall", "chapel", "library",
                  "bedroom_fine",                   # abbot's cell
                  "dormitory",                      # monks' sleeping hall
                  "dining_hall", "kitchen", "storage", "cellar", "stairwell"],
    "shrine": ["entry_hall", "chapel"],

    # === MILITARY ===
    "barracks": ["entry_hall",
                 "dormitory", "dormitory",        # common soldiers (8-16 beds)
                 "officer_quarters",               # NCOs/sergeants (1-2 beds)
                 "commander_quarters",             # captain (1 fine bed)
                 "dining_hall", "kitchen", "storage", "guard_room", "stairwell"],
    "guard_tower": ["entry_hall", "guard_room", "guard_room",
                    "officer_quarters",            # watch officer gets own room
                    "storage", "stairwell"],
    "watchtower": ["entry_hall", "guard_room", "stairwell"],

    # === NOBLE ===
    "castle": ["entry_hall", "throne_room",
               "double_bedroom_luxurious",         # royal chambers (king/queen)
               "bedroom_luxurious",                # heir's chambers
               "double_bedroom_fine", "bedroom_fine",  # lord/lady rooms
               "servants_quarters", "servants_quarters",  # castle servants
               "guard_room", "guard_room",         # castle guard sleeping
               "commander_quarters",               # captain of the guard
               "dining_hall", "kitchen", "library",
               "infirmary", "storage", "cellar", "stairwell"],
    "mansion": ["entry_hall", "common_room", "library",
                "double_bedroom_fine",             # master bedroom
                "bedroom_fine",                    # second bedroom
                "children_room",                   # children's room
                "servants_quarters",               # household servants
                "dining_hall", "kitchen", "storage", "stairwell"],
    "manor": ["entry_hall", "common_room",
              "double_bedroom_fine",               # lord's chambers
              "bedroom", "children_room",
              "servants_quarters",
              "kitchen", "storage", "stairwell"],

    # === AGRICULTURAL ===
    "stable": ["entry_hall", "stable", "storage", "stable_loft"],
    "farmstead": ["entry_hall", "common_room", "double_bedroom",
                  "children_room", "kitchen", "storage"],
    "barn": ["entry_hall", "storage", "storage", "stable_loft"],

    # === CIVIC ===
    "guildhall": ["entry_hall", "common_room", "library", "storage",
                  "bedroom", "stairwell"],
    "jail": ["entry_hall", "guard_room", "dungeon_cell", "dungeon_cell",
             "dungeon_cell", "storage"],
    "hospital": ["entry_hall", "infirmary", "infirmary", "bedroom",
                 "storage", "kitchen"],

    # === WILDERNESS ===
    "cabin": ["common_room", "bedroom", "storage"],  # mountain hut
    "tent": ["bedroom"],  # camping tent, just a sleeping area
    "dungeon": ["entry_hall", "corridor", "dungeon_cell", "dungeon_cell",
                "dungeon_cell", "storage", "stairwell"],
    "ruins": ["entry_hall", "corridor", "dungeon_cell", "dungeon_cell",
              "storage", "corridor", "stairwell"],
    "cave": ["entry_hall", "corridor", "corridor", "storage"],

    # === ENTERTAINMENT / ARENA ===
    "colosseum": ["entry_hall",
                  "dormitory", "dormitory",       # gladiator barracks
                  "commander_quarters",            # arena master
                  "infirmary",                     # medical room for fighters
                  "storage", "storage",            # weapon/armor storage
                  "dining_hall",                   # fighters' mess
                  "guard_room", "guard_room",      # arena guards
                  "stairwell"],
    "arena": ["entry_hall",
              "dormitory",                         # fighters' quarters
              "guard_room",                        # arena guard
              "storage",                           # weapons
              "infirmary"],                        # patch-up room
}


# ================================================================
# INTERIOR MAP — a separate tile grid for one building floor
# ================================================================

class InteriorMap:
    """A separate tile grid representing the inside of a building.
    Higher resolution than the overworld, with room data.
    """

    def __init__(self, width: int, height: int, building_name: str = "",
                 building_kind: str = "", floor_num: int = 0):
        self.width = width
        self.height = height
        self.building_name = building_name
        self.building_kind = building_kind
        self.floor_num = floor_num

        # Tile grid
        self.tiles = [[WALL for _ in range(width)] for _ in range(height)]

        # Room data
        self.rooms: List[Dict] = []  # {x, y, w, h, room_type, connected_to}

        # Entry/exit points
        self.entry_x = width // 2
        self.entry_y = height - 2
        self.exits: List[Dict] = []  # {x, y, target_floor, target_x, target_y}

        # Entities inside this interior
        self.npcs_inside: List[str] = []  # NPC names

        # Overworld ↔ interior tile mapping (for syncing damage)
        # Maps (world_x, world_y) → list of (interior_x, interior_y)
        self._world_to_interior: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
        # Building footprint on overworld
        self._building_rect: Optional[Tuple[int, int, int, int]] = None

        # Overworld anchor (where this building is on the main map)
        self.world_x = 0
        self.world_y = 0

    def sync_exterior_damage(self, world_x: int, world_y: int, new_tile_type: int):
        """Sync damage from the overworld to the interior map.

        When a wall/door/window on the overworld is destroyed, update the
        corresponding interior tiles to match.

        Args:
            world_x, world_y: Overworld tile that changed
            new_tile_type: What the tile became after destruction
        """
        interior_positions = self._world_to_interior.get((world_x, world_y), [])
        for ix, iy in interior_positions:
            if 0 <= ix < self.width and 0 <= iy < self.height:
                old = self.tiles[iy][ix]
                # Map the exterior replacement to appropriate interior tile
                if new_tile_type == FLOOR or new_tile_type == GRASS:
                    if old == WALL:
                        self.tiles[iy][ix] = FLOOR  # wall breached
                    elif old in (DOOR, LOCKED_DOOR):
                        self.tiles[iy][ix] = FLOOR  # door destroyed
                    elif old == WINDOW:
                        self.tiles[iy][ix] = FLOOR  # window smashed
                elif new_tile_type == RUBBLE:
                    if old == WALL:
                        self.tiles[iy][ix] = RUBBLE  # rubble from wall

    def is_walkable(self, x: int, y: int) -> bool:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x] not in (WALL, WINDOW)
        return False

    def get_tile(self, x: int, y: int) -> int:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y][x]
        return WALL


# ================================================================
# BSP DUNGEON/BUILDING GENERATOR
# ================================================================

class BSPNode:
    """Binary Space Partitioning node for room generation."""
    __slots__ = ('x', 'y', 'w', 'h', 'left', 'right', 'room')

    def __init__(self, x: int, y: int, w: int, h: int):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.left = None
        self.right = None
        self.room = None  # (rx, ry, rw, rh) if leaf


def bsp_split(node: BSPNode, min_size: int = 6, depth: int = 0,
              max_depth: int = 4, rng: random.Random = None) -> None:
    """Recursively split a BSP node into rooms."""
    if rng is None:
        rng = random.Random()

    if depth >= max_depth or node.w < min_size * 2 or node.h < min_size * 2:
        # Create a room in this leaf
        margin = 1
        max_rw = max(min_size - 1, node.w - margin * 2)
        max_rh = max(min_size - 1, node.h - margin * 2)
        rw = rng.randint(min(min_size - 1, max_rw), max_rw)
        rh = rng.randint(min(min_size - 1, max_rh), max_rh)
        max_rx = max(margin, node.w - rw - margin)
        max_ry = max(margin, node.h - rh - margin)
        rx = node.x + rng.randint(margin, max_rx)
        ry = node.y + rng.randint(margin, max_ry)
        node.room = (rx, ry, max(2, rw), max(2, rh))
        return

    # Choose split direction
    if node.w > node.h * 1.3:
        horizontal = False
    elif node.h > node.w * 1.3:
        horizontal = True
    else:
        horizontal = rng.random() < 0.5

    if horizontal:
        split = rng.randint(min_size, node.h - min_size)
        node.left = BSPNode(node.x, node.y, node.w, split)
        node.right = BSPNode(node.x, node.y + split, node.w, node.h - split)
    else:
        split = rng.randint(min_size, node.w - min_size)
        node.left = BSPNode(node.x, node.y, split, node.h)
        node.right = BSPNode(node.x + split, node.y, node.w - split, node.h)

    bsp_split(node.left, min_size, depth + 1, max_depth, rng)
    bsp_split(node.right, min_size, depth + 1, max_depth, rng)


def get_bsp_rooms(node: BSPNode) -> List[Tuple[int, int, int, int]]:
    """Collect all rooms from a BSP tree."""
    if node.room:
        return [node.room]
    rooms = []
    if node.left:
        rooms.extend(get_bsp_rooms(node.left))
    if node.right:
        rooms.extend(get_bsp_rooms(node.right))
    return rooms


def get_room_center(room: Tuple[int, int, int, int]) -> Tuple[int, int]:
    return (room[0] + room[2] // 2, room[1] + room[3] // 2)


# ================================================================
# INTERIOR GENERATOR
# ================================================================

def generate_interior(building_name: str, building_kind: str,
                      floor_num: int = 0, seed: int = None,
                      size_hint: str = "medium") -> InteriorMap:
    """Generate an interior map for a building using BSP.

    Args:
        building_name: Name of the building
        building_kind: Type (house, tavern, temple, castle, dungeon, cave)
        floor_num: 0=ground, 1=upper, -1=basement
        seed: Random seed for reproducibility
        size_hint: "small" (20x20), "medium" (30x30), "large" (40x40)

    Returns an InteriorMap with rooms, furniture, and connections.
    """
    rng = random.Random(seed) if seed else random.Random()

    sizes = {"small": (20, 20), "medium": (30, 30), "large": (40, 40), "huge": (50, 50)}
    w, h = sizes.get(size_hint, (30, 30))

    # Dungeons and caves are larger
    if building_kind in ("dungeon", "cave"):
        w, h = w + 10, h + 10

    interior = InteriorMap(w, h, building_name, building_kind, floor_num)

    # Generate rooms using BSP
    root = BSPNode(1, 1, w - 2, h - 2)
    max_depth = {"small": 3, "medium": 4, "large": 5, "huge": 5}
    bsp_split(root, min_size=5, max_depth=max_depth.get(size_hint, 4), rng=rng)

    bsp_rooms = get_bsp_rooms(root)

    # Get room types for this building
    room_types = list(BUILDING_ROOM_SETS.get(building_kind,
                                              BUILDING_ROOM_SETS["house"]))

    # Assign room types to BSP rooms
    for i, (rx, ry, rw, rh) in enumerate(bsp_rooms):
        # Carve room
        for cy in range(ry, ry + rh):
            for cx in range(rx, rx + rw):
                if 0 <= cx < w and 0 <= cy < h:
                    interior.tiles[cy][cx] = FLOOR

        # Assign room type
        room_type = room_types[i % len(room_types)] if room_types else "common_room"

        # Place furniture
        template = ROOM_TEMPLATES.get(room_type, ROOM_TEMPLATES["common_room"])
        for furn_tile, fmin, fmax in template.get("furniture", []):
            count = rng.randint(fmin, fmax)
            for _ in range(count):
                fx = rng.randint(rx + 1, rx + rw - 2)
                fy = rng.randint(ry + 1, ry + rh - 2)
                if 0 <= fx < w and 0 <= fy < h and interior.tiles[fy][fx] == FLOOR:
                    interior.tiles[fy][fx] = furn_tile

        interior.rooms.append({
            "x": rx, "y": ry, "w": rw, "h": rh,
            "room_type": room_type,
            "connected_to": [],
        })

    # Connect rooms with corridors
    for i in range(len(bsp_rooms) - 1):
        c1 = get_room_center(bsp_rooms[i])
        c2 = get_room_center(bsp_rooms[i + 1])
        _carve_corridor(interior, c1[0], c1[1], c2[0], c2[1], rng)
        interior.rooms[i]["connected_to"].append(i + 1)
        interior.rooms[i + 1]["connected_to"].append(i)

    # Place doors at corridor-room junctions
    _place_doors(interior)

    # Place windows on outer walls for non-underground floors
    if floor_num >= 0 and building_kind not in ("dungeon", "cave"):
        _place_windows(interior)

    # Set entry point (door at bottom of map)
    interior.entry_x = w // 2
    interior.entry_y = h - 2
    # Ensure entry is walkable
    for dy in range(-1, 2):
        for dx in range(-1, 2):
            ex, ey = interior.entry_x + dx, interior.entry_y + dy
            if 0 <= ex < w and 0 <= ey < h:
                if interior.tiles[ey][ex] == WALL:
                    interior.tiles[ey][ex] = FLOOR
    interior.tiles[h - 1][w // 2] = DOOR  # entrance door

    # Place stairs for multi-floor buildings
    # Ground floor (0): stairs UP to floor 1, and optionally stairs DOWN to basement
    # Upper floors (>0): stairs DOWN to return, stairs UP if more floors
    # Basements (<0): stairs UP to return
    stairwell_rooms = [r for r in interior.rooms if r["room_type"] == "stairwell"]

    # If no stairwell room exists but building type should have stairs,
    # use the last room as a stairwell
    needs_stairs = building_kind in ("castle", "mansion", "tavern", "temple",
                                      "dungeon", "ruins")
    if not stairwell_rooms and needs_stairs and interior.rooms:
        stairwell_rooms = [interior.rooms[-1]]

    for r in stairwell_rooms:
        sx_s = r["x"] + r["w"] // 2
        sy_s = r["y"] + r["h"] // 2
        if not (0 <= sx_s < w and 0 <= sy_s < h):
            continue

        # Always place STAIRS_UP (to go up a level)
        interior.tiles[sy_s][sx_s] = STAIRS_UP
        interior.exits.append({
            "x": sx_s, "y": sy_s,
            "target_floor": floor_num + 1,
            "target_x": sx_s, "target_y": sy_s,
        })

        # Place STAIRS_DOWN next to it (to go down a level) if there's space
        if floor_num > 0 or (building_kind in ("dungeon", "castle", "ruins")):
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nx, ny = sx_s + dx, sy_s + dy
                if 0 <= nx < w and 0 <= ny < h and interior.tiles[ny][nx] == FLOOR:
                    interior.tiles[ny][nx] = STAIRS_DOWN
                    interior.exits.append({
                        "x": nx, "y": ny,
                        "target_floor": floor_num - 1,
                        "target_x": nx, "target_y": ny,
                    })
                    break
        break  # only one stairwell

    return interior


def _carve_corridor(interior: InteriorMap, x1: int, y1: int,
                    x2: int, y2: int, rng: random.Random):
    """Carve an L-shaped corridor between two points."""
    x, y = x1, y1

    # Randomly choose horizontal-first or vertical-first
    if rng.random() < 0.5:
        # Horizontal then vertical
        while x != x2:
            if 0 <= x < interior.width and 0 <= y < interior.height:
                interior.tiles[y][x] = FLOOR
            x += 1 if x2 > x else -1
        while y != y2:
            if 0 <= x < interior.width and 0 <= y < interior.height:
                interior.tiles[y][x] = FLOOR
            y += 1 if y2 > y else -1
    else:
        # Vertical then horizontal
        while y != y2:
            if 0 <= x < interior.width and 0 <= y < interior.height:
                interior.tiles[y][x] = FLOOR
            y += 1 if y2 > y else -1
        while x != x2:
            if 0 <= x < interior.width and 0 <= y < interior.height:
                interior.tiles[y][x] = FLOOR
            x += 1 if x2 > x else -1


def _place_doors(interior: InteriorMap):
    """Place doors where corridors meet room walls."""
    for y in range(1, interior.height - 1):
        for x in range(1, interior.width - 1):
            if interior.tiles[y][x] != FLOOR:
                continue
            # Check if this is a doorway (floor between two walls with floor on other sides)
            if (interior.tiles[y-1][x] == WALL and interior.tiles[y+1][x] == WALL and
                interior.tiles[y][x-1] == FLOOR and interior.tiles[y][x+1] == FLOOR):
                interior.tiles[y][x] = DOOR
            elif (interior.tiles[y][x-1] == WALL and interior.tiles[y][x+1] == WALL and
                  interior.tiles[y-1][x] == FLOOR and interior.tiles[y+1][x] == FLOOR):
                interior.tiles[y][x] = DOOR


def _place_windows(interior: InteriorMap):
    """Place windows on exterior walls."""
    for y in range(1, interior.height - 1):
        for x in range(1, interior.width - 1):
            if interior.tiles[y][x] != WALL:
                continue
            # Check if this wall is on the building perimeter with floor inside
            adjacent_floor = 0
            adjacent_outside = 0
            for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                nx, ny = x+dx, y+dy
                if 0 <= nx < interior.width and 0 <= ny < interior.height:
                    if interior.tiles[ny][nx] == FLOOR:
                        adjacent_floor += 1
                    elif interior.tiles[ny][nx] == WALL:
                        pass
                else:
                    adjacent_outside += 1

            if adjacent_floor >= 1 and adjacent_outside >= 1:
                if random.random() < 0.3:  # 30% chance of window
                    interior.tiles[y][x] = WINDOW


# ================================================================
# INTERIOR VIEW STATE — manages which interior the player is in
# ================================================================

class InteriorViewState:
    """Tracks whether the player is inside a building and which one."""

    def __init__(self):
        self.is_inside = False
        self.current_interior: Optional[InteriorMap] = None
        self.current_floor = 0
        self.building_interiors: Dict[str, Dict[int, InteriorMap]] = {}
        # {building_name: {floor_num: InteriorMap}}

        # Player position within interior
        self.interior_x = 0.0
        self.interior_y = 0.0

        # Transition animation
        self.transitioning = False
        self.transition_alpha = 0  # 0=transparent, 255=opaque
        self.transition_target = ""  # building name entering
        self.transition_entering = True

    def get_or_create_interior(self, building_name: str, building_kind: str,
                                floor_num: int = 0,
                                world_x: int = 0, world_y: int = 0,
                                world=None, building_rect=None) -> InteriorMap:
        """Get cached interior or generate new one.
        If world and building_rect are provided, creates interior from actual
        overworld tiles (matching the building you see from outside).
        """
        rect_str = f"{building_rect}" if building_rect else ""
        cache_key = f"{building_name}_{world_x}_{world_y}_{rect_str}"
        if cache_key not in self.building_interiors:
            self.building_interiors[cache_key] = {}

        floors = self.building_interiors[cache_key]
        if floor_num not in floors:
            if world and building_rect and floor_num == 0:
                # Create interior from actual overworld building tiles
                interior = create_interior_from_world(
                    world, building_rect, building_name, building_kind)
            else:
                # Use realistic interior generator for ground floor,
                # BSP fallback for upper/lower floors
                seed = hash(building_name + str(floor_num)) & 0xFFFFFFFF
                if floor_num == 0:
                    try:
                        from game.systems.interior_gen import generate_realistic_interior
                        interior = generate_realistic_interior(
                            building_name, building_kind, floor_num,
                            seed=seed, num_residents=4)
                    except Exception:
                        sizes = {"house": "small", "shop": "small", "tavern": "medium",
                                "temple": "medium", "castle": "large", "mansion": "medium",
                                "dungeon": "large", "cave": "medium"}
                        size = sizes.get(building_kind, "medium")
                        interior = generate_interior(building_name, building_kind,
                                                    floor_num, seed, size)
                else:
                    # Upper/lower floors: match ground floor dimensions
                    # and place stairs at matching positions
                    ground = floors.get(0)
                    if ground:
                        target_w = ground.width
                        target_h = ground.height
                    else:
                        target_w = target_h = 30

                    sizes = {"house": "small", "shop": "small", "tavern": "medium",
                            "temple": "medium", "castle": "large", "mansion": "medium",
                            "dungeon": "large", "cave": "medium"}
                    size = sizes.get(building_kind, "medium")
                    interior = generate_interior(building_name, building_kind,
                                                floor_num, seed, size)

                    # Force matching dimensions if ground floor exists
                    if ground and (interior.width != target_w or interior.height != target_h):
                        # Regenerate at correct size
                        try:
                            from game.systems.interior_gen import generate_realistic_interior
                            interior = generate_realistic_interior(
                                building_name, building_kind, floor_num,
                                seed=seed, num_residents=3)
                        except Exception:
                            pass  # use BSP version

                    # Ensure stairs on this floor are near stairs on adjacent floor
                    if ground:
                        _align_stairs_with_floor(interior, ground, floor_num)

            interior.world_x = world_x
            interior.world_y = world_y
            interior._cache_key = cache_key
            floors[floor_num] = interior

        return floors[floor_num]

    def enter_building(self, building_name: str, building_kind: str,
                       world_x: int, world_y: int,
                       world=None, building_rect=None,
                       npcs=None, time_of_day: float = 0.3) -> "InteriorMap":
        """Player enters a building. Returns the interior map.

        Args:
            npcs: optional list of all NPCs — only those actually present will appear.
            time_of_day: normalized time (0.0-1.0) for probabilistic NPC placement.
        """
        interior = self.get_or_create_interior(
            building_name, building_kind, 0, world_x, world_y,
            world, building_rect)

        self.is_inside = True
        self.current_interior = interior
        self.current_floor = 0
        self.interior_x = float(interior.entry_x)
        self.interior_y = float(interior.entry_y)

        # Populate NPCs inside this building based on actual/probable location
        # Place them in contextually appropriate rooms with activities
        interior._cached_npcs = []
        interior._active_interior_npcs = []
        if npcs:
            import random as _rng
            present = _get_npcs_present_in_building(
                npcs, world_x, world_y, building_rect, building_kind, time_of_day)
            phase = _get_schedule_phase(time_of_day)
            for npc in present:
                inpc = place_npc_in_appropriate_room(interior, npc, phase, _rng)
                npc._interior_x = inpc.x
                npc._interior_y = inpc.y
                npc._interior_activity = inpc.activity
                interior._cached_npcs.append(npc)
                interior._active_interior_npcs.append(inpc)

        # Register damage sync callback so exterior damage affects this interior
        if world and hasattr(world, 'register_tile_callback') and interior._world_to_interior:
            def _sync_damage(wx, wy, new_type, _int=interior):
                _int.sync_exterior_damage(wx, wy, new_type)
            world.register_tile_callback(_sync_damage)

        # Start transition
        self.transitioning = True
        self.transition_alpha = 0
        self.transition_target = building_name
        self.transition_entering = True

        return interior

    def exit_building(self):
        """Player exits to the overworld."""
        self.is_inside = False
        self.current_interior = None
        self.current_floor = 0
        self.transitioning = False
        self.transition_alpha = 0

    def complete_exit(self):
        """Called after exit transition completes. Kept for compatibility."""
        self.is_inside = False
        self.current_interior = None
        self.current_floor = 0
        self.transitioning = False

    def change_floor(self, new_floor: int):
        """Move to a different floor via stairs.
        Places player at matching stair position on the new floor.
        """
        if not self.current_interior:
            return

        old_interior = self.current_interior
        old_floor = self.current_floor
        building_name = old_interior.building_name
        building_kind = old_interior.building_kind
        world_x = old_interior.world_x
        world_y = old_interior.world_y

        # Remember where the player used the stairs on the old floor
        stair_x = int(self.interior_x)
        stair_y = int(self.interior_y)

        # Use the stored cache key so we look up the same floors dict
        # that was used when entering the building (avoids cache key mismatch
        # when building_rect was provided to enter_building but not here)
        cache_key = getattr(old_interior, '_cache_key', None)
        if cache_key and cache_key in self.building_interiors:
            floors = self.building_interiors[cache_key]
            if new_floor in floors:
                interior = floors[new_floor]
            else:
                # Generate new floor under the correct cache key
                building_rect = getattr(old_interior, '_building_rect', None)
                interior = self.get_or_create_interior(
                    building_name, building_kind, new_floor, world_x, world_y,
                    building_rect=building_rect)
                # Move the new floor into the correct cache bucket
                if getattr(interior, '_cache_key', None) != cache_key:
                    floors[new_floor] = interior
                    interior._cache_key = cache_key
        else:
            # Fallback: use get_or_create_interior directly
            building_rect = getattr(old_interior, '_building_rect', None)
            interior = self.get_or_create_interior(
                building_name, building_kind, new_floor, world_x, world_y,
                building_rect=building_rect)

        # Force new floor to have same footprint
        # (generators should already do this, but enforce it)

        self.current_interior = interior
        self.current_floor = new_floor

        # Find the matching stair on the new floor:
        # Going UP (new_floor > old_floor) → look for STAIRS_DOWN on new floor
        # Going DOWN (new_floor < old_floor) → look for STAIRS_UP on new floor
        target_stair = STAIRS_DOWN if new_floor > old_floor else STAIRS_UP

        best_stair = None
        best_dist = float('inf')
        for y in range(interior.height):
            for x in range(interior.width):
                if interior.tiles[y][x] == target_stair:
                    # Prefer the stair closest to where we were on the old floor
                    d = abs(x - stair_x) + abs(y - stair_y)
                    if d < best_dist:
                        best_dist = d
                        best_stair = (x, y)

        if best_stair:
            self.interior_x = float(best_stair[0])
            self.interior_y = float(best_stair[1])
        else:
            # No matching stair found — place at same position (clamped)
            self.interior_x = float(min(stair_x, interior.width - 2))
            self.interior_y = float(min(stair_y, interior.height - 2))
            # Ensure walkable
            if not interior.is_walkable(int(self.interior_x), int(self.interior_y)):
                self.interior_x = float(interior.entry_x)
                self.interior_y = float(interior.entry_y)

    def update_transition(self, dt: float) -> bool:
        """Update transition animation. Returns True when complete."""
        if not self.transitioning:
            return False

        speed = 400  # alpha per second
        if self.transition_entering:
            self.transition_alpha = min(255, self.transition_alpha + int(speed * dt))
            if self.transition_alpha >= 255:
                self.transitioning = False
                return True
        else:
            self.transition_alpha = min(255, self.transition_alpha + int(speed * dt))
            if self.transition_alpha >= 255:
                self.complete_exit()
                self.transitioning = False
                return True
        return False


# ================================================================
# INTERIOR NPC AI — NPCs move around inside buildings doing activities
# ================================================================

# Activities NPCs do in each room type, with duration range (seconds)
_ROOM_ACTIVITIES = {
    "bedroom":                [("sleeping", 30, 90), ("resting", 10, 20)],
    "bedroom_poor":           [("sleeping", 25, 60), ("resting", 5, 10)],
    "bedroom_fine":           [("sleeping", 35, 90), ("resting", 12, 25), ("reading", 8, 20)],
    "bedroom_luxurious":      [("sleeping", 40, 100), ("resting", 15, 30), ("reading", 10, 25)],
    "double_bedroom":         [("sleeping", 30, 90), ("resting", 10, 20)],
    "double_bedroom_fine":    [("sleeping", 35, 90), ("resting", 12, 25)],
    "double_bedroom_luxurious":[("sleeping", 40, 100), ("resting", 15, 30)],
    "children_room":          [("sleeping", 30, 90), ("resting", 8, 15)],
    "nursery":                [("sleeping", 40, 120)],
    "servants_quarters":      [("sleeping", 25, 60), ("resting", 5, 15)],
    "dormitory":              [("sleeping", 25, 60), ("resting", 8, 20)],
    "officer_quarters":       [("sleeping", 30, 80), ("resting", 10, 20), ("reading", 5, 15)],
    "commander_quarters":     [("sleeping", 35, 90), ("resting", 12, 25), ("reading", 8, 20)],
    "guest_room":             [("sleeping", 30, 90), ("resting", 10, 20)],
    "guest_suite":            [("sleeping", 35, 90), ("resting", 12, 25)],
    "stable_loft":            [("sleeping", 20, 50), ("resting", 5, 10)],
    "common_room":      [("sitting", 8, 25), ("talking", 5, 15), ("eating", 8, 15)],
    "kitchen":          [("cooking", 10, 25), ("eating", 5, 12)],
    "dining_hall":      [("eating", 8, 20), ("talking", 5, 15), ("sitting", 5, 12)],
    "storage":          [("fetching", 3, 8)],
    "workshop":         [("working", 15, 40), ("smithing", 12, 30)],
    "throne_room":      [("attending", 10, 30), ("petitioning", 5, 15)],
    "library":          [("reading", 12, 35), ("studying", 10, 25)],
    "infirmary":        [("resting", 10, 30), ("working", 8, 20)],
    "chapel":           [("praying", 8, 25), ("sitting", 5, 12)],
    "guard_room":       [("guarding", 10, 30), ("resting", 5, 15)],
    "tavern_hall":      [("eating", 8, 20), ("talking", 5, 15), ("sitting", 8, 20)],
    "shop_floor":       [("working", 10, 25), ("talking", 5, 12)],
    "stable":           [("working", 8, 20), ("fetching", 3, 8)],
    "corridor":         [("walking", 2, 5)],
    "entry_hall":       [("waiting", 3, 10), ("arriving", 2, 4)],
    "stairwell":        [("walking", 2, 4)],
    "cellar":           [("fetching", 3, 8)],
    "dungeon_cell":     [("guarding", 10, 20)],
}

# What room types each schedule phase prefers (ordered by priority)
# All bedroom-like rooms are valid for sleeping
_SLEEP_ROOMS = ["double_bedroom_luxurious", "double_bedroom_fine", "double_bedroom",
                "bedroom_luxurious", "bedroom_fine", "bedroom", "bedroom_poor",
                "commander_quarters", "officer_quarters",
                "children_room", "nursery", "servants_quarters",
                "dormitory", "guest_suite", "guest_room", "guard_room", "stable_loft"]
_PHASE_ROOM_PREFERENCE = {
    "sleep":          _SLEEP_ROOMS,
    "wake_eat":       ["kitchen", "dining_hall", "common_room", "tavern_hall"],
    "morning_work":   ["workshop", "library", "throne_room", "shop_floor",
                       "stable", "guard_room", "infirmary", "chapel"],
    "lunch":          ["dining_hall", "kitchen", "common_room", "tavern_hall"],
    "afternoon_work": ["workshop", "library", "throne_room", "shop_floor",
                       "stable", "guard_room", "infirmary"],
    "evening":        ["common_room", "tavern_hall", "dining_hall", "kitchen"],
    "night":          _SLEEP_ROOMS + ["common_room"],
}


class InteriorNPC:
    """Lightweight state wrapper for an NPC active inside a building interior."""
    __slots__ = ('npc', 'x', 'y', 'target_x', 'target_y',
                 'activity', 'activity_timer', 'target_room_idx',
                 'speed', 'moving')

    def __init__(self, npc, x: float, y: float):
        self.npc = npc
        self.x = x
        self.y = y
        self.target_x = x
        self.target_y = y
        self.activity = "idle"
        self.activity_timer = 0.0
        self.target_room_idx = -1
        self.speed = 1.2  # tiles per second in interior
        self.moving = False


def _find_tile_in_room(interior, room: dict, tile_type: int):
    """Find a specific tile type within a room. Returns (x, y) or None."""
    rx, ry, rw, rh = room["x"], room["y"], room["w"], room["h"]
    for ty in range(ry, ry + rh):
        for tx in range(rx, rx + rw):
            if 0 <= tx < interior.width and 0 <= ty < interior.height:
                if interior.tiles[ty][tx] == tile_type:
                    return (tx, ty)
    return None


def _find_walkable_in_room(interior, room: dict, rng):
    """Find a random walkable tile in a room."""
    rx, ry, rw, rh = room["x"], room["y"], room["w"], room["h"]
    for _ in range(20):
        tx = rng.randint(rx, rx + rw - 1)
        ty = rng.randint(ry, ry + rh - 1)
        if interior.is_walkable(tx, ty):
            return (tx, ty)
    # Fallback: scan
    for ty in range(ry, ry + rh):
        for tx in range(rx, rx + rw):
            if interior.is_walkable(tx, ty):
                return (tx, ty)
    return (rx + rw // 2, ry + rh // 2)


# Rank → preferred sleeping room quality (highest first)
_RANK_SLEEP_ROOM = {
    # Royalty/top rank
    "monarch":    ["double_bedroom_luxurious", "bedroom_luxurious", "double_bedroom_fine"],
    "high_priest":["bedroom_luxurious", "bedroom_fine"],
    "tyrant":     ["double_bedroom_luxurious", "bedroom_luxurious"],
    "chief":      ["double_bedroom_fine", "bedroom_fine"],
    # Upper rank
    "duke":       ["double_bedroom_fine", "bedroom_fine"],
    "lord":       ["double_bedroom_fine", "bedroom_fine"],
    "senator":    ["bedroom_fine", "double_bedroom_fine"],
    "patrician":  ["bedroom_fine", "double_bedroom"],
    # Military officers
    "knight":     ["commander_quarters", "bedroom_fine", "officer_quarters"],
    "commander":  ["commander_quarters", "bedroom_fine"],
    "captain":    ["commander_quarters", "officer_quarters"],
    "marshal":    ["bedroom_luxurious", "commander_quarters"],
    # NCOs
    "sergeant":   ["officer_quarters", "bedroom"],
    # Servants / lower
    "servant":    ["servants_quarters", "bedroom_poor"],
    "serf":       ["bedroom_poor", "servants_quarters", "stable_loft"],
    "slave":      ["bedroom_poor", "stable_loft"],
    # Workers
    "guard":      ["guard_room", "dormitory", "officer_quarters"],
    "enforcer":   ["guard_room", "dormitory"],
    # Religious
    "clergy":     ["bedroom", "bedroom_fine"],
    # Default military
    "recruit":    ["dormitory", "bedroom_poor"],
    "soldier":    ["dormitory", "bedroom_poor"],
}

# Class → work room preference
_CLASS_WORK_ROOM = {
    "Fighter":   ["guard_room", "dining_hall", "common_room"],
    "Wizard":    ["library", "chapel"],
    "Cleric":    ["chapel", "infirmary", "library"],
    "Rogue":     ["shop_floor", "storage", "common_room"],
    "Ranger":    ["stable", "storage", "common_room"],
    "Paladin":   ["chapel", "guard_room", "throne_room"],
    "Barbarian": ["dining_hall", "common_room"],
    "Bard":      ["tavern_hall", "common_room", "library"],
    "Druid":     ["library", "infirmary", "storage"],
    "Monk":      ["chapel", "library"],
    "Sorcerer":  ["library", "bedroom_fine"],
    "Warlock":   ["library", "storage"],
    "Scholar":   ["library"],
    "Farmer":    ["stable", "storage", "kitchen"],
    "Blacksmith":["workshop"],
    "Merchant":  ["shop_floor", "storage"],
    "Healer":    ["infirmary"],
    "Innkeeper": ["tavern_hall", "kitchen"],
}


def place_npc_in_appropriate_room(interior, npc, phase: str, rng):
    """Place an NPC in the room appropriate for their rank, class, and time.

    During sleep: rank determines room quality (royalty → luxurious, recruit → dormitory).
    During work: class determines room (wizard → library, guard → guard_room).
    During meals: everyone goes to dining/common/kitchen.
    """
    rooms = interior.rooms
    if not rooms:
        for _ in range(20):
            rx = rng.randint(2, max(3, interior.width - 3))
            ry = rng.randint(2, max(3, interior.height - 3))
            if interior.is_walkable(rx, ry):
                return InteriorNPC(npc, float(rx), float(ry))
        return InteriorNPC(npc, float(interior.entry_x), float(interior.entry_y))

    title = getattr(npc, 'title', 'commoner')
    char_class = getattr(npc, 'char_class', '')
    target_room = None

    if phase in ("sleep", "night"):
        # === SLEEPING: match rank to room quality ===
        rank_prefs = _RANK_SLEEP_ROOM.get(title, [])
        # Try rank-specific rooms first
        for pref in rank_prefs:
            candidates = [r for r in rooms if r["room_type"] == pref]
            if candidates:
                target_room = rng.choice(candidates)
                break
        # Fallback: any bed room
        if not target_room:
            for pref in _SLEEP_ROOMS:
                candidates = [r for r in rooms if r["room_type"] == pref]
                if candidates:
                    target_room = rng.choice(candidates)
                    break

        if target_room:
            bed_pos = _find_tile_in_room(interior, target_room, BED)
            if bed_pos:
                inpc = InteriorNPC(npc, float(bed_pos[0]), float(bed_pos[1]))
                inpc.activity = "sleeping"
                inpc.activity_timer = rng.uniform(20, 60)
                return inpc

    elif phase in ("morning_work", "afternoon_work"):
        # === WORKING: match class to work room ===
        class_prefs = _CLASS_WORK_ROOM.get(char_class, [])
        for pref in class_prefs:
            candidates = [r for r in rooms if r["room_type"] == pref]
            if candidates:
                target_room = rng.choice(candidates)
                break
        # Servants go to common areas to serve
        if not target_room and title == "servant":
            for rt in ["kitchen", "dining_hall", "common_room", "storage"]:
                candidates = [r for r in rooms if r["room_type"] == rt]
                if candidates:
                    target_room = rng.choice(candidates)
                    break

    elif phase in ("wake_eat", "lunch", "evening"):
        # === EATING/SOCIAL: rank affects where you eat ===
        if title in ("monarch", "duke", "lord", "high_priest"):
            # Nobles eat in dining hall or their chambers
            for rt in ["dining_hall", "common_room", "double_bedroom_fine",
                        "double_bedroom_luxurious"]:
                candidates = [r for r in rooms if r["room_type"] == rt]
                if candidates:
                    target_room = rng.choice(candidates)
                    break
        elif title == "servant":
            # Servants eat in kitchen
            for rt in ["kitchen", "servants_quarters", "dining_hall"]:
                candidates = [r for r in rooms if r["room_type"] == rt]
                if candidates:
                    target_room = rng.choice(candidates)
                    break

    # Fallback: generic phase preference
    if not target_room:
        preferred = _PHASE_ROOM_PREFERENCE.get(phase, ["common_room"])
        for pref in preferred:
            candidates = [r for r in rooms if r["room_type"] == pref]
            if candidates:
                target_room = rng.choice(candidates)
                break

    # Last resort: any non-corridor room
    if not target_room:
        non_corridor = [r for r in rooms
                        if r["room_type"] not in ("corridor", "stairwell")]
        target_room = rng.choice(non_corridor) if non_corridor else rooms[0]

    pos = _find_walkable_in_room(interior, target_room, rng)
    inpc = InteriorNPC(npc, float(pos[0]), float(pos[1]))

    activities = _ROOM_ACTIVITIES.get(target_room["room_type"], [("idle", 5, 15)])
    act_name, t_min, t_max = rng.choice(activities)
    inpc.activity = act_name
    inpc.activity_timer = rng.uniform(t_min, t_max)
    inpc.target_room_idx = rooms.index(target_room) if target_room in rooms else -1

    return inpc


def update_interior_npcs(interior, dt: float, time_of_day: float):
    """Update all NPCs inside a building — movement and activity switching.

    Called each frame while the player is inside the building.
    """
    import random as _rng
    import math

    active_npcs = getattr(interior, '_active_interior_npcs', [])
    if not active_npcs:
        return

    phase = _get_schedule_phase(time_of_day)
    rooms = interior.rooms

    for inpc in active_npcs:
        # Tick activity timer
        inpc.activity_timer -= dt
        npc = inpc.npc

        # Sync position back to NPC for renderer
        npc._interior_x = inpc.x
        npc._interior_y = inpc.y

        if inpc.moving:
            # Move toward target
            dx = inpc.target_x - inpc.x
            dy = inpc.target_y - inpc.y
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.3:
                inpc.x = inpc.target_x
                inpc.y = inpc.target_y
                inpc.moving = False
            else:
                step = inpc.speed * dt
                nx = dx / dist
                ny = dy / dist
                new_x = inpc.x + nx * step
                new_y = inpc.y + ny * step
                if interior.is_walkable(int(new_x), int(inpc.y)):
                    inpc.x = new_x
                if interior.is_walkable(int(inpc.x), int(new_y)):
                    inpc.y = new_y

        elif inpc.activity_timer <= 0:
            # Choose next activity — pick a new room to go to
            if not rooms:
                inpc.activity_timer = _rng.uniform(5, 15)
                continue

            # Decide where to go based on phase
            preferred = _PHASE_ROOM_PREFERENCE.get(phase, ["common_room"])
            target_room = None

            # Weighted choice: 60% preferred room, 30% any room, 10% stay
            roll = _rng.random()
            if roll < 0.60:
                for pref in preferred:
                    candidates = [r for r in rooms if r["room_type"] == pref]
                    if candidates:
                        target_room = _rng.choice(candidates)
                        break
            if not target_room and roll < 0.90:
                non_corridor = [r for r in rooms
                                if r["room_type"] not in ("corridor", "stairwell")]
                if non_corridor:
                    target_room = _rng.choice(non_corridor)

            if target_room:
                # Move to the chosen room
                pos = _find_walkable_in_room(interior, target_room, _rng)
                inpc.target_x = float(pos[0])
                inpc.target_y = float(pos[1])
                inpc.moving = True

                activities = _ROOM_ACTIVITIES.get(target_room["room_type"],
                                                   [("idle", 5, 15)])
                act_name, t_min, t_max = _rng.choice(activities)
                inpc.activity = act_name
                inpc.activity_timer = _rng.uniform(t_min, t_max)
            else:
                # Stay in place
                inpc.activity = "idle"
                inpc.activity_timer = _rng.uniform(5, 12)


def _align_stairs_with_floor(new_floor: "InteriorMap", reference_floor: "InteriorMap",
                              new_floor_num: int):
    """Ensure stairs on new_floor match stair positions on reference_floor.

    If going up from floor 0: floor 1's STAIRS_DOWN should be at floor 0's STAIRS_UP position.
    If going down from floor 0: floor -1's STAIRS_UP should be at floor 0's STAIRS_DOWN position.
    """
    # Find stairs on reference floor
    ref_up = []
    ref_down = []
    for y in range(reference_floor.height):
        for x in range(reference_floor.width):
            if reference_floor.tiles[y][x] == STAIRS_UP:
                ref_up.append((x, y))
            elif reference_floor.tiles[y][x] == STAIRS_DOWN:
                ref_down.append((x, y))

    # Determine which reference stairs to match
    if new_floor_num > 0:
        # Going up — new floor needs STAIRS_DOWN at ref's STAIRS_UP positions
        targets = ref_up
        tile_to_place = STAIRS_DOWN
        tile_to_companion = STAIRS_UP
    else:
        # Going down — new floor needs STAIRS_UP at ref's STAIRS_DOWN positions
        targets = ref_down
        tile_to_place = STAIRS_UP
        tile_to_companion = STAIRS_DOWN

    if not targets:
        return

    for tx, ty in targets:
        # Clear any existing stairs on the new floor first
        for y2 in range(new_floor.height):
            for x2 in range(new_floor.width):
                if new_floor.tiles[y2][x2] in (STAIRS_UP, STAIRS_DOWN):
                    new_floor.tiles[y2][x2] = FLOOR

        # Place the matching stair at the target position (or nearest walkable)
        # First try to FORCE the exact position by clearing it
        if (0 <= tx < new_floor.width and 0 <= ty < new_floor.height):
            # Clear the target tile and its neighbor for stairs
            if new_floor.tiles[ty][tx] != WALL:
                new_floor.tiles[ty][tx] = FLOOR
            for dx2, dy2 in [(1,0),(-1,0),(0,1),(0,-1)]:
                cx, cy = tx + dx2, ty + dy2
                if (0 <= cx < new_floor.width and 0 <= cy < new_floor.height
                    and new_floor.tiles[cy][cx] != WALL):
                    new_floor.tiles[cy][cx] = FLOOR

        placed = False
        for radius in range(0, 5):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx, ny = tx + dx, ty + dy
                    if (0 <= nx < new_floor.width and 0 <= ny < new_floor.height
                        and new_floor.tiles[ny][nx] == FLOOR):
                        new_floor.tiles[ny][nx] = tile_to_place
                        # Place companion stair adjacent
                        for dx2, dy2 in [(1,0),(-1,0),(0,1),(0,-1)]:
                            cx, cy = nx + dx2, ny + dy2
                            if (0 <= cx < new_floor.width and 0 <= cy < new_floor.height
                                and new_floor.tiles[cy][cx] == FLOOR):
                                new_floor.tiles[cy][cx] = tile_to_companion
                                break
                        placed = True
                        break
                if placed:
                    break
            if placed:
                break
        break  # only handle first stair pair


# ================================================================
# NPC PRESENCE DETERMINATION — who is actually inside a building?
# ================================================================

# Base probability of being home during each schedule phase
_HOME_PROBABILITY = {
    "sleep":         0.92,
    "wake_eat":      0.82,
    "morning_work":  0.12,
    "lunch":         0.25,
    "afternoon_work":0.10,
    "evening":       0.35,
    "night":         0.80,
}

# Classes and their work-from-home tendency (added to base prob during work hours)
_CLASS_HOME_MOD = {
    "Farmer": 0.15, "Scholar": 0.25, "Healer": 0.10, "Druid": 0.15,
    "Sorcerer": 0.20, "Warlock": 0.18,
    "Ranger": -0.25, "Rogue": -0.15, "Barbarian": -0.20,
    "Fighter": -0.05, "Monk": -0.10, "Paladin": -0.05,
    "Bard": -0.10, "Wizard": 0.10, "Cleric": 0.05,
}

# Titles and where they'd be during work hours
_TITLE_WORK_LOCATION = {
    "servant": "castle",    # servants are at the castle/manor
    "guard": "patrol",      # guards patrol, not at home
    "knight": "castle",     # knights at court
    "lord": "castle",       # lords at court
    "duke": "castle",       # dukes at court
    "monarch": "castle",    # ruler in throne room
}


def _get_schedule_phase(time_of_day: float) -> str:
    """Get the current schedule phase name from normalized time."""
    if time_of_day < 0.22:
        return "sleep"
    elif time_of_day < 0.28:
        return "wake_eat"
    elif time_of_day < 0.48:
        return "morning_work"
    elif time_of_day < 0.53:
        return "lunch"
    elif time_of_day < 0.68:
        return "afternoon_work"
    elif time_of_day < 0.78:
        return "evening"
    else:
        return "night"


def _npc_presence_probability(npc, phase: str, building_kind: str,
                               building_world_x: int, building_world_y: int,
                               all_npcs: list) -> float:
    """Calculate the probability that an NPC is at their home building right now.

    Factors in: schedule phase, class, title, family, relationships,
    social needs, intrigue involvement, age, and building type.
    """
    prob = _HOME_PROBABILITY.get(phase, 0.3)

    char_class = getattr(npc, 'char_class', '')
    title = getattr(npc, 'title', 'commoner')
    age_cat = getattr(npc, 'age_category', 'prime')
    social_traits = getattr(npc, 'social_traits', [])
    needs = getattr(npc, 'needs', {})
    state = getattr(npc, 'state', 'idle')

    # --- Class modifier ---
    prob += _CLASS_HOME_MOD.get(char_class, 0.0)

    # --- Title/role modifier ---
    # Servants, guards, knights work at the castle, not at their own home
    work_loc = _TITLE_WORK_LOCATION.get(title)
    if work_loc and phase in ("morning_work", "afternoon_work"):
        if work_loc == "castle" and building_kind not in ("castle",):
            prob -= 0.40  # servants/guards/knights are at the castle, not home
        elif work_loc == "castle" and building_kind == "castle":
            prob += 0.30  # they ARE at the castle during work
        elif work_loc == "patrol":
            prob -= 0.50  # guards are out patrolling

    # Rulers live in castles
    if getattr(npc, 'is_ruler', False):
        if building_kind == "castle":
            prob += 0.40  # ruler is almost always at the castle
        else:
            prob -= 0.30  # ruler wouldn't be at a random house

    # --- Family / meals modifier ---
    # During meal times, family members cluster at home
    if phase in ("wake_eat", "lunch", "evening"):
        # Check if other family members live in same building
        npc_family_id = getattr(npc, 'family_id', None)
        if npc_family_id:
            family_here = sum(1 for other in all_npcs
                             if getattr(other, 'family_id', None) == npc_family_id
                             and other.name != npc.name
                             and abs(other.home_x - building_world_x) < 10
                             and abs(other.home_y - building_world_y) < 10)
            if family_here > 0:
                prob += 0.15 * min(family_here, 3)  # up to +0.45 for family meals

    # Spouse proximity — if spouse is home, more likely to be home too
    spouse_name = None
    life_ledger = getattr(npc, 'life_ledger', None)
    if life_ledger:
        for bond in getattr(life_ledger, 'bonds', []):
            if getattr(bond, 'bond_type', '') == 'spouse':
                spouse_name = getattr(bond, 'other_name', None)
                break
    if spouse_name:
        for other in all_npcs:
            if other.name == spouse_name:
                if (abs(other.home_x - building_world_x) < 10 and
                    abs(other.home_y - building_world_y) < 10):
                    if phase in ("sleep", "wake_eat", "evening", "night"):
                        prob += 0.15  # couples tend to be home together

    # --- Personality traits ---
    if "homebody" in social_traits or "cautious" in social_traits:
        prob += 0.10
    if "adventurous" in social_traits or "restless" in social_traits:
        prob -= 0.10
    if "social_butterfly" in social_traits and phase in ("lunch", "evening"):
        prob -= 0.15  # out socializing
    if "loner" in social_traits:
        prob += 0.08  # prefers staying in

    # --- Age modifier ---
    if age_cat in ("elder", "ancient"):
        prob += 0.20  # elderly stay home more
    elif age_cat == "child":
        prob += 0.25  # children mostly at home
    elif age_cat == "young":
        prob -= 0.05  # young adults out more

    # --- Social needs ---
    social_need = needs.get("social", 50)
    if social_need < 25 and phase in ("evening", "lunch"):
        prob -= 0.20  # desperate for socializing, goes to tavern

    # --- Rest needs ---
    rest_need = needs.get("rest", 50)
    if rest_need < 20:
        prob += 0.30  # exhausted, stays home

    # --- Intrigue modifier ---
    # Active plotters sometimes meet in secret (away from home)
    current_action = getattr(npc, 'current_action', '')
    if "plot" in current_action or "conspir" in current_action:
        if phase in ("evening", "night"):
            prob -= 0.25  # out plotting

    # --- Sleeping state override ---
    if state == "sleeping":
        prob = 0.95  # sleeping NPCs are home

    # --- Building-specific visitor logic (non-residential) ---
    if building_kind == "tavern":
        if phase in ("evening", "night", "lunch"):
            prob += 0.10  # people visit taverns
        if "social_butterfly" in social_traits:
            prob += 0.10
    elif building_kind == "temple":
        if char_class in ("Cleric", "Paladin", "Monk"):
            prob += 0.15  # clergy at temple
    elif building_kind == "castle":
        if title in ("servant", "guard", "knight", "lord", "duke", "monarch"):
            if phase in ("morning_work", "afternoon_work"):
                prob += 0.25  # court officials at castle

    return max(0.0, min(1.0, prob))


def _get_npcs_present_in_building(all_npcs: list, building_world_x: int,
                                   building_world_y: int,
                                   building_rect: tuple = None,
                                   building_kind: str = "house",
                                   time_of_day: float = 0.3) -> list:
    """Determine which NPCs are actually present inside a building right now.

    For active (nearby) NPCs: checks their real world position.
    For dormant (distant) NPCs: uses rich probabilistic model considering
    schedule, class, title, family, relationships, personality, intrigue.

    Non-residents may visit taverns, temples, shops based on social needs.
    """
    import random as _rng
    import math

    present = []
    phase = _get_schedule_phase(time_of_day)

    if building_rect:
        bx, by, bw, bh = building_rect
    else:
        bx, by, bw, bh = building_world_x - 5, building_world_y - 5, 10, 10

    home_radius = max(bw, bh) + 3

    # Collect residents and potential visitors separately
    for npc in all_npcs:
        if not getattr(npc, 'alive', True):
            continue

        home_dx = abs(npc.home_x - building_world_x)
        home_dy = abs(npc.home_y - building_world_y)
        is_resident = home_dx < home_radius and home_dy < home_radius

        # --- ACTIVE NPC: use real position ---
        is_active = (getattr(npc, 'state_timer', 0) > 0 or
                     npc.state not in ("idle", "sleeping"))
        if is_active and is_resident:
            npc_in_footprint = (bx - 2 <= npc.x <= bx + bw + 2 and
                                by - 2 <= npc.y <= by + bh + 2)
            if npc_in_footprint:
                present.append(npc)
                continue
            # Sleeping NPCs forced home
            if npc.state == "sleeping" and phase in ("sleep", "night"):
                present.append(npc)
                continue

        # --- DORMANT NPC or inactive active NPC: probabilistic ---
        if is_resident:
            prob = _npc_presence_probability(
                npc, phase, building_kind,
                building_world_x, building_world_y, all_npcs)
        else:
            # Non-resident visitor logic
            dist = math.sqrt((npc.x - building_world_x)**2 +
                             (npc.y - building_world_y)**2)
            if dist > 40:
                continue  # too far to visit

            prob = 0.0
            if building_kind == "tavern" and phase in ("lunch", "evening", "night"):
                prob = 0.06
                if "social_butterfly" in getattr(npc, 'social_traits', []):
                    prob += 0.04
                social = getattr(npc, 'needs', {}).get("social", 50)
                if social < 30:
                    prob += 0.08  # lonely NPC seeks company
                # Friends of residents visit more
                friends = getattr(npc, 'friends', [])
                for res in all_npcs:
                    if (res.name in friends and
                        abs(res.home_x - building_world_x) < home_radius and
                        abs(res.home_y - building_world_y) < home_radius):
                        prob += 0.05
                        break
            elif building_kind == "temple":
                if phase in ("morning_work", "evening"):
                    prob = 0.03
                    if getattr(npc, 'char_class', '') in ("Cleric", "Paladin", "Monk"):
                        prob += 0.10
            elif building_kind == "shop":
                if phase in ("morning_work", "afternoon_work"):
                    prob = 0.03
                    if getattr(npc, 'char_class', '') in ("Rogue", "Bard"):
                        prob += 0.04
            elif building_kind == "castle":
                title = getattr(npc, 'title', 'commoner')
                if title in ("servant", "guard", "knight", "lord", "duke"):
                    if phase in ("morning_work", "afternoon_work"):
                        prob = 0.30
                # Intrigue: conspirators sneak into castles
                current_action = getattr(npc, 'current_action', '')
                if "plot" in current_action and phase in ("night",):
                    prob += 0.10

            # Romantic visitors — NPC visiting a love interest's home
            life_ledger = getattr(npc, 'life_ledger', None)
            if life_ledger:
                for bond in getattr(life_ledger, 'bonds', []):
                    bond_type = getattr(bond, 'bond_type', '')
                    other = getattr(bond, 'other_name', '')
                    if bond_type in ('spouse', 'lover', 'friend'):
                        for res in all_npcs:
                            if (res.name == other and
                                abs(res.home_x - building_world_x) < home_radius and
                                abs(res.home_y - building_world_y) < home_radius):
                                if bond_type == 'spouse':
                                    prob += 0.25  # visiting spouse
                                elif bond_type == 'lover':
                                    if phase in ("evening", "night"):
                                        prob += 0.15  # secret affair visit
                                elif bond_type == 'friend':
                                    if phase in ("evening",):
                                        prob += 0.06  # visiting friend
                                break

            if prob <= 0:
                continue

        # Deterministic hash for stability
        seed = hash((npc.name, building_world_x, building_world_y, phase)) & 0xFFFFFFFF
        if _rng.Random(seed).random() < prob:
            present.append(npc)

    return present


# ================================================================
# OVERWORLD BUILDING VISIBILITY — hide interiors on the main map
# ================================================================

# ================================================================
# CREATE INTERIOR FROM ACTUAL OVERWORLD TILES
# ================================================================

def create_interior_from_world(world, building_rect: tuple,
                                building_name: str,
                                building_kind: str) -> InteriorMap:
    """Create an interior map from actual overworld building tiles.

    Walls stay 1 tile thick. Floor space between walls is expanded so
    rooms feel larger. Furniture is placed once (not duplicated).

    Strategy: for each overworld tile, check if it's a wall or floor.
    Walls map 1:1, floors get an extra row/column inserted between them
    and adjacent walls, expanding the room.
    """
    bx, by, bw, bh = building_rect

    # Read overworld tiles into a local grid
    src = []
    for wy in range(bh):
        row = []
        for wx in range(bw):
            world_x = bx + wx
            world_y = by + wy
            if 0 <= world_x < world.width and 0 <= world_y < world.height:
                row.append(world.tiles[world_y][world_x])
            else:
                row.append(WALL)
        src.append(row)

    # Classify tiles
    solid_tiles = {WALL, WINDOW, GRASS, ROAD, SAND}
    def is_solid(t):
        return t in solid_tiles or t >= 40

    # Scale up resolution: floor tiles expand to INTERIOR_SCALE x INTERIOR_SCALE,
    # wall tiles stay 1 tile thick. This gives rooms more space and detail
    # while keeping walls thin.
    scale = INTERIOR_SCALE  # 3x

    # First pass: compute the interior position of each source tile.
    # Walls get 1 row/col, floor-like tiles get `scale` rows/cols.
    col_size = []  # width of each source column in interior tiles
    for wx in range(bw):
        is_all_wall = all(is_solid(src[wy][wx]) for wy in range(bh))
        col_size.append(1 if is_all_wall else scale)

    row_size = []  # height of each source row in interior tiles
    for wy in range(bh):
        is_all_wall = all(is_solid(src[wy][wx]) for wx in range(bw))
        row_size.append(1 if is_all_wall else scale)

    iw = sum(col_size)
    ih = sum(row_size)

    interior = InteriorMap(iw, ih, building_name, building_kind, 0)
    interior.world_x = bx + bw // 2
    interior.world_y = by + bh // 2
    interior._building_rect = (bx, by, bw, bh)

    # Second pass: stamp each source tile into the interior at its mapped position
    # Also build the world→interior mapping for damage sync
    entry_set = False
    iy_start = 0
    for wy in range(bh):
        rh = row_size[wy]
        ix_start = 0
        for wx in range(bw):
            cw = col_size[wx]
            tile = src[wy][wx]
            world_x = bx + wx
            world_y = by + wy

            # Build mapping: this overworld tile → these interior tiles
            interior_positions = []
            for dy in range(rh):
                for dx in range(cw):
                    tx = ix_start + dx
                    ty = iy_start + dy
                    if 0 <= tx < iw and 0 <= ty < ih:
                        interior_positions.append((tx, ty))
            if interior_positions:
                interior._world_to_interior[(world_x, world_y)] = interior_positions

            for dy in range(rh):
                for dx in range(cw):
                    tx = ix_start + dx
                    ty = iy_start + dy
                    if not (0 <= tx < iw and 0 <= ty < ih):
                        continue

                    if is_solid(tile):
                        interior.tiles[ty][tx] = WINDOW if tile == WINDOW else WALL
                    elif tile == DOOR:
                        # Door occupies one tile; rest is floor
                        if dx == cw // 2 and dy == rh // 2:
                            interior.tiles[ty][tx] = DOOR
                            if not entry_set:
                                edge = (wx <= 1 or wx >= bw-2 or wy <= 1 or wy >= bh-2)
                                if edge:
                                    interior.entry_x = tx
                                    interior.entry_y = ty
                                    entry_set = True
                        else:
                            interior.tiles[ty][tx] = FLOOR
                    elif tile == LOCKED_DOOR:
                        if dx == cw // 2 and dy == rh // 2:
                            interior.tiles[ty][tx] = LOCKED_DOOR
                        else:
                            interior.tiles[ty][tx] = FLOOR
                    elif tile in (TABLE, BED, CHEST, STAIRS_UP, STAIRS_DOWN,
                                  PILLAR, ALTAR, FIREPLACE, THRONE, BOOKSHELF,
                                  BARREL, ANVIL, FORGE_FIRE, FOUNTAIN, CARPET,
                                  MOSAIC, ARCHWAY, IRON_GATE):
                        # Furniture occupies center tile; rest is floor
                        if dx == cw // 2 and dy == rh // 2:
                            interior.tiles[ty][tx] = tile
                        else:
                            interior.tiles[ty][tx] = FLOOR
                    else:
                        interior.tiles[ty][tx] = FLOOR

            ix_start += cw
        iy_start += rh

    # Find entry if not set
    if not entry_set:
        for iy2 in range(ih - 1, -1, -1):
            for ix2 in range(iw):
                if interior.tiles[iy2][ix2] == DOOR:
                    interior.entry_x = ix2
                    interior.entry_y = iy2
                    entry_set = True
                    break
            if entry_set:
                break

    if not entry_set:
        interior.entry_x = iw // 2
        interior.entry_y = ih - 2
        if 0 <= interior.entry_y < ih and 0 <= interior.entry_x < iw:
            interior.tiles[interior.entry_y][interior.entry_x] = FLOOR
        if interior.entry_y + 1 < ih:
            interior.tiles[interior.entry_y + 1][interior.entry_x] = DOOR

    # Detect rooms by flood-filling floor regions
    visited = set()
    floor_like = {FLOOR, TABLE, BED, CHEST, STAIRS_UP, STAIRS_DOWN,
                  PILLAR, ALTAR, FIREPLACE, THRONE, BOOKSHELF, BARREL,
                  ANVIL, FORGE_FIRE, FOUNTAIN, CARPET, MOSAIC, ARCHWAY, DOOR}

    for sy2 in range(ih):
        for sx2 in range(iw):
            if (sx2, sy2) in visited:
                continue
            if interior.tiles[sy2][sx2] not in floor_like:
                continue
            # Flood fill to find connected region
            region = []
            stack = [(sx2, sy2)]
            min_x, min_y = sx2, sy2
            max_x, max_y = sx2, sy2
            while stack:
                cx, cy = stack.pop()
                if (cx, cy) in visited:
                    continue
                if not (0 <= cx < iw and 0 <= cy < ih):
                    continue
                if interior.tiles[cy][cx] not in floor_like:
                    continue
                visited.add((cx, cy))
                region.append((cx, cy))
                min_x = min(min_x, cx)
                min_y = min(min_y, cy)
                max_x = max(max_x, cx)
                max_y = max(max_y, cy)
                for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    stack.append((cx+dx, cy+dy))

            if len(region) >= 4:  # minimum room size
                rw2 = max_x - min_x + 1
                rh2 = max_y - min_y + 1
                # Classify room by its furniture
                room_type = "common_room"
                has_bed = any(interior.tiles[ry][rx] == BED for rx, ry in region)
                has_throne = any(interior.tiles[ry][rx] == THRONE for rx, ry in region)
                has_bookshelf = any(interior.tiles[ry][rx] == BOOKSHELF for rx, ry in region)
                has_anvil = any(interior.tiles[ry][rx] == ANVIL for rx, ry in region)
                has_fireplace = any(interior.tiles[ry][rx] == FIREPLACE for rx, ry in region)
                has_chest = any(interior.tiles[ry][rx] == CHEST for rx, ry in region)
                has_table = any(interior.tiles[ry][rx] == TABLE for rx, ry in region)

                if has_throne:
                    room_type = "throne_room"
                elif has_bed:
                    room_type = "bedroom"
                elif has_bookshelf:
                    room_type = "library"
                elif has_anvil:
                    room_type = "workshop"
                elif has_fireplace and has_table:
                    room_type = "kitchen"
                elif has_chest and not has_table:
                    room_type = "storage"
                elif has_table:
                    room_type = "common_room"
                elif rw2 <= 4 or rh2 <= 4:
                    room_type = "corridor"
                else:
                    room_type = "entry_hall"

                interior.rooms.append({
                    "x": min_x, "y": min_y, "w": rw2, "h": rh2,
                    "room_type": room_type,
                    "connected_to": [],
                })

    return interior


def should_hide_tile(x: int, y: int, world, player_x: float, player_y: float,
                     player_inside: bool) -> bool:
    """Check if a tile should be hidden (covered by roof) on the overworld.

    Buildings show their roof (wall color) unless:
    - The player is inside that building
    - The tile is a window and nearby

    This makes buildings appear as solid blocks from outside.
    """
    if player_inside:
        return False  # player is in interior view, overworld not rendered

    tile = world.tiles[y][x]
    # Interior tiles (floor, furniture) should be hidden from outside
    if tile in (FLOOR, TABLE, BED, CHEST, STAIRS_UP, STAIRS_DOWN):
        # Check if this tile is inside a building
        structure = world.get_structure_at(float(x), float(y))
        if structure:
            # Player nearby can peek through windows
            dist = math.sqrt((x - player_x) ** 2 + (y - player_y) ** 2)
            if dist < 3:
                return False  # close enough to see in
            return True  # hide interior from afar

    return False
