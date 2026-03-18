"""Combat system: handles attacks between any entities, including spell casting."""

import math
import random
from typing import List, Optional, Union, Dict, Any
from game.settings import *
from game.core.player import Player
from game.core.creature import Creature
from game.core.npc import NPC


# ---------------------------------------------------------------------------
# Creature attack styles — maps creature kind to combat behaviour profile
# ---------------------------------------------------------------------------
CREATURE_ATTACK_STYLES = {
    # Pack hunters: coordinated attacks, bonus when allies nearby
    "wolf":       {"style": "pack", "dmg_type": "slash", "reach": 1.5, "speed": 1.0},
    "dire_wolf":  {"style": "pack", "dmg_type": "slash", "reach": 1.8, "speed": 1.0},
    "rat":        {"style": "pack", "dmg_type": "pierce", "reach": 1.0, "speed": 1.5},

    # Intelligent pack hunters — mix of ranged and melee fighters
    # Goblins: some throw javelins, some stab with daggers
    "goblin":     {"style": "pack", "dmg_type": "pierce", "reach": 1.5, "speed": 1.0,
                   "ranged_chance": 0.4, "ranged_type": "javelin", "range": 5.0},
    # Orcs: some use bows, most use swords/axes
    "orc":        {"style": "pack", "dmg_type": "slash", "reach": 1.8, "speed": 0.8,
                   "ranged_chance": 0.3, "ranged_type": "bow", "range": 7.0},
    # Gnolls: throw javelins and use bows
    "gnoll":      {"style": "pack", "dmg_type": "slash", "reach": 1.5, "speed": 0.9,
                   "ranged_chance": 0.4, "ranged_type": "bow", "range": 6.0},
    # Bandits: crossbows and thrown knives
    "bandit":     {"style": "pack", "dmg_type": "slash", "reach": 1.5, "speed": 1.0,
                   "ranged_chance": 0.5, "ranged_type": "crossbow", "range": 8.0},
    # Kobolds: slings and traps
    "kobold":     {"style": "pack", "dmg_type": "pierce", "reach": 1.3, "speed": 1.2,
                   "ranged_chance": 0.5, "ranged_type": "sling", "range": 5.0},
    # Bugbears: javelin ambush then melee
    "bugbear":    {"style": "ambush", "dmg_type": "blunt", "reach": 2.0, "speed": 0.8,
                   "ranged_chance": 0.3, "ranged_type": "javelin", "range": 4.0},

    # Ambush predators: bonus damage on first strike
    "spider":     {"style": "ambush", "dmg_type": "pierce", "reach": 1.5, "speed": 1.2, "special": "poison"},
    "giant_spider": {"style": "ambush", "dmg_type": "pierce", "reach": 2.0, "speed": 1.0, "special": "poison",
                   "ranged_chance": 1.0, "ranged_type": "web", "range": 4.0},  # web spit
    "giant_scorpion": {"style": "ambush", "dmg_type": "pierce", "reach": 2.0, "speed": 0.8, "special": "poison"},
    "snake":      {"style": "ambush", "dmg_type": "pierce", "reach": 1.0, "speed": 1.5, "special": "poison"},
    "viper":      {"style": "ambush", "dmg_type": "pierce", "reach": 1.0, "speed": 1.3, "special": "poison"},
    "mountain_lion": {"style": "ambush", "dmg_type": "slash", "reach": 1.5, "speed": 1.3},

    # Brutes: high damage, slow, intimidating
    "bear":       {"style": "brute", "dmg_type": "slash", "reach": 2.0, "speed": 0.7},
    "ogre":       {"style": "brute", "dmg_type": "blunt", "reach": 2.5, "speed": 0.6,
                   "ranged_chance": 0.3, "ranged_type": "boulder", "range": 5.0,
                   "siege_monster": True},  # living siege engine — throws rocks
    "troll":      {"style": "brute", "dmg_type": "slash", "reach": 2.0, "speed": 0.7, "special": "regenerate",
                   "ranged_chance": 0.2, "ranged_type": "boulder", "range": 4.0,
                   "siege_monster": True},  # can throw boulders
    "hill_giant": {"style": "brute", "dmg_type": "blunt", "reach": 3.0, "speed": 0.5,
                   "ranged_chance": 0.5, "ranged_type": "boulder", "range": 8.0,
                   "siege_monster": True},  # living siege engine — throws boulders
    "owlbear":    {"style": "brute", "dmg_type": "slash", "reach": 2.0, "speed": 0.8},
    "minotaur":   {"style": "brute", "dmg_type": "slash", "reach": 2.5, "speed": 0.7, "special": "charge"},
    "boar":       {"style": "brute", "dmg_type": "pierce", "reach": 1.5, "speed": 0.9, "special": "charge"},
    "wild_boar":  {"style": "brute", "dmg_type": "pierce", "reach": 1.5, "speed": 0.9, "special": "charge"},
    "crocodile":  {"style": "brute", "dmg_type": "slash", "reach": 2.0, "speed": 0.5, "special": "grapple"},

    # Flyers: hit and run, hard to pin down
    "harpy":      {"style": "flyer", "dmg_type": "slash", "reach": 1.5, "speed": 1.3,
                   "ranged_chance": 0.6, "ranged_type": "screech", "range": 5.0},  # sonic attack
    "griffin":     {"style": "flyer", "dmg_type": "slash", "reach": 2.0, "speed": 1.2},
    "wyvern":     {"style": "flyer", "dmg_type": "slash", "reach": 2.5, "speed": 1.1,
                   "special": "poison", "ranged_chance": 0.3, "ranged_type": "tail_sting", "range": 3.0},
    "manticore":  {"style": "flyer", "dmg_type": "pierce", "reach": 2.0, "speed": 1.0,
                   "special": "ranged_spines", "ranged_chance": 1.0, "ranged_type": "spines", "range": 6.0},

    # Ranged: dragons, casters — always prefer ranged, kite if possible
    "young_dragon": {"style": "ranged", "dmg_type": "fire", "reach": 3.0, "speed": 0.8,
                   "special": "breath_weapon", "range": 6.0, "ranged_chance": 1.0, "ranged_type": "breath",
                   "siege_monster": True},  # living siege engine — breath weapon
    "phoenix":    {"style": "ranged", "dmg_type": "fire", "reach": 2.0, "speed": 1.0,
                   "special": "breath_weapon", "range": 5.0, "ranged_chance": 1.0, "ranged_type": "breath"},

    # Undead: relentless, fear-inducing
    "zombie":     {"style": "brute", "dmg_type": "blunt", "reach": 1.5, "speed": 0.4},
    "skeleton":   {"style": "pack", "dmg_type": "slash", "reach": 1.5, "speed": 0.8,
                   "ranged_chance": 0.4, "ranged_type": "bow", "range": 6.0},  # skeleton archers
    "ghoul":      {"style": "ambush", "dmg_type": "necrotic", "reach": 1.5, "speed": 0.9, "special": "paralyze"},
    "wight":      {"style": "pack", "dmg_type": "necrotic", "reach": 1.8, "speed": 0.9,
                   "ranged_chance": 0.3, "ranged_type": "life_drain", "range": 4.0},
    "shadow":     {"style": "ambush", "dmg_type": "necrotic", "reach": 1.5, "speed": 1.2},
    "wraith":     {"style": "flyer", "dmg_type": "necrotic", "reach": 2.0, "speed": 1.2,
                   "ranged_chance": 0.5, "ranged_type": "life_drain", "range": 5.0},
    "vampire":    {"style": "ambush", "dmg_type": "necrotic", "reach": 1.5, "speed": 1.0, "special": "drain"},
    "lich":       {"style": "ranged", "dmg_type": "necrotic", "reach": 2.0, "speed": 0.7,
                   "special": "spell", "range": 8.0, "ranged_chance": 1.0, "ranged_type": "spell"},

    # Misc
    "gargoyle":   {"style": "brute", "dmg_type": "blunt", "reach": 1.5, "speed": 0.8},
    "centaur":    {"style": "flyer", "dmg_type": "pierce", "reach": 2.5, "speed": 1.2,
                   "ranged_chance": 0.6, "ranged_type": "bow", "range": 7.0},  # mounted archers
    "werewolf":   {"style": "ambush", "dmg_type": "slash", "reach": 1.8, "speed": 1.1},
    "ankheg":     {"style": "ambush", "dmg_type": "pierce", "reach": 2.0, "speed": 0.9,
                   "ranged_chance": 0.3, "ranged_type": "acid_spit", "range": 4.0, "special": "poison"},
    "basilisk":   {"style": "brute", "dmg_type": "pierce", "reach": 1.5, "speed": 0.6},
    "giant_crab": {"style": "brute", "dmg_type": "blunt", "reach": 2.0, "speed": 0.7},
}

_DEFAULT_ATTACK_STYLE = {"style": "brute", "dmg_type": "blunt", "reach": 1.8, "speed": 1.0}


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
        """Tactical NPC combat — role-based behavior, kiting, flanking, morale.

        Uses the game's real body damage system for wounds and equipment
        durability. AI behaviors ported from colosseum testing.
        """
        if not npc.alive or npc.state != "fighting":
            return None

        target = npc.combat_target
        if target is None or not getattr(target, 'alive', True):
            npc.state = "idle"
            npc.combat_target = None
            npc.current_action = ""
            return None

        # --- ALLEGIANCE CHECK: don't attack allies ---
        from game.systems.allegiance import should_attack, are_allies
        if not should_attack(npc, target):
            npc.combat_target = None
            npc.current_action = ""
            npc.state = "idle"
            return None

        dist = npc.dist_to(target)
        cc = getattr(npc, 'char_class', '')
        bravery = getattr(npc, 'bravery', 0.5)

        # --- MORALE CHECK: flee if badly hurt and not brave ---
        hp_pct = npc.hp / max(1, npc.max_hp)
        if hp_pct < 0.2 and bravery < 0.6 and cc != "Barbarian":
            # Check if there's a healer ally nearby
            has_healer = False
            for other in npcs:
                if (other is not npc and other.alive and
                    getattr(other, 'char_class', '') in ("Cleric", "Druid") and
                    npc.dist_to_sq(other) < 100):
                    has_healer = True
                    break
            if not has_healer:
                npc.flee_from(target.x, target.y)
                npc.combat_target = None
                return f"{npc.name} flees from {getattr(target, 'name', 'enemy')}!"

        # --- DETERMINE ROLE & WEAPON ---
        is_ranged = False
        weapon = getattr(npc, 'weapon', getattr(npc, 'equipped_weapon', None))
        weapon_name = getattr(weapon, 'name', '').lower() if weapon else ''
        attack_range = 1.5  # default melee

        if 'bow' in weapon_name or 'crossbow' in weapon_name:
            is_ranged = True
            attack_range = 8.0
        elif 'sling' in weapon_name or 'javelin' in weapon_name:
            is_ranged = True
            attack_range = 6.0
        elif cc in ("Ranger",) and not weapon_name:
            is_ranged = True
            attack_range = 7.0

        if 'spear' in weapon_name or 'pike' in weapon_name:
            attack_range = 2.5  # spears have reach
        elif 'staff' in weapon_name:
            attack_range = 2.0

        # Determine damage type from weapon
        dmg_type = "blunt"
        if 'sword' in weapon_name or 'axe' in weapon_name:
            dmg_type = "slash"
        elif 'bow' in weapon_name or 'arrow' in weapon_name or 'spear' in weapon_name:
            dmg_type = "pierce"

        # Formation speed modifier
        from game.systems.warfare import get_unit_speed_mult
        _formation_speed = get_unit_speed_mult(npc)

        # --- RANGED KITING: stay at optimal range ---
        if is_ranged:
            optimal = attack_range * 0.8
            if dist < optimal * 0.5:
                # Too close — retreat away from target
                dx = npc.x - target.x
                dy = npc.y - target.y
                d = math.sqrt(dx * dx + dy * dy) or 1
                flee_speed = getattr(npc, 'speed', 2.0) * dt * 1.3 * _formation_speed
                npc.x += (dx / d) * flee_speed
                npc.y += (dy / d) * flee_speed
                return None  # kiting, don't attack this tick
            elif dist > attack_range * 1.3:
                # Too far — close in slightly
                npc.target_x = target.x
                npc.target_y = target.y
                return None

        # --- FLANKER BEHAVIOR: circle to attack from behind ---
        if cc in ("Rogue", "Monk") and dist > attack_range and dist < 8.0:
            dx = target.x - npc.x
            dy = target.y - npc.y
            d = math.sqrt(dx * dx + dy * dy) or 1
            # Move perpendicular to approach from side/behind
            perp_x, perp_y = -dy / d, dx / d
            side = 1 if (npc.x + npc.y) % 2 > 1 else -1
            move_x = (dx / d) * 0.6 + perp_x * 0.4 * side
            move_y = (dy / d) * 0.6 + perp_y * 0.4 * side
            speed = getattr(npc, 'speed', 2.0) * dt
            npc.x += move_x * speed
            npc.y += move_y * speed
            npc.target_x = npc.x + move_x
            npc.target_y = npc.y + move_y
            return None

        # --- MOVE CLOSER if out of range ---
        if dist > attack_range:
            npc.target_x = target.x
            npc.target_y = target.y
            return None

        # --- ATTACK COOLDOWN ---
        if npc.npc_attack_timer > 0:
            npc.npc_attack_timer -= dt
            return None

        npc.npc_attack_timer = 1.0

        # --- TRY SPELL CASTING FIRST ---
        if getattr(npc, 'is_spellcaster', False) and hasattr(npc, 'mana'):
            from game.systems.magic import npc_choose_spell, npc_cast_spell
            enemies = [target]
            allies = [n for n in npcs if n is not npc and n.alive and npc.dist_to_sq(n) < 100]
            choice = npc_choose_spell(npc, enemies, allies)
            if choice is not None:
                sp_name, sp_target = choice
                all_nearby = list(creatures) + list(npcs) + [player]
                result = npc_cast_spell(npc, sp_name, sp_target, all_nearby)
                if result.get("success"):
                    return result.get("message")

        # --- EXECUTE ATTACK using body damage system ---
        from game.systems.body_damage import BodyDamageSystem, degrade_weapon
        from game.data.dnd import ability_modifier
        _bds = BodyDamageSystem()

        damage = getattr(npc, 'npc_attack_damage', 5)

        # Apply magic modifiers
        from game.systems.magic import integrate_magic_into_combat
        damage = integrate_magic_into_combat(damage, npc, target)

        # Combat modifier from wounds (injured fighters deal less damage)
        combat_mod = _bds.get_combat_modifier(npc)
        damage = max(1, int(damage * combat_mod))

        # Military unit modifiers (formation bonuses, rock-paper-scissors)
        from game.systems.warfare import apply_unit_combat_mods
        atk_mult, def_mult = apply_unit_combat_mods(npc, target)
        damage = max(1, int(damage * atk_mult))

        # D20 attack roll
        str_mod = ability_modifier(npc.ability_scores.get("strength", 10))
        dex_mod = ability_modifier(npc.ability_scores.get("dexterity", 10))
        atk_mod = dex_mod if is_ranged or cc in ("Rogue", "Monk") else str_mod
        prof = getattr(npc, 'proficiency_bonus', 2)
        roll = random.randint(1, 20)
        total = roll + atk_mod + prof
        ac = getattr(target, 'armor_class', 10)

        # Formation defense bonus (shield wall etc.)
        if def_mult > 1.0:
            ac = int(ac * def_mult)

        # Flanking bonus: check if attacking from behind
        if hasattr(target, 'facing'):
            tx, ty = getattr(target, 'facing', (0, 1))
            dx = npc.x - target.x
            dy = npc.y - target.y
            d = math.sqrt(dx * dx + dy * dy) or 1
            # Dot product of target facing vs direction to attacker
            dot = tx * (dx / d) + ty * (dy / d)
            if dot < -0.3:  # behind target
                total += 2
                damage = int(damage * 1.5)
                # Rogue sneak attack
                if cc == "Rogue":
                    damage += random.randint(1, 6) * max(1, getattr(npc, 'level', 1) // 2)

        if roll == 1:
            return f"{npc.name} fumbles!"  # critical miss
        if total < ac and roll != 20:
            return None  # miss

        if roll >= 20:
            damage = int(damage * 2.0)  # critical hit

        # Apply through body damage system (body parts, armor, wounds, durability)
        actual = _bds.apply_damage(target, damage, damage_type=dmg_type)

        # Degrade attacker's weapon
        degrade_weapon(npc)

        npc_name = npc.name
        target_name = getattr(target, 'name', getattr(target, 'kind', 'target'))

        if not getattr(target, 'alive', True):
            npc.state = "idle"
            npc.combat_target = None
            npc.current_action = ""
            return f"{npc_name} slew {target_name}!"

        return f"{npc_name} hits {target_name} for {actual} {dmg_type} damage"

    @staticmethod
    def creature_combat_tick(creature, target, dt: float,
                             nearby_allies: Optional[List] = None) -> Optional[str]:
        """Creature attacks a target using body damage, morale, and tactical movement.

        Creatures use the same damage systems as NPCs — body parts, wounds,
        armor degradation. Tactical behaviors based on CREATURE_ATTACK_STYLES:
        - Pack hunters coordinate (wolves, goblins)
        - Ambush predators deal bonus damage on first strike
        - Brutes hit hard and slow
        - Flyers do hit-and-run attacks
        - Ranged creatures attack from distance (dragons, liches)
        - Special abilities: poison, charge, regenerate, breath_weapon, drain, etc.
        """
        if not creature.alive or not target or not getattr(target, 'alive', True):
            return None

        # Allegiance check: don't attack allies
        from game.systems.allegiance import should_attack as _should_attack
        if not _should_attack(creature, target):
            return None

        kind = getattr(creature, 'kind', '').lower()
        style_info = CREATURE_ATTACK_STYLES.get(kind, _DEFAULT_ATTACK_STYLE)
        attack_style = style_info["style"]
        dmg_type = style_info["dmg_type"]
        attack_range = style_info["reach"]
        speed_mult = style_info["speed"]
        special = style_info.get("special")
        ranged_range = style_info.get("range", 0)

        # --- RANGED CREATURE ASSIGNMENT ---
        # Some individuals in a group become ranged attackers (archers, throwers)
        # Determined once per creature based on ranged_chance
        ranged_chance = style_info.get("ranged_chance", 0)
        if not hasattr(creature, '_is_ranged_attacker'):
            creature._is_ranged_attacker = random.random() < ranged_chance
            creature._ranged_type = style_info.get("ranged_type", "")
        is_ranged = creature._is_ranged_attacker

        # For ranged creatures, use the range field as attack range
        if is_ranged and ranged_range > 0:
            attack_range = ranged_range
        elif attack_style == "ranged" and ranged_range > 0:
            attack_range = ranged_range
        if special == "ranged_spines":
            attack_range = max(attack_range, 5.0)

        dist_sq = (creature.x - target.x) ** 2 + (creature.y - target.y) ** 2
        dist = math.sqrt(dist_sq)
        speed = getattr(creature, 'speed', 1.5)

        # --- RANGED KITING: ranged creatures maintain distance ---
        if is_ranged and ranged_range > 0:
            optimal = ranged_range * 0.7
            if dist < optimal * 0.5:
                # Too close — retreat
                dx = creature.x - target.x
                dy = creature.y - target.y
                d = math.sqrt(dx * dx + dy * dy) or 1
                creature.x += (dx / d) * speed * dt * 1.2
                creature.y += (dy / d) * speed * dt * 1.2
                return None

        # --- REGENERATE: trolls heal at start of tick ---
        if special == "regenerate":
            last_fire = getattr(creature, '_last_fire_damage_tick', -999)
            current_tick = getattr(creature, '_tick_count', 0)
            if current_tick - last_fire > 3:  # no fire damage recently
                creature.hp = min(creature.max_hp, creature.hp + 2)

        # --- MORALE: wounded creatures flee ---
        hp_pct = creature.hp / max(1, creature.max_hp)
        if hp_pct < 0.25 and not getattr(creature, '_is_arena', False):
            # Flee away from target
            dx = creature.x - target.x
            dy = creature.y - target.y
            d = math.sqrt(dx * dx + dy * dy) or 1
            creature.x += (dx / d) * speed * dt
            creature.y += (dy / d) * speed * dt
            creature.state = "fleeing"
            return None

        # Track previous distance for charge detection
        prev_dist = getattr(creature, '_prev_dist_to_target', dist)
        creature._prev_dist_to_target = dist

        # --- MOVEMENT: approach target ---
        if dist > attack_range:
            dx = target.x - creature.x
            dy = target.y - creature.y
            d = dist or 1
            move = min(speed * dt, d - (attack_range * 0.8))
            creature.x += (dx / d) * move
            creature.y += (dy / d) * move
            creature.facing = (dx / d, dy / d)
            return None

        # --- ATTACK COOLDOWN (modified by speed multiplier) ---
        attack_timer = getattr(creature, 'attack_timer', 0)
        if attack_timer > 0:
            creature.attack_timer = attack_timer - dt
            return None

        creature.attack_timer = 1.2 / speed_mult  # attack speed

        # --- ATTACK using body damage system ---
        from game.systems.body_damage import BodyDamageSystem
        _bds = BodyDamageSystem()

        damage = getattr(creature, 'damage', 5)

        # Combat modifier (wounded creatures attack weaker)
        combat_mod = _bds.get_combat_modifier(creature)
        damage = max(1, int(damage * combat_mod))

        # Military unit modifiers (formation/matchup for organized monsters)
        from game.systems.warfare import apply_unit_combat_mods
        atk_mult, def_mult = apply_unit_combat_mods(creature, target)
        damage = max(1, int(damage * atk_mult))

        # --- PACK BONUS: nearby allies of same kind boost damage ---
        pack_bonus = 0
        if attack_style == "pack" and nearby_allies:
            pack_count = sum(
                1 for a in nearby_allies
                if a is not creature and a.alive
                and getattr(a, 'kind', '').lower() == kind
                and ((a.x - creature.x) ** 2 + (a.y - creature.y) ** 2) < 64  # within 8 tiles
            )
            pack_bonus = min(pack_count, 4)  # cap at +4 allies
            damage = int(damage * (1.0 + pack_bonus * 0.15))  # +15% per ally, up to +60%

        # --- AMBUSH BONUS: first attack on this target deals double damage ---
        if attack_style == "ambush":
            targets_hit = getattr(creature, '_targets_damaged', set())
            target_id = id(target)
            if target_id not in targets_hit:
                damage *= 2  # ambush bonus
                targets_hit.add(target_id)
                creature._targets_damaged = targets_hit

        # --- CHARGE BONUS: double damage if was moving (far away last tick) ---
        if special == "charge" and prev_dist > attack_range * 1.5:
            damage *= 2

        # D20 roll
        roll = random.randint(1, 20)
        cr_bonus = min(5, int(getattr(creature, 'cr', 0.25) * 2))
        total = roll + cr_bonus

        # Pack coordination gives attack bonus too
        if pack_bonus > 0:
            total += pack_bonus

        ac = getattr(target, 'armor_class', 10)
        if def_mult > 1.0:
            ac = int(ac * def_mult)  # formation defense bonus

        if roll == 1:
            return None  # miss
        if total < ac and roll != 20:
            return None  # miss

        if roll >= 20:
            damage *= 2  # critical

        # --- LIVING SIEGE ENGINE: AoE for large ranged monsters ---
        # Large creatures with ranged attacks deal area damage like siege engines:
        # - Dragons: breath weapon (fire AoE, radius 3)
        # - Hill giants: boulder impact (blunt AoE, radius 2)
        # - Ogres/trolls: thrown rock splash (blunt AoE, radius 1.5)
        # - Ankhegs: acid spray (acid AoE, radius 2)
        # - Harpies: sonic screech (AoE, radius 3)
        # The AoE radius scales with creature CR
        SIEGE_MONSTER_AOE = {
            "breath_weapon": {"radius": 3.0, "splash_mult": 0.5},  # dragons, phoenix
            "boulder":       {"radius": 2.0, "splash_mult": 0.4},  # giants throw rocks
            "acid_spit":     {"radius": 2.0, "splash_mult": 0.5},  # ankhegs
            "screech":       {"radius": 3.0, "splash_mult": 0.3},  # harpies (sonic)
            "spell":         {"radius": 2.5, "splash_mult": 0.5},  # lich spells
            "web":           {"radius": 2.0, "splash_mult": 0.2},  # spider web (slows)
        }

        ranged_type = getattr(creature, '_ranged_type', '') or style_info.get("ranged_type", "")
        aoe_info = SIEGE_MONSTER_AOE.get(special) or SIEGE_MONSTER_AOE.get(ranged_type)

        if aoe_info and is_ranged and nearby_allies is not None:
            aoe_radius = aoe_info["radius"]
            splash_mult = aoe_info["splash_mult"]
            splash_dmg = max(1, int(damage * splash_mult))
            hits = 0
            for ent in nearby_allies:
                if ent is creature or ent is target or not getattr(ent, 'alive', True):
                    continue
                if getattr(ent, 'kind', '').lower() == kind:
                    continue  # don't hit own kind
                ex_dist = math.sqrt((ent.x - target.x)**2 + (ent.y - target.y)**2)
                if ex_dist <= aoe_radius:
                    _bds.apply_damage(ent, splash_dmg, damage_type=dmg_type, timestamp=0.0)
                    hits += 1

        actual = _bds.apply_damage(target, damage, damage_type=dmg_type,
                                    timestamp=0.0)

        # --- POST-HIT SPECIAL ABILITIES ---

        # Poison: 10% chance to add extra damage
        if special == "poison" and random.random() < 0.10:
            cr = getattr(creature, 'cr', 0.25)
            poison_dmg = max(1, int(3 + cr))
            _bds.apply_damage(target, poison_dmg, damage_type="blunt", timestamp=0.0)
            actual += poison_dmg

        # Drain: heal attacker for 50% of damage dealt
        if special == "drain":
            heal = max(1, actual // 2)
            creature.hp = min(creature.max_hp, creature.hp + heal)

        # Track fire damage for regeneration suppression
        if dmg_type == "fire":
            target._last_fire_damage_tick = getattr(target, '_tick_count', 0)

        creature_name = getattr(creature, 'kind', 'creature')
        target_name = getattr(target, 'name', getattr(target, 'kind', 'target'))

        # --- FLYER HIT-AND-RUN: move away after attacking ---
        if attack_style == "flyer":
            dx = creature.x - target.x
            dy = creature.y - target.y
            d = math.sqrt(dx * dx + dy * dy) or 1
            creature.x += (dx / d) * 2.0
            creature.y += (dy / d) * 2.0

        if not getattr(target, 'alive', True):
            return f"{creature_name} killed {target_name}! ({actual} {dmg_type})"

        suffix = ""
        if pack_bonus > 0:
            suffix = f" [pack +{pack_bonus}]"
        if special == "poison" and random.random() < 0.10:
            suffix += " [poisoned]"

        return f"{creature_name} hits {target_name} for {actual} {dmg_type}{suffix}"
