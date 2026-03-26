"""Simulation decisions — LLM-driven NPC decision making."""

import random
import time
import re
from typing import List, Tuple
from game.core.npc import NPC
from game.core.player import Player
from game.ai.prompts import Prompts, build_npc_context, mock_npc_decision
from game.settings import *


class SimDecisionsMixin:
    """LLM decision-related simulation methods."""

    def _request_decisions(self, npcs: List[NPC], dt: float, player: Player):
        now = time.time()
        for npc in npcs:
            if not npc.alive or npc.pending_llm_decision:
                continue

            # Skip detailed AI for distant NPCs (abstraction layer)
            if self._active_npc_set is not None and npc.name not in self._active_npc_set:
                continue

            if npc.current_action in ("chopping", "mining", "building", "farming",
                                       "fishing", "sleeping", "talking", "fighting",
                                       "training", "performing", "researching", "praying",
                                       "ritual", "enchanting", "crafting_pottery",
                                       "crafting_glass", "tanning", "dyeing",
                                       "training_animal", "seeking_bed", "fleeing",
                                       "approaching_player",
                                       "carrying", "commuting", "hunting",
                                       "smithing", "guarding",
                                       "seeking_shelter"):
                continue  # busy

            npc.llm_decision_timer -= dt
            if npc.llm_decision_timer > 0:
                continue

            # Determine interval based on distance to player
            dist = npc.dist_to(player)
            interval = NPC_DECISION_INTERVAL if dist < NPC_DECISION_PRIORITY_RANGE else NPC_DECISION_INTERVAL_FAR
            npc.llm_decision_timer = interval

            # Rate limit
            if now - self._last_llm_time < self._llm_min_interval:
                continue
            self._last_llm_time = now

            # Build context with rich social data — use spatial grid
            nearby_parts = []
            for other in self.npc_grid.get_nearby(npc.x, npc.y, 10):
                if other is npc or not other.alive:
                    continue
                d = npc.dist_to(other)
                if d < 10:
                    # Get detailed relationship from social system
                    social_rel = self.social.get_rel(npc.name, other.name)
                    rel_label = social_rel.label
                    trust = social_rel.trust
                    other_cls = getattr(other, 'char_class', other.profession)
                    other_race = getattr(other, 'race', '')
                    mood_word = ""
                    if getattr(other, 'mood', 0) < -0.3:
                        mood_word = ", seems upset"
                    elif getattr(other, 'mood', 0) > 0.3:
                        mood_word = ", seems happy"
                    nearby_parts.append(
                        f"- {other.name} ({other_race} {other_cls}), {d:.0f} tiles, "
                        f"{rel_label} (trust:{trust:+.0f}){mood_word}"
                    )
            # Player
            if dist < 12:
                rel = npc.player_relationship
                rel_word = "friendly" if rel > 20 else "hostile" if rel < -20 else "neutral"
                nearby_parts.append(f"- Player (adventurer), {dist:.0f} tiles, {rel_word}")
            # Creatures — use spatial grid for O(1) lookup instead of full scan
            nearby_creatures = []
            for c in self.creature_grid.get_nearby(npc.x, npc.y, 8):
                if c.alive:
                    d = npc.dist_to(c)
                    if d < 8:
                        nearby_parts.append(f"- {c.kind} (hostile creature), {d:.0f} tiles")
                        nearby_creatures.append(c.kind)

            loc = self.world.get_structure_at(npc.x, npc.y)
            loc_name = loc.name if loc else "wilderness"

            time_norm = self.time_sys.normalized
            tod = "night" if self.time_sys.is_night else "morning" if time_norm < 0.4 else "afternoon" if time_norm < 0.7 else "evening"

            nearby_npc_names = [p.split("(")[0].strip("- ").strip() for p in nearby_parts if "hostile creature" not in p]

            # Build situational context (activity, economy, events)
            npc_situation = build_npc_context(
                npc, world=self.world,
                world_effects=getattr(self, 'world_effects', None),
                governance=getattr(self, 'governance', None),
                time_sys=self.time_sys,
                event_log=self.event_log,
                economy=getattr(self, 'economy', None),
            )

            # Use LLM if enabled, otherwise mock
            if self.llm.enabled:
                prompt = Prompts.npc_decision(
                    name=npc.name, profession=npc.profession,
                    personality=npc.personality_desc + (" [" + ", ".join(getattr(npc, 'social_traits', [])) + "]" if getattr(npc, 'social_traits', None) else "") + (f", age {int(getattr(npc, 'age', 30))}, {getattr(npc, 'title', 'commoner')}" if hasattr(npc, 'age') else ""),
                    attributes=npc.attr_summary(),
                    needs=npc.needs_summary(),
                    hp_status=f"{int(npc.hp)}/{npc.max_hp}",
                    gold=npc.npc_gold,
                    inventory=npc.inventory_summary(),
                    location=loc_name,
                    nearby="\n".join(nearby_parts) if nearby_parts else "nobody nearby",
                    memories="\n".join(npc.get_recent_memories(5)) or "none",
                    current_goal=npc.current_goal,
                    known_info="; ".join(npc.known_info[-5:]) if npc.known_info else "",
                    time_of_day=tod, day=self.time_sys.day,
                    consciousness=npc.consciousness,
                    char_class=getattr(npc, 'char_class', ''),
                    race=getattr(npc, 'race', ''),
                    level=getattr(npc, 'level', 1),
                    long_term_goals=", ".join(getattr(npc, 'long_term_goals', [])),
                    current_plan="; ".join(getattr(npc, 'current_plan', [])),
                    friends=self.social.get_relationship_summary(npc.name, 5) if hasattr(self, 'social') else ", ".join(getattr(npc, 'friends', [])),
                    enemies=", ".join(getattr(npc, 'enemies', [])),
                    party_info=npc.party_id or "",
                    class_abilities=", ".join(getattr(npc, 'class_abilities', [])),
                    spells_available=", ".join(getattr(npc, 'known_spells', [])) if getattr(npc, 'is_spellcaster', False) else "",
                    alignment=getattr(npc, 'alignment', ''),
                    situation_context=npc_situation,
                )
                priority = 10 if dist < NPC_DECISION_PRIORITY_RANGE else 1
                req_id = f"decision_{npc.name}_{now:.0f}"

                def _on_decision(text, _npc=npc):
                    _npc.pending_llm_decision = False

                self.llm.request(req_id, prompt, callback=_on_decision,
                                 max_tokens=60, temperature=0.8)
                # Store req_id so we can poll
                npc._decision_req_id = req_id
                npc.pending_llm_decision = True
            else:
                # Independent approach check — NPCs notice player regardless of schedule
                if (dist < 8 and not npc.wants_to_talk
                        and npc.current_action != "approaching_player"
                        and random.random() < 0.08):
                    rel = getattr(npc, 'player_relationship', 0)
                    if rel > 20:
                        reason = "want to catch up with an old friend"
                    elif getattr(npc, 'has_quest_marker', False):
                        reason = "have something important to discuss"
                    elif random.random() < 0.5:
                        reason = "curious about the traveler"
                    else:
                        reason = "want to share some local news"
                    decision = f"APPROACH_PLAYER | player | {reason}"
                    self._apply_decision(npc, decision)
                    continue

                # Daily schedule — time-based routines (sleep/work/eat/socialize)
                from game.systems.daily_schedule import get_daily_action
                hour = getattr(self.time_sys, 'hour', 12.0)
                if not isinstance(hour, (int, float)):
                    hour = getattr(self.time_sys, 'normalized', 0.5) * 24.0
                is_storm = False
                if hasattr(self, 'climate') and self.climate:
                    w = getattr(self.climate, 'current_weather', None)
                    if w:
                        is_storm = getattr(w, 'condition', '') in ('storm', 'blizzard', 'heat_wave')
                daily_action = get_daily_action(npc, hour, self.world, is_storm)
                if daily_action and random.random() < 0.92:
                    npc.current_action = daily_action
                    npc._action_timer = random.uniform(3.0, 8.0)
                    npc._decision_timer = random.uniform(5.0, 15.0)
                    continue

                # Fallback: check older schedule system
                from game.systems.schedules import get_scheduled_action
                scheduled = get_scheduled_action(
                    npc, self.time_sys.normalized, self.world, self.world.structures)

                if scheduled and random.random() < 0.90:
                    decision = f"{scheduled['action']} | {scheduled.get('target_x', 'nearby')} | {scheduled['reason']}"
                    if scheduled.get('target_x') is not None:
                        npc.target_x = scheduled['target_x']
                        npc.target_y = scheduled.get('target_y', npc.y)
                else:
                    decision = mock_npc_decision(
                        npc.needs, npc.has_food(), npc.has_drink(),
                        nearby_npc_names, nearby_creatures, npc.profession,
                        char_class=getattr(npc, 'char_class', npc.profession),
                        long_term_goals=getattr(npc, 'long_term_goals', []),
                        friends=getattr(npc, 'friends', []),
                        party_id=getattr(npc, 'party_id', None),
                        alignment=getattr(npc, 'alignment', 'true neutral'),
                    )
                    # Prevent pure idle — if decision is IDLE, try to assign
                    # job-related work instead
                    if decision.upper().startswith("IDLE"):
                        from game.systems.schedules import CLASS_WORK_ACTIONS
                        cls = getattr(npc, 'char_class', '') or npc.profession
                        fallback = CLASS_WORK_ACTIONS.get(cls, CLASS_WORK_ACTIONS.get(npc.profession))
                        if fallback:
                            chosen = random.choice(fallback)
                            parts = [p.strip() for p in chosen.split("|")]
                            decision = f"{parts[0]} | {parts[1] if len(parts) > 1 else 'nearby'} | {parts[2] if len(parts) > 2 else 'keeping busy'}"
                self._apply_decision(npc, decision)

    def _check_creature_approaches(self, creatures, dt: float, player: Player):
        """Give intelligent creatures a chance to approach the player."""
        from game.core.creature_dialogs import is_intelligent
        for creature in creatures:
            if not creature.alive or not is_intelligent(creature.kind):
                continue
            if getattr(creature, 'wants_to_talk', False):
                continue
            if getattr(creature, 'state', '') in ('chasing', 'attacking', 'fleeing'):
                continue
            dist = creature.dist_to(player)
            if dist < 8 and random.random() < 0.03:
                creature.wants_to_talk = True
                reasons = {
                    "orc": "demands you leave their territory",
                    "goblin": "wants to trade with you",
                    "kobold": "squeaks nervously at you",
                    "gnoll": "sniffs the air hungrily",
                    "bandit": "blocks the road ahead",
                    "bugbear": "growls a warning",
                    "hobgoblin": "barks a challenge",
                }
                base = creature.kind.split("_")[0]
                creature.talk_reason = reasons.get(
                    base, "wants to speak with you")
                # Stop chasing so conversation can happen
                creature.state = "idle"
                creature.target = None

    def _poll_decisions(self, npcs: List[NPC]):
        for npc in npcs:
            if not npc.pending_llm_decision:
                continue
            req_id = getattr(npc, "_decision_req_id", None)
            if not req_id:
                continue
            result = self.llm.get_result(req_id)
            if result:
                npc.pending_llm_decision = False
                self._apply_decision(npc, result)

    def _apply_decision(self, npc: NPC, decision_text: str):
        """Parse and execute a decision string: ACTION | TARGET | REASON"""
        action, target, reason = self._parse_decision(decision_text)
        npc.last_decision_reason = reason
        self._execute_action(npc, action, target, reason)

    def _parse_decision(self, text: str) -> Tuple[str, str, str]:
        """Parse 'ACTION | TARGET | REASON' format."""
        text = text.strip().split("\n")[0]  # First line only
        parts = [p.strip() for p in text.split("|")]
        if len(parts) >= 3:
            return parts[0].upper(), parts[1], parts[2]
        elif len(parts) == 2:
            return parts[0].upper(), parts[1], ""
        else:
            # Try to extract just the action
            word = text.split()[0].upper() if text.split() else "IDLE"
            return word, "", ""

    # ---- ACTION EXECUTION ----

