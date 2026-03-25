"""Pet / Companion Taming System.

Allows the player to tame wild creatures as companions. Pets follow the
player, assist in combat, and grant passive bonuses.

Tameable kinds: dog, cat, wolf, hawk, horse, bear.
Taming uses a D20 + WIS modifier roll vs a creature-specific DC.
Max 2 active pets. Pets die permanently at 0 HP.
"""

import math
import random
from typing import Dict, List, Optional, Tuple

from game.settings import CREATURE_CHASE_RANGE


# ------------------------------------------------------------------
# Data tables
# ------------------------------------------------------------------

TAMEABLE_CREATURES: Dict[str, dict] = {
    "dog": {
        "dc": 8,
        "food": "Bread",
        "bonus_type": "detection",
        "bonus_desc": "+10% detection range",
        "base_hp": 15,
        "attack_damage": 3,
        "fail_action": "flee",
    },
    "cat": {
        "dc": 10,
        "food": "Fish",
        "bonus_type": "luck",
        "bonus_desc": "+5% luck on loot rolls",
        "base_hp": 10,
        "attack_damage": 2,
        "fail_action": "flee",
    },
    "wolf": {
        "dc": 14,
        "food": "Cooked Meat",
        "bonus_type": "combat",
        "bonus_desc": "Attacks for 5 damage",
        "base_hp": 25,
        "attack_damage": 5,
        "fail_action": "attack",
    },
    "hawk": {
        "dc": 12,
        "food": "Fish",
        "bonus_type": "vision",
        "bonus_desc": "Reveals fog in 5-tile radius ahead",
        "base_hp": 8,
        "attack_damage": 2,
        "fail_action": "flee",
    },
    "horse": {
        "dc": 10,
        "food": "Bread",
        "bonus_type": "speed",
        "bonus_desc": "+50% movement speed (mount)",
        "base_hp": 30,
        "attack_damage": 4,
        "fail_action": "flee",
    },
    "bear": {
        "dc": 18,
        "food": "Cooked Meat",
        "bonus_type": "tank",
        "bonus_desc": "50 HP tank, attacks for 10 damage",
        "base_hp": 50,
        "attack_damage": 10,
        "fail_action": "attack",
    },
}

MAX_PETS = 2
FOLLOW_DISTANCE_MIN = 2.0
FOLLOW_DISTANCE_MAX = 3.0
PET_ATTACK_RANGE = 1.8
PET_ATTACK_COOLDOWN = 1.5


# ------------------------------------------------------------------
# Pet class
# ------------------------------------------------------------------

class Pet:
    """A tamed companion creature."""

    def __init__(self, kind: str, source_creature=None):
        data = TAMEABLE_CREATURES[kind]
        self.kind = kind
        self.name = kind.capitalize()
        self.hp = data["base_hp"]
        self.max_hp = data["base_hp"]
        self.attack_damage = data["attack_damage"]
        self.bonus_type = data["bonus_type"]
        self.bonus_desc = data["bonus_desc"]
        self.alive = True
        self.following = True  # True = follow, False = stay
        self.x = 0.0
        self.y = 0.0
        self.facing = (0.0, 1.0)
        self.attack_timer = 0.0
        # Copy position from source creature if provided
        if source_creature is not None:
            self.x = source_creature.x
            self.y = source_creature.y
            self.hp = min(source_creature.hp, self.max_hp)

    def take_damage(self, amount: int) -> int:
        actual = max(0, amount)
        self.hp = max(0, self.hp - actual)
        if self.hp <= 0:
            self.alive = False
        return actual

    def heal(self, amount: int):
        self.hp = min(self.max_hp, self.hp + amount)

    def dist_to(self, other) -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx * dx + dy * dy)

    def dist_to_pos(self, tx: float, ty: float) -> float:
        dx = self.x - tx
        dy = self.y - ty
        return math.sqrt(dx * dx + dy * dy)


# ------------------------------------------------------------------
# Pet Manager  (lives on the player object as player.pet_manager)
# ------------------------------------------------------------------

class PetManager:
    """Manages the player's active pets."""

    def __init__(self):
        self.pets: List[Pet] = []
        self.messages: List[str] = []  # UI feedback messages

    # -- Queries ---------------------------------------------------

    @property
    def count(self) -> int:
        return len(self.pets)

    def has_bonus(self, bonus_type: str) -> bool:
        return any(p.alive and p.bonus_type == bonus_type for p in self.pets)

    def get_detection_bonus(self) -> float:
        """Extra detection range multiplier from dog."""
        if self.has_bonus("detection"):
            return 1.10
        return 1.0

    def get_luck_bonus(self) -> float:
        """Extra loot luck multiplier from cat."""
        if self.has_bonus("luck"):
            return 1.05
        return 1.0

    def get_speed_bonus(self) -> float:
        """Movement speed multiplier from horse mount."""
        if self.has_bonus("speed"):
            return 1.50
        return 1.0

    def get_vision_radius_bonus(self) -> int:
        """Extra fog-of-war reveal tiles from hawk."""
        if self.has_bonus("vision"):
            return 5
        return 0

    # -- Actions ---------------------------------------------------

    def _push_msg(self, text: str):
        self.messages.append(text)
        # Keep last 5 messages
        if len(self.messages) > 5:
            self.messages.pop(0)

    def attempt_tame(self, player, creature) -> str:
        """Try to tame *creature*. Returns a result message string."""
        kind = creature.kind
        if kind not in TAMEABLE_CREATURES:
            return f"{kind.capitalize()} cannot be tamed."

        if self.count >= MAX_PETS:
            return f"You already have {MAX_PETS} pets. Release one first."

        data = TAMEABLE_CREATURES[kind]
        food_name = data["food"]

        # Check food in inventory
        if player.count_item(food_name) < 1:
            return f"You need {food_name} to tame a {kind}."

        # Consume the food
        player.remove_item(food_name, 1)

        # D20 + WIS modifier vs DC
        from game.data.dnd import ability_modifier
        wis = player.ability_scores.get("wisdom", 10)
        wis_mod = ability_modifier(wis)
        roll = random.randint(1, 20)
        total = roll + wis_mod
        dc = data["dc"]

        if total >= dc:
            # Success — tame the creature
            pet = Pet(kind, source_creature=creature)
            self.pets.append(pet)
            creature.alive = False  # remove from world creature list
            msg = (f"Rolled {roll}+{wis_mod}={total} vs DC {dc}. "
                   f"Success! {kind.capitalize()} is now your pet.")
            self._push_msg(msg)
            return msg
        else:
            # Failure
            fail = data["fail_action"]
            if fail == "attack":
                creature.state = "chasing"
                creature.target = player
                msg = (f"Rolled {roll}+{wis_mod}={total} vs DC {dc}. "
                       f"Failed! The {kind} attacks you!")
            else:
                creature.state = "fleeing"
                creature.state_timer = 5.0
                msg = (f"Rolled {roll}+{wis_mod}={total} vs DC {dc}. "
                       f"Failed! The {kind} flees.")
            self._push_msg(msg)
            return msg

    def release_pet(self, index: int) -> str:
        """Release a pet back into the wild."""
        if index < 0 or index >= len(self.pets):
            return "Invalid pet index."
        pet = self.pets.pop(index)
        msg = f"{pet.name} has been released into the wild."
        self._push_msg(msg)
        return msg

    def toggle_follow(self, index: int = -1) -> str:
        """Toggle follow/stay for a specific pet or all pets."""
        targets = self.pets if index < 0 else (
            [self.pets[index]] if 0 <= index < len(self.pets) else []
        )
        results = []
        for pet in targets:
            if not pet.alive:
                continue
            pet.following = not pet.following
            state = "following" if pet.following else "staying"
            results.append(f"{pet.name} is now {state}.")
        msg = " ".join(results) if results else "No pets to command."
        self._push_msg(msg)
        return msg

    def rename_pet(self, index: int, new_name: str) -> str:
        if index < 0 or index >= len(self.pets):
            return "Invalid pet index."
        old = self.pets[index].name
        self.pets[index].name = new_name
        msg = f"{old} is now called {new_name}."
        self._push_msg(msg)
        return msg

    # -- Per-frame update ------------------------------------------

    def update(self, dt: float, player, world, creatures: list):
        """Move pets, handle combat, remove dead pets."""
        dead_indices = []
        for i, pet in enumerate(self.pets):
            if not pet.alive:
                dead_indices.append(i)
                continue
            _update_pet(pet, dt, player, world, creatures)
        # Remove dead pets (iterate in reverse)
        for i in reversed(dead_indices):
            dead_pet = self.pets.pop(i)
            self._push_msg(f"{dead_pet.name} has died!")


# ------------------------------------------------------------------
# Per-pet AI update (free function to keep PetManager small)
# ------------------------------------------------------------------

def _update_pet(pet: Pet, dt: float, player, world, creatures: list):
    """Move a single pet: follow player or attack hostiles."""
    pet.attack_timer = max(0.0, pet.attack_timer - dt)

    dist_to_player = pet.dist_to(player)

    # --- Combat: attack player's current combat target ----------------
    combat_target = _find_combat_target(pet, player, creatures)
    if combat_target is not None and pet.attack_timer <= 0:
        dist_to_target = pet.dist_to(combat_target)
        if dist_to_target < PET_ATTACK_RANGE:
            combat_target.take_damage(pet.attack_damage)
            pet.attack_timer = PET_ATTACK_COOLDOWN
            # Face the target
            dx = combat_target.x - pet.x
            dy = combat_target.y - pet.y
            d = max(0.01, math.sqrt(dx * dx + dy * dy))
            pet.facing = (dx / d, dy / d)
            return
        # Move toward target
        _move_pet_toward(pet, combat_target.x, combat_target.y, dt, world,
                         speed=3.0)
        return

    # --- Following / staying ----------------------------------------
    if not pet.following:
        return  # stay put

    if dist_to_player > FOLLOW_DISTANCE_MAX:
        # Move toward player
        _move_pet_toward(pet, player.x, player.y, dt, world, speed=3.5)
    elif dist_to_player > 20.0:
        # Teleport if too far (e.g. player fast-traveled)
        pet.x = player.x + random.uniform(-2, 2)
        pet.y = player.y + random.uniform(-2, 2)


def _find_combat_target(pet: Pet, player, creatures: list):
    """Return the nearest hostile creature attacking the player, or None."""
    best = None
    best_dist = 999.0
    for c in creatures:
        if not c.alive:
            continue
        if c.state in ("chasing", "attacking") and c.target is player:
            d = pet.dist_to(c)
            if d < CREATURE_CHASE_RANGE and d < best_dist:
                best = c
                best_dist = d
    return best


def _move_pet_toward(pet: Pet, tx: float, ty: float, dt: float, world,
                     speed: float = 3.0):
    """Move pet toward (tx, ty) with simple wall-sliding."""
    dx = tx - pet.x
    dy = ty - pet.y
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 0.1:
        return
    nx = dx / dist
    ny = dy / dist
    pet.facing = (nx, ny)
    move_x = nx * speed * dt
    move_y = ny * speed * dt

    new_x = pet.x + move_x
    new_y = pet.y + move_y

    # Simple walkability check (pets can walk where the player can)
    ix = int(new_x + 0.3 * (1 if move_x > 0 else -1))
    iy = int(new_y + 0.3 * (1 if move_y > 0 else -1))

    if world.is_walkable(ix, int(pet.y)):
        pet.x = new_x
    if world.is_walkable(int(pet.x), iy):
        pet.y = new_y


# ------------------------------------------------------------------
# Convenience: find nearest tameable creature to the player
# ------------------------------------------------------------------

def find_nearest_tameable(player, creatures: list,
                          max_range: float = 3.0):
    """Return the closest tameable creature within *max_range*, or None."""
    best = None
    best_dist = max_range + 1
    for c in creatures:
        if not c.alive:
            continue
        if c.kind not in TAMEABLE_CREATURES:
            continue
        d = player.dist_to(c)
        if d < best_dist:
            best = c
            best_dist = d
    return best


# ------------------------------------------------------------------
# Initialization helper  (call once when Player is created or loaded)
# ------------------------------------------------------------------

def init_pet_system(player):
    """Attach a PetManager to the player if not already present."""
    if not hasattr(player, "pet_manager"):
        player.pet_manager = PetManager()
