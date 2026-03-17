"""
Goods Transport System — physical movement of goods through the world.

Replaces instant teleportation of goods between settlements with a system
where labourers, pack animals, and carts physically carry goods along roads.

Components:
- DeliveryRequest: a pending goods movement between locations
- GoodsTransportManager: settlement delivery queues, caravan dispatch
- TradeCaravanTransport: physical trade caravans with vehicles and animals
- GroundItem: goods dropped on the ground (from dead carriers, robberies)

Goods lifecycle:
  1. Source (settlement store, farm, mine) removes goods
  2. Carrier NPC picks up goods (npc._work_state.carrying set)
  3. NPC walks to destination (visible in world, speed reduced)
  4. NPC deposits goods at destination store
  5. If carrier dies/robbed, goods become GroundItems on the map
"""

import math
import random
from typing import Dict, List, Optional, Tuple


# ================================================================
# CARRY CAPACITY — how much different entities can haul
# ================================================================

# Base carry capacity in "units" of goods
NPC_BASE_CARRY = 5
NPC_STRONG_CARRY = 8       # STR > 14
PORTER_CARRY = 10           # Porter / Laborer profession bonus

# Pack animal carry capacity (units)
PACK_ANIMAL_CARRY = {
    "donkey": 20,
    "mule": 30,
    "horse": 15,
    "camel": 25,
    "war_horse": 12,
    "elk": 10,
}

# Vehicle carry capacity (units) — supplements hauling.py values
# These are "goods units" not weight-lbs
VEHICLE_GOODS_CAPACITY = {
    "handcart": 30,
    "cart": 50,
    "wagon": 100,
    "supply_wagon": 120,
    "sled": 40,
}

# Speed multipliers when carrying goods
CARRY_SPEED_MULT = 0.7          # NPC on foot with goods
PACK_ANIMAL_SPEED_MULT = 0.85   # NPC with pack animal
HANDCART_SPEED_MULT = 0.6
CART_SPEED_MULT = 0.8
WAGON_SPEED_MULT = 0.7


# ================================================================
# DELIVERY REQUEST
# ================================================================

class DeliveryRequest:
    """A pending request to move goods from one location to another."""

    _next_id = 0

    def __init__(self, good: str, quantity: int,
                 from_x: float, from_y: float,
                 to_x: float, to_y: float,
                 from_label: str = "", to_label: str = "",
                 settlement_name: str = "",
                 priority: int = 0):
        DeliveryRequest._next_id += 1
        self.id = DeliveryRequest._next_id
        self.good = good
        self.quantity = quantity
        self.from_x = from_x
        self.from_y = from_y
        self.to_x = to_x
        self.to_y = to_y
        self.from_label = from_label    # e.g. "farm_south"
        self.to_label = to_label        # e.g. "market"
        self.settlement_name = settlement_name
        self.priority = priority        # higher = more urgent
        self.assigned_to: Optional[str] = None  # NPC name
        self.in_transit = False
        self.created_tick = 0
        self.age = 0.0                  # seconds since creation

    def __repr__(self):
        return (f"Delivery#{self.id}({self.quantity}x {self.good} "
                f"{self.from_label}->{self.to_label})")


# ================================================================
# GROUND ITEM — goods dropped on the map
# ================================================================

class GroundItem:
    """Goods dropped on the ground (dead carrier, robbery, etc.)."""

    def __init__(self, good: str, quantity: int, x: float, y: float):
        self.good = good
        self.quantity = quantity
        self.x = x
        self.y = y
        self.age = 0.0          # seconds on ground
        self.max_age = 600.0    # despawn after 10 minutes

    @property
    def expired(self) -> bool:
        return self.age >= self.max_age


# ================================================================
# TRADE CARAVAN TRANSPORT — physical trade between settlements
# ================================================================

class TradeCaravanTransport:
    """A trade caravan that physically moves goods between settlements.

    Uses vehicles and pack animals from hauling.py and domestication.py.
    Replaces instant trade_supplies() with physical movement.
    """

    _next_id = 0

    def __init__(self, origin: str, destination: str,
                 origin_x: float, origin_y: float,
                 dest_x: float, dest_y: float,
                 goods: Dict[str, int],
                 gold_cost: int = 0,
                 vehicle_type: str = "cart"):
        TradeCaravanTransport._next_id += 1
        self.id = TradeCaravanTransport._next_id
        self.origin = origin
        self.destination = destination
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.dest_x = dest_x
        self.dest_y = dest_y
        self.x = origin_x
        self.y = origin_y
        self.goods = dict(goods)                # {"food": 20, "ore": 5}
        self.gold_cost = gold_cost
        self.vehicle_type = vehicle_type
        self.capacity = VEHICLE_GOODS_CAPACITY.get(vehicle_type, 50)

        self.driver_name: Optional[str] = None  # NPC assigned as driver
        self.pack_animals: List[str] = []       # animal kinds pulling/carrying
        self.guard_names: List[str] = []

        self.speed = 1.2   # base, modified by vehicle + animals
        self.arrived = False
        self.returning = False
        self.destroyed = False
        self.phase = "loading"  # loading -> traveling -> unloading -> returning -> done

        # Compute speed from vehicle type
        speed_mults = {
            "handcart": HANDCART_SPEED_MULT,
            "cart": CART_SPEED_MULT,
            "wagon": WAGON_SPEED_MULT,
            "supply_wagon": WAGON_SPEED_MULT,
            "none": CARRY_SPEED_MULT,
        }
        self.speed *= speed_mults.get(vehicle_type, CART_SPEED_MULT)

    @property
    def total_goods(self) -> int:
        return sum(self.goods.values())

    def update(self, dt: float, world=None) -> bool:
        """Move toward current target. Returns True when reached."""
        if self.destroyed:
            return False

        if self.phase == "loading":
            # Brief loading delay (simulated by first update)
            self.phase = "traveling"
            return False

        if self.phase in ("traveling", "returning"):
            if self.phase == "traveling":
                tx, ty = self.dest_x, self.dest_y
            else:
                tx, ty = self.origin_x, self.origin_y

            dx = tx - self.x
            dy = ty - self.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < 3.0:
                if self.phase == "traveling":
                    self.phase = "unloading"
                    self.arrived = True
                    return True
                else:
                    self.phase = "done"
                    return True

            nx, ny = dx / dist, dy / dist
            move = self.speed * dt
            new_x = self.x + nx * move
            new_y = self.y + ny * move

            if world:
                if world.is_walkable(int(new_x), int(self.y), ignore_buildings=True):
                    self.x = new_x
                if world.is_walkable(int(self.x), int(new_y), ignore_buildings=True):
                    self.y = new_y
            else:
                self.x = new_x
                self.y = new_y

        return False


# ================================================================
# GOODS TRANSPORT MANAGER
# ================================================================

class GoodsTransportManager:
    """Central manager for all goods movement in the world.

    Maintains per-settlement delivery queues, dispatches labourers,
    manages trade caravans, and tracks ground items.
    """

    def __init__(self):
        # Per-settlement delivery queues
        self.delivery_queues: Dict[str, List[DeliveryRequest]] = {}
        # Active trade caravans
        self.trade_caravans: List[TradeCaravanTransport] = []
        # Goods dropped on the ground
        self.ground_items: List[GroundItem] = []
        # Goods currently in transit (removed from stores, not yet delivered)
        # Maps delivery_id -> {good, quantity, carrier_name}
        self.in_transit: Dict[int, Dict] = {}

        self._update_timer = 0.0
        self._caravan_check_timer = 0.0
        self._log: List[str] = []

    # ------------------------------------------------------------------
    # Delivery Queue API
    # ------------------------------------------------------------------

    def add_delivery(self, settlement_name: str, good: str, quantity: int,
                     from_x: float, from_y: float,
                     to_x: float, to_y: float,
                     from_label: str = "", to_label: str = "",
                     priority: int = 0) -> DeliveryRequest:
        """Add a delivery request to a settlement's queue."""
        req = DeliveryRequest(
            good, quantity, from_x, from_y, to_x, to_y,
            from_label, to_label, settlement_name, priority)

        if settlement_name not in self.delivery_queues:
            self.delivery_queues[settlement_name] = []
        self.delivery_queues[settlement_name].append(req)
        return req

    def get_pending_deliveries(self, settlement_name: str) -> List[DeliveryRequest]:
        """Get unassigned deliveries for a settlement, sorted by priority."""
        queue = self.delivery_queues.get(settlement_name, [])
        return sorted(
            [d for d in queue if d.assigned_to is None],
            key=lambda d: (-d.priority, d.age))

    def assign_delivery(self, delivery_id: int, npc_name: str) -> Optional[DeliveryRequest]:
        """Assign a delivery to an NPC. Returns the request or None."""
        for queue in self.delivery_queues.values():
            for req in queue:
                if req.id == delivery_id and req.assigned_to is None:
                    req.assigned_to = npc_name
                    req.in_transit = True
                    return req
        return None

    def complete_delivery(self, delivery_id: int):
        """Mark a delivery as complete and remove it."""
        for sname, queue in self.delivery_queues.items():
            for i, req in enumerate(queue):
                if req.id == delivery_id:
                    queue.pop(i)
                    self.in_transit.pop(delivery_id, None)
                    return
        self.in_transit.pop(delivery_id, None)

    def cancel_delivery(self, delivery_id: int):
        """Cancel a delivery (carrier died, etc). Goods may drop."""
        transit = self.in_transit.pop(delivery_id, None)
        for sname, queue in self.delivery_queues.items():
            for i, req in enumerate(queue):
                if req.id == delivery_id:
                    queue.pop(i)
                    return transit
        return transit

    # ------------------------------------------------------------------
    # Trade Caravan API (replaces instant trade_supplies)
    # ------------------------------------------------------------------

    def request_trade_caravan(self, from_settlement: str, to_settlement: str,
                              resource: str, amount: int, gold_cost: int,
                              from_x: float, from_y: float,
                              to_x: float, to_y: float,
                              vehicle_type: str = "cart") -> TradeCaravanTransport:
        """Create a physical trade caravan instead of instant transfer.

        Goods are removed from source settlement immediately (committed
        to transit). They arrive at destination when the caravan does.
        """
        goods = {resource: amount}
        caravan = TradeCaravanTransport(
            from_settlement, to_settlement,
            from_x, from_y, to_x, to_y,
            goods, gold_cost, vehicle_type)
        self.trade_caravans.append(caravan)
        self._log.append(
            f"Trade caravan #{caravan.id}: {amount} {resource} "
            f"from {from_settlement} to {to_settlement}")
        return caravan

    # ------------------------------------------------------------------
    # Ground Items
    # ------------------------------------------------------------------

    def drop_goods(self, good: str, quantity: int, x: float, y: float):
        """Drop goods on the ground (dead carrier, robbery)."""
        if quantity <= 0:
            return
        self.ground_items.append(GroundItem(good, quantity, x, y))
        self._log.append(f"Goods dropped: {quantity}x {good} at ({x:.0f},{y:.0f})")

    def pickup_ground_item(self, index: int) -> Optional[GroundItem]:
        """Pick up a ground item by index."""
        if 0 <= index < len(self.ground_items):
            return self.ground_items.pop(index)
        return None

    def find_ground_items_near(self, x: float, y: float,
                               radius: float = 5.0) -> List[Tuple[int, GroundItem]]:
        """Find ground items near a position. Returns (index, item) pairs."""
        results = []
        for i, item in enumerate(self.ground_items):
            dist = math.sqrt((item.x - x) ** 2 + (item.y - y) ** 2)
            if dist <= radius:
                results.append((i, item))
        return results

    # ------------------------------------------------------------------
    # Auto-generate delivery requests from store imbalances
    # ------------------------------------------------------------------

    def generate_settlement_deliveries(self, settlement_name: str,
                                       world_effects, world):
        """Scan a settlement for goods that need moving and create requests.

        Called periodically to detect:
        - Food at farms but not at market/center
        - Ore at mines but not at smithy
        - Finished goods needing distribution
        """
        sp = None
        if hasattr(world, 'plan'):
            for s in world.plan.settlements:
                if s.name == settlement_name:
                    sp = s
                    break
        if not sp:
            return

        stores = world_effects.get_stores_ref(settlement_name)
        existing = self.delivery_queues.get(settlement_name, [])
        # Don't flood the queue
        if len(existing) >= 8:
            return

        cx, cy = float(sp.x), float(sp.y)

        # Generate deliveries for surplus goods that need redistribution
        # Priority goods: food (keep people fed), ore (keep smiths busy)
        for good, threshold in [("food", 15), ("ore", 8), ("wood", 12),
                                ("weapons", 3), ("tools", 5)]:
            current = stores.get(good, 0)
            if current > threshold:
                # Find a building that might need this good
                # For now, create internal redistribution deliveries
                # from store center to various points in settlement
                surplus = current - threshold
                move_qty = min(surplus // 2, 10)
                if move_qty < 2:
                    continue

                # Check we don't already have a delivery for this good
                already = any(d.good == good and not d.in_transit
                              for d in existing)
                if already:
                    continue

                # Pick a random offset within settlement radius as delivery target
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(3, min(sp.radius, 15))
                tx = cx + math.cos(angle) * dist
                ty = cy + math.sin(angle) * dist

                self.add_delivery(
                    settlement_name, good, move_qty,
                    cx, cy, tx, ty,
                    from_label="store", to_label="distribution",
                    priority=2 if good == "food" else 1)

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------

    def update(self, dt: float, world=None, world_effects=None,
               structures=None):
        """Update all transport systems."""
        self._update_timer += dt

        # Age delivery requests
        for queue in self.delivery_queues.values():
            for req in queue:
                req.age += dt
            # Remove very old unassigned deliveries (> 5 minutes)
            queue[:] = [d for d in queue
                        if d.age < 300.0 or d.assigned_to is not None]

        # Update ground items (age and despawn)
        for item in self.ground_items:
            item.age += dt
        self.ground_items = [i for i in self.ground_items if not i.expired]

        # Update trade caravans
        if world:
            struct_map = {}
            if structures:
                struct_map = {s.name: s for s in structures}

            remaining = []
            for caravan in self.trade_caravans:
                if caravan.destroyed:
                    # Drop goods on ground
                    for good, qty in caravan.goods.items():
                        self.drop_goods(good, qty, caravan.x, caravan.y)
                    continue

                reached = caravan.update(dt, world)

                if reached and caravan.phase == "unloading":
                    # Deliver goods to destination
                    if world_effects:
                        dst_stores = world_effects.get_stores_ref(
                            caravan.destination)
                        for good, qty in caravan.goods.items():
                            dst_stores[good] = dst_stores.get(good, 0) + qty
                        # Gold payment
                        dst_stores["gold"] = max(
                            0, dst_stores.get("gold", 0) - caravan.gold_cost)
                        src_stores = world_effects.get_stores_ref(
                            caravan.origin)
                        src_stores["gold"] = (
                            src_stores.get("gold", 0) + caravan.gold_cost)

                    self._log.append(
                        f"Caravan #{caravan.id} delivered goods to "
                        f"{caravan.destination}")
                    caravan.goods.clear()
                    caravan.phase = "returning"
                    caravan.arrived = False
                    remaining.append(caravan)

                elif reached and caravan.phase == "done":
                    # Returned home — remove caravan
                    self._log.append(
                        f"Caravan #{caravan.id} returned to {caravan.origin}")
                    continue
                else:
                    remaining.append(caravan)

            self.trade_caravans = remaining

        # Periodically generate deliveries for settlements
        self._caravan_check_timer += dt
        if self._caravan_check_timer >= 30.0:
            self._caravan_check_timer = 0.0
            if world_effects and structures:
                for struct in structures:
                    if struct.kind in ("village", "town", "city", "castle"):
                        self.generate_settlement_deliveries(
                            struct.name, world_effects, world)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def get_carry_capacity(self, npc) -> int:
        """Calculate how much an NPC can carry, considering STR and profession."""
        profession = getattr(npc, 'profession', '')
        char_class = getattr(npc, 'char_class', '')

        # Base capacity
        capacity = NPC_BASE_CARRY

        # Profession bonus
        if profession in ("Porter", "Laborer") or char_class in ("Porter", "Laborer"):
            capacity = PORTER_CARRY

        # Strength bonus
        scores = getattr(npc, 'ability_scores', {})
        strength = scores.get('strength', 10)
        if isinstance(strength, (int, float)) and strength > 14:
            capacity = max(capacity, NPC_STRONG_CARRY)
            # Extra for very strong
            if strength > 16:
                capacity += (strength - 16)

        return capacity

    def get_carry_speed_mult(self, npc) -> float:
        """Get speed multiplier for an NPC carrying goods."""
        ws = getattr(npc, '_work_state', None)
        if ws is None or ws.carrying is None:
            return 1.0

        # Check for pack animal companion
        pack_animal = getattr(npc, '_pack_animal_kind', None)
        if pack_animal:
            return PACK_ANIMAL_SPEED_MULT

        # Check for vehicle
        vehicle = getattr(npc, '_transport_vehicle', None)
        if vehicle:
            vtype = getattr(vehicle, 'vehicle_type', 'cart')
            mults = {
                "handcart": HANDCART_SPEED_MULT,
                "cart": CART_SPEED_MULT,
                "wagon": WAGON_SPEED_MULT,
            }
            return mults.get(vtype, CART_SPEED_MULT)

        return CARRY_SPEED_MULT

    def get_total_capacity(self, npc) -> int:
        """Get total carry capacity including pack animals and vehicles."""
        base = self.get_carry_capacity(npc)

        # Add pack animal capacity
        pack_kind = getattr(npc, '_pack_animal_kind', None)
        if pack_kind:
            base += PACK_ANIMAL_CARRY.get(pack_kind, 15)

        # Add vehicle capacity
        vehicle = getattr(npc, '_transport_vehicle', None)
        if vehicle:
            vtype = getattr(vehicle, 'vehicle_type', 'cart')
            base += VEHICLE_GOODS_CAPACITY.get(vtype, 30)

        return base

    def get_log(self) -> List[str]:
        """Get and clear the transport log."""
        msgs = list(self._log)
        self._log.clear()
        return msgs
