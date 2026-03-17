"""
Game server for multiplayer.
Runs embedded in the host game - the first player IS the server.
Uses threading + TCP sockets to accept remote player connections.
"""

import socket
import threading
import time
import json
import traceback
from typing import Dict, Optional

from game.network.protocol import (
    MessageType, MessageBuffer, encode_message,
    make_player_state, make_time_sync, make_world_state,
    make_notification, make_game_event,
    PROTOCOL_VERSION, MAX_MESSAGE_SIZE,
)


class ClientConnection:
    """Represents a connected remote player on the server side."""

    def __init__(self, sock: socket.socket, addr: tuple, player_id: str):
        self.sock = sock
        self.addr = addr
        self.player_id = player_id
        self.player_name = ""
        self.buffer = MessageBuffer()
        self.connected = True
        self.last_heartbeat = time.time()
        # Remote player state
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

    def send(self, data: bytes):
        """Send data to this client. Non-blocking, silently drops on error."""
        if not self.connected:
            return
        try:
            self.sock.sendall(data)
        except (OSError, BrokenPipeError):
            self.connected = False

    def close(self):
        """Close the connection."""
        self.connected = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class GameServer:
    """TCP game server that runs in a background thread.

    The host player creates this server. Remote players (human or AI)
    connect to it. The server broadcasts game state and routes messages.

    Usage:
        server = GameServer(port=7777)
        server.start()
        # In game loop:
        messages = server.get_pending_messages()
        server.broadcast_state(game)
        # On shutdown:
        server.stop()
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 7777,
                 max_players: int = 2):
        self.host = host
        self.port = port
        self.max_players = max_players

        self._server_sock: Optional[socket.socket] = None
        self._clients: Dict[str, ClientConnection] = {}
        self._client_lock = threading.Lock()
        self._message_queue: list = []
        self._msg_lock = threading.Lock()
        self._running = False
        self._accept_thread: Optional[threading.Thread] = None
        self._next_id = 1

        # Chat history for new joiners
        self._chat_history: list = []
        self._max_chat_history = 50

    @property
    def running(self) -> bool:
        return self._running

    @property
    def client_count(self) -> int:
        with self._client_lock:
            return len(self._clients)

    def get_clients(self) -> dict:
        """Return a snapshot of connected clients."""
        with self._client_lock:
            return dict(self._clients)

    def start(self) -> bool:
        """Start the server. Returns True if started successfully."""
        if self._running:
            return True
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.settimeout(1.0)  # allows clean shutdown
            self._server_sock.bind((self.host, self.port))
            self._server_sock.listen(self.max_players)
            self._running = True
            self._accept_thread = threading.Thread(
                target=self._accept_loop, daemon=True, name="GameServer-Accept")
            self._accept_thread.start()
            print(f"[SERVER] Listening on {self.host}:{self.port}")
            return True
        except OSError as e:
            print(f"[SERVER] Failed to start: {e}")
            self._running = False
            return False

    def stop(self):
        """Stop the server and disconnect all clients."""
        if not self._running:
            return
        self._running = False
        print("[SERVER] Shutting down...")

        # Notify clients
        leave_msg = make_notification("Server shutting down.", 5.0, (255, 100, 100))
        with self._client_lock:
            for client in self._clients.values():
                client.send(leave_msg)
                client.close()
            self._clients.clear()

        # Close server socket
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass

        # Wait for accept thread
        if self._accept_thread and self._accept_thread.is_alive():
            self._accept_thread.join(timeout=3.0)

        print("[SERVER] Stopped.")

    def _accept_loop(self):
        """Background thread: accept new connections."""
        while self._running:
            try:
                client_sock, addr = self._server_sock.accept()
                client_sock.settimeout(0.5)
                client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._handle_new_connection(client_sock, addr)
            except socket.timeout:
                continue
            except OSError:
                if self._running:
                    traceback.print_exc()
                break

    def _handle_new_connection(self, sock: socket.socket, addr: tuple):
        """Process a new incoming connection."""
        with self._client_lock:
            if len(self._clients) >= self.max_players:
                # Reject
                try:
                    reject = encode_message(MessageType.PLAYER_REJECTED, {
                        "reason": "Server full",
                    })
                    sock.sendall(reject)
                    sock.close()
                except OSError:
                    pass
                print(f"[SERVER] Rejected connection from {addr} (full)")
                return

        player_id = f"player_{self._next_id}"
        self._next_id += 1
        client = ClientConnection(sock, addr, player_id)

        # Start receive thread for this client
        recv_thread = threading.Thread(
            target=self._client_recv_loop, args=(client,),
            daemon=True, name=f"GameServer-Recv-{player_id}")
        recv_thread.start()

        print(f"[SERVER] Connection from {addr}, assigned ID: {player_id}")

    def _client_recv_loop(self, client: ClientConnection):
        """Background thread: receive messages from a single client."""
        joined = False
        try:
            while self._running and client.connected:
                try:
                    data = client.sock.recv(4096)
                    if not data:
                        break
                    messages = client.buffer.feed(data)
                    for msg in messages:
                        self._process_client_message(client, msg)
                        if msg["type"] == MessageType.PLAYER_JOIN:
                            joined = True
                except socket.timeout:
                    continue
                except (ConnectionResetError, BrokenPipeError):
                    break
        except Exception:
            traceback.print_exc()
        finally:
            self._handle_disconnect(client, joined)

    def _process_client_message(self, client: ClientConnection, msg: dict):
        """Process an incoming message from a client."""
        msg_type = msg["type"]
        data = msg.get("data", {})

        if msg_type == MessageType.PLAYER_JOIN:
            name = data.get("name", "Unknown")
            version = data.get("version", 0)
            is_ai = data.get("is_ai", False)

            if version != PROTOCOL_VERSION:
                client.send(encode_message(MessageType.PLAYER_REJECTED, {
                    "reason": f"Protocol mismatch (server={PROTOCOL_VERSION}, "
                              f"client={version})",
                }))
                client.close()
                return

            client.player_name = name
            client.is_ai = is_ai

            # Register client
            with self._client_lock:
                self._clients[client.player_id] = client

            # Send acceptance with player ID and existing player list
            with self._client_lock:
                existing = {
                    pid: {"name": c.player_name, "x": c.x, "y": c.y}
                    for pid, c in self._clients.items()
                    if pid != client.player_id
                }
            client.send(encode_message(MessageType.PLAYER_ACCEPTED, {
                "player_id": client.player_id,
                "existing_players": existing,
            }))

            # Send recent chat history
            for chat_msg in self._chat_history[-10:]:
                client.send(chat_msg)

            # Broadcast join to other clients
            join_notification = make_notification(
                f"{name} joined the game.", 4.0, (100, 220, 100))
            self._broadcast_except(join_notification, client.player_id)

            # Queue for game loop
            self._enqueue(msg_type, {
                "player_id": client.player_id,
                "name": name,
                "is_ai": is_ai,
            })

            prefix = "[AI] " if is_ai else ""
            print(f"[SERVER] {prefix}{name} ({client.player_id}) joined from "
                  f"{client.addr}")

        elif msg_type == MessageType.PLAYER_MOVE:
            # Update server-side state
            client.x = data.get("x", client.x)
            client.y = data.get("y", client.y)
            client.vx = data.get("vx", 0)
            client.vy = data.get("vy", 0)
            client.facing = tuple(data.get("facing", [0, 1]))
            client.gait = data.get("gait", "walk")
            client.last_heartbeat = time.time()

            # Broadcast to other clients
            data["player_id"] = client.player_id
            move_msg = encode_message(MessageType.PLAYER_MOVE, data)
            self._broadcast_except(move_msg, client.player_id)

        elif msg_type == MessageType.PLAYER_CHAT:
            data["player_id"] = client.player_id
            data["name"] = client.player_name
            chat_msg = encode_message(MessageType.CHAT_MESSAGE, data)
            # Broadcast to all including sender (so they see it confirmed)
            self._broadcast_all(chat_msg)
            # Save to history
            self._chat_history.append(chat_msg)
            if len(self._chat_history) > self._max_chat_history:
                self._chat_history = self._chat_history[-self._max_chat_history:]
            # Queue for host game
            self._enqueue(MessageType.PLAYER_CHAT, data)

        elif msg_type == MessageType.PLAYER_ATTACK:
            data["player_id"] = client.player_id
            self._enqueue(msg_type, data)
            # Broadcast attack visual to other clients
            attack_msg = encode_message(MessageType.PLAYER_ATTACK, data)
            self._broadcast_except(attack_msg, client.player_id)

        elif msg_type == MessageType.PLAYER_INTERACT:
            data["player_id"] = client.player_id
            self._enqueue(msg_type, data)

        elif msg_type == MessageType.PING:
            client.send(encode_message(MessageType.PONG, {
                "server_time": time.time(),
            }))
            client.last_heartbeat = time.time()

        elif msg_type == MessageType.AI_COMMAND:
            data["player_id"] = client.player_id
            self._enqueue(msg_type, data)

    def _handle_disconnect(self, client: ClientConnection, was_joined: bool):
        """Handle a client disconnecting."""
        client.connected = False
        with self._client_lock:
            self._clients.pop(client.player_id, None)
        client.close()

        if was_joined:
            name = client.player_name or client.player_id
            leave_msg = make_notification(
                f"{name} left the game.", 4.0, (220, 150, 100))
            self._broadcast_all(leave_msg)
            self._enqueue(MessageType.PLAYER_LEAVE, {
                "player_id": client.player_id,
                "name": name,
            })
            print(f"[SERVER] {name} ({client.player_id}) disconnected")

    def _broadcast_all(self, data: bytes):
        """Send data to all connected clients."""
        with self._client_lock:
            for client in list(self._clients.values()):
                client.send(data)

    def _broadcast_except(self, data: bytes, exclude_id: str):
        """Send data to all clients except one."""
        with self._client_lock:
            for pid, client in list(self._clients.items()):
                if pid != exclude_id:
                    client.send(data)

    def _enqueue(self, msg_type: str, data: dict):
        """Add a message to the queue for the game loop to process."""
        with self._msg_lock:
            self._message_queue.append({"type": msg_type, "data": data})

    def get_pending_messages(self) -> list:
        """Retrieve and clear all pending messages. Called from game loop.

        Returns:
            List of message dicts with 'type' and 'data'.
        """
        with self._msg_lock:
            msgs = self._message_queue
            self._message_queue = []
        return msgs

    def broadcast_state(self, game):
        """Broadcast game state to all clients. Called from game loop.

        Sends:
        - All remote player positions
        - Nearby NPC data
        - Time sync
        - Game events
        """
        if not self._running or self.client_count == 0:
            return

        # Build player state dict (includes host player)
        players = {
            "host": {
                "name": game.player.name,
                "x": game.player.x,
                "y": game.player.y,
                "hp": int(game.player.hp),
                "max_hp": game.player.max_hp,
                "level": game.player.level,
                "facing": list(game.player.facing),
                "gait": getattr(game.player, 'current_gait', 'walk'),
            }
        }
        with self._client_lock:
            for pid, client in self._clients.items():
                players[pid] = {
                    "name": client.player_name,
                    "x": client.x,
                    "y": client.y,
                    "hp": client.hp,
                    "max_hp": client.max_hp,
                    "level": client.level,
                    "facing": list(client.facing),
                    "gait": client.gait,
                    "is_ai": client.is_ai,
                }

        # Gather nearby NPCs (within 30 tiles of any player)
        npc_data = []
        player_positions = [(p["x"], p["y"]) for p in players.values()]
        for npc in game.world_mgr.npcs[:200]:  # cap for bandwidth
            if not npc.alive:
                continue
            for px, py in player_positions:
                dx = npc.x - px
                dy = npc.y - py
                if dx * dx + dy * dy < 900:  # 30 tiles
                    npc_data.append({
                        "name": npc.name,
                        "x": npc.x, "y": npc.y,
                        "hp": int(npc.hp),
                        "max_hp": npc.max_hp,
                        "profession": npc.profession,
                        "action": getattr(npc, 'current_action', 'idle'),
                    })
                    break

        # Time sync
        time_msg = make_time_sync(
            game.time_sys.time, game.time_sys.day,
            game.time_sys.darkness)

        # World state
        state_msg = make_world_state(players, npc_data)

        # Send to all clients
        self._broadcast_all(time_msg)
        self._broadcast_all(state_msg)

    def send_event(self, event_type: str, description: str,
                   x: float = 0, y: float = 0):
        """Broadcast a game event to all clients."""
        if not self._running:
            return
        msg = make_game_event(event_type, description, x, y)
        self._broadcast_all(msg)

    def send_chat(self, sender_name: str, text: str):
        """Send a chat message from the host player."""
        if not self._running:
            return
        msg = encode_message(MessageType.CHAT_MESSAGE, {
            "player_id": "host",
            "name": sender_name,
            "text": text,
        })
        self._broadcast_all(msg)
        self._chat_history.append(msg)
        if len(self._chat_history) > self._max_chat_history:
            self._chat_history = self._chat_history[-self._max_chat_history:]

    def kick_player(self, player_id: str, reason: str = "Kicked by host"):
        """Disconnect a specific player."""
        with self._client_lock:
            client = self._clients.get(player_id)
        if client:
            client.send(make_notification(
                f"Kicked: {reason}", 5.0, (255, 100, 100)))
            client.close()
