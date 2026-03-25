"""Magic system: thin coordinator that re-exports from sub-modules.

Sub-modules:
- magic_spells: Spell class, SPELL_REGISTRY, SOUL_SPELLS, schools, equipment
- magic_effects: SpellEffect, mana, spell learning/casting, status effects
- magic_crafting: enchanting, alchemy, combat integration, visuals, supply chains
- magic_ai: NPC spell selection AI

All public names are re-exported here for backward compatibility.
Existing code can continue to use `from game.systems.magic import X`.
"""

# --- Spell definitions, registries, schools, equipment ---
from game.systems.magic_spells import (  # noqa: F401
    MAGIC_SCHOOLS,
    CLASS_SCHOOL_AFFINITY,
    PRACTITIONER_SPELLS,
    Spell,
    SPELL_REGISTRY,
    SOUL_SPELLS,
    SPELL_COMPONENTS,
    MAGIC_ITEMS,
)

# --- Spell effects, mana, casting, status helpers ---
from game.systems.magic_effects import (  # noqa: F401
    SpellEffect,
    MANA_REGEN_BASE,
    MANA_REGEN_RESTING,
    MANA_REGEN_TEMPLE,
    calc_max_mana,
    get_mana_regen_rate,
    init_mana,
    can_learn_spell,
    learn_spell,
    auto_learn_spells_for_class,
    can_cast,
    cast_spell,
    update_magic,
    get_speed_modifier,
    get_attack_modifier,
    get_defense_modifier,
    absorb_damage,
    has_effect,
)

# --- Enchanting, alchemy, combat integration, visuals ---
from game.systems.magic_crafting import (  # noqa: F401
    ENCHANTMENT_TYPES,
    ENCHANTMENT_RESISTANCES,
    ENCHANT_REAGENTS,
    RESIST_ENCHANT_REAGENTS,
    Enchantment,
    can_enchant_weapon,
    enchant_weapon,
    can_enchant_armor,
    enchant_armor,
    ALCHEMY_RECIPES,
    can_brew_potion,
    brew_potion,
    use_mana_potion,
    use_strength_potion,
    use_invisibility_potion,
    get_spell_visual,
    ALCHEMY_SUPPLY_CHAIN_ADDITIONS,
    register_alchemy_supply_chains,
    integrate_magic_into_combat,
    on_level_up,
)

# --- NPC magic AI ---
from game.systems.magic_ai import (  # noqa: F401
    npc_choose_spell,
    npc_cast_spell,
)
