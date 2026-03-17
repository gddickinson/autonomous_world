"""Combat system: handles attacks between any entities, including spell casting."""

import math
from typing import List, Optional, Union, Dict, Any
from game.settings import *
from game.core.player import Player
from game.core.creature import Creature
from game.core.npc import NPC


class CombatSystem:
    """Handles combat between any entities (player, NPCs, creatures)."""

    @staticmethod
    def player_attack(player: Player, creatures: List[Creature],
                      npcs: List[NPC]) -> Optional[str]:
        """Execute player attack on nearest entity in range (creature or NPC)."""
        if player.attack_timer > 0:
            return None

        player.attack_timer = PLAYER_ATTACK_COOLDOWN

        fx, fy = player.facing
        best_target = None
        best_dist = PLAYER_ATTACK_RANGE
        target_kind = ""  # "creature" or "npc"

        # Check creatures
        for creature in creatures:
            if not creature.alive:
                continue
            dist = player.dist_to(creature)
            if dist > PLAYER_ATTACK_RANGE:
                continue
            dx = creature.x - player.x
            dy = creature.y - player.y
            d = math.sqrt(dx * dx + dy * dy) or 1
            dot = fx * (dx / d) + fy * (dy / d)
            if dot > -0.3 and dist < best_dist:
                best_dist = dist
                best_target = creature
                target_kind = "creature"

        # Check NPCs (can attack anyone)
        for npc in npcs:
            if not npc.alive:
                continue
            dist = player.dist_to(npc)
            if dist > PLAYER_ATTACK_RANGE:
                continue
            dx = npc.x - player.x
            dy = npc.y - player.y
            d = math.sqrt(dx * dx + dy * dy) or 1
            dot = fx * (dx / d) + fy * (dy / d)
            if dot > -0.3 and dist < best_dist:
                best_dist = dist
                best_target = npc
                target_kind = "npc"

        if best_target is None:
            return None

        damage = player.get_attack_damage()

        # Apply magic modifiers (enchantments, buffs, shield absorption)
        from game.systems.magic import integrate_magic_into_combat
        damage = integrate_magic_into_combat(damage, player, best_target)

        # Use body damage system if target has a body
        from game.systems.body_damage import BodyDamageSystem
        _bds = BodyDamageSystem()
        if getattr(best_target, 'body', None) is not None:
            # Determine damage type from equipped weapon
            weapon = getattr(player, 'equipped_weapon', None)
            dmg_type = "blunt"
            if weapon:
                wname = weapon.name.lower()
                if "sword" in wname or "axe" in wname:
                    dmg_type = "slash"
                elif "bow" in wname or "arrow" in wname or "spear" in wname:
                    dmg_type = "pierce"
                elif "staff" in wname or "hammer" in wname or "mace" in wname:
                    dmg_type = "blunt"
            actual = _bds.apply_damage(best_target, damage, damage_type=dmg_type)
            # Degrade player weapon on hit
            from game.systems.body_damage import degrade_weapon
            degrade_weapon(player)
        else:
            defense = 0
            if target_kind == "npc":
                defense = getattr(best_target, 'npc_defense', 0)
            actual = max(1, damage - defense)
            best_target.take_damage(actual)

        if target_kind == "creature":
            name = best_target.kind
            result = f"Hit {name} for {actual} damage!"
            if not best_target.alive:
                player.gain_xp(best_target.xp_value)
                player.kills += 1
                result += f" +{best_target.xp_value} XP"
        else:
            name = best_target.name
            cls = getattr(best_target, 'char_class', best_target.profession)
            result = f"Hit {name} ({cls}) for {actual} damage!"
            if not best_target.alive:
                xp = getattr(best_target, 'level', 1) * 15
                player.gain_xp(xp)
                player.kills += 1
                result += f" Killed! +{xp} XP"
            else:
                # NPC fights back or flees
                if best_target.bravery > 0.4:
                    best_target.combat_target = player
                    best_target.current_action = "fighting"
                    best_target.state = "fighting"
                    best_target.add_memory("combat", f"Attacked by the player!", 5)
                    best_target.player_relationship = max(-100, best_target.player_relationship - 20)
                else:
                    best_target.flee_from(player.x, player.y, None)
                    best_target.add_memory("combat", f"The player attacked me! Fleeing!", 5)
                    best_target.player_relationship = max(-100, best_target.player_relationship - 30)

        # Nearby NPCs react
        for npc in npcs:
            if npc is best_target or not npc.alive:
                continue
            if npc.dist_to(best_target) < 8.0:
                if target_kind == "npc":
                    # Attacking an NPC - others turn hostile or flee
                    npc.player_relationship = max(-100, npc.player_relationship - 10)
                    npc.add_memory("witness", f"Saw the player attack {name}", 4)
                    if npc.bravery < 0.5:
                        npc.flee_from(player.x, player.y, None)
                else:
                    # Attacking a creature - cowards flee
                    if npc.bravery < 0.3:
                        npc.flee_from(player.x, player.y, None)

        return result

    @staticmethod
    def player_cast_spell(player: Player, spell_name: str,
                          creatures: List[Creature],
                          npcs: List[NPC],
                          target_pos=None) -> Optional[str]:
        """Player casts a spell. Returns result message or None.

        Finds appropriate targets based on spell type and nearby entities.
        """
        from game.systems.magic import (
            can_cast, cast_spell, SPELL_REGISTRY, SOUL_SPELLS,
            get_spell_visual,
        )

        ok, reason = can_cast(player, spell_name)
        if not ok:
            return f"Cannot cast {spell_name}: {reason}"

        spell = SPELL_REGISTRY.get(spell_name) or SOUL_SPELLS.get(spell_name)
        if spell is None:
            return f"Unknown spell: {spell_name}"

        # Gather all nearby entities
        all_entities = []
        for c in creatures:
            if c.alive and player.dist_to(c) <= spell.range_tiles + spell.area:
                all_entities.append(c)
        for n in npcs:
            if n.alive and player.dist_to(n) <= spell.range_tiles + spell.area:
                all_entities.append(n)

        # Find best target based on spell type
        target = None
        fx, fy = player.facing

        if spell.targets == "single" or spell.targets == "chain":
            # Find nearest hostile in facing direction
            best_dist = spell.range_tiles
            for ent in all_entities:
                dist = player.dist_to(ent)
                if dist > spell.range_tiles:
                    continue
                dx = ent.x - player.x
                dy = ent.y - player.y
                d = math.sqrt(dx * dx + dy * dy) or 1
                dot = fx * (dx / d) + fy * (dy / d)
                if dot > 0 and dist < best_dist:
                    # For heal/ally spells, prefer friendly NPCs
                    if spell.targets == "ally":
                        continue  # handled below
                    best_dist = dist
                    target = ent

        elif spell.targets == "ally":
            # Find nearest ally or self
            if spell.heal > 0 or spell.effect_type == "buff":
                # For resurrect, find dead NPCs
                if spell_name == "resurrect":
                    for n in npcs:
                        if not n.alive and player.dist_to(n) <= spell.range_tiles:
                            target = n
                            break
                else:
                    # Self-target for ally spells by default
                    target = player
                    # But prefer a hurt nearby NPC ally
                    for n in npcs:
                        if not n.alive:
                            continue
                        if n.hp < n.max_hp * 0.5 and player.dist_to(n) <= spell.range_tiles:
                            if getattr(n, 'player_relationship', 0) >= 0:
                                target = n
                                break

        elif spell.targets == "aoe":
            if not target_pos:
                # Default: cast in facing direction at range
                target_pos = (
                    player.x + fx * min(spell.range_tiles, 4),
                    player.y + fy * min(spell.range_tiles, 4),
                )

        elif spell.targets == "self":
            target = player

        result = cast_spell(
            player, spell_name,
            target=target,
            target_pos=target_pos,
            entities_nearby=all_entities + [player],
        )

        return result.get("message", "Spell cast!")

    @staticmethod
    def npc_combat_tick(npc: NPC, player: Player,
                        creatures: List[Creature],
                        npcs: List[NPC], dt: float) -> Optional[str]:
        """Called each frame for NPCs in combat state. Handles both melee and spell attacks.

        Returns a combat message or None.
        """
        if not npc.alive or npc.state != "fighting":
            return None

        target = npc.combat_target
        if target is None or not getattr(target, 'alive', True):
            npc.state = "idle"
            npc.combat_target = None
            npc.current_action = ""
            return None

        dist = npc.dist_to(target)

        # Try spell casting first (if NPC is a caster and has mana)
        if getattr(npc, 'is_spellcaster', False) and hasattr(npc, 'mana'):
            from game.systems.magic import npc_choose_spell, npc_cast_spell

            # Gather enemies and allies
            enemies = [target]
            allies = [n for n in npcs if n is not npc and n.alive and npc.dist_to(n) < 10]

            choice = npc_choose_spell(npc, enemies, allies)
            if choice is not None:
                sp_name, sp_target = choice
                all_nearby = list(creatures) + list(npcs) + [player]
                result = npc_cast_spell(npc, sp_name, sp_target, all_nearby)
                if result.get("success"):
                    return result.get("message")

        # Fall back to melee attack
        if npc.npc_attack_timer > 0:
            npc.npc_attack_timer -= dt
            return None

        if dist > 1.5:
            # Move closer
            npc.target_x = target.x
            npc.target_y = target.y
            return None

        # Execute melee attack
        npc.npc_attack_timer = 1.0
        damage = getattr(npc, 'npc_attack_damage', 5)

        # Apply magic modifiers to NPC melee
        from game.systems.magic import integrate_magic_into_combat
        damage = integrate_magic_into_combat(damage, npc, target)

        actual = target.take_damage(max(1, damage))
        npc_name = npc.name
        target_name = getattr(target, 'name', getattr(target, 'kind', 'target'))

        if not getattr(target, 'alive', True):
            npc.state = "idle"
            npc.combat_target = None
            npc.current_action = ""
            return f"{npc_name} slew {target_name}!"

        return f"{npc_name} hits {target_name} for {actual} damage"
