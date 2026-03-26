"""Rendering functions for the settlement survey.

Replicates the exact drawing code from test_world_viewer.py for use
in headless/offscreen screenshot capture.
"""

import pygame
from game.settings import TERRAIN_COLORS
from viewers.overlay_helpers import draw_farms


_TILE_COLORS = dict(TERRAIN_COLORS)
_TILE_COLORS.setdefault(70, (40, 35, 30))
_TILE_COLORS.setdefault(71, (180, 210, 230))

_ROAD_STYLES = {
    "king_road": ((200, 180, 140), 1.2),
    "paved_road": ((170, 165, 155), 0.9),
    "gravel_road": ((155, 135, 100), 0.6),
    "dirt_track": ((130, 110, 80), 0.4),
}

_ROAD_COLORS = {
    "road": (160, 140, 100),
    "cobblestone": (150, 150, 160),
    "dirt": (140, 120, 90),
    "main": (180, 160, 120),
}


def _elev_color(elev):
    if elev < 0.23:
        return (41, 100, 160)
    elif elev < 0.30:
        return (180, 170, 130)
    elif elev < 0.45:
        return (70, 130, 60)
    elif elev < 0.55:
        return (50, 110, 40)
    elif elev < 0.65:
        return (120, 105, 85)
    return (200, 200, 210)


def draw_terrain(surf, g, cam_x, cam_y, zoom, sw, sh, ww, wh):
    """Draw terrain tiles, matching test_world_viewer.py logic."""
    half_w = sw / 2 / zoom
    half_h = sh / 2 / zoom
    x0 = int(cam_x - half_w) - 1
    y0 = int(cam_y - half_h) - 1
    x1 = int(cam_x + half_w) + 2
    y1 = int(cam_y + half_h) + 2
    tile_px = max(1, round(zoom))

    if zoom >= 0.5:
        vx0, vy0 = max(0, x0), max(0, y0)
        vx1, vy1 = min(ww, x1), min(wh, y1)
        max_axis = min(300, int(sw / zoom) + 2)
        if vx1 - vx0 > max_axis:
            mid = (vx0 + vx1) // 2
            vx0, vx1 = mid - max_axis // 2, mid + max_axis // 2
        if vy1 - vy0 > max_axis:
            mid = (vy0 + vy1) // 2
            vy0, vy1 = mid - max_axis // 2, mid + max_axis // 2
        for ty in range(vy0, vy1):
            for tx in range(vx0, vx1):
                sx = int((tx - cam_x) * zoom) + sw // 2
                sy = int((ty - cam_y) * zoom) + sh // 2
                if sx + tile_px < 0 or sx > sw or sy + tile_px < 0 or sy > sh:
                    continue
                try:
                    tile = g.world.get_tile(tx, ty)
                except Exception:
                    tile = -1
                color = (_TILE_COLORS.get(tile, (80, 80, 80)) if tile >= 0
                         else _elev_color(g.world.plan.get_elevation_fast(tx, ty)))
                if tile_px <= 1:
                    if 0 <= sx < sw and 0 <= sy < sh:
                        surf.set_at((sx, sy), color)
                else:
                    pygame.draw.rect(surf, color, (sx, sy, tile_px, tile_px))
    else:
        # Low-zoom elevation-based rendering
        for psy in range(0, sh, 2):
            for psx in range(0, sw, 2):
                iwx = int(cam_x + (psx - sw / 2) / zoom)
                iwy = int(cam_y + (psy - sh / 2) / zoom)
                if 0 <= iwx < ww and 0 <= iwy < wh:
                    c = _elev_color(g.world.plan.get_elevation_fast(iwx, iwy))
                    surf.set_at((psx, psy), c)
                    surf.set_at((psx + 1, psy), c)
                    surf.set_at((psx, psy + 1), c)
                    surf.set_at((psx + 1, psy + 1), c)


def draw_lakes(surf, lakes, cam_x, cam_y, zoom, sw, sh):
    """Draw lake polygons as filled blue areas."""
    for lake in lakes:
        cx_l, cy_l = lake.center
        sx_l = int((cx_l - cam_x) * zoom) + sw // 2
        sy_l = int((cy_l - cam_y) * zoom) + sh // 2
        rad_px = max(2, int(lake.radius * zoom / 10))
        if -rad_px < sx_l < sw + rad_px and -rad_px < sy_l < sh + rad_px:
            for lx, ly in lake.cells:
                lsx = int((lx - cam_x) * zoom) + sw // 2
                lsy = int((ly - cam_y) * zoom) + sh // 2
                cell_px = max(1, int(10 * zoom))
                pygame.draw.rect(surf, (45, 95, 160),
                                 (lsx, lsy, cell_px, cell_px))


def draw_rivers(surf, rivers, cam_x, cam_y, zoom, sw, sh):
    """Draw river lines with width varying by flow rank."""
    for river in rivers:
        pts = getattr(river, 'points', getattr(river, 'waypoints', []))
        if len(pts) >= 2:
            screen_pts = [
                (int((px - cam_x) * zoom) + sw // 2,
                 int((py - cam_y) * zoom) + sh // 2)
                for px, py in pts
            ]
            if any(-50 < sx < sw + 50 and -50 < sy < sh + 50
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
                pygame.draw.lines(surf, color, False, screen_pts, w)


def draw_roads(surf, roads, cam_x, cam_y, zoom, sw, sh):
    """Draw inter-settlement roads with width/color by type."""
    for road in roads:
        pts = getattr(road, 'waypoints', getattr(road, 'points', []))
        if len(pts) >= 2:
            screen_pts = [
                (int((px - cam_x) * zoom) + sw // 2,
                 int((py - cam_y) * zoom) + sh // 2)
                for px, py in pts
            ]
            if any(-50 < sx < sw + 50 and -50 < sy < sh + 50
                   for sx, sy in screen_pts):
                rt = getattr(road, 'road_type', 'dirt_track')
                rc, rw_f = _ROAD_STYLES.get(rt, ((150, 130, 95), 0.5))
                pygame.draw.lines(surf, rc, False, screen_pts,
                                  max(1, int(zoom * rw_f)))


def draw_internal_roads_and_walls(surf, settlements, cam_x, cam_y, zoom,
                                  sw, sh):
    """Draw internal settlement roads, walls, gates, and towers."""
    if zoom < 0.2:
        return
    for sp in settlements:
        layout = getattr(sp, '_layout', None)
        if not layout:
            continue
        # Internal roads
        for rd in getattr(layout, 'roads', []):
            if len(rd) >= 4:
                rx1, ry1, rx2, ry2 = rd[0], rd[1], rd[2], rd[3]
                sx1 = int((rx1 - cam_x) * zoom) + sw // 2
                sy1 = int((ry1 - cam_y) * zoom) + sh // 2
                sx2 = int((rx2 - cam_x) * zoom) + sw // 2
                sy2 = int((ry2 - cam_y) * zoom) + sh // 2
                if any(-50 < s < max(sw, sh) + 50
                       for s in (sx1, sy1, sx2, sy2)):
                    rc = _ROAD_COLORS.get(
                        rd[4] if len(rd) > 4 else "road",
                        (160, 140, 100))
                    w = max(1, int(zoom * 0.8))
                    pygame.draw.line(surf, rc, (sx1, sy1), (sx2, sy2), w)
        # Walls/defenses
        defenses = getattr(layout, 'defenses', None)
        if defenses and zoom >= 0.3:
            walls = getattr(defenses, 'wall_points', [])
            if len(walls) >= 2:
                wall_pts = [
                    (int((wx - cam_x) * zoom) + sw // 2,
                     int((wy - cam_y) * zoom) + sh // 2)
                    for wx, wy in walls
                ]
                pygame.draw.lines(surf, (170, 160, 140), True,
                                  wall_pts, max(2, int(zoom * 1.5)))
            # Gates
            for gx, gy, *_ in getattr(defenses, 'gate_positions', []):
                gsx = int((gx - cam_x) * zoom) + sw // 2
                gsy = int((gy - cam_y) * zoom) + sh // 2
                gr = max(3, int(zoom * 2.5))
                pygame.draw.circle(surf, (220, 190, 100), (gsx, gsy), gr)
                pygame.draw.circle(surf, (140, 120, 70), (gsx, gsy), gr, 1)
            # Towers
            for tx_t, ty_t in getattr(defenses, 'tower_positions', []):
                tsx = int((tx_t - cam_x) * zoom) + sw // 2
                tsy = int((ty_t - cam_y) * zoom) + sh // 2
                tr = max(3, int(zoom * 2))
                pygame.draw.rect(surf, (140, 135, 125),
                                 (tsx - tr, tsy - tr, tr * 2, tr * 2))
                pygame.draw.rect(surf, (90, 85, 80),
                                 (tsx - tr, tsy - tr, tr * 2, tr * 2), 1)


def draw_buildings(surf, settlements, cam_x, cam_y, zoom, sw, sh):
    """Draw building footprints colored by function."""
    if zoom < 0.3:
        return
    for sp in settlements:
        if not sp.buildings:
            continue
        for bld in sp.buildings:
            bx = int((bld['x'] - cam_x) * zoom) + sw // 2
            by = int((bld['y'] - cam_y) * zoom) + sw // 2
            bw_px = max(1, int(bld['w'] * zoom))
            bh_px = max(1, int(bld['h'] * zoom))
            if bx + bw_px < 0 or bx > sw or by + bh_px < 0 or by > sh:
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
            pygame.draw.rect(surf, bc, (bx, by, bw_px, bh_px))
            if zoom >= 2:
                pygame.draw.rect(surf, (80, 70, 60),
                                 (bx, by, bw_px, bh_px), 1)


def draw_settlement_markers(surf, settlements, cam_x, cam_y, zoom,
                            sw, sh, font_sm):
    """Draw settlement center markers and labels."""
    for sp in settlements:
        sx = int((sp.x - cam_x) * zoom) + sw // 2
        sy = int((sp.y - cam_y) * zoom) + sh // 2
        if -50 < sx < sw + 50 and -50 < sy < sh + 50:
            colors = {
                "city": (255, 60, 60),
                "town": (255, 160, 60),
                "village": (255, 255, 100),
                "hamlet": (200, 200, 200),
            }
            sc = colors.get(sp.kind, (180, 180, 180))
            if zoom > 0.3:
                rad_px = int(sp.radius * zoom)
                if rad_px > 3:
                    pygame.draw.circle(surf, sc, (sx, sy), rad_px, 1)
            pygame.draw.circle(surf, sc, (sx, sy), 3)
            if zoom > 0.15:
                lbl = font_sm.render(f"{sp.name} ({sp.kind})", True, sc)
                surf.blit(lbl, (sx - lbl.get_width() // 2, sy - 18))


def draw_farm_zones(surf, settlements, cam_x, cam_y, zoom, sw, sh,
                    font_sm):
    """Draw farm/crop zones as semi-transparent overlays."""
    if zoom < 0.15:
        return
    draw_farms(surf, settlements, cam_x, cam_y, zoom, sw, sh, font_sm)


def render_view(surf, g, cam_x, cam_y, zoom, sw, sh, ww, wh,
                settlements, rivers, roads, font_sm):
    """Full render pass matching test_world_viewer.py with all layers on."""
    surf.fill((20, 30, 40))
    draw_terrain(surf, g, cam_x, cam_y, zoom, sw, sh, ww, wh)
    lakes = getattr(g.world.plan, 'lakes', [])
    draw_lakes(surf, lakes, cam_x, cam_y, zoom, sw, sh)
    draw_rivers(surf, rivers, cam_x, cam_y, zoom, sw, sh)
    draw_roads(surf, roads, cam_x, cam_y, zoom, sw, sh)
    draw_internal_roads_and_walls(surf, settlements, cam_x, cam_y, zoom,
                                 sw, sh)
    draw_buildings(surf, settlements, cam_x, cam_y, zoom, sw, sh)
    draw_farm_zones(surf, settlements, cam_x, cam_y, zoom, sw, sh,
                    font_sm)
    draw_settlement_markers(surf, settlements, cam_x, cam_y, zoom,
                            sw, sh, font_sm)
