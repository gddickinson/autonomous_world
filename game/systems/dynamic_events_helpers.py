"""Shared data classes and utilities for the dynamic events system.

Split from dynamic_events.py for modularity. Contains:
- DynamicEvent class
- Category weights and timing constants
- Helper functions for distance, tile destruction, kingdom checks
"""

import random
import math
from typing import Dict, Any, Tuple


# ================================================================
# EVENT CATEGORIES AND WEIGHTS
# ================================================================

CATEGORY_WEIGHTS = {
    "political": 0.20,
    "social": 0.25,
    "discovery": 0.15,
    "disaster": 0.40,
}

# How often (in game days) the system checks for a new event
EVENT_CHECK_MIN_DAYS = 5
EVENT_CHECK_MAX_DAYS = 15


# ================================================================
# DYNAMIC EVENT CLASS
# ================================================================

class DynamicEvent:
    """A story-driven world event with gameplay consequences."""

    def __init__(self, category: str, name: str, description: str,
                 effects: Dict[str, Any], settlement_name: str = "",
                 kingdom_name: str = "", duration_days: int = 0,
                 game_day: int = 0):
        self.category = category
        self.name = name
        self.description = description
        self.effects = effects
        self.settlement_name = settlement_name
        self.kingdom_name = kingdom_name
        self.duration_days = duration_days
        self.started_day = game_day
        self.resolved = False


# ================================================================
# HELPER FUNCTIONS
# ================================================================

def _weighted_choice(weights: Dict[str, float]) -> str:
    """Pick a category using weighted probabilities."""
    items = list(weights.items())
    total = sum(w for _, w in items)
    r = random.random() * total
    cumulative = 0.0
    for name, w in items:
        cumulative += w
        if r <= cumulative:
            return name
    return items[-1][0]


def _random_kingdom(governance) -> Tuple[str, Any]:
    """Return (name, Kingdom) or ('', None)."""
    kingdoms = governance.kingdoms if governance else {}
    if not kingdoms:
        return "", None
    kname = random.choice(list(kingdoms.keys()))
    return kname, kingdoms[kname]


def _in_kingdom(npc, kingdom) -> bool:
    """Check if NPC is within a kingdom's territory."""
    dx = npc.x - kingdom.castle_x
    dy = npc.y - kingdom.castle_y
    r = getattr(kingdom, 'territory_radius', 80)
    return dx * dx + dy * dy <= r * r


def _distance(a, b) -> float:
    """Euclidean distance between two entities with x, y."""
    dx = a.x - b.x
    dy = a.y - b.y
    return math.sqrt(dx * dx + dy * dy)


def _distance_to(entity, x: float, y: float) -> float:
    """Euclidean distance from entity to a point."""
    dx = entity.x - x
    dy = entity.y - y
    return math.sqrt(dx * dx + dy * dy)


def _destroy_tiles(world, cx: float, cy: float, radius: float,
                   tile_type: int, count: int,
                   replace_with: int) -> int:
    """Destroy up to `count` tiles of `tile_type` within radius."""
    destroyed = 0
    for _ in range(count * 3):  # try extra times
        if destroyed >= count:
            break
        rx = int(cx + random.uniform(-radius, radius))
        ry = int(cy + random.uniform(-radius, radius))
        if (0 <= rx < world.width and 0 <= ry < world.height
                and world.tiles[ry][rx] == tile_type):
            world.modify_tile(rx, ry, replace_with)
            destroyed += 1
    return destroyed
