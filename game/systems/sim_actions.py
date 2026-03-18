"""Simulation actions — NPC action execution, progress, completion."""

import random
import math
import time
from typing import List, Optional
from game.core.npc import NPC
from game.core.player import Player
from game.core.items import make_item, FOOD_ITEMS
from game.settings import *


from game.systems.sim_execute import SimExecuteMixin


class SimActionsMixin(SimExecuteMixin):
    """Action execution and progress methods.

    _execute_action is in sim_execute.py (SimExecuteMixin).
    """

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

