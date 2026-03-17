"""Physical Storage System — gives every item a real location in the world.

Replaces the abstract settlement stores (simple dicts) with location-aware
storage buildings.  Each settlement has a SettlementStorage manager that
tracks StorageLocation objects (granary, warehouse, armoury, etc.).  Goods
are deposited/withdrawn from these physical buildings, and NPCs must walk
to the right building to pick up or drop off materials.

The old dict-based interface (`get_stores_ref`) is preserved via
StorageBackedDict, which transparently reads/writes the physical storage
so every existing caller keeps working without changes.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple, Any

from game.settings import (
    BARREL, CHEST, STABLE_FLOOR, TABLE, ANVIL, FLOOR,
)


# ================================================================
# STORAGE BUILDING DEFINITIONS
# ================================================================

STORAGE_BUILDINGS = {
    "granary": {
        "stores": ["food", "wheat", "bread", "flour", "meat", "fish",
                    "Wheat", "Vegetables", "Bread", "Flour", "Raw Meat",
                    "Fish", "Apple", "Berries", "Mushrooms", "Eggs",
                    "Milk", "Honey", "preserved_food",
                    "Lembas Bread", "Exotic Fruits", "Salted Fish"],
        "capacity": 200,
        "tile_marker": BARREL,
        "min_settlement": "hamlet",
    },
    "warehouse": {
        "stores": ["wood", "stone", "ore", "tools", "clothing", "leather",
                   "Wood", "Stone", "Iron Ore", "Copper Ore", "Iron Ingot",
                   "Planks", "Nails", "Leather", "Linen", "Rope", "Flax",
                   "Clay", "Salt", "Sand", "Resin", "Wool", "Ink",
                   "Beeswax", "Flowers", "Wolf Pelt", "raw_materials",
                   "Mooncloth", "Dwarven Steel", "Beast Hide", "Scrap Metal",
                   "Embroidered Cloth", "Gem Jewelry", "Silk", "Pearls",
                   "Ivory", "Jade", "Incense", "Soul Gem", "Bone Tools",
                   "War Drums"],
        "capacity": 300,
        "tile_marker": CHEST,
        "min_settlement": "village",
    },
    "armoury": {
        "stores": ["weapons", "armour", "shields",
                   "Iron Sword", "Steel Sword", "Iron Shield",
                   "Chainmail", "Plate Armour", "Leather Armour",
                   "Iron Helm", "Steel Helm",
                   "Masterwork Weapon", "Masterwork Armor", "Bone Weapon",
                   "Enchanted Arrows", "Death Shroud", "War Paint"],
        "capacity": 100,
        "tile_marker": CHEST,
        "min_settlement": "town",
    },
    "treasury": {
        "stores": ["gold", "gems", "jewellery",
                   "Gold Nugget", "Gold Coin", "Silver Coin",
                   "Ruby", "Emerald", "Sapphire", "Diamond",
                   "Gem Jewelry", "Phylactery Shard", "Cursed Artifact"],
        "capacity": 500,
        "tile_marker": CHEST,
        "min_settlement": "town",
    },
    "stable": {
        "stores": ["horses", "donkeys", "feed"],
        "capacity": 50,
        "tile_marker": STABLE_FLOOR,
        "min_settlement": "village",
    },
    "market_stall": {
        "stores": ["any"],  # can hold anything for sale
        "capacity": 50,
        "tile_marker": TABLE,
        "min_settlement": "hamlet",
    },
    "workshop": {
        "stores": ["tools", "raw_materials",
                   "Iron Ingot", "Planks", "Nails", "Leather",
                   "Linen", "Rope", "Clay"],
        "capacity": 30,
        "tile_marker": ANVIL,
        "min_settlement": "village",
    },
    "cellar": {
        "stores": ["ale", "wine", "preserved_food",
                   "Ale", "Water Flask", "Bread",
                   "Elven Wine", "Fine Ale", "Mushroom Brew",
                   "Mead", "Wine", "Dwarven Stout", "Rum"],
        "capacity": 100,
        "tile_marker": BARREL,
        "min_settlement": "village",
    },
}

# Settlement type ordering for min_settlement checks
_SETTLEMENT_ORDER = {"hamlet": 0, "village": 1, "town": 2, "city": 3, "castle": 3}


def _meets_minimum(settlement_kind: str, min_settlement: str) -> bool:
    """Return True if *settlement_kind* is at least *min_settlement*."""
    return _SETTLEMENT_ORDER.get(settlement_kind, 0) >= _SETTLEMENT_ORDER.get(min_settlement, 0)


# ================================================================
# STORAGE LOCATION
# ================================================================

class StorageLocation:
    """A physical place where goods are stored."""
    __slots__ = ('name', 'kind', 'x', 'y', 'building_idx',
                 'capacity', 'contents', 'allowed_goods')

    def __init__(self, name: str, kind: str, x: int, y: int,
                 building_idx: int, capacity: int):
        self.name = name
        self.kind = kind
        self.x = x
        self.y = y
        self.building_idx = building_idx
        self.capacity = capacity
        self.contents: Dict[str, int] = {}
        self.allowed_goods: List[str] = []

    # -- mutators --

    def add(self, good: str, quantity: int) -> int:
        """Add *quantity* of *good*.  Returns amount actually stored."""
        if quantity <= 0:
            return 0
        current = sum(self.contents.values())
        space = self.capacity - current
        actual = min(quantity, max(0, space))
        if actual > 0:
            self.contents[good] = self.contents.get(good, 0) + actual
        return actual

    def remove(self, good: str, quantity: int) -> int:
        """Remove up to *quantity* of *good*.  Returns amount actually removed."""
        if quantity <= 0:
            return 0
        available = self.contents.get(good, 0)
        actual = min(quantity, available)
        if actual > 0:
            self.contents[good] = available - actual
            if self.contents[good] <= 0:
                self.contents.pop(good, None)
        return actual

    # -- queries --

    def has(self, good: str, quantity: int = 1) -> bool:
        return self.contents.get(good, 0) >= quantity

    def accepts(self, good: str) -> bool:
        """Return True if this location can store the given good."""
        return "any" in self.allowed_goods or good in self.allowed_goods

    @property
    def total_stored(self) -> int:
        return sum(self.contents.values())

    @property
    def space_remaining(self) -> int:
        return max(0, self.capacity - self.total_stored)


# ================================================================
# SETTLEMENT STORAGE MANAGER
# ================================================================

class SettlementStorage:
    """Manages all storage locations in a settlement."""

    def __init__(self, settlement_name: str):
        self.settlement_name = settlement_name
        self.locations: List[StorageLocation] = []

    # -- high-level operations --

    def find_storage_for(self, good: str, quantity: int = 1) -> Optional[StorageLocation]:
        """Find the best storage location for a good (specialised first)."""
        # 1. Specialised storage with space
        for loc in self.locations:
            if good in loc.allowed_goods and loc.space_remaining >= quantity:
                return loc
        # 2. General storage ("any")
        for loc in self.locations:
            if "any" in loc.allowed_goods and loc.space_remaining >= quantity:
                return loc
        # 3. Specialised with *some* space (partial fit)
        for loc in self.locations:
            if good in loc.allowed_goods and loc.space_remaining > 0:
                return loc
        # 4. General with some space
        for loc in self.locations:
            if "any" in loc.allowed_goods and loc.space_remaining > 0:
                return loc
        return None

    def find_good(self, good: str, quantity: int = 1) -> Optional[StorageLocation]:
        """Find a location that has at least *quantity* of *good*."""
        for loc in self.locations:
            if loc.has(good, quantity):
                return loc
        # Partial: find any location with some of the good
        for loc in self.locations:
            if loc.contents.get(good, 0) > 0:
                return loc
        return None

    def total_of(self, good: str) -> int:
        """Total quantity of *good* across all storage."""
        return sum(loc.contents.get(good, 0) for loc in self.locations)

    def deposit(self, good: str, quantity: int) -> int:
        """Deposit goods into the best available storage.  Returns qty stored."""
        if quantity <= 0:
            return 0
        remaining = quantity
        # Pass 1: specialised storage
        for loc in self.locations:
            if remaining <= 0:
                break
            if good in loc.allowed_goods:
                stored = loc.add(good, remaining)
                remaining -= stored
        # Pass 2: general ("any") storage
        for loc in self.locations:
            if remaining <= 0:
                break
            if "any" in loc.allowed_goods:
                stored = loc.add(good, remaining)
                remaining -= stored
        # Pass 3: any storage at all that accepts this good
        for loc in self.locations:
            if remaining <= 0:
                break
            if loc.accepts(good):
                stored = loc.add(good, remaining)
                remaining -= stored
        return quantity - remaining

    def withdraw(self, good: str, quantity: int) -> Tuple[int, Optional[StorageLocation]]:
        """Withdraw goods from storage.  Returns (actual_qty, last_location)."""
        if quantity <= 0:
            return 0, None
        total = 0
        last_loc = None
        for loc in self.locations:
            available = loc.contents.get(good, 0)
            if available > 0:
                take = min(available, quantity - total)
                loc.remove(good, take)
                total += take
                last_loc = loc
            if total >= quantity:
                break
        return total, last_loc

    def all_goods(self) -> Dict[str, int]:
        """Aggregate of all goods across all locations."""
        result: Dict[str, int] = {}
        for loc in self.locations:
            for good, qty in loc.contents.items():
                result[good] = result.get(good, 0) + qty
        return result

    @property
    def total_capacity(self) -> int:
        return sum(loc.capacity for loc in self.locations)

    @property
    def total_stored(self) -> int:
        return sum(loc.total_stored for loc in self.locations)

    @property
    def space_remaining(self) -> int:
        return sum(loc.space_remaining for loc in self.locations)


# ================================================================
# STORAGE-BACKED DICT  (compatibility wrapper)
# ================================================================

class StorageBackedDict(dict):
    """A dict that is backed by a SettlementStorage.

    Reads aggregate across all StorageLocations; writes go through the
    storage manager's deposit/withdraw logic so goods land in the right
    physical building.

    This lets all existing code that does ``stores = get_stores_ref(name)``
    and then ``stores["food"] += 3`` keep working transparently.
    """

    def __init__(self, storage: SettlementStorage):
        super().__init__()
        self._storage = storage

    # -- read --

    def __getitem__(self, key: str) -> int:
        return self._storage.total_of(key)

    def get(self, key: str, default: int = 0) -> int:
        val = self._storage.total_of(key)
        return val if val > 0 else default

    def __contains__(self, key) -> bool:
        return self._storage.total_of(key) > 0

    def keys(self):
        return self._storage.all_goods().keys()

    def values(self):
        return self._storage.all_goods().values()

    def items(self):
        return self._storage.all_goods().items()

    def __iter__(self):
        return iter(self._storage.all_goods())

    def __len__(self):
        return len(self._storage.all_goods())

    def __repr__(self):
        return f"StorageBackedDict({self._storage.settlement_name}, {dict(self._storage.all_goods())})"

    # -- write --

    def __setitem__(self, key: str, value: int):
        """Setting a key adjusts the storage to match the new value.

        If value > current total, deposit the difference.
        If value < current total, withdraw the difference.
        If value <= 0, withdraw everything.
        """
        current = self._storage.total_of(key)
        if value <= 0:
            self._storage.withdraw(key, current)
        elif value > current:
            self._storage.deposit(key, value - current)
        elif value < current:
            self._storage.withdraw(key, current - value)
        # value == current: no-op

    def __delitem__(self, key: str):
        current = self._storage.total_of(key)
        if current > 0:
            self._storage.withdraw(key, current)

    def pop(self, key: str, *args):
        current = self._storage.total_of(key)
        if current > 0:
            self._storage.withdraw(key, current)
            return current
        if args:
            return args[0]
        raise KeyError(key)

    def update(self, other=None, **kwargs):
        d = {}
        if other:
            d.update(other)
        d.update(kwargs)
        for k, v in d.items():
            self[k] = v

    def copy(self):
        """Return a plain dict snapshot (e.g. for get_settlement_stores)."""
        return dict(self._storage.all_goods())


# ================================================================
# AUTO-GENERATE STORAGE BUILDINGS FOR A SETTLEMENT
# ================================================================

def generate_storage_for_settlement(settlement_plan, storage: SettlementStorage):
    """Populate *storage* with StorageLocations appropriate for the settlement.

    Called once when a settlement is first accessed.
    """
    kind = settlement_plan.kind
    bldg_idx_offset = len(settlement_plan.buildings)  # avoid collisions

    # Capacity scales with settlement size
    _cap_mult = {"hamlet": 0.5, "village": 1.0, "town": 2.0, "city": 4.0, "castle": 3.0}
    mult = _cap_mult.get(kind, 1.0)

    idx = 0
    for sb_name, sb_def in STORAGE_BUILDINGS.items():
        if not _meets_minimum(kind, sb_def["min_settlement"]):
            continue

        cap = int(sb_def["capacity"] * mult)
        loc = StorageLocation(
            name=f"{settlement_plan.name} {sb_name.replace('_', ' ').title()}",
            kind=sb_name,
            x=settlement_plan.x,
            y=settlement_plan.y,
            building_idx=bldg_idx_offset + idx,
            capacity=cap,
        )
        loc.allowed_goods = list(sb_def["stores"])
        storage.locations.append(loc)
        idx += 1

    # If we placed real buildings, try to match locations to them
    _assign_storage_to_buildings(settlement_plan, storage)


def _assign_storage_to_buildings(sp, storage: SettlementStorage):
    """Try to position each StorageLocation at an actual building.

    First tries to match by ``storage_kind`` tag set during chunk generation,
    then falls back to matching by building kind category.
    """
    if not sp.buildings:
        return

    # Build a lookup by building kind (fallback)
    _kind_map = {
        "granary": ["storage", "utility", "house"],
        "warehouse": ["storage", "utility", "shop"],
        "armoury": ["storage", "military", "shop"],
        "treasury": ["storage", "castle", "shop"],
        "stable": ["utility"],
        "market_stall": ["shop"],
        "workshop": ["shop", "storage"],
        "cellar": ["storage", "tavern", "house"],
    }

    used_bldgs: set = set()

    for loc in storage.locations:
        assigned = False

        # Pass 1: match by storage_kind tag (exact match from chunk gen)
        for bld_idx, bld in enumerate(sp.buildings):
            if bld_idx in used_bldgs:
                continue
            if bld.get("storage_kind") == loc.kind:
                loc.x = bld["x"] + bld["w"] // 2
                loc.y = bld["y"] + bld["h"] // 2
                loc.building_idx = bld_idx
                used_bldgs.add(bld_idx)
                assigned = True
                break

        if assigned:
            continue

        # Pass 2: match by building kind category
        preferred_kinds = _kind_map.get(loc.kind, [])
        for bld_idx, bld in enumerate(sp.buildings):
            if bld_idx in used_bldgs:
                continue
            bld_kind = bld.get("kind", "")
            if bld_kind in preferred_kinds:
                loc.x = bld["x"] + bld["w"] // 2
                loc.y = bld["y"] + bld["h"] // 2
                loc.building_idx = bld_idx
                used_bldgs.add(bld_idx)
                assigned = True
                break

        if not assigned:
            # Fallback: use any unassigned building
            for bld_idx, bld in enumerate(sp.buildings):
                if bld_idx not in used_bldgs:
                    loc.x = bld["x"] + bld["w"] // 2
                    loc.y = bld["y"] + bld["h"] // 2
                    loc.building_idx = bld_idx
                    used_bldgs.add(bld_idx)
                    break


# ================================================================
# SEED INITIAL STOCK INTO PHYSICAL STORAGE
# ================================================================

# Default starting stock (matches the old _ensure_stores defaults)
_DEFAULT_STOCK = {
    "food": 50, "wood": 20, "stone": 10, "ore": 5, "gold": 100,
    "weapons": 5, "tools": 10, "clothing": 10,
    "leather": 3, "herbs": 3, "potions": 1, "ale": 5,
    "wool": 2, "armour": 1,
    "Wood": 15, "Stone": 8, "Iron Ore": 4, "Copper Ore": 2,
    "Wheat": 10, "Vegetables": 5, "Herbs": 4, "Flax": 3,
    "Clay": 3, "Salt": 2, "Honey": 2, "Beeswax": 1,
    "Berries": 3, "Mushrooms": 2, "Flowers": 2,
    "Wolf Pelt": 2, "Raw Meat": 5, "Sand": 2,
    "Resin": 1, "Wool": 3, "Milk": 2, "Eggs": 3,
    "Fish": 4, "Apple": 3, "Gold Nugget": 1,
    "Iron Ingot": 3, "Planks": 4, "Nails": 5,
    "Leather": 2, "Linen": 2, "Rope": 2,
    "Flour": 3, "Ink": 1,
    "Bread": 8, "Ale": 4, "Water Flask": 4,
}


def seed_initial_stock(storage: SettlementStorage):
    """Populate a newly created SettlementStorage with starting goods."""
    for good, qty in _DEFAULT_STOCK.items():
        storage.deposit(good, qty)


# ================================================================
# NPC HOME STORAGE
# ================================================================

class NpcHomeStorage:
    """Lightweight personal storage at an NPC's home building."""
    __slots__ = ('tools', 'food', 'valuables')

    def __init__(self):
        self.tools: List[str] = []      # work equipment names
        self.food: int = 3              # personal food stock
        self.valuables: List[str] = []  # personal treasures

    def add_tool(self, tool_name: str):
        if tool_name not in self.tools:
            self.tools.append(tool_name)

    def remove_tool(self, tool_name: str) -> bool:
        if tool_name in self.tools:
            self.tools.remove(tool_name)
            return True
        return False

    def consume_food(self) -> bool:
        """Consume one unit of personal food.  Returns False if empty."""
        if self.food > 0:
            self.food -= 1
            return True
        return False


# Maps profession -> default tool name
PROFESSION_TOOLS = {
    "Farmer": "hoe",
    "Miner": "pickaxe",
    "Fisher": "fishing_rod",
    "Fisherman": "fishing_rod",
    "Woodcutter": "axe",
    "Blacksmith": "hammer",
    "Armourer": "hammer",
    "Carpenter": "saw",
    "Cooper": "saw",
    "Wheelwright": "saw",
    "Shipbuilder": "saw",
    "Tanner": "scraping_knife",
    "Weaver": "loom_shuttle",
    "Potter": "potter_wheel",
    "Baker": "rolling_pin",
    "Brewer": "brewing_paddle",
    "Alchemist": "mortar_pestle",
    "Jeweler": "jewelers_loupe",
    "Glassblower": "blowpipe",
    "Mason": "chisel",
    "Hunter": "bow",
    "Herbalist": "herb_pouch",
    "Shepherd": "crook",
    "Beekeeper": "smoker",
    "Prospector": "pan",
    "Cook": "knife",
    "Barber": "razor",
    "Scribe": "quill",
    "Cartographer": "compass",
}


def ensure_npc_home_storage(npc) -> NpcHomeStorage:
    """Get or create home storage for an NPC, seeded with profession tools."""
    if not hasattr(npc, '_home_storage'):
        hs = NpcHomeStorage()
        prof = getattr(npc, 'npc_class', '') or getattr(npc, 'profession', '')
        tool = PROFESSION_TOOLS.get(prof)
        if tool:
            hs.add_tool(tool)
        npc._home_storage = hs
    return npc._home_storage


# ================================================================
# HELPER: find nearest storage building for a good
# ================================================================

def find_nearest_storage(storage: SettlementStorage, good: str,
                         from_x: float, from_y: float,
                         need_space: bool = False,
                         need_stock: bool = False) -> Optional[StorageLocation]:
    """Find the closest StorageLocation for *good*.

    If *need_space* is True, only considers locations with room.
    If *need_stock* is True, only considers locations that have the good.
    """
    import math
    best = None
    best_dist = float('inf')
    for loc in storage.locations:
        if not loc.accepts(good):
            continue
        if need_space and loc.space_remaining <= 0:
            continue
        if need_stock and loc.contents.get(good, 0) <= 0:
            continue
        dx = loc.x - from_x
        dy = loc.y - from_y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < best_dist:
            best_dist = dist
            best = loc
    return best
