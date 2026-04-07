"""Ambient particle effects — atmospheric visual details.

Provides lightweight screen-space particles for atmosphere:
- Falling leaves (autumn, forest biome)
- Fireflies (night, swamp/forest)
- Dust motes (indoor/desert)
- Snow ground accumulation (winter)
- Stars (clear night sky)

Wire into the main render loop: call update() then draw() each frame,
after terrain but before entities.
"""

import random
import math
import pygame
from typing import List, Optional
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT


class AmbientParticleSystem:
    """Manages atmospheric screen-space particles."""

    def __init__(self):
        self._leaves: List[dict] = []
        self._fireflies: List[dict] = []
        self._dust: List[dict] = []
        self._snow_accum: List[dict] = []
        self._stars: List[dict] = []

        # Timers for spawn throttling
        self._leaf_spawn_t = 0.0
        self._firefly_spawn_t = 0.0
        self._dust_spawn_t = 0.0
        self._star_init = False

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def update(self, dt: float, season: str = "summer",
               is_night: bool = False, biome: str = "grass",
               weather: str = "clear", is_indoor: bool = False):
        """Tick all ambient particle subsystems.

        Args:
            dt: frame delta in seconds.
            season: "spring", "summer", "autumn", "winter".
            is_night: True if darkness > 0.3.
            biome: dominant biome around the player ("grass", "forest",
                   "swamp", "desert", "snow", etc.).
            weather: current weather condition.
            is_indoor: True if player is inside a building.
        """
        self._update_leaves(dt, season, biome)
        self._update_fireflies(dt, is_night, biome)
        self._update_dust(dt, is_indoor, biome)
        self._update_snow_accum(dt, season, weather)
        self._update_stars(dt, is_night, weather)

    def draw(self, screen: pygame.Surface):
        """Render all active ambient particles to the screen."""
        self._draw_stars(screen)
        self._draw_leaves(screen)
        self._draw_fireflies(screen)
        self._draw_dust(screen)
        self._draw_snow_accum(screen)

    # ----------------------------------------------------------------
    # LEAVES (autumn / forest)
    # ----------------------------------------------------------------

    def _update_leaves(self, dt: float, season: str, biome: str):
        """Spawn and move falling leaf particles."""
        show = (season == "autumn" and biome in ("forest", "dense_forest"))
        max_count = 10 if show else 0

        if show:
            self._leaf_spawn_t += dt
            if self._leaf_spawn_t >= 0.6 and len(self._leaves) < max_count:
                self._leaf_spawn_t = 0.0
                self._leaves.append(self._make_leaf())

        alive = []
        for p in self._leaves:
            p["life"] -= dt
            if p["life"] <= 0:
                continue
            # Wobble horizontally
            p["wobble_phase"] += dt * 2.5
            p["x"] += (p["vx"] + math.sin(p["wobble_phase"]) * 12) * dt
            p["y"] += p["vy"] * dt
            if p["y"] > SCREEN_HEIGHT + 5:
                continue
            alive.append(p)
        self._leaves = alive

    def _make_leaf(self) -> dict:
        colors = [(180, 90, 30), (200, 120, 40), (160, 60, 25),
                  (190, 140, 40), (170, 80, 20)]
        return {
            "x": random.uniform(0, SCREEN_WIDTH),
            "y": random.uniform(-10, SCREEN_HEIGHT * 0.3),
            "vx": random.uniform(8, 25),
            "vy": random.uniform(12, 30),
            "wobble_phase": random.uniform(0, 6.28),
            "color": random.choice(colors),
            "size": random.randint(2, 3),
            "life": random.uniform(4, 8),
        }

    def _draw_leaves(self, screen: pygame.Surface):
        for p in self._leaves:
            alpha = min(255, int(255 * min(1.0, p["life"] / 1.5)))
            s = p["size"]
            surf = pygame.Surface((s, s), pygame.SRCALPHA)
            surf.fill((*p["color"], alpha))
            screen.blit(surf, (int(p["x"]), int(p["y"])))

    # ----------------------------------------------------------------
    # FIREFLIES (night, swamp/forest)
    # ----------------------------------------------------------------

    def _update_fireflies(self, dt: float, is_night: bool, biome: str):
        """Spawn and move firefly particles."""
        show = is_night and biome in ("forest", "dense_forest", "swamp")
        max_count = 8 if show else 0

        if show:
            self._firefly_spawn_t += dt
            if self._firefly_spawn_t >= 1.2 and len(self._fireflies) < max_count:
                self._firefly_spawn_t = 0.0
                self._fireflies.append(self._make_firefly())

        alive = []
        for p in self._fireflies:
            p["life"] -= dt
            if p["life"] <= 0:
                continue
            # Random gentle drift
            p["phase"] += dt
            p["x"] += math.sin(p["phase"] * 0.7) * 15 * dt
            p["y"] += math.cos(p["phase"] * 0.5) * 10 * dt
            # Blink on/off every 1-2 seconds
            p["blink_t"] += dt
            if p["blink_t"] >= p["blink_interval"]:
                p["blink_t"] = 0.0
                p["visible"] = not p["visible"]
            alive.append(p)

        # Kill fireflies when it's no longer night
        if not show:
            alive = [p for p in alive if p["life"] > 0.5]

        self._fireflies = alive

    def _make_firefly(self) -> dict:
        return {
            "x": random.uniform(50, SCREEN_WIDTH - 50),
            "y": random.uniform(SCREEN_HEIGHT * 0.2, SCREEN_HEIGHT * 0.7),
            "phase": random.uniform(0, 6.28),
            "color": (230, 230, 80),
            "life": random.uniform(5, 12),
            "visible": True,
            "blink_t": 0.0,
            "blink_interval": random.uniform(1.0, 2.0),
        }

    def _draw_fireflies(self, screen: pygame.Surface):
        for p in self._fireflies:
            if not p["visible"]:
                continue
            x, y = int(p["x"]), int(p["y"])
            if not (0 <= x < SCREEN_WIDTH and 0 <= y < SCREEN_HEIGHT):
                continue
            # Glow effect: larger translucent circle + bright center
            glow = pygame.Surface((8, 8), pygame.SRCALPHA)
            pygame.draw.circle(glow, (230, 230, 80, 50), (4, 4), 4)
            pygame.draw.circle(glow, (255, 255, 120, 200), (4, 4), 1)
            screen.blit(glow, (x - 4, y - 4))

    # ----------------------------------------------------------------
    # DUST MOTES (indoor / desert)
    # ----------------------------------------------------------------

    def _update_dust(self, dt: float, is_indoor: bool, biome: str):
        """Spawn and move subtle dust mote particles."""
        show = is_indoor or biome in ("desert", "sand")
        max_count = 10 if show else 0

        if show:
            self._dust_spawn_t += dt
            if self._dust_spawn_t >= 0.8 and len(self._dust) < max_count:
                self._dust_spawn_t = 0.0
                self._dust.append(self._make_dust())

        alive = []
        for p in self._dust:
            p["life"] -= dt
            if p["life"] <= 0:
                continue
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            alive.append(p)

        if not show:
            alive = [p for p in alive if p["life"] > 0.3]

        self._dust = alive

    def _make_dust(self) -> dict:
        return {
            "x": random.uniform(0, SCREEN_WIDTH),
            "y": random.uniform(0, SCREEN_HEIGHT),
            "vx": random.uniform(-5, 5),
            "vy": random.uniform(-3, 3),
            "life": random.uniform(3, 6),
        }

    def _draw_dust(self, screen: pygame.Surface):
        for p in self._dust:
            alpha = int(70 * min(1.0, p["life"] / 1.5))
            x, y = int(p["x"]), int(p["y"])
            if not (0 <= x < SCREEN_WIDTH and 0 <= y < SCREEN_HEIGHT):
                continue
            surf = pygame.Surface((2, 2), pygame.SRCALPHA)
            surf.fill((210, 200, 170, alpha))
            screen.blit(surf, (x, y))

    # ----------------------------------------------------------------
    # SNOW ACCUMULATION (winter weather)
    # ----------------------------------------------------------------

    def _update_snow_accum(self, dt: float, season: str, weather: str):
        """Snow particles that briefly sit on the ground then fade."""
        show = season == "winter" and weather == "snow"
        max_count = 15 if show else 0

        if show and random.random() < 0.15:
            if len(self._snow_accum) < max_count:
                self._snow_accum.append({
                    "x": random.randint(0, SCREEN_WIDTH - 1),
                    "y": random.randint(int(SCREEN_HEIGHT * 0.6), SCREEN_HEIGHT - 2),
                    "life": random.uniform(2.0, 3.5),
                    "max_life": 3.5,
                })

        alive = []
        for p in self._snow_accum:
            p["life"] -= dt
            if p["life"] > 0:
                alive.append(p)
        self._snow_accum = alive

    def _draw_snow_accum(self, screen: pygame.Surface):
        for p in self._snow_accum:
            alpha = int(180 * min(1.0, p["life"] / 1.0))
            x, y = int(p["x"]), int(p["y"])
            if not (0 <= x < SCREEN_WIDTH and 0 <= y < SCREEN_HEIGHT):
                continue
            surf = pygame.Surface((2, 2), pygame.SRCALPHA)
            surf.fill((240, 242, 248, alpha))
            screen.blit(surf, (x, y))

    # ----------------------------------------------------------------
    # STARS (clear night)
    # ----------------------------------------------------------------

    def _update_stars(self, dt: float, is_night: bool, weather: str):
        """Manage twinkling star dots for clear night sky."""
        show = is_night and weather in ("clear", "")
        target = 25 if show else 0

        # Initialize stars once, then just twinkle
        if show and not self._star_init:
            self._stars = [self._make_star() for _ in range(target)]
            self._star_init = True

        if not show:
            self._stars.clear()
            self._star_init = False
            return

        # Twinkle: vary opacity
        for s in self._stars:
            s["twinkle_t"] += dt
            if s["twinkle_t"] >= s["twinkle_interval"]:
                s["twinkle_t"] = 0.0
                s["alpha"] = random.randint(80, 255)

    def _make_star(self) -> dict:
        return {
            "x": random.randint(0, SCREEN_WIDTH - 1),
            "y": random.randint(0, int(SCREEN_HEIGHT * 0.35)),
            "alpha": random.randint(120, 255),
            "twinkle_t": random.uniform(0, 2.0),
            "twinkle_interval": random.uniform(0.8, 2.5),
            "size": 1 if random.random() < 0.7 else 2,
        }

    def _draw_stars(self, screen: pygame.Surface):
        for s in self._stars:
            x, y = s["x"], s["y"]
            a = s["alpha"]
            sz = s["size"]
            if sz == 1:
                surf = pygame.Surface((1, 1), pygame.SRCALPHA)
                surf.fill((255, 255, 255, a))
                screen.blit(surf, (x, y))
            else:
                surf = pygame.Surface((3, 3), pygame.SRCALPHA)
                pygame.draw.circle(surf, (255, 255, 240, a), (1, 1), 1)
                screen.blit(surf, (x - 1, y - 1))
