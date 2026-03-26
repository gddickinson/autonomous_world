"""Enhanced terrain tile generators — built/constructed terrain types.

Covers road, farmland, wall, built_wall, bridge, tilled_soil.
Split from terrain_sprites.py to keep each module under 500 lines.

Uses the same utility functions from terrain_sprites for consistency.
"""

import pygame
import random
import math

from game.ui.sprite_loader import SpriteSheet
from game.settings import (
    TERRAIN_COLORS, ROAD, FARMLAND, WALL, BUILT_WALL, BRIDGE, TILLED_SOIL,
)

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
# ROAD / COBBLESTONE
# ============================================================

def _gen_road(ts: int, variant: int) -> pygame.Surface:
    """Cobblestone road with grout lines and color variation."""
    rng = _seeded_rng(ROAD, variant)
    r, g, b = TERRAIN_COLORS[ROAD]
    surf = pygame.Surface((ts, ts))
    surf.fill(_c(r - 10, g - 10, b - 8))  # grout base

    # Cobblestone grid: 3-4px rounded rectangles
    stone_size = 3 if ts <= 16 else 5
    grout = 1
    for sy in range(0, ts, stone_size + grout):
        x_off = (stone_size // 2) if (sy // (stone_size + grout)) % 2 else 0
        for sx in range(-stone_size, ts + stone_size, stone_size + grout):
            bx = sx + x_off
            shade = rng.randint(-12, 12)
            stone_c = _c(r + shade, g + shade, b + shade - 3)
            rect = pygame.Rect(bx, sy, stone_size, stone_size)
            rect = rect.clip(pygame.Rect(0, 0, ts, ts))
            if rect.width > 0 and rect.height > 0:
                pygame.draw.rect(surf, stone_c, rect)

    # Cart-track wear: two darker lines
    track_w = max(1, ts // 6)
    track1_x = ts // 3
    track2_x = 2 * ts // 3
    for y in range(ts):
        for tx in [track1_x, track2_x]:
            for dx in range(track_w):
                px = tx + dx
                if 0 <= px < ts and rng.random() < 0.4:
                    c = surf.get_at((px, y))
                    surf.set_at((px, y), _c(c[0] - 10, c[1] - 10, c[2] - 8))

    # Scattered pebbles
    for _ in range(rng.randint(2, 4)):
        px = rng.randint(0, ts - 1)
        py = rng.randint(0, ts - 1)
        surf.set_at((px, py), _c(r - 25, g - 22, b - 18))

    return surf


# ============================================================
# FARMLAND
# ============================================================

def _gen_farmland(ts: int, variant: int) -> pygame.Surface:
    """Farmland with tilled rows and growing crops."""
    rng = _seeded_rng(FARMLAND, variant)
    r, g, b = TERRAIN_COLORS[FARMLAND]
    surf = pygame.Surface((ts, ts))

    # Tilled rows: alternating dark/light brown horizontal stripes
    row_h = max(2, ts // 8)
    for y in range(ts):
        row_idx = y // row_h
        if row_idx % 2 == 0:
            base = _c(r - 8, g - 10, b - 5)
        else:
            base = _c(r + 5, g + 3, b + 2)
        for x in range(ts):
            noise = rng.randint(-3, 3)
            surf.set_at((x, y), _c(base[0] + noise, base[1] + noise, base[2] + noise))

    # Crops based on variant
    if variant == 0:
        # Young sprouts
        for sx in range(2, ts - 1, max(3, ts // 5)):
            for sy in range(1, ts - 1, row_h * 2):
                sprout_c = _c(60, 140 + rng.randint(-10, 10), 40)
                pygame.draw.line(surf, sprout_c, (sx, sy + 2), (sx, sy))
    elif variant == 1:
        # Medium growth
        for sx in range(2, ts - 1, max(3, ts // 5)):
            for sy in range(1, ts - 1, row_h * 2):
                sprout_c = _c(50, 150 + rng.randint(-10, 10), 35)
                pygame.draw.line(surf, sprout_c, (sx, sy + 3), (sx, sy))
                surf.set_at((sx - 1, sy), _c(60, 130, 40))
    elif variant == 2:
        # Mature golden wheat
        for sx in range(1, ts, max(2, ts // 7)):
            for sy in range(0, ts - 1, row_h * 2):
                wheat_c = _c(200 + rng.randint(-10, 10),
                             180 + rng.randint(-10, 10),
                             60 + rng.randint(-10, 10))
                h = rng.randint(3, min(4, ts // 4))
                pygame.draw.line(surf, wheat_c, (sx, sy + h), (sx, sy))
    else:
        # Harvested — bare furrows with stubble
        for sx in range(3, ts - 1, max(4, ts // 4)):
            for sy in range(1, ts, row_h * 2):
                stub_c = _c(130, 110, 60)
                surf.set_at((sx, sy), stub_c)

    return surf


# ============================================================
# WALL / BUILT_WALL
# ============================================================

def _gen_wall(ts: int, variant: int) -> pygame.Surface:
    """Stone wall with block pattern and mortar lines."""
    rng = _seeded_rng(WALL, variant)
    r, g, b = TERRAIN_COLORS[WALL]
    surf = pygame.Surface((ts, ts))

    top_h = ts * 4 // 10
    top_c = _c(r + 25, g + 25, b + 25)
    front_c = _c(r - 5, g - 5, b - 5)
    pygame.draw.rect(surf, top_c, (0, 0, ts, top_h))
    pygame.draw.rect(surf, front_c, (0, top_h, ts, ts - top_h))

    block_w = max(3, ts // 4)
    block_h = max(2, (ts - top_h) // 3)
    mortar_c = _c(r - 20, g - 20, b - 18)

    for by in range(top_h, ts, block_h + 1):
        row_offset = (block_w // 2) if ((by - top_h) // (block_h + 1)) % 2 else 0
        for bx in range(-block_w, ts + block_w, block_w + 1):
            x = bx + row_offset
            shade = rng.randint(-8, 8)
            block_c = _c(r - 5 + shade, g - 5 + shade, b - 5 + shade)
            rect = pygame.Rect(x, by, block_w, block_h)
            rect = rect.clip(pygame.Rect(0, top_h, ts, ts - top_h))
            if rect.width > 0 and rect.height > 0:
                pygame.draw.rect(surf, block_c, rect)

    for my in range(top_h, ts, block_h + 1):
        pygame.draw.line(surf, mortar_c, (0, my), (ts - 1, my))
    pygame.draw.line(surf, mortar_c, (0, top_h), (ts - 1, top_h))

    if variant in (1, 3):
        cx = rng.randint(2, ts - 3)
        cy = rng.randint(top_h + 2, ts - 2)
        crack_len = rng.randint(2, 4)
        for i in range(crack_len):
            px = cx + i
            py = cy + rng.randint(-1, 1)
            if 0 <= px < ts and 0 <= py < ts:
                surf.set_at((px, py), _c(r - 30, g - 28, b - 25))

    return surf


def _gen_built_wall(ts: int, variant: int) -> pygame.Surface:
    """Built wall — stone block grid with mortar and variation."""
    rng = _seeded_rng(BUILT_WALL, variant)
    r, g, b = TERRAIN_COLORS[BUILT_WALL]
    surf = pygame.Surface((ts, ts))

    block_size = max(3, ts // 4)
    mortar_c = _c(r - 18, g - 18, b - 15)
    surf.fill(mortar_c)

    for by in range(1, ts - 1, block_size + 1):
        row_off = (block_size // 2) if ((by - 1) // (block_size + 1)) % 2 else 0
        for bx in range(-block_size, ts + block_size, block_size + 1):
            x = bx + row_off + 1
            shade = rng.randint(-6, 8)
            bc = _c(r + 10 + shade, g + 10 + shade, b + 10 + shade)
            rect = pygame.Rect(x, by, block_size, block_size)
            rect = rect.clip(pygame.Rect(1, 1, ts - 2, ts - 2))
            if rect.width > 0 and rect.height > 0:
                pygame.draw.rect(surf, bc, rect)

    pygame.draw.rect(surf, _c(r - 15, g - 15, b - 15), (0, 0, ts, ts), 1)

    if variant % 2 == 1:
        cx = rng.randint(2, ts - 4)
        cy = rng.randint(2, ts - 4)
        for i in range(rng.randint(2, 4)):
            px = cx + i
            py = cy + rng.randint(-1, 1)
            if 0 <= px < ts and 0 <= py < ts:
                surf.set_at((px, py), _c(r - 25, g - 22, b - 18))

    return surf


# ============================================================
# BRIDGE
# ============================================================

def _gen_bridge(ts: int, variant: int) -> pygame.Surface:
    """Wooden bridge with plank pattern."""
    rng = _seeded_rng(BRIDGE, variant)
    r, g, b = TERRAIN_COLORS[BRIDGE]
    surf = pygame.Surface((ts, ts))
    surf.fill(_c(r - 15, g - 15, b - 15))

    plank_h = max(2, ts // 5)
    for py in range(0, ts, plank_h + 1):
        shade = rng.randint(-8, 8)
        plank_c = _c(r + shade, g + shade, b + shade)
        for y in range(py, min(py + plank_h, ts)):
            for x in range(ts):
                noise = rng.randint(-3, 3)
                surf.set_at((x, y), _c(plank_c[0] + noise,
                                       plank_c[1] + noise,
                                       plank_c[2] + noise))
        if py + plank_h < ts:
            gap_c = _c(r - 25, g - 25, b - 20)
            for x in range(ts):
                if py + plank_h < ts:
                    surf.set_at((x, py + plank_h), gap_c)

    for py in range(plank_h // 2, ts, plank_h + 1):
        for px in [1, ts - 2]:
            if 0 <= py < ts:
                surf.set_at((px, py), _c(80, 80, 85))

    rail_c = _c(r - 10, g - 10, b - 8)
    pygame.draw.line(surf, rail_c, (0, 0), (0, ts - 1))
    pygame.draw.line(surf, rail_c, (ts - 1, 0), (ts - 1, ts - 1))

    return surf


# ============================================================
# TILLED SOIL
# ============================================================

def _gen_tilled_soil(ts: int, variant: int) -> pygame.Surface:
    """Tilled soil with furrows and optional sprouts."""
    rng = _seeded_rng(TILLED_SOIL, variant)
    r, g, b = TERRAIN_COLORS[TILLED_SOIL]
    surf = pygame.Surface((ts, ts))

    _dither_fill_weighted(surf, ts, [
        (_c(r + 6, g + 5, b + 3), 0.30),
        (_c(r, g, b), 0.40),
        (_c(r - 8, g - 6, b - 4), 0.30),
    ], rng)

    furrow_c = _c(r - 12, g - 10, b - 6)
    spacing = max(3, ts // 5)
    for fx in range(spacing, ts - 1, spacing):
        pygame.draw.line(surf, furrow_c, (fx, 1), (fx, ts - 2))

    if variant in (1, 2):
        for sx in range(spacing + spacing // 2, ts - 1, spacing):
            sy = ts // 2 + rng.randint(-2, 2)
            sprout_h = rng.randint(2, 4)
            sprout_c = _c(60, 140 + rng.randint(-10, 10), 40)
            pygame.draw.line(surf, sprout_c, (sx, sy), (sx, sy - sprout_h))

    return surf


# ============================================================
# GENERATORS dict for this module
# ============================================================

BUILT_GENERATORS = {
    ROAD: _gen_road,
    FARMLAND: _gen_farmland,
    WALL: _gen_wall,
    BUILT_WALL: _gen_built_wall,
    BRIDGE: _gen_bridge,
    TILLED_SOIL: _gen_tilled_soil,
}
