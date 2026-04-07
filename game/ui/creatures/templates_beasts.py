"""Beast templates — quadrupeds, ungulates, bears, small critters.

Enhanced with fur texture, paw/hoof detail, and ear variety.
"""

import pygame
from game.ui.creatures.draw_utils import (
    darken, lighten, draw_eye, draw_legs_quad, draw_tail, draw_ears
)


def _draw_fur_texture(screen, x, y, w, h, color, density=4):
    """Draw short fur lines on a body area."""
    fur_c = darken(color, 8)
    spacing = max(2, w // density)
    for col in range(x + 1, x + w - 1, spacing):
        for row in range(y + 2, y + h - 1, spacing + 1):
            pygame.draw.line(screen, fur_c, (col, row), (col, row + 1), 1)


def _draw_paw_detail(screen, x, y, w, h, color, cs):
    """Draw paw pads at the foot of a leg."""
    if cs < 3:
        return
    pad_c = darken(color, 30)
    # Main pad
    pad_r = max(1, w // 2)
    pygame.draw.circle(screen, pad_c, (x + w // 2, y + h - 1), pad_r)


def draw_quadruped(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Wolf, fox, cat, boar — horizontal body, 4 legs, head at front."""
    bw_r, bh_r = cfg.get("body_r", (1.0, 0.5))
    body_w = max(4, int(cs * 4 * bw_r))
    body_h = max(2, int(cs * 2 * bh_r))
    by = sy - body_h // 2 + int(breath)

    # Body (main ellipse)
    pygame.draw.ellipse(screen, color, (sx - body_w // 2, by, body_w, body_h))
    # Belly highlight
    belly = lighten(color, 15)
    bh2 = max(1, body_h // 3)
    pygame.draw.ellipse(screen, belly,
                        (sx - body_w // 3, by + body_h - bh2, body_w * 2 // 3, bh2))

    # Fur texture on body
    if cs >= 2:
        _draw_fur_texture(screen, sx - body_w // 2 + 1, by + 1,
                          body_w - 2, body_h - 2, color)

    # Legs
    draw_legs_quad(screen, sx, by, body_h, cs, color, walk_sin,
                   [-cs, -cs // 3, cs // 3, cs - 1])

    # Head
    head_shape = cfg.get("head", "round")
    hr = max(2, cs)
    hx = sx + body_w // 2
    hy = by + body_h // 3
    if head_shape == "pointed":
        # Snout: triangular head
        pts = [(hx, hy - hr), (hx + hr * 2, hy), (hx, hy + hr)]
        pygame.draw.polygon(screen, lighten(color, 10), pts)
        # Nose
        pygame.draw.circle(screen, (30, 30, 30), (hx + hr * 2 - 1, hy), max(1, cs // 4))
    elif head_shape == "flat":
        # Flat snout (boar)
        pygame.draw.ellipse(screen, lighten(color, 10),
                            (hx - hr // 2, hy - hr, hr * 2, hr * 2))
        # Snout disc
        pygame.draw.circle(screen, lighten(color, 25), (hx + hr, hy), max(1, hr // 2))
    else:
        # Round head
        pygame.draw.circle(screen, lighten(color, 10), (hx, hy), hr)
        pygame.draw.circle(screen, (30, 30, 30), (hx + hr - 1, hy), max(1, cs // 5))

    # Eyes
    eye_r = max(1, cs // 4)
    eye_style = cfg.get("eyes", "predator")
    draw_eye(screen, hx + hr // 2, hy - hr // 3, eye_r, eye_style)

    # Ears
    ear_size = max(2, cs // 2)
    ear_style = cfg.get("ears", "pointed")
    draw_ears(screen, hx - hr // 2, hx + hr // 3, hy - hr, ear_size, color, ear_style)

    # Tail
    tail_style = cfg.get("tail", "thin")
    tail_len = max(3, cs)
    draw_tail(screen, sx - body_w // 2, by + body_h // 3,
              tail_len, color, tail_style, walk_sin)

    # Extras (tusks)
    if "tusks" in cfg.get("extras", []):
        tusk_c = (230, 220, 200)
        tl = max(2, cs // 2)
        pygame.draw.line(screen, tusk_c, (hx + hr, hy - 1),
                         (hx + hr + tl, hy - tl), max(1, cs // 5))
        pygame.draw.line(screen, tusk_c, (hx + hr, hy + 1),
                         (hx + hr + tl, hy + tl), max(1, cs // 5))


def draw_ungulate(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Deer, horse, cow — taller legs, elongated head, possible antlers."""
    bw_r, bh_r = cfg.get("body_r", (1.0, 0.5))
    body_w = max(4, int(cs * 4 * bw_r))
    body_h = max(2, int(cs * 2 * bh_r))
    # Higher body position (longer legs)
    leg_extra = max(1, cs // 2)
    by = sy - body_h // 2 - leg_extra + int(breath)

    # Body
    fluffy = cfg.get("fluffy", False)
    if fluffy:
        # Woolly body (sheep)
        pygame.draw.ellipse(screen, lighten(color, 10),
                            (sx - body_w // 2 - 1, by - 1, body_w + 2, body_h + 2))
    pygame.draw.ellipse(screen, color, (sx - body_w // 2, by, body_w, body_h))

    # Legs (longer than quadruped)
    leg_w = max(1, cs // 3)
    leg_h = max(3, cs + leg_extra)
    dark = darken(color, 25)
    swing = int(walk_sin * cs * 0.35)
    for i, lx in enumerate([-cs, -cs // 3, cs // 3, cs - 1]):
        lo = swing if i % 2 == 0 else -swing
        pygame.draw.rect(screen, dark,
                         (sx + lx - leg_w // 2, by + body_h + lo, leg_w, leg_h))
        # Hoof (enhanced with split detail)
        hoof_c = darken(color, 45)
        hoof_x = sx + lx - leg_w // 2 - 1
        hoof_y = by + body_h + leg_h + lo
        hoof_w = leg_w + 2
        hoof_h = max(2, cs // 3)
        pygame.draw.rect(screen, hoof_c,
                         (hoof_x, hoof_y, hoof_w, hoof_h),
                         border_radius=max(1, cs // 5))
        # Split line in hoof
        if cs >= 3:
            pygame.draw.line(screen, darken(color, 55),
                             (sx + lx, hoof_y),
                             (sx + lx, hoof_y + hoof_h - 1), 1)

    # Head (elongated)
    hr = max(2, cs)
    hx = sx + body_w // 2
    hy = by + body_h // 4
    # Neck
    pygame.draw.line(screen, color, (sx + body_w // 3, by + 2),
                     (hx, hy), max(2, cs // 2))
    # Head shape
    head_w = max(3, int(hr * 1.8))
    head_h = max(2, hr)
    pygame.draw.ellipse(screen, lighten(color, 10),
                        (hx - head_h // 2, hy - head_h, head_w, head_h * 2))
    # Nose
    pygame.draw.circle(screen, darken(color, 30),
                       (hx + head_w - head_h, hy), max(1, cs // 5))

    # Eyes
    draw_eye(screen, hx, hy - head_h // 3, max(1, cs // 4),
             cfg.get("eyes", "gentle"))

    # Ears
    ear_size = max(2, cs // 2)
    draw_ears(screen, hx - hr // 2, hx + hr // 3, hy - hr,
              ear_size, color, cfg.get("ears", "pointed"))

    # Extras
    extras = cfg.get("extras", [])
    if "antlers" in extras:
        draw_ears(screen, hx - hr // 2, hx + hr // 3, hy - hr,
                  max(2, cs // 2), color, "antlers")
    if "horns" in extras:
        draw_ears(screen, hx - hr // 2, hx + hr // 3, hy - hr,
                  max(2, cs // 2), color, "horns")
    if "horn" in extras:
        # Single horn (unicorn)
        pygame.draw.line(screen, (230, 230, 250),
                         (hx + hr // 2, hy - hr),
                         (hx + hr, hy - hr * 3), max(1, cs // 4))
    if "mane" in extras:
        mane_c = darken(color, 15)
        for i in range(max(2, cs // 2)):
            mx = sx + body_w // 3 - i * max(1, cs // 3)
            my = by - max(1, cs // 4)
            pygame.draw.circle(screen, mane_c, (mx, my + i), max(1, cs // 3))
    if "humanoid_torso" in extras:
        # Centaur: small humanoid upper body at front
        tx = sx + body_w // 3
        ty = by - cs
        pygame.draw.rect(screen, lighten(color, 30),
                         (tx - cs // 2, ty, cs, cs), border_radius=max(1, cs // 4))
        pygame.draw.circle(screen, (200, 180, 150), (tx, ty - cs // 2), max(2, cs // 2))

    # Tail
    tail_style = cfg.get("tail", "thin")
    draw_tail(screen, sx - body_w // 2, by + body_h // 2,
              max(3, cs), color, tail_style, walk_sin)


def draw_bear(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Bear, owlbear — massive round body, thick legs, small ears."""
    body_w = max(6, cs * 5)
    body_h = max(4, cs * 4)
    by = sy - body_h // 2 + int(breath)

    # Massive body
    pygame.draw.ellipse(screen, color, (sx - body_w // 2, by, body_w, body_h))
    # Belly
    pygame.draw.ellipse(screen, lighten(color, 12),
                        (sx - body_w // 3, by + body_h // 2,
                         body_w * 2 // 3, body_h // 2))
    # Thick fur texture
    if cs >= 2:
        _draw_fur_texture(screen, sx - body_w // 2 + 1, by + 1,
                          body_w - 2, body_h - 2, color, density=3)

    # Thick legs
    leg_w = max(2, cs)
    leg_h = max(2, cs)
    dark = darken(color, 25)
    swing = int(walk_sin * cs * 0.3)
    for i, lx in enumerate([-cs - cs // 2, -cs // 2, cs // 2, cs + cs // 2]):
        lo = swing if i % 2 == 0 else -swing
        pygame.draw.rect(screen, dark,
                         (sx + lx - leg_w // 2, by + body_h + lo, leg_w, leg_h))

    # Head
    hr = max(3, int(cs * 1.3))
    hx = sx + body_w // 2 - hr // 2
    hy = by + body_h // 4
    pygame.draw.circle(screen, lighten(color, 8), (hx, hy), hr)
    # Snout
    pygame.draw.ellipse(screen, lighten(color, 20),
                        (hx + hr // 2, hy - hr // 4, hr, hr // 2))
    pygame.draw.circle(screen, (30, 30, 30), (hx + hr + hr // 2 - 1, hy), max(1, cs // 4))

    # Beak (owlbear)
    if cfg.get("beak"):
        pygame.draw.polygon(screen, (200, 180, 60),
                            [(hx + hr, hy - 1), (hx + hr + cs, hy),
                             (hx + hr, hy + 1)])

    # Eyes
    draw_eye(screen, hx + hr // 4, hy - hr // 3, max(1, cs // 3),
             cfg.get("eyes", "predator"))

    # Ears
    ear_size = max(2, cs // 3)
    draw_ears(screen, hx - hr // 2, hx + hr // 2, hy - hr + 1,
              ear_size, color, cfg.get("ears", "round"))


def draw_small(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Rabbit, squirrel, rat, pig, frog — tiny distinctive shapes."""
    shape = cfg.get("shape", "round")
    br = max(2, cs)

    if shape == "squat":
        # Frog — wide and flat
        pygame.draw.ellipse(screen, color, (sx - br * 2, sy - br, br * 4, br * 2))
        if cfg.get("eyes") == "big":
            for dx in (-br, br):
                pygame.draw.circle(screen, lighten(color, 30),
                                   (sx + dx, sy - br), max(1, br // 2))
                pygame.draw.circle(screen, (30, 30, 30),
                                   (sx + dx, sy - br), max(1, br // 3))
    else:
        # Round/oval body
        bw = br * 3 if shape == "oval" else br * 2
        pygame.draw.ellipse(screen, color, (sx - bw // 2, sy - br, bw, br * 2))
        # Belly
        pygame.draw.ellipse(screen, lighten(color, 15),
                            (sx - bw // 3, sy, bw * 2 // 3, br))

    # Legs (tiny)
    leg_w = max(1, cs // 3)
    leg_h = max(1, cs // 2)
    swing = int(walk_sin * cs * 0.3)
    dark = darken(color, 20)
    for i, dx in enumerate((-br // 2, br // 2)):
        lo = swing if i == 0 else -swing
        pygame.draw.rect(screen, dark,
                         (sx + dx - leg_w // 2, sy + br + lo, leg_w, leg_h))

    # Head
    hr = max(1, br // 2)
    hx = sx + br
    hy = sy - br // 2
    pygame.draw.circle(screen, lighten(color, 10), (hx, hy), hr)
    # Eye
    draw_eye(screen, hx + hr // 3, hy - hr // 4, max(1, cs // 5),
             cfg.get("eyes", "gentle"))

    # Snout (pig)
    if cfg.get("snout"):
        pygame.draw.circle(screen, lighten(color, 25),
                           (hx + hr, hy), max(1, hr // 2))

    # Ears
    ear_style = cfg.get("ears", "round")
    ear_size = max(1, cs // 3)
    if ear_style == "tall":
        # Rabbit ears (tall)
        for dx in (-hr // 3, hr // 3):
            pygame.draw.ellipse(screen, lighten(color, 10),
                                (hx + dx - 1, hy - hr - ear_size * 3,
                                 max(2, cs // 3), ear_size * 3))
    elif ear_style != "none":
        draw_ears(screen, hx - hr // 2, hx + hr // 2, hy - hr,
                  ear_size, color, ear_style)

    # Tail
    tail = cfg.get("tail", "")
    if tail == "puff":
        pygame.draw.circle(screen, lighten(color, 20),
                           (sx - br - 1, sy), max(1, cs // 3))
    elif tail == "bushy_up":
        draw_tail(screen, sx - br, sy - br // 2, max(2, cs),
                  lighten(color, 10), "bushy", walk_sin)
    elif tail == "thin":
        draw_tail(screen, sx - br - 1, sy, max(2, cs),
                  darken(color, 10), "thin", walk_sin)
