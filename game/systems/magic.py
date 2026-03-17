"""Magic system: schools, spells, mana, enchanting, alchemy, and soul magic.

Provides a unified magic framework with 8 schools (elemental, divine, arcane,
nature, necromancy, illusion, enchantment, transmutation), 102 spells with
real game effects, spell levels 1-9, practitioner class mappings, magic
equipment, spell components, a mana system, spell learning, enchanting,
alchemy integration, and soul magic tied to the soul system.
"""

import math
import random
import time as _time
from typing import List, Optional, Dict, Tuple, Any

from game.settings import *

# ================================================================
# SCHOOLS OF MAGIC
# ================================================================

MAGIC_SCHOOLS = {
    "elemental": {
        "spells": [
            "fireball", "ice_shard", "lightning_bolt", "wind_gust", "earthquake",
            "stone_wall", "flame_shield", "ice_storm", "chain_lightning",
            "meteor_swarm", "water_breathing", "fire_resistance", "frost_nova",
            "magma_burst", "control_weather",
        ],
        "color": (255, 100, 50),
        "description": "Harness the raw power of fire, ice, lightning, wind, and earth.",
        "stat": "intelligence",
    },
    "divine": {
        "spells": [
            "heal", "bless", "smite_undead", "sanctuary", "resurrect",
            "prayer", "divine_shield", "turn_undead", "holy_word", "mass_heal",
            "divine_wrath", "consecrate", "restoration", "atonement", "commune",
        ],
        "color": (255, 255, 200),
        "description": "Channel holy power to heal, protect, and smite the undead.",
        "stat": "wisdom",
    },
    "arcane": {
        "spells": [
            "magic_missile", "shield", "teleport", "detect_magic", "dispel",
            "identify", "invisibility", "fly", "time_stop", "polymorph",
            "scrying", "banishment", "prismatic_spray", "wish", "arcane_lock",
        ],
        "color": (150, 100, 255),
        "description": "Manipulate the weave of magic itself for offense and utility.",
        "stat": "intelligence",
    },
    "nature": {
        "spells": [
            "entangle", "cure_poison", "animal_friend", "growth", "storm_call",
            "speak_with_animals", "barkskin", "moonbeam", "insect_plague",
            "reincarnate", "tree_stride", "awaken", "sunbeam", "tsunami",
            "earthquake_greater",
        ],
        "color": (100, 200, 50),
        "description": "Draw upon the living world to bind, heal, and command nature.",
        "stat": "wisdom",
    },
    "necromancy": {
        "spells": [
            "animate_dead", "life_drain", "fear_aura", "corpse_explosion",
            "finger_of_death", "circle_of_death", "create_undead", "soul_trap",
            "death_ward", "speak_with_dead", "vampiric_touch", "blight",
        ],
        "color": (100, 50, 100),
        "description": "Command the forces of death, undeath, and negative energy.",
        "stat": "intelligence",
    },
    "illusion": {
        "spells": [
            "minor_illusion", "disguise", "mirror_image", "phantasmal_force",
            "greater_invisibility", "mirage", "dream", "simulacrum", "weird",
            "programmed_illusion",
        ],
        "color": (200, 150, 255),
        "description": "Bend light and perception to deceive, confuse, and terrify.",
        "stat": "intelligence",
    },
    "enchantment": {
        "spells": [
            "charm_person", "sleep_spell", "hold_person", "suggestion",
            "dominate", "geas", "mass_suggestion", "feeblemind",
            "power_word_stun", "power_word_kill",
        ],
        "color": (255, 150, 200),
        "description": "Influence and control the minds of others.",
        "stat": "charisma",
    },
    "transmutation": {
        "spells": [
            "mending", "enlarge", "haste", "slow", "stone_to_flesh",
            "flesh_to_stone", "disintegrate", "reverse_gravity",
            "true_polymorph", "creation",
        ],
        "color": (200, 200, 100),
        "description": "Alter the fundamental properties of matter and energy.",
        "stat": "intelligence",
    },
}

# Which D&D classes map to which magic school (primary school for affinity init)
CLASS_SCHOOL_AFFINITY = {
    "Wizard": "arcane",
    "Sorcerer": "elemental",
    "Cleric": "divine",
    "Paladin": "divine",
    "Druid": "nature",
    "Ranger": "nature",
    "Warlock": "necromancy",
    "Bard": "enchantment",
    "Necromancer": "necromancy",
    "Shaman": "nature",
    "Witch": "enchantment",
    "Monk": "transmutation",
}

# ================================================================
# PRACTITIONER CLASS MAPPINGS
# ================================================================

PRACTITIONER_SPELLS = {
    "Wizard": {"schools": ["arcane", "illusion", "enchantment", "transmutation"], "max_level": 9},
    "Sorcerer": {"schools": ["elemental", "arcane"], "max_level": 7, "innate": True},
    "Cleric": {"schools": ["divine"], "max_level": 7},
    "Druid": {"schools": ["nature"], "max_level": 7},
    "Warlock": {"schools": ["necromancy", "enchantment"], "max_level": 6},
    "Paladin": {"schools": ["divine"], "max_level": 4},
    "Ranger": {"schools": ["nature"], "max_level": 3},
    "Bard": {"schools": ["enchantment", "illusion"], "max_level": 5},
    "Necromancer": {"schools": ["necromancy"], "max_level": 9},
    "Shaman": {"schools": ["nature", "necromancy"], "max_level": 5},
    "Witch": {"schools": ["enchantment", "necromancy", "nature"], "max_level": 6},
    "Monk": {"schools": [], "ki_powers": True, "max_level": 0},
}


# ================================================================
# SPELL CLASS
# ================================================================

class Spell:
    """A castable spell with real game effects."""

    def __init__(self, name: str, school: str, mana_cost: int,
                 damage: int = 0, heal: int = 0,
                 range_tiles: float = 5.0, area: float = 0.0,
                 duration: float = 0.0, cooldown: float = 5.0,
                 description: str = "", level_required: int = 1,
                 effect_type: str = "instant",
                 targets: str = "single",
                 status_effect: str = "",
                 status_duration: float = 0.0,
                 chain_count: int = 0,
                 knockback: float = 0.0,
                 level: int = 1,
                 components: List[str] = None):
        self.name = name
        self.school = school
        self.level = level            # Spell level 1-9 (determines power tier)
        self.mana_cost = mana_cost
        self.damage = damage
        self.heal = heal
        self.range_tiles = range_tiles
        self.area = area              # AoE radius in tiles
        self.duration = duration       # buff/effect duration in seconds
        self.cooldown = cooldown       # seconds between casts
        self.description = description
        self.level_required = level_required
        self.effect_type = effect_type  # instant, buff, debuff, utility, summon
        self.targets = targets          # single, aoe, self, chain, ally
        self.status_effect = status_effect  # slow, stun, root, burn, etc.
        self.status_duration = status_duration
        self.chain_count = chain_count  # for chain spells
        self.knockback = knockback      # tiles of knockback
        self.components = components or []  # required spell components

    @property
    def base_mana_cost(self) -> int:
        """Level-based mana cost (level * 10)."""
        return self.level * 10

    @property
    def required_intelligence(self) -> int:
        """Minimum intelligence to learn this spell."""
        return 8 + self.level * 2

    @property
    def rarity(self) -> str:
        """Spell rarity tier based on level."""
        if self.level <= 3:
            return "common"
        elif self.level <= 6:
            return "uncommon"
        elif self.level <= 8:
            return "rare"
        else:
            return "legendary"


# ================================================================
# SPELL DEFINITIONS (102 spells across 8 schools)
# ================================================================

SPELL_REGISTRY: Dict[str, Spell] = {}


def _register_spells():
    """Register all 102 spells into the global registry."""
    spells = [
        # =============================================================
        # === ELEMENTAL (15) ===
        # =============================================================
        Spell("fireball", "elemental", mana_cost=25, damage=35,
              range_tiles=7, area=2.5, cooldown=8.0,
              description="Hurl an explosive ball of fire that damages all enemies in the blast.",
              level_required=3, effect_type="instant", targets="aoe",
              status_effect="burn", status_duration=4.0, level=3),

        Spell("ice_shard", "elemental", mana_cost=12, damage=20,
              range_tiles=6, cooldown=4.0,
              description="Launch a shard of ice that damages and slows the target.",
              level_required=1, effect_type="instant", targets="single",
              status_effect="slow", status_duration=5.0, level=1),

        Spell("lightning_bolt", "elemental", mana_cost=20, damage=25,
              range_tiles=8, cooldown=6.0,
              description="Call down a bolt of lightning that chains to nearby enemies.",
              level_required=3, effect_type="instant", targets="chain",
              chain_count=3, level=3),

        Spell("wind_gust", "elemental", mana_cost=10, damage=8,
              range_tiles=4, area=2.0, cooldown=5.0,
              description="Blast enemies back with a powerful gust of wind.",
              level_required=1, effect_type="instant", targets="aoe",
              knockback=3.0, level=1),

        Spell("earthquake", "elemental", mana_cost=35, damage=30,
              range_tiles=3, area=4.0, cooldown=15.0,
              description="Shake the earth, damaging and stunning all nearby enemies.",
              level_required=5, effect_type="instant", targets="aoe",
              status_effect="stun", status_duration=3.0, level=5),

        Spell("stone_wall", "elemental", mana_cost=20, duration=30.0,
              range_tiles=6, cooldown=15.0,
              description="Raise a wall of stone from the earth to block passage.",
              level_required=3, effect_type="utility", targets="aoe",
              area=1.5, level=3),

        Spell("flame_shield", "elemental", mana_cost=25, duration=20.0,
              damage=8, range_tiles=0, cooldown=12.0,
              description="Surround yourself in flames that damage melee attackers.",
              level_required=4, effect_type="buff", targets="self",
              status_effect="burn", status_duration=3.0, level=4),

        Spell("ice_storm", "elemental", mana_cost=40, damage=30,
              range_tiles=8, area=4.0, cooldown=18.0,
              description="Summon a storm of hail and ice over a wide area.",
              level_required=5, effect_type="instant", targets="aoe",
              status_effect="slow", status_duration=6.0, level=5),

        Spell("chain_lightning", "elemental", mana_cost=50, damage=40,
              range_tiles=10, cooldown=12.0,
              description="A bolt of lightning arcs between up to 6 enemies.",
              level_required=6, effect_type="instant", targets="chain",
              chain_count=6, level=6),

        Spell("meteor_swarm", "elemental", mana_cost=90, damage=80,
              range_tiles=12, area=6.0, cooldown=60.0,
              description="Call down a rain of meteors that devastates a huge area.",
              level_required=9, effect_type="instant", targets="aoe",
              status_effect="burn", status_duration=8.0, level=9,
              components=["fire_opal", "brimstone"]),

        Spell("water_breathing", "elemental", mana_cost=20, duration=600.0,
              range_tiles=3, cooldown=10.0,
              description="Grant the ability to breathe underwater.",
              level_required=2, effect_type="buff", targets="ally", level=2),

        Spell("fire_resistance", "elemental", mana_cost=25, duration=60.0,
              range_tiles=3, cooldown=15.0,
              description="Grant resistance to fire damage.",
              level_required=3, effect_type="buff", targets="ally", level=3),

        Spell("frost_nova", "elemental", mana_cost=18, damage=15,
              range_tiles=0, area=3.0, cooldown=8.0,
              description="Explode with freezing energy, damaging and slowing all nearby enemies.",
              level_required=2, effect_type="instant", targets="aoe",
              status_effect="slow", status_duration=4.0, level=2),

        Spell("magma_burst", "elemental", mana_cost=55, damage=50,
              range_tiles=6, area=3.0, cooldown=20.0,
              description="Erupt the ground with molten magma, leaving burning terrain.",
              level_required=6, effect_type="instant", targets="aoe",
              status_effect="burn", status_duration=6.0, level=6),

        Spell("control_weather", "elemental", mana_cost=70, duration=300.0,
              range_tiles=0, area=50.0, cooldown=120.0,
              description="Alter the weather in a large area for an extended period.",
              level_required=7, effect_type="utility", targets="self", level=7),

        # =============================================================
        # === DIVINE (15) ===
        # =============================================================
        Spell("heal", "divine", mana_cost=15, heal=40,
              range_tiles=3, cooldown=4.0,
              description="Restore health to yourself or a nearby ally.",
              level_required=1, effect_type="instant", targets="ally", level=1),

        Spell("bless", "divine", mana_cost=18, duration=30.0,
              range_tiles=5, area=3.0, cooldown=20.0,
              description="Bless nearby allies, boosting their attack and defense.",
              level_required=2, effect_type="buff", targets="aoe", level=2),

        Spell("smite_undead", "divine", mana_cost=20, damage=50,
              range_tiles=5, cooldown=6.0,
              description="Channel holy light to devastate undead creatures.",
              level_required=2, effect_type="instant", targets="single", level=2),

        Spell("sanctuary", "divine", mana_cost=25, duration=10.0,
              range_tiles=0, cooldown=30.0,
              description="Create a holy barrier that absorbs incoming damage.",
              level_required=3, effect_type="buff", targets="self", level=3),

        Spell("resurrect", "divine", mana_cost=50, heal=60,
              range_tiles=1, cooldown=120.0,
              description="Bring a recently fallen NPC back from death. Extremely taxing.",
              level_required=7, effect_type="instant", targets="ally", level=7,
              components=["diamond_dust", "holy_water"]),

        Spell("prayer", "divine", mana_cost=15, duration=60.0,
              range_tiles=0, area=5.0, cooldown=30.0,
              description="Offer a prayer that slightly boosts all allies' rolls.",
              level_required=2, effect_type="buff", targets="aoe", level=2),

        Spell("divine_shield", "divine", mana_cost=30, duration=15.0,
              range_tiles=3, cooldown=25.0,
              description="Encase an ally in a golden shield that absorbs heavy damage.",
              level_required=4, effect_type="buff", targets="ally", level=4),

        Spell("turn_undead", "divine", mana_cost=20, damage=15,
              range_tiles=0, area=5.0, cooldown=10.0,
              description="Force undead creatures to flee in terror from holy power.",
              level_required=2, effect_type="instant", targets="aoe",
              status_effect="fear", status_duration=6.0, level=2),

        Spell("holy_word", "divine", mana_cost=60, damage=55,
              range_tiles=0, area=6.0, cooldown=30.0,
              description="Speak a word of divine power that smites all evil creatures.",
              level_required=7, effect_type="instant", targets="aoe",
              status_effect="stun", status_duration=4.0, level=7),

        Spell("mass_heal", "divine", mana_cost=70, heal=50,
              range_tiles=0, area=6.0, cooldown=45.0,
              description="Restore health to all allies in a large area.",
              level_required=6, effect_type="instant", targets="aoe", level=6),

        Spell("divine_wrath", "divine", mana_cost=55, damage=60,
              range_tiles=8, cooldown=20.0,
              description="Call down a pillar of holy fire on a single target.",
              level_required=6, effect_type="instant", targets="single",
              status_effect="burn", status_duration=5.0, level=6),

        Spell("consecrate", "divine", mana_cost=30, duration=120.0,
              range_tiles=0, area=8.0, cooldown=60.0,
              description="Consecrate the ground, weakening undead and boosting allies.",
              level_required=3, effect_type="buff", targets="aoe", level=3),

        Spell("restoration", "divine", mana_cost=35, heal=20,
              range_tiles=3, cooldown=15.0,
              description="Remove curses, diseases, and ability drain from a target.",
              level_required=4, effect_type="instant", targets="ally", level=4),

        Spell("atonement", "divine", mana_cost=45, duration=0.0,
              range_tiles=1, cooldown=300.0,
              description="Absolve a creature of alignment transgressions, restoring divine favor.",
              level_required=5, effect_type="utility", targets="single", level=5),

        Spell("commune", "divine", mana_cost=50, duration=60.0,
              range_tiles=0, cooldown=600.0,
              description="Contact your deity to ask up to three yes-or-no questions.",
              level_required=5, effect_type="utility", targets="self", level=5),

        # =============================================================
        # === ARCANE (15) ===
        # =============================================================
        Spell("magic_missile", "arcane", mana_cost=8, damage=18,
              range_tiles=8, cooldown=2.0,
              description="Fire unerring bolts of force that always hit their target.",
              level_required=1, effect_type="instant", targets="single", level=1),

        Spell("shield", "arcane", mana_cost=12, duration=15.0,
              range_tiles=0, cooldown=10.0,
              description="Conjure a shimmering barrier that absorbs damage.",
              level_required=1, effect_type="buff", targets="self", level=1),

        Spell("teleport", "arcane", mana_cost=30,
              range_tiles=15, cooldown=20.0,
              description="Instantly move to a target location within range.",
              level_required=4, effect_type="utility", targets="self", level=5),

        Spell("detect_magic", "arcane", mana_cost=10, duration=20.0,
              range_tiles=10, cooldown=15.0,
              description="Reveal hidden magical items, traps, and enchantments.",
              level_required=1, effect_type="utility", targets="self", level=1),

        Spell("dispel", "arcane", mana_cost=20, range_tiles=6, cooldown=12.0,
              description="Remove curses, enchantments, and magical effects from a target.",
              level_required=3, effect_type="utility", targets="single", level=3),

        Spell("identify", "arcane", mana_cost=10, duration=0.0,
              range_tiles=1, cooldown=5.0,
              description="Reveal the properties of a magical item or creature.",
              level_required=1, effect_type="utility", targets="single", level=1),

        Spell("invisibility", "arcane", mana_cost=25, duration=30.0,
              range_tiles=1, cooldown=20.0,
              description="Turn yourself or an ally invisible until they attack.",
              level_required=3, effect_type="buff", targets="ally", level=2),

        Spell("fly", "arcane", mana_cost=30, duration=60.0,
              range_tiles=1, cooldown=30.0,
              description="Grant the ability to fly for a duration.",
              level_required=5, effect_type="buff", targets="ally", level=3),

        Spell("time_stop", "arcane", mana_cost=90, duration=6.0,
              range_tiles=0, cooldown=300.0,
              description="Freeze time for all other creatures, allowing free actions.",
              level_required=9, effect_type="utility", targets="self", level=9,
              components=["hourglass_sand", "moonstone"]),

        Spell("polymorph", "arcane", mana_cost=40, duration=60.0,
              range_tiles=5, cooldown=30.0,
              description="Transform a creature into a different beast form.",
              level_required=5, effect_type="utility", targets="single", level=4),

        Spell("scrying", "arcane", mana_cost=35, duration=30.0,
              range_tiles=0, cooldown=60.0,
              description="Observe a distant creature or location through a magical sensor.",
              level_required=5, effect_type="utility", targets="self", level=5,
              components=["crystal_ball"]),

        Spell("banishment", "arcane", mana_cost=40, duration=60.0,
              range_tiles=8, cooldown=30.0,
              description="Banish a creature to another plane of existence.",
              level_required=5, effect_type="instant", targets="single", level=4),

        Spell("prismatic_spray", "arcane", mana_cost=65, damage=50,
              range_tiles=10, area=3.0, cooldown=25.0,
              description="Spray a cone of seven colored rays with random devastating effects.",
              level_required=7, effect_type="instant", targets="aoe", level=7),

        Spell("wish", "arcane", mana_cost=90, duration=0.0,
              range_tiles=0, cooldown=86400.0,
              description="The mightiest spell a mortal can cast. Reshape reality itself.",
              level_required=9, effect_type="utility", targets="self", level=9,
              components=["astral_diamond"]),

        Spell("arcane_lock", "arcane", mana_cost=15, duration=86400.0,
              range_tiles=1, cooldown=10.0,
              description="Magically seal a door, chest, or portal.",
              level_required=2, effect_type="utility", targets="single", level=2),

        # =============================================================
        # === NATURE (15) ===
        # =============================================================
        Spell("entangle", "nature", mana_cost=15,
              range_tiles=6, area=2.0, cooldown=8.0,
              description="Roots burst from the ground to immobilize enemies.",
              level_required=1, effect_type="debuff", targets="aoe",
              status_effect="root", status_duration=5.0, level=1),

        Spell("cure_poison", "nature", mana_cost=12, heal=10,
              range_tiles=3, cooldown=5.0,
              description="Purge poison and disease from yourself or an ally.",
              level_required=1, effect_type="instant", targets="ally", level=1),

        Spell("animal_friend", "nature", mana_cost=15, duration=30.0,
              range_tiles=5, cooldown=15.0,
              description="Pacify a beast, making it non-hostile for a time.",
              level_required=2, effect_type="debuff", targets="single",
              status_effect="pacify", status_duration=30.0, level=2),

        Spell("growth", "nature", mana_cost=20, heal=25, duration=20.0,
              range_tiles=4, area=3.0, cooldown=25.0,
              description="Accelerate plant growth, healing allies and boosting nearby crops.",
              level_required=3, effect_type="buff", targets="aoe", level=3),

        Spell("storm_call", "nature", mana_cost=40, damage=28,
              range_tiles=8, area=5.0, cooldown=30.0,
              description="Summon a powerful storm that strikes enemies with wind and lightning.",
              level_required=5, effect_type="instant", targets="aoe",
              status_effect="slow", status_duration=4.0, level=5),

        Spell("speak_with_animals", "nature", mana_cost=10, duration=60.0,
              range_tiles=0, cooldown=10.0,
              description="Understand and communicate with beasts.",
              level_required=1, effect_type="utility", targets="self", level=1),

        Spell("barkskin", "nature", mana_cost=18, duration=60.0,
              range_tiles=1, cooldown=15.0,
              description="Harden skin to bark, granting natural armor.",
              level_required=2, effect_type="buff", targets="ally", level=2),

        Spell("moonbeam", "nature", mana_cost=25, damage=22,
              range_tiles=8, area=1.5, cooldown=10.0,
              description="Call down a beam of silvery moonlight that burns creatures.",
              level_required=3, effect_type="instant", targets="aoe",
              status_effect="burn", status_duration=3.0, level=3),

        Spell("insect_plague", "nature", mana_cost=45, damage=20,
              range_tiles=8, area=4.0, cooldown=20.0,
              description="Summon a swarm of biting insects that fills the area.",
              level_required=5, effect_type="instant", targets="aoe",
              status_effect="slow", status_duration=8.0, level=5),

        Spell("reincarnate", "nature", mana_cost=55, heal=80,
              range_tiles=1, cooldown=180.0,
              description="Return a dead creature to life in a new random body.",
              level_required=5, effect_type="instant", targets="ally", level=5),

        Spell("tree_stride", "nature", mana_cost=35, duration=60.0,
              range_tiles=0, cooldown=30.0,
              description="Step into one tree and emerge from another within range.",
              level_required=5, effect_type="utility", targets="self", level=5),

        Spell("awaken", "nature", mana_cost=50, duration=0.0,
              range_tiles=1, cooldown=600.0,
              description="Grant sentience and speech to a beast or plant permanently.",
              level_required=5, effect_type="utility", targets="single", level=5,
              components=["agate_gem"]),

        Spell("sunbeam", "nature", mana_cost=55, damage=45,
              range_tiles=10, cooldown=18.0,
              description="Fire a brilliant beam of sunlight that blinds and burns.",
              level_required=6, effect_type="instant", targets="single",
              status_effect="stun", status_duration=3.0, level=6),

        Spell("tsunami", "nature", mana_cost=75, damage=55,
              range_tiles=12, area=8.0, cooldown=60.0,
              description="Summon a massive wall of water that crashes over enemies.",
              level_required=8, effect_type="instant", targets="aoe",
              status_effect="slow", status_duration=6.0, level=8,
              components=["pearl"]),

        Spell("earthquake_greater", "nature", mana_cost=80, damage=50,
              range_tiles=5, area=10.0, cooldown=90.0,
              description="Cause a devastating earthquake that topples structures.",
              level_required=8, effect_type="instant", targets="aoe",
              status_effect="stun", status_duration=5.0, level=8),

        # =============================================================
        # === NECROMANCY (12) ===
        # =============================================================
        Spell("animate_dead", "necromancy", mana_cost=30, duration=300.0,
              range_tiles=3, cooldown=30.0,
              description="Raise a corpse as a skeleton or zombie servant.",
              level_required=3, effect_type="summon", targets="single", level=3),

        Spell("life_drain", "necromancy", mana_cost=20, damage=25, heal=15,
              range_tiles=5, cooldown=6.0,
              description="Drain life force from a target, healing yourself.",
              level_required=2, effect_type="instant", targets="single", level=2),

        Spell("fear_aura", "necromancy", mana_cost=25, duration=10.0,
              range_tiles=0, area=4.0, cooldown=15.0,
              description="Emit an aura of dread that terrifies nearby enemies.",
              level_required=3, effect_type="debuff", targets="aoe",
              status_effect="fear", status_duration=10.0, level=3),

        Spell("corpse_explosion", "necromancy", mana_cost=30, damage=35,
              range_tiles=6, area=3.0, cooldown=10.0,
              description="Detonate a corpse, dealing damage to all nearby creatures.",
              level_required=4, effect_type="instant", targets="aoe", level=4),

        Spell("finger_of_death", "necromancy", mana_cost=65, damage=80,
              range_tiles=6, cooldown=30.0,
              description="Point at a creature and channel lethal necrotic energy.",
              level_required=7, effect_type="instant", targets="single", level=7),

        Spell("circle_of_death", "necromancy", mana_cost=55, damage=50,
              range_tiles=8, area=5.0, cooldown=25.0,
              description="A sphere of negative energy expands, killing low-HP creatures.",
              level_required=6, effect_type="instant", targets="aoe", level=6),

        Spell("create_undead", "necromancy", mana_cost=60, duration=86400.0,
              range_tiles=3, cooldown=120.0,
              description="Create a powerful undead servant from remains.",
              level_required=6, effect_type="summon", targets="single", level=6,
              components=["onyx_gem", "black_candle"]),

        Spell("soul_trap", "necromancy", mana_cost=50, duration=0.0,
              range_tiles=5, cooldown=60.0,
              description="Trap the soul of a dying creature in a gem for later use.",
              level_required=6, effect_type="utility", targets="single", level=6,
              components=["soul_gem"]),

        Spell("death_ward", "necromancy", mana_cost=30, duration=120.0,
              range_tiles=3, cooldown=30.0,
              description="Protect a creature from death effects and instant-kill magic.",
              level_required=4, effect_type="buff", targets="ally", level=4),

        Spell("speak_with_dead", "necromancy", mana_cost=25, duration=30.0,
              range_tiles=3, cooldown=30.0,
              description="Ask questions of a corpse, drawing on residual memories.",
              level_required=3, effect_type="utility", targets="single", level=3),

        Spell("vampiric_touch", "necromancy", mana_cost=25, damage=30, heal=20,
              range_tiles=1, cooldown=8.0,
              description="Drain life with a touch, healing yourself for the damage dealt.",
              level_required=3, effect_type="instant", targets="single", level=3),

        Spell("blight", "necromancy", mana_cost=35, damage=40,
              range_tiles=6, cooldown=12.0,
              description="Wither a creature with necrotic energy. Devastating to plants.",
              level_required=4, effect_type="instant", targets="single", level=4),

        # =============================================================
        # === ILLUSION (10) ===
        # =============================================================
        Spell("minor_illusion", "illusion", mana_cost=5, duration=30.0,
              range_tiles=6, cooldown=3.0,
              description="Create a small illusory image or sound to distract.",
              level_required=1, effect_type="utility", targets="single", level=1),

        Spell("disguise", "illusion", mana_cost=12, duration=60.0,
              range_tiles=0, cooldown=10.0,
              description="Change your appearance to look like another humanoid.",
              level_required=1, effect_type="buff", targets="self", level=1),

        Spell("mirror_image", "illusion", mana_cost=18, duration=60.0,
              range_tiles=0, cooldown=15.0,
              description="Create illusory duplicates that confuse attackers.",
              level_required=2, effect_type="buff", targets="self", level=2),

        Spell("phantasmal_force", "illusion", mana_cost=22, damage=15, duration=30.0,
              range_tiles=8, cooldown=12.0,
              description="Create an illusion so real it deals psychic damage.",
              level_required=3, effect_type="debuff", targets="single",
              status_effect="fear", status_duration=5.0, level=3),

        Spell("greater_invisibility", "illusion", mana_cost=35, duration=30.0,
              range_tiles=1, cooldown=25.0,
              description="Turn invisible without breaking on attack.",
              level_required=5, effect_type="buff", targets="ally", level=4),

        Spell("mirage", "illusion", mana_cost=40, duration=120.0,
              range_tiles=10, area=10.0, cooldown=60.0,
              description="Create a large-scale illusion of terrain or structures.",
              level_required=5, effect_type="utility", targets="aoe", level=5),

        Spell("dream", "illusion", mana_cost=45, duration=480.0,
              range_tiles=0, cooldown=120.0,
              description="Enter a sleeping creature's dreams to communicate or terrify.",
              level_required=5, effect_type="utility", targets="single", level=5),

        Spell("simulacrum", "illusion", mana_cost=70, duration=86400.0,
              range_tiles=1, cooldown=600.0,
              description="Create an illusory duplicate of a creature with half its power.",
              level_required=7, effect_type="summon", targets="single", level=7,
              components=["powdered_ruby", "snow"]),

        Spell("weird", "illusion", mana_cost=80, damage=40,
              range_tiles=8, area=5.0, cooldown=40.0,
              description="Draw on deepest fears to create phantasmal killers for all in area.",
              level_required=9, effect_type="instant", targets="aoe",
              status_effect="fear", status_duration=10.0, level=9),

        Spell("programmed_illusion", "illusion", mana_cost=50, duration=86400.0,
              range_tiles=8, cooldown=60.0,
              description="Create an illusion that activates when specific conditions are met.",
              level_required=6, effect_type="utility", targets="single", level=6),

        # =============================================================
        # === ENCHANTMENT (10) ===
        # =============================================================
        Spell("charm_person", "enchantment", mana_cost=12, duration=60.0,
              range_tiles=6, cooldown=10.0,
              description="Magically charm a humanoid, making them regard you as a friend.",
              level_required=1, effect_type="debuff", targets="single",
              status_effect="pacify", status_duration=60.0, level=1),

        Spell("sleep_spell", "enchantment", mana_cost=15, duration=30.0,
              range_tiles=8, area=3.0, cooldown=12.0,
              description="Put creatures in an area into a magical slumber.",
              level_required=1, effect_type="debuff", targets="aoe",
              status_effect="stun", status_duration=30.0, level=1),

        Spell("hold_person", "enchantment", mana_cost=22, duration=15.0,
              range_tiles=6, cooldown=12.0,
              description="Paralyze a humanoid target with magical force.",
              level_required=3, effect_type="debuff", targets="single",
              status_effect="root", status_duration=15.0, level=2),

        Spell("suggestion", "enchantment", mana_cost=20, duration=120.0,
              range_tiles=5, cooldown=15.0,
              description="Magically influence a creature to follow a reasonable suggestion.",
              level_required=3, effect_type="debuff", targets="single",
              status_effect="pacify", status_duration=120.0, level=2),

        Spell("dominate", "enchantment", mana_cost=50, duration=60.0,
              range_tiles=6, cooldown=30.0,
              description="Take complete control of a creature's actions.",
              level_required=5, effect_type="debuff", targets="single",
              status_effect="pacify", status_duration=60.0, level=5),

        Spell("geas", "enchantment", mana_cost=45, duration=2592000.0,
              range_tiles=3, cooldown=120.0,
              description="Place a magical command on a creature that it must obey or suffer.",
              level_required=5, effect_type="debuff", targets="single", level=5),

        Spell("mass_suggestion", "enchantment", mana_cost=55, duration=120.0,
              range_tiles=8, area=5.0, cooldown=30.0,
              description="Suggest a course of action to up to twelve creatures.",
              level_required=6, effect_type="debuff", targets="aoe",
              status_effect="pacify", status_duration=120.0, level=6),

        Spell("feeblemind", "enchantment", mana_cost=70, duration=300.0,
              range_tiles=6, cooldown=60.0,
              description="Shatter a creature's intellect, reducing INT and CHA to 1.",
              level_required=8, effect_type="debuff", targets="single",
              status_effect="stun", status_duration=300.0, level=8),

        Spell("power_word_stun", "enchantment", mana_cost=75, duration=0.0,
              range_tiles=6, cooldown=40.0,
              description="Speak a word of power that stuns a creature below 150 HP.",
              level_required=8, effect_type="instant", targets="single",
              status_effect="stun", status_duration=10.0, level=8),

        Spell("power_word_kill", "enchantment", mana_cost=90, damage=999,
              range_tiles=6, cooldown=120.0,
              description="Speak a word of power that instantly kills a creature below 100 HP.",
              level_required=9, effect_type="instant", targets="single", level=9),

        # =============================================================
        # === TRANSMUTATION (10) ===
        # =============================================================
        Spell("mending", "transmutation", mana_cost=5, heal=5,
              range_tiles=1, cooldown=3.0,
              description="Repair a small break or tear in an object.",
              level_required=1, effect_type="utility", targets="single", level=1),

        Spell("enlarge", "transmutation", mana_cost=18, duration=60.0,
              range_tiles=5, cooldown=15.0,
              description="Double a creature's size, granting bonus damage.",
              level_required=2, effect_type="buff", targets="ally", level=2),

        Spell("haste", "transmutation", mana_cost=30, duration=30.0,
              range_tiles=5, cooldown=20.0,
              description="Double a creature's speed and grant an extra action.",
              level_required=3, effect_type="buff", targets="ally", level=3),

        Spell("slow", "transmutation", mana_cost=25, duration=30.0,
              range_tiles=8, area=3.0, cooldown=15.0,
              description="Halve the speed of up to six creatures in an area.",
              level_required=3, effect_type="debuff", targets="aoe",
              status_effect="slow", status_duration=30.0, level=3),

        Spell("stone_to_flesh", "transmutation", mana_cost=40, duration=0.0,
              range_tiles=3, cooldown=20.0,
              description="Restore a petrified creature to flesh, or soften stone.",
              level_required=6, effect_type="utility", targets="single", level=6),

        Spell("flesh_to_stone", "transmutation", mana_cost=50, duration=0.0,
              range_tiles=6, cooldown=30.0,
              description="Attempt to turn a creature to stone permanently.",
              level_required=6, effect_type="instant", targets="single",
              status_effect="stun", status_duration=999.0, level=6),

        Spell("disintegrate", "transmutation", mana_cost=60, damage=75,
              range_tiles=8, cooldown=25.0,
              description="A thin green ray reduces a creature or object to dust.",
              level_required=6, effect_type="instant", targets="single", level=6),

        Spell("reverse_gravity", "transmutation", mana_cost=65, damage=20,
              range_tiles=10, area=4.0, cooldown=30.0,
              description="Reverse gravity in an area, sending creatures skyward.",
              level_required=7, effect_type="instant", targets="aoe",
              status_effect="stun", status_duration=4.0, level=7),

        Spell("true_polymorph", "transmutation", mana_cost=85, duration=0.0,
              range_tiles=5, cooldown=120.0,
              description="Permanently transform a creature into another creature or object.",
              level_required=9, effect_type="utility", targets="single", level=9,
              components=["shapeshifter_essence"]),

        Spell("creation", "transmutation", mana_cost=45, duration=600.0,
              range_tiles=3, cooldown=30.0,
              description="Create a non-magical object from raw magical energy.",
              level_required=5, effect_type="utility", targets="self", level=5),
    ]

    for sp in spells:
        SPELL_REGISTRY[sp.name] = sp


_register_spells()


# ================================================================
# SPELL COMPONENTS (required materials for high-level spells)
# ================================================================

SPELL_COMPONENTS = {
    "resurrect": ["diamond_dust", "holy_water"],
    "wish": ["astral_diamond"],
    "meteor_swarm": ["fire_opal", "brimstone"],
    "time_stop": ["hourglass_sand", "moonstone"],
    "true_polymorph": ["shapeshifter_essence"],
    "create_undead": ["onyx_gem", "black_candle"],
    "soul_trap": ["soul_gem"],
    "simulacrum": ["powdered_ruby", "snow"],
    "awaken": ["agate_gem"],
    "tsunami": ["pearl"],
    "scrying": ["crystal_ball"],
    "finger_of_death": [],
    "circle_of_death": [],
    "holy_word": [],
    "prismatic_spray": [],
    "weird": [],
    "power_word_kill": [],
    "power_word_stun": [],
    "earthquake_greater": [],
    "feeblemind": [],
}


# ================================================================
# MAGIC EQUIPMENT
# ================================================================

MAGIC_ITEMS = {
    "wand_of_fireball": {"spell": "fireball", "charges": 10, "value": 500,
                         "description": "A wand that casts fireball."},
    "staff_of_healing": {"spell": "heal", "charges": 20, "mana_boost": 30, "value": 800,
                         "description": "A staff that heals and boosts mana capacity."},
    "ring_of_protection": {"effect": "ac_bonus", "bonus": 2, "value": 1000,
                           "description": "A ring that provides +2 armor class."},
    "amulet_of_mana": {"effect": "max_mana_boost", "bonus": 50, "value": 600,
                       "description": "An amulet that increases maximum mana by 50."},
    "cloak_of_invisibility": {"spell": "invisibility", "charges": 3, "value": 2000,
                              "description": "A cloak that grants invisibility."},
    "boots_of_speed": {"effect": "speed_boost", "bonus": 1.3, "value": 400,
                       "description": "Boots that increase movement speed by 30%."},
    "helm_of_telepathy": {"spell": "detect_magic", "charges": 5, "value": 700,
                          "description": "A helm that reveals magical auras."},
    "wand_of_lightning": {"spell": "lightning_bolt", "charges": 8, "value": 550,
                          "description": "A wand that casts lightning bolt."},
    "staff_of_the_necromancer": {"spell": "animate_dead", "charges": 5, "mana_boost": 20,
                                "value": 1200, "description": "A dark staff for raising the dead."},
    "ring_of_spell_storing": {"effect": "spell_store", "bonus": 3, "value": 1500,
                              "description": "A ring that stores up to 3 spell charges."},
    "amulet_of_proof_against_detection": {"effect": "scry_immunity", "bonus": 1, "value": 900,
                                          "description": "Blocks scrying and divination."},
    "pearl_of_power": {"effect": "mana_restore", "bonus": 30, "value": 700,
                       "description": "Once per day, restore 30 mana."},
    "rod_of_absorption": {"effect": "spell_absorb", "bonus": 50, "value": 2500,
                          "description": "Absorbs incoming spell damage as mana."},
    "bracers_of_defense": {"effect": "ac_bonus", "bonus": 3, "value": 1200,
                           "description": "Bracers that grant +3 AC to unarmored wearers."},
    "cloak_of_displacement": {"effect": "dodge_bonus", "bonus": 0.15, "value": 1800,
                              "description": "Illusory displacement grants 15% dodge chance."},
    "wand_of_fear": {"spell": "fear_aura", "charges": 7, "value": 600,
                     "description": "A wand that projects an aura of dread."},
    "staff_of_frost": {"spell": "ice_storm", "charges": 6, "mana_boost": 25, "value": 1000,
                       "description": "A staff of swirling frost energy."},
    "ring_of_regeneration": {"effect": "hp_regen", "bonus": 2, "value": 1400,
                             "description": "Slowly regenerates HP over time."},
    "wand_of_polymorph": {"spell": "polymorph", "charges": 5, "value": 900,
                          "description": "A wand that transforms creatures."},
    "tome_of_clear_thought": {"effect": "int_boost", "bonus": 2, "value": 3000,
                              "description": "Reading this tome permanently raises INT by 2."},
}


# ================================================================
# SOUL MAGIC (rare high-level spells, separate from the 4 schools)
# ================================================================

SOUL_SPELLS: Dict[str, Spell] = {}


def _register_soul_spells():
    """Soul magic -- rare spells requiring high divine or arcane affinity."""
    spells = [
        Spell("soul_sight", "divine", mana_cost=20, duration=30.0,
              range_tiles=0, cooldown=45.0,
              description="Temporarily see ghost souls drifting near their death location.",
              level_required=5, effect_type="utility", targets="self", level=5),

        Spell("soul_ward", "divine", mana_cost=30, duration=60.0,
              range_tiles=0, area=6.0, cooldown=90.0,
              description="Create a ward around an area that prevents undead soul drain.",
              level_required=6, effect_type="buff", targets="aoe", level=6),

        Spell("soul_speak", "arcane", mana_cost=25, duration=20.0,
              range_tiles=3, cooldown=60.0,
              description="Communicate with a ghost soul to learn its past-life memories.",
              level_required=5, effect_type="utility", targets="single", level=5),

        Spell("exorcism", "divine", mana_cost=40, damage=35,
              range_tiles=4, cooldown=45.0,
              description="Force an undead creature to release consumed souls, dealing holy damage.",
              level_required=7, effect_type="instant", targets="single", level=7),
    ]
    for sp in spells:
        SOUL_SPELLS[sp.name] = sp


_register_soul_spells()


# ================================================================
# ACTIVE SPELL EFFECT (applied to entities)
# ================================================================

class SpellEffect:
    """A temporary effect applied to an entity by a spell."""

    def __init__(self, name: str, effect_type: str, value: float,
                 duration: float, source_name: str = ""):
        self.name = name              # e.g. "burn", "slow", "shield"
        self.effect_type = effect_type  # "damage_over_time", "slow", "stun",
                                        # "root", "shield", "buff_attack",
                                        # "buff_defense", "pacify", "soul_sight"
        self.value = value            # magnitude (damage per tick, slow %, shield hp, etc.)
        self.duration = duration      # remaining seconds
        self.source_name = source_name
        self.tick_timer = 0.0         # for DoT effects

    def update(self, dt: float, entity) -> Optional[str]:
        """Tick the effect. Returns a message if something notable happens."""
        self.duration -= dt
        msg = None

        if self.effect_type == "damage_over_time":
            self.tick_timer += dt
            if self.tick_timer >= 1.0:
                self.tick_timer -= 1.0
                actual = entity.take_damage(int(self.value))
                msg = f"{getattr(entity, 'name', 'Target')} takes {actual} {self.name} damage"

        return msg

    @property
    def expired(self) -> bool:
        return self.duration <= 0


# ================================================================
# MANA SYSTEM
# ================================================================

# Mana regen rates (per second)
MANA_REGEN_BASE = 1.0
MANA_REGEN_RESTING = 3.0
MANA_REGEN_TEMPLE = 5.0

# Intelligence -> max mana formula
def calc_max_mana(intelligence: int, level: int) -> int:
    """Calculate maximum mana from intelligence score and level."""
    from game.data.dnd import ability_modifier
    int_mod = ability_modifier(intelligence)
    return max(20, 30 + int_mod * 8 + level * 5)


def get_mana_regen_rate(entity, world=None) -> float:
    """Determine mana regeneration rate based on context."""
    rate = MANA_REGEN_BASE

    # Resting bonus
    state = getattr(entity, 'state', '')
    if state in ('sleeping', 'resting'):
        rate = MANA_REGEN_RESTING

    # Wisdom bonus
    wis = 10
    scores = getattr(entity, 'ability_scores', None)
    if scores:
        wis = scores.get('wisdom', 10)
    from game.data.dnd import ability_modifier
    wis_mod = ability_modifier(wis)
    rate += max(0, wis_mod * 0.3)

    return rate


def init_mana(entity):
    """Initialize mana attributes on a player or NPC.

    Safe to call multiple times -- skips if already initialized.
    """
    if hasattr(entity, 'mana') and hasattr(entity, 'max_mana'):
        return  # already initialized

    scores = getattr(entity, 'ability_scores', {})
    intelligence = scores.get('intelligence', 10)
    level = getattr(entity, 'level', 1)
    entity.max_mana = calc_max_mana(intelligence, level)
    entity.mana = entity.max_mana

    # Spell cooldown tracking: spell_name -> remaining cooldown
    if not hasattr(entity, 'spell_cooldowns'):
        entity.spell_cooldowns = {}

    # Active spell effects on this entity
    if not hasattr(entity, 'active_spell_effects'):
        entity.active_spell_effects = []

    # Magic-system known spells (coexists with D&D spell_list in known_spells)
    if not hasattr(entity, 'magic_known_spells'):
        entity.magic_known_spells = []

    # School affinity: school_name -> proficiency (0.0 - 1.0)
    if not hasattr(entity, 'school_affinity'):
        entity.school_affinity = {}
        # Set affinity from D&D class
        char_class = getattr(entity, 'char_class', '')
        school = CLASS_SCHOOL_AFFINITY.get(char_class)
        if school:
            entity.school_affinity[school] = 0.5


# ================================================================
# SPELL LEARNING
# ================================================================

def can_learn_spell(entity, spell_name: str) -> Tuple[bool, str]:
    """Check if an entity can learn a spell. Returns (ok, reason)."""
    spell = SPELL_REGISTRY.get(spell_name) or SOUL_SPELLS.get(spell_name)
    if spell is None:
        return False, f"Unknown spell: {spell_name}"

    init_mana(entity)

    # Already known?
    if spell_name in entity.magic_known_spells:
        return False, f"Already knows {spell_name}"

    # Level check
    level = getattr(entity, 'level', 1)
    if level < spell.level_required:
        return False, f"Requires level {spell.level_required} (have {level})"

    # Intelligence check (uses spell level for scaling)
    scores = getattr(entity, 'ability_scores', {})
    intelligence = scores.get('intelligence', 10)
    min_int = spell.required_intelligence  # 8 + level * 2
    if intelligence < min_int:
        return False, f"Requires {min_int} INT (have {intelligence})"

    # Practitioner class spell level cap check
    char_class = getattr(entity, 'char_class', '')
    prac = PRACTITIONER_SPELLS.get(char_class)
    if prac:
        if spell.level > prac.get("max_level", 9):
            return False, f"{char_class} cannot learn spells above level {prac['max_level']}"
        # Check school access
        allowed_schools = prac.get("schools", [])
        if allowed_schools and spell.school not in allowed_schools:
            # Still allow if INT is very high (18+)
            if intelligence < 18:
                return False, f"{char_class} cannot access {spell.school} school"

    # Spell component awareness (components checked at cast time, not learn time)

    # School affinity check (soul spells need divine or arcane >= 0.3)
    if spell_name in SOUL_SPELLS:
        divine_aff = entity.school_affinity.get("divine", 0)
        arcane_aff = entity.school_affinity.get("arcane", 0)
        if divine_aff < 0.3 and arcane_aff < 0.3:
            return False, "Requires divine or arcane affinity"
    else:
        school_aff = entity.school_affinity.get(spell.school, 0)
        # Non-affinity schools need higher threshold
        if school_aff < 0.1:
            # Can still learn if INT is very high
            if intelligence < 16:
                return False, f"No affinity for {spell.school} school"

    return True, "OK"


def learn_spell(entity, spell_name: str) -> str:
    """Attempt to teach a spell to an entity. Returns result message."""
    ok, reason = can_learn_spell(entity, spell_name)
    if not ok:
        return f"Cannot learn {spell_name}: {reason}"

    init_mana(entity)
    entity.magic_known_spells.append(spell_name)

    # Boost school affinity slightly
    spell = SPELL_REGISTRY.get(spell_name) or SOUL_SPELLS.get(spell_name)
    if spell:
        old = entity.school_affinity.get(spell.school, 0)
        entity.school_affinity[spell.school] = min(1.0, old + 0.1)

    return f"Learned {spell_name}!"


def auto_learn_spells_for_class(entity):
    """Give an entity starting spells based on their D&D class.

    Called during entity initialization. Uses PRACTITIONER_SPELLS to determine
    which schools and spell levels the class can access.
    """
    init_mana(entity)
    char_class = getattr(entity, 'char_class', '')
    level = getattr(entity, 'level', 1)

    prac = PRACTITIONER_SPELLS.get(char_class)
    if not prac:
        # Fall back to old single-school affinity
        school = CLASS_SCHOOL_AFFINITY.get(char_class)
        if not school:
            return  # non-caster class
        school_data = MAGIC_SCHOOLS.get(school, {})
        available = school_data.get("spells", [])
        for sp_name in available:
            sp = SPELL_REGISTRY.get(sp_name)
            if sp and sp.level_required <= level:
                if sp_name not in entity.magic_known_spells:
                    entity.magic_known_spells.append(sp_name)
        entity.school_affinity[school] = min(1.0, 0.3 + level * 0.1)
        return

    max_spell_level = prac.get("max_level", 0)
    allowed_schools = prac.get("schools", [])

    # Learn spells from all allowed schools up to level allowance
    for school_name in allowed_schools:
        school_data = MAGIC_SCHOOLS.get(school_name, {})
        available = school_data.get("spells", [])
        for sp_name in available:
            sp = SPELL_REGISTRY.get(sp_name)
            if sp and sp.level_required <= level and sp.level <= max_spell_level:
                if sp_name not in entity.magic_known_spells:
                    entity.magic_known_spells.append(sp_name)
        # Set school affinity based on class level
        entity.school_affinity[school_name] = min(1.0, 0.3 + level * 0.1)


# ================================================================
# SPELL CASTING
# ================================================================

def can_cast(entity, spell_name: str) -> Tuple[bool, str]:
    """Check whether entity can cast a spell right now."""
    init_mana(entity)

    spell = SPELL_REGISTRY.get(spell_name) or SOUL_SPELLS.get(spell_name)
    if spell is None:
        return False, "Unknown spell"

    if spell_name not in entity.magic_known_spells:
        return False, "Spell not known"

    if entity.mana < spell.mana_cost:
        return False, f"Not enough mana ({entity.mana}/{spell.mana_cost})"

    cd = entity.spell_cooldowns.get(spell_name, 0)
    if cd > 0:
        return False, f"On cooldown ({cd:.1f}s)"

    # Stunned/silenced check
    for eff in getattr(entity, 'active_spell_effects', []):
        if eff.effect_type == "stun" and not eff.expired:
            return False, "Stunned!"
        if eff.effect_type == "root" and spell_name == "teleport":
            return False, "Rooted! Cannot teleport"
        if eff.effect_type == "fear" and not eff.expired:
            return False, "Too frightened to cast!"

    # Spell component check for high-level spells
    if spell.components:
        inv = getattr(entity, 'inventory', getattr(entity, 'npc_inventory', []))
        for comp in spell.components:
            found = False
            for item in inv:
                if getattr(item, 'name', '').lower().replace(' ', '_') == comp:
                    found = True
                    break
            if not found:
                return False, f"Missing component: {comp}"

    return True, "OK"


def cast_spell(caster, spell_name: str, target=None,
               target_pos: Tuple[float, float] = None,
               entities_nearby: List = None) -> Dict[str, Any]:
    """Execute a spell cast. Returns a result dict with messages and effects.

    Parameters:
        caster: the entity casting (Player or NPC)
        spell_name: name of the spell
        target: a specific target entity (or None for AoE/self)
        target_pos: (x, y) target position for positional spells
        entities_nearby: list of entities in range for AoE/chain spells

    Returns dict with keys:
        "success": bool
        "message": str
        "damage_dealt": dict of entity -> damage
        "healing_done": dict of entity -> healing
        "effects_applied": list of (entity, SpellEffect)
        "spell": the Spell object
    """
    ok, reason = can_cast(caster, spell_name)
    result = {
        "success": False, "message": reason,
        "damage_dealt": {}, "healing_done": {},
        "effects_applied": [], "spell": None,
    }
    if not ok:
        return result

    spell = SPELL_REGISTRY.get(spell_name) or SOUL_SPELLS.get(spell_name)
    result["spell"] = spell

    # Spend mana and set cooldown
    caster.mana -= spell.mana_cost
    caster.spell_cooldowns[spell_name] = spell.cooldown

    entities_nearby = entities_nearby or []

    # -- Resolve targets --
    targets_hit = []
    allies_hit = []

    if spell.targets == "self":
        targets_hit = [caster]
        allies_hit = [caster]

    elif spell.targets == "single":
        if target is not None:
            dist = _dist(caster, target)
            if dist <= spell.range_tiles:
                targets_hit = [target]
            else:
                result["message"] = "Target out of range"
                # Refund mana on range failure
                caster.mana += spell.mana_cost
                caster.spell_cooldowns[spell_name] = 0
                return result
        else:
            result["message"] = "No target"
            caster.mana += spell.mana_cost
            caster.spell_cooldowns[spell_name] = 0
            return result

    elif spell.targets == "ally":
        if target is not None:
            dist = _dist(caster, target)
            if dist <= spell.range_tiles:
                allies_hit = [target]
            else:
                result["message"] = "Target out of range"
                caster.mana += spell.mana_cost
                caster.spell_cooldowns[spell_name] = 0
                return result
        else:
            # Self-target for ally spells with no target
            allies_hit = [caster]

    elif spell.targets == "aoe":
        cx, cy = target_pos if target_pos else (caster.x, caster.y)
        for ent in entities_nearby:
            if not getattr(ent, 'alive', True):
                continue
            d = math.sqrt((ent.x - cx) ** 2 + (ent.y - cy) ** 2)
            if d <= spell.area:
                if spell.effect_type == "buff":
                    allies_hit.append(ent)
                else:
                    # Don't hit caster with own AoE damage
                    if ent is not caster:
                        targets_hit.append(ent)
        # For self-cast AoE buffs, always include caster
        if spell.effect_type == "buff" and caster not in allies_hit:
            allies_hit.append(caster)

    elif spell.targets == "chain":
        if target is not None:
            targets_hit = [target]
            # Chain to additional nearby enemies
            remaining = spell.chain_count - 1
            last = target
            used = {id(target)}
            for ent in sorted(entities_nearby,
                              key=lambda e: _dist(last, e)):
                if remaining <= 0:
                    break
                if id(ent) in used or ent is caster:
                    continue
                if not getattr(ent, 'alive', True):
                    continue
                if _dist(last, ent) <= 4.0:  # chain range
                    targets_hit.append(ent)
                    used.add(id(ent))
                    last = ent
                    remaining -= 1

    # -- Apply spell effects --
    messages = []

    # Damage
    if spell.damage > 0:
        for t in targets_hit:
            dmg = spell.damage
            # Smite undead bonus
            if spell_name == "smite_undead":
                mtype = getattr(t, 'monster_type', '')
                if mtype != 'undead':
                    dmg = dmg // 3  # reduced damage to non-undead

            # School affinity damage bonus
            aff = caster.school_affinity.get(spell.school, 0)
            dmg = int(dmg * (1.0 + aff * 0.3))

            # Intelligence scaling
            scores = getattr(caster, 'ability_scores', {})
            stat_name = MAGIC_SCHOOLS.get(spell.school, {}).get("stat", "intelligence")
            stat_val = scores.get(stat_name, 10)
            from game.data.dnd import ability_modifier
            stat_mod = ability_modifier(stat_val)
            dmg += stat_mod * 2

            actual = t.take_damage(max(1, dmg))
            result["damage_dealt"][t] = actual
            name = getattr(t, 'name', getattr(t, 'kind', 'target'))
            messages.append(f"{name} takes {actual} {spell.school} damage")

            if not getattr(t, 'alive', True):
                messages.append(f"{name} was slain!")

    # Healing
    if spell.heal > 0:
        heal_targets = allies_hit if allies_hit else targets_hit
        for t in heal_targets:
            # Resurrect special handling
            if spell_name == "resurrect":
                if not getattr(t, 'alive', True):
                    t.alive = True
                    t.hp = spell.heal
                    name = getattr(t, 'name', 'target')
                    messages.append(f"{name} has been resurrected!")
                    result["healing_done"][t] = spell.heal
                continue

            if not getattr(t, 'alive', True):
                continue
            old_hp = t.hp
            t.heal(spell.heal)
            healed = t.hp - old_hp
            result["healing_done"][t] = healed
            name = getattr(t, 'name', getattr(t, 'kind', 'target'))
            if healed > 0:
                messages.append(f"{name} healed for {healed}")

    # Cure poison
    if spell_name == "cure_poison":
        heal_targets = allies_hit if allies_hit else [caster]
        for t in heal_targets:
            conditions = getattr(t, 'conditions', [])
            removed = []
            for c in conditions:
                ckey = getattr(c, 'key', '')
                if 'poison' in ckey.lower() or 'disease' in ckey.lower():
                    removed.append(c)
            for c in removed:
                conditions.remove(c)
            if removed:
                name = getattr(t, 'name', 'target')
                messages.append(f"Cured {len(removed)} ailment(s) from {name}")

    # Status effects (burn, slow, stun, root, pacify)
    if spell.status_effect:
        effect_targets = targets_hit
        for t in effect_targets:
            eff = _make_status_effect(spell)
            if not hasattr(t, 'active_spell_effects'):
                t.active_spell_effects = []
            t.active_spell_effects.append(eff)
            result["effects_applied"].append((t, eff))
            name = getattr(t, 'name', getattr(t, 'kind', 'target'))
            messages.append(f"{name} is {spell.status_effect}{'ed' if not spell.status_effect.endswith('e') else 'd'}!")

    # Knockback
    if spell.knockback > 0:
        for t in targets_hit:
            dx = t.x - caster.x
            dy = t.y - caster.y
            dist = math.sqrt(dx * dx + dy * dy) or 1
            t.x += (dx / dist) * spell.knockback
            t.y += (dy / dist) * spell.knockback

    # Buff effects (bless, shield, sanctuary)
    if spell.effect_type == "buff" and spell.duration > 0:
        buff_targets = allies_hit if allies_hit else [caster]
        for t in buff_targets:
            eff = _make_buff_effect(spell)
            if not hasattr(t, 'active_spell_effects'):
                t.active_spell_effects = []
            t.active_spell_effects.append(eff)
            result["effects_applied"].append((t, eff))

        if spell_name == "bless":
            messages.append("Allies are blessed! +3 attack and defense")
        elif spell_name == "shield":
            messages.append("Arcane shield active! Absorbing up to 30 damage")
        elif spell_name == "sanctuary":
            messages.append("Holy sanctuary active! Absorbing up to 50 damage")
        elif spell_name == "growth":
            messages.append("Nature surges with vitality!")

    # Utility spells
    if spell_name == "teleport":
        if target_pos:
            caster.x, caster.y = target_pos
            messages.append(f"Teleported to ({int(target_pos[0])}, {int(target_pos[1])})")
        else:
            # Teleport in facing direction
            fx, fy = getattr(caster, 'facing', (0, 1))
            caster.x += fx * spell.range_tiles
            caster.y += fy * spell.range_tiles
            messages.append(f"Teleported forward!")

    if spell_name == "detect_magic":
        eff = SpellEffect("detect_magic", "detect_magic", 1.0,
                          spell.duration, getattr(caster, 'name', ''))
        if not hasattr(caster, 'active_spell_effects'):
            caster.active_spell_effects = []
        caster.active_spell_effects.append(eff)
        result["effects_applied"].append((caster, eff))
        messages.append("Magical auras revealed!")

    if spell_name == "dispel":
        if target is not None:
            effects = getattr(target, 'active_spell_effects', [])
            count = len(effects)
            target.active_spell_effects = []
            # Also try to remove curses from health conditions
            conditions = getattr(target, 'conditions', [])
            cursed = [c for c in conditions
                      if 'curse' in getattr(c, 'key', '').lower()]
            for c in cursed:
                conditions.remove(c)
            count += len(cursed)
            name = getattr(target, 'name', 'target')
            messages.append(f"Dispelled {count} effect(s) from {name}")

    if spell_name == "animal_friend":
        if target is not None:
            mtype = getattr(target, 'monster_type', '')
            if mtype == 'beast':
                target.passive = True
                # Mark as pacified
                if hasattr(target, 'combat_target'):
                    target.combat_target = None
                name = getattr(target, 'name', getattr(target, 'kind', 'beast'))
                messages.append(f"{name} is calmed and non-hostile")
            else:
                messages.append("Animal Friend only works on beasts")

    # -- Soul magic special handling --
    if spell_name == "soul_sight":
        eff = SpellEffect("soul_sight", "soul_sight", 1.0,
                          spell.duration, getattr(caster, 'name', ''))
        if not hasattr(caster, 'active_spell_effects'):
            caster.active_spell_effects = []
        caster.active_spell_effects.append(eff)
        result["effects_applied"].append((caster, eff))
        messages.append("You can now perceive ghost souls...")

    if spell_name == "soul_ward":
        eff = SpellEffect("soul_ward", "soul_ward", spell.area,
                          spell.duration, getattr(caster, 'name', ''))
        if not hasattr(caster, 'active_spell_effects'):
            caster.active_spell_effects = []
        caster.active_spell_effects.append(eff)
        result["effects_applied"].append((caster, eff))
        messages.append(f"Soul ward active in {spell.area:.0f} tile radius")

    if spell_name == "soul_speak":
        # The actual ghost interaction is handled by the caller
        messages.append("You reach out to the spirit world...")

    if spell_name == "exorcism":
        if target is not None:
            mtype = getattr(target, 'monster_type', '')
            if mtype == 'undead':
                # Extra holy damage to undead
                bonus = 20
                actual = target.take_damage(bonus)
                result["damage_dealt"][target] = result["damage_dealt"].get(target, 0) + actual
                messages.append(f"Exorcism tears {actual} additional damage from the undead!")
                # Release souls (handled by soul system integration)
            else:
                messages.append("Exorcism only affects undead")

    # Grant skill XP for casting
    _grant_cast_xp(caster, spell)

    result["success"] = True
    result["message"] = "; ".join(messages) if messages else f"Cast {spell_name}!"

    # Store pending spell visual for renderer to pick up
    target_x = target.x if target and hasattr(target, 'x') else caster.x
    target_y = target.y if target and hasattr(target, 'y') else caster.y
    if target_pos:
        target_x, target_y = target_pos
    if not hasattr(caster, '_pending_spell_visuals'):
        caster._pending_spell_visuals = []
    caster._pending_spell_visuals.append({
        "spell_name": spell_name,
        "x": caster.x, "y": caster.y,
        "target_x": target_x, "target_y": target_y,
    })

    return result


def _make_status_effect(spell: Spell) -> SpellEffect:
    """Create a SpellEffect from a spell's status effect."""
    etype_map = {
        "burn": "damage_over_time",
        "slow": "slow",
        "stun": "stun",
        "root": "root",
        "pacify": "pacify",
        "fear": "fear",
    }
    etype = etype_map.get(spell.status_effect, spell.status_effect)
    value = 0
    if spell.status_effect == "burn":
        value = 5  # 5 damage per second
    elif spell.status_effect == "slow":
        value = 0.5  # 50% speed reduction
    elif spell.status_effect == "stun":
        value = 1.0  # full stun
    elif spell.status_effect == "root":
        value = 1.0  # full root
    elif spell.status_effect == "pacify":
        value = 1.0
    elif spell.status_effect == "fear":
        value = 1.0  # full fear (flee behavior)

    return SpellEffect(spell.status_effect, etype, value,
                       spell.status_duration, spell.name)


def _make_buff_effect(spell: Spell) -> SpellEffect:
    """Create a buff SpellEffect from a spell."""
    if spell.name == "bless":
        return SpellEffect("bless", "buff_attack_defense", 3.0,
                           spell.duration, spell.name)
    elif spell.name == "shield":
        return SpellEffect("shield", "shield", 30.0,
                           spell.duration, spell.name)
    elif spell.name == "sanctuary":
        return SpellEffect("sanctuary", "shield", 50.0,
                           spell.duration, spell.name)
    elif spell.name == "growth":
        return SpellEffect("growth", "regen", 3.0,
                           spell.duration, spell.name)
    else:
        return SpellEffect(spell.name, "buff_generic", 1.0,
                           spell.duration, spell.name)


def _dist(a, b) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    return math.sqrt(dx * dx + dy * dy)


def _grant_cast_xp(caster, spell: Spell):
    """Grant spellcraft skill XP when casting."""
    if hasattr(caster, 'gain_skill_xp'):
        caster.gain_skill_xp("spellcraft", 0.5 + spell.mana_cost * 0.05)


# ================================================================
# MAGIC UPDATE (called each frame for entities with mana)
# ================================================================

def update_magic(entity, dt: float, world=None):
    """Per-frame update: mana regen, cooldowns, spell effects."""
    if not hasattr(entity, 'mana'):
        return

    # Mana regeneration
    if entity.mana < entity.max_mana and getattr(entity, 'alive', True):
        regen = get_mana_regen_rate(entity, world)
        entity.mana = min(entity.max_mana, entity.mana + regen * dt)

    # Tick cooldowns
    cds = getattr(entity, 'spell_cooldowns', {})
    for name in list(cds.keys()):
        cds[name] -= dt
        if cds[name] <= 0:
            del cds[name]

    # Tick active spell effects
    effects = getattr(entity, 'active_spell_effects', [])
    expired = []
    for eff in effects:
        msg = eff.update(dt, entity)
        if eff.expired:
            expired.append(eff)

    for eff in expired:
        effects.remove(eff)
        # Clean up effect side-effects
        if eff.effect_type == "pacify" and hasattr(entity, 'passive'):
            # Re-aggro when pacify wears off (creature)
            entity.passive = getattr(entity, '_original_passive', False)


def get_speed_modifier(entity) -> float:
    """Return speed multiplier from active spell effects (slow/root/stun)."""
    mult = 1.0
    for eff in getattr(entity, 'active_spell_effects', []):
        if eff.expired:
            continue
        if eff.effect_type == "slow":
            mult *= eff.value  # value is the multiplier (0.5 = half speed)
        elif eff.effect_type in ("stun", "root"):
            mult = 0.0
    return mult


def get_attack_modifier(entity) -> int:
    """Return attack bonus from active buff effects."""
    bonus = 0
    for eff in getattr(entity, 'active_spell_effects', []):
        if eff.expired:
            continue
        if eff.effect_type == "buff_attack_defense":
            bonus += int(eff.value)
    return bonus


def get_defense_modifier(entity) -> int:
    """Return defense bonus from active buff effects."""
    bonus = 0
    for eff in getattr(entity, 'active_spell_effects', []):
        if eff.expired:
            continue
        if eff.effect_type == "buff_attack_defense":
            bonus += int(eff.value)
    return bonus


def absorb_damage(entity, damage: int) -> int:
    """Check for shield effects that absorb damage. Returns remaining damage."""
    for eff in getattr(entity, 'active_spell_effects', []):
        if eff.expired:
            continue
        if eff.effect_type == "shield" and eff.value > 0:
            absorbed = min(damage, int(eff.value))
            eff.value -= absorbed
            damage -= absorbed
            if eff.value <= 0:
                eff.duration = 0  # expire the shield
            if damage <= 0:
                return 0
    return damage


def has_effect(entity, effect_name: str) -> bool:
    """Check if an entity has a specific active spell effect."""
    for eff in getattr(entity, 'active_spell_effects', []):
        if eff.name == effect_name and not eff.expired:
            return True
    return False


# ================================================================
# ENCHANTING SYSTEM
# ================================================================

ENCHANTMENT_TYPES = {
    "fire": {"damage_bonus": 5, "color": (255, 80, 20), "description": "Wreathed in flame"},
    "frost": {"damage_bonus": 4, "color": (100, 180, 255), "description": "Coated in frost"},
    "lightning": {"damage_bonus": 6, "color": (255, 255, 100), "description": "Crackling with sparks"},
    "holy": {"damage_bonus": 4, "color": (255, 255, 200), "description": "Blessed with holy light"},
}

ENCHANTMENT_RESISTANCES = {
    "fire_resist": {"reduction": 0.3, "description": "Resistant to fire"},
    "frost_resist": {"reduction": 0.3, "description": "Resistant to frost"},
    "lightning_resist": {"reduction": 0.3, "description": "Resistant to lightning"},
    "holy_resist": {"reduction": 0.3, "description": "Resistant to holy"},
}

# Reagent requirements for enchanting
ENCHANT_REAGENTS = {
    "fire": [("Raw Ruby", 1), ("Fire Oil", 2)],
    "frost": [("Raw Sapphire", 1), ("Herbs", 3)],
    "lightning": [("Raw Emerald", 1), ("Iron Ingot", 1)],
    "holy": [("Raw Diamond", 1), ("Holy Water", 2)],
}

RESIST_ENCHANT_REAGENTS = {
    "fire_resist": [("Raw Ruby", 1), ("Herbs", 2)],
    "frost_resist": [("Raw Sapphire", 1), ("Herbs", 2)],
    "lightning_resist": [("Raw Emerald", 1), ("Herbs", 2)],
    "holy_resist": [("Raw Diamond", 1), ("Herbs", 2)],
}


class Enchantment:
    """An enchantment applied to a weapon or armor piece."""

    def __init__(self, ench_type: str, charges: int = -1, permanent: bool = False):
        self.ench_type = ench_type        # e.g. "fire", "frost", "fire_resist"
        self.charges = charges            # -1 = permanent (weaker), >0 = limited charges
        self.permanent = permanent
        self.active = True

    @property
    def damage_bonus(self) -> int:
        if not self.active:
            return 0
        data = ENCHANTMENT_TYPES.get(self.ench_type, {})
        bonus = data.get("damage_bonus", 0)
        if self.permanent:
            bonus = max(1, bonus // 2)  # permanent enchants are weaker
        return bonus

    @property
    def resistance(self) -> float:
        if not self.active:
            return 0.0
        data = ENCHANTMENT_RESISTANCES.get(self.ench_type, {})
        red = data.get("reduction", 0)
        if self.permanent:
            red *= 0.5  # permanent resist enchants are weaker
        return red

    def use_charge(self):
        """Consume one charge (for non-permanent enchantments)."""
        if self.charges > 0:
            self.charges -= 1
            if self.charges <= 0:
                self.active = False


def can_enchant_weapon(entity, item, ench_type: str) -> Tuple[bool, str]:
    """Check if an entity can enchant a weapon."""
    if item.kind != ITEM_WEAPON:
        return False, "Can only enchant weapons"

    if ench_type not in ENCHANTMENT_TYPES:
        return False, f"Unknown enchantment type: {ench_type}"

    # Check enchanting skill
    skills = getattr(entity, 'skills', getattr(entity, 'npc_skills', {}))
    ench_skill = skills.get('enchanting', 0)
    if ench_skill < 2:
        return False, "Need enchanting skill level 2+"

    # Check mana
    init_mana(entity)
    if entity.mana < 20:
        return False, "Need at least 20 mana"

    # Check reagents
    reagents = ENCHANT_REAGENTS.get(ench_type, [])
    for reagent_name, count in reagents:
        have = 0
        inv = getattr(entity, 'inventory', getattr(entity, 'npc_inventory', []))
        for it in inv:
            if it.name == reagent_name:
                have = it.count if it.stackable else 1
        if have < count:
            return False, f"Need {count} {reagent_name} (have {have})"

    return True, "OK"


def enchant_weapon(entity, item, ench_type: str, permanent: bool = False) -> str:
    """Apply an enchantment to a weapon. Returns result message."""
    ok, reason = can_enchant_weapon(entity, item, ench_type)
    if not ok:
        return f"Cannot enchant: {reason}"

    # Consume resources
    entity.mana -= 20
    reagents = ENCHANT_REAGENTS.get(ench_type, [])
    for reagent_name, count in reagents:
        if hasattr(entity, 'remove_item'):
            entity.remove_item(reagent_name, count)
        elif hasattr(entity, 'npc_remove_item'):
            entity.npc_remove_item(reagent_name, count)

    # Apply enchantment
    charges = -1 if permanent else 30
    ench = Enchantment(ench_type, charges=charges, permanent=permanent)
    if not hasattr(item, 'enchantment'):
        item.enchantment = None
    item.enchantment = ench

    bonus = ench.damage_bonus
    item.damage += bonus

    desc = ENCHANTMENT_TYPES[ench_type]["description"]
    charge_str = "permanent" if permanent else f"{charges} charges"
    if hasattr(entity, 'gain_skill_xp'):
        entity.gain_skill_xp("enchanting", 3.0)
    return f"Enchanted {item.name} with {ench_type}! (+{bonus} dmg, {charge_str}, {desc})"


def can_enchant_armor(entity, item, resist_type: str) -> Tuple[bool, str]:
    """Check if an entity can enchant armor with a resistance."""
    if item.kind != ITEM_ARMOR:
        return False, "Can only enchant armor"

    if resist_type not in ENCHANTMENT_RESISTANCES:
        return False, f"Unknown resistance type: {resist_type}"

    skills = getattr(entity, 'skills', getattr(entity, 'npc_skills', {}))
    ench_skill = skills.get('enchanting', 0)
    if ench_skill < 3:
        return False, "Need enchanting skill level 3+"

    init_mana(entity)
    if entity.mana < 25:
        return False, "Need at least 25 mana"

    reagents = RESIST_ENCHANT_REAGENTS.get(resist_type, [])
    for reagent_name, count in reagents:
        have = 0
        inv = getattr(entity, 'inventory', getattr(entity, 'npc_inventory', []))
        for it in inv:
            if it.name == reagent_name:
                have = it.count if it.stackable else 1
        if have < count:
            return False, f"Need {count} {reagent_name} (have {have})"

    return True, "OK"


def enchant_armor(entity, item, resist_type: str, permanent: bool = False) -> str:
    """Apply a resistance enchantment to armor."""
    ok, reason = can_enchant_armor(entity, item, resist_type)
    if not ok:
        return f"Cannot enchant: {reason}"

    entity.mana -= 25
    reagents = RESIST_ENCHANT_REAGENTS.get(resist_type, [])
    for reagent_name, count in reagents:
        if hasattr(entity, 'remove_item'):
            entity.remove_item(reagent_name, count)
        elif hasattr(entity, 'npc_remove_item'):
            entity.npc_remove_item(reagent_name, count)

    charges = -1 if permanent else 30
    ench = Enchantment(resist_type, charges=charges, permanent=permanent)
    if not hasattr(item, 'enchantment'):
        item.enchantment = None
    item.enchantment = ench

    desc = ENCHANTMENT_RESISTANCES[resist_type]["description"]
    charge_str = "permanent" if permanent else f"{charges} charges"
    if hasattr(entity, 'gain_skill_xp'):
        entity.gain_skill_xp("enchanting", 4.0)
    return f"Enchanted {item.name} with {resist_type}! ({charge_str}, {desc})"


# ================================================================
# ALCHEMY SYSTEM
# ================================================================

ALCHEMY_RECIPES = {
    "Health Potion": {
        "ingredients": [("Herbs", 2), ("Mushrooms", 1)],
        "mana_cost": 5,
        "skill_required": 1,
        "description": "Restores 30 HP",
    },
    "Greater Health Potion": {
        "ingredients": [("Herbs", 4), ("Mushrooms", 2), ("Honey", 1)],
        "mana_cost": 10,
        "skill_required": 3,
        "description": "Restores 60 HP",
    },
    "Mana Potion": {
        "ingredients": [("Flowers", 3), ("Mushrooms", 2)],
        "mana_cost": 0,  # special: costs no mana since it restores mana
        "skill_required": 2,
        "description": "Restores 25 mana",
    },
    "Antidote": {
        "ingredients": [("Herbs", 2), ("Berries", 1)],
        "mana_cost": 3,
        "skill_required": 1,
        "description": "Cures poison",
    },
    "Strength Potion": {
        "ingredients": [("Mushrooms", 3), ("Raw Meat", 1), ("Herbs", 1)],
        "mana_cost": 8,
        "skill_required": 3,
        "description": "Temporarily boosts strength",
    },
    "Invisibility Potion": {
        "ingredients": [("Flowers", 4), ("Mushrooms", 3), ("Herbs", 2)],
        "mana_cost": 15,
        "skill_required": 5,
        "description": "Grants brief invisibility",
    },
}


def can_brew_potion(entity, recipe_name: str) -> Tuple[bool, str]:
    """Check if an entity can brew a potion."""
    recipe = ALCHEMY_RECIPES.get(recipe_name)
    if recipe is None:
        return False, f"Unknown recipe: {recipe_name}"

    # Check alchemy skill
    skills = getattr(entity, 'skills', getattr(entity, 'npc_skills', {}))
    alchemy_skill = skills.get('alchemy', 0)
    if alchemy_skill < recipe["skill_required"]:
        return False, f"Need alchemy skill {recipe['skill_required']}+ (have {alchemy_skill})"

    # Check mana
    if recipe["mana_cost"] > 0:
        init_mana(entity)
        if entity.mana < recipe["mana_cost"]:
            return False, f"Need {recipe['mana_cost']} mana"

    # Check ingredients
    inv = getattr(entity, 'inventory', getattr(entity, 'npc_inventory', []))
    for ingredient_name, count in recipe["ingredients"]:
        have = 0
        for it in inv:
            if it.name == ingredient_name:
                have = it.count if it.stackable else 1
        if have < count:
            return False, f"Need {count} {ingredient_name} (have {have})"

    return True, "OK"


def brew_potion(entity, recipe_name: str) -> str:
    """Brew a potion. Consumes ingredients and mana, produces item."""
    ok, reason = can_brew_potion(entity, recipe_name)
    if not ok:
        return f"Cannot brew: {reason}"

    recipe = ALCHEMY_RECIPES[recipe_name]

    # Consume mana
    if recipe["mana_cost"] > 0:
        entity.mana -= recipe["mana_cost"]

    # Consume ingredients
    for ingredient_name, count in recipe["ingredients"]:
        if hasattr(entity, 'remove_item'):
            entity.remove_item(ingredient_name, count)
        elif hasattr(entity, 'npc_remove_item'):
            entity.npc_remove_item(ingredient_name, count)

    # Produce potion
    from game.core.items import make_item, Item, ITEMS
    if recipe_name == "Mana Potion":
        # Mana Potion is a new item type
        potion = Item("Mana Potion", ITEM_CONSUMABLE, 20,
                      description="Restores 25 mana.", stackable=True)
    elif recipe_name == "Strength Potion":
        potion = Item("Strength Potion", ITEM_CONSUMABLE, 35,
                      description="Temporarily boosts strength by 4.", stackable=True)
    elif recipe_name == "Invisibility Potion":
        potion = Item("Invisibility Potion", ITEM_CONSUMABLE, 70,
                      description="Grants 15s of invisibility.", stackable=True)
    else:
        potion = make_item(recipe_name)

    if hasattr(entity, 'add_item'):
        entity.add_item(potion)
    elif hasattr(entity, 'npc_add_item'):
        entity.npc_add_item(potion)

    if hasattr(entity, 'gain_skill_xp'):
        entity.gain_skill_xp("alchemy", 2.0 + recipe.get("skill_required", 1))

    return f"Brewed {recipe_name}!"


def use_mana_potion(entity) -> str:
    """Use a Mana Potion from inventory to restore mana."""
    init_mana(entity)
    inv = getattr(entity, 'inventory', getattr(entity, 'npc_inventory', []))
    for item in inv:
        if item.name == "Mana Potion":
            old_mana = entity.mana
            entity.mana = min(entity.max_mana, entity.mana + 25)
            restored = entity.mana - old_mana
            if hasattr(entity, 'remove_item'):
                entity.remove_item("Mana Potion", 1)
            elif hasattr(entity, 'npc_remove_item'):
                entity.npc_remove_item("Mana Potion", 1)
            return f"Restored {restored:.0f} mana"
    return "No Mana Potion in inventory"


def use_strength_potion(entity) -> str:
    """Use a Strength Potion -- apply a temporary STR buff."""
    init_mana(entity)
    inv = getattr(entity, 'inventory', getattr(entity, 'npc_inventory', []))
    for item in inv:
        if item.name == "Strength Potion":
            eff = SpellEffect("strength_buff", "buff_strength", 4.0,
                              60.0, "Strength Potion")
            if not hasattr(entity, 'active_spell_effects'):
                entity.active_spell_effects = []
            entity.active_spell_effects.append(eff)
            if hasattr(entity, 'remove_item'):
                entity.remove_item("Strength Potion", 1)
            elif hasattr(entity, 'npc_remove_item'):
                entity.npc_remove_item("Strength Potion", 1)
            return "Strength increased by 4 for 60 seconds!"
    return "No Strength Potion in inventory"


def use_invisibility_potion(entity) -> str:
    """Use an Invisibility Potion -- apply a temporary invisibility effect."""
    inv = getattr(entity, 'inventory', getattr(entity, 'npc_inventory', []))
    for item in inv:
        if item.name == "Invisibility Potion":
            eff = SpellEffect("invisibility", "invisibility", 1.0,
                              15.0, "Invisibility Potion")
            if not hasattr(entity, 'active_spell_effects'):
                entity.active_spell_effects = []
            entity.active_spell_effects.append(eff)
            if hasattr(entity, 'remove_item'):
                entity.remove_item("Invisibility Potion", 1)
            elif hasattr(entity, 'npc_remove_item'):
                entity.npc_remove_item("Invisibility Potion", 1)
            return "You are invisible for 15 seconds!"
    return "No Invisibility Potion in inventory"


# ================================================================
# NPC MAGIC AI
# ================================================================

def npc_choose_spell(npc, enemies: List, allies: List) -> Optional[Tuple[str, Any]]:
    """NPC AI: pick the best spell to cast given the situation.

    Returns (spell_name, target) or None.
    """
    init_mana(npc)
    known = getattr(npc, 'magic_known_spells', [])
    if not known:
        return None

    # Priority: heal self/allies if low HP, then offensive
    npc_hp_pct = npc.hp / max(1, npc.max_hp)

    # Heal self if low
    if npc_hp_pct < 0.4 and "heal" in known:
        ok, _ = can_cast(npc, "heal")
        if ok:
            return ("heal", npc)

    # Heal low-HP ally
    for ally in allies:
        if not getattr(ally, 'alive', True):
            continue
        ally_hp_pct = ally.hp / max(1, ally.max_hp)
        if ally_hp_pct < 0.3 and "heal" in known:
            ok, _ = can_cast(npc, "heal")
            if ok and _dist(npc, ally) <= 3:
                return ("heal", ally)

    # Resurrect dead ally
    if "resurrect" in known:
        for ally in allies:
            if not getattr(ally, 'alive', True) and _dist(npc, ally) <= 1:
                ok, _ = can_cast(npc, "resurrect")
                if ok:
                    return ("resurrect", ally)

    # Bless if not already active and there are allies nearby
    if "bless" in known and not has_effect(npc, "bless"):
        ok, _ = can_cast(npc, "bless")
        if ok and (allies or enemies):
            return ("bless", None)

    # Shield/sanctuary if about to fight and not shielded
    if enemies:
        if "sanctuary" in known and not has_effect(npc, "sanctuary"):
            ok, _ = can_cast(npc, "sanctuary")
            if ok:
                return ("sanctuary", None)
        if "shield" in known and not has_effect(npc, "shield"):
            ok, _ = can_cast(npc, "shield")
            if ok:
                return ("shield", None)

    # Offensive spells
    if not enemies:
        return None

    # Find nearest enemy
    nearest = min(enemies, key=lambda e: _dist(npc, e))
    dist = _dist(npc, nearest)

    # Prioritize AoE if multiple enemies nearby
    clustered = sum(1 for e in enemies if _dist(nearest, e) < 3)

    # Undead-specific
    mtype = getattr(nearest, 'monster_type', '')
    if mtype == 'undead' and "smite_undead" in known:
        ok, _ = can_cast(npc, "smite_undead")
        if ok and dist <= 5:
            return ("smite_undead", nearest)

    if mtype == 'undead' and "exorcism" in known:
        ok, _ = can_cast(npc, "exorcism")
        if ok and dist <= 4:
            return ("exorcism", nearest)

    # AoE preference
    if clustered >= 3:
        for sp_name in ["fireball", "earthquake", "storm_call"]:
            if sp_name in known:
                ok, _ = can_cast(npc, sp_name)
                spell = SPELL_REGISTRY.get(sp_name)
                if ok and spell and dist <= spell.range_tiles:
                    return (sp_name, nearest)

    # Entangle if enemies are approaching
    if "entangle" in known and dist < 6:
        ok, _ = can_cast(npc, "entangle")
        if ok:
            return ("entangle", nearest)

    # Single target damage
    for sp_name in ["lightning_bolt", "ice_shard", "magic_missile"]:
        if sp_name in known:
            ok, _ = can_cast(npc, sp_name)
            spell = SPELL_REGISTRY.get(sp_name)
            if ok and spell and dist <= spell.range_tiles:
                return (sp_name, nearest)

    # Wind gust if enemy is very close
    if "wind_gust" in known and dist < 3:
        ok, _ = can_cast(npc, "wind_gust")
        if ok:
            return ("wind_gust", nearest)

    # Animal friend for beasts
    beast_type = getattr(nearest, 'monster_type', '')
    if beast_type == 'beast' and "animal_friend" in known:
        ok, _ = can_cast(npc, "animal_friend")
        if ok and dist <= 5:
            return ("animal_friend", nearest)

    return None


def npc_cast_spell(npc, spell_name: str, target, entities_nearby: List) -> Dict:
    """Execute an NPC spell cast."""
    target_pos = (target.x, target.y) if target else None
    return cast_spell(npc, spell_name, target=target,
                      target_pos=target_pos,
                      entities_nearby=entities_nearby)


# ================================================================
# SPELL EFFECT RENDERING HELPERS
# ================================================================

def get_spell_visual(spell_name: str) -> Dict[str, Any]:
    """Return visual parameters for rendering a spell effect.

    Used by the renderer to spawn particles / flash effects.
    """
    spell = SPELL_REGISTRY.get(spell_name) or SOUL_SPELLS.get(spell_name)
    if spell is None:
        return {"color": (255, 255, 255), "particles": 0, "flash": False}

    school_color = MAGIC_SCHOOLS.get(spell.school, {}).get("color", (255, 255, 255))

    visuals = {
        "color": school_color,
        "particles": 8,
        "flash": True,
        "flash_color": school_color,
        "particle_spread": spell.area if spell.area > 0 else 1.0,
        "particle_lifetime": 0.5,
        "school": spell.school,
    }

    # Per-spell overrides
    if spell_name == "fireball":
        visuals["color"] = (255, 120, 30)
        visuals["particles"] = 20
        visuals["particle_spread"] = spell.area
        visuals["flash_color"] = (255, 200, 100)
    elif spell_name == "ice_shard":
        visuals["color"] = (150, 200, 255)
        visuals["particles"] = 8
    elif spell_name == "lightning_bolt":
        visuals["color"] = (255, 255, 100)
        visuals["particles"] = 12
        visuals["flash_color"] = (255, 255, 200)
    elif spell_name == "earthquake":
        visuals["color"] = (140, 100, 60)
        visuals["particles"] = 25
        visuals["particle_spread"] = 4.0
    elif spell_name == "heal":
        visuals["color"] = (100, 255, 100)
        visuals["particles"] = 10
        visuals["flash_color"] = (200, 255, 200)
    elif spell_name == "smite_undead":
        visuals["color"] = (255, 255, 180)
        visuals["particles"] = 15
        visuals["flash_color"] = (255, 255, 220)
    elif spell_name == "magic_missile":
        visuals["color"] = (180, 130, 255)
        visuals["particles"] = 5
    elif spell_name == "shield":
        visuals["color"] = (130, 150, 255)
        visuals["particles"] = 6
        visuals["flash"] = False
    elif spell_name == "teleport":
        visuals["color"] = (200, 150, 255)
        visuals["particles"] = 15
        visuals["flash_color"] = (220, 200, 255)
    elif spell_name == "entangle":
        visuals["color"] = (60, 160, 40)
        visuals["particles"] = 12
    elif spell_name == "storm_call":
        visuals["color"] = (100, 100, 200)
        visuals["particles"] = 30
        visuals["particle_spread"] = 5.0
    elif spell_name == "soul_sight":
        visuals["color"] = (180, 180, 255)
        visuals["particles"] = 6
        visuals["flash"] = False
    elif spell_name == "exorcism":
        visuals["color"] = (255, 255, 200)
        visuals["particles"] = 20
        visuals["flash_color"] = (255, 255, 150)

    return visuals


# ================================================================
# ALCHEMY SUPPLY CHAIN ENTRIES
# (To be appended to supply_chains.SUPPLY_CHAINS at import time)
# ================================================================

ALCHEMY_SUPPLY_CHAIN_ADDITIONS = {
    "Mana Potion": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 2,
        "materials": {"Flowers": 3, "Mushrooms": 2},
        "time": 30,
        "output_count": 1,
    },
    "Strength Potion": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 3,
        "materials": {"Mushrooms": 3, "Raw Meat": 1, "Herbs": 1},
        "time": 40,
        "output_count": 1,
    },
    "Invisibility Potion": {
        "crafter": "Alchemist",
        "workstation": "alchemy",
        "skill": "alchemy",
        "skill_level": 5,
        "materials": {"Flowers": 4, "Mushrooms": 3, "Herbs": 2},
        "time": 60,
        "output_count": 1,
    },
}


def register_alchemy_supply_chains():
    """Inject alchemy recipes into the supply chain system.

    Safe to call multiple times; skips entries that already exist.
    """
    try:
        from game.data.supply_chains import SUPPLY_CHAINS
        for name, data in ALCHEMY_SUPPLY_CHAIN_ADDITIONS.items():
            if name not in SUPPLY_CHAINS:
                SUPPLY_CHAINS[name] = data
    except ImportError:
        pass


# ================================================================
# INTEGRATION HELPERS
# ================================================================

def integrate_magic_into_combat(damage: int, attacker, target) -> int:
    """Modify melee/ranged damage with enchantment bonuses and spell buffs.

    Called from CombatSystem to add magic modifiers to attacks.
    """
    # Attack buff from spells (bless, etc.)
    damage += get_attack_modifier(attacker)

    # Weapon enchantment bonus
    weapon = getattr(attacker, 'equipped_weapon', None)
    if weapon and hasattr(weapon, 'enchantment') and weapon.enchantment:
        ench = weapon.enchantment
        if ench.active:
            damage += ench.damage_bonus
            ench.use_charge()

    # Target defense buff from spells
    damage -= get_defense_modifier(target)

    # Shield absorption
    damage = absorb_damage(target, max(0, damage))

    # Armor enchantment resistance (not applied here -- applied per damage type)

    return max(1, damage)


def on_level_up(entity):
    """Recalculate mana on level up."""
    if hasattr(entity, 'mana'):
        scores = getattr(entity, 'ability_scores', {})
        intelligence = scores.get('intelligence', 10)
        level = getattr(entity, 'level', 1)
        old_max = entity.max_mana
        entity.max_mana = calc_max_mana(intelligence, level)
        # Restore the gained mana
        entity.mana += (entity.max_mana - old_max)
        entity.mana = min(entity.max_mana, entity.mana)
