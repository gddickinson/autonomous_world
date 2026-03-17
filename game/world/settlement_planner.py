"""Settlement Planner — terrain-aware medieval settlement layout.

Plans settlement layouts based on real medieval principles:
- Water-centric: settlements near rivers/wells, water determines layout
- Market at center: market square is the hub
- Church/temple prominent: near center on high ground
- Craft districts: blacksmiths at edge (fire risk), tanners downstream
- Farms outside walls: agricultural land surrounds the settlement
- Roads radiate from center: main roads connect market to gates
- Walls follow terrain: use natural features for defense
- Castle on high ground: for defense and authority
- Granaries near farms: storage close to production
- Stables near gates: for travelers and military

Each settlement type (hamlet, village, town, city, castle) has different
zone layouts. Buildings are placed in appropriate zones based on their
function, creating realistic medieval communities.
"""

import math
import random
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass, field

from game.settings import (WALL, FLOOR, DOOR, GRASS, ROAD, FARMLAND,
                            WATER, SHALLOW_WATER, COBBLESTONE, WELL,
                            GRAVEL_ROAD, MOUNTAIN, SAND, BUILT_WALL,
                            BUILT_FLOOR, BRIDGE, WHEAT_FIELD, STABLE_FLOOR)


# ================================================================
# DATA CLASSES
# ================================================================

@dataclass
class PlannedBuilding:
    """A building with its planned position and purpose."""
    name: str
    kind: str       # "granary", "blacksmith", "house", "market_stall", etc.
    x: int
    y: int
    w: int
    h: int
    zone: str       # which zone it belongs to
    blueprint_name: Optional[str] = None

    def overlaps(self, other: 'PlannedBuilding', buffer: int = 2) -> bool:
        """Check if two buildings overlap (with buffer space)."""
        return not (self.x + self.w + buffer <= other.x or
                    other.x + other.w + buffer <= self.x or
                    self.y + self.h + buffer <= other.y or
                    other.y + other.h + buffer <= self.y)

    def overlaps_rect(self, ox, oy, ow, oh, buffer: int = 2) -> bool:
        return not (self.x + self.w + buffer <= ox or
                    ox + ow + buffer <= self.x or
                    self.y + self.h + buffer <= oy or
                    oy + oh + buffer <= self.y)


@dataclass
class DefensePlan:
    """Defense layout for walled settlements."""
    wall_points: List[Tuple[int, int]] = field(default_factory=list)
    tower_positions: List[Tuple[int, int]] = field(default_factory=list)
    gate_positions: List[Tuple[int, int, str]] = field(default_factory=list)
    # gate: (x, y, direction)
    wall_radius: int = 0
    has_moat: bool = False


@dataclass
class SettlementLayout:
    """Complete layout plan for a settlement."""
    buildings: List[PlannedBuilding]
    roads: List[Tuple[int, int, int, int, str]]
    # (x1, y1, x2, y2, road_type)
    defenses: Optional[DefensePlan]
    farms: List[Tuple[int, int, int]]
    # (x, y, radius)
    zones: Dict[str, Tuple[int, int, int, int]]
    # zone_name -> (x, y, w, h)
    well_positions: List[Tuple[int, int]] = field(default_factory=list)


# ================================================================
# ZONE DEFINITIONS — what each settlement type should contain
# ================================================================

# radius_fraction: fraction of settlement radius for this zone's distance
# position: preferred compass direction or "center", "highest", "gate"
# buildings: list of building kind names to place in this zone

SETTLEMENT_ZONES = {
    "hamlet": {
        "center": {
            "buildings": ["well"],
            "radius_fraction": 0.2,
            "position": "center",
        },
        "residential": {
            "buildings": ["cottage", "cottage", "shack", "hovel"],
            "radius_fraction": 0.5,
            "position": "along_road",
        },
        "farming": {
            "buildings": ["barn"],
            "radius_fraction": 0.7,
            "position": "south",
        },
    },
    "village": {
        "center": {
            "buildings": ["well", "market_stall", "tavern"],
            "radius_fraction": 0.15,
            "position": "center",
        },
        "temple": {
            "buildings": ["chapel"],
            "radius_fraction": 0.25,
            "position": "north",
        },
        "craft": {
            "buildings": ["blacksmith", "workshop"],
            "radius_fraction": 0.45,
            "position": "east",
        },
        "residential": {
            "buildings": ["cottage", "cottage", "farmhouse", "house",
                          "cottage", "hovel"],
            "radius_fraction": 0.5,
            "position": "spread",
        },
        "farming": {
            "buildings": ["barn", "granary"],
            "radius_fraction": 0.7,
            "position": "south",
        },
        "stable": {
            "buildings": ["stable"],
            "radius_fraction": 0.6,
            "position": "south",
        },
    },
    "town": {
        "market": {
            "buildings": ["market_stall", "market_stall", "market_stall"],
            "radius_fraction": 0.1,
            "position": "center",
        },
        "administrative": {
            "buildings": ["town_hall", "treasury"],
            "radius_fraction": 0.15,
            "position": "center",
        },
        "temple": {
            "buildings": ["temple", "library"],
            "radius_fraction": 0.2,
            "position": "north",
        },
        "tavern": {
            "buildings": ["tavern"],
            "radius_fraction": 0.2,
            "position": "center",
        },
        "craft_metal": {
            "buildings": ["blacksmith", "workshop"],
            "radius_fraction": 0.5,
            "position": "east",
        },
        "craft_cloth": {
            "buildings": ["weaver", "tanner"],
            "radius_fraction": 0.55,
            "position": "water_downstream",
        },
        "bakery": {
            "buildings": ["bakery"],
            "radius_fraction": 0.15,
            "position": "center",
        },
        "residential": {
            "buildings": ["house", "house", "townhouse", "house",
                          "cottage", "house", "townhouse", "cottage",
                          "house", "house", "cottage", "house"],
            "radius_fraction": 0.55,
            "position": "spread",
        },
        "military": {
            "buildings": ["barracks", "armoury"],
            "radius_fraction": 0.65,
            "position": "gate",
        },
        "storage": {
            "buildings": ["warehouse", "granary", "granary", "cellar"],
            "radius_fraction": 0.5,
            "position": "south",
        },
        "stable": {
            "buildings": ["stable", "stable"],
            "radius_fraction": 0.6,
            "position": "gate",
        },
    },
    "city": {
        "market": {
            "buildings": ["market_stall", "market_stall", "market_stall",
                          "market_stall", "market_stall"],
            "radius_fraction": 0.08,
            "position": "center",
        },
        "administrative": {
            "buildings": ["town_hall", "treasury", "library"],
            "radius_fraction": 0.12,
            "position": "center",
        },
        "temple": {
            "buildings": ["temple", "chapel", "library"],
            "radius_fraction": 0.15,
            "position": "north",
        },
        "tavern": {
            "buildings": ["tavern", "tavern"],
            "radius_fraction": 0.2,
            "position": "center",
        },
        "craft_metal": {
            "buildings": ["blacksmith", "blacksmith", "workshop",
                          "workshop"],
            "radius_fraction": 0.45,
            "position": "east",
        },
        "craft_cloth": {
            "buildings": ["weaver", "weaver", "tanner"],
            "radius_fraction": 0.5,
            "position": "water_downstream",
        },
        "bakery": {
            "buildings": ["bakery", "bakery"],
            "radius_fraction": 0.12,
            "position": "center",
        },
        "mansion_district": {
            "buildings": ["mansion", "mansion", "mansion"],
            "radius_fraction": 0.2,
            "position": "north",
        },
        "residential": {
            "buildings": (["house"] * 8 + ["townhouse"] * 6
                          + ["cottage"] * 4 + ["mansion"]),
            "radius_fraction": 0.55,
            "position": "spread",
        },
        "military": {
            "buildings": ["barracks", "barracks", "armoury", "armoury"],
            "radius_fraction": 0.65,
            "position": "gate",
        },
        "storage": {
            "buildings": ["warehouse", "warehouse", "granary", "granary",
                          "cellar", "cellar"],
            "radius_fraction": 0.5,
            "position": "south",
        },
        "stable": {
            "buildings": ["stable", "stable", "stable"],
            "radius_fraction": 0.6,
            "position": "gate",
        },
    },
    "castle": {
        "keep": {
            "buildings": ["castle_keep"],
            "radius_fraction": 0.15,
            "position": "highest",
        },
        "inner_bailey": {
            "buildings": ["great_hall", "chapel", "lord_chambers"],
            "radius_fraction": 0.3,
            "position": "center",
        },
        "outer_bailey": {
            "buildings": ["barracks", "stable", "blacksmith",
                          "granary", "well"],
            "radius_fraction": 0.55,
            "position": "spread",
        },
        "gatehouse": {
            "buildings": ["gatehouse"],
            "radius_fraction": 0.6,
            "position": "south",
        },
    },
}


# ================================================================
# SPECIALIZATION ZONE OVERRIDES
# ================================================================
# These modify or replace zones from SETTLEMENT_ZONES based on
# the settlement's geographic specialization.  Only non-None entries
# override; everything else falls through to the base zones.

SPECIALIZATION_ZONE_OVERRIDES: Dict[str, Dict[str, Dict]] = {
    "port": {
        "waterfront": {
            "buildings": ["dock", "dock", "fish_market"],
            "radius_fraction": 0.55,
            "position": "water",
        },
        "shipyard": {
            "buildings": ["shipyard"],
            "radius_fraction": 0.5,
            "position": "water",
        },
        "harbor": {
            "buildings": ["lighthouse", "sailor_tavern"],
            "radius_fraction": 0.6,
            "position": "water",
        },
        "storage": {
            "buildings": ["warehouse", "warehouse", "granary"],
            "radius_fraction": 0.4,
            "position": "water",
        },
    },
    "fishing": {
        "waterfront": {
            "buildings": ["dock"],
            "radius_fraction": 0.5,
            "position": "water",
        },
        "center": {
            "buildings": ["well", "tavern"],
            "radius_fraction": 0.15,
            "position": "center",
        },
    },
    "mining": {
        "mine_district": {
            "buildings": ["mine_entrance", "mine_entrance"],
            "radius_fraction": 0.6,
            "position": "highest",
        },
        "smelting": {
            "buildings": ["smelter", "assay_office"],
            "radius_fraction": 0.5,
            "position": "east",
        },
        "ore_storage": {
            "buildings": ["ore_warehouse", "warehouse"],
            "radius_fraction": 0.4,
            "position": "south",
        },
        "craft_metal": {
            "buildings": ["blacksmith", "blacksmith", "workshop"],
            "radius_fraction": 0.35,
            "position": "east",
        },
    },
    "lumber": {
        "lumber_district": {
            "buildings": ["sawmill", "lumber_yard"],
            "radius_fraction": 0.55,
            "position": "east",
        },
        "forestry": {
            "buildings": ["hunting_lodge", "charcoal_kiln"],
            "radius_fraction": 0.65,
            "position": "north",
        },
        "craft": {
            "buildings": ["carpenter_workshop", "workshop"],
            "radius_fraction": 0.35,
            "position": "east",
        },
    },
    "agricultural": {
        "farming": {
            "buildings": ["barn", "barn", "granary", "granary", "livestock_pen"],
            "radius_fraction": 0.55,
            "position": "south",
        },
        "milling": {
            "buildings": ["windmill", "mill"],
            "radius_fraction": 0.45,
            "position": "highest",
        },
        "bakery": {
            "buildings": ["bakery"],
            "radius_fraction": 0.15,
            "position": "center",
        },
    },
    "crossroads": {
        "market": {
            "buildings": ["market_stall", "market_stall", "market_stall",
                          "market_stall", "market_stall", "market_stall"],
            "radius_fraction": 0.12,
            "position": "center",
        },
        "tavern": {
            "buildings": ["caravanserai", "tavern", "tavern"],
            "radius_fraction": 0.2,
            "position": "center",
        },
        "banking": {
            "buildings": ["money_changer"],
            "radius_fraction": 0.15,
            "position": "center",
        },
        "stable": {
            "buildings": ["stable", "stable", "stable"],
            "radius_fraction": 0.5,
            "position": "gate",
        },
    },
    "oasis": {
        "center": {
            "buildings": ["well", "cistern"],
            "radius_fraction": 0.1,
            "position": "center",
        },
        "tavern": {
            "buildings": ["caravanserai"],
            "radius_fraction": 0.2,
            "position": "center",
        },
        "market": {
            "buildings": ["market_stall", "market_stall", "market_stall"],
            "radius_fraction": 0.15,
            "position": "center",
        },
    },
    "swamp": {
        "residential": {
            "buildings": ["raised_house", "raised_house", "raised_house",
                          "herbalist_hut"],
            "radius_fraction": 0.5,
            "position": "spread",
        },
        "resources": {
            "buildings": ["peat_store"],
            "radius_fraction": 0.55,
            "position": "south",
        },
    },
    "border": {
        "military": {
            "buildings": ["barracks", "barracks", "armoury", "guard_tower",
                          "guard_tower"],
            "radius_fraction": 0.55,
            "position": "gate",
        },
        "customs": {
            "buildings": ["customs_house", "gatehouse"],
            "radius_fraction": 0.6,
            "position": "gate",
        },
    },
    "capital": {
        "palace": {
            "buildings": ["royal_palace"],
            "radius_fraction": 0.1,
            "position": "center",
        },
        "administrative": {
            "buildings": ["town_hall", "treasury", "library"],
            "radius_fraction": 0.2,
            "position": "center",
        },
        "temple": {
            "buildings": ["temple", "chapel"],
            "radius_fraction": 0.25,
            "position": "north",
        },
        "market": {
            "buildings": ["market_stall", "market_stall", "market_stall",
                          "market_stall", "market_stall", "market_stall",
                          "market_stall"],
            "radius_fraction": 0.15,
            "position": "center",
        },
        "mansion_district": {
            "buildings": ["mansion", "mansion", "mansion", "mansion"],
            "radius_fraction": 0.25,
            "position": "north",
        },
        "military": {
            "buildings": ["barracks", "barracks", "armoury", "armoury"],
            "radius_fraction": 0.6,
            "position": "gate",
        },
    },
}


# ================================================================
# TERRAIN ANALYSIS
# ================================================================

@dataclass
class TerrainAnalysis:
    """Results of terrain analysis around a settlement center."""
    water_direction: Optional[str] = None  # N/S/E/W or None
    water_distance: float = 999.0
    high_ground_dx: int = 0
    high_ground_dy: int = 0
    high_ground_elev: float = 0.0
    flat_area_direction: Optional[str] = None
    road_directions: List[str] = field(default_factory=list)
    has_river_north: bool = False
    has_river_south: bool = False
    has_river_east: bool = False
    has_river_west: bool = False


# ================================================================
# SETTLEMENT PLANNER
# ================================================================

class SettlementPlanner:
    """Plans settlement layout based on terrain, economy, and defense needs.

    Uses medieval layout principles to create realistic settlement plans
    that the chunk generator can stamp into the world.
    """

    def plan_settlement(self, name: str, kind: str, cx: int, cy: int,
                        radius: int, world_plan, rng: random.Random,
                        specialization: str = "general"
                        ) -> SettlementLayout:
        """Create a detailed settlement layout plan.

        Args:
            name: settlement name
            kind: "hamlet", "village", "town", "city", "castle"
            cx, cy: center world coordinates
            radius: settlement radius in tiles
            world_plan: WorldPlan with elevation cache and rivers
            rng: seeded RNG for determinism
            specialization: geographic specialization ("port", "mining", etc.)

        Returns:
            SettlementLayout with positioned buildings, roads, walls, farms
        """
        self._specialization = specialization

        # 1. Analyze terrain around center
        terrain = self._analyze_terrain(cx, cy, radius, world_plan)

        # 2. Compute zone positions based on terrain + specialization
        zones = self._plan_zones(kind, cx, cy, radius, terrain, rng,
                                  specialization)

        # 3. Place buildings in their zones (specialization-aware)
        buildings = self._place_buildings(kind, zones, cx, cy, radius,
                                          terrain, rng, specialization)

        # 4. Plan roads connecting buildings to center
        roads = self._plan_roads(buildings, cx, cy, radius, kind, zones)

        # 5. Plan walls and defenses (for towns+ and border settlements)
        defenses = self._plan_defenses(kind, cx, cy, radius, terrain,
                                        buildings, rng)

        # 6. Plan farms outside walls (more for agricultural)
        farms = self._plan_farms(kind, cx, cy, radius, terrain, rng,
                                  specialization)

        # 7. Plan well positions (more for oasis/swamp)
        wells = self._plan_wells(kind, cx, cy, radius, terrain, rng,
                                  specialization)

        return SettlementLayout(
            buildings=buildings,
            roads=roads,
            defenses=defenses,
            farms=farms,
            zones=zones,
            well_positions=wells,
        )

    # ------------------------------------------------------------------
    # Terrain Analysis
    # ------------------------------------------------------------------

    def _analyze_terrain(self, cx: int, cy: int, radius: int,
                         world_plan) -> TerrainAnalysis:
        """Analyze terrain features around the settlement center."""
        ta = TerrainAnalysis()
        scan_range = int(radius * 1.5)

        # Scan for water in cardinal directions
        best_water_dist = 999.0
        for direction, dx, dy in [("north", 0, -1), ("south", 0, 1),
                                   ("east", 1, 0), ("west", -1, 0)]:
            for dist in range(5, scan_range, 5):
                px = cx + dx * dist
                py = cy + dy * dist
                elev = world_plan.get_elevation_fast(px, py)
                if elev < 0.22:  # water threshold
                    if dist < best_water_dist:
                        best_water_dist = dist
                        ta.water_direction = direction
                        ta.water_distance = dist
                    if direction == "north":
                        ta.has_river_north = True
                    elif direction == "south":
                        ta.has_river_south = True
                    elif direction == "east":
                        ta.has_river_east = True
                    elif direction == "west":
                        ta.has_river_west = True
                    break

        # Also check rivers passing through/near settlement
        for river in world_plan.rivers:
            for px, py in river.points:
                dist = math.sqrt((px - cx) ** 2 + (py - cy) ** 2)
                if dist < scan_range:
                    dx_r = px - cx
                    dy_r = py - cy
                    if abs(dx_r) > abs(dy_r):
                        if dx_r > 0:
                            ta.has_river_east = True
                        else:
                            ta.has_river_west = True
                    else:
                        if dy_r > 0:
                            ta.has_river_south = True
                        else:
                            ta.has_river_north = True
                    if dist < ta.water_distance:
                        ta.water_distance = dist
                        if abs(dx_r) > abs(dy_r):
                            ta.water_direction = "east" if dx_r > 0 else "west"
                        else:
                            ta.water_direction = "south" if dy_r > 0 else "north"

        # Find highest point within radius for castle/temple placement
        best_elev = 0.0
        best_hx, best_hy = 0, 0
        step = max(3, radius // 8)
        for dy in range(-radius, radius + 1, step):
            for dx in range(-radius, radius + 1, step):
                if dx * dx + dy * dy > radius * radius:
                    continue
                elev = world_plan.get_elevation_fast(cx + dx, cy + dy)
                if elev > best_elev and elev < 0.65:  # avoid mountains
                    best_elev = elev
                    best_hx, best_hy = dx, dy
        ta.high_ground_dx = best_hx
        ta.high_ground_dy = best_hy
        ta.high_ground_elev = best_elev

        # Determine flat area direction (for farms) — opposite of water
        if ta.water_direction:
            opposite = {"north": "south", "south": "north",
                        "east": "west", "west": "east"}
            ta.flat_area_direction = opposite.get(ta.water_direction, "south")
        else:
            ta.flat_area_direction = "south"

        # Check which directions have roads
        for road in world_plan.roads:
            for wp_x, wp_y in road.waypoints:
                dist = math.sqrt((wp_x - cx) ** 2 + (wp_y - cy) ** 2)
                if dist < radius * 2:
                    dx_r = wp_x - cx
                    dy_r = wp_y - cy
                    if abs(dx_r) > abs(dy_r):
                        d = "east" if dx_r > 0 else "west"
                    else:
                        d = "south" if dy_r > 0 else "north"
                    if d not in ta.road_directions:
                        ta.road_directions.append(d)

        return ta

    # ------------------------------------------------------------------
    # Zone Planning
    # ------------------------------------------------------------------

    def _plan_zones(self, kind: str, cx: int, cy: int, radius: int,
                    terrain: TerrainAnalysis, rng: random.Random,
                    specialization: str = "general"
                    ) -> Dict[str, Tuple[int, int, int, int]]:
        """Compute (x, y, w, h) for each zone based on terrain.

        Merges specialization-specific zone overrides on top of the
        base settlement-type zones so that a port town gets waterfront
        and dock zones, a mining town gets mine zones, etc.
        """
        zone_defs = dict(SETTLEMENT_ZONES.get(kind, SETTLEMENT_ZONES["hamlet"]))

        # Merge specialization overrides — they add new zones or replace
        # existing ones with specialization-specific buildings
        spec_overrides = SPECIALIZATION_ZONE_OVERRIDES.get(specialization, {})
        for zone_name, zdef in spec_overrides.items():
            zone_defs[zone_name] = zdef

        zones = {}

        for zone_name, zdef in zone_defs.items():
            r_frac = zdef["radius_fraction"]
            position = zdef.get("position", "spread")
            zone_r = int(radius * r_frac)
            zone_size = max(10, zone_r)

            # Determine zone center offset based on position preference
            zx, zy = self._resolve_zone_position(
                position, cx, cy, radius, r_frac, terrain, rng)

            zones[zone_name] = (zx - zone_size // 2, zy - zone_size // 2,
                                zone_size, zone_size)

        return zones

    def _resolve_zone_position(self, position: str, cx: int, cy: int,
                                radius: int, r_frac: float,
                                terrain: TerrainAnalysis,
                                rng: random.Random
                                ) -> Tuple[int, int]:
        """Convert a position hint into world coordinates."""
        dist = int(radius * r_frac)

        if position == "water":
            # Place toward the nearest water source (for port/fishing zones)
            if terrain.water_direction:
                return self._resolve_zone_position(
                    terrain.water_direction, cx, cy, radius, r_frac,
                    terrain, rng)
            # fallback: south
            return cx + rng.randint(-dist // 3, dist // 3), cy + dist

        if position == "center":
            return (cx + rng.randint(-3, 3),
                    cy + rng.randint(-3, 3))

        elif position == "north":
            return cx + rng.randint(-dist // 3, dist // 3), cy - dist

        elif position == "south":
            return cx + rng.randint(-dist // 3, dist // 3), cy + dist

        elif position == "east":
            return cx + dist, cy + rng.randint(-dist // 3, dist // 3)

        elif position == "west":
            return cx - dist, cy + rng.randint(-dist // 3, dist // 3)

        elif position == "southeast":
            d = int(dist * 0.7)
            return cx + d, cy + d

        elif position == "highest":
            # Use terrain analysis to find high ground
            return (cx + terrain.high_ground_dx,
                    cy + terrain.high_ground_dy)

        elif position == "water_downstream":
            # Place downstream of water source (tanners, etc.)
            if terrain.water_direction == "north":
                return cx + rng.randint(-dist // 2, dist // 2), cy - dist
            elif terrain.water_direction == "south":
                return cx + rng.randint(-dist // 2, dist // 2), cy + dist
            elif terrain.water_direction == "east":
                return cx + dist, cy + rng.randint(-dist // 2, dist // 2)
            elif terrain.water_direction == "west":
                return cx - dist, cy + rng.randint(-dist // 2, dist // 2)
            # fallback: southeast
            d = int(dist * 0.7)
            return cx + d, cy + d

        elif position == "gate":
            # Place near the most used gate direction (road direction)
            if terrain.road_directions:
                d = rng.choice(terrain.road_directions)
                return self._resolve_zone_position(
                    d, cx, cy, radius, r_frac, terrain, rng)
            return cx + rng.randint(-dist, dist), cy + dist

        elif position == "along_road":
            # Scatter along the main east-west road
            return (cx + rng.randint(-dist, dist),
                    cy + rng.choice([-1, 1]) * rng.randint(3, dist // 2 + 3))

        else:  # "spread"
            angle = rng.uniform(0, 2 * math.pi)
            return (int(cx + math.cos(angle) * dist),
                    int(cy + math.sin(angle) * dist))

    # ------------------------------------------------------------------
    # Building Placement
    # ------------------------------------------------------------------

    def _place_buildings(self, kind: str, zones: Dict,
                         cx: int, cy: int, radius: int,
                         terrain: TerrainAnalysis,
                         rng: random.Random,
                         specialization: str = "general"
                         ) -> List[PlannedBuilding]:
        """Place buildings within their designated zones."""
        from game.world.buildings import BLUEPRINT_BY_KIND

        # Build merged zone defs (same as _plan_zones)
        zone_defs = dict(SETTLEMENT_ZONES.get(kind, SETTLEMENT_ZONES["hamlet"]))
        spec_overrides = SPECIALIZATION_ZONE_OVERRIDES.get(specialization, {})
        for zone_name, zdef in spec_overrides.items():
            zone_defs[zone_name] = zdef
        placed: List[PlannedBuilding] = []

        for zone_name, zdef in zone_defs.items():
            zone_rect = zones.get(zone_name)
            if not zone_rect:
                continue

            zx, zy, zw, zh = zone_rect
            building_kinds = zdef.get("buildings", [])

            for bkind in building_kinds:
                bp = BLUEPRINT_BY_KIND.get(bkind)
                if bp is None:
                    continue

                # Try to place within the zone, with some randomness
                success = False
                use_bp = bp
                for attempt in range(40):
                    # Randomly rotate
                    if rng.random() < 0.4:
                        use_bp = bp.rotated()
                    else:
                        use_bp = bp

                    bw, bh = use_bp.width, use_bp.height

                    # Pick position within zone rectangle with jitter
                    bx = zx + rng.randint(0, max(0, zw - bw))
                    by = zy + rng.randint(0, max(0, zh - bh))

                    # Ensure within settlement radius (with some margin)
                    dx = (bx + bw // 2) - cx
                    dy = (by + bh // 2) - cy
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist > radius * 0.85 and kind != "castle":
                        continue

                    # Check overlap with already placed buildings
                    pb = PlannedBuilding(
                        name=use_bp.name, kind=bkind,
                        x=bx, y=by, w=bw, h=bh,
                        zone=zone_name, blueprint_name=use_bp.name)

                    overlap = any(pb.overlaps(existing) for existing in placed)
                    if overlap:
                        continue

                    placed.append(pb)
                    success = True
                    break

                if not success:
                    # Try with wider search (anywhere within radius)
                    for attempt in range(30):
                        if rng.random() < 0.4:
                            use_bp = bp.rotated()
                        else:
                            use_bp = bp

                        bw, bh = use_bp.width, use_bp.height
                        angle = rng.uniform(0, 2 * math.pi)
                        dist_f = rng.uniform(3, radius * 0.75)
                        bx = int(cx + math.cos(angle) * dist_f - bw // 2)
                        by = int(cy + math.sin(angle) * dist_f - bh // 2)

                        pb = PlannedBuilding(
                            name=use_bp.name, kind=bkind,
                            x=bx, y=by, w=bw, h=bh,
                            zone=zone_name, blueprint_name=use_bp.name)

                        overlap = any(
                            pb.overlaps(existing) for existing in placed)
                        if not overlap:
                            placed.append(pb)
                            break

        return placed

    # ------------------------------------------------------------------
    # Road Planning
    # ------------------------------------------------------------------

    def _plan_roads(self, buildings: List[PlannedBuilding],
                    cx: int, cy: int, radius: int,
                    kind: str, zones: Dict
                    ) -> List[Tuple[int, int, int, int, str]]:
        """Plan roads connecting buildings to the center."""
        roads = []

        if kind == "hamlet":
            # Simple east-west path through hamlet
            roads.append((cx - radius, cy, cx + radius, cy, "dirt_track"))
            return roads

        # Determine road type based on settlement
        road_type = {
            "village": "gravel_road",
            "town": "road",
            "city": "cobblestone",
            "castle": "road",
        }.get(kind, "dirt_track")

        # Main cross-roads through center
        roads.append((cx - radius, cy, cx + radius, cy, road_type))
        roads.append((cx, cy - radius, cx, cy + radius, road_type))

        if kind in ("town", "city"):
            # Diagonal roads for larger settlements
            diag_len = int(radius * 0.7)
            roads.append((cx - diag_len, cy - diag_len,
                          cx + diag_len, cy + diag_len, "gravel_road"))
            roads.append((cx + diag_len, cy - diag_len,
                          cx - diag_len, cy + diag_len, "gravel_road"))

        if kind == "city":
            # Ring road at 60% radius
            ring_r = int(radius * 0.6)
            # Approximate ring road as 8 segments
            for i in range(8):
                a1 = (i / 8) * 2 * math.pi
                a2 = ((i + 1) / 8) * 2 * math.pi
                x1 = int(cx + math.cos(a1) * ring_r)
                y1 = int(cy + math.sin(a1) * ring_r)
                x2 = int(cx + math.cos(a2) * ring_r)
                y2 = int(cy + math.sin(a2) * ring_r)
                roads.append((x1, y1, x2, y2, road_type))

        # Connect each building's door to nearest road point
        for bld in buildings:
            door_x = bld.x + bld.w // 2
            door_y = bld.y + bld.h  # doors typically at bottom
            # Short path from door to the nearest main road axis
            if abs(door_x - cx) < abs(door_y - cy):
                # Connect to horizontal road
                roads.append((door_x, door_y, door_x, cy, "dirt_track"))
            else:
                # Connect to vertical road
                roads.append((door_x, door_y, cx, door_y, "dirt_track"))

        return roads

    # ------------------------------------------------------------------
    # Defense Planning
    # ------------------------------------------------------------------

    def _plan_defenses(self, kind: str, cx: int, cy: int, radius: int,
                        terrain: TerrainAnalysis,
                        buildings: List[PlannedBuilding],
                        rng: random.Random) -> Optional[DefensePlan]:
        """Plan walls, towers, and gates using terrain features.

        Border settlements get walls even at village size.
        Capital settlements get heavier defenses.
        """
        specialization = getattr(self, '_specialization', 'general')

        # Border and capital settlements always get walls
        if kind in ("hamlet", "village"):
            if specialization not in ("border", "capital"):
                return None

        defense = DefensePlan()

        # Wall radius — slightly inside the settlement radius
        if kind == "castle":
            wall_r = int(radius * 0.7)
        elif kind == "city":
            wall_r = int(radius * 0.85)
        else:
            wall_r = int(radius * 0.8)
        defense.wall_radius = wall_r

        # Compute wall points as a circle, but skip where natural
        # barriers exist (rivers, cliffs)
        for angle_deg in range(0, 360, 2):
            angle = math.radians(angle_deg)
            wx = int(cx + math.cos(angle) * wall_r)
            wy = int(cy + math.sin(angle) * wall_r)

            # Check if there's a natural barrier here
            # If river is on this side, skip wall (river acts as moat)
            skip = False
            if angle_deg < 45 or angle_deg > 315:
                # North-ish
                if terrain.has_river_north:
                    skip = True
            elif 45 <= angle_deg < 135:
                # East-ish
                if terrain.has_river_east:
                    skip = True
            elif 135 <= angle_deg < 225:
                # South-ish
                if terrain.has_river_south:
                    skip = True
            elif 225 <= angle_deg < 315:
                # West-ish
                if terrain.has_river_west:
                    skip = True

            if not skip:
                defense.wall_points.append((wx, wy))

        # Tower placement — at corners and regular intervals
        tower_interval = 8 if kind == "castle" else 12
        for angle_deg in range(0, 360, int(max(15, 360 // (
                2 * math.pi * wall_r // tower_interval + 1)))):
            angle = math.radians(angle_deg)
            tx = int(cx + math.cos(angle) * wall_r)
            ty = int(cy + math.sin(angle) * wall_r)
            defense.tower_positions.append((tx, ty))

        # Gate placement
        # Gates where main roads exit settlement
        gate_directions = []
        if terrain.road_directions:
            gate_directions = terrain.road_directions[:4]
        else:
            # Default: N/S for small, all four for large
            gate_directions = ["north", "south"]
            if kind in ("city", "town"):
                gate_directions.extend(["east", "west"])

        for direction in gate_directions:
            if direction == "north":
                gx, gy = cx, cy - wall_r
            elif direction == "south":
                gx, gy = cx, cy + wall_r
            elif direction == "east":
                gx, gy = cx + wall_r, cy
            elif direction == "west":
                gx, gy = cx - wall_r, cy
            else:
                continue

            # Skip gate if river is on this side (no wall there)
            river_on_side = False
            if direction == "north" and terrain.has_river_north:
                river_on_side = True
            elif direction == "south" and terrain.has_river_south:
                river_on_side = True
            elif direction == "east" and terrain.has_river_east:
                river_on_side = True
            elif direction == "west" and terrain.has_river_west:
                river_on_side = True

            if not river_on_side:
                defense.gate_positions.append((gx, gy, direction))

        # Ensure at least 2 gates
        if len(defense.gate_positions) < 2:
            for direction in ["north", "south", "east", "west"]:
                if any(g[2] == direction
                       for g in defense.gate_positions):
                    continue
                if direction == "north":
                    gx, gy = cx, cy - wall_r
                elif direction == "south":
                    gx, gy = cx, cy + wall_r
                elif direction == "east":
                    gx, gy = cx + wall_r, cy
                else:
                    gx, gy = cx - wall_r, cy
                defense.gate_positions.append((gx, gy, direction))
                if len(defense.gate_positions) >= 2:
                    break

        return defense

    # ------------------------------------------------------------------
    # Farm Planning
    # ------------------------------------------------------------------

    def _plan_farms(self, kind: str, cx: int, cy: int, radius: int,
                    terrain: TerrainAnalysis,
                    rng: random.Random,
                    specialization: str = "general"
                    ) -> List[Tuple[int, int, int]]:
        """Plan farm areas outside the settlement walls.

        Agricultural settlements get significantly more farms.
        Mining/port/swamp settlements get fewer.
        """
        farms = []

        farm_counts = {
            "hamlet": rng.randint(2, 4),
            "village": rng.randint(4, 8),
            "town": rng.randint(6, 12),
            "city": rng.randint(10, 18),
            "castle": rng.randint(2, 4),
        }
        num_farms = farm_counts.get(kind, 4)

        # Specialization adjustment
        if specialization == "agricultural":
            num_farms = int(num_farms * 2.0)  # double farms
        elif specialization in ("mining", "port", "swamp"):
            num_farms = max(1, int(num_farms * 0.4))  # fewer farms
        elif specialization in ("oasis",):
            num_farms = max(1, int(num_farms * 0.3))  # very few farms

        # Farm radius (size of each farm plot)
        farm_size = {
            "hamlet": 4,
            "village": 5,
            "town": 6,
            "city": 7,
            "castle": 4,
        }.get(kind, 5)

        # Preferred farming direction
        farm_dir = terrain.flat_area_direction or "south"
        dir_angles = {
            "north": -math.pi / 2,
            "south": math.pi / 2,
            "east": 0,
            "west": math.pi,
        }
        base_angle = dir_angles.get(farm_dir, math.pi / 2)

        for i in range(num_farms):
            angle = base_angle + rng.uniform(-math.pi / 2, math.pi / 2)
            dist = rng.uniform(radius * 0.85, radius * 1.3)
            fx = int(cx + math.cos(angle) * dist)
            fy = int(cy + math.sin(angle) * dist)
            farms.append((fx, fy, farm_size))

        return farms

    # ------------------------------------------------------------------
    # Well Placement
    # ------------------------------------------------------------------

    def _plan_wells(self, kind: str, cx: int, cy: int, radius: int,
                    terrain: TerrainAnalysis,
                    rng: random.Random,
                    specialization: str = "general"
                    ) -> List[Tuple[int, int]]:
        """Plan well positions. Every settlement needs water access.

        Oasis settlements get a critical well at center.
        Swamp settlements may have fewer (water everywhere).
        """
        wells = []

        num_wells = {
            "hamlet": 1,
            "village": 1,
            "town": 2,
            "city": 3,
            "castle": 1,
        }.get(kind, 1)

        # Specialization adjustment
        if specialization == "oasis":
            num_wells = max(num_wells, 3)  # water is critical
        elif specialization in ("port", "fishing", "swamp"):
            num_wells = max(1, num_wells - 1)  # water already nearby

        # First well near center (market square)
        wells.append((cx + rng.randint(-2, 2), cy + rng.randint(-2, 2)))

        # Additional wells spread through settlement
        for i in range(1, num_wells):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(radius * 0.3, radius * 0.6)
            wx = int(cx + math.cos(angle) * dist)
            wy = int(cy + math.sin(angle) * dist)
            wells.append((wx, wy))

        return wells
