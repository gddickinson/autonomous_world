"""Templates — humanoids, large brutes, winged beasts, ethereal."""

import math
import pygame
from game.ui.creatures.draw_utils import (
    darken, lighten, draw_eye, draw_legs_biped, draw_ears, _sin
)


def draw_humanoid(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Goblins, orcs, skeletons, bandits — bipedal with accents."""
    bw = max(3, cs * 3)
    bh = max(4, cs * 4)
    hunched = cfg.get("hunched", False)
    bulky = cfg.get("bulky", False)
    if bulky:
        bw = max(4, int(cs * 3.5))
    body_y = sy - bh // 2 + int(breath) + (cs // 3 if hunched else 0)

    # Legs first (behind body)
    draw_legs_biped(screen, sx, body_y, bh, cs, color, walk_sin)

    # Body
    body_c = color
    if cfg.get("furry"):
        body_c = lighten(color, 8)
    pygame.draw.rect(screen, body_c,
                     (sx - bw // 2, body_y, bw, bh),
                     border_radius=max(1, cs // 2))

    # Tattered clothing (zombie)
    if cfg.get("tattered"):
        for i in range(3):
            tx = sx - bw // 2 + i * bw // 3
            pygame.draw.rect(screen, darken(color, 20 + i * 5),
                             (tx, body_y + bh - cs, max(1, bw // 4), cs))

    # Arms
    arm_swing = int(walk_sin * cs * 0.3)
    arm_w = max(1, cs // 2)
    arm_h = max(2, int(cs * 1.5))
    for i, dx in [(-1, -bw // 2 - arm_w), (1, bw // 2)]:
        swing = arm_swing * i
        pygame.draw.rect(screen, lighten(color, 5) if not cfg.get("bony") else (200, 195, 180),
                         (sx + dx, body_y + cs // 2 + swing, arm_w, arm_h))
        # Claws
        if cfg.get("claws"):
            for ci in range(3):
                pygame.draw.line(screen, (200, 200, 190),
                                 (sx + dx + arm_w // 2, body_y + cs // 2 + arm_h + swing),
                                 (sx + dx + (ci - 1) * 2, body_y + cs // 2 + arm_h + cs // 3 + swing),
                                 1)

    # Weapon (bandit)
    if cfg.get("weapon"):
        wx = sx + bw // 2 + arm_w + 1
        wy = body_y + cs
        pygame.draw.line(screen, (180, 180, 190), (wx, wy),
                         (wx + cs, wy - cs * 2), max(1, cs // 3))

    # Head
    head_r = max(2, cs + (1 if not hunched else 0))
    hx = sx
    hy = body_y - head_r + (cs // 2 if hunched else 0)
    head_c = lighten(color, 15)

    if cfg.get("bony"):
        # Skull
        pygame.draw.circle(screen, (200, 195, 180), (hx, hy), head_r)
        # Jaw
        pygame.draw.arc(screen, (170, 165, 150),
                        (hx - head_r, hy, head_r * 2, head_r), 0.2, 2.9, 1)
        draw_eye(screen, hx - head_r // 3, hy - 1, max(1, cs // 3),
                 cfg.get("eyes", "undead"))
        draw_eye(screen, hx + head_r // 3, hy - 1, max(1, cs // 3),
                 cfg.get("eyes", "undead"))
    else:
        pygame.draw.circle(screen, head_c, (hx, hy), head_r)
        # Snout (gnoll, werewolf, kobold)
        if cfg.get("snout"):
            pygame.draw.ellipse(screen, lighten(head_c, 10),
                                (hx + head_r // 2, hy - head_r // 4,
                                 head_r, head_r // 2))
        draw_eye(screen, hx + head_r // 3, hy - head_r // 4, max(1, cs // 4),
                 cfg.get("eyes", "predator"))

    # Ears
    if cfg.get("ears"):
        draw_ears(screen, hx - head_r, hx + head_r, hy - head_r,
                  max(2, cs // 2), color, cfg["ears"])

    # Hood (bandit)
    if cfg.get("hood"):
        pygame.draw.arc(screen, darken(color, 25),
                        (hx - head_r - 1, hy - head_r - 1,
                         head_r * 2 + 2, head_r * 2 + 2),
                        0.5, 2.6, max(1, cs // 3))

    # Tusks (orc)
    if "tusks" in cfg.get("extras", []):
        for dy in (-1, 1):
            pygame.draw.line(screen, (230, 220, 200),
                             (hx + head_r // 2, hy + head_r // 3 + dy),
                             (hx + head_r // 2 + cs // 3, hy + dy * 2),
                             max(1, cs // 4))

    # Crown (lich)
    if cfg.get("crown"):
        for dx in range(-head_r, head_r + 1, max(2, head_r)):
            pygame.draw.line(screen, (180, 160, 40),
                             (hx + dx, hy - head_r),
                             (hx + dx, hy - head_r - cs // 2), max(1, cs // 4))

    # Cape (vampire)
    if cfg.get("cape"):
        cape_c = (60, 20, 30)
        pts = [(sx - bw // 2, body_y + cs // 3),
               (sx + bw // 2, body_y + cs // 3),
               (sx + bw // 2 + cs // 2, body_y + bh + cs),
               (sx - bw // 2 - cs // 2, body_y + bh + cs)]
        pygame.draw.polygon(screen, cape_c, pts)

    # Armor overlay (wight)
    if cfg.get("armored"):
        pygame.draw.rect(screen, (120, 125, 135),
                         (sx - bw // 2 + 1, body_y + 1, bw - 2, bh // 2),
                         border_radius=max(1, cs // 3))


def draw_large(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Ogre, troll, hill giant, minotaur — big & imposing."""
    bw = max(6, cs * 5)
    bh = max(6, cs * 5)
    body_y = sy - bh // 2 + int(breath)

    # Thick legs
    leg_w = max(2, cs)
    leg_h = max(3, int(cs * 1.8))
    swing = int(walk_sin * cs * 0.3)
    dark = darken(color, 25)
    for i, dx in enumerate((-cs, cs)):
        lo = swing if i == 0 else -swing
        pygame.draw.rect(screen, dark,
                         (sx + dx - leg_w // 2, body_y + bh + lo, leg_w, leg_h))

    # Massive body
    if cfg.get("hunched"):
        pygame.draw.ellipse(screen, color, (sx - bw // 2, body_y + cs, bw, bh - cs))
    else:
        pygame.draw.rect(screen, color,
                         (sx - bw // 2, body_y, bw, bh),
                         border_radius=max(2, cs))

    # Arms (thick, hanging low)
    arm_w = max(2, cs)
    arm_h = max(4, int(cs * 2.5))
    arm_swing = int(walk_sin * cs * 0.25)
    for i, dx in [(-1, -bw // 2 - arm_w), (1, bw // 2)]:
        pygame.draw.rect(screen, lighten(color, 5),
                         (sx + dx, body_y + cs + arm_swing * i, arm_w, arm_h))

    # Weapon
    if cfg.get("weapon"):
        wx = sx + bw // 2 + arm_w + 2
        pygame.draw.line(screen, (140, 100, 50),
                         (wx, body_y + cs), (wx, body_y - cs), max(2, cs // 2))

    # Head
    head_r = max(3, int(cs * 1.5))
    hx = sx
    hy = body_y - head_r // 2
    pygame.draw.circle(screen, lighten(color, 10), (hx, hy), head_r)
    draw_eye(screen, hx - head_r // 3, hy - head_r // 4, max(1, cs // 3), "predator")
    draw_eye(screen, hx + head_r // 3, hy - head_r // 4, max(1, cs // 3), "predator")

    # Horns (minotaur)
    if "horns" in cfg.get("extras", []):
        for dx in (-1, 1):
            pygame.draw.line(screen, (200, 190, 160),
                             (hx + dx * head_r, hy - head_r // 2),
                             (hx + dx * (head_r + cs), hy - head_r - cs),
                             max(1, cs // 2))


def draw_winged(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Dragons, wyverns, griffins — body + prominent wings."""
    is_quad = cfg.get("quad", False)
    is_humanoid = cfg.get("humanoid", False)
    bw = max(5, cs * 4)
    bh = max(4, cs * 3)
    by = sy - bh // 2 + int(breath)

    # Body
    if is_humanoid:
        pygame.draw.rect(screen, color, (sx - bw // 3, by, bw * 2 // 3, bh),
                         border_radius=max(1, cs // 2))
        draw_legs_biped(screen, sx, by, bh, cs, color, walk_sin)
    elif is_quad:
        pygame.draw.ellipse(screen, color, (sx - bw // 2, by, bw, bh))
        for i, lx in enumerate([-cs, -cs // 3, cs // 3, cs]):
            lo = int(walk_sin * cs * 0.3) * (1 if i % 2 == 0 else -1)
            pygame.draw.rect(screen, darken(color, 20),
                             (sx + lx, by + bh + lo, max(1, cs // 2), max(2, cs)))
    else:
        pygame.draw.ellipse(screen, color, (sx - bw // 2, by, bw, bh))
        draw_legs_biped(screen, sx, by, bh, cs, color, walk_sin)

    # Wings
    wing_size = cfg.get("wings", "large")
    flap = int(walk_sin * cs * 0.5)
    wing_span = cs * 3 if wing_size == "large" else cs * 2
    wing_h = cs * 2 if wing_size == "large" else cs
    wing_c = darken(color, 15)
    if wing_size == "arm":
        # Harpy — wings are the arms
        for dx in (-1, 1):
            pts = [(sx + dx * bw // 3, by + cs // 2),
                   (sx + dx * (bw // 2 + wing_span), by - wing_h + flap * dx),
                   (sx + dx * (bw // 2 + wing_span // 2), by + bh // 2)]
            pygame.draw.polygon(screen, wing_c, pts)
    else:
        for dx in (-1, 1):
            pts = [(sx + dx * bw // 4, by + cs // 3),
                   (sx + dx * (bw // 2 + wing_span), by - wing_h + flap * dx),
                   (sx + dx * (bw // 2 + wing_span * 2 // 3), by + bh // 3)]
            pygame.draw.polygon(screen, wing_c, pts)
            # Wing membrane lines
            for i in range(3):
                t = (i + 1) / 4
                pygame.draw.line(screen, darken(wing_c, 10),
                                 (sx + dx * bw // 4, by + cs // 3),
                                 (int(pts[1][0] * t + pts[2][0] * (1 - t)),
                                  int(pts[1][1] * t + pts[2][1] * (1 - t))), 1)

    # Head
    head_r = max(2, cs + 1)
    hx = sx + bw // 3
    hy = by + bh // 4
    pygame.draw.circle(screen, lighten(color, 10), (hx, hy), head_r)
    draw_eye(screen, hx + head_r // 3, hy - 1, max(1, cs // 3), "predator")

    # Jaws
    if cfg.get("jaws") or cfg.get("beak"):
        pygame.draw.polygon(screen, lighten(color, 20),
                            [(hx + head_r, hy - cs // 3), (hx + head_r + cs, hy),
                             (hx + head_r, hy + cs // 3)])

    # Stone texture (gargoyle)
    if cfg.get("stone"):
        for i in range(5):
            gx = sx - bw // 2 + (i * bw // 4)
            gy = by + (i * bh // 5)
            pygame.draw.circle(screen, darken(color, 8), (gx, gy), max(1, cs // 4))

    # Tail
    if cfg.get("tail"):
        tail_len = max(3, cs * 2)
        for i in range(5):
            t = i / 5
            tx = sx - bw // 2 - int(t * tail_len)
            ty = by + bh // 2 + int(_sin(t * 3 + walk_sin) * cs * 0.3)
            pygame.draw.circle(screen, darken(color, 10), (tx, ty),
                               max(1, int(cs * (1 - t * 0.5) // 2)))

    # Tail sting (wyvern, manticore)
    if cfg.get("tail_sting"):
        tx = sx - bw // 2 - cs * 2
        ty = by + bh // 3
        pygame.draw.circle(screen, (200, 50, 50), (tx, ty - cs // 2), max(1, cs // 3))


def draw_ethereal(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Wraith, shadow — translucent hovering shape."""
    bw = max(4, cs * 3)
    bh = max(5, cs * 4)
    bob = int(_sin(walk_sin * 0.8) * cs * 0.5)
    by = sy - bh // 2 + bob

    surf = pygame.Surface((bw + 4, bh + 4), pygame.SRCALPHA)
    # Wispy body layers
    for i in range(3):
        alpha = 60 - i * 15
        w = bw - i * cs // 2
        h = bh - i * cs // 3
        pygame.draw.ellipse(surf, (*color, alpha),
                            (2 + (bw - w) // 2, 2 + i * cs // 4, w, h))

    # Tattered bottom (wavy)
    for i in range(bw):
        wave = int(_sin(i * 0.5 + walk_sin * 2) * cs * 0.3)
        pygame.draw.line(surf, (*color, 30),
                         (2 + i, 2 + bh - cs // 2), (2 + i, 2 + bh + wave), 1)

    screen.blit(surf, (sx - bw // 2 - 2, by - 2))

    # Eyes (glowing)
    for dx in (-cs // 2, cs // 2):
        pygame.draw.circle(screen, (180, 200, 255), (sx + dx, by + bh // 3 + bob),
                           max(1, cs // 3))
