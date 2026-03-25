"""Monster tables and loot generation for multi-level dungeons.

Separated from dungeon_gen.py for modularity.  Each floor depth has
its own monster table and loot multiplier.
"""

import random
from typing import List, Dict

from game.world.dungeon_bsp import Rect

# ================================================================
# MONSTER TABLES (per floor difficulty)
# ================================================================

FLOOR_MONSTERS = {
    0: {  # shallow — easy
        "skeleton": {"hp": 20, "damage": 8, "speed": 1.6, "xp": 15,
                     "color": (200, 200, 190)},
        "rat":      {"hp": 10, "damage": 4, "speed": 2.0, "xp": 8,
                     "color": (140, 120, 100)},
    },
    1: {  # mid — medium
        "zombie": {"hp": 25, "damage": 6, "speed": 1.0, "xp": 18,
                   "color": (100, 130, 80)},
        "ghoul":  {"hp": 35, "damage": 12, "speed": 1.8, "xp": 25,
                   "color": (140, 110, 160)},
    },
    2: {  # deep — hard
        "wraith":       {"hp": 45, "damage": 16, "speed": 2.0, "xp": 40,
                         "color": (80, 80, 120)},
        "death_knight": {"hp": 55, "damage": 18, "speed": 1.5, "xp": 50,
                         "color": (60, 60, 80)},
    },
}

BOSS_MONSTERS = {
    "lich":    {"hp": 80, "damage": 18, "speed": 1.2, "xp": 80,
                "color": (60, 40, 100)},
    "vampire": {"hp": 60, "damage": 15, "speed": 2.2, "xp": 65,
                "color": (120, 20, 30)},
}

# Legacy alias for external code that references DUNGEON_MONSTERS
DUNGEON_MONSTERS = {
    "skeleton": FLOOR_MONSTERS[0]["skeleton"],
    "zombie":   FLOOR_MONSTERS[1]["zombie"],
    "ghoul":    FLOOR_MONSTERS[1]["ghoul"],
}

# Loot multiplier per floor depth
LOOT_MULTIPLIERS = {0: 1.0, 1: 1.5, 2: 2.5}

# Floor room count ranges
FLOOR_ROOM_COUNTS = {
    0: (8, 12),
    1: (10, 15),
    2: (6, 10),
}


# ================================================================
# MONSTER SPAWNING
# ================================================================

def spawn_monsters_for_rooms(rooms, floor_depth: int,
                             rng: random.Random) -> List[Dict]:
    """Spawn monsters appropriate for *floor_depth* in each room."""
    from game.world.dungeon_gen import (
        ROOM_BOSS, ROOM_MONSTER_LAIR, ROOM_TREASURE, ROOM_TRAP,
    )
    monsters: List[Dict] = []
    table = FLOOR_MONSTERS.get(floor_depth, FLOOR_MONSTERS[2])
    kinds = list(table.keys())

    for room in rooms:
        r = room.rect
        if room.room_type == ROOM_BOSS:
            monsters.extend(_spawn_boss(r, rng))
        elif room.room_type in (ROOM_MONSTER_LAIR, ROOM_TREASURE):
            count = rng.randint(2, 4)
            if room.room_type == ROOM_TREASURE:
                count = rng.randint(3, 4)
            for _ in range(count):
                kind = rng.choice(kinds)
                mx = rng.randint(r.x + 1, r.x + r.w - 2)
                my = rng.randint(r.y + 1, r.y + r.h - 2)
                stats = table[kind].copy()
                monsters.append({"kind": kind, "x": mx, "y": my,
                                 **stats})
        elif room.room_type == ROOM_TRAP:
            for _ in range(rng.randint(1, 2)):
                kind = rng.choice(kinds)
                mx = rng.randint(r.x + 1, r.x + r.w - 2)
                my = rng.randint(r.y + 1, r.y + r.h - 2)
                stats = table[kind].copy()
                monsters.append({"kind": kind, "x": mx, "y": my,
                                 **stats})
    return monsters


def _spawn_boss(r: Rect, rng: random.Random) -> List[Dict]:
    """Spawn a boss and its guards."""
    result: List[Dict] = []
    boss_kind = rng.choice(list(BOSS_MONSTERS.keys()))
    stats = BOSS_MONSTERS[boss_kind].copy()
    result.append({"kind": boss_kind, "x": r.cx, "y": r.cy + 1,
                    "is_boss": True, **stats})
    guard_table = FLOOR_MONSTERS[2]
    guard_kind = list(guard_table.keys())[0]
    for dx in [-2, 2]:
        gs = guard_table[guard_kind].copy()
        result.append({"kind": guard_kind,
                       "x": r.cx + dx, "y": r.cy, **gs})
    return result


# ================================================================
# LOOT PLACEMENT
# ================================================================

import numpy as np
from game.settings import CHEST


def place_loot_for_rooms(tiles: np.ndarray, rooms,
                         floor_depth: int,
                         rng: random.Random) -> List[Dict]:
    """Place loot in chest tiles and boss rooms."""
    from game.world.dungeon_gen import ROOM_BOSS
    loot: List[Dict] = []
    mult = LOOT_MULTIPLIERS.get(floor_depth, 1.0)
    h, w = tiles.shape
    for room in rooms:
        r = room.rect
        for y in range(r.y, r.y + r.h):
            for x in range(r.x, r.x + r.w):
                if 0 <= y < h and 0 <= x < w and tiles[y, x] == CHEST:
                    loot.append(_roll_chest(x, y, mult, rng))
        if room.room_type == ROOM_BOSS:
            loot.append(_roll_boss_loot(r, mult, rng))
    return loot


def _roll_chest(x: int, y: int, mult: float,
                rng: random.Random) -> Dict:
    gold = int(rng.randint(10, 50) * mult)
    items = [{"name": "gold", "quantity": gold}]
    if rng.random() < 0.5:
        items.append({"name": "health_potion",
                      "quantity": rng.randint(1, 2)})
    if rng.random() < 0.2 * mult:
        equip = rng.choice(
            ["iron_shield", "steel_helmet", "chainmail",
             "enchanted_ring", "mithril_boots"])
        items.append({"name": equip, "quantity": 1})
    if mult >= 2.0 and rng.random() < 0.15:
        items.append({"name": "treasure_map", "quantity": 1})
    return {"x": x, "y": y, "items": items}


def _roll_boss_loot(r: Rect, mult: float,
                    rng: random.Random) -> Dict:
    gold = int(rng.randint(30, 50) * mult)
    items = [
        {"name": "gold", "quantity": gold},
        {"name": "health_potion", "quantity": 2},
        {"name": "enchanted_sword", "quantity": 1},
    ]
    if mult >= 2.0:
        items.append({"name": "legendary_amulet", "quantity": 1})
    return {"x": r.cx, "y": r.cy + 2, "items": items}
