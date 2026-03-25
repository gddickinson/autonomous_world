"""Regional climate zones — sector-based moisture/temperature modifiers.

Divides the island into angular sectors from the center, each with
distinct climate characteristics:
  - Desert sector: reduced moisture, arid terrain
  - Tundra sector: temperature penalty, cold highlands
  - Tropical sector: moisture + temperature boost, jungle/swamp
  - Volcanic sector: near center peak, scorched earth + hot springs

Also generates mini-island positions for satellite islands in the ocean.
"""

import math
import random
import numpy as np
from typing import List, Tuple


# ================================================================
# SECTOR DEFINITIONS
# ================================================================

# Each sector: (name, relative_angle_offset, angular_width_radians,
#               moisture_modifier, temperature_modifier)
# Angle 0 = east, pi/2 = south, pi = west, -pi/2 = north

SECTOR_DEFS = [
    ("desert",   0.0,          1.2,  -0.40,  0.0),
    ("tundra",   -1.57,        1.0,   0.0,  -0.15),
    ("tropical",  1.57,        1.2,   0.15,  0.10),
    ("temperate", 3.14,        1.2,   0.0,   0.0),
]


def _generate_sector_angles(seed: int):
    """Generate randomized sector angles from a seed.

    Returns list of (name, center_angle, half_width, moisture_mod, temp_mod).
    The base rotation is randomized so each world has different orientation.
    """
    rng = random.Random(seed + 55555)
    base_rotation = rng.uniform(0, 2 * math.pi)

    sectors = []
    for name, offset, width, moist_mod, temp_mod in SECTOR_DEFS:
        center = base_rotation + offset
        # Normalize to [-pi, pi]
        center = math.atan2(math.sin(center), math.cos(center))
        sectors.append((name, center, width / 2.0, moist_mod, temp_mod))
    return sectors


def _angle_distance(a1, a2):
    """Shortest angular distance between two angles (vectorized)."""
    diff = a1 - a2
    return np.abs(np.arctan2(np.sin(diff), np.cos(diff)))


def apply_regional_climate(wx, wy, moisture, elevation,
                           world_w, world_h, seed):
    """Apply sector-based climate modifiers to moisture and temperature.

    Args:
        wx, wy: world coordinates (numpy arrays)
        moisture: base moisture values (numpy array, modified in-place)
        elevation: elevation values (numpy array)
        world_w, world_h: world dimensions
        seed: world seed

    Returns:
        (moisture, temp_modifier) — modified moisture array and
        temperature modifier array to pass to whittaker_biome.
    """
    cx = world_w / 2.0
    cy = world_h / 2.0
    dx = wx - cx
    dy = wy - cy

    theta = np.arctan2(dy, dx)
    dist_from_center = np.sqrt(dx * dx + dy * dy)
    max_dist = math.sqrt(cx * cx + cy * cy)
    norm_dist = dist_from_center / max_dist

    sectors = _generate_sector_angles(seed)
    temp_mod = np.zeros_like(moisture)

    for name, center_ang, half_width, moist_delta, temp_delta in sectors:
        # Smooth sector influence: full at center, fades at edges
        ang_dist = _angle_distance(theta, center_ang)
        # Influence: 1.0 at center of sector, 0.0 at edge
        influence = np.maximum(0.0, 1.0 - ang_dist / half_width)
        # Smooth with squared falloff for gradual blending
        influence = influence ** 2

        # Sectors are stronger away from island center (more distinct at coast)
        radial_factor = np.clip(norm_dist * 2.0, 0.3, 1.0)
        influence *= radial_factor

        moisture += influence * moist_delta
        temp_mod += influence * temp_delta

    moisture = np.clip(moisture, 0.0, 1.0).astype(np.float32)
    return moisture, temp_mod


# ================================================================
# VOLCANIC EFFECTS — near center peak
# ================================================================

def compute_volcanic_tiles(wx, wy, elevation, seed, world_w, world_h):
    """Determine which tiles should be volcanic (scorched / hot spring).

    Returns:
        (scorched_mask, hotspring_mask) — boolean numpy arrays
    """
    from game.world.terrain_gen import _fbm

    cx = world_w / 2.0
    cy = world_h / 2.0
    dist = np.sqrt((wx - cx) ** 2 + (wy - cy) ** 2)
    max_r = min(world_w, world_h) * 0.12  # volcanic zone radius

    # Only near center and at high elevation
    zone_mask = (dist < max_r) & (elevation > 0.55)

    # Noise for variety — not every tile in zone is volcanic
    vol_noise = _fbm(wx * 0.03, wy * 0.03, 3, seed=seed + 66666)

    scorched = zone_mask & (vol_noise > 0.65)
    hotspring = zone_mask & (vol_noise > 0.55) & (vol_noise <= 0.65) & \
                (elevation < 0.70)

    return scorched, hotspring


# ================================================================
# MINI-ISLAND GENERATION
# ================================================================

def generate_mini_islands(world_w, world_h, seed, n_islands=3):
    """Generate positions and radii for satellite islands.

    Places small islands in the ocean around the main island.
    Each island has: (center_x, center_y, radius, peak_elevation).

    Returns:
        List of (cx, cy, radius, peak_elev) tuples.
    """
    rng = random.Random(seed + 77777)
    islands = []

    # Main island is roughly centered; place mini-islands at edges
    margin = 300  # stay this far from world edges
    center_x = world_w / 2.0
    center_y = world_h / 2.0
    # Main island extends roughly 40% from center
    main_radius = min(world_w, world_h) * 0.35

    for _ in range(n_islands * 3):  # try multiple times to place
        if len(islands) >= n_islands:
            break

        # Random angle, distance just outside main island
        angle = rng.uniform(0, 2 * math.pi)
        dist = main_radius + rng.uniform(
            min(world_w, world_h) * 0.08,
            min(world_w, world_h) * 0.18)

        ix = center_x + math.cos(angle) * dist
        iy = center_y + math.sin(angle) * dist

        # Check within world bounds with margin
        if ix < margin or ix > world_w - margin:
            continue
        if iy < margin or iy > world_h - margin:
            continue

        # Check not too close to other mini-islands
        too_close = False
        for ox, oy, _or, _oe in islands:
            if math.sqrt((ix - ox) ** 2 + (iy - oy) ** 2) < 800:
                too_close = True
                break
        if too_close:
            continue

        radius = rng.randint(200, 500)
        peak_elev = rng.uniform(0.40, 0.50)
        islands.append((int(ix), int(iy), radius, peak_elev))

    return islands


def add_mini_island_elevation(wx, wy, elev, mini_islands):
    """Add mini-island elevation bumps to the elevation array.

    Each mini-island is a smooth circular bump added to existing elevation.

    Args:
        wx, wy: world coordinates (numpy arrays)
        elev: current elevation (numpy array, modified in-place)
        mini_islands: list of (cx, cy, radius, peak_elev)

    Returns:
        Modified elevation array.
    """
    for ix, iy, ir, peak in mini_islands:
        dist = np.sqrt((wx - ix) ** 2 + (wy - iy) ** 2) / ir
        # Smooth bump: peak * (1 - dist^2), clamped to 0
        island_elev = np.maximum(0.0, peak * (1.0 - dist ** 2))
        elev = np.maximum(elev, island_elev)

    return np.clip(elev, 0.0, 1.0).astype(np.float32)


def plan_mini_island_settlements(mini_islands, seed):
    """Generate settlement data for mini-islands.

    Each island gets 1-2 small settlements (hamlet or village).

    Returns:
        List of dicts with settlement placement info:
        {"x": int, "y": int, "kind": str, "name": str, "radius": int}
    """
    rng = random.Random(seed + 88888)
    island_names = [
        "Coral Cay", "Windswept Isle", "Seabird Rock",
        "Tidemark", "Driftwood Point", "Saltspray",
        "Shellhaven", "Stormwatch", "Breaker's Rest",
        "Gull's Landing", "Anchor Bay", "Kelp Shore",
    ]
    rng.shuffle(island_names)
    name_idx = 0

    settlements = []
    for ix, iy, ir, _peak in mini_islands:
        n_settle = rng.randint(1, 2)
        for s in range(n_settle):
            # Place near center but offset
            angle = rng.uniform(0, 2 * math.pi)
            dist = ir * rng.uniform(0.15, 0.40)
            sx = int(ix + math.cos(angle) * dist)
            sy = int(iy + math.sin(angle) * dist)

            kind = "hamlet" if s > 0 else rng.choice(["hamlet", "village"])
            name = island_names[name_idx % len(island_names)]
            name_idx += 1
            radius = 25 if kind == "hamlet" else 35

            settlements.append({
                "x": sx, "y": sy,
                "kind": kind,
                "name": name,
                "radius": radius,
                "specialization": "fishing",
            })

    return settlements
