"""Visual effects — weather, particles, spells, night, seasons."""

import pygame
import random
import math
import time
from typing import Optional
from game.settings import *
from game.world.camera import Camera


class RendererEffectsMixin:

    """Mixin — see parent class for context."""

    def _build_seasonal_color_cache(self):
        """Generate seasonal color variants for terrain types.

        Maps (terrain_type, season) -> color tuple for terrain types
        that change visually with the seasons.
        """
        base = TERRAIN_COLORS

        # --- SPRING: bright greens, flowers ---
        self._seasonal_color_cache[(GRASS, "spring")] = (100, 180, 80)
        self._seasonal_color_cache[(FOREST, "spring")] = (60, 140, 55)
        self._seasonal_color_cache[(DENSE_FOREST, "spring")] = (40, 105, 38)
        self._seasonal_color_cache[(FARMLAND, "spring")] = (110, 170, 65)
        self._seasonal_color_cache[(MARSH, "spring")] = (75, 140, 75)
        self._seasonal_color_cache[(WATER, "spring")] = (45, 135, 190)
        self._seasonal_color_cache[(SHALLOW_WATER, "spring")] = (85, 160, 200)

        # --- SUMMER: deep greens, yellowing ---
        self._seasonal_color_cache[(GRASS, "summer")] = (95, 145, 60)
        self._seasonal_color_cache[(FOREST, "summer")] = (45, 110, 40)
        self._seasonal_color_cache[(DENSE_FOREST, "summer")] = (28, 75, 25)
        self._seasonal_color_cache[(FARMLAND, "summer")] = (130, 150, 55)
        self._seasonal_color_cache[(MARSH, "summer")] = (65, 105, 55)

        # --- AUTUMN: orange/red/gold forests, brown grass ---
        self._seasonal_color_cache[(GRASS, "autumn")] = (140, 130, 65)
        self._seasonal_color_cache[(FOREST, "autumn")] = (160, 95, 35)
        self._seasonal_color_cache[(DENSE_FOREST, "autumn")] = (130, 70, 25)
        self._seasonal_color_cache[(FARMLAND, "autumn")] = (150, 130, 55)
        self._seasonal_color_cache[(MARSH, "autumn")] = (95, 100, 50)
        self._seasonal_color_cache[(FRUIT_TREE, "autumn")] = (170, 90, 40)
        self._seasonal_color_cache[(HERB_PATCH, "autumn")] = (100, 110, 50)
        self._seasonal_color_cache[(FLOWER_BED, "autumn")] = (140, 100, 70)

        # --- WINTER: white/gray on grass/forest, frozen water ---
        self._seasonal_color_cache[(GRASS, "winter")] = (170, 175, 160)
        self._seasonal_color_cache[(FOREST, "winter")] = (130, 130, 120)
        self._seasonal_color_cache[(DENSE_FOREST, "winter")] = (100, 100, 90)
        self._seasonal_color_cache[(FARMLAND, "winter")] = (150, 145, 130)
        self._seasonal_color_cache[(MARSH, "winter")] = (120, 130, 120)
        self._seasonal_color_cache[(WATER, "winter")] = (100, 160, 210)
        self._seasonal_color_cache[(SHALLOW_WATER, "winter")] = (140, 180, 215)
        self._seasonal_color_cache[(FRUIT_TREE, "winter")] = (110, 105, 95)
        self._seasonal_color_cache[(HERB_PATCH, "winter")] = (130, 135, 120)
        self._seasonal_color_cache[(FLOWER_BED, "winter")] = (160, 155, 145)

        # --- Crop tiles (WHEAT_FIELD, VEGETABLE_PLOT) seasonal variants ---
        self._seasonal_color_cache[(WHEAT_FIELD, "spring")] = (150, 165, 60)
        self._seasonal_color_cache[(WHEAT_FIELD, "summer")] = (190, 175, 65)
        self._seasonal_color_cache[(WHEAT_FIELD, "autumn")] = (200, 180, 70)
        self._seasonal_color_cache[(WHEAT_FIELD, "winter")] = (140, 135, 110)
        self._seasonal_color_cache[(VEGETABLE_PLOT, "spring")] = (75, 170, 60)
        self._seasonal_color_cache[(VEGETABLE_PLOT, "summer")] = (70, 155, 55)
        self._seasonal_color_cache[(VEGETABLE_PLOT, "autumn")] = (100, 130, 50)
        self._seasonal_color_cache[(VEGETABLE_PLOT, "winter")] = (130, 130, 110)
        self._seasonal_color_cache[(TILLED_SOIL, "spring")] = (105, 90, 55)
        self._seasonal_color_cache[(TILLED_SOIL, "summer")] = (100, 85, 50)
        self._seasonal_color_cache[(TILLED_SOIL, "autumn")] = (110, 95, 60)
        self._seasonal_color_cache[(TILLED_SOIL, "winter")] = (130, 120, 100)

    def _build_seasonal_tile_cache(self, season: str):
        """Build pre-rendered tile surfaces for a given season.

        Only generates tiles for terrain types that have seasonal color
        variants. Other terrain types fall through to the default cache.
        """
        # Clear old seasonal cache
        self._seasonal_tile_cache = {}

        affected_types = set()
        for (tt, s) in self._seasonal_color_cache:
            if s == season:
                affected_types.add(tt)

        for terrain_type in affected_types:
            key = (terrain_type, season)
            color = self._seasonal_color_cache.get(key)
            if not color:
                continue

            surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
            r, g, b = color
            surf.fill(color)

            # Replicate terrain texture detail with seasonal colors
            if terrain_type == GRASS:
                # Grass blades
                for i in range(4):
                    x = (hash((i * 7 + terrain_type)) % (TILE_SIZE - 2)) + 1
                    y = (hash((i * 13 + terrain_type)) % (TILE_SIZE - 2)) + 1
                    blade_color = (max(0, r - 15), min(255, g + 10), max(0, b - 10))
                    pygame.draw.line(surf, blade_color, (x, y), (x, y + 2))
                # Spring: add flower dots
                if season == "spring":
                    flower_colors = [(220, 100, 120), (240, 220, 80), (180, 100, 220), (100, 180, 230)]
                    for i in range(2):
                        fx = (hash(i * 31 + 5) % (TILE_SIZE - 2)) + 1
                        fy = (hash(i * 37 + 9) % (TILE_SIZE - 2)) + 1
                        fc = flower_colors[hash(i * 41) % len(flower_colors)]
                        surf.set_at((fx, fy), fc)
                # Winter: add white snow speckles
                elif season == "winter":
                    for i in range(5):
                        sx = hash(i * 19 + 3) % TILE_SIZE
                        sy = hash(i * 23 + 7) % TILE_SIZE
                        pygame.draw.circle(surf, (240, 242, 248), (sx, sy), 1)

            elif terrain_type == FOREST:
                # Ground cover
                for i in range(6):
                    gx = (hash(i * 11 + 1) % (TILE_SIZE - 2)) + 1
                    gy = (hash(i * 17 + 3) % (TILE_SIZE - 2)) + 1
                    pygame.draw.circle(surf, (max(0, r - 8), min(255, g + 5), max(0, b - 3)),
                                       (gx, gy), 1)
                cx, cy = TILE_SIZE // 2, TILE_SIZE // 2
                if season == "winter":
                    # Bare tree: visible trunk, minimal canopy
                    pygame.draw.rect(surf, (75, 50, 30), (cx - 2, cy - 2, 4, 10))
                    # Sparse branches
                    pygame.draw.line(surf, (85, 60, 35), (cx, cy - 1), (cx - 4, cy - 4))
                    pygame.draw.line(surf, (85, 60, 35), (cx, cy), (cx + 4, cy - 3))
                    # Snow on branches
                    pygame.draw.circle(surf, (230, 235, 242), (cx - 3, cy - 4), 1)
                    pygame.draw.circle(surf, (230, 235, 242), (cx + 3, cy - 3), 1)
                else:
                    # Normal tree with seasonal canopy color
                    pygame.draw.rect(surf, (75, 50, 30), (cx - 2, cy + 2, 4, 7))
                    pygame.draw.circle(surf, (max(0, r - 15), g, max(0, b - 8)), (cx, cy - 2), 7)
                    pygame.draw.circle(surf, (max(0, r - 5), min(255, g + 15), max(0, b - 3)),
                                       (cx - 1, cy - 3), 6)
                    if season == "autumn":
                        # Add scattered orange/red dots on canopy
                        for i in range(3):
                            dx = (hash(i * 7 + 99) % 10) - 5 + cx
                            dy = (hash(i * 11 + 77) % 8) - 5 + cy
                            dot_c = [(200, 80, 30), (220, 160, 40), (180, 50, 30)][i % 3]
                            if 0 <= dx < TILE_SIZE and 0 <= dy < TILE_SIZE:
                                surf.set_at((dx, dy), dot_c)

            elif terrain_type == DENSE_FOREST:
                trees = [(5, 5, 5), (11, 4, 6), (8, 12, 5), (14, 11, 4)]
                if season == "winter":
                    # Bare trees with snow
                    for ox, oy, tr in trees:
                        if ox < TILE_SIZE and oy < TILE_SIZE:
                            pygame.draw.rect(surf, (55, 35, 22), (ox, oy, 2, 6))
                            pygame.draw.line(surf, (65, 45, 30), (ox, oy), (ox - 3, oy - 3))
                            pygame.draw.line(surf, (65, 45, 30), (ox + 1, oy + 1), (ox + 4, oy - 2))
                    for i in range(6):
                        sx_s = hash(i * 17 + 5) % TILE_SIZE
                        sy_s = hash(i * 23 + 9) % TILE_SIZE
                        pygame.draw.circle(surf, (235, 238, 245), (sx_s, sy_s), 1)
                else:
                    for ox, oy, tr in trees:
                        if ox < TILE_SIZE and oy < TILE_SIZE:
                            pygame.draw.rect(surf, (55, 35, 22), (ox, oy + tr, 2, 4))
                            pygame.draw.circle(surf, (max(0, r - 8), min(255, g + 8), max(0, b - 5)),
                                               (ox, oy), tr)

            elif terrain_type in (WATER, SHALLOW_WATER):
                # Frozen/shifted water
                surf.fill(color)
                if season == "winter":
                    # Ice cracks
                    for i in range(3):
                        ix = (hash(i * 13 + 1) % (TILE_SIZE - 4)) + 2
                        iy = (hash(i * 17 + 3) % (TILE_SIZE - 4)) + 2
                        pygame.draw.line(surf, (min(255, r + 20), min(255, g + 15), min(255, b + 10)),
                                         (ix, iy), (ix + 3, iy + 2))
                else:
                    # Wave pattern with seasonal tint
                    for i in range(3):
                        y_pos = 5 + i * 5
                        wave_color = (min(255, r + 25), min(255, g + 25), min(255, b + 25))
                        for px in range(TILE_SIZE):
                            offset = (px * 3 + i * 7) % 4
                            if offset < 2:
                                surf.set_at((px, y_pos), wave_color)

            elif terrain_type == FARMLAND:
                for i in range(2, TILE_SIZE - 2, 4):
                    pygame.draw.line(surf, (max(0, r - 15), max(0, g - 15), max(0, b - 10)),
                                     (i, 2), (i, TILE_SIZE - 2))
                if season == "winter":
                    for i in range(4):
                        sx_s = hash(i * 19 + 7) % TILE_SIZE
                        sy_s = hash(i * 23 + 11) % TILE_SIZE
                        surf.set_at((sx_s, sy_s), (230, 233, 238))

            elif terrain_type == MARSH:
                for i in range(4):
                    wx = (hash(i * 9 + 1) % (TILE_SIZE - 4)) + 2
                    wy = (hash(i * 15 + 3) % (TILE_SIZE - 4)) + 2
                    if season == "winter":
                        pygame.draw.circle(surf, (140, 155, 170), (wx, wy), 3)
                    else:
                        pygame.draw.circle(surf, (max(0, r - 10), max(0, g - 8), max(0, b + 10)),
                                           (wx, wy), 3)

            elif terrain_type == FRUIT_TREE:
                cx, cy = TILE_SIZE // 2, TILE_SIZE // 2
                if season == "winter":
                    pygame.draw.rect(surf, (80, 50, 30), (cx - 1, cy + TILE_SIZE // 6, 2, TILE_SIZE // 4))
                    pygame.draw.line(surf, (85, 60, 35), (cx, cy - 1), (cx - 3, cy - 4))
                    pygame.draw.line(surf, (85, 60, 35), (cx, cy), (cx + 3, cy - 3))
                elif season == "autumn":
                    pygame.draw.circle(surf, (160, 85, 35), (cx, cy - 2), TILE_SIZE // 3)
                    pygame.draw.rect(surf, (80, 50, 30), (cx - 1, cy + TILE_SIZE // 6, 2, TILE_SIZE // 4))
                    pygame.draw.circle(surf, (200, 50, 40), (cx - 2, cy - 3), max(1, TILE_SIZE // 10))
                    pygame.draw.circle(surf, (200, 50, 40), (cx + 3, cy - 1), max(1, TILE_SIZE // 10))
                else:
                    pygame.draw.circle(surf, (min(255, r + 10), min(255, g + 20), min(255, b + 10)),
                                       (cx, cy - 2), TILE_SIZE // 3)
                    pygame.draw.rect(surf, (80, 50, 30), (cx - 1, cy + TILE_SIZE // 6, 2, TILE_SIZE // 4))

            elif terrain_type == HERB_PATCH:
                for i in range(4):
                    px_h = (hash(i * 11) % (TILE_SIZE - 2)) + 1
                    py_h = TILE_SIZE // 2 + (hash(i * 17) % (TILE_SIZE // 2))
                    pygame.draw.line(surf, (max(0, r - 20), min(255, g + 10), max(0, b - 10)),
                                     (px_h, py_h), (px_h, py_h - TILE_SIZE // 4))

            elif terrain_type == FLOWER_BED:
                if season == "winter":
                    # Dead flowers, brown
                    for i in range(4):
                        fx = (hash(i * 7) % (TILE_SIZE - 4)) + 2
                        fy = (hash(i * 13) % (TILE_SIZE - 4)) + 2
                        pygame.draw.circle(surf, (130, 115, 95), (fx, fy), max(1, TILE_SIZE // 8))
                elif season == "autumn":
                    colors = [(180, 100, 50), (160, 80, 40), (140, 90, 60), (170, 120, 50)]
                    for i, fc in enumerate(colors):
                        fx = (hash(i * 7) % (TILE_SIZE - 4)) + 2
                        fy = (hash(i * 13) % (TILE_SIZE - 4)) + 2
                        pygame.draw.circle(surf, fc, (fx, fy), max(1, TILE_SIZE // 8))
                else:
                    # Spring: extra vibrant flowers
                    colors = [(230, 80, 100), (240, 230, 80), (170, 80, 220), (80, 170, 230)]
                    for i, fc in enumerate(colors):
                        fx = (hash(i * 7) % (TILE_SIZE - 4)) + 2
                        fy = (hash(i * 13) % (TILE_SIZE - 4)) + 2
                        pygame.draw.circle(surf, fc, (fx, fy), max(1, TILE_SIZE // 8))

            self._seasonal_tile_cache[(terrain_type, season)] = surf

    def set_season(self, season: str):
        """Update the current season and rebuild tile caches if needed."""
        if season == self._current_season:
            return
        self._last_season = self._current_season
        self._current_season = season
        self._build_seasonal_tile_cache(season)
        # Clear the dimmed cache so it picks up new seasonal tiles
        if hasattr(self, '_dimmed_cache'):
            self._dimmed_cache = {}

    def _get_seasonal_tile(self, terrain_type: int) -> Optional[pygame.Surface]:
        """Get the seasonal variant of a tile, or None to use default."""
        key = (terrain_type, self._current_season)
        return self._seasonal_tile_cache.get(key)

    def draw_night_overlay(self, darkness: float):
        """Legacy wrapper — converts darkness to normalized time, delegates to draw_lighting."""
        if darkness <= 0:
            return
        # Approximate a normalized time from darkness: full dark -> midnight (0.0)
        # This keeps backward compat while using the smooth transition path.
        if darkness >= 0.99:
            approx_time = 0.0  # midnight
        elif darkness > 0:
            # Dusk range: map darkness 0->1 to time 0.75->0.833
            approx_time = 0.75 + darkness * 0.083
        else:
            approx_time = 0.5  # noon
        self.draw_lighting(approx_time)

    def draw_particles(self, camera: Camera, dt: float, player=None):
        """Update and draw particle effects (core + ambient effects)."""
        # Cap total particles for performance
        if len(self.particles) > 100:
            self.particles = self.particles[-100:]

        # Player position for distance culling
        px = getattr(player, 'x', 0) if player else 0
        py = getattr(player, 'y', 0) if player else 0

        # --- Core particles ---
        remaining = []
        for p in self.particles:
            p["life"] -= dt
            if p["life"] <= 0:
                continue

            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += p.get("gravity", 0) * dt

            sx, sy = camera.world_to_screen(p["x"], p["y"])
            # Skip off-screen particles
            if not (-20 < sx < SCREEN_WIDTH + 20 and -20 < sy < SCREEN_HEIGHT + 20):
                remaining.append(p)
                continue

            alpha = int(255 * (p["life"] / p["max_life"]))
            color = (*p["color"], min(255, alpha))

            size = max(1, int(p["size"] * (p["life"] / p["max_life"])))
            surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (size, size), size)
            self.screen.blit(surf, (int(sx) - size, int(sy) - size))

            remaining.append(p)
        self.particles = remaining

        # --- Ambient visual effects (distance-culled) ---
        self._update_smoke_particles(camera, dt, px, py)
        self._update_birds(camera, dt)
        self._update_damage_popups(camera, dt)
        self._update_swing_arcs(camera, dt)
        self._update_leaf_particles(camera, dt, px, py)
        self._update_water_ripples(camera, dt, px, py)

    # ================================================================
    # WEATHER VISUAL EFFECTS
    # ================================================================

    def draw_weather(self, weather_condition: str, camera: Camera, dt: float):
        """Draw weather visual effects: rain, snow, fog, storm.

        Call after world render, before UI.
        """
        self._weather_condition = weather_condition
        self._fog_offset += dt * 0.5  # slow animation for fog

        if weather_condition == "clear" or weather_condition == "cloudy":
            # Cloudy: slight darkening
            if weather_condition == "cloudy":
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                overlay.fill((30, 30, 40, 25))
                self.screen.blit(overlay, (0, 0))
            self._weather_particles.clear()
            return

        if weather_condition in ("rain", "heavy_rain"):
            self._draw_rain(weather_condition, camera, dt)
        elif weather_condition == "snow":
            self._draw_snow(camera, dt)
        elif weather_condition == "fog":
            self._draw_fog(dt)
        elif weather_condition == "storm":
            self._draw_storm(camera, dt)

    def spawn_death_effect(self, x: float, y: float):
        """Spawn death effect particles (gray dust rising)."""
        for _ in range(10):
            angle = math.radians(random.randint(0, 360))
            speed = random.uniform(0.3, 1.5)
            gray = random.randint(100, 180)
            self.particles.append({
                "x": x + random.uniform(-0.3, 0.3),
                "y": y + random.uniform(-0.3, 0.3),
                "vx": math.cos(angle) * speed,
                "vy": -random.uniform(0.5, 2.0),
                "gravity": -0.5,  # float upward
                "color": (gray, gray, gray),
                "size": random.randint(2, 4),
                "life": random.uniform(0.8, 1.5),
                "max_life": 1.5,
            })

    # ================================================================
    # LEAF PARTICLES — blowing in forest areas
    # ================================================================

    def spawn_hit_particles(self, x: float, y: float, color=(255, 50, 50)):
        """Spawn particles at a hit location."""
        for _ in range(8):
            angle = math.radians(random.randint(0, 360))
            speed = random.uniform(1, 4)
            self.particles.append({
                "x": x, "y": y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed - 2,
                "gravity": 5,
                "color": color,
                "size": random.randint(2, 4),
                "life": random.uniform(0.3, 0.8),
                "max_life": 0.8,
            })
        # Also spawn blood splatter and damage popup
        self.spawn_blood_splatter(x, y)

    def spawn_xp_particles(self, x: float, y: float):
        """Spawn gold/XP particles."""
        for _ in range(5):
            self.particles.append({
                "x": x + random.uniform(-0.3, 0.3),
                "y": y + random.uniform(-0.3, 0.3),
                "vx": random.uniform(-0.5, 0.5),
                "vy": -random.uniform(1, 3),
                "gravity": 0,
                "color": (255, 220, 50),
                "size": random.randint(2, 3),
                "life": random.uniform(0.5, 1.0),
                "max_life": 1.0,
            })

    # ================================================================
    # COMBAT POLISH: SCREEN SHAKE
    # ================================================================

    def spawn_spell_effect(self, spell_name: str, x: float, y: float,
                           target_x: float = None, target_y: float = None):
        """Spawn a visual spell effect at the given position.

        Args:
            spell_name: Name of the spell (fireball, ice_shard, lightning_bolt, heal, etc.)
            x, y: Origin position (caster).
            target_x, target_y: Target position (optional, for projectile effects).
        """
        tx = target_x if target_x is not None else x
        ty = target_y if target_y is not None else y

        if spell_name == "fireball":
            self._spawn_fireball_effect(tx, ty)
        elif spell_name in ("ice_shard", "ice_wall", "frost_nova",
                             "ice_storm", "cone_of_cold", "ray_of_frost"):
            self._spawn_ice_effect(tx, ty)
        elif spell_name in ("lightning_bolt", "chain_lightning",
                             "thunderwave"):
            self._spawn_lightning_effect(x, y, tx, ty)
        elif spell_name in ("heal", "mass_heal", "greater_heal",
                             "restoration"):
            self._spawn_heal_effect(tx, ty)
        else:
            # Check for extended elemental types via elemental_renderer
            from game.ui.elemental_renderer import get_spell_particle_colors
            colors = get_spell_particle_colors(spell_name)
            if colors:
                self._spawn_colored_spell_effect(tx, ty, colors)
            else:
                # Generic spell effect using spell school colors
                self._spawn_generic_spell_effect(spell_name, tx, ty)

    def _spawn_colored_spell_effect(self, x, y, colors):
        """Spawn particles with custom colors at (x, y)."""
        for _ in range(8):
            self.particles.append({
                "x": x + random.uniform(-0.5, 0.5),
                "y": y + random.uniform(-0.5, 0.5),
                "vx": random.uniform(-1.5, 1.5),
                "vy": random.uniform(-2.5, 0),
                "color": random.choice(colors),
                "life": random.uniform(0.4, 1.0),
                "size": random.randint(2, 4),
            })


