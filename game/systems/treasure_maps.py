"""Treasure map system — rare loot items that lead to buried treasure.

Treasure maps are found in dungeon chests (deep floors) or purchased
from merchants for 100 gold.  Each map stores a target world
coordinate.  When the player reaches that location and digs (E key),
they receive 50-200 gold plus a random artifact or rare equipment.

Usage:
    from game.systems.treasure_maps import TreasureMapManager
    mgr = TreasureMapManager(world_seed=42, world_w=10000, world_h=10000)

    # Player finds or buys a map
    tmap = mgr.create_map()

    # Check if player is at the dig site
    if mgr.can_dig(tmap, player_x, player_y):
        reward = mgr.dig(tmap)
        # reward = {"gold": 150, "items": [...]}
"""

import random
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# ================================================================
# CONSTANTS
# ================================================================

MAP_PURCHASE_COST = 100  # gold to buy from a merchant

# Loot tables
ARTIFACT_TABLE = [
    "ancient_crown", "dragon_scale", "phoenix_feather",
    "void_crystal", "sunstone", "moonstone",
    "runic_tablet", "golden_idol", "star_compass",
]

RARE_EQUIPMENT_TABLE = [
    "mithril_sword", "adamantine_shield", "enchanted_cloak",
    "boots_of_speed", "ring_of_protection", "amulet_of_strength",
    "staff_of_fire", "bow_of_wind", "helm_of_sight",
]

DIG_RADIUS = 3  # tiles from target to count as "close enough"


# ================================================================
# DATA CLASSES
# ================================================================

@dataclass
class TreasureMap:
    """A single treasure map pointing to a buried treasure location."""
    map_id: int
    target_x: int
    target_y: int
    gold_reward: int
    item_rewards: List[Dict] = field(default_factory=list)
    discovered: bool = False  # True once dug up
    quest_text: str = ""

    def to_dict(self) -> Dict:
        """Serialize for save/load."""
        return {
            "map_id": self.map_id,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "gold_reward": self.gold_reward,
            "item_rewards": self.item_rewards,
            "discovered": self.discovered,
            "quest_text": self.quest_text,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "TreasureMap":
        """Deserialize from save data."""
        return cls(
            map_id=data["map_id"],
            target_x=data["target_x"],
            target_y=data["target_y"],
            gold_reward=data["gold_reward"],
            item_rewards=data.get("item_rewards", []),
            discovered=data.get("discovered", False),
            quest_text=data.get("quest_text", ""),
        )


# ================================================================
# MANAGER
# ================================================================

class TreasureMapManager:
    """Creates and manages treasure maps for the game world."""

    def __init__(self, world_seed: int,
                 world_w: int = 10000, world_h: int = 10000):
        self.world_seed = world_seed
        self.world_w = world_w
        self.world_h = world_h
        self.rng = random.Random(world_seed)
        self._next_id = 1
        self.active_maps: List[TreasureMap] = []

    # ----------------------------------------------------------
    # Map creation
    # ----------------------------------------------------------

    def create_map(self, near_x: Optional[int] = None,
                   near_y: Optional[int] = None) -> TreasureMap:
        """Generate a new treasure map.

        If *near_x*/*near_y* are provided the treasure spawns within
        a reasonable distance (200-800 tiles); otherwise it is placed
        randomly on the world map.
        """
        map_id = self._next_id
        self._next_id += 1

        if near_x is not None and near_y is not None:
            dist = self.rng.randint(200, 800)
            angle = self.rng.uniform(0, 6.2832)
            import math
            tx = int(near_x + dist * math.cos(angle))
            ty = int(near_y + dist * math.sin(angle))
        else:
            tx = self.rng.randint(100, self.world_w - 100)
            ty = self.rng.randint(100, self.world_h - 100)

        # Clamp to world bounds
        tx = max(10, min(self.world_w - 10, tx))
        ty = max(10, min(self.world_h - 10, ty))

        gold = self.rng.randint(50, 200)
        items = self._roll_treasure_items()

        direction = _compass_direction(near_x or 0, near_y or 0, tx, ty)
        quest_text = (
            f"An old map marks buried treasure {direction} of here. "
            f"Dig at the marked location to claim the reward."
        )

        tmap = TreasureMap(
            map_id=map_id,
            target_x=tx, target_y=ty,
            gold_reward=gold,
            item_rewards=items,
            quest_text=quest_text,
        )
        self.active_maps.append(tmap)
        return tmap

    def _roll_treasure_items(self) -> List[Dict]:
        """Roll 1-2 rare items for the buried treasure."""
        items: List[Dict] = []

        # Always one artifact or rare equipment
        if self.rng.random() < 0.5:
            name = self.rng.choice(ARTIFACT_TABLE)
        else:
            name = self.rng.choice(RARE_EQUIPMENT_TABLE)
        items.append({"name": name, "quantity": 1})

        # 30 % chance of a second item
        if self.rng.random() < 0.3:
            name = self.rng.choice(RARE_EQUIPMENT_TABLE)
            items.append({"name": name, "quantity": 1})

        return items

    # ----------------------------------------------------------
    # Interaction
    # ----------------------------------------------------------

    def can_dig(self, tmap: TreasureMap,
                player_x: int, player_y: int) -> bool:
        """Return True if the player is close enough to dig."""
        if tmap.discovered:
            return False
        dx = abs(player_x - tmap.target_x)
        dy = abs(player_y - tmap.target_y)
        return dx <= DIG_RADIUS and dy <= DIG_RADIUS

    def dig(self, tmap: TreasureMap) -> Dict:
        """Dig up a treasure map. Returns reward dict."""
        if tmap.discovered:
            return {"gold": 0, "items": []}
        tmap.discovered = True
        return {
            "gold": tmap.gold_reward,
            "items": list(tmap.item_rewards),
        }

    # ----------------------------------------------------------
    # Query helpers
    # ----------------------------------------------------------

    def get_active(self) -> List[TreasureMap]:
        """Return all undiscovered maps."""
        return [m for m in self.active_maps if not m.discovered]

    def get_by_id(self, map_id: int) -> Optional[TreasureMap]:
        """Find a map by its ID."""
        for m in self.active_maps:
            if m.map_id == map_id:
                return m
        return None

    # ----------------------------------------------------------
    # Serialisation
    # ----------------------------------------------------------

    def to_dict(self) -> Dict:
        return {
            "next_id": self._next_id,
            "maps": [m.to_dict() for m in self.active_maps],
        }

    def load_dict(self, data: Dict) -> None:
        self._next_id = data.get("next_id", 1)
        self.active_maps = [
            TreasureMap.from_dict(d) for d in data.get("maps", [])
        ]


# ================================================================
# HELPERS
# ================================================================

def _compass_direction(fx: int, fy: int, tx: int, ty: int) -> str:
    """Return a compass direction string from (fx,fy) to (tx,ty)."""
    dx = tx - fx
    dy = ty - fy
    if abs(dx) > abs(dy) * 2:
        return "east" if dx > 0 else "west"
    if abs(dy) > abs(dx) * 2:
        return "south" if dy > 0 else "north"
    if dx > 0 and dy > 0:
        return "southeast"
    if dx > 0 and dy < 0:
        return "northeast"
    if dx < 0 and dy > 0:
        return "southwest"
    return "northwest"
