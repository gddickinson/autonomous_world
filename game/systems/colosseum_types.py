"""Colosseum types — Combatant and BattleResult classes."""

import random
import math
from typing import List, Optional, Tuple

from game.systems.colosseum import WEAPON_PROPS, ROLE_MAP


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

