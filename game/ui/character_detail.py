"""Enhanced character body-part drawing — detailed heads, torsos, limbs.

Provides helper functions called by character_anim.py and player_anim.py
to draw more detailed pixel-art body parts instead of plain geometric shapes.
"""

import math
import pygame

_sin = math.sin
_cos = math.cos

# ── Race width multipliers (wider/thinner builds) ────────────────────────
RACE_WIDTH = {
    "human": 1.0, "elf": 0.85, "half-elf": 0.9, "tiefling": 0.95,
    "dwarf": 1.25, "halfling": 0.9, "gnome": 0.9,
    "half-orc": 1.3, "orc": 1.35, "goliath": 1.4,
    "dragonborn": 1.2, "goblin": 0.85,
}

# ── Hair colors by race ──────────────────────────────────────────────────
HAIR_COLORS = {
    "human": [(80, 50, 30), (140, 100, 60), (40, 30, 20), (180, 140, 80),
              (120, 50, 30)],
    "elf": [(200, 190, 140), (180, 160, 120), (100, 80, 60), (220, 210, 170)],
    "dwarf": [(100, 60, 30), (160, 90, 40), (60, 40, 20), (140, 80, 40)],
    "halfling": [(120, 80, 40), (100, 70, 35), (80, 55, 25)],
    "half-orc": [(40, 40, 30), (60, 50, 35), (30, 30, 25)],
    "orc": [(30, 30, 25), (50, 45, 30)],
    "goblin": [(30, 40, 20), (50, 50, 30)],
    "gnome": [(160, 120, 70), (140, 100, 50), (100, 70, 40)],
    "tiefling": [(50, 20, 30), (80, 30, 40), (30, 15, 20)],
    "dragonborn": [],  # no hair
    "goliath": [(60, 50, 40)],
}

_hair_cache = {}


def _get_hair_color(race: str, entity_id: int) -> tuple:
    """Deterministic hair color based on race and entity identity."""
    key = (race, entity_id)
    cached = _hair_cache.get(key)
    if cached is not None:
        return cached
    r = race.lower() if race else "human"
    colors = HAIR_COLORS.get(r, HAIR_COLORS["human"])
    if not colors:
        result = None
    else:
        result = colors[entity_id % len(colors)]
    _hair_cache[key] = result
    return result


def _race_width(race: str) -> float:
    return RACE_WIDTH.get(race.lower() if race else "", 1.0)


def _darken(c, a=30):
    return (max(0, c[0] - a), max(0, c[1] - a), max(0, c[2] - a))


def _lighten(c, a=30):
    return (min(255, c[0] + a), min(255, c[1] + a), min(255, c[2] + a))


# ── Head detail ──────────────────────────────────────────────────────────

def draw_detailed_head(screen, skin, head_x, head_y, head_r, rs, race,
                       entity_id, facing=(0, 1), talking=False):
    """Draw an enhanced head with hair, ears, nose, and mouth detail."""
    draw = pygame.draw
    r_lower = race.lower() if race else "human"

    # Slightly oval head (wider than tall)
    head_w = max(3, int(head_r * 2.2))
    head_h = max(3, int(head_r * 1.9))
    draw.ellipse(screen, skin,
                 (head_x - head_w // 2, head_y - head_h // 2,
                  head_w, head_h))

    # Ears (small bumps on sides)
    if rs >= 2:
        ear_w = max(1, rs // 3)
        ear_h = max(2, rs // 2)
        ear_y = head_y - ear_h // 3
        # Elf ears: pointed and larger
        if r_lower in ("elf", "half-elf"):
            ear_h = max(3, rs)
            pts_l = [(head_x - head_w // 2, ear_y),
                     (head_x - head_w // 2 - ear_w - 1, ear_y - ear_h),
                     (head_x - head_w // 2, ear_y + ear_h // 2)]
            pts_r = [(head_x + head_w // 2, ear_y),
                     (head_x + head_w // 2 + ear_w + 1, ear_y - ear_h),
                     (head_x + head_w // 2, ear_y + ear_h // 2)]
            draw.polygon(screen, skin, pts_l)
            draw.polygon(screen, skin, pts_r)
        else:
            # Standard round ears
            draw.ellipse(screen, _darken(skin, 10),
                         (head_x - head_w // 2 - ear_w,
                          ear_y - ear_h // 2, ear_w + 1, ear_h))
            draw.ellipse(screen, _darken(skin, 10),
                         (head_x + head_w // 2 - 1,
                          ear_y - ear_h // 2, ear_w + 1, ear_h))

    # Hair (colored cap on top)
    hair_color = _get_hair_color(race, entity_id)
    if hair_color:
        hair_style = entity_id % 3  # 3 hair styles
        hy_top = head_y - head_h // 2
        if hair_style == 0:
            # Short crop: rectangle on top
            hw = max(3, int(head_w * 0.9))
            hh = max(2, head_h // 3)
            draw.rect(screen, hair_color,
                      (head_x - hw // 2, hy_top - 1, hw, hh),
                      border_radius=max(1, rs // 3))
        elif hair_style == 1:
            # Bowl cut: wider rectangle with rounded bottom
            hw = max(4, int(head_w * 1.05))
            hh = max(2, int(head_h * 0.45))
            draw.ellipse(screen, hair_color,
                         (head_x - hw // 2, hy_top - 2, hw, hh + 2))
        else:
            # Long hair: extends down sides
            hw = max(3, int(head_w * 0.95))
            hh = max(2, head_h // 3)
            draw.rect(screen, hair_color,
                      (head_x - hw // 2, hy_top - 1, hw, hh),
                      border_radius=max(1, rs // 3))
            # Side strands
            strand_h = max(2, head_h // 2)
            sw = max(1, rs // 3)
            draw.rect(screen, hair_color,
                      (head_x - head_w // 2 - 1, hy_top + hh - 1,
                       sw, strand_h))
            draw.rect(screen, hair_color,
                      (head_x + head_w // 2 - sw + 1, hy_top + hh - 1,
                       sw, strand_h))

    # Nose hint (1px dot)
    if rs >= 3:
        fx, fy = facing
        nose_x = head_x + int(fx * rs * 0.3)
        nose_y = head_y + max(1, head_h // 6)
        draw.rect(screen, _darken(skin, 20), (nose_x, nose_y, 1, 1))

    # Mouth line (visible when talking)
    if talking and rs >= 3:
        mouth_y = head_y + max(2, head_h // 4)
        mouth_w = max(2, head_w // 4)
        # Animated open/close
        draw.line(screen, _darken(skin, 40),
                  (head_x - mouth_w // 2, mouth_y),
                  (head_x + mouth_w // 2, mouth_y), 1)


# ── Eyes (enhanced) ──────────────────────────────────────────────────────

def draw_detailed_eyes(screen, head_x, head_y, head_r, rs, facing=(0, 1),
                       eye_color=(40, 40, 40)):
    """Draw eyes with pupils and white sclera."""
    if rs < 2:
        return
    draw = pygame.draw
    eye_r = max(1, rs // 3)
    fx, fy = facing
    eox = int(fx * rs * 0.3)
    eye_y = head_y - max(1, rs // 4) + int(fy * rs * 0.2)

    for dx in (-1, 1):
        ex = head_x + dx * (eye_r + 1) + eox
        # Sclera (white)
        if rs >= 4:
            draw.circle(screen, (235, 235, 235), (ex, eye_y), eye_r)
            # Pupil
            pupil_r = max(1, eye_r - 1)
            draw.circle(screen, eye_color,
                        (ex + int(fx * 0.5), eye_y + int(fy * 0.3)),
                        pupil_r)
        else:
            draw.circle(screen, eye_color, (ex, eye_y), eye_r)


# ── Torso detail ─────────────────────────────────────────────────────────

def draw_detailed_torso(screen, torso_x, torso_y, torso_w, torso_h,
                        torso_color, rs, char_class="", armored=False):
    """Draw enhanced torso with collar, belt, and armor texture."""
    draw = pygame.draw
    br = max(1, rs // 2)

    # Trapezoidal torso: wider at shoulders
    if rs >= 3:
        shoulder_extra = max(1, rs // 3)
        # Draw as polygon for trapezoid shape
        pts = [
            (torso_x - shoulder_extra, torso_y),  # top-left
            (torso_x + torso_w + shoulder_extra, torso_y),  # top-right
            (torso_x + torso_w, torso_y + torso_h),  # bottom-right
            (torso_x, torso_y + torso_h),  # bottom-left
        ]
        draw.polygon(screen, torso_color, pts)
        draw.polygon(screen, _darken(torso_color, 25), pts, 1)
    else:
        draw.rect(screen, torso_color,
                  (torso_x, torso_y, torso_w, torso_h),
                  border_radius=br)
        if rs >= 2:
            draw.rect(screen, _darken(torso_color, 25),
                      (torso_x, torso_y, torso_w, torso_h), 1,
                      border_radius=br)

    # Collar detail (V at neck)
    if rs >= 3:
        cx = torso_x + torso_w // 2
        cy = torso_y
        v_depth = max(2, rs)
        collar_c = _lighten(torso_color, 20)
        draw.line(screen, collar_c,
                  (cx - max(2, rs), cy), (cx, cy + v_depth), 1)
        draw.line(screen, collar_c,
                  (cx + max(2, rs), cy), (cx, cy + v_depth), 1)

    # Belt line (darker horizontal line at waist)
    if rs >= 2:
        belt_y = torso_y + torso_h - max(2, rs)
        belt_c = _darken(torso_color, 35)
        draw.line(screen, belt_c,
                  (torso_x + 1, belt_y),
                  (torso_x + torso_w - 1, belt_y), 1)
        # Belt buckle
        if rs >= 4:
            bk_x = torso_x + torso_w // 2
            draw.rect(screen, _lighten(belt_c, 30),
                      (bk_x - 1, belt_y - 1, 2, 2))

    # Armor texture (chainmail dots for fighters)
    if armored and rs >= 3:
        _draw_chainmail(screen, torso_x, torso_y, torso_w, torso_h,
                        torso_color, rs)

    # Robe texture (flowing lines for mages)
    if char_class in ("Wizard", "Sorcerer", "Warlock", "Druid", "Cleric"):
        _draw_robe_lines(screen, torso_x, torso_y, torso_w, torso_h,
                         torso_color, rs)


def _draw_chainmail(screen, tx, ty, tw, th, color, rs):
    """Draw chainmail dot pattern on torso."""
    dot_c = _lighten(color, 15)
    spacing = max(2, rs)
    for row in range(ty + 2, ty + th - 2, spacing):
        offset = (row // spacing) % 2
        for col in range(tx + 1 + offset, tx + tw - 1, spacing):
            screen.set_at((col, row), dot_c)


def _draw_robe_lines(screen, tx, ty, tw, th, color, rs):
    """Draw vertical flowing lines on robes."""
    if rs < 3:
        return
    line_c = _darken(color, 12)
    cx = tx + tw // 2
    # Center seam
    pygame.draw.line(screen, line_c, (cx, ty + 2), (cx, ty + th - 1), 1)
    # Side folds
    for dx in [-tw // 4, tw // 4]:
        pygame.draw.line(screen, line_c,
                         (cx + dx, ty + 3), (cx + dx, ty + th - 1), 1)


# ── Arm detail ───────────────────────────────────────────────────────────

def draw_detailed_arm(screen, ax, ay, arm_w, arm_h, arm_color, rs,
                      draw_hand=True, skin_color=None):
    """Draw an arm with wider shape and hand circle at end."""
    draw = pygame.draw
    # Slightly wider arm (2-3px)
    aw = max(2, arm_w + 1) if rs >= 3 else arm_w
    draw.rect(screen, arm_color, (ax, ay, aw, arm_h))

    # Hand as small circle at bottom
    if draw_hand and rs >= 3:
        hand_color = skin_color if skin_color else _lighten(arm_color, 15)
        hand_r = max(1, aw // 2 + 1)
        hand_x = ax + aw // 2
        hand_y = ay + arm_h
        draw.circle(screen, hand_color, (hand_x, hand_y), hand_r)


# ── Leg detail ───────────────────────────────────────────────────────────

def draw_detailed_legs(screen, sx, hip_y, rs, leg_w, leg_h, leg_color,
                       leg_swing, breath_offset, dark_color,
                       has_robe=False, race="human"):
    """Draw legs with boot shape and knee bend."""
    draw = pygame.draw
    lx = sx - rs
    rx = sx + rs - leg_w

    # Wider legs (pants)
    lw = max(2, leg_w + 1) if rs >= 3 else leg_w

    l_leg_y = hip_y + leg_swing + breath_offset
    r_leg_y = hip_y - leg_swing + breath_offset

    if has_robe:
        # Robe covers legs — draw single flowing shape
        robe_w = max(5, rs * 3)
        robe_h = max(4, leg_h + rs)
        robe_x = sx - robe_w // 2
        robe_c = dark_color
        draw.rect(screen, robe_c,
                  (robe_x, hip_y + breath_offset, robe_w, robe_h),
                  border_radius=max(1, rs // 3))
        # Robe hem detail
        if rs >= 3:
            hem_y = hip_y + breath_offset + robe_h - 1
            draw.line(screen, _darken(robe_c, 15),
                      (robe_x, hem_y), (robe_x + robe_w, hem_y), 1)
        return

    # Left leg
    draw.rect(screen, leg_color, (lx, l_leg_y, lw, leg_h))
    # Right leg
    draw.rect(screen, leg_color, (rx, r_leg_y, lw, leg_h))

    # Knee hint (darker line at mid-leg when walking)
    if rs >= 3 and abs(leg_swing) > 1:
        knee_y_l = l_leg_y + leg_h // 2
        knee_y_r = r_leg_y + leg_h // 2
        knee_c = _darken(leg_color, 15)
        draw.line(screen, knee_c, (lx, knee_y_l), (lx + lw, knee_y_l), 1)
        draw.line(screen, knee_c, (rx, knee_y_r), (rx + lw, knee_y_r), 1)

    # Boot shape at bottom (wider foot with darker color)
    boot_c = _darken(leg_color, 30)
    boot_h = max(2, rs // 2 + 1)
    boot_extra = max(1, rs // 3)
    draw.rect(screen, boot_c,
              (lx - boot_extra, l_leg_y + leg_h,
               lw + boot_extra * 2, boot_h),
              border_radius=max(1, rs // 4))
    draw.rect(screen, boot_c,
              (rx - boot_extra, r_leg_y + leg_h,
               lw + boot_extra * 2, boot_h),
              border_radius=max(1, rs // 4))


# ── Projectile / spell visuals ───────────────────────────────────────────

def draw_fireball(screen, x, y, radius):
    """Multi-layered fireball: orange core + red outer + yellow sparks."""
    r = max(3, radius)
    # Outer red glow
    surf = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
    cx, cy = r * 2, r * 2
    pygame.draw.circle(surf, (200, 40, 20, 80), (cx, cy), r * 2)
    # Red shell
    pygame.draw.circle(surf, (220, 60, 20, 160), (cx, cy), int(r * 1.3))
    # Orange core
    pygame.draw.circle(surf, (255, 140, 30), (cx, cy), r)
    # Yellow-white hot center
    pygame.draw.circle(surf, (255, 220, 80), (cx, cy), max(1, r // 2))
    # Sparks (small dots around edge)
    import random
    rng = random.Random(int(x * 100 + y * 7))
    for _ in range(4):
        angle = rng.uniform(0, math.tau)
        dist = r * 1.2 + rng.uniform(0, r * 0.8)
        sx_ = cx + int(math.cos(angle) * dist)
        sy_ = cy + int(math.sin(angle) * dist)
        pygame.draw.circle(surf, (255, 255, 100, 200), (sx_, sy_),
                           max(1, r // 4))
    screen.blit(surf, (int(x) - r * 2, int(y) - r * 2))


def draw_arrow_projectile(screen, x1, y1, x2, y2, color=(160, 140, 80)):
    """Arrow with arrowhead shape and feathered tail."""
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy)
    if length < 1:
        return
    nx = dx / length
    ny = dy / length
    # Perpendicular
    px, py = -ny, nx

    # Shaft
    pygame.draw.line(screen, color, (int(x1), int(y1)),
                     (int(x2), int(y2)), 1)

    # Arrowhead (triangle at tip)
    head_len = max(3, int(length * 0.25))
    head_w = max(2, head_len // 2)
    tip = (int(x2), int(y2))
    left = (int(x2 - nx * head_len + px * head_w),
            int(y2 - ny * head_len + py * head_w))
    right = (int(x2 - nx * head_len - px * head_w),
             int(y2 - ny * head_len - py * head_w))
    pygame.draw.polygon(screen, (80, 80, 80), [tip, left, right])

    # Feathered tail (lines at base)
    tail_len = max(2, int(length * 0.15))
    for sign in (-1, 1):
        fx = int(x1 + px * tail_len * 0.6 * sign)
        fy = int(y1 + py * tail_len * 0.6 * sign)
        pygame.draw.line(screen, (180, 160, 120),
                         (int(x1), int(y1)), (fx, fy), 1)


def draw_lightning_bolt(screen, x1, y1, x2, y2, color=(150, 180, 255)):
    """Zigzag lightning with branching."""
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy)
    if length < 2:
        return
    segments = max(3, int(length / 6))
    px, py = -dy / length, dx / length  # perpendicular

    points = [(int(x1), int(y1))]
    for i in range(1, segments):
        t = i / segments
        jitter = (((i * 7 + int(x1)) % 5) - 2) * max(2, int(length * 0.08))
        mx = int(x1 + dx * t + px * jitter)
        my = int(y1 + dy * t + py * jitter)
        points.append((mx, my))
    points.append((int(x2), int(y2)))

    # Glow
    for i in range(len(points) - 1):
        pygame.draw.line(screen, (*color[:3],), points[i], points[i + 1], 3)
    # Core bright line
    bright = _lighten(color, 60)
    for i in range(len(points) - 1):
        pygame.draw.line(screen, bright, points[i], points[i + 1], 1)

    # Branch from middle segment
    if len(points) > 3:
        mid = points[len(points) // 2]
        branch_end = (mid[0] + int(px * length * 0.2),
                      mid[1] + int(py * length * 0.2))
        pygame.draw.line(screen, color, mid, branch_end, 1)


def draw_ice_shard(screen, x, y, size):
    """Crystalline ice shard — diamond/triangle shapes."""
    s = max(3, size)
    ice_c = (160, 210, 255)
    ice_dark = (100, 160, 220)
    # Main diamond
    pts = [(int(x), int(y) - s),
           (int(x) + s // 2, int(y)),
           (int(x), int(y) + s // 2),
           (int(x) - s // 2, int(y))]
    pygame.draw.polygon(screen, ice_c, pts)
    pygame.draw.polygon(screen, ice_dark, pts, 1)
    # Inner highlight
    inner_pts = [(int(x), int(y) - s // 2),
                 (int(x) + s // 4, int(y)),
                 (int(x), int(y) + s // 4),
                 (int(x) - s // 4, int(y))]
    pygame.draw.polygon(screen, (200, 230, 255), inner_pts)
    # Small satellite crystals
    for angle in (0.8, 2.3, 4.0):
        cx = int(x + math.cos(angle) * s * 0.8)
        cy = int(y + math.sin(angle) * s * 0.8)
        mini = max(2, s // 3)
        mp = [(cx, cy - mini), (cx + mini // 2, cy), (cx, cy + mini // 2),
              (cx - mini // 2, cy)]
        pygame.draw.polygon(screen, ice_c, mp)
