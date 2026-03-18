"""Templates — birds, serpents, reptiles, arachnids, aquatic."""

import math
import pygame
from game.ui.creatures.draw_utils import (
    darken, lighten, draw_eye, _sin, _cos
)


def draw_bird(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Hawks, eagles, owls, chickens — body + wings + beak + tail."""
    br = max(2, cs)
    by = sy - br + int(breath)

    # Body (oval)
    pygame.draw.ellipse(screen, color, (sx - br, by, br * 2, int(br * 1.5)))
    # Breast
    pygame.draw.ellipse(screen, lighten(color, 15),
                        (sx - br // 2, by + br // 2, br, br))

    # Wings
    wing_type = cfg.get("wings", "feathered")
    wing_w = max(3, int(cs * 1.5))
    wing_h = max(2, cs)
    flap = int(walk_sin * cs * 0.3)
    if wing_type == "membrane":
        # Bat wings — pointed
        for dx, flip in [(-1, False), (1, True)]:
            wx = sx + dx * br
            pts = [(wx, by + br // 2),
                   (wx + dx * wing_w, by - wing_h // 2 + flap),
                   (wx + dx * wing_w // 2, by + br)]
            pygame.draw.polygon(screen, darken(color, 15), pts)
    else:
        # Feathered wings
        for dx in (-1, 1):
            wx = sx + dx * (br - 1)
            wing_c = darken(color, 10)
            pygame.draw.ellipse(screen, wing_c,
                                (wx - (wing_w if dx < 0 else 0), by + 2 + flap * dx,
                                 wing_w, wing_h))

    # Head
    hr = max(2, br)
    hx = sx
    hy = by - hr // 2
    # Big eyes for owl
    if cfg.get("eyes") == "big":
        pygame.draw.circle(screen, lighten(color, 15), (hx, hy), hr)
        for dx in (-hr // 3, hr // 3):
            pygame.draw.circle(screen, (220, 200, 50), (hx + dx, hy), max(1, hr // 2))
            pygame.draw.circle(screen, (30, 30, 30), (hx + dx, hy), max(1, hr // 3))
    else:
        pygame.draw.circle(screen, lighten(color, 10), (hx, hy), hr)
        draw_eye(screen, hx + hr // 3, hy - 1, max(1, cs // 4), "predator")

    # Beak
    beak = cfg.get("beak", "pointed")
    if beak == "hooked":
        pygame.draw.polygon(screen, (200, 170, 50),
                            [(hx + hr, hy), (hx + hr + cs, hy + 1),
                             (hx + hr, hy + cs // 3)])
    elif beak == "pointed":
        pygame.draw.polygon(screen, (200, 180, 60),
                            [(hx + hr - 1, hy - 1), (hx + hr + cs // 2, hy),
                             (hx + hr - 1, hy + 1)])
    elif beak == "round":
        pygame.draw.circle(screen, (180, 160, 50), (hx + hr, hy), max(1, cs // 4))

    # Comb (chicken)
    if cfg.get("comb"):
        pygame.draw.polygon(screen, (200, 40, 40),
                            [(hx - 1, hy - hr), (hx + 2, hy - hr - cs // 2),
                             (hx + 4, hy - hr)])

    # Tail feathers
    if cfg.get("tail_long"):
        for i in range(3):
            pygame.draw.line(screen, darken(color, 10 + i * 5),
                             (sx, by + br), (sx - cs - i * 2, by + br + cs // 2 + i),
                             max(1, cs // 4))
    else:
        pygame.draw.polygon(screen, darken(color, 15),
                            [(sx - br // 2, by + br),
                             (sx - br - cs // 2, by + br + cs // 3),
                             (sx - br // 2 + 2, by + br + 1)])

    # Fire effect (phoenix)
    if cfg.get("fire"):
        for i in range(4):
            fx = sx + int(_sin(walk_sin * 3 + i) * cs)
            fy = by - cs // 2 + int(_cos(walk_sin * 2 + i) * cs // 2)
            pygame.draw.circle(screen, (255, 160 + i * 20, 30), (fx, fy), max(1, cs // 3))

    # Legs (tiny, only for standing birds)
    if cfg.get("size") != "small" or cfg.get("beak") == "pointed":
        leg_h = max(1, cs // 2)
        swing = int(walk_sin * cs * 0.2)
        pygame.draw.line(screen, (180, 150, 80),
                         (sx - 2, by + int(br * 1.5)),
                         (sx - 2, by + int(br * 1.5) + leg_h + swing), max(1, cs // 4))
        pygame.draw.line(screen, (180, 150, 80),
                         (sx + 2, by + int(br * 1.5)),
                         (sx + 2, by + int(br * 1.5) + leg_h - swing), max(1, cs // 4))


def draw_serpent(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Snake, viper — sinusoidal body, no legs."""
    seg_count = max(4, cs * 2)
    seg_r = max(1, cs // 2)
    for i in range(seg_count):
        t = i / seg_count
        px = sx + int((t - 0.5) * cs * 4)
        py = sy + int(_sin(t * 6 + walk_sin * 2) * cs * 0.8)
        r = max(1, int(seg_r * (1.0 - t * 0.5)))  # taper toward tail
        pygame.draw.circle(screen, color, (px, py), r)
    # Head (wider)
    hx = sx - cs * 2
    hy = sy + int(_sin(walk_sin * 2) * cs * 0.5)
    hr = max(2, seg_r + 1)
    if cfg.get("head_wide"):
        pygame.draw.ellipse(screen, lighten(color, 10),
                            (hx - hr * 2, hy - hr, hr * 3, hr * 2))
    else:
        pygame.draw.circle(screen, lighten(color, 10), (hx, hy), hr)
    # Eyes
    draw_eye(screen, hx - hr // 2, hy - hr // 3, max(1, cs // 4), "predator")
    # Tongue
    pygame.draw.line(screen, (200, 50, 50), (hx - hr, hy),
                     (hx - hr - cs, hy + int(_sin(walk_sin * 5) * 2)), 1)


def draw_reptile(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Crocodile, turtle, basilisk — low flat body."""
    shape = cfg.get("shape", "long")
    if shape == "shell":
        # Turtle — dome shell
        shell_w = max(4, cs * 3)
        shell_h = max(3, cs * 2)
        pygame.draw.ellipse(screen, color, (sx - shell_w // 2, sy - shell_h, shell_w, shell_h))
        # Shell pattern
        pygame.draw.ellipse(screen, darken(color, 15),
                            (sx - shell_w // 2, sy - shell_h, shell_w, shell_h), 1)
        # Head poking out
        pygame.draw.circle(screen, lighten(color, 20), (sx + shell_w // 2, sy - shell_h // 2),
                           max(1, cs // 2))
        # Tiny legs
        for dx, dy in [(-cs, cs // 2), (cs, cs // 2), (-cs, -cs // 3), (cs, -cs // 3)]:
            pygame.draw.rect(screen, darken(color, 20),
                             (sx + dx, sy - shell_h // 2 + dy, max(1, cs // 3), max(1, cs // 3)))
    else:
        # Crocodile / basilisk — long flat body
        body_w = max(6, cs * 5)
        body_h = max(2, cs)
        pygame.draw.ellipse(screen, color,
                            (sx - body_w // 2, sy - body_h // 2 + int(breath), body_w, body_h))
        # Scales pattern
        for i in range(0, body_w, max(2, cs)):
            pygame.draw.circle(screen, darken(color, 10),
                               (sx - body_w // 2 + i, sy + int(breath)), max(1, cs // 4))
        # Stubby legs
        swing = int(walk_sin * cs * 0.3)
        for i, (dx, dy) in enumerate([(-cs, 0), (cs, 0), (-cs - cs // 2, 0), (cs + cs // 2, 0)]):
            lo = swing if i % 2 == 0 else -swing
            pygame.draw.rect(screen, darken(color, 20),
                             (sx + dx, sy + body_h // 2 + lo, max(1, cs // 3), max(1, cs // 2)))
        # Jaws
        if cfg.get("jaws"):
            jx = sx + body_w // 2
            jy = sy + int(breath)
            pygame.draw.polygon(screen, lighten(color, 15),
                                [(jx, jy - cs // 2), (jx + cs, jy), (jx, jy + cs // 2)])
            # Teeth
            for ty in range(jy - cs // 3, jy + cs // 3, max(1, cs // 3)):
                pygame.draw.line(screen, (230, 230, 220), (jx + cs // 2, ty),
                                 (jx + cs // 2 + 1, ty + 1), 1)
        # Eyes
        draw_eye(screen, sx + body_w // 3, sy - body_h // 3, max(1, cs // 4),
                 cfg.get("eyes", "predator"))


def draw_arachnid(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Spiders, scorpions — central body + radiating legs."""
    br = max(2, cs + 1)
    # Body
    pygame.draw.circle(screen, color, (sx, sy), br)
    # Abdomen (rear, larger for spiders)
    abd_r = max(2, int(br * 1.3))
    pygame.draw.circle(screen, darken(color, 10), (sx - br, sy), abd_r)
    # Pattern on abdomen
    if cs >= 3:
        pygame.draw.circle(screen, lighten(color, 20), (sx - br, sy - abd_r // 3),
                           max(1, abd_r // 3))

    # Legs
    num_legs = cfg.get("legs", 8)
    for i in range(num_legs):
        angle = math.pi * 2 * i / num_legs
        phase = walk_sin * (3 if i % 2 == 0 else -3) * 0.02
        # Leg has two segments (bent)
        mid_r = br * 1.5
        end_r = br * 2.5 + phase * cs
        mid_x = sx + int(math.cos(angle) * mid_r)
        mid_y = sy + int(math.sin(angle) * mid_r)
        end_x = sx + int(math.cos(angle + 0.3) * end_r)
        end_y = sy + int(math.sin(angle + 0.3) * end_r)
        pygame.draw.line(screen, color, (sx, sy), (mid_x, mid_y), max(1, cs // 3))
        pygame.draw.line(screen, darken(color, 15), (mid_x, mid_y), (end_x, end_y),
                         max(1, cs // 4))

    # Fangs
    if cfg.get("fangs"):
        pygame.draw.line(screen, (200, 200, 190), (sx + br, sy - 1),
                         (sx + br + cs // 2, sy + cs // 3), max(1, cs // 4))
        pygame.draw.line(screen, (200, 200, 190), (sx + br, sy + 1),
                         (sx + br + cs // 2, sy - cs // 3), max(1, cs // 4))

    # Eyes (cluster)
    for dx, dy in [(br // 2, -br // 3), (br // 2 + 2, -1), (br // 2, br // 3)]:
        pygame.draw.circle(screen, (200, 40, 40), (sx + dx, sy + dy), max(1, cs // 5))

    # Scorpion tail
    if cfg.get("tail_sting"):
        for i in range(4):
            t = i / 4
            tx = sx - br - int(t * cs * 2)
            ty = sy - int(t * t * cs * 3)
            pygame.draw.circle(screen, color, (tx, ty), max(1, cs // 3))
        pygame.draw.circle(screen, (200, 50, 50), (tx - cs // 2, ty - cs // 3),
                           max(1, cs // 3))

    # Claws
    if cfg.get("claws"):
        for dy in (-br, br):
            pygame.draw.line(screen, darken(color, 10),
                             (sx + br, sy + dy),
                             (sx + br + cs, sy + dy + (cs // 3 if dy > 0 else -cs // 3)),
                             max(1, cs // 3))


def draw_aquatic(screen, sx, sy, cs, color, walk_sin, breath, cfg):
    """Fish, fish school, crabs."""
    shape = cfg.get("shape", "fish")
    if shape == "school":
        # Multiple small fish
        for i in range(4):
            fx = sx + int(_sin(i * 2.5 + walk_sin) * cs * 2)
            fy = sy + int(_cos(i * 1.7 + walk_sin) * cs)
            fr = max(1, cs // 2)
            pygame.draw.ellipse(screen, color, (fx - fr, fy - fr // 2, fr * 2, fr))
            pygame.draw.polygon(screen, darken(color, 15),
                                [(fx - fr, fy), (fx - fr - fr, fy - fr // 2),
                                 (fx - fr, fy + fr // 3)])
    elif shape == "crab":
        # Crab — wide body + claws
        bw = max(4, cs * 3)
        bh = max(2, cs * 2)
        pygame.draw.ellipse(screen, color, (sx - bw // 2, sy - bh // 2, bw, bh))
        # Claws
        for dx in (-1, 1):
            cx = sx + dx * (bw // 2 + cs // 2)
            pygame.draw.circle(screen, lighten(color, 10), (cx, sy - cs // 2), max(1, cs))
            pygame.draw.line(screen, darken(color, 10),
                             (cx - cs // 3, sy - cs), (cx + cs // 3, sy - cs), max(1, cs // 3))
        # Eyes on stalks
        for dx in (-cs // 2, cs // 2):
            pygame.draw.line(screen, color, (sx + dx, sy - bh // 2),
                             (sx + dx, sy - bh // 2 - cs // 2), 1)
            pygame.draw.circle(screen, (30, 30, 30), (sx + dx, sy - bh // 2 - cs // 2),
                               max(1, cs // 5))
        # Legs
        swing = int(walk_sin * cs * 0.2)
        for i in range(3):
            for dx in (-1, 1):
                lx = sx + dx * (cs + i * cs // 2)
                pygame.draw.line(screen, darken(color, 20),
                                 (lx, sy + bh // 4),
                                 (lx + dx * cs // 2, sy + bh // 2 + cs // 2 + (swing if i % 2 == 0 else -swing)),
                                 max(1, cs // 4))
    else:
        # Single fish
        bw = max(3, cs * 3)
        bh = max(2, cs)
        pygame.draw.ellipse(screen, color, (sx - bw // 2, sy - bh // 2, bw, bh))
        # Tail fin
        pygame.draw.polygon(screen, darken(color, 10),
                            [(sx - bw // 2, sy), (sx - bw // 2 - cs, sy - cs // 2),
                             (sx - bw // 2 - cs, sy + cs // 2)])
        # Dorsal fin
        pygame.draw.polygon(screen, darken(color, 15),
                            [(sx - cs // 2, sy - bh // 2), (sx + cs // 2, sy - bh // 2),
                             (sx, sy - bh // 2 - cs // 2)])
        draw_eye(screen, sx + bw // 4, sy - 1, max(1, cs // 4), "gentle")
