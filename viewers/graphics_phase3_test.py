"""Graphics Phase 3 Test — enhanced buildings, spell visuals, item icons.

Tests:
1. Building tile showcase (floor, door, window, built floor)
2. Roof tile showcase (all roof styles)
3. Spell/projectile visual showcase (fireball, arrow, lightning, ice)
4. Item icon showcase (all icon types)
5. Headless gameplay (200 ticks, settlement visit, combat, inventory)

Output: viewers/graphics_test_output/phase3_*.png
"""

import os
import sys
import math
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "viewers", "graphics_test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_screenshot(screen, name):
    """Save a screenshot to the output directory."""
    import pygame
    path = os.path.join(OUTPUT_DIR, name)
    pygame.image.save(screen, path)
    print(f"  Saved: {path}")
    return path


def test_building_tiles():
    """Render enhanced building tiles: floor, door, window, built_floor."""
    import pygame
    pygame.init()
    from game.ui.renderer_tiles import build_tile_cache

    W, H = 500, 300
    screen = pygame.display.set_mode((W, H))
    surf = pygame.Surface((W, H))
    surf.fill((30, 30, 40))

    font = pygame.font.SysFont("monospace", 10)
    title = font.render("Phase 3: Enhanced Building Tiles", True,
                        (255, 255, 200))
    surf.blit(title, (10, 5))

    cache = build_tile_cache(16)

    # Show tiles at multiple scales
    tiles_to_show = [
        ("floor", 8), ("door", 20), ("window", 23),
        ("built_floor", 14), ("locked_door", 21),
    ]
    from game.settings import (FLOOR, DOOR, WINDOW, BUILT_FLOOR,
                                LOCKED_DOOR, TERRAIN_COLORS)

    tile_map = {
        "floor": FLOOR, "door": DOOR, "window": WINDOW,
        "built_floor": BUILT_FLOOR, "locked_door": LOCKED_DOOR,
    }

    y_base = 30
    for idx, (name, tid) in enumerate(tiles_to_show):
        tile_surf = cache.get(tid)
        if tile_surf is None:
            print(f"  Warning: tile {name} (id={tid}) not in cache")
            continue

        x_base = 20 + idx * 95

        # Original size
        surf.blit(tile_surf, (x_base, y_base))
        label = font.render(name, True, (180, 180, 180))
        surf.blit(label, (x_base, y_base + 20))

        # 2x scaled
        scaled = pygame.transform.scale(tile_surf, (32, 32))
        surf.blit(scaled, (x_base, y_base + 35))
        label2 = font.render("2x", True, (140, 140, 140))
        surf.blit(label2, (x_base, y_base + 70))

        # 4x scaled
        scaled4 = pygame.transform.scale(tile_surf, (64, 64))
        surf.blit(scaled4, (x_base, y_base + 85))
        label4 = font.render("4x", True, (140, 140, 140))
        surf.blit(label4, (x_base, y_base + 152))

    # Build tiles at bigger size directly
    y_base2 = y_base + 170
    subtitle = font.render("32px tile size:", True, (200, 200, 180))
    surf.blit(subtitle, (10, y_base2))
    y_base2 += 14

    cache32 = build_tile_cache(32)
    for idx, (name, tid) in enumerate(tiles_to_show):
        tile_surf = cache32.get(tid)
        if tile_surf is None:
            continue
        x_pos = 20 + idx * 95
        surf.blit(tile_surf, (x_pos, y_base2))
        label = font.render(name, True, (180, 180, 180))
        surf.blit(label, (x_pos, y_base2 + 35))

    return save_screenshot(surf, "phase3_building_tiles.png")


def test_spell_visuals():
    """Render spell/projectile visuals from character_detail.py."""
    import pygame
    pygame.init()
    from game.ui.character_detail import (
        draw_fireball, draw_arrow_projectile,
        draw_lightning_bolt, draw_ice_shard,
    )

    W, H = 600, 400
    screen = pygame.display.set_mode((W, H))
    surf = pygame.Surface((W, H))
    surf.fill((20, 20, 35))

    font = pygame.font.SysFont("monospace", 11)
    title = font.render("Phase 3: Enhanced Spell & Projectile Visuals",
                        True, (255, 255, 200))
    surf.blit(title, (10, 5))

    # Fireball at different sizes
    y = 60
    label = font.render("Fireball:", True, (200, 180, 140))
    surf.blit(label, (10, y - 15))
    for i, r in enumerate([4, 6, 10, 16]):
        x = 60 + i * 120
        draw_fireball(surf, x, y + 20, r)
        rlabel = font.render(f"r={r}", True, (160, 160, 160))
        surf.blit(rlabel, (x - 10, y + 45))

    # Arrows
    y = 140
    label = font.render("Arrow:", True, (200, 180, 140))
    surf.blit(label, (10, y - 15))
    angles = [0, 0.5, 1.0, 1.57, 2.5]
    for i, angle in enumerate(angles):
        x = 60 + i * 100
        x2 = x + int(math.cos(angle) * 30)
        y2 = y + 20 + int(math.sin(angle) * 30)
        draw_arrow_projectile(surf, x, y + 20, x2, y2)

    # Lightning
    y = 230
    label = font.render("Lightning Bolt:", True, (200, 180, 140))
    surf.blit(label, (10, y - 15))
    for i in range(4):
        x1 = 40 + i * 130
        draw_lightning_bolt(surf, x1, y, x1 + 80, y + 50)

    # Ice Shards
    y = 330
    label = font.render("Ice Shard:", True, (200, 180, 140))
    surf.blit(label, (10, y - 15))
    for i, size in enumerate([4, 6, 10, 15]):
        x = 60 + i * 120
        draw_ice_shard(surf, x, y + 20, size)
        slabel = font.render(f"s={size}", True, (160, 160, 160))
        surf.blit(slabel, (x - 10, y + 50))

    return save_screenshot(surf, "phase3_spell_visuals.png")


def test_item_icons():
    """Render all item icon types in a grid."""
    import pygame
    pygame.init()
    from game.ui.item_icons import get_item_icon

    W, H = 600, 400
    screen = pygame.display.set_mode((W, H))
    surf = pygame.Surface((W, H))
    surf.fill((25, 25, 40))

    font = pygame.font.SysFont("monospace", 9)
    title = font.render("Phase 3: Procedural Item Icons", True,
                        (255, 255, 200))
    surf.blit(title, (10, 5))

    items = [
        ("Iron Sword", "weapon"), ("Steel Axe", "weapon"),
        ("Longbow", "weapon"), ("Oak Staff", "weapon"),
        ("Iron Shield", "armor"), ("Chain Mail", "armor"),
        ("Iron Helm", "armor"), ("Leather Armor", "armor"),
        ("Health Potion", "consumable"), ("Bread", "food"),
        ("Cooked Meat", "food"), ("Apple", "food"),
        ("Gold Coins", "resource"), ("Iron Ore", "resource"),
        ("Oak Log", "resource"), ("Healing Herb", "resource"),
        ("Magic Scroll", "quest"), ("Ruby Gem", "resource"),
        ("Bronze Key", "tool"), ("Torch", "tool"),
        ("Rope", "tool"), ("War Hammer", "weapon"),
        ("Iron Spear", "weapon"), ("Ale", "drink"),
        ("Iron Pickaxe", "tool"), ("Silver Ring", "artifact"),
        ("Gold Amulet", "artifact"), ("Iron Dagger", "weapon"),
    ]

    cols = 7
    cell_w = 80
    cell_h = 40
    x_start = 15
    y_start = 25

    for idx, (name, kind) in enumerate(items):
        col = idx % cols
        row = idx // cols
        x = x_start + col * cell_w
        y = y_start + row * cell_h

        icon = get_item_icon(name, kind)

        # Draw icon at 1x
        surf.blit(icon, (x, y + 4))

        # Draw icon at 2x for visibility
        scaled = pygame.transform.scale(icon, (28, 28))
        surf.blit(scaled, (x + 16, y - 2))

        # Label
        label = font.render(name[:10], True, (170, 170, 170))
        surf.blit(label, (x, y + 30))

    return save_screenshot(surf, "phase3_item_icons.png")


def test_roof_tiles():
    """Render all roof tile styles."""
    import pygame
    pygame.init()

    W, H = 500, 300
    screen = pygame.display.set_mode((W, H))
    surf = pygame.Surface((W, H))
    surf.fill((30, 30, 45))

    font = pygame.font.SysFont("monospace", 9)
    title = font.render("Phase 3: Enhanced Roof Tile Styles", True,
                        (255, 255, 200))
    surf.blit(title, (10, 5))

    # We need a Renderer to build the roof cache
    from game.ui.renderer import Renderer
    r = Renderer(surf)
    r._build_roof_cache()

    # Flat roof tiles
    y_base = 25
    label = font.render("Flat roof tiles (16px + 4x scaled):", True,
                        (200, 200, 180))
    surf.blit(label, (10, y_base))
    y_base += 14

    roof_kinds = ["village", "hamlet", "town", "city", "castle",
                  "temple", "tavern", "blacksmith", "market", "default"]

    for idx, kind in enumerate(roof_kinds):
        col = idx % 5
        row = idx // 5
        x = 15 + col * 95
        y = y_base + row * 90

        tile = r._roof_cache.get(kind)
        if tile is None:
            continue

        # 1x
        surf.blit(tile, (x, y))
        # 4x
        scaled = pygame.transform.scale(tile, (64, 64))
        surf.blit(scaled, (x + 20, y))

        label = font.render(kind[:10], True, (170, 170, 170))
        surf.blit(label, (x, y + 68))

    return save_screenshot(surf, "phase3_roof_tiles.png")


def test_headless_gameplay():
    """Run headless game: 200 ticks, settlement visit, inventory check."""
    import pygame
    pygame.init()
    try:
        from game.ui.screenshot import HeadlessGame
        print("  Creating HeadlessGame (seed=42, use_chunked=True)...")
        hg = HeadlessGame(seed=42, mode="god", export_dir=OUTPUT_DIR,
                          use_chunked=True)
        print(f"  World created. Spawn: {hg.world.spawn_point}")
        print(f"  NPCs: {len(hg.world_mgr.npcs)}")

        # 1. Screenshot at spawn
        hg.tick(5)
        path1 = hg.capture("gameplay", suffix="phase3_spawn")
        print(f"  Saved spawn: {path1}")

        # 2. Visit a settlement
        if hg.world.structures:
            s = hg.world.structures[0]
            hg.move_player(float(s.x), float(s.y))
            hg.tick(5)
            path2 = hg.capture("gameplay", suffix="phase3_settlement")
            print(f"  Saved settlement: {path2}")

        # 3. Give player some items and show inventory
        from game.core.items import Item
        test_items = [
            Item("Iron Sword", "weapon", damage=5, value=50,
                 description="A sharp blade"),
            Item("Chain Mail", "armor", defense=3, value=80,
                 description="Linked metal rings"),
            Item("Health Potion", "consumable", heal=25, value=20,
                 description="Restores health"),
            Item("Bread", "food", heal=5, value=2,
                 description="Fresh baked"),
            Item("Gold Coins", "resource", value=100,
                 description="Shiny gold"),
        ]
        for item in test_items:
            hg.player.inventory.append(item)
        if not hg.player.equipped_weapon:
            hg.player.equipped_weapon = test_items[0]
        if not hg.player.equipped_armor:
            hg.player.equipped_armor = test_items[1]

        # Open inventory and capture
        hg.ui.show_inventory = True
        hg.ui.inv_selected = 0
        hg._draw_gameplay()
        hg.ui.draw_inventory(hg.player)
        path3 = save_screenshot(hg.screen, "phase3_inventory.png")
        hg.ui.show_inventory = False

        # 4. Spawn spell effects for visual test
        hg.move_player(float(hg.world.spawn_point[0]),
                        float(hg.world.spawn_point[1]))
        hg.tick(3)
        px, py = hg.player.x, hg.player.y
        hg.renderer.spawn_spell_effect("fireball", px, py, px + 3, py + 2)
        hg.renderer.spawn_spell_effect("lightning_bolt", px - 2, py - 1,
                                        px + 4, py + 3)
        hg.renderer.spawn_spell_effect("ice_shard", px + 2, py - 2,
                                        px + 2, py - 2)
        hg.renderer.spawn_spell_effect("heal", px, py, px, py)
        # Draw with effects
        hg._draw_gameplay()
        hg.renderer.draw_spell_effects(hg.camera, 0.016)
        path4 = save_screenshot(hg.screen, "phase3_combat_spells.png")

        # 5. Run 200 ticks to verify no crashes
        print("  Running 200 simulation ticks...")
        hg.tick(200)
        print("  200 ticks completed without crash.")

        path5 = hg.capture("gameplay", suffix="phase3_after200")
        print(f"  Saved after 200 ticks: {path5}")

        return True
    except Exception as e:
        print(f"  HeadlessGame error: {e}")
        traceback.print_exc()
        return False


def main():
    print("=== Graphics Phase 3 Test ===")
    print("  Buildings, Spells, Item Icons, Roofs")
    print()
    results = {}

    print("1. Building Tiles (floor, door, window, built_floor)...")
    try:
        results["building_tiles"] = test_building_tiles()
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        results["building_tiles"] = None

    print("2. Spell/Projectile Visuals...")
    try:
        results["spells"] = test_spell_visuals()
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        results["spells"] = None

    print("3. Item Icons...")
    try:
        results["icons"] = test_item_icons()
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        results["icons"] = None

    print("4. Roof Tiles...")
    try:
        results["roofs"] = test_roof_tiles()
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        results["roofs"] = None

    print("5. Headless Gameplay (200 ticks)...")
    results["gameplay"] = test_headless_gameplay()

    print()
    print("=== Results ===")
    for key, val in results.items():
        status = "OK" if val else "FAILED"
        print(f"  {key}: {status}")
    print(f"\nOutput dir: {OUTPUT_DIR}")
    print("Done!")


if __name__ == "__main__":
    main()
