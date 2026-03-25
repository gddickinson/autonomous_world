"""Specialization-specific building lists and terrain-aware building merging.

Maps settlement specializations to required/optional buildings that
supplement the generic ward-based building lists. Also provides a merge
function that combines specialization needs with ward assignments.
Includes biome-aware building style overrides for desert, tundra,
and tropical settlements.
"""

from typing import Dict, List, Set


# ================================================================
# SPECIALIZATION → BUILDING REQUIREMENTS
# ================================================================
# "required" buildings MUST appear in the settlement.
# "optional" buildings are placed when extra lots are available.
# These supplement (not replace) ward-based buildings from WARD_BUILDINGS.

SPECIALIZATION_BUILDINGS: Dict[str, Dict[str, List[str]]] = {
    "port": {
        "required": [
            "dock", "dock", "fish_market", "warehouse", "tavern",
            "shipwright",
        ],
        "optional": [
            "lighthouse", "customs_house", "net_loft", "chandlery",
        ],
    },
    "fishing": {
        "required": ["dock", "fish_market", "net_loft", "smokehouse"],
        "optional": ["boat_shed", "salt_store"],
    },
    "mining": {
        "required": ["mine_entrance", "smelter", "blacksmith", "warehouse"],
        "optional": ["assay_office", "tool_shop", "miner_barracks"],
    },
    "lumber": {
        "required": ["sawmill", "lumber_yard", "carpenter_workshop"],
        "optional": ["charcoal_kiln", "cooper_workshop", "woodcarver"],
    },
    "agricultural": {
        "required": ["granary", "mill", "barn", "barn"],
        "optional": ["bakery", "brewery", "cheese_press", "cider_press"],
    },
    "crossroads": {
        "required": ["tavern", "stable", "warehouse", "market_stall"],
        "optional": ["money_changer", "inn", "customs_post"],
    },
    "oasis": {
        "required": ["well", "tavern", "stable", "market_stall"],
        "optional": ["caravanserai", "cistern", "potter_workshop"],
    },
    "swamp": {
        "required": ["herbalist_hut", "workshop", "smokehouse"],
        "optional": ["peat_shed", "stilted_house", "healer_hut"],
    },
    "border": {
        "required": [
            "barracks", "guard_tower", "gatehouse", "armoury",
        ],
        "optional": ["blacksmith", "stable", "watchtower", "customs_post"],
    },
    "capital": {
        "required": [
            "castle_keep", "town_hall", "temple", "barracks",
            "library", "warehouse", "treasury",
        ],
        "optional": [
            "great_hall", "chapel", "guard_tower", "bakery",
            "stable", "market_stall", "market_stall",
        ],
    },
    "general": {
        "required": [],
        "optional": ["tavern", "well"],
    },
}

# Buildings that should be placed near water (river/coast)
WATERFRONT_BUILDINGS: Set[str] = {
    "dock", "fish_market", "shipwright", "lighthouse",
    "net_loft", "boat_shed", "customs_house", "chandlery",
    "smokehouse", "salt_store", "mill",
}

# ================================================================
# RACE-SPECIFIC SETTLEMENT CONFIG
# ================================================================
# Modifies settlement generation based on the dominant race.
# Each race config overrides defaults for terrain preference,
# building styles, wall types, and land clearing behavior.

RACE_SETTLEMENT_CONFIG: Dict[str, Dict] = {
    "elf": {
        "preferred_terrain": ["forest", "dense_forest"],
        "clear_land": False,  # elves don't clear forests
        "wall_type": None,  # no walls — use natural concealment
        "extra_buildings": ["tree_platform", "shrine", "herbalist_hut", "bowyer"],
        "replace_buildings": {"house": "tree_house", "barn": "garden_grove",
                              "blacksmith": "bowyer", "barracks": "ranger_post"},
        "farm_type": "garden",  # small gardens instead of fields
        "road_type": "forest_path",  # narrow paths instead of roads
    },
    "dwarf": {
        "preferred_terrain": ["mountain", "rocky_ground"],
        "clear_land": True,
        "wall_type": "stone",  # thick stone walls
        "extra_buildings": ["mine_entrance", "smelter", "stone_hall", "deep_forge"],
        "replace_buildings": {"house": "stone_house", "barn": "warehouse",
                              "cottage": "stone_cottage", "tavern": "mead_hall"},
        "farm_type": None,  # dwarves don't farm — they mine and trade
        "road_type": "stone_road",
    },
    "orc": {
        "preferred_terrain": ["rocky_ground", "grass"],
        "clear_land": True,
        "wall_type": "palisade",  # wooden palisade walls
        "extra_buildings": ["war_tent", "training_pit", "trophy_rack", "meat_smoker"],
        "replace_buildings": {"house": "hut", "cottage": "hut", "temple": "war_shrine",
                              "town_hall": "chieftain_hut", "chapel": "war_shrine"},
        "farm_type": None,  # orcs raid, don't farm
        "road_type": "dirt",
    },
    "goblin": {
        "preferred_terrain": ["swamp", "dense_forest"],
        "clear_land": False,
        "wall_type": "palisade",
        "extra_buildings": ["trap_workshop", "mushroom_cave", "scrap_heap"],
        "replace_buildings": {"house": "burrow", "cottage": "burrow",
                              "temple": "idol_pit", "town_hall": "boss_hut"},
        "farm_type": "mushroom",
        "road_type": "dirt",
    },
    "human": {
        "preferred_terrain": ["grass", "sand"],
        "clear_land": True,
        "wall_type": "stone",
        "extra_buildings": [],
        "replace_buildings": {},
        "farm_type": "field",
        "road_type": "cobblestone",
    },
}


# ================================================================
# BIOME-SPECIFIC BUILDING STYLES
# ================================================================
# Overrides applied based on the dominant biome at settlement center.
# Applied after race overrides (race takes priority for conflicts).

BIOME_BUILDING_CONFIG: Dict[str, Dict] = {
    "desert": {
        "replace_buildings": {
            "house": "sandstone_house",
            "cottage": "sandstone_house",
            "barn": "covered_storehouse",
            "tavern": "caravanserai",
            "market_stall": "bazaar_stall",
            "well": "desert_well",
        },
        "wall_type": "sandstone",
        "extra_buildings": ["cistern", "shade_canopy"],
        "remove_buildings": ["lumber_yard", "sawmill"],
        "road_type": "sand_path",
    },
    "tundra": {
        "replace_buildings": {
            "house": "stone_longhouse",
            "cottage": "stone_cottage",
            "barn": "insulated_storehouse",
            "market_stall": "covered_market",
            "tavern": "mead_hall",
        },
        "wall_type": "thick_stone",
        "extra_buildings": ["smokehouse", "fur_store"],
        "remove_buildings": ["market_stall"],  # no open-air markets
        "road_type": "stone_road",
    },
    "tropical": {
        "replace_buildings": {
            "house": "stilted_house",
            "cottage": "stilted_house",
            "barn": "raised_storehouse",
            "tavern": "open_air_tavern",
            "market_stall": "open_pavilion",
        },
        "wall_type": "bamboo_palisade",
        "extra_buildings": ["drying_rack", "rain_cistern"],
        "remove_buildings": [],
        "road_type": "boardwalk",
    },
    "volcanic": {
        "replace_buildings": {
            "house": "basalt_house",
            "cottage": "basalt_house",
            "well": "hot_spring_pool",
        },
        "wall_type": "basalt",
        "extra_buildings": ["forge", "obsidian_workshop"],
        "remove_buildings": [],
        "road_type": "stone_road",
    },
}

# Mapping from terrain tile types to biome category names
# Uses the terrain constants from settings
_BIOME_CATEGORY_MAP = {
    # Imported lazily to avoid circular import at module level
}


def get_biome_category(terrain_type: int) -> str:
    """Map a terrain tile type to a biome category for building style.

    Returns one of: 'desert', 'tundra', 'tropical', 'volcanic', 'default'.
    """
    from game.settings import (
        SAND, DUNE, TUNDRA, SNOW, JUNGLE, SWAMP, SCORCHED_EARTH,
        HOT_SPRING, GRASS, FOREST, DENSE_FOREST, ROCKY_GROUND,
        MOUNTAIN,
    )
    if terrain_type in (SAND, DUNE):
        return "desert"
    if terrain_type in (TUNDRA, SNOW):
        return "tundra"
    if terrain_type in (JUNGLE, SWAMP):
        return "tropical"
    if terrain_type in (SCORCHED_EARTH, HOT_SPRING):
        return "volcanic"
    return "default"


def get_biome_config(biome_category: str) -> Dict:
    """Get biome-specific building config for a biome category."""
    return BIOME_BUILDING_CONFIG.get(biome_category, {})


def apply_biome_buildings(buildings: List[str],
                          biome_category: str) -> List[str]:
    """Replace generic buildings with biome-specific equivalents.

    Applied after race buildings. Desert settlements get sandstone,
    tundra gets thick stone, tropical gets stilted buildings, etc.
    """
    cfg = BIOME_BUILDING_CONFIG.get(biome_category)
    if not cfg:
        return buildings

    replacements = cfg.get("replace_buildings", {})
    removals = set(cfg.get("remove_buildings", []))
    result = []
    for b in buildings:
        if b in removals:
            continue
        result.append(replacements.get(b, b))

    # Add biome-specific extras
    extras = cfg.get("extra_buildings", [])
    if extras:
        result.extend(extras[:2])

    return result


def get_race_config(race: str) -> Dict:
    """Get race-specific settlement config, defaulting to human.

    Handles compound races like 'Half-Elf' → elf, 'Half-Orc' → orc.
    """
    r = race.lower().replace("-", " ")
    if r in RACE_SETTLEMENT_CONFIG:
        return RACE_SETTLEMENT_CONFIG[r]
    # Check if any known race is a substring (e.g. "half-elf" contains "elf")
    for key in RACE_SETTLEMENT_CONFIG:
        if key in r:
            return RACE_SETTLEMENT_CONFIG[key]
    return RACE_SETTLEMENT_CONFIG["human"]


def apply_race_buildings(buildings: List[str], race: str) -> List[str]:
    """Replace generic buildings with race-specific equivalents."""
    cfg = get_race_config(race)
    replacements = cfg.get("replace_buildings", {})
    result = []
    for b in buildings:
        result.append(replacements.get(b, b))
    # Add race-specific extras at the end
    extras = cfg.get("extra_buildings", [])
    if extras:
        result.extend(extras[:2])  # add up to 2 extras
    return result

# Buildings that benefit from elevation (defensive/religious)
HILLTOP_BUILDINGS: Set[str] = {
    "temple", "chapel", "castle_keep", "guard_tower",
    "watchtower", "barracks", "lighthouse",
}

# Buildings that need flat terrain
FLAT_TERRAIN_BUILDINGS: Set[str] = {
    "market_stall", "granary", "mill", "barn", "warehouse",
    "lumber_yard", "stable", "inn", "tavern",
}


def get_settlement_buildings(
    specialization: str,
    kind: str,
    ward_types: Dict[int, str],
    ward_buildings_map: Dict[str, List[str]],
) -> Dict[int, List[str]]:
    """Get full building list per ward, incorporating specialization.

    Merges specialization-required buildings into the ward building
    lists. Required specialization buildings are distributed across
    appropriate wards; optional ones fill remaining capacity.

    Args:
        specialization: e.g. "port", "mining", "agricultural"
        kind: settlement kind — "hamlet", "village", "town", "city", "castle"
        ward_types: mapping ward_id → ward type string
        ward_buildings_map: WARD_BUILDINGS dict (ward_type → building list)

    Returns:
        Dict mapping ward_id → list of building kind strings.
    """
    spec_data = SPECIALIZATION_BUILDINGS.get(specialization, {})
    required = list(spec_data.get("required", []))
    optional = list(spec_data.get("optional", []))

    # Scale factor: bigger settlements get more optional buildings
    scale = {"hamlet": 0, "village": 1, "town": 2, "city": 3, "castle": 1}
    n_optional = min(len(optional), scale.get(kind, 1))
    extras = optional[:n_optional]

    # Start with ward-based buildings
    result: Dict[int, List[str]] = {}
    for wid, wtype in ward_types.items():
        base = list(ward_buildings_map.get(wtype, ["house"]))
        result[wid] = base

    # Distribute required specialization buildings into matching wards
    _distribute_to_wards(required, result, ward_types, priority=True)
    _distribute_to_wards(extras, result, ward_types, priority=False)

    return result


def _distribute_to_wards(
    buildings: List[str],
    ward_buildings: Dict[int, List[str]],
    ward_types: Dict[int, str],
    priority: bool,
) -> None:
    """Place buildings into the most appropriate wards.

    Waterfront buildings go to port wards, hilltop to temple/military,
    flat-terrain to market/commercial. Falls back to any ward if no
    ideal match exists.

    Args:
        buildings: list of building kind strings to place
        ward_buildings: mutable dict of ward_id → building list
        ward_types: ward_id → ward type
        priority: if True, insert at front of list (placed first)
    """
    # Categorise wards for matching
    water_wards = [w for w, t in ward_types.items() if t == "port"]
    high_wards = [w for w, t in ward_types.items()
                  if t in ("temple", "military")]
    flat_wards = [w for w, t in ward_types.items()
                  if t in ("market", "commercial", "storage")]
    all_wards = list(ward_types.keys())

    if not all_wards:
        return

    for bld in buildings:
        # Pick best ward for this building type
        if bld in WATERFRONT_BUILDINGS and water_wards:
            target = water_wards[0]
        elif bld in HILLTOP_BUILDINGS and high_wards:
            target = high_wards[0]
        elif bld in FLAT_TERRAIN_BUILDINGS and flat_wards:
            target = flat_wards[0]
        else:
            # Pick the ward with fewest buildings so far
            target = min(all_wards,
                         key=lambda w: len(ward_buildings.get(w, [])))

        if target not in ward_buildings:
            ward_buildings[target] = []

        if priority:
            ward_buildings[target].insert(0, bld)
        else:
            ward_buildings[target].append(bld)
