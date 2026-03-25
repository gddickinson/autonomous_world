"""Contextual help tooltips for interactive objects near the player.

Shows small grey hint text near the bottom of the screen when the player
is close to an interactive object (door, NPC, chest, crafting station, etc.).
Only the most relevant tooltip (nearest interactive object) is shown.
"""

import math
import pygame
from typing import Optional, Tuple, List
from game.settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE,
    DOOR, CHEST, STAIRS_DOWN, STAIRS_UP, ANVIL, FORGE_FIRE,
    FIREPLACE, LOCKED_DOOR,
)

# Interaction radius (tiles) for detecting nearby interactive objects
INTERACT_RADIUS = 3.0

# Tooltip definitions: (tile_type_or_kind, hint_text)
TILE_TOOLTIPS = {
    DOOR:        "Press E to enter",
    LOCKED_DOOR: "Locked door",
    CHEST:       "Press E to open",
    STAIRS_DOWN: "Press E to descend",
    STAIRS_UP:   "Press E to ascend",
    ANVIL:       "Press U to craft (Smithing)",
    FORGE_FIRE:  "Press U to craft (Smelting)",
}

# Building function name -> tooltip (checked via building_function_cache)
BUILDING_TOOLTIPS = {
    "tavern":    "Press E for Quest Board / Message Board",
    "inn":       "Press E to rest",
    "smithy":    "Press U to craft",
    "workshop":  "Press U to craft",
}


class TooltipSystem:
    """Manages contextual help tooltips shown near the bottom of the screen."""

    def __init__(self, font: pygame.font.Font):
        self.font = font
        self._last_tooltip: str = ""
        self._tooltip_alpha: float = 0.0  # smooth fade in/out

    def update_and_draw(
        self,
        screen: pygame.Surface,
        player,
        world,
        npcs: list,
        creatures: list,
        building_cache: dict,
        dt: float,
        any_panel_open: bool = False,
    ):
        """Find the nearest interactive object and draw a tooltip if appropriate.

        Args:
            screen: pygame display surface
            player: Player object with x, y attributes
            world: World object with tiles grid
            npcs: list of NPC objects
            creatures: list of Creature objects
            building_cache: dict mapping (x,y) -> building function name
            dt: delta time in seconds
            any_panel_open: if True, suppress tooltips
        """
        if any_panel_open:
            self._fade_out(dt)
            self._draw_tooltip(screen)
            return

        # Skip if player is inside a building interior
        interior = getattr(player, 'interior_state', None)
        if interior and getattr(interior, 'is_inside', False):
            self._fade_out(dt)
            self._draw_tooltip(screen)
            return

        tooltip = self._find_best_tooltip(player, world, npcs, creatures,
                                          building_cache)

        if tooltip:
            self._last_tooltip = tooltip
            # Fade in
            self._tooltip_alpha = min(1.0, self._tooltip_alpha + dt * 5.0)
        else:
            # Fade out
            self._fade_out(dt)

        self._draw_tooltip(screen)

    def _fade_out(self, dt: float):
        """Smoothly fade out the tooltip."""
        self._tooltip_alpha = max(0.0, self._tooltip_alpha - dt * 4.0)

    def _find_best_tooltip(
        self,
        player,
        world,
        npcs: list,
        creatures: list,
        building_cache: dict,
    ) -> Optional[str]:
        """Find the nearest interactive object and return its tooltip string."""
        px, py = player.x, player.y
        ipx, ipy = int(px), int(py)
        best_tooltip: Optional[str] = None
        best_dist: float = INTERACT_RADIUS + 1.0

        # 1. Check nearby tiles for interactive objects
        scan = int(INTERACT_RADIUS) + 1
        for dy in range(-scan, scan + 1):
            for dx in range(-scan, scan + 1):
                tx, ty = ipx + dx, ipy + dy
                if not (0 <= tx < world.width and 0 <= ty < world.height):
                    continue
                dist = math.sqrt((px - tx) ** 2 + (py - ty) ** 2)
                if dist >= best_dist:
                    continue

                tile = world.tiles[ty][tx]

                # Direct tile tooltip
                tip = TILE_TOOLTIPS.get(tile)
                if tip:
                    # For doors, include the structure name if available
                    if tile == DOOR:
                        struct = world.get_structure_at(float(tx), float(ty))
                        if struct:
                            tip = f"Press E to enter {struct.name}"
                    best_tooltip = tip
                    best_dist = dist
                    continue

                # Building function tooltip (tavern, smithy, etc.)
                bfunc = building_cache.get((tx, ty), "")
                if bfunc:
                    for key, btip in BUILDING_TOOLTIPS.items():
                        if key in bfunc:
                            if dist < best_dist:
                                best_tooltip = btip
                                best_dist = dist
                            break

        # 2. Check nearby NPCs (closer than tile matches take priority)
        for npc in npcs:
            if not getattr(npc, 'alive', False):
                continue
            dist = math.sqrt((px - npc.x) ** 2 + (py - npc.y) ** 2)
            if dist < best_dist and dist < INTERACT_RADIUS:
                name = getattr(npc, 'name', 'someone')
                best_tooltip = f"Press E to talk to {name}"
                best_dist = dist

        # 3. Check nearby creatures for tameable ones
        for cr in creatures:
            if not getattr(cr, 'alive', False):
                continue
            dist = math.sqrt((px - cr.x) ** 2 + (py - cr.y) ** 2)
            if dist >= best_dist or dist >= INTERACT_RADIUS:
                continue
            tameable = getattr(cr, 'tameable', False)
            tamed = getattr(cr, 'tamed', False)
            if tameable and not tamed:
                kind = getattr(cr, 'kind', 'creature')
                best_tooltip = f"Press T to tame {kind}"
                best_dist = dist
            elif tamed:
                kind = getattr(cr, 'kind', 'creature')
                best_tooltip = f"Press M to mount {kind}"
                best_dist = dist

        return best_tooltip

    def _draw_tooltip(self, screen: pygame.Surface):
        """Render the current tooltip at the bottom of the screen."""
        if self._tooltip_alpha <= 0.01 or not self._last_tooltip:
            return

        alpha = int(self._tooltip_alpha * 200)
        text_alpha = int(self._tooltip_alpha * 255)

        txt_surf = self.font.render(self._last_tooltip, True, (200, 200, 210))
        if text_alpha < 255:
            txt_surf.set_alpha(text_alpha)

        tw, th = txt_surf.get_size()
        x = SCREEN_WIDTH // 2 - tw // 2
        y = SCREEN_HEIGHT - 55

        # Dark background pill
        bg = pygame.Surface((tw + 16, th + 8), pygame.SRCALPHA)
        bg.fill((20, 20, 30, alpha))
        screen.blit(bg, (x - 8, y - 4))
        screen.blit(txt_surf, (x, y))
