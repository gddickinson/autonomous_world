"""3D creature poses — sleeping, resting, combat for different body types."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
from OpenGL.GL import *
from viewers.gl_viewer_base import draw_box, draw_sphere_approx


def _dk(c, a=20):
    return (max(0, c[0] - a), max(0, c[1] - a), max(0, c[2] - a))


def _lt(c, a=15):
    return (min(255, c[0] + a), min(255, c[1] + a), min(255, c[2] + a))


def draw_quadruped_sleeping_3d(sc, color, cfg):
    """Quadruped curled up on ground — body flat, legs tucked, tail wrapped."""
    bw = 0.3 * sc
    bh = 0.08 * sc  # thin when lying
    bd = 0.2 * sc
    ground_y = 0.02

    glBegin(GL_QUADS)
    # Flat body on ground
    draw_box(-bw / 2, ground_y, -bd / 2, bw, bh, bd, color)
    # Belly
    draw_box(-bw / 3, ground_y - 0.005, -bd / 3, bw * 2 / 3, 0.005, bd * 2 / 3,
             _lt(color, 10))
    # Tucked legs (small bumps at sides)
    for dx, dz in [(-bw * 0.3, -bd * 0.4), (-bw * 0.3, bd * 0.3),
                    (bw * 0.2, -bd * 0.4), (bw * 0.2, bd * 0.3)]:
        draw_box(dx, ground_y, dz, 0.04 * sc, bh, 0.04 * sc, _dk(color, 15))
    # Head tucked into body
    draw_box(bw * 0.2, ground_y + bh * 0.3, -0.05 * sc,
             0.1 * sc, 0.08 * sc, 0.1 * sc, _lt(color, 8))
    # Closed eyes (thin dark line)
    draw_box(bw * 0.28, ground_y + bh + 0.05, -0.055 * sc,
             0.02, 0.005, 0.005, (50, 40, 30))
    # Tail wrapped around body
    draw_box(-bw / 2 - 0.05 * sc, ground_y, -bd * 0.3,
             0.08 * sc, bh * 0.7, bd * 0.6, _dk(color, 8))
    glEnd()


def draw_quadruped_resting_3d(sc, color, cfg):
    """Quadruped lying down but alert — flat body, head raised."""
    bw = 0.35 * sc
    bh = 0.08 * sc
    bd = 0.2 * sc
    ground_y = 0.02

    glBegin(GL_QUADS)
    # Flat body
    draw_box(-bw / 2, ground_y, -bd / 2, bw, bh, bd, color)
    # Tucked legs
    for dx, dz in [(-bw * 0.3, -bd * 0.45), (-bw * 0.3, bd * 0.35),
                    (bw * 0.2, -bd * 0.45), (bw * 0.2, bd * 0.35)]:
        draw_box(dx, ground_y, dz, 0.04 * sc, bh + 0.01, 0.04 * sc, _dk(color, 15))
    # Neck (angled up from body)
    draw_box(bw * 0.25, ground_y + bh, -0.03 * sc,
             0.05 * sc, 0.12 * sc, 0.06 * sc, color)
    # Head raised
    draw_box(bw * 0.22, ground_y + bh + 0.1 * sc, -0.05 * sc,
             0.1 * sc, 0.07 * sc, 0.1 * sc, _lt(color, 8))
    # Eyes (alert)
    eye_c = (200, 50, 40) if cfg.get("eyes") == "predator" else (50, 40, 20)
    draw_box(bw * 0.3, ground_y + bh + 0.14 * sc, -0.055 * sc,
             0.015, 0.015, 0.01, eye_c)
    draw_box(bw * 0.3, ground_y + bh + 0.14 * sc, 0.04 * sc,
             0.015, 0.015, 0.01, eye_c)
    # Tail
    draw_box(-bw / 2 - 0.08 * sc, ground_y, -0.02,
             0.1 * sc, bh * 0.6, 0.04, _dk(color, 8))
    glEnd()


def draw_quadruped_combat_3d(sc, color, cfg):
    """Quadruped aggressive — low stance, head forward, hackles raised."""
    bw = 0.4 * sc
    bh = 0.18 * sc
    bd = 0.2 * sc
    by = 0.15 * sc  # lower than normal

    glBegin(GL_QUADS)
    # Body (low, tense)
    draw_box(-bw / 2, by, -bd / 2, bw, bh, bd, color)
    # Hackles (spiky ridge on back)
    for i in range(max(2, int(bw / (0.05 * sc)))):
        hx = -bw / 3 + i * 0.05 * sc
        draw_box(hx, by + bh, -0.01, 0.03 * sc, 0.04 * sc, 0.02, _dk(color, 10))
    glEnd()

    # Legs (wide stance, rotated slightly outward)
    lw, lh = 0.04 * sc, 0.15 * sc
    for i, (lx, lz) in enumerate([(-bw * 0.35, -bd * 0.35), (-bw * 0.35, bd * 0.25),
                                    (bw * 0.3, -bd * 0.35), (bw * 0.3, bd * 0.25)]):
        glPushMatrix()
        glTranslatef(lx, by, lz)
        glRotatef(8 if i % 2 == 0 else -8, 0, 0, 1)  # splay outward
        glBegin(GL_QUADS)
        draw_box(-lw / 2, -lh, -lw / 2, lw, lh, lw, _dk(color, 20))
        glEnd()
        glPopMatrix()

    glBegin(GL_QUADS)
    # Head (low, mouth open)
    hr = 0.08 * sc
    hx = bw / 2 + hr * 0.3
    hy = by + bh * 0.3
    # Upper jaw
    draw_box(hx, hy, -hr * 0.4, hr * 1.2, hr * 0.5, hr * 0.8, _lt(color, 10))
    # Lower jaw (dropped open)
    draw_box(hx, hy - hr * 0.3, -hr * 0.35, hr, hr * 0.3, hr * 0.7, _dk(color, 5))
    # Teeth
    for tz in range(-2, 3):
        draw_box(hx + hr * 0.3 + tz * 0.02, hy, -hr * 0.1 + tz * 0.03,
                 0.008, 0.015, 0.008, (230, 225, 210))
    # Eyes (angry)
    draw_box(hx + hr * 0.2, hy + hr * 0.35, -hr * 0.35, 0.02, 0.02, 0.015, (220, 50, 40))
    draw_box(hx + hr * 0.2, hy + hr * 0.35, hr * 0.2, 0.02, 0.02, 0.015, (220, 50, 40))
    glEnd()


def draw_bird_perching_3d(sc, color, cfg):
    """Bird perched — compact round body, wings tucked, on ground."""
    br = 0.08 * sc
    by = 0.06 * sc

    glBegin(GL_QUADS)
    # Compact body
    draw_box(-br, by, -br * 0.7, br * 2, br * 1.5, br * 1.4, color)
    # Breast
    draw_box(-br * 0.5, by - 0.005, -br * 0.5, br, 0.005, br, _lt(color, 10))
    # Folded wing hints
    draw_box(-br * 0.8, by + br * 0.5, -br * 0.6, br * 1.6, 0.01, br * 1.2,
             _dk(color, 8))
    # Head
    hr = br * 0.7
    draw_box(-hr / 2, by + br * 1.3, -hr / 2, hr, hr, hr, _lt(color, 10))
    # Beak
    draw_box(hr * 0.3, by + br * 1.4, -0.01, hr * 0.5, hr * 0.25, 0.02, (200, 170, 50))
    # Eye
    draw_box(hr * 0.15, by + br * 1.5, -hr * 0.55, 0.01, 0.01, 0.008, (30, 30, 30))
    # Legs
    for dz in (-br * 0.2, br * 0.2):
        draw_box(dz - 0.005, 0, -0.005, 0.01, by + 0.01, 0.01, (180, 150, 80))
    glEnd()


def draw_serpent_coiled_3d(sc, color, cfg):
    """Serpent coiled — concentric ring of segments, head raised."""
    coil_r = 0.15 * sc
    seg_r = 0.025 * sc
    ground_y = 0.02

    # Coiled body (ring of boxes)
    glBegin(GL_QUADS)
    segs = 12
    for i in range(segs):
        a = 2 * math.pi * i / segs
        cx = math.cos(a) * coil_r
        cz = math.sin(a) * coil_r
        draw_box(cx - seg_r, ground_y, cz - seg_r,
                 seg_r * 2, seg_r * 2, seg_r * 2,
                 _dk(color, (i * 3) % 15))
    # Inner coil
    for i in range(segs):
        a = 2 * math.pi * i / segs
        cx = math.cos(a) * coil_r * 0.5
        cz = math.sin(a) * coil_r * 0.5
        draw_box(cx - seg_r * 0.8, ground_y + seg_r, cz - seg_r * 0.8,
                 seg_r * 1.6, seg_r * 1.6, seg_r * 1.6,
                 _dk(color, 5 + (i * 3) % 10))
    # Neck rising from coil
    draw_box(coil_r * 0.3, ground_y + seg_r * 2, -seg_r,
             seg_r * 2, 0.1 * sc, seg_r * 2, color)
    # Head
    draw_box(coil_r * 0.2, ground_y + seg_r * 2 + 0.1 * sc, -seg_r * 1.5,
             seg_r * 3, seg_r * 2, seg_r * 3, _lt(color, 10))
    # Eyes
    draw_box(coil_r * 0.2 + seg_r * 2, ground_y + seg_r * 2 + 0.12 * sc, -seg_r * 1.6,
             0.01, 0.01, 0.008, (200, 50, 40))
    glEnd()


def draw_creature_pose_3d(pose, template, sc, color, cfg):
    """Dispatch to the right 3D creature pose."""
    if template in ("quadruped", "ungulate", "bear"):
        if pose == "sleeping":
            draw_quadruped_sleeping_3d(sc, color, cfg)
            return True
        elif pose == "resting":
            draw_quadruped_resting_3d(sc, color, cfg)
            return True
        elif pose == "combat":
            draw_quadruped_combat_3d(sc, color, cfg)
            return True
    elif template == "bird":
        if pose in ("sleeping", "resting"):
            draw_bird_perching_3d(sc, color, cfg)
            return True
    elif template == "serpent":
        if pose in ("sleeping", "resting"):
            draw_serpent_coiled_3d(sc, color, cfg)
            return True
    return False  # not handled, use default
