"""Quest Tracker HUD: persistent top-right overlay with compass arrow.

Shows active quest name, current objective, distance, and a rotated
triangle pointing toward the objective target.  Toggle with Q key
(when quest log is not open).
"""

import math
import pygame
from typing import List, Optional, Tuple
from game.settings import SCREEN_WIDTH, UI_TEXT, UI_HIGHLIGHT, GREEN, YELLOW


# Gold color for quest titles
QUEST_GOLD = (255, 215, 80)
COMPASS_COLOR = (240, 100, 60)
BG_COLOR = (10, 10, 25, 190)
BORDER_COLOR = (60, 70, 90)
DIM_TEXT = (130, 130, 150)

TRACKER_WIDTH = 280
TRACKER_X = SCREEN_WIDTH - TRACKER_WIDTH - 12
TRACKER_Y = 50


class QuestTracker:
    """Draws a compact quest tracker HUD with compass arrow."""

    def __init__(self):
        self.visible = True
        self.font_sm: Optional[pygame.font.Font] = None
        self.font_md: Optional[pygame.font.Font] = None
        self._fonts_ready = False

    # ------------------------------------------------------------------
    # Font lazy-init (pygame must be initialised first)
    # ------------------------------------------------------------------
    def _ensure_fonts(self):
        if self._fonts_ready:
            return
        self.font_sm = pygame.font.SysFont("monospace", 13)
        self.font_md = pygame.font.SysFont("monospace", 15, bold=True)
        self._fonts_ready = True

    # ------------------------------------------------------------------
    # Toggle visibility
    # ------------------------------------------------------------------
    def toggle(self):
        self.visible = not self.visible

    # ------------------------------------------------------------------
    # Resolve quest target position
    # ------------------------------------------------------------------
    @staticmethod
    def _quest_target_pos(quest, world) -> Optional[Tuple[float, float]]:
        """Return (x, y) target for a quest, or None."""
        # Try settlement name lookup
        sname = getattr(quest, "settlement", "")
        if sname and world is not None:
            structures = getattr(world, "structures", [])
            for s in structures:
                name = getattr(s, "name", "")
                if name and name.lower() == sname.lower():
                    cx = getattr(s, "center_x", getattr(s, "x", None))
                    cy = getattr(s, "center_y", getattr(s, "y", None))
                    if cx is not None and cy is not None:
                        return (float(cx), float(cy))
        return None

    # ------------------------------------------------------------------
    # Draw rotated compass arrow
    # ------------------------------------------------------------------
    @staticmethod
    def _draw_compass(screen: pygame.Surface, cx: int, cy: int,
                      angle: float, radius: int = 14):
        """Draw a small rotated triangle pointing at *angle* (radians)."""
        # Tip of the arrow
        tip_x = cx + math.cos(angle) * radius
        tip_y = cy + math.sin(angle) * radius
        # Two base points
        base_angle = math.pi * 0.82
        lx = cx + math.cos(angle + base_angle) * (radius * 0.55)
        ly = cy + math.sin(angle + base_angle) * (radius * 0.55)
        rx = cx + math.cos(angle - base_angle) * (radius * 0.55)
        ry = cy + math.sin(angle - base_angle) * (radius * 0.55)
        pygame.draw.polygon(screen, COMPASS_COLOR,
                            [(tip_x, tip_y), (lx, ly), (rx, ry)])
        # Small outline
        pygame.draw.polygon(screen, (255, 255, 255),
                            [(tip_x, tip_y), (lx, ly), (rx, ry)], 1)

    # ------------------------------------------------------------------
    # Main draw
    # ------------------------------------------------------------------
    def draw(self, screen: pygame.Surface, quests, player, world=None):
        """Render the quest tracker HUD.

        Parameters
        ----------
        quests : list of Quest objects (active_quests from QuestSystem)
        player : Player entity (needs .x, .y)
        world  : World object (for settlement position lookup)
        """
        if not self.visible:
            return
        self._ensure_fonts()

        active = [q for q in quests if not q.completed and not q.turned_in]
        if not active:
            return

        quest = active[0]  # primary quest

        # --- Resolve target position ---
        target_pos = self._quest_target_pos(quest, world)
        has_compass = target_pos is not None

        # Calculate distance and angle
        distance = 0.0
        angle = 0.0
        if has_compass:
            dx = target_pos[0] - player.x
            dy = target_pos[1] - player.y
            distance = math.sqrt(dx * dx + dy * dy)
            angle = math.atan2(dy, dx)

        # --- Layout ---
        line_h = 15
        lines_needed = 3  # title, objective, distance/compass
        if not has_compass:
            lines_needed = 2  # no distance line
        panel_h = 8 + lines_needed * line_h + (24 if has_compass else 4)
        tw = TRACKER_WIDTH
        tx = SCREEN_WIDTH - tw - 12
        ty = TRACKER_Y

        # Semi-transparent background
        panel = pygame.Surface((tw, panel_h), pygame.SRCALPHA)
        panel.fill(BG_COLOR)
        screen.blit(panel, (tx, ty))
        pygame.draw.rect(screen, BORDER_COLOR, (tx, ty, tw, panel_h), 1)

        # Header with toggle hint
        header = self.font_sm.render("QUEST TRACKER", True, UI_HIGHLIGHT)
        screen.blit(header, (tx + 6, ty + 2))
        hint = self.font_sm.render("[Q]", True, DIM_TEXT)
        screen.blit(hint, (tx + tw - hint.get_width() - 6, ty + 2))

        y = ty + 18

        # Quest title in gold
        title_text = quest.title[:30]
        title_surf = self.font_md.render(title_text, True, QUEST_GOLD)
        screen.blit(title_surf, (tx + 8, y))
        y += line_h + 2

        # Objective text
        obj_text = quest.progress_text
        if quest.target:
            obj_text = f"{quest.target}: {obj_text}"
        obj_text = obj_text[:36]
        obj_surf = self.font_sm.render(obj_text, True, UI_TEXT)
        screen.blit(obj_surf, (tx + 8, y))
        y += line_h

        # Distance and compass
        if has_compass:
            dist_str = f"{int(distance)} tiles away"
            if distance < 3:
                dist_str = "Nearby!"
            dist_surf = self.font_sm.render(dist_str, True, DIM_TEXT)
            screen.blit(dist_surf, (tx + 8, y))

            # Draw compass arrow to the right of distance text
            compass_cx = tx + tw - 22
            compass_cy = y + 6
            self._draw_compass(screen, compass_cx, compass_cy, angle, radius=10)
            y += line_h + 6

        # Secondary quests indicator
        remaining = len(active) - 1
        if remaining > 0:
            more = self.font_sm.render(f"+{remaining} more active", True, DIM_TEXT)
            screen.blit(more, (tx + tw - more.get_width() - 8,
                               ty + panel_h - 14))
