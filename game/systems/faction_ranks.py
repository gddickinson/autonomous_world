"""Faction Ranks — kingdom rank progression with rank-up quests and benefits.

Integrates with factions.FactionSystem, quests.Quest, and housing.PlayerHouse.
"""

import random
from typing import Dict, List, Optional, Tuple

from game.systems.quests import Quest


# ================================================================
# RANK DEFINITIONS
# ================================================================

RANKS = [
    "Outsider",   # 0 — default for all kingdoms
    "Citizen",    # 1
    "Trusted",    # 2
    "Honored",    # 3
    "Noble",      # 4
    "Commander",  # 5
    "Champion",   # 6
]

RANK_INDEX = {name: i for i, name in enumerate(RANKS)}

# Reputation thresholds required to *unlock* the rank-up quest.
# The quest must then be completed to actually advance.
RANK_REP_THRESHOLDS = {
    1: 10,   # Outsider -> Citizen
    2: 25,   # Citizen  -> Trusted
    3: 40,   # Trusted  -> Honored
    4: 55,   # Honored  -> Noble
    5: 70,   # Noble    -> Commander
    6: 85,   # Commander -> Champion
}

# ================================================================
# RANK BENEFITS
# ================================================================

RANK_BENEFITS = {
    "Citizen": {
        "shop_discount": 0.10,       # 10 % off faction shops
        "description": "Access to faction shops with 10% discount.",
    },
    "Trusted": {
        "free_rest": True,           # rest at any settlement for free
        "description": "Rest in any settlement of this kingdom for free.",
    },
    "Honored": {
        "guard_assist": True,        # guards help in nearby combat
        "description": "Kingdom guards assist you in combat nearby.",
    },
    "Noble": {
        "daily_stipend": 5,          # gold per in-game day
        "description": "Receive 5 gold per day as a royal stipend.",
    },
    "Commander": {
        "max_followers": 3,          # recruit up to 3 NPC followers
        "description": "Recruit up to 3 NPC followers from this kingdom.",
    },
    "Champion": {
        "land_grant": True,          # plot of land for housing
        "description": "Granted a plot of land for your own house.",
    },
}


# ================================================================
# RANK-UP QUEST GENERATORS
# ================================================================

def _pick(lst, fallback="the capital"):
    return random.choice(lst) if lst else fallback


def _make_rankup(kingdom, kind, target, count, gold, xp, rep, diff,
                 stages, settlement="", **kw):
    """Shorthand to build a rank-up Quest."""
    return Quest(
        title=kw.get("title", ""), description=kw.get("desc", ""),
        kind=kind, target=target, target_count=count,
        reward_gold=gold, reward_xp=xp, reward_reputation=rep,
        difficulty=diff, stages=stages, kingdom=kingdom,
        settlement=settlement, consequence="rank_up",
    )


def _gen_rank1(k, _kd, s, _ak):
    """Outsider->Citizen: complete 2 settlement tasks."""
    st = _pick(s)
    return _make_rankup(k, "fetch", "kingdom_task", 2, 20, 30, 5, "easy", 1,
                        settlement=st, title=f"Prove Your Worth to {k}",
                        desc=f"Complete 2 tasks for {st} to earn citizenship in {k}.")


def _gen_rank2(k, _kd, s, ak):
    """Citizen->Trusted: deliver message to allied kingdom."""
    ally = _pick(ak, "a distant ally")
    st = _pick(s)
    return _make_rankup(k, "deliver", "Sealed Documents", 1, 40, 50, 10, "medium", 2,
                        settlement=st, title=f"Diplomatic Courier for {k}",
                        desc=f"Deliver sealed documents from {k} to {ally}.")


def _gen_rank3(k, _kd, s, _ak):
    """Trusted->Honored: defeat a threat (bounty quest)."""
    threat = random.choice(["bandit leader", "rogue mage", "marauding beast", "undead knight"])
    st = _pick(s, "the outskirts")
    return _make_rankup(k, "bounty_hunt", threat, 1, 60, 70, 15, "hard", 1,
                        settlement=st,
                        title=f"Eliminate the {threat.title()} Threatening {k}",
                        desc=f"A {threat} terrorizes roads near {st}. Defeat them for {k}.")


def _gen_rank4(k, _kd, _s, _ak):
    """Honored->Noble: donate 200 gold to treasury. Reward: Ring of Shadows."""
    q = _make_rankup(k, "fetch", "gold_donation", 200, 0, 80, 15, "hard", 1,
                     title=f"Patronage of {k}",
                     desc=f"Donate 200 gold to the royal treasury of {k}.")
    q.reward_item = "Ring of Shadows"
    return q


def _gen_rank5(k, _kd, s, _ak):
    """Noble->Commander: lead troops in battle. Reward: Boots of Swiftness."""
    st = _pick(s, "the frontier")
    q = _make_rankup(k, "defend", "enemy_soldiers", 5, 100, 120, 20, "epic", 2,
                     settlement=st, title=f"Lead the Vanguard of {k}",
                     desc=f"Rally troops at {st} and lead them against the enemy.")
    q.reward_item = "Boots of Swiftness"
    return q


_CHAMPION_CHALLENGES = {
    "Human":    ("Win the Grand Tournament", "tournament_win",
                 "Compete in the kingdom's grand tournament and emerge victorious."),
    "Elf":      ("Complete the Moonlight Trial", "moonlight_trial",
                 "Survive the ancient elven trial under the full moon."),
    "Dwarf":    ("Forge the Masterwork", "masterwork_forge",
                 "Craft a masterwork weapon in the Great Forge."),
    "Half-Orc": ("Defeat the Warchief's Champion", "duel_champion",
                 "Best the current champion in single combat."),
    "Goblin":   ("Steal the Dragon's Tooth", "dragon_heist",
                 "Infiltrate the dragon's hoard and steal a fang."),
    "Undead":   ("Bind a Greater Spirit", "spirit_binding",
                 "Perform the ritual to bind a powerful spirit to your will."),
}


_CHAMPION_REWARDS = {
    "Human": "Crown of the Vanquished Lich",
    "Elf": "Staff of the Archmage",
    "Dwarf": "Shield of the Faithful",
    "Half-Orc": "Blade of the Dawn",
    "Goblin": "Ring of Shadows",
    "Undead": "Cloak of Many Stars",
}


def _gen_rank6(k, kd, _s, _ak):
    """Commander->Champion: unique kingdom-specific challenge. Reward: unique artifact."""
    race = kd.get("race", "Human")
    title, target, desc = _CHAMPION_CHALLENGES.get(race, _CHAMPION_CHALLENGES["Human"])
    q = _make_rankup(k, "investigate", target, 1, 200, 200, 25, "epic", 3,
                     title=f"{title} -- {k}",
                     desc=f"{desc} Final challenge to become Champion of {k}.")
    q.reward_item = _CHAMPION_REWARDS.get(race, "Crown of the Vanquished Lich")
    return q


_RANK_QUEST_GENERATORS = {
    1: _gen_rank1, 2: _gen_rank2, 3: _gen_rank3,
    4: _gen_rank4, 5: _gen_rank5, 6: _gen_rank6,
}


# ================================================================
# KINGDOM RANK TRACKER
# ================================================================

class KingdomRankTracker:
    """Per-kingdom rank state for the player."""

    __slots__ = ("kingdom", "rank_index", "rank_name",
                 "active_rankup_quest", "stipend_accumulator")

    def __init__(self, kingdom: str):
        self.kingdom: str = kingdom
        self.rank_index: int = 0
        self.rank_name: str = RANKS[0]
        self.active_rankup_quest: Optional[Quest] = None
        self.stipend_accumulator: float = 0.0  # tracks partial days

    # -- helpers --------------------------------------------------

    def can_attempt_promotion(self, reputation: float) -> bool:
        """True if rep meets threshold and no rank-up quest is active."""
        next_rank = self.rank_index + 1
        if next_rank >= len(RANKS):
            return False
        if self.active_rankup_quest is not None:
            return False
        threshold = RANK_REP_THRESHOLDS.get(next_rank, 999)
        return reputation >= threshold

    def promote(self) -> str:
        """Advance to the next rank. Returns the new rank name."""
        self.rank_index = min(self.rank_index + 1, len(RANKS) - 1)
        self.rank_name = RANKS[self.rank_index]
        self.active_rankup_quest = None
        return self.rank_name

    def get_benefits(self) -> Dict:
        """Accumulated benefits from all ranks up to current."""
        benefits: Dict = {}
        for i in range(1, self.rank_index + 1):
            rank_name = RANKS[i]
            rank_benefits = RANK_BENEFITS.get(rank_name, {})
            benefits.update(rank_benefits)
        return benefits

    def has_benefit(self, key: str) -> bool:
        return key in self.get_benefits()

    def get_shop_discount(self) -> float:
        """Total shop discount from rank benefits (0.0 – 1.0)."""
        return self.get_benefits().get("shop_discount", 0.0)

    def get_max_followers(self) -> int:
        return self.get_benefits().get("max_followers", 0)

    def get_daily_stipend(self) -> int:
        return self.get_benefits().get("daily_stipend", 0)


# ================================================================
# FACTION RANK SYSTEM (main manager)
# ================================================================

class FactionRankSystem:
    """Manages player ranks across all kingdoms.

    Sits alongside FactionSystem (reputation/crimes) and QuestSystem.
    Call ``update()`` each frame to process stipends and check promotions.
    """

    def __init__(self):
        self.trackers: Dict[str, KingdomRankTracker] = {}
        self._kingdoms_data: Dict[str, Dict] = {}  # kingdom_name -> dict
        self._allied_map: Dict[str, List[str]] = {}  # kingdom -> list of allies
        self._stipend_day_tracker: float = 0.0  # accumulates dt
        self._day_length: float = 600.0  # seconds per in-game day (default)

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self, kingdoms: List[Dict], day_length: float = 600.0):
        """Set up trackers for every kingdom in the world plan.

        ``kingdoms`` should be ``world_plan.kingdoms`` — a list of dicts
        with at least ``name``, ``race``, ``territory_settlements``.
        """
        self._day_length = day_length
        for kdata in kingdoms:
            name = kdata["name"]
            self._kingdoms_data[name] = kdata
            if name not in self.trackers:
                self.trackers[name] = KingdomRankTracker(name)

        # Build a naive allied map: same-governance kingdoms are allies
        gov_groups: Dict[str, List[str]] = {}
        for kdata in kingdoms:
            gov = kdata.get("governance_style", "")
            gov_groups.setdefault(gov, []).append(kdata["name"])
        for gov, members in gov_groups.items():
            for m in members:
                self._allied_map[m] = [a for a in members if a != m]

    # ------------------------------------------------------------------
    # Rank queries
    # ------------------------------------------------------------------

    def get_rank(self, kingdom: str) -> str:
        tracker = self.trackers.get(kingdom)
        return tracker.rank_name if tracker else "Outsider"

    def get_rank_index(self, kingdom: str) -> int:
        tracker = self.trackers.get(kingdom)
        return tracker.rank_index if tracker else 0

    def get_tracker(self, kingdom: str) -> Optional[KingdomRankTracker]:
        return self.trackers.get(kingdom)

    def get_all_ranks(self) -> Dict[str, str]:
        return {k: t.rank_name for k, t in self.trackers.items()}

    def get_benefits_for(self, kingdom: str) -> Dict:
        tracker = self.trackers.get(kingdom)
        return tracker.get_benefits() if tracker else {}

    def has_benefit(self, kingdom: str, key: str) -> bool:
        tracker = self.trackers.get(kingdom)
        return tracker.has_benefit(key) if tracker else False

    def best_shop_discount(self) -> float:
        """Highest shop discount across all kingdoms."""
        return max((t.get_shop_discount() for t in self.trackers.values()),
                   default=0.0)

    def total_max_followers(self) -> int:
        """Max NPC followers from any single kingdom rank."""
        return max((t.get_max_followers() for t in self.trackers.values()),
                   default=0)

    # ------------------------------------------------------------------
    # Rank-up quest generation
    # ------------------------------------------------------------------

    def check_promotions(self, faction_system) -> List[Tuple[str, Quest]]:
        """Check all kingdoms for promotion eligibility.

        Returns list of (kingdom_name, quest) for newly generated rank-up
        quests that should be offered to the player.
        """
        new_quests: List[Tuple[str, Quest]] = []
        for kingdom, tracker in self.trackers.items():
            rep = faction_system.get_reputation(kingdom)
            if not tracker.can_attempt_promotion(rep):
                continue

            next_rank = tracker.rank_index + 1
            gen = _RANK_QUEST_GENERATORS.get(next_rank)
            if gen is None:
                continue

            kdata = self._kingdoms_data.get(kingdom, {})
            settlements = kdata.get("territory_settlements", [])
            allies = self._allied_map.get(kingdom, [])
            quest = gen(kingdom, kdata, settlements, allies)
            quest.chain_id = f"rankup_{kingdom}_{next_rank}"
            tracker.active_rankup_quest = quest
            new_quests.append((kingdom, quest))

        return new_quests

    def on_rankup_quest_complete(self, quest: Quest) -> Optional[str]:
        """Call when a rank-up quest is completed. Promotes the player.

        Returns the new rank name, or None if quest isn't a rank-up quest.
        """
        kingdom = quest.kingdom
        tracker = self.trackers.get(kingdom)
        if tracker is None:
            return None
        if tracker.active_rankup_quest is None:
            return None
        if tracker.active_rankup_quest.chain_id != quest.chain_id:
            return None

        new_rank = tracker.promote()
        return new_rank

    # ------------------------------------------------------------------
    # Stipend processing
    # ------------------------------------------------------------------

    def update(self, dt: float, player) -> List[str]:
        """Per-frame update. Processes daily stipends.

        Returns list of notification messages.
        """
        messages: List[str] = []
        self._stipend_day_tracker += dt
        if self._stipend_day_tracker < self._day_length:
            return messages

        # A full day has passed
        self._stipend_day_tracker -= self._day_length
        total_stipend = 0
        for tracker in self.trackers.values():
            stipend = tracker.get_daily_stipend()
            if stipend > 0:
                total_stipend += stipend

        if total_stipend > 0 and player is not None:
            player.gold += total_stipend
            messages.append(
                f"You received {total_stipend} gold from your noble stipends."
            )

        return messages

    # ------------------------------------------------------------------
    # Reputation change hook
    # ------------------------------------------------------------------

    def on_reputation_change(self, kingdom: str, new_rep: float,
                             faction_system) -> List[Tuple[str, Quest]]:
        """Called after reputation changes. Checks if a new rank-up quest
        should be offered.

        Returns list of (kingdom, quest) if a new quest was generated.
        """
        tracker = self.trackers.get(kingdom)
        if tracker is None:
            return []
        if not tracker.can_attempt_promotion(new_rep):
            return []
        return self.check_promotions(faction_system)

    # ------------------------------------------------------------------
    # Combat: guard assistance check
    # ------------------------------------------------------------------

    def should_guards_assist(self, kingdom: str) -> bool:
        """True if player rank in this kingdom grants guard assistance."""
        return self.has_benefit(kingdom, "guard_assist")

    def can_rest_free(self, kingdom: str) -> bool:
        """True if player can rest free in this kingdom."""
        return self.has_benefit(kingdom, "free_rest")

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict:
        data: Dict = {"trackers": {}}
        for kingdom, tracker in self.trackers.items():
            data["trackers"][kingdom] = {
                "rank_index": tracker.rank_index,
                "rank_name": tracker.rank_name,
                "stipend_accumulator": tracker.stipend_accumulator,
            }
        data["stipend_day_tracker"] = self._stipend_day_tracker
        return data

    def from_dict(self, data: Dict):
        self._stipend_day_tracker = data.get("stipend_day_tracker", 0.0)
        for kingdom, tdata in data.get("trackers", {}).items():
            tracker = self.trackers.get(kingdom)
            if tracker is None:
                tracker = KingdomRankTracker(kingdom)
                self.trackers[kingdom] = tracker
            tracker.rank_index = tdata.get("rank_index", 0)
            tracker.rank_name = tdata.get("rank_name", RANKS[0])
            tracker.stipend_accumulator = tdata.get("stipend_accumulator", 0.0)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def get_ranks_report(self) -> str:
        lines = ["Kingdom Ranks:"]
        for kingdom, tracker in sorted(self.trackers.items()):
            benefits = tracker.get_benefits()
            benefit_keys = [k for k in benefits if k != "description"]
            bstr = ", ".join(benefit_keys) if benefit_keys else "none"
            line = (f"  {kingdom}: {tracker.rank_name} "
                    f"(rank {tracker.rank_index}/{len(RANKS)-1}) "
                    f"[benefits: {bstr}]")
            if tracker.active_rankup_quest:
                line += f" — quest active: {tracker.active_rankup_quest.title}"
            lines.append(line)
        return "\n".join(lines)
