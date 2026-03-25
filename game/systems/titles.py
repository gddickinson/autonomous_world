"""Reputation and Title system — titles earned through gameplay milestones.

Tracks kill counts per creature type, settlements visited, quests completed
per settlement, and awards titles when thresholds are met.
"""

from typing import Dict, List, Set, Optional


# ================================================================
# TITLE DEFINITIONS
# ================================================================

# Each title: (id, display_name, description, check_function_name)
# The check functions are methods on TitleTracker.
TITLE_DEFINITIONS = [
    ("rat_slayer",       "Rat Slayer",           "Kill 5 rats"),
    ("wolf_hunter",      "Wolf Hunter",          "Kill 10 wolves"),
    ("dragons_bane",     "Dragon's Bane",        "Kill a dragon"),
    ("explorer",         "Explorer",             "Visit 10 settlements"),
    ("wealthy",          "Wealthy",              "Accumulate 500 gold"),
    ("champion_arena",   "Champion of the Arena", "Win colosseum tournament"),
]

# Settlement-specific titles are generated dynamically:
#   "Friend of [Settlement]" — complete 3 quests for a settlement

# Kill-based title requirements: (title_id, creature_kind, count)
KILL_TITLES = [
    ("rat_slayer",  "rat",    5),
    ("wolf_hunter", "wolf",  10),
    ("dragons_bane", "dragon", 1),
]


class TitleTracker:
    """Tracks player achievements and awards titles.

    Stored on the player object as player.title_tracker.
    """

    def __init__(self):
        # Tracking data
        self.kill_counts: Dict[str, int] = {}       # creature_kind -> count
        self.settlements_visited: Set[str] = set()   # settlement names
        self.quests_per_settlement: Dict[str, int] = {}  # settlement -> count
        self.max_gold_held: int = 0
        self.arena_won: bool = False

        # Earned titles
        self.earned_titles: List[str] = []  # list of title display names
        self.active_title: str = ""         # currently displayed title

    def record_kill(self, creature_kind: str):
        """Record a creature kill."""
        kind = creature_kind.lower().replace(" ", "_")
        self.kill_counts[kind] = self.kill_counts.get(kind, 0) + 1

    def record_settlement_visit(self, settlement_name: str):
        """Record visiting a settlement."""
        self.settlements_visited.add(settlement_name)

    def record_quest_complete(self, settlement_name: str):
        """Record completing a quest for a settlement."""
        if settlement_name:
            self.quests_per_settlement[settlement_name] = (
                self.quests_per_settlement.get(settlement_name, 0) + 1
            )

    def record_gold(self, gold: int):
        """Update max gold tracking."""
        if gold > self.max_gold_held:
            self.max_gold_held = gold

    def record_arena_win(self):
        """Record winning the colosseum tournament."""
        self.arena_won = True

    def check_and_award(self, player_gold: int = 0) -> List[str]:
        """Check all title conditions and award any newly earned titles.

        Returns list of newly awarded title names (for notifications).
        """
        self.record_gold(player_gold)
        newly_earned = []

        # Kill-based titles
        for title_id, creature_kind, count in KILL_TITLES:
            title_name = _title_name_for_id(title_id)
            if title_name and title_name not in self.earned_titles:
                if self.kill_counts.get(creature_kind, 0) >= count:
                    self.earned_titles.append(title_name)
                    newly_earned.append(title_name)

        # Explorer title
        if "Explorer" not in self.earned_titles:
            if len(self.settlements_visited) >= 10:
                self.earned_titles.append("Explorer")
                newly_earned.append("Explorer")

        # Wealthy title
        if "Wealthy" not in self.earned_titles:
            if self.max_gold_held >= 500:
                self.earned_titles.append("Wealthy")
                newly_earned.append("Wealthy")

        # Arena champion
        if "Champion of the Arena" not in self.earned_titles:
            if self.arena_won:
                self.earned_titles.append("Champion of the Arena")
                newly_earned.append("Champion of the Arena")

        # Settlement friendship titles
        for settlement, count in self.quests_per_settlement.items():
            title = f"Friend of {settlement}"
            if count >= 3 and title not in self.earned_titles:
                self.earned_titles.append(title)
                newly_earned.append(title)

        # Set active title to newest if none set
        if newly_earned and not self.active_title:
            self.active_title = newly_earned[0]

        return newly_earned

    def set_active_title(self, title_name: str):
        """Set the active displayed title."""
        if title_name in self.earned_titles:
            self.active_title = title_name

    def get_all_titles(self) -> List[str]:
        """Return all earned titles."""
        return list(self.earned_titles)

    def get_title_progress(self) -> List[dict]:
        """Return progress toward all possible titles."""
        progress = []

        for title_id, creature_kind, count in KILL_TITLES:
            title_name = _title_name_for_id(title_id)
            current = self.kill_counts.get(creature_kind, 0)
            progress.append({
                "name": title_name,
                "description": f"Kill {count} {creature_kind}s",
                "current": min(current, count),
                "required": count,
                "earned": title_name in self.earned_titles,
            })

        progress.append({
            "name": "Explorer",
            "description": "Visit 10 settlements",
            "current": min(len(self.settlements_visited), 10),
            "required": 10,
            "earned": "Explorer" in self.earned_titles,
        })

        progress.append({
            "name": "Wealthy",
            "description": "Accumulate 500 gold",
            "current": min(self.max_gold_held, 500),
            "required": 500,
            "earned": "Wealthy" in self.earned_titles,
        })

        progress.append({
            "name": "Champion of the Arena",
            "description": "Win colosseum tournament",
            "current": 1 if self.arena_won else 0,
            "required": 1,
            "earned": "Champion of the Arena" in self.earned_titles,
        })

        return progress


def _title_name_for_id(title_id: str) -> Optional[str]:
    """Look up display name for a title ID."""
    for tid, name, _desc in TITLE_DEFINITIONS:
        if tid == title_id:
            return name
    return None


def initialize_title_tracker(player):
    """Attach a TitleTracker to a player object."""
    if not hasattr(player, 'title_tracker'):
        player.title_tracker = TitleTracker()


def update_titles(player, notifications=None):
    """Check title conditions and notify on new titles.

    Call this periodically (e.g., once per second) from the game loop.
    """
    if not hasattr(player, 'title_tracker'):
        initialize_title_tracker(player)

    tracker = player.title_tracker
    newly = tracker.check_and_award(player_gold=player.gold)

    if notifications and newly:
        for title in newly:
            notifications.add(f"Title earned: {title}!", 5.0, (220, 200, 100))
