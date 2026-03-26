#!/usr/bin/env python3
"""Final multi-session playtest — 6 game sessions with different objectives.

Sessions: New Adventurer, Wizard Explorer, God Mode Observer,
The Long Game, Crafter & Trader, Night & Day.

All screenshots saved to viewers/final_playtest_output/
"""

import os
import sys
import random
import math
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUTPUT_DIR = os.path.join(ROOT, "viewers", "final_playtest_output")
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
# SESSION 1: The New Adventurer (Human Fighter, mortal, seed 42)
# ================================================================
def session_1_new_adventurer():
    log("\n" + "=" * 60)
    log("SESSION 1: THE NEW ADVENTURER (Human Fighter, seed 42)")
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
    log(f"  Gold: {hg.player.gold}")

    hg.move_player(float(sx), float(sy))
    save(hg, "S1_01_spawn")
    save(hg, "S1_02_character_sheet", view="character_sheet")

    # Check starting quests
    quests = hg.quest_sys.active_quests
    log(f"  Active quests: {len(quests)}")
    for q in quests:
        log(f"    - {q.title}: {q.description[:80]}")

    # Walk to nearest settlement and talk to NPCs
    nearest = find_nearest_settlement(hg.world, sx, sy)
    if nearest:
        log(f"  Nearest settlement: {nearest.name} ({nearest.kind}) "
            f"at ({nearest.x}, {nearest.y})")
        hg.move_player(float(nearest.x), float(nearest.y))
        hg.world.reveal_around(nearest.x, nearest.y, 30)
        hg.tick(20)
        save(hg, "S1_03_at_settlement")

        # Check NPCs: class/greeting/job
        npcs_here = [n for n in hg.world_mgr.npcs if n.alive
                     and abs(n.x - nearest.x) + abs(n.y - nearest.y) < 30]
        log(f"  NPCs near {nearest.name}: {len(npcs_here)}")
        for npc in npcs_here[:8]:
            job = getattr(npc, 'job', getattr(npc, 'profession', '?'))
            log(f"    - {npc.name}: {npc.race} {npc.char_class}, job={job}")

        # Dialog with first NPC
        if npcs_here:
            npc = npcs_here[0]
            hg.move_player(float(npc.x), float(npc.y))
            try:
                npc.regenerate_dialog()
                hg.ui.open_dialog(npc)
                hg._draw_gameplay()
                hg.ui.draw_dialog()
                path = os.path.join(OUTPUT_DIR, "S1_04_npc_dialog.png")
                pygame.image.save(hg.screen, path)
                ALL_SCREENSHOTS.append(("S1_04_npc_dialog", path))
                log(f"  [screenshot] S1_04_npc_dialog.png")
                hg.ui.dialog_active = False
            except Exception as e:
                log(f"  Dialog error: {e}")

    # Fight creatures near spawn
    creatures_near = sorted(
        [(math.hypot(c.x - hg.player.x, c.y - hg.player.y), c)
         for c in hg.world_mgr.creatures],
        key=lambda x: x[0])[:10]
    log(f"  Nearest creatures:")
    for d, c in creatures_near[:5]:
        log(f"    - {c.kind}: HP={c.hp}/{c.max_hp}, dist={d:.0f}")
    if creatures_near:
        _, target = creatures_near[0]
        hg.move_player(target.x + 1, target.y)
        hg.world.reveal_around(int(target.x), int(target.y), 15)
        save(hg, f"S1_05_combat_{target.kind}")

    # Check sound system
    sound_init = pygame.mixer.get_init()
    log(f"  Sound system initialized: {sound_init is not None}")

    # Advance 500 ticks
    old_xp, old_level = hg.player.xp, hg.player.level
    hg.tick(500)
    log(f"  After 500 ticks: XP {old_xp}->{hg.player.xp}, "
        f"Level {old_level}->{hg.player.level}")
    save(hg, "S1_06_after_500_ticks")
    save(hg, "S1_07_quest_log", view="quest_log")
    log("  Session 1 complete.")


# ================================================================
# SESSION 2: The Wizard Explorer (Elf Wizard, mortal, seed 123)
# ================================================================
def session_2_wizard_explorer():
    log("\n" + "=" * 60)
    log("SESSION 2: THE WIZARD EXPLORER (Elf Wizard, seed 123)")
    log("=" * 60)

    hg = HeadlessGame(seed=123, mode="mortal", export_dir=OUTPUT_DIR,
                      use_chunked=True)
    hg.player.char_class = "Wizard"
    hg.player.race = "Elf"
    hg.player.name = "Elara"
    hg.player.is_spellcaster = True
    hg.player.max_mana = 50
    hg.player.mana = 50

    sx, sy = hg.world.spawn_point
    log(f"  Spawn: ({sx}, {sy})")
    log(f"  Player: {hg.player.name}, {hg.player.race} {hg.player.char_class}")

    hg.move_player(float(sx), float(sy))
    save(hg, "S2_01_wizard_spawn")
    save(hg, "S2_02_wizard_character", view="character_sheet")

    # Check spells
    spells = getattr(hg.player, 'known_spells', [])
    log(f"  Known spells: {len(spells)}")
    for s in spells[:8]:
        log(f"    - {s}")

    # Visit dungeon entrance at ruins
    ruins = find_special_structure(hg.world,
        kinds=("ruins", "dungeon", "crypt", "undead_crypt",
               "ancient_ruins", "cave"))
    if ruins:
        log(f"  Found: {ruins.name} ({ruins.kind}) at ({ruins.x}, {ruins.y})")
        hg.move_player(float(ruins.x), float(ruins.y))
        hg.world.reveal_around(ruins.x, ruins.y, 20)
        save(hg, "S2_03_ruins")
    else:
        kinds = set(s.kind for s in hg.world.structures)
        log(f"  No ruins found. Structure kinds: {kinds}")

    # Check biome variety: find desert, tundra, snow, swamp
    biome_checks = [
        ("desert/sand", SAND), ("swamp", SWAMP), ("snow", SNOW),
        ("forest", FOREST), ("mountain", MOUNTAIN), ("water", WATER),
    ]
    for bname, btype in biome_checks:
        pos = find_terrain(hg.world, btype, sx, sy, 500)
        if pos:
            log(f"  Biome {bname}: found at {pos}")
        else:
            log(f"  Biome {bname}: NOT found within 500 tiles")

    # Visit water for water rendering check
    water_pos = find_terrain(hg.world, WATER, sx, sy, 300)
    if water_pos:
        hg.move_player(float(water_pos[0]), float(water_pos[1]))
        hg.world.reveal_around(water_pos[0], water_pos[1], 15)
        save(hg, "S2_04_water_rendering")
        log(f"  Water at {water_pos}")

    # Advance 500 ticks
    hg.tick(500)
    save(hg, "S2_05_after_500_ticks")
    save(hg, "S2_06_world_map", view="world_map", zoom=0.5)
    log("  Session 2 complete.")


# ================================================================
# SESSION 3: God Mode Observer (god mode, seed 42)
# ================================================================
def session_3_god_mode():
    log("\n" + "=" * 60)
    log("SESSION 3: GOD MODE OBSERVER (seed 42)")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="god", export_dir=OUTPUT_DIR,
                      use_chunked=True)
    sx, sy = hg.world.spawn_point
    log(f"  Spawn: ({sx}, {sy}), God mode active")
    log(f"  HP: {hg.player.hp}, ATK: {hg.player.attack_damage}")

    hg.move_player(float(sx), float(sy))
    save(hg, "S3_01_god_overview")
    save(hg, "S3_02_god_world_map", view="world_map", zoom=0.25)

    # Visit settlements and check walls/gates/towers
    settlements = [s for s in hg.world.structures
                   if s.kind in ("village", "town", "city", "castle")]
    log(f"  Settlements: {len(settlements)}")
    for i, s in enumerate(settlements[:4]):
        hg.move_player(float(s.x), float(s.y))
        hg.world.reveal_around(s.x, s.y, 40)
        save(hg, f"S3_03_settlement_{i}_{s.kind}_{s.name[:10]}")
        # Check NPC profession sprites
        npcs = [n for n in hg.world_mgr.npcs if n.alive
                and abs(n.x - s.x) + abs(n.y - s.y) < 30]
        jobs = {}
        for n in npcs:
            j = getattr(n, 'job', getattr(n, 'profession', 'unknown'))
            jobs[j] = jobs.get(j, 0) + 1
        log(f"  {s.name} ({s.kind}): {len(npcs)} NPCs, jobs={jobs}")
        # Check buildings
        bldgs = getattr(s, 'buildings', [])
        log(f"    Buildings: {len(bldgs)}")

    # Kingdom overview
    if hasattr(hg.simulation, 'governance'):
        for kname, k in hg.simulation.governance.kingdoms.items():
            log(f"  Kingdom {kname}: treasury={k.treasury}, "
                f"army={k.army_size}, pop={k.population}, "
                f"morale={k.public_morale}")

    # Advance 1000 ticks at high speed
    log("  Advancing 1000 ticks...")
    alive_before = sum(1 for n in hg.world_mgr.npcs if n.alive)
    hg.tick(1000)
    alive_after = sum(1 for n in hg.world_mgr.npcs if n.alive)
    log(f"  NPCs: {alive_before} -> {alive_after}")

    # Check kingdom changes after ticks
    if hasattr(hg.simulation, 'governance'):
        for kname, k in hg.simulation.governance.kingdoms.items():
            log(f"  Kingdom {kname} (after): treasury={k.treasury}, "
                f"army={k.army_size}")

    save(hg, "S3_04_god_after_1000_ticks")
    save(hg, "S3_05_god_world_map_after", view="world_map", zoom=0.5)
    log("  Session 3 complete.")


# ================================================================
# SESSION 4: The Long Game (mortal, seed 42, 5000+ ticks)
# ================================================================
def session_4_long_game():
    log("\n" + "=" * 60)
    log("SESSION 4: THE LONG GAME (5000+ ticks, seed 42)")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="mortal", export_dir=OUTPUT_DIR,
                      use_chunked=True)
    hg.player.name = "Chronicler"
    sx, sy = hg.world.spawn_point
    hg.move_player(float(sx), float(sy))

    # Before state
    alive_before = sum(1 for n in hg.world_mgr.npcs if n.alive)
    creatures_before = len(hg.world_mgr.creatures)
    log(f"  Before: {alive_before} NPCs, {creatures_before} creatures")
    save(hg, "S4_01_before")

    # Record terrain around settlement for comparison
    nearest = find_nearest_settlement(hg.world, sx, sy)
    terrain_before = {}
    if nearest:
        for dy in range(-20, 21):
            for dx in range(-20, 21):
                tx, ty = nearest.x + dx, nearest.y + dy
                if 0 <= tx < hg.world.width and 0 <= ty < hg.world.height:
                    t = hg.world.tiles[ty][tx]
                    terrain_before[t] = terrain_before.get(t, 0) + 1
        log(f"  Terrain before: {terrain_before}")

    # Advance 5000 ticks in batches
    log("  Advancing 5000 ticks...")
    events = []
    for batch in range(50):
        hg.tick(100)
        for notif in hg.notifications.notifications:
            events.append(f"  Tick {(batch+1)*100}: {notif.text}")
    log(f"  Events captured: {len(events)}")
    for ev in events[:15]:
        log(ev)
    if len(events) > 15:
        log(f"  ... and {len(events) - 15} more")

    alive_after = sum(1 for n in hg.world_mgr.npcs if n.alive)
    creatures_after = len(hg.world_mgr.creatures)
    log(f"  After: {alive_after} NPCs, {creatures_after} creatures")
    log(f"  Deaths: {alive_before - alive_after}")
    log(f"  Time: {hg.time_sys.time_string}, Day: {hg.time_sys.day}, "
        f"Season: {hg.time_sys.season}")

    # Terrain after
    if nearest:
        terrain_after = {}
        for dy in range(-20, 21):
            for dx in range(-20, 21):
                tx, ty = nearest.x + dx, nearest.y + dy
                if 0 <= tx < hg.world.width and 0 <= ty < hg.world.height:
                    t = hg.world.tiles[ty][tx]
                    terrain_after[t] = terrain_after.get(t, 0) + 1
        log(f"  Terrain after: {terrain_after}")
        changes = {}
        for t in set(list(terrain_before.keys()) + list(terrain_after.keys())):
            b, a = terrain_before.get(t, 0), terrain_after.get(t, 0)
            if b != a:
                changes[t] = (b, a)
        if changes:
            log(f"  Terrain changes: {changes}")
        else:
            log("  No terrain changes detected")

    # Kingdom wars check
    if hasattr(hg.simulation, 'governance'):
        wars = getattr(hg.simulation.governance, 'active_wars', [])
        log(f"  Active wars: {len(wars) if isinstance(wars, list) else wars}")

    # Dead NPCs
    dead = [n for n in hg.world_mgr.npcs if not n.alive]
    log(f"  Dead NPCs: {len(dead)}")
    for n in dead[:5]:
        cause = getattr(n, 'death_cause', 'unknown')
        log(f"    - {n.name} ({n.char_class}): {cause}")

    hg.move_player(float(sx), float(sy))
    save(hg, "S4_02_after_5000_ticks")
    save(hg, "S4_03_world_map_after", view="world_map", zoom=0.5)
    log("  Session 4 complete.")


# ================================================================
# SESSION 5: The Crafter & Trader (UI panels, seed 42)
# ================================================================
def session_5_crafter_trader():
    log("\n" + "=" * 60)
    log("SESSION 5: THE CRAFTER & TRADER (UI panels, seed 42)")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="mortal", export_dir=OUTPUT_DIR,
                      use_chunked=True)
    hg.player.name = "Artisan"
    sx, sy = hg.world.spawn_point
    hg.move_player(float(sx), float(sy))

    # Capture all standard UI panels
    save(hg, "S5_01_gameplay")
    save(hg, "S5_02_character_sheet", view="character_sheet")
    save(hg, "S5_03_inventory", view="inventory")
    save(hg, "S5_04_quest_log", view="quest_log")
    save(hg, "S5_05_pause_menu", view="pause_menu")
    save(hg, "S5_06_planet_view", view="planet_view")

    # World map at different zooms
    save(hg, "S5_07_world_map_close", view="world_map", zoom=2.0)
    save(hg, "S5_08_world_map_medium", view="world_map", zoom=1.0)
    save(hg, "S5_09_world_map_far", view="world_map", zoom=0.25)

    # Check for chronicle/history panel
    try:
        hg.ui.show_chronicle = True
        if hasattr(hg, 'chronicles'):
            hg._draw_gameplay()
            hg.ui.draw_chronicle(hg.chronicles)
            path = os.path.join(OUTPUT_DIR, "S5_10_chronicle.png")
            pygame.image.save(hg.screen, path)
            ALL_SCREENSHOTS.append(("S5_10_chronicle", path))
            log(f"  [screenshot] S5_10_chronicle.png")
        else:
            log("  No chronicles system available")
        hg.ui.show_chronicle = False
    except Exception as e:
        log(f"  Chronicle panel error: {e}")
        hg.ui.show_chronicle = False

    # Full world overview
    save(hg, "S5_11_full_world", view="full_world", scale=1)

    # NPC shop dialog
    nearest = find_nearest_settlement(hg.world, sx, sy)
    if nearest:
        hg.move_player(float(nearest.x), float(nearest.y))
        npcs = [n for n in hg.world_mgr.npcs if n.alive
                and abs(n.x - nearest.x) + abs(n.y - nearest.y) < 30]
        shopkeeper = None
        for n in npcs:
            j = getattr(n, 'job', getattr(n, 'profession', ''))
            if 'shop' in str(j).lower() or 'merchant' in str(j).lower():
                shopkeeper = n
                break
        if shopkeeper:
            log(f"  Found shopkeeper: {shopkeeper.name}")
            try:
                hg.ui.shop_active = True
                hg._draw_gameplay()
                hg.ui.draw_shop(hg.player)
                path = os.path.join(OUTPUT_DIR, "S5_12_shop.png")
                pygame.image.save(hg.screen, path)
                ALL_SCREENSHOTS.append(("S5_12_shop", path))
                log(f"  [screenshot] S5_12_shop.png")
                hg.ui.shop_active = False
            except Exception as e:
                log(f"  Shop panel error: {e}")
                hg.ui.shop_active = False
        else:
            log("  No shopkeeper found nearby")

    log("  Session 5 complete.")


# ================================================================
# SESSION 6: Night & Day (time of day, seed 42)
# ================================================================
def session_6_night_and_day():
    log("\n" + "=" * 60)
    log("SESSION 6: NIGHT & DAY (time transitions, seed 42)")
    log("=" * 60)

    hg = HeadlessGame(seed=42, mode="mortal", export_dir=OUTPUT_DIR,
                      use_chunked=True)
    hg.player.name = "Sunwatcher"
    sx, sy = hg.world.spawn_point

    # Find scenic settlement near water
    nearest = find_nearest_settlement(hg.world, sx, sy)
    if nearest:
        hg.move_player(float(nearest.x), float(nearest.y))
        hg.world.reveal_around(nearest.x, nearest.y, 25)
    else:
        hg.move_player(float(sx), float(sy))

    # Time points
    time_points = [
        ("dawn", DAWN_START),
        ("morning", DAY_START),
        ("midday", 0.50),
        ("dusk", DUSK_START),
        ("night", NIGHT_START),
        ("midnight", 0.95),
    ]

    for name, frac in time_points:
        hg.time_sys.time = DAY_LENGTH * frac
        darkness = hg.time_sys.darkness
        log(f"  {name}: frac={frac:.2f}, darkness={darkness:.2f}")
        save(hg, f"S6_{name}_d{darkness:.2f}")

    # Water at different times
    water_pos = find_terrain(hg.world, WATER, sx, sy, 200)
    if water_pos:
        hg.move_player(float(water_pos[0]), float(water_pos[1]))
        hg.world.reveal_around(water_pos[0], water_pos[1], 15)
        for name, frac in [("water_day", 0.50), ("water_night", 0.90)]:
            hg.time_sys.time = DAY_LENGTH * frac
            save(hg, f"S6_{name}")

    log("  Session 6 complete.")


# ================================================================
# MAIN
# ================================================================
def main():
    log("=" * 60)
    log("FINAL PLAYTEST — AUTONOMOUS WORLD")
    log("=" * 60)

    sessions = [
        ("Session 1: New Adventurer", session_1_new_adventurer),
        ("Session 2: Wizard Explorer", session_2_wizard_explorer),
        ("Session 3: God Mode Observer", session_3_god_mode),
        ("Session 4: The Long Game", session_4_long_game),
        ("Session 5: Crafter & Trader", session_5_crafter_trader),
        ("Session 6: Night & Day", session_6_night_and_day),
    ]

    for name, func in sessions:
        try:
            func()
        except Exception as e:
            log(f"\n  ERROR in {name}: {e}")
            traceback.print_exc()
            REPORT_LINES.append(f"  Traceback: {traceback.format_exc()}")

    # Write log
    log_path = os.path.join(OUTPUT_DIR, "playtest_log.txt")
    with open(log_path, "w") as f:
        f.write("\n".join(REPORT_LINES))
    log(f"\nLog saved to {log_path}")
    log(f"Total screenshots: {len(ALL_SCREENSHOTS)}")

    log("\nScreenshot manifest:")
    for name, path in ALL_SCREENSHOTS:
        log(f"  {name}: {path}")


if __name__ == "__main__":
    main()
