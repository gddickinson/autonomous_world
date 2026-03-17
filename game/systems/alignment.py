"""
Alignment & Belief System: D&D 9-alignment grid with behavioral effects.

Lawful ←→ Chaotic (order vs freedom)
Good ←→ Evil (altruism vs selfishness)

Alignment affects:
- Dialog options and responses
- Social interaction choices (betray, help, steal, share)
- Combat decisions (mercy vs kill, fight fair vs ambush)
- Economic behavior (fair trade vs cheat, charity vs hoard)
- Political alignment (support law vs rebel, serve vs dominate)
- Reaction to crimes and injustice
- Worship and deity choice

Each alignment has specific behavioral tendencies that the NPC AI uses
when making decisions.
"""

import random
from typing import Dict, List, Tuple


# ================================================================
# THE NINE ALIGNMENTS
# ================================================================

ALIGNMENTS = {
    "lawful good": {
        "law_order": 1.0, "good_evil": 1.0,
        "description": "Honorable and compassionate. Follows rules to protect the innocent.",
        "tendencies": {
            "help_stranger": 0.9, "steal": 0.0, "lie": 0.05, "betray": 0.0,
            "mercy": 0.95, "share_food": 0.9, "obey_law": 0.95,
            "fight_evil": 0.9, "protect_weak": 0.95, "fair_trade": 0.95,
            "charity": 0.7, "forgive": 0.7, "honor_deal": 1.0,
        },
    },
    "neutral good": {
        "law_order": 0.0, "good_evil": 1.0,
        "description": "Does good without regard for rules. Helps others freely.",
        "tendencies": {
            "help_stranger": 0.8, "steal": 0.05, "lie": 0.15, "betray": 0.02,
            "mercy": 0.85, "share_food": 0.8, "obey_law": 0.6,
            "fight_evil": 0.8, "protect_weak": 0.85, "fair_trade": 0.8,
            "charity": 0.6, "forgive": 0.6, "honor_deal": 0.85,
        },
    },
    "chaotic good": {
        "law_order": -1.0, "good_evil": 1.0,
        "description": "Rebels with a heart of gold. Breaks rules to do what's right.",
        "tendencies": {
            "help_stranger": 0.75, "steal": 0.15, "lie": 0.3, "betray": 0.05,
            "mercy": 0.7, "share_food": 0.7, "obey_law": 0.2,
            "fight_evil": 0.85, "protect_weak": 0.8, "fair_trade": 0.6,
            "charity": 0.5, "forgive": 0.5, "honor_deal": 0.6,
        },
    },
    "lawful neutral": {
        "law_order": 1.0, "good_evil": 0.0,
        "description": "Follows the law above all. Order and structure are paramount.",
        "tendencies": {
            "help_stranger": 0.4, "steal": 0.0, "lie": 0.1, "betray": 0.05,
            "mercy": 0.5, "share_food": 0.3, "obey_law": 0.95,
            "fight_evil": 0.5, "protect_weak": 0.4, "fair_trade": 0.9,
            "charity": 0.2, "forgive": 0.3, "honor_deal": 0.95,
        },
    },
    "true neutral": {
        "law_order": 0.0, "good_evil": 0.0,
        "description": "Acts according to circumstances. Seeks balance above all.",
        "tendencies": {
            "help_stranger": 0.4, "steal": 0.1, "lie": 0.2, "betray": 0.1,
            "mercy": 0.5, "share_food": 0.4, "obey_law": 0.5,
            "fight_evil": 0.4, "protect_weak": 0.4, "fair_trade": 0.7,
            "charity": 0.2, "forgive": 0.4, "honor_deal": 0.7,
        },
    },
    "chaotic neutral": {
        "law_order": -1.0, "good_evil": 0.0,
        "description": "Values personal freedom above all. Unpredictable and self-serving.",
        "tendencies": {
            "help_stranger": 0.25, "steal": 0.3, "lie": 0.4, "betray": 0.2,
            "mercy": 0.35, "share_food": 0.2, "obey_law": 0.1,
            "fight_evil": 0.3, "protect_weak": 0.2, "fair_trade": 0.4,
            "charity": 0.1, "forgive": 0.3, "honor_deal": 0.4,
        },
    },
    "lawful evil": {
        "law_order": 1.0, "good_evil": -1.0,
        "description": "Uses law and order to dominate. Tyrannical and calculating.",
        "tendencies": {
            "help_stranger": 0.1, "steal": 0.1, "lie": 0.4, "betray": 0.3,
            "mercy": 0.1, "share_food": 0.05, "obey_law": 0.8,
            "fight_evil": 0.1, "protect_weak": 0.05, "fair_trade": 0.5,
            "charity": 0.0, "forgive": 0.05, "honor_deal": 0.7,
        },
    },
    "neutral evil": {
        "law_order": 0.0, "good_evil": -1.0,
        "description": "Purely selfish. Does whatever it takes to get ahead.",
        "tendencies": {
            "help_stranger": 0.05, "steal": 0.4, "lie": 0.5, "betray": 0.4,
            "mercy": 0.1, "share_food": 0.02, "obey_law": 0.3,
            "fight_evil": 0.05, "protect_weak": 0.02, "fair_trade": 0.3,
            "charity": 0.0, "forgive": 0.05, "honor_deal": 0.3,
        },
    },
    "chaotic evil": {
        "law_order": -1.0, "good_evil": -1.0,
        "description": "Revels in destruction and cruelty. Takes what it wants by force.",
        "tendencies": {
            "help_stranger": 0.0, "steal": 0.6, "lie": 0.6, "betray": 0.5,
            "mercy": 0.05, "share_food": 0.0, "obey_law": 0.0,
            "fight_evil": 0.0, "protect_weak": 0.0, "fair_trade": 0.1,
            "charity": 0.0, "forgive": 0.0, "honor_deal": 0.1,
        },
    },
}

# ================================================================
# CLASS AND RACE ALIGNMENT TENDENCIES
# ================================================================

# What alignment each class tends toward
CLASS_ALIGNMENT_WEIGHTS = {
    "Fighter":   {"lawful good": 15, "neutral good": 15, "lawful neutral": 15, "true neutral": 10, "chaotic good": 10},
    "Wizard":    {"true neutral": 20, "lawful neutral": 15, "neutral good": 15, "lawful good": 10},
    "Cleric":    {"lawful good": 25, "neutral good": 20, "lawful neutral": 10},
    "Rogue":     {"chaotic neutral": 20, "chaotic good": 15, "neutral evil": 10, "true neutral": 10},
    "Ranger":    {"neutral good": 20, "chaotic good": 20, "true neutral": 15},
    "Paladin":   {"lawful good": 50, "neutral good": 10},
    "Barbarian": {"chaotic neutral": 15, "chaotic good": 15, "true neutral": 15, "neutral evil": 5},
    "Bard":      {"chaotic good": 20, "chaotic neutral": 15, "neutral good": 15},
    "Druid":     {"true neutral": 25, "neutral good": 20, "chaotic neutral": 10},
    "Monk":      {"lawful good": 15, "lawful neutral": 25, "true neutral": 15},
    "Sorcerer":  {"chaotic neutral": 15, "chaotic good": 15, "true neutral": 15, "neutral evil": 5},
    "Warlock":   {"chaotic neutral": 15, "neutral evil": 15, "chaotic evil": 10, "true neutral": 10, "lawful evil": 5},
}

# Monster alignments
CREATURE_ALIGNMENTS = {
    "wolf": "true neutral", "bear": "true neutral", "deer": "true neutral",
    "goblin": "neutral evil", "kobold": "lawful evil", "orc": "chaotic evil",
    "gnoll": "chaotic evil", "bugbear": "chaotic evil",
    "bandit": "chaotic neutral", "skeleton": "lawful evil", "zombie": "neutral evil",
    "ogre": "chaotic evil", "troll": "chaotic evil",
    "spider": "true neutral", "werewolf": "chaotic evil",
    "young_dragon": "lawful evil",
}

# ================================================================
# GODS AND WORSHIP
# ================================================================

DEITIES = {
    "Solarius": {
        "domain": "Light and Justice",
        "alignment": "lawful good",
        "followers": ["Paladin", "Cleric", "Fighter"],
        "values": ["truth", "justice", "protection", "honor"],
        "symbol": "Golden sun",
        "blessing": "healing",
        "description": "The Sun God, patron of paladins and protector of the innocent.",
    },
    "Sylvana": {
        "domain": "Nature and Growth",
        "alignment": "neutral good",
        "followers": ["Druid", "Ranger"],
        "values": ["nature", "balance", "seasons", "animals"],
        "symbol": "Oak leaf",
        "blessing": "growth",
        "description": "The Forest Mother, guardian of all wild things.",
    },
    "Arcanus": {
        "domain": "Knowledge and Magic",
        "alignment": "true neutral",
        "followers": ["Wizard", "Sorcerer", "Bard"],
        "values": ["knowledge", "discovery", "truth", "magic"],
        "symbol": "Open eye",
        "blessing": "insight",
        "description": "The All-Seeing, keeper of arcane secrets.",
    },
    "Moradin": {
        "domain": "Forge and Craftsmanship",
        "alignment": "lawful good",
        "followers": ["Fighter", "Monk"],
        "values": ["craft", "honor", "duty", "strength"],
        "symbol": "Hammer and anvil",
        "description": "The Soul Forger, patron of dwarves and craftsmen.",
    },
    "Luthien": {
        "domain": "Moon and Dreams",
        "alignment": "chaotic good",
        "followers": ["Bard", "Rogue", "Ranger"],
        "values": ["freedom", "beauty", "music", "travel"],
        "symbol": "Crescent moon",
        "description": "The Dreamweaver, patron of travelers and artists.",
    },
    "Nerull": {
        "domain": "Death and Shadows",
        "alignment": "neutral evil",
        "followers": ["Warlock", "Rogue"],
        "values": ["power", "secrets", "ambition", "death"],
        "symbol": "Skull",
        "description": "The Reaper, lord of the dead and keeper of dark secrets.",
    },
    "Gruumsh": {
        "domain": "War and Destruction",
        "alignment": "chaotic evil",
        "followers": ["Barbarian"],
        "values": ["strength", "conquest", "rage", "dominance"],
        "symbol": "Single eye",
        "description": "The One-Eyed God, patron of orcs and war.",
    },
    "Tymora": {
        "domain": "Luck and Fortune",
        "alignment": "chaotic good",
        "followers": ["Rogue", "Bard"],
        "values": ["luck", "adventure", "daring", "fortune"],
        "symbol": "Coin",
        "description": "Lady Luck, patron of gamblers and adventurers.",
    },
}


# ================================================================
# ALIGNMENT SYSTEM
# ================================================================

def assign_alignment(npc):
    """Assign an alignment based on class, race, and personality."""
    cc = getattr(npc, 'char_class', 'Fighter')
    race = getattr(npc, 'race', 'Human')
    traits = getattr(npc, 'social_traits', [])

    # Get class weights
    weights = dict(CLASS_ALIGNMENT_WEIGHTS.get(cc, {"true neutral": 20}))

    # Personality modifiers
    if "compassionate" in traits or "generous" in traits:
        for a in weights:
            if "good" in a:
                weights[a] = weights.get(a, 0) + 10
    if "cruel" in traits or "greedy" in traits:
        for a in ["neutral evil", "chaotic evil", "lawful evil"]:
            weights[a] = weights.get(a, 0) + 10
    if "honest" in traits or "loyal" in traits:
        for a in weights:
            if "lawful" in a:
                weights[a] = weights.get(a, 0) + 8
    if "deceptive" in traits or "treacherous" in traits:
        for a in ["chaotic neutral", "chaotic evil", "neutral evil"]:
            weights[a] = weights.get(a, 0) + 8

    # Race modifiers
    if race == "Half-Orc":
        weights["chaotic neutral"] = weights.get("chaotic neutral", 0) + 5
    elif race == "Tiefling":
        weights["chaotic neutral"] = weights.get("chaotic neutral", 0) + 5

    alignments = list(weights.keys())
    w = [weights[a] for a in alignments]
    npc.alignment = random.choices(alignments, weights=w, k=1)[0]


def assign_deity(npc):
    """Assign a patron deity based on class and alignment."""
    cc = getattr(npc, 'char_class', '')
    alignment = getattr(npc, 'alignment', 'true neutral')

    best_deity = None
    best_score = -1

    for name, deity in DEITIES.items():
        score = 0
        if cc in deity["followers"]:
            score += 10
        # Alignment compatibility
        npc_law = ALIGNMENTS.get(alignment, {}).get("law_order", 0)
        npc_good = ALIGNMENTS.get(alignment, {}).get("good_evil", 0)
        deity_law = ALIGNMENTS.get(deity["alignment"], {}).get("law_order", 0)
        deity_good = ALIGNMENTS.get(deity["alignment"], {}).get("good_evil", 0)
        dist = abs(npc_law - deity_law) + abs(npc_good - deity_good)
        score += max(0, 10 - dist * 3)
        score += random.randint(0, 3)

        if score > best_score:
            best_score = score
            best_deity = name

    npc.deity = best_deity


def get_tendency(npc, action: str) -> float:
    """Get how likely an NPC is to take a specific action based on alignment."""
    alignment = getattr(npc, 'alignment', 'true neutral')
    data = ALIGNMENTS.get(alignment, ALIGNMENTS["true neutral"])
    return data["tendencies"].get(action, 0.5)


def should_act(npc, action: str) -> bool:
    """Roll against alignment tendency. Returns True if NPC would do this action."""
    tendency = get_tendency(npc, action)
    return random.random() < tendency


def alignment_compatibility(align1: str, align2: str) -> int:
    """How compatible are two alignments? Returns -20 to +20."""
    a1 = ALIGNMENTS.get(align1, {})
    a2 = ALIGNMENTS.get(align2, {})
    law_diff = abs(a1.get("law_order", 0) - a2.get("law_order", 0))
    good_diff = abs(a1.get("good_evil", 0) - a2.get("good_evil", 0))
    return int(20 - (law_diff + good_diff) * 10)
