"""Fast Travel via Roads — teleport between visited settlements along roads.

When player stands on a road tile and presses Y:
- Show connected settlements reachable by road
- Select destination -> player teleports there
- Travel takes game time proportional to road distance (1 min per 10 tiles)
- Can only fast travel to previously visited settlements
- Random encounter chance (10%) during travel -> spawns hostile creatures
"""

import math
import random
from typing import List, Tuple, Optional, Dict
from game.settings import ROAD, GRAVEL_ROAD


def is_on_road(world, x: int, y: int) -> bool:
    """Check if the given tile is a road tile."""
    try:
        tile = world.tiles[y][x]
        return tile in (ROAD, GRAVEL_ROAD)
    except (IndexError, KeyError):
        return False


def get_reachable_settlements(world, player_x: float, player_y: float,
                               visited: set) -> List[Dict]:
    """Find settlements reachable by road from current position.

    Returns list of dicts with settlement info and travel distance.
    Only includes previously visited settlements.
    """
    if not hasattr(world, 'plan'):
        return []

    # Find the nearest settlement to determine road connections
    px, py = int(player_x), int(player_y)
    nearest_settlement = None
    nearest_dist = float('inf')

    for sp in world.plan.settlements:
        dx = px - sp.x
        dy = py - sp.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < nearest_dist:
            nearest_settlement = sp
            nearest_dist = dist

    if not nearest_settlement:
        return []

    # Find all settlements connected by roads
    reachable = []
    connected_names = set()

    # Direct connections through roads
    for road in world.plan.roads:
        if road.start_name == nearest_settlement.name:
            connected_names.add(road.end_name)
        elif road.end_name == nearest_settlement.name:
            connected_names.add(road.start_name)

    # Also find indirect connections (settlements connected through intermediate roads)
    # Do a BFS up to depth 3
    frontier = {nearest_settlement.name}
    all_connected = set()
    for _depth in range(3):
        next_frontier = set()
        for name in frontier:
            for road in world.plan.roads:
                if road.start_name == name and road.end_name not in all_connected:
                    next_frontier.add(road.end_name)
                    all_connected.add(road.end_name)
                elif road.end_name == name and road.start_name not in all_connected:
                    next_frontier.add(road.start_name)
                    all_connected.add(road.start_name)
        frontier = next_frontier
        if not frontier:
            break

    # Build reachable list with distances
    settlement_map = {sp.name: sp for sp in world.plan.settlements}
    for name in all_connected:
        if name == nearest_settlement.name:
            continue
        if name not in visited:
            continue
        sp = settlement_map.get(name)
        if not sp:
            continue

        # Calculate road distance
        road_dist = _calc_road_distance(world, nearest_settlement, sp)
        travel_time = road_dist / 10.0  # 1 minute per 10 tiles

        reachable.append({
            "name": sp.name,
            "kind": sp.kind,
            "x": sp.x,
            "y": sp.y,
            "distance": road_dist,
            "travel_minutes": travel_time,
            "specialization": getattr(sp, 'specialization', 'general'),
        })

    # Sort by distance
    reachable.sort(key=lambda d: d["distance"])
    return reachable


def _calc_road_distance(world, start_sp, end_sp) -> float:
    """Calculate road distance between two settlements.

    Uses road waypoints if available, otherwise straight-line distance.
    """
    # Try to find the road connecting these settlements
    for road in world.plan.roads:
        names = (road.start_name, road.end_name)
        if start_sp.name in names and end_sp.name in names:
            if road.waypoints and len(road.waypoints) >= 2:
                # Sum up waypoint distances
                total = 0
                for i in range(1, len(road.waypoints)):
                    wx1, wy1 = road.waypoints[i - 1]
                    wx2, wy2 = road.waypoints[i]
                    total += math.sqrt((wx2 - wx1) ** 2 + (wy2 - wy1) ** 2)
                return total

    # Fallback: straight-line distance
    dx = end_sp.x - start_sp.x
    dy = end_sp.y - start_sp.y
    return math.sqrt(dx * dx + dy * dy)


def check_random_encounter() -> bool:
    """10% chance of random encounter during fast travel."""
    return random.random() < 0.10


def get_encounter_creatures(player_level: int) -> List[Dict]:
    """Generate random encounter creatures based on player level.

    Returns list of creature spawn dicts.
    """
    # Scale difficulty with player level
    tier = min(3, player_level // 3)

    encounter_tables = [
        # Tier 0 (level 1-2)
        [
            {"kind": "rat", "count": (2, 4)},
            {"kind": "wolf", "count": (1, 3)},
            {"kind": "goblin", "count": (1, 2)},
        ],
        # Tier 1 (level 3-5)
        [
            {"kind": "wolf", "count": (2, 4)},
            {"kind": "goblin", "count": (2, 4)},
            {"kind": "bandit", "count": (1, 3)},
            {"kind": "dire_wolf", "count": (1, 2)},
        ],
        # Tier 2 (level 6-8)
        [
            {"kind": "dire_wolf", "count": (2, 3)},
            {"kind": "bandit", "count": (2, 4)},
            {"kind": "orc", "count": (1, 3)},
            {"kind": "troll", "count": (1, 1)},
        ],
        # Tier 3 (level 9+)
        [
            {"kind": "orc", "count": (2, 4)},
            {"kind": "troll", "count": (1, 2)},
            {"kind": "ogre", "count": (1, 2)},
            {"kind": "drake", "count": (1, 1)},
        ],
    ]

    table = encounter_tables[tier]
    choice = random.choice(table)
    count = random.randint(*choice["count"])

    creatures = []
    for _ in range(count):
        creatures.append({"kind": choice["kind"]})

    return creatures


class FastTravelUI:
    """UI state for the fast travel destination selection."""

    def __init__(self):
        self.active = False
        self.destinations: List[Dict] = []
        self.selected_index = 0
        self._font_sm = None
        self._font_md = None
        self._font_lg = None

    def _ensure_fonts(self):
        if self._font_sm is None:
            import pygame
            self._font_sm = pygame.font.SysFont("monospace", 13)
            self._font_md = pygame.font.SysFont("monospace", 16)
            self._font_lg = pygame.font.SysFont("monospace", 22)

    def open(self, destinations: List[Dict]):
        """Open the destination selection menu."""
        self.destinations = destinations
        self.selected_index = 0
        self.active = True

    def close(self):
        self.active = False
        self.destinations = []
        self.selected_index = 0

    def navigate(self, direction: int):
        """Move selection up/down."""
        if not self.destinations:
            return
        self.selected_index = (self.selected_index + direction) % len(self.destinations)

    def get_selected(self) -> Optional[Dict]:
        """Return the currently selected destination."""
        if self.destinations and 0 <= self.selected_index < len(self.destinations):
            return self.destinations[self.selected_index]
        return None

    def draw(self, screen):
        """Draw the fast travel destination selection menu."""
        if not self.active:
            return

        import pygame
        from game.settings import (
            SCREEN_WIDTH, SCREEN_HEIGHT, UI_BORDER,
            YELLOW, GREEN, GRAY, WHITE,
        )

        self._ensure_fonts()

        # Panel dimensions
        line_h = 22
        header_h = 40
        count = len(self.destinations)
        ph = header_h + max(count, 1) * line_h + 40
        pw = 420
        px = SCREEN_WIDTH // 2 - pw // 2
        py = SCREEN_HEIGHT // 2 - ph // 2

        # Background
        panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel_surf.fill((15, 15, 28, 230))
        screen.blit(panel_surf, (px, py))
        pygame.draw.rect(screen, UI_BORDER, (px, py, pw, ph), 2)

        # Title
        title = self._font_lg.render("Fast Travel", True, (200, 180, 100))
        screen.blit(title, (px + pw // 2 - title.get_width() // 2, py + 8))
        pygame.draw.line(screen, UI_BORDER,
                         (px + 5, py + header_h - 4),
                         (px + pw - 5, py + header_h - 4))

        if not self.destinations:
            msg = self._font_md.render("No reachable settlements", True, GRAY)
            screen.blit(msg, (px + pw // 2 - msg.get_width() // 2,
                              py + header_h + 10))
        else:
            y = py + header_h + 4
            for i, dest in enumerate(self.destinations):
                is_selected = (i == self.selected_index)
                # Highlight selected
                if is_selected:
                    sel_bg = pygame.Surface((pw - 10, line_h), pygame.SRCALPHA)
                    sel_bg.fill((60, 80, 60, 120))
                    screen.blit(sel_bg, (px + 5, y))

                name_color = YELLOW if is_selected else WHITE
                kind = dest["kind"].capitalize()
                spec = dest.get("specialization", "")
                spec_str = f" ({spec})" if spec and spec != "general" else ""
                name_str = f"  {dest['name']} [{kind}{spec_str}]"
                screen.blit(self._font_sm.render(name_str, True, name_color),
                            (px + 10, y + 2))

                # Distance info on right
                dist = dest["distance"]
                mins = dest["travel_minutes"]
                dist_str = f"{dist:.0f} tiles  ~{mins:.0f} min"
                dist_surf = self._font_sm.render(dist_str, True, GRAY)
                screen.blit(dist_surf,
                            (px + pw - dist_surf.get_width() - 12, y + 2))
                y += line_h

        # Footer
        hint = self._font_sm.render(
            "W/S: Select  Enter: Travel  Esc: Cancel", True, (120, 120, 140))
        screen.blit(hint, (px + pw // 2 - hint.get_width() // 2, py + ph - 20))
