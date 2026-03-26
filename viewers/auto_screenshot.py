#!/usr/bin/env python3
"""Automated screenshot capture for settlement analysis.

Launches the world viewer headlessly, navigates to settlements at various
zoom levels, and saves screenshots for visual analysis.
"""

import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['SDL_VIDEODRIVER'] = 'cocoa'

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 1280, 800
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Auto Screenshot")
clock = pygame.time.Clock()
font_sm = pygame.font.SysFont("monospace", 11)
font_md = pygame.font.SysFont("monospace", 14, bold=True)
font_lg = pygame.font.SysFont("monospace", 24, bold=True)

from game.settings import TERRAIN_COLORS
from game.world.terrain_gen import compute_moisture, whittaker_biome
from viewers.overlay_helpers import draw_overlay, OVERLAY_NAMES

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


print("Generating world...")
t0 = time.time()

# Use a separate dummy display for HeadlessGame
old_screen = screen
dummy = pygame.display.set_mode((100, 100))
from game.ui.screenshot import HeadlessGame
g = HeadlessGame(seed=42, mode='god', spawn_location='test_island', use_chunked=True)
gen_time = time.time() - t0
print(f"World generated in {gen_time:.1f}s")

# Restore real display
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))

ww = getattr(g.world.plan, 'world_width', 10000)
wh = getattr(g.world.plan, 'world_height', 10000)
settlements = g.world.plan.settlements
rivers = g.world.plan.rivers


def world_to_screen(wx, wy, cam_x, cam_y, zoom):
    return (int((wx - cam_x) * zoom) + SCREEN_W // 2,
            int((wy - cam_y) * zoom) + SCREEN_H // 2)


def render_frame(cam_x, cam_y, zoom, show_farms=False, overlay_mode=0,
                 show_roads=True, show_rivers=True, show_buildings=True,
                 show_labels=True, show_settlements=True):
    """Render a single frame and return the surface."""
    screen.fill((20, 30, 40))

    half_w = SCREEN_W / 2 / zoom
    half_h = SCREEN_H / 2 / zoom
    x0, y0 = int(cam_x - half_w) - 1, int(cam_y - half_h) - 1
    x1, y1 = int(cam_x + half_w) + 2, int(cam_y + half_h) + 2
    tile_px = max(1, round(zoom))

    # Terrain
    if zoom >= 0.5:
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

    # Overlay
    if overlay_mode > 0:
        draw_overlay(screen, overlay_mode, g.world.plan, settlements, rivers,
                     cam_x, cam_y, zoom, SCREEN_W, SCREEN_H, ww, wh,
                     x0, y0, x1, y1, font_sm, font_md,
                     compute_moisture, whittaker_biome)

    # Rivers
    if show_rivers:
        for river in rivers:
            pts = getattr(river, 'points', getattr(river, 'waypoints', []))
            if len(pts) >= 2:
                screen_pts = [(int((px - cam_x) * zoom) + SCREEN_W // 2,
                               int((py - cam_y) * zoom) + SCREEN_H // 2) for px, py in pts]
                if any(-50 < sx < SCREEN_W + 50 and -50 < sy < SCREEN_H + 50
                       for sx, sy in screen_pts):
                    w = max(1, int(zoom * 0.3))
                    pygame.draw.lines(screen, (50, 110, 190), False, screen_pts, w)

    # Roads
    if show_roads:
        for road in g.world.plan.roads:
            pts = getattr(road, 'waypoints', getattr(road, 'points', []))
            if len(pts) >= 2:
                screen_pts = [(int((px - cam_x) * zoom) + SCREEN_W // 2,
                               int((py - cam_y) * zoom) + SCREEN_H // 2) for px, py in pts]
                if any(-50 < sx < SCREEN_W + 50 and -50 < sy < SCREEN_H + 50
                       for sx, sy in screen_pts):
                    pygame.draw.lines(screen, (170, 145, 100), False, screen_pts,
                                      max(1, int(zoom * 0.5)))

    # Internal roads and walls
    if show_buildings and zoom >= 0.2:
        road_colors = {"road": (160, 140, 100), "cobblestone": (150, 150, 160),
                       "dirt": (140, 120, 90), "main": (180, 160, 120)}
        for sp in settlements:
            layout = getattr(sp, '_layout', None)
            if not layout:
                continue
            for rd in getattr(layout, 'roads', []):
                if len(rd) >= 4:
                    rx1, ry1, rx2, ry2 = rd[0], rd[1], rd[2], rd[3]
                    sx1 = int((rx1 - cam_x) * zoom) + SCREEN_W // 2
                    sy1 = int((ry1 - cam_y) * zoom) + SCREEN_H // 2
                    sx2 = int((rx2 - cam_x) * zoom) + SCREEN_W // 2
                    sy2 = int((ry2 - cam_y) * zoom) + SCREEN_H // 2
                    if any(-50 < s < max(SCREEN_W, SCREEN_H) + 50
                           for s in (sx1, sy1, sx2, sy2)):
                        rc = road_colors.get(rd[4] if len(rd) > 4 else "road",
                                             (160, 140, 100))
                        w = max(1, int(zoom * 0.8))
                        pygame.draw.line(screen, rc, (sx1, sy1), (sx2, sy2), w)
            # Walls
            defenses = getattr(layout, 'defenses', None)
            if defenses and zoom >= 0.3:
                walls = getattr(defenses, 'wall_points', [])
                if len(walls) >= 2:
                    wall_pts = [(int((wx_w - cam_x) * zoom) + SCREEN_W // 2,
                                 int((wy_w - cam_y) * zoom) + SCREEN_H // 2)
                                for wx_w, wy_w in walls]
                    pygame.draw.lines(screen, (110, 105, 95), True, wall_pts,
                                      max(1, int(zoom * 0.5)))
                for gx, gy, *_ in getattr(defenses, 'gate_positions', []):
                    gsx = int((gx - cam_x) * zoom) + SCREEN_W // 2
                    gsy = int((gy - cam_y) * zoom) + SCREEN_H // 2
                    pygame.draw.circle(screen, (180, 160, 100), (gsx, gsy),
                                       max(2, int(zoom * 1.5)))

    # Buildings
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
                bname = bld.get('name', '').lower()
                if 'tavern' in bname or 'inn' in bname:
                    bc = (150, 95, 55)
                elif 'temple' in bname or 'chapel' in bname:
                    bc = (200, 190, 140)
                elif 'blacksmith' in bname or 'forge' in bname:
                    bc = (80, 80, 90)
                elif 'shop' in bname or 'market' in bname:
                    bc = (160, 120, 60)
                elif 'castle' in bname or 'keep' in bname or 'tower' in bname:
                    bc = (120, 120, 130)
                elif 'barracks' in bname or 'guard' in bname:
                    bc = (130, 100, 80)
                else:
                    bc = (140, 115, 85)
                pygame.draw.rect(screen, bc, (bx, by, bw_px, bh_px))
                if zoom >= 2:
                    pygame.draw.rect(screen, (80, 70, 60), (bx, by, bw_px, bh_px), 1)

    # Farms overlay
    if show_farms and zoom >= 0.15:
        farm_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        for sp in settlements:
            layout = getattr(sp, '_layout', None)
            if not layout:
                continue
            for farm in getattr(layout, 'farms', []):
                if len(farm) >= 3:
                    fx, fy, fr = farm[0], farm[1], farm[2]
                    fsx = int((fx - cam_x) * zoom) + SCREEN_W // 2
                    fsy = int((fy - cam_y) * zoom) + SCREEN_H // 2
                    fsr = max(2, int(fr * zoom))
                    if -fsr < fsx < SCREEN_W + fsr and -fsr < fsy < SCREEN_H + fsr:
                        pygame.draw.circle(farm_surf, (120, 160, 50, 70),
                                           (fsx, fsy), fsr)
                        pygame.draw.circle(farm_surf, (80, 140, 30, 120),
                                           (fsx, fsy), fsr, max(1, int(zoom * 0.5)))
            for zname, (zx, zy, zw, zh) in getattr(layout, 'zones', {}).items():
                if 'farm' in zname.lower():
                    zsx = int((zx - cam_x) * zoom) + SCREEN_W // 2
                    zsy = int((zy - cam_y) * zoom) + SCREEN_H // 2
                    zsw = max(2, int(zw * zoom))
                    zsh = max(2, int(zh * zoom))
                    if zsx + zsw > 0 and zsx < SCREEN_W and zsy + zsh > 0 and zsy < SCREEN_H:
                        pygame.draw.rect(farm_surf, (140, 180, 50, 50),
                                         (zsx, zsy, zsw, zsh))
        screen.blit(farm_surf, (0, 0))

    # Settlement markers
    if show_settlements:
        for sp in settlements:
            sx = int((sp.x - cam_x) * zoom) + SCREEN_W // 2
            sy = int((sp.y - cam_y) * zoom) + SCREEN_H // 2
            if -50 < sx < SCREEN_W + 50 and -50 < sy < SCREEN_H + 50:
                colors = {"city": (255, 60, 60), "town": (255, 160, 60),
                          "village": (255, 255, 100), "hamlet": (200, 200, 200)}
                sc = colors.get(sp.kind, (180, 180, 180))
                r = max(2, int(sp.radius * zoom * 0.1))
                if zoom > 0.3:
                    rad_px = int(sp.radius * zoom)
                    if rad_px > 3:
                        pygame.draw.circle(screen, sc, (sx, sy), rad_px, 1)
                pygame.draw.circle(screen, sc, (sx, sy), max(2, r))
                if show_labels and zoom > 0.15:
                    lbl = font_sm.render(f"{sp.name} ({sp.kind})", True, sc)
                    screen.blit(lbl, (sx - lbl.get_width() // 2, sy - r - 14))

    # Info text
    overlay_label = OVERLAY_NAMES.get(overlay_mode, "")
    info = f"Pos: ({int(cam_x)}, {int(cam_y)})  Zoom: {zoom:.2f}  Overlay: [{overlay_mode}] {overlay_label}"
    screen.blit(font_sm.render(info, True, (200, 200, 220)), (10, 10))

    pygame.display.flip()


def save_screenshot(name):
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        f"screenshot_{name}.png")
    pygame.image.save(screen, path)
    print(f"  Saved: {path}")
    return path


# ── Take automated screenshots ──────────────────────────────────────

screenshots = []

# 1. Full world overview
print("\n1. Full world overview...")
cam_x, cam_y = ww / 2, wh / 2
zoom = min(SCREEN_W / ww, SCREEN_H / wh) * 0.9
render_frame(cam_x, cam_y, zoom)
screenshots.append(save_screenshot("01_world_overview"))

# Process events to keep window alive
for e in pygame.event.get():
    pass

# 2-7. Individual settlements at various zoom levels
# Find settlements of different types
cities = [s for s in settlements if s.kind == "city"]
towns = [s for s in settlements if s.kind == "town"]
villages = [s for s in settlements if s.kind == "village"]
hamlets = [s for s in settlements if s.kind == "hamlet"]

print(f"\nSettlement counts: {len(cities)} cities, {len(towns)} towns, "
      f"{len(villages)} villages, {len(hamlets)} hamlets")

targets = []
if cities:
    targets.append(("city", cities[0]))
if len(cities) > 1:
    targets.append(("city2", cities[1]))
if towns:
    targets.append(("town", towns[0]))
if len(towns) > 1:
    targets.append(("town2", towns[1]))
if villages:
    targets.append(("village", villages[0]))
if hamlets:
    targets.append(("hamlet", hamlets[0]))

for idx, (label, sp) in enumerate(targets):
    print(f"\n{idx+2}. Settlement: {sp.name} ({sp.kind}), pop={sp.population}, "
          f"spec={getattr(sp, 'specialization', '?')}")
    cam_x, cam_y = float(sp.x), float(sp.y)

    # Medium zoom - see the whole settlement
    zoom = max(1.5, 200.0 / max(1, sp.radius))
    render_frame(cam_x, cam_y, zoom)
    screenshots.append(save_screenshot(f"{idx+2:02d}_{label}_medium"))

    for e in pygame.event.get():
        pass

    # Close zoom - see building detail
    zoom = max(3.0, 400.0 / max(1, sp.radius))
    render_frame(cam_x, cam_y, zoom)
    screenshots.append(save_screenshot(f"{idx+2:02d}_{label}_close"))

    for e in pygame.event.get():
        pass

    # With farms overlay
    zoom = max(1.5, 200.0 / max(1, sp.radius))
    render_frame(cam_x, cam_y, zoom, show_farms=True)
    screenshots.append(save_screenshot(f"{idx+2:02d}_{label}_farms"))

    for e in pygame.event.get():
        pass

# 8. Overlay modes - elevation, moisture, biome
print("\n8. Overlay modes...")
cam_x, cam_y = ww / 2, wh / 2
zoom = min(SCREEN_W / ww, SCREEN_H / wh) * 0.9

for ov_mode in [1, 2, 3, 6, 7]:
    ov_name = OVERLAY_NAMES.get(ov_mode, f"mode{ov_mode}")
    render_frame(cam_x, cam_y, zoom, overlay_mode=ov_mode)
    safe_name = ov_name.lower().replace(' ', '_').replace('/', '_')
    screenshots.append(save_screenshot(f"09_overlay_{safe_name}"))
    for e in pygame.event.get():
        pass

# 9. Road network zoomed
print("\n9. Road network...")
if towns:
    sp = towns[0]
    cam_x, cam_y = float(sp.x), float(sp.y)
    zoom = 0.5
    render_frame(cam_x, cam_y, zoom)
    screenshots.append(save_screenshot("10_road_network"))

print(f"\n=== Done! {len(screenshots)} screenshots saved ===")
print("Screenshots:")
for s in screenshots:
    print(f"  {s}")

pygame.quit()
