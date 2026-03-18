"""Conversation engagement rules — shared by player-NPC and NPC-NPC interactions.

Determines whether an entity will stop and talk, based on:
- Relationship/trust between the two entities
- Current activity (busy NPCs may refuse)
- Emotional state (scared entities flee, angry ones may fight)
- Needs (lonely NPCs are eager, busy ones brush you off)
- Bravery (cowards avoid hostile entities)

Used by:
- actions.py: _start_dialog (player initiates with NPC)
- social.py: _do_social_interaction (NPC-NPC)
- sim_conversations.py: _start_talk (NPC-NPC via LLM decision)
"""

import random


# Actions that completely block conversation
BUSY_ACTIONS = frozenset({"fighting", "fleeing", "sleeping", "dead"})

# Actions that can be interrupted if relationship is good enough
INTERRUPTIBLE_ACTIONS = frozenset({
    "working", "chopping", "mining", "farming", "fishing",
    "smithing", "hunting", "guarding", "building", "crafting",
    "foraging", "carrying", "commuting",
})


def check_conversation_willingness(initiator, target, nearby_allies=None) -> str:
    """Check if target is willing to converse with initiator.

    Returns:
        "ok" — willing to talk
        "busy" — too busy right now
        "refuse" — doesn't want to talk to this entity
        "flee" — scared, runs away
        "attack" — angry, attacks
        "ignore" — pretends not to hear
        "delegate_attack" — orders allies to attack instead
        "delegate_arrest" — orders guards to arrest
    """
    # Get relationship between the two
    rel = _get_relationship(initiator, target)
    bravery = getattr(target, 'bravery', 0.5)
    action = getattr(target, 'current_action', '')

    # --- Completely busy: can't talk ---
    if action in BUSY_ACTIONS:
        return "busy"
    if not getattr(target, 'alive', True):
        return "busy"

    # --- Hostile: important NPCs delegate to guards/allies ---
    if rel < -50:
        title = getattr(target, 'title', 'commoner')
        is_ruler = getattr(target, 'is_ruler', False)
        is_important = is_ruler or title in ('ruler', 'king', 'queen', 'lord',
                                              'duke', 'captain', 'knight')
        has_command = getattr(target, '_is_commander', False)

        if is_important or has_command:
            # Important NPCs order others to deal with threats
            guards = _find_nearby_muscle(target, nearby_allies)
            if guards:
                return "delegate_attack"

        # Regular hostile response
        if bravery > 0.6:
            return "attack"
        else:
            return "flee"

    # --- Unfriendly but not hostile: important NPCs may have guards warn ---
    if rel < -20:
        title = getattr(target, 'title', 'commoner')
        is_ruler = getattr(target, 'is_ruler', False)
        if is_ruler or title in ('ruler', 'king', 'queen', 'lord', 'duke'):
            guards = _find_nearby_muscle(target, nearby_allies)
            if guards and random.random() < 0.5:
                return "delegate_arrest"

    # --- Very unfriendly: may ignore ---
    if rel < -20:
        if random.random() < 0.4:
            return "ignore"

    # --- Busy with interruptible work ---
    if action in INTERRUPTIBLE_ACTIONS and rel < 20:
        social_need = 50
        if hasattr(target, 'needs'):
            social_need = target.needs.get("social", 50)
        # Lonely NPCs will stop work to talk
        if social_need > 40 and random.random() < 0.3:
            return "busy"

    # --- Emotional checks ---
    es = getattr(target, 'emotion_state', None)
    if es and hasattr(es, 'primary'):
        fear = es.primary.get("fear", 0)
        anger = es.primary.get("anger", 0)

        # Very scared of this specific entity
        if fear > 0.6 and rel < 0:
            if bravery < 0.4:
                return "flee"

        # Very angry at this specific entity
        if anger > 0.7 and rel < -10:
            if bravery > 0.5:
                return "attack"

    return "ok"


def engage_conversation(initiator, target):
    """Make target stop and engage in conversation.

    Saves previous state and sets to socializing/talking.
    Call disengage_conversation() when done.
    """
    # Save state
    target._pre_conv_state = getattr(target, 'state', 'idle')
    target._pre_conv_action = getattr(target, 'current_action', '')
    target._pre_conv_target_x = getattr(target, 'target_x', None)
    target._pre_conv_target_y = getattr(target, 'target_y', None)

    # Stop and face initiator
    target.state = "socializing"
    target.current_action = "talking"
    target.target_x = None
    target.target_y = None
    if hasattr(target, 'state_timer'):
        target.state_timer = 30.0

    # Face the initiator
    if hasattr(target, 'x') and hasattr(initiator, 'x'):
        dx = initiator.x - target.x
        dy = initiator.y - target.y
        target.facing = (1 if dx > 0 else -1, 1 if dy > 0 else -1)

    # Social need boost
    if hasattr(target, 'needs'):
        target.needs["social"] = min(100, target.needs.get("social", 50) + 5)


def disengage_conversation(target):
    """Restore target's state after conversation ends."""
    if target is None:
        return
    prev_state = getattr(target, '_pre_conv_state', 'idle')
    prev_action = getattr(target, '_pre_conv_action', '')
    target.state = prev_state if prev_state != "socializing" else "idle"
    target.current_action = prev_action if prev_action != "talking" else ""
    target.target_x = getattr(target, '_pre_conv_target_x', None)
    target.target_y = getattr(target, '_pre_conv_target_y', None)


def _get_relationship(a, b) -> int:
    """Get relationship score between two entities."""
    # Player to NPC
    if hasattr(b, 'player_relationship') and not hasattr(a, 'npc_attack_damage'):
        return b.player_relationship

    # NPC to NPC
    a_name = getattr(a, 'name', '')
    b_rels = getattr(b, 'npc_relationships', {})
    if a_name in b_rels:
        return b_rels[a_name]

    # Check friends/enemies lists
    if a_name in getattr(b, 'friends', []):
        return 30
    if a_name in getattr(b, 'enemies', []):
        return -30

    # Default: neutral
    return 0


def _find_nearby_muscle(entity, nearby_allies=None) -> list:
    """Find guards, soldiers, or allies nearby who can fight on entity's behalf.

    Checks for: guards, knights, fighters, companions, friends with combat ability.
    Returns list of entities that could be ordered to act.
    """
    candidates = []

    # If we have a pre-provided nearby list, use it
    if nearby_allies:
        for ally in nearby_allies:
            if ally is entity or not getattr(ally, 'alive', True):
                continue
            if _is_muscle(ally, entity):
                candidates.append(ally)
        return candidates

    # Otherwise check friends list (we can't do spatial without a grid)
    friends = getattr(entity, 'friends', [])
    if friends:
        # We can't resolve names to entities without world context,
        # but we can indicate that friends exist
        return ["friend_placeholder"]

    return candidates


def _is_muscle(ally, boss) -> bool:
    """Check if an ally could serve as muscle for the boss."""
    title = getattr(ally, 'title', 'commoner')
    cc = getattr(ally, 'char_class', '')
    action = getattr(ally, 'current_action', '')

    # Already busy fighting/fleeing
    if action in BUSY_ACTIONS:
        return False

    # Guards, knights, and soldiers are always available muscle
    if title in ('guard', 'knight', 'captain', 'soldier'):
        return True

    # Combat classes with positive relationship to boss
    if cc in ('Fighter', 'Paladin', 'Barbarian', 'Ranger'):
        boss_name = getattr(boss, 'name', '')
        ally_rels = getattr(ally, 'npc_relationships', {})
        if ally_rels.get(boss_name, 0) > 10:
            return True

    # Same faction/settlement
    a_faction = getattr(ally, 'faction', '')
    b_faction = getattr(boss, 'faction', '')
    if a_faction and a_faction == b_faction and title != 'commoner':
        return True

    return False


def delegate_response(boss, target, nearby_allies, action_type="attack"):
    """Boss orders nearby allies to deal with a target.

    action_type: "attack" — guards attack the target
                 "arrest" — guards confront and warn the target
                 "escort_out" — guards escort target away

    Returns list of allies that responded.
    """
    responded = []

    for ally in nearby_allies:
        if ally is boss or not getattr(ally, 'alive', True):
            continue
        if not _is_muscle(ally, boss):
            continue

        if action_type == "attack":
            ally.combat_target = target
            ally.current_action = "fighting"
            ally.state = "fighting"
            ally.add_memory("duty",
                f"{boss.name} ordered me to attack {getattr(target, 'name', 'intruder')}!", 4)
        elif action_type == "arrest":
            # Guards move to intercept and warn
            ally.target_x = target.x
            ally.target_y = target.y
            ally.current_action = "moving"
            ally.state = "walking"
            ally.state_timer = 10.0
            ally.add_memory("duty",
                f"{boss.name} ordered me to deal with {getattr(target, 'name', 'troublemaker')}", 3)
            # Drop relationship with target
            target_name = getattr(target, 'name', '')
            if target_name and hasattr(ally, 'npc_relationships'):
                ally.npc_relationships[target_name] = min(
                    ally.npc_relationships.get(target_name, 0), -10)
        elif action_type == "escort_out":
            ally.target_x = target.x
            ally.target_y = target.y
            ally.current_action = "moving"
            ally.state = "walking"
            ally.state_timer = 15.0

        responded.append(ally)

        # Max 3 responders
        if len(responded) >= 3:
            break

    # Boss remembers giving the order
    if responded:
        r_names = ', '.join(getattr(r, 'name', '?') for r in responded[:2])
        boss.add_memory("command",
            f"Ordered {r_names} to {action_type} {getattr(target, 'name', 'someone')}", 3)

    return responded
