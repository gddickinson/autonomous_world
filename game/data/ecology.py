"""
Biome-creature ecology data: which creatures spawn where, at what rarity.

Used by world_manager.py for biome-aware creature spawning.
"""

from game.settings import (
    GRASS, FOREST, DENSE_FOREST, MOUNTAIN, SWAMP, SHALLOW_WATER,
    SAND, SNOW, WATER, FARMLAND,
)

# ================================================================
# BIOME -> CREATURE MAPPING
# ================================================================
# Each biome has common / uncommon / rare creature lists and weights
# that control the probability of picking each tier.

BIOME_CREATURES = {
    # Grassland
    GRASS: {
        "common": ["rabbit", "deer", "fox", "hawk", "squirrel", "crow",
                    "sheep", "cow", "pheasant", "frog"],
        "uncommon": ["horse", "elk", "wild_boar", "snake", "dog", "goat",
                     "boar", "wolf"],
        "rare": ["centaur", "unicorn", "manticore"],
        "weights": [60, 30, 10],
    },
    # Forest
    FOREST: {
        "common": ["deer", "rabbit", "squirrel", "owl", "fox", "wolf",
                    "pheasant", "crow"],
        "uncommon": ["bear", "wild_boar", "spider", "bat", "snake",
                     "boar", "bugbear"],
        "rare": ["dire_wolf", "giant_spider", "unicorn", "werewolf"],
        "weights": [50, 35, 15],
    },
    # Dense Forest
    DENSE_FOREST: {
        "common": ["wolf", "spider", "bat", "owl", "snake", "rat"],
        "uncommon": ["bear", "dire_wolf", "giant_spider", "wild_boar",
                     "bugbear", "skeleton"],
        "rare": ["troll", "basilisk", "wyvern", "owlbear", "vampire"],
        "weights": [40, 40, 20],
    },
    # Mountain
    MOUNTAIN: {
        "common": ["goat", "eagle", "hawk", "bat", "crow"],
        "uncommon": ["mountain_lion", "bear", "giant_scorpion", "kobold"],
        "rare": ["griffin", "wyvern", "young_dragon", "gargoyle"],
        "weights": [45, 40, 15],
    },
    # Swamp
    SWAMP: {
        "common": ["frog", "snake", "rat", "turtle", "bat", "crow"],
        "uncommon": ["crocodile", "giant_spider", "viper", "zombie", "skeleton"],
        "rare": ["basilisk", "troll", "harpy", "ghoul", "wraith"],
        "weights": [50, 35, 15],
    },
    # Shallow Water / Shore
    SHALLOW_WATER: {
        "common": ["fish", "frog", "turtle", "fish_school"],
        "uncommon": ["crocodile", "giant_crab"],
        "rare": [],
        "weights": [70, 30, 0],
    },
    # Water (deep)
    WATER: {
        "common": ["fish", "fish_school"],
        "uncommon": [],
        "rare": [],
        "weights": [100, 0, 0],
    },
    # Sand / Desert
    SAND: {
        "common": ["snake", "hawk", "rabbit", "rat"],
        "uncommon": ["giant_scorpion", "viper", "gnoll", "giant_crab"],
        "rare": ["basilisk", "phoenix"],
        "weights": [50, 35, 15],
    },
    # Snow
    SNOW: {
        "common": ["rabbit", "owl", "wolf"],
        "uncommon": ["dire_wolf", "bear", "elk"],
        "rare": ["phoenix", "wyvern"],
        "weights": [50, 35, 15],
    },
    # Farmland (near settlements)
    FARMLAND: {
        "common": ["chicken", "cow", "pig", "sheep", "dog", "cat",
                    "goat"],
        "uncommon": ["horse", "donkey", "rabbit"],
        "rare": [],
        "weights": [70, 30, 0],
    },
}

# ================================================================
# PACK BEHAVIOUR — creatures that spawn in groups
# ================================================================
PACK_CREATURES = {
    "wolf":     (2, 4),   # min, max group size
    "dire_wolf": (2, 3),
    "deer":     (3, 6),
    "rabbit":   (2, 4),
    "crow":     (3, 6),
    "fish":     (3, 5),
    "fish_school": (2, 3),
    "goblin":   (2, 4),
    "orc":      (2, 3),
    "skeleton": (2, 4),
    "kobold":   (3, 5),
    "bat":      (2, 5),
    "rat":      (2, 4),
}

# ================================================================
# NOCTURNAL CREATURES — only spawn at night (time_of_day > 0.75 or < 0.25)
# ================================================================
NOCTURNAL_CREATURES = {
    "bat", "owl", "rat", "shadow", "ghoul", "werewolf",
    "wight", "zombie", "skeleton", "vampire", "wraith", "lich",
}

# ================================================================
# UNDEAD CREATURES — for undead system spawn and identification
# ================================================================
UNDEAD_CREATURES = {
    "skeleton", "zombie", "ghoul", "wight", "wraith", "vampire", "lich",
}

# Undead power tiers (affects soul drain rate and combat)
UNDEAD_POWER = {
    "skeleton": 0.5,
    "zombie":   0.5,
    "ghoul":    1.0,
    "wight":    2.0,
    "wraith":   3.0,
    "vampire":  5.0,
    "lich":     8.0,
}

# ================================================================
# WATER-ONLY CREATURES — restricted to water/shallow_water tiles
# ================================================================
WATER_ONLY_CREATURES = {
    "fish", "fish_school",
}

# ================================================================
# SETTLEMENT CREATURES — spawned near settlements
# ================================================================
SETTLEMENT_CREATURES = {
    "common": ["chicken", "cow", "pig", "sheep", "dog", "cat", "goat"],
    "uncommon": ["horse", "donkey"],
    "guard": ["dog"],  # guard animals near settlement perimeter
}

# ================================================================
# PREDATOR-PREY RELATIONSHIPS (for ecosystem simulation)
# ================================================================
PREDATOR_PREY = {
    "wolf":          ["deer", "rabbit", "sheep", "elk", "pheasant"],
    "dire_wolf":     ["deer", "elk", "sheep", "cow", "rabbit"],
    "bear":          ["deer", "fish", "rabbit"],
    "fox":           ["rabbit", "chicken", "pheasant", "squirrel"],
    "mountain_lion": ["deer", "elk", "goat", "sheep"],
    "eagle":         ["rabbit", "squirrel", "snake", "fish"],
    "hawk":          ["rabbit", "squirrel", "rat", "frog"],
    "owl":           ["rat", "rabbit", "squirrel", "bat"],
    "snake":         ["rat", "frog", "rabbit"],
    "viper":         ["rat", "frog"],
    "crocodile":     ["fish", "deer", "frog"],
    "giant_spider":  ["rat", "bat", "rabbit"],
    "spider":        ["rat", "bat"],
    "wild_boar":     [],   # omnivore, not a predator in the usual sense
}

# Creatures that breed faster in spring
BREEDING_CREATURES = {
    "deer", "rabbit", "elk", "fox", "wolf", "sheep", "cow",
    "chicken", "pig", "goat", "horse", "squirrel", "frog",
    "pheasant", "crow", "rat",
}
