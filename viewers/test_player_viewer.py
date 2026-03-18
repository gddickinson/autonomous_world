#!/usr/bin/env python3
"""Player Character Viewer — mortal/ghost/god modes in all view types.

Uses the same draw_player_body() as the game, shown at multiple scales.

Controls:
  LEFT/RIGHT: cycle player mode (mortal / ghost / god)
  UP/DOWN: cycle view scale
  SPACE: toggle attack animation
  W: toggle walking
  1-4: facing direction
  S: screenshot
  Esc: quit
"""

import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 1000, 700
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Player Character Viewer — All Modes & Views")
clock = pygame.time.Clock()
font = pygame.font.SysFont("monospace", 13)
font_lg = pygame.font.SysFont("monospace", 18, bold=True)

from game.settings import PLAYER_ATTACK_COOLDOWN
from game.ui.player_anim import draw_player_body


# ── Mock player ──────────────────────────────────────────────────────────

class MockPlayer:
    def __init__(self, mode="mortal"):
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.mode = mode
        self.alive = True
        self.facing = (0, 1)
        self.attack_timer = 0.0
        self.current_floor = 0
        self._current_building_rect = None
        self._anim = None
        self._last_dt = 0.016


PLAYER_MODES = ["mortal", "ghost", "god"]
VIEW_SCALES = [
    ("Strategy (16px)", 4),    # TILE_SIZE//4
    ("Adventure (32px)", 8),
    ("Detail (64px)", 16),
]


def main():
    mode_idx = 0
    view_idx = 0
    attacking = False
    walking = False
    attack_time = 0.0
    walk_time = 0.0
    # Persistent player objects (one per mode) so anim state persists
    players = {mode: MockPlayer(mode) for mode in PLAYER_MODES}
    # Grid players: [mode][view_idx]
    grid_players = {mode: [MockPlayer(mode) for _ in VIEW_SCALES]
                    for mode in PLAYER_MODES}

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT:
                    mode_idx = (mode_idx - 1) % len(PLAYER_MODES)
                elif event.key == pygame.K_RIGHT:
                    mode_idx = (mode_idx + 1) % len(PLAYER_MODES)
                elif event.key == pygame.K_UP:
                    view_idx = (view_idx - 1) % len(VIEW_SCALES)
                elif event.key == pygame.K_DOWN:
                    view_idx = (view_idx + 1) % len(VIEW_SCALES)
                elif event.key == pygame.K_SPACE:
                    attacking = not attacking
                elif event.key == pygame.K_w:
                    walking = not walking
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    dirs = {pygame.K_1: (-1, 0), pygame.K_2: (1, 0),
                            pygame.K_3: (0, -1), pygame.K_4: (0, 1)}
                    # Will be applied to each mock player below
                elif event.key == pygame.K_s:
                    pygame.image.save(screen, "screenshot_player_viewer.png")

        if attacking:
            attack_time += dt * 3
            if attack_time > 1.0:
                attack_time -= 1.0

        if walking:
            walk_time += dt

        # ── Render ──────────────────────────────────────────────────
        screen.fill((30, 30, 40))
        _draw_grid(screen)

        view_name, scale = VIEW_SCALES[view_idx]
        current_mode = PLAYER_MODES[mode_idx]

        # Get facing from last keypress
        keys = pygame.key.get_pressed()
        facing = (0, 1)
        if keys[pygame.K_1]: facing = (-1, 0)
        elif keys[pygame.K_2]: facing = (1, 0)
        elif keys[pygame.K_3]: facing = (0, -1)
        elif keys[pygame.K_4]: facing = (0, 1)

        # Title
        title = font_lg.render(
            f"Player: {current_mode.upper()} | {view_name}", True, (255, 255, 255))
        screen.blit(title, (20, 20))

        # Large centered player (persistent object)
        cx, cy = SCREEN_W // 2, SCREEN_H // 3
        player = players[current_mode]
        player.facing = facing
        player.attack_timer = attack_time * PLAYER_ATTACK_COOLDOWN if attacking else 0
        player._last_dt = dt
        if walking:
            player.x = math.sin(walk_time * 2) * 0.3
            player.y = math.cos(walk_time * 2) * 0.3
        else:
            player.x = player.y = 0.0
        draw_player_body(screen, player, cx, cy, scale)

        # ── Comparison panel: all modes × all views ─────────────────
        panel_y = SCREEN_H // 2 + 20
        _draw_panel_bg(screen, 0, panel_y - 10, SCREEN_W, SCREEN_H - panel_y + 10)

        header = font.render("All modes x all views:", True, (180, 180, 200))
        screen.blit(header, (20, panel_y))

        for mi, mode in enumerate(PLAYER_MODES):
            row_y = panel_y + 25 + mi * 80
            mode_label = font.render(mode.upper(), True, (200, 200, 220))
            screen.blit(mode_label, (20, row_y + 15))

            for vi, (vname, vs) in enumerate(VIEW_SCALES):
                col_x = 160 + vi * 260
                p = grid_players[mode][vi]
                p.facing = facing
                p.attack_timer = attack_time * PLAYER_ATTACK_COOLDOWN if attacking else 0
                p._last_dt = dt
                if walking:
                    p.x = math.sin(walk_time * 2 + vi * 0.5) * 0.3
                    p.y = math.cos(walk_time * 2 + vi * 0.5) * 0.3
                else:
                    p.x = p.y = 0.0
                draw_player_body(screen, p, col_x, row_y + 30, vs)

                if mi == 0:
                    screen.blit(font.render(vname, True, (140, 140, 160)),
                                (col_x - len(vname) * 4, panel_y + 10))

        # Controls
        info = [
            f"Walking: {'ON' if walking else 'OFF'} | "
            f"Attack: {'ON' if attacking else 'OFF'}",
        ]
        for i, line in enumerate(info):
            screen.blit(font.render(line, True, (160, 160, 180)), (20, 48 + i * 16))

        controls = [
            "LEFT/RIGHT: mode", "UP/DOWN: view", "SPACE: attack",
            "W: walk", "1-4: facing", "S: screenshot",
        ]
        for i, c in enumerate(controls):
            screen.blit(font.render(c, True, (110, 110, 130)),
                        (SCREEN_W - 200, 20 + i * 16))

        pygame.display.flip()

    pygame.quit()


def _draw_grid(screen):
    for x in range(0, SCREEN_W, 20):
        pygame.draw.line(screen, (40, 40, 50), (x, 0), (x, SCREEN_H))
    for y in range(0, SCREEN_H, 20):
        pygame.draw.line(screen, (40, 40, 50), (0, y), (SCREEN_W, y))


def _draw_panel_bg(screen, x, y, w, h):
    pygame.draw.rect(screen, (25, 25, 35), (x, y, w, h))
    pygame.draw.line(screen, (50, 50, 60), (x, y), (x + w, y))


if __name__ == "__main__":
    main()
