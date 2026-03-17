"""
Network message protocol for multiplayer.
JSON messages over TCP with newline delimiter.
"""

import json
import time
from enum import Enum


class MessageType(str, Enum):
    """All network message types."""
    # Connection
    PLAYER_JOIN = "player_join"
    PLAYER_LEAVE = "player_leave"
    PLAYER_ACCEPTED = "player_accepted"
    PLAYER_REJECTED = "player_rejected"

    # Player actions
    PLAYER_MOVE = "player_move"
    PLAYER_ATTACK = "player_attack"
    PLAYER_INTERACT = "player_interact"
    PLAYER_CHAT = "player_chat"
    PLAYER_USE_ITEM = "player_use_item"

    # State sync
    WORLD_STATE = "world_state"
    NPC_UPDATE = "npc_update"
    TIME_SYNC = "time_sync"
    PLAYER_STATE = "player_state"

    # Events
    GAME_EVENT = "game_event"
    NOTIFICATION = "notification"
    CHAT_MESSAGE = "chat_message"

    # AI player
    AI_COMMAND = "ai_command"
    AI_STATUS = "ai_status"

    # Heartbeat
    PING = "ping"
    PONG = "pong"


# Maximum message size (bytes) to prevent abuse
MAX_MESSAGE_SIZE = 65536

# Protocol version for compatibility checks
PROTOCOL_VERSION = 1


def encode_message(msg_type: str, data: dict = None) -> bytes:
    """Encode a message as JSON + newline delimiter.

    Args:
        msg_type: One of the MessageType values.
        data: Message payload dictionary.

    Returns:
        Encoded bytes ready for TCP send.
    """
    message = {
        "type": msg_type,
        "timestamp": time.time(),
        "data": data or {},
    }
    return (json.dumps(message, default=str) + "\n").encode("utf-8")


def decode_message(raw: str) -> dict:
    """Decode a single JSON message string.

    Args:
        raw: The raw JSON string (without newline).

    Returns:
        Parsed message dict with 'type', 'timestamp', 'data' keys.

    Raises:
        ValueError: If the message is invalid.
    """
    if len(raw) > MAX_MESSAGE_SIZE:
        raise ValueError("Message exceeds maximum size")
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    if "type" not in msg:
        raise ValueError("Message missing 'type' field")

    return msg


def validate_message(msg: dict) -> bool:
    """Check that a decoded message has valid structure.

    Args:
        msg: Decoded message dictionary.

    Returns:
        True if valid.
    """
    if not isinstance(msg, dict):
        return False
    if "type" not in msg:
        return False
    if msg["type"] not in [e.value for e in MessageType]:
        return False
    return True


class MessageBuffer:
    """Accumulates raw TCP data and yields complete messages.

    Handles partial reads and message framing using newline delimiters.
    """

    def __init__(self):
        self._buffer = ""

    def feed(self, data: bytes) -> list:
        """Feed raw bytes and return list of complete decoded messages.

        Args:
            data: Raw bytes received from TCP socket.

        Returns:
            List of decoded message dicts.
        """
        self._buffer += data.decode("utf-8", errors="replace")
        messages = []
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                msg = decode_message(line)
                if validate_message(msg):
                    messages.append(msg)
            except ValueError:
                # Discard malformed messages
                pass
        # Prevent buffer from growing unbounded
        if len(self._buffer) > MAX_MESSAGE_SIZE:
            self._buffer = ""
        return messages


# Convenience constructors for common messages

def make_join(player_name: str, protocol_version: int = PROTOCOL_VERSION) -> bytes:
    """Create a PLAYER_JOIN message."""
    return encode_message(MessageType.PLAYER_JOIN, {
        "name": player_name,
        "version": protocol_version,
    })


def make_move(player_id: str, x: float, y: float,
              vx: float = 0, vy: float = 0,
              facing: tuple = (0, 1), gait: str = "walk") -> bytes:
    """Create a PLAYER_MOVE message."""
    return encode_message(MessageType.PLAYER_MOVE, {
        "player_id": player_id,
        "x": x, "y": y,
        "vx": vx, "vy": vy,
        "facing": list(facing),
        "gait": gait,
    })


def make_chat(player_id: str, player_name: str, text: str) -> bytes:
    """Create a PLAYER_CHAT message."""
    return encode_message(MessageType.PLAYER_CHAT, {
        "player_id": player_id,
        "name": player_name,
        "text": text,
    })


def make_attack(player_id: str, target_type: str,
                target_id: str, x: float, y: float) -> bytes:
    """Create a PLAYER_ATTACK message."""
    return encode_message(MessageType.PLAYER_ATTACK, {
        "player_id": player_id,
        "target_type": target_type,
        "target_id": target_id,
        "x": x, "y": y,
    })


def make_player_state(player_id: str, player_data: dict) -> bytes:
    """Create a PLAYER_STATE sync message."""
    return encode_message(MessageType.PLAYER_STATE, {
        "player_id": player_id,
        **player_data,
    })


def make_time_sync(game_time: float, day: int, darkness: float) -> bytes:
    """Create a TIME_SYNC message."""
    return encode_message(MessageType.TIME_SYNC, {
        "game_time": game_time,
        "day": day,
        "darkness": darkness,
    })


def make_world_state(players: dict, npcs: list = None,
                     events: list = None) -> bytes:
    """Create a WORLD_STATE broadcast message."""
    return encode_message(MessageType.WORLD_STATE, {
        "players": players,
        "npcs": npcs or [],
        "events": events or [],
    })


def make_notification(text: str, duration: float = 3.0,
                      color: tuple = (220, 220, 230)) -> bytes:
    """Create a NOTIFICATION message."""
    return encode_message(MessageType.NOTIFICATION, {
        "text": text,
        "duration": duration,
        "color": list(color),
    })


def make_game_event(event_type: str, description: str,
                    x: float = 0, y: float = 0) -> bytes:
    """Create a GAME_EVENT message."""
    return encode_message(MessageType.GAME_EVENT, {
        "event_type": event_type,
        "description": description,
        "x": x, "y": y,
    })
