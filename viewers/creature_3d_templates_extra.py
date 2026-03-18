"""3D creature templates — small critters, reptiles, aquatic."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
from OpenGL.GL import *
from viewers.gl_viewer_base import draw_box, draw_sphere_approx


def _dk(c, a=20):
    return (max(0, c[0] - a), max(0, c[1] - a), max(0, c[2] - a))


def _lt(c, a=15):
    return (min(255, c[0] + a), min(255, c[1] + a), min(255, c[2] + a))


def draw_small_3d(sc, color, ws, bob, cfg):
    """Rabbit, squirrel, rat, pig, frog — tiny distinctive 3D shapes."""
    shape = cfg.get("shape", "round")
    br = 0.08 * sc
    by = 0.08 * sc + bob
    swing = ws * 20

    if shape == "squat":
        # Frog — flat wide body, big eyes, splayed legs
        bw, bh, bd = br * 3, br * 1.2, br * 2.5
        glBegin(GL_QUADS)
        draw_box(-bw / 2, by, -bd / 2, bw, bh, bd, color)
        # Lighter belly
        draw_box(-bw / 3, by - 0.005, -bd / 3, bw * 2 / 3, 0.005, bd * 2 / 3, _lt(color, 15))
        glEnd()
        # Big eyes (spheres on top)
        glBegin(GL_TRIANGLES)
        for dz in (-br * 0.8, br * 0.8):
            draw_sphere_approx(br * 0.5, by + bh + br * 0.3, dz,
                               br * 0.5, _lt(color, 25), 5)
            # Pupil
            draw_sphere_approx(br * 0.8, by + bh + br * 0.4, dz,
                               br * 0.2, (20, 20, 20), 4)
        glEnd()
        # Splayed legs
        for i, (lx, lz) in enumerate([(-bw * 0.4, -bd * 0.4), (-bw * 0.4, bd * 0.4),
                                        (bw * 0.3, -bd * 0.5), (bw * 0.3, bd * 0.5)]):
            glPushMatrix()
            glTranslatef(lx, by, lz)
            glRotatef(45 if i < 2 else -30, 0, 0, 1)
            s_phase = swing if i % 2 == 0 else -swing
            glRotatef(s_phase, 1, 0, 0)
            glBegin(GL_QUADS)
            lw = 0.015 * sc
            draw_box(-lw, -br * 1.5, -lw, lw * 2, br * 1.5, lw * 2, _dk(color, 15))
            # Webbed foot
            draw_box(-lw * 2, -br * 1.5 - 0.01, -lw * 2,
                     lw * 4, 0.01, lw * 4, _dk(color, 25))
            glEnd()
            glPopMatrix()
    else:
        # Round/oval critters (rabbit, squirrel, rat, pig)
        if shape == "oval":
            bw, bh, bd = br * 2.5, br * 1.5, br * 1.5
        else:
            bw, bh, bd = br * 2, br * 2, br * 2

        glBegin(GL_QUADS)
        # Body
        draw_box(-bw / 2, by, -bd / 2, bw, bh, bd, color)
        # Belly
        draw_box(-bw / 3, by - 0.005, -bd / 3, bw * 2 / 3, 0.005, bd * 2 / 3, _lt(color, 12))
        glEnd()

        # Head (sphere)
        hr = br * 0.8
        hx = bw / 2 + hr * 0.3
        hy = by + bh * 0.6
        glBegin(GL_TRIANGLES)
        draw_sphere_approx(hx, hy, 0, hr, _lt(color, 10), 6)
        # Eye
        draw_sphere_approx(hx + hr * 0.6, hy + hr * 0.2, -hr * 0.4,
                           hr * 0.2, (40, 30, 20), 4)
        glEnd()

        # Snout (pig)
        if cfg.get("snout"):
            glBegin(GL_QUADS)
            draw_box(hx + hr * 0.6, hy - hr * 0.2, -hr * 0.25,
                     hr * 0.5, hr * 0.4, hr * 0.5, _lt(color, 20))
            glEnd()

        # Ears
        ears = cfg.get("ears", "round")
        if ears == "tall":
            # Rabbit ears — tall thin boxes
            glBegin(GL_QUADS)
            for dz in (-hr * 0.3, hr * 0.3):
                draw_box(hx - hr * 0.2, hy + hr * 0.5, dz - 0.008,
                         0.016, br * 2.5, 0.016, _lt(color, 8))
                # Inner ear
                draw_box(hx - hr * 0.15, hy + hr * 0.7, dz - 0.005,
                         0.01, br * 1.8, 0.01, _lt(color, 30))
            glEnd()
        elif ears == "round":
            glBegin(GL_TRIANGLES)
            for dz in (-hr * 0.5, hr * 0.5):
                draw_sphere_approx(hx - hr * 0.1, hy + hr * 0.7, dz,
                                   hr * 0.3, color, 4)
            glEnd()
        elif ears == "floppy":
            glBegin(GL_QUADS)
            for dz_sign in (-1, 1):
                draw_box(hx - hr * 0.3, hy + hr * 0.1, dz_sign * hr * 0.5,
                         0.015, hr * 0.8, dz_sign * hr * 0.5, _dk(color, 10))
            glEnd()

        # Tiny legs
        lw = 0.012 * sc
        lh = 0.06 * sc
        for i, (lx, lz) in enumerate([(-br * 0.5, -br * 0.4), (-br * 0.5, br * 0.4),
                                        (br * 0.4, -br * 0.4), (br * 0.4, br * 0.4)]):
            lo = ws * 0.02 * (1 if i % 2 == 0 else -1)
            glPushMatrix()
            glTranslatef(lx, by, lz)
            glRotatef((swing if i % 2 == 0 else -swing), 0, 0, 1)
            glBegin(GL_QUADS)
            draw_box(-lw, -lh, -lw + lo, lw * 2, lh, lw * 2, _dk(color, 20))
            glEnd()
            glPopMatrix()

        # Tail
        tail = cfg.get("tail", "")
        if tail == "bushy_up":
            # Squirrel — tall fluffy tail curving up behind
            glBegin(GL_QUADS)
            tw = 0.03 * sc
            for i in range(3):
                t = i / 3
                tx = -bw / 2 - t * br
                ty_t = by + bh * 0.5 + t * br * 2
                draw_box(tx - tw, ty_t, -tw, tw * 2, br * 0.8, tw * 2,
                         _lt(color, 5 + i * 3))
            glEnd()
        elif tail == "puff":
            # Rabbit — small puff
            glBegin(GL_TRIANGLES)
            draw_sphere_approx(-bw / 2 - br * 0.3, by + bh * 0.3, 0,
                               br * 0.4, _lt(color, 20), 4)
            glEnd()
        elif tail == "thin":
            # Rat — long thin
            glBegin(GL_QUADS)
            tw = 0.008 * sc
            draw_box(-bw / 2 - br * 2, by + bh * 0.3, -tw,
                     br * 2, tw * 2, tw * 2, _dk(color, 10))
            glEnd()


def draw_reptile_3d(sc, color, ws, bob, cfg):
    """Crocodile, turtle, basilisk — low flat bodies."""
    shape = cfg.get("shape", "long")

    if shape == "shell":
        # Turtle — dome shell + peeking head + stubby legs
        sw = 0.2 * sc
        sh = 0.15 * sc
        by = 0.08 * sc + bob
        glBegin(GL_QUADS)
        # Shell (slightly domed via stacked boxes)
        draw_box(-sw / 2, by, -sw / 2, sw, sh * 0.6, sw, color)
        draw_box(-sw * 0.35, by + sh * 0.6, -sw * 0.35,
                 sw * 0.7, sh * 0.3, sw * 0.7, _lt(color, 8))
        # Shell pattern
        draw_box(-sw * 0.15, by + sh * 0.85, -sw * 0.15,
                 sw * 0.3, sh * 0.08, sw * 0.3, _dk(color, 15))
        # Head peeking out front
        hr = 0.04 * sc
        draw_box(sw / 2, by + sh * 0.2, -hr, hr * 2, hr * 1.5, hr * 2, _lt(color, 20))
        draw_box(sw / 2 + hr * 1.5, by + sh * 0.35, -0.01, 0.015, 0.015, 0.01, (30, 30, 30))
        # Stubby legs
        lw = 0.025 * sc
        for lx, lz in [(-sw * 0.35, -sw * 0.4), (-sw * 0.35, sw * 0.3),
                        (sw * 0.25, -sw * 0.4), (sw * 0.25, sw * 0.3)]:
            draw_box(lx, 0, lz, lw, by + 0.01, lw, _dk(color, 20))
        # Tail
        draw_box(-sw / 2 - 0.08 * sc, by + sh * 0.2, -0.01,
                 0.08 * sc, 0.02, 0.02, _dk(color, 10))
        glEnd()
    else:
        # Crocodile / basilisk — long flat body + jaws + stubby legs
        bw = 0.5 * sc
        bh = 0.08 * sc
        bd = 0.12 * sc
        by = 0.08 * sc + bob
        swing = ws * 15
        glBegin(GL_QUADS)
        draw_box(-bw / 2, by, -bd / 2, bw, bh, bd, color)
        # Belly
        draw_box(-bw / 3, by - 0.005, -bd / 3, bw * 2 / 3, 0.005, bd * 2 / 3, _lt(color, 10))
        # Scale ridges along back
        for i in range(max(2, int(bw / (0.06 * sc)))):
            rx = -bw / 2 + i * 0.06 * sc + 0.02
            draw_box(rx, by + bh, -0.01, 0.02, 0.015, 0.02, _dk(color, 10))
        # Stubby legs
        lw = 0.025 * sc
        lh = 0.07 * sc
        for i, (lx, lz) in enumerate([(-bw * 0.3, -bd * 0.5), (-bw * 0.3, bd * 0.4),
                                        (bw * 0.2, -bd * 0.5), (bw * 0.2, bd * 0.4)]):
            lo = swing * 0.005 * (1 if i % 2 == 0 else -1)
            draw_box(lx, 0, lz + lo, lw, by + 0.01, lw, _dk(color, 20))
        # Head / jaws
        if cfg.get("jaws"):
            # Upper jaw
            draw_box(bw / 2, by + bh * 0.3, -bd * 0.3,
                     0.15 * sc, bh * 0.6, bd * 0.6, _lt(color, 8))
            # Lower jaw (slightly open)
            draw_box(bw / 2, by - 0.01, -bd * 0.25,
                     0.12 * sc, bh * 0.4, bd * 0.5, _lt(color, 5))
            # Teeth
            for i in range(3):
                tz = -bd * 0.2 + i * bd * 0.15
                draw_box(bw / 2 + 0.03 + i * 0.02, by + bh * 0.3, tz,
                         0.008, 0.015, 0.008, (230, 225, 210))
            # Eyes
            draw_box(bw / 2 + 0.02, by + bh * 0.7, -bd * 0.35,
                     0.015, 0.015, 0.01, (180, 180, 40))
            draw_box(bw / 2 + 0.02, by + bh * 0.7, bd * 0.25,
                     0.015, 0.015, 0.01, (180, 180, 40))
        else:
            # Simple head (basilisk)
            draw_box(bw / 2, by, -bd * 0.3, 0.1 * sc, bh * 1.2, bd * 0.6, _lt(color, 10))
            ec = (180, 255, 180) if cfg.get("eyes") == "glowing" else (200, 50, 40)
            draw_box(bw / 2 + 0.05, by + bh * 0.7, -bd * 0.35,
                     0.015, 0.015, 0.01, ec)
        # Tail
        for i in range(3):
            t = (i + 1) / 4
            tw = bd * (1 - t * 0.4)
            draw_box(-bw / 2 - t * 0.15 * sc, by + bh * 0.2,
                     -tw / 2, 0.04, bh * (1 - t * 0.3), tw, _dk(color, 5 + i * 3))
        glEnd()


def draw_aquatic_3d(sc, color, ws, bob, cfg):
    """Fish, fish school, crabs."""
    shape = cfg.get("shape", "fish")

    if shape == "school":
        # Multiple small fish
        glBegin(GL_QUADS)
        for i in range(4):
            fx = math.sin(i * 2.5 + ws * 3) * 0.15 * sc
            fz = math.cos(i * 1.7 + ws * 2) * 0.1 * sc
            fr = 0.04 * sc
            draw_box(fx - fr, 0.05 + bob, fz - fr * 0.5,
                     fr * 2, fr, fr, color)
            # Tail fin
            draw_box(fx - fr * 2, 0.05 + bob, fz - fr * 0.3,
                     fr * 0.8, fr * 0.8, fr * 0.6, _dk(color, 15))
        glEnd()
    elif shape == "crab":
        # Crab — wide flat body + claws + eye stalks + legs
        bw, bh, bd = 0.2 * sc, 0.06 * sc, 0.15 * sc
        by = 0.06 * sc + bob
        glBegin(GL_QUADS)
        draw_box(-bw / 2, by, -bd / 2, bw, bh, bd, color)
        # Claws
        for dz_sign in (-1, 1):
            cx = bw / 2 + 0.02
            cz = dz_sign * bd * 0.3
            # Arm
            draw_box(cx, by + bh * 0.3, cz - 0.015, 0.06 * sc, 0.03, 0.03, _lt(color, 10))
            # Pincer (two halves)
            px = cx + 0.06 * sc
            draw_box(px, by + bh * 0.4, cz - 0.02, 0.03, 0.015, 0.01, _lt(color, 15))
            draw_box(px, by + bh * 0.15, cz - 0.02, 0.03, 0.015, 0.01, _lt(color, 15))
        # Eye stalks
        for dz in (-bd * 0.2, bd * 0.2):
            draw_box(bw * 0.2, by + bh, dz - 0.005, 0.01, 0.04 * sc, 0.01, color)
            draw_box(bw * 0.2, by + bh + 0.04 * sc, dz - 0.008,
                     0.016, 0.016, 0.016, (20, 20, 20))
        # Legs (3 pairs on sides)
        swing_c = ws * 0.02
        for i in range(3):
            for dz_sign in (-1, 1):
                lx = -bw * 0.3 + i * bw * 0.25
                lz = dz_sign * (bd / 2 + 0.01)
                lo = swing_c * (1 if (i + (0 if dz_sign > 0 else 1)) % 2 == 0 else -1)
                draw_box(lx, 0, lz + lo, 0.015, by + 0.005, 0.015, _dk(color, 15))
        glEnd()
    else:
        # Single fish
        bw, bh, bd = 0.2 * sc, 0.08 * sc, 0.06 * sc
        by = 0.06 * sc + bob
        glBegin(GL_QUADS)
        draw_box(-bw / 2, by, -bd / 2, bw, bh, bd, color)
        # Tail fin (V shape via two angled boxes)
        draw_box(-bw / 2 - 0.06 * sc, by - 0.01, -bd * 0.4,
                 0.05 * sc, bh * 0.5, bd * 0.3, _dk(color, 15))
        draw_box(-bw / 2 - 0.06 * sc, by + bh * 0.5, -bd * 0.4,
                 0.05 * sc, bh * 0.5, bd * 0.3, _dk(color, 15))
        # Dorsal fin
        draw_box(-0.02, by + bh, -0.005, 0.06 * sc, 0.04 * sc, 0.01, _dk(color, 10))
        # Eye
        draw_box(bw / 2 - 0.02, by + bh * 0.6, -bd * 0.55,
                 0.015, 0.015, 0.01, (30, 30, 30))
        draw_box(bw / 2 - 0.02, by + bh * 0.6, bd * 0.45,
                 0.015, 0.015, 0.01, (30, 30, 30))
        # Mouth
        draw_box(bw / 2, by + bh * 0.3, -0.01, 0.008, 0.01, 0.02, _dk(color, 30))
        glEnd()
