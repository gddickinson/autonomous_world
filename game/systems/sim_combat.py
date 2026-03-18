"""Simulation combat — threat response, NPC combat ticking."""

import random
import math
from typing import List, Optional
from game.core.npc import NPC
from game.core.creature import Creature
from game.core.player import Player
from game.settings import *


class SimCombatMixin:
    """Combat-related simulation methods."""

    def _threat_response(self, npcs: List[NPC], dt: float):
        """Tactical threat response — role-based, with group coordination.

        AI improvements from colosseum testing:
        - Tactical target selection (threat scoring, not just nearest)
        - Ranged NPCs engage from distance, don't close to melee
        - Group focus-fire on the same target
        - Healers prioritize healing wounded allies over fighting
        - Guards intercept threats heading toward civilians
        - Morale-aware fleeing (wounded cowards flee earlier)
        """
        threat_range = 12.0
        combat_classes = {"Fighter", "Paladin", "Barbarian", "Ranger"}
        caster_classes = {"Wizard", "Sorcerer", "Warlock", "Cleric", "Druid"}
        ranged_classes = {"Ranger"}
        healer_classes = {"Cleric", "Druid"}

        active_set = self.abstract.active_npcs if hasattr(self, 'abstract') else None
        busy_actions = frozenset(("fighting", "fleeing", "following_player"))

        for npc in npcs:
            if not npc.alive:
                continue
            if npc.current_action in busy_actions:
                continue
            if active_set is not None and npc.name not in active_set:
                continue

            nearby_creatures = self.creature_grid.get_nearby(npc.x, npc.y, threat_range)

            # --- TACTICAL TARGET SELECTION with ALLEGIANCE ---
            from game.systems.allegiance import should_attack, are_allies
            best_threat = None
            best_score = 0.0
            for creature in nearby_creatures:
                # Skip allies and passive creatures
                if not should_attack(npc, creature):
                    continue
                d = npc.dist_to(creature)
                if d > threat_range:
                    continue
                cr = getattr(creature, 'cr', 0.25)
                # Higher score = more urgent target
                proximity = max(0.1, 1.0 - d / threat_range)
                score = cr * proximity * 10

                # Bonus: target already fighting an ally (help them)
                for ally in self.npc_grid.get_nearby(npc.x, npc.y, 8):
                    if ally is npc or not ally.alive:
                        continue
                    if getattr(ally, 'combat_target', None) is creature:
                        score += 5  # focus fire bonus
                        break

                # Bonus: creature heading toward home/civilians
                if npc.dist_to_pos(npc.home_x, npc.home_y) < 20:
                    home_dist = creature.dist_to_pos(npc.home_x, npc.home_y) if hasattr(creature, 'dist_to_pos') else d
                    if home_dist < 15:
                        score += 8  # defend home

                if score > best_score:
                    best_score = score
                    best_threat = creature

            if best_threat is None:
                continue

            nearest_threat = best_threat
            nearest_dist = npc.dist_to(nearest_threat)

            char_class = getattr(npc, 'char_class', '')
            bravery = npc.bravery
            hp_ratio = npc.hp / max(1, npc.max_hp)

            threat_cr = getattr(nearest_threat, 'cr', 0.25)
            npc_level = getattr(npc, 'level', 1)
            can_handle = npc_level >= threat_cr * 2

            # --- HEALER BEHAVIOR: heal wounded allies instead of fighting ---
            if char_class in healer_classes:
                wounded_ally = None
                for ally in self.npc_grid.get_nearby(npc.x, npc.y, 8):
                    if ally is npc or not ally.alive or not are_allies(npc, ally):
                        continue
                    if ally.hp / max(1, ally.max_hp) < 0.5:
                        wounded_ally = ally
                        break
                if wounded_ally and nearest_dist > 3.0:
                    # Heal ally instead of fighting
                    npc.target_x = wounded_ally.x
                    npc.target_y = wounded_ally.y
                    npc.current_action = "moving"
                    npc.current_goal = f"heal {wounded_ally.name}"
                    npc.state = "walking"
                    npc.state_timer = 5.0
                    continue

            if nearest_dist < 4.0:
                # VERY CLOSE — immediate reaction
                if char_class in combat_classes and bravery > 0.4 and hp_ratio > 0.3 and can_handle:
                    npc.combat_target = nearest_threat
                    npc.current_action = "fighting"
                    npc.state = "fighting"
                    npc.add_memory("combat", f"Engaged a {nearest_threat.kind}!", 3)

                    # Alert + coordinate: nearby NPCs focus same target
                    nearby_npcs = self.npc_grid.get_nearby(npc.x, npc.y, 8)
                    for other in nearby_npcs:
                        if other is npc or not other.alive:
                            continue
                        other.add_memory("alert", f"{npc.name} is fighting a {nearest_threat.kind}!", 2)
                        # Group focus: idle combat NPCs join the fight on same target
                        other_cc = getattr(other, 'char_class', '')
                        if (other_cc in combat_classes and
                            other.current_action not in busy_actions and
                            other.bravery > 0.3):
                            other.combat_target = nearest_threat
                            other.current_action = "fighting"
                            other.state = "fighting"

                elif char_class in caster_classes and bravery > 0.3 and can_handle:
                    # Casters fight from range via combat tick
                    npc.combat_target = nearest_threat
                    npc.current_action = "fighting"
                    npc.state = "fighting"
                    npc.add_memory("combat", f"Engaged a {nearest_threat.kind} with magic!", 3)

                elif char_class in ranged_classes and bravery > 0.3:
                    # Ranged: engage but combat tick handles kiting
                    npc.combat_target = nearest_threat
                    npc.current_action = "fighting"
                    npc.state = "fighting"

                else:
                    # FLEE — morale check with HP awareness
                    flee_threshold = 0.3 + (1.0 - bravery) * 0.3
                    if hp_ratio < flee_threshold or bravery < 0.3:
                        npc.flee_from(nearest_threat.x, nearest_threat.y)
                        npc.add_memory("fear", f"Ran from a {nearest_threat.kind}!", 2)
                        home_dist = npc.dist_to_pos(npc.home_x, npc.home_y)
                        if home_dist < 15:
                            npc.target_x = npc.home_x
                            npc.target_y = npc.home_y
                            npc.current_action = "fleeing_home"
                    else:
                        # Not brave enough to fight solo, but not fleeing
                        # Alert guards
                        npc.add_memory("alert", f"Spotted a {nearest_threat.kind}!", 2)

            elif nearest_dist < 8.0:
                # MEDIUM RANGE
                if char_class in combat_classes and bravery > 0.5:
                    npc.target_x = nearest_threat.x
                    npc.target_y = nearest_threat.y
                    npc.current_action = "moving"
                    npc.current_goal = f"intercept {nearest_threat.kind}"
                    npc.state = "walking"
                    npc.state_timer = 5.0
                elif char_class in ranged_classes:
                    # Ranged NPCs engage from this distance
                    npc.combat_target = nearest_threat
                    npc.current_action = "fighting"
                    npc.state = "fighting"
                else:
                    npc.add_memory("alert", f"Spotted a {nearest_threat.kind} nearby", 2)
                    # Call for guards
                    nearby_npcs = self.npc_grid.get_nearby(npc.x, npc.y, 10)
                    for other in nearby_npcs:
                        if other is npc:
                            continue
                        other_class = getattr(other, 'char_class', '')
                        if other_class in combat_classes:
                            other.target_x = nearest_threat.x
                            other.target_y = nearest_threat.y
                            other.current_action = "moving"
                            other.current_goal = f"respond to threat: {nearest_threat.kind}"
                            other.state = "walking"
                            other.state_timer = 8.0
                            other.add_memory("alert", f"{npc.name} called for help against a {nearest_threat.kind}!", 3)
                            self.event_log.append(f"{npc.name} called {other.name} to fight a {nearest_threat.kind}!")
                            break


    def _npc_combat_tick(self, npcs: List[NPC], dt: float):
        """NPC combat — delegates to CombatSystem.npc_combat_tick for tactical AI.

        Handles: self-sacrifice, emotions, death recording, mental health.
        Combat mechanics (D20, body damage, kiting, flanking, morale) are
        all in CombatSystem.npc_combat_tick.
        """
        from game.systems.combat import CombatSystem

        active_set = self._active_npc_set
        player = self._player_ref if hasattr(self, '_player_ref') else None
        creatures = self.world_mgr.creatures

        for npc in npcs:
            if not npc.alive or npc.current_action != "fighting":
                continue
            if active_set is not None and npc.name not in active_set:
                continue

            target = npc.combat_target
            if not target or not target.alive:
                npc.current_action = ""
                npc.combat_target = None
                continue

            # Self-sacrifice: a loved one may intercept the blow
            if isinstance(target, NPC) and hasattr(self, 'social_dynamics'):
                _grid = self.npc_grid if hasattr(self, 'npc_grid') else None
                protector = self.social_dynamics.check_self_sacrifice(
                    target, npc, npcs, _grid)
                if protector is not None:
                    npc.combat_target = protector
                    target = protector
                    self.event_log.append(
                        f"{protector.name} leaps in to protect "
                        f"beloved {getattr(target, 'name', '?')}!")

            # Health system wound infection tracking
            if isinstance(target, NPC) and hasattr(self, 'health'):
                self.health.on_combat_damage(target, 0)  # just track exposure

            # Record target HP before attack
            hp_before = target.hp

            # --- DELEGATE to CombatSystem (tactical AI, body damage, etc.) ---
            _p = player if player else type('P', (), {'x': 0, 'y': 0})()
            msg = CombatSystem.npc_combat_tick(npc, _p, creatures, npcs, dt)

            # --- POST-ATTACK: emotions, death handling, ledger ---
            if target.hp < hp_before:
                # Target was hit
                if isinstance(target, NPC):
                    from game.systems.emotions import trigger_emotion
                    trigger_emotion(target, "attacked", intensity=0.8,
                                    target=npc.name,
                                    cause=f"attacked by {npc.name}",
                                    game_time=self.time_sys.time)

            if not target.alive:
                target_name = getattr(target, 'name', getattr(target, 'kind', '?'))
                npc.add_memory("combat", f"Defeated {target_name}", 4)

                from game.systems.emotions import trigger_emotion
                trigger_emotion(npc, "won_fight", intensity=0.8,
                                target=target_name,
                                cause=f"defeated {target_name}",
                                game_time=self.time_sys.time)
                for other in self.npc_grid.get_nearby(npc.x, npc.y, 10):
                    if other is not npc and other.alive:
                        trigger_emotion(other, "witnessed_death",
                                        intensity=0.6,
                                        target=target_name,
                                        cause=f"saw {target_name} die",
                                        game_time=self.time_sys.time)
                        if hasattr(self, 'mental_health'):
                            self.mental_health.on_death_witnessed(other)

                from game.systems.memory import ensure_life_ledger
                ledger = ensure_life_ledger(npc)
                is_npc_target = isinstance(target, NPC)
                ledger.record_kill(target_name, self.time_sys.day, is_npc=is_npc_target)

                if is_npc_target:
                    self._handle_npc_death(target)

    # ---- CONVERSATIONS & INFO ----

