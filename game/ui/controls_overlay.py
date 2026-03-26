"""Full-screen controls overlay: press ? to show, ? or Esc to dismiss.

Lists all game controls organised by category on a semi-transparent
dark background. Uses the shared KEY_BINDINGS data from help_screen.py
so both overlays stay in sync.
"""

import pygame
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT, UI_TEXT, UI_HIGHLIGHT
from game.ui.key_bindings import KEY_BINDINGS

# Build a flat list of (category, bindings) for the full overlay.
# We show ALL bindings regardless of context, grouped by category.
# Skip god sub-menus to keep the overlay readable.
_SKIP_TAGS = {"god_events", "god_kingdom", "god_spawn", "god_divine_realm",
              "god_panel", "dead", "quest_board", "fast_travel"}


def _build_all_controls():
    """Merge all KEY_BINDINGS into category groups for the full overlay."""
    groups = []
    seen = {}
    for tag, category, bindings in KEY_BINDINGS:
        if tag in _SKIP_TAGS:
            continue
        if category in seen:
            # Append to existing, avoiding duplicates
            existing = groups[seen[category]][1]
            existing_set = {(k, a) for k, a in existing}
            for k, a in bindings:
                if (k, a) not in existing_set:
                    existing.append((k, a))
        else:
            seen[category] = len(groups)
            groups.append((category, list(bindings)))
    return groups


CONTROLS = _build_all_controls()

# Layout constants
BG_ALPHA = 200
TITLE_COLOR = (255, 215, 80)
KEY_COLOR = (180, 220, 255)
ACTION_COLOR = UI_TEXT
HEADER_COLOR = UI_HIGHLIGHT
COL_WIDTH = 310
TOP_MARGIN = 60
LEFT_MARGIN = 60
LINE_HEIGHT = 18
CAT_GAP = 10


class ControlsOverlay:
    """Full-screen overlay that lists all keybindings."""

    def __init__(self):
        self.visible = False
        self.font_sm: pygame.font.Font | None = None
        self.font_md: pygame.font.Font | None = None
        self.font_lg: pygame.font.Font | None = None
        self._fonts_ready = False

    def _ensure_fonts(self):
        if self._fonts_ready:
            return
        self.font_sm = pygame.font.SysFont("monospace", 13)
        self.font_md = pygame.font.SysFont("monospace", 15, bold=True)
        self.font_lg = pygame.font.SysFont("monospace", 24, bold=True)
        self._fonts_ready = True

    def toggle(self):
        self.visible = not self.visible

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Return True if event was consumed."""
        if event.type != pygame.KEYDOWN:
            return False
        if not self.visible:
            # Open on '?' (shift + /)
            if event.key == pygame.K_SLASH and (event.mod & pygame.KMOD_SHIFT):
                self.visible = True
                return True
            return False
        # Close on '?' or Esc
        if event.key == pygame.K_ESCAPE:
            self.visible = False
            return True
        if event.key == pygame.K_SLASH and (event.mod & pygame.KMOD_SHIFT):
            self.visible = False
            return True
        return True  # consume all keys while overlay is open

    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        self._ensure_fonts()

        # Full-screen dark overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, BG_ALPHA))
        screen.blit(overlay, (0, 0))

        # Title
        title = self.font_lg.render("CONTROLS", True, TITLE_COLOR)
        screen.blit(title, ((SCREEN_WIDTH - title.get_width()) // 2, 18))
        hint = self.font_sm.render(
            "Press ? or Esc to close  |  Shift+H for context help",
            True, (140, 140, 160))
        screen.blit(hint, ((SCREEN_WIDTH - hint.get_width()) // 2, 46))

        # Render controls in two columns
        col_x = LEFT_MARGIN
        y = TOP_MARGIN + 20
        max_y = SCREEN_HEIGHT - 40
        col = 0

        for cat_name, bindings in CONTROLS:
            # Check if category fits in current column
            needed = CAT_GAP + LINE_HEIGHT + len(bindings) * LINE_HEIGHT
            if y + needed > max_y and col == 0:
                col = 1
                col_x = LEFT_MARGIN + COL_WIDTH + 40
                y = TOP_MARGIN + 20

            # Category header
            y += CAT_GAP
            header = self.font_md.render(cat_name, True, HEADER_COLOR)
            screen.blit(header, (col_x, y))
            y += LINE_HEIGHT + 2

            for key_label, action in bindings:
                key_surf = self.font_sm.render(key_label, True, KEY_COLOR)
                screen.blit(key_surf, (col_x + 8, y))
                sep_surf = self.font_sm.render(" - ", True, (100, 100, 110))
                sep_x = col_x + 140
                screen.blit(sep_surf, (sep_x, y))
                act_surf = self.font_sm.render(action, True, ACTION_COLOR)
                screen.blit(act_surf, (sep_x + sep_surf.get_width(), y))
                y += LINE_HEIGHT

            # Switch to second column if running out of space
            if y > max_y and col == 0:
                col = 1
                col_x = LEFT_MARGIN + COL_WIDTH + 40
                y = TOP_MARGIN + 20
