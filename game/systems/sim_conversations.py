"""Simulation conversations — NPC-NPC talking, trading, teaching."""

import random
import math
import time
from typing import List, Optional
from game.core.npc import NPC
from game.core.items import Item, make_item, FOOD_ITEMS
from game.ai.prompts import share_gossip, pick_contextual_topic
from game.settings import *


class Conversation:
    """An active conversation between two NPCs."""
    def __init__(self, npc1: NPC, npc2: NPC):
        self.npc1 = npc1
        self.npc2 = npc2
        self.timer = random.uniform(3.0, 6.0)
        self.started = time.time()
        self.info_exchanged: List[str] = []


class SimConversationsMixin:
    """Conversation-related simulation methods."""

    def _start_talk(self, npc: NPC, target_name: str):
        other = self._find_npc(target_name)
        if not other or not other.alive:
            npc.current_action = ""
            return
        d = npc.dist_to(other)
        if d > NPC_CONVERSATION_RANGE:
            npc.target_x, npc.target_y = other.x, other.y
            npc.state = "walking"
            npc.current_action = "moving"
            npc.state_timer = 10.0
            return

        conv = Conversation(npc, other)
        self.conversations.append(conv)
        npc.current_action = "talking"
        other.current_action = "talking"
        npc.state = "socializing"
        other.state = "socializing"
        npc.needs["social"] = min(100, npc.needs["social"] + 15)
        other.needs["social"] = min(100, other.needs["social"] + 10)

        # Generate a contextual conversation topic for the memory
        topic = pick_contextual_topic(
            npc, world=self.world,
            world_effects=getattr(self, 'world_effects', None),
            governance=getattr(self, 'governance', None),
            time_sys=self.time_sys,
            event_log=self.event_log,
            economy=getattr(self, 'economy', None),
        )
        npc.add_memory("social", f"Talked with {other.name}: \"{topic}\"", 2)
        other.add_memory("social", f"Talked with {npc.name}", 2)

        # Share gossip — NPCs exchange world knowledge and event memories
        share_gossip(npc, other, self.event_log,
                     current_day=self.time_sys.day)

        # Relationship boost
        npc.npc_relationships[other.name] = npc.npc_relationships.get(other.name, 0) + 3
        other.npc_relationships[npc.name] = other.npc_relationships.get(npc.name, 0) + 2

    def _start_trade(self, npc: NPC, target_name: str):
        other = self._find_npc(target_name)
        if not other or not other.alive:
            npc.current_action = ""
            return
        # Simple trade: NPC sells food/drink to other if other needs it
        if other.needs["hunger"] < 40 and npc.has_food() and other.npc_gold >= 3:
            for item in list(npc.npc_inventory):
                if item.name in FOOD_ITEMS:
                    npc.npc_remove_item(item.name)
                    other.npc_add_item(make_item(item.name))
                    other.npc_gold -= 3
                    npc.npc_gold += 3
                    npc.add_memory("trade", f"Sold {item.name} to {other.name}", 2)
                    other.add_memory("trade", f"Bought {item.name} from {npc.name}", 2)
                    self.event_log.append(f"{npc.name} traded {item.name} to {other.name}")
                    break
        npc.current_action = ""
        npc.needs["social"] = min(100, npc.needs["social"] + 8)

    def _start_persuade(self, npc: NPC, target_request: str):
        # Parse "name: request"
        parts = target_request.split(":", 1)
        target_name = parts[0].strip()
        request = parts[1].strip() if len(parts) > 1 else "help me"

        other = self._find_npc(target_name)
        if not other or not other.alive:
            npc.current_action = ""
            return

        # Success chance based on charisma vs intelligence and relationship
        charisma = npc.attributes.get("charisma", 5)
        intel = other.attributes.get("intelligence", 5)
        rel = npc.npc_relationships.get(other.name, 0)
        chance = 0.3 + (charisma - intel) * 0.05 + rel * 0.003
        success = random.random() < max(0.1, min(0.9, chance))

        if success:
            other.current_goal = request
            other.add_memory("persuasion", f"{npc.name} persuaded me to: {request}", 3)
            npc.add_memory("persuasion", f"Convinced {other.name} to {request}", 3)
            self.event_log.append(f"{npc.name} persuaded {other.name} to {request}")
        else:
            npc.add_memory("persuasion", f"Failed to convince {other.name}", 1)
            other.npc_relationships[npc.name] = other.npc_relationships.get(npc.name, 0) - 5
        npc.current_action = ""


    def _update_conversations(self, dt: float):
        remaining = []
        for conv in self.conversations:
            conv.timer -= dt
            if conv.timer <= 0:
                # Exchange information
                self._spread_information(conv.npc1, conv.npc2)
                conv.npc1.current_action = ""
                conv.npc2.current_action = ""
                conv.npc1.state = "idle"
                conv.npc2.state = "idle"
            else:
                remaining.append(conv)
        self.conversations = remaining

    def _spread_information(self, npc1: NPC, npc2: NPC):
        """Rich NPC-NPC conversation: exchange info, trade, teach, help, deepen bonds."""
        from game.systems.emotions import trigger_emotion
        friends1 = getattr(npc1, 'friends', [])
        friends2 = getattr(npc2, 'friends', [])
        enemies1 = getattr(npc1, 'enemies', [])
        enemies2 = getattr(npc2, 'enemies', [])
        gt = self.time_sys.time
        rel12 = npc1.npc_relationships.get(npc2.name, 0)
        rel21 = npc2.npc_relationships.get(npc1.name, 0)

        # --- Emotional response to partner ---
        if npc2.name in friends1:
            trigger_emotion(npc1, "saw_friend", intensity=0.5,
                            target=npc2.name, cause=f"talked with friend {npc2.name}",
                            game_time=gt)
        if npc1.name in friends2:
            trigger_emotion(npc2, "saw_friend", intensity=0.5,
                            target=npc1.name, cause=f"talked with friend {npc1.name}",
                            game_time=gt)
        if npc2.name in enemies1:
            trigger_emotion(npc1, "saw_enemy", intensity=0.5,
                            target=npc2.name, cause=f"encountered enemy {npc2.name}",
                            game_time=gt)
        if npc1.name in enemies2:
            trigger_emotion(npc2, "saw_enemy", intensity=0.5,
                            target=npc1.name, cause=f"encountered enemy {npc1.name}",
                            game_time=gt)

        # --- Share known_info (gossip) ---
        for info in npc1.known_info[-5:]:
            if info not in npc2.known_info:
                if random.random() < 0.5 + npc1.attributes.get("charisma", 5) * 0.05:
                    npc2.known_info.append(info)
                    if len(npc2.known_info) > 20:
                        npc2.known_info = npc2.known_info[-20:]
        for info in npc2.known_info[-5:]:
            if info not in npc1.known_info:
                if random.random() < 0.5 + npc2.attributes.get("charisma", 5) * 0.05:
                    npc1.known_info.append(info)
                    if len(npc1.known_info) > 20:
                        npc1.known_info = npc1.known_info[-20:]

        share_gossip(npc1, npc2, self.event_log,
                     current_day=self.time_sys.day)

        # --- Needs-driven help: share food with hungry friend ---
        if rel12 > 10 and npc2.needs.get("hunger", 50) < 30 and npc1.has_food():
            for item in list(npc1.npc_inventory):
                if item.name in FOOD_ITEMS:
                    npc1.npc_remove_item(item.name)
                    npc2.npc_add_item(make_item(item.name))
                    npc2.needs["hunger"] = min(100, npc2.needs["hunger"] + 25)
                    npc1.add_memory("social", f"Gave food to hungry {npc2.name}", 3)
                    npc2.add_memory("social", f"{npc1.name} shared food when I was starving", 4)
                    npc2.npc_relationships[npc1.name] = min(100, rel21 + 8)
                    trigger_emotion(npc2, "gift_received", intensity=0.5,
                                    target=npc1.name, cause=f"{npc1.name} gave me food",
                                    game_time=gt)
                    self.event_log.append(f"{npc1.name} shared food with hungry {npc2.name}")
                    break
        elif rel21 > 10 and npc1.needs.get("hunger", 50) < 30 and npc2.has_food():
            for item in list(npc2.npc_inventory):
                if item.name in FOOD_ITEMS:
                    npc2.npc_remove_item(item.name)
                    npc1.npc_add_item(make_item(item.name))
                    npc1.needs["hunger"] = min(100, npc1.needs["hunger"] + 25)
                    npc2.add_memory("social", f"Gave food to hungry {npc1.name}", 3)
                    npc1.add_memory("social", f"{npc2.name} shared food when I was starving", 4)
                    npc1.npc_relationships[npc2.name] = min(100, rel12 + 8)
                    trigger_emotion(npc1, "gift_received", intensity=0.5,
                                    target=npc2.name, cause=f"{npc2.name} gave me food",
                                    game_time=gt)
                    self.event_log.append(f"{npc2.name} shared food with hungry {npc1.name}")
                    break

        # --- Skill teaching (friends teach each other) ---
        if rel12 > 15 and random.random() < 0.08:
            self._npc_teach(npc1, npc2, gt)
        elif rel21 > 15 and random.random() < 0.08:
            self._npc_teach(npc2, npc1, gt)

        # --- Item trading (barter based on needs) ---
        if random.random() < 0.05:
            self._npc_barter(npc1, npc2, gt)

        # --- Emotional support (comfort sad friends) ---
        es2 = getattr(npc2, 'emotion_state', None)
        es1 = getattr(npc1, 'emotion_state', None)
        if es2 and rel12 > 10:
            sadness = es2.primary.get("sadness", 0) if hasattr(es2, 'primary') else 0
            if sadness > 0.4:
                es2.primary["sadness"] = max(0, sadness - 0.15)
                npc1.add_memory("social", f"Comforted {npc2.name} who was feeling down", 3)
                npc2.add_memory("social", f"{npc1.name} comforted me when I was sad", 4)
                npc2.npc_relationships[npc1.name] = min(100, rel21 + 5)
                npc2.needs["social"] = min(100, npc2.needs.get("social", 50) + 15)
        if es1 and rel21 > 10:
            sadness = es1.primary.get("sadness", 0) if hasattr(es1, 'primary') else 0
            if sadness > 0.4:
                es1.primary["sadness"] = max(0, sadness - 0.15)
                npc2.add_memory("social", f"Comforted {npc1.name} who was feeling down", 3)
                npc1.add_memory("social", f"{npc2.name} comforted me when I was sad", 4)
                npc1.npc_relationships[npc2.name] = min(100, rel12 + 5)
                npc1.needs["social"] = min(100, npc1.needs.get("social", 50) + 15)

        # --- Deep conversation (high relationship builds bonds) ---
        if rel12 > 40 and rel21 > 40 and random.random() < 0.1:
            topic = random.choice([
                "their dreams and fears",
                "life's meaning",
                "their shared experiences",
                "what they want for the future",
                "their families and loved ones",
            ])
            npc1.add_memory("social", f"Had a deep talk with {npc2.name} about {topic}", 4)
            npc2.add_memory("social", f"Had a deep talk with {npc1.name} about {topic}", 4)
            npc1.npc_relationships[npc2.name] = min(100, rel12 + 5)
            npc2.npc_relationships[npc1.name] = min(100, rel21 + 5)
            # Create emotional bond
            if es1 and hasattr(es1, 'bonds'):
                es1.bonds[npc2.name] = {"emotion": "trust",
                    "intensity": min(1.0, es1.bonds.get(npc2.name, {}).get("intensity", 0) + 0.1),
                    "cause": f"deep conversation about {topic}"}
            if es2 and hasattr(es2, 'bonds'):
                es2.bonds[npc1.name] = {"emotion": "trust",
                    "intensity": min(1.0, es2.bonds.get(npc1.name, {}).get("intensity", 0) + 0.1),
                    "cause": f"deep conversation about {topic}"}

        # --- Warning about dangers (share threat knowledge) ---
        dangers = [k for k in npc1.known_info if any(w in k.lower() for w in
                   ["danger", "monster", "bandit", "wolf", "attack", "raid", "killed"])]
        if dangers and rel12 > 5 and random.random() < 0.3:
            warning = random.choice(dangers)
            if warning not in npc2.known_info:
                npc2.known_info.append(warning)
                npc1.add_memory("social", f"Warned {npc2.name} about dangers", 2)
                npc2.add_memory("social", f"{npc1.name} warned me: {warning[:40]}", 3)
                trigger_emotion(npc2, "heard_threat", intensity=0.3,
                                cause=warning[:40], game_time=gt)

    def _npc_teach(self, teacher: NPC, student: NPC, gt: float):
        """Teacher NPC teaches their best skill to student NPC."""
        t_skills = getattr(teacher, 'npc_skills', {})
        s_skills = getattr(student, 'npc_skills', {})
        if not t_skills:
            return
        best = max(t_skills, key=t_skills.get)
        t_level = t_skills[best]
        s_level = s_skills.get(best, 0)
        if t_level <= s_level:
            return
        # Teach
        from game.systems.skills import gain_skill_xp
        gain_skill_xp(student, best, 1.5)
        gain_skill_xp(teacher, "leadership", 0.3)
        teacher.add_memory("teaching", f"Taught {student.name} about {best}", 3)
        student.add_memory("learning", f"{teacher.name} taught me about {best}", 3)
        rel = student.npc_relationships.get(teacher.name, 0)
        student.npc_relationships[teacher.name] = min(100, rel + 5)
        self.event_log.append(f"{teacher.name} taught {student.name} about {best}")

    def _npc_barter(self, npc1: NPC, npc2: NPC, gt: float):
        """NPCs trade items based on their needs and what they have."""
        from game.core.items import make_item
        inv1 = getattr(npc1, 'npc_inventory', [])
        inv2 = getattr(npc2, 'npc_inventory', [])

        # NPC1 needs something NPC2 has
        for item in list(inv2):
            need_match = False
            # Hungry NPC wants food
            if item.name in FOOD_ITEMS and npc1.needs.get("hunger", 50) < 40:
                need_match = True
            # Sick/hurt NPC wants healing items
            elif item.name in ("Health Potion", "Herbs", "Antidote") and npc1.hp < npc1.max_hp * 0.6:
                need_match = True
            # Warrior wants weapons/armor
            elif getattr(item, 'damage', 0) > 0 and getattr(npc1, 'char_class', '') in (
                    "Fighter", "Paladin", "Barbarian", "Ranger"):
                equipped = getattr(npc1, 'weapon', None)
                if not equipped or (hasattr(equipped, 'damage') and item.damage > equipped.damage):
                    need_match = True

            if need_match and npc1.npc_gold >= item.value:
                price = max(1, int(item.value * 0.7))
                if npc1.npc_gold >= price:
                    npc2.npc_remove_item(item.name)
                    npc1.npc_add_item(make_item(item.name))
                    npc1.npc_gold -= price
                    npc2.npc_gold += price
                    npc1.add_memory("trade", f"Bought {item.name} from {npc2.name} for {price}g", 2)
                    npc2.add_memory("trade", f"Sold {item.name} to {npc1.name} for {price}g", 2)
                    self.event_log.append(f"{npc1.name} bought {item.name} from {npc2.name}")
                    if item.name in FOOD_ITEMS:
                        npc1.needs["hunger"] = min(100, npc1.needs["hunger"] + 20)
                    elif getattr(item, 'heal', 0) > 0:
                        npc1.heal(item.heal)
                    return  # one trade per conversation

    # ---- WORLD EVENTS ----

