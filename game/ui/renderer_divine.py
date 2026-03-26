"""Divine Realm Renderer — draws the god world (Mt Olympus).

When the player is in the divine realm, this renderer replaces the
normal chunk-based world renderer. It draws the 200x200 tile map
with divine aesthetics (shimmer effects, golden glow, cloud edges).
"""

import math
import pygame
from typing import Dict, List, Tuple, Optional
from game.settings import (
    TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT, TERRAIN_COLORS,
    CLOUD, MARBLE_FLOOR, DIVINE_WATER, GOLDEN_PATH,
    WALL, DOOR, PILLAR, FOUNTAIN, ALTAR, THRONE, CARPET,
    BOOKSHELF, CHEST, FIREPLACE,
)


# Divine-specific colors (richer than TERRAIN_COLORS defaults)
DIVINE_COLORS = {
    CLOUD: (220, 225, 245),
    MARBLE_FLOOR: (235, 230, 220),
    DIVINE_WATER: (90, 170, 230),
    GOLDEN_PATH: (225, 205, 125),
    WALL: (180, 175, 165),
    DOOR: (170, 140, 80),
    PILLAR: (200, 195, 185),
    FOUNTAIN: (100, 180, 230),
    ALTAR: (220, 210, 180),
    THRONE: (210, 190, 80),
    CARPET: (160, 50, 60),
    BOOKSHELF: (120, 90, 55),
    CHEST: (180, 155, 60),
    FIREPLACE: (200, 100, 40),
}


class DivineRealmRenderer:
    """Renders the divine realm tile map with shimmer effects."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self._tile_cache: Dict[int, pygame.Surface] = {}
        self._shimmer_tick = 0
        self._font = None
        self._label_cache: Dict[str, pygame.Surface] = {}
        self._built = False

    def _ensure_built(self):
        if self._built:
            return
        self._font = pygame.font.SysFont("monospace", 11)
        self._font_lg = pygame.font.SysFont("monospace", 16, bold=True)
        # Build tile surfaces
        for tile_type, color in DIVINE_COLORS.items():
            surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
            surf.fill(color)
            # Add subtle detail
            if tile_type == MARBLE_FLOOR:
                # Marble veining
                for i in range(3):
                    x1 = (i * 5 + 2) % TILE_SIZE
                    pygame.draw.line(surf, (225, 220, 210),
                                    (x1, 0), (x1 + 3, TILE_SIZE), 1)
            elif tile_type == GOLDEN_PATH:
                # Gold sparkle dots
                for i in range(2):
                    px = (i * 7 + 3) % TILE_SIZE
                    py = (i * 11 + 5) % TILE_SIZE
                    surf.set_at((px, py), (255, 240, 160))
            elif tile_type == CLOUD:
                # Soft cloud texture
                for i in range(4):
                    px = (i * 4 + 1) % TILE_SIZE
                    py = (i * 3 + 2) % TILE_SIZE
                    surf.set_at((px, py), (230, 235, 250))
            self._tile_cache[tile_type] = surf

        # Also add any TERRAIN_COLORS entries not in DIVINE_COLORS
        for tile_type, color in TERRAIN_COLORS.items():
            if tile_type not in self._tile_cache:
                surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
                surf.fill(color)
                self._tile_cache[tile_type] = surf
        self._built = True

    def draw(self, realm_data: Dict, camera, player,
             divine_mgr=None):
        """Draw the divine realm."""
        self._ensure_built()
        self._shimmer_tick += 1

        tiles = realm_data["tiles"]
        realm_size = realm_data["size"]

        # Dark ethereal background
        self.screen.fill((30, 25, 45))

        # Camera tile range
        x0 = int(camera.x) // TILE_SIZE - 1
        y0 = int(camera.y) // TILE_SIZE - 1
        x1 = x0 + SCREEN_WIDTH // TILE_SIZE + 3
        y1 = y0 + SCREEN_HEIGHT // TILE_SIZE + 3

        # Draw tiles
        for y in range(max(0, y0), min(realm_size, y1)):
            for x in range(max(0, x0), min(realm_size, x1)):
                sx = x * TILE_SIZE - int(camera.x)
                sy = y * TILE_SIZE - int(camera.y)
                if sx + TILE_SIZE < 0 or sx > SCREEN_WIDTH:
                    continue
                if sy + TILE_SIZE < 0 or sy > SCREEN_HEIGHT:
                    continue

                tile_type = tiles[y][x]
                tile_surf = self._tile_cache.get(tile_type)
                if tile_surf:
                    self.screen.blit(tile_surf, (sx, sy))
                else:
                    color = TERRAIN_COLORS.get(tile_type, (100, 100, 100))
                    pygame.draw.rect(self.screen, color,
                                     (sx, sy, TILE_SIZE, TILE_SIZE))

                # Shimmer effect on divine water
                if tile_type == DIVINE_WATER:
                    phase = (self._shimmer_tick // 20 + x + y) % 3
                    if phase == 0:
                        shimmer = pygame.Surface((TILE_SIZE, TILE_SIZE),
                                                 pygame.SRCALPHA)
                        shimmer.fill((255, 255, 255, 15))
                        self.screen.blit(shimmer, (sx, sy))

                # Golden glow on path tiles
                if tile_type == GOLDEN_PATH and (self._shimmer_tick // 40 + x) % 5 == 0:
                    glow = pygame.Surface((TILE_SIZE, TILE_SIZE),
                                          pygame.SRCALPHA)
                    glow.fill((255, 230, 100, 10))
                    self.screen.blit(glow, (sx, sy))

        # Draw structure labels
        for struct in realm_data.get("structures", []):
            cx = struct["x"] + struct["w"] // 2
            cy = struct["y"]
            sx = cx * TILE_SIZE - int(camera.x)
            sy = cy * TILE_SIZE - int(camera.y) - 14
            if -100 < sx < SCREEN_WIDTH + 100 and -20 < sy < SCREEN_HEIGHT:
                name = struct["name"]
                if name not in self._label_cache:
                    self._label_cache[name] = self._font_lg.render(
                        name, True, (255, 230, 150))
                lbl = self._label_cache[name]
                self.screen.blit(lbl, (sx - lbl.get_width() // 2, sy))

        # Draw god NPC markers
        for god in realm_data.get("god_spawns", []):
            gx = god["x"] * TILE_SIZE - int(camera.x)
            gy = god["y"] * TILE_SIZE - int(camera.y)
            if -20 < gx < SCREEN_WIDTH + 20 and -20 < gy < SCREEN_HEIGHT + 20:
                # Golden circle for god
                pygame.draw.circle(self.screen, (255, 220, 80),
                                   (gx + TILE_SIZE // 2, gy + TILE_SIZE // 2),
                                   TILE_SIZE // 2 + 2)
                pygame.draw.circle(self.screen, (200, 170, 50),
                                   (gx + TILE_SIZE // 2, gy + TILE_SIZE // 2),
                                   TILE_SIZE // 2 + 2, 1)
                # Name
                n = self._font.render(god["name"], True, (255, 240, 180))
                self.screen.blit(n, (gx + TILE_SIZE // 2 - n.get_width() // 2,
                                     gy - 12))
                # Domain (smaller)
                d = self._font.render(god["domain"], True, (200, 190, 140))
                self.screen.blit(d, (gx + TILE_SIZE // 2 - d.get_width() // 2,
                                     gy + TILE_SIZE + 2))

        # Draw player
        if player:
            px = int(player.x * TILE_SIZE - camera.x)
            py = int(player.y * TILE_SIZE - camera.y)
            # Divine glow around player
            glow_r = TILE_SIZE + 4 + int(math.sin(self._shimmer_tick * 0.05) * 2)
            glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (255, 255, 200, 30),
                               (glow_r, glow_r), glow_r)
            self.screen.blit(glow_surf, (px - glow_r + TILE_SIZE // 2,
                                          py - glow_r + TILE_SIZE // 2))
            # Player body
            pygame.draw.circle(self.screen, (255, 230, 100),
                               (px + TILE_SIZE // 2, py + TILE_SIZE // 2),
                               TILE_SIZE // 2)

        # HUD overlay
        self._draw_hud(realm_data, divine_mgr)

    def _draw_hud(self, realm_data, divine_mgr):
        """Draw divine realm HUD."""
        # Title
        title = self._font_lg.render("DIVINE REALM", True, (255, 230, 150))
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 8))

        # Controls
        controls = [
            "HOME: Return to mortal world",
            "V: Viewing Pool (observe world)",
            "E: Interact with gods/structures",
        ]
        for i, text in enumerate(controls):
            surf = self._font.render(text, True, (180, 180, 200))
            self.screen.blit(surf, (10, SCREEN_HEIGHT - 50 + i * 14))

        # Nearby interaction hints
        if divine_mgr:
            god = divine_mgr.get_nearby_god_npc(
                divine_mgr.game.player.x, divine_mgr.game.player.y)
            if god:
                hint = self._font.render(
                    f"Press E to speak with {god['name']}", True,
                    (255, 230, 150))
                self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2,
                                        SCREEN_HEIGHT - 70))

            if divine_mgr.check_portal_interaction():
                hint = self._font.render(
                    "Press E to enter the Portal Gate", True,
                    (150, 200, 255))
                self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2,
                                        SCREEN_HEIGHT - 70))
