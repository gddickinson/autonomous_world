"""
Hauling & Draft Animal System — vehicles, cargo transport, and draft animals.

Vehicles are pulled by one or more draft animals. The system handles:
- Vehicle types (cart, wagon, chariot, sled, war chariot, siege wagon)
- Hitching animals to vehicles (harness/yoke required)
- Cargo capacity and weight calculations
- Movement speed based on animal strength, vehicle weight, terrain, road quality
- NPC skills: animal_handling (harness), driving (control), carpentry (build/repair)
- Economic integration: trade caravans, supply chains, construction hauling

Vehicle creation requires materials + carpentry skill.
Draft animals require breaking + training via domestication system.
Multiple animals can be hitched to one vehicle for heavier loads or faster speed.
"""

import math
import random
from typing import Dict, List, Optional, Tuple


# ================================================================
# VEHICLE TYPES
# ================================================================

VEHICLE_TYPES = {
    "handcart": {
        "cargo_capacity": 10,    # item slots (or weight units)
        "weight_empty": 30,      # lbs
        "max_weight": 200,       # lbs of cargo
        "speed_mult": 0.7,       # base speed multiplier
        "draft_animals": 0,      # can be pushed by person
        "min_animals": 0,
        "max_animals": 1,        # optionally pulled by one animal
        "build_materials": [("Wood", 4), ("Nails", 2)],
        "build_skill": 2,        # carpentry level needed
        "build_time_hours": 4,
        "cost": 15,
        "terrain_penalty": {"road": 0.9, "grass": 1.2, "forest": 2.0,
                           "mountain": 999, "swamp": 3.0, "sand": 1.8},
        "description": "A small hand-pushed cart for light loads",
    },
    "cart": {
        "cargo_capacity": 30,
        "weight_empty": 100,
        "max_weight": 600,
        "speed_mult": 0.8,
        "draft_animals": 1,
        "min_animals": 1,
        "max_animals": 2,
        "build_materials": [("Wood", 8), ("Nails", 4), ("Iron Ingot", 1)],
        "build_skill": 3,
        "build_time_hours": 8,
        "cost": 40,
        "terrain_penalty": {"road": 0.8, "grass": 1.3, "forest": 2.5,
                           "mountain": 999, "swamp": 999, "sand": 2.0},
        "description": "A two-wheeled cart pulled by one or two animals",
    },
    "wagon": {
        "cargo_capacity": 60,
        "weight_empty": 300,
        "max_weight": 1500,
        "speed_mult": 0.7,
        "draft_animals": 2,
        "min_animals": 2,
        "max_animals": 4,
        "build_materials": [("Wood", 15), ("Nails", 8), ("Iron Ingot", 3), ("Leather", 2)],
        "build_skill": 5,
        "build_time_hours": 16,
        "cost": 120,
        "terrain_penalty": {"road": 0.7, "grass": 1.5, "forest": 999,
                           "mountain": 999, "swamp": 999, "sand": 2.5},
        "description": "A four-wheeled wagon for heavy cargo",
    },
    "war_chariot": {
        "cargo_capacity": 5,
        "weight_empty": 150,
        "max_weight": 400,
        "speed_mult": 1.2,      # fast!
        "draft_animals": 2,
        "min_animals": 2,
        "max_animals": 2,
        "build_materials": [("Wood", 10), ("Iron Ingot", 4), ("Leather", 3)],
        "build_skill": 6,
        "build_time_hours": 20,
        "cost": 200,
        "terrain_penalty": {"road": 0.7, "grass": 1.0, "forest": 999,
                           "mountain": 999, "swamp": 999, "sand": 1.5},
        "armor_bonus": 2,        # AC bonus for rider
        "charge_bonus": 1.5,     # damage multiplier on charge
        "description": "A fast two-horse war chariot",
    },
    "sled": {
        "cargo_capacity": 40,
        "weight_empty": 80,
        "max_weight": 800,
        "speed_mult": 0.6,
        "draft_animals": 2,
        "min_animals": 1,
        "max_animals": 6,       # dog sled with multiple dogs
        "build_materials": [("Wood", 6), ("Leather", 2)],
        "build_skill": 3,
        "build_time_hours": 6,
        "cost": 30,
        "terrain_penalty": {"road": 1.5, "grass": 1.5, "snow": 0.5,  # fast on snow!
                           "mountain": 2.0, "forest": 2.0, "sand": 999},
        "description": "A sled — fast on snow and ice",
    },
    "siege_wagon": {
        "cargo_capacity": 10,
        "weight_empty": 500,
        "max_weight": 2000,
        "speed_mult": 0.3,      # very slow
        "draft_animals": 4,
        "min_animals": 2,
        "max_animals": 6,
        "build_materials": [("Wood", 20), ("Iron Ingot", 8), ("Rope", 4)],
        "build_skill": 7,
        "build_time_hours": 30,
        "cost": 300,
        "terrain_penalty": {"road": 0.8, "grass": 2.0, "forest": 999,
                           "mountain": 999, "swamp": 999, "sand": 999},
        "description": "Heavy wagon for transporting siege engines",
    },
    "supply_wagon": {
        "cargo_capacity": 80,
        "weight_empty": 250,
        "max_weight": 2000,
        "speed_mult": 0.6,
        "draft_animals": 2,
        "min_animals": 2,
        "max_animals": 4,
        "build_materials": [("Wood", 12), ("Nails", 6), ("Iron Ingot", 2), ("Canvas", 2)],
        "build_skill": 4,
        "build_time_hours": 14,
        "cost": 90,
        "terrain_penalty": {"road": 0.7, "grass": 1.3, "forest": 3.0,
                           "mountain": 999, "swamp": 999, "sand": 2.0},
        "description": "Army supply wagon with canvas cover",
    },
}

# What animals are good draft animals and their pull strength
DRAFT_ANIMAL_STATS = {
    "horse":      {"pull_strength": 300, "speed_mult": 1.0, "endurance": 1.0},
    "war_horse":  {"pull_strength": 350, "speed_mult": 0.9, "endurance": 1.2},
    "donkey":     {"pull_strength": 200, "speed_mult": 0.7, "endurance": 1.5},
    "mule":       {"pull_strength": 250, "speed_mult": 0.8, "endurance": 1.3},
    "camel":      {"pull_strength": 280, "speed_mult": 0.7, "endurance": 2.0},
    "cow":        {"pull_strength": 350, "speed_mult": 0.5, "endurance": 1.0},
    "elk":        {"pull_strength": 250, "speed_mult": 0.9, "endurance": 0.8},
    "dire_wolf":  {"pull_strength": 200, "speed_mult": 1.2, "endurance": 0.7},
    "bear":       {"pull_strength": 400, "speed_mult": 0.6, "endurance": 0.8},
    "ogre":       {"pull_strength": 500, "speed_mult": 0.5, "endurance": 0.6},
    "troll":      {"pull_strength": 450, "speed_mult": 0.5, "endurance": 0.7},
    "hill_giant": {"pull_strength": 800, "speed_mult": 0.6, "endurance": 1.0},
    # Elephants would be here if we had them
}


# ================================================================
# VEHICLE CLASS
# ================================================================

class Vehicle:
    """A vehicle that can be pulled by draft animals to transport cargo."""

    def __init__(self, vehicle_type: str, name: str = ""):
        if vehicle_type not in VEHICLE_TYPES:
            vehicle_type = "cart"
        data = VEHICLE_TYPES[vehicle_type]

        self.vehicle_type = vehicle_type
        self.name = name or f"{vehicle_type.replace('_', ' ').title()}"
        self.cargo_capacity = data["cargo_capacity"]
        self.weight_empty = data["weight_empty"]
        self.max_weight = data["max_weight"]
        self.speed_mult = data["speed_mult"]
        self.min_animals = data["min_animals"]
        self.max_animals = data["max_animals"]
        self.terrain_penalty = data["terrain_penalty"]

        self.cargo: List[Dict] = []  # [{name, count, weight}]
        self.cargo_weight = 0
        self.draft_animals: List = []  # creature/mount references
        self.hp = 50              # vehicle durability
        self.max_hp = 50
        self.driver_name = ""     # NPC/player controlling
        self.x = 0.0
        self.y = 0.0

    @property
    def total_weight(self) -> float:
        return self.weight_empty + self.cargo_weight

    @property
    def is_hitched(self) -> bool:
        return len(self.draft_animals) >= self.min_animals

    @property
    def overloaded(self) -> bool:
        return self.cargo_weight > self.max_weight

    def hitch_animal(self, animal) -> str:
        """Hitch a draft animal to this vehicle. Returns message."""
        if len(self.draft_animals) >= self.max_animals:
            return f"Maximum {self.max_animals} animals already hitched."

        kind = getattr(animal, 'kind', getattr(animal, 'mount_type', 'unknown'))
        if kind not in DRAFT_ANIMAL_STATS:
            return f"{kind} cannot pull a vehicle."

        # Check domestication
        dom = getattr(animal, 'domestication', None)
        if dom and not dom.is_rideable:
            return f"{kind} is not broken/trained for draft work."

        self.draft_animals.append(animal)
        return f"Hitched {kind} to {self.name} ({len(self.draft_animals)}/{self.max_animals})"

    def unhitch_animal(self, index: int = -1):
        """Remove a draft animal. Returns the animal or None."""
        if not self.draft_animals:
            return None
        return self.draft_animals.pop(index)

    def load_cargo(self, item_name: str, count: int, weight_per: float = 5.0) -> str:
        """Load cargo onto the vehicle."""
        total_w = count * weight_per
        if self.cargo_weight + total_w > self.max_weight:
            can_fit = int((self.max_weight - self.cargo_weight) / weight_per)
            if can_fit <= 0:
                return "Vehicle is full!"
            count = can_fit
            total_w = count * weight_per

        self.cargo.append({"name": item_name, "count": count, "weight": total_w})
        self.cargo_weight += total_w
        return f"Loaded {count}x {item_name} ({total_w:.0f} lbs). Cargo: {self.cargo_weight:.0f}/{self.max_weight} lbs"

    def unload_cargo(self, item_name: str, count: int = 999) -> int:
        """Unload cargo. Returns count actually unloaded."""
        unloaded = 0
        remaining = []
        for item in self.cargo:
            if item["name"] == item_name and unloaded < count:
                take = min(item["count"], count - unloaded)
                unloaded += take
                self.cargo_weight -= (take / item["count"]) * item["weight"]
                item["count"] -= take
                if item["count"] > 0:
                    item["weight"] -= (take / (take + item["count"])) * item["weight"]
                    remaining.append(item)
            else:
                remaining.append(item)
        self.cargo = remaining
        return unloaded

    def get_speed(self, terrain: str = "road") -> float:
        """Calculate movement speed based on animals, load, and terrain."""
        if not self.is_hitched and self.min_animals > 0:
            return 0.0  # can't move without draft animals

        # Base speed from vehicle
        speed = self.speed_mult

        # Animal contribution
        total_pull = 0
        total_animal_speed = 0
        for animal in self.draft_animals:
            kind = getattr(animal, 'kind', getattr(animal, 'mount_type', 'horse'))
            stats = DRAFT_ANIMAL_STATS.get(kind, DRAFT_ANIMAL_STATS["horse"])
            total_pull += stats["pull_strength"]
            total_animal_speed += stats["speed_mult"]

        if self.draft_animals:
            avg_animal_speed = total_animal_speed / len(self.draft_animals)
            speed *= avg_animal_speed

        # Overweight penalty
        if self.total_weight > 0 and total_pull > 0:
            load_ratio = self.total_weight / total_pull
            if load_ratio > 1.0:
                speed *= max(0.2, 1.0 / load_ratio)  # heavier = slower

        # Terrain penalty
        t_mult = self.terrain_penalty.get(terrain, 1.5)
        if t_mult >= 999:
            return 0.0  # impassable terrain for this vehicle
        speed *= (1.0 / t_mult)

        # Extra animals = slightly faster (diminishing returns)
        if len(self.draft_animals) > self.min_animals:
            extra = len(self.draft_animals) - self.min_animals
            speed *= (1.0 + extra * 0.15)

        return max(0.1, speed)

    def take_damage(self, amount: int) -> str:
        """Damage the vehicle. At 0 HP it breaks."""
        self.hp = max(0, self.hp - amount)
        if self.hp <= 0:
            return f"{self.name} has been destroyed!"
        return f"{self.name} takes {amount} damage ({self.hp}/{self.max_hp} HP)"

    def repair(self, amount: int = 10):
        """Repair the vehicle."""
        self.hp = min(self.max_hp, self.hp + amount)

    def get_status(self) -> str:
        animals = ", ".join(getattr(a, 'kind', getattr(a, 'mount_type', '?'))
                           for a in self.draft_animals)
        return (f"{self.name} ({self.vehicle_type}) | "
                f"HP:{self.hp}/{self.max_hp} | "
                f"Cargo:{self.cargo_weight:.0f}/{self.max_weight} lbs | "
                f"Animals: [{animals}] ({len(self.draft_animals)}/{self.max_animals}) | "
                f"{'HITCHED' if self.is_hitched else 'UNHITCHED'}")


# ================================================================
# VEHICLE BUILDER
# ================================================================

def build_vehicle(vehicle_type: str, builder_carpentry: int,
                   builder_inventory: list,
                   builder_gold: int = 0) -> Tuple[Optional[Vehicle], str]:
    """Build a vehicle from materials. Returns (vehicle, message).

    Args:
        vehicle_type: Type of vehicle to build
        builder_carpentry: Builder's carpentry skill level
        builder_inventory: Builder's inventory (items consumed)
        builder_gold: Alternative — buy from a workshop
    """
    data = VEHICLE_TYPES.get(vehicle_type)
    if not data:
        return None, f"Unknown vehicle type: {vehicle_type}"

    # Check skill
    if builder_carpentry < data["build_skill"]:
        return None, f"Need carpentry {data['build_skill']} (have {builder_carpentry})"

    # Check materials
    for item_name, count in data["build_materials"]:
        total = sum(getattr(i, 'count', 1) for i in builder_inventory
                   if getattr(i, 'name', str(i)) == item_name)
        if total < count:
            return None, f"Need {count}x {item_name} (have {total})"

    # Consume materials
    for item_name, count in data["build_materials"]:
        remaining = count
        for item in list(builder_inventory):
            if getattr(item, 'name', '') == item_name and remaining > 0:
                if hasattr(item, 'count') and item.count > remaining:
                    item.count -= remaining
                    remaining = 0
                else:
                    remaining -= getattr(item, 'count', 1)
                    builder_inventory.remove(item)

    vehicle = Vehicle(vehicle_type)
    return vehicle, f"Built {vehicle.name}! (took {data['build_time_hours']}h)"
