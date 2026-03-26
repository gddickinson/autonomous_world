#!/usr/bin/env python3
"""3D Player Character Viewer — mortal/ghost/god modes as 3D geometry.

Shows the player character in all 3 modes with attack animation
and proper visual effects (god aura, ghost transparency).

Controls:
  LEFT/RIGHT: cycle player mode (mortal / ghost / god)
  Arrows (SHIFT): rotate/tilt camera    +/-: zoom
  SPACE: toggle attack animation
  S: screenshot    Esc: quit
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from OpenGL.GL import *

from viewers.gl_viewer_base import (
    init_viewer, setup_camera, draw_hud, draw_ground_grid,
    draw_box, draw_sphere_approx, handle_camera_keys,
)

MODES = ["mortal", "ghost", "god"]


def _draw_player_mortal(attack_phase):
    """Blue body, skin head, weapon when attacking."""
    body = (60, 100, 180)
    skin = (220, 190, 160)
    glBegin(GL_QUADS)
    # Legs
    draw_box(-0.08, 0, -0.05, 0.07, 0.4, 0.1, (50, 80, 150))
    draw_box(0.02, 0, -0.05, 0.07, 0.4, 0.1, (50, 80, 150))
    # Torso
    draw_box(-0.15, 0.42, -0.08, 0.3, 0.4, 0.16, body)
    # Arms
    draw_box(-0.22, 0.48, -0.04, 0.07, 0.32, 0.08, skin)
    draw_box(0.15, 0.48, -0.04, 0.07, 0.32, 0.08, skin)
    # Weapon (when attacking)
    if attack_phase > 0:
        swing = math.sin(attack_phase * math.pi) * 0.4
        draw_box(0.22, 0.5 + swing * 0.3, -0.02 - swing,
                 0.03, 0.45, 0.03, (200, 200, 210))
    glEnd()
    # Head
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, 0.92, 0, 0.12, skin, 8)
    glEnd()
    # Selection circle
    glBegin(GL_LINE_LOOP)
    glColor3f(0.4, 0.8, 1.0)
    for i in range(24):
        a = 2 * math.pi * i / 24
        glVertex3f(math.cos(a) * 0.25, 0.005, math.sin(a) * 0.25)
    glEnd()


def _draw_player_ghost():
    """Translucent blue-white floaty form."""
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    t = pygame.time.get_ticks() * 0.003
    bob = math.sin(t) * 0.05
    wave = math.sin(t * 1.5) * 0.03

    # Ghost body (translucent)
    glBegin(GL_QUADS)
    # Use multiple semi-transparent layers for ghost effect
    for i in range(3):
        a = 0.15 + i * 0.05
        w = 0.2 - i * 0.03 + wave
        glColor4f(0.6, 0.7, 0.9, a)
        y_base = 0.1 + bob + i * 0.05
        glVertex3f(-w, y_base, -w * 0.6)
        glVertex3f(w, y_base, -w * 0.6)
        glVertex3f(w, y_base + 0.6, -w * 0.5)
        glVertex3f(-w, y_base + 0.6, -w * 0.5)
        glVertex3f(-w, y_base, w * 0.6)
        glVertex3f(w, y_base, w * 0.6)
        glVertex3f(w, y_base + 0.6, w * 0.5)
        glVertex3f(-w, y_base + 0.6, w * 0.5)
    glEnd()

    # Head
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, 0.75 + bob, 0, 0.1, (180, 200, 230), 6)
    # Eyes
    draw_sphere_approx(-0.04, 0.76 + bob, -0.08, 0.02, (100, 150, 255), 4)
    draw_sphere_approx(0.04, 0.76 + bob, -0.08, 0.02, (100, 150, 255), 4)
    glEnd()

    # Ghost circle
    glBegin(GL_LINE_LOOP)
    glColor4f(0.6, 0.6, 1.0, 0.5)
    for i in range(24):
        a = 2 * math.pi * i / 24
        glVertex3f(math.cos(a) * 0.25, 0.005, math.sin(a) * 0.25)
    glEnd()
    glDisable(GL_BLEND)


def _draw_player_god():
    """Golden body with radiant aura and crown."""
    # Aura glow (ground circle)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glBegin(GL_TRIANGLE_FAN)
    glColor4f(1.0, 0.9, 0.4, 0.15)
    glVertex3f(0, 0.01, 0)
    for i in range(25):
        a = 2 * math.pi * i / 24
        glVertex3f(math.cos(a) * 0.6, 0.01, math.sin(a) * 0.6)
    glEnd()
    glDisable(GL_BLEND)

    body = (200, 180, 60)
    skin = (255, 240, 180)
    glBegin(GL_QUADS)
    # Legs
    draw_box(-0.08, 0, -0.05, 0.07, 0.4, 0.1, (180, 160, 50))
    draw_box(0.02, 0, -0.05, 0.07, 0.4, 0.1, (180, 160, 50))
    # Torso
    draw_box(-0.15, 0.42, -0.08, 0.3, 0.4, 0.16, body)
    # Arms
    draw_box(-0.22, 0.48, -0.04, 0.07, 0.32, 0.08, skin)
    draw_box(0.15, 0.48, -0.04, 0.07, 0.32, 0.08, skin)
    # Crown spikes
    for dx in [-0.06, 0.0, 0.06]:
        draw_box(dx - 0.015, 1.0, -0.015, 0.03, 0.1, 0.03, (255, 215, 0))
    glEnd()

    # Head
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, 0.92, 0, 0.12, skin, 8)
    glEnd()

    # Selection circle
    glBegin(GL_LINE_LOOP)
    glColor3f(1.0, 0.85, 0.0)
    for i in range(24):
        a = 2 * math.pi * i / 24
        glVertex3f(math.cos(a) * 0.3, 0.005, math.sin(a) * 0.3)
    glEnd()


def main():
    screen, clock, font, W, H = init_viewer("3D Player Character Viewer")
    mode_idx = 0
    az, el, dist = 25.0, -20.0, 4.0
    attacking = False
    attack_time = 0.0

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    mode_idx = (mode_idx - 1) % len(MODES)
                elif event.key == pygame.K_RIGHT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    mode_idx = (mode_idx + 1) % len(MODES)
                elif event.key == pygame.K_SPACE:
                    attacking = not attacking
                elif event.key == pygame.K_s:
                    d = glReadPixels(0, 0, W, H, GL_RGB, GL_UNSIGNED_BYTE)
                    pygame.image.save(pygame.image.fromstring(bytes(d), (W, H), "RGB", True),
                                      "screenshot_player_3d.png")
                else:
                    az, el, dist = handle_camera_keys(event, az, el, dist)

        if attacking:
            attack_time += dt * 3
            if attack_time > 1.0:
                attack_time -= 1.0

        setup_camera(W, H, az, el, dist)
        draw_ground_grid(2)

        mode = MODES[mode_idx]
        if mode == "mortal":
            _draw_player_mortal(attack_time if attacking else 0)
        elif mode == "ghost":
            _draw_player_ghost()
        elif mode == "god":
            _draw_player_god()

        # Side-by-side comparison: all 3 modes
        for i, m in enumerate(MODES):
            glPushMatrix()
            glTranslatef(-2.0 + i * 2.0, 0, 2.5)
            glScalef(0.5, 0.5, 0.5)
            if m == "mortal":
                _draw_player_mortal(attack_time if attacking else 0)
            elif m == "ghost":
                _draw_player_ghost()
            elif m == "god":
                _draw_player_god()
            glPopMatrix()

        draw_hud([
            f"Player: {mode.upper()} mode",
            f"LEFT/RIGHT: mode  SPACE: attack  SHIFT+Arrows: camera  +/-: zoom",
        ], font, W, H)

        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
