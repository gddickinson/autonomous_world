"""Context-aware help screen that shows only relevant key bindings.

Activate with Shift+H or ? (Shift+/). Shows keys for the current game
state: god mode, panels, combat, dialog, etc.

Uses the shared KEY_BINDINGS data from key_bindings.py so controls_overlay.py
and this module stay in sync.
"""

import pygame
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT, UI_TEXT, UI_HIGHLIGHT
from game.ui.key_bindings import KEY_BINDINGS, get_bindings_for_context


def detect_context(game):
    """Inspect game state and return a set of context tags."""
    tags = {"universal", "system"}

    player = game.player
    is_god = getattr(player, 'god', False)
    dead = getattr(game, 'dead', False)

    # Dead state overrides most things
    if dead:
        tags.add("dead")
        return tags

    # Check panels first (they block other input)
    ui = game.ui
    if getattr(ui, 'dialog_active', False):
        tags.add("dialog")
        return tags
    if getattr(ui, 'shop_active', False):
        tags.add("shop")
        return tags
    if getattr(ui, 'show_inventory', False):
        tags.add("inventory")
        return tags
    if getattr(ui, 'show_character', False):
        tags.add("character")
        return tags
    if getattr(ui, 'show_quest_log', False):
        tags.add("quest_log")
        return tags
    if getattr(ui, 'show_chronicle', False):
        tags.add("chronicle")
        return tags
    if getattr(ui, 'show_world_map', False):
        tags.add("world_map")
        return tags
    if getattr(ui, 'show_planet_view', False):
        tags.add("planet_view")
        return tags
    if hasattr(game, 'crafting_ui') and game.crafting_ui.active:
        tags.add("crafting")
        return tags
    if hasattr(game, 'skill_tree_ui') and game.skill_tree_ui.active:
        tags.add("skill_tree")
        return tags
    if hasattr(game, 'fast_travel_ui') and game.fast_travel_ui.active:
        tags.add("fast_travel")
        return tags
    if getattr(game, 'quest_board_active', False):
        tags.add("quest_board")
        return tags

    # Movement is available when no blocking panel is open
    tags.add("movement")

    # God mode
    if is_god:
        tags.add("god")
        # Check sub-states
        dc = getattr(game, 'divine_commands', None)
        if dc and dc.active_menu:
            menu = dc.active_menu
            if menu == "event":
                tags.add("god_events")
            elif menu == "kingdom":
                tags.add("god_kingdom")
            elif menu == "spawn":
                tags.add("god_spawn")
        god_ui = getattr(game, 'god_ui', None)
        if god_ui and god_ui.panel_visible:
            tags.add("god_panel")
        dr = getattr(game, 'divine_realm', None)
        if dr and dr.in_divine_realm:
            tags.add("god_divine_realm")
    else:
        # Mortal mode
        tags.add("mortal")
        tags.add("panels")

        # Combat
        combat = getattr(game, 'combat', None)
        if combat and combat.active:
            tags.add("combat")

        # Spellcaster
        if getattr(player, 'is_spellcaster', False):
            tags.add("spellcaster")

        # 3D camera
        if getattr(game, 'view_mode', '') == '3d':
            tags.add("camera_3d")

        # NPC nearby
        if getattr(game, 'nearby_npc', None):
            tags.add("npc_nearby")

        # Building / tavern
        interior = getattr(player, 'interior_state', None)
        if interior and interior.is_inside:
            tags.add("building")
        bkind = getattr(player, '_current_building_kind', '')
        if bkind == 'tavern':
            tags.add("tavern")

    return tags


# ------------------------------------------------------------------ #
# Rendering
# ------------------------------------------------------------------ #

BG_ALPHA = 210
TITLE_COLOR = (255, 215, 80)
KEY_COLOR = (180, 220, 255)
ACTION_COLOR = UI_TEXT
HEADER_COLOR = UI_HIGHLIGHT
COL_WIDTH = 290
TOP_MARGIN = 55
LEFT_MARGIN = 50
LINE_HEIGHT = 18
CAT_GAP = 8


class HelpScreen:
    """Context-aware help overlay."""

    def __init__(self):
        self.visible = False
        self._fonts_ready = False
        self.font_sm = None
        self.font_md = None
        self.font_lg = None

    def _ensure_fonts(self):
        if self._fonts_ready:
            return
        self.font_sm = pygame.font.SysFont("monospace", 13)
        self.font_md = pygame.font.SysFont("monospace", 15, bold=True)
        self.font_lg = pygame.font.SysFont("monospace", 22, bold=True)
        self._fonts_ready = True

    def toggle(self):
        self.visible = not self.visible

    def handle_event(self, event):
        """Return True if event was consumed."""
        if event.type != pygame.KEYDOWN:
            return False

        mods = event.mod if hasattr(event, 'mod') else pygame.key.get_mods()

        if not self.visible:
            # Open on Shift+H
            if event.key == pygame.K_h and (mods & pygame.KMOD_SHIFT):
                self.visible = True
                return True
            return False

        # Close on Esc, ?, or Shift+H
        if event.key == pygame.K_ESCAPE:
            self.visible = False
            return True
        if event.key == pygame.K_h and (mods & pygame.KMOD_SHIFT):
            self.visible = False
            return True
        if event.key == pygame.K_SLASH and (mods & pygame.KMOD_SHIFT):
            self.visible = False
            return True
        # Consume all keys while visible
        return True

    def draw(self, screen, game):
        """Draw the context-aware help overlay."""
        if not self.visible:
            return
        self._ensure_fonts()

        tags = detect_context(game)
        groups = get_bindings_for_context(tags)

        # Full-screen dark overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, BG_ALPHA))
        screen.blit(overlay, (0, 0))

        # Title
        mode_label = "GOD MODE" if "god" in tags else "MORTAL"
        title_text = f"HELP - {mode_label}"
        title = self.font_lg.render(title_text, True, TITLE_COLOR)
        screen.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, 14))

        # Context hint
        ctx_parts = []
        for t in sorted(tags):
            if t not in ("universal", "system", "movement", "mortal",
                         "god", "panels"):
                ctx_parts.append(t.replace("_", " "))
        ctx_str = ", ".join(ctx_parts) if ctx_parts else "default"
        hint = self.font_sm.render(
            f"Context: {ctx_str}  |  Shift+H / ? / Esc to close",
            True, (140, 140, 160))
        screen.blit(hint, ((SCREEN_WIDTH - hint.get_width()) // 2, 38))

        # Render in columns
        col_x = LEFT_MARGIN
        y = TOP_MARGIN + 10
        max_y = SCREEN_HEIGHT - 30
        col = 0
        max_cols = max(1, (SCREEN_WIDTH - LEFT_MARGIN * 2) // (COL_WIDTH + 30))

        for cat_name, bindings in groups:
            needed = CAT_GAP + LINE_HEIGHT + len(bindings) * LINE_HEIGHT + 4
            if y + needed > max_y:
                col += 1
                if col >= max_cols:
                    break  # out of screen space
                col_x = LEFT_MARGIN + col * (COL_WIDTH + 30)
                y = TOP_MARGIN + 10

            # Category header
            y += CAT_GAP
            header = self.font_md.render(cat_name, True, HEADER_COLOR)
            screen.blit(header, (col_x, y))
            y += LINE_HEIGHT + 2

            for key_label, action in bindings:
                key_surf = self.font_sm.render(key_label, True, KEY_COLOR)
                screen.blit(key_surf, (col_x + 6, y))
                sep_x = col_x + 120
                sep = self.font_sm.render(" - ", True, (100, 100, 110))
                screen.blit(sep, (sep_x, y))
                act = self.font_sm.render(action, True, ACTION_COLOR)
                screen.blit(act, (sep_x + sep.get_width(), y))
                y += LINE_HEIGHT

        # Footer
        footer = self.font_sm.render(
            "Full reference: CONTROLS.md", True, (110, 110, 130))
        screen.blit(footer, ((SCREEN_WIDTH - footer.get_width()) // 2,
                             SCREEN_HEIGHT - 22))
