"""Volcanic island terrain generation with ridges, rivers, and Whittaker biomes.

Replaces the legacy circular-island FBM terrain with:
  1. Domain-warped radial island shape with rift arms
  2. Ridged multifractal mountain spines
  3. Priority-flood sink filling (Barnes et al. 2014)
  4. D8 flow-accumulation river network
  5. Whittaker biome classification (temperature x moisture)
  6. Regional climate zones (desert, tundra, tropical, volcanic)
  7. Satellite mini-islands in the ocean

All per-tile functions are numpy-vectorized for chunk-level performance.
"""

import math
import heapq
import random
import numpy as np
from typing import List, Tuple

from game.settings import (
    WATER, SAND, GRASS, FOREST, DENSE_FOREST, MOUNTAIN, SNOW,
    SWAMP, ROCKY_GROUND, SCORCHED_EARTH, HOT_SPRING,
    TUNDRA, JUNGLE, DUNE,
)
from game.world.regional_climate import (
    apply_regional_climate,
    compute_volcanic_tiles,
    add_mini_island_elevation,
)

# ================================================================
# NOISE HELPERS
# ================================================================

def _hash2d(x, y, seed):
    """Vectorized 2D hash for noise generation."""
    x = x.astype(np.int64)
    y = y.astype(np.int64)
    n = x * 374761393 + y * 668265263 + seed * 1274126177
    n = (n ^ (n >> 13)) * np.int64(1274126177)
    n = n ^ (n >> 16)
    return (n & np.int64(0x7FFFFFFF)).astype(np.float32) / np.float32(0x7FFFFFFF)


def _fbm(x, y, octaves=5, gain=0.5, seed=0):
    """Vectorized FBM noise using hash-based value noise."""
    total = np.zeros_like(x)
    amp = 1.0
    freq = 1.0
    max_val = 0.0
    for i in range(octaves):
        sx, sy = x * freq, y * freq
        ix, iy = np.floor(sx).astype(np.int64), np.floor(sy).astype(np.int64)
        fx = sx - ix; fy = sy - iy
        fx = fx * fx * (3.0 - 2.0 * fx)
        fy = fy * fy * (3.0 - 2.0 * fy)
        s = seed + i * 31
        v00 = _hash2d(ix, iy, s); v10 = _hash2d(ix + 1, iy, s)
        v01 = _hash2d(ix, iy + 1, s); v11 = _hash2d(ix + 1, iy + 1, s)
        val = (v00 + (v10 - v00) * fx) + ((v01 + (v11 - v01) * fx)
               - (v00 + (v10 - v00) * fx)) * fy
        total += val * amp
        max_val += amp
        amp *= gain
        freq *= 2.0
    return total / max_val


# ================================================================
# 1. ISLAND SHAPE — Domain-Warped Radial with Rift Arms
# ================================================================

def island_elevation(wx, wy, world_w, world_h, seed):
    """Compute base island elevation at world coordinates (vectorized).

    Creates an irregular volcanic island with:
    - Multiple peaks along rift arms (not one central dome)
    - Deep bays between arms
    - Domain-warped coastline
    - Valleys between ridges
    """
    dx = (wx / world_w - 0.5) * 2.0
    dy = (wy / world_h - 0.5) * 2.0

    # Domain warp for irregular coast
    warp_s = 0.002
    warp_a = 400.0 / max(world_w, world_h) * 2.0
    dx = dx + (_fbm(wx * warp_s, wy * warp_s, 3, seed=seed + 1111) - 0.5) * warp_a
    dy = dy + (_fbm(wx * warp_s + 50, wy * warp_s + 50, 3, seed=seed + 2222) - 0.5) * warp_a

    r = np.sqrt(dx * dx + dy * dy)
    theta = np.arctan2(dy, dx)

    # Rift arms — 3-4 protruding lobes at ~120° spacing
    arm_rng = random.Random(seed + 9999)
    n_arms = arm_rng.randint(3, 4)
    base_ang = arm_rng.uniform(0, 2 * math.pi)
    arm_angles = [base_ang + i * (2 * math.pi / n_arms)
                  + arm_rng.uniform(-0.3, 0.3) for i in range(n_arms)]
    arm_strengths = [arm_rng.uniform(0.25, 0.45) for _ in range(n_arms)]

    # Base radius is SMALL — arms add the land mass
    base_r = 0.30
    warped_radius = np.full_like(r, base_r)
    for ang, strength in zip(arm_angles, arm_strengths):
        # Wider lobes (power 1.5 instead of 2.5) for more pronounced arms
        warped_radius += strength * np.maximum(0.0, np.cos(theta - ang)) ** 1.5

    # Angle-based noise for coast irregularity
    angle_noise = _fbm(np.cos(theta) * 4.0 + seed * 0.01,
                        np.sin(theta) * 4.0 + seed * 0.01, 3, seed=seed + 3333)
    warped_radius += (angle_noise - 0.5) * 0.12

    # Soft falloff — use smoother curve for more gradual coast
    ratio = r / np.maximum(warped_radius, 0.01)
    base_elev = np.maximum(0.0, 1.0 - ratio ** 1.5)

    # Multiple peaks along ridges instead of one central dome
    # Use high-frequency noise to create peaks and saddles
    peak_noise = _fbm(wx * 0.006, wy * 0.006, 3, seed=seed + 4444)
    # Peaks where noise is high, valleys where low — modulates elevation
    peak_factor = 0.4 + peak_noise * 0.6  # range 0.4-1.0
    base_elev *= peak_factor

    # Ridge noise along arms — creates sharp ridgelines
    ridge_noise = 1.0 - np.abs(_fbm(wx * 0.008, wy * 0.008, 4, seed=seed + 5555) - 0.5) * 2.0
    ridge_noise = ridge_noise ** 2  # sharpen ridges
    # Only add ridges where elevation is already moderate (mountains, not coast)
    ridge_mask = np.clip(base_elev * 3.0, 0, 1)
    base_elev += ridge_noise * 0.15 * ridge_mask

    # FBM detail noise for terrain roughness
    detail = _fbm(wx * 0.015, wy * 0.015, 5, seed=seed)
    elev = base_elev * (0.7 + detail * 0.3)

    # Clamp — less aggressive, allow more terrain variation
    return np.clip(elev, 0.0, 1.0).astype(np.float32)


# ================================================================
# 2. MOUNTAIN RIDGES — Ridged Multifractal + Spine
# ================================================================

def mountain_elevation(wx, wy, spine_points, seed):
    """Add mountain ridge elevation along spine waypoints.

    Uses ridged multifractal noise: (1 - |noise|)^2 creates sharp ridges.
    """
    if not spine_points:
        return np.zeros_like(wx)

    sp = np.array(spine_points, dtype=np.float32)
    min_dist_sq = np.full_like(wx, 1e18, dtype=np.float32)
    for i in range(len(sp)):
        d2 = (wx - sp[i, 0]) ** 2 + (wy - sp[i, 1]) ** 2
        min_dist_sq = np.minimum(min_dist_sq, d2)

    sigma = 250.0
    spine_factor = np.exp(-min_dist_sq / (2.0 * sigma * sigma))

    n1 = _fbm(wx * 0.008, wy * 0.008, 4, seed=seed + 5555)
    ridge = (1.0 - np.abs(n1 * 2.0 - 1.0)) ** 2.0
    return (spine_factor * (0.15 + ridge * 0.25)).astype(np.float32)


# ================================================================
# 3. SINK FILLING — Priority Flood (Barnes et al. 2014)
# ================================================================

def fill_sinks(elevation_grid, keep_lake_depth=0.03):
    """Remove small depressions, keep deep ones as lakes.

    Depressions deeper than keep_lake_depth are preserved as lakes.
    Shallower depressions are filled to allow river flow.
    """
    h, w = elevation_grid.shape
    filled = elevation_grid.copy()
    visited = np.zeros((h, w), dtype=np.bool_)
    heap = []

    # Seed with edge cells
    for r in range(h):
        for c in [0, w - 1]:
            heapq.heappush(heap, (float(filled[r, c]), r, c))
            visited[r, c] = True
    for c in range(1, w - 1):
        for r in [0, h - 1]:
            heapq.heappush(heap, (float(filled[r, c]), r, c))
            visited[r, c] = True

    nbrs = [(-1, 0), (1, 0), (0, -1), (0, 1),
            (-1, -1), (-1, 1), (1, -1), (1, 1)]
    while heap:
        elev, r, c = heapq.heappop(heap)
        for dr, dc in nbrs:
            nr, nc = r + dr, c + dc
            if 0 <= nr < h and 0 <= nc < w and not visited[nr, nc]:
                visited[nr, nc] = True
                orig = float(elevation_grid[nr, nc])
                if orig < elev:
                    # Only fill if the depression is shallow
                    depth = elev - orig
                    if depth < keep_lake_depth:
                        filled[nr, nc] = elev  # fill shallow sink
                    # else: keep as lake (don't raise)
                heapq.heappush(heap, (float(filled[nr, nc]), nr, nc))
    return filled


# ================================================================
# 4. FLOW ACCUMULATION RIVERS (delegated to river_gen module)
# ================================================================

from game.world.river_gen import (  # noqa: E402
    compute_flow_dir as _compute_flow_dir,
    compute_flow_accum as _compute_flow_accum,
    compute_rivers,
    compute_lakes,
)


# ================================================================
# 5. WHITTAKER BIOME ASSIGNMENT
# ================================================================

_BIOME_TABLE = np.array([
    # Rows: temp (hot..frozen), Cols: moisture (arid..very_wet)
    [DUNE, SAND, GRASS, JUNGLE, JUNGLE],               # Hot
    [SAND, GRASS, FOREST, FOREST, DENSE_FOREST],       # Warm
    [ROCKY_GROUND, GRASS, FOREST, DENSE_FOREST, SWAMP],  # Temperate
    [MOUNTAIN, TUNDRA, MOUNTAIN, MOUNTAIN, SNOW],      # Cold
    [SNOW, SNOW, SNOW, SNOW, SNOW],                    # Frozen
], dtype=np.int8).ravel()

_TEMP_BREAKS = np.array([0.70, 0.50, 0.30, 0.15], dtype=np.float32)
_MOIST_BREAKS = np.array([0.20, 0.35, 0.50, 0.70], dtype=np.float32)


def whittaker_biome(elevation, moisture, base_temp=0.85, lapse_rate=0.6,
                    temp_modifier=None):
    """Assign biome from elevation + moisture using Whittaker diagram.

    Lapse rate controls how quickly temperature drops with altitude.
    0.6 means only peaks above ~0.7 elevation become cold/frozen.

    temp_modifier: optional numpy array of per-tile temperature adjustments
    from regional climate zones.
    """
    temperature = base_temp - elevation * lapse_rate
    if temp_modifier is not None:
        temperature = temperature + temp_modifier
    t_idx = np.clip(np.digitize(temperature, _TEMP_BREAKS), 0, 4).astype(np.int8)
    m_idx = np.clip(np.digitize(moisture, _MOIST_BREAKS), 0, 4).astype(np.int8)
    return _BIOME_TABLE[t_idx * 5 + m_idx]


def compute_moisture(wx, wy, elevation, seed, world_w, world_h):
    """Compute moisture with noise + rain shadow from western mountains."""
    base_moist = _fbm(wx * 0.018, wy * 0.018, 4, seed=seed + 7919)
    west_elev = _fbm((wx - 80.0) * 0.012, wy * 0.012, 3, seed=seed)
    shadow = np.maximum(0.0, 1.0 - west_elev * 0.7)
    moisture = base_moist * shadow
    moisture += np.maximum(0.0, 0.3 - elevation) * 0.5
    return np.clip(moisture, 0.0, 1.0).astype(np.float32)


# ================================================================
# 6. MOUNTAIN SPINE GENERATOR
# ================================================================

def generate_spine(world_w, world_h, seed, n_arms=0):
    """Generate mountain spine waypoints — rift arms radiating from center."""
    rng = random.Random(seed + 9999)
    if n_arms == 0:
        n_arms = rng.randint(3, 4)

    cx, cy = world_w / 2.0, world_h / 2.0
    waypoints = [(cx, cy)]
    base_ang = rng.uniform(0, 2 * math.pi)
    arm_angles = [base_ang + i * (2 * math.pi / n_arms)
                  + rng.uniform(-0.26, 0.26) for i in range(n_arms)]

    for arm_angle in arm_angles:
        x, y = cx, cy
        angle = arm_angle
        step = rng.uniform(50, 80)
        steps = int(min(world_w, world_h) * 0.38 / step)
        for s in range(steps):
            angle += rng.uniform(-0.15, 0.15)
            x += math.cos(angle) * step
            y += math.sin(angle) * step
            x = max(100, min(world_w - 100, x))
            y = max(100, min(world_h - 100, y))
            waypoints.append((x, y))
            # Branch with 20% probability
            if rng.random() < 0.20 and s > 1:
                ba = angle + rng.uniform(-1.0, 1.0)
                bx, by = x, y
                for _ in range(rng.randint(3, 7)):
                    ba += rng.uniform(-0.2, 0.2)
                    bx += math.cos(ba) * step * 0.8
                    by += math.sin(ba) * step * 0.8
                    bx = max(100, min(world_w - 100, bx))
                    by = max(100, min(world_h - 100, by))
                    waypoints.append((bx, by))
    return waypoints


# ================================================================
# 7. COMBINED TERRAIN FOR CHUNK GENERATOR
# ================================================================

def generate_terrain_new(chunk_tiles, plan, x0, y0, chunk_size):
    """Generate terrain for a single chunk using the new volcanic system.

    Drop-in replacement for the old _generate_terrain.
    Includes regional climate zones, volcanic effects, and mini-islands.
    """
    w, h, seed = plan.width, plan.height, plan.seed

    lx = np.arange(chunk_size, dtype=np.float32)
    ly = np.arange(chunk_size, dtype=np.float32)
    lxx, lyy = np.meshgrid(lx, ly)
    wx, wy = lxx + x0, lyy + y0

    elev = island_elevation(wx, wy, w, h, seed)

    # Add mini-island elevation bumps
    mini_islands = getattr(plan, '_mini_islands', None)
    if mini_islands:
        elev = add_mini_island_elevation(wx, wy, elev, mini_islands)

    spine = getattr(plan, '_mountain_spine', None)
    if spine:
        elev = np.clip(elev + mountain_elevation(wx, wy, spine, seed), 0.0, 1.0)

    moisture = compute_moisture(wx, wy, elev, seed, w, h)

    # Apply regional climate (sector-based moisture/temp modifiers)
    moisture, temp_mod = apply_regional_climate(
        wx, wy, moisture, elev, w, h, seed)

    result = whittaker_biome(elev, moisture, temp_modifier=temp_mod)

    # Volcanic effects near central peak
    scorched, hotspring = compute_volcanic_tiles(wx, wy, elev, seed, w, h)
    result[scorched] = SCORCHED_EARTH
    result[hotspring] = HOT_SPRING

    # Water / sand override at low elevation
    result[elev < 0.22] = WATER
    result[(elev >= 0.22) & (elev < 0.28)] = SAND
    result[wy >= h] = WATER
    result[wx >= w] = WATER

    chunk_tiles[:] = result
