"""
Location-based production costs and price-driven trade.

Each good has a base production cost.  The actual cost at a settlement
depends on:
  1. Raw material availability (local production vs. import)
  2. Workforce (skilled craftsmen present)
  3. Infrastructure (right buildings: forge, mill, tannery)
  4. Distance from source (transport markup per tile of distance)

Price boards are maintained per settlement and updated daily so that
merchants can find profitable trade routes.
"""

import math
from typing import Dict, List, Optional, Tuple

from game.world.specializations import SPECIALIZATION_ECONOMY
from game.data.supply_chains import SUPPLY_CHAINS, RAW_MATERIAL_SOURCES


# ================================================================
# BASE PRODUCTION COSTS
# ================================================================

PRODUCTION_COST_BASE: Dict[str, int] = {
    # Food
    "Bread": 1,
    "Cheese": 2,
    "Fish": 1,
    "Ale": 2,
    "Elven Cordial": 8,
    "Wine": 4,
    "Mead": 3,
    "Cooked Meat": 1,
    "Vegetable Stew": 2,
    "Berry Pie": 2,
    "Mushroom Soup": 1,
    "Meat Pie": 2,
    "Honey Cake": 3,
    "Salted Fish": 1,
    "Smoked Fish": 2,
    "Trail Rations": 2,
    "Feast Platter": 8,
    "Omelette": 1,
    "Butter": 1,
    "Cheese Wheel": 4,
    "Bacon": 2,
    "Sausage": 2,
    "Flour": 1,
    "Dwarven Stout": 5,

    # Raw materials
    "Wood": 1,
    "Iron Ore": 2,
    "Copper Ore": 2,
    "Stone": 2,
    "Leather": 2,
    "Wool": 1,
    "Wheat": 1,
    "Flax": 1,
    "Herbs": 1,
    "Clay": 1,
    "Salt": 1,
    "Raw Meat": 1,
    "Milk": 1,
    "Eggs": 1,
    "Honey": 2,
    "Resin": 2,
    "Gold Nugget": 5,

    # Processed materials
    "Iron Ingot": 3,
    "Copper Ingot": 3,
    "Bronze Ingot": 4,
    "Steel Ingot": 6,
    "Gold Bar": 8,
    "Planks": 2,
    "Linen": 2,
    "Wool Cloth": 2,
    "Dyed Cloth": 4,
    "Tanned Hide": 2,
    "Rope": 2,

    # Crafted goods
    "Iron Sword": 5,
    "Steel Sword": 10,
    "Wooden Sword": 2,
    "Hunting Bow": 4,
    "Arrows": 1,
    "Leather Armor": 6,
    "Chain Mail": 8,
    "Iron Armor": 10,
    "Plate Armor": 15,
    "Health Potion": 4,
    "Greater Health Potion": 8,
    "Antidote": 3,
    "Pickaxe": 3,
    "Axe": 3,
    "Hammer": 2,
    "Hoe": 2,
    "Nails": 1,

    # Luxury / rare
    "Silk": 15,
    "Ruby": 12,
    "Sapphire": 12,
    "Emerald": 15,
    "Diamond": 25,
    "Gold Ring": 10,
    "Ruby Ring": 18,
    "Sapphire Amulet": 20,
    "Emerald Pendant": 22,
    "Diamond Crown": 40,
    "Enchanted Ring": 30,
    "Enchanted Sword": 25,
    "Enchanted Staff": 20,

    # Books & scrolls
    "Book": 3,
    "Scroll of Healing": 5,
    "Scroll of Fire": 6,
    "Spellbook": 10,
    "Map": 3,

    # Foreign trade goods
    "Spices": 10,
    "Exotic Fruits": 8,
    "Pearls": 20,
    "Rum": 6,
    "Arcane Tomes": 25,
    "Jade": 18,
    "Ivory": 22,
    "Incense": 5,
}

# Default cost for goods not listed
_DEFAULT_COST = 5


# ================================================================
# KINGDOM SPECIALTIES — racial bonuses
# ================================================================

KINGDOM_SPECIALTIES: Dict[str, Dict[str, list]] = {
    "Human": {
        "produces": ["Bread", "Wheat", "Ale", "Leather Armor", "Iron Sword"],
        "signature": [],
    },
    "Elf": {
        "produces": ["Elven Cordial", "Herbs", "Hunting Bow", "Linen", "Book"],
        "signature": ["Elven Cordial", "Enchanted Staff"],
    },
    "Dwarf": {
        "produces": ["Iron Ingot", "Steel Ingot", "Iron Sword", "Plate Armor",
                      "Dwarven Stout", "Stone"],
        "signature": ["Dwarven Stout", "Steel Sword", "Plate Armor"],
    },
    "Orc": {
        "produces": ["Raw Meat", "Leather", "Iron Sword", "Weapons"],
        "signature": [],
    },
    "Goblin": {
        "produces": ["Arrows", "Nails", "Lockpick"],
        "signature": [],
    },
    "Undead": {
        "produces": ["Poison Vial", "Fire Oil", "Scroll of Fire"],
        "signature": ["Poison Vial"],
    },
}


# ================================================================
# TRANSPORT COSTS
# ================================================================

TRANSPORT_COST_PER_100_TILES = {
    "foot": 2.0,
    "donkey": 1.0,
    "cart": 0.5,
    "wagon": 0.3,
    "ship": 0.2,
}


def calculate_transport_cost(from_x: float, from_y: float,
                              to_x: float, to_y: float,
                              quantity: int = 1,
                              vehicle: str = "cart") -> int:
    """Return total transport cost for *quantity* units between two points."""
    dist = math.sqrt((to_x - from_x) ** 2 + (to_y - from_y) ** 2)
    per_unit = TRANSPORT_COST_PER_100_TILES.get(vehicle, 1.0) * (dist / 100.0)
    return max(0, int(quantity * per_unit))


# ================================================================
# ALL TRADEABLE GOODS (union of everything in the cost table)
# ================================================================

ALL_TRADEABLE_GOODS: List[str] = sorted(PRODUCTION_COST_BASE.keys())


# ================================================================
# PRICE CALCULATION
# ================================================================

def _find_kingdom(settlement_name: str, kingdoms: list) -> Optional[dict]:
    """Look up the kingdom a settlement belongs to."""
    for k in kingdoms:
        territory = k.get("territory_settlements", [])
        if settlement_name in territory:
            return k
    return None


def _settlement_has_crafter(good: str, settlement_plan) -> bool:
    """Check if the settlement has the profession needed to produce *good*."""
    chain = SUPPLY_CHAINS.get(good)
    if not chain:
        # Raw material -- check if gatherer profession is present
        raw = RAW_MATERIAL_SOURCES.get(good)
        if not raw:
            return False
        needed = raw.get("gatherer", "")
    else:
        needed = chain.get("crafter", "")

    if not needed:
        return False

    # Check spawns
    for spawn in getattr(settlement_plan, 'npc_spawns', []):
        cls = spawn.get("class", "")
        if cls == needed:
            return True
    return False


def _settlement_has_building(good: str, settlement_plan) -> bool:
    """Check if settlement has the right workstation building for *good*."""
    chain = SUPPLY_CHAINS.get(good)
    if not chain:
        return True  # raw materials don't need buildings
    workstation = chain.get("workstation")
    if not workstation:
        return True

    # Map workstation names to building kinds
    ws_to_building = {
        "forge": ("blacksmith", "forge"),
        "kitchen": ("bakery", "tavern", "house", "cottage"),
        "brewery": ("tavern", "brewery"),
        "workshop": ("workshop", "barn"),
        "loom": ("workshop",),
        "alchemy": ("workshop", "library"),
        "jeweler": ("workshop", "shop"),
        "tannery": ("workshop",),
        "enchanter": ("library", "temple"),
        "pottery": ("workshop",),
        "cartography": ("library", "workshop"),
        "dye_house": ("workshop",),
        "glassworks": ("workshop", "forge"),
    }
    building_kinds = ws_to_building.get(workstation, ())
    for b in getattr(settlement_plan, 'buildings', []):
        if b.get("kind", "") in building_kinds:
            return True
    return False


def calculate_local_price(good: str, settlement_plan, world_effects,
                           plan) -> int:
    """Calculate the price of a good at a specific settlement.

    Price = base_cost * availability_multiplier * demand_multiplier
    """
    base = PRODUCTION_COST_BASE.get(good, _DEFAULT_COST)

    # --- Availability ---
    stores = world_effects.get_settlement_stores(settlement_plan.name)
    spec_economy = SPECIALIZATION_ECONOMY.get(
        getattr(settlement_plan, 'specialization', 'general'), {})
    local_products = spec_economy.get("produces", [])

    # Normalise: SPECIALIZATION_ECONOMY uses lowercase short names
    # whereas the cost table uses item names.  Map common terms.
    _SPEC_GOOD_MAP = {
        "fish": ("Fish", "Salted Fish", "Smoked Fish"),
        "salt": ("Salt",),
        "grain": ("Wheat", "Flour", "Bread"),
        "timber": ("Wood", "Planks"),
        "ore": ("Iron Ore", "Copper Ore"),
        "stone": ("Stone",),
        "gems": ("Raw Ruby", "Raw Sapphire", "Raw Emerald", "Raw Diamond"),
        "metal_ingots": ("Iron Ingot", "Copper Ingot", "Bronze Ingot",
                          "Steel Ingot"),
        "charcoal": ("Wood",),
        "game_meat": ("Raw Meat",),
        "planks": ("Planks",),
        "livestock": ("Raw Meat", "Milk", "Eggs", "Wool"),
        "dairy": ("Milk", "Cheese", "Butter", "Cheese Wheel"),
        "bread": ("Bread",),
        "wool": ("Wool", "Wool Cloth"),
        "herbs": ("Herbs",),
        "peat": (),
        "medicine": ("Health Potion", "Antidote", "Healing Salve"),
        "water": (),
        "dates": (),
        "rope": ("Rope",),
        "ships": ("Boat Hull",),
        "trade_goods": (),
        "trade_services": (),
        "lodging": (),
        "military_services": (),
        "customs_revenue": (),
        "governance": (),
        "culture": (),
        "luxury_goods": ("Silk", "Gold Ring", "Ruby Ring"),
        "mixed": (),
        "security": (),
        "customs_goods": (),
        "laws": (),
        "everything": (),
    }

    is_local = False
    for prod_key in local_products:
        mapped = _SPEC_GOOD_MAP.get(prod_key, ())
        if good in mapped:
            is_local = True
            break

    stock = stores.get(good, 0)

    if is_local:
        availability = 0.6
    elif stock > 20:
        availability = 0.8
    elif stock > 5:
        availability = 1.0
    elif stock > 0:
        availability = 1.5
    else:
        availability = 2.5

    # --- Workforce modifier ---
    if good in SUPPLY_CHAINS or good in RAW_MATERIAL_SOURCES:
        if not _settlement_has_crafter(good, settlement_plan):
            availability *= 1.5  # no crafter = harder to get

    # --- Infrastructure modifier ---
    if good in SUPPLY_CHAINS:
        if not _settlement_has_building(good, settlement_plan):
            availability *= 1.3

    # --- Demand based on population ---
    pop = getattr(settlement_plan, 'population', 50)
    demand = 1.0
    if pop > 500:
        demand = 1.2
    elif pop > 200:
        demand = 1.1
    elif pop < 50:
        demand = 0.9

    # --- Kingdom racial bonus ---
    kingdoms = getattr(plan, 'kingdoms', [])
    kingdom = _find_kingdom(settlement_plan.name, kingdoms)
    if kingdom:
        race = kingdom.get("race", "")
        race_goods = KINGDOM_SPECIALTIES.get(race, {})
        if good in race_goods.get("produces", []):
            availability *= 0.8
        if good in race_goods.get("signature", []):
            availability *= 0.7

    return max(1, int(base * availability * demand))


# ================================================================
# SETTLEMENT PRICE BOARD
# ================================================================

class SettlementPriceBoard:
    """Tracks current prices for all goods at a settlement."""

    def __init__(self, settlement_name: str, settlement_plan,
                 world_effects, plan):
        self.settlement_name = settlement_name
        self.prices: Dict[str, int] = {}
        self._settlement_plan = settlement_plan
        self._plan = plan
        self.update(settlement_plan, world_effects, plan)

    # ---- core API ---------------------------------------------------

    def update(self, settlement_plan, world_effects, plan):
        """Recalculate all prices based on current supply/demand."""
        self._settlement_plan = settlement_plan
        self._plan = plan
        for good in ALL_TRADEABLE_GOODS:
            self.prices[good] = calculate_local_price(
                good, settlement_plan, world_effects, plan)

    def get_price(self, good: str) -> int:
        return self.prices.get(good, _DEFAULT_COST)

    # ---- trade analysis ---------------------------------------------

    def get_profitable_imports(
        self, other_board: "SettlementPriceBoard"
    ) -> List[Tuple[str, int, int, int]]:
        """Find goods cheaper at *other_board*'s settlement.

        Returns list of (good, buy_price, sell_price, margin) sorted by
        highest margin first.
        """
        opportunities: List[Tuple[str, int, int, int]] = []
        for good, local_price in self.prices.items():
            other_price = other_board.get_price(good)
            margin = local_price - other_price
            if margin > 2:
                opportunities.append((good, other_price, local_price, margin))
        opportunities.sort(key=lambda x: -x[3])
        return opportunities

    # ---- dynamic supply/demand adjustments --------------------------

    def record_purchase(self, good: str):
        """After a buy, nudge the price up (reduced supply)."""
        cur = self.prices.get(good, _DEFAULT_COST)
        self.prices[good] = max(1, int(cur * 1.05))

    def record_sale(self, good: str):
        """After a sell, nudge the price down (increased supply)."""
        cur = self.prices.get(good, _DEFAULT_COST)
        self.prices[good] = max(1, int(cur * 0.95))

    # ---- gossip helpers ---------------------------------------------

    def get_expensive_goods(self, threshold: int = 10
                            ) -> List[Tuple[str, int]]:
        return [(g, p) for g, p in self.prices.items()
                if p > threshold and g != "gold"]

    def get_cheap_goods(self, threshold: int = 3
                        ) -> List[Tuple[str, int]]:
        return [(g, p) for g, p in self.prices.items()
                if p < threshold and g != "gold"]


# ================================================================
# MARKET TRANSACTION HELPERS
# ================================================================

def buy_from_market(world_effects, settlement_name: str,
                    price_board: SettlementPriceBoard,
                    buyer_npc, good: str, quantity: int) -> int:
    """Buyer purchases *quantity* of *good* from the settlement market.

    Deducts gold from buyer, adds gold to settlement treasury, removes
    goods from settlement stores, nudges the price upward.
    Returns the number of units actually bought.
    """
    stores = world_effects.get_stores_ref(settlement_name)
    available = stores.get(good, 0)
    actual = min(quantity, available)
    if actual <= 0:
        return 0

    price = price_board.get_price(good)
    total_cost = actual * price

    buyer_gold = getattr(buyer_npc, 'npc_gold', 0)
    if buyer_gold < price:
        return 0  # can't even afford one unit

    affordable = buyer_gold // price
    actual = min(actual, affordable)
    total_cost = actual * price

    stores[good] = stores.get(good, 0) - actual
    buyer_npc.npc_gold = buyer_gold - total_cost
    stores["gold"] = stores.get("gold", 0) + total_cost

    price_board.record_purchase(good)
    return actual


def sell_to_market(world_effects, settlement_name: str,
                   price_board: SettlementPriceBoard,
                   seller_npc, good: str, quantity: int) -> int:
    """Seller sells *quantity* of *good* to the settlement market.

    Adds goods to settlement stores, pays seller from settlement gold,
    nudges the price downward.
    Returns the number of units actually sold.
    """
    stores = world_effects.get_stores_ref(settlement_name)
    buy_price = max(1, price_board.get_price(good) - 1)
    total_payment = quantity * buy_price

    gold_available = stores.get("gold", 0)
    actual_payment = min(total_payment, gold_available)
    actual_qty = actual_payment // max(1, buy_price) if buy_price > 0 else 0
    actual_qty = min(actual_qty, quantity)

    if actual_qty <= 0:
        return 0

    stores[good] = stores.get(good, 0) + actual_qty
    payment = actual_qty * buy_price
    stores["gold"] = stores.get("gold", 0) - payment
    seller_npc.npc_gold = getattr(seller_npc, 'npc_gold', 0) + payment

    price_board.record_sale(good)
    return actual_qty


# ================================================================
# NPC PRICE GOSSIP
# ================================================================

def get_price_gossip(settlement_name: str,
                     price_board: SettlementPriceBoard) -> List[str]:
    """Generate price-related conversation topics for NPCs."""
    topics: List[str] = []

    expensive = price_board.get_expensive_goods(10)
    if expensive:
        g, p = max(expensive, key=lambda x: x[1])
        topics.append(f"{g} costs {p} gold here -- outrageous!")

    cheap = price_board.get_cheap_goods(3)
    if cheap:
        g, p = min(cheap, key=lambda x: x[1])
        topics.append(f"At least {g} is cheap around here -- only {p} gold.")

    return topics
