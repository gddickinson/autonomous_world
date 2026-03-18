"""Dialog result processing — game effects from conversation choices."""

import random
from game.settings import *


class DialogResultsMixin:
    """Handles _process_dialog_result for the Game class."""

    def _process_dialog_result(self, npc, result: str):
        """Process a dialog choice - trigger game mechanics AND generate memories."""
        if not npc:
            return

        name = npc.name
        cc = getattr(npc, 'char_class', npc.profession)

        # === HEALING ===
        if result == "heal_done":
            heal = 20 + getattr(npc, 'level', 1) * 3
            self.player.heal(heal)
            self.notifications.add(f"{name} healed you for {heal} HP!", 3.0, GREEN)
            npc.add_memory("social", f"Healed the player's wounds", 3)
            npc.player_relationship = min(100, npc.player_relationship + 5)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 10)

        elif result == "blessing":
            self.player.heal(10)
            self.notifications.add(f"{name} blessed you! +10 HP", 2.0, GREEN)
            npc.add_memory("social", "Blessed the player with divine protection", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)

        # === LEARNING ===
        elif result == "learn_done":
            if hasattr(npc, 'npc_skills'):
                top = sorted(npc.npc_skills.items(), key=lambda x: -x[1])
                if top:
                    skill = top[0][0]
                    self.player.gain_skill_xp(skill, 2.0)
                    self.notifications.add(f"{name} taught you about {skill}!", 3.0, GREEN)
                    npc.add_memory("teaching", f"Taught the player about {skill}", 3)
                    npc.player_relationship = min(100, npc.player_relationship + 5)
                    from game.systems.skills import gain_skill_xp
                    gain_skill_xp(npc, "leadership", 0.5)

        # === QUEST ===
        elif result == "accept_quest":
            # If NPC has no formal quest, generate one from their goals/profession
            if not npc.quest:
                self.quest_sys.generate_quest_for_npc(npc)
                npc.regenerate_dialog()
            if npc.quest and not npc.quest.turned_in:
                already_have = npc.quest.title in [q.title for q in self.quest_sys.active_quests]
                if already_have:
                    self.notifications.add("You already have this quest.", 2.0, GRAY)
                elif self.quest_sys.accept_quest(npc.quest):
                    self.notifications.add(f"New quest: {npc.quest.title}", 4.0, YELLOW)
                    npc.add_memory("quest", "The player accepted a task from me", 3)
                    npc.player_relationship = min(100, npc.player_relationship + 3)
                else:
                    self.notifications.add("Quest log full! (max 10)", 3.0, RED)
            else:
                self.notifications.add("Quest accepted!", 3.0, YELLOW)
                npc.add_memory("quest", "The player accepted a task from me", 3)
                npc.player_relationship = min(100, npc.player_relationship + 3)

        elif result == "quest_complete":
            # Player claims to have finished a quest
            if npc.quest and npc.quest.completed and not npc.quest.turned_in:
                turn_in_result = self.quest_sys.turn_in_quest(npc.quest, self.player)
                if turn_in_result:
                    self.notifications.add(turn_in_result, 4.0, GREEN)
                    npc.has_quest_marker = False
                    npc.add_memory("quest", "The player completed my task! Grateful.", 5)
                    npc.player_relationship = min(100, npc.player_relationship + 10)
            else:
                self.notifications.add("You haven't completed this task yet.", 3.0, ORANGE)

        elif result == "quest_reward":
            npc.add_memory("social", "The player asked about rewards. Practical type.", 1)

        # === RECRUITMENT ===
        elif result == "recruit_offer":
            # Actually attempt to recruit the NPC
            recruited = False
            if hasattr(self, 'party'):
                recruited = self.party.try_recruit(npc)
            if recruited:
                self.notifications.add(f"{name} joins your party!", 3.0, GREEN)
                npc.add_memory("social", "I joined the player's party!", 5)
                npc.player_relationship = min(100, npc.player_relationship + 10)
            else:
                npc.add_memory("social", "The player asked me to join their party", 3)
                npc.player_relationship = min(100, npc.player_relationship + 2)
                if hasattr(self, 'party') and len(self.party.companions) >= self.party.max_companions:
                    self.notifications.add("Party is full! Dismiss someone first.", 3.0, ORANGE)
                elif npc.player_relationship < 15:
                    self.notifications.add(f"{name} doesn't trust you enough yet. (need 15+ relationship)", 3.0, ORANGE)
                else:
                    self.notifications.add(f"Press R near {name} to recruit.", 2.0, YELLOW)

        # === ABOUT SELF / PERSONAL ===
        elif result == "about_self":
            npc.add_memory("social", "Had a personal conversation with the player", 2)
            npc.player_relationship = min(100, npc.player_relationship + 2)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 8)

        elif result == "goals_detail":
            npc.add_memory("social", "Shared my goals and dreams with the player", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 5)

        elif result == "backstory" or result == "backstory_deep":
            npc.add_memory("social", "Told the player my life story. Felt good to share.", 3)
            npc.player_relationship = min(100, npc.player_relationship + 5)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 15)

        elif result == "friends_talk":
            npc.add_memory("social", "Talked about my friends with the player", 1)
            npc.player_relationship = min(100, npc.player_relationship + 2)

        elif result == "enemies_talk" or result == "enemy_story":
            npc.add_memory("social", "Confided about my enemies to the player", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)

        # === NEWS / INFORMATION ===
        elif result == "local_news" or result == "more_news":
            npc.add_memory("social", "Shared local news with the player", 1)
            npc.player_relationship = min(100, npc.player_relationship + 1)
            # Player learns what NPC knows
            for info in npc.known_info[-3:]:
                if hasattr(self, 'simulation') and hasattr(self.simulation, 'info'):
                    self.simulation.info.player_witnesses(
                        f"{name} told you: {info}", "gossip", 1, self.time_sys.day)

        elif result == "guard_report":
            npc.add_memory("duty", "Gave the player a security briefing", 2)
            npc.player_relationship = min(100, npc.player_relationship + 2)

        elif result == "kingdom_report":
            npc.add_memory("political", "Discussed the state of the kingdom with the player", 3)
            npc.player_relationship = min(100, npc.player_relationship + 3)

        # === TRADE / BARTER ===
        elif result == "barter" or result == "shop":
            npc.add_memory("trade", "The player wanted to trade with me", 1)
            # Shop UI is opened by handle_dialog_input when next_key == "shop"
            # No need to open it here (would be redundant)

        # === CLASS-SPECIFIC ===
        elif result == "bard_perform":
            npc.add_memory("social", "Performed a song for the player. Good audience!", 2)
            npc.player_relationship = min(100, npc.player_relationship + 4)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 15)
            from game.systems.skills import gain_skill_xp
            gain_skill_xp(npc, "trading", 0.5)  # performing builds charisma

        elif result == "bard_legend" or result == "great_war_story":
            npc.add_memory("social", "Told the player ancient legends", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)
            self.player.gain_skill_xp("history", 1.0)

        elif result == "magic_talk" or result == "ruin_lore":
            npc.add_memory("social", "Discussed magic and arcane theory with the player", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)

        elif result == "rogue_deal" or result == "rogue_detail" or result == "rogue_map":
            npc.add_memory("social", "Shared a secret opportunity with the player", 3)
            npc.player_relationship = min(100, npc.player_relationship + 4)

        elif result == "monk_wisdom" or result == "monk_training":
            npc.add_memory("teaching", "Shared wisdom with the player", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)

        elif result == "warlock_patron" or result == "warlock_power" or result == "warlock_cost":
            npc.add_memory("social", "Confided about my patron to the player. Risky.", 3)
            npc.player_relationship = min(100, npc.player_relationship + 5)

        elif result == "consciousness" or result == "consciousness_deep":
            npc.add_memory("philosophical", "Discussed the nature of reality with the player", 4)
            npc.player_relationship = min(100, npc.player_relationship + 5)
            npc.awareness_points += 1.0

        elif result == "help_with_goal":
            npc.add_memory("social", "The player offered to help me with my goals!", 4)
            npc.player_relationship = min(100, npc.player_relationship + 8)

        elif result == "offer_help_threat":
            npc.add_memory("social", "The player volunteered to help with local threats!", 3)
            npc.player_relationship = min(100, npc.player_relationship + 5)

        elif result == "kingdom_service":
            npc.add_memory("political", "The player offered service to the crown", 3)
            npc.player_relationship = min(100, npc.player_relationship + 5)

        elif result == "intro_friends":
            npc.add_memory("social", "Introduced the player to my friends", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)
            # Spread good reputation to friends
            for friend_name in getattr(npc, 'friends', [])[:3]:
                for other in self.world_mgr.npcs:
                    if other.name == friend_name and other.alive:
                        other.player_relationship = min(100, other.player_relationship + 3)
                        other.add_memory("social", f"{npc.name} introduced the player to me. Seems trustworthy.", 2)
                        break

        # === NEGATIVE OUTCOMES ===
        elif result == "insult":
            npc.add_memory("conflict", "The player insulted me!", 4)
            npc.player_relationship = max(-100, npc.player_relationship - 15)
            npc.mood = max(-1.0, getattr(npc, 'mood', 0) - 0.3)
            self.notifications.add(f"{name} is offended!", 3.0, RED)
            # Spread to friends
            for fname in getattr(npc, 'friends', [])[:3]:
                for other in self.world_mgr.npcs:
                    if other.name == fname and other.alive:
                        other.player_relationship = max(-100, other.player_relationship - 5)
                        other.add_memory("social", f"{name} told me the player was rude to them", 2)
                        break

        elif result == "threaten":
            npc.add_memory("conflict", "The player threatened me!", 5)
            npc.player_relationship = max(-100, npc.player_relationship - 25)
            npc.mood = max(-1.0, getattr(npc, 'mood', 0) - 0.5)
            self.notifications.add(f"{name} is afraid and angry!", 3.0, RED)
            if npc.bravery > 0.6:
                npc.combat_target = self.player
                npc.current_action = "fighting"
                npc.state = "fighting"
                self.notifications.add(f"{name} attacks you!", 3.0, RED)
            else:
                npc.flee_from(self.player.x, self.player.y)
            # All nearby NPCs turn hostile
            for other in self.world_mgr.npcs:
                if other is npc or not other.alive:
                    continue
                if self.player.dist_to(other) < 12:
                    other.player_relationship = max(-100, other.player_relationship - 10)
                    other.add_memory("witness", "Saw the player threaten someone!", 3)

        elif result == "demand_gold":
            if npc.npc_gold > 5 and npc.bravery < 0.4:
                # Coward pays up
                amount = min(10, int(npc.npc_gold * 0.5))
                npc.npc_gold -= amount
                self.player.gold += amount
                npc.add_memory("conflict", f"The player demanded {amount} gold from me. I paid out of fear.", 5)
                npc.player_relationship = max(-100, npc.player_relationship - 20)
                self.notifications.add(f"{name} reluctantly gives you {amount} gold.", 3.0, ORANGE)
            else:
                npc.add_memory("conflict", "The player tried to extort me!", 5)
                npc.player_relationship = max(-100, npc.player_relationship - 20)
                self.notifications.add(f"{name} refuses and is furious!", 3.0, RED)
                if npc.bravery > 0.5:
                    npc.combat_target = self.player
                    npc.current_action = "fighting"
                    self.notifications.add(f"{name} attacks!", 2.0, RED)

        elif result == "lie":
            # Player lied - NPC may detect it based on wisdom
            wisdom = npc.attributes.get("wisdom", 5)
            detected = random.random() < (wisdom * 0.08 + 0.2)
            if detected:
                npc.add_memory("conflict", "The player tried to deceive me. I saw through it.", 4)
                npc.player_relationship = max(-100, npc.player_relationship - 12)
                self.notifications.add(f"{name} sees through your deception!", 3.0, RED)
            else:
                npc.add_memory("social", "Spoke with the player. Seemed sincere.", 1)
                npc.player_relationship = min(100, npc.player_relationship + 1)

        elif result == "refuse_help":
            npc.add_memory("social", "Asked the player for help but they refused", 2)
            npc.player_relationship = max(-100, npc.player_relationship - 5)
            npc.mood = max(-1.0, getattr(npc, 'mood', 0) - 0.1)

        elif result == "mock_beliefs":
            npc.add_memory("conflict", "The player mocked my beliefs! Deeply hurtful.", 5)
            npc.player_relationship = max(-100, npc.player_relationship - 20)
            npc.mood = max(-1.0, getattr(npc, 'mood', 0) - 0.4)
            self.notifications.add(f"{name} is deeply offended!", 3.0, RED)

        elif result == "reject_quest":
            title = getattr(npc, 'title', 'commoner')
            is_ruler = getattr(npc, 'is_ruler', False)
            rel_penalty = -3
            emotion_hit = 0.1

            if is_ruler or title in ('ruler', 'king', 'queen', 'lord', 'duke'):
                # Refusing a ruler is a serious insult
                rel_penalty = -15
                emotion_hit = 0.4
                npc.add_memory("political",
                    "The player refused a direct request from me. Insolent!", 5)
                self.notifications.add(
                    f"{name} is displeased by your refusal! (-15 reputation)", 4.0, RED)
                # Ruler tells guards to watch you
                for other in self.world_mgr.npcs:
                    if other is npc or not other.alive:
                        continue
                    other_title = getattr(other, 'title', '')
                    if other_title in ('guard', 'knight', 'captain') and other.dist_to(npc) < 30:
                        other.player_relationship = max(-100,
                            other.player_relationship - 8)
                        other.add_memory("duty",
                            f"The ruler {name} was angered by the player. Keep watch.", 3)
            elif title in ('guard', 'captain', 'knight'):
                rel_penalty = -8
                emotion_hit = 0.25
                npc.add_memory("duty",
                    "The player refused to help with security matters", 3)
                self.notifications.add(
                    f"{name} notes your refusal. Guards will remember.", 3.0, ORANGE)
            elif npc.player_relationship > 30:
                # Rejecting a friend hurts more
                rel_penalty = -8
                emotion_hit = 0.3
                npc.add_memory("social",
                    "I asked my friend for help and they refused. Disappointing.", 4)
                self.notifications.add(
                    f"{name} is hurt by your refusal.", 3.0, ORANGE)
            else:
                npc.add_memory("social",
                    "The player turned down my request for help", 2)

            npc.player_relationship = max(-100, npc.player_relationship + rel_penalty)

            # Emotional reaction
            es = getattr(npc, 'emotion_state', None)
            if es and hasattr(es, 'primary'):
                if is_ruler or title in ('guard', 'knight', 'captain'):
                    es.primary["anger"] = min(1.0,
                        es.primary.get("anger", 0) + emotion_hit)
                else:
                    es.primary["sadness"] = min(1.0,
                        es.primary.get("sadness", 0) + emotion_hit)

        elif result == "steal_attempt":
            # Try to steal from NPC during conversation
            dex = self.player.ability_scores.get("dexterity", 10)
            from game.data.dnd import ability_modifier
            roll = random.randint(1, 20) + ability_modifier(dex)
            perception = npc.attributes.get("perception", 5)
            dc = 10 + perception

            if roll >= dc:
                # Steal succeeded
                if npc.npc_inventory:
                    stolen = npc.npc_inventory.pop(random.randint(0, len(npc.npc_inventory) - 1))
                    self.player.add_item(stolen)
                    self.notifications.add(f"Stole {stolen.name} from {name}!", 3.0, ORANGE)
                    self.player.gain_skill_xp("pickpocketing", 1.0)
                else:
                    self.notifications.add("Nothing to steal.", 2.0, GRAY)
            else:
                # Caught!
                npc.add_memory("conflict", "The player tried to steal from me!", 5)
                npc.player_relationship = max(-100, npc.player_relationship - 30)
                self.notifications.add(f"{name} caught you stealing! ({roll} vs DC {dc})", 3.0, RED)
                if npc.bravery > 0.3:
                    npc.combat_target = self.player
                    npc.current_action = "fighting"
                    self.notifications.add(f"{name} attacks!", 2.0, RED)
                # Alert guards
                for other in self.world_mgr.npcs:
                    if other is npc or not other.alive:
                        continue
                    if self.player.dist_to(other) < 15:
                        title = getattr(other, 'title', '')
                        if title in ('guard', 'knight'):
                            other.add_memory("crime", f"{name} reported the player tried to steal!", 4)
                            other.player_relationship = max(-100, other.player_relationship - 15)
                            other.combat_target = self.player
                            other.current_action = "fighting"

        # === PLAYER-ASSIGNED TASKS ===
        elif result in ("task_kill", "task_fetch", "task_scout",
                         "task_guard", "task_deliver"):
            # Check willingness
            if npc.player_relationship < 10 and result != "task_bribe_50":
                self.notifications.add(f"{name} doesn't trust you enough.", 3.0, ORANGE)
            else:
                task_kind = result.replace("task_", "")
                task_desc, target_count = {
                    "kill":    ("Hunt creatures nearby", 3),
                    "fetch":   ("Gather supplies", 5),
                    "scout":   ("Scout the surrounding area", 1),
                    "guard":   ("Guard this area", 1),
                    "deliver": ("Deliver items", 1),
                }.get(task_kind, ("Do a task", 1))
                npc.player_task = {
                    "kind": task_kind,
                    "target": task_kind,
                    "progress": 0,
                    "target_count": target_count,
                    "description": task_desc,
                    "reward_gold": 0,
                }
                npc.player_task_timer = 0.0
                npc.current_goal = f"player_task_{task_kind}"
                npc.add_memory("quest",
                    f"The player asked me to {task_desc.lower()}. I accepted.", 3)
                self.notifications.add(
                    f"{name} accepts your task: {task_desc}", 3.0, GREEN)
                npc.player_relationship = min(100, npc.player_relationship + 2)

        elif result == "task_bribe_50" or result == "task_bribe_100":
            amount = 50 if result == "task_bribe_50" else 100
            if self.player.gold >= amount:
                self.player.gold -= amount
                npc.npc_gold += amount
                npc.player_relationship = min(100, npc.player_relationship + 5)
                npc.add_memory("trade",
                    f"The player paid me {amount} gold for a job", 3)
                self.notifications.add(f"Paid {name} {amount} gold.", 2.0, YELLOW)
            else:
                self.notifications.add("Not enough gold!", 2.0, RED)

        elif result == "task_collect":
            # Player collects completed task results
            if npc.player_task and npc.player_task.get("progress", 0) >= \
                    npc.player_task.get("target_count", 1):
                task = npc.player_task
                reward = task.get("reward_gold", 0)
                kind = task.get("kind", "")
                # Give player the gathered items
                if kind == "fetch":
                    from game.core.items import make_item
                    gather_items = ["Bread", "Herbs", "Wood", "Stone", "Apple"]
                    for i in range(min(3, task["target_count"])):
                        item = make_item(random.choice(gather_items))
                        self.player.add_item(item)
                    self.notifications.add(
                        f"{name} hands over gathered supplies!", 3.0, GREEN)
                elif kind == "scout":
                    # Add knowledge to player
                    for info in npc.known_info[-3:]:
                        if hasattr(self, 'simulation') and hasattr(self.simulation, 'info'):
                            self.simulation.info.player_witnesses(
                                f"{name} scouted: {info}", "scout", 2,
                                self.time_sys.day)
                    self.notifications.add(
                        f"{name} reports scouting findings!", 3.0, GREEN)
                elif kind == "kill":
                    xp = task["target_count"] * 10
                    self.player.gain_xp(xp)
                    self.notifications.add(
                        f"{name} cleared {task['target_count']} creatures! +{xp} XP", 3.0, GREEN)

                npc.player_task = None
                npc.current_goal = ""
                npc.add_memory("quest",
                    "Completed the task the player gave me. Feels good.", 4)
                npc.player_relationship = min(100, npc.player_relationship + 5)
                self.notifications.add(
                    f"Task completed by {name}!", 3.0, GREEN)

        elif result == "task_cancel":
            if npc.player_task:
                npc.player_task = None
                npc.current_goal = ""
                npc.add_memory("social",
                    "The player cancelled my task. Waste of time.", 2)
                npc.player_relationship = max(-100, npc.player_relationship - 3)

        elif result == "task_assign":
            # Just navigating to the menu — no action needed
            pass

        elif result == "task_refuse":
            npc.add_memory("social",
                "I turned down a task from the player. Not my thing.", 1)

        # === EMOTION / NEEDS / GOSSIP / DEEP CONVERSATIONS ===
        elif result == "emotion_talk" or result == "emotion_detail":
            npc.add_memory("social", "The player asked about my feelings. Thoughtful.", 3)
            npc.player_relationship = min(100, npc.player_relationship + 4)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 15)
            # Emotional catharsis - reduce negative emotions
            es = getattr(npc, 'emotion_state', None)
            if es and hasattr(es, 'primary'):
                for neg in ("sadness", "anger", "fear"):
                    if es.primary.get(neg, 0) > 0.3:
                        es.primary[neg] = max(0, es.primary[neg] - 0.15)

        elif result == "emotion_help":
            npc.add_memory("social", "The player offered to help with my troubles", 4)
            npc.player_relationship = min(100, npc.player_relationship + 6)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 20)

        elif result == "needs_hunger":
            npc.add_memory("social", "The player noticed I was hungry and showed concern", 3)
            npc.player_relationship = min(100, npc.player_relationship + 3)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 10)

        elif result == "needs_social":
            npc.add_memory("social", "The player stopped to talk when I was lonely", 4)
            npc.player_relationship = min(100, npc.player_relationship + 5)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 25)

        elif result == "gossip" or result == "gossip_more":
            npc.add_memory("social", "Shared gossip with the player", 1)
            npc.player_relationship = min(100, npc.player_relationship + 2)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 8)
            # Player learns gossip as known_info
            if hasattr(self, 'simulation') and hasattr(self.simulation, 'info'):
                for info in npc.known_info[-2:]:
                    self.simulation.info.player_witnesses(
                        f"{name} gossiped: {info}", "gossip", 1, self.time_sys.day)

        elif result == "deep_talk" or result == "deep_bond" or result == "deep_empathy":
            npc.add_memory("social", "Had a deep personal conversation with the player. Meaningful.", 5)
            npc.player_relationship = min(100, npc.player_relationship + 6)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 20)
            # Deep conversations may trigger emotional bonds
            es = getattr(npc, 'emotion_state', None)
            if es and hasattr(es, 'bonds'):
                es.bonds["player"] = {"emotion": "trust", "intensity": min(1.0,
                    es.bonds.get("player", {}).get("intensity", 0) + 0.2),
                    "cause": "meaningful conversation"}

        # === GIFT (handled by gift panel, but process the result key too) ===
        elif result == "gift":
            pass  # Gift panel handles this via handle_gift_input

        # === GOODBYE ===
        elif result == "goodbye":
            if npc.player_relationship > 20:
                npc.add_memory("social", "Had a pleasant conversation with the player", 1)
            elif npc.player_relationship < -10:
                npc.add_memory("social", "The player left. Good riddance.", 1)

