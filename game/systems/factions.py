"""
Faction Reputation System: player standing with kingdoms, crimes, bounties.

Each kingdom tracks the player's reputation from -100 (hated) to +100 (revered).
Crimes accumulate bounties. Guards attack if bounty exceeds threshold.
Reputation affects NPC reactions and trade prices.
"""

import time
from typing import Dict, List, Optional, Tuple


# ================================================================
# CRIME DEFINITIONS
# ================================================================

CRIME_TYPES = {
    "theft":     {"rep_penalty": -10, "bounty_mult": 10, "description": "Theft of property"},
    "assault":   {"rep_penalty": -25, "bounty_mult": 10, "description": "Assault on a citizen"},
    "murder":    {"rep_penalty": -50, "bounty_mult": 10, "description": "Murder"},
    "trespass":  {"rep_penalty": -5,  "bounty_mult": 10, "description": "Trespassing"},
}

# Positive reputation sources
REPUTATION_GAINS = {
    "quest_easy":       5,
    "quest_medium":     10,
    "quest_hard":       15,
    "quest_epic":       20,
    "trading":          1,
    "defend_settlement": 10,
    "donate_temple":    5,
}

# NPC reaction thresholds
REACTION_THRESHOLDS = [
    (-100, -50, "hostile"),
    (-50,  -20, "wary"),
    (-20,   20, "neutral"),
    (20,    60, "friendly"),
    (60,   101, "revered"),
]

# Price modifiers by reaction
PRICE_MODIFIERS = {
    "hostile": 1.5,
    "wary":    1.2,
    "neutral": 1.0,
    "friendly": 0.9,
    "revered":  0.8,
}

GUARD_ATTACK_BOUNTY_THRESHOLD = 100


class Crime:
    """A recorded crime committed by the player."""
    def __init__(self, crime_type: str, kingdom: str, victim: str = "",
                 timestamp: float = 0.0):
        self.crime_type = crime_type
        self.kingdom = kingdom
        self.victim = victim
        self.timestamp = timestamp or time.time()
        data = CRIME_TYPES.get(crime_type, {})
        self.rep_penalty = data.get("rep_penalty", -5)
        self.bounty_value = abs(self.rep_penalty) * data.get("bounty_mult", 10)
        self.paid = False

    def __repr__(self):
        return f"Crime({self.crime_type}, {self.kingdom}, bounty={self.bounty_value})"


class FactionSystem:
    """Tracks player reputation with kingdoms, crimes, and bounties."""

    def __init__(self):
        self.reputations: Dict[str, float] = {}   # kingdom_name -> reputation (-100 to 100)
        self.crimes: List[Crime] = []              # list of Crime objects
        self.bounties: Dict[str, int] = {}         # player bounty per kingdom
        self.titles: Dict[str, str] = {}           # kingdom -> earned title
        self._decay_timer = 0.0
        self._decay_interval = 60.0  # seconds between reputation decay ticks

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self, kingdom_names: list):
        """Set all kingdoms to neutral reputation."""
        for name in kingdom_names:
            if name not in self.reputations:
                self.reputations[name] = 0.0
            if name not in self.bounties:
                self.bounties[name] = 0

    # ------------------------------------------------------------------
    # Core reputation
    # ------------------------------------------------------------------

    def change_reputation(self, kingdom: str, amount: float, cause: str = ""):
        """Adjust player reputation with a kingdom.

        Clamped to [-100, 100].
        """
        if kingdom not in self.reputations:
            self.reputations[kingdom] = 0.0
        old = self.reputations[kingdom]
        self.reputations[kingdom] = max(-100.0, min(100.0, old + amount))
        return self.reputations[kingdom]

    def get_reputation(self, kingdom: str) -> float:
        return self.reputations.get(kingdom, 0.0)

    def get_price_modifier(self, kingdom: str) -> float:
        """Prices change based on reputation: hated=1.5x, loved=0.8x"""
        reaction = self.get_npc_reaction(kingdom)
        return PRICE_MODIFIERS.get(reaction, 1.0)

    def get_npc_reaction(self, kingdom: str, reputation: Optional[float] = None) -> str:
        """How NPCs of this kingdom react: hostile, wary, neutral, friendly, revered"""
        rep = reputation if reputation is not None else self.get_reputation(kingdom)
        for low, high, label in REACTION_THRESHOLDS:
            if low <= rep < high:
                return label
        return "neutral"

    # ------------------------------------------------------------------
    # Crimes and bounties
    # ------------------------------------------------------------------

    def commit_crime(self, crime_type: str, kingdom: str, victim: str = "") -> Crime:
        """Record a crime. Types: theft, assault, murder, trespass.

        Returns the Crime object created.
        """
        crime = Crime(crime_type, kingdom, victim)
        self.crimes.append(crime)

        # Apply reputation penalty
        self.change_reputation(kingdom, crime.rep_penalty, cause=crime_type)

        # Add to bounty
        if kingdom not in self.bounties:
            self.bounties[kingdom] = 0
        self.bounties[kingdom] += crime.bounty_value

        return crime

    def get_bounty(self, kingdom: str) -> int:
        return self.bounties.get(kingdom, 0)

    def should_guards_attack(self, kingdom: str) -> bool:
        """Guards attack player if bounty exceeds threshold in their kingdom."""
        return self.get_bounty(kingdom) > GUARD_ATTACK_BOUNTY_THRESHOLD

    def pay_bounty(self, kingdom: str, player_gold: int) -> Tuple[bool, int, str]:
        """Pay off bounty to clear crimes.

        Returns (success, gold_cost, message).
        """
        bounty = self.get_bounty(kingdom)
        if bounty <= 0:
            return True, 0, "You have no bounty here."

        if player_gold < bounty:
            return False, bounty, f"You need {bounty} gold to pay your bounty (you have {player_gold})."

        # Clear bounty and mark crimes as paid
        self.bounties[kingdom] = 0
        for crime in self.crimes:
            if crime.kingdom == kingdom and not crime.paid:
                crime.paid = True

        # Partial reputation recovery from paying bounty
        self.change_reputation(kingdom, min(10, bounty // 20), cause="paid_bounty")

        return True, bounty, f"Paid {bounty} gold bounty in {kingdom}. Your record is cleared."

    def get_unpaid_crimes(self, kingdom: str) -> List[Crime]:
        return [c for c in self.crimes if c.kingdom == kingdom and not c.paid]

    # ------------------------------------------------------------------
    # Positive reputation actions
    # ------------------------------------------------------------------

    def on_quest_complete(self, kingdom: str, difficulty: str = "medium"):
        """Grant reputation for completing a quest in a kingdom."""
        key = f"quest_{difficulty}"
        amount = REPUTATION_GAINS.get(key, 10)
        self.change_reputation(kingdom, amount, cause="quest_complete")

    def on_trade(self, kingdom: str):
        """Small reputation boost for trading."""
        self.change_reputation(kingdom, REPUTATION_GAINS["trading"], cause="trade")

    def on_defend_settlement(self, kingdom: str):
        """Reputation boost for defending a settlement."""
        self.change_reputation(kingdom, REPUTATION_GAINS["defend_settlement"],
                               cause="defend_settlement")

    def on_donate_temple(self, kingdom: str):
        """Reputation boost for donating to a temple."""
        self.change_reputation(kingdom, REPUTATION_GAINS["donate_temple"],
                               cause="donate_temple")

    # ------------------------------------------------------------------
    # Titles
    # ------------------------------------------------------------------

    def check_title_earned(self, kingdom: str, settlement_name: str = "") -> Optional[str]:
        """Check if player has earned a title from reputation."""
        rep = self.get_reputation(kingdom)
        current = self.titles.get(kingdom)

        if rep >= 80 and current != f"Protector of {kingdom}":
            title = f"Protector of {kingdom}"
            self.titles[kingdom] = title
            return title
        elif rep >= 50 and settlement_name and current is None:
            title = f"Hero of {settlement_name}"
            self.titles[kingdom] = title
            return title
        return None

    # ------------------------------------------------------------------
    # Update (reputation decay toward 0 over time)
    # ------------------------------------------------------------------

    def update(self, dt: float):
        """Reputation decays toward 0 over time (forgiveness / fading fame)."""
        self._decay_timer += dt
        if self._decay_timer < self._decay_interval:
            return
        self._decay_timer = 0.0

        for kingdom in self.reputations:
            rep = self.reputations[kingdom]
            if abs(rep) < 1.0:
                self.reputations[kingdom] = 0.0
                continue
            # Decay 1 point toward zero
            if rep > 0:
                self.reputations[kingdom] = max(0.0, rep - 1.0)
            else:
                self.reputations[kingdom] = min(0.0, rep + 1.0)

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def get_reputation_report(self) -> str:
        """Summary of all faction standings."""
        lines = []
        for kingdom, rep in sorted(self.reputations.items()):
            reaction = self.get_npc_reaction(kingdom, rep)
            bounty = self.get_bounty(kingdom)
            title = self.titles.get(kingdom, "")
            price = self.get_price_modifier(kingdom)
            line = (f"  {kingdom}: {rep:+.0f} ({reaction}), "
                    f"bounty={bounty}g, prices={price:.0%}")
            if title:
                line += f", title=\"{title}\""
            lines.append(line)
        if not lines:
            return "No faction standings yet."
        return "Faction Standings:\n" + "\n".join(lines)

    def get_kingdom_for_position(self, x: float, y: float, governance) -> Optional[str]:
        """Helper: find which kingdom the player is in using governance system."""
        if governance is None:
            return None
        return governance.get_kingdom_at(x, y)
