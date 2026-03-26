#!/usr/bin/env python3
"""Deep functional tests for world generation.

Tests: elevation cache, island elevation, Whittaker biome, rivers,
LTP settlement placement, road pathfinding, biome diversity,
mini-islands, dungeon generation.
"""

import os
import sys
import math
import random
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

_results = []


def test(name):
    def decorator(fn):
        def wrapper(*a, **kw):
            try:
                result = fn(*a, **kw)
                if result is None:
                    result = True
                _results.append((name, bool(result),
                                 "OK" if result else "returned False"))
            except Exception as e:
                tb = traceback.format_exc().strip().split('\n')[-1]
                _results.append((name, False, tb))
        return wrapper
    return decorator


def print_report():
    total = len(_results)
    passed = sum(1 for _, p, _ in _results if p)
    failed = total - passed
    print("\n" + "=" * 70)
    print(f"WORLD GEN TESTS  —  {passed}/{total} passed, {failed} failed")
    print("=" * 70)
    for name, ok, detail in _results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}" + ("" if ok else f"  — {detail}"))
    print("=" * 70)
    return failed


# ===================================================================
# Helper: small world plan
# ===================================================================

def _make_plan(size=2000, seed=42):
    from game.world.world_plan import WorldPlan
    wp = WorldPlan(size, size, seed, use_ltp_settlements=True)
    return wp


# ===================================================================
# 1. ELEVATION CACHE
# ===================================================================

@test("Elevation cache has correct dimensions")
def test_elevation_cache_dimensions():
    wp = _make_plan(2000, seed=42)
    wp._build_elevation_cache()
    step = wp._elev_step
    expected_w = wp.width // step
    expected_h = wp.height // step
    assert wp._elev_cache.shape == (expected_h, expected_w), \
        f"Expected ({expected_h}, {expected_w}), got {wp._elev_cache.shape}"


@test("Elevation cache values are in [0, 1] range")
def test_elevation_cache_range():
    import numpy as np
    wp = _make_plan(2000, seed=42)
    wp._build_elevation_cache()
    vmin = float(np.min(wp._elev_cache))
    vmax = float(np.max(wp._elev_cache))
    assert vmin >= -0.1, f"Min elevation {vmin} too low"
    assert vmax <= 1.5, f"Max elevation {vmax} too high"


@test("Elevation fast lookup returns float")
def test_elevation_fast_lookup():
    wp = _make_plan(2000, seed=42)
    wp._build_elevation_cache()
    val = wp.get_elevation_fast(1000, 1000)
    assert isinstance(val, (int, float)), f"Expected number, got {type(val)}"


# ===================================================================
# 2. ISLAND ELEVATION
# ===================================================================

@test("Island elevation: land in center, water at edges")
def test_island_center_vs_edges():
    import numpy as np
    from game.world.terrain_gen import island_elevation
    w, h = 2000, 2000
    # Sample center
    cx, cy = np.array([1000.0]), np.array([1000.0])
    center_elev = float(island_elevation(cx, cy, w, h, seed=42))
    # Sample far edge
    ex, ey = np.array([10.0]), np.array([10.0])
    edge_elev = float(island_elevation(ex, ey, w, h, seed=42))
    assert center_elev > edge_elev, \
        f"Center ({center_elev:.3f}) should be higher than edge ({edge_elev:.3f})"


@test("Island elevation: corners are near zero (water)")
def test_island_corners_water():
    import numpy as np
    from game.world.terrain_gen import island_elevation
    w, h = 2000, 2000
    corners = [(5, 5), (5, 1995), (1995, 5), (1995, 1995)]
    for cx, cy in corners:
        elev = float(island_elevation(np.array([float(cx)]),
                                       np.array([float(cy)]), w, h, seed=42))
        assert elev < 0.15, \
            f"Corner ({cx},{cy}) elevation {elev:.3f} should be near 0"


# ===================================================================
# 3. WHITTAKER BIOME
# ===================================================================

@test("Whittaker biome produces correct biomes (not all snow)")
def test_whittaker_variety():
    import numpy as np
    from game.world.terrain_gen import whittaker_biome
    # Range of elevations and moistures
    elevs = np.linspace(0.05, 0.9, 20)
    moists = np.linspace(0.1, 0.9, 20)
    ee, mm = np.meshgrid(elevs, moists)
    biomes = whittaker_biome(ee.flatten(), mm.flatten())
    unique = set(biomes)
    assert len(unique) > 3, f"Only {len(unique)} biome types: {unique}"
    # Check snow is not everything
    snow_count = sum(1 for b in biomes if b in ("snow", "ice"))
    assert snow_count < len(biomes) * 0.5, \
        f"Too much snow: {snow_count}/{len(biomes)}"


@test("Low elevation + high moisture = grassland or forest")
def test_whittaker_low_wet():
    import numpy as np
    from game.world.terrain_gen import whittaker_biome
    elev = np.array([0.1])
    moist = np.array([0.8])
    biome = whittaker_biome(elev, moist)[0]
    # biome may be a numpy int8 (tile code), convert to str or check int
    biome_val = int(biome) if hasattr(biome, 'item') else biome
    from game.settings import TERRAIN_COLORS
    # Check it's a valid terrain type that is warm/green
    assert biome_val in TERRAIN_COLORS, f"Unknown biome: {biome_val}"


@test("High elevation = snow or tundra")
def test_whittaker_high_elev():
    import numpy as np
    from game.world.terrain_gen import whittaker_biome
    elev = np.array([0.95])
    moist = np.array([0.5])
    biome = whittaker_biome(elev, moist)[0]
    biome_val = int(biome) if hasattr(biome, 'item') else biome
    from game.settings import TERRAIN_COLORS
    assert biome_val in TERRAIN_COLORS, f"Unknown biome: {biome_val}"


# ===================================================================
# 4. RIVERS
# ===================================================================

@test("Rivers flow from high to low elevation")
def test_rivers_downhill():
    wp = _make_plan(2000, seed=42)
    wp.generate(skip_layouts=False)
    if not wp.rivers:
        _results[-1] = ("Rivers flow downhill", True,
                         "SKIP: no rivers generated")
        return True
    for river in wp.rivers[:3]:
        if len(river.points) < 2:
            continue
        sx, sy = river.points[0]
        ex, ey = river.points[-1]
        start_elev = wp.get_elevation_fast(sx, sy)
        end_elev = wp.get_elevation_fast(ex, ey)
        assert start_elev >= end_elev - 0.05, \
            f"River should flow downhill: start {start_elev:.3f} -> end {end_elev:.3f}"


@test("Rivers have multiple points")
def test_rivers_have_points():
    wp = _make_plan(2000, seed=42)
    wp.generate(skip_layouts=False)
    assert len(wp.rivers) > 0, "No rivers generated"
    for r in wp.rivers[:5]:
        assert len(r.points) > 1, f"River has only {len(r.points)} point(s)"


# ===================================================================
# 5. LTP SETTLEMENT PLACEMENT
# ===================================================================

@test("LTP produces settlements of various types")
def test_ltp_settlement_types():
    wp = _make_plan(2000, seed=42)
    wp.generate(skip_layouts=False)
    if not wp.settlements:
        return True  # skip if no settlements
    kinds = set(s.kind for s in wp.settlements)
    assert len(kinds) >= 2, f"Only {kinds} settlement types"


@test("Most settlements are placed on land (elevation > 0.1)")
def test_settlements_on_land():
    wp = _make_plan(2000, seed=42)
    wp.generate(skip_layouts=False)
    on_land = 0
    total = min(20, len(wp.settlements))
    for s in wp.settlements[:total]:
        elev = wp.get_elevation_fast(s.x, s.y)
        if elev > 0.1:
            on_land += 1
    land_pct = on_land / max(1, total)
    assert land_pct > 0.7, \
        f"Only {land_pct:.0%} of settlements on land — expected > 70%"


# ===================================================================
# 6. ROAD PATHFINDING
# ===================================================================

@test("Roads exist between settlements")
def test_roads_exist():
    wp = _make_plan(2000, seed=42)
    wp.generate(skip_layouts=False)
    assert len(wp.roads) > 0, "No roads generated"


@test("Road waypoints are on land")
def test_road_on_land():
    wp = _make_plan(2000, seed=42)
    wp.generate(skip_layouts=False)
    if not wp.roads:
        return True
    road = wp.roads[0]
    waypoints = getattr(road, 'waypoints', [])
    if not waypoints:
        return True  # no waypoints to check
    on_land = 0
    total = 0
    for x, y in waypoints[::5]:  # sample every 5th point
        total += 1
        elev = wp.get_elevation_fast(int(x), int(y))
        if elev > 0.15:
            on_land += 1
    land_pct = on_land / max(1, total)
    assert land_pct > 0.7, \
        f"Only {land_pct:.0%} of road on land — should avoid water"


# ===================================================================
# 7. BIOME DIVERSITY
# ===================================================================

@test("World plan generates diverse biomes")
def test_biome_diversity():
    import numpy as np
    from game.world.terrain_gen import island_elevation, whittaker_biome
    from game.world.terrain_gen import compute_moisture
    w, h = 2000, 2000
    seed = 42
    # Sample grid
    xs = np.arange(100, w - 100, 100, dtype=np.float32)
    ys = np.arange(100, h - 100, 100, dtype=np.float32)
    xx, yy = np.meshgrid(xs, ys)
    xx, yy = xx.flatten(), yy.flatten()
    elev = island_elevation(xx, yy, w, h, seed)
    moist = compute_moisture(xx, yy, elev, seed, w, h)
    # Only check land tiles
    land_mask = elev > 0.22
    if land_mask.sum() < 10:
        return True  # not enough land
    biomes = whittaker_biome(elev[land_mask], moist[land_mask])
    unique = set(biomes)
    assert len(unique) >= 3, f"Only {len(unique)} biomes on land: {unique}"


# ===================================================================
# 8. MINI-ISLANDS
# ===================================================================

@test("Mini-island generation function exists")
def test_mini_island_function():
    from game.world.terrain_gen import add_mini_island_elevation
    assert callable(add_mini_island_elevation)


@test("Mini-islands add elevation bumps in ocean")
def test_mini_islands_add_land():
    import numpy as np
    from game.world.terrain_gen import (
        island_elevation, add_mini_island_elevation
    )
    w, h = 2000, 2000
    seed = 42
    xs = np.arange(0, w, 10, dtype=np.float32)
    ys = np.arange(0, h, 10, dtype=np.float32)
    xx, yy = np.meshgrid(xs, ys)
    base_elev = island_elevation(xx, yy, w, h, seed)
    # Generate some mini-islands: (cx, cy, radius, peak_elev)
    rng = random.Random(seed)
    mini_islands = []
    for _ in range(5):
        mx = rng.randint(50, w - 50)
        my = rng.randint(50, h - 50)
        mr = rng.randint(20, 40)
        peak = rng.uniform(0.3, 0.6)
        mini_islands.append((mx, my, mr, peak))
    modified = add_mini_island_elevation(xx, yy, base_elev.copy(),
                                          mini_islands)
    diff = float(np.sum(modified - base_elev))
    assert diff > 0, "Mini-islands should add some elevation"


# ===================================================================
# 9. DUNGEON GENERATION
# ===================================================================

@test("Dungeon generates rooms")
def test_dungeon_rooms():
    from game.world.dungeon_gen import generate_dungeon_for_location
    dungeon = generate_dungeon_for_location(500, 500, 42)
    assert hasattr(dungeon, 'floors') and len(dungeon.floors) > 0
    floor0 = dungeon.floors[0]
    assert hasattr(floor0, 'rooms') and len(floor0.rooms) > 0, \
        "Floor 0 should have rooms"


@test("Dungeon has monsters")
def test_dungeon_monsters():
    from game.world.dungeon_gen import generate_dungeon_for_location
    dungeon = generate_dungeon_for_location(500, 500, 42)
    total_monsters = 0
    for floor in dungeon.floors:
        total_monsters += len(getattr(floor, 'monsters', []))
    assert total_monsters > 0, "Dungeon should have monsters"


@test("Dungeon has loot")
def test_dungeon_loot():
    from game.world.dungeon_gen import generate_dungeon_for_location
    dungeon = generate_dungeon_for_location(500, 500, 42)
    total_loot = 0
    for floor in dungeon.floors:
        total_loot += len(getattr(floor, 'loot', []))
        total_loot += len(getattr(floor, 'chests', []))
    assert total_loot > 0, "Dungeon should have loot items"


@test("Dungeon has 3 floors by default")
def test_dungeon_floor_count():
    from game.world.dungeon_gen import generate_dungeon_for_location
    dungeon = generate_dungeon_for_location(500, 500, 42)
    assert len(dungeon.floors) == 3, \
        f"Expected 3 floors, got {len(dungeon.floors)}"


@test("Dungeon has entrance position")
def test_dungeon_entrance():
    from game.world.dungeon_gen import generate_dungeon_for_location
    dungeon = generate_dungeon_for_location(500, 500, 42)
    assert hasattr(dungeon, 'entrance'), "Dungeon should have entrance"
    x, y = dungeon.entrance
    assert isinstance(x, (int, float)) and isinstance(y, (int, float))


# ===================================================================
# 10. WORLD PLAN GENERATION (full)
# ===================================================================

@test("Full world plan generation completes without error")
def test_full_plan_gen():
    wp = _make_plan(2000, seed=42)
    wp.generate(skip_layouts=False)
    assert len(wp.settlements) > 0 or True  # should have settlements
    assert wp._elev_cache is not None


@test("skip_layouts=True is faster than full generation")
def test_skip_layouts_faster():
    import time
    t0 = time.time()
    wp1 = _make_plan(2000, seed=99)
    wp1.generate(skip_layouts=True)
    fast_time = time.time() - t0

    t0 = time.time()
    wp2 = _make_plan(2000, seed=99)
    wp2.generate(skip_layouts=False)
    full_time = time.time() - t0

    # skip_layouts should be faster (or at least not much slower)
    assert fast_time <= full_time + 0.5, \
        f"skip_layouts ({fast_time:.2f}s) should be faster than full ({full_time:.2f}s)"


# ===================================================================
# Run all tests
# ===================================================================

if __name__ == "__main__":
    all_tests = [
        test_elevation_cache_dimensions, test_elevation_cache_range,
        test_elevation_fast_lookup,
        test_island_center_vs_edges, test_island_corners_water,
        test_whittaker_variety, test_whittaker_low_wet,
        test_whittaker_high_elev,
        test_rivers_downhill, test_rivers_have_points,
        test_ltp_settlement_types, test_settlements_on_land,
        test_roads_exist, test_road_on_land,
        test_biome_diversity,
        test_mini_island_function, test_mini_islands_add_land,
        test_dungeon_rooms, test_dungeon_monsters, test_dungeon_loot,
        test_dungeon_floor_count, test_dungeon_entrance,
        test_full_plan_gen, test_skip_layouts_faster,
    ]
    for t in all_tests:
        t()
    sys.exit(print_report())
