"""
Physical attributes system — derives gameplay stats from D&D ability scores.

Connects ability scores and skills to concrete physical capabilities:
- Carry capacity (Strength + Constitution)
- Movement speed (Dexterity + Constitution, walk vs run)
- Map reading (Intelligence + literacy/navigation skills)
- Communication (Charisma + persuasion/performance skills)
- Endurance (Constitution — how long before exhaustion)
- Perception range (Wisdom + tracking/insight skills)

Also defines mounts and pack animals for transport.
"""

import math
from typing import Optional


# ================================================================
# DERIVED PHYSICAL STATS
# ================================================================

def calc_carry_capacity(entity) -> int:
    """Maximum items an NPC can carry, derived from STR + CON.
    Base: 8 items. STR adds 1 per 2 points above 10. CON adds 1 per 3 above 10.
    """
    scores = getattr(entity, 'ability_scores', {})
    str_val = scores.get("strength", 10)
    con_val = scores.get("constitution", 10)
    base = 8
    str_bonus = max(0, (str_val - 10) // 2)
    con_bonus = max(0, (con_val - 10) // 3)
    return base + str_bonus + con_bonus


def calc_walk_speed(entity) -> float:
    """Walking speed in tiles/sec, derived from DEX + CON + race.
    Base: 1.0. Modified by dexterity and constitution.
    """
    scores = getattr(entity, 'ability_scores', {})
    dex_val = scores.get("dexterity", 10)
    con_val = scores.get("constitution", 10)

    base = 1.0
    dex_mod = (dex_val - 10) * 0.03  # ±0.3 at extreme values
    con_mod = (con_val - 10) * 0.015  # ±0.15
    speed = base + dex_mod + con_mod

    # Race modifier
    race = getattr(entity, 'race', 'Human')
    race_speed = {
        "Elf": 0.15, "Dwarf": -0.1, "Halfling": -0.1,
        "Half-Orc": 0.05, "Gnome": -0.1,
    }
    speed += race_speed.get(race, 0)

    # Encumbrance — slow down if carrying too much
    inv = getattr(entity, 'npc_inventory', getattr(entity, 'inventory', []))
    capacity = calc_carry_capacity(entity)
    load_ratio = len(inv) / max(1, capacity)
    if load_ratio > 0.8:
        speed *= 0.85  # heavily loaded
    elif load_ratio > 1.0:
        speed *= 0.6   # overloaded

    return max(0.4, speed)


def calc_jog_speed(entity) -> float:
    """Jogging/trotting speed — 1.4x walk speed, light energy cost."""
    return calc_walk_speed(entity) * 1.4


def calc_run_speed(entity) -> float:
    """Running/galloping speed — 1.9x walk speed, heavy energy cost.
    High DEX and CON sustain running longer.
    """
    return calc_walk_speed(entity) * 1.9


# Movement gaits with speed multipliers and energy cost per second
MOVEMENT_GAITS = {
    "walk":   {"speed_mult": 1.0, "energy_cost": 0.0,  "label": "Walking"},
    "jog":    {"speed_mult": 1.4, "energy_cost": 2.0,  "label": "Jogging"},
    "run":    {"speed_mult": 1.9, "energy_cost": 5.0,  "label": "Running"},
    "sprint": {"speed_mult": 2.5, "energy_cost": 12.0, "label": "Sprinting"},
    "sneak":  {"speed_mult": 0.5, "energy_cost": 1.0,  "label": "Sneaking"},
}

# Creature gaits (different names, same mechanics)
CREATURE_GAITS = {
    "walk":    {"speed_mult": 1.0, "energy_cost": 0.0},
    "trot":    {"speed_mult": 1.4, "energy_cost": 1.5},
    "gallop":  {"speed_mult": 2.0, "energy_cost": 4.0},
    "charge":  {"speed_mult": 2.5, "energy_cost": 8.0},  # combat charge
}


def get_gait_speed(entity, gait: str = "walk") -> float:
    """Get movement speed for a specific gait.
    Uses the entity's base walk speed and applies the gait multiplier.
    """
    base = getattr(entity, 'speed', 1.0)  # stored walk speed
    gaits = MOVEMENT_GAITS if hasattr(entity, 'npc_skills') or hasattr(entity, 'skills') else CREATURE_GAITS
    gait_data = gaits.get(gait, gaits.get("walk", {"speed_mult": 1.0}))
    return base * gait_data["speed_mult"]


def apply_gait_energy_cost(entity, gait: str, dt: float) -> bool:
    """Drain energy for non-walking gaits. Returns False if out of energy."""
    gaits = MOVEMENT_GAITS if hasattr(entity, 'npc_skills') or hasattr(entity, 'skills') else CREATURE_GAITS
    gait_data = gaits.get(gait, gaits.get("walk"))
    cost = gait_data.get("energy_cost", 0)
    if cost <= 0:
        return True

    # NPCs use rest need as energy proxy
    if hasattr(entity, 'needs'):
        entity.needs["rest"] = max(0, entity.needs["rest"] - cost * dt * 0.5)
        if entity.needs["rest"] <= 5:
            return False  # too tired to run

    # Player has explicit energy
    if hasattr(entity, 'energy'):
        entity.energy = max(0, entity.energy - cost * dt)
        if entity.energy <= 0:
            return False

    return True


def calc_perception_range(entity) -> float:
    """How far the NPC can detect things, in tiles.
    Based on Wisdom + tracking/insight skills.
    """
    scores = getattr(entity, 'ability_scores', {})
    wis_val = scores.get("wisdom", 10)
    base = 6.0
    wis_mod = (wis_val - 10) * 0.4

    # Skill bonuses
    skills = getattr(entity, 'npc_skills', getattr(entity, 'skills', {}))
    tracking = skills.get("tracking", 0)
    insight = skills.get("insight", 0)
    skill_bonus = (tracking + insight) * 0.3

    return max(4.0, base + wis_mod + skill_bonus)


def calc_map_reading(entity) -> float:
    """How well the NPC can read maps and navigate, 0-1 scale.
    Based on Intelligence + literacy + navigation + cartography.
    """
    scores = getattr(entity, 'ability_scores', {})
    int_val = scores.get("intelligence", 10)
    base = (int_val - 5) / 15.0  # 0.33 at INT 10, 1.0 at INT 20

    skills = getattr(entity, 'npc_skills', getattr(entity, 'skills', {}))
    literacy = skills.get("literacy", 0)
    navigation = skills.get("navigation", 0)
    cartography = skills.get("cartography", 0)
    skill_bonus = (literacy + navigation + cartography) * 0.05

    return max(0.0, min(1.0, base + skill_bonus))


def calc_communication(entity) -> float:
    """How well the NPC communicates, 0-1 scale.
    Based on Charisma + persuasion + performance + literacy.
    """
    scores = getattr(entity, 'ability_scores', {})
    cha_val = scores.get("charisma", 10)
    base = (cha_val - 5) / 15.0

    skills = getattr(entity, 'npc_skills', getattr(entity, 'skills', {}))
    persuasion = skills.get("persuasion", 0)
    performance = skills.get("performance", 0)
    literacy = skills.get("literacy", 0)
    skill_bonus = (persuasion + performance + literacy) * 0.04

    return max(0.0, min(1.0, base + skill_bonus))


def apply_physical_stats(npc):
    """Apply derived physical stats to an NPC. Call after creation or level-up."""
    npc.speed = calc_walk_speed(npc)  # base walking speed
    npc.jog_speed = calc_jog_speed(npc)
    npc.run_speed = calc_run_speed(npc)
    npc.current_gait = "walk"  # walk, jog, run, sprint, sneak
    npc.carry_capacity = calc_carry_capacity(npc)
    npc.perception_range = calc_perception_range(npc)
    npc.map_reading = calc_map_reading(npc)
    npc.communication = calc_communication(npc)


# ================================================================
# MOUNTS AND PACK ANIMALS
# ================================================================

MOUNTS = {
    "horse": {
        "speed_mult": 2.5,  # 2.5x walking speed
        "carry_bonus": 8,   # can carry 8 extra items
        "cost": 50,         # gold to buy
        "feed_cost": 1.0,   # food per day
        "description": "A sturdy riding horse",
    },
    "war_horse": {
        "speed_mult": 2.2,
        "carry_bonus": 6,
        "cost": 120,
        "feed_cost": 1.5,
        "description": "A trained war horse, armored",
    },
    "donkey": {
        "speed_mult": 1.3,
        "carry_bonus": 12,  # excellent pack animal
        "cost": 15,
        "feed_cost": 0.5,
        "description": "A reliable pack donkey",
    },
    "cart": {
        "speed_mult": 0.8,  # slower than walking
        "carry_bonus": 30,  # huge capacity
        "cost": 50,
        "feed_cost": 0,     # no feed needed (but needs horse/donkey to pull)
        "description": "A wheeled cart for hauling goods",
        "requires": "donkey",  # needs an animal to pull
    },
}


# ================================================================
# FIRE SYSTEM — warmth, cooking, light, and danger
# ================================================================

# Fire states
FIRE_STATES = {
    "none": {"warmth": 0, "light": 0, "cook": False},
    "embers": {"warmth": 2, "light": 1, "cook": False},
    "small": {"warmth": 5, "light": 3, "cook": True},
    "medium": {"warmth": 8, "light": 5, "cook": True},
    "large": {"warmth": 10, "light": 8, "cook": True},
    "raging": {"warmth": 10, "light": 10, "cook": True, "dangerous": True},
}

# Fuel types and burn duration (game seconds)
FUEL_TYPES = {
    "Wood": {"duration": 120, "quality": "medium"},
    "Planks": {"duration": 100, "quality": "medium"},
    "Torch": {"duration": 60, "quality": "small"},
    "Resin": {"duration": 40, "quality": "small", "boost": True},  # makes fire flare up
    "Coal": {"duration": 200, "quality": "large"},  # slow steady burn
}

# Temperature effects by season (base comfort temperature)
SEASON_TEMP = {
    "spring": 12,  # °C equivalent, comfortable
    "summer": 22,  # warm, no fire needed
    "autumn": 8,   # cool, fire helpful
    "winter": -2,  # cold, fire essential
}


class Fire:
    """A fire at a specific location — campfire, hearth, forge, etc."""
    __slots__ = ('x', 'y', 'fuel_remaining', 'state', 'fire_type', 'indoor')

    def __init__(self, x: int, y: int, fire_type: str = "campfire", indoor: bool = False):
        self.x = x
        self.y = y
        self.fuel_remaining = 0.0  # seconds of fuel left
        self.state = "none"
        self.fire_type = fire_type  # campfire, hearth, forge, furnace
        self.indoor = indoor

    def add_fuel(self, fuel_item: str) -> bool:
        """Add fuel to the fire. Returns True if successful."""
        fuel = FUEL_TYPES.get(fuel_item)
        if not fuel:
            return False
        self.fuel_remaining += fuel["duration"]
        if self.state == "none":
            self.state = "small"
        elif fuel.get("boost") and self.state in ("small", "medium"):
            self.state = "large"
        return True

    def update(self, dt: float):
        """Update fire state based on remaining fuel."""
        if self.fuel_remaining <= 0:
            self.state = "none"
            return

        self.fuel_remaining -= dt
        if self.fuel_remaining <= 0:
            self.state = "embers" if self.state != "none" else "none"
            self.fuel_remaining = max(0, self.fuel_remaining)
            return

        # State transitions based on fuel level
        if self.fuel_remaining > 200:
            self.state = "large"
        elif self.fuel_remaining > 100:
            self.state = "medium"
        elif self.fuel_remaining > 30:
            self.state = "small"
        else:
            self.state = "embers"

    @property
    def warmth(self) -> int:
        return FIRE_STATES.get(self.state, {}).get("warmth", 0)

    @property
    def can_cook(self) -> bool:
        return FIRE_STATES.get(self.state, {}).get("cook", False)

    @property
    def light_radius(self) -> int:
        return FIRE_STATES.get(self.state, {}).get("light", 0)

    @property
    def is_dangerous(self) -> bool:
        return FIRE_STATES.get(self.state, {}).get("dangerous", False)


class FireManager:
    """Manages all fires in the world."""

    def __init__(self):
        self.fires: list = []
        self._update_timer = 0.0

    def create_fire(self, x: int, y: int, fire_type: str = "campfire",
                    indoor: bool = False) -> Fire:
        """Create a new fire at a location."""
        fire = Fire(x, y, fire_type, indoor)
        self.fires.append(fire)
        return fire

    def get_fire_near(self, x: float, y: float, radius: float = 3.0) -> Optional[Fire]:
        """Find the nearest fire within radius."""
        best = None
        best_dist = radius
        for fire in self.fires:
            if fire.state == "none":
                continue
            d = math.sqrt((fire.x - x) ** 2 + (fire.y - y) ** 2)
            if d < best_dist:
                best_dist = d
                best = fire
        return best

    def get_warmth_at(self, x: float, y: float) -> int:
        """Get total warmth from nearby fires at a position."""
        warmth = 0
        for fire in self.fires:
            if fire.state == "none":
                continue
            d = math.sqrt((fire.x - x) ** 2 + (fire.y - y) ** 2)
            if d < 5:
                # Warmth falls off with distance
                falloff = max(0, 1.0 - d / 5.0)
                warmth += int(fire.warmth * falloff)
        return warmth

    def update(self, dt: float):
        """Update all fires."""
        self._update_timer += dt
        if self._update_timer < 5.0:  # update every 5 seconds
            return
        self._update_timer = 0.0

        for fire in self.fires:
            fire.update(5.0)

        # Remove dead fires (keep hearths/forges as permanent fixtures)
        self.fires = [f for f in self.fires
                     if f.state != "none" or f.fire_type in ("hearth", "forge", "furnace")]

    def initialize_settlement_fires(self, structures: list, world):
        """Place permanent hearths in buildings and forges in workshops."""
        from game.settings import TABLE, FLOOR
        for s in structures:
            if s.kind not in ("village", "town", "city", "hamlet", "castle"):
                continue
            # Place hearths in buildings
            for bx, by, bw, bh in getattr(s, 'buildings', []):
                # Put a hearth in the center of each building
                hx = bx + bw // 2
                hy = by + bh // 2
                if 0 <= hx < world.width and 0 <= hy < world.height:
                    fire = self.create_fire(hx, hy, "hearth", indoor=True)
                    fire.fuel_remaining = 300  # start with fuel
                    fire.state = "medium"


def calc_warmth_need(season: str, is_night: bool, indoor: bool) -> int:
    """How much warmth an NPC needs to be comfortable.
    Returns warmth units needed (0 = no fire needed, 10 = desperate).
    """
    base_temp = SEASON_TEMP.get(season, 10)
    if is_night:
        base_temp -= 8
    if indoor:
        base_temp += 5  # buildings provide some shelter

    if base_temp >= 15:
        return 0  # warm enough
    elif base_temp >= 5:
        return 3  # mild chill, fire is nice
    elif base_temp >= -5:
        return 7  # cold, fire needed
    else:
        return 10  # freezing, fire essential


# ================================================================
# WORLD SCALE CONSTANTS
# ================================================================

# Aethermoor is a large island approximately 150km x 150km
# 1 tile = 75 meters
TILE_METERS = 75
ISLAND_KM = 150

# Walking speed in real-world terms
# NPC base 1.0 tiles/sec in game time = ~5km/h equivalent
# (compressed by the 144x time factor)
WALK_KM_PER_HOUR = 5.0
RUN_KM_PER_HOUR = 10.0
HORSE_KM_PER_HOUR = 15.0

# Travel time estimates (game hours)
def estimate_travel_hours(distance_tiles: float, speed_tiles_per_sec: float) -> float:
    """Estimate travel time in game hours."""
    if speed_tiles_per_sec <= 0:
        return 999
    game_seconds = distance_tiles / speed_tiles_per_sec
    game_hours = game_seconds / (600.0 / 24.0)  # 600s per day / 24 hours per day
    return game_hours


# ================================================================
# TERRAIN-AWARE MOVEMENT
# ================================================================

def get_terrain_speed_modifier(entity, terrain_type, world=None, x=0, y=0):
    """Get speed modifier considering skills, equipment, and mounts.

    Returns the effective walk cost for the terrain, adjusted by the entity's
    skills, mount, and other factors. Lower = faster travel.
    """
    from game.settings import (
        TERRAIN_WALK_COST, MOUNTAIN, SNOW, DENSE_FOREST, SWAMP, CLIFF,
        GORGE, MOUNTAIN_PASS, ROAD, GRAVEL_ROAD, DIRT_TRACK, COBBLESTONE,
    )

    base_cost = TERRAIN_WALK_COST.get(terrain_type, 1.0)

    # Skill-based terrain mastery
    skills = getattr(entity, 'npc_skills', getattr(entity, 'skills', {}))

    # Mountains: impassable without climbing >= 3 and rope
    if terrain_type == MOUNTAIN:
        climbing = skills.get('climbing', 0)
        has_rope = False
        inv = getattr(entity, 'npc_inventory', getattr(entity, 'inventory', []))
        for item in inv:
            item_name = getattr(item, 'name', str(item)).lower()
            if 'rope' in item_name:
                has_rope = True
                break
        if climbing >= 3 and has_rope:
            base_cost = 3.0  # passable but slow
            if climbing >= 6:
                base_cost = 2.0  # experienced climber
        # else stays 999 (impassable)

    # Cliffs: impassable without climbing >= 5
    if terrain_type == CLIFF:
        climbing = skills.get('climbing', 0)
        if climbing >= 5:
            base_cost = 3.5
            if climbing >= 8:
                base_cost = 2.5
        # else stays 999

    # Gorge: impassable without rope/bridge
    if terrain_type == GORGE:
        has_rope = False
        inv = getattr(entity, 'npc_inventory', getattr(entity, 'inventory', []))
        for item in inv:
            item_name = getattr(item, 'name', str(item)).lower()
            if 'rope' in item_name or 'grapple' in item_name:
                has_rope = True
                break
        if has_rope and skills.get('climbing', 0) >= 2:
            base_cost = 4.0

    # Snow: reduced cost with winter_survival skill
    if terrain_type == SNOW:
        winter_survival = skills.get('winter_survival', 0)
        if winter_survival >= 3:
            base_cost *= 0.6  # 2.5 * 0.6 = 1.5
            if winter_survival >= 6:
                base_cost *= 0.8  # even better

    # Dense forest: reduced cost with nature_lore skill
    if terrain_type == DENSE_FOREST:
        nature_lore = skills.get('nature_lore', 0)
        if nature_lore >= 3:
            base_cost *= 0.6  # 2.0 * 0.6 = 1.2
            if nature_lore >= 6:
                base_cost *= 0.8

    # Swamp: reduced cost with navigation skill
    if terrain_type == SWAMP:
        navigation = skills.get('navigation', 0)
        if navigation >= 3:
            base_cost *= 0.6  # 2.5 * 0.6 = 1.5
            if navigation >= 6:
                base_cost *= 0.8

    # Elevation gradient penalty (if world provides elevation data)
    if world and hasattr(world, 'elevation'):
        if 0 <= x < world.width and 0 <= y < world.height:
            current_elev = world.elevation[y][x]
            # Check neighbors for steepness
            max_slope = 0
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < world.width and 0 <= ny < world.height:
                    neighbor_elev = world.elevation[ny][nx]
                    slope = abs(neighbor_elev - current_elev)
                    max_slope = max(max_slope, slope)
            # Uphill penalty: up to 50% slower on steep terrain
            if max_slope > 0.05:
                uphill_penalty = 1.0 + min(0.5, max_slope * 3.0)
                base_cost *= uphill_penalty

    # Mount bonus on roads, penalty off-road
    mount = getattr(entity, 'mount', None)
    if mount is not None:
        if terrain_type in (ROAD, GRAVEL_ROAD, DIRT_TRACK, COBBLESTONE):
            base_cost *= 0.5  # horses are much faster on roads
        elif terrain_type in (DENSE_FOREST, SWAMP, MOUNTAIN):
            base_cost *= 1.5  # horses struggle off-road
        elif terrain_type == MOUNTAIN_PASS:
            base_cost *= 1.2  # horses slow on mountain passes

    return base_cost


def mount_entity(entity, mount) -> str:
    """Mount an entity onto a mount. Returns status message."""
    if not getattr(mount, 'alive', True):
        return f"{mount.name} is dead and cannot be ridden."
    entity.mount = mount
    mount.owner = getattr(entity, 'name', '')
    mount.is_resting = False
    if mount.hitched_at:
        mount.unhitch()
    entity._pre_mount_speed = getattr(entity, 'speed', 1.0)
    entity.speed = entity._pre_mount_speed * mount.get_effective_speed()
    return f"Mounted {mount.name} (speed x{mount.get_effective_speed():.1f})"


def dismount_entity(entity, hitch: bool = False):
    """Dismount an entity. Optionally hitch the mount at current position.

    Returns the mount object, or None if not mounted.
    """
    mount = getattr(entity, 'mount', None)
    if mount is None:
        return None
    entity.mount = None
    if hasattr(entity, '_pre_mount_speed'):
        entity.speed = entity._pre_mount_speed
        del entity._pre_mount_speed
    # Hitch mount at current position (for going indoors)
    if hitch and hasattr(entity, 'x'):
        mount.hitch(entity.x, entity.y)
    return mount


def update_mount(entity, dt: float, world=None):
    """Update mounted entity's mount each tick.

    Drains stamina based on movement, updates hunger/thirst,
    adjusts speed in real-time, handles mount death.

    Call this every tick when the entity is mounted.
    """
    mount = getattr(entity, 'mount', None)
    if not mount or not getattr(mount, 'alive', True):
        return

    # Update mount needs
    mount.update(dt)

    # Adjust speed dynamically based on mount condition
    if hasattr(entity, '_pre_mount_speed'):
        entity.speed = entity._pre_mount_speed * mount.get_effective_speed()

    # Track distance for stamina drain
    if hasattr(entity, 'vx') and hasattr(entity, 'vy'):
        vx = getattr(entity, 'vx', 0)
        vy = getattr(entity, 'vy', 0)
        import math
        speed = math.sqrt(vx * vx + vy * vy)
        if speed > 0.01:
            terrain = ROAD  # default
            if world and hasattr(world, 'tiles'):
                ix, iy = int(getattr(entity, 'x', 0)), int(getattr(entity, 'y', 0))
                if 0 <= ix < world.width and 0 <= iy < world.height:
                    terrain = world.tiles[iy][ix]
            mount.travel(speed * dt, terrain)

    # Mount death — auto dismount
    if not mount.alive:
        entity.mount = None
        if hasattr(entity, '_pre_mount_speed'):
            entity.speed = entity._pre_mount_speed
            del entity._pre_mount_speed
        # Return the dead mount name for notification
        entity._mount_died = mount.name


def get_effective_speed(entity) -> float:
    """Get the entity's effective movement speed considering all factors.

    Factors: base speed, mount, terrain (at current position), exhaustion,
    encumbrance, and active gait.
    """
    base_speed = getattr(entity, 'speed', 1.0)

    # Mount speed
    mount = getattr(entity, 'mount', None)
    if mount is not None:
        if hasattr(mount, 'get_effective_speed'):
            mount_mult = mount.get_effective_speed()
        else:
            mount_mult = mount.get('speed_mult', 1.0) if isinstance(mount, dict) else 2.0
        pre_mount = getattr(entity, '_pre_mount_speed', base_speed)
        base_speed = pre_mount * mount_mult

    # Gait multiplier
    gait = getattr(entity, 'current_gait', 'walk')
    gaits = MOVEMENT_GAITS if hasattr(entity, 'npc_skills') or hasattr(entity, 'skills') else CREATURE_GAITS
    gait_data = gaits.get(gait, gaits.get("walk", {"speed_mult": 1.0}))
    base_speed *= gait_data["speed_mult"]

    # Exhaustion penalty
    exhaustion_mult = getattr(entity, 'exhaustion_speed_mult', 1.0)
    base_speed *= exhaustion_mult

    # Encumbrance
    inv = getattr(entity, 'npc_inventory', getattr(entity, 'inventory', []))
    capacity = calc_carry_capacity(entity)
    if mount is not None:
        capacity += getattr(mount, 'carry_capacity', 8)
    load_ratio = len(inv) / max(1, capacity)
    if load_ratio > 1.0:
        base_speed *= 0.5  # severely overloaded
    elif load_ratio > 0.8:
        base_speed *= 0.8  # heavy load

    return max(0.2, base_speed)
