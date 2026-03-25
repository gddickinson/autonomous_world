"""NPC magic AI: spell selection and casting logic.

Contains:
- npc_choose_spell: AI to pick the best spell for a given situation
- npc_cast_spell: execute an NPC spell cast
"""

import math
from typing import List, Optional, Tuple, Any, Dict

from game.systems.magic_spells import SPELL_REGISTRY
from game.systems.magic_effects import (
    init_mana, can_cast, cast_spell, has_effect,
)


def _dist(a, b) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    return math.sqrt(dx * dx + dy * dy)


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
