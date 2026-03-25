"""Player-to-player trading over multiplayer.

Trade flow:
1. Player presses E near a remote player -> GAME_EVENT "trade_request"
2. Remote player sees notification, presses E to accept -> "trade_accept"
3. Each player offers items via GAME_EVENT "trade_offer"
4. Both confirm -> GAME_EVENT "trade_confirm" -> items swap
5. Either can cancel at any time -> "trade_cancel"

All trade events ride on the existing GAME_EVENT message type.
The host (server) validates and executes the swap.
"""

from __future__ import annotations
import time
from typing import TYPE_CHECKING, Optional, List, Dict

if TYPE_CHECKING:
    from game.network.server import GameServer


class TradeSession:
    """Tracks an active trade between two players.

    Attributes:
        initiator_id: Player ID who started the trade ("host" or "player_N").
        partner_id:   The other player's ID.
        initiator_offer: List of (item_name, count) offered by initiator.
        partner_offer:   List of (item_name, count) offered by partner.
        initiator_confirmed: True once the initiator locks in.
        partner_confirmed:   True once the partner locks in.
    """

    def __init__(self, initiator_id: str, partner_id: str):
        self.initiator_id = initiator_id
        self.partner_id = partner_id
        self.initiator_offer: List[tuple] = []  # [(item_name, count), ...]
        self.partner_offer: List[tuple] = []
        self.initiator_confirmed = False
        self.partner_confirmed = False
        self.created_at = time.time()
        self.active = True

    @property
    def both_confirmed(self) -> bool:
        return self.initiator_confirmed and self.partner_confirmed

    def set_offer(self, player_id: str, items: List[tuple]):
        """Set or update a player's offered items. Resets confirmations."""
        self.initiator_confirmed = False
        self.partner_confirmed = False
        if player_id == self.initiator_id:
            self.initiator_offer = list(items)
        elif player_id == self.partner_id:
            self.partner_offer = list(items)

    def confirm(self, player_id: str) -> bool:
        """Mark a player as confirmed. Returns True if both confirmed."""
        if player_id == self.initiator_id:
            self.initiator_confirmed = True
        elif player_id == self.partner_id:
            self.partner_confirmed = True
        return self.both_confirmed

    def cancel(self):
        """Cancel the trade session."""
        self.active = False

    def is_expired(self) -> bool:
        """Trade expires after 2 minutes without completion."""
        return time.time() - self.created_at > 120

    def get_offer_for(self, player_id: str) -> List[tuple]:
        """Items this player is offering."""
        if player_id == self.initiator_id:
            return self.initiator_offer
        return self.partner_offer

    def get_receive_for(self, player_id: str) -> List[tuple]:
        """Items this player would receive."""
        if player_id == self.initiator_id:
            return self.partner_offer
        return self.initiator_offer


# ── Trade manager (runs on host) ─────────────────────────────────

class TradeManager:
    """Manages all active trade sessions. Lives on the host/server side.

    Usage:
        mgr = TradeManager()
        # When player requests trade:
        mgr.request_trade("host", "player_1", server)
        # When partner accepts:
        mgr.accept_trade("player_1", server)
        # When a player offers items:
        mgr.set_offer("host", [("Bread", 2), ("Iron Sword", 1)], server)
        # When a player confirms:
        mgr.confirm_trade("host", server, game)
    """

    def __init__(self):
        self.sessions: Dict[str, TradeSession] = {}  # keyed by initiator_id

    def get_session(self, player_id: str) -> Optional[TradeSession]:
        """Find the active trade session involving this player."""
        for session in self.sessions.values():
            if not session.active:
                continue
            if player_id in (session.initiator_id, session.partner_id):
                return session
        return None

    def request_trade(self, initiator_id: str, partner_id: str,
                      server: "GameServer", initiator_name: str = ""):
        """Initiate a trade request."""
        # Cancel any existing session for either party
        for pid in (initiator_id, partner_id):
            existing = self.get_session(pid)
            if existing:
                existing.cancel()

        session = TradeSession(initiator_id, partner_id)
        self.sessions[initiator_id] = session

        name = initiator_name or initiator_id
        server.send_event(
            "trade_request",
            f"{name} wants to trade with you! Press E to accept.",
        )

    def accept_trade(self, partner_id: str,
                     server: "GameServer") -> Optional[TradeSession]:
        """Partner accepts the trade. Returns the session if found."""
        session = self.get_session(partner_id)
        if session is None or partner_id != session.partner_id:
            return None
        server.send_event("trade_accept", "Trade accepted! Offer your items.")
        return session

    def set_offer(self, player_id: str, items: List[tuple],
                  server: "GameServer"):
        """A player updates their offered items."""
        session = self.get_session(player_id)
        if session is None:
            return
        session.set_offer(player_id, items)

        # Broadcast what was offered
        item_str = ", ".join(f"{c}x {n}" for n, c in items) if items else "nothing"
        server.send_event("trade_offer", f"Trade offer updated: {item_str}")

    def confirm_trade(self, player_id: str, server: "GameServer",
                      game) -> Optional[str]:
        """Player confirms the trade. If both confirm, execute the swap.

        Returns a result message if the trade completed, else None.
        """
        session = self.get_session(player_id)
        if session is None:
            return None

        if session.confirm(player_id):
            # Both confirmed — execute the swap
            result = _execute_trade(session, server, game)
            session.cancel()
            return result

        server.send_event(
            "trade_confirm",
            f"Waiting for the other player to confirm...",
        )
        return None

    def cancel_trade(self, player_id: str, server: "GameServer"):
        """Cancel the active trade for this player."""
        session = self.get_session(player_id)
        if session:
            session.cancel()
            server.send_event("trade_cancel", "Trade cancelled.")

    def cleanup_expired(self):
        """Remove expired trade sessions."""
        expired = [k for k, s in self.sessions.items()
                   if not s.active or s.is_expired()]
        for k in expired:
            del self.sessions[k]


def _execute_trade(session: TradeSession, server: "GameServer", game) -> str:
    """Execute the item swap between two players.

    The host player's inventory is accessed directly.
    Remote player items are tracked as GAME_EVENTs (the remote client
    applies the changes locally when it receives the trade_complete event).
    """
    from game.core.items import make_item

    host_is_initiator = session.initiator_id == "host"
    host_id = "host"
    remote_id = session.partner_id if host_is_initiator else session.initiator_id
    host_gives = session.get_offer_for(host_id)
    host_receives = session.get_receive_for(host_id)

    # Remove items from host inventory
    player = game.player
    for item_name, count in host_gives:
        player.remove_item(item_name, count)

    # Add received items to host inventory
    for item_name, count in host_receives:
        item = make_item(item_name)
        if item:
            item.count = count
            player.add_item(item)

    # Build description of what the remote player gets/loses
    give_str = ", ".join(f"{c}x {n}" for n, c in host_gives) or "nothing"
    recv_str = ", ".join(f"{c}x {n}" for n, c in host_receives) or "nothing"

    server.send_event(
        "trade_complete",
        f"Trade complete! You receive: {give_str}. You gave: {recv_str}",
    )

    return f"Trade complete! You gave: {give_str}. You received: {recv_str}."


# ── Client-side handler ──────────────────────────────────────────

def handle_trade_event(game, data: dict):
    """Handle trade-related GAME_EVENTs on the receiving (client) side.

    Args:
        game: The Game instance.
        data: GAME_EVENT data dict.
    """
    event_type = data.get("event_type", "")
    desc = data.get("description", "")

    if event_type == "trade_request":
        game.notifications.add(desc, 6.0, (255, 220, 100))
        # Flag so the client knows pressing E will accept
        game._pending_trade_request = True

    elif event_type == "trade_accept":
        game.notifications.add(desc, 4.0, (100, 220, 180))

    elif event_type == "trade_offer":
        game.notifications.add(desc, 4.0, (200, 200, 150))

    elif event_type == "trade_confirm":
        game.notifications.add(desc, 3.0, (180, 180, 220))

    elif event_type == "trade_cancel":
        game.notifications.add(desc, 3.0, (220, 150, 100))
        game._pending_trade_request = False

    elif event_type == "trade_complete":
        game.notifications.add(desc, 5.0, (100, 255, 100))
        game._pending_trade_request = False
        # Apply item changes on the client side
        _apply_remote_trade(game, desc)


def _apply_remote_trade(game, desc: str):
    """Parse the trade_complete description and apply item changes.

    The description says "You receive: X. You gave: Y" from the remote
    player's perspective, so we reverse it for the local client.
    """
    from game.core.items import make_item

    try:
        # Format: "Trade complete! You receive: ITEMS. You gave: ITEMS"
        if "You receive:" not in desc:
            return
        parts = desc.split("You receive:")[-1]
        receive_part, gave_part = parts.split(". You gave:")
        receive_part = receive_part.strip()
        gave_part = gave_part.strip().rstrip(".")

        player = game.player

        # Remove items we gave
        if receive_part and receive_part != "nothing":
            for chunk in receive_part.split(","):
                chunk = chunk.strip()
                if "x " in chunk:
                    count_str, name = chunk.split("x ", 1)
                    player.remove_item(name.strip(), int(count_str.strip()))

        # Add items we receive
        if gave_part and gave_part != "nothing":
            for chunk in gave_part.split(","):
                chunk = chunk.strip()
                if "x " in chunk:
                    count_str, name = chunk.split("x ", 1)
                    item = make_item(name.strip())
                    if item:
                        item.count = int(count_str.strip())
                        player.add_item(item)
    except (ValueError, IndexError):
        pass
