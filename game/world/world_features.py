"""World feature generation — test island, temples, ruins, rivers."""

import random
import math
from game.settings import *


class WorldFeaturesMixin:

    """Mixin — see parent class for context."""

    def _generate_rivers(self, rng: random.Random):
        """Generate rivers flowing from mountains to water/low ground."""
        num_rivers = max(3, (self.width * self.height) // 50000)
        for _ in range(num_rivers):
            # Start from a mountain tile
            for attempt in range(100):
                x = rng.randint(20, self.width - 20)
                y = rng.randint(20, self.height - 20)
                if self.tiles[y][x] == MOUNTAIN:
                    self._trace_river(x, y, rng)
                    break

    def _generate_test_island(self):
        """Generate an isolated desert island far from the main continent.

        The island is a flat sand oval with a spawn temple near the western edge.
        No settlements, NPCs, or creatures will spawn here — it's a controlled
        test environment on 'the other side of the planet'.
        """
        # Island parameters — placed in deep ocean far from the main continent.
        # The continent is centered at (width//2, height//2) with edge falloff
        # creating water around the borders. We place the island near the
        # top-right corner where it's guaranteed to be ocean.
        island_w, island_h = 200, 120
        # Center: 92% across in X, 7% down in Y — far corner of the ocean
        ix = int(self.width * 0.92)
        iy = int(self.height * 0.07)

        # Clamp so the island fits within world bounds with a water buffer
        buf = 10
        ix = max(island_w // 2 + buf, min(self.width - island_w // 2 - buf, ix))
        iy = max(island_h // 2 + buf, min(self.height - island_h // 2 - buf, iy))

        # Store bounding rect for exclusion zones (with generous margin)
        margin = 30
        self.test_island_rect = (
            ix - island_w // 2 - margin,
            iy - island_h // 2 - margin,
            island_w + margin * 2,
            island_h + margin * 2,
        )

        # First, ensure the whole area is water (ocean buffer around island)
        for dy in range(-island_h // 2 - 8, island_h // 2 + 9):
            for dx in range(-island_w // 2 - 8, island_w // 2 + 9):
                nx, ny = ix + dx, iy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    self.tiles[ny][nx] = WATER

        # Carve the island as a smooth ellipse of sand
        rx = island_w / 2.0   # semi-axis X
        ry = island_h / 2.0   # semi-axis Y
        for dy in range(-island_h // 2, island_h // 2 + 1):
            for dx in range(-island_w // 2, island_w // 2 + 1):
                # Ellipse test: (dx/rx)^2 + (dy/ry)^2 <= 1
                if (dx / rx) ** 2 + (dy / ry) ** 2 <= 1.0:
                    nx, ny = ix + dx, iy + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        self.tiles[ny][nx] = SAND

        # Thin beach fringe — sand tiles just outside the ellipse are already
        # water, which gives a natural coastline. Add a 1-tile SAND fringe
        # for a softer edge.
        for dy in range(-island_h // 2 - 1, island_h // 2 + 2):
            for dx in range(-island_w // 2 - 1, island_w // 2 + 2):
                e = (dx / rx) ** 2 + (dy / ry) ** 2
                if 1.0 < e <= 1.08:
                    nx, ny = ix + dx, iy + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        self.tiles[ny][nx] = SAND

        # Place spawn temple near the western edge of the island
        temple_x = ix - island_w // 2 + 20  # 20 tiles in from western edge
        temple_y = iy                        # vertically centered
        self._build_spawn_temple_minimal(temple_x, temple_y)

        # Colosseum is placed after all world gen — see end of _generate()
        self._test_colosseum_pos = (ix + 40, iy)

        self.test_island_spawn = (temple_x, temple_y)

    def _build_spawn_temple_minimal(self, cx: int, cy: int):
        """Build a simple spawn temple on the test island.

        Same circular design as the main temple but without the starter village
        or long roads — just the temple with short paths leading onto the sand.
        """
        r = 5  # slightly smaller than main temple

        # Clear immediate area to sand (it already is, but ensure floor contrast)
        for dy in range(-r - 3, r + 4):
            for dx in range(-r - 3, r + 4):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    self.tiles[ny][nx] = SAND

        # Temple walls (circle)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    dist2 = dx * dx + dy * dy
                    if dist2 <= r * r:
                        if dist2 >= (r - 1) * (r - 1):
                            self.tiles[ny][nx] = WALL
                        else:
                            self.tiles[ny][nx] = FLOOR

        # Doors on all 4 sides (3 tiles wide)
        for dx_off in [-1, 0, 1]:
            for dy_off in range(-r, -r + 3):
                nx, ny = cx + dx_off, cy + dy_off
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == WALL:
                        self.tiles[ny][nx] = DOOR
        for dx_off in [-1, 0, 1]:
            for dy_off in range(r - 2, r + 1):
                nx, ny = cx + dx_off, cy + dy_off
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == WALL:
                        self.tiles[ny][nx] = DOOR
        for dy_off in [-1, 0, 1]:
            for dx_off in range(r - 2, r + 1):
                nx, ny = cx + dx_off, cy + dy_off
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == WALL:
                        self.tiles[ny][nx] = DOOR
        for dy_off in [-1, 0, 1]:
            for dx_off in range(-r, -r + 3):
                nx, ny = cx + dx_off, cy + dy_off
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self.tiles[ny][nx] == WALL:
                        self.tiles[ny][nx] = DOOR

        # Short paths (5 tiles) from each door
        for dy in range(1, 6):
            ny = cy - r - dy
            if 0 <= ny < self.height and 0 <= cx < self.width:
                self.tiles[ny][cx] = SAND
        for dy in range(1, 6):
            ny = cy + r + dy
            if 0 <= ny < self.height and 0 <= cx < self.width:
                self.tiles[ny][cx] = SAND
        for dx in range(1, 6):
            nx = cx + r + dx
            if 0 <= nx < self.width and 0 <= cy < self.height:
                self.tiles[cy][nx] = SAND
        for dx in range(1, 6):
            nx = cx - r - dx
            if 0 <= nx < self.width and 0 <= cy < self.height:
                self.tiles[cy][nx] = SAND

        temple = Structure("Temple of Testing", "temple", cx, cy, radius=r)
        self.structures.append(temple)

    def _build_test_colosseum(self, cx: int, cy: int):
        """Stamp the colosseum blueprint onto the test island."""
        from game.world.blueprint_library import ENTERTAINMENT
        from game.world.buildings import stamp_blueprint

        colosseum_bp = ENTERTAINMENT[0]  # The grand Colosseum
        bw, bh = colosseum_bp.width, colosseum_bp.height

        # Clear entire blueprint footprint plus generous surround to sand
        # so no world-gen terrain peeks through the elliptical exterior gaps
        margin = 20
        for dy in range(-bh // 2 - margin, bh // 2 + margin + 1):
            for dx in range(-bw // 2 - margin, bw // 2 + margin + 1):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    # Force to sand — overwrite everything including resources
                    self.tiles[ny][nx] = SAND

        # Stamp the blueprint
        stamp_x = cx - bw // 2
        stamp_y = cy - bh // 2
        stamp_blueprint(self.tiles, colosseum_bp, stamp_x, stamp_y,
                        self.width, self.height)

        colosseum = Structure("Test Colosseum", "colosseum", cx, cy,
                              radius=max(bw, bh) // 2)
        self.structures.append(colosseum)

    def _place_ruins_and_shrines(self, rng: random.Random):
        """Place ruins and shrines in wilderness areas."""
        max_ruins = max(6, (self.width * self.height) // 15000)
        for _ in range(max_ruins):
            for attempt in range(50):
                x = rng.randint(20, self.width - 20)
                y = rng.randint(20, self.height - 20)
                if self.tiles[y][x] in (WATER, MOUNTAIN, WALL):
                    continue
                # Skip test island area
                if self.test_island_rect:
                    rx, ry, rw, rh = self.test_island_rect
                    if rx <= x <= rx + rw and ry <= y <= ry + rh:
                        continue
                too_close = any(
                    math.sqrt((s.x - x)**2 + (s.y - y)**2) < 20
                    for s in self.structures
                )
                if too_close:
                    continue
                # Build ruin
                name = rng.choice(["Ancient Ruins", "Forgotten Temple", "Crumbling Tower",
                                   "Lost Catacombs", "Shattered Keep", "Buried Sanctum",
                                   "The Dark Catacombs", "Goblin Warren", "Tomb of the Ancients"])
                ruin = Structure(name, "ruins", x, y, radius=5)
                for dy in range(-4, 5):
                    for dx in range(-4, 5):
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.width and 0 <= ny < self.height:
                            if dx * dx + dy * dy <= 16:
                                if abs(dx) >= 3 or abs(dy) >= 3:
                                    if rng.random() < 0.5:
                                        self.tiles[ny][nx] = WALL
                                    else:
                                        self.tiles[ny][nx] = FLOOR
                                else:
                                    self.tiles[ny][nx] = FLOOR
                self.structures.append(ruin)
                break


