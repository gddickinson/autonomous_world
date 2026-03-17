"""
3D Planet View — interactive rotating globe showing Edras.

Renders a sphere with continents, oceans, cities, and trade routes.
Uses software 3D rendering (no OpenGL) via spherical coordinate projection.

Controls:
  Left/Right arrows — rotate longitude
  Up/Down arrows — rotate latitude
  +/- — zoom in/out
  Escape/M — close

Features:
  - Textured sphere with continents colored by climate
  - City dots with names on hover
  - Trade route arcs between continents
  - Aethermoor highlighted as the playable continent
  - Day/night shading based on current game time
  - Legends panel showing continent info
"""

import math
import pygame
from typing import List, Tuple, Optional, Dict
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT, UI_BORDER, UI_TEXT, UI_HIGHLIGHT


# ================================================================
# CONTINENT GEOGRAPHY — lat/lon positions on the globe
# ================================================================

# Each continent defined by center lat/lon and polygon points (lat, lon)
# Latitude: -90 (south pole) to +90 (north pole)
# Longitude: -180 to +180

GLOBE_CONTINENTS = {
    "aethermoor": {
        "name": "Aethermoor",
        "color": (80, 140, 70),
        "highlight_color": (120, 200, 90),
        "center": (45, -60),  # lat, lon — northern hemisphere, western
        # ~150km island = ~1.4° lat x 1.9° lon — tiny on globe
        # Draw slightly enlarged (3x) so it's visible as a dot
        "points": [
            (47.5, -63), (47.8, -61), (47.3, -58.5), (46, -57.5),
            (44.5, -57.8), (43.5, -59), (43.2, -61), (43.8, -63),
            (45, -63.5), (46.5, -63.5), (47.5, -63),
        ],
        "is_playable": True,
        "draw_marker": True,  # draw a special marker since it's tiny
        "cities": [
            {"name": "Hearthstone", "lat": 45.2, "lon": -60.2, "size": 2},
            {"name": "Sunridge", "lat": 45.8, "lon": -59.5, "size": 2},
            {"name": "Ironholt", "lat": 46.5, "lon": -61, "size": 2},
            {"name": "Silverleaf", "lat": 44.5, "lon": -62, "size": 1},
            {"name": "Tidehaven", "lat": 43.8, "lon": -60.5, "size": 1},
        ],
    },
    # Nearby island groups in the western ocean
    "windward_isles": {
        "name": "Windward Isles",
        "color": (70, 130, 65),
        "highlight_color": (100, 170, 85),
        "center": (40, -55),
        "points": [
            (41, -56.5), (41.5, -55.5), (41, -54.5), (40, -54),
            (39, -54.5), (39, -55.5), (39.5, -56.5), (41, -56.5),
        ],
        "is_playable": False,
        "cities": [
            {"name": "Galeport", "lat": 40, "lon": -55, "size": 2},
        ],
    },
    "northshield": {
        "name": "Northshield",
        "color": (90, 130, 80),
        "highlight_color": (120, 170, 100),
        "center": (50, -65),
        "points": [
            (51, -66.5), (51.5, -65), (51, -63.5), (49.5, -63.5),
            (49, -65), (49.5, -66.5), (51, -66.5),
        ],
        "is_playable": False,
        "cities": [
            {"name": "Frostkeep", "lat": 50.2, "lon": -65, "size": 2},
        ],
    },
    "khor_dural": {
        "name": "Khor'Dural",
        "color": (150, 120, 80),
        "highlight_color": (180, 150, 100),
        "center": (40, 60),  # northern hemisphere, eastern
        "points": [
            (60, 25), (65, 40), (62, 60), (58, 80), (55, 95),
            (48, 100), (35, 95), (25, 85), (20, 70), (22, 50),
            (28, 35), (35, 25), (45, 20), (55, 22), (60, 25),
        ],
        "is_playable": False,
        "cities": [
            {"name": "Zarath", "lat": 42, "lon": 55, "size": 5},
            {"name": "Jade City", "lat": 35, "lon": 80, "size": 3},
            {"name": "Frostwatch", "lat": 58, "lon": 70, "size": 2},
            {"name": "Western Shore", "lat": 38, "lon": 30, "size": 2},
            {"name": "Dragon Peak", "lat": 50, "lon": 50, "size": 2},
        ],
    },
    "sun_vaal": {
        "name": "Sun'Vaal",
        "color": (180, 160, 80),
        "highlight_color": (210, 190, 100),
        "center": (-20, 20),  # southern hemisphere, central
        "points": [
            (-5, 0), (-3, 15), (-5, 30), (-10, 40), (-18, 42),
            (-28, 38), (-35, 30), (-38, 18), (-35, 5), (-28, -5),
            (-18, -8), (-10, -5), (-5, 0),
        ],
        "is_playable": False,
        "cities": [
            {"name": "River of Gold", "lat": -18, "lon": 20, "size": 4},
            {"name": "Pyramid City", "lat": -10, "lon": 15, "size": 3},
            {"name": "Sand Sea Oasis", "lat": -30, "lon": 25, "size": 2},
            {"name": "Tabaxi Throne", "lat": -8, "lon": 8, "size": 3},
        ],
    },
    "thal_marin": {
        "name": "Thal'Marin",
        "color": (100, 160, 130),
        "highlight_color": (130, 190, 160),
        "center": (5, -30),  # equatorial, western
        "points": [  # archipelago — multiple small islands
            (8, -35), (10, -32), (8, -28), (5, -26), (2, -28),
            (0, -32), (2, -36), (5, -38), (8, -35),
        ],
        "is_playable": False,
        "cities": [
            {"name": "Pearl Harbor", "lat": 6, "lon": -31, "size": 3},
            {"name": "Volcano Keep", "lat": 3, "lon": -33, "size": 2},
        ],
    },
    "vorn_thak": {
        "name": "Vorn'Thak",
        "color": (200, 210, 220),
        "highlight_color": (220, 230, 240),
        "center": (-75, 0),  # south polar
        "points": [
            (-65, -40), (-62, -15), (-63, 10), (-65, 35), (-68, 50),
            (-75, 55), (-82, 45), (-85, 20), (-84, -10), (-80, -30),
            (-75, -45), (-68, -45), (-65, -40),
        ],
        "is_playable": False,
        "cities": [
            {"name": "Frozen Archive", "lat": -72, "lon": 5, "size": 2},
            {"name": "Jarl's Seat", "lat": -68, "lon": -20, "size": 2},
        ],
    },
}

# Trade routes as arcs between continent centers
TRADE_ROUTES = [
    ("aethermoor", "thal_marin", (80, 180, 220)),
    ("aethermoor", "khor_dural", (180, 180, 220)),
    ("aethermoor", "windward_isles", (120, 200, 160)),
    ("aethermoor", "northshield", (140, 180, 200)),
    ("khor_dural", "sun_vaal", (220, 180, 80)),
    ("khor_dural", "thal_marin", (180, 200, 180)),
    ("sun_vaal", "thal_marin", (200, 180, 120)),
    ("windward_isles", "thal_marin", (100, 180, 180)),
]


# ================================================================
# 3D SPHERE PROJECTION
# ================================================================

def latlon_to_3d(lat: float, lon: float, radius: float) -> Tuple[float, float, float]:
    """Convert lat/lon (degrees) to 3D cartesian coordinates on a sphere."""
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    x = radius * math.cos(lat_r) * math.sin(lon_r)
    y = -radius * math.sin(lat_r)  # y up
    z = radius * math.cos(lat_r) * math.cos(lon_r)
    return (x, y, z)


def rotate_y(point: Tuple[float, float, float], angle: float) -> Tuple[float, float, float]:
    """Rotate a 3D point around the Y axis."""
    x, y, z = point
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (x * cos_a + z * sin_a, y, -x * sin_a + z * cos_a)


def rotate_x(point: Tuple[float, float, float], angle: float) -> Tuple[float, float, float]:
    """Rotate a 3D point around the X axis."""
    x, y, z = point
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (x, y * cos_a - z * sin_a, y * sin_a + z * cos_a)


def project_3d(point: Tuple[float, float, float], cx: int, cy: int,
               fov: float = 600) -> Tuple[Optional[int], Optional[int], float]:
    """Project 3D point to 2D screen coordinates.
    Returns (screen_x, screen_y, depth) or (None, None, depth) if behind camera.
    """
    x, y, z = point
    z_offset = fov * 1.8  # camera distance
    z_proj = z + z_offset
    if z_proj <= 0.1:
        return (None, None, z)
    scale = fov / z_proj
    sx = int(cx + x * scale)
    sy = int(cy + y * scale)
    return (sx, sy, z)


# ================================================================
# PLANET VIEW RENDERER
# ================================================================

class PlanetView:
    """Interactive 3D planet globe view."""

    def __init__(self):
        self.rot_lon = 0.0    # Y-axis rotation (longitude view)
        self.rot_lat = 0.3    # X-axis rotation (latitude tilt)
        self.zoom = 1.0
        self.radius = 220.0
        self.auto_rotate = True
        self.auto_rotate_speed = 0.15
        self.hovered_city = None
        self.hovered_continent = None
        self.selected_continent = "aethermoor"

        # Pre-compute sphere wireframe
        self._grid_lines = self._build_grid()

    def _build_grid(self) -> List[List[Tuple[float, float]]]:
        """Build lat/lon grid lines for the sphere."""
        lines = []
        # Latitude lines (every 30 degrees)
        for lat in range(-60, 90, 30):
            line = []
            for lon in range(-180, 181, 10):
                line.append((lat, lon))
            lines.append(line)
        # Longitude lines (every 30 degrees)
        for lon in range(-180, 180, 30):
            line = []
            for lat in range(-80, 81, 10):
                line.append((lat, lon))
            lines.append(line)
        return lines

    def update(self, dt: float):
        """Update rotation."""
        if self.auto_rotate:
            self.rot_lon += self.auto_rotate_speed * dt

    def handle_input(self, key) -> bool:
        """Handle input. Returns True if consumed."""
        if key == pygame.K_LEFT:
            self.rot_lon -= 0.1
            self.auto_rotate = False
            return True
        elif key == pygame.K_RIGHT:
            self.rot_lon += 0.1
            self.auto_rotate = False
            return True
        elif key == pygame.K_UP:
            self.rot_lat = max(-1.2, self.rot_lat - 0.1)
            return True
        elif key == pygame.K_DOWN:
            self.rot_lat = min(1.2, self.rot_lat + 0.1)
            return True
        elif key in (pygame.K_EQUALS, pygame.K_PLUS):
            self.zoom = min(2.5, self.zoom + 0.1)
            return True
        elif key == pygame.K_MINUS:
            self.zoom = max(0.5, self.zoom - 0.1)
            return True
        elif key == pygame.K_a:
            self.auto_rotate = not self.auto_rotate
            return True
        elif key == pygame.K_TAB:
            # Cycle selected continent
            names = list(GLOBE_CONTINENTS.keys())
            idx = names.index(self.selected_continent) if self.selected_continent in names else 0
            self.selected_continent = names[(idx + 1) % len(names)]
            # Snap view to that continent
            cont = GLOBE_CONTINENTS[self.selected_continent]
            self.rot_lon = -math.radians(cont["center"][1])
            self.rot_lat = math.radians(cont["center"][0]) * 0.5
            self.auto_rotate = False
            return True
        return False

    def _transform(self, lat: float, lon: float) -> Tuple[Optional[int], Optional[int], float]:
        """Transform lat/lon to screen coords with current rotation."""
        r = self.radius * self.zoom
        p = latlon_to_3d(lat, lon, r)
        p = rotate_y(p, self.rot_lon)
        p = rotate_x(p, self.rot_lat)
        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        return project_3d(p, cx, cy, 600 * self.zoom)

    def _is_visible(self, lat: float, lon: float) -> bool:
        """Check if a point on the sphere is on the visible side."""
        r = self.radius * self.zoom
        p = latlon_to_3d(lat, lon, r)
        p = rotate_y(p, self.rot_lon)
        p = rotate_x(p, self.rot_lat)
        return p[2] > -r * 0.1  # visible if z > slight threshold

    def draw(self, screen: pygame.Surface, font_sm, font_md, font_lg, time_sys=None):
        """Draw the full planet view."""
        # Dark background
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((5, 5, 15, 240))
        screen.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2
        cy = SCREEN_HEIGHT // 2
        r_screen = int(self.radius * self.zoom * 0.55)  # approximate screen radius

        # Draw ocean sphere (filled circle as base)
        pygame.draw.circle(screen, (25, 45, 80), (cx, cy), r_screen)
        pygame.draw.circle(screen, (35, 60, 100), (cx, cy), r_screen, 1)

        # Draw day/night terminator — darken the night side of the globe
        if time_sys:
            sun_lon = -(time_sys.normalized - 0.5) * 360  # sun longitude based on time of day
            self._draw_terminator(screen, cx, cy, r_screen, sun_lon)

        # Draw atmosphere glow
        for i in range(3):
            glow_r = r_screen + 3 + i * 3
            alpha = 40 - i * 12
            glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (60, 100, 180, alpha), (glow_r, glow_r), glow_r)
            screen.blit(glow_surf, (cx - glow_r, cy - glow_r))

        # Draw grid lines (behind continents)
        for line in self._grid_lines:
            points_2d = []
            for lat, lon in line:
                if self._is_visible(lat, lon):
                    sx, sy, z = self._transform(lat, lon)
                    if sx is not None:
                        points_2d.append((sx, sy))
                else:
                    if len(points_2d) > 1:
                        pygame.draw.lines(screen, (30, 50, 70), False, points_2d, 1)
                    points_2d = []
            if len(points_2d) > 1:
                pygame.draw.lines(screen, (30, 50, 70), False, points_2d, 1)

        # Draw continents (filled polygons)
        mouse_x, mouse_y = pygame.mouse.get_pos()
        self.hovered_continent = None
        self.hovered_city = None

        for cid, cont in GLOBE_CONTINENTS.items():
            visible_points = []
            all_visible = True
            for lat, lon in cont["points"]:
                if self._is_visible(lat, lon):
                    sx, sy, z = self._transform(lat, lon)
                    if sx is not None:
                        visible_points.append((sx, sy))
                else:
                    all_visible = False

            if len(visible_points) < 3:
                continue

            # Determine color
            is_selected = (cid == self.selected_continent)
            is_playable = cont.get("is_playable", False)
            color = cont["highlight_color"] if (is_selected or is_playable) else cont["color"]

            # Draw filled continent
            try:
                pygame.draw.polygon(screen, color, visible_points)
                pygame.draw.polygon(screen, tuple(min(255, c + 30) for c in color),
                                   visible_points, 2)
            except (ValueError, pygame.error):
                pass

            # For tiny islands (like Aethermoor), draw a visible marker
            if cont.get("draw_marker") and visible_points:
                center_lat, center_lon = cont["center"]
                if self._is_visible(center_lat, center_lon):
                    mx, my, _ = self._transform(center_lat, center_lon)
                    if mx is not None:
                        # Pulsing ring to highlight tiny island
                        import time as _time
                        pulse = int(3 + 2 * math.sin(_time.time() * 3))
                        ring_color = (255, 255, 100) if is_playable else color
                        pygame.draw.circle(screen, ring_color, (mx, my), 8 + pulse, 2)
                        pygame.draw.circle(screen, (255, 255, 255), (mx, my), 3)
                        # Label
                        label = font_sm.render(cont["name"], True, ring_color)
                        screen.blit(label, (mx + 12, my - 6))

            # Check hover on continent
            if all_visible and len(visible_points) >= 3:
                # Simple bounding box check
                min_x = min(p[0] for p in visible_points)
                max_x = max(p[0] for p in visible_points)
                min_y = min(p[1] for p in visible_points)
                max_y = max(p[1] for p in visible_points)
                if min_x <= mouse_x <= max_x and min_y <= mouse_y <= max_y:
                    self.hovered_continent = cid

            # Draw cities
            for city in cont.get("cities", []):
                if not self._is_visible(city["lat"], city["lon"]):
                    continue
                sx, sy, z = self._transform(city["lat"], city["lon"])
                if sx is None:
                    continue

                size = city["size"]
                city_color = (255, 220, 100) if is_playable else (200, 200, 180)

                # City dot
                pygame.draw.circle(screen, city_color, (sx, sy), size + 1)
                pygame.draw.circle(screen, (255, 255, 255), (sx, sy), size)

                # Check hover on city
                if abs(mouse_x - sx) < 10 and abs(mouse_y - sy) < 10:
                    self.hovered_city = (city["name"], cid, sx, sy)

                # Always show name for selected continent
                if is_selected and size >= 2:
                    name_surf = font_sm.render(city["name"], True, city_color)
                    screen.blit(name_surf, (sx + size + 4, sy - 6))

        # Draw trade routes (arcs between continents)
        for from_id, to_id, route_color in TRADE_ROUTES:
            from_cont = GLOBE_CONTINENTS.get(from_id)
            to_cont = GLOBE_CONTINENTS.get(to_id)
            if not from_cont or not to_cont:
                continue

            f_lat, f_lon = from_cont["center"]
            t_lat, t_lon = to_cont["center"]

            # Draw arc as series of points
            route_points = []
            n_steps = 20
            for i in range(n_steps + 1):
                t = i / n_steps
                # Interpolate on great circle (simplified as linear for now)
                lat = f_lat + (t_lat - f_lat) * t
                lon = f_lon + (t_lon - f_lon) * t
                # Slight arc lift
                arc_height = math.sin(t * math.pi) * 8
                lat += arc_height

                if self._is_visible(lat, lon):
                    sx, sy, z = self._transform(lat, lon)
                    if sx is not None:
                        route_points.append((sx, sy))
                else:
                    if len(route_points) > 1:
                        faded = tuple(c // 2 for c in route_color)
                        pygame.draw.lines(screen, faded, False, route_points, 1)
                    route_points = []

            if len(route_points) > 1:
                pygame.draw.lines(screen, route_color, False, route_points, 1)

        # Draw hover tooltip
        if self.hovered_city:
            name, cid, sx, sy = self.hovered_city
            cont = GLOBE_CONTINENTS[cid]
            tooltip = f"{name} ({cont['name']})"
            tip_surf = font_md.render(tooltip, True, (255, 255, 200))
            tip_bg = pygame.Surface((tip_surf.get_width() + 12, 24), pygame.SRCALPHA)
            tip_bg.fill((10, 10, 30, 200))
            screen.blit(tip_bg, (sx + 12, sy - 12))
            screen.blit(tip_surf, (sx + 18, sy - 10))

        # === INFO PANEL (left side) ===
        panel_w = 280
        panel_h = 340
        panel_x = 15
        panel_y = SCREEN_HEIGHT // 2 - panel_h // 2

        panel_bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_bg.fill((10, 10, 25, 200))
        screen.blit(panel_bg, (panel_x, panel_y))
        pygame.draw.rect(screen, UI_BORDER, (panel_x, panel_y, panel_w, panel_h), 1)

        py = panel_y + 8
        screen.blit(font_lg.render("Planet Edras", True, UI_HIGHLIGHT), (panel_x + 10, py))
        py += 28
        pygame.draw.line(screen, UI_BORDER, (panel_x + 5, py), (panel_x + panel_w - 5, py))
        py += 8

        # Show selected continent info
        sel = GLOBE_CONTINENTS.get(self.selected_continent, {})
        sel_name = sel.get("name", "Unknown")
        sel_color = sel.get("highlight_color", (200, 200, 200))

        # Continent name with color swatch
        pygame.draw.rect(screen, sel_color, (panel_x + 10, py + 2, 10, 10))
        screen.blit(font_md.render(sel_name, True, sel_color), (panel_x + 26, py))
        py += 20

        # Load continent data from planet module
        from game.world.planet import CONTINENTS as PLANET_DATA
        pdata = PLANET_DATA.get(self.selected_continent, {})

        if pdata:
            # Population
            pop = pdata.get("population", "unknown")
            screen.blit(font_sm.render(f"Pop: {pop}", True, UI_TEXT), (panel_x + 12, py))
            py += 16

            # Climate
            climate = pdata.get("climate", "")[:40]
            screen.blit(font_sm.render(f"Climate: {climate}", True, UI_TEXT), (panel_x + 12, py))
            py += 16

            # Known for
            known = pdata.get("known_for", "")[:38]
            screen.blit(font_sm.render(f"Known for:", True, (150, 150, 170)), (panel_x + 12, py))
            py += 14
            screen.blit(font_sm.render(f"  {known}", True, UI_TEXT), (panel_x + 12, py))
            py += 18

            # Nations
            nations = pdata.get("nations", [])
            screen.blit(font_sm.render(f"Nations ({len(nations)}):", True, (150, 150, 170)),
                       (panel_x + 12, py))
            py += 14
            for nation in nations[:5]:
                # Truncate long names
                display = nation[:35] + "..." if len(nation) > 38 else nation
                screen.blit(font_sm.render(f"  {display}", True, UI_TEXT),
                           (panel_x + 12, py))
                py += 13

            if sel.get("is_playable"):
                py += 6
                screen.blit(font_sm.render("[ YOU ARE HERE ]", True, (100, 255, 100)),
                           (panel_x + panel_w // 2 - 60, py))

        # === CONTROLS HINT (bottom) ===
        controls_y = SCREEN_HEIGHT - 35
        controls = "[Arrows] Rotate  [+/-] Zoom  [Tab] Cycle  [A] Auto-rotate  [M/Esc] Close"
        hint_surf = font_sm.render(controls, True, (120, 120, 140))
        screen.blit(hint_surf, (SCREEN_WIDTH // 2 - hint_surf.get_width() // 2, controls_y))

        # Title
        title = font_lg.render("World of Edras", True, (180, 200, 255))
        screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 15))

        # Two moons with actual phases
        moon_x = SCREEN_WIDTH - 90
        moon_y = 35
        if time_sys:
            lunara_phase = time_sys._astro["lunara_phase"]
            thal_phase = time_sys._astro["thal_phase"]
            lunara_name = time_sys.lunara_phase
            thal_name = time_sys.thal_phase
        else:
            lunara_phase = 0.5
            thal_phase = 0.3
            lunara_name = "full"
            thal_name = "waxing gibbous"

        self._draw_moon(screen, moon_x, moon_y, 14, lunara_phase,
                       (180, 190, 210), (200, 210, 230))
        screen.blit(font_sm.render(f"Lunara ({lunara_name})", True, (150, 160, 180)),
                   (moon_x - 40, moon_y + 18))

        self._draw_moon(screen, moon_x + 45, moon_y + 3, 9, thal_phase,
                       (180, 130, 90), (200, 150, 110))
        screen.blit(font_sm.render(f"Thal ({thal_name})", True, (170, 130, 100)),
                   (moon_x + 10, moon_y + 18 + 14))

        # Conjunction warning
        if time_sys and time_sys.conjunction_near:
            warn_surf = font_md.render("CONJUNCTION!", True, (255, 200, 50))
            screen.blit(warn_surf, (moon_x - 30, moon_y + 50))

        # Season and daylight info
        if time_sys:
            info_y = SCREEN_HEIGHT - 55
            season_str = time_sys.astronomy_string
            info_surf = font_sm.render(season_str, True, (140, 160, 200))
            screen.blit(info_surf, (SCREEN_WIDTH // 2 - info_surf.get_width() // 2, info_y))

    # ================================================================
    # HELPER DRAWING METHODS
    # ================================================================

    def _draw_terminator(self, screen, cx: int, cy: int, r: int, sun_lon: float):
        """Draw day/night shading on the globe. Night side gets a dark overlay."""
        # Create a semi-transparent overlay for the night side
        night_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)

        # The terminator is the line where sun_lon divides day from night
        # Points on the globe where longitude is >90 degrees from sun are in night
        n_points = 40
        night_points = []
        for i in range(n_points + 1):
            lat = -90 + (180 * i / n_points)
            # Night boundary: 90 degrees from the sun
            night_lon = sun_lon + 90
            if self._is_visible(lat, night_lon):
                sx, sy, z = self._transform(lat, night_lon)
                if sx is not None:
                    night_points.append((sx - cx + r + 2, sy - cy + r + 2))

        # Draw the dark half as a filled polygon over the sphere
        if len(night_points) >= 3:
            # Add corners on the night side to complete the polygon
            # Extend to edges of the sphere
            first = night_points[0]
            last = night_points[-1]
            # Add arc along the sphere edge on the night side
            night_points.append((r * 2 + 3, last[1]))
            night_points.append((r * 2 + 3, first[1]))
            try:
                pygame.draw.polygon(night_surf, (0, 0, 20, 80), night_points)
            except (ValueError, pygame.error):
                pass

        screen.blit(night_surf, (cx - r - 2, cy - r - 2))

    def _draw_moon(self, screen, x: int, y: int, radius: int,
                   phase: float, dark_color: tuple, light_color: tuple):
        """Draw a moon with proper phase illumination.
        phase: 0.0 = new moon, 0.25 = first quarter, 0.5 = full, 0.75 = last quarter
        """
        # Draw the full circle as the dark (shadow) side
        pygame.draw.circle(screen, dark_color, (x, y), radius)

        # Draw the illuminated portion
        if phase < 0.01 or phase > 0.99:
            return  # new moon — fully dark

        if 0.49 < phase < 0.51:
            # Full moon — fully lit
            pygame.draw.circle(screen, light_color, (x, y), radius)
            return

        # Partial illumination
        # For phases 0-0.5: right side is lit (waxing)
        # For phases 0.5-1.0: left side is lit (waning)
        for dy in range(-radius, radius + 1):
            # Width of the sphere at this y
            if abs(dy) > radius:
                continue
            half_width = math.sqrt(max(0, radius * radius - dy * dy))
            if half_width < 1:
                continue

            # Terminator position (how much is lit)
            if phase < 0.5:
                # Waxing: right side lit, terminator moves right to left
                t = phase * 2  # 0 to 1
                term_x = half_width * (1 - 2 * t)  # starts at half_width, moves to -half_width
                # Lit from term_x to half_width
                x1 = int(x + term_x)
                x2 = int(x + half_width)
            else:
                # Waning: left side lit, terminator moves left to right
                t = (phase - 0.5) * 2  # 0 to 1
                term_x = -half_width * (1 - 2 * t)  # starts at -half_width, moves to half_width
                # Lit from -half_width to term_x
                x1 = int(x - half_width)
                x2 = int(x + term_x)

            if x2 > x1:
                pygame.draw.line(screen, light_color, (x1, y + dy), (x2, y + dy))
