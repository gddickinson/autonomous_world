"""Player character rendering — uses same body parts as NPCs with mode effects."""

import math
import pygame
from game.settings import TILE_SIZE, PLAYER_ATTACK_COOLDOWN
from game.ui.character_anim import (
    get_anim, update_anim, _sin, _cos,
    _darken, _lighten, _EYE_COLOR, _get_skin,
    _draw_melee,
)

# Player mode colors
_MORTAL_BODY = (60, 100, 180)
_MORTAL_SKIN = (220, 190, 160)
_GOD_BODY = (200, 180, 60)
_GOD_SKIN = (255, 240, 180)
_GHOST_BODY = (150, 170, 220)


def draw_player_body(screen, player, sx: int, sy: int, s: int, mounted=False):
    """Draw the player using the same body-part system as NPCs."""
    mode = getattr(player, 'mode', 'mortal')
    anim = get_anim(player)
    update_anim(player, getattr(player, '_last_dt', 0.016))

    if mode == "ghost":
        _draw_ghost(screen, player, sx, sy, s, anim)
        return

    # Check for god disguise — overrides appearance
    disguise = getattr(player, '_disguise', None)
    if disguise:
        if disguise.invisible:
            return  # invisible gods aren't rendered
        if disguise.form_type == "creature" and disguise.creature_kind:
            # Draw as creature sprite instead of humanoid
            from game.ui.creatures.dispatch import draw_creature_body
            class _FakeCreature:
                def __init__(self, kind, x, y):
                    self.kind = kind
                    self.x = x; self.y = y
                    self.hp = 100; self.max_hp = 100
                    self.alive = True; self.state = ''
            fc = _FakeCreature(disguise.creature_kind, player.x, player.y)
            draw_creature_body(screen, fc, sx, sy, s)
            if disguise.glow:
                _draw_god_aura(screen, sx, sy, s)
            return
        # Humanoid disguise — override colors
        body_color = disguise.clothing_color
        skin = disguise.body_color
        # Scale size
        if disguise.size_scale != 1.0:
            s = max(1, int(s * disguise.size_scale))
        if disguise.glow:
            _draw_god_aura(screen, sx, sy, s)
    elif mode == "god":
        _draw_god_aura(screen, sx, sy, s)
        body_color = _GOD_BODY
        skin = _GOD_SKIN
    else:
        body_color = _MORTAL_BODY
        skin = _MORTAL_SKIN

    # Pose-based rendering for non-walking/standing actions
    if not mounted:
        from game.ui.poses import get_pose, draw_lying_body, draw_sitting_body, \
            draw_kneeling_body, draw_working_body, draw_combat_body, \
            draw_fishing_body, draw_alert_body, draw_status_overlay
        pose = get_pose(player)
        _pose_funcs = {
            "lying": draw_lying_body, "sitting": draw_sitting_body,
            "kneeling": draw_kneeling_body, "working": draw_working_body,
            "combat": draw_combat_body, "fishing": draw_fishing_body,
            "alert": draw_alert_body,
        }
        if pose in _pose_funcs:
            _pose_funcs[pose](screen, player, sx, sy, s, body_color, skin)
            draw_status_overlay(screen, player, sx, sy, s)
            return
    rs = max(1, s)

    # Walk animation
    if anim.moving:
        walk_sin = _sin(anim.walk_phase)
        leg_swing = int(walk_sin * rs * 1.2)
        arm_swing = int(-walk_sin * rs * 0.9)
        head_bob = int(abs(_cos(anim.walk_phase)) * rs * 0.3)
    else:
        leg_swing = 0
        arm_swing = 0
        head_bob = 0

    breath = _sin(anim.idle_phase) * 0.5
    breath_offset = int(breath * 0.5)
    dark_body = _darken(body_color, 20)
    dark_body2 = _darken(body_color, 35)

    # Geometry
    leg_w = max(1, rs)
    leg_h = max(2, rs * 2)
    torso_w = max(3, rs * 3)
    torso_h = max(3, rs * 3)
    torso_x = sx - torso_w // 2
    torso_y = sy - rs + breath_offset
    arm_w = max(1, rs)
    arm_h = max(2, rs * 2)
    arm_top = torso_y + max(1, rs // 2)
    la_x = torso_x - arm_w
    ra_x = torso_x + torso_w
    hip_y = torso_y + torso_h
    head_r = max(2, rs + 1)
    head_x = sx
    head_y = torso_y - head_r + breath_offset - head_bob

    draw = pygame.draw

    # ── Legs (rects sliding vertically) ────────────────────────────
    if not mounted:
        lx = sx - rs
        rx = sx + rs - leg_w
        l_leg_y = hip_y + leg_swing + breath_offset
        r_leg_y = hip_y - leg_swing + breath_offset
        draw.rect(screen, dark_body, (lx, l_leg_y, leg_w, leg_h))
        draw.rect(screen, dark_body, (rx, r_leg_y, leg_w, leg_h))
        foot_h = max(1, rs // 2)
        draw.rect(screen, dark_body2, (lx - 1, l_leg_y + leg_h, leg_w + 2, foot_h))
        draw.rect(screen, dark_body2, (rx - 1, r_leg_y + leg_h, leg_w + 2, foot_h))

    # ── Torso ──────────────────────────────────────────────────────
    br = max(1, rs // 2)
    draw.rect(screen, body_color, (torso_x, torso_y, torso_w, torso_h),
              border_radius=br)
    if rs >= 3:
        draw.rect(screen, _darken(body_color, 25),
                  (torso_x, torso_y, torso_w, torso_h), 1, border_radius=br)

    # ── Arms ───────────────────────────────────────────────────────
    l_arm_y = arm_top + arm_swing
    r_arm_y = arm_top - arm_swing
    draw.rect(screen, skin, (la_x, l_arm_y, arm_w, arm_h))
    draw.rect(screen, skin, (ra_x, r_arm_y, arm_w, arm_h))

    # ── Head ───────────────────────────────────────────────────────
    draw.circle(screen, skin, (head_x, head_y), head_r)

    # ── Eyes ───────────────────────────────────────────────────────
    if rs >= 2:
        eye_r = max(1, rs // 3)
        fx, fy = getattr(player, 'facing', (0, 1))
        eox = int(fx * rs * 0.3)
        eye_y = head_y - max(1, rs // 4) + int(fy * rs * 0.2)
        draw.circle(screen, _EYE_COLOR, (head_x - eye_r - 1 + eox, eye_y), eye_r)
        draw.circle(screen, _EYE_COLOR, (head_x + eye_r + 1 + eox, eye_y), eye_r)

    # ── Crown (god mode) ──────────────────────────────────────────
    if mode == "god":
        crown_y = head_y - head_r
        for dx in [-rs, 0, rs]:
            draw.line(screen, (255, 215, 0),
                      (head_x + dx, crown_y),
                      (head_x + dx, crown_y - max(2, rs)), max(1, rs // 3))

    # ── Weapon (when attacking) ────────────────────────────────────
    r_hand_x = ra_x + arm_w
    r_hand_y = r_arm_y + arm_h
    attack_timer = getattr(player, 'attack_timer', 0)
    if attack_timer > PLAYER_ATTACK_COOLDOWN * 0.5:
        _draw_melee(screen, draw, r_hand_x, r_hand_y, rs, player)
        if attack_timer > PLAYER_ATTACK_COOLDOWN * 0.9:
            # Spawn swing arc if renderer has that method
            pass

    # ── Selection indicator ────────────────────────────────────────
    sel_color = (255, 215, 0) if mode == "god" else (100, 200, 255)
    draw.circle(screen, sel_color, (sx, sy), max(3, rs * 3), 1)


def _draw_ghost(screen, player, sx, sy, s, anim):
    """Draw ghost mode — translucent floating figure with body parts."""
    rs = max(1, s)
    t = pygame.time.get_ticks() * 0.004
    bob = int(math.sin(t) * rs)
    wave = int(math.sin(t * 1.5) * rs * 0.5)
    sy_g = sy + bob

    surf_w = rs * 12
    surf_h = rs * 14
    surf = pygame.Surface((surf_w, surf_h), pygame.SRCALPHA)
    cx = surf_w // 2
    cy = surf_h // 2

    # Ghost body (translucent ellipse layers)
    for i in range(3):
        alpha = 90 - i * 20
        w = rs * 3 - i * rs // 2 + wave * (i - 1) // 2
        h = rs * 4 - i * rs // 3
        pygame.draw.ellipse(surf, (150, 170, 220, alpha),
                            (cx - w, cy - h // 2 + i * rs // 3, w * 2, h))

    # Tattered bottom wisps
    for j in range(5):
        wx = cx + (j - 2) * rs
        wy = cy + rs * 2
        wisp_h = rs + int(math.sin(t * 2 + j) * rs * 0.4)
        pygame.draw.line(surf, (150, 170, 220, 50),
                         (wx, wy), (wx + wave // 2, wy + wisp_h), max(1, rs // 2))

    # Head
    head_r = max(2, rs + 1)
    pygame.draw.circle(surf, (200, 210, 240, 140), (cx, cy - rs * 2), head_r)

    # Eyes (glowing blue)
    eye_r = max(1, rs // 3)
    pygame.draw.circle(surf, (100, 150, 255, 200), (cx - eye_r - 1, cy - rs * 2), eye_r)
    pygame.draw.circle(surf, (100, 150, 255, 200), (cx + eye_r + 1, cy - rs * 2), eye_r)

    screen.blit(surf, (int(sx) - cx, int(sy_g) - cy))

    # Selection circle
    pygame.draw.circle(screen, (150, 150, 255), (int(sx), int(sy)), max(3, rs * 3), 1)


def _draw_god_aura(screen, sx, sy, s):
    """Draw golden aura behind god-mode player."""
    rs = max(1, s)
    aura_r = rs * 5
    aura_surf = pygame.Surface((aura_r * 2, aura_r * 2), pygame.SRCALPHA)
    pygame.draw.circle(aura_surf, (255, 220, 100, 25), (aura_r, aura_r), aura_r)
    pygame.draw.circle(aura_surf, (255, 240, 150, 40), (aura_r, aura_r), aura_r * 2 // 3)
    screen.blit(aura_surf, (int(sx) - aura_r, int(sy) - aura_r))
