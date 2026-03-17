"""
Settlement generator - creates hamlets, villages, towns, and cities
with realistic layouts, proper building placement, and street networks.

Based on medieval city generation research:
- Settlements placed near water sources, road intersections
- Buildings arranged around central squares/streets
- Districts: residential, commercial, temple, military
- Size and building quality scales with settlement type

Sources:
- Medieval Fantasy City Generator (watabou) algorithmic approach
- Historical medieval village layouts
- "Procedural Modeling of Cities" (Parish & Müller)
"""

import math
import random
from typing import List, Tuple, Dict, Optional
from game.settings import (WALL, FLOOR, DOOR, TABLE, BED, CHEST, ROAD, GRASS,
                            WATER, FARMLAND, BUILT_WALL, BUILT_FLOOR,
                            WELL, SHALLOW_WATER)
from game.world.buildings import (
    Blueprint, stamp_blueprint, get_building_for_settlement,
    TAVERN, TEMPLE, GUARD_TOWER, CASTLE_KEEP, BLACKSMITH,
    SHOP, STABLE, MILL, MANSION, COTTAGE, COTTAGE_2, HOUSE, HOUSE_2,
    HOVEL, HOVEL_2, MARKET_STALL
)


class Settlement:
    """A generated settlement with buildings, streets, and NPCs."""
    def __init__(self, name: str, kind: str, x: int, y: int, region: str = ""):
        self.name = name
        self.kind = kind  # hamlet, village, town, city
        self.x = x
        self.y = y
        self.region = region
        self.radius = {"hamlet": 8, "village": 15, "town": 25, "city": 40}.get(kind, 15)
        self.buildings: List[Dict] = []  # {"blueprint": bp, "x": int, "y": int}
        self.npc_spawns: List[Dict] = []  # {"x": float, "y": float, "class": str, "race": str}
        self.population = 0


def generate_settlement(name: str, kind: str, cx: int, cy: int,
                        world_tiles: list, world_w: int, world_h: int,
                        rng: random.Random, region: str = "",
                        preferred_race: str = "") -> Settlement:
    """Generate a complete settlement at the given center position."""
    settlement = Settlement(name, kind, cx, cy, region)

    if kind == "hamlet":
        _generate_hamlet(settlement, world_tiles, world_w, world_h, rng, preferred_race)
    elif kind == "village":
        _generate_village(settlement, world_tiles, world_w, world_h, rng, preferred_race)
    elif kind == "town":
        _generate_town(settlement, world_tiles, world_w, world_h, rng, preferred_race)
    elif kind == "city":
        _generate_city(settlement, world_tiles, world_w, world_h, rng, preferred_race)

    # Place wells in all settlements as water sources
    _place_wells(settlement, world_tiles, world_w, world_h, rng)

    return settlement


def _place_wells(settlement, world_tiles: list, world_w: int, world_h: int,
                  rng: random.Random):
    """Place wells as water sources in settlements. Every settlement gets at least one."""
    cx, cy = settlement.x, settlement.y
    r = settlement.radius

    # Number of wells based on settlement size
    num_wells = {"hamlet": 1, "village": 1, "town": 2, "city": 3, "castle": 1}.get(
        settlement.kind, 1)

    placed = 0
    for _ in range(num_wells * 10):  # try multiple times
        if placed >= num_wells:
            break
        wx = cx + rng.randint(-r + 2, r - 2)
        wy = cy + rng.randint(-r + 2, r - 2)
        if (0 <= wx < world_w and 0 <= wy < world_h and
            world_tiles[wy][wx] in (ROAD, GRASS, FLOOR)):
            world_tiles[wy][wx] = WELL
            placed += 1

    # Guarantee at least one well by forcing placement at center if needed
    if placed == 0:
        for dx, dy in [(0, 2), (2, 0), (0, -2), (-2, 0), (1, 1)]:
            wx, wy = cx + dx, cy + dy
            if (0 <= wx < world_w and 0 <= wy < world_h and
                world_tiles[wy][wx] not in (WATER, WALL, BUILT_WALL)):
                world_tiles[wy][wx] = WELL
                break


def _clear_area(world_tiles: list, cx: int, cy: int, radius: int,
                world_w: int, world_h: int):
    """Clear an area to grass for building."""
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            nx, ny = cx + dx, cy + dy
            if (0 <= nx < world_w and 0 <= ny < world_h and
                dx * dx + dy * dy <= radius * radius):
                if world_tiles[ny][nx] not in (WATER,):
                    world_tiles[ny][nx] = GRASS


def _place_road_h(world_tiles: list, x0: int, x1: int, y: int, w: int, h: int):
    """Place horizontal road."""
    for x in range(max(0, min(x0, x1)), min(w, max(x0, x1) + 1)):
        if 0 <= y < h and world_tiles[y][x] not in (WATER, WALL):
            world_tiles[y][x] = ROAD


def _place_road_v(world_tiles: list, x: int, y0: int, y1: int, w: int, h: int):
    """Place vertical road."""
    for y in range(max(0, min(y0, y1)), min(h, max(y0, y1) + 1)):
        if 0 <= x < w and world_tiles[y][x] not in (WATER, WALL):
            world_tiles[y][x] = ROAD


def _try_place_building(bp: Blueprint, world_tiles: list, cx: int, cy: int,
                        radius: int, world_w: int, world_h: int,
                        rng: random.Random, settlement: Settlement,
                        preferred_race: str = "") -> bool:
    """Try to place a building within radius of center. Returns True on success."""
    for attempt in range(40):
        spread = max(radius, bp.width + 4)
        bx = cx + rng.randint(-spread, spread)
        by = cy + rng.randint(-spread, spread)

        # Maybe rotate
        placed_bp = bp
        if rng.random() < 0.5:
            placed_bp = bp.rotated()

        if stamp_blueprint(world_tiles, placed_bp, bx, by, world_w, world_h):
            settlement.buildings.append({"blueprint": placed_bp, "x": bx, "y": by})

            # Generate NPC spawn points
            floor_tiles = placed_bp.get_floor_positions()
            if floor_tiles:
                for i in range(placed_bp.npc_count):
                    if floor_tiles:
                        fx, fy = rng.choice(floor_tiles)
                        npc_class = placed_bp.npc_class or rng.choice([
                            "Fighter", "Rogue", "Bard", "Cleric"])
                        npc_race = preferred_race or ""
                        settlement.npc_spawns.append({
                            "x": float(bx + fx), "y": float(by + fy),
                            "class": npc_class, "race": npc_race,
                            "building": placed_bp.name,
                        })
                        settlement.population += 1
            return True
    return False


# ================================================================
# SETTLEMENT GENERATORS
# ================================================================

def _generate_hamlet(s: Settlement, tiles: list, w: int, h: int,
                     rng: random.Random, race: str):
    """Hamlet: 3-5 buildings along a path."""
    _clear_area(tiles, s.x, s.y, 10, w, h)

    # Main path through hamlet
    _place_road_h(tiles, s.x - 8, s.x + 8, s.y, w, h)

    # Place cottages along the path
    for i in range(rng.randint(3, 5)):
        bp = rng.choice([HOVEL, HOVEL_2, COTTAGE, COTTAGE_2])
        side = 1 if i % 2 == 0 else -1
        _try_place_building(bp, tiles, s.x - 6 + i * 3, s.y + side * 3,
                           4, w, h, rng, s, race)


def _generate_village(s: Settlement, tiles: list, w: int, h: int,
                      rng: random.Random, race: str):
    """Village: central square with tavern, buildings around it."""
    _clear_area(tiles, s.x, s.y, 18, w, h)

    # Central square (road)
    for dy in range(-2, 3):
        _place_road_h(tiles, s.x - 3, s.x + 3, s.y + dy, w, h)

    # Main roads from center
    _place_road_h(tiles, s.x - 15, s.x + 15, s.y, w, h)
    _place_road_v(tiles, s.x, s.y - 12, s.y + 12, w, h)

    # Place tavern near center
    _try_place_building(TAVERN, tiles, s.x, s.y - 6, 6, w, h, rng, s, race)

    # Temple or small church
    _try_place_building(rng.choice([TEMPLE, TEMPLE]) if rng.random() < 0.3 else TEMPLE,
                       tiles, s.x - 8, s.y - 5, 6, w, h, rng, s, race)

    # Blacksmith
    _try_place_building(BLACKSMITH, tiles, s.x + 5, s.y - 4, 5, w, h, rng, s, race)

    # Shop
    _try_place_building(SHOP, tiles, s.x + 5, s.y + 3, 5, w, h, rng, s, race)

    # Residential buildings
    for _ in range(rng.randint(5, 10)):
        bp = get_building_for_settlement("village", rng)
        _try_place_building(bp, tiles, s.x, s.y, 14, w, h, rng, s, race)

    # Farmland around edges
    for _ in range(rng.randint(4, 8)):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(12, 18)
        fx = int(s.x + math.cos(angle) * dist)
        fy = int(s.y + math.sin(angle) * dist)
        for dy in range(-2, 3):
            for dx in range(-3, 4):
                nx, ny = fx + dx, fy + dy
                if 0 <= nx < w and 0 <= ny < h and tiles[ny][nx] == GRASS:
                    tiles[ny][nx] = FARMLAND

    # Herb gardens and berry bushes near settlement
    for _ in range(rng.randint(3, 6)):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(8, 14)
        hx = int(s.x + math.cos(angle) * dist)
        hy = int(s.y + math.sin(angle) * dist)
        if 0 <= hx < w and 0 <= hy < h and tiles[hy][hx] == GRASS:
            tiles[hy][hx] = rng.choice([26, 27, 33])  # HERB_PATCH, BERRY_BUSH, FLOWER_BED


def _generate_town(s: Settlement, tiles: list, w: int, h: int,
                   rng: random.Random, race: str):
    """Town: walled settlement with main street, market square, districts."""
    radius = 22
    _clear_area(tiles, s.x, s.y, radius, w, h)

    # Town walls (circle of walls with gates)
    for angle_deg in range(0, 360, 2):
        angle = math.radians(angle_deg)
        wx = int(s.x + math.cos(angle) * (radius - 1))
        wy = int(s.y + math.sin(angle) * (radius - 1))
        if 0 <= wx < w and 0 <= wy < h:
            tiles[wy][wx] = WALL

    # Gates (N, S, E, W)
    for dx, dy in [(0, -(radius-1)), (0, radius-1), (radius-1, 0), (-(radius-1), 0)]:
        gx, gy = s.x + dx, s.y + dy
        for d in range(-1, 2):
            if 0 <= gx + (1 if dx == 0 else 0) * d < w and 0 <= gy + (1 if dy == 0 else 0) * d < h:
                tiles[gy + (1 if dx == 0 else 0) * d][gx + (1 if dy == 0 else 0) * d] = ROAD

    # Main cross streets
    _place_road_h(tiles, s.x - radius + 2, s.x + radius - 2, s.y, w, h)
    _place_road_v(tiles, s.x, s.y - radius + 2, s.y + radius - 2, w, h)

    # Market square near center
    for dy in range(-3, 4):
        for dx in range(-4, 5):
            nx, ny = s.x + dx, s.y + dy
            if 0 <= nx < w and 0 <= ny < h:
                tiles[ny][nx] = ROAD

    # Market stalls
    for i in range(rng.randint(3, 6)):
        _try_place_building(MARKET_STALL, tiles, s.x - 3, s.y - 2, 6, w, h, rng, s, race)

    # Key buildings
    _try_place_building(TAVERN, tiles, s.x + 5, s.y - 8, 6, w, h, rng, s, race)
    _try_place_building(TEMPLE, tiles, s.x - 12, s.y - 8, 6, w, h, rng, s, race)
    _try_place_building(BLACKSMITH, tiles, s.x + 8, s.y + 5, 5, w, h, rng, s, race)
    _try_place_building(STABLE, tiles, s.x - 10, s.y + 5, 5, w, h, rng, s, race)
    _try_place_building(MILL, tiles, s.x + 10, s.y + 8, 5, w, h, rng, s, race)

    # Guard towers at gates
    for dx, dy in [(radius - 3, 0), (-(radius - 3), 0), (0, radius - 3), (0, -(radius - 3))]:
        _try_place_building(GUARD_TOWER, tiles, s.x + dx, s.y + dy, 3, w, h, rng, s, race)

    # Residential fill
    for _ in range(rng.randint(12, 22)):
        bp = get_building_for_settlement("town", rng)
        _try_place_building(bp, tiles, s.x, s.y, radius - 3, w, h, rng, s, race)

    # Surrounding farmland
    for _ in range(rng.randint(6, 12)):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(radius + 2, radius + 10)
        fx = int(s.x + math.cos(angle) * dist)
        fy = int(s.y + math.sin(angle) * dist)
        for dy in range(-3, 4):
            for dx in range(-4, 5):
                nx, ny = fx + dx, fy + dy
                if 0 <= nx < w and 0 <= ny < h and tiles[ny][nx] == GRASS:
                    tiles[ny][nx] = FARMLAND


def _generate_city(s: Settlement, tiles: list, w: int, h: int,
                   rng: random.Random, race: str):
    """City: castle, cathedral, multiple districts, walls with towers."""
    radius = 35
    _clear_area(tiles, s.x, s.y, radius, w, h)

    # Outer walls
    for angle_deg in range(0, 360, 1):
        angle = math.radians(angle_deg)
        wx = int(s.x + math.cos(angle) * (radius - 1))
        wy = int(s.y + math.sin(angle) * (radius - 1))
        if 0 <= wx < w and 0 <= wy < h:
            tiles[wy][wx] = WALL

    # Gates
    for dx, dy in [(0, -(radius-1)), (0, radius-1), (radius-1, 0), (-(radius-1), 0)]:
        gx, gy = s.x + dx, s.y + dy
        for d in range(-2, 3):
            if dx == 0:
                nx, ny = gx + d, gy
            else:
                nx, ny = gx, gy + d
            if 0 <= nx < w and 0 <= ny < h:
                tiles[ny][nx] = ROAD

    # Major streets (cross + ring road)
    _place_road_h(tiles, s.x - radius + 2, s.x + radius - 2, s.y, w, h)
    _place_road_v(tiles, s.x, s.y - radius + 2, s.y + radius - 2, w, h)
    # Ring road at 60% radius
    ring_r = int(radius * 0.6)
    for angle_deg in range(0, 360, 3):
        angle = math.radians(angle_deg)
        rx = int(s.x + math.cos(angle) * ring_r)
        ry = int(s.y + math.sin(angle) * ring_r)
        if 0 <= rx < w and 0 <= ry < h:
            tiles[ry][rx] = ROAD

    # Castle in center-north
    _try_place_building(CASTLE_KEEP, tiles, s.x - 7, s.y - radius + 8, 8, w, h, rng, s, race)

    # Cathedral
    _try_place_building(TEMPLE, tiles, s.x + 10, s.y - 10, 8, w, h, rng, s, race)

    # Two taverns
    _try_place_building(TAVERN, tiles, s.x - 12, s.y + 5, 7, w, h, rng, s, race)
    _try_place_building(TAVERN, tiles, s.x + 12, s.y - 5, 7, w, h, rng, s, race)

    # Temple
    _try_place_building(TEMPLE, tiles, s.x - 15, s.y - 10, 7, w, h, rng, s, race)

    # Multiple shops and blacksmiths
    for _ in range(3):
        _try_place_building(BLACKSMITH, tiles, s.x, s.y, radius - 5, w, h, rng, s, race)
        _try_place_building(SHOP, tiles, s.x, s.y, radius - 5, w, h, rng, s, race)

    # Mansion district
    for _ in range(rng.randint(2, 4)):
        _try_place_building(MANSION, tiles, s.x, s.y - 5, radius - 8, w, h, rng, s, race)

    # Stables
    _try_place_building(STABLE, tiles, s.x + 15, s.y + 10, 6, w, h, rng, s, race)
    _try_place_building(STABLE, tiles, s.x - 15, s.y + 10, 6, w, h, rng, s, race)

    # Market stalls in center
    for _ in range(rng.randint(4, 8)):
        _try_place_building(MARKET_STALL, tiles, s.x - 5, s.y - 3, 10, w, h, rng, s, race)

    # Guard towers around walls
    for angle_deg in range(0, 360, 45):
        angle = math.radians(angle_deg)
        tx = int(s.x + math.cos(angle) * (radius - 3))
        ty = int(s.y + math.sin(angle) * (radius - 3))
        _try_place_building(GUARD_TOWER, tiles, tx, ty, 3, w, h, rng, s, race)

    # Fill with residential buildings
    for _ in range(rng.randint(20, 35)):
        bp = get_building_for_settlement("city", rng)
        _try_place_building(bp, tiles, s.x, s.y, radius - 4, w, h, rng, s, race)

    # Large farmland ring
    for _ in range(rng.randint(10, 18)):
        angle = rng.uniform(0, 2 * math.pi)
        dist = rng.uniform(radius + 2, radius + 15)
        fx = int(s.x + math.cos(angle) * dist)
        fy = int(s.y + math.sin(angle) * dist)
        for dy in range(-4, 5):
            for dx in range(-5, 6):
                nx, ny = fx + dx, fy + dy
                if 0 <= nx < w and 0 <= ny < h and tiles[ny][nx] == GRASS:
                    tiles[ny][nx] = FARMLAND
