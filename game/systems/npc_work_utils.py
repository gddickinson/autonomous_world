"""NPC work utilities — work station assignment, profession mapping."""

import random
import math
from typing import List, Dict, Optional
from game.settings import *


class NpcWorkUtilsMixin:

    """Mixin — see parent class for context."""

    def _profession_to_zone(self, profession: str) -> Optional[str]:
        """Map profession to zone type."""
        zone_map = {
            "Blacksmith": "smithy",
            "Armourer":   "smithy",
            "Wizard": "library",
            "Scholar": "library",
            "Sorcerer": "library",
            "Warlock": "library",
            "Scribe": "library",
            "Cartographer": "library",
            "Advisor": "library",
            "Cleric": "chapel",
            "Monk": "chapel",
            "Paladin": "chapel",
            "Bard": "tavern",
            "Innkeeper": "tavern",
            "Cook": "tavern",
            "Baker": "tavern",
            "Brewer": "tavern",
            "Barber": "tavern",
            "Healer": "infirmary",
            "Alchemist": "infirmary",
            "Farmer": "farm",
            "Shepherd": "farm",
            "Beekeeper": "farm",
            "Carpenter": "workshop",
            "Cooper": "workshop",
            "Wheelwright": "workshop",
            "Tanner": "tannery",
            "Weaver": "workshop",
            "Potter": "workshop",
            "Stablemaster": "stable",
            "Animal Trainer": "stable",
            "Merchant": "market",
            "Shop Assistant": "market",
            "Banker": "market",
        }
        return zone_map.get(profession)

    # ================================================================
    # STATE: Going to work
    # ================================================================

def daily_price_gossip(npcs: list, world_effects):
    """Run once per day: give trade-aware NPCs price gossip memories."""
    if not world_effects:
        return
    trade_professions = {"Merchant", "Trader", "Innkeeper", "Banker",
                         "Shop Assistant", "Barber"}
    for npc in npcs:
        if not getattr(npc, 'alive', True):
            continue
        profession = getattr(npc, 'profession', '')
        settlement = getattr(npc, 'home_settlement', None)
        if not settlement:
            settlement = getattr(npc, 'faction', None)
        if not settlement:
            continue

        if profession in trade_professions:
            inject_price_gossip(npc, world_effects, settlement)
        elif random.random() < 0.1:
            # 10% chance for non-trade NPCs to notice prices
            inject_price_gossip(npc, world_effects, settlement)


# ================================================================
# FOREIGN TRADE / CARAVAN SYSTEM
# ================================================================

class CaravanSystem:
    """Manages foreign merchant caravans that bring trade goods.

    Caravans arrive at towns/cities periodically, selling foreign luxury
    goods and buying local surplus.  This is the only source for items
    in FOREIGN_TRADE_GOODS.
    """


