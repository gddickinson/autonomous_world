#!/usr/bin/env python3
"""3D Mount & Rider Viewer — shows mounted combinations in OpenGL.

Rider sits on mount's back with legs straddling the body,
one arm holding reins, weapons in the other hand.

Controls:
  LEFT/RIGHT: cycle rider type
  UP/DOWN: cycle mount type
  SHIFT+Arrows: camera    +/-: zoom
  SPACE: toggle walking
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
from viewers.creature_3d_templates import draw_ungulate_3d
from game.ui.creatures.configs import CREATURE_CONFIGS

# ── Rider presets ────────────────────────────────────────────────────────

SKIN = {
    "human": (210, 185, 155), "elf": (220, 205, 175), "dwarf": (195, 165, 130),
    "halfling": (215, 190, 155), "half-orc": (140, 160, 120), "orc": (120, 145, 100),
}
SIZE = {
    "halfling": 0.7, "gnome": 0.7, "dwarf": 0.85,
    "half-orc": 1.15, "orc": 1.2,
}

_MELEE = {"Fighter", "Paladin", "Barbarian", "Rogue", "Guard", "Soldier", "Knight"}
_MAGE = {"Wizard", "Sorcerer", "Warlock", "Cleric", "Druid", "Bard"}
_ARMORED = {"Fighter", "Paladin", "Barbarian", "Guard", "Soldier", "Knight"}

RIDERS = [
    ("Player",          None,       None,        "human",    (60, 100, 180)),
    ("Human Fighter",   "Guard",    "Fighter",   "human",    (180, 60, 60)),
    ("Elf Ranger",      "Ranger",   "Ranger",    "elf",      (80, 140, 80)),
    ("Dwarf Paladin",   "Knight",   "Paladin",   "dwarf",    (180, 160, 60)),
    ("Orc Barbarian",   "Merc",     "Barbarian", "orc",      (80, 110, 70)),
    ("Gnome Wizard",    "Sage",     "Wizard",    "gnome",    (60, 60, 180)),
    ("Half-Orc Knight", "Knight",   "Paladin",   "half-orc", (140, 130, 120)),
]

MOUNT_TYPES = [
    ("horse",     (140, 100, 60),  1.0),
    ("war_horse", (80, 70, 65),    1.1),
    ("donkey",    (130, 120, 110), 0.85),
    ("mule",      (120, 105, 85),  0.9),
    ("camel",     (190, 170, 130), 1.05),
]


def _draw_mount_3d(mount_idx, ws, bob):
    """Draw the mount using ungulate template."""
    name, color, size_mult = MOUNT_TYPES[mount_idx]
    cfg = CREATURE_CONFIGS.get(name, CREATURE_CONFIGS.get("horse"))
    sc = size_mult
    draw_ungulate_3d(sc, color, ws, bob, cfg)
    # Return mount back height for rider placement
    bw_r, bh_r = cfg.get("body_r", (1.0, 0.5))
    bh = 0.2 * sc * bh_r
    by = 0.5 * sc + bob
    return by + bh  # top of mount body


def _draw_rider_3d(rider_idx, mount_back_y, ws, bob):
    """Draw rider sitting on mount — legs straddling, side-profile torso."""
    name, prof, cls, race, color = RIDERS[rider_idx]
    sc = SIZE.get(race, 1.0) if race else 1.0
    skin = SKIN.get(race, (210, 185, 155)) if race else (220, 190, 160)
    armored = (cls in _ARMORED) if cls else False
    torso_c = (170, 175, 185) if armored else color

    # Rider dimensions (slightly smaller than standing)
    tw = 0.2 * sc   # torso width
    th = 0.3 * sc   # torso height
    td = 0.12 * sc  # torso depth
    aw = 0.055 * sc  # arm width
    ah = 0.22 * sc   # arm length

    # Rider sits on mount back
    ty = mount_back_y - 0.02  # slight overlap into mount
    bob_r = abs(math.cos(ws * 6.28)) * 0.015 * sc if ws != 0 else 0

    # ── Legs straddling mount (hanging down each side) ─────────────
    leg_w = 0.05 * sc
    leg_h = 0.2 * sc
    leg_dark = (max(0, color[0] - 25), max(0, color[1] - 25), max(0, color[2] - 25))

    glBegin(GL_QUADS)
    # Left leg (hangs down on -Z side)
    draw_box(-0.04 * sc, ty - leg_h * 0.7, -td * 0.8 - leg_w,
             leg_w, leg_h, leg_w, leg_dark)
    # Right leg (hangs down on +Z side)
    draw_box(-0.04 * sc, ty - leg_h * 0.7, td * 0.8,
             leg_w, leg_h, leg_w, leg_dark)
    # Boots/feet at bottom of legs
    draw_box(-0.05 * sc, ty - leg_h * 0.7 - 0.02, -td * 0.8 - leg_w - 0.01,
             leg_w + 0.02, 0.02, leg_w, (max(0, color[0] - 40), max(0, color[1] - 40), max(0, color[2] - 40)))
    draw_box(-0.05 * sc, ty - leg_h * 0.7 - 0.02, td * 0.8 + 0.01,
             leg_w + 0.02, 0.02, leg_w, (max(0, color[0] - 40), max(0, color[1] - 40), max(0, color[2] - 40)))

    glEnd()

    # Rotate upper body to face forward (same direction as mount)
    glPushMatrix()
    glRotatef(-90, 0, 1, 0)

    # ── Torso (sitting upright on mount, now facing forward) ───────
    glBegin(GL_QUADS)
    draw_box(-tw / 2, ty + bob_r, -td / 2, tw, th, td, torso_c)
    glEnd()

    # ── Arms (one holds reins forward, one at side/weapon) ─────────
    shoulder_y = ty + th * 0.75 + bob_r

    # Left arm — holds reins (angled forward-down toward mount's neck)
    glPushMatrix()
    glTranslatef(-tw / 2 - aw / 2, shoulder_y, 0)
    glRotatef(35, 1, 0, 0)  # angle forward
    glRotatef(-15, 0, 0, 1)  # angle slightly down
    glBegin(GL_QUADS)
    draw_box(-aw / 2, -ah, -aw / 2, aw, ah, aw, skin)
    glEnd()
    # Rein line from hand toward mount head
    glBegin(GL_LINES)
    glColor3f(0.4, 0.3, 0.2)
    glVertex3f(0, -ah, 0)
    glVertex3f(0.15 * sc, -ah - 0.05, -0.05)
    glEnd()
    glPopMatrix()

    # Right arm — weapon hand (at side or holding weapon)
    glPushMatrix()
    glTranslatef(tw / 2 + aw / 2, shoulder_y, 0)
    if cls and cls in _MELEE:
        glRotatef(-20, 1, 0, 0)  # slight back angle (sword ready)
    else:
        glRotatef(10, 1, 0, 0)  # relaxed forward
    glBegin(GL_QUADS)
    draw_box(-aw / 2, -ah, -aw / 2, aw, ah, aw, skin)

    # Weapon in right hand
    if cls and cls in _MELEE:
        # Sword pointing forward
        bw_s = 0.02 * sc
        bl = 0.3 * sc
        draw_box(-bw_s / 2, -ah - 0.01, -bl - bw_s / 2,
                 bw_s, bw_s * 2, bl, (195, 200, 215))
        # Crossguard
        draw_box(-0.04 * sc, -ah - 0.005, -bw_s,
                 0.08 * sc, 0.02, 0.02, (160, 155, 140))
    elif cls and cls in _MAGE:
        # Staff pointing up
        staff_w = 0.02 * sc
        draw_box(-staff_w / 2, -ah, -staff_w / 2,
                 staff_w, ah + th * 0.6, staff_w, (120, 90, 50))
    glEnd()

    # Hand sphere
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, -ah, 0, 0.03 * sc, skin, 4)
    # Mage orb at staff top
    if cls and cls in _MAGE:
        orb_colors = {"Wizard": (80, 120, 220), "Sorcerer": (200, 80, 200),
                      "Warlock": (140, 60, 180), "Cleric": (220, 200, 100),
                      "Druid": (80, 180, 80), "Bard": (200, 140, 200)}
        oc = orb_colors.get(cls, (140, 140, 220))
        draw_sphere_approx(0, th * 0.6, 0, 0.04 * sc, oc, 5)
    glEnd()
    glPopMatrix()

    # ── Shield (armored — on left side) ────────────────────────────
    if armored:
        glBegin(GL_QUADS)
        s_w = 0.12 * sc
        s_h = 0.15 * sc
        draw_box(-tw / 2 - aw - 0.02, ty + th * 0.2 + bob_r, -s_w / 2,
                 0.025, s_h, s_w, (140, 100, 50))
        draw_box(-tw / 2 - aw - 0.025, ty + th * 0.2 - 0.005 + bob_r, -s_w / 2 - 0.005,
                 0.005, s_h + 0.01, s_w + 0.01, (110, 75, 35))
        glEnd()

    # ── Head ───────────────────────────────────────────────────────
    head_r = 0.09 * sc
    head_y = ty + th + head_r * 0.5 + bob_r
    glBegin(GL_TRIANGLES)
    draw_sphere_approx(0, head_y, 0, head_r, skin, 7)
    # Eyes (facing forward — toward mount head direction)
    draw_sphere_approx(head_r * 0.35, head_y + head_r * 0.15, -head_r * 0.7,
                        head_r * 0.18, (40, 35, 30), 4)
    draw_sphere_approx(-head_r * 0.2, head_y + head_r * 0.15, -head_r * 0.7,
                        head_r * 0.18, (40, 35, 30), 4)
    glEnd()

    glPopMatrix()  # end of 90° rotation for upper body


# ── Main loop ────────────────────────────────────────────────────────────

def main():
    screen, clock, font, W, H = init_viewer("3D Mount & Rider Viewer")
    rider_idx = 0
    mount_idx = 0
    az, el, dist = 30.0, -25.0, 5.0
    walking = False
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
                elif event.key == pygame.K_LEFT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    rider_idx = (rider_idx - 1) % len(RIDERS)
                elif event.key == pygame.K_RIGHT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    rider_idx = (rider_idx + 1) % len(RIDERS)
                elif event.key == pygame.K_UP and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    mount_idx = (mount_idx - 1) % len(MOUNT_TYPES)
                elif event.key == pygame.K_DOWN and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    mount_idx = (mount_idx + 1) % len(MOUNT_TYPES)
                elif event.key == pygame.K_SPACE:
                    walking = not walking
                elif event.key == pygame.K_s:
                    d = glReadPixels(0, 0, W, H, GL_RGB, GL_UNSIGNED_BYTE)
                    pygame.image.save(pygame.image.fromstring(bytes(d), (W, H), "RGB", True),
                                      "screenshot_mount_3d.png")
                else:
                    az, el, dist = handle_camera_keys(event, az, el, dist)

        if walking:
            walk_phase += dt * 6.0

        ws = math.sin(walk_phase) if walking else 0
        bob = abs(math.cos(walk_phase)) * 0.02 if walking else 0

        setup_camera(W, H, az, el, dist, look_y=0.7)
        draw_ground_grid(3)

        # Draw mount + rider
        mount_back = _draw_mount_3d(mount_idx, ws, bob)
        _draw_rider_3d(rider_idx, mount_back, ws, bob)

        # Draw comparison: all mounts with current rider in a row behind
        glPushMatrix()
        glTranslatef(-2.5, 0, 3.0)
        for mi in range(len(MOUNT_TYPES)):
            glPushMatrix()
            glTranslatef(mi * 1.2, 0, 0)
            glScalef(0.4, 0.4, 0.4)
            mb = _draw_mount_3d(mi, ws, bob)
            _draw_rider_3d(rider_idx, mb, ws, bob)
            glPopMatrix()
        glPopMatrix()

        rider_name = RIDERS[rider_idx][0]
        mount_name = MOUNT_TYPES[mount_idx][0].replace("_", " ")
        draw_hud([
            f"{rider_name} on {mount_name}",
            f"LEFT/RIGHT: rider  UP/DOWN: mount  SPACE: walk",
            f"SHIFT+Arrows: camera  +/-: zoom  S: screenshot",
        ], font, W, H)

        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
