"""
Menu system for Autonomous World.
Title screen, new game setup, options, and in-game pause menu.
"""

import sys
import pygame

from game.config import (
    GameConfig, CONFIG_OPTIONS, OPTIONS_TABS, NEW_GAME_KEYS,
    RESOLUTION_MAP,
)
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT, UI_HIGHLIGHT, WHITE, GRAY, YELLOW


class MenuSystem:
    """Handles all game menus (title, new game, options, pause)."""

    # Color palette
    BG = (10, 10, 20)
    TITLE_COLOR = UI_HIGHLIGHT
    TEXT = (220, 220, 230)
    TEXT_DIM = (140, 140, 155)
    TEXT_BRIGHT = (255, 255, 255)
    HIGHLIGHT_BG = (50, 65, 110)
    BOX_BG = (30, 30, 45)
    BOX_BORDER = (70, 70, 90)
    BOX_ACTIVE = (80, 100, 160)
    ACCENT_GREEN = (80, 200, 120)
    ACCENT_RED = (220, 80, 80)
    ACCENT_GOLD = (220, 200, 80)
    OVERLAY = (0, 0, 0, 140)

    def __init__(self, screen, clock, config: GameConfig):
        self.screen = screen
        self.clock = clock
        self.config = config
        self._init_fonts()

    def _init_fonts(self):
        self.font_title = pygame.font.SysFont("monospace", 42, bold=True)
        self.font_subtitle = pygame.font.SysFont("monospace", 20)
        self.font_lg = pygame.font.SysFont("monospace", 22)
        self.font_md = pygame.font.SysFont("monospace", 16)
        self.font_sm = pygame.font.SysFont("monospace", 13)

    # ================================================================
    # TITLE SCREEN
    # ================================================================

    def show_title(self):
        """Show the main title screen. Returns action string or None to quit.

        Returns:
            "new_game" - start a new game (config already updated)
            "continue" - load existing save
            None       - user wants to quit
        """
        selected = 0
        options = ["New Game", "Continue", "Options", "Quit"]

        while True:
            self.screen.fill(self.BG)

            # Title
            title = self.font_title.render("AUTONOMOUS WORLD", True, self.TITLE_COLOR)
            self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 140))

            # Subtitle
            sub = self.font_sm.render("A living medieval world", True, self.TEXT_DIM)
            self.screen.blit(sub, (SCREEN_WIDTH // 2 - sub.get_width() // 2, 190))

            # Menu options
            y = 280
            for i, label in enumerate(options):
                is_sel = i == selected
                bx = SCREEN_WIDTH // 2 - 160
                bw, bh = 320, 44

                bg = self.HIGHLIGHT_BG if is_sel else self.BOX_BG
                border = self.TEXT_BRIGHT if is_sel else self.BOX_BORDER

                pygame.draw.rect(self.screen, bg, (bx, y, bw, bh), border_radius=6)
                pygame.draw.rect(self.screen, border, (bx, y, bw, bh), 2, border_radius=6)

                color = self.TEXT_BRIGHT if is_sel else self.TEXT_DIM
                text = self.font_lg.render(label, True, color)
                self.screen.blit(text, (bx + bw // 2 - text.get_width() // 2,
                                        y + bh // 2 - text.get_height() // 2))
                y += bh + 12

            # Hint
            hint = self.font_sm.render("Up/Down to select, Enter to confirm", True, self.TEXT_DIM)
            self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, y + 20))

            # Version info
            ver = self.font_sm.render("v0.1 - Chunked World", True, (60, 60, 80))
            self.screen.blit(ver, (SCREEN_WIDTH - ver.get_width() - 10, SCREEN_HEIGHT - 20))

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        selected = (selected - 1) % len(options)
                    elif event.key == pygame.K_DOWN:
                        selected = (selected + 1) % len(options)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if selected == 0:  # New Game
                            result = self.show_new_game()
                            if result == "start":
                                return "new_game"
                            # else user pressed escape, stay on title
                        elif selected == 1:  # Continue
                            return "continue"
                        elif selected == 2:  # Options
                            self.show_options()
                        elif selected == 3:  # Quit
                            return None
                    elif event.key == pygame.K_ESCAPE:
                        return None

            self.clock.tick(30)

    # ================================================================
    # NEW GAME SETUP
    # ================================================================

    def show_new_game(self):
        """Configure new game settings. Returns "start" or "back"."""
        selected = 0
        keys = list(NEW_GAME_KEYS)
        # Add a "Start Game" button at the end
        start_idx = len(keys)

        while True:
            self.screen.fill(self.BG)

            # Header
            title = self.font_lg.render("NEW GAME SETUP", True, self.TITLE_COLOR)
            self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 60))

            # Draw options
            y = 130
            for i, key in enumerate(keys):
                is_sel = i == selected
                self._draw_option_row(y, key, is_sel)
                y += 46

            # History years: only show if world_gen_mode is simulated
            # (it's always in the list but we dim it if planned)
            # Already handled by drawing all keys

            # Start button
            y += 20
            is_sel = selected == start_idx
            bx = SCREEN_WIDTH // 2 - 120
            bw, bh = 240, 48
            bg = self.ACCENT_GREEN if is_sel else (40, 80, 50)
            border = self.TEXT_BRIGHT if is_sel else (60, 100, 65)
            pygame.draw.rect(self.screen, bg, (bx, y, bw, bh), border_radius=8)
            pygame.draw.rect(self.screen, border, (bx, y, bw, bh), 2, border_radius=8)
            start_text = self.font_lg.render("Start Game", True,
                                             self.TEXT_BRIGHT if is_sel else (120, 180, 130))
            self.screen.blit(start_text, (bx + bw // 2 - start_text.get_width() // 2,
                                          y + bh // 2 - start_text.get_height() // 2))

            # Hint
            hint_y = y + bh + 30
            hint = self.font_sm.render(
                "Up/Down: select   Left/Right: change   Enter: start   Esc: back",
                True, self.TEXT_DIM)
            self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, hint_y))

            # Description panel
            if selected < len(keys):
                self._draw_setting_description(hint_y + 30, keys[selected])

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        selected = (selected - 1) % (start_idx + 1)
                    elif event.key == pygame.K_DOWN:
                        selected = (selected + 1) % (start_idx + 1)
                    elif event.key == pygame.K_LEFT:
                        if selected < len(keys):
                            self.config.cycle_option(keys[selected], -1)
                            self._sync_world_dims()
                    elif event.key == pygame.K_RIGHT:
                        if selected < len(keys):
                            self.config.cycle_option(keys[selected], 1)
                            self._sync_world_dims()
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if selected == start_idx:
                            self.config.save()
                            return "start"
                    elif event.key == pygame.K_ESCAPE:
                        return "back"

            self.clock.tick(30)

    def _sync_world_dims(self):
        """Keep world_height in sync with world_width."""
        self.config["world_height"] = self.config["world_width"]

    # ================================================================
    # OPTIONS MENU
    # ================================================================

    def show_options(self):
        """Show the options menu with tabs. Saves on exit."""
        tab_names = list(OPTIONS_TABS.keys())
        current_tab = 0
        selected = 0

        while True:
            self.screen.fill(self.BG)

            # Header
            title = self.font_lg.render("OPTIONS", True, self.TITLE_COLOR)
            self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 30))

            # Tab bar
            tab_y = 70
            tab_x = 40
            for i, tab in enumerate(tab_names):
                is_cur = i == current_tab
                color = self.TITLE_COLOR if is_cur else self.TEXT_DIM
                text = self.font_md.render(tab, True, color)
                self.screen.blit(text, (tab_x, tab_y))
                if is_cur:
                    tw = text.get_width()
                    pygame.draw.line(self.screen, self.TITLE_COLOR,
                                     (tab_x, tab_y + 18), (tab_x + tw, tab_y + 18), 2)
                tab_x += text.get_width() + 30

            # Separator
            pygame.draw.line(self.screen, self.BOX_BORDER,
                             (30, tab_y + 24), (SCREEN_WIDTH - 30, tab_y + 24))

            # Options for current tab
            tab_keys = OPTIONS_TABS[tab_names[current_tab]]
            y = tab_y + 40
            for i, key in enumerate(tab_keys):
                is_sel = i == selected
                self._draw_option_row(y, key, is_sel)
                y += 46

            # Hint
            hint = self.font_sm.render(
                "Tab/Shift+Tab: switch tab   Up/Down: select   Left/Right: change   Esc: save & back",
                True, self.TEXT_DIM)
            self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2,
                                    SCREEN_HEIGHT - 40))

            # Description
            if selected < len(tab_keys):
                self._draw_setting_description(y + 20, tab_keys[selected])

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.config.save()
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    tab_keys_list = OPTIONS_TABS[tab_names[current_tab]]
                    if event.key == pygame.K_UP:
                        selected = (selected - 1) % max(1, len(tab_keys_list))
                    elif event.key == pygame.K_DOWN:
                        selected = (selected + 1) % max(1, len(tab_keys_list))
                    elif event.key == pygame.K_LEFT:
                        if selected < len(tab_keys_list):
                            self.config.cycle_option(tab_keys_list[selected], -1)
                    elif event.key == pygame.K_RIGHT:
                        if selected < len(tab_keys_list):
                            self.config.cycle_option(tab_keys_list[selected], 1)
                    elif event.key == pygame.K_TAB:
                        mods = pygame.key.get_mods()
                        if mods & pygame.KMOD_SHIFT:
                            current_tab = (current_tab - 1) % len(tab_names)
                        else:
                            current_tab = (current_tab + 1) % len(tab_names)
                        selected = 0
                    elif event.key == pygame.K_ESCAPE:
                        self.config.save()
                        return

            self.clock.tick(30)

    # ================================================================
    # IN-GAME PAUSE MENU
    # ================================================================

    def show_pause_menu(self):
        """Show in-game pause/escape menu.

        Returns:
            "resume"          - unpause and continue
            "options"         - open options (caller should call show_options after)
            "save"            - save game
            "load"            - load game
            "quit_to_menu"    - return to title screen
            "quit_to_desktop" - exit application
            None              - same as resume
        """
        selected = 0
        options = [
            ("Resume", "resume"),
            ("Options", "options"),
            ("Save Game", "save"),
            ("Load Game", "load"),
            ("Quit to Menu", "quit_to_menu"),
            ("Quit to Desktop", "quit_to_desktop"),
        ]

        while True:
            # Draw overlay
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill(self.OVERLAY)
            self.screen.blit(overlay, (0, 0))

            # Panel
            pw, ph = 360, 380
            px = SCREEN_WIDTH // 2 - pw // 2
            py = SCREEN_HEIGHT // 2 - ph // 2

            panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
            panel.fill((15, 15, 30, 230))
            self.screen.blit(panel, (px, py))
            pygame.draw.rect(self.screen, self.BOX_BORDER, (px, py, pw, ph), 2, border_radius=8)

            # Title
            title = self.font_lg.render("PAUSED", True, self.TITLE_COLOR)
            self.screen.blit(title, (px + pw // 2 - title.get_width() // 2, py + 20))

            # Options
            y = py + 65
            for i, (label, _action) in enumerate(options):
                is_sel = i == selected
                bx = px + 40
                bw, bh = pw - 80, 40

                bg = self.HIGHLIGHT_BG if is_sel else (25, 25, 40)
                border = self.TEXT_BRIGHT if is_sel else (50, 50, 65)
                pygame.draw.rect(self.screen, bg, (bx, y, bw, bh), border_radius=5)
                pygame.draw.rect(self.screen, border, (bx, y, bw, bh), 1, border_radius=5)

                color = self.TEXT_BRIGHT if is_sel else self.TEXT_DIM
                text = self.font_md.render(label, True, color)
                self.screen.blit(text, (bx + bw // 2 - text.get_width() // 2,
                                        y + bh // 2 - text.get_height() // 2))
                y += bh + 8

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit_to_desktop"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        selected = (selected - 1) % len(options)
                    elif event.key == pygame.K_DOWN:
                        selected = (selected + 1) % len(options)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        return options[selected][1]
                    elif event.key == pygame.K_ESCAPE:
                        return "resume"

            self.clock.tick(30)

    # ================================================================
    # HELPERS
    # ================================================================

    def _draw_option_row(self, y, key, is_selected):
        """Draw a single option row with name, current value, and arrows."""
        if key not in CONFIG_OPTIONS:
            return

        display_name, choices = CONFIG_OPTIONS[key]
        current_label = self.config.get_option_label(key)
        idx = self.config.get_option_index(key)
        n = len(choices)

        bx = SCREEN_WIDTH // 2 - 300
        bw = 600
        bh = 40

        # Dim history_years if not in simulated mode
        dimmed = (key == "history_years" and self.config["world_gen_mode"] != "simulated")

        if is_selected and not dimmed:
            bg = self.HIGHLIGHT_BG
            border = self.BOX_ACTIVE
        else:
            bg = self.BOX_BG
            border = self.BOX_BORDER

        pygame.draw.rect(self.screen, bg, (bx, y, bw, bh), border_radius=5)
        pygame.draw.rect(self.screen, border, (bx, y, bw, bh), 1, border_radius=5)

        # Label (left side)
        label_color = self.TEXT_DIM if dimmed else (self.TEXT_BRIGHT if is_selected else self.TEXT)
        label = self.font_md.render(display_name, True, label_color)
        self.screen.blit(label, (bx + 15, y + bh // 2 - label.get_height() // 2))

        # Value (right side)
        val_x = bx + bw - 15
        value_color = self.ACCENT_GOLD if is_selected and not dimmed else (
            self.TEXT_DIM if dimmed else self.TEXT)
        val_text = self.font_md.render(current_label, True, value_color)
        self.screen.blit(val_text, (val_x - val_text.get_width(), y + bh // 2 - val_text.get_height() // 2))

        # Arrow indicators
        if is_selected and not dimmed:
            arrow_color = self.TEXT_BRIGHT
            # Left arrow
            if n > 1:
                left_arrow = self.font_md.render("<", True, arrow_color)
                self.screen.blit(left_arrow, (val_x - val_text.get_width() - 20,
                                              y + bh // 2 - left_arrow.get_height() // 2))
                # Right arrow
                right_arrow = self.font_md.render(">", True, arrow_color)
                self.screen.blit(right_arrow, (val_x + 8,
                                               y + bh // 2 - right_arrow.get_height() // 2))

        # Position indicator dots
        if is_selected and not dimmed and n > 1:
            dot_y = y + bh - 6
            dot_total_w = n * 8
            dot_start = bx + bw // 2 + 80
            for d in range(n):
                dot_color = self.ACCENT_GOLD if d == idx else (60, 60, 80)
                pygame.draw.circle(self.screen, dot_color,
                                   (dot_start + d * 10, dot_y), 3)

    def _draw_setting_description(self, y, key):
        """Draw a description box for the currently selected setting."""
        descriptions = {
            "world_width": "Size of the generated world in tiles. Larger worlds have more settlements but take longer to generate.",
            "world_gen_mode": "Planned: Generates world layout algorithmically (fast). Simulated: Runs a historical simulation to place settlements organically (slow, more realistic).",
            "history_years": "How many years of history to simulate when using Simulated mode. More years = richer backstory but longer generation.",
            "player_mode": "Mortal: Normal gameplay with death. Ghost: Explore freely, pass through walls. God: Invincible, one-hit kills, see everything.",
            "spawn_location": "Mainland: Start in the populated world with NPCs and creatures. Test Island: Isolated sandbox with no NPCs.",
            "difficulty": "Affects creature spawn rates, damage, and economy. Easy: forgiving. Brutal: very challenging.",
            "screen_width": "Display resolution. Restart required for changes to take effect.",
            "default_view": "Starting camera view. Strategy (16px), Adventure (32px), or 3D. Can be changed in-game with V.",
            "show_fps": "Display frames-per-second counter on screen.",
            "tile_size": "Base tile size in pixels for the strategy view.",
            "time_speed": "Game time multiplier. Higher = faster day/night cycle and NPC actions.",
            "permadeath": "On: Death is permanent (become ghost). Off: Respawn at nearest settlement.",
            "combat_difficulty": "Multiplier on creature damage. 0.5x = easy, 2.0x = brutal.",
            "auto_save": "Automatically save the game at regular intervals.",
            "auto_save_interval": "Minutes between auto-saves.",
            "friendly_fire": "Allow player attacks to damage friendly NPCs.",
            "max_npcs_active": "Maximum NPCs simulated at once. Lower = better performance.",
            "npc_decision_interval": "Seconds between NPC AI decisions. Longer = less CPU usage.",
            "llm_enabled": "Enable LLM-powered NPC dialogue and decisions.",
            "llm_provider": "Which LLM service to use for NPC intelligence.",
            "view_radius_3d": "How many tiles to render in 3D mode. Larger = slower.",
            "starting_gold": "Amount of gold the player starts with.",
            "tax_rate_default": "Default tax rate for settlements.",
            "trade_frequency": "Days between foreign caravan arrivals at settlements.",
            "music_volume": "Background music volume level.",
            "sfx_volume": "Sound effects volume level.",
            "music_enabled": "Enable or disable background music.",
            "show_debug_info": "Show debug information overlay.",
            "show_npc_actions": "Show what NPCs are currently doing above their heads.",
            "show_settlement_stores": "Show settlement resource stores on the map.",
        }
        desc = descriptions.get(key, "")
        if not desc:
            return

        # Word wrap
        max_w = 500
        words = desc.split()
        lines = []
        line = ""
        for word in words:
            test = line + word + " "
            if self.font_sm.size(test)[0] > max_w:
                lines.append(line.strip())
                line = word + " "
            else:
                line = test
        if line.strip():
            lines.append(line.strip())

        bx = SCREEN_WIDTH // 2 - max_w // 2 - 10
        bh = len(lines) * 16 + 12
        bw = max_w + 20
        pygame.draw.rect(self.screen, (20, 20, 35), (bx, y, bw, bh), border_radius=4)
        pygame.draw.rect(self.screen, (50, 50, 70), (bx, y, bw, bh), 1, border_radius=4)

        for i, ln in enumerate(lines):
            text = self.font_sm.render(ln, True, self.TEXT_DIM)
            self.screen.blit(text, (bx + 10, y + 6 + i * 16))
