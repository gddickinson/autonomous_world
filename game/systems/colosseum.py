"""Colosseum Battle System — tactical arena combat with AI behaviors.

Combat AI uses:
- Boids-inspired steering (separation, cohesion, alignment) for formations
- Influence-map threat assessment for positioning
- Role-based behavior (tanks front, archers kite, healers support)
- Focus-fire target selection (prioritize weak/dangerous targets)
- Morale system with bravery-scaled fleeing
- Flanking mechanics (rear attacks deal bonus damage)
- Weapon differentiation (reach, speed, damage type)
- D20 attack rolls with criticals

References:
- Craig Reynolds' Boids (1986) for flocking/formation
- Influence maps for RTS spatial tactics
- D&D 5e combat mechanics for attack resolution
"""

import random
import math
import time
from typing import List, Dict, Optional, Tuple
from game.settings import ARENA_SAND, COURTYARD, IRON_GATE, FLOOR, WALL
import numpy as np


# ================================================================
# ARENA TERRAIN — elevation, cover, obstacles
# ================================================================

class ArenaTerrain:
    """Terrain map for the arena with elevation, cover, and obstacles.

    Features:
    - Elevation (0-3): low ground, flat, raised, high ground
      Higher elevation gives ranged bonus and melee defense
    - Cover (0-2): none, half cover, full cover
      Blocks missiles and grants defense bonus
    - Obstacles: impassable tiles (walls, pillars, barricades)
    - Ditches: low elevation + movement penalty
    - Water/mud: movement slow zones
    """

    # Terrain feature types
    FLAT = 0
    RAISED = 1        # slight elevation (stairs, platform)
    HIGH_GROUND = 2   # significant elevation (hill, tower)
    DITCH = -1        # below ground level (trench, pit)

    COVER_NONE = 0
    COVER_HALF = 1    # low wall, barrel, hedge
    COVER_FULL = 2    # high wall, pillar (blocks LoS)

    def __init__(self, width: int, height: int, center_x: float, center_y: float):
        self.width = width
        self.height = height
        self.cx = center_x
        self.cy = center_y
        # Per-tile arrays
        self.elevation = np.zeros((height, width), dtype=np.int8)
        self.cover = np.zeros((height, width), dtype=np.int8)
        self.obstacle = np.zeros((height, width), dtype=np.bool_)
        self.mud = np.zeros((height, width), dtype=np.bool_)
        self.name = "flat"

    def world_to_grid(self, wx: float, wy: float) -> Tuple[int, int]:
        gx = int(wx - self.cx + self.width // 2)
        gy = int(wy - self.cy + self.height // 2)
        return max(0, min(self.width - 1, gx)), max(0, min(self.height - 1, gy))

    def get_elevation(self, wx: float, wy: float) -> int:
        gx, gy = self.world_to_grid(wx, wy)
        return int(self.elevation[gy, gx])

    def get_cover(self, wx: float, wy: float) -> int:
        gx, gy = self.world_to_grid(wx, wy)
        return int(self.cover[gy, gx])

    def is_obstacle(self, wx: float, wy: float) -> bool:
        gx, gy = self.world_to_grid(wx, wy)
        return bool(self.obstacle[gy, gx])

    def is_mud(self, wx: float, wy: float) -> bool:
        gx, gy = self.world_to_grid(wx, wy)
        return bool(self.mud[gy, gx])

    def has_line_of_sight(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        """Check if there's clear line of sight between two points.

        Full cover blocks LoS. High obstacles block LoS.
        Uses Bresenham-style ray march.
        """
        steps = max(1, int(math.sqrt((x2-x1)**2 + (y2-y1)**2) * 2))
        for i in range(1, steps):
            t = i / steps
            mx = x1 + (x2 - x1) * t
            my = y1 + (y2 - y1) * t
            gx, gy = self.world_to_grid(mx, my)
            if self.cover[gy, gx] >= self.COVER_FULL:
                return False
            if self.obstacle[gy, gx]:
                return False
        return True

    def movement_cost(self, wx: float, wy: float) -> float:
        """Movement speed multiplier at position. <1 = slow."""
        gx, gy = self.world_to_grid(wx, wy)
        if self.obstacle[gy, gx]:
            return 0.0  # impassable
        cost = 1.0
        elev = self.elevation[gy, gx]
        if elev == self.DITCH:
            cost *= 0.6  # ditches are slow
        if self.mud[gy, gx]:
            cost *= 0.5  # mud halves speed
        return cost

    def elevation_advantage(self, attacker_x: float, attacker_y: float,
                             target_x: float, target_y: float) -> float:
        """Returns damage multiplier from elevation difference.

        Higher ground = bonus, lower ground = penalty.
        """
        a_elev = self.get_elevation(attacker_x, attacker_y)
        t_elev = self.get_elevation(target_x, target_y)
        diff = a_elev - t_elev
        if diff > 0:
            return 1.0 + diff * 0.15  # +15% per elevation level
        elif diff < 0:
            return max(0.7, 1.0 + diff * 0.1)  # -10% per level below
        return 1.0

    def ranged_bonus(self, shooter_x: float, shooter_y: float) -> float:
        """Bonus to ranged attack range from elevation."""
        elev = self.get_elevation(shooter_x, shooter_y)
        return 1.0 + max(0, elev) * 0.2  # +20% range per elevation

    def cover_defense_bonus(self, defender_x: float, defender_y: float) -> int:
        """AC bonus from cover at position."""
        cov = self.get_cover(defender_x, defender_y)
        return cov * 2  # +2 AC for half cover, +4 for full cover


# ================================================================
# PRESET ARENA LAYOUTS
# ================================================================

def make_arena_flat(cx: float, cy: float, radius: int = 20) -> ArenaTerrain:
    """Standard flat arena — no terrain features."""
    size = radius * 2
    t = ArenaTerrain(size, size, cx, cy)
    t.name = "flat"
    return t


def make_arena_hills(cx: float, cy: float, radius: int = 20) -> ArenaTerrain:
    """Arena with two hills on opposite sides — elevation matters."""
    size = radius * 2
    t = ArenaTerrain(size, size, cx, cy)
    t.name = "hills"
    mid = size // 2
    # Hill on left (team 0 side)
    for y in range(mid - 5, mid + 6):
        for x in range(3, 10):
            t.elevation[y, x] = t.RAISED
    for y in range(mid - 3, mid + 4):
        for x in range(5, 8):
            t.elevation[y, x] = t.HIGH_GROUND
    # Hill on right (team 1 side)
    for y in range(mid - 5, mid + 6):
        for x in range(size - 10, size - 3):
            t.elevation[y, x] = t.RAISED
    for y in range(mid - 3, mid + 4):
        for x in range(size - 8, size - 5):
            t.elevation[y, x] = t.HIGH_GROUND
    return t


def make_arena_trenches(cx: float, cy: float, radius: int = 20) -> ArenaTerrain:
    """Arena with defensive trenches across the middle."""
    size = radius * 2
    t = ArenaTerrain(size, size, cx, cy)
    t.name = "trenches"
    mid_x = size // 2
    mid_y = size // 2
    # Two trenches running north-south
    for y in range(5, size - 5):
        for dx in [-3, -2, 3, 4]:
            x = mid_x + dx
            if 0 <= x < size:
                t.elevation[y, x] = t.DITCH
    return t


def make_arena_obstacles(cx: float, cy: float, radius: int = 20) -> ArenaTerrain:
    """Arena with scattered cover — barricades, pillars, walls."""
    size = radius * 2
    t = ArenaTerrain(size, size, cx, cy)
    t.name = "obstacles"
    rng = random.Random(42)
    mid = size // 2
    # Scatter half-cover barricades
    for _ in range(12):
        bx = rng.randint(5, size - 6)
        by = rng.randint(5, size - 6)
        # Horizontal or vertical barricade (3 tiles long)
        if rng.random() < 0.5:
            for dx in range(3):
                if 0 <= bx + dx < size:
                    t.cover[by, bx + dx] = t.COVER_HALF
        else:
            for dy in range(3):
                if 0 <= by + dy < size:
                    t.cover[by + dy, bx] = t.COVER_HALF
    # A few full-cover pillars
    for _ in range(4):
        px = rng.randint(8, size - 9)
        py = rng.randint(8, size - 9)
        t.cover[py, px] = t.COVER_FULL
        t.obstacle[py, px] = True
    return t


def make_arena_mud(cx: float, cy: float, radius: int = 20) -> ArenaTerrain:
    """Arena with a muddy center — slows movement through the middle."""
    size = radius * 2
    t = ArenaTerrain(size, size, cx, cy)
    t.name = "mud_pit"
    mid = size // 2
    # Circular mud pit in center
    for y in range(size):
        for x in range(size):
            dx, dy = x - mid, y - mid
            if dx * dx + dy * dy < 64:  # radius ~8
                t.mud[y, x] = True
    return t


def make_arena_fortress(cx: float, cy: float, radius: int = 20) -> ArenaTerrain:
    """One side has a fortified position — walls, elevation, cover."""
    size = radius * 2
    t = ArenaTerrain(size, size, cx, cy)
    t.name = "fortress"
    # Right side (team 1) gets a fortress
    fort_x = size - 12
    # Raised platform
    for y in range(size // 2 - 6, size // 2 + 7):
        for x in range(fort_x, size - 3):
            t.elevation[y, x] = t.RAISED
    # Wall line with gaps
    for y in range(size // 2 - 6, size // 2 + 7):
        t.cover[y, fort_x] = t.COVER_FULL
        t.obstacle[y, fort_x] = True
    # Gaps for entry
    t.cover[size // 2, fort_x] = t.COVER_NONE
    t.obstacle[size // 2, fort_x] = False
    t.cover[size // 2 - 4, fort_x] = t.COVER_NONE
    t.obstacle[size // 2 - 4, fort_x] = False
    t.cover[size // 2 + 4, fort_x] = t.COVER_NONE
    t.obstacle[size // 2 + 4, fort_x] = False
    # Ditch in front of fortress
    for y in range(size // 2 - 7, size // 2 + 8):
        if 0 <= fort_x - 2 < size:
            t.elevation[y, fort_x - 2] = t.DITCH
            t.elevation[y, fort_x - 1] = t.DITCH
    return t


ARENA_LAYOUTS = {
    "flat": make_arena_flat,
    "hills": make_arena_hills,
    "trenches": make_arena_trenches,
    "obstacles": make_arena_obstacles,
    "mud_pit": make_arena_mud,
    "fortress": make_arena_fortress,
}


# ================================================================
# WEAPON PROPERTIES — reach, speed, damage type, range
# ================================================================

WEAPON_PROPS = {
    # name: (reach, attack_speed, damage_type, is_ranged, optimal_range)
    "Wooden Sword":   (1.5, 1.0, "slash",  False, 1.5),
    "Iron Sword":     (1.5, 1.0, "slash",  False, 1.5),
    "Steel Sword":    (1.5, 1.0, "slash",  False, 1.5),
    "Staff":          (2.0, 0.8, "blunt",  False, 2.0),
    "Hunting Bow":    (1.0, 1.2, "pierce", True,  8.0),
    "Arrows":         (1.0, 1.2, "pierce", True,  8.0),
    "Spear":          (2.5, 0.7, "pierce", False, 2.5),
    "Dagger":         (1.0, 1.5, "pierce", False, 1.0),
    "Mace":           (1.5, 0.8, "blunt",  False, 1.5),
    "Axe":            (1.5, 0.9, "slash",  False, 1.5),
    "Crossbow":       (1.0, 0.6, "pierce", True,  10.0),
    "Sling":          (1.0, 1.0, "blunt",  True,  6.0),
    "Javelin":        (2.0, 0.5, "pierce", True,  5.0),
}

# Role classification by class
ROLE_MAP = {
    "Fighter":    "tank",
    "Paladin":    "tank",
    "Barbarian":  "berserker",
    "Ranger":     "ranged",
    "Rogue":      "flanker",
    "Wizard":     "caster",
    "Sorcerer":   "caster",
    "Warlock":    "caster",
    "Cleric":     "healer",
    "Druid":      "healer",
    "Bard":       "support",
    "Monk":       "flanker",
}

# ================================================================
# COMBATANT — wrapper with tactical state
# ================================================================

class Combatant:
    """Entity participating in a colosseum fight with tactical AI state."""
    __slots__ = ('entity', 'team', 'is_npc', 'is_creature', 'name',
                 'hp_start', 'damage_dealt', 'kills', 'role',
                 'weapon_reach', 'weapon_speed', 'weapon_type', 'is_ranged',
                 'optimal_range', 'morale', 'fleeing', 'facing_angle',
                 'steer_vx', 'steer_vy', 'engagement_target',
                 'last_attack_time', 'dodge_cooldown',
                 '_formation', '_troop_type', '_troop_team',
                 '_is_commander', '_command_formation', '_is_siege_engine')

    def __init__(self, entity, team: int):
        self.entity = entity
        self.team = team
        self.is_npc = hasattr(entity, 'char_class')
        self.is_creature = hasattr(entity, 'kind') and not self.is_npc
        self.name = getattr(entity, 'name', '') or getattr(entity, 'kind', 'unknown')
        self.hp_start = entity.hp
        self.damage_dealt = 0
        self.kills = 0
        self.morale = 100.0
        self.fleeing = False
        self.facing_angle = 0.0
        self.steer_vx = 0.0
        self.steer_vy = 0.0
        self.engagement_target = None
        self.last_attack_time = 0.0
        self.dodge_cooldown = 0.0

        # Determine role and weapon properties
        cc = getattr(entity, 'char_class', '')
        self.role = ROLE_MAP.get(cc, "melee")
        if self.is_creature:
            self.role = "beast"

        # Weapon properties
        weapon = getattr(entity, 'weapon', None)
        weapon_name = getattr(weapon, 'name', '') if weapon else ''
        props = WEAPON_PROPS.get(weapon_name, (1.5, 1.0, "blunt", False, 1.5))
        self.weapon_reach = props[0]
        self.weapon_speed = props[1]
        self.weapon_type = props[2]
        self.is_ranged = props[3]
        self.optimal_range = props[4]

        # Troop/commander/siege state
        self._formation = None
        self._troop_type = ""
        self._troop_team = -1
        self._is_commander = False
        self._command_formation = None
        self._is_siege_engine = False

        # Ranged classes get ranged behavior even without explicit bow
        if cc in ("Ranger",) and not self.is_ranged:
            self.is_ranged = True
            self.optimal_range = 7.0

    @property
    def hp_pct(self) -> float:
        e = self.entity
        return e.hp / max(1, self.hp_start)

    @property
    def threat_score(self) -> float:
        """How dangerous this combatant is (for target priority)."""
        e = self.entity
        if not e.alive:
            return 0.0
        dmg = getattr(e, 'npc_attack_damage', getattr(e, 'damage', 5))
        return dmg * self.hp_pct

    @property
    def bravery(self) -> float:
        return getattr(self.entity, 'bravery', 0.5)


# ================================================================
# BATTLE RESULT
# ================================================================

class BattleResult:
    """Outcome of a colosseum battle."""
    def __init__(self):
        self.winner_team = -1
        self.duration = 0.0
        self.rounds = 0
        self.combatants: List[Combatant] = []
        self.kill_log: List[str] = []
        self.summary = ""

    def get_survivors(self, team: int = None) -> list:
        if team is not None:
            return [c for c in self.combatants if c.entity.alive and c.team == team]
        return [c for c in self.combatants if c.entity.alive]

    def format_report(self) -> str:
        lines = ["=== BATTLE REPORT ==="]
        lines.append(f"Duration: {self.duration:.1f}s, Rounds: {self.rounds}")
        lines.append(f"Winner: Team {self.winner_team}")
        lines.append("")
        for team_id in sorted(set(c.team for c in self.combatants)):
            team_members = [c for c in self.combatants if c.team == team_id]
            alive = sum(1 for c in team_members if c.entity.alive)
            lines.append(f"Team {team_id} ({alive}/{len(team_members)} alive):")
            for c in team_members:
                status = "ALIVE" if c.entity.alive else "DEAD"
                if c.fleeing:
                    status = "FLED"
                hp_pct = c.hp_pct * 100
                lines.append(f"  {c.name} [{c.role}]: {status} "
                             f"HP:{c.entity.hp}/{c.hp_start} ({hp_pct:.0f}%) "
                             f"Dmg:{c.damage_dealt} Kills:{c.kills} "
                             f"Morale:{c.morale:.0f}")
        lines.append("")
        if self.kill_log:
            lines.append("Battle Log (last 15):")
            for k in self.kill_log[-15:]:
                lines.append(f"  {k}")
        lines.append(f"\n{self.summary}")
        return "\n".join(lines)


# ================================================================
# COLOSSEUM MANAGER — tactical battle engine
# ================================================================

class ColosseumManager:
    """Manages battles with tactical AI, formations, and morale."""

    IDLE = "idle"
    PREPARING = "preparing"
    FIGHTING = "fighting"
    CONCLUDED = "concluded"

    def __init__(self, structure=None):
        self.structure = structure
        self.state = self.IDLE
        self.combatants: List[Combatant] = []
        self.battle_timer = 0.0
        self.max_battle_time = 180.0
        self.round_timer = 0.0
        self.round_interval = 0.5
        self.rounds = 0
        self.result: Optional[BattleResult] = None
        self.gates_locked = False
        self.battle_log: List[str] = []
        self.arena_center = (0.0, 0.0)
        self.arena_radius = 15.0
        self.terrain: Optional[ArenaTerrain] = None  # set via set_terrain()

    def set_terrain(self, layout: str = "flat"):
        """Set arena terrain layout. Options: flat, hills, trenches, obstacles, mud_pit, fortress"""
        cx, cy = self.arena_center
        builder = ARENA_LAYOUTS.get(layout, make_arena_flat)
        self.terrain = builder(cx, cy, int(self.arena_radius))
        self._log(f"Arena terrain: {layout}")

    def set_structure(self, structure):
        self.structure = structure
        self.arena_center = (float(structure.x), float(structure.y))
        self.arena_radius = min(structure.radius, 25.0)

    # ------------------------------------------------------------------
    # SPAWNING
    # ------------------------------------------------------------------

    def spawn_npc(self, name: str, char_class: str, race: str = "Human",
                  level: int = 3, team: int = 0,
                  weapon: str = "", armor: str = "") -> Optional[Combatant]:
        from game.core.npc import NPC
        from game.core.items import make_item

        cx, cy = self.arena_center
        # Position teams on opposite sides
        side = -1 if team == 0 else 1
        x = cx + side * random.uniform(5, self.arena_radius * 0.5)
        y = cy + random.uniform(-self.arena_radius * 0.3, self.arena_radius * 0.3)

        npc = NPC(x, y, name, char_class, char_class=char_class,
                  race=race, level=level)
        npc.home_x = x
        npc.home_y = y

        if weapon:
            item = make_item(weapon)
            if item:
                npc.npc_add_item(item)
                npc.weapon = item
                npc.npc_attack_damage = max(npc.npc_attack_damage,
                                             4 + getattr(item, 'damage', 0) // 3)
        if armor:
            item = make_item(armor)
            if item:
                npc.npc_add_item(item)
                npc.npc_defense += getattr(item, 'defense', 0) // 2
                npc.armor_class += getattr(item, 'defense', 0) // 3

        c = Combatant(npc, team)
        self.combatants.append(c)
        return c

    def spawn_creature(self, kind: str, team: int = 1) -> Optional[Combatant]:
        from game.core.creature import Creature

        cx, cy = self.arena_center
        side = -1 if team == 0 else 1
        x = cx + side * random.uniform(5, self.arena_radius * 0.5)
        y = cy + random.uniform(-self.arena_radius * 0.3, self.arena_radius * 0.3)

        creature = Creature(x, y, kind)
        creature.home_x = x
        creature.home_y = y
        creature.passive = False

        c = Combatant(creature, team)
        self.combatants.append(c)
        return c

    # ------------------------------------------------------------------
    # BATTLE CONTROL
    # ------------------------------------------------------------------

    def prepare_battle(self):
        if not self.combatants:
            return
        self.state = self.PREPARING
        self.battle_log = []
        self.rounds = 0
        self.battle_timer = 0.0

        # Ensure all combatants have body part system
        from game.systems.body_damage import ensure_body
        for c in self.combatants:
            e = c.entity
            ensure_body(e)
            if hasattr(e, 'combat_target'):
                e.combat_target = None
            if hasattr(e, 'current_action'):
                e.current_action = ""
            if hasattr(e, 'state'):
                e.state = "idle"
        self._log("Battle prepared. Combatants in position.")

    def start_battle(self):
        if self.state != self.PREPARING:
            self.prepare_battle()
        self.state = self.FIGHTING
        self.gates_locked = True
        self.battle_timer = 0.0
        self._log("FIGHT! Gates locked!")

    def update(self, dt: float):
        if self.state != self.FIGHTING:
            return
        self.battle_timer += dt
        self.round_timer += dt

        if self.round_timer >= self.round_interval:
            self.round_timer = 0.0
            self.rounds += 1
            self._process_round()

        if self._check_battle_end():
            self._conclude_battle()
        elif self.battle_timer >= self.max_battle_time:
            self._log("Time limit!")
            self._conclude_battle()

    # ------------------------------------------------------------------
    # TACTICAL COMBAT ROUND
    # ------------------------------------------------------------------

    def _process_round(self):
        """Process one tactical combat round with AI behaviors."""
        alive = [c for c in self.combatants if c.entity.alive and not c.fleeing]
        all_alive = [c for c in self.combatants if c.entity.alive]

        # Commander rally (every 5 rounds)
        if self.rounds % 5 == 0:
            for c in alive:
                if getattr(c, '_is_commander', False):
                    allies = [a for a in alive if a.team == c.team]
                    for ally in allies:
                        if ally.morale < 50:
                            ally.morale = min(100, ally.morale + 10)
                            if ally.fleeing and random.random() < 0.3:
                                ally.fleeing = False
                                self._log(f"{c.name} rallies {ally.name}!")

        # Siege engine area damage (every 3 rounds) — uses real damage system
        if self.rounds % 3 == 0:
            from game.systems.body_damage import BodyDamageSystem
            _bds = BodyDamageSystem()
            for c in alive:
                if getattr(c, '_is_siege_engine', False):
                    enemies = [e for e in all_alive if e.team != c.team and e.entity.alive]
                    if enemies:
                        target = random.choice(enemies)
                        blast_radius = 3.0
                        dmg = getattr(c.entity, 'npc_attack_damage', 20)
                        hit_count = 0
                        for e in enemies:
                            if self._dist(e.entity, target.entity) <= blast_radius:
                                actual = _bds.apply_damage(
                                    e.entity, dmg, damage_type="blunt",
                                    timestamp=self.battle_timer)
                                e.morale -= 8
                                c.damage_dealt += actual
                                hit_count += 1
                                if not e.entity.alive or e.entity.hp <= 0:
                                    e.entity.alive = False
                                    c.kills += 1
                                    self._log(f"{c.name} DEMOLISHES {e.name}!")
                        if hit_count > 0:
                            self._log(f"{c.name} fires! Hits {hit_count} targets!")

        for c in alive:
            # 1. Update morale
            self._update_morale(c, all_alive)

            # 2. Check flee condition
            if self._should_flee(c, all_alive):
                c.fleeing = True
                self._log(f"{c.name} breaks and FLEES! (morale:{c.morale:.0f})")
                self._do_flee(c)
                continue

            # 3. Select target (tactical)
            target = self._select_target(c, all_alive)
            if not target:
                continue
            c.entity.combat_target = target.entity
            c.engagement_target = target

            # 4. Role-based positioning & movement
            self._tactical_move(c, target, all_alive)

            # 5. Attack if in range
            dist = self._dist(c.entity, target.entity)
            attack_range = c.optimal_range if c.is_ranged else c.weapon_reach

            if dist <= attack_range:
                # Check attack speed cooldown
                if self.battle_timer - c.last_attack_time >= (1.0 / c.weapon_speed):
                    self._do_attack(c, target, all_alive)
                    c.last_attack_time = self.battle_timer

        # Update dodge cooldowns
        for c in all_alive:
            c.dodge_cooldown = max(0, c.dodge_cooldown - self.round_interval)

    # ------------------------------------------------------------------
    # MORALE SYSTEM
    # ------------------------------------------------------------------

    def _update_morale(self, c: Combatant, all_alive: list):
        """Update morale based on battle conditions."""
        # Base morale recovery
        c.morale = min(100, c.morale + 0.5)

        # HP-based morale loss
        if c.hp_pct < 0.5:
            c.morale -= 2.0
        if c.hp_pct < 0.25:
            c.morale -= 5.0

        # Team strength comparison
        allies = [x for x in all_alive if x.team == c.team and x.entity.alive]
        enemies = [x for x in all_alive if x.team != c.team and x.entity.alive]
        if enemies:
            ratio = len(allies) / max(1, len(enemies))
            if ratio < 0.5:
                c.morale -= 3.0  # outnumbered badly
            elif ratio < 0.75:
                c.morale -= 1.0

        # Seeing allies die drops morale
        dead_allies = [x for x in self.combatants if x.team == c.team and not x.entity.alive]
        if dead_allies:
            c.morale -= len(dead_allies) * 1.5

        # Berserkers get morale boost when hurt
        if c.role == "berserker" and c.hp_pct < 0.5:
            c.morale += 5.0  # rage

        c.morale = max(0, min(100, c.morale))

    def _should_flee(self, c: Combatant, all_alive: list) -> bool:
        """Check if combatant should flee based on morale and bravery."""
        if c.role == "berserker":
            return False  # barbarians never flee

        threshold = 30.0 * c.bravery  # brave = lower threshold
        if c.morale < threshold:
            return True

        # Very low HP with no healer nearby
        if c.hp_pct < 0.15 and c.role != "tank":
            allies = [x for x in all_alive if x.team == c.team and x.role == "healer" and x.entity.alive]
            if not allies:
                return True

        return False

    def _do_flee(self, c: Combatant):
        """Move fleeing combatant away from enemies."""
        enemies = [x for x in self.combatants if x.team != c.team and x.entity.alive]
        if not enemies:
            return
        # Average enemy position
        avg_x = sum(e.entity.x for e in enemies) / len(enemies)
        avg_y = sum(e.entity.y for e in enemies) / len(enemies)
        # Move away
        dx = c.entity.x - avg_x
        dy = c.entity.y - avg_y
        d = math.sqrt(dx * dx + dy * dy) or 1
        speed = getattr(c.entity, 'speed', 2.0) * 1.3  # flee faster
        c.entity.x += (dx / d) * speed * self.round_interval
        c.entity.y += (dy / d) * speed * self.round_interval
        # Clamp to arena
        self._clamp_to_arena(c)

    # ------------------------------------------------------------------
    # TARGET SELECTION — focus fire, priority targeting
    # ------------------------------------------------------------------

    def _select_target(self, c: Combatant, all_alive: list) -> Optional[Combatant]:
        """Tactical target selection based on role and threat."""
        enemies = [x for x in all_alive if x.team != c.team and x.entity.alive
                   and not x.fleeing]
        if not enemies:
            # Target fleeing enemies
            enemies = [x for x in all_alive if x.team != c.team and x.entity.alive]
        if not enemies:
            return None

        # Score each target
        scores = []
        for e in enemies:
            score = 0.0
            dist = self._dist(c.entity, e.entity)

            # Focus fire: prefer low HP targets (finish them off)
            score += (1.0 - e.hp_pct) * 30.0

            # Distance penalty (prefer closer targets)
            score -= dist * 2.0

            # Role-based priority
            if c.role in ("flanker", "ranged", "caster"):
                # Assassins/ranged prioritize healers and casters
                if e.role in ("healer", "caster", "support"):
                    score += 25.0
            elif c.role == "tank":
                # Tanks engage the biggest threats
                score += e.threat_score * 2.0
            elif c.role == "berserker":
                # Berserkers attack nearest
                score -= dist * 5.0

            # Flanking opportunity: prefer targets already engaged with allies
            if e.engagement_target and e.engagement_target.team == c.team:
                score += 15.0  # target is distracted

            # Avoid targeting fleeing enemies when others still fight
            if e.fleeing:
                score -= 20.0

            scores.append((e, score))

        scores.sort(key=lambda x: -x[1])
        return scores[0][0]

    # ------------------------------------------------------------------
    # TACTICAL MOVEMENT — role-based positioning with steering
    # ------------------------------------------------------------------

    def _tactical_move(self, c: Combatant, target: Combatant,
                       all_alive: list):
        """Move with tactical awareness: kiting, flanking, formation."""
        from game.systems.body_damage import BodyDamageSystem
        _bds = BodyDamageSystem()

        e = c.entity
        dist = self._dist(e, target.entity)
        base_speed = getattr(e, 'speed', 2.0)

        # Wounded entities move slower (body damage speed modifier)
        speed_mod = _bds.get_speed_modifier(e)
        speed = base_speed * speed_mod * self.round_interval

        # Calculate base movement vector toward target
        dx = target.entity.x - e.x
        dy = target.entity.y - e.y
        d = math.sqrt(dx * dx + dy * dy) or 1
        move_x = dx / d
        move_y = dy / d

        # --- ROLE-BASED BEHAVIOR ---
        if c.is_ranged and c.role in ("ranged", "caster"):
            # KITING: ranged units maintain optimal distance
            if dist < c.optimal_range * 0.6:
                # Too close! Retreat
                move_x = -move_x
                move_y = -move_y
                speed *= 1.2  # urgent retreat
                self._log_rare(f"{c.name} kites back from {target.name}")
            elif dist > c.optimal_range * 1.2:
                # Too far, close in slightly
                speed *= 0.7
            else:
                # At optimal range, strafe sideways
                move_x, move_y = -move_y * 0.5, move_x * 0.5
                speed *= 0.5

        elif c.role == "flanker":
            # FLANKING: rogues/monks circle to attack from behind
            if dist > c.weapon_reach * 1.5:
                # Approach at an angle (not straight on)
                perp_x, perp_y = -move_y, move_x
                # Alternate direction based on position
                side = 1 if (e.x + e.y) % 2 > 1 else -1
                move_x = move_x * 0.6 + perp_x * 0.4 * side
                move_y = move_y * 0.6 + perp_y * 0.4 * side
                # Normalize
                nm = math.sqrt(move_x * move_x + move_y * move_y) or 1
                move_x /= nm
                move_y /= nm

        elif c.role == "tank":
            # TANKS: move to intercept threats to allies
            allies = [a for a in all_alive if a.team == c.team and a.entity.alive
                      and a.role in ("healer", "caster", "ranged", "support")]
            if allies:
                # Position between nearest threatened ally and their attacker
                for ally in allies:
                    if ally.engagement_target and ally.engagement_target.team != c.team:
                        threat = ally.engagement_target
                        td = self._dist(e, threat.entity)
                        if td < 8.0:
                            # Intercept the threat
                            move_x = (threat.entity.x - e.x)
                            move_y = (threat.entity.y - e.y)
                            nm = math.sqrt(move_x**2 + move_y**2) or 1
                            move_x /= nm
                            move_y /= nm
                            target = threat  # re-target to the intercepted enemy
                            break

        elif c.role == "berserker":
            # BERSERKERS: charge straight in, faster when wounded
            if c.hp_pct < 0.5:
                speed *= 1.3  # rage speed

        elif c.role == "healer":
            # HEALERS: stay behind tanks, move toward wounded allies
            wounded = [a for a in all_alive if a.team == c.team and a.entity.alive
                       and a.hp_pct < 0.6 and a is not c]
            if wounded:
                # Move toward most wounded ally instead of enemy
                worst = min(wounded, key=lambda a: a.hp_pct)
                dx_h = worst.entity.x - e.x
                dy_h = worst.entity.y - e.y
                dh = math.sqrt(dx_h**2 + dy_h**2) or 1
                move_x = dx_h / dh
                move_y = dy_h / dh
                # Heal if close enough
                if dh < 3.0 and self.battle_timer - c.last_attack_time > 2.0:
                    heal = random.randint(5, 15)
                    worst.entity.hp = min(worst.hp_start, worst.entity.hp + heal)
                    c.last_attack_time = self.battle_timer
                    self._log(f"{c.name} heals {worst.name} for {heal} HP!")
                    return  # don't move further
            else:
                # No wounded allies — stay back from enemies
                if dist < 5.0:
                    move_x = -move_x
                    move_y = -move_y

        # --- TERRAIN-AWARE BEHAVIOR ---
        terrain = self.terrain
        if terrain:
            my_elev = terrain.get_elevation(e.x, e.y)
            my_cover = terrain.get_cover(e.x, e.y)

            # Ranged units seek high ground
            if c.is_ranged and my_elev < terrain.HIGH_GROUND:
                # Look for nearby high ground
                best_elev = my_elev
                best_dx, best_dy = 0.0, 0.0
                for probe_angle in range(0, 360, 45):
                    pa = math.radians(probe_angle)
                    px = e.x + math.cos(pa) * 4
                    py = e.y + math.sin(pa) * 4
                    pe = terrain.get_elevation(px, py)
                    if pe > best_elev and not terrain.is_obstacle(px, py):
                        best_elev = pe
                        best_dx = px - e.x
                        best_dy = py - e.y
                if best_elev > my_elev:
                    nd = math.sqrt(best_dx**2 + best_dy**2) or 1
                    move_x = move_x * 0.5 + (best_dx / nd) * 0.5
                    move_y = move_y * 0.5 + (best_dy / nd) * 0.5

            # Melee units seek cover when approaching ranged enemies
            if not c.is_ranged and target.is_ranged and dist > 4.0:
                best_cov = my_cover
                best_dx, best_dy = 0.0, 0.0
                for probe_angle in range(0, 360, 45):
                    pa = math.radians(probe_angle)
                    px = e.x + math.cos(pa) * 3
                    py = e.y + math.sin(pa) * 3
                    # Cover that's also closer to the enemy
                    pd = math.sqrt((px - target.entity.x)**2 + (py - target.entity.y)**2)
                    pc = terrain.get_cover(px, py)
                    if pc > best_cov and pd < dist and not terrain.is_obstacle(px, py):
                        best_cov = pc
                        best_dx = px - e.x
                        best_dy = py - e.y
                if best_cov > my_cover:
                    nd = math.sqrt(best_dx**2 + best_dy**2) or 1
                    move_x = move_x * 0.6 + (best_dx / nd) * 0.4
                    move_y = move_y * 0.6 + (best_dy / nd) * 0.4

            # Units avoid obstacles
            new_x = e.x + move_x * speed
            new_y = e.y + move_y * speed
            if terrain.is_obstacle(new_x, new_y):
                # Try perpendicular directions
                for alt in [(move_y, -move_x), (-move_y, move_x)]:
                    ax = e.x + alt[0] * speed
                    ay = e.y + alt[1] * speed
                    if not terrain.is_obstacle(ax, ay):
                        move_x, move_y = alt[0], alt[1]
                        break
                else:
                    return  # stuck, don't move

        # --- STEERING BEHAVIORS (Boids) ---
        sep_x, sep_y = self._separation(c, all_alive, 2.0)
        coh_x, coh_y = self._cohesion(c, all_alive, 8.0)
        ali_x, ali_y = self._alignment(c, all_alive, 6.0)

        # Combine: movement + separation + light cohesion + alignment
        final_x = move_x + sep_x * 0.8 + coh_x * 0.1 + ali_x * 0.05
        final_y = move_y + sep_y * 0.8 + coh_y * 0.1 + ali_y * 0.05

        # Normalize and apply speed
        fn = math.sqrt(final_x * final_x + final_y * final_y) or 1
        final_x /= fn
        final_y /= fn

        # Don't move if already in attack range (except ranged kiting)
        attack_range = c.optimal_range if c.is_ranged else c.weapon_reach
        if dist <= attack_range and not (c.is_ranged and dist < c.optimal_range * 0.6):
            return  # stay and fight

        # Apply terrain movement cost
        if terrain:
            speed *= terrain.movement_cost(e.x, e.y)
            if speed <= 0:
                return  # impassable

        e.x += final_x * speed
        e.y += final_y * speed

        # Update facing
        c.facing_angle = math.atan2(final_y, final_x)

        # Clamp to arena
        self._clamp_to_arena(c)

    def _separation(self, c: Combatant, all_alive: list, radius: float):
        """Boids separation: push away from nearby entities."""
        sx, sy = 0.0, 0.0
        count = 0
        for other in all_alive:
            if other is c:
                continue
            d = self._dist(c.entity, other.entity)
            if d < radius and d > 0.01:
                # Push away, stronger when closer
                dx = c.entity.x - other.entity.x
                dy = c.entity.y - other.entity.y
                sx += dx / (d * d)
                sy += dy / (d * d)
                count += 1
        if count > 0:
            sx /= count
            sy /= count
        return sx, sy

    def _cohesion(self, c: Combatant, all_alive: list, radius: float):
        """Boids cohesion: steer toward average ally position."""
        ax, ay = 0.0, 0.0
        count = 0
        for other in all_alive:
            if other is c or other.team != c.team:
                continue
            d = self._dist(c.entity, other.entity)
            if d < radius:
                ax += other.entity.x
                ay += other.entity.y
                count += 1
        if count == 0:
            return 0.0, 0.0
        ax /= count
        ay /= count
        dx = ax - c.entity.x
        dy = ay - c.entity.y
        d = math.sqrt(dx * dx + dy * dy) or 1
        return dx / d, dy / d

    def _alignment(self, c: Combatant, all_alive: list, radius: float):
        """Boids alignment: match heading of nearby allies."""
        ax, ay = 0.0, 0.0
        count = 0
        for other in all_alive:
            if other is c or other.team != c.team:
                continue
            d = self._dist(c.entity, other.entity)
            if d < radius:
                ax += other.steer_vx
                ay += other.steer_vy
                count += 1
        if count == 0:
            return 0.0, 0.0
        ax /= count
        ay /= count
        d = math.sqrt(ax * ax + ay * ay) or 1
        return ax / d, ay / d

    # ------------------------------------------------------------------
    # ATTACK — delegates to game's CombatSystem, adds terrain + morale
    # ------------------------------------------------------------------

    def _do_attack(self, attacker: Combatant, target: Combatant,
                   all_alive: list):
        """Attack using the game's real combat system (npc_combat_tick).

        The colosseum adds only:
        - Terrain LoS blocking for ranged attacks
        - Terrain elevation/cover modifiers (temporary AC/damage adjustments)
        - Morale tracking from damage dealt
        - Kill/damage stat tracking for battle reports
        No duplicate combat rules — everything flows through CombatSystem.
        """
        from game.systems.combat import CombatSystem

        a = attacker.entity
        t = target.entity
        target_name = target.name
        terrain = self.terrain

        # --- TERRAIN: LoS check for ranged ---
        if attacker.is_ranged and terrain:
            if not terrain.has_line_of_sight(a.x, a.y, t.x, t.y):
                return  # blocked by cover/obstacle

        # --- TERRAIN: Apply temporary modifiers before attack ---
        ac_bonus = 0
        dmg_mult = 1.0
        if terrain:
            ac_bonus = terrain.cover_defense_bonus(t.x, t.y)
            dmg_mult = terrain.elevation_advantage(a.x, a.y, t.x, t.y)

        # Temporarily boost target AC for cover
        orig_ac = getattr(t, 'armor_class', 10)
        if ac_bonus:
            t.armor_class = orig_ac + ac_bonus

        # Temporarily boost attacker damage for elevation
        orig_dmg = getattr(a, 'npc_attack_damage', getattr(a, 'damage', 5))
        if dmg_mult != 1.0 and hasattr(a, 'npc_attack_damage'):
            a.npc_attack_damage = max(1, int(orig_dmg * dmg_mult))
        elif dmg_mult != 1.0 and hasattr(a, 'damage'):
            a.damage = max(1, int(orig_dmg * dmg_mult))

        # Record HP before attack to measure damage dealt
        hp_before = t.hp

        # --- DELEGATE TO GAME'S COMBAT SYSTEM ---
        a.combat_target = t
        if hasattr(a, 'state'):
            a.state = "fighting"
        if hasattr(a, 'current_action'):
            a.current_action = "fighting"

        msg = None
        if attacker.is_npc:
            # Use game's NPC combat system
            if hasattr(a, 'npc_attack_timer'):
                a.npc_attack_timer = 0  # ensure attack fires

            from game.core.player import Player
            _dummy_player = Player(0, 0)
            all_npcs = [c.entity for c in self.combatants if c.is_npc and c.entity.alive]
            all_creatures = [c.entity for c in self.combatants if c.is_creature and c.entity.alive]

            msg = CombatSystem.npc_combat_tick(a, _dummy_player,
                                                all_creatures, all_npcs, 0.5)
        else:
            # Creature attack — use body damage system directly
            from game.systems.body_damage import BodyDamageSystem
            _bds = BodyDamageSystem()
            damage = getattr(a, 'damage', 5)
            if dmg_mult != 1.0:
                damage = max(1, int(damage * dmg_mult))
            # Simple hit check
            roll = random.randint(1, 20) + 2
            ac = getattr(t, 'armor_class', 10) + ac_bonus
            if roll >= ac or roll >= 20:
                if roll >= 20:
                    damage *= 2
                actual_damage = _bds.apply_damage(t, damage, damage_type="blunt",
                                                   timestamp=self.battle_timer)
                # We'll track this below
            else:
                actual_damage = 0  # miss

        # --- RESTORE terrain-modified values ---
        if ac_bonus:
            t.armor_class = orig_ac
        if dmg_mult != 1.0 and hasattr(a, 'npc_attack_damage'):
            a.npc_attack_damage = orig_dmg
        elif dmg_mult != 1.0 and hasattr(a, 'damage'):
            a.damage = orig_dmg

        # --- TRACK COLOSSEUM STATS ---
        if attacker.is_npc:
            actual_damage = max(0, hp_before - t.hp)
        # else: actual_damage already set by creature branch above
        attacker.damage_dealt += actual_damage

        if actual_damage > 0:
            target.morale -= actual_damage * 0.5

        if not t.alive or t.hp <= 0:
            t.alive = False
            if hasattr(t, 'state'):
                t.state = "dead"
            attacker.kills += 1

            body = getattr(t, 'body', None)
            death_detail = ""
            if body:
                for pname, part in body.parts.items():
                    if part.hp <= 0 and pname in ("head", "torso"):
                        death_detail = f" ({pname} destroyed)"
                        break

            self._log(f"{attacker.name} killed {target_name}! "
                      f"({actual_damage} {attacker.weapon_type}{death_detail})")
            a.combat_target = None

            for ally in self.combatants:
                if ally.team == attacker.team and ally.entity.alive:
                    ally.morale = min(100, ally.morale + 5)
            for enemy in self.combatants:
                if enemy.team == target.team and enemy.entity.alive:
                    enemy.morale -= 8

        elif msg and actual_damage > 0:
            self._log_rare(msg)

    def _is_flanking(self, attacker: Combatant, target: Combatant) -> bool:
        """Check if attacker is behind the target (flanking)."""
        t = target.entity
        a = attacker.entity
        # Target's facing direction
        t_angle = target.facing_angle
        # Angle from target to attacker
        dx = a.x - t.x
        dy = a.y - t.y
        attack_angle = math.atan2(dy, dx)

        # Angle difference
        diff = abs(attack_angle - t_angle)
        if diff > math.pi:
            diff = 2 * math.pi - diff

        # Behind = angle > 120 degrees from facing
        return diff > math.pi * 0.67

    # ------------------------------------------------------------------
    # BATTLE END
    # ------------------------------------------------------------------

    def _check_battle_end(self) -> bool:
        teams_alive = set()
        for c in self.combatants:
            if c.entity.alive and not c.fleeing:
                teams_alive.add(c.team)
        return len(teams_alive) <= 1

    def _conclude_battle(self):
        self.state = self.CONCLUDED
        self.gates_locked = False

        result = BattleResult()
        result.duration = self.battle_timer
        result.rounds = self.rounds
        result.combatants = list(self.combatants)
        result.kill_log = list(self.battle_log)

        teams_alive = {}
        for c in self.combatants:
            if c.entity.alive and not c.fleeing:
                teams_alive.setdefault(c.team, []).append(c)

        if teams_alive:
            result.winner_team = max(teams_alive.keys(),
                                      key=lambda t: len(teams_alive[t]))
            winner_names = [c.name for c in teams_alive[result.winner_team]]
            result.summary = f"Team {result.winner_team} wins! Survivors: {', '.join(winner_names)}"
        else:
            result.winner_team = -1
            result.summary = "Draw! All combatants eliminated or fled."

        self._log(f"Battle concluded! {result.summary}")
        self.result = result

        for c in self.combatants:
            e = c.entity
            if hasattr(e, 'combat_target'):
                e.combat_target = None
            if hasattr(e, 'current_action'):
                e.current_action = ""
            if hasattr(e, 'state') and e.alive:
                e.state = "idle"

    # ------------------------------------------------------------------
    # PRESET CONFIGURATIONS
    # ------------------------------------------------------------------

    def reset(self):
        self.combatants.clear()
        self.state = self.IDLE
        self.result = None
        self.battle_log.clear()
        self.gates_locked = False
        self.rounds = 0
        self.battle_timer = 0.0

    def setup_duel(self, name_a, class_a, name_b, class_b,
                   level=3, weapon_a="Iron Sword", weapon_b="Iron Sword"):
        self.reset()
        self.spawn_npc(name_a, class_a, level=level, team=0,
                       weapon=weapon_a, armor="Leather Armor")
        self.spawn_npc(name_b, class_b, level=level, team=1,
                       weapon=weapon_b, armor="Leather Armor")

    def setup_team_battle(self, team_a, team_b, level=3):
        self.reset()
        for name, cls in team_a:
            self.spawn_npc(name, cls, level=level, team=0,
                           weapon="Iron Sword", armor="Leather Armor")
        for name, cls in team_b:
            self.spawn_npc(name, cls, level=level, team=1,
                           weapon="Iron Sword", armor="Leather Armor")

    def setup_beast_fight(self, kind_a, count_a, kind_b, count_b):
        self.reset()
        for _ in range(count_a):
            self.spawn_creature(kind_a, team=0)
        for _ in range(count_b):
            self.spawn_creature(kind_b, team=1)

    def setup_gladiator_vs_beast(self, name, char_class, level,
                                  creature_kind, creature_count=1):
        self.reset()
        self.spawn_npc(name, char_class, level=level, team=0,
                       weapon="Steel Sword", armor="Iron Armor")
        for _ in range(creature_count):
            self.spawn_creature(creature_kind, team=1)

    # ------------------------------------------------------------------
    # TROOP & COMMANDER SYSTEM
    # ------------------------------------------------------------------

    def spawn_troop(self, unit_type: str, size: int, team: int = 0,
                    equipment: float = 1.0, formation: str = None) -> List[Combatant]:
        """Spawn a troop unit as individual combatants in a MilitaryUnit.

        Uses warfare.py UNIT_STATS + MilitaryUnit for formation bonuses,
        matchup bonuses, coordinated morale, and commander rallying.
        """
        from game.systems.warfare import UNIT_STATS, MilitaryUnit
        stats = UNIT_STATS.get(unit_type, UNIT_STATS["infantry_sword"])
        category = stats.get("category", "infantry")

        type_to_class = {
            "infantry": ("Fighter", "Iron Sword", "Iron Armor"),
            "archer": ("Ranger", "Hunting Bow", "Leather Armor"),
            "cavalry": ("Paladin", "Steel Sword", "Iron Armor"),
            "siege": ("Fighter", "Staff", "Iron Armor"),
            "beast": ("Barbarian", "Iron Sword", "Leather Armor"),
            "support": ("Cleric", "Staff", "Leather Armor"),
        }
        cls, weapon, armor = type_to_class.get(category,
                                                ("Fighter", "Iron Sword", "Leather Armor"))

        type_label = unit_type.replace("_", " ").title()
        spawned = []

        # Create MilitaryUnit for this group
        mil_unit = MilitaryUnit(f"T{team}_{type_label}", unit_type, formation)

        for i in range(size):
            name = f"{type_label}_{i+1}"
            c = self.spawn_npc(name, cls, level=3, team=team,
                               weapon=weapon, armor=armor)
            if c:
                e = c.entity
                e.npc_attack_damage = max(e.npc_attack_damage,
                                           stats["melee"] + stats["ranged"])
                e.npc_defense = max(e.npc_defense, stats["defense"] // 2)
                e.max_hp = stats["hp"] * 3
                e.hp = e.max_hp
                c.hp_start = e.hp

                role_map = {"infantry": "tank", "archer": "ranged",
                            "cavalry": "berserker", "siege": "siege",
                            "beast": "beast", "support": "healer"}
                c.role = role_map.get(category, "melee")

                if category == "archer":
                    c.is_ranged = True
                    c.optimal_range = 8.0 * stats.get("range_factor", 1.0)

                if category == "cavalry":
                    e.speed = getattr(e, 'speed', 2.0) * stats["speed"]

                # Register in MilitaryUnit (applies formation/matchup bonuses)
                mil_unit.add_member(e)

                if formation:
                    c._formation = formation

                # Tag as troop member
                c._troop_type = unit_type
                c._troop_team = team
                spawned.append(c)

        return spawned

    def spawn_siege_engine(self, engine_type: str, team: int = 0) -> Optional[Combatant]:
        """Spawn a siege engine as a special combatant.

        Siege engines: catapult, trebuchet, ram. They deal massive damage
        but are slow and vulnerable to melee attack.
        """
        from game.systems.warfare import UNIT_STATS
        type_map = {
            "catapult": "siege_catapult",
            "trebuchet": "siege_trebuchet",
            "ram": "siege_ram",
        }
        unit_key = type_map.get(engine_type, f"siege_{engine_type}")
        stats = UNIT_STATS.get(unit_key)
        if not stats:
            return None

        c = self.spawn_npc(f"Siege_{engine_type.title()}", "Fighter",
                           level=1, team=team, weapon="Staff", armor="")
        if c:
            e = c.entity
            e.max_hp = stats["hp"] * 2
            e.hp = e.max_hp
            c.hp_start = e.hp
            e.npc_attack_damage = stats.get("structural_dmg", 10) + stats.get("ranged", 0)
            e.speed = 0.5  # siege engines are slow
            c.role = "siege"
            c.is_ranged = True
            c.optimal_range = 12.0
            c.weapon_speed = 0.3  # very slow firing
            c.weapon_type = "blunt"
            c._is_siege_engine = True
            c.name = f"{engine_type.title()}"
            self._log(f"Siege engine deployed: {engine_type.title()} (Team {team})")
        return c

    def set_commander(self, team: int, combatant_name: str,
                      formation: str = None):
        """Designate a combatant as commander for their team.

        Commander boosts nearby allies' morale and can order formations.
        """
        for c in self.combatants:
            if c.name == combatant_name and c.team == team:
                c.role = "commander"
                c._is_commander = True
                c._command_formation = formation
                self._log(f"{c.name} is now commanding Team {team}"
                          + (f" in {formation}" if formation else ""))

                # Apply formation to all team members
                if formation:
                    self.set_formation(team, formation)
                return

    def set_formation(self, team: int, formation: str):
        """Set formation for all combatants on a team."""
        from game.systems.warfare import FORMATIONS
        if formation not in FORMATIONS:
            return
        fm = FORMATIONS[formation]
        for c in self.combatants:
            if c.team == team:
                c._formation = formation
                # Update MilitaryUnit formation (applies real combat modifiers)
                mil_unit = getattr(c.entity, '_military_unit', None)
                if mil_unit:
                    mil_unit.set_formation(formation)
                # Adjust colosseum AI behavior
                if formation == "shield_wall":
                    c.optimal_range = max(c.optimal_range, 1.5)
                    c.weapon_speed *= fm.get("attack_mult", 1.0)
                elif formation == "skirmish_line" and c.is_ranged:
                    c.optimal_range *= 1.2
                elif formation == "defensive_circle":
                    c.is_ranged = False
        self._log(f"Team {team} forms {formation}!")

    # ------------------------------------------------------------------
    # PRESET: ARMY BATTLES
    # ------------------------------------------------------------------

    def setup_army_battle(self, army_a: List[Tuple[str, int]],
                          army_b: List[Tuple[str, int]],
                          commander_a: str = "", commander_b: str = "",
                          formation_a: str = None, formation_b: str = None):
        """Set up an army battle with troop units.

        Args:
            army_a/b: list of (unit_type, count) e.g. [("infantry_sword", 5), ("archer_longbow", 3)]
            commander_a/b: name of commander (first spawned unit if empty)
            formation_a/b: starting formation
        """
        self.reset()
        first_a = None
        for unit_type, count in army_a:
            spawned = self.spawn_troop(unit_type, count, team=0)
            if spawned and not first_a:
                first_a = spawned[0]
        first_b = None
        for unit_type, count in army_b:
            spawned = self.spawn_troop(unit_type, count, team=1)
            if spawned and not first_b:
                first_b = spawned[0]

        # Assign commanders
        if first_a:
            cmd_name = commander_a or first_a.name
            self.set_commander(0, cmd_name, formation_a)
        if first_b:
            cmd_name = commander_b or first_b.name
            self.set_commander(1, cmd_name, formation_b)

    def setup_army_vs_individuals(self, army: List[Tuple[str, int]],
                                   individuals: List[Tuple[str, str, int]],
                                   army_team: int = 0):
        """Army vs individual combatants (heroes vs army).

        Args:
            army: list of (unit_type, count)
            individuals: list of (name, class, level)
        """
        self.reset()
        ind_team = 1 if army_team == 0 else 0
        for unit_type, count in army:
            self.spawn_troop(unit_type, count, team=army_team)
        for name, cls, level in individuals:
            self.spawn_npc(name, cls, level=level, team=ind_team,
                           weapon="Steel Sword", armor="Iron Armor")

    def setup_siege_battle(self, attackers: List[Tuple[str, int]],
                            defenders: List[Tuple[str, int]],
                            siege_engines: List[str] = None):
        """Set up a battle with siege engines.

        Args:
            attackers: troop composition
            defenders: troop composition
            siege_engines: list of engine types for attackers
        """
        self.reset()
        for unit_type, count in attackers:
            self.spawn_troop(unit_type, count, team=0)
        for unit_type, count in defenders:
            self.spawn_troop(unit_type, count, team=1)
        for engine in (siege_engines or []):
            self.spawn_siege_engine(engine, team=0)

    def run_battle(self, max_rounds=400) -> BattleResult:
        self.prepare_battle()
        self.start_battle()
        for _ in range(max_rounds):
            self.update(self.round_interval)
            if self.state == self.CONCLUDED:
                break
        if self.state != self.CONCLUDED:
            self._conclude_battle()
        return self.result

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _dist(self, a, b) -> float:
        dx = a.x - b.x
        dy = a.y - b.y
        return math.sqrt(dx * dx + dy * dy)

    def _clamp_to_arena(self, c: Combatant):
        cx, cy = self.arena_center
        r = self.arena_radius
        dx = c.entity.x - cx
        dy = c.entity.y - cy
        d = math.sqrt(dx * dx + dy * dy)
        if d > r:
            c.entity.x = cx + (dx / d) * r
            c.entity.y = cy + (dy / d) * r

    def _log(self, msg: str):
        self.battle_log.append(msg)

    def _log_rare(self, msg: str):
        """Log infrequent events (throttled)."""
        if random.random() < 0.3:
            self.battle_log.append(msg)

    @property
    def status_text(self) -> str:
        alive_by_team = {}
        for c in self.combatants:
            if c.entity.alive:
                alive_by_team.setdefault(c.team, []).append(c.name)
        parts = [f"[{self.state.upper()}] R{self.rounds} "
                 f"({self.battle_timer:.0f}s)"]
        for team, names in sorted(alive_by_team.items()):
            parts.append(f"T{team}:{len(names)}")
        return " | ".join(parts)
