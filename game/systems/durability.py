"""
Durability system: all objects can be damaged, broken, and repaired.

Every destructible tile has:
- Material type (wood, stone, iron, glass, cloth)
- HP based on material and construction
- Resistance/vulnerability to different attack types
- Replacement tile when destroyed (walls→rubble, doors→floor)

Attack types:
- PHYSICAL: swords, axes, hammering, body strength
- FIRE: torches, fire arrows, burning oil
- SIEGE: catapult stones, battering rams, trebuchets
- PICK: lockpicks, thieves' tools (doors/locks only)

Materials:
- Wood: weak to fire (2x), moderate physical, weak to siege
- Stone: resists fire (0.3x), strong physical, moderate siege
- Iron: resists fire (0.2x), very strong physical, moderate siege
- Glass: very fragile to everything
- Cloth: very weak to fire (3x), weak physical
"""

import random
from typing import Dict, List, Tuple, Optional
from game.settings import *


# ================================================================
# MATERIAL PROPERTIES
# ================================================================

MATERIALS = {
    "wood": {
        "base_hp_mult": 1.0,
        "resistance": {
            "physical": 1.0,
            "fire": 2.0,      # takes double fire damage
            "siege": 1.5,
            "pick": 0.8,
        },
        "flammable": True,
    },
    "stone": {
        "base_hp_mult": 2.5,
        "resistance": {
            "physical": 0.5,   # resists physical
            "fire": 0.3,       # nearly fireproof
            "siege": 0.8,
            "pick": 0.1,       # can't pick stone
        },
        "flammable": False,
    },
    "iron": {
        "base_hp_mult": 3.0,
        "resistance": {
            "physical": 0.3,
            "fire": 0.2,
            "siege": 0.6,
            "pick": 0.5,       # can be picked with skill
        },
        "flammable": False,
    },
    "glass": {
        "base_hp_mult": 0.3,
        "resistance": {
            "physical": 3.0,   # very fragile
            "fire": 1.0,
            "siege": 5.0,
            "pick": 0.0,       # doesn't apply
        },
        "flammable": False,
    },
    "cloth": {
        "base_hp_mult": 0.4,
        "resistance": {
            "physical": 1.5,
            "fire": 3.0,       # burns easily
            "siege": 2.0,
            "pick": 0.0,
        },
        "flammable": True,
    },
}

# What material each tile type is made of
TILE_MATERIAL = {
    WALL: "stone",
    BUILT_WALL: "stone",
    DOOR: "wood",           # basic wooden door
    LOCKED_DOOR: "iron",    # iron-reinforced locked door
    WINDOW: "glass",
    TABLE: "wood",
    BED: "cloth",           # bed frame is wood but covering is cloth
    CHEST: "wood",
    STAIRS_UP: "stone",
    STAIRS_DOWN: "stone",
    BUILT_FLOOR: "wood",
    IRON_GATE: "iron",      # portcullis
    BOOKSHELF: "wood",
    BARREL: "wood",
    THRONE: "wood",         # gilded wood
    FIREPLACE: "stone",
    PILLAR: "stone",
    ALTAR: "stone",
    ANVIL: "iron",
    FORGE_FIRE: "stone",
    FOUNTAIN: "stone",
    ARCHWAY: "stone",
}

# Base HP per tile type (before material multiplier)
TILE_BASE_HP = {
    WALL: 25,
    BUILT_WALL: 20,
    DOOR: 20,
    LOCKED_DOOR: 20,
    WINDOW: 10,
    TABLE: 15,
    BED: 12,
    CHEST: 18,
    STAIRS_UP: 40,
    STAIRS_DOWN: 40,
    BUILT_FLOOR: 25,
    IRON_GATE: 15,
    BOOKSHELF: 12,
    BARREL: 10,
    THRONE: 20,
    FIREPLACE: 30,
    PILLAR: 35,
    ALTAR: 25,
    ANVIL: 40,
    FORGE_FIRE: 30,
    FOUNTAIN: 25,
    ARCHWAY: 30,
}

def get_tile_max_hp(tile_type: int) -> int:
    """Get maximum HP for a tile considering its material."""
    base = TILE_BASE_HP.get(tile_type, 0)
    material_name = TILE_MATERIAL.get(tile_type, "wood")
    material = MATERIALS.get(material_name, MATERIALS["wood"])
    return int(base * material["base_hp_mult"])

def get_damage_multiplier(tile_type: int, attack_type: str) -> float:
    """Get damage multiplier for attacking a tile with a specific method."""
    material_name = TILE_MATERIAL.get(tile_type, "wood")
    material = MATERIALS.get(material_name, MATERIALS["wood"])
    return material["resistance"].get(attack_type, 1.0)

def is_flammable(tile_type: int) -> bool:
    """Check if a tile can catch fire."""
    material_name = TILE_MATERIAL.get(tile_type, "wood")
    return MATERIALS.get(material_name, {}).get("flammable", False)

# Backward compat — old TILE_DURABILITY computed from new system
TILE_DURABILITY = {t: get_tile_max_hp(t) for t in TILE_BASE_HP}

# What a tile becomes when destroyed
TILE_DESTROYED = {
    WALL: RUBBLE,          # stone wall → rubble (slows movement)
    BUILT_WALL: RUBBLE,
    DOOR: FLOOR,           # wooden door breaks open → walkable
    LOCKED_DOOR: FLOOR,    # iron door breaks → walkable
    WINDOW: FLOOR,         # glass smashes → walkable
    TABLE: FLOOR,
    BED: FLOOR,
    CHEST: FLOOR,
    BUILT_FLOOR: GRASS,
    IRON_GATE: RUBBLE,     # portcullis collapses into rubble
    BOOKSHELF: RUBBLE,     # heavy bookshelf → debris
    BARREL: FLOOR,         # barrel smashes → nothing left
    THRONE: RUBBLE,        # throne destroyed → debris
    PILLAR: RUBBLE,        # pillar collapse → heavy rubble
    ARCHWAY: RUBBLE,       # archway collapse → heavy rubble
}


# ================================================================
# RUBBLE ACCUMULATION
# ================================================================

class RubbleTracker:
    """Tracks rubble depth at each position. Multiple destroyed structures
    at the same location create deeper rubble that's harder to traverse.

    Rubble depth affects:
    - Walk cost: base 2.0 + 0.5 per extra layer
    - At depth 3+: impassable without climbing skill or clearing
    - Small/agile creatures can navigate rubble easier
    - Rubble can be cleared by workers (takes time)
    """

    def __init__(self):
        self.depth: Dict[Tuple[int, int], int] = {}  # (x,y) → rubble layers

    def add_rubble(self, x: int, y: int, amount: int = 1):
        """Add rubble layers at a position (from wall/pillar collapse)."""
        current = self.depth.get((x, y), 0)
        self.depth[(x, y)] = current + amount

    def get_depth(self, x: int, y: int) -> int:
        """Get rubble depth at position. 0 = no rubble."""
        return self.depth.get((x, y), 0)

    def get_walk_cost(self, x: int, y: int) -> float:
        """Get movement cost modifier for rubble at this position.

        Depth 0: no rubble (normal tile cost)
        Depth 1: 2.0 (standard rubble)
        Depth 2: 2.5 (piled rubble)
        Depth 3+: 999 (impassable — blocked by debris)
        """
        d = self.depth.get((x, y), 0)
        if d == 0:
            return 0  # no rubble — use normal tile cost
        elif d == 1:
            return 2.0
        elif d == 2:
            return 2.5
        else:
            return 999  # impassable

    def can_traverse(self, x: int, y: int, climbing_skill: int = 0,
                      is_small: bool = False) -> bool:
        """Check if an entity can traverse rubble here.

        Climbing skill >= 3 allows traversing depth 3 rubble.
        Small creatures (goblins, kobolds) can squeeze through depth 3.
        """
        d = self.depth.get((x, y), 0)
        if d < 3:
            return True
        if climbing_skill >= 3:
            return True
        if is_small and d <= 3:
            return True
        return False

    def clear_rubble(self, x: int, y: int, amount: int = 1,
                      dump_x: int = None, dump_y: int = None) -> Tuple[int, int]:
        """Move rubble from one location. Returns (remaining_at_source, added_at_dump).

        Rubble doesn't vanish — it gets moved to a dump location. If no dump
        specified, rubble is scattered adjacent (randomly).

        Args:
            x, y: Source rubble position
            amount: Layers to move
            dump_x, dump_y: Where to dump it (creates rubble there)

        Returns:
            (remaining_depth_at_source, new_depth_at_dump)
        """
        current = self.depth.get((x, y), 0)
        if current <= 0:
            return (0, 0)

        moved = min(amount, current)
        new_depth = current - moved
        if new_depth == 0:
            self.depth.pop((x, y), None)
        else:
            self.depth[(x, y)] = new_depth

        # Dump rubble somewhere
        dump_depth = 0
        if dump_x is not None and dump_y is not None:
            self.add_rubble(dump_x, dump_y, moved)
            dump_depth = self.depth.get((dump_x, dump_y), 0)

        return (new_depth, dump_depth)

    @staticmethod
    def calc_clear_rate(strength: int, has_tools: bool = False,
                         creature_size: str = "medium") -> float:
        """Calculate how fast an entity can clear rubble.

        Returns layers per game-hour of work.

        Strength determines base rate:
        - STR 8-10 (average): can't move stone bare-handed
        - STR 12-14 (strong): 0.2 layers/hr bare, 0.5 with tools
        - STR 16-18 (very strong): 0.5 bare, 1.0 with tools
        - STR 20+ (heroic): 1.0 bare, 2.0 with tools
        - STR 25+ (giant): 3.0 bare (living siege engine)
        - STR 30+ (colossal): 5.0 bare (titan)

        Tools: pickaxe, shovel, wheelbarrow → 2x-3x multiplier
        Size: large creatures get bonus, small get penalty
        """
        if strength < 10 and not has_tools:
            return 0.0  # too weak to move stone bare-handed

        # Base rate from strength
        if strength >= 30:
            base = 5.0    # titan / colossal creature
        elif strength >= 25:
            base = 3.0    # giant — living siege engine
        elif strength >= 20:
            base = 1.0    # heroic strength
        elif strength >= 16:
            base = 0.5    # very strong
        elif strength >= 12:
            base = 0.2    # strong
        elif strength >= 10:
            base = 0.05   # average — barely moves pebbles
        else:
            base = 0.0

        # Tool multiplier
        if has_tools:
            if strength >= 25:
                base *= 1.5  # tools matter less for giants
            else:
                base *= 2.5  # tools are crucial for normal folk

        # Size modifier
        size_mult = {
            "tiny": 0.1,
            "small": 0.5,
            "medium": 1.0,
            "large": 1.5,
            "huge": 2.5,
            "gargantuan": 4.0,
        }.get(creature_size, 1.0)

        return base * size_mult

    @staticmethod
    def calc_bash_damage(strength: int, creature_size: str = "medium",
                          has_weapon: bool = True) -> int:
        """Calculate how much structural damage an entity deals per hit.

        Very strong creatures and giants can bash through walls like
        siege engines. Returns damage per strike.

        For reference:
        - Catapult deals 35 siege damage per round
        - Battering ram deals 25 per round
        - A hill giant (STR 21) deals ~15 per hit
        - A fire giant (STR 25) deals ~25 per hit
        - A storm giant (STR 29) deals ~40 per hit
        """
        base = max(0, (strength - 10) // 2)  # STR modifier

        if has_weapon:
            base = int(base * 1.5)

        # Size bonus — large creatures hit harder against structures
        size_bonus = {
            "tiny": 0,
            "small": 0,
            "medium": 0,
            "large": 5,
            "huge": 15,
            "gargantuan": 30,
        }.get(creature_size, 0)

        return base + size_bonus

# Materials needed to repair each tile type
REPAIR_MATERIALS = {
    WALL: [("Stone", 2)],
    BUILT_WALL: [("Stone", 1), ("Wood", 1)],
    DOOR: [("Wood", 2), ("Nails", 1)],
    LOCKED_DOOR: [("Wood", 2), ("Nails", 1), ("Iron Ingot", 1)],
    WINDOW: [("Glass Pane", 1), ("Wood", 1)],
    TABLE: [("Wood", 2), ("Nails", 1)],
    BED: [("Wood", 2), ("Wool", 1)],
    CHEST: [("Wood", 2), ("Nails", 2), ("Iron Ingot", 1)],
    BUILT_FLOOR: [("Wood", 2)],
    IRON_GATE: [("Iron Ingot", 3)],
}

# Can a player bash through with body strength? (STR check DC)
BASH_DC = {
    DOOR: 12,           # wooden door — moderate STR check
    LOCKED_DOOR: 18,    # iron-reinforced — hard
    WINDOW: 8,          # glass — easy
    BARREL: 10,         # wooden barrel
    IRON_GATE: 25,      # portcullis — nearly impossible bare-handed
    BOOKSHELF: 14,      # heavy bookshelf
}


class DurabilitySystem:
    """Tracks and manages HP of destructible tiles."""

    def __init__(self):
        # Only track tiles that have taken damage (sparse storage)
        self.tile_hp: Dict[Tuple[int, int], int] = {}
        self.destroyed_tiles: List[Tuple[int, int, int]] = []  # (x, y, original_type)
        self.decay_timer = 0.0
        self.rubble = RubbleTracker()

    def get_hp(self, x: int, y: int, tile_type: int) -> int:
        """Get current HP of a tile. Full HP if not tracked."""
        if (x, y) in self.tile_hp:
            return self.tile_hp[(x, y)]
        return TILE_DURABILITY.get(tile_type, 0)

    def damage_tile(self, x: int, y: int, world, amount: int,
                    attack_type: str = "physical") -> Optional[str]:
        """Damage a tile with a specific attack type. Returns message if destroyed.

        Attack types: "physical", "fire", "siege", "pick"
        Damage is modified by the tile's material resistance.
        """
        tile_type = world.tiles[y][x]
        max_hp = get_tile_max_hp(tile_type)
        if max_hp == 0:
            return None  # indestructible

        # Apply material resistance
        mult = get_damage_multiplier(tile_type, attack_type)
        effective_damage = int(amount * mult)
        if effective_damage <= 0:
            material = TILE_MATERIAL.get(tile_type, "?")
            return f"The {material} resists {attack_type} damage!"

        current = self.tile_hp.get((x, y), max_hp)
        current -= effective_damage
        self.tile_hp[(x, y)] = current

        material = TILE_MATERIAL.get(tile_type, "unknown")
        names = {WALL: "wall", BUILT_WALL: "wall", DOOR: "door",
                 LOCKED_DOOR: "locked door", WINDOW: "window",
                 TABLE: "table", BED: "bed", CHEST: "chest",
                 IRON_GATE: "iron gate", BOOKSHELF: "bookshelf",
                 BARREL: "barrel", PILLAR: "pillar"}
        name = names.get(tile_type, "structure")

        if current <= 0:
            # Destroyed!
            replacement = TILE_DESTROYED.get(tile_type, GRASS)
            original = tile_type
            world.modify_tile(x, y, replacement)
            self.destroyed_tiles.append((x, y, original))
            del self.tile_hp[(x, y)]

            # Accumulate rubble for heavy materials (stone, iron)
            if replacement == RUBBLE:
                rubble_layers = {
                    "stone": 2,    # stone wall collapse → heavy rubble
                    "iron": 2,     # iron gate → heavy debris
                    "wood": 1,     # wooden structure → light debris
                }.get(material, 1)
                self.rubble.add_rubble(x, y, rubble_layers)
                depth = self.rubble.get_depth(x, y)
                if depth >= 3:
                    # So much rubble it's now impassable
                    world.modify_tile(x, y, RUBBLE)  # stays rubble

            # Fire can spread to adjacent flammable tiles
            if attack_type == "fire" and is_flammable(tile_type):
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = x + dx, y + dy
                    if (0 <= nx < world.width and 0 <= ny < world.height
                        and is_flammable(world.tiles[ny][nx])):
                        if random.random() < 0.3:
                            spread_hp = self.tile_hp.get((nx, ny),
                                get_tile_max_hp(world.tiles[ny][nx]))
                            self.tile_hp[(nx, ny)] = max(0, spread_hp - amount // 2)

            rubble_info = ""
            depth = self.rubble.get_depth(x, y)
            if depth >= 3:
                rubble_info = " Rubble blocks the passage!"
            elif depth >= 2:
                rubble_info = " Heavy rubble slows movement."
            elif depth >= 1:
                rubble_info = " Rubble litters the ground."
            return f"The {material} {name} was destroyed by {attack_type}!{rubble_info}"

        pct = current * 100 // max_hp
        return f"The {name} takes {effective_damage} {attack_type} damage ({pct}% remaining)"

    def bash_tile(self, x: int, y: int, world, strength: int,
                  creature_size: str = "medium",
                  has_weapon: bool = True) -> Optional[str]:
        """Attempt to bash through a tile with body strength.

        Normal creatures use STR check vs BASH_DC.
        Giants and huge creatures deal siege-level damage directly.

        Args:
            strength: STR ability score
            creature_size: tiny/small/medium/large/huge/gargantuan
            has_weapon: whether carrying a weapon/tool
        """
        tile_type = world.tiles[y][x]
        dc = BASH_DC.get(tile_type)
        if dc is None:
            # Check if it's a wall — very strong creatures can bash walls
            if tile_type in (WALL, BUILT_WALL) and strength >= 20:
                damage = RubbleTracker.calc_bash_damage(strength, creature_size, has_weapon)
                if damage >= 10:  # minimum effective siege damage
                    result = self.damage_tile(x, y, world, damage, "siege")
                    return f"Massive strike! ({damage} siege damage) {result}"
            return "Can't bash that."

        # Giants and huge creatures bypass the DC check entirely
        if creature_size in ("huge", "gargantuan") or strength >= 25:
            damage = RubbleTracker.calc_bash_damage(strength, creature_size, has_weapon)
            result = self.damage_tile(x, y, world, damage, "physical")
            if result and "destroyed" in result.lower():
                return f"Smashed through with brute force! ({damage} damage) {result}"
            return f"Powerful strike! ({damage} damage) {result or ''}"

        # Normal STR check for medium creatures
        str_mod = (strength - 10) // 2
        roll = random.randint(1, 20) + str_mod

        if roll >= dc:
            damage = RubbleTracker.calc_bash_damage(strength, creature_size, has_weapon)
            damage = max(1, damage)
            result = self.damage_tile(x, y, world, damage, "physical")
            if result and "destroyed" in result.lower():
                return f"Bashed through! (rolled {roll} vs DC {dc}) {result}"
            return f"Hit it hard! (rolled {roll} vs DC {dc}) {result or ''}"
        else:
            return f"Failed to break through (rolled {roll} vs DC {dc})"

    def repair_tile(self, x: int, y: int, world, original_type: int,
                    repairer_inventory: list) -> Optional[str]:
        """Repair a destroyed tile if the repairer has materials."""
        materials = REPAIR_MATERIALS.get(original_type)
        if not materials:
            return "Cannot repair this type of tile."

        # Check materials
        for item_name, count in materials:
            total = sum(i.count if i.stackable else 1
                       for i in repairer_inventory if i.name == item_name)
            if total < count:
                return f"Need {count} {item_name} to repair."

        # Consume materials
        for item_name, count in materials:
            remaining = count
            for item in list(repairer_inventory):
                if item.name == item_name and remaining > 0:
                    if item.stackable:
                        used = min(item.count, remaining)
                        item.count -= used
                        remaining -= used
                        if item.count <= 0:
                            repairer_inventory.remove(item)
                    else:
                        repairer_inventory.remove(item)
                        remaining -= 1

        # Restore tile
        world.modify_tile(x, y, original_type)
        self.tile_hp[(x, y)] = TILE_DURABILITY.get(original_type, 30)

        # Remove from destroyed list
        self.destroyed_tiles = [(dx, dy, dt) for dx, dy, dt in self.destroyed_tiles
                                if not (dx == x and dy == y)]

        names = {WALL: "wall", BUILT_WALL: "wall", DOOR: "door",
                 TABLE: "table", BED: "bed", CHEST: "chest", WINDOW: "window"}
        return f"Repaired the {names.get(original_type, 'structure')}!"

    def update(self, dt: float, world):
        """Slow natural decay of damaged structures."""
        self.decay_timer += dt
        if self.decay_timer < 300:  # every 5 minutes
            return
        self.decay_timer = 0

        # Slightly decay damaged tiles
        to_remove = []
        for (x, y), hp in self.tile_hp.items():
            if random.random() < 0.05:  # 5% chance per check
                self.tile_hp[(x, y)] = hp - 1
                if hp - 1 <= 0:
                    tile_type = world.tiles[y][x]
                    replacement = TILE_DESTROYED.get(tile_type, GRASS)
                    if replacement != tile_type:
                        self.destroyed_tiles.append((x, y, tile_type))
                        world.modify_tile(x, y, replacement)
                        to_remove.append((x, y))
        for key in to_remove:
            self.tile_hp.pop(key, None)
