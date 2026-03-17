"""
NPC Voice System — generates alignment-aware, personality-driven dialog context.

NPCs are self-aware of their skills, attributes, relationships, goals, and
alignment. They may lie, deflect, boast, or withhold based on:
- Alignment (good NPCs are honest, evil ones manipulate, chaotic ones are evasive)
- Relationship to the person they're talking to (trust level)
- What they want from the interaction (ulterior motives)
- Personality traits (shy, boastful, deceptive, honest)
- Current emotional state (needs, mood)

This module provides:
1. build_self_knowledge() — what the NPC knows about themselves
2. build_voice_filter() — how alignment/personality modifies their speech
3. filter_response() — applies voice to a raw response (may add lies, hedging, boasting)
4. build_llm_personality_prompt() — rich personality context for LLM prompts
"""

import random
from typing import Dict, List, Optional, Tuple


# ================================================================
# ALIGNMENT VOICE PROFILES — how each alignment axis affects speech
# ================================================================

# Law-Chaos axis affects speech FORMALITY and HONESTY
LAW_CHAOS_VOICE = {
    1.0: {  # Lawful
        "tone": "formal and proper",
        "honesty": 0.95,  # almost always honest
        "deflect_chance": 0.05,
        "boast_chance": 0.1,
        "speech_style": ["I believe in order", "The law is clear", "Honor demands",
                         "It is my duty", "I follow the code"],
        "lie_style": "omission",  # lawful liars omit rather than fabricate
    },
    0.0: {  # Neutral
        "tone": "pragmatic and measured",
        "honesty": 0.7,
        "deflect_chance": 0.2,
        "boast_chance": 0.15,
        "speech_style": ["It depends", "I see both sides", "Balance is important",
                         "I do what makes sense", "Circumstances matter"],
        "lie_style": "half-truth",
    },
    -1.0: {  # Chaotic
        "tone": "casual and unpredictable",
        "honesty": 0.5,
        "deflect_chance": 0.3,
        "boast_chance": 0.25,
        "speech_style": ["Rules are for fools", "Freedom above all", "I go where I please",
                         "Who cares about that?", "Life's too short for rules"],
        "lie_style": "fabrication",  # chaotic liars make things up freely
    },
}

# Good-Evil axis affects EMPATHY and SELF-INTEREST
GOOD_EVIL_VOICE = {
    1.0: {  # Good
        "empathy": "high",
        "self_interest": 0.2,
        "share_info": 0.9,  # willing to help freely
        "share_weakness": 0.6,  # open about vulnerabilities
        "speech_style": ["I want to help", "That's terrible, let me help",
                         "Everyone deserves kindness", "We must protect each other"],
        "reaction_to_suffering": "compassion",
    },
    0.0: {  # Neutral
        "empathy": "moderate",
        "self_interest": 0.5,
        "share_info": 0.5,
        "share_weakness": 0.3,
        "speech_style": ["What's in it for me?", "Fair enough", "I mind my own business",
                         "That's not really my problem"],
        "reaction_to_suffering": "indifference",
    },
    -1.0: {  # Evil
        "empathy": "low",
        "self_interest": 0.9,
        "share_info": 0.2,  # hoards information
        "share_weakness": 0.05,  # never shows vulnerability
        "speech_style": ["Power is everything", "The weak deserve their fate",
                         "What can you do for ME?", "Trust is for fools"],
        "reaction_to_suffering": "exploitation",
    },
}


# ================================================================
# SELF-KNOWLEDGE — what an NPC knows about themselves
# ================================================================

def build_self_knowledge(npc) -> Dict[str, str]:
    """Build a dictionary of what the NPC knows about themselves.
    This is TRUTH — what they actually think/know internally.
    Whether they share it depends on voice filtering.
    """
    knowledge = {}

    # Identity
    knowledge["name"] = npc.name
    knowledge["race"] = getattr(npc, 'race', 'Human')
    knowledge["class"] = getattr(npc, 'char_class', 'adventurer')
    knowledge["age"] = str(int(getattr(npc, 'age', 30)))
    knowledge["title"] = getattr(npc, 'title', 'commoner')
    knowledge["alignment"] = getattr(npc, 'alignment', 'true neutral')

    # Attributes (self-assessment)
    attrs = getattr(npc, 'attributes', {})
    strengths = []
    weaknesses = []
    for attr, val in attrs.items():
        if attr == "perception":
            continue  # skip alias
        if val >= 7:
            strengths.append(attr)
        elif val <= 3:
            weaknesses.append(attr)
    knowledge["strengths"] = ", ".join(strengths) if strengths else "nothing exceptional"
    knowledge["weaknesses"] = ", ".join(weaknesses) if weaknesses else "nothing notable"

    # Skills (top skills they're proud of)
    skills = getattr(npc, 'npc_skills', {})
    top_skills = sorted(skills.items(), key=lambda x: -x[1])[:5]
    if top_skills:
        knowledge["best_skills"] = ", ".join(
            f"{s.replace('_',' ')} (level {l})" for s, l in top_skills if l > 0)
    else:
        knowledge["best_skills"] = "basic survival skills"

    # Goals
    goals = getattr(npc, 'long_term_goals', [])
    knowledge["goals"] = "; ".join(goals[:2]) if goals else "survive and get by"

    # Relationships
    friends = getattr(npc, 'friends', [])
    enemies = getattr(npc, 'enemies', [])
    knowledge["friends"] = ", ".join(friends[:3]) if friends else "no close friends"
    knowledge["enemies"] = ", ".join(enemies[:3]) if enemies else "no enemies"

    # Deity
    deity = getattr(npc, 'deity', None)
    knowledge["deity"] = deity if deity else "no particular god"

    # Current state
    needs = getattr(npc, 'needs', {})
    if needs.get("hunger", 100) < 30:
        knowledge["current_state"] = "starving"
    elif needs.get("thirst", 100) < 30:
        knowledge["current_state"] = "parched"
    elif needs.get("rest", 100) < 20:
        knowledge["current_state"] = "exhausted"
    else:
        knowledge["current_state"] = "doing fine"

    # Combat history from ledger
    ledger = getattr(npc, 'life_ledger', None)
    if ledger:
        kills = ledger.get_total_kills()
        deaths_known = len(ledger.deaths_witnessed)
        knowledge["combat_experience"] = f"{kills} kills" if kills > 0 else "no combat experience"
        knowledge["losses"] = f"lost {deaths_known} people" if deaths_known > 0 else "hasn't lost anyone"
    else:
        knowledge["combat_experience"] = "unknown"
        knowledge["losses"] = "unknown"

    return knowledge


# ================================================================
# VOICE FILTER — determines HOW an NPC presents information
# ================================================================

def build_voice_filter(npc, listener_trust: int = 0) -> Dict:
    """Build a voice filter based on alignment, personality, and relationship.

    Args:
        npc: The speaking NPC
        listener_trust: Trust level toward the person they're talking to (-100 to 100)

    Returns dict with:
        honesty: 0-1 how truthful they'll be
        openness: 0-1 how much they'll share
        tone: description of speech tone
        ulterior_motive: what they want from this conversation
        will_lie_about: topics they'll be deceptive about
        will_boast_about: topics they'll exaggerate
        will_hide: topics they'll refuse to discuss
    """
    alignment = getattr(npc, 'alignment', 'true neutral')
    traits = getattr(npc, 'social_traits', [])
    friendliness = getattr(npc, 'friendliness', 0.5)

    # Parse alignment
    from game.systems.alignment import ALIGNMENTS
    align_data = ALIGNMENTS.get(alignment, ALIGNMENTS["true neutral"])
    law_order = align_data.get("law_order", 0)
    good_evil = align_data.get("good_evil", 0)

    # Get voice profiles for this alignment position
    law_key = 1.0 if law_order > 0.5 else (-1.0 if law_order < -0.5 else 0.0)
    good_key = 1.0 if good_evil > 0.5 else (-1.0 if good_evil < -0.5 else 0.0)

    law_voice = LAW_CHAOS_VOICE[law_key]
    good_voice = GOOD_EVIL_VOICE[good_key]

    # Base honesty from alignment
    honesty = law_voice["honesty"]

    # Adjust for traits
    if "deceptive" in traits:
        honesty -= 0.25
    if "honest" in traits:
        honesty += 0.2
    if "treacherous" in traits:
        honesty -= 0.3

    # Adjust for trust — more honest with trusted people
    trust_mod = listener_trust / 200.0  # -0.5 to +0.5
    honesty = max(0.1, min(1.0, honesty + trust_mod))

    # Openness — how much they share
    openness = good_voice["share_info"]
    if listener_trust > 30:
        openness = min(1.0, openness + 0.2)
    elif listener_trust < -20:
        openness = max(0.1, openness - 0.3)
    if "shy" in traits or "reserved" in traits:
        openness -= 0.2
    if "generous" in traits or "compassionate" in traits:
        openness += 0.1

    # Tone
    tone_parts = [law_voice["tone"]]
    if listener_trust > 40:
        tone_parts.append("warm")
    elif listener_trust < -30:
        tone_parts.append("guarded")
    if "cheerful" in traits or "jovial" in traits:
        tone_parts.append("upbeat")
    if "gruff" in traits or "stern" in traits:
        tone_parts.append("blunt")

    # Ulterior motive
    motive = "none"
    gold = getattr(npc, 'npc_gold', 10)
    needs = getattr(npc, 'needs', {})
    if gold <= 0:
        motive = "wants money or resources"
    elif needs.get("hunger", 100) < 30:
        motive = "desperately needs food"
    elif needs.get("social", 100) < 30:
        motive = "lonely, wants companionship"
    elif good_evil < -0.5 and listener_trust < 20:
        motive = "looking for advantage or weakness"
    elif good_evil > 0.5:
        motive = "genuinely wants to help"

    # What they'll lie about, boast about, or hide
    will_lie_about = []
    will_boast_about = []
    will_hide = []

    if good_evil < -0.5:  # Evil
        will_lie_about.extend(["true intentions", "alignment", "crimes"])
        will_hide.extend(["weaknesses", "fears"])
        will_boast_about.extend(["power", "kills", "wealth"])
    elif good_evil > 0.5:  # Good
        will_boast_about.extend(["helping others", "protecting the weak"])
        will_hide.extend(["doubts", "past failures"])
    else:  # Neutral
        will_hide.extend(["personal weaknesses"])

    if law_order < -0.5:  # Chaotic
        will_lie_about.append("past crimes")
        will_boast_about.append("freedom")
    elif law_order > 0.5:  # Lawful
        will_boast_about.append("duty and honor")

    # Traits modify
    if "greedy" in traits:
        will_hide.append("wealth")
        will_lie_about.append("how much gold I have")
    if "brave" in traits:
        will_boast_about.append("combat prowess")
    if "cowardly" in traits or "cautious" in traits:
        will_hide.append("fears")
    if "deceptive" in traits:
        will_lie_about.append("true feelings")

    return {
        "honesty": max(0.1, min(1.0, honesty)),
        "openness": max(0.1, min(1.0, openness)),
        "tone": " and ".join(tone_parts[:2]),
        "ulterior_motive": motive,
        "will_lie_about": will_lie_about,
        "will_boast_about": will_boast_about,
        "will_hide": will_hide,
        "share_weakness": good_voice["share_weakness"],
        "speech_style": law_voice["speech_style"] + good_voice["speech_style"],
    }


# ================================================================
# RESPONSE FILTERING — modify raw responses through voice filter
# ================================================================

def filter_self_disclosure(npc, topic: str, raw_truth: str,
                           listener_trust: int = 0) -> str:
    """Filter what an NPC says about themselves based on alignment and trust.

    Args:
        npc: The speaking NPC
        topic: What kind of info ("skills", "goals", "weakness", "wealth", "alignment")
        raw_truth: The truthful answer
        listener_trust: Trust level toward listener

    Returns the filtered response — may be truth, lie, deflection, or boast.
    """
    voice = build_voice_filter(npc, listener_trust)
    alignment = getattr(npc, 'alignment', 'true neutral')
    traits = getattr(npc, 'social_traits', [])

    # Check if this topic should be hidden
    if topic in voice["will_hide"] or any(topic in h for h in voice["will_hide"]):
        if random.random() > voice["openness"]:
            return _deflect(npc, topic)

    # Check if this topic should be lied about
    if topic in voice["will_lie_about"] or any(topic in l for l in voice["will_lie_about"]):
        if random.random() > voice["honesty"]:
            return _fabricate(npc, topic, raw_truth)

    # Check if this topic should be boasted about
    if topic in voice["will_boast_about"] or any(topic in b for b in voice["will_boast_about"]):
        if random.random() < 0.4:
            return _boast(npc, topic, raw_truth)

    # Trust gate — won't share personal info with strangers
    if topic in ("weakness", "fears", "true feelings") and listener_trust < 20:
        if random.random() > voice["share_weakness"]:
            return _deflect(npc, topic)

    return raw_truth


def _deflect(npc, topic: str) -> str:
    """Generate a deflection — NPC avoids the topic."""
    alignment = getattr(npc, 'alignment', 'true neutral')
    deflections = {
        "skills": [
            "I get by. That's all you need to know.",
            "A person's skills are their own business.",
            "Why do you want to know what I can do?",
            "Let's talk about something else.",
        ],
        "weakness": [
            "Everyone has weaknesses. I don't dwell on mine.",
            "Ha! You'd like to know, wouldn't you?",
            "I'm not in the habit of sharing my vulnerabilities with strangers.",
        ],
        "goals": [
            "My plans are my own, friend.",
            "I prefer to keep my ambitions close to the chest.",
            "Ask me again when I know you better.",
        ],
        "wealth": [
            "A wise person doesn't discuss their purse.",
            "Enough to get by. That's all I'll say.",
            "Why, planning to rob me?",
        ],
        "alignment": [
            "I am what I am. Make of that what you will.",
            "Labels are for bottles, not people.",
            "I follow my own path.",
        ],
    }
    options = deflections.get(topic, [
        "I'd rather not talk about that.",
        "That's personal.",
        "Another time, perhaps.",
    ])
    return random.choice(options)


def _fabricate(npc, topic: str, truth: str) -> str:
    """Generate a lie — NPC provides false information."""
    alignment = getattr(npc, 'alignment', 'true neutral')

    if topic == "goals":
        lies = [
            "Oh, nothing special. Just living peacefully.",
            "I'm simply a humble traveler, same as you.",
            "I want what everyone wants — a quiet life.",
        ]
        return random.choice(lies)
    elif topic == "wealth":
        return "I'm just scraping by, honestly. Barely have enough to eat."
    elif topic in ("alignment", "true intentions"):
        if "evil" in alignment:
            return "I'm just trying to do right by people. Help where I can."
        else:
            return truth  # good-aligned NPCs rarely lie about morals
    elif topic == "crimes":
        return "Me? I've never broken a law in my life."
    elif topic == "true feelings":
        return "I'm fine. Everything's fine."
    return truth  # fallback to truth if no lie pattern


def _boast(npc, topic: str, truth: str) -> str:
    """Generate a boast — NPC exaggerates."""
    if topic in ("combat prowess", "power", "kills"):
        kills = 0
        ledger = getattr(npc, 'life_ledger', None)
        if ledger:
            kills = ledger.get_total_kills()
        if kills > 0:
            exaggerated = kills * random.randint(2, 4)
            return f"I've defeated more foes than I can count. At least {exaggerated}, by my reckoning."
        return "I've seen more battles than most warriors twice my age."
    elif topic in ("duty and honor", "helping others"):
        return truth + " — and I wouldn't have it any other way."
    elif topic == "freedom":
        return "Nobody tells me what to do. I answer to no one but myself."
    return truth


# ================================================================
# LLM PERSONALITY PROMPT — rich context for the LLM
# ================================================================

def build_llm_personality_prompt(npc, listener_trust: int = 0) -> str:
    """Build a rich personality context block for LLM prompts.
    This tells the LLM WHO the NPC is and HOW they speak.
    """
    knowledge = build_self_knowledge(npc)
    voice = build_voice_filter(npc, listener_trust)
    alignment = getattr(npc, 'alignment', 'true neutral')
    traits = getattr(npc, 'social_traits', [])
    deity = getattr(npc, 'deity', None)

    lines = []
    lines.append(f"You are {knowledge['name']}, a {knowledge['age']}-year-old "
                 f"{knowledge['race']} {knowledge['class']}.")
    lines.append(f"Alignment: {alignment}. Title: {knowledge['title']}.")
    lines.append(f"Personality: {', '.join(traits)}. Tone: {voice['tone']}.")

    # Self-awareness
    lines.append(f"Your strengths: {knowledge['strengths']}.")
    lines.append(f"Your best skills: {knowledge['best_skills']}.")
    lines.append(f"Your goals: {knowledge['goals']}.")

    if deity:
        lines.append(f"You worship {deity}.")
    if knowledge["friends"] != "no close friends":
        lines.append(f"Your friends: {knowledge['friends']}.")
    if knowledge["enemies"] != "no enemies":
        lines.append(f"Your enemies: {knowledge['enemies']}.")

    # Ledger context
    ledger = getattr(npc, 'life_ledger', None)
    if ledger:
        narrative = ledger.narrate_full()
        if narrative:
            lines.append(f"Life history: {narrative}")

    # Voice instructions
    lines.append("")
    lines.append("SPEECH RULES:")
    if voice["honesty"] < 0.5:
        lines.append("- You are often dishonest. Lie, deflect, or exaggerate freely.")
    elif voice["honesty"] < 0.75:
        lines.append("- You shade the truth when it benefits you.")
    else:
        lines.append("- You are generally honest and straightforward.")

    if voice["openness"] < 0.3:
        lines.append("- You are very guarded. Share little about yourself.")
    elif voice["openness"] < 0.6:
        lines.append("- You share some things but keep personal matters private.")
    else:
        lines.append("- You are open and willing to share freely.")

    if voice["ulterior_motive"] != "none":
        lines.append(f"- You have an ulterior motive: {voice['ulterior_motive']}.")

    if voice["will_lie_about"]:
        lines.append(f"- You will lie about: {', '.join(voice['will_lie_about'])}.")
    if voice["will_hide"]:
        lines.append(f"- You will refuse to discuss: {', '.join(voice['will_hide'])}.")
    if voice["will_boast_about"]:
        lines.append(f"- You tend to boast about: {', '.join(voice['will_boast_about'])}.")

    # Alignment-specific speech guidance
    if "evil" in alignment:
        lines.append("- You are self-serving. Manipulate others for advantage.")
        lines.append("- Present a pleasant face but always seek benefit for yourself.")
    if "good" in alignment:
        lines.append("- You genuinely care about others' wellbeing.")
        lines.append("- You offer help freely and feel responsible for those around you.")
    if "chaotic" in alignment:
        lines.append("- You are informal, spontaneous, and dismiss rules and authority.")
    if "lawful" in alignment:
        lines.append("- You are formal, principled, and respect hierarchy and tradition.")

    # Current state
    lines.append(f"\nCurrent state: {knowledge['current_state']}.")

    return "\n".join(lines)


# ================================================================
# MOCK DIALOG MODIFIERS — for non-LLM dialog generation
# ================================================================

def get_alignment_greeting_modifier(npc) -> str:
    """Get an alignment-appropriate greeting prefix/suffix."""
    alignment = getattr(npc, 'alignment', 'true neutral')

    if "lawful good" == alignment:
        return random.choice(["May the light guide you.", "Well met, friend.",
                              "Honor and justice to you."])
    elif "chaotic good" == alignment:
        return random.choice(["Hey there!", "What's the word?",
                              "Good to see a friendly face."])
    elif "lawful evil" == alignment:
        return random.choice(["State your business.", "I trust you have a purpose here.",
                              "Speak, and be brief."])
    elif "chaotic evil" == alignment:
        return random.choice(["What do you want?", "Better make this worth my time.",
                              "Heh, fresh meat."])
    elif "neutral evil" == alignment:
        return random.choice(["Ah, a visitor. How... interesting.",
                              "What brings you to my attention?",
                              "I'm listening. For now."])
    elif "chaotic neutral" == alignment:
        return random.choice(["Oh, hey! You look like fun.",
                              "No rules, no problems. What's up?",
                              "Life's an adventure, right?"])
    elif "lawful neutral" == alignment:
        return random.choice(["Greetings. I hope you're here on legitimate business.",
                              "Welcome. Please conduct yourself properly.",
                              "Good day. How may I help you?"])
    elif "neutral good" == alignment:
        return random.choice(["Hello! How can I help?",
                              "Welcome, traveler. You're safe here.",
                              "Good to see you. Need anything?"])
    else:  # true neutral
        return random.choice(["Hello.", "Greetings.",
                              "What brings you here?"])


def get_skill_response_filtered(npc, listener_trust: int = 0) -> str:
    """Generate a filtered response about the NPC's skills."""
    skills = getattr(npc, 'npc_skills', {})
    top = sorted(skills.items(), key=lambda x: -x[1])[:4]
    if not top:
        return "I have a few useful tricks. Nothing worth bragging about."

    raw_truth = "My skills include " + ", ".join(
        f"{s.replace('_',' ')} (level {l})" for s, l in top) + "."

    return filter_self_disclosure(npc, "skills", raw_truth, listener_trust)


def get_goals_response_filtered(npc, listener_trust: int = 0) -> str:
    """Generate a filtered response about the NPC's goals."""
    goals = getattr(npc, 'long_term_goals', [])
    if not goals:
        raw = "I'm just trying to get by, day by day."
    else:
        raw = "What I really want is to " + goals[0].lower() + "."
        if len(goals) > 1:
            raw += " Also, to " + goals[1].lower() + "."

    return filter_self_disclosure(npc, "goals", raw, listener_trust)


def get_alignment_response_filtered(npc, listener_trust: int = 0) -> str:
    """Generate a filtered response about the NPC's values/morals."""
    alignment = getattr(npc, 'alignment', 'true neutral')

    # What they'd truthfully say about their values
    truth_map = {
        "lawful good": "I believe in justice, honor, and protecting the innocent.",
        "neutral good": "I try to do good wherever I can, rules or no rules.",
        "chaotic good": "I follow my heart. If a rule is unjust, I break it.",
        "lawful neutral": "I believe in order and structure above all else.",
        "true neutral": "I try to maintain balance. Extremes of any kind concern me.",
        "chaotic neutral": "Freedom is everything. I refuse to be bound by anyone's rules.",
        "lawful evil": "Power through discipline. The strong should lead, the weak should follow.",
        "neutral evil": "I look out for myself. That's the only honest way to live.",
        "chaotic evil": "The world is cruel. Why shouldn't I take what I want?",
    }
    raw = truth_map.get(alignment, "I try to live my life as best I can.")

    return filter_self_disclosure(npc, "alignment", raw, listener_trust)


def get_wealth_response_filtered(npc, listener_trust: int = 0) -> str:
    """Generate a filtered response about wealth."""
    gold = getattr(npc, 'npc_gold', 0)
    if gold > 50:
        raw = f"I've saved up a decent amount. About {int(gold)} gold coins."
    elif gold > 10:
        raw = "I'm getting by. Not rich, but not starving either."
    else:
        raw = "Times are hard. My purse is nearly empty."

    return filter_self_disclosure(npc, "wealth", raw, listener_trust)
