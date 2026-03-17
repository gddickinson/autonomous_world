"""
Universal Domestication & Mount System.

ANY creature can theoretically carry ANY other creature — it's a matter of:
- Size compatibility (rider must be smaller than mount)
- Weight capacity (mount's strength determines carry limit)
- Willingness (intelligent willing mounts vs broken/trained mounts)
- Domestication status (wild vs tame vs trained)

Categories:
  WILD:         Untouched by civilization. Will flee or attack riders.
  TAMED:        Accepts handling but not riding. Won't attack handler.
  BROKEN:       Accepts a rider (reluctantly). May buck. Needs maintenance.
  TRAINED:      Reliable mount. Responds to commands. Combat-capable.
  WILLING:      Intelligent being choosing to carry another (no breaking needed).
  DOMESTICATED: Raised from birth among other species. Fully integrated.

Size classes determine who can ride whom:
  Tiny → can ride Small, Medium creatures
  Small → can ride Medium, Large creatures
  Medium → can ride Large, Huge creatures
  Large → can ride Huge, Gargantuan creatures
  Huge → can ride Gargantuan creatures only

Special cases:
  - A slave is technically a "domesticated human" (willing or broken)
  - A cat could carry a fairy (tiny rider on small mount)
  - Giants can carry medium creatures in their hands
  - Multiple small riders can share a large mount
"""

import random
import math
from typing import Optional, Tuple


# ================================================================
# SIZE CLASSES
# ================================================================

SIZE_ORDER = ["tiny", "small", "medium", "large", "huge", "gargantuan"]

# Size → approximate weight (lbs) and carry capacity (lbs)
SIZE_STATS = {
    "tiny":        {"weight": 5,     "carry": 10,    "max_riders": 0},
    "small":       {"weight": 40,    "carry": 80,    "max_riders": 1},
    "medium":      {"weight": 150,   "carry": 300,   "max_riders": 1},
    "large":       {"weight": 500,   "carry": 1000,  "max_riders": 2},
    "huge":        {"weight": 2000,  "carry": 4000,  "max_riders": 4},
    "gargantuan":  {"weight": 8000,  "carry": 16000, "max_riders": 8},
}

# What creature kinds have what sizes
CREATURE_SIZE = {
    # Tiny
    "rabbit": "tiny", "chicken": "tiny", "rat": "tiny", "fish_school": "tiny",
    "frog": "tiny", "fish": "tiny", "bat": "tiny", "squirrel": "tiny",
    "crow": "tiny", "cat": "tiny",
    # Small
    "fox": "small", "pheasant": "small", "goblin": "small", "kobold": "small",
    "spider": "small", "snake": "small", "viper": "small", "hawk": "small",
    "owl": "small", "dog": "small", "turtle": "small",
    # Medium
    "wolf": "medium", "deer": "medium", "boar": "medium", "sheep": "medium",
    "goat": "medium", "pig": "medium", "gnoll": "medium", "orc": "medium",
    "skeleton": "medium", "zombie": "medium", "bandit": "medium",
    "bugbear": "medium", "ghoul": "medium", "wight": "medium",
    "werewolf": "medium", "harpy": "medium", "eagle": "medium",
    # Large
    "horse": "large", "cow": "large", "elk": "large", "bear": "large",
    "dire_wolf": "large", "wild_boar": "large", "ogre": "large",
    "owlbear": "large", "manticore": "large", "ankheg": "large",
    "war_horse": "large", "donkey": "large", "mule": "large",
    "camel": "large", "mountain_lion": "large", "centaur": "large",
    "giant_spider": "large", "giant_scorpion": "large", "crocodile": "large",
    "unicorn": "large", "basilisk": "large",
    # Huge
    "troll": "huge", "hill_giant": "huge", "minotaur": "huge",
    "giant_crab": "huge", "griffin": "huge", "wyvern": "huge",
    "phoenix": "huge",
    # Gargantuan
    "young_dragon": "gargantuan",
}

# NPC sizes (based on race)
NPC_RACE_SIZE = {
    "Human": "medium", "Elf": "medium", "Half-Elf": "medium",
    "Dwarf": "medium", "Half-Orc": "medium", "Tiefling": "medium",
    "Halfling": "small", "Gnome": "small",
}


# Mount-specific carry capacity (lbs) — more granular than size class
# This is how much RIDER + GEAR the mount can carry while being ridden
# (separate from draft pull strength which is for vehicles)
MOUNT_CARRY_CAPACITY = {
    "horse":      250,   # average horse carries ~250 lbs rider + gear
    "war_horse":  300,   # bred for armoured riders
    "donkey":     120,   # small, can't carry heavy riders
    "mule":       180,   # sturdy but not huge
    "camel":      220,   # good endurance, decent capacity
    "elk":        200,   # large but not bred for riders
    "dire_wolf":  180,   # large wolf, medium rider only
    "bear":       350,   # strong but hard to ride
    "cow":        200,   # not really a mount but technically...
    "wolf":       80,    # small rider only (child/halfling)
    "boar":       100,   # war pig for small riders
    "owlbear":    300,   # large and strong
    "troll":      400,   # huge creature
    "hill_giant": 600,   # can carry multiple medium riders
    "minotaur":   350,   # large and muscular
    "young_dragon": 800, # can carry heavily armoured riders
    "ogre":       350,   # large humanoid
    "giant_crab":  250,  # flat back, can carry things
    "wyvern":     300,   # flying mount
    "manticore":  250,   # flying mount
}

# Armour weight (lbs) — what common armour types weigh
ARMOR_WEIGHT = {
    "none": 0,
    "Leather Armor": 15,
    "Studded Leather": 20,
    "Chain Shirt": 25,
    "Scale Mail": 35,
    "Chain Mail": 40,
    "Iron Armor": 45,
    "Plate Armor": 65,
    "Shield": 8,
}

# Weight per gold coin (lbs per coin) — gold is HEAVY
GOLD_WEIGHT_PER_COIN = 0.02  # 50 coins per lb


def calc_rider_weight(entity) -> float:
    """Calculate total weight of a rider including body, armour, inventory, and gold.

    Returns weight in lbs.
    """
    from game.systems.domestication import get_creature_size, SIZE_STATS

    # Base body weight — use entity's body_weight if available, else estimate from size
    body_weight = getattr(entity, 'body_weight', None)
    if body_weight is None:
        size = get_creature_size(entity)
        body_weight = SIZE_STATS.get(size, SIZE_STATS["medium"])["weight"]

    # Armour weight
    armor = getattr(entity, 'equipped_armor', None)
    armor_weight = 0
    if armor:
        armor_name = getattr(armor, 'name', '')
        armor_weight = ARMOR_WEIGHT.get(armor_name, 20)

    # Inventory weight (rough: 5 lbs per item)
    inv = getattr(entity, 'inventory', getattr(entity, 'npc_inventory', []))
    inv_weight = len(inv) * 5.0

    # Gold weight
    gold = getattr(entity, 'gold', getattr(entity, 'npc_gold', 0))
    gold_weight = gold * GOLD_WEIGHT_PER_COIN

    # Weapon weight
    weapon = getattr(entity, 'equipped_weapon', None)
    weapon_weight = 5 if weapon else 0

    return body_weight + armor_weight + inv_weight + gold_weight + weapon_weight


def get_mount_carry_capacity(mount_entity) -> float:
    """Get how much weight (lbs) a mount can carry while being ridden."""
    kind = getattr(mount_entity, 'kind', getattr(mount_entity, 'mount_type', ''))
    # Check specific mount capacity
    if kind in MOUNT_CARRY_CAPACITY:
        base = MOUNT_CARRY_CAPACITY[kind]
    else:
        # Fall back to size-based estimate (1/3 of general carry)
        size = get_creature_size(mount_entity)
        base = SIZE_STATS.get(size, SIZE_STATS["medium"])["carry"] // 3

    # Strength bonus for intelligent mounts
    strength = getattr(mount_entity, 'ability_scores', {}).get('strength', 10)
    if isinstance(strength, (int, float)) and strength > 14:
        base *= (1.0 + (strength - 14) * 0.05)

    return base


def get_creature_size(entity) -> str:
    """Get the size class of any entity (creature, NPC, or player)."""
    # Check explicit size attribute
    if hasattr(entity, 'creature_size'):
        return entity.creature_size

    # Creature kinds
    kind = getattr(entity, 'kind', None)
    if kind and kind in CREATURE_SIZE:
        return CREATURE_SIZE[kind]

    # NPC race
    race = getattr(entity, 'race', None)
    if race and race in NPC_RACE_SIZE:
        return NPC_RACE_SIZE[race]

    return "medium"  # default


def can_ride(rider, mount_entity) -> Tuple[bool, str]:
    """Check if rider can ride mount_entity based on size AND weight.

    Checks:
    1. Size compatibility (rider must be smaller)
    2. Weight limit (rider + armor + inventory + gold vs mount capacity)

    Returns (can_ride, reason).
    """
    rider_size = get_creature_size(rider)
    mount_size = get_creature_size(mount_entity)

    rider_idx = SIZE_ORDER.index(rider_size) if rider_size in SIZE_ORDER else 2
    mount_idx = SIZE_ORDER.index(mount_size) if mount_size in SIZE_ORDER else 2

    # Rider must be at least 1 size smaller, or same with willing intelligence
    if rider_idx > mount_idx:
        return False, f"Too big to ride a {mount_size} creature."
    if rider_idx == mount_idx:
        intelligence = getattr(mount_entity, 'intelligence', 1)
        if intelligence < 3:
            return False, f"Same-size mount requires an intelligent willing carrier."

    # Weight check — rider's total weight vs mount's carry capacity
    rider_weight = calc_rider_weight(rider)
    mount_capacity = get_mount_carry_capacity(mount_entity)

    if rider_weight > mount_capacity:
        excess = rider_weight - mount_capacity
        return False, (f"Too heavy! Rider weighs {rider_weight:.0f} lbs "
                       f"but {getattr(mount_entity, 'kind', 'mount')} "
                       f"can only carry {mount_capacity:.0f} lbs. "
                       f"Remove {excess:.0f} lbs of gear/gold.")

    if rider_weight > mount_capacity * 0.8:
        return True, (f"Heavy load ({rider_weight:.0f}/{mount_capacity:.0f} lbs). "
                      f"Mount will tire faster.")

    return True, f"OK ({rider_weight:.0f}/{mount_capacity:.0f} lbs)."


# ================================================================
# DOMESTICATION STATUS
# ================================================================

class DomesticationState:
    """Tracks the domestication level of a creature."""

    WILD = "wild"
    TAMED = "tamed"        # won't attack handler, accepts petting
    BROKEN = "broken"      # accepts rider, may buck occasionally
    TRAINED = "trained"    # reliable mount, responds to commands
    WILLING = "willing"    # intelligent being choosing to serve
    DOMESTICATED = "domesticated"  # raised tame from birth

    def __init__(self):
        self.status = self.WILD
        self.trust = 0           # 0-100, how much the creature trusts its handler
        self.handler_name = ""   # who tamed/trained it
        self.break_progress = 0.0  # 0-1 for breaking process
        self.training_level = 0  # 0-10, combat/command responsiveness
        self.buck_chance = 0.0   # chance to throw rider each tick (broken mounts)

    @property
    def is_rideable(self) -> bool:
        """Can this creature be ridden?"""
        return self.status in (self.BROKEN, self.TRAINED, self.WILLING, self.DOMESTICATED)

    @property
    def is_tame(self) -> bool:
        """Is this creature non-hostile to its handler?"""
        return self.status != self.WILD

    def attempt_tame(self, handler_charisma: int, handler_animal_handling: int,
                      creature_cr: float) -> Tuple[bool, str]:
        """Attempt to tame a wild creature. Charisma + animal handling vs CR.

        Taming doesn't make it rideable — just non-hostile and handleable.
        """
        if self.status != self.WILD:
            return False, "Already tamed."

        dc = 10 + int(creature_cr * 3)
        roll = random.randint(1, 20) + (handler_charisma - 10) // 2 + handler_animal_handling
        if roll >= dc:
            self.status = self.TAMED
            self.trust = 20
            self.handler_name = ""  # set by caller
            return True, f"Tamed! (rolled {roll} vs DC {dc})"
        else:
            # Failed — creature may become hostile
            return False, f"Failed to tame (rolled {roll} vs DC {dc}). It's agitated!"

    def attempt_break(self, rider_strength: int, rider_animal_handling: int,
                       creature_cr: float, dt_hours: float = 1.0) -> Tuple[bool, str]:
        """Attempt to break a tamed creature for riding.

        Breaking takes multiple sessions. Stronger creatures resist more.
        """
        if self.status == self.WILD:
            return False, "Must tame first."
        if self.is_rideable:
            return False, "Already broken/trained."

        dc = 8 + int(creature_cr * 2)
        skill = (rider_strength - 10) // 2 + rider_animal_handling
        progress_per_session = max(0.05, (skill - dc + 10) * 0.05)
        self.break_progress += progress_per_session * dt_hours

        if self.break_progress >= 1.0:
            self.status = self.BROKEN
            self.trust = 40
            self.buck_chance = max(0.01, 0.15 - rider_animal_handling * 0.01)
            return True, "Broken! The creature accepts a rider (reluctantly)."
        else:
            return False, f"Breaking in progress ({self.break_progress*100:.0f}%)"

    def train(self, trainer_animal_handling: int, dt_hours: float = 1.0) -> str:
        """Train a broken mount for better obedience and combat capability."""
        if self.status not in (self.BROKEN, self.TRAINED):
            return "Must break the mount first."

        gain = (trainer_animal_handling * 0.1 + 0.2) * dt_hours
        self.training_level = min(10, self.training_level + gain)
        self.trust = min(100, self.trust + gain * 5)
        self.buck_chance = max(0.0, self.buck_chance - gain * 0.01)

        if self.training_level >= 5 and self.status == self.BROKEN:
            self.status = self.TRAINED
            return "Mount is now fully trained! Responds to commands."

        return f"Training: level {self.training_level:.1f}/10, trust {self.trust:.0f}/100"

    def check_buck(self) -> bool:
        """Check if a broken mount bucks its rider this tick."""
        if self.status == self.BROKEN and random.random() < self.buck_chance:
            return True
        return False

    def on_handler_death(self):
        """Handler died — mount may go wild or stay tame based on trust."""
        if self.trust < 30:
            self.status = self.WILD
            self.trust = 0
        elif self.trust < 60:
            self.status = self.TAMED
        # High trust mounts stay tame

    def get_speed_modifier(self) -> float:
        """How domestication affects mount speed."""
        mods = {
            self.WILD: 1.0,
            self.TAMED: 0.8,
            self.BROKEN: 0.9,
            self.TRAINED: 1.0,
            self.WILLING: 1.0,
            self.DOMESTICATED: 1.0,
        }
        return mods.get(self.status, 0.8)


# ================================================================
# DOMESTICATED ROLES — what tame creatures do besides being mounts
# ================================================================

# Roles a domesticated creature can fill
DOMESTIC_ROLES = {
    "mount":       {"requires_broken": True,  "description": "Carries riders"},
    "pack_animal": {"requires_broken": False, "description": "Carries goods"},
    "plough":      {"requires_broken": True,  "description": "Ploughs farm fields"},
    "guard":       {"requires_broken": False, "description": "Guards property, alerts to danger"},
    "herder":      {"requires_broken": False, "description": "Herds other animals"},
    "hunter":      {"requires_broken": True,  "description": "Hunts prey on command"},
    "pest_control":{"requires_broken": False, "description": "Catches vermin"},
    "companion":   {"requires_broken": False, "description": "Pet, provides comfort"},
    "food_source": {"requires_broken": False, "description": "Provides milk, eggs, wool"},
    "livestock":   {"requires_broken": False, "description": "Raised for meat"},
    "cart_puller": {"requires_broken": True,  "description": "Pulls carts and wagons"},
    "war_beast":   {"requires_broken": True,  "description": "Fights alongside handlers"},
    "messenger":   {"requires_broken": True,  "description": "Carries messages between locations"},
    "falcon":      {"requires_broken": True,  "description": "Hunts small game from the air"},
}

# What roles each creature kind is suited for
CREATURE_DOMESTIC_ROLES = {
    # Farm animals
    "horse":      ["mount", "plough", "cart_puller", "pack_animal"],
    "war_horse":  ["mount", "war_beast", "cart_puller"],
    "donkey":     ["pack_animal", "cart_puller", "plough"],
    "mule":       ["pack_animal", "cart_puller", "plough"],
    "camel":      ["mount", "pack_animal", "cart_puller"],
    "cow":        ["food_source", "plough", "livestock"],
    "pig":        ["livestock", "food_source"],
    "sheep":      ["food_source", "livestock"],  # wool + meat
    "goat":       ["food_source", "livestock"],   # milk + meat
    "chicken":    ["food_source"],                 # eggs
    # Working animals
    "wolf":       ["guard", "hunter", "war_beast"],  # domesticated = dog
    "dire_wolf":  ["mount", "guard", "war_beast"],
    "dog":        ["guard", "herder", "hunter", "companion"],
    "fox":        ["pest_control", "companion"],
    # Exotic
    "bear":       ["guard", "war_beast"],  # circus/war bear
    "elk":        ["mount", "pack_animal"],
    "boar":       ["guard", "war_beast"],  # war pig
    "wild_boar":  ["war_beast"],
    "hawk":       ["falcon", "messenger"],
    "pheasant":   ["food_source"],
    "rabbit":     ["food_source", "companion"],
    # Monsters (when domesticated)
    "owlbear":    ["guard", "war_beast"],
    "wyvern":     ["mount", "war_beast", "messenger"],
    "giant_crab": ["guard"],
    "spider":     ["guard", "pest_control"],  # giant spider guard
    # Humanoid (controversial but mechanically consistent)
    "orc":        ["guard", "war_beast"],     # orc thrall
    "goblin":     ["pest_control", "messenger"],  # goblin servant
    "kobold":     ["pack_animal", "pest_control"],  # kobold slave-worker
    "skeleton":   ["guard", "pack_animal"],   # animated servant
    "zombie":     ["plough", "pack_animal"],  # mindless labor
}

# What products each food_source creature produces per day
CREATURE_PRODUCTS = {
    "cow":     [("Milk", 1.0), ("Leather", 0.0)],  # leather only on slaughter
    "sheep":   [("Wool", 0.5)],
    "goat":    [("Milk", 0.5)],
    "chicken": [("Eggs", 1.0)],
    "pig":     [],  # meat only on slaughter
    "rabbit":  [],
    "pheasant":[("Eggs", 0.3)],
}

# Slaughter yields
SLAUGHTER_YIELD = {
    "cow":     [("Raw Meat", 8), ("Leather", 3)],
    "pig":     [("Raw Meat", 5)],
    "sheep":   [("Raw Meat", 4), ("Wool", 2)],
    "goat":    [("Raw Meat", 3)],
    "chicken": [("Raw Meat", 1)],
    "rabbit":  [("Raw Meat", 1)],
    "deer":    [("Raw Meat", 5), ("Leather", 2)],
    "elk":     [("Raw Meat", 7), ("Leather", 3)],
    "boar":    [("Raw Meat", 4)],
    "pheasant":[("Raw Meat", 1)],
    "horse":   [("Raw Meat", 6), ("Leather", 4)],  # horse meat is edible
}


class DomesticCreature:
    """Extended state for a domesticated creature with a job role.

    This wraps around a Creature or NPC and adds domestic behavior:
    - Role assignment (guard, plough, food_source, etc.)
    - Work output tracking (milk per day, fields ploughed, etc.)
    - Behavior modification (doesn't flee from handler, stays near home)
    - Product generation for food sources
    """

    def __init__(self, creature, role: str = "companion"):
        self.creature = creature
        self.role = role
        self.owner_name = ""
        self.home_x = getattr(creature, 'home_x', creature.x)
        self.home_y = getattr(creature, 'home_y', creature.y)
        self.work_output = 0.0  # accumulated work units
        self.days_worked = 0
        self.products_today: dict = {}  # item_name → count generated today

    def update(self, dt_days: float):
        """Daily update — generate products, track work."""
        kind = getattr(self.creature, 'kind', '')

        if self.role == "food_source":
            products = CREATURE_PRODUCTS.get(kind, [])
            for item_name, rate in products:
                produced = rate * dt_days
                self.products_today[item_name] = (
                    self.products_today.get(item_name, 0.0) + produced)

        elif self.role == "guard":
            self.work_output += dt_days

        elif self.role in ("plough", "cart_puller", "pack_animal"):
            self.work_output += dt_days * 0.5

        self.days_worked += dt_days

    def collect_products(self) -> dict:
        """Collect accumulated products. Returns {item_name: count} and resets."""
        collected = {}
        for name, amount in self.products_today.items():
            whole = int(amount)
            if whole > 0:
                collected[name] = whole
                self.products_today[name] = amount - whole
        return collected

    def get_behavior_override(self) -> dict:
        """Get AI behavior overrides for this domesticated creature.

        Returns dict of behavior modifications that the creature AI should apply.
        """
        overrides = {
            "flee_from_handler": False,  # never flee from owner
            "attack_handler": False,     # never attack owner
            "stay_near_home": True,      # stay near assigned home
            "leash_range": 10.0,         # shorter leash than wild
        }

        if self.role == "guard":
            overrides["aggro_strangers"] = True  # bark at/attack intruders
            overrides["patrol_home"] = True
            overrides["leash_range"] = 15.0

        elif self.role in ("herder", "hunter"):
            overrides["leash_range"] = 30.0  # longer range for working
            overrides["follow_handler"] = True

        elif self.role == "companion":
            overrides["follow_handler"] = True
            overrides["leash_range"] = 5.0  # stay close

        elif self.role in ("livestock", "food_source"):
            overrides["passive"] = True  # never attack
            overrides["leash_range"] = 8.0
            overrides["graze"] = True  # eat grass/hay automatically

        elif self.role in ("plough", "cart_puller"):
            overrides["follow_handler"] = True
            overrides["passive"] = True

        return overrides

    def slaughter(self) -> list:
        """Kill the creature for meat/materials. Returns list of (item_name, count)."""
        kind = getattr(self.creature, 'kind', '')
        yields = SLAUGHTER_YIELD.get(kind, [("Raw Meat", 1)])
        self.creature.alive = False
        self.creature.hp = 0
        return yields

    def get_status(self) -> str:
        kind = getattr(self.creature, 'kind', '')
        name = getattr(self.creature, 'name', kind)
        hp = getattr(self.creature, 'hp', 0)
        max_hp = getattr(self.creature, 'max_hp', 1)
        return (f"{name} ({kind}) — role: {self.role}, "
                f"HP: {hp}/{max_hp}, "
                f"worked: {self.days_worked:.1f} days")
