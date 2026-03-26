"""Mouse targeting system for spell and ranged attack aiming.

Provides a state machine that manages targeting modes (spell, throw, ranged)
and draws targeting overlays (range circles, crosshairs, AoE previews).
"""

import math
import pygame
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT


# Targeting states
IDLE = 0
SPELL_TARGET = 1
THROW_TARGET = 2
RANGED_TARGET = 3


class TargetingSystem:
    """State machine for mouse-based targeting of spells, throws, ranged."""

    def __init__(self):
        self.state = IDLE
        self.spell_name = None
        self.spell_data = None       # Spell object from SPELL_REGISTRY
        self.throw_item = None
        self.throw_range = 0.0
        self.max_range = 0.0
        self.target_type = "single"  # single, aoe, ground, self
        self.aoe_radius = 0.0
        self.mouse_x = 0
        self.mouse_y = 0
        self._hover_entity = None

    # ----------------------------------------------------------
    # State transitions
    # ----------------------------------------------------------

    def begin_spell_target(self, spell_name, spell_data, caster_level=1):
        """Enter spell targeting mode with level-scaled range/AoE."""
        self.state = SPELL_TARGET
        self.spell_name = spell_name
        self.spell_data = spell_data
        base_range = getattr(spell_data, 'range_tiles', 8.0)
        base_aoe = getattr(spell_data, 'area', 0.0)
        # Scale range and AoE with caster level
        self.max_range = base_range + (caster_level // 3)
        self.aoe_radius = base_aoe * (1.0 + 0.05 * caster_level) if base_aoe > 0 else 0.0

        # Determine target type from spell data
        targets = getattr(spell_data, 'targets', 'single')
        if targets == "aoe":
            self.target_type = "aoe"
        elif targets == "self":
            self.target_type = "self"
        elif targets in ("single", "chain"):
            self.target_type = "single"
        elif targets == "ally":
            self.target_type = "single"
        else:
            self.target_type = "ground"

    def begin_throw_target(self, item, throw_range):
        """Enter throw targeting mode."""
        self.state = THROW_TARGET
        self.throw_item = item
        self.throw_range = throw_range
        self.max_range = throw_range
        self.target_type = "single"
        self.aoe_radius = 0.0
        self.spell_name = None
        self.spell_data = None

    def begin_ranged_target(self, max_range):
        """Enter ranged attack targeting mode."""
        self.state = RANGED_TARGET
        self.max_range = max_range
        self.target_type = "single"
        self.aoe_radius = 0.0
        self.spell_name = None
        self.spell_data = None

    def cancel(self):
        """Return to IDLE, clearing all targeting state."""
        self.state = IDLE
        self.spell_name = None
        self.spell_data = None
        self.throw_item = None
        self.throw_range = 0.0
        self.max_range = 0.0
        self.target_type = "single"
        self.aoe_radius = 0.0
        self._hover_entity = None

    def is_active(self):
        """True if currently in any targeting mode."""
        return self.state != IDLE

    # ----------------------------------------------------------
    # Input handling
    # ----------------------------------------------------------

    def update_mouse(self, mx, my):
        """Store current mouse position for drawing."""
        self.mouse_x = mx
        self.mouse_y = my

    def handle_click(self, mouse_x, mouse_y, camera, world, creatures,
                     npcs, player):
        """Process a targeting click. Returns result dict or None.

        Result dict: {"world_x", "world_y", "entity", "valid"}
        """
        if self.state == IDLE:
            return None

        wx, wy = camera.screen_to_world(mouse_x, mouse_y)

        # Find nearest entity to click point — generous radius for usability
        entity = self._find_nearest_entity(wx, wy, creatures, npcs, player,
                                            radius=1.5)

        # Validate range
        dx = wx - player.x
        dy = wy - player.y
        dist = math.sqrt(dx * dx + dy * dy)
        in_range = dist <= self.max_range + 1.0  # slight forgiveness on range

        # Validate based on target type
        valid = False
        if self.target_type == "single":
            # Single target: need an entity, but also allow clicking ground
            # near an entity (finds closest within generous radius)
            if entity is not None and in_range:
                valid = True
            elif in_range:
                # No entity found nearby — still allow if close to any hostile
                entity = self._find_nearest_entity(
                    wx, wy, creatures, npcs, player, radius=3.0)
                valid = entity is not None
        elif self.target_type == "aoe":
            valid = in_range  # AoE: just needs to be in range
        elif self.target_type == "ground":
            valid = in_range
        elif self.target_type == "self":
            valid = True
            entity = player
            wx, wy = player.x, player.y

        result = {
            "world_x": wx,
            "world_y": wy,
            "entity": entity,
            "valid": valid,
        }
        return result

    def get_hover_entity(self, mouse_x, mouse_y, camera, creatures, npcs):
        """Find entity under cursor for tooltip display."""
        wx, wy = camera.screen_to_world(mouse_x, mouse_y)
        entity = self._find_nearest_entity(wx, wy, creatures, npcs, None,
                                            radius=1.5)
        self._hover_entity = entity
        return entity

    @property
    def hover_entity(self):
        return self._hover_entity

    def _find_nearest_entity(self, wx, wy, creatures, npcs, player,
                             radius=1.5):
        """Find the entity nearest to world coords within radius tiles."""
        best = None
        best_dist = radius

        for c in creatures:
            if not getattr(c, 'alive', True):
                continue
            dx = c.x - wx
            dy = c.y - wy
            d = math.sqrt(dx * dx + dy * dy)
            if d < best_dist:
                best_dist = d
                best = c

        for n in npcs:
            if not getattr(n, 'alive', True):
                continue
            dx = n.x - wx
            dy = n.y - wy
            d = math.sqrt(dx * dx + dy * dy)
            if d < best_dist:
                best_dist = d
                best = n

        return best

    # ----------------------------------------------------------
    # Drawing
    # ----------------------------------------------------------

    def draw(self, screen, camera, player):
        """Draw targeting overlay when active."""
        if self.state == IDLE:
            return

        ts = camera.tile_size
        px, py = camera.world_to_screen(player.x, player.y)

        # Mouse position in world coords
        wx, wy = camera.screen_to_world(self.mouse_x, self.mouse_y)
        mx_screen, my_screen = self.mouse_x, self.mouse_y

        # Distance from player to cursor in tiles
        dx = wx - player.x
        dy = wy - player.y
        dist = math.sqrt(dx * dx + dy * dy)
        in_range = dist <= self.max_range

        # Range circle around player
        range_px = int(self.max_range * ts)
        if range_px > 5:
            range_color = (255, 255, 255, 60)
            _draw_circle_alpha(screen, range_color,
                               (int(px), int(py)), range_px, 1)

        # Line from player to cursor (for projectile spells)
        if self.target_type in ("single", "ground"):
            line_color = (100, 255, 100) if in_range else (255, 80, 80)
            pygame.draw.line(screen, line_color,
                             (int(px), int(py)),
                             (mx_screen, my_screen), 1)

        # AoE radius preview circle
        if self.target_type == "aoe" and self.aoe_radius > 0:
            aoe_px = int(self.aoe_radius * ts)
            aoe_color = (255, 200, 80, 80) if in_range else (255, 80, 80, 80)
            _draw_circle_alpha(screen, aoe_color,
                               (mx_screen, my_screen), aoe_px, 2)
            # Fill with transparent color
            aoe_fill = pygame.Surface((aoe_px * 2, aoe_px * 2), pygame.SRCALPHA)
            fill_color = (255, 200, 80, 25) if in_range else (255, 80, 80, 25)
            pygame.draw.circle(aoe_fill, fill_color,
                               (aoe_px, aoe_px), aoe_px)
            screen.blit(aoe_fill,
                        (mx_screen - aoe_px, my_screen - aoe_px))

        # Crosshair at mouse position
        ch_size = 10
        ch_color = (100, 255, 100) if in_range else (255, 80, 80)
        pygame.draw.line(screen, ch_color,
                         (mx_screen - ch_size, my_screen),
                         (mx_screen + ch_size, my_screen), 1)
        pygame.draw.line(screen, ch_color,
                         (mx_screen, my_screen - ch_size),
                         (mx_screen, my_screen + ch_size), 1)

        # Highlight entity under cursor
        if self._hover_entity is not None:
            ent = self._hover_entity
            ex, ey = camera.world_to_screen(ent.x, ent.y)
            highlight_color = (100, 255, 100) if in_range else (255, 80, 80)
            pygame.draw.circle(screen, highlight_color,
                               (int(ex), int(ey)), ts // 2 + 2, 2)

        # Mode label
        label = self._get_mode_label()
        if label:
            font = pygame.font.SysFont("monospace", 12)
            txt = font.render(label, True, (220, 220, 240))
            screen.blit(txt, (mx_screen + 14, my_screen - 8))

        # Cancel hint
        hint_font = pygame.font.SysFont("monospace", 11)
        hint = hint_font.render("Right-click to cancel", True, (180, 180, 200))
        screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2,
                           SCREEN_HEIGHT - 70))

    def _get_mode_label(self):
        """Get display label for current targeting mode."""
        if self.state == SPELL_TARGET and self.spell_name:
            name = self.spell_name.replace("_", " ").title()
            return name
        elif self.state == THROW_TARGET and self.throw_item:
            return f"Throw {getattr(self.throw_item, 'name', 'item')}"
        elif self.state == RANGED_TARGET:
            return "Ranged Attack"
        return None


def _draw_circle_alpha(surface, color, center, radius, width):
    """Draw a circle with alpha transparency."""
    if radius <= 0:
        return
    if len(color) == 4:
        # RGBA - need temporary surface
        size = radius * 2 + width * 2 + 4
        temp = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(temp, color, (size // 2, size // 2), radius, width)
        surface.blit(temp, (center[0] - size // 2, center[1] - size // 2))
    else:
        pygame.draw.circle(surface, color, center, radius, width)
