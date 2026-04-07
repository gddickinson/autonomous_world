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
    # Wall background (top = roof side, bottom = front wall)
    top_color = (90, 80, 70)
    front_color = (75, 65, 55)
    pygame.draw.rect(surf, front_color, (0, ts * 4 // 10, ts, ts * 6 // 10))
    pygame.draw.rect(surf, top_color, (0, 0, ts, ts * 4 // 10))
    pygame.draw.line(surf, (60, 50, 40), (0, ts * 4 // 10), (ts, ts * 4 // 10))

    # Window frame (dark wood border)
    frame_color = (55, 45, 35)
    gx, gy = 3, ts * 4 // 10 + 2
    gw, gh = ts - 6, ts * 5 // 10 - 2
    # Outer frame
    pygame.draw.rect(surf, frame_color, (gx - 1, gy - 1, gw + 2, gh + 2))
    # Slight arch at top
    arch_r = gw // 2
    if arch_r > 2:
        pygame.draw.arc(surf, frame_color,
                        (gx, gy - arch_r // 2, gw, arch_r),
                        0, 3.15, 2)

    # Glass panes (lighter blue center)
    glass_light = (160, 200, 240)
    glass_dark = (120, 165, 210)
    pygame.draw.rect(surf, glass_dark, (gx, gy, gw, gh))

    # Cross-bar dividers
    mid_x = gx + gw // 2
    mid_y = gy + gh // 2
    bar_color = (65, 55, 45)
    pygame.draw.line(surf, bar_color, (mid_x, gy), (mid_x, gy + gh), 1)
    pygame.draw.line(surf, bar_color, (gx, mid_y), (gx + gw, mid_y), 1)

    # Each pane gets slightly different shade
    pane_w = gw // 2 - 1
    pane_h = gh // 2 - 1
    pygame.draw.rect(surf, glass_light, (gx + 1, gy + 1, pane_w, pane_h))
    pygame.draw.rect(surf, (145, 190, 230), (mid_x + 1, gy + 1, pane_w, pane_h))
    pygame.draw.rect(surf, (135, 175, 215), (gx + 1, mid_y + 1, pane_w, pane_h))
    pygame.draw.rect(surf, glass_light, (mid_x + 1, mid_y + 1, pane_w, pane_h))

    # Reflection highlight (small diagonal streak on top-left pane)
    if ts >= 12:
        hx, hy = gx + 2, gy + 2
        pygame.draw.line(surf, (200, 230, 255), (hx, hy + 2), (hx + 2, hy), 1)


def _build_locked_door(surf, ts):
    surf.fill((160, 130, 95))
    pygame.draw.rect(surf, (100, 70, 40), (4, 0, ts - 8, ts))
    pygame.draw.line(surf, (80, 55, 30), (ts // 2, 2), (ts // 2, ts - 2))
    pygame.draw.circle(surf, (180, 60, 40), (ts - 8, ts // 2), 4)
    pygame.draw.circle(surf, (140, 40, 30), (ts - 8, ts // 2), 4, 1)


def _build_floor(surf, r, g, b, ts):
    # Wooden plank floor with visible grain and color variation
    plank_h = max(3, ts // 4)  # 3-4px per plank
    for i in range(0, ts, plank_h):
        # Each plank gets slight color variation
        shade_off = ((i // plank_h) * 7) % 12 - 6
        pr = max(0, min(255, r + shade_off))
        pg = max(0, min(255, g + shade_off // 2))
        pb = max(0, min(255, b + shade_off // 3))
        pygame.draw.rect(surf, (pr, pg, pb), (0, i, ts, plank_h))
        # Plank gap line (darker)
        pygame.draw.line(surf, (max(0, r - 20), max(0, g - 18), max(0, b - 14)),
                         (0, i), (ts, i))
        # Wood grain lines within plank (subtle horizontal streaks)
        grain_y = i + plank_h // 2
        if grain_y < ts:
            grain_c = (max(0, pr - 8), max(0, pg - 6), max(0, pb - 4))
            pygame.draw.line(surf, grain_c, (1, grain_y), (ts - 1, grain_y))
    # Occasional knot (darker spot)
    knot_x = (ts * 3) // 7
    knot_y = (ts * 2) // 5
    if ts >= 12:
        pygame.draw.circle(surf, (max(0, r - 25), max(0, g - 22), max(0, b - 18)),
                           (knot_x, knot_y), max(1, ts // 10))


def _build_door(surf, r, g, b, ts):
    # Door frame (darker border)
    frame_c = (max(0, r - 40), max(0, g - 35), max(0, b - 30))
    surf.fill(frame_c)
    # Door body inset
    dx, dw = 3, ts - 6
    pygame.draw.rect(surf, (r, g, b), (dx, 1, dw, ts - 1))

    # Slight arch at top
    if ts >= 12:
        arch_w = dw
        arch_h = max(2, ts // 6)
        pygame.draw.arc(surf, frame_c,
                        (dx, 1 - arch_h // 2, arch_w, arch_h * 2),
                        0, 3.15, 2)

    # Two door panels (rectangular sections)
    panel_border = (max(0, r - 18), max(0, g - 15), max(0, b - 12))
    panel_fill = (min(255, r + 5), min(255, g + 3), min(255, b + 2))
    mid_y = ts // 2
    # Top panel
    px, pw = dx + 2, dw - 4
    py1, ph1 = 3, mid_y - 5
    pygame.draw.rect(surf, panel_border, (px, py1, pw, ph1), 1)
    pygame.draw.rect(surf, panel_fill, (px + 1, py1 + 1, pw - 2, ph1 - 2))
    # Bottom panel
    py2, ph2 = mid_y + 1, ts - mid_y - 3
    pygame.draw.rect(surf, panel_border, (px, py2, pw, ph2), 1)
    pygame.draw.rect(surf, panel_fill, (px + 1, py2 + 1, pw - 2, ph2 - 2))

    # Center divider line
    pygame.draw.line(surf, panel_border, (ts // 2, 2), (ts // 2, ts - 2), 1)

    # Door handle (small circle on one side)
    handle_x = ts - max(5, ts // 3)
    handle_y = mid_y + 1
    pygame.draw.circle(surf, (200, 180, 60), (handle_x, handle_y), max(1, ts // 8))
    # Handle shadow
    pygame.draw.circle(surf, (160, 140, 40), (handle_x, handle_y),
                       max(1, ts // 8), 1)


def _build_built_floor(surf, r, g, b, ts):
    # Stone floor: checkerboard pattern with mortar lines
    block = max(3, ts // 4)
    for bx in range(0, ts, block):
        for by in range(0, ts, block):
            # Checkerboard color variation
            checker = ((bx // block) + (by // block)) % 2
            shade = 6 if checker else -4
            cr = max(0, min(255, r + shade + (bx * 3) % 8 - 4))
            cg = max(0, min(255, g + shade + (by * 3) % 8 - 4))
            cb = max(0, min(255, b + shade))
            pygame.draw.rect(surf, (cr, cg, cb),
                             (bx, by, block - 1, block - 1))
    # Mortar lines (lighter gaps between stones)
    mortar = (min(255, r + 15), min(255, g + 12), min(255, b + 10))
    for mx in range(0, ts, block):
        pygame.draw.line(surf, mortar, (mx, 0), (mx, ts - 1))
    for my in range(0, ts, block):
        pygame.draw.line(surf, mortar, (0, my), (ts - 1, my))


def _build_tree_stump(surf, ts):
    pygame.draw.circle(surf, (90, 70, 45), (ts // 2, ts // 2), 5)
    pygame.draw.circle(surf, (70, 55, 35), (ts // 2, ts // 2), 5, 1)


# _build_tilled_soil removed — now handled by terrain_sprites.py
