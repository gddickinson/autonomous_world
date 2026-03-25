"""Colosseum Tournament — 8-fighter single elimination with betting + dialog.

Uses colosseum_betting for match simulation, odds, bets, and rankings.

Features:
- 8-fighter single elimination tournament brackets (QF -> SF -> Final)
- Player enters as fighter or spectator
- Betting before each round with NPC audience reactions
- Champion gets 500g prize and "Tournament Champion" title
- Dialog integration with colosseum NPCs
"""

import random
from typing import Optional, List, Dict, Tuple, Any

from game.core.creature import Creature
from game.systems.colosseum_betting import (
    TournamentMatch, ChampionRankings, get_rankings,
    Bet, calculate_odds,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOURNAMENT_SIZE = 8
ROUND_NAMES = ["Quarter-Final", "Semi-Final", "Final"]
CHAMPION_PRIZE = 500

_rankings = get_rankings()


# ---------------------------------------------------------------------------
# Tournament
# ---------------------------------------------------------------------------

class Tournament:
    """8-fighter single elimination tournament with betting.

    Rounds:
      0: Quarter-finals (4 matches)
      1: Semi-finals (2 matches)
      2: Final (1 match)
    """

    def __init__(self, fighters: List[Any], player=None):
        if len(fighters) != TOURNAMENT_SIZE:
            raise ValueError(f"Need {TOURNAMENT_SIZE} fighters, got {len(fighters)}")
        self.fighters = list(fighters)
        self.player = player
        self.player_participating = player in fighters if player else False
        self.current_round = 0
        self.matches: List[List[TournamentMatch]] = []
        self.champion = None
        self.active = True
        self.messages: List[str] = []
        self.npc_bets_placed = False
        self._build_round(fighters)

    def _build_round(self, fighters: List[Any]):
        matches = []
        for i in range(0, len(fighters), 2):
            if i + 1 < len(fighters):
                m = TournamentMatch(fighters[i], fighters[i + 1],
                                    self.current_round, i // 2)
                matches.append(m)
        self.matches.append(matches)

    @property
    def round_name(self) -> str:
        if 0 <= self.current_round < len(ROUND_NAMES):
            return ROUND_NAMES[self.current_round]
        return f"Round {self.current_round + 1}"

    @property
    def current_matches(self) -> List[TournamentMatch]:
        return self.matches[-1] if self.matches else []

    def get_betting_info(self) -> List[Dict[str, Any]]:
        """Return betting info for current-round unfinished matches."""
        return [
            {
                "match_index": m.match_index,
                "fighter_a": m.fighter_a_name,
                "fighter_b": m.fighter_b_name,
                "odds_a": m.odds_a,
                "odds_b": m.odds_b,
            }
            for m in self.current_matches if not m.finished
        ]

    def player_bet(self, match_index: int, fighter_index: int,
                   amount: int) -> str:
        """Player places a bet (10-100g). Returns result message."""
        if not self.player:
            return "No player in tournament."
        if amount < 10 or amount > 100:
            return "Bet must be 10-100 gold."
        if self.player.gold < amount:
            return "Not enough gold!"
        for m in self.current_matches:
            if m.match_index == match_index and not m.started:
                bet = m.place_bet("Player", amount, fighter_index)
                if bet:
                    self.player.gold -= amount
                    target = m.fighter_a_name if fighter_index == 0 else m.fighter_b_name
                    return f"Bet {amount}g on {target} at {bet.odds}x odds."
                return "Cannot place bet on this match."
        return "Match not found or already started."

    def generate_npc_bets(self, audience_npcs: List[Any]):
        """NPCs in the audience place random bets on current matches."""
        if self.npc_bets_placed:
            return
        self.npc_bets_placed = True
        for m in self.current_matches:
            if m.finished:
                continue
            num = min(len(audience_npcs), random.randint(3, 6))
            bettors = random.sample(audience_npcs, min(num, len(audience_npcs)))
            for npc in bettors:
                name = getattr(npc, 'name', 'Spectator')
                amount = random.choice([10, 20, 25, 30, 50])
                m.place_bet(name, amount, random.randint(0, 1))

    def run_current_round(self) -> List[str]:
        """Simulate all matches in the current round. Returns messages."""
        messages = [f"=== {self.round_name} ==="]
        for m in self.current_matches:
            if m.finished:
                continue
            messages.append(m.simulate_fight())
            messages.extend(m.resolve_bets())
            # Update rankings
            winner_name = getattr(m.winner, 'name', 'Unknown')
            loser = m.fighter_b if m.winner is m.fighter_a else m.fighter_a
            _rankings.record_win(winner_name)
            _rankings.record_loss(getattr(loser, 'name', 'Unknown'))

        # Check player elimination
        if self.player_participating and self.player:
            player_won = any(m.winner is self.player for m in self.current_matches)
            if not player_won:
                player_fought = any(
                    m.fighter_a is self.player or m.fighter_b is self.player
                    for m in self.current_matches)
                if player_fought:
                    messages.append("You have been eliminated!")
                    self.player_participating = False

        # Advance
        winners = [m.winner for m in self.current_matches if m.winner]
        self.current_round += 1
        self.npc_bets_placed = False

        if len(winners) == 1:
            self.champion = winners[0]
            self.active = False
            champ_name = getattr(self.champion, 'name', 'Unknown')
            messages.append(f"\n*** {champ_name} is the CHAMPION! ***")
            messages.append(f"Prize: {CHAMPION_PRIZE} gold!")
            if hasattr(self.champion, 'gold'):
                self.champion.gold += CHAMPION_PRIZE
            if hasattr(self.champion, 'title'):
                self.champion.title = "Tournament Champion"
            _rankings.record_title(champ_name, CHAMPION_PRIZE)
        elif winners:
            self._build_round(winners)
            messages.append(f"\nNext: {self.round_name} -- {len(winners)} fighters remain")

        self.messages.extend(messages)
        return messages

    def get_bracket_display(self) -> List[str]:
        """Return a text-based bracket display."""
        lines = ["=== TOURNAMENT BRACKET ===", ""]
        for r_idx, round_matches in enumerate(self.matches):
            r_name = ROUND_NAMES[r_idx] if r_idx < len(ROUND_NAMES) else f"Round {r_idx + 1}"
            lines.append(f"--- {r_name} ---")
            for m in round_matches:
                a, b = m.fighter_a_name, m.fighter_b_name
                if m.finished and m.winner:
                    w = getattr(m.winner, 'name', '?')
                    lines.append(f"  {a}{' [W]' if w == a else ''}  vs  "
                                 f"{b}{' [W]' if w == b else ''}")
                else:
                    lines.append(f"  {a}  vs  {b}  (pending)")
            lines.append("")
        if self.champion:
            lines.append(f"CHAMPION: {getattr(self.champion, 'name', 'Unknown')}")
        return lines


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------

_active_tournaments: Dict[int, Tournament] = {}
_tournament_counter = 0


def start_tournament(fighters: List[Any], player=None) -> Tuple[int, Tournament]:
    global _tournament_counter
    _tournament_counter += 1
    t = Tournament(fighters, player)
    _active_tournaments[_tournament_counter] = t
    return _tournament_counter, t


def get_tournament(tid: int) -> Optional[Tournament]:
    return _active_tournaments.get(tid)


def list_active_tournaments() -> List[Tuple[int, Tournament]]:
    return [(k, v) for k, v in _active_tournaments.items() if v.active]


def cleanup_finished():
    finished = [(k, v) for k, v in _active_tournaments.items() if not v.active]
    if len(finished) > 5:
        for k, _ in finished[:-5]:
            del _active_tournaments[k]


# ---------------------------------------------------------------------------
# Dialog Integration
# ---------------------------------------------------------------------------

def get_tournament_dialog_options(npc, player) -> list:
    """Return tournament dialog options for colosseum NPCs."""
    from game.systems.colosseum_player import is_colosseum_npc
    if not is_colosseum_npc(npc):
        return []
    options = []
    active = list_active_tournaments()
    if active:
        options.append(("Show me the tournament bracket.", "tournament_bracket"))
        options.append(("I want to place a bet.", "tournament_bet"))
        options.append(("Show champion rankings.", "tournament_rankings"))
    else:
        options.append(("Start a tournament!", "tournament_start"))
        options.append(("Show champion rankings.", "tournament_rankings"))
    return options


def handle_tournament_dialog(npc, player, choice: str,
                             nearby_npcs: Optional[List] = None) -> str:
    """Handle tournament dialog choices. Returns response text."""
    if choice == "tournament_start":
        fighters = [player]
        candidates = nearby_npcs or []
        valid = [n for n in candidates
                 if hasattr(n, 'hp') and n is not player and n is not npc
                 and getattr(n, 'alive', True)]
        while len(valid) < 7:
            kind = random.choice(["bandit", "skeleton", "wolf", "goblin"])
            c = Creature(npc.x + random.uniform(-5, 5),
                         npc.y + random.uniform(-5, 5), kind)
            c.name = f"{kind.title()} #{len(valid) + 1}"
            valid.append(c)
        chosen = random.sample(valid, min(7, len(valid)))[:7]
        fighters.extend(chosen)
        tid, t = start_tournament(fighters, player)
        bracket = "\n".join(t.get_bracket_display())
        return (f"Tournament #{tid} started! 8 fighters enter, 1 leaves!\n"
                f"{bracket}\n\nPlace your bets before each round!")

    elif choice == "tournament_bracket":
        active = list_active_tournaments()
        if not active:
            return "No active tournaments."
        return "\n".join(active[-1][1].get_bracket_display())

    elif choice == "tournament_bet":
        active = list_active_tournaments()
        if not active:
            return "No active tournaments."
        info = active[-1][1].get_betting_info()
        if not info:
            return "No matches available for betting right now."
        lines = ["Current matches -- place your bet:"]
        for b in info:
            lines.append(f"  Match {b['match_index']}: {b['fighter_a']} "
                         f"({b['odds_a']}x) vs {b['fighter_b']} ({b['odds_b']}x)")
        lines.append("Tell me: 'Bet [amount] on [fighter name]'")
        return "\n".join(lines)

    elif choice == "tournament_rankings":
        return "\n".join(_rankings.format_leaderboard())

    return "I don't understand."
