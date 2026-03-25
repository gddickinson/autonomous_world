"""Projectile Manager — ranged projectile physics for combat.

Handles arrow/bolt/javelin flight, hit/miss detection against moving targets,
and integration with the combat visual system.

When a ranged attack is made, a CombatProjectile is created with start pos,
target pos, and speed. The projectile travels in a straight line each frame.
If the target moves >2 tiles before impact, the projectile misses.
On hit: deal damage. On miss: projectile lands at the original target position.

Visual feedback: emits events to battle_visuals for rendering.
"""

import math
import random
from typing import List, Dict, Optional, Any


# ================================================================
# PROJECTILE SPEEDS by weapon type (tiles per second)
# ================================================================

PROJECTILE_SPEEDS = {
    "bow": 15.0,
    "longbow": 16.0,
    "crossbow": 10.0,
    "sling": 12.0,
    "javelin": 10.0,
    "thrown_knife": 13.0,
    # Monster projectiles
    "boulder": 6.0,
    "breath": 12.0,
    "web": 8.0,
    "acid_spit": 10.0,
    "spines": 14.0,
    "life_drain": 18.0,
    "screech": 20.0,
    "tail_sting": 8.0,
    "spell": 12.0,
}

# Mapping from weapon type to visual kind (for battle_visuals.Projectile)
PROJECTILE_VISUAL_KIND = {
    "bow": "arrow",
    "longbow": "arrow",
    "crossbow": "bolt",
    "sling": "stone",
    "javelin": "arrow",
    "thrown_knife": "arrow",
    "boulder": "stone",
    "breath": "fire",
    "web": "stone",
    "acid_spit": "fire",
    "spines": "arrow",
    "life_drain": "fire",
    "screech": "fire",
    "tail_sting": "arrow",
    "spell": "fire",
}

# How far a target can move before the projectile counts as a miss (tiles)
MISS_THRESHOLD = 2.0


# ================================================================
# COMBAT PROJECTILE — tracks flight + hit/miss logic
# ================================================================

class CombatProjectile:
    """A projectile in flight with hit/miss detection against a target entity."""

    __slots__ = (
        'start_x', 'start_y', 'target_orig_x', 'target_orig_y',
        'x', 'y', 'speed', 'damage', 'damage_type',
        'shooter', 'target', 'weapon_type',
        'elapsed', 'flight_time', 'arrived',
        'dx_norm', 'dy_norm', 'distance',
    )

    def __init__(self, start_x: float, start_y: float,
                 target_x: float, target_y: float,
                 speed: float, damage: int, damage_type: str,
                 shooter, target, weapon_type: str = "bow"):
        self.start_x = start_x
        self.start_y = start_y
        self.target_orig_x = target_x
        self.target_orig_y = target_y
        self.x = start_x
        self.y = start_y
        self.speed = speed
        self.damage = damage
        self.damage_type = damage_type
        self.shooter = shooter
        self.target = target
        self.weapon_type = weapon_type
        self.elapsed = 0.0
        self.arrived = False

        # Pre-compute direction and flight time
        dx = target_x - start_x
        dy = target_y - start_y
        self.distance = max(0.1, math.sqrt(dx * dx + dy * dy))
        self.flight_time = self.distance / speed
        self.dx_norm = dx / self.distance
        self.dy_norm = dy / self.distance

    def update(self, dt: float) -> bool:
        """Advance projectile. Returns True when it has arrived at destination."""
        if self.arrived:
            return True

        self.elapsed += dt
        if self.elapsed >= self.flight_time:
            self.x = self.target_orig_x
            self.y = self.target_orig_y
            self.arrived = True
            return True

        # Straight-line interpolation
        t = self.elapsed / self.flight_time
        self.x = self.start_x + (self.target_orig_x - self.start_x) * t
        self.y = self.start_y + (self.target_orig_y - self.start_y) * t
        return False

    def check_hit(self) -> bool:
        """Check if the target is still close enough to the original aim point.

        If the target has moved more than MISS_THRESHOLD tiles from where we
        aimed, the projectile misses.
        """
        if self.target is None or not getattr(self.target, 'alive', True):
            return False

        tx = getattr(self.target, 'x', self.target_orig_x)
        ty = getattr(self.target, 'y', self.target_orig_y)
        dx = tx - self.target_orig_x
        dy = ty - self.target_orig_y
        moved = math.sqrt(dx * dx + dy * dy)
        return moved <= MISS_THRESHOLD


# ================================================================
# HIT RESULT
# ================================================================

class HitResult:
    """Result of a projectile arriving at its destination."""

    __slots__ = ('hit', 'damage', 'damage_type', 'shooter', 'target',
                 'x', 'y', 'weapon_type', 'message')

    def __init__(self, hit: bool, damage: int, damage_type: str,
                 shooter, target, x: float, y: float,
                 weapon_type: str, message: str):
        self.hit = hit
        self.damage = damage
        self.damage_type = damage_type
        self.shooter = shooter
        self.target = target
        self.x = x
        self.y = y
        self.weapon_type = weapon_type
        self.message = message


# ================================================================
# PROJECTILE MANAGER
# ================================================================

class ProjectileManager:
    """Manages all in-flight combat projectiles.

    Each frame: update positions, check arrivals, resolve hits/misses,
    and emit visual events.
    """

    def __init__(self):
        self.active: List[CombatProjectile] = []

    def spawn(self, start_x: float, start_y: float,
              target, damage: int, damage_type: str = "pierce",
              shooter=None, weapon_type: str = "bow") -> CombatProjectile:
        """Create and register a new projectile aimed at target entity."""
        speed = PROJECTILE_SPEEDS.get(weapon_type, 12.0)
        tx = getattr(target, 'x', 0.0)
        ty = getattr(target, 'y', 0.0)
        proj = CombatProjectile(
            start_x, start_y, tx, ty,
            speed, damage, damage_type,
            shooter, target, weapon_type,
        )
        self.active.append(proj)

        # Emit visual projectile for rendering
        self._emit_visual(proj)
        return proj

    def update(self, dt: float) -> List[HitResult]:
        """Update all projectiles. Returns list of HitResults for arrivals."""
        results: List[HitResult] = []
        still_flying: List[CombatProjectile] = []

        for proj in self.active:
            arrived = proj.update(dt)
            if arrived:
                result = self._resolve(proj)
                results.append(result)
            else:
                still_flying.append(proj)

        self.active = still_flying
        return results

    def _resolve(self, proj: CombatProjectile) -> HitResult:
        """Resolve a projectile that has arrived: hit or miss."""
        hit = proj.check_hit()
        shooter_name = getattr(proj.shooter, 'name',
                               getattr(proj.shooter, 'kind', 'someone'))
        target_name = getattr(proj.target, 'name',
                              getattr(proj.target, 'kind', 'target'))

        if hit and proj.target and getattr(proj.target, 'alive', True):
            # Apply damage through body damage system if available
            actual = self._apply_damage(proj)
            msg = (f"{shooter_name}'s {proj.weapon_type} hits "
                   f"{target_name} for {actual} {proj.damage_type} damage!")

            # Emit damage visual
            from game.systems.combat import _emit_damage
            _emit_damage(proj.target, actual,
                         is_kill=not getattr(proj.target, 'alive', True))

            return HitResult(
                hit=True, damage=actual, damage_type=proj.damage_type,
                shooter=proj.shooter, target=proj.target,
                x=proj.x, y=proj.y,
                weapon_type=proj.weapon_type, message=msg,
            )
        else:
            msg = (f"{shooter_name}'s {proj.weapon_type} misses "
                   f"{target_name}!")
            return HitResult(
                hit=False, damage=0, damage_type=proj.damage_type,
                shooter=proj.shooter, target=proj.target,
                x=proj.target_orig_x, y=proj.target_orig_y,
                weapon_type=proj.weapon_type, message=msg,
            )

    def _apply_damage(self, proj: CombatProjectile) -> int:
        """Apply projectile damage to the target, using body damage if available."""
        target = proj.target
        damage = proj.damage

        if getattr(target, 'body', None) is not None:
            from game.systems.body_damage import BodyDamageSystem
            bds = BodyDamageSystem()
            return bds.apply_damage(target, damage, damage_type=proj.damage_type)
        else:
            defense = getattr(target, 'npc_defense', 0)
            actual = max(1, damage - defense)
            target._last_attacker = proj.shooter
            if hasattr(target, 'take_damage'):
                target.take_damage(actual)
            return actual

    def _emit_visual(self, proj: CombatProjectile):
        """Emit a visual projectile to battle_visuals if available."""
        try:
            from game.systems.battle_visuals import Projectile as VisualProjectile
            kind = PROJECTILE_VISUAL_KIND.get(proj.weapon_type, "arrow")
            vp = VisualProjectile(
                proj.start_x, proj.start_y,
                proj.target_orig_x, proj.target_orig_y,
                kind=kind, speed=proj.speed,
            )
            # Store on the combat projectile so renderers can find it
            proj._visual = vp
        except ImportError:
            pass

    @property
    def count(self) -> int:
        """Number of active projectiles."""
        return len(self.active)

    def clear(self):
        """Remove all active projectiles."""
        self.active.clear()
