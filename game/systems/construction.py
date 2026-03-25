"""
Construction & Infrastructure: work orders, road building, settlement founding.

NPCs and kingdoms can commission construction projects.
Workers gather materials and build over time.
Successful settlements grow and upgrade buildings.
Roads connect settlements and improve trade.
"""

import random
import math
from typing import Dict, List, Optional, Tuple
from game.settings import *


class ConstructionProject:
    """A building or infrastructure project."""
    def __init__(self, kind: str, x: int, y: int, name: str = ""):
        self.kind = kind  # "road", "building", "wall", "upgrade", "settlement"
        self.x = x
        self.y = y
        self.name = name
        self.progress = 0.0  # 0 to 1
        self.required_materials = {}  # item_name -> count needed
        self.materials_delivered = {}  # item_name -> count delivered
        self.workers: List[str] = []  # NPC names assigned
        self.commissioned_by = ""  # kingdom or NPC name
        self.completed = False

    @property
    def material_ready(self) -> bool:
        for item, needed in self.required_materials.items():
            if self.materials_delivered.get(item, 0) < needed:
                return False
        return True


# Project templates
PROJECT_TEMPLATES = {
    "road_segment": {
        "materials": {"Stone": 2, "Wood": 1},
        "workers_needed": 1,
        "build_time": 10.0,  # seconds
    },
    "wooden_house": {
        "materials": {"Wood": 8, "Nails": 6, "Planks": 4},
        "workers_needed": 2,
        "build_time": 30.0,
    },
    "stone_wall": {
        "materials": {"Stone": 5},
        "workers_needed": 1,
        "build_time": 15.0,
    },
    "upgrade_house": {
        "materials": {"Stone": 4, "Planks": 6, "Nails": 4, "Glass Pane": 2},
        "workers_needed": 2,
        "build_time": 40.0,
    },
    "new_settlement": {
        "materials": {"Wood": 20, "Stone": 10, "Nails": 10, "Planks": 8},
        "workers_needed": 4,
        "build_time": 120.0,
    },
}


# Building types that settlements can construct (abstract, not tile-level)
SETTLEMENT_BUILDINGS = {
    "tavern":       {"cost": 60,  "min_pop": 5,  "days": 8},
    "smithy":       {"cost": 80,  "min_pop": 8,  "days": 10},
    "market":       {"cost": 70,  "min_pop": 10, "days": 9},
    "barracks":     {"cost": 100, "min_pop": 12, "days": 12},
    "temple":       {"cost": 90,  "min_pop": 10, "days": 11},
    "library":      {"cost": 120, "min_pop": 15, "days": 14},
    "granary":      {"cost": 50,  "min_pop": 6,  "days": 7},
    "stables":      {"cost": 70,  "min_pop": 8,  "days": 9},
    "watchtower":   {"cost": 40,  "min_pop": 4,  "days": 6},
    "inn":          {"cost": 55,  "min_pop": 7,  "days": 8},
    "guild_hall":   {"cost": 150, "min_pop": 20, "days": 15},
    "walls":        {"cost": 200, "min_pop": 15, "days": 20},
    "workshop":     {"cost": 65,  "min_pop": 8,  "days": 9},
    "warehouse":    {"cost": 75,  "min_pop": 10, "days": 10},
}


class SettlementBuildProject:
    """A building under construction in a settlement (day-based timer)."""
    def __init__(self, settlement_name: str, building_type: str,
                 days_remaining: int, commissioned_by: str = ""):
        self.settlement_name = settlement_name
        self.building_type = building_type
        self.days_remaining = days_remaining
        self.commissioned_by = commissioned_by


class RoadBuildProject:
    """A road under construction between two settlements (day-based timer)."""
    def __init__(self, start_name: str, end_name: str,
                 start_x: int, start_y: int,
                 end_x: int, end_y: int,
                 days_remaining: int, commissioned_by: str = ""):
        self.start_name = start_name
        self.end_name = end_name
        self.start_x = start_x
        self.start_y = start_y
        self.end_x = end_x
        self.end_y = end_y
        self.days_remaining = days_remaining
        self.commissioned_by = commissioned_by


class ConstructionSystem:
    """Manages construction projects across the world."""

    def __init__(self):
        self.projects: List[ConstructionProject] = []
        self.completed_projects: List[str] = []
        self.update_timer = 0.0
        # Day-based settlement building projects (bypass material/worker reqs)
        self.building_projects: List[SettlementBuildProject] = []
        # Track which buildings each settlement has (name -> list of building types)
        self.settlement_buildings: Dict[str, List[str]] = {}
        # Day-based road construction projects
        self.road_build_projects: List[RoadBuildProject] = []

    def commission_project(self, kind: str, x: int, y: int,
                           commissioned_by: str = "", name: str = "") -> Optional[ConstructionProject]:
        """Create a new construction project."""
        template = PROJECT_TEMPLATES.get(kind)
        if not template:
            return None

        project = ConstructionProject(kind, x, y, name or kind)
        project.required_materials = dict(template["materials"])
        project.commissioned_by = commissioned_by
        self.projects.append(project)
        return project

    def update(self, dt: float, npcs: list, world):
        """Update construction progress."""
        self.update_timer += dt
        if self.update_timer < 5.0:
            return
        self.update_timer = 0.0

        remaining = []
        for project in self.projects:
            if project.completed:
                continue

            # Check if materials are ready and workers present
            if not project.material_ready:
                remaining.append(project)
                continue

            # Count workers at site
            workers_present = 0
            for npc in npcs:
                if (npc.alive and npc.name in project.workers and
                    npc.dist_to_pos(project.x, project.y) < 5):
                    workers_present += 1

            if workers_present == 0:
                remaining.append(project)
                continue

            # Progress based on workers
            template = PROJECT_TEMPLATES.get(project.kind, {})
            speed = workers_present / max(1, template.get("workers_needed", 1))
            project.progress += speed * 5.0 / max(1, template.get("build_time", 30))

            if project.progress >= 1.0:
                self._complete_project(project, world)
                self.completed_projects.append(
                    f"Completed: {project.name} at ({project.x}, {project.y})")
            else:
                remaining.append(project)

        self.projects = remaining

    def _complete_project(self, project: ConstructionProject, world):
        """Apply completed construction to the world."""
        project.completed = True

        if project.kind == "road_segment":
            world.modify_tile(project.x, project.y, ROAD)

        elif project.kind == "wooden_house":
            # Place a small building
            for dy in range(4):
                for dx in range(5):
                    nx, ny = project.x + dx, project.y + dy
                    if 0 <= nx < world.width and 0 <= ny < world.height:
                        if dy == 0 or dy == 3 or dx == 0 or dx == 4:
                            world.modify_tile(nx, ny, BUILT_WALL)
                        else:
                            world.modify_tile(nx, ny, BUILT_FLOOR)
            # Door
            world.modify_tile(project.x + 2, project.y + 3, DOOR)

        elif project.kind == "stone_wall":
            world.modify_tile(project.x, project.y, BUILT_WALL)

        elif project.kind == "new_settlement":
            from game.world.settlements import generate_settlement
            generate_settlement(
                project.name or "New Settlement", "hamlet",
                project.x, project.y,
                world.tiles, world.width, world.height,
                random.Random(), "", ""
            )

    def auto_commission(self, governance, world, structures):
        """Kingdoms automatically commission useful projects."""
        for kingdom_name, kingdom in governance.kingdoms.items():
            if kingdom.treasury < 50:
                continue

            # Road building between owned settlements
            if random.random() < 0.02 and len(kingdom.settlements) >= 2:
                # Find two settlements that need a road
                for s in structures:
                    if s.name in kingdom.settlements:
                        # Build road toward castle
                        mid_x = (s.x + kingdom.castle_x) // 2
                        mid_y = (s.y + kingdom.castle_y) // 2
                        if world.tiles[mid_y][mid_x] not in (ROAD, WATER, WALL):
                            self.commission_project("road_segment", mid_x, mid_y,
                                                   kingdom_name, f"Road near {s.name}")
                            kingdom.treasury -= 10
                            break

    def advance_building_projects(self, structures: list):
        """Advance day-based building projects by one day. Call once per game day."""
        struct_map = {s.name: s for s in structures}
        remaining = []
        for proj in self.building_projects:
            proj.days_remaining -= 1
            if proj.days_remaining <= 0:
                # Complete the building
                sname = proj.settlement_name
                btype = proj.building_type
                if sname not in self.settlement_buildings:
                    self.settlement_buildings[sname] = []
                self.settlement_buildings[sname].append(btype)

                # Also add to structure.buildings as a marker rect if possible
                struct = struct_map.get(sname)
                if struct:
                    # Append a symbolic (0,0,0,0) entry so len(buildings) grows
                    struct.buildings.append((struct.x, struct.y, 0, 0))

                display = btype.replace("_", " ").title()
                self.completed_projects.append(
                    f"Construction complete: New {display} built in {sname}")
            else:
                remaining.append(proj)
        self.building_projects = remaining

    def auto_commission_buildings(self, governance, structures):
        """Daily check: settlements with enough gold and population build new buildings."""
        struct_map = {s.name: s for s in structures}
        kingdoms = governance.kingdoms if hasattr(governance, 'kingdoms') else {}

        # Collect settlements already building something
        building_now = {p.settlement_name for p in self.building_projects}

        for kingdom_name, kingdom in kingdoms.items():
            if kingdom.treasury < 50:
                continue

            for sname in kingdom.settlements:
                if sname in building_now:
                    continue  # one project at a time per settlement

                struct = struct_map.get(sname)
                if not struct:
                    continue

                # Estimate population from NPC density proxy: use building count
                existing = self.settlement_buildings.get(sname, [])
                num_buildings = len(existing) + len(struct.buildings)

                # Determine what's missing
                candidates = []
                for btype, info in SETTLEMENT_BUILDINGS.items():
                    if btype in existing:
                        continue  # already has this building
                    if info["cost"] > kingdom.treasury:
                        continue
                    # Population proxy: more buildings = more pop assumed
                    # Small settlements get small buildings first
                    if num_buildings < info["min_pop"] // 3:
                        continue
                    candidates.append((btype, info))

                if not candidates and num_buildings > 0:
                    continue

                # Chance to commission: larger settlements build more often
                chance = 0.08 + num_buildings * 0.01
                if random.random() > chance:
                    continue

                if not candidates:
                    continue

                # Pick a building — prefer cheaper ones for smaller settlements
                candidates.sort(key=lambda c: c[1]["cost"])
                # Weight toward first few (cheaper) options
                idx = min(random.randint(0, 2), len(candidates) - 1)
                btype, info = candidates[idx]

                # Commission it
                days = info["days"] + random.randint(-2, 3)
                days = max(3, days)
                cost = info["cost"]

                proj = SettlementBuildProject(sname, btype, days, kingdom_name)
                self.building_projects.append(proj)
                kingdom.treasury -= cost

                display = btype.replace("_", " ").title()
                self.completed_projects.append(
                    f"{kingdom_name} commissions a {display} in {sname} "
                    f"(cost: {cost}g, completion in {days} days)")
                break  # one commission per kingdom per day

    # ------------------------------------------------------------------
    # Road construction between growing settlements
    # ------------------------------------------------------------------

    def check_road_construction(self, governance, structures, world_plan):
        """Growing settlements may build roads to unconnected neighbours.

        Called once per game day. When a settlement exceeds a population
        threshold, it can commission a road to the nearest settlement
        that isn't already connected by road.
        """
        if world_plan is None:
            return

        # Population threshold: settlements need enough buildings to justify
        POP_THRESHOLD = 8  # number of buildings (proxy for population)
        ROAD_BUILD_CHANCE = 0.05  # daily chance per qualifying settlement

        # Build a set of already-connected settlement pairs
        connected = set()
        for road in world_plan.roads:
            pair = tuple(sorted([road.start_name, road.end_name]))
            connected.add(pair)

        # Also track roads currently under construction
        building_roads = set()
        for proj in self.road_build_projects:
            pair = tuple(sorted([proj.start_name, proj.end_name]))
            building_roads.add(pair)

        struct_map = {s.name: s for s in structures}
        kingdoms = governance.kingdoms if hasattr(governance, 'kingdoms') else {}

        for kname, kingdom in kingdoms.items():
            if kingdom.treasury < 100:
                continue

            for sname in kingdom.settlements:
                struct = struct_map.get(sname)
                if not struct:
                    continue

                # Check population threshold (building count as proxy)
                num_buildings = len(getattr(struct, 'buildings', []))
                existing = self.settlement_buildings.get(sname, [])
                num_buildings += len(existing)
                if num_buildings < POP_THRESHOLD:
                    continue

                if random.random() > ROAD_BUILD_CHANCE:
                    continue

                # Find nearest unconnected settlement
                best_target = None
                best_dist = float('inf')

                for other in structures:
                    if other.name == sname:
                        continue
                    pair = tuple(sorted([sname, other.name]))
                    if pair in connected or pair in building_roads:
                        continue

                    dist = math.sqrt((struct.x - other.x) ** 2 +
                                     (struct.y - other.y) ** 2)
                    if dist < best_dist and dist < 500:
                        best_dist = dist
                        best_target = other

                if best_target is None:
                    continue

                # Commission road construction (10-20 game days)
                days = random.randint(10, 20)
                cost = int(best_dist * 0.2) + 50
                if cost > kingdom.treasury:
                    continue

                proj = RoadBuildProject(
                    sname, best_target.name,
                    struct.x, struct.y,
                    best_target.x, best_target.y,
                    days, kname)
                self.road_build_projects.append(proj)
                kingdom.treasury -= cost

                pair = tuple(sorted([sname, best_target.name]))
                building_roads.add(pair)

                self.completed_projects.append(
                    f"{kname} begins road construction: "
                    f"{sname} to {best_target.name} "
                    f"(est. {days} days)")
                break  # one road per kingdom per day

    def advance_road_projects(self, world, world_plan):
        """Advance road construction projects by one day.

        When complete, stamp road tiles into the world and add the road
        to the world plan so it persists across chunk regeneration.
        """
        if world_plan is None:
            return

        remaining = []
        for proj in self.road_build_projects:
            proj.days_remaining -= 1
            if proj.days_remaining <= 0:
                # Complete: stamp road tiles and register in world plan
                self._complete_road(proj, world, world_plan)
                self.completed_projects.append(
                    f"Road construction complete: "
                    f"{proj.start_name} to {proj.end_name}")
            else:
                remaining.append(proj)
        self.road_build_projects = remaining

    def _complete_road(self, proj, world, world_plan):
        """Stamp road tiles between two settlements and register the road."""
        from game.world.world_plan import RoadPlan

        # Generate waypoints (simple linear interpolation)
        waypoints = []
        x1, y1 = proj.start_x, proj.start_y
        x2, y2 = proj.end_x, proj.end_y
        dist = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        steps = max(2, int(dist / 4))

        for i in range(steps + 1):
            t = i / steps
            wx = int(x1 + (x2 - x1) * t)
            wy = int(y1 + (y2 - y1) * t)
            waypoints.append((wx, wy))

        # Try to use A* pathfinder if available
        try:
            from game.world.road_pathfinder import find_road_path
            better_waypoints = find_road_path(world_plan, x1, y1, x2, y2)
            if better_waypoints and len(better_waypoints) >= 2:
                waypoints = better_waypoints
        except (ImportError, Exception):
            pass

        # Stamp road tiles into the world
        for i in range(len(waypoints) - 1):
            ax, ay = waypoints[i]
            bx, by = waypoints[i + 1]
            seg_dist = max(1, int(math.sqrt((bx - ax)**2 + (by - ay)**2)))
            for j in range(seg_dist + 1):
                t = j / seg_dist
                tx = int(ax + (bx - ax) * t)
                ty = int(ay + (by - ay) * t)
                world.modify_tile(tx, ty, ROAD)

        # Register in world plan so it persists across chunk regeneration
        road = RoadPlan(
            start_name=proj.start_name,
            end_name=proj.end_name,
            road_type="dirt_track",
            waypoints=waypoints,
        )
        world_plan.roads.append(road)

    def get_log(self) -> List[str]:
        msgs = list(self.completed_projects)
        self.completed_projects.clear()
        return msgs
