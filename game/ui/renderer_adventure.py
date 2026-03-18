"""
Adventure Renderer — rich 2.5D rendering at 32px per tile.

Provides detailed terrain textures, building front faces (3/4 perspective),
drop shadows, ambient occlusion, and detailed character sprites.

Toggle with V key. Strategy view (16px) for overview, Adventure view (32px)
for exploration and interaction.
"""

import math
import pygame
from typing import List, Tuple, Optional
from game.settings import *
from game.world.world import World
from game.world.camera import Camera
from game.core.player import Player

TS = 32  # tile size for adventure mode


class AdventureRenderer:
    """Rich 2.5D renderer at 32px per tile."""

    TILE_SIZE = TS

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.tile_size = TS
        self.font_sm = pygame.font.SysFont("monospace", 12)
        self.font_md = pygame.font.SysFont("monospace", 16)
        self.font_lg = pygame.font.SysFont("monospace", 22)
        self.font_xl = pygame.font.SysFont("monospace", 32)
        self._creature_font = pygame.font.SysFont("monospace", 11, bold=True)

        self._tile_cache = {}
        self._dimmed_cache = {}
        self._roof_cache = {}
        self._shadow_surf = None
        self._build_tile_cache()
        self._build_roof_cache()

        self.minimap_surface = None
        self.minimap_explored = None
        self.night_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        self.particles = []

        # Caches
        self._exterior_doors = None
        self._tile_structure_map = None

    # ================================================================
    # TILE CACHE — rich 32px procedural textures
    # ================================================================

    def _build_tile_cache(self):
        """Build all 32x32 tile surfaces with detailed procedural textures."""
        T = TS

        for terrain_type, base_color in TERRAIN_COLORS.items():
            surf = pygame.Surface((T, T))
            r, g, b = base_color
            surf.fill(base_color)

            if terrain_type == GRASS:
                # Rich grass with blade variation and wildflowers
                for i in range(20):
                    bx = (hash(i * 7 + 1) % (T - 2)) + 1
                    by = (hash(i * 13 + 3) % (T - 4)) + 2
                    bl = 2 + (hash(i * 3) % 4)
                    shade = (max(0, r - 12 + (i % 5) * 3),
                             min(255, g + 5 + (i % 7) * 2),
                             max(0, b - 8 + (i % 3) * 2))
                    pygame.draw.line(surf, shade, (bx, by), (bx + (i % 3) - 1, by - bl))
                # Wildflower dots
                if hash(terrain_type + 99) % 4 == 0:
                    fx = hash(77) % (T - 4) + 2
                    fy = hash(33) % (T - 4) + 2
                    pygame.draw.circle(surf, (200, 180, 60), (fx, fy), 2)
                # Small stones
                for i in range(2):
                    sx = hash(i * 23 + 5) % (T - 2) + 1
                    sy = hash(i * 31 + 7) % (T - 2) + 1
                    pygame.draw.circle(surf, (max(0, r - 20), max(0, g - 25), max(0, b - 15)),
                                       (sx, sy), 1)

            elif terrain_type == WATER:
                deep = (max(0, r - 18), max(0, g - 8), min(255, b + 15))
                surf.fill(deep)
                # Wave pattern with variation
                for row in range(0, T, 4):
                    for col in range(T):
                        phase = (col * 0.3 + row * 0.7 + hash(row * 5) * 0.1)
                        brightness = int(12 * math.sin(phase))
                        c = (min(255, deep[0] + brightness + 8),
                             min(255, deep[1] + brightness + 8),
                             min(255, deep[2] + brightness + 5))
                        surf.set_at((col, row), c)
                # Highlight sparkles
                for i in range(4):
                    hx = hash(i * 19 + 3) % (T - 2) + 1
                    hy = hash(i * 23 + 7) % (T - 2) + 1
                    pygame.draw.circle(surf, (min(255, r + 50), min(255, g + 50), min(255, b + 40)),
                                       (hx, hy), 1)

            elif terrain_type == FOREST:
                # Ground layer
                ground = (max(0, r + 8), min(255, g + 5), max(0, b + 3))
                surf.fill(ground)
                # Leaf litter
                for i in range(8):
                    lx = hash(i * 11) % T
                    ly = hash(i * 17) % T
                    lc = (max(0, r - 5 + (i % 4) * 3), min(255, g + (i % 3) * 4), max(0, b - 3))
                    surf.set_at((lx, ly), lc)
                # Shadow under tree
                pygame.draw.ellipse(surf, (max(0, r - 18), max(0, g - 12), max(0, b - 10)),
                                     (T // 4, T // 2 + 2, T // 2, T // 4))
                # Trunk
                tx = T // 2
                pygame.draw.rect(surf, (70, 48, 28), (tx - 3, T // 2 - 2, 6, 12))
                pygame.draw.rect(surf, (58, 38, 22), (tx - 3, T // 2 - 2, 6, 12), 1)
                # Canopy — multi-layer
                pygame.draw.circle(surf, (max(0, r - 12), min(255, g + 5), max(0, b - 5)),
                                   (tx, T // 3), 11)
                pygame.draw.circle(surf, (max(0, r - 2), min(255, g + 18), max(0, b - 2)),
                                   (tx - 3, T // 3 - 2), 9)
                pygame.draw.circle(surf, (max(0, r + 5), min(255, g + 25), max(0, b + 2)),
                                   (tx + 2, T // 3 - 3), 7)

            elif terrain_type == DENSE_FOREST:
                # Dark ground
                surf.fill((max(0, r + 5), max(0, g - 3), max(0, b - 2)))
                # Multiple trees
                trees = [(8, 8, 8), (22, 6, 9), (14, 18, 7), (26, 20, 6), (6, 24, 5)]
                for ox, oy, tr in trees:
                    # Shadow
                    pygame.draw.ellipse(surf, (max(0, r - 15), max(0, g - 12), max(0, b - 8)),
                                         (ox - tr, oy + tr // 2, tr * 2, tr))
                    # Trunk
                    pygame.draw.rect(surf, (50, 32, 18), (ox - 1, oy, 3, tr + 2))
                    # Canopy
                    pygame.draw.circle(surf, (max(0, r - 8), min(255, g + 8), max(0, b - 3)),
                                       (ox, oy - 1), tr)
                    pygame.draw.circle(surf, (max(0, r + 3), min(255, g + 15), max(0, b)),
                                       (ox - 1, oy - 2), tr - 2)
                # Undergrowth
                for i in range(4):
                    ux = hash(i * 9 + 5) % (T - 2) + 1
                    pygame.draw.line(surf, (55, 85, 35), (ux, T - 2), (ux, T - 6))

            elif terrain_type == MOUNTAIN:
                # Rocky face with crevices
                for py in range(T):
                    for px in range(T):
                        noise = ((px * 7 + py * 13 + hash(px + py * T)) % 20) - 10
                        mr = max(0, min(255, r + noise))
                        mg = max(0, min(255, g + noise))
                        mb = max(0, min(255, b + noise - 2))
                        surf.set_at((px, py), (mr, mg, mb))
                # Mountain peak silhouette
                pts = [(T // 2, 3), (3, T - 3), (T - 3, T - 3)]
                pygame.draw.polygon(surf, (min(255, r + 20), min(255, g + 18), min(255, b + 15)), pts)
                pygame.draw.polygon(surf, (max(0, r - 10), max(0, g - 10), max(0, b - 8)), pts, 2)
                # Snow cap
                snow_pts = [(T // 2, 3), (T // 2 - 7, 14), (T // 2 + 7, 14)]
                pygame.draw.polygon(surf, (225, 230, 240), snow_pts)
                # Crevice lines
                pygame.draw.line(surf, (max(0, r - 30), max(0, g - 30), max(0, b - 25)),
                                (T // 3, T // 2), (T // 2 - 2, T - 5), 1)

            elif terrain_type == SNOW:
                # White with blue shadows and sparkles
                for py in range(T):
                    for px in range(T):
                        noise = ((px * 5 + py * 11) % 8) - 4
                        surf.set_at((px, py), (min(255, r + noise),
                                               min(255, g + noise),
                                               min(255, b + noise // 2)))
                # Blue shadow dips
                for i in range(3):
                    dx = hash(i * 17) % (T - 6) + 3
                    dy = hash(i * 23) % (T - 6) + 3
                    pygame.draw.ellipse(surf, (210, 215, 230), (dx, dy, 5, 3))
                # Sparkle
                for i in range(3):
                    sx2 = hash(i * 31) % (T - 2) + 1
                    sy2 = hash(i * 37) % (T - 2) + 1
                    pygame.draw.circle(surf, (255, 255, 255), (sx2, sy2), 1)

            elif terrain_type == SAND:
                # Warm sand with grain and ripples
                for py in range(T):
                    for px in range(T):
                        noise = ((px * 3 + py * 7) % 10) - 5
                        surf.set_at((px, py), (min(255, r + noise),
                                               min(255, g + noise - 1),
                                               min(255, b + noise - 2)))
                # Wind ripple lines
                for i in range(3):
                    ry = 6 + i * 10
                    for px in range(2, T - 2):
                        offset = int(2 * math.sin(px * 0.4 + i * 2))
                        surf.set_at((px, ry + offset),
                                    (min(255, r + 12), min(255, g + 8), min(255, b + 5)))
                # Pebble
                pygame.draw.circle(surf, (max(0, r - 30), max(0, g - 25), max(0, b - 20)),
                                   (hash(42) % (T - 4) + 2, hash(99) % (T - 4) + 2), 2)

            elif terrain_type == WALL:
                # 2.5D wall — top face + front face with stone block detail
                top_h = T * 2 // 5
                # Top face (lighter)
                top_col = (min(255, r + 30), min(255, g + 30), min(255, b + 28))
                pygame.draw.rect(surf, top_col, (0, 0, T, top_h))
                # Front face (darker with blocks)
                front_col = (max(0, r - 8), max(0, g - 8), max(0, b - 6))
                pygame.draw.rect(surf, front_col, (0, top_h, T, T - top_h))
                # Edge line
                pygame.draw.line(surf, (max(0, r - 25), max(0, g - 25), max(0, b - 22)),
                                (0, top_h), (T, top_h), 2)
                # Stone block mortar on front face
                mortar = (max(0, r - 18), max(0, g - 18), max(0, b - 15))
                for row in range(top_h + 6, T, 7):
                    pygame.draw.line(surf, mortar, (0, row), (T, row))
                for col in range(0, T, 10):
                    offset = 5 if ((col // 10) % 2 == 0) else 0
                    for row in range(top_h + 6, T, 7):
                        pygame.draw.line(surf, mortar, (col + offset, row),
                                        (col + offset, min(T, row + 7)))
                # Top face mortar
                for col in range(0, T, 8):
                    pygame.draw.line(surf, (min(255, r + 15), min(255, g + 15), min(255, b + 12)),
                                    (col, 0), (col, top_h))

            elif terrain_type == FLOOR:
                # Wooden planks with grain
                for plank_y in range(0, T, 5):
                    shade = r + (plank_y * 3) % 12 - 6
                    plank_col = (max(0, min(255, shade)),
                                 max(0, min(255, g + (plank_y % 4) - 2)),
                                 max(0, min(255, b - 2)))
                    pygame.draw.rect(surf, plank_col, (0, plank_y, T, 4))
                    # Plank edge
                    pygame.draw.line(surf, (max(0, r - 18), max(0, g - 18), max(0, b - 12)),
                                    (0, plank_y), (T, plank_y))
                    # Wood grain
                    for gx in range(3, T - 3, 8):
                        gc = (max(0, shade - 8), max(0, g - 10), max(0, b - 8))
                        pygame.draw.line(surf, gc, (gx, plank_y + 1), (gx + 2, plank_y + 3))
                # Knothole
                kx = hash(17) % (T - 6) + 3
                ky = hash(31) % (T - 6) + 3
                pygame.draw.circle(surf, (max(0, r - 25), max(0, g - 20), max(0, b - 15)),
                                   (kx, ky), 2)

            elif terrain_type == DOOR:
                # Doorway with frame and handle
                surf.fill((max(0, r - 8), max(0, g - 8), max(0, b - 6)))
                # Door frame
                frame = (95, 70, 45)
                pygame.draw.rect(surf, frame, (3, 0, 4, T))
                pygame.draw.rect(surf, frame, (T - 7, 0, 4, T))
                pygame.draw.rect(surf, frame, (3, 0, T - 6, 4))
                # Door panels
                door_col = (120, 85, 50)
                pygame.draw.rect(surf, door_col, (8, 5, T // 2 - 6, T - 6))
                pygame.draw.rect(surf, (max(0, door_col[0] - 15), max(0, door_col[1] - 15),
                                        max(0, door_col[2] - 10)),
                                (8, 5, T // 2 - 6, T - 6), 1)
                # Handle
                pygame.draw.circle(surf, (200, 180, 60), (T // 2 - 2, T // 2), 3)
                pygame.draw.circle(surf, (170, 150, 40), (T // 2 - 2, T // 2), 3, 1)

            elif terrain_type == ROAD:
                # Packed earth road with wheel ruts
                for py in range(T):
                    for px in range(T):
                        noise = ((px * 5 + py * 9) % 8) - 4
                        surf.set_at((px, py), (max(0, min(255, r + noise)),
                                               max(0, min(255, g + noise)),
                                               max(0, min(255, b + noise - 1))))
                # Wheel ruts
                for px in range(T):
                    for rut_x in [T // 3, T * 2 // 3]:
                        depth = (hash(px * 7 + rut_x) % 3)
                        c = (max(0, r - 12 - depth * 3), max(0, g - 12 - depth * 3),
                             max(0, b - 8 - depth * 2))
                        surf.set_at((rut_x + (hash(px) % 2), px), c)

            elif terrain_type == COBBLESTONE:
                # Individual cobblestones with mortar
                mortar = (max(0, r - 20), max(0, g - 20), max(0, b - 18))
                surf.fill(mortar)
                for row in range(0, T, 6):
                    offset = 3 if (row // 6) % 2 else 0
                    for col in range(offset, T, 7):
                        stone_shade = 130 + ((row + col) % 5) * 6
                        sw, sh = 5, 4
                        if col + sw > T:
                            sw = T - col
                        pygame.draw.rect(surf, (stone_shade, stone_shade, stone_shade + 3),
                                        (col + 1, row + 1, sw, sh))
                        # Highlight edge
                        pygame.draw.line(surf, (min(255, stone_shade + 15), min(255, stone_shade + 15),
                                                min(255, stone_shade + 12)),
                                        (col + 1, row + 1), (col + sw, row + 1))

            elif terrain_type == GRAVEL_ROAD:
                # Scattered pebbles on packed earth
                for py in range(T):
                    for px in range(T):
                        noise = ((px * 3 + py * 11) % 10) - 5
                        surf.set_at((px, py), (max(0, min(255, r + noise)),
                                               max(0, min(255, g + noise)),
                                               max(0, min(255, b + noise))))
                for i in range(15):
                    px = hash(i * 13 + 1) % (T - 2) + 1
                    py = hash(i * 19 + 3) % (T - 2) + 1
                    ps = 1 + hash(i * 7) % 2
                    pc = 110 + (i % 4) * 10
                    pygame.draw.circle(surf, (pc, pc - 5, pc - 10), (px, py), ps)

            elif terrain_type == DIRT_TRACK:
                # Beaten earth with grass growing through
                for py in range(T):
                    for px in range(T):
                        noise = ((px * 5 + py * 7) % 8) - 4
                        surf.set_at((px, py), (max(0, min(255, r + noise)),
                                               max(0, min(255, g + noise)),
                                               max(0, min(255, b + noise))))
                # Grass tufts at edges
                for i in range(5):
                    gx = hash(i * 11 + 7) % T
                    gy = hash(i * 17 + 3) % (T // 3)
                    if i % 2:
                        gy = T - gy - 1
                    pygame.draw.line(surf, (70, 130, 55), (gx, gy), (gx, max(0, gy - 4)))

            elif terrain_type == BRIDGE:
                # Wooden bridge with railings
                surf.fill((max(0, r - 5), max(0, g - 5), max(0, b - 3)))
                # Planks
                for px in range(0, T, 4):
                    shade = r + (px * 3) % 10 - 5
                    pygame.draw.rect(surf, (max(0, shade), max(0, g + (px % 3) - 2), max(0, b)),
                                    (px, 6, 3, T - 12))
                    pygame.draw.line(surf, (max(0, r - 15), max(0, g - 15), max(0, b - 10)),
                                    (px, 6), (px, T - 6))
                # Railings
                pygame.draw.rect(surf, (90, 65, 40), (0, 3, T, 3))
                pygame.draw.rect(surf, (90, 65, 40), (0, T - 6, T, 3))
                # Railing posts
                for px in [2, T // 2, T - 4]:
                    pygame.draw.rect(surf, (80, 55, 35), (px, 0, 3, 6))
                    pygame.draw.rect(surf, (80, 55, 35), (px, T - 8, 3, 8))

            elif terrain_type == FARMLAND:
                # Tilled rows with crops
                for row_y in range(0, T, 5):
                    # Earth row
                    pygame.draw.rect(surf, (max(0, r - 8), max(0, g - 10), max(0, b - 5)),
                                    (0, row_y, T, 3))
                    # Furrow
                    pygame.draw.line(surf, (max(0, r - 20), max(0, g - 22), max(0, b - 12)),
                                    (0, row_y), (T, row_y))
                    # Crop tops
                    for cx in range(3, T - 2, 6):
                        ch = 3 + hash(cx * 7 + row_y) % 3
                        pygame.draw.line(surf, (50, 140, 40), (cx, row_y + 3), (cx, row_y + 3 - ch))
                        pygame.draw.circle(surf, (60, 150, 50), (cx, row_y + 3 - ch), 1)

            elif terrain_type == SWAMP:
                # Murky water with reeds and lily pads
                for py in range(T):
                    for px in range(T):
                        noise = ((px * 3 + py * 7) % 10) - 5
                        surf.set_at((px, py), (max(0, min(255, r + noise)),
                                               max(0, min(255, g + noise)),
                                               max(0, min(255, b + noise))))
                # Dark water patches
                for i in range(3):
                    wx = hash(i * 11 + 2) % (T - 8) + 4
                    wy = hash(i * 17 + 5) % (T - 8) + 4
                    pygame.draw.ellipse(surf, (max(0, r - 12), max(0, g - 15), max(0, b - 8)),
                                         (wx, wy, 6, 4))
                # Reed stalks
                for i in range(4):
                    rx = hash(i * 13 + 7) % (T - 2) + 1
                    pygame.draw.line(surf, (55, 90, 38), (rx, T - 2), (rx, T // 3))
                    pygame.draw.circle(surf, (65, 100, 42), (rx, T // 3), 2)
                # Lily pad
                lx = hash(55) % (T - 8) + 4
                ly = hash(77) % (T - 8) + 4
                pygame.draw.ellipse(surf, (50, 120, 45), (lx, ly, 7, 5))
                # Bubble
                bx = hash(42) % (T - 4) + 2
                by = hash(99) % (T - 4) + 2
                pygame.draw.circle(surf, (min(255, r + 25), min(255, g + 30), min(255, b + 18)),
                                   (bx, by), 1)

            elif terrain_type == BED:
                surf.fill((160, 130, 95))
                # Bed frame
                pygame.draw.rect(surf, (100, 70, 40), (4, 2, T - 8, T - 4))
                pygame.draw.rect(surf, (85, 58, 32), (4, 2, T - 8, T - 4), 2)
                # Pillow
                pygame.draw.rect(surf, (200, 190, 170), (7, 4, T - 14, 8))
                # Blanket
                pygame.draw.rect(surf, (120, 60, 50), (7, 13, T - 14, T - 18))
                pygame.draw.rect(surf, (100, 50, 40), (7, 13, T - 14, T - 18), 1)

            elif terrain_type == TABLE:
                surf.fill((160, 130, 95))
                # Table surface
                pygame.draw.rect(surf, (140, 108, 68), (5, 6, T - 10, T - 12))
                pygame.draw.rect(surf, (120, 88, 50), (5, 6, T - 10, T - 12), 2)
                # Plate
                pygame.draw.circle(surf, (190, 185, 175), (T // 2, T // 2), 5)
                pygame.draw.circle(surf, (170, 165, 155), (T // 2, T // 2), 5, 1)

            elif terrain_type == CHEST:
                surf.fill((160, 130, 95))
                # Chest body
                pygame.draw.rect(surf, (r, g, b), (7, 10, T - 14, T - 18))
                pygame.draw.rect(surf, (max(0, r - 35), max(0, g - 35), max(0, b - 25)),
                                (7, 10, T - 14, T - 18), 2)
                # Metal bands
                pygame.draw.rect(surf, (120, 100, 60), (7, 14, T - 14, 3))
                pygame.draw.rect(surf, (120, 100, 60), (7, T - 12, T - 14, 3))
                # Lock
                pygame.draw.rect(surf, (200, 180, 60), (T // 2 - 3, T // 2 - 2, 6, 5))
                pygame.draw.rect(surf, (180, 160, 40), (T // 2 - 3, T // 2 - 2, 6, 5), 1)

            elif terrain_type == FIREPLACE:
                surf.fill((160, 130, 95))
                # Stone arch
                pygame.draw.rect(surf, (100, 90, 80), (4, 2, T - 8, T - 4))
                pygame.draw.rect(surf, (80, 70, 60), (8, 8, T - 16, T - 12))
                # Fire
                flame_colors = [(220, 120, 30), (240, 160, 40), (255, 200, 60)]
                for i, fc in enumerate(flame_colors):
                    pygame.draw.ellipse(surf, fc, (11 + i * 2, T // 2 - 2 - i, 8 - i * 2, 10 + i))

            elif terrain_type in (STAIRS_UP, STAIRS_DOWN):
                surf.fill((150, 140, 130) if terrain_type == STAIRS_UP else (100, 90, 85))
                for i in range(6):
                    shade = (140 - i * 10) if terrain_type == STAIRS_UP else (60 + i * 12)
                    step_y = 3 + i * 5
                    pygame.draw.rect(surf, (shade, max(0, shade - 10), max(0, shade - 18)),
                                    (5, step_y, T - 10, 4))
                arrow_col = (200, 200, 80) if terrain_type == STAIRS_UP else (200, 80, 80)
                if terrain_type == STAIRS_UP:
                    pygame.draw.polygon(surf, arrow_col,
                                       [(T // 2, 1), (T // 2 - 5, 10), (T // 2 + 5, 10)])
                else:
                    pygame.draw.polygon(surf, arrow_col,
                                       [(T // 2, T - 2), (T // 2 - 5, T - 11), (T // 2 + 5, T - 11)])

            elif terrain_type == WINDOW:
                # Window in wall
                top_h = T * 2 // 5
                pygame.draw.rect(surf, (min(255, 90 + 30), min(255, 80 + 30), min(255, 70 + 28)),
                                (0, 0, T, top_h))
                pygame.draw.rect(surf, (75, 65, 55), (0, top_h, T, T - top_h))
                pygame.draw.line(surf, (60, 50, 40), (0, top_h), (T, top_h), 2)
                # Glass pane
                gx, gy = 8, top_h + 4
                gw, gh = T - 16, T - top_h - 8
                pygame.draw.rect(surf, (80, 70, 58), (gx - 2, gy - 2, gw + 4, gh + 4))
                pygame.draw.rect(surf, (135, 175, 215), (gx, gy, gw, gh))
                # Cross bars
                pygame.draw.line(surf, (80, 70, 58), (gx + gw // 2, gy), (gx + gw // 2, gy + gh), 2)
                pygame.draw.line(surf, (80, 70, 58), (gx, gy + gh // 2), (gx + gw, gy + gh // 2), 2)

            elif terrain_type == MOUNTAIN_PASS:
                for py in range(T):
                    for px in range(T):
                        noise = ((px * 5 + py * 11) % 12) - 6
                        surf.set_at((px, py), (max(0, min(255, r + noise)),
                                               max(0, min(255, g + noise)),
                                               max(0, min(255, b + noise))))
                for i in range(8):
                    px2 = hash(i * 13) % (T - 3) + 1
                    py2 = hash(i * 19) % (T - 3) + 1
                    pygame.draw.circle(surf, (max(0, r - 15), max(0, g - 15), max(0, b - 12)),
                                       (px2, py2), 2)

            # Fallback: anything not specifically handled uses base color fill

            self._tile_cache[terrain_type] = surf

    # ================================================================
    # ROOF CACHE
    # ================================================================

    def _build_roof_cache(self):
        T = TS
        roof_styles = {
            "village":  (135, 100, 65),
            "hamlet":   (125, 105, 60),
            "town":     (155, 110, 75),
            "city":     (110, 110, 125),
            "castle":   (95, 95, 105),
            "temple":   (145, 125, 85),
            "tavern":   (165, 80, 55),
            "default":  (100, 90, 80),
        }
        for kind, base in roof_styles.items():
            surf = pygame.Surface((T, T))
            r, g, b = base
            surf.fill(base)
            # Tile/thatch pattern
            for row in range(0, T, 5):
                offset = 3 if (row // 5) % 2 else 0
                for col in range(offset, T, 7):
                    shade = r - 8 + ((row + col) % 4) * 3
                    sw = min(6, T - col)
                    pygame.draw.rect(surf, (max(0, shade), max(0, g - 6), max(0, b - 5)),
                                    (col, row, sw, 4))
                pygame.draw.line(surf, (max(0, r - 15), max(0, g - 15), max(0, b - 12)),
                                (0, row), (T, row))
            # Ridge
            pygame.draw.line(surf, (max(0, r - 28), max(0, g - 28), max(0, b - 22)),
                            (T // 2, 0), (T // 2, T), 2)
            self._roof_cache[kind] = surf

            # Dimmed version
            dimmed = surf.copy()
            dark = pygame.Surface((T, T), pygame.SRCALPHA)
            dark.fill((0, 0, 0, 140))
            dimmed.blit(dark, (0, 0))
            self._roof_cache[kind + "_dim"] = dimmed

    def _get_floor_overlay_adv(self, player, world):
        """Get tile overrides for non-ground floors. Same logic as strategy renderer."""
        floor_num = getattr(player, 'current_floor', 0)
        if floor_num == 0:
            return {}
        current_building = getattr(player, '_current_building_rect', None)

        if floor_num < 0 and hasattr(world, 'underground'):
            level_tiles = world.underground.get(floor_num, {})
            if current_building:
                bx, by, bw, bh = current_building
                overlay = {}
                margin = 20
                for ty in range(by - margin, by + bh + margin):
                    for tx in range(bx - margin, bx + bw + margin):
                        if (tx, ty) in level_tiles:
                            overlay[(tx, ty)] = level_tiles[(tx, ty)]
                return overlay
            return {}

        if floor_num > 0 and current_building:
            bx, by, bw, bh = current_building
            if hasattr(world, 'plan'):
                for sp in world.plan.settlements:
                    for bld in sp.buildings:
                        if (bld['x'] == bx and bld['y'] == by and
                                bld['w'] == bw and bld['h'] == bh):
                            floors = bld.get('floors', {})
                            floor_tiles = floors.get(floor_num)
                            if floor_tiles:
                                overlay = {}
                                for iy in range(min(len(floor_tiles), bh)):
                                    for ix in range(min(len(floor_tiles[iy]), bw)):
                                        overlay[(bx + ix, by + iy)] = floor_tiles[iy][ix]
                                return overlay
                            break
        return {}

    def _get_roof_for_tile(self, x, y, world):
        if self._tile_structure_map is None:
            self._tile_structure_map = {}
            for s in world.structures:
                for bx, by, bw, bh in getattr(s, 'buildings', []):
                    for ty in range(by, by + bh):
                        for tx in range(bx, bx + bw):
                            self._tile_structure_map[(tx, ty)] = s.kind
        kind = self._tile_structure_map.get((x, y), "default")
        return self._roof_cache.get(kind, self._roof_cache.get("default"))

    def _get_roof_dimmed(self, x, y, world):
        if self._tile_structure_map is None:
            self._get_roof_for_tile(x, y, world)
        kind = self._tile_structure_map.get((x, y), "default")
        return self._roof_cache.get(kind + "_dim", self._roof_cache.get("default_dim"))

    # ================================================================
    # WORLD DRAWING
    # ================================================================

    def draw_world(self, world, camera, visible_tiles=None, player=None):
        T = self.tile_size
        x0, y0, x1, y1 = camera.get_visible_tile_range()

        # Floor level and building tracking
        player_floor = getattr(player, 'current_floor', 0) if player else 0
        player_building_rect = getattr(player, '_current_building_rect', None) if player else None

        # Floor tile overlay for non-ground floors
        floor_tiles = None
        if player_floor != 0 and player:
            floor_tiles = self._get_floor_overlay_adv(player, world)

        underground_explored = set()
        if player_floor < 0 and player:
            underground_explored = getattr(player, '_underground_explored', set())

        player_inside = False
        if player and hasattr(player, 'interior_state'):
            player_inside = player.interior_state.is_inside
        building_tiles = getattr(world, '_building_interior_tiles', set()) if not player_inside else set()

        interior_tiles = (FLOOR, TABLE, BED, CHEST, STAIRS_UP, STAIRS_DOWN,
                          FIREPLACE, PILLAR, ALTAR, THRONE, BOOKSHELF, BARREL,
                          ANVIL, FORGE_FIRE, FOUNTAIN, CARPET, MOSAIC, ARCHWAY)

        # Draw shadows first (behind everything)
        if player_floor >= 0:
            self._draw_building_shadows(world, camera, x0, y0, x1, y1, building_tiles)

        for y in range(y0, y1):
            for x in range(x0, x1):
                sx = x * T - int(camera.x)
                sy = y * T - int(camera.y)

                in_fov = visible_tiles is None or (x, y) in visible_tiles
                explored = world.explored[y][x] if 0 <= y < world.height and 0 <= x < world.width else False

                # Is this tile in the player's current building?
                in_player_building = False
                if player_building_rect:
                    pbx, pby, pbw, pbh = player_building_rect
                    if pbx <= x < pbx + pbw and pby <= y < pby + pbh:
                        in_player_building = True

                if in_fov:
                    # Underground: show explored underground tiles, black elsewhere
                    if player_floor < 0:
                        has_underground = floor_tiles and (x, y) in floor_tiles
                        is_explored = (x, y) in underground_explored
                        if has_underground and is_explored:
                            tile_type = floor_tiles[(x, y)]
                            tile_surf = self._tile_cache.get(tile_type)
                            if tile_surf:
                                self.screen.blit(tile_surf, (sx, sy))
                            else:
                                color = TERRAIN_COLORS.get(tile_type, (80, 80, 80))
                                pygame.draw.rect(self.screen, color, (sx, sy, T, T))
                        else:
                            pygame.draw.rect(self.screen, (0, 0, 0), (sx, sy, T, T))
                        continue

                    # Upper floors: show floor overlay inside building
                    if floor_tiles and (x, y) in floor_tiles and in_player_building:
                        tile_type = floor_tiles[(x, y)]
                    else:
                        tile_type = world.tiles[y][x]

                    # Roof logic: show roofs on buildings the player isn't inside
                    if (not in_player_building and (x, y) in building_tiles and
                        tile_type in interior_tiles):
                        roof = self._get_roof_for_tile(x, y, world)
                        if roof:
                            self.screen.blit(roof, (sx, sy))
                            continue

                    # Dim exterior when on non-ground floor
                    tile_surf = self._tile_cache.get(tile_type)
                    if tile_surf:
                        self.screen.blit(tile_surf, (sx, sy))
                    else:
                        color = TERRAIN_COLORS.get(tile_type, (80, 80, 80))
                        pygame.draw.rect(self.screen, color, (sx, sy, T, T))

                elif explored:
                    # Underground: explored surface tiles must be black
                    if player_floor < 0:
                        pygame.draw.rect(self.screen, (0, 0, 0), (sx, sy, T, T))
                        continue

                    tile_type = world.tiles[y][x]
                    if (not player_inside and (x, y) in building_tiles and
                        tile_type in interior_tiles):
                        roof = self._get_roof_dimmed(x, y, world)
                        if roof:
                            self.screen.blit(roof, (sx, sy))
                        continue
                    if tile_type not in self._dimmed_cache:
                        ts = self._tile_cache.get(tile_type)
                        if ts:
                            d = ts.copy()
                            dark = pygame.Surface((T, T), pygame.SRCALPHA)
                            dark.fill((0, 0, 0, 140))
                            d.blit(dark, (0, 0))
                            self._dimmed_cache[tile_type] = d
                    dimmed = self._dimmed_cache.get(tile_type)
                    if dimmed:
                        self.screen.blit(dimmed, (sx, sy))
                else:
                    pygame.draw.rect(self.screen, (5, 5, 10), (sx, sy, T, T))

        # Draw building front faces (3/4 perspective south walls)
        self._draw_front_faces(world, camera, x0, y0, x1, y1, building_tiles, visible_tiles)

    def _draw_building_shadows(self, world, camera, x0, y0, x1, y1, building_tiles):
        """Draw drop shadows cast by buildings (sun from top-left)."""
        T = self.tile_size
        shadow_offset_x = 3
        shadow_offset_y = 4

        for y in range(y0, y1):
            for x in range(x0, x1):
                if (x, y) not in building_tiles:
                    continue
                tile = world.tiles[y][x]
                if tile != WALL:
                    continue
                # Check if this is a south or east edge
                sx_t = x * T - int(camera.x) + shadow_offset_x
                sy_t = y * T - int(camera.y) + shadow_offset_y
                # Shadow pixel
                shadow = pygame.Surface((T, T), pygame.SRCALPHA)
                shadow.fill((0, 0, 0, 30))
                self.screen.blit(shadow, (sx_t, sy_t))

    def _draw_front_faces(self, world, camera, x0, y0, x1, y1, building_tiles, visible_tiles):
        """Draw visible south wall faces for 3/4 perspective."""
        T = self.tile_size
        face_height = T // 3  # 10px front face

        for y in range(y0, y1):
            for x in range(x0, x1):
                if (x, y) not in building_tiles:
                    continue
                tile = world.tiles[y][x]
                if tile != WALL:
                    continue

                # Check if the tile below is NOT a wall (this is a south edge)
                below_y = y + 1
                if below_y >= world.height:
                    continue
                below_tile = world.tiles[below_y][x]
                below_is_wall = (below_tile == WALL or (x, below_y) in building_tiles)
                if below_is_wall:
                    continue

                in_fov = visible_tiles is None or (x, y) in visible_tiles
                if not in_fov:
                    continue

                sx = x * T - int(camera.x)
                sy = (y + 1) * T - int(camera.y) - face_height

                # Dark stone front face
                face_col = (72, 62, 52)
                pygame.draw.rect(self.screen, face_col, (sx, sy, T, face_height))

                # Mortar lines
                mortar = (60, 50, 42)
                mid_y = sy + face_height // 2
                pygame.draw.line(self.screen, mortar, (sx, mid_y), (sx + T, mid_y))
                for col in range(sx + 5, sx + T, 10):
                    pygame.draw.line(self.screen, mortar, (col, sy), (col, sy + face_height))

                # Shadow at base
                pygame.draw.line(self.screen, (40, 35, 30), (sx, sy + face_height),
                                (sx + T, sy + face_height), 2)

    # ================================================================
    # ENTITY DRAWING
    # ================================================================

    def draw_player(self, player, camera):
        T = self.tile_size
        sx, sy = camera.world_to_screen(player.x, player.y)
        ix, iy = int(sx), int(sy)

        is_ghost = getattr(player, 'ghost', False)
        is_god = getattr(player, 'god', False)

        if is_god:
            # Golden body with aura
            aura = pygame.Surface((T * 2, T * 2), pygame.SRCALPHA)
            pygame.draw.circle(aura, (255, 220, 80, 40), (T, T), T)
            self.screen.blit(aura, (ix - T, iy - T))
            body_color = (220, 190, 60)
            head_color = (240, 210, 80)
        elif is_ghost:
            body_color = (120, 130, 180)
            head_color = (150, 160, 210)
        else:
            body_color = (60, 100, 180)
            head_color = (90, 140, 200)

        # Body
        bw, bh = 10, 14
        pygame.draw.rect(self.screen, body_color,
                        (ix - bw // 2, iy - bh // 2 + 2, bw, bh),
                        border_radius=3)
        # Head
        pygame.draw.circle(self.screen, head_color, (ix, iy - bh // 2 - 2), 6)
        # Eyes (facing)
        fx, fy = getattr(player, 'facing', (0, 1))
        ex = ix + int(fx * 2)
        ey = iy - bh // 2 - 2 + int(fy * 2)
        pygame.draw.circle(self.screen, (30, 30, 50), (ex, ey), 1)
        # Weapon
        if getattr(player, 'equipped_weapon', None):
            wx = ix + int(fx * 8) + 5
            wy = iy + int(fy * 5)
            pygame.draw.line(self.screen, (180, 180, 180), (ix + 4, iy), (wx, wy), 2)

    def draw_npcs(self, npcs, camera, player, visible_tiles=None):
        T = self.tile_size
        for npc in npcs:
            if not npc.alive:
                continue
            if visible_tiles and (int(npc.x), int(npc.y)) not in visible_tiles:
                continue
            sx, sy = camera.world_to_screen(npc.x, npc.y)
            if not (-T < sx < SCREEN_WIDTH + T and -T < sy < SCREEN_HEIGHT + T):
                continue

            ix, iy = int(sx), int(sy)
            color = npc.color

            # Body
            bw, bh = 8, 12
            pygame.draw.rect(self.screen, color,
                            (ix - bw // 2, iy - bh // 2 + 2, bw, bh),
                            border_radius=2)
            # Head
            head_col = (min(255, color[0] + 30), min(255, color[1] + 25),
                        min(255, color[2] + 15))
            pygame.draw.circle(self.screen, head_col, (ix, iy - bh // 2 - 1), 5)

            # Name label (when close)
            if player and abs(npc.x - player.x) + abs(npc.y - player.y) < 8:
                name_surf = self.font_sm.render(npc.name, True, WHITE)
                self.screen.blit(name_surf, (ix - name_surf.get_width() // 2, iy - 22))

            # Quest marker
            if getattr(npc, 'has_quest_marker', False):
                pygame.draw.polygon(self.screen, YELLOW,
                                   [(ix, iy - 28), (ix - 4, iy - 22), (ix + 4, iy - 22)])

            # Need bars
            needs = getattr(npc, 'needs', None)
            if needs and player and abs(npc.x - player.x) + abs(npc.y - player.y) < 6:
                bar_y = iy + 12
                for need_name, bar_color in [("hunger", (200, 80, 80)), ("thirst", (80, 120, 200))]:
                    val = needs.get(need_name, 100)
                    if val < 45:
                        bx = ix - 10
                        pygame.draw.rect(self.screen, (30, 30, 30), (bx, bar_y, 20, 3))
                        pygame.draw.rect(self.screen, bar_color,
                                        (bx, bar_y, max(1, int(20 * val / 100)), 3))
                        bar_y += 4

    def draw_creatures(self, creatures, camera, visible_tiles=None):
        T = self.tile_size
        for creature in creatures:
            if not creature.alive:
                continue
            if visible_tiles and (int(creature.x), int(creature.y)) not in visible_tiles:
                continue
            sx, sy = camera.world_to_screen(creature.x, creature.y)
            if not (-T < sx < SCREEN_WIDTH + T and -T < sy < SCREEN_HEIGHT + T):
                continue

            ix, iy = int(sx), int(sy)
            color = creature.color
            cr = getattr(creature, 'cr', 0.25)
            size = max(4, int(6 + min(10, cr * 3)))

            # Shadow
            shadow = pygame.Surface((size * 3, size), pygame.SRCALPHA)
            pygame.draw.ellipse(shadow, (0, 0, 0, 40), (0, 0, size * 3, size))
            self.screen.blit(shadow, (ix - size * 3 // 2, iy + size // 2))

            # Body shape
            passive = {"deer", "rabbit", "chicken", "cow", "pig", "sheep", "goat",
                       "horse", "elk", "pheasant", "fox", "fish_school"}
            humanoid = {"bandit", "goblin", "orc", "gnoll", "bugbear", "skeleton",
                        "zombie", "kobold"}

            if creature.kind in passive:
                pygame.draw.ellipse(self.screen, color,
                                   (ix - size, iy - size // 2, size * 2, size))
                # Brown eyes
                pygame.draw.circle(self.screen, (60, 40, 20), (ix - size // 3, iy - 2), 1)
                pygame.draw.circle(self.screen, (60, 40, 20), (ix + size // 3, iy - 2), 1)
            elif creature.kind in humanoid:
                # Humanoid body + head
                pygame.draw.rect(self.screen, color,
                                (ix - size // 2, iy - size // 2, size, int(size * 1.3)),
                                border_radius=2)
                pygame.draw.circle(self.screen, (min(255, color[0] + 20),
                                                  min(255, color[1] + 15),
                                                  min(255, color[2] + 10)),
                                   (ix, iy - size // 2 - 2), max(2, size // 3))
            else:
                pygame.draw.ellipse(self.screen, color,
                                   (ix - size, iy - size // 2, size * 2, size))
                # Red eyes for hostiles
                if creature.kind not in passive:
                    pygame.draw.circle(self.screen, RED, (ix - 2, iy - 2), 1)
                    pygame.draw.circle(self.screen, RED, (ix + 2, iy - 2), 1)

            # Kind initial
            initial = creature.kind[0].upper()
            letter = self._creature_font.render(initial, True, WHITE)
            self.screen.blit(letter, (ix - letter.get_width() // 2,
                                      iy - letter.get_height() // 2))

            # HP bar
            if creature.hp < creature.max_hp:
                bar_w = max(12, size * 3)
                bar_h = 3
                bx = ix - bar_w // 2
                by = iy - size - 5
                pygame.draw.rect(self.screen, DARK_GRAY, (bx, by, bar_w, bar_h))
                hp_w = int(bar_w * creature.hp / creature.max_hp)
                pygame.draw.rect(self.screen, RED, (bx, by, hp_w, bar_h))

    # ================================================================
    # SUPPORT METHODS (matching Renderer interface)
    # ================================================================

    def draw_ground_items(self, items, camera):
        T = self.tile_size
        for gx, gy, item in items:
            sx, sy = camera.world_to_screen(gx, gy)
            if not (-T < sx < SCREEN_WIDTH + T and -T < sy < SCREEN_HEIGHT + T):
                continue
            color = YELLOW if item.kind == ITEM_WEAPON else \
                    LIGHT_GRAY if item.kind == ITEM_ARMOR else \
                    GREEN if item.kind in (ITEM_CONSUMABLE, ITEM_FOOD) else \
                    BLUE if item.kind == ITEM_DRINK else \
                    (200, 200, 200)
            pygame.draw.rect(self.screen, color, (int(sx) - 3, int(sy) - 3, 6, 6))
            pygame.draw.rect(self.screen, WHITE, (int(sx) - 3, int(sy) - 3, 6, 6), 1)

    def draw_structures(self, world, camera):
        T = self.tile_size
        for s in world.structures:
            if s.kind not in ("village", "town", "city", "castle", "hamlet",
                              "temple", "ruins"):
                continue
            sx, sy = camera.world_to_screen(s.x, s.y)
            if not (-200 < sx < SCREEN_WIDTH + 200 and -50 < sy < SCREEN_HEIGHT + 50):
                continue

            if s.kind in ("city", "castle"):
                color = (255, 220, 100)
                font = self.font_lg
            elif s.kind == "town":
                color = (200, 200, 220)
                font = self.font_md
            elif s.kind == "ruins":
                color = (180, 130, 100)
                font = self.font_sm
            else:
                color = (160, 200, 160)
                font = self.font_md

            label = font.render(s.name, True, color)
            lx = int(sx) - label.get_width() // 2
            ly = int(sy) - T - 5

            bg = pygame.Surface((label.get_width() + 8, label.get_height() + 4), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 150))
            self.screen.blit(bg, (lx - 4, ly - 2))
            self.screen.blit(label, (lx, ly))

    def draw_building_doors(self, world, camera, player):
        T = self.tile_size
        if self._exterior_doors is None:
            self._exterior_doors = []
            for s in world.structures:
                for bx, by, bw, bh in getattr(s, 'buildings', []):
                    for ty in range(by, by + bh):
                        for tx in range(bx, bx + bw):
                            if 0 <= tx < world.width and 0 <= ty < world.height:
                                if world.tiles[ty][tx] == DOOR:
                                    self._exterior_doors.append((tx, ty, s.name))

        for dx, dy, name in self._exterior_doors:
            sx, sy = camera.world_to_screen(dx, dy)
            if not (0 < sx < SCREEN_WIDTH and 0 < sy < SCREEN_HEIGHT):
                continue
            if player and abs(dx - player.x) + abs(dy - player.y) < 3:
                pygame.draw.rect(self.screen, (220, 200, 80),
                                (int(sx), int(sy), T, T), 2)

    def draw_night_overlay(self, darkness):
        if darkness <= 0:
            return
        self.night_surface.fill((0, 0, 20, int(darkness * 180)))
        self.screen.blit(self.night_surface, (0, 0))

    def draw_world_events(self, events, camera):
        T = self.tile_size
        for evt in events:
            sx, sy = camera.world_to_screen(evt.x, evt.y)
            r = int(evt.radius * T * 0.15)
            if -r < sx < SCREEN_WIDTH + r and -r < sy < SCREEN_HEIGHT + r:
                event_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                color = (200, 100, 100, 25)
                pygame.draw.circle(event_surf, color, (r, r), r)
                self.screen.blit(event_surf, (int(sx) - r, int(sy) - r))

    def draw_particles(self, camera, time_val, player=None):
        remaining = []
        for p in self.particles:
            p["life"] -= 0.016
            if p["life"] <= 0:
                continue
            p["x"] += p["vx"] * 0.016
            p["y"] += p["vy"] * 0.016
            sx, sy = camera.world_to_screen(p["x"], p["y"])
            alpha = int(255 * (p["life"] / p["max_life"]))
            ps = pygame.Surface((4, 4), pygame.SRCALPHA)
            c = p["color"]
            ps.fill((c[0], c[1], c[2], alpha))
            self.screen.blit(ps, (int(sx), int(sy)))
            remaining.append(p)
        self.particles = remaining

    def spawn_hit_particles(self, x, y):
        import random
        for _ in range(6):
            self.particles.append({
                "x": x, "y": y,
                "vx": random.uniform(-2, 2), "vy": random.uniform(-3, 0),
                "life": 0.5, "max_life": 0.5,
                "color": (220, 50, 50),
            })

    def spawn_xp_particles(self, x, y):
        import random
        for _ in range(4):
            self.particles.append({
                "x": x, "y": y,
                "vx": random.uniform(-1, 1), "vy": random.uniform(-3, -1),
                "life": 1.0, "max_life": 1.0,
                "color": (240, 220, 60),
            })

    # ================================================================
    # MINIMAP
    # ================================================================

    def build_minimap(self, world):
        from game.world.world import ChunkedWorld
        if isinstance(world, ChunkedWorld) and world.width > 4000:
            # Delegate to strategy renderer's plan-based minimap
            # Adventure renderer shares the same minimap data
            self.minimap_surface = None
            self.minimap_explored = None
            return
        w, h = world.width, world.height
        self.minimap_surface = pygame.Surface((w, h))
        self.minimap_explored = pygame.Surface((w, h), pygame.SRCALPHA)
        self.minimap_explored.fill((0, 0, 0, 200))
        for y in range(h):
            for x in range(w):
                color = TERRAIN_COLORS.get(world.tiles[y][x], (100, 100, 100))
                self.minimap_surface.set_at((x, y), color)

    def update_minimap_explored(self, world):
        if self.minimap_explored is None:
            return
        from game.world.world import ChunkedWorld
        if isinstance(world, ChunkedWorld) and world.width > 4000:
            return
        for y in range(world.height):
            for x in range(world.width):
                if world.explored[y][x]:
                    self.minimap_explored.set_at((x, y), (0, 0, 0, 0))

    def draw_minimap(self, world, player, npcs, creatures, show_minimap):
        if not show_minimap or self.minimap_surface is None:
            return
        scale = 0.12
        mw = int(world.width * scale)
        mh = int(world.height * scale)
        mx = SCREEN_WIDTH - mw - 10
        my = 50

        mini = pygame.transform.smoothscale(self.minimap_surface, (mw, mh))
        self.screen.blit(mini, (mx, my))

        px = mx + int(player.x * scale)
        py = my + int(player.y * scale)
        pygame.draw.circle(self.screen, (80, 180, 255), (px, py), 3)
        pygame.draw.rect(self.screen, UI_BORDER, (mx, my, mw, mh), 1)

    # Interior drawing delegates to the 16px renderer (interiors use 128px anyway)
    def draw_interior(self, interior, player, camera):
        pass  # Interior mode handled separately by main.py
