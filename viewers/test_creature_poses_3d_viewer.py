#!/usr/bin/env python3
"""3D Creature Pose Viewer — sleeping, resting, combat poses in OpenGL.

Controls:
  LEFT/RIGHT: cycle creature
  UP/DOWN: cycle pose
  SHIFT+Arrows: camera    +/-: zoom
  SPACE: toggle animation
  S: screenshot    Esc: quit
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from OpenGL.GL import *

from viewers.gl_viewer_base import (
    init_viewer, setup_camera, draw_hud, draw_ground_grid, handle_camera_keys,
)
from viewers.creature_3d_templates import (
    draw_quadruped_3d, draw_ungulate_3d, draw_bear_3d,
    draw_bird_3d, draw_serpent_3d,
)
from viewers.creature_3d_templates_extra import draw_small_3d
from viewers.creature_poses_3d import draw_creature_pose_3d
from game.ui.creatures.configs import CREATURE_CONFIGS

CREATURES = [
    ("wolf",       (120, 110, 100), 0.5),
    ("fox",        (200, 120, 50),  0.25),
    ("cat",        (170, 140, 100), 0.1),
    ("bear",       (100, 70, 40),   2.0),
    ("horse",      (140, 100, 60),  0.5),
    ("deer",       (160, 130, 80),  0.25),
    ("cow",        (140, 100, 70),  0.25),
    ("hawk",       (120, 100, 80),  0.25),
    ("owl",        (140, 130, 110), 0.25),
    ("snake",      (80, 120, 60),   0.25),
    ("viper",      (60, 80, 40),    0.5),
    ("boar",       (110, 80, 60),   0.5),
]

POSES = ["standing", "walking", "sleeping", "resting", "combat"]

# Map template → default draw function for standing/walking
_DEFAULT_DRAW = {
    "quadruped": draw_quadruped_3d,
    "ungulate": draw_ungulate_3d,
    "bear": draw_bear_3d,
    "bird": draw_bird_3d,
    "serpent": draw_serpent_3d,
    "small": draw_small_3d,
}


def _draw_creature(kind, color, cr, pose, phase):
    """Draw a creature in the specified pose."""
    cfg = CREATURE_CONFIGS.get(kind, {})
    template = cfg.get("t", "quadruped")
    sc = 1.0 + min(1.5, cr * 0.3)
    ws = math.sin(phase) if pose == "walking" else 0
    bob = abs(math.cos(phase)) * 0.02 * sc if pose == "walking" else 0

    # Try pose-specific drawing first
    if pose not in ("standing", "walking"):
        if draw_creature_pose_3d(pose, template, sc, color, cfg):
            return

    # Fall back to default template
    func = _DEFAULT_DRAW.get(template)
    if func:
        func(sc, color, ws, bob, cfg)


def main():
    screen, clock, font, W, H = init_viewer("3D Creature Pose Viewer")
    creature_idx = 0
    pose_idx = 0
    az, el, dist = 30.0, -25.0, 4.0
    animating = True
    phase = 0.0

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        if animating:
            phase += dt * 4

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    creature_idx = (creature_idx - 1) % len(CREATURES)
                elif event.key == pygame.K_RIGHT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    creature_idx = (creature_idx + 1) % len(CREATURES)
                elif event.key == pygame.K_UP and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    pose_idx = (pose_idx - 1) % len(POSES)
                elif event.key == pygame.K_DOWN and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    pose_idx = (pose_idx + 1) % len(POSES)
                elif event.key == pygame.K_SPACE:
                    animating = not animating
                elif event.key == pygame.K_s:
                    d = glReadPixels(0, 0, W, H, GL_RGB, GL_UNSIGNED_BYTE)
                    pygame.image.save(pygame.image.fromstring(bytes(d), (W, H), "RGB", True),
                                      "screenshot_creature_poses_3d.png")
                else:
                    az, el, dist = handle_camera_keys(event, az, el, dist)

        setup_camera(W, H, az, el, dist, look_y=0.2)
        draw_ground_grid(3)

        kind, color, cr = CREATURES[creature_idx]
        pose = POSES[pose_idx]

        # Main creature
        _draw_creature(kind, color, cr, pose, phase)

        # Back row: all poses for current creature
        glPushMatrix()
        glTranslatef(-1.5, 0, 2.5)
        for pi, p in enumerate(POSES):
            glPushMatrix()
            glTranslatef(pi * 0.8, 0, 0)
            glScalef(0.4, 0.4, 0.4)
            _draw_creature(kind, color, cr, p, phase)
            glPopMatrix()
        glPopMatrix()

        # Right column: all creatures in current pose
        glPushMatrix()
        glTranslatef(2.5, 0, -1.5)
        for ci, (ck, cc, ccr) in enumerate(CREATURES[:6]):
            glPushMatrix()
            glTranslatef(0, 0, ci * 0.7)
            glScalef(0.35, 0.35, 0.35)
            _draw_creature(ck, cc, ccr, pose, phase)
            glPopMatrix()
        glPopMatrix()

        cfg = CREATURE_CONFIGS.get(kind, {})
        draw_hud([
            f"{kind} — {pose} (template: {cfg.get('t', '?')})",
            f"[{creature_idx + 1}/{len(CREATURES)}] LEFT/RIGHT: creature  UP/DOWN: pose",
            f"SPACE: {'pause' if animating else 'play'}  SHIFT+Arrows: camera  +/-: zoom",
        ], font, W, H)

        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
