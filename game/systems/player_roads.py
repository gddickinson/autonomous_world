"""Player-built roads: place road tiles manually using resources.

Press J to enter road-building mode (when highlight system picker is closed).
Since J is already used by the highlight system, we use Shift+J instead.
Click or move while in road mode to place road tiles in a line.

Requirements per tile:
  - 5 Stone OR 10 Wood
  - 1 energy per tile
  - Player must be adjacent to placement location

Road tiles use COBBLESTONE (stone) or DIRT_TRACK (wood) and are persistent.
"""

import math
from typing import Optional, Tuple
from game.settings import (
    COBBLESTONE, DIRT_TRACK, WATER, SHALLOW_WATER,
    WALL, BUILT_WALL, MOUNTAIN, GREEN, YELLOW, RED, ORANGE, GRAY,
    SCREEN_WIDTH, SCREEN_HEIGHT,
)


# Tiles that cannot be overwritten with roads
_BLOCKED_TILES = {WATER, SHALLOW_WATER, WALL, BUILT_WALL, MOUNTAIN}

# Cost options
STONE_COST = 5
WOOD_COST = 10
ENERGY_COST = 1.0


class PlayerRoadBuilder:
    """Manages player road building mode and tile placement."""

    def __init__(self):
        self.active = False
        self.road_type = "stone"  # "stone" -> COBBLESTONE, "wood" -> DIRT_TRACK
        self.tiles_placed = 0
        self._last_place_pos: Optional[Tuple[int, int]] = None
        self._font = None

    def _ensure_font(self):
        if self._font is None:
            import pygame
            self._font = pygame.font.SysFont("monospace", 13)

    def toggle(self, game):
        """Toggle road building mode."""
        self.active = not self.active
        if self.active:
            self._last_place_pos = None
            self.tiles_placed = 0
            # Determine road type based on available resources
            self._pick_road_type(game.player)
            game.notifications.add(
                f"Road building: ON ({self.road_type}) "
                f"[Shift+J] off, click to place",
                3.0, GREEN,
            )
        else:
            if self.tiles_placed > 0:
                game.notifications.add(
                    f"Road building: OFF ({self.tiles_placed} tiles placed)",
                    2.0, YELLOW,
                )
            else:
                game.notifications.add("Road building: OFF", 1.5, GRAY)

    def _pick_road_type(self, player):
        """Choose stone or wood road based on inventory."""
        stone_count = self._count_item(player, "Stone")
        wood_count = self._count_item(player, "Wood")
        if stone_count >= STONE_COST:
            self.road_type = "stone"
        elif wood_count >= WOOD_COST:
            self.road_type = "wood"
        else:
            self.road_type = "stone"  # default, will fail on placement

    def handle_click(self, mx: int, my: int, game) -> bool:
        """Handle mouse click while in road building mode.

        Returns True if the click was consumed.
        """
        if not self.active:
            return False

        camera = game.camera
        # Convert screen coords to world tile coords
        wx, wy = camera.screen_to_world(mx, my)
        tx, ty = int(wx), int(wy)

        placed = self._try_place_tile(tx, ty, game)
        return True  # consume click even if placement failed

    def handle_movement(self, game):
        """Auto-place road tiles as the player moves in road mode."""
        if not self.active:
            return

        px, py = int(game.player.x), int(game.player.y)
        if self._last_place_pos == (px, py):
            return

        # Only auto-place when the player is actually on a non-road tile
        if 0 <= py < game.world.height and 0 <= px < game.world.width:
            tile = game.world.tiles[py][px]
            road_tiles = {COBBLESTONE, DIRT_TRACK}
            from game.settings import ROAD
            road_tiles.add(ROAD)
            if tile not in road_tiles and tile not in _BLOCKED_TILES:
                self._try_place_tile(px, py, game)

    def _try_place_tile(self, tx: int, ty: int, game) -> bool:
        """Attempt to place a road tile at (tx, ty)."""
        world = game.world
        player = game.player

        # Bounds check
        if not (0 <= tx < world.width and 0 <= ty < world.height):
            return False

        # Check tile is not blocked
        current = world.tiles[ty][tx]
        if current in _BLOCKED_TILES:
            game.notifications.add("Cannot build road here.", 1.0, RED)
            return False

        # Already a road?
        from game.settings import ROAD, GRAVEL_ROAD
        if current in (COBBLESTONE, DIRT_TRACK, ROAD, GRAVEL_ROAD):
            return False

        # Player must be reasonably close (within 3 tiles)
        dist = math.sqrt((player.x - tx) ** 2 + (player.y - ty) ** 2)
        if dist > 3.5:
            game.notifications.add("Too far away to build.", 1.0, RED)
            return False

        # Check energy
        if player.energy < ENERGY_COST:
            game.notifications.add("Not enough energy!", 1.0, RED)
            self.active = False
            return False

        # Check and consume resources
        if self.road_type == "stone":
            if not self._consume_item(player, "Stone", STONE_COST):
                # Try switching to wood
                if self._consume_item(player, "Wood", WOOD_COST):
                    self.road_type = "wood"
                else:
                    game.notifications.add(
                        f"Need {STONE_COST} Stone or {WOOD_COST} Wood.", 1.5, RED
                    )
                    return False
        else:
            if not self._consume_item(player, "Wood", WOOD_COST):
                if self._consume_item(player, "Stone", STONE_COST):
                    self.road_type = "stone"
                else:
                    game.notifications.add(
                        f"Need {WOOD_COST} Wood or {STONE_COST} Stone.", 1.5, RED
                    )
                    return False

        # Consume energy
        player.energy -= ENERGY_COST

        # Place the tile
        tile_type = COBBLESTONE if self.road_type == "stone" else DIRT_TRACK
        world.modify_tile(tx, ty, tile_type)

        self._last_place_pos = (tx, ty)
        self.tiles_placed += 1
        return True

    @staticmethod
    def _count_item(player, item_name: str) -> int:
        """Count how many of an item the player has."""
        return sum(
            1 for item in player.inventory
            if getattr(item, "name", "") == item_name
        )

    @staticmethod
    def _consume_item(player, item_name: str, count: int) -> bool:
        """Remove `count` items from player inventory. Returns False if not enough."""
        matching = [
            item for item in player.inventory
            if getattr(item, "name", "") == item_name
        ]
        if len(matching) < count:
            return False
        for i in range(count):
            player.inventory.remove(matching[i])
        return True

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, screen, camera, player):
        """Draw road building mode overlay."""
        if not self.active:
            return

        self._ensure_font()
        import pygame

        # Mode indicator
        label = f"ROAD MODE ({self.road_type.upper()}) - Shift+J to exit"
        surf = self._font.render(label, True, (220, 200, 100))
        bg = pygame.Surface((surf.get_width() + 12, 20), pygame.SRCALPHA)
        bg.fill((20, 15, 5, 200))
        x = SCREEN_WIDTH // 2 - surf.get_width() // 2
        screen.blit(bg, (x - 6, 75))
        screen.blit(surf, (x, 77))

        # Resource count
        stone = self._count_item(player, "Stone")
        wood = self._count_item(player, "Wood")
        res_text = f"Stone: {stone}  Wood: {wood}  Energy: {int(player.energy)}"
        res_surf = self._font.render(res_text, True, (180, 180, 160))
        screen.blit(res_surf, (x, 95))

        # Highlight tile under cursor
        mx, my = pygame.mouse.get_pos()
        wx, wy = camera.screen_to_world(mx, my)
        tx, ty = int(wx), int(wy)
        sx, sy = camera.world_to_screen(tx, ty)
        ts = camera.tile_size

        highlight = pygame.Surface((ts, ts), pygame.SRCALPHA)
        highlight.fill((100, 200, 100, 60))
        screen.blit(highlight, (int(sx), int(sy)))
        pygame.draw.rect(
            screen, (100, 200, 100),
            (int(sx), int(sy), ts, ts), 1
        )
