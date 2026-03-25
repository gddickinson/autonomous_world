"""Voronoi-based Settlement Layout — organic ward-based settlement generation."""
import math, random
from typing import List, Tuple, Dict, Optional, Set
from game.world.settlement_planner import PlannedBuilding, DefensePlan, SettlementLayout
from game.world.settlement_buildings import (
    get_settlement_buildings, apply_race_buildings, get_race_config,
    apply_biome_buildings, get_biome_category,
)
from game.world.terrain_checks import (
    SettlementTerrainChecker, classify_settlement_wards, apply_port_terrain_override)
from game.world.wall_generation import (
    generate_wall_polygon, generate_moat_points, find_wall_polygon_crossing,
    place_wall_towers)

WARD_SEEDS = {"hamlet": 5, "village": 12, "town": 25, "city": 45, "castle": 20}
WARD_CLASSES_BY_RING = {
    "inner":  ["market", "commercial", "tavern", "temple", "administrative"],
    "middle": ["residential", "craft", "craft_metal", "craft_cloth", "bakery", "storage"],
    "outer":  ["farming", "stable", "military", "storage"],
}
WARD_BUILDINGS = {
    "market": ["market_stall", "market_stall", "well"],
    "commercial": ["market_stall", "warehouse"], "tavern": ["tavern"],
    "temple": ["temple", "chapel"], "administrative": ["town_hall", "treasury"],
    "residential": ["house", "house", "cottage", "townhouse"],
    "craft": ["workshop", "workshop"], "craft_metal": ["blacksmith", "workshop"],
    "craft_cloth": ["weaver", "tanner"], "bakery": ["bakery"],
    "storage": ["warehouse", "granary"], "farming": ["barn", "granary"],
    "stable": ["stable"], "military": ["barracks", "armoury"],
    "keep": ["castle_keep"], "inner_bailey": ["great_hall", "chapel", "lord_chambers"],
    "outer_bailey": ["barracks", "stable", "blacksmith", "well"],
    "port": ["dock", "dock", "fish_market"], "gatehouse": ["gatehouse"],
}


class VoronoiSettlementLayout:
    """Generate settlement layout using Voronoi wards."""

    def __init__(self, name: str, kind: str, cx: int, cy: int,
                 radius: int, world_plan, rng: random.Random,
                 specialization: str = "general", race: str = "human"):
        self.name = name
        self.kind = kind
        self.cx = cx
        self.cy = cy
        self.radius = radius
        self.wp = world_plan
        self.rng = rng
        self.specialization = specialization
        self.race = race

        # Internal state
        self._seeds: List[Tuple[float, float]] = []
        self._ward_tiles: Dict[int, List[Tuple[int, int]]] = {}
        self._ward_types: Dict[int, str] = {}
        self._ward_adjacency: Set[Tuple[int, int]] = set()
        self._cached_roads: Optional[List[Tuple[int, int, int, int, str]]] = None
        self._streets = None
        self._terrain = SettlementTerrainChecker(cx, cy, radius, world_plan)

    def _is_buildable(self, x, y, w, h): return self._terrain.is_buildable(x, y, w, h)
    def _is_road_segment_passable(self, x1, y1, x2, y2): return self._terrain.is_road_segment_passable(x1, y1, x2, y2)
    def _detect_nearby_rivers(self): self._terrain.detect_nearby_rivers()

    @property
    def _nearby_river_points(self): return self._terrain.nearby_river_points
    @property
    def _river_direction(self): return self._terrain.river_direction

    def generate(self) -> SettlementLayout:
        """Generate the full settlement layout."""
        self._generate_seeds()
        self._assign_tiles_to_wards()
        self._lloyd_relaxation(iterations=3)
        self._detect_nearby_rivers()
        self._classify_wards()
        self._merge_specialization_buildings()
        buildings = self._place_buildings()
        roads = self._plan_roads()
        defenses = self._plan_defenses()
        farms = self._plan_farms()
        wells = self._plan_wells()
        zones = self._build_zone_dict()

        layout = SettlementLayout(
            buildings=buildings,
            roads=roads,
            defenses=defenses,
            farms=farms,
            zones=zones,
            well_positions=wells,
        )
        # Attach cleared radius for chunk generator to use
        layout.cleared_radius = self._compute_cleared_radius()
        return layout

    def _compute_cleared_radius(self) -> int:
        """Radius of cleared land around settlement. Elves don't clear."""
        if not get_race_config(self.race).get("clear_land", True):
            return 0  # e.g. elves live in forests without clearing
        scale = {"hamlet": 1.0, "village": 1.1, "town": 1.2,
                 "city": 1.3, "castle": 1.15}
        return int(self.radius * scale.get(self.kind, 1.1))

    def get_cleared_tiles(self, chunk_x: int, chunk_y: int,
                          chunk_w: int, chunk_h: int
                          ) -> List[Tuple[int, int]]:
        """Return tiles in the cleared area that overlap the given chunk."""
        cleared_r = getattr(self, '_cleared_radius_cache', None)
        if cleared_r is None:
            cleared_r = self._compute_cleared_radius()
            self._cleared_radius_cache = cleared_r
        r_sq = cleared_r * cleared_r
        tiles: List[Tuple[int, int]] = []
        x0 = max(chunk_x, self.cx - cleared_r)
        x1 = min(chunk_x + chunk_w, self.cx + cleared_r + 1)
        y0 = max(chunk_y, self.cy - cleared_r)
        y1 = min(chunk_y + chunk_h, self.cy + cleared_r + 1)
        for ty in range(y0, y1):
            dy = ty - self.cy
            for tx in range(x0, x1):
                dx = tx - self.cx
                if dx * dx + dy * dy <= r_sq:
                    tiles.append((tx, ty))
        return tiles

    def _generate_seeds(self):
        """Generate seed points in a golden-angle spiral."""
        golden_angle = math.pi * (3.0 - math.sqrt(5.0))
        n_seeds = WARD_SEEDS.get(self.kind, 12)

        seeds = []
        for i in range(n_seeds):
            if n_seeds <= 1:
                r = 0
            else:
                r = self.radius * math.sqrt(i / n_seeds) * 0.8
            theta = i * golden_angle
            sx = self.cx + r * math.cos(theta)
            sy = self.cy + r * math.sin(theta)
            seeds.append((sx, sy))

        self._seeds = seeds

    def _assign_tiles_to_wards(self):
        """Assign tiles within radius to nearest seed using numpy vectorization."""
        import numpy as np

        r = self.radius
        n_seeds = len(self._seeds)
        seed_arr = np.array(self._seeds, dtype=np.float32)
        step = 1 if r <= 30 else (2 if r <= 60 else 3)
        dy_range = np.arange(-r, r + 1, step, dtype=np.int32)
        dx_range = np.arange(-r, r + 1, step, dtype=np.int32)
        dy_grid, dx_grid = np.meshgrid(dy_range, dx_range, indexing='ij')

        # Filter to circle
        dist_sq = dx_grid * dx_grid + dy_grid * dy_grid
        mask = dist_sq <= r * r

        # World coordinates
        tx_all = self.cx + dx_grid[mask]
        ty_all = self.cy + dy_grid[mask]

        # Filter out-of-bounds
        valid = (tx_all >= 0) & (ty_all >= 0)
        tx_all = tx_all[valid]
        ty_all = ty_all[valid]

        # Filter water tiles (elevation < sea level)
        step_e = getattr(self.wp, '_elev_step', 10)
        elev_cache = getattr(self.wp, '_elev_cache', None)
        if elev_cache is not None:
            ci = np.clip(tx_all // step_e, 0, elev_cache.shape[1] - 1)
            cj = np.clip(ty_all // step_e, 0, elev_cache.shape[0] - 1)
            elevations = elev_cache[cj, ci]
            land_mask = elevations >= 0.23
            tx_all = tx_all[land_mask]
            ty_all = ty_all[land_mask]

        n_tiles = len(tx_all)

        if n_tiles == 0:
            self._ward_tiles = {i: [] for i in range(n_seeds)}
            self._ward_adjacency = set()
            self._assign_grid = {}
            return

        # Vectorized nearest-seed: compute distances to all seeds at once
        # tiles: (n_tiles, 2), seeds: (n_seeds, 2)
        tile_coords = np.column_stack([tx_all.astype(np.float32),
                                        ty_all.astype(np.float32)])
        # Batch in chunks to limit memory (for very large settlements)
        assignments = np.empty(n_tiles, dtype=np.int32)
        chunk_sz = 5000
        for ci in range(0, n_tiles, chunk_sz):
            end = min(ci + chunk_sz, n_tiles)
            chunk_tiles = tile_coords[ci:end]  # (chunk, 2)
            # Distances: (chunk, n_seeds)
            diffs = chunk_tiles[:, np.newaxis, :] - seed_arr[np.newaxis, :, :]
            dists = np.sum(diffs * diffs, axis=2)
            assignments[ci:end] = np.argmin(dists, axis=1)

        # Build ward_tiles dict and assign_grid
        ward_tiles: Dict[int, List[Tuple[int, int]]] = {
            i: [] for i in range(n_seeds)}
        assign_grid: Dict[Tuple[int, int], int] = {}

        for i in range(n_tiles):
            tx, ty, ward = int(tx_all[i]), int(ty_all[i]), int(assignments[i])
            # Fill step×step block from this sample
            for fy in range(step):
                for fx in range(step):
                    ftx, fty = tx + fx, ty + fy
                    ward_tiles[ward].append((ftx, fty))
                    assign_grid[(ftx, fty)] = ward

        # Detect adjacency and boundary tiles (sample tiles)
        adjacency: Set[Tuple[int, int]] = set()
        ward_boundary: Dict[int, Set[Tuple[int, int]]] = {
            i: set() for i in range(n_seeds)}
        sample_step = max(1, n_tiles // 500)
        for i in range(0, n_tiles, sample_step):
            tx, ty = int(tx_all[i]), int(ty_all[i])
            ward_id = int(assignments[i])
            for ndx, ndy in ((step, 0), (0, step)):
                nkey = (tx + ndx, ty + ndy)
                other = assign_grid.get(nkey)
                if other is not None and other != ward_id:
                    pair = (min(ward_id, other), max(ward_id, other))
                    adjacency.add(pair)
                    ward_boundary[ward_id].add((tx, ty))

        self._ward_tiles = ward_tiles
        self._ward_adjacency = adjacency
        self._assign_grid = assign_grid
        self._ward_boundary = ward_boundary

    def _lloyd_relaxation(self, iterations: int = 3):
        """Move seeds to ward centroids and reassign tiles."""
        import numpy as np
        # Fewer iterations for large settlements (performance)
        if self.radius > 80:
            iterations = min(iterations, 1)
        elif self.radius > 50:
            iterations = min(iterations, 2)
        for _ in range(iterations):
            # Compute centroids using numpy for speed
            new_seeds = []
            for si in range(len(self._seeds)):
                tiles = self._ward_tiles.get(si, [])
                if not tiles:
                    new_seeds.append(self._seeds[si])
                    continue
                arr = np.array(tiles, dtype=np.float32)
                new_seeds.append((float(arr[:, 0].mean()),
                                  float(arr[:, 1].mean())))

            self._seeds = new_seeds
            self._assign_tiles_to_wards()

    def _classify_wards(self):
        """Classify wards based on distance from center and terrain."""
        ward_dists = {}
        for si, (sx, sy) in enumerate(self._seeds):
            ward_dists[si] = math.sqrt(
                (sx - self.cx)**2 + (sy - self.cy)**2)
        sorted_wards = sorted(ward_dists.keys(),
                              key=lambda w: ward_dists[w])
        n_wards = len(sorted_wards)
        if n_wards == 0:
            return
        inner_cutoff = max(1, n_wards // 3)
        middle_cutoff = max(2, 2 * n_wards // 3)
        ward_types: Dict[int, str] = {}

        if self.kind == "castle":
            self._classify_castle_wards(sorted_wards, ward_dists,
                                        ward_types)
        else:
            self._classify_settlement_wards(sorted_wards, ward_dists,
                                            ward_types, inner_cutoff,
                                            middle_cutoff)

        # Special overrides based on terrain
        self._apply_terrain_overrides(ward_types, ward_dists)

        self._ward_types = ward_types

    def _classify_castle_wards(self, sorted_wards, ward_dists, ward_types):
        if sorted_wards: ward_types[sorted_wards[0]] = "keep"
        n = len(sorted_wards)
        for i, w in enumerate(sorted_wards):
            if i == 0: continue
            ward_types[w] = "inner_bailey" if i <= n // 3 else ("outer_bailey" if i <= 2 * n // 3 else "gatehouse")

    def _classify_settlement_wards(self, sorted_wards, ward_dists,
                                   ward_types, inner_cutoff, middle_cutoff):
        classify_settlement_wards(
            sorted_wards, ward_types, inner_cutoff, middle_cutoff,
            self.kind, self.specialization, self._terrain,
            self._seeds, self._ward_tiles,
            {k: list(v) for k, v in WARD_CLASSES_BY_RING.items()}, self.rng)

    def _apply_terrain_overrides(self, ward_types, ward_dists):
        apply_port_terrain_override(ward_types, ward_dists, self.specialization,
                                    self._seeds, self._terrain)

    def _merge_specialization_buildings(self) -> None:
        if self.specialization == "general" and not self._nearby_river_points:
            return
        merged = get_settlement_buildings(self.specialization, self.kind,
                                          self._ward_types, WARD_BUILDINGS)
        s = {"hamlet": 0.5, "village": 0.8, "town": 1.2, "city": 1.5, "castle": 1.0}.get(self.kind, 1.0)
        for wid, base in merged.items():
            c = max(1, int(len(base) * s))
            merged[wid] = [base[i % len(base)] for i in range(c)]
        self._merged_ward_buildings = merged

    def _place_buildings(self) -> List[PlannedBuilding]:
        """Place buildings in street-frontage lots, typed by ward."""
        from game.world.street_layout import StreetPlanner
        from game.world.road_utils import compute_building_setback

        planner = StreetPlanner()
        streets = self._streets
        if not streets:
            streets = planner.plan_streets(
                self.cx, self.cy, self.radius, self.kind,
                self.rng, self.wp)
            self._streets = streets

        lots = planner.plan_building_lots(
            streets, self.cx, self.cy, self.radius,
            self.rng, self.wp, kind=self.kind)

        # Cap building count by settlement type for realistic density
        max_bldgs = {"hamlet": 8, "village": 22, "town": 70,
                     "city": 250, "castle": 40}.get(self.kind, 30)
        buildings: List[PlannedBuilding] = []
        ward_counters: Dict[str, int] = {}

        for lot in lots:
            if len(buildings) >= max_bldgs:
                break
            ward_type = self._ward_at(
                lot.x + lot.w // 2, lot.y + lot.h // 2)
            bld_kinds = self._get_ward_buildings(ward_type)
            if not bld_kinds:
                continue
            idx = ward_counters.get(ward_type, 0)
            ward_counters[ward_type] = idx + 1
            bkind = bld_kinds[idx % len(bld_kinds)]

            bw, bh = min(lot.w, 8), min(lot.h, 8)
            if bw < 3 or bh < 3:
                continue
            bx, by = compute_building_setback(
                lot.x, lot.y, lot.w, lot.h,
                bw, bh, lot.road_direction)
            buildings.append(PlannedBuilding(
                name=bkind, kind=bkind, x=bx, y=by,
                w=bw, h=bh, zone=ward_type,
                blueprint_name=bkind))
        return buildings

    def _ward_at(self, x: int, y: int) -> str:
        """Return the ward type at a given tile position."""
        ward_id = getattr(self, '_assign_grid', {}).get((x, y))
        if ward_id is not None:
            return self._ward_types.get(ward_id, "residential")
        best_id, best_d = 0, float('inf')
        for si, (sx, sy) in enumerate(self._seeds):
            d = (sx - x) ** 2 + (sy - y) ** 2
            if d < best_d:
                best_d = d
                best_id = si
        return self._ward_types.get(best_id, "residential")

    def _get_biome_category(self) -> str:
        """Determine biome category at settlement center for building styles."""
        if hasattr(self, '_biome_category_cache'):
            return self._biome_category_cache
        # Sample terrain at center using the low-res elevation/moisture
        wp = self.wp
        if wp and hasattr(wp, 'get_elevation_fast'):
            import numpy as np
            from game.world.terrain_gen import (
                compute_moisture, whittaker_biome, _fbm,
            )
            from game.world.regional_climate import apply_regional_climate
            cx_arr = np.array([self.cx], dtype=np.float32)
            cy_arr = np.array([self.cy], dtype=np.float32)
            elev = np.array([wp.get_elevation_fast(self.cx, self.cy)],
                            dtype=np.float32)
            moist = compute_moisture(cx_arr, cy_arr, elev, wp.seed,
                                     wp.width, wp.height)
            moist, temp_mod = apply_regional_climate(
                cx_arr, cy_arr, moist, elev, wp.width, wp.height, wp.seed)
            biome_tile = whittaker_biome(elev, moist, temp_modifier=temp_mod)
            self._biome_category_cache = get_biome_category(int(biome_tile[0]))
        else:
            self._biome_category_cache = "default"
        return self._biome_category_cache

    def _get_ward_buildings(self, ward_type: str) -> List[str]:
        """Get building kinds for a ward type, with race and biome replacements."""
        if hasattr(self, '_merged_ward_buildings'):
            for wid, wt in self._ward_types.items():
                if wt == ward_type and wid in self._merged_ward_buildings:
                    result = apply_race_buildings(
                        self._merged_ward_buildings[wid], self.race)
                    return apply_biome_buildings(
                        result, self._get_biome_category())
        base = WARD_BUILDINGS.get(ward_type, ["house"])
        s = {"hamlet": 0.5, "village": 0.8, "town": 1.2,
             "city": 1.5, "castle": 1.0}.get(self.kind, 1.0)
        count = max(1, int(len(base) * s))
        result = [base[i % len(base)] for i in range(count)]
        result = apply_race_buildings(result, self.race)
        return apply_biome_buildings(result, self._get_biome_category())

    def _plan_roads(self) -> List[Tuple[int, int, int, int, str]]:
        """Generate roads using the coherent StreetPlanner (cached)."""
        if self._cached_roads is not None:
            return self._cached_roads

        from game.world.street_layout import StreetPlanner
        planner = StreetPlanner()
        streets = self._streets
        if not streets:
            streets = planner.plan_streets(
                self.cx, self.cy, self.radius, self.kind,
                self.rng, self.wp)
            self._streets = streets

        roads = []
        for street in streets:
            for x1, y1, x2, y2 in street.segments:
                roads.append((x1, y1, x2, y2, street.road_type))

        self._cached_roads = roads
        return roads

    def _plan_defenses(self) -> Optional[DefensePlan]:
        """Plan terrain-aware walls with gates on main roads.

        Walls follow terrain contours: pushed outward on ridges,
        retracted or omitted near water (natural defense). The
        polygon is smoothed for an organic medieval feel.
        """
        # Race check — some races don't build walls
        race_cfg = get_race_config(self.race)
        if race_cfg.get("wall_type") is None:
            return None  # e.g. elves use natural concealment
        if self.kind not in ("town", "city", "castle"):
            if self.specialization != "border":
                return None

        # Wall covers inner ~55% of settlement (core wards only)
        wall_r = int(self.radius * 0.55)
        n_sample = max(16, min(24, wall_r // 2))
        defense = DefensePlan(wall_radius=wall_r)

        # 1. Generate terrain-aware wall polygon
        defense.wall_points = generate_wall_polygon(
            self.cx, self.cy, self.radius, wall_r,
            self.wp, self.rng, n_points=n_sample)

        # 2. Place gates where main streets cross the wall polygon
        streets = self._streets or []
        gate_dirs_used: Set[str] = set()
        for street in streets:
            if street.road_type not in ("cobblestone", "main"):
                continue
            for x1, y1, x2, y2 in street.segments:
                gx, gy, gdir = find_wall_polygon_crossing(
                    x1, y1, x2, y2,
                    defense.wall_points, self.cx, self.cy)
                if gdir and gdir not in gate_dirs_used:
                    defense.gate_positions.append((gx, gy, gdir))
                    gate_dirs_used.add(gdir)

        # Ensure at least 2 gates on opposite sides
        if len(defense.gate_positions) < 2:
            for direction, ddx, ddy in [("north", 0, -1), ("south", 0, 1),
                                         ("east", 1, 0), ("west", -1, 0)]:
                if direction not in gate_dirs_used:
                    target_x = self.cx + ddx * wall_r
                    target_y = self.cy + ddy * wall_r
                    best_pt = min(
                        defense.wall_points,
                        key=lambda p: (p[0] - target_x) ** 2
                                      + (p[1] - target_y) ** 2)
                    defense.gate_positions.append(
                        (best_pt[0], best_pt[1], direction))
                    gate_dirs_used.add(direction)
                    if len(defense.gate_positions) >= 2:
                        break

        # 3. Place towers at corners and regular intervals
        defense.tower_positions = place_wall_towers(
            defense.wall_points, defense.gate_positions,
            min_spacing=30)

        # 4. Moat for cities/castles (skip where water already exists)
        if self.kind in ("city", "castle"):
            defense.has_moat = True
            defense.moat_points = generate_moat_points(
                defense.wall_points, self.cx, self.cy,
                self.wp, moat_offset=4)

        return defense

    def _plan_farms(self) -> List[Tuple[int, int, int]]:
        """Plan farm clusters. Races that don't farm get none."""
        race_cfg = get_race_config(self.race)
        if race_cfg.get("farm_type") is None:
            return []  # dwarves mine, orcs raid — no farms
        farms = []
        fr = max(5, self.radius // 6)
        for wid, wt in self._ward_types.items():
            if wt != "farming":
                continue
            tiles = self._ward_tiles.get(wid, [])
            if not tiles:
                continue
            cx = sum(t[0] for t in tiles) // len(tiles)
            cy = sum(t[1] for t in tiles) // len(tiles)
            elev = self.wp.get_elevation_fast(cx, cy)
            if elev < 0.25 or elev > 0.55:
                continue
            farms.append((cx, cy, fr))
        if self.kind in ("town", "city"):
            n_extra = 2 if self.kind == "town" else 4
            for i in range(n_extra):
                base_a = 2 * math.pi * i / n_extra
                for attempt in range(5):
                    a = base_a + self.rng.uniform(-0.3, 0.3)
                    if attempt > 0:
                        a += self.rng.uniform(-1.0, 1.0)
                    d = self.radius * self.rng.uniform(0.7, 0.95)
                    fx = int(self.cx + d * math.cos(a))
                    fy = int(self.cy + d * math.sin(a))
                    elev = self.wp.get_elevation_fast(fx, fy)
                    if 0.25 <= elev <= 0.55:
                        farms.append((fx, fy, fr))
                        break
        return farms

    def _plan_wells(self) -> List[Tuple[int, int]]:
        """Plan well positions in market and residential wards."""
        targets = {"market"}
        if self.kind in ("town", "city"):
            targets.add("residential")
        wells = []
        for wid, wt in self._ward_types.items():
            if wt in targets:
                tiles = self._ward_tiles.get(wid, [])
                if tiles:
                    wells.append((sum(t[0] for t in tiles) // len(tiles),
                                  sum(t[1] for t in tiles) // len(tiles)))
        return wells

    def _build_zone_dict(self) -> Dict[str, Tuple[int, int, int, int]]:
        """Build zone bounding boxes for SettlementLayout compatibility."""
        zones: Dict[str, Tuple[int, int, int, int]] = {}
        for wid, wt in self._ward_types.items():
            tiles = self._ward_tiles.get(wid, [])
            if not tiles:
                continue
            x0 = min(t[0] for t in tiles)
            x1 = max(t[0] for t in tiles)
            y0 = min(t[1] for t in tiles)
            y1 = max(t[1] for t in tiles)
            if wt in zones:
                ox, oy, ow, oh = zones[wt]
                x0, y0 = min(x0, ox), min(y0, oy)
                x1, y1 = max(x1, ox + ow), max(y1, oy + oh)
            zones[wt] = (x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        # Add a "cleared" zone representing the entire cleared area
        cleared_r = self._compute_cleared_radius()
        zones["cleared"] = (
            self.cx - cleared_r, self.cy - cleared_r,
            cleared_r * 2, cleared_r * 2)
        return zones
