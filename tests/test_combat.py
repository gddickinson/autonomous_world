#!/usr/bin/env python3
"""Deep functional tests for the combat system.

Tests: player attack damage, shield blocking, dodge mechanics,
surrender, projectile flight, difficulty scaling, combat effects,
AoE spells, spell damage scaling, creature combat tick.
"""

import os
import sys
import math
import time
import random
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------
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
    print(f"COMBAT TESTS  —  {passed}/{total} passed, {failed} failed")
    print("=" * 70)
    for name, ok, detail in _results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}" + ("" if ok else f"  — {detail}"))
    print("=" * 70)
    return failed


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
from game.core.player import Player
from game.core.creature import Creature
from game.core.npc import NPC
from game.core.items import Item, make_item
from game.settings import ITEM_WEAPON, ITEM_ARMOR


def _make_player(strength=14, dexterity=12, weapon_name="Iron Sword"):
    p = Player(100.0, 100.0, char_class="Fighter", race="Human",
               ability_scores={
                   "strength": strength, "dexterity": dexterity,
                   "constitution": 12, "intelligence": 10,
                   "wisdom": 10, "charisma": 10,
               })
    if weapon_name:
        w = make_item(weapon_name)
        p.inventory.append(w)
        p.equipped_weapon = w
    return p


def _make_npc(profession="Guard", hp=50, dex=10, shield=False,
              armor_name=""):
    npc = NPC(102.0, 100.0, name="TestNPC", profession=profession)
    npc.hp = hp
    npc.max_hp = max(hp, npc.max_hp)
    npc.ability_scores["dexterity"] = dex
    if shield:
        s = Item("Iron Shield", ITEM_ARMOR, 50, defense=3)
        s.durability = 10
        s.max_durability = 10
        npc.npc_inventory = getattr(npc, 'npc_inventory', [])
        npc.npc_inventory.append(s)
    if armor_name:
        a = make_item(armor_name) if armor_name in ("Leather Armor",
            "Iron Armor") else Item(armor_name, ITEM_ARMOR, 50, defense=8)
        npc.equipped_armor = a
    return npc


def _make_creature(kind="wolf"):
    return Creature(105.0, 100.0, kind=kind)


# ===================================================================
# 1. PLAYER ATTACK DAMAGE
# ===================================================================

@test("Player attack damage = base + weapon + level*2")
def test_player_damage_formula():
    p = _make_player(weapon_name="Iron Sword")
    weapon_dmg = p.equipped_weapon.damage  # 18
    base = p.attack_damage                 # 3
    level_bonus = p.level * 2              # 2
    expected = base + weapon_dmg + level_bonus
    actual = p.get_attack_damage()
    assert actual == expected, f"Expected {expected}, got {actual}"


@test("Player damage with no weapon uses base + level*2")
def test_player_damage_unarmed():
    p = _make_player(weapon_name="")
    p.equipped_weapon = None
    expected = p.attack_damage + p.level * 2
    actual = p.get_attack_damage()
    assert actual == expected, f"Expected {expected}, got {actual}"


@test("Higher level increases damage")
def test_damage_scales_with_level():
    p = _make_player()
    d1 = p.get_attack_damage()
    p.level = 5
    d5 = p.get_attack_damage()
    assert d5 > d1, f"Level 5 damage ({d5}) should exceed level 1 ({d1})"
    assert d5 - d1 == (5 - 1) * 2


# ===================================================================
# 2. SHIELD BLOCKING
# ===================================================================

@test("Shield block returns True/False (bool)")
def test_shield_block_returns_bool():
    from game.systems.combat_depth import try_shield_block
    npc = _make_npc(shield=True)
    results = set()
    random.seed(0)
    for _ in range(200):
        results.add(try_shield_block(npc))
    assert True in results and False in results, \
        f"Expected both True and False, got {results}"


@test("Shield block reduces durability on success")
def test_shield_durability_decreases():
    from game.systems.combat_depth import try_shield_block
    npc = _make_npc(shield=True)
    # The shield is in npc_inventory; find it
    shield = None
    for item in getattr(npc, 'npc_inventory', []):
        if "shield" in item.name.lower():
            shield = item
            break
    if shield is None:
        # Also check inventory
        for item in getattr(npc, 'inventory', []):
            if "shield" in item.name.lower():
                shield = item
                break
    assert shield is not None, "Shield not found in NPC equipment"
    initial_dur = shield.durability
    blocked = False
    for seed_val in range(1000):
        random.seed(seed_val)
        if try_shield_block(npc):
            blocked = True
            break
    assert blocked, "Could not get a single block in 1000 attempts"
    assert shield.durability < initial_dur, \
        f"Durability unchanged: {shield.durability}"


@test("No shield = block always returns False")
def test_no_shield_no_block():
    from game.systems.combat_depth import try_shield_block
    npc = _make_npc(shield=False)
    for _ in range(50):
        assert try_shield_block(npc) is False


# ===================================================================
# 3. DODGE MECHANICS
# ===================================================================

@test("Dodge works for unarmored targets")
def test_dodge_unarmored():
    from game.systems.combat_depth import try_dodge, _dodge_cooldowns
    _dodge_cooldowns.clear()
    npc = _make_npc(dex=16)  # high DEX, no armor
    npc.equipped_armor = None
    random.seed(42)
    results = set()
    for _ in range(300):
        _dodge_cooldowns.clear()
        results.add(try_dodge(npc))
    assert True in results, "High-DEX unarmored NPC should dodge sometimes"


@test("Dodge works for light armor (Leather)")
def test_dodge_light_armor():
    from game.systems.combat_depth import try_dodge, _dodge_cooldowns
    _dodge_cooldowns.clear()
    npc = _make_npc(dex=16, armor_name="Leather Armor")
    random.seed(42)
    results = set()
    for _ in range(300):
        _dodge_cooldowns.clear()
        results.add(try_dodge(npc))
    assert True in results, "Leather armor should allow dodging"


@test("Heavy armor (plate) prevents dodge")
def test_dodge_heavy_armor_fails():
    from game.systems.combat_depth import try_dodge, _dodge_cooldowns
    _dodge_cooldowns.clear()
    npc = _make_npc(dex=18, armor_name="Plate Armor")
    for _ in range(100):
        _dodge_cooldowns.clear()
        assert try_dodge(npc) is False, "Plate armor should prevent dodge"


@test("Dodge has 2-second cooldown")
def test_dodge_cooldown():
    from game.systems.combat_depth import try_dodge, _dodge_cooldowns
    _dodge_cooldowns.clear()
    npc = _make_npc(dex=20)
    npc.equipped_armor = None
    # Force a successful dodge
    random.seed(0)
    first_dodge = False
    for _ in range(500):
        _dodge_cooldowns.clear()
        if try_dodge(npc):
            first_dodge = True
            break
    assert first_dodge, "Should have dodged at least once"
    # Immediately try again — should fail due to cooldown
    second_dodge = try_dodge(npc)
    assert second_dodge is False, "Cooldown should prevent second dodge"


# ===================================================================
# 4. SURRENDER
# ===================================================================

@test("Surrender triggers below 20% HP")
def test_surrender_low_hp():
    from game.systems.combat_depth import (
        check_surrender, is_surrendered, _surrendered_entities
    )
    _surrendered_entities.clear()
    npc = _make_npc(hp=100)
    npc.hp = 15  # 15% HP
    random.seed(0)
    triggered = False
    for _ in range(50):
        _surrendered_entities.pop(id(npc), None)
        if check_surrender(npc):
            triggered = True
            break
    assert triggered, "NPC at 15% HP should surrender eventually"


@test("Surrender does not trigger above 20% HP")
def test_no_surrender_above_threshold():
    from game.systems.combat_depth import (
        check_surrender, _surrendered_entities
    )
    _surrendered_entities.clear()
    npc = _make_npc(hp=100)
    npc.hp = 25  # 25% HP
    for _ in range(100):
        assert check_surrender(npc) is False, \
            "NPC above 20% HP should not surrender"


@test("Creatures never surrender")
def test_creature_no_surrender():
    from game.systems.combat_depth import (
        check_surrender, _surrendered_entities
    )
    _surrendered_entities.clear()
    c = _make_creature("wolf")
    c.hp = 1  # very low HP
    c.max_hp = 100
    for _ in range(100):
        assert check_surrender(c) is False, \
            "Creatures should never surrender"


@test("is_surrendered returns True after surrender")
def test_is_surrendered_flag():
    from game.systems.combat_depth import (
        check_surrender, is_surrendered, _surrendered_entities,
        _apply_surrender
    )
    _surrendered_entities.clear()
    npc = _make_npc(hp=100)
    _apply_surrender(npc)
    assert is_surrendered(npc) is True


# ===================================================================
# 5. PROJECTILE FLIGHT
# ===================================================================

@test("Projectile arrives after correct flight time")
def test_projectile_flight_time():
    from game.systems.projectiles import ProjectileManager, PROJECTILE_SPEEDS
    pm = ProjectileManager()
    target = _make_npc()
    speed = PROJECTILE_SPEEDS["bow"]
    proj = pm.spawn(0.0, 0.0, target, damage=10, weapon_type="bow")
    expected_time = proj.distance / speed
    # Step just under the flight time
    results = pm.update(expected_time - 0.01)
    assert len(results) == 0, "Projectile should not arrive early"
    # Step past flight time
    results = pm.update(0.02)
    assert len(results) == 1, "Projectile should arrive after flight time"


@test("Projectile misses moving target")
def test_projectile_misses_moved_target():
    from game.systems.projectiles import ProjectileManager, MISS_THRESHOLD
    pm = ProjectileManager()
    target = _make_npc()
    proj = pm.spawn(0.0, 0.0, target, damage=10, weapon_type="bow")
    # Move target far away (beyond MISS_THRESHOLD)
    target.x += MISS_THRESHOLD + 5.0
    target.y += MISS_THRESHOLD + 5.0
    results = pm.update(proj.flight_time + 0.1)
    assert len(results) == 1
    assert results[0].hit is False, "Projectile should miss moved target"


@test("Projectile hits stationary target")
def test_projectile_hits_stationary():
    from game.systems.projectiles import ProjectileManager
    pm = ProjectileManager()
    target = _make_npc()
    proj = pm.spawn(0.0, 0.0, target, damage=10, weapon_type="bow")
    results = pm.update(proj.flight_time + 0.1)
    assert len(results) == 1
    assert results[0].hit is True, "Projectile should hit stationary target"


# ===================================================================
# 6. DIFFICULTY SCALING
# ===================================================================

@test("Easy difficulty halves enemy damage")
def test_easy_damage_scaling():
    from game.systems.difficulty import (
        DIFFICULTY, init_difficulty, scale_enemy_damage, get_difficulty
    )
    init_difficulty({"difficulty": "easy"})
    assert get_difficulty() == "easy"
    assert scale_enemy_damage(20) == 10  # 0.5x


@test("Hard difficulty scales damage up by 1.5x")
def test_hard_damage_scaling():
    from game.systems.difficulty import init_difficulty, scale_enemy_damage
    init_difficulty({"difficulty": "hard"})
    assert scale_enemy_damage(20) == 30  # 1.5x


@test("Brutal difficulty doubles enemy HP")
def test_brutal_hp_scaling():
    from game.systems.difficulty import init_difficulty, scale_enemy_hp
    init_difficulty({"difficulty": "brutal"})
    assert scale_enemy_hp(50) == 100  # 2.0x


@test("Normal difficulty is 1.0x for all multipliers")
def test_normal_difficulty():
    from game.systems.difficulty import (
        init_difficulty, scale_enemy_damage, scale_enemy_hp,
        scale_xp, scale_gold
    )
    init_difficulty({"difficulty": "normal"})
    assert scale_enemy_damage(20) == 20
    assert scale_enemy_hp(50) == 50
    assert scale_xp(100) == 100
    assert scale_gold(100) == 100


# Reset to normal for other tests
from game.systems.difficulty import init_difficulty
init_difficulty({"difficulty": "normal"})

# ===================================================================
# 7. COMBAT EFFECTS
# ===================================================================

@test("DamagePopup creates with correct values")
def test_damage_popup_creation():
    from game.ui.combat_effects import DamagePopup
    dp = DamagePopup(100, 200, 42)
    assert dp.x == 100 and dp.y == 200
    assert dp.value == 42


@test("Combat visual queue drains correctly")
def test_drain_combat_visuals():
    from game.systems.combat import (
        _pending_combat_visuals, drain_combat_visuals, _emit_damage
    )
    _pending_combat_visuals.clear()
    target = _make_npc()
    _emit_damage(target, 15)
    _emit_damage(target, 25)
    events = drain_combat_visuals()
    assert len(events) == 2
    assert events[0]["damage"] == 15
    assert events[1]["damage"] == 25
    # Queue should be empty after drain
    events2 = drain_combat_visuals()
    assert len(events2) == 0


# ===================================================================
# 8. AoE SPELLS HIT MULTIPLE TARGETS
# ===================================================================

@test("Fireball spell data exists with AoE radius")
def test_fireball_aoe_data():
    from game.systems.magic_spells import SPELL_REGISTRY
    fireball = SPELL_REGISTRY.get("fireball")
    assert fireball is not None, "Fireball should exist in SPELL_REGISTRY"
    # Spell is a class with area/targets attributes
    area = getattr(fireball, 'area', 0)
    targets = getattr(fireball, 'targets', 'single')
    assert area > 0 or targets != 'single', \
        f"Fireball should be AoE: area={area}, targets={targets}"


# ===================================================================
# 9. SPELL DAMAGE
# ===================================================================

@test("Spell registry has damage values for offensive spells")
def test_spell_damage_values():
    from game.systems.magic_spells import SPELL_REGISTRY
    offensive = ["fireball", "lightning_bolt", "magic_missile", "ice_shard"]
    for spell_name in offensive:
        spell = SPELL_REGISTRY.get(spell_name)
        if spell is not None:
            dmg = getattr(spell, 'damage', 0)
            assert dmg > 0, \
                f"{spell_name} should have damage, got {dmg}"


# ===================================================================
# 10. CREATURE COMBAT TICK
# ===================================================================

@test("Creature combat tick doesn't crash for wolf")
def test_creature_tick_wolf():
    c = _make_creature("wolf")
    target = _make_player()
    target.x = c.x + 1
    target.y = c.y
    from game.systems.combat import CombatSystem
    c.attack_timer = 0.0
    # Should not crash
    CombatSystem.creature_combat_tick(c, target, 1.0)


@test("Creature combat tick doesn't crash for dragon")
def test_creature_tick_dragon():
    c = _make_creature("young_dragon")
    target = _make_player()
    target.x = c.x + 1
    target.y = c.y
    from game.systems.combat import CombatSystem
    c.attack_timer = 0.0
    CombatSystem.creature_combat_tick(c, target, 1.0)


@test("Creature combat tick doesn't crash for skeleton")
def test_creature_tick_skeleton():
    c = _make_creature("skeleton")
    target = _make_player()
    target.x = c.x + 1
    target.y = c.y
    from game.systems.combat import CombatSystem
    c.attack_timer = 0.0
    CombatSystem.creature_combat_tick(c, target, 1.0)


@test("Creature combat tick doesn't crash for unknown creature")
def test_creature_tick_unknown():
    c = _make_creature("mythical_beast_xyz")
    target = _make_player()
    target.x = c.x + 1
    target.y = c.y
    from game.systems.combat import CombatSystem
    c.attack_timer = 0.0
    CombatSystem.creature_combat_tick(c, target, 1.0)


# ===================================================================
# Run all tests
# ===================================================================

if __name__ == "__main__":
    all_tests = [
        test_player_damage_formula, test_player_damage_unarmed,
        test_damage_scales_with_level,
        test_shield_block_returns_bool, test_shield_durability_decreases,
        test_no_shield_no_block,
        test_dodge_unarmored, test_dodge_light_armor,
        test_dodge_heavy_armor_fails, test_dodge_cooldown,
        test_surrender_low_hp, test_no_surrender_above_threshold,
        test_creature_no_surrender, test_is_surrendered_flag,
        test_projectile_flight_time, test_projectile_misses_moved_target,
        test_projectile_hits_stationary,
        test_easy_damage_scaling, test_hard_damage_scaling,
        test_brutal_hp_scaling, test_normal_difficulty,
        test_damage_popup_creation, test_drain_combat_visuals,
        test_fireball_aoe_data,
        test_spell_damage_values,
        test_creature_tick_wolf, test_creature_tick_dragon,
        test_creature_tick_skeleton, test_creature_tick_unknown,
    ]
    for t in all_tests:
        t()
    sys.exit(print_report())
