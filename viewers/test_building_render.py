#!/usr/bin/env python3
"""Standalone building rendering test bench.

Run directly to see different building styles, roof types, and perspectives
without loading the full game. Lets us experiment with 2.5D rendering
quickly.

Controls:
  Left/Right arrows: cycle through building presets
  Up/Down arrows: change number of floors
  R: cycle roof style (flat, pitched, conical, hip)
  T: cycle time of day (morning, noon, evening, night)
  +/-: zoom in/out
  Space: toggle grid overlay
  S: save screenshot
  Esc: quit
"""

import os
import sys
import math

# Don't override SDL_VIDEODRIVER — let pygame use the native display
os.environ.setdefault('SDL_AUDIODRIVER', '')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 800, 600
TILE = 16  # base tile size
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Building Render Test Bench")
clock = pygame.time.Clock()

# ================================================================
# BUILDING PRESETS
# ================================================================

PRESETS = [
    {"name": "Cottage (5x5)", "w": 5, "h": 5, "kind": "hamlet", "shape": "rect"},
    {"name": "House (8x6)", "w": 8, "h": 6, "kind": "village", "shape": "rect"},
    {"name": "Tavern (10x8)", "w": 10, "h": 8, "kind": "town", "shape": "rect"},
    {"name": "Tower (6x6)", "w": 6, "h": 6, "kind": "castle", "shape": "rect"},
    {"name": "Temple (r=5)", "w": 11, "h": 11, "kind": "temple", "shape": "circle", "radius": 5},
    {"name": "Keep (12x10)", "w": 12, "h": 10, "kind": "castle", "shape": "rect"},
    {"name": "City House (7x7)", "w": 7, "h": 7, "kind": "city", "shape": "rect"},
    {"name": "Round Tower (r=3)", "w": 7, "h": 7, "kind": "castle", "shape": "circle", "radius": 3},
]

ROOF_STYLES = ["flat", "pitched", "conical", "hip"]
TIMES = [("Morning", 0.30), ("Noon", 0.50), ("Afternoon", 0.65), ("Evening", 0.80)]

# Roof colors by kind
ROOF_COLORS = {
    "hamlet": (155, 120, 55),
    "village": (165, 75, 40),
    "town": (95, 70, 45),
    "city": (90, 95, 110),
    "castle": (75, 75, 80),
    "temple": (130, 145, 60),
}

WALL_COLOR_S = (140, 125, 105)
WALL_COLOR_E = (110, 100, 85)


# ================================================================
# RENDERING FUNCTIONS
# ================================================================

def draw_building(surface, preset, num_floors, roof_style, time_norm, zoom=1.0):
    """Draw a 2.5D building in 3/4 oblique perspective.

    Camera is above and slightly south-southeast — we see:
    - Top of roof (foreshortened, slightly offset so east slope is more visible)
    - Prominent south wall face (tall, detailed)
    - Visible east wall face (about 1/3 width of south wall)
    - Pitched ridge runs N-S, offset slightly left of center
    - Conical peak offset slightly left of center

    The east-offset creates the depth that makes it read as 3D.
    """
    ts = int(TILE * zoom)
    bw, bh = preset["w"], preset["h"]
    kind = preset["kind"]
    shape = preset["shape"]
    radius = preset.get("radius", 0)

    # Perspective parameters
    floor_h = ts + ts // 2         # wall height per floor (tall!)
    wall_h = num_floors * floor_h  # total south wall height
    east_w = max(4, ts * 2 // 5)   # east wall width (~40% of a tile — visible!)
    roof_depth = bh * ts * 2 // 5  # foreshortened depth (~40%)
    east_shear = east_w            # how much the roof top shifts right vs bottom

    # Colors
    rr, rg, rb = ROOF_COLORS.get(kind, (120, 90, 60))
    wr, wg, wb = WALL_COLOR_S
    er, eg, eb = WALL_COLOR_E

    # Center on surface — offset left slightly to make room for east wall
    cx = surface.get_width() // 2 - east_w
    total_vis_h = roof_depth + wall_h + ts
    cy = surface.get_height() // 2 + total_vis_h // 4

    # Building footprint
    roof_w = bw * ts
    bx = cx - roof_w // 2
    roof_top_y = cy - total_vis_h // 2
    wall_top_y = roof_top_y + roof_depth
    wall_bot_y = wall_top_y + wall_h

    # === 1. ROOF TOP (foreshortened + sheared east for oblique view) ===
    # Each row of the roof shifts right by (east_shear * row/depth) pixels.
    # This creates the oblique "looking from south-southeast" effect.

    def _roof_x_offset(row):
        """How much a roof row shifts right due to oblique perspective."""
        return int(east_shear * (1.0 - row / max(1, roof_depth)))

    if roof_style == "pitched" and shape == "rect":
        # Ridge runs N-S, offset slightly left because we see from the SE.
        # The east (right) slope is wider/brighter, west (left) is narrower/darker.
        ridge_offset = -roof_w // 8  # ridge shifted left of center
        for ty in range(roof_depth):
            x_off = _roof_x_offset(ty)
            row_left = bx + x_off
            row_right = row_left + roof_w
            ridge_x = row_left + roof_w // 2 + ridge_offset
            ry = roof_top_y + ty
            if ry < 0 or ry >= surface.get_height():
                continue
            row_v = (ty // 3 % 2) * 2 - 1
            # West slope (left of ridge — darker, smaller)
            for px in range(row_left, ridge_x):
                if 0 <= px < surface.get_width():
                    t = (ridge_x - px) / max(1, ridge_x - row_left)
                    shade = 0.65 + (1.0 - t) * 0.15
                    c = (max(0, min(255, int(rr * shade + row_v))),
                         max(0, min(255, int(rg * shade + row_v))),
                         max(0, min(255, int(rb * shade + row_v))))
                    surface.set_at((px, ry), c)
            # East slope (right of ridge — brighter, larger)
            for px in range(ridge_x, row_right):
                if 0 <= px < surface.get_width():
                    t = (px - ridge_x) / max(1, row_right - ridge_x)
                    shade = 0.85 + t * 0.12
                    c = (max(0, min(255, int(rr * shade + row_v))),
                         max(0, min(255, int(rg * shade + row_v))),
                         max(0, min(255, int(rb * shade + row_v))))
                    surface.set_at((px, ry), c)
            # Tile row lines
            if ty % 3 == 0:
                pygame.draw.line(surface, (max(0, rr - 15), max(0, rg - 12), max(0, rb - 10)),
                                 (max(0, row_left), ry), (min(surface.get_width()-1, row_right), ry))

        # Ridge line (diagonal due to shear)
        r_x_top = bx + _roof_x_offset(0) + roof_w // 2 + ridge_offset
        r_x_bot = bx + _roof_x_offset(roof_depth - 1) + roof_w // 2 + ridge_offset
        pygame.draw.line(surface, (max(0, rr - 35), max(0, rg - 30), max(0, rb - 25)),
                         (r_x_top, roof_top_y), (r_x_bot, roof_top_y + roof_depth - 1), 2)

    elif (roof_style == "conical") or (shape == "circle" and roof_style != "flat"):
        # Cone: foreshortened ellipse that shrinks to a peak.
        # Peak is offset left (we see from SE, so peak appears left of center).
        cone_r = (radius * ts) if radius > 0 else min(bw, bh) * ts // 2
        peak_offset_x = -cone_r // 4  # peak offset left
        for ty in range(roof_depth):
            x_off = _roof_x_offset(ty)
            t = 1.0 - ty / max(1, roof_depth)  # 1=top(north), 0=bottom(south)
            # Ellipse radius shrinks toward peak
            cur_r = int(cone_r * (1.0 - t * 0.92))
            center_x = bx + roof_w // 2 + x_off + int(peak_offset_x * t)
            ry = roof_top_y + ty
            if ry < 0 or ry >= surface.get_height() or cur_r <= 0:
                continue
            for px in range(-cur_r, cur_r + 1):
                sx = center_x + px
                if 0 <= sx < surface.get_width():
                    edge = abs(px) / max(1, cur_r)
                    shade = 0.7 + t * 0.25 + (1.0 - edge) * 0.1
                    # East side brighter (facing our viewpoint)
                    if px > 0:
                        shade += 0.05
                    row_v = (ty // 3 % 2) - 1
                    c = (max(0, min(255, int(rr * shade + row_v))),
                         max(0, min(255, int(rg * shade + row_v))),
                         max(0, min(255, int(rb * shade + row_v))))
                    surface.set_at((sx, ry), c)
        # Peak highlight
        peak_x = bx + roof_w // 2 + _roof_x_offset(0) + peak_offset_x
        pygame.draw.circle(surface, (min(255, rr + 25), min(255, rg + 20), min(255, rb + 15)),
                           (peak_x, roof_top_y + 1), max(2, ts // 5))

    elif roof_style == "hip":
        # Hip: rectangle that tapers inward on all sides toward a flat top.
        for ty in range(roof_depth):
            x_off = _roof_x_offset(ty)
            ry = roof_top_y + ty
            if ry < 0 or ry >= surface.get_height():
                continue
            # Taper from edges
            t_ns = min(ty, roof_depth - 1 - ty) / max(1, roof_depth // 2)
            for tx in range(roof_w):
                t_ew = min(tx, roof_w - 1 - tx) / max(1, roof_w // 2)
                edge_t = min(t_ns, t_ew)
                shade = 0.7 + edge_t * 0.25
                # East side brighter
                if tx > roof_w // 2:
                    shade += 0.05
                rx = bx + tx + x_off
                if 0 <= rx < surface.get_width():
                    row_v = (ty // 3 % 2) - 1
                    c = (max(0, min(255, int(rr * shade + row_v))),
                         max(0, min(255, int(rg * shade + row_v))),
                         max(0, min(255, int(rb * shade + row_v))))
                    surface.set_at((rx, ry), c)

    else:  # flat
        for ty in range(roof_depth):
            x_off = _roof_x_offset(ty)
            ry = roof_top_y + ty
            if ry < 0 or ry >= surface.get_height():
                continue
            row_v = (ty // 3 % 3) - 1
            for tx in range(roof_w):
                rx = bx + tx + x_off
                if 0 <= rx < surface.get_width():
                    c = (max(0, min(255, rr + row_v * 2)),
                         max(0, min(255, rg + row_v)),
                         max(0, min(255, rb + row_v)))
                    surface.set_at((rx, ry), c)
            if ty % 3 == 0:
                lx = bx + x_off
                pygame.draw.line(surface, (max(0, rr - 10), max(0, rg - 8), max(0, rb - 6)),
                                 (max(0, lx), ry), (min(surface.get_width()-1, lx + roof_w), ry))

    # === 2. SOUTH WALL FACE (the big visible front) ===
    for py in range(wall_h):
        t = py / max(1, wall_h)
        shade = 1.0 - t * 0.15  # slightly darker at bottom
        c = (int(wr * shade), int(wg * shade), int(wb * shade))
        pygame.draw.line(surface, c,
                         (bx, wall_top_y + py), (bx + roof_w - 1, wall_top_y + py))

    # Stone/brick mortar lines
    brick_h = max(3, ts // 3)
    for py in range(0, wall_h, brick_h):
        pygame.draw.line(surface, (max(0, wr - 20), max(0, wg - 18), max(0, wb - 15)),
                         (bx, wall_top_y + py), (bx + roof_w - 1, wall_top_y + py))
    # Vertical mortar (offset every other row)
    brick_w = ts
    for py_row in range(0, wall_h, brick_h):
        offset = brick_w // 2 if (py_row // brick_h) % 2 else 0
        for px in range(offset, roof_w, brick_w):
            x = bx + px
            y1 = wall_top_y + py_row
            y2 = min(wall_bot_y, y1 + brick_h)
            pygame.draw.line(surface, (max(0, wr - 18), max(0, wg - 16), max(0, wb - 13)),
                             (x, y1), (x, y2))

    # Pitched gable triangle on south wall (ridge runs N-S)
    if roof_style == "pitched" and shape == "rect":
        ridge_offset = -roof_w // 8
        gable_h = roof_depth * 2 // 3
        gable_mid = cx + ridge_offset  # ridge is offset left
        for py in range(gable_h):
            t = py / max(1, gable_h)
            # Asymmetric triangle — left side shorter, right side wider
            left_w = int((roof_w // 2 + ridge_offset) * (1.0 - t))
            right_w = int((roof_w // 2 - ridge_offset) * (1.0 - t))
            draw_y = wall_top_y - 1 - py
            if 0 <= draw_y < surface.get_height():
                # Left half (darker — west facing)
                if left_w > 0:
                    shade = 0.75 - t * 0.1
                    c = (int(wr * shade), int(wg * shade), int(wb * shade))
                    pygame.draw.line(surface, c,
                                     (gable_mid - left_w, draw_y), (gable_mid, draw_y))
                # Right half (lighter — south-east facing)
                if right_w > 0:
                    shade = 0.90 - t * 0.1
                    c = (int(wr * shade), int(wg * shade), int(wb * shade))
                    pygame.draw.line(surface, c,
                                     (gable_mid, draw_y), (gable_mid + right_w, draw_y))
                # Mortar
                if py % brick_h == 0:
                    pygame.draw.line(surface, (max(0, wr - 20), max(0, wg - 18), max(0, wb - 15)),
                                     (gable_mid - left_w, draw_y),
                                     (gable_mid + right_w, draw_y))

    # Conical front triangle (visible south-facing slope of cone)
    if (roof_style == "conical") or (shape == "circle" and roof_style != "flat"):
        cone_r = (radius * ts) if radius > 0 else min(bw, bh) * ts // 2
        cone_vis_h = roof_depth * 2 // 3
        for py in range(cone_vis_h):
            t = py / max(1, cone_vis_h)
            cur_w = int(cone_r * 2 * (1.0 - t * 0.95))
            # Offset peak left (oblique view)
            peak_shift = int(-cone_r * 0.15 * t)
            draw_y = wall_top_y - 1 - py
            mid = cx + peak_shift
            hw = cur_w // 2
            if hw > 0 and 0 <= draw_y < surface.get_height():
                shade = 0.75 + t * 0.2
                c = (max(0, min(255, int(rr * shade))),
                     max(0, min(255, int(rg * shade))),
                     max(0, min(255, int(rb * shade))))
                pygame.draw.line(surface, c, (mid - hw, draw_y), (mid + hw, draw_y))

    # === 3. EAST WALL FACE (visible side — oblique perspective) ===
    # The east wall connects the south wall's right edge to the roof's
    # right edge, which is sheared. Each row shifts left as it goes up.
    ex_base = bx + roof_w  # east wall right edge at ground level
    for py in range(wall_h):
        ey = wall_top_y + py
        if 0 <= ey < surface.get_height():
            t = py / max(1, wall_h)
            shade = 0.75 - t * 0.08
            c = (int(er * shade), int(eg * shade), int(eb * shade))
            pygame.draw.line(surface, c,
                             (ex_base, ey), (ex_base + east_w - 1, ey))
            # Mortar
            if py % brick_h == 0:
                pygame.draw.line(surface, (max(0, er - 15), max(0, eg - 13), max(0, eb - 10)),
                                 (ex_base, ey), (ex_base + east_w - 1, ey))

    # East wall of roof area (sheared — connects to roof top edge)
    for py in range(roof_depth):
        ey = roof_top_y + py
        x_off = _roof_x_offset(py)
        ex_roof = bx + roof_w + x_off
        if 0 <= ey < surface.get_height():
            t = py / max(1, roof_depth)
            shade = 0.7 + t * 0.05
            c = (int(er * shade), int(eg * shade), int(eb * shade))
            pygame.draw.line(surface, c,
                             (ex_roof, ey), (ex_roof + east_w - 1, ey))

    # === 4. WINDOWS on south wall ===
    win_w = max(4, ts * 2 // 3)
    win_h = max(5, floor_h // 2)
    glass = (120, 165, 210) if 0.25 < time_norm < 0.75 else (80, 100, 140)
    warm = (210, 185, 80) if time_norm > 0.7 else glass
    glow = warm if time_norm > 0.7 else glass

    for floor in range(num_floors):
        wy = wall_top_y + wall_h - (floor + 1) * floor_h + floor_h // 4
        for wx_idx in range(1, bw - 1, max(1, bw // 4)):
            wx = bx + wx_idx * ts + (ts - win_w) // 2
            if wx + win_w > bx + roof_w - ts // 2:
                continue
            # Recess shadow
            pygame.draw.rect(surface, (max(0, wr - 30), max(0, wg - 28), max(0, wb - 22)),
                             (wx - 2, wy - 2, win_w + 4, win_h + 4))
            # Frame
            pygame.draw.rect(surface, (55, 45, 30), (wx - 1, wy - 1, win_w + 2, win_h + 2))
            # Glass
            pygame.draw.rect(surface, glow, (wx, wy, win_w, win_h))
            # Mullion cross
            pygame.draw.line(surface, (55, 45, 30),
                             (wx + win_w // 2, wy), (wx + win_w // 2, wy + win_h))
            pygame.draw.line(surface, (55, 45, 30),
                             (wx, wy + win_h // 2), (wx + win_w, wy + win_h // 2))

    # === 5. DOOR (centered on south wall, ground level) ===
    door_w = max(5, ts)
    door_h = max(8, floor_h - 4)
    dx = cx - door_w // 2
    dy = wall_bot_y - door_h
    # Door recess
    pygame.draw.rect(surface, (max(0, wr - 25), max(0, wg - 22), max(0, wb - 18)),
                     (dx - 2, dy - 2, door_w + 4, door_h + 4))
    # Door arch
    pygame.draw.rect(surface, (60, 45, 25), (dx - 1, dy - 1, door_w + 2, door_h + 2))
    # Door panels
    pygame.draw.rect(surface, (85, 60, 35), (dx, dy, door_w, door_h))
    pygame.draw.rect(surface, (95, 70, 40), (dx + 1, dy + 1, door_w // 2 - 1, door_h - 2))
    pygame.draw.rect(surface, (80, 55, 32), (dx + door_w // 2 + 1, dy + 1, door_w // 2 - 2, door_h - 2))
    # Handle
    pygame.draw.circle(surface, (180, 160, 80), (dx + door_w - 3, dy + door_h // 2), max(1, ts // 8))

    # === 6. EAVE SHADOW LINE ===
    pygame.draw.line(surface, (30, 25, 20),
                     (bx - 2, wall_top_y), (bx + roof_w + east_w, wall_top_y))


def _draw_roof_tile(surface, x, y, ts, kind, tx, ty, radius):
    """Draw a single roof tile with texture variation."""
    rr, rg, rb = ROOF_COLORS.get(kind, (120, 90, 60))
    v = ((tx * 7 + ty * 13) % 5) - 2
    base = (max(20, min(255, rr + v * 4)),
            max(20, min(255, rg + v * 3)),
            max(20, min(255, rb + v * 3)))

    pygame.draw.rect(surface, base, (x, y, ts, ts))

    # Texture pattern based on kind
    if kind == "hamlet":  # thatch
        for py in range(0, ts, 2):
            shade = base[0] - 8 + (py % 4) * 2
            pygame.draw.line(surface, (max(20, shade), max(20, base[1] - 5), max(10, base[2] - 3)),
                             (x, y + py), (x + ts - 1, y + py))
    elif kind in ("village", "temple"):  # tile
        tile_h = max(2, ts // 4)
        offset = (tile_h // 2) if (ty % 2) else 0
        for row in range(0, ts, tile_h):
            pygame.draw.line(surface, (max(20, base[0] - 10), max(20, base[1] - 8), max(10, base[2] - 6)),
                             (x, y + row), (x + ts - 1, y + row))
    elif kind == "town":  # wood shingle
        for py in range(0, ts, max(2, ts // 5)):
            pygame.draw.line(surface, (max(20, base[0] - 8), max(20, base[1] - 6), max(10, base[2] - 5)),
                             (x, y + py), (x + ts - 1, y + py))
    elif kind == "city":  # slate
        for py in range(0, ts, 2):
            c = (base[0] + 3, base[1] + 3, min(255, base[2] + 5))
            pygame.draw.line(surface, c, (x, y + py), (x + ts - 1, y + py))
    elif kind == "castle":  # stone
        bsz = max(2, ts // 3)
        for row in range(0, ts, bsz):
            pygame.draw.line(surface, (max(20, base[0] - 12), max(20, base[1] - 12), max(20, base[2] - 10)),
                             (x, y + row), (x + ts - 1, y + row))


def _draw_wall_column(surface, x, y, ts, wall_h, base_color, curved_shade=0.0):
    """Draw a single tile-width column of south-facing wall."""
    wr, wg, wb = base_color
    curve_mult = 1.0 - curved_shade * 0.25

    for py in range(wall_h):
        t = py / max(1, wall_h)
        shade = (1.0 - t * 0.2) * curve_mult
        c = (int(wr * shade), int(wg * shade), int(wb * shade))
        pygame.draw.line(surface, c, (x, y + ts + py), (x + ts - 1, y + ts + py))

    # Brick texture
    for py in range(0, wall_h, 3):
        c = (int((wr - 15) * curve_mult), int((wg - 15) * curve_mult), int((wb - 12) * curve_mult))
        pygame.draw.line(surface, c, (x, y + ts + py), (x + ts - 1, y + ts + py))


def _draw_pitched_shading(surface, x, y, w, h):
    """Overlay pitched roof shading: dark north half, bright south half, ridge."""
    shade = pygame.Surface((w, h), pygame.SRCALPHA)
    mid = h // 2
    for py in range(h):
        if py < mid:
            t = 1.0 - py / max(1, mid)
            alpha = int(t * 60 + 15)
            pygame.draw.line(shade, (0, 0, 0, alpha), (0, py), (w - 1, py))
        else:
            t = (py - mid) / max(1, h - mid)
            alpha = int((1.0 - t) * 20)
            pygame.draw.line(shade, (255, 255, 220, alpha), (0, py), (w - 1, py))
    pygame.draw.line(shade, (0, 0, 0, 70), (0, mid), (w - 1, mid), 2)
    pygame.draw.line(shade, (255, 255, 200, 25), (0, mid + 2), (w - 1, mid + 2))
    surface.blit(shade, (x, y))


def _draw_conical_shading(surface, cx, cy, r):
    """Overlay conical roof shading for circular buildings."""
    if r <= 0:
        return
    shade = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
    sr = shade.get_width() // 2
    for py in range(shade.get_height()):
        for px in range(shade.get_width()):
            dx, dy = px - sr, py - sr
            dist = (dx * dx + dy * dy) ** 0.5
            if dist > r + 1:
                continue
            # Radial darkening + directional (south = bright)
            r_t = min(1.0, dist / max(1, r))
            dir_t = dy / max(1, r) * 0.3
            alpha = int(r_t * 70 - dir_t * 35)
            alpha = max(0, min(100, alpha))
            shade.set_at((px, py), (0, 0, 0, alpha))
    # Peak highlight
    pygame.draw.circle(shade, (255, 255, 200, 30), (sr, sr), max(2, r // 5))
    surface.blit(shade, (cx - sr, cy - sr))


def _draw_hip_shading(surface, x, y, w, h):
    """Hip roof: all four sides slope inward. Darker on all edges."""
    shade = pygame.Surface((w, h), pygame.SRCALPHA)
    for py in range(h):
        for px in range(w):
            # Distance from center as fraction
            dx = abs(px - w // 2) / max(1, w // 2)
            dy = abs(py - h // 2) / max(1, h // 2)
            edge_t = max(dx, dy)
            # South bias: south half brighter
            south_t = (py - h // 2) / max(1, h // 2) * 0.2
            alpha = int(edge_t * 60 - south_t * 30)
            alpha = max(0, min(80, alpha))
            shade.set_at((px, py), (0, 0, 0, alpha))
    surface.blit(shade, (x, y))


# ================================================================
# MAIN LOOP
# ================================================================

def main():
    preset_idx = 0
    num_floors = 1
    roof_idx = 1  # start with pitched
    time_idx = 0
    zoom = 2.0
    show_grid = False

    font = pygame.font.SysFont("monospace", 14)
    font_lg = pygame.font.SysFont("monospace", 18, bold=True)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RIGHT:
                    preset_idx = (preset_idx + 1) % len(PRESETS)
                elif event.key == pygame.K_LEFT:
                    preset_idx = (preset_idx - 1) % len(PRESETS)
                elif event.key == pygame.K_UP:
                    num_floors = min(5, num_floors + 1)
                elif event.key == pygame.K_DOWN:
                    num_floors = max(1, num_floors - 1)
                elif event.key == pygame.K_r:
                    roof_idx = (roof_idx + 1) % len(ROOF_STYLES)
                elif event.key == pygame.K_t:
                    time_idx = (time_idx + 1) % len(TIMES)
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                    zoom = min(4.0, zoom + 0.5)
                elif event.key == pygame.K_MINUS:
                    zoom = max(0.5, zoom - 0.5)
                elif event.key == pygame.K_SPACE:
                    show_grid = not show_grid
                elif event.key == pygame.K_s:
                    pygame.image.save(screen, "exports/screenshots/building_test.png")
                    print("Saved building_test.png")

        preset = PRESETS[preset_idx]
        roof_style = ROOF_STYLES[roof_idx]
        time_name, time_norm = TIMES[time_idx]

        # Background
        screen.fill((180, 165, 130))  # sand color

        # Draw grid
        if show_grid:
            ts = int(TILE * zoom)
            for gx in range(0, SCREEN_W, ts):
                pygame.draw.line(screen, (160, 145, 115), (gx, 0), (gx, SCREEN_H))
            for gy in range(0, SCREEN_H, ts):
                pygame.draw.line(screen, (160, 145, 115), (0, gy), (SCREEN_W, gy))

        # Draw building
        draw_building(screen, preset, num_floors, roof_style, time_norm, zoom)

        # UI overlay
        y = 10
        texts = [
            f"Building: {preset['name']}  (Left/Right)",
            f"Floors: {num_floors}  (Up/Down)",
            f"Roof: {roof_style}  (R)",
            f"Time: {time_name} ({time_norm:.2f})  (T)",
            f"Zoom: {zoom:.1f}x  (+/-)",
            f"Grid: {'on' if show_grid else 'off'}  (Space)",
            "S: screenshot  Esc: quit",
        ]
        for txt in texts:
            surf = font.render(txt, True, (40, 40, 50))
            screen.blit(surf, (10, y))
            y += 16

        # Title
        title = font_lg.render("Building Render Test Bench", True, (60, 50, 40))
        screen.blit(title, (SCREEN_W - title.get_width() - 10, 10))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


if __name__ == "__main__":
    main()
