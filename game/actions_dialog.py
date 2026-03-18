"""Dialog action handlers — free-text chat, LLM responses, conversation impact."""

import random
import time
from game.settings import *
from game.ai.prompts import Prompts, build_npc_context


def send_player_text(game):
    """Send player's typed text to LLM for NPC response."""
    npc = game.ui.dialog_npc
    text = game.ui.get_and_clear_input()
    if not npc or not text:
        return

    # Freeze the NPC
    npc.current_action = "talking"
    npc.state = "socializing"
    npc.state_timer = 30.0
    npc.target_x = None
    npc.target_y = None

    # Build prompt
    loc = game.world.get_structure_at(npc.x, npc.y)
    loc_name = loc.name if loc else "the wilderness"
    recent_memories = "\n".join(npc.get_recent_memories(3)) if npc.memories else "none"

    race = getattr(npc, 'race', '')
    char_class = getattr(npc, 'char_class', npc.profession)
    goals = ", ".join(getattr(npc, 'long_term_goals', []))

    # Build situational context (activity, economy, world events)
    sim = getattr(game, 'simulation', None)
    npc_context = build_npc_context(
        npc, world=game.world,
        world_effects=getattr(sim, 'world_effects', None) if sim else None,
        governance=getattr(sim, 'governance', None) if sim else None,
        time_sys=getattr(sim, 'time_sys', None) if sim else None,
        event_log=getattr(sim, 'event_log', None) if sim else None,
        economy=getattr(sim, 'economy', None) if sim else None,
    )

    prompt = Prompts.npc_dialog(
        npc_name=npc.name,
        profession=f"{race} {char_class}",
        personality=npc.personality_desc,
        consciousness=npc.consciousness,
        player_question=text,
        location=loc_name,
        relationship=npc.player_relationship,
        npc=npc,
        npc_context=npc_context,
    )
    prompt += f"\n\nYour state: {npc.needs_summary()}. Inventory: {npc.inventory_summary()}."
    prompt += f"\nYour goals: {goals or 'none'}."
    if recent_memories != "none":
        prompt += f"\nRecent memories: {recent_memories}"
    known = "; ".join(npc.known_info[-3:]) if getattr(npc, 'known_info', None) else ""
    if known:
        prompt += f"\nWorld knowledge: {known}"

    def _on_response(response_text, _npc=npc, _player_text=text, _game=game):
        # Strip any narrative/quotation marks from response
        clean = response_text.strip().strip('"').strip("'")
        # Remove common narrative prefixes
        for prefix in ["*", "He says", "She says", "They say", "he replied", "she replied"]:
            if clean.lower().startswith(prefix.lower()):
                clean = clean[len(prefix):].strip().strip(",").strip()
        clean = clean.strip('"').strip("*").strip()

        _game.ui.set_llm_response(clean)
        _npc.add_memory("conversation", f"Player said: {_player_text[:50]}", 3)
        _npc.add_memory("conversation", f"I replied: {clean[:50]}", 2)
        _npc.current_action = ""
        _npc.state = "idle"

        # Assess conversation impact (second LLM call or rule-based)
        _assess_conversation_impact(_game, _npc, _player_text, clean)

    if game.llm.enabled:
        game.llm.request(f"dialog_{npc.name}_{time.time():.0f}", prompt,
                         callback=_on_response, max_tokens=150, priority=100)
        if not game.ui.llm_response_text:
            game.ui.llm_waiting = True
    else:
        # LLM fallback: generate a scripted response based on context
        fallback = _generate_fallback_response(npc, text)
        game.ui.set_llm_response(fallback)
        npc.add_memory("conversation", f"I replied: {fallback[:50]}", 2)
        _assess_conversation_impact(game, npc, text, fallback)

    npc.add_memory("conversation", f"Player said: {text[:60]}", 3)
    game.player.gain_skill_xp("persuasion", 0.5)
    npc.needs["social"] = min(100, npc.needs.get("social", 50) + 10)


def _generate_fallback_response(npc, player_text: str) -> str:
    """Generate a scripted NPC response when LLM is unavailable."""
    text_lower = player_text.lower()
    cc = getattr(npc, 'char_class', npc.profession)
    rel = getattr(npc, 'player_relationship', 0)
    name = npc.name

    # Check for keywords and give contextual responses
    if any(w in text_lower for w in ["hello", "hi ", "hey", "greetings"]):
        if rel > 20:
            return "Hello, friend! Always good to see you."
        return f"Hello there. What can I do for you?"

    if any(w in text_lower for w in ["trade", "buy", "sell", "shop", "wares"]):
        if npc.shop_items:
            return "Of course! Let me show you what I have. Go back to the menu and select 'Show me your wares.'"
        elif getattr(npc, 'npc_inventory', []):
            return "I'm not a formal merchant, but I might have something you'd want. Ask about trading from the menu."
        return "I'm afraid I don't have much to trade right now."

    if any(w in text_lower for w in ["help", "quest", "job", "work", "task"]):
        goals = getattr(npc, 'long_term_goals', [])
        if goals:
            return f"Actually, I could use help with something. {goals[0]}. Ask me about work from the dialog menu."
        return "I appreciate the offer. I'll keep it in mind if something comes up."

    if any(w in text_lower for w in ["thank", "thanks"]):
        return random.choice(["You're welcome!", "Don't mention it.", "Anytime, friend.", "Happy to help."])

    if any(w in text_lower for w in ["sorry", "apologize", "forgive"]):
        if rel < 0:
            return "Words are cheap. But... I suppose we all make mistakes."
        return "No need to apologize. We're all just doing our best."

    if any(w in text_lower for w in ["fight", "battle", "monster", "danger"]):
        if cc in ("Fighter", "Paladin", "Barbarian", "Ranger"):
            return "I know a thing or two about fighting. The key is to stay calm and pick your moment."
        return "Be careful out there. The world is more dangerous than it looks."

    if any(w in text_lower for w in ["love", "feel", "emotion"]):
        es = getattr(npc, 'emotion_state', None)
        if es:
            dom = es.dominant_emotion() if hasattr(es, 'dominant_emotion') else ("calm", 0.1)
            return f"How do I feel? Honestly, I'd say I'm feeling {dom[0]} right now. Life is complicated."
        return "That's a deep question. I'm not sure how to answer it."

    if any(w in text_lower for w in ["weather", "rain", "sun", "storm", "cold", "hot"]):
        return random.choice([
            "The weather has been something, hasn't it? Affects everything we do around here.",
            "I try not to let the weather bother me, but it does affect my work.",
        ])

    if any(w in text_lower for w in ["family", "friend", "wife", "husband", "child"]):
        friends = getattr(npc, 'friends', [])
        if friends:
            return f"My closest companions are {', '.join(friends[:2])}. They mean the world to me."
        return "I keep to myself mostly. But I'm grateful for the people in my life."

    # Generic contextual responses based on NPC personality
    if rel > 30:
        generics = [
            "That's interesting! Tell me more.",
            "I appreciate you sharing that with me.",
            f"You know, I was thinking about something similar.",
            "Hmm, I hadn't considered that before.",
        ]
    elif rel < -10:
        generics = [
            "Hmm. Is that so.", "I don't have much to say about that.",
            "Can we talk about something else?",
        ]
    else:
        generics = [
            "Interesting. I'll have to think about that.",
            "I see what you mean.", "That's a fair point.",
            f"As a {cc}, I have my own perspective on that.",
            "Life in these parts teaches you a lot about that sort of thing.",
        ]
    return random.choice(generics)


def _assess_conversation_impact(game, npc, player_said: str, npc_replied: str):
    """Assess the social impact of a player-NPC conversation and apply consequences."""
    import re

    race = getattr(npc, 'race', '')
    char_class = getattr(npc, 'char_class', npc.profession)

    if game.llm.enabled:
        # Use LLM to assess impact
        prompt = Prompts.assess_conversation(
            npc.name, npc.personality_desc, race, char_class,
            npc.player_relationship, player_said, npc_replied
        )

        def _on_assessment(result_text, _npc=npc, _game=game, _said=player_said):
            trust, mood, action = _parse_assessment(result_text)
            _apply_conversation_effects(_game, _npc, trust, mood, action, _said)

        game.llm.request(f"assess_{npc.name}_{time.time():.0f}", prompt,
                         callback=_on_assessment, max_tokens=30, priority=80)
    else:
        # Rule-based assessment
        trust, mood, action = _rule_based_assessment(player_said, npc)
        _apply_conversation_effects(game, npc, trust, mood, action, player_said)


def _parse_assessment(text: str):
    """Parse LLM assessment: TRUST:+5 MOOD:+3 ACTION:none"""
    import re
    trust = 0
    mood = 0
    action = "none"

    trust_match = re.search(r'TRUST:\s*([+-]?\d+)', text)
    if trust_match:
        trust = int(trust_match.group(1))

    mood_match = re.search(r'MOOD:\s*([+-]?\d+)', text)
    if mood_match:
        mood = int(mood_match.group(1))

    action_match = re.search(r'ACTION:\s*(\w+)', text)
    if action_match:
        action = action_match.group(1).lower()

    return max(-10, min(10, trust)), max(-10, min(10, mood)), action


def _rule_based_assessment(player_said: str, npc):
    """Simple keyword-based assessment when no LLM is available."""
    said = player_said.lower()
    trust = 0
    mood = 0
    action = "none"

    # Positive keywords
    positive_words = {"thank", "help", "friend", "please", "kind", "brave", "great",
                      "wonderful", "beautiful", "impressive", "respect", "admire",
                      "love", "like", "good", "nice", "agree", "yes", "ally"}
    negative_words = {"stupid", "ugly", "hate", "kill", "die", "fool", "idiot",
                      "coward", "weak", "useless", "pathetic", "shut up", "leave",
                      "threat", "attack", "fight", "enemy", "liar", "thief", "scum"}
    trade_words = {"buy", "sell", "trade", "deal", "price", "gold", "offer", "barter"}
    help_words = {"help", "assist", "need", "please", "quest", "join", "together", "party"}

    pos_count = sum(1 for w in positive_words if w in said)
    neg_count = sum(1 for w in negative_words if w in said)

    if pos_count > neg_count:
        trust = min(8, pos_count * 3)
        mood = min(8, pos_count * 3)
    elif neg_count > pos_count:
        trust = max(-10, neg_count * -4)
        mood = max(-10, neg_count * -4)
        if neg_count >= 2 and npc.bravery > 0.5:
            action = "fight"
        elif neg_count >= 2:
            action = "flee"

    if any(w in said for w in trade_words):
        action = "trade"
        trust = max(trust, 1)

    if any(w in said for w in help_words):
        action = "help"
        trust = max(trust, 2)
        mood = max(mood, 2)

    return trust, mood, action


def _apply_conversation_effects(game, npc, trust_change: int, mood_change: int,
                                 action: str, player_said: str):
    """Apply the assessed conversation effects to the NPC and game state."""
    # Apply trust/relationship change
    old_rel = npc.player_relationship
    npc.player_relationship = max(-100, min(100, npc.player_relationship + trust_change))

    # Apply mood
    npc.mood = max(-1.0, min(1.0, getattr(npc, 'mood', 0) + mood_change * 0.05))

    # Update social system if available
    if hasattr(game, 'simulation') and hasattr(game.simulation, 'social'):
        rel = game.simulation.social.get_rel(npc.name, "Player")
        rel.trust = npc.player_relationship
        rel.interaction_count += 1
        rel.update_status()

    # Notify player of relationship change
    if trust_change > 3:
        game.notifications.add(f"{npc.name} likes what you said (+{trust_change} trust)", 3.0, GREEN)
    elif trust_change < -3:
        game.notifications.add(f"{npc.name} is offended ({trust_change} trust)", 3.0, RED)

    # Significant relationship shifts
    if old_rel >= -10 and npc.player_relationship < -10:
        game.notifications.add(f"{npc.name} now considers you a rival!", 4.0, RED)
        npc.add_memory("social", "The player has become my rival", 4)
    elif old_rel < 20 and npc.player_relationship >= 20:
        game.notifications.add(f"{npc.name} now considers you a friend!", 4.0, GREEN)
        npc.add_memory("social", "The player has become my friend", 4)

    # Action consequences
    if action == "fight":
        npc.combat_target = game.player
        npc.current_action = "fighting"
        npc.state = "fighting"
        npc.add_memory("conflict", f"Player angered me: {player_said[:40]}", 5)
        game.notifications.add(f"{npc.name} attacks you!", 3.0, RED)

    elif action == "flee":
        npc.flee_from(game.player.x, game.player.y)
        npc.add_memory("conflict", f"Player scared me: {player_said[:40]}", 4)

    elif action == "follow":
        # NPC wants to follow/help the player
        npc.current_goal = "follow and help the player"
        npc.current_action = "approaching_player"
        npc.approach_reason = "I want to join you"
        npc.add_memory("social", "I've decided to follow the player", 4)
        game.notifications.add(f"{npc.name} wants to follow you!", 4.0, YELLOW)

    elif action == "help":
        npc.current_goal = "help the player"
        npc.add_memory("social", f"Player asked for help: {player_said[:40]}", 3)

    elif action == "trade":
        if npc.shop_items:
            game.ui.open_shop(npc)

    # NPC-to-NPC influence: friends of this NPC also adjust relationship
    for friend_name in getattr(npc, 'friends', []):
        for other_npc in game.world_mgr.npcs:
            if other_npc.name == friend_name and other_npc.alive:
                # Friends share opinions (smaller effect)
                other_npc.player_relationship = max(-100, min(100,
                    other_npc.player_relationship + trust_change // 3))
                if abs(trust_change) > 5:
                    other_npc.known_info.append(
                        f"{npc.name} {'likes' if trust_change > 0 else 'dislikes'} the player")
                break


