"""
Character skill system — unified for NPCs and Players.

48 skills across 7 categories. Skills affect:
- Action success via D20 skill checks (roll + skill_level + ability_modifier vs DC)
- Crafting quality and speed
- Combat effectiveness and options
- Social outcomes (persuasion, intimidation, deception)
- Economic productivity and trade prices
- Magic power and ritual success

NPCs learn skills through practice, teaching, books, and experience.
Players learn through use (gain_skill_xp on relevant actions).
"""

import random
from typing import Dict, List, Optional, Tuple


# ================================================================
# SKILL CATEGORIES
# ================================================================

SKILL_CATEGORIES = {
    "social":   ["persuasion", "intimidation", "deception", "performance", "insight",
                 "trading", "leadership"],
    "stealth":  ["lockpicking", "pickpocketing", "stealth", "trap_making", "disguise"],
    "combat":   ["swordsmanship", "archery", "shield_work", "unarmed", "mounted_combat",
                 "hunting"],
    "knowledge":["arcana", "history", "religion", "nature_lore", "medicine", "literacy"],
    "craft":    ["smithing", "woodcraft", "cooking", "brewing", "alchemy", "leatherwork",
                 "weaving", "jewelcraft", "pottery", "glassblowing", "tanning", "dyeing",
                 "enchanting", "siege_engineering", "shipbuilding", "cartography"],
    "survival": ["farming", "mining", "fishing", "herbalism", "animal_care", "masonry",
                 "tracking", "navigation", "climbing", "swimming", "animal_training"],
    "magic":    ["spellcraft", "ritual_magic", "warding", "divination"],
}


# ================================================================
# SKILL DEFINITIONS — each skill's governing stat + training activities
# ================================================================

NPC_SKILLS = {
    # -- Social --
    "persuasion":      {"stat": "charisma",     "category": "social",
                        "activities": ["persuading", "trading", "negotiating"]},
    "intimidation":    {"stat": "charisma",     "category": "social",
                        "activities": ["threatening", "commanding", "interrogating"]},
    "deception":       {"stat": "charisma",     "category": "social",
                        "activities": ["lying", "disguising", "bluffing"]},
    "performance":     {"stat": "charisma",     "category": "social",
                        "activities": ["performing", "singing", "storytelling"]},
    "insight":         {"stat": "wisdom",       "category": "social",
                        "activities": ["observing", "interrogating", "counseling"]},
    "trading":         {"stat": "charisma",     "category": "social",
                        "activities": ["trading", "bartering", "appraising"]},
    "leadership":      {"stat": "charisma",     "category": "social",
                        "activities": ["commanding", "persuading", "teaching"]},
    # -- Stealth --
    "lockpicking":     {"stat": "dexterity",    "category": "stealth",
                        "activities": ["picking_locks", "disabling_traps"]},
    "pickpocketing":   {"stat": "dexterity",    "category": "stealth",
                        "activities": ["stealing", "sleight_of_hand"]},
    "stealth":         {"stat": "dexterity",    "category": "stealth",
                        "activities": ["sneaking", "hiding", "shadowing"]},
    "trap_making":     {"stat": "dexterity",    "category": "stealth",
                        "activities": ["crafting_traps", "rigging"]},
    "disguise":        {"stat": "charisma",     "category": "stealth",
                        "activities": ["disguising", "impersonating"]},
    # -- Combat --
    "swordsmanship":   {"stat": "strength",     "category": "combat",
                        "activities": ["sparring", "training_melee", "fighting"]},
    "archery":         {"stat": "dexterity",    "category": "combat",
                        "activities": ["target_shooting", "archery_practice", "hunting"]},
    "shield_work":     {"stat": "strength",     "category": "combat",
                        "activities": ["sparring", "blocking_practice", "drilling"]},
    "unarmed":         {"stat": "strength",     "category": "combat",
                        "activities": ["sparring", "wrestling", "exercising"]},
    "mounted_combat":  {"stat": "dexterity",    "category": "combat",
                        "activities": ["horse_training", "jousting", "mounted_patrol"]},
    "hunting":         {"stat": "dexterity",    "category": "combat",
                        "activities": ["hunting", "tracking", "trapping"]},
    # -- Knowledge --
    "arcana":          {"stat": "intelligence", "category": "knowledge",
                        "activities": ["studying", "researching", "spell_analysis"]},
    "history":         {"stat": "intelligence", "category": "knowledge",
                        "activities": ["reading", "researching", "studying"]},
    "religion":        {"stat": "wisdom",       "category": "knowledge",
                        "activities": ["praying", "meditating", "preaching"]},
    "nature_lore":     {"stat": "wisdom",       "category": "knowledge",
                        "activities": ["foraging", "observing_nature", "studying"]},
    "medicine":        {"stat": "wisdom",       "category": "knowledge",
                        "activities": ["healing", "treating", "surgery"]},
    "literacy":        {"stat": "intelligence", "category": "knowledge",
                        "activities": ["reading", "studying", "writing"]},
    # -- Craft --
    "smithing":        {"stat": "strength",     "category": "craft",
                        "activities": ["crafting_forge", "smelting", "forging"]},
    "woodcraft":       {"stat": "dexterity",    "category": "craft",
                        "activities": ["chopping", "crafting_workshop", "carpentry"]},
    "cooking":         {"stat": "wisdom",       "category": "craft",
                        "activities": ["crafting_kitchen", "baking"]},
    "brewing":         {"stat": "wisdom",       "category": "craft",
                        "activities": ["crafting_brewery", "fermenting", "distilling"]},
    "alchemy":         {"stat": "intelligence", "category": "craft",
                        "activities": ["crafting_alchemy", "potion_brewing"]},
    "leatherwork":     {"stat": "dexterity",    "category": "craft",
                        "activities": ["crafting_workshop", "tanning"]},
    "weaving":         {"stat": "dexterity",    "category": "craft",
                        "activities": ["crafting_loom", "spinning", "dyeing"]},
    "jewelcraft":      {"stat": "dexterity",    "category": "craft",
                        "activities": ["crafting_jeweler", "gem_cutting"]},
    "pottery":         {"stat": "dexterity",    "category": "craft",
                        "activities": ["crafting_pottery", "glazing"]},
    "glassblowing":    {"stat": "dexterity",    "category": "craft",
                        "activities": ["crafting_glassworks", "glass_cutting"]},
    "tanning":         {"stat": "constitution", "category": "craft",
                        "activities": ["tanning", "curing_hides"]},
    "dyeing":          {"stat": "dexterity",    "category": "craft",
                        "activities": ["dyeing", "color_mixing"]},
    "enchanting":      {"stat": "intelligence", "category": "craft",
                        "activities": ["enchanting", "inscribing"]},
    "siege_engineering":{"stat": "intelligence","category": "craft",
                        "activities": ["siege_building", "fortification"]},
    "shipbuilding":    {"stat": "strength",     "category": "craft",
                        "activities": ["shipwright_work", "rigging"]},
    "cartography":     {"stat": "intelligence", "category": "craft",
                        "activities": ["map_making", "surveying"]},
    # -- Survival --
    "farming":         {"stat": "constitution", "category": "survival",
                        "activities": ["farming", "foraging", "planting"]},
    "mining":          {"stat": "strength",     "category": "survival",
                        "activities": ["mining", "quarrying"]},
    "fishing":         {"stat": "dexterity",    "category": "survival",
                        "activities": ["fishing", "net_casting"]},
    "herbalism":       {"stat": "wisdom",       "category": "survival",
                        "activities": ["foraging", "crafting_alchemy", "herb_growing"]},
    "animal_care":     {"stat": "wisdom",       "category": "survival",
                        "activities": ["milking", "herding", "feeding"]},
    "masonry":         {"stat": "strength",     "category": "survival",
                        "activities": ["building", "quarrying", "stone_cutting"]},
    "tracking":        {"stat": "wisdom",       "category": "survival",
                        "activities": ["tracking", "hunting", "scouting"]},
    "navigation":      {"stat": "intelligence", "category": "survival",
                        "activities": ["exploring", "pathfinding", "surveying"]},
    "climbing":        {"stat": "strength",     "category": "survival",
                        "activities": ["climbing", "mountaineering"]},
    "swimming":        {"stat": "constitution", "category": "survival",
                        "activities": ["swimming", "diving"]},
    "animal_training": {"stat": "wisdom",       "category": "survival",
                        "activities": ["animal_training", "horse_training", "taming"]},
    # -- Finance --
    "accountancy":     {"stat": "intelligence", "category": "knowledge",
                        "activities": ["bookkeeping", "auditing", "calculating"]},
    "appraisal":       {"stat": "wisdom",       "category": "knowledge",
                        "activities": ["appraising", "valuing", "assessing"]},
    # -- Magic --
    "spellcraft":      {"stat": "intelligence", "category": "magic",
                        "activities": ["spell_study", "spell_analysis", "casting"]},
    "ritual_magic":    {"stat": "intelligence", "category": "magic",
                        "activities": ["ritual_casting", "circle_drawing"]},
    "warding":         {"stat": "wisdom",       "category": "magic",
                        "activities": ["warding", "protection_magic"]},
    "divination":      {"stat": "wisdom",       "category": "magic",
                        "activities": ["divining", "scrying", "meditating"]},
}

ALL_SKILL_NAMES = sorted(NPC_SKILLS.keys())


# ================================================================
# D20 SKILL CHECK
# ================================================================

def ability_modifier_from_score(score: int) -> int:
    """D&D ability modifier: (score - 10) // 2."""
    return (score - 10) // 2


def get_skill_level(entity, skill: str) -> int:
    """Get skill level from an entity (works for both Player and NPC)."""
    # NPC: npc_skills dict
    if hasattr(entity, 'npc_skills'):
        return entity.npc_skills.get(skill, 0)
    # Player: skills dict
    if hasattr(entity, 'skills'):
        return entity.skills.get(skill, 0)
    return 0


def get_ability_score(entity, ability: str) -> int:
    """Get raw ability score from an entity."""
    if hasattr(entity, 'ability_scores'):
        return entity.ability_scores.get(ability, 10)
    return 10


def skill_check(entity, skill: str, dc: int) -> Tuple[bool, int, int]:
    """Roll D20 + skill_level + ability_modifier vs DC.

    Returns (success, total, natural_roll).
    Natural 20 always succeeds, natural 1 always fails.
    """
    skill_level = get_skill_level(entity, skill)
    stat_name = NPC_SKILLS.get(skill, {}).get("stat", "intelligence")
    ability_score = get_ability_score(entity, stat_name)
    mod = ability_modifier_from_score(ability_score)

    natural = random.randint(1, 20)
    total = natural + skill_level + mod

    if natural == 20:
        return (True, total, natural)
    if natural == 1:
        return (False, total, natural)
    return (total >= dc, total, natural)


def skill_check_contested(entity1, skill1: str, entity2, skill2: str) -> bool:
    """Contested skill check: entity1 rolls skill1 vs entity2's skill2.
    Returns True if entity1 wins.
    """
    s1, t1, n1 = skill_check(entity1, skill1, 0)
    s2, t2, n2 = skill_check(entity2, skill2, 0)
    if t1 == t2:
        return random.random() < 0.5  # tie-break
    return t1 > t2


# ================================================================
# DIFFICULTY CLASSES
# ================================================================

DC_TRIVIAL = 5
DC_EASY = 8
DC_MEDIUM = 12
DC_HARD = 15
DC_VERY_HARD = 18
DC_HEROIC = 22
DC_LEGENDARY = 25


# ================================================================
# CLASS SKILL PROFILES
# ================================================================

CLASS_SKILLS = {
    # --- D&D character classes ---
    "Fighter":   {"swordsmanship": 3, "shield_work": 2, "hunting": 2,
                  "leadership": 2, "smithing": 1, "swimming": 1},
    "Wizard":    {"arcana": 4, "spellcraft": 3, "literacy": 4, "enchanting": 2,
                  "history": 2, "alchemy": 2, "herbalism": 1},
    "Cleric":    {"religion": 3, "medicine": 3, "literacy": 3, "leadership": 2,
                  "herbalism": 2, "cooking": 1, "insight": 2, "warding": 1},
    "Rogue":     {"lockpicking": 3, "stealth": 3, "pickpocketing": 2, "deception": 2,
                  "trap_making": 1, "trading": 2, "hunting": 1, "insight": 1,
                  "accountancy": 1, "appraisal": 1},
    "Ranger":    {"tracking": 3, "archery": 3, "hunting": 3, "nature_lore": 2,
                  "animal_training": 2, "stealth": 2, "navigation": 2,
                  "herbalism": 2, "woodcraft": 2, "swimming": 1, "climbing": 1},
    "Paladin":   {"swordsmanship": 3, "religion": 2, "shield_work": 2, "leadership": 2,
                  "medicine": 1, "intimidation": 1, "literacy": 1},
    "Barbarian": {"unarmed": 2, "swordsmanship": 2, "hunting": 2, "intimidation": 2,
                  "swimming": 2, "climbing": 2, "fishing": 1, "animal_care": 1,
                  "tracking": 1},
    "Bard":      {"performance": 4, "persuasion": 3, "deception": 2, "history": 2,
                  "literacy": 3, "trading": 2, "insight": 1, "cooking": 1},
    "Druid":     {"nature_lore": 3, "animal_training": 3, "herbalism": 3,
                  "ritual_magic": 2, "divination": 1, "farming": 2,
                  "animal_care": 3, "warding": 1, "medicine": 1},
    "Monk":      {"unarmed": 3, "stealth": 2, "insight": 2, "climbing": 2,
                  "medicine": 1, "literacy": 2, "religion": 1, "cooking": 1,
                  "swimming": 1},
    "Sorcerer":  {"spellcraft": 3, "arcana": 2, "intimidation": 1, "literacy": 2,
                  "alchemy": 1, "persuasion": 1},
    "Warlock":   {"arcana": 2, "spellcraft": 2, "deception": 2, "intimidation": 2,
                  "ritual_magic": 1, "literacy": 3, "alchemy": 1},
}

# --- Profession-specific skill profiles ---
# These are merged ON TOP of the class skills when an NPC has a profession.
PROFESSION_SKILLS = {
    # Primary Production
    "Farmer":       {"farming": 3, "cooking": 1, "animal_care": 1},
    "Fisherman":    {"fishing": 3, "swimming": 1, "cooking": 1},
    "Fisher":       {"fishing": 3, "swimming": 1},
    "Hunter":       {"hunting": 3, "tracking": 2, "archery": 2, "stealth": 1},
    "Herbalist":    {"herbalism": 3, "nature_lore": 2, "medicine": 1},
    "Woodcutter":   {"woodcraft": 3, "climbing": 1},
    "Miner":        {"mining": 3, "climbing": 1},
    "Shepherd":     {"animal_care": 3, "herding": 2, "animal_training": 1},
    "Beekeeper":    {"animal_care": 2, "herbalism": 1},
    "Prospector":   {"mining": 2, "navigation": 2, "tracking": 1},
    # Crafting/Manufacturing
    "Blacksmith":   {"smithing": 3, "mining": 1},
    "Armourer":     {"smithing": 3, "leatherwork": 1},
    "Carpenter":    {"woodcraft": 3, "masonry": 1},
    "Cooper":       {"woodcraft": 2},
    "Wheelwright":  {"woodcraft": 3},
    "Shipbuilder":  {"shipbuilding": 3, "woodcraft": 2},
    "Tanner":       {"tanning": 3, "leatherwork": 2},
    "Weaver":       {"weaving": 3},
    "Potter":       {"pottery": 3},
    "Baker":        {"cooking": 3},
    "Brewer":       {"brewing": 3, "cooking": 1},
    "Alchemist":    {"alchemy": 3, "herbalism": 2, "literacy": 2},
    # Services
    "Merchant":     {"trading": 3, "persuasion": 2, "accountancy": 1},
    "Innkeeper":    {"cooking": 2, "trading": 1, "persuasion": 1},
    "Cook":         {"cooking": 3},
    "Servant":      {"cooking": 1},
    "Shop Assistant": {"trading": 2, "persuasion": 1},
    "Banker":       {"accountancy": 3, "literacy": 2, "trading": 2},
    "Barber":       {"persuasion": 2, "medicine": 1},
    "Healer":       {"medicine": 3, "herbalism": 2},
    # Administrative/Leadership
    "Guard":        {"swordsmanship": 2, "shield_work": 1},
    "Captain":      {"swordsmanship": 3, "leadership": 3, "shield_work": 2},
    "Tax Collector":{"intimidation": 2, "accountancy": 2, "literacy": 1},
    "Steward":      {"leadership": 2, "accountancy": 2, "literacy": 2},
    "Scribe":       {"literacy": 4, "history": 2},
    "Diplomat":     {"persuasion": 3, "insight": 2, "literacy": 2},
    "Advisor":      {"leadership": 2, "literacy": 3, "insight": 2},
    # Skilled/Professional
    "Scholar":      {"literacy": 4, "history": 3, "arcana": 2},
    "Mason":        {"masonry": 3, "mining": 1},
    "Animal Trainer": {"animal_training": 3, "animal_care": 2},
    "Stablemaster": {"animal_care": 3, "animal_training": 1},
    "Cartographer": {"cartography": 3, "navigation": 2, "literacy": 2},
    # Construction/Labor
    "Builder":      {"masonry": 2, "woodcraft": 1},
    "Cleaner":      {"cooking": 1},
    "Gravedigger":  {"masonry": 1},
    "Porter":       {"climbing": 1, "swimming": 1},
    "Laborer":      {"farming": 1},
}


# ================================================================
# INITIALIZATION
# ================================================================

def initialize_npc_skills(npc):
    """Give an NPC starting skills based on their class, profession, race, and personality."""
    if not hasattr(npc, 'npc_skills'):
        npc.npc_skills = {}

    char_class = getattr(npc, 'char_class', '')
    base = CLASS_SKILLS.get(char_class, {"farming": 1, "cooking": 1})

    for skill, level in base.items():
        npc.npc_skills[skill] = level + random.randint(0, 1)

    # Layer profession skills on top (additive, so a Blacksmith-Fighter
    # gets both Fighter combat skills and Blacksmith crafting skills)
    profession = getattr(npc, 'profession', '')
    prof_skills = PROFESSION_SKILLS.get(profession, {})
    for skill, level in prof_skills.items():
        current = npc.npc_skills.get(skill, 0)
        npc.npc_skills[skill] = max(current, level + random.randint(0, 1))

    # Everyone has basic cooking and farming
    npc.npc_skills.setdefault("cooking", 1)
    npc.npc_skills.setdefault("farming", 1)

    # Race bonuses
    race = getattr(npc, 'race', 'Human')
    race_skill_bonuses = {
        "Elf":      {"archery": 1, "stealth": 1, "nature_lore": 1},
        "Dwarf":    {"smithing": 2, "mining": 1, "masonry": 1},
        "Halfling": {"stealth": 1, "cooking": 1, "persuasion": 1},
        "Half-Orc": {"intimidation": 1, "unarmed": 1, "climbing": 1},
        "Gnome":    {"alchemy": 1, "enchanting": 1, "history": 1},
        "Half-Elf": {"persuasion": 1, "performance": 1, "insight": 1},
        "Tiefling": {"deception": 1, "intimidation": 1, "arcana": 1},
        "Human":    {},  # humans get no racial skill bonus (they get ability bonuses)
    }
    for skill, bonus in race_skill_bonuses.get(race, {}).items():
        npc.npc_skills[skill] = npc.npc_skills.get(skill, 0) + bonus

    # Personality-driven skill nudges
    traits = getattr(npc, 'social_traits', [])
    trait_skills = {
        "compassionate": ("medicine", 1), "generous": ("trading", 1),
        "cruel": ("intimidation", 1), "greedy": ("pickpocketing", 1),
        "honest": ("insight", 1), "loyal": ("shield_work", 1),
        "deceptive": ("deception", 1), "treacherous": ("stealth", 1),
        "artistic": ("performance", 1), "scholarly": ("history", 1),
        "devout": ("religion", 1), "curious": ("arcana", 1),
        "brave": ("swordsmanship", 1), "cautious": ("stealth", 1),
    }
    for trait in traits:
        if trait in trait_skills:
            sk, bonus = trait_skills[trait]
            npc.npc_skills[sk] = npc.npc_skills.get(sk, 0) + bonus

    # Literacy depends on intelligence
    intel = npc.attributes.get("intelligence", 5)
    if intel >= 6 and "literacy" not in npc.npc_skills:
        npc.npc_skills["literacy"] = 1
    npc.literate = npc.npc_skills.get("literacy", 0) >= 2


def initialize_player_skills(player):
    """Set up the full skill dict on the player, migrating from old 6-skill set."""
    char_class = getattr(player, 'char_class', 'Fighter')
    base = CLASS_SKILLS.get(char_class, {"swordsmanship": 1, "cooking": 1})

    # Start all skills at 0
    new_skills = {name: 0 for name in ALL_SKILL_NAMES}

    # Apply class bonuses
    for skill, level in base.items():
        new_skills[skill] = level

    # Migrate any existing XP from old player skills
    old_map = {
        "combat": "swordsmanship", "foraging": "herbalism",
        "crafting": "smithing", "persuasion": "persuasion",
        "survival": "tracking", "exploration": "navigation",
    }
    old_skills = getattr(player, 'skills', {})
    old_xp = getattr(player, 'skill_xp', {})
    for old_name, new_name in old_map.items():
        if old_name in old_skills:
            new_skills[new_name] = max(new_skills.get(new_name, 0), old_skills[old_name])

    player.skills = new_skills
    player.skill_xp = {k: old_xp.get(k, 0.0) for k in new_skills}


# ================================================================
# XP AND LEVELING
# ================================================================

def gain_skill_xp(npc, skill: str, amount: float = 1.0):
    """NPC gains experience in a skill from performing activities."""
    if not hasattr(npc, 'npc_skills'):
        npc.npc_skills = {}
    if not hasattr(npc, 'npc_skill_xp'):
        npc.npc_skill_xp = {}

    current_level = npc.npc_skills.get(skill, 0)
    if current_level >= 10:
        return  # max level

    # Children learn faster (2x XP)
    if getattr(npc, 'is_child', False):
        amount *= 2.0

    xp = npc.npc_skill_xp.get(skill, 0) + amount
    threshold = 5.0 + current_level * 3.0

    if xp >= threshold:
        npc.npc_skills[skill] = current_level + 1
        npc.npc_skill_xp[skill] = 0
        npc.add_memory("learning", f"Improved {skill} to level {current_level + 1}!", 3)

        # Literacy unlock
        if skill == "literacy" and npc.npc_skills["literacy"] >= 2:
            npc.literate = True
    else:
        npc.npc_skill_xp[skill] = xp


# ================================================================
# LEARNING
# ================================================================

def try_learn_from_book(npc, book_item) -> Optional[str]:
    """NPC tries to learn from a book. Requires literacy."""
    if not getattr(npc, 'literate', False):
        return "Cannot read - not literate."

    if book_item.name == "Skill Manual":
        learnable = [s for s, l in npc.npc_skills.items() if l < 10]
        if not learnable:
            learnable = list(NPC_SKILLS.keys())
        skill = random.choice(learnable)
        gain_skill_xp(npc, skill, 3.0)
        return f"Studied {skill} from the manual."

    elif book_item.name == "Spellbook":
        if getattr(npc, 'is_spellcaster', False):
            gain_skill_xp(npc, "spellcraft", 2.0)
            gain_skill_xp(npc, "arcana", 1.0)
            return "Studied arcane theory."
        return "Cannot understand the arcane symbols."

    elif book_item.name == "Book":
        gain_skill_xp(npc, "literacy", 1.0)
        knowledge_skills = ["herbalism", "alchemy", "trading", "leadership",
                           "history", "arcana", "nature_lore", "religion"]
        skill = random.choice(knowledge_skills)
        gain_skill_xp(npc, skill, 1.0)
        return f"Read and gained knowledge of {skill}."

    elif book_item.name == "Map":
        gain_skill_xp(npc, "navigation", 2.0)
        gain_skill_xp(npc, "cartography", 1.0)
        return "Studied the map, improving navigation skills."

    return None


def try_teach(teacher, student, skill: str) -> Optional[str]:
    """A teacher tries to teach a student a skill. Teacher must be higher level."""
    if not hasattr(teacher, 'npc_skills') or not hasattr(student, 'npc_skills'):
        return None

    teacher_level = teacher.npc_skills.get(skill, 0)
    student_level = student.npc_skills.get(skill, 0)

    if teacher_level <= student_level:
        return None

    cha = teacher.attributes.get("charisma", 5)
    success_chance = 0.3 + (teacher_level - student_level) * 0.1 + cha * 0.03

    if random.random() < success_chance:
        gain_skill_xp(student, skill, 2.0)
        gain_skill_xp(teacher, "leadership", 0.5)
        return f"{teacher.name} taught {student.name} about {skill}."

    return None


# ================================================================
# SKILL ACTION REQUIREMENTS — what tools/zones/items an action needs
# ================================================================

SKILL_ACTION_REQUIREMENTS = {
    # action_name: {"skill": str, "tool": str|None, "zone": str|None, "dc": int, "time": float}
    "pick_lock":       {"skill": "lockpicking",   "tool": "Thieves' Tools", "zone": None, "dc": 14, "time": 3.0},
    "pickpocket":      {"skill": "pickpocketing",  "tool": None,             "zone": None, "dc": 13, "time": 1.0},
    "sneak":           {"skill": "stealth",        "tool": None,             "zone": None, "dc": 12, "time": 0.0},
    "set_trap":        {"skill": "trap_making",    "tool": None,             "zone": None, "dc": 11, "time": 5.0},
    "perform":         {"skill": "performance",    "tool": "Musical Instrument", "zone": None, "dc": 10, "time": 5.0},
    "intimidate":      {"skill": "intimidation",   "tool": None,             "zone": None, "dc": 12, "time": 1.0},
    "heal_other":      {"skill": "medicine",       "tool": "Healer's Kit",   "zone": None, "dc": 12, "time": 4.0},
    "train_combat":    {"skill": "swordsmanship",  "tool": None,         "zone": "training_ground", "dc": 8, "time": 6.0},
    "train_archery":   {"skill": "archery",        "tool": "Hunting Bow","zone": "archery_range",   "dc": 8, "time": 6.0},
    "research":        {"skill": "arcana",         "tool": None,             "zone": "library",  "dc": 12, "time": 6.0},
    "pray":            {"skill": "religion",       "tool": None,             "zone": "chapel",   "dc": 8,  "time": 4.0},
    "craft_pottery":   {"skill": "pottery",        "tool": None,       "zone": "pottery_studio",   "dc": 10, "time": 5.0},
    "craft_glass":     {"skill": "glassblowing",   "tool": "Glassblower's Tools", "zone": "glassworks", "dc": 12, "time": 6.0},
    "enchant_item":    {"skill": "enchanting",     "tool": "Enchanter's Focus", "zone": "enchanting_room", "dc": 16, "time": 8.0},
    "make_map":        {"skill": "cartography",    "tool": "Cartographer's Kit", "zone": None,  "dc": 12, "time": 5.0},
    "track":           {"skill": "tracking",       "tool": None,             "zone": None,  "dc": 12, "time": 2.0},
    "navigate":        {"skill": "navigation",     "tool": None,             "zone": None,  "dc": 10, "time": 0.0},
    "climb":           {"skill": "climbing",       "tool": None,             "zone": None,  "dc": 13, "time": 3.0},
    "swim":            {"skill": "swimming",       "tool": None,             "zone": None,  "dc": 11, "time": 2.0},
    "train_animal":    {"skill": "animal_training","tool": None,       "zone": "stable",           "dc": 13, "time": 6.0},
    "perform_ritual":  {"skill": "ritual_magic",   "tool": None,       "zone": "ritual_circle",    "dc": 15, "time": 10.0},
    "set_ward":        {"skill": "warding",        "tool": "Ward Stones","zone": None,              "dc": 14, "time": 6.0},
    "divine":          {"skill": "divination",     "tool": "Divination Crystal","zone": None,       "dc": 13, "time": 5.0},
    "tan_hide":        {"skill": "tanning",        "tool": None,        "zone": "tannery",          "dc": 10, "time": 4.0},
    "dye_cloth":       {"skill": "dyeing",         "tool": "Dye Kit",   "zone": "dye_house",        "dc": 10, "time": 3.0},
    "build_siege":     {"skill": "siege_engineering","tool": "Siege Tools","zone": None,             "dc": 16, "time": 12.0},
    "build_ship":      {"skill": "shipbuilding",   "tool": "Shipwright's Tools","zone": "shipyard",  "dc": 16, "time": 15.0},
    "disguise_self":   {"skill": "disguise",       "tool": "Disguise Kit","zone": None,              "dc": 13, "time": 3.0},
}


# ================================================================
# SKILL-BASED ACTION HELPERS
# ================================================================

def can_attempt_action(entity, action_name: str) -> Tuple[bool, str]:
    """Check if entity has the prerequisites for a skill action.
    Returns (can_do, reason_if_not).
    """
    req = SKILL_ACTION_REQUIREMENTS.get(action_name)
    if not req:
        return (True, "")

    # Check tool
    tool = req.get("tool")
    if tool:
        has_tool = False
        if hasattr(entity, 'npc_inventory'):
            has_tool = any(i.name == tool for i in entity.npc_inventory)
        elif hasattr(entity, 'inventory'):
            has_tool = any(i.name == tool for i in entity.inventory)
        if not has_tool:
            return (False, f"Requires {tool}")

    return (True, "")


def attempt_skill_action(entity, action_name: str) -> Tuple[bool, int, int, str]:
    """Attempt a skill-based action. Returns (success, total, natural, skill_name).
    Does NOT check prerequisites — call can_attempt_action first.
    """
    req = SKILL_ACTION_REQUIREMENTS.get(action_name)
    if not req:
        return (True, 20, 20, "")

    skill = req["skill"]
    dc = req["dc"]
    success, total, natural = skill_check(entity, skill, dc)

    # Gain XP regardless (learn from trying)
    xp_amount = 1.5 if success else 0.5
    if hasattr(entity, 'npc_skills'):
        gain_skill_xp(entity, skill, xp_amount)
    elif hasattr(entity, 'skill_xp'):
        # Player XP
        entity.gain_skill_xp(skill, xp_amount)

    return (success, total, natural, skill)


def get_best_skill_in_category(entity, category: str) -> Tuple[str, int]:
    """Get entity's highest skill in a category. Returns (skill_name, level)."""
    skills_in_cat = SKILL_CATEGORIES.get(category, [])
    best_name = skills_in_cat[0] if skills_in_cat else ""
    best_level = 0
    for sk in skills_in_cat:
        level = get_skill_level(entity, sk)
        if level > best_level:
            best_level = level
            best_name = sk
    return (best_name, best_level)


def get_skills_summary(entity, top_n: int = 5) -> str:
    """Get a summary string of entity's top skills."""
    if hasattr(entity, 'npc_skills'):
        skills = entity.npc_skills
    elif hasattr(entity, 'skills'):
        skills = entity.skills
    else:
        return "no skills"

    top = sorted(skills.items(), key=lambda x: -x[1])[:top_n]
    top = [(s, l) for s, l in top if l > 0]
    if not top:
        return "no notable skills"
    return ", ".join(f"{s} ({l})" for s, l in top)
