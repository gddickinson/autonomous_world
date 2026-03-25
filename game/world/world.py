"""Procedural world generation with coherent noise, biomes, villages, and roads."""

import math
import random
from typing import List, Tuple, Optional, Dict
from game.settings import *


def _hash2d(x: int, y: int, seed: int = 0) -> float:
    """Deterministic hash-based pseudo-random for 2D coordinates."""
    n = x * 374761393 + y * 668265263 + seed * 1274126177
    n = (n ^ (n >> 13)) * 1274126177
    n = n ^ (n >> 16)
    return (n & 0x7FFFFFFF) / 0x7FFFFFFF


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _smoothstep(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def value_noise(x: float, y: float, seed: int = 0) -> float:
    """Smooth value noise using bilinear interpolation of hashed grid values."""
    ix, iy = int(math.floor(x)), int(math.floor(y))
    fx, fy = x - ix, y - iy
    fx, fy = _smoothstep(fx), _smoothstep(fy)

    v00 = _hash2d(ix, iy, seed)
    v10 = _hash2d(ix + 1, iy, seed)
    v01 = _hash2d(ix, iy + 1, seed)
    v11 = _hash2d(ix + 1, iy + 1, seed)

    return _lerp(_lerp(v00, v10, fx), _lerp(v01, v11, fx), fy)


def fbm(x: float, y: float, octaves: int = 5, lacunarity: float = 2.0,
        gain: float = 0.5, seed: int = 0) -> float:
    """Fractal Brownian Motion - layered noise for natural terrain."""
    total = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0

    for i in range(octaves):
        total += value_noise(x * frequency, y * frequency, seed + i * 31) * amplitude
        max_val += amplitude
        amplitude *= gain
        frequency *= lacunarity

    return total / max_val


class Structure:
    """A named structure/location in the world."""
    def __init__(self, name: str, kind: str, x: int, y: int, radius: int = 4):
        self.name = name
        self.kind = kind
        self.x = x
        self.y = y
        self.radius = radius
        self.buildings: List[Tuple[int, int, int, int]] = []  # (x, y, w, h)


class World:
    """The game world with procedural terrain, villages, and roads."""

    def __init__(self, width: int = WORLD_WIDTH, height: int = WORLD_HEIGHT, seed: int = None):
        self.width = width
        self.height = height
        self.seed = seed if seed is not None else random.randint(0, 999999)
        self.tiles = [[GRASS] * width for _ in range(height)]
        self.explored = [[False] * width for _ in range(height)]
        self.structures: List[Structure] = []
        self.spawn_point = (width // 2, height // 2)
        self.test_island_spawn = None  # set by _generate_test_island()
        self.test_island_rect = None   # (x, y, w, h) bounding box for exclusion

        self._generate()

    def _generate(self):
        rng = random.Random(self.seed)

        # Generate height and moisture maps
        # Vectorized terrain generation using numpy (10-50x faster)
        import numpy as np

        e_seed = self.seed
        m_seed = self.seed + 7919
        scale = 0.018
        m_scale = 0.025

        # Generate coordinate grids
        xs = np.arange(self.width, dtype=np.float32)
        ys = np.arange(self.height, dtype=np.float32)
        xx, yy = np.meshgrid(xs, ys)

        # Distance from center for island shaping
        cx = (xx / self.width - 0.5) * 2
        cy = (yy / self.height - 0.5) * 2
        edge_falloff = np.maximum(0.0, 1.0 - np.sqrt(cx*cx + cy*cy) * 0.65)

        # Vectorized FBM using hash-based noise
        def fbm_vectorized(x_grid, y_grid, octaves, gain, seed):
            total = np.zeros_like(x_grid)
            amplitude = np.ones_like(x_grid)
            frequency = 1.0
            max_val = np.zeros_like(x_grid)
            for i in range(octaves):
                ix = np.floor(x_grid * frequency).astype(np.int64)
                iy = np.floor(y_grid * frequency).astype(np.int64)
                fx = x_grid * frequency - ix
                fy = y_grid * frequency - iy
                # Smooth interpolation
                fx = fx * fx * (3.0 - 2.0 * fx)
                fy = fy * fy * (3.0 - 2.0 * fy)
                # Hash corners
                def h(xi, yi):
                    n = xi * 374761393 + yi * 668265263 + (seed + i * 31) * 1274126177
                    n = np.int64(n)
                    n = (n ^ (n >> 13)) * np.int64(1274126177)
                    n = n ^ (n >> 16)
                    return (n & np.int64(0x7FFFFFFF)).astype(np.float32) / np.float32(0x7FFFFFFF)
                v00 = h(ix, iy)
                v10 = h(ix + 1, iy)
                v01 = h(ix, iy + 1)
                v11 = h(ix + 1, iy + 1)
                # Bilinear interpolation
                v = (v00 * (1-fx) + v10 * fx) * (1-fy) + (v01 * (1-fx) + v11 * fx) * fy
                total += v * amplitude
                max_val += amplitude
                amplitude *= gain
                frequency *= 2.0
            return total / max_val

        elevation = fbm_vectorized(xx * scale, yy * scale, 6, 0.5, e_seed) * edge_falloff
        moisture = fbm_vectorized(xx * m_scale, yy * m_scale, 4, 0.5, m_seed)

        # Vectorized biome determination
        tiles_np = np.full((self.height, self.width), GRASS, dtype=np.int32)
        tiles_np[elevation < 0.22] = WATER
        tiles_np[(elevation >= 0.22) & (elevation < 0.28)] = SAND
        # Mountains and snow
        tiles_np[(elevation >= 0.65) & (elevation < 0.78)] = MOUNTAIN
        tiles_np[elevation >= 0.78] = SNOW
        # Mid-elevation biomes
        mid = (elevation >= 0.28) & (elevation < 0.65)
        tiles_np[mid & (moisture < 0.30) & (elevation < 0.40)] = SAND
        tiles_np[mid & (moisture < 0.30) & (elevation >= 0.40)] = GRASS
        tiles_np[mid & (moisture >= 0.30) & (moisture < 0.50)] = GRASS
        tiles_np[mid & (moisture >= 0.50) & (moisture < 0.65)] = FOREST
        tiles_np[mid & (moisture >= 0.78) & (elevation < 0.38)] = SWAMP
        tiles_np[mid & (moisture >= 0.65) & ~((moisture >= 0.78) & (elevation < 0.38))] = DENSE_FOREST

        # Store elevation data for terrain-aware movement and cliff placement
        self.elevation = elevation.tolist()

        # Place cliffs near mountains (steep elevation changes) and mountain passes
        self._place_cliffs_and_passes(elevation, tiles_np, rng)
        # tiles are updated inside _place_cliffs_and_passes via tolist()

        # Generate rivers
        self._generate_rivers(rng)

        # Place natural resources (ore veins, herbs, berries, etc.)
        from game.systems.crafting import place_resources_in_world
        place_resources_in_world(self, rng)

        # Carve out the test island BEFORE settlements so it's already ocean/sand
        # and settlements won't try to generate there
        self._generate_test_island()

        # Generate regions and settlements
        self._generate_regions_and_settlements(rng)

        # Place colosseum on test island AFTER all world gen so nothing overwrites it
        if hasattr(self, '_test_colosseum_pos'):
            self._build_test_colosseum(*self._test_colosseum_pos)

        # Build set of building interior tiles (for blocking overworld entry)
        self._building_interior_tiles = set()
        for s in self.structures:
            for bx, by, bw, bh in getattr(s, 'buildings', []):
                for dy in range(bh):
                    for dx in range(bw):
                        tx, ty = bx + dx, by + dy
                        if 0 <= tx < self.width and 0 <= ty < self.height:
                            tile = self.tiles[ty][tx]
                            if tile in (FLOOR, TABLE, BED, CHEST,
                                       STAIRS_UP, STAIRS_DOWN):
                                self._building_interior_tiles.add((tx, ty))

    def _generate_rivers(self, rng: random.Random):
        """Generate rivers flowing from mountains to water/low ground."""
        num_rivers = max(3, (self.width * self.height) // 50000)
        for _ in range(num_rivers):
            # Start from a mountain tile
            for attempt in range(100):
                x = rng.randint(20, self.width - 20)
                y = rng.randint(20, self.height - 20)
                if self.tiles[y][x] == MOUNTAIN:
                    self._trace_river(x, y, rng)
                    break

    def _trace_river(self, start_x: int, start_y: int, rng: random.Random):
        """Trace a river from start point downhill toward water or edge."""
        x, y = start_x, start_y
        length = 0
        max_length = max(self.width, self.height) // 2
        visited = set()

        while length < max_length:
            if (x, y) in visited:
                break
            visited.add((x, y))

            if self.tiles[y][x] == WATER:
                break

            if self.tiles[y][x] not in (WALL, MOUNTAIN):
                self.tiles[y][x] = WATER

            # Flow generally downward/toward center with randomness
            dx = rng.choice([-1, 0, 0, 1])
            dy = rng.choice([0, 0, 1, 1])  # bias downward
            # Add tendency toward lower elevation (center of map)
            if x > self.width // 2:
                dx -= 1 if rng.random() < 0.3 else 0
            elif x < self.width // 2:
                dx += 1 if rng.random() < 0.3 else 0

            x = max(1, min(self.width - 2, x + dx))
            y = max(1, min(self.height - 2, y + dy))
            length += 1

    def _place_cliffs_and_passes(self, elevation, tiles_np, rng: random.Random):
        """Place cliff tiles at steep elevation changes and mountain passes at gaps.

        Cliffs appear where elevation changes sharply near mountains.
        Mountain passes appear at the lowest points in mountain ranges,
        creating traversable gaps.
        """
        import numpy as np

        h, w = elevation.shape

        # Compute elevation gradient magnitude
        grad_y = np.abs(np.diff(elevation, axis=0, prepend=elevation[:1, :]))
        grad_x = np.abs(np.diff(elevation, axis=1, prepend=elevation[:, :1]))
        gradient = np.sqrt(grad_y * grad_y + grad_x * grad_x)

        # Cliffs: steep gradient near mountain/snow elevation
        cliff_mask = (gradient > 0.08) & (elevation >= 0.55) & (elevation < 0.70)
        cliff_positions = np.argwhere(cliff_mask)

        # Only place a fraction of cliffs (too many would be overwhelming)
        if len(cliff_positions) > 0:
            max_cliffs = min(len(cliff_positions), w * h // 8000)
            indices = rng.sample(range(len(cliff_positions)), min(max_cliffs, len(cliff_positions)))
            for idx in indices:
                cy, cx = cliff_positions[idx]
                if tiles_np[cy][cx] == MOUNTAIN:
                    tiles_np[cy][cx] = CLIFF

        # Mountain passes: find lowest elevation points in mountain ranges
        # A pass is a mountain tile with lower elevation than its mountain neighbors
        mountain_mask = (tiles_np == MOUNTAIN)
        pass_candidates = []

        # Sample mountain tiles and check for saddle points
        mountain_positions = np.argwhere(mountain_mask)
        if len(mountain_positions) > 0:
            sample_size = min(len(mountain_positions), 2000)
            sample_indices = rng.sample(range(len(mountain_positions)), sample_size)

            for idx in sample_indices:
                my, mx = mountain_positions[idx]
                if not (2 <= mx < w - 2 and 2 <= my < h - 2):
                    continue

                elev = elevation[my][mx]
                # Check if this is a local minimum among mountain neighbors
                neighbor_elevs = []
                non_mountain_neighbors = 0
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        if dx == 0 and dy == 0:
                            continue
                        ny, nx = my + dy, mx + dx
                        if 0 <= nx < w and 0 <= ny < h:
                            if tiles_np[ny][nx] in (MOUNTAIN, SNOW):
                                neighbor_elevs.append(elevation[ny][nx])
                            else:
                                non_mountain_neighbors += 1

                # A pass needs: mountain neighbors on at least 2 sides,
                # non-mountain on at least 1 side, and lower than most neighbors
                if (len(neighbor_elevs) >= 4 and non_mountain_neighbors >= 2 and
                        elev < sum(neighbor_elevs) / len(neighbor_elevs)):
                    pass_candidates.append((elev, my, mx))

            # Sort by elevation (lowest = best pass) and place passes
            pass_candidates.sort()
            max_passes = max(3, w * h // 100000)
            placed_passes = 0
            placed_pass_positions = []

            for elev, py, px in pass_candidates:
                if placed_passes >= max_passes:
                    break
                # Check distance from other passes
                too_close = False
                for opy, opx in placed_pass_positions:
                    if abs(py - opy) + abs(px - opx) < 30:
                        too_close = True
                        break
                if too_close:
                    continue

                # Place the pass (3x3 area of MOUNTAIN_PASS tiles)
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        ny, nx = py + dy, px + dx
                        if 0 <= nx < w and 0 <= ny < h:
                            if tiles_np[ny][nx] == MOUNTAIN:
                                tiles_np[ny][nx] = MOUNTAIN_PASS
                placed_passes += 1
                placed_pass_positions.append((py, px))

        # Update self.tiles from the modified numpy array
        self.tiles = tiles_np.tolist()

    def _generate_regions_and_settlements(self, rng: random.Random):
        """Generate world regions with themed settlements using the new building system."""
        from game.world.regions import assign_regions, REGIONS
        from game.world.settlements import generate_settlement

        self.regions = assign_regions(self.width, self.height, rng)

        # Generate settlements for each region
        for region_name, region_info in self.regions.items():
            region_data = region_info["data"]
            rcx, rcy = region_info["center_x"], region_info["center_y"]
            radius = region_info["radius"]
            race = rng.choice(region_data["primary_races"])

            names = list(region_data["settlement_names"])
            rng.shuffle(names)
            name_idx = 0

            # Settlement count based on region
            num = min(region_data["max_settlements"], len(names))
            stypes = region_data["settlement_types"]

            for i in range(num):
                stype = stypes[i % len(stypes)]

                # Find suitable position
                for attempt in range(50):
                    angle = rng.uniform(0, 2 * math.pi)
                    dist = rng.uniform(20, radius * 0.8)
                    sx = int(rcx + math.cos(angle) * dist)
                    sy = int(rcy + math.sin(angle) * dist)
                    sx = max(50, min(self.width - 50, sx))
                    sy = max(50, min(self.height - 50, sy))

                    if self.tiles[sy][sx] in (WATER, MOUNTAIN, SNOW):
                        continue

                    # Check distance from other settlements
                    min_dist = 40 if stype in ("city", "town") else 25
                    too_close = any(
                        math.sqrt((s.x - sx)**2 + (s.y - sy)**2) < min_dist
                        for s in self.structures
                    )
                    if too_close:
                        continue

                    # Prefer locations near water for towns/cities
                    near_water = self.find_water_near(sx, sy, 15)
                    if stype in ("town", "city") and not near_water and rng.random() < 0.5:
                        continue

                    name = names[name_idx] if name_idx < len(names) else f"{region_data['name']} Settlement"
                    name_idx += 1

                    # Generate the settlement using new building system
                    settlement = generate_settlement(
                        name, stype, sx, sy,
                        self.tiles, self.width, self.height,
                        rng, region_name, race
                    )

                    # Create a Structure for backward compatibility
                    struct = Structure(name, stype, sx, sy, radius=settlement.radius)
                    struct.buildings = [(b["x"], b["y"],
                                       b["blueprint"].width, b["blueprint"].height)
                                      for b in settlement.buildings]
                    self.structures.append(struct)

                    # Store NPC spawn data
                    if not hasattr(self, 'npc_spawn_data'):
                        self.npc_spawn_data = []
                    self.npc_spawn_data.extend(settlement.npc_spawns)

                    break

            # Place castles for regions that have them
            for castle_name in region_data.get("castle_names", []):
                for attempt in range(50):
                    angle = rng.uniform(0, 2 * math.pi)
                    dist = rng.uniform(10, radius * 0.5)
                    sx = int(rcx + math.cos(angle) * dist)
                    sy = int(rcy + math.sin(angle) * dist)
                    sx = max(50, min(self.width - 50, sx))
                    sy = max(50, min(self.height - 50, sy))

                    if self.tiles[sy][sx] in (WATER,):
                        continue

                    too_close = any(
                        math.sqrt((s.x - sx)**2 + (s.y - sy)**2) < 30
                        for s in self.structures
                    )
                    if too_close:
                        continue

                    settlement = generate_settlement(
                        castle_name, "city", sx, sy,
                        self.tiles, self.width, self.height,
                        rng, region_name, race
                    )
                    struct = Structure(castle_name, "castle", sx, sy, radius=35)
                    self.structures.append(struct)
                    if not hasattr(self, 'npc_spawn_data'):
                        self.npc_spawn_data = []
                    self.npc_spawn_data.extend(settlement.npc_spawns)
                    break

        # Build roads between settlements
        self._build_roads(rng)

        # Build a spawn temple at the center of the world
        # This guarantees a safe, open spawn point with roads in all directions
        cx, cy = self.width // 2, self.height // 2
        self._build_spawn_temple(cx, cy)
        self.spawn_point = (cx, cy)

        # Place ruins and shrines in wilderness
        self._place_ruins_and_shrines(rng)

    def _build_spawn_temple(self, cx: int, cy: int):
        """Build a grand spawn temple at the world center.
        Open platform with doors on all 4 sides and roads leading outward."""
        r = 6  # temple radius

        # Clear the area
        for dy in range(-r - 4, r + 5):
            for dx in range(-r - 4, r + 5):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    self.tiles[ny][nx] = GRASS

        # Build temple walls (circle)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    dist2 = dx * dx + dy * dy
                    if dist2 <= r * r:
                        if dist2 >= (r - 1) * (r - 1):
                            self.tiles[ny][nx] = WALL  # outer ring = wall
                        else:
                            self.tiles[ny][nx] = FLOOR  # interior = floor

        # Doors on all 4 sides - cut through the ENTIRE wall thickness
        # North door (3 tiles wide)
        for dx_off in [-1, 0, 1]:
            for dy_off in range(-r, -r + 3):  # cut through wall ring
                nx, ny = cx + dx_off, cy + dy_off
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == WALL:
                        self.tiles[ny][nx] = DOOR
        # South door
        for dx_off in [-1, 0, 1]:
            for dy_off in range(r - 2, r + 1):
                nx, ny = cx + dx_off, cy + dy_off
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == WALL:
                        self.tiles[ny][nx] = DOOR
        # East door
        for dy_off in [-1, 0, 1]:
            for dx_off in range(r - 2, r + 1):
                nx, ny = cx + dx_off, cy + dy_off
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == WALL:
                        self.tiles[ny][nx] = DOOR
        # West door
        for dy_off in [-1, 0, 1]:
            for dx_off in range(-r, -r + 3):
                nx, ny = cx + dx_off, cy + dy_off
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == WALL:
                        self.tiles[ny][nx] = DOOR

        # Windows between doors
        for angle_offset in [45, 135, 225, 315]:
            import math as _m
            rad = _m.radians(angle_offset)
            wx = int(cx + _m.cos(rad) * (r - 0.5))
            wy = int(cy + _m.sin(rad) * (r - 0.5))
            if 0 <= wx < self.width and 0 <= wy < self.height:
                self.tiles[wy][wx] = WINDOW

        # Roads leading away from each door
        road_length = 20
        # North
        for dy in range(1, road_length + 1):
            ny = cy - r - dy
            if 0 <= ny < self.height:
                self.tiles[ny][cx] = ROAD
                for d in [-1, 1]:
                    if 0 <= cx + d < self.width:
                        self.tiles[ny][cx + d] = ROAD
        # South
        for dy in range(1, road_length + 1):
            ny = cy + r + dy
            if 0 <= ny < self.height:
                self.tiles[ny][cx] = ROAD
                for d in [-1, 1]:
                    if 0 <= cx + d < self.width:
                        self.tiles[ny][cx + d] = ROAD
        # East
        for dx in range(1, road_length + 1):
            nx = cx + r + dx
            if 0 <= nx < self.width:
                self.tiles[cy][nx] = ROAD
                for d in [-1, 1]:
                    if 0 <= cy + d < self.height:
                        self.tiles[cy + d][nx] = ROAD
        # West
        for dx in range(1, road_length + 1):
            nx = cx - r - dx
            if 0 <= nx < self.width:
                self.tiles[cy][nx] = ROAD
                for d in [-1, 1]:
                    if 0 <= cy + d < self.height:
                        self.tiles[cy + d][nx] = ROAD

        # Add to structures
        temple = Structure("Temple of Awakening", "temple", cx, cy, radius=r)
        self.structures.append(temple)

        # Build a starter village near the temple so players have NPCs to interact with
        from game.world.settlements import generate_settlement
        village_x = cx + 25
        village_y = cy
        # Clear area for village
        for dy in range(-20, 21):
            for dx in range(-20, 21):
                nx, ny = village_x + dx, village_y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] in (WATER, MOUNTAIN):
                        self.tiles[ny][nx] = GRASS
        starter = generate_settlement(
            "Hearthstone", "village", village_x, village_y,
            self.tiles, self.width, self.height,
            random.Random(self.seed + 999), "", "Human"
        )
        struct = Structure("Hearthstone", "village", village_x, village_y, radius=15)
        struct.buildings = [(b["x"], b["y"], b["blueprint"].width, b["blueprint"].height)
                           for b in starter.buildings]
        self.structures.append(struct)
        if not hasattr(self, 'npc_spawn_data'):
            self.npc_spawn_data = []
        self.npc_spawn_data.extend(starter.npc_spawns)

    def _generate_test_island(self):
        """Generate an isolated desert island far from the main continent.

        The island is a flat sand oval with a spawn temple near the western edge.
        No settlements, NPCs, or creatures will spawn here — it's a controlled
        test environment on 'the other side of the planet'.
        """
        # Island parameters — placed in deep ocean far from the main continent.
        # The continent is centered at (width//2, height//2) with edge falloff
        # creating water around the borders. We place the island near the
        # top-right corner where it's guaranteed to be ocean.
        island_w, island_h = 200, 120
        # Center: 92% across in X, 7% down in Y — far corner of the ocean
        ix = int(self.width * 0.92)
        iy = int(self.height * 0.07)

        # Clamp so the island fits within world bounds with a water buffer
        buf = 10
        ix = max(island_w // 2 + buf, min(self.width - island_w // 2 - buf, ix))
        iy = max(island_h // 2 + buf, min(self.height - island_h // 2 - buf, iy))

        # Store bounding rect for exclusion zones (with generous margin)
        margin = 30
        self.test_island_rect = (
            ix - island_w // 2 - margin,
            iy - island_h // 2 - margin,
            island_w + margin * 2,
            island_h + margin * 2,
        )

        # First, ensure the whole area is water (ocean buffer around island)
        for dy in range(-island_h // 2 - 8, island_h // 2 + 9):
            for dx in range(-island_w // 2 - 8, island_w // 2 + 9):
                nx, ny = ix + dx, iy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    self.tiles[ny][nx] = WATER

        # Carve the island as a smooth ellipse of sand
        rx = island_w / 2.0   # semi-axis X
        ry = island_h / 2.0   # semi-axis Y
        for dy in range(-island_h // 2, island_h // 2 + 1):
            for dx in range(-island_w // 2, island_w // 2 + 1):
                # Ellipse test: (dx/rx)^2 + (dy/ry)^2 <= 1
                if (dx / rx) ** 2 + (dy / ry) ** 2 <= 1.0:
                    nx, ny = ix + dx, iy + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        self.tiles[ny][nx] = SAND

        # Thin beach fringe — sand tiles just outside the ellipse are already
        # water, which gives a natural coastline. Add a 1-tile SAND fringe
        # for a softer edge.
        for dy in range(-island_h // 2 - 1, island_h // 2 + 2):
            for dx in range(-island_w // 2 - 1, island_w // 2 + 2):
                e = (dx / rx) ** 2 + (dy / ry) ** 2
                if 1.0 < e <= 1.08:
                    nx, ny = ix + dx, iy + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        self.tiles[ny][nx] = SAND

        # Place spawn temple near the western edge of the island
        temple_x = ix - island_w // 2 + 20  # 20 tiles in from western edge
        temple_y = iy                        # vertically centered
        self._build_spawn_temple_minimal(temple_x, temple_y)

        # Colosseum is placed after all world gen — see end of _generate()
        self._test_colosseum_pos = (ix + 40, iy)

        self.test_island_spawn = (temple_x, temple_y)

    def _build_spawn_temple_minimal(self, cx: int, cy: int):
        """Build a simple spawn temple on the test island.

        Same circular design as the main temple but without the starter village
        or long roads — just the temple with short paths leading onto the sand.
        """
        r = 5  # slightly smaller than main temple

        # Clear immediate area to sand (it already is, but ensure floor contrast)
        for dy in range(-r - 3, r + 4):
            for dx in range(-r - 3, r + 4):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    self.tiles[ny][nx] = SAND

        # Temple walls (circle)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    dist2 = dx * dx + dy * dy
                    if dist2 <= r * r:
                        if dist2 >= (r - 1) * (r - 1):
                            self.tiles[ny][nx] = WALL
                        else:
                            self.tiles[ny][nx] = FLOOR

        # Doors on all 4 sides (3 tiles wide)
        for dx_off in [-1, 0, 1]:
            for dy_off in range(-r, -r + 3):
                nx, ny = cx + dx_off, cy + dy_off
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == WALL:
                        self.tiles[ny][nx] = DOOR
        for dx_off in [-1, 0, 1]:
            for dy_off in range(r - 2, r + 1):
                nx, ny = cx + dx_off, cy + dy_off
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == WALL:
                        self.tiles[ny][nx] = DOOR
        for dy_off in [-1, 0, 1]:
            for dx_off in range(r - 2, r + 1):
                nx, ny = cx + dx_off, cy + dy_off
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == WALL:
                        self.tiles[ny][nx] = DOOR
        for dy_off in [-1, 0, 1]:
            for dx_off in range(-r, -r + 3):
                nx, ny = cx + dx_off, cy + dy_off
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == WALL:
                        self.tiles[ny][nx] = DOOR

        # Short paths (5 tiles) from each door
        for dy in range(1, 6):
            ny = cy - r - dy
            if 0 <= ny < self.height and 0 <= cx < self.width:
                self.tiles[ny][cx] = SAND
        for dy in range(1, 6):
            ny = cy + r + dy
            if 0 <= ny < self.height and 0 <= cx < self.width:
                self.tiles[ny][cx] = SAND
        for dx in range(1, 6):
            nx = cx + r + dx
            if 0 <= nx < self.width and 0 <= cy < self.height:
                self.tiles[cy][nx] = SAND
        for dx in range(1, 6):
            nx = cx - r - dx
            if 0 <= nx < self.width and 0 <= cy < self.height:
                self.tiles[cy][nx] = SAND

        temple = Structure("Temple of Testing", "temple", cx, cy, radius=r)
        self.structures.append(temple)

    def _build_test_colosseum(self, cx: int, cy: int):
        """Stamp the colosseum blueprint onto the test island."""
        from game.world.blueprint_library import ENTERTAINMENT
        from game.world.buildings import stamp_blueprint

        colosseum_bp = ENTERTAINMENT[0]  # The grand Colosseum
        bw, bh = colosseum_bp.width, colosseum_bp.height

        # Clear entire blueprint footprint plus generous surround to sand
        # so no world-gen terrain peeks through the elliptical exterior gaps
        margin = 20
        for dy in range(-bh // 2 - margin, bh // 2 + margin + 1):
            for dx in range(-bw // 2 - margin, bw // 2 + margin + 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    # Force to sand — overwrite everything including resources
                    self.tiles[ny][nx] = SAND

        # Stamp the blueprint
        stamp_x = cx - bw // 2
        stamp_y = cy - bh // 2
        stamp_blueprint(self.tiles, colosseum_bp, stamp_x, stamp_y,
                        self.width, self.height)

        colosseum = Structure("Test Colosseum", "colosseum", cx, cy,
                              radius=max(bw, bh) // 2)
        self.structures.append(colosseum)

    def _place_ruins_and_shrines(self, rng: random.Random):
        """Place ruins and shrines in wilderness areas."""
        max_ruins = max(6, (self.width * self.height) // 15000)
        for _ in range(max_ruins):
            for attempt in range(50):
                x = rng.randint(20, self.width - 20)
                y = rng.randint(20, self.height - 20)
                if self.tiles[y][x] in (WATER, MOUNTAIN, WALL):
                    continue
                # Skip test island area
                if self.test_island_rect:
                    rx, ry, rw, rh = self.test_island_rect
                    if rx <= x <= rx + rw and ry <= y <= ry + rh:
                        continue
                too_close = any(
                    math.sqrt((s.x - x)**2 + (s.y - y)**2) < 20
                    for s in self.structures
                )
                if too_close:
                    continue
                # Build ruin
                name = rng.choice(["Ancient Ruins", "Forgotten Temple", "Crumbling Tower",
                                   "Lost Catacombs", "Shattered Keep", "Buried Sanctum",
                                   "The Dark Catacombs", "Goblin Warren", "Tomb of the Ancients"])
                ruin = Structure(name, "ruins", x, y, radius=5)
                for dy in range(-4, 5):
                    for dx in range(-4, 5):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.width and 0 <= ny < self.height:
                            if dx * dx + dy * dy <= 16:
                                if abs(dx) >= 3 or abs(dy) >= 3:
                                    if rng.random() < 0.5:
                                        self.tiles[ny][nx] = WALL
                                    else:
                                        self.tiles[ny][nx] = FLOOR
                                else:
                                    self.tiles[ny][nx] = FLOOR
                self.structures.append(ruin)
                break

    def _place_structures(self, rng: random.Random):
        """Legacy structure placement - now handled by _generate_regions_and_settlements."""
        village_names = [
            "Millbrook", "Stonehaven", "Ashford", "Thornfield", "Riverwatch",
            "Oakvale", "Ironholt", "Briarwood", "Northmere", "Goldpeak",
            "Duskhollow", "Whitecliff", "Ravensgate", "Fogmere", "Sunridge",
            "Eldergrove", "Frosthaven", "Dawnspire", "Shadowfen", "Copperdale",
            "Silverbend", "Stormwatch", "Willowmere", "Embervale", "Mossgate",
            "Highcross", "Thornwall", "Greymoor", "Nighthaven", "Starfall",
        ]
        rng.shuffle(village_names)

        ruin_names = [
            "Ancient Ruins", "Forgotten Temple", "Crumbling Tower",
            "Lost Catacombs", "Shattered Keep", "Buried Sanctum"
        ]
        rng.shuffle(ruin_names)

        shrine_names = [
            "Moonlit Shrine", "Stone Circle", "Sacred Grove",
            "Spirit Well", "Elder Monument"
        ]
        rng.shuffle(shrine_names)

        # Scale village count with world size
        max_villages = max(8, (self.width * self.height) // 5000)
        vi = 0
        for attempt in range(1000):
            if vi >= max_villages:
                break
            x = rng.randint(30, self.width - 30)
            y = rng.randint(30, self.height - 30)

            if self.tiles[y][x] not in (GRASS, FOREST):
                continue

            # Check distance from other structures
            too_close = any(
                math.sqrt((s.x - x)**2 + (s.y - y)**2) < 35
                for s in self.structures
            )
            if too_close:
                continue

            name = village_names[vi] if vi < len(village_names) else f"Village {vi}"
            village = Structure(name, "village", x, y, radius=6)
            self._build_village(village, rng)
            self.structures.append(village)
            vi += 1

        # Place ruins in remote areas
        max_ruins = max(4, (self.width * self.height) // 10000)
        ri = 0
        for attempt in range(500):
            if ri >= max_ruins:
                break
            x = rng.randint(20, self.width - 20)
            y = rng.randint(20, self.height - 20)

            if self.tiles[y][x] in (WATER, MOUNTAIN, SNOW):
                continue

            too_close = any(
                math.sqrt((s.x - x)**2 + (s.y - y)**2) < 20
                for s in self.structures
            )
            if too_close:
                continue

            name = ruin_names[ri] if ri < len(ruin_names) else f"Ruins {ri}"
            ruin = Structure(name, "ruins", x, y, radius=4)
            self._build_ruin(ruin, rng)
            self.structures.append(ruin)
            ri += 1

        # Place shrines
        max_shrines = max(3, (self.width * self.height) // 15000)
        si = 0
        for attempt in range(300):
            if si >= max_shrines:
                break
            x = rng.randint(15, self.width - 15)
            y = rng.randint(15, self.height - 15)

            if self.tiles[y][x] in (WATER, MOUNTAIN, WALL):
                continue

            too_close = any(
                math.sqrt((s.x - x)**2 + (s.y - y)**2) < 15
                for s in self.structures
            )
            if too_close:
                continue

            name = shrine_names[si] if si < len(shrine_names) else f"Shrine {si}"
            shrine = Structure(name, "shrine", x, y, radius=2)
            # Simple shrine: small floor area
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        self.tiles[ny][nx] = FLOOR
            self.structures.append(shrine)
            si += 1

        # Place castles (2-4, with rulers)
        castle_names = ["Northwatch Keep", "Stormhold Citadel", "Ironthrone Fortress",
                        "Sunspear Castle", "Shadowkeep", "Dragon's Gate"]
        rng.shuffle(castle_names)
        ci = 0
        max_castles = max(2, (self.width * self.height) // 40000)
        for attempt in range(300):
            if ci >= max_castles:
                break
            x = rng.randint(30, self.width - 30)
            y = rng.randint(30, self.height - 30)
            if self.tiles[y][x] in (WATER, SWAMP):
                continue
            too_close = any(
                math.sqrt((s.x - x)**2 + (s.y - y)**2) < 25
                for s in self.structures
            )
            if too_close:
                continue

            name = castle_names[ci] if ci < len(castle_names) else f"Castle {ci}"
            castle = Structure(name, "castle", x, y, radius=8)
            # Build castle structure
            for dy in range(-8, 9):
                for dx in range(-8, 9):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        d2 = dx * dx + dy * dy
                        if d2 <= 64:
                            if abs(dx) >= 7 or abs(dy) >= 7:
                                self.tiles[ny][nx] = WALL
                            else:
                                self.tiles[ny][nx] = FLOOR
            # Castle courtyard road
            for dx in range(-6, 7):
                nx = x + dx
                if 0 <= nx < self.width:
                    self.tiles[y][nx] = ROAD
            self.structures.append(castle)
            ci += 1

        # Place taverns inside/near some villages
        tavern_names = ["The Rusty Dragon", "The Prancing Pony", "The Winking Skeever",
                        "The Gilded Goblet", "The Drunken Dwarf", "The Silver Stag",
                        "The Broken Blade", "The Dancing Dragon", "The Old Owl",
                        "The Copper Kettle", "The Wanderer's Rest", "The Golden Mug"]
        rng.shuffle(tavern_names)
        ti = 0
        for s in self.structures:
            if s.kind != "village" or ti >= len(tavern_names):
                continue
            if rng.random() < 0.6:  # 60% of villages get a tavern
                tx = s.x + rng.randint(-3, 3)
                ty = s.y + rng.randint(-3, 3)
                if 0 <= tx < self.width and 0 <= ty < self.height:
                    tavern = Structure(tavern_names[ti], "tavern", tx, ty, radius=2)
                    self.structures.append(tavern)
                    ti += 1

        # Place temples (3-6)
        temple_names = ["Temple of Light", "Sanctuary of Healing", "Chapel of the Dawn",
                        "Shrine of Wisdom", "Cathedral of Stars", "Abbey of Mercy"]
        rng.shuffle(temple_names)
        tei = 0
        max_temples = max(3, (self.width * self.height) // 30000)
        for attempt in range(200):
            if tei >= max_temples:
                break
            x = rng.randint(20, self.width - 20)
            y = rng.randint(20, self.height - 20)
            if self.tiles[y][x] in (WATER, MOUNTAIN):
                continue
            too_close = any(
                math.sqrt((s.x - x)**2 + (s.y - y)**2) < 12
                for s in self.structures
            )
            if too_close:
                continue
            name = temple_names[tei] if tei < len(temple_names) else f"Temple {tei}"
            temple = Structure(name, "temple", x, y, radius=3)
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        if abs(dx) == 2 or abs(dy) == 2:
                            self.tiles[ny][nx] = WALL
                        else:
                            self.tiles[ny][nx] = FLOOR
            self.structures.append(temple)
            tei += 1

        # Place dungeons (3-8, as larger ruins with more rooms)
        dungeon_names = ["The Dark Catacombs", "Goblin Warren", "Dragon's Lair",
                         "The Sunken Crypt", "Tomb of the Ancients", "The Underdark Gate",
                         "Lair of Shadows", "The Bone Pit"]
        rng.shuffle(dungeon_names)
        di = 0
        max_dungeons = max(3, (self.width * self.height) // 25000)
        for attempt in range(400):
            if di >= max_dungeons:
                break
            x = rng.randint(25, self.width - 25)
            y = rng.randint(25, self.height - 25)
            if self.tiles[y][x] in (WATER,):
                continue
            too_close = any(
                math.sqrt((s.x - x)**2 + (s.y - y)**2) < 20
                for s in self.structures
            )
            if too_close:
                continue
            name = dungeon_names[di] if di < len(dungeon_names) else f"Dungeon {di}"
            dungeon = Structure(name, "dungeon", x, y, radius=8)
            # Generate multi-room dungeon
            rooms = []
            for _ in range(rng.randint(4, 8)):
                rw = rng.randint(3, 6)
                rh = rng.randint(3, 6)
                rx = x + rng.randint(-7, 7 - rw)
                ry = y + rng.randint(-7, 7 - rh)
                rooms.append((rx, ry, rw, rh))
                for dy2 in range(rh):
                    for dx2 in range(rw):
                        nx, ny = rx + dx2, ry + dy2
                        if 0 <= nx < self.width and 0 <= ny < self.height:
                            if dx2 == 0 or dx2 == rw - 1 or dy2 == 0 or dy2 == rh - 1:
                                if self.tiles[ny][nx] != FLOOR:
                                    self.tiles[ny][nx] = WALL
                            else:
                                self.tiles[ny][nx] = FLOOR
            # Connect rooms with corridors
            for i in range(len(rooms) - 1):
                cx1 = rooms[i][0] + rooms[i][2] // 2
                cy1 = rooms[i][1] + rooms[i][3] // 2
                cx2 = rooms[i+1][0] + rooms[i+1][2] // 2
                cy2 = rooms[i+1][1] + rooms[i+1][3] // 2
                # L-shaped corridor
                for xx in range(min(cx1, cx2), max(cx1, cx2) + 1):
                    if 0 <= xx < self.width and 0 <= cy1 < self.height:
                        self.tiles[cy1][xx] = FLOOR
                for yy in range(min(cy1, cy2), max(cy1, cy2) + 1):
                    if 0 <= cx2 < self.width and 0 <= yy < self.height:
                        self.tiles[yy][cx2] = FLOOR
            dungeon.buildings = rooms
            self.structures.append(dungeon)
            di += 1

    def _build_village(self, village: Structure, rng: random.Random):
        """Build a village with buildings and open areas."""
        cx, cy = village.x, village.y
        r = village.radius

        # Clear ground
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if dx * dx + dy * dy <= r * r:
                        self.tiles[ny][nx] = GRASS

        # Place 4-7 buildings
        num_buildings = rng.randint(4, 7)
        for _ in range(num_buildings):
            bw = rng.randint(3, 5)
            bh = rng.randint(3, 5)
            bx = cx + rng.randint(-r + 1, r - bw)
            by = cy + rng.randint(-r + 1, r - bh)

            # Check overlap with other buildings
            overlap = False
            for ox, oy, ow, oh in village.buildings:
                if (bx < ox + ow + 1 and bx + bw + 1 > ox and
                    by < oy + oh + 1 and by + bh + 1 > oy):
                    overlap = True
                    break
            if overlap:
                continue

            # Build the building
            for dy in range(bh):
                for dx in range(bw):
                    nx, ny = bx + dx, by + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        if dx == 0 or dx == bw - 1 or dy == 0 or dy == bh - 1:
                            self.tiles[ny][nx] = WALL
                        else:
                            self.tiles[ny][nx] = FLOOR

            # Add door
            door_side = rng.choice(["n", "s", "e", "w"])
            if door_side == "n":
                dx, dy = bx + bw // 2, by
            elif door_side == "s":
                dx, dy = bx + bw // 2, by + bh - 1
            elif door_side == "e":
                dx, dy = bx + bw - 1, by + bh // 2
            else:
                dx, dy = bx, by + bh // 2
            if 0 <= dx < self.width and 0 <= dy < self.height:
                self.tiles[dy][dx] = FLOOR

            village.buildings.append((bx, by, bw, bh))

            # Place furniture inside buildings
            interior_tiles = []
            for fy in range(by + 1, by + bh - 1):
                for fx in range(bx + 1, bx + bw - 1):
                    if 0 <= fx < self.width and 0 <= fy < self.height:
                        if self.tiles[fy][fx] == FLOOR:
                            interior_tiles.append((fx, fy))

            if interior_tiles and len(interior_tiles) >= 2:
                # Place a table
                tx, ty = interior_tiles[0]
                self.tiles[ty][tx] = TABLE
                # Place a bed if room is big enough
                if len(interior_tiles) >= 3:
                    bx2, by2 = interior_tiles[-1]
                    self.tiles[by2][bx2] = BED
                # Place a chest sometimes
                if len(interior_tiles) >= 4 and rng.random() < 0.4:
                    cx2, cy2 = interior_tiles[len(interior_tiles) // 2]
                    self.tiles[cy2][cx2] = CHEST

        # Village center road/path
        for dx in range(-r, r + 1):
            nx = cx + dx
            if 0 <= nx < self.width:
                if self.tiles[cy][nx] not in (WALL,):
                    self.tiles[cy][nx] = ROAD

    def _build_ruin(self, ruin: Structure, rng: random.Random):
        """Build crumbling ruins."""
        cx, cy = ruin.x, ruin.y
        r = ruin.radius

        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if dx * dx + dy * dy <= r * r:
                        # Scattered walls and floors
                        if abs(dx) == r or abs(dy) == r:
                            if rng.random() < 0.5:
                                self.tiles[ny][nx] = WALL
                            else:
                                self.tiles[ny][nx] = FLOOR
                        else:
                            self.tiles[ny][nx] = FLOOR

    def _build_roads(self, rng: random.Random):
        """Connect ALL settlement types with roads using MST + trade route extras.

        Uses the RoadNetwork system to build proper typed roads:
        - DIRT_TRACK between hamlets
        - GRAVEL_ROAD between hamlets and villages
        - PAVED_ROAD between villages and towns
        - KING_ROAD between towns and cities
        - MOUNTAIN_PASS through mountains

        Roads are routed around mountains and water using A* pathfinding.
        Bridges are placed over rivers. Different tile types are used for
        major vs minor roads.
        """
        from game.systems.roads import (
            RoadNetwork, RoadType, place_roadside_inns,
        )

        settlement_kinds = {"hamlet", "village", "town", "city", "castle"}
        settlements = [s for s in self.structures if s.kind in settlement_kinds]
        if len(settlements) < 2:
            return

        # Build the road network (MST + extra edges)
        self.road_network = RoadNetwork()
        self.road_network.build_from_settlements(
            self.structures, self.tiles, self.width, self.height, rng)

        # Draw road tiles for each segment
        # Process in order of importance so major roads overwrite minor ones
        sorted_segs = sorted(self.road_network.segments,
                             key=lambda s: s.road_type.value)

        for seg in sorted_segs:
            # Map road type to tile and width
            if seg.road_type == RoadType.KING_ROAD:
                road_tile = COBBLESTONE
                road_width = 1  # 3 tiles wide
            elif seg.road_type == RoadType.PAVED_ROAD:
                road_tile = ROAD
                road_width = 1  # 3 tiles wide
            elif seg.road_type == RoadType.GRAVEL_ROAD:
                road_tile = GRAVEL_ROAD
                road_width = 0  # 1 tile wide
            elif seg.road_type == RoadType.DIRT_TRACK:
                road_tile = DIRT_TRACK
                road_width = 0  # 1 tile wide
            elif seg.road_type == RoadType.MOUNTAIN_PASS:
                road_tile = MOUNTAIN_PASS
                road_width = 0  # 1 tile wide
            else:
                road_tile = ROAD
                road_width = 0

            # Tiles that roads can overwrite
            natural = (GRASS, FOREST, SAND, DENSE_FOREST, SWAMP, FARMLAND,
                       ROCKY_GROUND, MARSH, SNOW, DIRT_TRACK, GRAVEL_ROAD)
            # Higher-tier roads can overwrite lower-tier roads
            if road_tile == COBBLESTONE:
                natural += (ROAD, GRAVEL_ROAD, DIRT_TRACK)
            elif road_tile == ROAD:
                natural += (GRAVEL_ROAD, DIRT_TRACK)

            for wx, wy in seg.waypoints:
                for ry in range(-road_width, road_width + 1):
                    for rx in range(-road_width, road_width + 1):
                        if abs(rx) + abs(ry) > road_width + 1:
                            continue
                        nx, ny = wx + rx, wy + ry
                        if not (0 <= nx < self.width and 0 <= ny < self.height):
                            continue
                        tile = self.tiles[ny][nx]
                        if tile in natural:
                            self.tiles[ny][nx] = road_tile
                        elif tile == WATER:
                            self.tiles[ny][nx] = BRIDGE

        # Place roadside inns along long major roads
        inn_spawn_data = place_roadside_inns(
            self.road_network, self.tiles, self.width, self.height,
            self.structures, rng)
        if inn_spawn_data:
            if not hasattr(self, 'npc_spawn_data'):
                self.npc_spawn_data = []
            self.npc_spawn_data.extend(inn_spawn_data)

    def _draw_road(self, x0: int, y0: int, x1: int, y1: int, rng: random.Random):
        """Draw a winding road between two points."""
        x, y = float(x0), float(y0)
        dx = x1 - x0
        dy = y1 - y0
        dist = max(1, math.sqrt(dx * dx + dy * dy))
        steps = int(dist * 1.5)

        for step in range(steps + 1):
            t = step / max(1, steps)
            # Add some wobble
            wobble_x = math.sin(t * 8 + self.seed) * 1.5
            wobble_y = math.cos(t * 6 + self.seed) * 1.5

            px = int(x0 + dx * t + wobble_x)
            py = int(y0 + dy * t + wobble_y)

            # Place road tile and neighbors for width
            for ry in range(-1, 2):
                for rx in range(-1, 2):
                    nx, ny = px + rx, py + ry
                    if (0 <= nx < self.width and 0 <= ny < self.height and
                        abs(rx) + abs(ry) <= 1):
                        if self.tiles[ny][nx] in (GRASS, FOREST, SAND, DENSE_FOREST, SWAMP):
                            self.tiles[ny][nx] = ROAD

            # Bridge over water
            for ry in range(-1, 2):
                for rx in range(-1, 2):
                    nx, ny = px + rx, py + ry
                    if (0 <= nx < self.width and 0 <= ny < self.height and
                        abs(rx) + abs(ry) <= 1):
                        if self.tiles[ny][nx] == WATER:
                            self.tiles[ny][nx] = BRIDGE

    def _place_farms(self, rng: random.Random):
        """Place farmland near villages."""
        for s in self.structures:
            if s.kind != "village":
                continue
            # Place 1-3 farm patches
            for _ in range(rng.randint(1, 3)):
                angle = rng.uniform(0, 2 * math.pi)
                dist = rng.uniform(s.radius + 2, s.radius + 6)
                fx = int(s.x + math.cos(angle) * dist)
                fy = int(s.y + math.sin(angle) * dist)

                farm_w = rng.randint(3, 6)
                farm_h = rng.randint(3, 6)

                for dy in range(farm_h):
                    for dx in range(farm_w):
                        nx, ny = fx + dx, fy + dy
                        if (0 <= nx < self.width and 0 <= ny < self.height and
                            self.tiles[ny][nx] in (GRASS, FOREST)):
                            self.tiles[ny][nx] = FARMLAND

    def is_walkable(self, x: int, y: int, ignore_buildings: bool = False) -> bool:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return False
        tile = self.tiles[y][x]
        if TERRAIN_WALK_COST.get(tile, 999) >= 10:
            # Allow walking in shallow water (WATER tiles adjacent to land)
            if tile == WATER:
                from game.ui.water_render import is_deep_water
                return not is_deep_water(self.tiles, x, y,
                                         self.width, self.height)
            return False
        return True

    def get_walk_cost(self, x: int, y: int) -> float:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return 999
        tile = self.tiles[y][x]
        base_cost = TERRAIN_WALK_COST.get(tile, 999)

        # Shallow water (adjacent to land) is wadeable at cost 2.5
        if tile == WATER and base_cost >= 10:
            from game.ui.water_render import is_deep_water
            if not is_deep_water(self.tiles, x, y, self.width, self.height):
                base_cost = 2.5

        # Check rubble depth — accumulated debris slows or blocks movement
        rubble = getattr(self, '_rubble_tracker', None)
        if rubble:
            rubble_cost = rubble.get_walk_cost(x, y)
            if rubble_cost > 0:
                base_cost = max(base_cost, rubble_cost)

        return base_cost

    def reveal_around(self, x: int, y: int, radius: int = 8):
        """Mark tiles as explored around a position."""
        r2 = radius * radius
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= r2:
                    nx, ny = int(x) + dx, int(y) + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        self.explored[ny][nx] = True

    def modify_tile(self, x: int, y: int, new_type: int) -> bool:
        """Change a terrain tile. Returns True if successful.

        Also notifies any cached interior maps that overlap this position,
        so siege damage to exterior walls is reflected in interior views.
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            self.tiles[y][x] = new_type

            # Propagate to cached interiors
            for callback in getattr(self, '_tile_change_callbacks', []):
                callback(x, y, new_type)

            return True
        return False

    def register_tile_callback(self, callback):
        """Register a callback for tile changes: callback(x, y, new_type)."""
        if not hasattr(self, '_tile_change_callbacks'):
            self._tile_change_callbacks = []
        self._tile_change_callbacks.append(callback)

    def find_nearest_tile(self, x: int, y: int, tile_types, max_radius: int = 10) -> Optional[Tuple[int, int]]:
        """Find nearest tile of given type(s) in expanding spiral."""
        if isinstance(tile_types, int):
            tile_types = {tile_types}
        else:
            tile_types = set(tile_types)
        for r in range(1, max_radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if abs(dx) != r and abs(dy) != r:
                        continue  # only check the ring
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        if self.tiles[ny][nx] in tile_types:
                            return (nx, ny)
        return None

    def find_water_near(self, x: int, y: int, max_radius: int = 8) -> Optional[Tuple[int, int]]:
        """Find nearest water source (water tile, shallow water, or well)."""
        return self.find_nearest_tile(x, y, {WATER, SHALLOW_WATER, WELL}, max_radius)

    def _build_structure_grid(self):
        """Build spatial hash for fast structure lookups."""
        cell = 50  # grid cell size
        grid = {}
        for s in self.structures:
            r = s.radius + 1
            cx0 = int((s.x - r) // cell)
            cx1 = int((s.x + r) // cell)
            cy0 = int((s.y - r) // cell)
            cy1 = int((s.y + r) // cell)
            for gx in range(cx0, cx1 + 1):
                for gy in range(cy0, cy1 + 1):
                    grid.setdefault((gx, gy), []).append(s)
        self._struct_grid = grid
        self._struct_grid_cell = cell

    def get_structure_at(self, x: float, y: float) -> Optional[Structure]:
        """Get the structure at a given position (spatial-hash accelerated)."""
        if not hasattr(self, '_struct_grid'):
            self._build_structure_grid()
        cell = self._struct_grid_cell
        key = (int(x // cell), int(y // cell))
        candidates = self._struct_grid.get(key, ())
        for s in candidates:
            dx = x - s.x
            dy = y - s.y
            if dx * dx + dy * dy <= (s.radius + 1) ** 2:
                return s
        return None

    def find_open_pos_near(self, x: int, y: int, radius: int = 5,
                           rng: random.Random = None,
                           exclude: set = None) -> Tuple[int, int]:
        """Find a walkable position near the given coordinates, avoiding excluded positions."""
        if rng is None:
            rng = random.Random()
        if exclude is None:
            exclude = set()

        for _ in range(80):
            nx = x + rng.randint(-radius, radius)
            ny = y + rng.randint(-radius, radius)
            if self.is_walkable(nx, ny) and (nx, ny) not in exclude:
                return (nx, ny)

        # Fallback: any walkable nearby
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx, ny = x + dx, y + dy
                if self.is_walkable(nx, ny) and (nx, ny) not in exclude:
                    return (nx, ny)
        return (x, y)


# ================================================================
# CHUNKED WORLD — 10,000 x 10,000 world using WorldPlan + ChunkGrid
# ================================================================

class ChunkedWorld:
    """Drop-in replacement for World that uses chunked tile storage.

    Presents the exact same interface as World (tiles, explored,
    structures, is_walkable, etc.) so all existing game systems work
    unchanged. Internally uses WorldPlan for metadata and ChunkGrid
    for lazy tile generation.
    """

    def __init__(self, width: int = None, height: int = None,
                 seed: int = None, progress_callback=None,
                 use_history_sim: bool = None):
        """Initialize chunked world.

        Args:
            progress_callback: optional callable(text, fraction) for loading UI
            use_history_sim: if True, use history simulation for world gen.
                If None, reads from GameConfig.
        """
        from game.settings import WORLD_WIDTH_NEW, WORLD_HEIGHT_NEW
        from game.world.world_plan import WorldPlan
        from game.world.chunk import ChunkGrid
        from game.world.chunk_generator import generate_chunk

        _progress = progress_callback or (lambda t, p: None)

        self.width = width or WORLD_WIDTH_NEW
        self.height = height or WORLD_HEIGHT_NEW
        self.seed = seed if seed is not None else random.randint(0, 999999)

        # Determine world gen mode from config if not specified
        if use_history_sim is None:
            try:
                from game.config import GameConfig
                cfg = GameConfig()
                use_history_sim = cfg.get("world_gen_mode", "simulated") == "simulated"
            except Exception:
                use_history_sim = True  # default to history sim

        # Generate the world plan (compact metadata)
        if use_history_sim:
            _progress("Simulating world history...", 0.02)
        else:
            _progress("Planning world...", 0.02)
        self.plan = WorldPlan(self.width, self.height, self.seed,
                              use_history_sim=use_history_sim)
        self.plan.generate(progress_callback=_progress if use_history_sim else None)
        _progress("World plan complete", 0.18)

        # Tile storage — ChunkGrid provides world.tiles[y][x] interface
        self.tiles = ChunkGrid(self.width, self.height, default_tile=GRASS,
                               seed=self.seed)
        self.tiles.generator = generate_chunk
        self.tiles.world_plan = self.plan

        # Explored state — also chunk-based to avoid huge flat array
        self._explored_set: set = set()  # (x, y) tuples of explored tiles

        # Build structures list from the plan
        self.structures: List[Structure] = []
        self._build_structures_from_plan()

        # Key locations
        self.spawn_point = self.plan.spawn_point
        self.test_island_spawn = self.plan.test_island_spawn
        self.test_island_rect = self.plan.test_island_rect

        # NPC spawn data — built from plan's NPC roster
        self.npc_spawn_data = self._build_npc_spawn_data()

        # Elevation — provide fast lookup method, not a full array
        self.elevation = _ElevationProxy(self.plan)

        # Callback system for tile changes
        self._tile_change_callbacks = []

        # Building interior tiles — populated after structures are built
        self._building_interior_tiles: set = set()

        # Rubble tracker (set by simulation system)
        self._rubble_tracker = None

        # Road network placeholder (for systems that query it)
        self.road_network = None

        # Underground tile layers — separate from surface tiles.
        # {level_num: {(x, y): tile_type}}
        # Level -1 = first basement, -2 = deeper, etc.
        # Populated from building basements and later from tunnels/caves.
        self.underground: Dict[int, Dict[Tuple[int, int], int]] = {}
        self._build_underground_from_plan()
        self._generate_underground_tunnels()

        # Preload chunks around spawn
        _progress("Loading terrain chunks...", 0.20)
        self.tiles.preload_around(
            self.spawn_point[0], self.spawn_point[1], radius_chunks=2)

        # Sync structure buildings from plan (now that chunks are generated)
        self._sync_structure_buildings()

        # Build interior tile set from structures
        _progress("Mapping building interiors...", 0.24)
        self._refresh_building_interior_tiles()

    # ------------------------------------------------------------------
    # Explored state (uses set instead of 2D array)
    # ------------------------------------------------------------------

    @property
    def explored(self):
        """Return a proxy that supports explored[y][x] reads/writes."""
        return _ExploredProxy(self)

    def reveal_around(self, x: int, y: int, radius: int = 8):
        """Mark tiles as explored around a position."""
        r2 = radius * radius
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= r2:
                    nx, ny = int(x) + dx, int(y) + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        self._explored_set.add((nx, ny))

    # ------------------------------------------------------------------
    # Movement & Pathfinding
    # ------------------------------------------------------------------

    def is_walkable(self, x: int, y: int, ignore_buildings: bool = False) -> bool:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return False
        tile = self.tiles[y][x]
        if TERRAIN_WALK_COST.get(tile, 999) >= 10:
            # Allow walking in shallow water (WATER tiles adjacent to land)
            if tile == WATER:
                from game.ui.water_render import is_deep_water
                return not is_deep_water(self.tiles, x, y,
                                         self.width, self.height)
            return False
        # Buildings are now freely walkable — player enters through doors
        # on the overworld map without needing to switch to interior mode
        return True

    def get_walk_cost(self, x: int, y: int) -> float:
        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return 999
        tile = self.tiles[y][x]
        base_cost = TERRAIN_WALK_COST.get(tile, 999)
        # Shallow water (adjacent to land) is wadeable at cost 2.5
        if tile == WATER and base_cost >= 10:
            from game.ui.water_render import is_deep_water
            if not is_deep_water(self.tiles, x, y, self.width, self.height):
                base_cost = 2.5
        if self._rubble_tracker:
            rubble_cost = self._rubble_tracker.get_walk_cost(x, y)
            if rubble_cost > 0:
                base_cost = max(base_cost, rubble_cost)
        return base_cost

    # ------------------------------------------------------------------
    # Tile modification
    # ------------------------------------------------------------------

    def modify_tile(self, x: int, y: int, new_type: int) -> bool:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.tiles[y][x] = new_type
            for callback in self._tile_change_callbacks:
                callback(x, y, new_type)
            return True
        return False

    def register_tile_callback(self, callback):
        self._tile_change_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Finding locations
    # ------------------------------------------------------------------

    def find_nearest_tile(self, x: int, y: int, tile_types,
                          max_radius: int = 10) -> Optional[Tuple[int, int]]:
        if isinstance(tile_types, int):
            tile_types = {tile_types}
        else:
            tile_types = set(tile_types)
        for r in range(1, max_radius + 1):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    if abs(dx) != r and abs(dy) != r:
                        continue
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        if self.tiles[ny][nx] in tile_types:
                            return (nx, ny)
        return None

    def find_water_near(self, x: int, y: int,
                        max_radius: int = 8) -> Optional[Tuple[int, int]]:
        return self.find_nearest_tile(
            x, y, {WATER, SHALLOW_WATER, WELL}, max_radius)

    def _build_structure_grid(self):
        """Build spatial hash for fast structure lookups."""
        cell = 50
        grid = {}
        for s in self.structures:
            r = s.radius + 1
            cx0 = int((s.x - r) // cell)
            cx1 = int((s.x + r) // cell)
            cy0 = int((s.y - r) // cell)
            cy1 = int((s.y + r) // cell)
            for gx in range(cx0, cx1 + 1):
                for gy in range(cy0, cy1 + 1):
                    grid.setdefault((gx, gy), []).append(s)
        self._struct_grid = grid
        self._struct_grid_cell = cell

    def get_structure_at(self, x: float, y: float) -> Optional[Structure]:
        if not hasattr(self, '_struct_grid'):
            self._build_structure_grid()
        cell = self._struct_grid_cell
        key = (int(x // cell), int(y // cell))
        candidates = self._struct_grid.get(key, ())
        for s in candidates:
            dx = x - s.x
            dy = y - s.y
            if dx * dx + dy * dy <= (s.radius + 1) ** 2:
                return s
        return None

    def find_open_pos_near(self, x: int, y: int, radius: int = 5,
                           rng: random.Random = None,
                           exclude: set = None) -> Tuple[int, int]:
        if rng is None:
            rng = random.Random()
        if exclude is None:
            exclude = set()
        for _ in range(80):
            nx = x + rng.randint(-radius, radius)
            ny = y + rng.randint(-radius, radius)
            if self.is_walkable(nx, ny) and (nx, ny) not in exclude:
                return (nx, ny)
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx, ny = x + dx, y + dy
                if self.is_walkable(nx, ny) and (nx, ny) not in exclude:
                    return (nx, ny)
        return (x, y)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_structures_from_plan(self):
        """Convert plan settlements + special locations into Structure objects.

        Buildings are initially empty because chunks haven't been generated yet.
        They are synced lazily via _sync_structure_buildings().
        """
        self._plan_settlement_map: Dict[str, 'SettlementPlan'] = {}
        for sp in self.plan.settlements:
            struct = Structure(sp.name, sp.kind, sp.x, sp.y, radius=sp.radius)
            # Buildings are populated lazily after chunk generation
            struct.buildings = [(b["x"], b["y"], b["w"], b["h"])
                                for b in sp.buildings]
            self.structures.append(struct)
            self._plan_settlement_map[sp.name] = sp

        for loc in self.plan.special_locations:
            struct = Structure(loc.name, loc.kind, loc.x, loc.y,
                               radius=loc.radius)
            self.structures.append(struct)

    def _sync_structure_buildings(self):
        """Sync Structure.buildings from plan settlements after chunk gen.

        Called after chunks are loaded so that building data (populated by
        the chunk generator) propagates to the Structure objects used by
        game systems.
        """
        for struct in self.structures:
            sp = self._plan_settlement_map.get(struct.name)
            if sp and sp.buildings and not struct.buildings:
                struct.buildings = [(b["x"], b["y"], b["w"], b["h"])
                                    for b in sp.buildings]

    def _build_npc_spawn_data(self) -> list:
        """Convert plan NPC roster into spawn data list."""
        result = []
        for npc in self.plan.npc_roster:
            result.append({
                "x": npc["home_x"],
                "y": npc["home_y"],
                "class": npc["class"],
                "race": npc["race"],
                "building": npc.get("role", ""),
                "name": npc["name"],
            })
        return result

    def _build_underground_from_plan(self):
        """Stamp building basements and underground structures into the
        underground tile layers.

        Each building with floors below 0 gets its layout stamped into
        world.underground[level][(x,y)] = tile_type. This creates a
        sparse tile map for each underground level.

        Later, tunnels/caves/sewers will also add tiles here, connecting
        buildings and creating underground networks.
        """
        for sp in self.plan.settlements:
            for bld in sp.buildings:
                floors = bld.get('floors', {})
                bx, by = bld['x'], bld['y']
                bw, bh = bld['w'], bld['h']

                for level_num, layout in floors.items():
                    if level_num >= 0:
                        continue  # only underground levels

                    if level_num not in self.underground:
                        self.underground[level_num] = {}

                    level_tiles = self.underground[level_num]
                    for dy in range(min(len(layout), bh)):
                        for dx in range(min(len(layout[dy]), bw)):
                            level_tiles[(bx + dx, by + dy)] = layout[dy][dx]

    def _generate_underground_tunnels(self):
        """Connect nearby buildings that have basements with underground tunnels.

        For each settlement, finds pairs of buildings that both have a
        basement (floor level < 0) and are within 30 tiles of each other.
        Carves an L-shaped corridor of FLOOR tiles bordered by WALL at
        level -1 to connect them.
        """
        MAX_TUNNEL_DIST = 30

        for sp in self.plan.settlements:
            # Gather buildings that have basements
            basement_buildings = []
            for bld in sp.buildings:
                floors = bld.get('floors', {})
                has_basement = any(lvl < 0 for lvl in floors)
                if has_basement:
                    # Use center of building as connection point
                    cx = bld['x'] + bld['w'] // 2
                    cy = bld['y'] + bld['h'] // 2
                    basement_buildings.append((cx, cy, bld))

            if len(basement_buildings) < 2:
                continue

            # Ensure level -1 exists
            if -1 not in self.underground:
                self.underground[-1] = {}
            level_tiles = self.underground[-1]

            # Connect nearby pairs (greedy: each building connects to nearest
            # unconnected neighbor to avoid excessive tunnels)
            connected = set()
            for i, (ax, ay, _bld_a) in enumerate(basement_buildings):
                for j, (bx, by, _bld_b) in enumerate(basement_buildings):
                    if j <= i:
                        continue
                    pair = (i, j)
                    if pair in connected:
                        continue

                    dist = math.sqrt((bx - ax) ** 2 + (by - ay) ** 2)
                    if dist > MAX_TUNNEL_DIST:
                        continue

                    connected.add(pair)

                    # Carve an L-shaped tunnel from (ax, ay) to (bx, by).
                    # Go horizontal first, then vertical.
                    self._carve_tunnel_segment(
                        level_tiles, ax, ay, bx, ay)   # horizontal leg
                    self._carve_tunnel_segment(
                        level_tiles, bx, ay, bx, by)   # vertical leg

    def _carve_tunnel_segment(self, level_tiles, x1, y1, x2, y2):
        """Carve a straight tunnel segment between two points at level -1.

        Places FLOOR tiles along the path (1 tile wide) with WALL on
        either side (only where no tile already exists, so we don't
        overwrite existing basement floors).
        """
        dx = 0 if x1 == x2 else (1 if x2 > x1 else -1)
        dy = 0 if y1 == y2 else (1 if y2 > y1 else -1)

        cx, cy = x1, y1
        while True:
            # Place floor at center
            level_tiles[(cx, cy)] = FLOOR

            # Place wall on perpendicular sides (if not already a floor)
            if dx != 0:
                # Horizontal tunnel — walls above and below
                for wy in (cy - 1, cy + 1):
                    if level_tiles.get((cx, wy)) != FLOOR:
                        level_tiles[(cx, wy)] = WALL
            else:
                # Vertical tunnel — walls left and right
                for wx in (cx - 1, cx + 1):
                    if level_tiles.get((wx, cy)) != FLOOR:
                        level_tiles[(wx, cy)] = WALL

            if cx == x2 and cy == y2:
                break
            cx += dx
            cy += dy

    # ------------------------------------------------------------------
    # Underground access
    # ------------------------------------------------------------------

    def get_underground_tile(self, x: int, y: int, level: int) -> int:
        """Get a tile from the underground at (x, y, level).
        Returns WALL if no tile exists (solid rock).
        """
        level_tiles = self.underground.get(level)
        if level_tiles:
            return level_tiles.get((x, y), WALL)
        return WALL

    def set_underground_tile(self, x: int, y: int, level: int, tile: int):
        """Set a tile in the underground. Creates the level if needed."""
        if level not in self.underground:
            self.underground[level] = {}
        self.underground[level][(x, y)] = tile

    def is_underground_walkable(self, x: int, y: int, level: int) -> bool:
        """Check if an underground tile is walkable."""
        tile = self.get_underground_tile(x, y, level)
        return TERRAIN_WALK_COST.get(tile, 999) < 10

    def get_underground_tiles_in_rect(self, x: int, y: int, w: int, h: int,
                                       level: int) -> Dict[Tuple[int, int], int]:
        """Get all underground tiles in a rectangle. For rendering."""
        level_tiles = self.underground.get(level, {})
        result = {}
        for ty in range(y, y + h):
            for tx in range(x, x + w):
                if (tx, ty) in level_tiles:
                    result[(tx, ty)] = level_tiles[(tx, ty)]
        return result

    def get_underground_connections(self, level: int = -1) -> list:
        """Get all surface-to-underground connection points at a level.
        Returns list of (x, y, tile_type) for stairs/shafts/entrances.

        Useful for pathfinding and rendering entrance markers on the surface.
        """
        connections = []
        level_tiles = self.underground.get(level, {})
        for (x, y), tile in level_tiles.items():
            if tile in (STAIRS_UP, STAIRS_DOWN):
                connections.append((x, y, tile))
        return connections

    def _refresh_building_interior_tiles(self):
        """Rebuild set of building interior tiles from plan settlements."""
        self._building_interior_tiles = set()
        sx, sy = self.spawn_point
        self._scan_building_tiles_near(sx, sy, 500)

    def update_building_interiors_near(self, x: float, y: float):
        """Refresh building interior tiles near the player position."""
        self._sync_structure_buildings()
        self._scan_building_tiles_near(x, y, 200)

    def _scan_building_tiles_near(self, cx: float, cy: float, radius: float):
        """Scan plan settlement buildings near (cx,cy) and add interior tiles."""
        interior_types = (FLOOR, TABLE, BED, CHEST, STAIRS_UP, STAIRS_DOWN,
                          FIREPLACE, PILLAR, ALTAR, THRONE, BOOKSHELF, BARREL,
                          ANVIL, FORGE_FIRE, FOUNTAIN, CARPET, MOSAIC, ARCHWAY)
        for sp in self.plan.settlements:
            if abs(sp.x - cx) > radius or abs(sp.y - cy) > radius:
                continue
            for bld in sp.buildings:
                bx, by = bld['x'], bld['y']
                bw, bh = bld['w'], bld['h']
                for dy in range(bh):
                    for dx in range(bw):
                        tx, ty = bx + dx, by + dy
                        if 0 <= tx < self.width and 0 <= ty < self.height:
                            tile = self.tiles[ty][tx]
                            if tile in interior_types:
                                self._building_interior_tiles.add((tx, ty))


class _ExploredProxy:
    """Proxy so world.explored[y][x] works with set-based storage."""

    def __init__(self, world: ChunkedWorld):
        self._world = world

    def __getitem__(self, y: int):
        return _ExploredRow(self._world, y)


class _ExploredRow:
    """Proxy for a single row of explored state."""

    def __init__(self, world: ChunkedWorld, y: int):
        self._world = world
        self._y = y

    def __getitem__(self, x: int) -> bool:
        return (x, self._y) in self._world._explored_set

    def __setitem__(self, x: int, value: bool):
        if value:
            self._world._explored_set.add((x, self._y))
        else:
            self._world._explored_set.discard((x, self._y))


class _ElevationProxy:
    """Proxy so world.elevation[y][x] works with plan's elevation cache."""

    def __init__(self, plan):
        self._plan = plan

    def __getitem__(self, y: int):
        return _ElevationRow(self._plan, y)


class _ElevationRow:
    def __init__(self, plan, y: int):
        self._plan = plan
        self._y = y

    def __getitem__(self, x: int) -> float:
        return self._plan.get_elevation_fast(x, self._y)
