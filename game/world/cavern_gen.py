"""Natural cavern generation using cellular automata.

Generates organic cave systems distinct from BSP dungeons.  Caves are
placed near mountains (elevation > 0.55) and connected to the surface
via a wide cave mouth entrance.

Cave features:
  - Stalactites (decorative ROCKY_GROUND tiles)
  - Underground pools (WATER tiles)
  - Crystal formations (GEM_DEPOSIT tiles)
  - Mushroom patches (MUSHROOMS tiles)

Monsters: cave-appropriate (bats, spiders, trolls).

Usage:
    from game.world.cavern_gen import generate_cavern, find_cavern_sites
    sites = find_cavern_sites(elevation_map, width, height, rng)
    for sx, sy in sites:
        cavern = generate_cavern(sx, sy, world_seed)
"""

import random
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

import numpy as np

from game.settings import (
    WALL, FLOOR, WATER, MUSHROOMS, GEM_DEPOSIT, ROCKY_GROUND,
    MOUNTAIN, RUBBLE,
)


# ================================================================
# CAVE MONSTERS
# ================================================================

CAVE_MONSTERS_SHALLOW = ["bat", "giant_rat", "giant_spider"]
CAVE_MONSTERS_DEEP = ["cave_troll", "giant_spider", "phase_spider"]
CAVE_MONSTERS_RARE = ["basilisk", "umber_hulk"]


# ================================================================
# DATA CLASSES
# ================================================================

@dataclass
class CavernRoom:
    """A connected region within the cavern."""
    cells: List[Tuple[int, int]] = field(default_factory=list)
    center_x: int = 0
    center_y: int = 0
    depth: int = 0  # 0 = near entrance, higher = deeper

    def compute_center(self):
        if self.cells:
            self.center_x = sum(c[0] for c in self.cells) // len(self.cells)
            self.center_y = sum(c[1] for c in self.cells) // len(self.cells)


@dataclass
class CavernMonster:
    """A monster placed in the cavern."""
    kind: str
    x: int
    y: int
    cr: int = 1


@dataclass
class CavernLayout:
    """Complete cavern output."""
    tiles: np.ndarray          # (height, width) int16
    width: int
    height: int
    entrance: Tuple[int, int]  # (x, y) of cave mouth on surface
    rooms: List[CavernRoom] = field(default_factory=list)
    monsters: List[CavernMonster] = field(default_factory=list)
    features: List[Dict] = field(default_factory=list)  # decorative features
    surface_x: int = 0        # world-space X of cave entrance
    surface_y: int = 0        # world-space Y of cave entrance


# ================================================================
# CELLULAR AUTOMATA CAVE GENERATOR
# ================================================================

class CavernGenerator:
    """Generate natural cave shapes via cellular automata."""

    INITIAL_FILL = 0.45  # 45% random wall fill
    SMOOTH_ITERATIONS = 4
    BIRTH_LIMIT = 5      # neighbours >= 5 -> become wall
    DEATH_LIMIT = 2      # neighbours <= 2 -> become floor

    def __init__(self, seed: int, width: int = 50, height: int = 50):
        self.seed = seed
        self.width = max(30, min(80, width))
        self.height = max(30, min(80, height))
        self.rng = random.Random(seed)

    def generate(self) -> CavernLayout:
        """Run the full cavern generation pipeline."""
        tiles = self._init_grid()
        tiles = self._smooth(tiles)
        self._ensure_border_walls(tiles)

        # Find connected regions
        rooms = self._find_regions(tiles)

        # Keep only the largest region; wall off the rest
        if rooms:
            rooms.sort(key=lambda r: len(r.cells), reverse=True)
            main_room = rooms[0]
            keep = set(main_room.cells)
            for y in range(self.height):
                for x in range(self.width):
                    if tiles[y, x] == FLOOR and (x, y) not in keep:
                        tiles[y, x] = WALL
            rooms = [main_room]
            # Split main region into sub-rooms by depth bands
            rooms = self._split_by_depth(main_room, tiles)

        # Place entrance (cave mouth)
        entrance = self._place_entrance(tiles, rooms)

        # Place features
        features = self._place_features(tiles, rooms)

        # Place monsters
        monsters = self._place_monsters(tiles, rooms)

        layout = CavernLayout(
            tiles=tiles,
            width=self.width,
            height=self.height,
            entrance=entrance,
            rooms=rooms,
            monsters=monsters,
            features=features,
        )
        return layout

    # ----------------------------------------------------------
    # Grid initialisation
    # ----------------------------------------------------------

    def _init_grid(self) -> np.ndarray:
        """Create initial random grid."""
        grid = np.full((self.height, self.width), WALL, dtype=np.int16)
        for y in range(1, self.height - 1):
            for x in range(1, self.width - 1):
                if self.rng.random() > self.INITIAL_FILL:
                    grid[y, x] = FLOOR
        return grid

    # ----------------------------------------------------------
    # Cellular automata smoothing
    # ----------------------------------------------------------

    def _smooth(self, grid: np.ndarray) -> np.ndarray:
        """Apply cellular automata rules to smooth the cave."""
        for _ in range(self.SMOOTH_ITERATIONS):
            new_grid = grid.copy()
            for y in range(1, self.height - 1):
                for x in range(1, self.width - 1):
                    neighbours = self._count_wall_neighbours(grid, x, y)
                    if grid[y, x] == WALL:
                        if neighbours <= self.DEATH_LIMIT:
                            new_grid[y, x] = FLOOR
                    else:
                        if neighbours >= self.BIRTH_LIMIT:
                            new_grid[y, x] = WALL
            grid = new_grid
        return grid

    @staticmethod
    def _count_wall_neighbours(grid: np.ndarray, x: int, y: int) -> int:
        """Count wall tiles in the 8-cell neighbourhood."""
        count = 0
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                if dx == 0 and dy == 0:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < grid.shape[0] and 0 <= nx < grid.shape[1]:
                    if grid[ny, nx] == WALL:
                        count += 1
                else:
                    count += 1  # out-of-bounds = wall
        return count

    def _ensure_border_walls(self, grid: np.ndarray):
        """Ensure edges are solid wall."""
        grid[0, :] = WALL
        grid[-1, :] = WALL
        grid[:, 0] = WALL
        grid[:, -1] = WALL

    # ----------------------------------------------------------
    # Region detection (flood fill)
    # ----------------------------------------------------------

    def _find_regions(self, grid: np.ndarray) -> List[CavernRoom]:
        """Flood-fill to find connected floor regions."""
        visited = set()
        regions: List[CavernRoom] = []

        for y in range(self.height):
            for x in range(self.width):
                if grid[y, x] == FLOOR and (x, y) not in visited:
                    room = CavernRoom()
                    stack = [(x, y)]
                    while stack:
                        cx, cy = stack.pop()
                        if (cx, cy) in visited:
                            continue
                        if grid[cy, cx] != FLOOR:
                            continue
                        visited.add((cx, cy))
                        room.cells.append((cx, cy))
                        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < self.width and 0 <= ny < self.height:
                                stack.append((nx, ny))
                    room.compute_center()
                    regions.append(room)

        return regions

    # ----------------------------------------------------------
    # Depth-based sub-rooms
    # ----------------------------------------------------------

    def _split_by_depth(self, main: CavernRoom,
                        grid: np.ndarray) -> List[CavernRoom]:
        """Split the main region into depth bands from the entrance side."""
        if not main.cells:
            return [main]

        # Use top-most row as the "entrance side"
        min_y = min(c[1] for c in main.cells)
        max_y = max(c[1] for c in main.cells)
        span = max(max_y - min_y, 1)
        band_count = min(3, max(1, span // 10))
        band_size = span / band_count

        rooms: List[CavernRoom] = []
        for band in range(band_count):
            y_lo = min_y + int(band * band_size)
            y_hi = min_y + int((band + 1) * band_size)
            room = CavernRoom(depth=band)
            room.cells = [(x, y) for x, y in main.cells
                          if y_lo <= y < y_hi]
            room.compute_center()
            if room.cells:
                rooms.append(room)

        return rooms if rooms else [main]

    # ----------------------------------------------------------
    # Entrance placement (wide cave mouth)
    # ----------------------------------------------------------

    def _place_entrance(self, grid: np.ndarray,
                        rooms: List[CavernRoom]) -> Tuple[int, int]:
        """Place a wide cave mouth at the top edge."""
        # Find floor tiles near the top
        candidates = []
        for x in range(2, self.width - 2):
            for y in range(1, min(8, self.height)):
                if grid[y, x] == FLOOR:
                    candidates.append((x, y))

        if not candidates:
            # Carve an entrance tunnel from top edge to nearest floor
            cx = self.width // 2
            for y in range(0, self.height):
                if grid[y, cx] == FLOOR:
                    # Carve wide mouth
                    for cy in range(0, y + 1):
                        for dx in range(-2, 3):
                            nx = cx + dx
                            if 0 <= nx < self.width:
                                grid[cy, nx] = FLOOR
                    return (cx, 0)
            # Fallback: carve through center
            for y in range(0, min(10, self.height)):
                for dx in range(-2, 3):
                    nx = cx + dx
                    if 0 <= nx < self.width:
                        grid[y, nx] = FLOOR
            return (cx, 0)

        # Pick the leftmost-ish floor near top
        candidates.sort(key=lambda c: c[1])
        ex, ey = candidates[0]

        # Widen the entrance (cave mouth is 5 tiles wide)
        for y in range(0, ey + 1):
            for dx in range(-2, 3):
                nx = ex + dx
                if 0 <= nx < self.width:
                    grid[y, nx] = FLOOR

        return (ex, 0)

    # ----------------------------------------------------------
    # Feature placement
    # ----------------------------------------------------------

    def _place_features(self, grid: np.ndarray,
                        rooms: List[CavernRoom]) -> List[Dict]:
        """Place stalactites, pools, crystals, and mushrooms."""
        features: List[Dict] = []

        for room in rooms:
            if not room.cells:
                continue

            floor_cells = [c for c in room.cells if grid[c[1], c[0]] == FLOOR]
            if not floor_cells:
                continue

            # Stalactites (decorative ROCKY_GROUND — near walls)
            wall_adjacent = [c for c in floor_cells
                             if self._near_wall(grid, c[0], c[1])]
            for _ in range(min(len(wall_adjacent), self.rng.randint(2, 5))):
                if wall_adjacent:
                    cx, cy = self.rng.choice(wall_adjacent)
                    grid[cy, cx] = ROCKY_GROUND
                    features.append({"type": "stalactite", "x": cx, "y": cy})
                    wall_adjacent.remove((cx, cy))

            # Underground pools (WATER — prefer deeper rooms)
            pool_count = self.rng.randint(0, 2) + room.depth
            pool_cells = self.rng.sample(
                floor_cells, min(pool_count * 3, len(floor_cells)))
            for cx, cy in pool_cells[:pool_count * 3]:
                if grid[cy, cx] == FLOOR:
                    grid[cy, cx] = WATER
                    features.append({"type": "pool", "x": cx, "y": cy})

            # Crystal formations (GEM_DEPOSIT — rare, deeper rooms)
            if room.depth >= 1 and self.rng.random() < 0.6:
                crystal_count = self.rng.randint(1, 3)
                remaining = [c for c in floor_cells if grid[c[1], c[0]] == FLOOR]
                for cx, cy in self.rng.sample(
                        remaining, min(crystal_count, len(remaining))):
                    grid[cy, cx] = GEM_DEPOSIT
                    features.append({"type": "crystal", "x": cx, "y": cy})

            # Mushroom patches (MUSHROOMS — damp areas near pools)
            pool_positions = [(f["x"], f["y"]) for f in features
                              if f["type"] == "pool"]
            if pool_positions:
                for _ in range(self.rng.randint(1, 3)):
                    px, py = self.rng.choice(pool_positions)
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = px + dx, py + dy
                        if (0 <= nx < self.width and 0 <= ny < self.height
                                and grid[ny, nx] == FLOOR):
                            grid[ny, nx] = MUSHROOMS
                            features.append({"type": "mushroom", "x": nx, "y": ny})
                            break

        return features

    @staticmethod
    def _near_wall(grid: np.ndarray, x: int, y: int) -> bool:
        """Check if a floor tile is adjacent to a wall."""
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            if 0 <= ny < grid.shape[0] and 0 <= nx < grid.shape[1]:
                if grid[ny, nx] == WALL:
                    return True
        return False

    # ----------------------------------------------------------
    # Monster placement
    # ----------------------------------------------------------

    def _place_monsters(self, grid: np.ndarray,
                        rooms: List[CavernRoom]) -> List[CavernMonster]:
        """Place cave-appropriate monsters in each room."""
        monsters: List[CavernMonster] = []

        for room in rooms:
            floor_cells = [c for c in room.cells if grid[c[1], c[0]] == FLOOR]
            if not floor_cells:
                continue

            if room.depth == 0:
                pool = CAVE_MONSTERS_SHALLOW
                count = self.rng.randint(1, 3)
                cr = 1
            elif room.depth == 1:
                pool = CAVE_MONSTERS_DEEP
                count = self.rng.randint(2, 4)
                cr = 2
            else:
                pool = CAVE_MONSTERS_DEEP
                count = self.rng.randint(2, 5)
                cr = 3
                # Small chance of a rare monster
                if self.rng.random() < 0.2:
                    pool = CAVE_MONSTERS_RARE
                    cr = 4

            for _ in range(min(count, len(floor_cells))):
                cx, cy = self.rng.choice(floor_cells)
                kind = self.rng.choice(pool)
                monsters.append(CavernMonster(kind=kind, x=cx, y=cy, cr=cr))

        return monsters


# ================================================================
# SITE SELECTION
# ================================================================

def find_cavern_sites(elevation_map, width: int, height: int,
                      rng: random.Random,
                      max_sites: int = 5,
                      min_elevation: float = 0.55) -> List[Tuple[int, int]]:
    """Find suitable cave entrance locations near mountains.

    Args:
        elevation_map: 2D array or callable (x, y) -> float
        width, height: world dimensions
        rng: random generator
        max_sites: maximum number of cavern sites
        min_elevation: minimum elevation for a cave entrance

    Returns:
        List of (x, y) world coordinates for cave entrances.
    """
    candidates: List[Tuple[int, int]] = []
    step = max(10, width // 50)  # sample sparsely

    for y in range(step, height - step, step):
        for x in range(step, width - step, step):
            try:
                if callable(elevation_map):
                    elev = elevation_map(x, y)
                else:
                    elev = elevation_map[y][x]
            except (IndexError, TypeError):
                continue

            if elev >= min_elevation:
                candidates.append((x, y))

    rng.shuffle(candidates)

    # Ensure sites are spaced apart (at least 40 tiles)
    selected: List[Tuple[int, int]] = []
    for cx, cy in candidates:
        if len(selected) >= max_sites:
            break
        too_close = any(
            abs(cx - sx) < 40 and abs(cy - sy) < 40
            for sx, sy in selected
        )
        if not too_close:
            selected.append((cx, cy))

    return selected


# ================================================================
# CONVENIENCE
# ================================================================

def generate_cavern(surface_x: int, surface_y: int,
                    world_seed: int,
                    width: int = 50, height: int = 50) -> CavernLayout:
    """Generate a cavern for a specific surface location.

    Seed is derived from world seed + surface coords for determinism.
    """
    cavern_seed = world_seed ^ (surface_x * 31337 + surface_y * 48271)
    gen = CavernGenerator(seed=cavern_seed, width=width, height=height)
    layout = gen.generate()
    layout.surface_x = surface_x
    layout.surface_y = surface_y
    return layout
