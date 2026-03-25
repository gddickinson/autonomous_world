"""
Vegetation Dynamics — tile health, grazing, depletion, and recovery.

Each vegetation tile has a health value (0.0–1.0).  When herbivores graze,
health drops.  When health reaches zero the tile type degrades (e.g. GRASS
becomes TILLED_SOIL).  Tiles recover slowly, modulated by season and
proximity to settlements.

Produces visual color overrides for tiles with reduced health so the
renderer can show barren/overgrazed land.
"""

import random
from typing import Dict, Tuple, Optional

from game.settings import (
    GRASS, FARMLAND, WHEAT_FIELD, FOREST,
    TILLED_SOIL, TREE_STUMP, TERRAIN_COLORS,
)

# Tile degradation mapping: when health hits 0, tile becomes…
_DEGRADE_MAP = {
    GRASS: TILLED_SOIL,
    WHEAT_FIELD: TILLED_SOIL,
    FARMLAND: TILLED_SOIL,
    FOREST: TREE_STUMP,
}

# Set of tiles that can be grazed at all
GRAZEABLE_TILES = set(_DEGRADE_MAP.keys())

# Season recovery multipliers
_SEASON_RECOVERY = {
    "spring": 2.0,
    "summer": 1.5,
    "autumn": 1.0,
    "winter": 0.25,
}

# Base recovery per game-hour (applied each tick, scaled by dt)
_BASE_RECOVERY = 0.02

# Health reduction per graze event
_GRAZE_COST = 0.15

# Food value returned to creature on successful graze
_GRAZE_FOOD = 30.0

# How many tiles to process per tick (round-robin)
_TILES_PER_TICK = 50

# Recovery bonus for farm tiles near settlements
_FARM_RECOVERY_BONUS = 3.0

# Health threshold below which tiles appear barren
_BARREN_THRESHOLD = 0.3

# Barren color (dried out brown)
_BARREN_COLOR = (155, 135, 95)

# Overgrazing threshold — if health hits 0 too many times, permanent damage
_OVERGRAZE_LIMIT = 3


class VegetationSystem:
    """Tracks per-tile health for grazed vegetation and drives recovery.

    Exposes color_overrides dict that the renderer can read to show
    overgrazed/barren tiles with modified colors.
    """

    def __init__(self):
        # (x, y) -> health [0.0 .. 1.0]
        self.tile_health: Dict[Tuple[int, int], float] = {}

        # Color overrides for visually degraded tiles: (x, y) -> (R, G, B)
        self.color_overrides: Dict[Tuple[int, int], Tuple[int, int, int]] = {}

        # Overgrazing counter: (x, y) -> depletion count
        self._overgraze_count: Dict[Tuple[int, int], int] = {}

        # Round-robin offset into the tile_health keys list
        self._rr_offset: int = 0

        # Settlement positions cache (rebuilt periodically)
        self._settlement_positions: list = []
        self._settle_cache_tick: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_health(self, x: int, y: int) -> float:
        """Return tile health.  1.0 if pristine (not tracked)."""
        return self.tile_health.get((x, y), 1.0)

    def get_color(self, x: int, y: int) -> Optional[Tuple[int, int, int]]:
        """Return color override for a tile, or None if no override."""
        return self.color_overrides.get((x, y))

    def graze_at(self, x: int, y: int, world) -> float:
        """An herbivore grazes at (x, y).

        Returns the food value gained (0 if tile depleted or not grazeable).
        """
        try:
            tile = (world.tiles.get_tile(x, y)
                    if hasattr(world.tiles, 'get_tile')
                    else world.tiles[y][x])
        except (IndexError, KeyError):
            return 0.0

        if tile not in GRAZEABLE_TILES:
            return 0.0

        health = self.tile_health.get((x, y), 1.0)
        if health <= 0.0:
            return 0.0

        # Reduce health
        health = max(0.0, health - _GRAZE_COST)
        self.tile_health[(x, y)] = health

        # Update visual color based on health
        self._update_tile_color(x, y, health, tile)

        # If depleted, degrade the tile
        if health <= 0.0:
            # Track overgrazing
            count = self._overgraze_count.get((x, y), 0) + 1
            self._overgraze_count[(x, y)] = count

            new_tile = _DEGRADE_MAP.get(tile)
            if new_tile is not None:
                self._set_world_tile(world, x, y, new_tile)

            # Permanent damage from overgrazing
            if count >= _OVERGRAZE_LIMIT:
                # Tile is permanently degraded — will not recover
                self.color_overrides[(x, y)] = _BARREN_COLOR

        return _GRAZE_FOOD

    def update(self, dt: float, world, time_sys):
        """Tick recovery for tracked tiles.  Called every tick but only
        processes a limited batch (round-robin).

        Args:
            dt: real-time delta
            world: game world
            time_sys: time system (has .season attribute)
        """
        if not self.tile_health:
            return

        season = getattr(time_sys, 'season', 'summer')
        season_mult = _SEASON_RECOVERY.get(season, 1.0)

        # Rebuild settlement cache every ~300 ticks
        self._settle_cache_tick += 1
        if self._settle_cache_tick >= 300:
            self._settle_cache_tick = 0
            self._rebuild_settlement_cache(world)

        keys = list(self.tile_health.keys())
        n = len(keys)
        if n == 0:
            return

        start = self._rr_offset % n
        end = min(start + _TILES_PER_TICK, n)
        batch = keys[start:end]
        self._rr_offset = end if end < n else 0

        to_remove = []
        for pos in batch:
            health = self.tile_health[pos]
            if health >= 1.0:
                to_remove.append(pos)
                continue

            # Skip permanently overgrazed tiles
            if self._overgraze_count.get(pos, 0) >= _OVERGRAZE_LIMIT:
                continue

            recovery = _BASE_RECOVERY * season_mult * dt
            # Farm tiles near settlements get a bonus (farmers tend them)
            if self._is_near_settlement(pos[0], pos[1]):
                try:
                    tile = (world.tiles.get_tile(pos[0], pos[1])
                            if hasattr(world.tiles, 'get_tile')
                            else world.tiles[pos[1]][pos[0]])
                except (IndexError, KeyError):
                    tile = 0
                if tile in (FARMLAND, WHEAT_FIELD, TILLED_SOIL):
                    recovery *= _FARM_RECOVERY_BONUS

            health = min(1.0, health + recovery)
            self.tile_health[pos] = health

            # Update visual color
            try:
                tile = (world.tiles.get_tile(pos[0], pos[1])
                        if hasattr(world.tiles, 'get_tile')
                        else world.tiles[pos[1]][pos[0]])
            except (IndexError, KeyError):
                tile = GRASS
            self._update_tile_color(pos[0], pos[1], health, tile)

            if health >= 1.0:
                to_remove.append(pos)

        # Clean up fully recovered tiles
        for pos in to_remove:
            self.tile_health.pop(pos, None)
            self.color_overrides.pop(pos, None)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _update_tile_color(self, x: int, y: int, health: float,
                           tile_type: int):
        """Set color override based on tile health.

        Blends between normal color and barren color as health drops.
        """
        if health >= 0.8:
            # Healthy enough — remove override
            self.color_overrides.pop((x, y), None)
            return

        # Permanently overgrazed — keep barren
        if self._overgraze_count.get((x, y), 0) >= _OVERGRAZE_LIMIT:
            self.color_overrides[(x, y)] = _BARREN_COLOR
            return

        # Blend: at health=0.8 use normal color, at health=0 use barren
        normal = TERRAIN_COLORS.get(tile_type, (86, 152, 72))
        t = 1.0 - (health / 0.8)  # 0 at health=0.8, 1 at health=0
        color = (
            int(normal[0] + (_BARREN_COLOR[0] - normal[0]) * t),
            int(normal[1] + (_BARREN_COLOR[1] - normal[1]) * t),
            int(normal[2] + (_BARREN_COLOR[2] - normal[2]) * t),
        )
        self.color_overrides[(x, y)] = color

    def _rebuild_settlement_cache(self, world):
        """Cache settlement centre positions for proximity checks."""
        self._settlement_positions = []
        for s in getattr(world, 'structures', []):
            if s.kind in ("village", "town", "city", "hamlet", "castle"):
                self._settlement_positions.append((s.x, s.y))

    def _is_near_settlement(self, x: int, y: int, radius: int = 30) -> bool:
        """Check if (x, y) is near any cached settlement."""
        r2 = radius * radius
        for sx, sy in self._settlement_positions:
            if (x - sx) ** 2 + (y - sy) ** 2 <= r2:
                return True
        return False

    @staticmethod
    def _set_world_tile(world, x: int, y: int, value: int):
        """Write a tile value, handling both ChunkGrid and plain array."""
        if hasattr(world.tiles, 'set_tile'):
            world.tiles.set_tile(x, y, value)
        else:
            try:
                world.tiles[y][x] = value
            except (IndexError, KeyError):
                pass
