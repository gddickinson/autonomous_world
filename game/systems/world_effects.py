"""World Effects — applies simulation changes to the physical world.

When the abstract simulation or governance system produces events
(wars, construction, migrations, disasters), this system modifies
the actual tile data so changes are visible in-game.

Effects include:
- Building destruction (war, siege) -> tiles become RUBBLE
- New construction -> stamp new blueprints into chunks
- Road damage/repair -> degrade or restore road tiles
- Settlement ownership changes -> update guards, flags
- Settlement destruction -> convert to ruins
- New settlement founding -> place new hamlet at suitable location
- Fire damage -> spread and convert tiles
- Farm creation, growth, harvest, and destruction
- Building ownership and habitation tracking
- Settlement stores, livestock, and resource management
- Fortification construction, upgrades, and damage
- Garrison deployment and management
- Daily economic updates (consumption, growth, regeneration)
"""

import math
import random
from typing import List, Tuple, Optional, Dict
from game.settings import *

from game.systems.storage import (
    SettlementStorage, StorageBackedDict, StorageLocation,
    generate_storage_for_settlement, seed_initial_stock,
    find_nearest_storage,
)
from game.data.pricing import (
    SettlementPriceBoard, calculate_local_price,
    buy_from_market, sell_to_market, get_price_gossip,
    calculate_transport_cost, ALL_TRADEABLE_GOODS,
)


class WorldEffects:
    """Processes world change events and modifies tiles accordingly.

    Persistent state dicts track the economic and military state of every
    settlement for the lifetime of the world.
    """

    def __init__(self, world):
        self.world = world
        self._pending_events: List[Dict] = []
        self._event_log: List[str] = []

        # --- A. Building Ownership & Habitation ---
        # Maps (settlement_name, building_idx) -> owner_name
        self._building_owners: Dict[Tuple[str, int], str] = {}

        # --- B. Farms and Croplands ---
        # Maps settlement_name -> list of {x, y, radius, crop_type, health}
        self._farms: Dict[str, List[Dict]] = {}

        # --- C. Stores and Supplies (physical storage system) ---
        # Maps settlement_name -> SettlementStorage (physical locations)
        self._settlement_storage: Dict[str, SettlementStorage] = {}
        # Maps settlement_name -> StorageBackedDict (compat wrapper)
        self._settlement_stores: Dict[str, Dict[str, int]] = {}

        # --- D. Domestic Animals and Resources ---
        # Maps settlement_name -> {cows, sheep, horses, chickens}
        self._settlement_livestock: Dict[str, Dict[str, int]] = {}
        # Maps settlement_name -> {forest_tiles, ore_tiles, water_access}
        self._local_resources: Dict[str, Dict] = {}

        # --- E. Castles, Defenses, Military ---
        # Maps settlement_name -> {kingdom, troops, supplies}
        self._garrisons: Dict[str, Dict] = {}
        # Maps settlement_name -> {level: int, wall_tiles: list of (x,y)}
        self._fortifications: Dict[str, Dict] = {}

        # --- Migration tracking ---
        # List of {npc_name, from_settlement, to_settlement, day}
        self._migration_log: List[Dict] = []

        # --- F. Price Boards (location-based pricing) ---
        # Maps settlement_name -> SettlementPriceBoard
        self._price_boards: Dict[str, SettlementPriceBoard] = {}

    # ------------------------------------------------------------------
    # Helper: ensure settlement tracking dicts exist
    # ------------------------------------------------------------------

    def _ensure_storage(self, name: str) -> SettlementStorage:
        """Return (and lazily create) the physical SettlementStorage."""
        if name not in self._settlement_storage:
            storage = SettlementStorage(name)
            # Find the settlement plan so we can size storage properly
            sp = self._find_settlement_plan(name)
            if sp:
                generate_storage_for_settlement(sp, storage)
            else:
                # No plan found — create minimal fallback storage
                loc = StorageLocation(
                    name=f"{name} General Store",
                    kind="market_stall",
                    x=0, y=0, building_idx=0, capacity=500,
                )
                loc.allowed_goods = ["any"]
                storage.locations.append(loc)
            seed_initial_stock(storage)
            self._settlement_storage[name] = storage
        return self._settlement_storage[name]

    def _ensure_stores(self, name: str) -> Dict[str, int]:
        """Return (and lazily create) the supply store for a settlement.

        Returns a StorageBackedDict that transparently reads/writes from
        the physical SettlementStorage while keeping the old dict API.

        Stores hold both abstract resource categories (food, wood, ore, ...)
        AND specific item names from the ITEMS dict (Iron Ingot, Bread, ...).
        The supply-chain crafting system reads/writes specific item names;
        the legacy abstract categories are kept for backward compatibility.
        """
        if name not in self._settlement_stores:
            storage = self._ensure_storage(name)
            self._settlement_stores[name] = StorageBackedDict(storage)
        return self._settlement_stores[name]

    def _ensure_livestock(self, name: str) -> Dict[str, int]:
        if name not in self._settlement_livestock:
            self._settlement_livestock[name] = {
                "cows": 0, "sheep": 0, "horses": 0, "chickens": 0,
            }
        return self._settlement_livestock[name]

    def _ensure_resources(self, name: str) -> Dict:
        if name not in self._local_resources:
            self._local_resources[name] = {
                "forest_tiles": 0, "ore_tiles": 0, "water_access": False,
            }
        return self._local_resources[name]

    def _ensure_garrison(self, name: str) -> Dict:
        if name not in self._garrisons:
            self._garrisons[name] = {
                "kingdom": "", "troops": 0, "supplies": 0,
            }
        return self._garrisons[name]

    def _ensure_fortification(self, name: str) -> Dict:
        if name not in self._fortifications:
            self._fortifications[name] = {
                "level": 0, "wall_tiles": [],
            }
        return self._fortifications[name]

    def _find_settlement_plan(self, name: str):
        """Look up the SettlementPlan object by name, or None (cached)."""
        if not hasattr(self.world, 'plan'):
            return None
        # Build name -> plan cache on first call
        if not hasattr(self, '_settlement_plan_cache'):
            self._settlement_plan_cache = {sp.name: sp for sp in self.world.plan.settlements}
        return self._settlement_plan_cache.get(name)

    def _tile_in_bounds(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.world.width and 0 <= ty < self.world.height

    # ------------------------------------------------------------------
    # Public API: Building Ownership & Habitation (A)
    # ------------------------------------------------------------------

    def assign_building_owner(self, settlement_name: str, building_idx: int,
                              owner_name: str):
        """Record that *owner_name* owns/lives in building *building_idx*."""
        self._building_owners[(settlement_name, building_idx)] = owner_name
        self._event_log.append(
            f"{owner_name} now owns building #{building_idx} in {settlement_name}")

    def evict_building(self, settlement_name: str, building_idx: int,
                       reason: str = "unknown"):
        """Remove the owner from a building (war, crime, death)."""
        key = (settlement_name, building_idx)
        old_owner = self._building_owners.pop(key, None)
        if old_owner:
            self._event_log.append(
                f"{old_owner} evicted from building #{building_idx} "
                f"in {settlement_name}: {reason}")

    def get_building_owner(self, settlement_name: str,
                           building_idx: int) -> Optional[str]:
        return self._building_owners.get((settlement_name, building_idx))

    def move_inhabitant(self, npc_name: str, from_settlement: str,
                        to_settlement: str):
        """Track an NPC migrating between settlements."""
        # Evict from any owned building in the old settlement
        keys_to_remove = [
            k for k, v in self._building_owners.items()
            if v == npc_name and k[0] == from_settlement
        ]
        for k in keys_to_remove:
            del self._building_owners[k]

        self._migration_log.append({
            "npc_name": npc_name,
            "from_settlement": from_settlement,
            "to_settlement": to_settlement,
        })
        self._event_log.append(
            f"{npc_name} migrated from {from_settlement} to {to_settlement}")

    # ------------------------------------------------------------------
    # Public API: Farms and Croplands (B)
    # ------------------------------------------------------------------

    def create_farm(self, x: int, y: int, radius: int, crop_type: str,
                    settlement_name: str = ""):
        """Convert GRASS tiles around (x, y) into FARMLAND.

        Registers the farm in self._farms under *settlement_name*.
        """
        count = 0
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                tx, ty = x + dx, y + dy
                if self._tile_in_bounds(tx, ty):
                    tile = self.world.tiles[ty][tx]
                    if tile == GRASS:
                        self.world.tiles[ty][tx] = FARMLAND
                        count += 1

        farm_entry = {
            "x": x, "y": y, "radius": radius,
            "crop_type": crop_type, "health": 100,
        }
        self._farms.setdefault(settlement_name, []).append(farm_entry)
        self._event_log.append(
            f"Farm ({crop_type}) created at ({x},{y}) r={radius}, "
            f"{count} tiles converted")

    def destroy_farm(self, x: int, y: int, radius: int):
        """Revert FARMLAND / WHEAT_FIELD / TILLED_SOIL back to GRASS."""
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                tx, ty = x + dx, y + dy
                if self._tile_in_bounds(tx, ty):
                    tile = self.world.tiles[ty][tx]
                    if tile in (FARMLAND, WHEAT_FIELD, TILLED_SOIL):
                        self.world.tiles[ty][tx] = GRASS

        # Remove matching farm entries
        for sname, farms in self._farms.items():
            self._farms[sname] = [
                f for f in farms
                if not (f["x"] == x and f["y"] == y and f["radius"] == radius)
            ]

        self._event_log.append(
            f"Farm destroyed at ({x},{y}) r={radius}")

    def harvest_crops(self, settlement_name: str):
        """Convert mature WHEAT_FIELD tiles back to TILLED_SOIL and add food."""
        farms = self._farms.get(settlement_name, [])
        total_harvested = 0
        for farm in farms:
            fx, fy, fr = farm["x"], farm["y"], farm["radius"]
            for dy in range(-fr, fr + 1):
                for dx in range(-fr, fr + 1):
                    if dx * dx + dy * dy > fr * fr:
                        continue
                    tx, ty = fx + dx, fy + dy
                    if self._tile_in_bounds(tx, ty):
                        if self.world.tiles[ty][tx] == WHEAT_FIELD:
                            self.world.tiles[ty][tx] = TILLED_SOIL
                            total_harvested += 1

        if total_harvested > 0:
            stores = self._ensure_stores(settlement_name)
            stores["food"] += total_harvested
            self._event_log.append(
                f"{settlement_name} harvested {total_harvested} food from farms")

    def seasonal_growth(self, settlement_name: str):
        """Progress farm tiles: TILLED_SOIL -> FARMLAND -> WHEAT_FIELD."""
        farms = self._farms.get(settlement_name, [])
        grown = 0
        for farm in farms:
            if farm["health"] <= 0:
                continue
            fx, fy, fr = farm["x"], farm["y"], farm["radius"]
            for dy in range(-fr, fr + 1):
                for dx in range(-fr, fr + 1):
                    if dx * dx + dy * dy > fr * fr:
                        continue
                    tx, ty = fx + dx, fy + dy
                    if self._tile_in_bounds(tx, ty):
                        tile = self.world.tiles[ty][tx]
                        if tile == TILLED_SOIL:
                            self.world.tiles[ty][tx] = FARMLAND
                            grown += 1
                        elif tile == FARMLAND:
                            self.world.tiles[ty][tx] = WHEAT_FIELD
                            grown += 1
        if grown > 0:
            self._event_log.append(
                f"{settlement_name}: {grown} crop tiles grew")

    # ------------------------------------------------------------------
    # Public API: Stores and Supplies (C)
    # ------------------------------------------------------------------

    def consume_supplies(self, settlement_name: str, food_amount: int):
        """Daily food consumption for the settlement population."""
        stores = self._ensure_stores(settlement_name)
        stores["food"] = max(0, stores["food"] - food_amount)

    def produce_supplies(self, settlement_name: str, resource: str,
                         amount: int):
        """Add produced goods to settlement stores."""
        stores = self._ensure_stores(settlement_name)
        stores[resource] = stores.get(resource, 0) + amount

    def trade_supplies(self, from_settlement: str, to_settlement: str,
                       resource: str, amount: int, gold_cost: int):
        """Move resources between settlements via physical caravan trade.

        Instead of instantly teleporting goods, this now:
        1. Removes goods from source settlement stores
        2. Creates a physical trade caravan via GoodsTransportManager
        3. Goods arrive at destination when caravan physically walks there

        Falls back to instant transfer if no transport manager is available.
        """
        src = self._ensure_stores(from_settlement)

        actual = min(amount, src.get(resource, 0))
        if actual <= 0:
            return

        # Remove from source immediately (committed to transit)
        src[resource] = src.get(resource, 0) - actual

        # Try to use the physical goods transport system
        gt = getattr(self, '_goods_transport', None)
        if gt is not None:
            # Find settlement positions for caravan routing
            from_sp = self._find_settlement_plan(from_settlement)
            to_sp = self._find_settlement_plan(to_settlement)
            if from_sp and to_sp:
                # Choose vehicle type based on amount
                if actual <= 10:
                    vtype = "handcart"
                elif actual <= 30:
                    vtype = "cart"
                else:
                    vtype = "wagon"

                gt.request_trade_caravan(
                    from_settlement, to_settlement,
                    resource, actual, gold_cost,
                    float(from_sp.x), float(from_sp.y),
                    float(to_sp.x), float(to_sp.y),
                    vehicle_type=vtype)

                self._event_log.append(
                    f"Trade caravan dispatched: {actual} {resource} from "
                    f"{from_settlement} to {to_settlement} ({gold_cost} gold)")
                return

        # Fallback: instant transfer if no transport system
        dst = self._ensure_stores(to_settlement)
        dst[resource] = dst.get(resource, 0) + actual
        dst["gold"] = max(0, dst["gold"] - gold_cost)
        src["gold"] = src.get("gold", 0) + gold_cost

        self._event_log.append(
            f"Trade: {actual} {resource} from {from_settlement} "
            f"to {to_settlement} for {gold_cost} gold")

    def _deplete_forest_tile(self, settlement_name: str):
        """Convert one FOREST tile near a settlement to TREE_STUMP."""
        sp = self._find_settlement_plan(settlement_name)
        if not sp:
            return
        rng = random.Random(hash(settlement_name) ^ hash("deplete"))
        radius = sp.radius + 10
        candidates = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                tx, ty = sp.x + dx, sp.y + dy
                if self._tile_in_bounds(tx, ty):
                    if self.world.tiles[ty][tx] == FOREST:
                        candidates.append((tx, ty))
        if candidates:
            cx, cy = rng.choice(candidates)
            self.world.tiles[cy][cx] = TREE_STUMP
            res = self._ensure_resources(settlement_name)
            res["forest_tiles"] = max(0, res["forest_tiles"] - 1)
            self._event_log.append(
                f"{settlement_name}: forest tile depleted at ({cx},{cy})")

    def _deplete_ore_tile(self, settlement_name: str):
        """Convert one ORE_VEIN tile near a settlement to ROCKY_GROUND."""
        sp = self._find_settlement_plan(settlement_name)
        if not sp:
            return
        rng = random.Random(hash(settlement_name) ^ hash("ore"))
        radius = sp.radius + 15
        candidates = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                tx, ty = sp.x + dx, sp.y + dy
                if self._tile_in_bounds(tx, ty):
                    if self.world.tiles[ty][tx] == ORE_VEIN:
                        candidates.append((tx, ty))
        if candidates:
            cx, cy = rng.choice(candidates)
            self.world.tiles[cy][cx] = ROCKY_GROUND
            res = self._ensure_resources(settlement_name)
            res["ore_tiles"] = max(0, res["ore_tiles"] - 1)
            self._event_log.append(
                f"{settlement_name}: ore vein depleted at ({cx},{cy})")

    def consume_resource(self, settlement_name: str, resource_type: str):
        """Consume a natural resource (logging or mining)."""
        if resource_type == "wood":
            self._deplete_forest_tile(settlement_name)
            self.produce_supplies(settlement_name, "wood", 3)
        elif resource_type == "ore":
            self._deplete_ore_tile(settlement_name)
            self.produce_supplies(settlement_name, "ore", 2)

    def regrow_resource(self, settlement_name: str, resource_type: str):
        """Slowly regenerate depleted resources (TREE_STUMP -> FOREST)."""
        sp = self._find_settlement_plan(settlement_name)
        if not sp:
            return
        rng = random.Random(hash(settlement_name) ^ hash("regrow"))
        radius = sp.radius + 15

        if resource_type == "wood":
            target_tile = TREE_STUMP
            result_tile = FOREST
        else:
            return  # only forests regrow naturally

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                tx, ty = sp.x + dx, sp.y + dy
                if self._tile_in_bounds(tx, ty):
                    if self.world.tiles[ty][tx] == target_tile:
                        # 10% chance per stump per regrowth call
                        if rng.random() < 0.10:
                            self.world.tiles[ty][tx] = result_tile
                            res = self._ensure_resources(settlement_name)
                            res["forest_tiles"] = res.get("forest_tiles", 0) + 1

    # ------------------------------------------------------------------
    # Public API: Domestic Animals (D)
    # ------------------------------------------------------------------

    def add_livestock(self, settlement_name: str, animal: str, count: int):
        livestock = self._ensure_livestock(settlement_name)
        livestock[animal] = livestock.get(animal, 0) + count

    def remove_livestock(self, settlement_name: str, animal: str, count: int):
        livestock = self._ensure_livestock(settlement_name)
        livestock[animal] = max(0, livestock.get(animal, 0) - count)

    def _breed_livestock(self, settlement_name: str, rng: random.Random):
        """Slow natural increase of livestock."""
        livestock = self._ensure_livestock(settlement_name)
        for animal, count in livestock.items():
            if count >= 2:
                # ~5% chance of +1 per breeding call
                if rng.random() < 0.05:
                    livestock[animal] += 1

    def survey_local_resources(self, settlement_name: str):
        """Count FOREST, ORE_VEIN, and WATER tiles near a settlement."""
        sp = self._find_settlement_plan(settlement_name)
        if not sp:
            return
        radius = sp.radius + 15
        forest = ore = 0
        water = False
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                tx, ty = sp.x + dx, sp.y + dy
                if self._tile_in_bounds(tx, ty):
                    tile = self.world.tiles[ty][tx]
                    if tile in (FOREST, DENSE_FOREST):
                        forest += 1
                    elif tile == ORE_VEIN:
                        ore += 1
                    elif tile in (WATER, SHALLOW_WATER):
                        water = True
        self._local_resources[settlement_name] = {
            "forest_tiles": forest,
            "ore_tiles": ore,
            "water_access": water,
        }

    # ------------------------------------------------------------------
    # Public API: Castles, Defenses, Military (E)
    # ------------------------------------------------------------------

    def build_fortification(self, settlement_name: str,
                            fort_type: str = "wall"):
        """Build BUILT_WALL tiles around a settlement perimeter.

        *fort_type*: "wall" (basic), "tower" (adds pillar corners).
        """
        sp = self._find_settlement_plan(settlement_name)
        if not sp:
            return

        fort = self._ensure_fortification(settlement_name)
        radius = sp.radius
        wall_tiles: list = fort["wall_tiles"]

        # Place walls on the perimeter ring
        placed = 0
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                dist_sq = dx * dx + dy * dy
                # Ring at ~radius distance (within 1 tile band)
                if abs(dist_sq - radius * radius) > radius * 2:
                    continue
                tx, ty = sp.x + dx, sp.y + dy
                if self._tile_in_bounds(tx, ty):
                    tile = self.world.tiles[ty][tx]
                    if tile in (GRASS, SAND, DIRT_TRACK):
                        if fort_type == "tower" and (abs(dx) + abs(dy)) % 8 == 0:
                            self.world.tiles[ty][tx] = PILLAR
                        else:
                            self.world.tiles[ty][tx] = BUILT_WALL
                        wall_tiles.append((tx, ty))
                        placed += 1

        fort["level"] = max(fort["level"], 1)
        self._event_log.append(
            f"Fortification ({fort_type}) built around {settlement_name}: "
            f"{placed} wall tiles")

    def upgrade_defense(self, settlement_name: str):
        """Strengthen existing fortifications (thicker walls, towers)."""
        sp = self._find_settlement_plan(settlement_name)
        if not sp:
            return

        fort = self._ensure_fortification(settlement_name)
        old_level = fort["level"]
        fort["level"] = min(5, old_level + 1)

        # Add guard towers at cardinal directions
        if fort["level"] >= 2:
            for angle_deg in (0, 90, 180, 270):
                angle = math.radians(angle_deg)
                tower_x = int(sp.x + math.cos(angle) * sp.radius)
                tower_y = int(sp.y + math.sin(angle) * sp.radius)
                for oy in range(-1, 2):
                    for ox in range(-1, 2):
                        tx, ty = tower_x + ox, tower_y + oy
                        if self._tile_in_bounds(tx, ty):
                            if ox == 0 and oy == 0:
                                self.world.tiles[ty][tx] = PILLAR
                            else:
                                tile = self.world.tiles[ty][tx]
                                if tile in (GRASS, SAND, DIRT_TRACK):
                                    self.world.tiles[ty][tx] = BUILT_WALL
                                    fort["wall_tiles"].append((tx, ty))

        self._event_log.append(
            f"{settlement_name} defenses upgraded: level {old_level} -> "
            f"{fort['level']}")

    def deploy_troops(self, kingdom_name: str, settlement_name: str,
                      count: int):
        """Deploy garrison troops to a settlement."""
        garrison = self._ensure_garrison(settlement_name)
        garrison["kingdom"] = kingdom_name
        garrison["troops"] += count
        self._event_log.append(
            f"{count} troops from {kingdom_name} deployed to {settlement_name} "
            f"(total: {garrison['troops']})")

    def withdraw_troops(self, kingdom_name: str, settlement_name: str,
                        count: int):
        """Withdraw garrison troops from a settlement."""
        garrison = self._ensure_garrison(settlement_name)
        actual = min(count, garrison["troops"])
        garrison["troops"] -= actual
        if garrison["troops"] <= 0:
            garrison["kingdom"] = ""
        self._event_log.append(
            f"{actual} troops withdrawn from {settlement_name} "
            f"(remaining: {garrison['troops']})")

    def damage_fortification(self, settlement_name: str,
                             severity: float = 0.3):
        """Damage walls during a siege or attack.

        *severity* 0.0-1.0: fraction of wall tiles converted to RUBBLE.
        """
        fort = self._ensure_fortification(settlement_name)
        rng = random.Random(hash(settlement_name) ^ hash("dmg"))
        destroyed = 0
        surviving = []
        for (tx, ty) in fort["wall_tiles"]:
            if rng.random() < severity:
                if self._tile_in_bounds(tx, ty):
                    self.world.tiles[ty][tx] = RUBBLE
                destroyed += 1
            else:
                surviving.append((tx, ty))
        fort["wall_tiles"] = surviving
        if destroyed > len(surviving):
            fort["level"] = max(0, fort["level"] - 1)
        self._event_log.append(
            f"{settlement_name} fortifications damaged: {destroyed} wall tiles "
            f"destroyed ({severity:.0%} severity)")

    # ------------------------------------------------------------------
    # Event queue processing
    # ------------------------------------------------------------------

    def queue_event(self, event: Dict):
        """Queue a world change event for processing.

        Event dict keys:
            type: str -- event type
            ... type-specific fields
        """
        self._pending_events.append(event)

    def process_events(self):
        """Process all queued events, modifying world tiles."""
        _dispatch = {
            "destroy_building": self._destroy_building,
            "damage_settlement": self._damage_settlement,
            "build_structure": self._build_structure,
            "found_settlement": self._found_settlement,
            "damage_road": self._damage_road,
            "repair_road": self._repair_road,
            "change_ownership": self._change_ownership,
            "raze_settlement": self._raze_settlement,
            "fire": self._spread_fire,
            "grow_settlement": self._grow_settlement,
            "create_farm": self._handle_create_farm,
            "destroy_farm": self._handle_destroy_farm,
            "harvest_crops": self._handle_harvest_crops,
            "seasonal_growth": self._handle_seasonal_growth,
            "consume_supplies": self._handle_consume_supplies,
            "produce_supplies": self._handle_produce_supplies,
            "trade_supplies": self._handle_trade_supplies,
            "consume_resource": self._handle_consume_resource,
            "build_fortification": self._handle_build_fortification,
            "upgrade_defense": self._handle_upgrade_defense,
            "deploy_troops": self._handle_deploy_troops,
            "withdraw_troops": self._handle_withdraw_troops,
            "damage_fortification": self._handle_damage_fortification,
            "move_inhabitant": self._handle_move_inhabitant,
            "assign_owner": self._handle_assign_owner,
            "evict_building": self._handle_evict_building,
        }

        for event in self._pending_events:
            etype = event.get("type", "")
            handler = _dispatch.get(etype)
            if handler:
                try:
                    handler(event)
                except Exception as e:
                    self._event_log.append(f"Error processing {etype}: {e}")
            else:
                self._event_log.append(f"Unknown event type: {etype}")

        self._pending_events.clear()

    # ------------------------------------------------------------------
    # Event-dict handlers for new event types
    # ------------------------------------------------------------------

    def _handle_create_farm(self, event):
        self.create_farm(
            event["x"], event["y"], event.get("radius", 5),
            event.get("crop_type", "wheat"),
            settlement_name=event.get("settlement_name", ""))

    def _handle_destroy_farm(self, event):
        self.destroy_farm(event["x"], event["y"], event.get("radius", 5))

    def _handle_harvest_crops(self, event):
        self.harvest_crops(event["settlement_name"])

    def _handle_seasonal_growth(self, event):
        self.seasonal_growth(event["settlement_name"])

    def _handle_consume_supplies(self, event):
        self.consume_supplies(event["settlement_name"],
                              event.get("food_amount", 1))

    def _handle_produce_supplies(self, event):
        self.produce_supplies(event["settlement_name"],
                              event["resource"], event["amount"])

    def _handle_trade_supplies(self, event):
        self.trade_supplies(
            event["from_settlement"], event["to_settlement"],
            event["resource"], event["amount"], event.get("gold_cost", 0))

    def _handle_consume_resource(self, event):
        self.consume_resource(event["settlement_name"],
                              event["resource_type"])

    def _handle_build_fortification(self, event):
        self.build_fortification(event["settlement_name"],
                                 event.get("fort_type", "wall"))

    def _handle_upgrade_defense(self, event):
        self.upgrade_defense(event["settlement_name"])

    def _handle_deploy_troops(self, event):
        self.deploy_troops(event["kingdom_name"], event["settlement_name"],
                           event["count"])

    def _handle_withdraw_troops(self, event):
        self.withdraw_troops(event["kingdom_name"], event["settlement_name"],
                             event["count"])

    def _handle_damage_fortification(self, event):
        self.damage_fortification(event["settlement_name"],
                                  event.get("severity", 0.3))

    def _handle_move_inhabitant(self, event):
        self.move_inhabitant(event["npc_name"],
                             event["from_settlement"],
                             event["to_settlement"])

    def _handle_assign_owner(self, event):
        self.assign_building_owner(event["settlement_name"],
                                   event["building_idx"],
                                   event["owner_name"])

    def _handle_evict_building(self, event):
        self.evict_building(event["settlement_name"],
                            event["building_idx"],
                            event.get("reason", "unknown"))

    # ------------------------------------------------------------------
    # Original event handlers (unchanged logic, preserved)
    # ------------------------------------------------------------------

    def _destroy_building(self, event):
        """Replace a building's tiles with RUBBLE.

        Event: {"type": "destroy_building", "x": int, "y": int,
                "w": int, "h": int, "reason": str}
        """
        x, y = event["x"], event["y"]
        w, h = event["w"], event["h"]
        reason = event.get("reason", "unknown")

        for dy in range(h):
            for dx in range(w):
                tx, ty = x + dx, y + dy
                if self._tile_in_bounds(tx, ty):
                    old = self.world.tiles[ty][tx]
                    if old in (WALL, FLOOR, DOOR, TABLE, BED, CHEST,
                               STAIRS_UP, STAIRS_DOWN, WINDOW):
                        self.world.tiles[ty][tx] = RUBBLE

        self._event_log.append(
            f"Building destroyed at ({x},{y}) {w}x{h}: {reason}")

    def _damage_settlement(self, event):
        """Partially damage a settlement -- destroy some buildings, damage walls.

        Event: {"type": "damage_settlement", "settlement_name": str,
                "severity": float (0-1), "attacker": str}
        """
        name = event["settlement_name"]
        severity = event.get("severity", 0.3)
        attacker = event.get("attacker", "unknown")

        sp = self._find_settlement_plan(name)
        if not sp:
            return

        rng = random.Random(hash(name) ^ hash(attacker))

        # Damage a proportion of buildings
        for bld in sp.buildings:
            if rng.random() < severity:
                bx, by = bld['x'], bld['y']
                bw, bh = bld['w'], bld['h']
                for dy in range(bh):
                    for dx in range(bw):
                        tx, ty = bx + dx, by + dy
                        if rng.random() < severity * 0.5:
                            if self._tile_in_bounds(tx, ty):
                                self.world.tiles[ty][tx] = RUBBLE

        self._event_log.append(
            f"Settlement {name} damaged ({severity:.0%}) by {attacker}")

    def _build_structure(self, event):
        """Build a new structure at a location.

        Event: {"type": "build_structure", "x": int, "y": int,
                "w": int, "h": int, "kind": str}
        """
        x, y = event["x"], event["y"]
        w, h = event["w"], event["h"]
        kind = event.get("kind", "house")

        # Simple box building
        for dy in range(h):
            for dx in range(w):
                tx, ty = x + dx, y + dy
                if self._tile_in_bounds(tx, ty):
                    if dx == 0 or dx == w - 1 or dy == 0 or dy == h - 1:
                        if dx == w // 2 and dy == h - 1:
                            self.world.tiles[ty][tx] = DOOR
                        else:
                            self.world.tiles[ty][tx] = WALL
                    else:
                        self.world.tiles[ty][tx] = FLOOR

        self._event_log.append(
            f"New {kind} built at ({x},{y}) {w}x{h}")

    def _found_settlement(self, event):
        """Found a new settlement -- place buildings and roads.

        Event: {"type": "found_settlement", "x": int, "y": int,
                "name": str, "kind": str, "kingdom": str}
        """
        x, y = event["x"], event["y"]
        name = event.get("name", "New Settlement")
        kind = event.get("kind", "hamlet")
        kingdom = event.get("kingdom", "")

        rng = random.Random(hash(name))

        # Clear area
        radius = {"hamlet": 8, "village": 15, "town": 25}.get(kind, 10)
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                tx, ty = x + dx, y + dy
                if (self._tile_in_bounds(tx, ty)
                        and dx * dx + dy * dy <= radius * radius):
                    tile = self.world.tiles[ty][tx]
                    if tile in (FOREST, DENSE_FOREST, SWAMP):
                        self.world.tiles[ty][tx] = GRASS

        # Place 3-5 small buildings
        num_buildings = rng.randint(3, 5)
        for _ in range(num_buildings):
            bw = rng.randint(4, 6)
            bh = rng.randint(4, 6)
            for attempt in range(20):
                bx = x + rng.randint(-radius // 2, radius // 2)
                by = y + rng.randint(-radius // 2, radius // 2)
                self._build_structure({
                    "type": "build_structure",
                    "x": bx, "y": by, "w": bw, "h": bh,
                    "kind": "house",
                })
                break

        # Place roads (cross through center)
        for dx in range(-radius, radius + 1):
            tx = x + dx
            if self._tile_in_bounds(tx, y):
                if self.world.tiles[y][tx] == GRASS:
                    self.world.tiles[y][tx] = ROAD
        for dy in range(-radius, radius + 1):
            ty = y + dy
            if self._tile_in_bounds(x, ty):
                if self.world.tiles[ty][x] == GRASS:
                    self.world.tiles[ty][x] = ROAD

        # Add to plan if available
        if hasattr(self.world, 'plan'):
            from game.world.world_plan import SettlementPlan
            sp = SettlementPlan(
                name=name, kind=kind, x=x, y=y,
                radius=radius, region="", race="Human",
                population=rng.randint(3, 10),
            )
            self.world.plan.settlements.append(sp)

        # Initialize stores and resources for the new settlement
        self._ensure_stores(name)
        self._ensure_livestock(name)
        self.survey_local_resources(name)

        # Create initial farm
        farm_x = x + rng.randint(-radius // 2, radius // 2)
        farm_y = y + rng.randint(-radius // 2, radius // 2)
        self.create_farm(farm_x, farm_y, 3, "wheat",
                         settlement_name=name)

        self._event_log.append(
            f"Settlement '{name}' ({kind}) founded at ({x},{y}) by {kingdom}")

    def _damage_road(self, event):
        """Degrade road tiles to dirt or grass.

        Event: {"type": "damage_road", "x1": int, "y1": int,
                "x2": int, "y2": int}
        """
        x1, y1 = event["x1"], event["y1"]
        x2, y2 = event["x2"], event["y2"]
        rng = random.Random(x1 * 31 + y1 * 97)

        dist = max(1, int(math.sqrt((x2 - x1)**2 + (y2 - y1)**2)))
        for i in range(dist + 1):
            t = i / max(1, dist)
            tx = int(x1 + (x2 - x1) * t)
            ty = int(y1 + (y2 - y1) * t)
            if self._tile_in_bounds(tx, ty):
                tile = self.world.tiles[ty][tx]
                if tile in (ROAD, COBBLESTONE):
                    if rng.random() < 0.3:
                        self.world.tiles[ty][tx] = DIRT_TRACK
                elif tile == GRAVEL_ROAD:
                    if rng.random() < 0.3:
                        self.world.tiles[ty][tx] = GRASS

        self._event_log.append(
            f"Road damaged from ({x1},{y1}) to ({x2},{y2})")

    def _repair_road(self, event):
        """Repair road tiles.

        Event: {"type": "repair_road", "x1": int, "y1": int,
                "x2": int, "y2": int, "road_type": int}
        """
        x1, y1 = event["x1"], event["y1"]
        x2, y2 = event["x2"], event["y2"]
        road_type = event.get("road_type", ROAD)

        dist = max(1, int(math.sqrt((x2 - x1)**2 + (y2 - y1)**2)))
        for i in range(dist + 1):
            t = i / max(1, dist)
            tx = int(x1 + (x2 - x1) * t)
            ty = int(y1 + (y2 - y1) * t)
            if self._tile_in_bounds(tx, ty):
                tile = self.world.tiles[ty][tx]
                if tile in (GRASS, DIRT_TRACK, GRAVEL_ROAD):
                    self.world.tiles[ty][tx] = road_type

        self._event_log.append(
            f"Road repaired from ({x1},{y1}) to ({x2},{y2})")

    def _change_ownership(self, event):
        """Change settlement ownership to a new kingdom.

        Event: {"type": "change_ownership", "settlement_name": str,
                "new_kingdom": str, "old_kingdom": str}
        """
        name = event["settlement_name"]
        new_kingdom = event["new_kingdom"]
        old_kingdom = event.get("old_kingdom", "")

        if hasattr(self.world, 'plan'):
            for kdata in self.world.plan.kingdoms:
                if kdata["name"] == old_kingdom:
                    if name in kdata["territory_settlements"]:
                        kdata["territory_settlements"].remove(name)
                if kdata["name"] == new_kingdom:
                    if name not in kdata["territory_settlements"]:
                        kdata["territory_settlements"].append(name)

        # Update garrison allegiance
        garrison = self._ensure_garrison(name)
        garrison["kingdom"] = new_kingdom

        self._event_log.append(
            f"Settlement {name} now controlled by {new_kingdom} "
            f"(was {old_kingdom})")

    def _raze_settlement(self, event):
        """Completely destroy a settlement -- all buildings become rubble.

        Event: {"type": "raze_settlement", "settlement_name": str,
                "attacker": str}
        """
        name = event["settlement_name"]
        attacker = event.get("attacker", "unknown")

        sp = self._find_settlement_plan(name)
        if not sp:
            return

        # Destroy all buildings
        for bld in sp.buildings:
            self._destroy_building({
                "type": "destroy_building",
                "x": bld["x"], "y": bld["y"],
                "w": bld["w"], "h": bld["h"],
                "reason": f"razed by {attacker}",
            })
        sp.kind = "ruins"
        sp.population = 0

        # Destroy fortifications
        self.damage_fortification(name, severity=1.0)

        # Clear garrison
        garrison = self._ensure_garrison(name)
        garrison["troops"] = 0
        garrison["kingdom"] = ""

        # Destroy farms
        for farm in self._farms.get(name, []):
            self.destroy_farm(farm["x"], farm["y"], farm["radius"])
        self._farms[name] = []

        # Evict all building owners
        keys_to_remove = [
            k for k in self._building_owners if k[0] == name
        ]
        for k in keys_to_remove:
            del self._building_owners[k]

        self._event_log.append(
            f"Settlement {name} razed by {attacker}")

    def _spread_fire(self, event):
        """Spread fire to flammable tiles in a radius.

        Event: {"type": "fire", "x": int, "y": int, "radius": int}
        """
        x, y = event["x"], event["y"]
        radius = event.get("radius", 3)
        rng = random.Random(x * 37 + y * 71)

        flammable = {FOREST, DENSE_FOREST, FARMLAND, WHEAT_FIELD}
        burns_to = {
            FOREST: TREE_STUMP,
            DENSE_FOREST: TREE_STUMP,
            FARMLAND: TILLED_SOIL,
            WHEAT_FIELD: TILLED_SOIL,
        }

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                tx, ty = x + dx, y + dy
                if self._tile_in_bounds(tx, ty):
                    tile = self.world.tiles[ty][tx]
                    if tile in flammable and rng.random() < 0.6:
                        self.world.tiles[ty][tx] = burns_to.get(tile, GRASS)

        self._event_log.append(f"Fire at ({x},{y}) radius {radius}")

    def _grow_settlement(self, event):
        """Add a new building to an existing settlement.

        Event: {"type": "grow_settlement", "settlement_name": str}
        """
        name = event["settlement_name"]
        sp = self._find_settlement_plan(name)
        if not sp:
            return

        rng = random.Random(hash(name) ^ len(sp.buildings))
        bw = rng.randint(4, 7)
        bh = rng.randint(4, 7)

        for attempt in range(30):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(5, sp.radius * 0.8)
            bx = int(sp.x + math.cos(angle) * dist)
            by = int(sp.y + math.sin(angle) * dist)

            clear = True
            for dy in range(bh):
                for dx in range(bw):
                    tx, ty = bx + dx, by + dy
                    if self._tile_in_bounds(tx, ty):
                        if self.world.tiles[ty][tx] not in (GRASS, SAND):
                            clear = False
                            break
                    else:
                        clear = False
                        break
                if not clear:
                    break

            if clear:
                self._build_structure({
                    "type": "build_structure",
                    "x": bx, "y": by, "w": bw, "h": bh,
                    "kind": "house",
                })
                sp.buildings.append({
                    "kind": "house", "name": "New House",
                    "x": bx, "y": by, "w": bw, "h": bh,
                    "bp_tiles": None,
                })
                sp.population += rng.randint(1, 3)
                self._event_log.append(
                    f"Settlement {name} grew: new building at ({bx},{by})")
                break

    # ------------------------------------------------------------------
    # Integration with abstract sim (F) -- expanded
    # ------------------------------------------------------------------

    def process_abstract_events(self, abstract_sim):
        """Read world change events from the abstract sim and queue them.

        Called once per game day to translate abstract simulation results
        into concrete world changes.  Covers:
        - Population growth -> grow_settlement + create_farm
        - Population decline -> abandon buildings
        - Wealth increase -> build new structures
        - Food shortage -> consume forests for farmland
        - Military buildup -> build_fortification
        - Under attack -> damage_settlement + damage_fortification
        - Settlement conquered -> change_ownership + deploy_troops
        - Settlement razed
        - New settlement founded -> found_settlement
        """
        for name, settlement in abstract_sim.abstracts.items():
            sp = self._find_settlement_plan(name)

            # --- Population growth -> grow settlement and expand farms ---
            if getattr(settlement, 'growth_pending', False):
                self.queue_event({
                    "type": "grow_settlement",
                    "settlement_name": name,
                })
                # Also create a new farm if population is large enough
                if sp and settlement.population > 10:
                    rng = random.Random(hash(name) ^ settlement.population)
                    fx = sp.x + rng.randint(-sp.radius, sp.radius)
                    fy = sp.y + rng.randint(-sp.radius, sp.radius)
                    self.queue_event({
                        "type": "create_farm",
                        "x": fx, "y": fy, "radius": 4,
                        "crop_type": "wheat",
                        "settlement_name": name,
                    })
                settlement.growth_pending = False

            # --- Population decline -> abandon buildings ---
            if getattr(settlement, 'decline_pending', False):
                if sp and sp.buildings:
                    # Destroy the last building
                    bld = sp.buildings[-1]
                    self.queue_event({
                        "type": "destroy_building",
                        "x": bld["x"], "y": bld["y"],
                        "w": bld["w"], "h": bld["h"],
                        "reason": "abandoned due to population decline",
                    })
                    # Evict owner
                    bld_idx = len(sp.buildings) - 1
                    self.evict_building(name, bld_idx, "population decline")
                    sp.buildings.pop()
                settlement.decline_pending = False

            # --- Wealth increase -> build new structures ---
            if getattr(settlement, 'wealth_boom', False):
                self.queue_event({
                    "type": "grow_settlement",
                    "settlement_name": name,
                })
                settlement.wealth_boom = False

            # --- Food shortage -> convert forest to farmland ---
            if getattr(settlement, 'food_shortage', False):
                if sp:
                    rng = random.Random(hash(name) ^ 0xF00D)
                    fx = sp.x + rng.randint(-sp.radius, sp.radius)
                    fy = sp.y + rng.randint(-sp.radius, sp.radius)
                    self.queue_event({
                        "type": "create_farm",
                        "x": fx, "y": fy, "radius": 3,
                        "crop_type": "wheat",
                        "settlement_name": name,
                    })
                    # Also log resource for wood
                    self.consume_resource(name, "wood")
                settlement.food_shortage = False

            # --- Military buildup -> build fortification ---
            if getattr(settlement, 'military_buildup', False):
                fort = self._ensure_fortification(name)
                if fort["level"] == 0:
                    self.queue_event({
                        "type": "build_fortification",
                        "settlement_name": name,
                        "fort_type": "wall",
                    })
                else:
                    self.queue_event({
                        "type": "upgrade_defense",
                        "settlement_name": name,
                    })
                settlement.military_buildup = False

            # --- Under attack -> damage settlement + fortifications ---
            if getattr(settlement, 'under_attack', False):
                attacker = getattr(settlement, 'attacker', 'unknown')
                severity = getattr(settlement, 'attack_severity', 0.2)
                self.queue_event({
                    "type": "damage_settlement",
                    "settlement_name": name,
                    "severity": severity,
                    "attacker": attacker,
                })
                # Also damage fortifications
                fort = self._ensure_fortification(name)
                if fort["level"] > 0:
                    self.queue_event({
                        "type": "damage_fortification",
                        "settlement_name": name,
                        "severity": severity,
                    })
                # Reduce garrison
                garrison = self._ensure_garrison(name)
                losses = int(garrison["troops"] * severity * 0.5)
                if losses > 0:
                    garrison["troops"] = max(0, garrison["troops"] - losses)
                settlement.under_attack = False

            # --- Settlement conquered -> change ownership + deploy troops ---
            if getattr(settlement, 'conquered', False):
                new_owner = getattr(settlement, 'conqueror', 'unknown')
                old_owner = getattr(settlement, 'faction', '')
                self.queue_event({
                    "type": "change_ownership",
                    "settlement_name": name,
                    "new_kingdom": new_owner,
                    "old_kingdom": old_owner,
                })
                self.queue_event({
                    "type": "deploy_troops",
                    "kingdom_name": new_owner,
                    "settlement_name": name,
                    "count": max(5, settlement.military_strength),
                })
                settlement.conquered = False

            # --- Settlement razed ---
            if getattr(settlement, 'razed', False):
                self.queue_event({
                    "type": "raze_settlement",
                    "settlement_name": name,
                    "attacker": getattr(settlement, 'attacker', 'unknown'),
                })
                settlement.razed = False

            # --- New settlement founded ---
            if getattr(settlement, 'founding_pending', False):
                founding = getattr(settlement, 'founding_data', {})
                self.queue_event({
                    "type": "found_settlement",
                    "x": founding.get("x", settlement.x),
                    "y": founding.get("y", settlement.y),
                    "name": founding.get("name", f"New {name}"),
                    "kind": founding.get("kind", "hamlet"),
                    "kingdom": founding.get("kingdom", settlement.faction),
                })
                settlement.founding_pending = False

    # ------------------------------------------------------------------
    # Daily update -- called once per game day
    # ------------------------------------------------------------------

    def daily_update(self, time_sys):
        """Run once-per-day economic and ecological updates.

        Handles:
        - Farm seasonal growth (spring/summer = grow, autumn = harvest,
          winter = dormant)
        - Supply consumption (food per population)
        - Resource regeneration (slow forest regrowth)
        - Livestock breeding
        - Defense maintenance costs
        """
        season = getattr(time_sys, 'season', 'spring')

        if not hasattr(self.world, 'plan'):
            return

        # Determine which chunks are loaded (to avoid triggering
        # chunk generation for distant settlements)
        loaded_chunks = set()
        if hasattr(self.world.tiles, 'loaded_chunk_keys'):
            loaded_chunks = self.world.tiles.loaded_chunk_keys()
        chunk_size = getattr(self.world.tiles, 'chunk_size', 200)

        def _is_near_loaded(sx, sy):
            """Check if a settlement is in or near a loaded chunk."""
            if not loaded_chunks:
                return False  # no loaded chunks = skip tile operations
            cx, cy = sx // chunk_size, sy // chunk_size
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    if (cx + dx, cy + dy) in loaded_chunks:
                        return True
            return False

        for sp in self.world.plan.settlements:
            name = sp.name
            population = sp.population
            if population <= 0:
                continue

            rng = random.Random(hash(name) ^ time_sys.day)
            stores = self._ensure_stores(name)

            # === ABSTRACT UPDATES (no tile access — safe for all settlements) ===

            # Daily food consumption
            food_needed = max(1, population // 3)
            self.consume_supplies(name, food_needed)

            # Livestock provide supplemental food
            livestock = self._ensure_livestock(name)
            milk_food = livestock.get("cows", 0) // 2
            egg_food = livestock.get("chickens", 0) // 4
            wool_gold = livestock.get("sheep", 0) // 3
            if milk_food + egg_food > 0:
                stores["food"] += milk_food + egg_food
            if wool_gold > 0:
                stores["gold"] += wool_gold

            # Resource production from cached counts (no tile access)
            res = self._ensure_resources(name)
            if res["forest_tiles"] > 0 and stores.get("wood", 0) < 50:
                stores["wood"] = stores.get("wood", 0) + min(2, res["forest_tiles"] // 10)
            if res["ore_tiles"] > 0 and stores.get("ore", 0) < 30:
                stores["ore"] = stores.get("ore", 0) + min(1, res["ore_tiles"] // 5)
            if res["water_access"]:
                stores["food"] = stores.get("food", 0) + 1

            # Livestock breeding (no tile access)
            self._breed_livestock(name, rng)

            # === TILE-LEVEL UPDATES (only for nearby loaded settlements) ===
            # Skip tile operations for distant settlements to avoid chunk loading
            if _is_near_loaded(sp.x, sp.y):
                if season in ("spring", "summer"):
                    self.seasonal_growth(name)
                elif season == "autumn":
                    self.harvest_crops(name)
                if rng.random() < 0.15:
                    self.regrow_resource(name, "wood")

            # --- Defense maintenance costs ---
            garrison = self._ensure_garrison(name)
            troop_cost = garrison["troops"]  # 1 food per soldier per day
            if troop_cost > 0:
                stores["food"] = max(0, stores["food"] - troop_cost)
                # Gold upkeep: 1 gold per 5 troops
                gold_cost = troop_cost // 5
                stores["gold"] = max(0, stores["gold"] - gold_cost)
                # Consume garrison supplies if food runs out
                if stores["food"] <= 0:
                    garrison["supplies"] = max(
                        0, garrison["supplies"] - troop_cost)
                    # Troops desert if no supplies at all
                    if garrison["supplies"] <= 0 and garrison["troops"] > 0:
                        desertions = max(1, garrison["troops"] // 10)
                        garrison["troops"] -= desertions
                        self._event_log.append(
                            f"{name}: {desertions} troops deserted "
                            f"due to starvation")

            # --- Food crisis detection ---
            # Flag on the abstract settlement so process_abstract_events
            # can react next day
            if stores["food"] <= 0 and population > 3:
                # Try to find the abstract settlement
                for aname, asettlement in self._get_abstracts().items():
                    if aname == name:
                        asettlement.food_shortage = True
                        break

        # --- Update price boards for all tracked settlements ---
        self.update_all_price_boards()

        # --- Foreign trade caravans ---
        try:
            from game.systems.npc_work import get_caravan_system
            caravan = get_caravan_system()
            if hasattr(self.world, 'plan'):
                caravan.daily_update(time_sys, self,
                                     self.world.plan.settlements)
        except Exception:
            pass  # caravan system is optional; don't break the daily tick

    def _get_abstracts(self) -> dict:
        """Try to get the abstract sim's settlement dict for flagging."""
        # The world may have a reference back to the simulation
        sim = getattr(self.world, '_simulation', None)
        if sim and hasattr(sim, 'abstract'):
            return sim.abstract.abstracts
        return {}

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_event_log(self) -> List[str]:
        """Get the log of processed world effect events."""
        return list(self._event_log)

    def get_settlement_stores(self, name: str) -> Dict[str, int]:
        """Get a copy of a settlement's supply stores."""
        stores = self._ensure_stores(name)
        if isinstance(stores, StorageBackedDict):
            return stores.copy()
        return dict(stores)

    def get_stores_ref(self, name: str) -> Dict[str, int]:
        """Get a MUTABLE reference to a settlement's supply stores.

        Use this when you need to modify stores in-place (e.g., paying
        wages from treasury gold, depositing goods from production).
        Returns a StorageBackedDict backed by physical storage.
        """
        return self._ensure_stores(name)

    def get_settlement_storage(self, name: str) -> SettlementStorage:
        """Get the physical SettlementStorage manager for a settlement.

        Use this when you need to work with physical storage locations
        directly (finding which building has ore, walking NPCs to the
        right building, checking capacity, etc.).
        """
        return self._ensure_storage(name)

    def find_storage_location(self, settlement_name: str, good: str,
                              from_x: float, from_y: float,
                              need_space: bool = False,
                              need_stock: bool = False):
        """Find the nearest StorageLocation for *good* in *settlement_name*.

        Args:
            need_space: if True, only locations with room to deposit.
            need_stock: if True, only locations that have the good.

        Returns a StorageLocation or None.
        """
        storage = self._ensure_storage(settlement_name)
        return find_nearest_storage(
            storage, good, from_x, from_y,
            need_space=need_space, need_stock=need_stock)

    def deposit_at_location(self, settlement_name: str, good: str,
                            quantity: int, location=None) -> int:
        """Deposit goods at a specific StorageLocation (or best-fit).

        Returns quantity actually stored.
        """
        storage = self._ensure_storage(settlement_name)
        if location is not None:
            return location.add(good, quantity)
        return storage.deposit(good, quantity)

    def withdraw_from_location(self, settlement_name: str, good: str,
                               quantity: int, location=None):
        """Withdraw goods from a specific StorageLocation (or any).

        Returns (actual_qty, location_used).
        """
        storage = self._ensure_storage(settlement_name)
        if location is not None:
            actual = location.remove(good, quantity)
            return actual, location
        return storage.withdraw(good, quantity)

    def get_storage_summary(self, settlement_name: str) -> Dict:
        """Return a summary of all storage locations and their contents."""
        storage = self._ensure_storage(settlement_name)
        result = {
            "settlement": settlement_name,
            "total_capacity": storage.total_capacity,
            "total_stored": storage.total_stored,
            "space_remaining": storage.space_remaining,
            "locations": [],
        }
        for loc in storage.locations:
            result["locations"].append({
                "name": loc.name,
                "kind": loc.kind,
                "x": loc.x, "y": loc.y,
                "capacity": loc.capacity,
                "stored": loc.total_stored,
                "space": loc.space_remaining,
                "contents": dict(loc.contents),
            })
        return result

    def get_settlement_livestock(self, name: str) -> Dict[str, int]:
        return dict(self._ensure_livestock(name))

    def get_settlement_garrison(self, name: str) -> Dict:
        return dict(self._ensure_garrison(name))

    def get_settlement_fortification(self, name: str) -> Dict:
        return dict(self._ensure_fortification(name))

    def get_settlement_farms(self, name: str) -> List[Dict]:
        return list(self._farms.get(name, []))

    def get_settlement_resources(self, name: str) -> Dict:
        return dict(self._ensure_resources(name))

    def get_migration_log(self) -> List[Dict]:
        return list(self._migration_log)

    # ------------------------------------------------------------------
    # Price Boards — location-based production costs and trade prices
    # ------------------------------------------------------------------

    def get_price_board(self, settlement_name: str) -> SettlementPriceBoard:
        """Return (and lazily create) the price board for a settlement."""
        if settlement_name not in self._price_boards:
            sp = self._find_settlement_plan(settlement_name)
            if sp is None:
                # Create a minimal board with default prices
                class _Stub:
                    name = settlement_name
                    specialization = "general"
                    population = 50
                    npc_spawns = []
                    buildings = []
                sp = _Stub()
            plan = getattr(self.world, 'plan', None)
            if plan is None:
                class _PlanStub:
                    kingdoms = []
                plan = _PlanStub()
            self._price_boards[settlement_name] = SettlementPriceBoard(
                settlement_name, sp, self, plan)
        return self._price_boards[settlement_name]

    def update_all_price_boards(self):
        """Recalculate every tracked price board (called daily)."""
        plan = getattr(self.world, 'plan', None)
        if plan is None:
            return
        for name in list(self._price_boards.keys()):
            sp = self._find_settlement_plan(name)
            if sp:
                self._price_boards[name].update(sp, self, plan)

    def market_buy(self, settlement_name: str, buyer_npc,
                   good: str, quantity: int) -> int:
        """Buy goods from a settlement market using the price board.

        Returns the number of units actually purchased.
        """
        board = self.get_price_board(settlement_name)
        return buy_from_market(self, settlement_name, board,
                               buyer_npc, good, quantity)

    def market_sell(self, settlement_name: str, seller_npc,
                    good: str, quantity: int) -> int:
        """Sell goods to a settlement market using the price board.

        Returns the number of units actually sold.
        """
        board = self.get_price_board(settlement_name)
        return sell_to_market(self, settlement_name, board,
                              seller_npc, good, quantity)

    def get_price_gossip(self, settlement_name: str) -> List[str]:
        """Return price-related NPC conversation topics."""
        board = self.get_price_board(settlement_name)
        return get_price_gossip(settlement_name, board)

    def get_transport_cost(self, from_name: str, to_name: str,
                           quantity: int = 1,
                           vehicle: str = "cart") -> int:
        """Calculate transport cost between two named settlements."""
        plan = getattr(self.world, 'plan', None)
        if not plan:
            return 0
        sp_from = self._find_settlement_plan(from_name)
        sp_to = self._find_settlement_plan(to_name)
        if not sp_from or not sp_to:
            return 0
        return calculate_transport_cost(
            sp_from.x, sp_from.y, sp_to.x, sp_to.y,
            quantity, vehicle)

    # ------------------------------------------------------------------
    # Settlement Market — handles supply/demand pricing and transactions
    # ------------------------------------------------------------------

    def get_market(self, settlement_name: str) -> "SettlementMarket":
        """Return (and lazily create) the market for a settlement."""
        if not hasattr(self, '_markets'):
            self._markets: Dict[str, "SettlementMarket"] = {}
        if settlement_name not in self._markets:
            stores = self._ensure_stores(settlement_name)
            storage = self._ensure_storage(settlement_name)
            self._markets[settlement_name] = SettlementMarket(
                settlement_name, stores, storage)
        return self._markets[settlement_name]


class SettlementMarket:
    """A local market where NPCs buy and sell goods.

    The market is backed by the settlement's stores dict — buying removes
    goods and adds gold to stores, selling adds goods and pays gold from
    stores.  Prices float based on supply: abundant goods are cheap,
    scarce goods are expensive.
    """

    # Base prices per unit
    BASE_PRICES = {
        "food": 1, "weapons": 5, "tools": 3, "clothing": 2,
        "wood": 1, "stone": 2, "ore": 3,
    }

    def __init__(self, name: str, stores: Dict[str, int],
                 storage: SettlementStorage = None):
        self.name = name
        self.stores = stores  # mutable ref to settlement stores (StorageBackedDict)
        self.storage = storage  # physical storage manager

    def price(self, good: str) -> float:
        """Current price of *good* based on supply (more supply = cheaper)."""
        base = self.BASE_PRICES.get(good, 2)
        stock = self.stores.get(good, 0)
        # Price ranges from 0.5x (abundant, stock>=80) to 3x (scarce, stock==0)
        if stock >= 80:
            return base * 0.5
        elif stock <= 0:
            return base * 3.0
        else:
            # Linear interpolation: stock 0->3x, stock 80->0.5x
            factor = 3.0 - 2.5 * (stock / 80.0)
            return base * factor

    def sell_to_market(self, npc, good: str, quantity: int) -> float:
        """NPC sells *quantity* units of *good* to the market.

        Returns gold paid to the NPC (may be less than expected if the
        market has insufficient gold).
        """
        unit_price = self.price(good)
        total_cost = unit_price * quantity
        market_gold = self.stores.get("gold", 0)
        actual_payment = min(total_cost, market_gold)
        if actual_payment <= 0:
            return 0.0
        # Transfer: goods go to market, gold goes to NPC
        self.stores[good] = self.stores.get(good, 0) + quantity
        self.stores["gold"] = max(0, market_gold - actual_payment)
        npc.npc_gold = min(9999, getattr(npc, 'npc_gold', 0) + actual_payment)
        return actual_payment

    def buy_from_market(self, npc, good: str, quantity: int) -> int:
        """NPC buys up to *quantity* units of *good* from the market.

        Returns the number of units actually purchased.  Gold flows from
        NPC to market stores.
        """
        available = self.stores.get(good, 0)
        if available <= 0:
            return 0
        actual_qty = min(quantity, available)
        unit_price = self.price(good)
        total_cost = unit_price * actual_qty
        npc_gold = getattr(npc, 'npc_gold', 0)
        # NPC may not afford everything — buy what they can
        if npc_gold < total_cost:
            actual_qty = max(1, int(npc_gold / unit_price))
            total_cost = unit_price * actual_qty
            if npc_gold < total_cost or actual_qty <= 0:
                return 0
        # Transfer: gold goes to market, goods go to NPC
        npc.npc_gold = max(0, npc_gold - total_cost)
        self.stores["gold"] = self.stores.get("gold", 0) + total_cost
        self.stores[good] = max(0, available - actual_qty)
        return actual_qty
