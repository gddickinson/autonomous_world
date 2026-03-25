"""Job-to-class mapping and job-specific dialog data.

Maps NPC professions to appropriate D&D character classes, provides
job-specific greetings, and job-specific dialog options.
"""

import random
from typing import Dict, List, Tuple


# ================================================================
# JOB -> D&D CLASS MAPPING
# ================================================================
# Maps profession/job names to the most thematically appropriate
# D&D character class. Used during NPC creation to replace the
# random class assignment so that a Guard is a Fighter, etc.

JOB_TO_CLASS: Dict[str, str] = {
    # Military / Combat
    "Guard": "Fighter",
    "Soldier": "Fighter",
    "Captain": "Fighter",
    "Knight": "Fighter",
    "Mercenary": "Fighter",
    "Gladiator": "Fighter",
    "Archer": "Ranger",
    "Watchman": "Fighter",

    # Civilian / Labor
    "Farmer": "Commoner",
    "Baker": "Commoner",
    "Cook": "Commoner",
    "Miller": "Commoner",
    "Brewer": "Commoner",
    "Beekeeper": "Commoner",
    "Shepherd": "Commoner",
    "Weaver": "Commoner",
    "Potter": "Commoner",
    "Barber": "Commoner",
    "Servant": "Commoner",
    "Laborer": "Commoner",
    "Porter": "Commoner",
    "Dock Worker": "Commoner",
    "Shop Assistant": "Commoner",
    "Water Carrier": "Commoner",
    "Peat Cutter": "Commoner",

    # Trade / Commerce
    "Merchant": "Rogue",
    "Innkeeper": "Rogue",
    "Banker": "Rogue",
    "Caravaneer": "Rogue",
    "Tax Collector": "Rogue",
    "Jeweler": "Rogue",

    # Scholarly / Arcane
    "Scholar": "Wizard",
    "Scribe": "Wizard",
    "Librarian": "Wizard",
    "Alchemist": "Wizard",
    "Cartographer": "Wizard",

    # Religious / Healing
    "Priest": "Cleric",
    "Healer": "Cleric",
    "Herbalist": "Cleric",

    # Crafting
    "Blacksmith": "Commoner",
    "Carpenter": "Commoner",
    "Mason": "Commoner",
    "Smelter": "Commoner",
    "Cooper": "Commoner",
    "Wheelwright": "Commoner",
    "Net Maker": "Commoner",
    "Armourer": "Commoner",
    "Shipbuilder": "Commoner",

    # Wilderness / Outdoors
    "Hunter": "Ranger",
    "Woodcutter": "Ranger",
    "Fisherman": "Ranger",
    "Sailor": "Ranger",
    "Prospector": "Ranger",
    "Charcoal Burner": "Ranger",
    "Lighthouse Keeper": "Ranger",

    # Intrigue / Diplomacy
    "Spy": "Rogue",
    "Diplomat": "Bard",
    "Advisor": "Bard",
    "Steward": "Bard",
    "Bard": "Bard",

    # Mining
    "Miner": "Commoner",

    # Stablemaster
    "Stablemaster": "Commoner",

    # Self-referencing class names used as professions
    "Ranger": "Ranger",
    "Bard": "Bard",

    # Additional labor professions (fallback to Commoner)
    "Philosopher": "Wizard",
    "Fisher": "Commoner",
    "Tanner": "Commoner",
    "Glassblower": "Commoner",
    "Animal Trainer": "Ranger",
    "Builder": "Commoner",
    "Cleaner": "Commoner",
    "Gravedigger": "Commoner",
}

# Fallback: if a job is not in JOB_TO_CLASS, use this heuristic
_FALLBACK_CLASS = "Commoner"


def get_class_for_job(profession: str) -> str:
    """Return the D&D class that best matches the given profession.

    Returns the mapped class if found, otherwise falls back to Commoner.
    """
    return JOB_TO_CLASS.get(profession, _FALLBACK_CLASS)


# ================================================================
# JOB-SPECIFIC GREETINGS
# ================================================================
# Keyed by profession. Each value is a list of possible greetings.
# These are used for the *neutral* relationship range (-5 to 20).
# The dialog system falls through to class-based greetings if the
# profession isn't listed here.

JOB_GREETINGS: Dict[str, List[str]] = {
    "Guard": [
        "Halt! State your business.",
        "Move along, citizen. Unless you need something.",
        "Keep your weapons sheathed in town.",
        "I'm {name}, on watch duty. What do you need?",
    ],
    "Farmer": [
        "*wipes dirt from hands* Oh, hello. I'm {name}. Don't mind the mess.",
        "Good day! The crops are looking fine this season. I'm {name}.",
        "Need any fresh produce? Name's {name}.",
        "Careful of the mud. I'm {name}, working the fields.",
    ],
    "Merchant": [
        "Welcome! Take a look at my wares. I'm {name}.",
        "I've got the best prices in town. Name's {name}.",
        "Looking to buy or sell? I'm {name}, at your service.",
        "Welcome to my shop! I'm {name}. What catches your eye?",
    ],
    "Scholar": [
        "Ah, a visitor. Do you seek knowledge? I'm {name}.",
        "I've been studying the ancient texts. I'm {name}.",
        "Hmm? Oh, forgive me. I was deep in thought. I'm {name}.",
    ],
    "Blacksmith": [
        "*sets down hammer* What can I forge for you? Name's {name}.",
        "I've got blades that could cut through stone. I'm {name}.",
        "The forge is hot today. Need something made? I'm {name}.",
    ],
    "Innkeeper": [
        "Welcome to my establishment! Rooms are 5 gold a night. I'm {name}.",
        "What'll you have? I'm {name}, I run this place.",
        "Take a seat by the fire. I'm {name}. Food and drink are ready.",
    ],
    "Fisherman": [
        "The fish aren't biting today. Name's {name}.",
        "I pulled a big one out of the river yesterday! I'm {name}.",
        "Watch your step near the dock. I'm {name}.",
    ],
    "Baker": [
        "Hello there! I'm {name}. Fresh bread just out of the oven!",
        "The smell of bread always brings people in. I'm {name}.",
        "Careful, that loaf's still hot. Name's {name}.",
    ],
    "Healer": [
        "Greetings. I'm {name}. Are you hurt? I can help.",
        "Come in, come in. I'm {name}. Let me have a look at you.",
        "I'm {name}, the healer. Prevention is better than cure.",
    ],
    "Hunter": [
        "Shh... you'll scare the game. I'm {name}.",
        "*nods* I'm {name}. These trails are mine to walk.",
        "Fresh venison for sale. Name's {name}.",
    ],
    "Woodcutter": [
        "Been chopping since dawn. My arms know it. I'm {name}.",
        "*leans on axe* Taking a breather. Name's {name}.",
        "Good timber around here. I'm {name}.",
    ],
    "Miner": [
        "Just came up from the tunnels. I'm {name}.",
        "The veins run deep here. Name's {name}.",
        "*brushes dust off* What brings you to the mine? I'm {name}.",
    ],
    "Soldier": [
        "At ease. I'm {name}, stationed here.",
        "You don't look like trouble. I'm {name}.",
        "Reporting for duty. I'm {name}.",
    ],
    "Captain": [
        "I'm Captain {name}. State your business.",
        "I command the garrison here. I'm {name}.",
        "You're in my jurisdiction now. Captain {name}.",
    ],
    "Carpenter": [
        "Working on a new piece. The wood has to be just right. I'm {name}.",
        "*measuring timber* Oh, hello. Name's {name}.",
        "Need something built? I'm {name}, the carpenter.",
    ],
    "Alchemist": [
        "Careful around the bottles. I'm {name}. Need a potion?",
        "*bubbling sounds* One moment... there. I'm {name}.",
        "Don't touch anything! I'm {name}. What do you need?",
    ],
    "Sailor": [
        "Just came ashore. Name's {name}.",
        "The sea calls to me, but right now I'm on land. I'm {name}.",
        "Need passage somewhere? I'm {name}.",
    ],
    "Spy": [
        "You didn't see me here. Name's {name}.",
        "Keep your voice down. I'm {name}.",
        "I know things. That's all you need to know. Call me {name}.",
    ],
    "Diplomat": [
        "Greetings, friend. I'm {name}, here on official business.",
        "Words solve more problems than swords. I'm {name}.",
        "Relations between settlements are my concern. I'm {name}.",
    ],
    "Bard": [
        "Welcome, welcome! I'm {name}, storyteller extraordinaire!",
        "*strums lute* Care for a song? I'm {name}.",
        "Every person has a tale worth telling. I'm {name}.",
    ],
    "Scribe": [
        "*looks up from parchment* Oh. I'm {name}.",
        "Words are power, my friend. I'm {name}, the scribe.",
        "I'm {name}. I record everything that happens here.",
    ],
    "Herbalist": [
        "Mind the nettles. I'm {name}.",
        "I know every plant in these parts. Name's {name}.",
        "Looking for remedies? I'm {name}.",
    ],
    "Priest": [
        "Blessings upon you. I'm {name}, servant of the divine.",
        "The temple is always open. I'm {name}.",
        "May peace find you. I'm {name}.",
    ],
    "Prospector": [
        "I've been surveying the hillside. Name's {name}.",
        "There's gold in these hills, I tell you! I'm {name}.",
        "Patience and a keen eye, that's the trick. I'm {name}.",
    ],
    "Stablemaster": [
        "Easy there, girl. Oh, hello. I'm {name}.",
        "Need your horse tended? I'm {name}.",
        "The stables are this way. Name's {name}.",
    ],
    "Laborer": [
        "*grunts* What? Oh, hello. I'm {name}.",
        "Hard work, honest pay. That's my motto. Name's {name}.",
        "Another day, another coin. I'm {name}.",
    ],
}


# ================================================================
# JOB-SPECIFIC DIALOG OPTIONS
# ================================================================
# Each entry: (player_prompt, dialog_key, npc_response_text)
# These are added to the greeting responses and create new dialog nodes.

JOB_DIALOG_OPTIONS: Dict[str, List[Tuple[str, str, str]]] = {
    "Guard": [
        ("Any trouble around here?", "guard_trouble",
         "We've had reports of monsters in the wilds nearby. Stay close to "
         "the settlement after dark. I've increased patrols, but an extra "
         "blade is always welcome."),
        ("I can deal with those threats for a bounty.", "guard_bounty_quest",
         "You would? There are creatures threatening our farmers and travelers. "
         "Eliminate them and I'll see you're paid from the garrison coffers."),
    ],
    "Merchant": [
        ("Show me your goods.", "merchant_goods",
         "Of course! I have supplies, equipment, and a few specialty items. "
         "Take your time browsing. I can also buy anything you want to sell."),
        ("Need anything delivered?", "merchant_delivery_quest",
         "As a matter of fact, yes! I have a shipment that needs to reach "
         "another settlement. The roads aren't safe enough for me to go alone. "
         "Would you carry it for me? I'll pay well."),
    ],
    "Farmer": [
        ("How's the harvest?", "farmer_harvest",
         "It's been a decent season so far. Rain came at the right time. "
         "Though the wolves have been getting closer to the livestock pens. "
         "Could use some help keeping them away."),
    ],
    "Scholar": [
        ("What are you researching?", "scholar_research",
         "I'm studying the ancient ruins east of here. The inscriptions hint "
         "at a civilization far older than any we know. If you find any "
         "artifacts or texts in your travels, please bring them to me."),
        ("I could investigate those ruins for you.", "scholar_investigation_quest",
         "Would you really? Strange things have been reported at the old ruins "
         "nearby. I need someone brave enough to go there and document what "
         "they find. I'll share my knowledge and coin as payment."),
    ],
    "Blacksmith": [
        ("Can you repair my equipment?", "smith_repair",
         "Let me take a look... yes, I can fix that up. It'll cost a few "
         "coins for materials and my time, but I'll have it good as new. "
         "Better than new, even."),
    ],
    "Innkeeper": [
        ("I'd like a room for the night.", "inn_room",
         "That'll be 5 gold for a bed, a meal, and a warm fire. You'll "
         "sleep safe here, I promise you that. The stew is fresh too."),
    ],
    "Healer": [
        ("Can you treat my wounds?", "healer_treat",
         "Sit down, let me see. I have poultices and healing herbs ready. "
         "You adventurers always come in battered. Hold still, this might "
         "sting."),
    ],
    "Hunter": [
        ("Seen any good game nearby?", "hunter_game",
         "Deer are moving through the eastern woods. Saw fresh tracks this "
         "morning. Stay downwind and you'll get a clean shot. Watch out for "
         "wolves though, they're tracking the same herds."),
    ],
    "Fisherman": [
        ("Where's the best fishing spot?", "fisher_spot",
         "The bend in the river upstream, where the water slows. That's "
         "where the big ones hide. Early morning is best, before the sun "
         "gets too high."),
    ],
    "Woodcutter": [
        ("Need help with the lumber?", "wood_help",
         "Always! There's more trees than one person can handle. The "
         "settlement needs timber for repairs and new buildings. Grab an "
         "axe and start on that stand of oaks to the north."),
    ],
    "Miner": [
        ("Found anything interesting down there?", "miner_find",
         "Mostly iron ore, which keeps the smithy busy. But last week I "
         "found a vein of something unusual, glowing faintly blue. Haven't "
         "told many people about it yet."),
    ],
    "Baker": [
        ("What's fresh today?", "baker_fresh",
         "Just pulled out a batch of rye bread, and the honey cakes are "
         "cooling now. I also have some travel biscuits that'll last you "
         "a fortnight on the road."),
    ],
    "Alchemist": [
        ("What potions do you have?", "alch_potions",
         "Health potions are always in stock. I also have antidotes, "
         "stamina draughts, and... a few experimental mixtures. The "
         "experimental ones are half price. Side effects may vary."),
    ],
    "Carpenter": [
        ("Can you build something for me?", "carp_build",
         "Depends what you need. Furniture, barrels, wagon repairs, "
         "structural work, I do it all. Bring me the materials and I'll "
         "give you a fair price on the labor."),
    ],
    "Sailor": [
        ("How are the seas?", "sailor_seas",
         "Rough this time of year. Storms roll in from the west with "
         "little warning. The trade routes are open though, if you've "
         "got cargo to move. Just watch for pirates near the straits."),
    ],
    "Soldier": [
        ("What's the military situation?", "soldier_report",
         "We're holding the border, but it's stretched thin. Command wants "
         "more patrols, fewer soldiers. If you're capable with a weapon, "
         "we could use volunteer scouts."),
    ],
    "Captain": [
        ("Need any mercenary work done?", "captain_work",
         "Always. I've got bounties on several threats in the region. "
         "Monster dens, bandit camps, missing supply caravans. Pick your "
         "poison and I'll pay well for results."),
    ],
    "Herbalist": [
        ("What remedies do you have?", "herb_remedy",
         "Fever-root tea, wound poultices, sleeping draughts, and a "
         "tincture for joint pain. I also have rare herbs if you're "
         "looking for something specific for alchemy."),
    ],
    "Spy": [
        ("What information do you have?", "spy_info",
         "Information costs gold, friend. But I'll give you this for "
         "free: the road north isn't as safe as people think. There are "
         "eyes watching. More than that... we'll need to discuss terms."),
    ],
    "Diplomat": [
        ("How are relations between settlements?", "diplo_relations",
         "Tense, as always. Trade keeps the peace, but old grudges die "
         "hard. If you're traveling between settlements, carrying a goodwill "
         "message could earn you favor on both sides."),
    ],
    "Bard": [
        ("Tell me a story.", "bard_story",
         "Ah, you want the tale of the Dragon of Ashenmoor? Or perhaps "
         "the Ballad of the Three Brothers? *strums a chord* Every story "
         "I tell is true. Well, mostly true. The embellishments are the "
         "best part."),
    ],
    "Priest": [
        ("Can I receive a blessing?", "priest_bless",
         "Of course, child. Kneel and receive the light. May it shield "
         "you from darkness and guide your steps on the righteous path. "
         "There. You are blessed."),
    ],
    "Scribe": [
        ("Do you have any interesting documents?", "scribe_docs",
         "I've been cataloguing the settlement's records. There are some "
         "old maps that show locations no one visits anymore. And a letter "
         "from decades ago mentioning hidden treasure. Want to see them?"),
    ],
    "Stablemaster": [
        ("Can you tend to my mount?", "stable_mount",
         "Bring them right in. Fresh hay, clean water, and a good "
         "brushing. Your mount will be well-rested by morning. That'll "
         "be 2 gold for the night."),
    ],
}
