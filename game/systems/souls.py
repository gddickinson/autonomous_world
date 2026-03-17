"""Soul system — metaphysical layer where a fixed pool of souls inhabit
living creatures, persist across death, and carry memories between lives.

Souls are tracked individually (up to MAX_TRACKED_SOULS) or handled
statistically.  Ghost souls drift near their death location before
eventually rejoining the free pool for reincarnation.  Souls persist
across saves via data/souls.json.
"""

import json
import math
import os
import random
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# EchoMemory — a fragment of memory carried between lives
# ---------------------------------------------------------------------------

class EchoMemory:
    """A strong memory from a past life that bleeds through incarnations."""

    def __init__(self, text: str, emotion: str, intensity: float,
                 life_number: int, host_name: str, host_type: str):
        self.text = text              # short description of the memory
        self.emotion = emotion        # primary emotion associated
        self.intensity = intensity    # 0-1
        self.life_number = life_number  # which incarnation
        self.host_name = host_name    # name of the creature that had this memory
        self.host_type = host_type    # "npc", "creature"

    # -- serialisation helpers --

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "emotion": self.emotion,
            "intensity": self.intensity,
            "life_number": self.life_number,
            "host_name": self.host_name,
            "host_type": self.host_type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EchoMemory":
        return cls(
            text=d["text"],
            emotion=d["emotion"],
            intensity=d.get("intensity", 0.5),
            life_number=d.get("life_number", 0),
            host_name=d.get("host_name", "unknown"),
            host_type=d.get("host_type", "npc"),
        )


# ---------------------------------------------------------------------------
# Soul
# ---------------------------------------------------------------------------

class Soul:
    """A single soul that persists across lives."""

    def __init__(self, soul_id: int):
        self.soul_id: int = soul_id       # unique persistent ID
        self.age: float = 0.0             # total time existed across all incarnations
        self.incarnation_count: int = 0   # how many bodies this soul has inhabited
        self.alignment: float = 0.0       # -1.0 evil to 1.0 good, drifts with host actions
        self.affinity: str = "neutral"    # "warrior", "scholar", "nature", "divine", "arcane", "neutral"
        self.power: float = 1.0           # grows with experience, range 1-100
        self.echo_memories: List[EchoMemory] = []
        self.current_host: Optional[str] = None   # name of current NPC/creature, or None
        self.host_type: Optional[str] = None       # "npc", "creature", None
        self.state: str = "embodied"      # "embodied", "ghost", "consumed", "divine"

        # Ghost state
        self.ghost_x: float = 0.0
        self.ghost_y: float = 0.0
        self.ghost_drift_target: Optional[Tuple[float, float]] = None
        self.time_as_ghost: float = 0.0
        self.ghost_duration: float = 0.0  # how long this ghost must wander
        self.death_type: Optional[str] = None  # "natural", "violent", "sacrifice", "undead"

        # Last death location (used for geographic rebirth preference)
        self.last_death_x: float = 0.0
        self.last_death_y: float = 0.0

    # -- serialisation --

    def to_dict(self) -> dict:
        return {
            "soul_id": self.soul_id,
            "age": self.age,
            "incarnation_count": self.incarnation_count,
            "alignment": self.alignment,
            "affinity": self.affinity,
            "power": self.power,
            "echo_memories": [m.to_dict() for m in self.echo_memories],
            "current_host": self.current_host,
            "host_type": self.host_type,
            "state": self.state,
            "ghost_x": self.ghost_x,
            "ghost_y": self.ghost_y,
            "ghost_drift_target": self.ghost_drift_target,
            "time_as_ghost": self.time_as_ghost,
            "ghost_duration": self.ghost_duration,
            "death_type": self.death_type,
            "last_death_x": self.last_death_x,
            "last_death_y": self.last_death_y,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Soul":
        s = cls(d["soul_id"])
        s.age = d.get("age", 0.0)
        s.incarnation_count = d.get("incarnation_count", 0)
        s.alignment = d.get("alignment", 0.0)
        s.affinity = d.get("affinity", "neutral")
        s.power = d.get("power", 1.0)
        s.echo_memories = [EchoMemory.from_dict(m) for m in d.get("echo_memories", [])]
        s.current_host = d.get("current_host")
        s.host_type = d.get("host_type")
        s.state = d.get("state", "embodied")
        s.ghost_x = d.get("ghost_x", 0.0)
        s.ghost_y = d.get("ghost_y", 0.0)
        s.ghost_drift_target = d.get("ghost_drift_target")
        s.time_as_ghost = d.get("time_as_ghost", 0.0)
        s.ghost_duration = d.get("ghost_duration", 0.0)
        s.death_type = d.get("death_type")
        s.last_death_x = d.get("last_death_x", 0.0)
        s.last_death_y = d.get("last_death_y", 0.0)
        return s


# ---------------------------------------------------------------------------
# SoulPool — the total inventory of souls in the world
# ---------------------------------------------------------------------------

class SoulPool:
    """Manages the complete pool of souls, both tracked and statistical."""

    MAX_TRACKED_SOULS: int = 500  # individually tracked

    def __init__(self, seed: Optional[int] = None):
        self.souls: Dict[int, Soul] = {}
        self.free_souls: List[int] = []       # soul_ids not in a body
        self.ghost_souls: List[int] = []      # soul_ids in ghost state
        self.statistical_soul_count: int = 2000  # untracked souls handled statistically
        self._next_id: int = 0
        self._rng = random.Random(seed)

    def create_soul(self) -> Soul:
        """Create a new tracked soul and return it."""
        soul = Soul(self._next_id)
        self._next_id += 1
        # Assign a random affinity
        soul.affinity = self._rng.choice(
            ["warrior", "scholar", "nature", "divine", "arcane", "neutral"]
        )
        self.souls[soul.soul_id] = soul
        return soul

    def remove_soul(self, soul_id: int):
        """Permanently destroy a soul (e.g. consumed by undead)."""
        if soul_id in self.souls:
            del self.souls[soul_id]
        if soul_id in self.free_souls:
            self.free_souls.remove(soul_id)
        if soul_id in self.ghost_souls:
            self.ghost_souls.remove(soul_id)

    # -- serialisation --

    def to_dict(self) -> dict:
        return {
            "souls": {str(k): v.to_dict() for k, v in self.souls.items()},
            "free_souls": self.free_souls,
            "ghost_souls": self.ghost_souls,
            "statistical_soul_count": self.statistical_soul_count,
            "_next_id": self._next_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SoulPool":
        pool = cls()
        pool._next_id = d.get("_next_id", 0)
        pool.statistical_soul_count = d.get("statistical_soul_count", 2000)
        pool.free_souls = d.get("free_souls", [])
        pool.ghost_souls = d.get("ghost_souls", [])
        for k, v in d.get("souls", {}).items():
            soul = Soul.from_dict(v)
            pool.souls[soul.soul_id] = soul
        return pool


# ---------------------------------------------------------------------------
# Affinity scoring helpers
# ---------------------------------------------------------------------------

# Map NPC char_class / profession to affinity matches
_CLASS_AFFINITY: Dict[str, str] = {
    "Fighter": "warrior", "Barbarian": "warrior", "Paladin": "warrior",
    "Ranger": "nature", "Druid": "nature",
    "Wizard": "arcane", "Sorcerer": "arcane", "Warlock": "arcane",
    "Cleric": "divine", "Monk": "divine",
    "Bard": "scholar", "Rogue": "scholar",
}

_PROFESSION_AFFINITY: Dict[str, str] = {
    "Guard": "warrior", "Captain": "warrior", "Soldier": "warrior",
    "Farmer": "nature", "Herbalist": "nature", "Shepherd": "nature",
    "Woodcutter": "nature", "Hunter": "nature",
    "Scholar": "scholar", "Scribe": "scholar", "Philosopher": "scholar",
    "Cartographer": "scholar",
    "Healer": "divine", "Cleric": "divine",
    "Alchemist": "arcane", "Jeweler": "arcane",
}

_SETTLEMENT_AFFINITY: Dict[str, str] = {
    "hamlet": "nature",
    "village": "neutral",
    "town": "scholar",
    "city": "scholar",
    "castle": "warrior",
}

# Emotions for trauma memories
_VIOLENT_EMOTIONS = ["anger", "fear", "anguish", "rage", "despair"]
_NATURAL_EMOTIONS = ["peace", "acceptance", "nostalgia", "serenity"]


def _host_affinity(entity) -> str:
    """Determine what soul affinity best matches this entity."""
    # NPC: check char_class first, then profession
    char_class = getattr(entity, "char_class", None)
    if char_class and char_class in _CLASS_AFFINITY:
        return _CLASS_AFFINITY[char_class]
    profession = getattr(entity, "profession", None)
    if profession and profession in _PROFESSION_AFFINITY:
        return _PROFESSION_AFFINITY[profession]
    # Creature: nature for beasts, arcane for magical
    monster_type = getattr(entity, "monster_type", None)
    if monster_type:
        if monster_type in ("beast", "plant"):
            return "nature"
        if monster_type in ("aberration", "dragon", "elemental", "fey"):
            return "arcane"
        if monster_type in ("celestial",):
            return "divine"
        if monster_type in ("undead", "fiend"):
            return "warrior"  # conflict-aligned
    return "neutral"


def _score_soul_for_host(soul: Soul, entity, settlement_kind: Optional[str] = None) -> float:
    """Score how well a free/ghost soul matches a new host. Higher = better."""
    score = 0.0
    host_aff = _host_affinity(entity)

    # Affinity match: +30
    if soul.affinity == host_aff:
        score += 30.0
    elif soul.affinity == "neutral" or host_aff == "neutral":
        score += 10.0

    # Settlement match: +15
    if settlement_kind:
        sett_aff = _SETTLEMENT_AFFINITY.get(settlement_kind, "neutral")
        if soul.affinity == sett_aff:
            score += 15.0

    # Geographic proximity to last death: +0-20 (closer = higher)
    ex = getattr(entity, "x", 0.0)
    ey = getattr(entity, "y", 0.0)
    dist = math.sqrt((soul.last_death_x - ex) ** 2 + (soul.last_death_y - ey) ** 2)
    geo_score = max(0.0, 20.0 - dist * 0.1)
    score += geo_score

    # Old souls slightly prefer new bodies (variety bonus)
    if soul.incarnation_count > 3:
        score += 5.0

    # Add some randomness so it's not deterministic
    score += random.uniform(0, 10)
    return score


# ---------------------------------------------------------------------------
# SoulSystem — the main manager
# ---------------------------------------------------------------------------

class SoulSystem:
    """Manages the soul lifecycle: birth assignment, ghost phase, reincarnation,
    and persistence across saves."""

    SAVE_PATH = os.path.join("data", "souls.json")

    def __init__(self, pool: Optional[SoulPool] = None):
        self.pool: SoulPool = pool or SoulPool()
        self.ghost_fade_time: float = 100.0   # game-time before ghost finds new body
        self.reincarnation_enabled: bool = True
        self._past_life_day_checked: Dict[str, int] = {}  # npc_name -> last day checked

    # ------------------------------------------------------------------
    # Main tick
    # ------------------------------------------------------------------

    def update(self, dt: float, game_time: float, npcs: list, creatures: list):
        """Main tick — update ghosts, handle reincarnation queue."""
        self._age_souls(dt)
        self._update_ghosts(dt, game_time)
        self._try_reincarnations(npcs, creatures, game_time)

    # ------------------------------------------------------------------
    # Birth — assign a soul to a newborn
    # ------------------------------------------------------------------

    def on_birth(self, entity, game_time: float, settlement_kind: Optional[str] = None):
        """Assign a soul to a newborn NPC or creature.

        Prefers affinity-matching free souls; falls back to ghosts, then creates
        new tracked souls (up to pool cap), or leaves untracked (statistical).
        """
        # Already has a tracked soul?
        if getattr(entity, "soul_id", None) is not None:
            return

        # Determine entity type label
        host_type = "npc" if hasattr(entity, "profession") else "creature"
        host_name = getattr(entity, "name", None) or getattr(entity, "kind", "unknown")

        # Gather candidates from free pool + ghost pool
        candidate_ids = list(self.pool.free_souls) + list(self.pool.ghost_souls)
        best_id: Optional[int] = None
        best_score: float = -1.0

        for sid in candidate_ids:
            soul = self.pool.souls.get(sid)
            if soul is None:
                continue
            sc = _score_soul_for_host(soul, entity, settlement_kind)
            if sc > best_score:
                best_score = sc
                best_id = sid

        if best_id is not None:
            soul = self.pool.souls[best_id]
        elif len(self.pool.souls) < SoulPool.MAX_TRACKED_SOULS:
            soul = self.pool.create_soul()
        else:
            # Use statistical (untracked) — no individual soul assigned
            entity.soul_id = None
            return

        # Remove from free / ghost lists
        if soul.soul_id in self.pool.free_souls:
            self.pool.free_souls.remove(soul.soul_id)
        if soul.soul_id in self.pool.ghost_souls:
            self.pool.ghost_souls.remove(soul.soul_id)

        # Bind soul to host
        soul.current_host = host_name
        soul.host_type = host_type
        soul.state = "embodied"
        soul.incarnation_count += 1
        soul.time_as_ghost = 0.0
        soul.ghost_drift_target = None
        soul.death_type = None
        entity.soul_id = soul.soul_id

        # Old soul bonus: 10% chance to bring a past-life skill bonus
        if soul.incarnation_count > 5 and random.random() < 0.10:
            self._apply_past_life_bonus(soul, entity)

    # ------------------------------------------------------------------
    # Death — release a soul from a dying host
    # ------------------------------------------------------------------

    def on_death(self, entity, death_type: str, game_time: float,
                 buried: bool = False):
        """Release soul from dying host into ghost state.

        *death_type*: ``"natural"``, ``"violent"``, ``"sacrifice"``, ``"undead"``
        """
        soul_id = getattr(entity, "soul_id", None)
        if soul_id is None:
            return  # untracked soul — nothing to do

        soul = self.pool.souls.get(soul_id)
        if soul is None:
            entity.soul_id = None
            return

        host_name = soul.current_host or getattr(entity, "name", None) or getattr(entity, "kind", "unknown")
        host_type = soul.host_type or ("npc" if hasattr(entity, "profession") else "creature")

        # Extract 1-2 strongest memories from host -> echo_memories
        self._extract_echo_memories(soul, entity, host_name, host_type)

        # Record death location
        soul.last_death_x = getattr(entity, "x", 0.0)
        soul.last_death_y = getattr(entity, "y", 0.0)
        soul.death_type = death_type

        # Unbind from host
        soul.current_host = None
        soul.host_type = None
        entity.soul_id = None

        # Soul power grows slightly with each death
        soul.power = min(100.0, soul.power + 0.5)

        if death_type == "sacrifice":
            # Claimed by a god — removed from circulation temporarily
            soul.state = "divine"
            return

        # Set ghost state
        soul.state = "ghost"
        soul.ghost_x = soul.last_death_x
        soul.ghost_y = soul.last_death_y
        soul.time_as_ghost = 0.0

        # Determine ghost duration based on death type
        if death_type == "violent":
            base_duration = random.uniform(50.0, 100.0)
            # Add trauma memory
            emotion = random.choice(_VIOLENT_EMOTIONS)
            soul.echo_memories.append(EchoMemory(
                text=f"Died violently as {host_name}",
                emotion=emotion,
                intensity=random.uniform(0.7, 1.0),
                life_number=soul.incarnation_count,
                host_name=host_name,
                host_type=host_type,
            ))
            # Alignment drifts slightly negative from violent death
            soul.alignment = max(-1.0, soul.alignment - 0.05)
        else:
            # Natural death
            base_duration = random.uniform(10.0, 30.0)

        # Burial modifier
        if buried:
            base_duration *= 0.5
        elif death_type != "sacrifice":
            # Left unburied — ghost duration doubled, drifts to death location
            base_duration *= 2.0
            soul.ghost_drift_target = (soul.last_death_x, soul.last_death_y)

        soul.ghost_duration = base_duration

        self.pool.ghost_souls.append(soul.soul_id)

    # ------------------------------------------------------------------
    # Soul consumed (by undead)
    # ------------------------------------------------------------------

    def on_soul_consumed(self, soul_id: int, consumer_name: str):
        """An undead creature consumes a soul — it is destroyed permanently.

        Some echo memories transfer to the consumer.
        """
        soul = self.pool.souls.get(soul_id)
        if soul is None:
            return

        # Transfer up to 2 echo memories to the consumer (handled externally
        # if the consumer is an NPC with memories)
        transferred = soul.echo_memories[:2]

        # Permanently remove
        self.pool.remove_soul(soul_id)
        self.pool.statistical_soul_count = max(0, self.pool.statistical_soul_count - 1)

        return transferred

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_soul(self, entity) -> Optional[Soul]:
        """Get the soul inhabiting this entity, or None."""
        soul_id = getattr(entity, "soul_id", None)
        if soul_id is None:
            return None
        return self.pool.souls.get(soul_id)

    def get_ghost_souls_near(self, x: float, y: float, radius: float = 20.0) -> List[Soul]:
        """Get ghost souls near a position (for ghost-mode rendering)."""
        result = []
        r2 = radius * radius
        for sid in self.pool.ghost_souls:
            soul = self.pool.souls.get(sid)
            if soul is None or soul.state != "ghost":
                continue
            dx = soul.ghost_x - x
            dy = soul.ghost_y - y
            if dx * dx + dy * dy <= r2:
                result.append(soul)
        return result

    def get_past_life_hint(self, npc, current_day: int = 0) -> Optional[str]:
        """Check if this NPC's soul has relevant past-life memories.

        Returns hint text or None.  Only triggers occasionally (1% chance
        per check), more likely for old souls (high incarnation_count).
        Checked at most once per game-day per NPC.
        """
        name = getattr(npc, "name", "")
        if not name:
            return None

        # Rate-limit: once per game-day
        last = self._past_life_day_checked.get(name, -1)
        if last >= current_day:
            return None
        self._past_life_day_checked[name] = current_day

        soul = self.get_soul(npc)
        if soul is None or not soul.echo_memories:
            return None

        # Base 1% chance, boosted by incarnation count
        chance = 0.01 + soul.incarnation_count * 0.005
        if random.random() > chance:
            return None

        # Pick strongest memory
        best = max(soul.echo_memories, key=lambda m: m.intensity)
        hint_templates = [
            f"A sudden flash — {npc.name} mutters: 'I remember... {best.text}...'",
            f"{npc.name} gets a distant look: 'In another life, I was {best.host_name}...'",
            f"{npc.name} shivers: 'Something about this place... {best.emotion}...'",
            f"For a moment, {npc.name}'s eyes glow faintly. 'I've been here before... as {best.host_name}.'",
        ]
        return random.choice(hint_templates)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _age_souls(self, dt: float):
        """Age all tracked souls by dt."""
        for soul in self.pool.souls.values():
            soul.age += dt

    def _update_ghosts(self, dt: float, game_time: float):
        """Update ghost positions and check for ghost-to-free transitions."""
        ghosts_to_free: List[int] = []

        for sid in list(self.pool.ghost_souls):
            soul = self.pool.souls.get(sid)
            if soul is None or soul.state != "ghost":
                ghosts_to_free.append(sid)
                continue

            soul.time_as_ghost += dt

            # Drift toward target (simple, no pathfinding)
            if soul.ghost_drift_target:
                tx, ty = soul.ghost_drift_target
                dx = tx - soul.ghost_x
                dy = ty - soul.ghost_y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 0.5:
                    speed = 0.3  # slow ghost drift
                    step = min(speed * dt, dist)
                    soul.ghost_x += (dx / dist) * step
                    soul.ghost_y += (dy / dist) * step
                else:
                    # Reached target, pick a new random nearby drift
                    soul.ghost_drift_target = (
                        soul.last_death_x + random.uniform(-5, 5),
                        soul.last_death_y + random.uniform(-5, 5),
                    )
            else:
                # Random drift near death location
                soul.ghost_x += random.uniform(-0.2, 0.2) * dt
                soul.ghost_y += random.uniform(-0.2, 0.2) * dt

            # Check if ghost duration expired
            if soul.time_as_ghost >= soul.ghost_duration:
                ghosts_to_free.append(sid)

        # Transition expired ghosts to free pool
        for sid in ghosts_to_free:
            if sid in self.pool.ghost_souls:
                self.pool.ghost_souls.remove(sid)
            soul = self.pool.souls.get(sid)
            if soul and soul.state == "ghost":
                soul.state = "embodied"  # will become embodied once assigned
                self.pool.free_souls.append(sid)

    def _try_reincarnations(self, npcs: list, creatures: list, game_time: float):
        """Attempt to reincarnate free souls into soulless living entities.

        Only runs when there are free souls AND soulless entities.
        Performance: does not run every frame — only checks entities without
        soul_id, which is rare after initial assignment.
        """
        if not self.reincarnation_enabled:
            return
        if not self.pool.free_souls:
            return

        # Find soulless living entities (should be rare)
        soulless = []
        for npc in npcs:
            if npc.alive and getattr(npc, "soul_id", None) is None:
                soulless.append(npc)
        for creature in creatures:
            if creature.alive and getattr(creature, "soul_id", None) is None:
                soulless.append(creature)

        if not soulless:
            return

        # Assign up to 5 per tick to avoid spikes
        for entity in soulless[:5]:
            if not self.pool.free_souls:
                break
            self.on_birth(entity, game_time)

    def _extract_echo_memories(self, soul: Soul, entity, host_name: str, host_type: str):
        """Pull 1-2 strongest memories from the dying host into the soul's echo list."""
        memories = getattr(entity, "memories", [])
        if not memories:
            return

        # Sort by importance (descending), then take top 2
        sorted_mems = sorted(
            memories,
            key=lambda m: m.get("importance", 0) if isinstance(m, dict) else 0,
            reverse=True,
        )

        count = 0
        for mem in sorted_mems[:2]:
            if not isinstance(mem, dict):
                continue
            text = mem.get("text", "")
            if not text:
                continue
            # Derive emotion from memory type
            mtype = mem.get("type", "")
            emotion_map = {
                "grief": "sorrow", "combat": "fear", "love": "love",
                "family": "warmth", "betrayal": "anger", "discovery": "wonder",
                "trade": "satisfaction", "adventure": "excitement",
            }
            emotion = emotion_map.get(mtype, "nostalgia")
            importance = mem.get("importance", 1)
            intensity = min(1.0, importance / 5.0)

            soul.echo_memories.append(EchoMemory(
                text=text,
                emotion=emotion,
                intensity=intensity,
                life_number=soul.incarnation_count,
                host_name=host_name,
                host_type=host_type,
            ))
            count += 1

        # Cap total echo memories to 20 per soul (keep strongest)
        if len(soul.echo_memories) > 20:
            soul.echo_memories.sort(key=lambda m: m.intensity, reverse=True)
            soul.echo_memories = soul.echo_memories[:20]

    def _apply_past_life_bonus(self, soul: Soul, entity):
        """Old souls (incarnation_count > 5) may grant a past-life skill bonus."""
        # Only for NPCs with skills
        skills = getattr(entity, "npc_skills", None)
        if skills is None:
            return

        # Boost a skill that matches the soul's affinity
        affinity_skills = {
            "warrior": ["melee_combat", "defense", "athletics"],
            "scholar": ["lore", "research", "persuasion"],
            "nature": ["survival", "herbalism", "animal_handling"],
            "divine": ["healing", "religion", "medicine"],
            "arcane": ["arcana", "enchanting", "alchemy"],
            "neutral": ["perception", "stealth", "crafting"],
        }
        candidates = affinity_skills.get(soul.affinity, ["perception"])
        for skill_name in candidates:
            if skill_name in skills:
                skills[skill_name] = min(10, skills[skill_name] + 1)
                return
        # If none matched, just boost the first available skill
        if skills:
            first_key = next(iter(skills))
            skills[first_key] = min(10, skills[first_key] + 1)

    # ------------------------------------------------------------------
    # Persistence (data/souls.json)
    # ------------------------------------------------------------------

    def save(self, base_path: str = ""):
        """Save soul pool to data/souls.json."""
        path = os.path.join(base_path, self.SAVE_PATH) if base_path else self.SAVE_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = self.pool.to_dict()
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, base_path: str = ""):
        """Load soul pool from data/souls.json.  Returns True if loaded."""
        path = os.path.join(base_path, self.SAVE_PATH) if base_path else self.SAVE_PATH
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self.pool = SoulPool.from_dict(data)
            return True
        except (json.JSONDecodeError, KeyError, TypeError):
            return False
