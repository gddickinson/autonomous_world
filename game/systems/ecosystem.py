"""
Ecosystem Manager — connects creature needs, vegetation, and NPC responses
into cascading feedback loops.

Runs every ~5 seconds (heavy, region-based analysis):
- Predator-prey balance adjustments
- Overhunting detection
- Population pressure on breeding
- Crop pest events (deer eating farmland)
- Livestock predation by wolves
- Food web cascading (predator migration when prey scarce)
- Settlement response triggers
"""

import math
import random
from typing import Dict, List, Tuple, Optional, Set

from game.data.ecology import PREDATOR_PREY, BREEDING_CREATURES
from game.settings import FARMLAND, WHEAT_FIELD

# Normal baseline populations per species (for "30% of normal" checks)
_NORMAL_POP = 10

# Overpopulation / underpopulation thresholds (within 50-tile radius)
_OVERPOP_THRESHOLD = 20
_UNDERPOP_THRESHOLD = 3

# Overhunting: if NPCs kill >50% of a species in a day, penalise spawns
_OVERHUNT_FRACTION = 0.50

# Crop pest chance per herbivore near farmland per update cycle
_PEST_CHANCE = 0.10

# Wolf livestock predation chance per update cycle
_WOLF_LIVESTOCK_CHANCE = 0.05

# Migration nudge distance when prey is scarce
_MIGRATION_NUDGE = 5.0

# Species considered crop pests near farmland
_PEST_SPECIES = {"deer", "rabbit", "elk", "wild_boar", "boar"}

# Species that attack livestock
_LIVESTOCK_PREDATORS = {"wolf", "dire_wolf", "mountain_lion", "bear"}


class EcosystemManager:
    """Master ecosystem tick that wires creature needs, vegetation,
    and NPC ecology responses together."""

    def __init__(self):
        # NPC kill tracking: {species: count} resets each game-day
        self.npc_kills: Dict[str, int] = {}
        self._last_kill_day: int = -1

        # Spawn rate modifiers from overhunting: {species: multiplier}
        self.spawn_modifiers: Dict[str, float] = {}

        # Predator attack history: {settlement_name: count}
        self.predator_attacks: Dict[str, int] = {}

        # Timer accumulator (update called every tick, we throttle to ~5s)
        self._accum: float = 0.0
        self._update_interval: float = 5.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_npc_kill(self, creature_kind: str):
        """Called when an NPC kills a creature (from npc_work hunting)."""
        self.npc_kills[creature_kind] = self.npc_kills.get(creature_kind, 0) + 1

    def update(self, dt: float, world, creatures, npcs, time_sys,
               vegetation=None, creature_grid=None, npc_grid=None,
               world_effects=None, event_log=None):
        """Master tick.  Internally throttled to self._update_interval."""
        self._accum += dt
        if self._accum < self._update_interval:
            return
        self._accum = 0.0

        if event_log is None:
            event_log = []

        season = getattr(time_sys, 'season', 'summer')
        day = getattr(time_sys, 'day', 0)

        # Reset daily kill counter
        if day != self._last_kill_day:
            self._process_overhunting(creatures)
            self.npc_kills.clear()
            self._last_kill_day = day

        # Census
        counts, positions = self._census(creatures)
        total = sum(counts.values())

        # Predator-prey balance
        self._predator_prey_balance(creatures, counts)

        # Population pressure on breeding
        self._population_pressure(creatures, creature_grid)

        # Crop pest events
        if vegetation is not None:
            self._crop_pests(creatures, world, vegetation, event_log)

        # Livestock predation
        if world_effects is not None:
            self._livestock_predation(creatures, world, world_effects,
                                       event_log, npcs)

        # Food web cascading (predator migration)
        self._food_web_migration(creatures, counts, creature_grid)

    # ------------------------------------------------------------------
    # Predator-prey balance
    # ------------------------------------------------------------------

    def _predator_prey_balance(self, creatures, counts: Dict[str, int]):
        """Adjust hunger rates based on prey availability."""
        for predator_kind, prey_list in PREDATOR_PREY.items():
            pred_count = counts.get(predator_kind, 0)
            if pred_count == 0:
                continue
            prey_total = sum(counts.get(p, 0) for p in prey_list)

            # Prey scarce → predators get hungrier faster
            if prey_total < pred_count:
                hunger_mult = 1.5
            elif prey_total == 0:
                hunger_mult = 2.0
            else:
                hunger_mult = 1.0

            if hunger_mult > 1.0:
                for c in creatures:
                    if c.alive and c.kind == predator_kind:
                        # Accelerate hunger decay
                        c.hunger = max(0.0, c.hunger - (hunger_mult - 1.0) * 0.5)

            # Prey has few predators → breed bonus handled via population_pressure
            if pred_count == 0 and prey_total > 0:
                for p_kind in prey_list:
                    # Mark for breeding boost (used by ecology system's breeding)
                    self.spawn_modifiers[p_kind] = self.spawn_modifiers.get(
                        p_kind, 1.0) * 1.5

    # ------------------------------------------------------------------
    # Overhunting detection
    # ------------------------------------------------------------------

    def _process_overhunting(self, creatures):
        """Check if NPCs over-hunted any species yesterday.  If so, reduce
        spawn modifier for that species."""
        # Count living creatures per species
        alive: Dict[str, int] = {}
        for c in creatures:
            if c.alive:
                alive[c.kind] = alive.get(c.kind, 0) + 1

        for species, kill_count in self.npc_kills.items():
            pop = alive.get(species, 0) + kill_count  # estimate pre-hunt pop
            if pop > 0 and kill_count / pop > _OVERHUNT_FRACTION:
                # Reduce spawn rate
                self.spawn_modifiers[species] = max(
                    0.1, self.spawn_modifiers.get(species, 1.0) * 0.5)
            else:
                # Slowly recover spawn rate toward 1.0
                cur = self.spawn_modifiers.get(species, 1.0)
                if cur < 1.0:
                    self.spawn_modifiers[species] = min(1.0, cur + 0.1)

    # ------------------------------------------------------------------
    # Population pressure
    # ------------------------------------------------------------------

    def _population_pressure(self, creatures, creature_grid):
        """Adjust breeding rates based on local density.

        This sets a transient flag on creatures that the existing
        EcologySystem breeding loop can read.
        """
        if creature_grid is None:
            return

        # Sample up to 30 creatures to avoid O(n^2)
        sample = [c for c in creatures if c.alive]
        if len(sample) > 30:
            sample = random.sample(sample, 30)

        for c in sample:
            nearby = creature_grid.get_nearby_of_kind(
                c.x, c.y, 50.0, c.kind)
            local_count = len(nearby)

            if local_count >= _OVERPOP_THRESHOLD:
                c._breed_modifier = 0.0
            elif local_count < _UNDERPOP_THRESHOLD:
                c._breed_modifier = 2.0
            else:
                c._breed_modifier = 1.0

    # ------------------------------------------------------------------
    # Crop pest events
    # ------------------------------------------------------------------

    def _crop_pests(self, creatures, world, vegetation, event_log):
        """Herbivores near farmland may eat crops."""
        for c in creatures:
            if not c.alive:
                continue
            if c.kind not in _PEST_SPECIES:
                continue
            if random.random() > _PEST_CHANCE:
                continue

            # Check if near a farm tile
            ix, iy = int(c.x), int(c.y)
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    tx, ty = ix + dx, iy + dy
                    try:
                        tile = (world.tiles.get_tile(tx, ty)
                                if hasattr(world.tiles, 'get_tile')
                                else world.tiles[ty][tx])
                    except (IndexError, KeyError):
                        continue
                    if tile in (FARMLAND, WHEAT_FIELD):
                        food = vegetation.graze_at(tx, ty, world)
                        if food > 0:
                            c.hunger = min(100.0, c.hunger + food)
                            # Only graze one tile per cycle
                            return

    # ------------------------------------------------------------------
    # Livestock predation
    # ------------------------------------------------------------------

    def _livestock_predation(self, creatures, world, world_effects,
                              event_log, npcs):
        """Wolves/predators near settlements may kill livestock."""
        structures = getattr(world, 'structures', [])
        for s in structures:
            if s.kind not in ("village", "town", "city", "hamlet", "castle"):
                continue

            livestock = world_effects.get_settlement_livestock(s.name)
            sheep_count = livestock.get("sheep", 0)
            if sheep_count <= 0:
                continue

            # Check for nearby predators
            for c in creatures:
                if not c.alive:
                    continue
                if c.kind not in _LIVESTOCK_PREDATORS:
                    continue
                d2 = (c.x - s.x) ** 2 + (c.y - s.y) ** 2
                if d2 > 30 * 30:
                    continue

                if random.random() < _WOLF_LIVESTOCK_CHANCE:
                    # Wolf kills a sheep
                    world_effects.remove_livestock(s.name, "sheep", 1)
                    c.hunger = min(100.0, 80.0)
                    event_log.append(
                        f"A {c.kind} attacked livestock near {s.name}!")

                    # Track attacks for settlement response
                    self.predator_attacks[s.name] = (
                        self.predator_attacks.get(s.name, 0) + 1)

                    # Trigger NPC response
                    from game.systems.npc_ecology import respond_to_predator_attack
                    respond_to_predator_attack(s, c.kind, npcs, event_log)
                    break  # one attack per settlement per cycle

    # ------------------------------------------------------------------
    # Food web cascading (predator migration)
    # ------------------------------------------------------------------

    def _food_web_migration(self, creatures, counts, creature_grid):
        """When prey is scarce, predators shift home toward prey-rich areas."""
        for predator_kind, prey_list in PREDATOR_PREY.items():
            prey_total = sum(counts.get(p, 0) for p in prey_list)
            if prey_total >= _NORMAL_POP * 0.3:
                continue  # prey is fine

            # Prey dangerously low — migrate predators toward remaining prey
            prey_positions = []
            for c in creatures:
                if c.alive and c.kind in prey_list:
                    prey_positions.append((c.x, c.y))

            if not prey_positions:
                continue

            # Average prey position
            avg_x = sum(p[0] for p in prey_positions) / len(prey_positions)
            avg_y = sum(p[1] for p in prey_positions) / len(prey_positions)

            for c in creatures:
                if not c.alive or c.kind != predator_kind:
                    continue
                dx = avg_x - c.home_x
                dy = avg_y - c.home_y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 1.0:
                    nudge = min(_MIGRATION_NUDGE, dist * 0.3)
                    c.home_x += dx / dist * nudge
                    c.home_y += dy / dist * nudge

    # ------------------------------------------------------------------
    # Census
    # ------------------------------------------------------------------

    @staticmethod
    def _census(creatures) -> Tuple[Dict[str, int], Dict[str, List]]:
        """Count creatures by kind and collect positions."""
        counts: Dict[str, int] = {}
        positions: Dict[str, List] = {}
        for c in creatures:
            if not c.alive:
                continue
            counts[c.kind] = counts.get(c.kind, 0) + 1
            if c.kind not in positions:
                positions[c.kind] = []
            positions[c.kind].append((c.x, c.y))
        return counts, positions
