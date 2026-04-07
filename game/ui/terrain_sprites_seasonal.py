"""Seasonal terrain tile variants — color shifts and accent details.

Applies per-season color adjustments and accent overlays (flowers, frost,
leaves, ice) to the base procedural tiles from terrain_sprites.py.

Public API:
    generate_seasonal_variant(tile_type, season, variant, ts) -> Surface
    generate_seasonal_terrain_sheets(ts, season) -> Dict[int, SpriteSheet]
"""

import pygame
import random
from typing import Dict

from game.ui.sprite_loader import SpriteSheet
from game.settings import (
    TERRAIN_COLORS, GRASS, WATER, FOREST, DENSE_FOREST, MOUNTAIN,
    SAND, SNOW, SWAMP,
)

# Local copies of tiny helpers to avoid circular import with terrain_sprites
NUM_VARIANTS = 4

def _clamp(v: int, lo: int = 0, hi: int = 255) -> int:
    return max(lo, min(hi, v))

def _c(r, g, b):
    return (_clamp(r), _clamp(g), _clamp(b))

def _seeded_rng(tile_type: int, variant: int) -> random.Random:
    return random.Random(tile_type * 1000 + variant * 7 + 42)

def _get_generators():
    """Lazily fetch generators from terrain_sprites (no top-level import)."""
    from game.ui.terrain_sprites import _NATURAL_GENERATORS, _GENERATORS, _load_built_generators
    return _NATURAL_GENERATORS, _GENERATORS, _load_built_generators


# ================================================================
# Per-season color adjustments: (r_shift, g_shift, b_shift)
# ================================================================

_SEASON_SHIFTS = {
    "spring": {
        GRASS:        (5, 35, 20),
        WATER:        (4, 7, 5),
        FOREST:       (15, 30, 15),
        DENSE_FOREST: (12, 30, 13),
        SAND:         (0, 0, 0),
        SNOW:         (0, 0, 0),
        SWAMP:        (5, 15, 5),
        MOUNTAIN:     (0, 0, 0),
    },
    "summer": {
        GRASS:        (0, 0, 0),
        WATER:        (0, 0, 0),
        FOREST:       (0, 0, 0),
        DENSE_FOREST: (0, 0, 0),
        SAND:         (5, 3, 0),
        SNOW:         (0, 0, 0),
        SWAMP:        (0, 0, 0),
        MOUNTAIN:     (0, 0, 0),
    },
    "autumn": {
        GRASS:        (45, -15, -15),
        WATER:        (0, -3, -5),
        FOREST:       (80, -15, -30),
        DENSE_FOREST: (70, -10, -25),
        SAND:         (5, 0, -5),
        SNOW:         (0, 0, 0),
        SWAMP:        (20, -5, -15),
        MOUNTAIN:     (5, 0, -5),
    },
    "winter": {
        GRASS:        (75, 30, 100),
        WATER:        (60, 32, 25),
        FOREST:       (85, 20, 90),
        DENSE_FOREST: (72, 25, 65),
        SAND:         (10, 10, 10),
        SNOW:         (0, 0, 0),
        SWAMP:        (55, 25, 60),
        MOUNTAIN:     (10, 10, 15),
    },
}


def _apply_season_shift(surf, ts, season, tile_type, rng):
    """Apply per-pixel seasonal color shift to an already-generated tile."""
    shifts = _SEASON_SHIFTS.get(season, {})
    shift = shifts.get(tile_type)
    if not shift or shift == (0, 0, 0):
        return surf

    dr, dg, db = shift
    for y in range(ts):
        for x in range(ts):
            c = surf.get_at((x, y))
            surf.set_at((x, y), _c(c[0] + dr, c[1] + dg, c[2] + db))
    return surf


# ================================================================
# Season-specific accent overlays
# ================================================================

def _add_spring_accents(surf, ts, tile_type, rng):
    """Wildflower dots and brighter canopy highlights."""
    if tile_type == GRASS:
        flower_colors = [(255, 255, 100), (255, 255, 255),
                         (255, 180, 200), (255, 220, 80)]
        for _ in range(rng.randint(2, 4)):
            fx = rng.randint(1, ts - 2)
            fy = rng.randint(1, ts - 2)
            surf.set_at((fx, fy), rng.choice(flower_colors))
    elif tile_type == FOREST:
        for _ in range(rng.randint(2, 4)):
            fx = rng.randint(ts // 4, 3 * ts // 4)
            fy = rng.randint(0, ts // 2)
            surf.set_at((fx, fy), _c(130, 210, 90))


def _add_summer_accents(surf, ts, tile_type, rng):
    """Golden grass edges and warm tones."""
    if tile_type == GRASS:
        for x in range(0, ts, 2):
            if rng.random() < 0.3:
                surf.set_at((x, ts - 1), _c(180, 170, 60))
                if ts > 8:
                    surf.set_at((x, ts - 2), _c(160, 155, 55))


def _add_autumn_accents(surf, ts, tile_type, rng):
    """Red/gold foliage dots and dry stalks."""
    if tile_type in (FOREST, DENSE_FOREST):
        accent_colors = [(200, 80, 30), (220, 160, 40), (180, 50, 20),
                         (210, 130, 30), (190, 100, 25)]
        for _ in range(rng.randint(3, 6)):
            fx = rng.randint(0, ts - 1)
            fy = rng.randint(0, ts // 2)
            surf.set_at((fx, fy), rng.choice(accent_colors))
    elif tile_type == GRASS:
        for _ in range(rng.randint(1, 3)):
            sx = rng.randint(1, ts - 2)
            sy = rng.randint(ts // 2, ts - 2)
            surf.set_at((sx, sy), _c(160, 130, 50))


def _add_winter_accents(surf, ts, tile_type, rng):
    """Snow speckles, bare trees, ice-blue water."""
    if tile_type == GRASS:
        for _ in range(rng.randint(3, 6)):
            sx = rng.randint(0, ts - 1)
            sy = rng.randint(0, ts - 1)
            shade = 230 + rng.randint(0, 20)
            surf.set_at((sx, sy), _c(shade, shade + 2, shade + 5))
    elif tile_type in (FOREST, DENSE_FOREST):
        for _ in range(rng.randint(2, 5)):
            sx = rng.randint(ts // 4, 3 * ts // 4)
            sy = rng.randint(0, ts // 2)
            surf.set_at((sx, sy), _c(235, 238, 245))
    elif tile_type == WATER:
        for _ in range(rng.randint(2, 4)):
            ix = rng.randint(1, ts - 2)
            iy = rng.randint(1, ts - 2)
            surf.set_at((ix, iy), _c(180, 210, 240))


# ================================================================
# Public API
# ================================================================

_ACCENT_FUNCS = {
    "spring": _add_spring_accents,
    "summer": _add_summer_accents,
    "autumn": _add_autumn_accents,
    "winter": _add_winter_accents,
}


def generate_seasonal_variant(tile_type: int, season: str,
                              variant: int, ts: int = 16) -> pygame.Surface:
    """Generate a tile surface with seasonal color variation.

    Args:
        tile_type: terrain constant (GRASS, FOREST, etc.)
        season: "spring", "summer", "autumn", or "winter"
        variant: tile variant index (0-3)
        ts: tile size in pixels

    Returns:
        A pygame.Surface with the seasonal variant.
    """
    _nat, _gens, _load = _get_generators()
    _load()
    gen_func = _gens.get(tile_type)
    if gen_func is None:
        surf = pygame.Surface((ts, ts))
        surf.fill(TERRAIN_COLORS.get(tile_type, (100, 100, 100)))
        return surf

    rng = _seeded_rng(tile_type * 100 + hash(season), variant)
    surf = gen_func(ts, variant)
    surf = _apply_season_shift(surf, ts, season, tile_type, rng)

    accent = _ACCENT_FUNCS.get(season)
    if accent:
        accent(surf, ts, tile_type, rng)

    return surf


def generate_seasonal_terrain_sheets(ts: int,
                                     season: str) -> Dict[int, SpriteSheet]:
    """Generate sprite sheets with seasonal variants for natural terrain.

    Returns:
        Dict mapping terrain_type -> SpriteSheet (4 variants each).
    """
    _nat, _gens, _load = _get_generators()
    sheets = {}
    for terrain_type in _nat:
        sheet_surf = pygame.Surface((ts * NUM_VARIANTS, ts))
        for v in range(NUM_VARIANTS):
            tile = generate_seasonal_variant(terrain_type, season, v, ts)
            sheet_surf.blit(tile, (v * ts, 0))
        sheets[terrain_type] = SpriteSheet(sheet_surf, ts, ts)
    return sheets
