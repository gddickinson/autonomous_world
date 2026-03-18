"""Unified Allegiance System — single source of truth for who's on whose side.

Replaces scattered faction/party/group/army checks with one system that
answers: "Are these two entities allies, enemies, or neutral?"

Allegiance hierarchy (highest priority first):
1. Same party (player party, NPC adventuring party)
2. Same military unit (army, troop, formed unit)
3. Same monster group (orc warband, goblin tribe)
4. Same settlement/kingdom
5. Same creature kind (wolves don't attack wolves)
6. Tamed/owned creatures follow their owner's allegiance

Used by:
- combat.py: Don't attack allies, focus-fire enemies
- simulation.py: Threat response respects allegiance
- living.py: Pack hunting respects allegiance
- colosseum.py: Team assignments map to allegiance
"""

from typing import Optional, Tuple
from enum import IntEnum


class Relation(IntEnum):
    """Relationship between two entities."""
    ALLIED = 2       # same team, will defend each other
    FRIENDLY = 1     # won't attack, may help
    NEUTRAL = 0      # default — ignore unless provoked
    UNFRIENDLY = -1  # suspicious, may attack if provoked
    HOSTILE = -2     # will attack on sight


def get_allegiance_id(entity) -> str:
    """Get the primary allegiance identifier for any entity.

    Returns the most specific group this entity belongs to.
    Priority: party > military_unit > monster_group > faction/settlement > kind
    """
    # Player party
    pid = getattr(entity, 'party_id', None)
    if pid:
        return f"party:{pid}"

    # Military unit
    mil = getattr(entity, '_military_unit', None)
    if mil:
        return f"unit:{mil.name}"

    # Monster group (creatures in organized societies)
    mg = getattr(entity, '_monster_group_id', None)
    if mg:
        return f"mgroup:{mg}"

    # Faction/kingdom (NPCs)
    faction = getattr(entity, 'faction', '')
    if faction:
        return f"faction:{faction}"

    # Home settlement (NPCs without explicit faction)
    home = getattr(entity, 'home_settlement', '')
    if home:
        return f"settlement:{home}"

    # Creature kind (wolves are allied with wolves)
    kind = getattr(entity, 'kind', '')
    if kind:
        return f"kind:{kind}"

    # Player
    if hasattr(entity, 'char_class') and not hasattr(entity, 'npc_attack_damage'):
        return "party:player"

    return "none"


def get_relation(entity_a, entity_b) -> Relation:
    """Determine the relationship between two entities.

    Returns: Relation enum (ALLIED, FRIENDLY, NEUTRAL, UNFRIENDLY, HOSTILE)
    """
    if entity_a is entity_b:
        return Relation.ALLIED

    a_id = get_allegiance_id(entity_a)
    b_id = get_allegiance_id(entity_b)

    # Same allegiance = allied
    if a_id == b_id and a_id != "none":
        return Relation.ALLIED

    # --- PARTY CHECKS ---
    a_party = getattr(entity_a, 'party_id', None)
    b_party = getattr(entity_b, 'party_id', None)
    if a_party and a_party == b_party:
        return Relation.ALLIED

    # Player party members are allied with the player
    if a_party == "player_party" or b_party == "player_party":
        # Check if the other is the player
        a_is_player = hasattr(entity_a, 'hotbar')  # Player has hotbar
        b_is_player = hasattr(entity_b, 'hotbar')
        if (a_party == "player_party" and b_is_player) or \
           (b_party == "player_party" and a_is_player):
            return Relation.ALLIED

    # --- TAMED/OWNED CREATURES ---
    a_owner = getattr(entity_a, 'owner_name', '')
    b_owner = getattr(entity_b, 'owner_name', '')
    if a_owner and a_owner == getattr(entity_b, 'name', ''):
        return Relation.ALLIED
    if b_owner and b_owner == getattr(entity_a, 'name', ''):
        return Relation.ALLIED
    if a_owner and b_owner and a_owner == b_owner:
        return Relation.ALLIED

    # --- MILITARY UNIT ---
    a_mil = getattr(entity_a, '_military_unit', None)
    b_mil = getattr(entity_b, '_military_unit', None)
    if a_mil and b_mil:
        if a_mil is b_mil:
            return Relation.ALLIED
        # Different units but same troop team?
        a_team = getattr(a_mil, '_troop_team', -1)
        b_team = getattr(b_mil, '_troop_team', -1)
        if a_team >= 0 and a_team == b_team:
            return Relation.ALLIED

    # --- FACTION/KINGDOM ---
    a_faction = getattr(entity_a, 'faction', '')
    b_faction = getattr(entity_b, 'faction', '')
    if a_faction and b_faction:
        if a_faction == b_faction:
            return Relation.ALLIED
        # Hostile factions (bandits, outlaws, pirates vs everyone else)
        hostile_factions = {"Outlaws", "Bandits", "Pirates", "Raiders"}
        a_hostile = a_faction in hostile_factions
        b_hostile = b_faction in hostile_factions
        if a_hostile != b_hostile:  # one is hostile, other isn't
            return Relation.HOSTILE
        # Different kingdoms — neutral by default
        return Relation.NEUTRAL

    # --- SETTLEMENT ---
    a_home = getattr(entity_a, 'home_settlement', '')
    b_home = getattr(entity_b, 'home_settlement', '')
    if a_home and b_home and a_home == b_home:
        return Relation.FRIENDLY  # same village = friendly

    # --- CREATURE KIND ---
    a_kind = getattr(entity_a, 'kind', '')
    b_kind = getattr(entity_b, 'kind', '')
    if a_kind and b_kind:
        if a_kind == b_kind:
            return Relation.ALLIED  # same species
        # Check monster group governance
        from game.systems.monster_society import CREATURE_GOVERNANCE_MAP
        a_gov = CREATURE_GOVERNANCE_MAP.get(a_kind.lower(), '')
        b_gov = CREATURE_GOVERNANCE_MAP.get(b_kind.lower(), '')
        if a_gov and a_gov == b_gov:
            return Relation.FRIENDLY  # same governance (orcs+bugbears)

    # --- NPC vs CREATURE default ---
    a_is_npc = hasattr(entity_a, 'char_class') and hasattr(entity_a, 'npc_attack_damage')
    b_is_npc = hasattr(entity_b, 'char_class') and hasattr(entity_b, 'npc_attack_damage')
    a_is_creature = hasattr(entity_a, 'kind') and not a_is_npc
    b_is_creature = hasattr(entity_b, 'kind') and not b_is_npc

    if a_is_npc and b_is_creature:
        if getattr(entity_b, 'passive', False):
            return Relation.NEUTRAL
        if a_home:
            return Relation.HOSTILE
    if b_is_npc and a_is_creature:
        if getattr(entity_a, 'passive', False):
            return Relation.NEUTRAL
        if b_home:
            return Relation.HOSTILE

    # --- PREDATOR vs PREY ---
    if a_is_creature and b_is_creature:
        a_passive = getattr(entity_a, 'passive', False)
        b_passive = getattr(entity_b, 'passive', False)
        # Predator hunts prey
        if not a_passive and b_passive:
            return Relation.HOSTILE
        if not b_passive and a_passive:
            return Relation.HOSTILE

    # --- HOSTILE FACTIONS (bandits, outlaws vs everyone else) ---
    if a_is_npc and b_is_npc:
        hostile_factions = {"Outlaws", "Bandits", "Pirates", "Raiders"}
        a_hostile = a_faction in hostile_factions
        b_hostile = b_faction in hostile_factions
        if a_hostile and not b_hostile:
            return Relation.HOSTILE
        if b_hostile and not a_hostile:
            return Relation.HOSTILE

    # --- PERSONAL RELATIONSHIP (NPC to NPC) ---
    if a_is_npc and b_is_npc:
        a_name = getattr(entity_a, 'name', '')
        b_name = getattr(entity_b, 'name', '')

        # Check if they're friends or enemies
        a_friends = getattr(entity_a, 'friends', [])
        a_enemies = getattr(entity_a, 'enemies', [])
        if b_name in a_friends:
            return Relation.FRIENDLY
        if b_name in a_enemies:
            return Relation.UNFRIENDLY

        # Same settlement = friendly
        if a_home and a_home == b_home:
            return Relation.FRIENDLY

    return Relation.NEUTRAL


def are_allies(entity_a, entity_b) -> bool:
    """Quick check: are these two entities on the same side?"""
    return get_relation(entity_a, entity_b) >= Relation.FRIENDLY


def are_enemies(entity_a, entity_b) -> bool:
    """Quick check: are these two entities hostile to each other?"""
    return get_relation(entity_a, entity_b) <= Relation.UNFRIENDLY


def should_attack(attacker, target) -> bool:
    """Should the attacker target this entity?

    Returns True if the target is a valid enemy.
    Considers allegiance, passive status, and alive status.
    """
    if not getattr(target, 'alive', True):
        return False
    if attacker is target:
        return False
    rel = get_relation(attacker, target)
    return rel <= Relation.UNFRIENDLY


def find_allies_nearby(entity, candidates: list, radius: float = 10.0) -> list:
    """Find allied entities within radius."""
    allies = []
    r_sq = radius * radius
    for c in candidates:
        if c is entity or not getattr(c, 'alive', True):
            continue
        dx = entity.x - c.x
        dy = entity.y - c.y
        if dx * dx + dy * dy <= r_sq and are_allies(entity, c):
            allies.append(c)
    return allies


def find_enemies_nearby(entity, candidates: list, radius: float = 10.0) -> list:
    """Find hostile entities within radius."""
    enemies = []
    r_sq = radius * radius
    for c in candidates:
        if c is entity or not getattr(c, 'alive', True):
            continue
        dx = entity.x - c.x
        dy = entity.y - c.y
        if dx * dx + dy * dy <= r_sq and are_enemies(entity, c):
            enemies.append(c)
    return enemies
