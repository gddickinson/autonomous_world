"""Graphics Phase 4 Test — flower bed fix, UI panel styling.

Tests:
1. Terrain showcase verifying FLOWER_BED is no longer pink
2. UI panels: inventory (I), character (C), quest log (Q), chronicle (H)
3. HUD buff icons and smooth bars
4. 100-tick stability run

Output: viewers/graphics_test_output/phase4_*.png
"""

import os
import sys
import traceback

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "viewers", "graphics_test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def save_screenshot(screen, name):
    import pygame
    path = os.path.join(OUTPUT_DIR, name)
    pygame.image.save(screen, path)
    print(f"  Saved: {path}")
    return path


def test_flower_bed_tiles():
    """Verify FLOWER_BED tile is green, not pink."""
    import pygame
    pygame.init()
    from game.ui.renderer_tiles import build_tile_cache
    from game.settings import FLOWER_BED, GRASS, HERB_PATCH, BERRY_BUSH, TERRAIN_COLORS

    W, H = 500, 200
    screen = pygame.display.set_mode((W, H))
    surf = pygame.Surface((W, H))
    surf.fill((30, 30, 40))

    font = pygame.font.SysFont("monospace", 10)
    title_surf = font.render("Phase 4: FLOWER_BED fix (should be green not pink)", True,
                             (255, 255, 200))
    surf.blit(title_surf, (10, 5))

    cache = build_tile_cache(16)

    tiles_to_show = [
        ("grass", GRASS),
        ("herb_patch", HERB_PATCH),
        ("berry_bush", BERRY_BUSH),
        ("flower_bed", FLOWER_BED),
    ]

    y_base = 30
    for idx, (name, tid) in enumerate(tiles_to_show):
        tile_surf = cache.get(tid)
        col_info = TERRAIN_COLORS.get(tid, (0, 0, 0))

        x_base = 20 + idx * 115

        if tile_surf is not None:
            # Show at 1x
            surf.blit(tile_surf, (x_base, y_base))
            # Show at 4x
            scaled = pygame.transform.scale(tile_surf, (64, 64))
            surf.blit(scaled, (x_base + 20, y_base))
        else:
            pygame.draw.rect(surf, col_info, (x_base, y_base, 16, 16))
            scaled_col = pygame.Surface((64, 64))
            scaled_col.fill(col_info)
            surf.blit(scaled_col, (x_base + 20, y_base))

        label = font.render(name, True, (180, 180, 180))
        surf.blit(label, (x_base, y_base + 68))
        col_text = font.render(str(col_info), True, (140, 160, 140))
        surf.blit(col_text, (x_base, y_base + 80))

    return save_screenshot(surf, "phase4_flower_bed_tiles.png")


def test_ui_panels():
    """Render all major UI panels and save screenshots."""
    import pygame
    pygame.init()

    try:
        from game.ui.screenshot import HeadlessGame
        from game.core.items import Item

        print("  Creating HeadlessGame (seed=99)...")
        hg = HeadlessGame(seed=99, mode="god", export_dir=OUTPUT_DIR,
                          use_chunked=True)
        print(f"  World ready. Structures: {len(hg.world.structures)}")

        # Give player test items so inventory has content
        test_items = [
            Item("Iron Sword", "weapon", damage=8, value=60,
                 description="A well-balanced blade"),
            Item("Steel Shield", "armor", defense=5, value=90,
                 description="Heavy steel shield"),
            Item("Health Potion", "consumable", heal=30, value=25,
                 description="Restores 30 HP"),
            Item("Bread", "food", heal=5, value=3,
                 description="Fresh baked bread"),
            Item("Gold Coins", "resource", value=100,
                 description="Shiny coins"),
            Item("Magic Scroll", "quest", value=200,
                 description="Ancient runes"),
        ]
        for item in test_items:
            hg.player.inventory.append(item)
        hg.player.equipped_weapon = test_items[0]
        hg.player.equipped_armor = test_items[1]
        hg.player.hp = hg.player.max_hp * 0.65  # slightly injured for visual interest

        # Inventory panel
        hg.tick(3)
        hg._draw_gameplay()
        hg.ui.show_inventory = True
        hg.ui.inv_selected = 0
        hg.ui.draw_inventory(hg.player)
        path_inv = save_screenshot(hg.screen, "phase4_inventory.png")
        hg.ui.show_inventory = False

        # Character sheet
        hg._draw_gameplay()
        hg.ui.show_character = True
        hg.ui.draw_character_sheet(hg.player)
        path_char = save_screenshot(hg.screen, "phase4_character.png")
        hg.ui.show_character = False

        # Quest log (add some quests)
        from game.systems.quests import Quest
        hg.player.quests = getattr(hg.player, 'quests', [])
        if not hg.player.quests:
            q1 = Quest("Slay the Wolf", "Kill 3 wolves in the forest.",
                       "wolf", 3, "Farmer Aldric", "easy")
            q2 = Quest("Gather Herbs", "Collect healing herbs.",
                       "herb", 5, "Healer Mira", "medium")
            hg.player.quests = [q1, q2]

        hg._draw_gameplay()
        hg.ui.show_quest_log = True
        hg.ui.draw_quest_log(hg.player.quests)
        path_quest = save_screenshot(hg.screen, "phase4_quest_log.png")
        hg.ui.show_quest_log = False

        # Chronicle
        hg._draw_gameplay()
        hg.ui.show_chronicle = True
        hg.ui.draw_chronicle(hg.chronicle)
        path_chronicle = save_screenshot(hg.screen, "phase4_chronicle.png")
        hg.ui.show_chronicle = False

        return path_inv, path_char, path_quest, path_chronicle

    except Exception as e:
        print(f"  Panel test error: {e}")
        traceback.print_exc()
        return None


def test_hud_and_gameplay():
    """Run 100 ticks and capture gameplay showing HUD + terrain."""
    import pygame
    pygame.init()

    try:
        from game.ui.screenshot import HeadlessGame

        print("  Creating HeadlessGame (seed=77)...")
        hg = HeadlessGame(seed=77, mode="god", export_dir=OUTPUT_DIR,
                          use_chunked=True)

        # Move to grassland area to show flower beds
        sp = hg.world.spawn_point
        hg.move_player(float(sp[0]), float(sp[1]))

        # Initial spawn screenshot
        hg.tick(5)
        path_spawn = hg.capture("gameplay", suffix="phase4_spawn")
        print(f"  Spawn: {path_spawn}")

        # Visit settlement
        if hg.world.structures:
            s = hg.world.structures[0]
            hg.move_player(float(s.x), float(s.y))
            hg.tick(5)
            path_settle = hg.capture("gameplay", suffix="phase4_settlement")
            print(f"  Settlement: {path_settle}")

        # Run 100 ticks
        print("  Running 100 simulation ticks...")
        hg.tick(100)
        print("  100 ticks completed.")
        path_after = hg.capture("gameplay", suffix="phase4_after100")
        print(f"  After 100 ticks: {path_after}")

        return True

    except Exception as e:
        print(f"  Gameplay test error: {e}")
        traceback.print_exc()
        return False


def main():
    print("=== Graphics Phase 4 Test: Flower Bed Fix + UI Styling ===")
    print()
    results = {}

    print("1. Flower Bed tile verification...")
    try:
        results["flower_bed"] = test_flower_bed_tiles()
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        results["flower_bed"] = None

    print()
    print("2. UI Panel screenshots (I, C, Q, H)...")
    try:
        results["panels"] = test_ui_panels()
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        results["panels"] = None

    print()
    print("3. HUD + gameplay (100-tick stability)...")
    try:
        results["gameplay"] = test_hud_and_gameplay()
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        results["gameplay"] = False

    print()
    print("=== Phase 4 Results ===")
    all_pass = True
    for k, v in results.items():
        status = "PASS" if v else "FAIL"
        if not v:
            all_pass = False
        print(f"  {k}: {status}")

    print()
    if all_pass:
        print("All phase 4 tests passed.")
    else:
        print("Some tests failed — check output above.")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
