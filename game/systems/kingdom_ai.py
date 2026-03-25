"""
Kingdom Strategic AI: governance-driven decisions for military, defense,
economic investment, resource stockpiling, and war.

Each kingdom's governance_style shapes its priorities. Every 3-5 game days,
kingdoms evaluate their situation and invest treasury in military recruitment,
fortifications, economic buildings, or expansion/war.

Split into:
- kingdom_ai_defs.py: constants, priority profiles, data classes
- kingdom_ai_war.py: war declaration, resolution, peace treaties (mixin)
- kingdom_ai.py (this file): main KingdomAI class, stockpiles, investment
"""

import random
from typing import Dict, List

from game.systems.kingdom_ai_defs import (
    GOVERNANCE_PRIORITIES, DEFAULT_PRIORITIES,
    DEFENSE_BUILDINGS, ECONOMY_BUILDINGS,
    SOLDIER_RECRUIT_COST, KingdomStockpile, WarState,
)
from game.systems.kingdom_ai_war import KingdomWarMixin


# Income bonuses granted by settlement buildings
BUILDING_INCOME_BONUSES = {
    "market":    {"tax_mult": 1.15, "description": "+15% tax income"},
    "warehouse": {"tax_mult": 1.10, "description": "+10% trade income"},
    "granary":   {"tax_mult": 1.05, "description": "-10% food costs (saves gold)"},
    "workshop":  {"tax_mult": 1.20, "description": "+20% production output"},
    "guild_hall":{"tax_mult": 1.10, "description": "+10% crafting income"},
    "smithy":    {"tax_mult": 1.05, "description": "+5% from metalwork"},
}

# Emergency reserve — AI won't spend below this
EMERGENCY_RESERVE = 100


class KingdomAI(KingdomWarMixin):
    """Strategic AI that makes periodic decisions for every kingdom.

    Wired into the simulation loop; call ``update(game_day)`` once per
    game day. The AI checks every 3-5 days per kingdom (staggered).
    """

    def __init__(self):
        self.stockpiles: Dict[str, KingdomStockpile] = {}
        self.next_decision_day: Dict[str, int] = {}
        self.wars: List[WarState] = []
        self.event_log: List[str] = []
        self._initialized = False

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _ensure_init(self, governance):
        """Lazily create stockpiles for every kingdom."""
        if self._initialized:
            return
        for kname in governance.kingdoms:
            if kname not in self.stockpiles:
                self.stockpiles[kname] = KingdomStockpile()
            if kname not in self.next_decision_day:
                self.next_decision_day[kname] = random.randint(0, 4)
        self._initialized = True

    # ------------------------------------------------------------------
    # Building income bonuses
    # ------------------------------------------------------------------

    def get_building_income_multiplier(self, kname: str, construction) -> float:
        """Calculate aggregate income multiplier from all buildings in kingdom settlements."""
        if not construction or not hasattr(construction, 'settlement_buildings'):
            return 1.0
        # Find which settlements belong to this kingdom
        multiplier = 1.0
        settlement_buildings = construction.settlement_buildings
        # We accumulate bonuses from all settlement buildings
        for sname, buildings in settlement_buildings.items():
            for btype in buildings:
                bonus = BUILDING_INCOME_BONUSES.get(btype)
                if bonus:
                    # Each building adds its bonus (diminishing: half effect)
                    multiplier += (bonus["tax_mult"] - 1.0) * 0.5
        return multiplier

    # ------------------------------------------------------------------
    # Main update — called once per game day
    # ------------------------------------------------------------------

    def update(self, game_day: int, governance, military, construction,
               structures: list, npcs: list):
        """Run kingdom AI for the current game day.

        Parameters
        ----------
        game_day : int
            Current in-game day counter.
        governance : GovernanceSystem
            Access to kingdoms and diplomacy.
        military : MilitarySystem
            Army data, campaign launching.
        construction : ConstructionSystem
            Building commissioning.
        structures : list
            World structures (settlements).
        npcs : list
            All NPC objects.
        """
        self._ensure_init(governance)

        # --- Daily stockpile production ---
        self._update_stockpiles(governance, npcs, game_day)

        # --- Daily war resource consumption ---
        self._consume_war_resources(governance, military)

        # --- Strategic decisions (staggered, every 3-5 days) ---
        for kname, kingdom in governance.kingdoms.items():
            if game_day < self.next_decision_day.get(kname, 0):
                continue
            self.next_decision_day[kname] = game_day + random.randint(3, 5)

            style = getattr(kingdom, 'governing_style', 'feudalism')
            priorities = GOVERNANCE_PRIORITIES.get(style, DEFAULT_PRIORITIES)

            self._decide_military(kname, kingdom, priorities, governance,
                                  military, npcs, game_day)
            self._decide_defense(kname, kingdom, priorities, construction,
                                 structures)
            self._decide_economy(kname, kingdom, priorities, construction,
                                 structures)
            self._decide_expansion(kname, kingdom, priorities, governance,
                                   military, game_day)

        # --- War resolution (every day while wars are active) ---
        self._update_wars(governance, military, structures, game_day)

    # ------------------------------------------------------------------
    # Stockpile production
    # ------------------------------------------------------------------

    def _update_stockpiles(self, governance, npcs: list, game_day: int):
        """Farmers produce food, blacksmiths produce weapons, taxes flow."""
        for kname, kingdom in governance.kingdoms.items():
            sp = self.stockpiles.setdefault(kname, KingdomStockpile())

            farmers = 0
            smiths = 0
            for npc in npcs:
                if not npc.alive:
                    continue
                prof = getattr(npc, 'profession', '')
                faction = getattr(npc, 'faction', '')
                if faction != kname and not kingdom.contains(npc.x, npc.y):
                    continue
                if prof in ('Farmer', 'Baker', 'Cook', 'Fisher', 'Fisherman',
                            'Hunter', 'Shepherd'):
                    farmers += 1
                elif prof in ('Blacksmith', 'Armourer'):
                    smiths += 1

            sp.food += farmers * 1.0
            sp.weapons += smiths * 0.5

            # Tax income -> gold reserve
            tax_income = getattr(kingdom, 'income_per_day', 0)
            sp.gold_reserve += max(0, tax_income * 0.1)

            # Log low stockpiles periodically
            if (sp.food < 30 or sp.weapons < 15) and game_day % 5 == 0:
                self.event_log.append(
                    f"{kname} stockpiles running low — "
                    f"{int(sp.food)} food, {int(sp.weapons)} weapons")

    # ------------------------------------------------------------------
    # War resource consumption
    # ------------------------------------------------------------------

    def _consume_war_resources(self, governance, military):
        """Armies consume food daily; starvation causes desertion."""
        for kname, kingdom in governance.kingdoms.items():
            sp = self.stockpiles.get(kname)
            if not sp:
                continue

            total_soldiers = sum(
                a.size for a in military.armies.values()
                if a.kingdom == kname and a.size > 0
            )
            if total_soldiers == 0:
                continue

            # Food: 1 per soldier per day
            food_needed = total_soldiers * 1.0
            sp.food -= food_needed
            if sp.food < 0:
                deserters = min(total_soldiers, int(abs(sp.food)))
                sp.food = 0
                if deserters > 0:
                    self._apply_desertions(kname, deserters, military)
                    self.event_log.append(
                        f"{kname}: {deserters} soldiers deserted (starvation)")

            # Weapons deplete during active wars only
            at_war = any(
                w.attacker == kname or w.defender == kname
                for w in self.wars if not w.ended
            )
            if at_war:
                sp.weapons = max(0, sp.weapons - total_soldiers * 0.1)

    def _apply_desertions(self, kingdom_name: str, count: int, military):
        """Remove soldiers from kingdom armies due to desertion."""
        remaining = count
        for army in military.armies.values():
            if army.kingdom != kingdom_name or army.size == 0:
                continue
            while remaining > 0 and army.soldiers:
                army.remove_soldier(army.soldiers[-1])
                remaining -= 1
            if remaining <= 0:
                break

    # ------------------------------------------------------------------
    # Military investment
    # ------------------------------------------------------------------

    def _decide_military(self, kname, kingdom, priorities, governance,
                         military, npcs, game_day):
        """Recruit soldiers if treasury and priority allow."""
        mil_p = priorities["military"]
        # Fix 6: Don't spend below emergency reserve
        if kingdom.treasury < EMERGENCY_RESERVE or mil_p < 0.25:
            return

        # Fix 6: Don't recruit if can't afford 30 days of upkeep for new soldiers
        current_upkeep = kingdom.army_size * 0.5
        available = kingdom.treasury - EMERGENCY_RESERVE
        if available < 200:
            return

        budget = int(available * mil_p * 0.3)
        max_recruits = budget // SOLDIER_RECRUIT_COST
        max_recruits = min(max_recruits, 8)
        if max_recruits <= 0:
            return

        # Fix 6: Check 30-day upkeep affordability for new soldiers
        new_upkeep_30days = max_recruits * 0.5 * 30
        if new_upkeep_30days > available * 0.5:
            max_recruits = max(1, int(available * 0.5 / (0.5 * 30)))
        if max_recruits <= 0:
            return

        # Find or create the main army
        main_army = None
        for a in military.armies.values():
            if a.kingdom == kname:
                if main_army is None or a.size > main_army.size:
                    main_army = a

        if main_army is None:
            from game.systems.military import Army
            army_name = f"Army of {kname}"
            main_army = Army(army_name, kname, kingdom.ruler_name,
                             float(kingdom.castle_x), float(kingdom.castle_y))
            main_army.commander_rank = "general"
            main_army.commander_leadership = 4
            military.armies[army_name] = main_army

        # Recruit idle civilians
        recruited = 0
        for npc in npcs:
            if recruited >= max_recruits:
                break
            if not npc.alive:
                continue
            if npc.name in main_army.soldiers:
                continue
            prof = getattr(npc, 'profession', '')
            if prof in ('Guard', 'Soldier', 'Captain'):
                continue
            faction = getattr(npc, 'faction', '')
            if faction != kname and not kingdom.contains(npc.x, npc.y):
                continue
            if getattr(npc, 'current_action', '') not in ('', 'idle', 'wandering'):
                continue

            main_army.add_soldier(npc.name)
            kingdom.treasury -= SOLDIER_RECRUIT_COST
            recruited += 1

        if recruited > 0:
            kingdom.army_size = sum(
                a.size for a in military.armies.values() if a.kingdom == kname)
            self.event_log.append(
                f"{kname} mobilizes {recruited} new soldiers "
                f"(army: {kingdom.army_size})")

    # ------------------------------------------------------------------
    # Defense investment
    # ------------------------------------------------------------------

    def _decide_defense(self, kname, kingdom, priorities, construction,
                        structures):
        """Build fortifications in border settlements."""
        def_p = priorities["defense"]
        # Fix 6: Don't spend below emergency reserve
        if kingdom.treasury < EMERGENCY_RESERVE + 100 or def_p < 0.20:
            return

        owned = [s for s in structures if s.name in kingdom.settlements]
        if not owned:
            return

        # Border settlements = farthest from castle
        owned.sort(key=lambda s: (s.x - kingdom.castle_x) ** 2 +
                                  (s.y - kingdom.castle_y) ** 2,
                   reverse=True)
        border = owned[:max(1, len(owned) // 2)]

        existing = construction.settlement_buildings
        already_building = {p.settlement_name
                            for p in construction.building_projects}

        for settlement in border:
            if settlement.name in already_building:
                continue
            sname = settlement.name
            built = existing.get(sname, [])

            for btype in DEFENSE_BUILDINGS:
                if btype in built:
                    continue
                from game.systems.construction import SETTLEMENT_BUILDINGS
                info = SETTLEMENT_BUILDINGS.get(btype)
                if not info or info["cost"] > kingdom.treasury:
                    continue

                from game.systems.construction import SettlementBuildProject
                days = info["days"] + random.randint(-1, 2)
                proj = SettlementBuildProject(sname, btype, max(3, days), kname)
                construction.building_projects.append(proj)
                kingdom.treasury -= info["cost"]

                display = btype.replace("_", " ").title()
                self.event_log.append(
                    f"{kname} reinforces border defenses: "
                    f"{display} at {sname}")
                return  # one project per decision cycle

    # ------------------------------------------------------------------
    # Economic investment
    # ------------------------------------------------------------------

    def _decide_economy(self, kname, kingdom, priorities, construction,
                        structures):
        """Build economic buildings — prioritize income-generating ones (markets first)."""
        eco_p = priorities["economy"]
        # Fix 6: Don't spend below emergency reserve
        if kingdom.treasury < EMERGENCY_RESERVE + 50 or eco_p < 0.20:
            return

        owned = [s for s in structures if s.name in kingdom.settlements]
        if not owned:
            return

        existing = construction.settlement_buildings
        already_building = {p.settlement_name
                            for p in construction.building_projects}

        # Fix 6: Prioritize income-generating buildings (market first)
        PRIORITIZED_ECONOMY_BUILDINGS = ["market", "workshop", "warehouse", "granary"]

        random.shuffle(owned)
        for settlement in owned:
            if settlement.name in already_building:
                continue
            sname = settlement.name
            built = existing.get(sname, [])

            for btype in PRIORITIZED_ECONOMY_BUILDINGS:
                if btype in built:
                    continue
                from game.systems.construction import SETTLEMENT_BUILDINGS
                info = SETTLEMENT_BUILDINGS.get(btype)
                if not info or info["cost"] > kingdom.treasury - EMERGENCY_RESERVE:
                    continue

                from game.systems.construction import SettlementBuildProject
                days = info["days"] + random.randint(-1, 2)
                proj = SettlementBuildProject(sname, btype, max(3, days), kname)
                construction.building_projects.append(proj)
                kingdom.treasury -= info["cost"]

                # Fix 4: Buildings provide income bonuses
                bonus = BUILDING_INCOME_BONUSES.get(btype)
                bonus_desc = f" ({bonus['description']})" if bonus else ""
                display = btype.replace("_", " ").title()
                self.event_log.append(
                    f"{kname} invests in {display} at {sname}{bonus_desc}")

                return  # one per cycle

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------

    def get_event_log(self) -> List[str]:
        """Return and clear accumulated log messages."""
        msgs = list(self.event_log)
        self.event_log.clear()
        return msgs
