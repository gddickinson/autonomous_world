#!/usr/bin/env python3
"""World Evolution Test — long-running simulation to measure what changes over time.

Initializes the world, takes baseline measurements, runs 1000+ ticks, and records
what systems actually produce dynamic world changes vs what stays static.

Outputs:
- Screenshots at tick 0, 250, 500, 750, 1000
- evolution_report.md with timeline and analysis
"""

import os
import sys
import time
import json
from collections import Counter, defaultdict
from copy import deepcopy

# Project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUTPUT_DIR = os.path.join(ROOT, "viewers", "evolution_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Force headless
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
pygame.init()

from game.ui.screenshot import HeadlessGame
from game.settings import (
    GRASS, FOREST, DENSE_FOREST, FARMLAND, WHEAT_FIELD, ROAD, WATER,
    SAND, MOUNTAIN, SNOW, SWAMP, TILLED_SOIL, TREE_STUMP,
)
from viewers.evolution_report_gen import generate_report, TILE_NAMES


def take_snapshot(hg, label=""):
    """Capture a comprehensive snapshot of the world state."""
    snap = {}
    snap["label"] = label
    snap["time_str"] = hg.time_sys.time_string
    snap["day"] = hg.time_sys.day
    snap["season"] = getattr(hg.time_sys, 'season', 'unknown')

    # --- NPC data ---
    alive_npcs = [n for n in hg.world_mgr.npcs if n.alive]
    dead_npcs = [n for n in hg.world_mgr.npcs if not n.alive]
    snap["npc_total"] = len(hg.world_mgr.npcs)
    snap["npc_alive"] = len(alive_npcs)
    snap["npc_dead"] = len(dead_npcs)
    snap["npc_names_alive"] = set(n.name for n in alive_npcs)

    # Job distribution
    job_counter = Counter()
    for n in alive_npcs:
        job_counter[getattr(n, 'profession', 'Unknown')] += 1
    snap["job_distribution"] = dict(job_counter)

    # NPC actions
    action_counter = Counter()
    for n in alive_npcs:
        action = getattr(n, 'current_action', '') or 'idle'
        action_counter[action] += 1
    snap["npc_actions"] = dict(action_counter)

    # NPC gold totals
    snap["npc_total_gold"] = sum(getattr(n, 'gold', 0) for n in alive_npcs)

    # NPC positions (for detecting movement)
    snap["npc_positions"] = {n.name: (round(n.x, 1), round(n.y, 1)) for n in alive_npcs}

    # --- Creature data ---
    snap["creature_count"] = len(hg.world_mgr.creatures)
    species_counter = Counter()
    for c in hg.world_mgr.creatures:
        species_counter[getattr(c, 'kind', 'Unknown')] += 1
    snap["creature_species"] = dict(species_counter)

    # --- Settlement data ---
    settlement_data = {}
    for s in hg.world.structures:
        if s.kind in ("village", "town", "city", "hamlet", "castle"):
            settlement_data[s.name] = {
                "kind": s.kind,
                "buildings": len(s.buildings),
                "x": s.x, "y": s.y,
            }
    snap["settlements"] = settlement_data

    # --- Kingdom data ---
    kingdom_data = {}
    if hasattr(hg, 'simulation') and hasattr(hg.simulation, 'governance'):
        for kname, k in hg.simulation.governance.kingdoms.items():
            kingdom_data[kname] = {
                "treasury": getattr(k, 'treasury', 0),
                "army_size": getattr(k, 'army_size', 0),
                "public_morale": getattr(k, 'public_morale', 50),
                "tax_rate": getattr(k, 'tax_rate', 0),
                "settlements": list(getattr(k, 'settlements', [])),
            }
    snap["kingdoms"] = kingdom_data

    # --- Terrain sampling (100x100 region around first city) ---
    terrain_counts = Counter()
    sample_cx, sample_cy = hg.world.spawn_point
    # Find a city for better sampling
    for s in hg.world.structures:
        if s.kind == "city":
            sample_cx, sample_cy = s.x, s.y
            break
    snap["terrain_sample_center"] = (sample_cx, sample_cy)
    sample_r = 50
    for dy in range(-sample_r, sample_r):
        for dx in range(-sample_r, sample_r):
            tx, ty = sample_cx + dx, sample_cy + dy
            if 0 <= tx < hg.world.width and 0 <= ty < hg.world.height:
                tile = hg.world.tiles[ty][tx]
                terrain_counts[tile] = terrain_counts.get(tile, 0) + 1
    snap["terrain_counts"] = dict(terrain_counts)

    # --- Trade activity ---
    trade_log = []
    if hasattr(hg, 'simulation') and hasattr(hg.simulation, 'trade'):
        caravans = getattr(hg.simulation.trade, 'caravans', [])
        snap["active_caravans"] = len(caravans)
    else:
        snap["active_caravans"] = 0

    # --- Events / Conflicts ---
    if hasattr(hg, 'simulation'):
        snap["active_events"] = len(hg.simulation.events)
        snap["event_log_size"] = len(hg.simulation.event_log)
        snap["dead_npcs_log"] = list(hg.simulation.dead_npcs)
        snap["event_history_size"] = len(getattr(hg.simulation, 'event_history', []))

        # Military / wars
        if hasattr(hg.simulation, 'military'):
            mil = hg.simulation.military
            snap["active_battles"] = len(getattr(mil, 'battles', []))
            snap["active_armies"] = len(getattr(mil, 'armies', []))

        # Construction projects
        if hasattr(hg.simulation, 'construction'):
            snap["construction_projects"] = len(
                getattr(hg.simulation.construction, 'projects', []))

        # World economy
        if hasattr(hg.simulation, 'world_market'):
            wm = hg.simulation.world_market
            market_data = {}
            for sname, sdata in getattr(wm, 'settlements', {}).items():
                market_data[sname] = {
                    "gold": getattr(sdata, 'gold', 0),
                    "population": getattr(sdata, 'population', 0),
                }
            snap["world_market"] = market_data

        # World effects (stores per settlement)
        if hasattr(hg.simulation, 'world_effects'):
            we = hg.simulation.world_effects
            stores_summary = {}
            for sname in getattr(we, '_stores', {}):
                store = we._stores[sname]
                stores_summary[sname] = {
                    "total_goods": sum(store.values()),
                    "item_count": len(store),
                }
            snap["settlement_stores"] = stores_summary

        # Population system
        if hasattr(hg.simulation, 'population'):
            pop = hg.simulation.population
            pop_data = {}
            for sname, sdata in pop.settlements.items():
                pop_data[sname] = {
                    "population": getattr(sdata, 'population', 0),
                    "births": getattr(sdata, 'births_today', 0),
                    "deaths": getattr(sdata, 'deaths_today', 0),
                }
            snap["population_data"] = pop_data

    # --- Vegetation system ---
    if hasattr(hg, 'simulation') and hasattr(hg.simulation, 'vegetation_sys'):
        veg = hg.simulation.vegetation_sys
        snap["vegetation_tracked_tiles"] = len(veg.tile_health)
        degraded = sum(1 for h in veg.tile_health.values() if h < 0.5)
        snap["vegetation_degraded_tiles"] = degraded

    # Ground items
    snap["ground_items"] = len(hg.world_mgr.ground_items)

    return snap


def compare_snapshots(prev, curr, tick):
    """Compare two snapshots and return a dict of changes."""
    changes = {}
    changes["tick"] = tick
    changes["time"] = curr["time_str"]
    changes["day"] = curr["day"]
    changes["season"] = curr["season"]

    # NPC births/deaths
    prev_names = prev["npc_names_alive"]
    curr_names = curr["npc_names_alive"]
    died = prev_names - curr_names
    born = curr_names - prev_names
    changes["npcs_died"] = list(died)
    changes["npcs_born"] = list(born)
    changes["npc_alive_delta"] = curr["npc_alive"] - prev["npc_alive"]

    # Job changes
    prev_jobs = prev["job_distribution"]
    curr_jobs = curr["job_distribution"]
    all_jobs = set(list(prev_jobs.keys()) + list(curr_jobs.keys()))
    job_deltas = {}
    for j in all_jobs:
        delta = curr_jobs.get(j, 0) - prev_jobs.get(j, 0)
        if delta != 0:
            job_deltas[j] = delta
    changes["job_changes"] = job_deltas

    # Action distribution changes
    changes["npc_actions"] = curr["npc_actions"]

    # NPC movement
    moved = 0
    for name in prev["npc_positions"]:
        if name in curr["npc_positions"]:
            px, py = prev["npc_positions"][name]
            cx, cy = curr["npc_positions"][name]
            if abs(px - cx) > 0.5 or abs(py - cy) > 0.5:
                moved += 1
    changes["npcs_moved"] = moved

    # Gold changes
    changes["npc_gold_delta"] = curr["npc_total_gold"] - prev["npc_total_gold"]

    # Creature changes
    changes["creature_delta"] = curr["creature_count"] - prev["creature_count"]
    prev_species = prev["creature_species"]
    curr_species = curr["creature_species"]
    all_species = set(list(prev_species.keys()) + list(curr_species.keys()))
    species_deltas = {}
    for sp in all_species:
        delta = curr_species.get(sp, 0) - prev_species.get(sp, 0)
        if delta != 0:
            species_deltas[sp] = delta
    changes["species_changes"] = species_deltas

    # Building changes
    building_deltas = {}
    for sname in set(list(prev["settlements"].keys()) + list(curr["settlements"].keys())):
        prev_b = prev["settlements"].get(sname, {}).get("buildings", 0)
        curr_b = curr["settlements"].get(sname, {}).get("buildings", 0)
        if prev_b != curr_b:
            building_deltas[sname] = curr_b - prev_b
    changes["building_changes"] = building_deltas

    # Kingdom treasury changes
    treasury_deltas = {}
    for kname in set(list(prev["kingdoms"].keys()) + list(curr["kingdoms"].keys())):
        prev_t = prev["kingdoms"].get(kname, {}).get("treasury", 0)
        curr_t = curr["kingdoms"].get(kname, {}).get("treasury", 0)
        if prev_t != curr_t:
            treasury_deltas[kname] = curr_t - prev_t
    changes["treasury_changes"] = treasury_deltas

    # Terrain changes
    terrain_deltas = {}
    all_tiles = set(list(prev["terrain_counts"].keys()) + list(curr["terrain_counts"].keys()))
    for t in all_tiles:
        delta = curr["terrain_counts"].get(t, 0) - prev["terrain_counts"].get(t, 0)
        if delta != 0:
            terrain_deltas[t] = delta
    changes["terrain_changes"] = terrain_deltas

    # Trade
    changes["active_caravans"] = curr.get("active_caravans", 0)

    # Events
    changes["active_events"] = curr.get("active_events", 0)
    changes["event_log_growth"] = (curr.get("event_log_size", 0)
                                   - prev.get("event_log_size", 0))

    # Construction
    changes["construction_projects"] = curr.get("construction_projects", 0)

    # Vegetation
    changes["vegetation_tracked"] = curr.get("vegetation_tracked_tiles", 0)
    changes["vegetation_degraded"] = curr.get("vegetation_degraded_tiles", 0)

    # Ground items
    changes["ground_items_delta"] = curr.get("ground_items", 0) - prev.get("ground_items", 0)

    return changes


def collect_event_log(hg):
    """Collect and return the current event log, then clear it."""
    if hasattr(hg, 'simulation'):
        log = list(hg.simulation.event_log)
        hg.simulation.event_log.clear()
        return log
    return []



# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("  WORLD EVOLUTION TEST")
    print("=" * 60)

    # Initialize
    print("\n[1/4] Initializing world (seed=42)...")
    t0 = time.time()
    hg = HeadlessGame(seed=42, mode='god', export_dir=OUTPUT_DIR)
    init_time = time.time() - t0
    print(f"  World initialized in {init_time:.1f}s")
    print(f"  World size: {hg.world.width}x{hg.world.height}")
    print(f"  NPCs: {len(hg.world_mgr.npcs)}")
    print(f"  Creatures: {len(hg.world_mgr.creatures)}")
    print(f"  Structures: {len(hg.world.structures)}")

    # Find a city to center screenshots on
    city = None
    for s in hg.world.structures:
        if s.kind == "city":
            city = s
            break
    if city is None:
        for s in hg.world.structures:
            if s.kind == "town":
                city = s
                break
    if city is None and hg.world.structures:
        city = hg.world.structures[0]

    if city:
        print(f"  Focus settlement: {city.name} ({city.kind}) at ({city.x}, {city.y})")
        hg.move_player(float(city.x), float(city.y))

    # Speed up time so daily systems actually trigger
    # Default: 1 tick = 1/30 sec game time. At speed=60, 1 tick = 2 sec game time.
    # DAY_LENGTH = 600s, so 300 ticks = 1 full day at speed=60.
    # 1000 ticks at speed=60 = ~3.3 game days.
    TIME_SPEED = 60
    hg.time_sys.speed = TIME_SPEED
    print(f"  Time speed: {TIME_SPEED}x (1 tick = {1/30 * TIME_SPEED:.1f}s game time)")
    print(f"  1000 ticks = ~{1000 / 30 * TIME_SPEED / 600:.1f} game days")

    # Configuration
    TOTAL_TICKS = 1000
    SNAPSHOT_INTERVAL = 100
    SCREENSHOT_TICKS = {0, 250, 500, 750, 1000}

    # Take baseline
    print("\n[2/4] Taking baseline measurements...")
    snapshots = []
    all_changes = []
    all_events = []

    baseline = take_snapshot(hg, "tick_0")
    snapshots.append(baseline)

    print(f"  Baseline: {baseline['npc_alive']} NPCs, "
          f"{baseline['creature_count']} creatures, "
          f"{len(baseline['settlements'])} settlements, "
          f"{len(baseline['kingdoms'])} kingdoms")

    # Take screenshot at tick 0
    if city:
        hg.move_player(float(city.x), float(city.y))
    path = hg.capture("gameplay", filename="evolution_tick_0000.png")
    print(f"  Screenshot: {path}")

    # Collect initial event log (clear it)
    collect_event_log(hg)

    # Run simulation
    print(f"\n[3/4] Running simulation for {TOTAL_TICKS} ticks...")
    sim_start = time.time()

    for tick in range(1, TOTAL_TICKS + 1):
        hg.tick(1)

        # Progress
        if tick % 50 == 0:
            elapsed = time.time() - sim_start
            tps = tick / elapsed if elapsed > 0 else 0
            print(f"  Tick {tick}/{TOTAL_TICKS} "
                  f"({elapsed:.1f}s, {tps:.1f} tps)")

        # Snapshot
        if tick % SNAPSHOT_INTERVAL == 0:
            events = collect_event_log(hg)
            all_events.append(events)

            snap = take_snapshot(hg, f"tick_{tick}")
            snapshots.append(snap)

            changes = compare_snapshots(snapshots[-2], snap, tick)
            all_changes.append(changes)

            # Summary
            print(f"    Snapshot at tick {tick}: "
                  f"alive={snap['npc_alive']}, "
                  f"creatures={snap['creature_count']}, "
                  f"died={len(changes['npcs_died'])}, "
                  f"moved={changes['npcs_moved']}, "
                  f"events={changes['event_log_growth']}")

        # Screenshots
        if tick in SCREENSHOT_TICKS:
            if city:
                hg.move_player(float(city.x), float(city.y))
            path = hg.capture("gameplay",
                              filename=f"evolution_tick_{tick:04d}.png")
            print(f"    Screenshot: {path}")

    sim_time = time.time() - sim_start
    total_tps = TOTAL_TICKS / sim_time if sim_time > 0 else 0

    print(f"\n  Simulation complete: {sim_time:.1f}s "
          f"({total_tps:.1f} ticks/sec)")

    # Generate report
    print("\n[4/4] Generating report...")
    timing = {
        "total_ticks": TOTAL_TICKS,
        "wall_time": sim_time,
        "tps": total_tps,
    }
    report_path = os.path.join(ROOT, "viewers", "evolution_report.md")
    report = generate_report(snapshots, all_changes, all_events,
                             timing, report_path)
    print(f"  Report saved to: {report_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)

    base = snapshots[0]
    final = snapshots[-1]
    print(f"  NPCs: {base['npc_alive']} -> {final['npc_alive']} "
          f"(died: {sum(len(ch['npcs_died']) for ch in all_changes)}, "
          f"born: {sum(len(ch['npcs_born']) for ch in all_changes)})")
    print(f"  Creatures: {base['creature_count']} -> {final['creature_count']}")
    print(f"  Day: {base['day']} -> {final['day']}")
    print(f"  Season: {base['season']} -> {final['season']}")

    total_events_count = sum(len(batch) for batch in all_events)
    print(f"  Total event log entries: {total_events_count}")
    total_moved = sum(ch["npcs_moved"] for ch in all_changes)
    print(f"  Total NPC movements: {total_moved}")

    print(f"\n  Report: {report_path}")
    print(f"  Screenshots: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
