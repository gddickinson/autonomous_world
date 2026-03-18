"""Shared drawing primitives for creature sprites."""

import pygame
import math

_sin = math.sin
_cos = math.cos


def darken(color, amount=30):
    return (max(0, color[0] - amount), max(0, color[1] - amount),
            max(0, color[2] - amount))


def lighten(color, amount=30):
    return (min(255, color[0] + amount), min(255, color[1] + amount),
            min(255, color[2] + amount))


def draw_eye(screen, x, y, r, style="predator"):
    """Draw an eye at (x, y) with radius r."""
    if style == "predator":
        pygame.draw.circle(screen, (220, 50, 40), (x, y), max(1, r))
        if r >= 2:
            pygame.draw.circle(screen, (255, 200, 50), (x, y), max(1, r - 1))
            pygame.draw.circle(screen, (30, 30, 30), (x, y), max(1, r // 2))
    elif style == "gentle":
        pygame.draw.circle(screen, (50, 35, 20), (x, y), max(1, r))
        if r >= 2:
            pygame.draw.circle(screen, (80, 60, 40), (x, y), max(1, r - 1))
    elif style == "glowing":
        pygame.draw.circle(screen, (180, 255, 180), (x, y), max(1, r))
    elif style == "undead":
        pygame.draw.circle(screen, (180, 200, 80), (x, y), max(1, r))
        if r >= 2:
            pygame.draw.circle(screen, (30, 30, 20), (x, y), max(1, r // 2))
    else:
        pygame.draw.circle(screen, (40, 40, 40), (x, y), max(1, r))


def draw_legs_quad(screen, cx, by, body_h, cs, color, walk_sin, offsets=None):
    """Draw 4 legs for a quadruped. Returns foot positions."""
    leg_w = max(1, cs // 3)
    leg_h = max(2, cs)
    dark = darken(color, 25)
    swing = int(walk_sin * cs * 0.4)
    if offsets is None:
        offsets = [-cs, -cs // 3, cs // 3, cs]
    feet = []
    for i, lx in enumerate(offsets):
        lo = swing if i % 2 == 0 else -swing
        fx = cx + lx
        fy = by + body_h + lo
        pygame.draw.rect(screen, dark, (fx - leg_w // 2, fy, leg_w, leg_h))
        # Hoof/paw
        pygame.draw.rect(screen, darken(color, 40),
                         (fx - leg_w // 2 - 1, fy + leg_h, leg_w + 2, max(1, cs // 4)))
        feet.append((fx, fy + leg_h))
    return feet


def draw_legs_biped(screen, cx, by, body_h, cs, color, walk_sin):
    """Draw 2 legs for a bipedal creature."""
    leg_w = max(1, cs // 2)
    leg_h = max(3, int(cs * 1.5))
    dark = darken(color, 20)
    swing = int(walk_sin * cs * 0.4)
    for i, dx in enumerate((-cs // 3, cs // 3)):
        lo = swing if i == 0 else -swing
        pygame.draw.rect(screen, dark,
                         (cx + dx - leg_w // 2, by + body_h + lo, leg_w, leg_h))
        # Foot
        pygame.draw.rect(screen, darken(color, 35),
                         (cx + dx - leg_w // 2 - 1, by + body_h + leg_h + lo,
                          leg_w + 3, max(1, cs // 3)))


def draw_tail(screen, x, y, length, color, style="thin", walk_sin=0):
    """Draw a tail from (x, y) extending left/up."""
    wag = int(walk_sin * length * 0.2)
    if style == "bushy":
        w = max(2, length // 2)
        pts = [(x, y), (x - length, y - length // 2 + wag),
               (x - length + w, y - length // 3 + wag)]
        pygame.draw.polygon(screen, color, pts)
    elif style == "thin":
        pygame.draw.line(screen, color, (x, y),
                         (x - length, y - length // 3 + wag), max(1, length // 6))
    elif style == "curly":
        for i in range(3):
            t = i / 3
            px = x - int(length * t)
            py = y - int(length * 0.3 * t) + int(math.sin(t * 4 + walk_sin) * length * 0.15)
            pygame.draw.circle(screen, color, (px, py), max(1, length // 5 - i))


def draw_ears(screen, lx, rx, y, size, color, style="pointed"):
    """Draw ears at given positions."""
    if style == "pointed":
        for ex in (lx, rx):
            pts = [(ex - size // 2, y + size // 2), (ex, y - size),
                   (ex + size // 2, y + size // 2)]
            pygame.draw.polygon(screen, color, pts)
            pygame.draw.polygon(screen, lighten(color, 20), pts, 1)
    elif style == "round":
        for ex in (lx, rx):
            pygame.draw.circle(screen, color, (ex, y), max(1, size))
    elif style == "floppy":
        for i, ex in enumerate((lx, rx)):
            dx = -size if i == 0 else size
            pygame.draw.ellipse(screen, color,
                                (ex + dx // 2, y, abs(dx), size * 2))
    elif style == "horns":
        for i, ex in enumerate((lx, rx)):
            dx = -size // 2 if i == 0 else size // 2
            pygame.draw.line(screen, lighten(color, 40),
                             (ex, y), (ex + dx, y - size * 2), max(1, size // 3))
    elif style == "antlers":
        for i, ex in enumerate((lx, rx)):
            dx = -1 if i == 0 else 1
            # Main beam
            pygame.draw.line(screen, (140, 120, 80),
                             (ex, y), (ex + dx * size, y - size * 3), max(1, size // 3))
            # Tines
            pygame.draw.line(screen, (130, 110, 70),
                             (ex + dx * size // 2, y - size),
                             (ex + dx * size * 2, y - size * 2), max(1, size // 4))
