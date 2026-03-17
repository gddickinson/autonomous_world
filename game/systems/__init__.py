"""Core game systems: time, notifications. Other systems split to own modules."""

from typing import List
from game.settings import *


class TimeSystem:
    """Day/night cycle and time tracking with planetary astronomy.

    Day length, sunrise/sunset, and seasons are calculated from Aethermoor's
    latitude (45°N) and the current day of the year. The planet Edras has a
    364-day year with seasons driven by a 23.5° axial tilt.
    """
    def __init__(self):
        from game.systems.astronomy import AETHERMOOR_LATITUDE, get_astronomy
        self.latitude = AETHERMOOR_LATITUDE
        self.time = DAY_LENGTH * DAY_START  # Start at dawn
        self.day = 1
        self.speed = 1.0  # time multiplier

        # Astronomical state (recalculated each day)
        self._astro = get_astronomy(self.latitude, self.day)

    def update(self, dt: float):
        self.time += dt * self.speed
        if self.time >= DAY_LENGTH:
            self.time -= DAY_LENGTH
            old_day = self.day
            self.day += 1
            # Recalculate astronomy on new day
            if self.day != old_day:
                from game.systems.astronomy import get_astronomy
                self._astro = get_astronomy(self.latitude, self.day)

    def _refresh_astro(self):
        """Force refresh astronomical data (call after changing latitude)."""
        from game.systems.astronomy import get_astronomy
        self._astro = get_astronomy(self.latitude, self.day)

    @property
    def normalized(self) -> float:
        """Time as 0.0 to 1.0 (fraction of day)."""
        return self.time / DAY_LENGTH

    @property
    def season(self) -> str:
        """Current season based on planetary position."""
        return self._astro["season"]

    @property
    def day_length_hours(self) -> float:
        """Hours of daylight today (varies by season and latitude)."""
        return self._astro["day_length_hours"]

    @property
    def solar_intensity(self) -> float:
        """Solar intensity 0.0-1.0 (affects temperature and crop growth)."""
        return self._astro["solar_intensity"]

    @property
    def day_of_year(self) -> int:
        """Day within the 364-day year."""
        return self._astro["day_of_year"]

    @property
    def year(self) -> int:
        """Current year number."""
        return self._astro["year"]

    @property
    def lunara_phase(self) -> str:
        """Silver moon phase name."""
        return self._astro["lunara_name"]

    @property
    def thal_phase(self) -> str:
        """Copper moon phase name."""
        return self._astro["thal_name"]

    @property
    def conjunction_near(self) -> bool:
        """Whether both moons are near full (magical event)."""
        return self._astro["conjunction_near"]

    @property
    def is_day(self) -> bool:
        t = self.normalized
        return self._astro["day_start"] <= t < self._astro["dusk_start"]

    @property
    def is_night(self) -> bool:
        t = self.normalized
        return t >= self._astro["night_start"] or t < self._astro["dawn_start"]

    @property
    def darkness(self) -> float:
        """0.0 = full daylight, 1.0 = full darkness. Uses astronomical sunrise/sunset."""
        t = self.normalized
        dawn = self._astro["dawn_start"]
        day_s = self._astro["day_start"]
        dusk = self._astro["dusk_start"]
        night = self._astro["night_start"]

        if day_s <= t < dusk:
            return 0.0
        elif dusk <= t < night:
            span = night - dusk
            return (t - dusk) / span if span > 0 else 1.0
        elif t >= night:
            return 1.0
        elif t < dawn:
            return 1.0
        else:  # dawn to day_start
            span = day_s - dawn
            return 1.0 - (t - dawn) / span if span > 0 else 0.0

    @property
    def time_string(self) -> str:
        """Human-readable time with season and astronomical info."""
        hours = int(self.normalized * 24)
        minutes = int((self.normalized * 24 - hours) * 60)
        season = self.season.capitalize()
        return f"Day {self.day} ({season}), {hours:02d}:{minutes:02d}"

    @property
    def astronomy_string(self) -> str:
        """Detailed astronomical status for UI display."""
        dl = self.day_length_hours
        lunara = self._astro["lunara_name"]
        thal = self._astro["thal_name"]
        parts = [
            f"Year {self.year}, Day {self.day_of_year + 1}/364",
            f"Season: {self.season.capitalize()}",
            f"Daylight: {dl:.1f}h",
            f"Lunara: {lunara}",
            f"Thal: {thal}",
        ]
        if self.conjunction_near:
            parts.append("CONJUNCTION NEAR!")
        return " | ".join(parts)


class Notification:
    """A temporary on-screen notification."""
    def __init__(self, text: str, duration: float = 3.0, color=None):
        self.text = text
        self.duration = duration
        self.timer = duration
        self.color = color or UI_TEXT
        self.alpha = 1.0


class NotificationSystem:
    """Manages on-screen notifications."""
    def __init__(self):
        self.notifications: List[Notification] = []

    def add(self, text: str, duration: float = 3.0, color=None):
        self.notifications.append(Notification(text, duration, color))

    def update(self, dt: float):
        for n in self.notifications:
            n.timer -= dt
            if n.timer < 1.0:
                n.alpha = max(0, n.timer)
        self.notifications = [n for n in self.notifications if n.timer > 0]


# Backward-compatible re-exports
from game.systems.combat import CombatSystem
from game.systems.quests import Quest, QuestSystem
from game.systems.world_manager import WorldManager
from game.systems.simulation import SimulationManager
