"""2D procedural sprites for siege engines, vehicles, and fortifications."""

import math
import pygame


def _dk(c, a=20):
    return (max(0, c[0] - a), max(0, c[1] - a), max(0, c[2] - a))


def _lt(c, a=15):
    return (min(255, c[0] + a), min(255, c[1] + a), min(255, c[2] + a))


# ── Siege Engines ────────────────────────────────────────────────────────

def draw_battering_ram(screen, sx, sy, cs, firing=False):
    """Battering ram — heavy log on a wheeled frame."""
    w = cs * 6
    h = cs * 2
    color = (110, 80, 45)
    # Frame (low rectangle)
    pygame.draw.rect(screen, _dk(color, 10), (sx - w // 2, sy - h // 4, w, h // 2))
    # Main log (thick horizontal beam)
    log_h = max(2, cs)
    pygame.draw.rect(screen, color, (sx - w // 2 - cs, sy - log_h // 2, w + cs * 2, log_h),
                     border_radius=max(1, cs // 2))
    # Ram head (metal cap)
    ram_x = sx + w // 2 + cs
    if firing:
        ram_x += cs  # extends forward when firing
    pygame.draw.circle(screen, (160, 160, 170), (ram_x, sy), max(2, cs))
    pygame.draw.circle(screen, (130, 130, 140), (ram_x, sy), max(2, cs), 1)
    # Wheels
    for wx in (-w // 3, w // 3):
        pygame.draw.circle(screen, (60, 50, 40), (sx + wx, sy + h // 2), max(2, cs))
        pygame.draw.circle(screen, (80, 70, 55), (sx + wx, sy + h // 2), max(1, cs - 1), 1)
    # Handles/ropes
    for hx in (-w // 4, 0, w // 4):
        pygame.draw.line(screen, (140, 120, 80),
                         (sx + hx, sy - h // 4), (sx + hx, sy - h // 2 - cs), max(1, cs // 3))


def draw_catapult(screen, sx, sy, cs, firing=False):
    """Catapult — wheeled platform with throwing arm."""
    w = cs * 5
    h = cs * 4
    color = (120, 90, 50)
    # Base platform
    pygame.draw.rect(screen, color, (sx - w // 2, sy, w, cs * 2))
    pygame.draw.rect(screen, _dk(color), (sx - w // 2, sy, w, cs * 2), 1)
    # Wheels
    for wx in (-w // 3, w // 3):
        pygame.draw.circle(screen, (60, 50, 40), (sx + wx, sy + cs * 2), max(2, cs))
    # Throwing arm
    arm_angle = -60 if not firing else -20
    arm_len = cs * 4
    rad = math.radians(arm_angle)
    arm_end_x = sx + int(math.cos(rad) * arm_len)
    arm_end_y = sy + int(math.sin(rad) * arm_len)
    pygame.draw.line(screen, (100, 75, 40), (sx, sy), (arm_end_x, arm_end_y),
                     max(2, cs // 2))
    # Bucket at end
    pygame.draw.circle(screen, (90, 70, 45), (arm_end_x, arm_end_y), max(2, cs))
    # Stone in bucket (if not firing)
    if not firing:
        pygame.draw.circle(screen, (140, 130, 120), (arm_end_x, arm_end_y - 1), max(1, cs // 2))
    # Pivot post
    pygame.draw.rect(screen, _dk(color, 15), (sx - cs // 2, sy - cs * 2, cs, cs * 2))


def draw_trebuchet(screen, sx, sy, cs, firing=False):
    """Trebuchet — massive counterweight engine."""
    w = cs * 7
    h = cs * 5
    color = (100, 75, 40)
    # Base frame (A-frame)
    pygame.draw.rect(screen, color, (sx - w // 2, sy + cs, w, cs * 2))
    # Wheels (large)
    for wx in (-w // 3, w // 3):
        wr = max(3, int(cs * 1.5))
        pygame.draw.circle(screen, (55, 45, 35), (sx + wx, sy + cs * 3), wr)
        pygame.draw.circle(screen, (75, 65, 50), (sx + wx, sy + cs * 3), wr, 1)
        # Spokes
        for a in range(0, 360, 60):
            ex = sx + wx + int(math.cos(math.radians(a)) * wr * 0.7)
            ey = sy + cs * 3 + int(math.sin(math.radians(a)) * wr * 0.7)
            pygame.draw.line(screen, (75, 65, 50), (sx + wx, sy + cs * 3), (ex, ey), 1)
    # Tall pivot frame
    pygame.draw.polygon(screen, _dk(color),
                        [(sx - cs, sy + cs), (sx + cs, sy + cs), (sx, sy - cs * 3)])
    # Throwing arm (long beam)
    arm_angle = -70 if not firing else -30
    arm_len = cs * 5
    rad = math.radians(arm_angle)
    arm_x = sx + int(math.cos(rad) * arm_len)
    arm_y = sy - cs * 2 + int(math.sin(rad) * arm_len)
    pygame.draw.line(screen, (90, 65, 35), (sx, sy - cs * 2), (arm_x, arm_y),
                     max(2, cs // 2))
    # Counterweight (heavy end, opposite to sling)
    cw_rad = math.radians(arm_angle + 180)
    cw_x = sx + int(math.cos(cw_rad) * cs * 2)
    cw_y = sy - cs * 2 + int(math.sin(cw_rad) * cs * 2)
    pygame.draw.rect(screen, (80, 80, 90), (cw_x - cs, cw_y - cs, cs * 2, cs * 2))
    # Sling with stone
    if not firing:
        pygame.draw.line(screen, (120, 100, 60), (arm_x, arm_y),
                         (arm_x + cs, arm_y + cs), 1)
        pygame.draw.circle(screen, (140, 130, 120), (arm_x + cs, arm_y + cs),
                           max(2, cs))


def draw_siege_tower(screen, sx, sy, cs, moving=False):
    """Siege tower — tall wooden structure on wheels."""
    w = cs * 4
    h = cs * 8
    color = (130, 100, 60)
    # Main body (tall rectangle)
    pygame.draw.rect(screen, color, (sx - w // 2, sy - h + cs * 2, w, h))
    pygame.draw.rect(screen, _dk(color), (sx - w // 2, sy - h + cs * 2, w, h), 1)
    # Floor levels (horizontal lines)
    for i in range(1, 4):
        y = sy - h + cs * 2 + i * h // 4
        pygame.draw.line(screen, _dk(color, 15), (sx - w // 2 + 1, y),
                         (sx + w // 2 - 1, y), 1)
    # Arrow slits (small dark rectangles)
    for i in range(3):
        for dx in (-w // 4, w // 4):
            slit_y = sy - h + cs * 3 + i * h // 4
            pygame.draw.rect(screen, (40, 35, 30),
                             (sx + dx - 1, slit_y, 2, cs))
    # Drawbridge at top (drops down to wall)
    bridge_y = sy - h + cs * 2
    pygame.draw.rect(screen, _lt(color, 10),
                     (sx + w // 2, bridge_y, w // 2, cs * 2))
    # Wheels
    for wx in (-w // 3, w // 3):
        pygame.draw.circle(screen, (55, 45, 35), (sx + wx, sy + cs * 2),
                           max(3, int(cs * 1.3)))
    # Roof (peaked)
    pygame.draw.polygon(screen, _dk(color, 10),
                        [(sx - w // 2, sy - h + cs * 2),
                         (sx + w // 2, sy - h + cs * 2),
                         (sx, sy - h)])


# ── Vehicles ─────────────────────────────────────────────────────────────

def draw_handcart(screen, sx, sy, cs, goods_color=None):
    """Handcart — small single-wheel pushcart."""
    color = (160, 130, 80)
    bw, bh = cs * 3, cs * 2
    # Cart body
    pygame.draw.rect(screen, color, (sx - bw // 2, sy - bh // 2, bw, bh))
    pygame.draw.rect(screen, _dk(color), (sx - bw // 2, sy - bh // 2, bw, bh), 1)
    # Wheel (single, front)
    pygame.draw.circle(screen, (60, 50, 40), (sx + bw // 2, sy + bh // 4), max(2, cs))
    # Handles (two lines extending back)
    for dy in (-bh // 3, bh // 3):
        pygame.draw.line(screen, (120, 100, 60),
                         (sx - bw // 2, sy + dy), (sx - bw // 2 - cs * 2, sy + dy),
                         max(1, cs // 3))
    # Cargo
    if goods_color:
        pygame.draw.rect(screen, goods_color,
                         (sx - bw // 4, sy - bh // 2 + 1, bw // 2, bh // 3))


def draw_cart(screen, sx, sy, cs, goods_color=None, draft_animal=False):
    """Cart — two-wheeled cart, optionally pulled by animal."""
    color = (140, 110, 70)
    bw, bh = cs * 4, cs * 2
    # Cart body
    pygame.draw.rect(screen, color, (sx - bw // 2, sy - bh // 2, bw, bh))
    pygame.draw.rect(screen, _dk(color), (sx - bw // 2, sy - bh // 2, bw, bh), 1)
    # Side rails
    pygame.draw.rect(screen, _dk(color, 10),
                     (sx - bw // 2, sy - bh // 2 - cs // 2, bw, cs // 2))
    # Two wheels
    for wx in (-bw // 4, bw // 4):
        pygame.draw.circle(screen, (55, 45, 35), (sx + wx, sy + bh // 2), max(2, cs))
        pygame.draw.circle(screen, (75, 65, 50), (sx + wx, sy + bh // 2), max(2, cs), 1)
    # Yoke/shaft extending forward
    pygame.draw.line(screen, (100, 80, 50),
                     (sx + bw // 2, sy), (sx + bw // 2 + cs * 3, sy), max(1, cs // 2))
    # Cargo
    if goods_color:
        pygame.draw.rect(screen, goods_color,
                         (sx - bw // 3, sy - bh // 2 + 1, bw * 2 // 3, bh // 3))


def draw_wagon(screen, sx, sy, cs, goods_color=None, draft_animal=False):
    """Wagon — four-wheeled covered wagon."""
    color = (120, 90, 50)
    bw, bh = cs * 6, cs * 3
    # Wagon body
    pygame.draw.rect(screen, color, (sx - bw // 2, sy - bh // 3, bw, bh // 2))
    pygame.draw.rect(screen, _dk(color), (sx - bw // 2, sy - bh // 3, bw, bh // 2), 1)
    # Canvas cover (arched top)
    cover_pts = [(sx - bw // 2, sy - bh // 3),
                 (sx - bw // 3, sy - bh // 3 - cs * 2),
                 (sx + bw // 3, sy - bh // 3 - cs * 2),
                 (sx + bw // 2, sy - bh // 3)]
    pygame.draw.polygon(screen, (180, 170, 150), cover_pts)
    pygame.draw.polygon(screen, (150, 140, 125), cover_pts, 1)
    # Canvas ribs
    for i in range(3):
        rx = sx - bw // 3 + i * bw // 3
        pygame.draw.line(screen, (160, 150, 130),
                         (rx, sy - bh // 3 - cs * 2), (rx, sy - bh // 3), 1)
    # Four wheels
    for wx in (-bw // 3, -bw // 6, bw // 6, bw // 3):
        wr = max(2, int(cs * 1.2))
        pygame.draw.circle(screen, (55, 45, 35), (sx + wx, sy + bh // 6), wr)
    # Shaft
    pygame.draw.line(screen, (100, 80, 50),
                     (sx + bw // 2, sy), (sx + bw // 2 + cs * 3, sy), max(1, cs // 2))
    # Cargo indicator
    if goods_color:
        pygame.draw.rect(screen, goods_color,
                         (sx - bw // 4, sy - bh // 3 + 1, bw // 2, bh // 4))


def draw_supply_wagon(screen, sx, sy, cs, goods_color=None):
    """Supply wagon — heavy military wagon."""
    color = (110, 85, 45)
    bw, bh = cs * 7, cs * 3
    # Heavy body
    pygame.draw.rect(screen, color, (sx - bw // 2, sy - bh // 3, bw, bh * 2 // 3))
    pygame.draw.rect(screen, _dk(color), (sx - bw // 2, sy - bh // 3, bw, bh * 2 // 3), 1)
    # Reinforced sides (darker bands)
    for i in range(3):
        band_y = sy - bh // 3 + i * bh // 4
        pygame.draw.line(screen, _dk(color, 15),
                         (sx - bw // 2, band_y), (sx + bw // 2, band_y), max(1, cs // 3))
    # Metal corner brackets
    for cx, cy in [(-bw // 2, -bh // 3), (bw // 2 - cs, -bh // 3),
                   (-bw // 2, bh // 3 - cs), (bw // 2 - cs, bh // 3 - cs)]:
        pygame.draw.rect(screen, (100, 100, 110), (sx + cx, sy + cy, cs, cs))
    # Heavy wheels (6)
    for wx in (-bw // 3, 0, bw // 3):
        wr = max(3, int(cs * 1.3))
        pygame.draw.circle(screen, (50, 42, 32), (sx + wx, sy + bh // 3), wr)
    # Shaft
    pygame.draw.line(screen, (90, 70, 40),
                     (sx + bw // 2, sy), (sx + bw // 2 + cs * 4, sy),
                     max(2, cs // 2))
    if goods_color:
        pygame.draw.rect(screen, goods_color,
                         (sx - bw // 3, sy - bh // 3 + 2, bw * 2 // 3, bh // 4))


# ── Fortifications ──────────────────────────────────────────────────────

def draw_palisade(screen, sx, sy, cs):
    """Wooden palisade — pointed log wall section."""
    w = cs * 3
    h = cs * 4
    color = (110, 80, 45)
    # Vertical logs
    log_w = max(2, cs)
    for i in range(w // log_w + 1):
        lx = sx - w // 2 + i * log_w
        # Pointed top
        pts = [(lx, sy + h // 2), (lx + log_w, sy + h // 2),
               (lx + log_w, sy - h // 2 + cs), (lx + log_w // 2, sy - h // 2),
               (lx, sy - h // 2 + cs)]
        shade = (i * 5) % 15
        pygame.draw.polygon(screen, (color[0] + shade, color[1] + shade, color[2]),
                            pts)
        pygame.draw.polygon(screen, _dk(color), pts, 1)


def draw_stone_wall(screen, sx, sy, cs):
    """Stone wall segment with brick pattern."""
    w = cs * 3
    h = cs * 3
    color = (130, 125, 115)
    pygame.draw.rect(screen, color, (sx - w // 2, sy - h // 2, w, h))
    # Brick pattern
    brick_h = max(2, cs)
    brick_w = max(3, cs * 2)
    for row in range(h // brick_h):
        offset = brick_w // 2 if row % 2 else 0
        by = sy - h // 2 + row * brick_h
        for col in range(-1, w // brick_w + 2):
            bx = sx - w // 2 + col * brick_w + offset
            pygame.draw.rect(screen, _dk(color, 8),
                             (bx, by, brick_w - 1, brick_h - 1))
    pygame.draw.rect(screen, _dk(color, 20), (sx - w // 2, sy - h // 2, w, h), 1)
    # Crenellations on top
    for i in range(0, w, max(2, cs * 2)):
        if (i // max(2, cs * 2)) % 2 == 0:
            pygame.draw.rect(screen, _lt(color, 5),
                             (sx - w // 2 + i, sy - h // 2 - cs, max(2, cs), cs))


def draw_tower(screen, sx, sy, cs):
    """Defensive tower with arrow slits."""
    w = cs * 4
    h = cs * 6
    color = (120, 115, 105)
    pygame.draw.rect(screen, color, (sx - w // 2, sy - h // 2, w, h))
    pygame.draw.rect(screen, _dk(color, 15), (sx - w // 2, sy - h // 2, w, h), 1)
    # Arrow slits
    for i in range(2):
        for dx in (-w // 4, w // 4):
            slit_y = sy - h // 4 + i * h // 3
            pygame.draw.rect(screen, (40, 35, 30),
                             (sx + dx - 1, slit_y, 2, cs))
    # Crenellations
    for i in range(0, w, max(2, cs * 2)):
        if (i // max(2, cs * 2)) % 2 == 0:
            pygame.draw.rect(screen, _lt(color, 8),
                             (sx - w // 2 + i, sy - h // 2 - cs, max(2, cs), cs))
    # Flag on top
    pole_x = sx
    pygame.draw.line(screen, (80, 70, 60), (pole_x, sy - h // 2 - cs),
                     (pole_x, sy - h // 2 - cs * 3), max(1, cs // 4))
    pygame.draw.polygon(screen, (180, 40, 40),
                        [(pole_x, sy - h // 2 - cs * 3),
                         (pole_x + cs * 2, sy - h // 2 - cs * 2),
                         (pole_x, sy - h // 2 - cs)])


def draw_gate(screen, sx, sy, cs, open_state=False):
    """Gate — portcullis/entry gate."""
    w = cs * 4
    h = cs * 4
    color = (100, 80, 55)
    # Gate frame (stone sides)
    side_w = max(2, cs)
    pygame.draw.rect(screen, (120, 115, 105),
                     (sx - w // 2, sy - h // 2, side_w, h))
    pygame.draw.rect(screen, (120, 115, 105),
                     (sx + w // 2 - side_w, sy - h // 2, side_w, h))
    # Arch top
    pygame.draw.arc(screen, (120, 115, 105),
                    (sx - w // 2 + side_w, sy - h // 2 - cs,
                     w - side_w * 2, cs * 3), 0, 3.14, max(1, cs // 2))
    if not open_state:
        # Portcullis bars (iron gate)
        gate_color = (80, 80, 90)
        for i in range(side_w + 1, w - side_w, max(2, cs)):
            gx = sx - w // 2 + i
            pygame.draw.line(screen, gate_color, (gx, sy - h // 4), (gx, sy + h // 2), 1)
        for gy in range(0, h * 3 // 4, max(2, cs)):
            pygame.draw.line(screen, gate_color,
                             (sx - w // 2 + side_w, sy - h // 4 + gy),
                             (sx + w // 2 - side_w, sy - h // 4 + gy), 1)
