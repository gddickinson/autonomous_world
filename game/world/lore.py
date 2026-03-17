"""
World Lore & Definition: the canonical world of Aethermoor.

This defines the default world with rich backstory, geography, factions,
settlements, and history. Used when no LLM is available for world generation.

The world of Aethermoor:
- A large island continent surrounded by ocean
- 5 major regions with distinct cultures and peoples
- A deep history of alliances, wars, and magical upheaval
- Multiple races coexisting (sometimes peacefully, sometimes not)

This file serves as both lore document and world blueprint.
An LLM can generate alternative worlds following this same structure.
"""

# ================================================================
# WORLD HISTORY
# ================================================================

WORLD_NAME = "Aethermoor"
PLANET_NAME = "Edras"

WORLD_HISTORY = """
The Continent of Aethermoor on the Planet Edras

Aethermoor is a large island in the western ocean of the planet Edras — a world
with two moons (silver Lunara and copper Thal) and five ages of history
stretching back over ten thousand years. The island lies in the northern
hemisphere of the Great Western Ocean.

In the first age, the mysterious First Civilization built portal-connected
cities on every continent, including Aethermoor. They vanished overnight
in the Great Disappearance, leaving only ruins. The Elder Races — Elves
and Dwarves — were the first to build new civilizations in their shadow.
The Elves claimed the Silverwood Forest in the west. The Dwarves carved
their halls into the Iron Peaks in the north.

Humans arrived during the Age of Expansion, settling the fertile central
plains they called the Heartlands. Ambitious and adaptable, they built
villages that grew into kingdoms. Five great castles were raised, each
becoming the seat of a noble house.

The Orcish clans inhabit the harsh eastern badlands. Some Half-Orc
communities have found acceptance in border settlements. The Halflings
built communities along the southern coast, becoming renowned sailors
who trade with distant continents. Gnomes settled in the foothills.

Five centuries ago, the Age of Sundering nearly destroyed all of Edras.
The Great Conjunction of the moons triggered a magical cataclysm that
sank an entire continent and reactivated First Civilization ruins across
the world. On Aethermoor, this manifested as the Great War of Shadows.
The races united to defeat the darkness, but the scars remain. The Temple
of Awakening was built at the center of the continent as a monument to
that alliance and a place of rebirth.

Today, Aethermoor exists in the Age of Recovery. The five kingdoms compete
for influence. Trade caravans connect the settlements, and halfling ships
connect Aethermoor to the wider world. Scholars study the First
Civilization ruins with renewed urgency — another Conjunction is predicted
in roughly 35 years. The frontier regions remain wild and dangerous,
drawing adventurers seeking fortune and glory.

Beyond Aethermoor: the vast Zarath Empire dominates the continent of
Khor'Dural across the Northern Passage. The tropical continent of
Sun'Vaal lies far to the south. The Thal'Marin archipelago — remnants
of the sunken continent — trades pearls and coral via halfling ships.
And at the bottom of the world, the frozen continent of Vorn'Thak holds
the greatest secrets of the First Civilization beneath its ice.
"""

# ================================================================
# REGION DEFINITIONS (with coordinates for 2000x2000 world)
# ================================================================

REGIONS = {
    "heartlands": {
        "name": "The Heartlands",
        "center": (1000, 1000),
        "radius": 400,
        "terrain": "plains",
        "description": "Fertile central plains, the breadbasket of Aethermoor. Rolling hills, golden wheat fields, and prosperous towns.",
        "primary_races": ["Human", "Half-Elf"],
        "culture": "Feudal kingdoms with a tradition of chivalry and commerce.",
        "known_for": "Agriculture, trade, and military strength.",
    },
    "silverwood": {
        "name": "The Silverwood",
        "center": (400, 800),
        "radius": 300,
        "terrain": "forest",
        "description": "Ancient forest of silver-barked trees, home to the Elven people for millennia. Magical groves and hidden clearings.",
        "primary_races": ["Elf", "Half-Elf"],
        "culture": "Ancient elven traditions of art, magic, and nature guardianship.",
        "known_for": "Arcane magic, herbalism, and ancient wisdom.",
    },
    "iron_peaks": {
        "name": "The Iron Peaks",
        "center": (800, 300),
        "radius": 300,
        "terrain": "mountains",
        "description": "Rugged mountain range rich in ore and gems. Dwarven halls carved deep into the stone.",
        "primary_races": ["Dwarf", "Gnome"],
        "culture": "Clan-based society centered on craftsmanship, mining, and brewing.",
        "known_for": "Superior metalwork, gemcutting, and the strongest ale in Aethermoor.",
    },
    "eastern_wastes": {
        "name": "The Eastern Wastes",
        "center": (1600, 600),
        "radius": 300,
        "terrain": "badlands",
        "description": "Harsh rocky terrain and sparse vegetation. Orcish war bands roam these unforgiving lands.",
        "primary_races": ["Half-Orc"],
        "culture": "Tribal society where strength determines leadership.",
        "known_for": "Fierce warriors, survival skills, and a code of honor through combat.",
    },
    "azure_coast": {
        "name": "The Azure Coast",
        "center": (600, 1600),
        "radius": 300,
        "terrain": "coastal",
        "description": "Sandy beaches, fishing villages, and busy ports. Halfling traders sail these waters.",
        "primary_races": ["Human", "Halfling"],
        "culture": "Maritime traditions of fishing, trading, and storytelling.",
        "known_for": "Seafood, exotic goods from distant lands, and the best stories.",
    },
}

# ================================================================
# SETTLEMENTS (with exact coordinates)
# ================================================================

SETTLEMENTS = [
    # === HEARTLANDS ===
    {"name": "Hearthstone", "kind": "village", "x": 1025, "y": 1000, "region": "heartlands",
     "race": "Human", "description": "A welcoming village near the Temple of Awakening. The first settlement most travelers encounter.",
     "notable": "Built around the crossroads leading to all five regions."},

    {"name": "Sunridge", "kind": "city", "x": 1100, "y": 900, "region": "heartlands",
     "race": "Human", "description": "The largest city in the Heartlands, known for its grand marketplace and tall walls.",
     "notable": "Seat of House Brightblade, the most powerful human noble house."},

    {"name": "Millbrook", "kind": "village", "x": 950, "y": 1100, "region": "heartlands",
     "race": "Human", "description": "A quiet farming village on the banks of a small river.",
     "notable": "Famous for its wheat and the annual harvest festival."},

    {"name": "Goldpeak", "kind": "town", "x": 1150, "y": 1050, "region": "heartlands",
     "race": "Human", "description": "A prosperous trading town at the junction of major roads.",
     "notable": "Home to the Merchant's Guild and the finest inn in the region."},

    {"name": "Thornwall", "kind": "town", "x": 1200, "y": 800, "region": "heartlands",
     "race": "Human", "description": "A fortified town guarding the eastern border against orc raids.",
     "notable": "Its walls have never been breached. Home to veteran soldiers."},

    # === SILVERWOOD ===
    {"name": "Silverleaf", "kind": "village", "x": 350, "y": 750, "region": "silverwood",
     "race": "Elf", "description": "An elven village built among the silver-barked trees. Buildings blend with nature.",
     "notable": "The village elder remembers events from 500 years ago."},

    {"name": "Moonwhisper", "kind": "village", "x": 450, "y": 850, "region": "silverwood",
     "race": "Elf", "description": "A secluded village known for its moonlit gardens and healing herbs.",
     "notable": "The finest herbalists in Aethermoor train here."},

    {"name": "Starbloom", "kind": "hamlet", "x": 300, "y": 900, "region": "silverwood",
     "race": "Half-Elf", "description": "A small settlement where half-elves have built a community between two worlds.",
     "notable": "Known for unique magical crafts blending human and elven traditions."},

    # === IRON PEAKS ===
    {"name": "Ironholt", "kind": "town", "x": 750, "y": 300, "region": "iron_peaks",
     "race": "Dwarf", "description": "The greatest dwarven settlement above ground. Forges burn day and night.",
     "notable": "Produces the finest weapons and armor in all of Aethermoor."},

    {"name": "Deepforge", "kind": "village", "x": 850, "y": 250, "region": "iron_peaks",
     "race": "Dwarf", "description": "A mining village at the entrance to the deep tunnels.",
     "notable": "Recently discovered a new vein of gold ore."},

    {"name": "Hammerfall", "kind": "village", "x": 700, "y": 350, "region": "iron_peaks",
     "race": "Gnome", "description": "A gnomish village known for inventions and clockwork devices.",
     "notable": "The gnomes here have built a working water wheel that powers their workshops."},

    # === EASTERN WASTES ===
    {"name": "Bloodfang Hold", "kind": "village", "x": 1550, "y": 550, "region": "eastern_wastes",
     "race": "Half-Orc", "description": "A fortified orc settlement built from scavenged stone and bone.",
     "notable": "The war chief here earned leadership by defeating a troll bare-handed."},

    {"name": "Ironjaw Fort", "kind": "hamlet", "x": 1650, "y": 650, "region": "eastern_wastes",
     "race": "Half-Orc", "description": "An outpost guarding the eastern trade route.",
     "notable": "Despite its fearsome name, it trades peacefully with passing caravans."},

    # === AZURE COAST ===
    {"name": "Tidehaven", "kind": "town", "x": 550, "y": 1600, "region": "azure_coast",
     "race": "Human", "description": "The largest port town on the Azure Coast. Ships from everywhere dock here.",
     "notable": "The harbor master has never lost a ship to the rocks."},

    {"name": "Coral Bay", "kind": "village", "x": 650, "y": 1650, "region": "azure_coast",
     "race": "Halfling", "description": "A cheerful halfling fishing village built on stilts over the water.",
     "notable": "Annual fish feast draws visitors from across the coast."},

    {"name": "Saltmere", "kind": "hamlet", "x": 500, "y": 1550, "region": "azure_coast",
     "race": "Human", "description": "A small salt-mining community on the coast.",
     "notable": "The salt flats here produce the finest preserving salt."},
]

# ================================================================
# CASTLES & KINGDOMS
# ================================================================

CASTLES = [
    {"name": "Northwatch Keep", "x": 900, "y": 500, "region": "heartlands",
     "ruler": "King Aldric Brightblade", "race": "Human", "class": "Paladin",
     "style": "feudalism",
     "description": "A mighty fortress on the northern border. Seat of the Brightblade dynasty.",
     "history": "Built 200 years ago after the Great War to guard against northern threats."},

    {"name": "Sunspear Castle", "x": 1200, "y": 1000, "region": "heartlands",
     "ruler": "Queen Vera Sunspear", "race": "Human", "class": "Wizard",
     "style": "republic",
     "description": "An elegant castle known for its tall spires and magical defenses.",
     "history": "The Sunspear family has ruled through wisdom and magic for five generations."},

    {"name": "Ironthrone Fortress", "x": 800, "y": 250, "region": "iron_peaks",
     "ruler": "Thane Thorin Ironforge", "race": "Dwarf", "class": "Fighter",
     "style": "feudalism",
     "description": "A massive fortress carved into the mountain itself.",
     "history": "The ancestral seat of the Ironforge clan for over a thousand years."},

    {"name": "Dragon's Gate", "x": 1500, "y": 700, "region": "eastern_wastes",
     "ruler": "Warchief Grok Bloodfist", "race": "Half-Orc", "class": "Barbarian",
     "style": "tribal",
     "description": "A fortress built from the bones of a dragon, or so the legends say.",
     "history": "The strongest orc warrior claims Dragon's Gate by right of combat."},

    {"name": "Stormhold Citadel", "x": 500, "y": 1500, "region": "azure_coast",
     "ruler": "Admiral Lyra Stormwind", "race": "Human", "class": "Ranger",
     "style": "merchant_republic",
     "description": "A coastal fortress that controls the major sea trade routes.",
     "history": "Built by merchants to protect their ships, now a seat of maritime power."},
]

# ================================================================
# RUINS & DUNGEONS
# ================================================================

RUINS = [
    {"name": "The Shattered Sanctum", "x": 1050, "y": 850, "region": "heartlands",
     "description": "Remnants of the dark temple from the Great War. Still radiates evil energy.",
     "creatures": ["skeleton", "zombie", "shadow", "wight"],
     "loot_level": 3},

    {"name": "Goblin Warren", "x": 1300, "y": 700, "region": "heartlands",
     "description": "A network of tunnels infested with goblins who raid nearby farms.",
     "creatures": ["goblin", "kobold", "rat"],
     "loot_level": 1},

    {"name": "The Elder Vault", "x": 400, "y": 700, "region": "silverwood",
     "description": "An ancient structure predating even the elves. Nobody knows who built it.",
     "creatures": ["gargoyle", "skeleton", "shadow"],
     "loot_level": 4},

    {"name": "Troll Bridge", "x": 700, "y": 500, "region": "iron_peaks",
     "description": "A stone bridge guarded by trolls who demand a toll - or your life.",
     "creatures": ["troll", "ogre"],
     "loot_level": 3},

    {"name": "The Bone Pit", "x": 1600, "y": 500, "region": "eastern_wastes",
     "description": "A mass grave from an ancient battle. Undead stir in the depths.",
     "creatures": ["skeleton", "zombie", "ghoul", "wight"],
     "loot_level": 3},

    {"name": "Sunken Crypt", "x": 600, "y": 1700, "region": "azure_coast",
     "description": "A coastal cave system that floods at high tide. Pirates once used it as a hideout.",
     "creatures": ["bandit", "giant_crab", "skeleton"],
     "loot_level": 2},

    {"name": "The Dark Hollows", "x": 350, "y": 950, "region": "silverwood",
     "description": "A corrupted section of the Silverwood where dark magic has twisted the trees.",
     "creatures": ["spider", "werewolf", "shadow"],
     "loot_level": 3},

    {"name": "Frostfang Caverns", "x": 900, "y": 200, "region": "iron_peaks",
     "description": "Ice-covered caves high in the mountains where a young dragon makes its lair.",
     "creatures": ["dire_wolf", "ogre", "young_dragon"],
     "loot_level": 5},
]

# ================================================================
# WORLD KNOWLEDGE (facts all NPCs might know)
# ================================================================

COMMON_KNOWLEDGE = [
    f"Our continent is called {WORLD_NAME}, on the planet {PLANET_NAME}",
    "The planet Edras has two moons — silver Lunara and copper Thal",
    "The Temple of Awakening stands at the center of Aethermoor",
    "Five kingdoms rule the civilized lands of Aethermoor",
    "The Great War of Shadows was part of the Age of Sundering, 500 years ago",
    "Ancient ruins from the First Civilization dot every continent",
    "Trade caravans connect our settlements, and ships reach other continents",
    "The roads are dangerous at night",
    "The Zarath Empire across the Northern Passage is the oldest human civilization",
    "Halfling sailors are the ones who connect the continents through sea trade",
    "Scholars say another Conjunction of the moons is coming in about 35 years",
]

REGIONAL_COMMON_KNOWLEDGE = {
    "heartlands": [
        "The Heartlands produce most of the food for Aethermoor",
        "House Brightblade has ruled Northwatch Keep for generations",
        "Queen Vera of Sunspear Castle is known for her magical prowess",
        "Bandits have been increasing on the eastern roads",
    ],
    "silverwood": [
        "The Silverwood is the oldest forest in Aethermoor",
        "Elven magic keeps the forest alive and vibrant",
        "The Elder Vault is forbidden - none who enter return unchanged",
        "Moonwhisper village produces the finest healing herbs",
    ],
    "iron_peaks": [
        "Thane Thorin has ruled Ironthrone Fortress for sixty years",
        "Dwarven steel is the strongest metal known",
        "A young dragon has been seen near the Frostfang Caverns",
        "The gnomes of Hammerfall are brilliant but eccentric inventors",
    ],
    "eastern_wastes": [
        "Warchief Grok earned his title by defeating a troll bare-handed",
        "The orcs follow a strict code of honor through combat",
        "Dragon's Gate is named for the dragon bones in its walls",
        "Some orc clans trade peacefully with the Heartlands",
    ],
    "azure_coast": [
        "Admiral Lyra controls the sea trade from Stormhold Citadel",
        "Halfling sailors are the best navigators in Aethermoor",
        "Pirates occasionally raid the smaller fishing villages",
        "The annual fish feast at Coral Bay draws visitors from everywhere",
    ],
}
