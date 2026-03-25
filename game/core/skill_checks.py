"""Skill check system for dialog interactions.

Handles D20 + ability modifier rolls against difficulty classes (DC).
Used by dialog_trees.py for [Intimidate], [Persuade], and [Deception]
options during NPC conversations.

Roll format: D20 + CHA modifier vs DC
- DC 12: basic checks
- DC 16: hard checks
- DC 20: very hard checks

On failure: NPC relationship decreases, may refuse to talk temporarily.
Results are shown as: "[Intimidate: 14 vs DC 12 -- Success!]"
"""

import random
from typing import Tuple


# ================================================================
# DIFFICULTY CLASSES
# ================================================================

DC_BASIC = 12
DC_HARD = 16
DC_VERY_HARD = 20


# ================================================================
# SKILL CHECK ROLL
# ================================================================

def _get_cha_modifier(player) -> int:
    """Extract CHA modifier from a player object."""
    from game.data.dnd import ability_modifier
    scores = getattr(player, 'ability_scores', {})
    cha_score = scores.get("charisma", 10)
    return ability_modifier(cha_score)


def roll_skill_check(skill_name: str, player, dc: int) -> Tuple[bool, int, str]:
    """Perform a D20 + CHA modifier skill check.

    Args:
        skill_name: "Intimidate", "Persuade", or "Deception"
        player: the player object (needs ability_scores)
        dc: difficulty class to beat

    Returns:
        (success, total_roll, result_text)
        result_text is like "[Intimidate: 14 vs DC 12 -- Success!]"
    """
    d20 = random.randint(1, 20)
    cha_mod = _get_cha_modifier(player)

    # Bonus from relevant player skills
    skill_bonus = 0
    skills = getattr(player, 'skills', {})
    if skill_name == "Intimidate":
        skill_bonus = skills.get("intimidation", 0)
    elif skill_name == "Persuade":
        skill_bonus = skills.get("persuasion", 0)
    elif skill_name == "Deception":
        skill_bonus = skills.get("deception", 0)

    # Proficiency bonus applies if skill level >= 2
    prof_bonus = 0
    if skill_bonus >= 2:
        prof_bonus = getattr(player, 'proficiency_bonus', 2)

    total = d20 + cha_mod + prof_bonus
    success = total >= dc

    # Natural 20 always succeeds, natural 1 always fails
    if d20 == 20:
        success = True
    elif d20 == 1:
        success = False

    status = "Success!" if success else "Failed."
    mod_str = f"+{cha_mod}" if cha_mod >= 0 else str(cha_mod)
    detail = f"d20({d20}){mod_str}"
    if prof_bonus > 0:
        detail += f"+prof({prof_bonus})"
    result_text = f"[{skill_name}: {detail}={total} vs DC {dc} -- {status}]"

    return success, total, result_text


# ================================================================
# DIALOG OUTCOMES — what happens after a check
# ================================================================

def intimidate_outcome(npc, player, dc: int = DC_BASIC) -> Tuple[str, str, list]:
    """Resolve an intimidation attempt on an NPC.

    Returns:
        (result_text, npc_response, follow_up_options)
    """
    success, total, result_text = roll_skill_check("Intimidate", player, dc)
    bravery = getattr(npc, 'bravery', 0.5)
    gold = int(getattr(npc, 'npc_gold', 0))

    if success:
        # NPC is scared — give gold, relationship drops slightly
        amount = max(1, gold // 3)
        npc_response = (
            f"{result_text}\n"
            f"*gulps nervously* F-fine! Take {amount} gold, just leave me alone!"
        )
        follow_up = [
            ("Take the gold.", "intimidate_take_gold"),
            ("I was just testing you. Keep it.", "apologize"),
        ]
        # Relationship drops on success (they fear you)
        npc.player_relationship = max(-100,
                                       npc.player_relationship - 5)
    else:
        npc_response = (
            f"{result_text}\n"
            f"Ha! You think you can scare me? I've faced worse than you!"
        )
        if bravery > 0.6:
            npc_response += " Now get out of my sight."
        follow_up = [
            ("[Back down] Sorry, bad joke.", "apologize"),
            ("[Press further] I mean it.", "threaten"),
        ]
        # Relationship drops more on failure
        npc.player_relationship = max(-100,
                                       npc.player_relationship - 10)
        # NPC may refuse to talk for a while
        _apply_talk_cooldown(npc)

    return result_text, npc_response, follow_up


def persuade_outcome(npc, player, dc: int = DC_BASIC,
                     context: str = "general") -> Tuple[str, str, list]:
    """Resolve a persuasion attempt on an NPC.

    Context can be: "general", "discount", "quest_reward", "information"
    Returns:
        (result_text, npc_response, follow_up_options)
    """
    success, total, result_text = roll_skill_check("Persuade", player, dc)

    if success:
        if context == "discount":
            npc_response = (
                f"{result_text}\n"
                "You drive a hard bargain... but fine, I'll give you "
                "a 20% discount. Just this once."
            )
            follow_up = [
                ("Thank you! Show me your wares.", "shop"),
                ("Much appreciated. Farewell.", "goodbye"),
            ]
        elif context == "quest_reward":
            npc_response = (
                f"{result_text}\n"
                "Hmm, you make a fair point. I suppose the reward "
                "could be a bit more generous. Fine, extra gold for you."
            )
            follow_up = [
                ("A pleasure doing business.", "greeting"),
                ("I'll get right on it.", "goodbye"),
            ]
        elif context == "information":
            npc_response = (
                f"{result_text}\n"
                "*leans in close* Alright, I'll tell you what I know, "
                "but you didn't hear it from me..."
            )
            follow_up = [
                ("Go on, I'm listening.", "gossip"),
                ("Your secret is safe with me.", "goodbye"),
            ]
        else:
            npc_response = (
                f"{result_text}\n"
                "You know what, you're right. I'll help you out."
            )
            follow_up = [
                ("Thank you.", "greeting"),
                ("I knew you'd see reason.", "goodbye"),
            ]
        # Small relationship boost on persuasion success
        npc.player_relationship = min(100,
                                       npc.player_relationship + 3)
    else:
        npc_response = (
            f"{result_text}\n"
            "Nice try, but I wasn't born yesterday. "
            "You'll have to do better than that."
        )
        follow_up = [
            ("Fair enough.", "greeting"),
            ("Worth a shot.", "goodbye"),
        ]
        npc.player_relationship = max(-100,
                                       npc.player_relationship - 5)
        _apply_talk_cooldown(npc)

    return result_text, npc_response, follow_up


def deception_outcome(npc, player, dc: int = DC_BASIC,
                      context: str = "general") -> Tuple[str, str, list]:
    """Resolve a deception attempt on an NPC.

    Context can be: "general", "free_item", "avoid_combat", "fake_authority"
    Returns:
        (result_text, npc_response, follow_up_options)
    """
    success, total, result_text = roll_skill_check("Deception", player, dc)
    inv = getattr(npc, 'npc_inventory', [])

    if success:
        if context == "free_item" and inv:
            item_name = inv[0].name if hasattr(inv[0], 'name') else str(inv[0])
            npc_response = (
                f"{result_text}\n"
                f"Oh, of course! I didn't realize. Here, take this "
                f"{item_name} — my apologies for the confusion."
            )
            follow_up = [
                ("Thank you kindly.", "goodbye"),
                ("No worries at all.", "greeting"),
            ]
        elif context == "avoid_combat":
            npc_response = (
                f"{result_text}\n"
                "Wait, you're right — there's no need for violence here. "
                "I must have been mistaken. Let's go our separate ways."
            )
            follow_up = [
                ("Wise decision.", "goodbye"),
                ("Indeed. No hard feelings.", "greeting"),
            ]
        elif context == "fake_authority":
            npc_response = (
                f"{result_text}\n"
                "My lord! I didn't recognize you. Please forgive my "
                "rudeness. How may I serve you?"
            )
            follow_up = [
                ("At ease. Tell me what you know.", "local_news"),
                ("I require your assistance.", "help_offer"),
            ]
        else:
            npc_response = (
                f"{result_text}\n"
                "Really? Well, I suppose that makes sense. "
                "I had no idea."
            )
            follow_up = [
                ("Indeed.", "greeting"),
                ("Now, about that favor...", "help_offer"),
            ]
        # No relationship change — they don't know they were deceived
    else:
        npc_response = (
            f"{result_text}\n"
            "Do you take me for a fool?! I can see right through "
            "your lies. Get away from me!"
        )
        follow_up = [
            ("[Back down] Sorry, I misspoke.", "apologize"),
            ("Fine, forget it.", "goodbye"),
        ]
        # Heavy relationship penalty for caught lying
        npc.player_relationship = max(-100,
                                       npc.player_relationship - 15)
        _apply_talk_cooldown(npc, duration=3)

    return result_text, npc_response, follow_up


# ================================================================
# COOLDOWN — NPC refuses to talk after failed checks
# ================================================================

def _apply_talk_cooldown(npc, duration: int = 2):
    """Mark an NPC as refusing to talk for N conversation attempts.

    The NPC's dialog tree should check this before building options.
    """
    npc_cooldowns = getattr(npc, '_skill_check_cooldown', 0)
    npc._skill_check_cooldown = max(npc_cooldowns, duration)
    npc.add_memory("social",
                   "The player tried to manipulate me. I don't trust them.", 3)


def check_talk_cooldown(npc) -> bool:
    """Check if NPC is in a talk cooldown. Returns True if cooled down (ok to talk).

    Decrements the cooldown counter each time it's checked.
    """
    cd = getattr(npc, '_skill_check_cooldown', 0)
    if cd <= 0:
        return True
    npc._skill_check_cooldown = cd - 1
    return False


def get_cooldown_response(npc) -> str:
    """Get a response for when NPC refuses to talk due to cooldown."""
    responses = [
        "*turns away* I have nothing to say to you right now.",
        "*crosses arms* Come back when you've learned some manners.",
        "*scowls* After what you tried? Not a chance.",
        "I don't trust you. Leave me be.",
        "*ignores you pointedly*",
    ]
    return random.choice(responses)


# ================================================================
# DC SELECTION HELPERS
# ================================================================

def get_intimidate_dc(npc) -> int:
    """Get the DC for intimidating this NPC based on their bravery."""
    bravery = getattr(npc, 'bravery', 0.5)
    if bravery < 0.3:
        return DC_BASIC
    elif bravery < 0.7:
        return DC_HARD
    return DC_VERY_HARD


def get_persuade_dc(npc) -> int:
    """Get the DC for persuading this NPC based on relationship."""
    rel = getattr(npc, 'player_relationship', 0)
    if rel > 20:
        return DC_BASIC
    elif rel > -10:
        return DC_HARD
    return DC_VERY_HARD


def get_deception_dc(npc) -> int:
    """Get the DC for deceiving this NPC based on traits and wisdom."""
    traits = getattr(npc, 'social_traits', [])
    if 'gullible' in traits or 'trusting' in traits:
        return DC_BASIC
    elif 'suspicious' in traits or 'perceptive' in traits:
        return DC_VERY_HARD
    return DC_HARD
