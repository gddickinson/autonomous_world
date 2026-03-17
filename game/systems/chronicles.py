"""Historical Chronicles System - auto-generates a readable history of the playthrough.

Records notable events as they happen and formats them into a chronicle
organized by year, season, and era. Viewable in-game with the H key.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


# ================================================================
# CHRONICLE CATEGORIES
# ================================================================

CHRONICLE_CATEGORIES = {
    "war",
    "peace",
    "birth",
    "death",
    "discovery",
    "disaster",
    "miracle",
    "construction",
    "trade",
    "political",
    "religious",
    "quest",
    "undead",
}

# Category display colors (R, G, B)
CATEGORY_COLORS = {
    "war":          (220, 80, 60),
    "peace":        (100, 200, 120),
    "birth":        (180, 220, 160),
    "death":        (160, 120, 120),
    "discovery":    (120, 180, 220),
    "disaster":     (220, 140, 40),
    "miracle":      (220, 200, 100),
    "construction": (160, 160, 180),
    "trade":        (200, 180, 80),
    "political":    (180, 140, 200),
    "religious":    (200, 200, 140),
    "quest":        (100, 200, 200),
    "undead":       (140, 100, 160),
}

# Season names by day-of-year fraction
SEASONS = [
    (0, "Early Spring"),
    (30, "Spring"),
    (60, "Late Spring"),
    (91, "Early Summer"),
    (121, "Summer"),
    (152, "Late Summer"),
    (182, "Early Autumn"),
    (213, "Autumn"),
    (244, "Late Autumn"),
    (274, "Early Winter"),
    (305, "Winter"),
    (335, "Late Winter"),
]


def _season_name(game_day: int) -> str:
    """Get the season name for a given game day (364-day year)."""
    day_of_year = ((game_day - 1) % 364)
    result = "Spring"
    for threshold, name in SEASONS:
        if day_of_year >= threshold:
            result = name
    return result


def _year_from_day(game_day: int) -> int:
    """Get the year number from a game day."""
    return ((game_day - 1) // 364) + 1


# ================================================================
# DATA CLASSES
# ================================================================

@dataclass
class ChronicleEntry:
    """A single recorded event in the chronicle."""
    game_day: int
    category: str
    title: str
    description: str
    importance: int = 1  # 1=minor, 2=notable, 3=major, 4=legendary

    @property
    def year(self) -> int:
        return _year_from_day(self.game_day)

    @property
    def season(self) -> str:
        return _season_name(self.game_day)


@dataclass
class EraMarker:
    """Marks a transition between eras in the chronicle."""
    game_day: int
    era_name: str
    description: str


# ================================================================
# CHRONICLE SYSTEM
# ================================================================

class ChronicleSystem:
    """Auto-generates a readable history of the current playthrough."""

    def __init__(self):
        self.entries: List[ChronicleEntry] = []
        self.era_markers: List[EraMarker] = []
        self._category_counts: Dict[str, int] = {c: 0 for c in CHRONICLE_CATEGORIES}
        self._last_era_day: int = 0
        self._era_check_interval: int = 30  # check for new era every N days
        self._current_era: str = "The Age of Foundation"
        self._max_entries: int = 500

        # Initial era marker
        self.era_markers.append(EraMarker(
            game_day=1,
            era_name="The Age of Foundation",
            description="A new chapter begins in the history of the realm."
        ))

    def record(self, game_day: int, category: str, title: str, description: str,
               importance: int = 1):
        """Record a notable event in the chronicle."""
        if category not in CHRONICLE_CATEGORIES:
            category = "discovery"  # fallback

        entry = ChronicleEntry(
            game_day=game_day,
            category=category,
            title=title,
            description=description,
            importance=importance,
        )
        self.entries.append(entry)
        self._category_counts[category] = self._category_counts.get(category, 0) + 1

        # Cap entries
        if len(self.entries) > self._max_entries:
            # Remove lowest-importance entries first
            self.entries.sort(key=lambda e: (e.importance, e.game_day))
            self.entries = self.entries[-(self._max_entries):]
            self.entries.sort(key=lambda e: e.game_day)

        # Check for era transition
        if game_day - self._last_era_day >= self._era_check_interval:
            self._check_era_transition(game_day)

    def _check_era_transition(self, game_day: int):
        """Check if recent events warrant naming a new era."""
        self._last_era_day = game_day

        # Count recent events by category (last 30 days)
        recent = {}
        for entry in self.entries:
            if entry.game_day > game_day - 30:
                cat = entry.category
                recent[cat] = recent.get(cat, 0) + entry.importance

        if not recent:
            return

        # Find dominant category
        dominant = max(recent, key=recent.get)
        score = recent[dominant]

        # Only create new era if there's enough activity
        if score < 5:
            return

        new_era = self._era_name_for_category(dominant, game_day)
        if new_era != self._current_era:
            self._current_era = new_era
            self.era_markers.append(EraMarker(
                game_day=game_day,
                era_name=new_era,
                description=f"The tenor of the realm shifts as {dominant} events dominate."
            ))

    def _era_name_for_category(self, category: str, game_day: int) -> str:
        """Generate an era name based on dominant event category."""
        era_names = {
            "war":          ["The Time of Strife", "The Age of Iron", "The Warring Days",
                            "The Blood Epoch", "The Season of Swords"],
            "peace":        ["The Golden Peace", "The Age of Prosperity", "The Tranquil Years",
                            "The Era of Harmony"],
            "birth":        ["The Age of Growth", "The Blossoming", "The Era of New Life"],
            "death":        ["The Dark Days", "The Age of Sorrow", "The Mourning Era",
                            "The Withering"],
            "discovery":    ["The Age of Discovery", "The Enlightenment", "The Era of Wonders"],
            "disaster":     ["The Calamity", "The Age of Ruin", "The Dark Times",
                            "The Breaking"],
            "miracle":      ["The Age of Miracles", "The Divine Era", "The Blessed Days"],
            "construction": ["The Age of Building", "The Era of Monuments", "The Great Works"],
            "trade":        ["The Merchant Age", "The Era of Commerce", "The Golden Road"],
            "political":    ["The Age of Diplomacy", "The Political Era", "The Time of Crowns"],
            "religious":    ["The Age of Faith", "The Pious Era", "The Holy Days"],
            "quest":        ["The Age of Heroes", "The Quest Era", "The Adventuring Days"],
            "undead":       ["The Haunted Age", "The Era of Undeath", "The Pale Epoch"],
        }
        import random
        names = era_names.get(category, ["The New Age"])
        # Use game_day as seed for consistency
        rng = random.Random(game_day + hash(category))
        return rng.choice(names)

    def get_era_name(self, game_day: int) -> str:
        """Get the current era name for the given game day."""
        era = "The Age of Foundation"
        for marker in self.era_markers:
            if marker.game_day <= game_day:
                era = marker.era_name
        return era

    def generate_chronicle(self) -> List[str]:
        """Generate a formatted text history of this playthrough.

        Returns a list of strings, each being one line of the chronicle.
        """
        if not self.entries:
            return [
                "THE CHRONICLE OF THE REALM",
                "",
                "  No events have yet been recorded.",
                "  The story waits to be written...",
            ]

        lines = []
        lines.append("THE CHRONICLE OF THE REALM")
        lines.append("=" * 40)
        lines.append("")

        # Sort entries by day
        sorted_entries = sorted(self.entries, key=lambda e: e.game_day)

        # Group by year and season
        current_year = -1
        current_season = ""
        current_era = ""

        for entry in sorted_entries:
            year = entry.year
            season = entry.season

            # Check for era marker at this point
            for marker in self.era_markers:
                if marker.game_day <= entry.game_day and marker.era_name != current_era:
                    current_era = marker.era_name
                    if lines and lines[-1] != "":
                        lines.append("")
                    lines.append(f"--- {current_era} ---")
                    lines.append("")

            # Year header
            if year != current_year:
                current_year = year
                current_season = ""
                if lines and lines[-1] != "":
                    lines.append("")
                lines.append(f"Year {year}")

            # Season subheader
            if season != current_season:
                current_season = season
                lines.append(f"  {season}:")

            # Entry
            importance_prefix = {
                1: "  ",
                2: "  * ",
                3: "  ** ",
                4: "  *** ",
            }
            prefix = importance_prefix.get(entry.importance, "  ")
            lines.append(f"{prefix}{entry.description}")

        lines.append("")
        lines.append(f"-- Chronicle contains {len(self.entries)} recorded events --")
        lines.append(f"-- Current Era: {self._current_era} --")

        return lines

    def get_recent_entries(self, count: int = 10) -> List[ChronicleEntry]:
        """Get the most recent chronicle entries."""
        return self.entries[-count:]

    def get_entries_by_category(self, category: str) -> List[ChronicleEntry]:
        """Get all entries of a specific category."""
        return [e for e in self.entries if e.category == category]


# ================================================================
# EVENT CLASSIFIER - classifies simulation event_log messages
# ================================================================

def classify_event(message: str) -> Optional[Tuple[str, str, int]]:
    """Classify a simulation event message into a chronicle entry.

    Returns (category, title, importance) or None if the event isn't notable enough.
    """
    msg_lower = message.lower()

    # War / Combat events
    if any(w in msg_lower for w in ["battle ", "siege ", "army ", "war ", "attacked", "invaded",
                                     "conquered", "fell to", "defended against"]):
        importance = 3 if any(w in msg_lower for w in ["siege", "conquered", "invaded", "army"]) else 2
        return ("war", _extract_title(message, "Battle"), importance)

    if "engages in combat" in msg_lower:
        return None  # Too common, skip individual combat

    # Death events
    if "has died" in msg_lower or "was killed" in msg_lower or "perished" in msg_lower:
        # Only chronicle notable deaths
        if any(w in msg_lower for w in ["king", "queen", "ruler", "lord", "leader", "chief"]):
            return ("death", _extract_title(message, "Death of a Ruler"), 3)
        if "old age" in msg_lower:
            return ("death", _extract_title(message, "A Passing"), 1)
        return None  # Skip routine deaths

    # Birth events
    if "born" in msg_lower or "child" in msg_lower and "birth" in msg_lower:
        if any(w in msg_lower for w in ["heir", "prince", "princess", "royal"]):
            return ("birth", _extract_title(message, "A Royal Birth"), 3)
        return ("birth", _extract_title(message, "New Life"), 1)

    # Settlement events
    if any(w in msg_lower for w in ["founded", "established", "new settlement", "village founded",
                                     "town founded", "city founded"]):
        return ("construction", _extract_title(message, "Settlement Founded"), 3)

    if any(w in msg_lower for w in ["destroyed", "razed", "burned down", "fell"]):
        if any(w in msg_lower for w in ["settlement", "village", "town", "city"]):
            return ("disaster", _extract_title(message, "Settlement Destroyed"), 3)

    # Construction
    if any(w in msg_lower for w in ["built", "constructed", "completed building"]):
        return ("construction", _extract_title(message, "Construction"), 1)

    # Trade events
    if any(w in msg_lower for w in ["trade route", "merchant", "caravan", "trade flourished",
                                     "market"]):
        if "trade route" in msg_lower:
            return ("trade", _extract_title(message, "Trade Route"), 2)
        return None  # Skip routine trade

    # Disaster events
    if any(w in msg_lower for w in ["plague", "famine", "drought", "flood", "earthquake",
                                     "disaster", "calamity", "storm"]):
        return ("disaster", _extract_title(message, "Disaster"), 3)

    # Miracle / Divine events
    if any(w in msg_lower for w in ["miracle", "divine", "blessing", "holy", "god ",
                                     "goddess", "pantheon", "sacred"]):
        return ("miracle", _extract_title(message, "Divine Event"), 2)

    # Political events
    if any(w in msg_lower for w in ["crowned", "abdicated", "treaty", "alliance",
                                     "diplomatic", "peace accord", "formed an alliance"]):
        importance = 3 if any(w in msg_lower for w in ["crowned", "treaty", "alliance"]) else 2
        return ("political", _extract_title(message, "Political Event"), importance)

    # Quest events
    if any(w in msg_lower for w in ["quest", "chain", "bounty"]):
        if "completed" in msg_lower or "complete" in msg_lower:
            return ("quest", _extract_title(message, "Quest Completed"), 2)
        return None

    # Undead events
    if any(w in msg_lower for w in ["undead", "risen", "zombie", "skeleton", "necromancer",
                                     "necromantic"]):
        return ("undead", _extract_title(message, "Undead Rising"), 2)

    # Religious events
    if any(w in msg_lower for w in ["temple", "shrine", "prayer", "worship", "heresy",
                                     "ritual"]):
        if "heresy" in msg_lower:
            return ("religious", _extract_title(message, "Heresy"), 2)
        return None  # Skip routine prayer

    # Discovery / Technology
    if any(w in msg_lower for w in ["discovered", "invention", "technology", "research",
                                     "breakthrough"]):
        return ("discovery", _extract_title(message, "Discovery"), 2)

    # Peace events
    if any(w in msg_lower for w in ["peace restored", "ceasefire", "truce", "prosperity"]):
        return ("peace", _extract_title(message, "Peace"), 2)

    return None


def _extract_title(message: str, fallback: str) -> str:
    """Extract a short title from a message."""
    # Use first 50 chars or up to first period
    title = message.split(".")[0][:50]
    if not title.strip():
        return fallback
    return title.strip()
