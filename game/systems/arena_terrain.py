"""Arena terrain layouts — hills, trenches, obstacles, mud, fortress."""

import random
import math
from typing import Tuple
from game.systems.colosseum import ArenaTerrain

def make_arena_flat(cx: float, cy: float, radius: int = 20) -> ArenaTerrain:
    """Standard flat arena — no terrain features."""
    size = radius * 2
    t = ArenaTerrain(size, size, cx, cy)
    t.name = "flat"
    return t



def make_arena_hills(cx: float, cy: float, radius: int = 20) -> ArenaTerrain:
    """Arena with two hills on opposite sides — elevation matters."""
    size = radius * 2
    t = ArenaTerrain(size, size, cx, cy)
    t.name = "hills"
    mid = size // 2
    # Hill on left (team 0 side)
    for y in range(mid - 5, mid + 6):
        for x in range(3, 10):
            t.elevation[y, x] = t.RAISED
    for y in range(mid - 3, mid + 4):
        for x in range(5, 8):
            t.elevation[y, x] = t.HIGH_GROUND
    # Hill on right (team 1 side)
    for y in range(mid - 5, mid + 6):
        for x in range(size - 10, size - 3):
            t.elevation[y, x] = t.RAISED
    for y in range(mid - 3, mid + 4):
        for x in range(size - 8, size - 5):
            t.elevation[y, x] = t.HIGH_GROUND
    return t



def make_arena_trenches(cx: float, cy: float, radius: int = 20) -> ArenaTerrain:
    """Arena with defensive trenches across the middle."""
    size = radius * 2
    t = ArenaTerrain(size, size, cx, cy)
    t.name = "trenches"
    mid_x = size // 2
    mid_y = size // 2
    # Two trenches running north-south
    for y in range(5, size - 5):
        for dx in [-3, -2, 3, 4]:
            x = mid_x + dx
            if 0 <= x < size:
                t.elevation[y, x] = t.DITCH
    return t



def make_arena_obstacles(cx: float, cy: float, radius: int = 20) -> ArenaTerrain:
    """Arena with scattered cover — barricades, pillars, walls."""
    size = radius * 2
    t = ArenaTerrain(size, size, cx, cy)
    t.name = "obstacles"
    rng = random.Random(42)
    mid = size // 2
    # Scatter half-cover barricades
    for _ in range(12):
        bx = rng.randint(5, size - 6)
        by = rng.randint(5, size - 6)
        # Horizontal or vertical barricade (3 tiles long)
        if rng.random() < 0.5:
            for dx in range(3):
                if 0 <= bx + dx < size:
                    t.cover[by, bx + dx] = t.COVER_HALF
        else:
            for dy in range(3):
                if 0 <= by + dy < size:
                    t.cover[by + dy, bx] = t.COVER_HALF
    # A few full-cover pillars
    for _ in range(4):
        px = rng.randint(8, size - 9)
        py = rng.randint(8, size - 9)
        t.cover[py, px] = t.COVER_FULL
        t.obstacle[py, px] = True
    return t



def make_arena_mud(cx: float, cy: float, radius: int = 20) -> ArenaTerrain:
    """Arena with a muddy center — slows movement through the middle."""
    size = radius * 2
    t = ArenaTerrain(size, size, cx, cy)
    t.name = "mud_pit"
    mid = size // 2
    # Circular mud pit in center
    for y in range(size):
        for x in range(size):
            dx, dy = x - mid, y - mid
            if dx * dx + dy * dy < 64:  # radius ~8
                t.mud[y, x] = True
    return t



def make_arena_fortress(cx: float, cy: float, radius: int = 20) -> ArenaTerrain:
    """One side has a fortified position — walls, elevation, cover."""
    size = radius * 2
    t = ArenaTerrain(size, size, cx, cy)
    t.name = "fortress"
    # Right side (team 1) gets a fortress
    fort_x = size - 12
    # Raised platform
    for y in range(size // 2 - 6, size // 2 + 7):
        for x in range(fort_x, size - 3):
            t.elevation[y, x] = t.RAISED
    # Wall line with gaps
    for y in range(size // 2 - 6, size // 2 + 7):
        t.cover[y, fort_x] = t.COVER_FULL
        t.obstacle[y, fort_x] = True
    # Gaps for entry
    t.cover[size // 2, fort_x] = t.COVER_NONE
    t.obstacle[size // 2, fort_x] = False
    t.cover[size // 2 - 4, fort_x] = t.COVER_NONE
    t.obstacle[size // 2 - 4, fort_x] = False
    t.cover[size // 2 + 4, fort_x] = t.COVER_NONE
    t.obstacle[size // 2 + 4, fort_x] = False
    # Ditch in front of fortress
    for y in range(size // 2 - 7, size // 2 + 8):
        if 0 <= fort_x - 2 < size:
            t.elevation[y, fort_x - 2] = t.DITCH
            t.elevation[y, fort_x - 1] = t.DITCH
    return t



