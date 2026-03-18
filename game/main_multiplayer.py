"""Multiplayer networking — TCP server/client, AI player."""

from game.settings import *


class MultiplayerMixin:
    """Multiplayer methods for the Game class."""

    def _init_multiplayer(self):
        """Initialize multiplayer networking based on config."""
        if not self.config.get("multiplayer_enabled", False):
            return

        port = self.config.get("server_port", DEFAULT_PORT)
        max_p = self.config.get("max_players", MAX_PLAYERS)
        self.player.name = self.config.get("player_name", "Player")

        if self.config.get("host_server", True):
            # This instance is the server + host player
            from game.network.server import GameServer
            self.net_server = GameServer(port=port, max_players=max_p)
            if self.net_server.start():
                self.notifications.add(
                    f"Multiplayer server started on port {port}",
                    5.0, (100, 220, 100))
                # Spawn AI player if enabled
                if self.config.get("ai_player_enabled", False):
                    self._spawn_ai_player()
            else:
                self.notifications.add(
                    f"Failed to start server on port {port}",
                    5.0, (255, 100, 100))
                self.net_server = None
        else:
            # This instance connects to a remote server
            from game.network.client import GameClient
            host = self.config.get("server_host", "localhost")
            name = self.config.get("player_name", "Player2")
            self.net_client = GameClient()
            self.net_client.on_notification = lambda t, d, c: \
                self.notifications.add(t, d, c)
            if self.net_client.connect(host, port, name):
                self.notifications.add(
                    f"Connected to server at {host}:{port}",
                    5.0, (100, 220, 100))
            else:
                reason = self.net_client.reject_reason or self.net_client.status
                self.notifications.add(
                    f"Failed to connect: {reason}",
                    5.0, (255, 100, 100))
                self.net_client = None

    def _spawn_ai_player(self):
        """Spawn an AI companion player."""
        try:
            from game.network.ai_player import AIPlayer
            personality = self.config.get("ai_player_personality", "explorer")
            port = self.config.get("server_port", DEFAULT_PORT)
            ai = AIPlayer(
                name=f"AI-{personality.title()}",
                personality=personality,
                host="localhost",
                port=port,
            )
            if ai.connect():
                self._ai_player = ai
                # Set AI starting position near host player
                ai.x = self.player.x + random.uniform(-3, 3)
                ai.y = self.player.y + random.uniform(-3, 3)
                ai._explore_origin = (ai.x, ai.y)
                self.notifications.add(
                    f"AI companion '{ai.name}' ({personality}) joined!",
                    4.0, (180, 140, 255))
            else:
                self.notifications.add(
                    "Failed to spawn AI player.", 3.0, (255, 100, 100))
        except Exception as e:
            print(f"[NET] AI player error: {e}")
            import traceback
            traceback.print_exc()

    def _update_multiplayer(self, dt: float):
        """Process multiplayer network updates. Called from _update."""
        if self.net_server:
            # Host: process incoming messages from remote players
            for msg in self.net_server.get_pending_messages():
                self._handle_net_message(msg)

            # Broadcast state periodically
            self._net_state_timer += dt
            if self._net_state_timer >= self._net_state_interval:
                self._net_state_timer = 0.0
                self.net_server.broadcast_state(self)

            # Update remote player entities from server client data
            clients = self.net_server.get_clients()
            seen = set()
            for pid, client in clients.items():
                seen.add(pid)
                if pid not in self.remote_players:
                    idx = len(self.remote_players)
                    rp = RemotePlayer(pid, client.player_name, idx)
                    self.remote_players[pid] = rp
                rp = self.remote_players[pid]
                rp.update_from_network(
                    client.x, client.y, client.hp, client.max_hp,
                    client.level, client.facing, client.gait, client.is_ai)
                rp.name = client.player_name
                rp.update(dt)

            # Remove disconnected players
            for pid in list(self.remote_players.keys()):
                if pid not in seen:
                    del self.remote_players[pid]

        elif self.net_client:
            # Remote client: send our position, process incoming
            self.net_client.send_move(
                self.player.x, self.player.y,
                self.player.vx, self.player.vy,
                self.player.facing,
                getattr(self.player, 'current_gait', 'walk'))

            self.net_client.update(dt)

            for msg in self.net_client.get_pending_messages():
                self._handle_net_message(msg)

            # Update remote player entities from client data
            for rp_state in self.net_client.get_remote_players():
                pid = rp_state.player_id
                if pid not in self.remote_players:
                    idx = len(self.remote_players)
                    rp = RemotePlayer(pid, rp_state.name, idx)
                    self.remote_players[pid] = rp
                rp = self.remote_players[pid]
                rp.update_from_network(
                    rp_state.x, rp_state.y, rp_state.hp, rp_state.max_hp,
                    rp_state.level, rp_state.facing, rp_state.gait,
                    rp_state.is_ai)
                rp.name = rp_state.name
                rp.update(dt)

    def _handle_net_message(self, msg: dict):
        """Handle a network message in the game loop."""
        from game.network.protocol import MessageType
        msg_type = msg.get("type", "")
        data = msg.get("data", {})

        if msg_type == MessageType.PLAYER_JOIN:
            name = data.get("name", "Unknown")
            is_ai = data.get("is_ai", False)
            prefix = "[AI] " if is_ai else ""
            self.notifications.add(
                f"{prefix}{name} joined the game!", 4.0, (100, 220, 100))

        elif msg_type == MessageType.PLAYER_LEAVE:
            name = data.get("name", "Unknown")
            pid = data.get("player_id", "")
            self.notifications.add(
                f"{name} left the game.", 4.0, (220, 150, 100))
            self.remote_players.pop(pid, None)

        elif msg_type == MessageType.PLAYER_CHAT or msg_type == MessageType.CHAT_MESSAGE:
            name = data.get("name", "?")
            text = data.get("text", "")
            self._multiplayer_chat_log.append((name, text, time.time()))
            if len(self._multiplayer_chat_log) > 50:
                self._multiplayer_chat_log = self._multiplayer_chat_log[-50:]
            self.notifications.add(f"[{name}]: {text}", 5.0, (180, 220, 255))

        elif msg_type == MessageType.NOTIFICATION:
            text = data.get("text", "")
            duration = data.get("duration", 3.0)
            color = tuple(data.get("color", [220, 220, 230]))
            self.notifications.add(text, duration, color)

        elif msg_type == MessageType.GAME_EVENT:
            desc = data.get("description", "")
            if desc:
                self.notifications.add(desc, 4.0, (200, 200, 100))

    def _draw_remote_players(self):
        """Draw all remote players on the overworld."""
        tile_size = self.camera.tile_size if hasattr(self.camera, 'tile_size') else TILE_SIZE
        for rp in self.remote_players.values():
            rp.draw(self.screen, self.camera, tile_size)

    def _draw_multiplayer_status(self):
        """Draw multiplayer connection status indicator."""
        font = self.renderer.font_sm
        if self.net_server:
            count = self.net_server.client_count
            port = self.config.get("server_port", DEFAULT_PORT)
            text = f"HOST :{port} [{count} connected]"
            color = (100, 220, 100) if count > 0 else (180, 180, 100)
        elif self.net_client:
            text = f"ONLINE [{self.net_client.status}]"
            latency = self.net_client.latency_ms
            if latency > 0:
                text += f" {latency:.0f}ms"
            color = (100, 220, 100) if self.net_client.connected else (255, 100, 100)
        else:
            return

        surf = font.render(text, True, color)
        self.screen.blit(surf, (10, SCREEN_HEIGHT - 20))

    def _draw_chat_log(self):
        """Draw recent multiplayer chat messages."""
        if not self._multiplayer_chat_log:
            return
        font = self.renderer.font_sm
        now = time.time()
        # Show messages from last 15 seconds
        recent = [(n, t, ts) for n, t, ts in self._multiplayer_chat_log
                  if now - ts < 15.0]
        if not recent:
            return
        y = SCREEN_HEIGHT - 80
        for name, text, ts in recent[-5:]:
            age = now - ts
            alpha = max(50, int(255 * (1.0 - age / 15.0)))
            msg = f"[{name}]: {text}"
            if len(msg) > 60:
                msg = msg[:57] + "..."
            surf = font.render(msg, True, (180, 220, 255))
            surf.set_alpha(alpha)
            self.screen.blit(surf, (10, y))
            y -= 14

