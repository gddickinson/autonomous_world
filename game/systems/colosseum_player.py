"""Colosseum Player Entry — allows the player to fight as a combatant.

The player enters the arena and faces progressively harder rounds:
  Round 1: 1 rat
  Round 2: 2 wolves
  Round 3: 1 bandit
  Round 4: 2 skeletons
  Round 5: 1 boss (minotaur)

Rewards per round: gold, XP, and a champion title on completion.
Triggered via dialog with a colosseum NPC ("I want to fight").
"""

import random
from typing import Optional, List, Dict, Any

from game.core.creature import Creature


# ---------------------------------------------------------------------------
# Arena Round Definitions
# ---------------------------------------------------------------------------

ARENA_ROUNDS = [
    {
        "name": "Round 1: The Rat Pit",
        "enemies": [("rat", 1)],
        "gold_reward": 10,
        "xp_reward": 15,
    },
    {
        "name": "Round 2: Wolf Pack",
        "enemies": [("wolf", 2)],
        "gold_reward": 25,
        "xp_reward": 30,
    },
    {
        "name": "Round 3: Bandit Challenge",
        "enemies": [("bandit", 1)],
        "gold_reward": 50,
        "xp_reward": 50,
    },
    {
        "name": "Round 4: Skeleton Warriors",
        "enemies": [("skeleton", 2)],
        "gold_reward": 75,
        "xp_reward": 75,
    },
    {
        "name": "Round 5: The Minotaur",
        "enemies": [("minotaur", 1)],
        "gold_reward": 200,
        "xp_reward": 150,
    },
]

CHAMPION_TITLE = "Arena Champion"
TOTAL_GOLD = sum(r["gold_reward"] for r in ARENA_ROUNDS)


class PlayerArenaSession:
    """Tracks a player's progress through colosseum combat rounds.

    Manages enemy spawning, round transitions, rewards, and victory state.
    """

    def __init__(self, player, arena_center_x: float, arena_center_y: float):
        self.player = player
        self.arena_cx = arena_center_x
        self.arena_cy = arena_center_y
        self.current_round = 0
        self.active = False
        self.enemies: List[Creature] = []
        self.total_gold_earned = 0
        self.total_xp_earned = 0
        self.rounds_won = 0
        self.defeated = False
        self.champion = False
        self.messages: List[str] = []

    @property
    def current_round_info(self) -> Optional[Dict]:
        if 0 <= self.current_round < len(ARENA_ROUNDS):
            return ARENA_ROUNDS[self.current_round]
        return None

    def start(self) -> str:
        """Begin the arena gauntlet. Returns status message."""
        self.active = True
        self.current_round = 0
        self.defeated = False
        self.champion = False
        self.total_gold_earned = 0
        self.total_xp_earned = 0
        self.rounds_won = 0

        # Move player to arena center
        self.player.x = self.arena_cx
        self.player.y = self.arena_cy

        # Spawn first round
        msg = self._spawn_round()
        return f"You enter the arena! {msg}"

    def _spawn_round(self) -> str:
        """Spawn enemies for the current round. Returns description."""
        info = self.current_round_info
        if info is None:
            return "No more rounds."

        self.enemies = []
        for kind, count in info["enemies"]:
            for i in range(count):
                # Place enemies in a semicircle around the arena
                angle = (i / max(1, count)) * 3.14159 + random.uniform(-0.3, 0.3)
                dist = 6.0 + random.uniform(0, 3)
                ex = self.arena_cx + dist * _cos(angle)
                ey = self.arena_cy + dist * _sin(angle)

                creature = Creature(ex, ey, kind)
                creature.passive = False
                creature._is_arena = True  # Prevent fleeing
                creature.combat_target = self.player
                creature.state = "fighting"
                self.enemies.append(creature)

        enemy_desc = ", ".join(
            f"{count} {kind}" for kind, count in info["enemies"]
        )
        return f'{info["name"]} -- Fight: {enemy_desc}!'

    def get_arena_creatures(self) -> List[Creature]:
        """Return active arena creatures for the combat system to process."""
        if not self.active:
            return []
        return [e for e in self.enemies if e.alive]

    def update(self, dt: float) -> Optional[str]:
        """Check round completion. Called each game tick.

        Returns a message if the round ends, or None.
        """
        if not self.active or self.defeated:
            return None

        # Check if player died
        if not self.player.alive or self.player.hp <= 0:
            self.defeated = True
            self.active = False
            return (f"You have been defeated in the arena after winning "
                    f"{self.rounds_won} rounds! "
                    f"Total earnings: {self.total_gold_earned}g, "
                    f"{self.total_xp_earned} XP")

        # Check if all enemies are dead
        alive_enemies = [e for e in self.enemies if e.alive]
        if alive_enemies:
            return None  # Round still in progress

        # Round won!
        info = self.current_round_info
        if info is None:
            self.active = False
            return None

        gold = info["gold_reward"]
        xp = info["xp_reward"]
        self.player.gold += gold
        self.player.gain_xp(xp)
        self.total_gold_earned += gold
        self.total_xp_earned += xp
        self.rounds_won += 1

        msg = (f'{info["name"]} complete! +{gold}g, +{xp} XP')

        # Advance to next round
        self.current_round += 1
        if self.current_round >= len(ARENA_ROUNDS):
            # All rounds won — champion!
            self.champion = True
            self.active = False
            self.player.title = CHAMPION_TITLE
            msg += (f"\n*** VICTORY! You are the {CHAMPION_TITLE}! ***\n"
                    f"Total: {self.total_gold_earned}g, "
                    f"{self.total_xp_earned} XP")
            return msg

        # Heal player between rounds (50% of missing HP)
        missing = self.player.max_hp - self.player.hp
        self.player.hp += missing // 2

        # Spawn next round
        next_msg = self._spawn_round()
        msg += f"\n{next_msg}"
        return msg

    def forfeit(self) -> str:
        """Player forfeits the arena match."""
        self.active = False
        self.enemies = []
        return (f"You forfeit the arena match. "
                f"Rounds won: {self.rounds_won}, "
                f"Gold earned: {self.total_gold_earned}g")


def _cos(angle: float) -> float:
    """Math.cos without importing math in every call."""
    import math
    return math.cos(angle)


def _sin(angle: float) -> float:
    """Math.sin without importing math in every call."""
    import math
    return math.sin(angle)


# ---------------------------------------------------------------------------
# Dialog Integration — adds "I want to fight" option to colosseum NPCs
# ---------------------------------------------------------------------------

# Active sessions by player id
_active_sessions: Dict[int, PlayerArenaSession] = {}


def get_player_arena_session(player) -> Optional[PlayerArenaSession]:
    """Get the active arena session for a player, if any."""
    return _active_sessions.get(id(player))


def start_arena_session(player, arena_cx: float, arena_cy: float) -> str:
    """Start a new arena session for the player.

    Called when the player selects "I want to fight" from a colosseum NPC.
    """
    pid = id(player)

    # Check if already in session
    existing = _active_sessions.get(pid)
    if existing and existing.active:
        return "You are already in an arena match!"

    session = PlayerArenaSession(player, arena_cx, arena_cy)
    _active_sessions[pid] = session
    return session.start()


def update_arena_session(player, dt: float) -> Optional[str]:
    """Update the player's arena session. Returns message or None."""
    session = _active_sessions.get(id(player))
    if session is None or not session.active:
        return None
    return session.update(dt)


def forfeit_arena(player) -> str:
    """Player forfeits current arena match."""
    session = _active_sessions.get(id(player))
    if session is None or not session.active:
        return "You are not in an arena match."
    return session.forfeit()


def is_colosseum_npc(npc) -> bool:
    """Check if an NPC is a colosseum-related NPC that offers arena fights.

    Recognizes NPCs near a colosseum building or with gladiator/arena titles.
    """
    title = getattr(npc, 'title', '').lower()
    prof = getattr(npc, 'profession', '').lower()
    name = getattr(npc, 'name', '').lower()

    arena_keywords = ('arena', 'colosseum', 'gladiator', 'pit fighter',
                      'fight master', 'battlemaster')
    combined = f"{title} {prof} {name}"
    return any(kw in combined for kw in arena_keywords)


def get_colosseum_dialog_options(npc, player) -> list:
    """Return extra dialog options for colosseum NPCs.

    Returns list of (player_text, dialog_key) tuples to add to greeting.
    """
    if not is_colosseum_npc(npc):
        return []

    session = get_player_arena_session(player)
    options = []

    if session and session.active:
        options.append(("I want to forfeit the match.", "arena_forfeit"))
    else:
        options.append(("I want to fight in the arena!", "arena_enter"))

    if session and session.champion:
        options.append(("I am the Arena Champion!", "arena_champion"))

    return options


def handle_colosseum_dialog(npc, player, choice: str) -> str:
    """Handle a colosseum dialog choice. Returns response text."""
    if choice == "arena_enter":
        cx = getattr(npc, 'x', 0.0)
        cy = getattr(npc, 'y', 0.0)
        # Try to find actual arena center from nearby structure
        if hasattr(npc, 'home_x') and hasattr(npc, 'home_y'):
            cx = npc.home_x
            cy = npc.home_y
        return start_arena_session(player, cx, cy)

    elif choice == "arena_forfeit":
        return forfeit_arena(player)

    elif choice == "arena_champion":
        return ("Hail, Champion! Your name will be remembered in the annals "
                "of the arena. May your blade stay sharp and your shield hold true.")

    return "I don't understand what you're asking."
