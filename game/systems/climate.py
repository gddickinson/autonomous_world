"""
Global Climate Model & Weather System.

A simple pressure-system-based weather model. A handful of PressureSystem blobs
drift across the world map; local weather at any point is computed by sampling
nearby pressure systems and combining with latitude, elevation, season, and
coastal proximity.

Performance target: update() < 1 ms per game-day; get_local_weather() < 0.01 ms.
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    pass


# ================================================================
# DATA CLASSES
# ================================================================

@dataclass
class LocalWeather:
    """Weather conditions at a specific world position."""
    temperature: float = 20.0       # celsius-like, -20 to 45
    precipitation: str = "none"     # "none","light_rain","rain","heavy_rain","snow","hail"
    wind_speed: float = 0.0         # 0-1 (calm to gale)
    cloud_cover: float = 0.0        # 0-1
    visibility: float = 1.0         # 0-1 (fog=0.2, clear=1.0)
    condition: str = "clear"        # "clear","cloudy","rain","storm","snow","fog","heat_wave","drought"

    @property
    def description(self) -> str:
        """Human-readable one-line summary."""
        temp_str = f"{self.temperature:.0f}C"
        return f"{self.condition.replace('_', ' ').title()}, {temp_str}"


@dataclass
class PressureSystem:
    """A drifting pressure blob on the world map."""
    x: float                        # world position
    y: float
    pressure_type: str              # "high" or "low"
    strength: float                 # 0-1
    radius: float                   # tiles affected (500-2000)
    age: int = 0                    # days since spawn
    max_age: int = 15               # days before dissipation
    vx: float = 0.0                 # drift velocity (tiles/day)
    vy: float = 0.0

    @property
    def alive(self) -> bool:
        return self.age < self.max_age


@dataclass
class DisasterEvent:
    """A natural disaster triggered by weather conditions."""
    disaster_type: str              # "flood","drought","wildfire","blizzard"
    x: float
    y: float
    radius: float
    severity: float                 # 0-1
    day_started: int = 0
    duration_days: int = 3
    description: str = ""


# ================================================================
# SEASON HELPERS
# ================================================================

SEASON_TEMP_OFFSET = {
    "spring": 0.0,
    "summer": 12.0,
    "autumn": -2.0,
    "winter": -18.0,
}

SEASON_STORM_CHANCE = {
    "spring": 0.12,
    "summer": 0.08,
    "autumn": 0.15,
    "winter": 0.10,
}

SEASON_FOG_CHANCE = {
    "spring": 0.10,
    "summer": 0.03,
    "autumn": 0.15,
    "winter": 0.08,
}


# ================================================================
# WEATHER MODIFIERS FOR GAMEPLAY
# ================================================================

# Multipliers: condition -> activity -> multiplier
_WEATHER_MODIFIERS = {
    "clear":     {"farming": 1.0, "travel": 1.0, "construction": 1.0,
                  "fishing": 1.0, "mining": 1.0, "outdoor_work": 1.0},
    "cloudy":    {"farming": 1.0, "travel": 1.0, "construction": 1.0,
                  "fishing": 1.0, "mining": 1.0, "outdoor_work": 1.0},
    "rain":      {"farming": 1.2, "travel": 0.7, "construction": 0.7,
                  "fishing": 0.9, "mining": 1.0, "outdoor_work": 0.8},
    "storm":     {"farming": 0.5, "travel": 0.3, "construction": 0.0,
                  "fishing": 0.0, "mining": 1.0, "outdoor_work": 0.2},
    "snow":      {"farming": 0.0, "travel": 0.5, "construction": 0.0,
                  "fishing": 0.5, "mining": 1.0, "outdoor_work": 0.3},
    "fog":       {"farming": 0.9, "travel": 0.8, "construction": 0.9,
                  "fishing": 0.8, "mining": 1.0, "outdoor_work": 0.9},
    "heat_wave": {"farming": 0.7, "travel": 0.8, "construction": 0.8,
                  "fishing": 1.0, "mining": 0.9, "outdoor_work": 0.6},
    "drought":   {"farming": 0.3, "travel": 1.0, "construction": 1.0,
                  "fishing": 0.5, "mining": 1.0, "outdoor_work": 0.8},
}

# Which professions map to which activity for weather modifiers
_PROFESSION_ACTIVITY = {
    "Farmer": "farming", "Shepherd": "farming", "Beekeeper": "farming",
    "Fisherman": "fishing", "Fisher": "fishing",
    "Miner": "mining", "Prospector": "mining", "Smelter": "mining",
    "Builder": "construction", "Mason": "construction", "Carpenter": "construction",
    "Woodcutter": "outdoor_work", "Hunter": "outdoor_work", "Herbalist": "outdoor_work",
    "Ranger": "outdoor_work", "Guard": "outdoor_work",
    "Merchant": "travel", "Caravaneer": "travel", "Porter": "travel",
}


def get_weather_modifier(climate_model, x: float, y: float, activity: str) -> float:
    """Return a production/speed multiplier for a given activity at a location.

    Args:
        climate_model: A ClimateModel instance (or None for 1.0 default).
        x, y: World position.
        activity: One of "farming","travel","construction","fishing","mining","outdoor_work".

    Returns:
        Float multiplier, typically 0.0-1.2.
    """
    if climate_model is None:
        return 1.0
    weather = climate_model.get_local_weather(x, y)
    mods = _WEATHER_MODIFIERS.get(weather.condition, _WEATHER_MODIFIERS["clear"])
    return mods.get(activity, 1.0)


def get_weather_modifier_for_profession(climate_model, x: float, y: float,
                                         profession: str) -> float:
    """Convenience: look up the activity for a profession and return modifier."""
    activity = _PROFESSION_ACTIVITY.get(profession, "outdoor_work")
    return get_weather_modifier(climate_model, x, y, activity)


# ================================================================
# CLIMATE MODEL
# ================================================================

class ClimateModel:
    """Simple global weather driven by drifting pressure systems.

    Usage:
        climate = ClimateModel(10000, 10000, seed=42)
        climate.update(game_day=1, season="spring")
        w = climate.get_local_weather(5000, 3000)
    """

    def __init__(self, world_width: int, world_height: int, seed=None,
                 world_plan=None):
        self.width = world_width
        self.height = world_height
        self.pressure_systems: List[PressureSystem] = []
        self.prevailing_wind = (1.0, 0.0)   # eastward drift
        self.season = "spring"
        self.rng = random.Random(seed)
        self.seed = seed if seed is not None else 0

        # World plan reference for elevation / river lookups
        self._world_plan = world_plan

        # Cache local weather per settlement each day
        self._weather_cache: Dict[Tuple[int, int], LocalWeather] = {}
        self._cache_day: int = -1

        # Track consecutive dry days per region bucket (for drought detection)
        # Key: (x // 500, y // 500), Value: consecutive days with no rain
        self._dry_day_counts: Dict[Tuple[int, int], int] = {}

        # Active disasters
        self.active_disasters: List[DisasterEvent] = []

        # Consecutive rainy days tracker (for emotion: prolonged rain)
        self._rain_day_counts: Dict[Tuple[int, int], int] = {}

        # Spawn initial pressure systems
        self._spawn_initial_systems()

    # ---- Initialization ----

    def _spawn_initial_systems(self):
        """Create a few starting pressure systems."""
        for _ in range(4):
            self._spawn_one_system()

    def _spawn_one_system(self):
        """Spawn a single random pressure system."""
        x = self.rng.uniform(0, self.width)
        y = self.rng.uniform(0, self.height)
        ptype = self.rng.choice(["high", "low"])
        strength = self.rng.uniform(0.3, 1.0)
        radius = self.rng.uniform(500, 2000)
        max_age = self.rng.randint(8, 20)

        # Drift: prevailing eastward + random component
        vx = self.prevailing_wind[0] * self.rng.uniform(30, 120)
        vy = self.prevailing_wind[1] + self.rng.uniform(-40, 40)

        ps = PressureSystem(
            x=x, y=y,
            pressure_type=ptype,
            strength=strength,
            radius=radius,
            max_age=max_age,
            vx=vx, vy=vy,
        )
        self.pressure_systems.append(ps)

    # ---- Per-Day Update ----

    def update(self, game_day: int, season: str):
        """Update climate once per game day. Must be <1ms."""
        self.season = season

        # Invalidate weather cache on new day
        if game_day != self._cache_day:
            self._weather_cache.clear()
            self._cache_day = game_day

        self._drift_pressure_systems()
        self._age_and_remove()
        self._spawn_new_systems(game_day)
        self._update_dry_rain_counters()
        self._expire_disasters(game_day)

    def _drift_pressure_systems(self):
        """Move pressure systems according to their velocity."""
        for ps in self.pressure_systems:
            ps.x += ps.vx
            ps.y += ps.vy

            # Wrap horizontally (weather comes from the west)
            if ps.x > self.width + ps.radius:
                ps.x = -ps.radius
            elif ps.x < -ps.radius:
                ps.x = self.width + ps.radius

            # Clamp vertically with bounce
            if ps.y < 0:
                ps.y = 0
                ps.vy = abs(ps.vy) * 0.5
            elif ps.y > self.height:
                ps.y = self.height
                ps.vy = -abs(ps.vy) * 0.5

            # Slight random perturbation
            ps.vx += self.rng.uniform(-5, 5)
            ps.vy += self.rng.uniform(-5, 5)

    def _age_and_remove(self):
        """Age pressure systems and remove expired ones."""
        alive = []
        for ps in self.pressure_systems:
            ps.age += 1
            # Strength fades with age
            fade = 1.0 - (ps.age / ps.max_age) ** 2
            ps.strength = max(0.0, ps.strength * fade + 0.01)
            if ps.alive and ps.strength > 0.05:
                alive.append(ps)
        self.pressure_systems = alive

    def _spawn_new_systems(self, game_day: int):
        """Maintain 3-6 active pressure systems."""
        target = 4 + (game_day % 3)  # fluctuate between 4-6
        while len(self.pressure_systems) < target:
            self._spawn_one_system()

        # Seasonal storms: extra low-pressure in stormy seasons
        storm_chance = SEASON_STORM_CHANCE.get(self.season, 0.1)
        if self.rng.random() < storm_chance and len(self.pressure_systems) < 8:
            self._spawn_one_system()
            self.pressure_systems[-1].pressure_type = "low"
            self.pressure_systems[-1].strength = self.rng.uniform(0.6, 1.0)

    def _update_dry_rain_counters(self):
        """Update regional dry/rain day counters for drought/prolonged-rain detection."""
        # Sample a grid of points
        step = 500
        for bx in range(0, self.width, step):
            by_key = bx // step
            for by in range(0, self.height, step):
                key = (by_key, by // step)
                w = self.get_local_weather(bx + step // 2, by + step // 2)
                if w.condition in ("rain", "storm", "snow"):
                    self._dry_day_counts[key] = 0
                    self._rain_day_counts[key] = self._rain_day_counts.get(key, 0) + 1
                else:
                    self._dry_day_counts[key] = self._dry_day_counts.get(key, 0) + 1
                    self._rain_day_counts[key] = 0

    def _expire_disasters(self, game_day: int):
        """Remove disasters that have run their course."""
        self.active_disasters = [
            d for d in self.active_disasters
            if game_day - d.day_started < d.duration_days
        ]

    # ---- Local Weather Sampling ----

    def get_local_weather(self, x: float, y: float) -> LocalWeather:
        """Compute weather at a world position. Results cached per settlement-bucket per day."""
        # Bucket to ~100-tile resolution for caching
        cache_key = (int(x) // 100, int(y) // 100)
        cached = self._weather_cache.get(cache_key)
        if cached is not None:
            return cached

        weather = self._compute_weather(x, y)
        self._weather_cache[cache_key] = weather
        return weather

    def _compute_weather(self, x: float, y: float) -> LocalWeather:
        """Full weather computation at a world position."""
        w = LocalWeather()

        # ---- Temperature ----
        w.temperature = self._compute_temperature(x, y)

        # ---- Pressure influence ----
        low_influence = 0.0
        high_influence = 0.0
        max_wind = 0.0

        for ps in self.pressure_systems:
            dx = x - ps.x
            dy = y - ps.y
            dist_sq = dx * dx + dy * dy
            r_sq = ps.radius * ps.radius
            if dist_sq > r_sq * 4:
                continue  # too far
            dist = math.sqrt(dist_sq)
            # Influence falls off linearly within radius, then quadratically beyond
            if dist < ps.radius:
                influence = ps.strength * (1.0 - dist / ps.radius)
            else:
                influence = ps.strength * (ps.radius / dist) ** 2
                influence = max(0.0, influence - 0.05)

            if ps.pressure_type == "low":
                low_influence = max(low_influence, influence)
            else:
                high_influence = max(high_influence, influence)

            # Wind is strongest at the edge of pressure systems
            edge_ratio = dist / max(1, ps.radius)
            wind = ps.strength * (1.0 - abs(edge_ratio - 0.7) / 0.7)
            max_wind = max(max_wind, max(0.0, wind))

        w.wind_speed = min(1.0, max_wind)

        # ---- Cloud cover ----
        w.cloud_cover = min(1.0, low_influence * 1.5 + 0.1)
        if high_influence > low_influence:
            w.cloud_cover = max(0.0, w.cloud_cover - high_influence * 0.5)

        # ---- Coastal moisture boost ----
        coast_factor = self._coastal_factor(x, y)
        moisture = low_influence + coast_factor * 0.2

        # ---- Rain shadow (mountains block moisture from the west) ----
        rain_shadow = self._rain_shadow_factor(x, y)
        moisture *= rain_shadow

        # ---- Precipitation ----
        w.precipitation = "none"
        if moisture > 0.2:
            if w.temperature <= 0:
                # Cold: snow
                if moisture > 0.6:
                    w.precipitation = "snow"
                elif moisture > 0.3:
                    w.precipitation = "snow"
            else:
                if moisture > 0.7:
                    w.precipitation = "heavy_rain"
                elif moisture > 0.5:
                    w.precipitation = "rain"
                elif moisture > 0.3:
                    w.precipitation = "light_rain"

            # Hail: rare in summer storms
            if (self.season == "summer" and low_influence > 0.8
                    and w.temperature > 25):
                if self.rng.random() < 0.1:
                    w.precipitation = "hail"

        # ---- Condition ----
        w.condition = self._determine_condition(
            w, low_influence, high_influence, moisture, x, y)

        # ---- Visibility ----
        w.visibility = 1.0
        if w.condition == "fog":
            w.visibility = 0.2
        elif w.condition == "storm":
            w.visibility = 0.4
        elif w.condition == "snow":
            w.visibility = 0.5
        elif w.condition in ("rain",):
            w.visibility = 0.7
        elif w.cloud_cover > 0.7:
            w.visibility = 0.8

        return w

    def _compute_temperature(self, x: float, y: float) -> float:
        """Temperature based on latitude, elevation, season, coast, time."""
        # Latitude gradient: top of map (y=0) is cold, bottom (y=height) is warm
        lat_ratio = y / max(1, self.height)  # 0=north/cold, 1=south/warm
        base_temp = -10.0 + lat_ratio * 40.0  # -10C at top, 30C at bottom

        # Season modifier
        season_offset = SEASON_TEMP_OFFSET.get(self.season, 0.0)
        base_temp += season_offset

        # Altitude modifier: higher = colder
        elevation = self._get_elevation(x, y)
        # elevation is 0-1; mountain threshold ~0.65
        if elevation > 0.35:
            alt_penalty = (elevation - 0.35) * 30.0  # up to -20C for highest peaks
            base_temp -= alt_penalty

        # Coastal moderation: coastal tiles have less extreme temperatures
        coast = self._coastal_factor(x, y)
        if coast > 0.3:
            # Pull toward 15C (moderate)
            base_temp = base_temp + (15.0 - base_temp) * coast * 0.3

        # Clamp
        return max(-25.0, min(45.0, base_temp))

    def _get_elevation(self, x: float, y: float) -> float:
        """Get elevation at a world position (0-1)."""
        if self._world_plan is not None and hasattr(self._world_plan, 'get_elevation_fast'):
            ix = max(0, min(int(x), self._world_plan.width - 1))
            iy = max(0, min(int(y), self._world_plan.height - 1))
            return self._world_plan.get_elevation_fast(ix, iy)
        # Fallback: use a simple hash-based estimate
        return 0.4  # average elevation

    def _coastal_factor(self, x: float, y: float) -> float:
        """How coastal this position is (0=inland, 1=right on water).

        Uses elevation as proxy: tiles near water (elev < 0.22) are coastal.
        """
        if self._world_plan is None:
            return 0.0
        # Sample nearby tiles for water
        step = 50
        water_count = 0
        total = 0
        for dx in range(-200, 201, step):
            for dy in range(-200, 201, step):
                nx = max(0, min(int(x + dx), self.width - 1))
                ny = max(0, min(int(y + dy), self.height - 1))
                elev = self._get_elevation(nx, ny)
                total += 1
                if elev < 0.22:
                    water_count += 1
        return min(1.0, water_count / max(1, total) * 3.0)

    def _rain_shadow_factor(self, x: float, y: float) -> float:
        """Rain shadow: tiles east of mountains are drier (returns 0-1 moisture multiplier)."""
        if self._world_plan is None:
            return 1.0
        # Check if there are mountains to the west
        step = 100
        mountain_west = False
        for dist in range(step, 600, step):
            wx = x - dist  # look westward
            if wx < 0:
                break
            elev = self._get_elevation(wx, y)
            if elev > 0.6:
                mountain_west = True
                break
        if mountain_west:
            return 0.5  # 50% moisture reduction in rain shadow
        return 1.0

    def _determine_condition(self, w: LocalWeather, low_infl: float,
                              high_infl: float, moisture: float,
                              x: float, y: float) -> str:
        """Determine the overall weather condition string."""
        # Check drought
        bucket = (int(x) // 500, int(y) // 500)
        dry_days = self._dry_day_counts.get(bucket, 0)
        if dry_days >= 10 and w.temperature > 25:
            return "drought"

        # Heat wave: high temp + high pressure + low moisture
        if w.temperature > 35 and high_infl > 0.4 and moisture < 0.2:
            return "heat_wave"

        # Storm: strong low pressure
        if low_infl > 0.6 and moisture > 0.5:
            return "storm"

        # Snow
        if w.precipitation == "snow":
            return "snow"

        # Rain
        if w.precipitation in ("rain", "heavy_rain"):
            return "rain"

        # Fog: calm conditions, high moisture, low wind, near coast or dawn
        fog_chance = SEASON_FOG_CHANCE.get(self.season, 0.05)
        coast = self._coastal_factor(x, y)
        if (w.wind_speed < 0.2 and coast > 0.2
                and moisture > 0.1 and w.cloud_cover > 0.3):
            # Deterministic fog based on position hash to avoid flickering
            fog_hash = ((int(x) * 7919 + int(y) * 6271 + self._cache_day * 3571)
                        & 0xFFFF) / 0xFFFF
            if fog_hash < fog_chance * 3:
                return "fog"

        # Cloudy
        if w.cloud_cover > 0.5:
            return "cloudy"

        # Light rain still counts as cloudy
        if w.precipitation == "light_rain":
            return "cloudy"

        return "clear"

    # ---- Natural Disasters ----

    def check_disasters(self, game_day: int) -> List[DisasterEvent]:
        """Check conditions for natural disasters. Call once per day.

        Only checks a sparse random sample of regions (max ~8 per day) to
        keep the disaster count reasonable. Skips the first 5 days as warmup.
        """
        new_disasters: List[DisasterEvent] = []

        # Warmup: don't generate disasters in the first 5 days
        if game_day < 5:
            return new_disasters

        # Sample a sparse random subset of regions instead of the full grid
        step = 500
        max_checks = 8
        all_keys = list(self._dry_day_counts.keys())
        if not all_keys:
            return new_disasters
        check_keys = self.rng.sample(all_keys, min(max_checks, len(all_keys)))

        for key in check_keys:
                bx_idx, by_idx = key
                cx = bx_idx * step + step // 2
                cy = by_idx * step + step // 2
                if cx >= self.width or cy >= self.height:
                    continue
                dry_days = self._dry_day_counts.get(key, 0)
                rain_days = self._rain_day_counts.get(key, 0)
                w = self.get_local_weather(cx, cy)
                elev = self._get_elevation(cx, cy)

                # Flood: prolonged heavy rain near rivers / low elevation
                if rain_days >= 5 and elev < 0.35 and elev > 0.22:
                    d = DisasterEvent(
                        disaster_type="flood",
                        x=cx, y=cy, radius=300,
                        severity=min(1.0, rain_days / 10.0),
                        day_started=game_day,
                        duration_days=3,
                        description=f"Flooding near ({cx},{cy}) after {rain_days} days of rain",
                    )
                    new_disasters.append(d)

                # Drought: no rain for 10+ days on warm land
                if dry_days >= 10 and w.temperature > 25 and 0.22 < elev < 0.6:
                    d = DisasterEvent(
                        disaster_type="drought",
                        x=cx, y=cy, radius=400,
                        severity=min(1.0, dry_days / 20.0),
                        day_started=game_day,
                        duration_days=max(3, dry_days - 7),
                        description=f"Drought near ({cx},{cy}), {dry_days} dry days",
                    )
                    new_disasters.append(d)

                # Wildfire: drought + heat + forest (elevation 0.3-0.55 is typically forest)
                if (dry_days >= 12 and w.temperature > 30
                        and 0.30 < elev < 0.55):
                    if self.rng.random() < 0.15:
                        d = DisasterEvent(
                            disaster_type="wildfire",
                            x=cx, y=cy, radius=200,
                            severity=min(1.0, (w.temperature - 25) / 20.0),
                            day_started=game_day,
                            duration_days=self.rng.randint(2, 5),
                            description=f"Wildfire near ({cx},{cy})",
                        )
                        new_disasters.append(d)

                # Blizzard: winter + low pressure + high latitude (north = low y)
                lat_ratio = cy / max(1, self.height)
                if (self.season == "winter" and lat_ratio < 0.4
                        and w.condition in ("snow", "storm")):
                    if self.rng.random() < 0.2:
                        d = DisasterEvent(
                            disaster_type="blizzard",
                            x=cx, y=cy, radius=500,
                            severity=min(1.0, w.wind_speed + 0.3),
                            day_started=game_day,
                            duration_days=self.rng.randint(1, 3),
                            description=f"Blizzard near ({cx},{cy})",
                        )
                        new_disasters.append(d)

        self.active_disasters.extend(new_disasters)
        return new_disasters

    # ---- Weather Emotions ----

    def apply_weather_emotions(self, npcs, game_time: float = 0.0):
        """Trigger emotions on NPCs based on current weather at their location.

        Call once per game day (or less frequently). Imports lazily.
        """
        try:
            from game.systems.emotions import trigger_emotion
        except ImportError:
            return

        for npc in npcs:
            if not hasattr(npc, 'x') or not hasattr(npc, 'y'):
                continue
            w = self.get_local_weather(npc.x, npc.y)

            # Prolonged rain (3+ days)
            bucket = (int(npc.x) // 500, int(npc.y) // 500)
            rain_days = self._rain_day_counts.get(bucket, 0)
            if rain_days >= 3:
                trigger_emotion(npc, "weather_sad", intensity=0.2,
                                cause="prolonged rain", game_time=game_time)

            # Storm: fear for outdoor NPCs
            if w.condition == "storm":
                # Check if NPC is outdoors (no building overhead)
                is_outdoor = not getattr(npc, 'is_indoors', False)
                if is_outdoor:
                    trigger_emotion(npc, "weather_fear", intensity=0.3,
                                    cause="caught in a storm", game_time=game_time)

            # Perfect sunny day
            if (w.condition == "clear" and 15 < w.temperature < 28
                    and w.wind_speed < 0.3):
                trigger_emotion(npc, "weather_joy", intensity=0.15,
                                cause="beautiful sunny day", game_time=game_time)

            # Bitter cold
            if w.temperature < -5:
                trigger_emotion(npc, "weather_sad", intensity=0.2,
                                cause="bitter cold", game_time=game_time)
                trigger_emotion(npc, "weather_fear", intensity=0.1,
                                cause="dangerously cold", game_time=game_time)

    # ---- Queries ----

    def get_settlement_weather(self, settlement) -> LocalWeather:
        """Get weather for a settlement object (has .x, .y attributes)."""
        return self.get_local_weather(settlement.x, settlement.y)

    def get_disaster_at(self, x: float, y: float) -> Optional[DisasterEvent]:
        """Check if a position is affected by any active disaster."""
        for d in self.active_disasters:
            dx = x - d.x
            dy = y - d.y
            if dx * dx + dy * dy <= d.radius * d.radius:
                return d
        return None

    def get_pressure_systems_summary(self) -> List[Dict]:
        """Return summary of active pressure systems for UI/debug."""
        return [
            {
                "x": ps.x, "y": ps.y,
                "type": ps.pressure_type,
                "strength": ps.strength,
                "radius": ps.radius,
                "age": ps.age,
            }
            for ps in self.pressure_systems
        ]


# ================================================================
# WEATHER OVERLAY FOR WORLD MAP
# ================================================================

def draw_weather_overlay(screen, climate_model: ClimateModel,
                          cam_x: float, cam_y: float, zoom: float,
                          overlay_mode: str = "pressure"):
    """Draw weather information on the world map view.

    Args:
        screen: pygame surface.
        climate_model: ClimateModel instance.
        cam_x, cam_y: Camera center in world tiles.
        zoom: Pixels per tile.
        overlay_mode: "pressure", "temperature", or "wind".
    """
    import pygame

    sw = screen.get_width()
    sh = screen.get_height()

    tiles_vis_x = sw / zoom
    tiles_vis_y = sh / zoom
    x0 = cam_x - tiles_vis_x / 2
    y0 = cam_y - tiles_vis_y / 2

    if overlay_mode == "pressure":
        _draw_pressure_overlay(screen, climate_model, x0, y0, zoom, sw, sh)
    elif overlay_mode == "temperature":
        _draw_temperature_overlay(screen, climate_model, x0, y0, zoom, sw, sh)
    elif overlay_mode == "wind":
        _draw_wind_overlay(screen, climate_model, x0, y0, zoom, sw, sh)


def _draw_pressure_overlay(screen, cm: ClimateModel,
                             x0: float, y0: float, zoom: float,
                             sw: int, sh: int):
    """Draw colored pressure zones on the world map."""
    import pygame

    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)

    for ps in cm.pressure_systems:
        # Screen position
        sx = int((ps.x - x0) * zoom)
        sy = int((ps.y - y0) * zoom)
        sr = int(ps.radius * zoom)

        if sx + sr < 0 or sx - sr > sw or sy + sr < 0 or sy - sr > sh:
            continue  # off screen

        if sr < 2:
            continue

        # Color: blue for high (clear), red for low (rain)
        alpha = int(ps.strength * 60)
        if ps.pressure_type == "high":
            color = (80, 120, 220, alpha)
        else:
            color = (220, 80, 80, alpha)

        # Draw filled circle
        if sr > 0:
            circle_surf = pygame.Surface((sr * 2, sr * 2), pygame.SRCALPHA)
            pygame.draw.circle(circle_surf, color, (sr, sr), sr)
            overlay.blit(circle_surf, (sx - sr, sy - sr))

        # Label
        label = "H" if ps.pressure_type == "high" else "L"
        try:
            font = pygame.font.SysFont("monospace", max(10, min(20, sr // 3)))
            text = font.render(label, True, (255, 255, 255, 200))
            overlay.blit(text, (sx - text.get_width() // 2,
                                sy - text.get_height() // 2))
        except Exception:
            pass

    screen.blit(overlay, (0, 0))


def _draw_temperature_overlay(screen, cm: ClimateModel,
                                x0: float, y0: float, zoom: float,
                                sw: int, sh: int):
    """Draw temperature color bands."""
    import pygame

    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    step_screen = 20  # pixels between samples
    step_world = step_screen / max(0.01, zoom)

    for sx in range(0, sw, step_screen):
        for sy in range(0, sh, step_screen):
            wx = x0 + sx / zoom
            wy = y0 + sy / zoom
            if wx < 0 or wy < 0 or wx >= cm.width or wy >= cm.height:
                continue

            w = cm.get_local_weather(wx, wy)
            t = w.temperature

            # Color map: blue (-20) -> cyan (0) -> green (10) -> yellow (20) -> red (35) -> magenta (45)
            if t < 0:
                ratio = max(0, (t + 25) / 25)
                r = int(50 * (1 - ratio))
                g = int(100 * ratio)
                b = int(200 * ratio + 50 * (1 - ratio))
            elif t < 15:
                ratio = t / 15
                r = int(50 + 150 * ratio)
                g = int(150 + 80 * ratio)
                b = int(200 * (1 - ratio))
            elif t < 30:
                ratio = (t - 15) / 15
                r = int(200 + 40 * ratio)
                g = int(230 * (1 - ratio) + 80 * ratio)
                b = int(30 * (1 - ratio))
            else:
                ratio = min(1, (t - 30) / 15)
                r = int(240 + 15 * ratio)
                g = int(80 * (1 - ratio))
                b = int(80 * ratio)

            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))

            pygame.draw.rect(overlay, (r, g, b, 50),
                             (sx, sy, step_screen, step_screen))

    screen.blit(overlay, (0, 0))


def _draw_wind_overlay(screen, cm: ClimateModel,
                         x0: float, y0: float, zoom: float,
                         sw: int, sh: int):
    """Draw wind direction arrows."""
    import pygame

    step_screen = 40  # pixels between arrows

    for sx in range(step_screen, sw, step_screen):
        for sy in range(step_screen, sh, step_screen):
            wx = x0 + sx / zoom
            wy = y0 + sy / zoom
            if wx < 0 or wy < 0 or wx >= cm.width or wy >= cm.height:
                continue

            w = cm.get_local_weather(wx, wy)
            if w.wind_speed < 0.05:
                continue

            # Find wind direction from nearest pressure system
            best_dist = float('inf')
            wind_dx, wind_dy = 1.0, 0.0
            for ps in cm.pressure_systems:
                dx = wx - ps.x
                dy = wy - ps.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < best_dist and dist < ps.radius * 2:
                    best_dist = dist
                    # Wind flows clockwise around high, counter-clockwise around low
                    if dist > 1:
                        ndx, ndy = dx / dist, dy / dist
                        if ps.pressure_type == "high":
                            wind_dx = ndy + ndx * 0.3
                            wind_dy = -ndx + ndy * 0.3
                        else:
                            wind_dx = -ndy + ndx * 0.3
                            wind_dy = ndx + ndy * 0.3

            # Normalize and scale by wind_speed
            mag = math.sqrt(wind_dx * wind_dx + wind_dy * wind_dy)
            if mag > 0:
                wind_dx /= mag
                wind_dy /= mag

            length = 8 + w.wind_speed * 12
            ex = sx + wind_dx * length
            ey = sy + wind_dy * length

            alpha = int(100 + w.wind_speed * 155)
            color = (200, 200, 220)
            pygame.draw.line(screen, color, (sx, sy), (int(ex), int(ey)), 1)

            # Arrowhead
            head_len = 4
            angle = math.atan2(wind_dy, wind_dx)
            for da in [2.5, -2.5]:
                hx = ex - head_len * math.cos(angle + da)
                hy = ey - head_len * math.sin(angle + da)
                pygame.draw.line(screen, color, (int(ex), int(ey)),
                                 (int(hx), int(hy)), 1)
