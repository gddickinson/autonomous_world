#!/usr/bin/env python3
"""Settlement Survey — automated screenshot capture at multiple zoom levels.

Generates the world headlessly (HeadlessGame, seed=42, god mode, chunked),
then renders views centered on each of the first 10 settlements at zoom
levels 1.0, 3.0, and 6.0, plus a full-world overview at zoom 0.08.

Saves screenshots to viewers/survey_output/.

Usage:
    python -m viewers.settlement_survey
"""

import os
import sys
import time

# Project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Force headless rendering
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 1600, 1000

screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
font_sm = pygame.font.SysFont("monospace", 11)
font_md = pygame.font.SysFont("monospace", 14, bold=True)

OUTPUT_DIR = os.path.join(ROOT, "viewers", "survey_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Generate world ──────────────────────────────────────────────────

print("Generating world (seed=42, chunked)...")
t0 = time.time()

from game.ui.screenshot import HeadlessGame

g = HeadlessGame(seed=42, mode='god', spawn_location='test_island',
                 use_chunked=True)

gen_time = time.time() - t0
print(f"World generated in {gen_time:.1f}s")

ww = getattr(g.world.plan, 'world_width', 10000)
wh = getattr(g.world.plan, 'world_height', 10000)
settlements = g.world.plan.settlements
rivers = g.world.plan.rivers
roads = g.world.plan.roads

print(f"  {len(settlements)} settlements, {len(rivers)} rivers, "
      f"{len(roads)} roads")

# ── Import renderer ─────────────────────────────────────────────────

from viewers.survey_renderer import render_view

# ── Sanitize filenames ──────────────────────────────────────────────


def _safe_name(name):
    """Convert settlement name to safe filename component."""
    return "".join(c if c.isalnum() else "_" for c in name).strip("_")


# ── Render and save ─────────────────────────────────────────────────


def capture_view(cam_x, cam_y, zoom, filename):
    """Render a view and save it as a PNG."""
    render_view(screen, g, cam_x, cam_y, zoom, SCREEN_W, SCREEN_H,
                ww, wh, settlements, rivers, roads, font_sm)
    # Add info label
    info = font_md.render(
        f"cam=({int(cam_x)},{int(cam_y)}) zoom={zoom:.2f}  "
        f"{os.path.basename(filename)}",
        True, (255, 255, 255))
    screen.blit(info, (10, SCREEN_H - 22))
    path = os.path.join(OUTPUT_DIR, filename)
    pygame.image.save(screen, path)
    return path


# ── Full world overview ─────────────────────────────────────────────

print("\nRendering full-world overview at zoom 0.08...")
p = capture_view(ww / 2, wh / 2, 0.08, "survey_OVERVIEW_zoom_0.08.png")
print(f"  Saved: {p}")

# ── Settlement views ────────────────────────────────────────────────

MAX_SETTLEMENTS = min(10, len(settlements))
ZOOM_LEVELS = [1.0, 3.0, 6.0]

for i, sp in enumerate(settlements[:MAX_SETTLEMENTS]):
    safe = _safe_name(sp.name)
    print(f"\n[{i+1}/{MAX_SETTLEMENTS}] {sp.name} ({sp.kind}) "
          f"at ({sp.x}, {sp.y}), pop={sp.population}, "
          f"radius={sp.radius}")
    for z in ZOOM_LEVELS:
        fname = f"survey_{safe}_zoom_{z:.1f}.png"
        p = capture_view(float(sp.x), float(sp.y), z, fname)
        print(f"  zoom {z:.1f} -> {p}")

# ── Summary ─────────────────────────────────────────────────────────

total = 1 + MAX_SETTLEMENTS * len(ZOOM_LEVELS)
print(f"\nDone! {total} screenshots saved to {OUTPUT_DIR}")

pygame.quit()
