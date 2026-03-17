"""
Realistic Building Interior Generator
======================================

Replaces the BSP-based generator with architecturally correct medieval layouts.

Design principles from medieval architecture:
- The hearth/fireplace is the CENTER of any house; rooms radiate from it
- Kitchen was often separate or at the "lower end" of the hall
- The great hall / common room is the main gathering space
- Bedrooms branch off the main hall (or are upstairs)
- Servants quarters are near the kitchen or at the back
- Corridors are minimal in smaller buildings; rooms connect directly
- Larger buildings (castles, mansions) have a central hall with wings
- Windows go on OUTER walls only
- Doors connect rooms that are adjacent
- Furniture is placed along walls, not in the center (except tables)

Generation pipeline:
    Stage 1: Room Graph      - connectivity based on building type
    Stage 2: Room Placement  - grid placement following the graph
    Stage 3: Walls and Doors - perimeter walls, shared walls, doors, windows
    Stage 4: Furniture       - realistic placement rules
    Stage 5: Decoration      - carpet, pillars, torches, clutter
"""

import random
from typing import Dict, List, Optional, Tuple, Set

from game.settings import (
    WALL, FLOOR, DOOR, TABLE, BED, CHEST,
    STAIRS_UP, STAIRS_DOWN, WINDOW, LOCKED_DOOR,
    TILE_SIZE, GRASS, ROAD, SAND,
    PILLAR, ALTAR, FIREPLACE, THRONE, BOOKSHELF,
    BARREL, ANVIL, FORGE_FIRE, FOUNTAIN, CARPET,
    MOSAIC, ARCHWAY, IRON_GATE,
)
from game.systems.interiors import InteriorMap, ROOM_TEMPLATES, BUILDING_ROOM_SETS


# ================================================================
# DIRECTION HELPERS
# ================================================================

NORTH = (0, -1)
SOUTH = (0, 1)
EAST = (1, 0)
WEST = (-1, 0)
CARDINALS = [NORTH, SOUTH, EAST, WEST]

# Opposite direction lookup
OPPOSITE = {
    NORTH: SOUTH,
    SOUTH: NORTH,
    EAST: WEST,
    WEST: EAST,
}


# ================================================================
# ROOM GRAPH NODE
# ================================================================

class RoomNode:
    """A node in the building connectivity graph."""
    __slots__ = ('room_type', 'children', 'parent', 'index',
                 'grid_x', 'grid_y', 'grid_w', 'grid_h',
                 'direction_from_parent', 'is_central')

    def __init__(self, room_type: str, index: int):
        self.room_type = room_type
        self.children: List['RoomNode'] = []
        self.parent: Optional['RoomNode'] = None
        self.index = index
        # Placement on tile grid (set during Stage 2)
        self.grid_x = 0
        self.grid_y = 0
        self.grid_w = 0
        self.grid_h = 0
        # Direction this room was placed relative to parent
        self.direction_from_parent: Optional[Tuple[int, int]] = None
        self.is_central = False

    def add_child(self, child: 'RoomNode', direction: Tuple[int, int] = None):
        self.children.append(child)
        child.parent = self
        child.direction_from_parent = direction


# ================================================================
# BUILDING TYPE CONNECTIVITY RULES
# ================================================================

# Defines which room is "central" and how rooms connect for each building type.
# Format: central_room_type -> list of (room_type, preferred_direction) pairs.
# None direction means "place wherever fits".

CONNECTIVITY_RULES = {
    # --- Residential ---
    "house": {
        "central": "common_room",
        "connections": [
            ("entry_hall", SOUTH),
            ("kitchen", EAST),
            ("double_bedroom", NORTH),
            ("children_room", NORTH),
            ("bedroom", NORTH),
            ("storage", EAST),
        ],
    },
    "cottage": {
        "central": "common_room",
        "connections": [
            ("entry_hall", SOUTH),
            ("kitchen", EAST),
            ("double_bedroom", NORTH),
            ("bedroom", NORTH),
        ],
    },
    "hovel": {
        "central": "common_room",
        "connections": [
            ("kitchen", EAST),
            ("bedroom", NORTH),
        ],
    },
    "hut": {
        "central": "common_room",
        "connections": [
            ("bedroom", NORTH),
        ],
    },

    # --- Commercial ---
    "shop": {
        "central": "shop_floor",
        "connections": [
            ("entry_hall", SOUTH),
            ("storage", NORTH),
            ("stairwell", EAST),
            ("bedroom", NORTH),
            ("kitchen", WEST),
        ],
    },
    "tavern": {
        "central": "tavern_hall",
        "connections": [
            ("entry_hall", SOUTH),
            ("kitchen", WEST),
            ("storage", WEST),
            ("guest_room", NORTH),
            ("guest_room", NORTH),
            ("guest_room", EAST),
            ("double_bedroom", EAST),
            ("stairwell", NORTH),
        ],
    },
    "inn": {
        "central": "tavern_hall",
        "connections": [
            ("entry_hall", SOUTH),
            ("kitchen", WEST),
            ("storage", WEST),
            ("guest_room", NORTH),
            ("guest_room", NORTH),
            ("guest_room", EAST),
            ("guest_suite", EAST),
            ("guest_suite", NORTH),
            ("double_bedroom", NORTH),
            ("stable_loft", WEST),
            ("stairwell", EAST),
        ],
    },
    "blacksmith": {
        "central": "workshop",
        "connections": [
            ("entry_hall", SOUTH),
            ("storage", EAST),
            ("stairwell", NORTH),
            ("bedroom", NORTH),
            ("kitchen", WEST),
        ],
    },

    # --- Religious ---
    "temple": {
        "central": "chapel",
        "connections": [
            ("entry_hall", SOUTH),
            ("library", EAST),
            ("bedroom_fine", NORTH),
            ("bedroom", WEST),
            ("bedroom", WEST),
            ("infirmary", EAST),
            ("storage", NORTH),
            ("stairwell", NORTH),
        ],
    },
    "monastery": {
        "central": "chapel",
        "connections": [
            ("entry_hall", SOUTH),
            ("library", EAST),
            ("bedroom_fine", NORTH),
            ("dormitory", WEST),
            ("dining_hall", SOUTH),
            ("kitchen", WEST),
            ("storage", WEST),
            ("cellar", NORTH),
            ("stairwell", EAST),
        ],
    },
    "shrine": {
        "central": "chapel",
        "connections": [
            ("entry_hall", SOUTH),
        ],
    },

    # --- Military ---
    "barracks": {
        "central": "dining_hall",
        "connections": [
            ("entry_hall", SOUTH),
            ("dormitory", NORTH),
            ("dormitory", EAST),
            ("officer_quarters", NORTH),
            ("commander_quarters", NORTH),
            ("kitchen", WEST),
            ("storage", WEST),
            ("guard_room", SOUTH),
            ("stairwell", EAST),
        ],
    },
    "guard_tower": {
        "central": "guard_room",
        "connections": [
            ("entry_hall", SOUTH),
            ("guard_room", NORTH),
            ("officer_quarters", EAST),
            ("storage", WEST),
            ("stairwell", NORTH),
        ],
    },
    "watchtower": {
        "central": "guard_room",
        "connections": [
            ("entry_hall", SOUTH),
            ("stairwell", NORTH),
        ],
    },

    # --- Noble ---
    "castle": {
        "central": "throne_room",
        "connections": [
            ("entry_hall", SOUTH),
            ("double_bedroom_luxurious", NORTH),
            ("bedroom_luxurious", NORTH),
            ("double_bedroom_fine", EAST),
            ("bedroom_fine", EAST),
            ("servants_quarters", WEST),
            ("servants_quarters", WEST),
            ("guard_room", SOUTH),
            ("guard_room", EAST),
            ("commander_quarters", EAST),
            ("dining_hall", WEST),
            ("kitchen", WEST),
            ("library", EAST),
            ("infirmary", NORTH),
            ("storage", WEST),
            ("cellar", WEST),
            ("stairwell", NORTH),
        ],
    },
    "mansion": {
        "central": "common_room",
        "connections": [
            ("entry_hall", SOUTH),
            ("library", EAST),
            ("double_bedroom_fine", NORTH),
            ("bedroom_fine", NORTH),
            ("children_room", NORTH),
            ("servants_quarters", WEST),
            ("dining_hall", WEST),
            ("kitchen", WEST),
            ("storage", WEST),
            ("stairwell", EAST),
        ],
    },
    "manor": {
        "central": "common_room",
        "connections": [
            ("entry_hall", SOUTH),
            ("double_bedroom_fine", NORTH),
            ("bedroom", NORTH),
            ("children_room", EAST),
            ("servants_quarters", WEST),
            ("kitchen", WEST),
            ("storage", EAST),
            ("stairwell", EAST),
        ],
    },

    # --- Agricultural ---
    "stable": {
        "central": "stable",
        "connections": [
            ("entry_hall", SOUTH),
            ("storage", EAST),
            ("stable_loft", NORTH),
        ],
    },
    "farmstead": {
        "central": "common_room",
        "connections": [
            ("entry_hall", SOUTH),
            ("double_bedroom", NORTH),
            ("children_room", NORTH),
            ("kitchen", EAST),
            ("storage", EAST),
        ],
    },
    "barn": {
        "central": "storage",
        "connections": [
            ("entry_hall", SOUTH),
            ("storage", NORTH),
            ("stable_loft", EAST),
        ],
    },

    # --- Civic ---
    "guildhall": {
        "central": "common_room",
        "connections": [
            ("entry_hall", SOUTH),
            ("library", EAST),
            ("storage", WEST),
            ("bedroom", NORTH),
            ("stairwell", NORTH),
        ],
    },
    "jail": {
        "central": "guard_room",
        "connections": [
            ("entry_hall", SOUTH),
            ("dungeon_cell", NORTH),
            ("dungeon_cell", NORTH),
            ("dungeon_cell", EAST),
            ("storage", WEST),
        ],
    },
    "hospital": {
        "central": "infirmary",
        "connections": [
            ("entry_hall", SOUTH),
            ("infirmary", NORTH),
            ("bedroom", EAST),
            ("storage", WEST),
            ("kitchen", WEST),
        ],
    },

    # --- Wilderness ---
    "cabin": {
        "central": "common_room",
        "connections": [
            ("bedroom", NORTH),
            ("storage", EAST),
        ],
    },
    "tent": {
        "central": "bedroom",
        "connections": [],
    },
    "dungeon": {
        "central": "corridor",
        "connections": [
            ("entry_hall", SOUTH),
            ("corridor", NORTH),
            ("dungeon_cell", EAST),
            ("dungeon_cell", WEST),
            ("dungeon_cell", EAST),
            ("storage", NORTH),
            ("stairwell", NORTH),
        ],
    },
    "ruins": {
        "central": "corridor",
        "connections": [
            ("entry_hall", SOUTH),
            ("corridor", NORTH),
            ("dungeon_cell", EAST),
            ("dungeon_cell", WEST),
            ("storage", NORTH),
            ("corridor", EAST),
            ("stairwell", NORTH),
        ],
    },
    "cave": {
        "central": "corridor",
        "connections": [
            ("entry_hall", SOUTH),
            ("corridor", NORTH),
            ("corridor", EAST),
            ("storage", NORTH),
        ],
    },
}


# ================================================================
# FURNITURE PLACEMENT CATEGORIES
# ================================================================

# Furniture that must be placed along walls
WALL_FURNITURE = {BED, CHEST, BOOKSHELF, BARREL, ANVIL, FORGE_FIRE}

# Furniture that goes in room center or near center
CENTER_FURNITURE = {TABLE, FOUNTAIN, ALTAR}

# Furniture placed against inner walls specifically
INNER_WALL_FURNITURE = {FIREPLACE}

# Decorative floor tiles (walkable, placed in open areas)
FLOOR_DECORATION = {CARPET, MOSAIC}

# Structural elements placed at room edges/entrances
STRUCTURAL = {PILLAR, ARCHWAY}

# Special placement: THRONE goes at far end, centered
THRONE_TILE = THRONE


# ================================================================
# STAGE 1: BUILD ROOM GRAPH
# ================================================================

def _build_room_graph(building_kind: str, room_list: List[str],
                      rng: random.Random) -> List[RoomNode]:
    """Build a connectivity graph from the room list and building type rules.

    Returns a list of RoomNode objects. The first node is always the central room.
    """
    rules = CONNECTIVITY_RULES.get(building_kind)
    if rules is None:
        # Fallback: use house rules
        rules = CONNECTIVITY_RULES["house"]

    central_type = rules["central"]
    connection_specs = list(rules["connections"])

    # Create all room nodes
    nodes: List[RoomNode] = []
    remaining_rooms = list(room_list)

    # Find and create central room
    central_node = None
    if central_type in remaining_rooms:
        remaining_rooms.remove(central_type)
        central_node = RoomNode(central_type, 0)
    else:
        # If the central type isn't in the room list, use the first room
        central_type = remaining_rooms.pop(0) if remaining_rooms else "common_room"
        central_node = RoomNode(central_type, 0)

    central_node.is_central = True
    nodes.append(central_node)

    # Match remaining rooms to connection specs
    # First pass: try to match each connection spec to a room in remaining_rooms
    used_specs = []
    for room_type, direction in connection_specs:
        if room_type in remaining_rooms:
            remaining_rooms.remove(room_type)
            idx = len(nodes)
            child = RoomNode(room_type, idx)
            central_node.add_child(child, direction)
            nodes.append(child)
            used_specs.append((child, direction))

    # Second pass: any rooms left over get attached to the nearest sensible parent
    # Bedrooms and living spaces branch off existing bedroom corridors or the central room
    # Service rooms (kitchen, storage) branch off the kitchen wing or central room
    for leftover in remaining_rooms:
        idx = len(nodes)
        child = RoomNode(leftover, idx)

        # Find best parent: prefer attaching to a room of similar function
        parent = _find_best_parent(child, nodes, rng)
        direction = _pick_open_direction(parent, nodes, rng)
        parent.add_child(child, direction)
        nodes.append(child)

    return nodes


def _find_best_parent(child: RoomNode, existing: List[RoomNode],
                      rng: random.Random) -> RoomNode:
    """Find the best parent node for a leftover room."""
    child_type = child.room_type

    # Sleeping rooms attach to other sleeping rooms or central
    sleeping = {"bedroom", "bedroom_poor", "bedroom_fine", "bedroom_luxurious",
                "double_bedroom", "double_bedroom_fine", "double_bedroom_luxurious",
                "children_room", "nursery", "guest_room", "guest_suite",
                "servants_quarters", "dormitory", "officer_quarters",
                "commander_quarters", "stable_loft", "dungeon_cell"}

    service = {"kitchen", "storage", "cellar", "stable"}

    # Try to find a node of similar category
    if child_type in sleeping:
        for node in existing:
            if node.room_type in sleeping and len(node.children) < 2:
                return node
    elif child_type in service:
        for node in existing:
            if node.room_type in service and len(node.children) < 2:
                return node

    # Fallback: attach to the central room or a room with few children
    best = existing[0]
    for node in existing:
        if len(node.children) < len(best.children):
            best = node
    return best


def _pick_open_direction(parent: RoomNode, all_nodes: List[RoomNode],
                         rng: random.Random) -> Tuple[int, int]:
    """Pick a direction from parent that isn't already taken by a child."""
    used_dirs = set()
    for ch in parent.children:
        if ch.direction_from_parent is not None:
            used_dirs.add(ch.direction_from_parent)
    if parent.direction_from_parent is not None:
        # Also avoid the direction back to our own parent
        used_dirs.add(OPPOSITE[parent.direction_from_parent])

    available = [d for d in CARDINALS if d not in used_dirs]
    if available:
        return rng.choice(available)
    # All directions taken -- just pick any
    return rng.choice(CARDINALS)


# ================================================================
# STAGE 2: ROOM PLACEMENT ON GRID
# ================================================================

def _determine_room_size(room_type: str, map_w: int, map_h: int,
                         is_central: bool, rng: random.Random) -> Tuple[int, int]:
    """Determine width and height for a room based on its template."""
    template = ROOM_TEMPLATES.get(room_type, ROOM_TEMPLATES.get("common_room"))
    if template is None:
        template = {"min_size": (3, 3), "max_size": (6, 6)}

    min_w, min_h = template["min_size"]
    max_w, max_h = template["max_size"]

    # Central rooms get a size boost
    if is_central:
        min_w = min(min_w + 2, max_w)
        min_h = min(min_h + 2, max_h)

    # Clamp to map size (leave room for walls)
    max_w = min(max_w, map_w // 3)
    max_h = min(max_h, map_h // 3)
    min_w = min(min_w, max_w)
    min_h = min(min_h, max_h)

    w = rng.randint(min_w, max_w)
    h = rng.randint(min_h, max_h)
    return w, h


def _place_rooms_on_grid(nodes: List[RoomNode], map_w: int, map_h: int,
                         rng: random.Random) -> bool:
    """Place all rooms on the grid. Returns True if successful.

    Strategy:
    1. Place central room in the center of the map.
    2. BFS outward, placing each child adjacent to its parent.
    3. If a room doesn't fit, try other directions.
    """
    if not nodes:
        return False

    central = nodes[0]

    # Size the central room
    cw, ch = _determine_room_size(central.room_type, map_w, map_h, True, rng)
    central.grid_w = cw
    central.grid_h = ch
    # Center it on the map, biased slightly south to leave room for bedrooms to the north
    central.grid_x = (map_w - cw) // 2
    central.grid_y = (map_h - ch) // 2 + 1

    placed: Set[int] = {0}
    occupied_rects: List[Tuple[int, int, int, int]] = [
        (central.grid_x, central.grid_y, cw, ch)
    ]

    # BFS placement
    queue = [central]
    while queue:
        parent = queue.pop(0)
        for child in parent.children:
            if child.index in placed:
                continue

            rw, rh = _determine_room_size(child.room_type, map_w, map_h, False, rng)
            child.grid_w = rw
            child.grid_h = rh

            # Try preferred direction first, then others
            preferred = child.direction_from_parent
            directions = [preferred] if preferred else []
            for d in CARDINALS:
                if d not in directions:
                    directions.append(d)

            success = False
            for direction in directions:
                dx, dy = direction

                # Calculate position adjacent to parent
                if dx > 0:  # EAST
                    rx = parent.grid_x + parent.grid_w
                    ry = parent.grid_y + (parent.grid_h - rh) // 2
                elif dx < 0:  # WEST
                    rx = parent.grid_x - rw
                    ry = parent.grid_y + (parent.grid_h - rh) // 2
                elif dy < 0:  # NORTH
                    rx = parent.grid_x + (parent.grid_w - rw) // 2
                    ry = parent.grid_y - rh
                else:  # SOUTH
                    rx = parent.grid_x + (parent.grid_w - rw) // 2
                    ry = parent.grid_y + parent.grid_h

                # Try small random offsets to find a fit
                for offset_attempt in range(5):
                    ox = 0
                    oy = 0
                    if offset_attempt > 0:
                        # Shift perpendicular to placement direction
                        if dx != 0:
                            oy = rng.randint(-3, 3)
                        else:
                            ox = rng.randint(-3, 3)

                    test_x = rx + ox
                    test_y = ry + oy

                    # Clamp to map bounds (leave 1 tile for outer wall)
                    test_x = max(1, min(test_x, map_w - rw - 1))
                    test_y = max(1, min(test_y, map_h - rh - 1))

                    if not _rect_overlaps_any(test_x, test_y, rw, rh, occupied_rects):
                        child.grid_x = test_x
                        child.grid_y = test_y
                        child.direction_from_parent = direction
                        occupied_rects.append((test_x, test_y, rw, rh))
                        placed.add(child.index)
                        queue.append(child)
                        success = True
                        break

                if success:
                    break

            if not success:
                # Last resort: scan for any open spot near parent
                found = _find_any_open_spot(parent, child, rw, rh,
                                            map_w, map_h, occupied_rects, rng)
                if found:
                    child.grid_x, child.grid_y = found
                    occupied_rects.append((child.grid_x, child.grid_y, rw, rh))
                    placed.add(child.index)
                    queue.append(child)
                else:
                    # Could not place this room at all; shrink and try once more
                    rw2 = max(2, rw - 1)
                    rh2 = max(2, rh - 1)
                    child.grid_w = rw2
                    child.grid_h = rh2
                    found2 = _find_any_open_spot(parent, child, rw2, rh2,
                                                 map_w, map_h, occupied_rects, rng)
                    if found2:
                        child.grid_x, child.grid_y = found2
                        occupied_rects.append((child.grid_x, child.grid_y, rw2, rh2))
                        placed.add(child.index)
                        queue.append(child)
                    # Otherwise skip this room entirely

    return len(placed) >= max(1, len(nodes) // 2)


def _rect_overlaps_any(x: int, y: int, w: int, h: int,
                       rects: List[Tuple[int, int, int, int]]) -> bool:
    """Check if a rectangle overlaps any existing rectangle."""
    for rx, ry, rw, rh in rects:
        if x < rx + rw and x + w > rx and y < ry + rh and y + h > ry:
            return True
    return False


def _find_any_open_spot(parent: RoomNode, child: RoomNode,
                        rw: int, rh: int, map_w: int, map_h: int,
                        occupied: List[Tuple[int, int, int, int]],
                        rng: random.Random) -> Optional[Tuple[int, int]]:
    """Scan outward from parent for any open spot that fits the room."""
    cx = parent.grid_x + parent.grid_w // 2
    cy = parent.grid_y + parent.grid_h // 2

    # Spiral outward from parent center
    for radius in range(1, max(map_w, map_h)):
        candidates = []
        for dx in range(-radius, radius + 1):
            for dy in [-radius, radius]:
                px, py = cx + dx, cy + dy
                if 1 <= px <= map_w - rw - 1 and 1 <= py <= map_h - rh - 1:
                    candidates.append((px, py))
        for dy in range(-radius + 1, radius):
            for dx in [-radius, radius]:
                px, py = cx + dx, cy + dy
                if 1 <= px <= map_w - rw - 1 and 1 <= py <= map_h - rh - 1:
                    candidates.append((px, py))

        rng.shuffle(candidates)
        for px, py in candidates:
            if not _rect_overlaps_any(px, py, rw, rh, occupied):
                return (px, py)

    return None


# ================================================================
# STAGE 3: WALLS, DOORS, WINDOWS
# ================================================================

def _carve_rooms_and_walls(interior: InteriorMap, nodes: List[RoomNode]):
    """Carve floor tiles for each room and ensure wall boundaries."""
    # Start with everything as WALL (already the default from InteriorMap.__init__)

    # Carve each room's interior as FLOOR
    for node in nodes:
        if node.grid_w <= 0 or node.grid_h <= 0:
            continue
        for y in range(node.grid_y, node.grid_y + node.grid_h):
            for x in range(node.grid_x, node.grid_x + node.grid_w):
                if 0 <= x < interior.width and 0 <= y < interior.height:
                    interior.tiles[y][x] = FLOOR


def _connect_adjacent_rooms(interior: InteriorMap, nodes: List[RoomNode],
                            rng: random.Random):
    """Place doors between adjacent rooms and carve corridors where needed."""
    placed_nodes = [n for n in nodes if n.grid_w > 0 and n.grid_h > 0]

    # For each parent-child pair, determine if they share a wall
    # If they share a wall (or are separated by exactly 1 wall tile), place a door
    # If they're separated by more, carve a short corridor
    connected_pairs: Set[Tuple[int, int]] = set()

    for node in placed_nodes:
        for child in node.children:
            if child.grid_w <= 0 or child.grid_h <= 0:
                continue
            pair_key = (min(node.index, child.index), max(node.index, child.index))
            if pair_key in connected_pairs:
                continue
            connected_pairs.add(pair_key)

            _connect_two_rooms(interior, node, child, rng)


def _connect_two_rooms(interior: InteriorMap, a: RoomNode, b: RoomNode,
                       rng: random.Random):
    """Connect two rooms with a door (if adjacent) or a short corridor + door."""
    # Find the shared wall region or closest edges
    # Room a bounds
    ax1, ay1 = a.grid_x, a.grid_y
    ax2, ay2 = a.grid_x + a.grid_w, a.grid_y + a.grid_h
    # Room b bounds
    bx1, by1 = b.grid_x, b.grid_y
    bx2, by2 = b.grid_x + b.grid_w, b.grid_y + b.grid_h

    # Check if rooms share an edge (adjacent with exactly 0 gap = shared wall)
    # or have a 1-tile gap (the wall between them)

    door_placed = False

    # Check if b is directly east of a (ax2 == bx1 or ax2 + 1 == bx1)
    if _try_door_horizontal(interior, a, b, rng):
        door_placed = True
    elif _try_door_horizontal(interior, b, a, rng):
        door_placed = True
    elif _try_door_vertical(interior, a, b, rng):
        door_placed = True
    elif _try_door_vertical(interior, b, a, rng):
        door_placed = True

    if not door_placed:
        # Rooms are not adjacent; carve a corridor between them
        _carve_corridor_between(interior, a, b, rng)


def _try_door_horizontal(interior: InteriorMap, left: RoomNode, right: RoomNode,
                         rng: random.Random) -> bool:
    """Try placing a door on a shared vertical wall between left and right rooms.
    Returns True if successful."""
    lx2 = left.grid_x + left.grid_w
    rx1 = right.grid_x

    gap = rx1 - lx2
    if gap < 0 or gap > 1:
        return False

    # Find vertical overlap
    y_start = max(left.grid_y, right.grid_y)
    y_end = min(left.grid_y + left.grid_h, right.grid_y + right.grid_h)

    if y_end - y_start < 1:
        return False

    # Place door at center of overlap, avoiding corners
    door_y_min = y_start + (1 if y_end - y_start > 2 else 0)
    door_y_max = y_end - 1 - (1 if y_end - y_start > 2 else 0)
    if door_y_min > door_y_max:
        door_y_min = door_y_max = (y_start + y_end) // 2

    door_y = rng.randint(door_y_min, door_y_max)

    # Scan the boundary for a WALL tile to convert to a door
    for door_x_candidate in [lx2, lx2 - 1, lx2 + 1]:
        if not (0 <= door_x_candidate < interior.width and 0 <= door_y < interior.height):
            continue
        if interior.tiles[door_y][door_x_candidate] == WALL:
            interior.tiles[door_y][door_x_candidate] = DOOR
            return True

    # No wall found — rooms are directly adjacent with no wall between.
    # Place a door marker on the boundary anyway if it's floor
    # (the rooms connect directly — door is cosmetic)
    door_x = lx2 if gap == 1 else lx2 - 1
    if 0 <= door_x < interior.width and 0 <= door_y < interior.height:
        if interior.tiles[door_y][door_x] == FLOOR:
            # Don't place a floating door — rooms already connect
            return True  # connected, no door tile needed

    return False


def _try_door_vertical(interior: InteriorMap, top: RoomNode, bottom: RoomNode,
                       rng: random.Random) -> bool:
    """Try placing a door on a shared horizontal wall between top and bottom rooms.
    Returns True if successful."""
    ty2 = top.grid_y + top.grid_h
    by1 = bottom.grid_y

    gap = by1 - ty2
    if gap < 0 or gap > 1:
        return False

    # Find horizontal overlap
    x_start = max(top.grid_x, bottom.grid_x)
    x_end = min(top.grid_x + top.grid_w, bottom.grid_x + bottom.grid_w)

    if x_end - x_start < 1:
        return False

    door_x_min = x_start + (1 if x_end - x_start > 2 else 0)
    door_x_max = x_end - 1 - (1 if x_end - x_start > 2 else 0)
    if door_x_min > door_x_max:
        door_x_min = door_x_max = (x_start + x_end) // 2

    door_x = rng.randint(door_x_min, door_x_max)

    # Scan the boundary for a WALL tile to convert to a door
    for door_y_candidate in [ty2, ty2 - 1, ty2 + 1]:
        if not (0 <= door_x < interior.width and 0 <= door_y_candidate < interior.height):
            continue
        if interior.tiles[door_y_candidate][door_x] == WALL:
            interior.tiles[door_y_candidate][door_x] = DOOR
            return True

    # No wall found — rooms connect directly
    door_y = ty2 if gap == 1 else ty2 - 1
    if 0 <= door_x < interior.width and 0 <= door_y < interior.height:
        if interior.tiles[door_y][door_x] == FLOOR:
            return True  # connected, no door tile needed

    return False


def _carve_corridor_between(interior: InteriorMap, a: RoomNode, b: RoomNode,
                            rng: random.Random):
    """Carve an L-shaped corridor between two non-adjacent rooms and place doors."""
    # Get center of each room
    ax = a.grid_x + a.grid_w // 2
    ay = a.grid_y + a.grid_h // 2
    bx = b.grid_x + b.grid_w // 2
    by = b.grid_y + b.grid_h // 2

    # Find the exit point from room a (edge closest to b)
    exit_a = _room_edge_towards(a, bx, by)
    # Find the entry point into room b (edge closest to a)
    entry_b = _room_edge_towards(b, ax, ay)

    # Carve L-shaped corridor
    x, y = exit_a
    tx, ty = entry_b

    # Make sure exit point itself is a door
    if 0 <= x < interior.width and 0 <= y < interior.height:
        if interior.tiles[y][x] == WALL:
            interior.tiles[y][x] = DOOR

    if rng.random() < 0.5:
        # Horizontal first
        _carve_line(interior, x, y, tx, y)
        _carve_line(interior, tx, y, tx, ty)
    else:
        # Vertical first
        _carve_line(interior, x, y, x, ty)
        _carve_line(interior, x, ty, tx, ty)

    # Make sure entry point is a door
    if 0 <= tx < interior.width and 0 <= ty < interior.height:
        if interior.tiles[ty][tx] == WALL:
            interior.tiles[ty][tx] = DOOR


def _room_edge_towards(node: RoomNode, target_x: int, target_y: int) -> Tuple[int, int]:
    """Find the point on node's edge closest to (target_x, target_y)."""
    cx = node.grid_x + node.grid_w // 2
    cy = node.grid_y + node.grid_h // 2

    dx = target_x - cx
    dy = target_y - cy

    # Choose the edge that faces the target
    if abs(dx) > abs(dy):
        # Exit through east or west edge
        if dx > 0:
            return (node.grid_x + node.grid_w, cy)
        else:
            return (node.grid_x - 1, cy)
    else:
        # Exit through north or south edge
        if dy > 0:
            return (cx, node.grid_y + node.grid_h)
        else:
            return (cx, node.grid_y - 1)


def _carve_line(interior: InteriorMap, x1: int, y1: int, x2: int, y2: int):
    """Carve a straight line of FLOOR tiles (only changes WALL tiles)."""
    x, y = x1, y1
    while True:
        if 0 <= x < interior.width and 0 <= y < interior.height:
            if interior.tiles[y][x] == WALL:
                interior.tiles[y][x] = FLOOR
        if x == x2 and y == y2:
            break
        if x != x2:
            x += 1 if x2 > x else -1
        elif y != y2:
            y += 1 if y2 > y else -1
        else:
            break


def _place_windows(interior: InteriorMap, rng: random.Random):
    """Place windows on outer walls at regular intervals.

    Windows go on outer walls only, every 3-4 tiles, not near corners.
    """
    w, h = interior.width, interior.height

    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if interior.tiles[y][x] != WALL:
                continue

            # Check if this wall tile is on the building perimeter
            # (has at least one neighbor that is out of bounds or is the outermost wall)
            on_perimeter = False
            has_interior_floor = False

            for dx, dy in CARDINALS:
                nx, ny = x + dx, y + dy
                if nx <= 0 or nx >= w - 1 or ny <= 0 or ny >= h - 1:
                    on_perimeter = True
                elif interior.tiles[ny][nx] == FLOOR or interior.tiles[ny][nx] == DOOR:
                    has_interior_floor = True

            if not on_perimeter or not has_interior_floor:
                continue

            # Don't place windows near corners (check for adjacent walls in both
            # perpendicular directions)
            corner = False
            if x <= 2 or x >= w - 3 or y <= 2 or y >= h - 3:
                corner = True

            if corner:
                continue

            # Place windows every 3-4 tiles (use coordinate-based spacing)
            if (x + y) % rng.randint(3, 4) == 0:
                interior.tiles[y][x] = WINDOW


# ================================================================
# STAGE 4: FURNITURE PLACEMENT (REALISTIC)
# ================================================================

def _place_furniture(interior: InteriorMap, nodes: List[RoomNode],
                     rng: random.Random):
    """Place furniture in each room following realistic medieval rules."""
    for node in nodes:
        if node.grid_w <= 0 or node.grid_h <= 0:
            continue

        template = ROOM_TEMPLATES.get(node.room_type)
        if template is None:
            template = ROOM_TEMPLATES.get("common_room", {"furniture": []})

        furniture_list = template.get("furniture", [])
        rx, ry = node.grid_x, node.grid_y
        rw, rh = node.grid_w, node.grid_h

        # Collect wall positions and center positions for this room
        wall_positions = _get_wall_adjacent_positions(interior, rx, ry, rw, rh)
        inner_wall_positions = _get_inner_wall_positions(interior, rx, ry, rw, rh)
        center_positions = _get_center_positions(rx, ry, rw, rh)
        door_positions = _get_door_positions(interior, rx, ry, rw, rh)

        # Keep track of what we've placed to avoid blocking paths
        placed_positions: Set[Tuple[int, int]] = set()

        # Special handling for throne room
        if node.room_type == "throne_room":
            _place_throne_room_furniture(interior, node, furniture_list,
                                         wall_positions, center_positions,
                                         door_positions, placed_positions, rng)
            continue

        for furn_tile, fmin, fmax in furniture_list:
            count = rng.randint(fmin, fmax)

            for _ in range(count):
                pos = _find_furniture_position(
                    interior, furn_tile, rx, ry, rw, rh,
                    wall_positions, inner_wall_positions,
                    center_positions, door_positions,
                    placed_positions, rng
                )
                if pos is not None:
                    fx, fy = pos
                    interior.tiles[fy][fx] = furn_tile
                    placed_positions.add(pos)


def _get_wall_adjacent_positions(interior: InteriorMap,
                                  rx: int, ry: int, rw: int, rh: int
                                  ) -> List[Tuple[int, int]]:
    """Get floor positions inside the room that are adjacent to a wall."""
    positions = []
    for y in range(ry, ry + rh):
        for x in range(rx, rx + rw):
            if not (0 <= x < interior.width and 0 <= y < interior.height):
                continue
            if interior.tiles[y][x] != FLOOR:
                continue
            # Check if any neighbor is a wall
            for dx, dy in CARDINALS:
                nx, ny = x + dx, y + dy
                if 0 <= nx < interior.width and 0 <= ny < interior.height:
                    if interior.tiles[ny][nx] == WALL:
                        positions.append((x, y))
                        break
                else:
                    # Out of bounds counts as wall
                    positions.append((x, y))
                    break
    return positions


def _get_inner_wall_positions(interior: InteriorMap,
                               rx: int, ry: int, rw: int, rh: int
                               ) -> List[Tuple[int, int]]:
    """Get floor positions adjacent to inner walls (not outer perimeter).
    Inner walls are walls that have rooms on both sides."""
    positions = []
    w, h = interior.width, interior.height
    for y in range(ry, ry + rh):
        for x in range(rx, rx + rw):
            if not (0 <= x < w and 0 <= y < h):
                continue
            if interior.tiles[y][x] != FLOOR:
                continue
            for dx, dy in CARDINALS:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w and 0 <= ny < h):
                    continue
                if interior.tiles[ny][nx] != WALL:
                    continue
                # Check if this wall is inner (not on the map perimeter)
                if nx > 1 and nx < w - 2 and ny > 1 and ny < h - 2:
                    positions.append((x, y))
                    break
    return positions


def _get_center_positions(rx: int, ry: int, rw: int, rh: int
                          ) -> List[Tuple[int, int]]:
    """Get positions in the center area of the room."""
    positions = []
    # Center area: inner 60% of the room
    margin_x = max(1, rw // 4)
    margin_y = max(1, rh // 4)
    for y in range(ry + margin_y, ry + rh - margin_y):
        for x in range(rx + margin_x, rx + rw - margin_x):
            positions.append((x, y))
    return positions


def _get_door_positions(interior: InteriorMap,
                        rx: int, ry: int, rw: int, rh: int
                        ) -> Set[Tuple[int, int]]:
    """Get all door tile positions in or adjacent to this room."""
    doors = set()
    # Check a 1-tile border around the room
    for y in range(ry - 1, ry + rh + 1):
        for x in range(rx - 1, rx + rw + 1):
            if 0 <= x < interior.width and 0 <= y < interior.height:
                if interior.tiles[y][x] == DOOR:
                    doors.add((x, y))
                    # Also mark tiles adjacent to doors as "near door"
                    for dx, dy in CARDINALS:
                        doors.add((x + dx, y + dy))
    return doors


def _find_furniture_position(interior: InteriorMap, furn_tile: int,
                              rx: int, ry: int, rw: int, rh: int,
                              wall_pos: List[Tuple[int, int]],
                              inner_wall_pos: List[Tuple[int, int]],
                              center_pos: List[Tuple[int, int]],
                              door_pos: Set[Tuple[int, int]],
                              placed: Set[Tuple[int, int]],
                              rng: random.Random) -> Optional[Tuple[int, int]]:
    """Find a valid position for a furniture tile following placement rules."""

    def _is_valid(x: int, y: int) -> bool:
        if not (0 <= x < interior.width and 0 <= y < interior.height):
            return False
        if interior.tiles[y][x] != FLOOR:
            return False
        if (x, y) in placed:
            return False
        if (x, y) in door_pos:
            return False
        # Must be within the room bounds
        if not (rx <= x < rx + rw and ry <= y < ry + rh):
            return False
        return True

    # Choose candidate list based on furniture type
    if furn_tile in WALL_FURNITURE:
        candidates = [p for p in wall_pos if _is_valid(p[0], p[1])]
    elif furn_tile in INNER_WALL_FURNITURE:
        # Fireplace: prefer inner walls, fall back to any wall
        candidates = [p for p in inner_wall_pos if _is_valid(p[0], p[1])]
        if not candidates:
            candidates = [p for p in wall_pos if _is_valid(p[0], p[1])]
    elif furn_tile in CENTER_FURNITURE:
        candidates = [p for p in center_pos if _is_valid(p[0], p[1])]
        if not candidates:
            # Fall back to any open floor in the room
            candidates = []
            for y in range(ry, ry + rh):
                for x in range(rx, rx + rw):
                    if _is_valid(x, y):
                        candidates.append((x, y))
    elif furn_tile in FLOOR_DECORATION:
        # Carpet/mosaic: prefer center area
        candidates = [p for p in center_pos if _is_valid(p[0], p[1])]
        if not candidates:
            candidates = []
            for y in range(ry, ry + rh):
                for x in range(rx, rx + rw):
                    if _is_valid(x, y):
                        candidates.append((x, y))
    elif furn_tile in STRUCTURAL:
        # Pillars: place at room edges near doors / at entrances
        candidates = []
        for y in range(ry, ry + rh):
            for x in range(rx, rx + rw):
                if _is_valid(x, y):
                    # Prefer positions 1 tile in from corners
                    if ((x == rx + 1 or x == rx + rw - 2) and
                            (y == ry + 1 or y == ry + rh - 2)):
                        candidates.append((x, y))
        if not candidates:
            candidates = [p for p in wall_pos if _is_valid(p[0], p[1])]
    else:
        # Default: wall placement
        candidates = [p for p in wall_pos if _is_valid(p[0], p[1])]

    if not candidates:
        return None

    return rng.choice(candidates)


def _place_throne_room_furniture(interior: InteriorMap, node: RoomNode,
                                  furniture_list: List[Tuple[int, int, int]],
                                  wall_positions: List[Tuple[int, int]],
                                  center_positions: List[Tuple[int, int]],
                                  door_positions: Set[Tuple[int, int]],
                                  placed: Set[Tuple[int, int]],
                                  rng: random.Random):
    """Special placement for throne rooms: throne at far end, carpet runner, pillars."""
    rx, ry = node.grid_x, node.grid_y
    rw, rh = node.grid_w, node.grid_h

    # Place throne at the far (north) end, centered
    throne_x = rx + rw // 2
    throne_y = ry + 1  # One tile from the north wall
    if (0 <= throne_x < interior.width and 0 <= throne_y < interior.height and
            interior.tiles[throne_y][throne_x] == FLOOR):
        interior.tiles[throne_y][throne_x] = THRONE
        placed.add((throne_x, throne_y))

    # Place carpet runner from entrance to throne
    carpet_x = rx + rw // 2
    for cy in range(ry + 2, ry + rh - 1):
        if (0 <= carpet_x < interior.width and 0 <= cy < interior.height and
                interior.tiles[cy][carpet_x] == FLOOR and
                (carpet_x, cy) not in placed):
            interior.tiles[cy][carpet_x] = CARPET
            placed.add((carpet_x, cy))

    # Carpet in front of throne
    for dx in [-1, 0, 1]:
        cx = throne_x + dx
        cy = throne_y + 1
        if (0 <= cx < interior.width and 0 <= cy < interior.height and
                interior.tiles[cy][cx] == FLOOR and (cx, cy) not in placed):
            interior.tiles[cy][cx] = CARPET
            placed.add((cx, cy))

    # Place pillars along the sides
    for furn_tile, fmin, fmax in furniture_list:
        if furn_tile == THRONE:
            continue  # Already placed
        if furn_tile == CARPET:
            continue  # Already placed

        count = rng.randint(fmin, fmax)
        if furn_tile == PILLAR:
            # Pillars in two rows along the hall
            pillar_spacing = max(2, rh // (count + 1))
            for i in range(count):
                py = ry + 2 + i * pillar_spacing
                for px in [rx + 1, rx + rw - 2]:
                    if (0 <= px < interior.width and 0 <= py < interior.height and
                            interior.tiles[py][px] == FLOOR and
                            (px, py) not in placed and
                            (px, py) not in door_positions):
                        interior.tiles[py][px] = PILLAR
                        placed.add((px, py))
        else:
            for _ in range(count):
                valid = [p for p in wall_positions
                         if p not in placed and p not in door_positions and
                         0 <= p[0] < interior.width and 0 <= p[1] < interior.height and
                         interior.tiles[p[1]][p[0]] == FLOOR]
                if valid:
                    pos = rng.choice(valid)
                    interior.tiles[pos[1]][pos[0]] = furn_tile
                    placed.add(pos)


# ================================================================
# STAGE 5: DECORATION PASS
# ================================================================

def _decoration_pass(interior: InteriorMap, nodes: List[RoomNode],
                     rng: random.Random):
    """Add atmospheric details: carpet in noble rooms, pillars, torches, clutter."""

    # Identify room types for targeted decoration
    noble_rooms = {"throne_room", "bedroom_luxurious", "double_bedroom_luxurious",
                   "bedroom_fine", "double_bedroom_fine", "commander_quarters",
                   "guest_suite", "chapel", "library"}
    storage_rooms = {"storage", "cellar"}
    corridor_rooms = {"corridor", "entry_hall"}
    large_rooms = {"throne_room", "tavern_hall", "dining_hall", "chapel",
                   "dormitory", "stable"}

    for node in nodes:
        if node.grid_w <= 0 or node.grid_h <= 0:
            continue
        rx, ry = node.grid_x, node.grid_y
        rw, rh = node.grid_w, node.grid_h

        # Noble rooms: add extra carpet near fireplace
        if node.room_type in noble_rooms:
            _add_carpet_near_fireplace(interior, rx, ry, rw, rh, rng)

        # Large rooms: add pillars at entrance
        if node.room_type in large_rooms and rw >= 5 and rh >= 5:
            _add_entrance_pillars(interior, node, rng)

        # Corridor rooms: add torch sconces (use FIREPLACE tile) along walls
        if node.room_type in corridor_rooms:
            _add_corridor_torches(interior, rx, ry, rw, rh, rng)

        # Storage rooms: add extra clutter
        if node.room_type in storage_rooms:
            _add_storage_clutter(interior, rx, ry, rw, rh, rng)


def _add_carpet_near_fireplace(interior: InteriorMap,
                                rx: int, ry: int, rw: int, rh: int,
                                rng: random.Random):
    """Place carpet tiles in front of any fireplace in the room."""
    for y in range(ry, ry + rh):
        for x in range(rx, rx + rw):
            if not (0 <= x < interior.width and 0 <= y < interior.height):
                continue
            if interior.tiles[y][x] == FIREPLACE:
                # Place carpet in front of fireplace (south side, since fireplace
                # is typically against a wall)
                for dx, dy in CARDINALS:
                    nx, ny = x + dx, y + dy
                    if (0 <= nx < interior.width and 0 <= ny < interior.height and
                            interior.tiles[ny][nx] == FLOOR):
                        interior.tiles[ny][nx] = CARPET
                        # Also one more tile out
                        nnx, nny = nx + dx, ny + dy
                        if (0 <= nnx < interior.width and 0 <= nny < interior.height and
                                interior.tiles[nny][nnx] == FLOOR):
                            interior.tiles[nny][nnx] = CARPET
                        break


def _add_entrance_pillars(interior: InteriorMap, node: RoomNode,
                          rng: random.Random):
    """Add pillar tiles at room entrances for large rooms."""
    rx, ry = node.grid_x, node.grid_y
    rw, rh = node.grid_w, node.grid_h

    # Find doors leading into this room
    for y in range(ry - 1, ry + rh + 1):
        for x in range(rx - 1, rx + rw + 1):
            if not (0 <= x < interior.width and 0 <= y < interior.height):
                continue
            if interior.tiles[y][x] != DOOR:
                continue

            # Place pillars flanking the door (inside the room)
            for dx, dy in CARDINALS:
                # The tile one step into the room from the door
                step_x, step_y = x + dx, y + dy
                if not (rx <= step_x < rx + rw and ry <= step_y < ry + rh):
                    continue
                # Place pillars perpendicular to the door direction
                if dx != 0:  # Door faces east/west, pillars go north/south
                    for pdy in [-1, 1]:
                        px, py = step_x, step_y + pdy
                        if (0 <= px < interior.width and 0 <= py < interior.height and
                                interior.tiles[py][px] == FLOOR):
                            interior.tiles[py][px] = PILLAR
                else:  # Door faces north/south, pillars go east/west
                    for pdx in [-1, 1]:
                        px, py = step_x + pdx, step_y
                        if (0 <= px < interior.width and 0 <= py < interior.height and
                                interior.tiles[py][px] == FLOOR):
                            interior.tiles[py][px] = PILLAR
                break  # Only process the first inward direction
            break  # Only process the first door found


def _add_corridor_torches(interior: InteriorMap,
                          rx: int, ry: int, rw: int, rh: int,
                          rng: random.Random):
    """Place torch sconces (FIREPLACE tile) every 5 tiles along corridor walls."""
    torch_interval = 5
    count = 0
    for y in range(ry, ry + rh):
        for x in range(rx, rx + rw):
            if not (0 <= x < interior.width and 0 <= y < interior.height):
                continue
            if interior.tiles[y][x] != FLOOR:
                continue
            # Check if adjacent to a wall
            adjacent_wall = False
            for dx, dy in CARDINALS:
                nx, ny = x + dx, y + dy
                if (0 <= nx < interior.width and 0 <= ny < interior.height and
                        interior.tiles[ny][nx] == WALL):
                    adjacent_wall = True
                    break
            if adjacent_wall:
                count += 1
                if count % torch_interval == 0:
                    interior.tiles[y][x] = FIREPLACE


def _add_storage_clutter(interior: InteriorMap,
                         rx: int, ry: int, rw: int, rh: int,
                         rng: random.Random):
    """Add extra barrels and chests as clutter in storage rooms."""
    clutter_tiles = [BARREL, BARREL, CHEST]
    num_extra = rng.randint(1, 3)

    for _ in range(num_extra):
        # Find a wall-adjacent floor tile
        for _attempt in range(20):
            x = rng.randint(rx, rx + rw - 1)
            y = rng.randint(ry, ry + rh - 1)
            if not (0 <= x < interior.width and 0 <= y < interior.height):
                continue
            if interior.tiles[y][x] != FLOOR:
                continue
            # Must be near a wall
            near_wall = False
            for dx, dy in CARDINALS:
                nx, ny = x + dx, y + dy
                if (0 <= nx < interior.width and 0 <= ny < interior.height and
                        interior.tiles[ny][nx] == WALL):
                    near_wall = True
                    break
            if near_wall:
                # Don't block doors
                near_door = False
                for dx, dy in CARDINALS:
                    nx, ny = x + dx, y + dy
                    if (0 <= nx < interior.width and 0 <= ny < interior.height and
                            interior.tiles[ny][nx] == DOOR):
                        near_door = True
                        break
                if not near_door:
                    interior.tiles[y][x] = rng.choice(clutter_tiles)
                    break


# ================================================================
# ENTRY, STAIRS, AND FINAL SETUP
# ================================================================

def _setup_entry(interior: InteriorMap, nodes: List[RoomNode]):
    """Place the building entry point at the south side of the entry hall
    (or central room if no entry hall)."""
    w, h = interior.width, interior.height

    # Find entry hall
    entry_node = None
    for node in nodes:
        if node.room_type == "entry_hall" and node.grid_w > 0:
            entry_node = node
            break

    if entry_node is None:
        # Use the southernmost room
        entry_node = max((n for n in nodes if n.grid_w > 0),
                         key=lambda n: n.grid_y + n.grid_h,
                         default=None)

    if entry_node is None:
        # Absolute fallback
        interior.entry_x = w // 2
        interior.entry_y = h - 2
        interior.tiles[h - 1][w // 2] = DOOR
        return

    # Place entry at the south edge of the entry room
    ex = entry_node.grid_x + entry_node.grid_w // 2
    ey = entry_node.grid_y + entry_node.grid_h  # Just below the room

    # Clamp to map
    ex = max(1, min(ex, w - 2))
    ey = max(1, min(ey, h - 2))

    interior.entry_x = ex
    interior.entry_y = ey

    # Ensure the entry area is walkable
    if 0 <= ex < w and 0 <= ey < h:
        interior.tiles[ey][ex] = FLOOR
    # Place the main entrance door one tile south of entry
    door_y = min(ey + 1, h - 1)
    if 0 <= ex < w and 0 <= door_y < h:
        interior.tiles[door_y][ex] = DOOR
    # Make sure path from entry to entry room is clear
    for dy in range(-1, 1):
        ty = ey + dy
        if 0 <= ex < w and 0 <= ty < h:
            if interior.tiles[ty][ex] == WALL:
                interior.tiles[ty][ex] = FLOOR


def _place_stairs(interior: InteriorMap, nodes: List[RoomNode],
                  building_kind: str, floor_num: int):
    """Place stairwell tiles for multi-floor buildings."""
    w, h = interior.width, interior.height

    # Find stairwell room
    stairwell_node = None
    for node in nodes:
        if node.room_type == "stairwell" and node.grid_w > 0:
            stairwell_node = node
            break

    needs_stairs = building_kind in ("castle", "mansion", "manor", "tavern", "inn",
                                      "temple", "monastery", "dungeon", "ruins",
                                      "shop", "blacksmith", "barracks",
                                      "guard_tower", "watchtower", "guildhall")

    if stairwell_node is None and not needs_stairs:
        return
    if stairwell_node is None and needs_stairs:
        # Use the last placed room as stairwell fallback
        for node in reversed(nodes):
            if node.grid_w > 0 and node.grid_h > 0:
                stairwell_node = node
                break
    if stairwell_node is None:
        return

    sx = stairwell_node.grid_x + stairwell_node.grid_w // 2
    sy = stairwell_node.grid_y + stairwell_node.grid_h // 2

    if not (0 <= sx < w and 0 <= sy < h):
        return

    # Place STAIRS_UP
    if interior.tiles[sy][sx] in (FLOOR, CARPET):
        interior.tiles[sy][sx] = STAIRS_UP
        interior.exits.append({
            "x": sx, "y": sy,
            "target_floor": floor_num + 1,
            "target_x": sx, "target_y": sy,
        })

    # Place STAIRS_DOWN adjacent (for basements or upper floors)
    if floor_num > 0 or building_kind in ("dungeon", "castle", "ruins"):
        for dx, dy in CARDINALS:
            nx, ny = sx + dx, sy + dy
            if (0 <= nx < w and 0 <= ny < h and
                    interior.tiles[ny][nx] in (FLOOR, CARPET)):
                interior.tiles[ny][nx] = STAIRS_DOWN
                interior.exits.append({
                    "x": nx, "y": ny,
                    "target_floor": floor_num - 1,
                    "target_x": nx, "target_y": ny,
                })
                break


def _ensure_connectivity(interior: InteriorMap):
    """Post-processing pass: ensure all FLOOR/DOOR areas are reachable from entry.
    If isolated pockets exist, carve a corridor to connect them."""
    w, h = interior.width, interior.height
    walkable = {FLOOR, DOOR, CARPET, MOSAIC, ARCHWAY, STAIRS_UP, STAIRS_DOWN,
                TABLE, BED, CHEST, FIREPLACE, THRONE, BOOKSHELF, BARREL,
                ANVIL, FORGE_FIRE, FOUNTAIN, PILLAR, ALTAR}

    # BFS from entry
    start = (interior.entry_x, interior.entry_y)
    visited: Set[Tuple[int, int]] = set()
    queue = [start]
    visited.add(start)

    while queue:
        cx, cy = queue.pop(0)
        for dx, dy in CARDINALS:
            nx, ny = cx + dx, cy + dy
            if (0 <= nx < w and 0 <= ny < h and
                    (nx, ny) not in visited and
                    interior.tiles[ny][nx] in walkable):
                visited.add((nx, ny))
                queue.append((nx, ny))

    # Find any floor tiles not reached
    unreached = []
    for y in range(h):
        for x in range(w):
            if interior.tiles[y][x] in (FLOOR, DOOR) and (x, y) not in visited:
                unreached.append((x, y))

    if not unreached:
        return

    # Connect the closest unreached tile to the closest reached tile
    # by carving through walls
    while unreached:
        # Find the unreached tile closest to any visited tile
        best_dist = float('inf')
        best_unreached = unreached[0]
        best_visited = start

        # Sample to avoid O(n^2) on large maps
        sample_unreached = unreached[:50]
        sample_visited = list(visited)[:200]

        for ux, uy in sample_unreached:
            for vx, vy in sample_visited:
                dist = abs(ux - vx) + abs(uy - vy)
                if dist < best_dist:
                    best_dist = dist
                    best_unreached = (ux, uy)
                    best_visited = (vx, vy)

        # Carve a path
        x, y = best_unreached
        tx, ty = best_visited
        while x != tx:
            if 0 <= x < w and 0 <= y < h and interior.tiles[y][x] == WALL:
                interior.tiles[y][x] = FLOOR
            x += 1 if tx > x else -1
        while y != ty:
            if 0 <= x < w and 0 <= y < h and interior.tiles[y][x] == WALL:
                interior.tiles[y][x] = FLOOR
            y += 1 if ty > y else -1

        # Re-BFS to find what's now reachable
        visited.clear()
        queue = [start]
        visited.add(start)
        while queue:
            cx, cy = queue.pop(0)
            for dx, dy in CARDINALS:
                nx, ny = cx + dx, cy + dy
                if (0 <= nx < w and 0 <= ny < h and
                        (nx, ny) not in visited and
                        interior.tiles[ny][nx] in walkable):
                    visited.add((nx, ny))
                    queue.append((nx, ny))

        unreached = [(x, y) for x, y in unreached if (x, y) not in visited]


# ================================================================
# MAIN GENERATOR
# ================================================================

def generate_realistic_interior(building_name: str, building_kind: str,
                                floor_num: int = 0, seed: int = None,
                                num_residents: int = 2) -> InteriorMap:
    """Generate a realistic building interior with architecturally correct layout.

    Args:
        building_name: Display name of the building.
        building_kind: Type key (house, tavern, castle, temple, dungeon, etc.).
        floor_num: 0 = ground, positive = upper floors, negative = basements.
        seed: Random seed for reproducible generation.
        num_residents: Number of people living/working in this building.
            Controls building size:
                1-2 residents -> small (20x20), 3-5 rooms
                3-5 residents -> medium (30x30), 5-8 rooms
                6+  residents -> large (40x40), 8-12 rooms

    Returns:
        A fully populated InteriorMap with rooms, furniture, doors, windows,
        stairs, and decorations.
    """
    rng = random.Random(seed) if seed is not None else random.Random()

    # --- Determine map size based on residents ---
    if num_residents <= 2:
        map_w, map_h = 20, 20
        max_rooms = 5
    elif num_residents <= 5:
        map_w, map_h = 30, 30
        max_rooms = 8
    else:
        map_w, map_h = 40, 40
        max_rooms = 12

    # Dungeons and caves get extra space
    if building_kind in ("dungeon", "cave", "ruins"):
        map_w += 10
        map_h += 10

    # Castles and large buildings need more room
    if building_kind in ("castle", "monastery", "barracks"):
        map_w = max(map_w, 40)
        map_h = max(map_h, 40)
        max_rooms = max(max_rooms, 12)

    # --- Get room list ---
    room_list = list(BUILDING_ROOM_SETS.get(building_kind,
                                             BUILDING_ROOM_SETS.get("house", [])))

    # Scale room count based on num_residents
    if len(room_list) > max_rooms:
        # Keep essential rooms (entry, central, kitchen, stairwell) and trim extras
        essential = set()
        rules = CONNECTIVITY_RULES.get(building_kind,
                                        CONNECTIVITY_RULES.get("house", {}))
        if rules:
            central = rules.get("central", "common_room")
            essential.add(central)

        # Always keep entry_hall and stairwell if present
        for rt in room_list:
            if rt in ("entry_hall", "stairwell"):
                essential.add(rt)

        # Keep essential rooms, then fill remaining slots
        kept = [r for r in room_list if r in essential]
        others = [r for r in room_list if r not in essential]
        rng.shuffle(others)
        kept.extend(others[:max_rooms - len(kept)])
        room_list = kept
    elif len(room_list) < 2:
        # Very small buildings: ensure at least a room
        if "common_room" not in room_list and "bedroom" not in room_list:
            room_list.append("common_room")

    # Add extra bedrooms for large resident counts
    if num_residents > len([r for r in room_list
                            if "bedroom" in r or "dormitory" in r or
                               "quarters" in r or "guest" in r]):
        beds_needed = num_residents - len([r for r in room_list
                                           if "bedroom" in r or "dormitory" in r])
        for _ in range(max(0, beds_needed)):
            if len(room_list) < max_rooms:
                room_list.append("bedroom")

    # --- Create InteriorMap ---
    interior = InteriorMap(map_w, map_h, building_name, building_kind, floor_num)

    # --- Stage 1: Build room graph ---
    nodes = _build_room_graph(building_kind, room_list, rng)

    # --- Stage 2: Place rooms on grid ---
    success = _place_rooms_on_grid(nodes, map_w, map_h, rng)

    if not success:
        # Retry with a larger map
        map_w += 10
        map_h += 10
        interior = InteriorMap(map_w, map_h, building_name, building_kind, floor_num)
        nodes = _build_room_graph(building_kind, room_list, rng)
        _place_rooms_on_grid(nodes, map_w, map_h, rng)

    # Filter to only placed rooms
    placed_nodes = [n for n in nodes if n.grid_w > 0 and n.grid_h > 0]

    # --- Stage 3: Carve rooms, walls, doors, windows ---
    _carve_rooms_and_walls(interior, placed_nodes)
    _connect_adjacent_rooms(interior, placed_nodes, rng)

    if floor_num >= 0 and building_kind not in ("dungeon", "cave"):
        _place_windows(interior, rng)

    # --- Stage 4: Furniture placement ---
    _place_furniture(interior, placed_nodes, rng)

    # --- Stage 5: Decoration pass ---
    _decoration_pass(interior, placed_nodes, rng)

    # --- Final setup: entry, stairs, connectivity ---
    _setup_entry(interior, placed_nodes)
    _place_stairs(interior, placed_nodes, building_kind, floor_num)
    _ensure_connectivity(interior)

    # --- Populate room data on the InteriorMap ---
    for node in placed_nodes:
        connected_indices = [ch.index for ch in node.children]
        if node.parent is not None:
            connected_indices.append(node.parent.index)
        interior.rooms.append({
            "x": node.grid_x,
            "y": node.grid_y,
            "w": node.grid_w,
            "h": node.grid_h,
            "room_type": node.room_type,
            "connected_to": connected_indices,
        })

    return interior
