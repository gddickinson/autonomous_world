"""
Environment & Ecology: seasons, weather, crop growth, forest regrowth,
and ecosystem simulation (predator-prey dynamics, breeding, migration).

Four seasons affect farming, creature behavior, and travel.
Crops grow through planting → growth → harvest cycles.
Chopped forests slowly regrow. Animal populations fluctuate.
"""

import random
import math
from typing import Dict, List, Optional, TYPE_CHECKING
from game.settings import *

if TYPE_CHECKING:
    from game.systems.world_manager import WorldManager


SEASONS = ["spring", "summer", "autumn", "winter"]

# Season effects on gameplay
SEASON_EFFECTS = {
    "spring":  {"crop_growth": 1.5, "food_decay": 0.8, "travel_speed": 1.0, "creature_activity": 1.2},
    "summer":  {"crop_growth": 2.0, "food_decay": 1.2, "travel_speed": 1.0, "creature_activity": 1.0},
    "autumn":  {"crop_growth": 0.5, "food_decay": 0.9, "travel_speed": 0.9, "creature_activity": 0.8},
    "winter":  {"crop_growth": 0.0, "food_decay": 0.7, "travel_speed": 0.7, "creature_activity": 0.5},
}

WEATHER_TYPES = ["clear", "cloudy", "rain", "storm", "fog", "snow"]

WEATHER_EFFECTS = {
    "clear":  {"visibility": 1.0, "speed_mult": 1.0, "morale_bonus": 2},
    "cloudy": {"visibility": 0.9, "speed_mult": 1.0, "morale_bonus": 0},
    "rain":   {"visibility": 0.7, "speed_mult": 0.8, "morale_bonus": -3},
    "storm":  {"visibility": 0.5, "speed_mult": 0.6, "morale_bonus": -8},
    "fog":    {"visibility": 0.4, "speed_mult": 0.9, "morale_bonus": -2},
    "snow":   {"visibility": 0.6, "speed_mult": 0.5, "morale_bonus": -5},
}


class EcologySystem:
    """Manages seasons, weather, crop growth, forest regrowth, and ecosystem."""

    def __init__(self):
        self.season = "spring"
        self.weather = "clear"
        self.season_day = 0  # day within current season
        self.season_length = 7  # game-days per season
        self.weather_timer = 0.0
        self.regrowth_timer = 0.0
        self.crop_timer = 0.0
        self.ecosystem_timer = 0.0
        self._world_mgr: Optional["WorldManager"] = None
        self._last_ecosystem_day = -1

    def set_world_manager(self, world_mgr: "WorldManager"):
        """Bind a WorldManager so the ecosystem can access creature lists."""
        self._world_mgr = world_mgr

    def update(self, dt: float, day: int, world, time_sys=None):
        """Update ecology systems."""
        # Season from astronomy (if time system available) or fixed cycle fallback
        if time_sys and hasattr(time_sys, 'season'):
            new_season = time_sys.season
        else:
            season_index = (day // self.season_length) % 4
            new_season = SEASONS[season_index]
        if new_season != self.season:
            self.season = new_season
            self.season_day = 0

        # Weather changes every few minutes
        self.weather_timer += dt
        if self.weather_timer > 180:
            self.weather_timer = 0
            self._change_weather()

        # Forest regrowth (check every 5 minutes)
        self.regrowth_timer += dt
        if self.regrowth_timer > 300:
            self.regrowth_timer = 0
            self._regrow_forests(world)

        # Crop growth
        self.crop_timer += dt
        if self.crop_timer > 120:
            self.crop_timer = 0
            self._grow_crops(world)

        # Ecosystem simulation (once per game-day, every 10 minutes real-time)
        self.ecosystem_timer += dt
        if self.ecosystem_timer > 600 and self._world_mgr is not None:
            self.ecosystem_timer = 0
            if day != self._last_ecosystem_day:
                self._last_ecosystem_day = day
                self._update_ecosystem(self._world_mgr, self.season, time_sys)

    def _change_weather(self):
        """Change weather based on season."""
        if self.season == "winter":
            self.weather = random.choices(
                ["clear", "cloudy", "snow", "storm", "fog"],
                weights=[15, 25, 30, 15, 15], k=1)[0]
        elif self.season == "spring":
            self.weather = random.choices(
                ["clear", "cloudy", "rain", "fog"],
                weights=[35, 30, 25, 10], k=1)[0]
        elif self.season == "summer":
            self.weather = random.choices(
                ["clear", "cloudy", "rain", "storm"],
                weights=[50, 25, 15, 10], k=1)[0]
        else:  # autumn
            self.weather = random.choices(
                ["clear", "cloudy", "rain", "fog", "storm"],
                weights=[20, 30, 25, 15, 10], k=1)[0]

    def _regrow_forests(self, world):
        """Tree stumps slowly regrow into forests.

        For chunked worlds, only processes loaded chunks.
        """
        from game.world.chunk import ChunkGrid
        count = 0
        if isinstance(world.tiles, ChunkGrid):
            # Only process loaded chunks
            for key in list(world.tiles.loaded_chunk_keys()):
                chunk = world.tiles._chunks.get(key)
                if chunk is None:
                    continue
                import numpy as np
                stumps = np.argwhere(chunk.tiles == TREE_STUMP)
                for ly, lx in stumps:
                    if random.random() < 0.05:
                        chunk.tiles[ly, lx] = FOREST
                        chunk.dirty = True
                        count += 1
        else:
            for y in range(world.height):
                for x in range(world.width):
                    if world.tiles[y][x] == TREE_STUMP and random.random() < 0.05:
                        world.tiles[y][x] = FOREST
                        count += 1
        return count

    def _grow_crops(self, world):
        """Tilled soil grows into farmland based on season."""
        from game.world.chunk import ChunkGrid
        effects = SEASON_EFFECTS.get(self.season, {})
        growth_rate = effects.get("crop_growth", 1.0)

        if growth_rate <= 0:
            return  # winter - no growth

        if isinstance(world.tiles, ChunkGrid):
            import numpy as np
            for key in list(world.tiles.loaded_chunk_keys()):
                chunk = world.tiles._chunks.get(key)
                if chunk is None:
                    continue
                tilled = np.argwhere(chunk.tiles == TILLED_SOIL)
                for ly, lx in tilled:
                    if random.random() < 0.1 * growth_rate:
                        chunk.tiles[ly, lx] = FARMLAND
                        chunk.dirty = True
        else:
            for y in range(world.height):
                for x in range(world.width):
                    if world.tiles[y][x] == TILLED_SOIL and random.random() < 0.1 * growth_rate:
                        world.tiles[y][x] = FARMLAND

    def get_season_info(self) -> str:
        effects = SEASON_EFFECTS.get(self.season, {})
        weather_fx = WEATHER_EFFECTS.get(self.weather, {})
        return (f"Season: {self.season.capitalize()}, Weather: {self.weather.capitalize()}, "
                f"Crop growth: {effects.get('crop_growth', 1.0):.0%}, "
                f"Visibility: {weather_fx.get('visibility', 1.0):.0%}")

    # ------------------------------------------------------------------
    # Ecosystem simulation
    # ------------------------------------------------------------------

    def _update_ecosystem(self, world_mgr: "WorldManager", season: str,
                          time_sys=None):
        """Simple predator-prey balance and seasonal breeding.

        Called once per game-day.  Operates on the live creature list only
        (dormant creatures are assumed to be in equilibrium off-screen).
        """
        from game.data.ecology import PREDATOR_PREY, BREEDING_CREATURES
        from game.core.creature import Creature

        # 1. Census: count each creature kind
        creature_counts: Dict[str, int] = {}
        for c in world_mgr.creatures:
            if c.alive:
                creature_counts[c.kind] = creature_counts.get(c.kind, 0) + 1

        total_creatures = sum(creature_counts.values())

        # 2. Predator starvation — if predators vastly outnumber their prey
        for predator, prey_list in PREDATOR_PREY.items():
            pred_count = creature_counts.get(predator, 0)
            if pred_count == 0:
                continue
            prey_total = sum(creature_counts.get(p, 0) for p in prey_list)
            # If predators outnumber prey 2:1, some predators starve
            if prey_total > 0 and pred_count > prey_total * 2:
                starve_chance = 0.15
            elif prey_total == 0 and pred_count > 2:
                starve_chance = 0.25
            else:
                continue
            for c in list(world_mgr.creatures):
                if c.alive and c.kind == predator and random.random() < starve_chance:
                    c.hp -= c.max_hp * 0.3  # lose 30% HP from hunger
                    if c.hp <= 0:
                        c.alive = False

        # 3. Seasonal breeding — spring means new creatures
        if season == "spring":
            breeding_chance = 0.08  # 8% per existing creature per day
        elif season == "summer":
            breeding_chance = 0.03
        else:
            breeding_chance = 0.0

        if breeding_chance > 0 and total_creatures < world_mgr.max_creatures:
            new_creatures = []
            for c in world_mgr.creatures:
                if not c.alive:
                    continue
                if c.kind not in BREEDING_CREATURES:
                    continue
                # Don't breed if already too many of this kind
                if creature_counts.get(c.kind, 0) >= 15:
                    continue
                if random.random() < breeding_chance:
                    # Spawn offspring near parent
                    ox = c.x + random.uniform(-3, 3)
                    oy = c.y + random.uniform(-3, 3)
                    if world_mgr.world.is_walkable(int(ox), int(oy)):
                        baby = Creature(ox, oy, c.kind)
                        baby.hp = baby.max_hp // 2  # young = half HP
                        baby.home_x = c.home_x
                        baby.home_y = c.home_y
                        baby.leash_range = c.leash_range
                        new_creatures.append(baby)
                        if total_creatures + len(new_creatures) >= world_mgr.max_creatures:
                            break
            world_mgr.creatures.extend(new_creatures)

        # 4. Population pressure — if too many creatures, weakest may die
        if total_creatures > world_mgr.max_creatures * 1.2:
            # Remove some of the most common prey species
            excess = total_creatures - world_mgr.max_creatures
            cull_count = 0
            for c in list(world_mgr.creatures):
                if cull_count >= excess:
                    break
                if (c.alive and c.kind in BREEDING_CREATURES
                        and creature_counts.get(c.kind, 0) > 8
                        and random.random() < 0.2):
                    c.alive = False
                    cull_count += 1

        # 5. Nocturnal creature despawn/respawn based on time of day
        if time_sys is not None:
            from game.data.ecology import NOCTURNAL_CREATURES
            time_of_day = getattr(time_sys, 'time_of_day', 0.5)
            is_night = time_of_day > NIGHT_START or time_of_day < DAWN_START
            for c in world_mgr.creatures:
                if not c.alive:
                    continue
                if c.kind in NOCTURNAL_CREATURES:
                    if not is_night:
                        # Nocturnal creatures hide during the day (go idle far away)
                        c.state = "idle"
                        c.aggro_range = 0  # don't attack during day

                    else:
                        # Active at night
                        c.aggro_range = CREATURE_CHASE_RANGE

        # 6. Seasonal migration — some creatures shift biomes
        if season == "winter":
            # Deer and elk move toward forest (seek shelter)
            for c in world_mgr.creatures:
                if c.alive and c.kind in ("deer", "elk"):
                    # Nudge home position slightly toward forests
                    c.home_x += random.uniform(-2, 2)
                    c.home_y += random.uniform(-2, 2)
        elif season == "spring":
            # Creatures spread out to grasslands
            for c in world_mgr.creatures:
                if c.alive and c.kind in ("deer", "elk", "rabbit"):
                    c.home_x += random.uniform(-3, 3)
                    c.home_y += random.uniform(-3, 3)
