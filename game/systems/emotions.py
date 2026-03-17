"""
Plutchik's Wheel of Emotions — core NPC emotion system.

Each NPC carries an EmotionState: 8 primary emotion floats (0-1),
a Big Five personality, emotional memories, grudges, and bonds.
Secondary emotions are computed on-the-fly from primary pairs.

The EmotionSystem runs per-tick: decays emotions, updates moods,
and provides behavioral hooks (rebellion, crime, work modifiers).
"""

import random
import math
from typing import Dict, List, Optional, Tuple


# ================================================================
# PRIMARY EMOTIONS (Plutchik's 8)
# ================================================================

PRIMARY_EMOTIONS = (
    "joy", "trust", "fear", "surprise",
    "sadness", "disgust", "anger", "anticipation",
)

# Intensity labels: (low_threshold, low_name, mid_name, high_name)
EMOTION_LABELS = {
    "joy":          (0.33, "serenity",      "joy",          "ecstasy"),
    "trust":        (0.33, "acceptance",    "trust",        "admiration"),
    "fear":         (0.33, "apprehension",  "fear",         "terror"),
    "surprise":     (0.33, "distraction",   "surprise",     "amazement"),
    "sadness":      (0.33, "pensiveness",   "sadness",      "grief"),
    "disgust":      (0.33, "boredom",       "disgust",      "loathing"),
    "anger":        (0.33, "annoyance",     "anger",        "rage"),
    "anticipation": (0.33, "interest",      "anticipation", "vigilance"),
}

# Valence: positive emotions contribute +1, negative -1 to mood
EMOTION_VALENCE = {
    "joy": 1.0, "trust": 0.5, "fear": -0.7, "surprise": 0.1,
    "sadness": -1.0, "disgust": -0.6, "anger": -0.8, "anticipation": 0.3,
}


# ================================================================
# SECONDARY EMOTIONS (adjacent pairs on Plutchik's wheel)
# ================================================================

SECONDARY_EMOTIONS = {
    "love":            ("joy", "trust"),
    "submission":      ("trust", "fear"),
    "awe":             ("fear", "surprise"),
    "disapproval":     ("surprise", "sadness"),
    "remorse":         ("sadness", "disgust"),
    "contempt":        ("disgust", "anger"),
    "aggressiveness":  ("anger", "anticipation"),
    "optimism":        ("anticipation", "joy"),
}


# ================================================================
# EVENT -> EMOTION MAPPINGS
# ================================================================

# Each event maps to a list of (emotion, base_intensity) tuples.
# Actual intensity is modulated by personality.
EVENT_RESPONSES = {
    "attacked":        [("fear", 0.6), ("anger", 0.5)],
    "praised":         [("joy", 0.5), ("trust", 0.3)],
    "insulted":        [("anger", 0.5), ("sadness", 0.2), ("disgust", 0.2)],
    "lost_loved_one":  [("sadness", 0.9), ("anger", 0.3), ("fear", 0.2)],
    "got_paid":        [("joy", 0.3), ("trust", 0.2)],
    "went_hungry":     [("sadness", 0.3), ("anger", 0.2), ("fear", 0.2)],
    "saw_friend":      [("joy", 0.4), ("trust", 0.3)],
    "saw_enemy":       [("anger", 0.3), ("fear", 0.3), ("disgust", 0.2)],
    "won_fight":       [("joy", 0.6), ("anticipation", 0.4), ("trust", 0.2)],
    "lost_fight":      [("sadness", 0.5), ("fear", 0.4), ("anger", 0.3)],
    "found_treasure":  [("joy", 0.7), ("surprise", 0.5), ("anticipation", 0.3)],
    "was_robbed":      [("anger", 0.6), ("fear", 0.3), ("sadness", 0.4)],
    "witnessed_death": [("fear", 0.5), ("sadness", 0.6), ("surprise", 0.3)],
    "received_gift":   [("joy", 0.5), ("trust", 0.4), ("surprise", 0.3)],
    "was_betrayed":    [("anger", 0.7), ("sadness", 0.5), ("disgust", 0.4)],
    "got_promoted":    [("joy", 0.6), ("anticipation", 0.4), ("trust", 0.3)],
    "got_fired":       [("sadness", 0.5), ("anger", 0.4), ("fear", 0.3)],
    "festival":        [("joy", 0.6), ("trust", 0.3), ("anticipation", 0.3)],
    "prayer_answered": [("joy", 0.5), ("trust", 0.6), ("surprise", 0.3)],

    # Creature-specific events
    "predator_nearby": [("fear", 0.7)],
    "predator_nearby_aggro": [("anger", 0.3)],
    "prey_spotted":    [("anticipation", 0.6), ("joy", 0.3)],
    "territory_invaded": [("anger", 0.6), ("anticipation", 0.4)],
    "pack_member_killed": [("sadness", 0.5), ("anger", 0.4)],
    "young_threatened": [("anger", 0.9)],
    "food_found":      [("joy", 0.4), ("anticipation", 0.3)],
    "injured":         [("fear", 0.5), ("anger", 0.3)],

    # Weather events (triggered by climate system)
    "weather_sad":     [("sadness", 0.2)],
    "weather_fear":    [("fear", 0.3)],
    "weather_joy":     [("joy", 0.15)],
}

# Base decay rate per second for each emotion (tuned for game-time)
BASE_DECAY_RATE = 0.008  # ~8 seconds to halve from 0.5

# Reinforcement decay multiplier: each reinforcement slows decay by this factor
REINFORCEMENT_DECAY_FACTOR = 0.85

# Maximum emotional memories kept per NPC
MAX_EMOTIONAL_MEMORIES = 30

# Mood smoothing factor (exponential moving average)
MOOD_ALPHA = 0.05

# Behavioral thresholds
REBEL_THRESHOLD = 0.7       # anger + (1 - trust) toward leader
CRIME_THRESHOLD = 0.65      # fear + anger + (1 - trust)
WORK_MOOD_WEIGHT = 0.25     # how much mood affects work output


# ================================================================
# EMOTIONAL MEMORY
# ================================================================

class EmotionalMemory:
    """A remembered emotional event that can be reinforced over time."""

    __slots__ = ("emotion", "intensity", "cause", "target",
                 "timestamp", "reinforcement_count")

    def __init__(self, emotion: str, intensity: float, cause: str,
                 target: Optional[str] = None, timestamp: float = 0.0):
        self.emotion = emotion
        self.intensity = intensity
        self.cause = cause
        self.target = target
        self.timestamp = timestamp
        self.reinforcement_count = 0

    def reinforce(self, amount: float = 0.1):
        """Strengthen this memory (same event happened again)."""
        self.reinforcement_count += 1
        self.intensity = min(1.0, self.intensity + amount)


# ================================================================
# PERSONALITY (BIG FIVE)
# ================================================================

class Personality:
    """Big Five personality traits, each 0.0 - 1.0."""

    __slots__ = ("openness", "conscientiousness", "extraversion",
                 "agreeableness", "neuroticism")

    def __init__(self, openness: float = 0.5, conscientiousness: float = 0.5,
                 extraversion: float = 0.5, agreeableness: float = 0.5,
                 neuroticism: float = 0.5):
        self.openness = openness
        self.conscientiousness = conscientiousness
        self.extraversion = extraversion
        self.agreeableness = agreeableness
        self.neuroticism = neuroticism

    @classmethod
    def random(cls) -> "Personality":
        """Generate a random personality with mild clustering around 0.5."""
        def _trait():
            return max(0.0, min(1.0, random.gauss(0.5, 0.2)))
        return cls(
            openness=_trait(),
            conscientiousness=_trait(),
            extraversion=_trait(),
            agreeableness=_trait(),
            neuroticism=_trait(),
        )

    @classmethod
    def from_npc(cls, npc) -> "Personality":
        """Derive personality from existing NPC traits for backward compatibility.

        Maps the old personality floats (friendliness, curiosity, bravery)
        and social_traits to Big Five dimensions.
        """
        friendliness = getattr(npc, "friendliness", 0.5)
        curiosity = getattr(npc, "curiosity", 0.5)
        bravery = getattr(npc, "bravery", 0.5)
        social_traits = getattr(npc, "social_traits", [])

        # Map old traits to Big Five
        agreeableness = max(0.0, min(1.0, friendliness * 0.7 + 0.15))
        openness = max(0.0, min(1.0, curiosity * 0.7 + 0.15))
        extraversion = max(0.0, min(1.0,
            friendliness * 0.4 + bravery * 0.3 + 0.15))
        neuroticism = max(0.0, min(1.0, (1.0 - bravery) * 0.6 + 0.2))
        conscientiousness = 0.5  # no direct mapping, stays neutral

        # Adjust from social traits
        trait_set = set(social_traits)
        if "Cheerful" in trait_set or "Friendly" in trait_set:
            extraversion = min(1.0, extraversion + 0.15)
            agreeableness = min(1.0, agreeableness + 0.1)
        if "Grumpy" in trait_set or "Mean" in trait_set:
            agreeableness = max(0.0, agreeableness - 0.2)
            neuroticism = min(1.0, neuroticism + 0.15)
        if "Lazy" in trait_set:
            conscientiousness = max(0.0, conscientiousness - 0.25)
        if "Active" in trait_set or "Ambitious" in trait_set:
            conscientiousness = min(1.0, conscientiousness + 0.2)
        if "Loner" in trait_set:
            extraversion = max(0.0, extraversion - 0.25)
        if "Creative" in trait_set or "Genius" in trait_set:
            openness = min(1.0, openness + 0.2)
        if "Hot-Headed" in trait_set:
            neuroticism = min(1.0, neuroticism + 0.2)
        if "Brave" in trait_set:
            neuroticism = max(0.0, neuroticism - 0.15)

        return cls(
            openness=openness,
            conscientiousness=conscientiousness,
            extraversion=extraversion,
            agreeableness=agreeableness,
            neuroticism=neuroticism,
        )


# ================================================================
# EMOTION STATE (per-NPC)
# ================================================================

class EmotionState:
    """Complete emotional state for a single NPC."""

    __slots__ = ("primary", "emotional_memories", "personality",
                 "mood", "grudges", "bonds")

    def __init__(self, personality: Optional[Personality] = None):
        self.primary: Dict[str, float] = {e: 0.0 for e in PRIMARY_EMOTIONS}
        self.emotional_memories: List[EmotionalMemory] = []
        self.personality: Personality = personality or Personality()
        self.mood: float = 0.0  # rolling average of valence, -1 to 1
        self.grudges: Dict[str, Dict] = {}
        # target_name -> {"emotion": str, "intensity": float,
        #                  "cause": str, "timestamp": float}
        self.bonds: Dict[str, Dict] = {}
        # target_name -> {"emotion": str, "intensity": float, "cause": str}

    # -- Secondary emotions (computed on demand) --

    def get_secondary(self, name: str) -> float:
        """Compute a secondary emotion from its two primary components."""
        pair = SECONDARY_EMOTIONS.get(name)
        if not pair:
            return 0.0
        a, b = pair
        # Geometric mean biased toward the weaker component
        va = self.primary.get(a, 0.0)
        vb = self.primary.get(b, 0.0)
        if va <= 0.0 or vb <= 0.0:
            return 0.0
        return math.sqrt(va * vb)

    def get_all_secondary(self) -> Dict[str, float]:
        """Return all secondary emotion values."""
        return {name: self.get_secondary(name)
                for name in SECONDARY_EMOTIONS}

    # -- Queries --

    def dominant_emotion(self) -> Tuple[str, float]:
        """Return (emotion_name, intensity) for the strongest primary."""
        best_name = "joy"
        best_val = 0.0
        for name, val in self.primary.items():
            if val > best_val:
                best_val = val
                best_name = name
        return best_name, best_val

    def emotion_label(self, emotion: str) -> str:
        """Return the intensity-appropriate label for an emotion."""
        val = self.primary.get(emotion, 0.0)
        if val <= 0.01:
            return "neutral"
        info = EMOTION_LABELS.get(emotion)
        if not info:
            return emotion
        threshold, low, mid, high = info
        if val < threshold:
            return low
        elif val < threshold * 2:
            return mid
        else:
            return high

    def valence(self) -> float:
        """Compute current emotional valence (-1 to 1)."""
        total = 0.0
        weight = 0.0
        for emotion, val in self.primary.items():
            v = EMOTION_VALENCE.get(emotion, 0.0)
            total += v * val
            weight += val
        if weight < 0.01:
            return 0.0
        return max(-1.0, min(1.0, total / max(weight, 0.5)))


# ================================================================
# TRIGGER FUNCTION
# ================================================================

def trigger_emotion(npc, event_type: str, intensity: float = 1.0,
                    target: Optional[str] = None, cause: str = "",
                    game_time: float = 0.0):
    """Apply an emotional event to an NPC.

    Args:
        npc: The NPC object (must have emotion_state attribute).
        event_type: One of the EVENT_RESPONSES keys.
        intensity: Multiplier on the base intensities (0-2 typical).
        target: Name of person/entity involved (for grudges/bonds).
        cause: Human-readable description of what happened.
        game_time: Current game time for timestamping memories.
    """
    es = getattr(npc, "emotion_state", None)
    if es is None:
        return

    responses = EVENT_RESPONSES.get(event_type)
    if not responses:
        return

    personality = es.personality

    # Grab cached mental health emotion multipliers (if any)
    _mh_emotion_mults = getattr(npc, '_mh_cached_emotion_mults', None)

    for emotion, base_intensity in responses:
        # Modulate by personality
        mod = _personality_modifier(personality, emotion)
        # Modulate by mental health conditions (cached multipliers)
        if _mh_emotion_mults:
            mh_mult = _mh_emotion_mults.get(emotion)
            if mh_mult is not None:
                mod *= mh_mult
        final_intensity = max(0.0, min(1.0, base_intensity * intensity * mod))

        if final_intensity < 0.01:
            continue

        # Apply to primary emotion (additive with soft cap)
        old = es.primary[emotion]
        # Diminishing returns: the higher the current value, the less new
        # stimulus adds. This prevents emotions from permanently pegging at 1.0
        headroom = 1.0 - old
        es.primary[emotion] = old + final_intensity * headroom

        # Record emotional memory
        mem = EmotionalMemory(
            emotion=emotion,
            intensity=final_intensity,
            cause=cause or event_type,
            target=target,
            timestamp=game_time,
        )

        # Check for reinforcement of existing similar memory
        reinforced = False
        for existing in es.emotional_memories:
            if (existing.emotion == emotion and
                existing.target == target and
                    existing.cause == mem.cause):
                existing.reinforce(final_intensity * 0.3)
                reinforced = True
                break

        if not reinforced:
            es.emotional_memories.append(mem)
            # Prune if too many memories
            if len(es.emotional_memories) > MAX_EMOTIONAL_MEMORIES:
                # Remove oldest low-intensity, unreinforced memories first
                es.emotional_memories.sort(
                    key=lambda m: m.intensity + m.reinforcement_count * 0.2)
                es.emotional_memories.pop(0)

    # Update grudges and bonds based on event valence
    if target:
        net_valence = 0.0
        for emotion, base_intensity in responses:
            v = EMOTION_VALENCE.get(emotion, 0.0)
            net_valence += v * base_intensity * intensity

        if net_valence < -0.3:
            # Negative event -> grudge
            dominant = max(responses, key=lambda r: r[1])[0]
            if target in es.grudges:
                es.grudges[target]["intensity"] = min(
                    1.0, es.grudges[target]["intensity"] + abs(net_valence) * 0.3)
            else:
                es.grudges[target] = {
                    "emotion": dominant,
                    "intensity": min(1.0, abs(net_valence)),
                    "cause": cause or event_type,
                    "timestamp": game_time,
                }
        elif net_valence > 0.3:
            # Positive event -> bond
            dominant = max(responses, key=lambda r: r[1])[0]
            if target in es.bonds:
                es.bonds[target]["intensity"] = min(
                    1.0, es.bonds[target]["intensity"] + net_valence * 0.3)
            else:
                es.bonds[target] = {
                    "emotion": dominant,
                    "intensity": min(1.0, net_valence),
                    "cause": cause or event_type,
                }


def _personality_modifier(personality: Personality, emotion: str) -> float:
    """Compute personality-based multiplier for a given emotion."""
    # High neuroticism amplifies negative emotions, dampens positive
    # High agreeableness amplifies trust/joy, dampens anger/disgust
    # High extraversion amplifies joy/surprise
    # High openness amplifies surprise/anticipation
    mod = 1.0

    if emotion in ("fear", "sadness", "anger", "disgust"):
        # Negative emotions amplified by neuroticism
        mod += (personality.neuroticism - 0.5) * 0.6
    elif emotion in ("joy", "trust"):
        # Positive emotions dampened by neuroticism, boosted by agreeableness
        mod -= (personality.neuroticism - 0.5) * 0.3
        mod += (personality.agreeableness - 0.5) * 0.4

    if emotion == "anger":
        # Agreeable people feel less anger
        mod -= (personality.agreeableness - 0.5) * 0.5
    elif emotion == "trust":
        mod += (personality.agreeableness - 0.5) * 0.4
    elif emotion == "surprise":
        mod += (personality.openness - 0.5) * 0.3
    elif emotion == "anticipation":
        mod += (personality.openness - 0.5) * 0.3
        mod += (personality.conscientiousness - 0.5) * 0.2
    elif emotion == "joy":
        mod += (personality.extraversion - 0.5) * 0.3
    elif emotion == "fear":
        # Brave (low neuroticism) people feel less fear
        mod += (personality.neuroticism - 0.5) * 0.4

    return max(0.2, min(2.0, mod))


# ================================================================
# EMOTION SYSTEM (global manager)
# ================================================================


# ================================================================
# SPECIES-BASED PERSONALITY TEMPLATES
# ================================================================

# Prey animals: high neuroticism, low agreeableness, low extraversion
_PREY_SPECIES = {"deer", "rabbit", "elk", "pheasant", "chicken", "sheep",
                 "goat", "fish_school", "cow", "pig", "donkey", "mule",
                 "camel", "horse", "war_horse"}

# Predators: low neuroticism, low agreeableness, high conscientiousness
_PREDATOR_SPECIES = {"wolf", "bear", "spider", "dire_wolf", "giant_spider",
                     "owlbear", "manticore", "basilisk", "chimera",
                     "displacer_beast", "wyvern", "phase_spider", "fox",
                     "crocodile", "panther", "lion", "tiger", "hawk",
                     "snake", "scorpion"}

# Pack animals: moderate extraversion bonus
_PACK_SPECIES = {"wolf", "dire_wolf", "goblin", "kobold", "gnoll"}

# Intelligent monsters: full personality range, high openness
_INTELLIGENT_SPECIES = {"dragon", "red_dragon", "lich", "vampire",
                        "mind_flayer", "green_dragon", "beholder"}

# Undead: these radiate fear
_UNDEAD_TYPES = {"undead"}


def personality_for_creature(kind: str, monster_type: str = "beast") -> Personality:
    """Build a species-appropriate Big Five personality for a creature."""
    if kind in _INTELLIGENT_SPECIES or monster_type == "dragon":
        return Personality(
            openness=random.uniform(0.7, 0.95),
            conscientiousness=random.uniform(0.5, 0.8),
            extraversion=random.uniform(0.3, 0.7),
            agreeableness=random.uniform(0.1, 0.5),
            neuroticism=random.uniform(0.2, 0.5),
        )
    if kind in _PREY_SPECIES:
        p = Personality(
            openness=random.uniform(0.2, 0.5),
            conscientiousness=random.uniform(0.3, 0.5),
            extraversion=0.2 + random.uniform(0.0, 0.15),
            agreeableness=0.3 + random.uniform(0.0, 0.15),
            neuroticism=0.8 + random.uniform(-0.1, 0.1),
        )
        if kind in _PACK_SPECIES:
            p.extraversion = max(p.extraversion, 0.6)
        return p
    if kind in _PREDATOR_SPECIES:
        p = Personality(
            openness=random.uniform(0.2, 0.5),
            conscientiousness=0.7 + random.uniform(-0.1, 0.1),
            extraversion=random.uniform(0.2, 0.4),
            agreeableness=0.2 + random.uniform(0.0, 0.15),
            neuroticism=0.3 + random.uniform(-0.1, 0.1),
        )
        if kind in _PACK_SPECIES:
            p.extraversion = max(p.extraversion, 0.6)
        return p
    # Generic / humanoid monsters
    p = Personality.random()
    if kind in _PACK_SPECIES:
        p.extraversion = max(p.extraversion, 0.6)
    if monster_type in _UNDEAD_TYPES:
        p.neuroticism = random.uniform(0.1, 0.3)
        p.agreeableness = random.uniform(0.0, 0.15)
    return p


def personality_for_player() -> Personality:
    """Create a balanced personality for the player character."""
    return Personality(
        openness=0.6,
        conscientiousness=0.5,
        extraversion=0.5,
        agreeableness=0.5,
        neuroticism=0.4,
    )


class EmotionSystem:
    """Manages emotion decay, mood updates, and behavioral queries for all NPCs."""

    def __init__(self):
        self._behavior_timer = 0.0
        self._behavior_interval = 5.0  # seconds between expensive checks
        self._contagion_timer = 0.0
        self._contagion_interval = 10.0  # seconds between contagion sweeps
        self.event_log: List[str] = []

    def initialize_npc(self, npc):
        """Attach an EmotionState to an NPC if it doesn't have one."""
        if hasattr(npc, "emotion_state") and npc.emotion_state is not None:
            return
        personality = Personality.from_npc(npc)
        npc.emotion_state = EmotionState(personality)

    def initialize_creature(self, creature):
        """Attach an EmotionState to a creature with species-appropriate personality."""
        if hasattr(creature, "emotion_state") and creature.emotion_state is not None:
            return
        kind = getattr(creature, "kind", "beast")
        mtype = getattr(creature, "monster_type", "beast")
        personality = personality_for_creature(kind, mtype)
        creature.emotion_state = EmotionState(personality)

    def initialize_player(self, player):
        """Attach an EmotionState to the player character."""
        if hasattr(player, "emotion_state") and player.emotion_state is not None:
            return
        player.emotion_state = EmotionState(personality_for_player())

    def update(self, dt: float, npcs: list, game_time: float,
               creatures: list = None, player=None):
        """Main tick: decay emotions, update moods, throttled behavioral checks.

        Args:
            dt: Delta time in seconds.
            npcs: List of all NPC objects.
            game_time: Current game time for memory timestamps.
            creatures: Optional list of Creature objects.
            player: Optional player object.
        """
        # Decay and mood update for every NPC (cheap: 8 floats per NPC)
        for npc in npcs:
            if not getattr(npc, "alive", True):
                continue
            es = getattr(npc, "emotion_state", None)
            if es is None:
                # Lazy initialization for NPCs spawned after system init
                self.initialize_npc(npc)
                es = npc.emotion_state
            self._decay_emotions(es, dt)
            self._update_mood(es)

        # Decay and mood for creatures (only those near player for perf)
        if creatures:
            px = getattr(player, 'x', 0) if player else 0
            py = getattr(player, 'y', 0) if player else 0
            for c in creatures:
                if not getattr(c, "alive", True):
                    continue
                # Only process creatures within 40 tiles of player
                dx = getattr(c, 'x', 0) - px
                dy = getattr(c, 'y', 0) - py
                if dx * dx + dy * dy > 1600:
                    continue
                es = getattr(c, "emotion_state", None)
                if es is None:
                    self.initialize_creature(c)
                    es = c.emotion_state
                self._decay_emotions(es, dt)
                self._update_mood(es)

        # Decay and mood for player
        if player:
            es = getattr(player, "emotion_state", None)
            if es is None:
                self.initialize_player(player)
                es = player.emotion_state
            self._decay_emotions(es, dt)
            self._update_mood(es)

        # Throttled behavioral checks (expensive: relationship queries)
        self._behavior_timer += dt
        if self._behavior_timer >= self._behavior_interval:
            self._behavior_timer = 0.0
            for npc in npcs:
                if not getattr(npc, "alive", True):
                    continue
                es = getattr(npc, "emotion_state", None)
                if es is None:
                    continue
                self._check_behavioral_triggers(npc, es, game_time)

        # Emotional contagion (throttled, near player only)
        self._contagion_timer += dt
        if self._contagion_timer >= self._contagion_interval:
            self._contagion_timer = 0.0
            all_entities = list(npcs)
            if creatures:
                # Only include nearby creatures
                px = getattr(player, 'x', 0) if player else 0
                py = getattr(player, 'y', 0) if player else 0
                for c in creatures:
                    if not getattr(c, 'alive', True):
                        continue
                    dx = getattr(c, 'x', 0) - px
                    dy = getattr(c, 'y', 0) - py
                    if dx * dx + dy * dy < 2500:  # 50 tile radius
                        all_entities.append(c)
            if player:
                all_entities.append(player)
            self.spread_emotions(all_entities, self._contagion_interval)

    def spread_emotions(self, entities: list, dt: float):
        """Spread dominant emotions between nearby entities.

        - Panic spreads: fear > 0.7 -> nearby same-species get fear +0.2
        - Anger spreads: fighting anger spreads to allies
        - Joy spreads: to nearby friendly NPCs
        - Undead aura: undead radiate fear to living within 8 tiles
        """
        if len(entities) < 2:
            return

        for source in entities:
            es = getattr(source, "emotion_state", None)
            if es is None or not getattr(source, "alive", True):
                continue

            sx = getattr(source, 'x', 0)
            sy = getattr(source, 'y', 0)
            source_kind = getattr(source, 'kind', None)
            source_faction = getattr(source, 'faction', '')
            source_mtype = getattr(source, 'monster_type', '')
            is_undead = source_mtype == "undead"

            # Determine what to spread
            fear_val = es.primary.get("fear", 0.0)
            anger_val = es.primary.get("anger", 0.0)
            joy_val = es.primary.get("joy", 0.0)

            for target in entities:
                if target is source:
                    continue
                tes = getattr(target, "emotion_state", None)
                if tes is None or not getattr(target, "alive", True):
                    continue

                tx = getattr(target, 'x', 0)
                ty = getattr(target, 'y', 0)
                dist_sq = (sx - tx) ** 2 + (sy - ty) ** 2

                target_kind = getattr(target, 'kind', None)
                target_mtype = getattr(target, 'monster_type', '')

                # Undead aura: radiate fear to living within 8 tiles
                if is_undead and target_mtype != "undead" and dist_sq <= 64:
                    headroom = 1.0 - tes.primary.get("fear", 0.0)
                    tes.primary["fear"] = tes.primary.get("fear", 0.0) + 0.15 * headroom
                    continue

                # Within 5 tiles
                if dist_sq > 25:
                    continue

                # Panic spreads to same species
                if fear_val > 0.7 and source_kind and source_kind == target_kind:
                    headroom = 1.0 - tes.primary.get("fear", 0.0)
                    tes.primary["fear"] = tes.primary.get("fear", 0.0) + 0.2 * headroom

                # Anger spreads to allies (same faction or same species)
                if anger_val > 0.5:
                    same_side = (source_faction and source_faction == getattr(target, 'faction', '')) or \
                                (source_kind and source_kind == target_kind)
                    if same_side:
                        headroom = 1.0 - tes.primary.get("anger", 0.0)
                        tes.primary["anger"] = tes.primary.get("anger", 0.0) + 0.15 * headroom

                # Joy spreads to nearby friendly NPCs
                if joy_val > 0.5:
                    # Both are NPCs or player
                    if not source_kind and not target_kind:
                        headroom = 1.0 - tes.primary.get("joy", 0.0)
                        tes.primary["joy"] = tes.primary.get("joy", 0.0) + 0.1 * headroom

    def _decay_emotions(self, es: EmotionState, dt: float):
        """Decay all primary emotions toward 0."""
        personality = es.personality

        # Neuroticism slows decay of negative emotions
        neg_decay_mult = 1.0 - (personality.neuroticism - 0.5) * 0.4
        pos_decay_mult = 1.0 + (personality.neuroticism - 0.5) * 0.2

        for emotion in PRIMARY_EMOTIONS:
            val = es.primary[emotion]
            if val <= 0.0:
                continue

            # Base decay
            is_negative = EMOTION_VALENCE.get(emotion, 0.0) < 0
            decay_mult = neg_decay_mult if is_negative else pos_decay_mult

            # Check if this emotion has reinforced memories (slower decay)
            reinforcement_bonus = 0.0
            for mem in es.emotional_memories:
                if mem.emotion == emotion and mem.reinforcement_count > 0:
                    reinforcement_bonus = max(
                        reinforcement_bonus,
                        mem.reinforcement_count * (1.0 - REINFORCEMENT_DECAY_FACTOR))
            decay_mult *= max(0.3, 1.0 - reinforcement_bonus)

            decay = BASE_DECAY_RATE * decay_mult * dt
            es.primary[emotion] = max(0.0, val - decay)

    def _update_mood(self, es: EmotionState):
        """Update rolling mood average from current emotional valence."""
        current_valence = es.valence()
        es.mood = es.mood * (1.0 - MOOD_ALPHA) + current_valence * MOOD_ALPHA

    def _check_behavioral_triggers(self, npc, es: EmotionState,
                                   game_time: float):
        """Check for emotion-driven behavioral changes (throttled)."""
        # Prune old grudges (fade after ~10 game-days = 6000 seconds)
        stale = []
        for target, grudge in es.grudges.items():
            age = game_time - grudge.get("timestamp", 0.0)
            if age > 6000:
                grudge["intensity"] *= 0.9
                if grudge["intensity"] < 0.05:
                    stale.append(target)
        for t in stale:
            del es.grudges[t]

        # Prune weak bonds
        stale_bonds = [t for t, b in es.bonds.items()
                       if b["intensity"] < 0.02]
        for t in stale_bonds:
            del es.bonds[t]

    # ================================================================
    # PUBLIC QUERY API
    # ================================================================

    @staticmethod
    def get_dominant_emotion(npc) -> Tuple[str, float]:
        """Return (emotion_name, intensity) for the NPC's strongest emotion."""
        es = getattr(npc, "emotion_state", None)
        if es is None:
            return ("joy", 0.0)
        return es.dominant_emotion()

    @staticmethod
    def get_mood_label(npc) -> str:
        """Return a human-readable mood description."""
        es = getattr(npc, "emotion_state", None)
        if es is None:
            return "calm"

        mood = es.mood
        dominant, intensity = es.dominant_emotion()

        # If a strong emotion dominates, describe it
        if intensity > 0.5:
            label = es.emotion_label(dominant)
            return label

        # Otherwise describe general mood
        if mood > 0.5:
            return "content"
        elif mood > 0.2:
            return "pleasant"
        elif mood > -0.2:
            return "calm"
        elif mood > -0.5:
            return "uneasy"
        else:
            return "distressed"

    @staticmethod
    def get_relationship_sentiment(npc, target_name: str) -> float:
        """Return net feeling toward a target (-1 to 1).

        Positive = bond, negative = grudge. Zero = neutral.
        """
        es = getattr(npc, "emotion_state", None)
        if es is None:
            return 0.0

        sentiment = 0.0
        bond = es.bonds.get(target_name)
        if bond:
            sentiment += bond["intensity"]
        grudge = es.grudges.get(target_name)
        if grudge:
            sentiment -= grudge["intensity"]

        return max(-1.0, min(1.0, sentiment))

    @staticmethod
    def should_rebel(npc) -> bool:
        """Check if the NPC's anger and distrust toward their leader
        exceeds the rebellion threshold."""
        es = getattr(npc, "emotion_state", None)
        if es is None:
            return False

        anger = es.primary.get("anger", 0.0)
        trust = es.primary.get("trust", 0.0)
        disgust = es.primary.get("disgust", 0.0)

        # Find the NPC's leader / faction ruler
        faction = getattr(npc, "faction", "")
        if not faction:
            return False

        # Check grudge against faction (proxy for leader)
        leader_grudge = 0.0
        for target, grudge in es.grudges.items():
            # Grudge against anyone in leadership
            if target == faction:
                leader_grudge = grudge["intensity"]
                break

        rebellion_score = (anger * 0.4 + (1.0 - trust) * 0.3 +
                           disgust * 0.15 + leader_grudge * 0.15)
        return rebellion_score > REBEL_THRESHOLD

    @staticmethod
    def should_commit_crime(npc) -> bool:
        """Check if desperation (fear + anger + low trust) pushes
        the NPC toward criminal behavior."""
        es = getattr(npc, "emotion_state", None)
        if es is None:
            return False

        fear = es.primary.get("fear", 0.0)
        anger = es.primary.get("anger", 0.0)
        trust = es.primary.get("trust", 0.0)
        sadness = es.primary.get("sadness", 0.0)

        # Conscientiousness and agreeableness inhibit crime
        inhibition = (es.personality.conscientiousness * 0.4 +
                      es.personality.agreeableness * 0.3)

        desperation = (fear * 0.3 + anger * 0.3 +
                       (1.0 - trust) * 0.2 + sadness * 0.2)
        return (desperation - inhibition * 0.5) > CRIME_THRESHOLD

    @staticmethod
    def get_work_modifier(npc) -> float:
        """Return a work output multiplier (0.3 to 1.5) based on mood
        and mental health conditions.

        Happy NPCs work better, miserable ones work worse.
        Mental conditions (depression, burnout, etc.) further reduce output.
        """
        es = getattr(npc, "emotion_state", None)
        if es is None:
            return 1.0

        # Mood ranges from -1 to 1
        mood_bonus = es.mood * WORK_MOOD_WEIGHT

        # Conscientiousness buffers against mood drops
        buffer = (es.personality.conscientiousness - 0.5) * 0.2
        modifier = 1.0 + mood_bonus + buffer

        # Apply mental health work modifier (cached)
        mh_stat_mults = getattr(npc, '_mh_cached_stat_mults', None)
        if mh_stat_mults:
            mh_work = mh_stat_mults.get("work")
            if mh_work is not None:
                modifier *= mh_work

        return max(0.3, min(1.5, modifier))

    def get_event_log(self) -> List[str]:
        """Get and clear the event log."""
        log = list(self.event_log)
        self.event_log.clear()
        return log
