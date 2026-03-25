"""
Kingdom AI — shared constants, data classes, and governance priority profiles.

Imported by both kingdom_ai.py (main AI) and kingdom_ai_war.py (war mixin).
"""

from typing import Dict, List, Optional, Tuple


# ================================================================
# GOVERNANCE PRIORITY PROFILES
# ================================================================

GOVERNANCE_PRIORITIES = {
    "feudalism":        {"military": 0.35, "defense": 0.25, "economy": 0.25, "expansion": 0.15},
    "republic":         {"military": 0.20, "defense": 0.25, "economy": 0.40, "expansion": 0.15},
    "theocracy":        {"military": 0.20, "defense": 0.30, "economy": 0.30, "expansion": 0.20},
    "tribal":           {"military": 0.45, "defense": 0.10, "economy": 0.15, "expansion": 0.30},
    "autocracy":        {"military": 0.30, "defense": 0.25, "economy": 0.25, "expansion": 0.20},
    "tyranny":          {"military": 0.40, "defense": 0.20, "economy": 0.15, "expansion": 0.25},
    "merchant_republic":{"military": 0.15, "defense": 0.20, "economy": 0.45, "expansion": 0.20},
    "anarchy":          {"military": 0.30, "defense": 0.10, "economy": 0.20, "expansion": 0.40},
    "magocracy":        {"military": 0.15, "defense": 0.20, "economy": 0.30, "expansion": 0.35},
    "confederation":    {"military": 0.25, "defense": 0.20, "economy": 0.35, "expansion": 0.20},
    "monarchy":         {"military": 0.30, "defense": 0.25, "economy": 0.30, "expansion": 0.15},
}

DEFAULT_PRIORITIES = {"military": 0.25, "defense": 0.25, "economy": 0.25, "expansion": 0.25}

# Defensive buildings ordered by cost (cheapest first)
DEFENSE_BUILDINGS = ["watchtower", "barracks", "walls"]
# Economic buildings ordered by cost
ECONOMY_BUILDINGS = ["market", "granary", "workshop", "warehouse"]

# Costs and thresholds
SOLDIER_RECRUIT_COST = 20
GUARD_RECRUIT_COST = 2
WAR_DECLARATION_MIN_TREASURY = 500
WAR_DECLARATION_ARMY_RATIO = 1.2
PEACE_TREATY_TRIBUTE_FRACTION = 0.50
WAR_MAX_DAYS = 60
PEACE_EXHAUSTION_THRESHOLD = 80
ARMY_MIN_FOR_WAR = 10


# ================================================================
# KINGDOM STOCKPILE STATE
# ================================================================

class KingdomStockpile:
    """Tracks food, weapons, and gold reserves for a kingdom."""

    def __init__(self):
        self.food = 50.0
        self.weapons = 20.0
        self.gold_reserve = 0.0

    def as_dict(self) -> Dict[str, float]:
        return {"food": round(self.food, 1),
                "weapons": round(self.weapons, 1),
                "gold_reserve": round(self.gold_reserve, 1)}


# ================================================================
# WAR STATE
# ================================================================

class WarState:
    """Tracks an active war between two kingdoms."""

    def __init__(self, attacker: str, defender: str, start_day: int):
        self.attacker = attacker
        self.defender = defender
        self.start_day = start_day
        self.battles_fought = 0
        self.settlements_captured: List[Tuple[str, str]] = []
        self.ended = False
        self.winner: Optional[str] = None
