"""
AI Storyteller System (RimWorld-inspired).

Controls dramatic pacing by managing event frequency and intensity.
Each storyteller personality shapes the rhythm of the game world
differently, creating emergent narratives through event scheduling.

The storyteller checks once per game day, evaluates world tension,
and dispatches events to existing game systems (climate, undead,
pantheon, military, health, economy, etc.)
"""

import random
import math
from typing import Dict, List, Optional, Tuple, Any


# ================================================================
# EVENT DEFINITIONS
# ================================================================

STORYTELLER_EVENTS = {
    "raid": {
        "tension_req": 0.3,
        "cooldown": 15,
        "severity_range": (0.3, 0.8),
        "category": "threat",
        "description": "A raiding party attacks a settlement",
    },
    "plague_outbreak": {
        "tension_req": 0.4,
        "cooldown": 30,
        "severity_range": (0.4, 0.9),
        "category": "threat",
        "description": "A deadly plague sweeps through a region",
    },
    "trade_caravan": {
        "tension_req": 0.0,
        "cooldown": 5,
        "severity_range": (0.1, 0.3),
        "category": "positive",
        "description": "A merchant caravan arrives with goods",
    },
    "wanderer_joins": {
        "tension_req": 0.0,
        "cooldown": 10,
        "severity_range": (0.1, 0.2),
        "category": "positive",
        "description": "A wanderer seeks to join a settlement",
    },
    "festival": {
        "tension_req": 0.0,
        "cooldown": 20,
        "severity_range": (0.1, 0.3),
        "category": "positive",
        "description": "A joyous festival lifts spirits",
    },
    "divine_intervention": {
        "tension_req": 0.5,
        "cooldown": 40,
        "severity_range": (0.3, 1.0),
        "category": "divine",
        "description": "The gods intervene in mortal affairs",
    },
    "monster_wave": {
        "tension_req": 0.4,
        "cooldown": 20,
        "severity_range": (0.3, 0.8),
        "category": "threat",
        "description": "A wave of monsters emerges from the wilds",
    },
    "diplomatic_crisis": {
        "tension_req": 0.3,
        "cooldown": 25,
        "severity_range": (0.2, 0.6),
        "category": "political",
        "description": "Diplomatic tensions between kingdoms escalate",
    },
    "natural_disaster": {
        "tension_req": 0.2,
        "cooldown": 30,
        "severity_range": (0.4, 0.9),
        "category": "disaster",
        "description": "A natural disaster strikes the land",
    },
    "economic_boom": {
        "tension_req": 0.0,
        "cooldown": 15,
        "severity_range": (0.1, 0.4),
        "category": "positive",
        "description": "Trade flourishes and markets boom",
    },
    "undead_rising": {
        "tension_req": 0.5,
        "cooldown": 25,
        "severity_range": (0.4, 0.8),
        "category": "threat",
        "description": "The dead rise from their graves",
    },
    "prophecy": {
        "tension_req": 0.2,
        "cooldown": 30,
        "severity_range": (0.1, 0.3),
        "category": "divine",
        "description": "A prophecy spreads among the people",
    },
}

# Events grouped by whether they raise or lower tension
_TENSION_RAISING = {"raid", "plague_outbreak", "monster_wave", "diplomatic_crisis",
                    "natural_disaster", "undead_rising"}
_TENSION_LOWERING = {"trade_caravan", "wanderer_joins", "festival", "economic_boom"}
_TENSION_VARIABLE = {"divine_intervention", "prophecy"}


# ================================================================
# STORYTELLER PERSONALITIES
# ================================================================

class _PersonalityConfig:
    """Parameters that define how a storyteller personality behaves."""
    __slots__ = ("name", "event_interval_base", "event_interval_variance",
                 "max_concurrent_threats", "tension_escalation_rate",
                 "tension_decay_rate", "positive_event_weight",
                 "threat_event_weight", "chaos_factor",
                 "resolution_threshold", "min_calm_days")

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


PERSONALITIES = {
    "balanced": _PersonalityConfig(
        name="Cassandra (Balanced)",
        event_interval_base=8,
        event_interval_variance=3,
        max_concurrent_threats=2,
        tension_escalation_rate=0.05,
        tension_decay_rate=0.03,
        positive_event_weight=1.0,
        threat_event_weight=1.0,
        chaos_factor=0.0,
        resolution_threshold=0.8,
        min_calm_days=5,
    ),
    "aggressive": _PersonalityConfig(
        name="Randy (Aggressive)",
        event_interval_base=5,
        event_interval_variance=8,
        max_concurrent_threats=4,
        tension_escalation_rate=0.08,
        tension_decay_rate=0.02,
        positive_event_weight=0.6,
        threat_event_weight=1.5,
        chaos_factor=0.3,
        resolution_threshold=0.9,
        min_calm_days=2,
    ),
    "peaceful": _PersonalityConfig(
        name="Phoebe (Peaceful)",
        event_interval_base=14,
        event_interval_variance=4,
        max_concurrent_threats=1,
        tension_escalation_rate=0.03,
        tension_decay_rate=0.06,
        positive_event_weight=1.8,
        threat_event_weight=0.5,
        chaos_factor=0.0,
        resolution_threshold=0.6,
        min_calm_days=10,
    ),
    "chaotic": _PersonalityConfig(
        name="Xaotl (Chaotic)",
        event_interval_base=4,
        event_interval_variance=12,
        max_concurrent_threats=5,
        tension_escalation_rate=0.1,
        tension_decay_rate=0.04,
        positive_event_weight=1.2,
        threat_event_weight=1.3,
        chaos_factor=0.6,
        resolution_threshold=0.95,
        min_calm_days=1,
    ),
}


# ================================================================
# AI STORYTELLER
# ================================================================

class AIStoryteller:
    """Controls dramatic pacing by managing event frequency and intensity.
    Inspired by RimWorld's storyteller system."""

    def __init__(self, personality: str = "balanced"):
        self.personality = personality
        self.config = PERSONALITIES.get(personality, PERSONALITIES["balanced"])
        self.tension: float = 0.0          # 0-1, current dramatic tension
        self.last_major_event: int = 0     # game day of last big event
        self.event_history: List[Dict] = []  # recent events with timestamps
        self.phase: str = "calm"           # "calm", "buildup", "crisis", "resolution"
        self._next_event_day: int = 0      # day when next event check fires
        self._active_threats: int = 0      # count of unresolved threat events
        self._event_cooldowns: Dict[str, int] = {}  # event_name -> day when available
        self._rng = random.Random()
        self._event_log: List[str] = []
        self._last_day_processed: int = -1

    # ----------------------------------------------------------------
    # Phase management
    # ----------------------------------------------------------------

    def _update_phase(self):
        """Transition between dramatic phases based on tension level."""
        old_phase = self.phase
        if self.tension < 0.2:
            self.phase = "calm"
        elif self.tension < 0.5:
            self.phase = "buildup"
        elif self.tension < 0.8:
            self.phase = "crisis"
        else:
            self.phase = "resolution"

        if self.phase != old_phase:
            self._event_log.append(
                f"[STORYTELLER] Phase shift: {old_phase} -> {self.phase} "
                f"(tension={self.tension:.2f})")

    # ----------------------------------------------------------------
    # Tension tracking
    # ----------------------------------------------------------------

    def _assess_world_tension(self, sim) -> float:
        """Read world state and compute tension adjustments.

        Tension rises from: active threats, deaths, low food, war, disease,
                           undead attacks.
        Tension falls from: victories, peace, prosperity, festivals, recovery.
        """
        delta = 0.0

        # Check active disasters (climate system)
        climate = getattr(sim, 'climate', None)
        if climate:
            n_disasters = len(climate.active_disasters)
            delta += n_disasters * 0.02

        # Check disease load (health system)
        health = getattr(sim, 'health', None)
        if health:
            sick_count = getattr(health, '_sick_count', 0)
            delta += min(0.05, sick_count * 0.005)

        # Check military conflicts
        military = getattr(sim, 'military', None)
        if military:
            active_battles = len(getattr(military, 'active_battles', []))
            delta += active_battles * 0.04

        # Check undead activity
        undead = getattr(sim, 'undead', None)
        if undead:
            n_undead = len(getattr(undead, 'active_undead', []))
            delta += min(0.06, n_undead * 0.01)

        # Average NPC mood (positive mood lowers tension)
        npcs = getattr(sim.world_mgr, 'npcs', [])
        if npcs:
            total_mood = 0.0
            count = 0
            for npc in npcs[:50]:  # sample up to 50 for perf
                es = getattr(npc, 'emotion_state', None)
                if es:
                    total_mood += es.mood
                    count += 1
            if count > 0:
                avg_mood = total_mood / count
                # Positive mood reduces tension, negative increases it
                delta -= avg_mood * 0.02

        # Recent deaths increase tension
        recent_deaths = 0
        for ev in self.event_history[-20:]:
            if ev.get("category") == "threat":
                recent_deaths += 1
        delta += recent_deaths * 0.005

        # Natural decay toward baseline
        decay = self.config.tension_decay_rate
        if self.phase == "calm":
            decay *= 1.5  # faster decay in calm

        self.tension = max(0.0, min(1.0, self.tension + delta - decay))
        return self.tension

    def raise_tension(self, amount: float, cause: str = ""):
        """Explicitly raise tension (called by other systems on bad events)."""
        old = self.tension
        self.tension = min(1.0, self.tension + amount)
        if cause:
            self._event_log.append(
                f"[STORYTELLER] Tension +{amount:.2f} ({cause}): "
                f"{old:.2f} -> {self.tension:.2f}")

    def lower_tension(self, amount: float, cause: str = ""):
        """Explicitly lower tension (called by other systems on good events)."""
        old = self.tension
        self.tension = max(0.0, self.tension - amount)
        if cause:
            self._event_log.append(
                f"[STORYTELLER] Tension -{amount:.2f} ({cause}): "
                f"{old:.2f} -> {self.tension:.2f}")

    # ----------------------------------------------------------------
    # Event selection
    # ----------------------------------------------------------------

    def _get_eligible_events(self, game_day: int) -> List[Tuple[str, Dict]]:
        """Return events that meet tension, cooldown, and phase requirements."""
        eligible = []
        cfg = self.config

        for name, evt in STORYTELLER_EVENTS.items():
            # Cooldown check
            cd_ready = self._event_cooldowns.get(name, 0)
            if game_day < cd_ready:
                continue

            # Tension requirement
            if self.tension < evt["tension_req"]:
                continue

            # Max concurrent threats
            if name in _TENSION_RAISING and self._active_threats >= cfg.max_concurrent_threats:
                continue

            # Peaceful storyteller avoids threats in calm phase
            if self.personality == "peaceful" and self.phase == "calm" and name in _TENSION_RAISING:
                continue

            eligible.append((name, evt))

        return eligible

    def _pick_event(self, eligible: List[Tuple[str, Dict]]) -> Optional[Tuple[str, float]]:
        """Choose an event and determine its severity.

        Returns (event_name, severity) or None.
        """
        if not eligible:
            return None

        cfg = self.config
        weights = []

        for name, evt in eligible:
            w = 1.0

            # Weight by category
            if name in _TENSION_RAISING:
                w *= cfg.threat_event_weight
            elif name in _TENSION_LOWERING:
                w *= cfg.positive_event_weight

            # Phase-based weighting
            if self.phase == "calm":
                # Prefer positive events during calm
                if name in _TENSION_LOWERING:
                    w *= 2.0
                elif name in _TENSION_RAISING:
                    w *= 0.3
            elif self.phase == "buildup":
                # Slight threat preference
                if name in _TENSION_RAISING:
                    w *= 1.5
            elif self.phase == "crisis":
                # Strong threat events
                if name in _TENSION_RAISING:
                    w *= 2.0
            elif self.phase == "resolution":
                # Force resolution: prefer positive events to bring tension down
                if name in _TENSION_LOWERING:
                    w *= 3.0
                elif name in _TENSION_RAISING:
                    w *= 0.1

            # Chaos factor adds randomness
            if cfg.chaos_factor > 0:
                w *= self._rng.uniform(1.0 - cfg.chaos_factor,
                                       1.0 + cfg.chaos_factor)

            weights.append(max(0.01, w))

        # Weighted random selection
        total = sum(weights)
        r = self._rng.random() * total
        cumulative = 0.0
        for i, (name, evt) in enumerate(eligible):
            cumulative += weights[i]
            if r <= cumulative:
                # Determine severity
                smin, smax = evt["severity_range"]
                # Severity scales with tension
                tension_factor = 0.3 + self.tension * 0.7
                severity = self._rng.uniform(smin, smax) * tension_factor
                severity = max(smin, min(smax, severity))

                # Chaotic storyteller can push severity higher
                if cfg.chaos_factor > 0:
                    severity *= self._rng.uniform(0.8, 1.0 + cfg.chaos_factor * 0.5)
                    severity = min(1.0, severity)

                return (name, severity)

        return None

    # ----------------------------------------------------------------
    # Event dispatch: translate chosen events into game system calls
    # ----------------------------------------------------------------

    def _dispatch_event(self, event_name: str, severity: float,
                        game_day: int, sim) -> str:
        """Execute a storyteller event by dispatching to existing systems.

        Returns a description string for the event log.
        """
        evt = STORYTELLER_EVENTS[event_name]
        desc = evt["description"]

        # Pick a target settlement near the player or random
        structures = getattr(sim.world, 'structures', [])
        settlements = [s for s in structures
                       if s.kind in ("village", "town", "city", "hamlet", "castle")]

        target = None
        if settlements:
            target = self._rng.choice(settlements)

        # ----- RAID -----
        if event_name == "raid":
            desc = self._dispatch_raid(severity, game_day, sim, target)

        # ----- PLAGUE OUTBREAK -----
        elif event_name == "plague_outbreak":
            desc = self._dispatch_plague(severity, game_day, sim, target)

        # ----- TRADE CARAVAN -----
        elif event_name == "trade_caravan":
            desc = self._dispatch_trade_caravan(severity, sim, target)

        # ----- WANDERER JOINS -----
        elif event_name == "wanderer_joins":
            desc = self._dispatch_wanderer(severity, sim, target)

        # ----- FESTIVAL -----
        elif event_name == "festival":
            desc = self._dispatch_festival(severity, game_day, sim, target)

        # ----- DIVINE INTERVENTION -----
        elif event_name == "divine_intervention":
            desc = self._dispatch_divine(severity, game_day, sim)

        # ----- MONSTER WAVE -----
        elif event_name == "monster_wave":
            desc = self._dispatch_monster_wave(severity, game_day, sim, target)

        # ----- DIPLOMATIC CRISIS -----
        elif event_name == "diplomatic_crisis":
            desc = self._dispatch_diplomatic_crisis(severity, sim)

        # ----- NATURAL DISASTER -----
        elif event_name == "natural_disaster":
            desc = self._dispatch_natural_disaster(severity, game_day, sim, target)

        # ----- ECONOMIC BOOM -----
        elif event_name == "economic_boom":
            desc = self._dispatch_economic_boom(severity, sim, target)

        # ----- UNDEAD RISING -----
        elif event_name == "undead_rising":
            desc = self._dispatch_undead_rising(severity, game_day, sim, target)

        # ----- PROPHECY -----
        elif event_name == "prophecy":
            desc = self._dispatch_prophecy(severity, sim)

        return desc

    def _dispatch_raid(self, severity, game_day, sim, target) -> str:
        """Spawn a raid event using the military system or simulation events."""
        if not target:
            return "A raid was rumored but no settlement was nearby."

        # Use the simulation's existing WorldEvent system for the raid
        from game.systems.simulation import WorldEvent
        raid_size = max(3, int(severity * 15))
        event = WorldEvent(
            name=f"Raid on {target.name}",
            description=f"Raiders ({raid_size} strong) attack {target.name}!",
            x=target.x, y=target.y,
            radius=40 + severity * 30,
            duration=60 + severity * 120,
            effects={"danger": "raiders", "raid_size": raid_size},
        )
        sim.events.append(event)

        # Tension impact
        self.raise_tension(severity * 0.15, f"raid on {target.name}")
        self._active_threats += 1

        return f"Raiders ({raid_size} strong) attack {target.name}!"

    def _dispatch_plague(self, severity, game_day, sim, target) -> str:
        """Trigger a plague through the health system."""
        if not target:
            return "A plague threatens but finds no victims."

        health = getattr(sim, 'health', None)
        if health and hasattr(health, 'start_epidemic'):
            disease = self._rng.choice(["plague", "flu", "pox", "fever"])
            health.start_epidemic(disease, target.x, target.y,
                                  radius=200 + severity * 300,
                                  virulence=severity)
            self.raise_tension(severity * 0.12, f"plague in {target.name}")
            self._active_threats += 1
            return f"A {disease} outbreak erupts in {target.name}! (severity {severity:.1f})"
        else:
            # Fallback: create a simulation event
            from game.systems.simulation import WorldEvent
            event = WorldEvent(
                name=f"Plague in {target.name}",
                description=f"A terrible plague sweeps through {target.name}.",
                x=target.x, y=target.y,
                radius=50, duration=80 + severity * 100,
                effects={"plague_dps": severity * 1.5},
            )
            sim.events.append(event)
            self.raise_tension(severity * 0.12, f"plague in {target.name}")
            self._active_threats += 1
            return f"A terrible plague sweeps through {target.name}!"

    def _dispatch_trade_caravan(self, severity, sim, target) -> str:
        """Spawn a trade caravan event."""
        if not target:
            return "A trade caravan passes through the region."

        # Boost economy via world effects
        we = getattr(sim, 'world_effects', None)
        if we and hasattr(we, 'add_trade_bonus'):
            we.add_trade_bonus(target.name, severity * 100)

        # Create positive event
        from game.systems.simulation import WorldEvent
        event = WorldEvent(
            name=f"Trade Caravan at {target.name}",
            description=f"A wealthy merchant caravan arrives at {target.name}!",
            x=target.x, y=target.y,
            radius=25, duration=60,
            effects={"trade_bonus": True},
        )
        sim.events.append(event)
        self.lower_tension(0.03, "trade caravan arrives")
        return f"A merchant caravan arrives at {target.name}!"

    def _dispatch_wanderer(self, severity, sim, target) -> str:
        """A wanderer joins a settlement."""
        if not target:
            return "A wanderer roams the wilderness."

        from game.systems.simulation import WorldEvent
        event = WorldEvent(
            name=f"Wanderer at {target.name}",
            description=f"A skilled wanderer seeks refuge in {target.name}.",
            x=target.x, y=target.y,
            radius=20, duration=30,
            effects={"social_boost": 0.5},
        )
        sim.events.append(event)
        self.lower_tension(0.02, "wanderer joins")
        return f"A wanderer seeks to join {target.name}."

    def _dispatch_festival(self, severity, game_day, sim, target) -> str:
        """Trigger a festival through the culture system."""
        if not target:
            return "Festive spirit is in the air."

        culture = getattr(sim, 'culture', None)
        if culture and hasattr(culture, 'start_festival'):
            culture.start_festival(target.name, game_day)

        # Trigger festival emotions for nearby NPCs
        npcs = getattr(sim.world_mgr, 'npcs', [])
        try:
            from game.systems.emotions import trigger_emotion
            game_time = getattr(sim.time_sys, 'time', 0.0)
            for npc in npcs:
                if not npc.alive:
                    continue
                dx = npc.x - target.x
                dy = npc.y - target.y
                if dx * dx + dy * dy < 2500:  # 50 tile radius
                    trigger_emotion(npc, "festival", intensity=severity,
                                    game_time=game_time)
        except ImportError:
            pass

        self.lower_tension(severity * 0.08, f"festival at {target.name}")
        return f"A grand festival begins in {target.name}!"

    def _dispatch_divine(self, severity, game_day, sim) -> str:
        """Trigger divine intervention via the pantheon system."""
        pantheon = getattr(sim, 'pantheon', None)
        if pantheon and hasattr(pantheon, 'gods') and pantheon.gods:
            god = self._rng.choice(list(pantheon.gods.values()))
            god_name = getattr(god, 'name', 'A deity')

            if severity > 0.6:
                # Wrathful intervention
                self.raise_tension(severity * 0.1, f"divine wrath of {god_name}")
                return f"{god_name} manifests divine wrath upon the mortal realm!"
            else:
                # Benevolent intervention
                self.lower_tension(severity * 0.08, f"divine blessing of {god_name}")
                return f"{god_name} bestows a blessing upon the faithful!"
        else:
            if severity > 0.6:
                self.raise_tension(severity * 0.08, "divine portent")
                return "Dark omens fill the sky as the gods stir."
            else:
                self.lower_tension(severity * 0.05, "divine peace")
                return "A warm divine light bathes the land."

    def _dispatch_monster_wave(self, severity, game_day, sim, target) -> str:
        """Spawn extra monsters near a settlement."""
        if not target:
            return "Monsters stir in the deep wilderness."

        # Use existing world event system
        from game.systems.simulation import WorldEvent
        monster_count = max(5, int(severity * 20))
        event = WorldEvent(
            name=f"Monster Wave near {target.name}",
            description=f"A horde of {monster_count} monsters descends on {target.name}!",
            x=target.x, y=target.y,
            radius=50 + severity * 30,
            duration=90 + severity * 90,
            effects={"danger": "monsters", "monster_count": monster_count},
        )
        sim.events.append(event)
        self.raise_tension(severity * 0.15, f"monster wave near {target.name}")
        self._active_threats += 1
        return f"A horde of monsters ({monster_count}) descends on {target.name}!"

    def _dispatch_diplomatic_crisis(self, severity, sim) -> str:
        """Create diplomatic tensions between kingdoms."""
        governance = getattr(sim, 'governance', None)
        if governance and hasattr(governance, 'kingdoms') and len(governance.kingdoms) >= 2:
            kingdoms = list(governance.kingdoms.keys())
            k1, k2 = self._rng.sample(kingdoms, 2)

            # Reduce diplomatic relations
            if hasattr(governance, 'relations'):
                key = tuple(sorted([k1, k2]))
                old = governance.relations.get(key, 0)
                governance.relations[key] = max(-100, old - int(severity * 40))

            self.raise_tension(severity * 0.08, f"diplomatic crisis: {k1} vs {k2}")
            return f"Diplomatic crisis! Tensions rise between {k1} and {k2}."
        else:
            self.raise_tension(severity * 0.04, "political unrest")
            return "Political unrest simmers across the realm."

    def _dispatch_natural_disaster(self, severity, game_day, sim, target) -> str:
        """Trigger a natural disaster through the climate system."""
        climate = getattr(sim, 'climate', None)
        if climate and target:
            from game.systems.climate import DisasterEvent
            dtype = self._rng.choice(["flood", "drought", "wildfire", "blizzard"])
            disaster = DisasterEvent(
                disaster_type=dtype,
                x=target.x, y=target.y,
                radius=200 + severity * 400,
                severity=severity,
                day_started=game_day,
                duration_days=max(2, int(severity * 8)),
                description=f"Storyteller {dtype} near {target.name}",
            )
            climate.active_disasters.append(disaster)
            self.raise_tension(severity * 0.12, f"{dtype} near {target.name}")
            self._active_threats += 1
            return f"A devastating {dtype} strikes near {target.name}! (severity {severity:.1f})"
        else:
            self.raise_tension(severity * 0.06, "natural disaster")
            return "The earth trembles and the sky darkens."

    def _dispatch_economic_boom(self, severity, sim, target) -> str:
        """Boost the economy of a settlement."""
        if not target:
            return "Trade winds blow favorably."

        we = getattr(sim, 'world_effects', None)
        if we and hasattr(we, 'add_trade_bonus'):
            we.add_trade_bonus(target.name, severity * 200)

        # Boost NPC mood
        npcs = getattr(sim.world_mgr, 'npcs', [])
        try:
            from game.systems.emotions import trigger_emotion
            game_time = getattr(sim.time_sys, 'time', 0.0)
            for npc in npcs:
                if not npc.alive:
                    continue
                dx = npc.x - target.x
                dy = npc.y - target.y
                if dx * dx + dy * dy < 4900:  # 70 tile radius
                    trigger_emotion(npc, "got_paid", intensity=severity * 0.5,
                                    game_time=game_time)
        except ImportError:
            pass

        self.lower_tension(severity * 0.06, f"economic boom in {target.name}")
        return f"An economic boom enriches {target.name}!"

    def _dispatch_undead_rising(self, severity, game_day, sim, target) -> str:
        """Trigger undead activity through the undead system."""
        if not target:
            return "An unnatural chill pervades the land."

        undead_sys = getattr(sim, 'undead', None)
        if undead_sys:
            # The undead system will naturally handle spawning; we just set
            # conditions by creating a world event that triggers fear
            from game.systems.simulation import WorldEvent
            event = WorldEvent(
                name=f"Undead Rising near {target.name}",
                description=f"The dead rise from their graves near {target.name}!",
                x=target.x, y=target.y,
                radius=40 + severity * 40,
                duration=100 + severity * 100,
                effects={"danger": "undead", "undead_severity": severity},
            )
            sim.events.append(event)

        # Trigger fear in nearby NPCs
        npcs = getattr(sim.world_mgr, 'npcs', [])
        try:
            from game.systems.emotions import trigger_emotion
            game_time = getattr(sim.time_sys, 'time', 0.0)
            for npc in npcs:
                if not npc.alive:
                    continue
                dx = npc.x - target.x
                dy = npc.y - target.y
                if dx * dx + dy * dy < 3600:
                    trigger_emotion(npc, "weather_fear",
                                    intensity=severity * 0.8,
                                    cause="undead rising",
                                    game_time=game_time)
        except ImportError:
            pass

        self.raise_tension(severity * 0.15, f"undead rising near {target.name}")
        self._active_threats += 1
        return f"The dead rise from their graves near {target.name}!"

    def _dispatch_prophecy(self, severity, sim) -> str:
        """Spread a prophecy through the information system."""
        prophecies = [
            "A great darkness will descend upon the land.",
            "The chosen one shall emerge from humble beginnings.",
            "Three kingdoms shall become one before the year's end.",
            "Beware the blood moon; the dead shall walk.",
            "A dragon stirs in the deep mountains.",
            "The old gods demand sacrifice.",
            "A child born under the twin stars shall unite the realm.",
            "Famine will test the faithful.",
        ]
        text = self._rng.choice(prophecies)

        info = getattr(sim, 'info', None)
        if info and hasattr(info, 'broadcast_news'):
            info.broadcast_news(f"Prophecy: {text}", importance=severity)

        if severity > 0.5:
            self.raise_tension(0.03, "ominous prophecy")
        else:
            self.lower_tension(0.02, "hopeful prophecy")

        return f"A prophecy spreads: '{text}'"

    # ----------------------------------------------------------------
    # Main update (called once per game day)
    # ----------------------------------------------------------------

    def update(self, game_day: int, sim):
        """Main storyteller update. Call once per game day.

        Args:
            game_day: Current game day number.
            sim: The SimulationManager instance (provides access to all systems).
        """
        # Prevent double-processing the same day
        if game_day == self._last_day_processed:
            return
        self._last_day_processed = game_day

        # Skip the first few days (warmup)
        if game_day < 3:
            return

        # Assess world state and update tension
        self._assess_world_tension(sim)
        self._update_phase()

        # Decay active threat count over time
        if self._active_threats > 0 and game_day % 10 == 0:
            self._active_threats = max(0, self._active_threats - 1)

        # Check if it's time for a new event
        if game_day < self._next_event_day:
            return

        # Schedule next event
        cfg = self.config
        interval = cfg.event_interval_base + self._rng.randint(
            -cfg.event_interval_variance, cfg.event_interval_variance)
        interval = max(1, interval)

        # In resolution phase, events come faster to resolve tension
        if self.phase == "resolution":
            interval = max(1, interval // 2)

        self._next_event_day = game_day + interval

        # Select and dispatch event
        eligible = self._get_eligible_events(game_day)
        choice = self._pick_event(eligible)

        if choice is None:
            return

        event_name, severity = choice

        # Apply cooldown
        cooldown = STORYTELLER_EVENTS[event_name]["cooldown"]
        self._event_cooldowns[event_name] = game_day + cooldown

        # Dispatch
        desc = self._dispatch_event(event_name, severity, game_day, sim)

        # Record in history
        self.event_history.append({
            "day": game_day,
            "event": event_name,
            "severity": severity,
            "phase": self.phase,
            "tension": self.tension,
            "category": STORYTELLER_EVENTS[event_name]["category"],
            "description": desc,
        })

        # Keep history bounded
        if len(self.event_history) > 100:
            self.event_history = self.event_history[-100:]

        # Track last major event
        if event_name in _TENSION_RAISING:
            self.last_major_event = game_day

        self._event_log.append(f"[STORYTELLER] {desc} (severity={severity:.2f})")

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    def get_event_log(self) -> List[str]:
        """Get and clear the event log."""
        log = list(self._event_log)
        self._event_log.clear()
        return log

    def get_status(self) -> Dict[str, Any]:
        """Return a summary of storyteller state for debug/UI."""
        return {
            "personality": self.config.name,
            "tension": self.tension,
            "phase": self.phase,
            "last_major_event_day": self.last_major_event,
            "active_threats": self._active_threats,
            "events_total": len(self.event_history),
            "next_event_day": self._next_event_day,
        }

    def set_personality(self, personality: str):
        """Change the storyteller personality mid-game."""
        if personality in PERSONALITIES:
            self.personality = personality
            self.config = PERSONALITIES[personality]
            self._event_log.append(
                f"[STORYTELLER] Personality changed to {self.config.name}")
