"""PvP arena — lets local player fight a remote player in the colosseum.

Uses PLAYER_ATTACK messages for damage and GAME_EVENT for state sync.
The host resolves all combat; clients see the result via broadcasts.

Usage (from game loop):
    from game.network.pvp_arena import PvPArenaSession

    # Start a PvP match (host side):
    session = PvPArenaSession(local_player, remote_player_id)
    session.start(server)

    # Each tick:
    msg = session.update(dt, local_player, remote_hp)
"""

from __future__ import annotations
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from game.network.server import GameServer
    from game.core.remote_player import RemotePlayer


class PvPArenaSession:
    """Tracks a player-vs-player arena fight.

    The host (server owner) runs the authoritative session.
    Combat uses the existing PLAYER_ATTACK message routing; this class
    adds HP tracking, round management, and victory resolution.
    """

    def __init__(self, local_player, remote_player_id: str):
        self.local_player = local_player
        self.remote_player_id = remote_player_id
        self.active = False
        self.start_time = 0.0

        # Snapshot HP at match start so we can restore on forfeit
        self._local_start_hp = 0
        self._remote_start_hp = 0

        # Remote HP is tracked server-side from PLAYER_ATTACK messages
        self.remote_hp = 100
        self.remote_max_hp = 100

        self.winner: Optional[str] = None  # "local" | "remote" | None
        self.messages: list = []

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self, server: "GameServer"):
        """Begin the PvP match. Broadcasts to all clients."""
        self.active = True
        self.start_time = time.time()
        self._local_start_hp = self.local_player.hp
        self.winner = None
        self.messages.clear()

        # Grab remote player's current HP from server client data
        clients = server.get_clients()
        client = clients.get(self.remote_player_id)
        if client:
            self.remote_hp = client.hp
            self.remote_max_hp = client.max_hp
            self._remote_start_hp = client.hp
            opponent_name = client.player_name
        else:
            opponent_name = self.remote_player_id

        server.send_event(
            "pvp_start",
            f"PvP Arena: {self.local_player.name} vs {opponent_name}!",
        )

        msg = f"PvP match started against {opponent_name}!"
        self.messages.append(msg)
        return msg

    def apply_attack_to_remote(self, damage: int, server: "GameServer"):
        """Host hits the remote player. Deduct HP and broadcast."""
        if not self.active:
            return
        self.remote_hp = max(0, self.remote_hp - damage)

        # Update the server-side client record so world state reflects it
        clients = server.get_clients()
        client = clients.get(self.remote_player_id)
        if client:
            client.hp = self.remote_hp

        server.send_event(
            "pvp_damage",
            f"{self.local_player.name} deals {damage} damage!",
        )

    def apply_attack_to_local(self, damage: int, server: "GameServer"):
        """Remote player hits the host. Deduct HP and broadcast."""
        if not self.active:
            return
        self.local_player.hp = max(0, self.local_player.hp - damage)

        server.send_event(
            "pvp_damage",
            f"You take {damage} damage!",
        )

    def update(self, dt: float, server: "GameServer") -> Optional[str]:
        """Check for match end. Returns status message or None."""
        if not self.active:
            return None

        # Check local player defeated
        if self.local_player.hp <= 0:
            self.active = False
            self.winner = "remote"
            clients = server.get_clients()
            client = clients.get(self.remote_player_id)
            name = client.player_name if client else "opponent"
            result = f"You were defeated by {name} in the arena!"
            self._end_match(server, name)
            return result

        # Check remote player defeated
        if self.remote_hp <= 0:
            self.active = False
            self.winner = "local"
            result = "You are victorious in the arena!"
            self._end_match(server, self.local_player.name)
            return result

        # Timeout after 5 minutes → draw
        if time.time() - self.start_time > 300:
            self.active = False
            self.winner = None
            server.send_event("pvp_end", "PvP match ended in a draw (timeout).")
            return "The arena match ended in a draw."

        return None

    def _end_match(self, server: "GameServer", winner_name: str):
        """Broadcast match result and restore HP."""
        server.send_event("pvp_end", f"PvP Arena: {winner_name} wins!")

        # Restore some HP so neither player is stuck at 0
        self.local_player.hp = max(
            self.local_player.hp,
            self._local_start_hp // 2,
        )
        clients = server.get_clients()
        client = clients.get(self.remote_player_id)
        if client:
            client.hp = max(client.hp, self._remote_start_hp // 2)

    def forfeit(self, server: "GameServer") -> str:
        """Host forfeits the PvP match."""
        self.active = False
        self.winner = "remote"
        server.send_event("pvp_end", "PvP match forfeited.")
        # Restore HP
        self.local_player.hp = self._local_start_hp
        clients = server.get_clients()
        client = clients.get(self.remote_player_id)
        if client:
            client.hp = self._remote_start_hp
        return "You forfeited the arena match."


# ── GAME_EVENT handler (client side) ─────────────────────────────

def handle_pvp_event(game, data: dict):
    """Handle PvP-related GAME_EVENT on the receiving side.

    Args:
        game: The Game instance.
        data: GAME_EVENT data with event_type starting with 'pvp_'.
    """
    event_type = data.get("event_type", "")
    desc = data.get("description", "")

    if event_type == "pvp_start":
        game.notifications.add(desc, 5.0, (255, 200, 100))
    elif event_type == "pvp_damage":
        game.notifications.add(desc, 2.0, (255, 100, 100))
    elif event_type == "pvp_end":
        game.notifications.add(desc, 6.0, (100, 255, 200))
