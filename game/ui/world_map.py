"""
World Map View — full-screen zoomable/scrollable map of the game world.

Shows terrain, roads, buildings, settlement labels, and player position.
Game is paused while viewing. Currently in "cheat mode" — reveals everything.

Controls:
  Arrow keys / WASD: scroll
  +/- or mouse wheel: zoom in/out
  Home: center on player
  F / ESC / M: close map
"""

import pygame
import math
from game.settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE,
    TERRAIN_COLORS, ROAD, GRAVEL_ROAD, BRIDGE, FLOOR, WALL, DOOR,
    WATER, GRASS, FOREST, DENSE_FOREST, MOUNTAIN, SNOW, SAND,
    SWAMP, FARMLAND, BUILT_WALL, BUILT_FLOOR, COBBLESTONE,
    DIRT_TRACK, MOUNTAIN_PASS, STABLE_FLOOR,
    WHITE, BLACK, YELLOW, RED, GREEN, UI_BORDER, UI_HIGHLIGHT, UI_TEXT,
)


# Zoom levels: pixels per tile
# At 0.064 px/tile, 10,000 tiles = 640px — fits on 1280px screen
ZOOM_LEVELS = [0.064, 0.1, 0.15, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0]
DEFAULT_ZOOM_INDEX = 6  # 1.0 px/tile


class WorldMapView:
    """Interactive full-screen world map."""

    def __init__(self):
        self.active = False

        # View state
        self.cam_x = 0.0  # center of view in world tiles
        self.cam_y = 0.0
        self.zoom_index = DEFAULT_ZOOM_INDEX
        self.zoom = ZOOM_LEVELS[self.zoom_index]  # pixels per tile

        # Pre-rendered full map at 1:1 (1 pixel per tile) — built once
        self._full_map_surface = None  # pygame.Surface (world_w x world_h)

        # Cached scaled surface for current zoom
        self._cached_surface = None
        self._cached_zoom = -1
        self._cached_region = None

        # Scroll speed (tiles per second)
        self.scroll_speed = 200.0

        # Fonts
        self._fonts_initialized = False
        self.font_sm = None
        self.font_md = None
        self.font_lg = None
        self.font_title = None

        # Label cache
        self._label_cache = {}

        # Weather overlay
        self._weather_overlay_mode = None  # None, "pressure", "temperature", "wind"
        self._climate_ref = None  # set externally by main.py

        # Travel mode
        self.travel_target = None  # settlement dict if travel selected
        self.travel_result = None  # TravelResult pending confirmation

    def _init_fonts(self):
        if not self._fonts_initialized:
            self.font_sm = pygame.font.SysFont("monospace", 10)
            self.font_md = pygame.font.SysFont("monospace", 13)
            self.font_lg = pygame.font.SysFont("monospace", 16)
            self.font_title = pygame.font.SysFont("monospace", 22, bold=True)
            self._fonts_initialized = True

    def open(self, player_x: float, player_y: float):
        """Open the map centered on the player."""
        self.active = True
        self.cam_x = player_x
        self.cam_y = player_y
        self._cached_surface = None

    def close(self):
        """Close the map."""
        self.active = False
        self._cached_surface = None
        self._label_cache.clear()

    def handle_input(self, key) -> bool:
        """Handle keyboard input. Returns True if map should close.

        Returns 'travel' string if player confirmed fast-travel.
        """
        if self.travel_result:
            # Travel confirmation mode
            if key == pygame.K_RETURN or key == pygame.K_y:
                result = self.travel_result
                self.travel_result = None
                self.travel_target = None
                self.close()
                return result  # return the TravelResult to the game
            elif key in (pygame.K_ESCAPE, pygame.K_n):
                self.travel_result = None
                self.travel_target = None
                return False

        if key in (pygame.K_ESCAPE, pygame.K_f, pygame.K_m):
            self.close()
            return True

        # Zoom
        if key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self._zoom_in()
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._zoom_out()

        # Center on player
        if key == pygame.K_HOME:
            pass

        # Weather overlay toggle (T key cycles: off -> pressure -> temperature -> wind -> off)
        if key == pygame.K_t:
            modes = [None, "pressure", "temperature", "wind"]
            cur_idx = 0
            if self._weather_overlay_mode in modes:
                cur_idx = modes.index(self._weather_overlay_mode)
            self._weather_overlay_mode = modes[(cur_idx + 1) % len(modes)]

        return False

    def handle_click(self, mouse_x: int, mouse_y: int, world, player):
        """Handle mouse click on the world map — select travel destination."""
        # Convert screen coords to world coords
        step = getattr(self, '_map_step', 1)
        tiles_visible_x = SCREEN_WIDTH / self.zoom
        tiles_visible_y = SCREEN_HEIGHT / self.zoom
        wx = (self.cam_x - tiles_visible_x / 2) + mouse_x / self.zoom
        wy = (self.cam_y - tiles_visible_y / 2) + mouse_y / self.zoom

        # Find nearest settlement to click
        best_dist = 999999
        best_settlement = None
        for s in world.structures:
            if s.kind not in ("hamlet", "village", "town", "city", "castle"):
                continue
            d = math.sqrt((s.x - wx)**2 + (s.y - wy)**2)
            click_radius = max(20, s.radius) / self.zoom * step
            if d < max(50, s.radius + 20) and d < best_dist:
                best_dist = d
                best_settlement = s

        if best_settlement:
            from game.systems.travel import calculate_travel
            result = calculate_travel(world, player,
                                      best_settlement.x, best_settlement.y,
                                      best_settlement.name)
            self.travel_target = best_settlement
            self.travel_result = result

    def handle_scroll(self, y: int):
        """Handle mouse wheel scroll for zooming."""
        if y > 0:
            self._zoom_in()
        elif y < 0:
            self._zoom_out()

    def _zoom_in(self):
        if self.zoom_index < len(ZOOM_LEVELS) - 1:
            self.zoom_index += 1
            self.zoom = ZOOM_LEVELS[self.zoom_index]
            self._cached_surface = None

    def _zoom_out(self):
        if self.zoom_index > 0:
            self.zoom_index -= 1
            self.zoom = ZOOM_LEVELS[self.zoom_index]
            self._cached_surface = None

    def update_scroll(self, dt: float):
        """Update camera position based on held keys."""
        keys = pygame.key.get_pressed()
        speed = self.scroll_speed / max(0.25, self.zoom)

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.cam_x -= speed * dt
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.cam_x += speed * dt
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.cam_y -= speed * dt
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.cam_y += speed * dt

    def draw(self, screen: pygame.Surface, world, player, structures):
        """Render the full world map."""
        if not self.active:
            return

        self._init_fonts()

        # Clamp camera
        self.cam_x = max(0, min(world.width, self.cam_x))
        self.cam_y = max(0, min(world.height, self.cam_y))

        # Calculate visible area in world tiles
        tiles_visible_x = SCREEN_WIDTH / self.zoom
        tiles_visible_y = SCREEN_HEIGHT / self.zoom

        x0 = int(self.cam_x - tiles_visible_x / 2)
        y0 = int(self.cam_y - tiles_visible_y / 2)
        x1 = int(self.cam_x + tiles_visible_x / 2) + 1
        y1 = int(self.cam_y + tiles_visible_y / 2) + 1

        # Clamp to world
        x0 = max(0, x0)
        y0 = max(0, y0)
        x1 = min(world.width, x1)
        y1 = min(world.height, y1)

        # Background
        screen.fill((8, 8, 15))

        # Ensure full map surface is built (one-time cost)
        if self._full_map_surface is None:
            self._build_full_map(world)

        # Blit the appropriate portion of the map, scaled to current zoom
        self._draw_terrain_from_cache(screen, world, x0, y0, x1, y1)

        # Draw structures (buildings as rectangles)
        self._draw_buildings(screen, world, x0, y0, x1, y1)

        # Draw player position
        self._draw_player_marker(screen, player)

        # Draw settlement labels
        self._draw_labels(screen, structures, x0, y0, x1, y1)

        # Draw weather overlay if active
        if self._weather_overlay_mode and self._climate_ref:
            try:
                from game.systems.climate import draw_weather_overlay
                draw_weather_overlay(screen, self._climate_ref,
                                      self.cam_x, self.cam_y, self.zoom,
                                      self._weather_overlay_mode)
            except Exception:
                pass

        # Draw travel confirmation dialog if active
        if self.travel_result and self.travel_target:
            self._draw_travel_dialog(screen, player)

        # Draw UI overlay (controls, zoom level, coordinates)
        self._draw_overlay(screen)

    def _draw_travel_dialog(self, screen, player):
        """Draw travel confirmation dialog."""
        self._init_fonts()
        t = self.travel_target
        r = self.travel_result

        bw, bh = 400, 160
        bx = SCREEN_WIDTH // 2 - bw // 2
        by = SCREEN_HEIGHT // 2 - bh // 2

        # Background
        surf = pygame.Surface((bw, bh), pygame.SRCALPHA)
        surf.fill((20, 20, 35, 230))
        screen.blit(surf, (bx, by))
        pygame.draw.rect(screen, UI_HIGHLIGHT, (bx, by, bw, bh), 2,
                         border_radius=6)

        # Title
        title = self.font_lg.render(f"Travel to {t.name}?", True, WHITE)
        screen.blit(title, (bx + 20, by + 12))

        # Details
        kind = t.kind.title()
        dist_km = r.distance_tiles * 3 / 1000  # 3m per tile
        hours = r.game_hours_elapsed
        lines = [
            f"Type: {kind}    Distance: {dist_km:.1f} km ({r.distance_tiles:.0f} tiles)",
            f"Travel time: {hours:.1f} game hours ({hours/24:.1f} days)",
        ]
        if r.encounter:
            lines.append(f"Warning: {r.message}")

        y = by + 40
        for line in lines:
            surf = self.font_md.render(line, True, UI_TEXT)
            screen.blit(surf, (bx + 20, y))
            y += 18

        # Prompt
        prompt = self.font_md.render(
            "Enter/Y: Travel    Esc/N: Cancel", True, (180, 200, 140))
        screen.blit(prompt, (bx + 20, by + bh - 30))

        # Highlight target on map
        sx, sy = self._world_to_screen(t.x, t.y)
        pygame.draw.circle(screen, (255, 200, 50), (sx, sy), 8, 2)

    def _world_to_screen(self, wx: float, wy: float) -> tuple:
        """Convert world coordinates to screen pixel coordinates."""
        tiles_visible_x = SCREEN_WIDTH / self.zoom
        tiles_visible_y = SCREEN_HEIGHT / self.zoom
        rel_x = wx - (self.cam_x - tiles_visible_x / 2)
        rel_y = wy - (self.cam_y - tiles_visible_y / 2)
        return (int(rel_x * self.zoom), int(rel_y * self.zoom))

    def _build_full_map(self, world):
        """Build a pixel map of the entire world.

        For chunked worlds (>4000), uses the elevation cache for a
        downsampled map. For small worlds, builds 1:1 from tiles.
        """
        import numpy as np
        from game.world.world import ChunkedWorld

        if isinstance(world, ChunkedWorld):
            self._build_full_map_from_plan(world)
            return

        w, h = world.width, world.height

        # Build color lookup array (max tile type + 1 entries)
        max_tile = max(TERRAIN_COLORS.keys()) + 1
        color_lut = [(40, 40, 40)] * (max_tile + 1)
        for tile_type, color in TERRAIN_COLORS.items():
            if tile_type <= max_tile:
                color_lut[tile_type] = color

        # Convert tiles to numpy array for fast color mapping
        # world.tiles is a list-of-lists for non-chunked worlds
        try:
            tile_array = np.array(world.tiles, dtype=np.int32)
        except (ValueError, TypeError):
            # Fallback: tiles might be a ChunkGrid or other proxy
            tile_array = np.zeros((h, w), dtype=np.int32)
            for y in range(h):
                for x in range(w):
                    try:
                        tile_array[y, x] = int(world.tiles[y][x])
                    except Exception:
                        pass
        # Clamp to valid range
        tile_array = np.clip(tile_array, 0, max_tile)

        # Create RGB array
        rgb = np.zeros((h, w, 3), dtype=np.uint8)
        for tile_type, color in TERRAIN_COLORS.items():
            mask = tile_array == tile_type
            rgb[mask] = color

        # Create pygame surface from array
        self._full_map_surface = pygame.surfarray.make_surface(
            np.ascontiguousarray(rgb.transpose(1, 0, 2))
        )

    def _build_full_map_from_plan(self, world):
        """Build world map from elevation cache (no chunk loading)."""
        import numpy as np

        plan = getattr(world, 'plan', None)
        if plan is None or not hasattr(plan, '_elev_cache'):
            # No plan data — create a blank map
            self._full_map_surface = pygame.Surface((200, 200))
            self._full_map_surface.fill((40, 60, 40))
            return
        elev = plan._elev_cache
        mh, mw = elev.shape

        rgb = np.zeros((mh, mw, 3), dtype=np.uint8)

        # Color from elevation thresholds
        rgb[elev < 0.22] = TERRAIN_COLORS[WATER]
        rgb[(elev >= 0.22) & (elev < 0.28)] = TERRAIN_COLORS[SAND]
        rgb[(elev >= 0.28) & (elev < 0.65)] = TERRAIN_COLORS[GRASS]
        rgb[(elev >= 0.65) & (elev < 0.78)] = TERRAIN_COLORS[MOUNTAIN]
        rgb[elev >= 0.78] = TERRAIN_COLORS[SNOW]

        # Stamp settlement markers — small dots, not area fills
        step = plan._elev_step
        for s in plan.settlements:
            mx, my = s.x // step, s.y // step
            # Just a 1-2 pixel marker, not the full radius
            dot = 1 if s.kind in ("hamlet", "village") else 2
            color = {"city": (220, 180, 60), "town": (200, 170, 80),
                     "village": (180, 160, 100), "hamlet": (160, 150, 110),
                     "castle": (220, 160, 50),
                     }.get(s.kind, (160, 140, 100))
            for dy in range(-dot, dot + 1):
                for dx in range(-dot, dot + 1):
                    px, py = mx + dx, my + dy
                    if 0 <= px < mw and 0 <= py < mh:
                        rgb[py, px] = color

        # Stamp roads
        road_color = np.array(TERRAIN_COLORS[ROAD], dtype=np.uint8)
        for road in plan.roads:
            for wx, wy in road.waypoints:
                mx, my = wx // step, wy // step
                if 0 <= mx < mw and 0 <= my < mh:
                    rgb[my, mx] = road_color

        self._full_map_surface = pygame.surfarray.make_surface(
            np.ascontiguousarray(rgb.transpose(1, 0, 2))
        )
        # Store step for coordinate mapping in draw calls
        self._map_step = step

    def _draw_terrain_from_cache(self, screen, world, x0, y0, x1, y1):
        """Draw terrain by blitting a scaled subsection of the pre-rendered map."""
        if self._full_map_surface is None:
            return

        # For downsampled maps, convert world coords to map coords
        step = getattr(self, '_map_step', 1)
        mx0 = x0 // step
        my0 = y0 // step
        mx1 = max(mx0 + 1, (x1 + step - 1) // step)
        my1 = max(my0 + 1, (y1 + step - 1) // step)

        # Source rectangle on the full map surface
        src_rect = pygame.Rect(mx0, my0, mx1 - mx0, my1 - my0)
        src_rect = src_rect.clip(self._full_map_surface.get_rect())

        if src_rect.width <= 0 or src_rect.height <= 0:
            return

        # Extract subsurface
        sub = self._full_map_surface.subsurface(src_rect)

        # Scale to fill the screen viewport.
        # Each map pixel covers `step` world tiles, each world tile is
        # `self.zoom` screen pixels, so each map pixel becomes
        # step * zoom screen pixels.
        px_per_map = self.zoom * step
        dest_w = int(src_rect.width * px_per_map)
        dest_h = int(src_rect.height * px_per_map)

        if dest_w <= 0 or dest_h <= 0:
            return

        if dest_w < src_rect.width:
            scaled = pygame.transform.smoothscale(sub, (dest_w, dest_h))
        else:
            scaled = pygame.transform.scale(sub, (dest_w, dest_h))

        # Position on screen: align the map-pixel grid with world coordinates.
        # The top-left of the source rect corresponds to world coords
        # (mx0 * step, my0 * step).  Convert that to screen position.
        screen_x0 = int((mx0 * step - self.cam_x) * self.zoom + SCREEN_WIDTH / 2)
        screen_y0 = int((my0 * step - self.cam_y) * self.zoom + SCREEN_HEIGHT / 2)

        screen.blit(scaled, (screen_x0, screen_y0))

    def _draw_buildings(self, screen, world, x0, y0, x1, y1):
        """Draw building outlines (only at high zoom)."""
        if self.zoom < 0.5:
            return  # buildings invisible at overview zoom

        for s in world.structures:
            if s.kind in ("ruins",):
                continue

            for bx, by, bw, bh in getattr(s, 'buildings', []):
                # Check if building is in view
                if bx + bw < x0 or bx > x1 or by + bh < y0 or by > y1:
                    continue

                sx1, sy1 = self._world_to_screen(bx, by)
                sx2, sy2 = self._world_to_screen(bx + bw, by + bh)
                w = max(1, sx2 - sx1)
                h = max(1, sy2 - sy1)

                if sx1 + w < 0 or sy1 + h < 0 or sx1 > SCREEN_WIDTH or sy1 > SCREEN_HEIGHT:
                    continue

                # Building color based on structure type
                if s.kind in ("city", "castle"):
                    outline_color = (180, 160, 100)
                elif s.kind == "town":
                    outline_color = (140, 140, 160)
                elif s.kind == "village":
                    outline_color = (120, 140, 120)
                else:
                    outline_color = (100, 100, 100)

                if self.zoom >= 2.0:
                    pygame.draw.rect(screen, outline_color, (sx1, sy1, w, h), 1)
                elif self.zoom >= 0.5:
                    # Just draw a dot for each building at low zoom
                    cx = sx1 + w // 2
                    cy = sy1 + h // 2
                    if 0 <= cx < SCREEN_WIDTH and 0 <= cy < SCREEN_HEIGHT:
                        screen.set_at((cx, cy), outline_color)

    def _draw_player_marker(self, screen, player):
        """Draw a pulsing marker at the player's position."""
        sx, sy = self._world_to_screen(player.x, player.y)

        if not (0 <= sx < SCREEN_WIDTH and 0 <= sy < SCREEN_HEIGHT):
            # Player is off-screen — draw arrow pointing toward them
            self._draw_offscreen_arrow(screen, sx, sy)
            return

        # Pulsing circle
        import time
        pulse = abs(math.sin(time.time() * 3.0))
        radius = max(3, int(4 + pulse * 4))

        # Outer glow
        glow_color = (50, 150, 255, 100)
        glow_surf = pygame.Surface((radius * 4, radius * 4), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, glow_color, (radius * 2, radius * 2), radius * 2)
        screen.blit(glow_surf, (sx - radius * 2, sy - radius * 2))

        # Inner bright marker
        pygame.draw.circle(screen, (80, 180, 255), (sx, sy), radius)
        pygame.draw.circle(screen, WHITE, (sx, sy), max(1, radius - 2))

        # Label
        label = self.font_md.render("You", True, (80, 180, 255))
        screen.blit(label, (sx - label.get_width() // 2, sy - radius - 14))

    def _draw_offscreen_arrow(self, screen, sx, sy):
        """Draw an arrow at the screen edge pointing toward the player."""
        # Clamp to screen edges with margin
        margin = 30
        ax = max(margin, min(SCREEN_WIDTH - margin, sx))
        ay = max(margin, min(SCREEN_HEIGHT - margin, sy))

        # Draw arrow
        pygame.draw.circle(screen, (80, 180, 255), (ax, ay), 6)
        pygame.draw.circle(screen, WHITE, (ax, ay), 4)

        # Direction line toward actual position
        dx = sx - ax
        dy = sy - ay
        mag = max(1, math.sqrt(dx * dx + dy * dy))
        nx, ny = dx / mag, dy / mag
        end_x = int(ax + nx * 15)
        end_y = int(ay + ny * 15)
        pygame.draw.line(screen, (80, 180, 255), (ax, ay), (end_x, end_y), 2)

    def _draw_labels(self, screen, structures, x0, y0, x1, y1):
        """Draw settlement names and points of interest."""
        for s in structures:
            # Only label significant structures
            if s.kind not in ("village", "town", "city", "castle", "hamlet",
                              "temple", "ruins"):
                continue

            # Check if in view (with generous margin for labels)
            if s.x < x0 - 20 or s.x > x1 + 20 or s.y < y0 - 20 or s.y > y1 + 20:
                continue

            sx, sy = self._world_to_screen(s.x, s.y)
            if sx < -100 or sx > SCREEN_WIDTH + 100 or sy < -50 or sy > SCREEN_HEIGHT + 50:
                continue

            # Choose font and color based on importance
            if s.kind in ("city", "castle"):
                font = self.font_lg
                color = (255, 220, 100)
                marker_size = max(3, int(self.zoom * 2))
                show_at_zoom = 0.25
            elif s.kind == "town":
                font = self.font_md
                color = (200, 200, 220)
                marker_size = max(2, int(self.zoom * 1.5))
                show_at_zoom = 0.35
            elif s.kind == "village":
                font = self.font_md
                color = (160, 200, 160)
                marker_size = max(2, int(self.zoom))
                show_at_zoom = 0.5
            elif s.kind == "hamlet":
                font = self.font_sm
                color = (140, 160, 140)
                marker_size = max(1, int(self.zoom * 0.8))
                show_at_zoom = 0.75
            elif s.kind == "temple":
                font = self.font_sm
                color = (180, 160, 220)
                marker_size = max(2, int(self.zoom))
                show_at_zoom = 0.5
            elif s.kind == "ruins":
                font = self.font_sm
                color = (160, 120, 100)
                marker_size = max(1, int(self.zoom * 0.7))
                show_at_zoom = 1.0
            else:
                continue

            # Only show label if zoomed in enough
            if self.zoom < show_at_zoom:
                continue

            # Draw marker dot
            pygame.draw.circle(screen, color, (sx, sy), marker_size)

            # Draw name label with shadow
            cache_key = (s.name, id(font), color)
            if cache_key not in self._label_cache:
                shadow = font.render(s.name, True, (0, 0, 0))
                label = font.render(s.name, True, color)
                self._label_cache[cache_key] = (label, shadow)
            label, shadow = self._label_cache[cache_key]

            lx = sx - label.get_width() // 2
            ly = sy - marker_size - label.get_height() - 2

            # Background for readability
            bg_rect = pygame.Rect(lx - 2, ly - 1,
                                   label.get_width() + 4, label.get_height() + 2)
            bg = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 140))
            screen.blit(bg, bg_rect)

            screen.blit(shadow, (lx + 1, ly + 1))
            screen.blit(label, (lx, ly))

            # Show settlement type at higher zoom
            if self.zoom >= 2.0 and s.kind not in ("ruins",):
                type_text = f"({s.kind})"
                type_surf = self.font_sm.render(type_text, True,
                                                 (color[0]//2, color[1]//2, color[2]//2))
                screen.blit(type_surf, (sx - type_surf.get_width() // 2,
                                        ly + label.get_height()))

    def _draw_overlay(self, screen):
        """Draw UI overlay with controls and info."""
        # Semi-transparent panel at top
        panel_h = 32
        panel = pygame.Surface((SCREEN_WIDTH, panel_h), pygame.SRCALPHA)
        panel.fill((10, 10, 20, 200))
        screen.blit(panel, (0, 0))

        # Title
        title = self.font_lg.render("WORLD MAP", True, UI_HIGHLIGHT)
        screen.blit(title, (10, 6))

        # Zoom level
        zoom_text = f"Zoom: {self.zoom:.2f}x"
        zoom_surf = self.font_md.render(zoom_text, True, UI_TEXT)
        screen.blit(zoom_surf, (160, 9))

        # Coordinates
        coord_text = f"({int(self.cam_x)}, {int(self.cam_y)})"
        coord_surf = self.font_md.render(coord_text, True, UI_TEXT)
        screen.blit(coord_surf, (330, 9))

        # Weather overlay indicator
        if self._weather_overlay_mode:
            weather_label = f"Weather: {self._weather_overlay_mode.title()}"
            weather_surf = self.font_md.render(weather_label, True, (200, 180, 100))
            screen.blit(weather_surf, (490, 9))

        # Controls
        controls = "WASD:Scroll  +/-:Zoom  T:Weather  Home:Center  F/Esc:Close"
        ctrl_surf = self.font_sm.render(controls, True, (160, 160, 170))
        screen.blit(ctrl_surf, (SCREEN_WIDTH - ctrl_surf.get_width() - 10, 11))

        # Bottom panel with legend
        legend_h = 24
        legend = pygame.Surface((SCREEN_WIDTH, legend_h), pygame.SRCALPHA)
        legend.fill((10, 10, 20, 180))
        screen.blit(legend, (0, SCREEN_HEIGHT - legend_h))

        items = [
            ((255, 220, 100), "City/Castle"),
            ((200, 200, 220), "Town"),
            ((160, 200, 160), "Village"),
            ((140, 160, 140), "Hamlet"),
            ((180, 160, 220), "Temple"),
            ((160, 120, 100), "Ruins"),
            ((80, 180, 255), "You"),
        ]
        lx = 10
        for color, name in items:
            pygame.draw.circle(screen, color,
                              (lx + 5, SCREEN_HEIGHT - legend_h + legend_h // 2), 4)
            lbl = self.font_sm.render(name, True, color)
            screen.blit(lbl, (lx + 12, SCREEN_HEIGHT - legend_h + 5))
            lx += lbl.get_width() + 24

        # Scale bar (bottom right)
        if self.zoom > 0:
            # 1 tile = 75 meters
            tile_meters = 75
            # Find a nice round distance for the scale bar
            bar_px = 100  # target pixel width
            bar_tiles = bar_px / self.zoom
            bar_meters = bar_tiles * tile_meters

            # Round to nice number
            if bar_meters > 10000:
                nice = int(bar_meters / 5000) * 5000
            elif bar_meters > 1000:
                nice = int(bar_meters / 1000) * 1000
            elif bar_meters > 100:
                nice = int(bar_meters / 100) * 100
            else:
                nice = max(10, int(bar_meters / 10) * 10)

            actual_px = int(nice / tile_meters * self.zoom)
            if nice >= 1000:
                scale_text = f"{nice // 1000} km"
            else:
                scale_text = f"{nice} m"

            bx = SCREEN_WIDTH - actual_px - 20
            by = SCREEN_HEIGHT - legend_h - 20

            pygame.draw.line(screen, WHITE, (bx, by), (bx + actual_px, by), 2)
            pygame.draw.line(screen, WHITE, (bx, by - 3), (bx, by + 3), 1)
            pygame.draw.line(screen, WHITE, (bx + actual_px, by - 3),
                            (bx + actual_px, by + 3), 1)

            scale_surf = self.font_sm.render(scale_text, True, WHITE)
            screen.blit(scale_surf, (bx + actual_px // 2 - scale_surf.get_width() // 2,
                                      by - 14))
