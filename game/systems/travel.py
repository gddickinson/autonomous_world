"""Travel Mode — fast-travel between settlements on the world map.

When the player selects a destination on the world map, this system:
1. Calculates travel time based on distance, roads, and mount speed
2. Rolls for random encounters along the route
3. Advances game time appropriately
4. Teleports the player to the destination
5. Activates the destination zone (loads chunks, spawns NPCs)

If a random encounter is triggered, the player drops back to the
high-resolution adventure view at the encounter location.
"""

import math
import random
from typing import Optional, Tuple, List
from game.settings import (TILE_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT,
                            DAY_LENGTH, ROAD, GRAVEL_ROAD, COBBLESTONE,
                            DIRT_TRACK)


# Travel speeds (tiles per game-hour)
TRAVEL_SPEED = {
    "walk":       87.5,    # 3.5 tiles/real-sec × 25 real-sec/game-hour
    "jog":        131.0,
    "horse":      200.0,
    "war_horse":  250.0,
    "donkey":     140.0,
    "coach":      175.0,
}

# Encounter chance per 500 tiles of travel (0-1)
ENCOUNTER_CHANCE = {
    "road":       0.10,   # 10% per leg on roads
    "wilderness": 0.25,   # 25% per leg off-road
}

ENCOUNTER_TYPES = [
    "bandit_ambush",
    "wildlife_attack",
    "merchant_caravan",
    "traveling_bard",
    "broken_bridge",
    "storm",
    "injured_traveler",
    "mysterious_shrine",
]


class TravelResult:
    """Result of a fast-travel attempt."""
    def __init__(self):
        self.success = False
        self.destination_name = ""
        self.destination_x = 0
        self.destination_y = 0
        self.game_hours_elapsed = 0.0
        self.distance_tiles = 0.0
        self.encounter = None       # None or encounter dict
        self.encounter_x = 0.0
        self.encounter_y = 0.0
        self.message = ""
        self.encounter_spawns: List[Tuple[str, float, float]] = []
        # List of (creature_kind, x, y) to spawn at the encounter site


def calculate_travel(world, player, dest_x: int, dest_y: int,
                     dest_name: str = "",
                     travel_mode: str = "walk") -> TravelResult:
    """Calculate travel from player position to destination.

    Returns a TravelResult with travel time, encounter info, etc.
    Does NOT actually move the player — the caller decides what to do.
    """
    result = TravelResult()
    result.destination_name = dest_name
    result.destination_x = dest_x
    result.destination_y = dest_y

    px, py = player.x, player.y
    dist = math.sqrt((dest_x - px)**2 + (dest_y - py)**2)
    result.distance_tiles = dist

    # Determine travel speed
    speed = TRAVEL_SPEED.get(travel_mode, TRAVEL_SPEED["walk"])

    # Check if player has a mount
    mount = getattr(player, 'mount', None)
    if mount and hasattr(mount, 'is_alive') and mount.is_alive:
        mount_kind = getattr(mount, 'kind', 'horse')
        speed = TRAVEL_SPEED.get(mount_kind, TRAVEL_SPEED["horse"])

    # Travel time in game hours
    hours = dist / speed
    result.game_hours_elapsed = hours

    # Check for random encounters along the route
    rng = random.Random()
    legs = max(1, int(dist / 500))
    for leg in range(legs):
        # Determine if this leg is on a road
        t = (leg + 0.5) / legs
        check_x = px + (dest_x - px) * t
        check_y = py + (dest_y - py) * t

        # Simple road check — if tile at midpoint is road-like
        tile = world.tiles[int(check_y)][int(check_x)]
        on_road = tile in (ROAD, GRAVEL_ROAD, COBBLESTONE, DIRT_TRACK)

        chance = ENCOUNTER_CHANCE["road"] if on_road else ENCOUNTER_CHANCE["wilderness"]

        if rng.random() < chance:
            # Encounter!
            enc_type = rng.choice(ENCOUNTER_TYPES)
            result.encounter = {
                "type": enc_type,
                "leg": leg,
                "on_road": on_road,
            }
            # Place encounter at the point along the route
            result.encounter_x = check_x
            result.encounter_y = check_y
            # Only partial travel time (up to encounter point)
            result.game_hours_elapsed = hours * t
            result.message = _encounter_message(enc_type)
            result.encounter_spawns = _encounter_creatures(
                enc_type, check_x, check_y, rng)
            result.success = False  # interrupted
            return result

    result.success = True
    result.message = (f"Arrived at {dest_name} after "
                      f"{hours:.1f} hours of travel.")
    return result


def execute_travel(game, result: TravelResult):
    """Execute the travel — move player, advance time, activate zone."""
    if result.success:
        # Teleport player to destination
        game.player.x = float(result.destination_x)
        game.player.y = float(result.destination_y)

        # Advance game time
        real_seconds = result.game_hours_elapsed * (DAY_LENGTH / 24.0)
        game.time_sys.update(real_seconds)

        # Preload chunks and activate zone at destination
        if hasattr(game.world.tiles, 'preload_around'):
            game.world.tiles.preload_around(
                game.player.x, game.player.y, radius_chunks=2)
        if hasattr(game.world_mgr, 'activate_zone'):
            game.world_mgr.activate_zone(game.player.x, game.player.y)
        if hasattr(game.world, 'update_building_interiors_near'):
            game.world.update_building_interiors_near(
                game.player.x, game.player.y)

        # Update camera
        game.camera.x = game.player.x * TILE_SIZE - SCREEN_WIDTH // 2
        game.camera.y = game.player.y * TILE_SIZE - SCREEN_HEIGHT // 2

        # Reveal area
        game.world.reveal_around(int(game.player.x), int(game.player.y), 12)

        game.notifications.add(result.message, 5.0, (100, 200, 100))

    elif result.encounter:
        # Travel interrupted — teleport to encounter location
        game.player.x = float(result.encounter_x)
        game.player.y = float(result.encounter_y)

        # Partial time advance
        real_seconds = result.game_hours_elapsed * (DAY_LENGTH / 24.0)
        game.time_sys.update(real_seconds)

        # Preload and activate
        if hasattr(game.world.tiles, 'preload_around'):
            game.world.tiles.preload_around(
                game.player.x, game.player.y, radius_chunks=2)
        if hasattr(game.world_mgr, 'activate_zone'):
            game.world_mgr.activate_zone(game.player.x, game.player.y)

        # Update camera
        game.camera.x = game.player.x * TILE_SIZE - SCREEN_WIDTH // 2
        game.camera.y = game.player.y * TILE_SIZE - SCREEN_HEIGHT // 2

        game.world.reveal_around(int(game.player.x), int(game.player.y), 12)

        # Spawn encounter creatures
        if result.encounter_spawns:
            from game.core.creature import Creature
            for kind, cx, cy in result.encounter_spawns:
                creature = Creature(cx, cy, kind)
                creature.home_x = cx
                creature.home_y = cy
                creature.leash_range = 15.0
                game.world_mgr.creatures.append(creature)

        game.notifications.add(result.message, 6.0, (220, 180, 60))


def get_nearby_settlements(world, x: float, y: float,
                           max_dist: float = 5000) -> List[dict]:
    """Get settlements within travel distance, sorted by distance."""
    results = []
    for s in world.structures:
        if s.kind not in ("hamlet", "village", "town", "city", "castle"):
            continue
        dist = math.sqrt((s.x - x)**2 + (s.y - y)**2)
        if dist < max_dist and dist > 50:  # not too close
            hours = dist / TRAVEL_SPEED["walk"]
            results.append({
                "name": s.name,
                "kind": s.kind,
                "x": s.x, "y": s.y,
                "distance": dist,
                "walk_hours": hours,
            })
    results.sort(key=lambda r: r["distance"])
    return results


def _encounter_creatures(enc_type: str, cx: float, cy: float,
                         rng: random.Random) -> List[Tuple[str, float, float]]:
    """Determine which creatures to spawn for an encounter.

    Returns a list of (creature_kind, x, y) tuples placed near (cx, cy).
    """
    spawns: List[Tuple[str, float, float]] = []

    def _scatter(kind: str, count: int):
        """Place `count` creatures of `kind` scattered around (cx, cy)."""
        for _ in range(count):
            ox = cx + rng.uniform(-4.0, 4.0)
            oy = cy + rng.uniform(-4.0, 4.0)
            spawns.append((kind, ox, oy))

    if enc_type == "bandit_ambush":
        _scatter("bandit", rng.randint(2, 4))

    elif enc_type == "wildlife_attack":
        if rng.random() < 0.6:
            _scatter("wolf", rng.randint(2, 3))
        else:
            _scatter("bear", 1)

    elif enc_type == "injured_traveler":
        # 50% chance it's actually a bandit ambush
        if rng.random() < 0.5:
            _scatter("bandit", rng.randint(1, 2))

    # merchant_caravan, traveling_bard, broken_bridge, storm,
    # mysterious_shrine — no hostile spawns

    return spawns


def _encounter_message(enc_type: str) -> str:
    """Generate a message for a travel encounter."""
    messages = {
        "bandit_ambush": "Bandits block the road ahead!",
        "wildlife_attack": "A pack of wolves emerges from the trees!",
        "merchant_caravan": "You encounter a merchant caravan on the road.",
        "traveling_bard": "A wandering bard offers to share news.",
        "broken_bridge": "The bridge ahead has collapsed. You must find another way.",
        "storm": "A violent storm forces you to take shelter.",
        "injured_traveler": "You find an injured traveler by the roadside.",
        "mysterious_shrine": "An ancient shrine glows faintly in the dusk.",
    }
    return messages.get(enc_type, f"Something happens: {enc_type}")

