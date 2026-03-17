"""
Battle Visuals System — projectiles, siege engines, mounted units, formations.

Provides visual feedback for warfare that can be rendered by any renderer.
Tracks active projectiles, siege engine positions, mounted NPCs, and
unit formations as lightweight data that renderers can draw.

This is a DATA layer — it doesn't draw anything itself. Renderers read
from these collections each frame.
"""

import math
import random
from typing import List, Dict, Optional, Tuple


# ================================================================
# PROJECTILES — arrows, bolts, stones, fire
# ================================================================

class Projectile:
    """A flying projectile (arrow, stone, etc.) with start/end position and travel time."""
    __slots__ = ('x', 'y', 'target_x', 'target_y', 'speed', 'life',
                 'max_life', 'kind', 'color', 'size', 'trail')

    def __init__(self, start_x: float, start_y: float,
                 target_x: float, target_y: float,
                 kind: str = "arrow", speed: float = 8.0):
        self.x = start_x
        self.y = start_y
        self.target_x = target_x
        self.target_y = target_y
        self.speed = speed
        dx = target_x - start_x
        dy = target_y - start_y
        dist = max(0.1, math.sqrt(dx * dx + dy * dy))
        self.life = dist / speed
        self.max_life = self.life
        self.kind = kind
        self.trail = []  # recent positions for trail effect

        # Visual properties by kind
        if kind == "arrow":
            self.color = (200, 180, 100)
            self.size = 2
        elif kind == "bolt":
            self.color = (180, 180, 200)
            self.size = 2
        elif kind == "stone":
            self.color = (140, 130, 120)
            self.size = 4
        elif kind == "fire":
            self.color = (240, 160, 40)
            self.size = 5
        elif kind == "boiling_oil":
            self.color = (80, 60, 20)
            self.size = 6
        else:
            self.color = (200, 200, 200)
            self.size = 2

    def update(self, dt: float) -> bool:
        """Update position. Returns False when arrived."""
        self.life -= dt
        if self.life <= 0:
            self.x = self.target_x
            self.y = self.target_y
            return False

        t = 1.0 - (self.life / self.max_life)
        self.trail.append((self.x, self.y))
        if len(self.trail) > 5:
            self.trail.pop(0)

        self.x = self.x + (self.target_x - self.x) * min(1, dt * self.speed)
        self.y = self.y + (self.target_y - self.y) * min(1, dt * self.speed)

        # Arc for stones and fire (parabolic trajectory)
        if self.kind in ("stone", "fire", "boiling_oil"):
            # Add vertical offset for arc (peaks at midpoint)
            arc = 4 * t * (1 - t) * 3.0  # max 3 tile arc height
            self.y -= arc * dt * 2

        return True


# ================================================================
# SIEGE ENGINE VISUALS
# ================================================================

class SiegeEngineVisual:
    """Visual representation of a siege engine on the battlefield."""

    def __init__(self, x: float, y: float, engine_type: str, owner: str):
        self.x = x
        self.y = y
        self.engine_type = engine_type
        self.owner = owner
        self.firing = False
        self.fire_timer = 0.0

        # Visual dimensions
        if engine_type == "battering_ram":
            self.width = 3
            self.height = 1
            self.color = (110, 80, 45)
        elif engine_type == "catapult":
            self.width = 2
            self.height = 2
            self.color = (120, 90, 50)
        elif engine_type == "trebuchet":
            self.width = 3
            self.height = 3
            self.color = (100, 75, 40)
        elif engine_type == "siege_tower":
            self.width = 2
            self.height = 3
            self.color = (130, 100, 60)
        else:
            self.width = 2
            self.height = 2
            self.color = (120, 90, 50)

    def fire_at(self, target_x: float, target_y: float) -> Optional[Projectile]:
        """Fire and create a projectile."""
        self.firing = True
        self.fire_timer = 0.5

        if self.engine_type == "catapult":
            return Projectile(self.x, self.y, target_x, target_y,
                            kind="stone", speed=5.0)
        elif self.engine_type == "trebuchet":
            return Projectile(self.x, self.y, target_x, target_y,
                            kind="stone", speed=4.0)
        elif self.engine_type == "battering_ram":
            return None  # ram doesn't launch projectiles
        return None


# ================================================================
# MOUNTED UNIT
# ================================================================

class MountedUnit:
    """Visual data for an NPC riding a mount."""

    def __init__(self, npc_name: str, mount_type: str = "horse"):
        self.npc_name = npc_name
        self.mount_type = mount_type
        self.charging = False
        self.speed_mult = 2.0 if mount_type == "war_horse" else 2.5

        if mount_type == "horse":
            self.mount_color = (140, 100, 60)
            self.mount_size = (3, 2)  # tiles wide, tall
        elif mount_type == "war_horse":
            self.mount_color = (100, 90, 80)
            self.mount_size = (3, 2)
        else:
            self.mount_color = (130, 95, 55)
            self.mount_size = (2, 2)


# ================================================================
# FORMATION
# ================================================================

class UnitFormation:
    """A group of NPCs in military formation."""

    def __init__(self, formation_type: str, center_x: float, center_y: float,
                 member_names: List[str], facing: Tuple[float, float] = (0, -1)):
        self.formation_type = formation_type  # "line", "wedge", "shield_wall", "circle"
        self.center_x = center_x
        self.center_y = center_y
        self.member_names = member_names
        self.facing = facing
        self.positions: Dict[str, Tuple[float, float]] = {}
        self._calculate_positions()

    def _calculate_positions(self):
        """Calculate position offsets for each member based on formation type."""
        n = len(self.member_names)
        if n == 0:
            return

        fx, fy = self.facing
        # Perpendicular direction
        px, py = -fy, fx

        if self.formation_type == "line":
            # Side by side, facing forward
            for i, name in enumerate(self.member_names):
                offset = (i - n // 2) * 1.5
                self.positions[name] = (
                    self.center_x + px * offset,
                    self.center_y + py * offset
                )

        elif self.formation_type == "wedge":
            # V-shape with leader at front
            for i, name in enumerate(self.member_names):
                if i == 0:
                    self.positions[name] = (self.center_x + fx * 2,
                                             self.center_y + fy * 2)
                else:
                    row = (i + 1) // 2
                    side = 1 if i % 2 == 1 else -1
                    self.positions[name] = (
                        self.center_x + fx * (2 - row) + px * side * row,
                        self.center_y + fy * (2 - row) + py * side * row
                    )

        elif self.formation_type == "shield_wall":
            # Two ranks: front shield, back spear
            front = n * 2 // 3
            for i, name in enumerate(self.member_names):
                if i < front:
                    offset = (i - front // 2) * 1.2
                    self.positions[name] = (
                        self.center_x + px * offset,
                        self.center_y + py * offset
                    )
                else:
                    offset = ((i - front) - (n - front) // 2) * 1.2
                    self.positions[name] = (
                        self.center_x + px * offset - fx * 1.5,
                        self.center_y + py * offset - fy * 1.5
                    )

        elif self.formation_type == "circle":
            # Defensive circle
            for i, name in enumerate(self.member_names):
                angle = 2 * math.pi * i / n
                r = max(2, n * 0.4)
                self.positions[name] = (
                    self.center_x + math.cos(angle) * r,
                    self.center_y + math.sin(angle) * r
                )


# ================================================================
# BATTLE VISUAL MANAGER
# ================================================================

class BattleVisuals:
    """Manages all visual battle elements. Renderers read from this each frame."""

    def __init__(self):
        self.projectiles: List[Projectile] = []
        self.siege_engines: List[SiegeEngineVisual] = []
        self.mounted_units: List[MountedUnit] = []
        self.formations: List[UnitFormation] = []
        self.impact_flashes: List[Dict] = []  # {x, y, timer, color}

    def update(self, dt: float):
        """Update all visual elements."""
        # Update projectiles
        alive = []
        for p in self.projectiles:
            if p.update(dt):
                alive.append(p)
            else:
                # Impact flash
                self.impact_flashes.append({
                    "x": p.target_x, "y": p.target_y,
                    "timer": 0.3, "color": p.color,
                    "size": p.size * 2,
                })
        self.projectiles = alive

        # Update siege engine fire timers
        for se in self.siege_engines:
            if se.fire_timer > 0:
                se.fire_timer -= dt
                if se.fire_timer <= 0:
                    se.firing = False

        # Update impact flashes
        remaining = []
        for flash in self.impact_flashes:
            flash["timer"] -= dt
            if flash["timer"] > 0:
                remaining.append(flash)
        self.impact_flashes = remaining

    def spawn_arrow_volley(self, from_x: float, from_y: float,
                           to_x: float, to_y: float, count: int = 5):
        """Spawn multiple arrows from archers toward target area."""
        for _ in range(count):
            tx = to_x + random.uniform(-2, 2)
            ty = to_y + random.uniform(-2, 2)
            fx = from_x + random.uniform(-1, 1)
            fy = from_y + random.uniform(-1, 1)
            self.projectiles.append(
                Projectile(fx, fy, tx, ty, kind="arrow",
                          speed=random.uniform(6, 10)))

    def spawn_siege_shot(self, engine: SiegeEngineVisual,
                          target_x: float, target_y: float):
        """Fire a siege engine and create its projectile."""
        proj = engine.fire_at(target_x, target_y)
        if proj:
            self.projectiles.append(proj)

    def create_formation(self, formation_type: str,
                          center_x: float, center_y: float,
                          members: List[str],
                          facing: Tuple[float, float] = (0, -1)) -> UnitFormation:
        """Create a unit formation."""
        f = UnitFormation(formation_type, center_x, center_y, members, facing)
        self.formations.append(f)
        return f

    def mount_npc(self, npc_name: str, mount_type: str = "horse") -> MountedUnit:
        """Register an NPC as mounted."""
        m = MountedUnit(npc_name, mount_type)
        self.mounted_units.append(m)
        return m

    def clear(self):
        """Clear all battle visuals."""
        self.projectiles.clear()
        self.siege_engines.clear()
        self.mounted_units.clear()
        self.formations.clear()
        self.impact_flashes.clear()
