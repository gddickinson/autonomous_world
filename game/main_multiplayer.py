"""Multiplayer networking — TCP server/client, AI player.

Includes co-op quest sync, PvP arena, and player-to-player trade.
"""

from game.settings import *


class MultiplayerMixin:
    """Multiplayer methods for the Game class."""

    def _init_multiplayer(self):
        """Initialize multiplayer networking based on config."""
        # Multiplayer gameplay state (always init so attrs exist)
        self._trade_manager = None
        self._pvp_session = None
        self._pending_trade_request = False

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
                # Init trade manager (host-only)
                from game.network.player_trade import TradeManager
                self._trade_manager = TradeManager()
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

            # Tick PvP session
            self._mp_update_pvp(dt)

            # Cleanup expired trades
            if self._trade_manager:
                self._trade_manager.cleanup_expired()

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

        elif msg_type == MessageType.PLAYER_ATTACK:
            # PvP: if the attack targets a player, route to PvP session
            target_type = data.get("target_type", "")
            if target_type == "player" and self._pvp_session:
                damage = data.get("damage", 0)
                if self._pvp_session.active and damage > 0:
                    self._pvp_session.apply_attack_to_local(
                        damage, self.net_server)

        elif msg_type == MessageType.GAME_EVENT:
            event_type = data.get("event_type", "")
            # Route to specialized handlers by event prefix
            if event_type.startswith("quest_"):
                from game.network.coop_quests import handle_quest_event
                handle_quest_event(self, data)
            elif event_type.startswith("pvp_"):
                from game.network.pvp_arena import handle_pvp_event
                handle_pvp_event(self, data)
            elif event_type.startswith("trade_"):
                from game.network.player_trade import handle_trade_event
                handle_trade_event(self, data)
            else:
                desc = data.get("description", "")
                if desc:
                    self.notifications.add(desc, 4.0, (200, 200, 100))

    # ── Co-op quest helpers ───────────────────────────────────────

    def _mp_broadcast_quest_accept(self, quest):
        """Broadcast quest acceptance to all connected players."""
        if not self.net_server:
            return
        from game.network.coop_quests import broadcast_quest_accept
        broadcast_quest_accept(self.net_server, quest)

    def _mp_broadcast_quest_kill(self, quest, killer_name: str = ""):
        """Broadcast quest progress after a kill."""
        if not self.net_server:
            return
        from game.network.coop_quests import broadcast_quest_progress
        broadcast_quest_progress(self.net_server, quest, killer_name)

    def _mp_broadcast_quest_complete(self, quest):
        """Broadcast quest completion to all connected players."""
        if not self.net_server:
            return
        from game.network.coop_quests import broadcast_quest_complete
        broadcast_quest_complete(self.net_server, quest)

    # ── PvP arena helpers ─────────────────────────────────────────

    def _mp_start_pvp(self, remote_player_id: str):
        """Start a PvP arena match against a remote player (host only)."""
        if not self.net_server:
            return
        from game.network.pvp_arena import PvPArenaSession
        self._pvp_session = PvPArenaSession(self.player, remote_player_id)
        msg = self._pvp_session.start(self.net_server)
        self.notifications.add(msg, 5.0, (255, 200, 100))

    def _mp_pvp_attack(self, damage: int):
        """Host attacks the remote player in PvP."""
        if self._pvp_session and self._pvp_session.active and self.net_server:
            self._pvp_session.apply_attack_to_remote(damage, self.net_server)

    def _mp_update_pvp(self, dt: float):
        """Tick the PvP session. Called from _update_multiplayer."""
        if self._pvp_session and self._pvp_session.active and self.net_server:
            result = self._pvp_session.update(dt, self.net_server)
            if result:
                self.notifications.add(result, 6.0, (255, 220, 100))

    # ── Trade helpers ─────────────────────────────────────────────

    def _mp_request_trade(self, remote_player_id: str):
        """Host initiates a trade with a remote player."""
        if not self._trade_manager or not self.net_server:
            return
        self._trade_manager.request_trade(
            "host", remote_player_id, self.net_server, self.player.name)
        self.notifications.add(
            "Trade request sent!", 3.0, (255, 220, 100))

    def _mp_offer_trade_items(self, items: list):
        """Host updates their trade offer. items = [(name, count), ...]"""
        if not self._trade_manager or not self.net_server:
            return
        self._trade_manager.set_offer("host", items, self.net_server)

    def _mp_confirm_trade(self):
        """Host confirms the trade."""
        if not self._trade_manager or not self.net_server:
            return
        result = self._trade_manager.confirm_trade(
            "host", self.net_server, self)
        if result:
            self.notifications.add(result, 5.0, (100, 255, 100))

    def _mp_cancel_trade(self):
        """Host cancels the active trade."""
        if not self._trade_manager or not self.net_server:
            return
        self._trade_manager.cancel_trade("host", self.net_server)

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

