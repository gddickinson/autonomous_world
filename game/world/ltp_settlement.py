"""LTP Settlement Placer — Landscape-Transport-Population model.

Emergent terrain-driven settlement placement via iterative
transport-connectivity reinforcement (simplified PageRank).
"""

import math
import random
from typing import List, Tuple, Dict, Optional

from game.world.world_plan import SettlementPlan, RoadPlan


def _elevation_cost(elev: float) -> float:
    """Transport cost multiplier based on elevation."""
    if elev < 0.23:
        return 0.5   # water/river route — cheap via boat
    if elev < 0.30:
        return 0.8   # coastal/sandy — easy terrain
    if elev < 0.50:
        return 1.0   # grassland/forest — baseline
    if elev < 0.60:
        return 2.0   # hills — moderate cost
    if elev < 0.70:
        return 5.0   # mountains — expensive
    return 10.0       # high mountains — very expensive


def _edge_transport_cost(elev_a, elev_b, distance):
    """Transport cost for an edge between two nodes."""
    avg_cost = (_elevation_cost(elev_a) + _elevation_cost(elev_b)) * 0.5
    slope_penalty = 1.0 + abs(elev_a - elev_b) * 5.0
    return distance * avg_cost * slope_penalty


class LTPSettlementPlacer:
    """LTP model for emergent settlement placement from terrain."""

    def __init__(self, world_plan, rng: random.Random):
        self.wp = world_plan
        self.rng = rng
        self.width = world_plan.width
        self.height = world_plan.height

        # Results
        self._settlements: List[SettlementPlan] = []
        self._trade_routes: List[RoadPlan] = []

        # LTP grid data (populated during generate)
        self._node_positions: List[Tuple[int, int]] = []
        self._node_elevations: List[float] = []
        self._populations = None  # numpy array
        self._connectivity = None  # dict of edge weights

    def generate(self) -> List[SettlementPlan]:
        """Run the full LTP pipeline and return settlement plans."""
        self._build_candidate_grid()
        self._build_transport_edges()
        self._initialize_populations()
        self._run_ltp_iteration()
        self._select_settlements()
        self._nudge_from_water()
        self._extract_trade_routes()
        return self._settlements

    def get_trade_routes(self) -> List[RoadPlan]:
        """Return trade routes extracted from LTP connectivity."""
        return self._trade_routes

    def _build_candidate_grid(self):
        """Sample candidate locations every ~50 tiles, filtering water/mountains."""
        step = 50
        nodes = []
        elevations = []

        for gy in range(step // 2, self.height, step):
            for gx in range(step // 2, self.width, step):
                # Skip edges of the world
                if gx < 100 or gx > self.width - 100:
                    continue
                if gy < 100 or gy > self.height - 100:
                    continue

                elev = self.wp.get_elevation_fast(gx, gy)

                # Filter out water and mountain peaks
                if elev < 0.23 or elev > 0.65:
                    continue

                # Skip test island area
                if self.wp.test_island_rect:
                    rx, ry, rw, rh = self.wp.test_island_rect
                    if rx <= gx <= rx + rw and ry <= gy <= ry + rh:
                        continue

                nodes.append((gx, gy))
                elevations.append(elev)

        self._node_positions = nodes
        self._node_elevations = elevations

    def _build_transport_edges(self):
        """Build sparse adjacency of transport costs between ~8 nearest neighbors."""
        import numpy as np

        positions = np.array(self._node_positions, dtype=np.float32)
        n = len(positions)

        if n == 0:
            self._edges = []
            self._neighbors = [[] for _ in range(n)]
            return

        max_dist = 150.0
        max_neighbors = 8

        # Build neighbor lists using a grid-based spatial index
        cell_size = int(max_dist)
        grid: Dict[Tuple[int, int], List[int]] = {}
        for i, (x, y) in enumerate(self._node_positions):
            key = (int(x) // cell_size, int(y) // cell_size)
            grid.setdefault(key, []).append(i)

        edges = []  # (i, j, cost)
        neighbors = [[] for _ in range(n)]

        for i in range(n):
            xi, yi = self._node_positions[i]
            ei = self._node_elevations[i]
            ci, cj_key = int(xi) // cell_size, int(yi) // cell_size

            # Check neighboring cells
            candidates = []
            for di in range(-1, 2):
                for dj in range(-1, 2):
                    cell_key = (ci + di, cj_key + dj)
                    if cell_key in grid:
                        for j in grid[cell_key]:
                            if j <= i:
                                continue
                            xj, yj = self._node_positions[j]
                            dist = math.sqrt((xi - xj)**2 + (yi - yj)**2)
                            if dist <= max_dist:
                                candidates.append((j, dist))

            # Keep at most max_neighbors closest
            candidates.sort(key=lambda c: c[1])
            for j, dist in candidates[:max_neighbors]:
                ej = self._node_elevations[j]
                cost = _edge_transport_cost(ei, ej, dist)
                edge_idx = len(edges)
                edges.append((i, j, cost))
                neighbors[i].append((j, edge_idx))
                neighbors[j].append((i, edge_idx))

        self._edges = edges
        self._neighbors = neighbors

    def _initialize_populations(self):
        """Initialize populations with noise; boost near ruins and rivers."""
        import numpy as np

        n = len(self._node_positions)
        if n == 0:
            self._populations = np.array([], dtype=np.float64)
            return

        # Near-uniform with noise
        pops = np.ones(n, dtype=np.float64)
        noise = np.array([self.rng.uniform(-0.1, 0.1) for _ in range(n)])
        pops += noise

        # Boost nodes near ruin/special locations (historical seeding)
        for loc in self.wp.special_locations:
            if loc.kind in ("ruins", "temple", "shrine"):
                for i, (nx, ny) in enumerate(self._node_positions):
                    dist = math.sqrt((nx - loc.x)**2 + (ny - loc.y)**2)
                    if dist < 200:
                        pops[i] += 2.0 * max(0, 1.0 - dist / 200.0)

        # Boost nodes near rivers (water access advantage)
        for river in self.wp.rivers:
            for px, py in river.points[::5]:  # sample every 5th point
                for i, (nx, ny) in enumerate(self._node_positions):
                    dist = math.sqrt((nx - px)**2 + (ny - py)**2)
                    if dist < 100:
                        pops[i] += 0.5 * max(0, 1.0 - dist / 100.0)

        # Normalize
        total = pops.sum()
        if total > 0:
            pops /= total

        self._populations = pops

    def _run_ltp_iteration(self, steps: int = 50):
        """Run LTP transport-connectivity reinforcement (PageRank-like)."""
        import numpy as np

        n = len(self._node_positions)
        if n == 0:
            return

        x = self._populations.copy()
        num_edges = len(self._edges)

        # Edge weights (connectivity)
        w = np.ones(num_edges, dtype=np.float64) * 0.01

        # Parameters
        epsilon = 0.01
        d = 0.8
        R = 100.0  # characteristic transport distance

        for step_i in range(steps):
            # --- Update edge weights ---
            for e_idx, (i, j, base_cost) in enumerate(self._edges):
                r_ij = base_cost / R
                decay = math.exp(-r_ij) if r_ij < 20 else 0.0
                w[e_idx] += epsilon * (x[i] * x[j] - decay * w[e_idx])
                if w[e_idx] < 0:
                    w[e_idx] = 0.0

            # --- Update populations ---
            new_x = np.zeros(n, dtype=np.float64)
            for i in range(n):
                nbrs = self._neighbors[i]
                if not nbrs:
                    new_x[i] = x[i]
                    continue

                w_sum = 0.0
                inflow = 0.0
                for j, e_idx in nbrs:
                    we = w[e_idx]
                    w_sum += we
                    inflow += we * x[j]

                if w_sum > 1e-12:
                    inflow /= w_sum
                else:
                    inflow = x[i]

                uniform = 1.0 / n
                new_x[i] = x[i] + d * (inflow - x[i]) + (1 - d) * (
                    uniform - x[i])
                if new_x[i] < 0.001 / n:
                    new_x[i] = 0.001 / n

            # Normalize
            total = new_x.sum()
            if total > 0:
                new_x /= total
            x = new_x

        self._populations = x
        self._edge_weights = w

    def _select_settlements(self):
        """Pick top-population nodes as settlements with distance constraints."""
        import numpy as np

        n = len(self._node_positions)
        if n == 0:
            return

        # Sort nodes by population descending
        sorted_indices = np.argsort(-self._populations)

        # Quotas — medieval-realistic: many hamlets, few cities
        # For a 10k x 10k world (base=25): ~3 cities, ~10 towns, ~30 villages, ~80 hamlets
        area = self.width * self.height
        base = area / (2000 * 2000)
        sqrt_base = math.sqrt(base)

        quotas = {
            "city":    max(2, int(0.6 * sqrt_base + 1)),
            "town":    max(4, int(2.0 * sqrt_base + 3)),
            "village": max(10, int(6.0 * sqrt_base + 5)),
            "hamlet":  max(25, int(16.0 * sqrt_base + 5)),
        }

        min_dist = {
            "city":    max(2000, int(500 * sqrt_base)),
            "town":    max(1000, int(250 * sqrt_base)),
            "village": max(500, int(120 * sqrt_base)),
            "hamlet":  max(300, int(70 * sqrt_base)),
        }

        radii = {
            "hamlet":  max(20, int(20 * sqrt_base)),
            "village": max(40, int(40 * sqrt_base)),
            "town":    max(70, int(70 * sqrt_base)),
            "city":    max(120, int(120 * sqrt_base)),
        }

        pop_counts = {
            "hamlet":  (5, 15),
            "village": (15, 40),
            "town":    (40, 100),
            "city":    (100, 250),
        }

        placed: List[Tuple[int, int, str]] = []
        counts = {"city": 0, "town": 0, "village": 0, "hamlet": 0}

        # Place each type in priority order (cities first, then towns, etc.)
        # so that distance-skipped candidates don't consume slots for
        # smaller settlement types.
        used_indices = set()

        for kind in ["city", "town", "village", "hamlet"]:
            quota = quotas[kind]
            for idx in sorted_indices:
                if counts[kind] >= quota:
                    break
                if int(idx) in used_indices:
                    continue

                sx, sy = self._node_positions[idx]

                # Distance check against already-placed settlements
                md = min_dist[kind]
                too_close = any(
                    math.sqrt((px - sx)**2 + (py - sy)**2) < md
                    for px, py, pk in placed
                )
                if too_close:
                    continue

                # Skip test island
                if self.wp.test_island_rect:
                    rx, ry, rw, rh = self.wp.test_island_rect
                    if rx <= sx <= rx + rw and ry <= sy <= ry + rh:
                        continue

                # Find which region this belongs to
                best_region = None
                best_rdist = float('inf')
                for region in self.wp.regions:
                    rd = math.sqrt((region.center_x - sx)**2 +
                                   (region.center_y - sy)**2)
                    if rd < best_rdist:
                        best_rdist = rd
                        best_region = region

                if best_region is None:
                    continue

                used_indices.add(int(idx))

                region_data = best_region.data
                race = self.rng.choice(
                    region_data.get("primary_races", ["Human"]))
                names = region_data.get("settlement_names", ["Settlement"])
                name = self.rng.choice(names) if names else f"{kind.title()}"

                # Avoid duplicate names
                existing = {s.name for s in self._settlements}
                if name in existing:
                    suffix = self.rng.choice([
                        'East', 'West', 'North', 'South',
                        'New', 'Old', 'Upper', 'Lower'])
                    name = f"{name} {suffix}"

                pop_lo, pop_hi = pop_counts[kind]
                pop = self.rng.randint(pop_lo, pop_hi)
                radius = radii[kind]

                sp = SettlementPlan(
                    name=name, kind=kind, x=sx, y=sy,
                    radius=radius, region=best_region.name,
                    race=race, population=pop,
                )

                # Determine specialization
                spec, terrain_ctx = self.wp._determine_specialization(
                    sx, sy, kind, self.rng)
                sp.specialization = spec
                sp.terrain_context = terrain_ctx

                self._settlements.append(sp)
                placed.append((sx, sy, kind))
                counts[kind] += 1

    def _nudge_from_water(self):
        """Push settlement centres away from nearby water edges.

        If any sample point within radius*0.3 of the centre is water
        (elev < 0.23), nudge the centre inland to avoid buildings on water.
        """
        water_elev = 0.23
        n_samples = 8
        for sp in self._settlements:
            check_dist = max(10, int(sp.radius * 0.3))
            for _attempt in range(5):
                water_dx, water_dy = 0.0, 0.0
                water_count = 0
                for i in range(n_samples):
                    angle = 2 * math.pi * i / n_samples
                    sx = int(sp.x + check_dist * math.cos(angle))
                    sy = int(sp.y + check_dist * math.sin(angle))
                    if self.wp.get_elevation_fast(sx, sy) < water_elev:
                        water_dx += math.cos(angle)
                        water_dy += math.sin(angle)
                        water_count += 1
                if self.wp.get_elevation_fast(sp.x, sp.y) < water_elev:
                    water_count += n_samples
                if water_count == 0:
                    break
                mag = math.sqrt(water_dx ** 2 + water_dy ** 2)
                nudge = max(5, check_dist // 2)
                if mag > 0.01:
                    sp.x = int(sp.x - (water_dx / mag) * nudge)
                    sp.y = int(sp.y - (water_dy / mag) * nudge)
                else:
                    # Water all around — nudge toward highest neighbor
                    best_e, best_dx, best_dy = -1.0, 0, 0
                    for i in range(n_samples):
                        angle = 2 * math.pi * i / n_samples
                        sx = int(sp.x + check_dist * math.cos(angle))
                        sy = int(sp.y + check_dist * math.sin(angle))
                        e = self.wp.get_elevation_fast(sx, sy)
                        if e > best_e:
                            best_e = e
                            best_dx = sx - sp.x
                            best_dy = sy - sp.y
                    if best_e >= water_elev:
                        sp.x += best_dx
                        sp.y += best_dy
                    else:
                        break
                margin = sp.radius + 20
                sp.x = max(margin, min(self.width - margin, sp.x))
                sp.y = max(margin, min(self.height - margin, sp.y))

    def _extract_trade_routes(self):
        """Convert high-connectivity edges into the road network."""
        import numpy as np

        if not hasattr(self, '_edge_weights') or len(self._edges) == 0:
            # Fallback: use MST road planning from WorldPlan
            return

        # Sort edges by weight descending
        w = self._edge_weights
        sorted_edge_indices = np.argsort(-w)

        num_edges = len(self._edges)
        top_20_cutoff = int(num_edges * 0.20)
        top_50_cutoff = int(num_edges * 0.50)

        # Build settlement lookup for quick nearest-settlement checks
        sett_positions = [(s.x, s.y, s.name, s.kind)
                          for s in self._settlements]

        def nearest_settlement(x, y, max_dist=300):
            best = None
            best_d = max_dist
            for sx, sy, sname, skind in sett_positions:
                d = math.sqrt((sx - x)**2 + (sy - y)**2)
                if d < best_d:
                    best_d = d
                    best = sname
            return best

        roads_created = set()

        for rank, e_idx in enumerate(sorted_edge_indices):
            if rank >= top_50_cutoff:
                break

            i, j, base_cost = self._edges[e_idx]
            if w[e_idx] < 1e-8:
                continue

            x1, y1 = self._node_positions[i]
            x2, y2 = self._node_positions[j]

            # Find nearest settlements to each endpoint
            s1 = nearest_settlement(x1, y1)
            s2 = nearest_settlement(x2, y2)

            if s1 is None or s2 is None or s1 == s2:
                continue

            road_key = tuple(sorted([s1, s2]))
            if road_key in roads_created:
                continue
            roads_created.add(road_key)

            # Determine road type
            if rank < top_20_cutoff:
                # Check settlement importance for main roads
                kind1 = next((s.kind for s in self._settlements
                              if s.name == s1), "hamlet")
                kind2 = next((s.kind for s in self._settlements
                              if s.name == s2), "hamlet")
                imp = {"city": 4, "town": 3, "village": 2, "hamlet": 1}
                max_imp = max(imp.get(kind1, 1), imp.get(kind2, 1))
                road_type = {4: "king_road", 3: "paved_road",
                             2: "gravel_road", 1: "dirt_track"}[max_imp]
            else:
                road_type = "dirt_track"

            # Generate terrain-aware waypoints via A* pathfinding
            from game.world.road_pathfinder import find_road_path
            pos1 = self._get_settlement_pos(s1)
            pos2 = self._get_settlement_pos(s2)
            waypoints = find_road_path(self.wp, pos1[0], pos1[1],
                                       pos2[0], pos2[1])

            self._trade_routes.append(RoadPlan(
                start_name=s1, end_name=s2,
                road_type=road_type, waypoints=waypoints,
            ))

    def _get_settlement_pos(self, name: str) -> Tuple[int, int]:
        """Get settlement position by name."""
        for s in self._settlements:
            if s.name == name:
                return (s.x, s.y)
        return (self.width // 2, self.height // 2)
