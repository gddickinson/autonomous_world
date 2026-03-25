"""
Creature Needs System — hunger and thirst for wildlife creatures.

Creatures experience hunger and thirst that decay over time.  When needs
drop below thresholds they seek food/water; when critically low they
take HP damage.  Herbivores graze vegetation tiles, predators hunt prey,
and all creatures seek water tiles when thirsty.
"""

import math
import random
from typing import Optional, TYPE_CHECKING

from game.settings import (
    GRASS, FARMLAND, WHEAT_FIELD, WATER, SHALLOW_WATER, FOREST,
)
from game.data.ecology import PREDATOR_PREY

if TYPE_CHECKING:
    from game.systems.vegetation import VegetationSystem

# Which creatures are considered herbivores (not in PREDATOR_PREY, and passive)
_PREDATOR_KINDS = set(PREDATOR_PREY.keys())

# Tiles an herbivore can graze on
_GRAZE_TILES = {GRASS, FARMLAND, WHEAT_FIELD}

# Tiles that quench thirst
_WATER_TILES = {WATER, SHALLOW_WATER}

# Seek-range when hungry/thirsty
_SEEK_RANGE = 12.0

# How far to scan for prey (predators)
_PREY_SEEK_RANGE = 15.0


def _is_herbivore(creature) -> bool:
    """Return True if creature is a grazing herbivore."""
    return (creature.kind not in _PREDATOR_KINDS
            and getattr(creature, 'passive', False))


def _is_predator(creature) -> bool:
    return creature.kind in _PREDATOR_KINDS


class CreatureNeedsSystem:
    """Manages hunger and thirst for all creatures each tick."""

    def __init__(self):
        self._vegetation: Optional["VegetationSystem"] = None
        self._tick_counter = 0

    def set_vegetation(self, veg: "VegetationSystem"):
        self._vegetation = veg

    def update(self, creatures, world, dt: float, creature_grid=None):
        """Called every tick. Only processes a batch of creatures per tick
        for performance — full cycle every ~10 ticks.

        Hunger/thirst decay is cheap (arithmetic), but seeking resources
        involves tile lookups and spatial queries, so we batch those.
        """
        creature_list = creatures if isinstance(creatures, list) else list(creatures)
        n = len(creature_list)
        if n == 0:
            return

        # Decay needs for ALL creatures every tick (cheap: just subtract)
        for c in creature_list:
            if not c.alive:
                continue
            if not hasattr(c, 'hunger'):
                c.hunger = 80.0
                c.thirst = 80.0
            # Inline decay for speed
            c.hunger = max(0.0, c.hunger - (0.3 if c.kind in _PREDATOR_KINDS else 0.5) * dt)
            c.thirst = max(0.0, c.thirst - 0.8 * dt)
            # Damage from starvation/dehydration
            if c.hunger < 10.0:
                c.hp -= dt
            if c.thirst < 10.0:
                c.hp -= dt
            if c.hp <= 0:
                c.hp = 0
                c.alive = False

        # Seek resources for a BATCH of creatures per tick (expensive: tile lookups)
        batch_size = max(5, n // 10)  # process ~10% per tick = full cycle in 10 ticks
        start = self._tick_counter % n
        self._tick_counter += batch_size
        for i in range(batch_size):
            idx = (start + i) % n
            c = creature_list[idx]
            if c.alive and (c.hunger < 20.0 or c.thirst < 20.0):
                self._seek_resources(c, world, dt, creature_grid)

    def _seek_resources(self, c, world, dt: float, creature_grid):
        """Drive creatures toward food or water when need is low.

        Only overrides creature state when creature is idle/wandering,
        so combat and fleeing are not interrupted.
        """
        if c.state in ("chasing", "attacking", "fleeing"):
            return

        # Thirst takes priority over hunger
        if c.thirst < 20.0:
            self._seek_water(c, world, dt)
            return

        if c.hunger < 20.0:
            if _is_herbivore(c):
                self._seek_vegetation(c, world, dt)
            elif _is_predator(c) and creature_grid is not None:
                self._seek_prey(c, creature_grid, dt)

    def _seek_water(self, c, world, dt: float):
        """Move creature toward the nearest water tile."""
        tx, ty = self._find_tile_nearby(c, world, _WATER_TILES, _SEEK_RANGE)
        if tx is not None:
            dist = math.sqrt((c.x - tx) ** 2 + (c.y - ty) ** 2)
            if dist < 1.5:
                # Drinking
                c.thirst = min(100.0, 90.0)
                c.state = "idle"
                c.state_timer = random.uniform(2.0, 4.0)
            else:
                c.state = "wandering"
                c.state_timer = 3.0
                c._move_toward(tx, ty, dt, world)

    def _seek_vegetation(self, c, world, dt: float):
        """Move herbivore toward a grazeable tile."""
        tx, ty = self._find_tile_nearby(c, world, _GRAZE_TILES, _SEEK_RANGE)
        if tx is not None:
            dist = math.sqrt((c.x - tx) ** 2 + (c.y - ty) ** 2)
            if dist < 1.5:
                # Grazing
                food = 30.0
                if self._vegetation is not None:
                    food = self._vegetation.graze_at(int(tx), int(ty), world)
                c.hunger = min(100.0, c.hunger + food)
                c.state = "idle"
                c.state_timer = random.uniform(3.0, 6.0)
            else:
                c.state = "wandering"
                c.state_timer = 3.0
                c._move_toward(tx, ty, dt, world)

    def _seek_prey(self, c, creature_grid, dt: float):
        """Predator seeks a prey creature from PREDATOR_PREY mapping."""
        prey_kinds = PREDATOR_PREY.get(c.kind, [])
        if not prey_kinds:
            return

        best = None
        best_d2 = _PREY_SEEK_RANGE * _PREY_SEEK_RANGE
        nearby = creature_grid.get_nearby(c.x, c.y, _PREY_SEEK_RANGE)
        for other in nearby:
            if not other.alive:
                continue
            if other.kind not in prey_kinds:
                continue
            d2 = (c.x - other.x) ** 2 + (c.y - other.y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = other

        if best is not None:
            # Chase prey — creature AI will handle the actual attack
            c.state = "chasing"
            c.target = best
            c.state_timer = 10.0

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _find_tile_nearby(creature, world, tile_set, radius):
        """Scan nearby tiles for one of the given types.

        Uses a sparse random-sample approach for performance —
        checks ~20 random positions rather than scanning the full area.
        Returns (x, y) of a matching tile or (None, None).
        """
        cx, cy = int(creature.x), int(creature.y)
        r = int(radius)
        best = None
        best_d2 = radius * radius + 1

        for _ in range(8):
            sx = cx + random.randint(-r, r)
            sy = cy + random.randint(-r, r)
            try:
                tile = world.tiles.get_tile(sx, sy) if hasattr(world.tiles, 'get_tile') else world.tiles[sy][sx]
            except (IndexError, KeyError):
                continue
            if tile in tile_set:
                d2 = (sx - cx) ** 2 + (sy - cy) ** 2
                if d2 < best_d2:
                    best_d2 = d2
                    best = (sx, sy)

        if best is not None:
            return best
        return (None, None)


def on_predator_kill(predator):
    """Called when a predator successfully kills prey.  Restores hunger."""
    if hasattr(predator, 'hunger'):
        predator.hunger = min(100.0, 80.0)
