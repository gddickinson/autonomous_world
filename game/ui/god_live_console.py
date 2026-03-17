"""Live Python Console for God Mode.

Provides a REPL that executes arbitrary Python code against the
live game state. Supports command history, output capture, and
convenience shortcuts for common god-mode operations.
"""

import io
import contextlib
import pygame
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT


class LivePythonConsole:
    """Execute arbitrary Python code against the live game state."""

    def __init__(self, game):
        self.game = game
        self.visible = False
        self.input_text = ""
        self.output_lines = []       # list of (kind, text)  kind: "input"|"output"|"error"
        self.history = []
        self.history_idx = -1
        self.cursor_pos = 0          # cursor within input_text
        self.scroll_offset = 0       # for scrolling output

        # Execution namespace -- gives access to everything
        self.namespace = {
            "game": game,
            "player": game.player,
            "settings": None,  # lazy
            "__builtins__": __builtins__,
            "reload": self._reload_module,
            "spawn": self._quick_spawn,
            "tp": self._quick_teleport,
            "gold": self._quick_gold,
            "heal": self._quick_heal,
            "kill_all": self._quick_kill_all,
            "speed": self._quick_speed,
            "help": self._show_help,
        }
        # Deferred bindings (set up when first used so init order doesn't matter)
        self._deferred_setup = False

    def _ensure_namespace(self):
        """Lazily bind deferred namespace entries."""
        if self._deferred_setup:
            return
        self._deferred_setup = True
        game = self.game
        try:
            self.namespace["world"] = game.world
        except AttributeError:
            pass
        try:
            self.namespace["npcs"] = game.world_mgr.npcs
        except AttributeError:
            pass
        try:
            self.namespace["creatures"] = game.world_mgr.creatures
        except AttributeError:
            pass
        try:
            self.namespace["sim"] = game.simulation
        except AttributeError:
            pass
        try:
            self.namespace["we"] = game.simulation.world_effects
        except AttributeError:
            pass
        try:
            self.namespace["gov"] = game.simulation.governance
        except AttributeError:
            pass
        try:
            self.namespace["plan"] = game.world.plan
        except AttributeError:
            pass
        try:
            import game.settings as _s
            self.namespace["settings"] = _s
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, code):
        """Execute Python code and capture output."""
        self._ensure_namespace()

        stdout_capture = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout_capture):
                # Try eval first (expression)
                try:
                    result = eval(code, self.namespace)
                    if result is not None:
                        print(repr(result))
                except SyntaxError:
                    # Fall back to exec (statement)
                    exec(code, self.namespace)

            output = stdout_capture.getvalue()
            if output:
                for line in output.strip().split("\n"):
                    self.output_lines.append(("output", line))
        except Exception as e:
            self.output_lines.append(("error", f"Error: {type(e).__name__}: {e}"))

        # Trim output history
        if len(self.output_lines) > 500:
            self.output_lines = self.output_lines[-500:]

    # ------------------------------------------------------------------
    # Convenience functions
    # ------------------------------------------------------------------

    def _reload_module(self, module_name):
        """Hot-reload a game module.  Usage: reload('game.settings')"""
        import importlib
        try:
            mod = importlib.import_module(module_name)
            importlib.reload(mod)
            self.output_lines.append(("output", f"Reloaded {module_name}"))
            return True
        except Exception as e:
            self.output_lines.append(("error", f"Reload failed: {e}"))
            return False

    def _quick_spawn(self, kind, x=None, y=None):
        """Spawn a creature at player position.  Usage: spawn('wolf')"""
        if x is None:
            x = self.game.player.x
        if y is None:
            y = self.game.player.y
        try:
            from game.core.creature import Creature
            c = Creature(kind, float(x), float(y))
            self.game.world_mgr.creatures.append(c)
            return f"Spawned {kind} at ({x:.0f}, {y:.0f})"
        except Exception as e:
            return f"Spawn failed: {e}"

    def _quick_teleport(self, x, y):
        """Teleport player.  Usage: tp(5000, 5000)"""
        self.game.player.x = float(x)
        self.game.player.y = float(y)
        return f"Teleported to ({x}, {y})"

    def _quick_gold(self, amount=1000):
        """Give gold.  Usage: gold(500)"""
        self.game.player.gold += amount
        return f"Gold: {self.game.player.gold}"

    def _quick_heal(self):
        """Heal player to full.  Usage: heal()"""
        self.game.player.hp = self.game.player.max_hp
        if hasattr(self.game.player, 'energy'):
            self.game.player.energy = getattr(self.game.player, 'max_energy', 100)
        return f"Healed to {self.game.player.hp} HP"

    def _quick_kill_all(self, radius=20):
        """Kill all creatures within radius.  Usage: kill_all(30)"""
        px, py = self.game.player.x, self.game.player.y
        count = 0
        for c in self.game.world_mgr.creatures:
            dx = c.x - px
            dy = c.y - py
            if dx * dx + dy * dy <= radius * radius:
                c.hp = 0
                c.alive = False
                count += 1
        return f"Killed {count} creatures within {radius} tiles"

    def _quick_speed(self, multiplier):
        """Set time speed.  Usage: speed(10)"""
        if hasattr(self.game.time_sys, 'speed'):
            self.game.time_sys.speed = float(multiplier)
        elif hasattr(self.game.time_sys, 'time_scale'):
            self.game.time_sys.time_scale = float(multiplier)
        return f"Time speed: {multiplier}x"

    def _show_help(self):
        """Show available shortcuts."""
        lines = [
            "=== Python Console Help ===",
            "Namespace objects:",
            "  game     - the Game object",
            "  world    - the ChunkedWorld",
            "  player   - the Player",
            "  npcs     - list of live NPCs",
            "  creatures- list of creatures",
            "  sim      - SimulationManager",
            "  we       - WorldEffects",
            "  gov      - GovernanceSystem",
            "  plan     - WorldPlan",
            "  settings - game settings module",
            "",
            "Shortcut functions:",
            "  reload('game.settings')  - hot-reload a module",
            "  spawn('wolf')            - spawn creature at player",
            "  spawn('bear', 100, 200)  - spawn at coordinates",
            "  tp(5000, 5000)           - teleport player",
            "  gold(500)                - give gold",
            "  heal()                   - heal player",
            "  kill_all(30)             - kill creatures in radius",
            "  speed(10)                - set time speed",
            "",
            "Any valid Python expression/statement works.",
            "  len(npcs)                - count NPCs",
            "  player.gold = 9999       - set gold directly",
            "  [n.name for n in npcs[:5]]  - list NPC names",
        ]
        for line in lines:
            print(line)

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def toggle(self):
        """Toggle visibility."""
        self.visible = not self.visible

    def handle_key(self, key, unicode_char, mods=0):
        """Handle keyboard input. Returns True if consumed."""
        if not self.visible:
            return False

        if key == pygame.K_RETURN:
            if self.input_text.strip():
                self.output_lines.append(("input", f">>> {self.input_text}"))
                self.history.append(self.input_text)
                self.execute(self.input_text)
                self.input_text = ""
                self.cursor_pos = 0
                self.history_idx = -1
                self.scroll_offset = 0
            return True

        elif key == pygame.K_BACKSPACE:
            if self.cursor_pos > 0:
                self.input_text = (self.input_text[:self.cursor_pos - 1]
                                   + self.input_text[self.cursor_pos:])
                self.cursor_pos -= 1
            return True

        elif key == pygame.K_DELETE:
            if self.cursor_pos < len(self.input_text):
                self.input_text = (self.input_text[:self.cursor_pos]
                                   + self.input_text[self.cursor_pos + 1:])
            return True

        elif key == pygame.K_HOME:
            self.cursor_pos = 0
            return True

        elif key == pygame.K_END:
            self.cursor_pos = len(self.input_text)
            return True

        elif key == pygame.K_LEFT:
            self.cursor_pos = max(0, self.cursor_pos - 1)
            return True

        elif key == pygame.K_RIGHT:
            self.cursor_pos = min(len(self.input_text), self.cursor_pos + 1)
            return True

        elif key == pygame.K_UP:
            if self.history:
                if self.history_idx == -1:
                    self.history_idx = len(self.history) - 1
                else:
                    self.history_idx = max(0, self.history_idx - 1)
                self.input_text = self.history[self.history_idx]
                self.cursor_pos = len(self.input_text)
            return True

        elif key == pygame.K_DOWN:
            if self.history and self.history_idx >= 0:
                self.history_idx += 1
                if self.history_idx >= len(self.history):
                    self.history_idx = -1
                    self.input_text = ""
                else:
                    self.input_text = self.history[self.history_idx]
                self.cursor_pos = len(self.input_text)
            return True

        elif key == pygame.K_PAGEUP:
            self.scroll_offset = min(
                len(self.output_lines), self.scroll_offset + 10)
            return True

        elif key == pygame.K_PAGEDOWN:
            self.scroll_offset = max(0, self.scroll_offset - 10)
            return True

        elif key == pygame.K_l and (mods & pygame.KMOD_CTRL):
            # Ctrl+L clears output
            self.output_lines.clear()
            self.scroll_offset = 0
            return True

        elif unicode_char and unicode_char.isprintable():
            self.input_text = (self.input_text[:self.cursor_pos]
                               + unicode_char
                               + self.input_text[self.cursor_pos:])
            self.cursor_pos += 1
            return True

        return True  # consume all keys when console is open

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, screen):
        """Draw the Python console overlay."""
        if not self.visible:
            return

        panel_w = SCREEN_WIDTH - 20
        panel_h = 300
        panel_x = 10
        panel_y = SCREEN_HEIGHT - panel_h - 10

        # Background
        surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        surf.fill((10, 10, 20, 240))
        screen.blit(surf, (panel_x, panel_y))
        pygame.draw.rect(screen, (60, 80, 120), (panel_x, panel_y, panel_w, panel_h), 1)

        font = pygame.font.SysFont("monospace", 12)

        # Title bar
        title_bg = pygame.Surface((panel_w, 18), pygame.SRCALPHA)
        title_bg.fill((20, 30, 50, 200))
        screen.blit(title_bg, (panel_x, panel_y))
        screen.blit(font.render("Python Console [~]  |  help() for shortcuts  |  Ctrl+L clear  |  PgUp/PgDn scroll",
                                True, (180, 200, 255)),
                    (panel_x + 5, panel_y + 3))

        # Output area
        output_y_start = panel_y + 20
        output_y_end = panel_y + panel_h - 22
        max_lines = (output_y_end - output_y_start) // 14

        # Apply scroll offset
        end_idx = len(self.output_lines) - self.scroll_offset
        start_idx = max(0, end_idx - max_lines)
        visible_lines = self.output_lines[start_idx:end_idx]

        y = output_y_start
        for kind, line in visible_lines:
            if kind == "input":
                color = (140, 180, 140)
            elif kind == "error":
                color = (255, 100, 100)
            else:
                color = (200, 200, 220)
            # Truncate long lines
            display = line[:120]
            screen.blit(font.render(display, True, color), (panel_x + 5, y))
            y += 14

        # Scroll indicator
        if self.scroll_offset > 0:
            ind = font.render(f"[scroll: {self.scroll_offset} lines up]", True, (120, 120, 160))
            screen.blit(ind, (panel_x + panel_w - ind.get_width() - 10, output_y_start))

        # Input line
        input_y = panel_y + panel_h - 20
        pygame.draw.rect(screen, (20, 20, 35), (panel_x + 2, input_y, panel_w - 4, 18))

        prompt = f">>> {self.input_text}"
        screen.blit(font.render(prompt, True, (100, 255, 100)), (panel_x + 5, input_y + 2))

        # Cursor blink
        import time
        if int(time.time() * 2) % 2 == 0:
            cursor_x = panel_x + 5 + font.size(f">>> {self.input_text[:self.cursor_pos]}")[0]
            pygame.draw.line(screen, (100, 255, 100),
                             (cursor_x, input_y + 2), (cursor_x, input_y + 14))
