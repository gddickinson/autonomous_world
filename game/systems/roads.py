"""
Road Network System -- manages road types, quality, routing, and maintenance.

Road types connect settlements of different importance:
- DIRT_TRACK: hamlet <-> hamlet
- GRAVEL_ROAD: hamlet <-> village
- PAVED_ROAD: village <-> town
- KING_ROAD: town <-> city, city <-> city
- MOUNTAIN_PASS: through mountains

Road quality degrades over time and affects travel speed.
NPC road-maintenance workers repair roads.
Roadside inns are placed along long routes.
"""

import math
import heapq
import random
from enum import IntEnum
from typing import Dict, List, Optional, Tuple


# ================================================================
# ROAD TYPES
# ================================================================

class RoadType(IntEnum):
    DIRT_TRACK = 0
    GRAVEL_ROAD = 1
    PAVED_ROAD = 2
    KING_ROAD = 3
    MOUNTAIN_PASS = 4


# Travel speed multiplier per road type (lower = faster)
ROAD_SPEED_COST = {
    RoadType.DIRT_TRACK: 0.85,
    RoadType.GRAVEL_ROAD: 0.75,
    RoadType.PAVED_ROAD: 0.65,
    RoadType.KING_ROAD: 0.55,
    RoadType.MOUNTAIN_PASS: 1.2,
}

# Settlement importance for determining road types between them
SETTLEMENT_IMPORTANCE = {
    "hamlet": 0,
    "village": 1,
    "town": 2,
    "city": 3,
    "castle": 3,
}

# How many extra connections each settlement type gets beyond MST
EXTRA_CONNECTIONS = {
    "hamlet": 0,
    "village": 1,
    "town": 2,
    "city": 3,
    "castle": 2,
}


def _road_type_for_pair(kind_a: str, kind_b: str) -> RoadType:
    """Determine road type based on the two settlements it connects."""
    imp_a = SETTLEMENT_IMPORTANCE.get(kind_a, 0)
    imp_b = SETTLEMENT_IMPORTANCE.get(kind_b, 0)
    max_imp = max(imp_a, imp_b)
    min_imp = min(imp_a, imp_b)

    if max_imp >= 3 and min_imp >= 2:
        return RoadType.KING_ROAD
    if max_imp >= 3 and min_imp >= 1:
        return RoadType.KING_ROAD
    if max_imp >= 2 and min_imp >= 1:
        return RoadType.PAVED_ROAD
    if max_imp >= 1 and min_imp >= 0:
        return RoadType.GRAVEL_ROAD
    return RoadType.DIRT_TRACK


# ================================================================
# ROAD SEGMENT
# ================================================================

class RoadSegment:
    """A single road connection between two settlements."""
    __slots__ = ('settlement_a', 'settlement_b', 'road_type', 'distance',
                 'waypoints', 'condition', 'last_maintenance_time')

    def __init__(self, settlement_a: str, settlement_b: str,
                 road_type: RoadType, distance: float,
                 waypoints: List[Tuple[int, int]]):
        self.settlement_a = settlement_a
        self.settlement_b = settlement_b
        self.road_type = road_type
        self.distance = distance
        self.waypoints = waypoints  # tile positions along the road
        self.condition = 1.0  # 0.0 = destroyed, 1.0 = perfect
        self.last_maintenance_time = 0.0

    def effective_speed_cost(self) -> float:
        """Speed cost considering road type and condition."""
        base = ROAD_SPEED_COST[self.road_type]
        # Poor condition increases cost by up to 80%
        condition_penalty = 1.0 + (1.0 - self.condition) * 0.8
        return base * condition_penalty

    def degrade(self, dt: float, traffic_factor: float = 1.0):
        """Degrade road condition over time. Higher traffic = faster degradation."""
        # King roads degrade slower, dirt tracks degrade faster
        degrade_rate = {
            RoadType.DIRT_TRACK: 0.0005,
            RoadType.GRAVEL_ROAD: 0.0003,
            RoadType.PAVED_ROAD: 0.0002,
            RoadType.KING_ROAD: 0.0001,
            RoadType.MOUNTAIN_PASS: 0.0004,
        }
        rate = degrade_rate.get(self.road_type, 0.0003)
        self.condition = max(0.0, self.condition - rate * dt * traffic_factor)

    def repair(self, amount: float):
        """Repair road condition."""
        self.condition = min(1.0, self.condition + amount)


# ================================================================
# ROAD NETWORK
# ================================================================

class RoadNetwork:
    """Manages all road segments between settlements and provides routing."""

    def __init__(self):
        self.segments: List[RoadSegment] = []
        # Adjacency map: settlement_name -> [(neighbor_name, segment_index)]
        self._adjacency: Dict[str, List[Tuple[str, int]]] = {}
        # Quick lookup: (name_a, name_b) -> segment_index (sorted key)
        self._segment_lookup: Dict[Tuple[str, str], int] = {}

    def _key(self, a: str, b: str) -> Tuple[str, str]:
        return (min(a, b), max(a, b))

    def add_segment(self, segment: RoadSegment):
        """Add a road segment to the network."""
        idx = len(self.segments)
        self.segments.append(segment)

        key = self._key(segment.settlement_a, segment.settlement_b)
        self._segment_lookup[key] = idx

        if segment.settlement_a not in self._adjacency:
            self._adjacency[segment.settlement_a] = []
        self._adjacency[segment.settlement_a].append(
            (segment.settlement_b, idx))

        if segment.settlement_b not in self._adjacency:
            self._adjacency[segment.settlement_b] = []
        self._adjacency[segment.settlement_b].append(
            (segment.settlement_a, idx))

    def get_road_between(self, a: str, b: str) -> Optional[RoadSegment]:
        """Get the road segment connecting two settlements, if any."""
        key = self._key(a, b)
        idx = self._segment_lookup.get(key)
        if idx is not None:
            return self.segments[idx]
        return None

    def get_route(self, from_settlement: str,
                  to_settlement: str) -> Optional[List[str]]:
        """Find the shortest route (list of settlement names) using Dijkstra."""
        if from_settlement not in self._adjacency:
            return None
        if to_settlement not in self._adjacency:
            return None
        if from_settlement == to_settlement:
            return [from_settlement]

        dist: Dict[str, float] = {from_settlement: 0.0}
        prev: Dict[str, str] = {}
        heap = [(0.0, from_settlement)]
        visited = set()

        while heap:
            d, node = heapq.heappop(heap)
            if node in visited:
                continue
            visited.add(node)

            if node == to_settlement:
                # Reconstruct path
                path = [node]
                while node in prev:
                    node = prev[node]
                    path.append(node)
                path.reverse()
                return path

            for neighbor, seg_idx in self._adjacency.get(node, []):
                if neighbor in visited:
                    continue
                seg = self.segments[seg_idx]
                edge_cost = seg.distance * seg.effective_speed_cost()
                new_dist = d + edge_cost
                if new_dist < dist.get(neighbor, float('inf')):
                    dist[neighbor] = new_dist
                    prev[neighbor] = node
                    heapq.heappush(heap, (new_dist, neighbor))

        return None  # no route found

    def get_route_waypoints(self, from_settlement: str,
                            to_settlement: str) -> Optional[List[Tuple[int, int]]]:
        """Get all tile waypoints along the route between two settlements."""
        route = self.get_route(from_settlement, to_settlement)
        if not route or len(route) < 2:
            return None

        all_waypoints = []
        for i in range(len(route) - 1):
            seg = self.get_road_between(route[i], route[i + 1])
            if seg:
                # Determine direction
                if seg.settlement_a == route[i]:
                    all_waypoints.extend(seg.waypoints)
                else:
                    all_waypoints.extend(reversed(seg.waypoints))
        return all_waypoints

    def get_neighbors(self, settlement_name: str) -> List[str]:
        """Get all settlements directly connected to the given one."""
        return [name for name, _ in self._adjacency.get(settlement_name, [])]

    def degrade_all(self, dt: float):
        """Degrade all road conditions over time."""
        for seg in self.segments:
            seg.degrade(dt)

    def build_from_settlements(self, structures: list, world_tiles: list,
                               world_w: int, world_h: int,
                               rng: random.Random):
        """Build complete road network connecting all settlements.

        Uses minimum spanning tree for base connectivity, then adds
        extra edges for major trade routes.
        """
        # Gather all settlements (not ruins, shrines, dungeons, temples)
        settlement_kinds = {"hamlet", "village", "town", "city", "castle"}
        settlements = [s for s in structures if s.kind in settlement_kinds]
        if len(settlements) < 2:
            return

        n = len(settlements)

        # Build distance matrix
        distances: List[Tuple[float, int, int]] = []
        for i in range(n):
            for j in range(i + 1, n):
                dx = settlements[i].x - settlements[j].x
                dy = settlements[i].y - settlements[j].y
                dist = math.sqrt(dx * dx + dy * dy)
                distances.append((dist, i, j))

        distances.sort()

        # Kruskal's MST
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
                return True
            return False

        mst_edges = []
        for dist, i, j in distances:
            if union(i, j):
                mst_edges.append((i, j, dist))
            if len(mst_edges) == n - 1:
                break

        # Add extra connections for important settlements
        extra_edges = []
        for i in range(n):
            kind = settlements[i].kind
            max_extra = EXTRA_CONNECTIONS.get(kind, 0)
            if max_extra <= 0:
                continue

            # Count existing connections
            existing = sum(1 for a, b, _ in mst_edges if a == i or b == i)
            existing += sum(1 for a, b, _ in extra_edges if a == i or b == i)

            # Find nearest settlements by distance
            neighbors = []
            for d, a, b in distances:
                if a == i:
                    neighbors.append((d, b))
                elif b == i:
                    neighbors.append((d, a))
            neighbors.sort()

            connected_to = set()
            for a, b, _ in mst_edges:
                if a == i:
                    connected_to.add(b)
                elif b == i:
                    connected_to.add(a)
            for a, b, _ in extra_edges:
                if a == i:
                    connected_to.add(b)
                elif b == i:
                    connected_to.add(a)

            added = 0
            for d, j in neighbors:
                if added >= max_extra:
                    break
                if j in connected_to:
                    continue
                extra_edges.append((i, j, d))
                connected_to.add(j)
                added += 1

        # Build all road segments
        all_edges = mst_edges + extra_edges
        for i, j, dist in all_edges:
            sa = settlements[i]
            sb = settlements[j]
            road_type = _road_type_for_pair(sa.kind, sb.kind)

            # Check if road goes through mountains
            goes_through_mountains = self._check_mountain_crossing(
                sa.x, sa.y, sb.x, sb.y, world_tiles, world_w, world_h)
            if goes_through_mountains:
                road_type = RoadType.MOUNTAIN_PASS

            # Generate waypoints using A* road pathing
            waypoints = self._route_road(
                sa.x, sa.y, sb.x, sb.y,
                world_tiles, world_w, world_h, rng)

            # Ensure road connects to settlement centers and has no gaps
            if waypoints:
                first = waypoints[0]
                if first != (sa.x, sa.y):
                    bridge = self._bresenham(sa.x, sa.y, first[0], first[1])
                    waypoints = bridge + waypoints
                last = waypoints[-1]
                if last != (sb.x, sb.y):
                    bridge = self._bresenham(last[0], last[1], sb.x, sb.y)
                    waypoints = waypoints + bridge
                # Final gap-fill pass
                waypoints = self._fill_gaps(waypoints)

            segment = RoadSegment(sa.name, sb.name, road_type, dist, waypoints)
            self.add_segment(segment)

    def _check_mountain_crossing(self, x0: int, y0: int, x1: int, y1: int,
                                  tiles: list, w: int, h: int) -> bool:
        """Check if a direct line between two points crosses mountains."""
        from game.settings import MOUNTAIN, SNOW
        dx = x1 - x0
        dy = y1 - y0
        dist = max(1, int(math.sqrt(dx * dx + dy * dy)))
        mountain_count = 0
        samples = min(dist, 50)
        for step in range(samples):
            t = step / max(1, samples - 1)
            px = int(x0 + dx * t)
            py = int(y0 + dy * t)
            if 0 <= px < w and 0 <= py < h:
                if tiles[py][px] in (MOUNTAIN, SNOW):
                    mountain_count += 1
        return mountain_count > samples * 0.15

    def _route_road(self, x0: int, y0: int, x1: int, y1: int,
                    tiles: list, w: int, h: int,
                    rng: random.Random) -> List[Tuple[int, int]]:
        """Route a road between two points, avoiding mountains and water.
        Uses simplified A* with large steps for performance."""
        from game.settings import WATER, MOUNTAIN, SNOW

        # For short distances, just do a direct path with wobble
        dist = math.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
        if dist < 30:
            return self._direct_road_path(x0, y0, x1, y1, rng)

        # A* on a coarse grid (every 5 tiles) for performance
        step_size = 5
        sx, sy = x0 // step_size, y0 // step_size
        ex, ey = x1 // step_size, y1 // step_size

        max_w = w // step_size + 1
        max_h = h // step_size + 1

        def cost_at(gx, gy):
            """Cost of traversing a coarse grid cell."""
            px, py = gx * step_size, gy * step_size
            if not (0 <= px < w and 0 <= py < h):
                return 999
            tile = tiles[py][px]
            if tile == WATER:
                return 5.0  # can bridge but expensive
            if tile in (MOUNTAIN, SNOW):
                return 15.0  # very expensive, prefer going around
            return 1.0

        def heuristic(ax, ay):
            return abs(ax - ex) + abs(ay - ey)

        open_set = [(0 + heuristic(sx, sy), 0, sx, sy)]
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score = {(sx, sy): 0.0}
        expanded = 0
        max_expand = 3000

        while open_set and expanded < max_expand:
            _, g, cx, cy = heapq.heappop(open_set)
            expanded += 1

            if cx == ex and cy == ey:
                # Reconstruct coarse path
                path = [(cx, cy)]
                while (cx, cy) in came_from:
                    cx, cy = came_from[(cx, cy)]
                    path.append((cx, cy))
                path.reverse()
                # Convert coarse path to fine waypoints
                fine_path = []
                # Start from actual origin
                coarse_fine = [(x0, y0)]
                for p in path[1:-1]:
                    coarse_fine.append((p[0] * step_size, p[1] * step_size))
                coarse_fine.append((x1, y1))

                for i in range(len(coarse_fine) - 1):
                    ax, ay = coarse_fine[i]
                    bx, by = coarse_fine[i + 1]
                    sub = self._direct_road_path(ax, ay, bx, by, rng)
                    # Bridge gap from previous sub-path
                    if fine_path and sub:
                        lx, ly = fine_path[-1]
                        fx, fy = sub[0]
                        if abs(lx - fx) > 1 or abs(ly - fy) > 1:
                            bridge = self._bresenham(lx, ly, fx, fy)
                            fine_path.extend(bridge[1:])
                    fine_path.extend(sub)
                return fine_path

            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1),
                           (-1, -1), (1, -1), (-1, 1), (1, 1)]:
                nx, ny = cx + dx, cy + dy
                if not (0 <= nx < max_w and 0 <= ny < max_h):
                    continue
                c = cost_at(nx, ny)
                if c >= 999:
                    continue
                move_cost = c * (1.414 if dx != 0 and dy != 0 else 1.0)
                new_g = g_score.get((cx, cy), float('inf')) + move_cost
                if new_g < g_score.get((nx, ny), float('inf')):
                    g_score[(nx, ny)] = new_g
                    came_from[(nx, ny)] = (cx, cy)
                    f = new_g + heuristic(nx, ny)
                    heapq.heappush(open_set, (f, new_g, nx, ny))

        # A* failed -- fall back to direct path
        return self._direct_road_path(x0, y0, x1, y1, rng)

    @staticmethod
    def _fill_gaps(waypoints: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Fill any gaps in a waypoint list using Bresenham interpolation."""
        if len(waypoints) < 2:
            return waypoints
        result = [waypoints[0]]
        for i in range(1, len(waypoints)):
            px, py = result[-1]
            nx, ny = waypoints[i]
            if abs(px - nx) > 1 or abs(py - ny) > 1:
                bridge = RoadNetwork._bresenham(px, py, nx, ny)
                result.extend(bridge[1:])  # skip first (already in result)
            else:
                result.append((nx, ny))
        return result

    def _direct_road_path(self, x0: int, y0: int, x1: int, y1: int,
                          rng: random.Random) -> List[Tuple[int, int]]:
        """Generate a continuous road path with gentle wobble.
        Returns one waypoint per tile — no gaps."""
        dx = x1 - x0
        dy = y1 - y0
        dist = max(1, int(math.sqrt(dx * dx + dy * dy)))
        seed_offset = rng.randint(0, 10000)

        # First generate sparse control points with wobble
        num_control = max(2, dist // 8)
        control_points = []
        for i in range(num_control + 1):
            t = i / max(1, num_control)
            wobble_x = math.sin(t * 6 + seed_offset) * 2.0
            wobble_y = math.cos(t * 5 + seed_offset) * 2.0
            # Reduce wobble near endpoints
            edge_factor = min(t, 1.0 - t) * 4
            edge_factor = min(1.0, edge_factor)
            px = x0 + dx * t + wobble_x * edge_factor
            py = y0 + dy * t + wobble_y * edge_factor
            control_points.append((px, py))

        # Interpolate between control points using Bresenham-style fill
        # to ensure every tile along the path is included
        waypoints = []
        seen = set()
        for i in range(len(control_points) - 1):
            ax, ay = control_points[i]
            bx, by = control_points[i + 1]
            # Bresenham line between consecutive control points
            for pt in self._bresenham(int(ax), int(ay), int(bx), int(by)):
                if pt not in seen:
                    seen.add(pt)
                    waypoints.append(pt)

        return waypoints

    @staticmethod
    def _bresenham(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
        """Bresenham's line algorithm — yields every tile along a line."""
        points = []
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            points.append((x0, y0))
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

        return points


# ================================================================
# ROAD MAINTENANCE
# ================================================================

class RoadMaintenance:
    """Manages NPC road-maintenance jobs."""

    def __init__(self, road_network: RoadNetwork):
        self.road_network = road_network
        self._update_timer = 0.0
        self._assigned_workers: Dict[str, int] = {}  # npc_name -> segment_index

    def find_worst_road(self) -> Optional[int]:
        """Find the road segment in worst condition."""
        worst_idx = None
        worst_cond = 1.0
        for i, seg in enumerate(self.road_network.segments):
            if seg.condition < worst_cond:
                worst_cond = seg.condition
                worst_idx = i
        # Only send workers if condition is below 0.7
        if worst_cond < 0.7:
            return worst_idx
        return None

    def assign_worker(self, npc, world) -> Optional[Tuple[float, float]]:
        """Assign an NPC to repair the worst road. Returns target position or None."""
        if not hasattr(npc, 'npc_skills'):
            return None

        skills = getattr(npc, 'npc_skills', {})
        # Need masonry or general skill
        repair_skill = max(skills.get('masonry', 0), skills.get('navigation', 0), 1)

        # Find worst road
        seg_idx = self.find_worst_road()
        if seg_idx is None:
            return None

        seg = self.road_network.segments[seg_idx]
        self._assigned_workers[getattr(npc, 'name', 'unknown')] = seg_idx

        # Target the midpoint of the road
        if seg.waypoints:
            mid = seg.waypoints[len(seg.waypoints) // 2]
            return (float(mid[0]), float(mid[1]))
        return None

    def do_repair(self, npc, dt: float):
        """NPC performs road repair work. Called while NPC is at the road."""
        npc_name = getattr(npc, 'name', 'unknown')
        seg_idx = self._assigned_workers.get(npc_name)
        if seg_idx is None or seg_idx >= len(self.road_network.segments):
            return

        seg = self.road_network.segments[seg_idx]
        skills = getattr(npc, 'npc_skills', {})
        repair_skill = max(skills.get('masonry', 0), skills.get('navigation', 0), 1)

        # Repair amount depends on skill level
        repair_amount = 0.002 * repair_skill * dt
        seg.repair(repair_amount)

        if seg.condition >= 0.95:
            # Road is repaired, unassign
            del self._assigned_workers[npc_name]

    def update(self, dt: float):
        """Update road degradation."""
        self._update_timer += dt
        if self._update_timer < 30.0:
            return
        self._update_timer = 0.0
        self.road_network.degrade_all(30.0)


# ================================================================
# ROADSIDE INN PLACEMENT
# ================================================================

def place_roadside_inns(road_network: RoadNetwork,
                        world_tiles: list, world_w: int, world_h: int,
                        structures: list,
                        rng: random.Random) -> List[dict]:
    """Place small inns/taverns at intervals along long roads.

    Places an inn every ~80 tiles on PAVED_ROAD and KING_ROAD segments.
    Returns list of inn placement data for NPC spawning.
    """
    from game.settings import ROAD, GRASS, FOREST, SAND, FLOOR, WALL, DOOR
    from game.world.world import Structure

    inn_data = []
    placed_positions = set()

    # Only place inns on major roads (paved and king)
    target_road_types = {RoadType.PAVED_ROAD, RoadType.KING_ROAD}
    inn_interval = 80  # tiles between inns

    for seg in road_network.segments:
        if seg.road_type not in target_road_types:
            continue
        if seg.distance < inn_interval * 0.8:
            continue

        # Calculate how many inns to place
        num_inns = max(1, int(seg.distance / inn_interval))

        for inn_i in range(num_inns):
            # Position along the road
            t = (inn_i + 1) / (num_inns + 1)
            wp_idx = int(t * max(1, len(seg.waypoints) - 1))
            wp_idx = min(wp_idx, len(seg.waypoints) - 1)

            if not seg.waypoints:
                continue

            ix, iy = seg.waypoints[wp_idx]

            # Check we're not too close to existing structures or inns
            too_close = False
            for s in structures:
                if math.sqrt((s.x - ix) ** 2 + (s.y - iy) ** 2) < 15:
                    too_close = True
                    break
            for px, py in placed_positions:
                if math.sqrt((px - ix) ** 2 + (py - iy) ** 2) < 40:
                    too_close = True
                    break
            if too_close:
                continue

            # Place a small inn (5x4 building)
            bw, bh = 5, 4
            # Offset slightly from road
            offset = rng.choice([-3, 3])
            bx = ix + offset
            by = iy

            # Check bounds and ground suitability
            if not (2 <= bx < world_w - bw - 2 and 2 <= by < world_h - bh - 2):
                continue

            can_place = True
            for dy in range(bh):
                for dx in range(bw):
                    tx, ty = bx + dx, by + dy
                    if not (0 <= tx < world_w and 0 <= ty < world_h):
                        can_place = False
                        break
                    tile = world_tiles[ty][tx]
                    from game.settings import WATER, MOUNTAIN, SNOW, WALL as WALL_TILE
                    if tile in (WATER, MOUNTAIN, SNOW, WALL_TILE):
                        can_place = False
                        break
                if not can_place:
                    break

            if not can_place:
                continue

            # Stamp the building
            for dy in range(bh):
                for dx in range(bw):
                    tx, ty = bx + dx, by + dy
                    if dx == 0 or dx == bw - 1 or dy == 0 or dy == bh - 1:
                        world_tiles[ty][tx] = WALL
                    else:
                        world_tiles[ty][tx] = FLOOR

            # Place door facing the road
            door_x = bx + bw // 2
            door_y = by if offset > 0 else by + bh - 1
            if 0 <= door_x < world_w and 0 <= door_y < world_h:
                world_tiles[door_y][door_x] = DOOR

            # Connect to road
            for step_y in range(min(iy, by), max(iy, by) + 1):
                if 0 <= door_x < world_w and 0 <= step_y < world_h:
                    if world_tiles[step_y][door_x] in (GRASS, FOREST, SAND):
                        world_tiles[step_y][door_x] = ROAD

            placed_positions.add((ix, iy))

            inn_name = rng.choice([
                "The Weary Traveler", "Roadside Rest", "The Crossroads Inn",
                "The Wayfarer's Lodge", "The Dusty Boot", "The Iron Horseshoe",
                "The Sleeping Bear", "The Wandering Minstrel",
                "The Rooster's Crow", "The Pilgrim's Hearth",
                "The Copper Lantern", "The Three Bridges",
            ]) + f" ({seg.settlement_a[:4]}-{seg.settlement_b[:4]})"

            inn_struct = Structure(inn_name, "tavern", bx + bw // 2, by + bh // 2, radius=3)
            structures.append(inn_struct)

            inn_data.append({
                "x": float(bx + 2), "y": float(by + 1),
                "class": "Bard", "race": "",
                "building": "Roadside Inn",
                "name": inn_name,
            })

    return inn_data
