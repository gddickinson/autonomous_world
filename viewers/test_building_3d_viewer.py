#!/usr/bin/env python3
"""Building 3D OpenGL Viewer — renders actual blueprints as 3D geometry.

Stamps real game blueprints and renders them with the same OpenGL pipeline
as the in-game 3D view: wall cubes, pitched roofs, interior furniture.

Controls:
  LEFT/RIGHT: cycle building blueprint
  UP/DOWN: change floor count (1-3)
  Arrow keys (with SHIFT): rotate camera (azimuth/elevation)
  +/-: zoom in/out
  R: rotate blueprint 90 degrees
  T: cycle roof style
  S: screenshot
  Esc: quit
"""

import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
from pygame.locals import DOUBLEBUF, OPENGL

pygame.init()

SCREEN_W, SCREEN_H = 1000, 750
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H), DOUBLEBUF | OPENGL)
pygame.display.set_caption("Building 3D OpenGL Viewer — Actual Blueprints")
clock = pygame.time.Clock()

from OpenGL.GL import *
from OpenGL.GLU import *

from game.settings import *
from game.world.buildings import ALL_BLUEPRINTS

# ── 3D Colors (from scene_3d.py) ────────────────────────────────────────

TILE_3D_COLORS = {
    WATER: (45, 100, 170), SAND: (195, 180, 140), GRASS: (75, 135, 65),
    FOREST: (45, 100, 40), MOUNTAIN: (130, 115, 95), SNOW: (225, 230, 235),
    ROAD: (155, 135, 100), FLOOR: (150, 125, 90), WALL: (120, 110, 95),
    DOOR: (100, 70, 40), TABLE: (120, 90, 50), BED: (140, 80, 60),
    CHEST: (160, 130, 50), STAIRS_UP: (140, 130, 120), STAIRS_DOWN: (100, 90, 85),
    WINDOW: (140, 170, 200), FIREPLACE: (180, 80, 30), THRONE: (170, 140, 50),
    BOOKSHELF: (100, 75, 45), BARREL: (130, 100, 55), ANVIL: (100, 100, 110),
    FORGE_FIRE: (220, 120, 30), FOUNTAIN: (70, 140, 200), CARPET: (140, 50, 50),
    MOSAIC: (160, 140, 100), ARCHWAY: (140, 125, 105), PILLAR: (160, 155, 145),
    ALTAR: (180, 170, 140), LOCKED_DOOR: (90, 60, 35), STABLE_FLOOR: (140, 115, 75),
}

WALL_COLORS = {
    'S': (150, 135, 115), 'E': (120, 110, 95),
    'N': (90, 82, 72), 'W': (105, 96, 83),
}

ROOF_COLORS = {
    "hamlet": (155, 120, 55), "village": (165, 80, 42), "town": (100, 75, 50),
    "city": (88, 92, 105), "castle": (72, 74, 82), "temple": (130, 145, 58),
    "tavern": (145, 85, 45), "blacksmith": (60, 58, 55), "market": (160, 100, 50),
}

_TILE_ROOF_KIND = {
    "tavern": "tavern", "shop": "market", "temple": "temple",
    "military": "castle", "castle": "castle", "civic": "town",
}


def _gl_color(rgb):
    glColor3f(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


def _quad(v0, v1, v2, v3, color):
    """Draw a quad as two triangles."""
    _gl_color(color)
    glVertex3f(*v0); glVertex3f(*v1); glVertex3f(*v2)
    glVertex3f(*v0); glVertex3f(*v2); glVertex3f(*v3)
    # Reverse winding for visibility from both sides
    glVertex3f(*v0); glVertex3f(*v2); glVertex3f(*v1)
    glVertex3f(*v0); glVertex3f(*v3); glVertex3f(*v2)


# ── Build 3D geometry from blueprint ────────────────────────────────────

def build_building_faces(bp, num_floors, roof_kind, show_roof=True):
    """Generate 3D face geometry from a blueprint."""
    wall_h = 1.2 * num_floors  # height per floor in world units

    # Determine which tiles are building tiles
    building_tiles = set()
    for by, row in enumerate(bp.tiles):
        for bx, tile in enumerate(row):
            if tile != GRASS:
                building_tiles.add((bx, by))

    effective_roof = _TILE_ROOF_KIND.get(bp.kind, roof_kind)
    roof_color = ROOF_COLORS.get(effective_roof, (100, 90, 80))

    faces = []  # list of (verts, color)

    for by, row in enumerate(bp.tiles):
        for bx, tile in enumerate(row):
            x, z = float(bx), float(by)

            if tile == GRASS:
                # Ground tile
                faces.append((
                    [(x, 0, z), (x + 1, 0, z), (x + 1, 0, z + 1), (x, 0, z + 1)],
                    (75, 135, 65)
                ))
                continue

            # Ground floor
            floor_color = TILE_3D_COLORS.get(tile, (150, 125, 90))
            faces.append((
                [(x, 0, z), (x + 1, 0, z), (x + 1, 0, z + 1), (x, 0, z + 1)],
                floor_color
            ))

            is_wall = tile == WALL or tile == WINDOW or tile == BUILT_WALL

            if is_wall:
                # Wall cube: 4 vertical faces
                y0, y1 = 0, wall_h
                # South face (z+1)
                if (bx, by + 1) not in building_tiles:
                    faces.append((
                        [(x, y0, z + 1), (x + 1, y0, z + 1),
                         (x + 1, y1, z + 1), (x, y1, z + 1)],
                        WALL_COLORS['S']
                    ))
                # North face (z)
                if (bx, by - 1) not in building_tiles:
                    faces.append((
                        [(x + 1, y0, z), (x, y0, z),
                         (x, y1, z), (x + 1, y1, z)],
                        WALL_COLORS['N']
                    ))
                # East face (x+1)
                if (bx + 1, by) not in building_tiles:
                    faces.append((
                        [(x + 1, y0, z), (x + 1, y0, z + 1),
                         (x + 1, y1, z + 1), (x + 1, y1, z)],
                        WALL_COLORS['E']
                    ))
                # West face (x)
                if (bx - 1, by) not in building_tiles:
                    faces.append((
                        [(x, y0, z + 1), (x, y0, z),
                         (x, y1, z), (x, y1, z + 1)],
                        WALL_COLORS['W']
                    ))

                # Window opening (darker rectangle on exterior walls)
                if tile == WINDOW:
                    win_y0 = wall_h * 0.35
                    win_y1 = wall_h * 0.75
                    if (bx, by + 1) not in building_tiles:
                        faces.append((
                            [(x + 0.2, win_y0, z + 1.01), (x + 0.8, win_y0, z + 1.01),
                             (x + 0.8, win_y1, z + 1.01), (x + 0.2, win_y1, z + 1.01)],
                            (80, 120, 160)
                        ))

            elif tile == DOOR or tile == LOCKED_DOOR:
                # Door: shorter wall with opening
                door_h = wall_h * 0.75
                door_color = (100, 70, 40) if tile == DOOR else (80, 55, 30)
                # Door face (south)
                if (bx, by + 1) not in building_tiles:
                    faces.append((
                        [(x + 0.15, 0, z + 1.01), (x + 0.85, 0, z + 1.01),
                         (x + 0.85, door_h, z + 1.01), (x + 0.15, door_h, z + 1.01)],
                        door_color
                    ))
                # North door
                if (bx, by - 1) not in building_tiles:
                    faces.append((
                        [(x + 0.85, 0, z - 0.01), (x + 0.15, 0, z - 0.01),
                         (x + 0.15, door_h, z - 0.01), (x + 0.85, door_h, z - 0.01)],
                        door_color
                    ))

            # Furniture as small boxes
            if tile == TABLE:
                _add_box(faces, x + 0.15, 0.35, z + 0.15, 0.7, 0.05, 0.7, (120, 90, 50))
                for lx, lz in [(0.2, 0.2), (0.8, 0.2), (0.2, 0.8), (0.8, 0.8)]:
                    _add_box(faces, x + lx - 0.03, 0, z + lz - 0.03, 0.06, 0.35, 0.06, (100, 75, 40))
            elif tile == BED:
                _add_box(faces, x + 0.1, 0.15, z + 0.1, 0.8, 0.15, 0.8, (140, 80, 60))
                _add_box(faces, x + 0.1, 0.3, z + 0.1, 0.8, 0.1, 0.25, (180, 170, 160))  # pillow
            elif tile == CHEST:
                _add_box(faces, x + 0.2, 0, z + 0.2, 0.6, 0.35, 0.6, (160, 130, 50))
            elif tile == BARREL:
                _add_box(faces, x + 0.2, 0, z + 0.2, 0.6, 0.5, 0.6, (130, 100, 55))
            elif tile == ANVIL:
                _add_box(faces, x + 0.25, 0, z + 0.25, 0.5, 0.4, 0.5, (100, 100, 110))
            elif tile == FIREPLACE:
                _add_box(faces, x + 0.1, 0, z + 0.1, 0.8, 0.5, 0.8, (80, 50, 30))
                faces.append((
                    [(x + 0.25, 0.15, z + 0.25), (x + 0.75, 0.15, z + 0.25),
                     (x + 0.75, 0.15, z + 0.75), (x + 0.25, 0.15, z + 0.75)],
                    (220, 120, 30)
                ))
            elif tile == THRONE:
                _add_box(faces, x + 0.2, 0, z + 0.2, 0.6, 0.4, 0.6, (170, 140, 50))
                _add_box(faces, x + 0.2, 0.4, z + 0.2, 0.6, 0.5, 0.15, (180, 150, 60))  # back
            elif tile == BOOKSHELF:
                _add_box(faces, x + 0.1, 0, z + 0.3, 0.8, 0.9, 0.4, (100, 75, 45))

            # Roof tile on every building tile
            if show_roof and (bx, by) in building_tiles:
                # Darken roof slightly for variety
                rv = ((bx * 7 + by * 13) % 4) * 3
                rc = (min(255, roof_color[0] + rv), min(255, roof_color[1] + rv),
                      min(255, roof_color[2] + rv))
                faces.append((
                    [(x, wall_h, z), (x + 1, wall_h, z),
                     (x + 1, wall_h, z + 1), (x, wall_h, z + 1)],
                    rc
                ))

    # Pitched roof ridge (triangular gable on short sides)
    if show_roof:
        _add_pitched_roof(faces, bp, building_tiles, wall_h, roof_color)

    return faces


def _add_box(faces, x, y, z, w, h, d, color):
    """Add a box (6 faces) to the face list."""
    x2, y2, z2 = x + w, y + h, z + d
    # Lighten top, darken sides
    top = (min(255, color[0] + 15), min(255, color[1] + 15), min(255, color[2] + 15))
    dark = (max(0, color[0] - 20), max(0, color[1] - 20), max(0, color[2] - 20))
    faces.append(([(x, y2, z), (x2, y2, z), (x2, y2, z2), (x, y2, z2)], top))      # top
    faces.append(([(x, y, z2), (x2, y, z2), (x2, y, z), (x, y, z)], dark))          # bottom
    faces.append(([(x, y, z2), (x2, y, z2), (x2, y2, z2), (x, y2, z2)], color))     # south
    faces.append(([(x2, y, z), (x, y, z), (x, y2, z), (x2, y2, z)], dark))          # north
    faces.append(([(x2, y, z2), (x2, y, z), (x2, y2, z), (x2, y2, z2)], color))     # east
    faces.append(([(x, y, z), (x, y, z2), (x, y2, z2), (x, y2, z)], dark))          # west


def _add_pitched_roof(faces, bp, building_tiles, wall_h, roof_color):
    """Add a pitched gable roof ridge."""
    if not building_tiles:
        return
    min_bx = min(bx for bx, _ in building_tiles)
    max_bx = max(bx for bx, _ in building_tiles)
    min_by = min(by for _, by in building_tiles)
    max_by = max(by for _, by in building_tiles)

    bw = max_bx - min_bx + 1
    bh = max_by - min_by + 1
    ridge_h = wall_h + min(bw, bh) * 0.3  # ridge height

    cx = min_bx + bw / 2.0
    z0, z1 = float(min_by), float(max_by + 1)
    x0, x1 = float(min_bx), float(max_bx + 1)

    bright = (min(255, roof_color[0] + 25), min(255, roof_color[1] + 20),
              min(255, roof_color[2] + 15))
    dark = (max(0, roof_color[0] - 20), max(0, roof_color[1] - 15),
            max(0, roof_color[2] - 10))

    # South slope
    faces.append((
        [(x0, wall_h, z1), (x1, wall_h, z1), (cx, ridge_h, z1), (cx, ridge_h, z1)],
        bright
    ))
    # North slope
    faces.append((
        [(x1, wall_h, z0), (x0, wall_h, z0), (cx, ridge_h, z0), (cx, ridge_h, z0)],
        dark
    ))
    # West slope
    faces.append((
        [(x0, wall_h, z0), (x0, wall_h, z1), (cx, ridge_h, z1), (cx, ridge_h, z0)],
        dark
    ))
    # East slope
    faces.append((
        [(x1, wall_h, z1), (x1, wall_h, z0), (cx, ridge_h, z0), (cx, ridge_h, z1)],
        bright
    ))


# ── Compile + render ────────────────────────────────────────────────────

def compile_faces(faces):
    """Compile face list into OpenGL display list."""
    dl = glGenLists(1)
    glNewList(dl, GL_COMPILE)
    glBegin(GL_TRIANGLES)
    for verts, color in faces:
        if len(verts) >= 3:
            _gl_color(color)
            for i in range(1, len(verts) - 1):
                v0, v1, v2 = verts[0], verts[i], verts[i + 1]
                glVertex3f(*v0); glVertex3f(*v1); glVertex3f(*v2)
                glVertex3f(*v0); glVertex3f(*v2); glVertex3f(*v1)
    glEnd()
    glEndList()
    return dl


# ── Main ────────────────────────────────────────────────────────────────

ROOF_KINDS = ["hamlet", "village", "town", "city", "castle", "temple"]


def main():
    bp_idx = 0
    roof_idx = 0
    num_floors = 1
    rotation = 0
    azimuth = 25.0
    elevation = -35.0
    cam_dist = 20.0
    show_roof = True

    glEnable(GL_DEPTH_TEST)
    glDisable(GL_CULL_FACE)
    glClearColor(0.45, 0.55, 0.7, 1.0)

    display_list = None
    needs_rebuild = True

    # HUD font rendering (2D overlay)
    hud_font = pygame.font.SysFont("monospace", 14)

    running = True
    while running:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                mods = pygame.key.get_mods()
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT:
                    if mods & pygame.KMOD_SHIFT:
                        azimuth -= 10
                    else:
                        bp_idx = (bp_idx - 1) % len(ALL_BLUEPRINTS)
                        rotation = 0
                        needs_rebuild = True
                elif event.key == pygame.K_RIGHT:
                    if mods & pygame.KMOD_SHIFT:
                        azimuth += 10
                    else:
                        bp_idx = (bp_idx + 1) % len(ALL_BLUEPRINTS)
                        rotation = 0
                        needs_rebuild = True
                elif event.key == pygame.K_UP:
                    if mods & pygame.KMOD_SHIFT:
                        elevation = max(-80, elevation - 5)
                    else:
                        num_floors = min(3, num_floors + 1)
                        needs_rebuild = True
                elif event.key == pygame.K_DOWN:
                    if mods & pygame.KMOD_SHIFT:
                        elevation = min(-10, elevation + 5)
                    else:
                        num_floors = max(1, num_floors - 1)
                        needs_rebuild = True
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                    cam_dist = max(5, cam_dist - 3)
                elif event.key == pygame.K_MINUS:
                    cam_dist = min(60, cam_dist + 3)
                elif event.key == pygame.K_r:
                    rotation = (rotation + 1) % 4
                    needs_rebuild = True
                elif event.key == pygame.K_t:
                    roof_idx = (roof_idx + 1) % len(ROOF_KINDS)
                    needs_rebuild = True
                elif event.key == pygame.K_v:
                    show_roof = not show_roof
                    needs_rebuild = True
                elif event.key == pygame.K_s:
                    # Screenshot via readPixels
                    data = glReadPixels(0, 0, SCREEN_W, SCREEN_H, GL_RGB, GL_UNSIGNED_BYTE)
                    surf = pygame.image.fromstring(bytes(data), (SCREEN_W, SCREEN_H), "RGB", True)
                    pygame.image.save(surf, "screenshot_building_3d.png")

        # Rebuild geometry if needed
        if needs_rebuild:
            bp = ALL_BLUEPRINTS[bp_idx]
            for _ in range(rotation):
                bp = bp.rotated()

            faces = build_building_faces(bp, num_floors, ROOF_KINDS[roof_idx],
                                        show_roof=show_roof)

            if display_list:
                glDeleteLists(display_list, 1)
            display_list = compile_faces(faces)
            needs_rebuild = False

        # ── Render 3D ───────────────────────────────────────────────
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, SCREEN_W / SCREEN_H, 0.1, 200.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Camera orbits around building center
        bp = ALL_BLUEPRINTS[bp_idx]
        for _ in range(rotation):
            bp = bp.rotated()
        center_x = bp.width / 2.0
        center_z = bp.height / 2.0

        az_rad = math.radians(azimuth)
        el_rad = math.radians(elevation)
        cam_x = center_x + cam_dist * math.sin(az_rad) * math.cos(el_rad)
        cam_y = cam_dist * -math.sin(el_rad)
        cam_z = center_z + cam_dist * math.cos(az_rad) * math.cos(el_rad)
        gluLookAt(cam_x, cam_y, cam_z, center_x, 0.5, center_z, 0.0, 1.0, 0.0)

        if display_list:
            glCallList(display_list)

        # ── 2D HUD overlay ──────────────────────────────────────────
        _draw_hud(bp_idx, roof_idx, num_floors, rotation, azimuth, elevation, cam_dist,
                  show_roof)

        pygame.display.flip()

    if display_list:
        glDeleteLists(display_list, 1)
    pygame.quit()


def _draw_hud(bp_idx, roof_idx, num_floors, rotation, azimuth, elevation, cam_dist,
              show_roof=True):
    """Draw 2D text overlay on top of 3D scene."""
    # Switch to 2D projection
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, SCREEN_W, SCREEN_H, 0, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glDisable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    bp = ALL_BLUEPRINTS[bp_idx]
    roof_state = "ON" if show_roof else "OFF"
    lines = [
        f"{bp.name} ({bp.kind}) {bp.width}x{bp.height} | Roof: {ROOF_KINDS[roof_idx]} {roof_state}",
        f"Floors: {num_floors} | Rot: {rotation * 90} | Az: {azimuth:.0f} El: {elevation:.0f}",
        f"[{bp_idx + 1}/{len(ALL_BLUEPRINTS)}] LEFT/RIGHT: bldg  SHIFT+arrows: camera  +/-: zoom",
        f"R: rotate  T: roof style  V: toggle roof  UP/DOWN: floors  S: screenshot",
    ]

    font = pygame.font.SysFont("monospace", 13)
    # Render all lines onto a single surface with dark background
    line_h = 16
    max_w = max(font.size(line)[0] for line in lines) + 12
    hud_h = len(lines) * line_h + 8
    hud_surf = pygame.Surface((max_w, hud_h), pygame.SRCALPHA)
    hud_surf.fill((15, 15, 25, 200))
    for i, line in enumerate(lines):
        text = font.render(line, True, (240, 240, 255))
        hud_surf.blit(text, (6, 4 + i * line_h))

    # Blit to OpenGL via glDrawPixels
    data = pygame.image.tostring(hud_surf, "RGBA", True)
    glRasterPos2i(8, 8 + hud_h)
    glDrawPixels(max_w, hud_h, GL_RGBA, GL_UNSIGNED_BYTE, data)

    glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()


if __name__ == "__main__":
    main()
