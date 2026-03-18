"""Simulation needs — decay, critical needs, sleep quality."""

import random
import math
from typing import List
from game.core.npc import NPC
from game.core.items import make_item
from game.settings import *


class SimNeedsMixin:
    """Needs-related simulation methods."""

    def _get_sleep_quality(self, npc) -> float:
        """Get sleep quality based on where the NPC is sleeping.
        Returns rest recovery rate per second."""
        x, y = int(npc.x), int(npc.y)

        # Check if on a bed tile (best rest)
        if 0 <= x < self.world.width and 0 <= y < self.world.height:
            tile = self.world.tiles[y][x]
            if tile == BED:
                return 2.5  # excellent rest in a proper bed

        # Check if inside a building (good rest)
        if hasattr(self, '_player_ref'):
            from game.systems.buildings import BuildingSystem
        loc = self.world.get_structure_at(npc.x, npc.y)
        if loc and loc.kind in ("village", "town", "city", "hamlet", "castle"):
            # Inside a settlement building
            if 0 <= x < self.world.width and 0 <= y < self.world.height:
                tile = self.world.tiles[y][x]
                if tile == FLOOR:
                    return 1.8  # decent rest indoors on floor

        # Check if near home (moderate rest)
        home_dist = npc.dist_to_pos(npc.home_x, npc.home_y)
        if home_dist < 5:
            return 1.5  # near home comfort

        # Check if on road (poor rest)
        if 0 <= x < self.world.width and 0 <= y < self.world.height:
            tile = self.world.tiles[y][x]
            if tile == ROAD:
                return 0.5  # terrible rest on the road

        # Outdoors in wilderness
        return 0.8  # poor rest outdoors

    def _get_sleep_safety(self, npc) -> bool:
        """Check if the NPC's sleeping location is safe from attacks."""
        x, y = int(npc.x), int(npc.y)

        # Inside a building with walls = safe
        if 0 <= x < self.world.width and 0 <= y < self.world.height:
            tile = self.world.tiles[y][x]
            if tile in (BED, FLOOR):
                # Check if enclosed (surrounded by walls on at least 2 sides)
                wall_count = 0
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.world.width and 0 <= ny < self.world.height:
                        if self.world.tiles[ny][nx] in (WALL, BUILT_WALL, LOCKED_DOOR, WINDOW):
                            wall_count += 1
                if wall_count >= 2:
                    return True  # enclosed = safe

        # Near guards = safe (spatial grid)
        nearby = self.npc_grid.get_nearby(npc.x, npc.y, 8)
        for other_npc in nearby:
            if other_npc is npc:
                continue
            if True:  # already filtered by spatial grid
                title = getattr(other_npc, 'title', '')
                char_class = getattr(other_npc, 'char_class', '')
                if title == 'guard' or char_class in ('Fighter', 'Paladin', 'Ranger'):
                    if other_npc.current_action != "sleeping":
                        return True  # guard nearby and awake

        # Outdoors = not safe
        return False


    def _decay_needs(self, npcs: List[NPC], dt: float):
        time_mult = self.time_sys.speed
        active_set = self._active_npc_set

        # Cap effective dt so needs don't drain impossibly fast at high time speeds.
        # At 100x speed, raw dt*speed would drain needs before NPCs can act.
        # Cap to equivalent of ~3x real-time decay regardless of speed setting.
        effective_dt = min(dt * time_mult, dt * 3.0 + 1.0 / 30.0)

        for npc in npcs:
            if not npc.alive:
                continue
            # Skip dormant NPCs - they're handled by abstract sim stabilizer
            if active_set is not None and npc.name not in active_set:
                continue
            # Apply active event effects
            h_mult = 1.0
            t_mult = 1.0
            r_mult = 1.0
            for evt in self.events:
                if evt.affects(npc):
                    h_mult *= evt.effects.get("hunger_mult", 1.0)
                    t_mult *= evt.effects.get("thirst_mult", 1.0)
                    r_mult *= evt.effects.get("rest_mult", 1.0)
                    # Social boost from festivals
                    if evt.effects.get("social_boost"):
                        npc.needs["social"] = min(100, npc.needs["social"] + evt.effects["social_boost"] * dt)

            # Apply race-specific need modifiers
            race_mods = getattr(npc, 'need_multipliers', {})
            race_h = race_mods.get("hunger", 1.0)
            race_t = race_mods.get("thirst", 1.0)
            race_r = race_mods.get("rest", 1.0)

            npc.needs["hunger"] = max(0, npc.needs["hunger"] - NEED_DECAY["hunger"] * effective_dt * h_mult * race_h)
            npc.needs["thirst"] = max(0, npc.needs["thirst"] - NEED_DECAY["thirst"] * effective_dt * t_mult * race_t)
            npc.needs["social"] = max(0, npc.needs["social"] - NEED_DECAY["social"] * effective_dt)

            # Rest: decays while awake, recovers while sleeping
            # Recovery rate depends on sleep quality (where they are)
            if npc.current_action == "sleeping":
                sleep_quality = self._get_sleep_quality(npc)
                npc.needs["rest"] = min(100, npc.needs["rest"] + sleep_quality * effective_dt)
                # Heal while sleeping well
                if sleep_quality > 1.0 and npc.hp < npc.max_hp:
                    npc.hp = min(npc.max_hp, npc.hp + 0.2 * dt)
            else:
                npc.needs["rest"] = max(0, npc.needs["rest"] - NEED_DECAY["rest"] * effective_dt * r_mult)

            # Sleep deprivation effects
            rest = npc.needs["rest"]
            if rest < 15:
                # Exhausted: speed penalty, can't fight well
                npc.speed = getattr(npc, '_base_speed', npc.speed) * 0.6
                if not hasattr(npc, '_base_speed'):
                    npc._base_speed = npc.speed / 0.6
                # Hallucination/confusion at very low rest
                if rest < 5 and random.random() < 0.001 * dt:
                    npc.add_memory("exhaustion", "So tired... can barely stay awake", 3)
            elif rest < 30:
                # Tired: slight speed penalty
                if hasattr(npc, '_base_speed'):
                    npc.speed = npc._base_speed * 0.85
            else:
                # Rested: restore normal speed
                if hasattr(npc, '_base_speed'):
                    npc.speed = npc._base_speed
                    del npc._base_speed

            # Force collapse if rest hits 0
            if rest <= 0 and npc.current_action != "sleeping":
                npc.current_action = "sleeping"
                npc.state = "sleeping"
                npc.state_timer = random.uniform(15, 30)
                npc.action_timer = npc.state_timer
                npc.add_memory("exhaustion", "Collapsed from exhaustion!", 4)
                # Collapse in place - vulnerable!

            # Sleeping NPCs are vulnerable to nearby threats
            if npc.current_action == "sleeping":
                sleep_safety = self._get_sleep_safety(npc)
                if not sleep_safety:
                    # Use spatial grid for O(1) nearby creature lookup
                    nearby_creatures = self.creature_grid.get_nearby(npc.x, npc.y, 3)
                    for creature in nearby_creatures:
                        if creature.alive:
                            # Creature attacks sleeping NPC!
                            dmg = getattr(creature, 'damage', 5)
                            npc.take_damage(dmg)
                            npc.current_action = ""
                            npc.state = "idle"
                            npc.needs["rest"] = min(npc.needs["rest"] + 10, 30)  # jolted awake
                            npc.add_memory("danger", f"Attacked by {creature.kind} while sleeping!", 5)
                            self.event_log.append(f"{npc.name} was attacked by a {creature.kind} while sleeping outdoors!")
                            # Fight or flee
                            if npc.bravery > 0.4:
                                npc.combat_target = creature
                                npc.current_action = "fighting"
                            else:
                                npc.flee_from(creature.x, creature.y)
                            break

            # Plague damage
            for evt in self.events:
                if evt.affects(npc) and evt.effects.get("plague_dps"):
                    npc.hp = max(0, npc.hp - evt.effects["plague_dps"] * dt)
                    if npc.hp <= 0:
                        npc.alive = False
                        if hasattr(self, 'burial'):
                            self.burial.on_death(npc, "disease",
                                                 self.time_sys.time_string,
                                                 self.time_sys.day, self.world)

    def _check_critical_needs(self, npcs: List[NPC], dt: float):
        for npc in list(npcs):
            if not npc.alive:
                continue
            # Skip dormant NPCs
            if self._active_npc_set is not None and npc.name not in self._active_npc_set:
                continue

            # Emotion trigger for hunger/thirst distress
            if npc.needs["hunger"] < 20 or npc.needs["thirst"] < 20:
                from game.systems.emotions import trigger_emotion
                trigger_emotion(npc, "went_hungry", intensity=0.4,
                                cause="starving" if npc.needs["hunger"] < 20 else "dehydrated",
                                game_time=self.time_sys.time)

            # Auto-eat/drink when getting low (survival instinct)
            # Don't interrupt timed work actions for routine eating
            is_busy = npc.action_timer > 0 and npc.current_action not in ("", "idle", "moving")
            if npc.needs["hunger"] < 45 and npc.has_food():
                eaten = npc.consume_food()
                if eaten:
                    if npc.needs["hunger"] < 20:
                        npc.add_memory("survival", f"Ate {eaten} — was starving", 3)
                    if not is_busy:
                        npc.current_action = ""
            if npc.needs["thirst"] < 45 and npc.has_drink():
                drunk = npc.consume_drink()
                if drunk:
                    if npc.needs["thirst"] < 20:
                        npc.add_memory("survival", f"Drank {drunk} — was parched", 3)
                    if not is_busy:
                        npc.current_action = ""

            # Cache structure lookup to avoid repeated calls
            _npc_loc = self.world.get_structure_at(npc.x, npc.y) if (
                npc.needs["hunger"] < 35 or not npc.has_drink() or
                npc.npc_count_item("Water Flask") < 2) else None

            # Settlement food sharing — NPCs in settlements share food with neighbors
            if npc.needs["hunger"] < 35 and not npc.has_food():
                loc = _npc_loc
                if loc and loc.kind in ("village", "town", "city", "hamlet", "castle"):
                    # Settlement provides basic food (communal supplies / market)
                    food = make_item("Bread")
                    food.count = 3
                    npc.npc_add_item(food)

            # Auto-forage when low on supplies and needs dropping
            if npc.needs["hunger"] < 50 and not npc.has_food() and npc.current_action == "":
                self._move_to_forage(npc)

            # Auto-refill water at wells/rivers/settlements
            if not npc.has_drink() or npc.npc_count_item("Water Flask") < 2:
                refilled = False
                nx, ny = int(npc.x), int(npc.y)
                # Check if NPC is in/near a settlement (settlements have wells)
                loc = _npc_loc
                if loc and loc.kind in ("village", "town", "city", "hamlet", "castle"):
                    # Settlement residents can always get water from the well
                    water = make_item("Water Flask")
                    water.count = 4
                    npc.npc_add_item(water)
                    npc.needs["thirst"] = min(100, npc.needs["thirst"] + 30)
                    refilled = True
                if not refilled:
                    # Check nearby tiles for natural water sources
                    for dx in range(-3, 4):
                        for dy in range(-3, 4):
                            tx, ty = nx + dx, ny + dy
                            if (0 <= tx < self.world.width and 0 <= ty < self.world.height and
                                self.world.tiles[ty][tx] in (WELL, WATER, SHALLOW_WATER)):
                                water = make_item("Water Flask")
                                water.count = 3
                                npc.npc_add_item(water)
                                npc.needs["thirst"] = min(100, npc.needs["thirst"] + 25)
                                refilled = True
                                break
                        if refilled:
                            break

            # Water seeking — urgent survival behavior
            non_interruptible = ("fighting", "fleeing", "seeking_water")
            if npc.needs["thirst"] < 30 and not npc.has_drink():
                if npc.current_action not in non_interruptible:
                    water = self.world.find_water_near(int(npc.x), int(npc.y), 20)
                    if water:
                        npc.target_x, npc.target_y = float(water[0]), float(water[1])
                        npc.current_action = "seeking_water"
                        npc.action_timer = 0
                        npc.state = "walking"
                    else:
                        # Desperate: drink from puddles/dew
                        npc.needs["thirst"] = min(100, npc.needs["thirst"] + 10)
                        npc.current_action = ""
            elif npc.needs["thirst"] < 50 and not npc.has_drink() and npc.current_action == "":
                water = self.world.find_water_near(int(npc.x), int(npc.y), 15)
                if water:
                    npc.target_x, npc.target_y = float(water[0]), float(water[1])
                    npc.current_action = "seeking_water"
                    npc.state = "walking"
                else:
                    self._move_to_forage(npc)

            # Seek safe rest when very tired
            if npc.needs["rest"] < 18 and npc.current_action not in ("sleeping", "fleeing", "fighting"):
                # Try to go home first (safest bed)
                home_dist = npc.dist_to_pos(npc.home_x, npc.home_y)
                if home_dist < 20:
                    # Go home and sleep
                    npc.target_x = npc.home_x
                    npc.target_y = npc.home_y
                    npc.state = "walking"
                    npc.current_action = "seeking_bed"
                    npc.current_goal = "find a safe place to sleep"
                elif npc.needs["rest"] < 10:
                    # Desperate: check nearest settlement (use cached lookup)
                    loc = _npc_loc if _npc_loc else self.world.get_structure_at(npc.x, npc.y)
                    if loc and loc.kind in ("village", "town", "city", "tavern"):
                        npc.target_x = float(loc.x)
                        npc.target_y = float(loc.y)
                        npc.state = "walking"
                        npc.current_action = "seeking_bed"
                    else:
                        # Just go home
                        npc.target_x = npc.home_x
                        npc.target_y = npc.home_y
                        npc.state = "walking"
                        npc.current_action = "seeking_bed"

            # If seeking a bed and arrived, sleep
            if npc.current_action == "seeking_bed":
                if npc.target_x is not None:
                    dist = npc.dist_to_pos(npc.target_x, npc.target_y)
                    if dist < 2:
                        npc.current_action = "sleeping"
                        npc.state = "sleeping"
                        npc.state_timer = random.uniform(15, 30)
                        npc.action_timer = npc.state_timer
                        npc.target_x = None
                        npc.target_y = None

            # Damage from starvation/dehydration (reduced to give NPCs more time)
            if npc.needs["hunger"] <= 0:
                npc.hp -= 0.3 * dt
            if npc.needs["thirst"] <= 0:
                npc.hp -= 0.5 * dt

            if npc.hp <= 0:
                self._handle_npc_death(npc)

