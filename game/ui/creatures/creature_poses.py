"""Creature pose system — body positions for different creature actions.

Provides alternative drawing for creatures that are sleeping, sitting,
in combat, or alert. Integrates with the creature sprite dispatch.
"""

import math
import pygame
from game.ui.creatures.draw_utils import darken, lighten, draw_eye, _sin


# Actions/states that trigger creature poses
CREATURE_ACTION_TO_POSE = {
    "sleeping": "sleeping",
    "resting": "sleeping",
    "idle": "resting",  # idle creatures rest, not stand
    "chasing": "alert",
    "attacking": "combat",
    "fleeing": "fleeing",
}

CREATURE_STATE_TO_POSE = {
    "sleeping": "sleeping",
    "idle": "resting",
    "chasing": "alert",
    "attacking": "combat",
}


def get_creature_pose(creature) -> str:
    """Get the visual pose for a creature."""
    if not getattr(creature, 'alive', True):
        return "dead"
    state = getattr(creature, 'state', 'idle')
    action = getattr(creature, 'current_action', '')
    if action in CREATURE_ACTION_TO_POSE:
        return CREATURE_ACTION_TO_POSE[action]
    if state in CREATURE_STATE_TO_POSE:
        return CREATURE_STATE_TO_POSE[state]
    return "standing"


def draw_quadruped_sleeping(screen, sx, sy, cs, color, cfg):
    """Quadruped curled up sleeping — compact oval, tail wrapped around."""
    body_w = max(3, cs * 3)
    body_h = max(2, int(cs * 1.5))
    by = sy - body_h // 3

    # Curled body (rounder than standing)
    pygame.draw.ellipse(screen, color, (sx - body_w // 2, by, body_w, body_h))
    # Belly highlight
    pygame.draw.ellipse(screen, lighten(color, 12),
                        (sx - body_w // 3, by + body_h // 2,
                         body_w * 2 // 3, body_h // 3))

    # Head tucked into body
    hr = max(2, cs)
    hx = sx + body_w // 3
    hy = by + body_h // 4
    pygame.draw.circle(screen, lighten(color, 10), (hx, hy), hr)
    # Closed eyes (lines instead of circles)
    if cs >= 2:
        ex = hx + hr // 3
        ey = hy - hr // 4
        pygame.draw.line(screen, (60, 50, 40), (ex - cs // 3, ey), (ex + cs // 3, ey), 1)

    # Tail wrapped around
    tail_style = cfg.get("tail", "thin")
    if tail_style:
        pts = [(sx - body_w // 2, by + body_h // 2),
               (sx - body_w // 2 - cs, by + body_h),
               (sx - body_w // 4, by + body_h)]
        pygame.draw.polygon(screen, darken(color, 10), pts)

    # Sleeping Zs
    t = pygame.time.get_ticks() * 0.003
    for i in range(2):
        zx = hx + hr + i * max(2, cs)
        zy = hy - hr - i * max(2, cs) + int(_sin(t + i) * cs * 0.3)
        z_font = pygame.font.SysFont("monospace", max(6, 7 + cs - i * 2))
        screen.blit(z_font.render("z", True, (150, 150, 200)), (zx, zy))


def draw_quadruped_resting(screen, sx, sy, cs, color, cfg):
    """Quadruped lying down alert — body flat, head up, legs tucked."""
    body_w = max(4, cs * 4)
    body_h = max(2, int(cs * 1.2))
    by = sy

    # Flat body
    pygame.draw.ellipse(screen, color, (sx - body_w // 2, by, body_w, body_h))
    # Belly
    pygame.draw.ellipse(screen, lighten(color, 10),
                        (sx - body_w // 3, by + body_h // 2,
                         body_w * 2 // 3, body_h // 3))

    # Tucked legs (small bumps visible underneath)
    dark = darken(color, 20)
    for lx in (-cs, cs):
        pygame.draw.rect(screen, dark, (sx + lx - cs // 4, by + body_h - 1,
                                         max(1, cs // 2), max(1, cs // 3)))

    # Head up (alert)
    hr = max(2, cs)
    head_shape = cfg.get("head", "round")
    hx = sx + body_w // 2 - hr // 2
    hy = by - hr // 2
    if head_shape == "pointed":
        pts = [(hx, hy - hr), (hx + hr * 2, hy), (hx, hy + hr)]
        pygame.draw.polygon(screen, lighten(color, 10), pts)
    else:
        pygame.draw.circle(screen, lighten(color, 10), (hx, hy), hr)

    # Eyes open
    eye_style = cfg.get("eyes", "predator")
    draw_eye(screen, hx + hr // 2, hy - hr // 4, max(1, cs // 4), eye_style)

    # Ears
    ear_style = cfg.get("ears", "pointed")
    if ear_style == "pointed":
        for dx in (-hr // 3, hr // 3):
            pts = [(hx + dx - cs // 4, hy), (hx + dx, hy - cs),
                   (hx + dx + cs // 4, hy)]
            pygame.draw.polygon(screen, color, pts)

    # Tail
    tail_style = cfg.get("tail", "thin")
    if tail_style == "bushy":
        pygame.draw.ellipse(screen, darken(color, 5),
                            (sx - body_w // 2 - cs, by + body_h // 3,
                             max(2, cs), max(2, cs)))
    elif tail_style:
        pygame.draw.line(screen, darken(color, 10),
                         (sx - body_w // 2, by + body_h // 2),
                         (sx - body_w // 2 - cs, by + body_h // 3), max(1, cs // 4))


def draw_quadruped_combat(screen, sx, sy, cs, color, cfg):
    """Quadruped in aggressive stance — low body, teeth bared, hackles up."""
    body_w = max(4, int(cs * 3.5))
    body_h = max(2, cs * 2)
    by = sy - body_h // 3

    # Body (slightly lower/flatter than normal)
    pygame.draw.ellipse(screen, color, (sx - body_w // 2, by, body_w, body_h))

    # Hackles/raised fur on back
    dark = darken(color, 10)
    for i in range(max(2, body_w // cs)):
        hx_h = sx - body_w // 3 + i * max(2, cs)
        pygame.draw.polygon(screen, dark,
                            [(hx_h, by), (hx_h + cs // 2, by - cs // 2),
                             (hx_h + cs, by)])

    # Legs (wide stance)
    leg_dark = darken(color, 25)
    leg_w = max(1, cs // 3)
    leg_h = max(2, cs)
    for lx in (-cs - cs // 2, -cs // 2, cs // 2, cs + cs // 2):
        pygame.draw.rect(screen, leg_dark,
                         (sx + lx - leg_w // 2, by + body_h, leg_w, leg_h))

    # Head low, mouth open
    hr = max(2, cs)
    hx = sx + body_w // 2
    hy = by + body_h // 2
    head_shape = cfg.get("head", "round")
    if head_shape == "pointed":
        # Open jaw
        pygame.draw.polygon(screen, lighten(color, 10),
                            [(hx, hy - hr), (hx + hr * 2, hy - 1), (hx, hy)])
        pygame.draw.polygon(screen, darken(color, 5),
                            [(hx, hy), (hx + hr * 2, hy + 1), (hx, hy + hr // 2)])
        # Teeth
        for i in range(3):
            tx = hx + hr // 2 + i * hr // 2
            pygame.draw.line(screen, (230, 225, 210),
                             (tx, hy - 1), (tx, hy + 1), 1)
    else:
        pygame.draw.circle(screen, lighten(color, 10), (hx, hy), hr)
        # Open mouth
        pygame.draw.arc(screen, (180, 50, 40),
                        (hx - hr // 2, hy, hr, hr // 2), 3.14, 0, 1)

    # Angry eyes
    draw_eye(screen, hx + hr // 3, hy - hr // 2, max(1, cs // 3), "predator")


def draw_bird_perching(screen, sx, sy, cs, color, cfg):
    """Bird perching — compact body, wings folded, on a branch/ground."""
    br = max(2, cs)
    by = sy - br

    # Round compact body
    pygame.draw.ellipse(screen, color, (sx - br, by, br * 2, int(br * 1.5)))
    # Breast
    pygame.draw.ellipse(screen, lighten(color, 12),
                        (sx - br // 2, by + br // 2, br, br * 2 // 3))

    # Folded wings (subtle lines on body)
    pygame.draw.arc(screen, darken(color, 15),
                    (sx - br, by + 2, br * 2, br), 0.5, 2.5, 1)

    # Head
    hr = max(1, br * 2 // 3)
    pygame.draw.circle(screen, lighten(color, 10), (sx, by - hr // 2), hr)
    # Eye
    draw_eye(screen, sx + hr // 3, by - hr // 2 - 1, max(1, cs // 4),
             cfg.get("eyes", "predator") if not cfg.get("eyes") == "big" else "big")

    # Beak
    beak = cfg.get("beak", "pointed")
    if beak in ("hooked", "pointed"):
        pygame.draw.polygon(screen, (200, 170, 50),
                            [(sx + hr, by - hr // 2), (sx + hr + cs // 2, by - hr // 4),
                             (sx + hr, by)])

    # Legs (thin, gripping)
    for dx in (-2, 2):
        pygame.draw.line(screen, (180, 150, 80),
                         (sx + dx, by + int(br * 1.5)),
                         (sx + dx, by + int(br * 1.5) + max(1, cs // 2)), 1)


def draw_serpent_coiled(screen, sx, sy, cs, color, cfg):
    """Serpent coiled up — concentric circles, head raised."""
    coil_r = max(3, cs * 2)

    # Coiled body (concentric arcs)
    for i in range(3):
        r = coil_r - i * max(1, cs // 2)
        if r < 2:
            break
        shade = darken(color, i * 8)
        pygame.draw.circle(screen, shade, (sx, sy), r, max(1, cs // 3))

    # Head raised above coil
    hr = max(2, cs)
    hx = sx + coil_r // 2
    hy = sy - coil_r - hr // 2
    # Neck
    pygame.draw.line(screen, color, (sx + coil_r // 3, sy - coil_r // 2),
                     (hx, hy + hr // 2), max(1, cs // 3))
    # Head
    if cfg.get("head_wide"):
        pygame.draw.ellipse(screen, lighten(color, 10),
                            (hx - hr, hy - hr // 2, hr * 2, hr))
    else:
        pygame.draw.circle(screen, lighten(color, 10), (hx, hy), hr)

    # Eyes
    draw_eye(screen, hx + hr // 3, hy - hr // 4, max(1, cs // 4), "predator")

    # Tongue
    t = pygame.time.get_ticks() * 0.005
    pygame.draw.line(screen, (200, 50, 50), (hx + hr, hy),
                     (hx + hr + cs // 2, hy + int(_sin(t * 5) * 2)), 1)
