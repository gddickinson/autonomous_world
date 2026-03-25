"""Combat action handlers — player attack, item use."""

import random
import math
from game.settings import *

def attack(game):
    """Player attack - target nearest enemy or cycle targets. Real-time, no freeze."""
    # Ghost mode: can't attack
    if getattr(game.player, 'ghost', False):
        game.notifications.add("Ghosts cannot attack.", 1.5, (150, 150, 220))
        return

    fx, fy = game.player.facing

    # Find all nearby hostiles sorted by distance
    targets = []
    for c in game.world_mgr.creatures:
        if c.alive and game.player.dist_to(c) < CREATURE_CHASE_RANGE:
            targets.append(c)
    for npc in game.world_mgr.npcs:
        if npc.alive and game.player.dist_to(npc) < PLAYER_ATTACK_RANGE * 3:
            if hasattr(game, 'party') and npc in game.party.companions:
                continue
            # Prefer enemies in facing direction
            dx = npc.x - game.player.x
            dy = npc.y - game.player.y
            d = math.sqrt(dx*dx + dy*dy) or 1
            dot = fx * (dx/d) + fy * (dy/d)
            if dot > 0.0:
                targets.append(npc)

    if not targets:
        game.notifications.add("No enemies nearby.", 1.5, GRAY)
        if game.combat.active:
            game.combat.end_combat()
        return

    targets.sort(key=lambda e: game.player.dist_to(e))

    # If already fighting, cycle to next target on repeated Space presses
    current_target = game.combat.player_state.target
    if current_target and getattr(current_target, 'alive', False):
        try:
            idx = targets.index(current_target)
            next_target = targets[(idx + 1) % len(targets)]
        except ValueError:
            next_target = targets[0]
    else:
        next_target = targets[0]

    msg = game.combat.set_player_target(next_target)
    game.notifications.add(msg, 2.0, RED)
    game.attack_flash_timer = 0.1
    # Audio: sword hit on engaging combat
    if hasattr(game, 'sound'):
        game.sound.play("sword_hit")

    # God mode: instant kill
    _cfx = getattr(game.active_renderer, 'combat_fx', None)
    if getattr(game.player, 'god', False) and next_target.alive:
        name = getattr(next_target, 'name', getattr(next_target, 'kind', '?'))
        next_target.take_damage(99999)
        game.notifications.add(f"Divine wrath! {name} obliterated!", 2.0, (255, 220, 100))
        game.renderer.spawn_hit_particles(next_target.x, next_target.y, (255, 220, 100))
        if hasattr(game.renderer, 'spawn_damage_popup'):
            game.renderer.spawn_damage_popup(next_target.x, next_target.y, 99999,
                                              (255, 220, 100))
        if hasattr(game.renderer, 'spawn_death_effect'):
            game.renderer.spawn_death_effect(next_target.x, next_target.y)
        if _cfx:
            _cfx.on_damage_dealt(next_target, 99999, is_kill=True)
        game.player.gain_skill_xp("swordsmanship", 0.2)
        return

    # Power strike bonus
    if game.power_strike_active:
        game.power_strike_active = False
        if next_target.alive:
            bonus_dmg = game.player.get_attack_damage() * 2
            next_target.take_damage(bonus_dmg)
            game.notifications.add(f"Power Strike! {bonus_dmg} bonus damage!", 2.0, YELLOW)
            game.renderer.spawn_hit_particles(next_target.x, next_target.y)
            if hasattr(game.renderer, 'spawn_damage_popup'):
                game.renderer.spawn_damage_popup(next_target.x, next_target.y,
                                                  int(bonus_dmg), (255, 220, 60))
            if _cfx:
                _cfx.on_damage_dealt(next_target, int(bonus_dmg),
                                     is_kill=not next_target.alive)

    game.player.gain_skill_xp("swordsmanship", 0.2)

    # Handle creature/NPC deaths and drops (check each frame via combat update)
    result = None
    if result:
        game.notifications.add(result, 2.0, RED)
        game.attack_flash_timer = 0.15
        game.player.gain_skill_xp("swordsmanship", 0.4)

        # Handle creature kills
        for creature in game.world_mgr.creatures:
            if not creature.alive and game.player.dist_to(creature) < PLAYER_ATTACK_RANGE * 1.5:
                game.renderer.spawn_hit_particles(creature.x, creature.y)
                game.renderer.spawn_xp_particles(creature.x, creature.y)
                game.quest_sys.on_kill(creature.kind)
                # Multiplayer: broadcast quest kill progress
                if hasattr(game, '_mp_broadcast_quest_kill'):
                    for q in game.quest_sys.active_quests:
                        if q.target == creature.kind and not q.completed:
                            game._mp_broadcast_quest_kill(q, game.player.name)
                            break
                drops = creature.get_drops()
                if drops:
                    game.world_mgr.drop_items(creature.x, creature.y, drops)
                    for item in drops:
                        game.notifications.add(f"{creature.kind} dropped {item.name}", 2.5, ORANGE)
            elif creature.alive and game.player.dist_to(creature) < PLAYER_ATTACK_RANGE * 1.5:
                game.renderer.spawn_hit_particles(creature.x, creature.y, (255, 100, 50))
                if damage_mult > 1:
                    creature.take_damage(game.player.get_attack_damage() * (damage_mult - 1))

        # Handle NPC kills
        for npc in game.world_mgr.npcs:
            if not npc.alive and game.player.dist_to(npc) < PLAYER_ATTACK_RANGE * 1.5:
                game.renderer.spawn_hit_particles(npc.x, npc.y, (200, 50, 50))
                # Drop NPC inventory
                for item in npc.npc_inventory:
                    game.world_mgr.ground_items.append((
                        npc.x + random.uniform(-0.5, 0.5),
                        npc.y + random.uniform(-0.5, 0.5), item))
                if npc.npc_gold > 0:
                    from game.core.items import make_item
                    gold = make_item("Gold Nugget")
                    game.world_mgr.ground_items.append((npc.x, npc.y, gold))
                npc.npc_inventory.clear()
                game.notifications.add(f"{npc.name} has been slain!", 3.0, RED)
            elif npc.alive and game.player.dist_to(npc) < PLAYER_ATTACK_RANGE * 1.5:
                if npc.hp < npc.max_hp:
                    game.renderer.spawn_hit_particles(npc.x, npc.y, (255, 100, 50))
                    if damage_mult > 1:
                        npc.take_damage(game.player.get_attack_damage() * (damage_mult - 1))



