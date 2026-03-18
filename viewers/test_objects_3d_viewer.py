#!/usr/bin/env python3
"""3D World Objects Viewer — siege engines, vehicles, fortifications in OpenGL.

Controls:
  LEFT/RIGHT: cycle object
  SHIFT+Arrows: camera    +/-: zoom
  SPACE: toggle firing/moving state
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


def _dk(c, a=20):
    return (max(0, c[0] - a), max(0, c[1] - a), max(0, c[2] - a))


def _lt(c, a=15):
    return (min(255, c[0] + a), min(255, c[1] + a), min(255, c[2] + a))


# ── 3D Siege Engines ────────────────────────────────────────────────────

def draw_battering_ram_3d(firing=False):
    wood = (110, 80, 45)
    metal = (150, 150, 160)
    glBegin(GL_QUADS)
    # Frame base
    draw_box(-0.6, 0.15, -0.2, 1.2, 0.12, 0.4, _dk(wood, 10))
    # Main log
    log_ext = 0.15 if firing else 0
    draw_box(-0.7, 0.22, -0.08, 1.6 + log_ext, 0.16, 0.16, wood)
    # Wheels (4)
    for x in (-0.35, 0.35):
        for z in (-0.22, 0.22):
            draw_box(x - 0.06, 0, z - 0.03, 0.12, 0.15, 0.06, (55, 45, 35))
    # Cross supports
    for x in (-0.3, 0.0, 0.3):
        draw_box(x - 0.03, 0.12, -0.2, 0.06, 0.18, 0.4, _dk(wood, 15))
    # Rope handles
    for z in (-0.15, 0.15):
        draw_box(-0.5, 0.35, z - 0.015, 0.08, 0.03, 0.03, (140, 120, 80))
        draw_box(0.3, 0.35, z - 0.015, 0.08, 0.03, 0.03, (140, 120, 80))
    glEnd()
    # Ram head (sphere)
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0.75 + log_ext, 0.3, 0, 0.1, metal, 6)
    glEnd()


def draw_catapult_3d(firing=False):
    wood = (120, 90, 50)
    arm_angle = 30 if firing else 70
    glBegin(GL_QUADS)
    # Platform
    draw_box(-0.4, 0.12, -0.3, 0.8, 0.1, 0.6, wood)
    # Wheels
    for z in (-0.32, 0.32):
        draw_box(-0.3, 0, z - 0.04, 0.12, 0.14, 0.08, (55, 45, 35))
        draw_box(0.2, 0, z - 0.04, 0.12, 0.14, 0.08, (55, 45, 35))
    # Pivot frame (A-frame)
    draw_box(-0.06, 0.2, -0.08, 0.12, 0.4, 0.16, _dk(wood, 15))
    glEnd()
    # Throwing arm (rotated)
    glPushMatrix()
    glTranslatef(0, 0.55, 0)
    glRotatef(arm_angle, 0, 0, 1)
    glBegin(GL_QUADS)
    draw_box(-0.03, 0, -0.03, 0.06, 0.6, 0.06, (100, 75, 40))
    # Bucket at end
    draw_box(-0.06, 0.55, -0.06, 0.12, 0.08, 0.12, (90, 70, 45))
    glEnd()
    if not firing:
        glBegin(GL_TRIANGLES)
        draw_sphere_approx(0, 0.6, 0, 0.06, (140, 130, 120), 5)
        glEnd()
    glPopMatrix()


def draw_trebuchet_3d(firing=False):
    wood = (100, 75, 40)
    arm_angle = 25 if firing else 65
    glBegin(GL_QUADS)
    # Base frame
    draw_box(-0.6, 0.1, -0.35, 1.2, 0.12, 0.7, wood)
    # Large wheels (6)
    for x in (-0.4, 0.0, 0.4):
        for z in (-0.38, 0.38):
            draw_box(x - 0.06, 0, z - 0.04, 0.12, 0.12, 0.08, (50, 40, 30))
    # A-frame pivot (tall)
    draw_box(-0.08, 0.2, -0.1, 0.16, 0.7, 0.2, _dk(wood, 10))
    # Cross brace
    draw_box(-0.25, 0.15, -0.04, 0.5, 0.06, 0.08, _dk(wood, 5))
    glEnd()
    # Throwing arm
    glPushMatrix()
    glTranslatef(0, 0.85, 0)
    glRotatef(arm_angle, 0, 0, 1)
    glBegin(GL_QUADS)
    draw_box(-0.03, -0.25, -0.03, 0.06, 0.9, 0.06, (90, 65, 35))
    # Counterweight (short end)
    draw_box(-0.1, -0.3, -0.1, 0.2, 0.2, 0.2, (80, 80, 90))
    glEnd()
    if not firing:
        # Sling + stone at long end
        glBegin(GL_TRIANGLES)
        draw_sphere_approx(0, 0.65, 0, 0.08, (140, 130, 120), 5)
        glEnd()
    glPopMatrix()


def draw_siege_tower_3d():
    wood = (130, 100, 60)
    glBegin(GL_QUADS)
    # Main body (tall box)
    draw_box(-0.3, 0.15, -0.25, 0.6, 1.2, 0.5, wood)
    # Floors (3 levels visible as darker lines)
    for i in range(1, 4):
        fy = 0.15 + i * 0.3
        draw_box(-0.28, fy, -0.23, 0.56, 0.02, 0.46, _dk(wood, 12))
    # Arrow slits on front
    for i in range(3):
        fy = 0.35 + i * 0.3
        draw_box(-0.05, fy, -0.26, 0.1, 0.06, 0.02, (35, 30, 25))
    # Arrow slits on sides
    for z in (-0.26, 0.24):
        for i in range(3):
            fy = 0.35 + i * 0.3
            draw_box(-0.28 if z < 0 else 0.26, fy, z - 0.03, 0.02, 0.06, 0.06,
                     (35, 30, 25))
    # Drawbridge (top, hinged forward)
    draw_box(0.3, 1.15, -0.2, 0.3, 0.03, 0.4, _lt(wood, 10))
    # Wheels (4, large)
    for x in (-0.2, 0.2):
        for z in (-0.28, 0.28):
            draw_box(x - 0.06, 0, z - 0.04, 0.12, 0.16, 0.08, (50, 40, 30))
    # Peaked roof
    glEnd()
    glBegin(GL_TRIANGLES)
    # Roof ridge
    c = _dk(wood, 10)
    r, g, b = c[0] / 255, c[1] / 255, c[2] / 255
    glColor3f(r, g, b)
    # Front slope
    glVertex3f(-0.3, 1.35, -0.25); glVertex3f(0.3, 1.35, -0.25); glVertex3f(0, 1.55, 0)
    # Back slope
    glVertex3f(0.3, 1.35, 0.25); glVertex3f(-0.3, 1.35, 0.25); glVertex3f(0, 1.55, 0)
    # Sides
    glVertex3f(-0.3, 1.35, -0.25); glVertex3f(-0.3, 1.35, 0.25); glVertex3f(0, 1.55, 0)
    glVertex3f(0.3, 1.35, 0.25); glVertex3f(0.3, 1.35, -0.25); glVertex3f(0, 1.55, 0)
    glEnd()


# ── 3D Vehicles ─────────────────────────────────────────────────────────

def draw_cart_3d(size="cart"):
    sizes = {"handcart": (0.25, 0.12), "cart": (0.35, 0.15),
             "wagon": (0.5, 0.2), "supply": (0.6, 0.22)}
    bw, bh = sizes.get(size, (0.35, 0.15))
    bd = 0.2
    colors = {"handcart": (160, 130, 80), "cart": (140, 110, 70),
              "wagon": (120, 90, 50), "supply": (110, 85, 45)}
    wood = colors.get(size, (140, 110, 70))

    glBegin(GL_QUADS)
    # Cart body
    draw_box(-bw, 0.12, -bd / 2, bw * 2, bh, bd, wood)
    # Side rails
    draw_box(-bw, 0.12 + bh, -bd / 2, bw * 2, 0.04, 0.02, _dk(wood, 10))
    draw_box(-bw, 0.12 + bh, bd / 2 - 0.02, bw * 2, 0.04, 0.02, _dk(wood, 10))
    # Front/back walls
    draw_box(-bw, 0.12 + bh, -bd / 2, 0.02, 0.04, bd, _dk(wood, 10))
    draw_box(bw - 0.02, 0.12 + bh, -bd / 2, 0.02, 0.04, bd, _dk(wood, 10))

    # Wheels
    n_wheels = 1 if size == "handcart" else (2 if size == "cart" else 4)
    wheel_r = 0.08 if size in ("wagon", "supply") else 0.06
    if n_wheels == 1:
        draw_box(bw - 0.03, 0, -0.03, 0.06, 0.13, 0.06, (55, 45, 35))
    elif n_wheels == 2:
        for z in (-bd / 2 - 0.03, bd / 2):
            draw_box(0 - 0.03, 0, z, 0.06, 0.13, 0.06, (55, 45, 35))
    else:
        for x in (-bw * 0.6, bw * 0.6):
            for z in (-bd / 2 - 0.04, bd / 2):
                draw_box(x - 0.04, 0, z, 0.08, 0.14, 0.06, (50, 40, 30))

    # Shaft/yoke extending forward
    draw_box(bw, 0.15, -0.015, 0.4, 0.03, 0.03, (100, 80, 50))

    # Canvas cover (wagon/supply only)
    if size in ("wagon", "supply"):
        # Hoops
        for x in (-bw * 0.5, 0, bw * 0.5):
            draw_box(x - 0.01, 0.12 + bh, -bd / 2, 0.02, 0.15, bd, (150, 120, 70))
        # Canvas top
        draw_box(-bw, 0.12 + bh + 0.13, -bd / 2, bw * 2, 0.02, bd, (180, 170, 150))

    # Cargo (visible inside)
    draw_box(-bw * 0.6, 0.13, -bd * 0.3, bw * 1.2, bh * 0.6, bd * 0.6, (200, 180, 80))
    glEnd()


# ── 3D Fortifications ───────────────────────────────────────────────────

def draw_wall_3d(stone=True):
    color = (130, 125, 115) if stone else (110, 80, 45)
    h = 0.6 if stone else 0.5
    glBegin(GL_QUADS)
    draw_box(-0.5, 0, -0.1, 1.0, h, 0.2, color)
    if stone:
        # Brick lines
        for i in range(5):
            by = i * h / 5
            draw_box(-0.5, by, -0.101, 1.0, 0.008, 0.002, _dk(color, 15))
        # Crenellations
        for i in range(3):
            draw_box(-0.4 + i * 0.35, h, -0.1, 0.15, 0.12, 0.2, _lt(color, 5))
    else:
        # Pointed palisade tops
        for i in range(5):
            px = -0.4 + i * 0.2
            draw_box(px - 0.04, h, -0.06, 0.08, 0.15, 0.12, _lt(color, 8))
    glEnd()
    if not stone:
        # Pointed tips (triangles)
        glBegin(GL_TRIANGLES)
        c = _lt(color, 8)
        r, g, b = c[0] / 255, c[1] / 255, c[2] / 255
        for i in range(5):
            px = -0.4 + i * 0.2
            glColor3f(r, g, b)
            glVertex3f(px - 0.04, h + 0.15, -0.06)
            glVertex3f(px + 0.04, h + 0.15, -0.06)
            glVertex3f(px, h + 0.25, 0)
        glEnd()


def draw_tower_3d():
    color = (120, 115, 105)
    glBegin(GL_QUADS)
    draw_box(-0.25, 0, -0.25, 0.5, 1.0, 0.5, color)
    # Arrow slits
    for z in (-0.26, 0.24):
        for i in range(2):
            fy = 0.3 + i * 0.3
            draw_box(-0.05, fy, z, 0.1, 0.08, 0.02, (35, 30, 25))
    for x in (-0.26, 0.24):
        for i in range(2):
            fy = 0.3 + i * 0.3
            draw_box(x, fy, -0.05, 0.02, 0.08, 0.1, (35, 30, 25))
    # Crenellations
    for i in range(3):
        for j in range(3):
            if (i + j) % 2 == 0:
                draw_box(-0.25 + i * 0.2, 1.0, -0.25 + j * 0.2,
                         0.12, 0.1, 0.12, _lt(color, 5))
    glEnd()
    # Flag
    glBegin(GL_QUADS)
    draw_box(-0.01, 1.1, -0.01, 0.02, 0.3, 0.02, (80, 70, 60))
    draw_box(0.01, 1.25, -0.01, 0.15, 0.1, 0.02, (180, 40, 40))
    glEnd()


# ── Object list ─────────────────────────────────────────────────────────

OBJECTS = [
    ("Battering Ram", lambda f: draw_battering_ram_3d(f), True),
    ("Catapult", lambda f: draw_catapult_3d(f), True),
    ("Trebuchet", lambda f: draw_trebuchet_3d(f), True),
    ("Siege Tower", lambda f: draw_siege_tower_3d(), False),
    ("Handcart", lambda f: draw_cart_3d("handcart"), False),
    ("Cart", lambda f: draw_cart_3d("cart"), False),
    ("Wagon", lambda f: draw_cart_3d("wagon"), False),
    ("Supply Wagon", lambda f: draw_cart_3d("supply"), False),
    ("Palisade", lambda f: draw_wall_3d(False), False),
    ("Stone Wall", lambda f: draw_wall_3d(True), False),
    ("Tower", lambda f: draw_tower_3d(), False),
]


def main():
    screen, clock, font, W, H = init_viewer("3D World Objects Viewer")
    idx = 0
    az, el, dist = 35.0, -30.0, 6.0
    firing = False

    running = True
    while running:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    idx = (idx - 1) % len(OBJECTS)
                elif event.key == pygame.K_RIGHT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    idx = (idx + 1) % len(OBJECTS)
                elif event.key == pygame.K_SPACE:
                    firing = not firing
                elif event.key == pygame.K_s:
                    d = glReadPixels(0, 0, W, H, GL_RGB, GL_UNSIGNED_BYTE)
                    pygame.image.save(pygame.image.fromstring(bytes(d), (W, H), "RGB", True),
                                      "screenshot_objects_3d.png")
                else:
                    az, el, dist = handle_camera_keys(event, az, el, dist)

        setup_camera(W, H, az, el, dist, look_y=0.4)
        draw_ground_grid(3)

        name, draw_fn, has_fire = OBJECTS[idx]
        draw_fn(firing and has_fire)

        draw_hud([
            f"{name} [{idx + 1}/{len(OBJECTS)}]"
            + (" | FIRING" if firing and has_fire else ""),
            "LEFT/RIGHT: object  SPACE: fire/toggle",
            "SHIFT+Arrows: camera  +/-: zoom  S: screenshot",
        ], font, W, H)

        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
