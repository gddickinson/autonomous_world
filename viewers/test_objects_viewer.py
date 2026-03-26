#!/usr/bin/env python3
"""2D World Objects Viewer — siege engines, vehicles, fortifications.

Shows all world objects at multiple scales with animation states.

Controls:
  LEFT/RIGHT: cycle object category
  UP/DOWN: cycle view scale
  SPACE: toggle firing/moving state
  S: screenshot    Esc: quit
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 1000, 700
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("World Objects Viewer — Siege, Vehicles, Fortifications")
clock = pygame.time.Clock()
font = pygame.font.SysFont("monospace", 13)
font_lg = pygame.font.SysFont("monospace", 18, bold=True)

from game.ui.object_sprites import (
    draw_battering_ram, draw_catapult, draw_trebuchet, draw_siege_tower,
    draw_handcart, draw_cart, draw_wagon, draw_supply_wagon,
    draw_palisade, draw_stone_wall, draw_tower, draw_gate,
)

# Object definitions: (name, draw_func, takes_firing, takes_goods)
CATEGORIES = {
    "Siege Engines": [
        ("Battering Ram", draw_battering_ram, True, False),
        ("Catapult", draw_catapult, True, False),
        ("Trebuchet", draw_trebuchet, True, False),
        ("Siege Tower", draw_siege_tower, False, False),
    ],
    "Vehicles": [
        ("Handcart", draw_handcart, False, True),
        ("Cart", draw_cart, False, True),
        ("Wagon", draw_wagon, False, True),
        ("Supply Wagon", draw_supply_wagon, False, True),
    ],
    "Fortifications": [
        ("Palisade", draw_palisade, False, False),
        ("Stone Wall", draw_stone_wall, False, False),
        ("Tower", draw_tower, False, False),
        ("Gate (Closed)", lambda s, x, y, cs: draw_gate(s, x, y, cs, False), False, False),
        ("Gate (Open)", lambda s, x, y, cs: draw_gate(s, x, y, cs, True), False, False),
    ],
}

CAT_NAMES = list(CATEGORIES.keys())
VIEW_SCALES = [("Small (4px)", 4), ("Medium (8px)", 8), ("Large (16px)", 16)]
GOODS_COLORS = [(200, 180, 80), (160, 140, 120), (140, 100, 50), (180, 180, 200)]
GOODS_NAMES = ["Food", "Ore", "Wood", "Weapons"]


def main():
    cat_idx = 0
    view_idx = 1
    active = False  # firing/moving state

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
                    cat_idx = (cat_idx - 1) % len(CAT_NAMES)
                elif event.key == pygame.K_RIGHT:
                    cat_idx = (cat_idx + 1) % len(CAT_NAMES)
                elif event.key == pygame.K_UP:
                    view_idx = (view_idx - 1) % len(VIEW_SCALES)
                elif event.key == pygame.K_DOWN:
                    view_idx = (view_idx + 1) % len(VIEW_SCALES)
                elif event.key == pygame.K_SPACE:
                    active = not active
                elif event.key == pygame.K_s:
                    pygame.image.save(screen, "screenshot_objects_viewer.png")

        screen.fill((30, 30, 40))

        cat_name = CAT_NAMES[cat_idx]
        objects = CATEGORIES[cat_name]
        view_name, scale = VIEW_SCALES[view_idx]

        # Title
        title = font_lg.render(f"{cat_name} | {view_name}", True, (255, 255, 255))
        screen.blit(title, (20, 15))
        state_txt = "FIRING/MOVING" if active else "IDLE"
        screen.blit(font.render(f"State: {state_txt} (SPACE to toggle)", True, (160, 160, 180)),
                    (20, 40))

        # Main display: all objects in category at current scale
        cols = min(len(objects), 3)
        spacing_x = SCREEN_W // (cols + 1)
        for i, (name, draw_fn, takes_fire, takes_goods) in enumerate(objects):
            cx = spacing_x * (i % cols + 1)
            cy = 150 + (i // cols) * 200

            # Draw
            kwargs = {}
            if takes_fire:
                draw_fn(screen, cx, cy, scale, firing=active)
            elif takes_goods:
                gc = GOODS_COLORS[i % len(GOODS_COLORS)]
                draw_fn(screen, cx, cy, scale, goods_color=gc)
            else:
                draw_fn(screen, cx, cy, scale)

            # Label
            label = font.render(name, True, (200, 200, 220))
            screen.blit(label, (cx - label.get_width() // 2, cy + scale * 6))

        # Bottom panel: all scales comparison for first object
        panel_y = SCREEN_H - 150
        pygame.draw.rect(screen, (25, 25, 35), (0, panel_y - 10, SCREEN_W, 160))
        pygame.draw.line(screen, (50, 50, 60), (0, panel_y - 10), (SCREEN_W, panel_y - 10))
        screen.blit(font.render("Scale comparison (first object):", True, (160, 160, 180)),
                    (20, panel_y - 5))

        if objects:
            name, draw_fn, takes_fire, takes_goods = objects[0]
            for vi, (vn, vs) in enumerate(VIEW_SCALES):
                vx = 120 + vi * 300
                vy = panel_y + 60
                if takes_fire:
                    draw_fn(screen, vx, vy, vs, firing=active)
                elif takes_goods:
                    draw_fn(screen, vx, vy, vs, goods_color=GOODS_COLORS[0])
                else:
                    draw_fn(screen, vx, vy, vs)
                screen.blit(font.render(vn, True, (140, 140, 160)),
                            (vx - 30, vy + vs * 6))

        # Controls
        controls = ["LEFT/RIGHT: category", "UP/DOWN: scale",
                    "SPACE: fire/move", "S: screenshot"]
        for i, c in enumerate(controls):
            screen.blit(font.render(c, True, (110, 110, 130)),
                        (SCREEN_W - 200, 15 + i * 15))

        # Category tabs
        tab_y = SCREEN_H - 20
        tab_x = 20
        for ci, cn in enumerate(CAT_NAMES):
            c = (220, 220, 240) if ci == cat_idx else (100, 100, 120)
            screen.blit(font.render(f"[{cn}]", True, c), (tab_x, tab_y))
            tab_x += len(cn) * 8 + 30

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
