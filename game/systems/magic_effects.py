"""Magic effects: spell casting, buffs/debuffs, mana, enchanting, alchemy.

Contains:
- SpellEffect class: temporary effects applied to entities
- Mana system: init, regen, max mana calculation
- Spell learning: can_learn_spell, learn_spell, auto_learn_spells_for_class
- Spell casting: can_cast, cast_spell with full effect resolution
- Status/buff effect helpers
- Effect query helpers: get_speed_modifier, get_attack_modifier, etc.
- update_magic: per-frame mana regen, cooldowns, effect ticking
- Enchanting system: weapon/armor enchantments with reagents
- Alchemy system: potion brewing
- Combat integration: integrate_magic_into_combat
- Spell visual helpers: get_spell_visual
- Supply chain integration
"""

import math
from typing import List, Optional, Dict, Tuple, Any

from game.settings import *
from game.systems.magic_spells import (
    Spell, SPELL_REGISTRY, SOUL_SPELLS, MAGIC_SCHOOLS,
    CLASS_SCHOOL_AFFINITY, PRACTITIONER_SPELLS, MAGIC_ITEMS,
    SPELL_COMPONENTS,
)


# ================================================================
# ACTIVE SPELL EFFECT (applied to entities)
# ================================================================

class SpellEffect:
    """A temporary effect applied to an entity by a spell."""

    def __init__(self, name: str, effect_type: str, value: float,
                 duration: float, source_name: str = ""):
        self.name = name              # e.g. "burn", "slow", "shield"
        self.effect_type = effect_type  # "damage_over_time", "slow", "stun",
                                        # "root", "shield", "buff_attack",
                                        # "buff_defense", "pacify", "soul_sight"
        self.value = value            # magnitude (damage per tick, slow %, shield hp, etc.)
        self.duration = duration      # remaining seconds
        self.source_name = source_name
        self.tick_timer = 0.0         # for DoT effects

    def update(self, dt: float, entity) -> Optional[str]:
        """Tick the effect. Returns a message if something notable happens."""
        self.duration -= dt
        msg = None

        if self.effect_type == "damage_over_time":
            self.tick_timer += dt
            if self.tick_timer >= 1.0:
                self.tick_timer -= 1.0
                actual = entity.take_damage(int(self.value))
                msg = f"{getattr(entity, 'name', 'Target')} takes {actual} {self.name} damage"

        return msg

    @property
    def expired(self) -> bool:
        return self.duration <= 0


# ================================================================
# MANA SYSTEM
# ================================================================

# Mana regen rates (per second)
MANA_REGEN_BASE = 1.0
MANA_REGEN_RESTING = 3.0
MANA_REGEN_TEMPLE = 5.0


def calc_max_mana(intelligence: int, level: int) -> int:
    """Calculate maximum mana from intelligence score and level."""
    from game.data.dnd import ability_modifier
    int_mod = ability_modifier(intelligence)
    return max(20, 30 + int_mod * 8 + level * 5)


def get_mana_regen_rate(entity, world=None) -> float:
    """Determine mana regeneration rate based on context."""
    rate = MANA_REGEN_BASE

    # Resting bonus
    state = getattr(entity, 'state', '')
    if state in ('sleeping', 'resting'):
        rate = MANA_REGEN_RESTING

    # Wisdom bonus
    wis = 10
    scores = getattr(entity, 'ability_scores', None)
    if scores:
        wis = scores.get('wisdom', 10)
    from game.data.dnd import ability_modifier
    wis_mod = ability_modifier(wis)
    rate += max(0, wis_mod * 0.3)

    return rate


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

def can_learn_spell(entity, spell_name: str) -> Tuple[bool, str]:
    """Check if an entity can learn a spell. Returns (ok, reason)."""
    spell = SPELL_REGISTRY.get(spell_name) or SOUL_SPELLS.get(spell_name)
    if spell is None:
        return False, f"Unknown spell: {spell_name}"

    init_mana(entity)

    # Already known?
    if spell_name in entity.magic_known_spells:
        return False, f"Already knows {spell_name}"

    # Level check
    level = getattr(entity, 'level', 1)
    if level < spell.level_required:
        return False, f"Requires level {spell.level_required} (have {level})"

    # Intelligence check (uses spell level for scaling)
    scores = getattr(entity, 'ability_scores', {})
    intelligence = scores.get('intelligence', 10)
    min_int = spell.required_intelligence  # 8 + level * 2
    if intelligence < min_int:
        return False, f"Requires {min_int} INT (have {intelligence})"

    # Practitioner class spell level cap check
    char_class = getattr(entity, 'char_class', '')
    prac = PRACTITIONER_SPELLS.get(char_class)
    if prac:
        if spell.level > prac.get("max_level", 9):
            return False, f"{char_class} cannot learn spells above level {prac['max_level']}"
        # Check school access
        allowed_schools = prac.get("schools", [])
        if allowed_schools and spell.school not in allowed_schools:
            # Still allow if INT is very high (18+)
            if intelligence < 18:
                return False, f"{char_class} cannot access {spell.school} school"

    # School affinity check (soul spells need divine or arcane >= 0.3)
    if spell_name in SOUL_SPELLS:
        divine_aff = entity.school_affinity.get("divine", 0)
        arcane_aff = entity.school_affinity.get("arcane", 0)
        if divine_aff < 0.3 and arcane_aff < 0.3:
            return False, "Requires divine or arcane affinity"
    else:
        school_aff = entity.school_affinity.get(spell.school, 0)
        # Non-affinity schools need higher threshold
        if school_aff < 0.1:
            # Can still learn if INT is very high
            if intelligence < 16:
                return False, f"No affinity for {spell.school} school"

    return True, "OK"


def learn_spell(entity, spell_name: str) -> str:
    """Attempt to teach a spell to an entity. Returns result message."""
    ok, reason = can_learn_spell(entity, spell_name)
    if not ok:
        return f"Cannot learn {spell_name}: {reason}"

    init_mana(entity)
    entity.magic_known_spells.append(spell_name)

    # Boost school affinity slightly
    spell = SPELL_REGISTRY.get(spell_name) or SOUL_SPELLS.get(spell_name)
    if spell:
        old = entity.school_affinity.get(spell.school, 0)
        entity.school_affinity[spell.school] = min(1.0, old + 0.1)

    return f"Learned {spell_name}!"


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

def can_cast(entity, spell_name: str) -> Tuple[bool, str]:
    """Check whether entity can cast a spell right now."""
    init_mana(entity)

    spell = SPELL_REGISTRY.get(spell_name) or SOUL_SPELLS.get(spell_name)
    if spell is None:
        return False, "Unknown spell"

    if spell_name not in entity.magic_known_spells:
        return False, "Spell not known"

    if entity.mana < spell.mana_cost:
        return False, f"Not enough mana ({entity.mana}/{spell.mana_cost})"

    cd = entity.spell_cooldowns.get(spell_name, 0)
    if cd > 0:
        return False, f"On cooldown ({cd:.1f}s)"

    # Stunned/silenced check
    for eff in getattr(entity, 'active_spell_effects', []):
        if eff.effect_type == "stun" and not eff.expired:
            return False, "Stunned!"
        if eff.effect_type == "root" and spell_name == "teleport":
            return False, "Rooted! Cannot teleport"
        if eff.effect_type == "fear" and not eff.expired:
            return False, "Too frightened to cast!"

    # Spell component check for high-level spells
    if spell.components:
        inv = getattr(entity, 'inventory', getattr(entity, 'npc_inventory', []))
        for comp in spell.components:
            found = False
            for item in inv:
                if getattr(item, 'name', '').lower().replace(' ', '_') == comp:
                    found = True
                    break
            if not found:
                return False, f"Missing component: {comp}"

    return True, "OK"


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


def _make_status_effect(spell: Spell,
                        duration_override: float = None) -> SpellEffect:
    """Create a SpellEffect from a spell's status effect."""
    etype_map = {
        "burn": "damage_over_time",
        "slow": "slow",
        "stun": "stun",
        "root": "root",
        "pacify": "pacify",
        "fear": "fear",
    }
    etype = etype_map.get(spell.status_effect, spell.status_effect)
    value = 0
    if spell.status_effect == "burn":
        value = 5  # 5 damage per second
    elif spell.status_effect == "slow":
        value = 0.5  # 50% speed reduction
    elif spell.status_effect == "stun":
        value = 1.0  # full stun
    elif spell.status_effect == "root":
        value = 1.0  # full root
    elif spell.status_effect == "pacify":
        value = 1.0
    elif spell.status_effect == "fear":
        value = 1.0  # full fear (flee behavior)

    dur = duration_override if duration_override is not None else spell.status_duration
    return SpellEffect(spell.status_effect, etype, value, dur, spell.name)


def _make_buff_effect(spell: Spell,
                      duration_override: float = None) -> SpellEffect:
    """Create a buff SpellEffect from a spell."""
    dur = duration_override if duration_override is not None else spell.duration
    if spell.name == "bless":
        return SpellEffect("bless", "buff_attack_defense", 3.0,
                           dur, spell.name)
    elif spell.name == "shield":
        return SpellEffect("shield", "shield", 30.0,
                           dur, spell.name)
    elif spell.name == "sanctuary":
        return SpellEffect("sanctuary", "shield", 50.0,
                           dur, spell.name)
    elif spell.name == "growth":
        return SpellEffect("growth", "regen", 3.0,
                           dur, spell.name)
    else:
        return SpellEffect(spell.name, "buff_generic", 1.0,
                           dur, spell.name)


def _dist(a, b) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    return math.sqrt(dx * dx + dy * dy)


def _grant_cast_xp(caster, spell: Spell):
    """Grant spellcraft skill XP when casting."""
    if hasattr(caster, 'gain_skill_xp'):
        caster.gain_skill_xp("spellcraft", 0.5 + spell.mana_cost * 0.05)


# ================================================================
# MAGIC UPDATE (called each frame for entities with mana)
# ================================================================

def update_magic(entity, dt: float, world=None):
    """Per-frame update: mana regen, cooldowns, spell effects."""
    if not hasattr(entity, 'mana'):
        return

    # Mana regeneration
    if entity.mana < entity.max_mana and getattr(entity, 'alive', True):
        regen = get_mana_regen_rate(entity, world)
        entity.mana = min(entity.max_mana, entity.mana + regen * dt)

    # Tick cooldowns
    cds = getattr(entity, 'spell_cooldowns', {})
    for name in list(cds.keys()):
        cds[name] -= dt
        if cds[name] <= 0:
            del cds[name]

    # Tick active spell effects
    effects = getattr(entity, 'active_spell_effects', [])
    expired = []
    for eff in effects:
        msg = eff.update(dt, entity)
        if eff.expired:
            expired.append(eff)

    for eff in expired:
        effects.remove(eff)
        # Clean up effect side-effects
        if eff.effect_type == "pacify" and hasattr(entity, 'passive'):
            # Re-aggro when pacify wears off (creature)
            entity.passive = getattr(entity, '_original_passive', False)


def get_speed_modifier(entity) -> float:
    """Return speed multiplier from active spell effects (slow/root/stun)."""
    mult = 1.0
    for eff in getattr(entity, 'active_spell_effects', []):
        if eff.expired:
            continue
        if eff.effect_type == "slow":
            mult *= eff.value  # value is the multiplier (0.5 = half speed)
        elif eff.effect_type in ("stun", "root"):
            mult = 0.0
    return mult


def get_attack_modifier(entity) -> int:
    """Return attack bonus from active buff effects."""
    bonus = 0
    for eff in getattr(entity, 'active_spell_effects', []):
        if eff.expired:
            continue
        if eff.effect_type == "buff_attack_defense":
            bonus += int(eff.value)
    return bonus


def get_defense_modifier(entity) -> int:
    """Return defense bonus from active buff effects."""
    bonus = 0
    for eff in getattr(entity, 'active_spell_effects', []):
        if eff.expired:
            continue
        if eff.effect_type == "buff_attack_defense":
            bonus += int(eff.value)
    return bonus


def absorb_damage(entity, damage: int) -> int:
    """Check for shield effects that absorb damage. Returns remaining damage."""
    for eff in getattr(entity, 'active_spell_effects', []):
        if eff.expired:
            continue
        if eff.effect_type == "shield" and eff.value > 0:
            absorbed = min(damage, int(eff.value))
            eff.value -= absorbed
            damage -= absorbed
            if eff.value <= 0:
                eff.duration = 0  # expire the shield
            if damage <= 0:
                return 0
    return damage


def has_effect(entity, effect_name: str) -> bool:
    """Check if an entity has a specific active spell effect."""
    for eff in getattr(entity, 'active_spell_effects', []):
        if eff.name == effect_name and not eff.expired:
            return True
    return False
