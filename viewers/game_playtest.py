#!/usr/bin/env python3
"""Automated game playtest — captures screenshots at various locations and zoom levels.

Generates a comprehensive visual survey of the game world including:
- World overview at different zooms
- Settlement visits (city, town, village, hamlet)
- NPC inspection
- Terrain variety (forest, mountain, coast, desert/sand)
- Combat scenarios
- Building close-ups
- River/lake areas
- Road networks

All screenshots saved to viewers/playtest_output/
"""

import os
import sys
import random

# Project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUTPUT_DIR = os.path.join(ROOT, "viewers", "playtest_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Force headless
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
pygame.init()

from game.ui.screenshot import HeadlessGame
from game.settings import (
    TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT,
    WATER, SAND, GRASS, FOREST, DENSE_FOREST, MOUNTAIN, SNOW,
    ROAD, SWAMP, FARMLAND,
)


def save(hg, name, view="gameplay", **kwargs):
    """Capture and save with a clean name."""
    filename = f"{name}.png"
    path = hg.capture(view, filename=filename, **kwargs)
    print(f"  Saved: {name}.png")
    return path


def find_terrain(world, terrain_type, near_x=None, near_y=None, radius=500):
    """Find a tile of a specific terrain type, optionally near a location."""
    cx = near_x or world.width // 2
    cy = near_y or world.height // 2
    best = None
    best_dist = 999999
    # Sample in a grid pattern for speed
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
                    # Count adjacent water
                    count = 0
                    for oy in range(-5, 6):
                        for ox in range(-5, 6):
                            nx, ny = x + ox, y + oy
                            if 0 <= nx < world.width and 0 <= ny < world.height:
                                if world.tiles[ny][nx] == WATER:
                                    count += 1
                    if count > best_count:
                        best_count = count
                        best = (x, y)
    return best


def find_road_segment(world, near_x=None, near_y=None, radius=500):
    """Find a road tile."""
    return find_terrain(world, ROAD, near_x, near_y, radius)


def main():
    print("=" * 60)
    print("AUTONOMOUS WORLD — AUTOMATED PLAYTEST")
    print("=" * 60)

    seed = 42
    print(f"\nInitializing headless game (seed={seed})...")
    hg = HeadlessGame(seed=seed, mode="god", export_dir=OUTPUT_DIR)
    print(f"World size: {hg.world.width}x{hg.world.height}")
    print(f"Structures: {len(hg.world.structures)}")
    print(f"NPCs: {len(hg.world_mgr.npcs)}")
    print(f"Creatures: {len(hg.world_mgr.creatures)}")
    print(f"Spawn: {hg.world.spawn_point}")

    # Let simulation warm up
    print("\nWarming up simulation (200 ticks)...")
    hg.tick(200)

    # ── 1. WORLD OVERVIEW ──────────────────────────────────────
    print("\n[1] World Overview")
    save(hg, "01_full_world", view="full_world", scale=1)
    save(hg, "02_world_map_zoomed_out", view="world_map", zoom=0.25)
    save(hg, "03_world_map_medium", view="world_map", zoom=0.5)
    save(hg, "04_world_map_zoomed_in", view="world_map", zoom=1.0)

    # ── 2. SETTLEMENT VISITS ───────────────────────────────────
    print("\n[2] Settlement Visits")
    settlements_by_kind = {}
    for s in hg.world.structures:
        if s.kind in ("city", "town", "village", "hamlet", "castle"):
            settlements_by_kind.setdefault(s.kind, []).append(s)

    counts = {k: len(v) for k, v in settlements_by_kind.items()}
    print(f"  Settlement counts: {counts}")

    visit_count = 0
    for kind in ["city", "castle", "town", "village", "hamlet"]:
        if kind not in settlements_by_kind:
            continue
        settlements = settlements_by_kind[kind]
        # Visit up to 2 of each type
        for s in settlements[:2]:
            visit_count += 1
            prefix = f"05_settlement_{visit_count:02d}_{kind}"
            print(f"  Visiting {s.name} ({kind}) at ({s.x}, {s.y})")

            # Strategy view (16px)
            hg.camera.set_tile_size(TILE_SIZE)
            hg.move_player(float(s.x), float(s.y))
            hg.world.reveal_around(s.x, s.y, 30)
            save(hg, f"{prefix}_strategy")

            # Adventure view (32px) — set up adventure renderer
            try:
                from game.ui.renderer_adventure import AdventureRenderer
                if not hasattr(hg, 'renderer_adventure') or hg.renderer_adventure is None:
                    hg.renderer_adventure = AdventureRenderer(hg.screen)
                    hg.renderer_adventure.build_minimap(hg.world)
                hg.active_renderer = hg.renderer_adventure
                hg.camera.set_tile_size(32)
                hg.move_player(float(s.x), float(s.y))
                save(hg, f"{prefix}_adventure")
            except Exception as e:
                print(f"    Adventure renderer failed: {e}")

            # Reset to strategy
            hg.active_renderer = hg.renderer
            hg.camera.set_tile_size(TILE_SIZE)

    # ── 3. NPC INSPECTION ──────────────────────────────────────
    print("\n[3] NPC Inspection")
    npcs = hg.world_mgr.npcs
    npc_report = []
    for i, npc in enumerate(npcs[:15]):
        job = getattr(npc, 'job', 'unknown')
        action = getattr(npc, 'current_action', 'idle')
        name = getattr(npc, 'name', f'NPC_{i}')
        x, y = getattr(npc, 'x', 0), getattr(npc, 'y', 0)
        hp = getattr(npc, 'hp', 0)
        max_hp = getattr(npc, 'max_hp', 0)
        mood = getattr(npc, 'mood', None)
        settlement = getattr(npc, 'home_settlement', 'unknown')
        npc_report.append({
            'name': name, 'job': job, 'action': action,
            'x': x, 'y': y, 'hp': hp, 'max_hp': max_hp,
            'mood': mood, 'settlement': settlement,
        })
        print(f"  {name}: {job}, doing '{action}' at ({x:.0f},{y:.0f}), "
              f"HP={hp}/{max_hp}")

    # Capture a few NPCs up close
    for i, npc in enumerate(npcs[:5]):
        nx, ny = getattr(npc, 'x', 0), getattr(npc, 'y', 0)
        hg.move_player(float(nx), float(ny))
        hg.world.reveal_around(int(nx), int(ny), 15)
        save(hg, f"06_npc_{i+1:02d}_{getattr(npc, 'name', 'unknown').replace(' ', '_')}")

    # ── 4. TERRAIN VARIETY ─────────────────────────────────────
    print("\n[4] Terrain Variety")
    sx, sy = hg.world.spawn_point
    terrain_targets = [
        ("forest", FOREST),
        ("dense_forest", DENSE_FOREST),
        ("mountain", MOUNTAIN),
        ("coast_sand", SAND),
        ("snow", SNOW),
        ("swamp", SWAMP),
        ("farmland", FARMLAND),
    ]
    for tname, ttype in terrain_targets:
        pos = find_terrain(hg.world, ttype, sx, sy, 800)
        if pos:
            x, y = pos
            hg.move_player(float(x), float(y))
            hg.world.reveal_around(x, y, 20)
            save(hg, f"07_terrain_{tname}")
            print(f"  Found {tname} at ({x}, {y})")
        else:
            print(f"  {tname}: not found within range")

    # ── 5. COMBAT SCENARIO ─────────────────────────────────────
    print("\n[5] Combat / Creatures")
    creatures = hg.world_mgr.creatures
    print(f"  Total creatures: {len(creatures)}")
    for i, c in enumerate(creatures[:8]):
        kind = getattr(c, 'kind', 'unknown')
        cx, cy = getattr(c, 'x', 0), getattr(c, 'y', 0)
        hp = getattr(c, 'hp', 0)
        max_hp = getattr(c, 'max_hp', 0)
        state = getattr(c, 'state', 'unknown')
        print(f"  {kind} at ({cx:.0f},{cy:.0f}), HP={hp}/{max_hp}, state={state}")
        if i < 4:
            hg.move_player(float(cx), float(cy))
            hg.world.reveal_around(int(cx), int(cy), 15)
            save(hg, f"08_creature_{i+1:02d}_{kind}")

    # ── 6. BUILDING VARIETY ────────────────────────────────────
    print("\n[6] Building Close-ups")
    # Pick a city or town and zoom into individual buildings
    for kind in ["city", "town"]:
        if kind in settlements_by_kind:
            s = settlements_by_kind[kind][0]
            if s.buildings:
                for bi, (bx, by, bw, bh) in enumerate(s.buildings[:4]):
                    hg.move_player(float(bx + bw // 2), float(by + bh // 2))
                    hg.world.reveal_around(bx + bw // 2, by + bh // 2, 15)
                    save(hg, f"09_building_{kind}_{bi+1:02d}")
                    print(f"  Building in {s.name}: ({bx},{by}) size {bw}x{bh}")
            break

    # ── 7. WATER FEATURES ──────────────────────────────────────
    print("\n[7] Water Features")
    water_pos = find_water_body(hg.world, sx, sy, 800)
    if water_pos:
        wx, wy = water_pos
        hg.move_player(float(wx), float(wy))
        hg.world.reveal_around(wx, wy, 25)
        save(hg, "10_water_feature_strategy")
        print(f"  Water body at ({wx}, {wy})")

        # Adventure view
        try:
            hg.active_renderer = hg.renderer_adventure
            hg.camera.set_tile_size(32)
            hg.move_player(float(wx), float(wy))
            save(hg, "10_water_feature_adventure")
        except Exception:
            pass
        hg.active_renderer = hg.renderer
        hg.camera.set_tile_size(TILE_SIZE)
    else:
        print("  No significant water body found")

    # ── 8. ROAD NETWORK ────────────────────────────────────────
    print("\n[8] Road Network")
    road_pos = find_road_segment(hg.world, sx, sy, 500)
    if road_pos:
        rx, ry = road_pos
        hg.move_player(float(rx), float(ry))
        hg.world.reveal_around(rx, ry, 25)
        save(hg, "11_road_network_strategy")
        print(f"  Road at ({rx}, {ry})")

        # World map zoom on road area
        save(hg, "11_road_network_worldmap", view="world_map",
             zoom=2.0, center_x=float(rx), center_y=float(ry))

    # ── 9. UI PANELS ───────────────────────────────────────────
    print("\n[9] UI Panels")
    # Move player back to spawn for panel screenshots
    hg.move_player(float(sx), float(sy))
    save(hg, "12_ui_character_sheet", view="character_sheet")
    save(hg, "12_ui_inventory", view="inventory")
    save(hg, "12_ui_quest_log", view="quest_log")
    save(hg, "12_ui_pause_menu", view="pause_menu")
    save(hg, "12_ui_planet_view", view="planet_view")

    # ── 10. TIME OF DAY ────────────────────────────────────────
    print("\n[10] Time of Day")
    # Find a nice settlement to show day/night
    if "town" in settlements_by_kind:
        s = settlements_by_kind["town"][0]
        hg.move_player(float(s.x), float(s.y))
        hg.world.reveal_around(s.x, s.y, 20)

        from game.settings import DAY_LENGTH
        # Dawn (normalized 0.25)
        hg.time_sys.time = 0.25 * DAY_LENGTH
        save(hg, "13_time_dawn")

        # Midday (normalized 0.5)
        hg.time_sys.time = 0.5 * DAY_LENGTH
        save(hg, "13_time_midday")

        # Dusk (normalized 0.75)
        hg.time_sys.time = 0.75 * DAY_LENGTH
        save(hg, "13_time_dusk")

        # Night (normalized 0.9)
        hg.time_sys.time = 0.9 * DAY_LENGTH
        save(hg, "13_time_night")

    # ── SUMMARY ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("PLAYTEST COMPLETE")
    print(f"Screenshots saved to: {OUTPUT_DIR}")
    files = sorted(os.listdir(OUTPUT_DIR))
    print(f"Total screenshots: {len([f for f in files if f.endswith('.png')])}")
    print("=" * 60)

    # Write NPC report
    with open(os.path.join(OUTPUT_DIR, "npc_report.txt"), "w") as f:
        f.write("NPC STATUS REPORT\n")
        f.write("=" * 40 + "\n")
        for npc in npc_report:
            f.write(f"{npc['name']}: {npc['job']}, action='{npc['action']}', "
                    f"at ({npc['x']:.0f},{npc['y']:.0f}), "
                    f"HP={npc['hp']}/{npc['max_hp']}, "
                    f"mood={npc['mood']}, settlement={npc['settlement']}\n")


if __name__ == "__main__":
    main()
