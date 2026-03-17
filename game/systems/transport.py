"""
Transport System -- mounts, carts, stables, caravans, coaches, and magical transport.

Provides a comprehensive travel and logistics layer:
- Mount: rideable animals with stamina, hunger, and health
- Cart: pulled by mounts for hauling goods (road-only)
- Stable: buy/sell/rent/stable mounts in settlements
- Caravan: multi-mount trade convoys with guards (extends trade.py)
- CoachService: scheduled passenger routes between major settlements
- MagicalTransport: teleportation circles and flying spells
"""

import math
import random
from enum import Enum
from typing import Dict, List, Optional, Tuple

from game.settings import (
    DAY_LENGTH, ROAD, GRAVEL_ROAD, DENSE_FOREST, SWAMP, MOUNTAIN, SNOW,
)


# ================================================================
# MOUNT TYPES
# ================================================================

MOUNT_TYPES = {
    "horse": {
        "speed_mult": 2.5,
        "carry_capacity": 8,
        "max_stamina": 100.0,
        "stamina_drain": 0.08,    # per tile traveled
        "stamina_regen": 0.15,    # per second resting
        "hunger_rate": 0.04,      # per game-minute
        "max_health": 60,
        "cost": 50,
        "feed_cost": 1.0,
        "description": "A sturdy riding horse",
    },
    "war_horse": {
        "speed_mult": 2.2,
        "carry_capacity": 6,
        "max_stamina": 120.0,
        "stamina_drain": 0.10,
        "stamina_regen": 0.12,
        "hunger_rate": 0.06,
        "max_health": 100,
        "cost": 120,
        "feed_cost": 1.5,
        "description": "A trained war horse, armored",
    },
    "donkey": {
        "speed_mult": 1.3,
        "carry_capacity": 12,
        "max_stamina": 80.0,
        "stamina_drain": 0.05,
        "stamina_regen": 0.20,
        "hunger_rate": 0.03,
        "max_health": 40,
        "cost": 15,
        "feed_cost": 0.5,
        "description": "A reliable pack donkey",
    },
    "mule": {
        "speed_mult": 1.5,
        "carry_capacity": 14,
        "max_stamina": 90.0,
        "stamina_drain": 0.04,
        "stamina_regen": 0.18,
        "hunger_rate": 0.03,
        "max_health": 50,
        "cost": 25,
        "feed_cost": 0.6,
        "description": "A hardy mule, excellent pack animal",
    },
    "camel": {
        "speed_mult": 1.8,
        "carry_capacity": 10,
        "max_stamina": 150.0,
        "stamina_drain": 0.03,
        "stamina_regen": 0.10,
        "hunger_rate": 0.02,
        "max_health": 55,
        "cost": 60,
        "feed_cost": 0.4,
        "description": "A desert camel, tireless traveler",
    },
}


# ================================================================
# MOUNT CLASS
# ================================================================

class Mount:
    """A rideable animal with stamina, hunger, thirst, and health.

    Mounts can be ridden to death through exhaustion, starvation, or
    dehydration. A well-cared-for mount is faster and more reliable.

    Health drains from:
    - Starvation (hunger=0): -2 HP per game-minute
    - Dehydration (thirst=0): -3 HP per game-minute
    - Exhaustion (stamina=0 while still ridden): -1 HP per game-minute
    - Combat damage

    Speed is affected by condition:
    - Hungry (hunger<30): speed x0.8
    - Starving (hunger=0): speed x0.5
    - Thirsty (thirst<30): speed x0.8
    - Tired (stamina<10%): speed x0.6
    - Exhausted (stamina=0): speed x0.3 (barely moving)
    - Injured (health<50%): speed x0.7

    At health=0, the mount dies. The rider is dismounted.
    """

    def __init__(self, mount_type: str, name: str = "", owner: str = ""):
        if mount_type not in MOUNT_TYPES:
            mount_type = "horse"
        data = MOUNT_TYPES[mount_type]

        self.mount_type = mount_type
        self.name = name or f"Unnamed {mount_type.replace('_', ' ').title()}"
        self.owner = owner

        self.speed_mult: float = data["speed_mult"]
        self.carry_capacity: int = data["carry_capacity"]
        self.max_stamina: float = data["max_stamina"]
        self.stamina: float = data["max_stamina"]
        self.stamina_drain: float = data["stamina_drain"]
        self.stamina_regen: float = data["stamina_regen"]
        self.hunger: float = 100.0   # 100=full, 0=starving
        self.thirst: float = 100.0   # 100=hydrated, 0=dehydrated
        self.hunger_rate: float = data["hunger_rate"]
        self.thirst_rate: float = data["hunger_rate"] * 1.5  # thirst drains faster
        self.health: int = data["max_health"]
        self.max_health: int = data["max_health"]
        self.cost: int = data["cost"]
        self.feed_cost: float = data["feed_cost"]

        self.is_alive: bool = True
        self.is_resting = False
        self.stabled_at: Optional[str] = None
        self.hitched_at: Optional[Tuple[float, float]] = None  # position when hitched
        self.inventory: List[str] = []
        self.total_distance_traveled: float = 0.0

    @property
    def alive(self) -> bool:
        return self.is_alive

    @alive.setter
    def alive(self, value: bool):
        self.is_alive = value

    def feed(self, amount: float = 30.0) -> str:
        """Feed the mount. Uses grain, hay, apples, or bread."""
        if not self.is_alive:
            return f"{self.name} is dead."
        old = self.hunger
        self.hunger = min(100.0, self.hunger + amount)
        gained = self.hunger - old
        return f"Fed {self.name}. Hunger: {self.hunger:.0f}/100 (+{gained:.0f})"

    def water(self, amount: float = 35.0) -> str:
        """Give the mount water."""
        if not self.is_alive:
            return f"{self.name} is dead."
        old = self.thirst
        self.thirst = min(100.0, self.thirst + amount)
        gained = self.thirst - old
        return f"Watered {self.name}. Thirst: {self.thirst:.0f}/100 (+{gained:.0f})"

    def rest(self, dt: float):
        """Rest the mount, restoring stamina."""
        self.is_resting = True
        regen = self.stamina_regen * dt
        if self.hunger > 50 and self.thirst > 50:
            regen *= 1.5  # well-cared mounts rest faster
        elif self.hunger < 20 or self.thirst < 20:
            regen *= 0.3  # hungry/thirsty mounts barely recover
        self.stamina = min(self.max_stamina, self.stamina + regen)

    def is_tired(self) -> bool:
        return self.stamina < self.max_stamina * 0.1

    def is_exhausted(self) -> bool:
        return self.stamina <= 0

    def get_effective_speed(self) -> float:
        """Current speed multiplier considering condition."""
        if not self.is_alive:
            return 0.0
        mult = self.speed_mult

        # Hunger penalties
        if self.hunger <= 0:
            mult *= 0.5   # starving
        elif self.hunger < 30:
            mult *= 0.8   # hungry

        # Thirst penalties
        if self.thirst <= 0:
            mult *= 0.4   # dehydrated (worse than hunger)
        elif self.thirst < 30:
            mult *= 0.8   # thirsty

        # Stamina penalties
        if self.stamina <= 0:
            mult *= 0.3   # exhausted — barely moving
        elif self.is_tired():
            mult *= 0.6   # tired — noticeably slower

        # Health penalties
        if self.health < self.max_health * 0.5:
            mult *= 0.7   # injured
        if self.health < self.max_health * 0.2:
            mult *= 0.5   # critically injured

        return mult

    def travel(self, distance: float, terrain_type: int = ROAD):
        """Record distance traveled and drain stamina/thirst."""
        if not self.is_alive:
            return
        self.total_distance_traveled += distance
        drain = self.stamina_drain * distance

        # Terrain affects stamina drain
        if terrain_type in (DENSE_FOREST, SWAMP, MOUNTAIN):
            drain *= 2.0
        elif terrain_type in (ROAD, GRAVEL_ROAD):
            drain *= 0.7

        self.stamina = max(0, self.stamina - drain)
        # Travel also drains thirst slightly
        self.thirst = max(0, self.thirst - distance * 0.02)
        self.is_resting = False

    def update(self, dt: float, game_minutes: float = 0):
        """Tick needs and check health. Can die from neglect."""
        if not self.is_alive:
            return

        # Hunger and thirst decrease over time
        self.hunger = max(0, self.hunger - self.hunger_rate * dt)
        self.thirst = max(0, self.thirst - self.thirst_rate * dt)

        # Starvation damage
        if self.hunger <= 0:
            self.health -= 2  # starving — losing health

        # Dehydration damage (worse than hunger)
        if self.thirst <= 0:
            self.health -= 3  # dehydrating

        # Exhaustion damage (if still being ridden while stamina=0)
        if self.stamina <= 0 and not self.is_resting:
            self.health -= 1  # being pushed beyond limits

        # Resting mount recovers stamina
        if self.is_resting:
            self.rest(dt)

        # Death check
        if self.health <= 0:
            self.is_alive = False
            self.health = 0

    def hitch(self, x: float, y: float) -> str:
        """Hitch the mount at a location (player going indoors)."""
        self.hitched_at = (x, y)
        self.is_resting = True  # hitched horse rests
        return f"Hitched {self.name} outside at ({x:.0f},{y:.0f})"

    def unhitch(self) -> str:
        """Unhitch the mount."""
        self.hitched_at = None
        self.is_resting = False
        return f"Unhitched {self.name}"

    def get_status(self) -> str:
        """Human-readable status."""
        if not self.is_alive:
            return f"{self.name} (DEAD)"
        parts = [f"{self.name} ({self.mount_type})"]
        parts.append(f"HP:{self.health}/{self.max_health}")
        parts.append(f"Stm:{self.stamina:.0f}/{self.max_stamina:.0f}")
        parts.append(f"Hgr:{self.hunger:.0f}")
        parts.append(f"Thr:{self.thirst:.0f}")
        if self.is_tired():
            parts.append("TIRED")
        if self.is_exhausted():
            parts.append("EXHAUSTED")
        if self.hunger <= 0:
            parts.append("STARVING")
        if self.thirst <= 0:
            parts.append("DEHYDRATED")
        speed = self.get_effective_speed()
        parts.append(f"Spd:x{speed:.1f}")
        return " | ".join(parts)

    def get_effective_speed(self) -> float:
        """Get current speed multiplier considering stamina and hunger."""
        base = self.speed_mult
        # Tired mounts slow down
        stamina_ratio = self.stamina / self.max_stamina
        if stamina_ratio < 0.3:
            base *= 0.5 + stamina_ratio
        # Hungry mounts slow down
        if self.hunger < 30:
            base *= 0.7
        # Injured mounts slow down
        if self.health < self.max_health * 0.5:
            base *= 0.6
        return max(0.3, base)

    @property
    def alive(self) -> bool:
        return self.health > 0


# ================================================================
# CART CLASS
# ================================================================

class Cart:
    """A wheeled cart pulled by a mount, for hauling large quantities of goods."""

    def __init__(self, name: str = "Cart"):
        self.name = name
        self.carry_capacity: int = 30
        self.inventory: List[str] = []
        self.health: int = 50
        self.max_health: int = 50
        self.puller: Optional[Mount] = None  # mount pulling this cart
        self.speed_penalty: float = 0.6  # multiplied onto mount speed
        self.cost: int = 50

    def attach_mount(self, mount: Mount):
        """Attach a mount to pull this cart."""
        self.puller = mount

    def detach_mount(self) -> Optional[Mount]:
        """Detach the pulling mount."""
        mount = self.puller
        self.puller = None
        return mount

    def can_travel_terrain(self, terrain_type: int) -> bool:
        """Carts can only travel on roads and flat terrain."""
        road_ok = {ROAD, GRAVEL_ROAD}
        from game.settings import (GRASS, SAND, FLOOR, BRIDGE, FARMLAND,
                                    BUILT_FLOOR, CARPET, MOSAIC, ARCHWAY)
        flat_ok = {GRASS, SAND, FLOOR, BRIDGE, FARMLAND, BUILT_FLOOR,
                   CARPET, MOSAIC, ARCHWAY}
        return terrain_type in road_ok or terrain_type in flat_ok

    def get_effective_speed(self) -> float:
        """Get cart speed (mount speed * penalty)."""
        if self.puller is None or not self.puller.alive:
            return 0.0
        return self.puller.get_effective_speed() * self.speed_penalty

    @property
    def alive(self) -> bool:
        return self.health > 0


# ================================================================
# STABLE CLASS
# ================================================================

class Stable:
    """A stable at a settlement where mounts are bought, sold, rented, and housed."""

    def __init__(self, settlement_name: str, x: int, y: int, capacity: int = 8):
        self.settlement_name = settlement_name
        self.x = x
        self.y = y
        self.capacity = capacity
        self.mounts: List[Mount] = []
        self.for_sale: List[Mount] = []
        self.rented: Dict[str, Tuple[Mount, float]] = {}  # renter_name -> (mount, return_time)
        self.workers: List[str] = []  # NPC names of stable hands

    def initialize_stock(self, rng: random.Random):
        """Create initial mounts for sale."""
        names_pool = [
            "Thunder", "Lightning", "Shadow", "Blaze", "Storm",
            "Midnight", "Copper", "Silver", "Dusty", "Patches",
            "Rowan", "Ember", "Frost", "Ash", "Willow",
            "Biscuit", "Pepper", "Clover", "Hazel", "Maple",
        ]
        rng.shuffle(names_pool)
        name_idx = 0

        num_for_sale = rng.randint(2, 5)
        types = list(MOUNT_TYPES.keys())

        for i in range(num_for_sale):
            mt = rng.choice(types)
            name = names_pool[name_idx % len(names_pool)]
            name_idx += 1
            mount = Mount(mt, name=name)
            self.for_sale.append(mount)

    def buy_mount(self, buyer_name: str, mount_index: int,
                  buyer_gold: int) -> Optional[Mount]:
        """Buy a mount. Returns the mount if successful."""
        if mount_index < 0 or mount_index >= len(self.for_sale):
            return None
        mount = self.for_sale[mount_index]
        if buyer_gold < mount.cost:
            return None
        self.for_sale.pop(mount_index)
        mount.owner = buyer_name
        return mount

    def sell_mount(self, mount: Mount) -> int:
        """Sell a mount to the stable. Returns gold received."""
        # Pay 40-60% of base cost depending on condition
        condition_ratio = mount.health / max(1, mount.max_health)
        price = int(mount.cost * 0.4 * condition_ratio + mount.cost * 0.1)
        mount.owner = ""
        self.for_sale.append(mount)
        return price

    def rent_mount(self, renter_name: str, duration_hours: float,
                   renter_gold: int) -> Optional[Tuple[Mount, int]]:
        """Rent a mount for a duration. Returns (mount, cost) or None."""
        if not self.for_sale:
            return None
        mount = self.for_sale[0]
        # Rental cost: 10% of mount cost per game-day
        cost_per_day = max(2, int(mount.cost * 0.10))
        days = max(1, duration_hours / 24.0)
        total_cost = int(cost_per_day * days)
        if renter_gold < total_cost:
            return None

        self.for_sale.pop(0)
        mount.owner = renter_name
        # Return time in game seconds
        return_time = duration_hours * (DAY_LENGTH / 24.0)
        self.rented[renter_name] = (mount, return_time)
        return (mount, total_cost)

    def stable_mount(self, mount: Mount) -> bool:
        """Stable a mount for safekeeping. Returns True if space available."""
        if len(self.mounts) >= self.capacity:
            return False
        mount.stabled_at = self.settlement_name
        mount.is_resting = True
        self.mounts.append(mount)
        return True

    def retrieve_mount(self, owner_name: str) -> Optional[Mount]:
        """Retrieve a stabled mount."""
        for i, m in enumerate(self.mounts):
            if m.owner == owner_name:
                m.stabled_at = None
                m.is_resting = False
                return self.mounts.pop(i)
        return None

    def update(self, dt: float):
        """Update all stabled mounts (feed, rest)."""
        for mount in self.mounts:
            mount.rest(dt)
            # Stable hands feed the mounts
            if mount.hunger < 70 and self.workers:
                mount.feed(20.0)

        # Check rental returns
        expired = []
        for name, (mount, return_time) in self.rented.items():
            # Decrease remaining rental time
            self.rented[name] = (mount, return_time - dt)
            if return_time - dt <= 0:
                expired.append(name)

        for name in expired:
            mount, _ = self.rented.pop(name)
            mount.owner = ""
            self.for_sale.append(mount)


# ================================================================
# CARAVAN CLASS (upgraded from trade.py)
# ================================================================

class Caravan:
    """A trade caravan with multiple mounts, carts, guards, and merchants.

    Speed is determined by the slowest member.
    Can be attacked by bandits.
    """

    def __init__(self, origin: str, destination: str,
                 leader_name: str, x: float, y: float):
        self.origin = origin
        self.destination = destination
        self.leader_name = leader_name
        self.x = x
        self.y = y

        self.mounts: List[Mount] = []
        self.carts: List[Cart] = []
        self.guard_names: List[str] = []
        self.merchant_names: List[str] = []
        self.goods: Dict[str, int] = {}
        self.gold: int = 0

        self.arrived = False
        self.returning = False
        self.under_attack = False
        self.destroyed = False
        self.total_distance = 0.0

        # Route waypoints from road network
        self.route_waypoints: List[Tuple[int, int]] = []
        self.waypoint_idx: int = 0

    @property
    def speed(self) -> float:
        """Speed determined by slowest member."""
        speeds = []
        for mount in self.mounts:
            speeds.append(mount.get_effective_speed())
        for cart in self.carts:
            s = cart.get_effective_speed()
            if s > 0:
                speeds.append(s)
        if not speeds:
            return 1.0  # walking speed
        return min(speeds)

    @property
    def guard_strength(self) -> int:
        """Total defensive strength based on number of guards."""
        return len(self.guard_names) * 10

    def add_mount(self, mount: Mount):
        self.mounts.append(mount)

    def add_cart(self, cart: Cart):
        self.carts.append(cart)

    def add_guard(self, name: str):
        self.guard_names.append(name)

    def add_merchant(self, name: str):
        self.merchant_names.append(name)

    def load_goods(self, item: str, quantity: int):
        self.goods[item] = self.goods.get(item, 0) + quantity

    def update(self, dt: float, dest_x: float, dest_y: float,
               world=None) -> bool:
        """Move toward destination along waypoints. Returns True when arrived."""
        if self.destroyed:
            return False

        # Follow waypoints if available
        if self.route_waypoints and self.waypoint_idx < len(self.route_waypoints):
            wx, wy = self.route_waypoints[self.waypoint_idx]
            target_x, target_y = float(wx), float(wy)
        else:
            target_x, target_y = dest_x, dest_y

        dx = target_x - self.x
        dy = target_y - self.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 3:
            if (self.route_waypoints and
                    self.waypoint_idx < len(self.route_waypoints) - 1):
                self.waypoint_idx += 1
                return False
            self.arrived = True
            return True

        # Move
        speed = self.speed
        nx_d, ny_d = dx / dist, dy / dist
        move_dist = speed * dt
        new_x = self.x + nx_d * move_dist
        new_y = self.y + ny_d * move_dist

        # Check walkability
        if world:
            if world.is_walkable(int(new_x), int(self.y), ignore_buildings=True):
                self.x = new_x
            if world.is_walkable(int(self.x), int(new_y), ignore_buildings=True):
                self.y = new_y
        else:
            self.x = new_x
            self.y = new_y

        # Update mounts
        actual_move = move_dist
        self.total_distance += actual_move
        for mount in self.mounts:
            terrain = ROAD
            if world:
                tx, ty = int(self.x), int(self.y)
                if 0 <= tx < world.width and 0 <= ty < world.height:
                    terrain = world.tiles[ty][tx]
            mount.travel(actual_move * 0.1, terrain)
            mount.update(dt)

        return False

    def check_bandit_attack(self, monster_lairs: list = None,
                            rng: random.Random = None) -> bool:
        """Check if bandits attack the caravan based on proximity to lairs.
        Returns True if attack happens.
        """
        if rng is None:
            rng = random.Random()
        if not monster_lairs:
            return False

        for lair in monster_lairs:
            lx = getattr(lair, 'x', 0)
            ly = getattr(lair, 'y', 0)
            dist = math.sqrt((self.x - lx) ** 2 + (self.y - ly) ** 2)
            if dist < 20:
                # Chance of attack based on distance and guard strength
                attack_chance = max(0.01, 0.3 - self.guard_strength * 0.01)
                if rng.random() < attack_chance:
                    self.under_attack = True
                    return True
        return False

    def resolve_attack(self, attacker_strength: int,
                       rng: random.Random = None) -> dict:
        """Resolve a bandit attack. Returns outcome dict."""
        if rng is None:
            rng = random.Random()

        guard_power = self.guard_strength + rng.randint(1, 20)
        bandit_power = attacker_strength + rng.randint(1, 20)

        result = {
            "success": False,
            "goods_lost": {},
            "gold_lost": 0,
            "guards_lost": 0,
            "mounts_lost": 0,
        }

        if bandit_power > guard_power:
            # Bandits win -- lose some goods and gold
            result["success"] = True
            gold_stolen = min(self.gold, rng.randint(5, self.gold // 2 + 1))
            self.gold -= gold_stolen
            result["gold_lost"] = gold_stolen

            # Lose some goods
            for item in list(self.goods.keys()):
                if rng.random() < 0.4:
                    lost = min(self.goods[item], rng.randint(1, 3))
                    self.goods[item] -= lost
                    result["goods_lost"][item] = lost
                    if self.goods[item] <= 0:
                        del self.goods[item]

            # Some guards may fall
            guards_lost = rng.randint(0, max(1, len(self.guard_names) // 2))
            for _ in range(guards_lost):
                if self.guard_names:
                    self.guard_names.pop()
                    result["guards_lost"] += 1

            # Possibly lose a mount
            if rng.random() < 0.2 and self.mounts:
                self.mounts.pop()
                result["mounts_lost"] = 1

            # Caravan destroyed if all guards and mounts gone
            if not self.guard_names and not self.mounts:
                self.destroyed = True
        else:
            # Caravan fights off the bandits
            if rng.random() < 0.3 and self.guard_names:
                self.guard_names.pop()
                result["guards_lost"] = 1

        self.under_attack = False
        return result


# ================================================================
# COACH SERVICE
# ================================================================

class CoachRoute:
    """A scheduled coach route between two major settlements."""

    def __init__(self, origin: str, destination: str,
                 origin_x: float, origin_y: float,
                 dest_x: float, dest_y: float,
                 fare: int, travel_time_hours: float):
        self.origin = origin
        self.destination = destination
        self.origin_x = origin_x
        self.origin_y = origin_y
        self.dest_x = dest_x
        self.dest_y = dest_y
        self.fare = fare
        self.travel_time_hours = travel_time_hours


class Coach:
    """An active coach traveling along a route."""

    def __init__(self, route: CoachRoute, departure_time: float):
        self.route = route
        self.departure_time = departure_time
        self.x = route.origin_x
        self.y = route.origin_y
        self.passengers: List[str] = []
        self.arrived = False
        self.progress = 0.0  # 0.0 to 1.0

    def update(self, dt: float, game_time: float) -> bool:
        """Update coach position. Returns True when arrived."""
        if self.arrived:
            return True

        travel_seconds = self.route.travel_time_hours * (DAY_LENGTH / 24.0)
        elapsed = game_time - self.departure_time
        self.progress = min(1.0, elapsed / max(1.0, travel_seconds))

        self.x = self.route.origin_x + (self.route.dest_x - self.route.origin_x) * self.progress
        self.y = self.route.origin_y + (self.route.dest_y - self.route.origin_y) * self.progress

        if self.progress >= 1.0:
            self.arrived = True
            return True
        return False


class CoachService:
    """Scheduled coach routes between major settlements.

    Coaches run on timetables, carry passengers, and only use paved/king roads.
    """

    def __init__(self):
        self.routes: List[CoachRoute] = []
        self.active_coaches: List[Coach] = []
        self._schedule_timer = 0.0
        self._departure_interval = DAY_LENGTH / 3.0  # 3 departures per day

    def initialize(self, structures: list, road_network=None):
        """Create coach routes between towns and cities on paved/king roads."""
        from game.systems.roads import RoadType

        major = [s for s in structures if s.kind in ("town", "city")]
        if len(major) < 2:
            return

        # Create routes between nearby major settlements
        for i, sa in enumerate(major):
            for sb in major[i + 1:]:
                dist = math.sqrt((sa.x - sb.x) ** 2 + (sa.y - sb.y) ** 2)
                if dist > 500:
                    continue

                # Check road network for valid road type
                valid = True
                if road_network:
                    seg = road_network.get_road_between(sa.name, sb.name)
                    if seg and seg.road_type not in (RoadType.PAVED_ROAD,
                                                      RoadType.KING_ROAD):
                        valid = False
                    # Also valid if there's a multi-hop route through paved roads
                    if not seg:
                        route = road_network.get_route(sa.name, sb.name)
                        if route and len(route) <= 4:
                            valid = True
                        else:
                            valid = False

                if not valid:
                    continue

                # Fare based on distance (1 gold per 20 tiles)
                fare = max(2, int(dist / 20))
                # Travel time: ~2 game-hours per 100 tiles
                travel_hours = dist / 50.0

                route = CoachRoute(
                    sa.name, sb.name,
                    float(sa.x), float(sa.y),
                    float(sb.x), float(sb.y),
                    fare, travel_hours,
                )
                self.routes.append(route)

                # Reverse route
                rev = CoachRoute(
                    sb.name, sa.name,
                    float(sb.x), float(sb.y),
                    float(sa.x), float(sa.y),
                    fare, travel_hours,
                )
                self.routes.append(rev)

    def get_routes_from(self, settlement_name: str) -> List[CoachRoute]:
        """Get all coach routes departing from a settlement."""
        return [r for r in self.routes if r.origin == settlement_name]

    def board_coach(self, passenger_name: str, route: CoachRoute,
                    game_time: float, gold: int) -> Optional[Coach]:
        """Board a coach. Returns the Coach if successful."""
        if gold < route.fare:
            return None

        # Check if there's already an active coach on this route we can join
        for coach in self.active_coaches:
            if (coach.route.origin == route.origin and
                    coach.route.destination == route.destination and
                    not coach.arrived and coach.progress < 0.05):
                coach.passengers.append(passenger_name)
                return coach

        # Create new coach
        coach = Coach(route, game_time)
        coach.passengers.append(passenger_name)
        self.active_coaches.append(coach)
        return coach

    def update(self, dt: float, game_time: float):
        """Update all active coaches and spawn scheduled departures."""
        # Update existing coaches
        remaining = []
        for coach in self.active_coaches:
            arrived = coach.update(dt, game_time)
            if not arrived:
                remaining.append(coach)
            # Keep arrived coaches briefly so passengers can disembark
            elif coach.progress < 1.05:
                coach.progress += dt * 0.01
                remaining.append(coach)

        self.active_coaches = remaining

        # Scheduled departures
        self._schedule_timer += dt
        if self._schedule_timer >= self._departure_interval:
            self._schedule_timer = 0.0
            # Auto-spawn coaches for NPC travel
            if self.routes:
                route = self.routes[int(game_time) % len(self.routes)]
                coach = Coach(route, game_time)
                self.active_coaches.append(coach)


# ================================================================
# MAGICAL TRANSPORT
# ================================================================

class TeleportCircle:
    """A teleportation circle at a temple or wizard tower."""

    def __init__(self, name: str, x: int, y: int,
                 settlement_name: str, circle_type: str = "temple"):
        self.name = name
        self.x = x
        self.y = y
        self.settlement_name = settlement_name
        self.circle_type = circle_type  # "temple" or "wizard_tower"
        self.active = True
        self.uses_today = 0
        self.max_uses_per_day = 5 if circle_type == "wizard_tower" else 3

    def can_use(self) -> bool:
        return self.active and self.uses_today < self.max_uses_per_day

    def reset_daily(self):
        self.uses_today = 0


class MagicalTransport:
    """Manages teleportation circles and magical flight.

    Teleportation requires a spellcaster with the teleportation spell.
    Consumes spell slots and can fail based on skill check.
    Non-casters must hire a wizard (expensive).
    Flying is very rare and short-range.
    """

    def __init__(self):
        self.circles: List[TeleportCircle] = []
        self._day_reset_timer = 0.0

    def initialize(self, structures: list):
        """Place teleportation circles at temples and in cities."""
        circle_id = 0
        for s in structures:
            if s.kind == "temple":
                name = f"Circle of {s.name}"
                circle = TeleportCircle(name, s.x, s.y, s.name, "temple")
                self.circles.append(circle)
                circle_id += 1
            elif s.kind == "city":
                # Cities get a wizard tower circle
                name = f"Arcane Circle of {s.name}"
                circle = TeleportCircle(
                    name, s.x + 5, s.y - 5, s.name, "wizard_tower")
                self.circles.append(circle)
                circle_id += 1

    def get_circles_near(self, x: float, y: float,
                         radius: float = 5.0) -> List[TeleportCircle]:
        """Find teleport circles near a position."""
        result = []
        for c in self.circles:
            dist = math.sqrt((c.x - x) ** 2 + (c.y - y) ** 2)
            if dist <= radius:
                result.append(c)
        return result

    def get_destination_circles(self, exclude_name: str = "") -> List[TeleportCircle]:
        """Get all possible teleport destinations."""
        return [c for c in self.circles
                if c.name != exclude_name and c.can_use()]

    def attempt_teleport(self, caster, source_circle: TeleportCircle,
                         dest_circle: TeleportCircle,
                         rng: random.Random = None) -> dict:
        """Attempt teleportation. Returns result dict.

        Result: {success, destination_x, destination_y, spell_slots_used, reason}
        """
        if rng is None:
            rng = random.Random()

        result = {
            "success": False,
            "destination_x": 0,
            "destination_y": 0,
            "spell_slots_used": 1,
            "reason": "",
        }

        if not source_circle.can_use():
            result["reason"] = "Source circle exhausted for today"
            return result

        if not dest_circle.can_use():
            result["reason"] = "Destination circle exhausted for today"
            return result

        # Skill check: spellcraft or arcana
        skills = getattr(caster, 'npc_skills', getattr(caster, 'skills', {}))
        scores = getattr(caster, 'ability_scores', {})
        spellcraft = skills.get('spellcraft', 0)
        arcana = skills.get('arcana', 0)
        int_mod = (scores.get('intelligence', 10) - 10) // 2

        # DC based on distance
        dist = math.sqrt((source_circle.x - dest_circle.x) ** 2 +
                         (source_circle.y - dest_circle.y) ** 2)
        dc = 10 + int(dist / 100)

        roll = rng.randint(1, 20) + max(spellcraft, arcana) + int_mod

        if roll >= dc:
            result["success"] = True
            result["destination_x"] = dest_circle.x
            result["destination_y"] = dest_circle.y
            source_circle.uses_today += 1
            dest_circle.uses_today += 1
        else:
            result["reason"] = f"Spell failed (rolled {roll} vs DC {dc})"
            # Misfire: appear at random offset
            if rng.random() < 0.3:
                offset = rng.randint(5, 20)
                angle = rng.uniform(0, 2 * math.pi)
                result["destination_x"] = int(dest_circle.x + math.cos(angle) * offset)
                result["destination_y"] = int(dest_circle.y + math.sin(angle) * offset)
                result["success"] = True
                result["reason"] = "Partial success - appeared off-target"
                source_circle.uses_today += 1

        return result

    def get_teleport_cost(self, caster) -> int:
        """Get gold cost for a non-caster to hire a wizard for teleportation."""
        skills = getattr(caster, 'npc_skills', getattr(caster, 'skills', {}))
        spellcraft = skills.get('spellcraft', 0)
        if spellcraft >= 3:
            return 0  # can self-cast
        return 50  # hire a wizard

    def attempt_fly(self, caster, target_x: float, target_y: float,
                    rng: random.Random = None) -> dict:
        """Attempt magical flight. Very rare, short distance only.

        Result: {success, max_distance, spell_slots_used, reason}
        """
        if rng is None:
            rng = random.Random()

        result = {
            "success": False,
            "max_distance": 0,
            "spell_slots_used": 2,
            "reason": "",
        }

        skills = getattr(caster, 'npc_skills', getattr(caster, 'skills', {}))
        scores = getattr(caster, 'ability_scores', {})
        spellcraft = skills.get('spellcraft', 0)

        if spellcraft < 5:
            result["reason"] = "Requires spellcraft >= 5"
            return result

        # Flight distance based on spellcraft level
        max_dist = 20 + spellcraft * 10  # tiles
        cx = getattr(caster, 'x', 0)
        cy = getattr(caster, 'y', 0)
        actual_dist = math.sqrt((target_x - cx) ** 2 + (target_y - cy) ** 2)

        if actual_dist > max_dist:
            result["reason"] = f"Target too far ({actual_dist:.0f} tiles, max {max_dist})"
            return result

        # Skill check DC 15
        int_mod = (scores.get('intelligence', 10) - 10) // 2
        roll = rng.randint(1, 20) + spellcraft + int_mod

        if roll >= 15:
            result["success"] = True
            result["max_distance"] = max_dist
        else:
            result["reason"] = f"Flight spell failed (rolled {roll} vs DC 15)"

        return result

    def update(self, dt: float):
        """Update magical transport (daily resets)."""
        self._day_reset_timer += dt
        if self._day_reset_timer >= DAY_LENGTH:
            self._day_reset_timer = 0.0
            for circle in self.circles:
                circle.reset_daily()


# ================================================================
# TRANSPORT SYSTEM (top-level manager)
# ================================================================

class TransportSystem:
    """Top-level manager coordinating all transport subsystems."""

    def __init__(self):
        self.stables: List[Stable] = []
        self.caravans: List[Caravan] = []
        self.coach_service = CoachService()
        self.magical_transport = MagicalTransport()
        self._update_timer = 0.0

    def initialize(self, structures: list, road_network=None,
                   rng: random.Random = None):
        """Initialize all transport subsystems."""
        if rng is None:
            rng = random.Random()

        # Create stables in towns and cities
        for s in structures:
            if s.kind in ("town", "city"):
                stable = Stable(s.name, s.x + 10, s.y + 5)
                stable.initialize_stock(rng)
                self.stables.append(stable)

        # Initialize coach routes
        self.coach_service.initialize(structures, road_network)

        # Initialize magical transport
        self.magical_transport.initialize(structures)

    def get_stable_at(self, settlement_name: str) -> Optional[Stable]:
        """Find stable at a settlement."""
        for stable in self.stables:
            if stable.settlement_name == settlement_name:
                return stable
        return None

    def get_stable_near(self, x: float, y: float,
                        radius: float = 20.0) -> Optional[Stable]:
        """Find nearest stable within radius."""
        best = None
        best_dist = radius
        for stable in self.stables:
            dist = math.sqrt((stable.x - x) ** 2 + (stable.y - y) ** 2)
            if dist < best_dist:
                best_dist = dist
                best = stable
        return best

    def update(self, dt: float, game_time: float, structures: list = None,
               world=None):
        """Update all transport systems."""
        self._update_timer += dt

        # Update stables every 5 seconds
        if self._update_timer >= 5.0:
            self._update_timer = 0.0
            for stable in self.stables:
                stable.update(5.0)

        # Update coaches
        self.coach_service.update(dt, game_time)

        # Update magical transport
        self.magical_transport.update(dt)

        # Update caravans
        if structures and world:
            struct_map = {s.name: s for s in structures}
            remaining = []
            for caravan in self.caravans:
                if caravan.destroyed:
                    continue
                if caravan.returning:
                    origin = struct_map.get(caravan.origin)
                    if origin:
                        arrived = caravan.update(
                            dt, float(origin.x), float(origin.y), world)
                        if not arrived:
                            remaining.append(caravan)
                    else:
                        remaining.append(caravan)
                else:
                    dest = struct_map.get(caravan.destination)
                    if dest:
                        arrived = caravan.update(
                            dt, float(dest.x), float(dest.y), world)
                        if arrived:
                            caravan.returning = True
                            caravan.arrived = False
                        remaining.append(caravan)
                    else:
                        remaining.append(caravan)
            self.caravans = remaining
