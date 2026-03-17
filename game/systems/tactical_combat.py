"""
Real-time directed combat system (Baldur's Gate / Dragon Age style).

Combat happens in real-time within the normal game world. No freezing.
The player directs their character and companions with orders:
- Click/select a target to attack
- Use abilities and spells as actions
- D20 attack rolls happen automatically on cooldown
- Status effects, saving throws work in real-time

Key design: the game NEVER freezes. Combat is part of the living world.
"""

import random
import math
from typing import List, Optional, Dict
from game.settings import *
from game.data.dnd import ability_modifier, get_proficiency_bonus, SPELLS


class CombatState:
    """Tracks an entity's combat state without freezing the game."""
    __slots__ = ('target', 'attack_cooldown', 'attack_timer',
                 'spell_cooldown', 'in_combat', 'last_damage_taken',
                 'last_damage_dealt', 'kill_count', 'damage_log')

    def __init__(self):
        self.target = None            # entity reference
        self.attack_cooldown = 1.5    # seconds between attacks
        self.attack_timer = 0.0       # countdown to next attack
        self.spell_cooldown = 0.0     # countdown to next spell
        self.in_combat = False
        self.last_damage_taken = 0
        self.last_damage_dealt = 0
        self.kill_count = 0
        self.damage_log: List[str] = []

    def add_log(self, msg: str):
        self.damage_log.append(msg)
        if len(self.damage_log) > 15:
            self.damage_log = self.damage_log[-15:]


class TacticalCombat:
    """
    Real-time directed combat. No game freeze.

    Usage:
        combat = TacticalCombat()
        # Player clicks an enemy -> combat.set_player_target(enemy)
        # Each frame -> combat.update(dt, player, allies, creatures, npcs)
        # Combat log shown in HUD
    """

    def __init__(self):
        self.active = False  # True when player is in combat
        self.player_state = CombatState()
        self.companion_states: Dict[str, CombatState] = {}
        self.combat_log: List[str] = []

    @property
    def is_player_turn(self) -> bool:
        """Always False in real-time - no turns."""
        return False

    def set_player_target(self, target) -> str:
        """Player directs attack at a target."""
        if target is None:
            self.player_state.target = None
            self.player_state.in_combat = False
            self.active = False
            return "Disengaged."

        self.player_state.target = target
        self.player_state.in_combat = True
        self.active = True
        name = getattr(target, 'name', getattr(target, 'kind', '?'))
        msg = f"Targeting {name}!"
        self.combat_log.append(msg)
        return msg

    def set_companion_target(self, companion, target):
        """Direct a companion to attack a specific target."""
        key = companion.name
        if key not in self.companion_states:
            self.companion_states[key] = CombatState()
        self.companion_states[key].target = target
        self.companion_states[key].in_combat = True

    def update(self, dt: float, player, companions: list,
               creatures: list, npcs: list, world=None):
        """Update all combat in real-time. Called every frame."""

        # Update player combat
        if self.player_state.in_combat and self.player_state.target:
            target = self.player_state.target
            if not getattr(target, 'alive', False):
                # Target dead
                xp = getattr(target, 'xp_value', getattr(target, 'level', 1) * 10)
                player.gain_xp(xp)
                player.kills += 1
                self.player_state.kill_count += 1
                name = getattr(target, 'name', getattr(target, 'kind', '?'))
                msg = f"Defeated {name}! +{xp} XP"
                self.combat_log.append(msg)
                self.player_state.target = None
                self.player_state.in_combat = False

                # Auto-target next nearby enemy
                next_target = self._find_nearest_hostile(player, creatures, npcs, companions)
                if next_target:
                    self.set_player_target(next_target)
                else:
                    self.active = False
                    self.combat_log.append("Combat ended.")
            else:
                self._process_attack(player, target, self.player_state, dt, is_player=True)

        # Update companion combat
        for companion in companions:
            if not companion.alive:
                continue
            key = companion.name
            if key not in self.companion_states:
                self.companion_states[key] = CombatState()
            state = self.companion_states[key]

            # Auto-target: companions attack what the player is attacking
            if not state.target or not getattr(state.target, 'alive', False):
                if self.player_state.target and getattr(self.player_state.target, 'alive', False):
                    state.target = self.player_state.target
                    state.in_combat = True
                else:
                    # Find own target
                    nearby = self._find_nearest_hostile(companion, creatures, npcs, companions)
                    if nearby:
                        state.target = nearby
                        state.in_combat = True
                    else:
                        state.in_combat = False

            if state.in_combat and state.target:
                if not getattr(state.target, 'alive', False):
                    state.target = None
                    state.in_combat = False
                else:
                    self._process_attack(companion, state.target, state, dt, is_player=False)

        # Check if all combat is done
        if self.active:
            any_fighting = self.player_state.in_combat
            if not any_fighting:
                for state in self.companion_states.values():
                    if state.in_combat:
                        any_fighting = True
                        break
            if not any_fighting:
                self.active = False

    def _process_attack(self, attacker, target, state: CombatState, dt: float,
                        is_player: bool = False):
        """Process a real-time attack with D20 rolls."""
        state.attack_timer -= dt

        # Move toward target if too far
        dist = attacker.dist_to(target)
        attack_range = PLAYER_ATTACK_RANGE if is_player else 1.5

        if dist > attack_range:
            # Auto-approach (for companions and player auto-move)
            if not is_player:
                dx = target.x - attacker.x
                dy = target.y - attacker.y
                d = math.sqrt(dx*dx + dy*dy) or 1
                speed = getattr(attacker, 'speed', NPC_SPEED) * dt
                attacker.x += (dx/d) * speed
                attacker.y += (dy/d) * speed
                attacker.facing = (dx/d, dy/d)
            return

        # Attack when cooldown is ready
        if state.attack_timer <= 0:
            state.attack_timer = state.attack_cooldown
            result = self._roll_attack(attacker, target, is_player)
            state.add_log(result)
            self.combat_log.append(result)
            if len(self.combat_log) > 20:
                self.combat_log = self.combat_log[-20:]

    def _roll_attack(self, attacker, target, is_player: bool) -> str:
        """Execute a D20 attack roll."""
        # Get attacker stats
        if is_player:
            atk_mod = ability_modifier(attacker.ability_scores.get("strength", 10))
            prof = getattr(attacker, 'proficiency_bonus', 2)
            dmg_bonus = atk_mod
            weapon_die = 8
            if attacker.equipped_weapon:
                weapon_die = max(4, attacker.equipped_weapon.damage // 2)
        elif hasattr(attacker, 'ability_scores'):
            # NPC
            str_mod = ability_modifier(attacker.ability_scores.get("strength", 10))
            dex_mod = ability_modifier(attacker.ability_scores.get("dexterity", 10))
            atk_mod = max(str_mod, dex_mod)
            prof = get_proficiency_bonus(getattr(attacker, 'level', 1))
            dmg_bonus = atk_mod
            weapon_die = 6
        else:
            # Creature
            atk_mod = 0
            prof = 2
            dmg_bonus = 0
            weapon_die = getattr(attacker, 'damage', 5)

        # Target AC
        target_ac = getattr(target, 'armor_class', 10)

        # D20 roll
        roll = random.randint(1, 20)
        total = roll + atk_mod + prof
        attacker_name = getattr(attacker, 'name', getattr(attacker, 'kind', '?'))
        target_name = getattr(target, 'name', getattr(target, 'kind', '?'))

        is_crit = roll == 20
        is_fumble = roll == 1

        if is_fumble or (total < target_ac and not is_crit):
            return f"{attacker_name} misses {target_name} ({roll}+{atk_mod+prof}={total} vs AC {target_ac})"

        # Calculate damage
        damage = random.randint(1, weapon_die) + dmg_bonus
        if is_crit:
            damage += random.randint(1, weapon_die)

        # Apply defense
        defense = getattr(target, 'npc_defense', 0) if hasattr(target, 'npc_defense') else 0
        actual = max(1, damage - defense)
        target.take_damage(actual)

        crit = " CRIT!" if is_crit else ""
        return f"{attacker_name} hits {target_name} for {actual}{crit} ({roll}+{atk_mod+prof}={total} vs AC {target_ac})"

    def cast_spell(self, caster, spell_name: str, target=None) -> str:
        """Cast a spell in real-time."""
        spell = SPELLS.get(spell_name)
        if not spell:
            return f"Unknown spell: {spell_name}"

        if not target:
            target = self.player_state.target
        if not target:
            return "No target selected."

        dist = caster.dist_to(target)
        if dist > spell.get("range", 5):
            return f"Out of range ({dist:.0f} > {spell['range']})"

        damage = spell.get("damage", 0)
        caster_name = getattr(caster, 'name', 'Player')
        target_name = getattr(target, 'name', getattr(target, 'kind', '?'))

        if damage > 0:
            # Spell attack or saving throw
            save_stat = spell.get("save")
            if save_stat and hasattr(target, 'ability_scores'):
                dc = 8 + ability_modifier(caster.ability_scores.get("intelligence", 10)) + \
                     getattr(caster, 'proficiency_bonus', 2)
                save_mod = ability_modifier(target.ability_scores.get(save_stat, 10))
                save_roll = random.randint(1, 20) + save_mod
                if save_roll >= dc:
                    damage = damage // 2

            target.take_damage(damage)
            msg = f"{caster_name} casts {spell_name} on {target_name}: {damage} {spell.get('type','')} damage!"
        elif damage < 0:
            heal = abs(damage)
            target.heal(heal)
            msg = f"{caster_name} casts {spell_name}: heals {target_name} for {heal}!"
        else:
            msg = f"{caster_name} casts {spell_name} on {target_name}!"

        self.combat_log.append(msg)

        # Store pending spell visual for renderer pickup
        if not hasattr(self, '_pending_spell_visuals'):
            self._pending_spell_visuals = []
        self._pending_spell_visuals.append({
            "spell_name": spell_name,
            "x": caster.x, "y": caster.y,
            "target_x": target.x, "target_y": target.y,
        })

        return msg

    def _find_nearest_hostile(self, entity, creatures, npcs, companions) -> Optional[object]:
        """Find nearest hostile entity."""
        best = None
        best_dist = CREATURE_CHASE_RANGE

        for c in creatures:
            if c.alive:
                d = entity.dist_to(c)
                if d < best_dist:
                    best_dist = d
                    best = c

        return best

    def end_combat(self):
        """Disengage from combat."""
        self.active = False
        self.player_state.target = None
        self.player_state.in_combat = False
        for state in self.companion_states.values():
            state.target = None
            state.in_combat = False
        self.combat_log.append("Disengaged from combat.")

    def get_combat_summary(self) -> str:
        """Get current combat state as text."""
        if not self.active:
            return ""
        target = self.player_state.target
        if target:
            name = getattr(target, 'name', getattr(target, 'kind', '?'))
            hp = getattr(target, 'hp', 0)
            maxhp = getattr(target, 'max_hp', 1)
            return f"Fighting: {name} HP:{hp}/{maxhp}"
        return "In combat"
