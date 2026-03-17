"""
Health, Disease, and Medicine System.

Manages NPC health conditions (diseases, infections, injuries), contagion
spread, seasonal illness, wound infection, and medical treatment.

Designed for efficiency:
- Disease spread checked every 30s (timer-gated)
- Seasonal illness checked once per game day
- Wound infection checked every 60s
- Condition advancement runs every tick but is just float arithmetic
"""

import copy
import math
import random
from typing import List, Dict, Optional, Set


# ================================================================
# HEALTH CONDITION
# ================================================================

class HealthCondition:
    """A single active health condition on an NPC."""

    __slots__ = ("name", "severity", "duration", "elapsed", "contagious",
                 "spread_rate", "symptoms", "stat_modifiers", "immunity_after")

    def __init__(self, name: str, severity: float, duration: float,
                 contagious: bool = False, spread_rate: float = 0.0,
                 symptoms: Optional[List[str]] = None,
                 stat_modifiers: Optional[Dict[str, float]] = None,
                 immunity_after: bool = False):
        self.name = name
        self.severity = severity          # 0-1 (0.1=mild, 0.5=serious, 1.0=fatal)
        self.duration = duration          # game days
        self.elapsed = 0.0               # game days elapsed
        self.contagious = contagious
        self.spread_rate = spread_rate    # chance per day per nearby NPC
        self.symptoms = symptoms or []    # ["fever", "cough", "weakness"]
        self.stat_modifiers = stat_modifiers or {}  # {"speed": 0.5, "work": 0.3}
        self.immunity_after = immunity_after


def _clone_condition(template: HealthCondition) -> HealthCondition:
    """Create a fresh instance from a disease template."""
    c = HealthCondition.__new__(HealthCondition)
    c.name = template.name
    c.severity = template.severity
    c.duration = template.duration
    c.elapsed = 0.0
    c.contagious = template.contagious
    c.spread_rate = template.spread_rate
    c.symptoms = list(template.symptoms)
    c.stat_modifiers = dict(template.stat_modifiers)
    c.immunity_after = template.immunity_after
    return c


# ================================================================
# DISEASE DEFINITIONS
# ================================================================

DISEASES: Dict[str, HealthCondition] = {
    # -- Seasonal --
    "common_cold": HealthCondition(
        "Common Cold", severity=0.1, duration=5, contagious=True,
        spread_rate=0.15, symptoms=["cough", "sneezing"],
        stat_modifiers={"work": 0.9}, immunity_after=False),
    "flu": HealthCondition(
        "Flu", severity=0.3, duration=8, contagious=True,
        spread_rate=0.1, symptoms=["fever", "weakness", "bedridden"],
        stat_modifiers={"work": 0.3, "speed": 0.5}, immunity_after=True),
    "frostbite": HealthCondition(
        "Frostbite", severity=0.4, duration=15,
        symptoms=["pain", "numbness"],
        stat_modifiers={"speed": 0.6, "work": 0.7}),
    "heatstroke": HealthCondition(
        "Heatstroke", severity=0.5, duration=3,
        symptoms=["confusion", "collapse"],
        stat_modifiers={"work": 0.0, "speed": 0.3}),
    "food_poisoning": HealthCondition(
        "Food Poisoning", severity=0.2, duration=3,
        symptoms=["nausea", "weakness"],
        stat_modifiers={"work": 0.4}),

    # -- Infections --
    "wound_infection": HealthCondition(
        "Wound Infection", severity=0.4, duration=10,
        symptoms=["fever", "swelling"],
        stat_modifiers={"work": 0.5, "combat": 0.6}),
    "sepsis": HealthCondition(
        "Sepsis", severity=0.9, duration=5,
        symptoms=["high_fever", "delirium"],
        stat_modifiers={"work": 0.0, "speed": 0.2}),

    # -- Contagious diseases --
    "plague": HealthCondition(
        "Plague", severity=0.8, duration=12, contagious=True,
        spread_rate=0.08, symptoms=["boils", "fever", "weakness"],
        stat_modifiers={"work": 0.0, "speed": 0.3}, immunity_after=True),
    "pox": HealthCondition(
        "Pox", severity=0.4, duration=14, contagious=True,
        spread_rate=0.12, symptoms=["rash", "fever"],
        stat_modifiers={"work": 0.5}, immunity_after=True),
    "consumption": HealthCondition(
        "Consumption", severity=0.5, duration=60, contagious=True,
        spread_rate=0.03, symptoms=["cough", "wasting"],
        stat_modifiers={"work": 0.6, "speed": 0.7}),
    "swamp_fever": HealthCondition(
        "Swamp Fever", severity=0.5, duration=7,
        symptoms=["fever", "chills", "recurring"],
        stat_modifiers={"work": 0.4, "speed": 0.6}),
    "red_death": HealthCondition(
        "Red Death", severity=0.9, duration=4, contagious=True,
        spread_rate=0.2, symptoms=["bloody_vomit", "dehydration"],
        stat_modifiers={"work": 0.0, "speed": 0.1}),
    "dysentery": HealthCondition(
        "Dysentery", severity=0.4, duration=7, contagious=True,
        spread_rate=0.06, symptoms=["dehydration", "weakness"],
        stat_modifiers={"work": 0.3, "speed": 0.6}),
}

# Disease keys by category for quick lookup
_CONTAGIOUS_DISEASES = [k for k, v in DISEASES.items() if v.contagious]
_SEASONAL_WINTER = ["common_cold", "flu", "frostbite"]
_SEASONAL_SUMMER = ["heatstroke"]
_SEASONAL_SPRING = ["food_poisoning"]


# ================================================================
# NPC HEALTH ATTRIBUTE INITIALIZATION
# ================================================================

def ensure_health_attrs(npc):
    """Attach health attributes to an NPC if missing.

    Called lazily on first interaction with the health system.
    """
    if not hasattr(npc, 'conditions'):
        npc.conditions = []
    if not hasattr(npc, 'immunities'):
        npc.immunities = set()
    if not hasattr(npc, 'constitution_base'):
        con = 10
        if hasattr(npc, 'ability_scores'):
            con = npc.ability_scores.get("constitution", 10)
        npc.constitution_base = con
    if not hasattr(npc, 'immune_strength'):
        # Derive from constitution: CON 8 -> 0.3, CON 10 -> 0.5, CON 16 -> 0.8
        con = getattr(npc, 'constitution_base', 10)
        npc.immune_strength = max(0.1, min(0.95, 0.5 + (con - 10) * 0.05))
    if not hasattr(npc, '_wound_infection_timer'):
        npc._wound_infection_timer = 0.0
    if not hasattr(npc, '_last_hp'):
        npc._last_hp = getattr(npc, 'hp', getattr(npc, 'max_hp', 10))


# ================================================================
# CROWDING MODIFIER
# ================================================================

_SETTLEMENT_CROWDING = {
    "city": 1.5,
    "town": 1.2,
    "village": 1.0,
    "hamlet": 0.5,
    "castle": 0.8,
}


def _get_crowding(npc) -> float:
    """Return crowding modifier based on nearest settlement type."""
    settlement = getattr(npc, 'home_settlement', '')
    if not settlement:
        return 0.7  # wilderness
    # Try to infer settlement kind from name conventions
    kind = getattr(npc, '_home_settlement_kind', None)
    if kind:
        return _SETTLEMENT_CROWDING.get(kind, 1.0)
    return 1.0


# ================================================================
# HEALTH SYSTEM
# ================================================================

class HealthSystem:
    """Manages disease, injury, treatment, and contagion for all NPCs."""

    def __init__(self):
        self.outbreak_log: List[Dict] = []   # history of epidemics
        self.event_log: List[str] = []
        self._spread_timer = 0.0             # accumulates dt for 30s spread checks
        self._seasonal_timer = 0.0           # accumulates dt for daily seasonal checks
        self._wound_timer = 0.0              # accumulates dt for 60s wound checks
        self._last_seasonal_day = -1
        self.on_death = None                 # callback(npc, cause) set by SimulationManager
        self._pending_deaths: List = []      # NPCs that died this tick from disease

    # ----------------------------------------------------------------
    # MAIN UPDATE
    # ----------------------------------------------------------------

    def update(self, dt: float, game_day: int, season: str, npcs: list,
               world=None, climate=None, npc_grid=None,
               trade_system=None, active_set=None):
        """Main tick -- advance conditions, check spread, seasonal checks.

        Args:
            dt: Delta time in seconds (may be scaled by tick multiplier).
            game_day: Current game day counter.
            season: "spring", "summer", "autumn", "winter".
            npcs: List of all NPC objects.
            world: World object (for biome/tile lookups).
            climate: Optional climate data.
            npc_grid: SpatialGrid for O(1) nearby lookups.
            trade_system: TradeSystem for trade route contagion.
            active_set: Set of active NPC names (skip dormant NPCs for
                        expensive checks, but still advance their conditions).
        """
        # Convert dt (seconds) to game-day fraction.
        # Assume ~600 seconds per game day (DAY_LENGTH from settings).
        from game.settings import DAY_LENGTH
        day_frac = dt / DAY_LENGTH

        # 1. Advance all conditions every tick (cheap: just float math)
        self._advance_conditions(day_frac, npcs)

        # Process any disease deaths via callback
        if self._pending_deaths and self.on_death:
            for dead_npc, cause in self._pending_deaths:
                self.on_death(dead_npc, cause)
            self._pending_deaths.clear()
        elif self._pending_deaths:
            self._pending_deaths.clear()

        # 2. Contagion spread -- every 30s of real time
        self._spread_timer += dt
        if self._spread_timer >= 30.0:
            self._spread_timer = 0.0
            self._check_spread(npcs, npc_grid, trade_system)

        # 3. Seasonal illness -- once per game day
        if game_day != self._last_seasonal_day:
            self._last_seasonal_day = game_day
            self._check_seasonal_illness(game_day, season, npcs, world)

        # 4. Wound infection -- every 60s
        self._wound_timer += dt
        if self._wound_timer >= 60.0:
            self._wound_timer = 0.0
            self._check_wound_infection(npcs)

    # ----------------------------------------------------------------
    # CONDITION ADVANCEMENT
    # ----------------------------------------------------------------

    def _advance_conditions(self, day_frac: float, npcs: list):
        """Advance elapsed time on all active conditions; remove expired ones."""
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            conditions = getattr(npc, 'conditions', None)
            if not conditions:
                continue

            resolved = []
            for cond in conditions:
                cond.elapsed += day_frac

                # Fatality check for severe conditions (severity >= 0.7)
                if cond.severity >= 0.7:
                    # Daily fatality chance = severity * 0.1 (scaled to day_frac)
                    fatality_chance = cond.severity * 0.1 * day_frac
                    # Constitution reduces fatality chance
                    immune_str = getattr(npc, 'immune_strength', 0.5)
                    fatality_chance *= (1.0 - immune_str * 0.5)
                    if random.random() < fatality_chance:
                        npc.alive = False
                        self.event_log.append(
                            f"{npc.name} has died from {cond.name}.")
                        # Notify simulation via callback
                        self._pending_deaths.append((npc, cond.name))
                        break

                # Check if condition has run its course
                if cond.elapsed >= cond.duration:
                    resolved.append(cond)

            if not npc.alive:
                continue

            # Remove resolved conditions, grant immunities
            for cond in resolved:
                conditions.remove(cond)
                if cond.immunity_after:
                    immunities = getattr(npc, 'immunities', set())
                    # Find disease key from name
                    for key, template in DISEASES.items():
                        if template.name == cond.name:
                            immunities.add(key)
                            break
                    npc.immunities = immunities

                self.event_log.append(
                    f"{npc.name} has recovered from {cond.name}.")

                # Emotional integration: recovery triggers joy
                self._trigger_recovery_emotion(npc)

    # ----------------------------------------------------------------
    # CONTAGION SPREAD
    # ----------------------------------------------------------------

    def _check_spread(self, npcs: list, npc_grid=None, trade_system=None):
        """Check contagious NPCs and try to spread to nearby targets."""
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            conditions = getattr(npc, 'conditions', None)
            if not conditions:
                continue

            contagious_conditions = [c for c in conditions if c.contagious]
            if not contagious_conditions:
                continue

            # Find nearby NPCs (within 2 tiles)
            if npc_grid:
                nearby = npc_grid.get_nearby(npc.x, npc.y, 2)
            else:
                # Fallback: brute force (expensive, should rarely happen)
                nearby = [
                    other for other in npcs
                    if other is not npc and other.alive
                    and abs(other.x - npc.x) <= 2 and abs(other.y - npc.y) <= 2
                ]

            crowding = _get_crowding(npc)

            for other in nearby:
                if other is npc or not other.alive:
                    continue
                ensure_health_attrs(other)

                for cond in contagious_conditions:
                    disease_key = None
                    for key, template in DISEASES.items():
                        if template.name == cond.name:
                            disease_key = key
                            break
                    if disease_key is None:
                        continue

                    # Already has this disease or is immune
                    if disease_key in getattr(other, 'immunities', set()):
                        continue
                    if any(c.name == cond.name
                           for c in getattr(other, 'conditions', [])):
                        continue

                    # Roll spread
                    # spread_rate is per day per nearby NPC; this check runs
                    # every 30s, so scale: 30s / DAY_LENGTH
                    from game.settings import DAY_LENGTH
                    time_scale = 30.0 / DAY_LENGTH
                    target_resist = 1.0 - getattr(other, 'immune_strength', 0.5)

                    # Quarantine check
                    quarantine_mult = 1.0
                    if getattr(other, '_quarantined', False):
                        quarantine_mult = 0.5

                    chance = (cond.spread_rate * time_scale * target_resist
                              * crowding * quarantine_mult)
                    if random.random() < chance:
                        self.infect(other, disease_key,
                                    cause=f"caught from {npc.name}")

        # Trade route spread (5% chance per day per infected settlement)
        if trade_system:
            self._spread_via_trade(npcs, trade_system)

    def _spread_via_trade(self, npcs: list, trade_system):
        """Spread disease along trade routes between settlements."""
        # Build set of infected settlement names
        infected_settlements: Dict[str, Set[str]] = {}  # settlement -> set of disease keys
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            conditions = getattr(npc, 'conditions', None)
            if not conditions:
                continue
            settlement = getattr(npc, 'home_settlement', '')
            if not settlement:
                continue
            for cond in conditions:
                if not cond.contagious:
                    continue
                for key, template in DISEASES.items():
                    if template.name == cond.name:
                        if settlement not in infected_settlements:
                            infected_settlements[settlement] = set()
                        infected_settlements[settlement].add(key)
                        break

        if not infected_settlements:
            return

        # Check trade routes
        routes = getattr(trade_system, 'routes', [])
        from game.settings import DAY_LENGTH
        # This runs every 30s; scale 5% daily to per-check
        trade_chance_scale = 30.0 / DAY_LENGTH

        for route in routes:
            src = getattr(route, 'source', getattr(route, 'start', None))
            dst = getattr(route, 'destination', getattr(route, 'end', None))
            if not src or not dst:
                continue

            # src -> dst
            if src in infected_settlements:
                for disease_key in infected_settlements[src]:
                    if random.random() < 0.05 * trade_chance_scale:
                        # Pick a random NPC in the destination settlement
                        targets = [n for n in npcs
                                   if getattr(n, 'home_settlement', '') == dst
                                   and n.alive]
                        if targets:
                            victim = random.choice(targets)
                            self.infect(victim, disease_key,
                                        cause=f"trade route from {src}")

            # dst -> src
            if dst in infected_settlements:
                for disease_key in infected_settlements[dst]:
                    if random.random() < 0.05 * trade_chance_scale:
                        targets = [n for n in npcs
                                   if getattr(n, 'home_settlement', '') == src
                                   and n.alive]
                        if targets:
                            victim = random.choice(targets)
                            self.infect(victim, disease_key,
                                        cause=f"trade route from {dst}")

    # ----------------------------------------------------------------
    # SEASONAL ILLNESS
    # ----------------------------------------------------------------

    def _check_seasonal_illness(self, game_day: int, season: str,
                                npcs: list, world=None):
        """Once per game day, roll seasonal illness for qualifying NPCs."""
        from game.settings import SWAMP

        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            ensure_health_attrs(npc)

            # Skip NPCs sleeping indoors (rough proxy: sleeping state)
            is_outdoor = getattr(npc, 'current_action', '') not in (
                "sleeping", "resting")

            # Immune strength reduces all seasonal chances
            resist = getattr(npc, 'immune_strength', 0.5)

            if season == "winter":
                if is_outdoor:
                    # 2% cold, 0.5% flu
                    if random.random() < 0.02 * (1.0 - resist * 0.5):
                        self.infect(npc, "common_cold", cause="winter exposure")
                    if random.random() < 0.005 * (1.0 - resist * 0.5):
                        self.infect(npc, "flu", cause="winter exposure")
                # Frostbite for prolonged outdoor exposure in winter
                # (simplified: 1% if working outdoors)
                if is_outdoor and random.random() < 0.01 * (1.0 - resist * 0.3):
                    self.infect(npc, "frostbite", cause="prolonged cold")

            elif season == "summer":
                if is_outdoor:
                    # 1% heatstroke in hot climates
                    heat_mult = 1.0
                    # Check if in hot biome (desert/sand tile)
                    if world:
                        try:
                            from game.settings import SAND
                            tile = world.get_tile(int(npc.x), int(npc.y))
                            if tile == SAND:
                                heat_mult = 2.0
                        except Exception:
                            pass
                    if random.random() < 0.01 * heat_mult * (1.0 - resist * 0.3):
                        self.infect(npc, "heatstroke", cause="summer heat")

            elif season == "spring":
                # 1% food poisoning from old winter stores
                if random.random() < 0.01 * (1.0 - resist * 0.3):
                    self.infect(npc, "food_poisoning",
                                cause="spoiled winter stores")

            # Swamp fever year-round (1% for NPCs in swamp biome)
            if world:
                try:
                    tile = world.get_tile(int(npc.x), int(npc.y))
                    if tile == SWAMP:
                        if random.random() < 0.01 * (1.0 - resist * 0.3):
                            self.infect(npc, "swamp_fever",
                                        cause="swamp miasma")
                except Exception:
                    pass

    # ----------------------------------------------------------------
    # WOUND INFECTION
    # ----------------------------------------------------------------

    def _check_wound_infection(self, npcs: list):
        """Check NPCs who recently took combat damage for wound infection.

        Also checks existing wound infections for progression to sepsis.
        """
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            ensure_health_attrs(npc)

            # Detect recent combat damage by comparing hp to last known hp
            current_hp = getattr(npc, 'hp', 0)
            last_hp = getattr(npc, '_last_hp', current_hp)
            if current_hp < last_hp:
                # Took damage -- 10% chance of wound infection
                damage_taken = last_hp - current_hp
                # Only trigger from significant damage (at least 2 hp)
                if damage_taken >= 2:
                    resist = getattr(npc, 'immune_strength', 0.5)
                    if random.random() < 0.10 * (1.0 - resist * 0.3):
                        self.infect(npc, "wound_infection",
                                    cause="combat wound")
            npc._last_hp = current_hp

            # Check wound_infection progression to sepsis
            conditions = getattr(npc, 'conditions', [])
            for cond in conditions:
                if cond.name == "Wound Infection" and cond.elapsed >= 5.0:
                    # 15% chance of sepsis after 5 days untreated
                    # (check runs every 60s; scale to per-check probability)
                    from game.settings import DAY_LENGTH
                    # Approximate: 15% over remaining duration, per 60s check
                    checks_per_day = DAY_LENGTH / 60.0
                    per_check_chance = 1.0 - (1.0 - 0.15) ** (1.0 / checks_per_day)
                    if random.random() < per_check_chance:
                        # Check if already has sepsis
                        if not any(c.name == "Sepsis" for c in conditions):
                            self.infect(npc, "sepsis",
                                        cause="untreated wound infection")

    # ----------------------------------------------------------------
    # PUBLIC API: INFECT
    # ----------------------------------------------------------------

    def infect(self, npc, disease_key: str, cause: str = ""):
        """Give an NPC a disease.

        Args:
            npc: The NPC to infect.
            disease_key: Key into DISEASES dict (e.g. "plague").
            cause: Human-readable cause string.

        Returns:
            True if infection took hold, False if immune or already infected.
        """
        template = DISEASES.get(disease_key)
        if template is None:
            return False

        ensure_health_attrs(npc)

        # Already immune?
        if disease_key in npc.immunities:
            return False

        # Already has this condition?
        if any(c.name == template.name for c in npc.conditions):
            return False

        # Immune system roll: immune_strength chance to resist
        # (doesn't apply to non-contagious conditions like frostbite/heatstroke)
        if template.contagious:
            if random.random() < npc.immune_strength * 0.3:
                return False

        # Create a fresh condition instance
        condition = _clone_condition(template)
        npc.conditions.append(condition)

        cause_str = f" ({cause})" if cause else ""
        self.event_log.append(
            f"{npc.name} has contracted {condition.name}{cause_str}.")

        # Track outbreaks for contagious diseases
        if condition.contagious:
            settlement = getattr(npc, 'home_settlement', 'unknown')
            self.outbreak_log.append({
                "disease": disease_key,
                "npc": npc.name,
                "settlement": settlement,
                "cause": cause,
            })

            # Check for epidemic (3+ cases in same settlement)
            recent_cases = sum(
                1 for entry in self.outbreak_log[-50:]
                if entry["disease"] == disease_key
                and entry["settlement"] == settlement)
            if recent_cases >= 3:
                self.event_log.append(
                    f"EPIDEMIC: {condition.name} outbreak in {settlement}!")
                self._trigger_epidemic_fear(npc, condition, settlement)

        # Emotional integration: getting sick triggers fear + sadness
        self._trigger_sickness_emotion(npc, condition)

        return True

    # ----------------------------------------------------------------
    # PUBLIC API: TREAT
    # ----------------------------------------------------------------

    def treat(self, npc, condition_name: str, healer_skill: float = 1.0,
              has_medicine: bool = False):
        """Attempt to treat a condition.

        Args:
            npc: The sick NPC.
            condition_name: Name of the condition to treat (e.g. "Plague").
            healer_skill: Healer's skill level (0-10 scale, 1.0 = basic).
            has_medicine: Whether medicinal herbs are available.

        Returns:
            True if treatment succeeded, False otherwise.
        """
        ensure_health_attrs(npc)
        conditions = npc.conditions

        target_cond = None
        for cond in conditions:
            if cond.name == condition_name:
                target_cond = cond
                break

        if target_cond is None:
            return False

        # Treatment success formula:
        # healer_skill * 0.5 + medicine_available * 0.3 + constitution * 0.2
        con_factor = getattr(npc, 'constitution_base', 10) / 20.0  # 0-1 range
        medicine_factor = 1.0 if has_medicine else 0.0
        skill_factor = min(healer_skill / 10.0, 1.0)  # normalize to 0-1

        success_chance = (skill_factor * 0.5
                          + medicine_factor * 0.3
                          + con_factor * 0.2)

        if random.random() < success_chance:
            # Success: reduce remaining duration by 50%
            remaining = target_cond.duration - target_cond.elapsed
            target_cond.duration -= remaining * 0.5

            # Prevent sepsis progression if treating wound infection
            if target_cond.name == "Wound Infection":
                # Mark as treated so it won't progress
                target_cond.severity = max(0.1, target_cond.severity - 0.2)

            self.event_log.append(
                f"{npc.name}'s {condition_name} is being treated successfully.")

            # Recovery emotion with healer trust
            try:
                from game.systems.emotions import trigger_emotion
                trigger_emotion(npc, "praised", intensity=0.4,
                                cause="received medical treatment")
            except Exception:
                pass

            return True

        return False

    def treat_with_miracle(self, npc, condition_name: str):
        """Instantly cure a condition via divine miracle.

        Used by the pantheon/god system when miracle points are spent.
        """
        ensure_health_attrs(npc)
        conditions = npc.conditions

        for i, cond in enumerate(conditions):
            if cond.name == condition_name:
                conditions.pop(i)
                self.event_log.append(
                    f"{npc.name}'s {condition_name} was cured by divine miracle!")

                # Strong positive emotion
                try:
                    from game.systems.emotions import trigger_emotion
                    trigger_emotion(npc, "prayer_answered", intensity=0.9,
                                    cause=f"{condition_name} miraculously cured")
                except Exception:
                    pass
                return True

        return False

    # ----------------------------------------------------------------
    # PUBLIC API: MODIFIERS
    # ----------------------------------------------------------------

    def get_work_modifier(self, npc) -> float:
        """Combined work speed modifier from all active conditions.

        Returns a multiplier 0.0-1.0 (1.0 = no penalty).
        """
        conditions = getattr(npc, 'conditions', None)
        if not conditions:
            return 1.0

        modifier = 1.0
        for cond in conditions:
            work_mod = cond.stat_modifiers.get("work")
            if work_mod is not None:
                modifier = min(modifier, work_mod)
        return modifier

    def get_speed_modifier(self, npc) -> float:
        """Movement speed modifier from conditions.

        Returns a multiplier 0.0-1.0 (1.0 = no penalty).
        """
        conditions = getattr(npc, 'conditions', None)
        if not conditions:
            return 1.0

        modifier = 1.0
        for cond in conditions:
            speed_mod = cond.stat_modifiers.get("speed")
            if speed_mod is not None:
                modifier = min(modifier, speed_mod)
        return modifier

    def get_combat_modifier(self, npc) -> float:
        """Combat effectiveness modifier from conditions."""
        conditions = getattr(npc, 'conditions', None)
        if not conditions:
            return 1.0

        modifier = 1.0
        for cond in conditions:
            combat_mod = cond.stat_modifiers.get("combat")
            if combat_mod is not None:
                modifier = min(modifier, combat_mod)
        return modifier

    # ----------------------------------------------------------------
    # PUBLIC API: QUERIES
    # ----------------------------------------------------------------

    def is_sick(self, npc) -> bool:
        """Check if NPC has any active condition."""
        conditions = getattr(npc, 'conditions', None)
        return bool(conditions)

    def is_bedridden(self, npc) -> bool:
        """Check if NPC is too sick to work (work modifier == 0)."""
        return self.get_work_modifier(npc) <= 0.01

    def get_conditions_summary(self, npc) -> str:
        """Return human-readable summary of active conditions."""
        conditions = getattr(npc, 'conditions', None)
        if not conditions:
            return "healthy"
        parts = []
        for cond in conditions:
            days_left = max(0, cond.duration - cond.elapsed)
            parts.append(f"{cond.name} ({days_left:.0f}d left)")
        return ", ".join(parts)

    def get_event_log(self) -> List[str]:
        """Get and clear the event log."""
        log = list(self.event_log)
        self.event_log.clear()
        return log

    # ----------------------------------------------------------------
    # COMBAT INTEGRATION: post-damage wound check
    # ----------------------------------------------------------------

    def on_combat_damage(self, npc, damage: int):
        """Called after an NPC takes combat damage.

        Gives a 10% chance of wound infection immediately.
        """
        if damage < 2:
            return
        ensure_health_attrs(npc)
        resist = getattr(npc, 'immune_strength', 0.5)
        if random.random() < 0.10 * (1.0 - resist * 0.3):
            self.infect(npc, "wound_infection", cause="combat wound")

    # ----------------------------------------------------------------
    # EMOTIONAL INTEGRATION
    # ----------------------------------------------------------------

    def _trigger_sickness_emotion(self, npc, condition: HealthCondition):
        """Getting sick triggers fear + sadness."""
        try:
            from game.systems.emotions import trigger_emotion
            intensity = condition.severity
            trigger_emotion(npc, "attacked", intensity=intensity * 0.5,
                            cause=f"contracted {condition.name}")
        except Exception:
            pass

    def _trigger_recovery_emotion(self, npc):
        """Recovery triggers joy + trust."""
        try:
            from game.systems.emotions import trigger_emotion
            trigger_emotion(npc, "praised", intensity=0.5,
                            cause="recovered from illness")
        except Exception:
            pass

    def _trigger_epidemic_fear(self, npc, condition: HealthCondition,
                               settlement: str):
        """Plague outbreak triggers mass fear in the settlement."""
        try:
            from game.systems.emotions import trigger_emotion
            # This will be called once when epidemic is detected;
            # trigger fear on the reporting NPC. The emotion system's
            # natural spread will propagate it.
            trigger_emotion(npc, "attacked", intensity=0.7,
                            cause=f"{condition.name} epidemic in {settlement}")
        except Exception:
            pass

    # ----------------------------------------------------------------
    # SETTLEMENT QUARANTINE CACHE
    # ----------------------------------------------------------------

    def cache_settlement_kinds(self, npcs: list, structures: list):
        """Pre-cache settlement kind on each NPC for crowding lookups.

        Called once during initialization.
        """
        settlement_kinds = {}
        for s in structures:
            if s.kind in ("hamlet", "village", "town", "city", "castle"):
                settlement_kinds[s.name] = s.kind

        for npc in npcs:
            home = getattr(npc, 'home_settlement', '')
            if home and home in settlement_kinds:
                npc._home_settlement_kind = settlement_kinds[home]
