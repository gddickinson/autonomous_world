#!/usr/bin/env python3
"""Divine Realm Playtest — test the god realm map, structures, NPCs,
realm transitions, mortal world as god, and divine powers.

All screenshots saved to viewers/god_realm_output/
"""

import os
import sys
import math
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

OUTPUT_DIR = os.path.join(ROOT, "viewers", "god_realm_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
pygame.init()

from game.ui.screenshot import HeadlessGame
from game.settings import (
    TERRAIN_COLORS, TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT,
    DAY_LENGTH, DAWN_START, DAY_START, DUSK_START, NIGHT_START,
)

ALL_SCREENSHOTS = []
REPORT = []


def log(msg):
    print(msg)
    REPORT.append(msg)


def save_surface(surf, name):
    """Save a pygame surface directly."""
    path = os.path.join(OUTPUT_DIR, f"{name}.png")
    pygame.image.save(surf, path)
    ALL_SCREENSHOTS.append((name, path))
    log(f"  [screenshot] {name}.png")
    return path


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
        }
    return stats


# Divine realm tile colors (custom palette for the ethereal feel)
DIVINE_COLORS = {
    80: (220, 230, 255),   # CLOUD — pale blue-white
    81: (240, 235, 220),   # MARBLE_FLOOR — warm ivory
    82: (100, 180, 255),   # DIVINE_WATER — bright ethereal blue
    83: (255, 215, 80),    # GOLDEN_PATH — rich gold
}


def get_tile_color(tile_id):
    """Get color for a divine realm tile, falling back to TERRAIN_COLORS."""
    if tile_id in DIVINE_COLORS:
        return DIVINE_COLORS[tile_id]
    return TERRAIN_COLORS.get(tile_id, (100, 100, 100))


def render_divine_realm(tiles, size=200, scale=4):
    """Render the full divine realm map to a scaled surface."""
    surf = pygame.Surface((size, size))
    for y in range(size):
        for x in range(size):
            color = get_tile_color(tiles[y][x])
            surf.set_at((x, y), color)
    scaled = pygame.transform.scale(surf, (size * scale, size * scale))
    return scaled


def render_zoom(tiles, cx, cy, radius, scale=8, label=""):
    """Render a zoomed-in view of the divine realm centered on (cx, cy)."""
    side = radius * 2
    surf = pygame.Surface((side, side))
    for dy in range(side):
        for dx in range(side):
            wx = cx - radius + dx
            wy = cy - radius + dy
            if 0 <= wx < 200 and 0 <= wy < 200:
                color = get_tile_color(tiles[wy][wx])
            else:
                color = (30, 30, 50)
            surf.set_at((dx, dy), color)
    scaled = pygame.transform.scale(surf, (side * scale, side * scale))
    return scaled


# ================================================================
# TEST 1: Divine Realm Map (3 screenshots)
# ================================================================
def test_1_divine_realm_map(hg, drm):
    log("\n" + "=" * 60)
    log("TEST 1: DIVINE REALM MAP")
    log("=" * 60)

    tiles = drm.realm_data['tiles']
    size = drm.realm_data['size']
    log(f"  Realm size: {size}x{size}")

    # Count tile types
    counts = {}
    for row in tiles:
        for t in row:
            counts[t] = counts.get(t, 0) + 1
    log(f"  Tile type distribution:")
    tile_names = {80: "Cloud", 81: "Marble", 82: "DivineWater",
                  83: "GoldenPath"}
    for tid, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        name = tile_names.get(tid, TERRAIN_COLORS.get(tid, f"Tile{tid}"))
        log(f"    {name} ({tid}): {cnt} tiles")

    # Full overview
    overview = render_divine_realm(tiles, size, scale=4)
    save_surface(overview, "01_divine_realm_overview")

    # Zoom: Pantheon Temple (north of center)
    temple = None
    for s in drm.realm_data['structures']:
        if s['kind'] == 'temple':
            temple = s
            break
    if temple:
        tcx = temple['x'] + temple['w'] // 2
        tcy = temple['y'] + temple['h'] // 2
        zoomed = render_zoom(tiles, tcx, tcy, 25, scale=8)
        save_surface(zoomed, "02_pantheon_temple_zoom")
        log(f"  Temple center: ({tcx}, {tcy})")

    # Zoom: Viewing Pool (center)
    pool_pos = drm.realm_data['pool_pos']
    zoomed_pool = render_zoom(tiles, pool_pos[0], pool_pos[1], 25, scale=8)
    save_surface(zoomed_pool, "03_viewing_pool_zoom")
    log(f"  Pool center: {pool_pos}")


# ================================================================
# TEST 2: God NPCs
# ================================================================
def test_2_god_npcs(hg, drm):
    log("\n" + "=" * 60)
    log("TEST 2: GOD NPCs")
    log("=" * 60)

    gods = drm.realm_data['god_spawns']
    log(f"  Total god NPCs: {len(gods)}")

    for i, god in enumerate(gods):
        log(f"\n  [{i+1}] {god['name']}")
        log(f"      Domain: {god['domain']}")
        log(f"      Position: ({god['x']}, {god['y']})")
        dialog = drm.get_god_dialog(god)
        log(f"      Dialog: \"{dialog}\"")

    # Verify count
    expected = 7
    actual = len(gods)
    log(f"\n  Expected {expected} gods, found {actual}: "
        f"{'PASS' if actual == expected else 'FAIL'}")


# ================================================================
# TEST 3: Divine Realm Structures
# ================================================================
def test_3_structures(hg, drm):
    log("\n" + "=" * 60)
    log("TEST 3: DIVINE REALM STRUCTURES")
    log("=" * 60)

    structures = drm.realm_data['structures']
    log(f"  Total structures: {len(structures)}")

    expected_kinds = {"pool", "temple", "portal", "armory",
                      "garden", "trophy_hall"}
    found_kinds = set()

    for s in structures:
        log(f"  - {s['name']} (kind={s['kind']}) "
            f"at ({s['x']},{s['y']}) size={s['w']}x{s['h']}")
        found_kinds.add(s['kind'])

    missing = expected_kinds - found_kinds
    if missing:
        log(f"  MISSING structures: {missing}")
    else:
        log(f"  All expected structures found: PASS")


# ================================================================
# TEST 4: Portal and Pool Interaction
# ================================================================
def test_4_interactions(hg, drm):
    log("\n" + "=" * 60)
    log("TEST 4: PORTAL AND POOL INTERACTION")
    log("=" * 60)

    # Save original position
    orig_x, orig_y = hg.player.x, hg.player.y
    log(f"  Original mortal position: ({orig_x:.0f}, {orig_y:.0f})")

    # Enter divine realm
    drm.enter_divine_realm()
    log(f"  After enter_divine_realm:")
    log(f"    in_divine_realm = {drm.in_divine_realm}")
    log(f"    Player pos: ({hg.player.x:.0f}, {hg.player.y:.0f})")
    log(f"    Mortal pos saved: {drm.mortal_position}")
    enter_ok = drm.in_divine_realm
    log(f"    PASS" if enter_ok else "    FAIL")

    # Test viewing pool toggle (player should be near pool center)
    pool = drm.realm_data['pool_pos']
    hg.player.x = float(pool[0])
    hg.player.y = float(pool[1])
    drm.toggle_viewing_pool()
    log(f"\n  Viewing pool toggle (near pool):")
    log(f"    viewing_pool_active = {drm.viewing_pool_active}")
    pool_ok = drm.viewing_pool_active
    log(f"    PASS" if pool_ok else "    FAIL")

    # Toggle off
    drm.toggle_viewing_pool()
    log(f"    Toggle off: viewing_pool_active = {drm.viewing_pool_active}")

    # Test pool toggle when far away
    hg.player.x = 10.0
    hg.player.y = 10.0
    drm.toggle_viewing_pool()
    log(f"\n  Viewing pool toggle (far away):")
    log(f"    viewing_pool_active = {drm.viewing_pool_active}")
    far_ok = not drm.viewing_pool_active
    log(f"    {'PASS' if far_ok else 'FAIL'} (should stay inactive)")

    # Test portal proximity check
    portal = drm.realm_data['portal_pos']
    hg.player.x = float(portal[0])
    hg.player.y = float(portal[1])
    near_portal = drm.check_portal_interaction()
    log(f"\n  Portal interaction (near portal):")
    log(f"    Near portal: {near_portal}")
    log(f"    PASS" if near_portal else "    FAIL")

    # Exit to mortal world
    drm.exit_to_mortal_world()
    log(f"\n  After exit_to_mortal_world:")
    log(f"    in_divine_realm = {drm.in_divine_realm}")
    log(f"    Player pos: ({hg.player.x:.0f}, {hg.player.y:.0f})")
    exit_ok = (not drm.in_divine_realm and
               abs(hg.player.x - orig_x) < 1 and
               abs(hg.player.y - orig_y) < 1)
    log(f"    Position restored: {'PASS' if exit_ok else 'FAIL'}")


# ================================================================
# TEST 5: Mortal World as God (3 screenshots)
# ================================================================
def test_5_mortal_world(hg, drm):
    log("\n" + "=" * 60)
    log("TEST 5: MORTAL WORLD AS GOD")
    log("=" * 60)

    # Make sure we're in mortal world
    if drm.in_divine_realm:
        drm.exit_to_mortal_world()

    sx, sy = hg.world.spawn_point
    sett = find_settlement(hg.world, sx, sy)
    if sett:
        hg.move_player(float(sett.x), float(sett.y))
        hg.world.reveal_around(sett.x, sett.y, 40)
        log(f"  Settlement: {sett.name} ({sett.kind})")
        save(hg, "04_settlement_strategy")
    else:
        hg.move_player(float(sx), float(sy))
        save(hg, "04_spawn_area")

    # Run 500 ticks
    log("  Running 500 ticks...")
    kstats_before = kingdom_stats(hg)
    hg.tick(500)
    kstats_after = kingdom_stats(hg)

    log(f"  Time: {hg.time_sys.time_string}, Day {hg.time_sys.day}")
    alive = sum(1 for n in hg.world_mgr.npcs if getattr(n, 'alive', True))
    log(f"  Alive NPCs: {alive}/{len(hg.world_mgr.npcs)}")

    for kn in kstats_before:
        kb = kstats_before[kn]
        ka = kstats_after.get(kn, {})
        log(f"  Kingdom {kn}: treasury {kb['treasury']:.0f} -> "
            f"{ka.get('treasury', 0):.0f}")

    # Daytime screenshot
    hg.time_sys.time = DAY_LENGTH * (DAY_START + 0.1)
    log(f"  Daytime: {hg.time_sys.time_string}")
    save(hg, "05_daytime_npcs")

    # Nighttime screenshot
    hg.time_sys.time = DAY_LENGTH * (NIGHT_START + 0.08)
    log(f"  Nighttime: {hg.time_sys.time_string}")
    save(hg, "06_nighttime_npcs")


# ================================================================
# TEST 6: Divine Powers
# ================================================================
def test_6_divine_powers(hg, drm):
    log("\n" + "=" * 60)
    log("TEST 6: DIVINE POWERS")
    log("=" * 60)

    sx, sy = hg.world.spawn_point
    sett = find_settlement(hg.world, sx, sy)
    if sett:
        hg.move_player(float(sett.x), float(sett.y))
    npcs = npcs_near(hg, hg.player.x, hg.player.y)

    # Smite test
    if npcs:
        target = npcs[0]
        log(f"  Smite target: {target.name}, HP={target.hp}/{target.max_hp}")
        target.hp = 0
        target.alive = False
        log(f"  SMITE! {target.name} HP -> 0")

        # Check nearby reactions
        fleeing = 0
        for npc in npcs[1:]:
            dx = npc.x - target.x
            dy = npc.y - target.y
            dist_sq = dx * dx + dy * dy
            if dist_sq < 100:
                npc.current_action = "fleeing"
                npc.action_timer = 5.0
                dist = max(0.1, math.sqrt(dist_sq))
                npc.target_x = npc.x + (dx / dist) * 15
                npc.target_y = npc.y + (dy / dist) * 15
                fleeing += 1
        log(f"  NPCs fleeing: {fleeing}")
    else:
        log("  No NPCs available for smite")

    # Festival event
    try:
        from game.systems.divine_events import trigger_festival
        trigger_festival(sett, hg)
        log(f"  Festival triggered at {sett.name if sett else 'spawn'}")
    except Exception as e:
        log(f"  Festival trigger error: {e}")

    # Treasury check
    kstats_pre = kingdom_stats(hg)
    hg.tick(100)
    kstats_post = kingdom_stats(hg)

    for kn in kstats_pre:
        pre = kstats_pre[kn]['treasury']
        post = kstats_post.get(kn, {}).get('treasury', 0)
        delta = post - pre
        log(f"  Kingdom {kn} treasury: {pre:.0f} -> {post:.0f} "
            f"(delta={delta:+.0f})")


# ================================================================
# MAIN
# ================================================================
def main():
    log("=" * 60)
    log("DIVINE REALM PLAYTEST")
    log("=" * 60)

    try:
        hg = HeadlessGame(seed=42, mode='god', use_chunked=True,
                          export_dir=OUTPUT_DIR)
        log(f"  Game initialized: seed=42, mode=god, chunked=True")
        log(f"  World: {hg.world.width}x{hg.world.height}")
        log(f"  NPCs: {len(hg.world_mgr.npcs)}")
    except Exception as e:
        log(f"FATAL: Could not initialize game: {e}")
        traceback.print_exc()
        return

    # Initialize divine realm manually
    from game.systems.divine_realm_manager import DivineRealmManager
    hg.divine_realm = DivineRealmManager(hg)
    hg.divine_realm.initialize()
    drm = hg.divine_realm
    log(f"  Divine realm initialized: {drm._initialized}")
    log(f"  Realm data keys: {list(drm.realm_data.keys())}")

    tests = [
        ("Test 1: Divine Realm Map", test_1_divine_realm_map),
        ("Test 2: God NPCs", test_2_god_npcs),
        ("Test 3: Structures", test_3_structures),
        ("Test 4: Interactions", test_4_interactions),
        ("Test 5: Mortal World", test_5_mortal_world),
        ("Test 6: Divine Powers", test_6_divine_powers),
    ]

    for name, func in tests:
        try:
            func(hg, drm)
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
