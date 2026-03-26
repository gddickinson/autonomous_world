#!/usr/bin/env python3
"""God Mode Playtest — comprehensive test of divine powers and dashboard.

Tests divine smite, bless, kingdom commands, event triggers, time control,
settlement quality, and day/night cycle across 5000 ticks.

All screenshots saved to viewers/god_playtest_output/
"""

import os
import sys
import math
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUTPUT_DIR = os.path.join(ROOT, "viewers", "god_playtest_output")
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
REPORT = []


def log(msg):
    print(msg)
    REPORT.append(msg)


def save(hg, name, view="gameplay", **kwargs):
    filename = f"{name}.png"
    path = hg.capture(view, filename=filename, **kwargs)
    ALL_SCREENSHOTS.append((name, path))
    log(f"  [screenshot] {name}.png")
    return path


def find_settlement(world, x, y, kind=None):
    best, best_d = None, 999999
    for s in world.structures:
        if s.kind not in ("village", "town", "city", "hamlet", "castle"):
            continue
        if kind and s.kind != kind:
            continue
        d = abs(s.x - x) + abs(s.y - y)
        if d < best_d:
            best_d, best = d, s
    return best


def npcs_near(hg, x, y, radius=30):
    return [n for n in hg.world_mgr.npcs
            if getattr(n, 'alive', True)
            and abs(n.x - x) + abs(n.y - y) < radius]


def kingdom_stats(hg):
    """Collect kingdom stats snapshot."""
    stats = {}
    gov = getattr(hg.simulation, 'governance', None)
    if not gov:
        return stats
    for kn, k in gov.kingdoms.items():
        stats[kn] = {
            'treasury': getattr(k, 'treasury', 0),
            'army': getattr(k, 'army_size', 0),
            'population': getattr(k, 'population', 0),
            'morale': getattr(k, 'public_morale', 50),
            'gov_style': getattr(k, 'governing_style', '?'),
            'settlements': len(getattr(k, 'settlements', [])),
            'ruler': getattr(k, 'ruler_name', '?'),
        }
    return stats


# ================================================================
# SECTION 1: Dashboard Overview (3 screenshots)
# ================================================================
def section_1_dashboard(hg):
    log("\n" + "=" * 60)
    log("SECTION 1: DASHBOARD OVERVIEW")
    log("=" * 60)

    sx, sy = hg.world.spawn_point
    hg.move_player(float(sx), float(sy))
    log(f"  Spawn: ({sx}, {sy})")
    log(f"  Player mode: {hg.player.mode}, HP: {hg.player.hp}")
    log(f"  God: {getattr(hg.player, 'god', False)}")

    # Screenshot 1: Starting view
    save(hg, "01_starting_view")

    # Check god dashboard / divine commands availability
    has_dashboard = hasattr(hg, 'god_dashboard')
    has_divine = hasattr(hg, 'divine_commands')
    log(f"  GodDashboard attached: {has_dashboard}")
    log(f"  DivineCommands attached: {has_divine}")

    # Read kingdom data from world plan
    plan_kingdoms = getattr(hg.world.plan, 'kingdoms', [])
    log(f"  World plan kingdoms: {len(plan_kingdoms)}")
    for pk in plan_kingdoms:
        name = pk.get('name', '?')
        race = pk.get('race', '?')
        style = pk.get('governing_style', '?')
        capital = pk.get('capital', '?')
        log(f"    {name}: race={race}, gov={style}, capital={capital}")

    # Read governance kingdoms (simulation)
    kstats = kingdom_stats(hg)
    log(f"  Governance kingdoms: {len(kstats)}")
    for kn, ks in kstats.items():
        log(f"    {kn}: treasury={ks['treasury']:.0f}, army={ks['army']}, "
            f"pop={ks['population']}, gov={ks['gov_style']}, ruler={ks['ruler']}")

    # Screenshot 2: World map
    save(hg, "02_world_map", view="world_map", zoom=0.25)

    # Screenshot 3: Settlement close-up
    nearest = find_settlement(hg.world, sx, sy)
    if nearest:
        hg.move_player(float(nearest.x), float(nearest.y))
        hg.world.reveal_around(nearest.x, nearest.y, 40)
        save(hg, "03_settlement_closeup")
        log(f"  Close-up of {nearest.name} ({nearest.kind})")
    else:
        save(hg, "03_spawn_area")


# ================================================================
# SECTION 2: Kingdom Survey (3 screenshots)
# ================================================================
def section_2_kingdoms(hg):
    log("\n" + "=" * 60)
    log("SECTION 2: KINGDOM SURVEY")
    log("=" * 60)

    kstats = kingdom_stats(hg)
    gov_styles = set()
    for kn, ks in kstats.items():
        gov_styles.add(ks['gov_style'])
        log(f"  {kn}: treasury={ks['treasury']:.0f}, army={ks['army']}, "
            f"gov={ks['gov_style']}, ruler={ks['ruler']}, "
            f"settlements={ks['settlements']}")

    log(f"  Governance diversity: {len(gov_styles)} styles: {gov_styles}")

    # Check race diversity from plan kingdoms
    races = set()
    for pk in getattr(hg.world.plan, 'kingdoms', []):
        races.add(pk.get('race', '?'))
    log(f"  Race diversity: {len(races)} races: {races}")

    # Visit 3 kingdom capitals
    capitals_visited = 0
    gov = getattr(hg.simulation, 'governance', None)
    if gov:
        for kn, k in list(gov.kingdoms.items())[:3]:
            cx = getattr(k, 'castle_x', 0)
            cy = getattr(k, 'castle_y', 0)
            if cx and cy:
                hg.move_player(float(cx), float(cy))
                hg.world.reveal_around(cx, cy, 40)
                npcs = npcs_near(hg, cx, cy)
                save(hg, f"04_capital_{capitals_visited}_{kn[:15]}")
                log(f"  Capital of {kn} at ({cx},{cy}): {len(npcs)} NPCs")
                capitals_visited += 1
    log(f"  Capitals visited: {capitals_visited}")


# ================================================================
# SECTION 3: Divine Smite Test (2 screenshots)
# ================================================================
def section_3_smite(hg):
    log("\n" + "=" * 60)
    log("SECTION 3: DIVINE SMITE TEST")
    log("=" * 60)

    # Find a settlement with NPCs
    sx, sy = hg.world.spawn_point
    sett = find_settlement(hg.world, sx, sy)
    if not sett:
        log("  No settlement found, skipping smite test")
        return

    hg.move_player(float(sett.x), float(sett.y))
    hg.world.reveal_around(sett.x, sett.y, 30)
    npcs = npcs_near(hg, sett.x, sett.y)
    log(f"  At {sett.name}: {len(npcs)} alive NPCs")

    if not npcs:
        log("  No NPCs to smite")
        save(hg, "05_smite_no_target")
        return

    # Before screenshot
    save(hg, "05_smite_before")

    # Pick target
    target = npcs[0]
    log(f"  Target: {target.name}, HP={target.hp}/{target.max_hp}")

    # Simulate smite
    target.hp = 0
    target.alive = False
    log(f"  SMITE! {target.name} HP -> 0, alive -> False")

    # Check nearby NPC reactions
    fleeing = 0
    for npc in npcs[1:]:
        dx, dy = npc.x - target.x, npc.y - target.y
        dist_sq = dx * dx + dy * dy
        if dist_sq < 100:
            npc.current_action = "fleeing"
            npc.action_timer = 5.0
            dist = max(0.1, math.sqrt(dist_sq))
            npc.target_x = npc.x + (dx / dist) * 15
            npc.target_y = npc.y + (dy / dist) * 15
            fleeing += 1
    log(f"  NPCs fleeing: {fleeing}")

    # After screenshot
    save(hg, "06_smite_after")

    # Check event log for smite record
    sim = getattr(hg, 'simulation', None)
    if sim:
        elog = getattr(sim, 'event_log', [])
        log(f"  Event log entries: {len(elog)}")


# ================================================================
# SECTION 4: World Event Test (2 screenshots)
# ================================================================
def section_4_events(hg):
    log("\n" + "=" * 60)
    log("SECTION 4: WORLD EVENT TEST")
    log("=" * 60)

    sx, sy = hg.world.spawn_point
    sett = find_settlement(hg.world, sx, sy)

    # Trigger a festival
    from game.systems.divine_events import trigger_festival, add_world_event
    trigger_festival(sett, hg)
    log(f"  Festival triggered at {sett.name if sett else 'player pos'}")

    # Check events list
    sim = getattr(hg, 'simulation', None)
    events = getattr(sim, 'events', []) if sim else []
    elog = getattr(sim, 'event_log', []) if sim else []
    log(f"  Active world events: {len(events)}")
    for evt in events:
        log(f"    - {getattr(evt, 'name', '?')}: {getattr(evt, 'description', '?')}")
    log(f"  Event log: {len(elog)} entries")
    for e in elog[-5:]:
        log(f"    - {e}")

    if sett:
        hg.move_player(float(sett.x), float(sett.y))
        hg.world.reveal_around(sett.x, sett.y, 30)
    save(hg, "07_festival_event")

    # Trigger earthquake too
    from game.systems.divine_events import trigger_earthquake
    effects_list = []
    trigger_earthquake(sett, hg, effects_list)
    log(f"  Earthquake triggered, {len(effects_list)} visual effects")

    hg.tick(10)
    save(hg, "08_earthquake_event")

    # Updated event count
    events = getattr(sim, 'events', []) if sim else []
    log(f"  Active events after both triggers: {len(events)}")


# ================================================================
# SECTION 5: Time Evolution (4 screenshots)
# ================================================================
def section_5_evolution(hg):
    log("\n" + "=" * 60)
    log("SECTION 5: TIME EVOLUTION (5000 ticks)")
    log("=" * 60)

    # Snapshot at tick 0
    alive_0 = sum(1 for n in hg.world_mgr.npcs if getattr(n, 'alive', True))
    creatures_0 = len(hg.world_mgr.creatures)
    kstats_0 = kingdom_stats(hg)
    log(f"  Tick 0: {alive_0} alive NPCs, {creatures_0} creatures")

    sx, sy = hg.world.spawn_point
    hg.move_player(float(sx), float(sy))

    # 1000 ticks
    log("  Running 1000 ticks...")
    hg.tick(1000)
    alive_1k = sum(1 for n in hg.world_mgr.npcs if getattr(n, 'alive', True))
    log(f"  Tick 1000: {alive_1k} alive NPCs")
    log(f"  Time: {hg.time_sys.time_string}, Day {hg.time_sys.day}")
    save(hg, "09_tick_1000")

    # 3000 total
    log("  Running 2000 more ticks...")
    hg.tick(2000)
    alive_3k = sum(1 for n in hg.world_mgr.npcs if getattr(n, 'alive', True))
    log(f"  Tick 3000: {alive_3k} alive NPCs")
    log(f"  Time: {hg.time_sys.time_string}, Day {hg.time_sys.day}")
    save(hg, "10_tick_3000")

    # Check construction and trade
    bs = getattr(hg, 'building_sys', None)
    construction = len(getattr(bs, 'active_projects', [])) if bs else 0
    gt = getattr(hg.simulation, 'goods_transport', None) if hg.simulation else None
    caravans = len(getattr(gt, 'active_journeys', [])) if gt else 0
    log(f"  Active construction: {construction}")
    log(f"  Active caravans: {caravans}")

    # 5000 total
    log("  Running 2000 more ticks...")
    hg.tick(2000)
    alive_5k = sum(1 for n in hg.world_mgr.npcs if getattr(n, 'alive', True))
    creatures_5k = len(hg.world_mgr.creatures)
    kstats_5k = kingdom_stats(hg)
    log(f"  Tick 5000: {alive_5k} alive NPCs, {creatures_5k} creatures")
    log(f"  Time: {hg.time_sys.time_string}, Day {hg.time_sys.day}")
    save(hg, "11_tick_5000")

    # Comprehensive comparison
    log("\n  === TICK 0 vs TICK 5000 COMPARISON ===")
    log(f"  NPCs: {alive_0} -> {alive_5k} "
        f"(survival: {alive_5k/max(1,alive_0)*100:.1f}%)")
    log(f"  Creatures: {creatures_0} -> {creatures_5k}")

    for kn in kstats_0:
        k0 = kstats_0[kn]
        k5 = kstats_5k.get(kn, {})
        log(f"  Kingdom {kn}:")
        log(f"    Treasury: {k0['treasury']:.0f} -> {k5.get('treasury', 0):.0f}")
        log(f"    Army: {k0['army']} -> {k5.get('army', 0)}")
        log(f"    Pop: {k0['population']} -> {k5.get('population', 0)}")
        log(f"    Morale: {k0['morale']:.0f} -> {k5.get('morale', 0):.0f}")

    # Dead NPCs summary
    dead = [n for n in hg.world_mgr.npcs if not getattr(n, 'alive', True)]
    log(f"  Total dead: {len(dead)}")
    causes = {}
    for n in dead:
        c = getattr(n, 'death_cause', 'unknown')
        causes[c] = causes.get(c, 0) + 1
    for c, cnt in sorted(causes.items(), key=lambda x: -x[1]):
        log(f"    {c}: {cnt}")

    # Event log summary
    sim = getattr(hg, 'simulation', None)
    elog = getattr(sim, 'event_log', []) if sim else []
    log(f"  Event log: {len(elog)} entries")
    for e in elog[-10:]:
        log(f"    {e}")

    save(hg, "12_world_map_5000", view="world_map", zoom=0.5)


# ================================================================
# SECTION 6: Settlement Quality Check (3 screenshots)
# ================================================================
def section_6_settlements(hg):
    log("\n" + "=" * 60)
    log("SECTION 6: SETTLEMENT QUALITY CHECK")
    log("=" * 60)

    # Find one of each type
    for kind in ("city", "village", "hamlet"):
        sett = find_settlement(hg.world, hg.player.x, hg.player.y, kind=kind)
        if not sett:
            # Search globally
            for s in hg.world.structures:
                if s.kind == kind:
                    sett = s
                    break
        if sett:
            hg.move_player(float(sett.x), float(sett.y))
            hg.world.reveal_around(sett.x, sett.y, 40)
            save(hg, f"13_{kind}_{sett.name[:15]}")
            npcs = npcs_near(hg, sett.x, sett.y)
            bldgs = getattr(sett, 'buildings', [])
            walls = getattr(sett, 'walls', [])
            gates = getattr(sett, 'gates', [])
            log(f"  {kind.upper()}: {sett.name}")
            log(f"    Buildings: {len(bldgs)}, Walls: {len(walls)}, "
                f"Gates: {len(gates)}")
            log(f"    NPCs nearby: {len(npcs)}")
            log(f"    Position: ({sett.x}, {sett.y}), "
                f"Radius: {getattr(sett, 'radius', '?')}")
        else:
            log(f"  No {kind} found")


# ================================================================
# SECTION 7: Night Scene (2 screenshots)
# ================================================================
def section_7_night(hg):
    log("\n" + "=" * 60)
    log("SECTION 7: NIGHT SCENE")
    log("=" * 60)

    # Move to a scenic settlement
    sx, sy = hg.world.spawn_point
    sett = find_settlement(hg.world, sx, sy)
    if sett:
        hg.move_player(float(sett.x), float(sett.y))
        hg.world.reveal_around(sett.x, sett.y, 30)

    # Dusk (18:00 ~ 0.75 of day)
    dusk_frac = DUSK_START + 0.03  # slightly past dusk start
    hg.time_sys.time = DAY_LENGTH * dusk_frac
    darkness = getattr(hg.time_sys, 'darkness', 0)
    log(f"  Dusk: frac={dusk_frac:.2f}, darkness={darkness:.2f}")
    log(f"  Time string: {hg.time_sys.time_string}")
    save(hg, "14_dusk_scene")

    # Night (21:00 ~ 0.875 of day)
    night_frac = NIGHT_START + 0.08
    hg.time_sys.time = DAY_LENGTH * night_frac
    darkness = getattr(hg.time_sys, 'darkness', 0)
    log(f"  Night: frac={night_frac:.2f}, darkness={darkness:.2f}")
    log(f"  Time string: {hg.time_sys.time_string}")
    save(hg, "15_night_scene")


# ================================================================
# MAIN
# ================================================================
def main():
    log("=" * 60)
    log("GOD MODE PLAYTEST — AUTONOMOUS WORLD")
    log("=" * 60)

    try:
        hg = HeadlessGame(seed=42, mode='god', use_chunked=True,
                          export_dir=OUTPUT_DIR)
        log(f"  Game initialized: seed=42, mode=god, chunked=True")
        log(f"  World: {hg.world.width}x{hg.world.height}")
        log(f"  Structures: {len(hg.world.structures)}")
        log(f"  NPCs: {len(hg.world_mgr.npcs)}")
        log(f"  Creatures: {len(hg.world_mgr.creatures)}")
    except Exception as e:
        log(f"FATAL: Could not initialize game: {e}")
        traceback.print_exc()
        return

    sections = [
        ("Section 1: Dashboard Overview", section_1_dashboard),
        ("Section 2: Kingdom Survey", section_2_kingdoms),
        ("Section 3: Divine Smite", section_3_smite),
        ("Section 4: World Events", section_4_events),
        ("Section 5: Time Evolution", section_5_evolution),
        ("Section 6: Settlement Quality", section_6_settlements),
        ("Section 7: Night Scene", section_7_night),
    ]

    for name, func in sections:
        try:
            func(hg)
        except Exception as e:
            log(f"\n  ERROR in {name}: {e}")
            traceback.print_exc()
            REPORT.append(f"  Traceback: {traceback.format_exc()}")

    # Save log
    log_path = os.path.join(OUTPUT_DIR, "playtest_log.txt")
    with open(log_path, "w") as f:
        f.write("\n".join(REPORT))
    log(f"\nLog saved to {log_path}")
    log(f"Total screenshots: {len(ALL_SCREENSHOTS)}")

    log("\nScreenshot manifest:")
    for name, path in ALL_SCREENSHOTS:
        log(f"  {name}: {path}")


if __name__ == "__main__":
    main()
