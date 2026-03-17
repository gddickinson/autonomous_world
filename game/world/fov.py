"""
Field of View using shadow casting algorithm.
Based on: https://journal.stuffwithstuff.com/2015/09/07/what-the-hero-sees/

Prevents the player from seeing through walls, creating proper fog-of-war
and line-of-sight mechanics like Baldur's Gate.
"""

import math
from typing import Set, Tuple


class _Shadow:
    """A shadow covering a range of angles (slopes 0-1 within an octant)."""
    __slots__ = ('start', 'end')

    def __init__(self, start: float, end: float):
        self.start = start
        self.end = end

    def contains(self, other: '_Shadow') -> bool:
        return self.start <= other.start and self.end >= other.end


class _ShadowLine:
    """Tracks accumulated shadow segments for one octant."""
    __slots__ = ('_shadows',)

    def __init__(self):
        self._shadows = []

    def is_in_shadow(self, projection: _Shadow) -> bool:
        for shadow in self._shadows:
            if shadow.contains(projection):
                return True
        return False

    def is_full(self) -> bool:
        return (len(self._shadows) == 1 and
                self._shadows[0].start <= 0 and self._shadows[0].end >= 1)

    def add(self, shadow: _Shadow):
        """Add a shadow, merging with existing overlapping shadows."""
        index = 0
        for i, existing in enumerate(self._shadows):
            if existing.start >= shadow.start:
                index = i
                break
            index = i + 1

        # Check for overlaps with neighbors
        overlapping_prev = (index > 0 and
                           self._shadows[index - 1].end >= shadow.start)
        overlapping_next = (index < len(self._shadows) and
                           self._shadows[index].start <= shadow.end)

        if overlapping_next:
            if overlapping_prev:
                # Merge prev, new, and next into prev
                self._shadows[index - 1].end = max(
                    self._shadows[index - 1].end,
                    shadow.end,
                    self._shadows[index].end
                )
                del self._shadows[index]
            else:
                # Merge new into next
                self._shadows[index].start = min(
                    self._shadows[index].start, shadow.start)
                self._shadows[index].end = max(
                    self._shadows[index].end, shadow.end)
        elif overlapping_prev:
            # Merge new into prev
            self._shadows[index - 1].end = max(
                self._shadows[index - 1].end, shadow.end)
        else:
            # No overlap, insert
            self._shadows.insert(index, shadow)


def _project_tile(row: int, col: int) -> _Shadow:
    """Calculate the shadow projection of a tile at (row, col) in an octant."""
    top_left = col / (row + 2)
    bottom_right = (col + 1) / (row + 1)
    return _Shadow(top_left, bottom_right)


# Octant transformations: (row, col) -> (dx, dy) from origin
def _transform_octant(row: int, col: int, octant: int) -> Tuple[int, int]:
    """Transform octant-local (row, col) to world-relative (dx, dy)."""
    if octant == 0:
        return (col, -row)
    elif octant == 1:
        return (row, -col)
    elif octant == 2:
        return (row, col)
    elif octant == 3:
        return (col, row)
    elif octant == 4:
        return (-col, row)
    elif octant == 5:
        return (-row, col)
    elif octant == 6:
        return (-row, -col)
    elif octant == 7:
        return (-col, -row)
    return (0, 0)


def compute_fov(origin_x: int, origin_y: int, max_radius: int,
                is_opaque_fn, width: int, height: int) -> Set[Tuple[int, int]]:
    """
    Compute field of view from an origin point using shadow casting.

    Args:
        origin_x, origin_y: The viewer's position
        max_radius: Maximum sight distance
        is_opaque_fn: callable(x, y) -> bool, returns True if tile blocks sight
        width, height: World bounds

    Returns:
        Set of (x, y) tuples that are visible
    """
    visible = {(origin_x, origin_y)}

    for octant in range(8):
        _scan_octant(origin_x, origin_y, octant, max_radius,
                     is_opaque_fn, width, height, visible)

    return visible


def _scan_octant(ox: int, oy: int, octant: int, max_radius: int,
                 is_opaque_fn, width: int, height: int,
                 visible: Set[Tuple[int, int]]):
    """Scan one octant, building up shadows from opaque tiles."""
    line = _ShadowLine()
    max_r2 = max_radius * max_radius

    for row in range(1, max_radius + 1):
        for col in range(row + 1):
            dx, dy = _transform_octant(row, col, octant)
            tx, ty = ox + dx, oy + dy

            # Bounds check
            if tx < 0 or tx >= width or ty < 0 or ty >= height:
                continue

            # Distance check (circular FOV)
            if dx * dx + dy * dy > max_r2:
                continue

            # Early termination
            if line.is_full():
                return

            projection = _project_tile(row, col)
            is_visible = not line.is_in_shadow(projection)

            if is_visible:
                visible.add((tx, ty))

            # If this tile blocks sight, add its shadow
            if is_visible and is_opaque_fn(tx, ty):
                line.add(projection)


def compute_fov_set(origin_x: int, origin_y: int, max_radius: int,
                    world) -> Set[Tuple[int, int]]:
    """
    Convenience function: compute FOV using a World object.
    Walls, mountains, and dense forest block sight.
    """
    from game.settings import WALL, MOUNTAIN, BUILT_WALL, DENSE_FOREST, LOCKED_DOOR, FRUIT_TREE

    # Windows are NOT opaque. Locked doors and fruit trees ARE opaque.
    opaque_tiles = {WALL, MOUNTAIN, BUILT_WALL, LOCKED_DOOR, FRUIT_TREE}

    def is_opaque(x: int, y: int) -> bool:
        if x < 0 or x >= world.width or y < 0 or y >= world.height:
            return True
        tile = world.tiles[y][x]
        return tile in opaque_tiles

    return compute_fov(origin_x, origin_y, max_radius,
                       is_opaque, world.width, world.height)
