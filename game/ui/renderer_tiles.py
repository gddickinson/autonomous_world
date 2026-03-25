"""Tile surface cache builder — generates pre-rendered tile surfaces.

Extracted from renderer.py to keep each module under 500 lines.
Called by Renderer._build_tile_cache() during initialization.
"""

import pygame
from game.settings import *
from game.ui.renderer_tiles_detail import build_furniture_and_misc


def build_tile_cache(tile_size: int) -> dict:
    """Pre-render tile surfaces for each terrain type.

    Returns a dict mapping terrain_type -> pygame.Surface.
    """
    cache = {}
    for terrain_type, base_color in TERRAIN_COLORS.items():
        surf = pygame.Surface((tile_size, tile_size))
        r, g, b = base_color
        surf.fill(base_color)

        if terrain_type == GRASS:
            _build_grass(surf, r, g, b, tile_size, terrain_type)
        elif terrain_type == WATER:
            _build_water(surf, r, g, b, tile_size)
        elif terrain_type == FOREST:
            _build_forest(surf, r, g, b, tile_size)
        elif terrain_type == DENSE_FOREST:
            _build_dense_forest(surf, r, g, b, tile_size)
        elif terrain_type == MOUNTAIN:
            _build_mountain(surf, r, g, b, tile_size)
        elif terrain_type == WALL:
            _build_wall(surf, r, g, b, tile_size)
        elif terrain_type == WINDOW:
            _build_window(surf, r, g, b, tile_size)
        elif terrain_type == LOCKED_DOOR:
            _build_locked_door(surf, tile_size)
        elif terrain_type == FLOOR:
            _build_floor(surf, r, g, b, tile_size)
        elif terrain_type == DOOR:
            _build_door(surf, r, g, b, tile_size)
        elif terrain_type == ROAD:
            _build_road(surf, r, g, b, tile_size)
        elif terrain_type == BRIDGE:
            _build_bridge(surf, r, g, b, tile_size)
        elif terrain_type == FARMLAND:
            _build_farmland(surf, r, g, b, tile_size)
        elif terrain_type == SNOW:
            _build_snow(surf, tile_size)
        elif terrain_type == SAND:
            _build_sand(surf, r, g, b, tile_size)
        elif terrain_type == SWAMP:
            _build_swamp(surf, r, g, b, tile_size)
        elif terrain_type == BUILT_WALL:
            _build_built_wall(surf, r, g, b, tile_size)
        elif terrain_type == BUILT_FLOOR:
            _build_built_floor(surf, r, g, b, tile_size)
        elif terrain_type == TREE_STUMP:
            _build_tree_stump(surf, tile_size)
        elif terrain_type == TILLED_SOIL:
            _build_tilled_soil(surf, r, g, b, tile_size)
        else:
            build_furniture_and_misc(surf, terrain_type, r, g, b, tile_size)

        cache[terrain_type] = surf
    return cache


# ------------------------------------------------------------------
# Individual tile builders — natural terrain and structures
# ------------------------------------------------------------------

def _build_grass(surf, r, g, b, ts, terrain_type):
    for i in range(4):
        x = (hash((i * 7 + terrain_type)) % (ts - 2)) + 1
        y = (hash((i * 13 + terrain_type)) % (ts - 2)) + 1
        pygame.draw.line(surf, (r - 15, g + 10, b - 10), (x, y), (x, y + 2))


def _build_water(surf, r, g, b, ts):
    deep = (max(0, r - 15), max(0, g - 5), min(255, b + 10))
    surf.fill(deep)
    for i in range(3):
        y_pos = 5 + i * 5
        wave_color = (min(255, r + 25), min(255, g + 25), min(255, b + 25))
        for px in range(ts):
            offset = (px * 3 + i * 7) % 4
            if offset < 2:
                surf.set_at((px, y_pos), wave_color)
    for i in range(2):
        fx = (hash(i * 19 + 3) % (ts - 2)) + 1
        fy = (hash(i * 23 + 7) % (ts - 2)) + 1
        surf.set_at((fx, fy), (min(255, r + 45), min(255, g + 45), min(255, b + 40)))


def _build_forest(surf, r, g, b, ts):
    for i in range(6):
        gx = (hash(i * 11 + 1) % (ts - 2)) + 1
        gy = (hash(i * 17 + 3) % (ts - 2)) + 1
        pygame.draw.circle(surf, (max(0, r - 8), min(255, g + 5), max(0, b - 3)),
                           (gx, gy), 1)
    cx, cy = ts // 2, ts // 2
    pygame.draw.rect(surf, (75, 50, 30), (cx - 2, cy + 2, 4, 7))
    pygame.draw.circle(surf, (max(0, r - 15), g, max(0, b - 8)), (cx, cy - 2), 7)
    pygame.draw.circle(surf, (max(0, r - 5), min(255, g + 15), max(0, b - 3)),
                       (cx - 1, cy - 3), 6)


def _build_dense_forest(surf, r, g, b, ts):
    trees = [(5, 5, 5), (11, 4, 6), (8, 12, 5), (14, 11, 4)]
    for ox, oy, tr in trees:
        if ox < ts and oy < ts:
            pygame.draw.rect(surf, (55, 35, 22), (ox, oy + tr, 2, 4))
            pygame.draw.circle(surf, (max(0, r - 8), min(255, g + 8), max(0, b - 5)),
                               (ox, oy), tr)
    for i in range(4):
        ux = (hash(i * 7 + 5) % (ts - 2)) + 1
        uy = ts - 4 + (hash(i * 3) % 3)
        pygame.draw.line(surf, (max(0, r - 12), max(0, g - 5), max(0, b - 8)),
                        (ux, uy), (ux, uy - 2))


def _build_mountain(surf, r, g, b, ts):
    pts = [(ts // 2, 4), (4, ts - 4), (ts - 4, ts - 4)]
    pygame.draw.polygon(surf, (r + 15, g + 15, b + 15), pts)
    pygame.draw.polygon(surf, (r, g, b), pts, 2)
    pygame.draw.polygon(surf, (220, 225, 230),
                        [(ts // 2, 4), (ts // 2 - 5, 12), (ts // 2 + 5, 12)])


def _build_wall(surf, r, g, b, ts):
    top_color = (r + 25, g + 25, b + 25)
    front_color = (r - 5, g - 5, b - 5)
    shadow_color = (r - 25, g - 25, b - 25)
    pygame.draw.rect(surf, front_color, (0, ts * 4 // 10, ts, ts * 6 // 10))
    pygame.draw.rect(surf, top_color, (0, 0, ts, ts * 4 // 10))
    pygame.draw.line(surf, shadow_color, (0, ts * 4 // 10), (ts, ts * 4 // 10))
    pygame.draw.line(surf, shadow_color, (0, ts * 7 // 10), (ts, ts * 7 // 10))
    pygame.draw.line(surf, shadow_color, (ts // 2, ts * 4 // 10), (ts // 2, ts * 7 // 10))


def _build_window(surf, r, g, b, ts):
    top_color = (90, 80, 70)
    front_color = (75, 65, 55)
    pygame.draw.rect(surf, front_color, (0, ts * 4 // 10, ts, ts * 6 // 10))
    pygame.draw.rect(surf, top_color, (0, 0, ts, ts * 4 // 10))
    pygame.draw.line(surf, (60, 50, 40), (0, ts * 4 // 10), (ts, ts * 4 // 10))
    glass_color = (140, 180, 220)
    glass_frame = (80, 70, 60)
    gx, gy = 6, ts * 4 // 10 + 3
    gw, gh = ts - 12, ts * 5 // 10 - 4
    pygame.draw.rect(surf, glass_frame, (gx - 1, gy - 1, gw + 2, gh + 2))
    pygame.draw.rect(surf, glass_color, (gx, gy, gw, gh))
    pygame.draw.line(surf, glass_frame, (gx + gw // 2, gy), (gx + gw // 2, gy + gh))
    pygame.draw.line(surf, glass_frame, (gx, gy + gh // 2), (gx + gw, gy + gh // 2))


def _build_locked_door(surf, ts):
    surf.fill((160, 130, 95))
    pygame.draw.rect(surf, (100, 70, 40), (4, 0, ts - 8, ts))
    pygame.draw.line(surf, (80, 55, 30), (ts // 2, 2), (ts // 2, ts - 2))
    pygame.draw.circle(surf, (180, 60, 40), (ts - 8, ts // 2), 4)
    pygame.draw.circle(surf, (140, 40, 30), (ts - 8, ts // 2), 4, 1)


def _build_floor(surf, r, g, b, ts):
    for i in range(0, ts, 8):
        plank_shade = r + (i * 2) % 12 - 6
        pygame.draw.rect(surf, (plank_shade, g + (i % 8) - 4, b - 3),
                        (0, i, ts, 7))
        pygame.draw.line(surf, (r - 15, g - 15, b - 10), (0, i), (ts, i))


def _build_door(surf, r, g, b, ts):
    surf.fill((160, 130, 95))
    pygame.draw.rect(surf, (r, g, b), (2, 0, ts - 4, ts))
    pygame.draw.circle(surf, (200, 180, 60), (ts - 8, ts // 2), 3)
    pygame.draw.line(surf, (r - 20, g - 20, b - 15),
                     (ts // 2, 2), (ts // 2, ts - 2), 1)


def _build_road(surf, r, g, b, ts):
    for i in range(0, ts, 6):
        pygame.draw.circle(surf, (r - 10, g - 10, b - 10), (i + 3, ts // 2), 1)


def _build_bridge(surf, r, g, b, ts):
    pygame.draw.rect(surf, (r - 15, g - 15, b - 15), (0, 4, ts, ts - 8))
    for i in range(0, ts, 8):
        pygame.draw.line(surf, (r + 10, g + 10, b + 10), (i, 4), (i, ts - 4))


def _build_farmland(surf, r, g, b, ts):
    for i in range(2, ts - 2, 4):
        pygame.draw.line(surf, (r - 15, g - 15, b - 10), (i, 2), (i, ts - 2))


def _build_snow(surf, ts):
    for i in range(5):
        x = hash(i * 17) % ts
        y = hash(i * 23) % ts
        pygame.draw.circle(surf, (250, 252, 255), (x, y), 2)


def _build_sand(surf, r, g, b, ts):
    for i in range(8):
        gx = hash(i * 11 + 5) % ts
        gy = hash(i * 19 + 3) % ts
        shade = (min(255, r + 8), min(255, g + 5), min(255, b + 3))
        surf.set_at((gx, gy), shade)
    px = hash(7) % (ts - 2) + 1
    py = hash(13) % (ts - 2) + 1
    pygame.draw.circle(surf, (max(0, r - 30), max(0, g - 25), max(0, b - 20)),
                       (px, py), 1)


def _build_swamp(surf, r, g, b, ts):
    for i in range(3):
        px = hash(i * 9 + 2) % (ts - 4) + 2
        py = hash(i * 15 + 1) % (ts - 4) + 2
        pygame.draw.circle(surf, (max(0, r - 10), max(0, g - 8), max(0, b - 5)),
                           (px, py), 3)
    for i in range(3):
        rx = hash(i * 13 + 7) % (ts - 2) + 1
        pygame.draw.line(surf, (60, 90, 40), (rx, ts - 2), (rx, ts // 3))
        pygame.draw.circle(surf, (70, 100, 45), (rx, ts // 3), 1)
    bx = hash(42) % (ts - 4) + 2
    by = hash(99) % (ts - 4) + 2
    pygame.draw.circle(surf, (min(255, r + 20), min(255, g + 25), min(255, b + 15)),
                       (bx, by), 1)


def _build_built_wall(surf, r, g, b, ts):
    pygame.draw.rect(surf, (r + 10, g + 10, b + 10), (2, 2, ts - 4, ts - 4))
    pygame.draw.rect(surf, (r - 15, g - 15, b - 15), (2, 2, ts - 4, ts - 4), 2)
    for by in range(4, ts - 4, 6):
        pygame.draw.line(surf, (r - 10, g - 10, b - 10), (3, by), (ts - 3, by))


def _build_built_floor(surf, r, g, b, ts):
    for bx in range(0, ts, 8):
        for by in range(0, ts, 8):
            c = (r + (bx * 3) % 10, g + (by * 3) % 10, b)
            pygame.draw.rect(surf, c, (bx, by, 7, 7))


def _build_tree_stump(surf, ts):
    pygame.draw.circle(surf, (90, 70, 45), (ts // 2, ts // 2), 5)
    pygame.draw.circle(surf, (70, 55, 35), (ts // 2, ts // 2), 5, 1)


def _build_tilled_soil(surf, r, g, b, ts):
    for i in range(2, ts - 2, 4):
        pygame.draw.line(surf, (r - 10, g - 10, b - 5), (i, 2), (i, ts - 2))
    for sx_pos in range(6, ts - 4, 10):
        pygame.draw.line(surf, (60, 140, 40), (sx_pos, ts // 2), (sx_pos, ts // 2 - 4))
