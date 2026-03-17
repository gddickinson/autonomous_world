"""Settlement specialization data — professions, buildings, and economy
for geographically-specialized settlements.

Each specialization defines:
- primary/secondary professions with weights
- required and bonus buildings
- economy description (what the settlement produces/trades)
- layout hints for the chunk generator
"""

from typing import Dict, List, Tuple


# ================================================================
# SPECIALIZATION PROFESSION POOLS
# ================================================================
# Format: list of (profession_name, weight) tuples.
# Primary professions have higher weights; secondary fill remaining slots.
# A "base" pool is always mixed in at low weight for variety.

SPECIALIZATION_PROFESSIONS: Dict[str, List[Tuple[str, int]]] = {
    "port": [
        ("Fisherman", 25), ("Sailor", 15), ("Shipbuilder", 10),
        ("Merchant", 15), ("Dock Worker", 10), ("Net Maker", 5),
        ("Innkeeper", 5), ("Lighthouse Keeper", 2),
        ("Cook", 3), ("Carpenter", 3), ("Guard", 4), ("Porter", 3),
    ],
    "fishing": [
        ("Fisherman", 30), ("Net Maker", 10), ("Sailor", 8),
        ("Carpenter", 5), ("Cook", 5), ("Dock Worker", 5),
        ("Farmer", 5), ("Laborer", 5),
    ],
    "mining": [
        ("Miner", 25), ("Prospector", 10), ("Blacksmith", 10),
        ("Mason", 8), ("Smelter", 8), ("Carpenter", 5),
        ("Guard", 5), ("Laborer", 5), ("Cook", 3),
        ("Porter", 3), ("Innkeeper", 2),
    ],
    "lumber": [
        ("Woodcutter", 25), ("Carpenter", 15), ("Hunter", 10),
        ("Charcoal Burner", 8), ("Cooper", 5), ("Wheelwright", 5),
        ("Farmer", 5), ("Guard", 3), ("Cook", 3),
        ("Laborer", 5),
    ],
    "agricultural": [
        ("Farmer", 25), ("Shepherd", 10), ("Baker", 8),
        ("Miller", 8), ("Brewer", 5), ("Weaver", 5),
        ("Beekeeper", 3), ("Carpenter", 3), ("Guard", 3),
        ("Innkeeper", 2), ("Laborer", 5),
    ],
    "crossroads": [
        ("Merchant", 20), ("Innkeeper", 10), ("Guard", 10),
        ("Banker", 5), ("Stablemaster", 5), ("Cook", 5),
        ("Barber", 3), ("Shop Assistant", 5), ("Porter", 5),
        ("Bard", 3), ("Farmer", 3), ("Carpenter", 2),
        ("Diplomat", 2), ("Cartographer", 2),
    ],
    "oasis": [
        ("Water Carrier", 15), ("Caravaneer", 12), ("Merchant", 12),
        ("Innkeeper", 8), ("Guard", 8), ("Farmer", 5),
        ("Cook", 5), ("Shepherd", 5), ("Potter", 3),
        ("Weaver", 3), ("Laborer", 5),
    ],
    "swamp": [
        ("Herbalist", 20), ("Fisherman", 15), ("Peat Cutter", 12),
        ("Healer", 8), ("Alchemist", 5), ("Hunter", 5),
        ("Farmer", 5), ("Carpenter", 3), ("Laborer", 5),
    ],
    "border": [
        ("Guard", 20), ("Soldier", 15), ("Captain", 5),
        ("Diplomat", 5), ("Spy", 3), ("Merchant", 5),
        ("Blacksmith", 5), ("Innkeeper", 5), ("Cook", 3),
        ("Farmer", 3), ("Mason", 3), ("Laborer", 5),
    ],
    "capital": [
        ("Guard", 8), ("Captain", 3), ("Merchant", 8),
        ("Banker", 3), ("Diplomat", 3), ("Advisor", 3),
        ("Steward", 2), ("Tax Collector", 2), ("Scribe", 3),
        ("Scholar", 3), ("Bard", 2), ("Innkeeper", 3),
        ("Blacksmith", 2), ("Armourer", 2), ("Baker", 2),
        ("Cook", 2), ("Servant", 3), ("Healer", 2),
        ("Alchemist", 2), ("Jeweler", 2), ("Barber", 2),
        ("Shop Assistant", 3), ("Farmer", 2), ("Carpenter", 2),
        ("Mason", 2), ("Weaver", 2), ("Porter", 2),
    ],
    "general": [
        ("Farmer", 5), ("Guard", 3), ("Merchant", 2),
        ("Carpenter", 2), ("Blacksmith", 2), ("Innkeeper", 2),
        ("Baker", 2), ("Healer", 1), ("Hunter", 2),
        ("Laborer", 3),
    ],
}


# ================================================================
# SPECIALIZATION BUILDING LISTS
# ================================================================
# Keys match BLUEPRINT_BY_KIND in buildings.py.
# "required" buildings are always placed first; "bonus" are added
# if there is room. "residential" overrides the default house pool.

SPECIALIZATION_BUILDINGS: Dict[str, Dict[str, list]] = {
    "port": {
        "required": ["warehouse", "tavern", "shop"],
        "bonus": ["stable", "guard_tower", "chapel"],
        "residential": ["house", "townhouse", "cottage"],
    },
    "fishing": {
        "required": ["tavern"],
        "bonus": ["barn", "workshop"],
        "residential": ["cottage", "farmhouse", "hovel", "shack"],
    },
    "mining": {
        "required": ["blacksmith", "workshop", "warehouse"],
        "bonus": ["tavern", "guard_tower", "barn"],
        "residential": ["cottage", "hovel", "shack", "house"],
    },
    "lumber": {
        "required": ["workshop", "barn"],
        "bonus": ["tavern", "stable", "granary"],
        "residential": ["cottage", "farmhouse", "hovel", "shack"],
    },
    "agricultural": {
        "required": ["granary", "barn", "mill"],
        "bonus": ["tavern", "bakery", "stable", "well"],
        "residential": ["farmhouse", "cottage", "hovel"],
    },
    "crossroads": {
        "required": ["tavern", "stable", "warehouse", "shop"],
        "bonus": ["guard_tower", "chapel", "bakery", "library"],
        "residential": ["house", "townhouse", "cottage"],
    },
    "oasis": {
        "required": ["well", "tavern", "stable"],
        "bonus": ["shop", "granary", "workshop"],
        "residential": ["cottage", "hovel", "shack"],
    },
    "swamp": {
        "required": ["workshop"],
        "bonus": ["tavern", "well"],
        "residential": ["hovel", "shack", "cottage"],
    },
    "border": {
        "required": ["barracks", "guard_tower", "gatehouse"],
        "bonus": ["blacksmith", "armoury", "tavern", "stable"],
        "residential": ["house", "cottage", "hovel"],
    },
    "capital": {
        "required": ["castle_keep", "town_hall", "temple", "barracks",
                     "library", "warehouse", "treasury"],
        "bonus": ["tavern", "blacksmith", "bakery", "stable",
                  "great_hall", "chapel", "shop", "guard_tower"],
        "residential": ["mansion", "townhouse", "house", "cottage"],
    },
    "general": {
        "required": [],
        "bonus": ["tavern", "well"],
        "residential": ["cottage", "house", "hovel"],
    },
}


# ================================================================
# SPECIALIZATION ECONOMY
# ================================================================
# What each specialization produces, imports, and exports.

SPECIALIZATION_ECONOMY: Dict[str, Dict[str, list]] = {
    "port": {
        "produces": ["fish", "salt", "rope", "ships"],
        "imports": ["grain", "timber", "ore", "cloth"],
        "exports": ["fish", "salt", "trade_goods", "ships"],
    },
    "fishing": {
        "produces": ["fish", "salt"],
        "imports": ["grain", "tools"],
        "exports": ["fish"],
    },
    "mining": {
        "produces": ["ore", "gems", "stone", "metal_ingots"],
        "imports": ["food", "timber", "cloth"],
        "exports": ["ore", "gems", "stone", "metal_ingots"],
    },
    "lumber": {
        "produces": ["timber", "charcoal", "game_meat", "planks"],
        "imports": ["grain", "metal_tools", "cloth"],
        "exports": ["timber", "charcoal", "planks"],
    },
    "agricultural": {
        "produces": ["grain", "livestock", "dairy", "bread", "wool"],
        "imports": ["metal_tools", "salt", "cloth"],
        "exports": ["grain", "livestock", "dairy", "bread", "wool"],
    },
    "crossroads": {
        "produces": ["trade_services", "lodging"],
        "imports": ["everything"],
        "exports": ["trade_services"],
    },
    "oasis": {
        "produces": ["water", "dates", "salt"],
        "imports": ["timber", "metal_tools", "cloth"],
        "exports": ["salt", "dates", "trade_goods"],
    },
    "swamp": {
        "produces": ["herbs", "peat", "medicine", "fish"],
        "imports": ["grain", "timber", "metal_tools"],
        "exports": ["herbs", "peat", "medicine"],
    },
    "border": {
        "produces": ["military_services", "customs_revenue"],
        "imports": ["food", "weapons", "armor"],
        "exports": ["security", "customs_goods"],
    },
    "capital": {
        "produces": ["governance", "culture", "luxury_goods"],
        "imports": ["everything"],
        "exports": ["laws", "culture", "luxury_goods"],
    },
    "general": {
        "produces": ["mixed"],
        "imports": ["mixed"],
        "exports": ["mixed"],
    },
}


# ================================================================
# SPECIALIZATION LAYOUT HINTS
# ================================================================
# Used by the chunk generator to adjust settlement layout.

SPECIALIZATION_LAYOUT: Dict[str, Dict] = {
    "port": {
        "face_water": True,        # orient buildings toward water
        "dock_tiles": True,        # place BRIDGE tiles extending into water
        "clear_waterfront": True,  # keep area near water clear for docks
    },
    "fishing": {
        "face_water": True,
        "dock_tiles": True,
        "clear_waterfront": True,
    },
    "mining": {
        "use_built_wall": True,    # stone buildings (BUILT_WALL)
        "mine_entrances": True,    # STAIRS_DOWN at mountain edges
        "terraced": True,          # follow terrain contours
    },
    "lumber": {
        "forest_edge": True,       # place buildings at forest boundary
        "lumber_yard": True,       # clear area with TREE_STUMP tiles
    },
    "agricultural": {
        "farm_fields": True,       # FARMLAND/WHEAT_FIELD radiating outward
        "livestock_pens": True,    # fenced areas with STABLE_FLOOR
    },
    "crossroads": {
        "large_market": True,      # bigger central market square
        "multiple_roads": True,    # roads converge at center
    },
    "oasis": {
        "well_center": True,       # WELL at absolute center
        "thick_walls": True,       # double-thick building walls (BUILT_WALL)
        "covered_market": True,    # roofed market area
    },
    "swamp": {
        "raised_buildings": True,  # use BUILT_FLOOR instead of FLOOR
        "spread_out": True,        # more spacing between buildings
    },
    "border": {
        "heavy_walls": True,       # BUILT_WALL perimeter
        "watchtowers": True,       # guard towers at edges
        "gatehouse": True,         # gatehouse on main road
    },
    "capital": {
        "palace_center": True,     # castle keep at center
        "multiple_markets": True,  # several market squares
        "districts": True,         # organized by function
    },
    "general": {},
}
