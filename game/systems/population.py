"""
Population dynamics: birth, child aging, migration, settlement growth.

This is the foundation for civilization - without population growth and
movement, civilizations can't emerge organically.

Birth rate depends on: food abundance, housing, peace, family status.
Children grow up, choose classes, join the workforce.
NPCs migrate seeking better conditions (jobs, safety, food, social).
Settlements grow/shrink based on population.
"""

import random
import math
from typing import List, Dict, Optional, Tuple
from game.settings import *


# Quality of life factors that drive birth and migration
QOL_WEIGHTS = {
    "food_security": 0.3,    # average hunger level of population
    "safety": 0.25,          # inverse of nearby creature threat
    "housing": 0.2,          # ratio of buildings to population
    "wealth": 0.15,          # average gold per capita
    "social": 0.1,           # average social need satisfaction
}

# Child class preferences based on parent class
CHILD_CLASS_WEIGHTS = {
    "Fighter":   {"Fighter": 30, "Paladin": 10, "Barbarian": 10, "Ranger": 5},
    "Wizard":    {"Wizard": 30, "Sorcerer": 15, "Cleric": 5},
    "Cleric":    {"Cleric": 30, "Paladin": 10, "Monk": 10},
    "Rogue":     {"Rogue": 25, "Bard": 15, "Ranger": 10},
    "Ranger":    {"Ranger": 25, "Druid": 15, "Fighter": 10},
    "Paladin":   {"Paladin": 20, "Fighter": 15, "Cleric": 15},
    "Barbarian": {"Barbarian": 25, "Fighter": 15, "Ranger": 10},
    "Bard":      {"Bard": 25, "Rogue": 10, "Sorcerer": 10},
    "Druid":     {"Druid": 25, "Ranger": 15, "Cleric": 10},
    "Monk":      {"Monk": 25, "Cleric": 10, "Fighter": 10},
    "Sorcerer":  {"Sorcerer": 25, "Wizard": 15, "Warlock": 10},
    "Warlock":   {"Warlock": 20, "Sorcerer": 15, "Wizard": 10},
}

# Settlement type thresholds
SETTLEMENT_THRESHOLDS = {
    5: "hamlet",
    15: "village",
    35: "town",
    60: "city",
}


class SettlementStats:
    """Aggregate statistics for a settlement used for population decisions."""
    def __init__(self, name: str, kind: str, x: int, y: int):
        self.name = name
        self.kind = kind
        self.x = x
        self.y = y
        self.population = 0
        self.food_security = 50.0  # 0-100
        self.safety = 80.0
        self.housing_capacity = 10
        self.avg_wealth = 10.0
        self.avg_social = 50.0
        self.quality_of_life = 50.0
        self.births_today = 0
        self.deaths_today = 0

    def recalculate_qol(self):
        """Recalculate quality of life score."""
        housing_ratio = min(100, (self.housing_capacity / max(1, self.population)) * 50)
        self.quality_of_life = (
            self.food_security * QOL_WEIGHTS["food_security"] +
            self.safety * QOL_WEIGHTS["safety"] +
            housing_ratio * QOL_WEIGHTS["housing"] +
            min(100, self.avg_wealth) * QOL_WEIGHTS["wealth"] +
            self.avg_social * QOL_WEIGHTS["social"]
        )


class PopulationSystem:
    """Manages population dynamics across all settlements."""

    def __init__(self):
        self.settlements: Dict[str, SettlementStats] = {}
        self.birth_timer = 0.0
        self.migration_timer = 0.0
        self.growth_timer = 0.0
        self.population_log: List[str] = []

        # Name pools for new NPCs
        self.name_pool = [
            "Aric", "Brea", "Corwin", "Delia", "Eryn", "Finn", "Gwen",
            "Hal", "Ivy", "Jace", "Kira", "Lor", "Mira", "Nico",
            "Ora", "Penn", "Ria", "Seth", "Tara", "Ulin", "Vale",
            "Wynn", "Xara", "Yael", "Zara", "Ash", "Beck", "Cara",
            "Dex", "Elm", "Fox", "Gray", "Hope", "Ink", "Joy",
            "Kit", "Lark", "Moss", "Neve", "Oak", "Pip", "Quinn",
            "Reed", "Sky", "True", "Una", "Vex", "Wren", "Yew", "Zen",
        ]
        self.name_index = 0
        self.on_birth = None  # callback(npc, settlement_kind) called when a child is born

    def initialize(self, structures: list, npcs: list):
        """Build settlement stats from world data."""
        for s in structures:
            if s.kind in ("hamlet", "village", "town", "city", "castle"):
                stats = SettlementStats(s.name, s.kind, s.x, s.y)
                stats.housing_capacity = {"hamlet": 8, "village": 20, "town": 50,
                                          "city": 100, "castle": 30}.get(s.kind, 10)
                self.settlements[s.name] = stats

        # Count population per settlement
        for npc in npcs:
            nearest = self._nearest_settlement(npc.x, npc.y)
            if nearest:
                self.settlements[nearest].population += 1

    def update(self, dt: float, npcs: list, creatures: list, world, time_sys):
        """Periodic population updates."""
        # Update settlement stats every 30 seconds
        self.growth_timer += dt
        if self.growth_timer > 30.0:
            self.growth_timer = 0.0
            self._update_settlement_stats(npcs, creatures)

        # Birth checks every 45 seconds (was 2 minutes — too infrequent)
        self.birth_timer += dt
        if self.birth_timer > 45.0:
            self.birth_timer = 0.0
            births = self._process_births(npcs, world, time_sys.day)
            if births:
                self.population_log.extend(births)

        # Migration checks every 3 minutes
        self.migration_timer += dt
        if self.migration_timer > 180.0:
            self.migration_timer = 0.0
            migrations = self._process_migrations(npcs)
            if migrations:
                self.population_log.extend(migrations)

    def _update_settlement_stats(self, npcs: list, creatures: list):
        """Recalculate all settlement statistics."""
        # Reset counts
        for stats in self.settlements.values():
            stats.population = 0
            stats.food_security = 0
            stats.avg_wealth = 0
            stats.avg_social = 0

        # Aggregate NPC data per settlement
        settlement_npcs: Dict[str, List] = {name: [] for name in self.settlements}

        for npc in npcs:
            if not npc.alive:
                continue
            nearest = self._nearest_settlement(npc.x, npc.y)
            if nearest and nearest in settlement_npcs:
                settlement_npcs[nearest].append(npc)

        for name, stats in self.settlements.items():
            local_npcs = settlement_npcs.get(name, [])
            stats.population = len(local_npcs)

            if local_npcs:
                stats.food_security = sum(n.needs.get("hunger", 50) for n in local_npcs) / len(local_npcs)
                stats.avg_wealth = sum(getattr(n, 'npc_gold', 0) for n in local_npcs) / len(local_npcs)
                stats.avg_social = sum(n.needs.get("social", 50) for n in local_npcs) / len(local_npcs)

            # Safety: check for nearby creatures
            threat_count = sum(1 for c in creatures if c.alive and
                              math.sqrt((c.x - stats.x)**2 + (c.y - stats.y)**2) < 30)
            stats.safety = max(0, 100 - threat_count * 10)

            stats.recalculate_qol()

    def _process_births(self, npcs: list, world, day: int) -> List[str]:
        """Check for new births in settlements with good conditions."""
        messages = []

        for name, stats in self.settlements.items():
            if stats.population < 2:
                continue
            if stats.population >= stats.housing_capacity:
                continue
            if stats.quality_of_life < 30:
                continue

            # Birth probability based on QoL and population
            # Raised base rate (0.003 from 0.001) so births actually happen
            birth_chance = stats.quality_of_life * 0.003 * (stats.housing_capacity - stats.population) / stats.housing_capacity
            birth_chance = max(0.01, min(0.4, birth_chance))  # minimum 1% per check

            if random.random() > birth_chance:
                continue

            # Find a family in this settlement to have a child
            local_npcs = [n for n in npcs if n.alive and
                         math.sqrt((n.x - stats.x)**2 + (n.y - stats.y)**2) < 30]

            # Find adults of prime/young age
            parents = [n for n in local_npcs
                      if getattr(n, 'age_category', '') in ('young', 'prime')]

            if len(parents) < 2:
                continue

            parent = random.choice(parents)
            child_npc = self._create_child(parent, world, stats)
            if child_npc:
                npcs.append(child_npc)
                stats.births_today += 1
                msg = f"A child ({child_npc.name}) was born in {name}!"
                messages.append(msg)
                parent.add_memory("family", f"My child {child_npc.name} was born!", 5)
                # Soul assignment callback
                if self.on_birth:
                    self.on_birth(child_npc, stats.kind if hasattr(stats, 'kind') else "village")
                from game.systems.memory import ensure_life_ledger
                ledger = ensure_life_ledger(parent)
                ledger.record_milestone("childbirth", f"My child {child_npc.name} was born", 0, name)
                ledger.record_bond(child_npc.name, "child", 0, trust=100, notes="my child")

        return messages

    def _create_child(self, parent, world, settlement_stats) -> Optional[object]:
        """Create a new child NPC near a parent."""
        from game.core.npc import NPC
        from game.data.dnd import random_npc_class_and_race

        # Get name
        name = self._get_next_name()

        # Inherit race from parent, choose class based on parent's class
        race = getattr(parent, 'race', 'Human')
        parent_class = getattr(parent, 'char_class', 'Fighter')

        # Weighted class choice based on parent
        weights = CHILD_CLASS_WEIGHTS.get(parent_class, {"Fighter": 20, "Rogue": 15})
        classes = list(weights.keys())
        w = [weights[c] for c in classes]
        child_class = random.choices(classes, weights=w, k=1)[0]

        # Place near parent
        cx = parent.x + random.uniform(-2, 2)
        cy = parent.y + random.uniform(-2, 2)

        child = NPC(cx, cy, name, child_class,
                   char_class=child_class, race=race, level=1)
        child.home_x = parent.home_x
        child.home_y = parent.home_y
        child.age = 0
        child.age_category = "child"
        child.max_hp = max(5, child.max_hp // 2)
        child.hp = child.max_hp
        child.speed = NPC_SPEED * 0.8

        # Family bond with parent
        child.friends.append(parent.name)
        parent.friends.append(child.name)
        child.npc_relationships[parent.name] = 50
        parent.npc_relationships[child.name] = 50

        return child

    def _process_migrations(self, npcs: list) -> List[str]:
        """NPCs in poor settlements may migrate to better ones."""
        messages = []

        if len(self.settlements) < 2:
            return messages

        # Find best and worst settlements
        ranked = sorted(self.settlements.values(),
                       key=lambda s: s.quality_of_life, reverse=True)

        best = ranked[0]
        worst = ranked[-1]

        if best.quality_of_life - worst.quality_of_life < 15:
            return messages  # not enough difference to motivate migration

        # Random NPC in worst settlement considers migrating
        local_npcs = [n for n in npcs if n.alive and
                     math.sqrt((n.x - worst.x)**2 + (n.y - worst.y)**2) < 30]

        if not local_npcs:
            return messages

        migrant = random.choice(local_npcs)

        # Only unhappy NPCs migrate
        if migrant.needs.get("hunger", 50) > 40 and migrant.needs.get("social", 50) > 30:
            return messages  # content enough to stay

        # Migrate!
        migrant.home_x = float(best.x + random.randint(-5, 5))
        migrant.home_y = float(best.y + random.randint(-5, 5))
        migrant.target_x = migrant.home_x
        migrant.target_y = migrant.home_y
        migrant.current_goal = f"migrate to {best.name}"
        migrant.state = "walking"
        migrant.state_timer = 60.0
        migrant.add_memory("life", f"Moved from {worst.name} to {best.name} seeking better life", 4)

        msg = f"{migrant.name} migrated from {worst.name} to {best.name}!"
        messages.append(msg)
        return messages

    def _nearest_settlement(self, x: float, y: float) -> Optional[str]:
        """Find the nearest settlement to a position."""
        best = None
        best_dist = float('inf')
        for name, stats in self.settlements.items():
            d = math.sqrt((x - stats.x)**2 + (y - stats.y)**2)
            if d < best_dist and d < 40:  # within 40 tiles
                best_dist = d
                best = name
        return best

    def _get_next_name(self) -> str:
        name = self.name_pool[self.name_index % len(self.name_pool)]
        self.name_index += 1
        # Add suffix for uniqueness
        if self.name_index > len(self.name_pool):
            suffix = self.name_index // len(self.name_pool)
            name = f"{name}_{suffix}"
        return name

    def get_population_log(self) -> List[str]:
        msgs = list(self.population_log)
        self.population_log.clear()
        return msgs

    def get_settlement_report(self) -> str:
        """Get a text report of all settlements for display."""
        lines = []
        for name, stats in sorted(self.settlements.items(),
                                   key=lambda x: -x[1].population):
            lines.append(
                f"{name} ({stats.kind}): pop={stats.population}/{stats.housing_capacity} "
                f"QoL={stats.quality_of_life:.0f} food={stats.food_security:.0f} "
                f"safety={stats.safety:.0f}")
        return "\n".join(lines)
