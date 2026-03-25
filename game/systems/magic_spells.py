"""Magic spell definitions, registries, schools, and equipment data.

Contains:
- MAGIC_SCHOOLS: 8 schools of magic with spell lists and colors
- CLASS_SCHOOL_AFFINITY: D&D class -> primary magic school mapping
- PRACTITIONER_SPELLS: class -> allowed schools and max spell level
- Spell class: data class for castable spells
- SPELL_REGISTRY: all 102 spells across 8 schools
- SOUL_SPELLS: rare soul magic spells
- SPELL_COMPONENTS: required materials for high-level spells
- MAGIC_ITEMS: magic equipment definitions
"""

from typing import List, Dict


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
# SOUL MAGIC (rare high-level spells)
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
