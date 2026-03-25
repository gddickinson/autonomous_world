"""
NPC Ecological Responses — NPCs react to ecological events.

Functions in this module are called by EcosystemManager when ecological
events occur (predator attacks on livestock, crop pest damage, food
shortages, creature overpopulation).  Each function modifies NPC state
and appends entries to the shared event log.
"""

import math
import random
from typing import List, Optional


# ------------------------------------------------------------------
# Predator attacks on settlement livestock
# ------------------------------------------------------------------

def respond_to_predator_attack(settlement, predator_kind: str, npcs: list,
                                event_log: list):
    """Guards hunt the predator type; farmers remember the attack.

    Args:
        settlement: structure object (has .x, .y, .name, .kind)
        predator_kind: e.g. "wolf"
        npcs: list of all NPCs
        event_log: shared log list
    """
    sx, sy = settlement.x, settlement.y

    for npc in npcs:
        if not npc.alive:
            continue
        d2 = (npc.x - sx) ** 2 + (npc.y - sy) ** 2
        if d2 > 30 * 30:
            continue

        profession = getattr(npc, 'profession', '')

        # Guards go hunting
        if profession in ("guard", "soldier", "knight", "ranger"):
            npc.current_action = "hunting"
            npc.state = "walking"
            # Point them outward from settlement center
            angle = math.atan2(npc.y - sy, npc.x - sx)
            npc.target_x = sx + math.cos(angle) * 25
            npc.target_y = sy + math.sin(angle) * 25
            npc.add_memory("ecology",
                           f"{predator_kind.capitalize()}s attacked our "
                           f"livestock near {settlement.name}!", 3)

        # Farmers remember
        elif profession in ("farmer", "rancher"):
            npc.add_memory("ecology",
                           f"{predator_kind.capitalize()}s killed our sheep!", 2)

    event_log.append(
        f"{predator_kind.capitalize()}s attacked livestock near "
        f"{settlement.name}")


# ------------------------------------------------------------------
# Crop pest damage
# ------------------------------------------------------------------

def respond_to_crop_damage(settlement, pest_kind: str, npcs: list,
                            event_log: list):
    """Farmers guard farmland; hunters dispatched to reduce pests.

    Args:
        settlement: structure object
        pest_kind: e.g. "deer"
        npcs: list of all NPCs
        event_log: shared log list
    """
    sx, sy = settlement.x, settlement.y

    for npc in npcs:
        if not npc.alive:
            continue
        d2 = (npc.x - sx) ** 2 + (npc.y - sy) ** 2
        if d2 > 30 * 30:
            continue

        profession = getattr(npc, 'profession', '')

        if profession == "farmer":
            npc.current_action = "guarding"
            npc.state = "idle"
            npc.add_memory("ecology",
                           f"{pest_kind.capitalize()} are eating our crops!", 2)

        elif profession in ("ranger", "hunter"):
            npc.current_action = "hunting"
            npc.state = "walking"
            npc.target_x = sx + random.uniform(-15, 15)
            npc.target_y = sy + random.uniform(-15, 15)
            npc.add_memory("ecology",
                           f"Dispatched to deal with {pest_kind} plague "
                           f"near {settlement.name}", 2)

    event_log.append(
        f"{pest_kind.capitalize()} are eating crops near {settlement.name}")


# ------------------------------------------------------------------
# Food shortage
# ------------------------------------------------------------------

def respond_to_food_shortage(settlement, npcs: list, event_log: list):
    """When food stores are low: NPCs trade more or migrate.

    Args:
        settlement: structure object
        npcs: list of all NPCs
        event_log: shared log list
    """
    sx, sy = settlement.x, settlement.y
    affected = []

    for npc in npcs:
        if not npc.alive:
            continue
        d2 = (npc.x - sx) ** 2 + (npc.y - sy) ** 2
        if d2 > 40 * 40:
            continue
        affected.append(npc)

    if not affected:
        return

    for npc in affected:
        profession = getattr(npc, 'profession', '')
        npc.add_memory("ecology",
                       f"Food shortage in {settlement.name}", 3)

        # Merchants prioritise food trading
        if profession in ("merchant", "trader"):
            npc.add_memory("ecology",
                           "Must trade for food — people are hungry", 2)

        # Some NPCs may migrate if prolonged shortage
        # (tracked by repeated calls — 3rd call triggers migration)
        shortage_count = _count_food_shortage_memories(npc)
        if shortage_count >= 3 and random.random() < 0.15:
            # Migrate: shift home outward
            angle = random.uniform(0, 2 * math.pi)
            npc.home_x += math.cos(angle) * 40
            npc.home_y += math.sin(angle) * 40
            npc.target_x = npc.home_x
            npc.target_y = npc.home_y
            npc.state = "walking"
            npc.add_memory("ecology",
                           f"Leaving {settlement.name} due to famine", 4)

    event_log.append(f"Food shortage in {settlement.name}")


# ------------------------------------------------------------------
# Creature overpopulation
# ------------------------------------------------------------------

def respond_to_overpopulation(creature_kind: str, region_x: float,
                               region_y: float, npcs: list,
                               event_log: list):
    """Hunters receive bounty quests for overpopulated creatures.

    Args:
        creature_kind: e.g. "deer"
        region_x, region_y: approximate centre of the overpopulated area
        npcs: list of all NPCs
        event_log: shared log list
    """
    # Find nearest settlement name for log message
    settlement_label = f"({int(region_x)}, {int(region_y)})"

    dispatched = 0
    for npc in npcs:
        if not npc.alive:
            continue
        if dispatched >= 3:
            break
        profession = getattr(npc, 'profession', '')
        if profession not in ("ranger", "hunter", "guard"):
            continue
        d2 = (npc.x - region_x) ** 2 + (npc.y - region_y) ** 2
        if d2 > 60 * 60:
            continue

        npc.current_action = "hunting"
        npc.state = "walking"
        npc.target_x = region_x + random.uniform(-10, 10)
        npc.target_y = region_y + random.uniform(-10, 10)
        npc.add_memory("ecology",
                       f"Bounty: cull {creature_kind} plague near "
                       f"{settlement_label}", 3)
        dispatched += 1

    event_log.append(
        f"{creature_kind.capitalize()} plague reported near "
        f"{settlement_label}")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _count_food_shortage_memories(npc) -> int:
    """Count how many 'Food shortage' memories the NPC has."""
    count = 0
    memories = getattr(npc, 'memories', [])
    for m in memories:
        text = m.get("text", "") if isinstance(m, dict) else str(m)
        if "Food shortage" in text:
            count += 1
    return count
