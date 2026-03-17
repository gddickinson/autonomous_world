"""
Culture & Religion: beliefs, education, festivals, history.

Settlements have cultural identity. Temples serve religions.
NPCs learn through apprenticeships and reading.
Major events are recorded as history that NPCs reference.
"""

import random
from typing import Dict, List, Optional


# Religions with different values
RELIGIONS = {
    "The Light": {
        "alignment": "lawful good",
        "values": ["healing", "protection", "justice"],
        "classes": ["Cleric", "Paladin"],
        "blessing": "healing",  # what temples provide
    },
    "The Old Gods": {
        "alignment": "neutral",
        "values": ["nature", "balance", "wisdom"],
        "classes": ["Druid", "Ranger"],
        "blessing": "rest",
    },
    "The Arcane Path": {
        "alignment": "true neutral",
        "values": ["knowledge", "magic", "discovery"],
        "classes": ["Wizard", "Sorcerer"],
        "blessing": "knowledge",
    },
    "The Shadow": {
        "alignment": "chaotic neutral",
        "values": ["freedom", "cunning", "survival"],
        "classes": ["Rogue", "Warlock"],
        "blessing": "stealth",
    },
    "The Forge": {
        "alignment": "lawful neutral",
        "values": ["craft", "industry", "strength"],
        "classes": ["Fighter", "Barbarian"],
        "blessing": "strength",
    },
}


class HistoricalEvent:
    """A recorded historical event."""
    def __init__(self, day: int, description: str, importance: int = 1,
                 location: str = "", participants: List[str] = None):
        self.day = day
        self.description = description
        self.importance = importance
        self.location = location
        self.participants = participants or []


class CultureSystem:
    """Manages religion, education, festivals, and recorded history."""

    def __init__(self):
        self.settlement_religions: Dict[str, str] = {}  # settlement -> religion name
        self.history: List[HistoricalEvent] = []
        self.festival_timer = 0.0
        self.education_timer = 0.0
        self.event_log: List[str] = []

    def initialize(self, structures: list, npcs: list):
        """Assign religions to settlements with temples."""
        religion_names = list(RELIGIONS.keys())
        for s in structures:
            if s.kind in ("temple", "castle", "city"):
                religion = random.choice(religion_names)
                self.settlement_religions[s.name] = religion

        # Assign NPCs their religion based on settlement
        for npc in npcs:
            if not npc.alive:
                continue
            for s in structures:
                if s.kind in self.settlement_religions and npc.dist_to_pos(s.x, s.y) < 30:
                    npc_religion = self.settlement_religions.get(s.name)
                    if npc_religion:
                        if not hasattr(npc, 'religion'):
                            npc.religion = npc_religion
                        break

        self.record_event(1, "The world awakens. Civilizations begin their stories.", 5)

    def update(self, dt: float, npcs: list, structures: list, day: int):
        """Periodic cultural updates."""
        # Festivals every 5 minutes
        self.festival_timer += dt
        if self.festival_timer > 300:
            self.festival_timer = 0
            self._trigger_festival(npcs, structures, day)

        # Education/apprenticeship every 2 minutes
        self.education_timer += dt
        if self.education_timer > 120:
            self.education_timer = 0
            self._education_tick(npcs)

    def _trigger_festival(self, npcs: list, structures: list, day: int):
        """Random festival at a settlement."""
        candidates = [s for s in structures if s.kind in ("village", "town", "city")]
        if not candidates:
            return

        settlement = random.choice(candidates)
        religion = self.settlement_religions.get(settlement.name, "The Light")
        rel_data = RELIGIONS.get(religion, {})
        blessing = rel_data.get("blessing", "morale")

        # Apply blessing to nearby NPCs
        blessed = 0
        for npc in npcs:
            if npc.alive and npc.dist_to_pos(settlement.x, settlement.y) < 25:
                npc.needs["social"] = min(100, npc.needs.get("social", 50) + 20)
                npc.mood = min(1.0, getattr(npc, 'mood', 0) + 0.3)
                if blessing == "healing":
                    npc.hp = min(npc.max_hp, npc.hp + 10)
                elif blessing == "rest":
                    npc.needs["rest"] = min(100, npc.needs["rest"] + 15)
                blessed += 1

        if blessed > 0:
            msg = f"Festival of {religion} at {settlement.name}! {blessed} people blessed."
            self.event_log.append(msg)
            self.record_event(day, msg, 2, settlement.name)

    def _education_tick(self, npcs: list):
        """NPCs with high skills teach nearby lower-skilled NPCs."""
        from game.systems.skills import try_teach, NPC_SKILLS

        for teacher in npcs:
            if not teacher.alive:
                continue
            if not hasattr(teacher, 'npc_skills'):
                continue

            # Find a skill they're good at
            best_skill = None
            best_level = 0
            for skill, level in teacher.npc_skills.items():
                if level > best_level and level >= 3:
                    best_skill = skill
                    best_level = level

            if not best_skill:
                continue

            # Find a nearby NPC to teach (occasionally)
            if random.random() > 0.05:
                continue

            for student in npcs:
                if student is teacher or not student.alive:
                    continue
                if teacher.dist_to(student) > 5:
                    continue

                result = try_teach(teacher, student, best_skill)
                if result:
                    self.event_log.append(result)
                    break

    def record_event(self, day: int, description: str, importance: int = 1,
                     location: str = "", participants: List[str] = None):
        """Record a historical event."""
        event = HistoricalEvent(day, description, importance, location, participants or [])
        self.history.append(event)
        if len(self.history) > 200:
            # Keep only important events when history gets long
            self.history = [e for e in self.history if e.importance >= 3] + self.history[-50:]

    def get_history(self, limit: int = 20) -> List[str]:
        """Get recent history as text."""
        return [f"Day {e.day}: {e.description}" for e in self.history[-limit:]]

    def get_event_log(self) -> List[str]:
        msgs = list(self.event_log)
        self.event_log.clear()
        return msgs
