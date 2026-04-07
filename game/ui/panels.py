"""UI system: HUD, dialogs, text input, inventory, quest log, character sheet, menus."""

import pygame
from typing import List, Optional, Tuple
from game.settings import *
from game.core.player import Player
from game.core.npc import NPC
from game.core.items import Item
from game.systems.quests import Quest
from game.systems import TimeSystem, Notification
from game.systems.chronicles import ChronicleSystem, CATEGORY_COLORS


class UI:
    """Complete UI system for the game."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_sm = pygame.font.SysFont("monospace", 13)
        self.font_md = pygame.font.SysFont("monospace", 16)
        self.font_lg = pygame.font.SysFont("monospace", 22)
        self.font_xl = pygame.font.SysFont("monospace", 36)
        self.font_title = pygame.font.SysFont("monospace", 48, bold=True)

        # UI state
        self.show_inventory = False
        self.show_quest_log = False
        self.show_character = False  # character sheet
        self.show_planet_view = False  # 3D globe view
        self.show_world_map = False   # Full world map view
        self.show_chronicle = False   # Historical chronicle view
        self.show_quest_tracker = True  # HUD quest tracker
        self.dialog_active = False
        self.shop_active = False
        self.paused = False

        # Chronicle state
        self.chronicle_scroll = 0

        # Inventory category tabs
        self.inv_category = 0  # 0=All, 1=Weapons, 2=Armor, 3=Consumables, 4=Materials, 5=Quest, 6=Magic

        # Planet view
        from game.ui.planet_view import PlanetView
        self.planet_view = PlanetView()

        # World map view
        from game.ui.world_map import WorldMapView
        self.world_map_view = WorldMapView()

        # Dialog state
        self.dialog_npc: Optional[NPC] = None
        self.dialog_key = "greeting"
        self.dialog_scroll = 0
        self.selected_response = 0

        # Free-text input
        self.text_input_active = False
        self.text_input_buffer = ""
        self.text_input_cursor_blink = 0.0
        self.llm_response_text = ""       # LLM reply to player's typed message
        self.llm_waiting = False           # waiting for LLM response

        # Shop state
        self.shop_npc: Optional[NPC] = None
        self.shop_selected = 0
        self._shop_sell_mode = False

        # Gift state
        self.gift_active = False
        self.gift_npc: Optional[NPC] = None
        self.gift_selected = 0

        # Inventory state
        self.inv_selected = 0

        # Smooth bar lerp state (for animated HP/Energy transitions)
        self._hp_display = -1.0       # -1 = uninitialised (copy from player on first frame)
        self._energy_display = -1.0
        self._bar_lerp_speed = 8.0    # units per second; fast enough to feel responsive

        # Ghost bar state: tracks "lost HP" that fades after damage
        self._hp_ghost = -1.0         # ghost bar tracks the old HP before damage
        self._hp_ghost_timer = 0.0    # how long ghost bar has been showing
        self._energy_ghost = -1.0
        self._energy_ghost_timer = 0.0

        # Panel slide-in animation
        self._panel_slide_progress = 1.0  # 0 = offscreen, 1 = fully visible
        self._panel_slide_active = False
        self._last_panel_state = False

        # Dawn/dusk color flash overlay
        self._time_flash_alpha = 0.0
        self._time_flash_color = (0, 0, 0)
        self._last_time_phase = ""

        # Building enter/exit fade
        self._building_fade_alpha = 0.0
        self._building_fade_direction = 0  # +1 = fading in, -1 = fading out
        self._was_indoor = False

    @property
    def any_panel_open(self) -> bool:
        return (self.show_inventory or self.show_quest_log or self.show_character
                or self.dialog_active or self.shop_active or self.paused
                or self.text_input_active or self.show_planet_view
                or self.show_world_map or self.show_chronicle
                or self.gift_active)

    def close_all(self):
        self.show_inventory = False
        self.show_quest_log = False
        self.show_character = False
        self.show_planet_view = False
        self.show_world_map = False
        self.show_chronicle = False
        self.dialog_active = False
        self.shop_active = False
        self.gift_active = False
        self.gift_npc = None
        self.paused = False
        self.text_input_active = False
        self.llm_response_text = ""
        self.llm_waiting = False

    # Panel title-bar color themes
    _PANEL_THEMES = {
        "character":  (60, 40, 90),    # deep purple — character sheet
        "inventory":  (30, 55, 80),    # dark blue — inventory
        "quest":      (70, 50, 20),    # dark gold — quest log
        "chronicle":  (50, 35, 15),    # dark amber — chronicle
        "shop":       (20, 55, 35),    # dark green — shop/barter
        "dialog":     (25, 35, 60),    # dark blue — dialog
        "default":    (30, 30, 45),    # dark slate — fallback
    }

    def _draw_panel(self, x: int, y: int, w: int, h: int, title: str = "",
                    theme: str = "default"):
        """Draw a styled panel with decorative border and themed title bar."""
        # Main background — slightly parchment-tinted dark
        panel = pygame.Surface((w, h), pygame.SRCALPHA)
        panel.fill((18, 18, 28, 225))
        # Subtle parchment texture: dither-like lighter rows
        for row in range(0, h, 8):
            s = pygame.Surface((w, 1), pygame.SRCALPHA)
            s.fill((255, 240, 200, 8))
            panel.blit(s, (0, row))
        self.screen.blit(panel, (x, y))

        # Outer border (double-line effect)
        outer_color = (100, 100, 120)
        inner_color = (60, 65, 80)
        pygame.draw.rect(self.screen, outer_color, (x, y, w, h), 2)
        pygame.draw.rect(self.screen, inner_color, (x + 3, y + 3, w - 6, h - 6), 1)

        # Corner accent squares
        corner_size = 5
        corner_color = (130, 130, 150)
        for cx2, cy2 in [(x, y), (x + w - corner_size, y),
                         (x, y + h - corner_size), (x + w - corner_size, y + h - corner_size)]:
            pygame.draw.rect(self.screen, corner_color, (cx2, cy2, corner_size, corner_size))

        if title:
            # Colored title bar
            bar_color = self._PANEL_THEMES.get(theme, self._PANEL_THEMES["default"])
            bar_h = 30
            bar_surf = pygame.Surface((w - 8, bar_h), pygame.SRCALPHA)
            bar_surf.fill((*bar_color, 230))
            self.screen.blit(bar_surf, (x + 4, y + 4))
            # Title text in bold
            title_surf = self.font_lg.render(title, True, UI_HIGHLIGHT)
            self.screen.blit(title_surf, (x + 12, y + 6))
            # Separator line below title bar
            pygame.draw.line(self.screen, outer_color, (x + 4, y + 34), (x + w - 4, y + 34))
            pygame.draw.line(self.screen, inner_color, (x + 4, y + 35), (x + w - 4, y + 35))

    def _wrap_text(self, text: str, max_width: int, font) -> List[str]:
        """Word-wrap text to fit width."""
        lines = []
        for paragraph in text.split("\n"):
            words = paragraph.split()
            line = ""
            for word in words:
                test = line + word + " "
                if font.size(test)[0] > max_width:
                    if line:
                        lines.append(line.rstrip())
                    line = word + " "
                else:
                    line = test
            if line:
                lines.append(line.rstrip())
        return lines or [""]

    # ================================================================
    # HUD
    # ================================================================

    def draw_hud(self, player: Player, time_sys: TimeSystem, dt: float = 0.016):
        """Draw the heads-up display."""
        # -- Smooth lerp for HP and Energy bars --
        if self._hp_display < 0:
            self._hp_display = float(player.hp)
            self._hp_ghost = float(player.hp)
        if self._energy_display < 0:
            self._energy_display = float(player.energy)
            self._energy_ghost = float(player.energy)

        # Lerp toward actual value (fast enough to track but visually smooth)
        lerp_k = min(1.0, self._bar_lerp_speed * dt)
        self._hp_display += (player.hp - self._hp_display) * lerp_k
        self._energy_display += (player.energy - self._energy_display) * lerp_k

        # Ghost bar management: when HP drops, ghost stays high, then fades
        if player.hp < self._hp_ghost - 0.5:
            # HP just dropped — start ghost fade timer
            self._hp_ghost_timer = 0.3  # show ghost for 0.3s before fading
        if self._hp_ghost_timer > 0:
            self._hp_ghost_timer -= dt
        else:
            # Fade ghost toward current HP
            ghost_k = min(1.0, 4.0 * dt)
            self._hp_ghost += (player.hp - self._hp_ghost) * ghost_k
        if player.hp > self._hp_ghost:
            self._hp_ghost = float(player.hp)

        # Same for energy ghost
        if player.energy < self._energy_ghost - 0.5:
            self._energy_ghost_timer = 0.3
        if self._energy_ghost_timer > 0:
            self._energy_ghost_timer -= dt
        else:
            ghost_k = min(1.0, 4.0 * dt)
            self._energy_ghost += (player.energy - self._energy_ghost) * ghost_k
        if player.energy > self._energy_ghost:
            self._energy_ghost = float(player.energy)

        # HP bar with ghost
        hp_color = (220, 40, 40) if player.hp < player.max_hp * 0.3 else UI_HP_BAR
        self._draw_bar_with_ghost(
            10, SCREEN_HEIGHT - 50, 200, 18,
            self._hp_display, self._hp_ghost, player.max_hp,
            hp_color, (180, 60, 60), f"HP: {int(player.hp)}/{player.max_hp}")

        # Energy bar with ghost
        self._draw_bar_with_ghost(
            10, SCREEN_HEIGHT - 28, 200, 14,
            self._energy_display, self._energy_ghost, player.max_energy,
            UI_ENERGY_BAR, (60, 100, 140), f"Energy: {int(player.energy)}")

        # Buff/debuff icons above HP bar
        self._draw_buff_icons(player)

        # XP bar (gold fill, no ghost)
        self._draw_bar(10, SCREEN_HEIGHT - 12, 200, 10,
                       player.xp, player.xp_to_next,
                       (200, 180, 60), "")

        # Level and gold
        level_text = self.font_md.render(f"Lv.{player.level}", True, YELLOW)
        self.screen.blit(level_text, (215, SCREEN_HEIGHT - 50))

        gold_text = self.font_md.render(f"Gold: {player.gold}", True, YELLOW)
        self.screen.blit(gold_text, (215, SCREEN_HEIGHT - 30))

        # Active title under player info
        tracker = getattr(player, 'title_tracker', None)
        if tracker and tracker.active_title:
            title_surf = self.font_sm.render(tracker.active_title, True, (200, 180, 100))
            self.screen.blit(title_surf, (10, SCREEN_HEIGHT - 64))

        # Time display (with season and moon info)
        time_text = self.font_md.render(time_sys.time_string, True, UI_TEXT)
        self.screen.blit(time_text, (SCREEN_WIDTH // 2 - time_text.get_width() // 2, 10))

        # Moon and daylight info (smaller, below time)
        if hasattr(time_sys, 'lunara_phase'):
            dl = time_sys.day_length_hours
            moon_info = f"Daylight: {dl:.0f}h  Lunara: {time_sys.lunara_phase}  Thal: {time_sys.thal_phase}"
            if time_sys.conjunction_near:
                moon_info += "  CONJUNCTION!"
            moon_surf = self.font_sm.render(moon_info, True, (120, 130, 160))
            # Dark background for readability
            mbg = pygame.Surface((moon_surf.get_width() + 10, 16), pygame.SRCALPHA)
            mbg.fill((10, 10, 25, 160))
            self.screen.blit(mbg, (SCREEN_WIDTH // 2 - moon_surf.get_width() // 2 - 5, 28))
            self.screen.blit(moon_surf, (SCREEN_WIDTH // 2 - moon_surf.get_width() // 2, 29))

        # Weather indicator (from climate system)
        _climate = getattr(self, '_climate_ref', None)
        if _climate is not None:
            try:
                w = _climate.get_local_weather(player.x, player.y)
                # Weather icon characters
                _icons = {
                    "clear": "*", "cloudy": "~", "rain": "%%",
                    "storm": "!!", "snow": "**", "fog": "...",
                    "heat_wave": "^^", "drought": "XX",
                }
                _colors = {
                    "clear": (255, 230, 100), "cloudy": (170, 170, 190),
                    "rain": (100, 150, 220), "storm": (200, 80, 80),
                    "snow": (220, 230, 245), "fog": (160, 160, 170),
                    "heat_wave": (240, 140, 40), "drought": (200, 160, 60),
                }
                icon = _icons.get(w.condition, "?")
                color = _colors.get(w.condition, UI_TEXT)
                weather_str = f"{icon} {w.condition.replace('_', ' ').title()} {w.temperature:.0f}C"
                weather_surf = self.font_sm.render(weather_str, True, color)
                wbg = pygame.Surface((weather_surf.get_width() + 10, 16), pygame.SRCALPHA)
                wbg.fill((10, 10, 25, 160))
                wx = SCREEN_WIDTH - weather_surf.get_width() - 15
                self.screen.blit(wbg, (wx - 5, 10))
                self.screen.blit(weather_surf, (wx, 11))
            except Exception:
                pass

        # Movement gait indicator
        gait = getattr(player, 'current_gait', 'walk')
        if gait != "walk" and (player.vx != 0 or player.vy != 0):
            from game.systems.physical import MOVEMENT_GAITS
            gait_data = MOVEMENT_GAITS.get(gait, {})
            gait_label = gait_data.get("label", gait.capitalize())
            gait_colors = {"jog": (180, 200, 100), "run": (220, 180, 60),
                          "sprint": (255, 120, 60), "sneak": (100, 160, 200)}
            color = gait_colors.get(gait, UI_TEXT)
            gait_surf = self.font_sm.render(gait_label, True, color)
            self.screen.blit(gait_surf, (10, SCREEN_HEIGHT - 52))

        # Controls hint bar (with dark background for visibility)
        hint = "WASD:Move  Shift:Run  Ctrl:Sneak  Space:Attack  E:Interact  I:Inv  C:Char  H:History  V:View  F:Map"
        hint_surf = self.font_sm.render(hint, True, (200, 200, 210))
        hw = hint_surf.get_width() + 16
        bg = pygame.Surface((hw, 20), pygame.SRCALPHA)
        bg.fill((10, 10, 20, 180))
        self.screen.blit(bg, (6, 28))
        self.screen.blit(hint_surf, (14, 30))

    # ================================================================
    # QUEST TRACKER HUD (top-right corner)
    # ================================================================

    def draw_quest_tracker(self, quests: List[Quest]):
        """Draw a small quest tracker in the top-right corner of the HUD."""
        if not self.show_quest_tracker:
            return

        active = [q for q in quests if not q.completed and not q.turned_in]
        if not active:
            return

        # Show up to 3 active quests
        display_quests = active[:3]

        tw = 260
        th = 10 + len(display_quests) * 42
        tx = SCREEN_WIDTH - tw - 10
        ty = 50  # below god mode hint area

        # Semi-transparent background
        panel = pygame.Surface((tw, th), pygame.SRCALPHA)
        panel.fill((10, 10, 25, 180))
        self.screen.blit(panel, (tx, ty))
        pygame.draw.rect(self.screen, (60, 70, 90), (tx, ty, tw, th), 1)

        # Header
        header = self.font_sm.render("QUESTS", True, UI_HIGHLIGHT)
        self.screen.blit(header, (tx + 5, ty + 2))

        # Toggle hint
        hint = self.font_sm.render("[Q]", True, (100, 100, 120))
        self.screen.blit(hint, (tx + tw - hint.get_width() - 5, ty + 2))

        y = ty + 16
        for quest in display_quests:
            # Difficulty color
            diff_colors = {
                "easy": (100, 200, 100), "medium": (200, 200, 100),
                "hard": (220, 140, 60), "epic": (180, 100, 220),
            }
            diff_color = diff_colors.get(quest.difficulty, UI_TEXT)

            # Quest title (truncated)
            title = quest.title[:28]
            title_surf = self.font_sm.render(title, True, diff_color)
            self.screen.blit(title_surf, (tx + 8, y))
            y += 13

            # Progress bar
            if quest.target_count > 0:
                ratio = min(1.0, quest.progress / max(1, quest.target_count))
                bar_w = tw - 20
                bar_h = 5
                pygame.draw.rect(self.screen, (40, 40, 55), (tx + 8, y, bar_w, bar_h))
                fill_w = int(bar_w * ratio)
                if fill_w > 0:
                    bar_color = GREEN if quest.completed else UI_HIGHLIGHT
                    pygame.draw.rect(self.screen, bar_color, (tx + 8, y, fill_w, bar_h))

                # Progress text
                prog = self.font_sm.render(quest.progress_text, True, (150, 150, 170))
                self.screen.blit(prog, (tx + 8, y + 6))
                y += 20
            else:
                y += 8

            # Separator
            if quest != display_quests[-1]:
                pygame.draw.line(self.screen, (50, 50, 65),
                                (tx + 5, y - 1), (tx + tw - 5, y - 1))

        # "More" indicator
        remaining = len(active) - 3
        if remaining > 0:
            more = self.font_sm.render(f"+{remaining} more", True, (120, 120, 140))
            self.screen.blit(more, (tx + tw - more.get_width() - 8, ty + th - 14))

    def _draw_bar(self, x: int, y: int, w: int, h: int,
                  current: float, maximum: float, color: tuple, text: str):
        bg = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        self.screen.blit(bg, (x - 1, y - 1))

        ratio = max(0, min(1, current / max(1, maximum)))
        bar_w = int(w * ratio)
        if bar_w > 0:
            pygame.draw.rect(self.screen, color, (x, y, bar_w, h))

        pygame.draw.rect(self.screen, UI_BORDER, (x - 1, y - 1, w + 2, h + 2), 1)

        if text:
            text_surf = self.font_sm.render(text, True, WHITE)
            self.screen.blit(text_surf, (x + 4, y + (h - text_surf.get_height()) // 2))

    def _draw_bar_with_ghost(self, x: int, y: int, w: int, h: int,
                             current: float, ghost: float, maximum: float,
                             color: tuple, ghost_color: tuple, text: str):
        """Draw a bar with a ghost (lost value) effect.

        The ghost portion appears as a lighter/faded extension that fades
        smoothly after damage, giving a visual cue of how much was lost.
        """
        bg = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        self.screen.blit(bg, (x - 1, y - 1))

        max_val = max(1, maximum)

        # Ghost bar (drawn first, underneath current bar)
        ghost_ratio = max(0, min(1, ghost / max_val))
        ghost_w = int(w * ghost_ratio)
        if ghost_w > 0:
            ghost_surf = pygame.Surface((ghost_w, h), pygame.SRCALPHA)
            ghost_surf.fill((*ghost_color, 140))
            self.screen.blit(ghost_surf, (x, y))

        # Current bar (drawn on top)
        ratio = max(0, min(1, current / max_val))
        bar_w = int(w * ratio)
        if bar_w > 0:
            pygame.draw.rect(self.screen, color, (x, y, bar_w, h))

        pygame.draw.rect(self.screen, UI_BORDER, (x - 1, y - 1, w + 2, h + 2), 1)

        if text:
            text_surf = self.font_sm.render(text, True, WHITE)
            self.screen.blit(text_surf, (x + 4, y + (h - text_surf.get_height()) // 2))

    def _draw_buff_icons(self, player: Player):
        """Draw small colored squares above the HP bar for active buffs/debuffs."""
        buffs = getattr(player, 'active_buffs', None) or []
        debuffs = getattr(player, 'active_debuffs', None) or []
        # Also check status_effects dict pattern
        status = getattr(player, 'status_effects', {}) or {}

        # Build a list of (label, color) pairs
        icons = []
        _buff_colors = {
            "blessed": (220, 200, 80),
            "haste":   (100, 200, 255),
            "shield":  (120, 180, 220),
            "regen":   (80, 220, 120),
            "strength":(220, 100, 60),
            "poison":  (80, 200, 60),
            "burning":  (255, 120, 40),
            "frozen":  (140, 200, 255),
            "stunned": (200, 200, 80),
            "cursed":  (160, 60, 220),
            "bleed":   (200, 40, 40),
        }
        for b in buffs:
            name = b if isinstance(b, str) else getattr(b, 'name', str(b))
            col = _buff_colors.get(name.lower(), (180, 180, 80))
            icons.append((name[:2].upper(), col))
        for d in debuffs:
            name = d if isinstance(d, str) else getattr(d, 'name', str(d))
            col = _buff_colors.get(name.lower(), (200, 80, 80))
            icons.append((name[:2].upper(), col))
        for sname, sval in status.items():
            if sval:
                col = _buff_colors.get(sname.lower(), (200, 120, 80))
                icons.append((sname[:2].upper(), col))

        if not icons:
            return

        icon_size = 12
        icon_gap = 3
        ix = 10
        iy = SCREEN_HEIGHT - 66
        for label, col in icons[:8]:  # show up to 8
            pygame.draw.rect(self.screen, col, (ix, iy, icon_size, icon_size))
            pygame.draw.rect(self.screen, (0, 0, 0), (ix, iy, icon_size, icon_size), 1)
            if not hasattr(self, '_buff_font'):
                self._buff_font = pygame.font.SysFont("monospace", 8, bold=True)
            lsurf = self._buff_font.render(label, True, (0, 0, 0))
            self.screen.blit(lsurf, (ix + icon_size // 2 - lsurf.get_width() // 2,
                                     iy + icon_size // 2 - lsurf.get_height() // 2))
            ix += icon_size + icon_gap

    def draw_notifications(self, notifications: List[Notification]):
        y = SCREEN_HEIGHT - 90
        for notif in reversed(notifications[-5:]):
            alpha = int(255 * notif.alpha)
            text_surf = self.font_md.render(notif.text, True, notif.color)
            if notif.alpha < 1.0:
                text_surf.set_alpha(alpha)
            self.screen.blit(text_surf, (SCREEN_WIDTH // 2 - text_surf.get_width() // 2, y))
            y -= 22

    # ================================================================
    # TRANSITION EFFECTS
    # ================================================================

    def update_transitions(self, dt: float, time_phase: str = "",
                           is_indoor: bool = False):
        """Update all smooth transition effects. Call once per frame.

        Args:
            dt: frame delta in seconds.
            time_phase: "dawn", "day", "dusk", "night" for color flash.
            is_indoor: True if the player is inside a building.
        """
        # --- Panel slide-in ---
        panel_open = self.any_panel_open
        if panel_open and not self._last_panel_state:
            # Panel just opened — start slide animation
            self._panel_slide_progress = 0.0
            self._panel_slide_active = True
        self._last_panel_state = panel_open

        if self._panel_slide_active:
            self._panel_slide_progress += dt / 0.1  # 100ms ease-in
            if self._panel_slide_progress >= 1.0:
                self._panel_slide_progress = 1.0
                self._panel_slide_active = False

        # --- Dawn/dusk color flash ---
        if time_phase and time_phase != self._last_time_phase:
            if time_phase == "dawn":
                self._time_flash_alpha = 60
                self._time_flash_color = (220, 160, 60)
            elif time_phase == "dusk":
                self._time_flash_alpha = 50
                self._time_flash_color = (200, 100, 60)
            self._last_time_phase = time_phase

        if self._time_flash_alpha > 0:
            self._time_flash_alpha = max(0, self._time_flash_alpha - 120 * dt)

        # --- Building enter/exit fade ---
        if is_indoor and not self._was_indoor:
            self._building_fade_alpha = 255
            self._building_fade_direction = -1  # fade from black
        elif not is_indoor and self._was_indoor:
            self._building_fade_alpha = 255
            self._building_fade_direction = -1
        self._was_indoor = is_indoor

        if self._building_fade_alpha > 0:
            # Fade out over 200ms
            self._building_fade_alpha = max(
                0, self._building_fade_alpha - 1275 * dt)  # 255/0.2

    def draw_transitions(self):
        """Draw active transition overlays. Call after panels are drawn."""
        # Dawn/dusk color flash
        if self._time_flash_alpha > 2:
            flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            r, g, b = self._time_flash_color
            flash.fill((r, g, b, int(self._time_flash_alpha)))
            self.screen.blit(flash, (0, 0))

        # Building fade
        if self._building_fade_alpha > 2:
            fade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            fade.fill((0, 0, 0, int(self._building_fade_alpha)))
            self.screen.blit(fade, (0, 0))

    def get_panel_slide_offset(self) -> int:
        """Return x-offset for panel slide-in animation (0 = fully visible).

        Panels that support sliding should add this offset to their x position.
        """
        if self._panel_slide_progress >= 1.0:
            return 0
        # Ease-in: starts from right side of screen
        t = 1.0 - self._panel_slide_progress
        return int(SCREEN_WIDTH * 0.3 * t * t)  # quadratic ease

    # ================================================================
    # INTERACTION PROMPTS
    # ================================================================

    def draw_interaction_prompt(self, npc: NPC):
        cls = f"{getattr(npc, 'race', '')} {getattr(npc, 'char_class', npc.profession)}"
        text = f"[E] Talk  [T] Chat  [R] Recruit  [Space] Attack  -  {npc.name} ({cls})"
        text_surf = self.font_md.render(text, True, YELLOW)
        x = SCREEN_WIDTH // 2 - text_surf.get_width() // 2
        y = SCREEN_HEIGHT - 110

        bg = pygame.Surface((text_surf.get_width() + 20, 26), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 180))
        self.screen.blit(bg, (x - 10, y - 3))
        self.screen.blit(text_surf, (x, y))

    def draw_pickup_prompt(self, items: list, player_x: float, player_y: float):
        import math
        nearby = [(gx, gy, item) for gx, gy, item in items
                  if math.sqrt((player_x - gx)**2 + (player_y - gy)**2) < 1.5]
        if not nearby:
            return

        text = f"[E] Pick up {nearby[0][2].name}"
        if len(nearby) > 1:
            text += f" (+{len(nearby) - 1} more)"
        text_surf = self.font_md.render(text, True, GREEN)
        x = SCREEN_WIDTH // 2 - text_surf.get_width() // 2
        y = SCREEN_HEIGHT - 135

        bg = pygame.Surface((text_surf.get_width() + 20, 26), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 180))
        self.screen.blit(bg, (x - 10, y - 3))
        self.screen.blit(text_surf, (x, y))

    # ================================================================
    # DIALOG SYSTEM (menu-based + free text input)
    # ================================================================

    def open_dialog(self, npc: NPC):
        self.dialog_active = True
        self.dialog_npc = npc
        self.dialog_key = "greeting"
        self.selected_response = 0
        self.llm_response_text = ""
        self.llm_waiting = False

    def open_text_input(self, npc: NPC):
        """Open free-text input to talk to NPC."""
        self.text_input_active = True
        self.text_input_buffer = ""
        self.dialog_npc = npc
        self.llm_response_text = ""
        self.llm_waiting = False

    def draw_dialog(self):
        if not self.dialog_active or not self.dialog_npc:
            return

        npc = self.dialog_npc
        dialog = npc.dialog_lines.get(self.dialog_key)
        if not dialog:
            self.dialog_active = False
            return

        dw, dh = 650, 280
        dx = SCREEN_WIDTH // 2 - dw // 2
        dy = SCREEN_HEIGHT - dh - 60

        title = f"{npc.name} - {getattr(npc, 'race', '')} {getattr(npc, 'char_class', npc.profession)} Lv.{getattr(npc, 'level', 1)}"
        self._draw_panel(dx, dy, dw, dh, title, theme="dialog")

        # NPC info line (needs, consciousness)
        info_parts = []
        if hasattr(npc, 'needs'):
            h = npc.needs.get("hunger", 0)
            if h < 40:
                info_parts.append(f"hungry({int(h)})")
        if npc.consciousness >= 2:
            info_parts.append(f"consciousness: {npc.consciousness}")
        if info_parts:
            info_str = "  ".join(info_parts)
            info_surf = self.font_sm.render(info_str, True, (120, 120, 160))
            self.screen.blit(info_surf, (dx + dw - info_surf.get_width() - 15, dy + 10))

        # NPC text (word-wrapped)
        text = dialog.text
        if self.llm_response_text:
            text = self.llm_response_text
        lines = self._wrap_text(text, dw - 30, self.font_md)
        y = dy + 42
        for line in lines[:6]:
            self.screen.blit(self.font_md.render(line, True, UI_TEXT), (dx + 15, y))
            y += 20

        # Response options
        responses = list(dialog.responses)
        # Add "Say something..." option
        responses.append(("Say something... (free text)", "free_text"))
        responses.append(("[Gift] Give an item...", "gift"))

        y = dy + dh - 15 - len(responses) * 22
        pygame.draw.line(self.screen, UI_BORDER, (dx + 5, y - 5), (dx + dw - 5, y - 5))

        for i, (response_text, _) in enumerate(responses):
            color = YELLOW if i == self.selected_response else UI_TEXT
            prefix = "> " if i == self.selected_response else "  "
            self.screen.blit(self.font_md.render(prefix + response_text, True, color), (dx + 15, y))
            y += 22

    def handle_dialog_input(self, key) -> Optional[str]:
        if not self.dialog_active or not self.dialog_npc:
            return None

        dialog = self.dialog_npc.dialog_lines.get(self.dialog_key)
        if not dialog:
            self.dialog_active = False
            return None

        responses = list(dialog.responses)
        responses.append(("Say something...", "free_text"))
        responses.append(("[Gift] Give an item...", "gift"))

        if key == pygame.K_UP:
            self.selected_response = max(0, self.selected_response - 1)
        elif key == pygame.K_DOWN:
            self.selected_response = min(len(responses) - 1, self.selected_response + 1)
        elif key == pygame.K_e or key == pygame.K_RETURN:
            if self.selected_response >= len(responses):
                return None

            _, next_key = responses[self.selected_response]

            if next_key == "free_text":
                self.dialog_active = False
                self.open_text_input(self.dialog_npc)
                return "free_text"
            elif next_key == "gift":
                self.dialog_active = False
                self.open_gift_panel(self.dialog_npc)
                return "gift"
            elif next_key == "goodbye":
                self.dialog_active = False
                return "close"
            elif next_key == "shop":
                self.dialog_active = False
                self.open_shop(self.dialog_npc)
                return "shop"
            else:
                self.dialog_key = next_key
                self.selected_response = 0
                return next_key
        elif key == pygame.K_ESCAPE:
            self.dialog_active = False
            return "close"
        elif key == pygame.K_t:
            self.dialog_active = False
            self.open_text_input(self.dialog_npc)
            return "free_text"

        return None

    # ================================================================
    # FREE TEXT INPUT
    # ================================================================

    def draw_text_input(self):
        """Draw the free-text input dialog."""
        if not self.text_input_active or not self.dialog_npc:
            return

        npc = self.dialog_npc
        dw, dh = 650, 300
        dx = SCREEN_WIDTH // 2 - dw // 2
        dy = SCREEN_HEIGHT - dh - 60

        self._draw_panel(dx, dy, dw, dh, f"Talking to {npc.name}", theme="dialog")

        y = dy + 42

        # Show LLM response if available
        if self.llm_response_text:
            resp_lines = self._wrap_text(self.llm_response_text, dw - 30, self.font_md)
            name_surf = self.font_md.render(f"{npc.name}:", True, UI_HIGHLIGHT)
            self.screen.blit(name_surf, (dx + 15, y))
            y += 22
            for line in resp_lines[:6]:
                self.screen.blit(self.font_md.render(line, True, UI_TEXT), (dx + 25, y))
                y += 20
            y += 10
        elif self.llm_waiting:
            wait = self.font_md.render(f"{npc.name} is thinking...", True, (150, 150, 180))
            self.screen.blit(wait, (dx + 15, y))
            y += 30

        # Input field
        pygame.draw.line(self.screen, UI_BORDER, (dx + 5, dy + dh - 80), (dx + dw - 5, dy + dh - 80))
        prompt_label = self.font_md.render("You say:", True, YELLOW)
        self.screen.blit(prompt_label, (dx + 15, dy + dh - 68))

        # Text input box
        input_rect = pygame.Rect(dx + 15, dy + dh - 48, dw - 30, 26)
        pygame.draw.rect(self.screen, (30, 30, 45), input_rect)
        pygame.draw.rect(self.screen, UI_HIGHLIGHT, input_rect, 1)

        # Text with cursor
        display_text = self.text_input_buffer
        self.text_input_cursor_blink += 0.05
        if int(self.text_input_cursor_blink) % 2 == 0:
            display_text += "|"
        text_surf = self.font_md.render(display_text[-50:], True, WHITE)  # show last 50 chars
        self.screen.blit(text_surf, (dx + 20, dy + dh - 44))

        # Hints
        hint = self.font_sm.render("[Enter] Send  [Escape] Close  [Tab] Back to menu", True, (150, 150, 170))
        self.screen.blit(hint, (dx + dw // 2 - hint.get_width() // 2, dy + dh - 18))

    def handle_text_input_event(self, event) -> Optional[str]:
        """Handle events for text input. Returns 'send', 'close', 'back', or None."""
        if not self.text_input_active:
            return None

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                if self.text_input_buffer.strip():
                    return "send"
            elif event.key == pygame.K_ESCAPE:
                self.text_input_active = False
                self.llm_response_text = ""
                return "close"
            elif event.key == pygame.K_TAB:
                # Go back to menu dialog
                self.text_input_active = False
                if self.dialog_npc:
                    self.open_dialog(self.dialog_npc)
                return "back"
            elif event.key == pygame.K_BACKSPACE:
                self.text_input_buffer = self.text_input_buffer[:-1]
            else:
                return None
        elif event.type == pygame.TEXTINPUT:
            self.text_input_buffer += event.text

        return None

    def get_and_clear_input(self) -> str:
        """Get the typed text and clear the buffer."""
        text = self.text_input_buffer.strip()
        self.text_input_buffer = ""
        return text

    def set_llm_response(self, text: str):
        """Set the LLM response to display."""
        self.llm_response_text = text
        self.llm_waiting = False

    # ================================================================
    # SHOP
    # ================================================================

    def open_shop(self, npc: NPC):
        # Support both formal shop_items and informal barter from npc_inventory
        if not npc.shop_items and not getattr(npc, 'npc_inventory', []):
            return
        self.shop_active = True
        self.shop_npc = npc
        self.shop_selected = 0
        self._shop_sell_mode = False
        # Track whether this is a barter (selling from personal inventory)
        self._shop_is_barter = not npc.shop_items and bool(getattr(npc, 'npc_inventory', []))

    def _get_shop_items(self):
        """Get displayable items - either shop_items or npc_inventory for barter."""
        npc = self.shop_npc
        if not npc:
            return []
        if npc.shop_items:
            return npc.shop_items
        return getattr(npc, 'npc_inventory', [])

    def draw_shop(self, player: Player):
        if not self.shop_active or not self.shop_npc:
            return

        is_barter = getattr(self, '_shop_is_barter', False)
        sell_mode = self._shop_sell_mode

        # Determine items to display based on mode
        if sell_mode:
            items = list(player.inventory)
        else:
            items = self._get_shop_items()

        sw, sh = 500, 350
        sx = SCREEN_WIDTH // 2 - sw // 2
        sy = SCREEN_HEIGHT // 2 - sh // 2

        mode_label = "SELL" if sell_mode else "BUY"
        if is_barter:
            title = f"Barter with {self.shop_npc.name} [{mode_label}]"
        else:
            title = f"{self.shop_npc.name}'s Shop [{mode_label}]"
        self._draw_panel(sx, sy, sw, sh, title, theme="shop")

        gold_text = self.font_md.render(f"Your Gold: {player.gold}", True, YELLOW)
        self.screen.blit(gold_text, (sx + sw - gold_text.get_width() - 15, sy + 8))

        if not items:
            msg = "You have nothing to sell." if sell_mode else "Nothing available to trade."
            no_items = self.font_md.render(msg, True, GRAY)
            self.screen.blit(no_items, (sx + 15, sy + 45))
            hint = self.font_sm.render("[Tab] Buy/Sell  [Escape] Close", True, (150, 150, 170))
            self.screen.blit(hint, (sx + sw // 2 - hint.get_width() // 2, sy + sh - 22))
            return

        y = sy + 45
        for i, item in enumerate(items):
            color = YELLOW if i == self.shop_selected else UI_TEXT
            if i == self.shop_selected:
                pygame.draw.rect(self.screen, (40, 40, 60), (sx + 5, y - 2, sw - 10, 22))

            if sell_mode:
                # Sell price: 50% value, or 40% for barter
                sell_mult = 0.4 if is_barter else 0.5
                price = max(1, int(item.value * sell_mult))
                text = f"{item.name:<25s} {price:>4d} gold"
            else:
                price = item.value if not is_barter else max(1, int(item.value * 0.8))
                text = f"{item.name:<25s} {price:>4d} gold"
            self.screen.blit(self.font_md.render(text, True, color), (sx + 15, y))
            y += 24

        if items and self.shop_selected < len(items):
            item = items[self.shop_selected]
            y += 10
            pygame.draw.line(self.screen, UI_BORDER, (sx + 5, y), (sx + sw - 5, y))
            y += 8
            desc = getattr(item, 'description', '') or ''
            self.screen.blit(self.font_sm.render(desc, True, GRAY), (sx + 15, y))
            y += 18
            if getattr(item, 'damage', 0):
                self.screen.blit(self.font_sm.render(f"Damage: +{item.damage}", True, RED), (sx + 15, y))
            elif getattr(item, 'defense', 0):
                self.screen.blit(self.font_sm.render(f"Defense: +{item.defense}", True, BLUE), (sx + 15, y))
            elif getattr(item, 'heal', 0):
                self.screen.blit(self.font_sm.render(f"Heals: {item.heal} HP", True, GREEN), (sx + 15, y))

        action_label = "Sell" if sell_mode else "Buy"
        hint = self.font_sm.render(f"[Tab] Buy/Sell  [Enter] {action_label}  [Escape] Close", True, (150, 150, 170))
        self.screen.blit(hint, (sx + sw // 2 - hint.get_width() // 2, sy + sh - 22))

    def handle_shop_input(self, key, player: Player) -> Optional[str]:
        if not self.shop_active or not self.shop_npc:
            return None

        is_barter = getattr(self, '_shop_is_barter', False)
        sell_mode = self._shop_sell_mode

        # Determine items based on mode
        if sell_mode:
            items = list(player.inventory)
        else:
            items = self._get_shop_items()

        if key == pygame.K_TAB:
            self._shop_sell_mode = not self._shop_sell_mode
            self.shop_selected = 0
            return None
        elif key == pygame.K_UP:
            self.shop_selected = max(0, self.shop_selected - 1)
        elif key == pygame.K_DOWN:
            self.shop_selected = min(len(items) - 1, self.shop_selected + 1) if items else 0
        elif key == pygame.K_RETURN or key == pygame.K_e:
            if not items or self.shop_selected >= len(items):
                return None

            if sell_mode:
                # Sell mode: remove item from player, add gold
                item = items[self.shop_selected]
                sell_mult = 0.4 if is_barter else 0.5
                price = max(1, int(item.value * sell_mult))
                player.gold += price
                # Give gold to NPC
                self.shop_npc.npc_gold = getattr(self.shop_npc, 'npc_gold', 0) - price
                # Remove from player inventory
                player.inventory.remove(item)
                # Adjust selection
                new_items = list(player.inventory)
                if self.shop_selected >= len(new_items):
                    self.shop_selected = max(0, len(new_items) - 1)
                return f"Sold {item.name} for {price} gold"
            else:
                # Buy mode (original logic)
                item = items[self.shop_selected]
                price = item.value if not is_barter else max(1, int(item.value * 0.8))
                if player.gold >= price:
                    if is_barter:
                        # Barter: take actual item from NPC's inventory
                        if player.add_item(item):
                            player.gold -= price
                            self.shop_npc.npc_gold = getattr(self.shop_npc, 'npc_gold', 0) + price
                            self.shop_npc.npc_inventory.remove(item)
                            # Adjust selection if we removed the last item
                            if self.shop_selected >= len(self.shop_npc.npc_inventory):
                                self.shop_selected = max(0, len(self.shop_npc.npc_inventory) - 1)
                            if not self.shop_npc.npc_inventory:
                                self.shop_active = False
                                return f"Bought {item.name} for {price} gold. Nothing left to trade."
                            return f"Bought {item.name} for {price} gold"
                        else:
                            return "Inventory full!"
                    else:
                        # Shop: create a copy of the item
                        from game.core.items import make_item
                        bought = make_item(item.name)
                        if player.add_item(bought):
                            player.gold -= price
                            return f"Bought {item.name} for {price} gold"
                        else:
                            return "Inventory full!"
                else:
                    return "Not enough gold!"
        elif key == pygame.K_ESCAPE:
            self.shop_active = False
            self._shop_is_barter = False
            self._shop_sell_mode = False
        return None

    # ================================================================
    # GIFT GIVING
    # ================================================================

    def open_gift_panel(self, npc: NPC):
        """Open the gift-giving panel for an NPC."""
        self.gift_active = True
        self.gift_npc = npc
        self.gift_selected = 0

    def draw_gift_panel(self, player: Player):
        """Render the gift selection panel."""
        if not self.gift_active or not self.gift_npc:
            return

        items = list(player.inventory)
        npc = self.gift_npc

        gw, gh = 500, 350
        gx = SCREEN_WIDTH // 2 - gw // 2
        gy = SCREEN_HEIGHT // 2 - gh // 2

        self._draw_panel(gx, gy, gw, gh, f"Give a Gift to {npc.name}", theme="shop")

        if not items:
            no_items = self.font_md.render("You have nothing to give.", True, GRAY)
            self.screen.blit(no_items, (gx + 15, gy + 45))
            hint = self.font_sm.render("[Escape] Close", True, (150, 150, 170))
            self.screen.blit(hint, (gx + gw // 2 - hint.get_width() // 2, gy + gh - 22))
            return

        y = gy + 45
        for i, item in enumerate(items):
            color = YELLOW if i == self.gift_selected else UI_TEXT
            if i == self.gift_selected:
                pygame.draw.rect(self.screen, (40, 40, 60), (gx + 5, y - 2, gw - 10, 22))

            text = f"Give {item.name} to {npc.name}"
            self.screen.blit(self.font_md.render(text, True, color), (gx + 15, y))
            y += 24

        # Selected item description
        if items and self.gift_selected < len(items):
            item = items[self.gift_selected]
            y += 10
            pygame.draw.line(self.screen, UI_BORDER, (gx + 5, y), (gx + gw - 5, y))
            y += 8
            desc = getattr(item, 'description', '') or ''
            self.screen.blit(self.font_sm.render(desc, True, GRAY), (gx + 15, y))
            y += 18
            if getattr(item, 'damage', 0):
                self.screen.blit(self.font_sm.render(f"Damage: +{item.damage}", True, RED), (gx + 15, y))
            elif getattr(item, 'defense', 0):
                self.screen.blit(self.font_sm.render(f"Defense: +{item.defense}", True, BLUE), (gx + 15, y))
            elif getattr(item, 'heal', 0):
                self.screen.blit(self.font_sm.render(f"Heals: {item.heal} HP", True, GREEN), (gx + 15, y))

        hint = self.font_sm.render("[Enter] Give  [Escape] Cancel", True, (150, 150, 170))
        self.screen.blit(hint, (gx + gw // 2 - hint.get_width() // 2, gy + gh - 22))

    def handle_gift_input(self, key, player: Player) -> Optional[Item]:
        """Handle gift selection input. Returns the given item or None."""
        if not self.gift_active or not self.gift_npc:
            return None

        items = list(player.inventory)

        if key == pygame.K_UP:
            self.gift_selected = max(0, self.gift_selected - 1)
        elif key == pygame.K_DOWN:
            self.gift_selected = min(len(items) - 1, self.gift_selected + 1) if items else 0
        elif key == pygame.K_RETURN or key == pygame.K_e:
            if items and self.gift_selected < len(items):
                item = items[self.gift_selected]
                # Remove item from player inventory
                player.inventory.remove(item)
                # Adjust selection
                new_items = list(player.inventory)
                if self.gift_selected >= len(new_items):
                    self.gift_selected = max(0, len(new_items) - 1)
                if not new_items:
                    self.gift_active = False
                    self.gift_npc = None
                return item
        elif key == pygame.K_ESCAPE:
            self.gift_active = False
            self.gift_npc = None
        return None

    # ================================================================
    # INVENTORY (expanded)
    # ================================================================

    # Inventory category definitions
    _INV_CATEGORIES = [
        ("All", None),
        ("Weapons", ITEM_WEAPON),
        ("Armor", ITEM_ARMOR),
        ("Consumables", ITEM_CONSUMABLE),
        ("Materials", ITEM_RESOURCE),
        ("Quest", ITEM_QUEST),
        ("Tools/Other", ITEM_TOOL),
    ]

    def _get_item_rarity(self, item: Item) -> Tuple[str, Tuple[int, int, int]]:
        """Determine item rarity based on value and stats."""
        total_power = item.value + (item.damage or 0) * 3 + (item.defense or 0) * 4
        if total_power >= 400:
            return ("Legendary", (255, 215, 0))      # gold
        elif total_power >= 200:
            return ("Epic", (180, 100, 220))          # purple
        elif total_power >= 100:
            return ("Rare", (80, 140, 220))           # blue
        elif total_power >= 40:
            return ("Uncommon", (80, 200, 100))       # green
        else:
            return ("Common", (220, 220, 230))        # white

    def _filter_inventory(self, player: Player) -> List[Item]:
        """Filter and sort player inventory based on selected category."""
        _, filter_kind = self._INV_CATEGORIES[self.inv_category]
        items = list(player.inventory)

        if filter_kind is not None:
            # Special handling: "Consumables" includes food and drink
            if filter_kind == ITEM_CONSUMABLE:
                items = [i for i in items if i.kind in (ITEM_CONSUMABLE, ITEM_FOOD, ITEM_DRINK)]
            # "Tools/Other" includes tools and miscellaneous
            elif filter_kind == ITEM_TOOL:
                items = [i for i in items if i.kind in (ITEM_TOOL,)]
            else:
                items = [i for i in items if i.kind == filter_kind]

        # Sort by value (descending) within category
        items.sort(key=lambda i: -i.value)
        return items

    def draw_inventory(self, player: Player):
        if not self.show_inventory:
            return

        iw, ih = 540, 500
        ix = SCREEN_WIDTH // 2 - iw // 2
        iy = SCREEN_HEIGHT // 2 - ih // 2

        self._draw_panel(ix, iy, iw, ih, f"Inventory ({len(player.inventory)}/20)", theme="inventory")

        # -- Equipped items section (top) --
        y = iy + 42
        equip_label = self.font_sm.render("EQUIPPED", True, (180, 160, 100))
        self.screen.blit(equip_label, (ix + 15, y))
        y += 16

        weapon_name = player.equipped_weapon.name if player.equipped_weapon else "None"
        armor_name = player.equipped_armor.name if player.equipped_armor else "None"

        # Weapon with rarity color
        wlabel = self.font_sm.render("Weapon: ", True, (150, 150, 170))
        self.screen.blit(wlabel, (ix + 20, y))
        if player.equipped_weapon:
            _, wcolor = self._get_item_rarity(player.equipped_weapon)
            durability_str = ""
            if hasattr(player.equipped_weapon, 'durability') and player.equipped_weapon.durability is not None:
                durability_str = f" [{player.equipped_weapon.durability}%]"
            wname_surf = self.font_sm.render(f"{weapon_name}{durability_str}", True, wcolor)
        else:
            wname_surf = self.font_sm.render(weapon_name, True, GRAY)
        self.screen.blit(wname_surf, (ix + 20 + wlabel.get_width(), y))

        # Armor on same line (right side)
        alabel = self.font_sm.render("Armor: ", True, (150, 150, 170))
        ax = ix + iw // 2 + 10
        self.screen.blit(alabel, (ax, y))
        if player.equipped_armor:
            _, acolor = self._get_item_rarity(player.equipped_armor)
            aname_surf = self.font_sm.render(armor_name, True, acolor)
        else:
            aname_surf = self.font_sm.render(armor_name, True, GRAY)
        self.screen.blit(aname_surf, (ax + alabel.get_width(), y))
        y += 16

        self.screen.blit(self.font_sm.render(
            f"ATK: {player.get_attack_damage()}  DEF: {player.get_defense()}  Gold: {player.gold}",
            True, (180, 180, 200)), (ix + 20, y))
        y += 18

        pygame.draw.line(self.screen, UI_BORDER, (ix + 5, y), (ix + iw - 5, y))
        y += 4

        # -- Category tabs --
        tab_x = ix + 8
        for ti, (tab_name, _) in enumerate(self._INV_CATEGORIES):
            is_active = (ti == self.inv_category)
            tab_color = UI_HIGHLIGHT if is_active else (100, 100, 120)
            bg_color = (40, 40, 60) if is_active else (20, 20, 35)

            tab_surf = self.font_sm.render(tab_name, True, tab_color)
            tw = tab_surf.get_width() + 10
            tab_rect = pygame.Rect(tab_x, y, tw, 16)

            if is_active:
                pygame.draw.rect(self.screen, bg_color, tab_rect)
                pygame.draw.rect(self.screen, tab_color, tab_rect, 1)

            self.screen.blit(tab_surf, (tab_x + 5, y + 1))
            tab_x += tw + 2

            if tab_x > ix + iw - 40:
                break  # prevent overflow

        y += 20
        pygame.draw.line(self.screen, UI_BORDER, (ix + 5, y), (ix + iw - 5, y))
        y += 4

        # -- Filtered item list --
        filtered_items = self._filter_inventory(player)

        if not filtered_items:
            empty_msg = "Empty" if not player.inventory else "No items in this category"
            self.screen.blit(self.font_md.render(empty_msg, True, GRAY),
                            (ix + iw // 2 - 50, y + 20))
        else:
            # Clamp selection
            if self.inv_selected >= len(filtered_items):
                self.inv_selected = max(0, len(filtered_items) - 1)

            for i, item in enumerate(filtered_items):
                if y > iy + ih - 90:
                    more = len(filtered_items) - i
                    self.screen.blit(self.font_sm.render(f"... and {more} more items", True, GRAY),
                                    (ix + 22, y))
                    break

                # Rarity color for item name
                rarity_name, rarity_color = self._get_item_rarity(item)
                is_selected = (i == self.inv_selected)

                if is_selected:
                    pygame.draw.rect(self.screen, (40, 40, 60), (ix + 5, y - 2, iw - 10, 18))

                count_str = f" x{item.count}" if item.stackable and item.count > 1 else ""
                text = f"{item.name}{count_str}"

                # Kind indicator dot
                kind_color = {
                    ITEM_WEAPON: YELLOW, ITEM_ARMOR: LIGHT_GRAY, ITEM_CONSUMABLE: GREEN,
                    ITEM_RESOURCE: ORANGE, ITEM_QUEST: (200, 100, 255),
                    ITEM_FOOD: (120, 200, 80), ITEM_DRINK: (80, 160, 220), ITEM_TOOL: (200, 180, 100),
                }.get(item.kind, UI_TEXT)

                pygame.draw.circle(self.screen, kind_color, (ix + 12, y + 7), 4)

                # Item name in rarity color (or highlighted if selected)
                name_color = YELLOW if is_selected else rarity_color
                self.screen.blit(self.font_sm.render(text, True, name_color), (ix + 22, y))

                # Quick stat summary on right
                stat_parts = []
                if item.damage:
                    stat_parts.append(f"+{item.damage}D")
                if item.defense:
                    stat_parts.append(f"+{item.defense}A")
                if item.heal:
                    stat_parts.append(f"+{item.heal}H")
                if stat_parts:
                    stat_str = " ".join(stat_parts)
                    stat_surf = self.font_sm.render(stat_str, True, (140, 140, 160))
                    self.screen.blit(stat_surf, (ix + iw - stat_surf.get_width() - 45, y))

                self.screen.blit(self.font_sm.render(f"{item.value}g", True, GRAY),
                                (ix + iw - 40, y))
                y += 18

        # -- Detail panel for selected item --
        if filtered_items and self.inv_selected < len(filtered_items):
            item = filtered_items[self.inv_selected]
            y = iy + ih - 82
            pygame.draw.line(self.screen, UI_BORDER, (ix + 5, y), (ix + iw - 5, y))
            y += 5

            # Rarity badge
            rarity_name, rarity_color = self._get_item_rarity(item)
            rarity_surf = self.font_sm.render(f"[{rarity_name}]", True, rarity_color)
            self.screen.blit(rarity_surf, (ix + 15, y))
            y += 14

            self.screen.blit(self.font_sm.render(item.description, True, GRAY), (ix + 15, y))
            y += 16
            stats = []
            if item.damage:
                stats.append(f"DMG:+{item.damage}")
            if item.defense:
                stats.append(f"DEF:+{item.defense}")
            if item.heal:
                stats.append(f"Heal:{item.heal}")
            if hasattr(item, 'durability') and item.durability is not None:
                stats.append(f"Dur:{item.durability}/{item.max_durability}")
            if stats:
                self.screen.blit(self.font_sm.render("  ".join(stats), True, UI_HIGHLIGHT), (ix + 15, y))
                y += 14

        hint = self.font_sm.render("[E] Use/Equip  [G/X] Drop  [Tab] Category  [Escape/I] Close", True, (150, 150, 170))
        self.screen.blit(hint, (ix + 15, iy + ih - 18))

    def handle_inventory_input(self, key, player: Player, world_mgr=None) -> Optional[str]:
        if not self.show_inventory:
            return None

        if key == pygame.K_ESCAPE or key == pygame.K_i:
            self.show_inventory = False
            return None

        # Tab to cycle category
        if key == pygame.K_TAB:
            self.inv_category = (self.inv_category + 1) % len(self._INV_CATEGORIES)
            self.inv_selected = 0
            return None

        if not player.inventory:
            return None

        # Work with filtered list
        filtered = self._filter_inventory(player)
        if not filtered:
            return None

        if key == pygame.K_UP:
            self.inv_selected = max(0, self.inv_selected - 1)
        elif key == pygame.K_DOWN:
            self.inv_selected = min(len(filtered) - 1, self.inv_selected + 1)
        elif key == pygame.K_e or key == pygame.K_RETURN:
            if self.inv_selected < len(filtered):
                item = filtered[self.inv_selected]
                result = player.use_item(item)
                if result:
                    self.inv_selected = min(self.inv_selected, max(0, len(self._filter_inventory(player)) - 1))
                    return result
        elif key in (pygame.K_x, pygame.K_g):
            if self.inv_selected < len(filtered):
                item = filtered[self.inv_selected]
                if item.kind != ITEM_QUEST:
                    player.inventory.remove(item)
                    self.inv_selected = min(self.inv_selected, max(0, len(self._filter_inventory(player)) - 1))
                    return ("drop", item)
                else:
                    return "Can't drop quest items!"
        return None

    # ================================================================
    # CHARACTER SHEET
    # ================================================================

    def draw_character_sheet(self, player: Player):
        if not self.show_character:
            return

        cw, ch = 620, 560
        cx = SCREEN_WIDTH // 2 - cw // 2
        cy = SCREEN_HEIGHT // 2 - ch // 2

        race = getattr(player, 'race', 'Human')
        char_class = getattr(player, 'char_class', 'Fighter')
        self._draw_panel(cx, cy, cw, ch,
                        f"{race} {char_class} - Level {player.level}", theme="character")

        y = cy + 42
        col2 = cx + cw // 2 + 10

        # -- LEFT COLUMN: Ability Scores --
        self.screen.blit(self.font_md.render("Ability Scores", True, UI_HIGHLIGHT), (cx + 15, y))
        y += 22
        from game.data.dnd import ability_modifier
        scores = getattr(player, 'ability_scores', {})
        for attr in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"):
            val = scores.get(attr, 10)
            mod = ability_modifier(val)
            mod_str = f"+{mod}" if mod >= 0 else str(mod)
            label = f"{attr[:3].upper()}: {val} ({mod_str})"
            self.screen.blit(self.font_sm.render(label, True, UI_TEXT), (cx + 25, y))
            y += 16
        y += 6

        # -- Combat Stats --
        self.screen.blit(self.font_md.render("Combat", True, UI_HIGHLIGHT), (cx + 15, y))
        y += 22
        ac = getattr(player, 'armor_class', 10)
        prof = getattr(player, 'proficiency_bonus', 2)
        combat_stats = [
            f"HP: {int(player.hp)}/{player.max_hp}  |  AC: {ac}",
            f"Attack: {player.get_attack_damage()}  |  Prof: +{prof}",
            f"Energy: {int(player.energy)}/{player.max_energy}",
            f"Gold: {player.gold}  |  XP: {player.xp}/{player.xp_to_next}",
        ]
        for s in combat_stats:
            self.screen.blit(self.font_sm.render(s, True, UI_TEXT), (cx + 25, y))
            y += 16
        y += 6

        # -- Class Abilities --
        abilities_list = getattr(player, 'class_abilities', [])
        self.screen.blit(self.font_md.render("Class Abilities", True, UI_HIGHLIGHT), (cx + 15, y))
        y += 22
        if abilities_list:
            for ab in abilities_list[:6]:
                self.screen.blit(self.font_sm.render(f"  {ab}", True, (160, 200, 160)), (cx + 15, y))
                y += 15
        else:
            self.screen.blit(self.font_sm.render("  None yet", True, GRAY), (cx + 15, y))
            y += 15
        y += 4

        # -- RIGHT COLUMN (start from top) --
        ry = cy + 42

        # Spells
        is_caster = getattr(player, 'is_spellcaster', False)
        self.screen.blit(self.font_md.render("Spells", True, UI_HIGHLIGHT), (col2, ry))
        ry += 22
        if is_caster:
            slots = getattr(player, 'spell_slots', [0,0,0])
            used = getattr(player, 'spell_slots_used', [0,0,0])
            for i in range(3):
                if slots[i] > 0:
                    self.screen.blit(self.font_sm.render(
                        f"Lv{i+1} slots: {slots[i] - used[i]}/{slots[i]}", True, UI_TEXT), (col2 + 10, ry))
                    ry += 14
            ry += 4
            spells = getattr(player, 'known_spells', [])
            for sp in spells[:8]:
                self.screen.blit(self.font_sm.render(f"  {sp}", True, (140, 180, 220)), (col2 + 10, ry))
                ry += 14
        else:
            self.screen.blit(self.font_sm.render("  Not a spellcaster", True, GRAY), (col2 + 10, ry))
            ry += 14
        ry += 8

        # Active abilities (from skill system)
        active_abs = player.get_abilities()
        self.screen.blit(self.font_md.render("Active Abilities", True, UI_HIGHLIGHT), (col2, ry))
        ry += 22
        if active_abs:
            for name, desc, ready, hotkey in active_abs:
                color = GREEN if ready else (100, 100, 100)
                label = f"[{hotkey}] {name}"
                self.screen.blit(self.font_sm.render(label, True, color), (col2 + 10, ry))
                ry += 14
                self.screen.blit(self.font_sm.render(f"  {desc}", True, GRAY), (col2 + 10, ry))
                ry += 14
        else:
            self.screen.blit(self.font_sm.render("  Level up skills to unlock", True, GRAY), (col2 + 10, ry))
            ry += 14
        ry += 8

        # Skills (only show non-zero skills, sorted by level)
        self.screen.blit(self.font_md.render("Skills", True, UI_HIGHLIGHT), (col2, ry))
        ry += 22
        active_skills = sorted(
            [(s, l) for s, l in player.skills.items() if l > 0],
            key=lambda x: -x[1])
        if not active_skills:
            self.screen.blit(self.font_sm.render("  No skills learned yet", True, GRAY), (col2 + 10, ry))
            ry += 16
        for skill, slevel in active_skills:
            xp_frac = player.skill_xp.get(skill, 0) / (5.0 + slevel * 3.0)
            label = skill.replace("_", " ").title()
            self.screen.blit(self.font_sm.render(f"{label:<16s} Lv.{slevel}", True, UI_TEXT),
                            (col2 + 10, ry))
            bx = col2 + 180
            bw = 70
            pygame.draw.rect(self.screen, DARK_GRAY, (bx, ry + 3, bw, 7))
            pygame.draw.rect(self.screen, UI_HIGHLIGHT, (bx, ry + 3, int(bw * xp_frac), 7))
            ry += 16

        # Record at bottom
        y = max(y, ry) + 8
        if y < cy + ch - 50:
            pygame.draw.line(self.screen, UI_BORDER, (cx + 5, y), (cx + cw - 5, y))
            y += 6
            records = f"Kills: {player.kills}  |  Quests: {player.quests_completed}  |  Distance: {int(player.steps)} tiles"
            self.screen.blit(self.font_sm.render(records, True, GRAY), (cx + 15, y))
            y += 18
            # Titles section
            tracker = getattr(player, 'title_tracker', None)
            if tracker:
                active = tracker.active_title
                if active:
                    self.screen.blit(self.font_sm.render(
                        f"Active Title: {active}", True, (220, 200, 100)), (cx + 15, y))
                    y += 16
                all_titles = tracker.get_all_titles()
                if all_titles:
                    titles_str = ", ".join(all_titles[:5])
                    if len(all_titles) > 5:
                        titles_str += f" (+{len(all_titles) - 5} more)"
                    self.screen.blit(self.font_sm.render(
                        f"Titles: {titles_str}", True, (180, 180, 200)), (cx + 15, y))

        hint = self.font_sm.render("[Escape/C] Close", True, (150, 150, 170))
        self.screen.blit(hint, (cx + cw // 2 - hint.get_width() // 2, cy + ch - 22))

    # ================================================================
    # ================================================================
    # PLANET VIEW (3D globe)
    # ================================================================

    def draw_planet_view(self, dt: float = 0.016, time_sys=None):
        """Draw the 3D planet globe view."""
        if not self.show_planet_view:
            return
        self.planet_view.update(dt)
        self.planet_view.draw(self.screen, self.font_sm, self.font_md, self.font_lg, time_sys)

    def handle_planet_view_input(self, key) -> bool:
        """Handle planet view input. Returns True if consumed."""
        if not self.show_planet_view:
            return False
        if key in (pygame.K_ESCAPE, pygame.K_m):
            self.show_planet_view = False
            return True
        return self.planet_view.handle_input(key)

    # ================================================================
    # EXAMINE (nearby info)
    # ================================================================

    def draw_examine(self, text: str):
        """Draw examine info box at bottom of screen."""
        if not text:
            return
        ew = min(600, SCREEN_WIDTH - 40)
        lines = self._wrap_text(text, ew - 20, self.font_md)
        eh = len(lines) * 20 + 20
        ex = SCREEN_WIDTH // 2 - ew // 2
        ey = SCREEN_HEIGHT - eh - 65

        self._draw_panel(ex, ey, ew, eh, "")
        y = ey + 8
        for line in lines:
            self.screen.blit(self.font_md.render(line, True, UI_TEXT), (ex + 10, y))
            y += 20

    # ================================================================
    # QUEST LOG
    # ================================================================

    def draw_quest_log(self, quests: List[Quest]):
        if not self.show_quest_log:
            return

        qw, qh = 450, 350
        qx = SCREEN_WIDTH // 2 - qw // 2
        qy = SCREEN_HEIGHT // 2 - qh // 2

        self._draw_panel(qx, qy, qw, qh, f"Quest Log ({len(quests)}/5)", theme="quest")

        y = qy + 42
        if not quests:
            self.screen.blit(self.font_md.render("No active quests", True, GRAY),
                            (qx + qw // 2 - 70, y + 20))
        else:
            for quest in quests:
                color = GREEN if quest.completed else UI_TEXT
                self.screen.blit(self.font_md.render(quest.title, True, color), (qx + 15, y))
                prog = self.font_sm.render(f"[{quest.progress_text}]", True,
                                          GREEN if quest.completed else YELLOW)
                self.screen.blit(prog, (qx + qw - prog.get_width() - 15, y + 2))
                y += 20
                self.screen.blit(self.font_sm.render(quest.description, True, GRAY), (qx + 25, y))
                y += 18
                self.screen.blit(self.font_sm.render(f"From: {quest.giver_name}", True, (100, 100, 120)),
                                (qx + 25, y))
                y += 24

        hint = self.font_sm.render("[Escape/Q] Close", True, (150, 150, 170))
        self.screen.blit(hint, (qx + qw // 2 - hint.get_width() // 2, qy + qh - 22))

    # ================================================================
    # PAUSE MENU
    # ================================================================

    def draw_pause_menu(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.screen.blit(overlay, (0, 0))

        title = self.font_xl.render("PAUSED", True, WHITE)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 4))

        hints = [
            "Press ESC to resume",
            "",
            "=== MOVEMENT ===",
            "WASD / Arrows  - Move (always works)",
            "",
            "=== COMBAT ===",
            "Space          - Target/attack nearest enemy",
            "Escape         - Disengage from combat",
            "F1-F5          - Use abilities",
            "",
            "=== INTERACTION ===",
            "E              - Interact (talk/pickup/doors/gather)",
            "T              - Free-text chat with NPC",
            "R              - Recruit NPC to party",
            "Tab            - Cycle nearby NPCs",
            "",
            "=== MENUS (Arrow keys to navigate) ===",
            "I              - Inventory (Tab: cycle categories)",
            "C              - Character sheet",
            "Q              - Quest log / toggle tracker",
            "H              - Historical chronicle",
            "X              - Examine surroundings",
            "G              - Drop item",
            "P              - Toggle auto-play",
        ]
        y = SCREEN_HEIGHT // 4 + 60
        for hint in hints:
            self.screen.blit(self.font_md.render(hint, True, UI_TEXT),
                            (SCREEN_WIDTH // 2 - 180, y))
            y += 24

    def draw_death_screen(self):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((60, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        title = self.font_title.render("YOU DIED", True, RED)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, SCREEN_HEIGHT // 3))

        hint = self.font_lg.render("Press R to respawn", True, UI_TEXT)
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT // 2))

    # ================================================================
    # HISTORICAL CHRONICLE
    # ================================================================

    def draw_chronicle(self, chronicle: 'ChronicleSystem'):
        """Draw the historical chronicle as a scrollable text panel."""
        if not self.show_chronicle:
            return

        cw, ch = 700, 520
        cx = SCREEN_WIDTH // 2 - cw // 2
        cy = SCREEN_HEIGHT // 2 - ch // 2

        self._draw_panel(cx, cy, cw, ch, "", theme="chronicle")

        # Title
        title_surf = self.font_lg.render("THE CHRONICLE OF THE REALM", True, (220, 200, 140))
        self.screen.blit(title_surf, (cx + cw // 2 - title_surf.get_width() // 2, cy + 8))
        pygame.draw.line(self.screen, (120, 110, 80), (cx + 10, cy + 34), (cx + cw - 10, cy + 34))

        # Current era
        era_surf = self.font_sm.render(f"Current Era: {chronicle.get_era_name(999999)}", True, (180, 160, 100))
        self.screen.blit(era_surf, (cx + cw // 2 - era_surf.get_width() // 2, cy + 38))

        # Generate chronicle text
        lines = chronicle.generate_chronicle()

        # Scrollable region
        content_y = cy + 56
        content_h = ch - 80
        max_visible = content_h // 16
        max_scroll = max(0, len(lines) - max_visible)
        self.chronicle_scroll = max(0, min(self.chronicle_scroll, max_scroll))

        visible_lines = lines[self.chronicle_scroll:self.chronicle_scroll + max_visible]

        y = content_y
        for line in visible_lines:
            # Color coding based on content
            color = UI_TEXT
            if line.startswith("===") or line.startswith("---"):
                color = (180, 160, 100)  # era markers in gold
            elif line.startswith("Year "):
                color = UI_HIGHLIGHT  # year headers in blue
            elif line.startswith("  ***"):
                color = (255, 215, 0)  # legendary events in gold
            elif line.startswith("  **"):
                color = (180, 100, 220)  # major events in purple
            elif line.startswith("  *"):
                color = (100, 200, 120)  # notable events in green
            elif line.strip().endswith(":"):
                color = (160, 160, 180)  # season headers

            line_surf = self.font_sm.render(line[:85], True, color)
            self.screen.blit(line_surf, (cx + 15, y))
            y += 16

        # Scroll indicator
        if len(lines) > max_visible:
            scroll_pct = self.chronicle_scroll / max(1, max_scroll)
            bar_h = content_h
            bar_x = cx + cw - 12
            pygame.draw.rect(self.screen, (40, 40, 55), (bar_x, content_y, 6, bar_h))
            thumb_h = max(20, int(bar_h * max_visible / len(lines)))
            thumb_y = content_y + int((bar_h - thumb_h) * scroll_pct)
            pygame.draw.rect(self.screen, UI_HIGHLIGHT, (bar_x, thumb_y, 6, thumb_h))

        # Entry count
        count_surf = self.font_sm.render(f"{len(chronicle.entries)} events recorded", True, GRAY)
        self.screen.blit(count_surf, (cx + 15, cy + ch - 20))

        hint = self.font_sm.render("[Up/Down] Scroll  [Escape/H] Close", True, (150, 150, 170))
        self.screen.blit(hint, (cx + cw // 2 - hint.get_width() // 2, cy + ch - 20))

    def handle_chronicle_input(self, key) -> Optional[str]:
        """Handle chronicle panel input."""
        if not self.show_chronicle:
            return None

        if key in (pygame.K_ESCAPE, pygame.K_h):
            self.show_chronicle = False
            return "close"
        elif key == pygame.K_UP:
            self.chronicle_scroll = max(0, self.chronicle_scroll - 3)
        elif key == pygame.K_DOWN:
            self.chronicle_scroll += 3
        elif key == pygame.K_PAGEUP:
            self.chronicle_scroll = max(0, self.chronicle_scroll - 20)
        elif key == pygame.K_PAGEDOWN:
            self.chronicle_scroll += 20
        elif key == pygame.K_HOME:
            self.chronicle_scroll = 0
        elif key == pygame.K_END:
            self.chronicle_scroll = 99999  # will be clamped

        return None

    def draw_location_banner(self, name: str, alpha: float):
        if alpha <= 0:
            return
        text = self.font_xl.render(name, True, WHITE)
        text.set_alpha(int(255 * alpha))
        self.screen.blit(text,
                        (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 4))
