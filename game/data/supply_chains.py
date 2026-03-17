"""
Supply Chain Data -- ensures every game item has a production source.

Three categories:
1. RAW_MATERIAL_SOURCES  -- gathered from the world (tiles, creatures, etc.)
2. SUPPLY_CHAINS         -- crafted/processed items with crafter, materials, workplace
3. FOREIGN_TRADE_GOODS   -- luxury goods that arrive via foreign caravans

Every item in game/core/items.py ITEMS dict must appear in exactly one of:
  - RAW_MATERIAL_SOURCES  (gathered / hunted / farmed)
  - SUPPLY_CHAINS         (crafted by an NPC profession)
  - FOREIGN_TRADE_GOODS   (imported by caravan)
  - QUEST_ITEMS           (scripted drops, not produced)

Gold enters the economy through:
  1. Prospectors panning gold_ore at GEM_DEPOSIT / river tiles
  2. Blacksmiths smelting Gold Nugget -> Gold Bar -> Gold Coins
  3. Foreign merchants paying gold for exported local goods
  4. Service professions (Innkeeper, Barber, Banker) generating gold from customers
"""

from game.settings import (
    FOREST, DENSE_FOREST, MOUNTAIN, WATER, FARMLAND,
    ORE_VEIN, HERB_PATCH, BERRY_BUSH, CLAY_PIT, MUSHROOMS,
    WHEAT_FIELD, VEGETABLE_PLOT, FRUIT_TREE, FLOWER_BED,
    GEM_DEPOSIT, COPPER_VEIN, FLAX_FIELD, BEEHIVE, SALT_FLAT,
    SHALLOW_WATER, ROCKY_GROUND, SAND,
    TABLE, ANVIL, FORGE_FIRE, FIREPLACE, BARREL, BOOKSHELF,
    GRASS, TREE_STUMP,
)


# ================================================================
# RAW MATERIAL SOURCES -- how each raw resource enters the world
# ================================================================

RAW_MATERIAL_SOURCES = {
    # --- Gathered from terrain ---
    "Wood": {
        "gatherer": "Woodcutter",
        "source_tiles": [FOREST, DENSE_FOREST],
        "action": "chopping",
        "leaves_tile": TREE_STUMP,
        "yield_range": (1, 3),
        "skill": "woodcraft",
        "tool": "Axe",
    },
    "Stone": {
        "gatherer": "Miner",
        "source_tiles": [MOUNTAIN],
        "action": "quarrying",
        "leaves_tile": ROCKY_GROUND,
        "yield_range": (1, 2),
        "skill": "mining",
        "tool": "Pickaxe",
    },
    "Iron Ore": {
        "gatherer": "Miner",
        "source_tiles": [ORE_VEIN],
        "action": "mining",
        "leaves_tile": ROCKY_GROUND,
        "yield_range": (1, 2),
        "skill": "mining",
        "tool": "Pickaxe",
    },
    "Copper Ore": {
        "gatherer": "Miner",
        "source_tiles": [COPPER_VEIN],
        "action": "mining",
        "leaves_tile": ROCKY_GROUND,
        "yield_range": (1, 3),
        "skill": "mining",
        "tool": "Pickaxe",
    },
    "Gold Nugget": {
        "gatherer": "Prospector",
        "source_tiles": [GEM_DEPOSIT, SHALLOW_WATER],
        "action": "panning",
        "leaves_tile": None,  # doesn't destroy tile
        "yield_range": (0, 1),
        "skill": "mining",
        "tool": "Pickaxe",
    },
    "Herbs": {
        "gatherer": "Herbalist",
        "source_tiles": [HERB_PATCH, BERRY_BUSH],
        "action": "gathering",
        "leaves_tile": GRASS,
        "yield_range": (1, 3),
        "skill": "herbalism",
    },
    "Medicinal Herbs": {
        "gatherer": "Herbalist",
        "source_tiles": [HERB_PATCH],
        "action": "gathering",
        "leaves_tile": GRASS,
        "yield_range": (1, 2),
        "skill": "herbalism",
        "note": "Specialized herbs for treating disease and infection.",
    },
    "Berries": {
        "gatherer": "Herbalist",
        "source_tiles": [BERRY_BUSH],
        "action": "picking",
        "leaves_tile": None,  # bush stays
        "yield_range": (2, 5),
        "skill": "herbalism",
    },
    "Mushrooms": {
        "gatherer": "Herbalist",
        "source_tiles": [MUSHROOMS],
        "action": "picking",
        "leaves_tile": GRASS,
        "yield_range": (1, 3),
        "skill": "herbalism",
    },
    "Flowers": {
        "gatherer": "Herbalist",
        "source_tiles": [FLOWER_BED],
        "action": "picking",
        "leaves_tile": None,  # flower bed stays
        "yield_range": (1, 2),
        "skill": "herbalism",
    },
    "Clay": {
        "gatherer": "Potter",
        "source_tiles": [CLAY_PIT],
        "action": "digging",
        "leaves_tile": GRASS,
        "yield_range": (1, 3),
    },
    "Sand": {
        "gatherer": "Potter",
        "source_tiles": [SAND],
        "action": "collecting",
        "leaves_tile": None,  # sand stays (abundant)
        "yield_range": (1, 3),
    },
    "Flax": {
        "gatherer": "Farmer",
        "source_tiles": [FLAX_FIELD],
        "action": "harvesting",
        "leaves_tile": GRASS,
        "yield_range": (2, 4),
        "skill": "farming",
        "tool": "Hoe",
    },
    "Wheat": {
        "gatherer": "Farmer",
        "source_tiles": [WHEAT_FIELD, FARMLAND],
        "action": "harvesting",
        "leaves_tile": FARMLAND,
        "yield_range": (1, 5),
        "skill": "farming",
        "tool": "Hoe",
    },
    "Vegetables": {
        "gatherer": "Farmer",
        "source_tiles": [VEGETABLE_PLOT],
        "action": "harvesting",
        "leaves_tile": FARMLAND,
        "yield_range": (1, 3),
        "skill": "farming",
        "tool": "Hoe",
    },
    "Apple": {
        "gatherer": "Farmer",
        "source_tiles": [FRUIT_TREE],
        "action": "picking",
        "leaves_tile": None,  # tree stays
        "yield_range": (1, 3),
    },
    "Honey": {
        "gatherer": "Beekeeper",
        "source_tiles": [BEEHIVE],
        "action": "collecting",
        "leaves_tile": None,  # hive stays
        "yield_range": (1, 2),
        "skill": "beekeeping",
    },
    "Beeswax": {
        "gatherer": "Beekeeper",
        "source_tiles": [BEEHIVE],
        "action": "collecting",
        "leaves_tile": None,
        "yield_range": (0, 1),
        "skill": "beekeeping",
    },
    "Salt": {
        "gatherer": "Laborer",
        "source_tiles": [SALT_FLAT],
        "action": "collecting",
        "leaves_tile": None,  # salt flat stays
        "yield_range": (1, 3),
    },
    "Resin": {
        "gatherer": "Woodcutter",
        "source_tiles": [DENSE_FOREST],
        "action": "tapping",
        "leaves_tile": None,  # tree stays
        "yield_range": (0, 1),
        "skill": "woodcraft",
    },
    "Seeds": {
        "gatherer": "Farmer",
        "source_tiles": [WHEAT_FIELD],
        "action": "harvesting",
        "leaves_tile": None,
        "yield_range": (1, 3),
        "skill": "farming",
    },

    # --- Gems (mined) ---
    "Raw Ruby": {
        "gatherer": "Prospector",
        "source_tiles": [GEM_DEPOSIT],
        "action": "mining",
        "leaves_tile": ROCKY_GROUND,
        "yield_range": (0, 1),
        "skill": "mining",
        "tool": "Pickaxe",
    },
    "Raw Sapphire": {
        "gatherer": "Prospector",
        "source_tiles": [GEM_DEPOSIT],
        "action": "mining",
        "leaves_tile": ROCKY_GROUND,
        "yield_range": (0, 1),
        "skill": "mining",
        "tool": "Pickaxe",
    },
    "Raw Emerald": {
        "gatherer": "Prospector",
        "source_tiles": [GEM_DEPOSIT],
        "action": "mining",
        "leaves_tile": ROCKY_GROUND,
        "yield_range": (0, 1),
        "skill": "mining",
        "tool": "Pickaxe",
    },
    "Raw Diamond": {
        "gatherer": "Prospector",
        "source_tiles": [GEM_DEPOSIT],
        "action": "mining",
        "leaves_tile": ROCKY_GROUND,
        "yield_range": (0, 1),
        "skill": "mining",
        "tool": "Pickaxe",
    },

    # --- Hunted / Animal products ---
    "Raw Meat": {
        "source": "hunting",
        "gatherer": "Hunter",
        "from_creatures": ["deer", "elk", "boar", "cow", "pig", "sheep",
                           "rabbit", "chicken", "wild_boar", "bear"],
        "yield_range": (1, 3),
    },
    "Wolf Pelt": {
        "source": "hunting",
        "gatherer": "Hunter",
        "from_creatures": ["wolf", "dire_wolf", "bear"],
        "yield_range": (1, 1),
    },
    "Feathers": {
        "source": "hunting",
        "gatherer": "Hunter",
        "from_creatures": ["chicken", "hawk", "eagle", "crow", "owl"],
        "yield_range": (1, 3),
    },
    "Wool": {
        "source": "shepherding",
        "gatherer": "Shepherd",
        "from_creatures": ["sheep"],
        "yield_range": (1, 2),
    },
    "Milk": {
        "source": "farming",
        "gatherer": "Farmer",
        "from_creatures": ["cow", "goat"],
        "yield_range": (1, 2),
    },
    "Eggs": {
        "source": "farming",
        "gatherer": "Farmer",
        "from_creatures": ["chicken"],
        "yield_range": (1, 3),
    },

    # --- Fishing ---
    "Fish": {
        "source": "fishing",
        "gatherer": "Fisherman",
        "source_tiles": [WATER, SHALLOW_WATER],
        "yield_range": (1, 3),
        "skill": "fishing",
        "tool": "Fishing Rod",
    },
}


# ================================================================
# SUPPLY CHAINS -- every crafted/processed item
# ================================================================
# Each entry maps an item name to its production data.
# "recipe" key references the RECIPES dict in crafting.py for
#  ingredient details; this dict adds the NPC production metadata.

SUPPLY_CHAINS = {
    # ======== SMELTING (Blacksmith at forge) ========
    "Iron Ingot": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 1,
    },
    "Copper Ingot": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 1,
    },
    "Bronze Ingot": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 2,
    },
    "Steel Ingot": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 3,
    },
    "Gold Bar": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 2,
    },

    # ======== WEAPONS (Blacksmith at forge) ========
    "Wooden Sword": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 1,
    },
    "Iron Sword": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 2,
    },
    "Steel Sword": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 4,
    },
    "Hunting Bow": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 2,
    },
    "Staff": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 1,
    },
    "Arrows": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 1,
    },

    # ======== ARMOR (Armourer / Blacksmith at forge) ========
    "Leather Armor": {
        "crafter": "Tanner",
        "workstation": "workshop",
        "skill": "leatherwork",
        "skill_level": 2,
    },
    "Chain Mail": {
        "crafter": "Armourer",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 3,
    },
    "Iron Armor": {
        "crafter": "Armourer",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 4,
    },
    "Plate Armor": {
        "crafter": "Armourer",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 6,
    },
    "Bronze Shield": {
        "crafter": "Armourer",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 2,
    },
    "Iron Shield": {
        "crafter": "Armourer",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 3,
    },
    "Wooden Shield": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 2,
    },

    # ======== LEATHER GOODS (Tanner at workshop) ========
    "Leather": {
        "crafter": "Tanner",
        "workstation": "workshop",
        "skill": "leatherwork",
        "skill_level": 1,
    },
    "Tanned Hide": {
        "crafter": "Tanner",
        "workstation": "tannery",
        "skill": "leatherwork",
        "skill_level": 1,
    },
    "Boots": {
        "crafter": "Tanner",
        "workstation": "workshop",
        "skill": "leatherwork",
        "skill_level": 1,
    },
    "Belt": {
        "crafter": "Tanner",
        "workstation": "workshop",
        "skill": "leatherwork",
        "skill_level": 1,
    },
    "Leather Gloves": {
        "crafter": "Tanner",
        "workstation": "workshop",
        "skill": "leatherwork",
        "skill_level": 1,
    },
    "Satchel": {
        "crafter": "Tanner",
        "workstation": "workshop",
        "skill": "leatherwork",
        "skill_level": 2,
    },
    "Saddle": {
        "crafter": "Tanner",
        "workstation": "workshop",
        "skill": "leatherwork",
        "skill_level": 3,
    },
    "Waterskin": {
        "crafter": "Tanner",
        "workstation": "workshop",
        "skill": "leatherwork",
        "skill_level": 1,
    },
    "Quiver": {
        "crafter": "Tanner",
        "workstation": "workshop",
        "skill": "leatherwork",
        "skill_level": 1,
    },

    # ======== WOODWORKING (Carpenter at workshop) ========
    "Planks": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 1,
    },
    "Barrel": {
        "crafter": "Cooper",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 2,
    },
    "Crate": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 1,
    },
    "Cart": {
        "crafter": "Wheelwright",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 4,
    },
    "Torch": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 1,
    },
    "Fishing Rod": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 1,
    },
    "Training Dummy": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 1,
    },
    "Bucket": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 1,
    },
    "Churn": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 1,
    },
    "Trough": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 1,
    },
    "Musical Instrument": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 3,
    },
    "Battering Ram": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 5,
    },
    "Boat Hull": {
        "crafter": "Shipbuilder",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 5,
    },

    # ======== SMITHING TOOLS & HARDWARE (Blacksmith at forge) ========
    "Pickaxe": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 2,
    },
    "Axe": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 2,
    },
    "Hammer": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 1,
    },
    "Hoe": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 1,
    },
    "Nails": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 1,
    },
    "Arrowheads": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 1,
    },
    "Iron Horseshoes": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 1,
    },
    "Lantern": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 2,
    },
    "Lockpick": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 2,
    },
    "Iron Chain": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 2,
    },
    "Smith's Tools": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 3,
    },
    "Caltrops": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 2,
    },
    "Strongbox": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 3,
    },
    "Cage": {
        "crafter": "Blacksmith",
        "workstation": "workshop",
        "skill": "smithing",
        "skill_level": 2,
    },
    "Thieves' Tools": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 3,
    },
    "Navigator's Tools": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 3,
    },
    "Grappling Hook": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 2,
    },
    "Siege Tools": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 5,
    },

    # ======== TEXTILES (Weaver at loom) ========
    "Linen": {
        "crafter": "Weaver",
        "workstation": "loom",
        "skill": "weaving",
        "skill_level": 1,
    },
    "Rope": {
        "crafter": "Weaver",
        "workstation": "loom",
        "skill": "weaving",
        "skill_level": 1,
    },
    "Bandage": {
        "crafter": "Weaver",
        "workstation": "loom",
        "skill": "weaving",
        "skill_level": 1,
    },
    "Cloak": {
        "crafter": "Weaver",
        "workstation": "loom",
        "skill": "weaving",
        "skill_level": 2,
    },
    "Robe": {
        "crafter": "Weaver",
        "workstation": "loom",
        "skill": "weaving",
        "skill_level": 3,
    },
    "Tent": {
        "crafter": "Weaver",
        "workstation": "loom",
        "skill": "weaving",
        "skill_level": 3,
    },
    "Net": {
        "crafter": "Weaver",
        "workstation": "workshop",
        "skill": "weaving",
        "skill_level": 1,
    },
    "Dyed Cloth": {
        "crafter": "Weaver",
        "workstation": "dye_house",
        "skill": "weaving",
        "skill_level": 2,
    },
    "Wool Cloth": {
        "crafter": "Weaver",
        "workstation": "loom",
        "skill": "weaving",
        "skill_level": 1,
    },

    # ======== COOKING (Baker / Cook at kitchen/fireplace) ========
    "Bread": {
        "crafter": "Baker",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 1,
    },
    "Flour": {
        "crafter": "Baker",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 1,
    },
    "Cooked Meat": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 1,
    },
    "Vegetable Stew": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 2,
    },
    "Berry Pie": {
        "crafter": "Baker",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 2,
    },
    "Mushroom Soup": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 1,
    },
    "Meat Pie": {
        "crafter": "Baker",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 2,
    },
    "Honey Cake": {
        "crafter": "Baker",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 2,
    },
    "Salted Fish": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 1,
    },
    "Trail Rations": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 2,
    },
    "Feast Platter": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 5,
    },
    "Omelette": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 1,
    },
    "Cheese": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 2,
    },
    "Butter": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 1,
    },
    "Cheese Wheel": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 3,
    },
    "Bacon": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 1,
    },
    "Sausage": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 2,
    },
    "Smoked Fish": {
        "crafter": "Cook",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 2,
    },

    # ======== BREWING (Brewer at brewery) ========
    "Ale": {
        "crafter": "Brewer",
        "workstation": "brewery",
        "skill": "brewing",
        "skill_level": 1,
    },
    "Mead": {
        "crafter": "Brewer",
        "workstation": "brewery",
        "skill": "brewing",
        "skill_level": 2,
    },
    "Wine": {
        "crafter": "Brewer",
        "workstation": "brewery",
        "skill": "brewing",
        "skill_level": 3,
    },
    "Dwarven Stout": {
        "crafter": "Brewer",
        "workstation": "brewery",
        "skill": "brewing",
        "skill_level": 4,
    },
    "Elven Cordial": {
        "crafter": "Brewer",
        "workstation": "brewery",
        "skill": "brewing",
        "skill_level": 5,
    },
    "Healing Tonic": {
        "crafter": "Brewer",
        "workstation": "brewery",
        "skill": "brewing",
        "skill_level": 2,
    },
    "Water Flask": {
        "crafter": "Potter",
        "workstation": "workshop",
        "skill": "pottery",
        "skill_level": 1,
    },

    # ======== ALCHEMY (Alchemist at alchemy bench) ========
    "Health Potion": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 2,
    },
    "Greater Health Potion": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 4,
    },
    "Antidote": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 1,
    },
    "Fire Oil": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 2,
    },
    "Poison Vial": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 3,
    },
    "Strength Elixir": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 4,
    },
    "Speed Elixir": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 4,
    },
    "Invisibility Oil": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 6,
    },
    "Healing Salve": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 1,
    },
    "Smelling Salts": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 1,
    },
    "Ink": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 1,
    },

    # ======== JEWELRY (Jeweler) ========
    "Ruby": {
        "crafter": "Jeweler",
        "workstation": "jeweler",
        "skill": "jeweling",
        "skill_level": 2,
    },
    "Sapphire": {
        "crafter": "Jeweler",
        "workstation": "jeweler",
        "skill": "jeweling",
        "skill_level": 2,
    },
    "Emerald": {
        "crafter": "Jeweler",
        "workstation": "jeweler",
        "skill": "jeweling",
        "skill_level": 3,
    },
    "Diamond": {
        "crafter": "Jeweler",
        "workstation": "jeweler",
        "skill": "jeweling",
        "skill_level": 4,
    },
    "Gold Ring": {
        "crafter": "Jeweler",
        "workstation": "jeweler",
        "skill": "jeweling",
        "skill_level": 2,
    },
    "Ruby Ring": {
        "crafter": "Jeweler",
        "workstation": "jeweler",
        "skill": "jeweling",
        "skill_level": 3,
    },
    "Sapphire Amulet": {
        "crafter": "Jeweler",
        "workstation": "jeweler",
        "skill": "jeweling",
        "skill_level": 4,
    },
    "Emerald Pendant": {
        "crafter": "Jeweler",
        "workstation": "jeweler",
        "skill": "jeweling",
        "skill_level": 4,
    },
    "Diamond Crown": {
        "crafter": "Jeweler",
        "workstation": "jeweler",
        "skill": "jeweling",
        "skill_level": 6,
    },
    "Enchanted Ring": {
        "crafter": "Jeweler",
        "workstation": "jeweler",
        "skill": "jeweling",
        "skill_level": 5,
    },

    # ======== POTTERY & GLASS (Potter / Glassblower) ========
    "Pot": {
        "crafter": "Potter",
        "workstation": "workshop",
        "skill": "pottery",
        "skill_level": 1,
    },
    "Vase": {
        "crafter": "Potter",
        "workstation": "workshop",
        "skill": "pottery",
        "skill_level": 2,
    },
    "Pottery Jar": {
        "crafter": "Potter",
        "workstation": "pottery",
        "skill": "pottery",
        "skill_level": 1,
    },
    "Glass Pane": {
        "crafter": "Potter",
        "workstation": "forge",
        "skill": "pottery",
        "skill_level": 2,
    },
    "Bottle": {
        "crafter": "Potter",
        "workstation": "forge",
        "skill": "pottery",
        "skill_level": 2,
    },
    "Stained Glass": {
        "crafter": "Potter",
        "workstation": "glassworks",
        "skill": "pottery",
        "skill_level": 4,
    },

    # ======== CHANDLERY (candles, wax) ========
    "Candle": {
        "crafter": "Beekeeper",
        "workstation": "workshop",
        "skill": "beekeeping",
        "skill_level": 1,
    },
    "Sealing Wax": {
        "crafter": "Beekeeper",
        "workstation": "workshop",
        "skill": "beekeeping",
        "skill_level": 1,
    },
    "Wax Seal": {
        "crafter": "Scribe",
        "workstation": "workshop",
        "skill": "writing",
        "skill_level": 1,
    },

    # ======== TRAPPING ========
    "Snare Trap": {
        "crafter": "Hunter",
        "workstation": "workshop",
        "skill": "trapping",
        "skill_level": 1,
    },
    "Trap": {
        "crafter": "Blacksmith",
        "workstation": "workshop",
        "skill": "smithing",
        "skill_level": 2,
    },

    # ======== HERBALISM & MEDICAL ========
    "Herbalism Kit": {
        "crafter": "Herbalist",
        "workstation": "workshop",
        "skill": "herbalism",
        "skill_level": 2,
    },
    "Healer's Kit": {
        "crafter": "Healer",
        "workstation": "workshop",
        "skill": "herbalism",
        "skill_level": 2,
    },
    "Herbal Poultice": {
        "crafter": "Healer",
        "workstation": "workshop",
        "skill": "herbalism",
        "skill_level": 1,
    },
    "Medicine": {
        "crafter": "Healer",
        "materials": [("Medicinal Herbs", 2)],
        "workstation": "workshop",
        "skill": "herbalism",
        "skill_level": 3,
        "note": "Prepared medicine for treating diseases and infections.",
    },
    "Holy Water": {
        "crafter": "Healer",
        "workstation": "enchanter",
        "skill": "herbalism",
        "skill_level": 2,
    },

    # ======== ENCHANTING (Scholar / Wizard) ========
    "Scroll of Healing": {
        "crafter": "Scholar",
        "workstation": "enchanter",
        "skill": "enchanting",
        "skill_level": 2,
    },
    "Scroll of Fire": {
        "crafter": "Scholar",
        "workstation": "enchanter",
        "skill": "enchanting",
        "skill_level": 3,
    },
    "Scroll of Ward": {
        "crafter": "Scholar",
        "workstation": "enchanter",
        "skill": "enchanting",
        "skill_level": 3,
    },
    "Wand of Sparks": {
        "crafter": "Scholar",
        "workstation": "enchanter",
        "skill": "enchanting",
        "skill_level": 5,
    },
    "Enchanted Sword": {
        "crafter": "Scholar",
        "workstation": "enchanter",
        "skill": "enchanting",
        "skill_level": 6,
    },
    "Enchanted Staff": {
        "crafter": "Scholar",
        "workstation": "enchanter",
        "skill": "enchanting",
        "skill_level": 5,
    },
    "Ward Stones": {
        "crafter": "Scholar",
        "workstation": "enchanter",
        "skill": "enchanting",
        "skill_level": 4,
    },
    "Enchanter's Focus": {
        "crafter": "Scholar",
        "workstation": "enchanter",
        "skill": "enchanting",
        "skill_level": 4,
    },
    "Divination Crystal": {
        "crafter": "Scholar",
        "workstation": "enchanter",
        "skill": "enchanting",
        "skill_level": 3,
    },

    # ======== BOOKS & KNOWLEDGE (Scribe) ========
    "Book": {
        "crafter": "Scribe",
        "workstation": "workshop",
        "skill": "writing",
        "skill_level": 2,
    },
    "Skill Manual": {
        "crafter": "Scribe",
        "workstation": "workshop",
        "skill": "writing",
        "skill_level": 3,
    },
    "Spellbook": {
        "crafter": "Scribe",
        "workstation": "workshop",
        "skill": "writing",
        "skill_level": 4,
    },
    "Journal": {
        "crafter": "Scribe",
        "workstation": "workshop",
        "skill": "writing",
        "skill_level": 1,
    },
    "Map": {
        "crafter": "Cartographer",
        "workstation": "workshop",
        "skill": "cartography",
        "skill_level": 2,
    },
    "Regional Map": {
        "crafter": "Cartographer",
        "workstation": "cartography",
        "skill": "cartography",
        "skill_level": 3,
    },

    # ======== FARMING processed ========
    "Compost": {
        "crafter": "Farmer",
        "workstation": None,
        "skill": "farming",
        "skill_level": 1,
    },

    # ======== CLIMBING & EXPLORATION ========
    "Climbing Kit": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 2,
    },
    "Disguise Kit": {
        "crafter": "Weaver",
        "workstation": "workshop",
        "skill": "weaving",
        "skill_level": 2,
    },
    "Cartographer's Kit": {
        "crafter": "Cartographer",
        "workstation": "workshop",
        "skill": "cartography",
        "skill_level": 2,
    },
    "Dye Kit": {
        "crafter": "Weaver",
        "workstation": "workshop",
        "skill": "weaving",
        "skill_level": 2,
    },

    # ======== GLASSBLOWING TOOLS ========
    "Glassblower's Tools": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 3,
    },
    "Shipwright's Tools": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 3,
    },
    "Jeweler's Tools": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 3,
    },

    # ======== FINANCIAL ITEMS (Scribe/Banker) ========
    "Ledger": {
        "crafter": "Scribe",
        "workstation": "workshop",
        "skill": "writing",
        "skill_level": 1,
    },
    "Abacus": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 2,
    },
    "Gold Coins": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 2,
        "note": "Minted from Gold Bar; main source of new currency.",
    },
    "Silver Coins": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 1,
        "note": "Minted from Iron Ingot (silver content).",
    },

    # ======== ELVEN SPECIALTY CRAFTS ========
    "Elven Wine": {
        "crafter": "Brewer",
        "workstation": "brewery",
        "skill": "brewing",
        "skill_level": 5,
        "note": "Only brewed by elven vintners.",
    },
    "Mooncloth": {
        "crafter": "Weaver",
        "workstation": "loom",
        "skill": "weaving",
        "skill_level": 5,
        "note": "Silvery fabric woven by elven weavers.",
    },
    "Lembas Bread": {
        "crafter": "Baker",
        "workstation": "kitchen",
        "skill": "cooking",
        "skill_level": 5,
        "note": "Elven waybread with sustaining properties.",
    },
    "Enchanted Arrows": {
        "crafter": "Scholar",
        "workstation": "enchanter",
        "skill": "enchanting",
        "skill_level": 4,
        "note": "Arrows imbued with arcane energy.",
    },

    # ======== DWARVEN SPECIALTY CRAFTS ========
    "Dwarven Steel": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 6,
        "note": "Legendary dwarven alloy.",
    },
    "Masterwork Weapon": {
        "crafter": "Blacksmith",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 7,
        "note": "A weapon of peerless craftsmanship.",
    },
    "Masterwork Armor": {
        "crafter": "Armourer",
        "workstation": "forge",
        "skill": "smithing",
        "skill_level": 7,
        "note": "Armor forged by a dwarven master.",
    },
    "Gem Jewelry": {
        "crafter": "Jeweler",
        "workstation": "jeweler",
        "skill": "jeweling",
        "skill_level": 5,
        "note": "Exquisite gem-studded jewelry.",
    },

    # ======== ORCISH SPECIALTY CRAFTS ========
    "Bone Weapon": {
        "crafter": "Carpenter",
        "workstation": "workshop",
        "skill": "woodcraft",
        "skill_level": 1,
        "note": "Crude weapon carved from bone and wood.",
    },
    "War Paint": {
        "crafter": "Herbalist",
        "workstation": "workshop",
        "skill": "herbalism",
        "skill_level": 1,
        "note": "Tribal war paint from natural pigments.",
    },

    # ======== GOBLIN SPECIALTY CRAFTS ========
    "Goblin Fire": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 3,
        "note": "Volatile goblin incendiary mixture.",
    },
    "Crude Trap": {
        "crafter": "Blacksmith",
        "workstation": "workshop",
        "skill": "smithing",
        "skill_level": 1,
        "note": "A crude mechanical trap.",
    },
    "Mushroom Brew": {
        "crafter": "Brewer",
        "workstation": "brewery",
        "skill": "brewing",
        "skill_level": 1,
        "note": "Dubious fungal concoction.",
    },

    # ======== HUMAN SPECIALTY CRAFTS ========
    "Fine Ale": {
        "crafter": "Brewer",
        "workstation": "brewery",
        "skill": "brewing",
        "skill_level": 4,
        "note": "Premium ale of exceptional quality.",
    },
    "Embroidered Cloth": {
        "crafter": "Weaver",
        "workstation": "loom",
        "skill": "weaving",
        "skill_level": 4,
        "note": "Beautifully embroidered fabric.",
    },
}


# ================================================================
# QUEST / SCRIPTED ITEMS -- not produced by NPCs
# ================================================================

QUEST_ITEMS = {
    "Ancient Relic",    # found in dungeons / ruins
    "Letter",           # given by quest NPCs
    "Debt Contract",    # generated by banking system
    "Bond Certificate", # generated by banking system
    "Insurance Writ",   # generated by banking system
    # Specialty items found only in ruins/loot, not crafted
    "Trophy Skulls",    # orcish trophies
    "Beast Hide",       # hunted from great beasts
    "War Drums",        # orcish craft (non-player)
    "Bone Tools",       # primitive tools
    "Scrap Metal",      # scavenged
    "Sneaky Lockpicks", # goblin specialty
    "Cursed Artifact",  # undead dark magic
    "Soul Gem",         # undead soul trap
    "Dark Tome",        # forbidden lore
    "Phylactery Shard", # lich fragment
    "Death Shroud",     # undead shroud
}


# ================================================================
# FOREIGN TRADE GOODS -- arrive via merchant caravans
# ================================================================

FOREIGN_TRADE_GOODS = {
    "Silk": {
        "from": "Zarath Empire",
        "base_price": 15,
        "type": "luxury",
        "description": "Fine silk from the east.",
    },
    "Spices": {
        "from": "Zarath Empire",
        "base_price": 10,
        "type": "food_enhancement",
        "description": "Exotic spices for cooking.",
    },
    "Exotic Fruits": {
        "from": "Southern Isles",
        "base_price": 8,
        "type": "food",
        "description": "Tropical fruits from warm climates.",
    },
    "Pearls": {
        "from": "Southern Isles",
        "base_price": 20,
        "type": "luxury",
        "description": "Ocean pearls of great beauty.",
    },
    "Rum": {
        "from": "Southern Isles",
        "base_price": 6,
        "type": "drink",
        "description": "Strong sugarcane spirit.",
    },
    "Arcane Tomes": {
        "from": "Zarath Empire",
        "base_price": 25,
        "type": "knowledge",
        "description": "Books of foreign magical theory.",
    },
    "Navigation Charts": {
        "from": "Southern Isles",
        "base_price": 12,
        "type": "tool",
        "description": "Sea charts for distant waters.",
    },
    "Jade": {
        "from": "Northern Clans",
        "base_price": 18,
        "type": "luxury",
        "description": "Green jade stone from the north.",
    },
    "Ivory": {
        "from": "Southern Isles",
        "base_price": 22,
        "type": "luxury",
        "description": "Carved ivory tusks.",
    },
    "Incense": {
        "from": "Zarath Empire",
        "base_price": 5,
        "type": "luxury",
        "description": "Fragrant temple incense.",
    },
}


# ================================================================
# GOLD MINING -- how gold enters the economy
# ================================================================

GOLD_SOURCES = {
    "panning": {
        "profession": "Prospector",
        "source_tile": GEM_DEPOSIT,
        "yield_item": "Gold Nugget",
        "yield_range": (0, 1),
        "skill": "mining",
    },
    "smelting": {
        "profession": "Blacksmith",
        "input": {"Gold Nugget": 3},
        "output": "Gold Bar",
        "output_count": 1,
    },
    "minting": {
        "profession": "Blacksmith",
        "input": {"Gold Bar": 1},
        "output": "Gold Coins",
        "output_count": 5,
        "note": "1 gold bar = 5 gold coins; primary money supply.",
    },
    "trade": {
        "source": "foreign_merchants",
        "note": "Foreign caravans pay gold for exported local goods.",
    },
    "services": {
        "professions": ["Innkeeper", "Barber", "Banker", "Merchant"],
        "note": "Service professions generate gold from customers.",
    },
}


# ================================================================
# CRAFTER -> ITEMS LOOKUP (derived at import time)
# ================================================================

# ======== MAGIC ALCHEMY ADDITIONS ========
# New potions added by the magic system
try:
    from game.systems.magic import ALCHEMY_SUPPLY_CHAIN_ADDITIONS
    for _name, _data in ALCHEMY_SUPPLY_CHAIN_ADDITIONS.items():
        if _name not in SUPPLY_CHAINS:
            SUPPLY_CHAINS[_name] = _data
except ImportError:
    pass

# Which items each profession crafts (for NPC work AI to pick what to make)
PROFESSION_CRAFTS = {}
for _item_name, _chain in SUPPLY_CHAINS.items():
    _crafter = _chain["crafter"]
    PROFESSION_CRAFTS.setdefault(_crafter, []).append(_item_name)

# Which items each profession gathers
PROFESSION_GATHERS = {}
for _item_name, _source in RAW_MATERIAL_SOURCES.items():
    _gatherer = _source.get("gatherer")
    if _gatherer:
        PROFESSION_GATHERS.setdefault(_gatherer, []).append(_item_name)
