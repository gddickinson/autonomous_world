"""3D creature shape templates using OpenGL — per-type geometry."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
from OpenGL.GL import *
from viewers.gl_viewer_base import draw_box, draw_sphere_approx


def _dk(c, a=20):
    return (max(0, c[0] - a), max(0, c[1] - a), max(0, c[2] - a))


def _lt(c, a=15):
    return (min(255, c[0] + a), min(255, c[1] + a), min(255, c[2] + a))


def _rotated_leg(x, y, z, lw, lh, color, angle_deg, axis='z'):
    """Draw a leg box rotated around its top (hip/shoulder joint).

    axis='z' swings front-to-back (along X), axis='x' swings side-to-side (along Z).
    """
    glPushMatrix()
    glTranslatef(x, y, z)
    if axis == 'z':
        glRotatef(angle_deg, 0, 0, 1)  # swing in X-Y plane (front-to-back)
    else:
        glRotatef(angle_deg, 1, 0, 0)  # swing in Z-Y plane (side-to-side)
    glBegin(GL_QUADS)
    draw_box(-lw / 2, -lh, -lw / 2, lw, lh, lw, color)
    # Foot/paw
    draw_box(-lw / 2 - 0.01, -lh - 0.03, -lw / 2, lw + 0.02, 0.03, lw, _dk(color, 30))
    glEnd()
    glPopMatrix()


def draw_quadruped_3d(sc, color, ws, bob, cfg):
    """Wolf, fox, cat, boar — horizontal body with rotating legs."""
    bw_r, bh_r = cfg.get("body_r", (1.0, 0.5))
    bw = 0.5 * sc * bw_r
    bh = 0.22 * sc * bh_r
    bd = 0.2 * sc
    by = 0.3 * sc + bob
    swing = ws * 30  # degrees
    lw, lh = 0.05 * sc, 0.25 * sc

    # Legs (rotating from hips)
    for i, (lx, lz) in enumerate([(-bw * 0.35, -bd * 0.3), (-bw * 0.35, bd * 0.3),
                                    (bw * 0.35, -bd * 0.3), (bw * 0.35, bd * 0.3)]):
        ang = swing if i % 2 == 0 else -swing
        _rotated_leg(lx, by, lz, lw, lh, _dk(color), ang)

    # Body
    glBegin(GL_QUADS)
    draw_box(-bw / 2, by, -bd / 2, bw, bh, bd, color)
    # Belly highlight
    draw_box(-bw / 3, by - 0.01, -bd / 3, bw * 2 / 3, 0.01, bd * 2 / 3, _lt(color, 10))
    glEnd()

    # Head
    hr = 0.1 * sc
    hx = bw / 2 + hr * 0.5
    hy = by + bh * 0.5
    head = cfg.get("head", "round")
    glBegin(GL_QUADS)
    if head == "pointed":
        # Snout: elongated box
        draw_box(hx - hr * 0.4, hy - hr * 0.4, -hr * 0.3,
                 hr * 1.8, hr * 0.8, hr * 0.6, _lt(color, 10))
        # Nose
        draw_box(hx + hr * 1.2, hy - 0.02, -0.02, 0.04, 0.04, 0.04, (30, 30, 30))
    elif head == "flat":
        # Flat snout (boar)
        draw_box(hx - hr * 0.5, hy - hr * 0.5, -hr * 0.4,
                 hr * 1.2, hr, hr * 0.8, _lt(color, 10))
        # Snout disc
        draw_box(hx + hr * 0.5, hy - hr * 0.2, -hr * 0.2,
                 hr * 0.4, hr * 0.4, hr * 0.4, _lt(color, 20))
    else:
        draw_box(hx - hr * 0.5, hy - hr * 0.5, -hr * 0.4,
                 hr, hr, hr * 0.8, _lt(color, 10))
    # Eyes
    eye_c = (200, 50, 40) if cfg.get("eyes") == "predator" else (60, 40, 20)
    draw_box(hx + hr * 0.3, hy + hr * 0.15, -hr * 0.35, 0.025, 0.025, 0.02, eye_c)
    draw_box(hx + hr * 0.3, hy + hr * 0.15, hr * 0.25, 0.025, 0.025, 0.02, eye_c)
    glEnd()

    # Ears
    glBegin(GL_TRIANGLES)
    ear_style = cfg.get("ears", "pointed")
    if ear_style == "pointed":
        for dz in (-hr * 0.3, hr * 0.3):
            p = [(hx, hy + hr * 0.4, dz), (hx - hr * 0.2, hy + hr * 0.4, dz),
                 (hx - hr * 0.1, hy + hr * 0.8, dz)]
            for v in p:
                glColor3f(color[0] / 255, color[1] / 255, color[2] / 255)
                glVertex3f(*v)
    glEnd()

    # Tail
    tail = cfg.get("tail", "thin")
    if tail:
        glBegin(GL_QUADS)
        tw = 0.02 * sc
        tlen = 0.2 * sc if tail == "bushy" else 0.15 * sc
        wag = ws * 0.05
        draw_box(-bw / 2 - tlen, by + bh * 0.3, -tw + wag,
                 tlen, tw * (3 if tail == "bushy" else 1.5), tw * 2, _dk(color, 10))
        glEnd()


def draw_ungulate_3d(sc, color, ws, bob, cfg):
    """Deer, horse, cow — taller with neck and longer legs."""
    bw_r, bh_r = cfg.get("body_r", (1.0, 0.5))
    bw = 0.5 * sc * bw_r
    bh = 0.2 * sc * bh_r
    bd = 0.18 * sc
    by = 0.5 * sc + bob  # higher body (longer legs)
    swing = ws * 25
    lw = 0.04 * sc
    lh = 0.4 * sc  # taller legs

    # Legs
    for i, (lx, lz) in enumerate([(-bw * 0.35, -bd * 0.3), (-bw * 0.35, bd * 0.3),
                                    (bw * 0.35, -bd * 0.3), (bw * 0.35, bd * 0.3)]):
        _rotated_leg(lx, by, lz, lw, lh, _dk(color), swing if i % 2 == 0 else -swing)

    glBegin(GL_QUADS)
    # Body
    draw_box(-bw / 2, by, -bd / 2, bw, bh, bd, color)

    # Neck
    nx = bw / 3
    draw_box(nx, by + bh * 0.5, -0.04 * sc, 0.08 * sc, 0.25 * sc, 0.08 * sc, color)

    # Head (elongated)
    hx = nx + 0.04 * sc
    hy = by + bh + 0.2 * sc
    draw_box(hx - 0.03, hy, -0.04 * sc, 0.15 * sc, 0.08 * sc, 0.08 * sc, _lt(color, 10))
    # Nose
    draw_box(hx + 0.12 * sc, hy + 0.02, -0.02, 0.03, 0.03, 0.04, _dk(color, 25))
    # Eye
    draw_box(hx + 0.05, hy + 0.06, -0.045 * sc, 0.02, 0.02, 0.015, (50, 35, 20))
    draw_box(hx + 0.05, hy + 0.06, 0.03 * sc, 0.02, 0.02, 0.015, (50, 35, 20))

    # Tail
    tail = cfg.get("tail", "thin")
    tw = 0.015 * sc
    tlen = 0.15 * sc
    draw_box(-bw / 2 - tlen, by + bh * 0.4, -tw,
             tlen, tw * (4 if tail == "bushy" else 2), tw * 2, _dk(color, 10))
    glEnd()

    # Antlers/horns
    extras = cfg.get("extras", [])
    if "antlers" in extras:
        glBegin(GL_QUADS)
        for dz in (-0.03, 0.03):
            draw_box(hx + 0.02, hy + 0.08, dz, 0.015, 0.15 * sc, 0.015, (140, 120, 80))
            draw_box(hx + 0.04, hy + 0.15, dz + (0.03 if dz > 0 else -0.03),
                     0.01, 0.08 * sc, 0.01, (130, 110, 70))
        glEnd()
    if "horns" in extras:
        glBegin(GL_QUADS)
        for dz in (-0.03, 0.03):
            draw_box(hx + 0.02, hy + 0.06, dz, 0.015, 0.1 * sc, 0.015, (200, 190, 160))
        glEnd()
    if "mane" in extras:
        glBegin(GL_QUADS)
        draw_box(nx - 0.02, by + bh * 0.6, -0.06 * sc,
                 0.12 * sc, 0.15 * sc, 0.12 * sc, _dk(color, 12))
        glEnd()


def draw_bear_3d(sc, color, ws, bob, cfg):
    """Bear — massive rounded body, thick legs."""
    bw, bh, bd = 0.4 * sc, 0.35 * sc, 0.3 * sc
    by = 0.3 * sc + bob
    swing = ws * 20
    lw, lh = 0.08 * sc, 0.25 * sc

    for i, (lx, lz) in enumerate([(-bw * 0.4, -bd * 0.3), (-bw * 0.4, bd * 0.3),
                                    (bw * 0.4, -bd * 0.3), (bw * 0.4, bd * 0.3)]):
        _rotated_leg(lx, by, lz, lw, lh, _dk(color), swing if i % 2 == 0 else -swing)

    glBegin(GL_QUADS)
    draw_box(-bw / 2, by, -bd / 2, bw, bh, bd, color)
    # Belly
    draw_box(-bw / 3, by - 0.01, -bd / 3, bw * 2 / 3, 0.01, bd * 2 / 3, _lt(color, 8))
    # Head
    hr = 0.12 * sc
    draw_box(bw / 2 - 0.02, by + bh * 0.3, -hr / 2, hr * 1.2, hr, hr, _lt(color, 8))
    # Snout
    draw_box(bw / 2 + hr * 0.8, by + bh * 0.4, -hr * 0.2,
             hr * 0.5, hr * 0.4, hr * 0.4, _lt(color, 20))
    draw_box(bw / 2 + hr * 1.2, by + bh * 0.5, -0.02, 0.03, 0.03, 0.04, (30, 30, 30))
    # Ears
    for dz in (-hr * 0.35, hr * 0.35):
        draw_box(bw / 2, by + bh * 0.3 + hr * 0.8, dz - 0.02,
                 0.04, 0.04, 0.04, color)
    # Eyes
    draw_box(bw / 2 + hr * 0.5, by + bh * 0.5, -hr * 0.3, 0.02, 0.02, 0.02, (30, 30, 30))
    draw_box(bw / 2 + hr * 0.5, by + bh * 0.5, hr * 0.2, 0.02, 0.02, 0.02, (30, 30, 30))
    glEnd()


def draw_humanoid_3d(sc, color, ws, bob, cfg):
    """Goblins, orcs, skeletons — bipedal with rotating limbs."""
    tw, th, td = 0.18 * sc, 0.28 * sc, 0.12 * sc
    bulky = cfg.get("bulky", False)
    if bulky:
        tw *= 1.3
        td *= 1.2
    ty = 0.4 * sc + bob
    swing = ws * 28
    lw, lh = 0.06 * sc, 0.32 * sc
    aw, ah = 0.05 * sc, 0.25 * sc

    # Legs (swing front-to-back for bipeds = rotate around X)
    for i, dx in enumerate((-0.05 * sc, 0.05 * sc)):
        _rotated_leg(dx, ty, 0, lw, lh, _dk(color), swing if i == 0 else -swing, axis='x')

    # Arms (swing front-to-back = rotate around X)
    arm_swing = -swing * 0.7
    for i, dx in enumerate((-tw / 2 - aw / 2, tw / 2 + aw / 2)):
        glPushMatrix()
        glTranslatef(dx, ty + th * 0.8, 0)
        glRotatef(arm_swing if i == 0 else -arm_swing, 1, 0, 0)
        glBegin(GL_QUADS)
        body_c = (200, 195, 180) if cfg.get("bony") else _lt(color, 5)
        draw_box(-aw / 2, -ah, -aw / 2, aw, ah, aw, body_c)
        if cfg.get("claws"):
            for ci in range(3):
                dz = (ci - 1) * aw * 0.4
                draw_box(-0.008, -ah - 0.04 * sc, dz - 0.005,
                         0.016, 0.04 * sc, 0.01, (200, 200, 190))
        glEnd()
        glPopMatrix()

    glBegin(GL_QUADS)
    # Torso
    torso_c = color
    if cfg.get("bony"):
        torso_c = (190, 185, 170)
    draw_box(-tw / 2, ty, -td / 2, tw, th, td, torso_c)

    # Head
    hr = 0.09 * sc
    hx, hy = 0, ty + th + hr * 0.1
    head_c = _lt(torso_c, 15)
    draw_box(-hr, hy, -hr * 0.8, hr * 2, hr * 1.6, hr * 1.6, head_c)
    # Eyes
    eye_style = cfg.get("eyes", "predator")
    ec = (200, 50, 40) if eye_style == "predator" else (180, 200, 80) if eye_style in ("undead", "glowing") else (50, 40, 30)
    draw_box(-hr * 0.4, hy + hr * 0.8, -hr * 0.85, 0.025, 0.025, 0.02, ec)
    draw_box(hr * 0.2, hy + hr * 0.8, -hr * 0.85, 0.025, 0.025, 0.02, ec)

    # Ears
    if cfg.get("ears") == "pointed":
        for dz in (-hr * 0.7, hr * 0.7):
            draw_box(dz - 0.015, hy + hr * 1.2, -hr * 0.3, 0.03, 0.06 * sc, 0.02, color)

    # Tusks
    if "tusks" in cfg.get("extras", []):
        for dz in (-hr * 0.3, hr * 0.3):
            draw_box(dz - 0.008, hy + hr * 0.3, -hr * 0.9, 0.016, 0.05 * sc, 0.016, (220, 210, 190))

    # Cape (vampire)
    if cfg.get("cape"):
        draw_box(-tw / 2 - 0.02, ty - lh * 0.3, td / 2,
                 tw + 0.04, th + lh * 0.3, 0.02, (60, 20, 30))
    glEnd()


def draw_large_3d(sc, color, ws, bob, cfg):
    """Ogre, troll, minotaur — imposing size."""
    tw, th, td = 0.3 * sc, 0.4 * sc, 0.25 * sc
    ty = 0.55 * sc + bob
    swing = ws * 22
    lw, lh = 0.1 * sc, 0.45 * sc
    aw, ah = 0.08 * sc, 0.35 * sc

    for i, dx in enumerate((-0.08 * sc, 0.08 * sc)):
        _rotated_leg(dx, ty, 0, lw, lh, _dk(color), swing if i == 0 else -swing, axis='x')

    for i, dx in enumerate((-tw / 2 - aw / 2, tw / 2 + aw / 2)):
        glPushMatrix()
        glTranslatef(dx, ty + th * 0.75, 0)
        glRotatef((-swing * 0.6) if i == 0 else (swing * 0.6), 1, 0, 0)
        glBegin(GL_QUADS)
        draw_box(-aw / 2, -ah, -aw / 2, aw, ah, aw, _lt(color, 5))
        glEnd()
        glPopMatrix()

    glBegin(GL_QUADS)
    draw_box(-tw / 2, ty, -td / 2, tw, th, td, color)
    # Head
    hr = 0.12 * sc
    draw_box(-hr, ty + th, -hr * 0.8, hr * 2, hr * 1.8, hr * 1.6, _lt(color, 10))
    draw_box(-hr * 0.4, ty + th + hr * 1.0, -hr * 0.85, 0.03, 0.03, 0.02, (200, 50, 40))
    draw_box(hr * 0.2, ty + th + hr * 1.0, -hr * 0.85, 0.03, 0.03, 0.02, (200, 50, 40))
    # Horns (minotaur)
    if "horns" in cfg.get("extras", []):
        for dz in (-hr * 0.6, hr * 0.6):
            draw_box(dz - 0.015, ty + th + hr * 1.5, -hr * 0.3,
                     0.03, 0.12 * sc, 0.03, (200, 190, 160))
    glEnd()


def draw_winged_3d(sc, color, ws, bob, cfg):
    """Dragon, wyvern, griffin — body + wing triangles."""
    bw, bh, bd = 0.4 * sc, 0.3 * sc, 0.25 * sc
    by = 0.35 * sc + bob
    swing = ws * 25

    # Legs
    lw, lh = 0.06 * sc, 0.3 * sc
    for i, (lx, lz) in enumerate([(-bw * 0.3, -bd * 0.2), (-bw * 0.3, bd * 0.2),
                                    (bw * 0.3, -bd * 0.2), (bw * 0.3, bd * 0.2)]):
        _rotated_leg(lx, by, lz, lw, lh, _dk(color), swing if i % 2 == 0 else -swing)

    glBegin(GL_QUADS)
    draw_box(-bw / 2, by, -bd / 2, bw, bh, bd, color)
    # Head + jaws
    hr = 0.1 * sc
    draw_box(bw / 2, by + bh * 0.3, -hr / 2, hr * 1.5, hr, hr, _lt(color, 10))
    if cfg.get("jaws") or cfg.get("beak"):
        draw_box(bw / 2 + hr * 1.2, by + bh * 0.35, -hr * 0.2,
                 hr * 0.6, hr * 0.3, hr * 0.4, _lt(color, 15))
    # Tail
    if cfg.get("tail"):
        for i in range(4):
            t = (i + 1) / 5
            draw_box(-bw / 2 - t * 0.3 * sc, by + bh * 0.3,
                     -0.02 + ws * 0.02 * (i % 2),
                     0.06 * sc, 0.05 * sc * (1 - t * 0.3), 0.04, _dk(color, 5 + i * 3))
    glEnd()

    # Wings (triangles)
    flap = ws * 20
    wing_span = 0.5 * sc if cfg.get("wings") == "large" else 0.3 * sc
    glBegin(GL_TRIANGLES)
    for dz_sign in (-1, 1):
        wc = _dk(color, 15)
        r, g, b = wc[0] / 255, wc[1] / 255, wc[2] / 255
        glColor3f(r, g, b)
        # Wing triangle
        base_z = dz_sign * bd * 0.3
        tip_z = dz_sign * (bd * 0.3 + wing_span)
        tip_y = by + bh + 0.1 * sc + math.radians(flap * dz_sign) * sc * 0.3
        glVertex3f(0, by + bh * 0.8, base_z)
        glVertex3f(-bw * 0.3, by + bh * 0.5, base_z)
        glVertex3f(0, tip_y, tip_z)
    # Eyes
    ec = (200, 50, 40)
    draw_sphere_approx(bw / 2 + hr * 0.5, by + bh * 0.5, -hr * 0.3, 0.02, ec, 4)
    draw_sphere_approx(bw / 2 + hr * 0.5, by + bh * 0.5, hr * 0.2, 0.02, ec, 4)
    glEnd()


def draw_ethereal_3d(sc, color, ws, bob, cfg):
    """Wraith, shadow — translucent floating form."""
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    bob_e = math.sin(ws * 0.8) * 0.12 * sc
    by = 0.2 * sc + bob_e
    r, g, b = color[0] / 255, color[1] / 255, color[2] / 255

    # Main body — tapered column of stacked boxes, visible from all sides
    # Wider at shoulders, narrowing to a wispy tattered bottom
    layers = 6
    for i in range(layers):
        t = i / layers  # 0=top, 1=bottom
        alpha = 0.35 - t * 0.15  # top more opaque, bottom fades
        w = (0.1 + t * 0.06) * sc  # widens toward bottom
        d = (0.08 + t * 0.04) * sc
        h = 0.08 * sc
        ly = by + 0.45 * sc - i * h  # stack top-to-bottom
        # Slight sway per layer
        sway_x = math.sin(ws * 1.2 + i * 0.8) * 0.015 * sc * (i + 1)
        sway_z = math.cos(ws * 0.9 + i * 1.1) * 0.01 * sc * (i + 1)

        glBegin(GL_QUADS)
        glColor4f(r, g, b, alpha)
        # All 4 sides + top face so it's visible from every angle
        x0, x1 = -w + sway_x, w + sway_x
        z0, z1 = -d + sway_z, d + sway_z
        y0, y1 = ly, ly + h
        # Front
        glVertex3f(x0, y0, z0); glVertex3f(x1, y0, z0)
        glVertex3f(x1, y1, z0); glVertex3f(x0, y1, z0)
        # Back
        glVertex3f(x1, y0, z1); glVertex3f(x0, y0, z1)
        glVertex3f(x0, y1, z1); glVertex3f(x1, y1, z1)
        # Left
        glVertex3f(x0, y0, z1); glVertex3f(x0, y0, z0)
        glVertex3f(x0, y1, z0); glVertex3f(x0, y1, z1)
        # Right
        glVertex3f(x1, y0, z0); glVertex3f(x1, y0, z1)
        glVertex3f(x1, y1, z1); glVertex3f(x1, y1, z0)
        # Top (only on topmost layer)
        if i == 0:
            glColor4f(r, g, b, alpha + 0.1)
            glVertex3f(x0, y1, z0); glVertex3f(x1, y1, z0)
            glVertex3f(x1, y1, z1); glVertex3f(x0, y1, z1)
        glEnd()

    # Tattered wisps trailing below (thin hanging strips)
    glBegin(GL_QUADS)
    for j in range(5):
        wx = (j / 4 - 0.5) * 0.2 * sc
        wz = math.sin(j * 2.1) * 0.06 * sc
        wisp_h = (0.08 + math.sin(ws * 1.5 + j) * 0.03) * sc
        wisp_w = 0.015 * sc
        wy = by + 0.45 * sc - layers * 0.08 * sc
        sway = math.sin(ws * 1.5 + j * 1.3) * 0.02 * sc
        glColor4f(r, g, b, 0.15)
        glVertex3f(wx - wisp_w + sway, wy, wz)
        glVertex3f(wx + wisp_w + sway, wy, wz)
        glVertex3f(wx + wisp_w + sway * 2, wy - wisp_h, wz)
        glVertex3f(wx - wisp_w + sway * 2, wy - wisp_h, wz)
    glEnd()

    # Hood/head shape — darker, more opaque at top
    head_w = 0.09 * sc
    head_h = 0.1 * sc
    head_y = by + 0.48 * sc
    glBegin(GL_QUADS)
    glColor4f(r * 0.6, g * 0.6, b * 0.6, 0.5)
    draw_box(-head_w, head_y, -head_w * 0.8, head_w * 2, head_h, head_w * 1.6,
             (int(color[0] * 0.6), int(color[1] * 0.6), int(color[2] * 0.6)))
    glEnd()

    # Glowing eyes
    glBegin(GL_TRIANGLES)
    eye_y = head_y + head_h * 0.4
    draw_sphere_approx(-0.035 * sc, eye_y, -head_w * 0.8 - 0.005,
                        0.018 * sc, (150, 200, 255), 5)
    draw_sphere_approx(0.035 * sc, eye_y, -head_w * 0.8 - 0.005,
                        0.018 * sc, (150, 200, 255), 5)
    glEnd()

    glDisable(GL_BLEND)


def draw_arachnid_3d(sc, color, ws, bob, cfg):
    """Spider, scorpion — body + rotating legs."""
    br = 0.12 * sc
    by = 0.1 * sc + bob

    glBegin(GL_QUADS)
    # Body
    draw_box(-br, by, -br, br * 2, br * 1.2, br * 2, color)
    # Abdomen
    abd = br * 1.3
    draw_box(-abd - br * 0.5, by - 0.01, -abd, abd * 2, abd * 1.5, abd * 2, _dk(color, 10))
    # Eyes
    for dz in (-br * 0.4, 0, br * 0.4):
        draw_box(br * 0.7, by + br * 0.8, dz - 0.01, 0.025, 0.025, 0.02, (200, 40, 40))
    glEnd()

    # Legs — 4 pairs, placed explicitly on left/right sides of body
    num = cfg.get("legs", 8)
    pairs = num // 2
    leg_w = 0.018
    leg_upper = 0.15 * sc
    leg_lower = 0.12 * sc
    dark_leg = _dk(color, 12)
    dark_foot = _dk(color, 25)

    glBegin(GL_QUADS)
    for i in range(pairs):
        # Spread along body X axis
        t = (i / max(1, pairs - 1) - 0.5) * br * 3
        phase = ws * 0.04 * (1 if i % 2 == 0 else -1)

        for side in (-1, 1):
            # Hip position: on the side of the body
            hx = t
            hy = by + br * 0.3
            hz = side * br * 1.1

            # Upper leg goes outward (along Z) and down (along -Y)
            knee_x = hx + phase
            knee_y = hy - leg_upper * 0.5
            knee_z = hz + side * leg_upper * 0.7

            # Lower leg goes further out and down to ground
            foot_x = knee_x - phase * 0.5
            foot_y = 0.0  # touches ground
            foot_z = knee_z + side * leg_lower * 0.4

            # Draw upper leg as a thin box from hip to knee
            draw_box(min(hx, knee_x) - leg_w, min(hy, knee_y),
                     min(hz, knee_z) - leg_w,
                     abs(knee_x - hx) + leg_w * 2,
                     abs(knee_y - hy) + leg_w,
                     abs(knee_z - hz) + leg_w * 2, dark_leg)

            # Draw lower leg from knee to foot
            draw_box(min(knee_x, foot_x) - leg_w, min(knee_y, foot_y),
                     min(knee_z, foot_z) - leg_w,
                     abs(foot_x - knee_x) + leg_w * 2,
                     abs(foot_y - knee_y) + leg_w,
                     abs(foot_z - knee_z) + leg_w * 2, dark_foot)
    glEnd()

    # Tail sting (scorpion)
    if cfg.get("tail_sting"):
        glBegin(GL_QUADS)
        for i in range(4):
            t = (i + 1) / 5
            draw_box(-abd - br * 0.5 - t * 0.2 * sc, by + t * 0.3 * sc,
                     -0.02, 0.04, 0.04, 0.04, color)
        draw_box(-abd - br * 0.5 - 0.22 * sc, by + 0.35 * sc,
                 -0.015, 0.03, 0.03, 0.03, (200, 50, 50))
        glEnd()


def draw_bird_3d(sc, color, ws, bob, cfg):
    """Birds — body + wing flap + beak."""
    br = 0.1 * sc
    by = 0.15 * sc + bob
    flap = ws * 25

    glBegin(GL_QUADS)
    # Body
    draw_box(-br, by, -br * 0.7, br * 2, br * 1.5, br * 1.4, color)
    # Breast
    draw_box(-br * 0.5, by - 0.01, -br * 0.5, br, 0.01, br, _lt(color, 12))
    # Head
    hr = br * 0.7
    draw_box(br * 0.5, by + br * 1.0, -hr / 2, hr * 1.2, hr, hr, _lt(color, 10))
    # Beak
    beak = cfg.get("beak", "pointed")
    if beak in ("hooked", "pointed"):
        draw_box(br * 0.5 + hr * 1.0, by + br * 1.1, -0.015,
                 hr * 0.8, hr * 0.3, 0.03, (200, 170, 50))
    # Eye
    draw_box(br * 0.5 + hr * 0.5, by + br * 1.3, -hr * 0.55,
             0.015, 0.015, 0.01, (30, 30, 30))
    # Tail
    draw_box(-br * 1.5, by + br * 0.3, -br * 0.3, br * 0.8, br * 0.15, br * 0.6,
             _dk(color, 15))
    glEnd()

    # Wings (flapping triangles)
    glBegin(GL_TRIANGLES)
    wc = _dk(color, 10)
    r, g, b = wc[0] / 255, wc[1] / 255, wc[2] / 255
    wing_w = 0.25 * sc if cfg.get("size") == "large" else 0.15 * sc
    for dz in (-1, 1):
        tip_y = by + br * 1.5 + math.radians(flap * dz) * sc * 0.2
        glColor3f(r, g, b)
        glVertex3f(0, by + br * 1.0, dz * br * 0.5)
        glVertex3f(-br * 0.5, by + br * 0.5, dz * br * 0.5)
        glVertex3f(0, tip_y, dz * (br * 0.5 + wing_w))
    glEnd()

    # Legs
    glBegin(GL_QUADS)
    swing_l = ws * 0.03
    for dz in (-br * 0.2, br * 0.2):
        draw_box(dz - 0.008, 0, -0.008 + swing_l, 0.016, by, 0.016, (180, 150, 80))
    glEnd()


def draw_serpent_3d(sc, color, ws, bob, cfg):
    """Snake — chain of segments."""
    segs = max(6, int(sc * 8))
    glBegin(GL_QUADS)
    for i in range(segs):
        t = i / segs
        px = (t - 0.5) * 0.6 * sc
        py = 0.03 * sc + bob * 0.5
        pz = math.sin(t * 6 + ws * 3) * 0.08 * sc
        r = 0.025 * sc * (1.0 - t * 0.4)
        draw_box(px - r, py, pz - r, r * 2, r * 2, r * 2, color)
    # Head
    draw_box(-0.33 * sc, 0.04 * sc, math.sin(ws * 3) * 0.05 * sc - 0.03,
             0.05 * sc, 0.04 * sc, 0.06 * sc, _lt(color, 12))
    draw_box(-0.35 * sc, 0.06 * sc, -0.015, 0.015, 0.015, 0.01, (200, 50, 40))
    glEnd()
