"""Procedural multi-level dungeon generation.

Generates multi-floor dungeon layouts using BSP (Binary Space
Partitioning).  Each floor has typed rooms (treasure, monster lair,
library, boss chamber, puzzle, etc.), undead monsters, and chest loot.

Floors are connected via STAIRS_DOWN / STAIRS_UP pairs.

  Floor 0 (shallow): 8-12 rooms, easy monsters (skeletons, rats)
  Floor 1 (mid):     10-15 rooms, medium monsters (zombies, ghouls)
  Floor 2 (deep):    6-10 rooms, hard monsters + boss

The BSP tree-splitting and corridor primitives live in dungeon_bsp.py.
Puzzle room logic lives in dungeon_puzzles.py.
Monster/loot tables live in dungeon_loot.py.

Usage:
    from game.world.dungeon_gen import generate_dungeon_for_location
    dungeon = generate_dungeon_for_location(loc_x, loc_y, world_seed)
    # dungeon.floors  -- list of DungeonFloor
    # dungeon.entrance -- (x, y) on floor 0
"""

import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

import numpy as np

from game.settings import (
    WALL, FLOOR, DOOR, STAIRS_UP, STAIRS_DOWN, CHEST, RUBBLE,
    BOOKSHELF, PILLAR, ALTAR, BARREL,
)
from game.world.dungeon_bsp import (
    BSPNode, Rect, split_node, create_rooms, connect_rooms,
)
from game.world.dungeon_puzzles import (
    PuzzleState, generate_puzzle_room,
)
from game.world.dungeon_loot import (
    FLOOR_ROOM_COUNTS, FLOOR_MONSTERS, BOSS_MONSTERS,
    DUNGEON_MONSTERS, spawn_monsters_for_rooms, place_loot_for_rooms,
)

# ================================================================
# ROOM TYPES
# ================================================================

ROOM_EMPTY = "empty"
ROOM_TREASURE = "treasure"
ROOM_MONSTER_LAIR = "monster_lair"
ROOM_TRAP = "trap"
ROOM_BOSS = "boss"
ROOM_LIBRARY = "library"
ROOM_PUZZLE = "puzzle"


# ================================================================
# DATA CLASSES
# ================================================================

@dataclass
class DungeonRoom:
    """A generated room with type and depth metadata."""
    rect: Rect
    room_type: str = ROOM_EMPTY
    depth: int = 0
    connected_to: List[int] = field(default_factory=list)


@dataclass
class DungeonFloor:
    """A single dungeon floor."""
    floor_depth: int
    tiles: np.ndarray                           # (height, width) int16
    width: int
    height: int
    rooms: List[DungeonRoom] = field(default_factory=list)
    monsters: List[Dict] = field(default_factory=list)
    loot: List[Dict] = field(default_factory=list)
    puzzles: List[PuzzleState] = field(default_factory=list)
    stairs_up: Optional[Tuple[int, int]] = None
    stairs_down: Optional[Tuple[int, int]] = None


@dataclass
class DungeonLayout:
    """Complete multi-floor dungeon output.

    Backwards-compatible: ``tiles``, ``rooms``, ``monsters``, ``loot``,
    and ``entrance`` all refer to floor 0 so existing code keeps working.
    """
    floors: List[DungeonFloor] = field(default_factory=list)

    @property
    def tiles(self) -> np.ndarray:
        return self.floors[0].tiles if self.floors else np.array([])

    @property
    def width(self) -> int:
        return self.floors[0].width if self.floors else 0

    @property
    def height(self) -> int:
        return self.floors[0].height if self.floors else 0

    @property
    def rooms(self) -> List[DungeonRoom]:
        return self.floors[0].rooms if self.floors else []

    @property
    def monsters(self) -> List[Dict]:
        return self.floors[0].monsters if self.floors else []

    @property
    def loot(self) -> List[Dict]:
        return self.floors[0].loot if self.floors else []

    @property
    def entrance(self) -> Tuple[int, int]:
        if self.floors and self.floors[0].stairs_up:
            return self.floors[0].stairs_up
        return (0, 0)


# ================================================================
# DUNGEON GENERATOR
# ================================================================

class DungeonGenerator:
    """Generates a multi-floor BSP dungeon layout."""

    def __init__(self, seed: int, width: int = 60, height: int = 60):
        self.seed = seed
        self.width = max(40, min(80, width))
        self.height = max(40, min(80, height))
        self.rng = random.Random(seed)

    def generate(self, num_floors: int = 3) -> DungeonLayout:
        """Generate a complete multi-level dungeon."""
        floors: List[DungeonFloor] = []
        for depth in range(num_floors):
            floor = self._generate_floor(depth)
            floors.append(floor)
        self._connect_floors(floors)
        return DungeonLayout(floors=floors)

    # ----------------------------------------------------------
    # Floor generation
    # ----------------------------------------------------------

    def _generate_floor(self, floor_depth: int) -> DungeonFloor:
        tiles = np.full((self.height, self.width), WALL, dtype=np.int16)

        _min, _max = FLOOR_ROOM_COUNTS.get(floor_depth, (6, 10))
        bsp_depth = 5 if floor_depth < 2 else 4

        root = BSPNode(0, 0, self.width, self.height)
        split_node(root, self.rng, max_depth=bsp_depth)

        rects: List[Rect] = []
        create_rooms(root, self.rng, rects)
        if len(rects) < 2:
            rects = [Rect(4, 4, self.width - 8, self.height - 8)]
        while len(rects) > _max:
            rects.pop()

        # Carve rooms
        for r in rects:
            for y in range(r.y, r.y + r.h):
                for x in range(r.x, r.x + r.w):
                    if 0 <= y < self.height and 0 <= x < self.width:
                        tiles[y, x] = FLOOR

        # Connect rooms
        connections: List[Tuple[int, int]] = []
        connect_rooms(root, tiles, self.rng, connections, rects)

        rooms = [DungeonRoom(rect=r) for r in rects]
        for li, ri in connections:
            if li < len(rooms) and ri < len(rooms):
                rooms[li].connected_to.append(ri)
                rooms[ri].connected_to.append(li)

        self._compute_depths(rooms, 0)
        self._assign_room_types(rooms, floor_depth)

        # Entrance stairs
        er = rooms[0].rect
        stairs_up_pos = (er.cx, er.cy)
        tiles[er.cy, er.cx] = STAIRS_UP

        # Decoration and puzzles
        self._place_doors(tiles, rooms)
        puzzles = self._decorate_rooms(tiles, rooms)

        # Monsters and loot (delegated to dungeon_loot)
        monsters = spawn_monsters_for_rooms(rooms, floor_depth, self.rng)
        loot = place_loot_for_rooms(tiles, rooms, floor_depth, self.rng)

        return DungeonFloor(
            floor_depth=floor_depth,
            tiles=tiles, width=self.width, height=self.height,
            rooms=rooms, monsters=monsters, loot=loot,
            puzzles=puzzles, stairs_up=stairs_up_pos,
        )

    # ----------------------------------------------------------
    # Connect floors via stairs
    # ----------------------------------------------------------

    def _connect_floors(self, floors: List[DungeonFloor]) -> None:
        for i in range(len(floors) - 1):
            upper = floors[i]
            lower = floors[i + 1]

            deepest_idx = max(
                range(len(upper.rooms)),
                key=lambda idx: upper.rooms[idx].depth,
            )
            dr = upper.rooms[deepest_idx].rect
            sdx, sdy = dr.cx, dr.cy
            if upper.tiles[sdy, sdx] != FLOOR:
                sdx = min(sdx + 1, dr.x + dr.w - 2)
            upper.tiles[sdy, sdx] = STAIRS_DOWN
            upper.stairs_down = (sdx, sdy)

            if lower.stairs_up:
                sx, sy = lower.stairs_up
                lower.tiles[sy, sx] = STAIRS_UP

    # ----------------------------------------------------------
    # BFS depth computation
    # ----------------------------------------------------------

    @staticmethod
    def _compute_depths(rooms: List[DungeonRoom], start: int) -> None:
        visited = {start}
        queue = [start]
        rooms[start].depth = 0
        while queue:
            nxt = []
            for idx in queue:
                for nb in rooms[idx].connected_to:
                    if nb not in visited:
                        visited.add(nb)
                        rooms[nb].depth = rooms[idx].depth + 1
                        nxt.append(nb)
            queue = nxt

    # ----------------------------------------------------------
    # Room type assignment
    # ----------------------------------------------------------

    def _assign_room_types(self, rooms: List[DungeonRoom],
                           floor_depth: int) -> None:
        if not rooms:
            return
        deepest_idx = max(range(len(rooms)),
                          key=lambda i: rooms[i].depth)

        if floor_depth == 2:
            rooms[deepest_idx].room_type = ROOM_BOSS
        else:
            rooms[deepest_idx].room_type = ROOM_MONSTER_LAIR

        rooms[0].room_type = ROOM_EMPTY

        puzzle_placed = False
        for i, room in enumerate(rooms):
            if i == 0 or i == deepest_idx:
                continue
            if not puzzle_placed and room.depth >= 2:
                room.room_type = ROOM_PUZZLE
                puzzle_placed = True
                continue
            roll = self.rng.random()
            if roll < 0.25:
                room.room_type = ROOM_TREASURE
            elif roll < 0.50:
                room.room_type = ROOM_MONSTER_LAIR
            elif roll < 0.65:
                room.room_type = ROOM_TRAP
            elif roll < 0.80:
                room.room_type = ROOM_LIBRARY
            else:
                room.room_type = ROOM_EMPTY

    # ----------------------------------------------------------
    # Door placement
    # ----------------------------------------------------------

    def _place_doors(self, tiles: np.ndarray,
                     rooms: List[DungeonRoom]) -> None:
        h, w = tiles.shape
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if tiles[y, x] != FLOOR:
                    continue
                n, s = tiles[y - 1, x], tiles[y + 1, x]
                e, wt = tiles[y, x + 1], tiles[y, x - 1]
                is_door = ((n == WALL and s == WALL
                            and e == FLOOR and wt == FLOOR) or
                           (e == WALL and wt == WALL
                            and n == FLOOR and s == FLOOR))
                if is_door and self._is_room_edge(x, y, rooms):
                    tiles[y, x] = DOOR

    @staticmethod
    def _is_room_edge(x: int, y: int,
                      rooms: List[DungeonRoom]) -> bool:
        for room in rooms:
            r = room.rect
            if (r.x <= x < r.x + r.w and r.y <= y < r.y + r.h):
                if (x == r.x or x == r.x + r.w - 1 or
                        y == r.y or y == r.y + r.h - 1):
                    return True
        return False

    # ----------------------------------------------------------
    # Room decoration (including puzzle rooms)
    # ----------------------------------------------------------

    def _decorate_rooms(self, tiles: np.ndarray,
                        rooms: List[DungeonRoom]) -> List[PuzzleState]:
        puzzles: List[PuzzleState] = []
        for i, room in enumerate(rooms):
            r = room.rect
            if room.room_type == ROOM_EMPTY:
                self._scatter(tiles, r, RUBBLE, 3)
            elif room.room_type == ROOM_TREASURE:
                self._place_chests(tiles, r)
            elif room.room_type == ROOM_TRAP:
                self._scatter(tiles, r, RUBBLE, 5)
            elif room.room_type == ROOM_LIBRARY:
                self._place_bookshelves(tiles, r)
            elif room.room_type == ROOM_BOSS:
                self._decorate_boss(tiles, r)
            elif room.room_type == ROOM_PUZZLE:
                ps = generate_puzzle_room(tiles, r, self.rng, i)
                puzzles.append(ps)
        return puzzles

    def _scatter(self, tiles, r, tile_type, count):
        for _ in range(self.rng.randint(0, count)):
            x = self.rng.randint(r.x + 1, r.x + r.w - 2)
            y = self.rng.randint(r.y + 1, r.y + r.h - 2)
            if tiles[y, x] == FLOOR:
                tiles[y, x] = tile_type

    def _place_chests(self, tiles, r):
        for i in range(self.rng.randint(1, 3)):
            x = r.x + 1 + i * 2
            y = r.y + 1
            if x < r.x + r.w - 1 and tiles[y, x] == FLOOR:
                tiles[y, x] = CHEST
        if r.w > 7 and r.h > 7:
            bx, by = r.x + r.w - 2, r.y + r.h - 2
            if tiles[by, bx] == FLOOR:
                tiles[by, bx] = BARREL

    def _place_bookshelves(self, tiles, r):
        for y in range(r.y + 1, r.y + r.h - 1):
            if tiles[y, r.x + 1] == FLOOR:
                tiles[y, r.x + 1] = BOOKSHELF
            if tiles[y, r.x + r.w - 2] == FLOOR:
                tiles[y, r.x + r.w - 2] = BOOKSHELF

    def _decorate_boss(self, tiles, r):
        corners = [
            (r.x + 2, r.y + 2), (r.x + r.w - 3, r.y + 2),
            (r.x + 2, r.y + r.h - 3), (r.x + r.w - 3, r.y + r.h - 3),
        ]
        for px, py in corners:
            if (0 <= py < tiles.shape[0] and 0 <= px < tiles.shape[1]
                    and tiles[py, px] == FLOOR):
                tiles[py, px] = PILLAR
        if tiles[r.cy, r.cx] == FLOOR:
            tiles[r.cy, r.cx] = ALTAR


# ================================================================
# CONVENIENCE
# ================================================================

def generate_dungeon_for_location(loc_x: int, loc_y: int,
                                  world_seed: int,
                                  width: int = 60,
                                  height: int = 60,
                                  num_floors: int = 3) -> DungeonLayout:
    """Generate a multi-level dungeon for a specific special location.

    Seed is derived from world seed + location coords so the same
    ruin always produces the same dungeon.
    """
    dungeon_seed = world_seed ^ (loc_x * 48271 + loc_y * 65537)
    gen = DungeonGenerator(seed=dungeon_seed, width=width, height=height)
    return gen.generate(num_floors=num_floors)
