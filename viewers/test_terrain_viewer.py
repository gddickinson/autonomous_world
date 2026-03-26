#!/usr/bin/env python3
"""Terrain & World Object Viewer — all 70 terrain types in all view modes.

Shows each terrain tile rendered at Strategy (16px) and Adventure (32px)
scales with procedural detail textures, organized by category.

Controls:
  LEFT/RIGHT: cycle category
  UP/DOWN: cycle season
  SPACE: toggle adventure tiles (if available)
  S: screenshot
  Esc: quit
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 1100, 750
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Terrain & World Object Viewer")
clock = pygame.time.Clock()
font = pygame.font.SysFont("monospace", 11)
font_md = pygame.font.SysFont("monospace", 14, bold=True)
font_lg = pygame.font.SysFont("monospace", 18, bold=True)

from game.settings import *

# ── Terrain categories ──────────────────────────────────────────────────

CATEGORIES = {
    "Natural": [
        (WATER, "Water"), (SHALLOW_WATER, "Shallow Water"), (SAND, "Sand"),
        (GRASS, "Grass"), (FOREST, "Forest"), (DENSE_FOREST, "Dense Forest"),
        (MOUNTAIN, "Mountain"), (SNOW, "Snow"), (SWAMP, "Swamp"),
        (FARMLAND, "Farmland"), (ROCKY_GROUND, "Rocky Ground"),
        (MARSH, "Marsh"),
    ],
    "Roads & Paths": [
        (ROAD, "Road"), (GRAVEL_ROAD, "Gravel Road"),
        (DIRT_TRACK, "Dirt Track"), (COBBLESTONE, "Cobblestone"),
        (BRIDGE, "Bridge"),
    ],
    "Building Structure": [
        (FLOOR, "Floor"), (WALL, "Wall"), (BUILT_WALL, "Built Wall"),
        (BUILT_FLOOR, "Built Floor"), (DOOR, "Door"),
        (LOCKED_DOOR, "Locked Door"), (WINDOW, "Window"),
        (STAIRS_UP, "Stairs Up"), (STAIRS_DOWN, "Stairs Down"),
        (LADDER_UP, "Ladder Up"), (LADDER_DOWN, "Ladder Down"),
        (ARCHWAY, "Archway"), (IRON_GATE, "Iron Gate"),
        (STABLE_FLOOR, "Stable Floor"), (COURTYARD, "Courtyard"),
        (ARENA_SAND, "Arena Sand"),
    ],
    "Furniture": [
        (TABLE, "Table"), (BED, "Bed"), (CHEST, "Chest"),
        (THRONE, "Throne"), (BOOKSHELF, "Bookshelf"),
        (BARREL, "Barrel"), (ANVIL, "Anvil"),
        (FIREPLACE, "Fireplace"), (FORGE_FIRE, "Forge Fire"),
        (FOUNTAIN, "Fountain"), (CARPET, "Carpet"),
        (MOSAIC, "Mosaic"), (PILLAR, "Pillar"), (ALTAR, "Altar"),
        (WELL, "Well"), (GRAVESTONE, "Gravestone"),
    ],
    "Resources": [
        (TREE_STUMP, "Tree Stump"), (TILLED_SOIL, "Tilled Soil"),
        (ORE_VEIN, "Ore Vein"), (HERB_PATCH, "Herb Patch"),
        (BERRY_BUSH, "Berry Bush"), (CLAY_PIT, "Clay Pit"),
        (MUSHROOMS, "Mushrooms"), (WHEAT_FIELD, "Wheat Field"),
        (VEGETABLE_PLOT, "Vegetable Plot"), (FRUIT_TREE, "Fruit Tree"),
        (FLOWER_BED, "Flower Bed"), (GEM_DEPOSIT, "Gem Deposit"),
        (COPPER_VEIN, "Copper Vein"), (FLAX_FIELD, "Flax Field"),
        (BEEHIVE, "Beehive"), (SALT_FLAT, "Salt Flat"),
        (FALLEN_TREE, "Fallen Tree"), (RUBBLE, "Rubble"),
    ],
    "Geography": [
        (CLIFF, "Cliff"), (GORGE, "Gorge"),
        (MOUNTAIN_PASS, "Mountain Pass"),
    ],
}

CATEGORY_NAMES = list(CATEGORIES.keys())
SEASONS = ["summer", "autumn", "winter", "spring"]


def _build_tile(terrain_type, size):
    """Build a terrain tile surface at given size using base color + procedural detail."""
    color = TERRAIN_COLORS.get(terrain_type, (100, 100, 100))
    surf = pygame.Surface((size, size))
    r, g, b = color
    surf.fill(color)

    # Add procedural detail (simplified from renderer._build_tile_cache)
    if terrain_type == GRASS:
        for i in range(max(2, size // 4)):
            x = (hash(i * 7 + terrain_type) % (size - 2)) + 1
            y = (hash(i * 13 + terrain_type) % (size - 2)) + 1
            pygame.draw.line(surf, (max(0, r - 15), min(255, g + 10), max(0, b - 10)),
                             (x, y), (x, y + max(1, size // 8)))
    elif terrain_type == WATER:
        deep = (max(0, r - 15), max(0, g - 5), min(255, b + 10))
        surf.fill(deep)
        for i in range(3):
            y_pos = size // 3 + i * (size // 4)
            wave_c = (min(255, r + 25), min(255, g + 25), min(255, b + 25))
            for px in range(size):
                if (px * 3 + i * 7) % 4 < 2:
                    surf.set_at((px, min(y_pos, size - 1)), wave_c)
    elif terrain_type == FOREST:
        cx, cy = size // 2, size // 2
        trunk_w = max(2, size // 8)
        pygame.draw.rect(surf, (75, 50, 30),
                         (cx - trunk_w // 2, cy, trunk_w, size // 3))
        canopy_r = max(3, size // 3)
        pygame.draw.circle(surf, (max(0, r - 15), g, max(0, b - 8)),
                           (cx, cy - canopy_r // 3), canopy_r)
    elif terrain_type == DENSE_FOREST:
        for tx, ty in [(size // 4, size // 4), (size * 3 // 4, size // 3),
                       (size // 2, size * 2 // 3)]:
            pygame.draw.rect(surf, (75, 50, 30), (tx - 1, ty, 3, size // 4))
            pygame.draw.circle(surf, (max(0, r - 10), min(255, g + 5), b),
                               (tx, ty - 2), max(3, size // 5))
    elif terrain_type == MOUNTAIN:
        mid = size // 2
        pts = [(0, size), (mid, max(2, size // 5)), (size, size)]
        pygame.draw.polygon(surf, (min(255, r + 10), min(255, g + 5), min(255, b + 5)), pts)
        # Snow cap
        pygame.draw.polygon(surf, (230, 235, 240),
                            [(mid - size // 6, size // 3),
                             (mid, max(2, size // 5)),
                             (mid + size // 6, size // 3)])
    elif terrain_type == SNOW:
        for i in range(max(2, size // 3)):
            sx = hash(i * 11) % size
            sy = hash(i * 17) % size
            surf.set_at((sx, sy), (240, 245, 250))
    elif terrain_type == SAND:
        for i in range(max(3, size // 2)):
            sx = hash(i * 19 + 5) % size
            sy = hash(i * 23 + 7) % size
            v = hash(i * 31) % 20 - 10
            surf.set_at((sx, sy), (min(255, r + v), min(255, g + v), min(255, b + v)))
    elif terrain_type == ROAD:
        pygame.draw.line(surf, (min(255, r + 10), min(255, g + 8), min(255, b + 5)),
                         (size // 2, 0), (size // 2, size), max(1, size // 4))
    elif terrain_type == FIREPLACE:
        pygame.draw.rect(surf, (100, 60, 30), (size // 4, size // 4,
                                                size // 2, size // 2))
        pygame.draw.circle(surf, (240, 140, 30), (size // 2, size // 2),
                           max(2, size // 5))
    elif terrain_type == FOUNTAIN:
        pygame.draw.circle(surf, (50, 100, 160), (size // 2, size // 2),
                           max(3, size // 3))
        pygame.draw.circle(surf, (100, 170, 220), (size // 2, size // 2),
                           max(2, size // 5))

    return surf


def _apply_season(color, season):
    """Tint a color for a season."""
    r, g, b = color
    if season == "autumn":
        return (min(255, r + 20), max(0, g - 20), max(0, b - 10))
    elif season == "winter":
        avg = (r + g + b) // 3
        return (min(255, (r + avg) // 2 + 20),
                min(255, (g + avg) // 2 + 15),
                min(255, (b + avg) // 2 + 25))
    elif season == "spring":
        return (r, min(255, g + 15), min(255, b + 5))
    return (r, g, b)


def main():
    cat_idx = 0
    season_idx = 0
    show_adventure = True

    running = True
    while running:
        dt = clock.tick(30) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT:
                    cat_idx = (cat_idx - 1) % len(CATEGORY_NAMES)
                elif event.key == pygame.K_RIGHT:
                    cat_idx = (cat_idx + 1) % len(CATEGORY_NAMES)
                elif event.key == pygame.K_UP:
                    season_idx = (season_idx - 1) % len(SEASONS)
                elif event.key == pygame.K_DOWN:
                    season_idx = (season_idx + 1) % len(SEASONS)
                elif event.key == pygame.K_SPACE:
                    show_adventure = not show_adventure
                elif event.key == pygame.K_s:
                    pygame.image.save(screen, "screenshot_terrain_viewer.png")

        # ── Render ──────────────────────────────────────────────────
        screen.fill((30, 30, 40))

        cat_name = CATEGORY_NAMES[cat_idx]
        season = SEASONS[season_idx]
        tiles = CATEGORIES[cat_name]

        # Title
        title = font_lg.render(
            f"Terrain: {cat_name} | Season: {season}", True, (255, 255, 255))
        screen.blit(title, (20, 15))
        subtitle = font.render(
            f"Category {cat_idx + 1}/{len(CATEGORY_NAMES)} | "
            f"{len(tiles)} tiles | SPACE: toggle adventure size",
            True, (160, 160, 180))
        screen.blit(subtitle, (20, 40))

        # Grid of tiles
        cols = 6 if show_adventure else 9
        margin_x = 30
        margin_y = 70
        cell_w = (SCREEN_W - margin_x * 2) // cols
        cell_h = 110 if show_adventure else 80

        for i, (tile_type, name) in enumerate(tiles):
            col = i % cols
            row = i // cols
            cx = margin_x + col * cell_w + cell_w // 2
            cy = margin_y + row * cell_h

            # Strategy tile (16px)
            strat_surf = _build_tile(tile_type, 16)
            # Apply season tint
            if season != "summer":
                base_color = TERRAIN_COLORS.get(tile_type, (100, 100, 100))
                tinted = _apply_season(base_color, season)
                strat_surf.fill(tinted)

            # Draw 2x scaled for visibility
            scaled_strat = pygame.transform.scale(strat_surf, (32, 32))
            screen.blit(scaled_strat, (cx - 16, cy))
            label = font.render("16px", True, (120, 120, 140))
            screen.blit(label, (cx - 14, cy + 34))

            # Adventure tile (32px) — shown alongside
            if show_adventure:
                adv_surf = _build_tile(tile_type, 32)
                if season != "summer":
                    base_color = TERRAIN_COLORS.get(tile_type, (100, 100, 100))
                    tinted = _apply_season(base_color, season)
                    adv_surf.fill(tinted)
                screen.blit(adv_surf, (cx + 24, cy))
                label2 = font.render("32px", True, (120, 120, 140))
                screen.blit(label2, (cx + 28, cy + 34))

            # Tile name
            name_surf = font.render(name, True, (200, 200, 220))
            name_x = cx - name_surf.get_width() // 2 + (12 if show_adventure else 0)
            screen.blit(name_surf, (name_x, cy + 48))

            # Color swatch
            tc = TERRAIN_COLORS.get(tile_type, (100, 100, 100))
            if season != "summer":
                tc = _apply_season(tc, season)
            pygame.draw.rect(screen, tc, (cx - 20, cy + 62, 12, 8))
            hex_label = font.render(f"#{tc[0]:02x}{tc[1]:02x}{tc[2]:02x}",
                                    True, (100, 100, 120))
            screen.blit(hex_label, (cx - 6, cy + 62))

        # Category tabs at bottom
        tab_y = SCREEN_H - 30
        tab_x = 20
        for ci, cname in enumerate(CATEGORY_NAMES):
            color = (220, 220, 240) if ci == cat_idx else (100, 100, 120)
            tab_surf = font.render(f"[{cname}]", True, color)
            screen.blit(tab_surf, (tab_x, tab_y))
            tab_x += tab_surf.get_width() + 10

        # Controls
        controls = ["LEFT/RIGHT: category", "UP/DOWN: season",
                    "SPACE: toggle 32px", "S: screenshot"]
        for i, c in enumerate(controls):
            screen.blit(font.render(c, True, (100, 100, 120)),
                        (SCREEN_W - 200, 15 + i * 14))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
