#!/usr/bin/env python3
"""3D Scene Renderer — OpenGL version for 60fps at large radii.

Same geometry as test_3d_scene.py but uses PyOpenGL for hardware-
accelerated rendering. Should handle radius 25+ at 60fps easily.

Controls: same as test_3d_scene.py
  WASD: move, Arrows: camera, [/]: radius, +/-: zoom
  P: print, S: screenshot, Esc: quit
"""

import os
import sys
import math

os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from pygame.locals import *

# OpenGL imports
from OpenGL.GL import *
from OpenGL.GLU import *

SCREEN_W, SCREEN_H = 1024, 768


def main():
    print("Loading game world (this takes ~20 seconds)...")

    # Load world data with dummy display
    os.environ['SDL_VIDEODRIVER'] = 'dummy'
    pygame.init()
    pygame.display.set_mode((100, 100))

    from game.ui.screenshot import HeadlessGame
    g = HeadlessGame(seed=42, mode='god', spawn_location='test_island',
                     use_chunked=True)

    print(f"World loaded. Player at ({g.player.x:.0f}, {g.player.y:.0f})")

    # Switch to real OpenGL display
    pygame.quit()
    if 'SDL_VIDEODRIVER' in os.environ:
        del os.environ['SDL_VIDEODRIVER']
    if 'SDL_AUDIODRIVER' in os.environ:
        del os.environ['SDL_AUDIODRIVER']
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H),
                                      DOUBLEBUF | OPENGL)
    pygame.display.set_caption("3D World — OpenGL")
    clock = pygame.time.Clock()

    # OpenGL setup
    glEnable(GL_DEPTH_TEST)
    # No face culling — vertex winding is inconsistent across different
    # face types. Depth buffer handles occlusion correctly without it.
    glDisable(GL_CULL_FACE)
    glClearColor(0.53, 0.61, 0.76, 1.0)  # sky blue

    # Import scene builder from game module
    from game.ui.scene_3d import build_scene

    # Camera
    azimuth = 15.0    # degrees
    elevation = -30.0
    cam_dist = 18.0
    view_radius = 20

    player_x = g.player.x
    player_y = g.player.y
    move_speed = 0.3

    plan = getattr(g.world, 'plan', None)
    scene_faces = build_scene(g.world, player_x, player_y, view_radius, plan)
    last_build_x, last_build_y = int(player_x), int(player_y)
    gl_list = _compile_scene(scene_faces)

    font = pygame.font.SysFont("monospace", 14)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            if event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    running = False
                elif event.key == K_LEFT:
                    azimuth -= 5
                elif event.key == K_RIGHT:
                    azimuth += 5
                elif event.key == K_UP:
                    elevation = max(-80, elevation - 5)
                elif event.key == K_DOWN:
                    elevation = min(-10, elevation + 5)
                elif event.key in (K_EQUALS, K_PLUS):
                    cam_dist = max(5, cam_dist - 2)
                elif event.key == K_MINUS:
                    cam_dist += 2
                elif event.key == K_LEFTBRACKET:
                    view_radius = max(4, view_radius - 2)
                    last_build_x = -999
                elif event.key == K_RIGHTBRACKET:
                    view_radius = min(40, view_radius + 2)
                    last_build_x = -999
                elif event.key == K_p:
                    print(f"az={azimuth:.1f} el={elevation:.1f} "
                          f"dist={cam_dist:.1f} radius={view_radius}")
                elif event.key == K_s:
                    _save_screenshot("exports/screenshots/3d_opengl.png")
                    print("Saved 3d_opengl.png")

        # Movement
        keys = pygame.key.get_pressed()
        if keys[K_w]:
            player_y -= move_speed
        if keys[K_s] and not keys[K_LCTRL]:
            player_y += move_speed
        if keys[K_a]:
            player_x -= move_speed
        if keys[K_d]:
            player_x += move_speed

        # Rebuild scene when player crosses a tile boundary
        cur_ix, cur_iy = int(player_x), int(player_y)
        if cur_ix != last_build_x or cur_iy != last_build_y:
            scene_faces = build_scene(g.world, player_x, player_y,
                                       view_radius, plan)
            last_build_x, last_build_y = cur_ix, cur_iy
            # Recompile display list
            if gl_list:
                glDeleteLists(gl_list, 1)
            gl_list = _compile_scene(scene_faces)

        # --- RENDER ---
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Set up perspective projection
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, SCREEN_W / SCREEN_H, 0.1, 200.0)

        # Camera
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Convert spherical camera to look-at
        az_rad = math.radians(azimuth)
        el_rad = math.radians(elevation)
        cam_x = cam_dist * math.sin(az_rad) * math.cos(el_rad)
        cam_y = cam_dist * -math.sin(el_rad)
        cam_z = cam_dist * math.cos(az_rad) * math.cos(el_rad)

        # Player is always at world origin (scene centered on player)
        gluLookAt(cam_x, cam_y, cam_z,  # camera position
                  0.5, 0.0, 0.5,        # look at center
                  0.0, 1.0, 0.0)         # up vector

        # Draw scene from display list
        if gl_list:
            glCallList(gl_list)

        # Draw player marker
        _draw_player_gl()

        # HUD overlay (switch to 2D for text)
        _draw_hud(screen, clock, view_radius, player_x, player_y,
                  azimuth, elevation, len(scene_faces), font)

        pygame.display.flip()
        clock.tick(60)

    if gl_list:
        glDeleteLists(gl_list, 1)
    pygame.quit()


def _compile_scene(faces):
    """Compile scene faces into an OpenGL display list for fast rendering."""
    dl = glGenLists(1)
    glNewList(dl, GL_COMPILE)

    glBegin(GL_TRIANGLES)
    for face_data in faces:
        verts, color, skip_cull = face_data
        r, g, b = color[0] / 255.0, color[1] / 255.0, color[2] / 255.0
        glColor3f(r, g, b)

        # Triangulate polygon (fan from first vertex)
        # Draw both windings to ensure visibility regardless of face direction
        if len(verts) >= 3:
            for i in range(1, len(verts) - 1):
                v0 = verts[0]
                v1 = verts[i]
                v2 = verts[i + 1]
                # Front face (CCW)
                glVertex3f(v0[0], v0[1], v0[2])
                glVertex3f(v1[0], v1[1], v1[2])
                glVertex3f(v2[0], v2[1], v2[2])
                # Back face (CW) — ensures visible from both sides
                glVertex3f(v0[0], v0[1], v0[2])
                glVertex3f(v2[0], v2[1], v2[2])
                glVertex3f(v1[0], v1[1], v1[2])
    glEnd()

    glEndList()
    return dl


def _draw_player_gl():
    """Draw a simple player marker at the origin."""
    glDisable(GL_CULL_FACE)

    # Yellow diamond
    glBegin(GL_TRIANGLES)
    glColor3f(0.9, 0.82, 0.25)
    size = 0.3
    cx, cy, cz = 0.5, 0.5, 0.5
    # 4 triangular faces of a diamond
    glVertex3f(cx, cy + size * 2, cz)
    glVertex3f(cx - size, cy, cz - size)
    glVertex3f(cx + size, cy, cz - size)

    glVertex3f(cx, cy + size * 2, cz)
    glVertex3f(cx + size, cy, cz - size)
    glVertex3f(cx + size, cy, cz + size)

    glVertex3f(cx, cy + size * 2, cz)
    glVertex3f(cx + size, cy, cz + size)
    glVertex3f(cx - size, cy, cz + size)

    glVertex3f(cx, cy + size * 2, cz)
    glVertex3f(cx - size, cy, cz + size)
    glVertex3f(cx - size, cy, cz - size)

    # Bottom half (darker)
    glColor3f(0.7, 0.65, 0.2)
    glVertex3f(cx, cy - size, cz)
    glVertex3f(cx + size, cy, cz - size)
    glVertex3f(cx - size, cy, cz - size)

    glVertex3f(cx, cy - size, cz)
    glVertex3f(cx + size, cy, cz + size)
    glVertex3f(cx + size, cy, cz - size)

    glVertex3f(cx, cy - size, cz)
    glVertex3f(cx - size, cy, cz + size)
    glVertex3f(cx + size, cy, cz + size)

    glVertex3f(cx, cy - size, cz)
    glVertex3f(cx - size, cy, cz - size)
    glVertex3f(cx - size, cy, cz + size)
    glEnd()

    glEnable(GL_CULL_FACE)


def _draw_hud(screen, clock, radius, px, py, az, el, face_count, font):
    """Draw 2D HUD text overlay on the OpenGL scene."""
    fps = clock.get_fps()
    lines = [
        f"FPS: {fps:.0f}  Faces: {face_count}  Radius: {radius}",
        f"Pos: ({px:.0f}, {py:.0f})  Az: {az:.0f}  El: {el:.0f}",
        "WASD:move  Arrows:cam  [/]:radius  +/-:zoom  S:save",
    ]

    # Render text to pygame surface
    hud_h = len(lines) * 18 + 8
    hud_w = 500
    hud_surf = pygame.Surface((hud_w, hud_h), pygame.SRCALPHA)
    hud_surf.fill((0, 0, 0, 140))
    for i, txt in enumerate(lines):
        rendered = font.render(txt, True, (240, 240, 250))
        hud_surf.blit(rendered, (5, 4 + i * 18))

    # Convert pygame surface to OpenGL texture and draw as 2D overlay
    tex_data = pygame.image.tostring(hud_surf, "RGBA", True)
    tex_w, tex_h = hud_surf.get_size()

    # Switch to 2D orthographic projection
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, SCREEN_W, 0, SCREEN_H, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_DEPTH_TEST)

    # Create and bind texture
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    tex_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tex_w, tex_h, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, tex_data)

    # Draw textured quad in top-left corner
    glColor3f(1, 1, 1)
    glBegin(GL_QUADS)
    y_pos = SCREEN_H - tex_h  # top of screen (OpenGL Y is flipped)
    glTexCoord2f(0, 0); glVertex2f(0, y_pos)
    glTexCoord2f(1, 0); glVertex2f(tex_w, y_pos)
    glTexCoord2f(1, 1); glVertex2f(tex_w, y_pos + tex_h)
    glTexCoord2f(0, 1); glVertex2f(0, y_pos + tex_h)
    glEnd()

    # Cleanup
    glDeleteTextures([tex_id])
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()


def _save_screenshot(path):
    """Save OpenGL framebuffer as image."""
    import numpy as np
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = glReadPixels(0, 0, SCREEN_W, SCREEN_H, GL_RGB, GL_UNSIGNED_BYTE)
    arr = np.frombuffer(data, dtype=np.uint8).reshape(SCREEN_H, SCREEN_W, 3)
    arr = np.flipud(arr)  # OpenGL y-axis is flipped
    surf = pygame.surfarray.make_surface(arr.swapaxes(0, 1))
    pygame.image.save(surf, path)


if __name__ == "__main__":
    main()
