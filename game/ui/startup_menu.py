"""Startup menu shown before world generation.

Provides Continue, New Game, Load Saved World, Options, and Quit.
Returns a result dict describing what the caller should do next.
"""

import sys
import pygame
from game.config import (
    GameConfig, CONFIG_OPTIONS, OPTIONS_TABS, NEW_GAME_KEYS, RESOLUTION_MAP,
)
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT, UI_HIGHLIGHT

# Color palette (matches MenuSystem)
BG = (10, 10, 20)
TITLE_COLOR = UI_HIGHLIGHT
TEXT = (220, 220, 230)
TEXT_DIM = (140, 140, 155)
TEXT_BRIGHT = (255, 255, 255)
HIGHLIGHT_BG = (50, 65, 110)
BOX_BG = (30, 30, 45)
BOX_BORDER = (70, 70, 90)
ACCENT_GREEN = (80, 200, 120)
ACCENT_GOLD = (220, 200, 80)


def show_startup_menu(screen=None, clock=None) -> dict:
    """Show the main startup menu. Returns dict with action, save_path, config."""
    need_init = screen is None
    if need_init:
        pygame.init()
        pygame.display.set_caption("Autonomous World")
        screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        clock = pygame.time.Clock()
    config = GameConfig()
    fonts = {
        "title": pygame.font.SysFont("monospace", 42, bold=True),
        "subtitle": pygame.font.SysFont("monospace", 20),
        "lg": pygame.font.SysFont("monospace", 22),
        "md": pygame.font.SysFont("monospace", 16),
        "sm": pygame.font.SysFont("monospace", 13),
    }
    return _MainMenu(screen, clock, config, fonts).run()


class _MainMenu:
    """Drives the startup menu event loop."""

    def __init__(self, screen, clock, config, fonts):
        self.screen = screen
        self.clock = clock
        self.config = config
        self.fonts = fonts

    def _quit_result(self):
        return {"action": "quit", "save_path": None, "config": self.config}

    def run(self) -> dict:
        from game.data.world_save import get_last_played_path
        import os
        last_path = get_last_played_path()
        # Fall back to default world if no last-played save exists
        if not last_path:
            default_path = os.path.join("data", "worlds", "default_world.json")
            if os.path.exists(default_path):
                last_path = default_path
        items = []
        if last_path:
            items.append(("Continue", "continue"))
        items.append(("New Game", "new"))
        items.append(("Load Saved World", "load"))
        items.append(("Options", "options"))
        items.append(("Quit", "quit"))
        selected = 0

        while True:
            self.screen.fill(BG)
            self._draw_title()
            y = 260
            for i, (label, _) in enumerate(items):
                self._draw_button(y, label, i == selected)
                y += 56
            hint = self.fonts["sm"].render(
                "Up/Down to navigate, Enter to select", True, TEXT_DIM)
            self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, y + 20))
            ver = self.fonts["sm"].render("v0.2 - Chunked World", True, (60, 60, 80))
            self.screen.blit(ver, (SCREEN_WIDTH - ver.get_width() - 10, SCREEN_HEIGHT - 20))
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return self._quit_result()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        selected = (selected - 1) % len(items)
                    elif event.key == pygame.K_DOWN:
                        selected = (selected + 1) % len(items)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        r = self._handle(items[selected][1], last_path)
                        if r is not None:
                            return r
                    elif event.key == pygame.K_ESCAPE:
                        return self._quit_result()
            self.clock.tick(30)

    def _handle(self, action, last_path):
        if action == "continue":
            return {"action": "continue", "save_path": last_path, "config": self.config}
        elif action == "new":
            if self._show_new_game() == "start":
                return {"action": "new", "save_path": None, "config": self.config}
        elif action == "load":
            path = self._show_load_menu()
            if path:
                return {"action": "load", "save_path": path, "config": self.config}
        elif action == "options":
            self._show_options()
        elif action == "quit":
            return self._quit_result()
        return None

    # -- Drawing helpers --------------------------------------------------

    def _draw_title(self):
        t = self.fonts["title"].render("AUTONOMOUS WORLD", True, TITLE_COLOR)
        self.screen.blit(t, (SCREEN_WIDTH // 2 - t.get_width() // 2, 120))
        s = self.fonts["subtitle"].render("A living medieval world", True, TEXT_DIM)
        self.screen.blit(s, (SCREEN_WIDTH // 2 - s.get_width() // 2, 175))

    def _draw_button(self, y, label, is_sel):
        bx, bw, bh = SCREEN_WIDTH // 2 - 180, 360, 44
        bg = HIGHLIGHT_BG if is_sel else BOX_BG
        border = TEXT_BRIGHT if is_sel else BOX_BORDER
        pygame.draw.rect(self.screen, bg, (bx, y, bw, bh), border_radius=6)
        pygame.draw.rect(self.screen, border, (bx, y, bw, bh), 2, border_radius=6)
        txt = self.fonts["lg"].render(label, True, TEXT_BRIGHT if is_sel else TEXT_DIM)
        self.screen.blit(txt, (bx + bw // 2 - txt.get_width() // 2,
                               y + bh // 2 - txt.get_height() // 2))

    def _draw_option_row(self, y, key, is_sel):
        if key not in CONFIG_OPTIONS:
            return
        display_name, choices = CONFIG_OPTIONS[key]
        current_label = self.config.get_option_label(key)
        bx, bw, bh = SCREEN_WIDTH // 2 - 260, 520, 36
        bg = HIGHLIGHT_BG if is_sel else BOX_BG
        border = TEXT_BRIGHT if is_sel else BOX_BORDER
        pygame.draw.rect(self.screen, bg, (bx, y, bw, bh), border_radius=4)
        pygame.draw.rect(self.screen, border, (bx, y, bw, bh), 2, border_radius=4)
        lbl = self.fonts["md"].render(display_name, True, TEXT_BRIGHT if is_sel else TEXT)
        self.screen.blit(lbl, (bx + 14, y + bh // 2 - lbl.get_height() // 2))
        val_color = ACCENT_GOLD if is_sel else TEXT_DIM
        val = self.fonts["md"].render(current_label, True, val_color)
        vx = bx + bw - val.get_width() - 40
        self.screen.blit(val, (vx, y + bh // 2 - val.get_height() // 2))
        if is_sel:
            al = self.fonts["md"].render("<", True, ACCENT_GOLD)
            ar = self.fonts["md"].render(">", True, ACCENT_GOLD)
            self.screen.blit(al, (vx - 18, y + bh // 2 - al.get_height() // 2))
            self.screen.blit(ar, (bx + bw - 20, y + bh // 2 - ar.get_height() // 2))

    # -- New Game ---------------------------------------------------------

    def _show_new_game(self) -> str:
        keys = list(NEW_GAME_KEYS)
        start_idx = len(keys)
        selected = 0
        while True:
            self.screen.fill(BG)
            hdr = self.fonts["lg"].render("NEW GAME SETUP", True, TITLE_COLOR)
            self.screen.blit(hdr, (SCREEN_WIDTH // 2 - hdr.get_width() // 2, 60))
            y = 130
            for i, key in enumerate(keys):
                self._draw_option_row(y, key, i == selected)
                y += 46
            # Start button
            y += 20
            is_sel = (selected == start_idx)
            bx, bw, bh = SCREEN_WIDTH // 2 - 120, 240, 48
            bg = ACCENT_GREEN if is_sel else (40, 80, 50)
            border = TEXT_BRIGHT if is_sel else (60, 100, 65)
            pygame.draw.rect(self.screen, bg, (bx, y, bw, bh), border_radius=8)
            pygame.draw.rect(self.screen, border, (bx, y, bw, bh), 2, border_radius=8)
            st = self.fonts["lg"].render("Start Game", True,
                                         TEXT_BRIGHT if is_sel else (120, 180, 130))
            self.screen.blit(st, (bx + bw // 2 - st.get_width() // 2,
                                  y + bh // 2 - st.get_height() // 2))
            hint = self.fonts["sm"].render(
                "Left/Right to change, Enter to start, ESC to go back", True, TEXT_DIM)
            self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, y + 70))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "back"
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return "back"
                    elif event.key == pygame.K_UP:
                        selected = (selected - 1) % (start_idx + 1)
                    elif event.key == pygame.K_DOWN:
                        selected = (selected + 1) % (start_idx + 1)
                    elif event.key == pygame.K_LEFT and selected < start_idx:
                        self.config.cycle_option(keys[selected], -1)
                    elif event.key == pygame.K_RIGHT and selected < start_idx:
                        self.config.cycle_option(keys[selected], 1)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        if selected == start_idx:
                            self.config.save()
                            return "start"
            self.clock.tick(30)

    # -- Load Saved World -------------------------------------------------

    def _show_load_menu(self):
        from game.data.world_save import list_saved_worlds
        worlds = list_saved_worlds()
        if not worlds:
            self._show_message("No saved worlds found.", 2.0)
            return None
        selected, scroll = 0, 0
        max_vis = 8
        while True:
            self.screen.fill(BG)
            hdr = self.fonts["lg"].render("LOAD SAVED WORLD", True, TITLE_COLOR)
            self.screen.blit(hdr, (SCREEN_WIDTH // 2 - hdr.get_width() // 2, 40))
            y = 100
            for i, w in enumerate(worlds[scroll:scroll + max_vis]):
                self._draw_save_entry(y, w, scroll + i == selected)
                y += 72
            if scroll > 0:
                a = self.fonts["md"].render("^ More above ^", True, TEXT_DIM)
                self.screen.blit(a, (SCREEN_WIDTH // 2 - a.get_width() // 2, 85))
            if scroll + max_vis < len(worlds):
                a = self.fonts["md"].render("v More below v", True, TEXT_DIM)
                self.screen.blit(a, (SCREEN_WIDTH // 2 - a.get_width() // 2, y + 5))
            hint = self.fonts["sm"].render(
                "Up/Down to select, Enter to load, ESC to go back", True, TEXT_DIM)
            self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2,
                                    SCREEN_HEIGHT - 40))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return None
                    elif event.key == pygame.K_UP:
                        selected = max(0, selected - 1)
                        if selected < scroll:
                            scroll = selected
                    elif event.key == pygame.K_DOWN:
                        selected = min(len(worlds) - 1, selected + 1)
                        if selected >= scroll + max_vis:
                            scroll = selected - max_vis + 1
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        return worlds[selected]["path"]
            self.clock.tick(30)

    def _draw_save_entry(self, y, info, is_sel):
        bx, bw, bh = SCREEN_WIDTH // 2 - 280, 560, 64
        bg = HIGHLIGHT_BG if is_sel else BOX_BG
        border = TEXT_BRIGHT if is_sel else BOX_BORDER
        pygame.draw.rect(self.screen, bg, (bx, y, bw, bh), border_radius=6)
        pygame.draw.rect(self.screen, border, (bx, y, bw, bh), 2, border_radius=6)
        # Line 1: player info
        line1 = f"{info.get('player_name', '?')} - Lv.{info.get('player_level', 1)} {info.get('player_class', '')}"
        t1 = self.fonts["md"].render(line1, True, TEXT_BRIGHT if is_sel else TEXT)
        self.screen.blit(t1, (bx + 12, y + 8))
        # Line 2: world info
        pt = info.get("playtime_seconds", 0)
        h, m = int(pt // 3600), int((pt % 3600) // 60)
        ts = f"{h}h {m}m" if h > 0 else f"{m}m"
        line2 = (f"Seed: {info.get('seed', 0)}  Day {info.get('day', 1)} "
                 f"({info.get('season', '')})  {info.get('settlement_count', 0)} "
                 f"settlements  Played: {ts}")
        t2 = self.fonts["sm"].render(line2, True, TEXT_DIM)
        self.screen.blit(t2, (bx + 12, y + 32))
        # Date
        sd = info.get("save_date", "")[:10]
        if sd:
            dt = self.fonts["sm"].render(sd, True, TEXT_DIM)
            self.screen.blit(dt, (bx + bw - dt.get_width() - 12, y + 8))

    # -- Options ----------------------------------------------------------

    def _show_options(self):
        tab_names = list(OPTIONS_TABS.keys())
        current_tab, selected = 0, 0
        while True:
            self.screen.fill(BG)
            hdr = self.fonts["lg"].render("OPTIONS", True, TITLE_COLOR)
            self.screen.blit(hdr, (SCREEN_WIDTH // 2 - hdr.get_width() // 2, 30))
            # Tab bar
            tx = 40
            for i, tn in enumerate(tab_names):
                color = ACCENT_GOLD if i == current_tab else TEXT_DIM
                tt = self.fonts["md"].render(tn, True, color)
                self.screen.blit(tt, (tx, 70))
                if i == current_tab:
                    pygame.draw.line(self.screen, ACCENT_GOLD,
                                     (tx, 90), (tx + tt.get_width(), 90), 2)
                tx += tt.get_width() + 24
            # Options rows
            keys = OPTIONS_TABS[tab_names[current_tab]]
            max_vis = 12
            scroll = max(0, selected - max_vis + 1)
            y = 110
            for i, key in enumerate(keys[scroll:scroll + max_vis]):
                self._draw_option_row(y, key, scroll + i == selected)
                y += 42
            hint = self.fonts["sm"].render(
                "Tab/Shift+Tab: tabs  Up/Down: select  Left/Right: change  ESC: save & back",
                True, TEXT_DIM)
            self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2,
                                    SCREEN_HEIGHT - 30))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.config.save()
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.config.save()
                        return
                    elif event.key == pygame.K_TAB:
                        d = -1 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
                        current_tab = (current_tab + d) % len(tab_names)
                        selected = 0
                    elif event.key == pygame.K_UP:
                        selected = (selected - 1) % len(keys)
                    elif event.key == pygame.K_DOWN:
                        selected = (selected + 1) % len(keys)
                    elif event.key == pygame.K_LEFT and selected < len(keys):
                        self.config.cycle_option(keys[selected], -1)
                    elif event.key == pygame.K_RIGHT and selected < len(keys):
                        self.config.cycle_option(keys[selected], 1)
            self.clock.tick(30)

    def _show_message(self, text, duration=2.0):
        start = pygame.time.get_ticks()
        while (pygame.time.get_ticks() - start) < duration * 1000:
            self.screen.fill(BG)
            msg = self.fonts["lg"].render(text, True, TEXT)
            self.screen.blit(msg, (SCREEN_WIDTH // 2 - msg.get_width() // 2,
                                   SCREEN_HEIGHT // 2 - msg.get_height() // 2))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type in (pygame.QUIT, pygame.KEYDOWN):
                    return
            self.clock.tick(30)
