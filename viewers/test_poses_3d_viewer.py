#!/usr/bin/env python3
"""3D Pose Viewer — all action poses in OpenGL.

Controls:
  LEFT/RIGHT: cycle pose
  TAB: cycle NPC type
  SHIFT+Arrows: camera    +/-: zoom
  SPACE: toggle animation phase
  S: screenshot    Esc: quit
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from OpenGL.GL import *

from viewers.gl_viewer_base import (
    init_viewer, setup_camera, draw_hud, draw_ground_grid, handle_camera_keys,
)
from viewers.poses_3d import draw_pose_3d

NPC_TYPES = [
    ("Human Fighter", "Guard",   "Fighter",  "human",    (180, 60, 60)),
    ("Elf Wizard",    "Sage",    "Wizard",   "elf",      (60, 60, 180)),
    ("Dwarf Paladin", "Knight",  "Paladin",  "dwarf",    (180, 160, 60)),
    ("Human Farmer",  "Farmer",  "Commoner", "human",    (140, 120, 80)),
    ("Orc Soldier",   "Soldier", "Fighter",  "orc",      (80, 110, 70)),
]

POSES = [
    "standing", "walking", "lying", "sitting", "kneeling",
    "working", "combat", "fishing", "alert", "fleeing", "dead",
]

POSE_LABELS = {
    "standing": "Standing (idle)", "walking": "Walking",
    "lying": "Lying (sleeping)", "sitting": "Sitting (talking)",
    "kneeling": "Kneeling (praying)", "working": "Working (chopping)",
    "combat": "Combat (fighting)", "fishing": "Fishing",
    "alert": "Guard (alert)", "fleeing": "Fleeing", "dead": "Dead",
}


def main():
    screen, clock, font, W, H = init_viewer("3D Pose Viewer")
    pose_idx = 0
    npc_idx = 0
    az, el, dist = 30.0, -25.0, 4.0
    animating = True
    phase = 0.0

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        if animating:
            phase += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    pose_idx = (pose_idx - 1) % len(POSES)
                elif event.key == pygame.K_RIGHT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    pose_idx = (pose_idx + 1) % len(POSES)
                elif event.key == pygame.K_TAB:
                    npc_idx = (npc_idx + 1) % len(NPC_TYPES)
                elif event.key == pygame.K_SPACE:
                    animating = not animating
                elif event.key == pygame.K_s:
                    d = glReadPixels(0, 0, W, H, GL_RGB, GL_UNSIGNED_BYTE)
                    pygame.image.save(pygame.image.fromstring(bytes(d), (W, H), "RGB", True),
                                      "screenshot_poses_3d.png")
                else:
                    az, el, dist = handle_camera_keys(event, az, el, dist)

        setup_camera(W, H, az, el, dist, look_y=0.35)
        draw_ground_grid(3)

        pose = POSES[pose_idx]
        name, prof, cls, race, color = NPC_TYPES[npc_idx]

        # Main pose
        draw_pose_3d(pose, name, prof, cls, race, color, phase)

        # Back row: all poses for current NPC
        glPushMatrix()
        glTranslatef(-2.5, 0, 2.5)
        for pi, p in enumerate(POSES):
            glPushMatrix()
            glTranslatef(pi * 0.55, 0, 0)
            glScalef(0.35, 0.35, 0.35)
            draw_pose_3d(p, name, prof, cls, race, color, phase)
            glPopMatrix()
        glPopMatrix()

        pose_label = POSE_LABELS.get(pose, pose)
        draw_hud([
            f"{name} — {pose_label}",
            f"[{pose_idx + 1}/{len(POSES)}] LEFT/RIGHT: pose  TAB: NPC type",
            f"SPACE: {'pause' if animating else 'play'} anim  "
            f"SHIFT+Arrows: camera  +/-: zoom",
        ], font, W, H)

        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
