#!/usr/bin/env python3
"""3D Scene Viewer — render game world tiles in 3D with software projection.

Loads a small area around the player from the actual game world and
renders it with perspective projection and painter's algorithm.

Controls:
  WASD: move player
  Left/Right arrows: rotate camera
  Up/Down arrows: tilt camera
  +/-: zoom
  [ / ]: change view radius
  P: print camera settings
  S: save screenshot
  Esc: quit
"""

import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from game.settings import *
from game.ui.scene_3d import build_scene


SCREEN_W, SCREEN_H = 1024, 768


# ── 3D projection helpers ───────────────────────────────────────────────

def _rotate_y(point, angle):
    x, y, z = point
    c, s = math.cos(angle), math.sin(angle)
    return (x * c + z * s, y, -x * s + z * c)

def _rotate_x(point, angle):
    x, y, z = point
    c, s = math.cos(angle), math.sin(angle)
    return (x, y * c - z * s, y * s + z * c)

def _transform(point, azimuth, elevation, cam_dist):
    p = _rotate_y(point, azimuth)
    p = _rotate_x(p, elevation)
    return (p[0], p[1], p[2] + cam_dist)

def _project(point, cam_dist, cx, cy, scale):
    x, y, z = point
    if z <= 0.1:
        z = 0.1
    f = cam_dist / z * scale
    return (int(cx + x * f), int(cy - y * f)), z


def render_scene(surface, faces, azimuth, elevation, cam_dist, scale):
    """Project and render all faces with back-face culling."""
    cx = surface.get_width() // 2
    cy = surface.get_height() // 2

    projected = []
    for verts_3d, color, skip_cull in faces:
        pts_2d = []
        avg_z = 0
        ok = True
        for v in verts_3d:
            tv = _transform(v, azimuth, elevation, cam_dist)
            sp, z = _project(tv, cam_dist, cx, cy, scale)
            pts_2d.append(sp)
            avg_z += z
            if z < 0.1:
                ok = False
        if not ok or len(pts_2d) < 3:
            continue
        avg_z /= len(verts_3d)

        if not skip_cull and len(pts_2d) >= 3:
            ax = pts_2d[1][0] - pts_2d[0][0]
            ay = pts_2d[1][1] - pts_2d[0][1]
            bx_c = pts_2d[2][0] - pts_2d[0][0]
            by_c = pts_2d[2][1] - pts_2d[0][1]
            cross = ax * by_c - ay * bx_c
            if abs(cross) < 2 or cross < 0:
                continue

        projected.append((pts_2d, color, avg_z))

    projected.sort(key=lambda f: -f[2])
    for pts, color, _ in projected:
        pygame.draw.polygon(surface, color, pts)
        ec = (max(0, color[0]-18), max(0, color[1]-16), max(0, color[2]-14))
        pygame.draw.polygon(surface, ec, pts, 1)


def draw_player_3d(surface, azimuth, elevation, cam_dist, scale):
    """Draw a simple player marker at the origin."""
    cx = surface.get_width() // 2
    cy = surface.get_height() // 2
    for h in [0.0, 0.2, 0.4, 0.6, 0.8]:
        tv = _transform((0.5, h + 0.1, 0.5), azimuth, elevation, cam_dist)
        sp, z = _project(tv, cam_dist, cx, cy, scale)
        if z > 0.1:
            size = max(2, int(4 * cam_dist / z))
            color = (220, 200, 60) if h < 0.6 else (200, 180, 50)
            pygame.draw.circle(surface, color, sp, size)
    tv = _transform((0.5, 1.0, 0.5), azimuth, elevation, cam_dist)
    sp, z = _project(tv, cam_dist, cx, cy, scale)
    if z > 0.1:
        pygame.draw.circle(surface, (230, 210, 70), sp, max(3, int(5 * cam_dist / z)))


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    print("Loading game world (this takes ~20 seconds)...")

    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    os.environ['SDL_AUDIODRIVER'] = 'dummy'
    pygame.init()
    pygame.display.set_mode((100, 100))

    from game.ui.screenshot import HeadlessGame
    g = HeadlessGame(seed=42, mode='god', spawn_location='test_island',
                     use_chunked=True)
    print(f"World loaded. Player at ({g.player.x:.0f}, {g.player.y:.0f})")

    pygame.quit()
    for key in ('SDL_VIDEODRIVER', 'SDL_AUDIODRIVER'):
        os.environ.pop(key, None)
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("3D World Scene Viewer")
    clock = pygame.time.Clock()

    azimuth = math.radians(15)
    elevation = math.radians(-30)
    cam_dist = 18.0
    scale = 55.0
    view_radius = 12
    player_x, player_y = g.player.x, g.player.y
    move_speed = 0.3

    plan = getattr(g.world, 'plan', None)
    scene_faces = build_scene(g.world, player_x, player_y, view_radius, plan)
    last_build_x, last_build_y = int(player_x), int(player_y)

    sky = pygame.Surface((SCREEN_W, SCREEN_H))
    for sy in range(SCREEN_H):
        t = sy / SCREEN_H
        pygame.draw.line(sky, (int(135+t*45), int(155+t*30), int(195-t*60)),
                         (0, sy), (SCREEN_W, sy))

    font = pygame.font.SysFont("monospace", 13)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT:
                    azimuth -= math.radians(5)
                elif event.key == pygame.K_RIGHT:
                    azimuth += math.radians(5)
                elif event.key == pygame.K_UP:
                    elevation = max(math.radians(-80), elevation - math.radians(5))
                elif event.key == pygame.K_DOWN:
                    elevation = min(math.radians(-10), elevation + math.radians(5))
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                    scale *= 1.15
                elif event.key == pygame.K_MINUS:
                    scale /= 1.15
                elif event.key == pygame.K_LEFTBRACKET:
                    view_radius = max(4, view_radius - 2)
                    last_build_x = -999
                elif event.key == pygame.K_RIGHTBRACKET:
                    view_radius = min(25, view_radius + 2)
                    last_build_x = -999
                elif event.key == pygame.K_p:
                    print(f"az={math.degrees(azimuth):.1f} el={math.degrees(elevation):.1f} "
                          f"dist={cam_dist:.1f} scale={scale:.1f} radius={view_radius}")
                elif event.key == pygame.K_s:
                    pygame.image.save(screen, "3d_scene_screenshot.png")
                    print("Saved screenshot")

        keys = pygame.key.get_pressed()
        if keys[pygame.K_w]:
            player_y -= move_speed
        if keys[pygame.K_s] and not keys[pygame.K_LCTRL]:
            player_y += move_speed
        if keys[pygame.K_a]:
            player_x -= move_speed
        if keys[pygame.K_d]:
            player_x += move_speed

        cur_ix, cur_iy = int(player_x), int(player_y)
        if cur_ix != last_build_x or cur_iy != last_build_y:
            scene_faces = build_scene(g.world, player_x, player_y, view_radius, plan)
            last_build_x, last_build_y = cur_ix, cur_iy

        screen.blit(sky, (0, 0))
        render_scene(screen, scene_faces, azimuth, elevation, cam_dist, scale)
        draw_player_3d(screen, azimuth, elevation, cam_dist, scale)

        fps = clock.get_fps()
        info = [
            f"FPS: {fps:.0f}  Faces: {len(scene_faces)}  Radius: {view_radius}",
            f"Pos: ({player_x:.0f}, {player_y:.0f})  Az: {math.degrees(azimuth):.0f}",
            "WASD:move  Arrows:camera  [/]:radius  +/-:zoom",
        ]
        for i, txt in enumerate(info):
            screen.blit(font.render(txt, True, (240, 240, 250)), (5, 5 + i * 15))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
