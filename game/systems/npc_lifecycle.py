"""
NPC Lifecycle System — connects economics, careers, social life, and daily routines.

This is the integration layer that wires together:
- Economy: work → income → spending → saving
- Career: promotion, demotion, hiring, firing, conscription
- Social: relationships → marriage → family → housing
- Daily routine: wake → work → eat → socialize → sleep
- Consequences: debt, crime, drunkenness, dismissal, war

Runs per-tick for active NPCs and periodically (daily) for dormant NPCs.
"""

import random
import math
from typing import Dict, List, Optional


# ================================================================
# WORK INCOME — what each class earns per game-day while working
# ================================================================

# Gold per game-day by class/profession (scales with level)
CLASS_DAILY_WAGE = {
    # D&D classes
    "Fighter": 2.0, "Wizard": 3.0, "Cleric": 2.5, "Rogue": 3.0,
    "Ranger": 2.0, "Paladin": 2.5, "Barbarian": 1.5, "Bard": 3.5,
    "Druid": 2.0, "Monk": 1.0, "Sorcerer": 3.0, "Warlock": 2.5,
    # Original professions
    "Farmer": 1.5, "Blacksmith": 3.0, "Merchant": 4.0, "Healer": 2.5,
    "Scholar": 2.0, "Innkeeper": 3.5, "Miner": 2.0, "Fisher": 1.5,
    # Primary Production
    "Fisherman": 1.5, "Hunter": 2.0, "Herbalist": 1.5, "Woodcutter": 1.5,
    "Shepherd": 1.5, "Beekeeper": 1.5, "Prospector": 2.0,
    # Crafting/Manufacturing
    "Armourer": 3.5, "Carpenter": 2.5, "Cooper": 2.0, "Wheelwright": 2.5,
    "Shipbuilder": 3.0, "Tanner": 2.0, "Weaver": 2.0, "Potter": 2.0,
    "Baker": 2.0, "Brewer": 2.5, "Alchemist": 3.5,
    # Services
    "Cook": 1.5, "Servant": 1.0, "Shop Assistant": 1.5, "Banker": 4.0,
    "Barber": 2.0,
    # Administrative/Leadership
    "Captain": 4.0, "Tax Collector": 3.0, "Steward": 3.5, "Scribe": 2.5,
    "Diplomat": 4.0, "Advisor": 3.5,
    # Skilled/Professional
    "Mason": 2.5, "Animal Trainer": 2.5, "Stablemaster": 2.0,
    "Cartographer": 3.0,
    # Construction/Labor
    "Builder": 2.0, "Cleaner": 1.0, "Gravedigger": 1.5, "Porter": 1.5,
    "Laborer": 1.0,
}

# Title pay bonus (per game-day, on top of class wage)
TITLE_PAY = {
    "monarch": 20.0, "duke": 10.0, "lord": 6.0, "knight": 4.0,
    "captain": 5.0, "sergeant": 3.0, "guard": 2.0, "servant": 0.5,
    "high_priest": 8.0, "clergy": 3.0, "senator": 8.0,
    "patrician": 6.0, "merchant": 4.0, "commoner": 0.0,
    "serf": 0.2, "slave": 0.0, "enforcer": 3.0,
    # Command hierarchy titles
    "steward": 5.0, "elder": 7.0, "mayor": 6.0, "chief": 5.0,
}

# Work actions that earn gold (maps current_action → income multiplier)
PRODUCTIVE_ACTIONS = {
    "working": 1.0, "farming": 0.8, "mining": 1.2, "chopping": 0.7,
    "fishing": 0.6, "foraging": 0.4, "smithing": 1.5, "trading": 1.3,
    "cooking": 0.5, "performing": 1.8, "researching": 0.8,
    "healing": 1.0, "guarding": 0.8, "training": 0.3,
    "crafting": 1.2, "building": 0.9,
    # Schedule-driven actions (set by _execute_action from schedule system)
    "praying": 0.6, "ritual": 0.7, "enchanting": 1.3,
    "crafting_pottery": 1.0, "crafting_glass": 1.1, "tanning": 0.9,
    "dyeing": 0.9, "training_animal": 0.7,
    # Work behavior actions (set by npc_work system)
    "commuting": 0.2, "carrying": 0.5, "hunting": 0.9,
    # New occupation work actions
    "baking": 0.8, "brewing": 0.9, "alchemy": 1.3,
    "carpentry": 1.0, "coopering": 0.9, "weaving": 0.8,
    "herding": 0.6, "beekeeping": 0.5, "prospecting": 0.8,
    "masonry": 1.0, "shipbuilding": 1.2,
    "innkeeping": 0.9, "cleaning": 0.3, "barbering": 0.7,
    "accounting": 1.0, "collecting": 0.9, "administering": 0.8,
    "writing": 0.7, "mapping": 0.9, "negotiating": 1.0,
    "advising": 0.9, "commanding": 1.0, "digging": 0.5,
    # Command-system actions (hierarchical orders from superiors)
    "escorting": 1.0, "waiting_materials": 0.1,
    # Idle/moving NPCs during work hours get subsistence rate (handled in code)
}

# ================================================================
# DAILY COSTS — what NPCs spend
# ================================================================

DAILY_COSTS = {
    "food": 0.3,      # basic food
    "rent": 0.2,      # housing (serfs/slaves pay 0)
    "upkeep": 0.1,    # clothing, tools
}

# Title-based cost multiplier (nobles spend more)
TITLE_COST_MULT = {
    "monarch": 5.0, "duke": 3.0, "lord": 2.5, "knight": 2.0,
    "captain": 1.5, "sergeant": 1.2, "guard": 1.0, "servant": 0.5,
    "commoner": 1.0, "serf": 0.3, "slave": 0.0,
    # Command hierarchy titles
    "steward": 2.0, "elder": 2.5, "mayor": 2.5, "chief": 2.0,
}

# ================================================================
# CAREER ADVANCEMENT
# ================================================================

# Requirements for NPC promotion (checked daily)
NPC_PROMOTION_PATHS = {
    # (current_title, new_title): requirements
    ("commoner", "guard"):    {"level": 2, "bravery": 0.4, "char_class": ("Fighter", "Ranger", "Paladin", "Barbarian")},
    ("guard", "sergeant"):    {"level": 3, "kills": 3, "days_in_role": 30},
    ("sergeant", "captain"):  {"level": 5, "kills": 10, "days_in_role": 60},
    ("captain", "knight"):    {"level": 7, "kills": 20, "gold": 100, "days_in_role": 90},
    ("knight", "lord"):       {"level": 9, "gold": 500, "days_in_role": 180},
    ("commoner", "clergy"):   {"char_class": ("Cleric", "Paladin", "Monk"), "level": 2},
    ("clergy", "high_priest"):{"level": 8, "days_in_role": 120},
    ("commoner", "servant"):  {"gold_below": 1},  # truly destitute become servants
    ("servant", "commoner"):  {"gold": 15},  # earn enough to be free
    # Command hierarchy promotions
    ("commoner", "steward"):  {"level": 4, "gold": 50, "days_in_role": 60,
                                "char_class": ("Wizard", "Cleric", "Bard", "Rogue",
                                               "Monk", "Druid", "Sorcerer", "Warlock")},
    ("lord", "elder"):        {"level": 10, "gold": 200, "days_in_role": 120},
}

# ================================================================
# SOCIAL EVENTS
# ================================================================

# Probability per game-day of social events happening
SOCIAL_EVENT_CHANCES = {
    "get_drunk":      0.03,   # per tavern visit
    "start_courtship":0.02,   # per social interaction (raised from 0.005)
    "propose_marriage":0.01,  # per day if courting (raised from 0.002)
    "have_child":     0.005,  # per day if married (raised from 0.001)
    "get_in_fight":   0.01,   # per social interaction with enemy
    "commit_crime":   0.003,  # per day if desperate (gold < 2)
    "get_fired":      0.005,  # per day if drunk or missing work
}


# ================================================================
# NPC LIFECYCLE SYSTEM
# ================================================================

class NpcLifecycle:
    """Manages the complete NPC economic and social lifecycle."""

    def __init__(self):
        self._daily_timer = 0.0
        self._hourly_timer = 0.0
        self.event_log: List[str] = []

    def update(self, dt: float, npcs: list, time_sys, world=None,
               governance=None, economy=None, world_effects=None):
        """Main update — called every simulation tick.

        Handles:
        - Per-tick: work income for active NPCs (paid from settlement gold)
        - Hourly: spending (gold flows to settlement), social events
        - Daily: career advancement, taxes, treasury redistribution
        """
        time_norm = getattr(time_sys, 'normalized', 0.3)
        day = getattr(time_sys, 'day', 1)
        time_speed = getattr(time_sys, 'speed', 1.0)
        scaled_dt = dt * time_speed  # account for time speed multiplier
        game_day_fraction = scaled_dt / 600.0  # DAY_LENGTH = 600s

        # Per-tick: work income (paid from settlement treasury)
        # Throttle: run every 3rd tick for performance
        if not hasattr(self, '_income_tick'):
            self._income_tick = 0
        self._income_tick += 1
        if self._income_tick % 3 == 0:
            adj_fraction = game_day_fraction * 3  # compensate for skipped ticks
            for npc in npcs:
                if not getattr(npc, 'alive', True):
                    continue
                self._tick_income(npc, adj_fraction, time_norm,
                                  world, world_effects)

        # Hourly checks (every ~25 game seconds = 1 game hour)
        self._hourly_timer += scaled_dt
        if self._hourly_timer >= 25.0:
            self._hourly_timer = 0.0
            for npc in npcs:
                if not getattr(npc, 'alive', True):
                    continue
                self._hourly_update(npc, time_norm, day, economy,
                                    world, world_effects)

        # Daily checks (every 600 game seconds = 1 game day)
        self._daily_timer += scaled_dt
        if self._daily_timer >= 600.0:
            self._daily_timer = 0.0

            # --- Treasury redistribution: kingdoms fund settlements ---
            if governance and world_effects:
                self._redistribute_treasury(governance, world_effects)

            for npc in npcs:
                if not getattr(npc, 'alive', True):
                    continue
                self._daily_update(npc, day, governance, npcs,
                                   world, world_effects)

    @staticmethod
    def _get_npc_settlement(npc, world):
        """Find the settlement name an NPC belongs to (home or current location)."""
        # Prefer home settlement if known
        home_settlement = getattr(npc, 'home_settlement', None)
        if home_settlement:
            return home_settlement
        # Fall back to faction (often the kingdom/settlement name)
        faction = getattr(npc, 'faction', None)
        if faction:
            return faction
        # Last resort: look up nearest structure
        if world and hasattr(world, 'get_structure_at'):
            s = world.get_structure_at(npc.x, npc.y)
            if s:
                return s.name
        return None

    def _tick_income(self, npc, day_fraction: float, time_norm: float,
                     world=None, world_effects=None):
        """Pay NPCs for productive work — gold flows FROM settlement stores.

        Farmers/miners produce goods that go into settlement stores and get
        paid from the settlement's gold reserves.  Guards/soldiers are paid
        from treasury.  If the settlement is broke, the NPC earns nothing.
        """
        # Only earn during work hours
        if not (0.28 < time_norm < 0.68):
            return

        action = getattr(npc, 'current_action', '')

        # Check if action is productive
        mult = PRODUCTIVE_ACTIONS.get(action, 0.0)
        if mult <= 0:
            state = getattr(npc, 'state', '')
            if state not in ('sleeping', 'fleeing', 'fighting'):
                mult = 0.3  # subsistence for being present during work hours
            else:
                return

        # Use profession wage first, fall back to char_class
        profession = getattr(npc, 'profession', '')
        char_class = getattr(npc, 'char_class', 'Fighter')
        level = getattr(npc, 'level', 1)
        base_wage = CLASS_DAILY_WAGE.get(profession, CLASS_DAILY_WAGE.get(char_class, 1.5))

        # Level scales income (level 5 earns 50% more than level 1)
        level_mult = 1.0 + (level - 1) * 0.1

        # Skill bonus: relevant skill adds up to 30% more
        skill_bonus = 0.0
        skills = getattr(npc, 'npc_skills', getattr(npc, 'skills', {}))
        _action_skill_map = {
            "smithing": ("smithing", 0.03),
            "farming": ("farming", 0.03),
            "mining": ("mining", 0.03),
            "performing": ("performance", 0.04),
            "healing": ("medicine", 0.03),
            "trading": ("persuasion", 0.03),
            "guarding": ("swordsmanship", 0.02),
            "fishing": ("fishing", 0.03),
            "chopping": ("woodcraft", 0.03),
            "foraging": ("herbalism", 0.03),
            "hunting": ("hunting", 0.03),
            "cooking": ("cooking", 0.03),
            "baking": ("cooking", 0.03),
            "brewing": ("brewing", 0.03),
            "alchemy": ("alchemy", 0.03),
            "carpentry": ("woodcraft", 0.03),
            "tanning": ("tanning", 0.03),
            "weaving": ("weaving", 0.03),
            "crafting_pottery": ("pottery", 0.03),
            "masonry": ("masonry", 0.03),
            "herding": ("animal_care", 0.03),
            "training_animal": ("animal_training", 0.03),
            "commanding": ("leadership", 0.03),
            "accounting": ("accountancy", 0.03),
            "writing": ("literacy", 0.02),
            "mapping": ("cartography", 0.03),
            "negotiating": ("persuasion", 0.03),
            "building": ("masonry", 0.02),
            "shipbuilding": ("shipbuilding", 0.03),
        }
        if action in _action_skill_map:
            sk, mult = _action_skill_map[action]
            skill_bonus = skills.get(sk, 0) * mult

        daily_income = base_wage * mult * level_mult * (1.0 + skill_bonus)

        # Title pay bonus
        title = getattr(npc, 'title', 'commoner')
        daily_income += TITLE_PAY.get(title, 0.0)

        # Convert to per-tick payment (work period = 40% of day = 240 seconds)
        tick_income = daily_income * day_fraction

        # === REAL ECONOMY: gold comes from settlement stores ===
        settlement = self._get_npc_settlement(npc, world)
        stores = None
        if settlement and world_effects and hasattr(world_effects, 'get_stores_ref'):
            stores = world_effects.get_stores_ref(settlement)

        if stores is not None:
            # Productive actions also contribute goods to settlement
            # (This is the per-tick trickle; the bulk comes from PROFESSION_PRODUCTION
            #  in npc_work.py when a full work cycle completes.)
            if action == "farming":
                stores["food"] = stores.get("food", 0) + day_fraction * 2
            elif action == "mining":
                stores["ore"] = stores.get("ore", 0) + day_fraction * 1.5
                # Ore can be converted to gold at market rate (1 ore ~ 2-3 gold)
                if stores.get("ore", 0) >= 5:
                    converted = min(2, stores["ore"] // 5)
                    stores["ore"] -= converted * 5
                    stores["gold"] = stores.get("gold", 0) + converted * 12
            elif action == "chopping":
                stores["wood"] = stores.get("wood", 0) + day_fraction * 1.5
            elif action in ("smithing", "crafting"):
                stores["weapons"] = stores.get("weapons", 0) + day_fraction * 0.3
                stores["tools"] = stores.get("tools", 0) + day_fraction * 0.3
            elif action == "fishing":
                stores["food"] = stores.get("food", 0) + day_fraction * 1.0
            elif action == "foraging":
                stores["herbs"] = stores.get("herbs", 0) + day_fraction * 0.5
            elif action == "herding":
                stores["wool"] = stores.get("wool", 0) + day_fraction * 0.3
            elif action in ("baking", "cooking"):
                stores["food"] = stores.get("food", 0) + day_fraction * 0.8
            elif action == "brewing":
                stores["ale"] = stores.get("ale", 0) + day_fraction * 0.3
            elif action == "tanning":
                stores["leather"] = stores.get("leather", 0) + day_fraction * 0.3
            elif action == "carpentry":
                stores["tools"] = stores.get("tools", 0) + day_fraction * 0.3
            elif action == "weaving":
                stores["clothing"] = stores.get("clothing", 0) + day_fraction * 0.3
            elif action == "alchemy":
                stores["potions"] = stores.get("potions", 0) + day_fraction * 0.2
            elif action == "masonry":
                stores["stone"] = stores.get("stone", 0) + day_fraction * 0.5
            elif action == "building":
                # Consumes wood/stone, does not produce tradeable goods
                pass

            # Grant skill XP for work (slow drip per tick)
            from game.systems.npc_work import grant_work_skill_xp
            grant_work_skill_xp(npc)

            # Pay from settlement gold pool
            available_gold = stores.get("gold", 0)
            actual_pay = min(tick_income, available_gold)
            if actual_pay > 0:
                stores["gold"] = available_gold - actual_pay
                npc.npc_gold = min(9999, getattr(npc, 'npc_gold', 0) + actual_pay)
            # If settlement is broke, NPC earns nothing (realistic!)
        else:
            # No settlement store found — give a minimal subsistence wage
            # so NPCs don't stagnate at zero gold forever.  This represents
            # self-employment, foraging, and informal trade.
            subsistence = tick_income * 0.4
            npc.npc_gold = min(9999, getattr(npc, 'npc_gold', 0) + subsistence)

        # Track work status
        if not hasattr(npc, '_days_worked'):
            npc._days_worked = 0
        npc._days_worked += day_fraction

    def _hourly_update(self, npc, time_norm: float, day: int, economy,
                       world=None, world_effects=None):
        """Hourly checks: spending (gold flows to settlement), social needs."""
        gold = getattr(npc, 'npc_gold', 0)
        needs = getattr(npc, 'needs', {})

        # Get settlement stores for real transactions
        settlement = self._get_npc_settlement(npc, world)
        stores = None
        if settlement and world_effects and hasattr(world_effects, 'get_stores_ref'):
            stores = world_effects.get_stores_ref(settlement)

        # Buy food when hungry and at settlement
        if needs.get('hunger', 100) < 40 and gold >= 3:
            if npc.has_food():
                pass  # already has food
            elif stores is not None and stores.get("food", 0) >= 1:
                # Real transaction: NPC pays gold, settlement gives food
                npc.npc_gold -= 3
                stores["gold"] = stores.get("gold", 0) + 3
                stores["food"] = max(0, stores.get("food", 0) - 1)
                from game.core.items import make_item
                food = make_item("Bread")
                if food and hasattr(npc, 'npc_inventory'):
                    npc.npc_inventory.append(food)
                needs['hunger'] = min(100, needs.get('hunger', 0) + 25)

        # Buy water when thirsty
        if needs.get('thirst', 100) < 35 and gold >= 2:
            if npc.has_drink():
                pass
            else:
                # Water is free from wells but costs gold at market
                cost = 2 if stores is not None else 0
                if cost <= gold:
                    npc.npc_gold -= cost
                    if stores is not None:
                        stores["gold"] = stores.get("gold", 0) + cost
                    from game.core.items import make_item
                    drink = make_item("Water Flask")
                    if drink and hasattr(npc, 'npc_inventory'):
                        npc.npc_inventory.append(drink)
                    needs['thirst'] = min(100, needs.get('thirst', 0) + 30)

        # Tavern visit — spend gold for rest and social (gold to settlement)
        if (0.68 < time_norm < 0.85 and gold >= 2 and
            needs.get('social', 100) < 40):
            npc.npc_gold -= 2
            if stores is not None:
                stores["gold"] = stores.get("gold", 0) + 2  # tavern revenue
            needs['social'] = min(100, needs.get('social', 0) + 20)
            needs['rest'] = min(100, needs.get('rest', 0) + 10)

            # Chance of getting drunk
            if random.random() < SOCIAL_EVENT_CHANCES["get_drunk"]:
                extra_spend = max(0, min(gold - 2, random.randint(1, 5)))
                npc.npc_gold -= extra_spend
                if stores is not None:
                    stores["gold"] = stores.get("gold", 0) + extra_spend
                npc.add_memory("social", "Got drunk at the tavern!", 2)
                if not hasattr(npc, '_drunk_days'):
                    npc._drunk_days = 0
                npc._drunk_days += 1

        # Desperate NPCs may turn to crime — steal FROM settlement stores
        if gold < 2 and needs.get('hunger', 100) < 20:
            if random.random() < SOCIAL_EVENT_CHANCES["commit_crime"]:
                stolen = random.randint(3, 10)
                if stores is not None:
                    # Steal from settlement gold
                    actual_stolen = min(stolen, stores.get("gold", 0))
                    stores["gold"] = max(0, stores.get("gold", 0) - actual_stolen)
                    stolen = actual_stolen
                if stolen > 0:
                    npc.npc_gold += stolen
                    npc.add_memory("crime", f"Stole {stolen} gold out of desperation", 4)
                    # Emotion: guilt (remorse = sadness+disgust) and fear of being caught
                    from game.systems.emotions import trigger_emotion
                    trigger_emotion(npc, "was_robbed", intensity=0.3,
                                    cause="committed theft out of desperation")
                    ledger = getattr(npc, 'life_ledger', None)
                    if ledger and hasattr(ledger, 'record_crime'):
                        ledger.record_crime("theft", f"Stole {stolen} gold", day)
                    self.event_log.append(f"{npc.name} stole {stolen}g (desperate)")

    def _daily_update(self, npc, day: int, governance, all_npcs,
                      world=None, world_effects=None):
        """Daily checks: costs, career, social progression, consequences."""
        gold = getattr(npc, 'npc_gold', 0)
        title = getattr(npc, 'title', 'commoner')

        # === DAILY COSTS (gold flows TO settlement stores) ===
        cost_mult = TITLE_COST_MULT.get(title, 1.0)
        total_cost = sum(DAILY_COSTS.values()) * cost_mult
        actual_cost = min(total_cost, gold)
        npc.npc_gold = max(0, gold - actual_cost)

        # Route the spending to the settlement
        settlement = self._get_npc_settlement(npc, world)
        stores = None
        if settlement and world_effects and hasattr(world_effects, 'get_stores_ref'):
            stores = world_effects.get_stores_ref(settlement)
        if stores is not None and actual_cost > 0:
            stores["gold"] = stores.get("gold", 0) + actual_cost
            # Food portion consumed
            food_fraction = DAILY_COSTS["food"] * cost_mult / total_cost if total_cost > 0 else 0.5
            food_consumed = food_fraction * actual_cost / max(1, stores.get("food", 1))
            stores["food"] = max(0, stores.get("food", 0) - food_consumed)

        # === CAREER ADVANCEMENT (title promotions) ===
        self._check_promotion(npc, day, all_npcs)

        # === PROFESSION ADVANCEMENT (job promotions) ===
        from game.systems.npc_work import try_profession_promotion
        result = try_profession_promotion(npc)
        if result:
            self.event_log.append(result)

        # === CONSEQUENCES ===
        # Drunk NPCs miss work → chance of demotion
        drunk_days = getattr(npc, '_drunk_days', 0)
        if drunk_days > 3:
            if random.random() < SOCIAL_EVENT_CHANCES["get_fired"]:
                if title in ("guard", "sergeant", "captain"):
                    npc.title = "commoner"
                    npc.add_memory("career", "Dismissed from duty for drunkenness!", 4)
                    self.event_log.append(f"{npc.name} dismissed for drunkenness")
                    # Emotion: sadness and anger from losing position
                    from game.systems.emotions import trigger_emotion
                    trigger_emotion(npc, "got_fired", intensity=0.7,
                                    cause="dismissed for drunkenness")
                npc._drunk_days = 0

        # Broke servants may leave service
        if title == "servant" and gold > 30:
            if random.random() < 0.05:
                npc.title = "commoner"
                npc.add_memory("career", "Saved enough to leave service", 3)

        # === SOCIAL PROGRESSION ===
        self._check_social_events(npc, day, all_npcs)

        # === ASPIRATIONS ===
        self._update_goals(npc)

        # === WAR / CONSCRIPTION ===
        if governance:
            self._check_conscription(npc, day, governance)

        # === CONSCIOUSNESS GROWTH ===
        self._update_consciousness(npc, day)

        # === TEACHING / LEARNING ===
        self._try_teaching(npc, all_npcs, day)

        # === CONSTRUCTION WORK ===
        self._volunteer_for_construction(npc)

        # === LONG-TERM GOALS → ACTIONS ===
        self._pursue_long_term_goals(npc)

    def _redistribute_treasury(self, governance, world_effects):
        """Kingdom treasuries fund their settlements once per game-day.

        This closes the fiscal loop: NPC taxes flow to kingdom treasury
        (handled by governance._collect_taxes), and treasury flows back
        to settlement stores so guards and workers can be paid.
        Gold is conserved — it just moves between entities.
        """
        for kname, kingdom in governance.kingdoms.items():
            settlements = getattr(kingdom, 'settlements', [])
            if not settlements:
                continue
            # Each settlement gets an equal share of a portion of treasury
            # Keep 40% as strategic reserve, distribute 60%
            distributable = kingdom.treasury * 0.6
            if distributable < 1:
                continue
            per_settlement = distributable / len(settlements)
            total_distributed = 0
            for sname in settlements:
                stores = world_effects.get_stores_ref(sname)
                share = min(per_settlement, distributable - total_distributed)
                if share <= 0:
                    break
                stores["gold"] = stores.get("gold", 0) + share
                total_distributed += share
            kingdom.treasury -= total_distributed

    def _update_consciousness(self, npc, day: int):
        """Boost consciousness growth based on experiences.

        NPCs gain awareness from: combat survival, witnessing death,
        social bonds, philosophical conversations, reading, prayer, travel.
        """
        awareness = getattr(npc, 'awareness_points', 0.0)
        old_consciousness = getattr(npc, 'consciousness', 0)

        # Experience-based awareness gains
        kills = getattr(npc, 'kills', 0)
        if kills > 0:
            awareness += min(kills * 0.2, 2.0)  # combat experience

        # Social bonds
        friends = getattr(npc, 'friends', [])
        if len(friends) >= 3:
            awareness += 0.1  # social connections foster awareness

        # Knowledge seekers (wizards, scholars, monks)
        char_class = getattr(npc, 'char_class', '')
        if char_class in ('Wizard', 'Monk', 'Cleric', 'Druid'):
            awareness += 0.05  # contemplative classes gain faster

        # Reading/study
        skills = getattr(npc, 'npc_skills', getattr(npc, 'skills', {}))
        literacy = skills.get('literacy', 0)
        if literacy >= 3:
            awareness += 0.03

        # Age — elders become more aware
        age_cat = getattr(npc, 'age_category', 'prime')
        if age_cat in ('elder', 'ancient'):
            awareness += 0.08

        # Suffering — hardship raises awareness
        gold = getattr(npc, 'npc_gold', 10)
        if gold <= 0:
            awareness += 0.05  # poverty brings clarity

        npc.awareness_points = awareness

        # Level up consciousness
        if awareness > 10 and old_consciousness < 1:
            npc.consciousness = 1
            npc.add_memory("philosophy", "I'm beginning to understand my place in the world.", 4)
            self.event_log.append(f"{npc.name} became AWARE (consciousness 1)")
        elif awareness > 30 and old_consciousness < 2:
            npc.consciousness = 2
            npc.add_memory("philosophy", "I can see patterns in life that others miss.", 5)
            self.event_log.append(f"{npc.name} became CONSCIOUS (consciousness 2)")
        elif awareness > 60 and old_consciousness < 3:
            npc.consciousness = 3
            npc.add_memory("philosophy", "I understand the nature of this world.", 5)
            # Add a philosophical thought
            thoughts = getattr(npc, 'philosophical_thoughts', [])
            thoughts.append(f"On day {day}, I achieved enlightenment.")
            npc.philosophical_thoughts = thoughts
            self.event_log.append(f"{npc.name} became ENLIGHTENED (consciousness 3)")

    def _try_teaching(self, npc, all_npcs, day: int):
        """NPCs with high skills may teach nearby NPCs with lower skills."""
        if random.random() > 0.02:  # 2% daily chance
            return

        skills = getattr(npc, 'npc_skills', {})
        if not skills:
            return

        # Find highest skill
        best_skill = max(skills, key=lambda s: skills[s])
        best_level = skills[best_skill]
        if best_level < 4:
            return  # need reasonable expertise to teach

        # Find a nearby NPC to teach
        for other in all_npcs:
            if other.name == npc.name or not other.alive:
                continue
            if abs(npc.home_x - other.home_x) + abs(npc.home_y - other.home_y) > 15:
                continue  # too far

            other_skills = getattr(other, 'npc_skills', {})
            other_level = other_skills.get(best_skill, 0)
            if other_level >= best_level:
                continue

            # Teach!
            from game.systems.skills import try_teach
            result = try_teach(npc, other, best_skill)
            if result:
                self.event_log.append(result)
                # Both NPCs gain social bond
                friends = getattr(npc, 'friends', [])
                if other.name not in friends and len(friends) < 10:
                    friends.append(other.name)
                    npc.friends = friends
            break  # one teaching attempt per day

    def _volunteer_for_construction(self, npc):
        """NPCs may volunteer as construction workers if projects exist nearby."""
        if random.random() > 0.01:  # 1% daily check
            return

        title = getattr(npc, 'title', 'commoner')
        if title in ('monarch', 'duke', 'lord', 'high_priest'):
            return  # nobles don't do manual labor

        char_class = getattr(npc, 'char_class', '')
        profession = getattr(npc, 'profession', '')
        # Prefer manual laborers — both by class and profession
        labor_classes = ('Fighter', 'Barbarian', 'Ranger', 'Monk',
                         'Farmer', 'Blacksmith', 'Miner')
        labor_profs = ('Builder', 'Mason', 'Laborer', 'Porter', 'Carpenter',
                       'Woodcutter', 'Farmer', 'Miner', 'Blacksmith',
                       'Gravedigger')
        if char_class not in labor_classes and profession not in labor_profs:
            if random.random() > 0.3:  # non-labor classes less likely
                return

        # Set a construction work flag that the construction system can detect
        npc.current_action = "building"
        npc.add_memory("work", "Volunteered for construction work", 2)

    def _pursue_long_term_goals(self, npc):
        """Convert long-term goals into actionable current goals."""
        goals = getattr(npc, 'long_term_goals', [])
        if not goals:
            return

        current = getattr(npc, 'current_goal', '')
        if current and current not in ('', 'idle'):
            return  # already pursuing something

        gold = getattr(npc, 'npc_gold', 0)
        title = getattr(npc, 'title', 'commoner')

        goal = random.choice(goals)
        goal_lower = goal.lower()

        # Map goal text to actionable current_goal
        if 'wealth' in goal_lower or 'rich' in goal_lower or 'fortune' in goal_lower:
            if gold < 50:
                npc.current_goal = "earn money"
            else:
                npc.current_goal = "invest wisely"
        elif 'rule' in goal_lower or 'power' in goal_lower or 'lead' in goal_lower:
            if title == 'commoner':
                npc.current_goal = "seek advancement"
            else:
                npc.current_goal = "strengthen position"
        elif 'friend' in goal_lower or 'ally' in goal_lower or 'social' in goal_lower:
            npc.current_goal = "find company"
        elif 'love' in goal_lower or 'family' in goal_lower or 'marry' in goal_lower:
            npc.current_goal = "find a partner"
        elif 'protect' in goal_lower or 'defend' in goal_lower:
            npc.current_goal = "patrol and protect"
        elif 'explore' in goal_lower or 'adventure' in goal_lower:
            npc.current_goal = "explore new places"
        elif 'knowledge' in goal_lower or 'learn' in goal_lower or 'study' in goal_lower:
            npc.current_goal = "seek knowledge"
        elif 'craft' in goal_lower or 'create' in goal_lower or 'build' in goal_lower:
            npc.current_goal = "work on craft"
        elif 'faith' in goal_lower or 'pray' in goal_lower or 'god' in goal_lower:
            npc.current_goal = "serve the faith"
            # Deity integration — if NPC has a deity, mention it
            deity = getattr(npc, 'deity', None)
            if deity:
                npc.current_goal = f"serve {deity}"

    def _check_promotion(self, npc, day: int, all_npcs):
        """Check if NPC qualifies for career advancement."""
        title = getattr(npc, 'title', 'commoner')
        level = getattr(npc, 'level', 1)
        gold = getattr(npc, 'npc_gold', 0)
        char_class = getattr(npc, 'char_class', '')
        kills = getattr(npc, 'kills', 0) if hasattr(npc, 'kills') else 0
        days_in_role = getattr(npc, '_days_in_role', 0)

        if not hasattr(npc, '_days_in_role'):
            npc._days_in_role = 0
        npc._days_in_role += 1

        for (from_title, to_title), reqs in NPC_PROMOTION_PATHS.items():
            if title != from_title:
                continue

            # Check all requirements
            meets = True
            if "level" in reqs and level < reqs["level"]:
                meets = False
            if "kills" in reqs and kills < reqs["kills"]:
                meets = False
            if "gold" in reqs and gold < reqs["gold"]:
                meets = False
            if "gold_below" in reqs and gold >= reqs["gold_below"]:
                meets = False
            if "bravery" in reqs and getattr(npc, 'bravery', 0) < reqs["bravery"]:
                meets = False
            if "days_in_role" in reqs and days_in_role < reqs["days_in_role"]:
                meets = False
            if "char_class" in reqs:
                if char_class not in reqs["char_class"]:
                    meets = False

            if meets and random.random() < 0.1:  # 10% chance per day when qualified
                npc.title = to_title
                npc._days_in_role = 0
                npc.add_memory("career", f"Promoted to {to_title}!", 5)
                self.event_log.append(f"{npc.name} promoted: {from_title} → {to_title}")
                # Emotion: joy and anticipation from promotion
                from game.systems.emotions import trigger_emotion
                trigger_emotion(npc, "got_promoted", intensity=0.8,
                                cause=f"promoted to {to_title}")

                ledger = getattr(npc, 'life_ledger', None)
                if ledger and hasattr(ledger, 'record_milestone'):
                    ledger.record_milestone("promotion", f"Became {to_title}",
                                             day, to_title)
                break

    def _check_social_events(self, npc, day: int, all_npcs):
        """Check for relationship events: courtship, marriage, children."""
        # Children can't court or marry
        if getattr(npc, 'is_child', False):
            return
        # Only during social hours or if social need is low
        friends = getattr(npc, 'friends', [])

        # Courtship: single NPCs with high friendship may start courting
        ledger = getattr(npc, 'life_ledger', None)
        has_spouse = False
        courting = None
        if ledger:
            for bond in getattr(ledger, 'bonds', []):
                if getattr(bond, 'bond_type', '') == 'spouse':
                    has_spouse = True
                elif getattr(bond, 'bond_type', '') == 'lover':
                    courting = getattr(bond, 'other_name', None)

        if not has_spouse and not courting:
            # Look for potential partner among friends
            for friend_name in friends:
                if random.random() > SOCIAL_EVENT_CHANCES["start_courtship"]:
                    continue
                for other in all_npcs:
                    if other.name == friend_name and other.alive:
                        # Check mutual interest
                        other_friends = getattr(other, 'friends', [])
                        if npc.name in other_friends:
                            # Start courtship
                            npc.add_memory("social",
                                f"Started courting {other.name}", 4)
                            if ledger and hasattr(ledger, 'record_bond'):
                                ledger.record_bond(other.name, "lover",
                                    f"Started courting", day)
                            self.event_log.append(
                                f"{npc.name} and {other.name} are courting")
                            # Emotion: joy from new romance
                            from game.systems.emotions import trigger_emotion
                            trigger_emotion(npc, "saw_friend", intensity=1.0,
                                            target=other.name,
                                            cause=f"started courting {other.name}")
                            trigger_emotion(other, "saw_friend", intensity=1.0,
                                            target=npc.name,
                                            cause=f"started courting {npc.name}")
                            break

        elif courting and not has_spouse:
            # Proposal after courting a while
            if getattr(npc, '_days_in_role', 0) > 60:
                if random.random() < SOCIAL_EVENT_CHANCES["propose_marriage"]:
                    for other in all_npcs:
                        if other.name == courting and other.alive:
                            # Marriage!
                            npc.add_memory("social",
                                f"Married {other.name}!", 5)
                            other.add_memory("social",
                                f"Married {npc.name}!", 5)
                            if ledger and hasattr(ledger, 'record_bond'):
                                ledger.record_bond(other.name, "spouse",
                                    "Married", day)
                            other_ledger = getattr(other, 'life_ledger', None)
                            if other_ledger and hasattr(other_ledger, 'record_bond'):
                                other_ledger.record_bond(npc.name, "spouse",
                                    "Married", day)
                            self.event_log.append(
                                f"{npc.name} married {other.name}!")
                            # Update family dicts for family tree tracking
                            for spouse_pair in [(npc, other), (other, npc)]:
                                sp = spouse_pair[0]
                                if not hasattr(sp, 'family') or sp.family is None:
                                    sp.family = {"mother": None, "father": None,
                                                 "children": [], "spouse": None,
                                                 "siblings": []}
                                sp.family["spouse"] = spouse_pair[1].name
                            # Emotion: ecstasy from marriage
                            from game.systems.emotions import trigger_emotion
                            trigger_emotion(npc, "festival", intensity=1.2,
                                            target=other.name,
                                            cause=f"married {other.name}")
                            trigger_emotion(other, "festival", intensity=1.2,
                                            target=npc.name,
                                            cause=f"married {npc.name}")
                            break

        elif has_spouse:
            # Children are now handled by ChildSystem (pregnancies, births,
            # inheritance).  The old random event is removed to avoid
            # duplicate "expecting" messages.
            pass

    def _update_goals(self, npc):
        """Update NPC aspirations based on current situation."""
        gold = getattr(npc, 'npc_gold', 0)
        title = getattr(npc, 'title', 'commoner')
        needs = getattr(npc, 'needs', {})

        goals = getattr(npc, 'long_term_goals', [])

        # Broke → earn money
        if gold < 5 and "earn money" not in str(goals):
            npc.current_goal = "earn money urgently"

        # Enough savings → seek promotion
        elif gold > 50 and title == "commoner":
            if random.random() < 0.01:
                npc.current_goal = "seek advancement"

        # Lonely → seek companionship
        elif needs.get('social', 100) < 30:
            npc.current_goal = "find company"

        # Exhausted → find rest
        elif needs.get('rest', 100) < 20:
            npc.current_goal = "find somewhere to rest"

        # Hungry → find food
        elif needs.get('hunger', 100) < 25:
            npc.current_goal = "find food"

    def _check_conscription(self, npc, day: int, governance):
        """Check if NPC gets conscripted during wartime."""
        title = getattr(npc, 'title', 'commoner')
        if title in ('monarch', 'duke', 'lord', 'servant', 'serf', 'slave'):
            return  # exempt

        char_class = getattr(npc, 'char_class', '')
        if char_class not in ('Fighter', 'Ranger', 'Paladin', 'Barbarian'):
            return  # non-combat classes exempt unless desperate

        # Check if any kingdom is at war
        for kname, kingdom in governance.kingdoms.items():
            at_war = False
            for rel in governance.diplomacy.values():
                if getattr(rel, 'status', '') == 'war':
                    at_war = True
                    break

            if at_war and random.random() < 0.002:  # small daily chance
                faction = getattr(npc, 'faction', '')
                if faction == kname or not faction:
                    npc.title = "guard"
                    npc.add_memory("military",
                        f"Conscripted into {kname}'s army!", 4)
                    self.event_log.append(
                        f"{npc.name} conscripted by {kname}")
                    break

    def get_event_log(self) -> List[str]:
        """Get and clear the event log."""
        log = list(self.event_log)
        self.event_log.clear()
        return log
