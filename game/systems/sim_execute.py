"""Simulation action execution — the big action dispatcher."""

import random
import math
import time
from typing import List, Optional
from game.core.npc import NPC
from game.core.items import make_item, FOOD_ITEMS
from game.settings import *


class SimExecuteMixin:
    """The _execute_action dispatcher — maps LLM decisions to game actions."""

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

