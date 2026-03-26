"""Relationship Overview panel — shows all known NPCs and relationship status.

Toggle with Shift+R key. Lists NPCs sorted by affinity (friends first, enemies last).
Color-coded: green for friends, red for enemies, grey for strangers.
Scrollable with W/S keys or mouse wheel.

Shows per NPC:
- Name, profession, settlement
- Relationship level (stranger/acquaintance/friend/close friend/rival/enemy)
- Affinity number (-100 to +100)
- Last interaction type and time
"""

import pygame
from typing import List, Optional, Tuple, Dict
from game.settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    UI_BORDER, UI_TEXT,
)


# ================================================================
# COLORS
# ================================================================

HEADER_COLOR = (200, 180, 100)
SUBHEADER_COLOR = (140, 170, 220)
DIM_COLOR = (120, 120, 140)

# Relationship tier colors
COLOR_CLOSE_FRIEND = (80, 220, 120)
COLOR_FRIEND = (100, 200, 130)
COLOR_ACQUAINTANCE = (160, 200, 170)
COLOR_STRANGER = (150, 150, 160)
COLOR_RIVAL = (220, 160, 80)
COLOR_ENEMY = (220, 80, 70)

STATUS_COLORS = {
    "close_friend": COLOR_CLOSE_FRIEND,
    "friend": COLOR_FRIEND,
    "acquaintance": COLOR_ACQUAINTANCE,
    "stranger": COLOR_STRANGER,
    "rival": COLOR_RIVAL,
    "enemy": COLOR_ENEMY,
    "ally": COLOR_CLOSE_FRIEND,
}

STATUS_LABELS = {
    "close_friend": "Close Friend",
    "friend": "Friend",
    "acquaintance": "Acquaintance",
    "stranger": "Stranger",
    "rival": "Rival",
    "enemy": "Enemy",
    "ally": "Ally",
}

# Affinity bar gradient
BAR_POSITIVE = (80, 200, 120)
BAR_NEGATIVE = (220, 80, 70)
BAR_BG = (40, 40, 55)


# ================================================================
# NPC RELATIONSHIP ENTRY
# ================================================================

class _RelEntry:
    """Temporary struct for sorting/display."""
    __slots__ = ('name', 'profession', 'settlement', 'status', 'affinity',
                 'last_interaction', 'last_time', 'interaction_count')

    def __init__(self):
        self.name = ""
        self.profession = ""
        self.settlement = ""
        self.status = "stranger"
        self.affinity = 0
        self.last_interaction = ""
        self.last_time = 0.0
        self.interaction_count = 0


# ================================================================
# PANEL CLASS
# ================================================================

class RelationshipPanel:
    """Scrollable relationship overview panel."""

    def __init__(self):
        self.visible = False
        self._font_sm = None
        self._font_md = None
        self._font_lg = None
        self.scroll_offset = 0
        self._max_scroll = 0
        self._entries: List[_RelEntry] = []
        self._cache_timer = 0.0

    def _ensure_fonts(self):
        if self._font_sm is None:
            self._font_sm = pygame.font.SysFont("monospace", 13)
            self._font_md = pygame.font.SysFont("monospace", 16)
            self._font_lg = pygame.font.SysFont("monospace", 22)

    def toggle(self):
        self.visible = not self.visible
        self.scroll_offset = 0
        self._cache_timer = 0.0  # force refresh

    def scroll(self, direction: int):
        """Scroll panel content. direction: positive=down, negative=up."""
        if self.visible:
            self.scroll_offset = max(0, min(self._max_scroll,
                                            self.scroll_offset + direction))

    def _build_entries(self, player, npcs, social_system):
        """Build sorted list of relationship entries from social system data."""
        entries = []
        player_name = getattr(player, 'name', 'Player')

        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue

            entry = _RelEntry()
            entry.name = getattr(npc, 'name', '?')
            entry.profession = getattr(npc, 'profession', '')
            entry.settlement = getattr(npc, 'home_settlement', '')

            # Get relationship data from social system
            if social_system:
                rel = social_system.get_rel(player_name, entry.name)
                entry.affinity = int(rel.trust)
                entry.status = rel.status
                entry.interaction_count = rel.interaction_count
                entry.last_time = rel.last_interaction
            else:
                # Fallback: use player_relationship attribute
                entry.affinity = int(getattr(npc, 'player_relationship', 0))
                entry.status = _affinity_to_status(entry.affinity)
                entry.interaction_count = 0
                entry.last_time = 0.0

            # Determine last interaction type from NPC memories
            entry.last_interaction = _get_last_interaction(npc)

            entries.append(entry)

        # Sort by affinity: friends first (highest), enemies last (lowest)
        entries.sort(key=lambda e: e.affinity, reverse=True)
        self._entries = entries

    def draw(self, screen: pygame.Surface, player, npcs, social_system=None,
             time_system=None):
        """Draw the relationship panel overlay."""
        if not self.visible:
            return

        self._ensure_fonts()

        # Rebuild entries periodically (every 2 seconds)
        self._cache_timer -= 1.0 / 60.0
        if self._cache_timer <= 0:
            self._build_entries(player, npcs, social_system)
            self._cache_timer = 2.0

        # Panel dimensions
        pw = min(700, SCREEN_WIDTH - 40)
        ph = SCREEN_HEIGHT - 80
        px = (SCREEN_WIDTH - pw) // 2
        py = 40

        # Background
        bg = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bg.fill((20, 20, 35, 230))
        screen.blit(bg, (px, py))
        pygame.draw.rect(screen, (80, 80, 120), (px, py, pw, ph), 1)

        # Title
        title = self._font_lg.render("Relationships", True, HEADER_COLOR)
        screen.blit(title, (px + pw // 2 - title.get_width() // 2, py + 8))

        # Column headers
        header_y = py + 38
        self._font_sm_render(screen, "Name", px + 10, header_y, SUBHEADER_COLOR)
        self._font_sm_render(screen, "Profession", px + 160, header_y, SUBHEADER_COLOR)
        self._font_sm_render(screen, "Settlement", px + 310, header_y, SUBHEADER_COLOR)
        self._font_sm_render(screen, "Status", px + 460, header_y, SUBHEADER_COLOR)
        self._font_sm_render(screen, "Affinity", px + 580, header_y, SUBHEADER_COLOR)

        # Separator line
        pygame.draw.line(screen, (60, 60, 80),
                         (px + 8, header_y + 16), (px + pw - 8, header_y + 16))

        # Scrollable entries
        entry_start_y = header_y + 22
        entry_height = 32
        visible_count = (ph - (entry_start_y - py) - 30) // entry_height
        self._max_scroll = max(0, len(self._entries) - visible_count)

        clip_rect = pygame.Rect(px, entry_start_y, pw, visible_count * entry_height)
        screen.set_clip(clip_rect)

        for i in range(self.scroll_offset,
                       min(len(self._entries), self.scroll_offset + visible_count)):
            entry = self._entries[i]
            ey = entry_start_y + (i - self.scroll_offset) * entry_height

            # Alternating row background
            if (i - self.scroll_offset) % 2 == 0:
                row_bg = pygame.Surface((pw - 16, entry_height - 2), pygame.SRCALPHA)
                row_bg.fill((30, 30, 50, 100))
                screen.blit(row_bg, (px + 8, ey))

            # Status color for the row
            status_color = STATUS_COLORS.get(entry.status, COLOR_STRANGER)

            # Name (colored by status)
            self._font_sm_render(screen, _truncate(entry.name, 18),
                                 px + 10, ey + 4, status_color)

            # Profession
            self._font_sm_render(screen, _truncate(entry.profession, 16),
                                 px + 160, ey + 4, DIM_COLOR)

            # Settlement
            self._font_sm_render(screen, _truncate(entry.settlement, 16),
                                 px + 310, ey + 4, DIM_COLOR)

            # Status label
            status_label = STATUS_LABELS.get(entry.status, entry.status)
            self._font_sm_render(screen, status_label,
                                 px + 460, ey + 4, status_color)

            # Affinity bar + number
            _draw_affinity_bar(screen, px + 580, ey + 6, 80, 10, entry.affinity)
            aff_str = f"{entry.affinity:+d}"
            aff_color = BAR_POSITIVE if entry.affinity > 0 else (
                BAR_NEGATIVE if entry.affinity < 0 else DIM_COLOR)
            self._font_sm_render(screen, aff_str,
                                 px + 665, ey + 4, aff_color)

            # Last interaction (second line, smaller)
            if entry.last_interaction:
                self._font_sm_render(screen, entry.last_interaction,
                                     px + 30, ey + 17, (100, 100, 120))

        screen.set_clip(None)

        # Scroll indicator
        if self._max_scroll > 0:
            _draw_scrollbar(screen, px + pw - 12, entry_start_y,
                            6, visible_count * entry_height,
                            self.scroll_offset, self._max_scroll + visible_count,
                            visible_count)

        # Footer
        footer_y = py + ph - 22
        count_text = f"{len(self._entries)} NPCs known"
        self._font_sm_render(screen, count_text, px + 10, footer_y, DIM_COLOR)
        hint = "[Shift+R] Close  [W/S or Scroll] Navigate"
        self._font_sm_render(screen, hint,
                             px + pw - self._font_sm.size(hint)[0] - 10,
                             footer_y, DIM_COLOR)

    def _font_sm_render(self, screen, text, x, y, color):
        """Render small font text at position."""
        surf = self._font_sm.render(str(text), True, color)
        screen.blit(surf, (x, y))


# ================================================================
# HELPER FUNCTIONS
# ================================================================

def _affinity_to_status(affinity: int) -> str:
    """Convert raw affinity number to status label."""
    if affinity >= 60:
        return "close_friend"
    elif affinity >= 30:
        return "friend"
    elif affinity >= 10:
        return "acquaintance"
    elif affinity >= -10:
        return "stranger"
    elif affinity >= -30:
        return "rival"
    return "enemy"


def _get_last_interaction(npc) -> str:
    """Extract last interaction description from NPC memories."""
    memories = getattr(npc, 'memories', [])
    if not memories:
        return ""
    # Search backward for social/combat memory involving the player
    for mem in reversed(memories):
        cat = getattr(mem, 'category', '') if hasattr(mem, 'category') else ''
        desc = getattr(mem, 'description', str(mem)) if hasattr(mem, 'description') else str(mem)
        if isinstance(mem, dict):
            cat = mem.get('category', '')
            desc = mem.get('description', '')
        if cat in ('social', 'combat', 'trade', 'witness'):
            return _truncate(desc, 50)
    return ""


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 2] + ".."


def _draw_affinity_bar(screen, x, y, width, height, affinity):
    """Draw a colored affinity bar: green for positive, red for negative."""
    # Background
    pygame.draw.rect(screen, BAR_BG, (x, y, width, height))

    # Midpoint
    mid = x + width // 2

    if affinity > 0:
        # Positive: fill right from center
        fill_w = min(width // 2, int((affinity / 100.0) * (width // 2)))
        pygame.draw.rect(screen, BAR_POSITIVE, (mid, y, fill_w, height))
    elif affinity < 0:
        # Negative: fill left from center
        fill_w = min(width // 2, int((abs(affinity) / 100.0) * (width // 2)))
        pygame.draw.rect(screen, BAR_NEGATIVE, (mid - fill_w, y, fill_w, height))

    # Center line
    pygame.draw.line(screen, (100, 100, 120), (mid, y), (mid, y + height))

    # Border
    pygame.draw.rect(screen, (60, 60, 80), (x, y, width, height), 1)


def _draw_scrollbar(screen, x, y, width, height, offset, total, visible):
    """Draw a simple scrollbar indicator."""
    if total <= 0 or visible >= total:
        return

    # Track
    pygame.draw.rect(screen, (40, 40, 55), (x, y, width, height))

    # Thumb
    thumb_h = max(20, int(height * visible / total))
    thumb_y = y + int((height - thumb_h) * offset / max(1, total - visible))
    pygame.draw.rect(screen, (80, 80, 110), (x, thumb_y, width, thumb_h))
