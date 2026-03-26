"""Overlay color mapping and rendering helpers for the world viewer.

Provides color gradient functions and draw_overlay() dispatcher to keep
the main viewer file under 500 lines.
"""

import numpy as np
import pygame


def _lerp(c1, c2, t):
    """Linearly interpolate between two RGB tuples."""
    t = max(0.0, min(1.0, t))
    return (int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t))


def elevation_color(elev):
    """Blue -> green -> brown -> white gradient for elevation 0-1."""
    if elev < 0.25:  return _lerp((20, 40, 140), (40, 100, 180), elev / 0.25)
    if elev < 0.35:  return _lerp((40, 100, 180), (60, 160, 80), (elev - 0.25) / 0.10)
    if elev < 0.55:  return _lerp((60, 160, 80), (40, 120, 40), (elev - 0.35) / 0.20)
    if elev < 0.70:  return _lerp((40, 120, 40), (140, 110, 70), (elev - 0.55) / 0.15)
    if elev < 0.85:  return _lerp((140, 110, 70), (180, 170, 160), (elev - 0.70) / 0.15)
    return _lerp((180, 170, 160), (240, 245, 250), (elev - 0.85) / 0.15)


def moisture_color(moist):
    """Brown -> green -> blue gradient for moisture 0-1."""
    if moist < 0.3:  return _lerp((160, 120, 60), (120, 140, 50), moist / 0.3)
    if moist < 0.6:  return _lerp((120, 140, 50), (40, 160, 80), (moist - 0.3) / 0.3)
    return _lerp((40, 160, 80), (30, 80, 200), (moist - 0.6) / 0.4)


def flow_color(intensity):
    """Dark -> bright cyan for flow accumulation 0-1."""
    if intensity < 0.01:
        return None
    return _lerp((15, 20, 30), (40, 200, 255), min(1.0, intensity * 3.0))


BIOME_COLORS = {
    1: (41, 128, 185), 2: (220, 200, 140), 3: (100, 170, 80),
    4: (40, 120, 50), 5: (25, 75, 25), 6: (160, 140, 120),
    7: (235, 240, 245), 70: (100, 90, 75), 13: (65, 100, 50),
}

SPEC_COLORS = {
    "mining": (180, 140, 60), "farming": (100, 160, 50),
    "fishing": (50, 130, 200), "trade": (200, 170, 50),
    "military": (200, 60, 60), "religious": (180, 160, 220),
    "academic": (100, 100, 200), "crafting": (200, 130, 60),
    "logging": (120, 90, 50), "port": (60, 140, 180),
}

KINGDOM_COLORS = [
    (220, 60, 60), (60, 160, 220), (60, 200, 80), (220, 180, 40),
    (180, 60, 200), (200, 120, 40), (60, 200, 200), (200, 80, 140),
    (140, 200, 60), (100, 80, 200), (200, 160, 120), (80, 140, 100),
]

OVERLAY_NAMES = {
    0: "Normal", 1: "Elevation", 2: "Moisture", 3: "Biome",
    4: "Flow Accumulation", 5: "Mountain Spine", 6: "Settlements/Wards",
    7: "Kingdom Territories", 8: "Chunk Debug Grid", 9: "Normal (overlays off)",
}


# ── Rendering functions ──────────────────────────────────────────────

def _draw_pixel_overlay(screen, mode, plan, rivers, cam_x, cam_y, zoom,
                        sw, sh, ww, wh, compute_moisture_fn, whittaker_fn):
    """Draw per-pixel overlays: elevation(1), moisture(2), biome(3), flow(4)."""
    step = max(2, int(4 / max(0.1, zoom)))
    seed = plan.seed
    for psy in range(0, sh, step):
        for psx in range(0, sw, step):
            iwx = int(cam_x + (psx - sw / 2) / zoom)
            iwy = int(cam_y + (psy - sh / 2) / zoom)
            if not (0 <= iwx < ww and 0 <= iwy < wh):
                continue
            elev = plan.get_elevation_fast(iwx, iwy)
            if mode == 1:
                c = elevation_color(elev)
            elif mode == 2:
                wa = np.array([iwx], dtype=np.float32)
                ya = np.array([iwy], dtype=np.float32)
                ea = np.array([elev], dtype=np.float32)
                c = moisture_color(float(compute_moisture_fn(wa, ya, ea, seed, ww, wh)[0]))
            elif mode == 3:
                wa = np.array([iwx], dtype=np.float32)
                ya = np.array([iwy], dtype=np.float32)
                ea = np.array([elev], dtype=np.float32)
                m = compute_moisture_fn(wa, ya, ea, seed, ww, wh)
                c = BIOME_COLORS.get(int(whittaker_fn(ea, m)[0]), (80, 80, 80))
            else:  # mode 4 — flow accumulation via river proximity
                min_d = 999999
                for river in rivers:
                    pts = getattr(river, 'points', [])
                    for rx, ry in pts[::max(1, len(pts) // 20)]:
                        d = abs(rx - iwx) + abs(ry - iwy)
                        if d < min_d:
                            min_d = d
                c = flow_color(max(0, 1.0 - min_d / 300.0))
                if c is None:
                    continue
            if step <= 1:
                screen.set_at((psx, psy), c)
            else:
                pygame.draw.rect(screen, c, (psx, psy, step, step))


def _draw_spine(screen, plan, cam_x, cam_y, zoom, sw, sh):
    """Draw mountain spine waypoints and connecting lines."""
    spine = getattr(plan, '_mountain_spine', [])
    for sx, sy in spine:
        px = int((sx - cam_x) * zoom) + sw // 2
        py = int((sy - cam_y) * zoom) + sh // 2
        if -10 < px < sw + 10 and -10 < py < sh + 10:
            pygame.draw.circle(screen, (255, 100, 50), (px, py), max(2, int(zoom * 3)))
    if len(spine) >= 2:
        pts = [(int((sx - cam_x) * zoom) + sw // 2,
                int((sy - cam_y) * zoom) + sh // 2) for sx, sy in spine]
        for j in range(len(pts) - 1):
            pygame.draw.line(screen, (255, 160, 60), pts[j], pts[j + 1], 1)


def _draw_settlements_overlay(screen, settlements, cam_x, cam_y, zoom, sw, sh, font):
    """Draw settlement specializations and ward zones."""
    for sp in settlements:
        sx = int((sp.x - cam_x) * zoom) + sw // 2
        sy = int((sp.y - cam_y) * zoom) + sh // 2
        if not (-50 < sx < sw + 50 and -50 < sy < sh + 50):
            continue
        spec = getattr(sp, 'specialization', 'unknown')
        sc = SPEC_COLORS.get(spec, (150, 150, 150))
        r = max(4, int(sp.radius * zoom * 0.15))
        pygame.draw.circle(screen, sc, (sx, sy), r)
        pygame.draw.circle(screen, (255, 255, 255), (sx, sy), r, 1)
        if zoom > 0.15:
            lbl = font.render(f"{sp.name}: {spec}", True, sc)
            screen.blit(lbl, (sx - lbl.get_width() // 2, sy - r - 14))
        layout = getattr(sp, '_layout', None)
        if layout and zoom > 0.3:
            for zname, (zx, zy, zw, zh) in getattr(layout, 'zones', {}).items():
                zsx = int((zx - cam_x) * zoom) + sw // 2
                zsy = int((zy - cam_y) * zoom) + sh // 2
                zsw, zsh = max(2, int(zw * zoom)), max(2, int(zh * zoom))
                pygame.draw.rect(screen, sc, (zsx, zsy, zsw, zsh), 1)
                if zoom > 1.0:
                    zl = font.render(zname, True, (200, 200, 200))
                    screen.blit(zl, (zsx + 2, zsy + 2))


def _draw_kingdoms(screen, plan, cam_x, cam_y, zoom, sw, sh, ww, wh, font):
    """Draw Voronoi-style kingdom territory fill with labels."""
    kingdoms = getattr(plan, 'kingdoms', [])
    if not kingdoms:
        return
    step = max(4, int(8 / max(0.1, zoom)))
    for psy in range(0, sh, step):
        for psx in range(0, sw, step):
            iwx = int(cam_x + (psx - sw / 2) / zoom)
            iwy = int(cam_y + (psy - sh / 2) / zoom)
            if not (0 <= iwx < ww and 0 <= iwy < wh):
                continue
            best_k, best_d = -1, 999999999
            for ki, k in enumerate(kingdoms):
                d = (iwx - k.get('center_x', 0)) ** 2 + (iwy - k.get('center_y', 0)) ** 2
                if d < best_d:
                    best_d, best_k = d, ki
            if best_k >= 0:
                base = KINGDOM_COLORS[best_k % len(KINGDOM_COLORS)]
                pygame.draw.rect(screen, (base[0]//2, base[1]//2, base[2]//2),
                                 (psx, psy, step, step))
    for ki, k in enumerate(kingdoms):
        kx = int((k.get('center_x', 0) - cam_x) * zoom) + sw // 2
        ky = int((k.get('center_y', 0) - cam_y) * zoom) + sh // 2
        if -50 < kx < sw + 50 and -50 < ky < sh + 50:
            kc = KINGDOM_COLORS[ki % len(KINGDOM_COLORS)]
            pygame.draw.circle(screen, kc, (kx, ky), 6)
            lbl = font.render(k.get('name', f'K{ki}'), True, kc)
            screen.blit(lbl, (kx - lbl.get_width() // 2, ky - 20))


def _draw_chunk_grid(screen, cam_x, cam_y, zoom, sw, sh, ww, wh, x0, y0, x1, y1, font):
    """Draw chunk boundaries with coordinate labels."""
    csz = 200
    cx_s = max(0, (x0 // csz) * csz)
    for cx in range(cx_s, min(ww, x1) + csz, csz):
        sx = int((cx - cam_x) * zoom) + sw // 2
        if 0 <= sx < sw:
            pygame.draw.line(screen, (0, 255, 200), (sx, 0), (sx, sh), 1)
    cy_s = max(0, (y0 // csz) * csz)
    for cy in range(cy_s, min(wh, y1) + csz, csz):
        sy = int((cy - cam_y) * zoom) + sh // 2
        if 0 <= sy < sh:
            pygame.draw.line(screen, (0, 255, 200), (0, sy), (sw, sy), 1)
    if zoom > 0.08:
        for cx in range(cx_s, min(ww, x1) + csz, csz):
            for cy in range(cy_s, min(wh, y1) + csz, csz):
                sx = int((cx - cam_x) * zoom) + sw // 2 + 3
                sy = int((cy - cam_y) * zoom) + sh // 2 + 3
                if 0 < sx < sw - 40 and 0 < sy < sh - 12:
                    lbl = font.render(f"{cx//csz},{cy//csz}", True, (0, 200, 170))
                    screen.blit(lbl, (sx, sy))


def draw_farms(screen, settlements, cam_x, cam_y, zoom, sw, sh, font):
    """Draw farm/crop zones as semi-transparent overlays."""
    farm_surf = pygame.Surface((sw, sh), pygame.SRCALPHA)
    fc = (120, 160, 50, 70)
    fc_outline = (80, 140, 30, 120)
    for sp in settlements:
        layout = getattr(sp, '_layout', None)
        if not layout:
            continue
        for farm in getattr(layout, 'farms', []):
            if len(farm) < 3:
                continue
            fx, fy, fr = farm[0], farm[1], farm[2]
            fsx = int((fx - cam_x) * zoom) + sw // 2
            fsy = int((fy - cam_y) * zoom) + sh // 2
            fsr = max(2, int(fr * zoom))
            if -fsr < fsx < sw + fsr and -fsr < fsy < sh + fsr:
                pygame.draw.circle(farm_surf, fc, (fsx, fsy), fsr)
                pygame.draw.circle(farm_surf, fc_outline, (fsx, fsy), fsr,
                                   max(1, int(zoom * 0.5)))
                if zoom >= 1.0:
                    fl = font.render("farm", True, (100, 180, 50))
                    farm_surf.blit(fl, (fsx - fl.get_width() // 2,
                                        fsy - fl.get_height() // 2))
        for zname, (zx, zy, zw, zh) in getattr(layout, 'zones', {}).items():
            if 'farm' not in zname.lower():
                continue
            zsx = int((zx - cam_x) * zoom) + sw // 2
            zsy = int((zy - cam_y) * zoom) + sh // 2
            zsw = max(2, int(zw * zoom))
            zsh = max(2, int(zh * zoom))
            if zsx + zsw > 0 and zsx < sw and zsy + zsh > 0 and zsy < sh:
                pygame.draw.rect(farm_surf, (140, 180, 50, 50),
                                 (zsx, zsy, zsw, zsh))
                pygame.draw.rect(farm_surf, (100, 160, 40, 130),
                                 (zsx, zsy, zsw, zsh), 1)
    screen.blit(farm_surf, (0, 0))


def draw_overlay(screen, mode, plan, settlements, rivers, cam_x, cam_y, zoom,
                 sw, sh, ww, wh, x0, y0, x1, y1, font_sm, font_md,
                 compute_moisture_fn, whittaker_fn):
    """Dispatch overlay rendering by mode. Called from main viewer loop."""
    if mode in (1, 2, 3, 4):
        _draw_pixel_overlay(screen, mode, plan, rivers, cam_x, cam_y, zoom,
                            sw, sh, ww, wh, compute_moisture_fn, whittaker_fn)
    elif mode == 5:
        _draw_spine(screen, plan, cam_x, cam_y, zoom, sw, sh)
    elif mode == 6:
        _draw_settlements_overlay(screen, settlements, cam_x, cam_y, zoom,
                                  sw, sh, font_sm)
    elif mode == 7:
        _draw_kingdoms(screen, plan, cam_x, cam_y, zoom, sw, sh, ww, wh, font_md)
    elif mode == 8:
        _draw_chunk_grid(screen, cam_x, cam_y, zoom, sw, sh, ww, wh,
                         x0, y0, x1, y1, font_sm)
