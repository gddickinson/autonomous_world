"""
Forest Regrowth — cleared forest tiles gradually regenerate.

Tracks tiles that were cleared from FOREST to GRASS by woodcutting.
After a cooldown period (30-60 game days), cleared tiles have a daily
chance to regrow into FOREST.  Dense forest never regrows.  Tiles near
settlements are suppressed from regrowing (cleared land stays clear).
"""

import random
from typing import Dict, Tuple, Optional

from game.settings import FOREST, DENSE_FOREST, GRASS, TREE_STUMP

# Minimum days before regrowth becomes possible
_MIN_REGROWTH_DAYS = 30
_MAX_REGROWTH_DAYS = 60

# Daily regrowth chance once cooldown has passed
_DAILY_REGROWTH_CHANCE = 0.05

# Settlement suppression radius (tiles)
_SETTLEMENT_SUPPRESS_RADIUS = 25

# Max tiles to process per daily update
_MAX_TILES_PER_UPDATE = 200


class ForestRegrowthSystem:
    """Tracks cleared forest tiles and rolls for regrowth each game day."""

    def __init__(self):
        # (x, y) -> cleared_day
        self.cleared_tiles: Dict[Tuple[int, int], int] = {}

        # Settlement positions cache
        self._settlement_positions: list = []
        self._settle_cache_day: int = -1

        # Last processed day
        self._last_update_day: int = -1

        # Stats
        self.total_regrown: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_tree_cleared(self, x: int, y: int, game_day: int,
                        was_dense: bool = False):
        """Called when a tree is chopped down.

        Dense forest tiles are not tracked (never regrow from clear).
        """
        if was_dense:
            return
        self.cleared_tiles[(x, y)] = game_day

    def update(self, game_day: int, world):
        """Daily regrowth check. Call once per game day.

        Args:
            game_day: current game day number
            world:    the game world (for tile access and structures)
        """
        if game_day == self._last_update_day:
            return
        self._last_update_day = game_day

        # Rebuild settlement cache
        if game_day != self._settle_cache_day:
            self._settle_cache_day = game_day
            self._rebuild_settlement_cache(world)

        # Also scan for tree stumps in loaded chunks and track them
        self._scan_stumps(world, game_day)

        to_remove = []
        processed = 0

        for pos, cleared_day in list(self.cleared_tiles.items()):
            if processed >= _MAX_TILES_PER_UPDATE:
                break
            processed += 1

            x, y = pos
            days_since = game_day - cleared_day

            # Not enough time has passed
            cooldown = random.randint(_MIN_REGROWTH_DAYS, _MAX_REGROWTH_DAYS)
            if days_since < cooldown:
                continue

            # Suppress regrowth near settlements
            if self._is_near_settlement(x, y):
                continue

            # Check current tile is still GRASS or TREE_STUMP
            tile = self._get_tile(world, x, y)
            if tile == FOREST:
                # Already regrown (perhaps by ecology system)
                to_remove.append(pos)
                continue
            if tile not in (GRASS, TREE_STUMP):
                # Tile was changed to something else — stop tracking
                to_remove.append(pos)
                continue

            # Roll for regrowth
            if random.random() < _DAILY_REGROWTH_CHANCE:
                self._set_tile(world, x, y, FOREST)
                to_remove.append(pos)
                self.total_regrown += 1

        for pos in to_remove:
            self.cleared_tiles.pop(pos, None)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _scan_stumps(self, world, game_day: int):
        """Find TREE_STUMP tiles in loaded chunks and track them."""
        from game.world.chunk import ChunkGrid
        if not isinstance(getattr(world, 'tiles', None), ChunkGrid):
            return

        import numpy as np
        grid = world.tiles
        for key in list(grid.loaded_chunk_keys()):
            chunk = grid._chunks.get(key)
            if chunk is None:
                continue
            cx, cy = chunk.cx, chunk.cy
            x0 = cx * chunk.tiles.shape[1]
            y0 = cy * chunk.tiles.shape[0]

            stumps = np.argwhere(chunk.tiles == TREE_STUMP)
            for ly, lx in stumps:
                wx, wy = x0 + lx, y0 + ly
                if (wx, wy) not in self.cleared_tiles:
                    # Assume cleared recently if we just discovered it
                    self.cleared_tiles[(wx, wy)] = max(1, game_day - 10)

    def _rebuild_settlement_cache(self, world):
        """Cache settlement positions for proximity checks."""
        self._settlement_positions = []
        for s in getattr(world, 'structures', []):
            if s.kind in ("village", "town", "city", "hamlet", "castle"):
                self._settlement_positions.append((s.x, s.y))

    def _is_near_settlement(self, x: int, y: int) -> bool:
        """Check if (x, y) is near any settlement (suppresses regrowth)."""
        r2 = _SETTLEMENT_SUPPRESS_RADIUS ** 2
        for sx, sy in self._settlement_positions:
            if (x - sx) ** 2 + (y - sy) ** 2 <= r2:
                return True
        return False

    @staticmethod
    def _get_tile(world, x: int, y: int) -> int:
        if hasattr(world.tiles, 'get_tile'):
            try:
                return world.tiles.get_tile(x, y)
            except (IndexError, KeyError):
                return 0
        try:
            return world.tiles[y][x]
        except (IndexError, KeyError):
            return 0

    @staticmethod
    def _set_tile(world, x: int, y: int, value: int):
        if hasattr(world.tiles, 'set_tile'):
            world.tiles.set_tile(x, y, value)
        else:
            try:
                world.tiles[y][x] = value
            except (IndexError, KeyError):
                pass
