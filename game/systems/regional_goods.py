"""Regional Goods System -- specialized goods, trade routes, and stockpiles.

Each settlement gets initial stockpiles based on:
1. Kingdom race (racial specialties and signature goods)
2. Settlement specialization (port, mining, lumber, etc.)
3. Historical trade routes (goods flowing between connected settlements)
4. Foreign contacts at ports and crossroads
5. Settlement size (population multiplier)
6. Ruin loot appropriate to the ruin's history

This module is called once at game initialization, after world_effects is
created, to replace the generic default stock with regionally appropriate
goods.
"""

import random
from typing import Dict, List, Optional


# ================================================================
# KINGDOM SPECIALTIES -- what each race produces and trades
# ================================================================

KINGDOM_SPECIALTIES: Dict[str, Dict[str, list]] = {
    "Human": {
        "produces": [
            "Wheat", "Bread", "Ale", "Wool Cloth", "Iron Sword",
            "Leather Armor", "Flour", "Vegetables", "Cheese",
        ],
        "signature": ["Fine Ale", "Embroidered Cloth"],
        "imports": ["Raw Ruby", "Spices", "Elven Wine"],
    },
    "Elf": {
        "produces": [
            "Elven Wine", "Enchanted Arrows", "Herbal Poultice",
            "Mooncloth", "Herbs", "Elven Cordial",
        ],
        "signature": ["Elven Wine", "Mooncloth", "Lembas Bread"],
        "imports": ["Iron Ore", "Dwarven Steel", "Wheat"],
    },
    "Dwarf": {
        "produces": [
            "Dwarven Steel", "Raw Ruby", "Stone", "Masterwork Weapon",
            "Iron Ingot", "Steel Ingot", "Pickaxe",
        ],
        "signature": ["Dwarven Steel", "Masterwork Armor", "Gem Jewelry"],
        "imports": ["Bread", "Wood", "Linen", "Ale"],
    },
    "Orc": {
        "produces": [
            "Bone Weapon", "Beast Hide", "War Drums", "Bone Tools",
            "Raw Meat", "Wolf Pelt",
        ],
        "signature": ["War Paint", "Trophy Skulls"],
        "imports": ["Iron Ore", "Bread"],
    },
    "Half-Orc": {  # alias for mixed settlements
        "produces": [
            "Bone Weapon", "Beast Hide", "Raw Meat", "Wolf Pelt",
            "Iron Sword",
        ],
        "signature": ["War Paint"],
        "imports": ["Iron Ore", "Bread", "Ale"],
    },
    "Goblin": {
        "produces": [
            "Crude Trap", "Poison Vial", "Scrap Metal", "Mushroom Brew",
            "Mushrooms",
        ],
        "signature": ["Goblin Fire", "Sneaky Lockpicks"],
        "imports": ["Iron Sword", "Bread"],
    },
    "Undead": {
        "produces": [
            "Bone Weapon", "Cursed Artifact", "Soul Gem", "Dark Tome",
        ],
        "signature": ["Phylactery Shard", "Death Shroud"],
        "imports": [],
    },
}


# ================================================================
# SPECIALIZATION GOODS -- what each settlement type produces
# ================================================================

SPECIALIZATION_GOODS: Dict[str, Dict] = {
    "port": {
        "produces": ["Fish", "Salt", "Rope", "Boat Hull"],
        "bonus": "trade_hub",
    },
    "mining": {
        "produces": ["Iron Ore", "Copper Ore", "Raw Ruby", "Stone"],
        "bonus": "raw_materials",
    },
    "lumber": {
        "produces": ["Wood", "Planks", "Barrel", "Torch"],
        "bonus": "construction",
    },
    "agricultural": {
        "produces": ["Wheat", "Flour", "Bread", "Vegetables", "Eggs"],
        "bonus": "food",
    },
    "crossroads": {
        "produces": [],
        "bonus": "trade_variety",
    },
    "fishing": {
        "produces": ["Fish", "Salted Fish", "Pearls", "Rope"],
        "bonus": "food",
    },
    "oasis": {
        "produces": ["Spices", "Salt", "Honey"],
        "bonus": "exotic",
    },
    "swamp": {
        "produces": ["Herbs", "Mushrooms", "Herbal Poultice"],
        "bonus": "alchemy",
    },
    "border": {
        "produces": ["Iron Sword", "Arrows", "Leather Armor"],
        "bonus": "military",
    },
    "capital": {
        "produces": ["Silk", "Wine", "Gold Ring", "Book"],
        "bonus": "luxury",
    },
    "general": {
        "produces": ["Bread", "Wood", "Stone"],
        "bonus": "mixed",
    },
}


# ================================================================
# RACIAL SKILL BONUSES -- applied on top of existing NPC skills
# ================================================================

RACIAL_SKILL_BONUSES: Dict[str, Dict[str, int]] = {
    "Elf": {
        "archery": 2, "herbalism": 2, "enchanting": 1, "nature_lore": 2,
    },
    "Half-Elf": {
        "archery": 1, "herbalism": 1, "enchanting": 1, "persuasion": 1,
    },
    "Dwarf": {
        "smithing": 3, "mining": 2, "stonecraft": 2,
    },
    "Half-Orc": {
        "unarmed": 2, "intimidation": 2, "hunting": 1,
    },
    "Halfling": {
        "stealth": 2, "cooking": 2, "farming": 1,
    },
    "Gnome": {
        "alchemy": 2, "enchanting": 1, "jeweling": 1,
    },
    "Human": {
        "farming": 1, "persuasion": 1, "literacy": 1,
    },
    "Tiefling": {
        "intimidation": 1, "alchemy": 1, "enchanting": 1,
    },
}

# Specialization skill bonuses -- NPCs in specialized settlements
# get a small boost to relevant skills
SPECIALIZATION_SKILL_BONUSES: Dict[str, Dict[str, int]] = {
    "port": {"sailing": 2, "fishing": 1, "navigation": 1},
    "mining": {"mining": 2, "smithing": 1, "stonecraft": 1},
    "lumber": {"woodcraft": 2, "carpentry": 1},
    "agricultural": {"farming": 2, "cooking": 1, "beekeeping": 1},
    "crossroads": {"persuasion": 1, "literacy": 1, "cartography": 1},
    "fishing": {"fishing": 2, "sailing": 1},
    "oasis": {"navigation": 1, "persuasion": 1},
    "swamp": {"herbalism": 2, "alchemy": 1},
    "border": {"combat": 1, "smithing": 1, "intimidation": 1},
    "capital": {"literacy": 2, "persuasion": 1, "enchanting": 1},
}


# ================================================================
# RUIN LOOT TABLES -- era-appropriate items for historical ruins
# ================================================================

RUIN_LOOT_TABLES: Dict[str, List[List]] = {
    # Each entry: list of (item_name, min_qty, max_qty) tuples
    "abandoned_castle": [
        ("Iron Sword", 1, 2), ("Chain Mail", 0, 1), ("Gold Coins", 3, 15),
        ("Arrows", 2, 8), ("Iron Shield", 0, 1), ("Health Potion", 0, 2),
        ("Torch", 1, 3),
    ],
    "ruined_tower": [
        ("Spellbook", 0, 1), ("Health Potion", 1, 3), ("Scroll of Healing", 0, 2),
        ("Scroll of Fire", 0, 1), ("Herbs", 2, 5), ("Candle", 1, 4),
        ("Ink", 0, 2), ("Book", 0, 2),
    ],
    "abandoned_mine": [
        ("Iron Ore", 3, 10), ("Copper Ore", 2, 6), ("Pickaxe", 0, 2),
        ("Raw Ruby", 0, 1), ("Raw Emerald", 0, 1), ("Stone", 3, 8),
        ("Torch", 2, 5), ("Gold Nugget", 0, 2),
    ],
    "dragon_lair": [
        ("Gold Coins", 10, 50), ("Raw Diamond", 0, 2), ("Raw Ruby", 1, 3),
        ("Masterwork Weapon", 0, 1), ("Enchanted Arrows", 0, 1),
        ("Gem Jewelry", 0, 1), ("Enchanted Ring", 0, 1),
        ("Plate Armor", 0, 1),
    ],
    "ancient_temple": [
        ("Holy Water", 1, 3), ("Health Potion", 1, 4), ("Ancient Relic", 0, 1),
        ("Scroll of Ward", 0, 2), ("Scroll of Healing", 1, 2),
        ("Candle", 2, 6), ("Incense", 1, 3), ("Gold Ring", 0, 1),
    ],
    "ancient_ruins": [
        ("Stone", 2, 6), ("Iron Sword", 0, 1), ("Gold Coins", 1, 8),
        ("Ancient Relic", 0, 1), ("Torch", 1, 3), ("Health Potion", 0, 2),
    ],
    "old_dungeon": [
        ("Iron Chain", 1, 3), ("Lockpick", 1, 4), ("Gold Coins", 2, 10),
        ("Poison Vial", 0, 2), ("Torch", 2, 5), ("Health Potion", 0, 2),
        ("Iron Sword", 0, 1), ("Thieves' Tools", 0, 1),
    ],
    "hermit_cave": [
        ("Herbs", 3, 8), ("Healing Salve", 1, 3), ("Mushrooms", 2, 5),
        ("Health Potion", 0, 2), ("Book", 0, 1), ("Journal", 0, 1),
        ("Spellbook", 0, 1),
    ],
    "watchtower": [
        ("Arrows", 3, 10), ("Iron Sword", 0, 1), ("Hunting Bow", 0, 1),
        ("Bread", 0, 3), ("Torch", 1, 4), ("Rope", 1, 2),
        ("Map", 0, 1),
    ],
    "ruins": [
        ("Stone", 1, 4), ("Wood", 1, 3), ("Gold Coins", 0, 5),
        ("Torch", 0, 2), ("Health Potion", 0, 1),
    ],
}

# Race-specific bonus loot for ruins from that race's settlements
RACE_RUIN_BONUSES: Dict[str, List] = {
    "Elf": [("Elven Wine", 0, 2), ("Enchanted Arrows", 0, 1), ("Mooncloth", 0, 1)],
    "Dwarf": [("Dwarven Steel", 0, 1), ("Gem Jewelry", 0, 1), ("Raw Ruby", 0, 2)],
    "Orc": [("Bone Weapon", 0, 2), ("War Paint", 0, 1), ("Beast Hide", 1, 3)],
    "Goblin": [("Goblin Fire", 0, 2), ("Crude Trap", 1, 3), ("Mushroom Brew", 0, 2)],
    "Undead": [("Soul Gem", 0, 1), ("Dark Tome", 0, 1), ("Cursed Artifact", 0, 1)],
}


# ================================================================
# HELPERS
# ================================================================

def _find_kingdom_for_settlement(settlement_name: str,
                                  kingdoms: list) -> Optional[Dict]:
    """Find the kingdom dict that contains the given settlement."""
    for k in kingdoms:
        if settlement_name in k.get("territory_settlements", []):
            return k
        if settlement_name == k.get("capital_settlement"):
            return k
    return None


# ================================================================
# A. INITIALIZE SETTLEMENT STOCKPILES
# ================================================================

def initialize_settlement_stockpiles(plan, world_effects):
    """Set up initial goods in each settlement based on its history and role.

    Called once at game start, after world_effects is created. Replaces the
    generic default stock with regionally appropriate goods.

    Parameters
    ----------
    plan : WorldPlan
        The world plan containing settlements, kingdoms, trade routes.
    world_effects : WorldEffects
        The world effects system with settlement storage.
    """
    kingdoms = getattr(plan, 'kingdoms', [])
    trade_routes = getattr(plan, '_history_trade_routes', [])
    foreign_contacts = getattr(plan, 'foreign_contacts', [])

    for sp in plan.settlements:
        stores = world_effects.get_stores_ref(sp.name)

        # --- Base goods from specialization ---
        spec_goods = SPECIALIZATION_GOODS.get(sp.specialization, {})
        for good in spec_goods.get("produces", []):
            current = stores.get(good, 0)
            stores[good] = current + random.randint(10, 30)

        # --- Kingdom-specific goods ---
        kingdom = _find_kingdom_for_settlement(sp.name, kingdoms)
        race = sp.race if hasattr(sp, 'race') else "Human"
        if kingdom:
            race = kingdom.get("race", race)

        kingdom_goods = KINGDOM_SPECIALTIES.get(race, {})
        for good in kingdom_goods.get("produces", []):
            current = stores.get(good, 0)
            stores[good] = current + random.randint(5, 15)
        # Signature goods (smaller quantity, higher value)
        for good in kingdom_goods.get("signature", []):
            current = stores.get(good, 0)
            stores[good] = current + random.randint(1, 5)

        # --- Trade route imports ---
        for route in trade_routes:
            route_from = route.get("from", "")
            route_to = route.get("to", "")
            if sp.name in (route_from, route_to):
                other = route_to if route_from == sp.name else route_from
                other_kingdom = _find_kingdom_for_settlement(other, kingdoms)
                if other_kingdom:
                    other_race = other_kingdom.get("race", "Human")
                    other_goods = KINGDOM_SPECIALTIES.get(other_race, {})
                    for good in other_goods.get("signature", [])[:2]:
                        current = stores.get(good, 0)
                        stores[good] = current + random.randint(1, 3)

        # --- Foreign trade goods at port towns and crossroads ---
        if sp.specialization in ("port", "crossroads"):
            for fg in foreign_contacts:
                for good in fg.get("trade_goods", [])[:2]:
                    current = stores.get(good, 0)
                    stores[good] = current + random.randint(1, 5)

        # --- Settlement size multiplier ---
        pop_mult = {
            "city": 3.0, "town": 2.0, "village": 1.0,
            "hamlet": 0.5, "castle": 2.5,
        }.get(sp.kind, 1.0)

        for good in list(stores.keys()):
            if good != "gold":
                val = stores.get(good, 0)
                if val > 0:
                    stores[good] = max(1, int(val * pop_mult))

        # --- Gold from kingdom treasury ---
        if kingdom:
            treasury = kingdom.get("treasury", 0)
            territory = kingdom.get("territory_settlements", [])
            n_settlements = max(1, len(territory))
            gold_share = treasury // n_settlements
            # Capital gets double share
            if sp.name == kingdom.get("capital_settlement"):
                gold_share *= 2
            current_gold = stores.get("gold", 0)
            stores["gold"] = current_gold + gold_share


# ================================================================
# B. INITIALIZE TRADE ROUTES FROM HISTORY
# ================================================================

def initialize_trade_routes(plan, trade_system, world_effects):
    """Set up initial trade routes from historical trade connections.

    Converts history sim trade routes into active TradeSystem routes,
    and sets up foreign trade routes at port settlements.

    Parameters
    ----------
    plan : WorldPlan
        The world plan with _history_trade_routes and settlements.
    trade_system : TradeSystem
        The active trade system to add routes to.
    world_effects : WorldEffects
        For reading settlement stores to determine trade goods.
    """
    history_routes = getattr(plan, '_history_trade_routes', [])

    for route in history_routes:
        from_name = route.get("from", "")
        to_name = route.get("to", "")

        # Find matching settlements
        from_sp = None
        to_sp = None
        for sp in plan.settlements:
            if sp.name == from_name:
                from_sp = sp
            elif sp.name == to_name:
                to_sp = sp

        if from_sp and to_sp:
            # Add the route if not already present
            route_pair = (from_name, to_name)
            reverse_pair = (to_name, from_name)
            if (route_pair not in trade_system.trade_routes and
                    reverse_pair not in trade_system.trade_routes):
                trade_system.trade_routes.append(route_pair)

    # Also set up foreign trade routes at ports
    foreign_contacts = getattr(plan, 'foreign_contacts', [])
    ports = [sp for sp in plan.settlements
             if sp.specialization in ("port",) and sp.kind in ("town", "city")]

    # Register foreign contacts as route metadata (for caravan spawning)
    for port in ports[:3]:
        for contact in foreign_contacts:
            contact_name = contact.get("name", "Unknown Land")
            trade_goods = contact.get("trade_goods", [])
            # Store as special foreign route metadata on trade system
            if not hasattr(trade_system, 'foreign_routes'):
                trade_system.foreign_routes = []
            trade_system.foreign_routes.append({
                "port": port.name,
                "foreign_contact": contact_name,
                "trade_goods": trade_goods,
            })


# ================================================================
# C. ASSIGN REGIONAL SKILLS TO NPCs
# ================================================================

def assign_regional_skills(npc, settlement_plan, kingdom):
    """Give NPCs skill bonuses appropriate for their settlement's specialization
    and their kingdom's race.

    Called once per NPC at game init, after normal skill initialization.

    Parameters
    ----------
    npc : NPC
        The NPC to augment.
    settlement_plan : SettlementPlan or None
        The settlement the NPC lives in.
    kingdom : dict or None
        The kingdom dict the NPC belongs to.
    """
    if not hasattr(npc, 'npc_skills'):
        npc.npc_skills = {}

    # --- Racial skill bonuses ---
    race = getattr(npc, 'race', 'Human')
    for skill, bonus in RACIAL_SKILL_BONUSES.get(race, {}).items():
        current = npc.npc_skills.get(skill, 0)
        npc.npc_skills[skill] = current + bonus

    # --- Specialization skill bonuses ---
    if settlement_plan:
        spec = getattr(settlement_plan, 'specialization', 'general')
        for skill, bonus in SPECIALIZATION_SKILL_BONUSES.get(spec, {}).items():
            current = npc.npc_skills.get(skill, 0)
            npc.npc_skills[skill] = current + bonus


def assign_regional_skills_to_npcs(npcs, plan):
    """Batch-apply regional skills to all NPCs.

    Parameters
    ----------
    npcs : list of NPC
        All NPCs in the world.
    plan : WorldPlan
        The world plan (for settlements and kingdoms).
    """
    # Build a lookup: settlement_name -> SettlementPlan
    settlement_map = {sp.name: sp for sp in plan.settlements}
    kingdoms = getattr(plan, 'kingdoms', [])

    for npc in npcs:
        # Find the NPC's settlement
        home_settlement = None
        npc_home_x = getattr(npc, 'home_x', npc.x)
        npc_home_y = getattr(npc, 'home_y', npc.y)

        # Try matching by name in npc_roster or by proximity
        best_dist = float('inf')
        for sp in plan.settlements:
            dx = sp.x - npc_home_x
            dy = sp.y - npc_home_y
            dist = dx * dx + dy * dy
            if dist < best_dist:
                best_dist = dist
                home_settlement = sp

        kingdom = None
        if home_settlement:
            kingdom = _find_kingdom_for_settlement(
                home_settlement.name, kingdoms)

        assign_regional_skills(npc, home_settlement, kingdom)


# ================================================================
# D. POPULATE RUIN LOOT
# ================================================================

def populate_ruin_loot(ruin, rng=None):
    """Generate loot items for a ruin based on its type and history.

    Parameters
    ----------
    ruin : RuinPlan or similar
        Must have ruin_type attribute. May have race attribute.
    rng : random.Random, optional
        RNG instance for deterministic generation.

    Returns
    -------
    list of (str, int)
        List of (item_name, quantity) tuples.
    """
    if rng is None:
        rng = random.Random()

    ruin_type = getattr(ruin, 'ruin_type', 'ruins')
    race = getattr(ruin, 'race', '')

    loot_table = RUIN_LOOT_TABLES.get(ruin_type, RUIN_LOOT_TABLES["ruins"])
    items = []

    for item_name, min_qty, max_qty in loot_table:
        qty = rng.randint(min_qty, max_qty)
        if qty > 0:
            items.append((item_name, qty))

    # Race-specific bonus loot
    if race in RACE_RUIN_BONUSES:
        for item_name, min_qty, max_qty in RACE_RUIN_BONUSES[race]:
            qty = rng.randint(min_qty, max_qty)
            if qty > 0:
                items.append((item_name, qty))

    return items


def initialize_ruin_stockpiles(plan, world_effects):
    """Place loot in ruins based on their historical type and race.

    Ruins are stored in plan._history_ruins as RuinPlan objects and in
    plan.special_locations as SpecialLocation objects. We populate loot
    into the world_effects storage for any ruin that has a name.

    Parameters
    ----------
    plan : WorldPlan
        The world plan with _history_ruins and special_locations.
    world_effects : WorldEffects
        For depositing loot into ruin storage.
    """
    seed = getattr(plan, 'seed', 42)
    rng = random.Random(seed + 7777)

    history_ruins = getattr(plan, '_history_ruins', [])

    for ruin in history_ruins:
        name = getattr(ruin, 'name', '')
        if not name:
            continue

        loot = populate_ruin_loot(ruin, rng)
        if not loot:
            continue

        # Deposit loot into a storage location for this ruin
        stores = world_effects.get_stores_ref(name)
        for item_name, qty in loot:
            current = stores.get(item_name, 0)
            stores[item_name] = current + qty


# ================================================================
# E. MASTER INITIALIZATION -- call from simulation.py
# ================================================================

def initialize_regional_goods(plan, world_effects, trade_system, npcs):
    """One-call initialization of the entire regional goods system.

    Convenience function that calls all sub-initializers in order.

    Parameters
    ----------
    plan : WorldPlan
        The world plan.
    world_effects : WorldEffects
        The world effects system.
    trade_system : TradeSystem
        The active trade system.
    npcs : list of NPC
        All NPCs in the world.
    """
    initialize_settlement_stockpiles(plan, world_effects)
    initialize_trade_routes(plan, trade_system, world_effects)
    initialize_ruin_stockpiles(plan, world_effects)
    assign_regional_skills_to_npcs(npcs, plan)
