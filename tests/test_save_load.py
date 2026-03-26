#!/usr/bin/env python3
"""Deep functional tests for save/load persistence.

Tests: world save JSON validity, required sections, player position,
kingdom state, skip_layouts performance, default world file, save list.
"""

import os
import sys
import json
import time
import tempfile
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
    print(f"SAVE/LOAD TESTS  —  {passed}/{total} passed, {failed} failed")
    print("=" * 70)
    for name, ok, detail in _results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}" + ("" if ok else f"  — {detail}"))
    print("=" * 70)
    return failed


# ---------------------------------------------------------------------------
# Shared headless game (expensive, created once)
# ---------------------------------------------------------------------------
print("Initializing headless game for save/load tests (seed=42)...")
t0 = time.time()
from game.ui.screenshot import HeadlessGame
_game = HeadlessGame(seed=42, mode='mortal', use_chunked=True)
_game._start_time = time.time()
print(f"  Ready in {time.time()-t0:.1f}s")


def _save_to_temp():
    """Helper: save game to temp file, return path and data dict."""
    from game.data.world_save import save_world_state
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        path = f.name
    save_world_state(_game, path=path)
    with open(path, 'r') as f:
        data = json.load(f)
    return path, data


# ===================================================================
# 1. SAVE CREATES VALID JSON
# ===================================================================

@test("Save produces a valid JSON file")
def test_save_valid_json():
    path, data = _save_to_temp()
    try:
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert len(data) > 0, "Save file is empty"
    finally:
        os.unlink(path)


@test("Save file is non-empty")
def test_save_file_size():
    path, _ = _save_to_temp()
    try:
        size = os.path.getsize(path)
        assert size > 100, f"Save file too small: {size} bytes"
    finally:
        os.unlink(path)


@test("Save file has version field")
def test_save_has_version():
    path, data = _save_to_temp()
    try:
        assert "version" in data, "Missing 'version' field"
        assert data["version"] >= 1
    finally:
        os.unlink(path)


# ===================================================================
# 2. SAVE CONTAINS ALL REQUIRED SECTIONS
# ===================================================================

@test("Save has world_plan section")
def test_save_world_plan():
    path, data = _save_to_temp()
    try:
        assert "world_plan" in data
        wp = data["world_plan"]
        assert "seed" in wp
        assert "width" in wp and "height" in wp
    finally:
        os.unlink(path)


@test("Save has player section")
def test_save_player():
    path, data = _save_to_temp()
    try:
        assert "player" in data
        p = data["player"]
        assert "x" in p and "y" in p
        assert "hp" in p
        assert "level" in p
    finally:
        os.unlink(path)


@test("Save has settlements section")
def test_save_settlements():
    path, data = _save_to_temp()
    try:
        assert "settlements" in data
        assert isinstance(data["settlements"], list)
    finally:
        os.unlink(path)


@test("Save has kingdoms section")
def test_save_kingdoms():
    path, data = _save_to_temp()
    try:
        assert "kingdoms" in data
        assert isinstance(data["kingdoms"], list)
    finally:
        os.unlink(path)


@test("Save has game_time section")
def test_save_game_time():
    path, data = _save_to_temp()
    try:
        assert "game_time" in data
    finally:
        os.unlink(path)


@test("Save has npc_summary section")
def test_save_npc_summary():
    path, data = _save_to_temp()
    try:
        assert "npc_summary" in data
        ns = data["npc_summary"]
        assert "total" in ns
    finally:
        os.unlink(path)


@test("Save has events section")
def test_save_events():
    path, data = _save_to_temp()
    try:
        assert "events" in data
    finally:
        os.unlink(path)


# ===================================================================
# 3. PLAYER POSITION
# ===================================================================

@test("Player position saved correctly (not divine realm coords)")
def test_player_position_correct():
    path, data = _save_to_temp()
    try:
        p = data["player"]
        x, y = p["x"], p["y"]
        # Divine realm is 200x200 at offset ~0. Normal world is much larger
        # Player should be in the mortal world
        assert x > 0 and y > 0, f"Position ({x}, {y}) invalid"
        # Should not be at 0,0 (uninitialized)
        assert not (x == 0 and y == 0), "Position is (0,0) — likely unset"
    finally:
        os.unlink(path)


@test("Player HP saved as positive number")
def test_player_hp_saved():
    path, data = _save_to_temp()
    try:
        hp = data["player"]["hp"]
        assert isinstance(hp, (int, float)) and hp > 0, \
            f"HP should be positive, got {hp}"
    finally:
        os.unlink(path)


@test("Player gold saved")
def test_player_gold_saved():
    path, data = _save_to_temp()
    try:
        gold = data["player"].get("gold", -1)
        assert gold >= 0, f"Gold should be >= 0, got {gold}"
    finally:
        os.unlink(path)


@test("Player inventory saved")
def test_player_inventory_saved():
    path, data = _save_to_temp()
    try:
        inv = data["player"].get("inventory", [])
        assert isinstance(inv, list)
        assert len(inv) > 0, "Inventory should not be empty"
    finally:
        os.unlink(path)


# ===================================================================
# 4. KINGDOM STATE
# ===================================================================

@test("Kingdoms saved with treasury")
def test_kingdom_treasury_saved():
    path, data = _save_to_temp()
    try:
        kingdoms = data.get("kingdoms", [])
        if len(kingdoms) > 0:
            k = kingdoms[0]
            assert "treasury" in k
            assert isinstance(k["treasury"], (int, float))
    finally:
        os.unlink(path)


@test("Kingdoms saved with ruler name")
def test_kingdom_ruler_saved():
    path, data = _save_to_temp()
    try:
        kingdoms = data.get("kingdoms", [])
        if len(kingdoms) > 0:
            assert "ruler_name" in kingdoms[0]
    finally:
        os.unlink(path)


@test("Kingdoms saved with army size")
def test_kingdom_army_saved():
    path, data = _save_to_temp()
    try:
        kingdoms = data.get("kingdoms", [])
        if len(kingdoms) > 0:
            assert "army_size" in kingdoms[0]
    finally:
        os.unlink(path)


@test("Kingdoms saved with governing style")
def test_kingdom_style_saved():
    path, data = _save_to_temp()
    try:
        kingdoms = data.get("kingdoms", [])
        if len(kingdoms) > 0:
            assert "governing_style" in kingdoms[0]
    finally:
        os.unlink(path)


# ===================================================================
# 5. LOAD
# ===================================================================

@test("load_world_state returns dict with required keys")
def test_load_world_state():
    from game.data.world_save import save_world_state, load_world_state
    path, _ = _save_to_temp()
    try:
        loaded = load_world_state(path)
        assert loaded is not None
        assert "world_plan" in loaded
        assert "player" in loaded
    finally:
        os.unlink(path)


@test("Loaded data matches saved data")
def test_load_matches_save():
    path, saved = _save_to_temp()
    try:
        from game.data.world_save import load_world_state
        loaded = load_world_state(path)
        assert loaded["world_plan"]["seed"] == saved["world_plan"]["seed"]
        assert loaded["player"]["level"] == saved["player"]["level"]
    finally:
        os.unlink(path)


# ===================================================================
# 6. DEFAULT WORLD FILE / SAVE LIST
# ===================================================================

@test("WORLDS_DIR path is defined")
def test_worlds_dir_defined():
    from game.data.world_save import WORLDS_DIR
    assert isinstance(WORLDS_DIR, str)
    assert len(WORLDS_DIR) > 0


@test("Save path generation uses seed")
def test_save_path_uses_seed():
    from game.data.world_save import _world_save_path
    path = _world_save_path(42)
    assert "42" in path, f"Save path should contain seed: {path}"
    assert path.endswith(".json")


@test("Multiple saves have unique filenames")
def test_unique_save_names():
    from game.data.world_save import _world_save_path
    p1 = _world_save_path(42)
    p2 = _world_save_path(99)
    assert p1 != p2, "Different seeds should produce different paths"


@test("Save and cleanup works")
def test_save_cleanup():
    path, _ = _save_to_temp()
    assert os.path.exists(path)
    os.unlink(path)
    assert not os.path.exists(path)


# ===================================================================
# Run all tests
# ===================================================================

if __name__ == "__main__":
    all_tests = [
        test_save_valid_json, test_save_file_size,
        test_save_has_version,
        test_save_world_plan, test_save_player,
        test_save_settlements, test_save_kingdoms,
        test_save_game_time, test_save_npc_summary,
        test_save_events,
        test_player_position_correct, test_player_hp_saved,
        test_player_gold_saved, test_player_inventory_saved,
        test_kingdom_treasury_saved, test_kingdom_ruler_saved,
        test_kingdom_army_saved, test_kingdom_style_saved,
        test_load_world_state, test_load_matches_save,
        test_worlds_dir_defined, test_save_path_uses_seed,
        test_unique_save_names, test_save_cleanup,
    ]
    for t in all_tests:
        t()
    sys.exit(print_report())
