"""Combat depth improvements — shield blocking, dodge/roll, surrender mechanics.

Phase 3 combat enhancements:
- Shield blocking: active defense with durability
- Dodge/roll: light armor evasion with DEX scaling and cooldown
- Surrender: NPCs/creatures below 20% HP may surrender
- Battle pacing: casualty caps for large-scale battles
"""

import random
import math
import time
from typing import Optional, List, Dict, Any

from game.systems.combat import _pending_combat_visuals


# ---------------------------------------------------------------------------
# Dodge / Roll — light armor evasion
# ---------------------------------------------------------------------------

# Heavy armor name substrings — characters wearing these cannot dodge
_HEAVY_ARMOR_KEYWORDS = {"chain", "plate", "splint", "half plate", "ring mail",
                         "scale mail", "breastplate"}

# Light armor name substrings (these allow dodging)
_LIGHT_ARMOR_KEYWORDS = {"leather", "hide", "padded", "studded"}

# Dodge cooldown tracking: entity id -> last dodge timestamp
_dodge_cooldowns: Dict[int, float] = {}

# Constants
DODGE_COOLDOWN_SECONDS = 2.0
DODGE_BASE_CHANCE = 0.15       # 15% base
DODGE_DEX_SCALE = 0.03         # +3% per DEX modifier point
DODGE_MAX_CHANCE = 0.35        # 35% cap
HEAVY_ARMOR_DEFENSE_THRESHOLD = 5  # armor.defense > 5 = heavy


def get_equipped_armor(entity):
    """Return the equipped armor item for an entity, or None."""
    armor = getattr(entity, 'equipped_armor', None)
    if armor is not None:
        return armor
    # Check NPC inventory for armor-type items (non-shield)
    inventory = getattr(entity, 'npc_inventory', [])
    for item in inventory:
        if getattr(item, 'defense', 0) > 0 and not _is_shield(item):
            return item
    return None


def _is_heavy_armor(armor) -> bool:
    """Check if armor is heavy (chain, plate, etc.) by name or defense value."""
    if armor is None:
        return False
    # Check defense threshold
    if getattr(armor, 'defense', 0) > HEAVY_ARMOR_DEFENSE_THRESHOLD:
        return True
    # Check name keywords
    name = getattr(armor, 'name', '').lower()
    return any(kw in name for kw in _HEAVY_ARMOR_KEYWORDS)


def _get_dodge_chance(entity) -> float:
    """Calculate dodge chance: 15% base + DEX modifier * 3%, capped at 35%."""
    ability_scores = getattr(entity, 'ability_scores', {})
    dex = ability_scores.get("dexterity", 10)
    from game.data.dnd import ability_modifier
    dex_mod = ability_modifier(dex)

    chance = DODGE_BASE_CHANCE + dex_mod * DODGE_DEX_SCALE
    return max(0.0, min(DODGE_MAX_CHANCE, chance))


def _emit_dodge(target):
    """Queue a 'DODGE!' floating text visual event."""
    _pending_combat_visuals.append({
        "type": "dodge",
        "target": target,
        "damage": 0,
        "text": "DODGE!",
        "x": getattr(target, 'x', 0),
        "y": getattr(target, 'y', 0),
    })


def try_dodge(target) -> bool:
    """Attempt to dodge an incoming attack.

    Light armor (leather, hide) or no armor characters can dodge.
    Heavy armor (chain, plate, defense > 5) prevents dodging.
    15% base chance + DEX modifier * 3%, capped at 35%.
    2-second cooldown between successful dodges.

    Returns True if the attack is dodged (0 damage).
    """
    # Heavy armor wearers cannot dodge
    armor = get_equipped_armor(target)
    if armor and _is_heavy_armor(armor):
        return False

    # Check dodge cooldown (2-second window)
    eid = id(target)
    now = time.monotonic()
    last_dodge = _dodge_cooldowns.get(eid, 0.0)
    if now - last_dodge < DODGE_COOLDOWN_SECONDS:
        return False

    dodge_chance = _get_dodge_chance(target)
    if dodge_chance <= 0:
        return False

    if random.random() < dodge_chance:
        _dodge_cooldowns[eid] = now
        _emit_dodge(target)
        return True

    return False


def clear_dodge_cooldowns():
    """Clear dodge cooldown tracking (call on world reset/new game)."""
    _dodge_cooldowns.clear()


# ---------------------------------------------------------------------------
# Shield Blocking
# ---------------------------------------------------------------------------

# Shield items recognized for blocking (name substring -> base block chance)
SHIELD_ITEMS = {
    "shield": 0.30,
    "buckler": 0.20,
}


def _emit_block(target):
    """Queue a 'BLOCKED!' visual event for the target."""
    _pending_combat_visuals.append({
        "type": "block",
        "target": target,
        "damage": 0,
        "text": "BLOCKED!",
        "x": getattr(target, 'x', 0),
        "y": getattr(target, 'y', 0),
    })


def _find_equipped_shield(entity):
    """Return the shield item if the entity has one equipped or in inventory.

    Checks equipped_armor first (shields are armor-type items), then
    inventory for any shield-type item.
    """
    # Check equipped armor slot
    armor = getattr(entity, 'equipped_armor', None)
    if armor and _is_shield(armor):
        return armor

    # Check inventory for shields (player or NPC)
    inventory = getattr(entity, 'inventory', None) or getattr(entity, 'npc_inventory', [])
    for item in inventory:
        if _is_shield(item):
            return item

    return None


def _is_shield(item) -> bool:
    """Check if an item is a shield based on its name."""
    if item is None:
        return False
    name = getattr(item, 'name', '').lower()
    return any(s in name for s in SHIELD_ITEMS)


def _get_block_chance(entity, shield) -> float:
    """Calculate block chance: base 30% + DEX modifier scaling.

    DEX modifier adds/subtracts 3% per point, capped at 15-50%.
    """
    shield_name = getattr(shield, 'name', '').lower()
    base = 0.30
    for key, chance in SHIELD_ITEMS.items():
        if key in shield_name:
            base = chance
            break

    # Scale with DEX modifier
    dex = 10
    ability_scores = getattr(entity, 'ability_scores', {})
    dex = ability_scores.get("dexterity", 10)
    from game.data.dnd import ability_modifier
    dex_mod = ability_modifier(dex)

    block_chance = base + dex_mod * 0.03
    return max(0.15, min(0.50, block_chance))


def try_shield_block(target) -> bool:
    """Attempt to block an incoming attack with a shield.

    Returns True if the attack is blocked (0 damage).
    Decreases shield durability by 1 per block.
    Shield breaks at 0 durability.
    """
    shield = _find_equipped_shield(target)
    if shield is None:
        return False

    # Check durability — broken shields can't block
    durability = getattr(shield, 'durability', None)
    if durability is not None and durability <= 0:
        return False

    block_chance = _get_block_chance(target, shield)

    if random.random() < block_chance:
        # Successful block — reduce durability
        if hasattr(shield, 'durability') and shield.durability is not None:
            shield.durability -= 1
            if shield.durability <= 0:
                # Shield breaks
                shield.durability = 0
                _emit_shield_break(target, shield)
                _remove_shield(target, shield)

        _emit_block(target)
        return True

    return False


def _emit_shield_break(target, shield):
    """Queue a shield-break visual event."""
    _pending_combat_visuals.append({
        "type": "shield_break",
        "target": target,
        "text": f"{getattr(shield, 'name', 'Shield')} shattered!",
        "x": getattr(target, 'x', 0),
        "y": getattr(target, 'y', 0),
    })


def _remove_shield(target, shield):
    """Remove a broken shield from the entity's equipment/inventory."""
    if getattr(target, 'equipped_armor', None) is shield:
        target.equipped_armor = None

    inventory = getattr(target, 'inventory', None) or getattr(target, 'npc_inventory', [])
    if shield in inventory:
        inventory.remove(shield)


# ---------------------------------------------------------------------------
# Surrender Mechanic
# ---------------------------------------------------------------------------

# Entities that have surrendered — tracked by id
_surrendered_entities: Dict[int, bool] = {}


def check_surrender(entity, attacker=None) -> bool:
    """Check if an entity surrenders due to low HP.

    Called each combat tick. Returns True if the entity surrenders this tick.
    - Triggers below 20% HP
    - 40% chance per tick for hostile NPCs
    - Surrendered entities stop attacking, kneel
    - Creatures never surrender (only NPCs/humanoid enemies)
    """
    eid = id(entity)

    # Already surrendered
    if eid in _surrendered_entities:
        return True

    # Only NPCs/humanoids surrender (not creatures/animals)
    if not hasattr(entity, 'char_class'):
        return False

    if not getattr(entity, 'alive', True):
        return False

    hp_pct = entity.hp / max(1, getattr(entity, 'max_hp', 1))
    if hp_pct >= 0.20:
        return False

    # 40% chance to surrender each tick
    if random.random() < 0.40:
        _apply_surrender(entity)
        return True

    return False


def _apply_surrender(entity):
    """Mark an entity as surrendered — stop fighting, kneel."""
    eid = id(entity)
    _surrendered_entities[eid] = True

    # Stop combat behavior
    entity.combat_target = None
    entity.current_action = "surrendered"
    entity.state = "surrendered"

    # Set pose to kneeling if supported
    if hasattr(entity, 'pose'):
        entity.pose = "kneeling"

    # Add memory
    if hasattr(entity, 'add_memory'):
        entity.add_memory("combat", "I surrendered in battle!", 5)

    # Emit visual
    _pending_combat_visuals.append({
        "type": "surrender",
        "target": entity,
        "text": f"{getattr(entity, 'name', 'Enemy')} surrenders!",
        "x": getattr(entity, 'x', 0),
        "y": getattr(entity, 'y', 0),
    })


def is_surrendered(entity) -> bool:
    """Check if an entity has surrendered."""
    return id(entity) in _surrendered_entities


def spare_entity(entity, player) -> str:
    """Player spares a surrendered entity — reputation boost, possible reward.

    Returns a message describing what happened.
    """
    eid = id(entity)
    if eid not in _surrendered_entities:
        return "They haven't surrendered."

    # Reputation boost
    if hasattr(entity, 'player_relationship'):
        entity.player_relationship = min(100, entity.player_relationship + 30)

    # Become neutral
    entity.state = "idle"
    entity.current_action = ""

    if hasattr(entity, 'add_memory'):
        entity.add_memory("combat", "The player spared my life!", 5)

    # Possible reward: gold or information
    reward_msg = ""
    gold_reward = random.randint(5, 25)
    if hasattr(entity, 'npc_gold') and entity.npc_gold >= gold_reward:
        entity.npc_gold -= gold_reward
        player.gold += gold_reward
        reward_msg = f" They offer {gold_reward} gold in gratitude."
    else:
        info_options = [
            "There's a hidden cache of supplies to the north.",
            "Beware the cave to the east — it's full of undead.",
            "The merchant guild has a bounty on bandits in this area.",
            "I know a shortcut through the mountains.",
            "The local lord is planning an expedition soon.",
        ]
        reward_msg = f' They share: "{random.choice(info_options)}"'

    # Clean up surrender state
    _surrendered_entities.pop(eid, None)

    # Player reputation with nearby NPCs
    if hasattr(player, 'faction_system'):
        kingdom = getattr(player, 'current_kingdom', '')
        if kingdom:
            player.faction_system.modify_reputation(kingdom, 5)

    return f"You spare {entity.name}.{reward_msg}"


def finish_entity(entity, player) -> str:
    """Player finishes off a surrendered entity — loot drops.

    Returns a message describing what happened.
    """
    eid = id(entity)
    if eid not in _surrendered_entities:
        return "They haven't surrendered."

    # Kill them
    entity.alive = False
    entity.hp = 0
    if hasattr(entity, '_death_cause'):
        entity._death_cause = "executed"

    # XP reward
    xp = getattr(entity, 'level', 1) * 15
    player.gain_xp(xp)
    player.kills += 1

    # Loot gold
    gold = getattr(entity, 'npc_gold', 0)
    if gold > 0:
        player.gold += gold
        entity.npc_gold = 0

    # Reputation penalty with nearby NPCs
    if hasattr(entity, 'player_relationship'):
        entity.player_relationship = -100

    if hasattr(player, 'faction_system'):
        kingdom = getattr(player, 'current_kingdom', '')
        if kingdom:
            player.faction_system.modify_reputation(kingdom, -10)

    # Clean up surrender state
    _surrendered_entities.pop(eid, None)

    loot_msg = f" +{xp} XP"
    if gold > 0:
        loot_msg += f", +{gold}g"

    return f"You finish off {entity.name}.{loot_msg}"


def clear_surrender_tracking():
    """Clear surrender tracking (call on world reset/new game)."""
    _surrendered_entities.clear()
    clear_dodge_cooldowns()
