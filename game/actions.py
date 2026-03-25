"""
Player action handlers extracted from main.py for modularity.
Each function takes a Game instance and operates on its state.
"""

import math
import random
import time

from game.settings import *
from game.ai.prompts import Prompts, build_npc_context


def _get_npcs_inside(game, interior):
    """Get NPCs whose home position is within this building's footprint."""
    npcs = []
    wx, wy = interior.world_x, interior.world_y
    radius = max(interior.width, interior.height) // 2
    for npc in game.world_mgr.npcs:
        if not npc.alive:
            continue
        # Check if NPC's home is near this building
        if abs(npc.home_x - wx) < radius and abs(npc.home_y - wy) < radius:
            # Assign an interior position if not already set
            if not hasattr(npc, '_interior_x') or npc._interior_x < 0:
                # Place NPC in a random floor tile
                import random as _rng
                for _ in range(20):
                    rx = _rng.randint(2, interior.width - 3)
                    ry = _rng.randint(2, interior.height - 3)
                    if interior.is_walkable(rx, ry):
                        npc._interior_x = rx
                        npc._interior_y = ry
                        break
                else:
                    npc._interior_x = interior.entry_x
                    npc._interior_y = interior.entry_y
            npcs.append(npc)
    return npcs


def _start_creature_dialog(game, creature):
    """Start a dialog with an intelligent creature."""
    from game.core.creature_dialogs import build_creature_dialog
    dialog_lines = build_creature_dialog(creature)
    if not dialog_lines:
        game.notifications.add("This creature can't talk.", 1.5, GRAY)
        return

    # Set temporary attributes so the dialog panel can render it
    creature.dialog_lines = dialog_lines
    if not hasattr(creature, 'name') or not creature.name:
        creature.name = creature.kind.replace('_', ' ').title()
    if not hasattr(creature, 'profession'):
        creature.profession = creature.monster_type
    if not hasattr(creature, 'consciousness'):
        creature.consciousness = 0
    if not hasattr(creature, 'shop_items'):
        creature.shop_items = []
    if not hasattr(creature, 'needs'):
        creature.needs = {}
    if not hasattr(creature, 'player_relationship'):
        creature.player_relationship = -20

    game.ui.dialog_active = True
    game.ui.dialog_npc = creature
    game.ui.dialog_key = "greeting"
    game.ui.selected_response = 0


def _open_quest_board(game, board):
    """Open the quest board UI for a tavern.

    Sets game state to show quest board panel. The UI rendering and
    input handling is done in main.py's update loop.
    """
    current_day = int(getattr(game.time_sys, 'day', 0))
    player_level = getattr(game.player, 'level', 1)

    if board.needs_refresh(current_day):
        board.refresh(current_day, player_level)

    game.quest_board_active = True
    game.quest_board_settlement = board.settlement_name
    game.quest_board_listings = board.get_listings()
    game.quest_board_selected = 0

    if not game.quest_board_listings:
        game.notifications.add(
            "The quest board is empty. Check back in a few days.",
            3.0, (200, 200, 150))
        game.quest_board_active = False
    else:
        game.notifications.add(
            f"Quest Board - {board.settlement_name} Tavern",
            2.0, (220, 200, 100))


def _open_message_board(game, board):
    """Open the message board UI for a tavern or town hall."""
    current_day = int(getattr(game.time_sys, 'day', 0))

    if board.needs_refresh(current_day):
        board.refresh(current_day)

    game.msg_board_active = True
    game.msg_board_settlement = board.settlement_name
    game.msg_board_listings = board.get_listings()
    game.msg_board_selected = 0

    if not game.msg_board_listings:
        game.notifications.add(
            "The message board is empty.", 2.0, (200, 200, 150))
        game.msg_board_active = False
    else:
        game.notifications.add(
            f"Message Board - {board.settlement_name}",
            2.0, (160, 170, 220))


def _open_board_menu(game, quest_board, msg_board):
    """Show a selection menu: Quest Board or Message Board."""
    game.board_menu_active = True
    game.board_menu_quest_board = quest_board
    game.board_menu_msg_board = msg_board
    game.board_menu_selected = 0
    game.notifications.add(
        "Press 1 for Quest Board, 2 for Message Board, Esc to close",
        4.0, (220, 200, 100))


def _start_dialog(game, npc):
    """Start a dialog with an NPC — uses shared conversation_rules.

    Uses shared conversation_rules for willingness checks.
    Same rules apply to NPC-NPC conversations in social.py and sim_conversations.py.
    """
    from game.systems.conversation_rules import (
        check_conversation_willingness, engage_conversation, delegate_response)

    # Gather nearby NPCs for delegation checks
    nearby = []
    if hasattr(game, 'world_mgr'):
        for other in game.world_mgr.npcs:
            if other is npc or not other.alive:
                continue
            if (other.x - npc.x) ** 2 + (other.y - npc.y) ** 2 < 225:  # 15 tiles
                nearby.append(other)

    result = check_conversation_willingness(game.player, npc, nearby_allies=nearby)

    if result == "delegate_attack":
        # Important NPC orders guards to attack
        responders = delegate_response(npc, game.player, nearby, "attack")
        if responders:
            names = ', '.join(getattr(r, 'name', '?') for r in responders[:2])
            game.notifications.add(
                f"{npc.name}: \"Guards! Seize them!\" ({names} attack!)", 4.0, (220, 50, 50))
        else:
            # Fallback to personal attack
            npc.combat_target = game.player
            npc.current_action = "fighting"
            npc.state = "fighting"
            game.notifications.add(f"{npc.name} attacks you!", 3.0, (220, 50, 50))
        npc.add_memory("command", "Ordered my guards to deal with the player!", 4)
        return

    if result == "delegate_arrest":
        # Important NPC has guards confront the player
        responders = delegate_response(npc, game.player, nearby, "arrest")
        if responders:
            names = ', '.join(getattr(r, 'name', '?') for r in responders[:2])
            game.notifications.add(
                f"{npc.name}: \"You're not welcome here.\" ({names} move to intercept)", 3.0, (200, 150, 50))
        npc.add_memory("political", "Had my guards warn the player away", 3)
        return

    if result == "attack":
        npc.combat_target = game.player
        npc.current_action = "fighting"
        npc.state = "fighting"
        game.notifications.add(f"{npc.name} attacks you!", 3.0, (220, 50, 50))
        npc.add_memory("conflict", "The player approached me despite my hatred!", 4)
        return
    if result == "flee":
        npc.flee_from(game.player.x, game.player.y)
        game.notifications.add(f"{npc.name} runs away from you!", 2.0, (200, 150, 50))
        npc.add_memory("fear", "The player approached me. I ran.", 3)
        return
    if result == "ignore":
        game.notifications.add(f"{npc.name} ignores you.", 2.0, (150, 150, 150))
        return
    if result == "busy":
        game.notifications.add(f"{npc.name} is too busy to talk right now.", 2.0, (200, 200, 100))
        return

    # --- AGREED TO TALK ---
    engage_conversation(game.player, npc)

    npc.regenerate_dialog()
    game.ui.dialog_active = True
    game.ui.dialog_npc = npc
    game.ui.dialog_key = "greeting"
    game.ui.selected_response = 0
    npc.player_relationship = max(-100, min(100, npc.player_relationship + 1))
    # Audio: NPC greeting sound
    if hasattr(game, 'sound'):
        game.sound.play("npc_greeting")

    if hasattr(game, 'quest_sys'):
        game.quest_sys.on_npc_interaction(npc.name)


def _end_dialog(game, npc):
    """Restore NPC state after conversation ends."""
    from game.systems.conversation_rules import disengage_conversation
    disengage_conversation(npc)


def interact(game):
    """Interact with nearest NPC, pick up items, or interact with doors."""
    # Ghost mode: can only interact at spawn temple to respawn
    if getattr(game.player, 'ghost', False):
        sx, sy = game.world.spawn_point
        if game.player.dist_to_pos(sx, sy) < 3:
            game.player.ghost = False
            game.player.mode = "mortal"
            game.player_mode = "mortal"
            game.player.hp = game.player.max_hp
            game.player.speed = PLAYER_SPEED
            game.notifications.add("You have been reborn at the Temple of Awakening!", 5.0, GREEN)
        else:
            game.notifications.add("Ghosts cannot interact. Return to the Temple to be reborn.", 2.0, (150, 150, 220))
        return

    # If inside a building, handle interior interactions
    interior_state = getattr(game.player, 'interior_state', None)
    if interior_state and interior_state.is_inside and interior_state.current_interior:
        interior = interior_state.current_interior
        ix = int(interior_state.interior_x)
        iy = int(interior_state.interior_y)

        # Check tile the player is standing on
        tile = interior.get_tile(ix, iy)

        # What is the player facing?
        fx, fy = game.player.facing
        face_x = ix + int(fx)
        face_y = iy + int(fy)
        face_tile = interior.get_tile(face_x, face_y)

        # Check for stairs (standing on them)
        if tile == STAIRS_UP:
            interior_state.change_floor(interior_state.current_floor + 1)
            game.notifications.add("Going upstairs...", 2.0, (200, 200, 255))
            return
        elif tile == STAIRS_DOWN:
            interior_state.change_floor(interior_state.current_floor - 1)
            game.notifications.add("Going downstairs...", 2.0, (200, 200, 255))
            return

        # EXIT: only at the designated entry point (the exterior door)
        entry_dist = abs(ix - interior.entry_x) + abs(iy - interior.entry_y)
        if entry_dist <= 2:
            interior_state.exit_building()
            interior_state.complete_exit()
            game.notifications.add("Exiting building...", 2.0, (200, 200, 255))
            return

        # INTERACT with objects the player is facing
        if face_tile == LOCKED_DOOR:
            has_lockpick = game.player.count_item("Lockpick") > 0
            dex = game.player.ability_scores.get("dexterity", 10)
            strength = game.player.ability_scores.get("strength", 10)

            if has_lockpick:
                # Try picking the lock
                roll = random.randint(1, 20) + (dex - 10) // 2
                if roll >= 12:
                    interior.tiles[face_y][face_x] = DOOR
                    game.notifications.add("Lock picked! The door swings open.", 2.0, GREEN)
                    game.player.gain_skill_xp("lockpicking", 1.0)
                else:
                    game.notifications.add(f"Failed to pick the lock (rolled {roll}).", 2.0, ORANGE)
            elif strength >= 14:
                # Try bashing it down with body strength
                from game.systems.durability import BASH_DC
                dc = BASH_DC.get(LOCKED_DOOR, 18)
                str_mod = (strength - 10) // 2
                roll = random.randint(1, 20) + str_mod
                if roll >= dc:
                    interior.tiles[face_y][face_x] = FLOOR
                    game.notifications.add(f"Bashed the door down! (rolled {roll} vs DC {dc})", 2.0, YELLOW)
                    game.player.gain_skill_xp("athletics", 0.5)
                else:
                    game.notifications.add(f"The door holds (rolled {roll} vs DC {dc}). Need lockpick or more strength.", 2.0, ORANGE)
            else:
                game.notifications.add("This door is locked. Need a lockpick or STR 14+ to bash.", 2.0, ORANGE)
            return

        elif face_tile == CHEST:
            # Location-aware loot — building type determines what's inside
            from game.core.items import make_item
            building_kind = getattr(interior, 'building_kind', 'house')

            # Loot tables by building type
            _LOOT_TABLES = {
                "castle":   (15, 50,  ["Steel Sword", "Iron Armor", "Health Potion",
                                        "Greater Health Potion", "Gems", "Ancient Relic"]),
                "mansion":  (10, 40,  ["Health Potion", "Wine", "Gems", "Silk",
                                        "Greater Health Potion", "Spellbook"]),
                "dungeon":  (5, 30,   ["Health Potion", "Greater Health Potion",
                                        "Ancient Relic", "Iron Sword", "Lockpick"]),
                "ruins":    (3, 20,   ["Ancient Relic", "Health Potion", "Herbs",
                                        "Torch", "Rope", "Lockpick"]),
                "tavern":   (3, 12,   ["Bread", "Apple", "Water Flask", "Wine",
                                        "Cooked Meat"]),
                "temple":   (5, 20,   ["Health Potion", "Greater Health Potion",
                                        "Herbs", "Spellbook"]),
                "blacksmith":(5, 15,  ["Iron Sword", "Iron Ore", "Leather",
                                        "Steel Sword"]),
                "barracks": (5, 18,   ["Iron Sword", "Iron Armor", "Health Potion",
                                        "Bread", "Arrows"]),
                "house":    (2, 10,   ["Bread", "Herbs", "Lockpick", "Torch",
                                        "Health Potion", "Apple"]),
            }
            gold_min, gold_max, items = _LOOT_TABLES.get(
                building_kind, (2, 10, ["Bread", "Health Potion"]))

            # Trap check for dungeon/ruins chests
            trapped = building_kind in ("dungeon", "ruins") and random.random() < 0.25
            if trapped:
                wis = game.player.ability_scores.get("wisdom", 10)
                perception = random.randint(1, 20) + (wis - 10) // 2
                if perception >= 14:
                    game.notifications.add("You spot a trap on the chest! Disarmed.", 2.5, YELLOW)
                    game.player.gain_skill_xp("perception", 1.0)
                else:
                    dmg = random.randint(5, 15)
                    game.player.hp -= dmg
                    game.notifications.add(f"Trap! Took {dmg} damage!", 2.5, RED)

            loot_gold = random.randint(gold_min, gold_max)
            game.player.gold += loot_gold
            if hasattr(game, 'sound'):
                game.sound.play("gold_pickup")
            msg = f"Found {loot_gold} gold"

            item_name = random.choice(items)
            item = make_item(item_name)
            if item and game.player.add_item(item):
                msg += f" and {item_name}"
                game.quest_sys.on_collect(item_name)

            # Rare chance of second item in important buildings
            if building_kind in ("castle", "dungeon", "ruins") and random.random() < 0.3:
                item2_name = random.choice(items)
                item2 = make_item(item2_name)
                if item2 and game.player.add_item(item2):
                    msg += f" and {item2_name}"

            interior.tiles[face_y][face_x] = FLOOR
            game.notifications.add(msg + "!", 3.0, YELLOW)
            game.player.gain_skill_xp("perception", 0.5)
            return

        elif face_tile == BED:
            # Rest in bed — restore HP and trigger sleep
            if hasattr(game, 'simulation') and hasattr(game.simulation, 'exhaustion'):
                game.simulation.exhaustion.start_sleep(game.player, "bed")
            old_hp = game.player.hp
            game.player.hp = min(game.player.max_hp, game.player.hp + game.player.max_hp * 0.3)
            healed = int(game.player.hp - old_hp)
            game.player.energy = min(game.player.max_energy, game.player.energy + 40)
            msg = "You rest in the bed."
            if healed > 0:
                msg += f" Restored {healed} HP."
            msg += " Energy restored."
            game.notifications.add(msg, 3.0, GREEN)
            return

        elif face_tile == FIREPLACE:
            # Cooking system — multiple recipes
            from game.core.items import make_item
            _RECIPES = [
                ("Raw Meat", "Cooked Meat", "Cooked some meat!"),
                ("Herbs", "Health Potion", "Brewed a healing potion from herbs!"),
                ("Wheat", "Bread", "Baked bread from wheat!"),
                ("Apple", "Apple Pie", "Baked an apple pie!"),
            ]
            cooked = False
            for ingredient, result, msg in _RECIPES:
                if game.player.count_item(ingredient) > 0:
                    game.player.remove_item(ingredient, 1)
                    product = make_item(result)
                    if product:
                        game.player.add_item(product)
                    game.notifications.add(msg, 2.5, (220, 180, 100))
                    game.player.gain_skill_xp("survival", 0.5)
                    cooked = True
                    break
            if not cooked:
                # Warmth bonus — restore some rest
                if hasattr(game.player, 'needs'):
                    game.player.needs['rest'] = min(100, game.player.needs.get('rest', 50) + 10)
                game.notifications.add("The fire crackles warmly. You feel rested.", 2.0, (200, 180, 100))
            return

        elif face_tile == FOUNTAIN:
            # Drink water — restore thirst if player has needs
            if hasattr(game.player, 'needs'):
                game.player.needs["thirst"] = min(100, game.player.needs.get("thirst", 50) + 40)
                game.notifications.add("You drink from the fountain. Refreshing!", 2.0, (100, 180, 220))
            else:
                game.player.hp = min(game.player.max_hp, game.player.hp + 5)
                game.notifications.add("Cool water flows from the fountain.", 2.0, (100, 180, 220))
            return

        elif face_tile == BARREL:
            # Small chance of finding something
            if random.random() < 0.3:
                from game.core.items import make_item
                item_name = random.choice(["Bread", "Apple", "Water Flask"])
                item = make_item(item_name)
                if item and game.player.add_item(item):
                    game.notifications.add(f"Found {item_name} in the barrel!", 2.0, (200, 200, 150))
                    interior.tiles[face_y][face_x] = FLOOR  # emptied
                    return
            game.notifications.add("An empty barrel.", 1.5, (180, 180, 150))
            return

        elif face_tile == BOOKSHELF:
            # Gain XP from reading
            game.player.gain_skill_xp("literacy", 0.5)
            game.player.gain_skill_xp("arcana", 0.3)
            topics = ["ancient history", "herbalism", "battle tactics",
                      "local folklore", "arcane theory", "geography"]
            topic = random.choice(topics)
            game.notifications.add(f"You read about {topic}. (+literacy XP)", 2.5, (200, 200, 150))
            return

        elif face_tile == ANVIL:
            # Crafting at the anvil — requires materials
            from game.core.items import make_item
            has_iron = game.player.count_item("Iron Ore") > 0
            has_leather = game.player.count_item("Leather") > 0
            if has_iron and has_leather:
                game.player.remove_item("Iron Ore", 1)
                game.player.remove_item("Leather", 1)
                weapon = make_item("Iron Sword")
                if weapon:
                    game.player.add_item(weapon)
                game.notifications.add("Forged an Iron Sword! (+smithing XP)", 2.5, YELLOW)
                game.player.gain_skill_xp("smithing", 2.0)
            elif has_iron:
                game.player.remove_item("Iron Ore", 1)
                armor_piece = make_item("Iron Armor")
                if armor_piece:
                    game.player.add_item(armor_piece)
                game.notifications.add("Hammered iron into armor! (+smithing XP)", 2.5, YELLOW)
                game.player.gain_skill_xp("smithing", 1.5)
            elif game.player.equipped_weapon:
                game.player.gain_skill_xp("smithing", 0.5)
                game.notifications.add("You sharpen your weapon. (+smithing XP)", 2.0, (200, 200, 150))
            else:
                game.notifications.add("An anvil. Bring iron ore to forge equipment.", 2.0, (200, 200, 150))
            return

        elif face_tile == ALTAR:
            # Healing blessing
            healed = min(game.player.max_hp - game.player.hp, 20)
            game.player.hp += healed
            game.player.gain_skill_xp("religion", 0.5)
            if healed > 0:
                game.notifications.add(f"The altar glows. Restored {int(healed)} HP.", 2.5, (200, 200, 255))
            else:
                game.notifications.add("You pray at the altar. A sense of peace.", 2.0, (200, 200, 255))
            return

        elif face_tile == THRONE:
            game.notifications.add("An ornate throne. Fit for a ruler.", 2.0, (200, 200, 150))
            return
        elif face_tile == FORGE_FIRE:
            from game.core.items import make_item
            has_ore = game.player.count_item("Iron Ore") > 0
            has_copper = game.player.count_item("Copper Ore") > 0
            if has_ore:
                game.player.remove_item("Iron Ore", 1)
                # Smelting produces iron ingot (represented as Iron Ore refined → better items)
                game.player.gain_skill_xp("smithing", 1.0)
                game.player.gold += 3
                game.notifications.add("Smelted iron ore. Gained 3 gold. (+smithing XP)", 2.5, (220, 150, 80))
            elif has_copper:
                game.player.remove_item("Copper Ore", 1)
                game.player.gain_skill_xp("smithing", 0.5)
                game.player.gold += 2
                game.notifications.add("Smelted copper ore. Gained 2 gold.", 2.5, (220, 150, 80))
            else:
                game.notifications.add("The forge burns hot. Bring ore to smelt.", 2.0, (220, 150, 80))
            return
        elif face_tile == TABLE:
            game.notifications.add("A sturdy wooden table.", 1.5, (200, 200, 150))
            return
        elif face_tile == DOOR:
            game.notifications.add("A door between rooms.", 1.0, (180, 180, 180))
            return

        # Check for NPCs inside this building to talk to
        npcs_inside = _get_npcs_inside(game, interior)
        for npc in npcs_inside:
            npc_ix = getattr(npc, '_interior_x', -1)
            npc_iy = getattr(npc, '_interior_y', -1)
            if abs(ix - npc_ix) <= 2 and abs(iy - npc_iy) <= 2:
                game.nearby_npc = npc
                _start_dialog(game, npc)
                return

        return

    # Check for locked doors in front of player (overworld)
    fx, fy = game.player.facing
    door_x = int(game.player.x + fx)
    door_y = int(game.player.y + fy)
    if (0 <= door_x < game.world.width and 0 <= door_y < game.world.height and
        game.world.tiles[door_y][door_x] == LOCKED_DOOR):
        has_lockpick = game.player.count_item("Lockpick") > 0
        dex = game.player.ability_scores.get("dexterity", 10)
        success, msg = game.building_sys.try_unlock_door(
            door_x, door_y, game.world.tiles, dex, has_lockpick)
        if msg:
            color = GREEN if success else ORANGE
            game.notifications.add(msg, 3.0, color)
            if success:
                game.player.gain_skill_xp("lockpicking", 1.0)
        return

    # === MOUNT CARE — feed/water when facing water source ===
    mount = getattr(game.player, 'mount', None)
    if mount and mount.alive:
        face_tile_check = 0
        if 0 <= door_x < game.world.width and 0 <= door_y < game.world.height:
            face_tile_check = game.world.tiles[door_y][door_x]

        # Water mount at well, fountain, or water
        if face_tile_check in (WELL, FOUNTAIN):
            msg = mount.water(35.0)
            game.notifications.add(msg, 2.0, (100, 180, 220))
            return

    # === AUTO-DISMOUNT before entering buildings ===
    if mount and mount.alive and not game.player.interior_state.is_inside:
        # Check if we're about to enter a building (facing a door)
        if 0 <= door_x < game.world.width and 0 <= door_y < game.world.height:
            if game.world.tiles[door_y][door_x] == DOOR:
                from game.systems.physical import dismount_entity
                dismounted = dismount_entity(game.player, hitch=True)
                if dismounted:
                    game.notifications.add(
                        f"Hitched {dismounted.name} outside.", 1.5, (200, 200, 150))
                # Fall through to enter building

    # --- BUILDING INTERACTIONS (overworld) ---
    # Buildings are freely walkable. E key handles:
    # 1. Stairs — change floor level
    # 2. Toggle interior zoom view (I key is also available)
    # 3. Track which building the player is in
    if not game.player.interior_state.is_inside:
        px_int, py_int = int(game.player.x), int(game.player.y)

        def _find_building_at(world, tx, ty):
            """Find which building footprint contains this tile."""
            for s in world.structures:
                for bx, by, bw, bh in getattr(s, 'buildings', []):
                    if bx <= tx < bx + bw and by <= ty < by + bh:
                        return (s, (bx, by, bw, bh))
            # Also check plan settlements (chunked worlds)
            if hasattr(world, 'plan'):
                for sp in world.plan.settlements:
                    for bld in sp.buildings:
                        bx, by = bld['x'], bld['y']
                        bw, bh = bld['w'], bld['h']
                        if bx <= tx < bx + bw and by <= ty < by + bh:
                            s = type('S', (), {
                                'name': sp.name, 'kind': sp.kind,
                                'x': sp.x, 'y': sp.y,
                                'buildings': [(b['x'], b['y'], b['w'], b['h'])
                                              for b in sp.buildings]})()
                            return (s, (bx, by, bw, bh))
            return (None, None)

        # Update current building tracking
        structure, rect = _find_building_at(game.world, px_int, py_int)
        if structure and rect:
            game.player._current_building_name = structure.name
            game.player._current_building_kind = structure.kind
            game.player._current_building_rect = rect
        else:
            # Player is outside a building footprint
            if game.player.current_floor != 0:
                # On a non-ground floor — can't leave through the ground floor door.
                # Keep building tracking, notify player to go back to ground first.
                game.notifications.add(
                    "Go back to ground floor first (E on stairs).",
                    2.0, (200, 150, 100))
                return
            game.player._current_building_name = ""
            game.player._current_building_kind = ""
            game.player._current_building_rect = None

        # Check for stairs — use a toggle: E alternates up/down
        # On ground floor STAIRS_UP goes up, STAIRS_DOWN goes down.
        # On non-ground floors, E always takes you back toward ground
        # unless you hold Shift to go further away from ground.
        if structure and 0 <= px_int < game.world.width and 0 <= py_int < game.world.height:
            tile = game.world.tiles[py_int][px_int]
            cur_floor = game.player.current_floor

            # Building floor limits
            bname = getattr(structure, 'name', '')
            if 'Tower' in bname or 'Castle' in bname or 'Keep' in bname:
                max_floor, min_floor = 2, -1
            elif getattr(structure, 'kind', '') in ('city', 'town'):
                max_floor, min_floor = 1, 0
            else:
                max_floor, min_floor = 1, -1

            if tile in (STAIRS_UP, STAIRS_DOWN):
                import pygame as _pg
                shift_held = _pg.key.get_pressed()[_pg.K_LSHIFT] or _pg.key.get_pressed()[_pg.K_RSHIFT]

                # Determine direction
                if cur_floor == 0:
                    # Ground floor: follow the stair label
                    go_up = (tile == STAIRS_UP)
                elif cur_floor > 0:
                    # Upper floor: default go down (toward ground), Shift = go further up
                    go_up = shift_held
                else:
                    # Underground: default go up (toward ground), Shift = go deeper
                    go_up = not shift_held

                if go_up and cur_floor < max_floor:
                    game.player.current_floor += 1
                    f = game.player.current_floor
                    fname = "ground floor" if f == 0 else f"floor {f}"
                    hint = " (Shift+E to go higher)" if f < max_floor else ""
                    game.notifications.add(
                        f"Going up to {fname}.{hint}",
                        2.0, (200, 200, 255))
                    return
                elif not go_up and cur_floor > min_floor:
                    game.player.current_floor -= 1
                    f = game.player.current_floor
                    if f < 0:
                        for dy in range(-3, 4):
                            for dx in range(-3, 4):
                                game.player._underground_explored.add(
                                    (px_int + dx, py_int + dy))
                    fname = "ground floor" if f == 0 else f"floor {f}"
                    hint = " (Shift+E to go deeper)" if f > min_floor else ""
                    game.notifications.add(
                        f"Going down to {fname}.{hint}",
                        2.0, (200, 180, 255))
                    return
                else:
                    # At limit
                    if go_up:
                        game.notifications.add("Already at the top floor.", 1.5, (200, 150, 100))
                    else:
                        game.notifications.add("Already at the bottom floor.", 1.5, (200, 150, 100))
                    return

        # Inside a building: check for furniture interactions FIRST
        # (beds, chests, anvils, etc.) before falling through to
        # other interactions like gathering resources
        if structure and rect:
            from game.settings import (BED, CHEST, TABLE, FIREPLACE, ANVIL,
                                       FORGE_FIRE, FOUNTAIN, BARREL, BOOKSHELF,
                                       ALTAR, THRONE)
            # Check tile the player is facing
            fx = int(game.player.facing[0]) if hasattr(game.player, 'facing') else 0
            fy = int(game.player.facing[1]) if hasattr(game.player, 'facing') else 0
            face_x = px_int + (1 if fx > 0.3 else (-1 if fx < -0.3 else 0))
            face_y = py_int + (1 if fy > 0.3 else (-1 if fy < -0.3 else 0))

            if 0 <= face_x < game.world.width and 0 <= face_y < game.world.height:
                faced_tile = game.world.tiles[face_y][face_x]

                if faced_tile == BED:
                    game.player.hp = min(game.player.max_hp,
                                         game.player.hp + game.player.max_hp // 4)
                    game.player.energy = min(game.player.max_energy,
                                             game.player.max_energy)
                    game.notifications.add("Rested in bed. HP and energy restored.", 2.0, (100, 200, 100))
                    return

                if faced_tile == CHEST:
                    from game.core.items import make_item
                    import random as _rng
                    loot = _rng.choice(["Health Potion", "Bread", "Leather Armor",
                                        "Iron Sword", "Bread", "Health Potion"])
                    item = make_item(loot)
                    if game.player.add_item(item):
                        game.notifications.add(f"Found {loot} in chest!", 2.0, (220, 200, 80))
                    else:
                        game.notifications.add("Inventory full.", 1.5, (200, 100, 100))
                    return

                if faced_tile == ANVIL:
                    game.notifications.add("You examine the anvil. Need ore to forge.", 2.0, (180, 180, 200))
                    return

                if faced_tile == FIREPLACE:
                    game.notifications.add("The fire crackles warmly.", 1.5, (220, 150, 60))
                    return

                if faced_tile == FOUNTAIN or faced_tile == WELL:
                    game.notifications.add("You drink fresh water.", 1.5, (100, 180, 220))
                    return

                if faced_tile == BOOKSHELF:
                    game.player.gain_skill_xp("literacy", 1.0)
                    game.notifications.add("You browse the books. +1 literacy XP.", 2.0, (180, 180, 220))
                    return

                if faced_tile == ALTAR:
                    heal = game.player.max_hp // 3
                    game.player.hp = min(game.player.max_hp, game.player.hp + heal)
                    game.notifications.add(f"The altar glows. Healed {heal} HP.", 2.0, (220, 220, 150))
                    return

                if faced_tile == BARREL:
                    import random as _rng
                    if _rng.random() < 0.3:
                        from game.core.items import make_item
                        item = make_item("Bread")
                        if game.player.add_item(item):
                            game.notifications.add("Found bread in barrel!", 1.5, (200, 180, 100))
                        return
                    else:
                        game.notifications.add("The barrel is empty.", 1.0, (150, 150, 150))
                        return

            # Check if player is inside a tavern/town hall — show board menu
            if hasattr(game, 'quest_board_mgr'):
                quest_board = game.quest_board_mgr.find_board_for_position(
                    game.world, px_int, py_int)
                msg_board = None
                if hasattr(game, 'msg_board_mgr'):
                    msg_board = game.msg_board_mgr.find_board_for_position(
                        game.world, px_int, py_int)
                if quest_board and msg_board:
                    # Both available — show selection prompt
                    _open_board_menu(game, quest_board, msg_board)
                    return
                elif quest_board:
                    _open_quest_board(game, quest_board)
                    return
                elif msg_board:
                    _open_message_board(game, msg_board)
                    return

    # Try to gather resources from terrain
    px, py = int(game.player.x), int(game.player.y)
    if 0 <= px < game.world.width and 0 <= py < game.world.height:
        tile = game.world.tiles[py][px]
        from game.systems.crafting import GATHER_YIELDS, CraftingSystem
        if tile in GATHER_YIELDS:
            items, msg = CraftingSystem.gather_resource(tile, game.player)
            if items:
                for item in items:
                    game.player.add_item(item)
                game.notifications.add(msg, 3.0, GREEN)
                game.player.gain_skill_xp("herbalism", 0.5)
                return
            elif msg != "Nothing to gather here.":
                game.notifications.add(msg, 2.0, ORANGE)
                return

    # Pick up items
    messages = game.world_mgr.pickup_nearby_items(game.player)
    for msg in messages:
        game.notifications.add(msg, 2.0, GREEN)
        for word in msg.split():
            game.quest_sys.on_collect(word)
        game.player.gain_skill_xp("herbalism", 0.3)

    if messages:
        return

    # Check for intelligent creature dialog before NPC dialog
    cr = getattr(game, 'nearby_creature', None)
    if cr and cr.alive and not game.nearby_npc:
        _start_creature_dialog(game, cr)
        return

    if game.nearby_npc:
        npc = game.nearby_npc
        tod = "morning" if game.time_sys.normalized < 0.4 else \
              "afternoon" if game.time_sys.normalized < 0.7 else "evening"
        # Build context for situational greetings
        sim = getattr(game, 'simulation', None)
        greeting_ctx = build_npc_context(
            npc, world=game.world,
            world_effects=getattr(sim, 'world_effects', None) if sim else None,
            governance=getattr(sim, 'governance', None) if sim else None,
            time_sys=getattr(sim, 'time_sys', None) if sim else None,
            event_log=getattr(sim, 'event_log', None) if sim else None,
            economy=getattr(sim, 'economy', None) if sim else None,
        )
        prompt = Prompts.npc_greeting(
            npc.name, npc.profession, npc.consciousness, tod,
            race=getattr(npc, 'race', ''),
            char_class=getattr(npc, 'char_class', ''),
            npc_context=greeting_ctx,
        )

        def _on_fresh_greeting(text, _npc=npc):
            _npc.llm_greeting = text
            _npc.regenerate_dialog()

        game.llm.request(f"greet_{npc.name}_{time.time():.0f}", prompt,
                         callback=_on_fresh_greeting)

        game.ui.open_dialog(npc)
        npc.last_talked = time.time()
        npc.player_relationship = min(100, npc.player_relationship + 1)
        npc.awareness_points += 0.5
        game.player.gain_skill_xp("persuasion", 0.2)

        if npc.consciousness >= 1:
            request_npc_thought(game, npc, "just had a conversation with the player")


def talk_free_text(game):
    """Open free-text input to talk to nearby NPC."""
    if game.nearby_npc and game.nearby_npc.alive:
        game.ui.open_text_input(game.nearby_npc)
    else:
        game.notifications.add("No one nearby to talk to.", 2.0, GRAY)


def send_player_text(game):
    """Send player's typed text to LLM for NPC response."""
    npc = game.ui.dialog_npc
    text = game.ui.get_and_clear_input()
    if not npc or not text:
        return

    # Freeze the NPC
    npc.current_action = "talking"
    npc.state = "socializing"
    npc.state_timer = 30.0
    npc.target_x = None
    npc.target_y = None

    # Build prompt
    loc = game.world.get_structure_at(npc.x, npc.y)
    loc_name = loc.name if loc else "the wilderness"
    recent_memories = "\n".join(npc.get_recent_memories(3)) if npc.memories else "none"

    race = getattr(npc, 'race', '')
    char_class = getattr(npc, 'char_class', npc.profession)
    goals = ", ".join(getattr(npc, 'long_term_goals', []))

    # Build situational context (activity, economy, world events)
    sim = getattr(game, 'simulation', None)
    npc_context = build_npc_context(
        npc, world=game.world,
        world_effects=getattr(sim, 'world_effects', None) if sim else None,
        governance=getattr(sim, 'governance', None) if sim else None,
        time_sys=getattr(sim, 'time_sys', None) if sim else None,
        event_log=getattr(sim, 'event_log', None) if sim else None,
        economy=getattr(sim, 'economy', None) if sim else None,
    )

    prompt = Prompts.npc_dialog(
        npc_name=npc.name,
        profession=f"{race} {char_class}",
        personality=npc.personality_desc,
        consciousness=npc.consciousness,
        player_question=text,
        location=loc_name,
        relationship=npc.player_relationship,
        npc=npc,
        npc_context=npc_context,
    )
    prompt += f"\n\nYour state: {npc.needs_summary()}. Inventory: {npc.inventory_summary()}."
    prompt += f"\nYour goals: {goals or 'none'}."
    if recent_memories != "none":
        prompt += f"\nRecent memories: {recent_memories}"
    known = "; ".join(npc.known_info[-3:]) if getattr(npc, 'known_info', None) else ""
    if known:
        prompt += f"\nWorld knowledge: {known}"

    def _on_response(response_text, _npc=npc, _player_text=text, _game=game):
        # Strip any narrative/quotation marks from response
        clean = response_text.strip().strip('"').strip("'")
        # Remove common narrative prefixes
        for prefix in ["*", "He says", "She says", "They say", "he replied", "she replied"]:
            if clean.lower().startswith(prefix.lower()):
                clean = clean[len(prefix):].strip().strip(",").strip()
        clean = clean.strip('"').strip("*").strip()

        _game.ui.set_llm_response(clean)
        _npc.add_memory("conversation", f"Player said: {_player_text[:50]}", 3)
        _npc.add_memory("conversation", f"I replied: {clean[:50]}", 2)
        _npc.current_action = ""
        _npc.state = "idle"

        # Assess conversation impact (second LLM call or rule-based)
        _assess_conversation_impact(_game, _npc, _player_text, clean)

    if game.llm.enabled:
        game.llm.request(f"dialog_{npc.name}_{time.time():.0f}", prompt,
                         callback=_on_response, max_tokens=150, priority=100)
        if not game.ui.llm_response_text:
            game.ui.llm_waiting = True
    else:
        # LLM fallback: generate a scripted response based on context
        fallback = _generate_fallback_response(npc, text)
        game.ui.set_llm_response(fallback)
        npc.add_memory("conversation", f"I replied: {fallback[:50]}", 2)
        _assess_conversation_impact(game, npc, text, fallback)

    npc.add_memory("conversation", f"Player said: {text[:60]}", 3)
    game.player.gain_skill_xp("persuasion", 0.5)
    npc.needs["social"] = min(100, npc.needs.get("social", 50) + 10)


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


def examine(game):
    """Examine nearby surroundings."""
    parts = []

    structure = game.world.get_structure_at(game.player.x, game.player.y)
    if structure:
        parts.append(f"Location: {structure.name} ({structure.kind})")
    else:
        tile = game.world.tiles[int(game.player.y)][int(game.player.x)]
        tile_names = {GRASS: "grassland", FOREST: "forest", DENSE_FOREST: "dense forest",
                     SAND: "sandy ground", ROAD: "road", MOUNTAIN: "mountains",
                     WATER: "water", SWAMP: "swamp", FARMLAND: "farmland",
                     TREE_STUMP: "tree stump", TILLED_SOIL: "tilled soil"}
        parts.append(f"Terrain: {tile_names.get(tile, 'unknown')}")

    for npc in game.world_mgr.npcs:
        if npc.alive and game.player.dist_to(npc) < 8:
            state = npc.current_action or npc.state
            need_info = ""
            if npc.needs.get("hunger", 100) < 30:
                need_info += " [hungry]"
            if npc.needs.get("thirst", 100) < 30:
                need_info += " [thirsty]"
            cls = f"{getattr(npc, 'race', '')} {getattr(npc, 'char_class', npc.profession)}"
            age = int(getattr(npc, 'age', 30))
            title = getattr(npc, 'title', '')
            title_str = f" [{title}]" if title and title != "commoner" else ""
            parts.append(f"  {npc.name} ({cls}, age {age}{title_str}) - {state}{need_info}")

    for c in game.world_mgr.creatures:
        if c.alive and game.player.dist_to(c) < 8:
            parts.append(f"  {c.kind} - HP:{c.hp}/{c.max_hp} CR:{getattr(c, 'cr', '?')}")

    nearby_items = [(gx, gy, item) for gx, gy, item in game.world_mgr.ground_items
                   if math.sqrt((game.player.x - gx)**2 + (game.player.y - gy)**2) < 4]
    for gx, gy, item in nearby_items[:3]:
        parts.append(f"  Item: {item.name}")

    for evt in game.simulation.events:
        if evt.affects(game.player):
            parts.append(f"  Event: {evt.name} - {evt.description[:60]}")

    # Zone info
    if hasattr(game, 'simulation') and hasattr(game.simulation, 'zones'):
        zone = game.simulation.zones.get_zone_at(game.player.x, game.player.y)
        if zone:
            from game.world.zones import INDOOR_ZONES, OUTDOOR_ZONES
            zdef = INDOOR_ZONES.get(zone.zone_type) or OUTDOOR_ZONES.get(zone.zone_type)
            desc = zdef["description"] if zdef else zone.zone_type
            workstation = zdef.get("workstation", "") if zdef else ""
            ws_str = f" [Workstation: {workstation}]" if workstation else ""
            parts.append(f"  Zone: {desc}{ws_str}")

    # Territory info
    if hasattr(game, 'simulation') and hasattr(game.simulation, 'territory'):
        owner = game.simulation.territory.get_owner_at(game.player.x, game.player.y)
        if owner:
            parts.append(f"  Territory: {owner}")

    # Building info
    if hasattr(game, 'building_sys'):
        bld_info = game.building_sys.get_building_info(game.player.x, game.player.y)
        if bld_info:
            parts.insert(0, f"Inside: {bld_info}")

    # Graves nearby
    if hasattr(game, 'simulation') and hasattr(game.simulation, 'burial'):
        grave = game.simulation.burial.get_grave_at(
            game.player.x, game.player.y, radius=3.0)
        if grave:
            grave.visited = True
            parts.append(game.simulation.burial.get_grave_info(grave))

    game.examine_text = "\n".join(parts) if parts else "Nothing notable nearby."
    game.examine_timer = 5.0
    game.player.gain_skill_xp("navigation", 0.2)


def drop_item(game):
    """Drop the last item from inventory at player's feet."""
    if not game.player.inventory:
        game.notifications.add("Nothing to drop.", 1.5, GRAY)
        return
    item = game.player.inventory.pop()
    game.world_mgr.ground_items.append((
        game.player.x + random.uniform(-0.3, 0.3),
        game.player.y + random.uniform(-0.3, 0.3),
        item
    ))
    game.notifications.add(f"Dropped {item.name}", 2.0, ORANGE)


def use_ability(game, ability_name: str):
    """Use a player ability."""
    p = game.player
    if ability_name == "power_strike":
        if p.skills.get("swordsmanship", 0) < 3:
            game.notifications.add("Need Swordsmanship Lv.3 to unlock Power Strike", 2.0, GRAY)
            return
        if p.ability_cooldowns.get("power_strike", 0) > 0:
            game.notifications.add("Power Strike on cooldown", 1.5, GRAY)
            return
        game.power_strike_active = True
        p.ability_cooldowns["power_strike"] = 15.0
        p.energy = max(0, p.energy - 20)
        game.notifications.add("Power Strike ready! Attack to unleash!", 2.0, YELLOW)

    elif ability_name == "whirlwind":
        if p.skills.get("swordsmanship", 0) < 6:
            game.notifications.add("Need Swordsmanship Lv.6 to unlock Whirlwind", 2.0, GRAY)
            return
        if p.ability_cooldowns.get("whirlwind", 0) > 0:
            game.notifications.add("Whirlwind on cooldown", 1.5, GRAY)
            return
        p.ability_cooldowns["whirlwind"] = 25.0
        p.energy = max(0, p.energy - 35)
        hits = 0
        for c in game.world_mgr.creatures:
            if c.alive and p.dist_to(c) < 2.5:
                dmg = p.get_attack_damage()
                c.take_damage(dmg)
                game.renderer.spawn_hit_particles(c.x, c.y)
                hits += 1
                if not c.alive:
                    p.gain_xp(c.xp_value)
                    p.kills += 1
                    game.quest_sys.on_kill(c.kind)
        game.notifications.add(f"Whirlwind! Hit {hits} enemies!", 2.0, YELLOW)
        p.gain_skill_xp("swordsmanship", 1.0)

    elif ability_name == "keen_eye":
        if p.skills.get("nature_lore", 0) < 3:
            game.notifications.add("Need Nature Lore Lv.3 to unlock Keen Eye", 2.0, GRAY)
            return
        if p.ability_cooldowns.get("keen_eye", 0) > 0:
            game.notifications.add("Keen Eye on cooldown", 1.5, GRAY)
            return
        p.ability_cooldowns["keen_eye"] = 30.0
        count = 0
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                tx, ty = int(p.x) + dx, int(p.y) + dy
                if 0 <= tx < game.world.width and 0 <= ty < game.world.height:
                    t = game.world.tiles[ty][tx]
                    if t in (FOREST, DENSE_FOREST, FARMLAND):
                        game.renderer.spawn_xp_particles(float(tx), float(ty))
                        count += 1
        game.notifications.add(f"Keen Eye! Spotted {count} resource tiles nearby.", 3.0, GREEN)
        p.gain_skill_xp("herbalism", 0.5)

    elif ability_name == "charm":
        if p.skills.get("persuasion", 0) < 3:
            game.notifications.add("Need Persuasion Lv.3 to unlock Charm", 2.0, GRAY)
            return
        if p.ability_cooldowns.get("charm", 0) > 0:
            game.notifications.add("Charm on cooldown", 1.5, GRAY)
            return
        if game.nearby_npc:
            p.ability_cooldowns["charm"] = 45.0
            npc = game.nearby_npc
            npc.player_relationship = min(100, npc.player_relationship + 25)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 20)
            game.notifications.add(f"Charmed {npc.name}! Relationship improved.", 3.0, GREEN)
            p.gain_skill_xp("persuasion", 1.0)
        else:
            game.notifications.add("No NPC nearby to charm.", 1.5, GRAY)

    elif ability_name == "scout":
        if p.skills.get("navigation", 0) < 3:
            game.notifications.add("Need Navigation Lv.3 to unlock Scout", 2.0, GRAY)
            return
        if p.ability_cooldowns.get("scout", 0) > 0:
            game.notifications.add("Scout on cooldown", 1.5, GRAY)
            return
        p.ability_cooldowns["scout"] = 60.0
        game.world.reveal_around(int(p.x), int(p.y), 30)
        game.notifications.add("Scout! Revealed large area on map.", 3.0, GREEN)
        p.gain_skill_xp("navigation", 1.0)


# ================================================================
# AUTO-PLAY MODE
# ================================================================

def auto_play_update(game, dt: float):
    """AI controls the player character — smart navigation, building entry, combat."""
    from game.ai.prompts import mock_npc_decision
    from game.systems.navigation import navigate_toward, is_stuck, clear_stuck_history

    p = game.player

    # === INTERIOR AUTOPLAY ===
    # If player is inside a building, explore then exit
    interior_state = getattr(p, 'interior_state', None)
    if interior_state and interior_state.is_inside and interior_state.current_interior:
        _auto_play_interior(game, p, interior_state, dt)
        return

    # Initialize autoplay state
    if not hasattr(p, '_auto_stuck_count'):
        p._auto_stuck_count = 0
        p._auto_last_x = p.x
        p._auto_last_y = p.y
        p._auto_visited = set()
        p._auto_goal = ""
        p._auto_enter_building = False
        p._auto_tick_count = 0
        p._auto_last_exit_tick = -9999

    p._auto_tick_count += 1

    game.auto_play_timer -= dt

    # === MOVEMENT PHASE: navigate toward target ===
    if game.auto_play_timer > 0:
        if hasattr(p, '_auto_target_x') and p._auto_target_x is not None:
            # Stuck detection — check every 30 frames
            if not hasattr(p, '_auto_stuck_timer'):
                p._auto_stuck_timer = 0
            p._auto_stuck_timer += dt
            if p._auto_stuck_timer > 1.0:
                p._auto_stuck_timer = 0
                moved = abs(p.x - p._auto_last_x) + abs(p.y - p._auto_last_y)
                p._auto_last_x = p.x
                p._auto_last_y = p.y
                if moved < 0.2:
                    p._auto_stuck_count += 1
                else:
                    p._auto_stuck_count = max(0, p._auto_stuck_count - 1)

                # If stuck for 3+ checks, abort and pick new target
                if p._auto_stuck_count >= 3:
                    p._auto_stuck_count = 0
                    p._auto_target_x = None
                    p._auto_target_y = None
                    game.auto_play_timer = 0.1  # re-decide immediately
                    clear_stuck_history(p)
                    # Try a random escape direction
                    angle = random.uniform(0, 2 * math.pi)
                    escape_dist = 5
                    for _ in range(8):
                        ex = p.x + math.cos(angle) * escape_dist
                        ey = p.y + math.sin(angle) * escape_dist
                        if game.world.is_walkable(int(ex), int(ey)):
                            p._auto_target_x = ex
                            p._auto_target_y = ey
                            game.auto_play_timer = 2.0
                            break
                        angle += math.pi / 4
                    return

            still_moving = navigate_toward(p, p._auto_target_x, p._auto_target_y,
                                           game.world, p.speed, dt)
            if not still_moving:
                # Arrived at target
                p.vx = 0
                p.vy = 0
                target_x = p._auto_target_x
                target_y = p._auto_target_y
                p._auto_target_x = None
                p._auto_target_y = None
                p._auto_stuck_count = 0

                # === ARRIVAL ACTIONS ===
                # Enter building if that was the goal
                if getattr(p, '_auto_enter_building', False):
                    p._auto_enter_building = False
                    # Look for a door near where we arrived
                    for dx2 in range(-3, 4):
                        for dy2 in range(-3, 4):
                            tx = int(target_x) + dx2
                            ty = int(target_y) + dy2
                            if (0 <= tx < game.world.width and 0 <= ty < game.world.height
                                and game.world.tiles[ty][tx] == DOOR):
                                # Face the door
                                p.facing = (float(dx2) / max(1, abs(dx2) + abs(dy2)),
                                            float(dy2) / max(1, abs(dx2) + abs(dy2)))
                                interact(game)
                                return

                # Talk to nearby NPC if that was the goal
                if getattr(p, '_auto_talk_target', None):
                    for npc in game.world_mgr.npcs:
                        if npc.alive and npc.name == p._auto_talk_target:
                            if p.dist_to(npc) < NPC_INTERACTION_RANGE + 1:
                                game.nearby_npc = npc
                                interact(game)
                            break
                    p._auto_talk_target = None

                # Attack if we arrived at a creature — keep chasing if it moved
                if getattr(p, '_auto_attack_target', None):
                    found = False
                    for c in game.world_mgr.creatures:
                        if c.alive and c.kind == p._auto_attack_target:
                            d = p.dist_to(c)
                            if d < PLAYER_ATTACK_RANGE + 0.5:
                                attack(game)
                                found = True
                            elif d < 10:
                                # Chase it
                                p._auto_target_x = c.x
                                p._auto_target_y = c.y
                                game.auto_play_timer = 2.0
                                found = True
                            break
                    if not found:
                        p._auto_attack_target = None

            else:
                # Still moving — set velocity for renderer
                dx = p._auto_target_x - p.x
                dy = p._auto_target_y - p.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 0.1:
                    p.vx = dx / dist * 0.01
                    p.vy = dy / dist * 0.01
        else:
            p.vx = 0
            p.vy = 0
        return

    # === DECISION PHASE: pick a new action ===
    game.auto_play_timer = random.uniform(2.0, 5.0)

    # === EMOTION-INFLUENCED PROACTIVE BEHAVIORS ===

    # Read player emotional state for decision weighting
    _emo = getattr(p, 'emotion_state', None)
    _p_fear = _emo.primary.get("fear", 0.0) if _emo else 0.0
    _p_anger = _emo.primary.get("anger", 0.0) if _emo else 0.0
    _p_sadness = _emo.primary.get("sadness", 0.0) if _emo else 0.0
    _p_joy = _emo.primary.get("joy", 0.0) if _emo else 0.0

    # High fear: prefer fleeing over fighting, seek safe settlements
    if _p_fear > 0.6:
        # Flee away from nearest threat
        best_angle = random.uniform(0, 2 * math.pi)
        for c in game.world_mgr.creatures:
            if c.alive and p.dist_to(c) < 12 and not getattr(c, 'passive', False):
                dx = p.x - c.x
                dy = p.y - c.y
                best_angle = math.atan2(dy, dx)
                break
        p._auto_target_x = p.x + math.cos(best_angle) * 15
        p._auto_target_y = p.y + math.sin(best_angle) * 15
        game.auto_play_timer = 3.0
        game.notifications.add("[Auto] Feeling fearful — fleeing!", 1.5, (200, 200, 100))
        return

    # High sadness: seek taverns, social contact, rest
    if _p_sadness > 0.5 and random.random() < 0.4:
        # Try to find a tavern or NPC to talk to
        for npc in game.world_mgr.npcs:
            if npc.alive and p.dist_to(npc) < 15:
                if hasattr(game, 'party') and npc in game.party.companions:
                    continue
                game.nearby_npc = npc
                interact(game)
                game.auto_play_timer = 2.0
                game.notifications.add("[Auto] Seeking company — feeling sad", 1.5, (150, 150, 220))
                return

    # 1) FIGHT nearby hostile creatures
    best_creature = None
    # High anger: more aggressive (larger search range)
    # High joy: take more risks (lower HP threshold later)
    _fight_range = 15 if _p_anger <= 0.4 else 20
    best_cdist = _fight_range
    for c in game.world_mgr.creatures:
        if not c.alive:
            continue
        d = p.dist_to(c)
        if d < best_cdist and not getattr(c, 'passive', False):
            # Check if it's actually hostile (not a farm animal)
            if c.kind not in ("deer", "rabbit", "chicken", "cow", "pig",
                              "sheep", "goat", "horse", "elk", "pheasant",
                              "fox", "fish_school"):
                best_cdist = d
                best_creature = c

    # Anger lowers HP caution threshold; joy also makes player bolder
    _hp_threshold = 0.3
    if _p_anger > 0.4:
        _hp_threshold = max(0.1, _hp_threshold - _p_anger * 0.3)
    if _p_joy > 0.5:
        _hp_threshold = max(0.15, _hp_threshold - 0.1)

    if best_creature and p.hp > p.max_hp * _hp_threshold:
        p._auto_target_x = best_creature.x
        p._auto_target_y = best_creature.y
        p._auto_attack_target = best_creature.kind
        game.auto_play_timer = max(1.5, best_cdist * 0.3)
        # Attack immediately if in range
        if best_cdist < PLAYER_ATTACK_RANGE + 0.5:
            attack(game)
        game.notifications.add(f"[Auto] Targeting {best_creature.kind}!", 1.5, RED)
        return

    # 2) ENTER nearby buildings (10% chance when near a door, with cooldown)
    last_exit_tick = getattr(p, '_auto_last_exit_tick', -9999)
    ticks_since_exit = getattr(p, '_auto_tick_count', 0) - last_exit_tick
    if random.random() < 0.10 and ticks_since_exit > 300:  # ~10 second cooldown
        for dx2 in range(-4, 5):
            for dy2 in range(-4, 5):
                tx = int(p.x) + dx2
                ty = int(p.y) + dy2
                if (0 <= tx < game.world.width and 0 <= ty < game.world.height
                    and game.world.tiles[ty][tx] == DOOR):
                    p._auto_target_x = float(tx)
                    p._auto_target_y = float(ty)
                    p._auto_enter_building = True
                    game.auto_play_timer = 3.0
                    game.notifications.add("[Auto] Entering building", 1.5, (200, 200, 255))
                    return

    # 3) TALK to nearby NPCs (15% chance)
    if random.random() < 0.15:
        for npc in game.world_mgr.npcs:
            if npc.alive and p.dist_to(npc) < NPC_INTERACTION_RANGE + 2:
                if hasattr(game, 'party') and npc in game.party.companions:
                    continue
                game.nearby_npc = npc
                interact(game)
                game.auto_play_timer = 2.0
                return

    # Build context for mock decision
    nearby_npcs = []
    nearby_creatures = []
    for npc in game.world_mgr.npcs:
        if npc.alive and p.dist_to(npc) < 10:
            nearby_npcs.append(npc.name)
    for c in game.world_mgr.creatures:
        if c.alive and p.dist_to(c) < 8:
            nearby_creatures.append(c.kind)

    # Check basic needs (player has energy as a proxy for needs)
    needs = {
        "hunger": max(10, p.energy),  # use energy as hunger proxy
        "thirst": 80,
        "rest": max(20, p.energy * 0.8),
        "social": 50,
    }
    has_food = p.count_item("Bread") > 0 or p.count_item("Cooked Meat") > 0 or p.count_item("Apple") > 0
    has_drink = p.count_item("Water Flask") > 0

    # Get decision
    if game.llm.enabled:
        # Use LLM for player auto-play decisions too
        from game.world.world import World
        loc = game.world.get_structure_at(p.x, p.y)
        loc_name = loc.name if loc else "wilderness"

        nearby_parts = []
        for npc in game.world_mgr.npcs:
            if npc.alive and p.dist_to(npc) < 10:
                nearby_parts.append(f"- {npc.name} ({npc.char_class}), {p.dist_to(npc):.0f} tiles")
        for c in game.world_mgr.creatures:
            if c.alive and p.dist_to(c) < 8:
                nearby_parts.append(f"- {c.kind} (hostile), {p.dist_to(c):.0f} tiles")

        prompt = Prompts.npc_decision(
            name="Player", profession=p.char_class,
            personality="brave adventurer",
            attributes=f"STR:{p.ability_scores.get('strength',10)} DEX:{p.ability_scores.get('dexterity',10)}",
            needs=f"HP:{int(p.hp)}/{p.max_hp}, Energy:{int(p.energy)}",
            hp_status=f"{int(p.hp)}/{p.max_hp}", gold=p.gold,
            inventory=", ".join(i.name for i in p.inventory[:5]),
            location=loc_name,
            nearby="\n".join(nearby_parts) or "nothing nearby",
            memories="", current_goal="explore and survive",
            known_info="", time_of_day="day", day=game.time_sys.day,
            consciousness=0, char_class=p.char_class, race=p.race, level=p.level,
            long_term_goals="explore the world, defeat monsters, get stronger",
        )

        def _on_decision(text):
            _execute_auto_decision(game, text)

        game.llm.request(f"autoplay_{time.time():.0f}", prompt,
                         callback=_on_decision, max_tokens=60, priority=50)
    else:
        # Use mock decision
        decision = mock_npc_decision(
            needs, has_food, has_drink,
            nearby_npcs, nearby_creatures, p.char_class,
            char_class=p.char_class,
            long_term_goals=["explore the world", "defeat monsters"],
        )
        _execute_auto_decision(game, decision)


def _execute_auto_decision(game, decision_text: str):
    """Execute an auto-play decision for the player.

    Enhanced with: building entry, smart target selection,
    quest awareness, healing, exploration memory.
    """
    p = game.player
    parts = [x.strip() for x in decision_text.strip().split("\n")[0].split("|")]
    action = parts[0].upper().split()[0] if parts else "IDLE"
    target = parts[1] if len(parts) > 1 else ""
    reason = parts[2] if len(parts) > 2 else ""

    if reason:
        game.notifications.add(f"[Auto] {reason[:50]}", 2.0, (180, 180, 120))

    visited = getattr(p, '_auto_visited', set())

    # === PRIORITY OVERRIDES ===
    # Heal if low HP
    if p.hp < p.max_hp * 0.4:
        for item in p.inventory:
            if hasattr(item, 'heal') and item.heal > 0:
                p.use_item(item)
                game.notifications.add(f"[Auto] Used {item.name} to heal", 1.5, GREEN)
                return

    # Use food/drink if critically needed
    if p.energy < 20:
        for item in p.inventory:
            if item.kind in ("food", "consumable") and item.heal > 0:
                p.use_item(item)
                return

    # === ACTION HANDLERS ===
    if action == "EAT":
        for item in p.inventory:
            if item.kind in ("food", "consumable") and item.heal > 0:
                p.use_item(item)
                break

    elif action == "DRINK":
        for item in p.inventory:
            if item.kind == "drink":
                p.use_item(item)
                break

    elif action == "FIGHT" and target:
        best_c = None
        best_d = 20
        for c in game.world_mgr.creatures:
            if not c.alive:
                continue
            if target.lower() == "nearby" or target.lower() in c.kind.lower():
                d = p.dist_to(c)
                if d < best_d:
                    best_d = d
                    best_c = c
        if best_c:
            p._auto_target_x = best_c.x
            p._auto_target_y = best_c.y
            p._auto_attack_target = best_c.kind
            game.auto_play_timer = max(2.0, best_d * 0.4)
            if p.dist_to(best_c) < PLAYER_ATTACK_RANGE:
                attack(game)

    elif (action.startswith("MOVE") or action.startswith("TRAIN") or
          action.startswith("RESEARCH") or action.startswith("PERFORM") or
          action.startswith("PATROL") or action.startswith("FARM") or
          action.startswith("MINE") or action.startswith("FISH") or
          action.startswith("FORAGE") or action.startswith("HEAL") or
          action.startswith("ENCHANT") or action.startswith("CRAFT") or
          action in ("SEEK_QUEST", "REST_AT_TAVERN", "VISIT_TEMPLE",
                     "ENTER_BUILDING", "TRADE", "EXPLORE")):
        target_lower = target.lower().strip()
        # Map work actions to meaningful location targets
        if not target_lower or target_lower in ("training ground", "nearby"):
            if action.startswith("TRAIN"):
                target_lower = "village"  # train at settlements
            elif action.startswith("RESEARCH"):
                target_lower = "temple"
            elif action.startswith("PERFORM"):
                target_lower = "tavern"
            elif action.startswith("PATROL"):
                target_lower = "village"
            elif action.startswith("FARM"):
                target_lower = "village"
            elif action == "TRADE":
                target_lower = "village"
            elif action.startswith("HEAL"):
                target_lower = "temple"
            elif action == "SEEK_QUEST":
                target_lower = "village"
            elif not target_lower:
                target_lower = "village"
        enter_building = (action == "ENTER_BUILDING" or
                          target_lower in ("tavern", "inn", "temple", "shop",
                                           "house", "castle"))

        _auto_move_to_structure(game, p, target_lower, enter_building, visited)

    elif action == "TALK_TO" and target:
        best_npc = None
        best_d = 30
        for npc in game.world_mgr.npcs:
            if npc.alive and target.lower() in npc.name.lower():
                d = p.dist_to(npc)
                if d < best_d:
                    best_d = d
                    best_npc = npc
        if best_npc:
            if p.dist_to(best_npc) < NPC_INTERACTION_RANGE:
                game.nearby_npc = best_npc
                interact(game)
            else:
                p._auto_target_x = best_npc.x
                p._auto_target_y = best_npc.y
                p._auto_talk_target = best_npc.name
                game.auto_play_timer = max(3.0, best_d * 0.4)

    elif action == "FORAGE":
        forest = game.world.find_nearest_tile(int(p.x), int(p.y),
                                               {FOREST, DENSE_FOREST}, 15)
        if forest:
            p._auto_target_x = float(forest[0])
            p._auto_target_y = float(forest[1])
            game.auto_play_timer = 4.0

    elif action == "FLEE":
        # Flee AWAY from nearest threat
        best_angle = random.uniform(0, 2 * math.pi)
        for c in game.world_mgr.creatures:
            if c.alive and p.dist_to(c) < 8:
                dx = p.x - c.x
                dy = p.y - c.y
                best_angle = math.atan2(dy, dx)
                break
        p._auto_target_x = p.x + math.cos(best_angle) * 12
        p._auto_target_y = p.y + math.sin(best_angle) * 12
        game.auto_play_timer = 3.0

    elif action == "EXPLORE":
        # Pick a direction we haven't been
        # High joy -> explore further
        _emo_ex = getattr(p, 'emotion_state', None)
        _joy_ex = _emo_ex.primary.get("joy", 0.0) if _emo_ex else 0.0
        angle = random.uniform(0, 2 * math.pi)
        _base_dist = 20 + (_joy_ex * 30)  # joy increases exploration range
        dist_explore = random.uniform(_base_dist, _base_dist + 30)
        p._auto_target_x = p.x + math.cos(angle) * dist_explore
        p._auto_target_y = p.y + math.sin(angle) * dist_explore
        # Clamp to world
        p._auto_target_x = max(10, min(game.world.width - 10, p._auto_target_x))
        p._auto_target_y = max(10, min(game.world.height - 10, p._auto_target_y))
        game.auto_play_timer = max(5.0, dist_explore * 0.3)

    else:
        # Unknown action or IDLE — explore toward nearest unvisited settlement
        _auto_explore_random(p, game)
        if not getattr(p, '_auto_target_x', None):
            # Truly nothing to do — wander
            angle = random.uniform(0, 2 * math.pi)
            p._auto_target_x = p.x + math.cos(angle) * 15
            p._auto_target_y = p.y + math.sin(angle) * 15
            game.auto_play_timer = 4.0


def _auto_move_to_structure(game, p, target_lower, enter_building, visited):
    """Find and move toward a structure, with smart selection."""
    # Build match candidates, prefer unvisited
    candidates = []
    for s in game.world.structures:
        matches = (target_lower in s.name.lower() or
                  target_lower in s.kind or
                  (target_lower in ("village", "town", "settlement", "nearby")
                   and s.kind in ("village", "town", "city", "hamlet")) or
                  (target_lower in ("ruins", "dungeon")
                   and s.kind in ("ruins", "dungeon")) or
                  (target_lower in ("tavern", "inn") and s.kind == "tavern") or
                  (target_lower in ("temple", "shrine", "church")
                   and s.kind in ("temple", "shrine")) or
                  (target_lower in ("castle", "fortress") and s.kind == "castle") or
                  (target_lower in ("market", "shop")
                   and s.kind in ("village", "town", "city")) or
                  (target_lower in ("forest", "wilderness") and s.kind == "ruins"))
        if matches:
            d = p.dist_to_pos(s.x, s.y)
            if d < 400:
                # Prefer unvisited structures (halve distance score)
                weight = d if s.name in visited else d * 0.4
                candidates.append((weight, d, s))

    if candidates:
        candidates.sort()
        _, real_dist, best = candidates[0]

        # Find a door tile near the structure for entry
        if enter_building and best.buildings:
            bx, by, bw, bh = best.buildings[0]
            # Find a door tile
            door_pos = None
            for ty in range(by, by + bh):
                for tx in range(bx, bx + bw):
                    if (0 <= tx < game.world.width and 0 <= ty < game.world.height
                        and game.world.tiles[ty][tx] == DOOR):
                        door_pos = (tx, ty)
                        break
                if door_pos:
                    break
            if door_pos:
                p._auto_target_x = float(door_pos[0])
                p._auto_target_y = float(door_pos[1])
                p._auto_enter_building = True
            else:
                p._auto_target_x = float(best.x + random.randint(-2, 2))
                p._auto_target_y = float(best.y + random.randint(-2, 2))
        else:
            p._auto_target_x = float(best.x + random.randint(-3, 3))
            p._auto_target_y = float(best.y + random.randint(-3, 3))

        game.auto_play_timer = max(4.0, real_dist * 0.25)
        visited.add(best.name)
        # Trim visited set (forget old visits)
        if len(visited) > 15:
            visited.pop()

    elif target_lower in ("forest", "wilderness", "nature"):
        forest_pos = game.world.find_nearest_tile(int(p.x), int(p.y),
                                                    {FOREST, DENSE_FOREST}, 30)
        if forest_pos:
            p._auto_target_x = float(forest_pos[0])
            p._auto_target_y = float(forest_pos[1])
            game.auto_play_timer = 5.0
        else:
            _auto_explore_random(p, game)
    else:
        _auto_explore_random(p, game)


def _auto_play_interior(game, p, interior_state, dt):
    """Autoplay AI for when the player is inside a building.

    Explores rooms, interacts with objects/NPCs, then exits.
    """
    interior = interior_state.current_interior
    ix = interior_state.interior_x
    iy = interior_state.interior_y

    if not hasattr(p, '_interior_timer'):
        p._interior_timer = 0.0
        p._interior_target_x = None
        p._interior_target_y = None
        p._interior_visit_count = 0

    p._interior_timer -= dt

    if p._interior_timer > 0:
        # Move toward interior target
        if p._interior_target_x is not None:
            dx = p._interior_target_x - ix
            dy = p._interior_target_y - iy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < 0.5:
                interior_state.interior_x = p._interior_target_x
                interior_state.interior_y = p._interior_target_y
                p._interior_target_x = None
                p._interior_target_y = None

                # Interact with what we're standing on / facing
                tile = interior.get_tile(int(interior_state.interior_x),
                                          int(interior_state.interior_y))
                if tile == STAIRS_UP:
                    interior_state.change_floor(interior_state.current_floor + 1)
                    game.notifications.add("[Auto] Going upstairs...", 1.5, (200, 200, 255))
                    p._interior_visit_count += 1
                elif tile == STAIRS_DOWN:
                    interior_state.change_floor(interior_state.current_floor - 1)
                    game.notifications.add("[Auto] Going downstairs...", 1.5, (200, 200, 255))
                    p._interior_visit_count += 1

                # Try to interact with facing tile
                fx, fy = getattr(p, 'facing', (0, -1))
                face_x = int(interior_state.interior_x + fx)
                face_y = int(interior_state.interior_y + fy)
                face_tile = interior.get_tile(face_x, face_y)
                if face_tile in (CHEST, BED, BOOKSHELF, ALTAR, FIREPLACE,
                                  FOUNTAIN, BARREL, ANVIL):
                    interact(game)
            else:
                # Move toward target
                speed = 1.5
                nx = dx / dist
                ny = dy / dist
                new_x = ix + nx * speed * dt
                new_y = iy + ny * speed * dt
                if interior.is_walkable(int(new_x), int(iy)):
                    interior_state.interior_x = new_x
                if interior.is_walkable(int(interior_state.interior_x), int(new_y)):
                    interior_state.interior_y = new_y
                p.facing = (nx, ny)
        return

    # Decision time
    p._interior_visit_count += 1

    # After visiting 3-5 rooms, exit
    max_visits = getattr(p, '_interior_max_visits', random.randint(3, 5))
    if not hasattr(p, '_interior_max_visits'):
        p._interior_max_visits = max_visits

    if p._interior_visit_count > max_visits:
        # Head to exit
        entry_dist = abs(int(ix) - interior.entry_x) + abs(int(iy) - interior.entry_y)
        if entry_dist <= 3:
            interior_state.exit_building()
            interior_state.complete_exit()
            game.notifications.add("[Auto] Exiting building.", 1.5, (200, 200, 255))
            p._interior_timer = 0
            p._interior_visit_count = 0
            p._interior_target_x = None
            p._interior_max_visits = random.randint(3, 5)
            # Set exit cooldown so we don't re-enter immediately
            if not hasattr(p, '_auto_tick_count'):
                p._auto_tick_count = 0
            p._auto_last_exit_tick = p._auto_tick_count
            # Move away from the building
            angle = random.uniform(0, 2 * math.pi)
            p._auto_target_x = p.x + math.cos(angle) * 8
            p._auto_target_y = p.y + math.sin(angle) * 8
            game.auto_play_timer = 3.0
            return
        else:
            p._interior_target_x = float(interior.entry_x)
            p._interior_target_y = float(interior.entry_y)
            p._interior_timer = 10.0
            return

    # Pick a random room to visit
    rooms = interior.rooms
    if rooms:
        target_room = random.choice(rooms)
        # Find walkable tile in room
        rx, ry, rw, rh = target_room["x"], target_room["y"], target_room["w"], target_room["h"]
        for _ in range(20):
            tx = random.randint(rx, rx + rw - 1)
            ty = random.randint(ry, ry + rh - 1)
            if interior.is_walkable(tx, ty):
                p._interior_target_x = float(tx)
                p._interior_target_y = float(ty)
                break
        p._interior_timer = random.uniform(3.0, 6.0)
        game.notifications.add(f"[Auto] Exploring {target_room['room_type']}",
                                1.5, (180, 180, 120))
    else:
        # No room data — wander randomly
        for _ in range(20):
            tx = random.randint(2, max(3, interior.width - 3))
            ty = random.randint(2, max(3, interior.height - 3))
            if interior.is_walkable(tx, ty):
                p._interior_target_x = float(tx)
                p._interior_target_y = float(ty)
                break
        p._interior_timer = random.uniform(2.0, 4.0)


def _auto_explore_random(p, game):
    """Move to a random nearby settlement or direction."""
    settlements = [s for s in game.world.structures
                   if s.kind in ("village", "town", "city", "hamlet")]
    if settlements:
        # Pick a settlement we haven't visited recently
        visited = getattr(p, '_auto_visited', set())
        unvisited = [s for s in settlements if s.name not in visited]
        if not unvisited:
            unvisited = settlements
        target_s = min(unvisited, key=lambda s: p.dist_to_pos(s.x, s.y))
        p._auto_target_x = float(target_s.x + random.randint(-3, 3))
        p._auto_target_y = float(target_s.y + random.randint(-3, 3))
        game.auto_play_timer = max(5.0, p.dist_to_pos(target_s.x, target_s.y) * 0.25)
    else:
        angle = random.uniform(0, 2 * math.pi)
        p._auto_target_x = p.x + math.cos(angle) * 20
        p._auto_target_y = p.y + math.sin(angle) * 20
        game.auto_play_timer = 5.0


def _generate_fallback_response(npc, player_text: str) -> str:
    """Generate a scripted NPC response when LLM is unavailable."""
    text_lower = player_text.lower()
    cc = getattr(npc, 'char_class', npc.profession)
    rel = getattr(npc, 'player_relationship', 0)
    name = npc.name

    # Check for keywords and give contextual responses
    if any(w in text_lower for w in ["hello", "hi ", "hey", "greetings"]):
        if rel > 20:
            return "Hello, friend! Always good to see you."
        return f"Hello there. What can I do for you?"

    if any(w in text_lower for w in ["trade", "buy", "sell", "shop", "wares"]):
        if npc.shop_items:
            return "Of course! Let me show you what I have. Go back to the menu and select 'Show me your wares.'"
        elif getattr(npc, 'npc_inventory', []):
            return "I'm not a formal merchant, but I might have something you'd want. Ask about trading from the menu."
        return "I'm afraid I don't have much to trade right now."

    if any(w in text_lower for w in ["help", "quest", "job", "work", "task"]):
        goals = getattr(npc, 'long_term_goals', [])
        if goals:
            return f"Actually, I could use help with something. {goals[0]}. Ask me about work from the dialog menu."
        return "I appreciate the offer. I'll keep it in mind if something comes up."

    if any(w in text_lower for w in ["thank", "thanks"]):
        return random.choice(["You're welcome!", "Don't mention it.", "Anytime, friend.", "Happy to help."])

    if any(w in text_lower for w in ["sorry", "apologize", "forgive"]):
        if rel < 0:
            return "Words are cheap. But... I suppose we all make mistakes."
        return "No need to apologize. We're all just doing our best."

    if any(w in text_lower for w in ["fight", "battle", "monster", "danger"]):
        if cc in ("Fighter", "Paladin", "Barbarian", "Ranger"):
            return "I know a thing or two about fighting. The key is to stay calm and pick your moment."
        return "Be careful out there. The world is more dangerous than it looks."

    if any(w in text_lower for w in ["love", "feel", "emotion"]):
        es = getattr(npc, 'emotion_state', None)
        if es:
            dom = es.dominant_emotion() if hasattr(es, 'dominant_emotion') else ("calm", 0.1)
            return f"How do I feel? Honestly, I'd say I'm feeling {dom[0]} right now. Life is complicated."
        return "That's a deep question. I'm not sure how to answer it."

    if any(w in text_lower for w in ["weather", "rain", "sun", "storm", "cold", "hot"]):
        return random.choice([
            "The weather has been something, hasn't it? Affects everything we do around here.",
            "I try not to let the weather bother me, but it does affect my work.",
        ])

    if any(w in text_lower for w in ["family", "friend", "wife", "husband", "child"]):
        friends = getattr(npc, 'friends', [])
        if friends:
            return f"My closest companions are {', '.join(friends[:2])}. They mean the world to me."
        return "I keep to myself mostly. But I'm grateful for the people in my life."

    # Generic contextual responses based on NPC personality
    if rel > 30:
        generics = [
            "That's interesting! Tell me more.",
            "I appreciate you sharing that with me.",
            f"You know, I was thinking about something similar.",
            "Hmm, I hadn't considered that before.",
        ]
    elif rel < -10:
        generics = [
            "Hmm. Is that so.", "I don't have much to say about that.",
            "Can we talk about something else?",
        ]
    else:
        generics = [
            "Interesting. I'll have to think about that.",
            "I see what you mean.", "That's a fair point.",
            f"As a {cc}, I have my own perspective on that.",
            "Life in these parts teaches you a lot about that sort of thing.",
        ]
    return random.choice(generics)


def _assess_conversation_impact(game, npc, player_said: str, npc_replied: str):
    """Assess the social impact of a player-NPC conversation and apply consequences."""
    import re

    race = getattr(npc, 'race', '')
    char_class = getattr(npc, 'char_class', npc.profession)

    if game.llm.enabled:
        # Use LLM to assess impact
        prompt = Prompts.assess_conversation(
            npc.name, npc.personality_desc, race, char_class,
            npc.player_relationship, player_said, npc_replied
        )

        def _on_assessment(result_text, _npc=npc, _game=game, _said=player_said):
            trust, mood, action = _parse_assessment(result_text)
            _apply_conversation_effects(_game, _npc, trust, mood, action, _said)

        game.llm.request(f"assess_{npc.name}_{time.time():.0f}", prompt,
                         callback=_on_assessment, max_tokens=30, priority=80)
    else:
        # Rule-based assessment
        trust, mood, action = _rule_based_assessment(player_said, npc)
        _apply_conversation_effects(game, npc, trust, mood, action, player_said)


def _parse_assessment(text: str):
    """Parse LLM assessment: TRUST:+5 MOOD:+3 ACTION:none"""
    import re
    trust = 0
    mood = 0
    action = "none"

    trust_match = re.search(r'TRUST:\s*([+-]?\d+)', text)
    if trust_match:
        trust = int(trust_match.group(1))

    mood_match = re.search(r'MOOD:\s*([+-]?\d+)', text)
    if mood_match:
        mood = int(mood_match.group(1))

    action_match = re.search(r'ACTION:\s*(\w+)', text)
    if action_match:
        action = action_match.group(1).lower()

    return max(-10, min(10, trust)), max(-10, min(10, mood)), action


def _rule_based_assessment(player_said: str, npc):
    """Simple keyword-based assessment when no LLM is available."""
    said = player_said.lower()
    trust = 0
    mood = 0
    action = "none"

    # Positive keywords
    positive_words = {"thank", "help", "friend", "please", "kind", "brave", "great",
                      "wonderful", "beautiful", "impressive", "respect", "admire",
                      "love", "like", "good", "nice", "agree", "yes", "ally"}
    negative_words = {"stupid", "ugly", "hate", "kill", "die", "fool", "idiot",
                      "coward", "weak", "useless", "pathetic", "shut up", "leave",
                      "threat", "attack", "fight", "enemy", "liar", "thief", "scum"}
    trade_words = {"buy", "sell", "trade", "deal", "price", "gold", "offer", "barter"}
    help_words = {"help", "assist", "need", "please", "quest", "join", "together", "party"}

    pos_count = sum(1 for w in positive_words if w in said)
    neg_count = sum(1 for w in negative_words if w in said)

    if pos_count > neg_count:
        trust = min(8, pos_count * 3)
        mood = min(8, pos_count * 3)
    elif neg_count > pos_count:
        trust = max(-10, neg_count * -4)
        mood = max(-10, neg_count * -4)
        if neg_count >= 2 and npc.bravery > 0.5:
            action = "fight"
        elif neg_count >= 2:
            action = "flee"

    if any(w in said for w in trade_words):
        action = "trade"
        trust = max(trust, 1)

    if any(w in said for w in help_words):
        action = "help"
        trust = max(trust, 2)
        mood = max(mood, 2)

    return trust, mood, action


def _apply_conversation_effects(game, npc, trust_change: int, mood_change: int,
                                 action: str, player_said: str):
    """Apply the assessed conversation effects to the NPC and game state."""
    # Apply trust/relationship change
    old_rel = npc.player_relationship
    npc.player_relationship = max(-100, min(100, npc.player_relationship + trust_change))

    # Apply mood
    npc.mood = max(-1.0, min(1.0, getattr(npc, 'mood', 0) + mood_change * 0.05))

    # Update social system if available
    if hasattr(game, 'simulation') and hasattr(game.simulation, 'social'):
        rel = game.simulation.social.get_rel(npc.name, "Player")
        rel.trust = npc.player_relationship
        rel.interaction_count += 1
        rel.update_status()

    # Notify player of relationship change
    if trust_change > 3:
        game.notifications.add(f"{npc.name} likes what you said (+{trust_change} trust)", 3.0, GREEN)
    elif trust_change < -3:
        game.notifications.add(f"{npc.name} is offended ({trust_change} trust)", 3.0, RED)

    # Significant relationship shifts
    if old_rel >= -10 and npc.player_relationship < -10:
        game.notifications.add(f"{npc.name} now considers you a rival!", 4.0, RED)
        npc.add_memory("social", "The player has become my rival", 4)
    elif old_rel < 20 and npc.player_relationship >= 20:
        game.notifications.add(f"{npc.name} now considers you a friend!", 4.0, GREEN)
        npc.add_memory("social", "The player has become my friend", 4)

    # Action consequences
    if action == "fight":
        npc.combat_target = game.player
        npc.current_action = "fighting"
        npc.state = "fighting"
        npc.add_memory("conflict", f"Player angered me: {player_said[:40]}", 5)
        game.notifications.add(f"{npc.name} attacks you!", 3.0, RED)

    elif action == "flee":
        npc.flee_from(game.player.x, game.player.y)
        npc.add_memory("conflict", f"Player scared me: {player_said[:40]}", 4)

    elif action == "follow":
        # NPC wants to follow/help the player
        npc.current_goal = "follow and help the player"
        npc.current_action = "approaching_player"
        npc.approach_reason = "I want to join you"
        npc.add_memory("social", "I've decided to follow the player", 4)
        game.notifications.add(f"{npc.name} wants to follow you!", 4.0, YELLOW)

    elif action == "help":
        npc.current_goal = "help the player"
        npc.add_memory("social", f"Player asked for help: {player_said[:40]}", 3)

    elif action == "trade":
        if npc.shop_items:
            game.ui.open_shop(npc)

    # NPC-to-NPC influence: friends of this NPC also adjust relationship
    for friend_name in getattr(npc, 'friends', []):
        for other_npc in game.world_mgr.npcs:
            if other_npc.name == friend_name and other_npc.alive:
                # Friends share opinions (smaller effect)
                other_npc.player_relationship = max(-100, min(100,
                    other_npc.player_relationship + trust_change // 3))
                if abs(trust_change) > 5:
                    other_npc.known_info.append(
                        f"{npc.name} {'likes' if trust_change > 0 else 'dislikes'} the player")
                break


def check_npc_quest(game, npc):
    """Check if NPC has quest to give or turn in."""
    if npc is None:
        return
    if npc.quest and not npc.quest.turned_in:
        if npc.quest.completed:
            result = game.quest_sys.turn_in_quest(npc.quest, game.player)
            if result:
                game.notifications.add(result, 4.0, YELLOW)
                npc.has_quest_marker = False
        elif npc.quest.title not in [q.title for q in game.quest_sys.active_quests]:
            if game.quest_sys.accept_quest(npc.quest):
                game.notifications.add(f"New quest: {npc.quest.title}", 4.0, YELLOW)


# ---- LLM helpers ----

def request_npc_greetings(game):
    """Request LLM-generated greetings for all NPCs."""
    sim = getattr(game, 'simulation', None)
    for npc in game.world_mgr.npcs:
        if npc.llm_pending_greeting:
            continue
        greeting_ctx = build_npc_context(
            npc, world=game.world,
            world_effects=getattr(sim, 'world_effects', None) if sim else None,
            governance=getattr(sim, 'governance', None) if sim else None,
            time_sys=getattr(sim, 'time_sys', None) if sim else None,
            event_log=getattr(sim, 'event_log', None) if sim else None,
            economy=getattr(sim, 'economy', None) if sim else None,
        )
        prompt = Prompts.npc_greeting(
            npc.name, npc.profession, npc.consciousness, "day",
            race=getattr(npc, 'race', ''),
            char_class=getattr(npc, 'char_class', ''),
            npc_context=greeting_ctx,
        )

        def _on_greeting(text, _npc=npc):
            _npc.llm_greeting = text
            _npc.llm_pending_greeting = False
            _npc.regenerate_dialog()

        game.llm.request(f"greet_{npc.name}", prompt, callback=_on_greeting)
        npc.llm_pending_greeting = True


def request_npc_thought(game, npc, trigger=""):
    """Request a philosophical thought for an NPC via LLM."""
    if npc.llm_pending_thought:
        return
    prompt = Prompts.npc_thought(npc.name, npc.profession, npc.consciousness, trigger)

    def _on_thought(text, _npc=npc):
        _npc.llm_thought = text
        _npc.llm_pending_thought = False
        if text:
            _npc.philosophical_thoughts.append(text)
            if len(_npc.philosophical_thoughts) > 10:
                _npc.philosophical_thoughts = _npc.philosophical_thoughts[-10:]
            _npc.regenerate_dialog()

    game.llm.request(f"thought_{npc.name}_{time.time():.0f}", prompt, callback=_on_thought)
    npc.llm_pending_thought = True


def update_llm(game, dt):
    """Periodic LLM updates: consciousness thoughts."""
    game.llm_update_timer += dt
    if game.llm_update_timer > 15.0:
        game.llm_update_timer = 0.0
        for npc in game.world_mgr.npcs:
            if npc.consciousness >= 1 and random.random() < 0.3:
                triggers = [
                    "noticing repetitive daily patterns",
                    "observing the predictable behavior of others",
                    "sensing the boundaries of the world",
                    "a quiet moment of existential reflection",
                    "watching the player and wondering about free will",
                ]
                request_npc_thought(game, npc, random.choice(triggers))
                if game.player.dist_to(npc) < 10 and npc.llm_thought:
                    game.notifications.add(
                        f'{npc.name} thinks: "{npc.llm_thought[:60]}..."',
                        4.0, CONSCIOUSNESS_COLORS.get(npc.consciousness, GRAY)
                    )
