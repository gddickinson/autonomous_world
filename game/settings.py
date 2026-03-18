"""Game constants and configuration."""

import pygame

# Display
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800
FPS = 60
TITLE = "Autonomous World"

# Tiles
TILE_SIZE = 16
WORLD_WIDTH = 2000        # Legacy — used by old World class
WORLD_HEIGHT = 2000       # Legacy — used by old World class

# New chunked world dimensions
WORLD_WIDTH_NEW = 10000
WORLD_HEIGHT_NEW = 10000
METERS_PER_TILE = 3       # 1 tile ≈ 3 meters (buildings ~5 tiles wide = 15m)
CHUNK_SIZE = 200          # tiles per chunk side

# Camera
CAMERA_LERP = 0.08

# Player
PLAYER_SPEED = 3.5
PLAYER_MAX_HP = 100
PLAYER_MAX_ENERGY = 100
PLAYER_ATTACK_RANGE = 1.5
PLAYER_ATTACK_DAMAGE = 15
PLAYER_ATTACK_COOLDOWN = 0.4

# NPCs
NPC_SPEED = 1.2
NPC_INTERACTION_RANGE = 2.0
NPC_VISION_RANGE = 8.0

# Creatures
CREATURE_SPEED = 1.8
CREATURE_CHASE_RANGE = 6.0
CREATURE_ATTACK_RANGE = 1.2
CREATURE_ATTACK_COOLDOWN = 1.0

# Time
DAY_LENGTH = 600.0  # seconds for a full day
DAWN_START = 0.20
DAY_START = 0.30
DUSK_START = 0.70
NIGHT_START = 0.80

# Terrain types
WATER = 0
SAND = 1
GRASS = 2
FOREST = 3
DENSE_FOREST = 4
MOUNTAIN = 5
SNOW = 6
ROAD = 7
FLOOR = 8
WALL = 9
BRIDGE = 10
FARMLAND = 11
SWAMP = 12
BUILT_WALL = 13
BUILT_FLOOR = 14
TREE_STUMP = 15
TILLED_SOIL = 16
TABLE = 17
BED = 18
CHEST = 19
DOOR = 20
STAIRS_UP = 21
STAIRS_DOWN = 22
WINDOW = 23
LOCKED_DOOR = 24
ORE_VEIN = 25
HERB_PATCH = 26
BERRY_BUSH = 27
CLAY_PIT = 28
MUSHROOMS = 29
WHEAT_FIELD = 30
VEGETABLE_PLOT = 31
FRUIT_TREE = 32
FLOWER_BED = 33
GEM_DEPOSIT = 34
COPPER_VEIN = 35
FLAX_FIELD = 36
BEEHIVE = 37
SALT_FLAT = 38
RUBBLE = 39         # destroyed wall/building debris
SHALLOW_WATER = 40  # wadeable water near shores
ROCKY_GROUND = 41   # rough terrain near mountains
MARSH = 42          # wet grassland near water
GRAVEL_ROAD = 43    # minor roads/paths
FALLEN_TREE = 44    # natural obstacle, harvestable
WELL = 45           # water source in settlements
PILLAR = 46         # stone pillar/column (blocks movement)
ALTAR = 47          # altar/shrine (interactable)
FIREPLACE = 48      # hearth/chimney (warmth + light)
LADDER_UP = 49      # ladder going up
LADDER_DOWN = 50    # ladder going down
THRONE = 51         # ruler's throne
BOOKSHELF = 52      # bookshelf (interactable, blocks movement)
BARREL = 53         # barrel (storage, blocks movement)
ANVIL = 54          # blacksmith's anvil
FORGE_FIRE = 55     # forge fire (hot, light source)
FOUNTAIN = 56       # decorative fountain (water source)
CARPET = 57         # floor carpet (decorative, walkable)
MOSAIC = 58         # mosaic floor (decorative, walkable)
ARCHWAY = 59        # open archway (walkable, no door)
IRON_GATE = 60      # portcullis/iron gate (lockable)
CLIFF = 61          # steep cliff face (needs climbing skill)
GORGE = 62          # deep gorge (needs rope/bridge)
MOUNTAIN_PASS = 63  # passable mountain route (slow but traversable)
DIRT_TRACK = 64     # minor path between hamlets
COBBLESTONE = 65    # paved city road (fastest)
STABLE_FLOOR = 66   # stable interior (walkable, mount-related)
GRAVESTONE = 67     # grave marker (walkable, interactable)
COURTYARD = 68      # open courtyard (walkable, outdoor interior)
ARENA_SAND = 69     # arena fighting floor (walkable, combat zone)

# Multiplayer
DEFAULT_PORT = 7777
MAX_PLAYERS = 2

TERRAIN_COLORS = {
    WATER:        (41, 128, 185),
    SAND:         (214, 196, 153),
    GRASS:        (86, 152, 72),
    FOREST:       (50, 115, 45),
    DENSE_FOREST: (30, 80, 28),
    MOUNTAIN:     (139, 119, 101),
    SNOW:         (230, 235, 240),
    ROAD:         (170, 145, 100),
    FLOOR:        (160, 130, 95),
    WALL:         (90, 80, 70),
    BRIDGE:       (140, 110, 70),
    FARMLAND:     (120, 145, 60),
    SWAMP:        (75, 110, 55),
    BUILT_WALL:   (110, 95, 80),
    BUILT_FLOOR:  (150, 125, 90),
    TREE_STUMP:   (100, 130, 65),
    TILLED_SOIL:  (95, 80, 50),
    TABLE:        (140, 110, 70),
    BED:          (120, 80, 60),
    CHEST:        (160, 130, 50),
    DOOR:         (130, 100, 60),
    STAIRS_UP:    (150, 140, 130),
    STAIRS_DOWN:  (100, 90, 85),
    WINDOW:       (140, 170, 200),
    LOCKED_DOOR:  (110, 80, 50),
    ORE_VEIN:     (160, 140, 110),
    HERB_PATCH:   (60, 140, 80),
    BERRY_BUSH:   (120, 60, 80),
    CLAY_PIT:     (170, 140, 100),
    MUSHROOMS:    (140, 120, 90),
    WHEAT_FIELD:  (200, 180, 80),
    VEGETABLE_PLOT: (80, 160, 60),
    FRUIT_TREE:   (100, 150, 60),
    FLOWER_BED:   (180, 120, 160),
    GEM_DEPOSIT:  (130, 100, 140),
    COPPER_VEIN:  (180, 120, 80),
    FLAX_FIELD:   (150, 180, 100),
    BEEHIVE:      (200, 180, 60),
    SALT_FLAT:    (220, 220, 210),
    RUBBLE:       (120, 110, 100),
    SHALLOW_WATER:(80, 150, 190),
    ROCKY_GROUND: (130, 120, 110),
    MARSH:        (70, 120, 70),
    GRAVEL_ROAD:  (150, 140, 120),
    FALLEN_TREE:  (80, 100, 50),
    WELL:         (60, 120, 180),
    PILLAR:       (160, 155, 145),
    ALTAR:        (180, 170, 140),
    FIREPLACE:    (180, 80, 30),
    LADDER_UP:    (140, 120, 80),
    LADDER_DOWN:  (110, 95, 65),
    THRONE:       (170, 140, 50),
    BOOKSHELF:    (100, 75, 45),
    BARREL:       (130, 100, 55),
    ANVIL:        (100, 100, 110),
    FORGE_FIRE:   (220, 120, 30),
    FOUNTAIN:     (70, 140, 200),
    CARPET:       (140, 50, 50),
    MOSAIC:       (160, 140, 100),
    ARCHWAY:      (140, 125, 105),
    IRON_GATE:    (80, 80, 90),
    CLIFF:        (110, 95, 85),
    GORGE:        (70, 60, 55),
    MOUNTAIN_PASS:(155, 140, 120),
    DIRT_TRACK:   (160, 140, 105),
    COBBLESTONE:  (145, 145, 150),
    STABLE_FLOOR: (140, 115, 75),
    GRAVESTONE:   (140, 135, 130),
    COURTYARD:    (180, 170, 140),
    ARENA_SAND:   (200, 180, 120),
}

TERRAIN_WALK_COST = {
    WATER: 999,
    SAND: 1.5,
    GRASS: 1.0,
    FOREST: 1.4,
    DENSE_FOREST: 2.0,
    MOUNTAIN: 999,
    SNOW: 2.5,
    ROAD: 0.6,
    FLOOR: 0.8,
    WALL: 999,
    BRIDGE: 0.7,
    FARMLAND: 1.2,
    SWAMP: 2.5,
    BUILT_WALL: 999,
    BUILT_FLOOR: 0.8,
    TREE_STUMP: 1.0,
    TILLED_SOIL: 1.1,
    TABLE: 999,
    BED: 999,
    CHEST: 999,
    DOOR: 0.8,
    STAIRS_UP: 0.8,
    STAIRS_DOWN: 0.8,
    WINDOW: 999,       # can't walk through windows
    LOCKED_DOOR: 999,  # locked until unlocked
    ORE_VEIN: 1.5,
    HERB_PATCH: 1.0,
    BERRY_BUSH: 1.2,
    CLAY_PIT: 1.3,
    MUSHROOMS: 1.5,
    WHEAT_FIELD: 1.0,
    VEGETABLE_PLOT: 1.0,
    FRUIT_TREE: 999,   # can't walk through trees
    FLOWER_BED: 1.0,
    GEM_DEPOSIT: 1.5,
    COPPER_VEIN: 1.5,
    FLAX_FIELD: 1.0,
    BEEHIVE: 999,     # can't walk through beehive
    SALT_FLAT: 0.8,
    RUBBLE: 2.0,         # slow to walk through rubble
    SHALLOW_WATER: 2.0,  # wadeable but slow
    ROCKY_GROUND: 1.5,   # rough terrain
    MARSH: 2.5,          # boggy
    GRAVEL_ROAD: 0.7,    # slightly slower than road
    FALLEN_TREE: 999,    # can't walk over (need to chop)
    WELL: 0.8,           # walkable - draw water when adjacent
    PILLAR: 999,         # can't walk through pillars
    ALTAR: 999,          # can't walk through altars
    FIREPLACE: 999,      # can't walk through fireplaces
    LADDER_UP: 0.8,      # climbable
    LADDER_DOWN: 0.8,    # climbable
    THRONE: 999,         # can't walk through throne
    BOOKSHELF: 999,      # can't walk through bookshelves
    BARREL: 999,         # can't walk through barrels
    ANVIL: 999,          # can't walk through anvil
    FORGE_FIRE: 999,     # can't walk through forge
    FOUNTAIN: 999,       # can't walk through fountain
    CARPET: 0.8,         # walkable carpet
    MOSAIC: 0.8,         # walkable mosaic
    ARCHWAY: 0.7,        # walkable archway
    IRON_GATE: 999,      # locked gate - not walkable until opened
    CLIFF: 999,          # impassable without climbing skill >= 5
    GORGE: 999,          # impassable without rope/bridge
    MOUNTAIN_PASS: 1.8,  # passable but slow mountain route
    DIRT_TRACK: 0.8,     # minor path, faster than grass
    COBBLESTONE: 0.55,   # best road surface
    STABLE_FLOOR: 0.8,   # stable interior
    GRAVESTONE: 1.0,     # walkable grave marker
    COURTYARD: 0.9,     # open courtyard, slightly slower than floor
    ARENA_SAND: 1.0,    # arena fighting floor
}

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (220, 50, 50)
GREEN = (50, 200, 50)
BLUE = (50, 100, 220)
YELLOW = (240, 220, 60)
ORANGE = (230, 150, 40)
GRAY = (150, 150, 150)
DARK_GRAY = (60, 60, 60)
LIGHT_GRAY = (200, 200, 200)

UI_BG = (20, 20, 30, 200)
UI_BORDER = (80, 80, 100)
UI_TEXT = (220, 220, 230)
UI_HIGHLIGHT = (100, 140, 200)
UI_HP_BAR = (180, 40, 40)
UI_ENERGY_BAR = (40, 140, 180)
UI_XP_BAR = (140, 120, 40)

# Consciousness colors
CONSCIOUSNESS_COLORS = {
    0: (140, 140, 200),  # Basic - soft blue
    1: (100, 200, 120),  # Aware - green
    2: (220, 200, 80),   # Conscious - gold
    3: (220, 100, 220),  # Enlightened - purple
}

# Item types
ITEM_WEAPON = "weapon"
ITEM_ARMOR = "armor"
ITEM_CONSUMABLE = "consumable"
ITEM_RESOURCE = "resource"
ITEM_QUEST = "quest"
ITEM_TOOL = "tool"
ITEM_FOOD = "food"
ITEM_DRINK = "drink"

# NPC Simulation
NPC_DECISION_INTERVAL = 8.0          # seconds between LLM decision calls (near player)
NPC_DECISION_INTERVAL_FAR = 20.0     # for distant NPCs
NPC_DECISION_PRIORITY_RANGE = 25.0   # tiles - within this, NPC gets frequent LLM calls
NPC_MAX_MEMORIES = 40
NPC_CONVERSATION_RANGE = 3.0
NPC_MAX_INVENTORY = 12
NPC_NEED_CRITICAL = 15
NPC_FORAGE_TIME = 4.0
NPC_CHOP_TIME = 5.0
NPC_MINE_TIME = 8.0
NPC_BUILD_TIME = 6.0
NPC_FARM_TIME = 4.0
NPC_TRAIN_TIME = 6.0
NPC_PERFORM_TIME = 5.0
NPC_RESEARCH_TIME = 6.0
NPC_RITUAL_TIME = 10.0
NPC_ENCHANT_TIME = 8.0
NPC_CRAFT_TIME = 5.0
NPC_HEAL_TIME = 4.0

# Need decay rates (per real second, at 1x time speed)
NEED_DECAY = {
    "hunger": 0.10,
    "thirst": 0.14,
    "rest":   0.08,
    "social": 0.05,
}

# Attribute biases per profession {attr: bonus}
PROFESSION_ATTRIBUTES = {
    # Original
    "Philosopher": {"intelligence": 3, "perception": 2},
    "Blacksmith":  {"strength": 3, "dexterity": 1},
    "Merchant":    {"charisma": 3, "intelligence": 1},
    "Farmer":      {"strength": 2, "constitution": 2},
    "Scholar":     {"intelligence": 3, "perception": 1},
    "Bard":        {"charisma": 3, "dexterity": 1},
    "Guard":       {"strength": 2, "constitution": 2},
    "Ranger":      {"dexterity": 2, "perception": 2},
    "Healer":      {"intelligence": 2, "perception": 2},
    "Innkeeper":   {"charisma": 2, "constitution": 1},
    "Miner":       {"strength": 3, "constitution": 1},
    "Fisher":      {"dexterity": 2, "perception": 1},
    # Primary Production
    "Fisherman":   {"dexterity": 2, "perception": 1},
    "Hunter":      {"dexterity": 2, "perception": 2},
    "Herbalist":   {"intelligence": 1, "perception": 3},
    "Woodcutter":  {"strength": 3, "constitution": 1},
    "Shepherd":    {"perception": 2, "constitution": 1},
    "Beekeeper":   {"perception": 2, "dexterity": 1},
    "Prospector":  {"perception": 3, "constitution": 1},
    # Crafting/Manufacturing
    "Armourer":    {"strength": 2, "dexterity": 2},
    "Carpenter":   {"strength": 2, "dexterity": 2},
    "Cooper":      {"dexterity": 2, "strength": 1},
    "Wheelwright": {"dexterity": 2, "strength": 1},
    "Shipbuilder": {"strength": 3, "dexterity": 1},
    "Tanner":      {"constitution": 2, "dexterity": 1},
    "Weaver":      {"dexterity": 3, "perception": 1},
    "Potter":      {"dexterity": 3, "perception": 1},
    "Baker":       {"dexterity": 1, "constitution": 1},
    "Brewer":      {"constitution": 2, "perception": 1},
    "Alchemist":   {"intelligence": 3, "perception": 1},
    "Jeweler":     {"dexterity": 3, "perception": 1},
    "Glassblower": {"dexterity": 2, "constitution": 1},
    # Services
    "Cook":        {"dexterity": 1, "perception": 1},
    "Servant":     {"constitution": 1, "dexterity": 1},
    "Shop Assistant": {"charisma": 2, "dexterity": 1},
    "Banker":      {"intelligence": 3, "charisma": 1},
    "Barber":      {"dexterity": 2, "charisma": 2},
    # Administrative/Leadership
    "Captain":     {"strength": 2, "charisma": 2},
    "Tax Collector": {"charisma": 1, "intelligence": 2},
    "Steward":     {"intelligence": 2, "charisma": 2},
    "Scribe":      {"intelligence": 3, "dexterity": 1},
    "Diplomat":    {"charisma": 3, "intelligence": 1},
    "Advisor":     {"intelligence": 2, "charisma": 2},
    # Skilled/Professional
    "Mason":       {"strength": 3, "constitution": 1},
    "Animal Trainer": {"perception": 2, "charisma": 1},
    "Stablemaster":{"strength": 1, "perception": 2},
    "Cartographer":{"intelligence": 2, "perception": 2},
    # Construction/Labor
    "Builder":     {"strength": 2, "constitution": 2},
    "Cleaner":     {"constitution": 2, "dexterity": 1},
    "Gravedigger": {"strength": 2, "constitution": 2},
    "Porter":      {"strength": 3, "constitution": 1},
    "Laborer":     {"strength": 2, "constitution": 2},
    # Specialization professions (geographic)
    "Sailor":          {"dexterity": 2, "constitution": 2},
    "Dock Worker":     {"strength": 3, "constitution": 1},
    "Net Maker":       {"dexterity": 3, "perception": 1},
    "Charcoal Burner": {"constitution": 2, "strength": 2},
    "Miller":          {"strength": 2, "constitution": 1},
    "Water Carrier":   {"strength": 2, "constitution": 2},
    "Caravaneer":      {"constitution": 2, "charisma": 1},
    "Peat Cutter":     {"strength": 2, "constitution": 2},
    "Smelter":         {"strength": 2, "constitution": 2},
    "Soldier":         {"strength": 2, "constitution": 2},
    "Spy":             {"dexterity": 2, "charisma": 2},
    "Lighthouse Keeper": {"perception": 3, "constitution": 1},
}

# Professions
PROFESSIONS = [
    # Original
    "Philosopher", "Blacksmith", "Merchant", "Farmer", "Scholar",
    "Bard", "Guard", "Ranger", "Healer", "Innkeeper", "Miner", "Fisher",
    # Primary Production
    "Fisherman", "Hunter", "Herbalist", "Woodcutter", "Shepherd",
    "Beekeeper", "Prospector",
    # Crafting/Manufacturing
    "Armourer", "Carpenter", "Cooper", "Wheelwright", "Shipbuilder",
    "Tanner", "Weaver", "Potter", "Baker", "Brewer", "Alchemist",
    "Jeweler", "Glassblower",
    # Services
    "Cook", "Servant", "Shop Assistant", "Banker", "Barber",
    # Administrative/Leadership
    "Captain", "Tax Collector", "Steward", "Scribe", "Diplomat", "Advisor",
    # Skilled/Professional
    "Mason", "Animal Trainer", "Stablemaster", "Cartographer",
    # Construction/Labor
    "Builder", "Cleaner", "Gravedigger", "Porter", "Laborer",
    # Specialization professions (geographic)
    "Sailor", "Dock Worker", "Net Maker", "Charcoal Burner", "Miller",
    "Water Carrier", "Caravaneer", "Peat Cutter", "Smelter", "Soldier",
    "Spy", "Lighthouse Keeper",
]

# Settlement-type weighted profession pools for NPC spawning
SETTLEMENT_PROFESSIONS = {
    "hamlet": [
        ("Farmer", 5), ("Woodcutter", 3), ("Shepherd", 2), ("Hunter", 2),
        ("Herbalist", 1), ("Fisher", 1), ("Fisherman", 1), ("Laborer", 2),
    ],
    "village": [
        ("Farmer", 4), ("Woodcutter", 2), ("Shepherd", 1), ("Hunter", 1),
        ("Fisherman", 1), ("Blacksmith", 1), ("Baker", 1), ("Innkeeper", 1),
        ("Guard", 2), ("Carpenter", 1), ("Tanner", 1), ("Healer", 1),
        ("Mason", 1), ("Laborer", 1),
    ],
    "town": [
        ("Farmer", 3), ("Woodcutter", 1), ("Fisherman", 1), ("Blacksmith", 1),
        ("Baker", 1), ("Innkeeper", 1), ("Guard", 2), ("Carpenter", 1),
        ("Tanner", 1), ("Weaver", 1), ("Potter", 1), ("Brewer", 1),
        ("Merchant", 2), ("Healer", 1), ("Scribe", 1), ("Cook", 1),
        ("Mason", 1), ("Barber", 1), ("Shop Assistant", 1), ("Porter", 1),
        ("Captain", 1), ("Steward", 1),
    ],
    "city": [
        ("Farmer", 2), ("Blacksmith", 1), ("Armourer", 1), ("Baker", 1),
        ("Innkeeper", 1), ("Guard", 3), ("Captain", 1), ("Carpenter", 1),
        ("Tanner", 1), ("Weaver", 1), ("Potter", 1), ("Brewer", 1),
        ("Merchant", 3), ("Healer", 1), ("Scribe", 1), ("Cook", 1),
        ("Mason", 1), ("Barber", 1), ("Shop Assistant", 2), ("Porter", 1),
        ("Banker", 1), ("Diplomat", 1), ("Alchemist", 1), ("Advisor", 1),
        ("Tax Collector", 1), ("Steward", 1), ("Bard", 1), ("Scholar", 1),
        ("Wheelwright", 1), ("Cooper", 1), ("Cartographer", 1),
        ("Stablemaster", 1), ("Animal Trainer", 1),
        ("Jeweler", 1), ("Glassblower", 1),
    ],
    "castle": [
        ("Guard", 4), ("Captain", 2), ("Servant", 3), ("Cook", 1),
        ("Steward", 1), ("Advisor", 1), ("Scribe", 1), ("Blacksmith", 1),
        ("Stablemaster", 1), ("Tax Collector", 1),
    ],
}

# NPC work action durations (seconds) for new professions
NPC_BREW_TIME = 5.0
NPC_TAN_TIME = 5.0
NPC_WEAVE_TIME = 5.0
NPC_BAKE_TIME = 4.0
NPC_ALCHEMY_TIME = 6.0
NPC_CARPENTRY_TIME = 5.0
NPC_POTTERY_TIME = 5.0
NPC_MASON_TIME = 6.0
NPC_BARBER_TIME = 3.0

# NPC Names
NPC_NAMES = [
    "Aria", "Bram", "Celia", "Daven", "Elena", "Finn", "Greta",
    "Hector", "Iris", "Jasper", "Kira", "Liam", "Maya", "Nolan",
    "Petra", "Quinn", "Rowan", "Sage", "Theron", "Vera", "Wren",
    "Xander", "Yara", "Zane", "Aldric", "Brynn", "Corin", "Dahlia",
    "Emeric", "Faye", "Gareth", "Hazel", "Ivo", "Juno", "Kai"
]

# Creature types (fallback stats — D&D MONSTERS dict in data/dnd.py is authoritative)
CREATURE_TYPES = {
    # Original hostile
    "wolf": {"hp": 30, "damage": 8, "speed": 2.2, "xp": 15, "color": (120, 110, 100)},
    "bear": {"hp": 60, "damage": 15, "speed": 1.5, "xp": 30, "color": (100, 70, 40)},
    "bandit": {"hp": 40, "damage": 12, "speed": 1.8, "xp": 25, "color": (150, 50, 50)},
    "skeleton": {"hp": 35, "damage": 10, "speed": 1.6, "xp": 20, "color": (200, 200, 190)},
    "spider": {"hp": 20, "damage": 6, "speed": 2.5, "xp": 10, "color": (60, 50, 50)},
    "boar": {"hp": 25, "damage": 7, "speed": 2.0, "xp": 12, "color": (110, 80, 60)},
    # Domestic / farm animals
    "cow": {"hp": 20, "damage": 2, "speed": 0.8, "xp": 5, "color": (160, 130, 100)},
    "sheep": {"hp": 12, "damage": 1, "speed": 1.0, "xp": 3, "color": (220, 215, 200)},
    "chicken": {"hp": 5, "damage": 0, "speed": 1.5, "xp": 1, "color": (200, 180, 130)},
    "pig": {"hp": 15, "damage": 3, "speed": 1.2, "xp": 4, "color": (210, 170, 150)},
    "goat": {"hp": 12, "damage": 2, "speed": 1.4, "xp": 3, "color": (180, 170, 155)},
    "horse": {"hp": 30, "damage": 5, "speed": 3.0, "xp": 8, "color": (140, 100, 60)},
    "donkey": {"hp": 25, "damage": 3, "speed": 1.5, "xp": 5, "color": (130, 120, 110)},
    "dog": {"hp": 15, "damage": 4, "speed": 2.5, "xp": 5, "color": (150, 120, 80)},
    "cat": {"hp": 8, "damage": 2, "speed": 2.0, "xp": 2, "color": (170, 140, 100)},
    # Wildlife
    "deer": {"hp": 18, "damage": 2, "speed": 2.8, "xp": 8, "color": (160, 130, 90)},
    "elk": {"hp": 35, "damage": 8, "speed": 2.2, "xp": 15, "color": (140, 110, 70)},
    "rabbit": {"hp": 3, "damage": 0, "speed": 3.0, "xp": 1, "color": (180, 160, 140)},
    "fox": {"hp": 10, "damage": 3, "speed": 2.5, "xp": 5, "color": (200, 130, 50)},
    "hawk": {"hp": 8, "damage": 4, "speed": 3.5, "xp": 5, "color": (120, 100, 80)},
    "eagle": {"hp": 15, "damage": 6, "speed": 3.5, "xp": 10, "color": (100, 80, 60)},
    "crow": {"hp": 5, "damage": 1, "speed": 2.8, "xp": 1, "color": (30, 30, 35)},
    "snake": {"hp": 8, "damage": 5, "speed": 1.8, "xp": 5, "color": (80, 120, 60)},
    "frog": {"hp": 3, "damage": 0, "speed": 1.5, "xp": 1, "color": (60, 140, 50)},
    "fish": {"hp": 5, "damage": 0, "speed": 2.0, "xp": 2, "color": (100, 150, 180)},
    "turtle": {"hp": 15, "damage": 1, "speed": 0.5, "xp": 3, "color": (80, 100, 60)},
    "owl": {"hp": 10, "damage": 3, "speed": 2.0, "xp": 4, "color": (140, 130, 110)},
    "bat": {"hp": 5, "damage": 2, "speed": 2.5, "xp": 2, "color": (60, 50, 50)},
    "rat": {"hp": 4, "damage": 1, "speed": 2.0, "xp": 1, "color": (120, 110, 100)},
    "squirrel": {"hp": 3, "damage": 0, "speed": 3.0, "xp": 1, "color": (160, 100, 50)},
    # Dangerous predators
    "mountain_lion": {"hp": 40, "damage": 12, "speed": 2.8, "xp": 25, "color": (180, 150, 100)},
    "dire_wolf": {"hp": 50, "damage": 14, "speed": 2.5, "xp": 30, "color": (100, 95, 90)},
    "giant_spider": {"hp": 30, "damage": 10, "speed": 2.0, "xp": 20, "color": (50, 45, 40)},
    "giant_scorpion": {"hp": 35, "damage": 12, "speed": 1.5, "xp": 22, "color": (100, 70, 40)},
    "crocodile": {"hp": 45, "damage": 15, "speed": 1.2, "xp": 28, "color": (70, 90, 50)},
    "wild_boar": {"hp": 25, "damage": 8, "speed": 2.0, "xp": 15, "color": (100, 80, 60)},
    "viper": {"hp": 12, "damage": 8, "speed": 1.5, "xp": 10, "color": (60, 80, 40)},
    # Mythical / fantasy
    "griffin": {"hp": 80, "damage": 20, "speed": 3.0, "xp": 60, "color": (180, 160, 80)},
    "wyvern": {"hp": 70, "damage": 18, "speed": 2.8, "xp": 50, "color": (80, 100, 60)},
    "basilisk": {"hp": 60, "damage": 16, "speed": 1.5, "xp": 45, "color": (60, 80, 50)},
    "phoenix": {"hp": 50, "damage": 15, "speed": 3.5, "xp": 55, "color": (240, 160, 40)},
    "unicorn": {"hp": 40, "damage": 10, "speed": 3.0, "xp": 35, "color": (240, 240, 250)},
    "troll": {"hp": 80, "damage": 18, "speed": 1.5, "xp": 40, "color": (80, 120, 70)},
    "ogre": {"hp": 65, "damage": 16, "speed": 1.3, "xp": 35, "color": (140, 120, 90)},
    "harpy": {"hp": 30, "damage": 10, "speed": 2.5, "xp": 20, "color": (160, 130, 100)},
    "minotaur": {"hp": 75, "damage": 20, "speed": 1.8, "xp": 45, "color": (130, 100, 70)},
    "centaur": {"hp": 50, "damage": 14, "speed": 2.8, "xp": 30, "color": (160, 140, 110)},
}
