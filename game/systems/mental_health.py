"""
Mental Health System.

Manages long-term psychological conditions for NPCs: depression, anxiety,
PTSD, mania, paranoia, addiction, grief disorder, and burnout.

Conditions arise from sustained emotional states and life events, modify
emotion responses and stat outputs, and recover based on social support,
housing quality, healer access, and temple visits.

Designed for efficiency:
- Trigger checks run once per game day (timer-gated)
- Modifier application runs every 5th tick via cached multipliers
- Recovery checks run once per game day alongside triggers
"""

import random
from typing import Dict, List, Optional, Tuple


# ================================================================
# MENTAL CONDITION
# ================================================================

class MentalCondition:
    """A single active mental health condition on an NPC."""

    __slots__ = ("name", "severity", "duration_days", "elapsed_days",
                 "triggers", "emotion_modifiers", "stat_modifiers",
                 "body_modifiers", "recovery_rate", "compulsion",
                 "onset_day")

    def __init__(self, name: str, severity: float = 0.5,
                 duration_days: float = 60.0,
                 emotion_mods: Optional[Dict[str, float]] = None,
                 stat_mods: Optional[Dict[str, float]] = None,
                 body_mods: Optional[Dict[str, float]] = None,
                 recovery_rate: float = 0.02,
                 triggers: Optional[List[str]] = None,
                 compulsion: Optional[str] = None):
        self.name = name
        self.severity = severity              # 0-1
        self.duration_days = duration_days     # expected duration before natural resolution
        self.elapsed_days = 0.0
        self.triggers = triggers or []        # event types that can cause flashbacks
        self.emotion_modifiers = emotion_mods or {}   # emotion -> multiplier
        self.stat_modifiers = stat_mods or {}         # stat -> multiplier
        self.body_modifiers = body_mods or {}         # body stat -> additive modifier
        self.recovery_rate = recovery_rate    # base daily recovery (severity reduction)
        self.compulsion = compulsion          # building type NPC is compelled to visit
        self.onset_day = 0                    # game day when condition started


def _clone_condition(template: MentalCondition, onset_day: int = 0) -> MentalCondition:
    """Create a fresh instance from a condition template."""
    c = MentalCondition.__new__(MentalCondition)
    c.name = template.name
    c.severity = template.severity
    c.duration_days = template.duration_days
    c.elapsed_days = 0.0
    c.triggers = list(template.triggers)
    c.emotion_modifiers = dict(template.emotion_modifiers)
    c.stat_modifiers = dict(template.stat_modifiers)
    c.body_modifiers = dict(template.body_modifiers)
    c.recovery_rate = template.recovery_rate
    c.compulsion = template.compulsion
    c.onset_day = onset_day
    return c


# ================================================================
# CONDITION DEFINITIONS
# ================================================================

CONDITIONS: Dict[str, MentalCondition] = {
    "depression": MentalCondition(
        name="Depression", severity=0.6, duration_days=90,
        emotion_mods={"joy": 0.5, "sadness": 1.5, "anticipation": 0.3},
        stat_mods={"work": 0.6, "social": 0.4, "sleep_quality": 0.5},
        body_mods={"immune_strength": -0.2, "appetite": 0.5},
        recovery_rate=0.015),
    "anxiety": MentalCondition(
        name="Anxiety", severity=0.5, duration_days=60,
        emotion_mods={"fear": 2.0, "anticipation": 1.5, "trust": 0.5},
        stat_mods={"work": 0.8, "study": 0.7, "social": 0.6},
        body_mods={"exhaustion_rate": 1.3},
        recovery_rate=0.02),
    "ptsd": MentalCondition(
        name="PTSD", severity=0.7, duration_days=180,
        emotion_mods={"fear": 1.8, "anger": 1.3, "trust": 0.3},
        stat_mods={"combat": 0.6, "sleep_quality": 0.3},
        triggers=["combat", "explosion", "death_witnessed"],
        recovery_rate=0.01),
    "mania": MentalCondition(
        name="Mania", severity=0.6, duration_days=30,
        emotion_mods={"joy": 2.0, "anger": 1.5, "fear": 0.3},
        stat_mods={"work": 1.5, "judgment": 0.3, "spending": 3.0},
        recovery_rate=0.03),
    "paranoia": MentalCondition(
        name="Paranoia", severity=0.6, duration_days=90,
        emotion_mods={"trust": 0.1, "fear": 1.5, "anger": 1.3, "disgust": 1.5},
        stat_mods={"social": 0.2, "trade": 0.1},
        recovery_rate=0.015),
    "addiction_alcohol": MentalCondition(
        name="Alcohol Addiction", severity=0.5, duration_days=120,
        stat_mods={"work": 0.7, "constitution": -0.1},
        compulsion="tavern",
        recovery_rate=0.008),
    "grief_disorder": MentalCondition(
        name="Grief Disorder", severity=0.7, duration_days=120,
        emotion_mods={"joy": 0.2, "sadness": 2.0},
        stat_mods={"work": 0.3, "social": 0.3},
        recovery_rate=0.012),
    "burnout": MentalCondition(
        name="Burnout", severity=0.5, duration_days=45,
        emotion_mods={"joy": 0.4, "anticipation": 0.3},
        stat_mods={"work": 0.5, "social": 0.5},
        recovery_rate=0.025),
}


# ================================================================
# NPC ATTRIBUTE INITIALIZATION
# ================================================================

def ensure_mental_health_attrs(npc):
    """Attach mental health tracking attributes to an NPC if missing.

    Called lazily on first interaction with the mental health system.
    """
    if not hasattr(npc, 'mental_conditions'):
        npc.mental_conditions = []
    if not hasattr(npc, 'mental_health_history'):
        npc.mental_health_history = []
    if not hasattr(npc, 'days_since_rest'):
        npc.days_since_rest = 0
    if not hasattr(npc, 'tavern_visits'):
        npc.tavern_visits = 0
    if not hasattr(npc, '_mh_mood_tracker'):
        npc._mh_mood_tracker = []       # list of (game_day, mood) for rolling average
    if not hasattr(npc, '_mh_fear_events'):
        npc._mh_fear_events = []         # list of game_day when fear > 0.5
    if not hasattr(npc, '_mh_deaths_witnessed'):
        npc._mh_deaths_witnessed = 0
    if not hasattr(npc, '_mh_near_death'):
        npc._mh_near_death = False
    if not hasattr(npc, '_mh_betrayals'):
        npc._mh_betrayals = 0
    if not hasattr(npc, '_mh_consecutive_work_days'):
        npc._mh_consecutive_work_days = 0
    if not hasattr(npc, '_mh_cached_emotion_mults'):
        npc._mh_cached_emotion_mults = {}
    if not hasattr(npc, '_mh_cached_stat_mults'):
        npc._mh_cached_stat_mults = {}
    if not hasattr(npc, '_mh_susceptibility_bonus'):
        npc._mh_susceptibility_bonus = 0.0
    if not hasattr(npc, '_mh_last_check_day'):
        npc._mh_last_check_day = -1


# ================================================================
# MENTAL HEALTH SYSTEM
# ================================================================

class MentalHealthSystem:
    """Manages mental health conditions for all NPCs."""

    def __init__(self):
        self._check_timer = 0.0
        self._last_check_day = -1
        self.event_log: List[str] = []

    # ----------------------------------------------------------------
    # MAIN UPDATE
    # ----------------------------------------------------------------

    def update(self, dt: float, game_day: int, npcs: list):
        """Main tick: once per game day check triggers and recovery,
        every call refresh cached modifiers for NPCs with conditions.

        Args:
            dt: Delta time in seconds (may be pre-scaled).
            game_day: Current game day counter.
            npcs: List of all NPC objects.
        """
        from game.settings import DAY_LENGTH
        day_frac = dt / DAY_LENGTH

        # Daily checks: triggers, recovery, tracking updates
        if game_day != self._last_check_day:
            self._last_check_day = game_day
            for npc in npcs:
                if not getattr(npc, 'alive', True):
                    continue
                ensure_mental_health_attrs(npc)
                self._update_trackers(npc, game_day)
                self.check_triggers(npc, game_day)
                self._advance_conditions(npc, day_frac=1.0)
                self.check_recovery(npc, game_day)
                self._rebuild_caches(npc)

        # Advance elapsed days for active conditions every tick (cheap float math)
        else:
            for npc in npcs:
                if not getattr(npc, 'alive', True):
                    continue
                conditions = getattr(npc, 'mental_conditions', None)
                if conditions:
                    self._advance_conditions(npc, day_frac)

    # ----------------------------------------------------------------
    # TRACKER UPDATES (once per game day)
    # ----------------------------------------------------------------

    def _update_trackers(self, npc, game_day: int):
        """Update rolling mood history and event counters."""
        es = getattr(npc, 'emotion_state', None)
        if es is None:
            return

        # Track mood history (keep last 20 days)
        mood = es.mood
        npc._mh_mood_tracker.append((game_day, mood))
        if len(npc._mh_mood_tracker) > 20:
            npc._mh_mood_tracker = npc._mh_mood_tracker[-20:]

        # Track fear events
        fear = es.primary.get("fear", 0.0)
        if fear > 0.5:
            npc._mh_fear_events.append(game_day)
        # Prune old fear events (keep last 10 days)
        cutoff = game_day - 10
        npc._mh_fear_events = [d for d in npc._mh_fear_events if d >= cutoff]

        # Track near-death (hp < 20% of max)
        hp = getattr(npc, 'hp', 10)
        max_hp = getattr(npc, 'max_hp', 10)
        if max_hp > 0 and hp / max_hp < 0.2:
            npc._mh_near_death = True

        # Track consecutive work days vs rest
        action = getattr(npc, 'current_action', '')
        state = getattr(npc, 'state', '')
        is_working = action in ('working', 'chopping', 'mining', 'farming',
                                'building', 'crafting', 'smithing', 'cooking',
                                'foraging', 'fishing', 'hunting', 'trading',
                                'carrying', 'hauling', 'patrolling', 'guarding')
        is_resting = state == 'sleeping' or action in ('sleeping', 'resting',
                                                        'socializing', 'praying',
                                                        'tavern', 'festival')
        if is_working:
            npc._mh_consecutive_work_days += 1
        elif is_resting:
            npc._mh_consecutive_work_days = max(0,
                                                 npc._mh_consecutive_work_days - 1)
            npc.days_since_rest = 0

        # Track tavern visits
        if action == 'tavern' or getattr(npc, '_at_tavern', False):
            npc.tavern_visits += 1

        # Track betrayals from emotion memories
        es_grudges = getattr(es, 'grudges', {})
        betrayal_count = 0
        for _target, grudge in es_grudges.items():
            if grudge.get('cause', '') in ('was_betrayed', 'betrayed'):
                betrayal_count += 1
        npc._mh_betrayals = betrayal_count

        # Track deaths witnessed from emotional memories
        death_count = 0
        for mem in getattr(es, 'emotional_memories', []):
            if mem.cause in ('witnessed_death', 'lost_loved_one',
                             'pack_member_killed'):
                death_count += 1
        npc._mh_deaths_witnessed = death_count

    # ----------------------------------------------------------------
    # TRIGGER CHECKS
    # ----------------------------------------------------------------

    def check_triggers(self, npc, game_day: int):
        """Check if NPC should develop a new mental health condition."""
        # Skip if already checked today
        if npc._mh_last_check_day == game_day:
            return
        npc._mh_last_check_day = game_day

        es = getattr(npc, 'emotion_state', None)
        if es is None:
            return

        # Base susceptibility from personality (high neuroticism = more vulnerable)
        neuroticism = getattr(es.personality, 'neuroticism', 0.5)
        base_suscept = 0.5 + (neuroticism - 0.5) * 0.6
        # Hereditary bonus
        suscept = base_suscept + npc._mh_susceptibility_bonus

        active_names = {c.name for c in npc.mental_conditions}

        # --- Depression ---
        if "Depression" not in active_names:
            self._check_depression(npc, es, game_day, suscept)

        # --- Anxiety ---
        if "Anxiety" not in active_names:
            self._check_anxiety(npc, es, game_day, suscept)

        # --- PTSD ---
        if "PTSD" not in active_names:
            self._check_ptsd(npc, es, game_day, suscept)

        # --- Mania (follows depression) ---
        if "Mania" not in active_names:
            self._check_mania(npc, es, game_day, suscept)

        # --- Paranoia ---
        if "Paranoia" not in active_names:
            self._check_paranoia(npc, es, game_day, suscept)

        # --- Addiction ---
        if "Alcohol Addiction" not in active_names:
            self._check_addiction(npc, es, game_day, suscept)

        # --- Grief Disorder ---
        if "Grief Disorder" not in active_names:
            self._check_grief(npc, es, game_day, suscept)

        # --- Burnout ---
        if "Burnout" not in active_names:
            self._check_burnout(npc, es, game_day, suscept)

    def _check_depression(self, npc, es, game_day: int, suscept: float):
        """Depression: prolonged sadness (mood < -0.3 for 10+ days)
        OR bereavement OR chronic pain."""
        # Prolonged low mood
        low_mood_days = sum(1 for _d, m in npc._mh_mood_tracker if m < -0.3)
        if low_mood_days >= 10:
            chance = 0.15 * suscept
            if random.random() < chance:
                self._apply_condition(npc, "depression", game_day)
                return

        # Bereavement (lost_loved_one memory with high sadness)
        sadness = es.primary.get("sadness", 0.0)
        for mem in getattr(es, 'emotional_memories', []):
            if mem.cause == 'lost_loved_one' and sadness > 0.5:
                chance = 0.20 * suscept
                if random.random() < chance:
                    self._apply_condition(npc, "depression", game_day)
                    return

        # Chronic pain (health conditions with pain symptom)
        conditions = getattr(npc, 'conditions', [])
        chronic_pain = any(
            c.elapsed >= 10.0 and 'pain' in getattr(c, 'symptoms', [])
            for c in conditions)
        if chronic_pain:
            chance = 0.10 * suscept
            if random.random() < chance:
                self._apply_condition(npc, "depression", game_day)

    def _check_anxiety(self, npc, es, game_day: int, suscept: float):
        """Anxiety: repeated fear events (3+ in 5 days) OR combat trauma."""
        # Recent fear events
        recent_cutoff = game_day - 5
        recent_fears = sum(1 for d in npc._mh_fear_events if d >= recent_cutoff)
        if recent_fears >= 3:
            chance = 0.12 * suscept
            if random.random() < chance:
                self._apply_condition(npc, "anxiety", game_day)
                return

        # Combat trauma (took significant damage recently)
        hp = getattr(npc, 'hp', 10)
        max_hp = getattr(npc, 'max_hp', 10)
        if max_hp > 0 and hp / max_hp < 0.4:
            fear = es.primary.get("fear", 0.0)
            if fear > 0.3:
                chance = 0.08 * suscept
                if random.random() < chance:
                    self._apply_condition(npc, "anxiety", game_day)

    def _check_ptsd(self, npc, es, game_day: int, suscept: float):
        """PTSD: witnessed 3+ deaths OR survived near-death experience."""
        if npc._mh_deaths_witnessed >= 3:
            chance = 0.10 * suscept
            if random.random() < chance:
                self._apply_condition(npc, "ptsd", game_day)
                return

        if npc._mh_near_death:
            chance = 0.08 * suscept
            if random.random() < chance:
                self._apply_condition(npc, "ptsd", game_day)
                npc._mh_near_death = False  # reset flag after triggering

    def _check_mania(self, npc, es, game_day: int, suscept: float):
        """Mania: 10% chance after depression resolves."""
        for entry in npc.mental_health_history:
            if entry.get('name') == 'Depression':
                resolved_day = entry.get('resolved_day', 0)
                # Within 10 days of depression resolving
                if 0 < game_day - resolved_day <= 10:
                    chance = 0.10 * suscept
                    if random.random() < chance:
                        self._apply_condition(npc, "mania", game_day)
                    return  # only check most recent depression

    def _check_paranoia(self, npc, es, game_day: int, suscept: float):
        """Paranoia: betrayal + isolation."""
        if npc._mh_betrayals >= 1:
            # Check isolation: few friends nearby or low social need
            social_need = npc.needs.get("social", 50)
            friends = getattr(npc, 'friends', [])
            is_isolated = len(friends) <= 1 or social_need < 30
            if is_isolated:
                chance = 0.10 * suscept
                if random.random() < chance:
                    self._apply_condition(npc, "paranoia", game_day)

    def _check_addiction(self, npc, es, game_day: int, suscept: float):
        """Addiction: visited tavern 5+ times in 10 days while sad/anxious."""
        if npc.tavern_visits >= 5:
            mood = es.mood
            has_sadness = es.primary.get("sadness", 0.0) > 0.3
            has_anxiety = any(c.name == "Anxiety" for c in npc.mental_conditions)
            if mood < -0.1 or has_sadness or has_anxiety:
                chance = 0.12 * suscept
                if random.random() < chance:
                    self._apply_condition(npc, "addiction_alcohol", game_day)
                    # Reset counter
                    npc.tavern_visits = 0

    def _check_grief(self, npc, es, game_day: int, suscept: float):
        """Grief disorder: loved one died + sadness > 0.7 for 15+ days."""
        has_loss = any(
            mem.cause == 'lost_loved_one'
            for mem in getattr(es, 'emotional_memories', []))
        if not has_loss:
            return

        high_sadness_days = sum(1 for _d, m in npc._mh_mood_tracker if m < -0.5)
        if high_sadness_days >= 15:
            chance = 0.15 * suscept
            if random.random() < chance:
                self._apply_condition(npc, "grief_disorder", game_day)

    def _check_burnout(self, npc, es, game_day: int, suscept: float):
        """Burnout: worked 20+ consecutive days without social/rest balance."""
        if npc._mh_consecutive_work_days >= 20:
            social_need = npc.needs.get("social", 50)
            rest_need = npc.needs.get("rest", 50)
            if social_need < 40 or rest_need < 40:
                chance = 0.15 * suscept
                if random.random() < chance:
                    self._apply_condition(npc, "burnout", game_day)
                    npc._mh_consecutive_work_days = 0

    # ----------------------------------------------------------------
    # CONDITION APPLICATION
    # ----------------------------------------------------------------

    def _apply_condition(self, npc, condition_key: str, game_day: int):
        """Apply a new mental health condition to an NPC."""
        template = CONDITIONS.get(condition_key)
        if template is None:
            return

        # Don't double up
        if any(c.name == template.name for c in npc.mental_conditions):
            return

        condition = _clone_condition(template, onset_day=game_day)
        npc.mental_conditions.append(condition)

        self.event_log.append(
            f"{npc.name} has developed {condition.name}.")

        # Trigger emotional response to developing a condition
        try:
            from game.systems.emotions import trigger_emotion
            trigger_emotion(npc, "attacked", intensity=condition.severity * 0.4,
                            cause=f"developed {condition.name}")
        except Exception:
            pass

        # Rebuild caches immediately
        self._rebuild_caches(npc)

    # ----------------------------------------------------------------
    # CONDITION ADVANCEMENT
    # ----------------------------------------------------------------

    def _advance_conditions(self, npc, day_frac: float):
        """Advance elapsed time on all active mental conditions."""
        conditions = getattr(npc, 'mental_conditions', None)
        if not conditions:
            return
        for cond in conditions:
            cond.elapsed_days += day_frac

    # ----------------------------------------------------------------
    # RECOVERY
    # ----------------------------------------------------------------

    def check_recovery(self, npc, game_day: int):
        """Check if conditions are improving based on social support,
        housing, healer access, and temple visits."""
        conditions = getattr(npc, 'mental_conditions', None)
        if not conditions:
            return

        resolved = []
        for cond in conditions:
            recovery_mult = 1.0

            # Social support: friends nearby -> recovery +20%
            friends = getattr(npc, 'friends', [])
            if len(friends) >= 2:
                recovery_mult += 0.20

            # Good housing/food -> recovery +10%
            hunger = npc.needs.get("hunger", 50)
            rest = npc.needs.get("rest", 50)
            if hunger > 60 and rest > 60:
                recovery_mult += 0.10

            # Healer counseling -> recovery +30%
            # (approximated by: NPC lives near a healer or was recently treated)
            profession = getattr(npc, 'profession', '')
            # Check if NPC has been treated recently (has healer bond)
            es = getattr(npc, 'emotion_state', None)
            has_healer_support = False
            if es:
                for target, bond in getattr(es, 'bonds', {}).items():
                    if 'medical' in bond.get('cause', '') or 'heal' in bond.get('cause', ''):
                        has_healer_support = True
                        break
            if has_healer_support:
                recovery_mult += 0.30

            # Temple visits -> recovery +15%
            deity = getattr(npc, 'deity', None)
            action = getattr(npc, 'current_action', '')
            if deity and action in ('praying', 'worship'):
                recovery_mult += 0.15

            # Triggers still present -> no recovery for PTSD
            if cond.triggers:
                triggers_active = False
                if es:
                    for mem in getattr(es, 'emotional_memories', []):
                        if mem.cause in cond.triggers:
                            triggers_active = True
                            break
                if triggers_active:
                    recovery_mult = 0.0

            # Apply recovery
            daily_recovery = cond.recovery_rate * recovery_mult
            cond.severity = max(0.0, cond.severity - daily_recovery)

            # Check if resolved (severity dropped below threshold or exceeded duration)
            if cond.severity < 0.05 or cond.elapsed_days >= cond.duration_days:
                resolved.append(cond)

        # Remove resolved conditions
        for cond in resolved:
            npc.mental_conditions.remove(cond)
            npc.mental_health_history.append({
                'name': cond.name,
                'onset_day': cond.onset_day,
                'resolved_day': game_day,
                'duration': cond.elapsed_days,
            })
            self.event_log.append(
                f"{npc.name} has recovered from {cond.name}.")

            # Recovery emotion
            try:
                from game.systems.emotions import trigger_emotion
                trigger_emotion(npc, "praised", intensity=0.5,
                                cause=f"recovered from {cond.name}")
            except Exception:
                pass

        if resolved:
            self._rebuild_caches(npc)

    # ----------------------------------------------------------------
    # MODIFIER APPLICATION
    # ----------------------------------------------------------------

    def apply_modifiers(self, npc):
        """Apply emotion and stat modifiers from active conditions.

        Updates the cached modifier dicts on the NPC. Called after
        condition changes and read by other systems.
        """
        self._rebuild_caches(npc)

    def _rebuild_caches(self, npc):
        """Recompute cached emotion and stat multipliers from all active conditions."""
        ensure_mental_health_attrs(npc)
        conditions = npc.mental_conditions

        emotion_mults: Dict[str, float] = {}
        stat_mults: Dict[str, float] = {}

        for cond in conditions:
            # Emotion modifiers: multiply together across conditions
            for emotion, mult in cond.emotion_modifiers.items():
                # Scale modifier by severity (at 0 severity, no effect)
                scaled = 1.0 + (mult - 1.0) * cond.severity
                if emotion in emotion_mults:
                    emotion_mults[emotion] *= scaled
                else:
                    emotion_mults[emotion] = scaled

            # Stat modifiers: use worst (minimum) across conditions
            for stat, mult in cond.stat_modifiers.items():
                scaled = 1.0 + (mult - 1.0) * cond.severity
                if stat in stat_mults:
                    stat_mults[stat] = min(stat_mults[stat], scaled)
                else:
                    stat_mults[stat] = scaled

            # Body modifiers: apply to NPC attributes directly
            for body_stat, mod_val in cond.body_modifiers.items():
                scaled_mod = mod_val * cond.severity
                if body_stat == "immune_strength":
                    base = getattr(npc, 'immune_strength', 0.5)
                    npc.immune_strength = max(0.1, min(0.95, base + scaled_mod))

        npc._mh_cached_emotion_mults = emotion_mults
        npc._mh_cached_stat_mults = stat_mults

    # ----------------------------------------------------------------
    # PUBLIC QUERY API
    # ----------------------------------------------------------------

    def get_condition_names(self, npc) -> List[str]:
        """Return list of active condition names for this NPC."""
        conditions = getattr(npc, 'mental_conditions', [])
        return [c.name for c in conditions]

    def get_work_modifier(self, npc) -> float:
        """Return work output multiplier from mental conditions (0-1.5)."""
        mults = getattr(npc, '_mh_cached_stat_mults', {})
        return mults.get("work", 1.0)

    def get_social_modifier(self, npc) -> float:
        """Return social effectiveness multiplier."""
        mults = getattr(npc, '_mh_cached_stat_mults', {})
        return mults.get("social", 1.0)

    def get_combat_modifier(self, npc) -> float:
        """Return combat effectiveness modifier."""
        mults = getattr(npc, '_mh_cached_stat_mults', {})
        return mults.get("combat", 1.0)

    def get_emotion_modifier(self, npc, emotion: str) -> float:
        """Return emotion response multiplier for a specific emotion."""
        mults = getattr(npc, '_mh_cached_emotion_mults', {})
        return mults.get(emotion, 1.0)

    def get_conditions_summary(self, npc) -> str:
        """Return human-readable summary of active mental conditions."""
        conditions = getattr(npc, 'mental_conditions', [])
        if not conditions:
            return "mentally healthy"
        parts = []
        for cond in conditions:
            sev_label = "mild" if cond.severity < 0.3 else "moderate" if cond.severity < 0.6 else "severe"
            parts.append(f"{cond.name} ({sev_label})")
        return ", ".join(parts)

    def has_condition(self, npc, condition_name: str) -> bool:
        """Check if NPC has a specific active condition."""
        conditions = getattr(npc, 'mental_conditions', [])
        return any(c.name == condition_name for c in conditions)

    def get_compulsion(self, npc) -> Optional[str]:
        """Return the building type the NPC is compelled to visit, or None."""
        conditions = getattr(npc, 'mental_conditions', [])
        for cond in conditions:
            if cond.compulsion:
                return cond.compulsion
        return None

    # ----------------------------------------------------------------
    # HEREDITARY SUSCEPTIBILITY
    # ----------------------------------------------------------------

    def apply_hereditary_susceptibility(self, child_npc, parent_npcs: list):
        """Children of mentally ill parents get +15% susceptibility.

        Called by the child system when a new NPC is born.
        """
        ensure_mental_health_attrs(child_npc)
        for parent in parent_npcs:
            parent_conditions = getattr(parent, 'mental_conditions', [])
            parent_history = getattr(parent, 'mental_health_history', [])
            if parent_conditions or parent_history:
                child_npc._mh_susceptibility_bonus = 0.15
                break

    # ----------------------------------------------------------------
    # EVENT HOOKS (called by other systems)
    # ----------------------------------------------------------------

    def on_death_witnessed(self, npc):
        """Called when an NPC witnesses a death."""
        ensure_mental_health_attrs(npc)
        npc._mh_deaths_witnessed += 1

    def on_near_death(self, npc):
        """Called when an NPC survives a near-death experience."""
        ensure_mental_health_attrs(npc)
        npc._mh_near_death = True

    def on_tavern_visit(self, npc):
        """Called when an NPC visits a tavern."""
        ensure_mental_health_attrs(npc)
        npc.tavern_visits += 1

    def on_betrayal(self, npc):
        """Called when an NPC is betrayed."""
        ensure_mental_health_attrs(npc)
        npc._mh_betrayals += 1

    def get_event_log(self) -> List[str]:
        """Get and clear the event log."""
        log = list(self.event_log)
        self.event_log.clear()
        return log
