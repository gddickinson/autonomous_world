"""Divine Realm — Mt Olympus / Nirvana, the home of the gods.

A separate 200x200 floating island map with marble buildings,
a viewing pool for observing the mortal world, a portal gate,
and resident god NPCs from the pantheon.
"""

import math
import random
from typing import List, Dict, Tuple, Optional

from game.settings import (
    WATER, FLOOR, WALL, DOOR, PILLAR, FOUNTAIN, ALTAR,
    THRONE, CARPET, BOOKSHELF, CHEST, TABLE, FIREPLACE,
)

# Divine tile types (defined in settings.py)
CLOUD = 80
MARBLE_FLOOR = 81
DIVINE_WATER = 82
GOLDEN_PATH = 83

REALM_SIZE = 200
ISLAND_RADIUS = 80
CENTER = REALM_SIZE // 2


def generate_divine_realm(seed: int = 42) -> Dict:
    """Generate the divine realm tile map and structure positions.

    Returns dict with:
      tiles: 2D list [y][x] of tile types
      structures: list of {name, kind, x, y, w, h}
      god_spawns: list of {name, x, y, domain}
      portal_pos: (x, y)
      pool_pos: (x, y)
    """
    rng = random.Random(seed)
    tiles = [[CLOUD] * REALM_SIZE for _ in range(REALM_SIZE)]

    # Carve island shape (slightly irregular circle)
    for y in range(REALM_SIZE):
        for x in range(REALM_SIZE):
            dx, dy = x - CENTER, y - CENTER
            dist = math.sqrt(dx * dx + dy * dy)
            # Slight irregularity
            angle = math.atan2(dy, dx)
            wobble = 5 * math.sin(angle * 3 + seed * 0.1)
            if dist < ISLAND_RADIUS + wobble:
                tiles[y][x] = MARBLE_FLOOR

    # Golden paths — cross pattern from center
    for d in range(ISLAND_RADIUS - 10):
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            px = CENTER + dx * d
            py = CENTER + dy * d
            if 0 <= px < REALM_SIZE and 0 <= py < REALM_SIZE:
                tiles[py][px] = GOLDEN_PATH
                # 3-tile wide paths
                for ox in range(-1, 2):
                    for oy in range(-1, 2):
                        nx, ny = px + ox, py + oy
                        if 0 <= nx < REALM_SIZE and 0 <= ny < REALM_SIZE:
                            if tiles[ny][nx] == MARBLE_FLOOR:
                                tiles[ny][nx] = GOLDEN_PATH

    structures = []
    god_spawns = []

    # Viewing Pool — center, 15-tile radius circle of divine water
    pool_r = 15
    for dy in range(-pool_r, pool_r + 1):
        for dx in range(-pool_r, pool_r + 1):
            if dx * dx + dy * dy <= pool_r * pool_r:
                px, py = CENTER + dx, CENTER + dy
                if 0 <= px < REALM_SIZE and 0 <= py < REALM_SIZE:
                    tiles[py][px] = DIVINE_WATER
    # Ring of pillars around pool
    for i in range(12):
        a = 2 * math.pi * i / 12
        px = int(CENTER + (pool_r + 2) * math.cos(a))
        py = int(CENTER + (pool_r + 2) * math.sin(a))
        if 0 <= px < REALM_SIZE and 0 <= py < REALM_SIZE:
            tiles[py][px] = PILLAR
    structures.append({"name": "Viewing Pool", "kind": "pool",
                       "x": CENTER - pool_r, "y": CENTER - pool_r,
                       "w": pool_r * 2, "h": pool_r * 2})

    # Pantheon Temple — north
    tx, ty = CENTER - 15, CENTER - 55
    _build_temple(tiles, tx, ty, 30, 20)
    structures.append({"name": "Pantheon Temple", "kind": "temple",
                       "x": tx, "y": ty, "w": 30, "h": 20})
    # God thrones inside temple
    gods = [
        {"name": "Tharion", "domain": "War & Honor", "x": tx + 5, "y": ty + 10},
        {"name": "Sylvana", "domain": "Nature & Beasts", "x": tx + 10, "y": ty + 10},
        {"name": "Verithos", "domain": "Knowledge & Magic", "x": tx + 15, "y": ty + 10},
        {"name": "Morwen", "domain": "Death & Fate", "x": tx + 20, "y": ty + 10},
        {"name": "Auriel", "domain": "Commerce & Wealth", "x": tx + 25, "y": ty + 10},
        {"name": "Lyria", "domain": "Love & Compassion", "x": tx + 8, "y": ty + 15},
        {"name": "Xaotl", "domain": "Chaos & Change", "x": tx + 22, "y": ty + 15},
    ]
    for g in gods:
        if 0 <= g["x"] < REALM_SIZE and 0 <= g["y"] < REALM_SIZE:
            tiles[g["y"]][g["x"]] = THRONE
        god_spawns.append(g)

    # Portal Gate — west
    px, py = CENTER - 55, CENTER - 5
    _build_portal(tiles, px, py, 10, 10)
    structures.append({"name": "Portal Gate", "kind": "portal",
                       "x": px, "y": py, "w": 10, "h": 10})
    portal_pos = (px + 5, py + 5)

    # Armory of the Divine — east
    ax, ay = CENTER + 40, CENTER - 8
    _build_building(tiles, ax, ay, 16, 16, "armory")
    structures.append({"name": "Armory of the Divine", "kind": "armory",
                       "x": ax, "y": ay, "w": 16, "h": 16})

    # Garden of Eternity — south
    gx, gy = CENTER - 20, CENTER + 35
    _build_garden(tiles, gx, gy, 40, 25)
    structures.append({"name": "Garden of Eternity", "kind": "garden",
                       "x": gx, "y": gy, "w": 40, "h": 25})

    # Trophy Hall — northeast
    hx, hy = CENTER + 30, CENTER - 40
    _build_building(tiles, hx, hy, 14, 12, "trophy")
    structures.append({"name": "Trophy Hall", "kind": "trophy_hall",
                       "x": hx, "y": hy, "w": 14, "h": 12})

    # Central fountain at viewing pool edge
    tiles[CENTER - pool_r - 1][CENTER] = FOUNTAIN

    return {
        "tiles": tiles,
        "structures": structures,
        "god_spawns": god_spawns,
        "portal_pos": portal_pos,
        "pool_pos": (CENTER, CENTER),
        "size": REALM_SIZE,
    }


def _build_temple(tiles, x, y, w, h):
    """Build a grand columned temple."""
    for dy in range(h):
        for dx in range(w):
            tx, ty_ = x + dx, y + dy
            if 0 <= tx < REALM_SIZE and 0 <= ty_ < REALM_SIZE:
                if dy == 0 or dy == h - 1 or dx == 0 or dx == w - 1:
                    tiles[ty_][tx] = WALL
                else:
                    tiles[ty_][tx] = MARBLE_FLOOR
    # Pillars along sides
    for i in range(2, w - 2, 4):
        for row in [y + 2, y + h - 3]:
            if 0 <= x + i < REALM_SIZE and 0 <= row < REALM_SIZE:
                tiles[row][x + i] = PILLAR
    # Altar at back
    if 0 <= x + w // 2 < REALM_SIZE and 0 <= y + 3 < REALM_SIZE:
        tiles[y + 3][x + w // 2] = ALTAR
    # Carpet aisle
    for dy in range(3, h - 1):
        if 0 <= x + w // 2 < REALM_SIZE and 0 <= y + dy < REALM_SIZE:
            tiles[y + dy][x + w // 2] = CARPET
    # Doors
    if 0 <= x + w // 2 < REALM_SIZE and 0 <= y + h - 1 < REALM_SIZE:
        tiles[y + h - 1][x + w // 2] = DOOR


def _build_portal(tiles, x, y, w, h):
    """Build a shimmering portal structure."""
    for dy in range(h):
        for dx in range(w):
            tx, ty_ = x + dx, y + dy
            if 0 <= tx < REALM_SIZE and 0 <= ty_ < REALM_SIZE:
                dist = math.sqrt((dx - w // 2) ** 2 + (dy - h // 2) ** 2)
                if dist < min(w, h) // 2 - 1:
                    tiles[ty_][tx] = DIVINE_WATER  # portal shimmer
                elif dist < min(w, h) // 2 + 1:
                    tiles[ty_][tx] = PILLAR  # portal frame


def _build_building(tiles, x, y, w, h, kind):
    """Build a rectangular marble building."""
    for dy in range(h):
        for dx in range(w):
            tx, ty_ = x + dx, y + dy
            if 0 <= tx < REALM_SIZE and 0 <= ty_ < REALM_SIZE:
                if dy == 0 or dy == h - 1 or dx == 0 or dx == w - 1:
                    tiles[ty_][tx] = WALL
                else:
                    tiles[ty_][tx] = MARBLE_FLOOR
    # Door
    if 0 <= x + w // 2 < REALM_SIZE and 0 <= y + h - 1 < REALM_SIZE:
        tiles[y + h - 1][x + w // 2] = DOOR
    # Interior based on kind
    if kind == "armory":
        for i in range(2, w - 2, 3):
            if 0 <= x + i < REALM_SIZE and 0 <= y + 2 < REALM_SIZE:
                tiles[y + 2][x + i] = CHEST
    elif kind == "trophy":
        for i in range(2, w - 2, 3):
            if 0 <= x + i < REALM_SIZE and 0 <= y + 2 < REALM_SIZE:
                tiles[y + 2][x + i] = BOOKSHELF


def _build_garden(tiles, x, y, w, h):
    """Build a garden with paths and green patches."""
    rng = random.Random(x * 7 + y * 13)
    for dy in range(h):
        for dx in range(w):
            tx, ty_ = x + dx, y + dy
            if 0 <= tx < REALM_SIZE and 0 <= ty_ < REALM_SIZE:
                if dx == 0 or dx == w - 1 or dy == 0 or dy == h - 1:
                    tiles[ty_][tx] = GOLDEN_PATH  # garden border
                elif (dx + dy) % 6 == 0:
                    tiles[ty_][tx] = GOLDEN_PATH  # garden paths
                elif rng.random() < 0.1:
                    tiles[ty_][tx] = FOUNTAIN  # decorative fountains
                else:
                    tiles[ty_][tx] = MARBLE_FLOOR
