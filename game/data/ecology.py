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
        "common": ["rabbit", "rabbit", "deer", "deer", "fox", "fox",
                    "hawk", "squirrel", "crow", "pheasant", "frog"],
        "uncommon": ["horse", "elk", "wild_boar", "snake", "goat",
                     "boar", "wolf"],
        "rare": ["centaur", "unicorn", "manticore"],
        "weights": [60, 30, 10],
    },
    # Forest
    FOREST: {
        "common": ["deer", "deer", "rabbit", "rabbit", "squirrel", "owl",
                    "fox", "fox", "wolf", "wolf", "pheasant", "crow", "boar"],
        "uncommon": ["bear", "wild_boar", "spider", "bat", "snake",
                     "bugbear"],
        "rare": ["dire_wolf", "giant_spider", "unicorn", "werewolf"],
        "weights": [55, 30, 15],
    },
    # Dense Forest
    DENSE_FOREST: {
        "common": ["wolf", "spider", "bat", "owl", "snake", "rat"],
        "uncommon": ["bear", "dire_wolf", "giant_spider", "wild_boar",
                     "bugbear", "skeleton"],
        "rare": ["troll", "basilisk", "wyvern", "owlbear"],
        "weights": [40, 40, 20],
    },
    # Mountain
    MOUNTAIN: {
        "common": ["goat", "goat", "eagle", "eagle", "hawk", "hawk",
                    "bat", "crow"],
        "uncommon": ["mountain_lion", "bear", "bear", "giant_scorpion",
                     "kobold"],
        "rare": ["griffin", "wyvern", "young_dragon", "gargoyle"],
        "weights": [50, 35, 15],
    },
    # Swamp
    SWAMP: {
        "common": ["frog", "snake", "snake", "rat", "turtle", "bat",
                    "crow", "viper"],
        "uncommon": ["crocodile", "giant_spider", "zombie", "skeleton"],
        "rare": ["basilisk", "troll", "harpy", "ghoul"],
        "weights": [55, 30, 15],
    },
    # Shallow Water / Shore
    SHALLOW_WATER: {
        "common": ["frog", "turtle"],
        "uncommon": ["fish", "giant_crab"],
        "rare": [],
        "weights": [65, 35, 0],
        "spawn_chance": 0.4,   # reduced from 1.0 — fewer aquatic spawns
    },
    # Water (deep) — most water tiles produce nothing; fish are rare
    WATER: {
        "common": [],
        "uncommon": ["fish"],
        "rare": [],
        "weights": [0, 100, 0],
        "spawn_chance": 0.03,  # heavily reduced — fish were 53% of all creatures
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
    "fish":     (1, 2),
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
    "fish",
}

# ================================================================
# SETTLEMENT CREATURES — spawned near settlements
# ================================================================
# Base pool used by all settlement types
SETTLEMENT_CREATURES = {
    "common": ["chicken", "cow", "pig", "sheep", "dog", "cat", "goat"],
    "uncommon": ["horse", "donkey"],
    "guard": ["dog"],  # guard animals near settlement perimeter
}

# Per-settlement-type domestic animal tables with (kind, min, max) counts
SETTLEMENT_DOMESTIC = {
    "hamlet": {
        "always": [("dog", 1, 2), ("cat", 1, 1)],
        "farm":   [("chicken", 2, 4), ("pig", 1, 2), ("cow", 1, 1), ("sheep", 1, 3)],
    },
    "village": {
        "always": [("dog", 1, 2), ("cat", 1, 2)],
        "farm":   [("chicken", 3, 5), ("pig", 2, 3), ("cow", 1, 2),
                   ("sheep", 2, 4), ("goat", 1, 2)],
    },
    "town": {
        "always": [("dog", 2, 3), ("cat", 1, 3)],
        "farm":   [("chicken", 3, 5), ("pig", 2, 3), ("cow", 1, 2), ("sheep", 2, 4)],
        "stable": [("horse", 2, 4), ("donkey", 1, 2)],
    },
    "city": {
        "always": [("dog", 2, 4), ("cat", 2, 4)],
        "farm":   [("chicken", 2, 3), ("pig", 1, 2), ("cow", 1, 1)],
        "stable": [("horse", 3, 5), ("donkey", 1, 2)],
    },
    "castle": {
        "always": [("dog", 2, 3), ("cat", 1, 2)],
        "stable": [("horse", 3, 5)],
    },
}

# High-CR undead restricted to ruins/graveyards only
HIGH_CR_UNDEAD = {"lich", "vampire", "wraith", "shadow"}

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
