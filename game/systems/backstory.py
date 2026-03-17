"""
Backstory generation: every NPC starts with memories, knowledge, and history.

Each NPC gets:
1. Personal backstory based on race, class, age, location
2. Knowledge of their settlement and region
3. Memories of recent events (last few weeks of life before game start)
4. Opinions about nearby NPCs (friends/enemies)
5. Knowledge of local threats, resources, politics

When an LLM is available, these are generated dynamically.
When not, rich templates create plausible histories.
"""

import random
from typing import List, Dict


# Regional knowledge by region name
REGION_KNOWLEDGE = {
    "human_kingdoms": [
        "The Heartlands are the breadbasket of civilization",
        "The kingdom taxes are fair but the roads need repair",
        "Merchants travel between the great cities carrying silks and spices",
        "The harvest was good this year but wolves have been a problem",
        "The king's guards patrol the roads but bandits still lurk in the forests",
    ],
    "elven_forests": [
        "The Silverwood has stood for thousands of years",
        "The ancient trees hold memories of ages past",
        "We elves live in harmony with the forest creatures",
        "There are ruins deep in the wood that predate even our people",
        "The forest provides everything we need if we treat it with respect",
    ],
    "dwarven_highlands": [
        "The Iron Peaks hold the richest veins of ore in the land",
        "Our forges burn day and night producing the finest steel",
        "The mountain tunnels connect our settlements underground",
        "Trolls and ogres raid our outposts in the lower passes",
        "Dwarven ale is brewed with mountain spring water and ancient recipes",
    ],
    "orcish_badlands": [
        "The Blasted Wastes test the strong and consume the weak",
        "Only the mightiest warriors lead the war bands",
        "We take what we need from the soft lowlanders",
        "The old shamans speak of a time when orcs ruled all the lands",
        "Food is scarce here so we raid the human settlements when we must",
    ],
    "coastal_reaches": [
        "The Azure Coast is rich with fish and trade",
        "Ships from distant lands dock at our ports",
        "The salt flats provide valuable salt for preserving food",
        "Pirates sometimes raid the smaller fishing villages",
        "The sea provides but it also takes - many have been lost to storms",
    ],
    "wild_frontier": [
        "The Untamed Wilds are the last true wilderness",
        "Only rangers and druids know the safe paths through here",
        "Dire wolves and owlbears roam freely in these lands",
        "There are ancient ruins here that no one has explored",
        "The frontier attracts those seeking freedom from the kingdoms",
    ],
}

# Personal history templates by class
CLASS_BACKSTORIES = {
    "Fighter": [
        "Trained with the village militia since age {teen}",
        "Served as a guard in {nearby_settlement} for several years",
        "Lost a duel to a rival warrior and trained harder ever since",
        "Defended the village from a wolf attack last winter",
        "Was taught swordplay by a retired knight passing through",
        "Dreams of joining the royal guard at {nearest_castle}",
    ],
    "Wizard": [
        "Discovered magical talent as a child and studied under a mentor",
        "Found an old spellbook in the ruins and taught myself the basics",
        "Was sent to study at the temple library in {nearby_settlement}",
        "Accidentally set fire to a barn with uncontrolled magic as a youth",
        "Corresponded with scholars across the land seeking knowledge",
        "Seeks to understand the ancient magic in the nearby ruins",
    ],
    "Cleric": [
        "Heard the calling of the divine during a terrible illness",
        "Trained at the temple since childhood under the elder priests",
        "Healed a dying child and knew this was my purpose",
        "Traveled from {nearby_settlement} to serve the faithful here",
        "The temple elders recognized my gift for healing early on",
        "Lost a loved one and found solace in faith and service",
    ],
    "Rogue": [
        "Grew up on the streets learning to survive by wit alone",
        "Used to run with a band of thieves before going straight",
        "Learned lockpicking from a traveling merchant as a teenager",
        "Has contacts in every settlement within a week's travel",
        "Once stole from the wrong person and had to flee {nearby_settlement}",
        "Now uses cunning for honest trade... mostly",
    ],
    "Ranger": [
        "Grew up in the wilderness, raised by a hermit who taught woodcraft",
        "Has tracked and mapped every trail within fifty leagues",
        "Saved a farmer's family from wolves and earned the village's respect",
        "Knows the location of every water source and safe campsite nearby",
        "Once tracked an orc war band for three days to warn the settlements",
        "Prefers the company of animals to most people",
    ],
    "Paladin": [
        "Swore a sacred oath after witnessing injustice as a youth",
        "Trained at the temple of {nearest_castle} under the holy knights",
        "Led a group of villagers against a bandit raid and prevailed",
        "Carries a blessed weapon passed down through generations",
        "Once faced an undead creature and drove it back through faith alone",
    ],
    "Barbarian": [
        "Came from the wild lands beyond the frontier",
        "Won leadership of the hunting party through strength alone",
        "Once wrestled a bear and earned the scars to prove it",
        "Distrusts the soft ways of city folk but respects their crafts",
        "The strongest fighter in the settlement, and everyone knows it",
    ],
    "Bard": [
        "Learned songs and stories from traveling performers as a child",
        "Has performed in taverns across three different settlements",
        "Knows the history of every ruin within a hundred leagues",
        "Once talked a bandit chief out of raiding the village",
        "Collects tales from every traveler who passes through",
        "Dreams of composing the greatest ballad the world has ever heard",
    ],
    "Druid": [
        "Was chosen by the forest spirits during a vision quest",
        "Tends the sacred grove that has stood for centuries",
        "Grew up learning the properties of every herb and plant",
        "Can predict the weather by reading the behavior of animals",
        "Fought to protect an ancient tree from loggers last season",
        "Teaches the younger folk which plants heal and which ones kill",
    ],
    "Monk": [
        "Left the monastery to test discipline in the real world",
        "Meditates at the shrine every dawn without fail",
        "Once fasted for seven days to achieve a spiritual breakthrough",
        "Trains body and mind with equal rigor every single day",
    ],
    "Sorcerer": [
        "Magic manifested unexpectedly during a moment of strong emotion",
        "Struggles to control powers that sometimes flare up unbidden",
        "Seeks others with innate magic to understand the gift better",
        "Was feared by neighbors as a child due to magical outbursts",
    ],
    "Warlock": [
        "Made a pact during a desperate moment and gained strange powers",
        "Hears whispers from the patron entity during dreams",
        "Studies forbidden texts to understand the nature of the pact",
        "Keeps the details of the arrangement strictly private",
    ],
}

# Relationship memory templates
RELATIONSHIP_MEMORIES = {
    "friend": [
        "Shared a meal with {other} last week. Good company.",
        "{other} helped me when I was in trouble. I won't forget that.",
        "{other} and I have been friends since we were young.",
        "I trust {other} with my life. We've been through a lot together.",
        "{other} taught me something valuable about {skill}.",
    ],
    "enemy": [
        "{other} cheated me in a trade. I haven't forgiven that.",
        "{other} and I had a terrible argument about territory.",
        "I don't trust {other}. Something about them feels wrong.",
        "{other} insulted my family. Words like that aren't forgotten.",
    ],
    "neutral": [
        "I see {other} around the village sometimes. We nod but rarely talk.",
        "{other} seems decent enough. We just don't have much in common.",
    ],
}


def generate_backstory(npc, structures: list, region_name: str = "",
                       governance=None, demographics=None):
    """Generate a complete backstory with memories and knowledge for an NPC."""
    rng = random.Random(hash(npc.name))
    char_class = getattr(npc, 'char_class', 'Fighter')
    race = getattr(npc, 'race', 'Human')
    age = int(getattr(npc, 'age', 30))
    name = npc.name

    # Find nearby settlement names for templates
    nearby = []
    nearest_castle = "the capital"
    for s in structures:
        d = npc.dist_to_pos(s.x, s.y)
        if d < 100 and s.kind in ("village", "town", "city"):
            nearby.append(s.name)
        if s.kind == "castle" and d < 200:
            nearest_castle = s.name

    nearby_settlement = rng.choice(nearby) if nearby else "a distant village"
    teen = rng.randint(12, 16)

    # === 1. Personal backstory memories ===
    templates = CLASS_BACKSTORIES.get(char_class, ["Has lived a quiet life"])
    backstory_texts = rng.sample(templates, min(3, len(templates)))
    for text in backstory_texts:
        filled = text.format(
            nearby_settlement=nearby_settlement,
            nearest_castle=nearest_castle,
            teen=teen
        )
        npc.add_memory("backstory", filled, 2)

    # === 2. Regional and world knowledge (from canonical lore) ===
    try:
        from game.world.lore import COMMON_KNOWLEDGE, REGIONAL_COMMON_KNOWLEDGE, WORLD_NAME
        # Everyone knows basic world facts
        for fact in rng.sample(COMMON_KNOWLEDGE, min(3, len(COMMON_KNOWLEDGE))):
            if fact not in npc.known_info:
                npc.known_info.append(fact)
        # Regional knowledge
        regional = REGIONAL_COMMON_KNOWLEDGE.get(region_name, [])
        if regional:
            for fact in rng.sample(regional, min(2, len(regional))):
                if fact not in npc.known_info:
                    npc.known_info.append(fact)
    except ImportError:
        pass

    # Planetary knowledge (based on class, race, skills)
    try:
        from game.world.planet import get_planetary_knowledge
        planet_facts = get_planetary_knowledge(npc)
        # Give each NPC 2-4 planetary facts based on their education level
        literacy = getattr(npc, 'npc_skills', {}).get('literacy', 0)
        num_facts = min(len(planet_facts), 2 + literacy)
        for fact in rng.sample(planet_facts, min(num_facts, len(planet_facts))):
            if fact not in npc.known_info:
                npc.known_info.append(fact)
    except ImportError:
        pass

    region_knowledge = REGION_KNOWLEDGE.get(region_name, REGION_KNOWLEDGE.get("human_kingdoms", []))
    known = rng.sample(region_knowledge, min(2, len(region_knowledge)))
    for info in known:
        if info not in npc.known_info:
            npc.known_info.append(info)

    # === 3. Local knowledge ===
    local_knowledge = []
    for s in structures:
        d = npc.dist_to_pos(s.x, s.y)
        if d < 60:
            if s.kind == "village":
                local_knowledge.append(f"The village of {s.name} is nearby")
            elif s.kind == "ruins":
                local_knowledge.append(f"There are ruins called {s.name} in the area - dangerous but full of treasure")
            elif s.kind == "castle":
                local_knowledge.append(f"The castle of {s.name} rules this region")
            elif s.kind == "tavern":
                local_knowledge.append(f"The tavern {s.name} serves food and drink")
            elif s.kind == "temple":
                local_knowledge.append(f"The temple {s.name} offers healing and blessings")

    for info in local_knowledge[:5]:
        if info not in npc.known_info:
            npc.known_info.append(info)

    # === 3b. Political knowledge (from actual governance state) ===
    if governance:
        # Which kingdom am I in?
        for kingdom_name, kingdom in governance.kingdoms.items():
            if kingdom.contains(npc.x, npc.y):
                ruler = kingdom.ruler_name
                style = kingdom.governing_style
                npc.known_info.append(f"We are ruled by {ruler} of {kingdom_name}")
                npc.known_info.append(f"Our government is a {style}")
                npc.faction = kingdom_name

                if kingdom.treasury > 300:
                    npc.known_info.append(f"The kingdom of {kingdom_name} is prosperous")
                elif kingdom.treasury < 50:
                    npc.known_info.append(f"The kingdom of {kingdom_name} is struggling financially")

                if kingdom.public_morale > 70:
                    npc.known_info.append("The people are generally content with the rule")
                elif kingdom.public_morale < 30:
                    npc.known_info.append("There is unrest among the people")

                if kingdom.corruption > 0.3:
                    npc.known_info.append("Corruption is a problem among the officials")

                npc.add_memory("political", f"I live under the rule of {ruler} in {kingdom_name}", 2)
                break

        # Knowledge of other kingdoms
        for kingdom_name, kingdom in governance.kingdoms.items():
            if not kingdom.contains(npc.x, npc.y):
                d = ((npc.x - kingdom.castle_x)**2 + (npc.y - kingdom.castle_y)**2)**0.5
                if d < 200:
                    npc.known_info.append(f"The kingdom of {kingdom_name} is ruled by {kingdom.ruler_name}")

        # Knowledge of diplomatic relations
        for (k1, k2), rel in governance.diplomacy.items():
            if rel.status == "at_war":
                npc.known_info.append(f"{k1} and {k2} are at war!")
                npc.add_memory("political", f"War between {k1} and {k2}!", 4)
            elif rel.status == "allied":
                npc.known_info.append(f"{k1} and {k2} are allies")

    # === 3c. Family knowledge ===
    if demographics:
        family_info = demographics.get_family_info(npc.name)
        if "No family" not in family_info:
            npc.known_info.append(f"I belong to {family_info}")
            npc.add_memory("personal", f"I am a member of {family_info}", 2)

        # Title-based memories
        title = getattr(npc, 'title', 'commoner')
        if title == "monarch":
            npc.add_memory("political", f"I am the ruler of this land. The weight of leadership is heavy.", 5)
            npc.add_memory("political", "I must protect my people and maintain order", 4)
        elif title == "duke":
            npc.add_memory("political", "I serve as duke, advising the ruler and managing the realm", 4)
        elif title == "knight":
            npc.add_memory("duty", "I am sworn as a knight to defend the realm", 3)
        elif title == "guard":
            npc.add_memory("duty", "I stand watch to protect the people from threats", 3)

    # === 4. Relationship memories ===
    for friend_name in getattr(npc, 'friends', [])[:3]:
        skill = rng.choice(list(getattr(npc, 'npc_skills', {}).keys()) or ["survival"])
        template = rng.choice(RELATIONSHIP_MEMORIES["friend"])
        memory = template.format(other=friend_name, skill=skill)
        npc.add_memory("relationship", memory, 2)

    for enemy_name in getattr(npc, 'enemies', [])[:2]:
        template = rng.choice(RELATIONSHIP_MEMORIES["enemy"])
        memory = template.format(other=enemy_name)
        npc.add_memory("relationship", memory, 3)

    # === 5. Race-specific memories ===
    race_memories = {
        "Elf": [
            "I remember the forest when the trees were younger, centuries ago",
            "Elven traditions teach patience that other races don't understand",
        ],
        "Dwarf": [
            "My family has worked these mines for seven generations",
            "Dwarven craftsmanship is unmatched - I learned that from my father's forge",
        ],
        "Halfling": [
            "I miss the green hills of my homeland but adventure called me here",
            "A good meal and warm company - that's what life is really about",
        ],
        "Half-Orc": [
            "I've had to prove myself twice as hard because of my blood",
            "Strength earned me respect where words could not",
        ],
        "Gnome": [
            "I've always been curious about how things work - took apart a clock at age five",
            "My people say curiosity is the greatest gift. I agree wholeheartedly",
        ],
        "Tiefling": [
            "People stare. They always stare. I've learned to ignore it",
            "My heritage is a burden but also a source of strength",
        ],
    }
    for memory in race_memories.get(race, []):
        npc.add_memory("personal", memory, 2)

    # === 6. Recent life memories ===
    recent = [
        f"Had a good conversation with a traveler passing through last week",
        f"The weather has been {rng.choice(['mild', 'harsh', 'unpredictable'])} lately",
        f"Spent yesterday {rng.choice(['working', 'resting', 'training', 'gathering herbs', 'patrolling'])}",
        f"Heard rumors about {rng.choice(['bandits on the road', 'treasure in the ruins', 'a new trade route', 'monster sightings'])}",
    ]
    for memory in rng.sample(recent, 2):
        npc.add_memory("recent", memory, 1)


def generate_all_backstories(npcs: list, structures: list, regions: dict = None,
                             governance=None, demographics=None):
    """Generate backstories for all NPCs using actual world state."""
    from game.world.regions import get_region_at

    for npc in npcs:
        if not npc.alive:
            continue

        region_name = ""
        if regions:
            region_name = get_region_at(int(npc.x), int(npc.y), regions) or ""

        generate_backstory(npc, structures, region_name, governance, demographics)
