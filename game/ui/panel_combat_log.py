"""Combat Log panel — scrollable, filterable, color-coded event log.

Toggle with L key. Shows last 20 combat/event messages.
Color-coded: damage=red, healing=green, quest=gold, kingdom=blue.
Auto-hides after 5 seconds of no new messages.
Scrollable with mouse wheel when open.
"""

import time
import pygame
from typing import List, Tuple
from game.settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    UI_BORDER, UI_TEXT, RED, GREEN, YELLOW, BLUE, GRAY,
)


# ================================================================
# MESSAGE CATEGORIES AND COLORS
# ================================================================

COLOR_DAMAGE = (220, 70, 60)
COLOR_HEALING = (80, 200, 100)
COLOR_QUEST = (220, 200, 80)
COLOR_KINGDOM = (100, 140, 220)
COLOR_COMBAT = (200, 120, 80)
COLOR_DEATH = (180, 60, 60)
COLOR_DEFAULT = (180, 180, 180)

# Keywords for auto-categorization
_DAMAGE_WORDS = {"hit", "damage", "slash", "stab", "crush", "burn", "strike",
                 "attack", "hurt", "wound", "critical"}
_HEALING_WORDS = {"heal", "restore", "recover", "potion", "cure", "mend"}
_QUEST_WORDS = {"quest", "reward", "complete", "objective", "bounty", "deliver"}
_KINGDOM_WORDS = {"kingdom", "settlement", "town", "city", "village", "king",
                  "queen", "ruler", "alliance", "war", "treaty"}
_DEATH_WORDS = {"killed", "died", "slain", "defeat", "death", "destroy"}


def _categorize_message(text: str) -> Tuple[int, int, int]:
    """Return a color based on message content."""
    lower = text.lower()

    # Check for death first (subset of damage)
    for w in _DEATH_WORDS:
        if w in lower:
            return COLOR_DEATH

    for w in _DAMAGE_WORDS:
        if w in lower:
            return COLOR_DAMAGE

    for w in _HEALING_WORDS:
        if w in lower:
            return COLOR_HEALING

    for w in _QUEST_WORDS:
        if w in lower:
            return COLOR_QUEST

    for w in _KINGDOM_WORDS:
        if w in lower:
            return COLOR_KINGDOM

    return COLOR_DEFAULT


class CombatLogMessage:
    """A single message in the combat log."""

    def __init__(self, text: str, color: Tuple[int, int, int] = None,
                 timestamp: float = None):
        self.text = text
        self.color = color if color else _categorize_message(text)
        self.timestamp = timestamp if timestamp else time.time()


class CombatLogPanel:
    """Scrollable combat log panel.

    Attributes:
        visible: Whether the panel is manually toggled on.
        auto_visible: Whether the panel is showing due to recent messages.
        messages: List of CombatLogMessage.
        scroll_offset: Current scroll position (0 = bottom/newest).
        max_messages: Maximum messages to keep.
    """

    def __init__(self):
        self.visible = False
        self.auto_visible = False
        self.messages: List[CombatLogMessage] = []
        self.scroll_offset = 0
        self.max_messages = 100  # keep in memory
        self.display_count = 20  # show at once
        self._auto_hide_delay = 5.0  # seconds
        self._last_message_time = 0.0
        self._font_sm = None
        self._font_md = None

    def _ensure_fonts(self):
        """Lazy-init fonts (pygame must be initialized first)."""
        if self._font_sm is None:
            self._font_sm = pygame.font.SysFont("monospace", 13)
            self._font_md = pygame.font.SysFont("monospace", 16)

    def add_message(self, text: str, color: Tuple[int, int, int] = None):
        """Add a message to the log."""
        msg = CombatLogMessage(text, color)
        self.messages.append(msg)
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]
        self._last_message_time = time.time()
        self.auto_visible = True
        # Reset scroll to bottom on new message
        self.scroll_offset = 0

    def toggle(self):
        """Toggle manual visibility."""
        self.visible = not self.visible
        if self.visible:
            self.scroll_offset = 0

    def scroll(self, direction: int):
        """Scroll the log. direction: +1 = up (older), -1 = down (newer)."""
        if not self.is_showing:
            return
        self.scroll_offset += direction
        max_scroll = max(0, len(self.messages) - self.display_count)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))

    @property
    def is_showing(self) -> bool:
        """Whether the panel should be drawn."""
        if self.visible:
            return True
        if self.auto_visible:
            elapsed = time.time() - self._last_message_time
            if elapsed > self._auto_hide_delay:
                self.auto_visible = False
                return False
            return True
        return False

    def draw(self, screen: pygame.Surface):
        """Draw the combat log panel."""
        if not self.is_showing:
            return
        if not self.messages:
            return

        self._ensure_fonts()

        # Panel dimensions and position (right side, middle-ish)
        pw = 380
        line_h = 16
        header_h = 28
        ph = header_h + self.display_count * line_h + 8
        px = SCREEN_WIDTH - pw - 12
        py = SCREEN_HEIGHT // 2 - ph // 2

        # Draw panel background
        panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel_surf.fill((12, 12, 25, 200))
        screen.blit(panel_surf, (px, py))
        pygame.draw.rect(screen, UI_BORDER, (px, py, pw, ph), 1)

        # Header
        title_color = (200, 180, 100) if self.visible else (180, 180, 180)
        title = "Combat Log [L]" if self.visible else "Combat Log"
        title_surf = self._font_md.render(title, True, title_color)
        screen.blit(title_surf, (px + 8, py + 4))
        pygame.draw.line(screen, UI_BORDER,
                         (px + 4, py + header_h - 2),
                         (px + pw - 4, py + header_h - 2))

        # Messages (newest at bottom)
        total = len(self.messages)
        end_idx = total - self.scroll_offset
        start_idx = max(0, end_idx - self.display_count)

        y = py + header_h + 2
        for i in range(start_idx, end_idx):
            msg = self.messages[i]
            # Truncate long messages
            text = msg.text if len(msg.text) <= 45 else msg.text[:42] + "..."
            text_surf = self._font_sm.render(text, True, msg.color)
            screen.blit(text_surf, (px + 8, y))
            y += line_h

        # Scroll indicator
        if total > self.display_count:
            if self.scroll_offset > 0:
                arrow_down = self._font_sm.render("v more v", True, GRAY)
                screen.blit(arrow_down,
                            (px + pw // 2 - arrow_down.get_width() // 2,
                             py + ph - line_h))
            max_scroll = total - self.display_count
            if self.scroll_offset < max_scroll:
                arrow_up = self._font_sm.render("^ more ^", True, GRAY)
                screen.blit(arrow_up,
                            (px + pw // 2 - arrow_up.get_width() // 2,
                             py + header_h + 2))

    def ingest_combat_log(self, combat_messages: List[str]):
        """Import messages from the TacticalCombat.combat_log.

        Only imports messages we haven't seen before (by comparing length).
        """
        existing_count = getattr(self, '_last_ingested_count', 0)
        if len(combat_messages) > existing_count:
            for msg in combat_messages[existing_count:]:
                self.add_message(msg)
        self._last_ingested_count = len(combat_messages)
