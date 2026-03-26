#!/usr/bin/env python3
"""Creature & Animal Viewer — all 65+ creature types in all view modes.

Displays creatures at Strategy/Adventure/Detail scales with animation.

Controls:
  LEFT/RIGHT: cycle creature
  UP/DOWN: cycle view mode (strategy / adventure / detail)
  TAB: toggle hostile / passive / all filter
  SPACE: toggle walk/idle
  D: die
  H: toggle half-HP (show damaged HP bar)
  R: reset
  S: screenshot
  Esc: quit
"""

import os
import sys
import math
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 1000, 700
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Creature & Animal Viewer — All View Modes")
clock = pygame.time.Clock()
font = pygame.font.SysFont("monospace", 13)
font_lg = pygame.font.SysFont("monospace", 18, bold=True)

from game.ui.character_anim import (
    get_anim, update_anim, draw_creature_body
)
from game.data.dnd import MONSTERS


# ── Mock creature ────────────────────────────────────────────────────────

class MockCreature:
    def __init__(self, kind, color, cr, hp):
        self.x = self.y = 0.0
        self.kind = kind
        self.color = color
        self.cr = cr
        self.hp = hp
        self.max_hp = hp
        self.alive = True
        self._anim = None


# ── Build creature list from game data ───────────────────────────────────

def _build_creature_list():
    creatures = []
    for kind, data in sorted(MONSTERS.items(), key=lambda kv: kv[1].get("cr", 0)):
        color = data.get("color", (150, 150, 150))
        cr = data.get("cr", 0.25)
        hp = data.get("hp", 10)
        passive = data.get("passive", False)
        creatures.append((kind, color, cr, hp, passive))
    return creatures

ALL_CREATURES = _build_creature_list()

VIEW_MODES = [
    ("Strategy (16px)",  4),
    ("Adventure (32px)", 8),
    ("Detail (64px)",   16),
]

FILTERS = ["all", "hostile", "passive"]


def main():
    creature_idx = 0
    view_idx = 0
    filter_idx = 0
    walking = False
    walk_time = 0.0
    half_hp = False

    def filtered():
        f = FILTERS[filter_idx]
        if f == "all":
            return ALL_CREATURES
        elif f == "hostile":
            return [c for c in ALL_CREATURES if not c[4]]
        else:
            return [c for c in ALL_CREATURES if c[4]]

    def make_creature():
        lst = filtered()
        if not lst:
            return MockCreature("none", (100, 100, 100), 0, 10)
        kind, color, cr, hp, _ = lst[creature_idx % len(lst)]
        c = MockCreature(kind, color, cr, hp)
        if half_hp:
            c.hp = c.max_hp // 2
        return c

    creature = make_creature()
    running = True

    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT:
                    lst = filtered()
                    creature_idx = (creature_idx - 1) % max(1, len(lst))
                    creature = make_creature()
                elif event.key == pygame.K_RIGHT:
                    lst = filtered()
                    creature_idx = (creature_idx + 1) % max(1, len(lst))
                    creature = make_creature()
                elif event.key == pygame.K_UP:
                    view_idx = (view_idx - 1) % len(VIEW_MODES)
                elif event.key == pygame.K_DOWN:
                    view_idx = (view_idx + 1) % len(VIEW_MODES)
                elif event.key == pygame.K_TAB:
                    filter_idx = (filter_idx + 1) % len(FILTERS)
                    creature_idx = 0
                    creature = make_creature()
                elif event.key == pygame.K_SPACE:
                    walking = not walking
                elif event.key == pygame.K_d:
                    creature.alive = False
                elif event.key == pygame.K_h:
                    half_hp = not half_hp
                    creature.hp = creature.max_hp // 2 if half_hp else creature.max_hp
                elif event.key == pygame.K_r:
                    creature.alive = True
                    creature._anim = None
                    creature.hp = creature.max_hp if not half_hp else creature.max_hp // 2
                    walking = False
                elif event.key == pygame.K_s:
                    pygame.image.save(screen, "screenshot_creature_viewer.png")

        if walking:
            walk_time += dt
            creature.x = math.sin(walk_time * 2.0) * 0.5
            creature.y = math.cos(walk_time * 2.0) * 0.5

        update_anim(creature, dt)

        # ── Render ──────────────────────────────────────────────────
        screen.fill((30, 30, 40))
        _draw_grid(screen)

        view_name, scale = VIEW_MODES[view_idx]
        lst = filtered()

        # Main creature (center)
        cx, cy = SCREEN_W // 2, SCREEN_H // 2 - 40
        draw_creature_body(screen, creature, cx, cy, scale)

        # Info about this creature
        if lst:
            kind, color, cr, hp, passive = lst[creature_idx % len(lst)]
            tag = "PASSIVE" if passive else "HOSTILE"
            title = font_lg.render(f"{kind} (CR {cr}) [{tag}]", True, (255, 255, 255))
        else:
            title = font_lg.render("No creatures in filter", True, (255, 255, 255))
        screen.blit(title, (20, 20))

        info = [
            f"View: {view_name} | Filter: {FILTERS[filter_idx]} ({len(lst)} creatures)",
            f"HP: {creature.hp}/{creature.max_hp} | Alive: {creature.alive}",
            f"Creature {creature_idx + 1}/{max(1, len(lst))}",
        ]
        for i, line in enumerate(info):
            screen.blit(font.render(line, True, (160, 160, 180)), (20, 48 + i * 16))

        # Side-by-side all view modes
        panel_y = SCREEN_H - 160
        _draw_panel_bg(screen, 0, panel_y - 20, SCREEN_W, 180)
        for vi, (vname, vscale) in enumerate(VIEW_MODES):
            col_x = 100 + vi * 280
            preview = make_creature()
            if walking:
                preview.x = math.sin(walk_time * 2.0 + vi) * 0.3
            update_anim(preview, dt)
            draw_creature_body(screen, preview, col_x, panel_y + 40, vscale)
            screen.blit(font.render(vname, True, (160, 160, 180)),
                        (col_x - len(vname) * 4, panel_y + 80))

        # Lineup strip: nearby creatures
        strip_y = panel_y - 60
        _draw_panel_bg(screen, 0, strip_y - 5, SCREEN_W, 45)
        strip_scale = 4
        spacing = 35
        start = max(0, creature_idx - 12)
        for i in range(min(25, len(lst))):
            idx = (start + i) % len(lst)
            kind, color, cr, hp, _ = lst[idx]
            c = MockCreature(kind, color, cr, hp)
            c.x = math.sin(time.time() * 2 + idx) * 0.2
            update_anim(c, dt)
            sx = 30 + i * spacing
            if sx > SCREEN_W - 20:
                break
            draw_creature_body(screen, c, sx, strip_y + 18, strip_scale)
            if idx == creature_idx % len(lst):
                pygame.draw.circle(screen, (255, 200, 80), (sx, strip_y + 18), 14, 1)

        # Controls
        controls = [
            "LEFT/RIGHT: creature", "UP/DOWN: view mode", "TAB: filter",
            "SPACE: walk", "D: die", "H: half HP", "R: reset", "S: screenshot",
        ]
        for i, c in enumerate(controls):
            screen.blit(font.render(c, True, (110, 110, 130)),
                        (SCREEN_W - 210, 20 + i * 16))

        pygame.display.flip()

    pygame.quit()


def _draw_grid(screen):
    for x in range(0, SCREEN_W, 20):
        pygame.draw.line(screen, (40, 40, 50), (x, 0), (x, SCREEN_H))
    for y in range(0, SCREEN_H, 20):
        pygame.draw.line(screen, (40, 40, 50), (0, y), (SCREEN_W, y))


def _draw_panel_bg(screen, x, y, w, h):
    pygame.draw.rect(screen, (25, 25, 35), (x, y, w, h))
    pygame.draw.line(screen, (50, 50, 60), (x, y), (x + w, y))


if __name__ == "__main__":
    main()
