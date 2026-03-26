#!/usr/bin/env python3
"""World Viewer — pan/zoom world with terrain, settlements, roads, rivers.

Keys: WASD/arrows=pan, scroll/+/-=zoom, TAB=next settlement, HOME=reset,
R=roads, V=rivers, B=labels, G=grid, T=terrain, C=centers, P=buildings,
O=contours, F=farms, 1-8=overlays, 9=off, F12=screenshot, Esc=quit
"""

import os, sys, time, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 1280, 800
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("World Viewer")
clock = pygame.time.Clock()
font_sm = pygame.font.SysFont("monospace", 11)
font_md = pygame.font.SysFont("monospace", 14, bold=True)
font_lg = pygame.font.SysFont("monospace", 24, bold=True)
font_xl = pygame.font.SysFont("monospace", 32, bold=True)

from game.settings import TERRAIN_COLORS
from game.world.terrain_gen import compute_moisture, whittaker_biome
from viewers.overlay_helpers import draw_overlay, draw_farms, OVERLAY_NAMES

_TILE_COLORS = dict(TERRAIN_COLORS)
_TILE_COLORS.setdefault(70, (40, 35, 30))
_TILE_COLORS.setdefault(71, (180, 210, 230))


def _elev_color(elev):
    if elev < 0.23: return (41, 100, 160)
    elif elev < 0.30: return (180, 170, 130)
    elif elev < 0.45: return (70, 130, 60)
    elif elev < 0.55: return (50, 110, 40)
    elif elev < 0.65: return (120, 105, 85)
    return (200, 200, 210)


# ── Loading Screen ───────────────────────────────────────────────────────

def _draw_loading(message, progress):
    screen.fill((15, 15, 25))
    # Title
    title = font_xl.render("WORLD VIEWER", True, (180, 180, 200))
    screen.blit(title, (SCREEN_W // 2 - title.get_width() // 2, SCREEN_H // 3 - 40))
    # Message
    msg = font_md.render(message, True, (140, 140, 160))
    screen.blit(msg, (SCREEN_W // 2 - msg.get_width() // 2, SCREEN_H // 2 - 10))
    # Progress bar
    bar_w = 400
    bar_h = 20
    bar_x = SCREEN_W // 2 - bar_w // 2
    bar_y = SCREEN_H // 2 + 20
    pygame.draw.rect(screen, (40, 40, 55), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
    fill_w = int(bar_w * max(0, min(1, progress)))
    if fill_w > 0:
        pygame.draw.rect(screen, (80, 140, 220), (bar_x, bar_y, fill_w, bar_h), border_radius=4)
    pygame.draw.rect(screen, (60, 60, 80), (bar_x, bar_y, bar_w, bar_h), 1, border_radius=4)
    # Percentage
    pct = font_sm.render(f"{int(progress * 100)}%", True, (180, 180, 200))
    screen.blit(pct, (bar_x + bar_w + 10, bar_y + 2))
    pygame.display.flip()
    # Process events to prevent "not responding"
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()

_draw_loading("Initializing...", 0.0)

# Generate world
os.environ['SDL_VIDEODRIVER'] = 'dummy'
_draw_loading("Generating world...", 0.05)
dummy_screen = pygame.display.set_mode((100, 100))

from game.ui.screenshot import HeadlessGame

t0 = time.time()
_draw_loading("Generating terrain and settlements...", 0.1)
g = HeadlessGame(seed=42, mode='god', spawn_location='test_island', use_chunked=True)
gen_time = time.time() - t0

# Switch back to real display
os.environ.pop('SDL_VIDEODRIVER', None)
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption(
    f"World Viewer — {len(g.world.plan.settlements)} settlements, "
    f"{len(g.world.plan.rivers)} rivers (generated in {gen_time:.0f}s)")

_draw_loading("Building minimap...", 0.85)

# ── Minimap ──────────────────────────────────────────────────────────────

MINIMAP_W, MINIMAP_H = 200, 200
ww = getattr(g.world.plan, 'world_width', 10000)
wh = getattr(g.world.plan, 'world_height', 10000)
settlements = g.world.plan.settlements
rivers = g.world.plan.rivers


def _build_minimap():
    surf = pygame.Surface((MINIMAP_W, MINIMAP_H))
    for my in range(MINIMAP_H):
        for mx in range(MINIMAP_W):
            wx = int(mx / MINIMAP_W * ww)
            wy = int(my / MINIMAP_H * wh)
            elev = g.world.plan.get_elevation_fast(wx, wy)
            surf.set_at((mx, my), _elev_color(elev))
    # Lakes on minimap
    for lake in getattr(g.world.plan, 'lakes', []):
        cx_l, cy_l = lake.center
        mx_l = int(cx_l / ww * MINIMAP_W)
        my_l = int(cy_l / wh * MINIMAP_H)
        mr = max(1, int(lake.radius / max(ww, wh) * MINIMAP_W))
        pygame.draw.circle(surf, (45, 95, 160), (mx_l, my_l), mr)
    # Rivers on minimap — width by rank
    for river in rivers:
        pts = getattr(river, 'points', getattr(river, 'waypoints', []))
        if len(pts) >= 2:
            mapped = [(int(p[0] / ww * MINIMAP_W), int(p[1] / wh * MINIMAP_H))
                      for p in pts]
            rank = getattr(river, 'rank', 'stream')
            lw = 2 if rank == 'major' else 1
            pygame.draw.lines(surf, (60, 120, 200), False, mapped, lw)
    # Settlements on minimap
    for sp in settlements:
        sx = int(sp.x / ww * MINIMAP_W)
        sy = int(sp.y / wh * MINIMAP_H)
        colors = {"city": (255, 50, 50), "town": (255, 150, 50),
                  "village": (255, 255, 100), "hamlet": (200, 200, 200)}
        r = 3 if sp.kind == "city" else 2 if sp.kind in ("town", "village") else 1
        pygame.draw.circle(surf, colors.get(sp.kind, (180, 180, 180)), (sx, sy), r)
    # Roads on minimap
    for road in g.world.plan.roads:
        pts = getattr(road, 'waypoints', getattr(road, 'points', []))
        if len(pts) >= 2:
            mapped = [(int(p[0] / ww * MINIMAP_W), int(p[1] / wh * MINIMAP_H))
                      for p in pts]
            pygame.draw.lines(surf, (140, 120, 80), False, mapped, 1)
    return surf


minimap = _build_minimap()
_draw_loading("Ready!", 1.0)
time.sleep(0.3)

# ── Initial State — center on island, fit whole world ────────────────────

cam_x = float(ww / 2)
cam_y = float(wh / 2)
# Zoom to fit entire world in view
zoom = min(SCREEN_W / ww, SCREEN_H / wh) * 0.9
min_zoom = 0.02
max_zoom = 16.0
pan_speed = 200.0

show_roads = True
show_rivers = True
show_labels = True
show_grid = False
show_terrain = True
show_settlements = True
show_buildings = True
show_contours = False
show_farms = False
overlay_mode = 0
_road_styles = {
    "king_road": ((200, 180, 140), 1.2), "paved_road": ((170, 165, 155), 0.9),
    "gravel_road": ((155, 135, 100), 0.6), "dirt_track": ((130, 110, 80), 0.4),
}
settlement_idx = -1

# ── Main Loop ────────────────────────────────────────────────────────────

running = True
while running:
    dt = clock.tick(60) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key == pygame.K_r:
                show_roads = not show_roads
            elif event.key == pygame.K_v:
                show_rivers = not show_rivers
            elif event.key == pygame.K_b:
                show_labels = not show_labels
            elif event.key == pygame.K_g:
                show_grid = not show_grid
            elif event.key == pygame.K_t:
                show_terrain = not show_terrain
            elif event.key == pygame.K_c:
                show_settlements = not show_settlements
            elif event.key == pygame.K_p:
                show_buildings = not show_buildings
            elif event.key == pygame.K_o:
                show_contours = not show_contours
            elif event.key == pygame.K_f:
                show_farms = not show_farms
            elif event.key == pygame.K_HOME:
                cam_x, cam_y = ww / 2, wh / 2
                zoom = min(SCREEN_W / ww, SCREEN_H / wh) * 0.9
            elif event.key == pygame.K_TAB:
                if settlements:
                    settlement_idx = (settlement_idx + 1) % len(settlements)
                    sp = settlements[settlement_idx]
                    cam_x, cam_y = float(sp.x), float(sp.y)
                    zoom = max(2.0, zoom)
            elif event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                zoom = min(max_zoom, zoom * 1.5)
            elif event.key == pygame.K_MINUS:
                zoom = max(min_zoom, zoom / 1.5)
            elif event.key == pygame.K_F12:
                _ss_num = 0
                while os.path.exists(f"world_viewer_screenshot_{_ss_num}.png"):
                    _ss_num += 1
                _ss_path = f"world_viewer_screenshot_{_ss_num}.png"
                pygame.image.save(screen, _ss_path)
                print(f"Screenshot saved: {_ss_path}")
            elif event.key in range(pygame.K_1, pygame.K_9 + 1):
                overlay_mode = event.key - pygame.K_1 + 1
                if overlay_mode == 9:
                    overlay_mode = 0
        elif event.type == pygame.MOUSEWHEEL:
            if event.y > 0:
                zoom = min(max_zoom, zoom * 1.3)
            elif event.y < 0:
                zoom = max(min_zoom, zoom / 1.3)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            mm_x = SCREEN_W - MINIMAP_W - 10
            mm_y = 10
            if mm_x <= mx <= mm_x + MINIMAP_W and mm_y <= my <= mm_y + MINIMAP_H:
                cam_x = (mx - mm_x) / MINIMAP_W * ww
                cam_y = (my - mm_y) / MINIMAP_H * wh

    # Smooth panning
    keys = pygame.key.get_pressed()
    spd = pan_speed / max(0.1, zoom) * dt
    if keys[pygame.K_LEFT] or keys[pygame.K_a]: cam_x -= spd
    if keys[pygame.K_RIGHT] or keys[pygame.K_d]: cam_x += spd
    if keys[pygame.K_UP] or keys[pygame.K_w]: cam_y -= spd
    if keys[pygame.K_DOWN] or keys[pygame.K_s]: cam_y += spd
    cam_x = max(0, min(ww, cam_x))
    cam_y = max(0, min(wh, cam_y))

    # ── Render ───────────────────────────────────────────────────────
    screen.fill((20, 30, 40))

    half_w = SCREEN_W / 2 / zoom
    half_h = SCREEN_H / 2 / zoom
    x0, y0 = int(cam_x - half_w) - 1, int(cam_y - half_h) - 1
    x1, y1 = int(cam_x + half_w) + 2, int(cam_y + half_h) + 2
    tile_px = max(1, round(zoom))

    # Terrain (T toggles)
    if not show_terrain:
        screen.fill((35, 40, 45))  # neutral dark background when terrain hidden
    elif zoom >= 0.5:
        vx0, vy0 = max(0, x0), max(0, y0)
        vx1, vy1 = min(ww, x1), min(wh, y1)
        max_axis = min(300, int(SCREEN_W / zoom) + 2)
        if vx1 - vx0 > max_axis:
            mid = (vx0 + vx1) // 2
            vx0, vx1 = mid - max_axis // 2, mid + max_axis // 2
        if vy1 - vy0 > max_axis:
            mid = (vy0 + vy1) // 2
            vy0, vy1 = mid - max_axis // 2, mid + max_axis // 2
        for ty in range(vy0, vy1):
            for tx in range(vx0, vx1):
                sx = int((tx - cam_x) * zoom) + SCREEN_W // 2
                sy = int((ty - cam_y) * zoom) + SCREEN_H // 2
                if sx + tile_px < 0 or sx > SCREEN_W or sy + tile_px < 0 or sy > SCREEN_H:
                    continue
                try:
                    tile = g.world.get_tile(tx, ty)
                except Exception:
                    tile = -1
                color = _TILE_COLORS.get(tile, (80, 80, 80)) if tile >= 0 else _elev_color(
                    g.world.plan.get_elevation_fast(tx, ty))
                if tile_px <= 1:
                    if 0 <= sx < SCREEN_W and 0 <= sy < SCREEN_H:
                        screen.set_at((sx, sy), color)
                else:
                    pygame.draw.rect(screen, color, (sx, sy, tile_px, tile_px))
    else:
        for psy in range(0, SCREEN_H, 2):
            for psx in range(0, SCREEN_W, 2):
                iwx = int(cam_x + (psx - SCREEN_W / 2) / zoom)
                iwy = int(cam_y + (psy - SCREEN_H / 2) / zoom)
                if 0 <= iwx < ww and 0 <= iwy < wh:
                    c = _elev_color(g.world.plan.get_elevation_fast(iwx, iwy))
                    screen.set_at((psx, psy), c)
                    screen.set_at((psx + 1, psy), c)
                    screen.set_at((psx, psy + 1), c)
                    screen.set_at((psx + 1, psy + 1), c)

    # Contour lines (O toggles)
    if show_contours:
        ci = 0.05  # contour interval
        step_c = max(2, int(4 / max(0.1, zoom)))
        for psy in range(0, SCREEN_H, step_c):
            for psx in range(0, SCREEN_W, step_c):
                iwx = int(cam_x + (psx - SCREEN_W / 2) / zoom)
                iwy = int(cam_y + (psy - SCREEN_H / 2) / zoom)
                if not (0 <= iwx < ww - 1 and 0 <= iwy < wh - 1):
                    continue
                stp = max(1, int(1/zoom))
                e0 = g.world.plan.get_elevation_fast(iwx, iwy)
                l0 = int(e0 / ci)
                l1 = int(g.world.plan.get_elevation_fast(iwx + stp, iwy) / ci)
                l2 = int(g.world.plan.get_elevation_fast(iwx, iwy + stp) / ci)
                if l0 != l1 or l0 != l2:
                    major = (l0 % 4 == 0)
                    cc = (220, 190, 120) if major else (180, 160, 100)
                    pygame.draw.rect(screen, cc, (psx, psy, 2 if major else 1, 2 if major else 1))

    # ── Overlay rendering ─────────────────────────────────────────
    if overlay_mode > 0:
        draw_overlay(screen, overlay_mode, g.world.plan, settlements, rivers,
                     cam_x, cam_y, zoom, SCREEN_W, SCREEN_H, ww, wh,
                     x0, y0, x1, y1, font_sm, font_md,
                     compute_moisture, whittaker_biome)

    # Grid
    if show_grid and zoom >= 2:
        for tx in range(max(0, x0), min(ww, x1)):
            sx = int((tx - cam_x) * zoom) + SCREEN_W // 2
            pygame.draw.line(screen, (40, 40, 50), (sx, 0), (sx, SCREEN_H))
        for ty in range(max(0, y0), min(wh, y1)):
            sy = int((ty - cam_y) * zoom) + SCREEN_H // 2
            pygame.draw.line(screen, (40, 40, 50), (0, sy), (SCREEN_W, sy))

    # Lakes
    if show_rivers:
        for lake in getattr(g.world.plan, 'lakes', []):
            cx_l, cy_l = lake.center
            sx_l = int((cx_l - cam_x) * zoom) + SCREEN_W // 2
            sy_l = int((cy_l - cam_y) * zoom) + SCREEN_H // 2
            rad_px = max(2, int(lake.radius * zoom / 10))
            if -rad_px < sx_l < SCREEN_W + rad_px and -rad_px < sy_l < SCREEN_H + rad_px:
                # Draw lake cells as filled blue area
                for lx, ly in lake.cells:
                    lsx = int((lx - cam_x) * zoom) + SCREEN_W // 2
                    lsy = int((ly - cam_y) * zoom) + SCREEN_H // 2
                    cell_px = max(1, int(10 * zoom))
                    pygame.draw.rect(screen, (45, 95, 160), (lsx, lsy, cell_px, cell_px))

    # Rivers — width varies by flow rank
    if show_rivers:
        for river in rivers:
            pts = getattr(river, 'points', getattr(river, 'waypoints', []))
            if len(pts) >= 2:
                screen_pts = [(int((px - cam_x) * zoom) + SCREEN_W // 2,
                               int((py - cam_y) * zoom) + SCREEN_H // 2) for px, py in pts]
                if any(-50 < sx < SCREEN_W + 50 and -50 < sy < SCREEN_H + 50
                       for sx, sy in screen_pts):
                    rank = getattr(river, 'rank', 'stream')
                    if rank == 'major':
                        w = max(2, int(zoom * 1.2))
                        color = (40, 100, 200)
                    elif rank == 'medium':
                        w = max(1, int(zoom * 0.7))
                        color = (50, 110, 190)
                    else:
                        w = max(1, int(zoom * 0.35))
                        color = (60, 120, 180)
                    pygame.draw.lines(screen, color, False, screen_pts, w)

    # Roads (width/color by type)
    if show_roads:
        for road in g.world.plan.roads:
            pts = getattr(road, 'waypoints', getattr(road, 'points', []))
            if len(pts) >= 2:
                screen_pts = [(int((px - cam_x) * zoom) + SCREEN_W // 2,
                               int((py - cam_y) * zoom) + SCREEN_H // 2) for px, py in pts]
                if any(-50 < sx < SCREEN_W + 50 and -50 < sy < SCREEN_H + 50
                       for sx, sy in screen_pts):
                    rt = getattr(road, 'road_type', 'dirt_track')
                    rc, rw_f = _road_styles.get(rt, ((150, 130, 95), 0.5))
                    pygame.draw.lines(screen, rc, False, screen_pts,
                                      max(1, int(zoom * rw_f)))

    # Internal settlement roads and walls (drawn with buildings)
    if show_buildings and zoom >= 0.2:
        # Road colors and width multipliers by type
        road_colors = {
            "cobblestone": (150, 150, 160),
            "main": (185, 170, 135),
            "gravel": (155, 140, 115),
            "dirt": (120, 100, 70),
            "road": (160, 140, 100),
        }
        road_widths = {
            "cobblestone": 1.2,
            "main": 1.4,
            "gravel": 0.9,
            "dirt": 0.6,
            "road": 0.8,
        }
        for sp in settlements:
            layout = getattr(sp, '_layout', None)
            if not layout:
                continue
            # Internal roads
            for rd in getattr(layout, 'roads', []):
                if len(rd) >= 4:
                    rx1, ry1, rx2, ry2 = rd[0], rd[1], rd[2], rd[3]
                    sx1 = int((rx1 - cam_x) * zoom) + SCREEN_W // 2
                    sy1 = int((ry1 - cam_y) * zoom) + SCREEN_H // 2
                    sx2 = int((rx2 - cam_x) * zoom) + SCREEN_W // 2
                    sy2 = int((ry2 - cam_y) * zoom) + SCREEN_H // 2
                    if any(-50 < s < max(SCREEN_W, SCREEN_H) + 50
                           for s in (sx1, sy1, sx2, sy2)):
                        rtype = rd[4] if len(rd) > 4 else "road"
                        rc = road_colors.get(rtype, (160, 140, 100))
                        wf = road_widths.get(rtype, 0.8)
                        w = max(1, int(zoom * wf))
                        pygame.draw.line(screen, rc, (sx1, sy1), (sx2, sy2), w)
            # Walls/defenses
            defenses = getattr(layout, 'defenses', None)
            if defenses and zoom >= 0.3:
                walls = getattr(defenses, 'wall_points', [])
                if len(walls) >= 2:
                    wall_pts = [(int((wx - cam_x) * zoom) + SCREEN_W // 2,
                                 int((wy - cam_y) * zoom) + SCREEN_H // 2)
                                for wx, wy in walls]
                    pygame.draw.lines(screen, (170, 160, 140), True, wall_pts,
                                      max(2, int(zoom * 1.5)))
                # Gates
                for gx, gy, *_ in getattr(defenses, 'gate_positions', []):
                    gsx = int((gx - cam_x) * zoom) + SCREEN_W // 2
                    gsy = int((gy - cam_y) * zoom) + SCREEN_H // 2
                    gr = max(3, int(zoom * 2.5))
                    pygame.draw.circle(screen, (220, 190, 100), (gsx, gsy), gr)
                    pygame.draw.circle(screen, (140, 120, 70), (gsx, gsy), gr, 1)
                # Towers
                for tx_t, ty_t in getattr(defenses, 'tower_positions', []):
                    tsx = int((tx_t - cam_x) * zoom) + SCREEN_W // 2
                    tsy = int((ty_t - cam_y) * zoom) + SCREEN_H // 2
                    tr = max(3, int(zoom * 2))
                    pygame.draw.rect(screen, (140, 135, 125),
                                     (tsx - tr, tsy - tr, tr * 2, tr * 2))
                    pygame.draw.rect(screen, (90, 85, 80),
                                     (tsx - tr, tsy - tr, tr * 2, tr * 2), 1)

    # Building footprints (P toggles)
    if show_buildings and zoom >= 0.3:
        for sp in settlements:
            if not sp.buildings:
                continue
            for bld in sp.buildings:
                bx = int((bld['x'] - cam_x) * zoom) + SCREEN_W // 2
                by = int((bld['y'] - cam_y) * zoom) + SCREEN_H // 2
                bw_px = max(1, int(bld['w'] * zoom))
                bh_px = max(1, int(bld['h'] * zoom))
                if bx + bw_px < 0 or bx > SCREEN_W or by + bh_px < 0 or by > SCREEN_H:
                    continue
                # Color by building function — distinct per type
                bname = bld.get('name', '').lower()
                if 'tavern' in bname or 'inn' in bname:
                    bc = (180, 110, 50)
                elif 'temple' in bname or 'chapel' in bname:
                    bc = (200, 190, 140)
                elif 'blacksmith' in bname or 'forge' in bname:
                    bc = (60, 60, 70)
                elif 'dock' in bname or 'fish_market' in bname:
                    bc = (80, 100, 120)
                elif 'barn' in bname or 'granary' in bname:
                    bc = (150, 80, 50)
                elif 'market' in bname or 'stall' in bname:
                    bc = (190, 160, 60)
                elif 'workshop' in bname or 'weaver' in bname or 'tanner' in bname:
                    bc = (130, 120, 70)
                elif 'castle' in bname or 'keep' in bname or 'tower' in bname:
                    bc = (130, 130, 140)
                elif 'barracks' in bname or 'guard' in bname or 'armoury' in bname:
                    bc = (110, 90, 75)
                elif 'bakery' in bname:
                    bc = (170, 130, 80)
                elif 'warehouse' in bname:
                    bc = (120, 110, 95)
                elif 'house' in bname or 'cottage' in bname:
                    # Slight random variation for residential
                    h_seed = (bld['x'] * 7 + bld['y'] * 13) % 30
                    bc = (130 + h_seed, 105 + h_seed // 2, 75 + h_seed // 3)
                else:
                    bc = (140, 115, 85)
                pygame.draw.rect(screen, bc, (bx, by, bw_px, bh_px))
                if zoom >= 2:
                    pygame.draw.rect(screen, (80, 70, 60), (bx, by, bw_px, bh_px), 1)
                # Building name labels at high zoom
                if zoom >= 4 and bw_px > 10:
                    blbl = font_sm.render(bname[:12], True, (220, 220, 200))
                    screen.blit(blbl, (bx + 1, by + 1))

    # Farm/crop zones (F toggles)
    if show_farms and zoom >= 0.15:
        draw_farms(screen, settlements, cam_x, cam_y, zoom,
                   SCREEN_W, SCREEN_H, font_sm)

    # Settlement markers (C toggles)
    if show_settlements:
        for sp in settlements:
            sx = int((sp.x - cam_x) * zoom) + SCREEN_W // 2
            sy = int((sp.y - cam_y) * zoom) + SCREEN_H // 2
            if -50 < sx < SCREEN_W + 50 and -50 < sy < SCREEN_H + 50:
                colors = {"city": (255, 60, 60), "town": (255, 160, 60),
                          "village": (255, 255, 100), "hamlet": (200, 200, 200)}
                sc = colors.get(sp.kind, (180, 180, 180))
                if zoom > 0.3:
                    rad_px = int(sp.radius * zoom)
                    if rad_px > 3:
                        pygame.draw.circle(screen, sc, (sx, sy), rad_px, 1)
                pygame.draw.circle(screen, sc, (sx, sy), 3)
                if show_labels and zoom > 0.15:
                    lbl = font_sm.render(f"{sp.name} ({sp.kind})", True, sc)
                    screen.blit(lbl, (sx - lbl.get_width() // 2, sy - 17))

    # ── HUD ──────────────────────────────────────────────────────────
    # Minimap
    mm_x = SCREEN_W - MINIMAP_W - 10
    mm_y = 10
    screen.blit(minimap, (mm_x, mm_y))
    pygame.draw.rect(screen, (100, 100, 120), (mm_x, mm_y, MINIMAP_W, MINIMAP_H), 1)
    cx_mm = int(cam_x / ww * MINIMAP_W) + mm_x
    cy_mm = int(cam_y / wh * MINIMAP_H) + mm_y
    pygame.draw.circle(screen, (255, 255, 255), (cx_mm, cy_mm), 3)
    vw = int(half_w * 2 / ww * MINIMAP_W)
    vh = int(half_h * 2 / wh * MINIMAP_H)
    if vw > 1 and vh > 1:
        pygame.draw.rect(screen, (255, 255, 255),
                         (cx_mm - vw // 2, cy_mm - vh // 2, vw, vh), 1)

    # Info
    overlay_label = OVERLAY_NAMES.get(overlay_mode, "")
    info = [
        f"Pos: ({int(cam_x)}, {int(cam_y)})  Zoom: {zoom:.2f}  Overlay: [{overlay_mode}] {overlay_label}",
        f"Settlements: {len(settlements)}  Rivers: {len(rivers)}  Roads: {len(g.world.plan.roads)}",
        f"R:roads {'ON' if show_roads else 'OFF'}  V:rivers {'ON' if show_rivers else 'OFF'}  "
        f"T:terrain {'ON' if show_terrain else 'OFF'}  C:centers {'ON' if show_settlements else 'OFF'}  "
        f"P:buildings {'ON' if show_buildings else 'OFF'}  O:contours {'ON' if show_contours else 'OFF'}  "
        f"F:farms {'ON' if show_farms else 'OFF'}",
        f"B:labels  G:grid  1-8:overlays  9:off  WASD:pan  Scroll:zoom  TAB:settlement",
    ]
    for i, line in enumerate(info):
        screen.blit(font_sm.render(line, True, (200, 200, 220)), (10, 10 + i * 14))

    if 0 <= settlement_idx < len(settlements):
        sp = settlements[settlement_idx]
        si = font_md.render(
            f">>> {sp.name} ({sp.kind}) pop={sp.population} "
            f"spec={getattr(sp, 'specialization', '?')}",
            True, (255, 220, 100))
        screen.blit(si, (10, SCREEN_H - 24))

    pygame.display.flip()

pygame.quit()
