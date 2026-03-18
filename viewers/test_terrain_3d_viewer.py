#!/usr/bin/env python3
"""3D Terrain Viewer — all terrain types rendered as 3D tiles.

Shows terrain tiles as textured 3D surfaces with elevation, trees,
water, and resource objects.

Controls:
  PgUp/PgDn: cycle terrain category
  Arrows: camera    +/-: zoom
  S: screenshot    Esc: quit
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from OpenGL.GL import *

from viewers.gl_viewer_base import (
    init_viewer, setup_camera, draw_hud, handle_camera_keys,
    draw_box, draw_sphere_approx,
)
from game.settings import *

# ── Terrain categories ──────────────────────────────────────────────────

CATEGORIES = {
    "Natural": [
        (WATER, "Water"), (SHALLOW_WATER, "Shallow"), (SAND, "Sand"),
        (GRASS, "Grass"), (FOREST, "Forest"), (DENSE_FOREST, "Dense Forest"),
        (MOUNTAIN, "Mountain"), (SNOW, "Snow"), (SWAMP, "Swamp"),
        (FARMLAND, "Farmland"), (ROCKY_GROUND, "Rocky"), (MARSH, "Marsh"),
    ],
    "Roads": [
        (ROAD, "Road"), (GRAVEL_ROAD, "Gravel"), (DIRT_TRACK, "Dirt Track"),
        (COBBLESTONE, "Cobblestone"), (BRIDGE, "Bridge"),
    ],
    "Building": [
        (FLOOR, "Floor"), (WALL, "Wall"), (BUILT_WALL, "Built Wall"),
        (BUILT_FLOOR, "Built Floor"), (DOOR, "Door"), (WINDOW, "Window"),
        (STAIRS_UP, "Stairs Up"), (STAIRS_DOWN, "Stairs Down"),
        (COURTYARD, "Courtyard"), (ARENA_SAND, "Arena"),
    ],
    "Furniture": [
        (TABLE, "Table"), (BED, "Bed"), (CHEST, "Chest"), (THRONE, "Throne"),
        (BOOKSHELF, "Bookshelf"), (BARREL, "Barrel"), (ANVIL, "Anvil"),
        (FIREPLACE, "Fire"), (FOUNTAIN, "Fountain"), (ALTAR, "Altar"),
        (PILLAR, "Pillar"), (WELL, "Well"),
    ],
    "Resources": [
        (ORE_VEIN, "Ore"), (HERB_PATCH, "Herb"), (BERRY_BUSH, "Berry"),
        (WHEAT_FIELD, "Wheat"), (FRUIT_TREE, "Fruit Tree"),
        (FLOWER_BED, "Flowers"), (MUSHROOMS, "Mushrooms"),
        (GEM_DEPOSIT, "Gems"), (COPPER_VEIN, "Copper"),
        (FALLEN_TREE, "Fallen Tree"), (RUBBLE, "Rubble"),
    ],
}

CAT_NAMES = list(CATEGORIES.keys())


def _draw_terrain_tile(tile_type, x, z, color):
    """Draw a single terrain tile as 3D geometry at (x, 0, z)."""
    r, g, b = color

    # Base ground quad
    if tile_type == WATER or tile_type == SHALLOW_WATER:
        y = -0.08 if tile_type == WATER else -0.03
        glColor3f(r / 255, g / 255, b / 255)
        glVertex3f(x, y, z); glVertex3f(x + 1, y, z)
        glVertex3f(x + 1, y, z + 1); glVertex3f(x, y, z + 1)
        # Shimmer highlights
        glColor3f(min(1, r / 255 + 0.1), min(1, g / 255 + 0.1), min(1, b / 255 + 0.08))
        for wx in [0.3, 0.7]:
            glVertex3f(x + wx - 0.05, y + 0.005, z + 0.4)
            glVertex3f(x + wx + 0.05, y + 0.005, z + 0.4)
            glVertex3f(x + wx + 0.05, y + 0.005, z + 0.6)
            glVertex3f(x + wx - 0.05, y + 0.005, z + 0.6)
    elif tile_type == MOUNTAIN:
        # Raised peak
        glColor3f(r / 255, g / 255, b / 255)
        glVertex3f(x, 0, z); glVertex3f(x + 1, 0, z)
        glVertex3f(x + 1, 0, z + 1); glVertex3f(x, 0, z + 1)
        # Peak as pyramid (switch to triangles after)
    else:
        # Flat ground
        v = ((int(x * 7 + z * 13)) % 5) * 0.01
        glColor3f(r / 255 + v, g / 255 + v, b / 255 + v * 0.5)
        glVertex3f(x, 0, z); glVertex3f(x + 1, 0, z)
        glVertex3f(x + 1, 0, z + 1); glVertex3f(x, 0, z + 1)


def _draw_terrain_object(tile_type, x, z, color):
    """Draw 3D objects on top of terrain tiles (trees, furniture, etc.)."""
    if tile_type == FOREST or tile_type == DENSE_FOREST:
        # Tree trunk
        draw_box(x + 0.35, 0, z + 0.35, 0.3, 0.6, 0.3, (85, 60, 35))
        lc = (40, 95, 35) if tile_type == FOREST else (28, 70, 25)
        draw_box(x + 0.15, 0.6, z + 0.15, 0.7, 0.6, 0.7, lc)
        if tile_type == DENSE_FOREST:
            draw_box(x + 0.25, 1.0, z + 0.25, 0.5, 0.4, 0.5,
                     (max(0, lc[0] - 5), min(255, lc[1] + 5), lc[2]))
    elif tile_type == MOUNTAIN:
        draw_box(x + 0.2, 0, z + 0.2, 0.6, 0.8, 0.6, color)
        draw_box(x + 0.3, 0.8, z + 0.3, 0.4, 0.4, 0.4, (200, 205, 210))  # snow cap
    elif tile_type == TABLE:
        draw_box(x + 0.15, 0.35, z + 0.15, 0.7, 0.05, 0.7, (120, 90, 50))
        for lx, lz in [(0.2, 0.2), (0.8, 0.2), (0.2, 0.8), (0.8, 0.8)]:
            draw_box(x + lx - 0.03, 0, z + lz - 0.03, 0.06, 0.35, 0.06, (100, 75, 40))
    elif tile_type == BED:
        draw_box(x + 0.1, 0, z + 0.1, 0.8, 0.25, 0.8, (140, 80, 60))
        draw_box(x + 0.15, 0.25, z + 0.1, 0.7, 0.08, 0.3, (200, 190, 180))
    elif tile_type == CHEST:
        draw_box(x + 0.2, 0, z + 0.2, 0.6, 0.35, 0.6, (160, 130, 50))
        draw_box(x + 0.22, 0.35, z + 0.22, 0.56, 0.15, 0.56, (170, 140, 55))
    elif tile_type == BARREL:
        draw_box(x + 0.2, 0, z + 0.2, 0.6, 0.6, 0.6, (130, 100, 55))
    elif tile_type == ANVIL:
        draw_box(x + 0.2, 0, z + 0.3, 0.6, 0.3, 0.4, (80, 80, 90))
        draw_box(x + 0.15, 0.3, z + 0.25, 0.7, 0.1, 0.5, (100, 100, 110))
    elif tile_type == FIREPLACE:
        draw_box(x + 0.1, 0, z + 0.1, 0.8, 0.5, 0.8, (80, 50, 30))
        draw_box(x + 0.25, 0.1, z + 0.25, 0.5, 0.02, 0.5, (220, 120, 30))
    elif tile_type == FOUNTAIN:
        draw_box(x + 0.15, 0, z + 0.15, 0.7, 0.3, 0.7, (100, 100, 110))
        draw_box(x + 0.25, 0.15, z + 0.25, 0.5, 0.02, 0.5, (60, 130, 200))
    elif tile_type == THRONE:
        draw_box(x + 0.25, 0, z + 0.25, 0.5, 0.35, 0.5, (170, 140, 50))
        draw_box(x + 0.25, 0.35, z + 0.25, 0.5, 0.5, 0.12, (180, 150, 60))
    elif tile_type == BOOKSHELF:
        draw_box(x + 0.15, 0, z + 0.35, 0.7, 0.9, 0.3, (100, 75, 45))
    elif tile_type == PILLAR:
        draw_box(x + 0.3, 0, z + 0.3, 0.4, 1.2, 0.4, (160, 155, 145))
    elif tile_type == ALTAR:
        draw_box(x + 0.15, 0, z + 0.2, 0.7, 0.5, 0.6, (180, 170, 140))
    elif tile_type == WELL:
        draw_box(x + 0.2, 0, z + 0.2, 0.6, 0.35, 0.6, (110, 110, 120))
        draw_box(x + 0.3, 0.05, z + 0.3, 0.4, 0.01, 0.4, (40, 100, 170))
    elif tile_type == WALL:
        draw_box(x, 0, z, 1.0, 1.2, 1.0, color)
    elif tile_type == DOOR:
        draw_box(x + 0.15, 0, z + 0.1, 0.7, 0.9, 0.15, (100, 70, 40))
    elif tile_type == STAIRS_UP:
        for i in range(4):
            draw_box(x + 0.1, i * 0.2, z + 0.1 + i * 0.2, 0.8, 0.2, 0.2,
                     (140 + i * 5, 130 + i * 3, 120 + i * 3))
    elif tile_type == FRUIT_TREE:
        draw_box(x + 0.4, 0, z + 0.4, 0.2, 0.5, 0.2, (85, 60, 35))
        draw_box(x + 0.2, 0.5, z + 0.2, 0.6, 0.5, 0.6, (80, 140, 50))
    elif tile_type in (ORE_VEIN, COPPER_VEIN, GEM_DEPOSIT):
        draw_box(x + 0.15, 0, z + 0.15, 0.7, 0.35, 0.7, color)
    elif tile_type in (WHEAT_FIELD, HERB_PATCH, FLOWER_BED, MUSHROOMS):
        # Low ground cover
        draw_box(x + 0.05, 0, z + 0.05, 0.9, 0.15, 0.9, color)
    elif tile_type == FALLEN_TREE:
        draw_box(x, 0, z + 0.3, 1.0, 0.2, 0.4, (80, 60, 35))
    elif tile_type == RUBBLE:
        for rx, rz, rh in [(0.1, 0.1, 0.2), (0.5, 0.3, 0.15), (0.3, 0.6, 0.25)]:
            draw_box(x + rx, 0, z + rz, 0.3, rh, 0.25, color)


def main():
    screen, clock, font, W, H = init_viewer("3D Terrain & World Objects Viewer")
    cat_idx = 0
    az, el, dist = 35.0, -35.0, 12.0

    running = True
    while running:
        clock.tick(30)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    cat_idx = (cat_idx - 1) % len(CAT_NAMES)
                elif event.key == pygame.K_RIGHT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    cat_idx = (cat_idx + 1) % len(CAT_NAMES)
                elif event.key == pygame.K_s:
                    d = glReadPixels(0, 0, W, H, GL_RGB, GL_UNSIGNED_BYTE)
                    pygame.image.save(pygame.image.fromstring(bytes(d), (W, H), "RGB", True),
                                      "screenshot_terrain_3d.png")
                else:
                    az, el, dist = handle_camera_keys(event, az, el, dist)

        cat = CAT_NAMES[cat_idx]
        tiles = CATEGORIES[cat]
        cols = min(6, len(tiles))
        rows = (len(tiles) + cols - 1) // cols

        cx = cols / 2.0
        cz = rows * 1.5 / 2.0
        setup_camera(W, H, az, el, dist, look_x=cx, look_y=0.3, look_z=cz)

        # Draw all tiles in a grid
        glBegin(GL_QUADS)
        for i, (tile_type, name) in enumerate(tiles):
            col = i % cols
            row = i // cols
            x = col * 1.5
            z = row * 1.5
            color = TERRAIN_COLORS.get(tile_type, (100, 100, 100))
            _draw_terrain_tile(tile_type, x, z, color)
            _draw_terrain_object(tile_type, x, z, color)
        glEnd()

        # Draw mountains as triangles (separate pass)
        glBegin(GL_TRIANGLES)
        for i, (tile_type, name) in enumerate(tiles):
            if tile_type == MOUNTAIN:
                col = i % cols
                row = i // cols
                x, z = col * 1.5, row * 1.5
                color = TERRAIN_COLORS[MOUNTAIN]
        # Tree canopy spheres
        for i, (tile_type, name) in enumerate(tiles):
            if tile_type in (FOREST, DENSE_FOREST, FRUIT_TREE):
                col = i % cols
                row = i // cols
                x, z = col * 1.5, row * 1.5
        glEnd()

        # Labels (as small ground text indicators — just colored squares for now)
        glBegin(GL_QUADS)
        for i, (tile_type, name) in enumerate(tiles):
            col = i % cols
            row = i // cols
            x, z = col * 1.5, row * 1.5
            # Small name indicator bar
            glColor3f(0.15, 0.15, 0.2)
            glVertex3f(x, 0.001, z + 1.15)
            glVertex3f(x + 1, 0.001, z + 1.15)
            glVertex3f(x + 1, 0.001, z + 1.35)
            glVertex3f(x, 0.001, z + 1.35)
        glEnd()

        draw_hud([
            f"Terrain: {cat} ({len(tiles)} tiles)",
            f"[{cat_idx+1}/{len(CAT_NAMES)}] LEFT/RIGHT: category",
            f"SHIFT+Arrows: camera  +/-: zoom  S: screenshot",
        ], font, W, H)

        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
