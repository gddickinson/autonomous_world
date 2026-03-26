"""3D pose rendering — body positions for different NPC actions."""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
from OpenGL.GL import *
from viewers.gl_viewer_base import draw_box, draw_sphere_approx

SKIN = {
    "human": (210, 185, 155), "elf": (220, 205, 175), "dwarf": (195, 165, 130),
    "halfling": (215, 190, 155), "half-orc": (140, 160, 120), "orc": (120, 145, 100),
}
SIZE = {"halfling": 0.7, "gnome": 0.7, "dwarf": 0.85, "half-orc": 1.15, "orc": 1.2}
_ARMORED = {"Fighter", "Paladin", "Barbarian", "Guard", "Soldier", "Knight"}


def _dk(c, a=20):
    return (max(0, c[0] - a), max(0, c[1] - a), max(0, c[2] - a))


def _dims(sc):
    """Standard body dimensions scaled by race."""
    return {
        "tw": 0.2 * sc, "th": 0.3 * sc, "td": 0.12 * sc,
        "aw": 0.055 * sc, "ah": 0.22 * sc,
        "lw": 0.06 * sc, "lh": 0.32 * sc,
        "head_r": 0.09 * sc,
    }


def draw_standing_3d(sc, color, skin, torso_c, walk_phase=0):
    """Default standing pose with optional walk animation."""
    d = _dims(sc)
    swing = math.sin(walk_phase) * 30 if walk_phase else 0
    ty = d["lh"] + 0.02

    # Legs
    for i, dx in enumerate((-0.05 * sc, 0.05 * sc)):
        glPushMatrix()
        glTranslatef(dx, ty, 0)
        glRotatef(swing if i == 0 else -swing, 1, 0, 0)
        glBegin(GL_QUADS)
        draw_box(-d["lw"] / 2, -d["lh"], -d["lw"] / 2, d["lw"], d["lh"], d["lw"], _dk(color))
        glEnd()
        glPopMatrix()

    glBegin(GL_QUADS)
    draw_box(-d["tw"] / 2, ty, -d["td"] / 2, d["tw"], d["th"], d["td"], torso_c)
    glEnd()

    # Arms
    arm_swing = -swing * 0.7
    for i, dx in enumerate((-d["tw"] / 2 - d["aw"] / 2, d["tw"] / 2 + d["aw"] / 2)):
        glPushMatrix()
        glTranslatef(dx, ty + d["th"] * 0.8, 0)
        glRotatef(arm_swing if i == 0 else -arm_swing, 1, 0, 0)
        glBegin(GL_QUADS)
        draw_box(-d["aw"] / 2, -d["ah"], -d["aw"] / 2, d["aw"], d["ah"], d["aw"], skin)
        glEnd()
        glPopMatrix()

    # Head
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, ty + d["th"] + d["head_r"] * 0.6, 0, d["head_r"], skin, 7)
    glEnd()


def draw_lying_3d(sc, color, skin, torso_c):
    """Lying flat on back — built directly as horizontal geometry, no rotation."""
    d = _dims(sc)
    ground_y = 0.04  # slightly above ground
    body_h = d["td"]  # thickness when lying flat

    glBegin(GL_QUADS)
    # Torso (flat on ground — width along X, thickness along Y, length along Z)
    draw_box(-d["tw"] / 2, ground_y, -d["th"] / 2,
             d["tw"], body_h, d["th"], torso_c)

    # Legs (extend along +Z from torso, flat on ground)
    for dx in (-0.03 * sc, 0.03 * sc):
        draw_box(dx - d["lw"] / 2, ground_y, d["th"] / 2,
                 d["lw"], d["lw"], d["lh"], _dk(color))
    # Feet
    for dx in (-0.03 * sc, 0.03 * sc):
        draw_box(dx - d["lw"] / 2 - 0.005, ground_y, d["th"] / 2 + d["lh"],
                 d["lw"] + 0.01, d["lw"] + 0.01, 0.02, _dk(color, 30))

    # Arms (along sides, flat on ground, extend along Z)
    draw_box(-d["tw"] / 2 - d["aw"], ground_y, -d["th"] / 4,
             d["aw"], d["aw"], d["ah"] * 0.7, skin)
    draw_box(d["tw"] / 2, ground_y, -d["th"] / 4,
             d["aw"], d["aw"], d["ah"] * 0.7, skin)
    glEnd()

    # Head (at -Z end, resting on ground)
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, ground_y + d["head_r"] * 0.8,
                        -d["th"] / 2 - d["head_r"] * 0.6,
                        d["head_r"], skin, 6)
    glEnd()


def draw_sitting_3d(sc, color, skin, torso_c):
    """Sitting — torso upright, upper legs forward (-Z), lower legs hanging down."""
    d = _dims(sc)
    seat_y = 0.15 * sc

    # Upper legs: rotate forward from hip (around X axis, 90 degrees)
    for dx in (-0.04 * sc, 0.04 * sc):
        glPushMatrix()
        glTranslatef(dx, seat_y, 0)
        glRotatef(90, 1, 0, 0)  # rotate leg forward (along -Z)
        glBegin(GL_QUADS)
        draw_box(-d["lw"] / 2, -d["lh"] * 0.5, -d["lw"] / 2,
                 d["lw"], d["lh"] * 0.5, d["lw"], _dk(color))
        glEnd()
        # Lower leg hangs straight down from knee
        glTranslatef(0, -d["lh"] * 0.5, 0)
        glRotatef(-90, 1, 0, 0)  # rotate back to vertical
        glBegin(GL_QUADS)
        draw_box(-d["lw"] / 2, -d["lh"] * 0.45, -d["lw"] / 2,
                 d["lw"], d["lh"] * 0.45, d["lw"], _dk(color, 25))
        # Foot
        draw_box(-d["lw"] / 2 - 0.005, -d["lh"] * 0.45 - 0.02, -d["lw"] / 2,
                 d["lw"] + 0.01, 0.02, d["lw"] + 0.01, _dk(color, 35))
        glEnd()
        glPopMatrix()

    glBegin(GL_QUADS)
    # Torso upright
    draw_box(-d["tw"] / 2, seat_y, -d["td"] / 2, d["tw"], d["th"], d["td"], torso_c)
    # Arms resting on thighs
    draw_box(-d["tw"] / 2 - d["aw"], seat_y + d["th"] * 0.2, -d["td"] / 2 - d["aw"],
             d["aw"], d["ah"] * 0.5, d["aw"], skin)
    draw_box(d["tw"] / 2, seat_y + d["th"] * 0.2, -d["td"] / 2 - d["aw"],
             d["aw"], d["ah"] * 0.5, d["aw"], skin)
    glEnd()
    # Head
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, seat_y + d["th"] + d["head_r"] * 0.6, 0, d["head_r"], skin, 7)
    glEnd()


def draw_kneeling_3d(sc, color, skin, torso_c):
    """Kneeling — one knee down, arms reaching to ground."""
    d = _dims(sc)
    knee_y = 0.05

    glBegin(GL_QUADS)
    # Kneeling leg (folded underneath)
    draw_box(-0.06 * sc, 0, -d["lw"] / 2, d["lw"] * 2, d["lw"], d["lw"], _dk(color))
    # Other leg (knee forward)
    draw_box(0.04 * sc, 0, d["lw"] / 2, d["lw"], d["lh"] * 0.5, d["lw"], _dk(color, 25))
    # Torso (lower than standing)
    ty = d["lh"] * 0.35
    draw_box(-d["tw"] / 2, ty, -d["td"] / 2, d["tw"], d["th"], d["td"], torso_c)
    glEnd()
    # Arms reaching down
    for i, dx in enumerate((-d["tw"] / 2 - d["aw"] / 2, d["tw"] / 2 + d["aw"] / 2)):
        glPushMatrix()
        glTranslatef(dx, ty + d["th"] * 0.7, 0)
        glRotatef(40, 1, 0, 0)  # angle forward-down
        glBegin(GL_QUADS)
        draw_box(-d["aw"] / 2, -d["ah"], -d["aw"] / 2, d["aw"], d["ah"], d["aw"], skin)
        glEnd()
        glPopMatrix()
    # Head
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, ty + d["th"] + d["head_r"] * 0.5, 0, d["head_r"], skin, 7)
    glEnd()


def draw_working_3d(sc, color, skin, torso_c, phase=0):
    """Working — standing, right arm swinging tool."""
    d = _dims(sc)
    ty = d["lh"] + 0.02
    arm_angle = math.sin(phase * 4) * 50  # swing up and down

    # Legs (standing)
    glBegin(GL_QUADS)
    for dx in (-0.05 * sc, 0.05 * sc):
        draw_box(dx - d["lw"] / 2, 0, -d["lw"] / 2, d["lw"], d["lh"], d["lw"], _dk(color))
    draw_box(-d["tw"] / 2, ty, -d["td"] / 2, d["tw"], d["th"], d["td"], torso_c)
    glEnd()

    # Left arm (at side)
    glPushMatrix()
    glTranslatef(-d["tw"] / 2 - d["aw"] / 2, ty + d["th"] * 0.8, 0)
    glBegin(GL_QUADS)
    draw_box(-d["aw"] / 2, -d["ah"], -d["aw"] / 2, d["aw"], d["ah"], d["aw"], skin)
    glEnd()
    glPopMatrix()

    # Right arm (swinging tool)
    glPushMatrix()
    glTranslatef(d["tw"] / 2 + d["aw"] / 2, ty + d["th"] * 0.8, 0)
    glRotatef(arm_angle - 30, 1, 0, 0)
    glBegin(GL_QUADS)
    draw_box(-d["aw"] / 2, -d["ah"], -d["aw"] / 2, d["aw"], d["ah"], d["aw"], skin)
    # Tool (axe/hammer at hand)
    draw_box(-0.01, -d["ah"] - 0.15 * sc, -0.015, 0.02, 0.15 * sc, 0.03, (140, 140, 150))
    draw_box(-0.03, -d["ah"] - 0.15 * sc, -0.02, 0.06, 0.04, 0.04, (120, 120, 130))
    glEnd()
    glPopMatrix()

    # Head
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, ty + d["th"] + d["head_r"] * 0.6, 0, d["head_r"], skin, 7)
    glEnd()


def draw_combat_3d(sc, color, skin, torso_c, cls=""):
    """Combat stance — wide legs, weapon raised."""
    d = _dims(sc)
    ty = d["lh"] * 0.9

    # Wide stance legs
    for i, dx in enumerate((-0.08 * sc, 0.08 * sc)):
        glPushMatrix()
        glTranslatef(dx, ty, 0)
        glRotatef(8 if i == 0 else -8, 0, 0, 1)
        glBegin(GL_QUADS)
        draw_box(-d["lw"] / 2, -d["lh"], -d["lw"] / 2, d["lw"], d["lh"], d["lw"], _dk(color))
        glEnd()
        glPopMatrix()

    glBegin(GL_QUADS)
    draw_box(-d["tw"] / 2, ty, -d["td"] / 2, d["tw"], d["th"], d["td"], torso_c)
    glEnd()

    # Left arm (guard/shield)
    glPushMatrix()
    glTranslatef(-d["tw"] / 2 - d["aw"] / 2, ty + d["th"] * 0.8, 0)
    glRotatef(30, 1, 0, 0)
    glBegin(GL_QUADS)
    draw_box(-d["aw"] / 2, -d["ah"], -d["aw"] / 2, d["aw"], d["ah"], d["aw"], skin)
    if cls in _ARMORED:
        draw_box(-d["aw"], -d["ah"] * 0.8, -0.06 * sc,
                 0.02, 0.12 * sc, 0.12 * sc, (140, 100, 50))
    glEnd()
    glPopMatrix()

    # Right arm (weapon raised)
    glPushMatrix()
    glTranslatef(d["tw"] / 2 + d["aw"] / 2, ty + d["th"] * 0.8, 0)
    glRotatef(-40, 1, 0, 0)
    glBegin(GL_QUADS)
    draw_box(-d["aw"] / 2, -d["ah"], -d["aw"] / 2, d["aw"], d["ah"], d["aw"], skin)
    # Sword
    draw_box(-0.01, -d["ah"] - 0.01, -0.3 * sc, 0.02, 0.02, 0.3 * sc, (195, 200, 215))
    draw_box(-0.035, -d["ah"] - 0.005, -0.01, 0.07, 0.02, 0.02, (160, 155, 140))
    glEnd()
    glPopMatrix()

    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, ty + d["th"] + d["head_r"] * 0.6, 0, d["head_r"], skin, 7)
    glEnd()


def draw_fishing_3d(sc, color, skin, torso_c, phase=0):
    """Fishing — sitting with legs forward, rod extended."""
    d = _dims(sc)
    seat_y = 0.12 * sc

    # Legs forward (same as sitting)
    for dx in (-0.04 * sc, 0.04 * sc):
        glPushMatrix()
        glTranslatef(dx, seat_y, 0)
        glRotatef(90, 1, 0, 0)
        glBegin(GL_QUADS)
        draw_box(-d["lw"] / 2, -d["lh"] * 0.5, -d["lw"] / 2,
                 d["lw"], d["lh"] * 0.5, d["lw"], _dk(color))
        glEnd()
        glTranslatef(0, -d["lh"] * 0.5, 0)
        glRotatef(-90, 1, 0, 0)
        glBegin(GL_QUADS)
        draw_box(-d["lw"] / 2, -d["lh"] * 0.4, -d["lw"] / 2,
                 d["lw"], d["lh"] * 0.4, d["lw"], _dk(color, 25))
        glEnd()
        glPopMatrix()

    glBegin(GL_QUADS)
    draw_box(-d["tw"] / 2, seat_y, -d["td"] / 2, d["tw"], d["th"], d["td"], torso_c)
    glEnd()

    # Right arm + fishing rod (angled forward-up)
    glPushMatrix()
    glTranslatef(d["tw"] / 2 + d["aw"] / 2, seat_y + d["th"] * 0.7, 0)
    glRotatef(-25 + math.sin(phase * 2) * 5, 1, 0, 0)
    glBegin(GL_QUADS)
    draw_box(-d["aw"] / 2, -d["ah"], -d["aw"] / 2, d["aw"], d["ah"], d["aw"], skin)
    # Rod (extends forward-up from hand)
    draw_box(-0.008, -d["ah"] - 0.02, -0.008, 0.016, 0.5 * sc, 0.016, (120, 90, 50))
    glEnd()
    glPopMatrix()

    # Left arm resting on thigh
    glBegin(GL_QUADS)
    draw_box(-d["tw"] / 2 - d["aw"], seat_y + d["th"] * 0.2, -d["td"] / 2 - d["aw"],
             d["aw"], d["ah"] * 0.5, d["aw"], skin)
    glEnd()

    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, seat_y + d["th"] + d["head_r"] * 0.5, 0, d["head_r"], skin, 7)
    glEnd()


def draw_alert_3d(sc, color, skin, torso_c):
    """Guard stance — upright, spear vertical."""
    d = _dims(sc)
    ty = d["lh"] + 0.02

    glBegin(GL_QUADS)
    # Legs together
    for dx in (-0.02 * sc, 0.02 * sc):
        draw_box(dx - d["lw"] / 2, 0, -d["lw"] / 2, d["lw"], d["lh"], d["lw"], _dk(color))
    draw_box(-d["tw"] / 2, ty, -d["td"] / 2, d["tw"], d["th"], d["td"], torso_c)
    # Arms at sides
    draw_box(-d["tw"] / 2 - d["aw"], ty + d["th"] * 0.3, -d["aw"] / 2,
             d["aw"], d["ah"], d["aw"], skin)
    draw_box(d["tw"] / 2, ty + d["th"] * 0.3, -d["aw"] / 2,
             d["aw"], d["ah"], d["aw"], skin)
    # Spear (vertical, in right hand)
    spear_x = d["tw"] / 2 + d["aw"] + 0.01
    draw_box(spear_x - 0.008, 0, -0.008,
             0.016, ty + d["th"] + 0.2 * sc, 0.016, (160, 150, 130))
    # Spear tip
    draw_box(spear_x - 0.015, ty + d["th"] + 0.2 * sc, -0.015,
             0.03, 0.06 * sc, 0.015, (180, 180, 190))
    glEnd()

    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, ty + d["th"] + d["head_r"] * 0.6, 0, d["head_r"], skin, 7)
    glEnd()


def draw_dead_3d(sc, color, skin):
    """Dead — skull and crossbones on ground."""
    bone_c = (210, 200, 180)
    # Crossbones (each bone in its own begin/end + matrix block)
    for angle in (30, -30):
        glPushMatrix()
        glTranslatef(0, 0.03, 0)
        glRotatef(angle, 0, 1, 0)
        glBegin(GL_QUADS)
        draw_box(-0.2 * sc, 0, -0.015, 0.4 * sc, 0.03, 0.03, bone_c)
        for dx in (-0.2 * sc, 0.2 * sc - 0.03):
            draw_box(dx, -0.01, -0.02, 0.04, 0.05, 0.04, bone_c)
        glEnd()
        glPopMatrix()
    # Skull
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, 0.12 * sc, 0, 0.08 * sc, bone_c, 6)
    draw_sphere_approx(-0.025 * sc, 0.13 * sc, -0.06 * sc, 0.02, (30, 25, 20), 4)
    draw_sphere_approx(0.025 * sc, 0.13 * sc, -0.06 * sc, 0.02, (30, 25, 20), 4)
    glEnd()


def draw_pose_3d(pose, name, prof, cls, race, color, phase=0):
    """Main dispatcher — draw the right 3D pose."""
    sc = SIZE.get(race, 1.0) if race else 1.0
    skin = SKIN.get(race, (210, 185, 155)) if race else (210, 185, 155)
    armored = (cls in _ARMORED) if cls else False
    torso_c = (170, 175, 185) if armored else color

    funcs = {
        "standing": lambda: draw_standing_3d(sc, color, skin, torso_c),
        "walking": lambda: draw_standing_3d(sc, color, skin, torso_c, phase),
        "lying": lambda: draw_lying_3d(sc, color, skin, torso_c),
        "sitting": lambda: draw_sitting_3d(sc, color, skin, torso_c),
        "kneeling": lambda: draw_kneeling_3d(sc, color, skin, torso_c),
        "working": lambda: draw_working_3d(sc, color, skin, torso_c, phase),
        "combat": lambda: draw_combat_3d(sc, color, skin, torso_c, cls or ""),
        "fishing": lambda: draw_fishing_3d(sc, color, skin, torso_c, phase),
        "alert": lambda: draw_alert_3d(sc, color, skin, torso_c),
        "dead": lambda: draw_dead_3d(sc, color, skin),
        "fleeing": lambda: draw_standing_3d(sc, color, skin, torso_c, phase * 1.6),
    }
    fn = funcs.get(pose, funcs["standing"])
    fn()
