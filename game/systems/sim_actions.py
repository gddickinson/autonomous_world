"""Simulation actions — NPC action execution, progress, completion."""

import random
import math
import time
from typing import List, Optional
from game.core.npc import NPC
from game.core.player import Player
from game.core.items import make_item, FOOD_ITEMS
from game.settings import *


class SimActionsMixin:
    """Action execution and progress methods."""

    def _execute_action(self, npc: NPC, action: str, target: str, reason: str):
        action = action.split()[0]  # Just the first word
        # Clear stale movement targets so timed actions don't get stuck
        # (individual actions that need movement will re-set these)
        if action not in ("MOVE_TO", "MOVE", "APPROACH_PLAYER", "FLEE"):
            npc.target_x = None
            npc.target_y = None

        if action == "EAT":
            eaten = npc.consume_food()
            if eaten:
                npc.add_memory("action", f"Ate {eaten}", 1)
                npc.current_action = ""
            else:
                npc.current_goal = "find food"
                self._move_to_forage(npc)

        elif action == "DRINK":
            drunk = npc.consume_drink()
            if drunk:
                npc.add_memory("action", f"Drank {drunk}", 1)
                npc.current_action = ""
            else:
                # Try to find water source
                water = self.world.find_water_near(int(npc.x), int(npc.y))
                if water:
                    npc.target_x, npc.target_y = float(water[0]), float(water[1])
                    npc.state = "walking"
                    npc.current_action = "seeking_water"
                    npc.current_goal = "find water"

        elif action == "SLEEP":
            npc.current_action = "sleeping"
            npc.state = "sleeping"
            npc.target_x = npc.home_x
            npc.target_y = npc.home_y
            npc.state_timer = random.uniform(10, 30)
            npc.action_timer = npc.state_timer

        elif action == "FORAGE":
            self._move_to_forage(npc)

        elif action == "CHOP_TREE":
            tree = self.world.find_nearest_tile(int(npc.x), int(npc.y), {FOREST, DENSE_FOREST}, 8)
            if tree and npc.npc_has_item("Axe"):
                npc.target_x, npc.target_y = float(tree[0]), float(tree[1])
                npc.current_action = "chopping"
                npc.action_timer = NPC_CHOP_TIME - npc.attributes.get("strength", 5) * 0.3
                npc.action_target = tree
                npc.state = "working"
            else:
                npc.current_action = ""

        elif action == "MINE_ROCK":
            rock = self.world.find_nearest_tile(int(npc.x), int(npc.y), {MOUNTAIN}, 8)
            if rock and npc.npc_has_item("Pickaxe"):
                npc.target_x, npc.target_y = float(rock[0]), float(rock[1])
                npc.current_action = "mining"
                npc.action_timer = NPC_MINE_TIME - npc.attributes.get("strength", 5) * 0.4
                npc.action_target = rock
                npc.state = "working"

        elif action == "BUILD":
            what = target.lower() if target else "floor"
            # Need wood for floor, stone for wall
            if "wall" in what and npc.npc_count_item("Stone") >= 2:
                npc.current_action = "building"
                npc.action_target = ("wall", BUILT_WALL)
                npc.action_timer = NPC_BUILD_TIME
            elif npc.npc_count_item("Wood") >= 2:
                npc.current_action = "building"
                npc.action_target = ("floor", BUILT_FLOOR)
                npc.action_timer = NPC_BUILD_TIME
            else:
                npc.current_action = ""

        elif action == "FARM":
            sub = target.lower() if target else "plant"
            if "harvest" in sub:
                farm = self.world.find_nearest_tile(int(npc.x), int(npc.y), {FARMLAND}, 6)
                if farm:
                    npc.target_x, npc.target_y = float(farm[0]), float(farm[1])
                    npc.current_action = "farming"
                    npc.action_target = "harvest"
                    npc.action_timer = NPC_FARM_TIME
            else:
                if npc.npc_has_item("Hoe") and npc.npc_has_item("Seeds"):
                    grass = self.world.find_nearest_tile(int(npc.x), int(npc.y), {GRASS}, 8)
                    if grass:
                        npc.target_x, npc.target_y = float(grass[0]), float(grass[1])
                        npc.current_action = "farming"
                        npc.action_target = "plant"
                        npc.action_timer = NPC_FARM_TIME

        elif action == "FISH":
            water = self.world.find_water_near(int(npc.x), int(npc.y), 6)
            if water and npc.npc_has_item("Fishing Rod"):
                npc.target_x, npc.target_y = float(water[0]), float(water[1])
                npc.current_action = "fishing"
                npc.action_timer = NPC_FORAGE_TIME
                npc.state = "working"

        elif action == "TALK_TO":
            self._start_talk(npc, target)

        elif action == "TRADE":
            self._start_trade(npc, target)

        elif action == "PERSUADE":
            self._start_persuade(npc, target)

        elif action == "FIGHT":
            self._start_fight(npc, target)

        elif action == "FLEE":
            npc.state = "fleeing"
            angle = random.uniform(0, 2 * math.pi)
            npc.target_x = npc.x + math.cos(angle) * 12
            npc.target_y = npc.y + math.sin(angle) * 12
            npc.state_timer = 5.0
            npc.current_action = "fleeing"

        elif action == "GIVE":
            self._give_item(npc, target)

        elif action.startswith("MOVE"):
            self._move_npc(npc, target)

        elif action == "IDLE":
            npc.current_action = "idle"
            npc.state = "idle"
            npc.state_timer = random.uniform(3, 8)

        elif action == "APPROACH_PLAYER":
            # Move toward player to initiate conversation
            npc.target_x = self._player_ref.x if hasattr(self, '_player_ref') else npc.home_x
            npc.target_y = self._player_ref.y if hasattr(self, '_player_ref') else npc.home_y
            npc.current_action = "approaching_player"
            npc.approach_reason = reason
            npc.state = "walking"
            npc.state_timer = 15.0

        elif action == "FORM_PARTY":
            other = self._find_npc(target)
            if other and other.alive and not getattr(other, 'party_id', None):
                party_id = f"party_{npc.name}_{id(npc)}"
                npc.party_id = party_id
                npc.party_role = "leader"
                other.party_id = party_id
                other.party_role = "member"
                if npc.name not in getattr(other, 'friends', []):
                    if not hasattr(other, 'friends'):
                        other.friends = []
                    other.friends.append(npc.name)
                if other.name not in getattr(npc, 'friends', []):
                    npc.friends.append(other.name)
                npc.add_memory("social", f"Formed an adventuring party with {other.name}", 4)
                other.add_memory("social", f"Joined {npc.name}'s adventuring party", 4)
                self.event_log.append(f"{npc.name} and {other.name} formed an adventuring party!")
                # Record in life ledgers
                from game.systems.memory import ensure_life_ledger
                ensure_life_ledger(npc).record_milestone(
                    "formed_party", f"Formed a party with {other.name}", self.time_sys.day)
                ensure_life_ledger(npc).record_bond(
                    other.name, "party_member", self.time_sys.day, trust=30)
                ensure_life_ledger(other).record_milestone(
                    "joined_party", f"Joined {npc.name}'s party", self.time_sys.day)
                ensure_life_ledger(other).record_bond(
                    npc.name, "party_leader", self.time_sys.day, trust=30)
                npc.current_action = ""

        elif action == "SEEK_QUEST":
            # Move to nearest castle, tavern, or village for quests
            for s in self.world.structures:
                if s.kind in ("castle", "tavern", "village"):
                    npc.target_x, npc.target_y = float(s.x), float(s.y)
                    npc.current_action = "moving"
                    npc.current_goal = "find a quest or purpose"
                    npc.state = "walking"
                    npc.state_timer = 30.0
                    break

        elif action == "CAST_SPELL":
            # Simple spell casting
            if getattr(npc, 'is_spellcaster', False) and getattr(npc, 'known_spells', []):
                spell_name = target.split(" ON ")[0].strip() if " ON " in target else target
                from game.data.dnd import SPELLS
                spell = SPELLS.get(spell_name)
                if spell and spell["level"] <= 1:
                    # Damage spell on creature (spatial grid lookup)
                    if spell.get("damage", 0) > 0:
                        spell_range = spell.get("range", 5)
                        for c in self.creature_grid.get_nearby(npc.x, npc.y, spell_range):
                            if c.alive and npc.dist_to(c) < spell_range:
                                c.take_damage(spell["damage"])
                                npc.add_memory("combat", f"Cast {spell_name} on {c.kind}", 2)
                                break
                    # Heal spell on self or ally
                    elif spell.get("damage", 0) < 0:
                        heal_amount = abs(spell["damage"])
                        npc.heal(heal_amount)
                        npc.add_memory("action", f"Cast {spell_name} to heal", 1)
            npc.current_action = ""

        elif action == "REST_AT_TAVERN":
            loc = self.world.get_structure_at(npc.x, npc.y)
            if loc and loc.kind in ("tavern", "village"):
                npc.target_x, npc.target_y = float(loc.x), float(loc.y)
            else:
                # Fall back to home
                npc.target_x, npc.target_y = npc.home_x, npc.home_y
            if npc.target_x is not None:
                npc.current_action = "moving"
                npc.current_goal = "rest at tavern"
                npc.state = "walking"
                npc.state_timer = 20.0

        elif action == "VISIT_TEMPLE":
            for s in self.world.structures:
                if s.kind in ("temple", "shrine"):
                    npc.target_x, npc.target_y = float(s.x), float(s.y)
                    npc.current_action = "moving"
                    npc.current_goal = "visit temple"
                    npc.state = "walking"
                    npc.state_timer = 20.0
                    break

        elif action == "CRAFT":
            npc.current_action = ""
            npc.add_memory("action", f"Attempted to craft {target}", 1)

        # ================================================================
        # EXPANDED SKILL-BASED ACTIONS
        # ================================================================

        elif action == "MAKE_FIRE":
            # NPC builds or tends a fire
            if npc.npc_has_item("Wood") or npc.npc_has_item("Torch"):
                fire = self.fire_mgr.get_fire_near(npc.x, npc.y, 3.0)
                if not fire:
                    fire = self.fire_mgr.create_fire(int(npc.x), int(npc.y), "campfire")
                fuel = "Wood" if npc.npc_has_item("Wood") else "Torch"
                fire.add_fuel(fuel)
                npc.npc_remove_item(fuel)
                npc.add_memory("action", "Built a fire to stay warm", 1)
                from game.systems.skills import gain_skill_xp
                gain_skill_xp(npc, "tracking", 0.5)  # survival skill
            npc.current_action = ""

        elif action == "GATHER_FIREWOOD":
            # NPC gathers wood for fuel
            tree = self.world.find_nearest_tile(int(npc.x), int(npc.y),
                                                {FOREST, DENSE_FOREST}, 10)
            if tree:
                npc.target_x, npc.target_y = float(tree[0]), float(tree[1])
                npc.current_action = "chopping"
                npc.action_timer = NPC_CHOP_TIME
                npc.action_target = tree
                npc.state = "working"
                npc.current_goal = "gather firewood"
            else:
                npc.current_action = ""

        elif action == "FETCH_WATER":
            # NPC goes to nearest well/water source and fills up supplies
            water = self.world.find_water_near(int(npc.x), int(npc.y), 20)
            if water:
                npc.target_x, npc.target_y = float(water[0]), float(water[1])
                npc.current_action = "seeking_water"
                npc.state = "walking"
                npc.current_goal = "fetch water for the settlement"
            else:
                npc.current_action = ""

        elif action == "TRAIN_COMBAT":
            from game.systems.skills import gain_skill_xp, skill_check
            zone = self._find_zone_for_npc(npc, "training_ground")
            if zone:
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "training"
                npc.action_timer = NPC_TRAIN_TIME
                # Determine which combat skill to train
                combat_skill = "swordsmanship"
                if npc.npc_skills.get("archery", 0) > npc.npc_skills.get("swordsmanship", 0):
                    combat_skill = "archery"
                elif npc.npc_skills.get("unarmed", 0) > npc.npc_skills.get("swordsmanship", 0):
                    combat_skill = "unarmed"
                npc.action_target = combat_skill
            else:
                npc.current_action = ""

        elif action == "TRAIN_ARCHERY":
            from game.systems.skills import gain_skill_xp
            zone = self._find_zone_for_npc(npc, "archery_range")
            if zone and (npc.npc_has_item("Hunting Bow") or npc.npc_has_item("Arrows")):
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "training"
                npc.action_timer = NPC_TRAIN_TIME
                npc.action_target = "archery"
            else:
                npc.current_action = ""

        elif action in ("GUARD_WALL", "GUARD_GATE", "GUARD_TOWER", "PATROL", "SCOUT"):
            # Military duty actions — move to defensive position
            npc.state = "working"
            npc.current_action = "guarding"
            npc.action_timer = random.uniform(8.0, 15.0)

            # Find the nearest appropriate position
            home_struct = None
            for s in self.world.structures:
                if s.kind in ("village", "town", "city", "castle",
                              "orc_stronghold", "goblin_warren"):
                    if abs(npc.home_x - s.x) < s.radius + 5 and abs(npc.home_y - s.y) < s.radius + 5:
                        home_struct = s
                        break

            if home_struct:
                r = home_struct.radius
                if action == "GUARD_WALL":
                    # Move to a point on the settlement perimeter (wall)
                    angle = random.uniform(0, 2 * math.pi)
                    npc.target_x = home_struct.x + math.cos(angle) * (r - 1)
                    npc.target_y = home_struct.y + math.sin(angle) * (r - 1)
                elif action == "GUARD_GATE":
                    # Move to one of the 4 gate positions (N/S/E/W)
                    gate_dir = random.choice([(0, -1), (0, 1), (-1, 0), (1, 0)])
                    npc.target_x = home_struct.x + gate_dir[0] * r
                    npc.target_y = home_struct.y + gate_dir[1] * r
                elif action == "GUARD_TOWER":
                    # Move to nearest guard tower building
                    for bx, by, bw, bh in getattr(home_struct, 'buildings', []):
                        if bw <= 5 and bh <= 5:  # small buildings are likely towers
                            npc.target_x = float(bx + bw // 2)
                            npc.target_y = float(by + bh // 2)
                            break
                    else:
                        # Fallback: perimeter position
                        angle = random.uniform(0, 2 * math.pi)
                        npc.target_x = home_struct.x + math.cos(angle) * r
                        npc.target_y = home_struct.y + math.sin(angle) * r
                elif action in ("PATROL", "SCOUT"):
                    # Walk a section of the perimeter
                    angle = random.uniform(0, 2 * math.pi)
                    npc.target_x = home_struct.x + math.cos(angle) * (r + 3)
                    npc.target_y = home_struct.y + math.sin(angle) * (r + 3)

                # Gain military skills from duty
                from game.systems.skills import gain_skill_xp
                gain_skill_xp(npc, "swordsmanship", 0.1)
                if action in ("GUARD_TOWER", "SCOUT"):
                    gain_skill_xp(npc, "archery", 0.2)
                    gain_skill_xp(npc, "navigation", 0.1)
                if action == "PATROL":
                    gain_skill_xp(npc, "navigation", 0.15)
            else:
                npc.current_action = ""

        elif action == "PERFORM":
            from game.systems.skills import skill_check, gain_skill_xp
            npc.current_action = "performing"
            npc.action_timer = NPC_PERFORM_TIME
            npc.state = "working"
            npc.action_target = "performance"
            npc.target_x = None  # perform in place
            npc.target_y = None

        elif action == "HEAL_OTHER":
            from game.systems.skills import skill_check, gain_skill_xp
            other = self._find_npc(target)
            if other and other.alive and other.hp < other.max_hp:
                has_kit = npc.npc_has_item("Healer's Kit") or npc.npc_has_item("Herbalism Kit")
                if has_kit and npc.dist_to(other) < NPC_CONVERSATION_RANGE + 2:
                    success, total, natural = skill_check(npc, "medicine", 12)
                    if success:
                        heal_amt = 10 + npc.npc_skills.get("medicine", 0) * 3
                        other.heal(heal_amt)
                        npc.add_memory("action", f"Healed {other.name} for {heal_amt} HP", 2)
                        other.add_memory("social", f"{npc.name} healed me", 2)
                        gain_skill_xp(npc, "medicine", 1.5)
                    else:
                        npc.add_memory("action", f"Failed to heal {other.name}", 1)
                        gain_skill_xp(npc, "medicine", 0.5)
                else:
                    if other and other.alive:
                        npc.target_x, npc.target_y = other.x, other.y
                        npc.state = "walking"
                        npc.current_action = "moving"
                        npc.state_timer = 10.0
                    else:
                        npc.current_action = ""
            else:
                npc.current_action = ""

        elif action == "RESEARCH":
            from game.systems.skills import skill_check, gain_skill_xp
            zone = self._find_zone_for_npc(npc, "library")
            if zone:
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "researching"
                npc.action_timer = NPC_RESEARCH_TIME
                # Pick research topic based on class
                if npc.is_spellcaster:
                    npc.action_target = "arcana"
                elif npc.char_class in ("Cleric", "Paladin"):
                    npc.action_target = "religion"
                else:
                    npc.action_target = "history"
            else:
                npc.current_action = ""

        elif action == "PRAY":
            from game.systems.skills import skill_check, gain_skill_xp
            zone = self._find_zone_for_npc(npc, "chapel")
            if zone:
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "praying"
                npc.action_timer = 4.0
                npc.action_target = "religion"
            else:
                # Can pray anywhere
                npc.state = "working"
                npc.current_action = "praying"
                npc.action_timer = 4.0
                npc.action_target = "religion"
                npc.target_x = None
                npc.target_y = None

        elif action == "PICK_LOCK":
            from game.systems.skills import skill_check, gain_skill_xp
            if npc.npc_has_item("Thieves' Tools") or npc.npc_has_item("Lockpick"):
                # Find nearby locked door
                nx, ny = int(npc.x), int(npc.y)
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        tx, ty = nx + dx, ny + dy
                        if 0 <= tx < self.world.width and 0 <= ty < self.world.height:
                            if self.world.tiles[ty][tx] == LOCKED_DOOR:
                                success, total, natural = skill_check(npc, "lockpicking", 14)
                                if success:
                                    self.world.modify_tile(tx, ty, DOOR)
                                    npc.add_memory("action", "Picked a lock successfully", 2)
                                    gain_skill_xp(npc, "lockpicking", 2.0)
                                else:
                                    npc.add_memory("action", "Failed to pick a lock", 1)
                                    gain_skill_xp(npc, "lockpicking", 0.5)
                                    # Lockpick might break
                                    if natural == 1 and npc.npc_has_item("Lockpick"):
                                        npc.npc_remove_item("Lockpick")
                                npc.current_action = ""
                                return
                npc.current_action = ""
            else:
                npc.current_action = ""

        elif action == "PICKPOCKET":
            from game.systems.skills import skill_check_contested, gain_skill_xp
            other = self._find_npc(target)
            if other and other.alive and npc.dist_to(other) < NPC_CONVERSATION_RANGE:
                won = skill_check_contested(npc, "pickpocketing", other, "insight")
                if won and other.npc_inventory:
                    stolen = random.choice(other.npc_inventory)
                    other.npc_remove_item(stolen.name)
                    npc.npc_add_item(make_item(stolen.name))
                    npc.add_memory("action", f"Stole {stolen.name} from {other.name}", 3)
                    gain_skill_xp(npc, "pickpocketing", 2.0)
                    gain_skill_xp(npc, "stealth", 0.5)
                    # Record crime in both ledgers
                    from game.systems.memory import ensure_life_ledger
                    ensure_life_ledger(npc).record_crime(
                        "theft", f"Stole {stolen.name} from {other.name}",
                        self.time_sys.day, perpetrator=npc.name, victim=other.name,
                        witnessed=False)
                elif not won:
                    # Caught!
                    npc.add_memory("action", f"Caught trying to steal from {other.name}!", 3)
                    other.add_memory("social", f"{npc.name} tried to steal from me!", 4)
                    from game.systems.memory import ensure_life_ledger
                    ensure_life_ledger(other).record_crime(
                        "theft_attempt", f"{npc.name} tried to steal from me",
                        self.time_sys.day, perpetrator=npc.name, victim=other.name,
                        witnessed=True)
                    rel = self.social.get_rel(other.name, npc.name)
                    rel.trust = max(-100, rel.trust - 30)
                    rel.update_status()
                    gain_skill_xp(npc, "pickpocketing", 0.3)
                    self.event_log.append(f"{other.name} caught {npc.name} stealing!")
            npc.current_action = ""

        elif action == "SNEAK":
            from game.systems.skills import skill_check, gain_skill_xp
            success, total, natural = skill_check(npc, "stealth", 12)
            if success:
                npc.state = "walking"
                npc.speed = NPC_SPEED * 0.6  # slower but stealthy
                npc.state_timer = 15.0
                npc.add_memory("action", "Sneaking around undetected", 1)
                gain_skill_xp(npc, "stealth", 1.0)
            else:
                gain_skill_xp(npc, "stealth", 0.3)
            npc.current_action = ""

        elif action == "SET_TRAP":
            from game.systems.skills import skill_check, gain_skill_xp
            has_materials = (npc.npc_has_item("Trap") or
                           (npc.npc_has_item("Rope") and npc.npc_count_item("Iron Ingot") >= 1))
            if has_materials:
                success, total, natural = skill_check(npc, "trap_making", 11)
                if success:
                    if npc.npc_has_item("Trap"):
                        npc.npc_remove_item("Trap")
                    else:
                        npc.npc_remove_item("Rope")
                        npc.npc_remove_item("Iron Ingot")
                    npc.add_memory("action", "Set a trap successfully", 2)
                    gain_skill_xp(npc, "trap_making", 1.5)
                else:
                    npc.add_memory("action", "Failed to set trap properly", 1)
                    gain_skill_xp(npc, "trap_making", 0.5)
            npc.current_action = ""

        elif action == "TRACK":
            from game.systems.skills import skill_check, gain_skill_xp
            success, total, natural = skill_check(npc, "tracking", 12)
            if success:
                # Find nearest creature using spatial grid
                found = False
                for c in self.creature_grid.get_nearby(npc.x, npc.y, 30):
                    if c.alive and npc.dist_to(c) < 30:
                        npc.add_memory("action", f"Tracked a {c.kind} at ({int(c.x)},{int(c.y)})", 2)
                        gain_skill_xp(npc, "tracking", 1.5)
                        found = True
                        break
                if not found:
                    npc.add_memory("action", "Found no creature tracks nearby", 1)
                    gain_skill_xp(npc, "tracking", 0.5)
            else:
                gain_skill_xp(npc, "tracking", 0.3)
            npc.current_action = ""

        elif action == "NAVIGATE":
            from game.systems.skills import skill_check, gain_skill_xp
            success, total, natural = skill_check(npc, "navigation", 10)
            if success:
                npc.speed = NPC_SPEED * 1.3  # temporary speed boost from good navigation
                npc.state_timer = 20.0
                gain_skill_xp(npc, "navigation", 1.0)
            else:
                gain_skill_xp(npc, "navigation", 0.3)
            npc.current_action = ""

        elif action == "CLIMB":
            from game.systems.skills import skill_check, gain_skill_xp
            success, total, natural = skill_check(npc, "climbing", 13)
            if success:
                npc.add_memory("action", "Scaled a difficult surface", 1)
                gain_skill_xp(npc, "climbing", 1.5)
            else:
                # Fall damage on failure
                npc.take_damage(random.randint(3, 8))
                npc.add_memory("action", "Fell while trying to climb!", 2)
                gain_skill_xp(npc, "climbing", 0.5)
            npc.current_action = ""

        elif action == "SWIM":
            from game.systems.skills import skill_check, gain_skill_xp
            success, total, natural = skill_check(npc, "swimming", 11)
            if success:
                gain_skill_xp(npc, "swimming", 1.0)
            else:
                npc.take_damage(random.randint(2, 5))
                npc.add_memory("action", "Struggled in the water", 1)
                gain_skill_xp(npc, "swimming", 0.5)
            npc.current_action = ""

        elif action == "TRAIN_ANIMAL":
            from game.systems.skills import skill_check, gain_skill_xp
            zone = self._find_zone_for_npc(npc, "stable")
            if zone:
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "training_animal"
                npc.action_timer = NPC_TRAIN_TIME
                npc.action_target = "animal_training"
            else:
                npc.current_action = ""

        elif action == "PERFORM_RITUAL":
            from game.systems.skills import skill_check, gain_skill_xp
            zone = self._find_zone_for_npc(npc, "ritual_circle")
            if zone and getattr(npc, 'is_spellcaster', False):
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "ritual"
                npc.action_timer = NPC_RITUAL_TIME
                npc.action_target = "ritual_magic"
            else:
                npc.current_action = ""

        elif action == "SET_WARD":
            from game.systems.skills import skill_check, gain_skill_xp
            if npc.npc_has_item("Ward Stones"):
                success, total, natural = skill_check(npc, "warding", 14)
                if success:
                    npc.npc_remove_item("Ward Stones")
                    npc.add_memory("action", "Set a protective ward", 3)
                    gain_skill_xp(npc, "warding", 2.0)
                else:
                    npc.add_memory("action", "Ward spell fizzled", 1)
                    gain_skill_xp(npc, "warding", 0.5)
            npc.current_action = ""

        elif action == "DIVINE":
            from game.systems.skills import skill_check, gain_skill_xp
            if npc.npc_has_item("Divination Crystal"):
                success, total, natural = skill_check(npc, "divination", 13)
                if success:
                    # Learn about a random world event or creature location
                    visions = [
                        "a storm gathering in the north",
                        "danger approaching from the east",
                        "a treasure hidden in nearby ruins",
                        "a friend in need of help",
                        "prosperity for the village",
                    ]
                    vision = random.choice(visions)
                    npc.add_memory("action", f"Divination vision: {vision}", 3)
                    npc.known_info.append(f"A vision showed {vision}")
                    gain_skill_xp(npc, "divination", 2.0)
                else:
                    npc.add_memory("action", "Divination was unclear", 1)
                    gain_skill_xp(npc, "divination", 0.5)
            npc.current_action = ""

        elif action == "ENCHANT_ITEM":
            from game.systems.skills import skill_check, gain_skill_xp
            zone = self._find_zone_for_npc(npc, "enchanting_room")
            if zone and npc.npc_has_item("Enchanter's Focus"):
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "enchanting"
                npc.action_timer = NPC_ENCHANT_TIME
                npc.action_target = "enchanting"
            else:
                npc.current_action = ""

        elif action == "MAKE_MAP":
            from game.systems.skills import skill_check, gain_skill_xp
            if npc.npc_has_item("Cartographer's Kit") and npc.npc_has_item("Ink"):
                success, total, natural = skill_check(npc, "cartography", 12)
                if success:
                    npc.npc_remove_item("Ink")
                    new_map = make_item("Regional Map")
                    npc.npc_add_item(new_map)
                    npc.add_memory("action", "Drew a regional map", 2)
                    gain_skill_xp(npc, "cartography", 2.0)
                else:
                    npc.add_memory("action", "Map drawing was inaccurate", 1)
                    gain_skill_xp(npc, "cartography", 0.5)
            npc.current_action = ""

        elif action == "CRAFT_POTTERY":
            from game.systems.skills import gain_skill_xp
            zone = self._find_zone_for_npc(npc, "pottery_studio")
            if zone and npc.npc_count_item("Clay") >= 2:
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "crafting_pottery"
                npc.action_timer = NPC_CRAFT_TIME
                npc.action_target = "pottery"
            else:
                npc.current_action = ""

        elif action == "CRAFT_GLASS":
            from game.systems.skills import gain_skill_xp
            zone = self._find_zone_for_npc(npc, "glassworks")
            if zone and npc.npc_has_item("Glassblower's Tools") and npc.npc_count_item("Sand") >= 2:
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "crafting_glass"
                npc.action_timer = NPC_CRAFT_TIME
                npc.action_target = "glassblowing"
            else:
                npc.current_action = ""

        elif action == "TAN_HIDE":
            from game.systems.skills import gain_skill_xp
            zone = self._find_zone_for_npc(npc, "tannery")
            if zone and npc.npc_has_item("Wolf Pelt"):
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "tanning"
                npc.action_timer = NPC_CRAFT_TIME
                npc.action_target = "tanning"
            else:
                npc.current_action = ""

        elif action == "DYE_CLOTH":
            from game.systems.skills import gain_skill_xp
            zone = self._find_zone_for_npc(npc, "dye_house")
            if zone and npc.npc_has_item("Dye Kit") and npc.npc_has_item("Linen"):
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "dyeing"
                npc.action_timer = NPC_CRAFT_TIME
                npc.action_target = "dyeing"
            else:
                npc.current_action = ""

        elif action in ("JOKE_WITH", "COMFORT", "ARGUE_WITH", "INTIMIDATE",
                        "SHARE_MEAL", "FLIRT_WITH", "CHALLENGE", "SPAR_WITH"):
            # Social interactions handled by the social system
            other = self._find_npc(target)
            if other and other.alive and npc.dist_to(other) < NPC_CONVERSATION_RANGE + 2:
                action_to_social = {
                    "JOKE_WITH": "joke", "COMFORT": "comfort", "ARGUE_WITH": "argue",
                    "INTIMIDATE": "intimidate", "SHARE_MEAL": "share_meal",
                    "FLIRT_WITH": "flirt", "CHALLENGE": "challenge", "SPAR_WITH": "spar",
                }
                social_type = action_to_social.get(action, "friendly_chat")
                from game.systems.social import SOCIAL_INTERACTIONS
                idata = SOCIAL_INTERACTIONS.get(social_type, SOCIAL_INTERACTIONS["friendly_chat"])
                # Execute the social interaction
                rel_ab = self.social.get_rel(npc.name, other.name)
                rel_ba = self.social.get_rel(other.name, npc.name)
                trust_min, trust_max = idata["trust_change"]
                cha_mod = (npc.attributes.get("charisma", 5) - 5) * 0.5
                trust_change = random.uniform(trust_min, trust_max) + cha_mod
                mood_min, mood_max = idata["mood_change"]
                mood_change = random.uniform(mood_min, mood_max)

                rel_ab.trust = max(-100, min(100, rel_ab.trust + trust_change))
                rel_ba.trust = max(-100, min(100, rel_ba.trust + trust_change * 0.7))
                rel_ab.interaction_count += 1
                rel_ab.update_status()
                rel_ba.update_status()

                npc.needs["social"] = min(100, npc.needs.get("social", 50) + abs(mood_change) * 0.5)
                other.needs["social"] = min(100, other.needs.get("social", 50) + abs(mood_change) * 0.3)

                desc = idata["description"].format(a=npc.name, b=other.name)
                npc.add_memory("social", desc, 2)
                other.add_memory("social", desc, 2)
                self.event_log.append(desc)
                npc.current_action = ""
            else:
                # Not nearby - move toward them
                if other and other.alive:
                    npc.target_x, npc.target_y = other.x, other.y
                    npc.state = "walking"
                    npc.current_action = "moving"
                    npc.state_timer = 10.0
                else:
                    npc.current_action = ""

        else:
            npc.current_action = ""
            npc.state_timer = random.uniform(2, 5)

    def _move_to_forage(self, npc: NPC):
        """Move to forest to forage for food/water."""
        forest = self.world.find_nearest_tile(int(npc.x), int(npc.y), {FOREST, DENSE_FOREST}, 12)
        if forest:
            npc.target_x, npc.target_y = float(forest[0]), float(forest[1])
            npc.current_action = "foraging"
            npc.action_timer = NPC_FORAGE_TIME
            npc.state = "walking"
        else:
            npc.current_action = ""

    def _move_npc(self, npc: NPC, target: str):
        """Move to the NEAREST matching location, NPC, or direction."""
        # Check travel restrictions based on social class
        from game.systems.social_class import can_travel
        gov_style = "feudalism"
        if hasattr(self, 'governance'):
            for k in self.governance.kingdoms.values():
                gov_style = getattr(k, 'governing_style', 'feudalism')
                break
        if not can_travel(npc, gov_style):
            # Restricted — can only move near home
            if "home" not in target.lower():
                home_dist = npc.dist_to_pos(npc.home_x, npc.home_y)
                if home_dist > 20:
                    # Already far — go home instead
                    npc.target_x, npc.target_y = npc.home_x, npc.home_y
                    npc.state = "walking"
                    npc.current_action = "moving"
                    npc.state_timer = 15.0
                    return

        target_lower = target.lower().strip()

        # Find nearest matching structure
        best = None
        best_dist = float('inf')
        for s in self.world.structures:
            matches = (target_lower in s.name.lower() or target_lower in s.kind or
                      (target_lower in ("village", "town", "settlement", "nearby") and s.kind in ("village", "town", "city", "hamlet")) or
                      (target_lower in ("ruins", "dungeon") and s.kind in ("ruins", "dungeon")) or
                      (target_lower in ("tavern", "inn") and s.kind == "tavern") or
                      (target_lower in ("temple", "shrine") and s.kind in ("temple", "shrine")) or
                      (target_lower in ("castle", "fortress") and s.kind == "castle") or
                      (target_lower in ("forest", "wilderness") and s.kind in ("ruins",)))  # forests aren't structures
            if matches:
                d = npc.dist_to_pos(s.x, s.y)
                if d < best_dist:
                    best_dist = d
                    best = s

        if best:
            dest_x, dest_y = float(best.x), float(best.y)

            # For long journeys, plan supplies first
            if best_dist > 30 and hasattr(self, 'world_map'):
                from game.systems.world_map import plan_journey, prepare_for_journey
                plan = plan_journey(npc, dest_x, dest_y, self.world_map)
                if plan["supplies_needed"]:
                    # Try to prepare
                    ready = prepare_for_journey(npc, plan)
                    if not ready and not plan["should_go"]:
                        # Can't afford supplies for this journey — stay put
                        npc.current_action = ""
                        npc.add_memory("action",
                            f"Wanted to travel to {best.name} but lacked supplies", 1)
                        return

            npc.target_x, npc.target_y = dest_x, dest_y
            npc.state = "walking"
            npc.current_action = "moving"
            npc.state_timer = max(10, best_dist * 0.3)
            return

        # Try to find a named NPC nearby
        nearby_npcs = self.npc_grid.get_nearby(npc.x, npc.y, 30) if hasattr(self, 'npc_grid') else []
        for other in nearby_npcs:
            if other.name.lower() == target_lower and other.alive:
                npc.target_x, npc.target_y = other.x, other.y
                npc.state = "walking"
                npc.current_action = "moving"
                npc.state_timer = 20.0
                return

        # Direction or "home"
        if "home" in target_lower:
            npc.target_x, npc.target_y = npc.home_x, npc.home_y
        elif "north" in target_lower:
            npc.target_y = npc.y - random.uniform(5, 12)
        elif "south" in target_lower:
            npc.target_y = npc.y + random.uniform(5, 12)
        elif "east" in target_lower:
            npc.target_x = npc.x + random.uniform(5, 12)
        elif "west" in target_lower:
            npc.target_x = npc.x - random.uniform(5, 12)
        else:
            # Random wander — stay near home, don't wander into wilderness
            angle = random.uniform(0, 2 * math.pi)
            d = random.uniform(3, 8)
            # Bias toward home to prevent drift
            home_dx = npc.home_x - npc.x
            home_dy = npc.home_y - npc.y
            home_dist = math.sqrt(home_dx * home_dx + home_dy * home_dy)
            if home_dist > 15:
                # Too far from home — head back
                npc.target_x = npc.home_x + random.uniform(-3, 3)
                npc.target_y = npc.home_y + random.uniform(-3, 3)
            else:
                npc.target_x = npc.home_x + math.cos(angle) * d
                npc.target_y = npc.home_y + math.sin(angle) * d

        npc.state = "walking"
        npc.current_action = "moving"
        npc.state_timer = 20.0


    def _start_fight(self, npc: NPC, target_name: str):
        # Find target (NPC or creature) — use spatial grid for creatures
        target = self._find_npc(target_name)
        if not target:
            for c in self.creature_grid.get_nearby(npc.x, npc.y, 10):
                if c.alive and c.kind.lower() == target_name.lower() and npc.dist_to(c) < 10:
                    target = c
                    break
        if not target or not target.alive:
            npc.current_action = ""
            return

        npc.current_action = "fighting"
        npc.combat_target = target
        npc.state = "fighting"
        npc.add_memory("combat", f"Started fighting {target_name}", 3)
        self.event_log.append(f"{npc.name} engages in combat with {target_name}!")

    def _give_item(self, npc: NPC, target_str: str):
        """Give item: 'item_name TO recipient'"""
        parts = target_str.upper().split(" TO ")
        if len(parts) != 2:
            npc.current_action = ""
            return
        item_name = parts[0].strip()
        recipient_name = parts[1].strip()

        # Find matching item (case-insensitive)
        found_item = None
        for item in npc.npc_inventory:
            if item.name.upper() == item_name:
                found_item = item
                break
        if not found_item:
            npc.current_action = ""
            return

        recipient = self._find_npc(recipient_name)
        if recipient and recipient.alive:
            npc.npc_remove_item(found_item.name)
            recipient.npc_add_item(make_item(found_item.name))
            npc.add_memory("give", f"Gave {found_item.name} to {recipient.name}", 2)
            recipient.add_memory("receive", f"Received {found_item.name} from {npc.name}", 2)
            recipient.npc_relationships[npc.name] = recipient.npc_relationships.get(npc.name, 0) + 10
            self.event_log.append(f"{npc.name} gave {found_item.name} to {recipient.name}")
        npc.current_action = ""

    def _find_npc(self, name: str) -> Optional[NPC]:
        name_lower = name.lower().strip()
        for npc in self.world_mgr.npcs:
            if npc.name.lower() == name_lower:
                return npc
        return None

    def _find_zone_for_npc(self, npc: NPC, zone_type: str):
        """Find nearest zone of given type for an NPC."""
        if hasattr(self, 'zones') and self.zones:
            return self.zones.find_zone(zone_type, npc.x, npc.y, 50)
        return None

    # ---- ACTION PROGRESS ----


    def _update_action_progress(self, npcs: List[NPC], dt: float, player: Player):
        active_set = self._active_npc_set
        for npc in npcs:
            if not npc.alive:
                continue
            # Skip dormant NPCs
            if active_set is not None and npc.name not in active_set:
                continue
            npc.npc_attack_timer = max(0, npc.npc_attack_timer - dt)

            # Seeking water: if next to water, drink directly
            if npc.current_action == "seeking_water":
                wx = self.world.find_water_near(int(npc.x), int(npc.y), 2)
                if wx:
                    npc.needs["thirst"] = min(100, npc.needs["thirst"] + 40)
                    npc.add_memory("survival", "Drank from a water source", 1)
                    npc.current_action = ""
                    npc.state = "idle"

            # Approaching player
            if npc.current_action == "approaching_player":
                if hasattr(self, '_player_ref'):
                    dist = npc.dist_to(self._player_ref)
                    if dist < NPC_CONVERSATION_RANGE:
                        npc.wants_to_talk = True
                        npc.talk_reason = getattr(npc, 'approach_reason', 'wants to speak with you')
                        npc.current_action = ""
                        npc.state = "idle"
                    elif dist < 12:
                        # Keep moving toward player
                        npc.target_x = self._player_ref.x
                        npc.target_y = self._player_ref.y

            # Party members follow their leader — use spatial grid
            if getattr(npc, 'party_id', None) and getattr(npc, 'party_role', '') == "member":
                for other in self.npc_grid.get_nearby(npc.x, npc.y, 20):
                    if (getattr(other, 'party_id', None) == npc.party_id and
                        getattr(other, 'party_role', '') == "leader" and other.alive):
                        if npc.dist_to(other) > 3.0 and npc.current_action not in ("fighting", "sleeping"):
                            npc.target_x = other.x + random.uniform(-1, 1)
                            npc.target_y = other.y + random.uniform(-1, 1)
                            npc.state = "walking"
                        break

            if npc.action_timer > 0 and npc.current_action in (
                "chopping", "mining", "building", "farming", "fishing", "foraging", "sleeping",
                "training", "performing", "researching", "praying", "ritual",
                "enchanting", "crafting_pottery", "crafting_glass", "tanning", "dyeing",
                "training_animal", "smithing", "hunting", "guarding",
            ):
                # Only tick down when near the target
                at_target = True
                if npc.target_x is not None:
                    dist = npc.dist_to_pos(npc.target_x, npc.target_y)
                    if dist > 2.0:
                        at_target = False

                if at_target:
                    npc.action_timer -= dt
                    npc.action_progress = max(0, 1.0 - npc.action_timer / 8.0)

                if npc.action_timer <= 0:
                    self._complete_action(npc)

    def _update_player_tasks(self, npcs: List[NPC], dt: float):
        """Progress NPCs working on player-assigned tasks."""
        for npc in npcs:
            if not npc.alive:
                continue
            task = getattr(npc, 'player_task', None)
            if not task:
                continue
            if task.get("progress", 0) >= task.get("target_count", 1):
                # Task already done — NPC approaches player to report
                if not npc.wants_to_talk and npc.current_action != "approaching_player":
                    npc.wants_to_talk = True
                    npc.talk_reason = f"I've finished the task you gave me!"
                continue

            # Advance timer
            npc.player_task_timer = getattr(npc, 'player_task_timer', 0) + dt
            kind = task.get("kind", "")

            # Each task type progresses at different rates
            if kind == "kill":
                # NPC hunts nearby creatures every ~15 seconds of work
                if npc.player_task_timer > 15.0:
                    npc.player_task_timer = 0.0
                    # Check for nearby creatures to fight
                    for c in self.creature_grid.get_nearby(npc.x, npc.y, 15):
                        if c.alive:
                            npc.combat_target = c
                            npc.current_action = "fighting"
                            npc.state = "fighting"
                            task["progress"] = task.get("progress", 0) + 1
                            npc.add_memory("combat",
                                f"Killed a {c.kind} on the player's orders", 2)
                            c.hp = 0
                            c.alive = False
                            self.event_log.append(
                                f"{npc.name} killed a {c.kind} (player task {task['progress']}/{task['target_count']})")
                            break

            elif kind == "fetch":
                # NPC gathers items every ~10 seconds of work
                if npc.player_task_timer > 10.0:
                    npc.player_task_timer = 0.0
                    task["progress"] = task.get("progress", 0) + 1
                    # Generate an item
                    gather = random.choice(["Herbs", "Wood", "Stone", "Apple", "Bread", "Mushrooms"])
                    npc.npc_add_item(make_item(gather))
                    npc.add_memory("work",
                        f"Gathered {gather} for the player ({task['progress']}/{task['target_count']})", 1)

            elif kind == "scout":
                # Scouting takes ~20 seconds total
                if npc.player_task_timer > 20.0:
                    npc.player_task_timer = 0.0
                    task["progress"] = 1
                    # Learn something new from scouting
                    structure = self.world.get_structure_at(npc.x, npc.y)
                    loc = structure.name if structure else "the wilderness"
                    info = random.choice([
                        f"Scouted area near {loc}: seems safe",
                        f"Noticed creature tracks near {loc}",
                        f"Found a possible camp site near {loc}",
                        f"Area near {loc} has good foraging",
                        f"Spotted movement in the trees near {loc}",
                    ])
                    npc.known_info.append(info)
                    npc.add_memory("work", f"Completed scouting: {info}", 2)

            elif kind == "guard":
                # Guarding takes ~30 seconds, auto-complete
                if npc.player_task_timer > 30.0:
                    task["progress"] = 1
                    npc.add_memory("work", "Completed guard duty for the player", 2)
                else:
                    # While guarding, fight any nearby creatures
                    for c in self.creature_grid.get_nearby(npc.x, npc.y, 8):
                        if c.alive:
                            npc.combat_target = c
                            npc.current_action = "fighting"
                            npc.state = "fighting"
                            break

            elif kind == "deliver":
                # Delivery takes ~20 seconds
                if npc.player_task_timer > 20.0:
                    task["progress"] = 1
                    npc.add_memory("work", "Completed delivery for the player", 2)

    def _complete_action(self, npc: NPC):
        """Complete a timed action and gain skill XP."""
        from game.systems.skills import gain_skill_xp
        action = npc.current_action

        # Gain skill XP from completing work
        skill_map = {
            "chopping": "woodcraft", "mining": "mining", "building": "masonry",
            "farming": "farming", "fishing": "fishing", "foraging": "herbalism",
            "smithing": "smithing", "hunting": "tracking", "guarding": "swordsmanship",
        }
        if action in skill_map:
            gain_skill_xp(npc, skill_map[action], 1.0)

        if action == "chopping":
            from game.systems.skills import skill_check
            target = npc.action_target
            if target:
                tx, ty = target
                self.world.modify_tile(tx, ty, TREE_STUMP)
                success, total, natural = skill_check(npc, "woodcraft", 8)
                base_count = random.randint(1, 3)
                bonus = 1 if success else 0
                wood = make_item("Wood")
                wood.count = base_count + bonus
                npc.npc_add_item(wood)
                npc.add_memory("work", f"Chopped a tree, got {wood.count} wood", 1)
                npc.daily_builds += 1
                gain_skill_xp(npc, "woodcraft", 1.0)

        elif action == "mining":
            from game.systems.skills import skill_check
            target = npc.action_target
            if target:
                success, total, natural = skill_check(npc, "mining", 10)
                ore_chance = 0.4 + (0.1 if success else 0)
                if random.random() < ore_chance:
                    ore = make_item("Iron Ore")
                    npc.npc_add_item(ore)
                    npc.add_memory("work", "Mined iron ore", 1)
                else:
                    stone = make_item("Stone")
                    stone.count = random.randint(1, 2) + (1 if success else 0)
                    npc.npc_add_item(stone)
                    npc.add_memory("work", f"Mined {stone.count} stone", 1)
                gain_skill_xp(npc, "mining", 1.0)

        elif action == "building":
            if npc.action_target and npc.daily_builds < 10:
                what, tile_type = npc.action_target
                bx, by = int(npc.x), int(npc.y)
                # Find adjacent empty spot
                for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                    nx, ny = bx + dx, by + dy
                    if self.world.is_walkable(nx, ny) and self.world.tiles[ny][nx] == GRASS:
                        if what == "wall" and npc.npc_count_item("Stone") >= 2:
                            self.world.modify_tile(nx, ny, tile_type)
                            npc.npc_remove_item("Stone", 2)
                            npc.add_memory("build", f"Built a stone wall", 2)
                            npc.daily_builds += 1
                        elif what == "floor" and npc.npc_count_item("Wood") >= 2:
                            self.world.modify_tile(nx, ny, tile_type)
                            npc.npc_remove_item("Wood", 2)
                            npc.add_memory("build", f"Built a wooden floor", 2)
                            npc.daily_builds += 1
                        break

        elif action == "farming":
            sub = npc.action_target
            if sub == "plant":
                tx, ty = int(npc.x), int(npc.y)
                if self.world.tiles[ty][tx] == GRASS and npc.npc_has_item("Seeds"):
                    self.world.modify_tile(tx, ty, TILLED_SOIL)
                    npc.npc_remove_item("Seeds")
                    npc.add_memory("work", "Planted seeds", 1)
            elif sub == "harvest":
                tx, ty = int(npc.x), int(npc.y)
                if self.world.tiles[ty][tx] in (FARMLAND, TILLED_SOIL):
                    food = make_item(random.choice(["Bread", "Apple"]))
                    food.count = random.randint(1, 3)
                    npc.npc_add_item(food)
                    npc.add_memory("work", f"Harvested {food.count} {food.name}", 1)
                    if self.world.tiles[ty][tx] == TILLED_SOIL:
                        self.world.modify_tile(tx, ty, FARMLAND)

        elif action == "fishing":
            from game.systems.skills import skill_check
            if npc.npc_has_item("Fishing Rod"):
                success, total, natural = skill_check(npc, "fishing", 10)
                catch_chance = 0.7 + (0.15 if success else 0)
                if random.random() < catch_chance:
                    fish = make_item("Fish")
                    fish.count = 1 + (1 if success and natural >= 18 else 0)
                    npc.npc_add_item(fish)
                    npc.add_memory("work", f"Caught {fish.count} fish", 1)
                gain_skill_xp(npc, "fishing", 1.0)

        elif action == "foraging":
            # Forage in forest for food/herbs/water
            tile = self.world.tiles[int(npc.y)][int(npc.x)] if \
                0 <= int(npc.x) < self.world.width and 0 <= int(npc.y) < self.world.height else GRASS
            if tile in (FOREST, DENSE_FOREST):
                roll = random.random()
                if roll < 0.4:
                    food = make_item(random.choice(["Apple", "Herbs"]))
                    npc.npc_add_item(food)
                    npc.add_memory("forage", f"Found {food.name} in the forest", 1)
                elif roll < 0.6:
                    water = make_item("Water Flask")
                    npc.npc_add_item(water)
                    npc.add_memory("forage", "Found fresh water", 1)

        elif action == "sleeping":
            pass  # Rest recovery handled in _decay_needs

        elif action == "smithing":
            from game.systems.skills import skill_check
            success, total, natural = skill_check(npc, "smithing", 11)
            gain_skill_xp(npc, "smithing", 2.0 if success else 0.8)
            if success:
                product = random.choice(["Iron Sword", "Iron Armor", "Steel Sword"])
                item = make_item(product)
                if item:
                    npc.npc_add_item(item)
                npc.add_memory("work", f"Forged a {product}", 2)
                # Deposit to settlement stores
                if hasattr(self, 'world_effects'):
                    _loc = self.world.get_structure_at(npc.x, npc.y)
                    if _loc:
                        _st = self.world_effects.get_stores_ref(_loc.name)
                        _st["weapons"] = _st.get("weapons", 0) + 1
                        _st["tools"] = _st.get("tools", 0) + 0.5
            else:
                npc.add_memory("work", "Failed to forge a quality piece", 1)

        elif action == "guarding":
            gain_skill_xp(npc, "swordsmanship", 0.3)
            gain_skill_xp(npc, "navigation", 0.2)
            npc.add_memory("duty", "Completed a patrol shift", 1)

        elif action == "hunting":
            gain_skill_xp(npc, "tracking", 1.0)
            gain_skill_xp(npc, "archery", 0.5)
            npc.add_memory("work", "Returned from a hunt", 1)

        # ---- NEW SKILL-BASED ACTION COMPLETIONS ----

        elif action == "training":
            from game.systems.skills import skill_check
            combat_skill = npc.action_target or "swordsmanship"
            dc = 8 + npc.npc_skills.get(combat_skill, 0)
            success, total, natural = skill_check(npc, combat_skill, dc)
            gain_skill_xp(npc, combat_skill, 2.5 if success else 1.0)
            npc.add_memory("training", f"Trained {combat_skill} {'successfully' if success else 'with difficulty'}", 1)

        elif action == "performing":
            from game.systems.skills import skill_check
            success, total, natural = skill_check(npc, "performance", 10)
            gain_skill_xp(npc, "performance", 2.5 if success else 1.0)
            if success:
                # Earn gold from audience — collect tips from nearby NPCs
                base_earnings = random.randint(2, 5) + npc.npc_skills.get("performance", 0)
                actual_earnings = 0
                # Try to collect from nearby NPCs (audience)
                nearby = self.npc_grid.get_nearby(npc.x, npc.y, 8) if hasattr(self, 'npc_grid') else []
                for audience_npc in nearby:
                    if audience_npc is npc or not audience_npc.alive:
                        continue
                    tip = min(1, getattr(audience_npc, 'npc_gold', 0))
                    if tip > 0 and actual_earnings < base_earnings:
                        audience_npc.npc_gold -= tip
                        actual_earnings += tip
                # If few audience NPCs, supplement from settlement stores
                if actual_earnings < base_earnings and hasattr(self, 'world_effects'):
                    _loc = self.world.get_structure_at(npc.x, npc.y)
                    if _loc:
                        _st = self.world_effects.get_stores_ref(_loc.name)
                        supplement = min(base_earnings - actual_earnings,
                                        _st.get("gold", 0))
                        if supplement > 0:
                            _st["gold"] -= supplement
                            actual_earnings += supplement
                if actual_earnings > 0:
                    npc.npc_gold += actual_earnings
                    npc.add_memory("work", f"Performed and earned {actual_earnings} gold", 2)
                else:
                    npc.add_memory("work", "Performed but the crowd was too poor to tip", 1)
                npc.needs["social"] = min(100, npc.needs.get("social", 50) + 15)
                gain_skill_xp(npc, "persuasion", 0.5)
            else:
                npc.add_memory("work", "Performance fell flat", 1)

        elif action == "researching":
            from game.systems.skills import skill_check
            research_skill = npc.action_target or "arcana"
            success, total, natural = skill_check(npc, research_skill, 12)
            gain_skill_xp(npc, research_skill, 2.5 if success else 1.0)
            gain_skill_xp(npc, "literacy", 0.5)
            if success:
                topics = {
                    "arcana": ["a new spell formula", "ancient magical theory", "planar mechanics"],
                    "history": ["a forgotten kingdom", "an ancient battle", "a lost trade route"],
                    "religion": ["a divine prophecy", "a sacred ritual", "the nature of the gods"],
                }
                discovery = random.choice(topics.get(research_skill, ["something interesting"]))
                npc.add_memory("research", f"Researched and discovered {discovery}", 3)
                npc.known_info.append(f"Discovered {discovery} through research")

        elif action == "praying":
            from game.systems.skills import skill_check
            success, total, natural = skill_check(npc, "religion", 8)
            gain_skill_xp(npc, "religion", 2.0 if success else 0.5)
            if success:
                npc.needs["social"] = min(100, npc.needs.get("social", 50) + 10)
                deity = getattr(npc, 'deity', 'the gods')
                npc.add_memory("spiritual", f"Felt the presence of {deity} during prayer", 2)
                # Small chance of healing
                if random.random() < 0.3 and npc.hp < npc.max_hp:
                    npc.heal(5 + npc.npc_skills.get("religion", 0))

        elif action == "ritual":
            from game.systems.skills import skill_check
            success, total, natural = skill_check(npc, "ritual_magic", 15)
            gain_skill_xp(npc, "ritual_magic", 2.0 if success else 0.5)
            if success:
                # Powerful magical effect
                effects = ["warded the area against evil", "glimpsed the future",
                           "strengthened the local ley lines", "communed with nature spirits"]
                effect = random.choice(effects)
                npc.add_memory("magic", f"Completed a ritual: {effect}", 4)
                self.event_log.append(f"{npc.name} completed a magical ritual near ({int(npc.x)},{int(npc.y)})")
                gain_skill_xp(npc, "spellcraft", 1.0)
            else:
                npc.add_memory("magic", "Ritual failed - the magic dissipated", 2)

        elif action == "enchanting":
            from game.systems.skills import skill_check
            success, total, natural = skill_check(npc, "enchanting", 16)
            gain_skill_xp(npc, "enchanting", 2.0 if success else 0.5)
            if success:
                # Find a weapon or armor in inventory to enchant
                for item in npc.npc_inventory:
                    if item.kind == "weapon" and "Enchanted" not in item.name:
                        item.damage += 5
                        item.name = f"Enchanted {item.name}"
                        item.value *= 2
                        npc.add_memory("craft", f"Enchanted {item.name}", 4)
                        break
                else:
                    npc.add_memory("craft", "Practiced enchanting techniques", 1)
            else:
                npc.add_memory("craft", "Enchantment attempt fizzled", 1)

        elif action == "crafting_pottery":
            from game.systems.skills import skill_check
            if npc.npc_count_item("Clay") >= 2:
                success, total, natural = skill_check(npc, "pottery", 10)
                npc.npc_remove_item("Clay", 2)
                gain_skill_xp(npc, "pottery", 1.5 if success else 0.5)
                if success:
                    product = random.choice(["Pottery Jar", "Vase", "Pot"])
                    npc.npc_add_item(make_item(product))
                    npc.add_memory("craft", f"Made a {product}", 2)
                else:
                    npc.add_memory("craft", "Pottery cracked in the kiln", 1)

        elif action == "crafting_glass":
            from game.systems.skills import skill_check
            if npc.npc_count_item("Sand") >= 2:
                success, total, natural = skill_check(npc, "glassblowing", 12)
                npc.npc_remove_item("Sand", 2)
                gain_skill_xp(npc, "glassblowing", 1.5 if success else 0.5)
                if success:
                    product = random.choice(["Glass Pane", "Bottle"])
                    npc.npc_add_item(make_item(product))
                    npc.add_memory("craft", f"Made {product}", 2)
                else:
                    npc.add_memory("craft", "Glass shattered during blowing", 1)

        elif action == "tanning":
            from game.systems.skills import skill_check
            if npc.npc_has_item("Wolf Pelt"):
                success, total, natural = skill_check(npc, "tanning", 10)
                npc.npc_remove_item("Wolf Pelt")
                gain_skill_xp(npc, "tanning", 1.5 if success else 0.5)
                if success:
                    npc.npc_add_item(make_item("Tanned Hide"))
                    npc.add_memory("craft", "Tanned a hide into leather", 2)
                else:
                    npc.add_memory("craft", "Hide was ruined during tanning", 1)

        elif action == "dyeing":
            from game.systems.skills import skill_check
            if npc.npc_has_item("Linen") and npc.npc_has_item("Flowers"):
                success, total, natural = skill_check(npc, "dyeing", 10)
                npc.npc_remove_item("Linen")
                npc.npc_remove_item("Flowers")
                gain_skill_xp(npc, "dyeing", 1.5 if success else 0.5)
                if success:
                    npc.npc_add_item(make_item("Dyed Cloth"))
                    npc.add_memory("craft", "Dyed cloth with beautiful colors", 2)
                else:
                    npc.add_memory("craft", "Dye didn't set properly", 1)

        elif action == "training_animal":
            from game.systems.skills import skill_check
            success, total, natural = skill_check(npc, "animal_training", 13)
            gain_skill_xp(npc, "animal_training", 1.5 if success else 0.5)
            if success:
                npc.add_memory("work", "Trained an animal successfully", 2)
                gain_skill_xp(npc, "animal_care", 0.5)
            else:
                npc.add_memory("work", "Animal was stubborn today", 1)

        npc.current_action = ""
        npc.action_target = None
        npc.action_timer = 0
        npc.action_progress = 0
        npc.state = "idle"
        # Reset decision timer so NPC quickly picks next action
        npc.llm_decision_timer = random.uniform(0.5, 2.0)

    # ---- NPC COMBAT ----

