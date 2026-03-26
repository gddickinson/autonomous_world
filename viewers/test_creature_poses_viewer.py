#!/usr/bin/env python3
"""Creature Pose Viewer — 2D and 3D creature poses side by side.

Shows quadrupeds, birds, serpents in sleeping, resting, combat poses.

Controls:
  LEFT/RIGHT: cycle creature
  UP/DOWN: cycle pose
  TAB: toggle 2D / 3D view
  SHIFT+Arrows: camera (3D)    +/-: zoom (3D)
  SPACE: toggle walk animation
  S: screenshot    Esc: quit
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 1100, 700
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Creature Pose Viewer — All Poses")
clock = pygame.time.Clock()
font = pygame.font.SysFont("monospace", 12)
font_lg = pygame.font.SysFont("monospace", 18, bold=True)

from game.ui.character_anim import update_anim, get_anim
from game.ui.creatures.dispatch import draw_creature_body
from game.ui.creatures.configs import CREATURE_CONFIGS

# Creature presets (kind, color, cr)
CREATURES = [
    ("wolf",       (120, 110, 100), 0.5),
    ("cat",        (170, 140, 100), 0.1),
    ("horse",      (140, 100, 60),  0.5),
    ("bear",       (100, 70, 40),   2.0),
    ("deer",       (160, 130, 80),  0.25),
    ("hawk",       (120, 100, 80),  0.25),
    ("owl",        (140, 130, 110), 0.25),
    ("snake",      (80, 120, 60),   0.25),
    ("goblin",     (100, 130, 60),  0.5),
    ("orc",        (80, 110, 70),   1.0),
    ("skeleton",   (200, 200, 190), 0.5),
    ("spider",     (60, 50, 50),    1.0),
    ("young_dragon",(180, 50, 50),  8.0),
]

POSES = ["standing", "walking", "sleeping", "resting", "combat", "dead"]


class MockCreature:
    def __init__(self, kind, color, cr, state="idle", action=""):
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.kind = kind
        self.color = color
        self.cr = cr
        self.hp = 50
        self.max_hp = 50
        self.alive = True
        self.state = state
        self.current_action = action
        self._anim = None


def _make_creature(kind, color, cr, pose):
    c = MockCreature(kind, color, cr)
    if pose == "sleeping":
        c.state = "sleeping"
        c.current_action = "sleeping"
    elif pose == "resting":
        c.state = "idle"
    elif pose == "combat":
        c.state = "attacking"
        c.current_action = "attacking"
    elif pose == "dead":
        c.alive = False
    elif pose == "walking":
        c.state = "wandering"
    return c


def main():
    creature_idx = 0
    pose_idx = 0
    walking = False
    walk_time = 0.0

    # Persistent creatures for death anim
    persistent = {}

    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        if walking:
            walk_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT:
                    creature_idx = (creature_idx - 1) % len(CREATURES)
                    persistent.clear()
                elif event.key == pygame.K_RIGHT:
                    creature_idx = (creature_idx + 1) % len(CREATURES)
                    persistent.clear()
                elif event.key == pygame.K_UP:
                    pose_idx = (pose_idx - 1) % len(POSES)
                elif event.key == pygame.K_DOWN:
                    pose_idx = (pose_idx + 1) % len(POSES)
                elif event.key == pygame.K_SPACE:
                    walking = not walking
                elif event.key == pygame.K_s:
                    pygame.image.save(screen, "screenshot_creature_poses.png")

        screen.fill((30, 30, 40))

        kind, color, cr = CREATURES[creature_idx]
        pose = POSES[pose_idx]
        cfg = CREATURE_CONFIGS.get(kind, {})
        template = cfg.get("t", "quadruped")
        scale = 8

        # Title
        title = font_lg.render(f"{kind} — {pose} (template: {template})",
                                True, (255, 255, 255))
        screen.blit(title, (20, 15))

        # Main display
        cx, cy = SCREEN_W // 2, SCREEN_H // 3
        key = (creature_idx, pose_idx, "main")
        if key not in persistent:
            persistent[key] = _make_creature(kind, color, cr, pose)
        c = persistent[key]
        if walking and pose == "walking":
            c.x = math.sin(walk_time * 2) * 0.3
            c.y = math.cos(walk_time * 2) * 0.3
        update_anim(c, dt)
        draw_creature_body(screen, c, cx, cy, scale)

        # All poses strip
        panel_y = SCREEN_H // 2 + 30
        pygame.draw.rect(screen, (25, 25, 35), (0, panel_y - 10, SCREEN_W, SCREEN_H - panel_y + 10))
        pygame.draw.line(screen, (50, 50, 60), (0, panel_y - 10), (SCREEN_W, panel_y - 10))
        screen.blit(font.render("All poses:", True, (180, 180, 200)), (10, panel_y - 5))

        spacing = SCREEN_W // (len(POSES) + 1)
        for pi, p in enumerate(POSES):
            px = spacing * (pi + 1)
            py_s = panel_y + 60

            key_s = (creature_idx, pi, "strip")
            if key_s not in persistent:
                persistent[key_s] = _make_creature(kind, color, cr, p)
            cs = persistent[key_s]
            if walking and p == "walking":
                cs.x = math.sin(walk_time * 2 + pi) * 0.2
            update_anim(cs, dt)
            draw_creature_body(screen, cs, px, py_s, 6)

            lbl_c = (255, 220, 100) if pi == pose_idx else (120, 120, 140)
            screen.blit(font.render(p, True, lbl_c), (px - len(p) * 3, py_s + 30))

        # All creatures in current pose
        row_y = panel_y + 130
        screen.blit(font.render(f"All creatures in '{pose}':", True, (180, 180, 200)),
                    (10, row_y - 5))
        cr_spacing = SCREEN_W // (len(CREATURES) + 1)
        for ci, (ck, cc, ccr) in enumerate(CREATURES):
            crx = cr_spacing * (ci + 1)
            cry = row_y + 50

            key_c = (ci, pose_idx, "row")
            if key_c not in persistent:
                persistent[key_c] = _make_creature(ck, cc, ccr, pose)
            cr_obj = persistent[key_c]
            if walking and pose == "walking":
                cr_obj.x = math.sin(walk_time * 2 + ci) * 0.15
            update_anim(cr_obj, dt)
            draw_creature_body(screen, cr_obj, crx, cry, 5)

            lbl_c = (255, 220, 100) if ci == creature_idx else (100, 100, 120)
            screen.blit(font.render(ck[:6], True, lbl_c), (crx - 15, cry + 25))

        # Controls
        controls = ["LEFT/RIGHT: creature", "UP/DOWN: pose", "SPACE: walk", "S: screenshot"]
        for i, ctrl in enumerate(controls):
            screen.blit(font.render(ctrl, True, (110, 110, 130)),
                        (SCREEN_W - 190, 15 + i * 14))

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
