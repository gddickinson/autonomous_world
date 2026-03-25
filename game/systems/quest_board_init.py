"""Quest board initialization, NPC quest generation, and kingdom-special quests.

Separated from quest_board.py for modularity:
- NPC quest generators (guard, merchant, scholar)
- Kingdom-special quest generator (Noble+ rank)
- World initialization of quest boards at tavern settlements
"""

import random
from typing import List

from game.systems.quests import Quest
from game.systems.quest_board import (
    QuestBoardManager,
    generate_bounty_quest,
    generate_delivery_quest,
    generate_investigation_quest,
)


# ================================================================
# KINGDOM-SPECIAL QUESTS (Noble+ rank)
# ================================================================

KINGDOM_SPECIAL_QUESTS = [
    {"title": "Retrieve the King's Lost Heirloom",
     "desc": "The royal heirloom of {kingdom} has been stolen. "
             "Recover it from the thieves' den.",
     "kind": "fetch", "target": "Royal Heirloom", "count": 1,
     "reward_item": "Crown of the Vanquished Lich"},
    {"title": "Diplomatic Mission to the Border",
     "desc": "Carry a sealed treaty to the border garrison of {kingdom}.",
     "kind": "deliver", "target": "border garrison", "count": 1,
     "reward_item": "Boots of Swiftness"},
    {"title": "Destroy the Lich's Phylactery",
     "desc": "A lich threatens {kingdom}. Find and destroy its phylactery.",
     "kind": "investigate", "target": "lich phylactery", "count": 1,
     "reward_item": "Shield of the Faithful"},
]


def generate_kingdom_special_quest(settlement_name: str,
                                   kingdom: str = "",
                                   player_level: int = 1) -> Quest:
    """Generate a special kingdom quest for Noble+ players."""
    template = random.choice(KINGDOM_SPECIAL_QUESTS)
    k_name = kingdom or settlement_name

    level_mult = 1.0 + (player_level - 1) * 0.2
    gold = int(random.randint(50, 100) * level_mult)
    xp = int(gold * 1.5)

    title = template["title"]
    desc = template["desc"].format(kingdom=k_name)

    return Quest(
        title=title,
        description=desc,
        kind=template["kind"],
        target=template["target"],
        target_count=template["count"],
        reward_gold=gold,
        reward_xp=xp,
        reward_item=template.get("reward_item", ""),
        difficulty="hard" if player_level <= 8 else "epic",
        settlement=settlement_name,
    )


# ================================================================
# NPC QUEST GENERATION — for dialog-based quest giving
# ================================================================

def generate_guard_quest(npc_name: str, settlement_name: str,
                         player_level: int = 1) -> Quest:
    """Generate a bounty quest from a guard NPC.

    Guards offer kill quests for threats near their settlement.
    """
    threats = ["wolves", "bandits", "goblins", "spiders"]
    threat = random.choice(threats)
    quest = generate_bounty_quest(settlement_name, player_level, threat)
    quest.giver_name = npc_name
    # Guards give slightly better rewards (official bounty)
    quest.reward_gold = int(quest.reward_gold * 1.2)
    return quest


def generate_merchant_quest(npc_name: str, settlement_name: str,
                            nearby_settlements: List[str] = None,
                            player_level: int = 1) -> Quest:
    """Generate a delivery quest from a merchant NPC.

    Merchants need goods carried to other settlements.
    """
    destinations = nearby_settlements or ["a nearby town"]
    dest = random.choice(destinations)
    quest = generate_delivery_quest(settlement_name, dest, player_level)
    quest.giver_name = npc_name
    # Merchants pay well for reliable couriers
    quest.reward_gold = int(quest.reward_gold * 1.1)
    return quest


def generate_scholar_quest(npc_name: str, settlement_name: str,
                           player_level: int = 1) -> Quest:
    """Generate an investigation quest from a scholar NPC.

    Scholars want ancient sites and mysteries explored.
    """
    quest = generate_investigation_quest(settlement_name,
                                         player_level=player_level)
    quest.giver_name = npc_name
    # Scholars offer extra XP instead of gold
    quest.reward_xp = int(quest.reward_xp * 1.5)
    return quest


# ================================================================
# INITIALIZATION HELPER
# ================================================================

def initialize_quest_boards(world, quest_board_mgr: QuestBoardManager):
    """Set up quest boards for all settlements that have taverns.

    Called during game initialization. Scans settlements for tavern
    buildings and registers a quest board for each.

    Args:
        world: The game world (may have .plan for chunked worlds).
        quest_board_mgr: The QuestBoardManager to populate.
    """
    settlements = []

    # Gather settlement data
    if hasattr(world, 'plan') and hasattr(world.plan, 'settlements'):
        settlements = world.plan.settlements
    elif hasattr(world, 'structures'):
        # Non-chunked world: build pseudo-settlement list
        for s in world.structures:
            if s.kind in ("village", "town", "city", "castle", "hamlet"):
                settlements.append(s)
        # Also register standalone tavern structures
        for s in world.structures:
            if s.kind == 'tavern':
                quest_board_mgr.register_board(
                    s.name, threats=["wolves", "bandits"])

    for sp in settlements:
        has_tavern = False

        # Check buildings list for tavern
        buildings = getattr(sp, 'buildings', [])
        for bld in buildings:
            bkind = bld.get('kind', '') if isinstance(bld, dict) else ''
            if bkind == 'tavern':
                has_tavern = True
                break

        # Also check settlement kind (tavern structures in non-chunked)
        if getattr(sp, 'kind', '') == 'tavern':
            has_tavern = True

        if not has_tavern:
            continue

        # Gather context for quest generation
        nearby = []
        trade_conns = getattr(sp, 'trade_connections', [])
        if trade_conns:
            nearby = trade_conns[:5]
        else:
            # Find closest settlements
            sp_x = getattr(sp, 'x', 0)
            sp_y = getattr(sp, 'y', 0)
            dists = []
            for other in settlements:
                if other.name == sp.name:
                    continue
                ox = getattr(other, 'x', 0)
                oy = getattr(other, 'y', 0)
                d = abs(ox - sp_x) + abs(oy - sp_y)
                dists.append((d, other.name))
            dists.sort()
            nearby = [n for _, n in dists[:4]]

        terrain_ctx = getattr(sp, 'terrain_context', {})

        # Determine threats from terrain
        threats = []
        if terrain_ctx.get('forest', 0) > 5:
            threats.extend(["wolves", "bears", "spiders"])
        if terrain_ctx.get('mountain', 0) > 3:
            threats.extend(["goblins", "orcs"])
        if terrain_ctx.get('swamp', 0) > 3:
            threats.extend(["undead", "spiders"])
        if not threats:
            threats = ["wolves", "bandits"]

        # Determine kingdom for reputation-gated quests
        kingdom = getattr(sp, 'kingdom', '')
        if not kingdom and hasattr(world, 'plan'):
            # Find which kingdom owns this settlement
            for kdata in getattr(world.plan, 'kingdoms', []):
                k_settlements = kdata.get('territory_settlements', [])
                if sp.name in k_settlements:
                    kingdom = kdata['name']
                    break

        quest_board_mgr.register_board(
            sp.name,
            nearby_settlements=nearby,
            terrain_context=terrain_ctx,
            threats=threats,
            kingdom=kingdom,
        )
