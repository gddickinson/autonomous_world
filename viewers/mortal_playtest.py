#!/usr/bin/env python3
"""Mortal mode playtest — plays the game as a normal character (not god mode).

Tests gameplay, combat, NPC interactions, exploration, settlement visuals,
walls and defenses, and all UI panels. Takes screenshots at each step.

All screenshots saved to viewers/mortal_playtest_output/
"""

import os
import sys
import random
import math

# Project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUTPUT_DIR = os.path.join(ROOT, "viewers", "mortal_playtest_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Force headless
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
pygame.init()

from game.ui.screenshot import HeadlessGame
from game.settings import (
    TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT, DAY_LENGTH,
    WATER, SAND, GRASS, FOREST, DENSE_FOREST, MOUNTAIN, SNOW,
    ROAD, SWAMP, FARMLAND,
)

# Collected screenshot paths for later analysis
ALL_SCREENSHOTS = []


def save(hg, name, view="gameplay", **kwargs):
    """Capture and save with a clean name."""
    filename = f"{name}.png"
    path = hg.capture(view, filename=filename, **kwargs)
    ALL_SCREENSHOTS.append((name, path))
    print(f"  Saved: {name}.png")
    return path


def find_terrain(world, terrain_type, near_x=None, near_y=None, radius=500):
    """Find a tile of a specific terrain type near a location."""
    cx = near_x or world.width // 2
    cy = near_y or world.height // 2
    best = None
    best_dist = 999999
    step = 3
    for dy in range(-radius, radius, step):
        for dx in range(-radius, radius, step):
            x, y = cx + dx, cy + dy
            if 0 <= x < world.width and 0 <= y < world.height:
                if world.tiles[y][x] == terrain_type:
                    d = abs(dx) + abs(dy)
                    if d < best_dist:
                        best_dist = d
                        best = (x, y)
    return best


def find_water_body(world, near_x=None, near_y=None, radius=500, min_size=20):
    """Find a substantial water body (lake/river)."""
    cx = near_x or world.width // 2
    cy = near_y or world.height // 2
    best = None
    best_count = 0
    step = 10
    for dy in range(-radius, radius, step):
        for dx in range(-radius, radius, step):
            x, y = cx + dx, cy + dy
            if 0 <= x < world.width and 0 <= y < world.height:
                if world.tiles[y][x] == WATER:
                    count = sum(
                        1 for oy in range(-5, 6) for ox in range(-5, 6)
                        if 0 <= x + ox < world.width and 0 <= y + oy < world.height
                        and world.tiles[y + oy][x + ox] == WATER
                    )
                    if count > best_count:
                        best_count = count
                        best = (x, y)
    return best


def find_nearest_settlement(world, x, y, kind=None):
    """Find the nearest settlement, optionally of a specific kind."""
    best = None
    best_dist = 999999
    for s in world.structures:
        if s.kind not in ("village", "town", "city", "hamlet", "castle"):
            continue
        if kind and s.kind != kind:
            continue
        d = abs(s.x - x) + abs(s.y - y)
        if d < best_dist:
            best_dist = d
            best = s
    return best


def find_nearby_npc(hg, x, y, radius=30, job_filter=None):
    """Find an NPC near a position."""
    best = None
    best_dist = 999999
    for npc in hg.world_mgr.npcs:
        if not npc.alive:
            continue
        if job_filter and getattr(npc, 'job', '') != job_filter:
            continue
        d = abs(npc.x - x) + abs(npc.y - y)
        if d < radius and d < best_dist:
            best_dist = d
            best = npc
    return best


def find_walled_settlement(world):
    """Find a settlement with walls (town or city)."""
    for s in world.structures:
        if s.kind in ("city", "castle"):
            return s
    for s in world.structures:
        if s.kind == "town":
            return s
    return None


# ================================================================
# SECTION A: Character Start
# ================================================================
def section_a_character_start(hg):
    """Capture starting position, character sheet, inventory, etc."""
    print("\n[A] CHARACTER START")

    sx, sy = hg.world.spawn_point
    print(f"  Spawn point: ({sx}, {sy})")
    print(f"  Player: {hg.player.name}, {hg.player.race} {hg.player.char_class}")
    print(f"  Level: {hg.player.level}, HP: {hg.player.hp}/{hg.player.max_hp}")
    print(f"  Gold: {hg.player.gold}")
    print(f"  Mode: {hg.player.mode}")

    # Starting position gameplay view
    hg.move_player(float(sx), float(sy))
    save(hg, "A01_starting_position")

    # Character sheet
    save(hg, "A02_character_sheet", view="character_sheet")

    # Inventory
    save(hg, "A03_inventory", view="inventory")

    # Quest log (should be empty or have starting quests)
    save(hg, "A04_quest_log", view="quest_log")

    # World map centered on spawn
    save(hg, "A05_world_map_spawn", view="world_map", zoom=1.0)

    # Full world overview
    save(hg, "A06_full_world", view="full_world", scale=1)

    # Pause menu (shows game info)
    save(hg, "A07_pause_menu", view="pause_menu")

    return sx, sy


# ================================================================
# SECTION B: Settlement Exploration
# ================================================================
def section_b_settlement_exploration(hg, sx, sy):
    """Walk to nearest settlement and explore it."""
    print("\n[B] SETTLEMENT EXPLORATION")

    settlements_by_kind = {}
    for s in hg.world.structures:
        if s.kind in ("city", "town", "village", "hamlet", "castle"):
            settlements_by_kind.setdefault(s.kind, []).append(s)
    counts = {k: len(v) for k, v in settlements_by_kind.items()}
    print(f"  Settlement counts: {counts}")

    # Visit nearest settlement of each type
    shot_num = 1
    for kind in ["city", "castle", "town", "village", "hamlet"]:
        s = find_nearest_settlement(hg.world, sx, sy, kind=kind)
        if not s:
            print(f"  No {kind} found")
            continue

        print(f"  Visiting {s.name} ({kind}) at ({s.x}, {s.y})")

        # Strategy view (default TILE_SIZE)
        hg.camera.set_tile_size(TILE_SIZE)
        hg.move_player(float(s.x), float(s.y))
        hg.world.reveal_around(s.x, s.y, 30)
        save(hg, f"B{shot_num:02d}_{kind}_strategy_{s.name.replace(' ', '_')}")
        shot_num += 1

        # Adventure view (32px tiles)
        try:
            from game.ui.renderer_adventure import AdventureRenderer
            if not hasattr(hg, 'renderer_adventure') or hg.renderer_adventure is None:
                hg.renderer_adventure = AdventureRenderer(hg.screen)
                hg.renderer_adventure.build_minimap(hg.world)
            hg.active_renderer = hg.renderer_adventure
            hg.camera.set_tile_size(32)
            hg.move_player(float(s.x), float(s.y))
            save(hg, f"B{shot_num:02d}_{kind}_adventure_{s.name.replace(' ', '_')}")
            shot_num += 1
        except Exception as e:
            print(f"    Adventure renderer failed: {e}")

        # Reset to strategy
        hg.active_renderer = hg.renderer
        hg.camera.set_tile_size(TILE_SIZE)

        # World map showing this settlement
        save(hg, f"B{shot_num:02d}_{kind}_worldmap_{s.name.replace(' ', '_')}",
             view="world_map", zoom=2.0,
             center_x=float(s.x), center_y=float(s.y))
        shot_num += 1

    return settlements_by_kind


# ================================================================
# SECTION C: NPC Interactions
# ================================================================
def section_c_npc_interactions(hg, sx, sy, settlements_by_kind):
    """Find NPCs and simulate dialog interactions."""
    print("\n[C] NPC INTERACTIONS")

    # Find a settlement with NPCs near it
    target_settlement = find_nearest_settlement(hg.world, sx, sy)
    if not target_settlement:
        print("  No settlement found for NPC interaction!")
        return

    print(f"  Looking for NPCs near {target_settlement.name}")
    hg.move_player(float(target_settlement.x), float(target_settlement.y))
    hg.world.reveal_around(target_settlement.x, target_settlement.y, 40)
    hg.tick(10)  # let NPCs settle

    shot_num = 1
    npc_types_found = set()

    # Try to find different NPC types
    for npc in hg.world_mgr.npcs:
        if not npc.alive:
            continue
        d = abs(npc.x - target_settlement.x) + abs(npc.y - target_settlement.y)
        if d > 50:
            continue
        job = getattr(npc, 'job', getattr(npc, 'profession', 'unknown'))
        if job in npc_types_found and len(npc_types_found) < 5:
            continue

        npc_types_found.add(job)
        print(f"  Found {npc.name} ({job}) at ({npc.x:.0f}, {npc.y:.0f})")

        # Move near the NPC
        hg.move_player(float(npc.x), float(npc.y))
        hg.world.reveal_around(int(npc.x), int(npc.y), 15)

        # Gameplay view showing NPC nearby
        save(hg, f"C{shot_num:02d}_npc_{job}_{npc.name.replace(' ', '_')}")
        shot_num += 1

        # Open dialog with this NPC
        try:
            npc.regenerate_dialog()
            hg.ui.open_dialog(npc)
            # Draw the dialog panel on top of gameplay
            hg._draw_gameplay()
            hg.ui.draw_dialog()
            filename = f"C{shot_num:02d}_dialog_{job}_{npc.name.replace(' ', '_')}.png"
            filepath = os.path.join(OUTPUT_DIR, filename)
            pygame.image.save(hg.screen, filepath)
            ALL_SCREENSHOTS.append((filename.replace('.png', ''), filepath))
            print(f"  Saved: {filename}")
            shot_num += 1

            # Close dialog
            hg.ui.dialog_active = False
        except Exception as e:
            print(f"    Dialog failed for {npc.name}: {e}")

        if shot_num > 12:
            break

    # Print NPC summary
    print(f"  NPC types found: {npc_types_found}")


# ================================================================
# SECTION D: Combat
# ================================================================
def section_d_combat(hg, sx, sy):
    """Find hostile creatures and engage in combat."""
    print("\n[D] COMBAT")

    creatures = hg.world_mgr.creatures
    print(f"  Total creatures: {len(creatures)}")

    shot_num = 1

    # List creature types
    creature_kinds = {}
    for c in creatures:
        kind = getattr(c, 'kind', 'unknown')
        creature_kinds[kind] = creature_kinds.get(kind, 0) + 1
    print(f"  Creature types: {creature_kinds}")

    # Find closest creature to spawn
    best_creature = None
    best_dist = 999999
    for c in creatures:
        if not getattr(c, 'alive', True):
            continue
        d = abs(c.x - sx) + abs(c.y - sy)
        if d < best_dist:
            best_dist = d
            best_creature = c

    if best_creature:
        kind = getattr(best_creature, 'kind', 'unknown')
        cx, cy = best_creature.x, best_creature.y
        print(f"  Engaging {kind} at ({cx:.0f}, {cy:.0f}), "
              f"HP={best_creature.hp}/{best_creature.max_hp}")

        # Move to creature
        hg.move_player(float(cx), float(cy))
        hg.world.reveal_around(int(cx), int(cy), 15)
        save(hg, f"D{shot_num:02d}_creature_{kind}_approach")
        shot_num += 1

        # Simulate combat — attack the creature
        # Set player right next to it
        hg.player.x = cx + 1
        hg.player.y = cy
        hg.attack_flash_timer = 0.3  # simulate attack flash

        # Deal damage manually to simulate combat
        orig_hp = best_creature.hp
        dmg = hg.player.attack_damage
        best_creature.hp = max(0, best_creature.hp - dmg)
        print(f"  Player attacks {kind} for {dmg} damage "
              f"({orig_hp} -> {best_creature.hp})")

        # Draw with combat happening
        hg._draw_gameplay()
        filename = f"D{shot_num:02d}_combat_attack_{kind}.png"
        filepath = os.path.join(OUTPUT_DIR, filename)
        pygame.image.save(hg.screen, filepath)
        ALL_SCREENSHOTS.append((filename.replace('.png', ''), filepath))
        print(f"  Saved: {filename}")
        shot_num += 1

        # Tick a few times to see combat effects
        hg.tick(5)
        save(hg, f"D{shot_num:02d}_combat_aftermath_{kind}")
        shot_num += 1

    # Visit a few more creatures
    creatures_visited = 0
    for c in creatures:
        if not getattr(c, 'alive', True):
            continue
        if c is best_creature:
            continue
        kind = getattr(c, 'kind', 'unknown')
        hg.move_player(float(c.x), float(c.y))
        hg.world.reveal_around(int(c.x), int(c.y), 15)
        save(hg, f"D{shot_num:02d}_creature_{kind}")
        shot_num += 1
        creatures_visited += 1
        if creatures_visited >= 3:
            break

    # Check player HP after combat
    print(f"  Player HP after combat: {hg.player.hp}/{hg.player.max_hp}")


# ================================================================
# SECTION E: World Exploration
# ================================================================
def section_e_world_exploration(hg, sx, sy):
    """Travel between settlements, visit different terrain types."""
    print("\n[E] WORLD EXPLORATION")

    shot_num = 1

    # Find road and travel along it
    road_pos = find_terrain(hg.world, ROAD, sx, sy, 500)
    if road_pos:
        rx, ry = road_pos
        hg.move_player(float(rx), float(ry))
        hg.world.reveal_around(rx, ry, 20)
        save(hg, f"E{shot_num:02d}_road_travel")
        shot_num += 1
        print(f"  Road at ({rx}, {ry})")

    # Visit different terrains
    terrains = [
        ("forest", FOREST),
        ("dense_forest", DENSE_FOREST),
        ("mountain", MOUNTAIN),
        ("coast", SAND),
        ("snow", SNOW),
        ("swamp", SWAMP),
        ("farmland", FARMLAND),
    ]
    for tname, ttype in terrains:
        pos = find_terrain(hg.world, ttype, sx, sy, 600)
        if pos:
            x, y = pos
            hg.move_player(float(x), float(y))
            hg.world.reveal_around(x, y, 20)
            save(hg, f"E{shot_num:02d}_terrain_{tname}")
            shot_num += 1
            print(f"  {tname} at ({x}, {y})")
        else:
            print(f"  {tname}: not found")

    # Water body
    water_pos = find_water_body(hg.world, sx, sy, 600)
    if water_pos:
        wx, wy = water_pos
        hg.move_player(float(wx), float(wy))
        hg.world.reveal_around(wx, wy, 25)
        save(hg, f"E{shot_num:02d}_water_body")
        shot_num += 1
        print(f"  Water body at ({wx}, {wy})")

    # Day/night cycle
    print("  Day/night cycle:")
    hg.move_player(float(sx), float(sy))
    hg.world.reveal_around(sx, sy, 20)

    for time_name, time_frac in [("dawn", 0.25), ("midday", 0.5),
                                   ("dusk", 0.75), ("night", 0.9)]:
        hg.time_sys.time = time_frac * DAY_LENGTH
        save(hg, f"E{shot_num:02d}_time_{time_name}")
        shot_num += 1
        print(f"  Time set to {time_name} ({time_frac})")

    # Reset to midday
    hg.time_sys.time = 0.5 * DAY_LENGTH


# ================================================================
# SECTION F: Game Systems
# ================================================================
def section_f_game_systems(hg, sx, sy):
    """Capture all UI panels and game systems."""
    print("\n[F] GAME SYSTEMS")

    hg.move_player(float(sx), float(sy))
    shot_num = 1

    # Character sheet
    save(hg, f"F{shot_num:02d}_character_sheet_detail", view="character_sheet")
    shot_num += 1

    # Inventory
    save(hg, f"F{shot_num:02d}_inventory_detail", view="inventory")
    shot_num += 1

    # Quest log
    save(hg, f"F{shot_num:02d}_quest_log_detail", view="quest_log")
    shot_num += 1

    # World map at various zooms
    save(hg, f"F{shot_num:02d}_worldmap_overview", view="world_map", zoom=0.25)
    shot_num += 1
    save(hg, f"F{shot_num:02d}_worldmap_medium", view="world_map", zoom=0.5)
    shot_num += 1
    save(hg, f"F{shot_num:02d}_worldmap_detailed", view="world_map", zoom=2.0)
    shot_num += 1

    # Planet view
    save(hg, f"F{shot_num:02d}_planet_view", view="planet_view")
    shot_num += 1

    # Print player stats
    p = hg.player
    print(f"  Name: {p.name}")
    print(f"  Race: {p.race}, Class: {p.char_class}")
    print(f"  Level: {p.level}, XP: {p.xp}/{p.xp_to_next}")
    print(f"  HP: {p.hp}/{p.max_hp}")
    print(f"  Gold: {p.gold}")
    print(f"  Attack: {p.attack_damage}, Defense: {p.defense}")
    print(f"  Abilities: {p.ability_scores}")
    print(f"  Spellcaster: {p.is_spellcaster}")
    if p.is_spellcaster:
        print(f"  Known spells: {p.known_spells}")
    print(f"  Inventory: {[i.name for i in p.inventory]}")
    if p.equipped_weapon:
        print(f"  Weapon: {p.equipped_weapon.name}")
    if p.equipped_armor:
        print(f"  Armor: {p.equipped_armor.name}")


# ================================================================
# SECTION G: Walls & Defenses
# ================================================================
def section_g_walls_defenses(hg, sx, sy):
    """Find walled settlements and inspect their defenses."""
    print("\n[G] WALLS & DEFENSES")

    shot_num = 1
    walled = find_walled_settlement(hg.world)
    if not walled:
        print("  No walled settlement found!")
        return

    print(f"  Inspecting walls of {walled.name} ({walled.kind}) "
          f"at ({walled.x}, {walled.y})")

    # Overview of the walled settlement
    hg.camera.set_tile_size(TILE_SIZE)
    hg.move_player(float(walled.x), float(walled.y))
    hg.world.reveal_around(walled.x, walled.y, 50)
    save(hg, f"G{shot_num:02d}_walled_{walled.kind}_overview")
    shot_num += 1

    # Adventure view (larger tiles)
    try:
        from game.ui.renderer_adventure import AdventureRenderer
        if not hasattr(hg, 'renderer_adventure') or hg.renderer_adventure is None:
            hg.renderer_adventure = AdventureRenderer(hg.screen)
            hg.renderer_adventure.build_minimap(hg.world)
        hg.active_renderer = hg.renderer_adventure
        hg.camera.set_tile_size(32)
        hg.move_player(float(walled.x), float(walled.y))
        save(hg, f"G{shot_num:02d}_walled_{walled.kind}_adventure")
        shot_num += 1
    except Exception as e:
        print(f"    Adventure renderer failed: {e}")

    # Reset
    hg.active_renderer = hg.renderer
    hg.camera.set_tile_size(TILE_SIZE)

    # Walk around the perimeter — north, south, east, west edges
    radius = getattr(walled, 'radius', 20)
    for direction, dx, dy in [("north", 0, -radius),
                               ("south", 0, radius),
                               ("east", radius, 0),
                               ("west", -radius, 0)]:
        px, py = walled.x + dx, walled.y + dy
        hg.move_player(float(px), float(py))
        hg.world.reveal_around(int(px), int(py), 20)
        save(hg, f"G{shot_num:02d}_wall_{direction}")
        shot_num += 1
        print(f"  Wall {direction} side at ({px}, {py})")

    # Check for gate tiles (ROAD tiles at wall boundaries)
    # Look for roads that enter the settlement
    gate_found = False
    for dy in range(-radius - 5, radius + 5):
        for dx in range(-radius - 5, radius + 5):
            x, y = walled.x + dx, walled.y + dy
            if 0 <= x < hg.world.width and 0 <= y < hg.world.height:
                if hg.world.tiles[y][x] == ROAD:
                    # Check if it's at the edge of the settlement
                    dist = math.sqrt(dx * dx + dy * dy)
                    if abs(dist - radius) < 3:
                        hg.move_player(float(x), float(y))
                        hg.world.reveal_around(x, y, 15)
                        save(hg, f"G{shot_num:02d}_gate_area")
                        shot_num += 1
                        gate_found = True
                        print(f"  Gate area at ({x}, {y})")
                        break
        if gate_found:
            break

    # World map of the walled settlement
    save(hg, f"G{shot_num:02d}_walled_worldmap",
         view="world_map", zoom=2.0,
         center_x=float(walled.x), center_y=float(walled.y))
    shot_num += 1


# ================================================================
# MAIN
# ================================================================
def main():
    print("=" * 60)
    print("MORTAL MODE PLAYTEST")
    print("=" * 60)

    seed = 42
    print(f"\nInitializing headless game (seed={seed}, mode='mortal')...")
    hg = HeadlessGame(seed=seed, mode="mortal", export_dir=OUTPUT_DIR)
    print(f"World size: {hg.world.width}x{hg.world.height}")
    print(f"Structures: {len(hg.world.structures)}")
    print(f"NPCs: {len(hg.world_mgr.npcs)}")
    print(f"Creatures: {len(hg.world_mgr.creatures)}")
    print(f"Spawn: {hg.world.spawn_point}")
    print(f"Player mode: {hg.player.mode}")
    print(f"FOV radius: {hg.fov_radius}")

    # Warm up simulation
    print("\nWarming up simulation (200 ticks)...")
    hg.tick(200)

    # Run all sections
    sx, sy = section_a_character_start(hg)
    settlements = section_b_settlement_exploration(hg, sx, sy)
    section_c_npc_interactions(hg, sx, sy, settlements)
    section_d_combat(hg, sx, sy)
    section_e_world_exploration(hg, sx, sy)
    section_f_game_systems(hg, sx, sy)
    section_g_walls_defenses(hg, sx, sy)

    # Summary
    print("\n" + "=" * 60)
    print("MORTAL PLAYTEST COMPLETE")
    print(f"Screenshots saved to: {OUTPUT_DIR}")
    png_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.png')]
    print(f"Total screenshots: {len(png_files)}")
    print("=" * 60)

    # Write screenshot index
    with open(os.path.join(OUTPUT_DIR, "screenshot_index.txt"), "w") as f:
        f.write("MORTAL PLAYTEST SCREENSHOT INDEX\n")
        f.write("=" * 50 + "\n\n")
        for name, path in ALL_SCREENSHOTS:
            f.write(f"{name}: {os.path.basename(path)}\n")

    return ALL_SCREENSHOTS


if __name__ == "__main__":
    main()
