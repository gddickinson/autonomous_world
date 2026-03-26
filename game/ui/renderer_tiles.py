"""Tile surface cache builder — generates pre-rendered tile surfaces.

Extracted from renderer.py to keep each module under 500 lines.
Called by Renderer._build_tile_cache() during initialization.

Enhanced terrain types (grass, water, forest, mountain, sand, snow, road,
farmland, wall, built_wall, swamp, bridge, dense_forest, tilled_soil) use
the detailed procedural generators in terrain_sprites.py.  Other types
(furniture, windows, doors, etc.) still use the legacy builders below.
"""

import pygame
from game.settings import *
from game.ui.renderer_tiles_detail import build_furniture_and_misc
from game.ui.sprite_loader import get_sprite_manager


def build_tile_cache(tile_size: int) -> dict:
    """Pre-render tile surfaces for each terrain type.

    For terrain types with enhanced generators (terrain_sprites.py),
    uses variant 0 as the default cached tile.  The renderer can
    call SpriteManager.get_variant_for_position() for per-tile
    variation at draw time.

    Returns a dict mapping terrain_type -> pygame.Surface.
    """
    # Initialize the sprite manager with enhanced terrain sheets
    mgr = get_sprite_manager()
    mgr.initialize(tile_size)

    cache = {}
    for terrain_type, base_color in TERRAIN_COLORS.items():
        # Try enhanced sprite first (variant 0 as default)
        enhanced = mgr.get_terrain_tile(terrain_type, variant=0)
        if enhanced is not None:
            cache[terrain_type] = enhanced
            continue

        # Fall back to legacy builders for types not yet enhanced
        surf = pygame.Surface((tile_size, tile_size))
        r, g, b = base_color
        surf.fill(base_color)

        if terrain_type == WINDOW:
            _build_window(surf, r, g, b, tile_size)
        elif terrain_type == LOCKED_DOOR:
            _build_locked_door(surf, tile_size)
        elif terrain_type == FLOOR:
            _build_floor(surf, r, g, b, tile_size)
        elif terrain_type == DOOR:
            _build_door(surf, r, g, b, tile_size)
        elif terrain_type == BUILT_FLOOR:
            _build_built_floor(surf, r, g, b, tile_size)
        elif terrain_type == TREE_STUMP:
            _build_tree_stump(surf, tile_size)
        else:
            build_furniture_and_misc(surf, terrain_type, r, g, b, tile_size)

        cache[terrain_type] = surf
    return cache


# ------------------------------------------------------------------
# Individual tile builders — legacy builders for types not yet
# covered by the enhanced terrain_sprites.py generators.
# ------------------------------------------------------------------

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


def _build_built_floor(surf, r, g, b, ts):
    for bx in range(0, ts, 8):
        for by in range(0, ts, 8):
            c = (r + (bx * 3) % 10, g + (by * 3) % 10, b)
            pygame.draw.rect(surf, c, (bx, by, 7, 7))


def _build_tree_stump(surf, ts):
    pygame.draw.circle(surf, (90, 70, 45), (ts // 2, ts // 2), 5)
    pygame.draw.circle(surf, (70, 55, 35), (ts // 2, ts // 2), 5, 1)


# _build_tilled_soil removed — now handled by terrain_sprites.py
