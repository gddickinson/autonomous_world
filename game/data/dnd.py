"""
D&D-inspired data tables: classes, races, spells, monsters, and equipment.
Based on AD&D/5e SRD rules adapted for real-time gameplay.
"""

import random
from typing import Dict, List, Tuple, Optional, Any

# ================================================================
# RACES
# ================================================================

RACES = {
    "Human": {
        "ability_mods": {"strength": 1, "dexterity": 1, "constitution": 1,
                         "intelligence": 1, "wisdom": 1, "charisma": 1},
        "speed_mod": 0, "hp_bonus": 0,
        "traits": ["Versatile", "Ambitious"],
        "description": "Adaptable and driven, humans are the most common race.",
    },
    "Elf": {
        "ability_mods": {"dexterity": 2, "intelligence": 1},
        "speed_mod": 0.2, "hp_bonus": 0,
        "traits": ["Darkvision", "Keen Senses", "Fey Ancestry"],
        "description": "Graceful and long-lived, with keen senses and affinity for magic.",
    },
    "Dwarf": {
        "ability_mods": {"constitution": 2, "strength": 1},
        "speed_mod": -0.1, "hp_bonus": 5,
        "traits": ["Darkvision", "Dwarven Resilience", "Stonecunning"],
        "description": "Stout and hardy, dwarves are master crafters and fierce warriors.",
    },
    "Halfling": {
        "ability_mods": {"dexterity": 2, "charisma": 1},
        "speed_mod": -0.1, "hp_bonus": 0,
        "traits": ["Lucky", "Brave", "Nimble"],
        "description": "Small and cheerful, halflings are surprisingly brave and lucky.",
    },
    "Half-Orc": {
        "ability_mods": {"strength": 2, "constitution": 1},
        "speed_mod": 0, "hp_bonus": 3,
        "traits": ["Darkvision", "Relentless Endurance", "Savage Attacks"],
        "description": "Powerful and intimidating, half-orcs excel in combat.",
    },
    "Gnome": {
        "ability_mods": {"intelligence": 2, "constitution": 1},
        "speed_mod": -0.1, "hp_bonus": 0,
        "traits": ["Darkvision", "Gnome Cunning", "Tinker"],
        "description": "Curious and inventive, gnomes love discovery and tinkering.",
    },
    "Half-Elf": {
        "ability_mods": {"charisma": 2, "dexterity": 1},
        "speed_mod": 0, "hp_bonus": 0,
        "traits": ["Darkvision", "Fey Ancestry", "Skill Versatility"],
        "description": "Combining human ambition with elven grace.",
    },
    "Tiefling": {
        "ability_mods": {"charisma": 2, "intelligence": 1},
        "speed_mod": 0, "hp_bonus": 0,
        "traits": ["Darkvision", "Hellish Resistance", "Infernal Legacy"],
        "description": "Bearing the mark of an infernal heritage, tieflings face distrust.",
    },
}

RACE_NAMES = list(RACES.keys())

# ================================================================
# CHARACTER CLASSES
# ================================================================

CLASSES = {
    "Fighter": {
        "hit_die": 10, "primary": ["strength", "constitution"],
        "armor": "all", "weapons": "all",
        "abilities": {
            1: ["Second Wind", "Fighting Style"],
            3: ["Action Surge"],
            5: ["Extra Attack"],
            7: ["Indomitable"],
        },
        "spellcaster": False,
        "description": "Masters of martial combat, trained in a variety of weapons and armor.",
        "quest_drive": "protect others and seek glory in battle",
        "preferred_actions": ["FIGHT", "MOVE_TO", "TRADE"],
    },
    "Wizard": {
        "hit_die": 6, "primary": ["intelligence", "wisdom"],
        "armor": "none", "weapons": "simple",
        "abilities": {
            1: ["Arcane Recovery", "Spellcasting"],
            2: ["Arcane Tradition"],
            5: ["Arcane Ward"],
        },
        "spellcaster": True, "spell_stat": "intelligence",
        "spell_slots": {1: [2,0,0], 3: [3,2,0], 5: [3,3,2]},
        "spell_list": ["Fire Bolt", "Light", "Mage Hand", "Magic Missile", "Shield",
                       "Burning Hands", "Detect Magic", "Mage Armor", "Scorching Ray",
                       "Misty Step", "Fireball", "Counterspell", "Lightning Bolt"],
        "description": "Scholarly practitioners of arcane magic.",
        "quest_drive": "pursue knowledge and magical power",
        "preferred_actions": ["TALK_TO", "MOVE_TO", "IDLE"],
    },
    "Cleric": {
        "hit_die": 8, "primary": ["wisdom", "charisma"],
        "armor": "medium", "weapons": "simple",
        "abilities": {
            1: ["Spellcasting", "Divine Domain"],
            2: ["Channel Divinity", "Turn Undead"],
            5: ["Destroy Undead"],
        },
        "spellcaster": True, "spell_stat": "wisdom",
        "spell_slots": {1: [2,0,0], 3: [3,2,0], 5: [3,3,2]},
        "spell_list": ["Sacred Flame", "Cure Wounds", "Bless", "Healing Word",
                       "Guiding Bolt", "Shield of Faith", "Spiritual Weapon",
                       "Prayer of Healing", "Revivify", "Spirit Guardians"],
        "description": "Divine agents who channel the power of their deity.",
        "quest_drive": "heal the sick and protect the faithful",
        "preferred_actions": ["TALK_TO", "TRADE", "MOVE_TO"],
    },
    "Rogue": {
        "hit_die": 8, "primary": ["dexterity", "intelligence"],
        "armor": "light", "weapons": "simple",
        "abilities": {
            1: ["Sneak Attack", "Thieves' Cant"],
            2: ["Cunning Action"],
            3: ["Roguish Archetype"],
            5: ["Uncanny Dodge"],
        },
        "spellcaster": False,
        "description": "Skilled in stealth, deception, and precise strikes.",
        "quest_drive": "find treasure and uncover secrets",
        "preferred_actions": ["MOVE_TO", "TRADE", "TALK_TO"],
    },
    "Ranger": {
        "hit_die": 10, "primary": ["dexterity", "wisdom"],
        "armor": "medium", "weapons": "all",
        "abilities": {
            1: ["Favored Enemy", "Natural Explorer"],
            2: ["Fighting Style", "Spellcasting"],
            3: ["Ranger Archetype", "Primeval Awareness"],
            5: ["Extra Attack"],
        },
        "spellcaster": True, "spell_stat": "wisdom",
        "spell_slots": {2: [2,0,0], 5: [3,2,0]},
        "spell_list": ["Hunter's Mark", "Cure Wounds", "Goodberry",
                       "Pass without Trace", "Spike Growth"],
        "description": "Warriors of the wilderness, skilled trackers and hunters.",
        "quest_drive": "patrol the wilds and protect nature",
        "preferred_actions": ["MOVE_TO", "FIGHT", "FORAGE", "CHOP_TREE"],
    },
    "Paladin": {
        "hit_die": 10, "primary": ["strength", "charisma"],
        "armor": "all", "weapons": "all",
        "abilities": {
            1: ["Divine Sense", "Lay on Hands"],
            2: ["Fighting Style", "Spellcasting", "Divine Smite"],
            3: ["Sacred Oath"],
            5: ["Extra Attack"],
        },
        "spellcaster": True, "spell_stat": "charisma",
        "spell_slots": {2: [2,0,0], 5: [3,2,0]},
        "spell_list": ["Bless", "Cure Wounds", "Shield of Faith",
                       "Branding Smite", "Aid"],
        "description": "Holy warriors bound by a sacred oath.",
        "quest_drive": "uphold justice and smite evil",
        "preferred_actions": ["FIGHT", "TALK_TO", "MOVE_TO"],
    },
    "Barbarian": {
        "hit_die": 12, "primary": ["strength", "constitution"],
        "armor": "medium", "weapons": "all",
        "abilities": {
            1: ["Rage", "Unarmored Defense"],
            2: ["Reckless Attack", "Danger Sense"],
            3: ["Primal Path"],
            5: ["Extra Attack", "Fast Movement"],
        },
        "spellcaster": False,
        "description": "Fierce warriors who channel primal fury in battle.",
        "quest_drive": "seek worthy foes and prove strength",
        "preferred_actions": ["FIGHT", "MOVE_TO", "FORAGE"],
    },
    "Bard": {
        "hit_die": 8, "primary": ["charisma", "dexterity"],
        "armor": "light", "weapons": "simple",
        "abilities": {
            1: ["Spellcasting", "Bardic Inspiration"],
            2: ["Jack of All Trades", "Song of Rest"],
            3: ["Bard College"],
            5: ["Font of Inspiration"],
        },
        "spellcaster": True, "spell_stat": "charisma",
        "spell_slots": {1: [2,0,0], 3: [3,2,0], 5: [3,3,2]},
        "spell_list": ["Vicious Mockery", "Healing Word", "Charm Person",
                       "Thunderwave", "Invisibility", "Shatter", "Hypnotic Pattern"],
        "description": "Versatile performers whose magic comes from music and stories.",
        "quest_drive": "collect stories and inspire others",
        "preferred_actions": ["TALK_TO", "PERSUADE", "MOVE_TO"],
    },
    "Druid": {
        "hit_die": 8, "primary": ["wisdom", "constitution"],
        "armor": "medium", "weapons": "simple",
        "abilities": {
            1: ["Druidic", "Spellcasting"],
            2: ["Wild Shape", "Druid Circle"],
            4: ["Wild Shape Improvement"],
        },
        "spellcaster": True, "spell_stat": "wisdom",
        "spell_slots": {1: [2,0,0], 3: [3,2,0], 5: [3,3,2]},
        "spell_list": ["Produce Flame", "Shillelagh", "Entangle", "Goodberry",
                       "Cure Wounds", "Moonbeam", "Barkskin", "Call Lightning"],
        "description": "Guardians of nature who draw power from the natural world.",
        "quest_drive": "protect nature and maintain balance",
        "preferred_actions": ["FORAGE", "FARM", "MOVE_TO", "TALK_TO"],
    },
    "Monk": {
        "hit_die": 8, "primary": ["dexterity", "wisdom"],
        "armor": "none", "weapons": "simple",
        "abilities": {
            1: ["Unarmored Defense", "Martial Arts"],
            2: ["Ki", "Flurry of Blows", "Patient Defense"],
            3: ["Monastic Tradition", "Deflect Missiles"],
            5: ["Extra Attack", "Stunning Strike"],
        },
        "spellcaster": False,
        "description": "Masters of martial arts who harness the power of body and mind.",
        "quest_drive": "achieve inner peace and physical perfection",
        "preferred_actions": ["IDLE", "MOVE_TO", "FIGHT"],
    },
    "Sorcerer": {
        "hit_die": 6, "primary": ["charisma", "constitution"],
        "armor": "none", "weapons": "simple",
        "abilities": {
            1: ["Spellcasting", "Sorcerous Origin"],
            2: ["Font of Magic", "Sorcery Points"],
            3: ["Metamagic"],
        },
        "spellcaster": True, "spell_stat": "charisma",
        "spell_slots": {1: [2,0,0], 3: [3,2,0], 5: [3,3,2]},
        "spell_list": ["Fire Bolt", "Ray of Frost", "Magic Missile", "Shield",
                       "Burning Hands", "Scorching Ray", "Fireball", "Fly"],
        "description": "Born with innate magical power flowing through their veins.",
        "quest_drive": "understand and master innate magical powers",
        "preferred_actions": ["TALK_TO", "MOVE_TO", "IDLE"],
    },
    "Warlock": {
        "hit_die": 8, "primary": ["charisma", "constitution"],
        "armor": "light", "weapons": "simple",
        "abilities": {
            1: ["Otherworldly Patron", "Pact Magic"],
            2: ["Eldritch Invocations"],
            3: ["Pact Boon"],
            5: ["Mystic Arcanum"],
        },
        "spellcaster": True, "spell_stat": "charisma",
        "spell_slots": {1: [1,0,0], 3: [2,0,0], 5: [2,2,0]},
        "spell_list": ["Eldritch Blast", "Hellish Rebuke", "Hex", "Armor of Agathys",
                       "Darkness", "Misty Step", "Hunger of Hadar"],
        "description": "Wielders of magic gained through a pact with an otherworldly being.",
        "quest_drive": "fulfill pact obligations and gain forbidden knowledge",
        "preferred_actions": ["TALK_TO", "MOVE_TO", "IDLE"],
    },
    "Commoner": {
        "hit_die": 6, "primary": ["constitution", "wisdom"],
        "armor": "none", "weapons": "simple",
        "abilities": {
            1: ["Jack of All Trades"],
        },
        "spellcaster": False,
        "description": "Ordinary folk — farmers, craftspeople, and laborers.",
        "quest_drive": "live a peaceful life and provide for their community",
        "preferred_actions": ["FARM", "TRADE", "IDLE", "TALK_TO"],
    },
}

CLASS_NAMES = list(CLASSES.keys())

# ================================================================
# SPELLS
# ================================================================

SPELLS = {
    # Cantrips (at-will)
    "Fire Bolt":       {"level": 0, "damage": 8,  "range": 6, "type": "fire",     "school": "evocation",    "save": None},
    "Sacred Flame":    {"level": 0, "damage": 6,  "range": 5, "type": "radiant",  "school": "evocation",    "save": "dexterity"},
    "Eldritch Blast":  {"level": 0, "damage": 8,  "range": 8, "type": "force",    "school": "evocation",    "save": None},
    "Ray of Frost":    {"level": 0, "damage": 6,  "range": 5, "type": "cold",     "school": "evocation",    "save": None},
    "Produce Flame":   {"level": 0, "damage": 6,  "range": 3, "type": "fire",     "school": "conjuration",  "save": None},
    "Vicious Mockery": {"level": 0, "damage": 4,  "range": 5, "type": "psychic",  "school": "enchantment",  "save": "wisdom"},
    "Poison Spray":    {"level": 0, "damage": 10, "range": 1, "type": "poison",   "school": "conjuration",  "save": "constitution"},
    "Shillelagh":      {"level": 0, "damage": 0,  "range": 0, "type": "buff",     "school": "transmutation","save": None},
    "Light":           {"level": 0, "damage": 0,  "range": 2, "type": "utility",  "school": "evocation",    "save": None},
    "Mage Hand":       {"level": 0, "damage": 0,  "range": 3, "type": "utility",  "school": "conjuration",  "save": None},
    # Level 1
    "Magic Missile":   {"level": 1, "damage": 10, "range": 8, "type": "force",    "school": "evocation",    "save": None},
    "Burning Hands":   {"level": 1, "damage": 12, "range": 2, "type": "fire",     "school": "evocation",    "save": "dexterity"},
    "Cure Wounds":     {"level": 1, "damage": -10,"range": 1, "type": "heal",     "school": "evocation",    "save": None},
    "Healing Word":    {"level": 1, "damage": -8, "range": 5, "type": "heal",     "school": "evocation",    "save": None},
    "Bless":           {"level": 1, "damage": 0,  "range": 3, "type": "buff",     "school": "enchantment",  "save": None},
    "Shield":          {"level": 1, "damage": 0,  "range": 0, "type": "buff",     "school": "abjuration",   "save": None},
    "Shield of Faith": {"level": 1, "damage": 0,  "range": 5, "type": "buff",     "school": "abjuration",   "save": None},
    "Mage Armor":      {"level": 1, "damage": 0,  "range": 0, "type": "buff",     "school": "abjuration",   "save": None},
    "Guiding Bolt":    {"level": 1, "damage": 14, "range": 8, "type": "radiant",  "school": "evocation",    "save": None},
    "Thunderwave":     {"level": 1, "damage": 10, "range": 2, "type": "thunder",  "school": "evocation",    "save": "constitution"},
    "Charm Person":    {"level": 1, "damage": 0,  "range": 3, "type": "control",  "school": "enchantment",  "save": "wisdom"},
    "Sleep":           {"level": 1, "damage": 0,  "range": 6, "type": "control",  "school": "enchantment",  "save": None},
    "Entangle":        {"level": 1, "damage": 0,  "range": 6, "type": "control",  "school": "conjuration",  "save": "strength"},
    "Hunter's Mark":   {"level": 1, "damage": 4,  "range": 6, "type": "buff",     "school": "divination",   "save": None},
    "Hex":             {"level": 1, "damage": 4,  "range": 6, "type": "necrotic", "school": "enchantment",  "save": None},
    "Goodberry":       {"level": 1, "damage": -5, "range": 0, "type": "heal",     "school": "transmutation","save": None},
    "Hellish Rebuke":  {"level": 1, "damage": 12, "range": 5, "type": "fire",     "school": "evocation",    "save": "dexterity"},
    "Detect Magic":    {"level": 1, "damage": 0,  "range": 3, "type": "utility",  "school": "divination",   "save": None},
    # Level 2
    "Scorching Ray":   {"level": 2, "damage": 18, "range": 8, "type": "fire",     "school": "evocation",    "save": None},
    "Spiritual Weapon":{"level": 2, "damage": 12, "range": 5, "type": "force",    "school": "evocation",    "save": None},
    "Misty Step":      {"level": 2, "damage": 0,  "range": 0, "type": "utility",  "school": "conjuration",  "save": None},
    "Moonbeam":        {"level": 2, "damage": 14, "range": 5, "type": "radiant",  "school": "evocation",    "save": "constitution"},
    "Shatter":         {"level": 2, "damage": 16, "range": 5, "type": "thunder",  "school": "evocation",    "save": "constitution"},
    "Hold Person":     {"level": 2, "damage": 0,  "range": 5, "type": "control",  "school": "enchantment",  "save": "wisdom"},
    "Invisibility":    {"level": 2, "damage": 0,  "range": 0, "type": "utility",  "school": "illusion",     "save": None},
    "Barkskin":        {"level": 2, "damage": 0,  "range": 0, "type": "buff",     "school": "transmutation","save": None},
    "Prayer of Healing":{"level":2, "damage": -12,"range": 3, "type": "heal",     "school": "evocation",    "save": None},
    "Aid":             {"level": 2, "damage": -8, "range": 3, "type": "heal",     "school": "abjuration",   "save": None},
    # Level 3
    "Fireball":        {"level": 3, "damage": 28, "range": 8, "type": "fire",     "school": "evocation",    "save": "dexterity"},
    "Lightning Bolt":  {"level": 3, "damage": 28, "range": 8, "type": "lightning","school": "evocation",    "save": "dexterity"},
    "Counterspell":    {"level": 3, "damage": 0,  "range": 5, "type": "utility",  "school": "abjuration",   "save": None},
    "Call Lightning":  {"level": 3, "damage": 22, "range": 8, "type": "lightning","school": "conjuration",  "save": "dexterity"},
    "Revivify":        {"level": 3, "damage": -30,"range": 1, "type": "heal",     "school": "necromancy",   "save": None},
    "Spirit Guardians":{"level": 3, "damage": 16, "range": 2, "type": "radiant",  "school": "conjuration",  "save": "wisdom"},
    "Hypnotic Pattern":{"level": 3, "damage": 0,  "range": 8, "type": "control",  "school": "illusion",     "save": "wisdom"},
}

# ================================================================
# MONSTERS (expanded with D&D types)
# ================================================================

MONSTERS = {
    # CR 0 - trivial
    "rat":          {"hp": 5,   "ac": 10, "damage": 2,  "speed": 2.0, "xp": 3,   "cr": 0,
                     "type": "beast", "color": (120, 100, 80), "biomes": ["floor", "swamp"],
                     "drops": [("Herbs", 0.1)]},
    # CR 1/4
    "goblin":       {"hp": 15,  "ac": 12, "damage": 5,  "speed": 2.2, "xp": 12,  "cr": 0.25,
                     "type": "humanoid", "color": (100, 130, 60), "biomes": ["forest", "dense_forest", "road"],
                     "drops": [("Gold Nugget", 0.3), ("Bread", 0.2)]},
    "skeleton":     {"hp": 20,  "ac": 13, "damage": 6,  "speed": 1.6, "xp": 15,  "cr": 0.25,
                     "type": "undead", "color": (200, 200, 190), "biomes": ["floor"],
                     "drops": [("Ancient Relic", 0.1), ("Iron Ore", 0.3)]},
    "wolf":         {"hp": 18,  "ac": 11, "damage": 6,  "speed": 2.5, "xp": 12,  "cr": 0.25,
                     "type": "beast", "color": (120, 110, 100), "biomes": ["forest", "dense_forest", "grass"],
                     "drops": [("Wolf Pelt", 0.6), ("Raw Meat", 0.5)]},
    "zombie":       {"hp": 25,  "ac": 8,  "damage": 5,  "speed": 1.0, "xp": 15,  "cr": 0.25,
                     "type": "undead", "color": (100, 120, 80), "biomes": ["floor", "swamp"],
                     "drops": [("Herbs", 0.2)]},
    "spider":       {"hp": 12,  "ac": 12, "damage": 4,  "speed": 2.5, "xp": 8,   "cr": 0.25,
                     "type": "beast", "color": (60, 50, 50), "biomes": ["dense_forest", "swamp"],
                     "drops": [("Herbs", 0.4)]},
    "kobold":       {"hp": 10,  "ac": 12, "damage": 4,  "speed": 2.0, "xp": 8,   "cr": 0.125,
                     "type": "humanoid", "color": (140, 100, 60), "biomes": ["mountain", "floor"],
                     "drops": [("Stone", 0.3)]},
    # CR 1/2
    "orc":          {"hp": 30,  "ac": 13, "damage": 9,  "speed": 2.0, "xp": 20,  "cr": 0.5,
                     "type": "humanoid", "color": (80, 110, 70), "biomes": ["forest", "grass", "road"],
                     "drops": [("Iron Sword", 0.15), ("Gold Nugget", 0.3), ("Cooked Meat", 0.2)]},
    "gnoll":        {"hp": 28,  "ac": 12, "damage": 8,  "speed": 2.0, "xp": 20,  "cr": 0.5,
                     "type": "humanoid", "color": (140, 120, 80), "biomes": ["grass", "sand"],
                     "drops": [("Wolf Pelt", 0.3), ("Bread", 0.3)]},
    "shadow":       {"hp": 20,  "ac": 12, "damage": 8,  "speed": 2.5, "xp": 20,  "cr": 0.5,
                     "type": "undead", "color": (40, 40, 60), "biomes": ["floor"],
                     "drops": [("Ancient Relic", 0.15)]},
    # CR 1
    "bugbear":      {"hp": 35,  "ac": 14, "damage": 12, "speed": 1.8, "xp": 30,  "cr": 1,
                     "type": "humanoid", "color": (130, 100, 60), "biomes": ["forest", "dense_forest"],
                     "drops": [("Iron Sword", 0.2), ("Gold Nugget", 0.4)]},
    "dire_wolf":    {"hp": 35,  "ac": 13, "damage": 10, "speed": 2.8, "xp": 30,  "cr": 1,
                     "type": "beast", "color": (80, 80, 90), "biomes": ["forest", "snow"],
                     "drops": [("Wolf Pelt", 0.8), ("Cooked Meat", 0.4)]},
    "ghoul":        {"hp": 28,  "ac": 12, "damage": 10, "speed": 1.8, "xp": 30,  "cr": 1,
                     "type": "undead", "color": (150, 160, 140), "biomes": ["floor"],
                     "drops": [("Ancient Relic", 0.2)]},
    "harpy":        {"hp": 32,  "ac": 11, "damage": 8,  "speed": 2.2, "xp": 30,  "cr": 1,
                     "type": "monstrosity", "color": (160, 130, 100), "biomes": ["mountain", "forest"],
                     "drops": [("Herbs", 0.3), ("Gold Nugget", 0.2)]},
    "boar":         {"hp": 22,  "ac": 11, "damage": 7,  "speed": 2.0, "xp": 15,  "cr": 0.25,
                     "type": "beast", "color": (110, 80, 60), "biomes": ["forest", "grass"],
                     "drops": [("Cooked Meat", 0.5), ("Bread", 0.2)]},
    # CR 2
    "ogre":         {"hp": 55,  "ac": 11, "damage": 15, "speed": 1.5, "xp": 45,  "cr": 2,
                     "type": "giant", "color": (140, 120, 90), "biomes": ["forest", "mountain"],
                     "drops": [("Gold Nugget", 0.5), ("Iron Armor", 0.1), ("Cooked Meat", 0.4)]},
    "gargoyle":     {"hp": 50,  "ac": 15, "damage": 10, "speed": 1.5, "xp": 45,  "cr": 2,
                     "type": "elemental", "color": (130, 130, 140), "biomes": ["mountain", "floor"],
                     "drops": [("Stone", 0.5), ("Ancient Relic", 0.15)]},
    "ankheg":       {"hp": 45,  "ac": 14, "damage": 12, "speed": 1.8, "xp": 45,  "cr": 2,
                     "type": "monstrosity", "color": (100, 120, 60), "biomes": ["grass", "farmland"],
                     "drops": [("Iron Ore", 0.3)]},
    "bear":         {"hp": 42,  "ac": 11, "damage": 12, "speed": 1.5, "xp": 30,  "cr": 1,
                     "type": "beast", "color": (100, 70, 40), "biomes": ["forest", "dense_forest"],
                     "drops": [("Raw Meat", 0.9), ("Raw Meat", 0.5), ("Wolf Pelt", 0.5)]},
    "bandit":       {"hp": 30,  "ac": 12, "damage": 8,  "speed": 1.8, "xp": 20,  "cr": 0.5,
                     "type": "humanoid", "color": (150, 50, 50), "biomes": ["forest", "road"],
                     "drops": [("Gold Nugget", 0.4), ("Iron Sword", 0.1), ("Health Potion", 0.3)]},
    # CR 3
    "owlbear":      {"hp": 60,  "ac": 13, "damage": 16, "speed": 1.6, "xp": 70,  "cr": 3,
                     "type": "monstrosity", "color": (120, 100, 70), "biomes": ["forest", "dense_forest"],
                     "drops": [("Wolf Pelt", 0.4), ("Cooked Meat", 0.6)]},
    "minotaur":     {"hp": 65,  "ac": 14, "damage": 18, "speed": 1.8, "xp": 70,  "cr": 3,
                     "type": "monstrosity", "color": (120, 80, 60), "biomes": ["floor"],
                     "drops": [("Iron Sword", 0.3), ("Gold Nugget", 0.5)]},
    "werewolf":     {"hp": 55,  "ac": 12, "damage": 14, "speed": 2.2, "xp": 70,  "cr": 3,
                     "type": "shapechanger", "color": (90, 90, 100), "biomes": ["forest"],
                     "drops": [("Wolf Pelt", 0.8), ("Gold Nugget", 0.3)]},
    "manticore":    {"hp": 68,  "ac": 14, "damage": 16, "speed": 2.0, "xp": 70,  "cr": 3,
                     "type": "monstrosity", "color": (160, 120, 80), "biomes": ["mountain", "grass"],
                     "drops": [("Gold Nugget", 0.6), ("Health Potion", 0.3)]},
    "wight":        {"hp": 45,  "ac": 14, "damage": 12, "speed": 1.8, "xp": 70,  "cr": 3,
                     "type": "undead", "color": (160, 160, 170), "biomes": ["floor"],
                     "drops": [("Ancient Relic", 0.3), ("Iron Sword", 0.2)]},
    "wraith":       {"hp": 67,  "ac": 13, "damage": 18, "speed": 2.5, "xp": 180, "cr": 5,
                     "type": "undead", "color": (80, 80, 120), "biomes": ["floor"],
                     "drops": [("Soul Gem", 0.4), ("Ancient Relic", 0.3)]},
    "vampire":      {"hp": 144, "ac": 16, "damage": 20, "speed": 2.0, "xp": 390, "cr": 7,
                     "type": "undead", "color": (120, 20, 30), "biomes": ["floor"],
                     "drops": [("Soul Gem", 0.6), ("Gold Nugget", 0.8), ("Ancient Relic", 0.5)]},
    "lich":         {"hp": 135, "ac": 17, "damage": 25, "speed": 1.5, "xp": 700, "cr": 10,
                     "type": "undead", "color": (60, 180, 60), "biomes": ["floor"],
                     "drops": [("Soul Gem", 0.8), ("Ancient Relic", 0.7), ("Greater Health Potion", 0.5)]},
    # CR 5+
    "troll":        {"hp": 84,  "ac": 15, "damage": 22, "speed": 1.8, "xp": 180, "cr": 5,
                     "type": "giant", "color": (70, 100, 60), "biomes": ["swamp", "forest"],
                     "drops": [("Gold Nugget", 0.7), ("Greater Health Potion", 0.3)]},
    "hill_giant":   {"hp": 105, "ac": 13, "damage": 28, "speed": 1.5, "xp": 180, "cr": 5,
                     "type": "giant", "color": (150, 130, 100), "biomes": ["mountain", "grass"],
                     "drops": [("Gold Nugget", 0.8), ("Iron Armor", 0.2), ("Greater Health Potion", 0.4)]},
    "young_dragon": {"hp": 120, "ac": 17, "damage": 30, "speed": 2.0, "xp": 390, "cr": 7,
                     "type": "dragon", "color": (180, 50, 50), "biomes": ["mountain"],
                     "drops": [("Gold Nugget", 1.0), ("Ancient Relic", 0.5),
                               ("Steel Sword", 0.3), ("Greater Health Potion", 0.5)]},
    # === PASSIVE / HUNTABLE ANIMALS ===
    # These flee from players instead of attacking. Killed for food and resources.
    "deer":         {"hp": 18,  "ac": 10, "damage": 0,  "speed": 3.0, "xp": 5,   "cr": 0,
                     "type": "beast", "color": (160, 130, 80), "biomes": ["forest", "grass"],
                     "drops": [("Raw Meat", 0.9), ("Raw Meat", 0.5), ("Wolf Pelt", 0.3)],
                     "passive": True},
    "rabbit":       {"hp": 6,   "ac": 10, "damage": 0,  "speed": 3.5, "xp": 2,   "cr": 0,
                     "type": "beast", "color": (170, 150, 120), "biomes": ["grass", "forest"],
                     "drops": [("Raw Meat", 0.8)],
                     "passive": True},
    "chicken":      {"hp": 6,   "ac": 8,  "damage": 0,  "speed": 1.5, "xp": 1,   "cr": 0,
                     "type": "beast", "color": (220, 200, 170), "biomes": ["grass", "farmland"],
                     "drops": [("Raw Meat", 0.7)],
                     "passive": True},
    "cow":          {"hp": 30,  "ac": 8,  "damage": 0,  "speed": 1.0, "xp": 5,   "cr": 0,
                     "type": "beast", "color": (140, 100, 70), "biomes": ["grass", "farmland"],
                     "drops": [("Raw Meat", 1.0), ("Raw Meat", 0.8), ("Leather", 0.5)],
                     "passive": True},
    "pig":          {"hp": 20,  "ac": 8,  "damage": 0,  "speed": 1.2, "xp": 4,   "cr": 0,
                     "type": "beast", "color": (200, 160, 140), "biomes": ["grass", "farmland"],
                     "drops": [("Raw Meat", 1.0), ("Raw Meat", 0.6)],
                     "passive": True},
    "sheep":        {"hp": 16,  "ac": 8,  "damage": 0,  "speed": 1.3, "xp": 3,   "cr": 0,
                     "type": "beast", "color": (230, 225, 210), "biomes": ["grass"],
                     "drops": [("Raw Meat", 0.7), ("Wolf Pelt", 0.5)],
                     "passive": True},
    "goat":         {"hp": 16,  "ac": 10, "damage": 2,  "speed": 1.5, "xp": 3,   "cr": 0,
                     "type": "beast", "color": (180, 170, 150), "biomes": ["grass", "mountain"],
                     "drops": [("Raw Meat", 0.8)],
                     "passive": True},
    "horse":        {"hp": 35,  "ac": 10, "damage": 3,  "speed": 4.0, "xp": 8,   "cr": 0.25,
                     "type": "beast", "color": (130, 90, 50), "biomes": ["grass"],
                     "drops": [("Raw Meat", 0.8), ("Leather", 0.6)],
                     "passive": True},
    "elk":          {"hp": 25,  "ac": 10, "damage": 4,  "speed": 2.8, "xp": 8,   "cr": 0.25,
                     "type": "beast", "color": (140, 110, 70), "biomes": ["forest", "grass"],
                     "drops": [("Raw Meat", 1.0), ("Raw Meat", 0.7), ("Wolf Pelt", 0.4)],
                     "passive": True},
    "pheasant":     {"hp": 3,   "ac": 10, "damage": 0,  "speed": 2.5, "xp": 2,   "cr": 0,
                     "type": "beast", "color": (150, 100, 60), "biomes": ["forest", "grass"],
                     "drops": [("Raw Meat", 0.6)],
                     "passive": True},
    "fox":          {"hp": 6,   "ac": 12, "damage": 2,  "speed": 3.0, "xp": 4,   "cr": 0,
                     "type": "beast", "color": (200, 120, 50), "biomes": ["forest", "grass"],
                     "drops": [("Raw Meat", 0.5), ("Wolf Pelt", 0.4)],
                     "passive": True},
    "fish_school":  {"hp": 5,   "ac": 8,  "damage": 0,  "speed": 1.5, "xp": 2,   "cr": 0,
                     "type": "beast", "color": (100, 140, 180), "biomes": ["sand"],
                     "drops": [("Fish", 1.0), ("Fish", 0.6)],
                     "passive": True},
    # Hostile animals that also drop food
    "wild_boar":    {"hp": 20,  "ac": 11, "damage": 6,  "speed": 2.0, "xp": 10,  "cr": 0.25,
                     "type": "beast", "color": (100, 75, 50), "biomes": ["forest", "dense_forest"],
                     "drops": [("Raw Meat", 1.0), ("Raw Meat", 0.6)]},
    "giant_crab":   {"hp": 15,  "ac": 13, "damage": 5,  "speed": 1.5, "xp": 8,   "cr": 0.125,
                     "type": "beast", "color": (180, 80, 60), "biomes": ["sand"],
                     "drops": [("Raw Meat", 0.8)]},
    # === ADDITIONAL DOMESTIC ANIMALS ===
    "donkey":       {"hp": 28,  "ac": 10, "damage": 2,  "speed": 1.5, "xp": 5,   "cr": 0,
                     "type": "beast", "color": (130, 120, 110), "biomes": ["grass", "farmland"],
                     "drops": [("Raw Meat", 0.6), ("Leather", 0.4)],
                     "passive": True},
    "dog":          {"hp": 16,  "ac": 10, "damage": 4,  "speed": 2.5, "xp": 5,   "cr": 0.125,
                     "type": "beast", "color": (150, 120, 80), "biomes": ["grass", "farmland"],
                     "drops": [("Raw Meat", 0.4)],
                     "passive": True},
    "cat":          {"hp": 8,   "ac": 12, "damage": 1,  "speed": 2.0, "xp": 2,   "cr": 0,
                     "type": "beast", "color": (170, 140, 100), "biomes": ["grass", "farmland"],
                     "drops": [],
                     "passive": True},
    # === ADDITIONAL WILDLIFE ===
    "hawk":         {"hp": 8,   "ac": 12, "damage": 4,  "speed": 3.5, "xp": 5,   "cr": 0.125,
                     "type": "beast", "color": (120, 100, 80), "biomes": ["grass", "mountain"],
                     "drops": [("Raw Meat", 0.4)],
                     "passive": True},
    "eagle":        {"hp": 12,  "ac": 12, "damage": 5,  "speed": 3.5, "xp": 8,   "cr": 0.25,
                     "type": "beast", "color": (100, 80, 60), "biomes": ["mountain", "grass"],
                     "drops": [("Raw Meat", 0.5)],
                     "passive": True},
    "crow":         {"hp": 4,   "ac": 12, "damage": 1,  "speed": 2.8, "xp": 1,   "cr": 0,
                     "type": "beast", "color": (30, 30, 35), "biomes": ["grass", "forest", "swamp"],
                     "drops": [],
                     "passive": True},
    "snake":        {"hp": 6,   "ac": 12, "damage": 3,  "speed": 1.8, "xp": 4,   "cr": 0.125,
                     "type": "beast", "color": (80, 120, 60), "biomes": ["forest", "swamp", "sand"],
                     "drops": [("Herbs", 0.3)]},
    "frog":         {"hp": 2,   "ac": 10, "damage": 0,  "speed": 1.5, "xp": 1,   "cr": 0,
                     "type": "beast", "color": (60, 140, 50), "biomes": ["swamp", "grass"],
                     "drops": [],
                     "passive": True},
    "fish":         {"hp": 3,   "ac": 8,  "damage": 0,  "speed": 2.0, "xp": 2,   "cr": 0,
                     "type": "beast", "color": (100, 150, 180), "biomes": ["water"],
                     "drops": [("Fish", 0.9)],
                     "passive": True},
    "turtle":       {"hp": 12,  "ac": 14, "damage": 1,  "speed": 0.5, "xp": 3,   "cr": 0,
                     "type": "beast", "color": (80, 100, 60), "biomes": ["swamp", "sand"],
                     "drops": [("Raw Meat", 0.5)],
                     "passive": True},
    "owl":          {"hp": 8,   "ac": 11, "damage": 3,  "speed": 2.0, "xp": 4,   "cr": 0.125,
                     "type": "beast", "color": (140, 130, 110), "biomes": ["forest", "dense_forest"],
                     "drops": [],
                     "passive": True},
    "bat":          {"hp": 4,   "ac": 12, "damage": 1,  "speed": 2.5, "xp": 2,   "cr": 0,
                     "type": "beast", "color": (60, 50, 50), "biomes": ["dense_forest", "floor"],
                     "drops": [],
                     "passive": True},
    "squirrel":     {"hp": 2,   "ac": 12, "damage": 0,  "speed": 3.0, "xp": 1,   "cr": 0,
                     "type": "beast", "color": (160, 100, 50), "biomes": ["forest", "grass"],
                     "drops": [],
                     "passive": True},
    # === DANGEROUS PREDATORS ===
    "mountain_lion": {"hp": 35, "ac": 13, "damage": 10, "speed": 2.8, "xp": 25,  "cr": 1,
                     "type": "beast", "color": (180, 150, 100), "biomes": ["mountain", "forest"],
                     "drops": [("Raw Meat", 0.8), ("Wolf Pelt", 0.6)]},
    "giant_spider": {"hp": 26,  "ac": 14, "damage": 8,  "speed": 2.0, "xp": 20,  "cr": 1,
                     "type": "beast", "color": (50, 45, 40), "biomes": ["dense_forest", "floor"],
                     "drops": [("Herbs", 0.5)]},
    "giant_scorpion": {"hp": 30, "ac": 15, "damage": 10, "speed": 1.5, "xp": 22, "cr": 1,
                     "type": "beast", "color": (100, 70, 40), "biomes": ["sand", "mountain"],
                     "drops": [("Herbs", 0.4)]},
    "crocodile":    {"hp": 40,  "ac": 12, "damage": 12, "speed": 1.2, "xp": 28,  "cr": 1,
                     "type": "beast", "color": (70, 90, 50), "biomes": ["swamp"],
                     "drops": [("Raw Meat", 0.8), ("Leather", 0.5)]},
    "viper":        {"hp": 10,  "ac": 13, "damage": 7,  "speed": 1.5, "xp": 10,  "cr": 0.5,
                     "type": "beast", "color": (60, 80, 40), "biomes": ["swamp", "sand"],
                     "drops": [("Herbs", 0.5)]},
    # === MYTHICAL / FANTASY CREATURES ===
    "griffin":      {"hp": 75,  "ac": 14, "damage": 18, "speed": 3.0, "xp": 60,  "cr": 4,
                     "type": "monstrosity", "color": (180, 160, 80), "biomes": ["mountain"],
                     "drops": [("Gold Nugget", 0.8), ("Greater Health Potion", 0.3)]},
    "wyvern":       {"hp": 70,  "ac": 13, "damage": 16, "speed": 2.8, "xp": 50,  "cr": 4,
                     "type": "dragon", "color": (80, 100, 60), "biomes": ["mountain"],
                     "drops": [("Gold Nugget", 0.7), ("Health Potion", 0.4)]},
    "basilisk":     {"hp": 55,  "ac": 15, "damage": 14, "speed": 1.5, "xp": 45,  "cr": 3,
                     "type": "monstrosity", "color": (60, 80, 50), "biomes": ["dense_forest", "swamp"],
                     "drops": [("Ancient Relic", 0.3), ("Herbs", 0.5)]},
    "phoenix":      {"hp": 50,  "ac": 16, "damage": 14, "speed": 3.5, "xp": 55,  "cr": 5,
                     "type": "elemental", "color": (240, 160, 40), "biomes": ["mountain", "sand"],
                     "drops": [("Ancient Relic", 0.5), ("Greater Health Potion", 0.5)]},
    "unicorn":      {"hp": 40,  "ac": 14, "damage": 10, "speed": 3.0, "xp": 35,  "cr": 3,
                     "type": "celestial", "color": (240, 240, 250), "biomes": ["forest"],
                     "drops": [("Greater Health Potion", 0.6), ("Herbs", 0.8)],
                     "passive": True},
    "centaur":      {"hp": 45,  "ac": 13, "damage": 12, "speed": 2.8, "xp": 30,  "cr": 2,
                     "type": "monstrosity", "color": (160, 140, 110), "biomes": ["grass", "forest"],
                     "drops": [("Longbow", 0.2), ("Health Potion", 0.3)]},
}

MONSTER_NAMES = list(MONSTERS.keys())

# Biome mapping for terrain constants
BIOME_MAP = {
    "grass": 2, "forest": 3, "dense_forest": 4, "mountain": 5,
    "snow": 6, "road": 7, "floor": 8, "sand": 1, "swamp": 12,
    "farmland": 11, "water": 0, "shallow_water": 40,
}

# ================================================================
# EQUIPMENT
# ================================================================

WEAPONS = {
    "Dagger":          {"damage": 4,  "type": "simple",  "range": 1, "value": 5,   "weight": 1},
    "Handaxe":         {"damage": 6,  "type": "simple",  "range": 1, "value": 8,   "weight": 2},
    "Mace":            {"damage": 6,  "type": "simple",  "range": 1, "value": 8,   "weight": 4},
    "Quarterstaff":    {"damage": 6,  "type": "simple",  "range": 1, "value": 3,   "weight": 4},
    "Spear":           {"damage": 6,  "type": "simple",  "range": 2, "value": 5,   "weight": 3},
    "Light Crossbow":  {"damage": 8,  "type": "simple",  "range": 6, "value": 25,  "weight": 5},
    "Shortsword":      {"damage": 6,  "type": "martial", "range": 1, "value": 20,  "weight": 2},
    "Longsword":       {"damage": 8,  "type": "martial", "range": 1, "value": 30,  "weight": 3},
    "Greatsword":      {"damage": 12, "type": "martial", "range": 1, "value": 50,  "weight": 6},
    "Battleaxe":       {"damage": 8,  "type": "martial", "range": 1, "value": 25,  "weight": 4},
    "Warhammer":       {"damage": 8,  "type": "martial", "range": 1, "value": 30,  "weight": 5},
    "Rapier":          {"damage": 8,  "type": "martial", "range": 1, "value": 35,  "weight": 2},
    "Longbow":         {"damage": 8,  "type": "martial", "range": 8, "value": 50,  "weight": 2},
    "Heavy Crossbow":  {"damage": 10, "type": "martial", "range": 7, "value": 50,  "weight": 8},
    "Halberd":         {"damage": 10, "type": "martial", "range": 2, "value": 40,  "weight": 6},
}

ARMOR = {
    "Padded":      {"ac": 1,  "type": "light",  "value": 10,  "weight": 8},
    "Leather":     {"ac": 2,  "type": "light",  "value": 20,  "weight": 10},
    "Studded":     {"ac": 3,  "type": "light",  "value": 45,  "weight": 13},
    "Chain Shirt": {"ac": 4,  "type": "medium", "value": 50,  "weight": 20},
    "Scale Mail":  {"ac": 5,  "type": "medium", "value": 50,  "weight": 45},
    "Breastplate": {"ac": 6,  "type": "medium", "value": 200, "weight": 20},
    "Half Plate":  {"ac": 7,  "type": "medium", "value": 250, "weight": 40},
    "Chain Mail":  {"ac": 8,  "type": "heavy",  "value": 75,  "weight": 55},
    "Splint":      {"ac": 9,  "type": "heavy",  "value": 200, "weight": 60},
    "Plate":       {"ac": 10, "type": "heavy",  "value": 500, "weight": 65},
    "Shield":      {"ac": 2,  "type": "shield", "value": 10,  "weight": 6},
}


# ================================================================
# HELPER FUNCTIONS
# ================================================================

def roll_ability_scores(race: str, char_class: str) -> Dict[str, int]:
    """Generate ability scores: 4d6 drop lowest, apply race mods, boost class primary."""
    scores = {}
    for attr in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"):
        rolls = sorted([random.randint(1, 6) for _ in range(4)], reverse=True)
        scores[attr] = sum(rolls[:3])

    # Race mods
    race_data = RACES.get(race, {})
    for attr, mod in race_data.get("ability_mods", {}).items():
        scores[attr] = min(20, scores.get(attr, 10) + mod)

    # Ensure primary stats are decent
    class_data = CLASSES.get(char_class, {})
    for primary in class_data.get("primary", []):
        if scores.get(primary, 10) < 12:
            scores[primary] = random.randint(12, 16)

    return scores


def ability_modifier(score: int) -> int:
    """D&D ability modifier: (score - 10) // 2"""
    return (score - 10) // 2


def get_class_hp(char_class: str, level: int, con_mod: int) -> int:
    """Calculate HP for a class at given level."""
    class_data = CLASSES.get(char_class, {})
    hit_die = class_data.get("hit_die", 8)
    # Level 1: max hit die + con_mod, higher levels: average + con_mod
    hp = hit_die + con_mod
    for _ in range(1, level):
        hp += max(1, hit_die // 2 + 1 + con_mod)
    return max(1, hp)


def get_class_abilities(char_class: str, level: int) -> List[str]:
    """Get all abilities unlocked at or below the given level."""
    class_data = CLASSES.get(char_class, {})
    abilities = []
    for lvl, ability_list in class_data.get("abilities", {}).items():
        if lvl <= level:
            abilities.extend(ability_list)
    return abilities


def get_proficiency_bonus(level: int) -> int:
    """D&D proficiency bonus by level."""
    if level < 5:
        return 2
    elif level < 9:
        return 3
    elif level < 13:
        return 4
    elif level < 17:
        return 5
    return 6


def get_appropriate_monsters(player_level: int, biome_type: int) -> List[str]:
    """Get monsters appropriate for a biome and level range."""
    biome_name = None
    for name, val in BIOME_MAP.items():
        if val == biome_type:
            biome_name = name
            break
    if not biome_name:
        return []

    result = []
    max_cr = player_level * 0.5 + 1
    for name, stats in MONSTERS.items():
        if stats["cr"] <= max_cr and biome_name in stats.get("biomes", []):
            result.append(name)
    return result


def random_npc_class_and_race() -> Tuple[str, str]:
    """Pick a weighted-random class and race for an NPC."""
    # Weight toward common martial classes; spellcasters should be ~15-20%
    class_weights = {
        "Fighter": 25, "Rogue": 15, "Barbarian": 12, "Monk": 10,
        "Ranger": 3, "Paladin": 3, "Cleric": 3, "Bard": 2,
        "Druid": 2, "Wizard": 2, "Sorcerer": 1, "Warlock": 1,
    }
    classes = list(class_weights.keys())
    weights = [class_weights[c] for c in classes]
    char_class = random.choices(classes, weights=weights, k=1)[0]

    # Weight toward common races
    race_weights = {
        "Human": 30, "Elf": 15, "Dwarf": 15, "Halfling": 12,
        "Half-Elf": 8, "Gnome": 7, "Half-Orc": 7, "Tiefling": 6,
    }
    races = list(race_weights.keys())
    rweights = [race_weights[r] for r in races]
    race = random.choices(races, weights=rweights, k=1)[0]

    return char_class, race
