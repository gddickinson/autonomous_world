"""
Dialog trees for intelligent monsters.

Intelligent creature types (orcs, goblins, kobolds, gnolls, bandits,
bugbears, hobgoblins) can have conversations with the player.
Mindless undead (skeletons, zombies) cannot talk.
"""

import random
from typing import Dict, Optional
from game.core.dialog_trees import DialogLine


# Which creature kinds are intelligent enough to talk
INTELLIGENT_KINDS = frozenset({
    "orc", "orc_war_chief", "orc_eye_of_gruumsh",
    "goblin", "goblin_boss",
    "kobold",
    "gnoll", "gnoll_pack_lord",
    "bandit", "bandit_captain",
    "bugbear", "bugbear_chief",
    "hobgoblin", "hobgoblin_captain", "hobgoblin_warlord",
})

# Mindless / mute creatures that should never talk
MINDLESS_KINDS = frozenset({
    "skeleton", "zombie", "ghoul", "wight", "wraith", "specter",
    "shadow", "mummy", "animated_armor",
})


def is_intelligent(kind: str) -> bool:
    """Return True if this creature kind can hold a conversation."""
    return kind in INTELLIGENT_KINDS


def _orc_dialog(creature) -> Dict[str, DialogLine]:
    """Aggressive / territorial dialog for orcs and bugbears."""
    hp_pct = creature.hp / max(1, creature.max_hp)
    name = creature.kind.replace("_", " ").title()

    if hp_pct < 0.4:
        greeting = (f"*the wounded {name} snarls* You fight well... "
                    "Perhaps we can reach an arrangement before more blood is shed.")
    else:
        greeting = (f"*a {name} blocks your path* Leave our lands or face our blades! "
                    "This territory belongs to us.")

    lines = {}
    lines["greeting"] = DialogLine(greeting, [
        ("[Intimidate] I've slain dozens of your kind. Stand aside.", "intimidate"),
        ("[Negotiate] I'm just passing through. No need for violence.", "negotiate"),
        ("[Fight] Then let's settle this.", "fight"),
        ("I'll leave. For now.", "leave"),
    ])

    lines["intimidate"] = DialogLine(
        "*eyes you warily* You... you do carry yourself like a killer. "
        "Fine. Pass through. But don't linger." if hp_pct < 0.6
        else "*laughs* You think words scare us? We've eaten bigger than you!",
        [("[Fight] Wrong answer.", "fight"),
         ("Smart choice.", "leave")] if hp_pct < 0.6
        else [("[Fight] Then let's go.", "fight"),
              ("[Back down] Maybe another time.", "leave")])

    lines["negotiate"] = DialogLine(
        "Passing through? Hmph. Pay a toll of 20 gold and we'll let you walk. "
        "Otherwise..." if hp_pct > 0.5
        else "You... you'd show mercy? Fine. Go. We won't stop you.",
        [("Here's 20 gold. [Pay toll]", "pay_toll"),
         ("I don't pay tolls to monsters.", "fight"),
         ("How about I help you with something instead?", "offer_help")]
        if hp_pct > 0.5
        else [("Stay safe.", "leave")])

    lines["pay_toll"] = DialogLine(
        "*takes the gold* Wise. You may pass. Don't come back without more gold.",
        [("Farewell.", "goodbye")])

    lines["offer_help"] = DialogLine(
        "*considers* There are wolves hunting near our camp. "
        "Kill them, and we'll leave travelers alone for a moon cycle.",
        [("I'll deal with the wolves.", "accept_task"),
         ("Not interested.", "leave")])

    lines["accept_task"] = DialogLine(
        "Good. Come back when it's done. We remember our debts.",
        [("I'll return.", "goodbye")])

    lines["fight"] = DialogLine(
        "*draws weapon* So be it! Blood for blood!",
        [])

    lines["leave"] = DialogLine(
        "*watches you go* Don't come back.",
        [])

    lines["goodbye"] = DialogLine(
        "*grunts and turns away*",
        [])

    return lines


def _goblin_dialog(creature) -> Dict[str, DialogLine]:
    """Cunning / cowardly dialog for goblins and kobolds."""
    name = creature.kind.replace("_", " ").title()
    hp_pct = creature.hp / max(1, creature.max_hp)

    if hp_pct < 0.5:
        greeting = (f"*the {name} cowers* Wait wait! Don't hurt us! "
                    "We can trade... we have shinies!")
    else:
        greeting = (f"*a {name} peers at you from the shadows* "
                    "Halt, tall one! You want pass? You pay! Or maybe... we trade?")

    lines = {}
    lines["greeting"] = DialogLine(greeting, [
        ("What do you have to trade?", "trade"),
        ("[Demand tribute] Give me everything you have.", "demand"),
        ("[Threaten] Get out of my way, runt.", "threaten"),
        ("I'll go another way.", "leave"),
    ])

    lines["trade"] = DialogLine(
        "*rummages through a dirty sack* We got shiny rocks, old bones, "
        "maybe a potion we found... also know where treasure is hidden! "
        "Information costs extra, yes yes!",
        [("Tell me about the treasure.", "treasure_info"),
         ("Show me the potion.", "show_goods"),
         ("Never mind.", "leave")])

    lines["treasure_info"] = DialogLine(
        "*looks around nervously* Big chest in old ruins, north of here. "
        "Guarded by big ugly spider. We too small to fight it. "
        "You kill spider, keep treasure, yes? Just let us go!",
        [("Thanks for the tip.", "leave"),
         ("How do I know you're not lying?", "trust_check")])

    lines["trust_check"] = DialogLine(
        "*squeaks* We not lie! Lying gets us killed! "
        "We seen the chest with our own eyes, promise promise!",
        [("Fine, I'll check it out.", "leave"),
         ("Get lost.", "leave")])

    lines["show_goods"] = DialogLine(
        "*holds up a cracked vial* Health potion! Only slightly expired! "
        "10 gold, good deal!",
        [("Deal. [Pay 10 gold]", "buy_potion"),
         ("That's overpriced junk.", "leave")])

    lines["buy_potion"] = DialogLine(
        "*snatches the gold* Pleasure doing business! "
        "Come back anytime, we always here! ...probably.",
        [("Farewell.", "goodbye")])

    lines["demand"] = DialogLine(
        "*trembles* P-please! We give you 5 gold, that's all we have! "
        "Don't squish us!" if hp_pct < 0.7
        else "*hisses* You want fight whole tribe? We many, you one!",
        [("Hand it over.", "take_tribute"),
         ("Keep your gold. Just stay out of my way.", "leave")]
        if hp_pct < 0.7
        else [("[Fight] Try me.", "fight"),
              ("Fine, forget it.", "leave")])

    lines["take_tribute"] = DialogLine(
        "*drops a few coins and scurries back* Take! Take! Just go away!",
        [("Smart.", "goodbye")])

    lines["threaten"] = DialogLine(
        "*yelps and jumps back* Okay okay! We go! No hurt! "
        "We just hungry, that's all!",
        [("Then go find food elsewhere.", "leave"),
         ("Here, take this food.", "give_food")])

    lines["give_food"] = DialogLine(
        "*eyes widen* You... give food? To us? "
        "You not so bad, tall one. We remember this!",
        [("Don't mention it.", "goodbye")])

    lines["fight"] = DialogLine(
        "*shrieks* Attack! Attack! Get the tall one!",
        [])

    lines["leave"] = DialogLine(
        "*watches with beady eyes as you go*",
        [])

    lines["goodbye"] = DialogLine(
        "*scurries off into the shadows*",
        [])

    return lines


def _bandit_dialog(creature) -> Dict[str, DialogLine]:
    """Mercenary dialog for bandits."""
    hp_pct = creature.hp / max(1, creature.max_hp)

    if hp_pct < 0.4:
        greeting = ("*the bandit holds up hands* Hold! I yield! "
                    "Take my gold, just let me live!")
    else:
        greeting = ("*a rough-looking bandit steps forward* "
                    "Your gold or your life! Don't try anything stupid.")

    lines = {}
    lines["greeting"] = DialogLine(greeting, [
        ("[Pay toll] How much do you want?", "pay_toll"),
        ("[Fight] Over my dead body.", "fight"),
        ("[Persuade] I'm worth more alive. I can help you.", "persuade"),
        ("[Flee] I'm not looking for trouble. *backs away*", "flee"),
    ])

    lines["pay_toll"] = DialogLine(
        "30 gold and you walk free. Fair deal, considering the alternative.",
        [("Fine, here's 30 gold. [Pay 30 gold]", "paid"),
         ("That's robbery!", "fight"),
         ("How about 10?", "haggle")])

    lines["paid"] = DialogLine(
        "*pockets the gold* Pleasure doing business. "
        "Word of advice: don't travel this road at night.",
        [("Thanks for the tip.", "goodbye")])

    lines["haggle"] = DialogLine(
        "*scoffs* 10? You insult me. 20, final offer. "
        "Or we can settle this the hard way.",
        [("20 it is. [Pay 20 gold]", "paid"),
         ("[Fight] The hard way, then.", "fight")])

    lines["persuade"] = DialogLine(
        "*raises an eyebrow* Help us how? "
        "We don't exactly put out job postings.",
        [("I know where a merchant caravan will pass tomorrow.", "info_trade"),
         ("I'm a skilled fighter. Hire me.", "offer_service"),
         ("Actually, never mind.", "fight")])

    lines["info_trade"] = DialogLine(
        "*strokes chin* Information for passage... I like it. "
        "Tell me more and you walk free.",
        [("There's a caravan heading east at dawn.", "gave_info"),
         ("Actually, I made that up. [Fight]", "fight")])

    lines["gave_info"] = DialogLine(
        "*grins* Now THAT'S valuable. You're free to go. "
        "Maybe we'll do business again.",
        [("Maybe.", "goodbye")])

    lines["offer_service"] = DialogLine(
        "*looks you over* You do look capable. "
        "But we don't need more swords right now. Move along.",
        [("Fair enough.", "goodbye")])

    lines["fight"] = DialogLine(
        "*draws blade* Your funeral!",
        [])

    lines["flee"] = DialogLine(
        "*the bandit laughs* That's right, run!",
        [])

    lines["goodbye"] = DialogLine(
        "*melts back into the shadows*",
        [])

    return lines


def _gnoll_dialog(creature) -> Dict[str, DialogLine]:
    """Savage / hungry dialog for gnolls."""
    hp_pct = creature.hp / max(1, creature.max_hp)
    name = creature.kind.replace("_", " ").title()

    if hp_pct < 0.3:
        greeting = (f"*the {name} whimpers* No more fight... "
                    "We hungry, that is all...")
    else:
        greeting = (f"*a {name} sniffs the air* "
                    "Meat! Fresh meat walks into our territory!")

    lines = {}
    lines["greeting"] = DialogLine(greeting, [
        ("[Fight] Come and get it.", "fight"),
        ("[Intimidate] I'll make a rug out of your hide.", "intimidate"),
        ("[Offer food] I have food. Take it and let me pass.", "offer_food"),
        ("[Flee] *slowly backs away*", "flee"),
    ])

    lines["fight"] = DialogLine(
        "*howls and charges* The pack feeds tonight!",
        [])

    lines["intimidate"] = DialogLine(
        "*growls low* You... you strong. Pack not hungry enough "
        "to fight strong prey. Go. But leave food." if hp_pct < 0.6
        else "*snarls* You threaten the pack? The pack eats your bones!",
        [("Here's some food. Now leave me alone.", "offer_food"),
         ("[Fight] I don't negotiate with beasts.", "fight")]
        if hp_pct < 0.6
        else [("[Fight] Bring it.", "fight"),
              ("[Back down] Easy now...", "flee")])

    lines["offer_food"] = DialogLine(
        "*sniffs the food, then snatches it* "
        "Mmm... good meat. You go now. Pack remembers kindness. "
        "Maybe we not eat you next time. Maybe.",
        [("You're welcome.", "goodbye")])

    lines["flee"] = DialogLine(
        "*the gnoll licks its lips but doesn't pursue* "
        "Run, little prey. We find you later...",
        [])

    lines["goodbye"] = DialogLine(
        "*returns to gnawing on a bone*",
        [])

    return lines


def build_creature_dialog(creature) -> Optional[Dict[str, DialogLine]]:
    """Build a dialog tree for an intelligent creature.

    Returns None for mindless creatures or unknown types.
    """
    kind = creature.kind.lower()

    if kind in MINDLESS_KINDS:
        return None

    if not is_intelligent(kind):
        return None

    # Route to the appropriate dialog builder
    if any(k in kind for k in ("orc", "bugbear")):
        return _orc_dialog(creature)
    elif any(k in kind for k in ("goblin", "kobold")):
        return _goblin_dialog(creature)
    elif "bandit" in kind:
        return _bandit_dialog(creature)
    elif "gnoll" in kind:
        return _gnoll_dialog(creature)
    elif "hobgoblin" in kind:
        return _orc_dialog(creature)  # hobgoblins use orc-style dialog

    return None
