"""Shared OpenGL viewer utilities — camera, HUD, geometry helpers.

Used by all 3D test viewers to avoid duplicating boilerplate.
"""

import math
import pygame
from pygame.locals import DOUBLEBUF, OPENGL
from OpenGL.GL import *
from OpenGL.GLU import *


def init_viewer(title, width=1000, height=750):
    """Initialize pygame + OpenGL window. Returns (screen, clock, font)."""
    pygame.init()
    screen = pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
    pygame.display.set_caption(title)
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("monospace", 13)

    glEnable(GL_DEPTH_TEST)
    glDisable(GL_CULL_FACE)
    glClearColor(0.35, 0.4, 0.5, 1.0)
    return screen, clock, font, width, height


def setup_camera(width, height, azimuth, elevation, cam_dist,
                 look_x=0.0, look_y=0.5, look_z=0.0):
    """Set up perspective camera for a frame."""
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45, width / height, 0.1, 200.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    az_rad = math.radians(azimuth)
    el_rad = math.radians(elevation)
    cam_x = look_x + cam_dist * math.sin(az_rad) * math.cos(el_rad)
    cam_y = cam_dist * -math.sin(el_rad)
    cam_z = look_z + cam_dist * math.cos(az_rad) * math.cos(el_rad)
    gluLookAt(cam_x, cam_y, cam_z, look_x, look_y, look_z, 0.0, 1.0, 0.0)


def draw_hud(lines, font, width, height):
    """Draw text overlay on 3D scene with dark background."""
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, width, height, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    line_h = 16
    max_w = max((font.size(l)[0] for l in lines), default=100) + 12
    hud_h = len(lines) * line_h + 8
    hud_surf = pygame.Surface((max_w, hud_h), pygame.SRCALPHA)
    hud_surf.fill((15, 15, 25, 200))
    for i, line in enumerate(lines):
        text = font.render(line, True, (240, 240, 255))
        hud_surf.blit(text, (6, 4 + i * line_h))

    data = pygame.image.tostring(hud_surf, "RGBA", True)
    glRasterPos2i(8, 8 + hud_h)
    glDrawPixels(max_w, hud_h, GL_RGBA, GL_UNSIGNED_BYTE, data)

    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()


def draw_ground_grid(size=5, y=0.0):
    """Draw a flat ground grid for reference."""
    glBegin(GL_QUADS)
    glColor3f(0.3, 0.38, 0.28)
    glVertex3f(-size, y, -size)
    glVertex3f(size, y, -size)
    glVertex3f(size, y, size)
    glVertex3f(-size, y, size)
    glEnd()
    # Grid lines
    glBegin(GL_LINES)
    glColor3f(0.25, 0.32, 0.22)
    for i in range(-size, size + 1):
        glVertex3f(i, y + 0.005, -size)
        glVertex3f(i, y + 0.005, size)
        glVertex3f(-size, y + 0.005, i)
        glVertex3f(size, y + 0.005, i)
    glEnd()


def gl_color(rgb):
    glColor3f(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def draw_box(x, y, z, w, h, d, color, shade=0.8):
    """Draw a solid box with directional shading."""
    x2, y2, z2 = x + w, y + h, z + d
    r, g, b = color[0] / 255.0, color[1] / 255.0, color[2] / 255.0
    # Top (bright)
    glColor3f(r, g, b)
    glVertex3f(x, y2, z); glVertex3f(x2, y2, z)
    glVertex3f(x2, y2, z2); glVertex3f(x, y2, z2)
    # South (lit)
    glColor3f(r * 0.95, g * 0.95, b * 0.95)
    glVertex3f(x, y, z2); glVertex3f(x2, y, z2)
    glVertex3f(x2, y2, z2); glVertex3f(x, y2, z2)
    # North (dark)
    s = shade
    glColor3f(r * s * 0.8, g * s * 0.8, b * s * 0.8)
    glVertex3f(x2, y, z); glVertex3f(x, y, z)
    glVertex3f(x, y2, z); glVertex3f(x2, y2, z)
    # East
    glColor3f(r * s, g * s, b * s)
    glVertex3f(x2, y, z2); glVertex3f(x2, y, z)
    glVertex3f(x2, y2, z); glVertex3f(x2, y2, z2)
    # West
    glColor3f(r * s * 0.85, g * s * 0.85, b * s * 0.85)
    glVertex3f(x, y, z); glVertex3f(x, y, z2)
    glVertex3f(x, y2, z2); glVertex3f(x, y2, z)


def draw_sphere_approx(cx, cy, cz, radius, color, segments=8):
    """Draw an approximate sphere using triangle fan slices."""
    r, g, b = color[0] / 255.0, color[1] / 255.0, color[2] / 255.0
    for i in range(segments):
        lat0 = math.pi * (-0.5 + i / segments)
        lat1 = math.pi * (-0.5 + (i + 1) / segments)
        for j in range(segments):
            lon0 = 2 * math.pi * j / segments
            lon1 = 2 * math.pi * (j + 1) / segments
            # Shade based on latitude (top brighter)
            shade = 0.7 + 0.3 * (math.sin(lat0) + 1) / 2
            glColor3f(r * shade, g * shade, b * shade)

            x0 = cx + radius * math.cos(lat0) * math.cos(lon0)
            y0 = cy + radius * math.sin(lat0)
            z0 = cz + radius * math.cos(lat0) * math.sin(lon0)
            x1 = cx + radius * math.cos(lat0) * math.cos(lon1)
            y1 = cy + radius * math.sin(lat0)
            z1 = cz + radius * math.cos(lat0) * math.sin(lon1)
            x2 = cx + radius * math.cos(lat1) * math.cos(lon1)
            y2 = cy + radius * math.sin(lat1)
            z2 = cz + radius * math.cos(lat1) * math.sin(lon1)
            x3 = cx + radius * math.cos(lat1) * math.cos(lon0)
            y3 = cy + radius * math.sin(lat1)
            z3 = cz + radius * math.cos(lat1) * math.sin(lon0)

            glVertex3f(x0, y0, z0); glVertex3f(x1, y1, z1); glVertex3f(x2, y2, z2)
            glVertex3f(x0, y0, z0); glVertex3f(x2, y2, z2); glVertex3f(x3, y3, z3)


def handle_camera_keys(event, azimuth, elevation, cam_dist):
    """Handle camera keys (SHIFT+arrows for rotation). Returns (az, el, dist)."""
    mods = pygame.key.get_mods()
    shift = mods & pygame.KMOD_SHIFT
    if event.key == pygame.K_LEFT and shift:
        azimuth -= 10
    elif event.key == pygame.K_RIGHT and shift:
        azimuth += 10
    elif event.key == pygame.K_UP and shift:
        elevation = max(-80, elevation - 5)
    elif event.key == pygame.K_DOWN and shift:
        elevation = min(-10, elevation + 5)
    elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
        cam_dist = max(2, cam_dist - 1)
    elif event.key == pygame.K_MINUS:
        cam_dist = min(30, cam_dist + 1)
    return azimuth, elevation, cam_dist
