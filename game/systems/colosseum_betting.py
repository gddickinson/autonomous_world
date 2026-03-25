"""Colosseum Betting — odds calculation, bets, fight simulation, rankings.

Extracted from colosseum_tournament to keep files under 500 lines.
"""

import random
from typing import Optional, List, Dict, Tuple


# ---------------------------------------------------------------------------
# Fighter Stats (for odds calculation)
# ---------------------------------------------------------------------------

def _fighter_power(fighter) -> float:
    """Estimate a fighter's combat power for odds calculation."""
    hp = getattr(fighter, 'hp', 20)
    max_hp = getattr(fighter, 'max_hp', hp)
    damage = getattr(fighter, 'damage', 5)
    ac = getattr(fighter, 'armor_class', 10)
    level = getattr(fighter, 'level', 1)
    return (max_hp * 0.4 + damage * 3.0 + ac * 2.0 + level * 5.0)


def calculate_odds(fighter_a, fighter_b) -> Tuple[float, float]:
    """Return (odds_a, odds_b) as payout multipliers (e.g. 2.0 = 2x).

    Underdog gets higher payout. Minimum 1.5x, maximum 5.0x.
    """
    pa = max(1.0, _fighter_power(fighter_a))
    pb = max(1.0, _fighter_power(fighter_b))
    total = pa + pb
    prob_a = pa / total
    prob_b = pb / total
    odds_a = max(1.5, min(5.0, 1.0 / max(0.1, prob_a)))
    odds_b = max(1.5, min(5.0, 1.0 / max(0.1, prob_b)))
    return (round(odds_a, 1), round(odds_b, 1))


# ---------------------------------------------------------------------------
# Bet
# ---------------------------------------------------------------------------

class Bet:
    """A single bet placed on a fighter."""
    __slots__ = ('bettor_name', 'amount', 'fighter_index', 'odds', 'resolved')

    def __init__(self, bettor_name: str, amount: int,
                 fighter_index: int, odds: float):
        self.bettor_name = bettor_name
        self.amount = amount
        self.fighter_index = fighter_index
        self.odds = odds
        self.resolved = False

    def payout(self) -> int:
        return int(self.amount * self.odds)


# ---------------------------------------------------------------------------
# NPC Audience Reactions
# ---------------------------------------------------------------------------

NPC_BET_REACTIONS_WIN = [
    "{name} cheers: 'I knew it!'",
    "{name} pumps fist: 'Easy money!'",
    "{name} grins and collects winnings.",
    "{name} shouts: 'That's my fighter!'",
]

NPC_BET_REACTIONS_LOSE = [
    "{name} groans and tosses coin purse.",
    "{name} mutters: 'Rigged...'",
    "{name} shakes head in disbelief.",
    "{name} sighs: 'There goes my savings.'",
]


# ---------------------------------------------------------------------------
# Tournament Match
# ---------------------------------------------------------------------------

class TournamentMatch:
    """A single match in the tournament bracket."""
    __slots__ = ('fighter_a', 'fighter_b', 'winner', 'round_num',
                 'match_index', 'bets', 'odds_a', 'odds_b',
                 'fight_log', 'started', 'finished')

    def __init__(self, fighter_a, fighter_b, round_num: int, match_index: int):
        self.fighter_a = fighter_a
        self.fighter_b = fighter_b
        self.winner = None
        self.round_num = round_num
        self.match_index = match_index
        self.bets: List[Bet] = []
        self.odds_a, self.odds_b = calculate_odds(fighter_a, fighter_b)
        self.fight_log: List[str] = []
        self.started = False
        self.finished = False

    @property
    def fighter_a_name(self) -> str:
        return getattr(self.fighter_a, 'name', 'Fighter A')

    @property
    def fighter_b_name(self) -> str:
        return getattr(self.fighter_b, 'name', 'Fighter B')

    def place_bet(self, bettor_name: str, amount: int,
                  fighter_index: int) -> Optional[Bet]:
        """Place a bet on fighter 0 (A) or 1 (B). Returns Bet or None."""
        if self.finished or self.started:
            return None
        if fighter_index not in (0, 1):
            return None
        if amount < 10 or amount > 100:
            return None
        odds = self.odds_a if fighter_index == 0 else self.odds_b
        bet = Bet(bettor_name, amount, fighter_index, odds)
        self.bets.append(bet)
        return bet

    def simulate_fight(self) -> str:
        """Simulate the fight and determine a winner. Returns summary."""
        self.started = True
        fa, fb = self.fighter_a, self.fighter_b
        hp_a = getattr(fa, 'max_hp', 20)
        hp_b = getattr(fb, 'max_hp', 20)
        dmg_a = max(1, getattr(fa, 'damage', 5))
        dmg_b = max(1, getattr(fb, 'damage', 5))
        ac_a = getattr(fa, 'armor_class', 10)
        ac_b = getattr(fb, 'armor_class', 10)
        name_a, name_b = self.fighter_a_name, self.fighter_b_name

        turn = 0
        while hp_a > 0 and hp_b > 0 and turn < 20:
            turn += 1
            # A attacks B
            roll_a = random.randint(1, 20)
            if roll_a >= ac_b - 2:
                hit = dmg_a + random.randint(0, dmg_a // 2)
                if roll_a == 20:
                    hit *= 2
                    self.fight_log.append(f"Turn {turn}: {name_a} CRITS {name_b} for {hit}!")
                else:
                    self.fight_log.append(f"Turn {turn}: {name_a} hits {name_b} for {hit}")
                hp_b -= hit
            else:
                self.fight_log.append(f"Turn {turn}: {name_a} misses {name_b}")
            if hp_b <= 0:
                break
            # B attacks A
            roll_b = random.randint(1, 20)
            if roll_b >= ac_a - 2:
                hit = dmg_b + random.randint(0, dmg_b // 2)
                if roll_b == 20:
                    hit *= 2
                    self.fight_log.append(f"Turn {turn}: {name_b} CRITS {name_a} for {hit}!")
                else:
                    self.fight_log.append(f"Turn {turn}: {name_b} hits {name_a} for {hit}")
                hp_a -= hit
            else:
                self.fight_log.append(f"Turn {turn}: {name_b} misses {name_a}")

        if hp_a > hp_b:
            self.winner = fa
        elif hp_b > hp_a:
            self.winner = fb
        else:
            self.winner = random.choice([fa, fb])

        self.finished = True
        winner_name = getattr(self.winner, 'name', 'Unknown')
        summary = f"{winner_name} wins! ({turn} turns)"
        self.fight_log.append(summary)
        return summary

    def resolve_bets(self) -> List[str]:
        """Resolve all bets after fight. Returns reaction messages."""
        if not self.finished or self.winner is None:
            return []
        winner_idx = 0 if self.winner is self.fighter_a else 1
        messages = []
        for bet in self.bets:
            if bet.resolved:
                continue
            bet.resolved = True
            if bet.fighter_index == winner_idx:
                winnings = bet.payout()
                msg = random.choice(NPC_BET_REACTIONS_WIN).format(name=bet.bettor_name)
                messages.append(f"{msg} (+{winnings}g)")
            else:
                msg = random.choice(NPC_BET_REACTIONS_LOSE).format(name=bet.bettor_name)
                messages.append(f"{msg} (-{bet.amount}g)")
        return messages


# ---------------------------------------------------------------------------
# Champion Rankings
# ---------------------------------------------------------------------------

class ChampionRankings:
    """Tracks win/loss records and leaderboard for tournament fighters."""

    def __init__(self):
        self._records: Dict[str, Dict[str, int]] = {}

    def record_win(self, name: str):
        rec = self._records.setdefault(
            name, {"wins": 0, "losses": 0, "titles": 0, "gold_earned": 0})
        rec["wins"] += 1

    def record_loss(self, name: str):
        rec = self._records.setdefault(
            name, {"wins": 0, "losses": 0, "titles": 0, "gold_earned": 0})
        rec["losses"] += 1

    def record_title(self, name: str, gold: int = 0):
        rec = self._records.setdefault(
            name, {"wins": 0, "losses": 0, "titles": 0, "gold_earned": 0})
        rec["titles"] += 1
        rec["gold_earned"] += gold

    def get_record(self, name: str) -> Dict[str, int]:
        return self._records.get(
            name, {"wins": 0, "losses": 0, "titles": 0, "gold_earned": 0})

    def leaderboard(self, top_n: int = 10) -> List[Tuple[str, Dict[str, int]]]:
        """Return top N fighters sorted by wins (then titles as tiebreaker)."""
        entries = list(self._records.items())
        entries.sort(key=lambda e: (e[1]["wins"], e[1]["titles"]), reverse=True)
        return entries[:top_n]

    def format_leaderboard(self, top_n: int = 10) -> List[str]:
        """Return formatted leaderboard lines."""
        lb = self.leaderboard(top_n)
        lines = ["=== CHAMPION RANKINGS ==="]
        for i, (name, rec) in enumerate(lb, 1):
            w, l = rec["wins"], rec["losses"]
            titles = rec["titles"]
            title_str = f" [{titles}x Champion]" if titles else ""
            lines.append(f"  {i}. {name} -- {w}W/{l}L{title_str}")
        if not lb:
            lines.append("  No records yet.")
        return lines


# Global rankings instance
_rankings = ChampionRankings()


def get_rankings() -> ChampionRankings:
    return _rankings
