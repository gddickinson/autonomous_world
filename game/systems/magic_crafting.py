"""Magic crafting: enchanting, alchemy, combat integration, visuals, supply chains.

Contains:
- Enchanting system: weapon/armor enchantments with reagents and charges
- Alchemy system: potion brewing with ingredients
- Potion usage: mana potion, strength potion, invisibility potion
- Combat integration: integrate_magic_into_combat
- Spell visual helpers: get_spell_visual for rendering
- Supply chain registration for alchemy products
- on_level_up: mana recalculation on level up
"""

from typing import Tuple, Dict, Any

from game.settings import *
from game.systems.magic_spells import (
    SPELL_REGISTRY, SOUL_SPELLS, MAGIC_SCHOOLS,
)
from game.systems.magic_effects import (
    SpellEffect, init_mana, get_attack_modifier,
    get_defense_modifier, absorb_damage, calc_max_mana,
)


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
