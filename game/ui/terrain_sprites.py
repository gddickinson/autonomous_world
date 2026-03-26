"""Enhanced terrain tile generators — natural terrain procedural pixel-art.

Each terrain type gets 4 variants arranged in a horizontal sprite sheet.
Tiles use dithering, multi-shade color mixing, and natural patterns
to create much richer visuals than simple colored rectangles.

Natural terrain types: grass, water, forest, dense_forest, mountain,
sand, snow, swamp.

Built/constructed terrain (road, farmland, wall, etc.) lives in
terrain_sprites_built.py.
"""

import pygame
import random
import math
from typing import Dict

from game.ui.sprite_loader import SpriteSheet
from game.settings import (
    TERRAIN_COLORS, GRASS, WATER, FOREST, DENSE_FOREST, MOUNTAIN,
    SAND, SNOW, SWAMP,
)

# Number of tile variants per terrain type
NUM_VARIANTS = 4


def _clamp(v: int, lo: int = 0, hi: int = 255) -> int:
    return max(lo, min(hi, v))


def _c(r, g, b):
    """Clamp RGB tuple."""
    return (_clamp(r), _clamp(g), _clamp(b))


def _seeded_rng(tile_type: int, variant: int) -> random.Random:
    """Get a deterministic RNG for a specific tile variant."""
    return random.Random(tile_type * 1000 + variant * 7 + 42)


def _dither_fill_weighted(surf, ts, color_weights, rng):
    """Fill with weighted color selection: [(color, weight), ...]."""
    total = sum(w for _, w in color_weights)
    for y in range(ts):
        for x in range(ts):
            r = rng.random() * total
            cumulative = 0
            for color, weight in color_weights:
                cumulative += weight
                if r <= cumulative:
                    surf.set_at((x, y), color)
                    break


# ============================================================
# GRASS
# ============================================================

def _gen_grass(ts: int, variant: int) -> pygame.Surface:
    """Detailed grass tile with dithered base and blade details."""
    rng = _seeded_rng(GRASS, variant)
    r, g, b = TERRAIN_COLORS[GRASS]
    surf = pygame.Surface((ts, ts))

    light = _c(r + 12, g + 18, b + 8)
    medium = _c(r, g, b)
    dark = _c(r - 10, g - 8, b - 6)
    _dither_fill_weighted(surf, ts, [
        (light, 0.25), (medium, 0.50), (dark, 0.25)
    ], rng)

    # Grass blades: 8-12 lines of varying height and shade
    num_blades = rng.randint(8, 12)
    for _ in range(num_blades):
        bx = rng.randint(1, ts - 2)
        by = rng.randint(ts // 3, ts - 2)
        blade_h = rng.randint(2, min(5, ts // 3))
        shade = _c(r - 15 + rng.randint(-5, 5),
                   g + 10 + rng.randint(-8, 8),
                   b - 10 + rng.randint(-5, 5))
        pygame.draw.line(surf, shade, (bx, by),
                         (bx + rng.randint(-1, 1), by - blade_h))

    # Wildflower accents: 0-2 per tile
    flower_colors = [(255, 255, 100), (255, 255, 255),
                     (180, 120, 220), (255, 180, 80)]
    for _ in range(rng.randint(0, 2)):
        fx = rng.randint(1, ts - 2)
        fy = rng.randint(1, ts - 3)
        surf.set_at((fx, fy), rng.choice(flower_colors))

    # Small stones
    for _ in range(rng.randint(2, 3)):
        sx = rng.randint(0, ts - 1)
        sy = rng.randint(0, ts - 1)
        stone_shade = rng.randint(120, 160)
        surf.set_at((sx, sy), (stone_shade, stone_shade - 5, stone_shade - 10))

    # Edge shadow dithering
    for x in range(ts):
        if rng.random() < 0.4:
            c = surf.get_at((x, ts - 1))
            surf.set_at((x, ts - 1), _c(c[0] - 8, c[1] - 8, c[2] - 6))
    for y in range(ts):
        if rng.random() < 0.3:
            c = surf.get_at((ts - 1, y))
            surf.set_at((ts - 1, y), _c(c[0] - 6, c[1] - 6, c[2] - 5))

    return surf


# ============================================================
# WATER (4 animation frames with shifting waves)
# ============================================================

def _gen_water(ts: int, variant: int) -> pygame.Surface:
    """Detailed water tile with wave patterns and sparkle."""
    rng = _seeded_rng(WATER, variant)
    r, g, b = TERRAIN_COLORS[WATER]
    surf = pygame.Surface((ts, ts))

    # Base: 2-tone blue with depth gradient
    for y in range(ts):
        for x in range(ts):
            edge_dist = min(x, y, ts - 1 - x, ts - 1 - y)
            depth_factor = min(edge_dist / max(ts // 4, 1), 1.0)
            dr = r - int(8 * depth_factor) + rng.randint(-3, 3)
            dg = g - int(4 * depth_factor) + rng.randint(-2, 2)
            db = b + int(6 * depth_factor) + rng.randint(-3, 3)
            surf.set_at((x, y), _c(dr, dg, db))

    # Horizontal wave pattern shifted by variant for animation
    phase_offset = variant * (ts // NUM_VARIANTS)
    for wave_i in range(4):
        wave_y = (3 + wave_i * (ts // 4) + phase_offset) % ts
        wave_color = _c(r + 30, g + 28, b + 22)
        for px in range(ts):
            wave_offset = int(math.sin((px + variant * 3) * 0.8) * 1.2)
            wy = (wave_y + wave_offset) % ts
            if rng.random() < 0.7:
                surf.set_at((px, wy), wave_color)

    # Sparkle highlights
    for i in range(rng.randint(3, 6)):
        sx = (rng.randint(1, ts - 2) + variant * 3) % ts
        sy = (rng.randint(1, ts - 2) + variant * 2) % ts
        sparkle = _c(r + 50 + rng.randint(0, 20),
                     g + 45 + rng.randint(0, 15),
                     b + 35 + rng.randint(0, 10))
        surf.set_at((sx, sy), sparkle)

    # Foam at edges
    for x in range(ts):
        if rng.random() < 0.35:
            surf.set_at((x, 0), _c(r + 40, g + 40, b + 30))
        if rng.random() < 0.35:
            surf.set_at((x, ts - 1), _c(r + 35, g + 35, b + 25))

    return surf


# ============================================================
# FOREST
# ============================================================

def _gen_forest(ts: int, variant: int) -> pygame.Surface:
    """Detailed forest tile with trunk, canopy, and undergrowth."""
    rng = _seeded_rng(FOREST, variant)
    r, g, b = TERRAIN_COLORS[FOREST]
    surf = pygame.Surface((ts, ts))

    # Dark green ground with leaf litter
    ground_colors = [
        _c(r + 5, g - 5, b + 3), _c(r - 3, g - 8, b - 2),
        _c(r + 2, g + 3, b + 1),
    ]
    litter_colors = [_c(110, 85, 50), _c(140, 100, 40), _c(90, 70, 35)]
    for y in range(ts):
        for x in range(ts):
            if rng.random() < 0.08:
                surf.set_at((x, y), rng.choice(litter_colors))
            else:
                surf.set_at((x, y), rng.choice(ground_colors))

    # Tree trunk
    cx = ts // 2 + rng.randint(-1, 1)
    trunk_top = ts // 2 - 1
    trunk_bottom = ts - 2
    trunk_w = 2 if ts <= 16 else 3
    trunk_base = _c(75, 50, 30)
    for ty in range(trunk_top, trunk_bottom + 1):
        for tx in range(cx - trunk_w // 2, cx + (trunk_w + 1) // 2):
            if 0 <= tx < ts:
                bark_var = rng.randint(-8, 8)
                surf.set_at((tx, ty), _c(trunk_base[0] + bark_var,
                                         trunk_base[1] + bark_var,
                                         trunk_base[2] + bark_var))

    # Canopy with highlight/shadow gradient
    canopy_r = max(4, ts // 2 - 1)
    canopy_cx = cx
    canopy_cy = ts // 3
    canopy_dark = _c(r - 18, g - 5, b - 10)
    canopy_mid = _c(r - 5, g + 8, b - 3)
    canopy_light = _c(r + 8, g + 20, b + 5)

    for dy in range(-canopy_r, canopy_r + 1):
        for dx in range(-canopy_r, canopy_r + 1):
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= canopy_r:
                px, py = canopy_cx + dx, canopy_cy + dy
                if 0 <= px < ts and 0 <= py < ts:
                    t = (dy + canopy_r) / (2 * canopy_r)
                    noise = rng.randint(-6, 6)
                    if t < 0.35:
                        c = canopy_light
                    elif t < 0.65:
                        c = canopy_mid
                    else:
                        c = canopy_dark
                    surf.set_at((px, py), _c(c[0] + noise,
                                             c[1] + noise,
                                             c[2] + noise))

    # Ground shadow
    shadow_cy = ts - 3
    shadow_rx = canopy_r - 1
    shadow_ry = max(1, canopy_r // 3)
    for dy in range(-shadow_ry, shadow_ry + 1):
        for dx in range(-shadow_rx, shadow_rx + 1):
            if (dx * dx) / max(shadow_rx * shadow_rx, 1) + \
               (dy * dy) / max(shadow_ry * shadow_ry, 1) <= 1.0:
                px, py = cx + dx, shadow_cy + dy
                if 0 <= px < ts and 0 <= py < ts and rng.random() < 0.6:
                    c = surf.get_at((px, py))
                    surf.set_at((px, py), _c(c[0] - 25, c[1] - 20, c[2] - 15))

    # Undergrowth
    for _ in range(rng.randint(2, 3)):
        ux = rng.randint(1, ts - 3)
        uy = rng.randint(ts - 4, ts - 2)
        uc = _c(r + rng.randint(-5, 10), g + rng.randint(5, 15),
                b + rng.randint(-3, 5))
        pygame.draw.circle(surf, uc, (ux, uy), rng.randint(1, 2))

    return surf


# ============================================================
# SAND
# ============================================================

def _gen_sand(ts: int, variant: int) -> pygame.Surface:
    """Detailed sand with dithered shading and ripple lines."""
    rng = _seeded_rng(SAND, variant)
    r, g, b = TERRAIN_COLORS[SAND]
    surf = pygame.Surface((ts, ts))

    warm = _c(r + 8, g + 5, b + 3)
    mid = _c(r, g, b)
    cool = _c(r - 10, g - 8, b - 5)
    _dither_fill_weighted(surf, ts, [
        (warm, 0.30), (mid, 0.45), (cool, 0.25)
    ], rng)

    # Wind-blown ripple lines
    for i in range(rng.randint(3, 5)):
        ry = rng.randint(2, ts - 3)
        ripple_c = _c(r + 12, g + 8, b + 5)
        for x in range(ts):
            offset = int(math.sin((x + variant * 4) * 0.6) * 0.8)
            py = ry + offset
            if 0 <= py < ts and rng.random() < 0.65:
                surf.set_at((x, py), ripple_c)

    # Pebbles
    for _ in range(rng.randint(3, 4)):
        px = rng.randint(0, ts - 1)
        py = rng.randint(0, ts - 1)
        pebble = _c(r - 30 + rng.randint(-10, 10),
                     g - 25 + rng.randint(-10, 10),
                     b - 20 + rng.randint(-10, 10))
        surf.set_at((px, py), pebble)

    # Shell on one variant
    if variant == 2:
        sx, sy = rng.randint(2, ts - 4), rng.randint(2, ts - 4)
        surf.set_at((sx, sy), _c(230, 220, 200))
        surf.set_at((sx + 1, sy), _c(220, 210, 190))

    # Edge darkening
    for x in range(ts):
        for edge_y in [0, ts - 1]:
            if rng.random() < 0.3:
                c = surf.get_at((x, edge_y))
                surf.set_at((x, edge_y), _c(c[0] - 6, c[1] - 5, c[2] - 4))

    return surf


# ============================================================
# MOUNTAIN
# ============================================================

def _gen_mountain(ts: int, variant: int) -> pygame.Surface:
    """Detailed mountain with rock texture and lighting."""
    rng = _seeded_rng(MOUNTAIN, variant)
    r, g, b = TERRAIN_COLORS[MOUNTAIN]
    surf = pygame.Surface((ts, ts))

    light = _c(r + 15, g + 15, b + 15)
    mid = _c(r, g, b)
    dark = _c(r - 15, g - 12, b - 10)
    _dither_fill_weighted(surf, ts, [
        (light, 0.20), (mid, 0.50), (dark, 0.30)
    ], rng)

    # Directional lighting
    for y in range(ts):
        for x in range(ts):
            factor = (x + y) / (2 * ts)
            c = surf.get_at((x, y))
            adj = int((factor - 0.5) * 20)
            surf.set_at((x, y), _c(c[0] - adj, c[1] - adj, c[2] - adj))

    # Rock cracks
    for _ in range(rng.randint(2, 4)):
        sx = rng.randint(0, ts // 2)
        sy = rng.randint(2, ts - 3)
        length = rng.randint(ts // 3, ts - 2)
        crack_c = _c(r - 30, g - 25, b - 20)
        for dx in range(length):
            cx = sx + dx
            cy = sy + rng.randint(-1, 1)
            if 0 <= cx < ts and 0 <= cy < ts:
                surf.set_at((cx, cy), crack_c)

    # Peak outline
    peak_pts = [(ts // 2 + rng.randint(-1, 1), 2),
                (3 + rng.randint(0, 2), ts - 3),
                (ts - 3 - rng.randint(0, 2), ts - 3)]
    peak_c = _c(r + 20, g + 20, b + 20)
    pygame.draw.polygon(surf, peak_c, peak_pts, 1)

    # Snow cap
    snow_line = ts // 3
    for y in range(0, snow_line):
        for x in range(ts):
            center_dist = abs(x - ts // 2)
            max_dist = (snow_line - y) + 2
            if center_dist <= max_dist and rng.random() < 0.5:
                snow_shade = 220 + rng.randint(0, 30)
                surf.set_at((x, y), _c(snow_shade, snow_shade + 3,
                                       snow_shade + 8))

    return surf


# ============================================================
# SNOW
# ============================================================

def _gen_snow(ts: int, variant: int) -> pygame.Surface:
    """Detailed snow with subtle blue-grey dithering and sparkles."""
    rng = _seeded_rng(SNOW, variant)
    r, g, b = TERRAIN_COLORS[SNOW]
    surf = pygame.Surface((ts, ts))

    for y in range(ts):
        for x in range(ts):
            nr = r + rng.randint(-4, 4)
            ng = g + rng.randint(-3, 3)
            nb = b + rng.randint(-2, 4)
            surf.set_at((x, y), _c(nr, ng, nb))

    # Sparkle highlights
    for _ in range(rng.randint(3, 6)):
        sx = rng.randint(0, ts - 1)
        sy = rng.randint(0, ts - 1)
        surf.set_at((sx, sy), _c(252, 254, 255))

    # Wind ridges
    for _ in range(rng.randint(1, 3)):
        ry = rng.randint(2, ts - 3)
        ridge_c = _c(r - 8, g - 6, b - 3)
        for x in range(ts):
            offset = int(math.sin((x + variant * 5) * 0.5) * 0.8)
            py = ry + offset
            if 0 <= py < ts and rng.random() < 0.5:
                surf.set_at((x, py), ridge_c)

    # Packed center
    center_shade = _c(r - 5, g - 4, b - 2)
    cx, cy = ts // 2, ts // 2
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            px, py = cx + dx, cy + dy
            if 0 <= px < ts and 0 <= py < ts and rng.random() < 0.3:
                surf.set_at((px, py), center_shade)

    return surf


# ============================================================
# SWAMP
# ============================================================

def _gen_swamp(ts: int, variant: int) -> pygame.Surface:
    """Swamp with murky water pools and reed plants."""
    rng = _seeded_rng(SWAMP, variant)
    r, g, b = TERRAIN_COLORS[SWAMP]
    surf = pygame.Surface((ts, ts))

    colors = [
        _c(r + 5, g + 8, b + 3), _c(r, g, b),
        _c(r - 8, g - 5, b - 6), _c(r - 3, g + 12, b - 2),
    ]
    _dither_fill_weighted(surf, ts, [
        (colors[0], 0.25), (colors[1], 0.35),
        (colors[2], 0.25), (colors[3], 0.15)
    ], rng)

    # Dark water pools
    for _ in range(rng.randint(1, 3)):
        px = rng.randint(2, ts - 4)
        py = rng.randint(2, ts - 4)
        pool_c = _c(r - 15, g - 10, b - 8)
        pygame.draw.circle(surf, pool_c, (px, py), rng.randint(2, 3))

    # Reed plants
    for _ in range(rng.randint(3, 5)):
        rx = rng.randint(1, ts - 2)
        ry = rng.randint(ts // 3, ts - 2)
        reed_h = rng.randint(3, ts // 2)
        reed_c = _c(60, 90 + rng.randint(-10, 10), 40)
        pygame.draw.line(surf, reed_c, (rx, ry), (rx, ry - reed_h))
        if ry - reed_h >= 0:
            surf.set_at((rx, ry - reed_h), _c(70, 100, 45))

    # Bubble
    bx = rng.randint(2, ts - 3)
    by = rng.randint(2, ts - 3)
    surf.set_at((bx, by), _c(r + 25, g + 30, b + 20))

    return surf


# ============================================================
# DENSE FOREST
# ============================================================

def _gen_dense_forest(ts: int, variant: int) -> pygame.Surface:
    """Dense forest with multiple overlapping canopies."""
    rng = _seeded_rng(DENSE_FOREST, variant)
    r, g, b = TERRAIN_COLORS[DENSE_FOREST]
    surf = pygame.Surface((ts, ts))

    for y in range(ts):
        for x in range(ts):
            noise = rng.randint(-4, 4)
            surf.set_at((x, y), _c(r + noise, g + noise, b + noise))

    # Multiple small trees
    trees = [(ts // 4, ts // 4), (3 * ts // 4, ts // 4),
             (ts // 3, 2 * ts // 3), (2 * ts // 3, 2 * ts // 3)]
    for i, (tcx, tcy) in enumerate(trees):
        tcx += rng.randint(-2, 2)
        tcy += rng.randint(-1, 1)
        for ty in range(tcy, min(tcy + 3, ts)):
            if 0 <= tcx < ts and 0 <= ty < ts:
                surf.set_at((tcx, ty), _c(55, 35, 22))
        cr = rng.randint(2, max(3, ts // 5))
        shades = [_c(r - 8, g + 8, b - 5), _c(r + 3, g + 15, b),
                  _c(r - 5, g + 5, b - 3)]
        shade_idx = i % 3
        for dy in range(-cr, cr + 1):
            for dx in range(-cr, cr + 1):
                if dx * dx + dy * dy <= cr * cr:
                    px, py = tcx + dx, tcy - 2 + dy
                    if 0 <= px < ts and 0 <= py < ts:
                        noise = rng.randint(-5, 5)
                        sc = shades[shade_idx]
                        surf.set_at((px, py), _c(sc[0] + noise,
                                                 sc[1] + noise,
                                                 sc[2] + noise))

    # Undergrowth
    for _ in range(rng.randint(3, 5)):
        ux = rng.randint(0, ts - 1)
        uy = rng.randint(ts - 4, ts - 1)
        uc = _c(r - 5, g - 8, b - 5)
        pygame.draw.line(surf, uc, (ux, uy), (ux, uy - rng.randint(1, 3)))

    return surf


# ============================================================
# ASSEMBLY — generate all sheets
# ============================================================

# Natural terrain generators in this module
_NATURAL_GENERATORS = {
    GRASS: _gen_grass,
    WATER: _gen_water,
    FOREST: _gen_forest,
    DENSE_FOREST: _gen_dense_forest,
    MOUNTAIN: _gen_mountain,
    SAND: _gen_sand,
    SNOW: _gen_snow,
    SWAMP: _gen_swamp,
}

# Combined generators (natural + built)
_GENERATORS = dict(_NATURAL_GENERATORS)


def _load_built_generators():
    """Lazily merge built terrain generators."""
    from game.ui.terrain_sprites_built import BUILT_GENERATORS
    _GENERATORS.update(BUILT_GENERATORS)


def generate_all_terrain_sheets(ts: int) -> Dict[int, SpriteSheet]:
    """Generate sprite sheets for all terrain types.

    Returns:
        Dict mapping terrain_type -> SpriteSheet (4 variants each).
    """
    _load_built_generators()
    sheets = {}
    for terrain_type, gen_func in _GENERATORS.items():
        sheet_surf = pygame.Surface((ts * NUM_VARIANTS, ts))
        for v in range(NUM_VARIANTS):
            tile = gen_func(ts, v)
            sheet_surf.blit(tile, (v * ts, 0))
        sheets[terrain_type] = SpriteSheet(sheet_surf, ts, ts)
    return sheets
