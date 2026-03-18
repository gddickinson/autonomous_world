"""
Monster Society — governance, economy, and politics for intelligent creature groups.

Intelligent monsters (intelligence >= 2) form societies with:
- Leadership hierarchies (chieftains, war bosses, pack leaders)
- Internal economies (food sharing, loot hoarding, tribute)
- Territory claims and expansion
- Raids on settlements and trade routes
- Diplomacy (trade/war/tribute) with NPC kingdoms and other monster groups
- Succession through combat, cunning, or lineage

Each species has a distinct governance model:

ORC WARBAND:
  Warchief → Captains → Warriors → Grunts → Slaves
  - Warchief chosen by combat (strongest fighter)
  - Raids generate loot, split by rank
  - War economy: plunder > production
  - Tribute from conquered settlements

GOBLIN TRIBE:
  Boss → Shamans → Scouts → Workers → Runts
  - Boss is the most cunning (not strongest)
  - Trap-making and ambush specialists
  - Scavenger economy: steal > make
  - Breed fast, expendable troops

KOBOLD WARREN:
  Overlord → Trapmakers → Miners → Diggers
  - Lawful hierarchy, very organized
  - Mining economy: gems, ore, tunnels
  - Dragon worship drives behavior
  - Elaborate trap networks

BANDIT GANG:
  Kingpin → Lieutenants → Thugs → Pickpockets
  - Leader chosen by wealth and connections
  - Protection rackets and highway robbery
  - Trade stolen goods with fences
  - Can negotiate with NPC merchants

GNOLL PACK:
  Alpha → Hunters → Hyenas (war beasts) → Scavengers
  - Demonic pack hierarchy
  - Raid-or-starve mentality
  - No diplomacy, pure aggression
  - Eat the fallen (both sides)

UNDEAD HORDE:
  Necromancer/Lich → Wights → Ghouls → Zombies → Skeletons
  - Intelligent undead command mindless ones
  - No economy (undead don't eat/trade)
  - Expand through raising the dead
  - Driven by ancient purpose
"""

import random
import math
from typing import Dict, List, Optional, Tuple


# ================================================================
# MONSTER GOVERNANCE MODELS
# ================================================================

MONSTER_GOVERNANCE = {
    "orc": {
        "name": "Orc Warband",
        "ranks": ["warchief", "captain", "warrior", "grunt", "slave"],
        "leadership": "combat",  # strongest leads
        "economy": "raid",       # plunder-based
        "diplomacy": "hostile",  # can negotiate under strength
        "can_trade": True,       # will trade with those who pay tribute
        "can_ally": True,        # can form temporary alliances
        "tribute_demand": 0.3,   # 30% of settlement income as tribute
        "raid_range": 60,        # tiles from base to raid
        "growth_rate": 0.02,     # population growth per day
        "description": "A warband ruled by the strongest orc through combat",
    },
    "goblin": {
        "name": "Goblin Tribe",
        "ranks": ["boss", "shaman", "scout", "worker", "runt"],
        "leadership": "cunning",
        "economy": "scavenge",
        "diplomacy": "sneaky",   # pretend to ally, then betray
        "can_trade": True,
        "can_ally": False,       # too treacherous
        "tribute_demand": 0.15,
        "raid_range": 40,
        "growth_rate": 0.05,     # breed fast
        "description": "A tribe ruled by the cleverest goblin through trickery",
    },
    "kobold": {
        "name": "Kobold Warren",
        "ranks": ["overlord", "trapmaker", "miner", "digger"],
        "leadership": "hierarchy",  # rigid order
        "economy": "mining",
        "diplomacy": "subservient",  # serve stronger powers
        "can_trade": True,          # trade ore and gems
        "can_ally": True,           # loyal once allied
        "tribute_demand": 0.0,     # they pay tribute, not demand it
        "raid_range": 25,
        "growth_rate": 0.04,
        "description": "An organized warren of miners serving their overlord",
    },
    "bandit": {
        "name": "Bandit Gang",
        "ranks": ["kingpin", "lieutenant", "thug", "pickpocket"],
        "leadership": "wealth",    # richest leads
        "economy": "robbery",
        "diplomacy": "mercenary",  # will work for anyone who pays
        "can_trade": True,         # fence stolen goods
        "can_ally": True,          # temporary alliances
        "tribute_demand": 0.25,
        "raid_range": 50,
        "growth_rate": 0.01,       # recruit, don't breed
        "description": "A criminal gang ruled by whoever holds the most gold",
    },
    "gnoll": {
        "name": "Gnoll Pack",
        "ranks": ["alpha", "hunter", "hyena_handler", "scavenger"],
        "leadership": "combat",
        "economy": "raid",
        "diplomacy": "none",     # gnolls don't negotiate
        "can_trade": False,
        "can_ally": False,
        "tribute_demand": 0.0,   # just attack
        "raid_range": 70,        # range far
        "growth_rate": 0.03,
        "description": "A vicious pack driven by hunger and destruction",
    },
    "undead": {
        "name": "Undead Horde",
        "ranks": ["necromancer", "wight", "ghoul", "zombie", "skeleton"],
        "leadership": "magic",   # most powerful spellcaster
        "economy": "none",       # undead don't eat or trade
        "diplomacy": "hostile",
        "can_trade": False,
        "can_ally": False,
        "tribute_demand": 0.0,
        "raid_range": 40,
        "growth_rate": 0.0,      # grow by raising the dead
        "description": "Mindless hordes commanded by an intelligent undead or necromancer",
    },
}

# Map creature kinds to governance type
CREATURE_GOVERNANCE_MAP = {
    "orc": "orc", "bugbear": "orc",
    "goblin": "goblin",
    "kobold": "kobold",
    "bandit": "bandit",
    "gnoll": "gnoll", "hyena": "gnoll",
    "skeleton": "undead", "zombie": "undead", "ghoul": "undead",
    "wight": "undead", "shadow": "undead",
}


# ================================================================
# MONSTER GROUP
# ================================================================

class MonsterGroup:
    """A society of intelligent monsters with governance and economy."""

    def __init__(self, group_id: str, kind: str, base_x: float, base_y: float):
        self.group_id = group_id
        self.kind = kind  # orc, goblin, kobold, bandit, gnoll, undead
        self.governance = MONSTER_GOVERNANCE.get(kind, MONSTER_GOVERNANCE["orc"])
        self.base_x = base_x
        self.base_y = base_y

        # Members (creature names/IDs)
        self.members: List[str] = []
        self.leader_name: str = ""
        self.leader_rank: str = self.governance["ranks"][0]

        # Economy
        self.treasury = random.randint(10, 50)  # looted gold
        self.food_stockpile = 20.0
        self.resources: Dict[str, float] = {}  # ore, gems, weapons, etc.

        # Territory
        self.territory_radius = 15.0
        self.controlled_tiles: int = 0

        # Military
        self.raid_target: Optional[str] = None  # settlement name
        self.raid_cooldown: float = 0.0
        self.war_targets: List[str] = []  # other group IDs or kingdom names
        self.victories = 0
        self.defeats = 0

        # Diplomacy
        self.relations: Dict[str, str] = {}  # entity_name -> "hostile"/"tribute"/"trade"/"allied"
        self.tribute_income = 0.0

        # Population
        self.population = 0
        self.max_population = 20

        # History
        self.events: List[str] = []

    @property
    def strength(self) -> float:
        return self.population * 1.5 + self.treasury * 0.01

    def assign_ranks(self, creatures: list):
        """Assign ranks to group members based on governance style."""
        alive_members = [c for c in creatures
                        if getattr(c, 'kind', '') in self._get_kinds() and c.alive
                        and self._in_territory(c)]

        if not alive_members:
            return

        self.members = [c.kind + "_" + str(id(c)) for c in alive_members]
        self.population = len(alive_members)

        # Choose leader
        if self.governance["leadership"] == "combat":
            leader = max(alive_members, key=lambda c: c.hp + getattr(c, 'damage', 5))
        elif self.governance["leadership"] == "cunning":
            leader = max(alive_members, key=lambda c: getattr(c, 'speed', 1.0) * 10 +
                        random.random() * 5)
        elif self.governance["leadership"] == "wealth":
            leader = max(alive_members, key=lambda c: random.random() * 10)
        elif self.governance["leadership"] == "magic":
            leader = max(alive_members, key=lambda c: c.hp * 2)
        else:
            leader = alive_members[0]

        self.leader_name = getattr(leader, 'kind', 'unknown') + " leader"

    def _get_kinds(self) -> set:
        """Get all creature kinds that belong to this governance type."""
        return {k for k, v in CREATURE_GOVERNANCE_MAP.items() if v == self.kind}

    def _in_territory(self, creature) -> bool:
        dx = creature.x - self.base_x
        dy = creature.y - self.base_y
        return dx * dx + dy * dy <= self.territory_radius ** 2

    def form_military_units(self, creatures: list) -> list:
        """Organize group members into MilitaryUnits for real combat.

        Maps monster kinds to warfare unit types and assigns formations
        based on governance style. Returns list of MilitaryUnit objects.

        Orc warbands form shield_wall infantry + archer support.
        Goblin tribes form skirmish packs.
        Undead hordes form defensive_circle with brute front line.
        Bandits form ambush groups.
        """
        from game.systems.warfare import MilitaryUnit, UNIT_STATS

        # Map creature kinds to warfare unit types
        kind_to_unit = {
            "orc": "infantry_sword", "bugbear": "infantry_sword",
            "goblin": "infantry_sword", "kobold": "infantry_sword",
            "gnoll": "infantry_sword", "bandit": "infantry_sword",
            "skeleton": "infantry_spear", "zombie": "infantry_sword",
            "ghoul": "infantry_sword", "wight": "infantry_sword",
        }

        # Governance-based formation choice
        formation_map = {
            "orc": "shield_wall",
            "goblin": "skirmish_line",
            "kobold": "defensive_circle",
            "bandit": None,  # ambush — no fixed formation
            "gnoll": None,   # feral charge
            "undead": "defensive_circle",
        }
        formation = formation_map.get(self.kind)

        # Find actual creature entities belonging to this group
        my_creatures = [c for c in creatures if c.alive and
                        getattr(c, 'kind', '').lower() in CREATURE_GOVERNANCE_MAP and
                        CREATURE_GOVERNANCE_MAP.get(c.kind.lower()) == self.kind and
                        self._in_territory(c)]

        if not my_creatures:
            return []

        # Group by creature kind
        by_kind = {}
        for c in my_creatures:
            by_kind.setdefault(c.kind.lower(), []).append(c)

        units = []
        for kind, members in by_kind.items():
            unit_type = kind_to_unit.get(kind, "infantry_sword")
            mil_unit = MilitaryUnit(
                f"{self.kind}_{kind}", unit_type, formation)

            for creature in members:
                mil_unit.add_member(creature)

            units.append(mil_unit)

        # Assign leader as commander for morale rally
        if self.leader_name and units:
            for c in my_creatures:
                if getattr(c, 'name', '') == self.leader_name or \
                   getattr(c, 'kind', '') == self.leader_name:
                    # Tag leader
                    c._is_commander = True
                    break

        self.events.append(f"Formed {len(units)} military units ({len(my_creatures)} warriors)")
        return units

    def update(self, dt: float, day: int, creatures: list,
               settlements: dict = None, other_groups: list = None):
        """Update monster society."""
        day_fraction = dt / 600.0

        # Reassign ranks periodically
        self.assign_ranks(creatures)

        if self.population == 0:
            return

        # Economy
        self._update_economy(day_fraction)

        # Raids
        self.raid_cooldown = max(0, self.raid_cooldown - day_fraction)
        if (self.raid_cooldown <= 0 and self.governance["economy"] in ("raid", "robbery")
            and settlements and self.population >= 3):
            self._plan_raid(settlements)

        # Population growth
        if self.food_stockpile > self.population * 2:
            if random.random() < self.governance["growth_rate"] * day_fraction:
                self.population = min(self.max_population, self.population + 1)

        # Inter-group diplomacy
        if other_groups and self.governance["can_ally"]:
            self._update_diplomacy(other_groups)

    def _update_economy(self, day_fraction: float):
        """Update group economy based on type."""
        economy = self.governance["economy"]

        # Food consumption
        self.food_stockpile -= self.population * 0.05 * day_fraction

        if economy == "mining":
            # Kobolds produce ore and gems
            self.resources["ore"] = self.resources.get("ore", 0) + self.population * 0.1 * day_fraction
            self.resources["gems"] = self.resources.get("gems", 0) + self.population * 0.02 * day_fraction
            self.treasury += self.population * 0.05 * day_fraction

        elif economy == "scavenge":
            # Goblins scavenge a little of everything
            self.food_stockpile += self.population * 0.03 * day_fraction
            self.treasury += self.population * 0.02 * day_fraction

        elif economy == "raid":
            # Orcs/gnolls get wealth from raids (processed separately)
            pass

        elif economy == "robbery":
            # Bandits get steady income from highway robbery
            self.treasury += self.population * 0.08 * day_fraction

        # Tribute income
        self.treasury += self.tribute_income * day_fraction

    def _plan_raid(self, settlements: dict):
        """Plan a raid on the nearest vulnerable settlement."""
        best_target = None
        best_score = -1

        for name, econ in settlements.items():
            dist = math.sqrt((econ.name == name) and 1 or
                           (self.base_x - 100) ** 2 + (self.base_y - 100) ** 2)

            # Can we reach it?
            if dist > self.governance["raid_range"]:
                continue

            # Is it worth raiding?
            value = getattr(econ, 'treasury', 0) + getattr(econ, 'population', 10) * 5
            defense = getattr(econ, 'population', 10) * 2
            score = value / max(1, defense) - dist * 0.1

            if score > best_score:
                best_score = score
                best_target = name

        if best_target and best_score > 0:
            self.raid_target = best_target
            self.raid_cooldown = 5.0  # 5 game days between raids

            # Calculate raid results
            raid_strength = self.population * 1.5
            defense = 10  # base settlement defense

            if raid_strength > defense:
                # Successful raid
                loot = random.randint(5, 20)
                food = random.randint(3, 10)
                self.treasury += loot
                self.food_stockpile += food
                self.victories += 1
                self.events.append(f"Raided {best_target}: took {loot}g and {food} food")
            else:
                # Failed raid — losses
                self.defeats += 1
                self.population = max(1, self.population - 1)
                self.events.append(f"Failed raid on {best_target}: lost warriors")

    def _update_diplomacy(self, other_groups: list):
        """Update relations with other monster groups."""
        for other in other_groups:
            if other.group_id == self.group_id:
                continue

            dist = math.sqrt((self.base_x - other.base_x) ** 2 +
                           (self.base_y - other.base_y) ** 2)

            if dist > 80:
                continue  # too far to interact

            rel = self.relations.get(other.group_id, "neutral")

            # Same species tend to ally
            if self.kind == other.kind and rel != "allied":
                if random.random() < 0.05:
                    self.relations[other.group_id] = "allied"
                    other.relations[self.group_id] = "allied"
                    self.events.append(f"Allied with {other.governance['name']} at ({other.base_x:.0f},{other.base_y:.0f})")

            # Different species: potential conflict
            elif self.kind != other.kind:
                if self.strength > other.strength * 1.5:
                    # Demand tribute from weaker group
                    if other.governance.get("tribute_demand", 0) == 0:
                        self.relations[other.group_id] = "tribute"
                        self.tribute_income += other.treasury * 0.1

                elif dist < 30:
                    # Territorial conflict
                    if random.random() < 0.02:
                        self.relations[other.group_id] = "hostile"
                        self.war_targets.append(other.group_id)
                        self.events.append(f"War with {other.governance['name']}")

    def can_trade_with_npcs(self) -> bool:
        return self.governance.get("can_trade", False)

    def get_trade_goods(self) -> Dict[str, float]:
        """What this group can sell to NPC merchants."""
        goods = {}
        if self.kind == "kobold":
            goods["ore"] = self.resources.get("ore", 0) * 0.5
            goods["gems"] = self.resources.get("gems", 0) * 0.5
        elif self.kind == "bandit":
            goods["stolen_goods"] = self.treasury * 0.3
        elif self.kind == "orc":
            goods["weapons"] = self.population * 0.5
            goods["armor"] = self.population * 0.3
        return goods

    def get_report(self) -> str:
        gov = self.governance
        return (f"{gov['name']} at ({self.base_x:.0f},{self.base_y:.0f}): "
                f"pop={self.population}, treasury={self.treasury:.0f}g, "
                f"food={self.food_stockpile:.0f}, W/L={self.victories}/{self.defeats}")


# ================================================================
# MONSTER SOCIETY MANAGER
# ================================================================

class MonsterSocietyManager:
    """Manages all monster groups and their interactions."""

    def __init__(self):
        self.groups: List[MonsterGroup] = []
        self._update_timer = 0.0
        self._next_id = 1

    def initialize(self, creatures: list, world):
        """Detect and form monster groups from existing creature clusters."""
        # Find clusters of intelligent creatures
        intelligent = [c for c in creatures if c.alive and
                      CREATURE_GOVERNANCE_MAP.get(getattr(c, 'kind', ''), None)]

        # Cluster by proximity and type
        used = set()
        for creature in intelligent:
            if id(creature) in used:
                continue

            kind = creature.kind
            gov_type = CREATURE_GOVERNANCE_MAP.get(kind)
            if not gov_type:
                continue

            # Find nearby creatures of compatible type
            cluster = [creature]
            used.add(id(creature))
            compatible_kinds = {k for k, v in CREATURE_GOVERNANCE_MAP.items() if v == gov_type}

            for other in intelligent:
                if id(other) in used or other.kind not in compatible_kinds:
                    continue
                dist = math.sqrt((creature.x - other.x) ** 2 + (creature.y - other.y) ** 2)
                if dist < 20:
                    cluster.append(other)
                    used.add(id(other))

            if len(cluster) >= 2:  # need at least 2 for a society
                group_id = f"group_{self._next_id}"
                self._next_id += 1

                # Center of the cluster
                cx = sum(c.x for c in cluster) / len(cluster)
                cy = sum(c.y for c in cluster) / len(cluster)

                group = MonsterGroup(group_id, gov_type, cx, cy)
                group.assign_ranks(cluster)
                self.groups.append(group)

    def update(self, dt: float, day: int, creatures: list,
               settlements: dict = None):
        """Update all monster societies."""
        self._update_timer += dt
        if self._update_timer < 30.0:  # every 30 seconds
            return
        self._update_timer = 0.0

        for group in self.groups:
            group.update(30.0, day, creatures, settlements, self.groups)

        # Remove empty groups
        self.groups = [g for g in self.groups if g.population > 0]

    def get_group_at(self, x: float, y: float) -> Optional[MonsterGroup]:
        """Find a monster group controlling territory at a position."""
        for group in self.groups:
            dist = math.sqrt((x - group.base_x) ** 2 + (y - group.base_y) ** 2)
            if dist < group.territory_radius:
                return group
        return None

    def get_groups_near(self, x: float, y: float, radius: float = 50) -> List[MonsterGroup]:
        """Find monster groups near a position."""
        result = []
        for group in self.groups:
            dist = math.sqrt((x - group.base_x) ** 2 + (y - group.base_y) ** 2)
            if dist < radius:
                result.append(group)
        return result

    def get_report(self) -> str:
        if not self.groups:
            return "No organized monster groups"
        lines = [f"Monster Societies ({len(self.groups)}):"]
        for g in self.groups:
            lines.append(f"  {g.get_report()}")
        return "\n".join(lines)

    def get_event_log(self) -> List[str]:
        events = []
        for g in self.groups:
            for e in g.events:
                events.append(f"[{g.governance['name']}] {e}")
            g.events.clear()
        return events
