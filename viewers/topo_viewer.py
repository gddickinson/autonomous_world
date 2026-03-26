#!/usr/bin/env python3
"""Topography Viewer — island outline, elevation, contours, rivers and lakes.

A clean, focused viewer for inspecting terrain generation.

Controls:
  Mouse drag (left button): pan camera
  Mouse wheel: zoom in/out
  O: toggle contour lines
  L: toggle labels (elevation at cursor)
  HOME: reset view to fit island
  F12: screenshot
  Esc: quit
"""

import os, sys, time, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pygame
pygame.init()

SCREEN_W, SCREEN_H = 1400, 900
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Topography Viewer")
clock = pygame.time.Clock()
font_sm = pygame.font.SysFont("monospace", 11)
font_md = pygame.font.SysFont("monospace", 14, bold=True)
font_xl = pygame.font.SysFont("monospace", 28, bold=True)


# ── Color helpers ────────────────────────────────────────────────────

def _elev_color(e):
    """Topographic color: deep blue → sand → green → brown → snow."""
    if e < 0.18: return (25, 55, 120)     # deep ocean
    if e < 0.22: return (35, 80, 150)     # shallow ocean
    if e < 0.25: return (50, 110, 175)    # coastal water
    if e < 0.28: return (190, 180, 140)   # beach/sand
    if e < 0.35: return (120, 170, 80)    # lowland grass
    if e < 0.45: return (80, 145, 55)     # grassland
    if e < 0.52: return (55, 120, 40)     # forest green
    if e < 0.60: return (100, 100, 70)    # upland
    if e < 0.70: return (135, 115, 90)    # mountain brown
    if e < 0.80: return (160, 150, 140)   # high mountain
    return (220, 225, 230)                 # snow


# ── Loading screen ───────────────────────────────────────────────────

def _draw_loading(msg, pct):
    screen.fill((15, 15, 25))
    t = font_xl.render("TOPOGRAPHY VIEWER", True, (180, 180, 200))
    screen.blit(t, (SCREEN_W // 2 - t.get_width() // 2, SCREEN_H // 3))
    m = font_md.render(msg, True, (140, 140, 160))
    screen.blit(m, (SCREEN_W // 2 - m.get_width() // 2, SCREEN_H // 2))
    bx, by, bw, bh = SCREEN_W // 2 - 200, SCREEN_H // 2 + 25, 400, 16
    pygame.draw.rect(screen, (40, 40, 55), (bx, by, bw, bh), border_radius=3)
    fw = int(bw * max(0, min(1, pct)))
    if fw > 0:
        pygame.draw.rect(screen, (70, 130, 200), (bx, by, fw, bh), border_radius=3)
    pygame.display.flip()
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT: pygame.quit(); sys.exit()

_draw_loading("Initializing...", 0.0)

# Generate world (headless)
os.environ['SDL_VIDEODRIVER'] = 'dummy'
_draw_loading("Generating terrain...", 0.05)
pygame.display.set_mode((100, 100))

from game.ui.screenshot import HeadlessGame

t0 = time.time()
_draw_loading("Building elevation, rivers, lakes...", 0.1)
g = HeadlessGame(seed=42, mode='god', spawn_location='test_island', use_chunked=True)
gen_time = time.time() - t0

os.environ.pop('SDL_VIDEODRIVER', None)
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))

plan = g.world.plan
ww = getattr(plan, 'world_width', 10000)
wh = getattr(plan, 'world_height', 10000)
rivers = plan.rivers
lakes = getattr(plan, 'lakes', [])
elev_cache = plan._elev_cache
elev_step = plan._elev_step

pygame.display.set_caption(
    f"Topography — {len(rivers)} rivers, {len(lakes)} lakes "
    f"(generated in {gen_time:.0f}s)")

_draw_loading("Pre-rendering elevation map...", 0.85)

# ── Pre-render full elevation surface at cache resolution ────────────

ch, cw = elev_cache.shape
topo_surf = pygame.Surface((cw, ch))
for cy in range(ch):
    for cx in range(cw):
        topo_surf.set_at((cx, cy), _elev_color(float(elev_cache[cy, cx])))

# Draw water features onto the topo surface directly
# Lakes first (filled circles so they're visible)
lake_color = (35, 85, 155)
for lake in lakes:
    lcx = max(0, min(cw - 1, lake.center[0] // elev_step))
    lcy = max(0, min(ch - 1, lake.center[1] // elev_step))
    lr = max(3, lake.radius // elev_step)
    pygame.draw.circle(topo_surf, lake_color, (lcx, lcy), lr)
    # Also fill individual cells for irregular shape
    for lx, ly in lake.cells:
        cx_l = max(0, min(cw - 1, lx // elev_step))
        cy_l = max(0, min(ch - 1, ly // elev_step))
        pygame.draw.circle(topo_surf, lake_color, (cx_l, cy_l), 2)

# Rivers — draw much wider so they're visible when zoomed out
# Sort: streams first (drawn thinner, underneath), major last (on top)
sorted_rivers = sorted(rivers,
    key=lambda r: {'major': 2, 'medium': 1}.get(getattr(r, 'rank', 'stream'), 0))
for river in sorted_rivers:
    pts = getattr(river, 'points', getattr(river, 'waypoints', []))
    if len(pts) < 2:
        continue
    rank = getattr(river, 'rank', 'stream')
    if rank == 'major':
        color, w = (25, 70, 180), 5
    elif rank == 'medium':
        color, w = (35, 90, 175), 3
    else:
        color, w = (50, 110, 170), 1
    mapped = [(max(0, min(cw - 1, int(px / elev_step))),
               max(0, min(ch - 1, int(py / elev_step)))) for px, py in pts]
    if len(mapped) >= 2:
        pygame.draw.lines(topo_surf, color, False, mapped, w)

_draw_loading("Ready!", 1.0)
time.sleep(0.3)

# ── Camera state ─────────────────────────────────────────────────────

cam_x = float(ww / 2)
cam_y = float(wh / 2)
zoom = min(SCREEN_W / ww, SCREEN_H / wh) * 0.9
min_zoom = 0.01
max_zoom = 20.0

show_contours = True
show_cursor_info = True
dragging = False
drag_start = (0, 0)
cam_drag_start = (0.0, 0.0)

# ── Minimap ──────────────────────────────────────────────────────────

MM_W, MM_H = 180, 180
minimap = pygame.transform.smoothscale(topo_surf, (MM_W, MM_H))

# ── Main loop ────────────────────────────────────────────────────────

running = True
while running:
    dt = clock.tick(60) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_o:
                show_contours = not show_contours
            elif event.key == pygame.K_l:
                show_cursor_info = not show_cursor_info
            elif event.key == pygame.K_HOME:
                cam_x, cam_y = ww / 2, wh / 2
                zoom = min(SCREEN_W / ww, SCREEN_H / wh) * 0.9
            elif event.key == pygame.K_F12:
                n = 0
                while os.path.exists(f"topo_screenshot_{n}.png"):
                    n += 1
                pygame.image.save(screen, f"topo_screenshot_{n}.png")
                print(f"Screenshot saved: topo_screenshot_{n}.png")
        elif event.type == pygame.MOUSEWHEEL:
            # Zoom toward mouse cursor position
            mx, my = pygame.mouse.get_pos()
            wx_before = cam_x + (mx - SCREEN_W / 2) / zoom
            wy_before = cam_y + (my - SCREEN_H / 2) / zoom
            if event.y > 0:
                zoom = min(max_zoom, zoom * 1.25)
            else:
                zoom = max(min_zoom, zoom / 1.25)
            wx_after = cam_x + (mx - SCREEN_W / 2) / zoom
            wy_after = cam_y + (my - SCREEN_H / 2) / zoom
            cam_x += wx_before - wx_after
            cam_y += wy_before - wy_after
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                # Check minimap click
                mm_x, mm_y = SCREEN_W - MM_W - 10, 10
                if (mm_x <= event.pos[0] <= mm_x + MM_W and
                        mm_y <= event.pos[1] <= mm_y + MM_H):
                    cam_x = (event.pos[0] - mm_x) / MM_W * ww
                    cam_y = (event.pos[1] - mm_y) / MM_H * wh
                else:
                    dragging = True
                    drag_start = event.pos
                    cam_drag_start = (cam_x, cam_y)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                dragging = False
        elif event.type == pygame.MOUSEMOTION:
            if dragging:
                dx = event.pos[0] - drag_start[0]
                dy = event.pos[1] - drag_start[1]
                cam_x = cam_drag_start[0] - dx / zoom
                cam_y = cam_drag_start[1] - dy / zoom

    # WASD panning
    keys = pygame.key.get_pressed()
    spd = 300.0 / max(0.1, zoom) * dt
    if keys[pygame.K_LEFT] or keys[pygame.K_a]: cam_x -= spd
    if keys[pygame.K_RIGHT] or keys[pygame.K_d]: cam_x += spd
    if keys[pygame.K_UP] or keys[pygame.K_w]: cam_y -= spd
    if keys[pygame.K_DOWN] or keys[pygame.K_s]: cam_y += spd
    cam_x = max(0, min(ww, cam_x))
    cam_y = max(0, min(wh, cam_y))

    # ── Render ──────────────────────────────────────────────────────

    screen.fill((15, 20, 30))

    # Draw pre-rendered topo surface scaled to current view
    # Convert camera world coords to cache coords
    half_w = SCREEN_W / 2 / zoom
    half_h = SCREEN_H / 2 / zoom
    # Source rect in world coords → cache coords
    src_x = (cam_x - half_w) / elev_step
    src_y = (cam_y - half_h) / elev_step
    src_w = SCREEN_W / zoom / elev_step
    src_h = SCREEN_H / zoom / elev_step

    # Clamp source rect
    sx0 = max(0, int(src_x))
    sy0 = max(0, int(src_y))
    sx1 = min(cw, int(src_x + src_w) + 1)
    sy1 = min(ch, int(src_y + src_h) + 1)
    sw = sx1 - sx0
    sh = sy1 - sy0

    if sw > 0 and sh > 0:
        sub = topo_surf.subsurface((sx0, sy0, sw, sh))
        dest_w = int(sw * elev_step * zoom)
        dest_h = int(sh * elev_step * zoom)
        if dest_w > 0 and dest_h > 0:
            scaled = pygame.transform.scale(sub, (dest_w, dest_h))
            dest_x = int((sx0 * elev_step - cam_x) * zoom) + SCREEN_W // 2
            dest_y = int((sy0 * elev_step - cam_y) * zoom) + SCREEN_H // 2
            screen.blit(scaled, (dest_x, dest_y))

    # Contour lines — wider intervals, only on land
    if show_contours and zoom > 0.03:
        ci = 0.10  # contour every 0.10 elevation units
        step_c = max(2, int(4 / max(0.1, zoom)))
        stp = max(elev_step, int(elev_step / max(0.01, zoom)))
        for psy in range(0, SCREEN_H, step_c):
            for psx in range(0, SCREEN_W, step_c):
                iwx = int(cam_x + (psx - SCREEN_W / 2) / zoom)
                iwy = int(cam_y + (psy - SCREEN_H / 2) / zoom)
                if not (0 <= iwx < ww - stp and 0 <= iwy < wh - stp):
                    continue
                e0 = plan.get_elevation_fast(iwx, iwy)
                if e0 < 0.24:  # skip water
                    continue
                e1 = plan.get_elevation_fast(iwx + stp, iwy)
                e2 = plan.get_elevation_fast(iwx, iwy + stp)
                l0, l1, l2 = int(e0 / ci), int(e1 / ci), int(e2 / ci)
                if l0 != l1 or l0 != l2:
                    major = (l0 % 2 == 0)  # every other contour is major
                    cc = (60, 45, 25) if major else (90, 75, 50)
                    sz = 2 if major else 1
                    pygame.draw.rect(screen, cc, (psx, psy, sz, sz))

    # ── HUD ─────────────────────────────────────────────────────────

    # Minimap
    mm_x, mm_y = SCREEN_W - MM_W - 10, 10
    screen.blit(minimap, (mm_x, mm_y))
    pygame.draw.rect(screen, (80, 80, 100), (mm_x, mm_y, MM_W, MM_H), 1)
    # Camera position on minimap
    cx_mm = int(cam_x / ww * MM_W) + mm_x
    cy_mm = int(cam_y / wh * MM_H) + mm_y
    pygame.draw.circle(screen, (255, 255, 255), (cx_mm, cy_mm), 2)
    vw = int(half_w * 2 / ww * MM_W)
    vh = int(half_h * 2 / wh * MM_H)
    if vw > 1 and vh > 1:
        pygame.draw.rect(screen, (255, 255, 255),
                         (cx_mm - vw // 2, cy_mm - vh // 2, vw, vh), 1)

    # Info bar
    info = [
        f"Pos: ({int(cam_x)}, {int(cam_y)})  Zoom: {zoom:.2f}  "
        f"Rivers: {len(rivers)}  Lakes: {len(lakes)}",
        f"O:contours {'ON' if show_contours else 'OFF'}  "
        f"L:cursor info {'ON' if show_cursor_info else 'OFF'}  "
        f"Drag:pan  Scroll:zoom  HOME:reset  F12:screenshot",
    ]
    for i, line in enumerate(info):
        screen.blit(font_sm.render(line, True, (200, 200, 220)), (10, 10 + i * 14))

    # Cursor elevation info
    if show_cursor_info:
        mx, my = pygame.mouse.get_pos()
        wx = int(cam_x + (mx - SCREEN_W / 2) / zoom)
        wy = int(cam_y + (my - SCREEN_H / 2) / zoom)
        if 0 <= wx < ww and 0 <= wy < wh:
            elev = plan.get_elevation_fast(wx, wy)
            terrain = "water" if elev < 0.22 else "beach" if elev < 0.28 else \
                      "lowland" if elev < 0.40 else "upland" if elev < 0.55 else \
                      "mountain" if elev < 0.70 else "peak"
            lbl = font_md.render(
                f"({wx}, {wy})  elev={elev:.3f}  {terrain}",
                True, (255, 240, 180))
            screen.blit(lbl, (10, SCREEN_H - 24))

    pygame.display.flip()

pygame.quit()
