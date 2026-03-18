"""Spell casting — mana, spell selection, NPC AI for spells."""

import random
import math
from typing import List, Dict, Optional, Tuple
from game.settings import *

def init_mana(entity):
    """Initialize mana attributes on a player or NPC.

    Safe to call multiple times -- skips if already initialized.
    """
    if hasattr(entity, 'mana') and hasattr(entity, 'max_mana'):
        return  # already initialized

    scores = getattr(entity, 'ability_scores', {})
    intelligence = scores.get('intelligence', 10)
    level = getattr(entity, 'level', 1)
    entity.max_mana = calc_max_mana(intelligence, level)
    entity.mana = entity.max_mana

    # Spell cooldown tracking: spell_name -> remaining cooldown
    if not hasattr(entity, 'spell_cooldowns'):
        entity.spell_cooldowns = {}

    # Active spell effects on this entity
    if not hasattr(entity, 'active_spell_effects'):
        entity.active_spell_effects = []

    # Magic-system known spells (coexists with D&D spell_list in known_spells)
    if not hasattr(entity, 'magic_known_spells'):
        entity.magic_known_spells = []

    # School affinity: school_name -> proficiency (0.0 - 1.0)
    if not hasattr(entity, 'school_affinity'):
        entity.school_affinity = {}
        # Set affinity from D&D class
        char_class = getattr(entity, 'char_class', '')
        school = CLASS_SCHOOL_AFFINITY.get(char_class)
        if school:
            entity.school_affinity[school] = 0.5


# ================================================================
# SPELL LEARNING
# ================================================================

def auto_learn_spells_for_class(entity):
    """Give an entity starting spells based on their D&D class.

    Called during entity initialization. Uses PRACTITIONER_SPELLS to determine
    which schools and spell levels the class can access.
    """
    init_mana(entity)
    char_class = getattr(entity, 'char_class', '')
    level = getattr(entity, 'level', 1)

    prac = PRACTITIONER_SPELLS.get(char_class)
    if not prac:
        # Fall back to old single-school affinity
        school = CLASS_SCHOOL_AFFINITY.get(char_class)
        if not school:
            return  # non-caster class
        school_data = MAGIC_SCHOOLS.get(school, {})
        available = school_data.get("spells", [])
        for sp_name in available:
            sp = SPELL_REGISTRY.get(sp_name)
            if sp and sp.level_required <= level:
                if sp_name not in entity.magic_known_spells:
                    entity.magic_known_spells.append(sp_name)
        entity.school_affinity[school] = min(1.0, 0.3 + level * 0.1)
        return

    max_spell_level = prac.get("max_level", 0)
    allowed_schools = prac.get("schools", [])

    # Learn spells from all allowed schools up to level allowance
    for school_name in allowed_schools:
        school_data = MAGIC_SCHOOLS.get(school_name, {})
        available = school_data.get("spells", [])
        for sp_name in available:
            sp = SPELL_REGISTRY.get(sp_name)
            if sp and sp.level_required <= level and sp.level <= max_spell_level:
                if sp_name not in entity.magic_known_spells:
                    entity.magic_known_spells.append(sp_name)
        # Set school affinity based on class level
        entity.school_affinity[school_name] = min(1.0, 0.3 + level * 0.1)


# ================================================================
# SPELL CASTING
# ================================================================

def cast_spell(caster, spell_name: str, target=None,
               target_pos: Tuple[float, float] = None,
               entities_nearby: List = None) -> Dict[str, Any]:
    """Execute a spell cast. Returns a result dict with messages and effects.

    Parameters:
        caster: the entity casting (Player or NPC)
        spell_name: name of the spell
        target: a specific target entity (or None for AoE/self)
        target_pos: (x, y) target position for positional spells
        entities_nearby: list of entities in range for AoE/chain spells

    Returns dict with keys:
        "success": bool
        "message": str
        "damage_dealt": dict of entity -> damage
        "healing_done": dict of entity -> healing
        "effects_applied": list of (entity, SpellEffect)
        "spell": the Spell object
    """
    ok, reason = can_cast(caster, spell_name)
    result = {
        "success": False, "message": reason,
        "damage_dealt": {}, "healing_done": {},
        "effects_applied": [], "spell": None,
    }
    if not ok:
        return result

    spell = SPELL_REGISTRY.get(spell_name) or SOUL_SPELLS.get(spell_name)
    result["spell"] = spell

    # Spend mana and set cooldown
    caster.mana -= spell.mana_cost
    caster.spell_cooldowns[spell_name] = spell.cooldown

    entities_nearby = entities_nearby or []

    # -- Resolve targets --
    targets_hit = []
    allies_hit = []

    if spell.targets == "self":
        targets_hit = [caster]
        allies_hit = [caster]

    elif spell.targets == "single":
        if target is not None:
            dist = _dist(caster, target)
            if dist <= spell.range_tiles:
                targets_hit = [target]
            else:
                result["message"] = "Target out of range"
                # Refund mana on range failure
                caster.mana += spell.mana_cost
                caster.spell_cooldowns[spell_name] = 0
                return result
        else:
            result["message"] = "No target"
            caster.mana += spell.mana_cost
            caster.spell_cooldowns[spell_name] = 0
            return result

    elif spell.targets == "ally":
        if target is not None:
            dist = _dist(caster, target)
            if dist <= spell.range_tiles:
                allies_hit = [target]
            else:
                result["message"] = "Target out of range"
                caster.mana += spell.mana_cost
                caster.spell_cooldowns[spell_name] = 0
                return result
        else:
            # Self-target for ally spells with no target
            allies_hit = [caster]

    elif spell.targets == "aoe":
        cx, cy = target_pos if target_pos else (caster.x, caster.y)
        for ent in entities_nearby:
            if not getattr(ent, 'alive', True):
                continue
            d = math.sqrt((ent.x - cx) ** 2 + (ent.y - cy) ** 2)
            if d <= spell.area:
                if spell.effect_type == "buff":
                    allies_hit.append(ent)
                else:
                    # Don't hit caster with own AoE damage
                    if ent is not caster:
                        targets_hit.append(ent)
        # For self-cast AoE buffs, always include caster
        if spell.effect_type == "buff" and caster not in allies_hit:
            allies_hit.append(caster)

    elif spell.targets == "chain":
        if target is not None:
            targets_hit = [target]
            # Chain to additional nearby enemies
            remaining = spell.chain_count - 1
            last = target
            used = {id(target)}
            for ent in sorted(entities_nearby,
                              key=lambda e: _dist(last, e)):
                if remaining <= 0:
                    break
                if id(ent) in used or ent is caster:
                    continue
                if not getattr(ent, 'alive', True):
                    continue
                if _dist(last, ent) <= 4.0:  # chain range
                    targets_hit.append(ent)
                    used.add(id(ent))
                    last = ent
                    remaining -= 1

    # -- Apply spell effects --
    messages = []

    # Damage
    if spell.damage > 0:
        for t in targets_hit:
            dmg = spell.damage
            # Smite undead bonus
            if spell_name == "smite_undead":
                mtype = getattr(t, 'monster_type', '')
                if mtype != 'undead':
                    dmg = dmg // 3  # reduced damage to non-undead

            # School affinity damage bonus
            aff = caster.school_affinity.get(spell.school, 0)
            dmg = int(dmg * (1.0 + aff * 0.3))

            # Intelligence scaling
            scores = getattr(caster, 'ability_scores', {})
            stat_name = MAGIC_SCHOOLS.get(spell.school, {}).get("stat", "intelligence")
            stat_val = scores.get(stat_name, 10)
            from game.data.dnd import ability_modifier
            stat_mod = ability_modifier(stat_val)
            dmg += stat_mod * 2

            actual = t.take_damage(max(1, dmg))
            result["damage_dealt"][t] = actual
            name = getattr(t, 'name', getattr(t, 'kind', 'target'))
            messages.append(f"{name} takes {actual} {spell.school} damage")

            if not getattr(t, 'alive', True):
                messages.append(f"{name} was slain!")

    # Healing
    if spell.heal > 0:
        heal_targets = allies_hit if allies_hit else targets_hit
        for t in heal_targets:
            # Resurrect special handling
            if spell_name == "resurrect":
                if not getattr(t, 'alive', True):
                    t.alive = True
                    t.hp = spell.heal
                    name = getattr(t, 'name', 'target')
                    messages.append(f"{name} has been resurrected!")
                    result["healing_done"][t] = spell.heal
                continue

            if not getattr(t, 'alive', True):
                continue
            old_hp = t.hp
            t.heal(spell.heal)
            healed = t.hp - old_hp
            result["healing_done"][t] = healed
            name = getattr(t, 'name', getattr(t, 'kind', 'target'))
            if healed > 0:
                messages.append(f"{name} healed for {healed}")

    # Cure poison
    if spell_name == "cure_poison":
        heal_targets = allies_hit if allies_hit else [caster]
        for t in heal_targets:
            conditions = getattr(t, 'conditions', [])
            removed = []
            for c in conditions:
                ckey = getattr(c, 'key', '')
                if 'poison' in ckey.lower() or 'disease' in ckey.lower():
                    removed.append(c)
            for c in removed:
                conditions.remove(c)
            if removed:
                name = getattr(t, 'name', 'target')
                messages.append(f"Cured {len(removed)} ailment(s) from {name}")

    # Status effects (burn, slow, stun, root, pacify)
    if spell.status_effect:
        effect_targets = targets_hit
        for t in effect_targets:
            eff = _make_status_effect(spell)
            if not hasattr(t, 'active_spell_effects'):
                t.active_spell_effects = []
            t.active_spell_effects.append(eff)
            result["effects_applied"].append((t, eff))
            name = getattr(t, 'name', getattr(t, 'kind', 'target'))
            messages.append(f"{name} is {spell.status_effect}{'ed' if not spell.status_effect.endswith('e') else 'd'}!")

    # Knockback
    if spell.knockback > 0:
        for t in targets_hit:
            dx = t.x - caster.x
            dy = t.y - caster.y
            dist = math.sqrt(dx * dx + dy * dy) or 1
            t.x += (dx / dist) * spell.knockback
            t.y += (dy / dist) * spell.knockback

    # Buff effects (bless, shield, sanctuary)
    if spell.effect_type == "buff" and spell.duration > 0:
        buff_targets = allies_hit if allies_hit else [caster]
        for t in buff_targets:
            eff = _make_buff_effect(spell)
            if not hasattr(t, 'active_spell_effects'):
                t.active_spell_effects = []
            t.active_spell_effects.append(eff)
            result["effects_applied"].append((t, eff))

        if spell_name == "bless":
            messages.append("Allies are blessed! +3 attack and defense")
        elif spell_name == "shield":
            messages.append("Arcane shield active! Absorbing up to 30 damage")
        elif spell_name == "sanctuary":
            messages.append("Holy sanctuary active! Absorbing up to 50 damage")
        elif spell_name == "growth":
            messages.append("Nature surges with vitality!")

    # Utility spells
    if spell_name == "teleport":
        if target_pos:
            caster.x, caster.y = target_pos
            messages.append(f"Teleported to ({int(target_pos[0])}, {int(target_pos[1])})")
        else:
            # Teleport in facing direction
            fx, fy = getattr(caster, 'facing', (0, 1))
            caster.x += fx * spell.range_tiles
            caster.y += fy * spell.range_tiles
            messages.append(f"Teleported forward!")

    if spell_name == "detect_magic":
        eff = SpellEffect("detect_magic", "detect_magic", 1.0,
                          spell.duration, getattr(caster, 'name', ''))
        if not hasattr(caster, 'active_spell_effects'):
            caster.active_spell_effects = []
        caster.active_spell_effects.append(eff)
        result["effects_applied"].append((caster, eff))
        messages.append("Magical auras revealed!")

    if spell_name == "dispel":
        if target is not None:
            effects = getattr(target, 'active_spell_effects', [])
            count = len(effects)
            target.active_spell_effects = []
            # Also try to remove curses from health conditions
            conditions = getattr(target, 'conditions', [])
            cursed = [c for c in conditions
                      if 'curse' in getattr(c, 'key', '').lower()]
            for c in cursed:
                conditions.remove(c)
            count += len(cursed)
            name = getattr(target, 'name', 'target')
            messages.append(f"Dispelled {count} effect(s) from {name}")

    if spell_name == "animal_friend":
        if target is not None:
            mtype = getattr(target, 'monster_type', '')
            if mtype == 'beast':
                target.passive = True
                # Mark as pacified
                if hasattr(target, 'combat_target'):
                    target.combat_target = None
                name = getattr(target, 'name', getattr(target, 'kind', 'beast'))
                messages.append(f"{name} is calmed and non-hostile")
            else:
                messages.append("Animal Friend only works on beasts")

    # -- Soul magic special handling --
    if spell_name == "soul_sight":
        eff = SpellEffect("soul_sight", "soul_sight", 1.0,
                          spell.duration, getattr(caster, 'name', ''))
        if not hasattr(caster, 'active_spell_effects'):
            caster.active_spell_effects = []
        caster.active_spell_effects.append(eff)
        result["effects_applied"].append((caster, eff))
        messages.append("You can now perceive ghost souls...")

    if spell_name == "soul_ward":
        eff = SpellEffect("soul_ward", "soul_ward", spell.area,
                          spell.duration, getattr(caster, 'name', ''))
        if not hasattr(caster, 'active_spell_effects'):
            caster.active_spell_effects = []
        caster.active_spell_effects.append(eff)
        result["effects_applied"].append((caster, eff))
        messages.append(f"Soul ward active in {spell.area:.0f} tile radius")

    if spell_name == "soul_speak":
        # The actual ghost interaction is handled by the caller
        messages.append("You reach out to the spirit world...")

    if spell_name == "exorcism":
        if target is not None:
            mtype = getattr(target, 'monster_type', '')
            if mtype == 'undead':
                # Extra holy damage to undead
                bonus = 20
                actual = target.take_damage(bonus)
                result["damage_dealt"][target] = result["damage_dealt"].get(target, 0) + actual
                messages.append(f"Exorcism tears {actual} additional damage from the undead!")
                # Release souls (handled by soul system integration)
            else:
                messages.append("Exorcism only affects undead")

    # Grant skill XP for casting
    _grant_cast_xp(caster, spell)

    result["success"] = True
    result["message"] = "; ".join(messages) if messages else f"Cast {spell_name}!"

    # Store pending spell visual for renderer to pick up
    target_x = target.x if target and hasattr(target, 'x') else caster.x
    target_y = target.y if target and hasattr(target, 'y') else caster.y
    if target_pos:
        target_x, target_y = target_pos
    if not hasattr(caster, '_pending_spell_visuals'):
        caster._pending_spell_visuals = []
    caster._pending_spell_visuals.append({
        "spell_name": spell_name,
        "x": caster.x, "y": caster.y,
        "target_x": target_x, "target_y": target_y,
    })

    return result


def npc_choose_spell(npc, enemies: List, allies: List) -> Optional[Tuple[str, Any]]:
    """NPC AI: pick the best spell to cast given the situation.

    Returns (spell_name, target) or None.
    """
    init_mana(npc)
    known = getattr(npc, 'magic_known_spells', [])
    if not known:
        return None

    # Priority: heal self/allies if low HP, then offensive
    npc_hp_pct = npc.hp / max(1, npc.max_hp)

    # Heal self if low
    if npc_hp_pct < 0.4 and "heal" in known:
        ok, _ = can_cast(npc, "heal")
        if ok:
            return ("heal", npc)

    # Heal low-HP ally
    for ally in allies:
        if not getattr(ally, 'alive', True):
            continue
        ally_hp_pct = ally.hp / max(1, ally.max_hp)
        if ally_hp_pct < 0.3 and "heal" in known:
            ok, _ = can_cast(npc, "heal")
            if ok and _dist(npc, ally) <= 3:
                return ("heal", ally)

    # Resurrect dead ally
    if "resurrect" in known:
        for ally in allies:
            if not getattr(ally, 'alive', True) and _dist(npc, ally) <= 1:
                ok, _ = can_cast(npc, "resurrect")
                if ok:
                    return ("resurrect", ally)

    # Bless if not already active and there are allies nearby
    if "bless" in known and not has_effect(npc, "bless"):
        ok, _ = can_cast(npc, "bless")
        if ok and (allies or enemies):
            return ("bless", None)

    # Shield/sanctuary if about to fight and not shielded
    if enemies:
        if "sanctuary" in known and not has_effect(npc, "sanctuary"):
            ok, _ = can_cast(npc, "sanctuary")
            if ok:
                return ("sanctuary", None)
        if "shield" in known and not has_effect(npc, "shield"):
            ok, _ = can_cast(npc, "shield")
            if ok:
                return ("shield", None)

    # Offensive spells
    if not enemies:
        return None

    # Find nearest enemy
    nearest = min(enemies, key=lambda e: _dist(npc, e))
    dist = _dist(npc, nearest)

    # Prioritize AoE if multiple enemies nearby
    clustered = sum(1 for e in enemies if _dist(nearest, e) < 3)

    # Undead-specific
    mtype = getattr(nearest, 'monster_type', '')
    if mtype == 'undead' and "smite_undead" in known:
        ok, _ = can_cast(npc, "smite_undead")
        if ok and dist <= 5:
            return ("smite_undead", nearest)

    if mtype == 'undead' and "exorcism" in known:
        ok, _ = can_cast(npc, "exorcism")
        if ok and dist <= 4:
            return ("exorcism", nearest)

    # AoE preference
    if clustered >= 3:
        for sp_name in ["fireball", "earthquake", "storm_call"]:
            if sp_name in known:
                ok, _ = can_cast(npc, sp_name)
                spell = SPELL_REGISTRY.get(sp_name)
                if ok and spell and dist <= spell.range_tiles:
                    return (sp_name, nearest)

    # Entangle if enemies are approaching
    if "entangle" in known and dist < 6:
        ok, _ = can_cast(npc, "entangle")
        if ok:
            return ("entangle", nearest)

    # Single target damage
    for sp_name in ["lightning_bolt", "ice_shard", "magic_missile"]:
        if sp_name in known:
            ok, _ = can_cast(npc, sp_name)
            spell = SPELL_REGISTRY.get(sp_name)
            if ok and spell and dist <= spell.range_tiles:
                return (sp_name, nearest)

    # Wind gust if enemy is very close
    if "wind_gust" in known and dist < 3:
        ok, _ = can_cast(npc, "wind_gust")
        if ok:
            return ("wind_gust", nearest)

    # Animal friend for beasts
    beast_type = getattr(nearest, 'monster_type', '')
    if beast_type == 'beast' and "animal_friend" in known:
        ok, _ = can_cast(npc, "animal_friend")
        if ok and dist <= 5:
            return ("animal_friend", nearest)

    return None


def npc_cast_spell(npc, spell_name: str, target, entities_nearby: List) -> Dict:
    """Execute an NPC spell cast."""
    target_pos = (target.x, target.y) if target else None
    return cast_spell(npc, spell_name, target=target,
                      target_pos=target_pos,
                      entities_nearby=entities_nearby)


# ================================================================
# SPELL EFFECT RENDERING HELPERS
# ================================================================

def integrate_magic_into_combat(damage: int, attacker, target) -> int:
    """Modify melee/ranged damage with enchantment bonuses and spell buffs.

    Called from CombatSystem to add magic modifiers to attacks.
    """
    # Attack buff from spells (bless, etc.)
    damage += get_attack_modifier(attacker)

    # Weapon enchantment bonus
    weapon = getattr(attacker, 'equipped_weapon', None)
    if weapon and hasattr(weapon, 'enchantment') and weapon.enchantment:
        ench = weapon.enchantment
        if ench.active:
            damage += ench.damage_bonus
            ench.use_charge()

    # Target defense buff from spells
    damage -= get_defense_modifier(target)

    # Shield absorption
    damage = absorb_damage(target, max(0, damage))

    # Armor enchantment resistance (not applied here -- applied per damage type)

    return max(1, damage)



