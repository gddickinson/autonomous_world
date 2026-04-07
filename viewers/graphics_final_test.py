"""Graphics Final Test — seasonal visuals, ambient particles, minimap, bars.

Tests:
1. Spring daytime screenshot (default)
2. Advance to autumn — screenshot showing color change
3. Night scene with fireflies/stars
4. Settlement with enhanced buildings + minimap
5. Run 200 ticks to verify stability
6. Save all to viewers/graphics_test_output/final_*.png

Output: viewers/graphics_test_output/final_*.png
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


def test_seasonal_tiles():
    """Generate seasonal tile showcase — all 4 seasons side by side."""
    import pygame
    pygame.init()

    from game.ui.terrain_sprites_seasonal import generate_seasonal_variant
    from game.settings import GRASS, FOREST, WATER, DENSE_FOREST, SNOW, SWAMP

    W, H = 640, 320
    screen = pygame.display.set_mode((W, H))
    surf = pygame.Surface((W, H))
    surf.fill((20, 20, 30))

    font = pygame.font.SysFont("monospace", 11)
    title = font.render("Seasonal Terrain Variants (Spring/Summer/Autumn/Winter)",
                        True, (240, 240, 200))
    surf.blit(title, (10, 5))

    seasons = ["spring", "summer", "autumn", "winter"]
    tiles = [
        ("Grass", GRASS), ("Forest", FOREST), ("Water", WATER),
        ("Dense Forest", DENSE_FOREST), ("Snow", SNOW), ("Swamp", SWAMP),
    ]

    y_base = 25
    for row_idx, (name, tid) in enumerate(tiles):
        label = font.render(name, True, (180, 180, 180))
        surf.blit(label, (5, y_base + row_idx * 48 + 8))

        for col_idx, season in enumerate(seasons):
            tile = generate_seasonal_variant(tid, season, 0, 16)
            x = 110 + col_idx * 130
            y = y_base + row_idx * 48
            # Show at 1x
            surf.blit(tile, (x, y))
            # Show at 2x
            scaled = pygame.transform.scale(tile, (32, 32))
            surf.blit(scaled, (x + 20, y))
            # Season label on first row
            if row_idx == 0:
                sl = font.render(season.title(), True, (200, 200, 160))
                surf.blit(sl, (x, y - 12))

    screen.blit(surf, (0, 0))
    return save_screenshot(screen, "final_seasonal_tiles.png")


def test_spring_daytime():
    """Capture spring daytime gameplay."""
    import pygame
    pygame.init()
    from game.ui.screenshot import HeadlessGame

    print("  Creating HeadlessGame (seed=42, spring)...")
    hg = HeadlessGame(seed=42, mode="god", export_dir=OUTPUT_DIR,
                      use_chunked=True)

    # Set season to spring
    hg.renderer.set_season("spring")

    sp = hg.world.spawn_point
    hg.move_player(float(sp[0]), float(sp[1]))
    hg.tick(5)
    path = hg.capture("gameplay", suffix="final_spring_day")
    print(f"  Spring day: {path}")
    return hg, path


def test_autumn_scene(hg):
    """Switch to autumn and capture."""
    hg.renderer.set_season("autumn")
    hg.tick(3)
    path = hg.capture("gameplay", suffix="final_autumn")
    print(f"  Autumn: {path}")
    return path


def test_night_scene(hg):
    """Advance to night and capture with fireflies/stars."""
    # Set time to night (0.0 = midnight)
    hg.time_sys.time = 0.0
    hg.renderer.set_season("summer")
    hg.tick(3)

    # Force a draw with night lighting
    hg._draw_gameplay()
    hg.renderer.draw_lighting(0.0, hg.camera, hg.world)

    # Tick ambient particles with night conditions
    for _ in range(30):
        hg.renderer.ambient_particles.update(
            0.033, "summer", True, "forest", "clear", False)
    hg.renderer.ambient_particles.draw(hg.screen)

    path = save_screenshot(hg.screen, "final_night_scene.png")
    print(f"  Night scene: {path}")
    return path


def test_settlement_minimap(hg):
    """Visit a settlement with minimap visible."""
    # Reset to daytime
    hg.time_sys.time = 0.4  # midday
    hg.renderer.set_season("summer")

    if hg.world.structures:
        s = hg.world.structures[0]
        hg.move_player(float(s.x), float(s.y))
        hg.tick(5)

    # Draw with minimap
    hg.show_minimap = True
    hg._draw_gameplay()
    path = save_screenshot(hg.screen, "final_settlement_minimap.png")
    print(f"  Settlement+minimap: {path}")
    hg.show_minimap = False
    return path


def test_winter_scene(hg):
    """Winter scene screenshot."""
    hg.renderer.set_season("winter")
    hg.tick(3)
    path = hg.capture("gameplay", suffix="final_winter")
    print(f"  Winter: {path}")
    return path


def test_stability(hg):
    """Run 200 ticks and verify no crashes."""
    print("  Running 200 simulation ticks...")
    hg.renderer.set_season("summer")
    hg.time_sys.time = 0.4
    try:
        hg.tick(200)
        print("  200 ticks completed successfully.")
        path = hg.capture("gameplay", suffix="final_after200")
        print(f"  After 200 ticks: {path}")
        return True
    except Exception as e:
        print(f"  FAILED at tick: {e}")
        traceback.print_exc()
        return False


def main():
    print("=== Graphics Final Test: Seasons + Ambient + Minimap + Polish ===")
    print()
    results = {}

    # 1. Seasonal tile showcase
    print("1. Seasonal tile showcase...")
    try:
        results["seasonal_tiles"] = test_seasonal_tiles()
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        results["seasonal_tiles"] = None

    # 2-6. Full gameplay tests
    hg = None
    print()
    print("2. Spring daytime...")
    try:
        hg, path = test_spring_daytime()
        results["spring_day"] = path
    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()
        results["spring_day"] = None

    if hg:
        print()
        print("3. Autumn scene...")
        try:
            results["autumn"] = test_autumn_scene(hg)
        except Exception as e:
            print(f"  FAILED: {e}")
            traceback.print_exc()
            results["autumn"] = None

        print()
        print("4. Night scene with ambient effects...")
        try:
            results["night"] = test_night_scene(hg)
        except Exception as e:
            print(f"  FAILED: {e}")
            traceback.print_exc()
            results["night"] = None

        print()
        print("5. Settlement with minimap...")
        try:
            results["settlement_minimap"] = test_settlement_minimap(hg)
        except Exception as e:
            print(f"  FAILED: {e}")
            traceback.print_exc()
            results["settlement_minimap"] = None

        print()
        print("5b. Winter scene...")
        try:
            results["winter"] = test_winter_scene(hg)
        except Exception as e:
            print(f"  FAILED: {e}")
            traceback.print_exc()
            results["winter"] = None

        print()
        print("6. 200-tick stability run...")
        try:
            results["stability"] = test_stability(hg)
        except Exception as e:
            print(f"  FAILED: {e}")
            traceback.print_exc()
            results["stability"] = False

    print()
    print("=== Final Test Results ===")
    all_pass = True
    for k, v in results.items():
        status = "PASS" if v else "FAIL"
        if not v:
            all_pass = False
        print(f"  {k}: {status}")

    print()
    if all_pass:
        print("All final graphics tests passed.")
    else:
        print("Some tests failed — check output above.")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
