"""Entity pose system — body position variants for different actions.

Provides pose modifiers that adjust how body parts are positioned
based on the entity's current state/action. Works with both NPC
and player 2D rendering.
"""

import math
import pygame

_sin = math.sin
_cos = math.cos


# ── Pose types ──────────────────────────────────────────────────────────

# Map actions/states to pose names
ACTION_TO_POSE = {
    # Sleeping / resting
    "sleeping": "lying",
    "collapsed_exhaustion": "lying",
    # Sitting
    "talking": "sitting",
    "trading": "sitting",
    "performing": "sitting",
    "researching": "sitting",
    # Kneeling
    "praying": "kneeling",
    "foraging": "kneeling",
    "farming": "kneeling",
    "mining": "kneeling",
    "digging": "kneeling",
    "healing": "kneeling",
    # Working (standing, arms active)
    "chopping": "working",
    "smithing": "working",
    "building": "working",
    "road_building": "working",
    "clearing_rubble": "working",
    "crafting_pottery": "working",
    "crafting_glass": "working",
    "tanning": "working",
    "dyeing": "working",
    "enchanting": "working",
    "loading": "working",
    # Combat
    "fighting": "combat",
    # Fishing (arm extended)
    "fishing": "fishing",
    # Guarding (alert stance)
    "guarding": "alert",
    "training": "combat",
}

STATE_TO_POSE = {
    "sleeping": "lying",
    "fleeing": "fleeing",  # handled separately in draw code
}


def get_pose(entity) -> str:
    """Determine the visual pose for an entity based on state/action."""
    if not getattr(entity, 'alive', True):
        return "dead"

    # Check action first (more specific)
    action = getattr(entity, 'current_action', '')
    if action in ACTION_TO_POSE:
        return ACTION_TO_POSE[action]

    # Fall back to state
    state = getattr(entity, 'state', 'idle')
    if state in STATE_TO_POSE:
        return STATE_TO_POSE[state]

    if state == "walking":
        return "walking"

    return "standing"


# ── Pose drawing helpers ────────────────────────────────────────────────

def draw_lying_body(screen, entity, sx, sy, s, body_color, skin):
    """Draw entity lying flat — sleeping or collapsed."""
    rs = max(1, s)
    draw = pygame.draw

    torso_w = max(4, rs * 4)
    torso_h = max(2, rs * 2)

    # Body (horizontal — rotated 90 degrees)
    draw.rect(screen, body_color,
              (sx - torso_w // 2, sy - torso_h // 2, torso_w, torso_h),
              border_radius=max(1, rs // 2))

    # Head (to one side)
    head_r = max(2, rs)
    draw.circle(screen, skin, (sx - torso_w // 2 - head_r + 1, sy), head_r)

    # Arms (along body)
    arm_w = max(3, rs * 2)
    arm_h = max(1, rs // 2)
    draw.rect(screen, skin, (sx - arm_w // 2, sy - torso_h // 2 - arm_h, arm_w, arm_h))

    # Legs (extended)
    leg_w = max(3, rs * 2)
    leg_h = max(1, rs // 2)
    from game.ui.character_anim import _darken
    draw.rect(screen, _darken(body_color, 20),
              (sx + torso_w // 2 - 1, sy - leg_h, leg_w, leg_h))
    draw.rect(screen, _darken(body_color, 20),
              (sx + torso_w // 2 - 1, sy + 1, leg_w, leg_h))

    # Sleeping Zs
    action = getattr(entity, 'current_action', getattr(entity, 'state', ''))
    if action == "sleeping":
        t = pygame.time.get_ticks() * 0.003
        for i in range(3):
            zx = sx - torso_w // 2 - head_r - max(2, rs) - i * max(2, rs)
            zy = sy - head_r - i * max(2, rs) + int(_sin(t + i) * rs * 0.3)
            alpha = max(80, 220 - i * 60)
            z_size = max(6, 8 + rs - i * 2)
            z_font = pygame.font.SysFont("monospace", z_size)
            z_surf = z_font.render("z", True, (150, 150, 200))
            screen.blit(z_surf, (zx, zy))


def draw_sitting_body(screen, entity, sx, sy, s, body_color, skin):
    """Draw entity sitting — torso upright, legs bent forward."""
    rs = max(1, s)
    draw = pygame.draw
    from game.ui.character_anim import _darken

    dark_body = _darken(body_color, 20)
    torso_w = max(3, rs * 3)
    torso_h = max(2, rs * 2)  # shorter torso (sitting)
    torso_x = sx - torso_w // 2
    torso_y = sy - rs

    # Legs bent forward (horizontal)
    leg_w = max(2, rs * 2)
    leg_h = max(1, rs)
    draw.rect(screen, dark_body, (sx - rs, sy + torso_h // 2, leg_w, leg_h))

    # Torso
    draw.rect(screen, body_color, (torso_x, torso_y, torso_w, torso_h),
              border_radius=max(1, rs // 2))

    # Arms (resting on lap)
    arm_w = max(1, rs)
    arm_h = max(1, rs)
    draw.rect(screen, skin, (torso_x - arm_w, torso_y + torso_h // 2, arm_w, arm_h))
    draw.rect(screen, skin, (torso_x + torso_w, torso_y + torso_h // 2, arm_w, arm_h))

    # Head
    head_r = max(2, rs + 1)
    draw.circle(screen, skin, (sx, torso_y - head_r + 1), head_r)

    # Eyes
    if rs >= 2:
        eye_r = max(1, rs // 3)
        fx, fy = getattr(entity, 'facing', (0, 1))
        eox = int(fx * rs * 0.3)
        from game.ui.character_anim import _EYE_COLOR
        draw.circle(screen, _EYE_COLOR, (sx - eye_r - 1 + eox, torso_y - head_r - 1), eye_r)
        draw.circle(screen, _EYE_COLOR, (sx + eye_r + 1 + eox, torso_y - head_r - 1), eye_r)


def draw_kneeling_body(screen, entity, sx, sy, s, body_color, skin):
    """Draw entity kneeling — torso upright but lower, one knee down."""
    rs = max(1, s)
    draw = pygame.draw
    from game.ui.character_anim import _darken

    dark_body = _darken(body_color, 20)
    torso_w = max(3, rs * 3)
    torso_h = max(2, rs * 2)
    # Lower than standing (kneeling drops height)
    torso_y = sy

    # Kneeling leg (bent underneath)
    draw.rect(screen, dark_body, (sx - rs, sy + torso_h, max(2, rs * 2), max(1, rs // 2)))

    # Torso
    draw.rect(screen, body_color, (sx - torso_w // 2, torso_y, torso_w, torso_h),
              border_radius=max(1, rs // 2))

    # Arms (reaching down — working on ground)
    arm_w = max(1, rs)
    arm_h = max(2, rs * 2)
    draw.rect(screen, skin, (sx - torso_w // 2 - arm_w, torso_y + rs, arm_w, arm_h))
    draw.rect(screen, skin, (sx + torso_w // 2, torso_y + rs, arm_w, arm_h))

    # Head
    head_r = max(2, rs + 1)
    draw.circle(screen, skin, (sx, torso_y - head_r + 1), head_r)

    # Eyes (looking down)
    if rs >= 2:
        eye_r = max(1, rs // 3)
        from game.ui.character_anim import _EYE_COLOR
        draw.circle(screen, _EYE_COLOR, (sx - eye_r - 1, torso_y - head_r + 2), eye_r)
        draw.circle(screen, _EYE_COLOR, (sx + eye_r + 1, torso_y - head_r + 2), eye_r)


def draw_working_body(screen, entity, sx, sy, s, body_color, skin):
    """Draw entity in work pose — one arm raised with tool motion."""
    rs = max(1, s)
    draw = pygame.draw
    from game.ui.character_anim import _darken

    dark_body = _darken(body_color, 20)
    torso_w = max(3, rs * 3)
    torso_h = max(3, rs * 3)
    torso_x = sx - torso_w // 2
    torso_y = sy - rs

    # Legs (standing)
    leg_w = max(1, rs)
    leg_h = max(2, rs * 2)
    hip_y = torso_y + torso_h
    draw.rect(screen, dark_body, (sx - rs, hip_y, leg_w, leg_h))
    draw.rect(screen, dark_body, (sx + rs - leg_w, hip_y, leg_w, leg_h))

    # Torso
    draw.rect(screen, body_color, (torso_x, torso_y, torso_w, torso_h),
              border_radius=max(1, rs // 2))

    # Right arm raised (swinging tool)
    t = pygame.time.get_ticks() * 0.005
    arm_swing = int(_sin(t * 3) * rs * 1.5)
    ra_x = torso_x + torso_w
    draw.line(screen, skin,
              (ra_x, torso_y + rs // 2),
              (ra_x + rs, torso_y - rs * 2 + arm_swing), max(1, rs))
    # Tool at end of arm
    tool_x = ra_x + rs
    tool_y = torso_y - rs * 2 + arm_swing
    draw.line(screen, (140, 140, 150), (tool_x, tool_y),
              (tool_x + rs, tool_y - rs), max(1, rs // 2))

    # Left arm (at side)
    la_x = torso_x - max(1, rs)
    draw.rect(screen, skin, (la_x, torso_y + rs, max(1, rs), max(2, rs * 2)))

    # Head
    head_r = max(2, rs + 1)
    draw.circle(screen, skin, (sx, torso_y - head_r + 1), head_r)


def draw_combat_body(screen, entity, sx, sy, s, body_color, skin):
    """Draw entity in combat stance — legs wide, weapon ready."""
    rs = max(1, s)
    draw = pygame.draw
    from game.ui.character_anim import _darken

    dark_body = _darken(body_color, 20)
    torso_w = max(3, rs * 3)
    torso_h = max(3, rs * 3)
    torso_x = sx - torso_w // 2
    torso_y = sy - rs

    # Legs (wide stance)
    leg_w = max(1, rs)
    leg_h = max(2, rs * 2)
    hip_y = torso_y + torso_h
    draw.rect(screen, dark_body, (sx - rs - rs // 2, hip_y, leg_w, leg_h))
    draw.rect(screen, dark_body, (sx + rs + rs // 2 - leg_w, hip_y, leg_w, leg_h))

    # Torso (slightly leaned forward)
    draw.rect(screen, body_color, (torso_x, torso_y, torso_w, torso_h),
              border_radius=max(1, rs // 2))

    # Right arm (weapon raised)
    ra_x = torso_x + torso_w
    draw.line(screen, skin, (ra_x, torso_y + rs // 2),
              (ra_x + rs * 2, torso_y - rs), max(1, rs))
    # Weapon
    draw.line(screen, (195, 200, 210), (ra_x + rs * 2, torso_y - rs),
              (ra_x + rs * 3, torso_y - rs * 3), max(1, rs // 2))

    # Left arm (shield/guard)
    la_x = torso_x - max(1, rs)
    draw.line(screen, skin, (la_x + rs // 2, torso_y + rs),
              (la_x - rs, torso_y + rs * 2), max(1, rs))

    # Head
    head_r = max(2, rs + 1)
    draw.circle(screen, skin, (sx, torso_y - head_r + 1), head_r)

    # Determined eyes
    if rs >= 2:
        eye_r = max(1, rs // 3)
        from game.ui.character_anim import _EYE_COLOR
        draw.circle(screen, _EYE_COLOR, (sx - eye_r - 1, torso_y - head_r), eye_r)
        draw.circle(screen, _EYE_COLOR, (sx + eye_r + 1, torso_y - head_r), eye_r)


def draw_fishing_body(screen, entity, sx, sy, s, body_color, skin):
    """Draw entity fishing — sitting with rod extended."""
    rs = max(1, s)
    draw = pygame.draw
    from game.ui.character_anim import _darken

    dark_body = _darken(body_color, 20)
    torso_w = max(3, rs * 3)
    torso_h = max(2, rs * 2)
    torso_y = sy

    # Legs dangling forward
    draw.rect(screen, dark_body, (sx - rs, sy + torso_h, max(2, rs * 2), max(1, rs)))

    # Torso
    draw.rect(screen, body_color, (sx - torso_w // 2, torso_y, torso_w, torso_h),
              border_radius=max(1, rs // 2))

    # Fishing rod (long diagonal line)
    rod_end_x = sx + rs * 5
    rod_end_y = sy - rs * 2
    draw.line(screen, (120, 90, 50),
              (sx + torso_w // 2, torso_y + rs // 2),
              (rod_end_x, rod_end_y), max(1, rs // 3))
    # Fishing line (hanging down from rod tip)
    t = pygame.time.get_ticks() * 0.002
    line_sway = int(_sin(t) * rs)
    draw.line(screen, (180, 180, 180),
              (rod_end_x, rod_end_y),
              (rod_end_x + line_sway, rod_end_y + rs * 4), 1)
    # Bobber
    draw.circle(screen, (200, 50, 50),
                (rod_end_x + line_sway, rod_end_y + rs * 4), max(1, rs // 3))

    # Head
    head_r = max(2, rs + 1)
    draw.circle(screen, skin, (sx, torso_y - head_r + 1), head_r)


def draw_alert_body(screen, entity, sx, sy, s, body_color, skin):
    """Draw entity in alert/guard stance — upright, weapon at ready."""
    rs = max(1, s)
    draw = pygame.draw
    from game.ui.character_anim import _darken

    dark_body = _darken(body_color, 20)
    torso_w = max(3, rs * 3)
    torso_h = max(3, rs * 3)
    torso_x = sx - torso_w // 2
    torso_y = sy - rs

    # Legs (together, at attention)
    leg_w = max(1, rs)
    leg_h = max(2, rs * 2)
    hip_y = torso_y + torso_h
    draw.rect(screen, dark_body, (sx - rs // 2, hip_y, leg_w, leg_h))
    draw.rect(screen, dark_body, (sx + rs // 2 - leg_w, hip_y, leg_w, leg_h))

    # Torso (upright)
    draw.rect(screen, body_color, (torso_x, torso_y, torso_w, torso_h),
              border_radius=max(1, rs // 2))

    # Arms at sides, weapon vertical
    arm_w = max(1, rs)
    arm_h = max(2, rs * 2)
    draw.rect(screen, skin, (torso_x - arm_w, torso_y + rs // 2, arm_w, arm_h))
    draw.rect(screen, skin, (torso_x + torso_w, torso_y + rs // 2, arm_w, arm_h))

    # Spear/weapon (vertical)
    wx = torso_x + torso_w + arm_w
    draw.line(screen, (160, 160, 170), (wx, torso_y - rs * 2),
              (wx, torso_y + arm_h + rs), max(1, rs // 3))

    # Head
    head_r = max(2, rs + 1)
    draw.circle(screen, skin, (sx, torso_y - head_r + 1), head_r)

    # Alert eyes (looking forward)
    if rs >= 2:
        eye_r = max(1, rs // 3)
        from game.ui.character_anim import _EYE_COLOR
        draw.circle(screen, _EYE_COLOR, (sx - eye_r - 1, torso_y - head_r), eye_r)
        draw.circle(screen, _EYE_COLOR, (sx + eye_r + 1, torso_y - head_r), eye_r)


# ── Status effect overlays ──────────────────────────────────────────────

def draw_status_overlay(screen, entity, sx, sy, s):
    """Draw visual overlays for status effects (bleeding, burning, etc.)."""
    rs = max(1, s)
    t = pygame.time.get_ticks() * 0.003

    # Bleeding (red drips)
    body = getattr(entity, 'body', None)
    if body and hasattr(body, 'parts'):
        bleeding = any(getattr(p, 'bleeding', False) for p in body.parts.values())
        if bleeding:
            for i in range(2):
                bx = sx + int(_sin(t + i * 2) * rs)
                by = sy + int(t * 5 + i * rs * 3) % (rs * 6)
                pygame.draw.circle(screen, (180, 30, 30), (bx, by), max(1, rs // 3))

    # Exhaustion level
    exhaustion = getattr(entity, 'exhaustion_level', 0)
    if exhaustion >= 3:
        # Dazed swirl above head
        for i in range(3):
            sx_s = sx + int(_sin(t * 2 + i * 2.1) * rs * 2)
            sy_s = sy - rs * 4 + int(_cos(t * 2 + i * 2.1) * rs)
            pygame.draw.circle(screen, (200, 200, 100), (sx_s, sy_s), max(1, rs // 4))

    # Poison (green tinge particles)
    if getattr(entity, '_poisoned', False):
        for i in range(2):
            px = sx + int(_sin(t * 1.5 + i * 3) * rs * 2)
            py = sy - rs * 2 + int(_cos(t + i) * rs)
            pygame.draw.circle(screen, (80, 180, 60), (px, py), max(1, rs // 3))
