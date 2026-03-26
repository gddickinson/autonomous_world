#!/usr/bin/env python3
"""3D Creature Viewer — all creature types with per-type 3D templates.

Controls:
  LEFT/RIGHT: cycle creature
  TAB: filter (all / hostile / passive)
  SHIFT+Arrows: camera    +/-: zoom
  SPACE: toggle walk    D: die (flatten)
  S: screenshot    Esc: quit
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from OpenGL.GL import *

from viewers.gl_viewer_base import (
    init_viewer, setup_camera, draw_hud, draw_ground_grid,
    draw_box, handle_camera_keys,
)
from viewers.creature_3d_templates import (
    draw_quadruped_3d, draw_ungulate_3d, draw_bear_3d,
    draw_humanoid_3d, draw_large_3d, draw_winged_3d, draw_ethereal_3d,
    draw_arachnid_3d, draw_bird_3d, draw_serpent_3d,
)
from viewers.creature_3d_templates_extra import (
    draw_small_3d, draw_reptile_3d, draw_aquatic_3d,
)
from game.data.dnd import MONSTERS
from game.ui.creatures.configs import CREATURE_CONFIGS

# Build creature list sorted by CR
CREATURES = sorted(
    [(k, v.get("color", (150, 150, 150)), v.get("cr", 0.25),
      v.get("hp", 10), v.get("passive", False))
     for k, v in MONSTERS.items()],
    key=lambda x: x[2]
)

FILTERS = ["all", "hostile", "passive"]

_3D_TEMPLATES = {
    "quadruped": draw_quadruped_3d,
    "ungulate": draw_ungulate_3d,
    "bear": draw_bear_3d,
    "humanoid": draw_humanoid_3d,
    "large": draw_large_3d,
    "winged": draw_winged_3d,
    "ethereal": draw_ethereal_3d,
    "arachnid": draw_arachnid_3d,
    "bird": draw_bird_3d,
    "serpent": draw_serpent_3d,
    "small": draw_small_3d,
    "reptile": draw_reptile_3d,
    "aquatic": draw_aquatic_3d,
}


def _draw_creature_3d(kind, color, cr, walk_phase, dead):
    """Draw creature using config-driven 3D template."""
    sc = 1.0 + min(1.5, cr * 0.3)
    ws = math.sin(walk_phase) if not dead else 0
    bob = abs(math.cos(walk_phase)) * 0.02 * sc if not dead else 0

    if dead:
        glBegin(GL_QUADS)
        draw_box(-0.3 * sc, 0, -0.15 * sc, 0.6 * sc, 0.05, 0.3 * sc, color)
        glEnd()
        return

    cfg = CREATURE_CONFIGS.get(kind, {})
    template = cfg.get("t", "quadruped")
    func = _3D_TEMPLATES.get(template)

    if func:
        func(sc, color, ws, bob, cfg)
    else:
        # Fallback
        glBegin(GL_QUADS)
        draw_box(-0.2 * sc, 0.1 * sc + bob, -0.1 * sc,
                 0.4 * sc, 0.2 * sc, 0.2 * sc, color)
        glEnd()


def main():
    screen, clock, font, W, H = init_viewer("3D Creature Viewer")
    idx = 0
    filt = 0
    az, el, dist = 30.0, -25.0, 5.0
    walking = False
    dead = False
    walk_phase = 0.0

    def filtered():
        f = FILTERS[filt]
        if f == "all": return CREATURES
        elif f == "hostile": return [c for c in CREATURES if not c[4]]
        return [c for c in CREATURES if c[4]]

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    lst = filtered()
                    idx = (idx - 1) % max(1, len(lst))
                    dead = False
                elif event.key == pygame.K_RIGHT and not (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    lst = filtered()
                    idx = (idx + 1) % max(1, len(lst))
                    dead = False
                elif event.key == pygame.K_TAB:
                    filt = (filt + 1) % len(FILTERS)
                    idx = 0; dead = False
                elif event.key == pygame.K_SPACE:
                    walking = not walking
                elif event.key == pygame.K_d:
                    dead = not dead
                elif event.key == pygame.K_s:
                    d = glReadPixels(0, 0, W, H, GL_RGB, GL_UNSIGNED_BYTE)
                    pygame.image.save(pygame.image.fromstring(bytes(d), (W, H), "RGB", True),
                                      "screenshot_creature_3d.png")
                else:
                    az, el, dist = handle_camera_keys(event, az, el, dist)

        if walking:
            walk_phase += dt * 6.0

        lst = filtered()
        if not lst:
            lst = CREATURES; idx = 0

        setup_camera(W, H, az, el, dist)
        draw_ground_grid(3)

        kind, color, cr, hp, passive = lst[idx % len(lst)]
        _draw_creature_3d(kind, color, cr, walk_phase if walking else 0, dead)

        cfg = CREATURE_CONFIGS.get(kind, {})
        tag = "PASSIVE" if passive else "HOSTILE"
        draw_hud([
            f"{kind} (CR {cr}) [{tag}] HP:{hp} — {cfg.get('t', '?')}",
            f"Filter: {FILTERS[filt]} ({len(lst)}) | [{idx+1}/{len(lst)}]",
            f"LEFT/RIGHT: cycle  TAB: filter  SPACE: walk  D: die",
            f"SHIFT+Arrows: camera  +/-: zoom  S: screenshot",
        ], font, W, H)

        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
