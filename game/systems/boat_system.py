"""Boat System — river and coastal travel.

Boats allow the player to traverse WATER tiles. A boat can be purchased
from a dock/port settlement (100 gold) or crafted (10 Wood + 2 Cloth).

Controls:
  B key — board / disembark (when near water with boat, or adjacent to land).

Movement on water:
  - Base speed is 75% of normal walk speed.
  - Following a river downstream grants +25% speed bonus.
  - Every 50 water tiles traveled there is a 5% chance of rough water
    (small HP loss).

The boat is stored as an inventory item ("Boat") when not in use.
"""

import math
import random
from typing import Optional

from game.settings import WATER, SHALLOW_WATER


# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

BOAT_COST_GOLD = 100
BOAT_CRAFT_WOOD = 10
BOAT_CRAFT_CLOTH = 2
BOAT_SPEED_FACTOR = 0.75       # fraction of normal walk speed
RIVER_DOWNSTREAM_BONUS = 1.25  # multiplier when going downstream
ROUGH_WATER_INTERVAL = 50      # tiles between hazard checks
ROUGH_WATER_CHANCE = 0.05      # 5% per check
ROUGH_WATER_DAMAGE = 5         # HP loss on rough water event
BOARD_RANGE = 2.0              # max distance to water to board


# ------------------------------------------------------------------
# Boat state (attached to Player)
# ------------------------------------------------------------------

class BoatState:
    """Tracks whether the player is currently in a boat."""

    def __init__(self):
        self.in_boat = False
        self.water_tiles_traveled = 0.0  # fractional accumulator
        self.last_msg = ""

    def reset(self):
        self.in_boat = False
        self.water_tiles_traveled = 0.0


# ------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------

def init_boat_system(player):
    """Attach a BoatState to the player if not already present."""
    if not hasattr(player, "boat_state"):
        player.boat_state = BoatState()


# ------------------------------------------------------------------
# Queries
# ------------------------------------------------------------------

def has_boat_item(player) -> bool:
    """Check if the player has a Boat in inventory."""
    return player.count_item("Boat") >= 1


def _is_water_tile(world, x: int, y: int) -> bool:
    if x < 0 or x >= world.width or y < 0 or y >= world.height:
        return False
    tile = world.tiles[y][x]
    return tile in (WATER, SHALLOW_WATER)


def _is_land_tile(world, x: int, y: int) -> bool:
    """True if walkable and NOT water."""
    if x < 0 or x >= world.width or y < 0 or y >= world.height:
        return False
    tile = world.tiles[y][x]
    if tile in (WATER, SHALLOW_WATER):
        return False
    return world.is_walkable(x, y)


def _adjacent_water(world, px: float, py: float) -> bool:
    """True if any of the 8 neighbours is a water tile."""
    ix, iy = int(px), int(py)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            if _is_water_tile(world, ix + dx, iy + dy):
                return True
    return False


def _adjacent_land(world, px: float, py: float) -> bool:
    """True if any of the 8 neighbours is a land tile."""
    ix, iy = int(px), int(py)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            if _is_land_tile(world, ix + dx, iy + dy):
                return True
    return False


def _find_land_neighbour(world, px: float, py: float):
    """Return (x, y) of the nearest land neighbour, or None."""
    ix, iy = int(px), int(py)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = ix + dx, iy + dy
            if _is_land_tile(world, nx, ny):
                return (nx + 0.5, ny + 0.5)
    return None


# ------------------------------------------------------------------
# Board / Disembark toggle  (call on B key press)
# ------------------------------------------------------------------

def toggle_boat(player, world) -> str:
    """Toggle boarding / disembarking. Returns a UI message."""
    init_boat_system(player)
    bs = player.boat_state

    if bs.in_boat:
        # --- Disembark ---
        if _adjacent_land(world, player.x, player.y):
            land = _find_land_neighbour(world, player.x, player.y)
            if land:
                player.x, player.y = land
            bs.reset()
            msg = "You step ashore."
            bs.last_msg = msg
            return msg
        else:
            msg = "No land nearby to disembark."
            bs.last_msg = msg
            return msg
    else:
        # --- Board ---
        if not has_boat_item(player):
            msg = "You don't have a boat."
            bs.last_msg = msg
            return msg
        if _adjacent_water(world, player.x, player.y):
            bs.in_boat = True
            bs.water_tiles_traveled = 0.0
            # Move player onto the nearest water tile
            ix, iy = int(player.x), int(player.y)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx, ny = ix + dx, iy + dy
                    if _is_water_tile(world, nx, ny):
                        player.x = nx + 0.5
                        player.y = ny + 0.5
                        break
            msg = "You board your boat."
            bs.last_msg = msg
            return msg
        else:
            msg = "No water nearby to board."
            bs.last_msg = msg
            return msg


# ------------------------------------------------------------------
# Water walkability override
# ------------------------------------------------------------------

def is_boat_walkable(player, world, x: int, y: int) -> bool:
    """When in a boat, the player can walk on water tiles."""
    bs = getattr(player, "boat_state", None)
    if bs is None or not bs.in_boat:
        return False
    return _is_water_tile(world, x, y)


# ------------------------------------------------------------------
# Speed modifier
# ------------------------------------------------------------------

def get_boat_speed_factor(player, world) -> float:
    """Return speed multiplier while in boat (1.0 if not in boat)."""
    bs = getattr(player, "boat_state", None)
    if bs is None or not bs.in_boat:
        return 1.0
    # Check for river downstream bonus (simplified: rivers flow
    # toward lower elevation; if player is heading in the direction
    # of decreasing noise, grant the bonus).
    base = BOAT_SPEED_FACTOR
    px, py = int(player.x), int(player.y)
    fx, fy = player.facing
    ahead_x = px + int(round(fx))
    ahead_y = py + int(round(fy))
    if _is_water_tile(world, ahead_x, ahead_y):
        # Simple heuristic: if tile ahead AND behind are water
        # (i.e. we're in a river channel), grant downstream bonus.
        behind_x = px - int(round(fx))
        behind_y = py - int(round(fy))
        if _is_water_tile(world, behind_x, behind_y):
            base *= RIVER_DOWNSTREAM_BONUS
    return base


# ------------------------------------------------------------------
# Hazard check  (call after player moves on water)
# ------------------------------------------------------------------

def check_water_hazard(player, distance_moved: float) -> Optional[str]:
    """Accumulate water travel and maybe trigger a rough-water event."""
    bs = getattr(player, "boat_state", None)
    if bs is None or not bs.in_boat:
        return None
    bs.water_tiles_traveled += distance_moved
    if bs.water_tiles_traveled >= ROUGH_WATER_INTERVAL:
        bs.water_tiles_traveled -= ROUGH_WATER_INTERVAL
        if random.random() < ROUGH_WATER_CHANCE:
            player.take_damage(ROUGH_WATER_DAMAGE)
            msg = f"Rough water! You take {ROUGH_WATER_DAMAGE} damage."
            bs.last_msg = msg
            return msg
    return None


# ------------------------------------------------------------------
# Crafting / buying helpers
# ------------------------------------------------------------------

def can_craft_boat(player) -> bool:
    return (player.count_item("Wood") >= BOAT_CRAFT_WOOD
            and player.count_item("Cloth") >= BOAT_CRAFT_CLOTH)


def craft_boat(player) -> str:
    """Attempt to craft a boat. Returns UI message."""
    if not can_craft_boat(player):
        return (f"Need {BOAT_CRAFT_WOOD} Wood and "
                f"{BOAT_CRAFT_CLOTH} Cloth to craft a boat.")
    player.remove_item("Wood", BOAT_CRAFT_WOOD)
    player.remove_item("Cloth", BOAT_CRAFT_CLOTH)
    from game.core.items import make_item
    boat = make_item("Boat")
    if not player.add_item(boat):
        return "Inventory full — cannot craft boat."
    return "You craft a sturdy boat."


def buy_boat(player) -> str:
    """Buy a boat for gold. Returns UI message."""
    if player.gold < BOAT_COST_GOLD:
        return f"You need {BOAT_COST_GOLD} gold to buy a boat."
    player.gold -= BOAT_COST_GOLD
    from game.core.items import make_item
    boat = make_item("Boat")
    if not player.add_item(boat):
        player.gold += BOAT_COST_GOLD  # refund
        return "Inventory full — cannot buy boat."
    return "You purchase a boat from the dock."
