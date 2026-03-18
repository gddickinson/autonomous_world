#!/usr/bin/env python3
"""3D NPC Viewer — NPCs as assembled 3D body parts with equipment.

Shows NPCs with head sphere, torso box, arms, legs, weapons, shields,
and staff/orbs for mages. Walk animation cycles limbs.

Controls:
  LEFT/RIGHT: cycle NPC preset
  Arrows: rotate/tilt camera    +/-: zoom
  SPACE: toggle walk animation
  F: toggle flee mode
  S: screenshot    Esc: quit
"""

import os, sys, math, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from OpenGL.GL import *

from viewers.gl_viewer_base import (
    init_viewer, setup_camera, draw_hud, draw_ground_grid,
    draw_box, draw_sphere_approx, handle_camera_keys, gl_color,
)

# ── Skin tones / sizes ──────────────────────────────────────────────────

SKIN = {
    "human": (210, 185, 155), "elf": (220, 205, 175), "dwarf": (195, 165, 130),
    "halfling": (215, 190, 155), "half-orc": (140, 160, 120), "orc": (120, 145, 100),
    "gnome": (210, 195, 165), "tiefling": (180, 130, 130), "goblin": (130, 150, 90),
    "dragonborn": (160, 170, 150), "goliath": (180, 170, 155),
}
SIZE = {
    "halfling": 0.7, "gnome": 0.7, "goblin": 0.7, "dwarf": 0.85,
    "half-orc": 1.15, "orc": 1.2, "dragonborn": 1.15, "goliath": 1.3,
}

PRESETS = [
    ("Human Fighter",   "Guard",     "Fighter",   "human",     (180, 60, 60)),
    ("Elf Wizard",      "Sage",      "Wizard",    "elf",       (60, 60, 180)),
    ("Dwarf Paladin",   "Knight",    "Paladin",   "dwarf",     (180, 160, 60)),
    ("Halfling Rogue",  "Thief",     "Rogue",     "halfling",  (100, 100, 100)),
    ("Half-Orc Barb",   "Mercenary", "Barbarian", "half-orc",  (140, 80, 60)),
    ("Gnome Bard",      "Performer", "Bard",      "gnome",     (180, 120, 180)),
    ("Tiefling Warlock", "Mystic",   "Warlock",   "tiefling",  (140, 60, 180)),
    ("Dragonborn Cleric","Priest",   "Cleric",    "dragonborn",(220, 200, 100)),
    ("Human Ranger",    "Ranger",    "Ranger",    "human",     (80, 140, 80)),
    ("Orc Soldier",     "Soldier",   "Fighter",   "orc",       (80, 110, 70)),
    ("Goliath Knight",  "Knight",    "Paladin",   "goliath",   (140, 130, 120)),
    ("Human Farmer",    "Farmer",    "Commoner",  "human",     (140, 120, 80)),
    ("Elf Druid",       "Herbalist", "Druid",     "elf",       (60, 160, 80)),
]

_MELEE = {"Fighter", "Paladin", "Barbarian", "Rogue", "Guard", "Soldier", "Knight", "Mercenary"}
_RANGED = {"Ranger", "Archer"}
_MAGE = {"Wizard", "Sorcerer", "Warlock", "Cleric", "Druid", "Bard"}
_ARMORED = {"Fighter", "Paladin", "Barbarian", "Guard", "Soldier", "Knight"}
_ORB = {"Wizard": (0.3, 0.5, 0.9), "Sorcerer": (0.8, 0.3, 0.8), "Warlock": (0.55, 0.2, 0.7),
        "Cleric": (0.9, 0.8, 0.4), "Druid": (0.3, 0.7, 0.3), "Bard": (0.8, 0.55, 0.8)}


def _draw_npc_3d(name, prof, cls, race, color, walk_phase, fleeing):
    """Draw a single NPC as 3D body parts with joint-based limb rotation."""
    sc = SIZE.get(race, 1.0)
    skin = SKIN.get(race, (210, 185, 155))
    armored = cls in _ARMORED or prof in _ARMORED
    torso_c = (170, 175, 185) if armored else color

    # Swing angle in degrees for glRotatef
    swing_deg = math.sin(walk_phase) * 35  # ~35 degree max swing
    if fleeing:
        swing_deg *= 1.6
    bob = abs(math.cos(walk_phase)) * 0.03 * sc

    tw, td = 0.3 * sc, 0.2 * sc
    th = 0.4 * sc
    ty = 0.45 * sc + bob

    # Limb dimensions
    aw, ah = 0.07 * sc, 0.3 * sc  # arm width, length
    lw, lh = 0.08 * sc, 0.38 * sc  # leg width, length

    # Joint positions
    l_hip_x, r_hip_x = -0.07 * sc, 0.07 * sc
    hip_y = ty  # bottom of torso
    l_shoulder_x = -tw / 2 - aw / 2
    r_shoulder_x = tw / 2 + aw / 2
    shoulder_y = ty + th * 0.85  # near top of torso

    leg_dark = (max(0, color[0] - 20), max(0, color[1] - 20), max(0, color[2] - 20))
    foot_dark = (max(0, color[0] - 35), max(0, color[1] - 35), max(0, color[2] - 35))

    # ── Legs (rotate from hips) ────────────────────────────────────
    # Left leg swings forward (+swing_deg rotation around X axis at hip)
    glPushMatrix()
    glTranslatef(l_hip_x, hip_y, 0)
    glRotatef(swing_deg, 1, 0, 0)  # rotate around X (biped front-to-back)
    glBegin(GL_QUADS)
    draw_box(-lw / 2, -lh, -lw / 2, lw, lh, lw, leg_dark)
    draw_box(-lw / 2 - 0.01, -lh - 0.04 * sc, -lw / 2, lw + 0.02, 0.04 * sc, lw, foot_dark)
    glEnd()
    glPopMatrix()

    # Right leg swings opposite
    glPushMatrix()
    glTranslatef(r_hip_x, hip_y, 0)
    glRotatef(-swing_deg, 1, 0, 0)
    glBegin(GL_QUADS)
    draw_box(-lw / 2, -lh, -lw / 2, lw, lh, lw, leg_dark)
    draw_box(-lw / 2 - 0.01, -lh - 0.04 * sc, -lw / 2, lw + 0.02, 0.04 * sc, lw, foot_dark)
    glEnd()
    glPopMatrix()

    # ── Torso (static) ─────────────────────────────────────────────
    glBegin(GL_QUADS)
    draw_box(-tw / 2, ty, -td / 2, tw, th, td, torso_c)
    glEnd()

    # ── Arms (rotate from shoulders) ──────────────────────────────
    arm_swing_deg = -swing_deg * 0.7  # arms swing opposite to legs
    if fleeing:
        # Arms raised: rotate backward (negative X rotation)
        l_arm_rot = -60 + math.sin(walk_phase * 2) * 15
        r_arm_rot = -60 - math.sin(walk_phase * 2) * 15
    else:
        l_arm_rot = arm_swing_deg
        r_arm_rot = -arm_swing_deg

    # Local hand offset (relative to shoulder, in arm's rotated space)
    hx, hy, hz = 0, -ah, 0  # hand is at bottom of arm

    # Left arm + equipment
    glPushMatrix()
    glTranslatef(l_shoulder_x, shoulder_y, 0)
    glRotatef(l_arm_rot, 1, 0, 0)
    glBegin(GL_QUADS)
    draw_box(-aw / 2, -ah, -aw / 2, aw, ah, aw, skin)
    # Shield (in front of hand, across body)
    if armored:
        s_thick = 0.03 * sc
        s_h = 0.18 * sc
        s_w = 0.15 * sc
        draw_box(hx - s_w * 0.2, hy - s_h * 0.2, hz - s_w * 0.6,
                 s_w, s_h, s_thick, (140, 100, 50))
        draw_box(hx - s_w * 0.2 - 0.006, hy - s_h * 0.2 - 0.006,
                 hz - s_w * 0.6 - 0.004,
                 s_w + 0.012, s_h + 0.012, 0.004, (110, 75, 35))
    # Bow (in left hand)
    if cls in _RANGED or prof in _RANGED:
        bow_w = 0.02 * sc
        bow_h = 0.26 * sc
        draw_box(hx - bow_w - 0.01, hy - bow_h * 0.3, hz - bow_w,
                 bow_w, bow_h, bow_w, (140, 100, 50))
        draw_box(hx + 0.005, hy - bow_h * 0.25, hz - 0.004,
                 0.004, bow_h * 0.6, 0.004, (200, 190, 170))
    glEnd()
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(hx, hy, hz, 0.035 * sc, skin, 4)
    glEnd()
    glPopMatrix()

    # Right arm + equipment
    glPushMatrix()
    glTranslatef(r_shoulder_x, shoulder_y, 0)
    glRotatef(r_arm_rot, 1, 0, 0)
    glBegin(GL_QUADS)
    draw_box(-aw / 2, -ah, -aw / 2, aw, ah, aw, skin)
    # Sword (extending forward from hand)
    if cls in _MELEE or prof in _MELEE:
        bw = 0.025 * sc
        blade_len = 0.38 * sc
        draw_box(hx - bw / 2, hy - bw, hz - blade_len,
                 bw, bw * 2, blade_len, (195, 200, 215))
        # Crossguard
        cg_w = 0.08 * sc
        draw_box(hx - cg_w / 2, hy - 0.012 * sc, hz - 0.012,
                 cg_w, 0.024 * sc, 0.024, (160, 155, 140))
        # Pommel
        draw_box(hx - 0.012, hy - 0.012, hz + 0.015,
                 0.024, 0.024, 0.035 * sc, (140, 120, 80))
    # Staff (extends from hand up and down)
    if cls in _MAGE:
        staff_w = 0.022 * sc
        # Staff below hand (toward ground)
        draw_box(hx - staff_w / 2, hy, hz - staff_w / 2,
                 staff_w, ah + 0.1 * sc, staff_w, (120, 90, 50))
        # Staff above hand (toward orb)
        draw_box(hx - staff_w / 2, hy + ah + 0.1 * sc, hz - staff_w / 2,
                 staff_w, 0.25 * sc, staff_w, (120, 90, 50))
    glEnd()
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(hx, hy, hz, 0.035 * sc, skin, 4)
    # Mage orb at staff top
    if cls in _ORB:
        orb_rgb = _ORB[cls]
        orb_c = (int(orb_rgb[0] * 255), int(orb_rgb[1] * 255), int(orb_rgb[2] * 255))
        draw_sphere_approx(hx, hy + ah + 0.35 * sc, hz, 0.045 * sc, orb_c, 6)
    glEnd()
    glPopMatrix()

    # ── Head (sphere, in world space) ──────────────────────────────
    head_r = 0.12 * sc
    head_y_pos = ty + th + head_r + bob
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, head_y_pos, 0, head_r, skin, 8)
    glEnd()


def main():
    screen, clock, font, W, H = init_viewer("3D NPC Viewer")
    idx = 0
    az, el, dist = 25.0, -25.0, 5.0
    walking = False
    fleeing = False
    walk_phase = 0.0

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    walking = not walking
                elif event.key == pygame.K_f:
                    fleeing = not fleeing
                    walking = fleeing or walking
                elif event.key == pygame.K_LEFT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    idx = (idx - 1) % len(PRESETS)
                elif event.key == pygame.K_RIGHT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    idx = (idx + 1) % len(PRESETS)
                elif event.key == pygame.K_s:
                    data = glReadPixels(0, 0, W, H, GL_RGB, GL_UNSIGNED_BYTE)
                    surf = pygame.image.fromstring(bytes(data), (W, H), "RGB", True)
                    pygame.image.save(surf, "screenshot_npc_3d.png")
                else:
                    az, el, dist = handle_camera_keys(event, az, el, dist)

        if walking:
            walk_phase += dt * 8.0

        setup_camera(W, H, az, el, dist)
        draw_ground_grid(3)

        name, prof, cls, race, color = PRESETS[idx]
        _draw_npc_3d(name, prof, cls, race, color, walk_phase if walking else 0, fleeing)

        # Lineup: draw small NPCs in a row
        glPushMatrix()
        glTranslatef(-3.0, 0, 3.0)
        for i, (n, p, c, r, col) in enumerate(PRESETS):
            glPushMatrix()
            glTranslatef(i * 0.7, 0, 0)
            glScalef(0.4, 0.4, 0.4)
            _draw_npc_3d(n, p, c, r, col, walk_phase + i * 0.5 if walking else 0, False)
            glPopMatrix()
        glPopMatrix()

        p = PRESETS[idx]
        draw_hud([
            f"{p[0]} ({p[3]} {p[2]})",
            f"[{idx+1}/{len(PRESETS)}] LEFT/RIGHT: cycle  SPACE: walk  F: flee",
            f"SHIFT+Arrows: camera  +/-: zoom  S: screenshot",
        ], font, W, H)

        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
