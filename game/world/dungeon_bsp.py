"""BSP (Binary Space Partitioning) utilities for dungeon generation.

Provides the tree-splitting, room creation, and corridor carving
primitives used by DungeonGenerator in dungeon_gen.py.
"""

import random
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

import numpy as np

from game.settings import WALL, FLOOR

# ================================================================
# CONSTANTS
# ================================================================

MIN_LEAF_SIZE = 12      # minimum BSP leaf before we stop splitting
MIN_ROOM_SIZE = 6       # minimum room dimension
CORRIDOR_WIDTH = 2


# ================================================================
# DATA CLASSES
# ================================================================

@dataclass
class BSPNode:
    """A node in the binary space partition tree."""
    x: int
    y: int
    w: int
    h: int
    left: Optional["BSPNode"] = None
    right: Optional["BSPNode"] = None
    room: Optional["Rect"] = None


@dataclass
class Rect:
    """Simple rectangle."""
    x: int
    y: int
    w: int
    h: int

    @property
    def cx(self) -> int:
        return self.x + self.w // 2

    @property
    def cy(self) -> int:
        return self.y + self.h // 2


# ================================================================
# BSP TREE OPERATIONS
# ================================================================

def split_node(node: BSPNode, rng: random.Random,
               depth: int = 0, max_depth: int = 5) -> None:
    """Recursively split a BSP node into two children."""
    if depth >= max_depth:
        return
    if node.w < MIN_LEAF_SIZE * 2 and node.h < MIN_LEAF_SIZE * 2:
        return

    # Choose split direction: prefer splitting the longer axis
    if node.w > node.h * 1.25:
        split_h = False
    elif node.h > node.w * 1.25:
        split_h = True
    else:
        split_h = rng.random() < 0.5

    if split_h:
        if node.h < MIN_LEAF_SIZE * 2:
            return
        split = rng.randint(MIN_LEAF_SIZE, node.h - MIN_LEAF_SIZE)
        node.left = BSPNode(node.x, node.y, node.w, split)
        node.right = BSPNode(node.x, node.y + split, node.w,
                             node.h - split)
    else:
        if node.w < MIN_LEAF_SIZE * 2:
            return
        split = rng.randint(MIN_LEAF_SIZE, node.w - MIN_LEAF_SIZE)
        node.left = BSPNode(node.x, node.y, split, node.h)
        node.right = BSPNode(node.x + split, node.y, node.w - split,
                             node.h)

    split_node(node.left, rng, depth + 1, max_depth)
    split_node(node.right, rng, depth + 1, max_depth)


def create_rooms(node: BSPNode, rng: random.Random,
                 rooms: List[Rect]) -> Optional[Rect]:
    """Create rooms inside BSP leaf nodes. Returns the room rect."""
    if node.left is not None and node.right is not None:
        left_room = create_rooms(node.left, rng, rooms)
        right_room = create_rooms(node.right, rng, rooms)
        return left_room or right_room

    # Leaf node — create a room with some padding
    pad = 2
    max_w = node.w - pad * 2
    max_h = node.h - pad * 2
    if max_w < MIN_ROOM_SIZE or max_h < MIN_ROOM_SIZE:
        return None

    rw = rng.randint(MIN_ROOM_SIZE, max_w)
    rh = rng.randint(MIN_ROOM_SIZE, max_h)
    rx = node.x + rng.randint(pad, node.w - rw - pad)
    ry = node.y + rng.randint(pad, node.h - rh - pad)

    room = Rect(rx, ry, rw, rh)
    node.room = room
    rooms.append(room)
    return room


def get_room(node: BSPNode) -> Optional[Rect]:
    """Get any room from a node's subtree."""
    if node.room is not None:
        return node.room
    if node.left is not None:
        r = get_room(node.left)
        if r:
            return r
    if node.right is not None:
        return get_room(node.right)
    return None


# ================================================================
# CORRIDOR CARVING
# ================================================================

def connect_rooms(node: BSPNode, tiles: np.ndarray,
                  rng: random.Random,
                  connections: List[Tuple[int, int]],
                  rooms: List[Rect]) -> None:
    """Connect sibling rooms with corridors (recursive)."""
    if node.left is None or node.right is None:
        return

    connect_rooms(node.left, tiles, rng, connections, rooms)
    connect_rooms(node.right, tiles, rng, connections, rooms)

    left_room = get_room(node.left)
    right_room = get_room(node.right)
    if left_room is None or right_room is None:
        return

    li = rooms.index(left_room) if left_room in rooms else -1
    ri = rooms.index(right_room) if right_room in rooms else -1
    if li >= 0 and ri >= 0:
        connections.append((li, ri))

    _carve_corridor(tiles, left_room, right_room, rng)


def _carve_corridor(tiles: np.ndarray, r1: Rect, r2: Rect,
                    rng: random.Random) -> None:
    """Carve an L-shaped corridor between two room centres."""
    x1, y1 = r1.cx, r1.cy
    x2, y2 = r2.cx, r2.cy
    hw = CORRIDOR_WIDTH // 2

    if rng.random() < 0.5:
        _carve_h(tiles, x1, x2, y1, hw)
        _carve_v(tiles, y1, y2, x2, hw)
    else:
        _carve_v(tiles, y1, y2, x1, hw)
        _carve_h(tiles, x1, x2, y2, hw)


def _carve_h(tiles: np.ndarray, x1: int, x2: int, y: int,
             hw: int) -> None:
    """Carve a horizontal corridor segment."""
    h = tiles.shape[0]
    lo, hi = min(x1, x2), max(x1, x2)
    for xx in range(lo, hi + 1):
        for dy in range(-hw, hw + 1):
            yy = y + dy
            if 0 <= yy < h and 0 <= xx < tiles.shape[1]:
                tiles[yy, xx] = FLOOR


def _carve_v(tiles: np.ndarray, y1: int, y2: int, x: int,
             hw: int) -> None:
    """Carve a vertical corridor segment."""
    w = tiles.shape[1]
    lo, hi = min(y1, y2), max(y1, y2)
    for yy in range(lo, hi + 1):
        for dx in range(-hw, hw + 1):
            xx = x + dx
            if 0 <= yy < tiles.shape[0] and 0 <= xx < w:
                tiles[yy, xx] = FLOOR
