"""
Memory decay and compaction system.

Memories fade over time based on:
- Age: older memories decay faster
- Importance: high-importance memories resist decay
- Repetition: repeated similar events get compacted into summaries
- Emotional weight: traumatic/joyful events persist longer

Memory lifecycle:
1. FRESH (< 1 game day): Full detail, no decay
2. RECENT (1-3 days): Minor details start to fade
3. FADING (3-7 days): Low-importance memories get pruned or compacted
4. DISTANT (7+ days): Only high-importance memories survive, compacted into summaries

Compaction rules:
- Multiple "Ate X" memories → "Has been eating regularly"
- Multiple "Talked to X" → "Frequently socializes with X"
- Multiple combat events → "Has seen several battles recently"
- Multiple work events → "Has been working hard at [skill]"

The LLM can optionally refine compacted memories into richer summaries.
"""

import random
import time as _time
from typing import List, Dict, Optional, Tuple


# ================================================================
# IMPORTANCE THRESHOLDS
# ================================================================

# Memories at or above this importance never decay (landmark events)
PERMANENT_IMPORTANCE = 5

# Importance boost for emotional/social memories
EMOTIONAL_TYPES = {"death", "combat", "danger", "betrayal", "love", "friendship"}

# How many game-days before each decay phase
FRESH_DAYS = 1
RECENT_DAYS = 3
FADING_DAYS = 7

# Seconds per game day (matches DAY_LENGTH in settings)
SECONDS_PER_DAY = 600.0


# ================================================================
# COMPACTION PATTERNS — groups of similar memories to merge
# ================================================================

COMPACTION_PATTERNS = {
    "eating": {
        "match_types": {"action", "survival"},
        "match_words": {"ate", "eaten", "bread", "meat", "food"},
        "summary": "Has been eating regularly to stay nourished",
        "min_count": 3,
        "result_importance": 1,
        "result_type": "routine",
    },
    "drinking": {
        "match_types": {"action", "survival"},
        "match_words": {"drank", "drink", "water", "ale", "thirst"},
        "summary": "Has been keeping hydrated",
        "min_count": 3,
        "result_importance": 1,
        "result_type": "routine",
    },
    "socializing": {
        "match_types": {"social"},
        "match_words": {"conversation", "chat", "talked", "joke", "flirt", "meal"},
        "summary_fn": "_compact_social",
        "min_count": 3,
        "result_importance": 2,
        "result_type": "social_summary",
    },
    "combat": {
        "match_types": {"combat", "alert"},
        "match_words": {"fought", "fighting", "attacked", "engaged", "battle", "threat"},
        "summary_fn": "_compact_combat",
        "min_count": 2,
        "result_importance": 3,
        "result_type": "combat_summary",
    },
    "work": {
        "match_types": {"work", "forage", "action"},
        "match_words": {"chopped", "mined", "harvested", "caught", "built", "crafted",
                       "performed", "earned", "gathered", "farmed", "fished"},
        "summary_fn": "_compact_work",
        "min_count": 3,
        "result_importance": 2,
        "result_type": "work_summary",
    },
    "training": {
        "match_types": {"training"},
        "match_words": {"trained", "practiced", "improved", "honed"},
        "summary_fn": "_compact_training",
        "min_count": 2,
        "result_importance": 2,
        "result_type": "training_summary",
    },
    "spiritual": {
        "match_types": {"spiritual"},
        "match_words": {"prayer", "prayed", "deity", "presence", "divine"},
        "summary_fn": "_compact_spiritual",
        "min_count": 2,
        "result_importance": 2,
        "result_type": "spiritual_summary",
    },
    "economy": {
        "match_types": {"economy"},
        "match_words": {"price", "supply", "demand", "trade", "market", "tax"},
        "summary": "Has been tracking market prices and trade",
        "min_count": 4,
        "result_importance": 1,
        "result_type": "routine",
    },
}


# ================================================================
# MEMORY MANAGER
# ================================================================

class MemoryManager:
    """Manages memory decay and compaction for all NPCs."""

    def __init__(self):
        self._decay_timer = 0.0
        self._decay_interval = 30.0  # process every 30 seconds
        self._compact_timer = 0.0
        self._compact_interval = 120.0  # compact every 2 minutes

    def update(self, dt: float, npcs: list, game_day: int):
        """Periodic memory maintenance for all NPCs."""
        self._decay_timer += dt
        self._compact_timer += dt

        if self._decay_timer >= self._decay_interval:
            self._decay_timer = 0.0
            self._decay_all(npcs, game_day)

        if self._compact_timer >= self._compact_interval:
            self._compact_timer = 0.0
            self._compact_all(npcs, game_day)

    def _decay_all(self, npcs: list, game_day: int):
        """Apply time-based decay to all NPC memories."""
        now = _time.time()
        for npc in npcs:
            if not npc.alive or not hasattr(npc, 'memories'):
                continue
            self._decay_npc_memories(npc, now, game_day)

    def _decay_npc_memories(self, npc, now: float, game_day: int):
        """Decay and prune memories for a single NPC."""
        if not npc.memories:
            return

        surviving = []
        for mem in npc.memories:
            age_seconds = now - mem.get("time", now)
            age_days = age_seconds / SECONDS_PER_DAY
            importance = mem.get("importance", 1)
            mem_type = mem.get("type", "")

            # Permanent memories never decay
            if importance >= PERMANENT_IMPORTANCE:
                surviving.append(mem)
                continue

            # Emotional memories get an importance boost for decay purposes
            effective_importance = importance
            if mem_type in EMOTIONAL_TYPES:
                effective_importance += 1

            # Fresh memories always survive
            if age_days < FRESH_DAYS:
                surviving.append(mem)
                continue

            # Recent memories: low-importance start to fade
            if age_days < RECENT_DAYS:
                if effective_importance >= 2:
                    surviving.append(mem)
                elif random.random() < 0.8:  # 80% chance low-importance survives
                    surviving.append(mem)
                continue

            # Fading memories: moderate importance required
            if age_days < FADING_DAYS:
                if effective_importance >= 3:
                    surviving.append(mem)
                elif effective_importance >= 2 and random.random() < 0.6:
                    surviving.append(mem)
                continue

            # Distant memories: only high-importance survives
            if effective_importance >= 3:
                surviving.append(mem)
            elif effective_importance >= 2 and random.random() < 0.3:
                surviving.append(mem)

        npc.memories = surviving

    def _compact_all(self, npcs: list, game_day: int):
        """Compact similar memories into summaries for all NPCs.
        Only processes a few NPCs per call to spread the cost.
        """
        now = _time.time()
        # Process at most 5 NPCs per call to spread the cost
        if not hasattr(self, '_compact_idx'):
            self._compact_idx = 0
        processed = 0
        alive_npcs = [n for n in npcs if n.alive and hasattr(n, 'memories')]
        if not alive_npcs:
            return
        start_idx = self._compact_idx % len(alive_npcs)
        for i in range(len(alive_npcs)):
            idx = (start_idx + i) % len(alive_npcs)
            npc = alive_npcs[idx]
            if len(npc.memories) > 25:  # only compact when really full
                self._compact_npc_memories(npc, now)
                processed += 1
                if processed >= 5:
                    break
        self._compact_idx = (start_idx + processed) % max(1, len(alive_npcs))

    def _compact_npc_memories(self, npc, now: float):
        """Find groups of similar memories and merge them into summaries."""
        for pattern_name, pattern in COMPACTION_PATTERNS.items():
            matches = []
            non_matches = []

            for mem in npc.memories:
                if self._matches_pattern(mem, pattern, now):
                    matches.append(mem)
                else:
                    non_matches.append(mem)

            if len(matches) >= pattern["min_count"]:
                # Create compacted summary
                summary = self._create_summary(npc, matches, pattern)
                # Keep the most important original + the summary
                best_original = max(matches, key=lambda m: m.get("importance", 0))
                compacted_mem = {
                    "time": now,
                    "type": pattern["result_type"],
                    "text": summary,
                    "importance": max(pattern["result_importance"],
                                     best_original.get("importance", 1)),
                    "compacted_from": len(matches),
                }
                non_matches.append(compacted_mem)

                # Keep the single most important original if it's significant
                if best_original.get("importance", 0) >= 3:
                    non_matches.append(best_original)

                npc.memories = non_matches

    def _matches_pattern(self, mem: dict, pattern: dict, now: float) -> bool:
        """Check if a memory matches a compaction pattern."""
        # Cheapest checks first
        mem_type = mem.get("type", "")
        if mem_type not in pattern["match_types"]:
            return False

        # Don't compact already-compacted memories
        if mem.get("compacted_from"):
            return False

        # Don't compact very recent memories (< 1 day)
        age = now - mem.get("time", now)
        if age < SECONDS_PER_DAY * 0.5:
            return False

        # Keyword match (only call .lower() if we get this far)
        match_words = pattern.get("match_words", set())
        if match_words:
            mem_text = mem.get("text", "").lower()
            if not any(w in mem_text for w in match_words):
                return False

        return True

    def _create_summary(self, npc, memories: list, pattern: dict) -> str:
        """Create a compacted summary from a group of memories."""
        # Use custom summary function if provided
        summary_fn_name = pattern.get("summary_fn")
        if summary_fn_name:
            fn = getattr(self, summary_fn_name, None)
            if fn:
                return fn(npc, memories)

        # Use static summary template
        return pattern.get("summary", f"Various {pattern.get('result_type', 'events')} occurred")

    # ================================================================
    # CUSTOM COMPACTION FUNCTIONS
    # ================================================================

    def _compact_social(self, npc, memories: list) -> str:
        """Compact social memories into a relationship summary."""
        names = set()
        interaction_types = set()
        for mem in memories:
            text = mem.get("text", "")
            # Extract names from social memories
            for word in text.split():
                if word[0].isupper() and word not in ("The", "A", "An", "Has", "Was", "Is"):
                    if word != npc.name and len(word) > 2:
                        names.add(word.rstrip(".,!?"))
                        break

            for itype in ("conversation", "joke", "meal", "flirt", "argue", "comfort"):
                if itype in text.lower():
                    interaction_types.add(itype)

        names_str = ", ".join(list(names)[:3])
        if names_str:
            return f"Has been socializing frequently with {names_str}"
        return "Has been socializing with various people"

    def _compact_combat(self, npc, memories: list) -> str:
        """Compact combat memories into a battle summary."""
        creatures = set()
        for mem in memories:
            text = mem.get("text", "").lower()
            for creature in ("wolf", "bear", "bandit", "skeleton", "spider", "goblin",
                           "orc", "troll", "ogre", "zombie", "gnoll"):
                if creature in text:
                    creatures.add(creature)

        if creatures:
            return f"Has fought {', '.join(creatures)} in recent days"
        return "Has been in several fights recently"

    def _compact_work(self, npc, memories: list) -> str:
        """Compact work memories into a productivity summary."""
        activities = set()
        items_gained = set()
        for mem in memories:
            text = mem.get("text", "").lower()
            if "chop" in text: activities.add("woodcutting")
            elif "mine" in text: activities.add("mining")
            elif "harvest" in text or "farm" in text: activities.add("farming")
            elif "fish" in text or "caught" in text: activities.add("fishing")
            elif "perform" in text: activities.add("performing")
            elif "craft" in text or "made" in text: activities.add("crafting")
            elif "forage" in text or "gather" in text: activities.add("foraging")
            elif "built" in text: activities.add("building")
            elif "heal" in text: activities.add("healing")

        if activities:
            return f"Has been busy with {', '.join(activities)}"
        return "Has been working hard recently"

    def _compact_training(self, npc, memories: list) -> str:
        """Compact training memories."""
        skills = set()
        for mem in memories:
            text = mem.get("text", "").lower()
            for skill in ("swordsmanship", "archery", "shield", "unarmed",
                         "stealth", "lockpicking", "performance", "religion"):
                if skill in text:
                    skills.add(skill)

        if skills:
            return f"Has been training in {', '.join(skills)}"
        return "Has been training and improving skills"

    def _compact_spiritual(self, npc, memories: list) -> str:
        """Compact spiritual memories."""
        deity = getattr(npc, 'deity', None)
        if deity:
            return f"Has been praying regularly to {deity}"
        return "Has been spending time in prayer and meditation"


# ================================================================
# LLM-ENHANCED COMPACTION (optional)
# ================================================================

def request_memory_compaction(llm, npc, memories_to_compact: list,
                              callback=None) -> Optional[str]:
    """Use the LLM to create a rich, narrative compaction of memories.

    Only called when LLM is available. Falls back to rule-based compaction.
    """
    if not llm or not llm.enabled:
        return None

    mem_texts = [m.get("text", "") for m in memories_to_compact]
    prompt = (
        f"You are {npc.name}, a {getattr(npc, 'race', 'Human')} "
        f"{getattr(npc, 'char_class', 'adventurer')}. "
        f"Summarize these memories into 1-2 sentences as if you're recalling them:\n\n"
        + "\n".join(f"- {t}" for t in mem_texts) +
        f"\n\nWrite a brief personal summary (1-2 sentences, first person)."
    )

    req_id = f"compact_{npc.name}_{_time.time():.0f}"
    llm.request(req_id, prompt, callback=callback, max_tokens=60, temperature=0.7)
    return req_id


# ================================================================
# MEMORY RETRIEVAL HELPERS
# ================================================================

def get_important_memories(npc, count: int = 5) -> List[str]:
    """Get the most important memories, blending ephemeral memories with ledger highlights."""
    result = []

    # Pull highlights from life ledger first (these are permanent facts)
    ledger = getattr(npc, 'life_ledger', None)
    if ledger:
        # Most impactful milestones
        for m in ledger.milestones[-2:]:
            result.append(m["description"])
        # Recent deaths of close bonds
        for name, info in list(ledger.deaths_witnessed.items())[-2:]:
            if info.get("relationship") in ("friend", "close friend", "child"):
                result.append(f"Lost {name} ({info['relationship']}) to {info['cause']}")

    # Fill remaining slots from ephemeral memories
    if not hasattr(npc, 'memories') or not npc.memories:
        return result[:count]

    scored = []
    now = _time.time()
    for mem in npc.memories:
        importance = mem.get("importance", 1)
        age = now - mem.get("time", now)
        age_penalty = min(5, age / SECONDS_PER_DAY)
        score = importance * 10 - age_penalty
        scored.append((score, mem))

    scored.sort(key=lambda x: -x[0])

    seen_types = set()
    seen_texts = set(result)  # avoid duplicating ledger entries
    for score, mem in scored:
        if len(result) >= count:
            break
        mem_type = mem.get("type", "unknown")
        text = mem["text"]
        if text in seen_texts:
            continue
        if mem_type not in seen_types or len(result) < count:
            result.append(text)
            seen_types.add(mem_type)
            seen_texts.add(text)

    return result[:count]


def get_memories_about(npc, subject: str, count: int = 3) -> List[str]:
    """Get memories mentioning a specific subject (person, place, creature)."""
    if not hasattr(npc, 'memories'):
        return []

    subject_lower = subject.lower()
    matches = [(m.get("importance", 0), m)
               for m in npc.memories
               if subject_lower in m.get("text", "").lower()]
    matches.sort(key=lambda x: -x[0])
    return [m["text"] for _, m in matches[:count]]


def get_memory_summary(npc) -> str:
    """Get a one-line summary of an NPC's mental state from their memories."""
    if not hasattr(npc, 'memories') or not npc.memories:
        return "No notable memories"

    total = len(npc.memories)
    types = {}
    for m in npc.memories:
        t = m.get("type", "unknown")
        types[t] = types.get(t, 0) + 1

    compacted = sum(1 for m in npc.memories if m.get("compacted_from"))
    important = sum(1 for m in npc.memories if m.get("importance", 0) >= 3)

    ledger = getattr(npc, 'life_ledger', None)
    ledger_str = ""
    if ledger:
        counts = ledger.summary_counts()
        parts = [f"{v} {k}" for k, v in counts.items() if v > 0]
        if parts:
            ledger_str = f", ledger: {', '.join(parts)}"

    top_type = max(types, key=types.get) if types else "none"
    return (f"{total} memories ({important} important, {compacted} compacted), "
            f"mostly about {top_type}{ledger_str}")


# ================================================================
# LIFE LEDGER — structured permanent records of landmark events
# ================================================================

class LifeLedger:
    """Permanent structured record of an NPC's landmark life events.

    Unlike ephemeral memories that decay, the ledger stores compact structured
    data that persists forever. This is separate from the memory stream —
    the ledger records FACTS, memories record FEELINGS.

    Categories:
    - deaths_witnessed: people this NPC saw die
    - kills: creatures/NPCs this NPC has killed
    - bonds: significant relationships formed or broken
    - milestones: becoming ruler, joining party, having children, etc.
    - crimes: crimes witnessed or committed
    - discoveries: places, secrets, or lore discovered
    """

    __slots__ = ('deaths_witnessed', 'kills', 'bonds', 'milestones',
                 'crimes', 'discoveries')

    def __init__(self):
        # {name: {"race": str, "class": str, "cause": str, "day": int,
        #         "relationship": str, "location": str}}
        self.deaths_witnessed: Dict[str, Dict] = {}

        # {target_name_or_kind: {"count": int, "last_day": int, "is_npc": bool}}
        self.kills: Dict[str, Dict] = {}

        # {name: {"type": str, "formed_day": int, "broken_day": int|None,
        #         "trust_peak": int, "notes": str}}
        self.bonds: Dict[str, Dict] = {}

        # [{"type": str, "description": str, "day": int, "location": str}]
        self.milestones: List[Dict] = []

        # [{"type": str, "description": str, "day": int, "perpetrator": str,
        #   "victim": str, "witnessed": bool}]
        self.crimes: List[Dict] = []

        # [{"type": str, "description": str, "day": int, "location": str}]
        self.discoveries: List[Dict] = []

    # ---- Recording methods ----

    def record_death(self, deceased_name: str, cause: str, day: int,
                     relationship: str = "acquaintance",
                     race: str = "", char_class: str = "",
                     location: str = ""):
        """Record witnessing someone's death."""
        self.deaths_witnessed[deceased_name] = {
            "race": race, "class": char_class, "cause": cause,
            "day": day, "relationship": relationship, "location": location,
        }

    def record_kill(self, target: str, day: int, is_npc: bool = False):
        """Record killing a creature or NPC."""
        if target in self.kills:
            self.kills[target]["count"] += 1
            self.kills[target]["last_day"] = day
        else:
            self.kills[target] = {"count": 1, "last_day": day, "is_npc": is_npc}

    def record_bond(self, name: str, bond_type: str, day: int,
                    trust: int = 0, notes: str = ""):
        """Record forming or changing a significant relationship."""
        if name in self.bonds:
            entry = self.bonds[name]
            entry["type"] = bond_type
            if trust > entry.get("trust_peak", 0):
                entry["trust_peak"] = trust
            if notes:
                entry["notes"] = notes
        else:
            self.bonds[name] = {
                "type": bond_type, "formed_day": day,
                "broken_day": None, "trust_peak": trust, "notes": notes,
            }

    def record_bond_broken(self, name: str, day: int, reason: str = ""):
        """Record a relationship ending (betrayal, death, departure)."""
        if name in self.bonds:
            self.bonds[name]["broken_day"] = day
            if reason:
                self.bonds[name]["notes"] = reason

    def record_milestone(self, milestone_type: str, description: str,
                         day: int, location: str = ""):
        """Record a major life milestone."""
        # Don't duplicate
        for m in self.milestones:
            if m["type"] == milestone_type and m["description"] == description:
                return
        self.milestones.append({
            "type": milestone_type, "description": description,
            "day": day, "location": location,
        })

    def record_crime(self, crime_type: str, description: str, day: int,
                     perpetrator: str = "", victim: str = "",
                     witnessed: bool = True):
        """Record a crime witnessed or committed."""
        self.crimes.append({
            "type": crime_type, "description": description, "day": day,
            "perpetrator": perpetrator, "victim": victim,
            "witnessed": witnessed,
        })
        # Cap crimes list
        if len(self.crimes) > 20:
            self.crimes = self.crimes[-20:]

    def record_discovery(self, discovery_type: str, description: str,
                         day: int, location: str = ""):
        """Record discovering something notable."""
        self.discoveries.append({
            "type": discovery_type, "description": description,
            "day": day, "location": location,
        })
        if len(self.discoveries) > 15:
            self.discoveries = self.discoveries[-15:]

    # ---- Query methods ----

    def get_known_dead(self) -> List[str]:
        """Get list of people this NPC knows are dead."""
        return list(self.deaths_witnessed.keys())

    def knew_deceased(self, name: str) -> bool:
        """Check if this NPC witnessed a specific person's death."""
        return name in self.deaths_witnessed

    def get_death_details(self, name: str) -> Optional[Dict]:
        """Get details about a deceased person."""
        return self.deaths_witnessed.get(name)

    def get_total_kills(self) -> int:
        """Total number of kills."""
        return sum(k["count"] for k in self.kills.values())

    def get_living_bonds(self, dead_names: set = None) -> Dict[str, Dict]:
        """Get bonds with people who are still alive."""
        if dead_names is None:
            dead_names = set(self.deaths_witnessed.keys())
        return {n: b for n, b in self.bonds.items()
                if b.get("broken_day") is None and n not in dead_names}

    def get_strongest_bonds(self, count: int = 3) -> List[tuple]:
        """Get the most significant bonds, ranked by trust peak."""
        ranked = sorted(self.bonds.items(),
                       key=lambda x: x[1].get("trust_peak", 0), reverse=True)
        return ranked[:count]

    def summary_counts(self) -> Dict[str, int]:
        """Get counts for display."""
        return {
            "deaths": len(self.deaths_witnessed),
            "kills": self.get_total_kills(),
            "bonds": len(self.bonds),
            "milestones": len(self.milestones),
            "crimes": len(self.crimes),
            "discoveries": len(self.discoveries),
        }

    # ---- Narrative generation ----

    def narrate_deaths(self, max_entries: int = 5) -> str:
        """Generate a narrative summary of deaths witnessed."""
        if not self.deaths_witnessed:
            return ""
        entries = list(self.deaths_witnessed.items())[-max_entries:]
        parts = []
        for name, info in entries:
            rel = info.get("relationship", "someone")
            cause = info.get("cause", "unknown causes")
            parts.append(f"{name} ({rel}) died from {cause}")
        return "People I've lost: " + "; ".join(parts)

    def narrate_bonds(self, max_entries: int = 5) -> str:
        """Generate a narrative summary of significant relationships."""
        if not self.bonds:
            return ""
        strongest = self.get_strongest_bonds(max_entries)
        parts = []
        for name, info in strongest:
            btype = info.get("type", "acquaintance")
            broken = " (lost)" if info.get("broken_day") is not None else ""
            parts.append(f"{name} — {btype}{broken}")
        return "Important relationships: " + "; ".join(parts)

    def narrate_milestones(self) -> str:
        """Generate a narrative summary of life milestones."""
        if not self.milestones:
            return ""
        parts = [m["description"] for m in self.milestones[-5:]]
        return "Life events: " + "; ".join(parts)

    def narrate_kills(self) -> str:
        """Generate a narrative of combat history."""
        if not self.kills:
            return ""
        # Irregular plurals
        plurals = {"wolf": "wolves", "thief": "thieves", "dwarf": "dwarves"}
        parts = []
        for target, info in sorted(self.kills.items(),
                                    key=lambda x: -x[1]["count"])[:5]:
            cnt = info["count"]
            if cnt > 1:
                plural = plurals.get(target, target + "s")
                parts.append(f"{cnt} {plural}")
            else:
                parts.append(f"a {target}")
        return "Has slain: " + ", ".join(parts)

    def narrate_full(self) -> str:
        """Full narrative of the ledger for LLM context."""
        sections = []
        d = self.narrate_deaths()
        if d: sections.append(d)
        b = self.narrate_bonds()
        if b: sections.append(b)
        m = self.narrate_milestones()
        if m: sections.append(m)
        k = self.narrate_kills()
        if k: sections.append(k)
        return ". ".join(sections) if sections else ""


def ensure_life_ledger(npc) -> LifeLedger:
    """Get or create the life ledger for an NPC."""
    if not hasattr(npc, 'life_ledger') or npc.life_ledger is None:
        npc.life_ledger = LifeLedger()
    return npc.life_ledger
