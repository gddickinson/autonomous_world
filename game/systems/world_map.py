"""
World Knowledge Map — shared knowledge of explored locations.

A global map that NPCs and the player can consult to plan journeys.
Records known locations of:
- Settlements (name, position, kind, services available)
- Water sources (wells, rivers, lakes)
- Roads and paths
- Dangerous areas (monster territories, ruins)
- Resource locations (forests for wood, mountains for ore)

NPCs use this to:
- Plan supply requirements before a journey
- Choose safe routes between settlements
- Estimate travel time and provisions needed
- Avoid known dangers (or seek them out, depending on alignment)

The map starts partially populated (common knowledge) and grows as
NPCs and the player explore and share information.
"""

import math
from typing import Dict, List, Optional, Tuple, Set


class MapLocation:
    """A known location on the world map."""
    __slots__ = ('x', 'y', 'kind', 'name', 'details', 'discovered_day')

    def __init__(self, x: int, y: int, kind: str, name: str = "",
                 details: str = "", discovered_day: int = 0):
        self.x = x
        self.y = y
        self.kind = kind  # settlement, water, road, danger, resource, ruin
        self.name = name
        self.details = details
        self.discovered_day = discovered_day

    def dist_to(self, x: float, y: float) -> float:
        return math.sqrt((self.x - x) ** 2 + (self.y - y) ** 2)


class WorldKnowledgeMap:
    """Shared knowledge map of the world. All civilized NPCs can access this."""

    def __init__(self):
        self.locations: List[MapLocation] = []
        self._settlement_index: Dict[str, MapLocation] = {}
        self._water_sources: List[MapLocation] = []
        self._danger_zones: List[MapLocation] = []

    def initialize(self, world, structures: list):
        """Populate the map with known locations from world data."""
        # Settlements are common knowledge
        for s in structures:
            if s.kind in ("hamlet", "village", "town", "city", "castle",
                         "temple", "shrine", "tavern", "ruins"):
                loc = MapLocation(s.x, s.y, "settlement" if s.kind != "ruins" else "ruin",
                                 s.name, f"{s.kind}", 0)
                self.locations.append(loc)
                if s.kind != "ruins":
                    self._settlement_index[s.name] = loc

        # Scan for water sources near settlements (wells, rivers)
        for s in structures:
            if s.kind not in ("hamlet", "village", "town", "city", "castle"):
                continue
            # Find water within settlement radius
            from game.settings import WATER, SHALLOW_WATER, WELL
            r = getattr(s, 'radius', 10) + 5
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    nx, ny = s.x + dx, s.y + dy
                    if 0 <= nx < world.width and 0 <= ny < world.height:
                        tile = world.tiles[ny][nx]
                        if tile in (WATER, SHALLOW_WATER, WELL):
                            # Don't duplicate nearby water
                            if not any(w.dist_to(nx, ny) < 5 for w in self._water_sources):
                                wloc = MapLocation(nx, ny, "water",
                                    f"Water near {s.name}",
                                    "well" if tile == WELL else "river", 0)
                                self.locations.append(wloc)
                                self._water_sources.append(wloc)
                            break
                    # Only check in a cross pattern for speed
                    if abs(dx) > 3 and abs(dy) > 3:
                        continue

        # Roads connect settlements — mark road network
        from game.settings import ROAD, GRAVEL_ROAD
        # Sample road tiles near settlements
        for s in structures:
            if s.kind in ("hamlet", "village", "town", "city"):
                for d in range(5, 30, 5):
                    for angle_i in range(8):
                        angle = angle_i * math.pi / 4
                        tx = int(s.x + math.cos(angle) * d)
                        ty = int(s.y + math.sin(angle) * d)
                        if 0 <= tx < world.width and 0 <= ty < world.height:
                            if world.tiles[ty][tx] in (ROAD, GRAVEL_ROAD):
                                if not any(l.dist_to(tx, ty) < 10 for l in self.locations
                                          if l.kind == "road"):
                                    self.locations.append(MapLocation(
                                        tx, ty, "road", "Road", "", 0))

    def find_nearest_water(self, x: float, y: float,
                           max_dist: float = 100) -> Optional[MapLocation]:
        """Find the nearest known water source."""
        best = None
        best_dist = max_dist
        for w in self._water_sources:
            d = w.dist_to(x, y)
            if d < best_dist:
                best_dist = d
                best = w
        return best

    def find_nearest_settlement(self, x: float, y: float,
                                max_dist: float = 200) -> Optional[MapLocation]:
        """Find the nearest known settlement."""
        best = None
        best_dist = max_dist
        for loc in self.locations:
            if loc.kind == "settlement":
                d = loc.dist_to(x, y)
                if d < best_dist:
                    best_dist = d
                    best = loc
        return best

    def find_settlements_between(self, x1: float, y1: float,
                                  x2: float, y2: float,
                                  corridor_width: float = 30) -> List[MapLocation]:
        """Find settlements along a route between two points (for resupply stops)."""
        results = []
        dx, dy = x2 - x1, y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            return results

        nx, ny = dx / length, dy / length  # route direction
        px, py = -ny, nx  # perpendicular

        for loc in self.locations:
            if loc.kind != "settlement":
                continue
            # Project onto route
            lx, ly = loc.x - x1, loc.y - y1
            along = lx * nx + ly * ny  # distance along route
            perp = abs(lx * px + ly * py)  # distance from route
            if 0 <= along <= length and perp < corridor_width:
                results.append(loc)

        results.sort(key=lambda l: (l.x - x1) * nx + (l.y - y1) * ny)
        return results

    def estimate_journey(self, x1: float, y1: float,
                         x2: float, y2: float,
                         speed: float = 1.2) -> dict:
        """Estimate journey requirements between two points.

        Returns dict with:
            distance: tiles
            travel_time: game seconds
            water_needed: number of water flasks
            food_needed: number of food items
            waypoints: list of settlements to resupply at
            danger_level: 0-1 based on known dangers along route
        """
        distance = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        travel_time = distance / speed  # seconds

        # Water: ~1 flask per 300 game seconds of travel
        water_needed = max(2, int(travel_time / 300) + 1)
        # Food: ~1 item per 400 game seconds
        food_needed = max(1, int(travel_time / 400) + 1)

        # Find waypoints for resupply
        waypoints = self.find_settlements_between(x1, y1, x2, y2)

        # Check for known dangers
        danger = 0.0
        for loc in self.locations:
            if loc.kind in ("danger", "ruin"):
                d = _point_to_line_dist(loc.x, loc.y, x1, y1, x2, y2)
                if d < 20:
                    danger += 0.2

        return {
            "distance": distance,
            "travel_time": travel_time,
            "water_needed": water_needed,
            "food_needed": food_needed,
            "waypoints": waypoints,
            "danger_level": min(1.0, danger),
        }


def _point_to_line_dist(px, py, x1, y1, x2, y2) -> float:
    """Distance from point (px,py) to line segment (x1,y1)-(x2,y2)."""
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq < 0.01:
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)


# ================================================================
# JOURNEY PLANNER — NPCs prepare before leaving settlement
# ================================================================

def plan_journey(npc, destination_x: float, destination_y: float,
                 world_map: WorldKnowledgeMap) -> dict:
    """Plan a journey for an NPC, determining supplies needed.

    Returns dict with:
        should_go: bool (False if too dangerous or under-supplied)
        supplies_needed: dict of item_name -> count
        waypoints: list of resupply points
        estimated_time: game seconds
    """
    from game.core.items import FOOD_ITEMS, DRINK_ITEMS

    estimate = world_map.estimate_journey(npc.x, npc.y,
                                           destination_x, destination_y)

    # Check current supplies
    current_food = sum(1 for i in npc.npc_inventory if i.name in FOOD_ITEMS)
    current_water = sum(i.count if i.stackable else 1
                       for i in npc.npc_inventory if i.name in DRINK_ITEMS)

    food_deficit = max(0, estimate["food_needed"] - current_food)
    water_deficit = max(0, estimate["water_needed"] - current_water)

    # With waypoints, we need less — can resupply
    if estimate["waypoints"]:
        food_deficit = max(0, food_deficit - len(estimate["waypoints"]) * 2)
        water_deficit = max(0, water_deficit - len(estimate["waypoints"]) * 2)

    supplies_needed = {}
    if food_deficit > 0:
        supplies_needed["Bread"] = food_deficit
    if water_deficit > 0:
        supplies_needed["Water Flask"] = water_deficit

    # Should they go? Consider bravery, supplies, danger
    bravery = getattr(npc, 'bravery', 0.5)
    has_enough = (food_deficit <= 0 and water_deficit <= 0)
    danger_ok = estimate["danger_level"] < bravery

    should_go = has_enough or (food_deficit <= 2 and water_deficit <= 2)
    if estimate["danger_level"] > 0.5 and bravery < 0.4:
        should_go = False

    return {
        "should_go": should_go,
        "supplies_needed": supplies_needed,
        "waypoints": estimate["waypoints"],
        "estimated_time": estimate["travel_time"],
        "distance": estimate["distance"],
        "danger_level": estimate["danger_level"],
    }


def prepare_for_journey(npc, plan: dict) -> bool:
    """NPC gathers supplies for a planned journey.
    Returns True if ready to depart, False if still need supplies.
    """
    from game.core.items import make_item

    # Try to acquire needed supplies
    for item_name, count in plan["supplies_needed"].items():
        current = npc.npc_count_item(item_name)
        if current < count:
            # Try to buy from gold
            needed = count - current
            from game.core.items import ITEMS
            item_template = ITEMS.get(item_name)
            cost_per = item_template.value if item_template else 3
            total_cost = needed * cost_per

            if npc.npc_gold >= total_cost:
                npc.npc_gold -= total_cost
                item = make_item(item_name)
                item.count = needed
                npc.npc_add_item(item)
            else:
                return False  # can't afford

    return True
