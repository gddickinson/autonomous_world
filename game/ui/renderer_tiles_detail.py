"""Detail tile builders — furniture, resources, and miscellaneous terrain.

Split from renderer_tiles.py to keep each module under 500 lines.
"""

import pygame
from game.settings import *
from game.ui.renderer_tiles_biome import build_biome_tile


def build_furniture_and_misc(surf, terrain_type, r, g, b, ts):
    """Build tile surface for furniture, resources, and misc terrain types."""
    cx, cy = ts // 2, ts // 2

    if terrain_type == TABLE:
        surf.fill((160, 130, 95))
        pygame.draw.rect(surf, (r, g, b), (4, 6, ts - 8, ts - 12))
        pygame.draw.rect(surf, (r - 20, g - 20, b - 15), (4, 6, ts - 8, ts - 12), 2)
    elif terrain_type == BED:
        surf.fill((160, 130, 95))
        pygame.draw.rect(surf, (r, g, b), (4, 2, ts - 8, ts - 4))
        pygame.draw.rect(surf, (180, 160, 140), (6, 3, ts - 12, 10))
        pygame.draw.rect(surf, (r - 20, g - 15, b - 10), (4, 2, ts - 8, ts - 4), 1)
    elif terrain_type == CHEST:
        surf.fill((160, 130, 95))
        pygame.draw.rect(surf, (r, g, b), (6, 8, ts - 12, ts - 16))
        pygame.draw.rect(surf, (r - 30, g - 30, b - 20), (6, 8, ts - 12, ts - 16), 2)
        pygame.draw.rect(surf, (200, 180, 60), (cx - 3, cy - 2, 6, 4))
    elif terrain_type == STAIRS_UP:
        surf.fill((160, 130, 95))
        for i in range(5):
            shade = r - i * 8
            y_pos = 4 + i * 5
            pygame.draw.rect(surf, (shade, shade - 10, shade - 20), (4, y_pos, ts - 8, 4))
        pygame.draw.polygon(surf, (200, 200, 80),
                            [(cx, 2), (cx - 4, 10), (cx + 4, 10)])
    elif terrain_type == STAIRS_DOWN:
        surf.fill((100, 90, 85))
        for i in range(5):
            shade = 60 + i * 8
            y_pos = 4 + i * 5
            pygame.draw.rect(surf, (shade, shade - 5, shade - 10), (4, y_pos, ts - 8, 4))
        pygame.draw.polygon(surf, (200, 80, 80),
                            [(cx, ts - 4), (cx - 4, ts - 12), (cx + 4, ts - 12)])
    elif terrain_type == ORE_VEIN:
        surf.fill((139, 119, 101))
        for i in range(3):
            ox = (hash(i * 7) % (ts - 4)) + 2
            oy = (hash(i * 13) % (ts - 4)) + 2
            pygame.draw.circle(surf, (200, 170, 80), (ox, oy), max(1, ts // 10))
    elif terrain_type == HERB_PATCH:
        for i in range(4):
            px = (hash(i * 11) % (ts - 2)) + 1
            py = ts // 2 + (hash(i * 17) % (ts // 2))
            pygame.draw.line(surf, (40, 120, 50), (px, py), (px, py - ts // 4))
            pygame.draw.circle(surf, (50, 140, 60), (px, py - ts // 4), max(1, ts // 8))
    elif terrain_type == BERRY_BUSH:
        pygame.draw.circle(surf, (60, 120, 50), (cx, cy), ts // 3)
        for i in range(4):
            bx = cx + (hash(i * 7) % 6) - 3
            by = cy + (hash(i * 11) % 6) - 3
            pygame.draw.circle(surf, (180, 40, 50), (bx, by), max(1, ts // 10))
    elif terrain_type == CLAY_PIT:
        pygame.draw.ellipse(surf, (r - 10, g - 10, b - 10), (2, 2, ts - 4, ts - 4))
    elif terrain_type == MUSHROOMS:
        for i in range(3):
            mx = ts // 4 + (hash(i * 9) % (ts // 2))
            my = ts // 2 + (hash(i * 5) % (ts // 3))
            pygame.draw.rect(surf, (120, 100, 70), (mx, my, 1, ts // 5))
            pygame.draw.circle(surf, (r, g, b), (mx, my), max(1, ts // 7))
    elif terrain_type == WHEAT_FIELD:
        for i in range(0, ts, max(2, ts // 5)):
            pygame.draw.line(surf, (r - 20, g - 20, b - 10), (i, ts), (i + 1, ts // 3))
            pygame.draw.circle(surf, (r, g, b), (i + 1, ts // 3), max(1, ts // 10))
    elif terrain_type == VEGETABLE_PLOT:
        for i in range(2, ts - 2, max(3, ts // 4)):
            pygame.draw.line(surf, (r - 10, g - 15, b - 5), (i, 2), (i, ts - 2))
            pygame.draw.circle(surf, (60, 180, 50), (i, ts // 3), max(1, ts // 8))
    elif terrain_type == FRUIT_TREE:
        pygame.draw.circle(surf, (50, 130, 50), (cx, cy - 2), ts // 3)
        pygame.draw.rect(surf, (80, 50, 30), (cx - 1, cy + ts // 6, 2, ts // 4))
        pygame.draw.circle(surf, (200, 50, 40), (cx - 2, cy - 3), max(1, ts // 10))
        pygame.draw.circle(surf, (200, 50, 40), (cx + 3, cy - 1), max(1, ts // 10))
    elif terrain_type == FLOWER_BED:
        colors = [(200, 80, 80), (200, 200, 80), (150, 80, 200), (80, 150, 200)]
        for i, fc in enumerate(colors):
            fx = (hash(i * 7) % (ts - 4)) + 2
            fy = (hash(i * 13) % (ts - 4)) + 2
            pygame.draw.circle(surf, fc, (fx, fy), max(1, ts // 8))
    elif terrain_type == COBBLESTONE:
        for i in range(4):
            for j in range(4):
                bx = i * 4 + (j % 2)
                by = j * 4
                shade = 135 + ((i + j) % 3) * 8
                pygame.draw.rect(surf, (shade, shade, shade + 5), (bx, by, 3, 3))
                pygame.draw.rect(surf, (shade - 15, shade - 15, shade - 10),
                                 (bx, by, 3, 3), 1)
    elif terrain_type == DIRT_TRACK:
        for i in range(3):
            fx = 4 + i * 5
            fy = 3 + (i * 7) % 10
            pygame.draw.ellipse(surf, (r - 10, g - 10, b - 8), (fx, fy, 3, 4))
    elif terrain_type == MOUNTAIN_PASS:
        for i in range(5):
            px = (hash(i * 11) % (ts - 3)) + 1
            py = (hash(i * 17) % (ts - 3)) + 1
            pygame.draw.circle(surf, (r - 10, g - 10, b - 8), (px, py), 2)
    elif terrain_type == CLIFF:
        for i in range(0, ts, 3):
            shade = max(0, r - 15 - (i % 2) * 10)
            pygame.draw.line(surf, (shade, max(0, g - 15 - (i % 2) * 10),
                                    max(0, b - 15 - (i % 2) * 10)),
                             (i, 0), (i, ts))
        for i in range(3):
            y_pos = 4 + i * 5
            pygame.draw.line(surf, (max(0, r - 30), max(0, g - 30), max(0, b - 30)),
                             (1, y_pos), (ts - 2, y_pos))
    elif terrain_type == SHALLOW_WATER:
        surf.fill((min(255, r + 10), min(255, g + 10), min(255, b + 10)))
        for i in range(4):
            y_pos = 3 + i * 4
            ripple_color = (min(255, r + 30), min(255, g + 30), min(255, b + 25))
            for px in range(ts):
                offset = (px * 2 + i * 5) % 6
                if offset < 3:
                    surf.set_at((px, y_pos), ripple_color)
        for i in range(3):
            sx = (hash(i * 11 + 5) % (ts - 2)) + 1
            sy = (hash(i * 19 + 3) % (ts - 2)) + 1
            surf.set_at((sx, sy), (min(255, r + 50), min(255, g + 50), min(255, b + 40)))
    elif terrain_type == ROCKY_GROUND:
        _build_rocky_ground(surf, r, g, b, ts)
    elif terrain_type == MARSH:
        _build_marsh(surf, ts)
    elif terrain_type == GRAVEL_ROAD:
        _build_gravel_road(surf, r, g, b, ts)
    elif terrain_type == FALLEN_TREE:
        _build_fallen_tree(surf, ts)
    elif terrain_type == RUBBLE:
        _build_rubble(surf, r, g, b, ts)
    elif terrain_type == GORGE:
        _build_gorge(surf, r, g, b, ts)
    elif terrain_type == WELL:
        _build_well(surf, cx, cy)
    elif terrain_type == PILLAR:
        _build_pillar(surf, r, g, b, cx, ts)
    elif terrain_type == ALTAR:
        _build_altar(surf, r, g, b, cx, cy, ts)
    elif terrain_type == FIREPLACE:
        _build_fireplace(surf, cx, cy, ts)
    elif terrain_type == THRONE:
        _build_throne(surf, r, g, b, cx, ts)
    elif terrain_type == BOOKSHELF:
        _build_bookshelf(surf, r, g, b, ts)
    elif terrain_type == BARREL:
        _build_barrel(surf, r, g, b, cx, cy)
    elif terrain_type == ANVIL:
        _build_anvil(surf, r, g, b, cx, cy)
    elif terrain_type == FORGE_FIRE:
        _build_forge_fire(surf, r, g, b, cx, cy, ts)
    elif terrain_type == FOUNTAIN:
        _build_fountain(surf, r, g, b, cx, cy)
    elif terrain_type == CARPET:
        _build_carpet(surf, r, g, b, cx, cy, ts)
    elif terrain_type == MOSAIC:
        _build_mosaic(surf, r, g, b, ts)
    elif terrain_type == ARCHWAY:
        _build_archway(surf, r, g, b, cx, ts)
    elif terrain_type == IRON_GATE:
        _build_iron_gate(surf, r, g, b, ts)
    elif terrain_type == STABLE_FLOOR:
        _build_stable_floor(surf, r, g, b, ts)
    elif terrain_type == GEM_DEPOSIT:
        _build_gem_deposit(surf, ts)
    elif terrain_type == COPPER_VEIN:
        _build_copper_vein(surf, r, g, b, ts)
    elif terrain_type == FLAX_FIELD:
        _build_flax_field(surf, r, g, b, ts)
    elif terrain_type == BEEHIVE:
        _build_beehive(surf, r, g, b, cx, cy, ts)
    elif terrain_type == SALT_FLAT:
        _build_salt_flat(surf, r, g, b, ts)
    elif terrain_type == LADDER_UP:
        _build_ladder_up(surf, r, g, b, cx, ts)
    elif terrain_type == LADDER_DOWN:
        _build_ladder_down(surf, r, g, b, cx, ts)
    elif terrain_type == GRAVESTONE:
        _build_gravestone(surf, r, g, b, cx, ts)
    else:
        # Tile types 68-79 (biome variety, dungeon puzzles)
        build_biome_tile(surf, terrain_type, r, g, b, cx, cy, ts)


# ------------------------------------------------------------------
# Helper builders for larger terrain detail tiles
# ------------------------------------------------------------------

def _build_rocky_ground(surf, r, g, b, ts):
    for i in range(6):
        rx = (hash(i * 7 + 2) % (ts - 4)) + 2
        ry = (hash(i * 13 + 5) % (ts - 4)) + 2
        rock_shade = (max(0, r - 10 + (i % 3) * 5),
                      max(0, g - 10 + (i % 3) * 5),
                      max(0, b - 8 + (i % 3) * 5))
        pygame.draw.circle(surf, rock_shade, (rx, ry), 2)
        pygame.draw.circle(surf, (max(0, r - 20), max(0, g - 20), max(0, b - 15)),
                           (rx, ry), 2, 1)


def _build_marsh(surf, ts):
    for i in range(4):
        wx = (hash(i * 9 + 1) % (ts - 4)) + 2
        wy = (hash(i * 15 + 3) % (ts - 4)) + 2
        pygame.draw.circle(surf, (50, 90, 110), (wx, wy), 3)
        pygame.draw.circle(surf, (60, 100, 120), (wx, wy), 2)
    for i in range(3):
        rx = (hash(i * 11 + 7) % (ts - 2)) + 1
        pygame.draw.line(surf, (50, 100, 40), (rx, ts - 1), (rx, ts // 3))


def _build_gravel_road(surf, r, g, b, ts):
    for i in range(10):
        gx = (hash(i * 7 + 3) % (ts - 2)) + 1
        gy = (hash(i * 11 + 9) % (ts - 2)) + 1
        dot_shade = (max(0, r - 8 + (i % 3) * 6),
                     max(0, g - 8 + (i % 3) * 6),
                     max(0, b - 6 + (i % 3) * 6))
        pygame.draw.circle(surf, dot_shade, (gx, gy), 1)
    pygame.draw.line(surf, (max(0, r - 12), max(0, g - 12), max(0, b - 10)),
                     (ts // 2, 0), (ts // 2, ts))


def _build_fallen_tree(surf, ts):
    surf.fill((86, 152, 72))
    pygame.draw.rect(surf, (100, 70, 35), (2, ts // 2 - 2, ts - 4, 4))
    pygame.draw.rect(surf, (80, 55, 25), (2, ts // 2 - 2, ts - 4, 4), 1)
    pygame.draw.line(surf, (90, 65, 30), (4, ts // 2), (2, ts // 2 - 4))
    pygame.draw.line(surf, (90, 65, 30), (ts - 6, ts // 2), (ts - 3, ts // 2 + 4))
    for i in range(3):
        lx = (hash(i * 13 + 1) % (ts - 4)) + 2
        ly = (hash(i * 7 + 5) % (ts - 4)) + 2
        pygame.draw.circle(surf, (70, 130, 55), (lx, ly), 1)


def _build_rubble(surf, r, g, b, ts):
    for i in range(8):
        rx = (hash(i * 7 + 4) % (ts - 4)) + 2
        ry = (hash(i * 11 + 6) % (ts - 4)) + 2
        size = 1 + (i % 3)
        debris_shade = (max(0, r - 10 + (i % 4) * 5),
                        max(0, g - 10 + (i % 4) * 5),
                        max(0, b - 8 + (i % 4) * 5))
        pygame.draw.rect(surf, debris_shade, (rx, ry, size, size))
        pygame.draw.rect(surf, (max(0, r - 25), max(0, g - 25), max(0, b - 20)),
                         (rx, ry, size, size), 1)


def _build_gorge(surf, r, g, b, ts):
    surf.fill((max(0, r - 10), max(0, g - 10), max(0, b - 10)))
    for i in range(5):
        y_pos = 2 + i * 3
        depth_color = (max(0, r - 20 - i * 5), max(0, g - 20 - i * 5),
                       max(0, b - 15 - i * 5))
        pygame.draw.line(surf, depth_color, (1, y_pos), (ts - 1, y_pos))
    pygame.draw.rect(surf, (max(0, r - 30), max(0, g - 30), max(0, b - 25)),
                     (ts // 4, ts // 4, ts // 2, ts // 2))


def _build_well(surf, cx, cy):
    surf.fill((86, 152, 72))
    pygame.draw.circle(surf, (140, 135, 125), (cx, cy), 6)
    pygame.draw.circle(surf, (100, 95, 85), (cx, cy), 6, 1)
    pygame.draw.circle(surf, (20, 40, 60), (cx, cy), 4)
    pygame.draw.circle(surf, (40, 70, 100), (cx - 1, cy - 1), 1)


def _build_pillar(surf, r, g, b, cx, ts):
    surf.fill((160, 130, 95))
    pygame.draw.rect(surf, (r, g, b), (cx - 3, 3, 6, ts - 6))
    pygame.draw.rect(surf, (min(255, r + 10), min(255, g + 10), min(255, b + 10)),
                     (cx - 4, 2, 8, 3))
    pygame.draw.rect(surf, (min(255, r + 10), min(255, g + 10), min(255, b + 10)),
                     (cx - 4, ts - 5, 8, 3))
    pygame.draw.line(surf, (min(255, r + 15), min(255, g + 15), min(255, b + 15)),
                     (cx - 1, 4), (cx - 1, ts - 5))


def _build_altar(surf, r, g, b, cx, cy, ts):
    surf.fill((160, 130, 95))
    pygame.draw.rect(surf, (r, g, b), (3, cy - 1, ts - 6, ts // 2 + 1))
    pygame.draw.rect(surf, (min(255, r + 15), min(255, g + 12), min(255, b + 8)),
                     (2, cy - 3, ts - 4, 4))
    pygame.draw.line(surf, (200, 180, 100), (5, cy - 2), (ts - 5, cy - 2))
    pygame.draw.circle(surf, (200, 180, 100), (cx, cy - 2), 2, 1)


def _build_fireplace(surf, cx, cy, ts):
    surf.fill((160, 130, 95))
    pygame.draw.rect(surf, (100, 90, 80), (3, cy - 2, ts - 6, ts // 2 + 2))
    pygame.draw.circle(surf, (220, 120, 30), (cx, cy), 4)
    pygame.draw.circle(surf, (240, 160, 40), (cx, cy), 3)
    pygame.draw.polygon(surf, (250, 200, 60),
                        [(cx, cy - 5), (cx - 2, cy - 1), (cx + 2, cy - 1)])
    pygame.draw.polygon(surf, (240, 140, 30),
                        [(cx + 2, cy - 3), (cx + 1, cy), (cx + 3, cy)])


def _build_throne(surf, r, g, b, cx, ts):
    surf.fill((160, 130, 95))
    pygame.draw.rect(surf, (r, g, b), (cx - 4, 2, 8, ts - 6))
    pygame.draw.rect(surf, (max(0, r - 15), max(0, g - 15), max(0, b - 10)),
                     (cx - 6, ts // 2, 2, ts // 3))
    pygame.draw.rect(surf, (max(0, r - 15), max(0, g - 15), max(0, b - 10)),
                     (cx + 4, ts // 2, 2, ts // 3))
    pygame.draw.polygon(surf, (220, 190, 50),
                        [(cx - 3, 3), (cx, 1), (cx + 3, 3)])
    pygame.draw.line(surf, (220, 190, 50), (cx - 3, 4), (cx - 3, ts // 2))
    pygame.draw.line(surf, (220, 190, 50), (cx + 3, 4), (cx + 3, ts // 2))


def _build_bookshelf(surf, r, g, b, ts):
    surf.fill((160, 130, 95))
    pygame.draw.rect(surf, (r, g, b), (3, 2, ts - 6, ts - 4))
    pygame.draw.rect(surf, (max(0, r - 20), max(0, g - 15), max(0, b - 10)),
                     (3, 2, ts - 6, ts - 4), 1)
    for i in range(3):
        sy = 5 + i * 5
        pygame.draw.line(surf, (max(0, r - 15), max(0, g - 10), max(0, b - 5)),
                         (4, sy), (ts - 4, sy))
    book_colors = [(140, 40, 40), (40, 80, 140), (40, 120, 60), (160, 120, 40)]
    for i, bc in enumerate(book_colors):
        bx = 5 + i * 3
        by = 3
        pygame.draw.rect(surf, bc, (bx, by, 2, 4))
        pygame.draw.rect(surf, bc, (bx, by + 6, 2, 4))


def _build_barrel(surf, r, g, b, cx, cy):
    surf.fill((160, 130, 95))
    pygame.draw.circle(surf, (r, g, b), (cx, cy), 6)
    pygame.draw.circle(surf, (max(0, r - 20), max(0, g - 15), max(0, b - 10)),
                       (cx, cy), 6, 1)
    pygame.draw.circle(surf, (80, 80, 70), (cx, cy), 5, 1)
    pygame.draw.circle(surf, (80, 80, 70), (cx, cy), 3, 1)


def _build_anvil(surf, r, g, b, cx, cy):
    surf.fill((160, 130, 95))
    pygame.draw.rect(surf, (max(0, r - 10), max(0, g - 10), max(0, b - 10)),
                     (cx - 4, cy + 2, 8, 4))
    pygame.draw.rect(surf, (r, g, b), (cx - 5, cy - 2, 10, 4))
    pygame.draw.polygon(surf, (min(255, r + 5), min(255, g + 5), min(255, b + 8)),
                        [(cx - 5, cy - 1), (cx - 7, cy), (cx - 5, cy + 1)])
    pygame.draw.line(surf, (min(255, r + 15), min(255, g + 15), min(255, b + 18)),
                     (cx - 3, cy - 2), (cx + 3, cy - 2))


def _build_forge_fire(surf, r, g, b, cx, cy, ts):
    surf.fill((160, 130, 95))
    pygame.draw.rect(surf, (80, 70, 60), (3, 3, ts - 6, ts - 6))
    pygame.draw.circle(surf, (r, g, b), (cx, cy), 5)
    pygame.draw.circle(surf, (min(255, r + 20), min(255, g + 40), min(255, b + 20)),
                       (cx, cy), 3)
    pygame.draw.polygon(surf, (250, 200, 50),
                        [(cx, cy - 6), (cx - 3, cy - 1), (cx + 3, cy - 1)])
    for i in range(3):
        sx = cx + (hash(i * 7) % 6) - 3
        sy = cy - 4 - (hash(i * 11) % 3)
        surf.set_at((max(0, min(ts - 1, sx)), max(0, min(ts - 1, sy))),
                    (255, 220, 80))


def _build_fountain(surf, r, g, b, cx, cy):
    surf.fill((160, 130, 95))
    pygame.draw.circle(surf, (130, 125, 115), (cx, cy), 7)
    pygame.draw.circle(surf, (100, 95, 85), (cx, cy), 7, 1)
    pygame.draw.circle(surf, (r, g, b), (cx, cy), 5)
    pygame.draw.circle(surf, (min(255, r + 40), min(255, g + 30), min(255, b + 20)),
                       (cx, cy), 2)
    surf.set_at((cx - 1, cy - 2),
                (min(255, r + 60), min(255, g + 50), min(255, b + 30)))


def _build_carpet(surf, r, g, b, cx, cy, ts):
    pygame.draw.rect(surf, (max(0, r - 30), max(0, g - 15), max(0, b - 15)),
                     (0, 0, ts, ts))
    pygame.draw.rect(surf, (r, g, b), (2, 2, ts - 4, ts - 4))
    pygame.draw.rect(surf, (min(255, r + 20), min(255, g + 10), min(255, b + 10)),
                     (4, 4, ts - 8, ts - 8), 1)
    pygame.draw.polygon(surf, (min(255, r + 30), min(255, g + 15), min(255, b + 15)),
                        [(cx, cy - 3), (cx + 3, cy), (cx, cy + 3), (cx - 3, cy)])


def _build_mosaic(surf, r, g, b, ts):
    tile_colors = [
        (180, 140, 80), (80, 120, 160), (160, 80, 80), (80, 140, 100),
        (140, 100, 140), (160, 150, 90)
    ]
    for i in range(4):
        for j in range(4):
            mx = i * 4
            my = j * 4
            mc = tile_colors[(i + j * 3) % len(tile_colors)]
            pygame.draw.rect(surf, mc, (mx + 1, my + 1, 3, 3))
    for i in range(1, 4):
        pygame.draw.line(surf, (max(0, r - 20), max(0, g - 15), max(0, b - 10)),
                         (i * 4, 0), (i * 4, ts))
        pygame.draw.line(surf, (max(0, r - 20), max(0, g - 15), max(0, b - 10)),
                         (0, i * 4), (ts, i * 4))


def _build_archway(surf, r, g, b, cx, ts):
    surf.fill((160, 130, 95))
    pygame.draw.rect(surf, (r, g, b), (2, 4, 3, ts - 4))
    pygame.draw.rect(surf, (r, g, b), (ts - 5, 4, 3, ts - 4))
    pygame.draw.arc(surf, (r, g, b), (2, 2, ts - 4, ts // 2), 0, 3.14159, 2)
    pygame.draw.rect(surf, (min(255, r + 15), min(255, g + 12), min(255, b + 8)),
                     (cx - 2, 2, 4, 3))


def _build_iron_gate(surf, r, g, b, ts):
    surf.fill((160, 130, 95))
    for i in range(3, ts - 2, 3):
        pygame.draw.line(surf, (r, g, b), (i, 1), (i, ts - 1))
    pygame.draw.line(surf, (min(255, r + 10), min(255, g + 10), min(255, b + 12)),
                     (2, ts // 3), (ts - 2, ts // 3))
    pygame.draw.line(surf, (min(255, r + 10), min(255, g + 10), min(255, b + 12)),
                     (2, ts * 2 // 3), (ts - 2, ts * 2 // 3))


def _build_stable_floor(surf, r, g, b, ts):
    for i in range(0, ts, 6):
        plank_shade = max(0, r + (i * 2) % 12 - 6)
        pygame.draw.rect(surf, (plank_shade, max(0, g + (i % 6) - 3), max(0, b - 2)),
                         (0, i, ts, 5))
        pygame.draw.line(surf, (max(0, r - 15), max(0, g - 12), max(0, b - 8)),
                         (0, i), (ts, i))
    for i in range(4):
        hx = (hash(i * 9 + 2) % (ts - 2)) + 1
        hy = (hash(i * 15 + 7) % (ts - 2)) + 1
        pygame.draw.line(surf, (180, 160, 60), (hx, hy), (hx + 2, hy + 1))


def _build_gem_deposit(surf, ts):
    surf.fill((139, 119, 101))
    for i in range(3):
        gx = (hash(i * 11 + 1) % (ts - 4)) + 2
        gy = (hash(i * 17 + 3) % (ts - 4)) + 2
        pygame.draw.polygon(surf, (180, 100, 200),
                            [(gx, gy - 2), (gx + 2, gy), (gx, gy + 2), (gx - 2, gy)])
        surf.set_at((gx, gy - 1), (220, 180, 240))


def _build_copper_vein(surf, r, g, b, ts):
    surf.fill((139, 119, 101))
    for i in range(4):
        cx_pos = (hash(i * 9 + 2) % (ts - 4)) + 2
        cy_pos = (hash(i * 13 + 5) % (ts - 4)) + 2
        pygame.draw.circle(surf, (r, g, b), (cx_pos, cy_pos), 2)
        surf.set_at((cx_pos, cy_pos),
                    (min(255, r + 20), min(255, g + 10), max(0, b - 5)))


def _build_flax_field(surf, r, g, b, ts):
    for i in range(0, ts, max(2, ts // 5)):
        pygame.draw.line(surf, (max(0, r - 20), min(255, g + 10), max(0, b - 20)),
                         (i, ts), (i, ts // 4))
        pygame.draw.circle(surf, (100, 130, 200), (i, ts // 4), 1)


def _build_beehive(surf, r, g, b, cx, cy, ts):
    surf.fill((86, 152, 72))
    pygame.draw.ellipse(surf, (r, g, b), (cx - 5, cy - 4, 10, 10))
    for i in range(3):
        y_pos = cy - 2 + i * 3
        pygame.draw.line(surf, (max(0, r - 25), max(0, g - 25), max(0, b - 10)),
                         (cx - 3, y_pos), (cx + 3, y_pos))
    pygame.draw.circle(surf, (80, 60, 20), (cx, cy + 3), 1)


def _build_salt_flat(surf, r, g, b, ts):
    for i in range(6):
        sx = (hash(i * 7 + 3) % (ts - 2)) + 1
        sy = (hash(i * 13 + 9) % (ts - 2)) + 1
        pygame.draw.rect(surf, (min(255, r + 10), min(255, g + 10), min(255, b + 8)),
                         (sx, sy, 2, 2))
    for i in range(2):
        cx_s = (hash(i * 17) % (ts - 4)) + 2
        cy_s = (hash(i * 23) % (ts - 4)) + 2
        pygame.draw.line(surf, (max(0, r - 15), max(0, g - 15), max(0, b - 12)),
                         (cx_s, cy_s), (cx_s + 4, cy_s + 3))


def _build_ladder_up(surf, r, g, b, cx, ts):
    surf.fill((160, 130, 95))
    pygame.draw.line(surf, (r, g, b), (cx - 4, 2), (cx - 4, ts - 2))
    pygame.draw.line(surf, (r, g, b), (cx + 4, 2), (cx + 4, ts - 2))
    for i in range(4):
        y_pos = 4 + i * 4
        pygame.draw.line(surf, (min(255, r + 10), min(255, g + 10), max(0, b + 5)),
                         (cx - 3, y_pos), (cx + 3, y_pos))
    pygame.draw.polygon(surf, (200, 200, 80),
                        [(cx, 1), (cx - 3, 5), (cx + 3, 5)])


def _build_ladder_down(surf, r, g, b, cx, ts):
    surf.fill((160, 130, 95))
    pygame.draw.line(surf, (r, g, b), (cx - 4, 2), (cx - 4, ts - 2))
    pygame.draw.line(surf, (r, g, b), (cx + 4, 2), (cx + 4, ts - 2))
    for i in range(4):
        y_pos = 4 + i * 4
        pygame.draw.line(surf, (min(255, r + 10), min(255, g + 10), max(0, b + 5)),
                         (cx - 3, y_pos), (cx + 3, y_pos))
    pygame.draw.polygon(surf, (200, 80, 80),
                        [(cx, ts - 2), (cx - 3, ts - 6), (cx + 3, ts - 6)])


def _build_gravestone(surf, r, g, b, cx, ts):
    surf.fill(TERRAIN_COLORS.get(GRASS, (86, 152, 72)))
    pygame.draw.rect(surf, (120, 115, 110), (cx - 3, ts - 5, 6, 3))
    pygame.draw.rect(surf, (r, g, b), (cx - 2, ts // 2 - 2, 5, ts // 2 + 1))
    pygame.draw.circle(surf, (r, g, b), (cx, ts // 2 - 2), 3)
    pygame.draw.line(surf, (110, 105, 100), (cx, ts // 2 - 1), (cx, ts // 2 + 3))
    pygame.draw.line(surf, (110, 105, 100),
                     (cx - 1, ts // 2 + 1), (cx + 1, ts // 2 + 1))
