"""
Spatial hash grid for O(1) nearby entity lookups.

Instead of checking every entity against every other entity (O(n²)),
entities are placed in grid cells. Finding nearby entities only checks
the cell and its neighbors (O(n×k) where k is small).

This is the #1 performance optimization for the simulation.
"""

from typing import List, Dict, Set, Tuple, Any
import math


class SpatialGrid:
    """Fast spatial lookup using a hash grid."""

    __slots__ = ('cell_size', 'grid', '_entity_cells')

    def __init__(self, cell_size: int = 20):
        self.cell_size = cell_size
        self.grid: Dict[Tuple[int, int], List] = {}
        self._entity_cells: Dict[int, Tuple[int, int]] = {}  # entity id -> cell

    def clear(self):
        """Clear all entities from the grid."""
        self.grid.clear()
        self._entity_cells.clear()

    def _cell(self, x: float, y: float) -> Tuple[int, int]:
        return (int(x) // self.cell_size, int(y) // self.cell_size)

    def insert(self, entity):
        """Insert an entity into the grid."""
        cell = self._cell(entity.x, entity.y)
        if cell not in self.grid:
            self.grid[cell] = []
        self.grid[cell].append(entity)
        self._entity_cells[id(entity)] = cell

    def update_all(self, entities: list):
        """Rebuild the entire grid from a list of entities. Call once per frame."""
        self.clear()
        for entity in entities:
            if getattr(entity, 'alive', True):
                self.insert(entity)

    def get_nearby(self, x: float, y: float, radius: float) -> List:
        """Get all entities within radius of a point. O(k) not O(n)."""
        results = []
        cx, cy = self._cell(x, y)
        cell_radius = int(math.ceil(radius / self.cell_size)) + 1
        r2 = radius * radius

        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                cell = (cx + dx, cy + dy)
                if cell in self.grid:
                    for entity in self.grid[cell]:
                        ex = entity.x - x
                        ey = entity.y - y
                        if ex * ex + ey * ey <= r2:
                            results.append(entity)

        return results

    def get_nearby_of_kind(self, x: float, y: float, radius: float,
                           kind: str) -> List:
        """Get nearby entities of a specific kind."""
        results = []
        cx, cy = self._cell(x, y)
        cell_radius = int(math.ceil(radius / self.cell_size)) + 1
        r2 = radius * radius

        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                cell = (cx + dx, cy + dy)
                if cell in self.grid:
                    for entity in self.grid[cell]:
                        if getattr(entity, 'kind', None) == kind:
                            ex = entity.x - x
                            ey = entity.y - y
                            if ex * ex + ey * ey <= r2:
                                results.append(entity)

        return results

    def count_nearby(self, x: float, y: float, radius: float) -> int:
        """Count entities within radius. Faster than get_nearby when you just need count."""
        count = 0
        cx, cy = self._cell(x, y)
        cell_radius = int(math.ceil(radius / self.cell_size)) + 1
        r2 = radius * radius

        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                cell = (cx + dx, cy + dy)
                if cell in self.grid:
                    for entity in self.grid[cell]:
                        ex = entity.x - x
                        ey = entity.y - y
                        if ex * ex + ey * ey <= r2:
                            count += 1

        return count
