"""
Dynamic economy with supply/demand pricing, taxes, rent, and trade.

Every item has a base value. Actual price depends on:
- Local supply (more supply = cheaper)
- Local demand (more demand = expensive)
- Buyer/seller relationship and charisma
- Settlement wealth level

NPCs earn money from work, spend on food/rent/goods, pay taxes.
"""

import random
import math
from typing import Dict, List, Tuple, Optional
from game.core.items import ITEMS


class LocalMarket:
    """Economy for a single settlement."""
    def __init__(self, name: str, wealth: float = 1.0):
        self.name = name
        self.wealth = wealth  # 0.5 (poor hamlet) to 2.0 (rich city)
        self.supply: Dict[str, int] = {}   # item_name -> quantity available
        self.demand: Dict[str, float] = {}  # item_name -> demand multiplier
        self.tax_rate = 0.1  # 10% tax on transactions
        self.treasury = 0  # gold collected in taxes

    def get_price(self, item_name: str, buying: bool = True) -> int:
        """Get price for an item. Buying = player buys from shop, Selling = player sells."""
        base = ITEMS.get(item_name)
        if not base:
            return 1
        base_value = base.value

        # Supply/demand modifier
        supply = self.supply.get(item_name, 5)
        demand = self.demand.get(item_name, 1.0)

        if supply > 10:
            price_mult = 0.7  # surplus = cheap
        elif supply > 5:
            price_mult = 0.9
        elif supply > 2:
            price_mult = 1.0
        elif supply > 0:
            price_mult = 1.3  # scarce = expensive
        else:
            price_mult = 1.8  # out of stock = very expensive

        price = int(base_value * price_mult * demand * self.wealth)

        if not buying:
            price = int(price * 0.5)  # sell price is half buy price

        return max(1, price)

    def buy(self, item_name: str) -> int:
        """Record a purchase, reduce supply. Returns price paid."""
        price = self.get_price(item_name, buying=True)
        self.supply[item_name] = max(0, self.supply.get(item_name, 5) - 1)
        tax = int(price * self.tax_rate)
        self.treasury += tax
        return price

    def sell(self, item_name: str) -> int:
        """Record a sale, increase supply. Returns gold received."""
        price = self.get_price(item_name, buying=False)
        self.supply[item_name] = self.supply.get(item_name, 5) + 1
        return price

    def restock(self, dt: float):
        """Slowly restock toward baseline supply."""
        for item_name in list(self.supply.keys()):
            baseline = 5
            current = self.supply[item_name]
            if current < baseline:
                self.supply[item_name] = min(baseline, current + 1)


class EconomySystem:
    """Global economy managing all local markets."""

    def __init__(self):
        self.markets: Dict[str, LocalMarket] = {}
        self.global_tax_rate = 0.1
        self.restock_timer = 0.0

    def register_settlement(self, name: str, kind: str):
        wealth = {"hamlet": 0.6, "village": 0.8, "town": 1.2, "city": 1.5, "castle": 1.8}.get(kind, 1.0)
        self.markets[name] = LocalMarket(name, wealth)

        # Stock based on settlement type
        market = self.markets[name]
        if kind in ("town", "city"):
            for item in ["Bread", "Water Flask", "Health Potion", "Iron Sword", "Leather Armor"]:
                market.supply[item] = random.randint(3, 10)
            market.demand["Iron Ore"] = 1.5
            market.demand["Wheat"] = 1.3
        elif kind == "village":
            for item in ["Bread", "Water Flask", "Seeds", "Herbs"]:
                market.supply[item] = random.randint(2, 8)

    def get_market(self, settlement_name: str) -> Optional[LocalMarket]:
        return self.markets.get(settlement_name)

    def update(self, dt: float):
        self.restock_timer += dt
        if self.restock_timer > 60.0:  # restock every minute
            self.restock_timer = 0.0
            for market in self.markets.values():
                market.restock(dt)


# ================================================================
# NPC FINANCIAL OBLIGATIONS
# ================================================================

# Monthly costs by class (gold per game-day)
DAILY_COSTS = {
    "rent": 0.5,       # housing rent
    "food": 0.3,       # daily food budget
    "tax": 0.2,        # taxes to local lord
    "upkeep": 0.1,     # equipment maintenance
}

# Income rates per class (gold earned per work period)
CLASS_INCOME = {
    "Fighter": 3, "Paladin": 4, "Barbarian": 2, "Ranger": 3,
    "Wizard": 4, "Sorcerer": 3, "Warlock": 3,
    "Cleric": 3, "Druid": 2,
    "Rogue": 5, "Bard": 4, "Monk": 1,
}


def apply_daily_costs(npc, day_fraction: float):
    """Deduct daily living costs from NPC gold."""
    if day_fraction < 0.01:  # once per day
        total_cost = sum(DAILY_COSTS.values())
        npc.npc_gold = max(0, npc.npc_gold - total_cost)

        # If broke, NPC becomes desperate
        if npc.npc_gold <= 0:
            npc.current_goal = "earn money urgently"
            # Only add memory if not already recorded recently
            if not any("need money" in m.get("text", "") for m in npc.memories[-5:]):
                npc.add_memory("economy", "I'm broke and need money!", 2)
