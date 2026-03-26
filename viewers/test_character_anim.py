#!/usr/bin/env python3
"""Character Animation Viewer — NPC body parts, walk cycles, equipment in all views.

Displays NPCs at multiple scales matching the 3 game view modes:
Strategy (16px), Adventure (32px), and close-up detail view.

Controls:
  LEFT/RIGHT: cycle NPC preset
  UP/DOWN: cycle view mode (strategy / adventure / detail)
  SPACE: toggle walk/idle
  F: flee mode
  D: die
  R: reset (revive + idle)
  1-4: facing (left, right, up, down)
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
pygame.display.set_caption("NPC Character Viewer — All View Modes")
clock = pygame.time.Clock()
font = pygame.font.SysFont("monospace", 13)
font_lg = pygame.font.SysFont("monospace", 18, bold=True)

from game.ui.character_anim import (
    get_anim, update_anim, draw_npc_body, AnimState
)

# ── Mock NPC ─────────────────────────────────────────────────────────────

class MockNPC:
    def __init__(self, name, profession, char_class, race, color):
        self.x = self.y = 0.0
        self.name = name
        self.profession = profession
        self.char_class = char_class
        self.race = race
        self.color = color
        self.alive = True
        self.state = "idle"
        self.current_action = ""
        self.facing = (0, 1)
        self.consciousness = 0
        self._anim = None


# ── Presets: all class/race combos ───────────────────────────────────────

PRESETS = [
    # D&D classes
    ("Human Fighter",     "Guard",      "Fighter",   "human",      (180, 60, 60)),
    ("Elf Wizard",        "Sage",       "Wizard",    "elf",        (60, 60, 180)),
    ("Dwarf Paladin",     "Knight",     "Paladin",   "dwarf",      (180, 160, 60)),
    ("Halfling Rogue",    "Thief",      "Rogue",     "halfling",   (100, 100, 100)),
    ("Half-Orc Barbarian","Mercenary",  "Barbarian", "half-orc",   (140, 80, 60)),
    ("Gnome Bard",        "Performer",  "Bard",      "gnome",      (180, 120, 180)),
    ("Tiefling Warlock",  "Mystic",     "Warlock",   "tiefling",   (140, 60, 180)),
    ("Dragonborn Cleric", "Priest",     "Cleric",    "dragonborn", (220, 200, 100)),
    ("Human Ranger",      "Ranger",     "Ranger",    "human",      (80, 140, 80)),
    ("Elf Druid",         "Herbalist",  "Druid",     "elf",        (60, 160, 80)),
    ("Orc Soldier",       "Soldier",    "Fighter",   "orc",        (80, 110, 70)),
    ("Goliath Knight",    "Knight",     "Paladin",   "goliath",    (140, 130, 120)),
    # Civilians
    ("Human Farmer",      "Farmer",     "Commoner",  "human",      (140, 120, 80)),
    ("Human Blacksmith",  "Blacksmith", "Commoner",  "human",      (120, 100, 80)),
    ("Elf Merchant",      "Merchant",   "Commoner",  "elf",        (100, 140, 100)),
    ("Dwarf Miner",       "Miner",      "Commoner",  "dwarf",      (130, 110, 90)),
    ("Human Baker",       "Baker",      "Commoner",  "human",      (180, 160, 120)),
    ("Halfling Innkeeper", "Innkeeper", "Commoner",  "halfling",   (160, 140, 100)),
]

VIEW_MODES = [
    ("Strategy (16px)",  4),   # TILE_SIZE//4 = 4
    ("Adventure (32px)", 8),   # 32//4 = 8
    ("Detail (64px)",   16),   # close-up
]


def main():
    preset_idx = 0
    view_idx = 0
    walking = False
    walk_time = 0.0

    def make_npc():
        name, prof, cls, race, color = PRESETS[preset_idx]
        return MockNPC(name, prof, cls, race, color)

    npc = make_npc()
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
                    preset_idx = (preset_idx - 1) % len(PRESETS)
                    npc = make_npc()
                    if walking:
                        npc.state = "walking"
                elif event.key == pygame.K_RIGHT:
                    preset_idx = (preset_idx + 1) % len(PRESETS)
                    npc = make_npc()
                    if walking:
                        npc.state = "walking"
                elif event.key == pygame.K_UP:
                    view_idx = (view_idx - 1) % len(VIEW_MODES)
                elif event.key == pygame.K_DOWN:
                    view_idx = (view_idx + 1) % len(VIEW_MODES)
                elif event.key == pygame.K_SPACE:
                    walking = not walking
                    npc.state = "walking" if walking else "idle"
                elif event.key == pygame.K_f:
                    if npc.state == "fleeing":
                        npc.state = "idle"
                        walking = False
                    else:
                        npc.state = "fleeing"
                        walking = True
                elif event.key == pygame.K_d:
                    npc.alive = False
                elif event.key == pygame.K_r:
                    npc.alive = True
                    npc.state = "idle"
                    npc._anim = None
                    walking = False
                elif event.key == pygame.K_1:
                    npc.facing = (-1, 0)
                elif event.key == pygame.K_2:
                    npc.facing = (1, 0)
                elif event.key == pygame.K_3:
                    npc.facing = (0, -1)
                elif event.key == pygame.K_4:
                    npc.facing = (0, 1)
                elif event.key == pygame.K_s:
                    pygame.image.save(screen, "screenshot_npc_viewer.png")

        # Simulate walk
        if walking:
            walk_time += dt
            npc.x = math.sin(walk_time * 2.0) * 0.5
            npc.y = math.cos(walk_time * 2.0) * 0.5

        update_anim(npc, dt)

        # ── Render ──────────────────────────────────────────────────
        screen.fill((30, 30, 40))
        _draw_grid(screen)

        view_name, scale = VIEW_MODES[view_idx]

        # Main character (center)
        cx, cy = SCREEN_W // 2, SCREEN_H // 2 - 30
        draw_npc_body(screen, npc, cx, cy, scale)

        # Side-by-side: all 3 view modes
        panel_y = SCREEN_H - 180
        _draw_panel_bg(screen, 0, panel_y - 20, SCREEN_W, 200)
        label = font.render("All view modes:", True, (180, 180, 200))
        screen.blit(label, (20, panel_y - 15))

        for vi, (vname, vscale) in enumerate(VIEW_MODES):
            col_x = 100 + vi * 280
            # Draw this NPC at each scale
            preview = make_npc()
            preview.state = npc.state
            preview.facing = npc.facing
            preview.alive = npc.alive
            if walking:
                preview.x = math.sin(walk_time * 2.0 + vi) * 0.3
            update_anim(preview, dt)
            draw_npc_body(screen, preview, col_x, panel_y + 50, vscale)
            lbl = font.render(vname, True, (160, 160, 180))
            screen.blit(lbl, (col_x - lbl.get_width() // 2, panel_y + 90))

        # ── HUD ─────────────────────────────────────────────────────
        p = PRESETS[preset_idx]
        title = font_lg.render(f"{p[0]} ({p[3]} {p[2]})", True, (255, 255, 255))
        screen.blit(title, (20, 20))

        anim = get_anim(npc)
        info = [
            f"View: {view_name} (scale={scale}) | State: {npc.state}",
            f"Facing: {npc.facing} | Moving: {anim.moving}",
            f"Preset {preset_idx + 1}/{len(PRESETS)}",
        ]
        for i, line in enumerate(info):
            screen.blit(font.render(line, True, (160, 160, 180)), (20, 50 + i * 16))

        controls = [
            "LEFT/RIGHT: preset", "UP/DOWN: view mode", "SPACE: walk",
            "F: flee", "D: die", "R: reset", "1-4: facing", "S: screenshot",
        ]
        for i, c in enumerate(controls):
            screen.blit(font.render(c, True, (110, 110, 130)),
                        (SCREEN_W - 200, 20 + i * 16))

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
