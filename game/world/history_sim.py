"""History Simulation — generates world settlements through centuries of simulated history.

Runs at world creation time and simulates ~500 years of tribal migration,
settlement founding, warfare, diplomacy, and development to produce realistic
settlement placement, road networks, kingdom boundaries, and ruins.

The simulation operates on the coarse elevation cache (1000x1000 for a
10,000x10,000 world) so it completes in a few seconds.

Output is a HistoryResult that WorldPlan converts into its standard
SettlementPlan / RoadPlan / SpecialLocation / kingdom data structures.
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set, Callable

import numpy as np


# ================================================================
# CONFIGURATION
# ================================================================

# Elevation thresholds (must match chunk_generator / world_plan)
WATER_THRESHOLD = 0.22
SAND_THRESHOLD = 0.28
MOUNTAIN_THRESHOLD = 0.65
SNOW_THRESHOLD = 0.78

# Settlement growth thresholds
POP_HAMLET = 30
POP_VILLAGE = 80
POP_TOWN = 250
POP_CITY = 600

# Tribe entry definitions
TRIBE_TEMPLATES = [
    # (race, anchor_side, count, pop_range, trait_sets)
    ("Human",  "south",  3, (80, 150),  [{"mercantile", "expansionist"}, {"agrarian", "defensive"}, {"mercantile", "aggressive"}]),
    ("Elf",    "northwest", 2, (50, 100), [{"isolationist", "scholarly"}, {"defensive", "nature"}]),
    ("Dwarf",  "northeast", 2, (60, 120), [{"industrious", "defensive"}, {"mercantile", "industrious"}]),
    ("Orc",    "east",   2, (70, 130),  [{"aggressive", "expansionist"}, {"aggressive", "nomadic"}]),
    ("Goblin", "scattered", 3, (40, 80), [{"sneaky", "nomadic"}, {"aggressive", "sneaky"}, {"sneaky", "mercantile"}]),
    ("Undead", "wilderness", 1, (30, 60), [{"aggressive", "isolationist"}]),
]

# Name pools
HUMAN_SETTLEMENT_NAMES = [
    "Millbrook", "Ashford", "Goldpeak", "Sunridge", "Highcross",
    "Thornwall", "Copperdale", "Silverbend", "Stormwatch", "Embervale",
    "Dawnspire", "Starfall", "Greymoor", "Brighthollow", "Oakshire",
    "Riverford", "Castlebridge", "Kingsfield", "Whitehaven", "Redmoor",
    "Greenhollow", "Fairwind", "Ironton", "Lakemere", "Willowdale",
    "Northgate", "Southpass", "Eastmarch", "Westbrook", "Hillcrest",
    "Marshton", "Stonecross", "Heatherwick", "Granitevale", "Brackenwood",
    "Foxborough", "Pinevale", "Eaglesrest", "Havenport", "Dunmere",
]

ELF_SETTLEMENT_NAMES = [
    "Silverleaf", "Moonwhisper", "Starbloom", "Willowglen",
    "Dewlight", "Thornrose", "Mistwood", "Crystalbrook",
    "Starweave", "Dreamhaven", "Silverthorn", "Leafshadow",
    "Moonpetal", "Duskhollow", "Sunveil", "Briarlight",
    "Ambergrove", "Fawnmere", "Gladewhisper", "Ivoryspire",
]

DWARF_SETTLEMENT_NAMES = [
    "Ironholt", "Stonehaven", "Deepforge", "Hammerfall",
    "Granite Hall", "Anvil's Rest", "Coppermine", "Silverdelve",
    "Steelpeak", "Forgecrest", "Boulderholm", "Oreheart",
    "Cinderhold", "Blackrock", "Goldvein", "Firebrand Hall",
    "Ironclad", "Mithrildeep", "Thunderpeak", "Obsidian Gate",
]

ORC_SETTLEMENT_NAMES = [
    "Skullcrush Camp", "Bloodfang Hold", "Ashbone Warren",
    "Ironjaw Fort", "Razormaw Den", "Blackfist Outpost",
    "Goretusk Lair", "Snaggletooth Hollow", "Bonepile Camp",
    "Rotgut Stronghold", "Wartusk Fortress", "Grimsnarl Pit",
    "Thundermaw Camp", "Doomcrag Hold", "Ripfang Outpost",
]

GOBLIN_SETTLEMENT_NAMES = [
    "Snotgulch", "Rathole", "Gloomburrow", "Skritch Warren",
    "Muckmire", "Toadstool Hollow", "Moldpit", "Sludgeden",
    "Wormhole", "Rottooth Caves", "Puddlewick", "Filchburrow",
    "Knifenick", "Greasy Bend", "Fungus Grotto",
]

UNDEAD_SETTLEMENT_NAMES = [
    "Necropolis", "Dreadkeep", "Hollow Throne", "Ashenveil",
    "Bonecrypt", "Soulrest", "The Pale Citadel", "Tombhaven",
    "Wighthall", "Grimbarrow", "Dustcrown", "Voidspire",
]

RACE_NAME_POOLS = {
    "Human": HUMAN_SETTLEMENT_NAMES,
    "Elf": ELF_SETTLEMENT_NAMES,
    "Dwarf": DWARF_SETTLEMENT_NAMES,
    "Orc": ORC_SETTLEMENT_NAMES,
    "Goblin": GOBLIN_SETTLEMENT_NAMES,
    "Undead": UNDEAD_SETTLEMENT_NAMES,
}

# Race alliance affinities: positive = likely allies, negative = likely enemies
RACE_AFFINITY = {
    ("Human", "Elf"):     30,
    ("Human", "Dwarf"):   20,
    ("Human", "Orc"):    -30,
    ("Human", "Goblin"): -20,
    ("Human", "Undead"): -40,
    ("Elf",   "Dwarf"):   10,
    ("Elf",   "Orc"):    -30,
    ("Elf",   "Goblin"): -15,
    ("Elf",   "Undead"): -50,
    ("Dwarf", "Orc"):    -20,
    ("Dwarf", "Goblin"): -25,
    ("Dwarf", "Undead"): -30,
    ("Orc",   "Goblin"):  10,
    ("Orc",   "Undead"):  -5,
    ("Goblin","Undead"):   0,
}

# Kingdom governance styles by race
RACE_GOVERNANCE = {
    "Human": "feudalism",
    "Elf":   "republic",
    "Dwarf": "feudalism",
    "Orc":   "tyranny",
    "Goblin": "tribal",
    "Undead": "autocracy",
}


# Ruin types — flavour categories for destroyed / ancient structures
RUIN_TYPES = [
    "abandoned_castle",    # fallen kingdom's fortress
    "ruined_tower",        # wizard's tower, now crumbling
    "old_dungeon",         # underground prison/vault
    "ancient_temple",      # pre-civilisation religious site
    "dragon_lair",         # cave complex, high-CR area
    "necropolis",          # undead crypt complex
    "abandoned_mine",      # depleted mine with tunnels
    "fallen_city",         # once-great city, now overgrown
    "watchtower",          # border watchtower, partially intact
    "bandit_hideout",      # occupied ruin used by bandits
    "hermit_cave",         # recluse wizard/monk lives here
    "collapsed_bridge",    # broken infrastructure
]

# Map settlement kind -> ruin type when a settlement is destroyed
_KIND_TO_RUIN = {
    "city":    "fallen_city",
    "castle":  "abandoned_castle",
    "town":    "fallen_city",
    "village": "bandit_hideout",
    "hamlet":  "bandit_hideout",
    "camp":    "bandit_hideout",
}

# Ruin name fragments for ancient pre-history structures
ANCIENT_RUIN_NAME_PARTS = {
    "ancient_temple":  (["Temple", "Shrine", "Sanctum", "Cathedral"],
                        ["of the Sun", "of the Moon", "of Forgotten Gods",
                         "of the Old Ones", "of Eternal Dawn"]),
    "dragon_lair":     (["The Dragon's", "Wyrm's", "Serpent's"],
                        ["Nest", "Lair", "Aerie", "Den", "Roost"]),
    "old_dungeon":     (["The", "Dark", "Deep"],
                        ["Oubliette", "Dungeon", "Vault", "Catacombs"]),
    "hermit_cave":     (["The Hermit's", "The Sage's", "The Recluse's"],
                        ["Cave", "Grotto", "Hollow", "Refuge"]),
    "collapsed_bridge": (["The Old", "The Broken", "The Shattered"],
                         ["Bridge", "Crossing", "Span", "Viaduct"]),
    "ancient_ruins":   (["The Lost", "The Forgotten", "The Sunken"],
                        ["City", "Citadel", "Fortress", "Halls"]),
    "watchtower":      (["The Old", "The Crumbling", "The Lone"],
                        ["Watchtower", "Beacon", "Spire", "Tower"]),
    "ruined_tower":    (["The Shattered", "The Fallen", "The Dark"],
                        ["Tower", "Spire", "Pillar", "Obelisk"]),
    "necropolis":      (["The", "The Ancient", "The Accursed"],
                        ["Necropolis", "Crypt", "Tomb", "Burial Grounds"]),
}

# Historical figure name pools by race
HISTORICAL_FIGURE_NAMES = {
    "Human": [
        "Aldric", "Seraphina", "Edwyn", "Margaux", "Castellan",
        "Theodric", "Elara", "Marcus", "Helena", "Reynard",
        "Guinevere", "Oswald", "Beatrix", "Cedric", "Rowena",
    ],
    "Elf": [
        "Galadwen", "Thalion", "Arannis", "Celeborn", "Ithilwen",
        "Lorendel", "Faelwen", "Earendil", "Nimloth", "Cirdan",
    ],
    "Dwarf": [
        "Borik", "Brunhild", "Durin", "Gretta", "Korrin",
        "Hilda", "Thorin", "Dagna", "Balin", "Moria",
    ],
    "Orc": [
        "Grommash", "Urzog", "Kargath", "Nazgrim", "Drakthar",
        "Azuka", "Thrall", "Garruk", "Morgash", "Zuluhed",
    ],
    "Goblin": [
        "Nixle", "Skrit", "Grizznak", "Plit", "Yikkit",
        "Ratclaw", "Snivels", "Grub", "Filch", "Squit",
    ],
    "Undead": [
        "Veranthos", "Malachar", "Nethara", "Sarthorel", "Drevius",
        "Ashenveil", "Morgathos", "Kael'thar", "Xalvador", "Zynara",
    ],
}

# Creature territory data — maps biome/terrain to notable creatures
# that form territorial regions in the world
TERRITORY_CREATURES = {
    "mountain": [
        ("griffin", "rare", "A griffin eyrie crowns the peaks"),
        ("wyvern", "rare", "Wyverns circle the high crags"),
        ("young_dragon", "very_rare", "A dragon lairs in the deepest cavern"),
        ("goat", "common", "Mountain goats scramble across the cliffs"),
        ("eagle", "uncommon", "Eagles nest on the ledges"),
    ],
    "forest": [
        ("wolf", "common", "Wolf packs roam the dark woods"),
        ("bear", "uncommon", "Bears forage among the trees"),
        ("dire_wolf", "rare", "Dire wolves prowl the ancient forest"),
        ("giant_spider", "uncommon", "Giant spiders web the canopy"),
        ("unicorn", "very_rare", "A unicorn has been sighted in the deepest glade"),
    ],
    "swamp": [
        ("crocodile", "uncommon", "Crocodiles lurk in the murky waters"),
        ("basilisk", "rare", "A basilisk haunts the poisoned marsh"),
        ("troll", "rare", "Trolls dwell beneath the rotting bridges"),
        ("snake", "common", "Venomous snakes infest the reeds"),
    ],
    "plains": [
        ("horse", "common", "Wild horses gallop across the grasslands"),
        ("centaur", "rare", "Centaur tribes patrol the open plains"),
        ("manticore", "very_rare", "A manticore terrorises the region"),
        ("boar", "common", "Wild boar root through the scrubland"),
    ],
    "desert": [
        ("giant_scorpion", "uncommon", "Giant scorpions burrow in the sand"),
        ("basilisk", "rare", "A basilisk lurks among the dunes"),
        ("gnoll", "uncommon", "Gnoll packs raid from the wastes"),
    ],
    "snow": [
        ("wolf", "common", "White wolves hunt across the tundra"),
        ("bear", "uncommon", "Great frost bears wander the snowfields"),
        ("wyvern", "rare", "Ice wyverns roost on frozen peaks"),
    ],
}


def _get_affinity(race_a: str, race_b: str) -> int:
    if race_a == race_b:
        return 40
    key = (race_a, race_b) if (race_a, race_b) in RACE_AFFINITY else (race_b, race_a)
    return RACE_AFFINITY.get(key, 0)


# ================================================================
# DATA CLASSES — internal simulation state
# ================================================================

class HistoricalSettlement:
    """A settlement that exists (or once existed) during the simulation."""

    __slots__ = ("name", "x", "y", "kind", "population", "founded_year",
                 "destroyed_year", "walls", "specialization", "tribe_name",
                 "race", "garrison", "ruin_type")

    def __init__(self, name: str, x: int, y: int, kind: str,
                 founded_year: int, tribe_name: str = "", race: str = ""):
        self.name = name
        self.x = x
        self.y = y
        self.kind = kind
        self.population = 10
        self.founded_year = founded_year
        self.destroyed_year: Optional[int] = None
        self.walls = False
        self.specialization = "general"
        self.tribe_name = tribe_name
        self.race = race
        self.garrison = 0
        self.ruin_type = ""  # set when destroyed or for pre-placed ruins

    @property
    def alive(self) -> bool:
        return self.destroyed_year is None

    def upgrade_kind(self):
        """Promote settlement kind based on population."""
        if self.population >= POP_CITY:
            self.kind = "city"
        elif self.population >= POP_TOWN:
            self.kind = "town"
        elif self.population >= POP_VILLAGE:
            self.kind = "village"
        elif self.population >= POP_HAMLET:
            self.kind = "hamlet"
        else:
            self.kind = "camp"


class Tribe:
    """A tribe participating in the history simulation."""

    __slots__ = ("name", "race", "x", "y", "population", "settlements",
                 "territory", "gold", "military", "tech_level", "traits",
                 "relations", "alive", "kingdom_name", "explored",
                 "_name_idx")

    def __init__(self, name: str, race: str, entry_point: Tuple[int, int],
                 population: int, traits: Set[str]):
        self.name = name
        self.race = race
        self.x = entry_point[0]
        self.y = entry_point[1]
        self.population = population
        self.settlements: List[HistoricalSettlement] = []
        self.territory: Set[Tuple[int, int]] = set()
        self.gold = 100
        self.military = population // 5
        self.tech_level = 0
        self.traits = traits
        self.relations: Dict[str, int] = {}  # other_tribe_name -> trust
        self.alive = True
        self.kingdom_name = ""
        self.explored: Set[Tuple[int, int]] = set()
        self._name_idx = 0

    @property
    def living_settlements(self) -> List[HistoricalSettlement]:
        return [s for s in self.settlements if s.alive]

    @property
    def total_pop(self) -> int:
        return sum(s.population for s in self.living_settlements)

    @property
    def center(self) -> Tuple[int, int]:
        """Weighted center of living settlements."""
        ls = self.living_settlements
        if not ls:
            return (self.x, self.y)
        tx = sum(s.x * s.population for s in ls)
        ty = sum(s.y * s.population for s in ls)
        tp = sum(s.population for s in ls)
        if tp == 0:
            return (self.x, self.y)
        return (tx // tp, ty // tp)


# ================================================================
# OUTPUT DATA CLASSES
# ================================================================

@dataclass
class RuinPlan:
    """A destroyed settlement that should appear as ruins in the world."""
    name: str
    x: int
    y: int
    original_kind: str
    destroyed_year: int
    destroyed_by: str  # tribe name that destroyed it
    race: str
    ruin_type: str = "ruins"  # specific ruin flavour (abandoned_castle, dragon_lair, etc.)

@dataclass
class HistoryResult:
    """Complete output of the history simulation."""
    settlements: list = field(default_factory=list)   # SettlementPlan objects
    ruins: list = field(default_factory=list)          # RuinPlan objects
    roads: list = field(default_factory=list)           # RoadPlan objects
    kingdoms: list = field(default_factory=list)        # kingdom dicts
    diplomatic_relations: dict = field(default_factory=dict)
    historical_events: list = field(default_factory=list)  # list of strings
    trade_routes: list = field(default_factory=list)
    creature_territories: list = field(default_factory=list)  # creature region dicts
    historical_figures: list = field(default_factory=list)  # notable NPCs from history


# ================================================================
# THE SIMULATION
# ================================================================

class HistorySimulation:
    """Simulates centuries of tribal history to determine settlement placement.

    Uses the coarse elevation cache from WorldPlan (typically 1000x1000 for
    a 10,000x10,000 world) for all terrain queries.  No pathfinding, no
    tile modifications — just placement decisions and abstract combat.
    """

    def __init__(self, width: int, height: int, seed: int,
                 elev_cache: np.ndarray, elev_step: int,
                 moisture_scale: float = 0.018,
                 elevation_scale: float = 0.012,
                 edge_falloff_strength: float = 0.55):
        self.width = width
        self.height = height
        self.seed = seed
        self.elev_cache = elev_cache          # [ch, cw] numpy array
        self.elev_step = elev_step
        self.elev_ch, self.elev_cw = elev_cache.shape
        self.moisture_scale = moisture_scale
        self.elevation_scale = elevation_scale
        self.edge_falloff_strength = edge_falloff_strength

        self.tribes: List[Tribe] = []
        self.all_settlements: List[HistoricalSettlement] = []
        self.events: List[str] = []
        self.used_names: Set[str] = set()
        self.trade_links: Set[Tuple[str, str]] = set()  # (tribe_a, tribe_b)

        # Pre-compute moisture cache (same resolution as elevation)
        self._build_moisture_cache()

    # ------------------------------------------------------------------
    # Terrain helpers
    # ------------------------------------------------------------------

    def _build_moisture_cache(self):
        """Build a coarse moisture grid matching the elevation cache."""
        from game.world.chunk_generator import _fbm_vec

        xs = np.arange(self.elev_cw, dtype=np.float32) * self.elev_step
        ys = np.arange(self.elev_ch, dtype=np.float32) * self.elev_step
        xx, yy = np.meshgrid(xs, ys)

        self.moisture_cache = _fbm_vec(
            xx * self.moisture_scale,
            yy * self.moisture_scale,
            octaves=4, seed=self.seed + 7919)

    def _elev_at(self, x: int, y: int) -> float:
        """Fast elevation lookup from cache."""
        ci = min(max(0, x // self.elev_step), self.elev_cw - 1)
        cj = min(max(0, y // self.elev_step), self.elev_ch - 1)
        return float(self.elev_cache[cj, ci])

    def _moisture_at(self, x: int, y: int) -> float:
        """Fast moisture lookup from cache."""
        ci = min(max(0, x // self.elev_step), self.elev_cw - 1)
        cj = min(max(0, y // self.elev_step), self.elev_ch - 1)
        return float(self.moisture_cache[cj, ci])

    def _is_land(self, x: int, y: int) -> bool:
        return WATER_THRESHOLD < self._elev_at(x, y) < MOUNTAIN_THRESHOLD

    def _has_water_nearby(self, x: int, y: int, radius: int = 80) -> bool:
        step = self.elev_step
        for dy in range(-radius, radius + 1, step):
            for dx in range(-radius, radius + 1, step):
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self._elev_at(nx, ny) < WATER_THRESHOLD:
                        return True
        return False

    def _has_farmland_nearby(self, x: int, y: int, radius: int = 60) -> bool:
        step = self.elev_step
        fertile = 0
        for dy in range(-radius, radius + 1, step):
            for dx in range(-radius, radius + 1, step):
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    e = self._elev_at(nx, ny)
                    m = self._moisture_at(nx, ny)
                    if 0.30 <= e <= 0.50 and m > 0.35:
                        fertile += 1
        return fertile >= 3

    def _has_ore_nearby(self, x: int, y: int, radius: int = 80) -> bool:
        step = self.elev_step
        for dy in range(-radius, radius + 1, step):
            for dx in range(-radius, radius + 1, step):
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if self._elev_at(nx, ny) >= 0.55:
                        return True
        return False

    def _has_forest_nearby(self, x: int, y: int, radius: int = 60) -> bool:
        step = self.elev_step
        for dy in range(-radius, radius + 1, step):
            for dx in range(-radius, radius + 1, step):
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    e = self._elev_at(nx, ny)
                    m = self._moisture_at(nx, ny)
                    if 0.30 <= e <= 0.60 and m > 0.50:
                        return True
        return False

    def _has_high_ground(self, x: int, y: int) -> bool:
        e = self._elev_at(x, y)
        return 0.45 <= e <= 0.60

    def _has_natural_barriers(self, x: int, y: int) -> bool:
        """Check if location is flanked by water or mountains."""
        barriers = 0
        step = self.elev_step * 3
        for dx, dy in [(step, 0), (-step, 0), (0, step), (0, -step)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                e = self._elev_at(nx, ny)
                if e < WATER_THRESHOLD or e >= MOUNTAIN_THRESHOLD:
                    barriers += 1
        return barriers >= 2

    def _score_location(self, x: int, y: int, tribe: Tribe,
                        rng: random.Random) -> float:
        """Score a potential settlement site for a tribe."""
        if not self._is_land(x, y):
            return -1000

        score = 0.0

        # Water access (critical)
        if self._has_water_nearby(x, y):
            score += 50

        # Fertile land
        if self._has_farmland_nearby(x, y):
            score += 30

        # Resources
        if self._has_ore_nearby(x, y):
            score += 20
            if "industrious" in tribe.traits:
                score += 15

        if self._has_forest_nearby(x, y):
            score += 15
            if "nature" in tribe.traits:
                score += 10

        # Defensibility
        if self._has_high_ground(x, y):
            score += 10
            if "defensive" in tribe.traits:
                score += 10

        if self._has_natural_barriers(x, y):
            score += 10

        # Distance from hostile tribes
        for other in self.tribes:
            if other.name == tribe.name or not other.alive:
                continue
            for s in other.living_settlements:
                d = math.sqrt((s.x - x) ** 2 + (s.y - y) ** 2)
                trust = tribe.relations.get(other.name, 0)
                if trust < -20:
                    if d < 300:
                        score -= (300 - d) * 0.05
                elif trust > 20:
                    # Near friendly = trade potential
                    if d < 500:
                        score += 15

        # Don't stack on top of own settlements
        for s in tribe.living_settlements:
            d = math.sqrt((s.x - x) ** 2 + (s.y - y) ** 2)
            if d < 120:
                score -= 100  # too close

        # Don't overlap other tribes' settlements
        for s in self.all_settlements:
            if s.alive and s.tribe_name != tribe.name:
                d = math.sqrt((s.x - x) ** 2 + (s.y - y) ** 2)
                if d < 80:
                    score -= 200

        # Racial preferences
        elev = self._elev_at(x, y)
        moist = self._moisture_at(x, y)
        if tribe.race == "Elf" and moist > 0.50 and 0.30 <= elev <= 0.55:
            score += 25  # elves prefer forests
        elif tribe.race == "Dwarf" and elev >= 0.50:
            score += 25  # dwarves prefer highlands
        elif tribe.race == "Orc" and elev >= 0.35 and moist < 0.40:
            score += 15  # orcs prefer dry badlands
        elif tribe.race == "Goblin":
            score += 5  # goblins aren't picky
        elif tribe.race == "Undead" and moist < 0.35:
            score += 15  # undead prefer barren areas

        # Trade potential
        score += self._score_trade_potential(x, y) * 0.5

        # Strategic military value
        score += self._score_strategic_value(x, y) * 0.3

        # Randomness for variety
        score += rng.uniform(-10, 10)

        return score

    # ------------------------------------------------------------------
    # Trade and strategic scoring
    # ------------------------------------------------------------------

    def _score_trade_potential(self, x: int, y: int) -> float:
        """Score a location for trade route viability."""
        score = 0.0

        # River crossings are natural trade hubs
        # Check if a river (water tile strip) runs nearby
        water_dirs = 0
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            if self._elev_at(x + dx * 50, y + dy * 50) < WATER_THRESHOLD:
                water_dirs += 1
        if water_dirs >= 2:  # water on two sides = river crossing/confluence
            score += 30

        # Centrality — distance to center of the map (trade routes converge)
        cx, cy = self.width // 2, self.height // 2
        dist_to_center = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        max_dist = math.sqrt(cx ** 2 + cy ** 2)
        centrality = 1.0 - (dist_to_center / max_dist)
        score += centrality * 20

        # Between two existing friendly settlements = trade corridor
        for s1 in self.all_settlements:
            if not s1.alive:
                continue
            for s2 in self.all_settlements:
                if s1 is s2 or not s2.alive:
                    continue
                # Check if (x, y) is roughly between s1 and s2
                d1 = math.sqrt((x - s1.x) ** 2 + (y - s1.y) ** 2)
                d2 = math.sqrt((x - s2.x) ** 2 + (y - s2.y) ** 2)
                d12 = math.sqrt((s1.x - s2.x) ** 2 + (s1.y - s2.y) ** 2)
                if d12 > 200 and d1 + d2 < d12 * 1.3:  # roughly on the path
                    score += 10
                    break

        return score

    def _score_strategic_value(self, x: int, y: int) -> float:
        """Score a location for military/strategic value."""
        score = 0.0

        # Mountain pass — land between mountains
        mountains_nearby = 0
        land_nearby = 0
        for dx in range(-100, 101, self.elev_step):
            for dy in range(-100, 101, self.elev_step):
                e = self._elev_at(x + dx, y + dy)
                if e >= MOUNTAIN_THRESHOLD:
                    mountains_nearby += 1
                elif WATER_THRESHOLD < e < MOUNTAIN_THRESHOLD:
                    land_nearby += 1

        # Narrow land = strategic (few land tiles surrounded by mountains/water)
        if mountains_nearby > 5 and land_nearby < 10:
            score += 40  # mountain pass!

        # River ford — land on both sides of a river
        # (water to north/south, land to east/west or vice versa)
        water_ns = (self._elev_at(x, y - 80) < WATER_THRESHOLD or
                    self._elev_at(x, y + 80) < WATER_THRESHOLD)
        land_ew = (self._is_land(x - 80, y) and self._is_land(x + 80, y))
        if water_ns and land_ew:
            score += 30  # river ford

        water_ew = (self._elev_at(x - 80, y) < WATER_THRESHOLD or
                    self._elev_at(x + 80, y) < WATER_THRESHOLD)
        land_ns = (self._is_land(x, y - 80) and self._is_land(x, y + 80))
        if water_ew and land_ns:
            score += 30  # river ford (perpendicular)

        return score

    def _determine_specialization(self, x: int, y: int) -> str:
        """Determine what a settlement at (x,y) would specialize in."""
        elev = self._elev_at(x, y)
        moist = self._moisture_at(x, y)

        if self._has_water_nearby(x, y, radius=40):
            if elev < 0.30:
                return "fishing"
            return "port"
        if elev >= 0.55:
            return "mining"
        if moist > 0.55 and elev < 0.55:
            return "lumber"
        if moist > 0.35 and 0.30 <= elev <= 0.50:
            return "agricultural"
        if moist < 0.30:
            return "oasis"
        return "general"

    # ------------------------------------------------------------------
    # Name generation
    # ------------------------------------------------------------------

    def _pick_name(self, race: str, rng: random.Random) -> str:
        pool = RACE_NAME_POOLS.get(race, HUMAN_SETTLEMENT_NAMES)
        for _ in range(50):
            name = rng.choice(pool)
            if name not in self.used_names:
                self.used_names.add(name)
                return name
        # Fallback: suffix
        base = rng.choice(pool)
        suffix = rng.choice(["East", "West", "North", "South", "New",
                              "Old", "Upper", "Lower", "Greater", "Lesser"])
        name = f"{base} {suffix}"
        self.used_names.add(name)
        return name

    # ------------------------------------------------------------------
    # Tribe initialization
    # ------------------------------------------------------------------

    def _create_tribes(self, rng: random.Random):
        """Create initial tribes entering from map edges."""
        margin = int(self.width * 0.05)
        cx, cy = self.width // 2, self.height // 2

        tribe_num = 0
        for race, anchor, count, pop_range, trait_sets in TRIBE_TEMPLATES:
            for i in range(count):
                traits = trait_sets[i % len(trait_sets)]
                pop = rng.randint(*pop_range)

                # Determine entry point based on anchor side
                if anchor == "south":
                    ex = cx + rng.randint(-self.width // 4, self.width // 4)
                    ey = self.height - margin - rng.randint(0, self.height // 6)
                elif anchor == "northwest":
                    ex = margin + rng.randint(0, self.width // 4)
                    ey = margin + rng.randint(0, self.height // 4)
                elif anchor == "northeast":
                    ex = self.width - margin - rng.randint(0, self.width // 4)
                    ey = margin + rng.randint(0, self.height // 4)
                elif anchor == "east":
                    ex = self.width - margin - rng.randint(0, self.width // 6)
                    ey = cy + rng.randint(-self.height // 4, self.height // 4)
                elif anchor == "scattered":
                    # Random position on land
                    for _ in range(200):
                        ex = rng.randint(margin, self.width - margin)
                        ey = rng.randint(margin, self.height - margin)
                        if self._is_land(ex, ey):
                            break
                elif anchor == "wilderness":
                    # Deep wilderness — far from center
                    for _ in range(200):
                        angle = rng.uniform(0, 2 * math.pi)
                        dist = rng.uniform(self.width * 0.3, self.width * 0.45)
                        ex = int(cx + math.cos(angle) * dist)
                        ey = int(cy + math.sin(angle) * dist)
                        ex = max(margin, min(self.width - margin, ex))
                        ey = max(margin, min(self.height - margin, ey))
                        if self._is_land(ex, ey):
                            break
                else:
                    ex = rng.randint(margin, self.width - margin)
                    ey = rng.randint(margin, self.height - margin)

                # Clamp to land
                ex = max(margin, min(self.width - margin, ex))
                ey = max(margin, min(self.height - margin, ey))

                tribe_num += 1
                name = f"{race} Tribe {tribe_num}" if count > 1 else f"The {race}s"
                if race == "Undead":
                    name = "The Risen"

                tribe = Tribe(name, race, (ex, ey), pop, traits)
                self.tribes.append(tribe)

        # Initialize relations
        for t in self.tribes:
            for other in self.tribes:
                if t.name != other.name:
                    base = _get_affinity(t.race, other.race)
                    t.relations[other.name] = base + rng.randint(-10, 10)

    # ------------------------------------------------------------------
    # Year simulation phases
    # ------------------------------------------------------------------

    def _explore(self, tribe: Tribe, rng: random.Random):
        """Tribe scouts explore nearby terrain."""
        cx, cy = tribe.center
        radius = 200 + tribe.tech_level * 30
        step = self.elev_step * 4  # coarse exploration
        for _ in range(3 + tribe.tech_level):
            dx = rng.randint(-radius, radius)
            dy = rng.randint(-radius, radius)
            ex, ey = cx + dx, cy + dy
            if 0 <= ex < self.width and 0 <= ey < self.height:
                tribe.explored.add((ex // (step), ey // (step)))

    def _try_settle(self, tribe: Tribe, year: int, rng: random.Random):
        """Try to found a new settlement in the best location found."""
        cx, cy = tribe.center

        # Don't settle too frequently
        ls = tribe.living_settlements
        if ls and year - ls[-1].founded_year < 15:
            return

        # Require enough surplus population
        total_pop = tribe.total_pop
        if total_pop < 40 and len(ls) > 0:
            return

        # Search for good locations
        best_score = -9999
        best_xy = None
        scan_radius = 300 + tribe.tech_level * 50
        step = self.elev_step * 3

        for _ in range(30):  # sample 30 random candidates
            dx = rng.randint(-scan_radius, scan_radius)
            dy = rng.randint(-scan_radius, scan_radius)
            sx = cx + dx
            sy = cy + dy
            # Snap to grid for consistency
            sx = (sx // step) * step
            sy = (sy // step) * step
            if not (50 < sx < self.width - 50 and 50 < sy < self.height - 50):
                continue
            score = self._score_location(sx, sy, tribe, rng)
            if score > best_score:
                best_score = score
                best_xy = (sx, sy)

        if best_xy is None or best_score < 0:
            return

        sx, sy = best_xy
        name = self._pick_name(tribe.race, rng)
        settlement = HistoricalSettlement(
            name=name, x=sx, y=sy, kind="camp",
            founded_year=year, tribe_name=tribe.name, race=tribe.race,
        )

        # Seed population from tribe surplus
        seed_pop = max(10, tribe.total_pop // 6)
        settlement.population = seed_pop
        settlement.specialization = self._determine_specialization(sx, sy)

        tribe.settlements.append(settlement)
        self.all_settlements.append(settlement)

        # Claim territory around the settlement
        claim_radius = 100 // self.elev_step
        ci, cj = sx // self.elev_step, sy // self.elev_step
        for di in range(-claim_radius, claim_radius + 1):
            for dj in range(-claim_radius, claim_radius + 1):
                if di * di + dj * dj <= claim_radius * claim_radius:
                    tribe.territory.add((ci + di, cj + dj))

        self.events.append(
            f"In year {year}, {tribe.name} founded {name}.")

    def _grow_settlements(self, tribe: Tribe, year: int, rng: random.Random):
        """Grow settlement populations based on resources."""
        for s in tribe.living_settlements:
            # Base growth rate — slow enough that many settlements stay small
            growth_rate = 0.015
            if s.specialization == "agricultural":
                growth_rate = 0.025
            elif s.specialization in ("fishing", "port"):
                growth_rate = 0.02
            elif s.specialization == "mining":
                growth_rate = 0.012

            if "agrarian" in tribe.traits:
                growth_rate += 0.01
            if "mercantile" in tribe.traits:
                growth_rate += 0.005

            # Diminishing returns at high population
            # Cap varies by settlement location quality and age
            base_cap = 200
            if s.specialization in ("agricultural", "port", "crossroads", "capital"):
                base_cap = 800
            elif s.specialization in ("mining", "lumber", "fishing"):
                base_cap = 400
            else:
                base_cap = 300
            # Older settlements had more time to develop infrastructure
            age_bonus = min(200, (year - s.founded_year) // 5)
            cap = base_cap + age_bonus
            growth_factor = max(0.1, 1.0 - s.population / cap)
            growth = int(s.population * growth_rate * growth_factor)
            growth = max(1, growth + rng.randint(-1, 2))
            s.population = min(cap, s.population + growth)

            # Upgrade kind based on population
            old_kind = s.kind
            s.upgrade_kind()
            if s.kind != old_kind and s.kind in ("town", "city"):
                self.events.append(
                    f"In year {year}, {s.name} grew into a {s.kind}.")

            # Military garrison
            s.garrison = max(s.garrison, s.population // 8)

            # Fortification
            if s.population >= POP_TOWN and not s.walls:
                if "defensive" in tribe.traits or rng.random() < 0.3:
                    s.walls = True
                    self.events.append(
                        f"In year {year}, {s.name} built defensive walls.")

        # Update tribe-level military from settlements
        tribe.military = sum(s.garrison for s in tribe.living_settlements)
        # Income: taxes from settlements
        income = sum(s.population // 10 for s in tribe.living_settlements)
        if "mercantile" in tribe.traits:
            income += len(tribe.living_settlements) * 5
        tribe.gold += income

        # Expenses: military upkeep, infrastructure, administration
        military_cost = tribe.military * 2
        admin_cost = len(tribe.living_settlements) * 3
        infra_cost = sum(5 for s in tribe.living_settlements if s.walls)
        total_cost = military_cost + admin_cost + infra_cost
        tribe.gold = max(0, tribe.gold - total_cost)

    def _handle_diplomacy(self, tribe: Tribe, year: int, rng: random.Random):
        """Handle diplomatic interactions between tribes."""
        for other in self.tribes:
            if other.name == tribe.name or not other.alive:
                continue

            trust = tribe.relations.get(other.name, 0)

            # Check territory overlap
            overlap = len(tribe.territory & other.territory)
            if overlap > 0:
                # Territory friction
                friction = min(overlap, 20)
                tribe.relations[other.name] = trust - friction // 2
                other.relations[tribe.name] = other.relations.get(
                    tribe.name, 0) - friction // 2
            else:
                # Slow drift toward racial baseline
                baseline = _get_affinity(tribe.race, other.race)
                drift = 1 if trust < baseline else (-1 if trust > baseline else 0)
                tribe.relations[other.name] = trust + drift

            # Trade opportunity: nearby friendly settlements
            if trust > 10:
                for s1 in tribe.living_settlements:
                    for s2 in other.living_settlements:
                        d = math.sqrt((s1.x - s2.x) ** 2 + (s1.y - s2.y) ** 2)
                        if d < 600:
                            link = tuple(sorted([tribe.name, other.name]))
                            if link not in self.trade_links:
                                self.trade_links.add(link)
                                tribe.relations[other.name] = min(
                                    100, trust + 5)
                                other.relations[tribe.name] = min(
                                    100, other.relations.get(
                                        tribe.name, 0) + 5)
                                tribe.gold += 10
                                other.gold += 10
                                if year % 50 == 0:
                                    self.events.append(
                                        f"In year {year}, {tribe.name} and "
                                        f"{other.name} established trade.")
                            break
                    else:
                        continue
                    break

    def _handle_warfare(self, tribe: Tribe, year: int, rng: random.Random):
        """Handle military conflicts."""
        if "isolationist" in tribe.traits and rng.random() < 0.7:
            return

        for other in self.tribes:
            if other.name == tribe.name or not other.alive:
                continue

            trust = tribe.relations.get(other.name, 0)

            # War conditions
            aggression_threshold = -30
            if "aggressive" in tribe.traits:
                aggression_threshold = -10

            if trust > aggression_threshold:
                continue

            # Find a target settlement
            target = None
            min_dist = float("inf")
            for s in other.living_settlements:
                for own in tribe.living_settlements:
                    d = math.sqrt((s.x - own.x) ** 2 + (s.y - own.y) ** 2)
                    if d < min_dist:
                        min_dist = d
                        target = s

            if target is None or min_dist > 800:
                continue

            # Only attack nearby settlements
            attack_strength = tribe.military
            defense_strength = target.garrison
            if target.walls:
                defense_strength = int(defense_strength * 1.8)
            if self._has_high_ground(target.x, target.y):
                defense_strength = int(defense_strength * 1.3)

            # Probabilistic outcome using Lanchester-style comparison
            ratio = attack_strength / max(1, defense_strength)
            win_chance = min(0.9, max(0.1, ratio / (1 + ratio)))

            if rng.random() < win_chance and attack_strength > defense_strength * 0.6:
                # Victory: destroy the settlement
                target.destroyed_year = year
                # Assign ruin type based on what the settlement was
                target.ruin_type = _KIND_TO_RUIN.get(target.kind,
                                                     "bandit_hideout")
                # Mining towns become abandoned mines
                if target.specialization == "mining":
                    target.ruin_type = "abandoned_mine"
                other_name = other.name

                self.events.append(
                    f"In year {year}, {tribe.name} attacked and destroyed "
                    f"{target.name} (held by {other_name}).")

                # Casualties
                tribe.military = max(
                    tribe.military // 2,
                    tribe.military - defense_strength // 2)
                other.military = max(0, other.military - target.garrison)

                # Loot
                tribe.gold += max(0, target.population // 5)

                # Worsen relations
                tribe.relations[other.name] = max(-100, trust - 30)
                other.relations[tribe.name] = max(
                    -100, other.relations.get(tribe.name, 0) - 40)

                # Check if other tribe is eliminated
                if not other.living_settlements:
                    other.alive = False
                    self.events.append(
                        f"In year {year}, {other.name} was destroyed by "
                        f"{tribe.name}.")

                # Only one attack per year
                return

    def _advance_technology(self, tribe: Tribe, year: int,
                            rng: random.Random):
        """Advance tribe technology level over time."""
        # Tech advances slowly, boosted by population and gold
        pop = tribe.total_pop
        if pop > 200 and tribe.gold > 50 and rng.random() < 0.15:
            tribe.tech_level = min(10, tribe.tech_level + 1)
            if tribe.tech_level in (3, 6, 9):
                self.events.append(
                    f"In year {year}, {tribe.name} advanced their technology.")

    def _check_resource_depletion(self, settlement: HistoricalSettlement,
                                   year: int, rng: random.Random):
        """Check if a settlement's key resource is exhausted."""
        if settlement.specialization == "mining":
            # Ore depletes over time — mining town lifespan ~200 years
            age = year - settlement.founded_year
            if age > 150 and rng.random() < 0.05:
                settlement.specialization = "general"
                settlement.population = max(POP_HAMLET,
                                            settlement.population // 2)
                settlement.ruin_type = "abandoned_mine"
                self.events.append(
                    f"In year {year}, {settlement.name}'s mines ran dry.")
        elif settlement.specialization == "lumber":
            # Forests can be replanted, slower decline
            age = year - settlement.founded_year
            if age > 250 and rng.random() < 0.03:
                settlement.specialization = "agricultural"
                self.events.append(
                    f"In year {year}, the forests around {settlement.name} "
                    f"were depleted.")

    def _form_kingdoms(self, year: int, rng: random.Random):
        """Tribes with enough population and settlements become kingdoms."""
        for tribe in self.tribes:
            if not tribe.alive or tribe.kingdom_name:
                continue
            ls = tribe.living_settlements
            if tribe.total_pop < POP_TOWN or len(ls) < 3:
                continue

            # Form kingdom
            governance = RACE_GOVERNANCE.get(tribe.race, "feudalism")
            kingdom_names = {
                "Human": ["Kingdom of {cap}", "Realm of {cap}",
                           "The {cap} Dominion"],
                "Elf": ["Elven Dominion of {cap}", "The {cap} Conclave",
                          "Sylvan Realm of {cap}"],
                "Dwarf": ["Dwarven Holds of {cap}", "The {cap} Clanholds",
                            "{cap} Undermountain"],
                "Orc": ["Orcish Warband of {cap}", "The {cap} Horde",
                          "{cap} Warclan"],
                "Goblin": ["Goblin Warrens of {cap}", "The {cap} Swarm",
                             "{cap} Tunnelkin"],
                "Undead": ["The Undead Realm of {cap}", "Domain of {cap}",
                             "{cap} Necropolis"],
            }

            # Pick capital (largest settlement)
            capital = max(ls, key=lambda s: s.population)
            templates = kingdom_names.get(tribe.race, ["{cap} Kingdom"])
            name = rng.choice(templates).format(cap=capital.name)
            tribe.kingdom_name = name

            self.events.append(
                f"In year {year}, {tribe.name} united under {name} "
                f"with {capital.name} as the capital.")

    def _late_developments(self, year: int, rng: random.Random):
        """Handle late-era developments: cities, decline, castles."""
        for tribe in self.tribes:
            if not tribe.alive:
                continue

            ls = tribe.living_settlements

            # Build castles at border settlements (strategic locations)
            if tribe.kingdom_name and tribe.tech_level >= 3:
                for s in ls:
                    if s.kind in ("town", "village") and s.walls:
                        # Check if near another tribe's territory
                        ci = s.x // self.elev_step
                        cj = s.y // self.elev_step
                        near_border = False
                        for other in self.tribes:
                            if other.name == tribe.name or not other.alive:
                                continue
                            for di in range(-5, 6):
                                for dj in range(-5, 6):
                                    if (ci + di, cj + dj) in other.territory:
                                        near_border = True
                                        break
                                if near_border:
                                    break
                            if near_border:
                                break

                        if near_border and s.kind != "castle":
                            self._try_build_strategic_castle(
                                tribe, s, year, rng)

            # Decline: disasters happen throughout history, more common with larger populations
            for victim in ls:
                disaster_chance = 0.03 if victim.population > POP_TOWN else 0.01
                if rng.random() < disaster_chance:
                    loss_frac = rng.uniform(0.2, 0.5)
                    loss = int(victim.population * loss_frac)
                    if loss > 5:
                        victim.population -= loss
                        victim.upgrade_kind()  # downgrade if population dropped
                        causes = [
                            "plague", "famine", "civil unrest",
                            "resource depletion", "corruption",
                            "drought", "flood", "fire",
                        ]
                        cause = rng.choice(causes)
                        self.events.append(
                            f"In year {year}, {victim.name} suffered {cause}, "
                            f"losing {loss} inhabitants.")

    # ------------------------------------------------------------------
    # Pre-history: ancient ruins
    # ------------------------------------------------------------------

    def _generate_ruin_name(self, ruin_type: str, rng: random.Random) -> str:
        """Generate an evocative name for a ruin based on its type."""
        parts = ANCIENT_RUIN_NAME_PARTS.get(ruin_type)
        if parts:
            prefix = rng.choice(parts[0])
            suffix = rng.choice(parts[1])
            return f"{prefix} {suffix}"
        # Fallback
        return f"Ancient {ruin_type.replace('_', ' ').title()}"

    def _place_ancient_ruins(self, rng: random.Random):
        """Place ruins from a civilisation that existed before the tribes."""
        num_ancient = self.width * self.height // 5_000_000 + 3

        for _ in range(num_ancient):
            for attempt in range(50):
                x = rng.randint(100, self.width - 100)
                y = rng.randint(100, self.height - 100)
                if not self._is_land(x, y):
                    continue

                ruin_type = rng.choice([
                    "ancient_temple", "dragon_lair", "old_dungeon",
                    "hermit_cave", "collapsed_bridge", "ancient_ruins",
                ])

                settlement = HistoricalSettlement(
                    name=self._generate_ruin_name(ruin_type, rng),
                    x=x, y=y, kind="ruins",
                    founded_year=-500,
                    tribe_name="",
                    race="",
                )
                settlement.destroyed_year = -100  # long-abandoned
                settlement.population = 0
                settlement.ruin_type = ruin_type
                self.all_settlements.append(settlement)

                self.events.append(
                    f"Ancient {ruin_type.replace('_', ' ')} discovered "
                    f"at ({x},{y}) — predates all known civilisations.")
                break

    def _place_standalone_structures(self, rng: random.Random):
        """Place standalone structures that aren't from destroyed settlements.

        Called after the main simulation to add wizard towers, dungeons,
        watchtowers, hermit caves, and dragon lairs.
        """
        margin = 100

        # Wizard towers — on high ground, isolated, built during golden ages
        num_towers = max(1, self.width * self.height // 8_000_000 + 1)
        for _ in range(num_towers):
            for attempt in range(60):
                x = rng.randint(margin, self.width - margin)
                y = rng.randint(margin, self.height - margin)
                e = self._elev_at(x, y)
                if not (0.45 <= e <= 0.62):
                    continue
                # Must be far from settlements (isolated)
                too_close = False
                for s in self.all_settlements:
                    if s.alive and math.sqrt((s.x - x) ** 2 +
                                             (s.y - y) ** 2) < 200:
                        too_close = True
                        break
                if too_close:
                    continue

                tower = HistoricalSettlement(
                    name=self._generate_ruin_name("ruined_tower", rng),
                    x=x, y=y, kind="ruins",
                    founded_year=rng.randint(50, 300),
                )
                tower.destroyed_year = rng.randint(350, 490)
                tower.population = 0
                tower.ruin_type = "ruined_tower"
                self.all_settlements.append(tower)
                self.events.append(
                    f"A wizard's tower once stood at ({x},{y}), now "
                    f"crumbling and abandoned.")
                break

        # Dungeons — in mountain/hill areas, built by dark powers
        num_dungeons = max(1, self.width * self.height // 10_000_000 + 1)
        for _ in range(num_dungeons):
            for attempt in range(60):
                x = rng.randint(margin, self.width - margin)
                y = rng.randint(margin, self.height - margin)
                e = self._elev_at(x, y)
                if not (0.50 <= e < MOUNTAIN_THRESHOLD):
                    continue
                dungeon = HistoricalSettlement(
                    name=self._generate_ruin_name("old_dungeon", rng),
                    x=x, y=y, kind="ruins",
                    founded_year=-300,
                )
                dungeon.destroyed_year = -50
                dungeon.population = 0
                dungeon.ruin_type = "old_dungeon"
                self.all_settlements.append(dungeon)
                self.events.append(
                    f"An ancient dungeon lies beneath the hills at ({x},{y}).")
                break

        # Watchtowers — along kingdom borders, some abandoned
        for tribe in self.tribes:
            if not tribe.alive or not tribe.kingdom_name:
                continue
            ls = tribe.living_settlements
            if len(ls) < 2:
                continue
            # Place 1-2 watchtowers near border settlements
            border_settlements = []
            for s in ls:
                ci = s.x // self.elev_step
                cj = s.y // self.elev_step
                for other in self.tribes:
                    if other.name == tribe.name or not other.alive:
                        continue
                    for di in range(-5, 6):
                        for dj in range(-5, 6):
                            if (ci + di, cj + dj) in other.territory:
                                border_settlements.append(s)
                                break
                        else:
                            continue
                        break
                    else:
                        continue
                    break
            if not border_settlements:
                continue
            num_wt = min(2, len(border_settlements))
            chosen = rng.sample(border_settlements, num_wt)
            for bs in chosen:
                # Place watchtower offset from the settlement
                angle = rng.uniform(0, 2 * math.pi)
                dist = rng.randint(60, 120)
                wx = int(bs.x + math.cos(angle) * dist)
                wy = int(bs.y + math.sin(angle) * dist)
                if not self._is_land(wx, wy):
                    continue
                wt = HistoricalSettlement(
                    name=self._generate_ruin_name("watchtower", rng),
                    x=wx, y=wy, kind="ruins",
                    founded_year=rng.randint(200, 400),
                )
                # Some watchtowers are still active (not ruined)
                if rng.random() < 0.4:
                    wt.destroyed_year = rng.randint(350, 490)
                    wt.ruin_type = "watchtower"
                else:
                    wt.destroyed_year = None
                    wt.ruin_type = "watchtower"
                    wt.kind = "camp"
                    wt.population = rng.randint(3, 8)
                    wt.tribe_name = tribe.name
                    wt.race = tribe.race
                wt.population = 0 if wt.destroyed_year else wt.population
                self.all_settlements.append(wt)

        # Hermit caves — deep wilderness, far from settlements
        num_hermits = max(1, self.width * self.height // 12_000_000 + 1)
        for _ in range(num_hermits):
            for attempt in range(80):
                x = rng.randint(margin, self.width - margin)
                y = rng.randint(margin, self.height - margin)
                if not self._is_land(x, y):
                    continue
                # Must be far from ALL settlements
                too_close = False
                for s in self.all_settlements:
                    if s.alive and math.sqrt((s.x - x) ** 2 +
                                             (s.y - y) ** 2) < 300:
                        too_close = True
                        break
                if too_close:
                    continue
                hermit = HistoricalSettlement(
                    name=self._generate_ruin_name("hermit_cave", rng),
                    x=x, y=y, kind="ruins",
                    founded_year=rng.randint(100, 400),
                )
                # Hermit caves are "alive" — someone lives there
                hermit.destroyed_year = None
                hermit.population = 1
                hermit.ruin_type = "hermit_cave"
                self.all_settlements.append(hermit)
                self.events.append(
                    f"A reclusive hermit dwells in a cave at ({x},{y}).")
                break

        # Dragon lairs — high mountains, very rare
        num_dragons = max(0, self.width * self.height // 20_000_000)
        if rng.random() < 0.5:
            num_dragons += 1  # at least occasionally one
        for _ in range(num_dragons):
            for attempt in range(100):
                x = rng.randint(margin, self.width - margin)
                y = rng.randint(margin, self.height - margin)
                e = self._elev_at(x, y)
                if e < 0.58:  # must be high mountain area
                    continue
                lair = HistoricalSettlement(
                    name=self._generate_ruin_name("dragon_lair", rng),
                    x=x, y=y, kind="ruins",
                    founded_year=-1000,
                )
                lair.destroyed_year = None  # dragon lairs are active!
                lair.population = 0
                lair.ruin_type = "dragon_lair"
                self.all_settlements.append(lair)
                self.events.append(
                    f"A dragon is rumoured to lair in the mountains "
                    f"at ({x},{y}).")
                break

    # ------------------------------------------------------------------
    # Historical figures
    # ------------------------------------------------------------------

    def _generate_historical_figures(self, tribe: Tribe, year: int,
                                     rng: random.Random):
        """Occasionally generate notable NPCs in history."""
        if rng.random() > 0.01:  # 1% chance per tribe per year
            return

        figure_types = [
            ("hero", "warrior", "the Champion of {tribe}"),
            ("wizard", "mage", "the Archmage of {tribe}"),
            ("villain", "tyrant", "the Scourge of the Realm"),
            ("explorer", "pathfinder", "the Trailblazer"),
            ("prophet", "seer", "the Oracle"),
        ]
        kind, role, title_tmpl = rng.choice(figure_types)
        title = title_tmpl.format(tribe=tribe.name)

        name_pool = HISTORICAL_FIGURE_NAMES.get(tribe.race,
                                                 HISTORICAL_FIGURE_NAMES["Human"])
        name = rng.choice(name_pool)

        self.events.append(
            f"In year {year}, {name} {title} emerged among "
            f"the {tribe.name}.")

        # Store the figure for the result
        figure = {
            "name": name,
            "title": title,
            "kind": kind,
            "role": role,
            "race": tribe.race,
            "tribe": tribe.name,
            "year": year,
        }

        if not hasattr(self, "_historical_figures"):
            self._historical_figures = []
        self._historical_figures.append(figure)

        # Historical figures affect the world
        if kind == "hero":
            tribe.military += 50
            self.events.append(
                f"In year {year}, {name}'s heroism rallied "
                f"{tribe.name}'s armies.")
        elif kind == "wizard":
            # Wizard builds a tower — find a high-ground location
            cx, cy = tribe.center
            for attempt in range(30):
                tx = cx + rng.randint(-300, 300)
                ty = cy + rng.randint(-300, 300)
                if self._has_high_ground(tx, ty):
                    tower = HistoricalSettlement(
                        name=f"{name}'s Tower",
                        x=tx, y=ty, kind="ruins",
                        founded_year=year,
                        tribe_name=tribe.name,
                        race=tribe.race,
                    )
                    tower.destroyed_year = None
                    tower.population = 1
                    tower.ruin_type = "ruined_tower"
                    self.all_settlements.append(tower)
                    self.events.append(
                        f"In year {year}, {name} raised a tower at "
                        f"({tx},{ty}).")
                    break
        elif kind == "villain":
            # Villain causes destruction to a random settlement
            targets = tribe.living_settlements
            if targets:
                victim = rng.choice(targets)
                loss = max(5, victim.population // 3)
                victim.population -= loss
                victim.upgrade_kind()
                self.events.append(
                    f"In year {year}, {name} the tyrant's reign of "
                    f"terror cost {victim.name} {loss} lives.")
        elif kind == "explorer":
            # Explorer expands explored territory significantly
            for _ in range(20):
                dx = rng.randint(-500, 500)
                dy = rng.randint(-500, 500)
                cx, cy = tribe.center
                step = self.elev_step * 4
                tribe.explored.add(((cx + dx) // step, (cy + dy) // step))

    # ------------------------------------------------------------------
    # Climate events and natural disasters
    # ------------------------------------------------------------------

    def _climate_events(self, year: int, rng: random.Random):
        """World-wide climate events."""
        # Ice age (rare, affects all tribes)
        if rng.random() < 0.002:  # ~1 per 500 years
            self.events.append(
                f"In year {year}, a great winter descended upon the land.")
            for tribe in self.tribes:
                for s in tribe.living_settlements:
                    s.population = int(s.population * 0.7)  # 30% die
                    s.upgrade_kind()

        # Volcanic eruption (very rare, devastating to one area)
        if rng.random() < 0.003:
            # Find a mountain
            mx = rng.randint(100, self.width - 100)
            my = rng.randint(100, self.height - 100)
            if self._elev_at(mx, my) >= MOUNTAIN_THRESHOLD:
                self.events.append(
                    f"In year {year}, a great volcano erupted "
                    f"at ({mx},{my})!")
                # Destroy nearby settlements
                for s in self.all_settlements:
                    if s.alive:
                        d = math.sqrt((s.x - mx) ** 2 + (s.y - my) ** 2)
                        if d < 150:
                            s.population = 0
                            s.destroyed_year = year
                            s.ruin_type = "fallen_city"
                            self.events.append(
                                f"In year {year}, {s.name} was "
                                f"buried by volcanic ash.")

        # Plague (uncommon, spreads between nearby settlements)
        if rng.random() < 0.005:
            # Pick a random living settlement as origin
            living = [s for s in self.all_settlements if s.alive and
                      s.population > POP_HAMLET]
            if living:
                origin = rng.choice(living)
                plague_name = rng.choice([
                    "the Grey Plague", "the Wasting Sickness",
                    "the Red Fever", "Bonechill", "the Sweating Death",
                ])
                self.events.append(
                    f"In year {year}, {plague_name} broke out in "
                    f"{origin.name}.")
                origin.population = int(origin.population * 0.6)
                origin.upgrade_kind()
                # Spread to nearby settlements
                for s in self.all_settlements:
                    if s.alive and s is not origin:
                        d = math.sqrt((s.x - origin.x) ** 2 +
                                      (s.y - origin.y) ** 2)
                        if d < 300 and rng.random() < 0.4:
                            s.population = int(s.population * 0.7)
                            s.upgrade_kind()

    # ------------------------------------------------------------------
    # Foreign trade
    # ------------------------------------------------------------------

    def _establish_foreign_trade(self, year: int, rng: random.Random):
        """Establish trade with foreign powers."""
        if year < 100:
            return  # too early for foreign contact

        # Find coastal settlements (potential ports)
        coastal = [s for s in self.all_settlements
                   if s.alive and self._has_water_nearby(s.x, s.y, 50)]

        if not coastal:
            return

        # Zarath Empire traders arrive from the east
        if year > 150 and rng.random() < 0.02:
            port = rng.choice(coastal)
            if port.specialization not in ("port", "capital"):
                port.specialization = "port"
            self.events.append(
                f"In year {year}, merchants from the Zarath Empire "
                f"established a trading post at {port.name}.")
            # The port grows faster due to trade
            port.population = int(port.population * 1.3)

        # Southern Isles sailors arrive
        if year > 200 and rng.random() < 0.015:
            port = rng.choice(coastal)
            self.events.append(
                f"In year {year}, explorers from the Southern Isles "
                f"made contact at {port.name}.")

        # Drifters from the western continent
        if year > 250 and rng.random() < 0.01:
            port = rng.choice(coastal)
            self.events.append(
                f"In year {year}, refugees from the Western Continent "
                f"arrived at {port.name}, bringing new knowledge.")
            # Small tech boost to the owning tribe
            for tribe in self.tribes:
                if tribe.alive:
                    for s in tribe.living_settlements:
                        if s is port:
                            tribe.tech_level = min(10,
                                                   tribe.tech_level + 1)
                            break

    # ------------------------------------------------------------------
    # Creature territories
    # ------------------------------------------------------------------

    def _populate_creature_territories(self, rng: random.Random):
        """Assign creature populations to regions based on biome.

        Scans large terrain regions, determines the dominant biome, and
        assigns notable creature territories.  Creatures near settlements
        are displaced; deep wilderness gets more dangerous beasts.
        """
        territories = []
        region_size = max(200, self.width // 8)

        for rx in range(0, self.width, region_size):
            for ry in range(0, self.height, region_size):
                cx = rx + region_size // 2
                cy = ry + region_size // 2
                if cx >= self.width or cy >= self.height:
                    continue

                # Determine dominant biome of this region
                e = self._elev_at(cx, cy)
                m = self._moisture_at(cx, cy)
                biome = self._classify_biome(e, m)
                if biome == "water":
                    continue

                # Check proximity to settlements (creatures displaced)
                min_settlement_dist = float("inf")
                for s in self.all_settlements:
                    if s.alive and s.population > POP_HAMLET:
                        d = math.sqrt((s.x - cx) ** 2 + (s.y - cy) ** 2)
                        if d < min_settlement_dist:
                            min_settlement_dist = d

                creature_pool = TERRITORY_CREATURES.get(biome, [])
                if not creature_pool:
                    continue

                # Deep wilderness gets more dangerous creatures
                is_deep_wild = min_settlement_dist > 500

                for creature, rarity, desc in creature_pool:
                    # Filter by rarity and distance to settlements
                    if rarity == "very_rare" and not is_deep_wild:
                        continue
                    if rarity == "rare" and min_settlement_dist < 250:
                        continue
                    if rarity == "common" and min_settlement_dist < 100:
                        continue  # common creatures displaced near towns

                    # Probabilistic placement
                    chance = {"common": 0.6, "uncommon": 0.3,
                              "rare": 0.1, "very_rare": 0.05}
                    if rng.random() < chance.get(rarity, 0.1):
                        territories.append({
                            "creature": creature,
                            "rarity": rarity,
                            "description": desc,
                            "region_x": cx,
                            "region_y": cy,
                            "biome": biome,
                            "is_deep_wilderness": is_deep_wild,
                        })
                        # Record significant creatures in events
                        if rarity in ("rare", "very_rare"):
                            direction = self._compass_direction(cx, cy)
                            self.events.append(
                                f"{desc} in the {direction} {biome}.")

        self._creature_territories = territories

    def _classify_biome(self, elev: float, moisture: float) -> str:
        """Classify a biome from elevation and moisture."""
        if elev < WATER_THRESHOLD:
            return "water"
        if elev >= SNOW_THRESHOLD:
            return "snow"
        if elev >= MOUNTAIN_THRESHOLD:
            return "mountain"
        if moisture > 0.55 and elev < 0.55:
            return "forest"
        if moisture < 0.25 and elev < 0.50:
            return "desert"
        if moisture > 0.50 and elev < 0.35:
            return "swamp"
        return "plains"

    def _compass_direction(self, x: int, y: int) -> str:
        """Return a compass-style direction name for coordinates."""
        cx, cy = self.width // 2, self.height // 2
        dx = x - cx
        dy = y - cy
        if abs(dx) < self.width // 6 and abs(dy) < self.height // 6:
            return "central"
        parts = []
        if dy < -self.height // 6:
            parts.append("northern")
        elif dy > self.height // 6:
            parts.append("southern")
        if dx < -self.width // 6:
            parts.append("western")
        elif dx > self.width // 6:
            parts.append("eastern")
        return " ".join(parts) if parts else "central"

    def _creature_events_during_sim(self, year: int, rng: random.Random):
        """Handle creature encounters during the simulation.

        Tribes fight monsters, domesticate animals, and suffer attacks.
        """
        for tribe in self.tribes:
            if not tribe.alive:
                continue

            # Monster encounter while exploring
            if rng.random() < 0.02:
                monsters = ["a troll", "a giant spider nest",
                            "a pack of dire wolves", "a wyvern",
                            "a basilisk", "a band of gnolls"]
                monster = rng.choice(monsters)
                self.events.append(
                    f"In year {year}, scouts from {tribe.name} encountered "
                    f"{monster} in the wilderness.")
                # Small military loss
                tribe.military = max(0, tribe.military - rng.randint(2, 10))

            # Domestication events (race-specific, rare)
            if year > 50 and rng.random() < 0.005:
                domestications = {
                    "Human": ("horses", "cavalry"),
                    "Elf": ("hawks", "scouts"),
                    "Dwarf": ("moles", "tunnel diggers"),
                    "Orc": ("wolves", "wolf-riders"),
                    "Goblin": ("rats", "spies"),
                }
                if tribe.race in domestications:
                    animal, use = domestications[tribe.race]
                    self.events.append(
                        f"In year {year}, {tribe.name} domesticated "
                        f"{animal} for use as {use}.")
                    tribe.military += 20

        # Dragon attack on settlements (very rare, devastating)
        if rng.random() < 0.003:
            living = [s for s in self.all_settlements
                      if s.alive and s.population > POP_VILLAGE]
            if living:
                victim = rng.choice(living)
                loss = max(10, int(victim.population * 0.4))
                victim.population -= loss
                victim.upgrade_kind()
                dragon_names = [
                    "Scorchtail", "Ashwing", "Grimfang",
                    "Dreadscale", "Infernus", "Shadowmaw",
                ]
                dragon = rng.choice(dragon_names)
                self.events.append(
                    f"In year {year}, the dragon {dragon} attacked "
                    f"{victim.name}, slaying {loss} souls.")

    # ------------------------------------------------------------------
    # Castle strategic placement helper
    # ------------------------------------------------------------------

    def _try_build_strategic_castle(self, tribe: Tribe, settlement: HistoricalSettlement,
                                    year: int, rng: random.Random):
        """Prefer building castles at locations with high strategic value."""
        # Evaluate the settlement's strategic score
        strat = self._score_strategic_value(settlement.x, settlement.y)
        # Higher strategic value = higher chance of castle construction
        base_chance = 0.05
        if strat > 30:
            base_chance = 0.15  # mountain pass or river ford
        elif strat > 15:
            base_chance = 0.10

        if rng.random() < base_chance:
            settlement.kind = "castle"
            settlement.garrison = max(settlement.garrison,
                                      settlement.population // 3)
            self.events.append(
                f"In year {year}, a castle was built at "
                f"{settlement.name} to defend {tribe.kingdom_name}.")

    # ------------------------------------------------------------------
    # Main simulation loop
    # ------------------------------------------------------------------

    def run(self, years: int = 500, rng: random.Random = None,
            progress_callback: Optional[Callable] = None) -> HistoryResult:
        """Run the full history simulation.

        Parameters
        ----------
        years : int
            Number of simulated years (default 500).
        rng : random.Random
            Deterministic RNG.
        progress_callback : callable, optional
            Called as progress_callback(message, fraction) during simulation.

        Returns
        -------
        HistoryResult
            Settlements, ruins, roads, kingdoms, events, etc.
        """
        if rng is None:
            rng = random.Random(self.seed)

        # Initialise storage for new subsystems
        self._historical_figures = []
        self._creature_territories = []

        if progress_callback:
            progress_callback("Placing ancient ruins...", 0.0)

        # Pre-history: place ruins from before the tribes arrived
        self._place_ancient_ruins(rng)

        if progress_callback:
            progress_callback("Creating tribes...", 0.02)

        self._create_tribes(rng)

        for year in range(years):
            if progress_callback and year % 50 == 0:
                progress_callback(f"Simulating year {year}...",
                                  0.05 + 0.80 * (year / years))

            for tribe in self.tribes:
                if not tribe.alive:
                    continue

                # Phase 1: Exploration (heavy early, tapers off)
                if year < 100 or rng.random() < 0.3:
                    self._explore(tribe, rng)

                # Phase 2: Settlement (throughout, but slows)
                settle_chance = 0.3 if year < 100 else 0.1
                if rng.random() < settle_chance:
                    self._try_settle(tribe, year, rng)

                # Growth every year
                self._grow_settlements(tribe, year, rng)

                # Resource depletion for mature settlements
                if year >= 100:
                    for s in tribe.living_settlements:
                        self._check_resource_depletion(s, year, rng)

                # Phase 3: Diplomacy and warfare (from year 30+)
                if year >= 30:
                    self._handle_diplomacy(tribe, year, rng)
                if year >= 50:
                    self._handle_warfare(tribe, year, rng)

                # Technology
                self._advance_technology(tribe, year, rng)

                # Historical figures (year 50+)
                if year >= 50:
                    self._generate_historical_figures(tribe, year, rng)

            # Phase 4: Kingdom formation (year 100+)
            if year >= 100 and year % 10 == 0:
                self._form_kingdoms(year, rng)

            # Phase 5: Late developments (year 300+)
            if year >= 300:
                self._late_developments(year, rng)

            # Climate events and natural disasters (any year)
            self._climate_events(year, rng)

            # Foreign trade (year 100+)
            self._establish_foreign_trade(year, rng)

            # Creature encounters during exploration
            if year >= 20:
                self._creature_events_during_sim(year, rng)

        if progress_callback:
            progress_callback("Placing standalone structures...", 0.88)

        # Post-simulation: place standalone structures
        self._place_standalone_structures(rng)

        if progress_callback:
            progress_callback("Populating creature territories...", 0.92)

        # Populate creature territories based on final world state
        self._populate_creature_territories(rng)

        if progress_callback:
            progress_callback("Building final world state...", 0.95)

        return self._build_result(rng)

    # ------------------------------------------------------------------
    # Result conversion
    # ------------------------------------------------------------------

    def _build_result(self, rng: random.Random) -> HistoryResult:
        """Convert simulation state into HistoryResult."""
        from game.world.world_plan import (
            SettlementPlan, RoadPlan, SpecialLocation)

        result = HistoryResult()
        result.historical_events = list(self.events)

        # --- Living settlements -> SettlementPlan ---
        area = self.width * self.height
        base = area / (2000 * 2000)
        radii = {
            "camp":    int(15 * math.sqrt(base)),
            "hamlet":  int(20 * math.sqrt(base)),
            "village": int(40 * math.sqrt(base)),
            "town":    int(70 * math.sqrt(base)),
            "city":    int(120 * math.sqrt(base)),
            "castle":  int(50 * math.sqrt(base)),
        }

        # Map tribe -> region name
        tribe_regions = {}
        for tribe in self.tribes:
            # Use the closest region-style name
            if tribe.race == "Human":
                tribe_regions[tribe.name] = "The Heartlands"
            elif tribe.race == "Elf":
                tribe_regions[tribe.name] = "The Silverwood"
            elif tribe.race == "Dwarf":
                tribe_regions[tribe.name] = "The Iron Peaks"
            elif tribe.race == "Orc":
                tribe_regions[tribe.name] = "The Blasted Wastes"
            elif tribe.race == "Goblin":
                tribe_regions[tribe.name] = "The Untamed Wilds"
            elif tribe.race == "Undead":
                tribe_regions[tribe.name] = "The Azure Coast"
            else:
                tribe_regions[tribe.name] = "The Heartlands"

        for s in self.all_settlements:
            if not s.alive:
                continue

            # Map population to NPC count (scaled down for gameplay)
            if s.kind == "city":
                npc_pop = rng.randint(100, 250)
            elif s.kind == "town":
                npc_pop = rng.randint(40, 100)
            elif s.kind == "village":
                npc_pop = rng.randint(15, 40)
            elif s.kind == "castle":
                npc_pop = rng.randint(20, 60)
            else:
                npc_pop = rng.randint(5, 15)

            region = tribe_regions.get(s.tribe_name, "The Heartlands")
            radius = radii.get(s.kind, radii["hamlet"])

            sp = SettlementPlan(
                name=s.name,
                kind=s.kind,
                x=s.x,
                y=s.y,
                radius=radius,
                region=region,
                race=s.race,
                population=npc_pop,
                specialization=s.specialization,
            )
            result.settlements.append(sp)

        # --- Destroyed settlements -> ruins ---
        for s in self.all_settlements:
            if s.destroyed_year is not None:
                # Find who destroyed it
                destroyed_by = "unknown"
                for event in self.events:
                    if s.name in event and "destroyed" in event:
                        # Extract the attacker
                        parts = event.split(" attacked and destroyed ")
                        if parts:
                            attacker_part = parts[0].split(", ")[-1]
                            destroyed_by = attacker_part
                        break

                result.ruins.append(RuinPlan(
                    name=s.name,
                    x=s.x,
                    y=s.y,
                    original_kind=s.kind,
                    destroyed_year=s.destroyed_year,
                    destroyed_by=destroyed_by,
                    race=s.race,
                    ruin_type=s.ruin_type or _KIND_TO_RUIN.get(
                        s.kind, "ruins"),
                ))

        # --- Road network (MST + trade routes) ---
        living = [s for s in result.settlements]
        if len(living) >= 2:
            result.roads = self._build_road_network(living, rng)

        # --- Kingdoms ---
        for tribe in self.tribes:
            if not tribe.alive or not tribe.kingdom_name:
                continue
            ls = tribe.living_settlements
            if not ls:
                continue

            capital = max(ls, key=lambda s: s.population)
            territory_names = [s.name for s in ls]

            result.kingdoms.append({
                "name": tribe.kingdom_name,
                "race": tribe.race,
                "governance_style": RACE_GOVERNANCE.get(
                    tribe.race, "feudalism"),
                "capital_settlement": capital.name,
                "territory_settlements": territory_names,
                "region": tribe_regions.get(tribe.name, "The Heartlands"),
                "center_x": tribe.center[0],
                "center_y": tribe.center[1],
                "ruler_name": self._generate_ruler_name(tribe.race, rng),
                "treasury": min(1000, max(50, tribe.gold)),  # cap to reasonable range
            })

        # --- Diplomatic relations ---
        for tribe in self.tribes:
            if not tribe.alive:
                continue
            for other_name, trust in tribe.relations.items():
                other = next(
                    (t for t in self.tribes if t.name == other_name), None)
                if other and other.alive:
                    key = tuple(sorted([tribe.name, other_name]))
                    if key not in result.diplomatic_relations:
                        result.diplomatic_relations[key] = trust

        # --- Trade routes ---
        for link in self.trade_links:
            t1_name, t2_name = link
            t1 = next((t for t in self.tribes if t.name == t1_name), None)
            t2 = next((t for t in self.tribes if t.name == t2_name), None)
            if t1 and t2 and t1.alive and t2.alive:
                result.trade_routes.append({
                    "tribe_a": t1_name,
                    "tribe_b": t2_name,
                    "race_a": t1.race,
                    "race_b": t2.race,
                })

        # --- Creature territories ---
        result.creature_territories = getattr(
            self, "_creature_territories", [])

        # --- Historical figures ---
        result.historical_figures = getattr(
            self, "_historical_figures", [])

        return result

    def _build_road_network(self, settlements: list,
                            rng: random.Random) -> list:
        """Build a road network using MST + extra trade connections."""
        from game.world.world_plan import RoadPlan

        if len(settlements) < 2:
            return []

        nodes = [(s.x, s.y, s.name, s.kind) for s in settlements]
        n = len(nodes)

        # Build edge list (only consider reasonably close pairs for speed)
        max_road_dist = max(self.width, self.height) * 0.4
        edges = []
        for i in range(n):
            for j in range(i + 1, n):
                dx = nodes[i][0] - nodes[j][0]
                dy = nodes[i][1] - nodes[j][1]
                d = math.sqrt(dx * dx + dy * dy)
                if d < max_road_dist:
                    edges.append((d, i, j))
        edges.sort()

        # Kruskal's MST
        parent = list(range(n))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        mst_edges = []
        for d, i, j in edges:
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[ri] = rj
                mst_edges.append((i, j, d))
            if len(mst_edges) == n - 1:
                break

        # Add extra edges for redundancy (20% of MST)
        mst_set = {(min(i, j), max(i, j)) for i, j, d in mst_edges}
        extra = max(2, len(mst_edges) // 5)
        for d, i, j in edges:
            key = (min(i, j), max(i, j))
            if key not in mst_set and extra > 0 and d < max_road_dist * 0.6:
                mst_edges.append((i, j, d))
                mst_set.add(key)
                extra -= 1

        # Create RoadPlan objects
        roads = []
        importance = {"city": 4, "town": 3, "castle": 3,
                      "village": 2, "hamlet": 1, "camp": 1}

        for i, j, d in mst_edges:
            x1, y1, n1, k1 = nodes[i]
            x2, y2, n2, k2 = nodes[j]

            imp = max(importance.get(k1, 1), importance.get(k2, 1))
            road_type = {4: "king_road", 3: "paved_road",
                         2: "gravel_road", 1: "dirt_track"}[imp]

            waypoints = self._road_waypoints(x1, y1, x2, y2, rng)
            roads.append(RoadPlan(
                start_name=n1, end_name=n2,
                road_type=road_type, waypoints=waypoints,
            ))

        return roads

    def _road_waypoints(self, x1: int, y1: int, x2: int, y2: int,
                        rng: random.Random) -> list:
        """Generate waypoints with natural curves, avoiding water."""
        points = [(x1, y1)]
        dist = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        segments = max(3, int(dist / 50))

        for i in range(1, segments):
            t = i / segments
            mx = x1 + (x2 - x1) * t + rng.randint(-15, 15)
            my = y1 + (y2 - y1) * t + rng.randint(-15, 15)
            mx = max(5, min(self.width - 5, mx))
            my = max(5, min(self.height - 5, my))

            # Try to avoid water
            if self._elev_at(int(mx), int(my)) < WATER_THRESHOLD:
                # Nudge toward midpoint between endpoints
                mx = x1 + (x2 - x1) * t
                my = y1 + (y2 - y1) * t

            points.append((int(mx), int(my)))

        points.append((x2, y2))
        return points

    def _generate_ruler_name(self, race: str,
                             rng: random.Random) -> str:
        """Generate a ruler name for a kingdom."""
        pools = {
            "Human": [
                "King Aldric", "Queen Seraphina", "Lord Edwyn",
                "Lady Margaux", "Duke Alderon", "Regent Castellan",
                "King Theodric", "Queen Elara", "King Marcus",
            ],
            "Elf": [
                "Archon Galadwen", "Councillor Thalion", "Elder Arannis",
                "Speaker Celeborn", "Warden Ithilwen", "Sage Lorendel",
            ],
            "Dwarf": [
                "Thane Borik Ironhand", "Thane Brunhild Stoneshield",
                "High Forgemaster Durin", "Clan Elder Gretta",
                "Thane Korrin Deepdelve", "Forge-Queen Hilda",
            ],
            "Orc": [
                "Warchief Grommash", "Warchief Urzog Bloodfist",
                "Overlord Kargath", "Boss Zug'thak",
                "Warlord Nazgrim", "Chieftain Drakthar",
            ],
            "Goblin": [
                "Great Sneak Nixle", "Boss Skrit", "Chief Grizznak",
                "Grand Skulker Plit", "Kingpin Yikkit", "Boss Ratclaw",
            ],
            "Undead": [
                "Lich Lord Veranthos", "The Pale King",
                "Necrolord Ashenveil", "Dread Sovereign Malachar",
                "The Bone Emperor", "Lich Queen Nethara",
            ],
        }
        pool = pools.get(race, pools["Human"])
        return rng.choice(pool)
