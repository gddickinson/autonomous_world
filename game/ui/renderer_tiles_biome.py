"""Tile surface builders for biome-variety and dungeon-puzzle tile types.

Covers tile types 68-79: courtyard, arena, scorched earth, ice, dungeon
puzzles, hot springs, tundra, jungle, dunes, and oasis.

Split from renderer_tiles_detail.py to keep each module under 500 lines.
"""

import pygame
from game.settings import (
    TERRAIN_COLORS, GRASS, COURTYARD, ARENA_SAND, SCORCHED_EARTH,
    ICE_SHEET, LEVER, PRESSURE_PLATE, RIDDLE_DOOR, HOT_SPRING,
    TUNDRA, JUNGLE, DUNE, OASIS_WATER,
)


_BIOME_BUILDERS = {}  # populated after function definitions


def build_biome_tile(surf, terrain_type, r, g, b, cx, cy, ts):
    """Dispatch to the appropriate builder for biome/puzzle tile types 68-79."""
    builder = _BIOME_BUILDERS.get(terrain_type)
    if builder:
        builder(surf, r, g, b, cx, cy, ts)


def _build_courtyard(surf, r, g, b, ts):
    """Open courtyard — flagstone pattern."""
    for i in range(0, ts, 6):
        for j in range(0, ts, 6):
            shade = r + ((i + j) % 3) * 4 - 4
            pygame.draw.rect(surf, (shade, max(0, g + (j % 3) - 2),
                                    max(0, b - 2)),
                             (i, j, 5, 5))
    # Subtle grid lines
    for i in range(0, ts, 6):
        pygame.draw.line(surf, (max(0, r - 15), max(0, g - 15), max(0, b - 12)),
                         (i, 0), (i, ts))
        pygame.draw.line(surf, (max(0, r - 15), max(0, g - 15), max(0, b - 12)),
                         (0, i), (ts, i))


def _build_arena_sand(surf, r, g, b, ts):
    """Arena fighting floor — packed sand with scuff marks."""
    for i in range(6):
        gx = (hash(i * 11 + 3) % (ts - 2)) + 1
        gy = (hash(i * 17 + 5) % (ts - 2)) + 1
        shade = (min(255, r + 8), min(255, g + 5), min(255, b + 3))
        surf.set_at((gx, gy), shade)
    # Scuff marks
    for i in range(2):
        sx = (hash(i * 13 + 7) % (ts - 6)) + 3
        sy = (hash(i * 19 + 11) % (ts - 6)) + 3
        pygame.draw.line(surf, (max(0, r - 20), max(0, g - 20), max(0, b - 15)),
                         (sx, sy), (sx + 3, sy + 1))


def _build_scorched_earth(surf, r, g, b, ts):
    """Fire-blackened ground with ember spots and char patterns."""
    # Char cracks
    for i in range(4):
        cx = (hash(i * 7 + 1) % (ts - 4)) + 2
        cy = (hash(i * 13 + 3) % (ts - 4)) + 2
        pygame.draw.line(surf, (max(0, r - 15), max(0, g - 15), max(0, b - 12)),
                         (cx, cy), (cx + 3, cy + 2))
    # Ember spots (orange/red)
    for i in range(3):
        ex = (hash(i * 11 + 5) % (ts - 2)) + 1
        ey = (hash(i * 17 + 9) % (ts - 2)) + 1
        pygame.draw.circle(surf, (min(255, 120 + i * 30), 40, 10),
                           (ex, ey), 1)
    # Ash patches
    for i in range(3):
        ax = (hash(i * 9 + 2) % (ts - 3)) + 1
        ay = (hash(i * 15 + 7) % (ts - 3)) + 1
        pygame.draw.circle(surf, (60, 55, 48), (ax, ay), 2)


def _build_ice_sheet(surf, r, g, b, ts):
    """Frozen surface with cracks and reflections."""
    # Ice cracks
    for i in range(3):
        ix = (hash(i * 13 + 1) % (ts - 6)) + 3
        iy = (hash(i * 17 + 3) % (ts - 6)) + 3
        pygame.draw.line(surf, (min(255, r + 15), min(255, g + 10), min(255, b + 8)),
                         (ix, iy), (ix + 4, iy + 2))
    # Reflective highlights
    for i in range(2):
        hx = (hash(i * 7 + 5) % (ts - 2)) + 1
        hy = (hash(i * 11 + 9) % (ts - 2)) + 1
        pygame.draw.circle(surf, (min(255, r + 30), min(255, g + 25), min(255, b + 15)),
                           (hx, hy), 1)


def _build_lever(surf, r, g, b, cx, cy, ts):
    """Puzzle lever on floor tile."""
    surf.fill((160, 130, 95))  # floor base
    # Lever base
    pygame.draw.rect(surf, (100, 90, 75), (cx - 3, cy + 2, 6, 3))
    # Lever arm (angled)
    pygame.draw.line(surf, (r, g, b), (cx, cy + 3), (cx - 3, cy - 4), 2)
    # Handle knob
    pygame.draw.circle(surf, (min(255, r + 20), min(255, g + 20), b),
                       (cx - 3, cy - 4), 2)


def _build_pressure_plate(surf, r, g, b, cx, cy, ts):
    """Puzzle pressure plate — raised stone slab on floor."""
    surf.fill((160, 130, 95))  # floor base
    # Plate
    pygame.draw.rect(surf, (r, g, b), (3, 3, ts - 6, ts - 6))
    pygame.draw.rect(surf, (min(255, r + 15), min(255, g + 15), min(255, b + 12)),
                     (3, 3, ts - 6, ts - 6), 1)
    # Center mark
    pygame.draw.circle(surf, (min(255, r + 10), min(255, g + 10), min(255, b + 8)),
                       (cx, cy), 2)


def _build_riddle_door(surf, r, g, b, cx, cy, ts):
    """Puzzle door with riddle — ornate door with glyph."""
    surf.fill((160, 130, 95))  # floor base
    # Door frame
    pygame.draw.rect(surf, (r, g, b), (3, 0, ts - 6, ts))
    # Mysterious glyph (question mark shape)
    pygame.draw.arc(surf, (180, 160, 220), (cx - 3, cy - 5, 6, 6),
                    0.5, 3.14, 2)
    pygame.draw.circle(surf, (180, 160, 220), (cx, cy + 2), 1)


def _build_hot_spring(surf, r, g, b, cx, cy, ts):
    """Volcanic hot spring — steamy blue-green water with bubbles."""
    # Water
    for i in range(3):
        y_pos = 4 + i * 5
        wave = (min(255, r + 20), min(255, g + 15), min(255, b + 10))
        for px in range(ts):
            offset = (px * 3 + i * 5) % 4
            if offset < 2:
                surf.set_at((px, y_pos), wave)
    # Steam/bubbles
    for i in range(4):
        bx = (hash(i * 7 + 3) % (ts - 4)) + 2
        by = (hash(i * 11 + 7) % (ts - 4)) + 2
        pygame.draw.circle(surf, (min(255, r + 40), min(255, g + 30),
                                  min(255, b + 20)),
                           (bx, by), 1)


def _build_tundra(surf, r, g, b, ts):
    """Frozen grassland — pale grass with frost and sparse tufts."""
    # Frost speckles
    for i in range(6):
        fx = hash(i * 17 + 1) % ts
        fy = hash(i * 23 + 5) % ts
        pygame.draw.circle(surf, (min(255, r + 15), min(255, g + 12),
                                  min(255, b + 10)),
                           (fx, fy), 1)
    # Sparse brown grass tufts
    for i in range(3):
        gx = (hash(i * 13 + 9) % (ts - 2)) + 1
        gy = (hash(i * 7 + 3) % (ts - 2)) + 1
        pygame.draw.line(surf, (140, 130, 100), (gx, gy), (gx, gy - 2))


def _build_jungle(surf, r, g, b, ts):
    """Dense tropical vegetation — layered greens with vines."""
    # Dense undergrowth circles
    for i in range(5):
        jx = (hash(i * 11 + 2) % (ts - 4)) + 2
        jy = (hash(i * 17 + 6) % (ts - 4)) + 2
        radius = 2 + (i % 2)
        shade = (max(0, r - 5 + i * 3), min(255, g + 10 - i * 4),
                 max(0, b - 3 + i * 2))
        pygame.draw.circle(surf, shade, (jx, jy), radius)
    # Vine lines
    for i in range(2):
        vx = (hash(i * 9 + 4) % (ts - 2)) + 1
        pygame.draw.line(surf, (max(0, r + 5), min(255, g + 20), max(0, b + 5)),
                         (vx, 0), (vx + 2, ts))


def _build_dune(surf, r, g, b, ts):
    """Sand dune — wind-swept ridges and shadow lines."""
    # Wind ridges
    for i in range(4):
        y_pos = 3 + i * 4
        ridge = (min(255, r + 10), min(255, g + 8), min(255, b + 5))
        shadow = (max(0, r - 15), max(0, g - 12), max(0, b - 8))
        pygame.draw.line(surf, ridge, (0, y_pos), (ts, y_pos))
        pygame.draw.line(surf, shadow, (0, y_pos + 1), (ts, y_pos + 1))
    # Grain dots
    for i in range(5):
        gx = hash(i * 13 + 7) % ts
        gy = hash(i * 19 + 3) % ts
        surf.set_at((gx, gy), (min(255, r + 15), min(255, g + 12),
                                min(255, b + 8)))


def _build_oasis_water(surf, r, g, b, cx, cy, ts):
    """Oasis pool — clear water with palm-green tint."""
    # Gentle waves
    for i in range(3):
        y_pos = 4 + i * 5
        wave = (min(255, r + 25), min(255, g + 20), min(255, b + 15))
        for px in range(ts):
            offset = (px * 2 + i * 7) % 5
            if offset < 2:
                surf.set_at((px, y_pos), wave)
    # Sparkle
    for i in range(2):
        sx = (hash(i * 11 + 5) % (ts - 2)) + 1
        sy = (hash(i * 17 + 3) % (ts - 2)) + 1
        surf.set_at((sx, sy), (min(255, r + 50), min(255, g + 45),
                                min(255, b + 35)))


# ── Dispatch table (populated after all builders are defined) ──────────
# Each wrapper normalizes to (surf, r, g, b, cx, cy, ts) signature.
_BIOME_BUILDERS.update({
    COURTYARD:      lambda s, r, g, b, cx, cy, ts: _build_courtyard(s, r, g, b, ts),
    ARENA_SAND:     lambda s, r, g, b, cx, cy, ts: _build_arena_sand(s, r, g, b, ts),
    SCORCHED_EARTH: lambda s, r, g, b, cx, cy, ts: _build_scorched_earth(s, r, g, b, ts),
    ICE_SHEET:      lambda s, r, g, b, cx, cy, ts: _build_ice_sheet(s, r, g, b, ts),
    LEVER:          lambda s, r, g, b, cx, cy, ts: _build_lever(s, r, g, b, cx, cy, ts),
    PRESSURE_PLATE: lambda s, r, g, b, cx, cy, ts: _build_pressure_plate(s, r, g, b, cx, cy, ts),
    RIDDLE_DOOR:    lambda s, r, g, b, cx, cy, ts: _build_riddle_door(s, r, g, b, cx, cy, ts),
    HOT_SPRING:     lambda s, r, g, b, cx, cy, ts: _build_hot_spring(s, r, g, b, cx, cy, ts),
    TUNDRA:         lambda s, r, g, b, cx, cy, ts: _build_tundra(s, r, g, b, ts),
    JUNGLE:         lambda s, r, g, b, cx, cy, ts: _build_jungle(s, r, g, b, ts),
    DUNE:           lambda s, r, g, b, cx, cy, ts: _build_dune(s, r, g, b, ts),
    OASIS_WATER:    lambda s, r, g, b, cx, cy, ts: _build_oasis_water(s, r, g, b, cx, cy, ts),
})
