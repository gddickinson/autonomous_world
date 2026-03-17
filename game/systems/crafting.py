"""
Crafting and resource gathering system.

Based on D&D 5e 2024 crafting rules + medieval simulation games:
- Raw materials gathered from environment (chop trees, mine ore, pick herbs, farm crops)
- Crafted at workstations (forge, alchemy bench, kitchen, brewery, loom)
- Tool proficiency affects success and quality
- Production chains: ore → ingot → sword, grain → flour → bread, herbs → potion

Sources: D&D 2024 PHB crafting, Manor Lords production chains,
Medieval Dynasty resource management
"""

import random
from typing import Dict, List, Tuple, Optional
from game.settings import *


# ================================================================
# RESOURCE TERRAIN TYPES (harvestable tiles)
# ================================================================

# These are the terrain type constants from settings.py
# FOREST = 3        → chop → Wood
# DENSE_FOREST = 4  → chop → Wood + Herbs
# MOUNTAIN = 5      → mine → Stone, Iron Ore, Gold Nugget
# WATER = 0         → fish → Fish
# FARMLAND = 11     → harvest → Wheat, Vegetables
# New resource types to add to settings:
ORE_VEIN = 25       # iron/copper ore deposit in mountains
HERB_PATCH = 26     # wild herbs in forests
BERRY_BUSH = 27     # berries near forests
CLAY_PIT = 28       # clay near water
MUSHROOMS = 29      # mushrooms in dense forest
WHEAT_FIELD = 30    # planted wheat (mature)
VEGETABLE_PLOT = 31 # planted vegetables (mature)
FRUIT_TREE = 32     # apple/pear tree
FLOWER_BED = 33     # flowers for alchemy
GEM_DEPOSIT = 34    # gemstones in deep mountain
COPPER_VEIN = 35    # copper ore near mountains
FLAX_FIELD = 36     # flax for linen/rope
BEEHIVE = 37        # wild bees for honey/wax
SALT_FLAT = 38      # salt deposits near coast/desert
SAND_TILE = 1       # alias for sand terrain (SAND from settings)
SHALLOW_WATER_TILE = 40  # shallow water near shores

# What you get from gathering each resource type
GATHER_YIELDS = {
    FOREST:       [("Wood", 1, 3)],
    DENSE_FOREST: [("Wood", 1, 2), ("Herbs", 0, 1), ("Resin", 0, 1)],
    MOUNTAIN:     [("Stone", 1, 2)],
    ORE_VEIN:     [("Iron Ore", 1, 2), ("Gold Nugget", 0, 1)],
    HERB_PATCH:   [("Herbs", 1, 3)],
    BERRY_BUSH:   [("Berries", 2, 5)],
    CLAY_PIT:     [("Clay", 1, 3)],
    MUSHROOMS:    [("Mushrooms", 1, 3)],
    WHEAT_FIELD:  [("Wheat", 2, 5)],
    VEGETABLE_PLOT: [("Vegetables", 1, 3)],
    FRUIT_TREE:   [("Apple", 1, 3)],
    FLOWER_BED:   [("Flowers", 1, 2)],
    FARMLAND:     [("Wheat", 1, 2)],
    GEM_DEPOSIT:  [("Raw Ruby", 0, 1), ("Raw Sapphire", 0, 1), ("Raw Emerald", 0, 1), ("Raw Diamond", 0, 1)],
    COPPER_VEIN:  [("Copper Ore", 1, 3)],
    FLAX_FIELD:   [("Flax", 2, 4)],
    BEEHIVE:      [("Honey", 1, 2), ("Beeswax", 0, 1)],
    SALT_FLAT:    [("Salt", 1, 3)],
    SAND_TILE:    [("Sand", 1, 3)],
    SHALLOW_WATER_TILE: [("Fish", 1, 3)],
    0:            [("Fish", 0, 2)],   # deep water (WATER=0) -- lower yield
}

# Tool required for gathering
GATHER_TOOLS = {
    FOREST: "Axe", DENSE_FOREST: "Axe",
    MOUNTAIN: "Pickaxe", ORE_VEIN: "Pickaxe",
    GEM_DEPOSIT: "Pickaxe", COPPER_VEIN: "Pickaxe",
    HERB_PATCH: None, BERRY_BUSH: None, CLAY_PIT: None,
    MUSHROOMS: None, FRUIT_TREE: None, FLOWER_BED: None,
    WHEAT_FIELD: "Hoe", VEGETABLE_PLOT: "Hoe", FARMLAND: "Hoe",
    FLAX_FIELD: "Hoe", BEEHIVE: None, SALT_FLAT: None,
    SAND_TILE: None, SHALLOW_WATER_TILE: "Fishing Rod", 0: "Fishing Rod",
}

# Time to gather (seconds)
GATHER_TIME = {
    FOREST: 4.0, DENSE_FOREST: 5.0, MOUNTAIN: 6.0,
    ORE_VEIN: 5.0, GEM_DEPOSIT: 8.0, COPPER_VEIN: 5.0,
    HERB_PATCH: 2.0, BERRY_BUSH: 1.5, CLAY_PIT: 3.0,
    MUSHROOMS: 1.5, WHEAT_FIELD: 3.0, VEGETABLE_PLOT: 3.0,
    FRUIT_TREE: 2.0, FLOWER_BED: 2.0, FARMLAND: 3.0,
    FLAX_FIELD: 3.0, BEEHIVE: 3.0, SALT_FLAT: 2.0,
    SAND_TILE: 2.0, SHALLOW_WATER_TILE: 4.0, 0: 5.0,
}


# ================================================================
# CRAFTING RECIPES
# ================================================================

# Each recipe: {result_item: (count, [(ingredient, count), ...], tool_required, workstation, time)}
RECIPES = {
    # ======== COOKING (Kitchen / Campfire / Bakery) ========
    "Bread":           (2, [("Wheat", 2)], None, "kitchen", 3.0),
    "Cooked Meat":     (1, [("Raw Meat", 1)], None, "kitchen", 2.0),
    "Vegetable Stew":  (2, [("Vegetables", 2), ("Water Flask", 1)], None, "kitchen", 4.0),
    "Berry Pie":       (1, [("Berries", 3), ("Wheat", 1)], None, "kitchen", 3.0),
    "Mushroom Soup":   (2, [("Mushrooms", 2), ("Water Flask", 1)], None, "kitchen", 3.0),
    "Meat Pie":        (1, [("Raw Meat", 1), ("Wheat", 2)], None, "kitchen", 4.0),
    "Honey Cake":      (2, [("Wheat", 2), ("Honey", 1)], None, "kitchen", 3.0),
    "Salted Fish":     (2, [("Fish", 1), ("Salt", 1)], None, "kitchen", 2.0),
    "Trail Rations":   (3, [("Bread", 1), ("Cooked Meat", 1), ("Berries", 2)], None, "kitchen", 3.0),
    "Feast Platter":   (1, [("Cooked Meat", 2), ("Vegetables", 2), ("Bread", 2), ("Ale", 1)], None, "kitchen", 8.0),

    # ======== BREWING (Brewery) ========
    "Ale":             (2, [("Wheat", 3), ("Water Flask", 1)], None, "brewery", 5.0),
    "Healing Tonic":   (1, [("Herbs", 2), ("Berries", 1), ("Water Flask", 1)], None, "brewery", 4.0),
    "Mead":            (2, [("Water Flask", 1), ("Honey", 2)], None, "brewery", 6.0),
    "Wine":            (2, [("Berries", 4), ("Water Flask", 1)], None, "brewery", 8.0),
    "Dwarven Stout":   (2, [("Wheat", 4), ("Honey", 1), ("Water Flask", 1)], None, "brewery", 10.0),
    "Elven Cordial":   (1, [("Flowers", 3), ("Honey", 1), ("Water Flask", 1)], None, "brewery", 8.0),

    # ======== ALCHEMY (Alchemy Bench) ========
    "Health Potion":   (1, [("Herbs", 3), ("Flowers", 1), ("Water Flask", 1)], "Herbalism Kit", "alchemy", 5.0),
    "Greater Health Potion": (1, [("Herbs", 5), ("Flowers", 2), ("Gold Nugget", 1)], "Herbalism Kit", "alchemy", 8.0),
    "Antidote":        (1, [("Herbs", 2), ("Mushrooms", 1)], "Herbalism Kit", "alchemy", 3.0),
    "Fire Oil":        (1, [("Resin", 2), ("Clay", 1)], None, "alchemy", 4.0),
    "Poison Vial":     (1, [("Mushrooms", 3), ("Herbs", 1)], "Herbalism Kit", "alchemy", 5.0),
    "Strength Elixir": (1, [("Herbs", 3), ("Raw Ruby", 1), ("Honey", 1)], "Herbalism Kit", "alchemy", 8.0),
    "Speed Elixir":    (1, [("Herbs", 3), ("Raw Sapphire", 1), ("Honey", 1)], "Herbalism Kit", "alchemy", 8.0),
    "Invisibility Oil": (1, [("Flowers", 3), ("Raw Diamond", 1), ("Mushrooms", 2)], "Herbalism Kit", "alchemy", 12.0),
    "Healing Salve":   (2, [("Herbs", 2), ("Beeswax", 1)], "Herbalism Kit", "alchemy", 3.0),
    "Smelling Salts":  (1, [("Salt", 2), ("Herbs", 1)], None, "alchemy", 2.0),
    "Ink":             (1, [("Flowers", 2), ("Water Flask", 1)], None, "alchemy", 2.0),

    # ======== SMITHING (Forge / Blacksmith) ========
    "Iron Ingot":      (1, [("Iron Ore", 2)], "Smith's Tools", "forge", 4.0),
    "Copper Ingot":    (1, [("Copper Ore", 2)], "Smith's Tools", "forge", 3.0),
    "Bronze Ingot":    (1, [("Copper Ingot", 1), ("Iron Ingot", 1)], "Smith's Tools", "forge", 4.0),
    "Steel Ingot":     (1, [("Iron Ingot", 2)], "Smith's Tools", "forge", 6.0),
    "Gold Bar":        (1, [("Gold Nugget", 3)], "Smith's Tools", "forge", 5.0),
    "Iron Sword":      (1, [("Iron Ingot", 2), ("Wood", 1)], "Smith's Tools", "forge", 6.0),
    "Iron Armor":      (1, [("Iron Ingot", 4), ("Leather", 1)], "Smith's Tools", "forge", 10.0),
    "Steel Sword":     (1, [("Steel Ingot", 2), ("Wood", 1)], "Smith's Tools", "forge", 8.0),
    "Bronze Shield":   (1, [("Bronze Ingot", 2), ("Wood", 1)], "Smith's Tools", "forge", 6.0),
    "Chain Mail":      (1, [("Iron Ingot", 6)], "Smith's Tools", "forge", 12.0),
    "Plate Armor":     (1, [("Steel Ingot", 5), ("Leather", 2)], "Smith's Tools", "forge", 16.0),
    "Pickaxe":         (1, [("Iron Ingot", 1), ("Wood", 2)], "Smith's Tools", "forge", 4.0),
    "Axe":             (1, [("Iron Ingot", 1), ("Wood", 2)], "Smith's Tools", "forge", 4.0),
    "Hammer":          (1, [("Iron Ingot", 1), ("Wood", 1)], "Smith's Tools", "forge", 3.0),
    "Hoe":             (1, [("Iron Ingot", 1), ("Wood", 2)], "Smith's Tools", "forge", 3.0),
    "Nails":           (5, [("Iron Ingot", 1)], "Smith's Tools", "forge", 2.0),
    "Arrowheads":      (10, [("Iron Ingot", 1)], "Smith's Tools", "forge", 3.0),
    "Iron Horseshoes": (4, [("Iron Ingot", 1)], "Smith's Tools", "forge", 2.0),
    "Lantern":         (1, [("Iron Ingot", 1), ("Glass Pane", 1)], "Smith's Tools", "forge", 4.0),
    "Lockpick":        (2, [("Iron Ingot", 1)], "Smith's Tools", "forge", 2.0),
    "Iron Chain":      (1, [("Iron Ingot", 2)], "Smith's Tools", "forge", 3.0),

    # ======== JEWELER (Jeweler's Bench) ========
    "Ruby":            (1, [("Raw Ruby", 1)], "Jeweler's Tools", "jeweler", 6.0),
    "Sapphire":        (1, [("Raw Sapphire", 1)], "Jeweler's Tools", "jeweler", 6.0),
    "Emerald":         (1, [("Raw Emerald", 1)], "Jeweler's Tools", "jeweler", 6.0),
    "Diamond":         (1, [("Raw Diamond", 1)], "Jeweler's Tools", "jeweler", 10.0),
    "Gold Ring":       (1, [("Gold Bar", 1)], "Jeweler's Tools", "jeweler", 4.0),
    "Ruby Ring":       (1, [("Gold Ring", 1), ("Ruby", 1)], "Jeweler's Tools", "jeweler", 6.0),
    "Sapphire Amulet": (1, [("Gold Bar", 1), ("Sapphire", 1), ("Iron Chain", 1)], "Jeweler's Tools", "jeweler", 8.0),
    "Emerald Pendant": (1, [("Gold Bar", 1), ("Emerald", 1), ("Iron Chain", 1)], "Jeweler's Tools", "jeweler", 8.0),
    "Diamond Crown":   (1, [("Gold Bar", 3), ("Diamond", 2)], "Jeweler's Tools", "jeweler", 16.0),
    "Enchanted Ring":  (1, [("Gold Ring", 1), ("Ruby", 1), ("Sapphire", 1)], "Jeweler's Tools", "jeweler", 12.0),

    # ======== LEATHERWORKING (Workshop / Tannery) ========
    "Leather":         (1, [("Wolf Pelt", 1), ("Salt", 1)], None, "workshop", 3.0),
    "Leather Armor":   (1, [("Leather", 3)], None, "workshop", 5.0),
    "Boots":           (1, [("Leather", 2)], None, "workshop", 3.0),
    "Quiver":          (1, [("Leather", 1), ("Wood", 1)], None, "workshop", 2.0),
    "Belt":            (1, [("Leather", 1)], None, "workshop", 1.0),
    "Leather Gloves":  (1, [("Leather", 1)], None, "workshop", 2.0),
    "Satchel":         (1, [("Leather", 2)], None, "workshop", 3.0),
    "Saddle":          (1, [("Leather", 3), ("Iron Ingot", 1)], None, "workshop", 6.0),
    "Waterskin":       (1, [("Leather", 1)], None, "workshop", 2.0),

    # ======== WOODWORKING (Workshop / Carpenter) ========
    "Planks":          (3, [("Wood", 2)], "Axe", "workshop", 2.0),
    "Wooden Shield":   (1, [("Planks", 3), ("Nails", 2)], "Hammer", "workshop", 4.0),
    "Hunting Bow":     (1, [("Wood", 2)], None, "workshop", 3.0),
    "Arrows":          (10, [("Wood", 1), ("Arrowheads", 5)], None, "workshop", 2.0),
    "Fishing Rod":     (1, [("Wood", 2)], None, "workshop", 2.0),
    "Staff":           (1, [("Wood", 2)], None, "workshop", 2.0),
    "Torch":           (3, [("Wood", 1), ("Resin", 1)], None, "workshop", 1.0),
    "Barrel":          (1, [("Planks", 4), ("Nails", 3)], "Hammer", "workshop", 4.0),
    "Crate":           (1, [("Planks", 3), ("Nails", 2)], "Hammer", "workshop", 3.0),
    "Cart":            (1, [("Planks", 6), ("Nails", 4), ("Iron Ingot", 2)], "Hammer", "workshop", 10.0),

    # ======== TEXTILES (Loom / Weaver) ========
    "Linen":           (2, [("Flax", 3)], None, "loom", 3.0),
    "Rope":            (2, [("Flax", 2)], None, "loom", 2.0),
    "Bandage":         (3, [("Linen", 1)], None, "loom", 1.0),
    "Cloak":           (1, [("Linen", 3)], None, "loom", 4.0),
    "Robe":            (1, [("Linen", 4), ("Flowers", 1)], None, "loom", 5.0),
    "Tent":            (1, [("Linen", 4), ("Rope", 2), ("Wood", 2)], None, "loom", 6.0),

    # ======== POTTERY & GLASS (Workshop) ========
    "Water Flask":     (2, [("Clay", 2)], None, "workshop", 2.0),
    "Pot":             (1, [("Clay", 3)], None, "workshop", 3.0),
    "Vase":            (1, [("Clay", 2), ("Flowers", 1)], None, "workshop", 3.0),
    "Glass Pane":      (1, [("Sand", 3)], None, "forge", 4.0),
    "Bottle":          (1, [("Sand", 2)], None, "forge", 3.0),

    # ======== CHANDLERY (Candles & Wax) ========
    "Candle":          (3, [("Beeswax", 1), ("Flax", 1)], None, "workshop", 2.0),
    "Sealing Wax":     (2, [("Beeswax", 1), ("Resin", 1)], None, "workshop", 2.0),

    # ======== FARMING ========
    "Seeds":           (3, [("Wheat", 1)], None, None, 1.0),
    "Flour":           (2, [("Wheat", 3)], None, "kitchen", 2.0),
    "Compost":         (1, [("Vegetables", 2), ("Mushrooms", 1)], None, None, 3.0),

    # ======== ENCHANTING (Enchanter's Table) ========
    "Scroll of Healing": (1, [("Ink", 1), ("Linen", 1), ("Herbs", 2)], None, "enchanter", 5.0),
    "Scroll of Fire":    (1, [("Ink", 1), ("Linen", 1), ("Fire Oil", 1)], None, "enchanter", 5.0),
    "Wand of Sparks":    (1, [("Wood", 1), ("Ruby", 1), ("Gold Bar", 1)], None, "enchanter", 10.0),

    # ======== DAIRY & ANIMAL PRODUCTS ========
    "Cheese":          (2, [("Milk", 3), ("Salt", 1)], None, "kitchen", 5.0),
    "Butter":          (2, [("Milk", 2)], "Churn", "kitchen", 3.0),
    "Cheese Wheel":    (1, [("Cheese", 4), ("Salt", 1)], None, "kitchen", 8.0),
    "Omelette":        (2, [("Eggs", 2), ("Butter", 1)], None, "kitchen", 2.0),
    "Bacon":           (2, [("Raw Meat", 2), ("Salt", 1)], None, "kitchen", 4.0),
    "Sausage":         (2, [("Raw Meat", 2), ("Salt", 1), ("Herbs", 1)], None, "kitchen", 4.0),
    "Smoked Fish":     (2, [("Fish", 2), ("Salt", 1), ("Wood", 1)], None, "kitchen", 4.0),

    # ======== TRAPPING & FARMING TOOLS ========
    "Snare Trap":      (2, [("Rope", 1), ("Wood", 1)], None, "workshop", 2.0),
    "Cage":            (1, [("Iron Ingot", 2), ("Wood", 2)], "Smith's Tools", "workshop", 5.0),
    "Net":             (1, [("Rope", 2), ("Flax", 2)], None, "workshop", 3.0),
    "Bucket":          (1, [("Planks", 2), ("Nails", 2)], None, "workshop", 2.0),
    "Churn":           (1, [("Planks", 3), ("Nails", 2)], None, "workshop", 3.0),
    "Trough":          (1, [("Planks", 3), ("Nails", 2)], None, "workshop", 3.0),

    # ======== BOOKS & KNOWLEDGE ========
    "Book":            (1, [("Linen", 2), ("Ink", 2), ("Leather", 1)], None, "workshop", 5.0),
    "Skill Manual":    (1, [("Book", 1), ("Ink", 2)], None, "workshop", 8.0),
    "Journal":         (1, [("Linen", 1), ("Ink", 1)], None, "workshop", 3.0),
    "Map":             (1, [("Linen", 1), ("Ink", 1)], None, "workshop", 4.0),

    # ======== WOOL TEXTILES ========
    "Wool Cloth":      (2, [("Wool", 3)], None, "loom", 3.0),

    # ======== HERBALISM & TOOLS ========
    "Herbalism Kit":   (1, [("Herbs", 3), ("Leather", 1)], None, "workshop", 3.0),
    "Smith's Tools":   (1, [("Iron Ingot", 2), ("Wood", 1), ("Leather", 1)], None, "forge", 5.0),
    "Jeweler's Tools": (1, [("Iron Ingot", 1), ("Gold Bar", 1)], "Smith's Tools", "forge", 6.0),

    # ======== NEW SKILL TOOLS (crafted) ========
    "Thieves' Tools":  (1, [("Iron Ingot", 1), ("Leather", 1)], "Smith's Tools", "forge", 4.0),
    "Healer's Kit":    (1, [("Herbs", 3), ("Linen", 2), ("Leather", 1)], None, "workshop", 4.0),
    "Climbing Kit":    (1, [("Rope", 2), ("Iron Ingot", 1)], None, "workshop", 3.0),
    "Dye Kit":         (1, [("Flowers", 3), ("Clay", 2)], None, "workshop", 3.0),
    "Disguise Kit":    (1, [("Linen", 2), ("Leather", 1), ("Ink", 1)], None, "workshop", 4.0),
    "Musical Instrument": (1, [("Wood", 3), ("Flax", 2)], None, "workshop", 6.0),
    "Cartographer's Kit": (1, [("Ink", 2), ("Linen", 1), ("Wood", 1)], None, "workshop", 4.0),
    "Navigator's Tools":  (1, [("Iron Ingot", 1), ("Glass Pane", 1)], "Smith's Tools", "forge", 5.0),
    "Grappling Hook":  (1, [("Iron Ingot", 1), ("Rope", 1)], "Smith's Tools", "forge", 3.0),
    "Training Dummy":  (1, [("Wood", 3), ("Rope", 1)], None, "workshop", 3.0),
    "Iron Shield":     (1, [("Iron Ingot", 3)], "Smith's Tools", "forge", 5.0),

    # ======== NEW POTTERY (Pottery Studio) ========
    "Pottery Jar":     (2, [("Clay", 2)], None, "pottery", 3.0),

    # ======== NEW GLASSBLOWING (Glassworks) ========
    "Stained Glass":   (1, [("Glass Pane", 2), ("Flowers", 2)], "Glassblower's Tools", "glassworks", 6.0),

    # ======== NEW TANNING (Tannery) ========
    "Tanned Hide":     (1, [("Wolf Pelt", 1), ("Salt", 1)], None, "tannery", 3.0),

    # ======== NEW DYEING (Dye House) ========
    "Dyed Cloth":      (1, [("Linen", 1), ("Flowers", 2)], "Dye Kit", "dye_house", 3.0),

    # ======== NEW ENCHANTING (Enchanter) ========
    "Enchanted Sword": (1, [("Steel Sword", 1), ("Diamond", 1), ("Ruby", 1)], "Enchanter's Focus", "enchanter", 16.0),
    "Enchanted Staff": (1, [("Staff", 1), ("Sapphire", 1), ("Emerald", 1)], "Enchanter's Focus", "enchanter", 14.0),
    "Scroll of Ward":  (1, [("Linen", 1), ("Ink", 1), ("Emerald", 1)], "Enchanter's Focus", "enchanter", 6.0),
    "Ward Stones":     (3, [("Stone", 3), ("Ruby", 1)], "Enchanter's Focus", "enchanter", 8.0),

    # ======== NEW CARTOGRAPHY (Map Room) ========
    "Regional Map":    (1, [("Linen", 1), ("Ink", 2)], "Cartographer's Kit", "cartography", 5.0),

    # ======== NEW TRAP MAKING (Workshop) ========
    "Trap":            (2, [("Iron Ingot", 1), ("Rope", 1)], None, "workshop", 4.0),
    "Caltrops":        (5, [("Iron Ingot", 1)], "Smith's Tools", "forge", 2.0),

    # ======== SIEGE ENGINEERING ========
    "Battering Ram":   (1, [("Wood", 5), ("Iron Ingot", 3), ("Rope", 2)], "Siege Tools", "workshop", 12.0),

    # ======== MEDICINE ========
    "Herbal Poultice": (2, [("Herbs", 2), ("Linen", 1)], "Healer's Kit", "workshop", 3.0),
    "Holy Water":      (2, [("Water Flask", 1), ("Salt", 1), ("Flowers", 1)], None, "enchanter", 3.0),

    # ======== SHIPBUILDING ========
    "Boat Hull":       (1, [("Planks", 10), ("Nails", 8), ("Resin", 3)], "Shipwright's Tools", "workshop", 20.0),

    # ======== MISSING WEAPON RECIPES ========
    "Wooden Sword":    (1, [("Wood", 2)], None, "workshop", 2.0),

    # ======== MISSING TOOL RECIPES ========
    "Siege Tools":     (1, [("Iron Ingot", 3), ("Wood", 2), ("Rope", 1)], "Smith's Tools", "forge", 8.0),
    "Shipwright's Tools": (1, [("Iron Ingot", 2), ("Wood", 2), ("Rope", 1)], "Smith's Tools", "forge", 6.0),
    "Glassblower's Tools": (1, [("Iron Ingot", 2), ("Copper Ingot", 1)], "Smith's Tools", "forge", 5.0),
    "Strongbox":       (1, [("Iron Ingot", 3), ("Nails", 4)], "Smith's Tools", "forge", 6.0),
    "Abacus":          (1, [("Wood", 1), ("Iron Ingot", 1)], None, "workshop", 3.0),
    "Ledger":          (1, [("Linen", 2), ("Ink", 2), ("Leather", 1)], None, "workshop", 4.0),

    # ======== ENCHANTING TOOLS ========
    "Enchanter's Focus": (1, [("Glass Pane", 2), ("Gold Bar", 1), ("Ruby", 1)], None, "enchanter", 8.0),
    "Divination Crystal": (1, [("Glass Pane", 2), ("Sapphire", 1)], None, "enchanter", 6.0),

    # ======== BOOKS (extended) ========
    "Spellbook":       (1, [("Book", 1), ("Ink", 3), ("Ruby", 1)], None, "enchanter", 10.0),

    # ======== CURRENCY MINTING ========
    "Gold Coins":      (5, [("Gold Bar", 1)], "Smith's Tools", "forge", 3.0),
    "Silver Coins":    (10, [("Iron Ingot", 1)], "Smith's Tools", "forge", 2.0),
    "Wax Seal":        (3, [("Beeswax", 1), ("Sealing Wax", 1)], None, "workshop", 1.0),
}

# New items that need to be registered
NEW_ITEMS = {
    "Berries":         {"kind": "food", "value": 1, "heal": 3, "desc": "Wild berries.", "stack": True},
    "Mushrooms":       {"kind": "food", "value": 2, "heal": 5, "desc": "Forest mushrooms.", "stack": True},
    "Wheat":           {"kind": "resource", "value": 1, "desc": "Harvested wheat grain.", "stack": True},
    "Vegetables":      {"kind": "food", "value": 2, "heal": 8, "desc": "Fresh vegetables.", "stack": True},
    "Flowers":         {"kind": "resource", "value": 2, "desc": "Colorful flowers for alchemy.", "stack": True},
    "Clay":            {"kind": "resource", "value": 1, "desc": "Wet clay for pottery.", "stack": True},
    "Raw Meat":        {"kind": "resource", "value": 3, "desc": "Uncooked meat.", "stack": True},
    "Iron Ingot":      {"kind": "resource", "value": 12, "desc": "Smelted iron bar.", "stack": True},
    "Leather":         {"kind": "resource", "value": 8, "desc": "Tanned leather.", "stack": True},
    "Planks":          {"kind": "resource", "value": 3, "desc": "Sawn wooden planks.", "stack": True},
    "Nails":           {"kind": "resource", "value": 1, "desc": "Iron nails.", "stack": True},
    "Arrowheads":      {"kind": "resource", "value": 1, "desc": "Iron arrowheads.", "stack": True},
    "Arrows":          {"kind": "weapon", "value": 2, "damage": 6, "desc": "A bundle of arrows.", "stack": True},
    "Vegetable Stew":  {"kind": "food", "value": 5, "heal": 15, "desc": "Hearty vegetable stew.", "stack": True},
    "Berry Pie":       {"kind": "food", "value": 4, "heal": 12, "desc": "Sweet berry pie.", "stack": True},
    "Mushroom Soup":   {"kind": "food", "value": 4, "heal": 12, "desc": "Savory mushroom soup.", "stack": True},
    "Healing Tonic":   {"kind": "consumable", "value": 10, "heal": 20, "desc": "A mild healing tonic.", "stack": True},
    "Mead":            {"kind": "drink", "value": 5, "desc": "Honeyed mead.", "stack": True},
    "Antidote":        {"kind": "consumable", "value": 8, "heal": 5, "desc": "Cures poison.", "stack": True},
    "Fire Oil":        {"kind": "resource", "value": 10, "desc": "Flammable oil.", "stack": True},
    "Boots":           {"kind": "armor", "value": 15, "defense": 1, "desc": "Leather boots."},
    "Quiver":          {"kind": "resource", "value": 8, "desc": "Holds arrows."},
    "Wooden Shield":   {"kind": "armor", "value": 10, "defense": 2, "desc": "A sturdy wooden shield."},
    "Pot":             {"kind": "tool", "value": 5, "desc": "A clay cooking pot."},
    "Smith's Tools":   {"kind": "tool", "value": 25, "desc": "Blacksmithing tools."},
}


# ================================================================
# CRAFTING SYSTEM
# ================================================================

class CraftingSystem:
    """Manages crafting recipes, workstation requirements, and production."""

    @staticmethod
    def get_available_recipes(crafter_inventory: list, workstation: str = None) -> List[str]:
        """Get recipes the crafter can make with current inventory and workstation."""
        available = []
        for recipe_name, (count, ingredients, tool, station, time) in RECIPES.items():
            # Check workstation
            if station and station != workstation:
                continue

            # Check tool
            if tool and not any(i.name == tool for i in crafter_inventory):
                continue

            # Check ingredients
            has_all = True
            for ing_name, ing_count in ingredients:
                total = sum(i.count if i.stackable else 1 for i in crafter_inventory if i.name == ing_name)
                if total < ing_count:
                    has_all = False
                    break

            if has_all:
                available.append(recipe_name)

        return available

    @staticmethod
    def craft(recipe_name: str, crafter, workstation: str = None) -> Tuple[bool, str]:
        """Attempt to craft an item. Returns (success, message)."""
        if recipe_name not in RECIPES:
            return False, f"Unknown recipe: {recipe_name}"

        count, ingredients, tool, station, craft_time = RECIPES[recipe_name]

        # Check workstation
        if station and station != workstation:
            return False, f"Requires a {station} workstation"

        # Check tool
        inv = crafter.inventory if hasattr(crafter, 'inventory') else getattr(crafter, 'npc_inventory', [])
        if tool and not any(i.name == tool for i in inv):
            return False, f"Requires {tool}"

        # Check and consume ingredients
        for ing_name, ing_count in ingredients:
            total = sum(i.count if i.stackable else 1 for i in inv if i.name == ing_name)
            if total < ing_count:
                return False, f"Need {ing_count} {ing_name} (have {total})"

        # Consume ingredients
        for ing_name, ing_count in ingredients:
            remaining = ing_count
            for item in list(inv):
                if item.name == ing_name and remaining > 0:
                    if item.stackable:
                        used = min(item.count, remaining)
                        item.count -= used
                        remaining -= used
                        if item.count <= 0:
                            inv.remove(item)
                    else:
                        inv.remove(item)
                        remaining -= 1

        # Create result
        from game.core.items import make_item
        result_item = make_item(recipe_name)
        result_item.count = count

        if hasattr(crafter, 'add_item'):
            crafter.add_item(result_item)
        elif hasattr(crafter, 'npc_add_item'):
            crafter.npc_add_item(result_item)

        return True, f"Crafted {count}x {recipe_name}!"

    @staticmethod
    def gather_resource(tile_type: int, gatherer, rng: random.Random = None) -> Tuple[List, str]:
        """Gather resources from a terrain tile. Returns (items, message)."""
        if rng is None:
            rng = random

        yields = GATHER_YIELDS.get(tile_type)
        if not yields:
            return [], "Nothing to gather here."

        tool_needed = GATHER_TOOLS.get(tile_type)
        inv = gatherer.inventory if hasattr(gatherer, 'inventory') else getattr(gatherer, 'npc_inventory', [])

        if tool_needed and not any(i.name == tool_needed for i in inv):
            return [], f"Need a {tool_needed} to gather here."

        items = []
        from game.core.items import make_item
        for item_name, min_count, max_count in yields:
            count = rng.randint(min_count, max_count)
            if count > 0:
                item = make_item(item_name)
                item.count = count
                items.append(item)

        if not items:
            return [], "Found nothing useful."

        names = ", ".join(f"{i.count}x {i.name}" for i in items)
        return items, f"Gathered: {names}"


def place_resources_in_world(world, rng: random.Random):
    """Place resource nodes (ore veins, herb patches, etc.) in appropriate locations."""
    w, h = world.width, world.height

    for y in range(h):
        for x in range(w):
            tile = world.tiles[y][x]

            # Ore veins in/near mountains (8% chance, check multiple neighbors)
            if tile == MOUNTAIN and rng.random() < 0.08:
                for dx, dy in [(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and world.tiles[ny][nx] in (GRASS, SAND, FOREST):
                        world.tiles[ny][nx] = ORE_VEIN
                        break

            # Herb patches in forests (2% chance)
            elif tile == FOREST and rng.random() < 0.02:
                world.tiles[y][x] = HERB_PATCH

            # Berry bushes near forest edges (1.5% for grass near forest)
            elif tile == GRASS:
                has_forest_neighbor = False
                for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and world.tiles[ny][nx] in (FOREST, DENSE_FOREST):
                        has_forest_neighbor = True
                        break
                if has_forest_neighbor and rng.random() < 0.015:
                    world.tiles[y][x] = BERRY_BUSH

            # Mushrooms in dense forest (3% chance)
            elif tile == DENSE_FOREST and rng.random() < 0.03:
                world.tiles[y][x] = MUSHROOMS

            # Clay near water (4% for grass/sand adjacent to water)
            elif tile in (GRASS, SAND):
                has_water = False
                for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and world.tiles[ny][nx] == WATER:
                        has_water = True
                        break
                if has_water and rng.random() < 0.04:
                    world.tiles[y][x] = CLAY_PIT

            # Flower beds in grassland (1% chance)
            elif tile == GRASS and rng.random() < 0.01:
                world.tiles[y][x] = FLOWER_BED

            # Fruit trees scattered in forests (1.5%)
            elif tile == FOREST and rng.random() < 0.015:
                world.tiles[y][x] = FRUIT_TREE

            # Gem deposits deep in mountains (2.5%)
            if tile == MOUNTAIN and rng.random() < 0.025:
                for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    nx, ny = x + dx, y + dy
                    if (0 <= nx < w and 0 <= ny < h and
                        world.tiles[ny][nx] in (GRASS, SAND, FOREST)):
                        world.tiles[ny][nx] = GEM_DEPOSIT
                        break

            # Copper veins near mountains (10%)
            if tile == MOUNTAIN and rng.random() < 0.10:
                for dx, dy in [(1,1),(-1,-1),(1,-1),(-1,1)]:
                    nx, ny = x + dx, y + dy
                    if (0 <= nx < w and 0 <= ny < h and
                        world.tiles[ny][nx] in (GRASS, SAND)):
                        world.tiles[ny][nx] = COPPER_VEIN
                        break

            # Flax fields in grassland (0.8%)
            if tile == GRASS and rng.random() < 0.008:
                world.tiles[y][x] = FLAX_FIELD

            # Beehives near forest edges (rare 0.3%)
            if tile == GRASS:
                near_forest = any(
                    0 <= x+ddx < w and 0 <= y+ddy < h and
                    world.tiles[y+ddy][x+ddx] in (FOREST, DENSE_FOREST, FRUIT_TREE)
                    for ddx, ddy in [(1,0),(-1,0),(0,1),(0,-1)]
                )
                if near_forest and rng.random() < 0.003:
                    world.tiles[y][x] = BEEHIVE

            # Salt flats near coast/desert (2% of sand near water)
            if tile == SAND:
                near_water = any(
                    0 <= x+ddx < w and 0 <= y+ddy < h and
                    world.tiles[y+ddy][x+ddx] == WATER
                    for ddx, ddy in [(1,0),(-1,0),(0,1),(0,-1)]
                )
                if near_water and rng.random() < 0.02:
                    world.tiles[y][x] = SALT_FLAT

            # === TERRAIN FEATURES ===
            # Shallow water near shores
            if tile == WATER:
                has_land = any(
                    0 <= x+ddx < w and 0 <= y+ddy < h and
                    world.tiles[y+ddy][x+ddx] in (GRASS, SAND, ROAD)
                    for ddx, ddy in [(-1,0),(1,0),(0,-1),(0,1)]
                )
                if has_land and rng.random() < 0.3:
                    world.tiles[y][x] = 40  # SHALLOW_WATER

            # Rocky ground near mountains
            if tile == GRASS:
                has_mountain = any(
                    0 <= x+ddx < w and 0 <= y+ddy < h and
                    world.tiles[y+ddy][x+ddx] == MOUNTAIN
                    for ddx, ddy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1)]
                )
                if has_mountain and rng.random() < 0.25:
                    world.tiles[y][x] = 41  # ROCKY_GROUND

            # Marsh near water in grassland
            if tile == GRASS:
                has_water = any(
                    0 <= x+ddx < w and 0 <= y+ddy < h and
                    world.tiles[y+ddy][x+ddx] in (WATER, 40)
                    for ddx, ddy in [(-2,0),(2,0),(0,-2),(0,2)]
                )
                if has_water and rng.random() < 0.1:
                    world.tiles[y][x] = 42  # MARSH

            # Fallen trees in forest (rare)
            if tile == FOREST and rng.random() < 0.005:
                world.tiles[y][x] = 44  # FALLEN_TREE
