"""Colosseum battle presets — army setup, troop spawning, formations."""

import random
import math
from typing import List, Tuple, Optional
from game.settings import *


class ColosseumPresetsMixin:

    """Mixin — see parent class for context."""

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


