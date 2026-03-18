#!/usr/bin/env python3
"""Building 2.5D Viewer — renders actual game blueprints with in-game rendering.

Stamps real blueprints onto a tile grid and renders them using the same
2.5D height system as the game: south walls, east walls, roof tiles, and
pitched roof shading.

Controls:
  LEFT/RIGHT: cycle building blueprint
  UP/DOWN: cycle roof style (hamlet/village/town/city/castle/temple)
  +/-: change floor count (1-3)
  R: rotate building 90 degrees
  Z: zoom in/out
  S: screenshot
  Esc: quit
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 1000, 750
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Building 2.5D Viewer — Actual Game Blueprints")
clock = pygame.time.Clock()
font = pygame.font.SysFont("monospace", 12)
font_md = pygame.font.SysFont("monospace", 15, bold=True)

from game.settings import *
from game.world.buildings import ALL_BLUEPRINTS


# ── Roof tile generation (from renderer_buildings._get_roof_tile_25d) ───

def _build_roof_tile(kind, ts, variant=0):
    """Reproduce the in-game roof tile generation."""
    surf = pygame.Surface((ts, ts))
    r = g = b = 100  # fallback

    if kind == "hamlet":
        base = (155 + variant * 5, 120 + variant * 3, 55 + variant * 4)
        surf.fill(base)
        r, g, b = base
        for py in range(0, ts, max(2, ts // 8)):
            offset = variant * 2 + (py // 2) % 3
            shade = r - 8 + (py % 4) * 2
            pygame.draw.line(surf, (max(40, shade), max(40, g - 6), max(20, b - 4)),
                             (offset, py), (ts, py))
        for py in range(0, ts, max(5, ts // 3)):
            pygame.draw.line(surf, (r - 20, g - 15, b - 8),
                             (0, py), (min(ts, py + 6), 0))
    elif kind == "village":
        base = (165 + variant * 4, 75 + variant * 3, 40 + variant * 2)
        surf.fill(base)
        r, g, b = base
        tile_h = max(3, ts // 4)
        for row in range(0, ts, tile_h):
            offset = (tile_h // 2) if (row // tile_h) % 2 else 0
            for col in range(offset - tile_h, ts + tile_h, tile_h + 1):
                shade = r + ((col + row) % 3) * 4 - 4
                tc = (max(40, min(255, shade)), max(20, min(255, g + ((col * 3) % 5) - 2)),
                      max(15, min(255, b + ((row * 2) % 3) - 1)))
                pygame.draw.rect(surf, tc, (col, row, tile_h, tile_h - 1))
    elif kind == "town":
        base = (95 + variant * 3, 70 + variant * 2, 45 + variant * 2)
        surf.fill(base)
        r, g, b = base
        plank_h = max(3, ts // 5)
        for row in range(0, ts, plank_h):
            offset = (ts // 3) if (row // plank_h) % 2 else 0
            for col in range(offset - ts // 2, ts + ts // 2, ts // 2):
                shade = ((col + row * 3) % 7) - 3
                pygame.draw.rect(surf, (max(30, r + shade * 2), max(20, g + shade), max(15, b + shade)),
                                 (col, row, ts // 2 - 1, plank_h - 1))
    elif kind == "city":
        base = (90 + variant * 3, 95 + variant * 2, 110 + variant * 3)
        surf.fill(base)
        r, g, b = base
        slate_h = max(2, ts // 6)
        for row in range(0, ts, slate_h):
            offset = (ts // 4) if (row // slate_h) % 2 else 0
            for col in range(offset - ts // 3, ts + ts // 3, ts // 3):
                shade = ((col * 5 + row * 7) % 5) - 2
                pygame.draw.rect(surf, (max(50, r + shade * 2), max(55, g + shade * 2), max(65, b + shade * 3)),
                                 (col, row, ts // 3 - 1, slate_h - 1))
    elif kind == "castle":
        base = (75 + variant * 2, 75 + variant * 2, 80 + variant * 3)
        surf.fill(base)
        r, g, b = base
        block_w = max(3, ts // 3)
        block_h = max(3, ts // 3)
        for row in range(0, ts, block_h):
            offset = (block_w // 2) if (row // block_h) % 2 else 0
            for col in range(offset, ts, block_w):
                shade = ((col + row) % 4) - 2
                pygame.draw.rect(surf, (max(40, r + shade * 3), max(40, g + shade * 3), max(45, b + shade * 3)),
                                 (col, row, block_w - 1, block_h - 1))
    elif kind == "temple":
        base = (210 + variant * 3, 200 + variant * 2, 170 + variant * 4)
        surf.fill(base)
        r, g, b = base
        for py in range(0, ts, 4):
            pygame.draw.line(surf, (min(255, r + 10), min(255, g - 5), max(40, b - 30)),
                             (0, py), (ts, py))
        cx_t, cy_t = ts // 2, ts // 2
        pygame.draw.line(surf, (220, 190, 60), (cx_t - 2, cy_t), (cx_t + 2, cy_t), 1)
        pygame.draw.line(surf, (220, 190, 60), (cx_t, cy_t - 2), (cx_t, cy_t + 2), 1)
    elif kind == "tavern":
        base = (155 + variant * 3, 90 + variant * 2, 50 + variant * 2)
        surf.fill(base)
        r, g, b = base
        tile_h = max(3, ts // 4)
        for row in range(0, ts, tile_h):
            offset = (tile_h // 2) if (row // tile_h) % 2 else 0
            for col in range(offset - tile_h, ts + tile_h, tile_h + 1):
                shade = r + ((col + row) % 3) * 3 - 3
                pygame.draw.rect(surf, (max(40, min(255, shade)), max(20, min(255, g + ((col * 2) % 4) - 2)),
                                        max(15, min(255, b + ((row) % 3) - 1))),
                                 (col, row, tile_h, tile_h - 1))
    elif kind == "blacksmith":
        base = (65 + variant * 2, 62 + variant * 2, 60 + variant * 3)
        surf.fill(base)
        r, g, b = base
        for row in range(0, ts, 3):
            offset = (ts // 3) if (row // 3) % 2 else 0
            for col in range(offset - ts // 2, ts + ts // 2, ts // 2):
                shade = ((col + row * 3) % 5) - 2
                pygame.draw.rect(surf, (max(30, r + shade), max(30, g + shade), max(30, b + shade)),
                                 (col, row, ts // 2 - 1, 2))
    elif kind == "market":
        base = (170 + variant * 4, 110 + variant * 3, 55 + variant * 3)
        surf.fill(base)
        stripe_colors = [(180, 60, 50), (50, 120, 170), (180, 150, 40), (60, 140, 70)]
        stripe_w = max(2, ts // 4)
        for i, sc in enumerate(stripe_colors):
            pygame.draw.rect(surf, sc, (i * stripe_w, 0, stripe_w - 1, ts))
    else:
        surf.fill((90, 80, 70))

    return surf


# ── 2.5D rendering ──────────────────────────────────────────────────────

WALL_S = (140, 125, 105)
WALL_E = (110, 100, 85)

INTERIOR_TILES = frozenset({
    FLOOR, TABLE, BED, CHEST, STAIRS_UP, STAIRS_DOWN,
    FIREPLACE, PILLAR, ALTAR, THRONE, BOOKSHELF, BARREL,
    ANVIL, FORGE_FIRE, FOUNTAIN, CARPET, MOSAIC, ARCHWAY,
    DOOR, WINDOW, LOCKED_DOOR, STABLE_FLOOR,
})

# Map tile type to a specific roof kind override
_TILE_ROOF_KIND = {
    "tavern": "tavern", "shop": "market", "temple": "temple",
    "military": "castle", "castle": "castle", "civic": "town",
}


def _render_building_25d(screen, bp, roof_kind, num_floors, ts, ox, oy,
                         show_roof=True):
    """Render a blueprint in 2.5D at given tile size and offset."""
    floor_px = ts * 3 // 4
    wall_h = num_floors * floor_px

    # Build height map: which tiles are part of the building
    building_tiles = set()
    for by, row in enumerate(bp.tiles):
        for bx, tile in enumerate(row):
            if tile != GRASS:
                building_tiles.add((bx, by))

    # Determine effective roof kind from blueprint kind
    effective_roof = _TILE_ROOF_KIND.get(bp.kind, roof_kind)

    # Pass 1: draw ground tiles
    for by, row in enumerate(bp.tiles):
        for bx, tile in enumerate(row):
            sx = ox + bx * ts
            sy = oy + by * ts
            color = TERRAIN_COLORS.get(tile, (100, 100, 100))
            if tile == GRASS:
                color = (86, 152, 72)
            pygame.draw.rect(screen, color, (sx, sy, ts, ts))
            # Outline
            pygame.draw.rect(screen, (max(0, color[0] - 20), max(0, color[1] - 20),
                                       max(0, color[2] - 20)),
                             (sx, sy, ts, ts), 1)

    # Pass 2: north-to-south painter's for walls + roofs
    for by in range(len(bp.tiles)):
        for bx in range(len(bp.tiles[0])):
            if (bx, by) not in building_tiles:
                continue

            tile = bp.tiles[by][bx]
            sx = ox + bx * ts
            sy = oy + by * ts

            # South face
            south_in = (bx, by + 1) in building_tiles
            if not south_in:
                wall_top = sy + ts
                wall_bot = wall_top + wall_h
                pygame.draw.rect(screen, WALL_S, (sx, wall_top, ts, wall_h))
                # Brick lines
                brick = (max(0, WALL_S[0] - 18), max(0, WALL_S[1] - 18), max(0, WALL_S[2] - 15))
                for py in range(0, wall_h, max(4, ts // 3)):
                    pygame.draw.line(screen, brick, (sx, wall_top + py),
                                     (sx + ts, wall_top + py))
                # Bottom gradient
                if wall_h > 4:
                    grad_h = wall_h // 2
                    grad = pygame.Surface((ts, grad_h), pygame.SRCALPHA)
                    grad.fill((0, 0, 0, 30))
                    screen.blit(grad, (sx, wall_bot - grad_h))

            # East face
            east_in = (bx + 1, by) in building_tiles
            if not east_in:
                east_x = sx + ts
                east_w = max(2, ts // 5)
                wall_top = sy + ts
                ec = (int(WALL_E[0] * 0.85), int(WALL_E[1] * 0.85), int(WALL_E[2] * 0.85))
                pygame.draw.rect(screen, ec, (east_x, wall_top, east_w, wall_h))

            # Roof tile
            if show_roof:
                roof_y = sy - wall_h
                variant = (bx * 7 + by * 13) % 4
                roof_surf = _build_roof_tile(effective_roof, ts, variant)
                screen.blit(roof_surf, (sx, roof_y))

    # Pass 3: pitched roof shading
    if show_roof:
        _draw_pitched_shade(screen, bp, building_tiles, wall_h, ts, ox, oy)


def _draw_pitched_shade(screen, bp, building_tiles, wall_h, ts, ox, oy):
    """Add pitched roof shading (gable effect) over the roof area."""
    # Find bounding box of building tiles
    min_bx = min(bx for bx, _ in building_tiles)
    max_bx = max(bx for bx, _ in building_tiles)
    min_by = min(by for _, by in building_tiles)
    max_by = max(by for _, by in building_tiles)

    bw_px = (max_bx - min_bx + 1) * ts
    bh_px = (max_by - min_by + 1) * ts

    shade_x = ox + min_bx * ts
    shade_y = oy + min_by * ts - wall_h

    shade = pygame.Surface((bw_px, bh_px), pygame.SRCALPHA)
    mid_y = bh_px // 2

    for py in range(bh_px):
        if py < mid_y:
            t = 1.0 - (py / max(1, mid_y))
            alpha = int(t * 70 + 20)
            pygame.draw.line(shade, (0, 0, 0, alpha), (0, py), (bw_px - 1, py))
        else:
            t = (py - mid_y) / max(1, bh_px - mid_y)
            alpha = int((1.0 - t) * 25)
            pygame.draw.line(shade, (255, 255, 220, alpha), (0, py), (bw_px - 1, py))

    # Ridge line
    pygame.draw.line(shade, (0, 0, 0, 80), (0, mid_y), (bw_px - 1, mid_y), 2)
    pygame.draw.line(shade, (255, 255, 200, 30), (0, mid_y + 2), (bw_px - 1, mid_y + 2))
    screen.blit(shade, (shade_x, shade_y))

    # Eave shadow
    eave_y = shade_y + bh_px
    pygame.draw.line(screen, (40, 35, 30), (shade_x, eave_y), (shade_x + bw_px - 1, eave_y))


# ── Main loop ────────────────────────────────────────────────────────────

ROOF_KINDS = ["hamlet", "village", "town", "city", "castle", "temple",
              "tavern", "blacksmith", "market"]


def main():
    bp_idx = 0
    roof_idx = 0
    num_floors = 1
    tile_size = 16
    zoom_levels = [12, 16, 24, 32]
    zoom_idx = 1
    rotation = 0
    show_roof = True

    running = True
    while running:
        clock.tick(30)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT:
                    bp_idx = (bp_idx - 1) % len(ALL_BLUEPRINTS)
                    rotation = 0
                elif event.key == pygame.K_RIGHT:
                    bp_idx = (bp_idx + 1) % len(ALL_BLUEPRINTS)
                    rotation = 0
                elif event.key == pygame.K_UP:
                    roof_idx = (roof_idx - 1) % len(ROOF_KINDS)
                elif event.key == pygame.K_DOWN:
                    roof_idx = (roof_idx + 1) % len(ROOF_KINDS)
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    num_floors = min(3, num_floors + 1)
                elif event.key == pygame.K_MINUS:
                    num_floors = max(1, num_floors - 1)
                elif event.key == pygame.K_r:
                    rotation = (rotation + 1) % 4
                elif event.key == pygame.K_v:
                    show_roof = not show_roof
                elif event.key == pygame.K_z:
                    zoom_idx = (zoom_idx + 1) % len(zoom_levels)
                    tile_size = zoom_levels[zoom_idx]
                elif event.key == pygame.K_s:
                    pygame.image.save(screen, "screenshot_building_25d.png")

        # Get current blueprint
        bp = ALL_BLUEPRINTS[bp_idx]
        for _ in range(rotation):
            bp = bp.rotated()

        # ── Render ──────────────────────────────────────────────────
        screen.fill((60, 80, 50))  # grass-like background

        roof_kind = ROOF_KINDS[roof_idx]

        # Center the building
        bw_px = bp.width * tile_size
        bh_px = bp.height * tile_size
        floor_px = tile_size * 3 // 4
        total_h = bh_px + num_floors * floor_px + floor_px
        ox = (SCREEN_W - bw_px) // 2
        oy = (SCREEN_H - bh_px) // 2 + num_floors * floor_px // 2

        _render_building_25d(screen, bp, roof_kind, num_floors, tile_size, ox, oy,
                             show_roof=show_roof)

        # ── HUD ─────────────────────────────────────────────────────
        orig_bp = ALL_BLUEPRINTS[bp_idx]
        hud_lines = [
            f"{orig_bp.name} ({orig_bp.kind}) — {orig_bp.width}x{orig_bp.height}",
            f"Roof: {roof_kind} {'ON' if show_roof else 'OFF'} | Floors: {num_floors} | Tile: {tile_size}px | Rot: {rotation * 90}°",
            f"NPCs: {orig_bp.npc_count} | Class: {orig_bp.npc_class or 'Commoner'}",
            f"Blueprint {bp_idx + 1}/{len(ALL_BLUEPRINTS)}",
        ]
        # Background for HUD
        pygame.draw.rect(screen, (20, 20, 30), (0, 0, SCREEN_W, 70))
        for i, line in enumerate(hud_lines):
            screen.blit(font_md.render(line, True, (220, 220, 230)), (15, 8 + i * 16))

        # Controls
        ctrl_lines = [
            "LEFT/RIGHT: building  UP/DOWN: roof  +/-: floors",
            "R: rotate  V: toggle roof  Z: zoom  S: screenshot  ESC: quit",
        ]
        pygame.draw.rect(screen, (20, 20, 30), (0, SCREEN_H - 36, SCREEN_W, 36))
        for i, line in enumerate(ctrl_lines):
            screen.blit(font.render(line, True, (150, 150, 170)), (15, SCREEN_H - 32 + i * 14))

        # Floor plan legend (small, bottom-right)
        _draw_floor_plan(screen, orig_bp, SCREEN_W - 20, SCREEN_H - 50)

        pygame.display.flip()

    pygame.quit()


def _draw_floor_plan(screen, bp, right_x, bottom_y):
    """Draw a tiny floor plan in the corner."""
    cell = 4
    pw = bp.width * cell
    ph = bp.height * cell
    ox = right_x - pw
    oy = bottom_y - ph

    pygame.draw.rect(screen, (20, 20, 30), (ox - 4, oy - 14, pw + 8, ph + 18))
    screen.blit(font.render("Plan", True, (120, 120, 140)), (ox, oy - 12))

    for by, row in enumerate(bp.tiles):
        for bx, tile in enumerate(row):
            color = TERRAIN_COLORS.get(tile, (60, 60, 60))
            if tile == GRASS:
                color = (40, 50, 35)
            pygame.draw.rect(screen, color, (ox + bx * cell, oy + by * cell, cell, cell))


if __name__ == "__main__":
    main()
