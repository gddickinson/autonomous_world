"""Guaranteed hostile creature spawns near the Temple of Awakening.

Ensures Level 1 players encounter low-level threats within 200 tiles of spawn:
  - Wolf pack in nearby forest (100-150 tiles)
  - Giant rats near the temple ruins (30-60 tiles)
  - Bandit camp along the road (120-180 tiles)
  - Skeletons at the nearest ruins/special location (or fallback position)
"""

import math
import random as _random_mod
from typing import List, Tuple


def spawn_starter_hostiles(world, creatures_list, rng: _random_mod.Random):
    """Spawn guaranteed hostile creatures near the spawn temple.

    Args:
        world: The game world (ChunkedWorld or similar).
        creatures_list: The mutable list to append Creature objects to.
        rng: Seeded random instance.
    """
    from game.core.creature import Creature

    sx, sy = world.spawn_point

    spawned = []

    # --- 1. Wolf pack (3-5 wolves, 100-150 tiles away in a random direction) ---
    wolf_count = rng.randint(3, 5)
    wolf_angle = rng.uniform(0, 2 * math.pi)
    wolf_dist = rng.uniform(100, 150)
    wolf_cx = int(sx + math.cos(wolf_angle) * wolf_dist)
    wolf_cy = int(sy + math.sin(wolf_angle) * wolf_dist)
    for i in range(wolf_count):
        wx = wolf_cx + rng.randint(-4, 4)
        wy = wolf_cy + rng.randint(-4, 4)
        if world.is_walkable(wx, wy):
            c = Creature(float(wx), float(wy), "wolf")
            c.home_x = float(wolf_cx)
            c.home_y = float(wolf_cy)
            c.leash_range = 20.0
            creatures_list.append(c)
            spawned.append(c)

    # --- 2. Giant rats near the temple (30-60 tiles) ---
    rat_count = rng.randint(2, 3)
    rat_angle = rng.uniform(0, 2 * math.pi)
    rat_dist = rng.uniform(30, 60)
    rat_cx = int(sx + math.cos(rat_angle) * rat_dist)
    rat_cy = int(sy + math.sin(rat_angle) * rat_dist)
    for i in range(rat_count):
        rx = rat_cx + rng.randint(-3, 3)
        ry = rat_cy + rng.randint(-3, 3)
        if world.is_walkable(rx, ry):
            c = Creature(float(rx), float(ry), "rat")
            c.home_x = float(rat_cx)
            c.home_y = float(rat_cy)
            c.leash_range = 15.0
            creatures_list.append(c)
            spawned.append(c)

    # --- 3. Bandit camp (2-3 bandits, 120-180 tiles, prefer road direction) ---
    # Try to place near a road by picking a direction toward the nearest settlement
    nearest_settlement = _find_nearest_settlement(world, sx, sy)
    if nearest_settlement:
        dx = nearest_settlement.x - sx
        dy = nearest_settlement.y - sy
        road_angle = math.atan2(dy, dx)
    else:
        road_angle = rng.uniform(0, 2 * math.pi)
    # Offset slightly from the direct road line
    bandit_angle = road_angle + rng.uniform(-0.3, 0.3)
    bandit_dist = rng.uniform(120, 180)
    bandit_cx = int(sx + math.cos(bandit_angle) * bandit_dist)
    bandit_cy = int(sy + math.sin(bandit_angle) * bandit_dist)
    bandit_count = rng.randint(2, 3)
    for i in range(bandit_count):
        bx = bandit_cx + rng.randint(-3, 3)
        by = bandit_cy + rng.randint(-3, 3)
        if world.is_walkable(bx, by):
            c = Creature(float(bx), float(by), "bandit")
            c.home_x = float(bandit_cx)
            c.home_y = float(bandit_cy)
            c.leash_range = 18.0
            creatures_list.append(c)
            spawned.append(c)

    # --- 4. Skeletons (2-4) at the nearest ruins or a fallback position ---
    skeleton_count = rng.randint(2, 4)
    ruins_loc = _find_nearest_ruins(world, sx, sy, max_dist=200)
    if ruins_loc:
        skel_cx, skel_cy = ruins_loc
    else:
        # Fallback: opposite direction from wolves, ~80-120 tiles
        skel_angle = wolf_angle + math.pi + rng.uniform(-0.5, 0.5)
        skel_dist = rng.uniform(80, 120)
        skel_cx = int(sx + math.cos(skel_angle) * skel_dist)
        skel_cy = int(sy + math.sin(skel_angle) * skel_dist)
    for i in range(skeleton_count):
        kx = skel_cx + rng.randint(-4, 4)
        ky = skel_cy + rng.randint(-4, 4)
        if world.is_walkable(kx, ky):
            c = Creature(float(kx), float(ky), "skeleton")
            c.home_x = float(skel_cx)
            c.home_y = float(skel_cy)
            c.leash_range = 15.0
            creatures_list.append(c)
            spawned.append(c)

    return spawned


def _find_nearest_settlement(world, sx, sy):
    """Find the nearest settlement structure to (sx, sy)."""
    nearest = None
    nearest_dist = float("inf")
    for s in world.structures:
        if s.kind in ("village", "town", "city", "hamlet", "castle"):
            dx = s.x - sx
            dy = s.y - sy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = s
    return nearest


def _find_nearest_ruins(world, sx, sy, max_dist=200) -> Tuple[int, int]:
    """Find the nearest ruins or special location within max_dist.

    Returns (x, y) or None.
    """
    nearest = None
    nearest_dist = float("inf")
    for s in world.structures:
        if s.kind in ("ruins", "undead_crypt"):
            dx = s.x - sx
            dy = s.y - sy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < nearest_dist and dist <= max_dist:
                nearest_dist = dist
                nearest = s
    # Also check special locations (plan-level)
    if hasattr(world, "plan"):
        for loc in world.plan.special_locations:
            if loc.kind in ("ruins", "dungeon"):
                dx = loc.x - sx
                dy = loc.y - sy
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < nearest_dist and dist <= max_dist:
                    nearest_dist = dist
                    nearest = loc
    if nearest is None:
        return None
    return (nearest.x, nearest.y)
