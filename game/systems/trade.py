"""
Trade system: caravans, trade routes, resource dependencies.

Merchant NPCs form caravans that travel between settlements
buying low and selling high. Settlements need goods they can't
produce locally, creating natural trade networks.
"""

import random
import math
from typing import Dict, List, Optional, Tuple


class TradeCaravan:
    """A group of merchants traveling between settlements."""

    def __init__(self, origin: str, destination: str, merchant_name: str,
                 x: float, y: float):
        self.origin = origin
        self.destination = destination
        self.merchant_name = merchant_name
        self.x = x
        self.y = y
        self.goods: Dict[str, int] = {}  # item_name -> quantity
        self.gold = random.randint(20, 80)
        self.speed = 1.5
        self.arrived = False
        self.returning = False

    def update(self, dt: float, dest_x: float, dest_y: float, world) -> bool:
        """Move toward destination. Returns True when arrived."""
        dx = dest_x - self.x
        dy = dest_y - self.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 3:
            self.arrived = True
            return True

        nx, ny = dx / dist, dy / dist
        new_x = self.x + nx * self.speed * dt
        new_y = self.y + ny * self.speed * dt
        if world.is_walkable(int(new_x), int(self.y)):
            self.x = new_x
        if world.is_walkable(int(self.x), int(new_y)):
            self.y = new_y
        return False


# What each settlement type typically needs
SETTLEMENT_DEMANDS = {
    "hamlet":  ["Iron Sword", "Health Potion", "Salt", "Bread"],
    "village": ["Iron Sword", "Health Potion", "Herbs", "Iron Ore"],
    "town":    ["Steel Sword", "Iron Armor", "Gems", "Wine", "Books"],
    "city":    ["Steel Sword", "Plate Armor", "Gems", "Spellbook", "Wine"],
    "castle":  ["Iron Armor", "Arrows", "Health Potion", "Bread"],
}


class TradeSystem:
    """Manages trade routes and caravans between settlements."""

    def __init__(self):
        self.caravans: List[TradeCaravan] = []
        self.trade_routes: List[Tuple[str, str]] = []  # (origin, destination)
        self.trade_timer = 0.0
        self.trade_log: List[str] = []

    def initialize(self, structures: list):
        """Create initial trade routes between settlements."""
        settlements = [s for s in structures
                      if s.kind in ("hamlet", "village", "town", "city", "castle")]

        # Connect each settlement to 1-3 nearest others
        for s in settlements:
            others = sorted(
                [o for o in settlements if o is not s],
                key=lambda o: (o.x - s.x)**2 + (o.y - s.y)**2  # squared dist preserves sort order
            )
            for partner in others[:random.randint(1, 3)]:
                route = (s.name, partner.name)
                reverse = (partner.name, s.name)
                if route not in self.trade_routes and reverse not in self.trade_routes:
                    self.trade_routes.append(route)

    def update(self, dt: float, structures: list, npcs: list, economy, world):
        """Update caravans and spawn new ones."""
        self.trade_timer += dt

        # Spawn new caravans periodically (every ~30s of accumulated dt)
        if self.trade_timer > 30.0 and len(self.caravans) < 10:
            self.trade_timer = 0.0
            if self.trade_routes:
                route = random.choice(self.trade_routes)
                self._spawn_caravan(route, structures, npcs, economy)

        # Update existing caravans
        struct_map = {s.name: s for s in structures}
        remaining = []
        for caravan in self.caravans:
            if caravan.returning:
                # Going home
                origin = struct_map.get(caravan.origin)
                if origin:
                    arrived = caravan.update(dt, float(origin.x), float(origin.y), world)
                    if arrived:
                        self.trade_log.append(
                            f"Caravan returned to {caravan.origin} with {caravan.gold}g profit")
                        continue  # remove caravan
                remaining.append(caravan)
            else:
                # Going to destination
                dest = struct_map.get(caravan.destination)
                if dest:
                    arrived = caravan.update(dt, float(dest.x), float(dest.y), world)
                    if arrived:
                        # Trade at destination
                        self._execute_trade(caravan, economy)
                        caravan.returning = True
                        caravan.arrived = False
                remaining.append(caravan)

        self.caravans = remaining

    def _spawn_caravan(self, route: Tuple[str, str], structures: list,
                       npcs: list, economy):
        """Spawn a new trade caravan."""
        origin_name, dest_name = route
        origin = next((s for s in structures if s.name == origin_name), None)
        if not origin:
            return

        # Find a merchant NPC at origin — prefer Rogues/Bards, but accept anyone
        merchant = None
        fallback = None
        for npc in npcs:
            if not npc.alive:
                continue
            if npc.dist_to_pos(origin.x, origin.y) < 30:
                if getattr(npc, 'char_class', '') in ('Rogue', 'Bard'):
                    merchant = npc
                    break
                elif fallback is None and npc.current_action in ('', 'idle'):
                    fallback = npc
        if merchant is None:
            merchant = fallback

        merchant_name = merchant.name if merchant else "Traveling Merchant"

        caravan = TradeCaravan(
            origin_name, dest_name, merchant_name,
            float(origin.x), float(origin.y)
        )

        # Buy goods at origin (cheap local goods)
        market = economy.get_market(origin_name)
        if market:
            for item in ["Bread", "Wood", "Iron Ore", "Herbs", "Wheat"]:
                if market.supply.get(item, 0) > 3:
                    caravan.goods[item] = random.randint(2, 5)
                    caravan.gold -= 2
        # Always carry at least some goods so trade is meaningful
        if not caravan.goods:
            caravan.goods["Trade Goods"] = random.randint(3, 8)

        self.caravans.append(caravan)
        self.trade_log.append(f"Caravan departs {origin_name} for {dest_name}")

    def _execute_trade(self, caravan: TradeCaravan, economy):
        """Sell goods at destination and buy local goods for return trip."""
        market = economy.get_market(caravan.destination)
        if not market:
            return

        profit = 0
        for item, qty in caravan.goods.items():
            price = market.sell(item) * qty
            profit += price

        caravan.gold += profit
        caravan.goods.clear()

        # Buy local goods for return
        for item in ["Bread", "Herbs", "Wheat"]:
            if market.supply.get(item, 0) > 3:
                caravan.goods[item] = random.randint(1, 3)

        self.trade_log.append(
            f"Caravan traded at {caravan.destination} (+{profit}g)")

    def register_new_settlements(self, new_structures: list):
        """Register newly-activated settlements and create trade routes to them."""
        # Gather existing settlement structures for distance checks
        existing_names = set()
        for r in self.trade_routes:
            existing_names.add(r[0])
            existing_names.add(r[1])

        for s in new_structures:
            if s.kind not in ("village", "town", "city"):
                continue
            if s.name in existing_names:
                continue
            # Connect to 1-2 nearest existing route endpoints
            existing_list = list(existing_names)
            if not existing_list:
                existing_names.add(s.name)
                continue
            # We don't have coordinates for existing route names, so just
            # pair with random existing partners
            partners = random.sample(existing_list, min(2, len(existing_list)))
            for partner in partners:
                route = (s.name, partner)
                reverse = (partner, s.name)
                if route not in self.trade_routes and reverse not in self.trade_routes:
                    self.trade_routes.append(route)
            existing_names.add(s.name)

    def passive_trade(self, structures: list, governance):
        """Daily passive trade along routes — transfers gold between treasuries.

        Called once per game day. Each route has a 20% chance of generating
        background trade that moves gold and generates event log entries.
        """
        struct_map = {s.name: s for s in structures}
        kingdoms = governance.kingdoms if hasattr(governance, 'kingdoms') else {}

        for origin_name, dest_name in self.trade_routes:
            if random.random() > 0.20:
                continue

            origin = struct_map.get(origin_name)
            dest = struct_map.get(dest_name)
            if not origin or not dest:
                continue

            # Determine trade value based on settlement sizes
            size_bonus = {"hamlet": 0, "village": 1, "town": 2, "city": 3,
                          "castle": 1}
            o_bonus = size_bonus.get(origin.kind, 0)
            d_bonus = size_bonus.get(dest.kind, 0)
            # Specialization match: different settlement types trade more
            spec_bonus = 3 if origin.kind != dest.kind else 0
            trade_value = random.randint(5, 12) + o_bonus + d_bonus + spec_bonus

            # Find kingdoms that own these settlements and transfer gold
            origin_kingdom = None
            dest_kingdom = None
            for kname, kingdom in kingdoms.items():
                if origin_name in kingdom.settlements:
                    origin_kingdom = kingdom
                if dest_name in kingdom.settlements:
                    dest_kingdom = kingdom

            # Both kingdoms benefit from trade (tax revenue)
            tax = max(1, trade_value // 5)
            if origin_kingdom:
                origin_kingdom.treasury += tax
            if dest_kingdom:
                dest_kingdom.treasury += tax

            # Inter-kingdom trade tariffs: 10% tariff when different kingdoms
            if (origin_kingdom and dest_kingdom
                    and origin_kingdom is not dest_kingdom):
                tariff = max(1, int(trade_value * 0.1))
                origin_kingdom.treasury += tariff
                dest_kingdom.treasury += tariff

            self.trade_log.append(
                f"Trade caravan traveled from {origin_name} to {dest_name}, "
                f"delivering goods worth {trade_value} gold")

    def get_trade_log(self) -> List[str]:
        msgs = list(self.trade_log)
        self.trade_log.clear()
        return msgs
