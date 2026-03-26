#!/usr/bin/env python3
"""Comprehensive assessment playtest — 4 sessions testing game systems.

Sessions: Mortal Fighter, God Mode Economy, Visual Check, Systems Check.
All screenshots saved to viewers/assessment_output/
"""

import os
import sys
import random
import math
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUTPUT_DIR = os.path.join(ROOT, "viewers", "assessment_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
pygame.init()

from game.ui.screenshot import HeadlessGame
from game.settings import (
    TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT, DAY_LENGTH,
    DAWN_START, DAY_START, DUSK_START, NIGHT_START,
)

ALL_SCREENSHOTS = []
REPORT_LINES = []
DATA = {}  # collected data for the report


def log(msg):
    print(msg)
    REPORT_LINES.append(msg)


def save(hg, name, view="gameplay", **kwargs):
    filename = f"{name}.png"
    path = hg.capture(view, filename=filename, **kwargs)
    ALL_SCREENSHOTS.append((name, path))
    log(f"  [screenshot] {name}.png")
    return path


def find_nearest_settlement(world, x, y, kind=None):
    best, best_dist = None, 999999
    for s in world.structures:
        if s.kind not in ("village", "town", "city", "hamlet", "castle"):
            continue
        if kind and s.kind != kind:
            continue
        d = abs(s.x - x) + abs(s.y - y)
        if d < best_dist:
            best_dist, best = d, s
    return best


# ================================================================
# SESSION 1: Mortal Fighter (seed 42, chunked, 500 ticks)
# ================================================================
def session_1_mortal_fighter():
    log("\n" + "=" * 60)
    log("SESSION 1: MORTAL FIGHTER (500 ticks)")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="mortal", export_dir=OUTPUT_DIR,
                       use_chunked=True)
    hg.player.char_class = "Fighter"
    hg.player.race = "Human"
    hg.player.name = "Thorn"

    sx, sy = hg.world.spawn_point
    log(f"  Spawn: ({sx}, {sy})")
    log(f"  Player: {hg.player.name}, {hg.player.race} {hg.player.char_class}")
    log(f"  HP: {hg.player.hp}/{hg.player.max_hp}, Level: {hg.player.level}")

    hg.move_player(float(sx), float(sy))
    save(hg, "S1_spawn_point")

    # Check starting quest
    quests = hg.quest_sys.active_quests
    log(f"  Starting quests: {len(quests)}")
    DATA["starting_quests"] = len(quests)
    for q in quests:
        log(f"    - {q.title}: {q.description[:80]}")

    # Check NPC names and classes
    all_npcs = hg.world_mgr.npcs
    log(f"  Total NPCs: {len(all_npcs)}")
    DATA["total_npcs"] = len(all_npcs)

    bad_names = [n for n in all_npcs if n.name.startswith("NPC_")]
    log(f"  NPCs with bad names (NPC_xxxx): {len(bad_names)}")
    DATA["bad_name_count"] = len(bad_names)

    # Show sample NPC names
    sample = all_npcs[:15]
    log("  Sample NPC names/classes:")
    for npc in sample:
        job = getattr(npc, 'job', getattr(npc, 'profession', '?'))
        log(f"    {npc.name}: {npc.race} {npc.char_class}, job={job}")

    # Check terrain at spawn (no white/black tiles)
    terrain_counts = {}
    for dy in range(-10, 11):
        for dx in range(-10, 11):
            tx, ty = int(sx) + dx, int(sy) + dy
            if 0 <= tx < hg.world.width and 0 <= ty < hg.world.height:
                t = hg.world.tiles[ty][tx]
                terrain_counts[t] = terrain_counts.get(t, 0) + 1
    log(f"  Terrain around spawn: {terrain_counts}")
    DATA["spawn_terrain"] = terrain_counts

    # Find settlement, check NPCs there
    nearest = find_nearest_settlement(hg.world, sx, sy)
    if nearest:
        log(f"  Nearest settlement: {nearest.name} ({nearest.kind})")
        dist = math.hypot(nearest.x - sx, nearest.y - sy)
        log(f"  Distance: {dist:.0f} tiles")
        DATA["nearest_settlement"] = nearest.name
        DATA["nearest_distance"] = dist

    # Settlement/kingdom stats
    settlements = [s for s in hg.world.structures
                   if s.kind in ("village", "town", "city", "hamlet", "castle")]
    log(f"  Settlements: {len(settlements)}")
    DATA["settlement_count"] = len(settlements)
    by_kind = {}
    for s in settlements:
        by_kind[s.kind] = by_kind.get(s.kind, 0) + 1
    log(f"  By type: {by_kind}")

    if hasattr(hg, 'simulation') and hasattr(hg.simulation, 'governance'):
        kingdoms = hg.simulation.governance.kingdoms
        log(f"  Kingdoms: {len(kingdoms)}")
        DATA["kingdom_count"] = len(kingdoms)
        for kn, k in kingdoms.items():
            log(f"    {kn}: treasury={k.treasury}, pop={k.population}, "
                f"army={k.army_size}")

    # Advance 500 ticks
    alive_before = sum(1 for n in all_npcs if n.alive)
    hg.tick(500)
    alive_after = sum(1 for n in all_npcs if n.alive)

    log(f"  NPCs alive: {alive_before} -> {alive_after} "
        f"(survival rate: {alive_after/max(alive_before,1)*100:.1f}%)")
    DATA["npc_survival_rate"] = alive_after / max(alive_before, 1) * 100
    DATA["npcs_alive_before"] = alive_before
    DATA["npcs_alive_after"] = alive_after

    save(hg, "S1_after_500_ticks")
    log("  Session 1 complete.")
    return hg


# ================================================================
# SESSION 2: God Mode Economy Check (seed 42, chunked, 2000 ticks)
# ================================================================
def session_2_economy():
    log("\n" + "=" * 60)
    log("SESSION 2: GOD MODE ECONOMY CHECK (2000 ticks)")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="god", export_dir=OUTPUT_DIR,
                       use_chunked=True)
    sim = hg.simulation

    # Treasury snapshots
    def snapshot_treasuries():
        result = {}
        if hasattr(sim, 'governance'):
            for kn, k in sim.governance.kingdoms.items():
                result[kn] = {
                    "treasury": k.treasury,
                    "population": k.population,
                    "army_size": k.army_size,
                    "morale": k.public_morale,
                }
        return result

    snap_0 = snapshot_treasuries()
    log(f"  Tick 0 — Kingdoms: {len(snap_0)}")
    for kn, kd in snap_0.items():
        log(f"    {kn}: treasury={kd['treasury']}, pop={kd['population']}")

    # Advance to tick 1000
    log("  Advancing to tick 1000...")
    hg.tick(1000)
    snap_1000 = snapshot_treasuries()
    log(f"  Tick 1000:")
    for kn, kd in snap_1000.items():
        t0 = snap_0.get(kn, {}).get("treasury", 0)
        delta = kd["treasury"] - t0
        log(f"    {kn}: treasury={kd['treasury']} (delta={delta:+.0f})")

    # Advance to tick 2000
    log("  Advancing to tick 2000...")
    hg.tick(1000)
    snap_2000 = snapshot_treasuries()
    log(f"  Tick 2000:")
    treasury_growth = []
    for kn, kd in snap_2000.items():
        t0 = snap_0.get(kn, {}).get("treasury", 0)
        delta = kd["treasury"] - t0
        treasury_growth.append(delta)
        log(f"    {kn}: treasury={kd['treasury']} (total delta={delta:+.0f})")

    growing = sum(1 for d in treasury_growth if d > 0)
    shrinking = sum(1 for d in treasury_growth if d < 0)
    flat = sum(1 for d in treasury_growth if d == 0)
    log(f"  Treasury trend: {growing} growing, {shrinking} shrinking, {flat} flat")
    DATA["treasury_growing"] = growing
    DATA["treasury_shrinking"] = shrinking
    DATA["treasury_flat"] = flat

    # Trade stats
    if hasattr(sim, 'trade'):
        caravans = getattr(sim.trade, 'active_caravans', [])
        completed = getattr(sim.trade, 'completed_trades', 0)
        routes = getattr(sim.trade, 'trade_routes', [])
        log(f"  Active caravans: {len(caravans)}")
        log(f"  Completed trades: {completed}")
        log(f"  Trade routes: {len(routes)}")
        DATA["active_caravans"] = len(caravans)
        DATA["completed_trades"] = completed

    # Construction stats
    if hasattr(sim, 'construction'):
        projects = getattr(sim.construction, 'active_projects', [])
        completed_b = getattr(sim.construction, 'completed_projects', 0)
        log(f"  Active construction: {len(projects)}")
        log(f"  Completed builds: {completed_b}")
        DATA["active_construction"] = len(projects)
        DATA["completed_builds"] = completed_b

    # Wars
    if hasattr(sim, 'military'):
        wars = getattr(sim.military, 'active_wars', [])
        log(f"  Active wars: {len(wars)}")
        DATA["active_wars"] = len(wars)

    # NPC activity distribution
    activity_dist = {}
    alive_npcs = [n for n in hg.world_mgr.npcs if n.alive]
    for n in alive_npcs:
        action = getattr(n, 'current_action', 'idle')
        activity_dist[action] = activity_dist.get(action, 0) + 1
    total_alive = len(alive_npcs)
    log(f"  NPC Activity Distribution ({total_alive} alive):")
    idle_count = 0
    working_count = 0
    for act, cnt in sorted(activity_dist.items(), key=lambda x: -x[1]):
        pct = cnt / max(total_alive, 1) * 100
        log(f"    {act}: {cnt} ({pct:.1f}%)")
        if act in ('idle', 'waiting', 'none', None):
            idle_count += cnt
        else:
            working_count += cnt
    DATA["idle_pct"] = idle_count / max(total_alive, 1) * 100
    DATA["working_pct"] = working_count / max(total_alive, 1) * 100
    DATA["activity_dist"] = activity_dist

    save(hg, "S2_economy_after_2000")
    log("  Session 2 complete.")
    return hg


# ================================================================
# SESSION 3: Visual Check (screenshots)
# ================================================================
def session_3_visual():
    log("\n" + "=" * 60)
    log("SESSION 3: VISUAL CHECK")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="god", export_dir=OUTPUT_DIR,
                       use_chunked=True)

    sx, sy = hg.world.spawn_point
    settlement = find_nearest_settlement(hg.world, sx, sy)

    if settlement:
        hg.move_player(float(settlement.x), float(settlement.y))
        hg.world.reveal_around(settlement.x, settlement.y, 40)
        log(f"  Settlement: {settlement.name} at ({settlement.x}, {settlement.y})")

    # Strategy zoom (default TILE_SIZE)
    save(hg, "S3_strategy_zoom")

    # Adventure zoom (32px tiles)
    try:
        hg.camera.set_tile_size(32)
        from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT
        ts = hg.camera.tile_size
        hg.camera.x = hg.player.x * ts - SCREEN_WIDTH // 2
        hg.camera.y = hg.player.y * ts - SCREEN_HEIGHT // 2
        save(hg, "S3_adventure_zoom")
        hg.camera.set_tile_size(TILE_SIZE)  # reset
    except Exception as e:
        log(f"  Adventure zoom error: {e}")

    # Dusk scene
    hg.time_sys.time = DAY_LENGTH * DUSK_START
    darkness = hg.time_sys.darkness
    log(f"  Dusk: darkness={darkness:.2f}")
    save(hg, "S3_dusk_scene")

    # Night scene with torch glow
    hg.time_sys.time = DAY_LENGTH * 0.90
    darkness = hg.time_sys.darkness
    log(f"  Night: darkness={darkness:.2f}")
    save(hg, "S3_night_scene")

    # World map overview
    save(hg, "S3_world_map", view="world_map", zoom=0.5)

    log("  Session 3 complete.")
    return hg


# ================================================================
# SESSION 4: Systems Check
# ================================================================
def session_4_systems():
    log("\n" + "=" * 60)
    log("SESSION 4: SYSTEMS CHECK")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="god", export_dir=OUTPUT_DIR,
                       use_chunked=True)

    sx, sy = hg.world.spawn_point

    # Creature diversity
    creature_types = {}
    for c in hg.world_mgr.creatures:
        creature_types[c.kind] = creature_types.get(c.kind, 0) + 1
    log(f"  Creature types: {len(creature_types)}")
    for kind, cnt in sorted(creature_types.items(), key=lambda x: -x[1]):
        log(f"    {kind}: {cnt}")
    DATA["creature_types"] = creature_types
    DATA["creature_diversity"] = len(creature_types)
    DATA["total_creatures"] = len(hg.world_mgr.creatures)

    # Domestic animals near settlements
    settlement = find_nearest_settlement(hg.world, sx, sy)
    domestic_kinds = {"chicken", "cow", "pig", "sheep", "goat", "horse",
                      "dog", "cat", "donkey", "ox", "mule"}
    domestic_near = []
    hostile_near = []
    if settlement:
        for c in hg.world_mgr.creatures:
            d = math.hypot(c.x - settlement.x, c.y - settlement.y)
            if d < 50:
                if c.kind.lower() in domestic_kinds:
                    domestic_near.append(c)
                elif getattr(c, 'hostile', False):
                    hostile_near.append(c)
    log(f"  Domestic animals near settlement: {len(domestic_near)}")
    for c in domestic_near[:5]:
        log(f"    {c.kind} at ({c.x:.0f}, {c.y:.0f})")
    DATA["domestic_near_settlement"] = len(domestic_near)

    # Hostile creatures near spawn
    hostile_spawn = []
    for c in hg.world_mgr.creatures:
        d = math.hypot(c.x - sx, c.y - sy)
        if d < 80 and getattr(c, 'hostile', False):
            hostile_spawn.append((d, c))
    hostile_spawn.sort()
    log(f"  Hostile creatures near spawn (80 tiles): {len(hostile_spawn)}")
    for d, c in hostile_spawn[:5]:
        log(f"    {c.kind}: dist={d:.0f}, HP={c.hp}/{c.max_hp}")
    DATA["hostile_near_spawn"] = len(hostile_spawn)

    # Sound system
    try:
        from game.audio.sound_system import SoundManager
        sm = SoundManager()
        log(f"  Sound system: INITIALIZES OK")
        DATA["sound_system"] = "OK"
    except Exception as e:
        log(f"  Sound system: FAILED ({e})")
        DATA["sound_system"] = f"FAILED: {e}"

    # Exposure system
    try:
        from game.systems.exposure import process_exposure
        log(f"  Exposure system: IMPORTS OK")
        DATA["exposure_system"] = "OK"
    except Exception as e:
        log(f"  Exposure system: FAILED ({e})")
        DATA["exposure_system"] = f"FAILED: {e}"

    # Check other systems
    systems_status = {}
    sys_checks = [
        ("TimeSystem", "game.systems", "TimeSystem"),
        ("QuestSystem", "game.systems.quests", "QuestSystem"),
        ("WorldManager", "game.systems.world_manager", "WorldManager"),
        ("SimulationManager", "game.systems.simulation", "SimulationManager"),
        ("GovernanceSystem", "game.systems.governance", "GovernanceSystem"),
        ("TradeSystem", "game.systems.trade", "TradeSystem"),
        ("ConstructionSystem", "game.systems.construction", "ConstructionSystem"),
        ("BuildingSystem", "game.systems.buildings", "BuildingSystem"),
        ("TacticalCombat", "game.systems.tactical_combat", "TacticalCombat"),
        ("PlayerParty", "game.systems.party", "PlayerParty"),
        ("MusicSystem", "game.audio.music_system", "MusicSystem"),
        ("ChunkedWorld", "game.world.world", "ChunkedWorld"),
        ("FactionSystem", "game.systems.factions", "FactionSystem"),
        ("WarfareSystem", "game.systems.warfare", "WarfareSystem"),
    ]
    for label, mod_path, cls_name in sys_checks:
        try:
            mod = __import__(mod_path, fromlist=[cls_name])
            cls = getattr(mod, cls_name)
            systems_status[label] = "OK"
        except Exception as e:
            systems_status[label] = f"FAILED: {e}"

    log("  Systems inventory:")
    for label, status in sorted(systems_status.items()):
        log(f"    {label}: {status}")
    DATA["systems_status"] = systems_status

    save(hg, "S4_systems_check")
    log("  Session 4 complete.")
    return hg


# ================================================================
# MAIN
# ================================================================
def main():
    log("=" * 60)
    log("ASSESSMENT PLAYTEST — AUTONOMOUS WORLD")
    log("=" * 60)

    sessions = [
        ("Session 1: Mortal Fighter", session_1_mortal_fighter),
        ("Session 2: God Mode Economy", session_2_economy),
        ("Session 3: Visual Check", session_3_visual),
        ("Session 4: Systems Check", session_4_systems),
    ]

    for name, func in sessions:
        try:
            func()
        except Exception as e:
            log(f"\n  ERROR in {name}: {e}")
            traceback.print_exc()
            REPORT_LINES.append(f"  Traceback: {traceback.format_exc()}")

    # Write log
    log_path = os.path.join(OUTPUT_DIR, "assessment_log.txt")
    with open(log_path, "w") as f:
        f.write("\n".join(REPORT_LINES))
    log(f"\nLog saved to {log_path}")
    log(f"Total screenshots: {len(ALL_SCREENSHOTS)}")
    log("\nScreenshot manifest:")
    for name, path in ALL_SCREENSHOTS:
        log(f"  {name}: {path}")


if __name__ == "__main__":
    main()
