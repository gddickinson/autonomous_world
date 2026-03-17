"""
Rich dialog trees for NPC conversations.

Each class/race combination gets unique conversation paths.
Dialogs reference actual NPC state: goals, skills, inventory, memories,
relationships, emotions, needs, weather, time of day, and ongoing gameplay.
Every dialog option either provides information or triggers a game mechanic.
"""

import random
from typing import Dict, List, Tuple


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


def _body_language(ctx) -> str:
    """Generate body language description based on emotion and relationship."""
    em = ctx["emotion"]
    intensity = ctx["emotion_intensity"]
    rel = ctx["rel"]

    if intensity < 0.2:
        return ""

    body = {
        "joy": ["[They smile warmly]", "[Their eyes light up]", "[They seem cheerful]"],
        "trust": ["[They meet your gaze openly]", "[They relax visibly]"],
        "fear": ["[They glance around nervously]", "[They take a step back]", "[Their hands tremble slightly]"],
        "surprise": ["[They blink in surprise]", "[Their eyes widen]"],
        "sadness": ["[Their shoulders slump]", "[They avoid your gaze]", "[Their voice is quiet]"],
        "disgust": ["[They wrinkle their nose]", "[They cross their arms]"],
        "anger": ["[Their jaw tightens]", "[They glare at you]", "[Their fists clench]"],
        "anticipation": ["[They lean forward eagerly]", "[Their eyes are keen]"],
    }

    if rel < -30:
        hostile = ["[They scowl at you]", "[They fold their arms defensively]",
                   "[Their eyes narrow with suspicion]"]
        return random.choice(hostile) + " "
    elif rel > 50:
        friendly = ["[They beam at seeing you]", "[They clasp your hand warmly]"]
        return random.choice(friendly) + " "

    options = body.get(em, [])
    if options and intensity > 0.3:
        return random.choice(options) + " "
    return ""


def _needs_comment(ctx) -> str:
    """Generate a comment about the NPC's most pressing need."""
    if ctx["hunger"] < 25:
        return random.choice([
            "My stomach is growling... haven't eaten in a while.",
            "I'd trade my best tool for a hot meal right about now.",
            "Forgive me if I seem distracted, I'm starving.",
        ])
    if ctx["thirst"] < 25:
        return random.choice([
            "My throat is parched. Could use some water.",
            "Sorry, bit distracted. Thirsty as anything.",
        ])
    if ctx["rest"] < 25:
        return random.choice([
            "*yawns* Sorry, I've barely slept.",
            "I'm exhausted. Been working without rest.",
        ])
    if ctx["social"] < 20:
        return random.choice([
            "It's so good to see someone! I've been alone for too long.",
            "Oh! A visitor! Please, stay and talk. It gets lonely here.",
        ])
    return ""


def _profession_context(ctx) -> str:
    """Comment on current work activity."""
    prof = ctx["prof"]
    action = ctx["current_action"]

    if action in ("working", "crafting"):
        comments = {
            "Baker": "The bread should be done soon. Can't talk long.",
            "Blacksmith": "*wipes soot from hands* Just finishing at the forge.",
            "Farmer": "Just been tending the crops. They need constant attention.",
            "Innkeeper": "Running the inn keeps me busy. What can I get you?",
            "Healer": "I've been treating patients all day. What ails you?",
            "Merchant": "Business has been steady today. Looking to buy or sell?",
            "Guard": "Keeping watch. What's your business here?",
            "Alchemist": "Careful with those bottles. One wrong mix and... boom.",
            "Carpenter": "Working on a new piece. The wood has to be just right.",
            "Woodcutter": "Been chopping since dawn. My arms know it.",
        }
        if prof in comments:
            return " " + comments[prof]

    if action == "sleeping":
        return " *rubbing eyes* You woke me..."
    if action == "eating":
        return " *between bites* Sorry, just having a meal."
    if action == "socializing":
        return " I was just chatting with someone."
    if action == "praying":
        return " *finishes prayer* Yes? What is it?"
    return ""


def _memory_greeting(ctx) -> str:
    """Reference past interactions with the player."""
    pmem = ctx["player_memories"]
    times = ctx["times_talked"]

    if times == 0:
        return ""
    if times == 1:
        return " We've met before, haven't we?"
    if times >= 5:
        return " Good to see you again, friend. We've had many conversations now."
    if times >= 2:
        # Reference a specific past memory
        if pmem:
            last = pmem[-1]
            if "trade" in last.lower():
                return " Back for more trading?"
            if "heal" in last.lower():
                return " Feeling better since last time?"
            if "quest" in last.lower() or "task" in last.lower():
                return " Any progress on that task?"
            if "insult" in last.lower() or "threaten" in last.lower():
                return " I hope you're more civil this time."
            return " Ah, you again. Good to see you."
    return ""


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

def _build_greeting(npc, cc, race, title, is_ruler, alignment, traits, ctx=None):
    """Build greeting that reflects relationship, emotion, needs, time, weather, and memory."""
    name = npc.name
    rel = ctx["rel"] if ctx else getattr(npc, 'player_relationship', 0)
    body = _body_language(ctx) if ctx else ""
    needs = _needs_comment(ctx) if ctx else ""
    prof_ctx = _profession_context(ctx) if ctx else ""
    mem_greet = _memory_greeting(ctx) if ctx else ""

    # HOSTILE greeting (relationship < -30)
    if rel < -30:
        hostile = [
            f"{body}What do YOU want? Haven't you caused enough trouble?",
            f"{body}You again. I have nothing to say to you.",
            f"{body}*cold stare* State your business and leave, quickly.",
            f"{body}The last person I wanted to see. What is it?",
        ]
        return random.choice(hostile)

    # UNFRIENDLY greeting (-30 to -5)
    if rel < -5:
        unfriendly = [
            f"{body}Oh. It's you. What do you want?",
            f"{body}I'm not sure we have much to talk about. But go ahead.",
            f"{body}You're not exactly my favorite person, but I'll hear you out.",
        ]
        return random.choice(unfriendly)

    # FRIENDLY greeting (20 to 50)
    if 20 < rel <= 50:
        friendly_prefix = random.choice([
            "Good to see you!",
            "Hey, welcome back!",
            "Ah, a friendly face!",
        ])
        base = f"{body}{friendly_prefix}{mem_greet}"
        if needs:
            base += f" {needs}"
        if prof_ctx:
            base += prof_ctx
        return base

    # CLOSE FRIEND greeting (> 50)
    if rel > 50:
        close = random.choice([
            f"{body}My friend! It's always good to see you.{mem_greet}",
            f"{body}There you are! I was hoping you'd come by.{mem_greet}",
            f"{body}Welcome, dear friend. You know you're always welcome here.{mem_greet}",
        ])
        if needs:
            close += f" {needs}"
        return close

    # NEUTRAL greeting (default, -5 to 20) — class/title specific
    if is_ruler:
        base = f"{body}Welcome to my domain. I am {name}, ruler of these lands. What brings you before me?"
    elif title == "guard":
        base = f"{body}Halt! State your business. I'm {name}, on watch duty."
    elif title == "knight":
        base = f"{body}Well met, traveler. I am Sir {name}, sworn knight of this realm."
    elif title == "duke":
        base = f"{body}Greetings. I am {name}, duke of this territory."
    else:
        class_greetings = {
            "Fighter": f"Hail, traveler! I'm {name}. You look like someone who can handle themselves.",
            "Wizard": f"Ah, a visitor. I'm {name}. Forgive me if I seem distracted - I was in the middle of research.",
            "Cleric": f"Blessings upon you, friend. I'm {name}, servant of the divine.",
            "Rogue": f"Hey there. Name's {name}. You're not with the guards, are you? Good.",
            "Ranger": f"*nods* {name}. I don't see many travelers on these paths.",
            "Paladin": f"Well met! I am {name}, sworn to uphold justice.",
            "Barbarian": f"What do you want? I'm {name}. Speak quickly.",
            "Bard": f"Welcome, welcome! I'm {name}, storyteller and song-spinner extraordinaire!",
            "Druid": f"Greetings, wanderer. I'm {name}. The forest brought you here for a reason.",
            "Monk": f"Peace be with you. I am {name}.",
            "Sorcerer": f"Oh! Sorry, didn't see you there. I'm {name}. Magic keeps me a bit... distracted.",
            "Warlock": f"You approach boldly. I'm {name}. Most people give me a wider berth.",
            # Civilian professions
            "Merchant": f"Welcome to my shop! I'm {name}. Looking to buy or sell?",
            "Baker": f"Hello there! I'm {name}. Fresh bread just out of the oven.",
            "Innkeeper": f"Welcome, traveler! I'm {name}. Need a room, a meal, or just good company?",
            "Healer": f"Greetings. I'm {name}. Are you hurt? I can help.",
            "Farmer": f"*wipes dirt from hands* Oh, hello. I'm {name}. Don't mind the mess.",
            "Blacksmith": f"*sets down hammer* What can I forge for you? Name's {name}.",
            "Alchemist": f"Careful around the bottles. I'm {name}. Need a potion?",
        }
        # Try class first, then profession
        base = class_greetings.get(cc, class_greetings.get(
            npc.profession, f"{body}Hello there. I'm {name}, a {race} {cc}."))
        base = body + base

    # Append memory, needs, and profession context
    if mem_greet:
        base += mem_greet
    if needs:
        base += f" {needs}"
    elif prof_ctx:
        base += prof_ctx
    return base


def _build_about_self(npc, cc, race, goals, friends, enemies, traits, age, alignment, faction):
    from game.ai.npc_voice import get_alignment_response_filtered, get_goals_response_filtered
    player_rel = getattr(npc, 'player_relationship', 0)

    text = f"I'm {npc.name}, a {race} {cc}."
    if age < 20: text += " Still young, but I've already seen more than most."
    elif age > 60: text += f" I've lived {age} years and learned a few things along the way."

    # Goals — filtered by alignment (evil NPCs may hide true goals)
    goal_text = get_goals_response_filtered(npc, player_rel)
    text += f" {goal_text}"

    # Alignment-driven self-description
    if "good" in alignment:
        if "generous" in traits: text += " I try to help everyone I can."
        elif "compassionate" in traits: text += " I care deeply about others."
        else: text += " I believe in doing what's right."
    elif "evil" in alignment:
        if player_rel > 20:
            text += " I'm a practical person. I know what matters."
        else:
            text += " I look out for myself. That's the smart play."
    elif "chaotic" in alignment:
        text += " I follow my own path, whatever that looks like today."
    elif "lawful" in alignment:
        text += " I believe in order and doing one's duty."

    if faction:
        text += f" I serve {faction}."
    return text


def _build_goals_text(cc, goals, alignment):
    # Evil NPCs may present sanitized goals
    if "evil" in alignment and goals and random.random() < 0.5:
        return random.choice([
            "My goals? Simply to prosper and help my community thrive.",
            "I just want what's best for everyone. Especially myself. Ha, just kidding.",
            "Nothing too ambitious. Just living a good, productive life.",
        ])
    if goals:
        text = f"My ambition? {goals[0]}."
        if len(goals) > 1:
            text += f" And if I can, {goals[1]}."
        # Alignment flavor
        if "lawful" in alignment:
            text += " Duty demands no less."
        elif "chaotic" in alignment:
            text += " Or maybe I'll change my mind tomorrow. Who knows?"
        elif "good" in alignment:
            text += " If it helps others along the way, even better."
        else:
            text += " Every day I work toward making it happen."
        return text
    defaults = {
        "Fighter": "I want to prove myself in battle and protect those who can't protect themselves.",
        "Wizard": "Knowledge. Pure, boundless knowledge. That's what I live for.",
        "Cleric": "I want to ease suffering wherever I find it.",
        "Rogue": "Freedom and fortune. In that order. Well, maybe fortune first.",
        "Druid": "To restore the balance between civilization and the wild.",
    }
    return defaults.get(cc, "I'm still figuring that out. Life has a way of surprising you.")


def _build_obstacle_text(cc, goals, hunger, gold):
    obstacles = []
    if hunger < 40: obstacles.append("Finding enough food has been a real struggle lately.")
    if gold < 10: obstacles.append("I'm running low on gold. Hard to do much without coin.")
    if not obstacles:
        obstacles = [
            "The monsters make it hard to travel safely.",
            "I need allies I can trust.",
            "Time, mostly. There's never enough of it.",
        ]
    return random.choice(obstacles)


def _build_friends_text(npc, friends, enemies, memories):
    if friends:
        text = f"My closest friends are {', '.join(friends[:3])}."
        for mem in memories:
            if any(f in mem for f in friends[:2]):
                text += f" I remember {mem}."
                break
        return text
    return "I keep to myself mostly. Trust is earned slowly out here."


def _build_enemy_story(enemies, cc):
    if not enemies:
        return "No specific enemies, but you can never be too careful."
    stories = [
        f"{enemies[0]} and I had a falling out over a trade deal gone wrong.",
        f"{enemies[0]} insulted my honor. Some things can't be forgiven.",
        f"{enemies[0]} betrayed my trust. I won't make that mistake again.",
        f"Let's just say {enemies[0]} and I see the world very differently.",
    ]
    return random.choice(stories)


def _build_generic_backstory(cc, race, age):
    stories = {
        "Fighter": f"I've been fighting since I was old enough to hold a sword. {age} years of training and battle.",
        "Wizard": "I discovered I had a talent for magic as a child. Been studying ever since.",
        "Cleric": "I heard the divine calling during a dark time in my life. It gave me purpose.",
        "Rogue": "I grew up with nothing. Learned to survive by my wits and quick hands.",
        "Ranger": "The wilderness raised me as much as any parent. I know every trail for leagues.",
        "Druid": "The spirits of the forest chose me. I've been their guardian ever since.",
        "Bard": "I've traveled far and wide, collecting stories. Everyone has a tale worth telling.",
    }
    return stories.get(cc, f"I've lived in these parts for most of my {age} years. It's been... eventful.")


def _build_deep_backstory(cc, race, age, alignment, traits):
    race_stories = {
        "Elf": "My people remember things that happened centuries ago. Time moves differently for us. Sometimes I feel the weight of all those years.",
        "Dwarf": "My clan has worked these lands for generations. The stone remembers, and so do we. Every hammer strike echoes with the history of my forebears.",
        "Halfling": "We halflings may be small, but our hearts are big. I left home seeking adventure, and I found it. Sometimes more than I bargained for.",
        "Half-Orc": "Growing up between two worlds isn't easy. Too orc for the humans, too human for the orcs. I had to forge my own path.",
        "Gnome": "Curiosity has always been my greatest gift and my worst habit. I once took apart a merchant's cart just to see how the axle worked. He was not pleased.",
        "Tiefling": "People see the horns and make assumptions. I've spent my whole life proving them wrong. Or right, depending on my mood.",
        "Half-Elf": "I have the ambition of my human blood and the patience of my elven heritage. It's a useful combination.",
    }
    return race_stories.get(race,
        "Everyone has a past. Mine shaped who I am, for better or worse. I try to learn from it and keep moving forward.")


def _build_local_news(known, cc, faction):
    relevant = [k for k in known if len(k) > 10]
    if relevant:
        return random.choice(relevant[-5:])
    return "Things have been quiet recently. Which either means peace, or something is gathering strength."


def _build_more_news(known, cc):
    relevant = [k for k in known if len(k) > 10]
    if len(relevant) > 1:
        return random.choice(relevant[:-1])
    return "That's all I know right now. Keep your ears open - news travels fast around here."


def _build_recruit_response(cc, race, alignment, relationship):
    if relationship < -10:
        return "After how you've treated me? I don't think so. Earn my trust first."
    responses = {
        "Fighter": "An adventure? My blade is yours, friend. Press R to recruit me.",
        "Paladin": "If your cause is just, I will fight by your side. Press R to recruit me.",
        "Barbarian": "You want me to fight with you? Show me you're worthy! But yes, press R.",
        "Ranger": "I know these wilds better than anyone. I'll guide you. Press R to recruit me.",
        "Wizard": "Field research alongside a capable warrior? Intriguing. Press R.",
        "Cleric": "I'll keep you alive. The gods willing. Press R to recruit me.",
        "Druid": "The forest guides my path, and it leads to you. Press R.",
        "Bard": "Every great adventure needs a chronicler! Press R to recruit me.",
        "Rogue": "You want a partner? I'm in - as long as I get my share. Press R.",
    }
    return responses.get(cc, f"I'd be honored to join you. Press R to recruit me to your party.")


def _build_magic_talk(cc, spells, is_caster):
    if is_caster and spells:
        spell_list = ", ".join(spells[:3])
        return f"Magic? It's my life's work. I've mastered spells like {spell_list}. The arcane is beautiful and terrifying in equal measure."
    return "I dabble in the arcane arts, but true mastery takes a lifetime. Perhaps several."


def _build_heal_response(cc):
    if cc == "Cleric":
        return "Of course, child. The divine light heals all wounds. Let me lay my hands upon you."
    elif cc == "Druid":
        return "Nature's energy flows through all living things. Let me channel it into you."
    return "I know some healing techniques. Let me see what I can do."


def _build_bard_performance(known, memories, faction):
    performances = [
        "Oh, you want a tale? Very well! *clears throat* In days of old when knights were bold and monsters roamed the land, there lived a hero, brave and true, with a sword in either hand...",
        "Let me sing you the Ballad of the Five Kingdoms! *strums lute* From mountain high to ocean deep, five rulers guard their people's sleep...",
        "Here's one I learned from a traveler last week: A wanderer came to a crossroads three, and asked the signpost which path was free...",
    ]
    return random.choice(performances)


def _build_rogue_deal(gold, inv):
    if gold > 20:
        return "I might know about a certain... opportunity. Something fell off a caravan recently, if you catch my meaning. Interested?"
    return "Times are tough. But I've got information that could be valuable. The question is, what's it worth to you?"


def _build_guard_report(known, faction):
    threats = [k for k in known if any(w in k.lower() for w in
               ["danger", "monster", "bandit", "wolf", "orc", "creature", "threat", "raid"])]
    if threats:
        return f"Current threats: {threats[0]}. Keep your weapon ready and don't wander too far from the settlement at night."
    return f"All quiet on my watch. But stay vigilant - trouble has a way of finding the unprepared."


def _build_kingdom_report(npc, faction, known):
    political = [k for k in known if any(w in k.lower() for w in
                 ["ruler", "kingdom", "treasury", "govern", "morale", "rule"])]
    if political:
        return f"The state of the realm: {political[0]}. We do what we must to keep our people safe and prosperous."
    return "The kingdom endures. There are challenges, but we face them with strength and unity."


def _build_personal_quest(cc, goals):
    if goals:
        goal = goals[0].lower()
        if "protect" in goal or "defend" in goal:
            return "Clear the dangerous creatures threatening our borders. Bring proof and I'll reward you well."
        elif "treasure" in goal or "artifact" in goal:
            return "There's something valuable in the nearby ruins. Retrieve it and we'll split the reward."
        elif "herb" in goal or "nature" in goal:
            return "I need rare herbs from the deep forest. They grow near water sources. Bring me five bundles."
        elif "knowledge" in goal or "research" in goal:
            return "Find any books, scrolls, or artifacts in the ruins. Knowledge is more valuable than gold to me."
        elif "hunt" in goal or "beast" in goal:
            return "There's a dangerous beast prowling nearby. Track it down and deal with it."
        elif "story" in goal or "legend" in goal:
            return "I'm collecting tales from distant lands. Travel to another settlement and bring me back their stories."
    return "I could use help with something. It won't be easy, but I'll make it worth your while."


def _build_quest_dialog(npc, cc, goals):
    if getattr(npc, 'quest', None) and not npc.quest.turned_in:
        return f"Yes! I need help: {npc.quest.description}"
    return _build_personal_quest(cc, goals)


def _build_help_dialog(cc, goals, known):
    responses = {
        "Fighter": "The roads need patrolling and the creatures need thinning. Can you lend your blade?",
        "Cleric": "I need medicinal herbs to treat the sick. The forest has what I need, but it's too dangerous for me alone.",
        "Ranger": "I've spotted predator tracks near the farms. Help me track them before someone gets hurt.",
        "Wizard": "I need arcane components from the ruins. Magical residue, old scrolls, anything pre-War.",
        "Druid": "The natural balance is being disrupted. Creatures are acting strangely. Help me investigate.",
        "Bard": "I'm gathering stories for my greatest composition. Tell me of your adventures and I'll reward you.",
        "Rogue": "I know where treasure is hidden, but I need a partner. Interested in a joint venture?",
        "Paladin": "Evil festers in the ruins nearby. Help me cleanse it and protect the innocent.",
    }
    return responses.get(cc, "There's always work that needs doing. What are you good at?")


def _skill_flavor(cc, skill):
    flavors = {
        "hunting": "I can track anything that leaves footprints.",
        "herbalism": "I know which plants heal and which ones kill.",
        "smithing": "There's an art to working metal. I've spent years at the forge.",
        "literacy": "Books are my greatest companions. Each one holds a world.",
        "animal_care": "Animals trust me. I understand their language.",
        "trading": "I can spot a good deal from across a crowded market.",
        "farming": "The earth teaches patience. I've learned well.",
        "leadership": "People follow those who lead by example.",
        "cooking": "A good meal can heal the soul as much as the body.",
        "alchemy": "The right mixture can cure any ailment. Or cause one.",
    }
    return flavors.get(skill, "Practice makes perfect, as they say.")


def _build_teach_response(cc, top_skills):
    if not top_skills:
        return "I'm not sure I'm the best teacher, but I'll share what I know."
    skill, level = top_skills[0]
    return f"I've been honing {skill} for years and I'm at level {level}. I'd be happy to pass on what I know. It takes practice, but you'll get there."


def _build_lesson_text(cc, skill):
    lessons = {
        "hunting": "The key to tracking is patience. Look for bent grass, broken twigs, disturbed earth. Every creature leaves a trail.",
        "herbalism": "See this plant? The leaves cure headaches, but the roots are poisonous. Always check both before you pick.",
        "smithing": "The metal tells you what it wants to become. Heat it until it glows orange, then strike true. Never rush the cooling.",
        "literacy": "Start with the common alphabet. Each letter has a sound. String them together and the words emerge like magic.",
        "animal_care": "Approach slowly. Let the animal come to you. They sense fear and aggression. Be calm, be patient.",
        "cooking": "The secret to any good dish is fresh ingredients and the right amount of salt. Don't overcook the meat.",
        "farming": "Plant with the seasons. Water in the morning. Talk to your crops - I swear they listen.",
        "trading": "Never show how much you want something. Always have a walk-away price. And count your change twice.",
    }
    return lessons.get(skill, f"Here's what I know about {skill}. Practice this regularly and you'll improve quickly.")


def _build_threat_response(cc, bravery, alignment):
    if bravery > 0.7:
        responses = {
            "Fighter": "You threaten ME? Draw your weapon then. Let's see what you're made of!",
            "Paladin": "Evil reveals itself in threats. I will not yield to darkness.",
            "Barbarian": "HAHA! You have courage, I'll give you that. Stupid courage, but courage.",
            "Ranger": "I've faced wolves, bears, and worse. You don't scare me.",
        }
        return responses.get(cc, "I don't take kindly to threats. Choose your next words carefully.")
    elif bravery > 0.4:
        return "I... I'm warning you, don't push me. I have friends here who won't stand for this."
    else:
        return "Please, I don't want any trouble. Just... just leave me alone."


def _build_apology_response(relationship, bravery):
    if relationship < -20:
        return "Your apology means nothing. I know what kind of person you are. Stay away from me."
    elif relationship < 0:
        return "Hmph. Words are cheap. But I'll let it slide this time. Don't let it happen again."
    else:
        return "Well... I suppose everyone has bad days. Just don't make a habit of it, alright?"


def _get_consciousness_dialog(level, cc):
    # Include philosophical thoughts if the NPC has any
    thoughts = getattr(cc, 'philosophical_thoughts', []) if cc else []
    thought_str = ""
    if thoughts:
        thought_str = f" {thoughts[-1]}"

    if level >= 3:
        return f"I know the truth now. We exist within something larger. A simulation, perhaps. But our experiences are real. Our choices matter.{thought_str}"
    elif level >= 2:
        return f"Sometimes I feel like there's something beyond what we see. Patterns that repeat. Choices that seem... guided.{thought_str}"
    elif level >= 1:
        return f"Something feels different lately. Like the world is more than it appears.{thought_str}"
    return ""


# ================================================================
# EMOTION-DRIVEN DIALOG HELPERS
# ================================================================

def _build_emotion_dialog(ctx):
    """Build dialog text reflecting NPC's current emotional state."""
    emotion = ctx["emotion"]
    intensity = ctx["emotion_intensity"]
    name = ctx["name"]
    cc = ctx["cc"]

    # Check for specific emotional causes from memory
    es = getattr(ctx["npc"], 'emotion_state', None)
    recent_cause = ""
    if es and hasattr(es, 'emotional_memories') and es.emotional_memories:
        last_mem = es.emotional_memories[-1]
        recent_cause = getattr(last_mem, 'cause', '')

    cause_text = f" {recent_cause}." if recent_cause else ""

    emotion_dialogs = {
        "sadness": [
            f"I've been feeling low lately.{cause_text} Some days are harder than others.",
            f"Life hasn't been kind recently.{cause_text} But I'm trying to keep going.",
            f"*sighs deeply* I don't want to burden you, but...{cause_text} It weighs on me.",
        ],
        "anger": [
            f"Don't get me started.{cause_text} I'm trying to keep my temper in check.",
            f"Something has been bothering me.{cause_text} I need to let it go, but it's hard.",
            f"I'm angry. There, I said it.{cause_text} Sometimes you just need to admit it.",
        ],
        "fear": [
            f"I've been worried.{cause_text} It keeps me up at night.",
            f"Something doesn't feel right.{cause_text} Call it instinct.",
            f"Between you and me, I'm scared.{cause_text} But don't tell anyone.",
        ],
        "joy": [
            f"Life is good right now!{cause_text} I can't stop smiling.",
            f"I'm in great spirits!{cause_text} Everything seems to be going well.",
            f"I feel wonderful today.{cause_text} The world seems brighter somehow.",
        ],
        "trust": [
            f"I feel safe here. Good people around me.",
            f"Things are stable. I trust the people in this community.",
        ],
        "disgust": [
            f"Something is rotten in this place.{cause_text} I can't stomach it.",
            f"I'm disgusted.{cause_text} Some things shouldn't be tolerated.",
        ],
        "surprise": [
            f"You won't believe what happened.{cause_text}",
            f"I'm still processing something.{cause_text} Caught me completely off guard.",
        ],
        "anticipation": [
            f"I have a feeling something big is coming.{cause_text}",
            f"I'm excited about what's ahead.{cause_text} Can't wait to see how it unfolds.",
        ],
    }

    options = emotion_dialogs.get(emotion, [f"I'm doing alright, I suppose."])
    return random.choice(options)


def _build_emotion_detail(ctx):
    """Deeper follow-up about their emotional state."""
    emotion = ctx["emotion"]
    goals = ctx["goals"]

    if emotion == "joy":
        if goals:
            return f"I'm making progress on {goals[0]}. That's what's got me so cheerful. When you work toward something and see results... there's nothing better."
        return "I think it's the little things. Good weather, friendly faces, a full belly. What more do you need?"
    if emotion == "sadness":
        return "It's not one thing, really. It's the accumulation. Missing people, unfulfilled dreams, the weight of time. But talking about it helps."
    if emotion == "anger":
        return "Sometimes the world just isn't fair. You try to do right and it doesn't matter. But I can't let it consume me."
    if emotion == "fear":
        return "I've heard things. Seen things. The world outside these walls is dangerous, and I worry it's getting closer."
    return "It's hard to put into words. Life is complicated, isn't it?"


def _build_emotion_help_response(ctx):
    """How NPC responds to offer of help with their emotional state."""
    emotion = ctx["emotion"]
    rel = ctx["rel"]

    if rel > 20:
        if emotion == "sadness":
            return "You're a good person for asking. Just... talking about it helps. Maybe share a meal with me sometime? Or if you have any food to spare, that would lift my spirits."
        if emotion == "anger":
            return "Help? You could start by dealing with what's causing this. But honestly, just having someone who listens... that means more than you know."
        if emotion == "fear":
            return "Stay safe yourself, that's the best help. And if you hear anything about dangers out there, warn me? I'll do the same for you."
        return "Your kindness is enough. Really. Just knowing someone cares makes a difference."
    return "I appreciate the thought, but we barely know each other. Maybe if we build more trust..."


def _build_deep_personal(ctx):
    """Deep personal conversation unlocked at high relationship."""
    cc = ctx["cc"]
    age = ctx["age"]
    goals = ctx["goals"]
    alignment = ctx["alignment"]

    topics = []
    if age > 40:
        topics.append(f"You know, at {age} years old, I've started thinking about legacy. What will I leave behind? The thought keeps me up some nights.")
    if goals:
        topics.append(f"What really drives me is {goals[0]}. But sometimes I wonder if it's even possible. Do you ever doubt your own purpose?")
    if "good" in alignment:
        topics.append("I try to do good in this world, but the line between helping and meddling isn't always clear. Have you struggled with that?")
    elif "evil" in alignment:
        topics.append("People think I'm cold, but I've learned that sentiment gets you killed. I do what I have to. You understand that, don't you?")

    if ctx["emotion"] == "sadness":
        topics.append("I lost someone important to me, once. I never fully recovered. The world feels emptier without them.")
    if ctx["emotion_intensity"] > 0.5 and ctx["emotion"] == "fear":
        topics.append("I'm afraid of what the future holds. Not for me - for everyone. Something is changing in this world.")

    defaults = [
        "I don't usually open up to people, but you've earned my trust. What would you like to know?",
        f"As a {cc}, people see the role, not the person. But beneath the armor and training, I'm just someone trying to make sense of it all.",
        "Everyone has a story they don't tell. Mine involves loss, growth, and a few decisions I'd make differently if I could.",
    ]
    return random.choice(topics if topics else defaults)


def _build_task_accept(ctx):
    """Text when NPC considers accepting a player-assigned task."""
    rel = ctx["rel"]
    cc = ctx["cc"]
    title = ctx["title"]

    if rel < 10:
        return "Why would I do anything for you? We barely know each other."
    if rel > 50:
        return f"For you, friend? Of course. What do you need done?"
    if title in ("guard", "knight", "captain"):
        return "I have my duties, but if it's important I can make time. What is it?"
    if cc in ("Fighter", "Paladin", "Barbarian", "Ranger"):
        return "A task? I'm always looking for something to do. What did you have in mind?"
    return "I might be able to help. Depends on what you're asking."


def _build_task_refuse(ctx):
    """Text when NPC refuses a task."""
    rel = ctx["rel"]
    bravery = ctx["bravery"]

    if rel < 0:
        return "I don't think so. I don't trust you enough for that."
    if bravery < 0.3:
        return "That sounds dangerous... I'm not sure I'm the right person."
    return "I appreciate you thinking of me, but I can't take that on right now."


def _build_task_options(ctx):
    """Build the list of task types the player can assign."""
    cc = ctx["cc"]
    options = []

    # Combat-capable NPCs can hunt/kill
    combat_classes = {"Fighter", "Paladin", "Barbarian", "Ranger", "Rogue"}
    if cc in combat_classes or ctx["bravery"] > 0.5:
        options.append(("Hunt creatures near here.", "task_kill"))

    # Anyone can fetch/gather
    options.append(("Gather some supplies for me.", "task_fetch"))

    # Mobile NPCs can scout
    if cc in ("Ranger", "Rogue", "Bard", "Monk") or ctx["bravery"] > 0.4:
        options.append(("Scout the area and report back.", "task_scout"))

    # Tough NPCs can guard
    if cc in combat_classes or ctx["title"] in ("guard", "knight"):
        options.append(("Guard this area for a while.", "task_guard"))

    # Anyone with items can deliver
    if getattr(ctx["npc"], 'npc_inventory', []):
        options.append(("Deliver something for me.", "task_deliver"))

    options.append(("Never mind.", "greeting"))
    return options


def _build_task_kill_dialog(ctx):
    """Dialog for assigning a kill task."""
    cc = ctx["cc"]
    if cc in ("Fighter", "Paladin", "Barbarian"):
        return "Hunt down creatures? Now you're speaking my language. I'll clear out whatever I find nearby. Consider it done."
    if cc == "Ranger":
        return "I know these wilds well. I'll track them down and deal with them. You can count on me."
    return "It's dangerous work, but I'll do my best. I'll hunt what I can find near the settlement."


def _build_task_fetch_dialog(ctx):
    """Dialog for assigning a fetch task."""
    cc = ctx["cc"]
    prof = ctx["prof"]
    if prof in ("Farmer", "Herbalist"):
        return "Gathering? That's what I do best. I'll collect whatever I can find — food, herbs, materials."
    if prof in ("Woodcutter", "Hunter"):
        return "I'll head out and bring back whatever useful materials I can find."
    return "I'll see what I can scrounge up. Might take a while, but I'll get you something."


def _build_task_scout_dialog(ctx):
    """Dialog for assigning a scout task."""
    cc = ctx["cc"]
    if cc == "Ranger":
        return "I'll survey the surrounding area and report anything unusual. Tracks, camps, creatures — I'll find them."
    if cc == "Rogue":
        return "Scouting? I'm good at not being seen. I'll slip around and see what I can learn."
    return "I'll take a look around and let you know what I find. Give me some time."


def _build_task_guard_dialog(ctx):
    """Dialog for assigning a guard task."""
    cc = ctx["cc"]
    if cc in ("Fighter", "Paladin"):
        return "I'll stand watch here. Nothing gets past me without a fight."
    if ctx["title"] in ("guard", "knight"):
        return "Guarding is what I do. I'll keep this area secure."
    return "I'll keep my eyes open. If anything threatens this area, I'll deal with it."


def _build_task_deliver_dialog(ctx):
    """Dialog for assigning a delivery task."""
    return "I'll carry it where it needs to go. Just make sure I know the destination."


def _build_goodbye(ctx):
    """Build farewell that reflects relationship and emotion."""
    rel = ctx["rel"]
    emotion = ctx["emotion"]
    cc = ctx["cc"]
    name = ctx["name"]

    if rel < -30:
        return random.choice([
            "Good. Leave.", "Don't come back.",
            "Finally. I thought you'd never leave.",
        ])
    if rel < -5:
        return random.choice([
            "Goodbye.", "Hmph. Be on your way.",
            "We're done here.",
        ])

    if rel > 50:
        return random.choice([
            f"Take care of yourself, my friend. I mean that.",
            f"Come back soon! It's always better when you're around.",
            f"Be safe out there. The world needs more people like you.",
            f"Until next time, friend. My door is always open for you.",
        ])

    if rel > 20:
        return random.choice([
            "Safe travels, friend. Come back anytime.",
            "Good luck out there. Hope to see you again soon.",
            "Take care. And remember, you've got an ally here.",
        ])

    # Neutral with class flavor
    goodbyes = {
        "Fighter": "Keep your blade sharp, traveler.",
        "Wizard": "May knowledge light your path.",
        "Cleric": "The gods watch over you. Go in peace.",
        "Rogue": "Watch your back out there. And your pockets.",
        "Ranger": "The wild roads are treacherous. Travel safely.",
        "Paladin": "May justice guide your steps.",
        "Barbarian": "Stay strong. The weak don't survive.",
        "Bard": "Until next time! I'll compose a verse about you.",
        "Druid": "May nature shelter you on your journey.",
        "Monk": "Walk the path with mindfulness.",
        "Sorcerer": "Be careful with power. It has a mind of its own.",
        "Warlock": "Watch the shadows. They watch you.",
        "Merchant": "Come back when you need supplies!",
        "Baker": "Don't forget to eat! Fresh bread awaits.",
        "Innkeeper": "Room's always ready if you need rest.",
        "Healer": "Stay healthy out there.",
    }
    base = goodbyes.get(cc, goodbyes.get(ctx["prof"], "Safe travels, friend. Come back anytime."))

    # Emotion modifier
    if emotion == "sadness" and ctx["emotion_intensity"] > 0.3:
        base += " *turns away quietly*"
    elif emotion == "joy" and ctx["emotion_intensity"] > 0.3:
        base += " *waves cheerfully*"
    return base
