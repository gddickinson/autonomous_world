"""Dialog tree helper functions — greeting builders, emotion text, task dialogs."""

import random
from typing import Dict, List, Tuple

# Context-building functions used by dialog helpers
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




def _build_greeting(npc, cc, race, title, is_ruler, alignment, traits, ctx=None):
    """Build greeting that reflects relationship, emotion, needs, time, weather, and memory.

    Prioritizes job-specific greetings from JOB_GREETINGS, then falls back to
    class-based greetings. Relationship level overrides both for extreme values.
    """
    from game.data.job_classes import JOB_GREETINGS

    name = npc.name
    prof = npc.profession
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

    # NEUTRAL greeting (default, -5 to 20) — job/class/title specific
    if is_ruler:
        base = f"{body}Welcome to my domain. I am {name}, ruler of these lands. What brings you before me?"
    elif title == "guard":
        base = f"{body}Halt! State your business. I'm {name}, on watch duty."
    elif title == "knight":
        base = f"{body}Well met, traveler. I am Sir {name}, sworn knight of this realm."
    elif title == "duke":
        base = f"{body}Greetings. I am {name}, duke of this territory."
    elif prof in JOB_GREETINGS:
        # Job-specific greeting — prioritized over class-based
        template = random.choice(JOB_GREETINGS[prof])
        base = body + template.format(name=name)
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
            "Commoner": f"Hello there. I'm {name}, just a simple {prof.lower()}.",
        }
        base = class_greetings.get(cc,
            f"{body}Hello there. I'm {name}, a {prof.lower()} around here.")
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

    prof = npc.profession
    if prof and prof != cc:
        text = f"I'm {npc.name}, a {race} {prof.lower()} by trade."
    else:
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
    return stories.get(cc,
        f"I've lived in these parts for most of my {age} years. "
        "It's been... eventful." if cc != "Commoner" else
        f"I've worked with my hands all my life. {age} years of honest labor. "
        "It's a simple life, but it's mine.")



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
    return responses.get(cc,
        "There's always work that needs doing around here. What are you good at?")



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

    # Neutral with class flavor — try profession first, then class
    prof_goodbyes = {
        "Guard": "Stay out of trouble, citizen.",
        "Farmer": "Mind the crops if you pass through the fields.",
        "Merchant": "Come back when you need supplies!",
        "Baker": "Don't forget to eat! Fresh bread awaits.",
        "Innkeeper": "Room's always ready if you need rest.",
        "Healer": "Stay healthy out there.",
        "Blacksmith": "Keep your gear in good shape out there.",
        "Hunter": "Watch for tracks. They'll tell you everything.",
        "Fisherman": "If you're by the water, try your luck with a line.",
        "Miner": "Watch your step underground.",
        "Woodcutter": "Good timber waits for no one.",
        "Scholar": "May you find the answers you seek.",
        "Soldier": "Stay sharp out there.",
        "Captain": "Dismissed. Stay safe.",
        "Alchemist": "Don't drink anything you find in the wild.",
        "Herbalist": "Nature provides, if you know where to look.",
    }
    class_goodbyes = {
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
        "Commoner": "Take care of yourself out there.",
    }
    base = prof_goodbyes.get(ctx["prof"],
        class_goodbyes.get(cc, "Safe travels, friend. Come back anytime."))

    # Emotion modifier
    if emotion == "sadness" and ctx["emotion_intensity"] > 0.3:
        base += " *turns away quietly*"
    elif emotion == "joy" and ctx["emotion_intensity"] > 0.3:
        base += " *waves cheerfully*"
    return base


# ================================================================
# PERSONAL STORYLINE QUESTS (unlock at relationship > 30)
# ================================================================

# Each profession has a unique personal problem and quest type.
# NPCs only offer one personal quest ever (tracked via npc._personal_quest_offered).

PERSONAL_STORYLINES = {
    "Guard": {
        "dialog": "*lowers voice* Bandits killed my brother on the north "
                  "road last season. I know where their camp is but I "
                  "can't leave my post. Will you bring them to justice?",
        "quest_title": "Avenge the Fallen Guard",
        "quest_desc": "Hunt down the bandits who killed the guard's brother. "
                      "Find their camp and eliminate the threat.",
        "quest_kind": "bounty_hunt",
        "quest_target": "bandit",
        "quest_count": 3,
        "reward_gold": 60,
        "reward_xp": 50,
        "difficulty": "medium",
    },
    "Farmer": {
        "dialog": "*sighs* My crops are failing. Blight hit the fields "
                  "and nothing I've tried works. The herbalist in the "
                  "next settlement might know a cure, but I need someone "
                  "to fetch the remedy — I can't leave my land.",
        "quest_title": "Cure the Crop Blight",
        "quest_desc": "Find the herbalist and bring back a remedy for "
                      "the crop blight devastating the farmer's fields.",
        "quest_kind": "fetch",
        "quest_target": "Blight Remedy",
        "quest_count": 1,
        "reward_gold": 35,
        "reward_xp": 30,
        "difficulty": "easy",
    },
    "Merchant": {
        "dialog": "*glances around nervously* I'm being extorted. A gang "
                  "of thugs demands 'protection money' every week. If I "
                  "don't pay, they wreck my stall. I need someone to "
                  "convince them to stop. Permanently.",
        "quest_title": "End the Extortion Racket",
        "quest_desc": "Deal with the thugs extorting the merchant. "
                      "Eliminate or drive off their gang.",
        "quest_kind": "kill",
        "quest_target": "thug",
        "quest_count": 4,
        "reward_gold": 75,
        "reward_xp": 55,
        "difficulty": "medium",
    },
    "Blacksmith": {
        "dialog": "I found a vein of star-metal in the old mine, but "
                  "creatures have infested the tunnels. If someone could "
                  "clear them out and bring me a sample of the ore... "
                  "I'd forge you something legendary.",
        "quest_title": "Star-Metal Expedition",
        "quest_desc": "Clear the mine of creatures and retrieve a sample "
                      "of rare star-metal ore for the blacksmith.",
        "quest_kind": "fetch",
        "quest_target": "Star-Metal Ore",
        "quest_count": 1,
        "reward_gold": 50,
        "reward_xp": 60,
        "difficulty": "hard",
    },
    "Healer": {
        "dialog": "A plague is coming. I can feel it. I need moonpetal "
                  "flowers from the deep forest — they only bloom at "
                  "night near ancient trees. Without them, people will "
                  "die. Please, I need your help.",
        "quest_title": "Moonpetal Harvest",
        "quest_desc": "Gather moonpetal flowers from the deep forest "
                      "at night so the healer can prepare plague medicine.",
        "quest_kind": "fetch",
        "quest_target": "Moonpetal Flower",
        "quest_count": 5,
        "reward_gold": 40,
        "reward_xp": 35,
        "difficulty": "medium",
    },
    "Scholar": {
        "dialog": "I've been translating an ancient text that references "
                  "a hidden library beneath the ruins east of here. The "
                  "knowledge inside could change everything we know about "
                  "the old world. But the ruins are dangerous...",
        "quest_title": "The Hidden Library",
        "quest_desc": "Explore the ruins and find the ancient library "
                      "mentioned in the scholar's texts.",
        "quest_kind": "investigate",
        "quest_target": "ancient library",
        "quest_count": 1,
        "reward_gold": 80,
        "reward_xp": 70,
        "difficulty": "hard",
    },
    "Innkeeper": {
        "dialog": "A traveler left behind a sealed letter before he "
                  "vanished. It mentions a treasure buried near the old "
                  "bridge. I'd look myself but... running an inn doesn't "
                  "leave time for treasure hunts.",
        "quest_title": "The Vanished Traveler's Treasure",
        "quest_desc": "Follow the clues in the traveler's letter to "
                      "find the buried treasure near the old bridge.",
        "quest_kind": "investigate",
        "quest_target": "treasure",
        "quest_count": 1,
        "reward_gold": 55,
        "reward_xp": 40,
        "difficulty": "medium",
    },
    "Hunter": {
        "dialog": "There's a beast in the deep woods — bigger than "
                  "anything I've ever tracked. Killed two of my dogs. "
                  "I can't let it keep terrorizing the forest. Will you "
                  "help me hunt it down?",
        "quest_title": "The Great Beast Hunt",
        "quest_desc": "Track and slay the massive predator terrorizing "
                      "the deep woods.",
        "quest_kind": "kill",
        "quest_target": "great beast",
        "quest_count": 1,
        "reward_gold": 65,
        "reward_xp": 60,
        "difficulty": "hard",
    },
    "Baker": {
        "dialog": "Rats. Giant ones. They've infested my grain cellar "
                  "and I can hear them gnawing through the walls at "
                  "night. If I lose my grain stores, the whole village "
                  "goes hungry this winter.",
        "quest_title": "Cellar Infestation",
        "quest_desc": "Clear out the giant rats infesting the baker's "
                      "grain cellar before the stores are ruined.",
        "quest_kind": "kill",
        "quest_target": "giant rat",
        "quest_count": 6,
        "reward_gold": 25,
        "reward_xp": 20,
        "difficulty": "easy",
    },
    "Miner": {
        "dialog": "We broke into a new cavern last week and... "
                  "something's down there. Glowing eyes in the dark. "
                  "Two miners haven't come back. I need someone brave "
                  "enough to go in and find them.",
        "quest_title": "Rescue in the Deep",
        "quest_desc": "Descend into the newly opened cavern, rescue "
                      "the missing miners, and deal with whatever lurks below.",
        "quest_kind": "investigate",
        "quest_target": "missing miners",
        "quest_count": 2,
        "reward_gold": 55,
        "reward_xp": 50,
        "difficulty": "medium",
    },
}


def _build_personal_storyline(npc, ctx):
    """Build personal storyline dialog for high-relationship NPCs.

    Returns (dialog_text, quest_data) or (None, None) if no storyline
    is available. Each NPC only offers one personal quest.
    """
    # Check if already offered
    if getattr(npc, '_personal_quest_offered', False):
        return None, None

    prof = ctx["prof"]
    storyline = PERSONAL_STORYLINES.get(prof)
    if not storyline:
        return None, None

    return storyline["dialog"], storyline

