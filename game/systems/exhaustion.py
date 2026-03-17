"""
Exhaustion & Sleep System — realistic fatigue with progressive debuffs.

Sleep deprivation progresses through stages:
  RESTED → TIRED (12h) → EXHAUSTED (24h) → DELIRIOUS (36h) → UNCONSCIOUS (48h)

Each level imposes ability score penalties, speed reductions, and behavioral changes.
Constitution saves can delay progression. Sleeping recovers based on location quality.

Research: D&D 5e exhaustion rules (simplified), real sleep deprivation stages.
"""

import random
from typing import Dict, Optional


# ================================================================
# EXHAUSTION LEVELS
# ================================================================

EXHAUSTION_LEVELS = {
    0: {"name": "Rested",      "check_penalty": 0,  "speed_mult": 1.0,
        "can_cast": True,  "can_fight": True,  "wander": False},
    1: {"name": "Tired",       "check_penalty": -1, "speed_mult": 0.95,
        "can_cast": True,  "can_fight": True,  "wander": False},
    2: {"name": "Exhausted",   "check_penalty": -2, "speed_mult": 0.80,
        "can_cast": True,  "can_fight": True,  "wander": False},
    3: {"name": "Delirious",   "check_penalty": -4, "speed_mult": 0.50,
        "can_cast": False, "can_fight": False, "wander": True},
    4: {"name": "Unconscious", "check_penalty": -99, "speed_mult": 0.0,
        "can_cast": False, "can_fight": False, "wander": False},
}

# Hours awake before reaching each level
EXHAUSTION_THRESHOLDS = {
    1: 16.0,   # 16 hours awake → Tired
    2: 24.0,   # 24 hours → Exhausted
    3: 36.0,   # 36 hours → Delirious
    4: 48.0,   # 48 hours → Unconscious
}

# Sleep quality by location
SLEEP_QUALITY = {
    "bed":       {"recovery_rate": 1.0,  "full_rest_hours": 8.0,  "comfort": 1.0},
    "inn_bed":   {"recovery_rate": 1.0,  "full_rest_hours": 7.0,  "comfort": 1.0},
    "tavern":    {"recovery_rate": 0.8,  "full_rest_hours": 9.0,  "comfort": 0.7},
    "tent":      {"recovery_rate": 0.7,  "full_rest_hours": 10.0, "comfort": 0.6},
    "campfire":  {"recovery_rate": 0.6,  "full_rest_hours": 11.0, "comfort": 0.5},
    "ground":    {"recovery_rate": 0.4,  "full_rest_hours": 14.0, "comfort": 0.3},
    "rain":      {"recovery_rate": 0.2,  "full_rest_hours": 20.0, "comfort": 0.1},
}


# ================================================================
# EXHAUSTION SYSTEM
# ================================================================

class ExhaustionSystem:
    """Manages sleep/exhaustion for all entities."""

    def __init__(self):
        self._update_timer = 0.0

    def initialize_entity(self, entity):
        """Set up exhaustion tracking on an entity."""
        if not hasattr(entity, 'hours_awake'):
            entity.hours_awake = 0.0
        if not hasattr(entity, 'exhaustion_level'):
            entity.exhaustion_level = 0
        if not hasattr(entity, 'is_sleeping'):
            entity.is_sleeping = False
        if not hasattr(entity, 'sleep_location_quality'):
            entity.sleep_location_quality = "ground"
        if not hasattr(entity, 'sleep_hours_accumulated'):
            entity.sleep_hours_accumulated = 0.0
        if not hasattr(entity, '_exhaustion_penalties'):
            entity._exhaustion_penalties = {}

    def update(self, dt: float, entities: list, day_length: float = 600.0):
        """Update exhaustion for all entities. dt is real seconds."""
        self._update_timer += dt
        if self._update_timer < 5.0:
            return
        self._update_timer = 0.0

        # Convert 5 real seconds to game hours
        # DAY_LENGTH (600s) = 24 game hours
        game_hours = 5.0 * (24.0 / day_length)

        for entity in entities:
            if not getattr(entity, 'alive', True):
                continue
            self.initialize_entity(entity)
            self._update_entity(entity, game_hours)

    def _update_entity(self, entity, game_hours: float):
        """Update a single entity's exhaustion state."""
        # Undead and constructs don't need sleep
        race = getattr(entity, 'race', '')
        kind = getattr(entity, 'kind', '')
        if kind in ('skeleton', 'zombie', 'ghoul', 'wight', 'shadow'):
            return
        if race in ('Construct', 'Undead'):
            return

        if entity.is_sleeping:
            self._process_sleep(entity, game_hours)
        else:
            self._process_wakefulness(entity, game_hours)

    def _process_wakefulness(self, entity, game_hours: float):
        """Entity is awake — accumulate fatigue."""
        entity.hours_awake += game_hours

        # Check exhaustion level advancement
        old_level = entity.exhaustion_level
        new_level = 0
        for level, threshold in sorted(EXHAUSTION_THRESHOLDS.items()):
            if entity.hours_awake >= threshold:
                new_level = level
            else:
                break

        # Constitution save to resist advancement
        if new_level > old_level:
            con = getattr(entity, 'ability_scores', {}).get('constitution', 10)
            con_mod = (con - 10) // 2
            dc = 10 + (new_level * 2)
            roll = random.randint(1, 20) + con_mod
            if roll >= dc:
                # Resisted! Don't advance (but next check will be harder)
                new_level = old_level
            else:
                entity.exhaustion_level = new_level

        # Apply penalties
        self._apply_penalties(entity)

        # Unconscious entities collapse
        if entity.exhaustion_level >= 4:
            entity.is_sleeping = True
            entity.sleep_location_quality = "ground"
            entity.sleep_hours_accumulated = 0.0
            if hasattr(entity, 'state'):
                entity.state = "sleeping"
            if hasattr(entity, 'current_action'):
                entity.current_action = "collapsed_exhaustion"

    def _process_sleep(self, entity, game_hours: float):
        """Entity is sleeping — recover fatigue."""
        quality = SLEEP_QUALITY.get(entity.sleep_location_quality,
                                     SLEEP_QUALITY["ground"])
        recovery_rate = quality["recovery_rate"]

        # Accumulate sleep hours
        entity.sleep_hours_accumulated += game_hours * recovery_rate

        # Recovery: reduce hours_awake based on sleep quality
        entity.hours_awake = max(0, entity.hours_awake - game_hours * recovery_rate * 2.0)

        # Update exhaustion level based on reduced hours_awake
        new_level = 0
        for level, threshold in sorted(EXHAUSTION_THRESHOLDS.items()):
            if entity.hours_awake >= threshold:
                new_level = level
            else:
                break
        entity.exhaustion_level = new_level

        # Check if fully rested
        full_rest = quality["full_rest_hours"]
        if entity.sleep_hours_accumulated >= full_rest:
            entity.hours_awake = 0.0
            entity.exhaustion_level = 0
            entity.is_sleeping = False
            entity.sleep_hours_accumulated = 0.0
            self._remove_penalties(entity)
            if hasattr(entity, 'state') and entity.state == "sleeping":
                entity.state = "idle"
            if hasattr(entity, 'current_action') and "sleep" in entity.current_action:
                entity.current_action = ""

        self._apply_penalties(entity)

    def _apply_penalties(self, entity):
        """Apply exhaustion penalties to ability scores and speed."""
        level_data = EXHAUSTION_LEVELS.get(entity.exhaustion_level, EXHAUSTION_LEVELS[0])

        # Speed reduction
        base_speed = getattr(entity, '_base_speed_no_exhaustion', None)
        if base_speed is None:
            entity._base_speed_no_exhaustion = getattr(entity, 'speed', 1.0)
            base_speed = entity._base_speed_no_exhaustion
        entity.speed = base_speed * level_data["speed_mult"]

        # Store penalty info for skill checks
        entity._exhaustion_penalties = {
            "check_penalty": level_data["check_penalty"],
            "can_cast": level_data["can_cast"],
            "can_fight": level_data["can_fight"],
            "wander": level_data["wander"],
            "level": entity.exhaustion_level,
            "name": level_data["name"],
        }

    def _remove_penalties(self, entity):
        """Remove all exhaustion penalties."""
        if hasattr(entity, '_base_speed_no_exhaustion'):
            entity.speed = entity._base_speed_no_exhaustion
        entity._exhaustion_penalties = {
            "check_penalty": 0, "can_cast": True, "can_fight": True,
            "wander": False, "level": 0, "name": "Rested",
        }

    def start_sleep(self, entity, location_quality: str = "ground"):
        """Begin sleeping for an entity."""
        self.initialize_entity(entity)
        entity.is_sleeping = True
        entity.sleep_location_quality = location_quality
        entity.sleep_hours_accumulated = 0.0
        if hasattr(entity, 'state'):
            entity.state = "sleeping"

    def wake_up(self, entity):
        """Wake an entity (interrupted sleep)."""
        self.initialize_entity(entity)
        entity.is_sleeping = False
        if hasattr(entity, 'state') and entity.state == "sleeping":
            entity.state = "idle"

    def get_sleep_quality_at(self, entity, world=None, structures=None) -> str:
        """Determine sleep quality based on entity's location."""
        from game.settings import BED, FLOOR, ROAD

        if world is None:
            return "ground"

        x, y = int(getattr(entity, 'x', 0)), int(getattr(entity, 'y', 0))

        # Check if on a bed tile
        tile = world.tiles[y][x] if 0 <= x < world.width and 0 <= y < world.height else None
        if tile == BED:
            return "bed"

        # Check if in a settlement structure
        if structures:
            for s in structures:
                if s.kind in ("village", "town", "city", "hamlet", "castle"):
                    dx = abs(x - s.x)
                    dy = abs(y - s.y)
                    if dx <= s.radius and dy <= s.radius:
                        # Inside settlement - check for tavern/inn nearby
                        for s2 in structures:
                            if s2.kind in ("tavern",) and abs(x - s2.x) < 10 and abs(y - s2.y) < 10:
                                return "tavern"
                        # Inside a building floor
                        if tile == FLOOR:
                            return "inn_bed"
                        return "campfire"  # settlement but outdoors

        # Check for nearby fire
        if tile == FLOOR:
            return "tent"  # indoor but not a proper bed

        # Outdoors
        return "ground"

    def get_exhaustion_summary(self, entity) -> str:
        """Get human-readable exhaustion status."""
        self.initialize_entity(entity)
        level_data = EXHAUSTION_LEVELS.get(entity.exhaustion_level, EXHAUSTION_LEVELS[0])
        hours = entity.hours_awake
        if entity.is_sleeping:
            return f"Sleeping ({entity.sleep_hours_accumulated:.1f}h, {entity.sleep_location_quality})"
        return f"{level_data['name']} (awake {hours:.1f}h)"
