"""Starting quest — guides newly awakened players to the nearest settlement."""

import math
from typing import Optional


def create_starting_quest(world, quest_sys) -> Optional[str]:
    """Create and add the 'Find Civilization' starting quest.

    Finds the nearest settlement to the spawn temple and creates a quest
    to reach it. Returns the settlement name or None if no settlement found.
    """
    from game.systems.quests import Quest

    sx, sy = world.spawn_point

    # Find the nearest settlement
    nearest = None
    nearest_dist = float("inf")
    for s in world.structures:
        if s.kind in ("village", "town", "city", "hamlet", "castle"):
            dx = s.x - sx
            dy = s.y - sy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = s

    if nearest is None:
        return None

    settlement_name = nearest.name
    quest = Quest(
        title="Find Civilization",
        description=(
            "You've awakened at an ancient temple with no memory of how "
            "you got here. Find the nearest settlement and speak with the "
            f"locals. The settlement of {settlement_name} should be nearby."
        ),
        kind="investigate",
        target=settlement_name,
        target_count=1,
        reward_gold=10,
        reward_xp=25,
        difficulty="easy",
        stages=1,
    )
    quest.giver_name = "Temple of Awakening"
    quest.hint = "A guard might know of work available."

    quest_sys.accept_quest(quest)
    return settlement_name
