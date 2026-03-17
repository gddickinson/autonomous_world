"""
Functional zones: specialized rooms and outdoor areas with equipment.

Each zone has a type, required equipment/furniture, and enables specific NPC activities.
Zones are placed inside buildings (rooms) or outdoors (areas).
NPCs seek out zones to perform their trades and activities.

Indoor zones (rooms within buildings):
  Kitchen, Bedroom, Library, Workshop, Forge, Throne Room, etc.

Outdoor zones (designated areas):
  Paddock, Pasture, Market, Training Ground, Archery Range, etc.
"""

import random
import math
from typing import Dict, List, Optional, Tuple
from game.settings import *


# ================================================================
# ZONE DEFINITIONS
# ================================================================

# Each zone: required_tiles (what must be present), activities (what NPCs can do here),
#            equipment (what the zone contains), classes (who uses it)

INDOOR_ZONES = {
    "kitchen": {
        "min_size": (3, 3),
        "equipment": [TABLE, CHEST],  # cooking table and storage
        "activities": ["cooking", "brewing", "baking"],
        "classes": ["all"],
        "description": "A kitchen with cooking facilities",
        "workstation": "kitchen",
    },
    "bedroom": {
        "min_size": (2, 2),
        "equipment": [BED],
        "activities": ["sleeping", "resting"],
        "classes": ["all"],
        "description": "A bedroom for rest",
        "workstation": None,
    },
    "library": {
        "min_size": (3, 3),
        "equipment": [TABLE, CHEST],  # reading desk and bookshelves
        "activities": ["reading", "studying", "researching", "writing"],
        "classes": ["Wizard", "Cleric", "Bard", "Scholar", "Monk"],
        "description": "A library with books and scrolls",
        "workstation": "enchanter",
    },
    "workshop": {
        "min_size": (3, 3),
        "equipment": [TABLE, CHEST],
        "activities": ["crafting", "woodworking", "leatherworking", "weaving"],
        "classes": ["Rogue", "Ranger", "Druid"],
        "description": "A crafting workshop",
        "workstation": "workshop",
    },
    "forge": {
        "min_size": (3, 3),
        "equipment": [TABLE],  # anvil represented as table
        "activities": ["smithing", "smelting", "forging"],
        "classes": ["Fighter", "Barbarian"],
        "description": "A blacksmith's forge with anvil and furnace",
        "workstation": "forge",
    },
    "alchemy_lab": {
        "min_size": (3, 3),
        "equipment": [TABLE, CHEST],
        "activities": ["alchemy", "potion_brewing", "herbalism"],
        "classes": ["Wizard", "Cleric", "Druid", "Warlock"],
        "description": "An alchemy laboratory",
        "workstation": "alchemy",
    },
    "throne_room": {
        "min_size": (5, 5),
        "equipment": [TABLE],  # throne represented as special table
        "activities": ["ruling", "judging", "commanding", "audience"],
        "classes": ["monarch", "duke"],
        "description": "A throne room for the ruler",
        "workstation": None,
    },
    "dining_hall": {
        "min_size": (4, 4),
        "equipment": [TABLE, TABLE],
        "activities": ["eating", "feasting", "socializing"],
        "classes": ["all"],
        "description": "A communal dining hall",
        "workstation": None,
    },
    "barracks": {
        "min_size": (3, 4),
        "equipment": [BED, BED, CHEST],
        "activities": ["sleeping", "training", "arming"],
        "classes": ["Fighter", "Paladin", "guard", "knight"],
        "description": "Military barracks with bunks and weapon racks",
        "workstation": None,
    },
    "chapel": {
        "min_size": (3, 3),
        "equipment": [TABLE],  # altar
        "activities": ["praying", "healing", "blessing", "meditating"],
        "classes": ["Cleric", "Paladin", "Monk"],
        "description": "A small chapel for worship",
        "workstation": None,
    },
    "jeweler_studio": {
        "min_size": (2, 3),
        "equipment": [TABLE, CHEST],
        "activities": ["gem_cutting", "jewelry_making", "appraising"],
        "classes": ["Rogue", "Wizard"],
        "description": "A jeweler's studio with precision tools",
        "workstation": "jeweler",
    },
    "brewery": {
        "min_size": (3, 3),
        "equipment": [TABLE, CHEST],
        "activities": ["brewing", "fermenting", "distilling"],
        "classes": ["Bard", "Druid"],
        "description": "A brewery with vats and barrels",
        "workstation": "brewery",
    },
    "loom_room": {
        "min_size": (3, 3),
        "equipment": [TABLE],
        "activities": ["weaving", "spinning", "dyeing"],
        "classes": ["all"],
        "description": "A weaving room with loom",
        "workstation": "loom",
    },
    "storage_room": {
        "min_size": (2, 2),
        "equipment": [CHEST, CHEST],
        "activities": ["storing", "organizing"],
        "classes": ["all"],
        "description": "A storage room with chests and shelves",
        "workstation": None,
    },
    "infirmary": {
        "min_size": (3, 3),
        "equipment": [BED, TABLE],
        "activities": ["healing", "treating", "surgery"],
        "classes": ["Cleric", "Druid", "Monk"],
        "description": "A healing room with cots and supplies",
        "workstation": None,
    },
    "tannery": {
        "min_size": (3, 3),
        "equipment": [TABLE, CHEST],
        "activities": ["tanning", "curing_hides", "leatherworking"],
        "classes": ["Ranger", "Barbarian"],
        "description": "A tannery for processing hides",
        "workstation": "tannery",
    },
    "pottery_studio": {
        "min_size": (3, 3),
        "equipment": [TABLE],
        "activities": ["pottery", "glazing"],
        "classes": ["all"],
        "description": "A pottery studio with wheel and kiln",
        "workstation": "pottery",
    },
    "glassworks": {
        "min_size": (3, 3),
        "equipment": [TABLE, CHEST],
        "activities": ["glassblowing", "glass_cutting"],
        "classes": ["all"],
        "description": "A glassblowing workshop with furnace",
        "workstation": "glassworks",
    },
    "dye_house": {
        "min_size": (3, 3),
        "equipment": [TABLE, CHEST],
        "activities": ["dyeing", "color_mixing"],
        "classes": ["all"],
        "description": "A dye house with vats and pigments",
        "workstation": "dye_house",
    },
    "enchanting_room": {
        "min_size": (3, 3),
        "equipment": [TABLE, CHEST],
        "activities": ["enchanting", "inscribing", "warding"],
        "classes": ["Wizard", "Sorcerer", "Warlock"],
        "description": "An enchanting room with arcane circles",
        "workstation": "enchanter",
    },
    "war_room": {
        "min_size": (4, 4),
        "equipment": [TABLE, TABLE],
        "activities": ["planning", "strategizing", "commanding"],
        "classes": ["Fighter", "Paladin", "monarch", "duke"],
        "description": "A war room with strategy table and maps",
        "workstation": None,
    },
    "performance_hall": {
        "min_size": (4, 4),
        "equipment": [TABLE],
        "activities": ["performing", "singing", "storytelling"],
        "classes": ["Bard"],
        "description": "A hall for performances and entertainment",
        "workstation": None,
    },
    "meditation_room": {
        "min_size": (2, 3),
        "equipment": [],
        "activities": ["meditating", "divination", "ritual_casting"],
        "classes": ["Monk", "Cleric", "Druid"],
        "description": "A quiet room for meditation and prayer",
        "workstation": None,
    },
    "surgery": {
        "min_size": (3, 3),
        "equipment": [BED, TABLE],
        "activities": ["surgery", "medicine", "treating"],
        "classes": ["Cleric", "Druid"],
        "description": "A surgical room with clean cots and instruments",
        "workstation": "surgery",
    },
    "map_room": {
        "min_size": (3, 3),
        "equipment": [TABLE, CHEST],
        "activities": ["cartography", "navigation_planning", "researching"],
        "classes": ["Wizard", "Ranger", "Rogue"],
        "description": "A room with maps, charts, and navigation tools",
        "workstation": "cartography",
    },
    "bank_office": {
        "min_size": (3, 3),
        "equipment": [TABLE, CHEST],
        "activities": ["banking", "lending", "bookkeeping", "appraising"],
        "classes": ["Rogue", "Wizard"],
        "description": "A bank office with strongboxes and ledgers",
        "workstation": None,
    },
    "treasury": {
        "min_size": (3, 3),
        "equipment": [CHEST, CHEST],
        "activities": ["tax_collection", "auditing", "counting"],
        "classes": ["monarch", "duke"],
        "description": "A treasury room with locked chests",
        "workstation": None,
    },
}

OUTDOOR_ZONES = {
    "training_ground": {
        "min_size": (6, 6),
        "terrain": GRASS,
        "activities": ["training", "sparring", "drilling", "exercising"],
        "classes": ["Fighter", "Paladin", "Barbarian", "Monk", "guard", "knight"],
        "description": "An open training area with practice dummies",
    },
    "archery_range": {
        "min_size": (8, 4),
        "terrain": GRASS,
        "activities": ["archery_practice", "target_shooting"],
        "classes": ["Ranger", "Fighter", "Rogue"],
        "description": "A long archery range with targets",
    },
    "marketplace": {
        "min_size": (6, 6),
        "terrain": ROAD,
        "activities": ["trading", "selling", "buying", "bartering", "performing"],
        "classes": ["all"],
        "description": "An open marketplace for trading goods",
    },
    "paddock": {
        "min_size": (5, 5),
        "terrain": GRASS,
        "activities": ["animal_keeping", "horse_training", "herding"],
        "classes": ["Ranger", "Druid", "Barbarian"],
        "description": "An enclosed paddock for animals",
    },
    "pasture": {
        "min_size": (8, 8),
        "terrain": GRASS,
        "activities": ["grazing", "herding", "milking", "shearing"],
        "classes": ["Druid", "Ranger"],
        "description": "Open pastureland for livestock",
    },
    "garden": {
        "min_size": (4, 4),
        "terrain": TILLED_SOIL,
        "activities": ["gardening", "herb_growing", "composting"],
        "classes": ["Druid", "Monk", "Cleric"],
        "description": "A cultivated garden with herbs and flowers",
    },
    "orchard": {
        "min_size": (5, 5),
        "terrain": GRASS,
        "activities": ["fruit_picking", "pruning", "planting"],
        "classes": ["Druid", "Ranger"],
        "description": "An orchard of fruit trees",
    },
    "quarry": {
        "min_size": (4, 4),
        "terrain": ROCKY_GROUND,
        "activities": ["quarrying", "stone_cutting"],
        "classes": ["Fighter", "Barbarian"],
        "description": "A stone quarry",
    },
    "lumberyard": {
        "min_size": (5, 4),
        "terrain": GRASS,
        "activities": ["woodcutting", "plank_making", "log_splitting"],
        "classes": ["Ranger", "Barbarian"],
        "description": "A lumberyard with log piles",
    },
    "fishing_dock": {
        "min_size": (3, 3),
        "terrain": ROAD,
        "activities": ["fishing", "net_casting", "boat_repair"],
        "classes": ["Ranger", "Druid"],
        "description": "A dock for fishing",
    },
    "common_ground": {
        "min_size": (8, 8),
        "terrain": GRASS,
        "activities": ["socializing", "playing", "gathering", "celebrating"],
        "classes": ["all"],
        "description": "Open common land for community gatherings",
    },
    "graveyard": {
        "min_size": (4, 4),
        "terrain": GRASS,
        "activities": ["mourning", "burial", "remembrance"],
        "classes": ["Cleric", "Monk"],
        "description": "A graveyard for the departed",
    },
    "obstacle_course": {
        "min_size": (6, 4),
        "terrain": GRASS,
        "activities": ["climbing_practice", "swimming_practice", "agility_training"],
        "classes": ["Fighter", "Barbarian", "Monk", "Ranger", "Rogue"],
        "description": "An obstacle course for physical training",
    },
    "stable": {
        "min_size": (4, 5),
        "terrain": GRASS,
        "activities": ["horse_training", "mounted_combat_practice", "animal_training"],
        "classes": ["Ranger", "Paladin", "Fighter"],
        "description": "A stable for horses and mounted training",
    },
    "shipyard": {
        "min_size": (6, 5),
        "terrain": ROAD,
        "activities": ["shipbuilding", "boat_repair", "rigging"],
        "classes": ["all"],
        "description": "A shipyard for building and repairing boats",
    },
    "siege_ground": {
        "min_size": (6, 6),
        "terrain": GRASS,
        "activities": ["siege_practice", "fortification_building"],
        "classes": ["Fighter", "Barbarian"],
        "description": "A grounds for siege engine practice",
    },
    "ritual_circle": {
        "min_size": (4, 4),
        "terrain": GRASS,
        "activities": ["ritual_casting", "warding", "divination"],
        "classes": ["Wizard", "Druid", "Warlock", "Cleric"],
        "description": "A stone circle for magical rituals",
    },
    "swimming_hole": {
        "min_size": (4, 4),
        "terrain": GRASS,
        "activities": ["swimming", "diving", "water_training"],
        "classes": ["all"],
        "description": "A natural pool for swimming practice",
    },
    "thieves_den": {
        "min_size": (3, 4),
        "terrain": GRASS,
        "activities": ["lockpicking_practice", "stealth_training", "pickpocketing_practice"],
        "classes": ["Rogue"],
        "description": "A hidden area for practicing covert skills",
    },
}


# ================================================================
# ZONE INSTANCE
# ================================================================

class Zone:
    """A functional zone placed in the world."""
    __slots__ = ('zone_type', 'indoor', 'x', 'y', 'width', 'height',
                 'settlement', 'equipment_placed', 'owner')

    def __init__(self, zone_type: str, indoor: bool, x: int, y: int,
                 width: int, height: int, settlement: str = ""):
        self.zone_type = zone_type
        self.indoor = indoor
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.settlement = settlement
        self.equipment_placed = False
        self.owner = ""

    def contains(self, px: float, py: float) -> bool:
        return (self.x <= px < self.x + self.width and
                self.y <= py < self.y + self.height)

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)


# ================================================================
# ZONE SYSTEM
# ================================================================

class ZoneSystem:
    """Manages functional zones across the world."""

    def __init__(self):
        self.zones: List[Zone] = []
        self.settlement_zones: Dict[str, List[Zone]] = {}

    def initialize(self, structures: list, world, near=None, radius=500):
        """Detect and register zones in existing buildings and settlements.

        Args:
            near: optional (x, y) — if set, only process structures within radius
            radius: max distance from 'near' to process
        """
        for s in structures:
            if s.kind not in ("village", "town", "city", "castle", "hamlet"):
                continue
            if near is not None:
                nx, ny = near
                if abs(s.x - nx) > radius or abs(s.y - ny) > radius:
                    continue

            zones_here = []

            # Scan for indoor zones (rooms with furniture)
            self._detect_indoor_zones(s, world, zones_here)

            # Create outdoor zones around settlements
            self._create_outdoor_zones(s, world, zones_here)

            self.settlement_zones[s.name] = zones_here
            self.zones.extend(zones_here)

    def _detect_indoor_zones(self, structure, world, zones_list):
        """Detect rooms in buildings and classify them as zones."""
        sx, sy = structure.x, structure.y
        r = structure.radius

        # Scan for clusters of floor tiles with furniture
        visited = set()
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                nx, ny = sx + dx, sy + dy
                if (nx, ny) in visited:
                    continue
                if not (0 <= nx < world.width and 0 <= ny < world.height):
                    continue
                if world.tiles[ny][nx] != FLOOR:
                    continue

                # Flood-fill to find the room
                room_tiles = []
                furniture = []
                stack = [(nx, ny)]
                while stack and len(room_tiles) < 50:
                    cx, cy = stack.pop()
                    if (cx, cy) in visited:
                        continue
                    visited.add((cx, cy))
                    if not (0 <= cx < world.width and 0 <= cy < world.height):
                        continue
                    tile = world.tiles[cy][cx]
                    if tile in (FLOOR, TABLE, BED, CHEST, DOOR, STAIRS_UP, STAIRS_DOWN):
                        room_tiles.append((cx, cy))
                        if tile in (TABLE, BED, CHEST):
                            furniture.append(tile)
                        for ddx, ddy in [(-1,0),(1,0),(0,-1),(0,1)]:
                            stack.append((cx+ddx, cy+ddy))

                if len(room_tiles) < 4:
                    continue

                # Classify room by furniture
                min_x = min(t[0] for t in room_tiles)
                min_y = min(t[1] for t in room_tiles)
                max_x = max(t[0] for t in room_tiles)
                max_y = max(t[1] for t in room_tiles)
                width = max_x - min_x + 1
                height = max_y - min_y + 1

                zone_type = self._classify_room(furniture, width, height, structure.kind)
                zone = Zone(zone_type, True, min_x, min_y, width, height, structure.name)
                zones_list.append(zone)

    def _classify_room(self, furniture: list, width: int, height: int,
                       settlement_kind: str) -> str:
        """Classify a room based on its furniture and size."""
        has_bed = BED in furniture
        has_table = TABLE in furniture
        has_chest = CHEST in furniture
        area = width * height

        if has_bed and not has_table and area <= 8:
            return "bedroom"
        elif has_bed and has_table and area >= 12:
            return "barracks"
        elif has_table and has_chest and area >= 9:
            if settlement_kind == "castle" and area >= 20:
                return "throne_room"
            return "workshop"  # default functional room
        elif has_table and area >= 12:
            return "dining_hall"
        elif has_chest and area >= 6:
            return "storage_room"
        elif has_table:
            return "kitchen"
        elif has_bed:
            return "bedroom"
        else:
            return "storage_room"

    def _create_outdoor_zones(self, structure, world, zones_list):
        """Create outdoor functional zones around a settlement."""
        sx, sy = structure.x, structure.y
        r = structure.radius
        rng = random.Random(hash(structure.name))

        # Training ground (for towns, cities, castles)
        if structure.kind in ("town", "city", "castle"):
            tx = sx + rng.randint(r, r + 8)
            ty = sy + rng.randint(-5, 5)
            zone = Zone("training_ground", False, tx, ty, 6, 6, structure.name)
            zones_list.append(zone)

        # Marketplace (for villages, towns, cities)
        if structure.kind in ("village", "town", "city"):
            zone = Zone("marketplace", False, sx - 3, sy - 3, 6, 6, structure.name)
            zones_list.append(zone)

        # Pasture/paddock (for villages and hamlets)
        if structure.kind in ("village", "hamlet"):
            px = sx + rng.randint(-r-8, -r-2)
            py = sy + rng.randint(-5, 5)
            zone = Zone("pasture", False, px, py, 8, 8, structure.name)
            zones_list.append(zone)

        # Garden (for temples and monasteries)
        if structure.kind in ("village", "city"):
            gx = sx + rng.randint(r+2, r+6)
            gy = sy + rng.randint(-3, 3)
            zone = Zone("garden", False, gx, gy, 4, 4, structure.name)
            zones_list.append(zone)

        # Common ground (for all settlements)
        if structure.kind in ("town", "city"):
            zone = Zone("common_ground", False, sx + rng.randint(-8, 8),
                        sy + r + 2, 8, 8, structure.name)
            zones_list.append(zone)

        # Stable (for towns, cities, castles)
        if structure.kind in ("town", "city", "castle"):
            stx = sx + rng.randint(-r-6, -r-2)
            sty = sy + rng.randint(-3, 3)
            zone = Zone("stable", False, stx, sty, 4, 5, structure.name)
            zones_list.append(zone)

        # Ritual circle (for cities and castles)
        if structure.kind in ("city", "castle"):
            rcx = sx + rng.randint(r+2, r+8)
            rcy = sy + rng.randint(r+2, r+6)
            zone = Zone("ritual_circle", False, rcx, rcy, 4, 4, structure.name)
            zones_list.append(zone)

        # Obstacle course (for towns, cities, castles)
        if structure.kind in ("town", "city", "castle"):
            ocx = sx + rng.randint(-r-8, -r-3)
            ocy = sy + rng.randint(r+2, r+6)
            zone = Zone("obstacle_course", False, ocx, ocy, 6, 4, structure.name)
            zones_list.append(zone)

        # Swimming hole (villages near water get one)
        if structure.kind in ("village", "hamlet"):
            zone = Zone("swimming_hole", False, sx + rng.randint(r+2, r+6),
                        sy + rng.randint(-4, 4), 4, 4, structure.name)
            zones_list.append(zone)

    def find_zone(self, zone_type: str, near_x: float, near_y: float,
                  max_dist: float = 50) -> Optional[Zone]:
        """Find the nearest zone of a given type."""
        best = None
        best_dist = max_dist
        for zone in self.zones:
            if zone.zone_type != zone_type:
                continue
            cx, cy = zone.center
            d = math.sqrt((cx - near_x)**2 + (cy - near_y)**2)
            if d < best_dist:
                best_dist = d
                best = zone
        return best

    def find_zones_for_class(self, char_class: str, near_x: float, near_y: float,
                             max_dist: float = 50) -> List[Zone]:
        """Find zones suitable for a character class."""
        results = []
        all_defs = {**INDOOR_ZONES, **OUTDOOR_ZONES}
        suitable_types = set()
        for ztype, zdef in all_defs.items():
            if "all" in zdef["classes"] or char_class in zdef["classes"]:
                suitable_types.add(ztype)

        for zone in self.zones:
            if zone.zone_type in suitable_types:
                cx, cy = zone.center
                d = math.sqrt((cx - near_x)**2 + (cy - near_y)**2)
                if d < max_dist:
                    results.append(zone)

        results.sort(key=lambda z: math.sqrt(
            (z.center[0] - near_x)**2 + (z.center[1] - near_y)**2))
        return results

    def get_zone_at(self, x: float, y: float) -> Optional[Zone]:
        """Get the zone at a world position."""
        for zone in self.zones:
            if zone.contains(x, y):
                return zone
        return None

    def get_workstation_at(self, x: float, y: float) -> Optional[str]:
        """Get the workstation type available at a position."""
        zone = self.get_zone_at(x, y)
        if zone and zone.zone_type in INDOOR_ZONES:
            return INDOOR_ZONES[zone.zone_type].get("workstation")
        return None

    def get_zone_report(self, settlement_name: str = "") -> str:
        """Get summary of zones."""
        if settlement_name:
            zones = self.settlement_zones.get(settlement_name, [])
        else:
            zones = self.zones

        counts = {}
        for z in zones:
            counts[z.zone_type] = counts.get(z.zone_type, 0) + 1

        parts = [f"{k}: {v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])]
        return ", ".join(parts)
