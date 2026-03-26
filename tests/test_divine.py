#!/usr/bin/env python3
"""Deep functional tests for divine/god systems.

Tests: divine realm generation, god NPCs/pantheon, disguise system,
disguise templates, divine realm transition, smite, viewing pool,
portal, god dashboard.
"""

import os
import sys
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
    print(f"DIVINE TESTS  —  {passed}/{total} passed, {failed} failed")
    print("=" * 70)
    for name, ok, detail in _results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}" + ("" if ok else f"  — {detail}"))
    print("=" * 70)
    return failed


# ===================================================================
# 1. DIVINE REALM GENERATION
# ===================================================================

@test("Divine realm generates dict with required keys")
def test_realm_has_keys():
    from game.world.divine_realm import generate_divine_realm
    realm = generate_divine_realm(seed=42)
    assert isinstance(realm, dict)
    required = ["tiles", "structures", "god_spawns", "portal_pos", "pool_pos"]
    for key in required:
        assert key in realm, f"Missing key: {key}"


@test("Divine realm has correct tile dimensions (200x200)")
def test_realm_tile_size():
    from game.world.divine_realm import generate_divine_realm, REALM_SIZE
    realm = generate_divine_realm(seed=42)
    tiles = realm["tiles"]
    assert len(tiles) == REALM_SIZE, \
        f"Expected {REALM_SIZE} rows, got {len(tiles)}"
    assert len(tiles[0]) == REALM_SIZE, \
        f"Expected {REALM_SIZE} cols, got {len(tiles[0])}"


@test("Divine realm generates structures (6+)")
def test_realm_structure_count():
    from game.world.divine_realm import generate_divine_realm
    realm = generate_divine_realm(seed=42)
    structs = realm["structures"]
    assert len(structs) >= 6, \
        f"Expected 6+ structures, got {len(structs)}"


@test("Divine realm has god spawn points")
def test_realm_god_spawns():
    from game.world.divine_realm import generate_divine_realm
    realm = generate_divine_realm(seed=42)
    spawns = realm["god_spawns"]
    assert len(spawns) > 0, "No god spawn points"
    for s in spawns:
        assert "name" in s and "x" in s and "y" in s


@test("Divine realm has portal position")
def test_realm_portal():
    from game.world.divine_realm import generate_divine_realm
    realm = generate_divine_realm(seed=42)
    px, py = realm["portal_pos"]
    assert isinstance(px, (int, float))
    assert isinstance(py, (int, float))


@test("Divine realm has viewing pool position")
def test_realm_pool():
    from game.world.divine_realm import generate_divine_realm
    realm = generate_divine_realm(seed=42)
    px, py = realm["pool_pos"]
    assert isinstance(px, (int, float))
    assert isinstance(py, (int, float))


# ===================================================================
# 2. GOD NPCs / PANTHEON
# ===================================================================

@test("Default pantheon has 7 gods")
def test_pantheon_count():
    from game.systems.pantheon import DEFAULT_PANTHEON
    assert len(DEFAULT_PANTHEON) == 7, \
        f"Expected 7 gods, got {len(DEFAULT_PANTHEON)}"


@test("Pantheon includes Tharion (war)")
def test_pantheon_tharion():
    from game.systems.pantheon import DEFAULT_PANTHEON
    names = {g.name for g in DEFAULT_PANTHEON}
    assert "Tharion" in names


@test("Pantheon includes Sylvana (nature)")
def test_pantheon_sylvana():
    from game.systems.pantheon import DEFAULT_PANTHEON
    names = {g.name for g in DEFAULT_PANTHEON}
    assert "Sylvana" in names


@test("All 7 gods have correct names")
def test_all_god_names():
    from game.systems.pantheon import DEFAULT_PANTHEON
    expected = {"Tharion", "Sylvana", "Verithos", "Morwen",
                "Auriel", "Lyria", "Xaotl"}
    actual = {g.name for g in DEFAULT_PANTHEON}
    assert actual == expected, \
        f"Expected {expected}, got {actual}"


@test("Each god has a unique sphere/domain")
def test_god_domains_unique():
    from game.systems.pantheon import DEFAULT_PANTHEON
    domains = [g.sphere for g in DEFAULT_PANTHEON]
    assert len(set(domains)) == len(domains), \
        f"Duplicate domains: {domains}"


@test("Gods have personality traits")
def test_god_personalities():
    from game.systems.pantheon import DEFAULT_PANTHEON
    for g in DEFAULT_PANTHEON:
        assert len(g.personality) > 0, \
            f"{g.name} has no personality traits"


# ===================================================================
# 3. DISGUISE SYSTEM
# ===================================================================

@test("GodDisguiseManager initializes with no disguise")
def test_disguise_init():
    from game.systems.god_disguise import GodDisguiseManager
    from game.core.player import Player
    p = Player(100, 100, char_class="Fighter")
    p.name = "TestGod"
    gdm = GodDisguiseManager(p)
    assert gdm.current_disguise is None


@test("set_disguise applies template")
def test_set_disguise():
    from game.systems.god_disguise import GodDisguiseManager
    from game.core.player import Player
    p = Player(100, 100, char_class="Fighter")
    p.name = "TestGod"
    gdm = GodDisguiseManager(p)
    success = gdm.set_disguise("wandering_merchant")
    assert success is True
    assert gdm.current_disguise is not None
    assert gdm.current_disguise.form_type == "humanoid"


@test("set_disguise with invalid template returns False")
def test_invalid_disguise():
    from game.systems.god_disguise import GodDisguiseManager
    from game.core.player import Player
    p = Player(100, 100)
    p.name = "TestGod"
    gdm = GodDisguiseManager(p)
    result = gdm.set_disguise("nonexistent_template")
    assert result is False
    assert gdm.current_disguise is None


# ===================================================================
# 4. DISGUISE TEMPLATES
# ===================================================================

@test("All disguise templates have valid form_type")
def test_template_form_types():
    from game.systems.god_disguise import DISGUISE_TEMPLATES
    valid_types = {"humanoid", "creature", "npc", "invisible"}
    for name, d in DISGUISE_TEMPLATES.items():
        assert d.form_type in valid_types, \
            f"Template '{name}' has invalid form_type: {d.form_type}"


@test("Disguise templates have required color tuples")
def test_template_colors():
    from game.systems.god_disguise import DISGUISE_TEMPLATES
    for name, d in DISGUISE_TEMPLATES.items():
        assert len(d.body_color) == 3, \
            f"Template '{name}' body_color invalid: {d.body_color}"
        assert len(d.clothing_color) == 3
        assert len(d.hair_color) == 3


@test("At least 5 disguise templates available")
def test_template_count():
    from game.systems.god_disguise import DISGUISE_TEMPLATES
    assert len(DISGUISE_TEMPLATES) >= 5, \
        f"Expected 5+ templates, got {len(DISGUISE_TEMPLATES)}"


@test("Disguise templates have valid races")
def test_template_races():
    from game.systems.god_disguise import DISGUISE_TEMPLATES
    from game.data.dnd import RACE_NAMES
    valid_races = set(RACE_NAMES) | {"God"}  # God is valid for true_form
    for name, d in DISGUISE_TEMPLATES.items():
        if d.form_type == "humanoid":
            assert d.race in valid_races, \
                f"Template '{name}' has invalid race: {d.race}"


# ===================================================================
# 5. DIVINE REALM TRANSITION
# ===================================================================

@test("Player position can be saved/restored for realm transition")
def test_position_save_restore():
    from game.core.player import Player
    p = Player(500, 600)
    # Save mortal position
    saved_x, saved_y = p.x, p.y
    # Move to divine realm coords
    p.x, p.y = 100, 100
    assert p.x == 100 and p.y == 100
    # Restore mortal position
    p.x, p.y = saved_x, saved_y
    assert p.x == 500 and p.y == 600


# ===================================================================
# 6. SMITE
# ===================================================================

@test("Smite miracle defined with damage effect")
def test_smite_miracle():
    from game.systems.pantheon import MIRACLES
    assert "smite" in MIRACLES
    smite = MIRACLES["smite"]
    assert smite["effect"] == "damage_target"
    assert smite["cost"] > 0


@test("Smite spheres include war")
def test_smite_spheres():
    from game.systems.pantheon import MIRACLES
    assert "war" in MIRACLES["smite"]["spheres"]


# ===================================================================
# 7. VIEWING POOL
# ===================================================================

@test("Viewing pool is at center of divine realm")
def test_pool_at_center():
    from game.world.divine_realm import (
        generate_divine_realm, CENTER
    )
    realm = generate_divine_realm(seed=42)
    px, py = realm["pool_pos"]
    # Pool should be near center
    assert abs(px - CENTER) < 20, f"Pool x={px}, center={CENTER}"
    assert abs(py - CENTER) < 20, f"Pool y={py}, center={CENTER}"


@test("Viewing pool tiles are divine water")
def test_pool_tiles():
    from game.world.divine_realm import (
        generate_divine_realm, CENTER, DIVINE_WATER
    )
    realm = generate_divine_realm(seed=42)
    tiles = realm["tiles"]
    # Center should be divine water
    assert tiles[CENTER][CENTER] == DIVINE_WATER, \
        f"Center tile should be DIVINE_WATER, got {tiles[CENTER][CENTER]}"


# ===================================================================
# 8. PORTAL
# ===================================================================

@test("Portal position is within realm bounds")
def test_portal_in_bounds():
    from game.world.divine_realm import (
        generate_divine_realm, REALM_SIZE
    )
    realm = generate_divine_realm(seed=42)
    px, py = realm["portal_pos"]
    assert 0 <= px < REALM_SIZE, f"Portal x={px} out of bounds"
    assert 0 <= py < REALM_SIZE, f"Portal y={py} out of bounds"


# ===================================================================
# 9. GOD DASHBOARD
# ===================================================================

@test("GodDashboard class exists and has handle_key")
def test_god_dashboard_class():
    from game.ui.god_dashboard import GodDashboard
    assert hasattr(GodDashboard, 'handle_key')


@test("GodDashboard can be instantiated with a mock game")
def test_god_dashboard_init():
    from game.ui.god_dashboard import GodDashboard

    class MockGame:
        pass
    gd = GodDashboard(MockGame())
    assert gd is not None


@test("PantheonSystem initializes with default gods")
def test_pantheon_system_init():
    from game.systems.pantheon import PantheonSystem
    ps = PantheonSystem()
    assert len(ps.gods) == 7
    assert "Tharion" in ps.gods


@test("Gods have inter-relationships after init")
def test_god_relationships():
    from game.systems.pantheon import PantheonSystem
    ps = PantheonSystem()
    tharion = ps.gods["Tharion"]
    assert len(tharion.relationships) > 0, \
        "Tharion should have relationships with other gods"


# ===================================================================
# Run all tests
# ===================================================================

if __name__ == "__main__":
    all_tests = [
        test_realm_has_keys, test_realm_tile_size,
        test_realm_structure_count, test_realm_god_spawns,
        test_realm_portal, test_realm_pool,
        test_pantheon_count, test_pantheon_tharion,
        test_pantheon_sylvana, test_all_god_names,
        test_god_domains_unique, test_god_personalities,
        test_disguise_init, test_set_disguise, test_invalid_disguise,
        test_template_form_types, test_template_colors,
        test_template_count, test_template_races,
        test_position_save_restore,
        test_smite_miracle, test_smite_spheres,
        test_pool_at_center, test_pool_tiles,
        test_portal_in_bounds,
        test_god_dashboard_class, test_god_dashboard_init,
        test_pantheon_system_init, test_god_relationships,
    ]
    for t in all_tests:
        t()
    sys.exit(print_report())
