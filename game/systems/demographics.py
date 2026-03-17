"""
Demographics: ages, families, dynasties, feudal hierarchy.

NPCs have ages, belong to families, and follow a feudal structure:
  Monarch → Dukes → Lords → Knights → Guards → Commoners

Ages affect: health (old = frailer), desires (young = adventurous),
capabilities (prime = strongest), and mortality (very old = chance of death).

Families: parents, children, spouses share stronger bonds and will
defend each other. Royal families have succession.
"""

import random
import math
from typing import Dict, List, Optional, Tuple


# Age categories and their effects
AGE_CATEGORIES = {
    "child":  (5, 15,   {"hp_mult": 0.5, "speed_mult": 0.8, "str_mult": 0.5, "can_fight": False}),
    "young":  (16, 25,  {"hp_mult": 0.9, "speed_mult": 1.1, "str_mult": 0.9, "can_fight": True}),
    "prime":  (26, 45,  {"hp_mult": 1.0, "speed_mult": 1.0, "str_mult": 1.0, "can_fight": True}),
    "middle": (46, 60,  {"hp_mult": 0.9, "speed_mult": 0.9, "str_mult": 0.9, "can_fight": True}),
    "elder":  (61, 80,  {"hp_mult": 0.7, "speed_mult": 0.7, "str_mult": 0.7, "can_fight": False}),
    "ancient":(81, 120, {"hp_mult": 0.5, "speed_mult": 0.5, "str_mult": 0.5, "can_fight": False}),
}

# Race affects lifespan
RACE_LIFESPAN = {
    "Human": 80, "Half-Elf": 180, "Half-Orc": 60,
    "Elf": 700, "Dwarf": 350, "Halfling": 150,
    "Gnome": 400, "Tiefling": 100,
}

# Feudal titles
TITLES = {
    "monarch": {"tax_income": 10, "guards": 8, "servants": 4},
    "duke":    {"tax_income": 5, "guards": 4, "servants": 2},
    "lord":    {"tax_income": 3, "guards": 2, "servants": 1},
    "knight":  {"tax_income": 1, "guards": 0, "servants": 0},
    "commoner":{"tax_income": 0, "guards": 0, "servants": 0},
}


class Family:
    """A family unit with shared bonds."""
    def __init__(self, family_id: str, surname: str):
        self.id = family_id
        self.surname = surname
        self.members: List[str] = []  # NPC names
        self.head: str = ""  # family head name
        self.wealth = 0  # shared family wealth
        self.title = "commoner"
        self.home_settlement = ""

    def add_member(self, name: str):
        if name not in self.members:
            self.members.append(name)

    @property
    def size(self) -> int:
        return len(self.members)


class DemographicsSystem:
    """Manages ages, families, feudal hierarchy."""

    def __init__(self):
        self.families: Dict[str, Family] = {}
        self.npc_families: Dict[str, str] = {}  # npc_name -> family_id
        self.aging_timer = 0.0
        self.deaths_total = 0       # cumulative death counter
        self.births_total = 0       # cumulative birth counter (wired from population)
        self.on_death = None        # callback(npc, cause) set by simulation

    def initialize(self, npcs: list, structures: list):
        """Assign ages, create families, set up feudal hierarchy."""
        rng = random.Random()

        # Assign ages based on race
        for npc in npcs:
            race = getattr(npc, 'race', 'Human')
            max_age = RACE_LIFESPAN.get(race, 80)
            # Weight toward prime age
            npc.age = rng.randint(int(max_age * 0.15), int(max_age * 0.6))
            npc.max_age = max_age
            npc.age_category = self._get_age_category(npc.age, max_age)

            # Apply age effects
            cat_data = AGE_CATEGORIES.get(npc.age_category, AGE_CATEGORIES["prime"])
            effects = cat_data[2]
            if effects.get("hp_mult", 1.0) != 1.0:
                npc.max_hp = max(5, int(npc.max_hp * effects["hp_mult"]))
                npc.hp = min(npc.hp, npc.max_hp)
            npc.speed *= effects.get("speed_mult", 1.0)

        # Create families (group nearby NPCs by surname)
        surnames = [
            "Ironforge", "Brightblade", "Shadowmere", "Thornwood", "Goldleaf",
            "Stormwind", "Moonwhisper", "Ashford", "Blackthorn", "Silvervein",
            "Oakenshield", "Fireheart", "Winterborn", "Dawnwalker", "Nightshade",
            "Stonefist", "Ravencrest", "Swiftarrow", "Deepwater", "Highcastle",
            "Starweaver", "Emberfall", "Frostpeak", "Sunblade", "Darkhollow",
        ]
        rng.shuffle(surnames)

        # Group NPCs into families based on proximity
        assigned = set()
        surname_idx = 0
        for npc in npcs:
            if npc.name in assigned:
                continue

            surname = surnames[surname_idx % len(surnames)]
            surname_idx += 1
            family_id = f"family_{surname}_{surname_idx}"

            family = Family(family_id, surname)
            family.head = npc.name
            family.add_member(npc.name)
            self.npc_families[npc.name] = family_id
            assigned.add(npc.name)

            # Add nearby NPCs as family members (same settlement, 1-3 members)
            family_size = rng.randint(1, 3)
            added = 0
            for other in npcs:
                if other.name in assigned or added >= family_size:
                    continue
                if npc.dist_to(other) < 10:
                    family.add_member(other.name)
                    self.npc_families[other.name] = family_id
                    assigned.add(other.name)
                    added += 1

                    # Family members are friends
                    if other.name not in npc.friends:
                        npc.friends.append(other.name)
                    if npc.name not in other.friends:
                        other.friends.append(npc.name)
                    npc.npc_relationships[other.name] = npc.npc_relationships.get(other.name, 0) + 30
                    other.npc_relationships[npc.name] = other.npc_relationships.get(npc.name, 0) + 30

            self.families[family_id] = family

        # Assign feudal titles to NPCs at castles
        castle_npcs = []
        for s in structures:
            if s.kind == "castle":
                for npc in npcs:
                    if npc.dist_to_pos(s.x, s.y) < s.radius + 5:
                        castle_npcs.append((npc, s))
                        break

        for npc, castle in castle_npcs:
            npc.is_ruler = True
            npc.title = "monarch"
            npc.faction = castle.name
            fid = self.npc_families.get(npc.name)
            if fid and fid in self.families:
                self.families[fid].title = "monarch"
                self.families[fid].wealth = rng.randint(200, 500)

            # Assign some nearby NPCs as guards, servants, duke
            nearby = [(other, npc.dist_to(other)) for other in npcs
                      if other is not npc and other.alive and npc.dist_to(other) < 20]
            nearby.sort(key=lambda x: x[1])

            for i, (other, dist) in enumerate(nearby[:8]):
                if i == 0:
                    other.title = "duke"
                    other.faction = castle.name
                elif i < 3:
                    other.title = "knight"
                    other.faction = castle.name
                elif i < 6:
                    other.title = "guard"
                    other.faction = castle.name
                    other.current_goal = f"guard {castle.name}"
                else:
                    other.title = "servant"
                    other.faction = castle.name

            npc.add_memory("status", f"I am the ruler of {castle.name}", 5)
            npc.long_term_goals.insert(0, f"Rule and protect {castle.name}")
            npc.long_term_goals.insert(1, "Expand the kingdom's influence")

    def _get_age_category(self, age: int, max_age: int) -> str:
        """Get age category adjusted for race lifespan."""
        ratio = age / max(1, max_age)
        if ratio < 0.15:
            return "child"
        elif ratio < 0.25:
            return "young"
        elif ratio < 0.50:
            return "prime"
        elif ratio < 0.70:
            return "middle"
        elif ratio < 0.90:
            return "elder"
        return "ancient"

    def update(self, dt: float, npcs: list, day: int):
        """Periodic aging and mortality checks."""
        self.aging_timer += dt
        if self.aging_timer < 60.0:  # check every minute
            return
        self.aging_timer = 0.0

        for npc in npcs:
            if not npc.alive:
                continue

            age = getattr(npc, 'age', 30)
            max_age = getattr(npc, 'max_age', 80)

            # Natural aging — 1 year per ~5 real minutes (faster for more
            # visible demographic changes)
            npc.age = age + 0.2

            # Mortality check for elderly
            ratio = npc.age / max(1, max_age)
            if ratio > 0.80:
                death_chance = (ratio - 0.80) * 0.05  # higher chance
                if random.random() < death_chance:
                    npc.alive = False
                    npc.hp = 0
                    self.deaths_total += 1

                    # Call death callback if set (wires into population counters)
                    if self.on_death:
                        self.on_death(npc, "old age")

                    # Notify family
                    fid = self.npc_families.get(npc.name)
                    if fid and fid in self.families:
                        family = self.families[fid]
                        for member_name in family.members:
                            for other in npcs:
                                if other.name == member_name and other.alive:
                                    other.add_memory("grief", f"My family member {npc.name} has died of old age", 5)
                                    other.mood = max(-1.0, getattr(other, 'mood', 0) - 0.5)

    def get_family_info(self, npc_name: str) -> str:
        """Get family info for display."""
        fid = self.npc_families.get(npc_name)
        if not fid or fid not in self.families:
            return "No family"
        family = self.families[fid]
        title = getattr(family, 'title', 'commoner')
        return f"House {family.surname} ({title}, {family.size} members)"

    def get_npc_title(self, npc) -> str:
        """Get display title for an NPC."""
        title = getattr(npc, 'title', 'commoner')
        if title == "monarch":
            return "King" if random.random() < 0.5 else "Queen"
        return title.capitalize()

    def are_family(self, name_a: str, name_b: str) -> bool:
        """Check if two NPCs are in the same family."""
        fid_a = self.npc_families.get(name_a)
        fid_b = self.npc_families.get(name_b)
        return fid_a is not None and fid_a == fid_b
