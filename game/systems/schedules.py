"""
NPC daily schedule system - Sims-style routines based on time-of-day and class.
NPCs wake, eat, work, socialize, shop, and sleep on realistic schedules.
Work periods now use skill-based actions matching each class's strengths.
"""

import random
import math
from typing import Optional


# Schedule phases mapped to time-of-day (0.0-1.0)
SCHEDULE = {
    "sleep":     (0.00, 0.22),  # midnight to early morning
    "wake_eat":  (0.22, 0.28),  # wake up and breakfast
    "morning_work": (0.28, 0.48),  # morning work shift
    "lunch":     (0.48, 0.53),  # lunch break
    "afternoon_work": (0.53, 0.68),  # afternoon work
    "evening":   (0.68, 0.78),  # dinner, tavern, socialize
    "night":     (0.78, 1.00),  # go home, sleep
}

# Skill-based work actions by class — these fire during work hours
CLASS_WORK_ACTIONS = {
    "Fighter":   [
        "TRAIN_COMBAT | training ground | morning drill",
        "TRAIN_COMBAT | training ground | sword practice",
        "MOVE_TO | village | patrolling the settlement",
        "GUARD_WALL | wall | standing watch on the walls",
        "GUARD_GATE | gate | guarding the main gate",
        "PATROL | village perimeter | walking the perimeter",
    ],
    "Wizard":    [
        "RESEARCH | library | studying arcane texts",
        "ENCHANT_ITEM | workshop | working on enchantments",
        "RESEARCH | library | cataloguing spell components",
    ],
    "Cleric":    [
        "PRAY | chapel | morning prayers",
        "HEAL_OTHER | nearby | tending to the sick",
        "RESEARCH | library | studying scripture",
    ],
    "Rogue":     [
        "SNEAK | village | practicing stealth",
        "PICK_LOCK | locked door | testing locks",
        "SET_TRAP | wilderness | laying snares",
        "MOVE_TO | ruins | looking for opportunities",
    ],
    "Ranger":    [
        "TRACK | wilderness | scouting for threats",
        "TRAIN_ARCHERY | range | target practice",
        "TRAIN_ANIMAL | stable | working with animals",
        "NAVIGATE | forest | mapping the wilds",
        "GUARD_TOWER | tower | manning the watchtower",
        "SCOUT | village perimeter | watching for enemies",
    ],
    "Paladin":   [
        "TRAIN_COMBAT | training ground | martial training",
        "PRAY | chapel | devotional prayers",
        "MOVE_TO | village | protecting the innocent",
        "GUARD_GATE | gate | defending the gate",
        "PATROL | village perimeter | holy vigil",
    ],
    "Barbarian": [
        "TRAIN_COMBAT | training ground | strength training",
        "CLIMB | mountain | physical conditioning",
        "SWIM | river | endurance training",
    ],
    "Bard":      [
        "PERFORM | marketplace | entertaining the crowd",
        "RESEARCH | library | studying lore and legends",
        "PERFORM | tavern | playing music for patrons",
    ],
    "Druid":     [
        "TRAIN_ANIMAL | stable | communing with animals",
        "FORAGE | forest | gathering herbs",
        "PERFORM_RITUAL | ritual circle | nature ritual",
        "DIVINE | sacred grove | reading the omens",
    ],
    "Monk":      [
        "PRAY | chapel | morning meditation",
        "TRAIN_COMBAT | training ground | martial arts practice",
        "CLIMB | mountain | physical discipline",
        "SWIM | river | breath control training",
    ],
    "Sorcerer":  [
        "RESEARCH | library | studying innate magic",
        "PERFORM_RITUAL | ritual circle | channeling power",
    ],
    "Warlock":   [
        "RESEARCH | library | studying forbidden texts",
        "PERFORM_RITUAL | ritual circle | patron communion",
        "DIVINE | quiet spot | consulting the beyond",
    ],
    "Merchant":  [
        "TRADE | nearby | looking to buy and sell",
        "MOVE_TO | market | managing the shop",
        "MAKE_MAP | map room | charting trade routes",
    ],
    "Guard":     [
        "GUARD_WALL | wall | standing watch on the walls",
        "GUARD_GATE | gate | guarding the gate",
        "PATROL | village perimeter | walking the perimeter",
        "TRAIN_COMBAT | training ground | drilling",
        "GUARD_TOWER | tower | manning the watchtower",
    ],
    "Farmer":    [
        "FARM | plant | tending crops",
        "FARM | harvest | checking the fields",
        "TRAIN_ANIMAL | stable | caring for livestock",
        "FETCH_WATER | well | fetching water for the farm",
        "GATHER_FIREWOOD | forest | gathering firewood",
    ],
    "Healer":    [
        "HEAL_OTHER | nearby | treating patients",
        "FORAGE | herbs | gathering medicinal herbs",
        "RESEARCH | library | studying medical texts",
    ],
    "Innkeeper": [
        "MOVE_TO | tavern | managing the inn",
        "TRADE | nearby | buying supplies",
    ],
    "Fisher":    [
        "FISH | water | casting lines",
        "SWIM | water | checking nets",
        "NAVIGATE | coastline | charting fishing spots",
    ],
    "Miner":     [
        "MINE_ROCK | nearby | working the mine",
        "CLIMB | mine shaft | exploring deeper veins",
    ],
    "Scholar":   [
        "RESEARCH | library | reading ancient texts",
        "MAKE_MAP | map room | documenting the region",
        "RESEARCH | library | translating old manuscripts",
    ],
}

# Title-specific duty overrides — these REPLACE class actions when the NPC
# holds a specific military/civic title. Guards spend most time on walls/gates,
# not just doing generic fighter training.
TITLE_DUTY_ACTIONS = {
    "guard": [
        "GUARD_WALL | wall | standing watch on the walls",
        "GUARD_GATE | gate | guarding the main gate",
        "PATROL | village perimeter | perimeter patrol",
        "GUARD_TOWER | tower | manning the watchtower",
        "TRAIN_COMBAT | training ground | guard drill",
    ],
    "sergeant": [
        "PATROL | village perimeter | inspecting the guard posts",
        "GUARD_GATE | gate | overseeing gate security",
        "TRAIN_COMBAT | training ground | drilling the troops",
        "GUARD_WALL | wall | inspecting wall defenses",
    ],
    "captain": [
        "PATROL | village perimeter | security inspection",
        "GUARD_GATE | gate | commanding gate defense",
        "MOVE_TO | barracks | reviewing troop readiness",
        "TRAIN_COMBAT | training ground | leading exercises",
    ],
    "knight": [
        "TRAIN_COMBAT | training ground | mounted combat practice",
        "PATROL | village perimeter | knightly patrol",
        "GUARD_GATE | gate | defending the gate with honor",
        "PRAY | chapel | vigil of devotion",
    ],
    "servant": [
        "MOVE_TO | kitchen | preparing meals",
        "MOVE_TO | storage | fetching supplies",
        "MOVE_TO | common_room | cleaning and tidying",
        "FETCH_WATER | well | drawing water",
    ],
}


def get_schedule_phase(time_normalized: float) -> str:
    """Get the current schedule phase for a given time."""
    for phase, (start, end) in SCHEDULE.items():
        if start <= time_normalized < end:
            return phase
    return "sleep"


def get_scheduled_action(npc, time_normalized: float, world, structures) -> Optional[dict]:
    """
    Get what an NPC should be doing based on schedule.
    Returns {"action": str, "target_x": float, "target_y": float, "reason": str}
    or None if no schedule override.
    """
    phase = get_schedule_phase(time_normalized)
    char_class = getattr(npc, 'char_class', '')

    if phase == "sleep":
        return {
            "action": "SLEEP",
            "target_x": npc.home_x,
            "target_y": npc.home_y,
            "reason": "time to sleep",
        }

    elif phase == "wake_eat":
        if npc.has_food():
            return {
                "action": "EAT",
                "target_x": npc.home_x,
                "target_y": npc.home_y,
                "reason": "breakfast time",
            }
        return None

    elif phase in ("morning_work", "afternoon_work"):
        # Title-specific duties override class actions (guards patrol walls, etc.)
        title = getattr(npc, 'title', 'commoner')
        title_actions = TITLE_DUTY_ACTIONS.get(title)
        if title_actions:
            chosen = random.choice(title_actions)
            parts = [p.strip() for p in chosen.split("|")]
            action = parts[0]
            reason = parts[2] if len(parts) > 2 else "on duty"
            return {"action": action, "target_x": None, "target_y": None,
                    "reason": reason}

        # Otherwise use class-specific skill actions
        cls = char_class or getattr(npc, 'profession', 'Farmer')
        work_actions = CLASS_WORK_ACTIONS.get(cls, CLASS_WORK_ACTIONS.get("Farmer"))
        if work_actions:
            chosen = random.choice(work_actions)
            parts = [p.strip() for p in chosen.split("|")]
            action = parts[0]
            reason = parts[2] if len(parts) > 2 else "working"
            return {"action": action, "target_x": None, "target_y": None,
                    "reason": reason}
        return None

    elif phase == "lunch":
        tavern = _find_nearest_structure(npc, structures, "tavern")
        if tavern and npc.npc_gold >= 3:
            return {
                "action": "MOVE_TO",
                "target_x": float(tavern.x),
                "target_y": float(tavern.y),
                "reason": "lunch at the tavern",
            }
        elif npc.has_food():
            return {"action": "EAT", "target_x": npc.x, "target_y": npc.y,
                    "reason": "eating lunch"}
        return None

    elif phase == "evening":
        tavern = _find_nearest_structure(npc, structures, "tavern")
        if tavern:
            return {
                "action": "MOVE_TO",
                "target_x": float(tavern.x),
                "target_y": float(tavern.y),
                "reason": "evening at the tavern",
            }
        return None

    elif phase == "night":
        return {
            "action": "MOVE_TO",
            "target_x": npc.home_x,
            "target_y": npc.home_y,
            "reason": "heading home for the night",
        }

    return None


def _find_nearest_structure(npc, structures, kind: str):
    """Find nearest structure of given kind."""
    best = None
    best_dist = float('inf')
    for s in structures:
        if s.kind == kind:
            dx = npc.x - s.x
            dy = npc.y - s.y
            d = dx * dx + dy * dy
            if d < best_dist:
                best_dist = d
                best = s
    return best
