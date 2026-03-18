"""
Rich dialog trees for NPC conversations.

Each class/race combination gets unique conversation paths.
Dialogs reference actual NPC state: goals, skills, inventory, memories,
relationships, emotions, needs, weather, time of day, and ongoing gameplay.
Every dialog option either provides information or triggers a game mechanic.
"""

import random
from typing import Dict, List, Tuple

# Helper functions split into dialog_helpers.py for maintainability
from game.core.dialog_helpers import (
    # Context builders
    _body_language, _needs_comment, _profession_context, _memory_greeting,
    # Greeting and dialog builders
    _build_greeting, _build_about_self, _build_goals_text,
    _build_obstacle_text, _build_friends_text, _build_enemy_story,
    _build_generic_backstory, _build_deep_backstory,
    _build_local_news, _build_more_news, _build_recruit_response,
    _build_magic_talk, _build_heal_response, _build_bard_performance,
    _build_rogue_deal, _build_guard_report, _build_kingdom_report,
    _build_personal_quest, _build_quest_dialog, _build_help_dialog,
    _skill_flavor, _build_teach_response, _build_lesson_text,
    _build_threat_response, _build_apology_response, _get_consciousness_dialog,
    # Emotion dialog
    _build_emotion_dialog, _build_emotion_detail, _build_emotion_help_response,
    _build_deep_personal,
    # Task dialog
    _build_task_accept, _build_task_refuse, _build_task_options,
    _build_task_kill_dialog, _build_task_fetch_dialog, _build_task_scout_dialog,
    _build_task_guard_dialog, _build_task_deliver_dialog,
    _build_goodbye,
)


class DialogLine:
    """A single dialog option or NPC line."""
    def __init__(self, text: str, responses: List[Tuple[str, str]] = None):
        self.text = text
        self.responses = responses or []


# ================================================================
# CONTEXT GATHERING — collects all state for dialog generation
# ================================================================

def _gather_context(npc) -> dict:
    """Gather all relevant NPC state for dialog generation."""
    cc = getattr(npc, 'char_class', npc.profession)
    ctx = {
        "npc": npc,
        "name": npc.name,
        "cc": cc,
        "prof": npc.profession,
        "race": getattr(npc, 'race', 'Human'),
        "title": getattr(npc, 'title', 'commoner'),
        "is_ruler": getattr(npc, 'is_ruler', False),
        "goals": getattr(npc, 'long_term_goals', []),
        "friends": getattr(npc, 'friends', []),
        "enemies": getattr(npc, 'enemies', []),
        "known": getattr(npc, 'known_info', []),
        "skills": getattr(npc, 'npc_skills', {}),
        "alignment": getattr(npc, 'alignment', 'true neutral'),
        "traits": getattr(npc, 'social_traits', []),
        "age": int(getattr(npc, 'age', 30)),
        "gold": int(getattr(npc, 'npc_gold', 0)),
        "faction": getattr(npc, 'faction', ''),
        "rel": getattr(npc, 'player_relationship', 0),
        "bravery": getattr(npc, 'bravery', 0.5),
    }
    ctx["top_skills"] = sorted(ctx["skills"].items(), key=lambda x: -x[1])[:3]
    ctx["memories"] = npc.get_recent_memories(5) if hasattr(npc, 'get_recent_memories') else []
    ctx["inv"] = npc.inventory_summary()[:50] if hasattr(npc, 'inventory_summary') else ""

    # Needs
    needs = getattr(npc, 'needs', {})
    ctx["hunger"] = needs.get("hunger", 50)
    ctx["thirst"] = needs.get("thirst", 50)
    ctx["rest"] = needs.get("rest", 50)
    ctx["social"] = needs.get("social", 50)

    # Emotions
    es = getattr(npc, 'emotion_state', None)
    if es:
        dom = es.dominant_emotion() if hasattr(es, 'dominant_emotion') else ("joy", 0.1)
        ctx["emotion"] = dom[0]
        ctx["emotion_intensity"] = dom[1]
        ctx["mood"] = getattr(es, 'mood', 0.0)
        ctx["grudges"] = getattr(es, 'grudges', {})
        ctx["bonds"] = getattr(es, 'bonds', {})
    else:
        ctx["emotion"] = "joy"
        ctx["emotion_intensity"] = 0.1
        ctx["mood"] = 0.0
        ctx["grudges"] = {}
        ctx["bonds"] = {}

    # Player-related memories
    player_memories = []
    all_mems = getattr(npc, 'memories', [])
    for m in all_mems:
        txt = m.get("text", "") if isinstance(m, dict) else str(m)
        if "player" in txt.lower():
            player_memories.append(txt)
    ctx["player_memories"] = player_memories[-5:]
    ctx["times_talked"] = sum(1 for m in all_mems
                              if isinstance(m, dict) and "player" in m.get("text", "").lower()
                              and m.get("type", "") in ("social", "trade", "teaching", "quest"))

    # Current action/state
    ctx["current_action"] = getattr(npc, 'current_action', '')
    ctx["state"] = getattr(npc, 'state', '')
    return ctx


def build_dialog_tree(npc) -> Dict[str, DialogLine]:
    """Build a complete dialog tree for an NPC based on their full context."""
    ctx = _gather_context(npc)
    lines = {}
    cc = ctx["cc"]
    race = ctx["race"]
    title = ctx["title"]
    goals = ctx["goals"]
    friends = ctx["friends"]
    enemies = ctx["enemies"]
    known = ctx["known"]
    top_skills = ctx["top_skills"]
    memories = ctx["memories"]
    inv = ctx["inv"]
    alignment = ctx["alignment"]
    traits = ctx["traits"]
    age = ctx["age"]
    gold = ctx["gold"]
    hunger = ctx["hunger"]
    faction = ctx["faction"]
    name = ctx["name"]
    is_ruler = ctx["is_ruler"]
    rel = ctx["rel"]

    # ================================================================
    # GREETING - varies by class, race, title, relationship, emotion,
    # needs, time of day, weather, memory of past interactions
    # ================================================================
    greeting = _build_greeting(npc, cc, race, title, is_ruler, alignment, traits, ctx)

    greeting_responses = [
        ("Tell me about yourself.", "about_self"),
        ("What's going on around here?", "local_news"),
    ]

    # Class-specific greeting options
    if cc in ("Fighter", "Paladin", "Barbarian", "Ranger"):
        greeting_responses.append(("Want to join me? I could use a fighter.", "recruit_offer"))
    elif cc in ("Wizard", "Sorcerer"):
        greeting_responses.append(("Know any magic you could teach me?", "magic_talk"))
    elif cc in ("Cleric", "Druid"):
        greeting_responses.append(("I need healing.", "heal_offer"))
    elif cc == "Bard":
        greeting_responses.append(("Sing me a song or tell me a tale.", "bard_perform"))
    elif cc == "Rogue":
        greeting_responses.append(("Got any... special opportunities?", "rogue_deal"))
    elif cc == "Monk":
        greeting_responses.append(("Can you teach me your discipline?", "monk_wisdom"))
    elif cc == "Warlock":
        greeting_responses.append(("Tell me about your patron.", "warlock_patron"))

    # Universal options
    if npc.shop_items:
        greeting_responses.append(("Show me your wares.", "shop"))
    elif getattr(npc, 'npc_inventory', []):
        greeting_responses.append(("Could we trade?", "barter"))

    if is_ruler:
        greeting_responses.insert(0, ("What is the state of your kingdom?", "kingdom_report"))

    if title in ("guard", "knight"):
        greeting_responses.append(("What threats should I watch for?", "guard_report"))

    if getattr(npc, 'quest', None) and not npc.quest.turned_in:
        if getattr(npc.quest, 'completed', False):
            greeting_responses.insert(1, ("I've completed your task!", "quest_complete"))
        else:
            greeting_responses.insert(1, ("Have you got any work for me?", "quest_offer"))
    else:
        greeting_responses.append(("Is there anything I can help with?", "help_offer"))

    # Needs-driven dialog options (NPC reveals their needs)
    if ctx["hunger"] < 30 and hasattr(npc, 'player_relationship'):
        greeting_responses.append(("You look hungry. Are you alright?", "needs_hunger"))
    if ctx["social"] < 25:
        greeting_responses.append(("You seem lonely. Want to talk?", "needs_social"))

    # Emotion-driven option (if NPC has a strong emotion)
    if ctx["emotion_intensity"] > 0.4:
        emotion_prompts = {
            "sadness": ("You seem upset. What's wrong?", "emotion_talk"),
            "anger": ("You look angry. What happened?", "emotion_talk"),
            "fear": ("Are you alright? You seem afraid.", "emotion_talk"),
            "joy": ("You seem happy today!", "emotion_talk"),
        }
        em_prompt = emotion_prompts.get(ctx["emotion"])
        if em_prompt:
            greeting_responses.append(em_prompt)

    # Gossip (if NPC knows interesting things about others)
    gossip_worthy = [k for k in known if any(w in k.lower() for w in
                     ["married", "died", "born", "fight", "killed", "scandal",
                      "left", "arrived", "discovered", "betrayed"])]
    if gossip_worthy:
        greeting_responses.append(("Heard any gossip lately?", "gossip"))

    if npc.consciousness >= 2:
        greeting_responses.append(("Something seems different about you...", "consciousness"))

    # Give NPC a task (requires relationship > 10)
    if rel > 10:
        # Check if NPC already has a player task
        if getattr(npc, 'player_task', None):
            task = npc.player_task
            if task.get("progress", 0) >= task.get("target_count", 1):
                greeting_responses.append(("About that task I gave you...", "task_report_done"))
            else:
                greeting_responses.append(("How's that task going?", "task_report_progress"))
        else:
            greeting_responses.append(("I need you to do something for me.", "task_assign"))

    # Negative options (always available)
    greeting_responses.append(("[Intimidate] Give me your gold.", "demand_gold"))
    greeting_responses.append(("[Threaten] You'd better watch yourself.", "threaten"))

    greeting_responses.append(("Farewell.", "goodbye"))

    lines["greeting"] = DialogLine(greeting, greeting_responses)

    # ================================================================
    # ABOUT SELF - deep personal info branching
    # ================================================================
    about = _build_about_self(npc, cc, race, goals, friends, enemies, traits, age, alignment, faction)
    lines["about_self"] = DialogLine(about, [
        ("What are your goals in life?", "goals_detail"),
        ("What skills do you have?", "skills_detail"),
        ("Tell me about your friends.", "friends_talk") if friends else ("Do you know anyone here?", "friends_talk"),
        ("What's your story?", "backstory"),
        ("Back to other topics.", "greeting"),
    ])

    # === Goals ===
    lines["goals_detail"] = DialogLine(
        _build_goals_text(cc, goals, alignment),
        [("Maybe I can help with that.", "help_with_goal"),
         ("What's stopping you?", "goal_obstacle"),
         ("Interesting.", "greeting")])

    lines["goal_obstacle"] = DialogLine(
        _build_obstacle_text(cc, goals, hunger, gold),
        [("I could help with that.", "help_with_goal"),
         ("I understand.", "greeting")])

    lines["help_with_goal"] = DialogLine(
        "You'd really help? That means a lot. Let me think about what we could do together.",
        [("Join my party and we'll tackle it together.", "recruit_offer"),
         ("Just tell me what you need.", "goal_quest"),
         ("I'll think about it.", "greeting")])

    lines["goal_quest"] = DialogLine(
        _build_personal_quest(cc, goals),
        [("I'll do it!", "accept_quest"),
         ("What's the reward?", "quest_reward"),
         ("Not right now.", "greeting")])

    lines["quest_reward"] = DialogLine(
        f"I can offer you {max(10, gold // 2)} gold and my gratitude. Plus whatever you find along the way.",
        [("Deal! I'll get started.", "accept_quest"),
         ("Not enough.", "greeting")])

    lines["accept_quest"] = DialogLine(
        "Excellent! I'll be here when you return. Good luck out there.",
        [("I won't let you down.", "goodbye")])

    # === Skills (filtered by alignment — evil NPCs may hide skills) ===
    from game.ai.npc_voice import get_skill_response_filtered
    player_rel = getattr(npc, 'player_relationship', 0)
    skill_text = get_skill_response_filtered(npc, player_rel)

    lines["skills_detail"] = DialogLine(skill_text, [
        ("Could you teach me?", "teach_offer"),
        ("Impressive.", "greeting")])

    lines["teach_offer"] = DialogLine(
        _build_teach_response(cc, top_skills),
        [("Yes, please teach me!", "learn_done"),
         ("Maybe another time.", "greeting")])

    lines["learn_done"] = DialogLine(
        _build_lesson_text(cc, top_skills[0][0] if top_skills else "survival"),
        [("Thank you, that was helpful!", "greeting")])

    # === Friends ===
    lines["friends_talk"] = DialogLine(
        _build_friends_text(npc, friends, enemies, memories),
        [("Could you introduce me?", "intro_friends") if friends else ("I see.", "greeting"),
         ("Anyone I should avoid?", "enemies_talk") if enemies else ("Good to know.", "greeting"),
         ("Back to other topics.", "greeting")])

    lines["intro_friends"] = DialogLine(
        f"Sure! Look for {friends[0] if friends else 'them'} around the village. Tell them I sent you.",
        [("Thanks!", "greeting")])

    lines["enemies_talk"] = DialogLine(
        f"Watch out for {enemies[0] if enemies else 'certain people'}. We don't see eye to eye.",
        [("What happened between you?", "enemy_story"),
         ("I'll be careful.", "greeting")])

    lines["enemy_story"] = DialogLine(
        _build_enemy_story(enemies, cc),
        [("That's unfortunate.", "greeting")])

    # === Backstory (enriched with life ledger) ===
    ledger = getattr(npc, 'life_ledger', None)
    backstory_parts = []
    if ledger:
        # Milestones
        for m in ledger.milestones[-2:]:
            backstory_parts.append(m["description"])
        # Strongest bonds
        for bname, binfo in ledger.get_strongest_bonds(2):
            if binfo.get("broken_day") is None:
                backstory_parts.append(f"{bname} is my {binfo['type']}")
        # Deaths of close ones
        for dname, dinfo in list(ledger.deaths_witnessed.items())[-2:]:
            if dinfo.get("relationship") in ("friend", "close friend", "child", "party_member"):
                backstory_parts.append(f"I lost {dname} to {dinfo['cause']}")
        # Combat history
        kill_narrative = ledger.narrate_kills()
        if kill_narrative:
            backstory_parts.append(kill_narrative)

    if backstory_parts:
        backstory = "My story? " + ". ".join(backstory_parts[:3]) + "."
    elif memories:
        backstory = f"My story? Well... {memories[0]}. "
        if len(memories) > 1:
            backstory += f"Also, {memories[1]}."
    else:
        backstory = _build_generic_backstory(cc, race, age)

    backstory_responses = [("Tell me more.", "backstory_deep"),
                           ("Fascinating.", "greeting")]
    # Add ledger-specific dialog options
    if ledger and ledger.deaths_witnessed:
        backstory_responses.insert(0, ("Who have you lost?", "talk_losses"))
    if ledger and ledger.kills:
        backstory_responses.insert(0, ("You've seen battle?", "talk_battles"))

    lines["backstory"] = DialogLine(backstory, backstory_responses)

    # Talk about losses
    if ledger and ledger.deaths_witnessed:
        loss_text = ledger.narrate_deaths(4)
        if not loss_text:
            loss_text = "I've been fortunate — haven't lost anyone close."
        lines["talk_losses"] = DialogLine(loss_text,
            [("I'm sorry for your losses.", "greeting"),
             ("That must be hard.", "greeting")])
    else:
        lines["talk_losses"] = DialogLine(
            "I've been fortunate so far. No great losses.",
            [("Good to hear.", "greeting")])

    # Talk about battles
    if ledger and ledger.kills:
        battle_text = ledger.narrate_kills()
        total = ledger.get_total_kills()
        if total > 5:
            battle_text += f" — {total} foes in total. It weighs on you."
        elif total > 0:
            battle_text += ". I do what I must to survive."
        lines["talk_battles"] = DialogLine(battle_text,
            [("You're a seasoned warrior.", "greeting"),
             ("Stay safe out there.", "greeting")])
    else:
        lines["talk_battles"] = DialogLine(
            "I try to avoid violence when I can.",
            [("Wise approach.", "greeting")])

    lines["backstory_deep"] = DialogLine(
        _build_deep_backstory(cc, race, age, alignment, traits),
        [("Thank you for sharing.", "greeting")])

    # ================================================================
    # LOCAL NEWS - what they know about the world
    # ================================================================
    news = _build_local_news(known, cc, faction)
    news_responses = [("Tell me more.", "more_news")]
    if any(w in " ".join(known).lower() for w in ["danger", "monster", "bandit", "wolf", "orc", "war"]):
        news_responses.append(("I could help deal with that.", "offer_help_threat"))
    news_responses.append(("Thanks for the info.", "greeting"))

    lines["local_news"] = DialogLine(news, news_responses)

    lines["more_news"] = DialogLine(
        _build_more_news(known, cc),
        [("Useful information. Thanks.", "greeting")])

    lines["offer_help_threat"] = DialogLine(
        "Really? That would be a great help. The people here could use someone brave.",
        [("Where should I go?", "threat_directions"),
         ("I'll look into it.", "greeting")])

    lines["threat_directions"] = DialogLine(
        "Head into the wilds away from the settlement. Be careful, especially at night. Don't go alone if you can help it.",
        [("I'll be careful.", "goodbye")])

    # ================================================================
    # CLASS-SPECIFIC BRANCHES
    # ================================================================

    # Fighter/Paladin/Barbarian/Ranger: Combat talk
    lines["recruit_offer"] = DialogLine(
        _build_recruit_response(cc, race, alignment, npc.player_relationship),
        [("Great, let's go! [Press R to recruit]", "greeting"),
         ("Maybe another time.", "greeting")])

    # Wizard/Sorcerer: Magic discussion
    lines["magic_talk"] = DialogLine(
        _build_magic_talk(cc, getattr(npc, 'known_spells', []), getattr(npc, 'is_spellcaster', False)),
        [("Can you teach me a spell?", "teach_offer"),
         ("What do you know about the arcane ruins?", "ruin_lore"),
         ("Fascinating.", "greeting")])

    lines["ruin_lore"] = DialogLine(
        "The ruins predate even the Elder Races. Strange energies still pulse within. I've sensed magical artifacts there, but the undead make exploration treacherous.",
        [("I'll explore them.", "greeting"),
         ("Sounds dangerous.", "greeting")])

    # Cleric/Druid: Healing and blessings
    lines["heal_offer"] = DialogLine(
        _build_heal_response(cc),
        [("Thank you. [Heals 20 HP]", "heal_done"),
         ("Can you bless me too?", "blessing"),
         ("I'm fine actually.", "greeting")])

    lines["heal_done"] = DialogLine(
        "There. You should feel the warmth of healing energy flowing through you. Take better care of yourself.",
        [("Thank you!", "greeting")])

    lines["blessing"] = DialogLine(
        "May the light protect you on your journey. You are blessed for the next day.",
        [("I feel stronger already. Thank you.", "greeting")])

    # Bard: Performance and lore
    lines["bard_perform"] = DialogLine(
        _build_bard_performance(known, memories, faction),
        [("That was wonderful! Do you know any legends?", "bard_legend"),
         ("You have real talent.", "greeting")])

    lines["bard_legend"] = DialogLine(
        "In the age before ages, when the world was young and the stars sang differently, the Elder Races first walked upon Aethermoor. The Elves sang the forests into being, and the Dwarves woke the mountains with their hammers.",
        [("Tell me about the Great War.", "great_war_story"),
         ("Amazing. Thank you.", "greeting")])

    lines["great_war_story"] = DialogLine(
        "Two centuries ago, a dark power rose from the ancient ruins. The Shadow consumed entire villages before the races united against it. The battle at the Temple of Awakening turned the tide, but the scars remain in every ruin you see.",
        [("That explains a lot.", "greeting")])

    # Rogue: Deals and secrets
    lines["rogue_deal"] = DialogLine(
        _build_rogue_deal(gold, inv),
        [("I'm interested. Tell me more.", "rogue_detail"),
         ("That's too risky for me.", "greeting")])

    lines["rogue_detail"] = DialogLine(
        "I know the location of a hidden cache in the ruins nearby. For a small cut of the profits, I'll mark it on your map. Or we could go together - I handle the traps, you handle the monsters.",
        [("Let's go together. [Press R to recruit]", "recruit_offer"),
         ("Just tell me where it is.", "rogue_map"),
         ("I'll pass.", "greeting")])

    lines["rogue_map"] = DialogLine(
        "Head to the nearest ruins and look for a loose stone on the eastern wall. Behind it, there's a passage. Good luck - and remember my cut.",
        [("Thanks for the tip.", "goodbye")])

    # Monk: Wisdom and training
    lines["monk_wisdom"] = DialogLine(
        "Discipline begins with the breath. Control your breathing, control your mind. Control your mind, control your actions. But true wisdom? That comes from knowing when NOT to act.",
        [("Can you teach me to fight like you?", "monk_training"),
         ("That's very wise.", "greeting")])

    lines["monk_training"] = DialogLine(
        "Fighting is the last resort of the disciplined mind. But yes, I can teach you to center yourself. Focus your energy. Strike with precision, not force.",
        [("Train me! [Gain combat skill XP]", "learn_done"),
         ("I'll practice on my own.", "greeting")])

    # Warlock: Patron mysteries
    lines["warlock_patron"] = DialogLine(
        "My patron? That's... not something I discuss lightly. Let's just say I made an arrangement when I was desperate, and now I have power I never dreamed of. The cost... is complicated.",
        [("What kind of power?", "warlock_power"),
         ("What's the cost?", "warlock_cost"),
         ("I understand. Secrets are yours to keep.", "greeting")])

    lines["warlock_power"] = DialogLine(
        "I can see things others can't. Feel the threads of magic in the air. Cast spells that would take a wizard years to learn. But the whispers... the whispers never stop.",
        [("That sounds terrifying.", "greeting")])

    lines["warlock_cost"] = DialogLine(
        "Every gift has a price. Sometimes I'm asked to do things. Small things, usually. Investigate a ruin. Collect a particular item. Nothing evil... not yet.",
        [("Be careful.", "greeting")])

    # Guard/Knight: Duty report
    lines["guard_report"] = DialogLine(
        _build_guard_report(known, faction),
        [("I'll help keep watch.", "recruit_offer"),
         ("I'll stay alert. Thanks.", "greeting")])

    # Ruler: Kingdom report
    lines["kingdom_report"] = DialogLine(
        _build_kingdom_report(npc, faction, known),
        [("How can I serve the kingdom?", "kingdom_service"),
         ("Long live the ruler.", "greeting")])

    lines["kingdom_service"] = DialogLine(
        "The kingdom always needs capable people. Clear the monsters threatening our borders, protect our trade caravans, or bring me intelligence about rival kingdoms.",
        [("I'll clear out the monsters.", "accept_quest"),
         ("I'll protect the caravans.", "accept_quest"),
         ("What do I get in return?", "kingdom_reward")])

    lines["kingdom_reward"] = DialogLine(
        "Gold, equipment, and the gratitude of the crown. Prove yourself and perhaps a title and land will follow.",
        [("I'll serve gladly.", "accept_quest"),
         ("I'll think about it.", "greeting")])

    # Barter
    lines["barter"] = DialogLine(
        f"I'm not a merchant, but I have some things. {inv}. Anything interest you?",
        [("Let me see.", "shop"),
         ("Not right now.", "greeting")])

    # Shop
    lines["shop"] = DialogLine(
        "Here's what I have available." if npc.shop_items else "I don't have a formal shop, but we could work something out.",
        [("Let me browse.", "greeting"), ("Farewell.", "goodbye")])

    # Quest offer
    lines["quest_offer"] = DialogLine(
        _build_quest_dialog(npc, cc, goals),
        [("I'll take the job!", "accept_quest"),
         ("What's the pay?", "quest_reward"),
         ("Not right now.", "greeting")])

    # Help offer
    lines["help_offer"] = DialogLine(
        _build_help_dialog(cc, goals, known),
        [("I can do that!", "accept_quest"),
         ("Tell me more.", "help_detail"),
         ("Maybe later.", "greeting")])

    lines["help_detail"] = DialogLine(
        "It won't be easy, but nothing worth doing ever is. You'll need to be prepared - bring weapons, supplies, and maybe a friend or two.",
        [("I'm ready. Let's do this.", "accept_quest"),
         ("I need to prepare first.", "greeting")])

    # Consciousness
    lines["consciousness"] = DialogLine(
        _get_consciousness_dialog(npc.consciousness, cc),
        [("That's... profound.", "consciousness_deep"),
         ("Are you feeling alright?", "greeting")])

    lines["consciousness_deep"] = DialogLine(
        "Have you ever noticed how predictable everyone is? The patterns repeat. But you... you're different. You make real choices. I can sense it.",
        [("What do you mean by that?", "greeting"),
         ("You're starting to scare me.", "goodbye")])

    # === NEGATIVE INTERACTIONS ===

    # Demand gold
    if npc.bravery < 0.4:
        lines["demand_gold"] = DialogLine(
            "P-please, don't hurt me! Here, take what I have, just leave me alone!",
            [("Smart choice.", "goodbye"),
             ("I was just joking. Relax.", "apologize")])
    else:
        lines["demand_gold"] = DialogLine(
            f"You dare threaten me? I'm a {cc} and I won't be bullied!",
            [("[Back down] Sorry, bad joke.", "apologize"),
             ("[Press further] I mean it.", "threaten")])

    # Threaten
    lines["threaten"] = DialogLine(
        _build_threat_response(cc, npc.bravery, alignment),
        [("[Attack them]", "threaten"),  # triggers combat via mechanic
         ("[Back down] Forget I said anything.", "apologize")])

    # Apologize (de-escalation)
    lines["apologize"] = DialogLine(
        _build_apology_response(npc.player_relationship, npc.bravery),
        [("Let's start over.", "greeting"),
         ("Whatever.", "goodbye")])

    # Insult (reachable from some conversation paths)
    lines["insult"] = DialogLine(
        "How dare you! I won't forget this. You've made an enemy today.",
        [("Good.", "goodbye"),
         ("Wait, I'm sorry.", "apologize")])

    # Refuse to help when asked
    lines["refuse_help"] = DialogLine(
        "I see. Well, I suppose I'll have to manage on my own then.",
        [("Sorry, I'm busy.", "goodbye"),
         ("Actually, let me reconsider.", "help_offer")])

    # Try to steal during conversation
    lines["steal_attempt"] = DialogLine(
        "[You reach for their belongings while they're distracted...]",
        [("[Try to steal] (DEX check)", "steal_attempt"),  # triggers mechanic
         ("[Think better of it]", "greeting")])

    # Mock beliefs (religious NPCs)
    if cc in ("Cleric", "Paladin", "Monk", "Druid"):
        lines["mock_beliefs"] = DialogLine(
            "You... you would mock the sacred? I pity your ignorance.",
            [("I was only asking questions.", "apologize"),
             ("Your gods aren't real.", "mock_beliefs")])  # triggers mechanic

    # Add negative sub-options to existing branches
    if "about_self" in lines:
        existing = lines["about_self"].responses
        existing.append(("[Insult] That's pathetic.", "insult"))
        existing.append(("[Steal] (try to pickpocket)", "steal_attempt"))

    if "goals_detail" in lines:
        existing = lines["goals_detail"].responses
        existing.append(("That's a waste of time.", "insult"))

    if "help_offer" in lines:
        existing = lines["help_offer"].responses
        existing.append(("Not my problem.", "refuse_help"))

    if "quest_offer" in lines:
        existing = lines["quest_offer"].responses
        existing.append(("Do it yourself.", "reject_quest"))

    if "heal_offer" in lines and cc in ("Cleric", "Paladin"):
        existing = lines["heal_offer"].responses
        existing.append(("Your magic is just tricks.", "mock_beliefs"))

    if "monk_wisdom" in lines:
        existing = lines["monk_wisdom"].responses
        existing.append(("That's nonsense.", "insult"))

    if "bard_perform" in lines:
        existing = lines["bard_perform"].responses
        existing.append(("Terrible. Stop singing.", "insult"))

    # ================================================================
    # NEEDS-DRIVEN DIALOG — NPCs reveal and act on their needs
    # ================================================================
    if ctx["hunger"] < 30:
        food_response = [("Here, take this food.", "gift"),
                         ("I hope you find something to eat.", "greeting")]
        lines["needs_hunger"] = DialogLine(
            _body_language(ctx) + random.choice([
                f"*stomach growls* I haven't eaten in days. Food is scarce right now.",
                f"I'm starving, honestly. If you have any food to spare...",
                f"I've been too busy to eat. Or maybe too poor. Either way, my belly is empty.",
            ]),
            food_response)
    else:
        lines["needs_hunger"] = DialogLine(
            "I'm fine, actually. Had a meal not long ago. Thank you for asking though!",
            [("Good to hear.", "greeting")])

    if ctx["social"] < 25:
        lines["needs_social"] = DialogLine(
            _body_language(ctx) + random.choice([
                "I... yes. It's been so long since someone actually stopped to talk. Everyone is so busy.",
                "You noticed? I've been out here alone for days. It wears on you.",
                "Thank you for asking. Most people just walk past. It means a lot.",
            ]),
            [("Tell me what's on your mind.", "about_self"),
             ("I'm always happy to chat.", "greeting")])
    else:
        lines["needs_social"] = DialogLine(
            "That's kind of you, but I've been keeping good company lately.",
            [("Glad to hear it.", "greeting")])

    # ================================================================
    # EMOTION-DRIVEN DIALOG — deep conversations about feelings
    # ================================================================
    emotion_text = _build_emotion_dialog(ctx)
    emotion_responses = [("Is there anything I can do to help?", "emotion_help"),
                         ("I understand. Stay strong.", "greeting")]
    if ctx["emotion"] == "joy":
        emotion_responses = [("That's wonderful! What happened?", "emotion_detail"),
                             ("Your happiness is contagious!", "greeting")]
    lines["emotion_talk"] = DialogLine(
        _body_language(ctx) + emotion_text,
        emotion_responses)

    lines["emotion_detail"] = DialogLine(
        _build_emotion_detail(ctx),
        [("That's really interesting.", "greeting"),
         ("Tell me more about yourself.", "about_self")])

    lines["emotion_help"] = DialogLine(
        _build_emotion_help_response(ctx),
        [("I'll do what I can.", "greeting"),
         ("Here, take this as a gift.", "gift")])

    # ================================================================
    # GOSSIP — NPCs share interesting things they know
    # ================================================================
    gossip_worthy = [k for k in known if any(w in k.lower() for w in
                     ["married", "died", "born", "fight", "killed", "scandal",
                      "left", "arrived", "discovered", "betrayed"])]
    if gossip_worthy:
        gossip_text = random.choice(gossip_worthy)
        lines["gossip"] = DialogLine(
            _body_language(ctx) + f"*leans in* You didn't hear this from me, but... {gossip_text}",
            [("Tell me more.", "gossip_more"),
             ("That's juicy. Thanks.", "greeting")])
        other_gossip = [g for g in gossip_worthy if g != gossip_text]
        if other_gossip:
            lines["gossip_more"] = DialogLine(
                f"Also... {random.choice(other_gossip)}",
                [("Anything else?", "local_news"),
                 ("Thanks for the information.", "greeting")])
        else:
            lines["gossip_more"] = DialogLine(
                "That's all I've heard. But keep your ears open!",
                [("Will do.", "greeting")])
    else:
        lines["gossip"] = DialogLine(
            "Not much gossip right now. Things have been quiet.",
            [("That's probably a good thing.", "greeting")])

    # ================================================================
    # QUEST COMPLETION — acknowledge player finished a task
    # ================================================================
    quest = getattr(npc, 'quest', None)
    if quest and getattr(quest, 'completed', False) and not quest.turned_in:
        reward_gold = getattr(quest, 'reward_gold', max(10, gold // 2))
        lines["quest_complete"] = DialogLine(
            f"You did it! I can't believe it! Thank you so much. Here's {reward_gold} gold as promised. You've earned my eternal gratitude.",
            [("It was my pleasure.", "goodbye"),
             ("Do you have any more work?", "help_offer")])
    else:
        lines["quest_complete"] = DialogLine(
            "Hmm, I don't think you've finished the task yet. Come back when you have.",
            [("You're right, I'll keep working on it.", "goodbye")])

    # ================================================================
    # PLAYER-ASSIGNED TASKS — player gives NPC a job
    # ================================================================
    _task_accept_text = _build_task_accept(ctx)
    _task_refuse_text = _build_task_refuse(ctx)
    task_options = _build_task_options(ctx)

    lines["task_assign"] = DialogLine(
        _task_accept_text,
        task_options)

    lines["task_refuse"] = DialogLine(
        _task_refuse_text,
        [("Fair enough.", "greeting"),
         ("I'll make it worth your while. (offer gold)", "task_bribe")])

    # Specific task types
    lines["task_kill"] = DialogLine(
        _build_task_kill_dialog(ctx),
        [("Good, get started.", "goodbye"),
         ("Actually, never mind.", "greeting")])

    lines["task_fetch"] = DialogLine(
        _build_task_fetch_dialog(ctx),
        [("Good, get started.", "goodbye"),
         ("Actually, never mind.", "greeting")])

    lines["task_scout"] = DialogLine(
        _build_task_scout_dialog(ctx),
        [("Report back when you're done.", "goodbye"),
         ("Actually, never mind.", "greeting")])

    lines["task_guard"] = DialogLine(
        _build_task_guard_dialog(ctx),
        [("I'm counting on you.", "goodbye"),
         ("Actually, never mind.", "greeting")])

    lines["task_deliver"] = DialogLine(
        _build_task_deliver_dialog(ctx),
        [("Thanks, get going.", "goodbye"),
         ("Actually, never mind.", "greeting")])

    lines["task_bribe"] = DialogLine(
        "Hmm... how much gold are we talking?" if rel > 0 else
        "You think you can buy me? ...how much?",
        [("50 gold for your trouble.", "task_bribe_50"),
         ("100 gold. Good pay.", "task_bribe_100"),
         ("Forget it.", "greeting")])

    lines["task_bribe_50"] = DialogLine(
        "50 gold? I suppose that changes things. What did you need?",
        task_options)

    lines["task_bribe_100"] = DialogLine(
        "100 gold! Now you're talking. What's the job?",
        task_options)

    # Task progress reports
    player_task = getattr(npc, 'player_task', None)
    if player_task:
        prog = player_task.get("progress", 0)
        total = player_task.get("target_count", 1)
        desc = player_task.get("description", "your task")
        if prog >= total:
            lines["task_report_done"] = DialogLine(
                f"It's done! {desc}. I completed what you asked. ({prog}/{total})",
                [("Excellent work! Here's your reward.", "task_collect"),
                 ("Well done. Anything else to report?", "greeting")])
            lines["task_collect"] = DialogLine(
                "Thank you! It was hard work but I'm glad I could help.",
                [("You've earned my respect.", "goodbye")])
        else:
            lines["task_report_progress"] = DialogLine(
                f"I'm working on it. {desc}. Progress: {prog}/{total}. "
                f"It's not easy but I'll get it done.",
                [("Keep at it.", "goodbye"),
                 ("Take your time.", "greeting"),
                 ("Forget it, I'll do it myself.", "task_cancel")])
    else:
        lines["task_report_done"] = DialogLine(
            "I don't have any task to report on.",
            [("My mistake.", "greeting")])
        lines["task_report_progress"] = DialogLine(
            "I'm not working on anything for you right now.",
            [("Right, sorry.", "greeting")])

    lines["task_cancel"] = DialogLine(
        "You're calling it off? Fine. I had other things to do anyway.",
        [("Sorry for wasting your time.", "goodbye")])

    # ================================================================
    # DEEPER RELATIONSHIP CONVERSATIONS (unlock at higher relationship)
    # ================================================================
    if rel > 30:
        # Deeper personal topics unlock with trust
        lines["deep_talk"] = DialogLine(
            _build_deep_personal(ctx),
            [("Thank you for sharing that.", "greeting"),
             ("I feel the same way sometimes.", "deep_bond"),
             ("That must be hard.", "deep_empathy")])

        lines["deep_bond"] = DialogLine(
            f"Really? I didn't expect you to understand. Most people don't. Maybe we're more alike than I thought.",
            [("I think so too.", "greeting")])

        lines["deep_empathy"] = DialogLine(
            "Thank you for listening. It helps more than you know. Not many people take the time.",
            [("Anytime. That's what friends are for.", "greeting")])

        # Add deep talk option to about_self
        if "about_self" in lines:
            lines["about_self"].responses.insert(-1,
                ("Can I ask you something personal?", "deep_talk"))

    # Grudge/bond references
    if ctx["grudges"]:
        grudge_name, grudge_info = next(iter(ctx["grudges"].items()))
        cause = grudge_info.get("cause", "something unforgivable")
        if "enemies_talk" not in lines or not lines.get("enemies_talk"):
            lines["enemies_talk"] = DialogLine(
                f"Don't get me started on {grudge_name}. {cause}. I won't forget that.",
                [("Sounds serious.", "greeting")])

    if ctx["bonds"]:
        bond_name, bond_info = next(iter(ctx["bonds"].items()))
        cause = bond_info.get("cause", "we've been through a lot together")
        if friends and bond_name in friends:
            # Enhance friends_talk with bond info
            if "friends_talk" in lines:
                orig = lines["friends_talk"].text
                lines["friends_talk"] = DialogLine(
                    orig + f" {bond_name} is special to me - {cause}.",
                    lines["friends_talk"].responses)

    # ================================================================
    # GOODBYE — varies by relationship, emotion, and class
    # ================================================================
    goodbye_text = _build_goodbye(ctx)
    lines["goodbye"] = DialogLine(goodbye_text, [])

    # Reject quest (referenced by negative dialog additions)
    lines["reject_quest"] = DialogLine(
        "Fine. I'll find someone else who has the courage to help.",
        [("Wait, maybe I'll reconsider.", "quest_offer"),
         ("Good luck with that.", "goodbye")])

    # Gift node (intercepted by panels.py, but kept as fallback)
    lines["gift"] = DialogLine(
        "You want to give me something? That's very kind of you!",
        [("Here you go.", "gift"),  # intercepted by panels.py
         ("Actually, never mind.", "greeting")])

    return lines


# ================================================================
# HELPER FUNCTIONS
# ================================================================


# Helper functions have been moved to game/core/dialog_helpers.py
