"""
Geological terrain system — realistic terrain with subsurface layers.

Generates multi-layered terrain with:
- Height map: elevation using multi-octave fractal noise
- Moisture map: independent noise + rainfall from mountains + river accumulation
- Rock type map: granite, limestone, sandstone, clay — determines mining yields
- Aquifer map: underground water reserves — determines well viability
- Soil fertility: determines farming quality
- Mineral deposits: ore veins, gem deposits — placed by geology

Rivers follow gradient descent from mountains, carving valleys and
depositing sediment. Settlements are placed at locations with high
suitability scores based on water access, farmland, resources, and
defensibility.

Inspired by the landscape-generator project's fractal noise approach
and enhanced with geological realism.
"""

import numpy as np
import random as pyrandom
import math
from typing import Dict, List, Tuple, Optional

from game.settings import (WATER, SAND, GRASS, FOREST, DENSE_FOREST, MOUNTAIN,
                           SNOW, SWAMP, SHALLOW_WATER, ROCKY_GROUND, MARSH,
                           FARMLAND, WELL)


# ================================================================
# NOISE GENERATION — multi-octave fractal noise
# ================================================================

def fbm_noise(width: int, height: int, seed: int, octaves: int = 6,
              persistence: float = 0.5, lacunarity: float = 2.0,
              scale: float = 0.018) -> np.ndarray:
    """Generate fractal Brownian motion noise.
    Uses hash-based value noise with smooth interpolation.
    Returns normalized [0, 1] array of shape (height, width).
    """
    xs = np.arange(width, dtype=np.float64) * scale
    ys = np.arange(height, dtype=np.float64) * scale
    xx, yy = np.meshgrid(xs, ys)

    total = np.zeros((height, width), dtype=np.float64)
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0

    for i in range(octaves):
        # Rotated coordinates for more natural patterns
        angle = (seed + i * 37) * 0.618  # golden ratio spacing
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        rx = xx * frequency * cos_a - yy * frequency * sin_a
        ry = xx * frequency * sin_a + yy * frequency * cos_a

        ix = np.floor(rx).astype(np.int64)
        iy = np.floor(ry).astype(np.int64)
        fx = rx - ix
        fy = ry - iy
        # Smoothstep interpolation
        fx = fx * fx * (3.0 - 2.0 * fx)
        fy = fy * fy * (3.0 - 2.0 * fy)

        def h(xi, yi):
            n = xi * np.int64(374761393) + yi * np.int64(668265263) + np.int64(seed + i * 31) * np.int64(1274126177)
            n = (n ^ (n >> np.int64(13))) * np.int64(1274126177)
            n = n ^ (n >> np.int64(16))
            return (n & np.int64(0x7FFFFFFF)).astype(np.float64) / np.float64(0x7FFFFFFF)

        v00 = h(ix, iy)
        v10 = h(ix + 1, iy)
        v01 = h(ix, iy + 1)
        v11 = h(ix + 1, iy + 1)
        v = (v00 * (1-fx) + v10 * fx) * (1-fy) + (v01 * (1-fx) + v11 * fx) * fy

        total += v * amplitude
        max_val += amplitude
        amplitude *= persistence
        frequency *= lacunarity

    result = total / max_val
    result = (result - result.min()) / (result.max() - result.min() + 1e-10)
    return result


# ================================================================
# GEOLOGICAL LAYERS
# ================================================================

class GeologyMap:
    """Multi-layer geological map of the world.

    Layers:
    - elevation: surface height [0, 1]
    - moisture: surface moisture [0, 1]
    - rock_type: 0=clay, 1=sandstone, 2=limestone, 3=granite, 4=volcanic
    - aquifer: underground water saturation [0, 1]
    - soil_fertility: farming quality [0, 1]
    - mineral_richness: ore/gem potential [0, 1]
    """

    def __init__(self, width: int, height: int, seed: int):
        self.width = width
        self.height = height
        self.seed = seed

        # Generate all layers
        self.elevation = self._gen_elevation(seed)
        self.moisture = self._gen_moisture(seed + 7919)
        self.rock_type = self._gen_rock_type(seed + 4217)
        self.aquifer = self._gen_aquifer()
        self.soil_fertility = self._gen_soil_fertility()
        self.mineral_richness = self._gen_mineral_richness(seed + 8831)

        # Simulate rivers (modifies elevation and moisture)
        self.river_map = np.zeros((height, width), dtype=np.float32)
        self._simulate_rivers(seed)

        # Update moisture from rivers
        self.moisture = np.clip(self.moisture + self.river_map * 0.3, 0, 1)

    def _gen_elevation(self, seed: int) -> np.ndarray:
        """Generate elevation with island falloff."""
        elev = fbm_noise(self.width, self.height, seed,
                        octaves=6, scale=0.018)

        # Island shape: circular falloff from center (gentler for more land)
        xs = np.linspace(-1, 1, self.width)
        ys = np.linspace(-1, 1, self.height)
        xx, yy = np.meshgrid(xs, ys)
        dist = np.sqrt(xx*xx + yy*yy)
        falloff = np.clip(1.0 - dist * 0.55, 0, 1)  # gentler falloff
        falloff = np.power(falloff, 0.8)  # flatten the center plateau

        # Apply falloff
        elev = elev * falloff

        # Add mountain ridges using a second noise layer
        ridges = fbm_noise(self.width, self.height, seed + 3331,
                          octaves=4, scale=0.025, persistence=0.6)
        ridges = np.power(ridges, 1.5)  # sharpen ridges

        # Blend: base terrain + ridges
        elev = elev * 0.5 + ridges * 0.5 * falloff

        # Stretch elevation range to ensure full spectrum
        # Normalize to [0, 1] then rescale so peaks reach mountains
        elev = (elev - elev.min()) / (elev.max() - elev.min() + 1e-10)
        elev = elev * falloff  # re-apply island shape
        # Power curve: raise lowlands, keep peaks
        elev = np.power(elev, 0.7)

        return elev

    def _gen_moisture(self, seed: int) -> np.ndarray:
        """Generate moisture. Higher near coasts, lower in rain shadows."""
        base = fbm_noise(self.width, self.height, seed,
                        octaves=4, scale=0.025)

        # Orographic effect: mountains block moisture
        # Moisture comes from the west (prevailing winds)
        rain_shadow = np.zeros_like(base)
        for y in range(self.height):
            shadow = 0.0
            for x in range(self.width):
                if self.elevation[y, x] > 0.65:
                    shadow = min(1.0, shadow + 0.03)  # mountain blocks moisture
                else:
                    shadow *= 0.98  # shadow fades
                rain_shadow[y, x] = shadow

        # Coastal moisture boost
        water_mask = (self.elevation < 0.22).astype(np.float32)
        from scipy.ndimage import uniform_filter
        coastal_moisture = uniform_filter(water_mask, size=20)

        moisture = base * 0.5 + coastal_moisture * 0.4 - rain_shadow * 0.3
        return np.clip(moisture, 0, 1)

    def _gen_rock_type(self, seed: int) -> np.ndarray:
        """Generate rock types based on elevation and noise.
        0=clay (lowlands), 1=sandstone (dry areas), 2=limestone (mid),
        3=granite (mountains), 4=volcanic (peaks).
        """
        noise = fbm_noise(self.width, self.height, seed,
                         octaves=3, scale=0.03)

        rock = np.zeros((self.height, self.width), dtype=np.int8)
        rock[self.elevation < 0.30] = 0  # clay in lowlands
        rock[(self.elevation >= 0.30) & (self.elevation < 0.50)] = 1  # sandstone
        rock[(self.elevation >= 0.50) & (self.elevation < 0.65)] = 2  # limestone
        rock[self.elevation >= 0.65] = 3  # granite in mountains

        # Volcanic patches near highest peaks
        rock[(self.elevation >= 0.80) & (noise > 0.7)] = 4

        return rock

    def _gen_aquifer(self) -> np.ndarray:
        """Generate underground water saturation.
        Water collects in valleys, under clay, near rivers.
        """
        # Base: inverse of elevation (water flows downhill)
        aquifer = 1.0 - self.elevation

        # Clay holds water better than granite
        clay_bonus = (self.rock_type == 0).astype(np.float32) * 0.2
        limestone_bonus = (self.rock_type == 2).astype(np.float32) * 0.15

        aquifer = aquifer * 0.6 + self.moisture * 0.3 + clay_bonus + limestone_bonus

        # Smooth to create realistic aquifer zones
        try:
            from scipy.ndimage import gaussian_filter
            aquifer = gaussian_filter(aquifer, sigma=5)
        except ImportError:
            pass

        return np.clip(aquifer, 0, 1)

    def _gen_soil_fertility(self) -> np.ndarray:
        """Generate soil fertility. Best in flat, moist areas with good soil."""
        # Flat areas (low slope) are more fertile
        gy, gx = np.gradient(self.elevation)
        slope = np.sqrt(gx*gx + gy*gy)
        flatness = 1.0 - np.clip(slope * 20, 0, 1)

        # Clay and alluvial soils are most fertile
        clay_bonus = (self.rock_type == 0).astype(np.float32) * 0.3

        fertility = flatness * 0.4 + self.moisture * 0.3 + clay_bonus
        # Mountains and water are infertile
        fertility[self.elevation > 0.65] = 0
        fertility[self.elevation < 0.22] = 0

        return np.clip(fertility, 0, 1)

    def _gen_mineral_richness(self, seed: int) -> np.ndarray:
        """Generate mineral deposits. Rich in mountains and volcanic areas."""
        noise = fbm_noise(self.width, self.height, seed,
                         octaves=3, scale=0.04, persistence=0.6)

        minerals = np.zeros((self.height, self.width), dtype=np.float32)

        # Granite mountains have base minerals
        minerals[(self.rock_type == 3)] = 0.3

        # Volcanic areas are richest (ore, gems)
        minerals[(self.rock_type == 4)] = 0.6

        # Random veins in limestone
        minerals[(self.rock_type == 2) & (noise > 0.7)] = 0.4

        # Modulate by noise for natural vein patterns
        minerals *= (0.5 + noise * 0.5)

        return np.clip(minerals, 0, 1)

    def _simulate_rivers(self, seed: int):
        """Simulate rivers using gradient descent from high points.
        Rivers follow the steepest downhill path, accumulating flow.
        """
        rng = pyrandom.Random(seed)
        num_rivers = max(3, (self.width * self.height) // 40000)

        # Find mountain sources
        sources = []
        for _ in range(num_rivers * 5):
            x = rng.randint(20, self.width - 20)
            y = rng.randint(20, self.height - 20)
            if self.elevation[y, x] > 0.60:
                sources.append((x, y, self.elevation[y, x]))

        sources.sort(key=lambda s: -s[2])  # highest first
        sources = sources[:num_rivers]

        for sx, sy, _ in sources:
            self._trace_river_gradient(sx, sy)

    def _trace_river_gradient(self, start_x: int, start_y: int):
        """Trace a river following steepest gradient descent."""
        x, y = start_x, start_y
        visited = set()
        flow = 0.1

        for _ in range(max(self.width, self.height)):
            if (x, y) in visited:
                break
            visited.add((x, y))

            # Reached water or edge
            if self.elevation[y, x] < 0.22 or not (2 <= x < self.width-2 and 2 <= y < self.height-2):
                break

            # Mark as river
            self.river_map[y, x] = min(1.0, flow)
            flow += 0.05  # flow accumulates

            # Find steepest descent among 8 neighbors
            best_dx, best_dy = 0, 1  # default: flow south
            best_slope = 0.0
            current_h = self.elevation[y, x]

            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if not (0 <= nx < self.width and 0 <= ny < self.height):
                        continue
                    slope = current_h - self.elevation[ny, nx]
                    if slope > best_slope:
                        best_slope = slope
                        best_dx, best_dy = dx, dy

            # If no downhill neighbor, stop (lake)
            if best_slope <= 0:
                # Create a small lake
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.width and 0 <= ny < self.height:
                            self.river_map[ny, nx] = min(1.0, flow)
                break

            x += best_dx
            y += best_dy

    # ================================================================
    # SETTLEMENT SUITABILITY SCORING
    # ================================================================

    def calc_settlement_suitability(self, x: int, y: int, radius: int = 8) -> float:
        """Score how suitable a location is for a settlement.

        Factors:
        - Water access (rivers, coast, aquifer for wells)
        - Soil fertility (food production)
        - Mineral access (economic potential)
        - Flatness (buildable terrain)
        - Not underwater or on mountains
        - Defensibility (nearby hills for walls)

        Returns 0-1 suitability score.
        """
        if not (radius <= x < self.width - radius and radius <= y < self.height - radius):
            return 0

        # Must be on buildable land
        h = self.elevation[y, x]
        if h < 0.25 or h > 0.65:
            return 0

        # Sample the neighborhood
        area = np.s_[max(0,y-radius):min(self.height,y+radius),
                     max(0,x-radius):min(self.width,x+radius)]

        # Water access (nearby rivers or coast)
        water_nearby = np.sum(self.river_map[area] > 0.1) + \
                       np.sum(self.elevation[area] < 0.22)
        water_score = min(1.0, water_nearby / 10.0)

        # Aquifer (well viability)
        aquifer_score = float(np.mean(self.aquifer[area]))

        # Soil fertility
        fertility_score = float(np.mean(self.soil_fertility[area]))

        # Mineral access (within larger radius)
        big_area = np.s_[max(0,y-radius*2):min(self.height,y+radius*2),
                         max(0,x-radius*2):min(self.width,x+radius*2)]
        mineral_score = float(np.mean(self.mineral_richness[big_area]))

        # Flatness
        local_elev = self.elevation[area]
        slope = float(np.std(local_elev))
        flatness_score = max(0, 1.0 - slope * 15)

        # Defensibility (nearby higher ground)
        max_nearby = float(np.max(self.elevation[area]))
        defense_score = min(1.0, (max_nearby - h) * 5) if max_nearby > h else 0

        # Weighted sum
        score = (water_score * 0.30 +      # water is most important
                aquifer_score * 0.15 +      # wells
                fertility_score * 0.25 +    # food
                mineral_score * 0.05 +      # resources
                flatness_score * 0.15 +     # buildable
                defense_score * 0.10)       # safety

        return float(np.clip(score, 0, 1))

    def find_best_settlement_locations(self, count: int = 20,
                                       min_distance: int = 40) -> List[Tuple[int, int, float]]:
        """Find the best locations for settlements.
        Returns list of (x, y, suitability_score) sorted by score.
        """
        candidates = []
        step = max(5, min(self.width, self.height) // 50)

        for y in range(20, self.height - 20, step):
            for x in range(20, self.width - 20, step):
                score = self.calc_settlement_suitability(x, y)
                if score > 0.3:
                    candidates.append((x, y, score))

        # Sort by score descending
        candidates.sort(key=lambda c: -c[2])

        # Filter for minimum distance
        selected = []
        for x, y, score in candidates:
            if len(selected) >= count:
                break
            too_close = any(
                math.sqrt((x - sx)**2 + (y - sy)**2) < min_distance
                for sx, sy, _ in selected
            )
            if not too_close:
                selected.append((x, y, score))

        return selected

    def get_well_viability(self, x: int, y: int) -> float:
        """How viable is a well at this location? Based on aquifer depth."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return 0
        return float(self.aquifer[y, x])

    def get_mining_potential(self, x: int, y: int) -> Dict[str, float]:
        """What can be mined at this location?"""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return {}

        richness = self.mineral_richness[y, x]
        rock = self.rock_type[y, x]

        yields = {}
        if richness < 0.1:
            return {"stone": 1.0}

        # Rock type determines what you find
        if rock == 0:  # clay
            yields = {"clay": 1.0, "stone": 0.5}
        elif rock == 1:  # sandstone
            yields = {"stone": 1.0, "sand": 0.8}
        elif rock == 2:  # limestone
            yields = {"stone": 1.0, "iron_ore": richness * 0.5,
                      "copper": richness * 0.3}
        elif rock == 3:  # granite
            yields = {"stone": 1.0, "iron_ore": richness,
                      "gold": richness * 0.2, "gems": richness * 0.1}
        elif rock == 4:  # volcanic
            yields = {"stone": 0.5, "iron_ore": richness * 0.8,
                      "gold": richness * 0.4, "gems": richness * 0.3,
                      "obsidian": 0.5}

        return yields

    def get_farming_quality(self, x: int, y: int) -> float:
        """How good is the soil for farming here?"""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return 0
        return float(self.soil_fertility[y, x])

    def apply_to_tiles(self, tiles: list):
        """Apply geological data to the tile map, enhancing biome placement."""
        h = self.height
        w = self.width

        for y in range(h):
            for x in range(w):
                elev = self.elevation[y, x]
                moist = self.moisture[y, x]
                river = self.river_map[y, x]

                # Rivers
                if river > 0.2:
                    if river > 0.5:
                        tiles[y][x] = WATER  # wide river
                    else:
                        tiles[y][x] = SHALLOW_WATER  # stream
                    continue

                # Ocean
                if elev < 0.22:
                    tiles[y][x] = WATER
                    continue

                # Beach
                if elev < 0.27:
                    tiles[y][x] = SAND
                    continue

                # Mountains and snow
                if elev >= 0.78:
                    tiles[y][x] = SNOW
                    continue
                if elev >= 0.65:
                    if self.rock_type[y, x] == 4:
                        tiles[y][x] = ROCKY_GROUND  # volcanic
                    else:
                        tiles[y][x] = MOUNTAIN
                    continue

                # Mid-elevation biomes
                if moist < 0.25:
                    tiles[y][x] = SAND if elev < 0.40 else ROCKY_GROUND
                elif moist < 0.40:
                    tiles[y][x] = GRASS
                elif moist < 0.55:
                    if self.soil_fertility[y, x] > 0.5:
                        tiles[y][x] = FARMLAND  # naturally fertile
                    else:
                        tiles[y][x] = GRASS
                elif moist < 0.70:
                    tiles[y][x] = FOREST
                elif moist < 0.85:
                    tiles[y][x] = DENSE_FOREST
                else:
                    if elev < 0.35:
                        tiles[y][x] = SWAMP
                    else:
                        tiles[y][x] = MARSH
