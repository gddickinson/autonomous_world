"""
World Economy — macro-economic simulation for Aethermoor and beyond.

Incorporates ideas from the economic_simulation project:
- Tatonnement price discovery with sticky prices
- Cobb-Douglas production for settlements
- Supply/demand driven inter-settlement and inter-continental trade
- Population-driven labor markets
- Investment, capital accumulation, and depreciation
- Government taxation and spending
- Seasonal and resource-based production modifiers

This replaces the simple fixed-price economy with a living one where:
- Prices reflect actual supply and demand
- Settlements specialize based on resources and geography
- Trade caravans respond to price differentials
- Foreign continents have their own macro-economies that interact via trade
- War, plague, and seasons create economic shocks

Runs alongside the abstract simulation layer — detailed near the player,
statistical everywhere else, but economy flows globally.
"""

import random
import math
from typing import Dict, List, Optional, Tuple


# ================================================================
# GOODS CATEGORIES — what the economy tracks
# ================================================================

TRADE_GOODS = {
    # Good: {base_price, category, perishable, weight}
    "food":       {"base_price": 3.0,  "category": "basic",    "perishable": True,  "weight": 1.0},
    "water":      {"base_price": 1.0,  "category": "basic",    "perishable": False, "weight": 2.0},
    "timber":     {"base_price": 4.0,  "category": "raw",      "perishable": False, "weight": 3.0},
    "stone":      {"base_price": 5.0,  "category": "raw",      "perishable": False, "weight": 5.0},
    "iron_ore":   {"base_price": 8.0,  "category": "raw",      "perishable": False, "weight": 4.0},
    "herbs":      {"base_price": 6.0,  "category": "raw",      "perishable": True,  "weight": 0.5},
    "wool":       {"base_price": 4.0,  "category": "raw",      "perishable": False, "weight": 1.0},
    "leather":    {"base_price": 8.0,  "category": "processed", "perishable": False, "weight": 1.0},
    "iron_goods": {"base_price": 20.0, "category": "manufactured", "perishable": False, "weight": 3.0},
    "weapons":    {"base_price": 40.0, "category": "manufactured", "perishable": False, "weight": 2.0},
    "armor":      {"base_price": 60.0, "category": "manufactured", "perishable": False, "weight": 5.0},
    "ale":        {"base_price": 4.0,  "category": "luxury",   "perishable": True,  "weight": 2.0},
    "wine":       {"base_price": 10.0, "category": "luxury",   "perishable": False, "weight": 2.0},
    "gems":       {"base_price": 50.0, "category": "luxury",   "perishable": False, "weight": 0.2},
    "spices":     {"base_price": 30.0, "category": "luxury",   "perishable": False, "weight": 0.3},
    "silk":       {"base_price": 25.0, "category": "luxury",   "perishable": False, "weight": 0.5},
    "books":      {"base_price": 15.0, "category": "luxury",   "perishable": False, "weight": 1.0},
    "potions":    {"base_price": 12.0, "category": "manufactured", "perishable": True, "weight": 0.5},
    "salt":       {"base_price": 3.0,  "category": "basic",    "perishable": False, "weight": 1.0},
    "cloth":      {"base_price": 6.0,  "category": "processed", "perishable": False, "weight": 1.0},
}


# ================================================================
# SETTLEMENT PRODUCTION PROFILES — what each type produces
# ================================================================

PRODUCTION_PROFILES = {
    "hamlet": {
        "produces": {"food": 3.0, "timber": 1.0, "herbs": 0.5},
        "consumes": {"iron_goods": 0.2, "salt": 0.3, "cloth": 0.2},
        "labor_force": 0.6,  # fraction of population that works
        "base_productivity": 0.8,
    },
    "village": {
        "produces": {"food": 5.0, "timber": 2.0, "wool": 1.0, "herbs": 1.0, "leather": 0.5},
        "consumes": {"iron_goods": 0.5, "weapons": 0.1, "salt": 0.5, "ale": 0.3, "cloth": 0.5},
        "labor_force": 0.65,
        "base_productivity": 1.0,
    },
    "town": {
        "produces": {"food": 3.0, "iron_goods": 2.0, "cloth": 2.0, "ale": 1.5,
                     "leather": 1.0, "potions": 0.5, "weapons": 0.5},
        "consumes": {"food": 2.0, "iron_ore": 1.5, "timber": 1.0, "herbs": 0.8,
                     "wool": 1.0, "wine": 0.3, "books": 0.2},
        "labor_force": 0.7,
        "base_productivity": 1.2,
    },
    "city": {
        "produces": {"iron_goods": 3.0, "weapons": 2.0, "armor": 1.0, "cloth": 2.0,
                     "potions": 1.0, "books": 0.5, "ale": 2.0, "wine": 0.5},
        "consumes": {"food": 5.0, "iron_ore": 3.0, "timber": 2.0, "herbs": 1.5,
                     "wool": 1.5, "leather": 1.0, "gems": 0.3, "spices": 0.2, "silk": 0.2},
        "labor_force": 0.75,
        "base_productivity": 1.5,
    },
    "castle": {
        "produces": {"weapons": 1.0, "armor": 0.5},
        "consumes": {"food": 3.0, "iron_ore": 2.0, "timber": 1.0, "ale": 1.0,
                     "weapons": 0.5, "armor": 0.3},
        "labor_force": 0.5,
        "base_productivity": 1.0,
    },
}


# ================================================================
# REGIONAL RESOURCE ENDOWMENTS — what's naturally available
# ================================================================

REGIONAL_RESOURCES = {
    "heartlands":     {"food": 2.0, "timber": 1.0, "wool": 1.5, "stone": 0.5, "herbs": 0.5},
    "silverwood":     {"timber": 3.0, "herbs": 3.0, "food": 0.5},
    "iron_peaks":     {"iron_ore": 3.0, "stone": 3.0, "gems": 1.0, "food": 0.3},
    "eastern_wastes": {"stone": 1.0, "leather": 2.0, "iron_ore": 0.5, "food": 0.5},
    "azure_coast":    {"food": 2.0, "salt": 3.0, "fish": 2.0},
}


# ================================================================
# SETTLEMENT ECONOMY — one per settlement in the game world
# ================================================================

class SettlementEconomy:
    """Economic state of a single settlement.

    Uses Cobb-Douglas production: Output = Productivity * Labor^0.6 * Capital^0.3
    Prices adjust via tatonnement with sticky prices.
    """

    def __init__(self, name: str, kind: str, region: str, population: int):
        self.name = name
        self.kind = kind
        self.region = region
        self.population = max(5, population)

        profile = PRODUCTION_PROFILES.get(kind, PRODUCTION_PROFILES["village"])
        region_res = REGIONAL_RESOURCES.get(region, {})

        # Market prices (start at base, adjust with supply/demand)
        self.prices: Dict[str, float] = {g: d["base_price"] for g, d in TRADE_GOODS.items()}

        # Stockpiles — how much of each good is available
        self.stockpile: Dict[str, float] = {g: 10.0 for g in TRADE_GOODS}

        # Production capacity (units/day, modified by resources and labor)
        self.production: Dict[str, float] = {}
        for good, rate in profile["produces"].items():
            resource_bonus = region_res.get(good, 1.0)
            self.production[good] = rate * resource_bonus

        # Consumption needs (units/day)
        self.consumption: Dict[str, float] = dict(profile["consumes"])
        # Everyone needs food
        self.consumption.setdefault("food", self.population * 0.1)

        # Capital stock (accumulated wealth invested in infrastructure)
        self.capital = 50.0 + population * 2.0
        self.productivity = profile["base_productivity"]
        self.labor_force = profile["labor_force"]

        # Treasury (tax revenue)
        self.treasury = population * 3.0
        self.tax_rate = 0.10
        self.wage_level = 2.0

        # Trade balance tracking
        self.exports_value = 0.0
        self.imports_value = 0.0

        # History (for trend analysis)
        self.gdp_history: List[float] = []
        self.price_history: Dict[str, List[float]] = {g: [] for g in TRADE_GOODS}

    def calc_output(self, good: str) -> float:
        """Calculate production output using Cobb-Douglas."""
        base_rate = self.production.get(good, 0)
        if base_rate <= 0:
            return 0

        labor = self.population * self.labor_force
        capital = max(1.0, self.capital)

        # Y = A * L^0.6 * K^0.3 * base_rate
        output = self.productivity * (labor ** 0.6) * (capital ** 0.3) * base_rate * 0.02
        return max(0, output)

    def calc_demand(self, good: str) -> float:
        """Calculate demand for a good based on population and needs."""
        base = self.consumption.get(good, 0)
        # Population-scaled demand
        pop_factor = self.population / 20.0
        # Wealth effect: richer settlements demand more luxuries
        wealth_factor = 1.0
        if TRADE_GOODS.get(good, {}).get("category") == "luxury":
            wealth_factor = min(2.0, self.treasury / (self.population * 5 + 1))
        return base * pop_factor * wealth_factor

    def update_production(self, dt: float, season: str = "spring",
                          solar_intensity: float = 0.5):
        """Produce goods, consume needs, and update prices."""
        day_fraction = dt / 600.0  # normalize to day fraction

        # Seasonal modifier (affects food and raw materials)
        season_mod = {"spring": 1.2, "summer": 1.5, "autumn": 0.8, "winter": 0.3}
        food_season = season_mod.get(season, 1.0)

        # Produce goods
        gdp = 0.0
        for good in self.production:
            output = self.calc_output(good) * day_fraction
            # Seasonal effect on agricultural goods
            if good in ("food", "herbs", "wool"):
                output *= food_season
            # Solar intensity affects all production slightly
            output *= (0.7 + 0.3 * solar_intensity)
            self.stockpile[good] = self.stockpile.get(good, 0) + output
            gdp += output * self.prices.get(good, 1.0)

        # Consume needs
        for good, rate in self.consumption.items():
            demand = self.calc_demand(good) * day_fraction
            consumed = min(demand, self.stockpile.get(good, 0))
            self.stockpile[good] = max(0, self.stockpile.get(good, 0) - consumed)

        # Perishable goods decay
        for good, info in TRADE_GOODS.items():
            if info["perishable"]:
                self.stockpile[good] = self.stockpile.get(good, 0) * (1 - 0.02 * day_fraction)

        # Capital depreciation (5% per game-day, scaled to dt)
        self.capital *= (1 - 0.0005 * day_fraction)

        # Investment: reinvest portion of treasury
        if self.treasury > self.population * 2:
            invest = min(self.treasury * 0.02, 1.0) * day_fraction
            self.capital += invest
            self.treasury -= invest

        # Wages
        labor = self.population * self.labor_force
        wage_bill = labor * self.wage_level * day_fraction
        self.treasury -= wage_bill

        # Tax collection
        tax_income = gdp * self.tax_rate * day_fraction
        self.treasury += tax_income
        self.treasury = max(0, self.treasury)

        # Record GDP
        if len(self.gdp_history) < 100:
            self.gdp_history.append(gdp)
        else:
            self.gdp_history.pop(0)
            self.gdp_history.append(gdp)

    def update_prices(self, dt: float):
        """Tatonnement price adjustment — prices move toward supply/demand equilibrium."""
        day_fraction = dt / 600.0
        stickiness = 0.85  # prices are sticky (85% old, 15% implied)
        adjustment_speed = 0.08

        for good in TRADE_GOODS:
            supply = self.stockpile.get(good, 0)
            demand = self.calc_demand(good)
            current_price = self.prices[good]

            if supply <= 0.01 and demand > 0:
                # No supply, high demand → price rises
                implied = current_price * 1.3
            elif demand <= 0.01:
                # No demand → price drops slowly
                implied = current_price * 0.95
            else:
                # Power-law price adjustment from economic_simulation
                ratio = demand / max(0.01, supply)
                implied = current_price * (ratio ** 0.3)

            # Sticky blending
            target = stickiness * current_price + (1 - stickiness) * implied
            price_change = adjustment_speed * (target - current_price) * day_fraction * 10
            new_price = current_price + price_change

            # Clamp
            base = TRADE_GOODS[good]["base_price"]
            self.prices[good] = max(base * 0.2, min(base * 5.0, new_price))

            # Record price history
            if good in self.price_history:
                hist = self.price_history[good]
                if len(hist) >= 50:
                    hist.pop(0)
                hist.append(self.prices[good])

    def get_export_surplus(self) -> Dict[str, float]:
        """What this settlement can export (surplus above needs)."""
        surplus = {}
        for good in TRADE_GOODS:
            stock = self.stockpile.get(good, 0)
            need = self.calc_demand(good) * 3  # keep 3 days of buffer
            if stock > need + 1:
                surplus[good] = stock - need
        return surplus

    def get_import_needs(self) -> Dict[str, float]:
        """What this settlement needs to import (deficit below needs)."""
        needs = {}
        for good in TRADE_GOODS:
            stock = self.stockpile.get(good, 0)
            demand = self.calc_demand(good) * 3
            if stock < demand * 0.5 and demand > 0.1:
                needs[good] = demand - stock
        return needs

    def get_price(self, good: str) -> float:
        """Get current market price for a good."""
        return self.prices.get(good, TRADE_GOODS.get(good, {}).get("base_price", 10.0))

    @property
    def prosperity(self) -> float:
        """0-1 prosperity score."""
        food = min(1.0, self.stockpile.get("food", 0) / max(1, self.population * 0.5))
        wealth = min(1.0, self.treasury / max(1, self.population * 5))
        return (food + wealth) / 2

    @property
    def gdp(self) -> float:
        """Recent GDP."""
        return self.gdp_history[-1] if self.gdp_history else 0


# ================================================================
# CONTINENTAL ECONOMY — macro-level for foreign continents
# ================================================================

class ContinentalEconomy:
    """Macro-economic model for a foreign continent.

    These don't have individual settlements simulated — just aggregate
    supply, demand, prices, and trade capacity. They participate in
    inter-continental trade via the world market.
    """

    def __init__(self, name: str, population: float, development: float,
                 specialization: Dict[str, float] = None,
                 trade_openness: float = 0.5):
        self.name = name
        self.population = population  # in millions
        self.development = development  # 0-1, affects productivity
        self.trade_openness = trade_openness

        # What this continent produces efficiently
        self.specialization = specialization or {}

        # Aggregate prices (world-facing)
        self.prices: Dict[str, float] = {g: d["base_price"] for g, d in TRADE_GOODS.items()}
        for good, bonus in self.specialization.items():
            if good in self.prices:
                self.prices[good] *= max(0.3, 1.0 - bonus * 0.3)  # cheaper if specialized

        # Trade state
        self.export_capacity: Dict[str, float] = {}
        self.import_demand: Dict[str, float] = {}
        self.gdp = population * development * 100
        self.treasury = population * development * 50
        self.trade_balance = 0.0

    def update(self, dt: float, season: str = "spring"):
        """Simple aggregate update for continental economy."""
        day_fraction = dt / 600.0

        # GDP growth (slow, based on development)
        growth_rate = 0.001 + self.development * 0.002
        self.gdp *= (1 + growth_rate * day_fraction)

        # Calculate what this continent can export (specialization surplus)
        self.export_capacity = {}
        for good, spec in self.specialization.items():
            capacity = self.population * spec * 10 * self.trade_openness
            self.export_capacity[good] = capacity

        # Calculate what this continent wants to import (non-specialized goods)
        self.import_demand = {}
        for good in TRADE_GOODS:
            if good not in self.specialization or self.specialization[good] < 0.5:
                demand = self.population * 2 * self.trade_openness
                if TRADE_GOODS[good]["category"] == "luxury":
                    demand *= self.development
                self.import_demand[good] = demand

        # Price convergence toward world average (slow)
        for good in self.prices:
            base = TRADE_GOODS[good]["base_price"]
            self.prices[good] += (base - self.prices[good]) * 0.01 * day_fraction


# ================================================================
# WORLD MARKET — inter-settlement and inter-continental trade
# ================================================================

class WorldMarket:
    """Coordinates trade between all settlements and continents.

    Trade flows from low-price to high-price regions.
    Transportation cost increases with distance.
    """

    def __init__(self):
        self.settlements: Dict[str, SettlementEconomy] = {}
        self.continents: Dict[str, ContinentalEconomy] = {}
        self.trade_log: List[str] = []
        self.world_prices: Dict[str, float] = {g: d["base_price"] for g, d in TRADE_GOODS.items()}
        self._update_timer = 0.0
        self._trade_timer = 0.0

    def initialize(self, structures: list):
        """Set up settlement economies and continental economies."""
        # Settlement economies
        for s in structures:
            if s.kind in PRODUCTION_PROFILES:
                region = getattr(s, 'region', 'heartlands')
                pop = getattr(s, 'population', 15)
                if pop <= 0:
                    pop = {"hamlet": 8, "village": 20, "town": 50,
                           "city": 100, "castle": 30}.get(s.kind, 15)
                econ = SettlementEconomy(s.name, s.kind, region, pop)
                self.settlements[s.name] = econ

        # Continental economies (from planet.py data)
        self.continents["khor_dural"] = ContinentalEconomy(
            "Khor'Dural", population=12.0, development=0.8,
            specialization={"silk": 2.0, "spices": 1.5, "books": 1.5,
                           "weapons": 1.0, "potions": 1.0},
            trade_openness=0.4)

        self.continents["sun_vaal"] = ContinentalEconomy(
            "Sun'Vaal", population=5.0, development=0.5,
            specialization={"gems": 2.0, "herbs": 1.5, "spices": 2.0,
                           "food": 1.0},
            trade_openness=0.3)

        self.continents["thal_marin"] = ContinentalEconomy(
            "Thal'Marin", population=0.8, development=0.6,
            specialization={"gems": 1.5, "salt": 1.5, "food": 1.0},
            trade_openness=0.7)

        self.continents["vorn_thak"] = ContinentalEconomy(
            "Vorn'Thak", population=0.05, development=0.2,
            specialization={"iron_ore": 2.0, "gems": 1.0, "stone": 1.5},
            trade_openness=0.1)

    def update(self, dt: float, season: str = "spring", solar: float = 0.5):
        """Update all economies and process trade."""
        self._update_timer += dt
        self._trade_timer += dt

        # Update settlement production and prices every 10 seconds
        if self._update_timer >= 10.0:
            self._update_timer = 0.0
            for econ in self.settlements.values():
                econ.update_production(10.0, season, solar)
                econ.update_prices(10.0)

            for cont in self.continents.values():
                cont.update(10.0, season)

            self._update_world_prices()

        # Process inter-settlement trade every 30 seconds
        if self._trade_timer >= 30.0:
            self._trade_timer = 0.0
            self._process_local_trade()
            self._process_continental_trade()

    def _update_world_prices(self):
        """Calculate world average prices from all markets."""
        for good in TRADE_GOODS:
            prices = []
            for econ in self.settlements.values():
                prices.append(econ.prices.get(good, TRADE_GOODS[good]["base_price"]))
            for cont in self.continents.values():
                prices.append(cont.prices.get(good, TRADE_GOODS[good]["base_price"]))
            if prices:
                self.world_prices[good] = sum(prices) / len(prices)

    def _process_local_trade(self):
        """Trade between settlements on Aethermoor.
        Goods flow from surplus (low price) to deficit (high price).
        """
        settlements = list(self.settlements.values())
        if len(settlements) < 2:
            return

        for good in TRADE_GOODS:
            # Find exporters (surplus) and importers (deficit)
            exporters = []
            importers = []
            for econ in settlements:
                surplus = econ.get_export_surplus()
                needs = econ.get_import_needs()
                if good in surplus and surplus[good] > 1:
                    exporters.append((econ, surplus[good], econ.prices[good]))
                elif good in needs and needs[good] > 1:
                    importers.append((econ, needs[good], econ.prices[good]))

            if not exporters or not importers:
                continue

            # Sort: cheapest exporters first, most expensive importers first
            exporters.sort(key=lambda x: x[2])
            importers.sort(key=lambda x: -x[2])

            # Match trades where price differential covers transport
            for exp_econ, exp_qty, exp_price in exporters:
                for imp_econ, imp_qty, imp_price in importers:
                    if exp_price >= imp_price:
                        continue  # no profitable trade

                    trade_qty = min(exp_qty * 0.3, imp_qty * 0.3, 5.0)  # limit per tick
                    if trade_qty < 0.1:
                        continue

                    trade_price = (exp_price + imp_price) / 2
                    trade_value = trade_qty * trade_price

                    # Execute trade
                    exp_econ.stockpile[good] -= trade_qty
                    imp_econ.stockpile[good] += trade_qty
                    exp_econ.treasury += trade_value * 0.9  # transport cost
                    imp_econ.treasury -= trade_value
                    exp_econ.exports_value += trade_value
                    imp_econ.imports_value += trade_value

    def _process_continental_trade(self):
        """Trade between Aethermoor settlements and foreign continents.
        Foreign continents offer exotic goods at competitive prices.
        """
        # Azure Coast settlements trade with overseas
        coastal_settlements = [e for e in self.settlements.values()
                              if e.region == "azure_coast"]
        if not coastal_settlements:
            # Fallback: any settlement can trade (via trade caravans)
            coastal_settlements = list(self.settlements.values())[:3]

        for cont in self.continents.values():
            for good, capacity in cont.export_capacity.items():
                if capacity < 0.5:
                    continue

                # Find Aethermoor settlements that want this good
                for econ in coastal_settlements:
                    local_price = econ.prices.get(good, 99)
                    foreign_price = cont.prices.get(good, 99)

                    # Import if foreign price is significantly lower
                    if foreign_price < local_price * 0.8:
                        import_qty = min(capacity * 0.1, 2.0)  # small amounts
                        cost = import_qty * foreign_price * 1.3  # shipping markup

                        if econ.treasury >= cost:
                            econ.stockpile[good] = econ.stockpile.get(good, 0) + import_qty
                            econ.treasury -= cost
                            cont.treasury += cost * 0.7  # they keep most
                            cont.trade_balance += cost

            # Aethermoor exports to continent
            for good, demand in cont.import_demand.items():
                if demand < 0.5:
                    continue

                for econ in coastal_settlements:
                    surplus = econ.get_export_surplus()
                    if good in surplus and surplus[good] > 1:
                        export_qty = min(surplus[good] * 0.1, demand * 0.1, 2.0)
                        revenue = export_qty * cont.prices.get(good, 10) * 0.9

                        econ.stockpile[good] -= export_qty
                        econ.treasury += revenue
                        cont.trade_balance -= revenue

    def get_settlement_economy(self, name: str) -> Optional[SettlementEconomy]:
        return self.settlements.get(name)

    def get_item_price(self, settlement_name: str, item_name: str,
                       buying: bool = True) -> int:
        """Get the price of a game item at a settlement.
        Maps game item names to trade good categories.
        """
        econ = self.settlements.get(settlement_name)
        if not econ:
            from game.core.items import ITEMS
            base = ITEMS.get(item_name)
            return base.value if base else 1

        # Map item to trade good
        good = _item_to_good(item_name)
        if good:
            price = econ.prices.get(good, TRADE_GOODS[good]["base_price"])
            # Scale to individual item value
            from game.core.items import ITEMS
            base_item = ITEMS.get(item_name)
            base_value = base_item.value if base_item else 10
            ratio = price / TRADE_GOODS[good]["base_price"]
            final = int(base_value * ratio)
        else:
            from game.core.items import ITEMS
            base = ITEMS.get(item_name)
            final = base.value if base else 1

        if not buying:
            final = int(final * 0.5)
        return max(1, final)

    def get_trade_log(self) -> List[str]:
        log = list(self.trade_log)
        self.trade_log.clear()
        return log

    def get_world_report(self) -> str:
        """Summary for UI display."""
        lines = []
        for name, econ in sorted(self.settlements.items()):
            lines.append(f"{name} ({econ.kind}): GDP={econ.gdp:.0f}, "
                        f"pop={econ.population}, prosperity={econ.prosperity:.2f}")
        for name, cont in self.continents.items():
            lines.append(f"[{cont.name}]: GDP={cont.gdp:.0f}M, "
                        f"trade_bal={cont.trade_balance:+.0f}")
        return "\n".join(lines)


# ================================================================
# ITEM TO TRADE GOOD MAPPING
# ================================================================

_ITEM_GOOD_MAP = {
    # Food
    "Bread": "food", "Cooked Meat": "food", "Apple": "food", "Fish": "food",
    "Vegetables": "food", "Berries": "food", "Honey": "food", "Cheese": "food",
    "Meat Pie": "food", "Trail Rations": "food", "Feast Platter": "food",
    # Water
    "Water Flask": "water", "Waterskin": "water",
    # Timber
    "Wood": "timber", "Planks": "timber",
    # Stone
    "Stone": "stone",
    # Ore
    "Iron Ore": "iron_ore", "Copper Ore": "iron_ore", "Gold Nugget": "gems",
    # Herbs
    "Herbs": "herbs", "Flowers": "herbs",
    # Wool/Leather
    "Wool": "wool", "Wolf Pelt": "leather", "Leather": "leather",
    "Tanned Hide": "leather",
    # Iron goods
    "Iron Ingot": "iron_goods", "Nails": "iron_goods", "Iron Chain": "iron_goods",
    # Weapons
    "Iron Sword": "weapons", "Steel Sword": "weapons", "Hunting Bow": "weapons",
    "Enchanted Sword": "weapons", "Arrows": "weapons",
    # Armor
    "Leather Armor": "armor", "Iron Armor": "armor", "Chain Mail": "armor",
    "Plate Armor": "armor", "Iron Shield": "armor",
    # Drinks
    "Ale": "ale", "Mead": "ale", "Wine": "wine", "Dwarven Stout": "ale",
    # Gems
    "Ruby": "gems", "Sapphire": "gems", "Emerald": "gems", "Diamond": "gems",
    "Raw Ruby": "gems", "Raw Sapphire": "gems",
    # Potions
    "Health Potion": "potions", "Greater Health Potion": "potions",
    "Healing Tonic": "potions", "Antidote": "potions",
    # Cloth
    "Linen": "cloth", "Rope": "cloth", "Cloak": "cloth", "Robe": "cloth",
    "Dyed Cloth": "cloth",
    # Books
    "Book": "books", "Spellbook": "books", "Skill Manual": "books",
    # Salt
    "Salt": "salt",
    # Silk (from foreign trade)
    # Spices (from foreign trade)
}


def _item_to_good(item_name: str) -> Optional[str]:
    """Map a game item to a trade good category."""
    return _ITEM_GOOD_MAP.get(item_name)
