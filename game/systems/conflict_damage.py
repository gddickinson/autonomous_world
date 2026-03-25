"""Conflict Damage — terrain destruction from raids, battles, and monster attacks.

When combat events (raids, battles, monster waves) occur near settlements,
this system damages nearby terrain tiles and potentially destroys buildings.

Damage types:
- Farmland destruction: FARMLAND/TILLED_SOIL -> GRASS (burned crops)
- Building destruction: BUILT_WALL/BUILT_FLOOR -> RUBBLE (structural damage)
- Forest fire: FOREST -> GRASS (scorched earth from siege)

Called from sim_events.py during event processing.
"""

import random
import math
from typing import List, Optional, Tuple
from game.settings import (
    GRASS, FARMLAND, TILLED_SOIL, FOREST, DENSE_FOREST,
    BUILT_WALL, BUILT_FLOOR, RUBBLE,
)


# ================================================================
# DAMAGE CONFIGURATION
# ================================================================

# How many farmland tiles to damage per raid severity
RAID_FARM_DAMAGE = (3, 5)       # min, max tiles damaged
BATTLE_FARM_DAMAGE = (5, 10)    # larger battles do more damage

# Chance per raid of destroying a building in the target settlement
RAID_BUILDING_DESTROY_CHANCE = 0.10  # 10%
BATTLE_BUILDING_DESTROY_CHANCE = 0.20  # 20% for full battles

# Radius around event center to search for damageable tiles
DAMAGE_SEARCH_RADIUS = 15


# ================================================================
# CORE DAMAGE FUNCTIONS
# ================================================================

def damage_farmland(world, center_x: float, center_y: float,
                    count_range: Tuple[int, int] = RAID_FARM_DAMAGE,
                    event_log: List[str] = None,
                    source_name: str = "raiders") -> int:
    """Convert nearby FARMLAND/TILLED_SOIL tiles to GRASS (burned/trampled).

    Returns the number of tiles damaged.
    """
    cx, cy = int(center_x), int(center_y)
    target_count = random.randint(count_range[0], count_range[1])
    damaged = 0

    # Collect candidate farmland tiles within radius
    candidates = []
    r = DAMAGE_SEARCH_RADIUS
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < world.width and 0 <= ny < world.height:
                tile = world.tiles[ny][nx]
                if tile in (FARMLAND, TILLED_SOIL):
                    dist_sq = dx * dx + dy * dy
                    if dist_sq <= r * r:
                        candidates.append((nx, ny, dist_sq))

    if not candidates:
        return 0

    # Sort by distance (damage nearest first) and pick up to target_count
    candidates.sort(key=lambda t: t[2])
    for nx, ny, _ in candidates[:target_count]:
        world.modify_tile(nx, ny, GRASS)
        damaged += 1

    return damaged


def damage_buildings(world, center_x: float, center_y: float,
                     destroy_chance: float = RAID_BUILDING_DESTROY_CHANCE,
                     event_log: List[str] = None,
                     source_name: str = "raiders") -> bool:
    """With a probability, destroy a random building tile near the center.

    Converts BUILT_WALL/BUILT_FLOOR to RUBBLE. Returns True if destroyed.
    """
    if random.random() > destroy_chance:
        return False

    cx, cy = int(center_x), int(center_y)
    r = DAMAGE_SEARCH_RADIUS

    # Collect building tiles
    building_tiles = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < world.width and 0 <= ny < world.height:
                tile = world.tiles[ny][nx]
                if tile in (BUILT_WALL, BUILT_FLOOR):
                    dist_sq = dx * dx + dy * dy
                    if dist_sq <= r * r:
                        building_tiles.append((nx, ny))

    if not building_tiles:
        return False

    # Destroy 1-3 random building tiles
    destroy_count = min(len(building_tiles), random.randint(1, 3))
    targets = random.sample(building_tiles, destroy_count)
    for nx, ny in targets:
        world.modify_tile(nx, ny, RUBBLE)

    return True


def scorch_terrain(world, center_x: float, center_y: float,
                   count: int = 3) -> int:
    """Burn forest tiles near a battle (fire damage). Returns count scorched."""
    cx, cy = int(center_x), int(center_y)
    r = DAMAGE_SEARCH_RADIUS
    scorched = 0

    candidates = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < world.width and 0 <= ny < world.height:
                tile = world.tiles[ny][nx]
                if tile in (FOREST, DENSE_FOREST):
                    dist_sq = dx * dx + dy * dy
                    if dist_sq <= r * r:
                        candidates.append((nx, ny))

    if candidates:
        for nx, ny in random.sample(candidates, min(count, len(candidates))):
            world.modify_tile(nx, ny, GRASS)
            scorched += 1

    return scorched


# ================================================================
# EVENT PROCESSING — called from sim_events._update_events
# ================================================================

def process_conflict_damage(evt, world, event_log: List[str]):
    """Process terrain damage for a conflict-type event.

    Called once when the event first triggers (announced == False).
    Handles raids, battles, monster waves, and wolf pack attacks.

    Args:
        evt: WorldEvent with .effects, .x, .y, .name
        world: World object with .tiles and .modify_tile
        event_log: List to append damage messages to
    """
    effects = evt.effects
    is_raid = effects.get("danger") in ("raiders", "wolves") or "raid_size" in effects
    is_battle = "battle" in evt.name.lower()
    is_monster = "monster" in evt.name.lower() or "wave" in evt.name.lower()

    if not (is_raid or is_battle or is_monster):
        return

    # Find nearest settlement name for log messages
    settlement_name = _find_nearest_settlement_name(world, evt.x, evt.y)
    location = settlement_name or f"({int(evt.x)}, {int(evt.y)})"

    # --- Raid damage ---
    if is_raid:
        farm_count = damage_farmland(
            world, evt.x, evt.y,
            count_range=RAID_FARM_DAMAGE,
            event_log=event_log,
            source_name=evt.name,
        )
        if farm_count > 0:
            event_log.append(
                f"{evt.name}: burned {farm_count} farmland tiles near {location}")

        if damage_buildings(world, evt.x, evt.y,
                           destroy_chance=RAID_BUILDING_DESTROY_CHANCE,
                           event_log=event_log,
                           source_name=evt.name):
            event_log.append(
                f"{evt.name}: destroyed a building near {location}!")

    # --- Battle / monster wave damage (heavier) ---
    if is_battle or is_monster:
        farm_count = damage_farmland(
            world, evt.x, evt.y,
            count_range=BATTLE_FARM_DAMAGE,
            event_log=event_log,
            source_name=evt.name,
        )
        if farm_count > 0:
            event_log.append(
                f"Battle near {location}: {farm_count} farmland tiles destroyed")

        if damage_buildings(world, evt.x, evt.y,
                           destroy_chance=BATTLE_BUILDING_DESTROY_CHANCE,
                           event_log=event_log,
                           source_name=evt.name):
            event_log.append(
                f"Battle near {location}: buildings damaged in the fighting!")

        # Scorched forest from battle fire
        scorched = scorch_terrain(world, evt.x, evt.y, count=3)
        if scorched > 0:
            event_log.append(
                f"Battle fires scorched {scorched} forest tiles near {location}")


def _find_nearest_settlement_name(world, x: float, y: float,
                                   max_dist: float = 50.0) -> Optional[str]:
    """Find the name of the nearest settlement to coordinates."""
    best_name = None
    best_dist = max_dist * max_dist

    for s in world.structures:
        if s.kind in ("village", "town", "city", "hamlet", "castle"):
            dx = s.x - x
            dy = s.y - y
            d2 = dx * dx + dy * dy
            if d2 < best_dist:
                best_dist = d2
                best_name = s.name

    return best_name
