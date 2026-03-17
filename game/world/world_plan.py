"""World Plan — the compact, upfront description of the entire game world.

Generated once at world creation time. Contains everything needed to
deterministically regenerate any chunk of the world:
  - Seed and dimensions
  - Settlement locations, names, types, populations
  - Road network with waypoints
  - River paths
  - Region boundaries
  - NPC roster (who exists, where they live)
  - Special locations (spawn temple, test island, ruins)

The WorldPlan is small enough to always stay in memory (~1-5 MB) even for
a 10,000 x 10,000 tile world. The actual tile data is generated lazily
per-chunk by the chunk generator, which reads the plan to know what
features to stamp into each chunk.
"""

import math
import random
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

from game.settings import *


# ================================================================
# DATA CLASSES
# ================================================================

@dataclass
class SettlementPlan:
    """A planned settlement — location and metadata, no tile data."""
    name: str
    kind: str           # hamlet, village, town, city, castle
    x: int              # center x in world coords
    y: int              # center y in world coords
    radius: int         # extent in tiles
    region: str         # which region this belongs to
    race: str           # dominant race
    population: int     # planned NPC count
    buildings: List[Dict] = field(default_factory=list)
    # Each building: {"kind": str, "blueprint_name": str, "x": int, "y": int,
    #                 "w": int, "h": int}
    npc_spawns: List[Dict] = field(default_factory=list)
    # Each spawn: {"x": float, "y": float, "class": str, "race": str,
    #              "building": str, "name": str}
    specialization: str = "general"     # port, mining, lumber, agricultural, etc.
    terrain_context: Dict = field(default_factory=dict)  # nearby terrain counts
    trade_connections: List[str] = field(default_factory=list)  # connected settlement names


@dataclass
class RoadPlan:
    """A road connecting two settlements."""
    start_name: str
    end_name: str
    road_type: str      # "king_road", "paved_road", "gravel_road", "dirt_track"
    waypoints: List[Tuple[int, int]] = field(default_factory=list)
    # World-coordinate waypoints along the road path


@dataclass
class RiverPlan:
    """A river path from source to mouth."""
    points: List[Tuple[int, int]] = field(default_factory=list)


@dataclass
class SpecialLocation:
    """A non-settlement point of interest (ruins, shrine, temple, etc.)."""
    name: str
    kind: str           # "temple", "ruins", "shrine", "dungeon", "test_island"
    x: int
    y: int
    radius: int


@dataclass
class RegionPlan:
    """A named region of the world."""
    name: str
    center_x: int
    center_y: int
    radius: int
    data: Dict          # biome preferences, races, settlement themes


# ================================================================
# WORLD PLAN
# ================================================================

class WorldPlan:
    """Compact description of the entire game world.

    This is generated once during world creation and persists for the
    lifetime of the game. It contains no tile data — just the metadata
    needed to regenerate tiles deterministically.
    """

    def __init__(self, width: int, height: int, seed: int,
                 use_history_sim: bool = False):
        self.width = width
        self.height = height
        self.seed = seed
        self.use_history_sim = use_history_sim

        # Noise parameters (used by chunk generator for terrain)
        self.elevation_scale = 0.012     # lower = larger features for bigger world
        self.moisture_scale = 0.018
        self.edge_falloff_strength = 0.55  # softer falloff for larger world

        # Plan data — populated by generate()
        self.settlements: List[SettlementPlan] = []
        self.roads: List[RoadPlan] = []
        self.rivers: List[RiverPlan] = []
        self.regions: List[RegionPlan] = []
        self.special_locations: List[SpecialLocation] = []

        # Key locations
        self.spawn_point: Tuple[int, int] = (width // 2, height // 2)
        self.test_island_spawn: Optional[Tuple[int, int]] = None
        self.test_island_rect: Optional[Tuple[int, int, int, int]] = None

        # Kingdom metadata — planned kingdoms for the governance system
        self.kingdoms: List[Dict] = []
        # Each: {"name": str, "race": str, "governance_style": str,
        #        "capital_settlement": str, "territory_settlements": [str],
        #        "region": str, "center_x": int, "center_y": int,
        #        "ruler_name": str, "treasury": int}

        # Foreign contacts — other continents for gossip/trade
        self.foreign_contacts: List[Dict] = []

        # NPC roster (compact — full NPC objects created on zone activation)
        self.npc_roster: List[Dict] = []
        # Each: {"name": str, "class": str, "race": str, "settlement": str,
        #        "home_x": float, "home_y": float, "role": str}

        # History simulation output (populated when use_history_sim=True)
        self._history: List[str] = []
        self._history_ruins: list = []
        self._history_diplomatic_relations: dict = {}
        self._history_trade_routes: list = []

    def generate(self, progress_callback=None):
        """Generate the complete world plan.

        This is the ONE-TIME upfront generation that decides where
        everything goes. It's fast because it doesn't generate tile data.

        Parameters
        ----------
        progress_callback : callable, optional
            Called as progress_callback(message, fraction) to report progress.
            Useful for loading screen display.
        """
        rng = random.Random(self.seed)

        # Pre-compute a low-res elevation grid for fast settlement placement.
        # Resolution: 1 sample per 10 tiles = 1000x1000 for a 10,000 world.
        self._build_elevation_cache()

        self._plan_regions(rng)
        self._plan_rivers(rng)

        if self.use_history_sim:
            # Use the history simulation for settlements, roads, kingdoms
            self._plan_settlements_simulated(rng, years=500,
                                             progress_callback=progress_callback)
        else:
            self._plan_settlements(rng)
            self._plan_roads(rng)

        self._plan_special_locations(rng)
        self._plan_test_island()
        self._plan_spawn_temple()

        if not self.use_history_sim:
            # History sim already sets up kingdoms
            self._plan_kingdoms(rng)

        self._plan_foreign_contacts()

        # Post-planning specialization passes
        self._assign_capital_specializations()
        self._assign_trade_connections()

        # Re-evaluate crossroads now that roads exist
        for sp in self.settlements:
            if sp.specialization == "general":
                road_count = 0
                for road in self.roads:
                    for wx, wy in road.waypoints:
                        if abs(wx - sp.x) < 25 and abs(wy - sp.y) < 25:
                            road_count += 1
                            break
                if road_count >= 3:
                    sp.specialization = "crossroads"

        self._build_npc_roster(rng)

    # ------------------------------------------------------------------
    # Elevation cache (low-res for fast queries)
    # ------------------------------------------------------------------

    def _build_elevation_cache(self):
        """Pre-compute a coarse elevation grid using vectorized noise.

        Resolution: 1 sample per ELEV_CACHE_STEP tiles.
        Used for fast land/water checks during settlement placement.
        """
        import numpy as np
        from game.world.chunk_generator import _fbm_vec

        step = 10
        self._elev_step = step
        cw = self.width // step
        ch = self.height // step

        xs = np.arange(cw, dtype=np.float32) * step
        ys = np.arange(ch, dtype=np.float32) * step
        xx, yy = np.meshgrid(xs, ys)

        elev = _fbm_vec(xx * self.elevation_scale,
                         yy * self.elevation_scale,
                         octaves=5, seed=self.seed)

        # Apply edge falloff
        edge_dx = (xx / self.width - 0.5) * 2
        edge_dy = (yy / self.height - 0.5) * 2
        edge_dist = np.sqrt(edge_dx**2 + edge_dy**2)
        elev *= np.maximum(0.0, 1.0 - edge_dist * self.edge_falloff_strength)

        self._elev_cache = elev  # numpy array [ch, cw]
        self._elev_cw = cw
        self._elev_ch = ch

    def get_elevation_fast(self, x: int, y: int) -> float:
        """Fast elevation lookup from the coarse cache."""
        step = self._elev_step
        ci = min(x // step, self._elev_cw - 1)
        cj = min(y // step, self._elev_ch - 1)
        return float(self._elev_cache[cj, ci])

    # ------------------------------------------------------------------
    # Settlement specialization
    # ------------------------------------------------------------------

    def _determine_specialization(self, sx: int, sy: int, kind: str,
                                  rng) -> Tuple[str, Dict]:
        """Determine settlement specialization based on terrain context.

        Analyzes the terrain in a radius around the settlement center,
        counts nearby roads/rivers, and picks the best-fitting
        specialization.

        Returns (specialization_name, terrain_counts_dict).
        """
        import numpy as np

        radius = 20  # tiles to scan around settlement center
        step = self._elev_step

        # Count terrain types from the elevation cache
        terrain_counts = {
            "water": 0, "shallow_water": 0, "sand": 0, "grass": 0,
            "forest": 0, "dense_forest": 0, "mountain": 0, "snow": 0,
            "swamp": 0,
        }

        # Also compute moisture for forest/swamp detection
        from game.world.chunk_generator import _fbm_vec

        # Sample in a grid around the settlement
        sample_step = 2  # sample every 2 tiles for speed
        total_samples = 0
        for dy in range(-radius, radius + 1, sample_step):
            for dx in range(-radius, radius + 1, sample_step):
                wx, wy = sx + dx, sy + dy
                if wx < 0 or wx >= self.width or wy < 0 or wy >= self.height:
                    continue
                elev = self.get_elevation_fast(wx, wy)
                total_samples += 1

                if elev < 0.22:
                    terrain_counts["water"] += 1
                elif elev < 0.28:
                    terrain_counts["sand"] += 1
                elif elev >= 0.78:
                    terrain_counts["snow"] += 1
                elif elev >= 0.65:
                    terrain_counts["mountain"] += 1
                else:
                    # Mid-elevation: need moisture for biome
                    # Use a fast approximation — check the cache
                    terrain_counts["grass"] += 1  # default

        # Refine grass count with moisture data for forest/swamp
        # Use vectorized noise for a small patch
        xs_arr = np.array([sx], dtype=np.float32)
        ys_arr = np.array([sy], dtype=np.float32)
        moist_center = float(_fbm_vec(
            xs_arr * self.moisture_scale,
            ys_arr * self.moisture_scale,
            octaves=4, seed=self.seed + 7919)[0])

        # Heuristic: if the center point is moist and surrounded by
        # mid-elevation, reclassify some grass as forest/swamp
        elev_center = self.get_elevation_fast(sx, sy)
        if elev_center < 0.35 and moist_center > 0.60:
            # Swamp conditions
            swamp_convert = terrain_counts["grass"] // 3
            terrain_counts["swamp"] += swamp_convert
            terrain_counts["grass"] -= swamp_convert
        if moist_center > 0.50:
            forest_convert = terrain_counts["grass"] // 3
            terrain_counts["forest"] += forest_convert
            terrain_counts["grass"] -= forest_convert
        if moist_center > 0.65:
            dense_convert = terrain_counts["forest"] // 2
            terrain_counts["dense_forest"] += dense_convert
            terrain_counts["forest"] -= dense_convert

        # Count nearby river points
        river_nearby = 0
        for river in self.rivers:
            for px, py in river.points:
                if abs(px - sx) < 30 and abs(py - sy) < 30:
                    river_nearby += 1

        # Count roads converging near this settlement
        road_count = 0
        for road in self.roads:
            for wx, wy in road.waypoints:
                if abs(wx - sx) < 25 and abs(wy - sy) < 25:
                    road_count += 1
                    break

        # Check if this is a kingdom capital
        for kingdom in self.kingdoms:
            if kingdom.get("capital_settlement") == "":
                continue
            # Capital check will happen after kingdoms are assigned;
            # for now, skip — capitals are set in _assign_capital_specializations

        # Check if near kingdom border
        near_border = False
        if len(self.regions) >= 2:
            # Find the two closest region centers
            region_dists = []
            for r in self.regions:
                d = math.sqrt((r.center_x - sx)**2 + (r.center_y - sy)**2)
                region_dists.append((d, r))
            region_dists.sort(key=lambda x: x[0])
            if len(region_dists) >= 2:
                d1 = region_dists[0][0]
                d2 = region_dists[1][0]
                r1_radius = region_dists[0][1].radius
                # If roughly equidistant from two regions, it's a border
                if d2 < r1_radius * 1.2 and abs(d1 - d2) < r1_radius * 0.3:
                    near_border = True

        # Determine specialization by priority
        water_pct = terrain_counts["water"] / max(total_samples, 1)
        mountain_pct = terrain_counts["mountain"] / max(total_samples, 1)
        forest_pct = (terrain_counts["forest"] + terrain_counts["dense_forest"]) / max(total_samples, 1)
        grass_pct = terrain_counts["grass"] / max(total_samples, 1)
        sand_pct = terrain_counts["sand"] / max(total_samples, 1)
        swamp_pct = terrain_counts["swamp"] / max(total_samples, 1)

        # Water access is the strongest signal
        if water_pct > 0.15 or river_nearby > 5:
            if kind in ("town", "city"):
                return "port", terrain_counts
            else:
                return "fishing", terrain_counts

        # Mountain settlements
        if mountain_pct > 0.15:
            return "mining", terrain_counts

        # Swamp settlements
        if swamp_pct > 0.12:
            return "swamp", terrain_counts

        # Forest settlements
        if forest_pct > 0.25:
            return "lumber", terrain_counts

        # Desert/arid settlements
        if sand_pct > 0.20:
            return "oasis", terrain_counts

        # Border town
        if near_border and kind in ("town", "city", "village"):
            return "border", terrain_counts

        # Crossroads (multiple roads converging)
        if road_count >= 3:
            return "crossroads", terrain_counts

        # Default: agricultural for grass-heavy areas
        if grass_pct > 0.30:
            return "agricultural", terrain_counts

        return "general", terrain_counts

    def _score_city_location(self, sx: int, sy: int) -> float:
        """Score a potential city location based on geographic advantage.

        Higher scores = better city locations. Considers:
        - Water access (river/coast for trade)
        - Road potential (central position)
        - Resource diversity
        - Defensibility
        """
        score = 0.0

        # Water access: rivers nearby = major bonus
        river_nearby = 0
        for river in self.rivers:
            for px, py in river.points:
                if abs(px - sx) < 40 and abs(py - sy) < 40:
                    river_nearby += 1
        score += min(river_nearby, 10) * 8.0

        # Elevation diversity (more terrain types = more resources)
        terrain_types = set()
        for dy in range(-25, 26, 5):
            for dx in range(-25, 26, 5):
                elev = self.get_elevation_fast(
                    max(0, min(self.width - 1, sx + dx)),
                    max(0, min(self.height - 1, sy + dy)))
                if elev < 0.22:
                    terrain_types.add("water")
                elif elev < 0.28:
                    terrain_types.add("sand")
                elif elev >= 0.65:
                    terrain_types.add("mountain")
                else:
                    terrain_types.add("grass")
        score += len(terrain_types) * 6.0

        # Centrality to region (distance from region center)
        for r in self.regions:
            d = math.sqrt((r.center_x - sx)**2 + (r.center_y - sy)**2)
            if d < r.radius:
                # Closer to center = better trade position
                centrality = 1.0 - (d / r.radius)
                score += centrality * 10.0
                break

        # Defensibility: river on one side, hills nearby
        elev_center = self.get_elevation_fast(sx, sy)
        if 0.35 <= elev_center <= 0.50:
            score += 5.0  # on a hill but not mountain

        # Not too close to edge
        edge_dist = min(sx, sy, self.width - sx, self.height - sy)
        if edge_dist > self.width * 0.15:
            score += 5.0

        return score

    def _assign_capital_specializations(self):
        """After kingdoms are planned, mark capital settlements."""
        for kingdom in self.kingdoms:
            cap_name = kingdom.get("capital_settlement", "")
            if not cap_name:
                continue
            for s in self.settlements:
                if s.name == cap_name:
                    s.specialization = "capital"
                    break

    def _assign_trade_connections(self):
        """After roads are planned, record which settlements connect."""
        for road in self.roads:
            for s in self.settlements:
                if s.name == road.start_name:
                    if road.end_name not in s.trade_connections:
                        s.trade_connections.append(road.end_name)
                elif s.name == road.end_name:
                    if road.start_name not in s.trade_connections:
                        s.trade_connections.append(road.start_name)

    # ------------------------------------------------------------------
    # Region planning
    # ------------------------------------------------------------------

    def _plan_regions(self, rng: random.Random):
        """Assign regions to the world — cultural/biome areas."""
        from game.world.regions import REGIONS

        cx, cy = self.width // 2, self.height // 2
        # Scale region radii to world size
        base_radius = min(self.width, self.height) // 5

        region_defs = [
            ("human_kingdoms", cx + rng.randint(-50, 50),
             cy + rng.randint(-50, 50), base_radius),
            ("elven_forests", cx - base_radius, cy - base_radius // 2,
             int(base_radius * 0.8)),
            ("dwarven_highlands", cx + base_radius // 2,
             cy - base_radius, int(base_radius * 0.7)),
            ("orcish_badlands", cx + base_radius,
             cy + base_radius // 2, int(base_radius * 0.8)),
            ("coastal_reaches", cx - base_radius // 2,
             cy + base_radius, int(base_radius * 0.9)),
            ("wild_frontier", cx, cy - base_radius,
             int(base_radius * 0.6)),
        ]

        for name, rx, ry, radius in region_defs:
            data = REGIONS.get(name, {})
            self.regions.append(RegionPlan(
                name=data.get("name", name),
                center_x=max(radius, min(self.width - radius, rx)),
                center_y=max(radius, min(self.height - radius, ry)),
                radius=radius,
                data=data,
            ))

    # ------------------------------------------------------------------
    # River planning
    # ------------------------------------------------------------------

    def _plan_rivers(self, rng: random.Random):
        """Plan river paths. Rivers flow from high ground toward the coast.

        Strategy: find the highest points on the elevation cache, then
        trace downhill toward the ocean. Uses a lower threshold (0.40)
        to find plenty of starting points on hills and mountains.
        """
        import numpy as np

        num_rivers = max(10, (self.width * self.height) // 1_500_000)

        # Find candidate starting points from the elevation cache
        # Sort by elevation (descending) so we start from the highest peaks
        elev = self._elev_cache
        step = self._elev_step
        flat = elev.flatten()
        # Get indices above 0.35 (hills, highlands, mountains)
        high_mask = flat > 0.35
        high_indices = np.where(high_mask)[0]
        if len(high_indices) == 0:
            return

        # Sort by elevation, take the top candidates
        sorted_idx = high_indices[np.argsort(flat[high_indices])[::-1]]
        candidates = sorted_idx[:num_rivers * 20]  # plenty of options
        rng.shuffle(list(candidates))  # randomize among top candidates

        placed = 0
        min_dist_between = max(self.width, self.height) // 20
        river_starts = []

        for idx in candidates:
            if placed >= num_rivers:
                break
            cy_c = int(idx) // self._elev_cw
            cx_c = int(idx) % self._elev_cw
            wx = cx_c * step
            wy = cy_c * step

            # Skip if too close to another river start
            too_close = any(
                abs(wx - rx) + abs(wy - ry) < min_dist_between
                for rx, ry in river_starts
            )
            if too_close:
                continue

            path = self._trace_river_path(wx, wy, rng)
            if len(path) > 10:
                self.rivers.append(RiverPlan(points=path))
                river_starts.append((wx, wy))
                placed += 1

    def _trace_river_path(self, sx: int, sy: int,
                          rng: random.Random) -> List[Tuple[int, int]]:
        """Trace a river path downhill from (sx, sy) toward the ocean.

        Uses a larger step size at the coarse elevation cache resolution
        and adds momentum to avoid oscillation between similar-height cells.
        """
        path = [(sx, sy)]
        x, y = float(sx), float(sy)
        visited = set()
        max_len = max(self.width, self.height) // 2
        step = self._elev_step  # match cache resolution (10 tiles)
        # Momentum — bias toward continuing in the same direction
        prev_dx, prev_dy = 0, 1

        for _ in range(max_len):
            key = (int(x) // step, int(y) // step)
            if key in visited:
                break
            visited.add(key)

            current_elev = self.get_elevation_fast(int(x), int(y))
            if current_elev < 0.23:
                break

            edge_dx = (x / self.width - 0.5) * 2
            edge_dy = (y / self.height - 0.5) * 2
            if math.sqrt(edge_dx**2 + edge_dy**2) > 0.90:
                break

            # Find lowest neighbor, with momentum bonus for current direction
            best_score = 999
            best_dx, best_dy = prev_dx, prev_dy
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1),
                           (1, 1), (-1, 1), (1, -1), (-1, -1)]:
                nx, ny = x + dx * step, y + dy * step
                if nx < 0 or nx >= self.width or ny < 0 or ny >= self.height:
                    continue
                nkey = (int(nx) // step, int(ny) // step)
                if nkey in visited:
                    continue  # don't revisit
                e = self.get_elevation_fast(int(nx), int(ny))
                # Momentum bonus: favor continuing in same direction
                if dx == prev_dx and dy == prev_dy:
                    e -= 0.02
                e += rng.uniform(-0.02, 0.02)
                if e < best_score:
                    best_score = e
                    best_dx, best_dy = dx, dy

            prev_dx, prev_dy = best_dx, best_dy
            x += best_dx * step
            y += best_dy * step
            x = max(1, min(self.width - 2, x))
            y = max(1, min(self.height - 2, y))
            path.append((int(x), int(y)))

        return path

    # ------------------------------------------------------------------
    # Settlement planning
    # ------------------------------------------------------------------

    def _plan_settlements(self, rng: random.Random):
        """Place settlements across the world.

        Scaled for 10,000x10,000:
        - 2-4 cities, 8-12 towns, 30-50 villages, 80-120 hamlets
        - Minimum distances scaled to world size
        """
        from game.world.regions import REGIONS

        # Settlement quotas scaled to world area
        area = self.width * self.height
        base = area / (2000 * 2000)  # relative to old world size

        quotas = {
            "city":    max(2, int(3 * base)),
            "town":    max(5, int(10 * base)),
            "village": max(15, int(40 * base)),
            "hamlet":  max(30, int(80 * base)),
        }

        # Minimum distances between settlements (in tiles)
        min_dist = {
            "city":    int(300 * math.sqrt(base)),
            "town":    int(200 * math.sqrt(base)),
            "village": int(100 * math.sqrt(base)),
            "hamlet":  int(60 * math.sqrt(base)),
        }

        # Settlement radii (bigger world = bigger settlements)
        radii = {
            "hamlet":  int(20 * math.sqrt(base)),
            "village": int(40 * math.sqrt(base)),
            "town":    int(70 * math.sqrt(base)),
            "city":    int(120 * math.sqrt(base)),
        }

        placed = []  # [(x, y, kind)]

        for kind in ["city", "town", "village", "hamlet"]:
            count = quotas[kind]
            radius = radii[kind]
            min_d = min_dist[kind]

            for _ in range(count):
                for attempt in range(200):
                    # Pick a location within a random region
                    region = rng.choice(self.regions)
                    angle = rng.uniform(0, 2 * math.pi)
                    dist = rng.uniform(0, region.radius * 0.8)
                    sx = int(region.center_x + math.cos(angle) * dist)
                    sy = int(region.center_y + math.sin(angle) * dist)

                    # Bounds check with margin
                    margin = radius + 20
                    if not (margin < sx < self.width - margin and
                            margin < sy < self.height - margin):
                        continue

                    # Check elevation — avoid water and mountains
                    elev = self.get_elevation_fast(sx, sy)
                    if elev < 0.25 or elev > 0.65:
                        continue  # water or mountain

                    # Distance check
                    too_close = any(
                        math.sqrt((px - sx)**2 + (py - sy)**2) < min_d
                        for px, py, pk in placed
                    )
                    if too_close:
                        continue

                    # Check test island exclusion
                    if self.test_island_rect:
                        rx, ry, rw, rh = self.test_island_rect
                        if rx <= sx <= rx + rw and ry <= sy <= ry + rh:
                            continue

                    # Place it!
                    region_data = region.data
                    race = rng.choice(region_data.get("primary_races",
                                                       ["Human"]))
                    names = region_data.get("settlement_names",
                                            ["Settlement"])
                    name = rng.choice(names) if names else f"{kind.title()}"
                    # Avoid duplicate names
                    existing = {s.name for s in self.settlements}
                    if name in existing:
                        name = f"{name} {rng.choice(['East', 'West', 'North', 'South', 'New', 'Old', 'Upper', 'Lower'])}"

                    pop = {
                        "hamlet": rng.randint(5, 15),
                        "village": rng.randint(15, 40),
                        "town": rng.randint(40, 100),
                        "city": rng.randint(100, 250),
                    }[kind]

                    sp = SettlementPlan(
                        name=name, kind=kind, x=sx, y=sy,
                        radius=radius, region=region.name,
                        race=race, population=pop,
                    )

                    # Determine geographic specialization
                    spec, terrain_ctx = self._determine_specialization(
                        sx, sy, kind, rng)
                    sp.specialization = spec
                    sp.terrain_context = terrain_ctx

                    self.settlements.append(sp)
                    placed.append((sx, sy, kind))
                    break

    def _plan_settlements_simulated(self, rng: random.Random,
                                     years: int = 500,
                                     progress_callback=None):
        """Use history simulation instead of algorithmic placement.

        Runs the HistorySimulation for the given number of years and
        converts its output into WorldPlan data: settlements, roads,
        kingdoms, ruins (as special locations), and historical events.
        """
        from game.world.history_sim import HistorySimulation

        sim = HistorySimulation(
            self.width, self.height, self.seed,
            self._elev_cache, self._elev_step,
            moisture_scale=self.moisture_scale,
            elevation_scale=self.elevation_scale,
            edge_falloff_strength=self.edge_falloff_strength,
        )
        result = sim.run(years=years, rng=rng,
                         progress_callback=progress_callback)

        # Convert HistoryResult into WorldPlan data structures
        self.settlements = result.settlements
        self.roads = result.roads
        self.kingdoms = result.kingdoms

        # Determine terrain context and refine specializations for each
        # settlement now that they are placed
        for sp in self.settlements:
            spec, terrain_ctx = self._determine_specialization(
                sp.x, sp.y, sp.kind, rng)
            # Keep the history-sim specialization if it was already set
            # to something meaningful; otherwise use terrain-derived one
            if sp.specialization == "general":
                sp.specialization = spec
            sp.terrain_context = terrain_ctx

        # Convert ruins into special locations with specific ruin types
        _ruin_kind_map = {
            "abandoned_castle": "ruins",
            "ruined_tower": "ruins",
            "old_dungeon": "dungeon",
            "ancient_temple": "temple",
            "dragon_lair": "dungeon",
            "necropolis": "dungeon",
            "abandoned_mine": "ruins",
            "fallen_city": "ruins",
            "watchtower": "ruins",
            "bandit_hideout": "ruins",
            "hermit_cave": "shrine",
            "collapsed_bridge": "ruins",
            "ancient_ruins": "ruins",
        }
        for ruin in result.ruins:
            ruin_radius = {"city": 12, "town": 8, "village": 6,
                           "castle": 8}.get(ruin.original_kind, 4)
            ruin_type = getattr(ruin, "ruin_type", "ruins")
            loc_kind = _ruin_kind_map.get(ruin_type, "ruins")
            # Use a descriptive name based on ruin type
            if ruin_type in ("ancient_temple", "dragon_lair",
                             "old_dungeon", "hermit_cave",
                             "ancient_ruins"):
                display_name = ruin.name  # already has a good name
            else:
                display_name = f"Ruins of {ruin.name}"
            self.special_locations.append(SpecialLocation(
                name=display_name,
                kind=loc_kind,
                x=ruin.x,
                y=ruin.y,
                radius=ruin_radius,
            ))

        # Store historical events for NPC lore / gossip
        self._history = result.historical_events
        self._history_ruins = result.ruins
        self._history_diplomatic_relations = result.diplomatic_relations
        self._history_trade_routes = result.trade_routes
        self._history_creature_territories = getattr(
            result, "creature_territories", [])
        self._history_figures = getattr(
            result, "historical_figures", [])

    # ------------------------------------------------------------------
    # Road planning
    # ------------------------------------------------------------------

    def _plan_roads(self, rng: random.Random):
        """Plan road network using MST + extra connections.

        Roads are stored as waypoint lists. The chunk generator stamps
        road tiles along these paths.
        """
        if len(self.settlements) < 2:
            return

        # Build MST using Kruskal's
        nodes = [(s.x, s.y, s.name) for s in self.settlements]
        edges = []
        for i, (x1, y1, n1) in enumerate(nodes):
            for j, (x2, y2, n2) in enumerate(nodes):
                if i < j:
                    d = math.sqrt((x1 - x2)**2 + (y1 - y2)**2)
                    edges.append((d, i, j))
        edges.sort()

        # Union-Find
        parent = list(range(len(nodes)))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        mst_edges = []
        for d, i, j in edges:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj
                mst_edges.append((i, j, d))
            if len(mst_edges) == len(nodes) - 1:
                break

        # Add some extra edges for redundancy (20% of MST)
        extra = max(2, len(mst_edges) // 5)
        mst_set = {(min(i, j), max(i, j)) for i, j, d in mst_edges}
        for d, i, j in edges:
            key = (min(i, j), max(i, j))
            if key not in mst_set and extra > 0:
                mst_edges.append((i, j, d))
                mst_set.add(key)
                extra -= 1

        # Create road plans with straight-line waypoints
        # (chunk generator can refine paths around obstacles)
        for i, j, d in mst_edges:
            x1, y1, n1 = nodes[i]
            x2, y2, n2 = nodes[j]

            # Road type based on settlement importance
            kind_i = next((s.kind for s in self.settlements if s.name == n1),
                          "hamlet")
            kind_j = next((s.kind for s in self.settlements if s.name == n2),
                          "hamlet")
            importance = {"city": 4, "town": 3, "village": 2, "hamlet": 1}
            imp = max(importance.get(kind_i, 1), importance.get(kind_j, 1))
            road_type = {4: "king_road", 3: "paved_road",
                         2: "gravel_road", 1: "dirt_track"}[imp]

            # Generate waypoints (Bresenham-ish with slight curves)
            waypoints = self._road_waypoints(x1, y1, x2, y2, rng)

            self.roads.append(RoadPlan(
                start_name=n1, end_name=n2,
                road_type=road_type, waypoints=waypoints,
            ))

    def _road_waypoints(self, x1: int, y1: int, x2: int, y2: int,
                        rng: random.Random) -> List[Tuple[int, int]]:
        """Generate waypoints between two points with natural curves."""
        points = [(x1, y1)]
        dist = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        segments = max(3, int(dist / 50))

        for i in range(1, segments):
            t = i / segments
            # Lerp with random offset for natural curves
            mx = x1 + (x2 - x1) * t + rng.randint(-15, 15)
            my = y1 + (y2 - y1) * t + rng.randint(-15, 15)
            mx = max(5, min(self.width - 5, mx))
            my = max(5, min(self.height - 5, my))
            points.append((int(mx), int(my)))

        points.append((x2, y2))
        return points

    # ------------------------------------------------------------------
    # Special locations
    # ------------------------------------------------------------------

    def _plan_special_locations(self, rng: random.Random):
        """Place ruins, shrines, dungeons in wilderness."""
        num_ruins = max(10, (self.width * self.height) // 2_000_000)
        ruin_names = [
            "Ancient Ruins", "Forgotten Temple", "Crumbling Tower",
            "Lost Catacombs", "Shattered Keep", "Buried Sanctum",
            "The Dark Catacombs", "Goblin Warren", "Tomb of the Ancients",
            "Abandoned Mine", "Haunted Barrow", "Collapsed Shrine",
        ]

        for _ in range(num_ruins):
            for attempt in range(100):
                x = rng.randint(50, self.width - 50)
                y = rng.randint(50, self.height - 50)

                # Must be on land, not near settlements
                elev = self.get_elevation_fast(x, y)
                if elev < 0.25 or elev > 0.7:
                    continue

                too_close = any(
                    math.sqrt((s.x - x)**2 + (s.y - y)**2) < 80
                    for s in self.settlements
                ) or any(
                    math.sqrt((l.x - x)**2 + (l.y - y)**2) < 40
                    for l in self.special_locations
                )
                if too_close:
                    continue

                self.special_locations.append(SpecialLocation(
                    name=rng.choice(ruin_names),
                    kind="ruins",
                    x=x, y=y, radius=6,
                ))
                break

    def _plan_test_island(self):
        """Plan the isolated test island in deep ocean."""
        island_w, island_h = 120, 80
        ix = int(self.width * 0.90)
        iy = int(self.height * 0.10)

        buf = 10
        ix = max(island_w // 2 + buf, min(self.width - island_w // 2 - buf, ix))
        iy = max(island_h // 2 + buf, min(self.height - island_h // 2 - buf, iy))

        margin = 30
        self.test_island_rect = (
            ix - island_w // 2 - margin,
            iy - island_h // 2 - margin,
            island_w + margin * 2,
            island_h + margin * 2,
        )

        temple_x = ix - island_w // 2 + 20
        temple_y = iy
        self.test_island_spawn = (temple_x, temple_y)

        self.special_locations.append(SpecialLocation(
            name="Test Island", kind="test_island",
            x=ix, y=iy, radius=max(island_w, island_h) // 2,
        ))
        self.special_locations.append(SpecialLocation(
            name="Temple of Testing", kind="temple",
            x=temple_x, y=temple_y, radius=5,
        ))

        # Test building: 3 stories + underground, east of temple
        tb_x = temple_x + 20
        tb_y = temple_y
        self.special_locations.append(SpecialLocation(
            name="Test Tower", kind="test_building",
            x=tb_x, y=tb_y, radius=6,
        ))

        # Register as a settlement so building-finding code works
        tb_bx = tb_x - 5  # building top-left (10x10 centered)
        tb_by = tb_y - 5
        self.settlements.append(SettlementPlan(
            name="Test Tower", kind="hamlet",
            x=tb_x, y=tb_y, radius=8,
            region="", race="Human", population=0,
            buildings=[{
                "kind": "tower", "name": "Test Tower",
                "x": tb_bx, "y": tb_by, "w": 10, "h": 10,
                "bp_tiles": None,  # ground floor stamped by chunk_generator
                "floors": self._generate_test_tower_floors(10, 10),
                "num_floors_up": 2,
                "num_floors_down": 1,
            }],
        ))

    def _generate_test_tower_floors(self, w, h):
        """Generate all floor layouts for the test tower."""
        from game.settings import (WALL, FLOOR, DOOR, STAIRS_UP, STAIRS_DOWN,
                                    TABLE, BED, CHEST, BOOKSHELF, BARREL,
                                    FIREPLACE, WINDOW)

        # Ground floor (matches _stamp_test_building in chunk_generator)
        ground = [
            [WALL, WALL,       WALL,  WALL,  WALL,  WALL,  WALL,  WALL,       WALL,  WALL],
            [WALL, STAIRS_DOWN,FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR,      STAIRS_UP, WALL],
            [WALL, FLOOR,      FLOOR, TABLE, FLOOR, FLOOR, FLOOR, FLOOR,      FLOOR, WALL],
            [WALL, FLOOR,      FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, BOOKSHELF,  FLOOR, WALL],
            [WALL, FLOOR,      FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR,      FLOOR, WALL],
            [WALL, FIREPLACE,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR,      FLOOR, WALL],
            [WALL, FLOOR,      FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR,      FLOOR, WALL],
            [WALL, FLOOR,      BED,   FLOOR, FLOOR, FLOOR, CHEST, FLOOR,      FLOOR, WALL],
            [WALL, FLOOR,      FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR,      FLOOR, WALL],
            [WALL, WALL,       WALL,  WALL,  DOOR,  DOOR,  WALL,  WALL,       WALL,  WALL],
        ]

        # Floor 1 (first upper) — bedrooms
        floor1 = [
            [WALL, WALL,   WALL,  WALL,  WALL,  WALL,  WALL,  WALL,   WALL,  WALL],
            [WALL, STAIRS_DOWN, FLOOR, FLOOR, FLOOR, WALL, FLOOR, FLOOR, STAIRS_UP, WALL],
            [WALL, FLOOR,  BED,   FLOOR, FLOOR, WALL, FLOOR, BED,   FLOOR, WALL],
            [WALL, FLOOR,  FLOOR, CHEST, FLOOR, WALL, FLOOR, FLOOR, CHEST, WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, WALL,   WALL,  FLOOR, FLOOR, FLOOR, FLOOR, WALL,  WALL,  WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, FLOOR,  TABLE, FLOOR, FLOOR, FLOOR, FLOOR, TABLE, FLOOR, WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, WALL,   WALL,  WALL, WINDOW, WINDOW, WALL, WALL,  WALL,  WALL],
        ]

        # Floor 2 (top) — study/lookout
        floor2 = [
            [WALL, WALL,   WALL,  WALL,  WALL,  WALL,  WALL,  WALL,   WALL,  WALL],
            [WALL, STAIRS_DOWN, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, FLOOR,  BOOKSHELF, FLOOR, FLOOR, FLOOR, FLOOR, BOOKSHELF, FLOOR, WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, TABLE, TABLE, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, WALL,   WALL,  WALL, WINDOW, WINDOW, WALL, WALL,  WALL,  WALL],
        ]

        # Floor -1 (basement) — storage/dungeon
        basement = [
            [WALL, WALL,   WALL,  WALL,  WALL,  WALL,  WALL,  WALL,   WALL,  WALL],
            [WALL, STAIRS_UP, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, FLOOR,  BARREL, FLOOR, FLOOR, WALL,  FLOOR, BARREL, FLOOR, WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, FLOOR, WALL,  FLOOR, FLOOR, FLOOR, WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, WALL,   WALL,  FLOOR, FLOOR, FLOOR, FLOOR, WALL,  WALL,  WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, FLOOR,  CHEST, FLOOR, FLOOR, FLOOR, CHEST, FLOOR, FLOOR, WALL],
            [WALL, FLOOR,  FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, FLOOR, WALL],
            [WALL, WALL,   WALL,  WALL,  WALL,  WALL,  WALL,  WALL,  WALL,  WALL],
        ]

        return {0: ground, 1: floor1, 2: floor2, -1: basement}

    def _plan_spawn_temple(self):
        """Plan the main spawn temple at world center."""
        cx, cy = self.width // 2, self.height // 2
        self.spawn_point = (cx, cy)
        self.special_locations.append(SpecialLocation(
            name="Temple of Awakening", kind="temple",
            x=cx, y=cy, radius=6,
        ))

        # Starter village east of temple
        vx, vy = cx + 60, cy  # further away in bigger world
        spec, terrain_ctx = self._determine_specialization(
            vx, vy, "village", random.Random(self.seed + 999))
        self.settlements.append(SettlementPlan(
            name="Hearthstone", kind="village",
            x=vx, y=vy, radius=40,
            region="The Heartlands", race="Human",
            population=20,
            specialization=spec,
            terrain_context=terrain_ctx,
        ))

    # ------------------------------------------------------------------
    # Kingdom planning
    # ------------------------------------------------------------------

    def _plan_kingdoms(self, rng: random.Random):
        """Plan kingdoms based on regions and assign settlements to them.

        Creates 6 kingdoms:
        - 3 human-aligned (human monarchy, elven council, dwarven clans)
        - 1 undead
        - 2 monster (orc warlord, goblin tribal)
        """
        # Ruler name pools per race
        human_rulers = [
            "King Aldric", "Queen Seraphina", "Lord Edwyn", "Lady Margaux",
            "Duke Alderon", "Regent Castellan",
        ]
        elven_rulers = [
            "Archon Galadwen", "Councillor Thalion", "Elder Arannis",
            "Speaker Celeborn",
        ]
        dwarven_rulers = [
            "Thane Borik Ironhand", "Thane Brunhild Stoneshield",
            "High Forgemaster Durin", "Clan Elder Gretta",
        ]
        orc_rulers = [
            "Warchief Grommash", "Warchief Urzog Bloodfist",
            "Overlord Kargath", "Boss Zug'thak",
        ]
        goblin_rulers = [
            "Great Sneak Nixle", "Boss Skrit", "Chief Grizznak",
            "Grand Skulker Plit",
        ]
        undead_rulers = [
            "Lich Lord Veranthos", "The Pale King", "Necrolord Ashenveil",
            "Dread Sovereign Malachar",
        ]

        rng.shuffle(human_rulers)
        rng.shuffle(elven_rulers)
        rng.shuffle(dwarven_rulers)
        rng.shuffle(orc_rulers)
        rng.shuffle(goblin_rulers)
        rng.shuffle(undead_rulers)

        from game.world.regions import REGIONS as _REGIONS

        # Map region names to RegionPlan objects
        region_map = {r.name: r for r in self.regions}
        # Also map by key (e.g. "human_kingdoms" -> "The Heartlands")
        region_key_map = {}
        for r in self.regions:
            for rkey, rdata in _REGIONS.items():
                if rdata.get("name") == r.name:
                    region_key_map[rkey] = r
                    break

        # Helper: find settlements in a region
        def settlements_in_region(region_name):
            return [s.name for s in self.settlements if s.region == region_name]

        # Helper: find the largest settlement in a list as capital
        def pick_capital(settlement_names):
            if not settlement_names:
                return ""
            kind_rank = {"city": 4, "town": 3, "village": 2, "hamlet": 1}
            best = None
            best_rank = -1
            for s in self.settlements:
                if s.name in settlement_names:
                    rank = kind_rank.get(s.kind, 0)
                    if rank > best_rank:
                        best_rank = rank
                        best = s.name
            return best or (settlement_names[0] if settlement_names else "")

        # Kingdom definitions
        kingdom_defs = [
            {
                "name": "Kingdom of the Heartlands",
                "race": "Human",
                "governance_style": "feudalism",
                "region_key": "human_kingdoms",
                "ruler_pool": human_rulers,
                "treasury_range": (300, 800),
            },
            {
                "name": "Elven Dominion",
                "race": "Elf",
                "governance_style": "republic",
                "region_key": "elven_forests",
                "ruler_pool": elven_rulers,
                "treasury_range": (200, 500),
            },
            {
                "name": "Dwarven Holds",
                "race": "Dwarf",
                "governance_style": "feudalism",
                "region_key": "dwarven_highlands",
                "ruler_pool": dwarven_rulers,
                "treasury_range": (400, 900),
            },
            {
                "name": "Orcish Warband",
                "race": "Half-Orc",
                "governance_style": "tyranny",
                "region_key": "orcish_badlands",
                "ruler_pool": orc_rulers,
                "treasury_range": (50, 200),
            },
            {
                "name": "Goblin Warrens",
                "race": "Goblin",
                "governance_style": "tribal",
                "region_key": "wild_frontier",
                "ruler_pool": goblin_rulers,
                "treasury_range": (20, 100),
            },
            {
                "name": "The Undead Realm",
                "race": "Undead",
                "governance_style": "autocracy",
                "region_key": "coastal_reaches",
                "ruler_pool": undead_rulers,
                "treasury_range": (100, 400),
            },
        ]

        for kdef in kingdom_defs:
            region = region_key_map.get(kdef["region_key"])
            if not region:
                continue

            territory = settlements_in_region(region.name)
            capital = pick_capital(territory)

            self.kingdoms.append({
                "name": kdef["name"],
                "race": kdef["race"],
                "governance_style": kdef["governance_style"],
                "capital_settlement": capital,
                "territory_settlements": territory,
                "region": region.name,
                "center_x": region.center_x,
                "center_y": region.center_y,
                "ruler_name": kdef["ruler_pool"][0],
                "treasury": rng.randint(*kdef["treasury_range"]),
            })

    def _plan_foreign_contacts(self):
        """Define foreign contacts from other continents.

        These are not playable kingdoms — they represent distant powers
        that send merchants, sailors, and diplomats. Used by the
        gossip/information system.
        """
        self.foreign_contacts = [
            {
                "name": "Zarath Empire",
                "relation": "trade_partner",
                "description": "A vast desert empire across the eastern sea. "
                               "Known for silks, spices, and arcane scholarship.",
                "sends": ["merchants", "scholars"],
                "trade_goods": ["silk", "spices", "arcane_tomes", "gemstones"],
            },
            {
                "name": "Southern Isles",
                "relation": "explorers",
                "description": "A loose confederation of tropical islands. "
                               "Their sailors map the world's coastlines.",
                "sends": ["sailors", "explorers", "cartographers"],
                "trade_goods": ["exotic_fruits", "pearls", "rum", "navigation_charts"],
            },
        ]

    # ------------------------------------------------------------------
    # NPC roster
    # ------------------------------------------------------------------

    def _build_npc_roster(self, rng: random.Random):
        """Create a compact roster of all NPCs in the world.

        Full NPC objects are created only when a zone becomes active.
        The roster stores just enough to recreate them deterministically.

        Professions are drawn from the settlement's specialization pool
        so that a mining town is mostly miners, a port is mostly sailors, etc.
        """
        from game.data.dnd import random_npc_class_and_race
        from game.settings import NPC_NAMES, PROFESSIONS
        from game.world.specializations import SPECIALIZATION_PROFESSIONS

        name_pool = list(NPC_NAMES) + [
            "Alara", "Brom", "Circe", "Dorian", "Elowen", "Faelen",
            "Gwynn", "Hadrian", "Isolde", "Jareth", "Kael", "Lyra",
            "Mordecai", "Niamh", "Orin", "Perrin", "Rhiannon", "Silas",
            "Tamsin", "Ulric", "Vesper", "Wynne", "Xara", "Yorick", "Zelda",
        ]
        rng.shuffle(name_pool)
        name_idx = [0]

        def next_name():
            if name_idx[0] < len(name_pool):
                n = name_pool[name_idx[0]]
                name_idx[0] += 1
                return n
            return f"NPC_{rng.randint(1000, 9999)}"

        for settlement in self.settlements:
            # Get specialization-aware profession pool
            spec = getattr(settlement, 'specialization', 'general')
            spec_pool = SPECIALIZATION_PROFESSIONS.get(spec)

            if spec_pool:
                prof_names = [p for p, w in spec_pool]
                prof_weights = [w for p, w in spec_pool]
            else:
                prof_names = None
                prof_weights = None

            for i in range(settlement.population):
                cls, race = random_npc_class_and_race()
                if settlement.race and rng.random() < 0.7:
                    race = settlement.race

                # Assign home position near settlement center
                angle = rng.uniform(0, 2 * math.pi)
                dist = rng.uniform(0, settlement.radius * 0.6)
                hx = settlement.x + math.cos(angle) * dist
                hy = settlement.y + math.sin(angle) * dist

                # Pick profession from specialization pool (80%) or generic (20%)
                if prof_names and rng.random() < 0.80:
                    role = rng.choices(prof_names, weights=prof_weights, k=1)[0]
                else:
                    role = rng.choice(PROFESSIONS)

                self.npc_roster.append({
                    "name": next_name(),
                    "class": cls,
                    "race": race,
                    "settlement": settlement.name,
                    "home_x": hx,
                    "home_y": hy,
                    "role": role,
                })

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def settlements_in_rect(self, x: int, y: int, w: int, h: int
                            ) -> List[SettlementPlan]:
        """Return settlements whose center falls within the rectangle."""
        return [s for s in self.settlements
                if x <= s.x < x + w and y <= s.y < y + h]

    def settlements_overlapping_chunk(self, cx: int, cy: int,
                                       chunk_size: int) -> List[SettlementPlan]:
        """Return settlements that could have buildings in this chunk."""
        x0 = cx * chunk_size
        y0 = cy * chunk_size
        return [s for s in self.settlements
                if (s.x - s.radius < x0 + chunk_size and
                    s.x + s.radius > x0 and
                    s.y - s.radius < y0 + chunk_size and
                    s.y + s.radius > y0)]

    def roads_in_chunk(self, cx: int, cy: int,
                       chunk_size: int) -> List[RoadPlan]:
        """Return roads that pass through or near this chunk."""
        x0 = cx * chunk_size
        y0 = cy * chunk_size
        x1 = x0 + chunk_size
        y1 = y0 + chunk_size
        margin = 20  # road width buffer
        result = []
        for road in self.roads:
            for wx, wy in road.waypoints:
                if (x0 - margin <= wx <= x1 + margin and
                        y0 - margin <= wy <= y1 + margin):
                    result.append(road)
                    break
        return result

    def rivers_in_chunk(self, cx: int, cy: int,
                        chunk_size: int) -> List[RiverPlan]:
        """Return rivers that pass through this chunk."""
        x0 = cx * chunk_size
        y0 = cy * chunk_size
        x1 = x0 + chunk_size
        y1 = y0 + chunk_size
        result = []
        for river in self.rivers:
            for px, py in river.points:
                if x0 <= px <= x1 and y0 <= py <= y1:
                    result.append(river)
                    break
        return result

    def npcs_in_settlement(self, name: str) -> List[Dict]:
        """Return NPC roster entries for a given settlement."""
        return [n for n in self.npc_roster if n["settlement"] == name]

    def get_summary(self) -> str:
        """Human-readable summary of the world plan."""
        # Count specializations
        spec_counts: Dict[str, int] = {}
        for s in self.settlements:
            spec = getattr(s, 'specialization', 'general')
            spec_counts[spec] = spec_counts.get(spec, 0) + 1

        spec_str = ", ".join(f"{k}: {v}" for k, v in sorted(spec_counts.items()))

        lines = [
            f"World Plan: {self.width}x{self.height} (seed={self.seed})",
            f"Regions: {len(self.regions)}",
            f"Settlements: {len(self.settlements)} "
            f"({sum(1 for s in self.settlements if s.kind == 'city')} cities, "
            f"{sum(1 for s in self.settlements if s.kind == 'town')} towns, "
            f"{sum(1 for s in self.settlements if s.kind == 'village')} villages, "
            f"{sum(1 for s in self.settlements if s.kind == 'hamlet')} hamlets)",
            f"Specializations: {spec_str}",
            f"Roads: {len(self.roads)}",
            f"Rivers: {len(self.rivers)}",
            f"Special locations: {len(self.special_locations)}",
            f"Kingdoms: {len(self.kingdoms)}",
            f"Foreign contacts: {len(self.foreign_contacts)}",
            f"NPCs: {len(self.npc_roster)}",
            f"Spawn: {self.spawn_point}",
            f"Test island: {self.test_island_spawn}",
        ]
        return "\n".join(lines)
