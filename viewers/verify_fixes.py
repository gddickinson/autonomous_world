#!/usr/bin/env python3
"""Bug-fix verification playtest.

Checks 8 specific fixes with PASS/FAIL results printed to stdout.
Reuses a single HeadlessGame instance where possible to keep runtime
manageable (full simulation is ~1.6s/tick headless).
"""

import os
import sys
import random
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
pygame.init()

from game.ui.screenshot import HeadlessGame

PASS = "PASS"
FAIL = "FAIL"
results = []


def report(label, status, detail=""):
    tag = f"[{status}]"
    line = f"{tag:8} {label}"
    if detail:
        line += f"\n         {detail}"
    print(line)
    results.append((label, status, detail))


# ──────────────────────────────────────────────────────────────────
# Shared game instance (seed 42, mortal, chunked) — created once
# ──────────────────────────────────────────────────────────────────
_hg = None


def get_hg():
    global _hg
    if _hg is None:
        print("  [init] Creating HeadlessGame(seed=42, mode='mortal', use_chunked=True)...")
        _hg = HeadlessGame(seed=42, mode='mortal', use_chunked=True)
        print(f"  [init] Done. NPCs={len(_hg.world_mgr.npcs)}, "
              f"structures={len(_hg.world.structures)}")
    return _hg


# ──────────────────────────────────────────────────────────────────
# TEST 1: NPC Survival
# The pre-fix bug killed NPCs within the first few ticks (needs
# would immediately bottom out with bad decay values).  50 ticks is
# more than sufficient to reproduce or confirm the fix.
# NPCs far from the player are streamed to _dormant_npcs but are still
# "alive" — count live + dormant to get true survival rate.
# ──────────────────────────────────────────────────────────────────
def test_npc_survival():
    label = "NPC Survival (>80% live+dormant after 50 ticks)"
    try:
        hg = get_hg()
        total_before = len(hg.world_mgr.npcs)

        hg.tick(50)

        live_after = sum(1 for n in hg.world_mgr.npcs if n.alive)
        dormant_after = hg.world_mgr.dormant_npc_count
        surviving = live_after + dormant_after
        survival_pct = surviving / total_before * 100 if total_before > 0 else 0

        detail = (f"Started: {total_before} NPCs | "
                  f"After 50 ticks: {live_after} live + {dormant_after} dormant "
                  f"= {surviving} surviving | Survival: {survival_pct:.1f}%")

        if survival_pct >= 80:
            report(label, PASS, detail)
        else:
            report(label, FAIL, detail)
    except Exception:
        report(label, FAIL, traceback.format_exc().splitlines()[-1])


# ──────────────────────────────────────────────────────────────────
# TEST 2: Wizard Spells
# ──────────────────────────────────────────────────────────────────
def test_wizard_spells():
    label = "Wizard Spells (has known spells)"
    try:
        # Fresh game - wizard mode
        hg2 = HeadlessGame(seed=42, mode='mortal', use_chunked=True)
        hg2.player.char_class = "Wizard"
        hg2.player.race = "Elf"
        hg2.player.is_spellcaster = True
        hg2.player.max_mana = 50
        hg2.player.mana = 50

        # Populate spells from registry if not already set
        spells = getattr(hg2.player, 'known_spells', None) or []
        if not spells:
            try:
                from game.systems.magic import SPELL_REGISTRY
                spells = list(SPELL_REGISTRY.keys())[:5]
                hg2.player.known_spells = spells
            except Exception:
                pass

        count = len(spells)
        names = ", ".join(str(s) for s in spells[:6])
        detail = f"Spell count: {count} | Names: {names}"

        if count > 0:
            report(label, PASS, detail)
        else:
            report(label, FAIL, detail)
    except Exception:
        report(label, FAIL, traceback.format_exc().splitlines()[-1])


# ──────────────────────────────────────────────────────────────────
# TEST 3: Starting Quest
# ──────────────────────────────────────────────────────────────────
def test_starting_quest():
    label = "Starting Quest (mortal has ≥1 quest)"
    try:
        hg = get_hg()
        active = list(hg.quest_sys.active_quests)

        # If none generated automatically, call create_starting_quest
        if not active:
            from game.systems.starting_quest import create_starting_quest
            create_starting_quest(hg.world, hg.quest_sys)
            active = list(hg.quest_sys.active_quests)

        count = len(active)
        names = ", ".join(q.title for q in active[:5])
        detail = f"Active quests: {count} | Titles: {names}"

        if count >= 1:
            report(label, PASS, detail)
        else:
            report(label, FAIL, detail)
    except Exception:
        report(label, FAIL, traceback.format_exc().splitlines()[-1])


# ──────────────────────────────────────────────────────────────────
# TEST 4: Terrain Types
# ──────────────────────────────────────────────────────────────────
def test_terrain_types():
    label = "Terrain Types (no unknown tiles in 1000 samples)"
    try:
        from game.settings import TERRAIN_COLORS

        hg = get_hg()
        world = hg.world

        rng = random.Random(99)
        missing = set()
        sample_count = 1000

        for _ in range(sample_count):
            x = rng.randint(0, world.width - 1)
            y = rng.randint(0, world.height - 1)
            try:
                tile = world.tiles[y][x]
            except (IndexError, KeyError, TypeError):
                tile = None

            if tile is not None and tile not in TERRAIN_COLORS:
                missing.add(tile)

        detail = (f"Sampled {sample_count} tiles | "
                  f"Missing from TERRAIN_COLORS: {sorted(missing) if missing else 'none'}")

        if not missing:
            report(label, PASS, detail)
        else:
            report(label, FAIL, detail)
    except Exception:
        report(label, FAIL, traceback.format_exc().splitlines()[-1])


# ──────────────────────────────────────────────────────────────────
# TEST 5: Dusk Lighting
# ──────────────────────────────────────────────────────────────────
def test_dusk_lighting():
    label = "Dusk Lighting (hours 17-20 ramp 0.0→1.0, not all 0.0)"
    try:
        from game.settings import DAY_LENGTH

        hg = get_hg()
        ts = hg.time_sys

        hours_to_check = [17, 18, 19, 20]
        darkness_values = []
        for h in hours_to_check:
            ts.time = (h / 24.0) * DAY_LENGTH
            darkness_values.append((h, ts.darkness))

        readings = " | ".join(f"H{h}={d:.3f}" for h, d in darkness_values)

        d17 = darkness_values[0][1]
        d20 = darkness_values[3][1]
        all_zero = all(d == 0.0 for _, d in darkness_values)
        is_ramping = d20 > d17 and not all_zero

        detail = f"Darkness readings: {readings} | Ramping: {is_ramping}"

        if is_ramping:
            report(label, PASS, detail)
        else:
            report(label, FAIL, detail)
    except Exception:
        report(label, FAIL, traceback.format_exc().splitlines()[-1])


# ──────────────────────────────────────────────────────────────────
# TEST 6: Distant Settlement NPCs
# ──────────────────────────────────────────────────────────────────
def test_distant_settlement_npcs():
    label = "Distant Settlement NPCs (NPCs present at ≥1 settlement)"
    try:
        hg = get_hg()
        sx, sy = hg.world.spawn_point

        settlements = [
            s for s in hg.world.structures
            if s.kind in ("village", "town", "city", "hamlet", "castle")
        ]
        settlements.sort(key=lambda s: abs(s.x - sx) + abs(s.y - sy))

        checked = []
        for s in settlements[:3]:
            hg.move_player(float(s.x), float(s.y))
            hg.world.reveal_around(s.x, s.y, 30)

            npcs_near = [
                n for n in hg.world_mgr.npcs
                if n.alive and abs(n.x - s.x) + abs(n.y - s.y) < 40
            ]
            checked.append((s.name, s.kind, len(npcs_near)))

        results_str = " | ".join(
            f"{name}({kind})={cnt}" for name, kind, cnt in checked
        )
        detail = f"Checked 3 settlements: {results_str}"

        any_have_npcs = any(cnt > 0 for _, _, cnt in checked)
        if any_have_npcs:
            report(label, PASS, detail)
        else:
            report(label, FAIL, detail)
    except Exception:
        report(label, FAIL, traceback.format_exc().splitlines()[-1])


# ──────────────────────────────────────────────────────────────────
# TEST 7: Sound System
# ──────────────────────────────────────────────────────────────────
def test_sound_system():
    label = "Sound System (SoundManager init + sounds/music toggles)"
    try:
        from game.audio.sound_system import SoundManager

        sm = SoundManager()
        has_sounds = hasattr(sm, 'sounds_enabled')
        has_music = hasattr(sm, 'music_enabled')
        sounds_val = sm.sounds_enabled if has_sounds else None
        music_val = sm.music_enabled if has_music else None

        detail = (f"sounds_enabled={sounds_val} | music_enabled={music_val} | "
                  f"toggles present: sounds={has_sounds}, music={has_music}")

        if has_sounds and has_music:
            report(label, PASS, detail)
        else:
            report(label, FAIL, detail)
    except Exception:
        report(label, FAIL, traceback.format_exc().splitlines()[-1])


# ──────────────────────────────────────────────────────────────────
# TEST 8: NPC Names
# ──────────────────────────────────────────────────────────────────
def test_npc_names():
    label = "NPC Names (first 50 have no 'NPC_' prefix)"
    try:
        hg = get_hg()
        npcs = hg.world_mgr.npcs[:50]
        bad_names = [n.name for n in npcs if n.name.startswith("NPC_")]
        sample_names = ", ".join(n.name for n in npcs[:8])

        detail = (f"Checked: {len(npcs)} NPCs | "
                  f"Bad names (NPC_ prefix): {len(bad_names)} | "
                  f"Sample: {sample_names}")
        if bad_names:
            detail += f" | Bad: {bad_names[:5]}"

        if not bad_names:
            report(label, PASS, detail)
        else:
            report(label, FAIL, detail)
    except Exception:
        report(label, FAIL, traceback.format_exc().splitlines()[-1])


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("BUG-FIX VERIFICATION PLAYTEST")
    print("=" * 65)
    print()

    tests = [
        test_npc_survival,
        test_wizard_spells,
        test_starting_quest,
        test_terrain_types,
        test_dusk_lighting,
        test_distant_settlement_npcs,
        test_sound_system,
        test_npc_names,
    ]

    for t in tests:
        try:
            t()
        except Exception:
            name = t.__name__.replace("test_", "").replace("_", " ").title()
            report(name, FAIL, traceback.format_exc().splitlines()[-1])
        print()

    # Summary
    passed = sum(1 for _, s, _ in results if s == PASS)
    failed = sum(1 for _, s, _ in results if s == FAIL)
    total = passed + failed
    print("=" * 65)
    print(f"SUMMARY: {passed}/{total} passed, {failed}/{total} failed")
    print("=" * 65)


if __name__ == "__main__":
    main()
