"""Graphics test — generate screenshots of enhanced terrain tiles.

Creates a synthetic terrain map showing all terrain types and captures
screenshots at 16px (strategy) and 32px (adventure) zoom levels.

Output is saved to viewers/graphics_test_output/
"""

import os
import sys
import pygame

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "viewers", "graphics_test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def render_tile_showcase(tile_size: int, filename: str):
    """Render a showcase of all enhanced terrain tiles at given size.

    Creates a grid showing each terrain type with all 4 variants,
    plus labels.
    """
    pygame.init()

    from game.ui.sprite_loader import SpriteManager
    from game.ui.terrain_sprites import _GENERATORS, NUM_VARIANTS
    from game.settings import TERRAIN_COLORS

    # Terrain type names for labels
    type_names = {
        0: "WATER", 1: "SAND", 2: "GRASS", 3: "FOREST",
        4: "DENSE_FOREST", 5: "MOUNTAIN", 6: "SNOW", 7: "ROAD",
        9: "WALL", 10: "BRIDGE", 11: "FARMLAND", 12: "SWAMP",
        13: "BUILT_WALL", 16: "TILLED_SOIL",
    }

    mgr = SpriteManager()
    mgr.initialize(tile_size)

    # Layout: one row per terrain type, 4 variants + label
    enhanced_types = sorted(_GENERATORS.keys())
    label_w = 120
    padding = 4
    cols = NUM_VARIANTS
    rows = len(enhanced_types)

    img_w = label_w + (tile_size + padding) * cols + padding
    img_h = (tile_size + padding) * rows + padding + 30  # 30 for title

    screen = pygame.display.set_mode((max(img_w, 400), max(img_h, 300)))
    surf = pygame.Surface((img_w, img_h))
    surf.fill((30, 30, 40))

    font = pygame.font.SysFont("monospace", 11)

    # Title
    title = font.render(f"Enhanced Tiles ({tile_size}px) - 4 Variants Each",
                         True, (255, 255, 200))
    surf.blit(title, (10, 5))

    y_offset = 25
    for row, ttype in enumerate(enhanced_types):
        name = type_names.get(ttype, f"TYPE_{ttype}")
        label = font.render(name, True, (200, 200, 200))
        ly = y_offset + row * (tile_size + padding) + padding
        surf.blit(label, (5, ly + tile_size // 2 - 6))

        for v in range(NUM_VARIANTS):
            tile = mgr.get_terrain_tile(ttype, v)
            if tile:
                tx = label_w + v * (tile_size + padding) + padding
                # Scale up for visibility if tile_size is small
                if tile_size <= 16:
                    scaled = pygame.transform.scale(tile, (tile_size * 2, tile_size * 2))
                    surf.blit(scaled, (tx, ly))
                else:
                    surf.blit(tile, (tx, ly))

    # Adjust image height for scaled tiles
    if tile_size <= 16:
        actual_h = y_offset + rows * (tile_size * 2 + padding) + padding
        img_w_actual = label_w + (tile_size * 2 + padding) * cols + padding
        final = pygame.Surface((img_w_actual, actual_h))
        final.fill((30, 30, 40))

        # Re-render with proper scaling
        title = font.render(f"Enhanced Tiles ({tile_size}px, 2x zoom) - 4 Variants",
                             True, (255, 255, 200))
        final.blit(title, (10, 5))

        for row, ttype in enumerate(enhanced_types):
            name = type_names.get(ttype, f"TYPE_{ttype}")
            label = font.render(name, True, (200, 200, 200))
            ly = y_offset + row * (tile_size * 2 + padding) + padding
            final.blit(label, (5, ly + tile_size - 6))

            for v in range(NUM_VARIANTS):
                tile = mgr.get_terrain_tile(ttype, v)
                if tile:
                    tx = label_w + v * (tile_size * 2 + padding) + padding
                    scaled = pygame.transform.scale(tile, (tile_size * 2, tile_size * 2))
                    final.blit(scaled, (tx, ly))

        surf = final

    filepath = os.path.join(OUTPUT_DIR, filename)
    pygame.image.save(surf, filepath)
    print(f"  Saved: {filepath}")
    return filepath


def render_terrain_map(tile_size: int, filename: str):
    """Render a synthetic terrain map showing terrain transitions.

    Creates a landscape with grass, forest, water, mountain, snow,
    sand, road, and farmland arranged to show transitions.
    """
    pygame.init()

    from game.ui.sprite_loader import SpriteManager
    from game.settings import (
        GRASS, WATER, FOREST, DENSE_FOREST, MOUNTAIN,
        SAND, SNOW, ROAD, FARMLAND, WALL, BUILT_WALL,
        SWAMP, BRIDGE, TILLED_SOIL,
    )

    mgr = SpriteManager()
    mgr.initialize(tile_size)

    # Design a 30x20 map
    W, H = 30, 20
    terrain_map = [[GRASS] * W for _ in range(H)]

    # Water body (left side)
    for y in range(3, 12):
        for x in range(0, 7):
            terrain_map[y][x] = WATER
    # Sand beach
    for y in range(3, 12):
        terrain_map[y][7] = SAND
        if y > 4 and y < 11:
            terrain_map[y][8] = SAND

    # Forest (middle-right)
    for y in range(1, 8):
        for x in range(14, 22):
            terrain_map[y][x] = FOREST
    for y in range(2, 6):
        for x in range(16, 20):
            terrain_map[y][x] = DENSE_FOREST

    # Mountain range (top right)
    for y in range(0, 5):
        for x in range(23, 30):
            terrain_map[y][x] = MOUNTAIN
    # Snow caps
    for y in range(0, 2):
        for x in range(24, 29):
            terrain_map[y][x] = SNOW

    # Road (horizontal through middle)
    for x in range(8, 25):
        terrain_map[10][x] = ROAD
    # Bridge over water extension
    terrain_map[10][7] = BRIDGE

    # Farmland (bottom area)
    for y in range(13, 18):
        for x in range(10, 18):
            terrain_map[y][x] = FARMLAND
    for y in range(14, 17):
        for x in range(18, 22):
            terrain_map[y][x] = TILLED_SOIL

    # Settlement (small building footprint near road)
    for y in range(8, 10):
        for x in range(11, 14):
            terrain_map[y][x] = WALL
    terrain_map[9][12] = BUILT_WALL

    # Swamp (bottom left)
    for y in range(14, 19):
        for x in range(2, 8):
            terrain_map[y][x] = SWAMP

    # Render to surface
    map_w = W * tile_size
    map_h = H * tile_size

    # Use a larger display for the map
    display_scale = 2 if tile_size <= 16 else 1
    screen = pygame.display.set_mode((map_w * display_scale, map_h * display_scale))

    map_surf = pygame.Surface((map_w, map_h))
    map_surf.fill((30, 30, 40))

    for y in range(H):
        for x in range(W):
            ttype = terrain_map[y][x]
            tile = mgr.get_variant_for_position(ttype, x, y)
            if tile is None:
                from game.settings import TERRAIN_COLORS
                color = TERRAIN_COLORS.get(ttype, (80, 80, 80))
                pygame.draw.rect(map_surf, color,
                                 (x * tile_size, y * tile_size, tile_size, tile_size))
            else:
                map_surf.blit(tile, (x * tile_size, y * tile_size))

    # Scale up for visibility
    if display_scale > 1:
        final = pygame.transform.scale(map_surf,
                                        (map_w * display_scale, map_h * display_scale))
    else:
        final = map_surf

    filepath = os.path.join(OUTPUT_DIR, filename)
    pygame.image.save(final, filepath)
    print(f"  Saved: {filepath}")
    return filepath


def render_headless_gameplay(filename: str):
    """Use HeadlessGame to capture actual gameplay with enhanced tiles."""
    pygame.init()
    try:
        from game.ui.screenshot import HeadlessGame
        hg = HeadlessGame(seed=12345, mode="god",
                          export_dir=OUTPUT_DIR)
        hg.tick(10)

        # Capture at spawn (gameplay view)
        path = hg.capture("gameplay", suffix="enhanced_tiles")
        print(f"  Saved gameplay: {path}")

        # Find a settlement and capture there
        if hg.world.structures:
            s = hg.world.structures[0]
            hg.move_player(float(s.x), float(s.y))
            hg.tick(5)
            path2 = hg.capture("gameplay", suffix="settlement")
            print(f"  Saved settlement: {path2}")

        # Capture world map
        path3 = hg.capture("world_map", zoom=0.5, suffix="overview")
        print(f"  Saved world_map: {path3}")

        return path
    except Exception as e:
        print(f"  HeadlessGame error: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("=== Graphics Enhancement Test ===")
    print()

    print("1. Tile showcase at 16px (strategy view)...")
    render_tile_showcase(16, "tile_showcase_16px.png")

    print("2. Tile showcase at 32px (adventure view)...")
    render_tile_showcase(32, "tile_showcase_32px.png")

    print("3. Terrain map at 16px (strategy view)...")
    render_terrain_map(16, "terrain_map_16px.png")

    print("4. Terrain map at 32px (adventure view)...")
    render_terrain_map(32, "terrain_map_32px.png")

    print("5. Headless gameplay capture...")
    render_headless_gameplay("gameplay_enhanced.png")

    print()
    print(f"All output saved to: {OUTPUT_DIR}")
    print("Done!")


if __name__ == "__main__":
    main()
