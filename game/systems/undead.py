"""Undead & Soul Predation system.

Undead creatures hunt living NPCs and creatures to drain and consume their
souls.  Necromancer NPCs can raise corpses.  Priests and consecrated ground
provide counter-measures.

Undead types (ordered by power):
  skeleton  - weakest, animated by ambient dark magic or necromancers
  zombie    - slow shambling corpse
  ghoul     - feeds on corpses and weak souls
  wight     - stronger melee undead
  wraith    - fast ghost-like, directly attacks souls
  vampire   - intelligent, hunts at night, drains souls slowly
  lich      - powerful mage undead, commands lesser undead
"""

import math
import random
from typing import Dict, List, Optional, Tuple

from game.data.ecology import UNDEAD_CREATURES, UNDEAD_POWER


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOUL_DRAIN_RANGE = 3.0           # tiles — undead must be this close to drain
SOUL_DRAIN_HP_PER_SEC = 1.0      # HP drained per second per power level
SOUL_DRAIN_MAXHP_PER_SEC = 0.1   # permanent max_hp reduction per second
POWER_PER_CONSUMED_SOUL = 0.1    # power gain when a soul is consumed
HOLY_DAMAGE_MULT = 2.0           # blessed weapons deal 2x to undead

CORPSE_RISE_BASE_CHANCE = 0.002  # per-second chance for unburied corpse to rise
NECRO_RAISE_COOLDOWN = 60.0      # seconds between necromancer raises
MASS_GRAVE_SPAWN_CHANCE = 0.005  # per-second chance at mass-grave sites (night)

CONSECRATED_RADIUS = 15.0        # tiles — radius of temple consecrated ground
WARD_RADIUS = 10.0               # tiles — radius of a priest ward
WARD_SPAWN_REDUCTION = 0.8       # 80% reduction inside ward

ACTIVE_RANGE = 100.0             # only process undead within this of the player

SOUL_POOL_LOW_THRESHOLD = 0.20   # warn when <20% souls remain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dist_sq(ax: float, ay: float, bx: float, by: float) -> float:
    dx = ax - bx
    dy = ay - by
    return dx * dx + dy * dy


def _is_undead(creature) -> bool:
    """Check whether a creature is undead."""
    if getattr(creature, "undead", False):
        return True
    kind = getattr(creature, "kind", "")
    if kind in UNDEAD_CREATURES:
        return True
    mtype = getattr(creature, "monster_type", "")
    return mtype == "undead"


def _is_night(time_sys) -> bool:
    """Return True if it is currently night-time."""
    if time_sys is None:
        return False
    if hasattr(time_sys, "is_night"):
        return time_sys.is_night
    norm = getattr(time_sys, "normalized", 0.3)
    return norm > 0.75 or norm < 0.25


def _undead_power(creature) -> float:
    """Return the power level of an undead creature."""
    base = UNDEAD_POWER.get(getattr(creature, "kind", ""), 1.0)
    # Accumulated power from consumed souls
    extra = getattr(creature, "consumed_soul_power", 0.0)
    return base + extra


# ---------------------------------------------------------------------------
# UndeadSystem
# ---------------------------------------------------------------------------

class UndeadSystem:
    """Manages undead hunting, soul draining, spawning, and counter-measures."""

    def __init__(self, soul_system):
        self.soul_system = soul_system
        self.active_undead: List = []        # creature references (refreshed each tick)
        self.necromancers: List = []          # NPC references (refreshed each tick)
        self.soul_drain_events: List[Dict] = []   # event log
        self._initial_soul_count: Optional[int] = None
        self._low_pool_warned: bool = False
        self._consecrated_zones: List[Tuple[float, float, float]] = []  # (x, y, radius)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, dt: float, game_time: float, creatures: list,
               npcs: list, world, time_sys=None, player=None):
        """Main tick — undead hunt for souls, corpses rise, priests ward."""
        # Snapshot initial soul count on first tick
        if self._initial_soul_count is None:
            pool = self.soul_system.pool
            self._initial_soul_count = max(1, len(pool.souls) + pool.statistical_soul_count)

        # Refresh active lists (only near player for performance)
        px = getattr(player, "x", 0.0) if player else 0.0
        py = getattr(player, "y", 0.0) if player else 0.0
        active_range_sq = ACTIVE_RANGE * ACTIVE_RANGE

        self.active_undead = [
            c for c in creatures
            if c.alive and _is_undead(c)
            and _dist_sq(c.x, c.y, px, py) <= active_range_sq
        ]

        self.necromancers = [
            n for n in npcs
            if n.alive and getattr(n, "profession", "") == "Necromancer"
            and _dist_sq(n.x, n.y, px, py) <= active_range_sq
        ]

        night = _is_night(time_sys)

        # Core subsystems
        self._undead_hunt(dt, creatures, npcs, game_time, night)
        self._check_necromancer_activity(npcs, creatures, game_time, world)
        self._check_corpse_rising(dt, creatures, npcs, world, night, time_sys)
        self._check_soul_pool_health()

    def get_event_log(self) -> List[str]:
        """Return and clear recent drain/spawn events."""
        msgs = [e["msg"] for e in self.soul_drain_events]
        self.soul_drain_events.clear()
        return msgs

    def register_consecrated_zone(self, x: float, y: float,
                                   radius: float = CONSECRATED_RADIUS):
        """Register a consecrated area (temple, churchyard) that repels undead."""
        self._consecrated_zones.append((x, y, radius))

    def is_consecrated(self, x: float, y: float) -> bool:
        """Return True if position is on consecrated ground."""
        for cx, cy, cr in self._consecrated_zones:
            if _dist_sq(x, y, cx, cy) <= cr * cr:
                return True
        return False

    # ------------------------------------------------------------------
    # Soul drain
    # ------------------------------------------------------------------

    def _undead_hunt(self, dt: float, creatures: list, npcs: list,
                     game_time: float, night: bool):
        """Undead creatures seek living targets to drain souls."""
        if not self.active_undead:
            return

        drain_range_sq = SOUL_DRAIN_RANGE * SOUL_DRAIN_RANGE

        for undead in self.active_undead:
            # Vampires only hunt at night
            kind = getattr(undead, "kind", "")
            if kind == "vampire" and not night:
                continue

            # Undead on consecrated ground are repelled (skip their turn)
            if self.is_consecrated(undead.x, undead.y):
                continue

            power = _undead_power(undead)

            # Find nearest living target in drain range
            best_target = None
            best_dist_sq = drain_range_sq + 1

            for npc in npcs:
                if not npc.alive:
                    continue
                dsq = _dist_sq(undead.x, undead.y, npc.x, npc.y)
                if dsq <= drain_range_sq and dsq < best_dist_sq:
                    # Skip targets on consecrated ground
                    if not self.is_consecrated(npc.x, npc.y):
                        best_target = npc
                        best_dist_sq = dsq

            if best_target is None:
                continue

            # --- Perform soul drain ---
            hp_drain = SOUL_DRAIN_HP_PER_SEC * power * dt
            maxhp_drain = SOUL_DRAIN_MAXHP_PER_SEC * dt

            best_target.hp = max(0, best_target.hp - hp_drain)
            best_target.max_hp = max(1, best_target.max_hp - maxhp_drain)

            # Check if victim died from drain
            if best_target.hp <= 0:
                best_target.alive = False
                self._on_drain_kill(undead, best_target, game_time)

    def _on_drain_kill(self, undead, victim, game_time: float):
        """Handle a victim killed by soul drain — consume their soul."""
        soul_id = getattr(victim, "soul_id", None)
        soul = self.soul_system.pool.souls.get(soul_id) if soul_id is not None else None

        victim_name = getattr(victim, "name", getattr(victim, "kind", "unknown"))
        undead_kind = getattr(undead, "kind", "undead")

        if soul is not None:
            self.on_soul_consumed(undead, victim, soul)
        else:
            # No tracked soul — still log the kill
            self.soul_drain_events.append({
                "msg": f"A {undead_kind} drained the life from {victim_name}.",
                "undead": undead_kind,
                "victim": victim_name,
                "type": "drain_kill",
            })

    def on_soul_consumed(self, undead_creature, victim, soul):
        """Handle a soul being consumed by undead.

        - Transfers the strongest echo memory to the undead
        - Increases undead power
        - Removes the soul from the pool permanently
        - Logs the event
        """
        victim_name = getattr(victim, "name", getattr(victim, "kind", "unknown"))
        undead_kind = getattr(undead_creature, "kind", "undead")

        # Transfer strongest echo memory
        if soul.echo_memories:
            strongest = max(soul.echo_memories, key=lambda m: m.intensity)
            if not hasattr(undead_creature, "echo_memories"):
                undead_creature.echo_memories = []
            undead_creature.echo_memories.append(strongest)
            # Cap at 10 memories per undead
            if len(undead_creature.echo_memories) > 10:
                undead_creature.echo_memories.sort(
                    key=lambda m: m.intensity, reverse=True)
                undead_creature.echo_memories = undead_creature.echo_memories[:10]

        # Increase undead power from consumed souls
        if not hasattr(undead_creature, "consumed_soul_power"):
            undead_creature.consumed_soul_power = 0.0
        undead_creature.consumed_soul_power += POWER_PER_CONSUMED_SOUL

        # Mark the soul as consumed and remove from pool
        soul.state = "consumed"
        soul.death_type = "undead"
        transferred = self.soul_system.on_soul_consumed(
            soul.soul_id, undead_kind)

        # Log the event
        self.soul_drain_events.append({
            "msg": (f"A {undead_kind} consumed the soul of {victim_name}! "
                    f"The soul is lost forever."),
            "undead": undead_kind,
            "victim": victim_name,
            "soul_id": soul.soul_id,
            "type": "soul_consumed",
        })

    # ------------------------------------------------------------------
    # Exorcism — freeing consumed souls when undead is killed
    # ------------------------------------------------------------------

    def on_undead_killed(self, undead_creature):
        """When an undead with consumed souls is killed, free its stored
        echo memories as new ghost souls back into the pool."""
        memories = getattr(undead_creature, "echo_memories", [])
        consumed_power = getattr(undead_creature, "consumed_soul_power", 0.0)
        undead_kind = getattr(undead_creature, "kind", "undead")

        if not memories and consumed_power <= 0:
            return

        # Estimate how many souls were consumed (power / POWER_PER_CONSUMED_SOUL)
        num_freed = max(1, int(consumed_power / POWER_PER_CONSUMED_SOUL))

        pool = self.soul_system.pool
        freed_count = 0
        for i in range(num_freed):
            if len(pool.souls) >= pool.MAX_TRACKED_SOULS:
                # Just increment statistical count
                pool.statistical_soul_count += 1
                freed_count += 1
                continue
            # Create a new ghost soul carrying one of the memories
            new_soul = pool.create_soul()
            new_soul.state = "ghost"
            new_soul.ghost_x = getattr(undead_creature, "x", 0.0)
            new_soul.ghost_y = getattr(undead_creature, "y", 0.0)
            new_soul.last_death_x = new_soul.ghost_x
            new_soul.last_death_y = new_soul.ghost_y
            new_soul.ghost_duration = random.uniform(20.0, 60.0)
            new_soul.time_as_ghost = 0.0
            new_soul.death_type = "violent"
            # Transfer a memory if available
            if i < len(memories):
                new_soul.echo_memories.append(memories[i])
            pool.ghost_souls.append(new_soul.soul_id)
            freed_count += 1

        if freed_count > 0:
            self.soul_drain_events.append({
                "msg": (f"A {undead_kind} was destroyed! "
                        f"{freed_count} trapped soul(s) freed as ghosts."),
                "undead": undead_kind,
                "freed": freed_count,
                "type": "exorcism",
            })

    # ------------------------------------------------------------------
    # Necromancer activity
    # ------------------------------------------------------------------

    def _check_necromancer_activity(self, npcs: list, creatures: list,
                                    game_time: float, world):
        """Necromancer NPCs animate nearby corpses as undead."""
        for necro in self.necromancers:
            # Cooldown
            last_raise = getattr(necro, "_necro_last_raise", 0.0)
            if game_time - last_raise < NECRO_RAISE_COOLDOWN:
                continue

            # Look for dead creatures nearby to animate
            for creature in creatures:
                if creature.alive:
                    continue
                if _dist_sq(necro.x, necro.y, creature.x, creature.y) > 100:
                    continue  # within 10 tiles
                if _is_undead(creature):
                    continue  # already undead

                # Raise as skeleton
                self._raise_as_undead(creature, "skeleton")
                necro._necro_last_raise = game_time
                self.soul_drain_events.append({
                    "msg": (f"Necromancer {necro.name} raised a skeleton "
                            f"from the dead at ({int(creature.x)}, {int(creature.y)})."),
                    "type": "necromancer_raise",
                })
                break  # one raise per tick

    # ------------------------------------------------------------------
    # Corpse rising (ambient undead spawning)
    # ------------------------------------------------------------------

    def _check_corpse_rising(self, dt: float, creatures: list, npcs: list,
                              world, night: bool, time_sys):
        """Unburied corpses may rise as undead, especially at night
        near lingering ghosts."""
        if not night:
            return  # only at night

        for creature in creatures:
            if creature.alive:
                continue
            if _is_undead(creature):
                continue
            # Skip if on consecrated ground
            if self.is_consecrated(creature.x, creature.y):
                continue

            # Base chance, boosted by nearby ghosts
            ghost_count = len(self.soul_system.get_ghost_souls_near(
                creature.x, creature.y, radius=15.0))
            chance = CORPSE_RISE_BASE_CHANCE * dt * (1.0 + ghost_count * 0.5)

            # Ward reduction
            if self._in_ward_zone(creature.x, creature.y, npcs):
                chance *= (1.0 - WARD_SPAWN_REDUCTION)

            if random.random() < chance:
                # Determine what kind of undead rises
                kind = self._pick_risen_kind(ghost_count)
                self._raise_as_undead(creature, kind)
                self.soul_drain_events.append({
                    "msg": (f"A corpse has risen as a {kind} at "
                            f"({int(creature.x)}, {int(creature.y)})!"),
                    "type": "corpse_rise",
                })

    def _pick_risen_kind(self, ghost_count: int) -> str:
        """Choose what type of undead a corpse rises as, weighted by
        nearby ghost density."""
        if ghost_count >= 5:
            choices = ["skeleton", "zombie", "ghoul", "wight"]
            weights = [30, 30, 25, 15]
        elif ghost_count >= 2:
            choices = ["skeleton", "zombie", "ghoul"]
            weights = [40, 40, 20]
        else:
            choices = ["skeleton", "zombie"]
            weights = [60, 40]
        return random.choices(choices, weights=weights, k=1)[0]

    def _raise_as_undead(self, creature, kind: str):
        """Transform a dead creature into an active undead of the given kind."""
        from game.data.dnd import MONSTERS

        creature.alive = True
        creature.kind = kind
        creature.undead = True
        creature.consumed_soul_power = 0.0
        creature.echo_memories = []

        # Apply stats from monster data
        if kind in MONSTERS:
            stats = MONSTERS[kind]
            creature.max_hp = stats["hp"]
            creature.hp = stats["hp"]
            creature.damage = stats["damage"]
            creature.speed = stats.get("speed", 1.8)
            creature.xp_value = stats["xp"]
            creature.color = stats["color"]
            creature.armor_class = stats.get("ac", 10)
            creature.monster_type = "undead"
            creature.cr = stats.get("cr", 0.25)
            creature.passive = False
        else:
            # Minimal fallback
            creature.max_hp = 20
            creature.hp = 20
            creature.damage = 6
            creature.speed = 1.6
            creature.monster_type = "undead"
            creature.passive = False

        creature.state = "wandering"
        creature.home_x = creature.x
        creature.home_y = creature.y
        creature.leash_range = 30.0  # undead wander further

    # ------------------------------------------------------------------
    # Counter-measures
    # ------------------------------------------------------------------

    def _in_ward_zone(self, x: float, y: float, npcs: list) -> bool:
        """Return True if position is within a priest's ward zone."""
        ward_sq = WARD_RADIUS * WARD_RADIUS
        for npc in npcs:
            if not npc.alive:
                continue
            prof = getattr(npc, "profession", "")
            char_class = getattr(npc, "char_class", "")
            if prof in ("Priest", "Cleric", "Healer") or char_class in ("Cleric", "Paladin"):
                # Check divine skill level — higher skill = larger ward
                skills = getattr(npc, "npc_skills", {})
                divine_level = skills.get("religion", skills.get("healing", 0))
                effective_radius_sq = ward_sq * (1.0 + divine_level * 0.1)
                if _dist_sq(x, y, npc.x, npc.y) <= effective_radius_sq:
                    return True
        return False

    def initialize_consecrated_zones(self, world):
        """Scan world structures for temples and churchyards and register
        them as consecrated zones."""
        self._consecrated_zones.clear()
        for s in getattr(world, "structures", []):
            kind = getattr(s, "kind", "")
            if kind in ("temple", "church", "monastery", "shrine"):
                self.register_consecrated_zone(
                    s.x, s.y, CONSECRATED_RADIUS)

    @staticmethod
    def is_holy_weapon(item) -> bool:
        """Check if an item is a holy/blessed weapon (deals 2x to undead)."""
        if item is None:
            return False
        name = getattr(item, "name", "")
        if "Holy" in name or "Blessed" in name:
            return True
        tags = getattr(item, "tags", set())
        return "holy" in tags or "blessed" in tags

    @staticmethod
    def compute_damage_to_undead(base_damage: float, weapon=None) -> float:
        """Compute damage dealt to an undead creature, applying holy bonus."""
        if UndeadSystem.is_holy_weapon(weapon):
            return base_damage * HOLY_DAMAGE_MULT
        return base_damage

    # ------------------------------------------------------------------
    # Soul pool health check
    # ------------------------------------------------------------------

    def _check_soul_pool_health(self):
        """Warn if the soul pool is getting dangerously low."""
        pool = self.soul_system.pool
        current = len(pool.souls) + pool.statistical_soul_count
        ratio = current / max(1, self._initial_soul_count)

        if ratio < SOUL_POOL_LOW_THRESHOLD and not self._low_pool_warned:
            self._low_pool_warned = True
            self.soul_drain_events.append({
                "msg": ("The world grows dim — fewer than 20% of souls remain. "
                        "The balance between life and death is in peril."),
                "type": "soul_pool_low",
                "ratio": ratio,
            })
        elif ratio >= SOUL_POOL_LOW_THRESHOLD:
            self._low_pool_warned = False
