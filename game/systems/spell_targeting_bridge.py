"""Bridge between targeting UI and spell/combat systems.

Wires together: TargetingSystem results -> TacticalCombat spell casting
-> ElementalEffects terrain changes -> visual effects spawning.
"""

from game.systems.combat import CombatSystem


# Spell name -> elemental effect type mapping
_FIRE_SPELLS = frozenset({
    "fireball", "burning_hands", "scorching_ray", "flame_shield",
    "fire_bolt", "magma_burst", "meteor_swarm", "divine_wrath",
})

_ICE_SPELLS = frozenset({
    "ice_shard", "ice_wall", "frost_nova", "ice_storm", "ray_of_frost",
    "cone_of_cold",
})

_LIGHTNING_SPELLS = frozenset({
    "lightning_bolt", "chain_lightning", "thunderwave",
})

_ACID_SPELLS = frozenset({
    "acid_splash", "acid_arrow", "poison_spray", "cloudkill",
})


def execute_targeted_spell(game, spell_name, target_result):
    """Cast a targeted spell using the targeting result.

    Args:
        game: Game instance.
        spell_name: Name of the spell to cast.
        target_result: Dict from TargetingSystem.handle_click with
                       keys world_x, world_y, entity, valid.
    """
    if not target_result or not target_result.get("valid"):
        game.notifications.add("Invalid target!", 1.5, (200, 80, 80))
        return

    wx = target_result["world_x"]
    wy = target_result["world_y"]

    # Cast via TacticalCombat (handles damage, mana cost, cooldowns)
    result = CombatSystem.player_cast_spell(
        game.player,
        spell_name,
        game.world_mgr.creatures,
        game.world_mgr.npcs,
        target_pos=(wx, wy),
    )

    if result:
        # Color-code notification
        if "Cannot" in result or "Unknown" in result:
            color = (200, 80, 80)
        elif "slain" in result.lower() or "damage" in result.lower():
            color = (220, 180, 60)
        elif "heal" in result.lower() or "cure" in result.lower():
            color = (80, 200, 80)
        else:
            color = (140, 180, 220)
        game.notifications.add(result, 3.0, color)

    # Apply terrain effects if elemental system is available
    elemental = getattr(game, 'elemental', None)
    if elemental:
        apply_spell_terrain_effects(spell_name, wx, wy, elemental, game.world)

    # Trigger visual effects on the renderer
    renderer = getattr(game, 'active_renderer', None)
    if renderer and hasattr(renderer, 'spawn_spell_effect'):
        renderer.spawn_spell_effect(
            spell_name, game.player.x, game.player.y, wx, wy)


def apply_spell_terrain_effects(spell_name, wx, wy, elemental_effects, world):
    """Map a spell to elemental terrain effects and apply them.

    Args:
        spell_name: Spell name string.
        wx, wy: World coordinates of the impact point.
        elemental_effects: ElementalEffects instance.
        world: World object for terrain manipulation.
    """
    ix, iy = int(wx), int(wy)

    if spell_name in _FIRE_SPELLS:
        # Fire: center + small area
        elemental_effects.apply_fire(ix, iy, 0.8, 10.0, world)
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if dx == 0 and dy == 0:
                    continue
                if abs(dx) + abs(dy) <= 1:  # 4-neighbors only
                    elemental_effects.apply_fire(
                        ix + dx, iy + dy, 0.5, 6.0, world)

    elif spell_name in _ICE_SPELLS:
        # Ice: freeze center + small area
        elemental_effects.apply_ice(ix, iy, 15.0, world)
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if abs(dx) + abs(dy) <= 1:
                    elemental_effects.apply_ice(
                        ix + dx, iy + dy, 12.0, world)

    elif spell_name in _LIGHTNING_SPELLS:
        # Lightning: scorch center
        elemental_effects.apply_lightning_scorch(ix, iy, world)

    elif spell_name in _ACID_SPELLS:
        # Acid: center + small puddle
        elemental_effects.apply_acid(ix, iy, 20.0, world)
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                if abs(dx) + abs(dy) <= 1:
                    elemental_effects.apply_acid(
                        ix + dx, iy + dy, 15.0, world)


def execute_targeted_throw(game, item, target_result):
    """Handle a thrown item using the targeting result.

    Args:
        game: Game instance.
        item: Item object to throw.
        target_result: Dict from TargetingSystem.handle_click.
    """
    if not target_result or not target_result.get("valid"):
        game.notifications.add("Invalid throw target!", 1.5, (200, 80, 80))
        return

    wx = target_result["world_x"]
    wy = target_result["world_y"]
    entity = target_result.get("entity")

    # Remove item from inventory
    inv = getattr(game.player, 'inventory', [])
    if item in inv:
        inv.remove(item)

    # If hit entity, deal damage
    if entity and getattr(entity, 'alive', True):
        damage = getattr(item, 'damage', 5)
        entity.take_damage(damage)
        name = getattr(entity, 'name', getattr(entity, 'kind', 'target'))
        game.notifications.add(
            f"Threw {item.name} at {name} for {damage} damage!",
            2.0, (220, 180, 60))
    else:
        # Drop item on ground
        ground_items = getattr(game.world_mgr, 'ground_items', [])
        ground_items.append({
            "item": item, "x": wx, "y": wy, "age": 0.0
        })
        game.notifications.add(
            f"Threw {item.name}.", 1.5, (180, 180, 200))
