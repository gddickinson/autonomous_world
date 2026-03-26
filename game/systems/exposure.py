"""Environmental exposure damage from adverse weather and temperature.

Entities (NPCs, creatures, player) take damage from temperature extremes
they are not adapted or equipped for. Status effects accumulate over time.
Called every 30 ticks from the simulation loop for performance.
"""
from __future__ import annotations
import math, random
from dataclasses import dataclass
from typing import Dict, TYPE_CHECKING
if TYPE_CHECKING:
    from game.systems.climate import ClimateModel

# Temperature zones and damage rates (HP per 30-tick exposure check)
DAMAGE = {"freezing": 0.2, "cold": 0.05, "hot": 0.03, "scorching": 0.15}
HYPOTHERMIA_TICKS, HEATSTROKE_TICKS, FROSTBITE_TICKS = 60, 60, 120
SANDSTORM_DPS = 0.02

# Race tolerance offsets (degrees C added to comfort range)
RACE_COLD = {"Dwarf": 10, "Half-Orc": 10, "Gnome": 5}
RACE_HEAT = {"Elf": 5, "Half-Elf": 3, "Half-Orc": 10, "Tiefling": 8}

# Equipment that grants protection
COLD_ITEMS = {"Cloak", "Fur Cloak", "Winter Cloak", "Wolf Pelt",
              "Wool Cloth", "Wool", "Cloak of Many Stars"}
HEAT_ITEMS = {"Robe", "Linen", "Waterskin", "Water Flask"}

# Creature biome sets for immunity classification
_COLD_BIOMES = {"snow", "tundra"}
_HOT_BIOMES = {"sand", "desert"}
_FIRE_KINDS = {"phoenix", "fire_elemental"}
_ICE_KINDS = {"ice_elemental", "frost_giant"}


def _temp_zone(t: float) -> str:
    if t < -5: return "freezing"
    if t < 5: return "cold"
    if t <= 30: return "comfortable"
    if t <= 40: return "hot"
    return "scorching"


@dataclass
class ExposureState:
    """Tracks per-entity exposure accumulation."""
    cold_ticks: int = 0
    heat_ticks: int = 0
    has_hypothermia: bool = False
    has_heatstroke: bool = False
    has_frostbite: bool = False
    frostbite_hp_lost: int = 0
    damage_label: str = ""   # "COLD" / "HOT" / ""
    tint: str = ""           # "blue" / "red" / ""


def _get_exposure(entity) -> ExposureState:
    s = getattr(entity, "exposure_state", None)
    if s is None:
        s = ExposureState()
        entity.exposure_state = s
    return s


# -- Weather felt-temperature modifiers --

def _weather_mod(weather) -> float:
    mod = 0.0
    cond = getattr(weather, "condition", "clear")
    precip = getattr(weather, "precipitation", "none")
    if precip in ("rain", "heavy_rain", "light_rain"):
        mod -= 5.0
    if cond == "snow" or (cond == "storm" and precip == "snow"):
        mod -= 10.0
    if cond == "heat_wave":
        mod += 5.0
    return mod


# -- Protection checks --

def _is_indoors(entity, world) -> bool:
    if world is None:
        return False
    x, y = int(getattr(entity, "x", 0)), int(getattr(entity, "y", 0))
    from game.settings import FLOOR, BED, BUILT_FLOOR, STABLE_FLOOR
    if 0 <= x < world.width and 0 <= y < world.height:
        return world.tiles[y][x] in (FLOOR, BED, BUILT_FLOOR, STABLE_FLOOR)
    return False


def _near_fireplace(entity, world) -> bool:
    if world is None:
        return False
    x, y = int(getattr(entity, "x", 0)), int(getattr(entity, "y", 0))
    from game.settings import FIREPLACE
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            nx, ny = x + dx, y + dy
            if 0 <= nx < world.width and 0 <= ny < world.height:
                if world.tiles[ny][nx] == FIREPLACE:
                    return True
    return False


def _cold_resist(entity) -> float:
    b = RACE_COLD.get(getattr(entity, "race", ""), 0.0)
    inv = getattr(entity, "npc_inventory", None) or getattr(entity, "inventory", [])
    for item in inv:
        if getattr(item, "name", "") in COLD_ITEMS:
            return b + 10.0
    return b


def _heat_resist(entity) -> float:
    b = RACE_HEAT.get(getattr(entity, "race", ""), 0.0)
    inv = getattr(entity, "npc_inventory", None) or getattr(entity, "inventory", [])
    for item in inv:
        if getattr(item, "name", "") in HEAT_ITEMS:
            return b + 8.0
    return b


# -- Creature immunity classification --

def _creature_immunity(creature):
    """Return (cold_immune, heat_immune, extra_cold_vuln, extra_heat_vuln)."""
    kind = getattr(creature, "kind", "").lower()
    mtype = getattr(creature, "monster_type", "beast")
    if mtype == "undead":
        return (True, True, False, False)
    if kind in _FIRE_KINDS:
        return (False, True, True, False)
    if kind in _ICE_KINDS:
        return (True, False, False, True)
    try:
        from game.data.dnd import MONSTERS
        biomes = set(MONSTERS.get(kind, {}).get("biomes", []))
    except ImportError:
        biomes = set()
    if biomes & _COLD_BIOMES:
        return (True, False, False, True)
    if biomes & _HOT_BIOMES:
        return (False, True, True, False)
    return (False, False, False, False)


# ================================================================
# MAIN UPDATE
# ================================================================

def update(npcs, creatures, player, climate, world, event_log=None,
           time_sys=None):
    """Process environmental exposure for all entities."""
    if climate is None:
        return
    if player is not None and getattr(player, "alive", False):
        _process_entity(player, climate, world, event_log, is_player=True)
    for npc in npcs:
        if getattr(npc, "alive", False):
            _process_entity(npc, climate, world, event_log, is_npc=True,
                            time_sys=time_sys)
    for creature in creatures:
        if getattr(creature, "alive", False):
            _process_creature(creature, climate, world, event_log)


def _process_entity(entity, climate, world, event_log,
                    is_player=False, is_npc=False, time_sys=None):
    """Process exposure for an NPC or the player."""
    weather = climate.get_local_weather(
        getattr(entity, "x", 0), getattr(entity, "y", 0))
    felt = weather.temperature + _weather_mod(weather)
    state = _get_exposure(entity)

    # Indoor protection: full shelter, decay exposure, clear seeking_shelter
    if _is_indoors(entity, world):
        _decay_exposure(state)
        # Clear shelter-seeking immediately when inside a building
        if is_npc and getattr(entity, "current_action", "") == "seeking_shelter":
            entity.current_action = ""
            entity.current_goal = ""
        return

    if _near_fireplace(entity, world):
        felt += 15.0

    eff_cold = felt + _cold_resist(entity)
    eff_heat = felt - _heat_resist(entity)
    state.damage_label = ""
    state.tint = ""

    # -- Cold --
    cz = _temp_zone(eff_cold)
    if cz in ("freezing", "cold"):
        entity.hp = max(0, getattr(entity, "hp", 0) - DAMAGE[cz])
        state.cold_ticks += 1
        state.damage_label, state.tint = "COLD", "blue"
        if state.cold_ticks >= HYPOTHERMIA_TICKS and not state.has_hypothermia:
            state.has_hypothermia = True
            if is_npc:
                entity.add_memory("exposure",
                                  "Suffering from hypothermia", 4)
        if (felt < -10 and state.cold_ticks >= FROSTBITE_TICKS
                and not state.has_frostbite):
            state.has_frostbite = True
            state.frostbite_hp_lost = 5
            entity.max_hp = max(1, getattr(entity, "max_hp", 10) - 5)
            entity.hp = min(entity.hp, entity.max_hp)
            if is_npc:
                entity.add_memory("exposure", "Frostbite!", 5)
        if entity.hp <= 0:
            entity._death_cause = "exposure_cold"
            entity.alive = False
            if event_log is not None and is_npc:
                event_log.append(
                    f"{getattr(entity, 'name', '?')} froze to death!")
    else:
        if state.cold_ticks > 0:
            state.cold_ticks = max(0, state.cold_ticks - 2)
        if state.cold_ticks == 0:
            state.has_hypothermia = False

    # -- Heat --
    hz = _temp_zone(eff_heat)
    if hz in ("hot", "scorching"):
        entity.hp = max(0, getattr(entity, "hp", 0) - DAMAGE[hz])
        state.heat_ticks += 1
        state.damage_label, state.tint = "HOT", "red"
        if state.heat_ticks >= HEATSTROKE_TICKS and not state.has_heatstroke:
            state.has_heatstroke = True
            if is_npc:
                entity.add_memory("exposure", "Heatstroke!", 4)
        needs = getattr(entity, "needs", None)
        if needs and "thirst" in needs:
            needs["thirst"] = max(0, needs["thirst"] - 0.5)
        if entity.hp <= 0:
            entity._death_cause = "exposure_heat"
            entity.alive = False
            if event_log is not None and is_npc:
                event_log.append(
                    f"{getattr(entity, 'name', '?')} died of heatstroke!")
    else:
        if state.heat_ticks > 0:
            state.heat_ticks = max(0, state.heat_ticks - 2)
        if state.heat_ticks == 0:
            state.has_heatstroke = False

    # -- Sandstorm --
    if (getattr(weather, "condition", "") == "heat_wave"
            and getattr(weather, "wind_speed", 0) > 0.5):
        entity.hp = max(0, getattr(entity, "hp", 0) - SANDSTORM_DPS)

    # -- NPC shelter seeking --
    # Only trigger when ACTUALLY taking damage (not just non-ideal zone)
    # and only at night (after 20:00) or during storms
    if is_npc and state.damage_label:
        _npc_seek_shelter(entity, state, world, weather, time_sys)


def _process_creature(creature, climate, world, event_log):
    """Process exposure for a creature, considering biome immunity."""
    weather = climate.get_local_weather(
        getattr(creature, "x", 0), getattr(creature, "y", 0))
    felt = weather.temperature + _weather_mod(weather)
    cold_imm, heat_imm, extra_cold, extra_heat = _creature_immunity(creature)
    state = _get_exposure(creature)
    state.damage_label, state.tint = "", ""
    zone = _temp_zone(felt)

    if zone in ("freezing", "cold"):
        if not cold_imm:
            dmg = DAMAGE[zone] * (2.0 if extra_cold else 1.0)
            creature.hp = max(0, getattr(creature, "hp", 0) - dmg)
            state.cold_ticks += 1
            state.damage_label, state.tint = "COLD", "blue"
        else:
            state.cold_ticks = 0
    if zone in ("hot", "scorching"):
        if not heat_imm:
            dmg = DAMAGE[zone] * (2.0 if extra_heat else 1.0)
            creature.hp = max(0, getattr(creature, "hp", 0) - dmg)
            state.heat_ticks += 1
            state.damage_label, state.tint = "HOT", "red"
        else:
            state.heat_ticks = 0
    if zone == "comfortable":
        state.cold_ticks = max(0, state.cold_ticks - 2)
        state.heat_ticks = max(0, state.heat_ticks - 2)

    if state.damage_label and getattr(creature, "state", "") == "wandering":
        _creature_migrate(creature, state)
    if creature.hp <= 0:
        creature.alive = False


def _decay_exposure(state: ExposureState):
    state.cold_ticks = max(0, state.cold_ticks - 3)
    state.heat_ticks = max(0, state.heat_ticks - 3)
    state.has_hypothermia = state.cold_ticks >= HYPOTHERMIA_TICKS
    state.has_heatstroke = state.heat_ticks >= HEATSTROKE_TICKS
    state.damage_label, state.tint = "", ""


# -- NPC shelter seeking --

def _npc_seek_shelter(npc, state, world, weather=None, time_sys=None):
    """NPCs seek shelter only when actually in danger.

    Guards NEVER seek shelter (they patrol regardless).
    Only triggers at night (after 20:00) or during storms, not during
    comfortable daytime weather. Requires 10+ exposure ticks so minor
    temperature dips don't cause mass shelter-seeking.
    """
    # Guards never seek shelter
    prof = getattr(npc, "profession", "").lower()
    title = getattr(npc, "title", "").lower()
    if title == "guard" or prof in ("guard", "soldier", "captain", "knight"):
        return

    ca = getattr(npc, "current_action", "")
    if ca in ("fighting", "fleeing", "sleeping", "seeking_shelter"):
        return

    # Require significant exposure accumulation (10 ticks, not 3)
    if max(state.cold_ticks, state.heat_ticks) < 10:
        return

    # Time-of-day gate: only seek shelter at night or during storms
    is_storm = False
    if weather is not None:
        cond = getattr(weather, "condition", "clear")
        is_storm = cond in ("storm", "blizzard", "heat_wave")

    is_night = False
    if time_sys is not None:
        norm = getattr(time_sys, "normalized", 0.5)
        is_night = norm > 0.83 or norm < 0.17  # after ~20:00 or before ~04:00
    else:
        # Fallback: allow shelter-seeking if we can't check time
        is_night = True

    if not is_night and not is_storm:
        return

    npc.current_action = "seeking_shelter"
    npc.current_goal = "find shelter from the elements"
    hx, hy = getattr(npc, "home_x", None), getattr(npc, "home_y", None)
    if hx is not None:
        npc.target_x, npc.target_y = hx, hy
        npc.state = "walking"


# -- Creature migration --

def _creature_migrate(creature, state):
    """Nudge creature toward preferred biome (its home location)."""
    hx = getattr(creature, "home_x", None)
    hy = getattr(creature, "home_y", None)
    if hx is None:
        return
    cx, cy = getattr(creature, "x", 0), getattr(creature, "y", 0)
    dx, dy = hx - cx, hy - cy
    if math.sqrt(dx * dx + dy * dy) < 2:
        angle = random.uniform(0, 2 * math.pi)
        creature.home_x = cx + math.cos(angle) * 10
        creature.home_y = cy + math.sin(angle) * 10


# ================================================================
# STATUS EFFECT QUERIES (for rendering / other systems)
# ================================================================

def get_speed_modifier(entity) -> float:
    """Speed multiplier from exposure (hypothermia -30%, heatstroke -20%)."""
    s = getattr(entity, "exposure_state", None)
    if s is None:
        return 1.0
    m = 1.0
    if s.has_hypothermia:
        m *= 0.7
    if s.has_heatstroke:
        m *= 0.8
    return m


def get_attack_modifier(entity) -> float:
    """Attack multiplier (hypothermia -20%)."""
    s = getattr(entity, "exposure_state", None)
    if s is None or not s.has_hypothermia:
        return 1.0
    return 0.8


def get_action_label(entity) -> str:
    """'shivering' / 'overheated' / '' for UI display."""
    s = getattr(entity, "exposure_state", None)
    if s is None:
        return ""
    if s.has_hypothermia:
        return "shivering"
    if s.has_heatstroke:
        return "overheated"
    return ""


def get_visual_tint(entity) -> str:
    """'blue' / 'red' / '' for rendering overlay."""
    s = getattr(entity, "exposure_state", None)
    return s.tint if s else ""


def get_damage_label(entity) -> str:
    """'COLD' / 'HOT' / '' for floating damage text."""
    s = getattr(entity, "exposure_state", None)
    return s.damage_label if s else ""


def heal_frostbite(entity):
    """Cure frostbite at a temple, restoring lost max HP."""
    s = getattr(entity, "exposure_state", None)
    if s is None or not s.has_frostbite:
        return
    entity.max_hp = getattr(entity, "max_hp", 10) + s.frostbite_hp_lost
    s.has_frostbite = False
    s.frostbite_hp_lost = 0
