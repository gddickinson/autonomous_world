"""NPC Daily Schedule System — time-based routines for a living world.

NPCs follow daily schedules based on profession and time of day:
  05-06: Wake/eat  06-12: Morning work  12-13: Lunch
  13-17: Afternoon work  17-19: Leisure  19-20: Dinner  20-05: Sleep
"""

import math
from typing import Optional, Tuple

# Work actions by profession (what they do during work hours)
PROFESSION_WORK = {
    "Guard": ("guarding", None),
    "Soldier": ("guarding", None),
    "Captain": ("guarding", None),
    "Knight": ("guarding", None),
    "Farmer": ("farming", "farmland"),
    "Shepherd": ("herding", "pasture"),
    "Baker": ("baking", "bakery"),
    "Cook": ("cooking", "tavern"),
    "Innkeeper": ("innkeeping", "tavern"),
    "Merchant": ("trading", "market"),
    "Blacksmith": ("smithing", "forge"),
    "Carpenter": ("building", "workshop"),
    "Mason": ("masonry", "workshop"),
    "Woodcutter": ("chopping", "forest"),
    "Hunter": ("hunting", "wilderness"),
    "Fisherman": ("fishing", "water"),
    "Miner": ("mining", "mine"),
    "Scholar": ("studying", "library"),
    "Scribe": ("studying", "library"),
    "Healer": ("healing", "temple"),
    "Herbalist": ("gathering", "garden"),
    "Priest": ("praying", "temple"),
    "Weaver": ("weaving", "workshop"),
    "Tanner": ("tanning", "workshop"),
    "Potter": ("crafting", "workshop"),
    "Brewer": ("brewing", "tavern"),
    "Alchemist": ("researching", "workshop"),
    "Bard": ("performing", "tavern"),
    "Diplomat": ("administering", "town_hall"),
    "Advisor": ("administering", "town_hall"),
    "Stable Master": ("herding", "stable"),
    "Laborer": ("working", None),
    "Porter": ("carrying", None),
    "Builder": ("building", None),
    "Prospector": ("mining", "mountain"),
    "Sailor": ("working", "dock"),
    "Dock Worker": ("carrying", "dock"),
}

# Default for unknown professions
DEFAULT_WORK = ("working", None)


class DailySchedule:
    """Manages time-based NPC routines."""

    def get_scheduled_action(self, npc, hour: float, is_storm: bool = False
                             ) -> Optional[Tuple[str, Optional[str]]]:
        """Return (action, target_place) for this NPC at this hour.

        Returns None during free time (NPC can make own decisions).
        Returns ("sleeping", "home") at night, etc.
        """
        # Combat overrides schedule
        if getattr(npc, 'state', '') == 'combat':
            return None
        if getattr(npc, 'combat_target', None) is not None:
            return None
        # Fleeing overrides schedule
        if getattr(npc, 'state', '') == 'fleeing':
            return None

        prof = getattr(npc, 'profession', '')

        # Night: sleep (20:00 - 05:00)
        if hour >= 20 or hour < 5:
            # Guards work night shift too (half of them)
            if prof in ('Guard', 'Soldier', 'Captain', 'Knight'):
                name_hash = hash(getattr(npc, 'name', '')) % 2
                if name_hash == 0:  # half the guards sleep
                    return ("sleeping", "home")
                else:  # other half patrol at night
                    return ("guarding", None)
            return ("sleeping", "home")

        # Early morning: wake up, eat (05:00 - 06:00)
        if 5 <= hour < 6:
            return ("eating", "home")

        # Morning work (06:00 - 12:00)
        if 6 <= hour < 12:
            return self._get_work(prof)

        # Lunch (12:00 - 13:00)
        if 12 <= hour < 13:
            return ("eating", "tavern")

        # Afternoon work (13:00 - 17:00)
        if 13 <= hour < 17:
            return self._get_work(prof)

        # Evening leisure (17:00 - 19:00)
        if 17 <= hour < 19:
            # NPCs socialize, visit tavern, walk around
            name_hash = hash(getattr(npc, 'name', '')) % 3
            if name_hash == 0:
                return ("socializing", "tavern")
            elif name_hash == 1:
                return ("walking", None)
            else:
                return None  # free time — use regular decision system

        # Dinner (19:00 - 20:00)
        if 19 <= hour < 20:
            return ("eating", "home")

        return None

    def _get_work(self, profession: str) -> Tuple[str, Optional[str]]:
        """Get the work action for a profession."""
        return PROFESSION_WORK.get(profession, DEFAULT_WORK)

    def get_action_for_schedule(self, npc, hour: float, world=None,
                                is_storm: bool = False) -> Optional[str]:
        """Simplified interface: return just the action string, or None."""
        result = self.get_scheduled_action(npc, hour, is_storm)
        if result is None:
            return None
        action, target = result
        # If the action requires going to a specific place, set target
        if target == "home" and action in ("sleeping", "eating"):
            hx = getattr(npc, 'home_x', npc.x)
            hy = getattr(npc, 'home_y', npc.y)
            if abs(npc.x - hx) > 2 or abs(npc.y - hy) > 2:
                npc.target_x = hx
                npc.target_y = hy
                return "commuting"
            if action == "sleeping":
                # Set lying pose when at home
                if hasattr(npc, 'state'):
                    npc.state = 'resting'
                return "sleeping"
        return action


# Module-level singleton
_schedule = DailySchedule()


def get_daily_action(npc, hour: float, world=None, is_storm: bool = False
                     ) -> Optional[str]:
    """Get the scheduled action for an NPC at this hour.

    Returns an action string or None (use regular decision system).
    """
    return _schedule.get_action_for_schedule(npc, hour, world, is_storm)
