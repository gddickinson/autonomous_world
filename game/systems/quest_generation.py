"""Procedural quest generation — templates, difficulty scaling."""

import random
from typing import List, Optional
from game.settings import *

def _difficulty_for_level(player_level: int) -> str:
    """Pick a difficulty appropriate for the player's level."""
    if player_level <= 3:
        return random.choices(["easy", "medium"], weights=[3, 1])[0]
    elif player_level <= 7:
        return random.choices(["easy", "medium", "hard"], weights=[1, 3, 1])[0]
    elif player_level <= 12:
        return random.choices(["medium", "hard", "epic"], weights=[1, 3, 1])[0]
    else:
        return random.choices(["hard", "epic"], weights=[2, 3])[0]


def _generate_procedural_quest(player_level: int,
                                settlement: str = "",
                                kingdom: str = "",
                                settlement_names: List[str] = None,
                                kingdom_names: List[str] = None,
                                npc_names: List[str] = None) -> Optional[Quest]:
    """Generate a single procedural quest from templates."""
    template = random.choice(QUEST_TEMPLATES)
    difficulty = _difficulty_for_level(player_level)
    tier = DIFFICULTY_TIERS[difficulty]

    gold = int(template["base_gold"] * tier["gold_mult"])
    xp = int(template["base_xp"] * tier["xp_mult"])
    qtype = template["type"]
    stages = template["stages"]

    # Default fill-ins
    _settlements = settlement_names or [settlement or "the village"]
    _kingdoms = kingdom_names or [kingdom or "the realm"]
    _npcs = npc_names or ["a traveler"]
    dest = random.choice(_settlements)
    npc_name = random.choice(_npcs)

    # Build title and description
    title = template["title"]
    desc = template["desc"]
    target = ""
    target_count = 1

    if qtype == "fetch":
        item = random.choice(FETCH_ITEMS)
        reason = random.choice(FETCH_REASONS)
        target_count = random.randint(2, 5)
        title = title.format(item=item)
        desc = desc.format(item=item, count=target_count, reason=reason)
        target = item

    elif qtype == "kill":
        creature = random.choice(KILL_CREATURES)
        target_count = random.randint(1, 5)
        title = title.format(creature=creature.capitalize())
        desc = desc.format(creature=creature.capitalize(), count=target_count)
        target = creature

    elif qtype == "escort":
        title = title.format(npc=npc_name, destination=dest)
        desc = desc.format(npc=npc_name, destination=dest)
        target = dest

    elif qtype == "deliver":
        item = random.choice(FETCH_ITEMS)
        target_count = random.randint(1, 3)
        title = title.format(item=item, npc=npc_name)
        desc = desc.format(item=item, count=target_count, npc=npc_name, destination=dest)
        target = item

    elif qtype == "investigate":
        location = random.choice(_settlements)
        title = title.format(location=location)
        desc = desc.format(location=location)
        target = location
        target_count = stages  # one "clue" per stage

    elif qtype == "defend":
        threat = random.choice(THREATS)
        target_settlement = random.choice(_settlements)
        title = title.format(settlement=target_settlement, threat=threat.capitalize())
        desc = desc.format(settlement=target_settlement, threat=threat.capitalize())
        target = threat
        target_count = random.randint(3, 8)

    elif qtype == "diplomacy":
        target_kingdom = random.choice(_kingdoms)
        title = title.format(kingdom=target_kingdom)
        desc = desc.format(kingdom=target_kingdom)
        target = target_kingdom
        target_count = stages

    elif qtype == "bounty_hunt":
        criminal = random.choice(CRIMINAL_NAMES)
        target_settlement = random.choice(_settlements)
        title = title.format(criminal=criminal)
        desc = desc.format(criminal=criminal, settlement=target_settlement)
        target = criminal

    # Determine reward item
    reward_item = ""
    if random.random() < 0.4:
        reward_item = random.choice(REWARD_ITEMS.get(difficulty, REWARD_ITEMS["easy"]))

    # Reputation reward scales with difficulty
    rep_amount = {"easy": 5, "medium": 10, "hard": 15, "epic": 20}.get(difficulty, 10)

    # Consequences
    consequence = ""
    if qtype == "defend":
        consequence = "defend_settlement"
    elif qtype == "escort":
        consequence = "npc_safety"
    elif qtype == "diplomacy":
        consequence = "diplomatic"

    quest = Quest(
        title=title,
        description=desc,
        kind=qtype,
        target=target,
        target_count=target_count,
        reward_gold=gold,
        reward_xp=xp,
        reward_item=reward_item,
        reward_reputation=rep_amount,
        difficulty=difficulty,
        stages=stages,
        kingdom=kingdom,
        settlement=settlement,
        consequence=consequence,
    )
    return quest


# ================================================================
# QUEST SYSTEM (main manager)
# ================================================================

class QuestSystem:
    """Manages quests, bounty boards, quest chains, and world consequences."""


