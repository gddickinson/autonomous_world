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


class ConstructionSystem:
    """Manages construction projects across the world."""

    def __init__(self):
        self.projects: List[ConstructionProject] = []
        self.completed_projects: List[str] = []
        self.update_timer = 0.0

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

    def get_log(self) -> List[str]:
        msgs = list(self.completed_projects)
        self.completed_projects.clear()
        return msgs
