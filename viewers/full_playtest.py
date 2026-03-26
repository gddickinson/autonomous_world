#!/usr/bin/env python3
"""Full multi-session playtest — plays the game multiple times as a mortal character.

Sessions: Fighter Explorer, Town Life Observer, Dungeon Delver,
Night Explorer, Kingdom Watcher.

All screenshots saved to viewers/full_playtest_output/
"""

import os
import sys
import random
import math
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUTPUT_DIR = os.path.join(ROOT, "viewers", "full_playtest_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
pygame.init()

from game.ui.screenshot import HeadlessGame
from game.settings import (
    TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT, DAY_LENGTH,
    WATER, SAND, GRASS, FOREST, DENSE_FOREST, MOUNTAIN, SNOW,
    ROAD, SWAMP, FARMLAND, STAIRS_DOWN, SHALLOW_WATER,
    DAWN_START, DAY_START, DUSK_START, NIGHT_START,
)

ALL_SCREENSHOTS = []
REPORT_LINES = []


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


def find_terrain(world, terrain_type, near_x, near_y, radius=300):
    best, best_dist = None, 999999
    step = 5
    for dy in range(-radius, radius, step):
        for dx in range(-radius, radius, step):
            x, y = near_x + dx, near_y + dy
            if 0 <= x < world.width and 0 <= y < world.height:
                if world.tiles[y][x] == terrain_type:
                    d = abs(dx) + abs(dy)
                    if d < best_dist:
                        best_dist, best = d, (x, y)
    return best


def find_special_structure(world, kinds=("ruins", "dungeon", "crypt")):
    for s in world.structures:
        if s.kind in kinds:
            return s
    return None


# ================================================================
# SESSION 1: The Fighter Explorer
# ================================================================
def session_1_fighter_explorer():
    log("\n" + "=" * 60)
    log("SESSION 1: THE FIGHTER EXPLORER")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="mortal", export_dir=OUTPUT_DIR, use_chunked=True)
    hg.player.char_class = "Fighter"
    hg.player.race = "Human"
    hg.player.name = "Thorn"

    sx, sy = hg.world.spawn_point
    log(f"  Spawn: ({sx}, {sy})")
    log(f"  Player: {hg.player.name}, {hg.player.race} {hg.player.char_class}")
    log(f"  HP: {hg.player.hp}/{hg.player.max_hp}, Level: {hg.player.level}")
    log(f"  Gold: {hg.player.gold}")

    # Starting position
    hg.move_player(float(sx), float(sy))
    save(hg, "S1_01_spawn_point")
    save(hg, "S1_02_character_sheet", view="character_sheet")
    save(hg, "S1_03_inventory", view="inventory")
    save(hg, "S1_04_quest_log", view="quest_log")

    # Check starting quest
    quests = hg.quest_sys.active_quests
    log(f"  Active quests: {len(quests)}")
    for q in quests:
        log(f"    - {q.title}: {q.description[:60]}...")

    # Find nearest settlement
    nearest = find_nearest_settlement(hg.world, sx, sy)
    if nearest:
        log(f"  Nearest settlement: {nearest.name} ({nearest.kind}) at ({nearest.x}, {nearest.y})")
        dist = math.hypot(nearest.x - sx, nearest.y - sy)
        log(f"  Distance: {dist:.0f} tiles")

        # Walk toward it (partial move)
        mid_x = (sx + nearest.x) / 2
        mid_y = (sy + nearest.y) / 2
        hg.move_player(mid_x, mid_y)
        hg.tick(20)
        save(hg, "S1_05_walking_to_settlement")

        # Arrive at settlement
        hg.move_player(float(nearest.x), float(nearest.y))
        hg.world.reveal_around(nearest.x, nearest.y, 30)
        hg.tick(10)
        save(hg, "S1_06_at_settlement")

    # Find and examine creatures nearby
    creatures_near = []
    for c in hg.world_mgr.creatures:
        d = math.hypot(c.x - hg.player.x, c.y - hg.player.y)
        if d < 100:
            creatures_near.append((d, c))
    creatures_near.sort(key=lambda x: x[0])

    log(f"  Creatures within 100 tiles: {len(creatures_near)}")
    for d, c in creatures_near[:10]:
        log(f"    - {c.kind}: HP={c.hp}/{c.max_hp}, DMG={c.damage}, "
            f"dist={d:.0f}, pos=({c.x:.0f},{c.y:.0f})")

    # Visit nearest creature for combat screenshot
    if creatures_near:
        _, target = creatures_near[0]
        hg.move_player(target.x + 1, target.y)
        hg.world.reveal_around(int(target.x), int(target.y), 15)
        save(hg, f"S1_07_near_creature_{target.kind}")

    # Check NPCs in settlement
    if nearest:
        hg.move_player(float(nearest.x), float(nearest.y))
        npcs_here = []
        for npc in hg.world_mgr.npcs:
            if not npc.alive:
                continue
            d = abs(npc.x - nearest.x) + abs(npc.y - nearest.y)
            if d < 30:
                npcs_here.append(npc)

        log(f"  NPCs near {nearest.name}: {len(npcs_here)}")
        for npc in npcs_here[:8]:
            job = getattr(npc, 'job', getattr(npc, 'profession', '?'))
            log(f"    - {npc.name}: {npc.race} {npc.char_class}, job={job}, "
                f"HP={npc.hp}/{npc.max_hp}")

        # Dialog with first NPC
        if npcs_here:
            npc = npcs_here[0]
            hg.move_player(float(npc.x), float(npc.y))
            try:
                npc.regenerate_dialog()
                hg.ui.open_dialog(npc)
                hg._draw_gameplay()
                hg.ui.draw_dialog()
                path = os.path.join(OUTPUT_DIR, "S1_08_npc_dialog.png")
                pygame.image.save(hg.screen, path)
                ALL_SCREENSHOTS.append(("S1_08_npc_dialog", path))
                log(f"  [screenshot] S1_08_npc_dialog.png")
                hg.ui.dialog_active = False
            except Exception as e:
                log(f"  Dialog error: {e}")

    # Advance 500 ticks, check XP/leveling
    old_xp = hg.player.xp
    old_level = hg.player.level
    hg.tick(500)
    log(f"  After 500 ticks: XP {old_xp} -> {hg.player.xp}, "
        f"Level {old_level} -> {hg.player.level}")
    save(hg, "S1_09_after_500_ticks")
    save(hg, "S1_10_world_map", view="world_map", zoom=1.0)

    log("  Session 1 complete.")
    return hg


# ================================================================
# SESSION 2: The Town Life Observer
# ================================================================
def session_2_town_life():
    log("\n" + "=" * 60)
    log("SESSION 2: THE TOWN LIFE OBSERVER")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="mortal", export_dir=OUTPUT_DIR, use_chunked=True)
    hg.player.name = "Observer"

    # Find a town to observe
    sx, sy = hg.world.spawn_point
    town = find_nearest_settlement(hg.world, sx, sy, kind="town")
    if not town:
        town = find_nearest_settlement(hg.world, sx, sy, kind="city")
    if not town:
        town = find_nearest_settlement(hg.world, sx, sy)

    if not town:
        log("  ERROR: No settlement found!")
        return hg

    log(f"  Observing: {town.name} ({town.kind}) at ({town.x}, {town.y})")
    hg.move_player(float(town.x), float(town.y))
    hg.world.reveal_around(town.x, town.y, 40)

    # Before snapshot
    save(hg, "S2_01_town_before")

    # Count NPCs and their activities before
    npcs_before = []
    for npc in hg.world_mgr.npcs:
        if not npc.alive:
            continue
        d = abs(npc.x - town.x) + abs(npc.y - town.y)
        if d < 40:
            action = getattr(npc, 'current_action', 'idle')
            npcs_before.append((npc.name, action, npc.x, npc.y))

    log(f"  NPCs before: {len(npcs_before)}")
    action_counts = {}
    for _, action, _, _ in npcs_before:
        action_counts[action] = action_counts.get(action, 0) + 1
    log(f"  Actions before: {action_counts}")

    # Capture kingdom info before
    kingdoms_before = {}
    if hasattr(hg, 'simulation') and hasattr(hg.simulation, 'governance'):
        for kname, kingdom in hg.simulation.governance.kingdoms.items():
            kingdoms_before[kname] = {
                "treasury": kingdom.treasury,
                "army_size": kingdom.army_size,
                "population": kingdom.population,
                "morale": kingdom.public_morale,
            }
        log(f"  Kingdoms: {len(kingdoms_before)}")
        for kn, kd in kingdoms_before.items():
            log(f"    - {kn}: treasury={kd['treasury']}, army={kd['army_size']}, "
                f"pop={kd['population']}, morale={kd['morale']}")

    # Advance 2000 ticks
    log("  Advancing 2000 ticks...")
    for batch in range(20):
        hg.tick(100)
    log("  Done advancing.")

    # After snapshot
    hg.move_player(float(town.x), float(town.y))
    save(hg, "S2_02_town_after_2000_ticks")

    # Check NPC activities after
    npcs_after = []
    for npc in hg.world_mgr.npcs:
        if not npc.alive:
            continue
        d = abs(npc.x - town.x) + abs(npc.y - town.y)
        if d < 40:
            action = getattr(npc, 'current_action', 'idle')
            npcs_after.append((npc.name, action, npc.x, npc.y))

    log(f"  NPCs after: {len(npcs_after)}")
    action_counts_after = {}
    for _, action, _, _ in npcs_after:
        action_counts_after[action] = action_counts_after.get(action, 0) + 1
    log(f"  Actions after: {action_counts_after}")

    # NPC movement check
    moved = 0
    for name_b, _, xb, yb in npcs_before:
        for name_a, _, xa, ya in npcs_after:
            if name_b == name_a:
                if abs(xa - xb) > 0.5 or abs(ya - yb) > 0.5:
                    moved += 1
                break
    log(f"  NPCs that moved: {moved}/{min(len(npcs_before), len(npcs_after))}")

    # Kingdom changes
    if hasattr(hg, 'simulation') and hasattr(hg.simulation, 'governance'):
        for kname, kingdom in hg.simulation.governance.kingdoms.items():
            before = kingdoms_before.get(kname, {})
            log(f"  Kingdom {kname}: treasury {before.get('treasury', '?')} -> {kingdom.treasury}, "
                f"army {before.get('army_size', '?')} -> {kingdom.army_size}")

    # Check terrain changes near settlement
    terrain_counts = {}
    for dy in range(-20, 21):
        for dx in range(-20, 21):
            tx, ty = town.x + dx, town.y + dy
            if 0 <= tx < hg.world.width and 0 <= ty < hg.world.height:
                t = hg.world.tiles[ty][tx]
                terrain_counts[t] = terrain_counts.get(t, 0) + 1
    log(f"  Terrain around town: {terrain_counts}")

    save(hg, "S2_03_world_map_after", view="world_map", zoom=1.0)

    # Time/season info
    log(f"  Time: {hg.time_sys.time_string}")
    log(f"  Season: {hg.time_sys.season}")
    log(f"  Day: {hg.time_sys.day}")

    log("  Session 2 complete.")
    return hg


# ================================================================
# SESSION 3: The Dungeon Delver
# ================================================================
def session_3_dungeon_delver():
    log("\n" + "=" * 60)
    log("SESSION 3: THE DUNGEON DELVER")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="mortal", export_dir=OUTPUT_DIR, use_chunked=True)
    hg.player.name = "Delver"
    hg.player.char_class = "Rogue"

    sx, sy = hg.world.spawn_point

    # Look for ruins/dungeon structures
    ruins = find_special_structure(hg.world,
        kinds=("ruins", "dungeon", "crypt", "undead_crypt",
               "ancient_ruins", "cave"))
    if ruins:
        log(f"  Found special location: {ruins.name} ({ruins.kind}) at ({ruins.x}, {ruins.y})")
        hg.move_player(float(ruins.x), float(ruins.y))
        hg.world.reveal_around(ruins.x, ruins.y, 20)
        save(hg, "S3_01_ruins_exterior")
    else:
        log("  No ruins/dungeon structure found in world.structures")
        # List all structure kinds
        kinds = set(s.kind for s in hg.world.structures)
        log(f"  Available structure kinds: {kinds}")

    # Search for STAIRS_DOWN in world tiles
    stairs_found = []
    search_radius = 500
    for dy in range(-search_radius, search_radius, 3):
        for dx in range(-search_radius, search_radius, 3):
            x, y = sx + dx, sy + dy
            if 0 <= x < hg.world.width and 0 <= y < hg.world.height:
                if hg.world.tiles[y][x] == STAIRS_DOWN:
                    stairs_found.append((x, y))

    log(f"  STAIRS_DOWN tiles found within {search_radius}: {len(stairs_found)}")
    if stairs_found:
        stx, sty = stairs_found[0]
        log(f"  First stairs at ({stx}, {sty})")
        hg.move_player(float(stx), float(sty))
        hg.world.reveal_around(stx, sty, 15)
        save(hg, "S3_02_stairs_down_location")

    # Try to generate a dungeon
    try:
        from game.world.dungeon_gen import generate_dungeon_for_location
        dungeon = generate_dungeon_for_location(sx, sy, hg.world.seed)
        log(f"  Dungeon generated: {dungeon.tiles.shape}")
        log(f"  Rooms: {len(dungeon.rooms)}")
        log(f"  Monsters: {len(dungeon.monsters)}")
        log(f"  Loot: {len(dungeon.loot)}")
        log(f"  Entrance: {dungeon.entrance}")

        for m in dungeon.monsters[:5]:
            log(f"    Monster: {m}")
        for l in dungeon.loot[:5]:
            log(f"    Loot: {l}")
        for r in dungeon.rooms[:5]:
            log(f"    Room: {r.room_type} at ({r.x},{r.y}) {r.w}x{r.h}")
    except Exception as e:
        log(f"  Dungeon generation error: {e}")

    # Check for monster spawns near any special locations
    if ruins:
        creatures_at_ruins = []
        for c in hg.world_mgr.creatures:
            d = math.hypot(c.x - ruins.x, c.y - ruins.y)
            if d < 30:
                creatures_at_ruins.append((d, c))
        creatures_at_ruins.sort()
        log(f"  Creatures near ruins: {len(creatures_at_ruins)}")
        for d, c in creatures_at_ruins[:5]:
            log(f"    - {c.kind}: HP={c.hp}, dist={d:.0f}")

    save(hg, "S3_03_world_overview", view="world_map", zoom=0.5)
    log("  Session 3 complete.")
    return hg


# ================================================================
# SESSION 4: The Night Explorer
# ================================================================
def session_4_night_explorer():
    log("\n" + "=" * 60)
    log("SESSION 4: THE NIGHT EXPLORER")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="mortal", export_dir=OUTPUT_DIR, use_chunked=True)
    hg.player.name = "Nightwalker"

    sx, sy = hg.world.spawn_point

    # Find a scenic spot with water nearby
    settlement = find_nearest_settlement(hg.world, sx, sy)
    if settlement:
        hg.move_player(float(settlement.x), float(settlement.y))
        hg.world.reveal_around(settlement.x, settlement.y, 25)
    else:
        hg.move_player(float(sx), float(sy))

    # Capture at different times of day
    time_points = [
        ("dawn", DAWN_START),
        ("morning", DAY_START),
        ("midday", 0.50),
        ("afternoon", 0.60),
        ("dusk", DUSK_START),
        ("evening", 0.75),
        ("night", NIGHT_START),
        ("midnight", 0.95),
    ]

    for name, frac in time_points:
        # Set time directly
        hg.time_sys.time = DAY_LENGTH * frac
        darkness = hg.time_sys.darkness
        log(f"  {name}: time_frac={frac:.2f}, darkness={darkness:.2f}")
        save(hg, f"S4_{name}_darkness{darkness:.2f}")

    # Check water rendering
    water_pos = find_terrain(hg.world, WATER, sx, sy, 200)
    if water_pos:
        wx, wy = water_pos
        hg.move_player(float(wx), float(wy))
        hg.world.reveal_around(wx, wy, 15)
        hg.time_sys.time = DAY_LENGTH * 0.50  # midday for water
        save(hg, "S4_water_midday")
        hg.time_sys.time = DAY_LENGTH * NIGHT_START
        save(hg, "S4_water_night")
        log(f"  Water found at ({wx}, {wy})")

    # Check shallow water
    shallow = find_terrain(hg.world, SHALLOW_WATER, sx, sy, 200)
    if shallow:
        shx, shy = shallow
        hg.move_player(float(shx), float(shy))
        hg.world.reveal_around(shx, shy, 15)
        hg.time_sys.time = DAY_LENGTH * 0.50
        save(hg, "S4_shallow_water")
        log(f"  Shallow water found at ({shx}, {shy})")
    else:
        log("  No shallow water found nearby")

    log("  Session 4 complete.")
    return hg


# ================================================================
# SESSION 5: Kingdom Watcher
# ================================================================
def session_5_kingdom_watcher():
    log("\n" + "=" * 60)
    log("SESSION 5: KINGDOM WATCHER")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="mortal", export_dir=OUTPUT_DIR, use_chunked=True)
    hg.player.name = "Chronicler"

    sx, sy = hg.world.spawn_point
    hg.move_player(float(sx), float(sy))

    # Record initial state
    initial_state = {}
    sim = hg.simulation

    if hasattr(sim, 'governance'):
        for kname, k in sim.governance.kingdoms.items():
            initial_state[kname] = {
                "treasury": k.treasury,
                "army_size": k.army_size,
                "population": k.population,
                "morale": k.public_morale,
                "settlements": list(k.settlements),
                "governing_style": k.governing_style,
            }
        log(f"  Kingdoms at start: {len(initial_state)}")
        for kn, kd in initial_state.items():
            log(f"    {kn}: treasury={kd['treasury']}, army={kd['army_size']}, "
                f"pop={kd['population']}, morale={kd['morale']}, "
                f"style={kd['governing_style']}, "
                f"settlements={kd['settlements']}")

    # Count initial living NPCs
    alive_before = sum(1 for n in hg.world_mgr.npcs if n.alive)
    creatures_before = len(hg.world_mgr.creatures)
    log(f"  NPCs alive: {alive_before}")
    log(f"  Creatures: {creatures_before}")

    save(hg, "S5_01_initial_state")
    save(hg, "S5_02_world_map_initial", view="world_map", zoom=0.5)

    # Advance 5000 ticks in batches
    log("  Advancing 5000 ticks (50 batches of 100)...")
    events_log = []
    for batch in range(50):
        hg.tick(100)
        # Check for events/notifications
        for notif in hg.notifications.notifications:
            events_log.append(f"  Tick {(batch+1)*100}: {notif.text}")

    log(f"  Simulation events captured: {len(events_log)}")
    for ev in events_log[:20]:
        log(ev)
    if len(events_log) > 20:
        log(f"  ... and {len(events_log) - 20} more events")

    # Record final state
    log(f"\n  === AFTER 5000 TICKS ===")
    log(f"  Time: {hg.time_sys.time_string}")
    log(f"  Day: {hg.time_sys.day}, Season: {hg.time_sys.season}")

    alive_after = sum(1 for n in hg.world_mgr.npcs if n.alive)
    creatures_after = len(hg.world_mgr.creatures)
    log(f"  NPCs alive: {alive_before} -> {alive_after} "
        f"(delta: {alive_after - alive_before})")
    log(f"  Creatures: {creatures_before} -> {creatures_after}")

    # Kingdom changes
    if hasattr(sim, 'governance'):
        for kname, k in sim.governance.kingdoms.items():
            before = initial_state.get(kname, {})
            changes = []
            if k.treasury != before.get("treasury", 0):
                changes.append(f"treasury: {before.get('treasury', '?')} -> {k.treasury}")
            if k.army_size != before.get("army_size", 0):
                changes.append(f"army: {before.get('army_size', '?')} -> {k.army_size}")
            if k.population != before.get("population", 0):
                changes.append(f"pop: {before.get('population', '?')} -> {k.population}")
            if k.public_morale != before.get("morale", 50):
                changes.append(f"morale: {before.get('morale', '?')} -> {k.public_morale}")
            sett_now = list(k.settlements)
            if set(sett_now) != set(before.get("settlements", [])):
                changes.append(f"settlements changed")
            status = " | ".join(changes) if changes else "NO CHANGE"
            log(f"    {kname}: {status}")

    # Check dead NPCs
    dead_npcs = [n for n in hg.world_mgr.npcs if not n.alive]
    log(f"  Dead NPCs: {len(dead_npcs)}")
    for n in dead_npcs[:5]:
        cause = getattr(n, 'death_cause', 'unknown')
        log(f"    - {n.name} ({n.char_class}): cause={cause}")

    # Check NPC activities distribution
    activity_dist = {}
    for n in hg.world_mgr.npcs:
        if n.alive:
            action = getattr(n, 'current_action', 'idle')
            activity_dist[action] = activity_dist.get(action, 0) + 1
    log(f"  NPC activity distribution:")
    for act, cnt in sorted(activity_dist.items(), key=lambda x: -x[1]):
        log(f"    {act}: {cnt}")

    # Check trade events
    if hasattr(sim, 'trade'):
        caravans = getattr(sim.trade, 'active_caravans', [])
        log(f"  Active caravans: {len(caravans)}")
        completed = getattr(sim.trade, 'completed_trades', 0)
        log(f"  Completed trades: {completed}")

    # Check construction
    if hasattr(sim, 'construction'):
        projects = getattr(sim.construction, 'active_projects', [])
        completed_builds = getattr(sim.construction, 'completed_projects', 0)
        log(f"  Active construction: {len(projects)}")
        log(f"  Completed builds: {completed_builds}")

    save(hg, "S5_03_after_5000_ticks")
    save(hg, "S5_04_world_map_after", view="world_map", zoom=0.5)
    save(hg, "S5_05_character_sheet", view="character_sheet")

    log("  Session 5 complete.")
    return hg


# ================================================================
# MAIN
# ================================================================
def main():
    log("=" * 60)
    log("FULL PLAYTEST — AUTONOMOUS WORLD")
    log("=" * 60)

    sessions = [
        ("Session 1: Fighter Explorer", session_1_fighter_explorer),
        ("Session 2: Town Life Observer", session_2_town_life),
        ("Session 3: Dungeon Delver", session_3_dungeon_delver),
        ("Session 4: Night Explorer", session_4_night_explorer),
        ("Session 5: Kingdom Watcher", session_5_kingdom_watcher),
    ]

    for name, func in sessions:
        try:
            func()
        except Exception as e:
            log(f"\n  ERROR in {name}: {e}")
            traceback.print_exc()
            REPORT_LINES.append(f"  Traceback: {traceback.format_exc()}")

    # Write report log
    report_path = os.path.join(OUTPUT_DIR, "playtest_log.txt")
    with open(report_path, "w") as f:
        f.write("\n".join(REPORT_LINES))
    log(f"\nReport log saved to {report_path}")
    log(f"Total screenshots: {len(ALL_SCREENSHOTS)}")

    # Print screenshot list
    log("\nScreenshot manifest:")
    for name, path in ALL_SCREENSHOTS:
        log(f"  {name}: {path}")


if __name__ == "__main__":
    main()
