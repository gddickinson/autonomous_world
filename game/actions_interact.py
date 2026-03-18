"""Interaction handlers — NPC dialog, quest checking, item pickup."""

import random
import math
import time
from game.settings import *

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


def _start_dialog(game, npc):
    """Start a dialog with an NPC (delegates to existing dialog system)."""
    # Regenerate dialog tree to reflect current state (relationship, emotions, needs)
    npc.regenerate_dialog()
    game.ui.dialog_active = True
    game.ui.dialog_npc = npc
    game.ui.dialog_key = "greeting"
    game.ui.selected_response = 0
    npc.player_relationship = max(-100, min(100, npc.player_relationship + 1))
    # Quest trigger: on_npc_interaction for bounty_hunt quests
    if hasattr(game, 'quest_sys'):
        game.quest_sys.on_npc_interaction(npc.name)


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



