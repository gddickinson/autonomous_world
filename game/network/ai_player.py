"""
AI-controlled remote player.
Implements the same protocol as a human remote player but with
autonomous behaviors and a command interface.

Can be used standalone or controlled by a Claude Code session.
"""

import math
import random
import time
import threading
from typing import Optional

from game.network.client import GameClient


class Personality:
    """Defines AI player behavior tendencies."""

    PRESETS = {
        "explorer": {
            "name": "Explorer",
            "explore_weight": 0.6,
            "fight_weight": 0.1,
            "trade_weight": 0.1,
            "social_weight": 0.2,
            "wander_radius": 60,
            "courage": 0.4,
            "chattiness": 0.3,
        },
        "warrior": {
            "name": "Warrior",
            "explore_weight": 0.2,
            "fight_weight": 0.5,
            "trade_weight": 0.05,
            "social_weight": 0.25,
            "wander_radius": 30,
            "courage": 0.9,
            "chattiness": 0.4,
        },
        "trader": {
            "name": "Trader",
            "explore_weight": 0.15,
            "fight_weight": 0.05,
            "trade_weight": 0.5,
            "social_weight": 0.3,
            "wander_radius": 40,
            "courage": 0.2,
            "chattiness": 0.6,
        },
        "socialite": {
            "name": "Socialite",
            "explore_weight": 0.1,
            "fight_weight": 0.05,
            "trade_weight": 0.15,
            "social_weight": 0.7,
            "wander_radius": 20,
            "courage": 0.3,
            "chattiness": 0.8,
        },
    }

    def __init__(self, preset: str = "explorer"):
        data = self.PRESETS.get(preset, self.PRESETS["explorer"])
        self.name = data["name"]
        self.explore_weight = data["explore_weight"]
        self.fight_weight = data["fight_weight"]
        self.trade_weight = data["trade_weight"]
        self.social_weight = data["social_weight"]
        self.wander_radius = data["wander_radius"]
        self.courage = data["courage"]
        self.chattiness = data["chattiness"]


class AIPlayer:
    """AI-controlled player that connects to a game server.

    Autonomous behaviors:
    - Explore: wander the world, discover new areas
    - Fight: engage nearby hostile creatures
    - Trade: interact with merchant NPCs
    - Social: chat with NPCs and other players

    Can also receive text commands from the host player via chat
    or from a Claude Code session via the command interface.

    Usage:
        ai = AIPlayer("AI-Explorer", personality="explorer")
        ai.connect("localhost", 7777)
        # The AI runs autonomously in a background thread.
        # Send commands:
        ai.execute_command("goto 100 200")
        ai.execute_command("say Hello everyone!")
        ai.execute_command("fight")
        # Stop:
        ai.stop()
    """

    # Chat messages the AI can say based on personality
    EXPLORE_CHATS = [
        "Found an interesting area over here!",
        "I'm going to explore to the east.",
        "What's beyond those mountains?",
        "This forest looks promising.",
        "I see something interesting ahead.",
    ]
    FIGHT_CHATS = [
        "Watch out, hostile creature nearby!",
        "I'll take care of this one.",
        "Engaging enemy!",
        "Need backup here!",
        "Got a kill!",
    ]
    SOCIAL_CHATS = [
        "Hey, how's it going?",
        "Nice weather today.",
        "Seen anything interesting?",
        "Want to explore together?",
        "This is a great settlement.",
    ]
    IDLE_CHATS = [
        "Taking a breather.",
        "Looking around...",
        "Hmm, what to do next?",
    ]

    def __init__(self, name: str = "AI-Player",
                 personality: str = "explorer",
                 host: str = "localhost", port: int = 7777):
        self.name = name
        self.personality = Personality(personality)
        self.host = host
        self.port = port

        self.client = GameClient()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # AI state
        self.x = 0.0
        self.y = 0.0
        self.target_x = 0.0
        self.target_y = 0.0
        self.speed = 3.5
        self.state = "idle"  # idle, exploring, fighting, socializing, moving
        self._state_timer = 0.0
        self._chat_cooldown = 0.0
        self._decision_timer = 0.0
        self._command_queue: list = []
        self._cmd_lock = threading.Lock()

        # World knowledge (from server updates)
        self._known_npcs: list = []
        self._known_players: dict = {}
        self._known_events: list = []

        # Exploration targets
        self._explore_origin = (0.0, 0.0)
        self._visited_areas: set = set()  # (grid_x, grid_y) in 10-tile chunks

    @property
    def connected(self) -> bool:
        return self.client.connected

    def connect(self, host: str = None, port: int = None) -> bool:
        """Connect to the game server and start the AI loop.

        Returns:
            True if connected successfully.
        """
        h = host or self.host
        p = port or self.port
        if self.client.connect(h, p, self.name, is_ai=True):
            self.x = 0.0
            self.y = 0.0
            self._explore_origin = (self.x, self.y)
            self._running = True
            self._thread = threading.Thread(
                target=self._ai_loop, daemon=True, name=f"AIPlayer-{self.name}")
            self._thread.start()
            return True
        return False

    def stop(self):
        """Stop the AI and disconnect."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self.client.disconnect()

    def execute_command(self, command: str):
        """Queue a command for the AI to execute.

        Commands:
            goto X Y       - Move to position (X, Y)
            say TEXT       - Send a chat message
            fight          - Enter combat mode
            explore        - Enter exploration mode
            trade          - Enter trading mode
            follow         - Follow the host player
            stop           - Stop current action, go idle
            status         - Report current status via chat
            personality P  - Switch personality preset
        """
        with self._cmd_lock:
            self._command_queue.append(command.strip())

    def _ai_loop(self):
        """Main AI behavior loop. Runs in background thread."""
        dt = 0.1  # 10 Hz tick rate
        try:
            while self._running and self.client.connected:
                loop_start = time.time()

                # Process server messages
                for msg in self.client.get_pending_messages():
                    self._handle_server_message(msg)

                # Process queued commands
                self._process_commands()

                # Update client interpolation
                self.client.update(dt)

                # AI decision making
                self._decision_timer -= dt
                if self._decision_timer <= 0:
                    self._make_decision()
                    self._decision_timer = 2.0 + random.uniform(0, 2.0)

                # Execute current behavior
                self._execute_behavior(dt)

                # Send position update
                facing = self._calc_facing()
                self.client.send_move(
                    self.x, self.y, 0, 0, facing,
                    "walk" if self.state != "fighting" else "run")

                # Chat cooldown
                if self._chat_cooldown > 0:
                    self._chat_cooldown -= dt

                # State timer
                if self._state_timer > 0:
                    self._state_timer -= dt

                # Ping periodically
                if random.random() < 0.01:
                    self.client.send_ping()

                # Sleep to maintain tick rate
                elapsed = time.time() - loop_start
                sleep_time = max(0.01, dt - elapsed)
                time.sleep(sleep_time)

        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            self._running = False

    def _handle_server_message(self, msg: dict):
        """Process a message from the server."""
        msg_type = msg.get("type", "")
        data = msg.get("data", {})

        if msg_type == MessageType.NPC_UPDATE:
            self._known_npcs = data.get("npcs", [])

        elif msg_type == MessageType.CHAT_MESSAGE:
            # Check if it's a command from the host
            name = data.get("name", "")
            text = data.get("text", "")
            pid = data.get("player_id", "")
            if pid == "host" and text.startswith(f"@{self.name} "):
                cmd = text[len(f"@{self.name} "):]
                self.execute_command(cmd)

        elif msg_type == MessageType.GAME_EVENT:
            self._known_events.append(data)
            if len(self._known_events) > 20:
                self._known_events = self._known_events[-20:]

        elif msg_type == MessageType.NOTIFICATION:
            pass  # AI notes notifications but doesn't display them

    def _process_commands(self):
        """Process queued commands."""
        with self._cmd_lock:
            commands = self._command_queue
            self._command_queue = []

        for cmd in commands:
            parts = cmd.split(None, 1)
            if not parts:
                continue
            action = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if action == "goto":
                try:
                    coords = arg.split()
                    self.target_x = float(coords[0])
                    self.target_y = float(coords[1])
                    self.state = "moving"
                    self._state_timer = 60.0
                    self.client.send_chat(
                        f"Moving to ({self.target_x:.0f}, {self.target_y:.0f})")
                except (ValueError, IndexError):
                    self.client.send_chat("Usage: goto X Y")

            elif action == "say":
                if arg:
                    self.client.send_chat(arg)

            elif action == "fight":
                self.state = "fighting"
                self._state_timer = 30.0
                self.client.send_chat("Entering combat mode!")

            elif action == "explore":
                self.state = "exploring"
                self._state_timer = 60.0
                self._pick_explore_target()
                self.client.send_chat("Going exploring!")

            elif action == "trade":
                self.state = "socializing"
                self._state_timer = 30.0
                self.client.send_chat("Looking for traders...")

            elif action == "follow":
                self.state = "following"
                self._state_timer = 120.0
                self.client.send_chat("Following the host player.")

            elif action == "stop":
                self.state = "idle"
                self._state_timer = 0
                self.target_x = self.x
                self.target_y = self.y
                self.client.send_chat("Stopping.")

            elif action == "status":
                latency = f"{self.client.latency_ms:.0f}ms"
                self.client.send_chat(
                    f"Status: {self.state} at ({self.x:.0f},{self.y:.0f}) "
                    f"Ping: {latency}")

            elif action == "personality":
                if arg in Personality.PRESETS:
                    self.personality = Personality(arg)
                    self.client.send_chat(
                        f"Personality set to: {self.personality.name}")
                else:
                    presets = ", ".join(Personality.PRESETS.keys())
                    self.client.send_chat(f"Available: {presets}")

    def _make_decision(self):
        """Choose next behavior based on personality and situation."""
        if self.state == "moving" and self._state_timer > 0:
            return  # don't override explicit movement
        if self.state == "following":
            return  # don't override follow mode

        # Roll against personality weights
        roll = random.random()
        p = self.personality
        if roll < p.explore_weight:
            if self.state != "exploring":
                self.state = "exploring"
                self._pick_explore_target()
                self._state_timer = 30.0 + random.uniform(0, 30)
        elif roll < p.explore_weight + p.fight_weight:
            self.state = "fighting"
            self._state_timer = 15.0 + random.uniform(0, 15)
        elif roll < p.explore_weight + p.fight_weight + p.social_weight:
            self.state = "socializing"
            self._state_timer = 10.0 + random.uniform(0, 10)
        else:
            self.state = "idle"
            self._state_timer = 5.0 + random.uniform(0, 5)

        # Occasional chat
        if (self._chat_cooldown <= 0 and
                random.random() < self.personality.chattiness * 0.1):
            self._say_something()
            self._chat_cooldown = 15.0 + random.uniform(0, 15)

    def _execute_behavior(self, dt: float):
        """Execute the current behavior state."""
        if self.state == "exploring":
            self._move_toward_target(dt)
            # Pick new target when close
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            if dx * dx + dy * dy < 4:
                self._pick_explore_target()

        elif self.state == "moving":
            self._move_toward_target(dt)
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            if dx * dx + dy * dy < 4:
                self.state = "idle"
                self.client.send_chat("Arrived at destination.")

        elif self.state == "following":
            # Follow host player
            for rp in self.client.get_remote_players():
                if rp.player_id == "host" or rp.name == "Player":
                    self.target_x = rp.x + random.uniform(-2, 2)
                    self.target_y = rp.y + random.uniform(-2, 2)
                    break
            # Also check world state for host position
            self._move_toward_target(dt)

        elif self.state == "fighting":
            # Move toward nearest known NPC/creature that could be hostile
            # (simplified - real combat would require server-side validation)
            if self._known_npcs:
                nearest = min(self._known_npcs,
                              key=lambda n: self._dist_to(n["x"], n["y"]))
                if self._dist_to(nearest["x"], nearest["y"]) < 2:
                    # Attack
                    self.client.send_attack(
                        "npc", nearest.get("name", ""),
                        nearest["x"], nearest["y"])
                else:
                    self.target_x = nearest["x"]
                    self.target_y = nearest["y"]
                    self._move_toward_target(dt)
            else:
                # No targets, wander
                self.state = "exploring"
                self._pick_explore_target()

        elif self.state == "socializing":
            # Move toward nearest NPC
            if self._known_npcs:
                nearest = min(self._known_npcs,
                              key=lambda n: self._dist_to(n["x"], n["y"]))
                dist = self._dist_to(nearest["x"], nearest["y"])
                if dist < 2:
                    # Interact
                    if self._chat_cooldown <= 0:
                        npc_name = nearest.get("name", "someone")
                        self.client.send_chat(
                            f"*talks with {npc_name}*")
                        self._chat_cooldown = 10.0
                else:
                    self.target_x = nearest["x"]
                    self.target_y = nearest["y"]
                    self._move_toward_target(dt)

        elif self.state == "idle":
            # Small random movements
            if random.random() < 0.02:
                self.target_x = self.x + random.uniform(-5, 5)
                self.target_y = self.y + random.uniform(-5, 5)
                self._move_toward_target(dt)

    def _move_toward_target(self, dt: float):
        """Move toward the current target position."""
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 0.1:
            return
        nx = dx / dist
        ny = dy / dist
        move_speed = self.speed * dt
        if move_speed > dist:
            self.x = self.target_x
            self.y = self.target_y
        else:
            self.x += nx * move_speed
            self.y += ny * move_speed

        # Track visited areas
        grid_x = int(self.x) // 10
        grid_y = int(self.y) // 10
        self._visited_areas.add((grid_x, grid_y))

    def _pick_explore_target(self):
        """Choose a new exploration target."""
        r = self.personality.wander_radius
        for _ in range(10):
            tx = self._explore_origin[0] + random.uniform(-r, r)
            ty = self._explore_origin[1] + random.uniform(-r, r)
            grid_x = int(tx) // 10
            grid_y = int(ty) // 10
            if (grid_x, grid_y) not in self._visited_areas:
                self.target_x = tx
                self.target_y = ty
                return
        # All nearby areas visited, expand origin
        self._explore_origin = (
            self._explore_origin[0] + random.uniform(-r / 2, r / 2),
            self._explore_origin[1] + random.uniform(-r / 2, r / 2),
        )
        self.target_x = self._explore_origin[0] + random.uniform(-r, r)
        self.target_y = self._explore_origin[1] + random.uniform(-r, r)

    def _calc_facing(self) -> tuple:
        """Calculate facing direction from current movement."""
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 0.1:
            return (0, 1)
        return (dx / dist, dy / dist)

    def _dist_to(self, x: float, y: float) -> float:
        dx = self.x - x
        dy = self.y - y
        return math.sqrt(dx * dx + dy * dy)

    def _say_something(self):
        """Say a contextual chat message."""
        if self.state == "exploring":
            msg = random.choice(self.EXPLORE_CHATS)
        elif self.state == "fighting":
            msg = random.choice(self.FIGHT_CHATS)
        elif self.state == "socializing":
            msg = random.choice(self.SOCIAL_CHATS)
        else:
            msg = random.choice(self.IDLE_CHATS)
        self.client.send_chat(msg)


def run_ai_player(name: str = "AI-Explorer", personality: str = "explorer",
                  host: str = "localhost", port: int = 7777):
    """Run an AI player as a standalone process.

    This can be called from the command line or from a Claude Code session.

    Args:
        name: Display name for the AI player.
        personality: One of "explorer", "warrior", "trader", "socialite".
        host: Server address.
        port: Server port.
    """
    ai = AIPlayer(name, personality, host, port)
    if not ai.connect():
        print(f"Failed to connect to {host}:{port}")
        return

    print(f"AI player '{name}' ({personality}) connected to {host}:{port}")
    print("Commands: goto X Y | say TEXT | fight | explore | trade | "
          "follow | stop | status | quit")

    try:
        while ai.connected:
            try:
                cmd = input("> ").strip()
            except EOFError:
                break
            if cmd.lower() == "quit":
                break
            if cmd:
                ai.execute_command(cmd)
    except KeyboardInterrupt:
        pass
    finally:
        ai.stop()
        print("AI player stopped.")


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "AI-Explorer"
    personality = sys.argv[2] if len(sys.argv) > 2 else "explorer"
    host = sys.argv[3] if len(sys.argv) > 3 else "localhost"
    port = int(sys.argv[4]) if len(sys.argv) > 4 else 7777
    run_ai_player(name, personality, host, port)
