"""Player Housing — buy or earn a house, store items, rest, customize.

A player can own one house per settlement. Houses are acquired by:
  1. Reaching Noble rank (free land grant from the kingdom)
  2. Purchasing from a settlement NPC for 500 gold

Houses provide persistent storage (50 slots), a rest bonus (+20 % HP
regen for 8 hours), and furniture customization.

Integrates with:
  - game.systems.faction_ranks.FactionRankSystem  (Noble rank check)
  - game.core.player.Player  (gold, inventory, HP regen)
  - game.core.items.Item  (storage and furniture items)
"""

import time
from typing import Dict, List, Optional, Tuple

from game.core.items import Item, make_item


# ================================================================
# CONSTANTS
# ================================================================

HOUSE_PURCHASE_COST = 500       # gold
MAX_STORAGE_SLOTS = 50
REST_BONUS_REGEN = 0.20        # +20 % HP regen multiplier
REST_BONUS_DURATION = 28800.0  # 8 real-time hours (seconds)

# Valid furniture types the player can place
FURNITURE_TYPES = {
    "bed":       {"name": "Bed",       "description": "A comfortable bed for resting."},
    "table":     {"name": "Table",     "description": "A sturdy wooden table."},
    "chest":     {"name": "Chest",     "description": "Extra storage chest (+10 slots)."},
    "bookshelf": {"name": "Bookshelf", "description": "A bookshelf for tomes and scrolls."},
    "chair":     {"name": "Chair",     "description": "A simple wooden chair."},
    "fireplace": {"name": "Fireplace", "description": "Warms the home on cold nights."},
    "rug":       {"name": "Rug",       "description": "A decorative woven rug."},
    "banner":    {"name": "Banner",    "description": "A banner displaying your colours."},
}

EXTRA_SLOTS_PER_CHEST = 10  # each placed chest furniture adds slots


# ================================================================
# PLAYER HOUSE
# ================================================================

class PlayerHouse:
    """Represents a single player-owned house in a settlement."""

    def __init__(self, settlement_name: str, kingdom: str,
                 tile_x: int, tile_y: int):
        self.settlement: str = settlement_name
        self.kingdom: str = kingdom
        self.tile_x: int = tile_x
        self.tile_y: int = tile_y
        self.owned: bool = True

        # Storage
        self.storage: List[Optional[Item]] = [None] * MAX_STORAGE_SLOTS

        # Furniture placed in the house
        self.furniture: List[Dict] = []
        # Each entry: {"type": str, "x": int, "y": int}

        # Rest bonus tracking
        self.last_rest_time: float = 0.0

    # -- storage --------------------------------------------------

    @property
    def storage_capacity(self) -> int:
        extra = sum(EXTRA_SLOTS_PER_CHEST
                    for f in self.furniture if f["type"] == "chest")
        return MAX_STORAGE_SLOTS + extra

    @property
    def used_slots(self) -> int:
        return sum(1 for s in self.storage if s is not None)

    @property
    def free_slots(self) -> int:
        return self.storage_capacity - self.used_slots

    def store_item(self, item: Item) -> bool:
        """Put an item into storage. Returns True on success."""
        # Expand storage list if furniture chests added capacity
        while len(self.storage) < self.storage_capacity:
            self.storage.append(None)

        for i, slot in enumerate(self.storage):
            if slot is None:
                self.storage[i] = item
                return True
        return False  # full

    def retrieve_item(self, index: int) -> Optional[Item]:
        """Take an item out of storage by slot index."""
        if 0 <= index < len(self.storage) and self.storage[index] is not None:
            item = self.storage[index]
            self.storage[index] = None
            return item
        return None

    def list_storage(self) -> List[Tuple[int, Item]]:
        """Return (index, item) for all occupied slots."""
        return [(i, s) for i, s in enumerate(self.storage) if s is not None]

    # -- furniture ------------------------------------------------

    def place_furniture(self, furniture_type: str,
                        x: int = 0, y: int = 0) -> Tuple[bool, str]:
        """Place a furniture item. Returns (success, message)."""
        if furniture_type not in FURNITURE_TYPES:
            return False, f"Unknown furniture type: {furniture_type}"

        self.furniture.append({"type": furniture_type, "x": x, "y": y})

        # If it's a chest, expand storage
        if furniture_type == "chest":
            for _ in range(EXTRA_SLOTS_PER_CHEST):
                self.storage.append(None)

        fdata = FURNITURE_TYPES[furniture_type]
        return True, f"Placed {fdata['name']} in your house."

    def remove_furniture(self, index: int) -> Tuple[bool, str]:
        """Remove a furniture piece by list index."""
        if 0 <= index < len(self.furniture):
            piece = self.furniture.pop(index)
            ftype = piece["type"]
            # Shrink storage if removing a chest (drop trailing empty slots)
            if ftype == "chest":
                to_remove = EXTRA_SLOTS_PER_CHEST
                while to_remove > 0 and self.storage and self.storage[-1] is None:
                    self.storage.pop()
                    to_remove -= 1
            return True, f"Removed {FURNITURE_TYPES.get(ftype, {}).get('name', ftype)}."
        return False, "Invalid furniture index."

    def list_furniture(self) -> List[Dict]:
        return list(self.furniture)

    # -- rest bonus -----------------------------------------------

    def rest(self, current_time: float) -> Tuple[bool, str]:
        """Sleep in your own house. Grants HP regen bonus.

        Returns (granted_bonus, message).
        """
        self.last_rest_time = current_time
        has_bed = any(f["type"] == "bed" for f in self.furniture)
        if has_bed:
            return True, ("You sleep in your own bed. "
                          "+20% HP regen for the next 8 hours.")
        return True, "You rest in your house. A bed would improve your sleep."

    def has_rest_bonus(self, current_time: float) -> bool:
        """True if the rest bonus is still active."""
        if self.last_rest_time <= 0:
            return False
        has_bed = any(f["type"] == "bed" for f in self.furniture)
        if not has_bed:
            return False
        return (current_time - self.last_rest_time) < REST_BONUS_DURATION

    def get_regen_multiplier(self, current_time: float) -> float:
        """Returns 1.0 normally, 1.2 if rest bonus is active."""
        if self.has_rest_bonus(current_time):
            return 1.0 + REST_BONUS_REGEN
        return 1.0

    # -- serialization --------------------------------------------

    def to_dict(self) -> Dict:
        storage_data = []
        for slot in self.storage:
            if slot is None:
                storage_data.append(None)
            else:
                storage_data.append({
                    "name": slot.name,
                    "kind": getattr(slot, "kind", "misc"),
                })
        return {
            "settlement": self.settlement,
            "kingdom": self.kingdom,
            "tile_x": self.tile_x,
            "tile_y": self.tile_y,
            "storage": storage_data,
            "furniture": self.furniture,
            "last_rest_time": self.last_rest_time,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "PlayerHouse":
        house = cls(
            settlement_name=data["settlement"],
            kingdom=data["kingdom"],
            tile_x=data.get("tile_x", 0),
            tile_y=data.get("tile_y", 0),
        )
        house.last_rest_time = data.get("last_rest_time", 0.0)
        house.furniture = data.get("furniture", [])

        # Rebuild storage
        house.storage = []
        for slot_data in data.get("storage", []):
            if slot_data is None:
                house.storage.append(None)
            else:
                house.storage.append(make_item(slot_data["name"]))
        # Pad to capacity
        while len(house.storage) < house.storage_capacity:
            house.storage.append(None)

        return house


# ================================================================
# HOUSING SYSTEM (main manager)
# ================================================================

class HousingSystem:
    """Manages all player-owned houses across the world."""

    def __init__(self):
        self.houses: Dict[str, PlayerHouse] = {}  # settlement_name -> house
        self.home_marker: Optional[str] = None     # settlement with "home" icon

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_house(self, settlement: str) -> Optional[PlayerHouse]:
        return self.houses.get(settlement)

    def has_house_in(self, settlement: str) -> bool:
        return settlement in self.houses

    def get_home_settlement(self) -> Optional[str]:
        return self.home_marker

    def get_all_houses(self) -> Dict[str, PlayerHouse]:
        return dict(self.houses)

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------

    def can_buy_house(self, settlement: str, player_gold: int,
                      rank_system=None, kingdom: str = "") -> Tuple[bool, str]:
        """Check if the player can acquire a house in this settlement."""
        if settlement in self.houses:
            return False, "You already own a house here."

        # Noble rank grants free housing
        if rank_system and kingdom:
            rank_idx = rank_system.get_rank_index(kingdom)
            if rank_idx >= 4:  # Noble or higher
                return True, "Your noble rank entitles you to a free house."

        if player_gold >= HOUSE_PURCHASE_COST:
            return True, f"Purchase a house for {HOUSE_PURCHASE_COST} gold."

        return False, (f"You need {HOUSE_PURCHASE_COST} gold or Noble rank "
                       f"to buy a house (you have {player_gold} gold).")

    def acquire_house(self, settlement: str, kingdom: str,
                      tile_x: int, tile_y: int,
                      player=None, rank_system=None,
                      free: bool = False) -> Tuple[bool, str]:
        """Buy or claim a house. Deducts gold unless free (rank grant).

        Returns (success, message).
        """
        if settlement in self.houses:
            return False, "You already own a house here."

        cost = 0
        if not free:
            # Check noble rank for free grant
            if rank_system and kingdom:
                rank_idx = rank_system.get_rank_index(kingdom)
                if rank_idx >= 4:
                    free = True

        if not free:
            cost = HOUSE_PURCHASE_COST
            if player is None or player.gold < cost:
                gold = player.gold if player else 0
                return False, f"Not enough gold ({gold}/{cost})."
            player.gold -= cost

        house = PlayerHouse(settlement, kingdom, tile_x, tile_y)
        # Start with a basic bed
        house.place_furniture("bed", x=2, y=2)
        self.houses[settlement] = house

        # Set as home if first house
        if self.home_marker is None:
            self.home_marker = settlement

        cost_msg = "free (noble privilege)" if free else f"{cost} gold"
        return True, (f"You now own a house in {settlement} ({cost_msg})! "
                      f"A bed has been placed for you.")

    def set_home(self, settlement: str) -> Tuple[bool, str]:
        """Set which house shows the home marker on the world map."""
        if settlement not in self.houses:
            return False, "You don't own a house there."
        self.home_marker = settlement
        return True, f"Home marker set to {settlement}."

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict:
        return {
            "houses": {k: h.to_dict() for k, h in self.houses.items()},
            "home_marker": self.home_marker,
        }

    def from_dict(self, data: Dict):
        self.home_marker = data.get("home_marker")
        self.houses.clear()
        for settlement, hdata in data.get("houses", {}).items():
            self.houses[settlement] = PlayerHouse.from_dict(hdata)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------

    def get_housing_report(self) -> str:
        if not self.houses:
            return "You don't own any houses."
        lines = ["Your Houses:"]
        for settlement, house in sorted(self.houses.items()):
            home = " [HOME]" if settlement == self.home_marker else ""
            fcount = len(house.furniture)
            lines.append(
                f"  {settlement}{home}: "
                f"{house.used_slots}/{house.storage_capacity} storage, "
                f"{fcount} furniture"
            )
        return "\n".join(lines)
