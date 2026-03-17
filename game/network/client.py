"""
Remote client connection for multiplayer.
Connects to a GameServer via TCP, sends player input, receives state updates.
"""

import socket
import threading
import time
import traceback
from typing import Optional, Callable

from game.network.protocol import (
    MessageType, MessageBuffer, encode_message,
    make_join, make_move, make_chat, make_attack,
    PROTOCOL_VERSION,
)


class RemotePlayerState:
    """State of a remote player as seen by this client."""

    def __init__(self, player_id: str, name: str):
        self.player_id = player_id
        self.name = name
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.facing = (0, 1)
        self.gait = "walk"
        self.hp = 100
        self.max_hp = 100
        self.level = 1
        self.is_ai = False
        # Interpolation
        self.target_x = 0.0
        self.target_y = 0.0
        self.last_update = time.time()


class GameClient:
    """TCP client that connects to a GameServer.

    Usage:
        client = GameClient()
        if client.connect("192.168.1.10", 7777, "Player2"):
            # In game loop:
            client.send_move(x, y, vx, vy)
            client.update(dt)  # interpolates remote players
            for msg in client.get_pending_messages():
                handle(msg)
            # On shutdown:
            client.disconnect()
    """

    def __init__(self):
        self._sock: Optional[socket.socket] = None
        self._buffer = MessageBuffer()
        self._connected = False
        self._recv_thread: Optional[threading.Thread] = None

        # Assigned by server on join
        self.player_id: str = ""
        self.player_name: str = ""

        # Remote players visible to this client
        self.remote_players: dict = {}  # player_id -> RemotePlayerState
        self._players_lock = threading.Lock()

        # Message queue for game loop
        self._message_queue: list = []
        self._msg_lock = threading.Lock()

        # Chat log
        self.chat_log: list = []  # list of (name, text, timestamp)
        self._max_chat = 100

        # Time sync
        self.server_time = 0.0
        self.server_day = 0
        self.server_darkness = 0.0

        # Latency measurement
        self._ping_sent = 0.0
        self.latency_ms = 0.0

        # Connection status
        self.status = "disconnected"
        self.reject_reason = ""

        # Callbacks
        self.on_chat: Optional[Callable] = None
        self.on_notification: Optional[Callable] = None

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self, host: str, port: int, player_name: str,
                is_ai: bool = False, timeout: float = 5.0) -> bool:
        """Connect to a game server.

        Args:
            host: Server IP address or hostname.
            port: Server port.
            player_name: Display name for this player.
            is_ai: Whether this is an AI-controlled player.
            timeout: Connection timeout in seconds.

        Returns:
            True if connection and join were successful.
        """
        if self._connected:
            self.disconnect()

        self.player_name = player_name
        self.status = "connecting"

        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(timeout)
            self._sock.connect((host, port))
            self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._sock.settimeout(0.5)  # for recv loop
        except (OSError, ConnectionRefusedError) as e:
            self.status = f"failed: {e}"
            print(f"[CLIENT] Connection failed: {e}")
            return False

        # Send join request
        join_msg = encode_message(MessageType.PLAYER_JOIN, {
            "name": player_name,
            "version": PROTOCOL_VERSION,
            "is_ai": is_ai,
        })
        try:
            self._sock.sendall(join_msg)
        except OSError as e:
            self.status = f"failed: {e}"
            return False

        # Wait for acceptance
        try:
            self._sock.settimeout(timeout)
            data = self._sock.recv(4096)
            if not data:
                self.status = "rejected: no response"
                return False
            messages = self._buffer.feed(data)
            for msg in messages:
                if msg["type"] == MessageType.PLAYER_ACCEPTED:
                    self.player_id = msg["data"]["player_id"]
                    # Register existing players
                    existing = msg["data"].get("existing_players", {})
                    with self._players_lock:
                        for pid, pdata in existing.items():
                            rp = RemotePlayerState(pid, pdata.get("name", "?"))
                            rp.x = rp.target_x = pdata.get("x", 0)
                            rp.y = rp.target_y = pdata.get("y", 0)
                            self.remote_players[pid] = rp
                    self._connected = True
                    self.status = "connected"
                    print(f"[CLIENT] Connected as {self.player_id}")
                elif msg["type"] == MessageType.PLAYER_REJECTED:
                    reason = msg["data"].get("reason", "Unknown")
                    self.status = f"rejected: {reason}"
                    self.reject_reason = reason
                    print(f"[CLIENT] Rejected: {reason}")
                    self._sock.close()
                    return False
        except socket.timeout:
            self.status = "failed: timeout waiting for server response"
            self._sock.close()
            return False

        if not self._connected:
            self.status = "failed: no acceptance received"
            self._sock.close()
            return False

        # Start receive thread
        self._sock.settimeout(0.5)
        self._recv_thread = threading.Thread(
            target=self._recv_loop, daemon=True, name="GameClient-Recv")
        self._recv_thread.start()

        return True

    def disconnect(self):
        """Disconnect from the server."""
        if not self._connected:
            return
        self._connected = False
        self.status = "disconnected"
        # Send leave
        try:
            leave = encode_message(MessageType.PLAYER_LEAVE, {
                "player_id": self.player_id,
            })
            self._sock.sendall(leave)
        except OSError:
            pass
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self._sock.close()
        except OSError:
            pass
        if self._recv_thread and self._recv_thread.is_alive():
            self._recv_thread.join(timeout=2.0)
        with self._players_lock:
            self.remote_players.clear()
        print("[CLIENT] Disconnected")

    def _recv_loop(self):
        """Background thread: receive messages from server."""
        try:
            while self._connected:
                try:
                    data = self._sock.recv(8192)
                    if not data:
                        break
                    messages = self._buffer.feed(data)
                    for msg in messages:
                        self._handle_message(msg)
                except socket.timeout:
                    continue
                except (ConnectionResetError, BrokenPipeError):
                    break
        except Exception:
            traceback.print_exc()
        finally:
            if self._connected:
                self._connected = False
                self.status = "disconnected (lost connection)"
                print("[CLIENT] Lost connection to server")

    def _handle_message(self, msg: dict):
        """Process an incoming message from the server."""
        msg_type = msg["type"]
        data = msg.get("data", {})

        if msg_type == MessageType.WORLD_STATE:
            self._handle_world_state(data)

        elif msg_type == MessageType.TIME_SYNC:
            self.server_time = data.get("game_time", 0)
            self.server_day = data.get("day", 0)
            self.server_darkness = data.get("darkness", 0)

        elif msg_type == MessageType.PLAYER_MOVE:
            pid = data.get("player_id", "")
            with self._players_lock:
                rp = self.remote_players.get(pid)
                if rp:
                    rp.target_x = data.get("x", rp.x)
                    rp.target_y = data.get("y", rp.y)
                    rp.vx = data.get("vx", 0)
                    rp.vy = data.get("vy", 0)
                    rp.facing = tuple(data.get("facing", [0, 1]))
                    rp.gait = data.get("gait", "walk")
                    rp.last_update = time.time()

        elif msg_type == MessageType.PLAYER_ATTACK:
            # Queue for game loop to render attack effects
            self._enqueue(msg_type, data)

        elif msg_type == MessageType.CHAT_MESSAGE:
            name = data.get("name", "?")
            text = data.get("text", "")
            self.chat_log.append((name, text, time.time()))
            if len(self.chat_log) > self._max_chat:
                self.chat_log = self.chat_log[-self._max_chat:]
            if self.on_chat:
                self.on_chat(name, text)
            self._enqueue(msg_type, data)

        elif msg_type == MessageType.NOTIFICATION:
            text = data.get("text", "")
            if self.on_notification:
                duration = data.get("duration", 3.0)
                color = tuple(data.get("color", [220, 220, 230]))
                self.on_notification(text, duration, color)
            self._enqueue(msg_type, data)

        elif msg_type == MessageType.GAME_EVENT:
            self._enqueue(msg_type, data)

        elif msg_type == MessageType.NPC_UPDATE:
            self._enqueue(msg_type, data)

        elif msg_type == MessageType.PONG:
            if self._ping_sent > 0:
                self.latency_ms = (time.time() - self._ping_sent) * 1000
                self._ping_sent = 0

    def _handle_world_state(self, data: dict):
        """Process a WORLD_STATE update from the server."""
        players_data = data.get("players", {})

        with self._players_lock:
            seen_ids = set()
            for pid, pdata in players_data.items():
                if pid == self.player_id:
                    continue  # skip self
                seen_ids.add(pid)
                if pid not in self.remote_players:
                    name = pdata.get("name", "?")
                    self.remote_players[pid] = RemotePlayerState(pid, name)
                rp = self.remote_players[pid]
                rp.name = pdata.get("name", rp.name)
                rp.target_x = pdata.get("x", rp.x)
                rp.target_y = pdata.get("y", rp.y)
                rp.hp = pdata.get("hp", rp.hp)
                rp.max_hp = pdata.get("max_hp", rp.max_hp)
                rp.level = pdata.get("level", rp.level)
                rp.facing = tuple(pdata.get("facing", list(rp.facing)))
                rp.gait = pdata.get("gait", rp.gait)
                rp.is_ai = pdata.get("is_ai", rp.is_ai)
                rp.last_update = time.time()

            # Remove players no longer in state
            for pid in list(self.remote_players.keys()):
                if pid not in seen_ids:
                    del self.remote_players[pid]

        # NPC data available for rendering
        npc_data = data.get("npcs", [])
        if npc_data:
            self._enqueue(MessageType.NPC_UPDATE, {"npcs": npc_data})

    def update(self, dt: float):
        """Update client state. Call each frame.

        Interpolates remote player positions for smooth rendering.
        """
        if not self._connected:
            return

        # Interpolate remote player positions
        with self._players_lock:
            for rp in self.remote_players.values():
                # Lerp toward target position
                lerp_speed = 8.0  # higher = snappier
                dx = rp.target_x - rp.x
                dy = rp.target_y - rp.y
                if abs(dx) > 20 or abs(dy) > 20:
                    # Teleport if too far (respawn, etc.)
                    rp.x = rp.target_x
                    rp.y = rp.target_y
                else:
                    rp.x += dx * min(1.0, lerp_speed * dt)
                    rp.y += dy * min(1.0, lerp_speed * dt)

    def _enqueue(self, msg_type: str, data: dict):
        """Queue a message for game loop processing."""
        with self._msg_lock:
            self._message_queue.append({"type": msg_type, "data": data})

    def get_pending_messages(self) -> list:
        """Retrieve and clear pending messages. Called from game loop."""
        with self._msg_lock:
            msgs = self._message_queue
            self._message_queue = []
        return msgs

    def get_remote_players(self) -> list:
        """Get a snapshot of all remote player states.

        Returns:
            List of RemotePlayerState objects.
        """
        with self._players_lock:
            return list(self.remote_players.values())

    # ---- Send methods ----

    def send_move(self, x: float, y: float, vx: float = 0, vy: float = 0,
                  facing: tuple = (0, 1), gait: str = "walk"):
        """Send player position update to server."""
        if not self._connected:
            return
        msg = make_move(self.player_id, x, y, vx, vy, facing, gait)
        try:
            self._sock.sendall(msg)
        except OSError:
            pass

    def send_chat(self, text: str):
        """Send a chat message."""
        if not self._connected or not text:
            return
        msg = make_chat(self.player_id, self.player_name, text)
        try:
            self._sock.sendall(msg)
        except OSError:
            pass

    def send_attack(self, target_type: str, target_id: str,
                    x: float, y: float):
        """Send an attack action to the server."""
        if not self._connected:
            return
        msg = make_attack(self.player_id, target_type, target_id, x, y)
        try:
            self._sock.sendall(msg)
        except OSError:
            pass

    def send_interact(self, target_type: str, target_id: str):
        """Send an interaction to the server."""
        if not self._connected:
            return
        msg = encode_message(MessageType.PLAYER_INTERACT, {
            "player_id": self.player_id,
            "target_type": target_type,
            "target_id": target_id,
        })
        try:
            self._sock.sendall(msg)
        except OSError:
            pass

    def send_ping(self):
        """Send a latency ping to the server."""
        if not self._connected:
            return
        self._ping_sent = time.time()
        msg = encode_message(MessageType.PING, {})
        try:
            self._sock.sendall(msg)
        except OSError:
            pass

    def send_ai_command(self, command: str, args: dict = None):
        """Send an AI command (for AI-controlled players)."""
        if not self._connected:
            return
        msg = encode_message(MessageType.AI_COMMAND, {
            "player_id": self.player_id,
            "command": command,
            "args": args or {},
        })
        try:
            self._sock.sendall(msg)
        except OSError:
            pass
