#!/usr/bin/env python3
"""3D Building Model Viewer — find the right camera perspective.

Creates actual 3D geometry for buildings (boxes + roof prisms/cones),
projects them with a proper camera, and renders filled polygons.
Once we find the right angle, we lock it in for all building rendering.

Controls:
  Left/Right: rotate camera horizontally (azimuth)
  Up/Down: rotate camera vertically (elevation)
  +/-: zoom in/out
  1-5: change number of floors
  R: cycle roof style (flat, pitched, conical, hip)
  B: cycle building preset
  W: toggle wireframe/filled
  S: save screenshot
  P: print current camera angles
  Esc: quit
"""

import os
import sys
import math

# Don't override SDL_VIDEODRIVER — let pygame use the native display
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

SCREEN_W, SCREEN_H = 900, 700
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("3D Building Viewer — Find the Right Perspective")
clock = pygame.time.Clock()


# ================================================================
# 3D MATH
# ================================================================

def rotate_y(point, angle):
    """Rotate point around Y axis (horizontal rotation)."""
    x, y, z = point
    c, s = math.cos(angle), math.sin(angle)
    return (x * c + z * s, y, -x * s + z * c)


def rotate_x(point, angle):
    """Rotate point around X axis (vertical tilt)."""
    x, y, z = point
    c, s = math.cos(angle), math.sin(angle)
    return (x, y * c - z * s, y * s + z * c)


def project(point, cam_dist, screen_cx, screen_cy, scale):
    """Project 3D point to 2D screen using perspective projection."""
    x, y, z = point
    # Perspective divide (z is depth into screen)
    if z <= 0.1:
        z = 0.1
    factor = cam_dist / z * scale
    sx = screen_cx + x * factor
    sy = screen_cy - y * factor  # flip Y (screen Y goes down)
    return (int(sx), int(sy)), z


def transform_point(point, azimuth, elevation, cam_dist):
    """Transform a world point through camera rotation."""
    p = rotate_y(point, azimuth)
    p = rotate_x(p, elevation)
    # Translate along Z (move camera back)
    return (p[0], p[1], p[2] + cam_dist)


# ================================================================
# 3D BUILDING GEOMETRY
# ================================================================

def make_box(x, y, z, w, h, d):
    """Create a box (6 faces) at position (x,y,z) with size (w,h,d).
    Y is up. Returns list of (vertices, color, normal_hint) for each face.
    """
    x2, y2, z2 = x + w, y + h, z + d
    faces = [
        # South face (front, facing -Z)
        ([(x, y, z), (x2, y, z), (x2, y2, z), (x, y2, z)], "south"),
        # North face (back, facing +Z)
        ([(x2, y, z2), (x, y, z2), (x, y2, z2), (x2, y2, z2)], "north"),
        # East face (right, facing +X)
        ([(x2, y, z), (x2, y, z2), (x2, y2, z2), (x2, y2, z)], "east"),
        # West face (left, facing -X)
        ([(x, y, z2), (x, y, z), (x, y2, z), (x, y2, z2)], "west"),
        # Top face (facing +Y)
        ([(x, y2, z), (x2, y2, z), (x2, y2, z2), (x, y2, z2)], "top"),
        # Bottom face (facing -Y)
        ([(x, y, z2), (x2, y, z2), (x2, y, z), (x, y, z)], "bottom"),
    ]
    return faces


def make_pitched_roof(x, y, z, w, h, d):
    """Create a pitched (gable) roof prism. Ridge runs along Z (N-S).
    Base at y, peak at y+h, width w, depth d.
    """
    x2 = x + w
    z2 = z + d
    mid_x = x + w / 2  # ridge along center X

    faces = [
        # South gable (triangle, facing -Z)
        ([(x, y, z), (x2, y, z), (mid_x, y + h, z)], "south"),
        # North gable (triangle, facing +Z)
        ([(x2, y, z2), (x, y, z2), (mid_x, y + h, z2)], "north"),
        # West slope (facing west-up)
        ([(x, y, z), (x, y, z2), (mid_x, y + h, z2), (mid_x, y + h, z)], "west_slope"),
        # East slope (facing east-up)
        ([(x2, y, z2), (x2, y, z), (mid_x, y + h, z), (mid_x, y + h, z2)], "east_slope"),
    ]
    return faces


def make_hip_roof(x, y, z, w, h, d):
    """Hip roof — all 4 sides slope inward to a ridge."""
    x2 = x + w
    z2 = z + d
    # Ridge is a shorter line at the top, centered
    inset = min(w, d) * 0.35
    rx1 = x + inset
    rx2 = x2 - inset
    rz1 = z + inset
    rz2 = z2 - inset
    ry = y + h

    faces = [
        # South face (trapezoid)
        ([(x, y, z), (x2, y, z), (rx2, ry, rz1), (rx1, ry, rz1)], "south"),
        # North face
        ([(x2, y, z2), (x, y, z2), (rx1, ry, rz2), (rx2, ry, rz2)], "north"),
        # East face
        ([(x2, y, z), (x2, y, z2), (rx2, ry, rz2), (rx2, ry, rz1)], "east"),
        # West face
        ([(x, y, z2), (x, y, z), (rx1, ry, rz1), (rx1, ry, rz2)], "west"),
        # Top (small rectangle)
        ([(rx1, ry, rz1), (rx2, ry, rz1), (rx2, ry, rz2), (rx1, ry, rz2)], "top"),
    ]
    return faces


def make_cone_roof(cx, y, cz, radius, h, segments=16):
    """Conical roof. Circle base at y, peak at y+h."""
    peak = (cx, y + h, cz)
    faces = []
    for i in range(segments):
        a1 = 2 * math.pi * i / segments
        a2 = 2 * math.pi * (i + 1) / segments
        p1 = (cx + radius * math.cos(a1), y, cz + radius * math.sin(a1))
        p2 = (cx + radius * math.cos(a2), y, cz + radius * math.sin(a2))
        # Determine face direction for shading
        mid_a = (a1 + a2) / 2
        if mid_a < math.pi:
            hint = "north" if mid_a < math.pi / 2 else "west"
        else:
            hint = "south" if mid_a < 3 * math.pi / 2 else "east"
        faces.append(([p1, p2, peak], hint))
    return faces


# ================================================================
# BUILDING PRESETS
# ================================================================

PRESETS = [
    {"name": "Cottage 5x5", "w": 5, "h": 5, "floors": 1, "shape": "rect"},
    {"name": "House 8x6", "w": 8, "h": 6, "floors": 2, "shape": "rect"},
    {"name": "Tower 6x6", "w": 6, "h": 6, "floors": 3, "shape": "rect"},
    {"name": "Keep 12x10", "w": 12, "h": 10, "floors": 2, "shape": "rect"},
    {"name": "Temple r=5", "w": 10, "h": 10, "floors": 1, "shape": "circle", "radius": 5},
    {"name": "Round Tower r=3", "w": 6, "h": 6, "floors": 3, "shape": "circle", "radius": 3},
]

ROOF_STYLES = ["flat", "pitched", "conical", "hip"]

# Face colors based on direction
FACE_COLORS = {
    "south":      (160, 145, 125),  # brightest (facing camera)
    "north":      (90, 80, 70),     # darkest (facing away)
    "east":       (120, 110, 95),   # medium-dark
    "west":       (100, 90, 78),    # dark
    "top":        (140, 130, 115),  # medium (seen from above)
    "bottom":     (60, 55, 50),
    "west_slope": (130, 85, 45),    # roof west slope
    "east_slope": (155, 100, 55),   # roof east slope (brighter)
    "south_slope": (165, 110, 60),  # roof south
    "north_slope": (110, 72, 38),   # roof north (darker)
}

ROOF_COLORS = {
    "hamlet":  {"west_slope": (140, 105, 50), "east_slope": (165, 125, 60),
                "south": (155, 115, 55), "north": (115, 85, 42), "top": (150, 110, 52)},
    "castle":  {"west_slope": (70, 72, 80), "east_slope": (90, 92, 105),
                "south": (85, 87, 98), "north": (58, 60, 68), "top": (80, 82, 92)},
    "village": {"west_slope": (140, 70, 35), "east_slope": (170, 85, 45),
                "south": (160, 80, 40), "north": (115, 58, 30), "top": (150, 75, 38)},
    "temple":  {"west_slope": (110, 130, 50), "east_slope": (135, 155, 65),
                "south": (125, 145, 58), "north": (90, 110, 42), "top": (120, 140, 55)},
}


def build_geometry(preset, num_floors, roof_style):
    """Generate all 3D faces for a building."""
    w = preset["w"]
    d = preset["h"]  # depth (N-S)
    floor_h = 1.5     # height per floor in world units
    shape = preset.get("shape", "rect")
    radius = preset.get("radius", 0)

    all_faces = []  # (projected_verts, color, avg_z)

    # Center building at origin
    ox = -w / 2
    oz = -d / 2

    # Wall box(es)
    if shape == "circle" and radius > 0:
        # Approximate circle with octagonal segments
        segments = 16
        for i in range(segments):
            a1 = 2 * math.pi * i / segments
            a2 = 2 * math.pi * (i + 1) / segments
            x1 = radius * math.cos(a1)
            z1 = radius * math.sin(a1)
            x2 = radius * math.cos(a2)
            z2 = radius * math.sin(a2)
            h = num_floors * floor_h
            face = [(x1, 0, z1), (x2, 0, z2), (x2, h, z2), (x1, h, z1)]
            # Direction hint
            mid_a = (a1 + a2) / 2
            if abs(math.sin(mid_a)) > abs(math.cos(mid_a)):
                hint = "south" if math.sin(mid_a) < 0 else "north"
            else:
                hint = "east" if math.cos(mid_a) > 0 else "west"
            all_faces.append((face, "wall", hint))

        # Top cap (flat roof base)
        top_y = num_floors * floor_h
        top_face = []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            top_face.append((radius * math.cos(a), top_y, radius * math.sin(a)))
        all_faces.append((top_face, "roof_base", "top"))

    else:
        # Rectangular walls
        wall_faces = make_box(ox, 0, oz, w, num_floors * floor_h, d)
        for verts, hint in wall_faces:
            all_faces.append((verts, "wall", hint))

    # Roof
    top_y = num_floors * floor_h
    roof_h = min(w, d) * 0.4  # roof height proportional to building

    if roof_style == "pitched":
        if shape == "circle":
            # Conical for circular buildings
            roof_faces = make_cone_roof(0, top_y, 0, radius, roof_h)
        else:
            roof_faces = make_pitched_roof(ox, top_y, oz, w, roof_h, d)
        for verts, hint in roof_faces:
            all_faces.append((verts, "roof", hint))

    elif roof_style == "conical":
        r = radius if radius > 0 else min(w, d) / 2
        roof_faces = make_cone_roof(0 if radius else ox + w/2, top_y,
                                     0 if radius else oz + d/2,
                                     r, roof_h, 20)
        for verts, hint in roof_faces:
            all_faces.append((verts, "roof", hint))

    elif roof_style == "hip":
        if shape == "circle":
            roof_faces = make_cone_roof(0, top_y, 0, radius, roof_h)
        else:
            roof_faces = make_hip_roof(ox, top_y, oz, w, roof_h, d)
        for verts, hint in roof_faces:
            all_faces.append((verts, "roof", hint))

    # else flat — no extra roof geometry

    return all_faces


# ================================================================
# RENDERING
# ================================================================

def render_building(surface, faces, azimuth, elevation, cam_dist, scale,
                    wireframe=False, kind="hamlet"):
    """Project and render all faces with painter's algorithm."""
    cx = surface.get_width() // 2
    cy = surface.get_height() // 2

    projected_faces = []

    for verts_3d, part, hint in faces:
        # Transform all vertices
        transformed = [transform_point(v, azimuth, elevation, cam_dist)
                       for v in verts_3d]
        # Project to 2D
        screen_pts = []
        avg_z = 0
        valid = True
        for tv in transformed:
            sp, z = project(tv, cam_dist, cx, cy, scale)
            screen_pts.append(sp)
            avg_z += z
            if z < 0.1:
                valid = False
        if not valid:
            continue
        avg_z /= len(transformed)

        # Determine color
        if part == "wall":
            color = FACE_COLORS.get(hint, (130, 120, 105))
        elif part == "roof":
            roof_palette = ROOF_COLORS.get(kind, ROOF_COLORS["hamlet"])
            color = roof_palette.get(hint, roof_palette.get("top", (140, 100, 55)))
        elif part == "roof_base":
            color = FACE_COLORS.get("top", (140, 130, 115))
        else:
            color = (120, 110, 100)

        projected_faces.append((screen_pts, color, avg_z, part, hint))

    # Painter's algorithm: draw far faces first
    projected_faces.sort(key=lambda f: -f[2])

    for pts, color, _, part, hint in projected_faces:
        if len(pts) < 3:
            continue
        if wireframe:
            pygame.draw.polygon(surface, color, pts, 1)
        else:
            pygame.draw.polygon(surface, color, pts)
            # Edge lines for definition
            edge_color = (max(0, color[0] - 25), max(0, color[1] - 22),
                          max(0, color[2] - 18))
            pygame.draw.polygon(surface, edge_color, pts, 1)


# ================================================================
# MAIN LOOP
# ================================================================

def main():
    # Camera angles — start with a good guess
    azimuth = math.radians(-25)    # slight rotation to see east side
    elevation = math.radians(-55)  # looking down at ~55 degrees
    cam_dist = 15.0
    scale = 40.0

    preset_idx = 2   # start with Tower
    roof_idx = 1     # pitched
    num_floors = 3
    wireframe = False
    kind = "castle"

    font = pygame.font.SysFont("monospace", 14)
    font_lg = pygame.font.SysFont("monospace", 18, bold=True)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_LEFT:
                    azimuth -= math.radians(5)
                elif event.key == pygame.K_RIGHT:
                    azimuth += math.radians(5)
                elif event.key == pygame.K_UP:
                    elevation -= math.radians(5)
                elif event.key == pygame.K_DOWN:
                    elevation += math.radians(5)
                elif event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                    scale *= 1.2
                elif event.key == pygame.K_MINUS:
                    scale /= 1.2
                elif event.key == pygame.K_r:
                    roof_idx = (roof_idx + 1) % len(ROOF_STYLES)
                elif event.key == pygame.K_b:
                    preset_idx = (preset_idx + 1) % len(PRESETS)
                    kind = ["hamlet", "village", "castle", "castle", "temple", "castle"][preset_idx]
                elif event.key == pygame.K_w:
                    wireframe = not wireframe
                elif event.key == pygame.K_1:
                    num_floors = 1
                elif event.key == pygame.K_2:
                    num_floors = 2
                elif event.key == pygame.K_3:
                    num_floors = 3
                elif event.key == pygame.K_4:
                    num_floors = 4
                elif event.key == pygame.K_5:
                    num_floors = 5
                elif event.key == pygame.K_p:
                    print(f"azimuth={math.degrees(azimuth):.1f}  "
                          f"elevation={math.degrees(elevation):.1f}  "
                          f"cam_dist={cam_dist:.1f}  scale={scale:.1f}")
                elif event.key == pygame.K_s:
                    pygame.image.save(screen, "exports/screenshots/3d_building.png")
                    print("Saved 3d_building.png")

        preset = PRESETS[preset_idx]
        roof_style = ROOF_STYLES[roof_idx]
        faces = build_geometry(preset, num_floors, roof_style)

        # Draw
        screen.fill((180, 170, 145))

        # Ground plane (simple quad)
        ground_pts = []
        for gp in [(-20, 0, -20), (20, 0, -20), (20, 0, 20), (-20, 0, 20)]:
            tp = transform_point(gp, azimuth, elevation, cam_dist)
            sp, _ = project(tp, cam_dist, SCREEN_W // 2, SCREEN_H // 2, scale)
            ground_pts.append(sp)
        pygame.draw.polygon(screen, (165, 155, 130), ground_pts)
        pygame.draw.polygon(screen, (145, 135, 115), ground_pts, 1)

        render_building(screen, faces, azimuth, elevation, cam_dist, scale,
                        wireframe, kind)

        # UI
        y = 10
        lines = [
            f"Building: {preset['name']}  (B)",
            f"Floors: {num_floors}  (1-5)",
            f"Roof: {roof_style}  (R)",
            f"Azimuth: {math.degrees(azimuth):.0f} deg  (Left/Right)",
            f"Elevation: {math.degrees(elevation):.0f} deg  (Up/Down)",
            f"Scale: {scale:.0f}  (+/-)",
            f"{'Wireframe' if wireframe else 'Filled'}  (W)",
            "P: print angles  S: screenshot  Esc: quit",
        ]
        for txt in lines:
            surf = font.render(txt, True, (40, 40, 50))
            screen.blit(surf, (10, y))
            y += 16

        title = font_lg.render("3D Building Viewer", True, (60, 50, 40))
        screen.blit(title, (SCREEN_W - title.get_width() - 10, 10))

        pygame.display.flip()
        clock.tick(30)

    pygame.quit()


if __name__ == "__main__":
    main()
