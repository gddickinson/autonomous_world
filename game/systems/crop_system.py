"""
Crop System — seasonal crop growth cycles with visual feedback.

Tracks per-tile crop state on FARMLAND tiles:
  FALLOW -> PLANTED -> GROWING -> MATURE -> HARVESTED

Spring:  farmers plant crops
Summer:  crops grow through stages
Autumn:  mature crops are harvested, adding food to settlement stores
Winter:  fields lie fallow, some crops die
"""

import random
from typing import Dict, Tuple, Optional, TYPE_CHECKING

from game.settings import FARMLAND, WHEAT_FIELD, TILLED_SOIL, VEGETABLE_PLOT

if TYPE_CHECKING:
    pass

# Growth stages (string enum for readability in debug)
FALLOW = "fallow"
PLANTED = "planted"
GROWING = "growing"
MATURE = "mature"
HARVESTED = "harvested"

STAGES_ORDER = [FALLOW, PLANTED, GROWING, MATURE, HARVESTED]

# Crop types and their growth durations (game days from planted to mature)
CROP_TYPES = {
    "wheat":      {"days_to_grow": 50, "food_yield": 3, "tile_type": WHEAT_FIELD},
    "barley":     {"days_to_grow": 45, "food_yield": 2, "tile_type": WHEAT_FIELD},
    "vegetables": {"days_to_grow": 35, "food_yield": 2, "tile_type": VEGETABLE_PLOT},
    "flax":       {"days_to_grow": 55, "food_yield": 1, "tile_type": FARMLAND},
}

# Color overrides for crop stages — used by the renderer
# Format: (R, G, B)
CROP_STAGE_COLORS = {
    FALLOW:    (110, 90, 55),       # brown soil
    PLANTED:   (120, 105, 60),      # light brown with hint of green
    GROWING:   (100, 155, 55),      # green-yellow
    HARVESTED: (130, 110, 65),      # stubble brown
}

# Mature colors depend on crop type
CROP_MATURE_COLORS = {
    "wheat":      (200, 180, 70),   # golden yellow
    "barley":     (190, 170, 65),   # golden
    "vegetables": (70, 150, 55),    # green
    "flax":       (140, 170, 90),   # pale green
}

# How many tiles to process per update tick
_TILES_PER_TICK = 80


class CropData:
    """State for a single crop tile."""
    __slots__ = ("stage", "planted_day", "crop_type", "progress")

    def __init__(self, crop_type: str = "wheat", planted_day: int = 0):
        self.stage: str = FALLOW
        self.planted_day: int = planted_day
        self.crop_type: str = crop_type
        self.progress: float = 0.0  # 0.0-1.0 within current growth phase


class CropSystem:
    """Manages crop lifecycle across all tracked farmland tiles."""

    def __init__(self):
        # (x, y) -> CropData
        self.crops: Dict[Tuple[int, int], CropData] = {}

        # Color overrides the renderer can read: (x, y) -> (R, G, B)
        self.color_overrides: Dict[Tuple[int, int], Tuple[int, int, int]] = {}

        # Settlement positions cache for harvest delivery
        self._settlement_cache: list = []
        self._settle_cache_day: int = -1

        # Track last update day to avoid double-processing
        self._last_update_day: int = -1

        # Round-robin offset for per-tick visual updates
        self._rr_offset: int = 0

        # Stats
        self.total_planted: int = 0
        self.total_harvested: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_farmland(self, x: int, y: int, crop_type: str = "wheat"):
        """Register a tile for crop tracking (called when farmer plants)."""
        if (x, y) not in self.crops:
            self.crops[(x, y)] = CropData(crop_type)
        cd = self.crops[(x, y)]
        cd.crop_type = crop_type
        self._update_color(x, y, cd)

    def get_stage(self, x: int, y: int) -> Optional[str]:
        """Return the crop stage at (x, y), or None if not tracked."""
        cd = self.crops.get((x, y))
        return cd.stage if cd else None

    def get_color(self, x: int, y: int) -> Optional[Tuple[int, int, int]]:
        """Return color override for renderer, or None."""
        return self.color_overrides.get((x, y))

    def update(self, game_day: int, season: str, world, world_effects=None):
        """Daily crop cycle update. Call once per game day.

        Args:
            game_day:  current game day number
            season:    "spring", "summer", "autumn", or "winter"
            world:     the game world (for tile access)
            world_effects: WorldEffects instance (for food stockpile)
        """
        if game_day == self._last_update_day:
            return
        self._last_update_day = game_day

        # Rebuild settlement cache periodically
        if game_day != self._settle_cache_day:
            self._settle_cache_day = game_day
            self._rebuild_settlement_cache(world)

        # Auto-discover farmland tiles in loaded chunks
        self._discover_farmland(world)

        # Process all crop tiles for the day
        harvested_by_settlement: Dict[str, int] = {}

        for pos, cd in list(self.crops.items()):
            x, y = pos

            # Verify tile is still farmland-type
            tile = self._get_tile(world, x, y)
            if tile not in (FARMLAND, WHEAT_FIELD, TILLED_SOIL, VEGETABLE_PLOT):
                self.crops.pop(pos, None)
                self.color_overrides.pop(pos, None)
                continue

            self._advance_crop(cd, game_day, season)
            self._update_color(x, y, cd)

            # Harvest mature crops in autumn
            if season == "autumn" and cd.stage == MATURE:
                self._harvest_tile(cd, x, y, world, harvested_by_settlement)

            # Winter die-off: some planted/growing crops die
            if season == "winter" and cd.stage in (PLANTED, GROWING):
                if random.random() < 0.08:
                    cd.stage = FALLOW
                    cd.progress = 0.0
                    self._update_color(x, y, cd)

        # Deliver harvested food to settlement stores
        if world_effects and harvested_by_settlement:
            for sname, amount in harvested_by_settlement.items():
                stores = world_effects.get_stores_ref(sname)
                stores["food"] = stores.get("food", 0) + amount

    def plant_crop(self, x: int, y: int, game_day: int,
                   crop_type: str = "wheat"):
        """A farmer plants a crop at (x, y)."""
        if (x, y) not in self.crops:
            self.crops[(x, y)] = CropData(crop_type, game_day)
        cd = self.crops[(x, y)]
        cd.stage = PLANTED
        cd.planted_day = game_day
        cd.crop_type = crop_type
        cd.progress = 0.0
        self.total_planted += 1
        self._update_color(x, y, cd)

    def update_visuals_tick(self):
        """Per-tick visual update: refresh a batch of color overrides.

        Call this every tick (lightweight, round-robin).
        """
        keys = list(self.crops.keys())
        n = len(keys)
        if n == 0:
            return
        start = self._rr_offset % n
        end = min(start + _TILES_PER_TICK, n)
        for i in range(start, end):
            pos = keys[i]
            cd = self.crops[pos]
            self._update_color(pos[0], pos[1], cd)
        self._rr_offset = end if end < n else 0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _advance_crop(self, cd: CropData, game_day: int, season: str):
        """Advance a crop through its growth stages based on season."""
        if cd.stage == FALLOW:
            # In spring, fallow fields can be auto-planted
            if season == "spring" and random.random() < 0.03:
                cd.stage = PLANTED
                cd.planted_day = game_day
                cd.progress = 0.0
                self.total_planted += 1
            return

        if cd.stage == HARVESTED:
            # After harvest, revert to fallow
            if random.random() < 0.15:
                cd.stage = FALLOW
                cd.progress = 0.0
            return

        if cd.stage == PLANTED:
            # Transition to growing after a few days
            days_since = game_day - cd.planted_day
            if days_since >= 5 and season in ("spring", "summer"):
                cd.stage = GROWING
                cd.progress = 0.0
            return

        if cd.stage == GROWING:
            # Grow toward maturity
            crop_info = CROP_TYPES.get(cd.crop_type, CROP_TYPES["wheat"])
            days_to_grow = crop_info["days_to_grow"]
            days_since = game_day - cd.planted_day

            # Growth rate depends on season
            if season == "summer":
                growth_rate = 2.0
            elif season == "spring":
                growth_rate = 1.5
            elif season == "autumn":
                growth_rate = 0.5
            else:
                growth_rate = 0.0

            cd.progress = min(1.0, (days_since / days_to_grow) * growth_rate)

            if cd.progress >= 1.0:
                cd.stage = MATURE
                cd.progress = 1.0
            return

    def _harvest_tile(self, cd: CropData, x: int, y: int, world,
                      harvested_by_settlement: Dict[str, int]):
        """Harvest a mature crop tile."""
        crop_info = CROP_TYPES.get(cd.crop_type, CROP_TYPES["wheat"])
        food = crop_info["food_yield"]

        cd.stage = HARVESTED
        cd.progress = 0.0
        self.total_harvested += food

        # Find nearest settlement to credit
        sname = self._nearest_settlement_name(x, y)
        if sname:
            harvested_by_settlement[sname] = (
                harvested_by_settlement.get(sname, 0) + food
            )

        self._update_color(x, y, cd)

    def _update_color(self, x: int, y: int, cd: CropData):
        """Set the color override for this tile based on crop stage."""
        if cd.stage == MATURE:
            color = CROP_MATURE_COLORS.get(cd.crop_type, (200, 180, 70))
        elif cd.stage == GROWING:
            # Blend from planted color to growing color based on progress
            pc = CROP_STAGE_COLORS[PLANTED]
            gc = CROP_STAGE_COLORS[GROWING]
            t = cd.progress
            color = (
                int(pc[0] + (gc[0] - pc[0]) * t),
                int(pc[1] + (gc[1] - pc[1]) * t),
                int(pc[2] + (gc[2] - pc[2]) * t),
            )
        else:
            color = CROP_STAGE_COLORS.get(cd.stage, (110, 90, 55))
        self.color_overrides[(x, y)] = color

    def _discover_farmland(self, world):
        """Auto-discover FARMLAND/WHEAT_FIELD tiles in loaded chunks."""
        from game.world.chunk import ChunkGrid
        import numpy as np

        if not isinstance(getattr(world, 'tiles', None), ChunkGrid):
            return

        grid = world.tiles
        for key in list(grid.loaded_chunk_keys()):
            chunk = grid._chunks.get(key)
            if chunk is None:
                continue
            cx, cy = chunk.cx, chunk.cy
            x0 = cx * chunk.tiles.shape[1]  # CHUNK_SIZE
            y0 = cy * chunk.tiles.shape[0]

            farm_mask = (
                (chunk.tiles == FARMLAND) |
                (chunk.tiles == WHEAT_FIELD) |
                (chunk.tiles == VEGETABLE_PLOT)
            )
            farm_positions = np.argwhere(farm_mask)
            for ly, lx in farm_positions:
                wx, wy = x0 + lx, y0 + ly
                if (wx, wy) not in self.crops:
                    ct = "wheat"
                    if chunk.tiles[ly, lx] == VEGETABLE_PLOT:
                        ct = "vegetables"
                    self.crops[(wx, wy)] = CropData(ct)

    def _rebuild_settlement_cache(self, world):
        """Cache settlement positions for harvest delivery."""
        self._settlement_cache = []
        for s in getattr(world, 'structures', []):
            if s.kind in ("village", "town", "city", "hamlet", "castle"):
                self._settlement_cache.append((s.x, s.y, s.name))

    def _nearest_settlement_name(self, x: int, y: int) -> Optional[str]:
        """Find the nearest settlement to (x, y)."""
        best_name = None
        best_d2 = float('inf')
        for sx, sy, sname in self._settlement_cache:
            d2 = (x - sx) ** 2 + (y - sy) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_name = sname
        return best_name

    @staticmethod
    def _get_tile(world, x: int, y: int) -> int:
        """Read tile type, handling both ChunkGrid and array."""
        if hasattr(world.tiles, 'get_tile'):
            try:
                return world.tiles.get_tile(x, y)
            except (IndexError, KeyError):
                return 0
        try:
            return world.tiles[y][x]
        except (IndexError, KeyError):
            return 0
