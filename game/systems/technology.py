"""
Technology & Research: tech tree, scholar research, tech spread, eras.

Settlements progress through technological eras.
Scholars at libraries/temples research new technologies.
Technologies spread between connected settlements via trade.
Each tech unlocks new crafting recipes or capabilities.
"""

import random
from typing import Dict, List, Set, Optional


# Technology tree
TECHNOLOGIES = {
    # Stone Age (starting)
    "fire":           {"era": 0, "prereqs": [], "unlocks": ["cooking"], "research_cost": 0},
    "stone_tools":    {"era": 0, "prereqs": [], "unlocks": ["mining"], "research_cost": 0},
    "farming":        {"era": 0, "prereqs": [], "unlocks": ["agriculture"], "research_cost": 0},

    # Bronze Age
    "bronze_working": {"era": 1, "prereqs": ["stone_tools"], "unlocks": ["bronze_weapons", "bronze_armor"],
                       "research_cost": 20},
    "pottery":        {"era": 1, "prereqs": ["fire"], "unlocks": ["storage", "water_flask"],
                       "research_cost": 15},
    "writing":        {"era": 1, "prereqs": ["farming"], "unlocks": ["literacy", "record_keeping"],
                       "research_cost": 25},
    "animal_husbandry":{"era": 1, "prereqs": ["farming"], "unlocks": ["dairy", "leather_working"],
                       "research_cost": 20},
    "herbalism":      {"era": 1, "prereqs": ["farming"], "unlocks": ["potions", "medicine"],
                       "research_cost": 15},

    # Iron Age
    "iron_working":   {"era": 2, "prereqs": ["bronze_working"], "unlocks": ["iron_weapons", "iron_armor"],
                       "research_cost": 40},
    "masonry":        {"era": 2, "prereqs": ["stone_tools"], "unlocks": ["stone_buildings", "fortifications"],
                       "research_cost": 30},
    "alchemy":        {"era": 2, "prereqs": ["herbalism", "writing"], "unlocks": ["advanced_potions", "elixirs"],
                       "research_cost": 50},
    "trade_routes":   {"era": 2, "prereqs": ["writing", "animal_husbandry"], "unlocks": ["caravans", "markets"],
                       "research_cost": 35},
    "mathematics":    {"era": 2, "prereqs": ["writing"], "unlocks": ["architecture", "engineering"],
                       "research_cost": 40},

    # Steel Age
    "steel_working":  {"era": 3, "prereqs": ["iron_working"], "unlocks": ["steel_weapons", "plate_armor"],
                       "research_cost": 80},
    "architecture":   {"era": 3, "prereqs": ["masonry", "mathematics"], "unlocks": ["castles", "cathedrals"],
                       "research_cost": 60},
    "enchanting":     {"era": 3, "prereqs": ["alchemy", "mathematics"], "unlocks": ["magic_items", "scrolls"],
                       "research_cost": 100},
    "navigation":     {"era": 3, "prereqs": ["trade_routes", "mathematics"], "unlocks": ["exploration", "ships"],
                       "research_cost": 70},
    "jewel_cutting":  {"era": 3, "prereqs": ["iron_working"], "unlocks": ["gems", "jewelry"],
                       "research_cost": 50},
}

ERA_NAMES = {0: "Stone Age", 1: "Bronze Age", 2: "Iron Age", 3: "Steel Age"}


class TechSystem:
    """Manages technology research and progression per settlement."""

    def __init__(self):
        # Each settlement has its own tech tree progress
        self.settlement_techs: Dict[str, Set[str]] = {}
        self.research_progress: Dict[str, Dict[str, float]] = {}  # settlement -> {tech -> progress}
        self.update_timer = 0.0
        self.event_log: List[str] = []

    def initialize(self, structures: list):
        """All settlements start with Stone Age technologies."""
        for s in structures:
            if s.kind in ("hamlet", "village", "town", "city", "castle"):
                self.settlement_techs[s.name] = {"fire", "stone_tools", "farming"}
                self.research_progress[s.name] = {}

                # Towns and cities start more advanced
                if s.kind in ("town", "city"):
                    for tech in ["bronze_working", "pottery", "writing", "animal_husbandry", "herbalism"]:
                        self.settlement_techs[s.name].add(tech)
                if s.kind == "city":
                    for tech in ["iron_working", "masonry", "trade_routes"]:
                        self.settlement_techs[s.name].add(tech)
                if s.kind == "castle":
                    for tech in ["bronze_working", "iron_working", "masonry", "writing"]:
                        self.settlement_techs[s.name].add(tech)

    def update(self, dt: float, npcs: list, structures: list, day: int):
        """Scholars research technologies, techs spread via trade."""
        self.update_timer += dt
        if self.update_timer < 60.0:
            return
        self.update_timer = 0.0

        # Research at settlements with scholars
        for s in structures:
            if s.name not in self.settlement_techs:
                continue

            known = self.settlement_techs[s.name]

            # Count scholars nearby
            scholars = 0
            for npc in npcs:
                if not npc.alive:
                    continue
                if npc.dist_to_pos(s.x, s.y) > 25:
                    continue
                char_class = getattr(npc, 'char_class', '')
                if char_class in ('Wizard', 'Cleric', 'Druid') or getattr(npc, 'literate', False):
                    scholars += 1

            if scholars == 0:
                continue

            # Find researchable techs
            for tech_name, tech_data in TECHNOLOGIES.items():
                if tech_name in known:
                    continue
                # Check prerequisites
                if all(p in known for p in tech_data["prereqs"]):
                    # Research!
                    if s.name not in self.research_progress:
                        self.research_progress[s.name] = {}
                    progress = self.research_progress[s.name].get(tech_name, 0)
                    progress += scholars * random.uniform(1, 3)

                    if progress >= tech_data["research_cost"]:
                        known.add(tech_name)
                        self.research_progress[s.name].pop(tech_name, None)
                        era = ERA_NAMES.get(tech_data["era"], "Unknown")
                        msg = f"{s.name} discovered {tech_name}! ({era})"
                        self.event_log.append(msg)
                    else:
                        self.research_progress[s.name][tech_name] = progress
                    break  # one research per settlement per tick

        # Tech spread: connected settlements share knowledge (slow)
        if random.random() < 0.1:
            settlement_names = list(self.settlement_techs.keys())
            if len(settlement_names) >= 2:
                s1, s2 = random.sample(settlement_names, 2)
                techs1 = self.settlement_techs[s1]
                techs2 = self.settlement_techs[s2]
                # Share one tech that one has and the other doesn't
                diff = techs1 - techs2
                if diff:
                    shared = random.choice(list(diff))
                    tech_data = TECHNOLOGIES.get(shared, {})
                    if all(p in techs2 for p in tech_data.get("prereqs", [])):
                        techs2.add(shared)
                        self.event_log.append(f"{s2} learned {shared} from {s1} via trade")

    def get_era(self, settlement_name: str) -> str:
        """Get the technological era of a settlement."""
        techs = self.settlement_techs.get(settlement_name, set())
        max_era = 0
        for tech_name in techs:
            era = TECHNOLOGIES.get(tech_name, {}).get("era", 0)
            max_era = max(max_era, era)
        return ERA_NAMES.get(max_era, "Stone Age")

    def get_tech_report(self) -> str:
        lines = []
        for settlement, techs in sorted(self.settlement_techs.items()):
            era = self.get_era(settlement)
            lines.append(f"{settlement} ({era}): {len(techs)} technologies")
        return "\n".join(lines)

    def get_event_log(self) -> List[str]:
        msgs = list(self.event_log)
        self.event_log.clear()
        return msgs
