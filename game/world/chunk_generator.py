"""Chunk Generator — converts WorldPlan metadata into actual tile data.

Given a Chunk (cx, cy) and a WorldPlan, this module deterministically
generates the tile contents:
  1. Base terrain from FBM noise (elevation + moisture + edge falloff)
  2. Rivers stamped as water tiles
  3. Roads stamped along waypoint paths
  4. Settlement buildings placed from blueprints
  5. Resource nodes scattered based on terrain rules
  6. Special locations (temples, ruins, test island)

Everything is seeded from (world_seed, cx, cy) so the same chunk always
generates the same tiles.
"""

import math
import random
import numpy as np
from typing import List, Tuple

from game.settings import *
from game.world.chunk import Chunk, CHUNK_SIZE


def generate_chunk(chunk: Chunk, plan) -> None:
    """Fill a chunk with tile data derived from the world plan.

    This is the main entry point — called by ChunkGrid._ensure_chunk()
    when a chunk is first accessed.
    """
    cx, cy = chunk.cx, chunk.cy
    x0 = cx * CHUNK_SIZE
    y0 = cy * CHUNK_SIZE

    # Deterministic RNG for this chunk
    chunk_seed = plan.seed ^ (cx * 374761393 + cy * 668265263)
    rng = random.Random(chunk_seed)

    # 1. Base terrain
    _generate_terrain(chunk, plan, x0, y0)

    # 2. Rivers
    _stamp_rivers(chunk, plan, x0, y0)

    # 3. Special locations — islands and terrain modifications first
    _stamp_special_locations(chunk, plan, x0, y0, before_settlements=True)

    # 4. Settlements (buildings, roads within settlement)
    _stamp_settlements(chunk, plan, x0, y0, rng)

    # 5. Special locations — custom buildings (after settlements to override)
    _stamp_special_locations(chunk, plan, x0, y0, before_settlements=False)

    # 6. Roads between settlements
    _stamp_roads(chunk, plan, x0, y0)

    # 6. Resource placement
    _place_resources(chunk, plan, x0, y0, rng)

    chunk.generated = True


# ================================================================
# TERRAIN
# ================================================================

def _generate_terrain(chunk: Chunk, plan, x0: int, y0: int):
    """Generate base terrain tiles from FBM noise (vectorized with numpy)."""
    tiles = chunk.tiles
    w = plan.width
    h = plan.height
    e_scale = plan.elevation_scale
    m_scale = plan.moisture_scale
    falloff = plan.edge_falloff_strength
    seed = plan.seed

    # Build coordinate grids for this chunk
    lx = np.arange(CHUNK_SIZE, dtype=np.float32)
    ly = np.arange(CHUNK_SIZE, dtype=np.float32)
    lxx, lyy = np.meshgrid(lx, ly)
    wx = (lxx + x0)
    wy = (lyy + y0)

    # Vectorized FBM (hash-based noise, fast)
    elev = _fbm_vec(wx * e_scale, wy * e_scale, octaves=5, seed=seed)
    moist = _fbm_vec(wx * m_scale, wy * m_scale, octaves=4, seed=seed + 7919)

    # Edge falloff
    edge_dx = (wx / w - 0.5) * 2
    edge_dy = (wy / h - 0.5) * 2
    edge_dist = np.sqrt(edge_dx * edge_dx + edge_dy * edge_dy)
    elev *= np.maximum(0.0, 1.0 - edge_dist * falloff)

    # Biome assignment (vectorized)
    # Start with grass, then overwrite
    result = np.full((CHUNK_SIZE, CHUNK_SIZE), GRASS, dtype=np.int8)

    result[elev < 0.22] = WATER
    sand_mask = (elev >= 0.22) & (elev < 0.28)
    result[sand_mask] = SAND

    mid_mask = (elev >= 0.28) & (elev < 0.65)
    result[mid_mask & (moist > 0.65)] = DENSE_FOREST
    result[mid_mask & (moist > 0.50) & (moist <= 0.65)] = FOREST
    result[mid_mask & (moist < 0.20)] = SAND
    result[mid_mask & (elev < 0.35) & (moist > 0.60)] = SWAMP

    result[(elev >= 0.65) & (elev < 0.78)] = MOUNTAIN
    result[elev >= 0.78] = SNOW

    # Mark out-of-bounds as water
    result[wy >= h] = WATER
    result[wx >= w] = WATER

    tiles[:] = result


def _hash2d_vec(x: np.ndarray, y: np.ndarray, seed: int) -> np.ndarray:
    """Vectorized 2D hash for noise generation."""
    x = x.astype(np.int64)
    y = y.astype(np.int64)
    n = x * 374761393 + y * 668265263 + seed * 1274126177
    n = (n ^ (n >> 13)) * np.int64(1274126177)
    n = n ^ (n >> 16)
    return (n & np.int64(0x7FFFFFFF)).astype(np.float32) / np.float32(0x7FFFFFFF)


def _fbm_vec(x: np.ndarray, y: np.ndarray, octaves: int = 5,
             gain: float = 0.5, seed: int = 0) -> np.ndarray:
    """Vectorized FBM noise using hash-based value noise."""
    total = np.zeros_like(x)
    amplitude = 1.0
    frequency = 1.0
    max_val = 0.0

    for i in range(octaves):
        sx = x * frequency
        sy = y * frequency
        ix = np.floor(sx).astype(np.int64)
        iy = np.floor(sy).astype(np.int64)
        fx = sx - ix
        fy = sy - iy
        # Smoothstep
        fx = fx * fx * (3.0 - 2.0 * fx)
        fy = fy * fy * (3.0 - 2.0 * fy)

        s = seed + i * 31
        v00 = _hash2d_vec(ix, iy, s)
        v10 = _hash2d_vec(ix + 1, iy, s)
        v01 = _hash2d_vec(ix, iy + 1, s)
        v11 = _hash2d_vec(ix + 1, iy + 1, s)

        v0 = v00 + (v10 - v00) * fx
        v1 = v01 + (v11 - v01) * fx
        val = v0 + (v1 - v0) * fy

        total += val * amplitude
        max_val += amplitude
        amplitude *= gain
        frequency *= 2.0

    return total / max_val


# ================================================================
# RIVERS
# ================================================================

def _stamp_rivers(chunk: Chunk, plan, x0: int, y0: int):
    """Stamp river tiles along planned river paths."""
    rivers = plan.rivers_in_chunk(chunk.cx, chunk.cy, CHUNK_SIZE)
    if not rivers:
        return

    tiles = chunk.tiles
    for river in rivers:
        for i in range(len(river.points) - 1):
            px, py = river.points[i]
            nx, ny = river.points[i + 1]
            # Bresenham between consecutive points
            for wx, wy in _bresenham(px, py, nx, ny):
                lx = wx - x0
                ly = wy - y0
                if 0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE:
                    tiles[ly, lx] = WATER
                    # River is 2-3 tiles wide
                    for dx in [-1, 0, 1]:
                        nlx = lx + dx
                        if 0 <= nlx < CHUNK_SIZE:
                            if tiles[ly, nlx] != WATER:
                                tiles[ly, nlx] = SHALLOW_WATER


# ================================================================
# SPECIAL LOCATIONS
# ================================================================

def _stamp_special_locations(chunk: Chunk, plan, x0: int, y0: int,
                             before_settlements: bool = True):
    """Stamp special locations into the chunk.

    Called twice: once before settlements (terrain: islands, temples, ruins)
    and once after (custom buildings like test tower that override settlement boxes).
    """
    tiles = chunk.tiles
    x1 = x0 + CHUNK_SIZE
    y1 = y0 + CHUNK_SIZE

    # Which kinds go before vs after settlements
    before_kinds = {"test_island", "temple", "ruins"}
    after_kinds = {"test_building"}

    wanted = before_kinds if before_settlements else after_kinds

    for loc in plan.special_locations:
        if loc.kind not in wanted:
            continue
        if (loc.x - loc.radius >= x1 or loc.x + loc.radius < x0 or
                loc.y - loc.radius >= y1 or loc.y + loc.radius < y0):
            continue

        if loc.kind == "test_island":
            _stamp_test_island(tiles, loc, x0, y0, plan)
        elif loc.kind == "temple":
            _stamp_temple(tiles, loc, x0, y0)
        elif loc.kind == "test_building":
            _stamp_test_building(tiles, loc, x0, y0)
        elif loc.kind == "ruins":
            _stamp_ruins(tiles, loc, x0, y0, plan.seed)


def _stamp_test_island(tiles, loc, x0: int, y0: int, plan):
    """Carve the test island: ocean buffer + sand ellipse."""
    island_w, island_h = 120, 80
    ix, iy = loc.x, loc.y
    rx, ry = island_w / 2.0, island_h / 2.0

    for ly in range(CHUNK_SIZE):
        wy = y0 + ly
        for lx in range(CHUNK_SIZE):
            wx = x0 + lx
            dx = wx - ix
            dy = wy - iy

            # Ocean buffer (8 tiles around island)
            if abs(dx) <= rx + 8 and abs(dy) <= ry + 8:
                e = (dx / rx) ** 2 + (dy / ry) ** 2
                if e <= 1.0:
                    tiles[ly, lx] = SAND
                elif e <= 1.08:
                    tiles[ly, lx] = SAND  # fringe
                elif abs(dx) <= rx + 8 and abs(dy) <= ry + 8:
                    tiles[ly, lx] = WATER


def _stamp_temple(tiles, loc, x0: int, y0: int):
    """Stamp a circular temple structure."""
    r = loc.radius
    cx, cy = loc.x, loc.y

    for ly in range(CHUNK_SIZE):
        wy = y0 + ly
        dy = wy - cy
        for lx in range(CHUNK_SIZE):
            wx = x0 + lx
            dx = wx - cx

            dist2 = dx * dx + dy * dy

            # Clear area around temple
            if dist2 <= (r + 3) * (r + 3):
                # Determine if this is on sand (test island) or grass
                if tiles[ly, lx] == SAND:
                    pass  # keep sand
                else:
                    tiles[ly, lx] = GRASS

            if dist2 <= r * r:
                if dist2 >= (r - 1) * (r - 1):
                    tiles[ly, lx] = WALL
                else:
                    tiles[ly, lx] = FLOOR

            # Doors (3 tiles wide on each cardinal side)
            if abs(dx) <= 1 and (dy <= -r + 2 and dy >= -r):
                if tiles[ly, lx] == WALL:
                    tiles[ly, lx] = DOOR
            if abs(dx) <= 1 and (dy >= r - 2 and dy <= r):
                if tiles[ly, lx] == WALL:
                    tiles[ly, lx] = DOOR
            if abs(dy) <= 1 and (dx >= r - 2 and dx <= r):
                if tiles[ly, lx] == WALL:
                    tiles[ly, lx] = DOOR
            if abs(dy) <= 1 and (dx <= -r + 2 and dx >= -r):
                if tiles[ly, lx] == WALL:
                    tiles[ly, lx] = DOOR


def _stamp_test_building(tiles, loc, x0: int, y0: int):
    """Stamp a 3-story test building with underground level.

    Ground floor layout (10x10):
    - Walls around edge, door on south side
    - STAIRS_UP in northeast corner
    - STAIRS_DOWN in northwest corner
    - Furniture: table, bed, chest, fireplace, bookshelf
    """
    cx, cy = loc.x, loc.y
    w, h = 10, 10
    bx, by = cx - w // 2, cy - h // 2

    # Ground floor tile layout
    layout = [
        [WALL, WALL,       WALL,  WALL,  WALL,  WALL,  WALL,  WALL,       WALL,  WALL],
        [WALL, STAIRS_DOWN,FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR,      STAIRS_UP, WALL],
        [WALL, FLOOR,      FLOOR, TABLE, FLOOR, FLOOR, FLOOR, FLOOR,      FLOOR, WALL],
        [WALL, FLOOR,      FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, BOOKSHELF,  FLOOR, WALL],
        [WALL, FLOOR,      FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR,      FLOOR, WALL],
        [WALL, FIREPLACE,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR,      FLOOR, WALL],
        [WALL, FLOOR,      FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR,      FLOOR, WALL],
        [WALL, FLOOR,      BED,   FLOOR, FLOOR, FLOOR, CHEST, FLOOR,      FLOOR, WALL],
        [WALL, FLOOR,      FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR,      FLOOR, WALL],
        [WALL, WALL,       WALL,  WALL,  DOOR,  DOOR,  WALL,  WALL,       WALL,  WALL],
    ]

    for dy in range(h):
        wy = by + dy
        ly = wy - y0
        if ly < 0 or ly >= CHUNK_SIZE:
            continue
        for dx in range(w):
            wx = bx + dx
            lx = wx - x0
            if lx < 0 or lx >= CHUNK_SIZE:
                continue
            tiles[ly, lx] = layout[dy][dx]


def _stamp_ruins(tiles, loc, x0: int, y0: int, seed: int):
    """Stamp a small ruin structure."""
    rng = random.Random(seed ^ (loc.x * 31 + loc.y * 97))
    r = loc.radius

    for ly in range(CHUNK_SIZE):
        wy = y0 + ly
        dy = wy - loc.y
        for lx in range(CHUNK_SIZE):
            wx = x0 + lx
            dx = wx - loc.x
            dist2 = dx * dx + dy * dy
            if dist2 <= r * r:
                if abs(dx) >= r - 1 or abs(dy) >= r - 1:
                    tiles[ly, lx] = WALL if rng.random() < 0.5 else FLOOR
                else:
                    tiles[ly, lx] = FLOOR


# ================================================================
# SETTLEMENTS
# ================================================================

def _stamp_settlements(chunk: Chunk, plan, x0: int, y0: int,
                       rng: random.Random):
    """Stamp settlement buildings, roads, walls, and farms.

    Uses the SettlementPlanner layout for zone-based building placement
    with medieval layout principles: market at center, craft districts,
    walls following terrain, farms outside walls.
    """
    settlements = plan.settlements_overlapping_chunk(
        chunk.cx, chunk.cy, CHUNK_SIZE)

    if not settlements:
        return

    tiles = chunk.tiles

    for sp in settlements:
        # Generate building data once per settlement (cached on plan)
        if not sp.buildings:
            s_rng = random.Random(plan.seed ^ hash(sp.name))
            _generate_settlement_buildings(sp, plan, s_rng)

        layout = getattr(sp, '_layout', None)
        spec = getattr(sp, 'specialization', 'general')

        # Clear settlement area first — specialization affects what we clear
        for ly in range(CHUNK_SIZE):
            wy = y0 + ly
            dy = wy - sp.y
            for lx in range(CHUNK_SIZE):
                wx = x0 + lx
                dx = wx - sp.x
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < sp.radius:
                    current = tiles[ly, lx]

                    # Port/fishing: keep water at edges (for docks)
                    if spec in ("port", "fishing"):
                        if current == WATER and dist > sp.radius * 0.6:
                            continue  # keep outer water for waterfront
                        if current == SHALLOW_WATER:
                            continue

                    # Swamp: keep some swamp tiles for atmosphere
                    if spec == "swamp":
                        if current == SWAMP and dist > sp.radius * 0.4:
                            continue  # keep outer swamp

                    # Mining: keep mountain at edges
                    if spec == "mining":
                        if current == MOUNTAIN and dist > sp.radius * 0.5:
                            continue

                    if current in (WATER, MOUNTAIN, SNOW,
                                   DENSE_FOREST, SWAMP):
                        tiles[ly, lx] = GRASS

        # Stamp roads from layout (or fallback to cross-roads)
        if layout and layout.roads:
            _stamp_settlement_roads(tiles, layout.roads, x0, y0, sp)
        else:
            # Fallback: simple cross-roads through center
            for ly in range(CHUNK_SIZE):
                wy = y0 + ly
                dy = wy - sp.y
                for lx in range(CHUNK_SIZE):
                    wx = x0 + lx
                    dx = wx - sp.x
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < sp.radius * 0.8:
                        if ((abs(dx) <= 1 or abs(dy) <= 1) and
                                tiles[ly, lx] == GRASS):
                            tiles[ly, lx] = ROAD

        # Stamp walls and defenses
        if layout and layout.defenses:
            _stamp_settlement_defenses(tiles, layout.defenses, x0, y0)

        # Stamp farms
        if layout and layout.farms:
            _stamp_settlement_farms(tiles, layout.farms, x0, y0)

        # Stamp wells
        if layout and layout.well_positions:
            for wx, wy in layout.well_positions:
                lx = wx - x0
                ly = wy - y0
                if 0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE:
                    if tiles[ly, lx] in (GRASS, ROAD):
                        tiles[ly, lx] = WELL

        # Stamp each building's blueprint tiles
        for bld in sp.buildings:
            bp_tiles = bld.get("bp_tiles")
            bx, by = bld["x"], bld["y"]
            bw, bh = bld["w"], bld["h"]

            if bp_tiles:
                # Use actual blueprint tile data
                for bdy in range(bh):
                    wy = by + bdy
                    ly = wy - y0
                    if ly < 0 or ly >= CHUNK_SIZE:
                        continue
                    for bdx in range(bw):
                        wx = bx + bdx
                        lx = wx - x0
                        if lx < 0 or lx >= CHUNK_SIZE:
                            continue
                        bt = bp_tiles[bdy][bdx]
                        if bt != GRASS:  # GRASS = exterior/skip
                            tiles[ly, lx] = bt
            else:
                # Fallback: simple box building
                for bdy in range(bh):
                    wy = by + bdy
                    ly = wy - y0
                    if ly < 0 or ly >= CHUNK_SIZE:
                        continue
                    for bdx in range(bw):
                        wx = bx + bdx
                        lx = wx - x0
                        if lx < 0 or lx >= CHUNK_SIZE:
                            continue
                        if bdx == 0 or bdx == bw - 1 or bdy == 0 or bdy == bh - 1:
                            if bdx == bw // 2 and bdy == bh - 1:
                                tiles[ly, lx] = DOOR
                            else:
                                tiles[ly, lx] = WALL
                        else:
                            tiles[ly, lx] = FLOOR

        # Specialization-specific terrain post-processing
        _stamp_specialization_features(tiles, sp, x0, y0, plan, rng)


def _stamp_specialization_features(tiles, sp, x0, y0, plan, rng):
    """Add specialization-specific terrain features after buildings.

    This creates the visual and functional character of specialized
    settlements: docks for ports, mine entrances for mining towns,
    extra farmland for agricultural settlements, etc.
    """
    spec = getattr(sp, 'specialization', 'general')
    if spec == "general":
        return

    cx, cy = sp.x, sp.y
    radius = sp.radius

    if spec in ("port", "fishing"):
        # Place BRIDGE tiles at water edges to create docks
        for ly in range(CHUNK_SIZE):
            wy = y0 + ly
            dy = wy - cy
            for lx in range(CHUNK_SIZE):
                wx = x0 + lx
                dx = wx - cx
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < radius * 0.9:
                    current = tiles[ly, lx]
                    # Convert water tiles adjacent to land into bridge (dock)
                    if current == WATER:
                        has_land = False
                        for ddx, ddy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                            nlx, nly = lx + ddx, ly + ddy
                            if (0 <= nlx < CHUNK_SIZE and 0 <= nly < CHUNK_SIZE):
                                adj = tiles[nly, nlx]
                                if adj not in (WATER, SHALLOW_WATER, BRIDGE):
                                    has_land = True
                                    break
                        if has_land and rng.random() < 0.7:
                            tiles[ly, lx] = BRIDGE

    elif spec == "mining":
        # Place STAIRS_DOWN at mountain edges within settlement
        mines_placed = 0
        for ly in range(CHUNK_SIZE):
            wy = y0 + ly
            dy = wy - cy
            for lx in range(CHUNK_SIZE):
                wx = x0 + lx
                dx = wx - cx
                dist = math.sqrt(dx * dx + dy * dy)
                if radius * 0.4 < dist < radius * 0.7:
                    if tiles[ly, lx] == MOUNTAIN:
                        # Check for adjacent grass to place entrance
                        for ddx, ddy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                            nlx, nly = lx + ddx, ly + ddy
                            if (0 <= nlx < CHUNK_SIZE and 0 <= nly < CHUNK_SIZE
                                    and tiles[nly, nlx] == GRASS):
                                if rng.random() < 0.15 and mines_placed < 3:
                                    tiles[nly, nlx] = STAIRS_DOWN
                                    mines_placed += 1
                                break

    elif spec == "agricultural":
        # Extra farmland around the settlement
        for ly in range(CHUNK_SIZE):
            wy = y0 + ly
            dy = wy - cy
            for lx in range(CHUNK_SIZE):
                wx = x0 + lx
                dx = wx - cx
                dist = math.sqrt(dx * dx + dy * dy)
                if radius * 0.7 < dist < radius * 1.3:
                    if tiles[ly, lx] == GRASS and rng.random() < 0.35:
                        tiles[ly, lx] = rng.choice([FARMLAND, WHEAT_FIELD,
                                                     FARMLAND, FARMLAND])

    elif spec == "oasis":
        # Ensure a well at the center and thick walls on buildings
        center_lx = cx - x0
        center_ly = cy - y0
        if 0 <= center_lx < CHUNK_SIZE and 0 <= center_ly < CHUNK_SIZE:
            if tiles[center_ly, center_lx] in (GRASS, ROAD, FLOOR):
                tiles[center_ly, center_lx] = WELL

    elif spec == "swamp":
        # Convert some floor tiles to BUILT_FLOOR for raised-building feel
        for bld in sp.buildings:
            bx, by = bld["x"], bld["y"]
            bw, bh = bld["w"], bld["h"]
            for bdy in range(bh):
                wy = by + bdy
                ly = wy - y0
                if ly < 0 or ly >= CHUNK_SIZE:
                    continue
                for bdx in range(bw):
                    wx = bx + bdx
                    lx = wx - x0
                    if lx < 0 or lx >= CHUNK_SIZE:
                        continue
                    if tiles[ly, lx] == FLOOR:
                        tiles[ly, lx] = BUILT_FLOOR

    elif spec == "lumber":
        # Place tree stumps around the forest edge (logging area)
        for ly in range(CHUNK_SIZE):
            wy = y0 + ly
            dy = wy - cy
            for lx in range(CHUNK_SIZE):
                wx = x0 + lx
                dx = wx - cx
                dist = math.sqrt(dx * dx + dy * dy)
                if radius * 0.6 < dist < radius * 1.0:
                    if tiles[ly, lx] == GRASS:
                        # Near forest = tree stumps from logging
                        has_forest = False
                        for ddx, ddy in [(1, 0), (-1, 0), (0, 1), (0, -1),
                                          (2, 0), (-2, 0), (0, 2), (0, -2)]:
                            nlx, nly = lx + ddx, ly + ddy
                            if (0 <= nlx < CHUNK_SIZE and 0 <= nly < CHUNK_SIZE):
                                if tiles[nly, nlx] in (FOREST, DENSE_FOREST):
                                    has_forest = True
                                    break
                        if has_forest and rng.random() < 0.12:
                            from game.settings import TREE_STUMP
                            tiles[ly, lx] = TREE_STUMP

    elif spec == "crossroads":
        # Wider central market square area
        for ly in range(CHUNK_SIZE):
            wy = y0 + ly
            dy = wy - cy
            for lx in range(CHUNK_SIZE):
                wx = x0 + lx
                dx = wx - cx
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < radius * 0.15:
                    if tiles[ly, lx] == GRASS:
                        tiles[ly, lx] = COBBLESTONE


def _stamp_settlement_roads(tiles, roads, x0, y0, sp):
    """Stamp planned settlement roads into the chunk."""
    road_tile_map = {
        "cobblestone": COBBLESTONE,
        "road": ROAD,
        "gravel_road": GRAVEL_ROAD,
        "dirt_track": DIRT_TRACK,
    }

    no_overwrite = (WALL, FLOOR, DOOR, WATER, SHALLOW_WATER)

    for x1, y1, x2, y2, road_type in roads:
        road_tile = road_tile_map.get(road_type, ROAD)

        for wx, wy in _bresenham(x1, y1, x2, y2):
            lx = wx - x0
            ly = wy - y0
            if 0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE:
                if tiles[ly, lx] not in no_overwrite:
                    # Don't overwrite higher-quality roads with lower
                    current = tiles[ly, lx]
                    if current == COBBLESTONE:
                        continue
                    if current == ROAD and road_tile in (
                            GRAVEL_ROAD, DIRT_TRACK):
                        continue
                    tiles[ly, lx] = road_tile


def _stamp_settlement_defenses(tiles, defense, x0, y0):
    """Stamp walls, towers, and gates from defense plan."""
    # Stamp wall points
    for wx, wy in defense.wall_points:
        lx = wx - x0
        ly = wy - y0
        if 0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE:
            if tiles[ly, lx] not in (FLOOR, DOOR):
                tiles[ly, lx] = WALL

    # Stamp gate openings (3 tiles wide)
    for gx, gy, direction in defense.gate_positions:
        for offset in range(-1, 2):
            if direction in ("north", "south"):
                wx, wy = gx + offset, gy
            else:
                wx, wy = gx, gy + offset
            lx = wx - x0
            ly = wy - y0
            if 0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE:
                tiles[ly, lx] = ROAD

    # Stamp tower positions (2x2 wall blocks)
    for tx, ty in defense.tower_positions:
        for dy in range(-1, 1):
            for dx in range(-1, 1):
                lx = (tx + dx) - x0
                ly = (ty + dy) - y0
                if 0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE:
                    if tiles[ly, lx] not in (FLOOR, DOOR, ROAD):
                        tiles[ly, lx] = WALL


def _stamp_settlement_farms(tiles, farms, x0, y0):
    """Stamp farmland patches from farm plan."""
    for fx, fy, farm_r in farms:
        for dy in range(-farm_r, farm_r + 1):
            for dx in range(-farm_r, farm_r + 1):
                wx = fx + dx
                wy = fy + dy
                lx = wx - x0
                ly = wy - y0
                if 0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE:
                    if tiles[ly, lx] == GRASS:
                        tiles[ly, lx] = FARMLAND


def _generate_floor_layout(w: int, h: int, floor_num: int,
                           rng: random.Random,
                           ground_tiles: list) -> list:
    """Generate a tile layout for a non-ground floor.

    Upper floors have the same outer walls as the ground floor but
    different room layouts. Underground floors are darker/simpler.
    Stairs connect to the floor below/above.

    Args:
        w, h: building dimensions
        floor_num: positive=upper, negative=underground
        rng: seeded random for determinism
        ground_tiles: ground floor tile layout (for stair positions)
    """
    layout = []
    for dy in range(h):
        row = []
        for dx in range(w):
            # Outer walls match ground floor
            if dx == 0 or dx == w - 1 or dy == 0 or dy == h - 1:
                # Keep walls, but no doors on upper/lower floors
                gt = ground_tiles[dy][dx] if dy < len(ground_tiles) and dx < len(ground_tiles[dy]) else WALL
                if gt == DOOR:
                    if floor_num > 0:
                        row.append(WINDOW)  # upper floors have windows where doors were
                    else:
                        row.append(WALL)    # underground has solid walls
                else:
                    row.append(gt if gt == WALL else WALL)
            else:
                row.append(FLOOR)
        layout.append(row)

    # Find stair positions from ground floor
    stairs_up_pos = None
    stairs_down_pos = None
    for dy in range(h):
        for dx in range(w):
            if dy < len(ground_tiles) and dx < len(ground_tiles[dy]):
                if ground_tiles[dy][dx] == STAIRS_UP:
                    stairs_up_pos = (dx, dy)
                elif ground_tiles[dy][dx] == STAIRS_DOWN:
                    stairs_down_pos = (dx, dy)

    # Place connecting stairs
    if floor_num > 0:
        # Upper floor: STAIRS_DOWN at the position of ground's STAIRS_UP
        # (so you can go back down)
        if stairs_up_pos:
            sx, sy = stairs_up_pos
            if 0 < sx < w - 1 and 0 < sy < h - 1:
                layout[sy][sx] = STAIRS_DOWN
        # STAIRS_UP to go further up (at ground's STAIRS_DOWN position or nearby)
        if stairs_down_pos:
            sx, sy = stairs_down_pos
            if 0 < sx < w - 1 and 0 < sy < h - 1:
                layout[sy][sx] = STAIRS_UP
    elif floor_num < 0:
        # Underground: STAIRS_UP at position of ground's STAIRS_DOWN
        if stairs_down_pos:
            sx, sy = stairs_down_pos
            if 0 < sx < w - 1 and 0 < sy < h - 1:
                layout[sy][sx] = STAIRS_UP
        # STAIRS_DOWN to go further underground
        if stairs_up_pos:
            sx, sy = stairs_up_pos
            if 0 < sx < w - 1 and 0 < sy < h - 1:
                layout[sy][sx] = STAIRS_DOWN

    # Add interior walls and furniture based on floor type
    if floor_num > 0 and w > 5 and h > 5:
        # Upper floors: create rooms with corridors
        _add_rooms_to_floor(layout, w, h, floor_num, rng)

    elif floor_num < 0 and w > 5 and h > 5:
        # Underground: darker, rougher rooms with storage
        _add_underground_rooms(layout, w, h, abs(floor_num), rng)

    return layout


def _add_rooms_to_floor(layout, w, h, floor_num, rng):
    """Add room divisions and furniture to an upper floor layout.

    Creates 2-4 rooms separated by walls with doorways, then furnishes
    each room based on a template.
    """
    # Decide room division: horizontal, vertical, or both
    if w >= 8 and h >= 8:
        # Both: create 4 rooms with a corridor
        mid_x = w // 2
        mid_y = h // 2
        # Horizontal wall
        for dx in range(1, w - 1):
            if layout[mid_y][dx] == FLOOR:
                layout[mid_y][dx] = WALL
        # Vertical wall
        for dy in range(1, h - 1):
            if layout[dy][mid_x] == FLOOR:
                layout[dy][mid_x] = WALL
        # Door openings (2 tiles wide)
        for offset in [-1, 0]:
            # Horizontal doors
            door_x = mid_x // 2 + rng.randint(-1, 1)
            door_x = max(2, min(mid_x - 2, door_x))
            if 0 < door_x < w - 1:
                layout[mid_y][door_x] = DOOR
            door_x2 = mid_x + (w - mid_x) // 2 + rng.randint(-1, 1)
            door_x2 = max(mid_x + 2, min(w - 3, door_x2))
            if 0 < door_x2 < w - 1:
                layout[mid_y][door_x2] = DOOR
            # Vertical doors
            door_y = mid_y // 2 + rng.randint(-1, 1)
            door_y = max(2, min(mid_y - 2, door_y))
            if 0 < door_y < h - 1:
                layout[door_y][mid_x] = DOOR
            door_y2 = mid_y + (h - mid_y) // 2 + rng.randint(-1, 1)
            door_y2 = max(mid_y + 2, min(h - 3, door_y2))
            if 0 < door_y2 < h - 1:
                layout[door_y2][mid_x] = DOOR
        rooms = [
            (1, 1, mid_x - 1, mid_y - 1),          # NW
            (mid_x + 1, 1, w - 2 - mid_x, mid_y - 1),  # NE
            (1, mid_y + 1, mid_x - 1, h - 2 - mid_y),  # SW
            (mid_x + 1, mid_y + 1, w - 2 - mid_x, h - 2 - mid_y),  # SE
        ]
    elif w >= 6:
        # Vertical split only
        mid_x = w // 2
        for dy in range(1, h - 1):
            if layout[dy][mid_x] == FLOOR:
                layout[dy][mid_x] = WALL
        door_y = h // 2
        layout[door_y][mid_x] = DOOR
        rooms = [
            (1, 1, mid_x - 1, h - 2),
            (mid_x + 1, 1, w - 2 - mid_x, h - 2),
        ]
    else:
        rooms = [(1, 1, w - 2, h - 2)]

    # Furnish rooms with templates
    room_types = ["bedroom", "study", "storage", "living"]
    rng.shuffle(room_types)
    furniture_map = {
        "bedroom": [(BED, 0.3, 0.3), (CHEST, 0.7, 0.3), (TABLE, 0.3, 0.7)],
        "study": [(TABLE, 0.5, 0.4), (BOOKSHELF, 0.2, 0.2), (BOOKSHELF, 0.8, 0.2)],
        "storage": [(BARREL, 0.3, 0.3), (BARREL, 0.7, 0.3), (CHEST, 0.5, 0.7)],
        "living": [(TABLE, 0.5, 0.5), (FIREPLACE, 0.5, 0.2)],
    }

    for i, (rx, ry, rw, rh) in enumerate(rooms):
        if rw < 2 or rh < 2:
            continue
        rtype = room_types[i % len(room_types)]
        for tile_type, fx, fy in furniture_map.get(rtype, []):
            tx = rx + max(0, min(rw - 1, int(fx * rw)))
            ty = ry + max(0, min(rh - 1, int(fy * rh)))
            if 0 < tx < w - 1 and 0 < ty < h - 1 and layout[ty][tx] == FLOOR:
                layout[ty][tx] = tile_type

    # Add windows on outer walls (upper floors)
    for dx in range(2, w - 2, 3):
        if layout[0][dx] == WALL:
            layout[0][dx] = WINDOW
        if layout[h - 1][dx] == WALL:
            layout[h - 1][dx] = WINDOW
    for dy in range(2, h - 2, 3):
        if layout[dy][0] == WALL:
            layout[dy][0] = WINDOW
        if layout[dy][w - 1] == WALL:
            layout[dy][w - 1] = WINDOW


def _add_underground_rooms(layout, w, h, depth, rng):
    """Add rooms and features to underground floors.

    Deeper levels are rougher and more dangerous.
    """
    if w >= 8 and h >= 8:
        # Create an irregular room layout
        mid_x = w // 2 + rng.randint(-1, 1)
        # One thick wall creating two rooms
        for dy in range(1, h - 1):
            if layout[dy][mid_x] == FLOOR:
                layout[dy][mid_x] = WALL
            if mid_x + 1 < w - 1 and layout[dy][mid_x + 1] == FLOOR:
                layout[dy][mid_x + 1] = WALL
        # Door between rooms
        door_y = h // 2
        layout[door_y][mid_x] = DOOR
        layout[door_y][mid_x + 1] = FLOOR

    # Storage and dungeon furniture
    items = [BARREL, BARREL, CHEST, BARREL, CHEST]
    if depth > 1:
        items += [CHEST, CHEST]  # more loot deeper down

    for item in items:
        for _ in range(10):
            fx = rng.randint(2, w - 3)
            fy = rng.randint(2, h - 3)
            if layout[fy][fx] == FLOOR:
                layout[fy][fx] = item
                break

    # Add a fireplace/torch for lighting
    for _ in range(5):
        fx = rng.randint(1, w - 2)
        fy = rng.randint(1, h - 2)
        if layout[fy][fx] == WALL:
            # Check adjacent floor
            has_floor = False
            for ddx, ddy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nx, ny = fx + ddx, fy + ddy
                if 0 < nx < w - 1 and 0 < ny < h - 1 and layout[ny][nx] == FLOOR:
                    has_floor = True
            if has_floor:
                layout[fy][fx] = FIREPLACE
                break


def _generate_settlement_buildings(sp, plan, rng: random.Random):
    """Generate building placement data using the SettlementPlanner.

    Uses medieval layout principles to place buildings in appropriate
    zones: market at center, temple on high ground, blacksmiths at
    the edge, tanners downstream, farms outside walls, etc.

    Storage buildings required by the storage system are guaranteed
    placement. Results are cached on the SettlementPlan.
    """
    from game.world.buildings import (BLUEPRINT_BY_KIND, STORAGE_BLUEPRINTS,
                                       get_building_for_settlement)
    from game.world.settlement_planner import SettlementPlanner
    from game.systems.storage import STORAGE_BUILDINGS, _meets_minimum

    # --- Use the planner to create a layout ---
    planner = SettlementPlanner()
    spec = getattr(sp, 'specialization', 'general')
    layout = planner.plan_settlement(
        sp.name, sp.kind, sp.x, sp.y, sp.radius, plan, rng,
        specialization=spec)

    # Store layout on the settlement plan for road/wall/farm stamping
    sp._layout = layout

    placed_rects = []  # (x, y, w, h) for collision checks

    def _finalize_building(use_bp, bx, by, bw, bh, storage_kind=None,
                           zone=""):
        """Register a building and generate NPC spawns."""
        placed_rects.append((bx, by, bw, bh))

        bname = use_bp.name
        if 'Tower' in bname or 'Keep' in bname or 'Castle' in bname or 'Palace' in bname:
            num_floors_up, num_floors_down = 2, 1
        elif 'Lighthouse' in bname:
            num_floors_up, num_floors_down = 3, 0
        elif 'Mine' in bname:
            num_floors_up, num_floors_down = 0, 2
        elif sp.kind in ('city', 'castle'):
            num_floors_up, num_floors_down = 1, 0
        else:
            num_floors_up, num_floors_down = 0, 0

        floors = {0: use_bp.tiles}
        for fl in range(1, num_floors_up + 1):
            floors[fl] = _generate_floor_layout(
                bw, bh, fl, rng, use_bp.tiles)
        for fl in range(-1, -num_floors_down - 1, -1):
            floors[fl] = _generate_floor_layout(
                bw, bh, fl, rng, use_bp.tiles)

        bld_data = {
            "kind": use_bp.kind,
            "name": use_bp.name,
            "x": bx, "y": by, "w": bw, "h": bh,
            "bp_tiles": use_bp.tiles,
            "floors": floors,
            "num_floors_up": num_floors_up,
            "num_floors_down": num_floors_down,
            "zone": zone,
        }
        if storage_kind:
            bld_data["storage_kind"] = storage_kind
        sp.buildings.append(bld_data)

        floor_positions = use_bp.get_floor_positions()
        for i in range(use_bp.npc_count):
            if floor_positions:
                fx, fy = rng.choice(floor_positions)
                sp.npc_spawns.append({
                    "x": float(bx + fx),
                    "y": float(by + fy),
                    "class": use_bp.npc_class or rng.choice(
                        ["Fighter", "Rogue", "Bard", "Cleric"]),
                    "race": sp.race,
                    "building": use_bp.name,
                })

    # --- Phase 1: place planned buildings from layout ---
    storage_kinds_placed = set()

    for pb in layout.buildings:
        bp = BLUEPRINT_BY_KIND.get(pb.kind)
        if bp is None:
            continue

        # Match rotation: if planned dimensions differ, rotate
        use_bp = bp
        if (bp.width != pb.w or bp.height != pb.h):
            rotated = bp.rotated()
            if rotated.width == pb.w and rotated.height == pb.h:
                use_bp = rotated

        # Check if this building kind is a required storage building
        storage_kind = None
        for sb_name in STORAGE_BLUEPRINTS:
            if sb_name == pb.kind:
                storage_kind = sb_name
                storage_kinds_placed.add(sb_name)
                break

        _finalize_building(use_bp, pb.x, pb.y,
                           use_bp.width, use_bp.height,
                           storage_kind=storage_kind,
                           zone=pb.zone)

    # --- Phase 2: guarantee required storage buildings ---
    for sb_name, sb_def in STORAGE_BUILDINGS.items():
        if sb_name in storage_kinds_placed:
            continue
        if not _meets_minimum(sp.kind, sb_def["min_settlement"]):
            continue
        sb_bp = STORAGE_BLUEPRINTS.get(sb_name)
        if sb_bp is None:
            continue

        # Try to place this storage building
        for attempt in range(50):
            use_bp = sb_bp
            if rng.random() < 0.5:
                use_bp = sb_bp.rotated()
            bw, bh = use_bp.width, use_bp.height
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(5, sp.radius * 0.7)
            bx = int(sp.x + math.cos(angle) * dist - bw // 2)
            by = int(sp.y + math.sin(angle) * dist - bh // 2)

            overlap = any(
                not (bx + bw + 2 < px or bx > px + pw + 2 or
                     by + bh + 2 < py or by > py + ph + 2)
                for px, py, pw, ph in placed_rects
            )
            if overlap:
                continue

            _finalize_building(use_bp, bx, by, bw, bh,
                               storage_kind=sb_name, zone="storage")
            break


# ================================================================
# ROADS
# ================================================================

def _stamp_roads(chunk: Chunk, plan, x0: int, y0: int):
    """Stamp inter-settlement roads into the chunk."""
    roads = plan.roads_in_chunk(chunk.cx, chunk.cy, CHUNK_SIZE)
    if not roads:
        return

    tiles = chunk.tiles
    road_tile_map = {
        "king_road": COBBLESTONE,
        "paved_road": ROAD,
        "gravel_road": GRAVEL_ROAD,
        "dirt_track": DIRT_TRACK,
    }

    for road in roads:
        road_tile = road_tile_map.get(road.road_type, ROAD)
        road_width = {"king_road": 2, "paved_road": 1,
                      "gravel_road": 1, "dirt_track": 0}
        rw = road_width.get(road.road_type, 1)

        for i in range(len(road.waypoints) - 1):
            wx1, wy1 = road.waypoints[i]
            wx2, wy2 = road.waypoints[i + 1]

            for wx, wy in _bresenham(wx1, wy1, wx2, wy2):
                lx = wx - x0
                ly = wy - y0
                if 0 <= lx < CHUNK_SIZE and 0 <= ly < CHUNK_SIZE:
                    if tiles[ly, lx] not in (WALL, FLOOR, DOOR, WATER):
                        tiles[ly, lx] = road_tile
                    # Road width
                    for d in range(1, rw + 1):
                        for dlx, dly in [(d, 0), (-d, 0), (0, d), (0, -d)]:
                            nlx, nly = lx + dlx, ly + dly
                            if (0 <= nlx < CHUNK_SIZE and
                                    0 <= nly < CHUNK_SIZE):
                                if tiles[nly, nlx] not in (
                                        WALL, FLOOR, DOOR, WATER):
                                    tiles[nly, nlx] = road_tile


# ================================================================
# RESOURCES
# ================================================================

def _place_resources(chunk: Chunk, plan, x0: int, y0: int,
                     rng: random.Random):
    """Scatter resource nodes based on local terrain (numpy-vectorized)."""
    tiles = chunk.tiles
    S = CHUNK_SIZE

    # Use numpy seeded RNG for vectorized random generation
    np_rng = np.random.RandomState(rng.randint(0, 2**31 - 1))
    rand_map = np_rng.random((S, S)).astype(np.float32)

    # Clamp out-of-bounds rows/cols
    max_ly = min(S, plan.height - y0)
    max_lx = min(S, plan.width - x0)
    if max_ly <= 0 or max_lx <= 0:
        return

    # Work on valid sub-region
    t = tiles[:max_ly, :max_lx]
    r = rand_map[:max_ly, :max_lx]

    # --- Forest resources (2% herb, 3% fruit tree) ---
    forest_mask = (t == FOREST)
    t[forest_mask & (r < 0.02)] = HERB_PATCH
    t[forest_mask & (r >= 0.02) & (r < 0.05)] = FRUIT_TREE

    # --- Dense forest (5% mushrooms, 2% fallen tree) ---
    dense_mask = (t == DENSE_FOREST)
    t[dense_mask & (r < 0.05)] = MUSHROOMS
    t[dense_mask & (r >= 0.05) & (r < 0.07)] = FALLEN_TREE

    # --- Swamp flora (4% herb, 3% fallen tree, 3% mushrooms) ---
    swamp_mask = (t == SWAMP)
    t[swamp_mask & (r < 0.04)] = HERB_PATCH
    t[swamp_mask & (r >= 0.04) & (r < 0.07)] = FALLEN_TREE
    t[swamp_mask & (r >= 0.07) & (r < 0.10)] = MUSHROOMS

    # --- Desert flora (2% stump/cacti) ---
    sand_mask = (t == SAND)
    t[sand_mask & (r < 0.02)] = TREE_STUMP

    # --- Grassland adjacency checks (vectorized via shifted arrays) ---
    grass_mask = (t == GRASS)
    if np.any(grass_mask):
        # Build adjacency masks using shifts
        forest_tiles = np.zeros((max_ly, max_lx), dtype=bool)
        mountain_tiles = np.zeros((max_ly, max_lx), dtype=bool)
        water_tiles = np.zeros((max_ly, max_lx), dtype=bool)

        forest_set = {FOREST, DENSE_FOREST}
        water_set = {WATER, SHALLOW_WATER}

        for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            # Shifted view of tiles
            sy0 = max(0, dy)
            sy1 = max_ly + min(0, dy)
            sx0 = max(0, dx)
            sx1 = max_lx + min(0, dx)
            ty0 = max(0, -dy)
            ty1 = max_ly + min(0, -dy)
            tx0 = max(0, -dx)
            tx1 = max_lx + min(0, -dx)
            if sy1 <= sy0 or sx1 <= sx0:
                continue
            shifted = t[sy0:sy1, sx0:sx1]
            # Check adjacency types
            for ft in forest_set:
                forest_tiles[ty0:ty1, tx0:tx1] |= (shifted == ft)
            mountain_tiles[ty0:ty1, tx0:tx1] |= (shifted == MOUNTAIN)
            for wt in water_set:
                water_tiles[ty0:ty1, tx0:tx1] |= (shifted == wt)

        t[grass_mask & forest_tiles & (r < 0.02)] = BERRY_BUSH
        t[grass_mask & mountain_tiles & ~forest_tiles & (r < 0.25)] = ROCKY_GROUND
        t[grass_mask & water_tiles & ~forest_tiles & ~mountain_tiles & (r < 0.08)] = MARSH
        # Wildflowers for remaining grass (use a second random to avoid correlation)
        r2 = np_rng.random((max_ly, max_lx)).astype(np.float32)
        still_grass = (t == GRASS)
        t[still_grass & (r2 < 0.02)] = FLOWER_BED

    # --- Ore near mountains (need adjacency, keep Python for direction preference) ---
    mountain_mask = (t == MOUNTAIN) & (r < 0.08)
    ore_ys, ore_xs = np.where(mountain_mask)
    ore_targets = {GRASS, SAND, ROCKY_GROUND}
    for ly, lx in zip(ore_ys, ore_xs):
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nlx, nly = int(lx + dx), int(ly + dy)
            if (0 <= nlx < max_lx and 0 <= nly < max_ly and
                    t[nly, nlx] in ore_targets):
                t[nly, nlx] = ORE_VEIN
                break

    # --- Shallow water near shores ---
    water_mask = (t == WATER)
    if np.any(water_mask):
        # has_land is True if ANY neighbor is non-water
        has_land = np.zeros((max_ly, max_lx), dtype=bool)
        for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            sy0 = max(0, dy)
            sy1 = max_ly + min(0, dy)
            sx0 = max(0, dx)
            sx1 = max_lx + min(0, dx)
            ty0 = max(0, -dy)
            ty1 = max_ly + min(0, -dy)
            tx0 = max(0, -dx)
            tx1 = max_lx + min(0, -dx)
            if sy1 <= sy0 or sx1 <= sx0:
                continue
            shifted = t[sy0:sy1, sx0:sx1]
            is_land = (shifted != WATER) & (shifted != SHALLOW_WATER)
            has_land[ty0:ty1, tx0:tx1] |= is_land
        t[water_mask & has_land & (r < 0.3)] = SHALLOW_WATER


# ================================================================
# HELPERS
# ================================================================

def _bresenham(x0: int, y0: int, x1: int, y1: int):
    """Yield integer coordinates along a line from (x0,y0) to (x1,y1)."""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    while True:
        yield x0, y0
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
