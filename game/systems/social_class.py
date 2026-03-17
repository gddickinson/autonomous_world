"""
Social Class & Caste System — hierarchical society with movement restrictions.

Each governance style imposes a different social structure:

FEUDALISM:
  Royalty → Nobility → Gentry → Freemen → Serfs
  - Serfs bound to land, need lord's permission to travel
  - Freemen can move but pay tolls
  - Only nobility can own land or hold office
  - Social mobility: military service, marriage, royal decree

REPUBLIC:
  Citizens → Residents → Foreigners
  - Citizens can vote, hold office, own property
  - Residents can work and trade freely
  - Foreigners have limited rights, pay extra taxes
  - Social mobility: earn citizenship through service or wealth

THEOCRACY:
  Clergy → Faithful → Layfolk → Unbelievers
  - Clergy rule and are exempt from taxes
  - Faithful get access to healing and education
  - Layfolk are tolerated but restricted
  - Unbelievers face penalties, may be expelled

TRIBAL:
  Chief → Warriors → Elders → Hunters → Gatherers
  - Strength determines rank
  - All tribe members equal in basic rights
  - Outsiders must prove worth through combat or gift

MERCHANT REPUBLIC:
  Patricians → Merchants → Artisans → Laborers → Debtors
  - Wealth determines class
  - Anyone can rise through trade
  - Debtors lose rights until debts repaid
  - Most socially mobile system

TYRANNY:
  Tyrant → Enforcers → Subjects → Slaves
  - Absolute rule by fear
  - Enforcers have power over subjects
  - Slaves from conquered peoples or debt default
  - No upward mobility except through the tyrant's favor

AUTOCRACY:
  Ruler → Bureaucrats → Citizens → Laborers → Outcasts
  - Rigid bureaucratic hierarchy
  - Advancement through loyalty and service
  - Outcasts are criminals and dissidents

ANARCHY:
  No formal classes — might makes right
  - Strongest take what they want
  - Informal gangs and protection rackets
  - Complete freedom but no safety
"""

import random
from typing import Dict, List, Optional, Tuple


# ================================================================
# SOCIAL CLASS DEFINITIONS PER GOVERNANCE STYLE
# ================================================================

SOCIAL_HIERARCHIES = {
    "feudalism": {
        "classes": ["royalty", "nobility", "gentry", "freeman", "serf"],
        "descriptions": {
            "royalty": "The ruling family and their direct kin",
            "nobility": "Lords, dukes, and landed knights",
            "gentry": "Minor landowners, wealthy merchants, and officials",
            "freeman": "Free workers, craftsmen, and traders",
            "serf": "Bound to the land, cannot travel without permission",
        },
        "rights": {
            "royalty":  {"travel": True, "own_land": True, "hold_office": True, "carry_weapons": True, "tax_exempt": True},
            "nobility": {"travel": True, "own_land": True, "hold_office": True, "carry_weapons": True, "tax_exempt": False},
            "gentry":   {"travel": True, "own_land": True, "hold_office": False, "carry_weapons": True, "tax_exempt": False},
            "freeman":  {"travel": True, "own_land": False, "hold_office": False, "carry_weapons": True, "tax_exempt": False},
            "serf":     {"travel": False, "own_land": False, "hold_office": False, "carry_weapons": False, "tax_exempt": False},
        },
        "tax_multiplier": {
            "royalty": 0.0, "nobility": 0.5, "gentry": 0.8, "freeman": 1.0, "serf": 1.5,
        },
        "mobility": "low",  # how easy to change class
        "foreigner_class": "freeman",  # what class outsiders get
    },

    "republic": {
        "classes": ["senator", "citizen", "resident", "foreigner"],
        "descriptions": {
            "senator": "Elected officials who make laws",
            "citizen": "Full members of the republic with voting rights",
            "resident": "Inhabitants who live and work but cannot vote",
            "foreigner": "Visitors and immigrants with limited rights",
        },
        "rights": {
            "senator":   {"travel": True, "own_land": True, "hold_office": True, "carry_weapons": True, "tax_exempt": True},
            "citizen":   {"travel": True, "own_land": True, "hold_office": True, "carry_weapons": True, "tax_exempt": False},
            "resident":  {"travel": True, "own_land": False, "hold_office": False, "carry_weapons": True, "tax_exempt": False},
            "foreigner": {"travel": True, "own_land": False, "hold_office": False, "carry_weapons": False, "tax_exempt": False},
        },
        "tax_multiplier": {
            "senator": 0.0, "citizen": 1.0, "resident": 1.2, "foreigner": 1.5,
        },
        "mobility": "high",
        "foreigner_class": "foreigner",
    },

    "theocracy": {
        "classes": ["high_priest", "clergy", "faithful", "layfolk", "unbeliever"],
        "descriptions": {
            "high_priest": "The divine ruler and head of the faith",
            "clergy": "Priests, monks, and temple servants",
            "faithful": "Devout followers of the state religion",
            "layfolk": "Those who pay lip service but don't truly follow",
            "unbeliever": "Heathens and followers of other gods",
        },
        "rights": {
            "high_priest": {"travel": True, "own_land": True, "hold_office": True, "carry_weapons": True, "tax_exempt": True},
            "clergy":      {"travel": True, "own_land": True, "hold_office": True, "carry_weapons": False, "tax_exempt": True},
            "faithful":    {"travel": True, "own_land": True, "hold_office": False, "carry_weapons": True, "tax_exempt": False},
            "layfolk":     {"travel": True, "own_land": False, "hold_office": False, "carry_weapons": True, "tax_exempt": False},
            "unbeliever":  {"travel": False, "own_land": False, "hold_office": False, "carry_weapons": False, "tax_exempt": False},
        },
        "tax_multiplier": {
            "high_priest": 0.0, "clergy": 0.0, "faithful": 0.8, "layfolk": 1.2, "unbeliever": 2.0,
        },
        "mobility": "medium",  # conversion = mobility
        "foreigner_class": "layfolk",
    },

    "tribal": {
        "classes": ["chief", "warrior", "elder", "hunter", "gatherer"],
        "descriptions": {
            "chief": "Leader chosen by strength and wisdom",
            "warrior": "Proven fighters who defend the tribe",
            "elder": "Respected advisors and keepers of tradition",
            "hunter": "Those who bring food through skill",
            "gatherer": "Those who tend crops and gather resources",
        },
        "rights": {
            "chief":    {"travel": True, "own_land": True, "hold_office": True, "carry_weapons": True, "tax_exempt": True},
            "warrior":  {"travel": True, "own_land": False, "hold_office": False, "carry_weapons": True, "tax_exempt": False},
            "elder":    {"travel": True, "own_land": False, "hold_office": True, "carry_weapons": False, "tax_exempt": True},
            "hunter":   {"travel": True, "own_land": False, "hold_office": False, "carry_weapons": True, "tax_exempt": False},
            "gatherer": {"travel": True, "own_land": False, "hold_office": False, "carry_weapons": False, "tax_exempt": False},
        },
        "tax_multiplier": {
            "chief": 0.0, "warrior": 0.5, "elder": 0.0, "hunter": 0.8, "gatherer": 1.0,
        },
        "mobility": "high",  # prove yourself and rise
        "foreigner_class": "gatherer",
    },

    "merchant_republic": {
        "classes": ["patrician", "merchant", "artisan", "laborer", "debtor"],
        "descriptions": {
            "patrician": "The wealthiest families who control trade",
            "merchant": "Successful traders and business owners",
            "artisan": "Skilled craftspeople with their own workshops",
            "laborer": "Workers who sell their labor for wages",
            "debtor": "Those who owe debts and have lost rights",
        },
        "rights": {
            "patrician": {"travel": True, "own_land": True, "hold_office": True, "carry_weapons": True, "tax_exempt": False},
            "merchant":  {"travel": True, "own_land": True, "hold_office": True, "carry_weapons": True, "tax_exempt": False},
            "artisan":   {"travel": True, "own_land": True, "hold_office": False, "carry_weapons": True, "tax_exempt": False},
            "laborer":   {"travel": True, "own_land": False, "hold_office": False, "carry_weapons": False, "tax_exempt": False},
            "debtor":    {"travel": False, "own_land": False, "hold_office": False, "carry_weapons": False, "tax_exempt": False},
        },
        "tax_multiplier": {
            "patrician": 0.8, "merchant": 1.0, "artisan": 1.0, "laborer": 1.2, "debtor": 2.0,
        },
        "mobility": "very_high",  # wealth = mobility
        "foreigner_class": "laborer",
    },

    "tyranny": {
        "classes": ["tyrant", "enforcer", "subject", "slave"],
        "descriptions": {
            "tyrant": "The absolute ruler",
            "enforcer": "Those who enforce the tyrant's will",
            "subject": "The general population under the tyrant",
            "slave": "Those with no rights, property of others",
        },
        "rights": {
            "tyrant":   {"travel": True, "own_land": True, "hold_office": True, "carry_weapons": True, "tax_exempt": True},
            "enforcer": {"travel": True, "own_land": False, "hold_office": False, "carry_weapons": True, "tax_exempt": True},
            "subject":  {"travel": False, "own_land": False, "hold_office": False, "carry_weapons": False, "tax_exempt": False},
            "slave":    {"travel": False, "own_land": False, "hold_office": False, "carry_weapons": False, "tax_exempt": False},
        },
        "tax_multiplier": {
            "tyrant": 0.0, "enforcer": 0.0, "subject": 1.5, "slave": 0.0,  # slaves own nothing to tax
        },
        "mobility": "none",
        "foreigner_class": "subject",
    },

    "autocracy": {
        "classes": ["ruler", "bureaucrat", "citizen", "laborer", "outcast"],
        "descriptions": {
            "ruler": "The supreme authority",
            "bureaucrat": "Administrators who run the state",
            "citizen": "Loyal members of the state",
            "laborer": "Workers with basic rights",
            "outcast": "Criminals, dissidents, and exiles",
        },
        "rights": {
            "ruler":      {"travel": True, "own_land": True, "hold_office": True, "carry_weapons": True, "tax_exempt": True},
            "bureaucrat": {"travel": True, "own_land": True, "hold_office": True, "carry_weapons": True, "tax_exempt": False},
            "citizen":    {"travel": True, "own_land": True, "hold_office": False, "carry_weapons": True, "tax_exempt": False},
            "laborer":    {"travel": True, "own_land": False, "hold_office": False, "carry_weapons": False, "tax_exempt": False},
            "outcast":    {"travel": False, "own_land": False, "hold_office": False, "carry_weapons": False, "tax_exempt": False},
        },
        "tax_multiplier": {
            "ruler": 0.0, "bureaucrat": 0.5, "citizen": 1.0, "laborer": 1.3, "outcast": 0.0,
        },
        "mobility": "low",
        "foreigner_class": "laborer",
    },

    "anarchy": {
        "classes": ["warlord", "gang_member", "survivor"],
        "descriptions": {
            "warlord": "The strongest individual who takes what they want",
            "gang_member": "Part of a protection group",
            "survivor": "Everyone else — fending for themselves",
        },
        "rights": {
            "warlord":     {"travel": True, "own_land": True, "hold_office": False, "carry_weapons": True, "tax_exempt": True},
            "gang_member": {"travel": True, "own_land": False, "hold_office": False, "carry_weapons": True, "tax_exempt": True},
            "survivor":    {"travel": True, "own_land": False, "hold_office": False, "carry_weapons": True, "tax_exempt": True},
        },
        "tax_multiplier": {
            "warlord": 0.0, "gang_member": 0.0, "survivor": 0.0,
        },
        "mobility": "high",  # kill your way up
        "foreigner_class": "survivor",
    },
}


# ================================================================
# RACIAL GOVERNANCE PREFERENCES
# ================================================================

RACE_GOVERNANCE = {
    "Human":    ["feudalism", "republic", "merchant_republic"],
    "Elf":      ["republic", "theocracy"],       # elven councils
    "Dwarf":    ["feudalism", "autocracy"],       # clan-based hierarchies
    "Halfling": ["republic", "merchant_republic"],  # democratic, trade-oriented
    "Half-Orc": ["tribal", "tyranny"],            # strength-based
    "Gnome":    ["republic", "merchant_republic"],  # inventive democracies
    "Half-Elf": ["republic", "feudalism"],         # blend of cultures
    "Tiefling": ["autocracy", "anarchy"],          # outsider governance
}


# ================================================================
# SOCIAL CLASS ASSIGNMENT
# ================================================================

def assign_social_class(npc, governance_style: str, kingdom_name: str = ""):
    """Assign a social class to an NPC based on governance style, title, wealth, and race."""
    hierarchy = SOCIAL_HIERARCHIES.get(governance_style,
                                       SOCIAL_HIERARCHIES["feudalism"])
    classes = hierarchy["classes"]
    title = getattr(npc, 'title', 'commoner')
    gold = getattr(npc, 'npc_gold', 0)
    char_class = getattr(npc, 'char_class', '')
    alignment = getattr(npc, 'alignment', 'true neutral')
    is_ruler = getattr(npc, 'is_ruler', False)

    # Top class for rulers
    if is_ruler or title == "monarch":
        npc.social_class = classes[0]
        npc.social_class_kingdom = kingdom_name
        return

    if governance_style == "feudalism":
        if title in ("duke", "lord"):
            npc.social_class = "nobility"
        elif title == "knight":
            npc.social_class = "gentry"
        elif title == "guard":
            npc.social_class = "freeman"
        elif title == "servant":
            npc.social_class = "serf"
        elif gold > 40 or char_class in ("Wizard", "Cleric", "Bard"):
            npc.social_class = "gentry"  # educated/wealthy = gentry
        elif char_class in ("Fighter", "Ranger", "Paladin", "Rogue"):
            npc.social_class = "freeman"  # armed/skilled = free
        else:
            npc.social_class = random.choice(["freeman", "freeman", "serf"])

    elif governance_style == "republic":
        if title in ("duke", "lord", "monarch"):
            npc.social_class = "senator"
        elif gold > 30 or char_class in ("Wizard", "Cleric"):
            npc.social_class = "citizen"
        elif title == "guard" or char_class in ("Fighter", "Ranger"):
            npc.social_class = "citizen"
        else:
            npc.social_class = "resident"

    elif governance_style == "theocracy":
        if char_class in ("Cleric", "Paladin", "Monk"):
            npc.social_class = "clergy"
        elif char_class == "Druid":
            npc.social_class = "faithful"  # nature worship accepted
        elif "good" in alignment or "lawful" in alignment:
            npc.social_class = "faithful"
        elif char_class == "Warlock" or "evil" in alignment:
            npc.social_class = "unbeliever"
        else:
            npc.social_class = "layfolk"

    elif governance_style == "tribal":
        if title == "monarch" or is_ruler:
            npc.social_class = "chief"
        elif char_class in ("Fighter", "Barbarian", "Paladin", "Ranger"):
            npc.social_class = "warrior"
        elif getattr(npc, 'age', 30) > 55:
            npc.social_class = "elder"
        elif char_class in ("Ranger", "Rogue", "Druid"):
            npc.social_class = "hunter"
        else:
            npc.social_class = "gatherer"

    elif governance_style == "merchant_republic":
        if gold > 80:
            npc.social_class = "patrician"
        elif gold > 30 or char_class in ("Rogue", "Bard"):
            npc.social_class = "merchant"
        elif char_class in ("Fighter", "Wizard", "Cleric"):
            npc.social_class = "artisan"
        else:
            npc.social_class = "laborer"

    elif governance_style == "tyranny":
        if is_ruler:
            npc.social_class = "tyrant"
        elif title in ("guard", "knight") or char_class in ("Fighter", "Barbarian"):
            npc.social_class = "enforcer"
        else:
            npc.social_class = "subject"

    elif governance_style == "autocracy":
        if is_ruler:
            npc.social_class = "ruler"
        elif title in ("duke", "lord", "knight"):
            npc.social_class = "bureaucrat"
        elif char_class in ("Wizard", "Cleric"):
            npc.social_class = "bureaucrat"
        elif gold > 20:
            npc.social_class = "citizen"
        else:
            npc.social_class = "laborer"

    elif governance_style == "anarchy":
        if getattr(npc, 'bravery', 0.5) > 0.7 and char_class in ("Fighter", "Barbarian"):
            npc.social_class = "warlord"
        elif getattr(npc, 'friendliness', 0.5) < 0.4:
            npc.social_class = "gang_member"
        else:
            npc.social_class = "survivor"

    else:
        npc.social_class = classes[-1]  # lowest class

    npc.social_class_kingdom = kingdom_name


def get_npc_rights(npc, governance_style: str) -> dict:
    """Get the rights for an NPC based on their social class."""
    hierarchy = SOCIAL_HIERARCHIES.get(governance_style,
                                       SOCIAL_HIERARCHIES["feudalism"])
    sc = getattr(npc, 'social_class', hierarchy["classes"][-1])
    return hierarchy["rights"].get(sc, {
        "travel": True, "own_land": False, "hold_office": False,
        "carry_weapons": False, "tax_exempt": False,
    })


def get_tax_multiplier(npc, governance_style: str) -> float:
    """Get the tax multiplier for an NPC's social class."""
    hierarchy = SOCIAL_HIERARCHIES.get(governance_style,
                                       SOCIAL_HIERARCHIES["feudalism"])
    sc = getattr(npc, 'social_class', hierarchy["classes"][-1])
    return hierarchy["tax_multiplier"].get(sc, 1.0)


def can_travel(npc, governance_style: str) -> bool:
    """Check if an NPC is allowed to travel freely under their governance."""
    rights = get_npc_rights(npc, governance_style)
    return rights.get("travel", True)


def get_class_description(social_class: str, governance_style: str) -> str:
    """Get a human-readable description of a social class."""
    hierarchy = SOCIAL_HIERARCHIES.get(governance_style,
                                       SOCIAL_HIERARCHIES["feudalism"])
    return hierarchy["descriptions"].get(social_class, "Unknown status")


def check_social_mobility(npc, governance_style: str, trigger: str) -> Optional[str]:
    """Check if an NPC can move up in social class based on a trigger event.

    Triggers: "wealth_gained", "military_victory", "royal_decree",
              "marriage", "debt_default", "crime_convicted", "religious_conversion"

    Returns new class name or None.
    """
    hierarchy = SOCIAL_HIERARCHIES.get(governance_style,
                                       SOCIAL_HIERARCHIES["feudalism"])
    mobility = hierarchy.get("mobility", "low")
    current = getattr(npc, 'social_class', hierarchy["classes"][-1])
    classes = hierarchy["classes"]
    current_idx = classes.index(current) if current in classes else len(classes) - 1

    # Can't go higher than the top
    if current_idx <= 1:  # already at or near top
        return None

    # Downward mobility (always possible)
    if trigger == "debt_default":
        if governance_style == "merchant_republic":
            return "debtor"
        elif governance_style == "tyranny":
            return "slave"
    if trigger == "crime_convicted":
        if governance_style == "autocracy":
            return "outcast"
        elif governance_style == "theocracy":
            return "unbeliever"

    # Upward mobility depends on governance
    if mobility == "none":
        return None

    if trigger == "wealth_gained":
        if mobility in ("high", "very_high"):
            gold = getattr(npc, 'npc_gold', 0)
            if governance_style == "merchant_republic" and gold > 80:
                return "patrician" if current != "patrician" else None
            if gold > 50 and current_idx > 2:
                return classes[current_idx - 1]

    if trigger == "military_victory":
        if governance_style in ("feudalism", "tribal", "autocracy"):
            if current_idx > 2:
                return classes[current_idx - 1]

    if trigger == "religious_conversion":
        if governance_style == "theocracy":
            if current in ("unbeliever", "layfolk"):
                return "faithful"

    if trigger == "royal_decree":
        if mobility != "none" and current_idx > 1:
            return classes[current_idx - 1]

    return None


# ================================================================
# LAW ENFORCEMENT
# ================================================================

# Laws that can be active in a kingdom
LAWS = {
    # Movement laws
    "freedom_of_movement":  {"description": "All classes may travel freely", "morale": +5},
    "travel_permits":       {"description": "Lower classes need permits to travel", "morale": -5},
    "curfew":              {"description": "Non-privileged classes must be indoors at night", "morale": -10},

    # Weapons laws
    "open_carry":          {"description": "Anyone may carry weapons", "morale": +3},
    "restricted_arms":     {"description": "Only upper classes may carry weapons", "morale": -5},
    "total_disarmament":   {"description": "No one may carry weapons except guards", "morale": -15},

    # Economic laws
    "free_trade":          {"description": "No restrictions on trade", "morale": +5},
    "guild_monopoly":      {"description": "Only guild members may sell certain goods", "morale": -3},
    "price_controls":      {"description": "Government sets maximum prices", "morale": 0},

    # Social laws
    "equal_rights":        {"description": "All classes have equal legal standing", "morale": +10},
    "class_segregation":   {"description": "Classes must live in separate districts", "morale": -10},
    "interclass_marriage":  {"description": "Marriage between classes is forbidden", "morale": -5},

    # Criminal laws
    "harsh_punishment":    {"description": "Severe penalties for all crimes", "morale": -10},
    "fair_trials":         {"description": "Accused have right to trial", "morale": +5},
    "summary_justice":     {"description": "Guards may judge and punish on the spot", "morale": -15},
}

# Default laws by governance style
DEFAULT_LAWS = {
    "feudalism":          ["travel_permits", "restricted_arms", "guild_monopoly", "fair_trials"],
    "republic":           ["freedom_of_movement", "open_carry", "free_trade", "equal_rights", "fair_trials"],
    "theocracy":          ["travel_permits", "restricted_arms", "guild_monopoly", "class_segregation"],
    "tribal":             ["freedom_of_movement", "open_carry", "free_trade", "summary_justice"],
    "merchant_republic":  ["freedom_of_movement", "open_carry", "free_trade", "fair_trials"],
    "tyranny":            ["curfew", "total_disarmament", "price_controls", "class_segregation", "harsh_punishment", "summary_justice"],
    "autocracy":          ["travel_permits", "restricted_arms", "guild_monopoly", "harsh_punishment"],
    "anarchy":            ["freedom_of_movement", "open_carry", "free_trade"],
}


def get_active_laws(governance_style: str) -> List[str]:
    """Get the list of active laws for a governance style."""
    return DEFAULT_LAWS.get(governance_style, DEFAULT_LAWS["feudalism"])


def is_action_legal(npc, action: str, governance_style: str) -> Tuple[bool, str]:
    """Check if an NPC's action is legal under the current laws.

    Actions: "travel", "carry_weapon", "trade", "steal", "assault", "trespass"
    Returns (is_legal, reason_if_illegal).
    """
    rights = get_npc_rights(npc, governance_style)
    laws = get_active_laws(governance_style)

    if action == "travel":
        if not rights.get("travel", True):
            if "travel_permits" in laws:
                return (False, "Travel requires a permit from your lord")
            if "curfew" in laws:
                return (False, "Curfew in effect — you must stay indoors")
        return (True, "")

    if action == "carry_weapon":
        if not rights.get("carry_weapons", True):
            if "total_disarmament" in laws:
                return (False, "Weapons are banned for your class")
            if "restricted_arms" in laws:
                return (False, "Only the privileged may carry weapons")
        return (True, "")

    if action == "trade":
        if "guild_monopoly" in laws:
            sc = getattr(npc, 'social_class', '')
            if sc in ("serf", "slave", "debtor", "subject"):
                return (False, "Only guild members may trade")
        return (True, "")

    # Criminal actions are always illegal (but enforcement varies)
    if action in ("steal", "assault", "trespass"):
        return (False, f"{action.capitalize()} is a crime")

    return (True, "")
