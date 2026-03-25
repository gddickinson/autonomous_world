"""Elemental terrain effects — fire spread, ice, acid, scorch marks.

Manages persistent elemental effects on tiles: burning fires that spread
to combustible terrain, ice that freezes water, acid that dissolves walls,
and permanent scorch marks from lightning.
"""

import random
import math
from game.settings import (
    FOREST, DENSE_FOREST, WHEAT_FIELD, FLAX_FIELD, FRUIT_TREE,
    HERB_PATCH, BERRY_BUSH, FLOWER_BED, FALLEN_TREE, TREE_STUMP,
    TABLE, BED, CHEST, BARREL, BOOKSHELF, DOOR,
    WATER, WALL, RUBBLE,
)

# New terrain type IDs (added to settings.py)
SCORCHED_EARTH = 70
ICE_SHEET = 71

# Tiles that can catch fire
COMBUSTIBLE = frozenset({
    FOREST, DENSE_FOREST, WHEAT_FIELD, FLAX_FIELD, FRUIT_TREE,
    HERB_PATCH, BERRY_BUSH, FLOWER_BED, FALLEN_TREE, TREE_STUMP,
    TABLE, BED, CHEST, BARREL, BOOKSHELF, DOOR,
})

MAX_FIRES = 200
MAX_FROZEN = 100
SPREAD_INTERVAL = 2.5       # seconds between spread attempts
SPREAD_CHANCE = 0.30        # 30% chance per neighbor
FIRE_DPS = 8.0              # damage per second to entities standing in fire
ACID_DPS = 5.0              # damage per second for acid
SPREAD_BATCH = 20           # process this many fire tiles per frame


class ElementalEffects:
    """Tracks and updates elemental effects on the tile grid."""

    def __init__(self):
        # {(x,y): {"intensity": float, "remaining": float, "original": int,
        #          "spread_timer": float}}
        self.fires = {}

        # {(x,y): {"remaining": float, "original": int}}
        self.frozen = {}

        # {(x,y): {"remaining": float}}
        self.acid = {}

        # permanent scorch marks — set of (x,y)
        self.scorched = set()

        # Round-robin index for fire spread processing
        self._fire_keys = []
        self._fire_idx = 0

    # ----------------------------------------------------------
    # Apply effects
    # ----------------------------------------------------------

    def apply_fire(self, x, y, intensity, duration, world):
        """Start a fire at (x, y).

        Args:
            x, y: Tile coordinates.
            intensity: 0.0-1.0 fire intensity (affects spread chance).
            duration: Seconds until fire burns out.
            world: World object for terrain access.
        """
        if len(self.fires) >= MAX_FIRES:
            return
        ix, iy = int(x), int(y)
        key = (ix, iy)
        if key in self.fires:
            # Refresh duration if already burning
            self.fires[key]["remaining"] = max(
                self.fires[key]["remaining"], duration)
            return

        original = _get_tile(world, ix, iy)
        if original is None:
            return

        self.fires[key] = {
            "intensity": min(1.0, max(0.1, intensity)),
            "remaining": duration,
            "original": original,
            "spread_timer": random.uniform(0, SPREAD_INTERVAL),
        }
        self._fire_keys = list(self.fires.keys())

    def apply_ice(self, x, y, duration, world):
        """Freeze a tile at (x, y). Water becomes ICE_SHEET."""
        if len(self.frozen) >= MAX_FROZEN:
            return
        ix, iy = int(x), int(y)
        key = (ix, iy)
        if key in self.frozen:
            self.frozen[key]["remaining"] = max(
                self.frozen[key]["remaining"], duration)
            return

        original = _get_tile(world, ix, iy)
        if original is None:
            return

        self.frozen[key] = {
            "remaining": duration,
            "original": original,
        }
        # Change water to ice visually
        if original == WATER:
            _set_tile(world, ix, iy, ICE_SHEET)

    def apply_acid(self, x, y, duration, world):
        """Apply acid at (x, y). Walls dissolve to rubble over time."""
        ix, iy = int(x), int(y)
        key = (ix, iy)
        if key in self.acid:
            self.acid[key]["remaining"] = max(
                self.acid[key]["remaining"], duration)
            return

        self.acid[key] = {"remaining": duration}

    def apply_lightning_scorch(self, x, y, world):
        """Instant scorch mark plus chance to start fire."""
        ix, iy = int(x), int(y)
        self.scorched.add((ix, iy))
        _set_tile(world, ix, iy, SCORCHED_EARTH)

        # 40% chance to ignite surrounding combustible tiles
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = ix + dx, iy + dy
            t = _get_tile(world, nx, ny)
            if t is not None and t in COMBUSTIBLE and random.random() < 0.4:
                self.apply_fire(nx, ny, 0.6, 6.0, world)

    # ----------------------------------------------------------
    # Tick — called every frame
    # ----------------------------------------------------------

    def tick(self, dt, world):
        """Process fire spread, decay, thaw, acid dissolution."""
        self._tick_fires(dt, world)
        self._tick_frozen(dt, world)
        self._tick_acid(dt, world)

    def _tick_fires(self, dt, world):
        """Update active fires: decay, spread, burn out."""
        if not self.fires:
            return

        expired = []
        keys = self._fire_keys
        if not keys:
            keys = list(self.fires.keys())
            self._fire_keys = keys

        # Process a batch of fires for spread
        count = min(SPREAD_BATCH, len(keys))
        for _ in range(count):
            if self._fire_idx >= len(keys):
                self._fire_idx = 0
                self._fire_keys = list(self.fires.keys())
                keys = self._fire_keys
                if not keys:
                    break
            if self._fire_idx >= len(keys):
                break

            key = keys[self._fire_idx]
            self._fire_idx += 1

            fire = self.fires.get(key)
            if fire is None:
                continue

            # Decay
            fire["remaining"] -= dt
            if fire["remaining"] <= 0:
                expired.append(key)
                continue

            # Spread timer
            fire["spread_timer"] -= dt
            if fire["spread_timer"] <= 0:
                fire["spread_timer"] = SPREAD_INTERVAL
                self._try_spread(key[0], key[1], fire["intensity"], world)

        # Remove expired fires
        for key in expired:
            fire = self.fires.pop(key, None)
            if fire:
                # Terrain becomes scorched
                self.scorched.add(key)
                _set_tile(world, key[0], key[1], SCORCHED_EARTH)
            self._fire_keys = list(self.fires.keys())

    def _try_spread(self, x, y, intensity, world):
        """Try to spread fire to 4 neighboring tiles."""
        if len(self.fires) >= MAX_FIRES:
            return
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            key = (nx, ny)
            if key in self.fires:
                continue
            t = _get_tile(world, nx, ny)
            if t is None:
                continue
            if t in COMBUSTIBLE:
                chance = SPREAD_CHANCE * intensity
                if random.random() < chance:
                    self.apply_fire(nx, ny, intensity * 0.8, 8.0, world)

    def _tick_frozen(self, dt, world):
        """Thaw expired ice."""
        if not self.frozen:
            return
        expired = []
        for key, data in self.frozen.items():
            data["remaining"] -= dt
            if data["remaining"] <= 0:
                expired.append(key)
        for key in expired:
            data = self.frozen.pop(key)
            original = data["original"]
            current = _get_tile(world, key[0], key[1])
            if current == ICE_SHEET:
                _set_tile(world, key[0], key[1], original)

    def _tick_acid(self, dt, world):
        """Decay acid, dissolve walls."""
        if not self.acid:
            return
        expired = []
        for key, data in self.acid.items():
            data["remaining"] -= dt
            if data["remaining"] <= 0:
                expired.append(key)
                continue
            # Dissolve walls
            t = _get_tile(world, key[0], key[1])
            if t == WALL and random.random() < 0.02 * dt:
                _set_tile(world, key[0], key[1], RUBBLE)
        for key in expired:
            self.acid.pop(key, None)

    # ----------------------------------------------------------
    # Entity damage
    # ----------------------------------------------------------

    def damage_entities_in_effects(self, creatures, npcs, dt):
        """Damage entities standing in fire or acid."""
        if not self.fires and not self.acid:
            return

        for ent in _iter_alive(creatures, npcs):
            ex, ey = int(ent.x), int(ent.y)
            key = (ex, ey)
            if key in self.fires:
                dmg = FIRE_DPS * dt
                ent.take_damage(dmg)
            if key in self.acid:
                dmg = ACID_DPS * dt
                ent.take_damage(dmg)

    # ----------------------------------------------------------
    # Query for rendering
    # ----------------------------------------------------------

    def get_effects_in_view(self, x0, y0, x1, y1):
        """Return effects visible in the given tile range.

        Returns dict with keys: fires, frozen, acid, scorched — each
        containing only the entries within bounds.
        """
        result = {
            "fires": {},
            "frozen": {},
            "acid": {},
            "scorched": set(),
        }
        for key, data in self.fires.items():
            if x0 <= key[0] <= x1 and y0 <= key[1] <= y1:
                result["fires"][key] = data
        for key, data in self.frozen.items():
            if x0 <= key[0] <= x1 and y0 <= key[1] <= y1:
                result["frozen"][key] = data
        for key, data in self.acid.items():
            if x0 <= key[0] <= x1 and y0 <= key[1] <= y1:
                result["acid"][key] = data
        for key in self.scorched:
            if x0 <= key[0] <= x1 and y0 <= key[1] <= y1:
                result["scorched"].add(key)
        return result


# ----------------------------------------------------------
# Helpers — world tile access
# ----------------------------------------------------------

def _get_tile(world, x, y):
    """Safely get terrain type at (x, y)."""
    try:
        if hasattr(world, 'get_tile'):
            return world.get_tile(x, y)
        if 0 <= x < world.width and 0 <= y < world.height:
            return world.tiles[y][x]
    except (IndexError, AttributeError):
        pass
    return None


def _set_tile(world, x, y, terrain):
    """Safely set terrain type at (x, y)."""
    try:
        if hasattr(world, 'set_tile'):
            world.set_tile(x, y, terrain)
        elif 0 <= x < world.width and 0 <= y < world.height:
            world.tiles[y][x] = terrain
    except (IndexError, AttributeError):
        pass


def _iter_alive(*groups):
    """Yield alive entities from multiple lists."""
    for group in groups:
        for ent in group:
            if getattr(ent, 'alive', True):
                yield ent
