"""
Planetary Geography & History: the world of Edras.

Aethermoor is one continent on the planet Edras — a world roughly Earth-sized
with three major continents, two minor ones, and numerous island chains.
The playable area is Aethermoor, but NPCs know about the wider world through
trade, lore, travelers' tales, and ancient histories.

This module defines:
- Planetary overview (continents, oceans, climate zones)
- Each continent's peoples, nations, and cultures
- Deep planetary history spanning five ages
- Trade routes and inter-continental relationships
- Legends and mysteries that span the globe

NPCs access this through the knowledge system — scholars and travelers
know more, while isolated villagers may only know rumors.
"""


# ================================================================
# THE PLANET EDRAS
# ================================================================

PLANET_NAME = "Edras"

PLANET_OVERVIEW = """
Edras is a world of vast oceans and scattered landmasses. Three great continents
dominate the northern and southern hemispheres, connected by treacherous sea
routes and, in some ages, by magical portals now long dormant. Two smaller
continents and dozens of island chains dot the oceans between them.

The planet orbits a single sun and has two moons — the greater moon Lunara
(silver) and the lesser moon Thal (red-copper). When both moons align, magical
energies surge across the world — an event called the Conjunction, occurring
roughly once every 47 years. The last Conjunction was 12 years ago.

The climate ranges from frozen polar wastes to equatorial jungles, with most
civilizations thriving in the temperate bands. Ocean currents create unusual
climate patterns: the western coast of Aethermoor is warmer than it should be,
while the eastern shores of Khor'Dural are locked in perpetual winter despite
being at a moderate latitude.
"""


# ================================================================
# CONTINENTS
# ================================================================

CONTINENTS = {
    "aethermoor": {
        "name": "Aethermoor",
        "position": "northern hemisphere, western ocean",
        "size": "large island (~150km across, comparable to a large real-world island)",
        "climate": "temperate to cold, with forests, plains, and mountains",
        "description": (
            "A large island of ancient forests, fertile plains, and "
            "snow-capped mountains rising from the western ocean. Home to the "
            "five kingdoms of humans, the elven Silverwood, the dwarven Iron "
            "Peaks, and the orcish Eastern Wastes. A walking journey from coast "
            "to coast takes about three days. Despite its modest size, the island "
            "holds an outsized importance due to the Temple of Awakening at its "
            "center and the density of First Civilization ruins in its soil."
        ),
        "population": "~200,000 (humans, elves, dwarves, halflings, orcs, gnomes)",
        "nations": [
            "Kingdom of Brightblade (human feudal monarchy)",
            "Sunspear Republic (human magocracy)",
            "Ironforge Clanholds (dwarven confederation)",
            "The Silverwood Dominion (elven council)",
            "The Orcish Tribal Confederation (tribal alliances)",
            "The Azure Coast Free Cities (merchant republics)",
        ],
        "known_for": "Rich natural resources, ancient ruins, frontier spirit",
        "is_playable": True,
    },

    "khor_dural": {
        "name": "Khor'Dural",
        "position": "northern hemisphere, eastern ocean",
        "size": "large continent (the largest landmass on Edras)",
        "climate": "varied — from frozen tundra in the east to tropical coast in the west",
        "description": (
            "The oldest and most populous continent. Khor'Dural is home to the "
            "great Zarath Empire, the oldest continuously existing civilization "
            "on Edras. Its cities are vast and ancient, its magic the most "
            "refined, and its armies the most feared. The eastern half is dominated "
            "by the Frostreach — a cursed frozen wasteland where something ancient "
            "and terrible sleeps beneath the ice."
        ),
        "population": "~12 million",
        "nations": [
            "The Zarath Empire (human-led magical empire, 3000 years old)",
            "The Jade Kingdoms (three allied nations of rice farmers and martial artists)",
            "The Frostreach Nomads (hardy tribespeople surviving the eternal winter)",
            "The Dragonborn Enclaves (dragonborn city-states in the southern mountains)",
            "The Free Cities of the Western Shore (independent trading ports)",
        ],
        "known_for": "Ancient magic, vast libraries, imperial legions, silk and spice trade",
        "is_playable": False,
    },

    "sun_vaal": {
        "name": "Sun'Vaal",
        "position": "southern hemisphere, central",
        "size": "medium-large continent",
        "climate": "tropical to arid — vast jungles, deserts, and savannas",
        "description": (
            "A continent of extremes. The northern half is dense jungle inhabited "
            "by the Tabaxi (cat-folk) and ancient lizardfolk civilizations that "
            "predate all others on Edras. The southern half is the Great Sand Sea, "
            "a vast desert crossed by nomadic peoples who navigate by the stars. "
            "Between them lies the Verdant Belt — a fertile strip where the greatest "
            "Sun'Vaali cities were built along the River of Gold."
        ),
        "population": "~5 million",
        "nations": [
            "The Tabaxi Kingdoms (jungle city-states ruled by priest-kings)",
            "The Scaled Dominion (lizardfolk empire, claims to be the oldest civilization)",
            "The Sand Sea Nomads (desert peoples, masters of water and wind magic)",
            "The River Cities (trading cities along the River of Gold)",
            "The Verdant Confederation (alliance of farming communities)",
        ],
        "known_for": "Ancient pyramids, exotic beasts, gold, rare herbs, spirit magic",
        "is_playable": False,
    },

    "thal_marin": {
        "name": "Thal'Marin",
        "position": "western ocean, equatorial archipelago",
        "size": "small continent (large island chain)",
        "climate": "tropical volcanic islands with coral reefs",
        "description": (
            "Not a true continent but a vast archipelago of hundreds of volcanic "
            "islands stretching across the equatorial ocean. The sea-elves and "
            "merfolk claim the waters between the islands, while surface dwellers "
            "live on the islands themselves. The islands are the remnants of a "
            "continent that sank beneath the waves in the Age of Sundering."
        ),
        "population": "~800,000",
        "nations": [
            "The Pearl Isles (sea-elf kingdom, partly underwater)",
            "The Volcano Lords (fire-genasi who harness volcanic power)",
            "The Coral Republic (trading federation of island communities)",
            "The Merfolk Deep (undersea civilization in the trenches)",
        ],
        "known_for": "Naval power, pearls, coral, volcanic glass, sea magic",
        "is_playable": False,
    },

    "vorn_thak": {
        "name": "Vorn'Thak",
        "position": "southern polar region",
        "size": "small continent (mostly frozen)",
        "climate": "arctic — ice sheets, glaciers, and frozen tundra",
        "description": (
            "A frozen wasteland at the bottom of the world. Few venture here "
            "willingly. Beneath the ice lie the ruins of the First Civilization — "
            "the beings who built the ancient ruins found on every continent. "
            "The Frost Giants claim these lands as their own, and the few "
            "expeditions that have returned speak of cyclopean structures "
            "preserved perfectly in the ice, waiting to be found."
        ),
        "population": "~50,000 (mostly frost giants and cold-adapted peoples)",
        "nations": [
            "The Frost Giant Jarls (territorial giant clans)",
            "The Ice Walkers (human and dwarf exiles who adapted to the cold)",
            "The Frozen Archive (a single scholarly outpost studying the ruins)",
        ],
        "known_for": "Ancient secrets, adamantine deposits, danger, mystery",
        "is_playable": False,
    },
}


# ================================================================
# OCEANS AND SEAS
# ================================================================

OCEANS = {
    "great_western": {
        "name": "The Great Western Ocean",
        "description": "The vast ocean between Aethermoor and Thal'Marin. Storms are frequent but trade routes are established.",
        "dangers": "Sea serpents, pirates, magical storms during Conjunctions",
        "trade_routes": ["Aethermoor ↔ Thal'Marin (6 weeks)", "Aethermoor ↔ Sun'Vaal (10 weeks)"],
    },
    "jade_sea": {
        "name": "The Jade Sea",
        "description": "The warm sea between Khor'Dural and Sun'Vaal. Named for its green-tinged waters.",
        "dangers": "Merfolk tolls, coral reefs, kraken sightings",
        "trade_routes": ["Khor'Dural ↔ Sun'Vaal (4 weeks)", "Khor'Dural ↔ Thal'Marin (5 weeks)"],
    },
    "northern_passage": {
        "name": "The Northern Passage",
        "description": "The cold strait between Aethermoor and Khor'Dural. Icebergs make winter crossings deadly.",
        "dangers": "Icebergs, frost wyrms, ghost ships",
        "trade_routes": ["Aethermoor ↔ Khor'Dural (3 weeks in summer, impassable in winter)"],
    },
    "frozen_deep": {
        "name": "The Frozen Deep",
        "description": "The ice-choked waters around Vorn'Thak. Only the most desperate or foolish sail here.",
        "dangers": "Ice, frost giants, sea ice elementals, the Leviathan",
        "trade_routes": [],
    },
}


# ================================================================
# PLANETARY HISTORY — THE FIVE AGES
# ================================================================

PLANETARY_HISTORY = {
    "first_age": {
        "name": "The Age of Origins",
        "duration": "Unknown — perhaps 10,000+ years",
        "summary": (
            "The earliest age, shrouded in myth. The gods shaped Edras from the "
            "void and populated it with the First Civilization — beings of immense "
            "power whose true nature is debated by scholars. They built cities of "
            "crystal and stone on every continent, connected by magical portals. "
            "Their ruins still dot the landscape. They vanished suddenly and "
            "completely, leaving only their structures behind."
        ),
        "key_events": [
            "The gods create Edras and its two moons",
            "The First Civilization builds portal-connected cities on all continents",
            "The Elder Races (elves, dwarves, dragons) emerge in the First Civilization's shadow",
            "The First Civilization vanishes overnight — the Great Disappearance",
            "The portals between continents go dormant",
        ],
        "mystery": "What were the First Civilization? Why did they vanish? Some say they ascended. Others say they were destroyed. The ruins hold clues.",
    },

    "second_age": {
        "name": "The Age of Elders",
        "duration": "~5,000 years",
        "summary": (
            "With the First Civilization gone, the Elder Races inherited the world. "
            "The elves built great forest kingdoms on Aethermoor and Khor'Dural. "
            "The dwarves carved their mountain halls. The dragons claimed the "
            "highest peaks and deepest caverns. This was a time of slow growth "
            "and relative peace, as the long-lived Elder Races had little need "
            "to rush."
        ),
        "key_events": [
            "Elves establish the Silverwood on Aethermoor and the Jade Forests on Khor'Dural",
            "Dwarves found the first great mountain halls on three continents",
            "Dragons establish the Dragon Courts — loose alliances of dragon lords",
            "The lizardfolk of Sun'Vaal build the first pyramids, claiming to be taught by the First Civilization",
            "The Tabaxi emerge from the jungles as a civilized people",
            "First contact between continents via restored portal fragments (unstable)",
        ],
        "mystery": "The Dragon Courts knew something about the First Civilization. Some dragons still guard that knowledge.",
    },

    "third_age": {
        "name": "The Age of Expansion",
        "duration": "~3,000 years",
        "summary": (
            "The younger races — humans, halflings, gnomes, orcs — spread across "
            "Edras. Humans proved the most adaptable and ambitious, founding "
            "kingdoms on every continent. The Zarath Empire on Khor'Dural became "
            "the first great human civilization, eventually growing to dominate "
            "most of its continent. On Aethermoor, human settlers arrived later, "
            "carving kingdoms from the wilderness."
        ),
        "key_events": [
            "Humans spread across all continents via primitive sailing",
            "The Zarath Empire is founded on Khor'Dural (year 0 by imperial calendar)",
            "Halflings develop advanced sailing and become the first reliable inter-continental traders",
            "Orcs emerge from the mountains as organized tribal societies",
            "Gnomes discover clockwork engineering (inspired by First Civilization mechanisms)",
            "The Sand Sea Nomads learn to summon water from desert air",
            "The first human kingdoms are established on Aethermoor",
            "The Zarath Empire attempts to conquer Sun'Vaal — repelled by the Scaled Dominion",
        ],
        "mystery": "The Zarath Empire found something in a First Civilization ruin that gave them their magical supremacy. What was it?",
    },

    "fourth_age": {
        "name": "The Age of Sundering",
        "duration": "~1,000 years (ended ~500 years ago)",
        "summary": (
            "A catastrophic age. The Conjunction of the two moons triggered a "
            "magical cataclysm that sank the continent between Aethermoor and "
            "Khor'Dural, creating the Thal'Marin archipelago. Magical storms "
            "raged for decades. The Dragon Courts fell into civil war. Dark forces "
            "from the First Civilization ruins awakened across the world. Every "
            "continent suffered. This age ended when the Concord of Races united "
            "the peoples of Edras against the awakened darkness."
        ),
        "key_events": [
            "The Great Conjunction — both moons align for an unprecedented three days",
            "The continent of Thal'Mar sinks beneath the waves, creating the archipelago",
            "Magical storms sever most inter-continental portals permanently",
            "First Civilization constructs begin reactivating, spawning undead and constructs",
            "The Dragon Civil War — chromatic vs metallic dragons, devastating all continents",
            "The Zarath Empire nearly falls to internal rebellion and external threats",
            "The Scaled Dominion retreats to their deepest temples",
            "The Concord of Races — all peoples unite to seal the awakened ruins",
            "The Great War of Shadows on Aethermoor (a local manifestation of the global crisis)",
        ],
        "mystery": "The sinking of Thal'Mar was not natural. Something beneath it was deliberately destroyed — or released.",
    },

    "fifth_age": {
        "name": "The Age of Recovery (current)",
        "duration": "~500 years and counting",
        "summary": (
            "The current age. The world slowly recovers from the Sundering. "
            "Inter-continental trade has been re-established by sea, though the "
            "portals remain dormant. New nations have risen from the ashes of the "
            "old. The Zarath Empire has contracted but still dominates Khor'Dural. "
            "On Aethermoor, the five kingdoms compete for influence. Scholars "
            "study the First Civilization ruins with renewed urgency, sensing "
            "that another Conjunction approaches."
        ),
        "key_events": [
            "Aethermoor's five kingdoms stabilize and begin competing",
            "The Zarath Empire consolidates, abandoning outer provinces",
            "Sea trade routes reopen — halfling traders reconnect the continents",
            "The Frost Giants of Vorn'Thak become more aggressive, raiding the south",
            "The Frozen Archive discovers intact First Civilization texts",
            "Scholars predict the next Great Conjunction in approximately 35 years",
            "Tensions rise between the Zarath Empire and the Free Cities",
            "Aethermoor's frontier settlements expand, discovering new ruins",
            "The player arrives at the Temple of Awakening",
        ],
        "mystery": "The next Conjunction is coming. If the First Civilization ruins reactivate again, will the world survive a second Sundering?",
    },
}


# ================================================================
# INTER-CONTINENTAL RELATIONSHIPS
# ================================================================

CONTINENTAL_RELATIONS = {
    ("aethermoor", "khor_dural"): {
        "status": "cautious trade",
        "description": (
            "The Zarath Empire views Aethermoor as a backwater colony that never "
            "properly developed. Aethermoor resents the Empire's condescension. "
            "Trade flows through the Northern Passage in summer — Aethermoor "
            "exports raw materials (timber, ore, furs) and imports luxury goods "
            "(silk, spices, magical artifacts). Zarath diplomats occasionally "
            "appear at Aethermoor courts, always with ulterior motives."
        ),
    },
    ("aethermoor", "sun_vaal"): {
        "status": "rare contact",
        "description": (
            "Few from Aethermoor have visited Sun'Vaal. The journey takes months. "
            "Occasionally a Sun'Vaali trading vessel appears at the Azure Coast "
            "bearing exotic goods — golden jewelry, rare herbs, enchanted ivory. "
            "The tales they bring are extraordinary: pyramids that touch the sky, "
            "jungles where the trees walk, and deserts that sing at night."
        ),
    },
    ("aethermoor", "thal_marin"): {
        "status": "friendly trade",
        "description": (
            "The Pearl Isles of Thal'Marin are the closest foreign land to "
            "Aethermoor's Azure Coast. Halfling sailors make the six-week crossing "
            "regularly. Thal'Marin exports pearls, coral, volcanic glass, and "
            "tropical fruit. The sea-elves there have a distant kinship with "
            "Aethermoor's wood elves — they share songs across the ocean."
        ),
    },
    ("khor_dural", "sun_vaal"): {
        "status": "old rivalry",
        "description": (
            "The Zarath Empire tried to conquer Sun'Vaal a thousand years ago "
            "and failed. The resentment runs deep. The Scaled Dominion of "
            "Sun'Vaal claims their civilization predates the Zarath by millennia. "
            "Trade exists but is tense. Diplomatic incidents are frequent."
        ),
    },
}


# ================================================================
# GLOBAL LEGENDS — mysteries that span the planet
# ================================================================

GLOBAL_LEGENDS = [
    {
        "name": "The First Civilization",
        "description": (
            "Before elves, before dragons, before even the gods' memory, the "
            "First Civilization built cities on every continent connected by "
            "magical portals. Their ruins contain technology that seems more "
            "magical than magical. They vanished in a single night. Some scholars "
            "believe they didn't die — they transcended to another plane of existence."
        ),
        "known_by": ["scholars", "wizards", "high-level NPCs"],
    },
    {
        "name": "The Leviathan",
        "description": (
            "Sailors across every ocean speak of the Leviathan — a creature so "
            "vast that sailors have mistaken its back for an island. The merfolk "
            "worship it as a god. Some say it is the last of the First "
            "Civilization, transformed rather than vanished."
        ),
        "known_by": ["sailors", "halflings", "coastal NPCs"],
    },
    {
        "name": "The Conjunction Prophecy",
        "description": (
            "The next Great Conjunction of the two moons is predicted in roughly "
            "35 years. The last one caused the Sundering. Scholars debate whether "
            "the ruins will reactivate again. Some say this time the world can "
            "prepare. Others say preparation is futile."
        ),
        "known_by": ["scholars", "wizards", "clerics", "rulers"],
    },
    {
        "name": "The Sleeping God of Vorn'Thak",
        "description": (
            "Beneath the ice of Vorn'Thak, something sleeps. The Frost Giants "
            "guard it not out of worship but out of fear. The Frozen Archive has "
            "detected a heartbeat — impossibly slow, one beat per century — "
            "coming from deep beneath the southern ice cap."
        ),
        "known_by": ["scholars", "frost giant contacts", "high-level NPCs"],
    },
    {
        "name": "The Lost Portals",
        "description": (
            "The First Civilization connected every continent through magical "
            "portals. Most were destroyed in the Sundering, but legends persist "
            "of dormant portals hidden in ancient ruins. If one could be "
            "reactivated, instant travel between continents would be possible."
        ),
        "known_by": ["wizards", "archaeologists", "well-traveled merchants"],
    },
    {
        "name": "The Dragon Pact",
        "description": (
            "After the Dragon Civil War during the Sundering, the surviving "
            "dragons made a pact to never again war among themselves. The terms "
            "of this pact are secret, but dragons who break it are hunted by "
            "all others. Some say the pact binds them to protect the world "
            "from the next Conjunction."
        ),
        "known_by": ["scholars", "dragon cultists", "ancient elves"],
    },
]


# ================================================================
# KNOWLEDGE TIERS — what NPCs know about the wider world
# ================================================================

def get_planetary_knowledge(npc) -> list:
    """Get what an NPC knows about the wider world based on class, race, skills, and traits.

    Returns a list of knowledge strings suitable for known_info.
    """
    facts = []

    char_class = getattr(npc, 'char_class', '')
    race = getattr(npc, 'race', 'Human')
    skills = getattr(npc, 'npc_skills', {})
    literacy = skills.get('literacy', 0)
    history = skills.get('history', 0)
    navigation = skills.get('navigation', 0)
    arcana = skills.get('arcana', 0)

    # Everyone knows the planet name and basic geography
    facts.append(f"The world is called {PLANET_NAME}")
    facts.append("Aethermoor is one continent among several on Edras")
    facts.append("The planet has two moons — silver Lunara and copper Thal")

    # Literate/educated NPCs know more
    if literacy >= 2 or history >= 1:
        facts.append("The Zarath Empire on Khor'Dural is the oldest human civilization")
        facts.append("The Age of Sundering nearly destroyed the world 500 years ago")
        facts.append("Ancient ruins on every continent were built by the First Civilization")

    if history >= 3 or arcana >= 3:
        facts.append("The First Civilization vanished overnight in the Great Disappearance")
        facts.append("The next Great Conjunction of the moons is predicted in 35 years")
        facts.append("The continent of Thal'Mar sank during the Sundering, creating the archipelago")

    if history >= 5 or arcana >= 5:
        facts.append("Something sleeps beneath the ice of Vorn'Thak — a being from the First Civilization")
        facts.append("The Zarath Empire found something in a ruin that gave them magical supremacy")
        facts.append("Dragons made a secret pact after their civil war during the Sundering")

    # Navigators and sailors know trade routes
    if navigation >= 2 or race == "Halfling":
        facts.append("Halfling sailors connect the continents via sea trade")
        facts.append("The Northern Passage to Khor'Dural is only open in summer")
        facts.append("Thal'Marin is the closest foreign land to Aethermoor's coast")

    if navigation >= 4:
        facts.append("Sun'Vaal lies across the Great Western Ocean — a ten-week voyage")
        facts.append("The Frozen Deep around Vorn'Thak is deadly to all but the hardiest ships")

    # Racial knowledge
    if race == "Elf":
        facts.append("Our kin the sea-elves live among the Pearl Isles of Thal'Marin")
        facts.append("The elves of Khor'Dural were allies during the Age of Elders")
    elif race == "Dwarf":
        facts.append("Dwarven halls exist on three continents — we are a widespread people")
        facts.append("The finest adamantine comes from Vorn'Thak, but few survive to mine it")
    elif race == "Halfling":
        facts.append("Our people sail every ocean — we connect the continents through trade")
        facts.append("The Coral Republic in Thal'Marin is a halfling trading hub")
    elif race == "Gnome":
        facts.append("First Civilization mechanisms inspired gnomish clockwork engineering")
        facts.append("Gnome scholars maintain the Frozen Archive on Vorn'Thak")

    # Class-specific knowledge
    if char_class == "Wizard" or char_class == "Sorcerer":
        facts.append("Zarath battle-mages are said to be the most powerful on Edras")
        facts.append("The Conjunction amplifies all magical energy — spells become unpredictable")
    elif char_class == "Cleric" or char_class == "Paladin":
        facts.append("The gods who shaped Edras are worshipped differently on each continent")
        facts.append("The Tabaxi of Sun'Vaal worship beast-spirits, not the gods we know")
    elif char_class == "Ranger":
        facts.append("Sun'Vaal's jungles contain creatures found nowhere else — walking trees, sky serpents")
        facts.append("The Frostreach of eastern Khor'Dural is cursed land — a permanent winter")
    elif char_class == "Bard":
        facts.append("Every continent has legends of the First Civilization's disappearance")
        facts.append("Sun'Vaali musicians play instruments made from singing crystal")
    elif char_class == "Warlock":
        facts.append("Some warlocks draw power from entities sleeping in First Civilization ruins")
        facts.append("The thing beneath Vorn'Thak has been reaching out to sensitive minds")

    return facts
