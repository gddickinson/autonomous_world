"""
Governance & Politics: kingdoms, diplomacy, taxation, laws, succession.

Each castle defines a kingdom with territory, treasury, army, and laws.
Kingdoms have diplomatic relations with each other.
Tax flows from commoners → lords → duke → monarch treasury.
Treasury funds army upkeep, construction, and festivals.
When a monarch dies, succession rules determine the heir.
"""

import random
import math
from typing import Dict, List, Optional, Tuple


# ================================================================
# GOVERNING STYLES - evolve based on ruler personality
# ================================================================

GOVERNING_STYLES = {
    "autocracy": {
        "description": "Absolute rule by a single ruler",
        "tax_mult": 1.5, "morale_mod": -10, "build_freedom": False,
        "corruption_resist": 0.3, "military_bonus": 1.3,
        "land_policy": "ruler_only",  # only ruler grants land
        "personality": {"bravery": 0.6, "charisma": 0.3},  # what rulers tend toward this
    },
    "feudalism": {
        "description": "Lords manage land on behalf of the crown",
        "tax_mult": 1.0, "morale_mod": 0, "build_freedom": False,
        "corruption_resist": 0.5, "military_bonus": 1.0,
        "land_policy": "lords_grant",  # lords can grant land to subjects
        "personality": {"bravery": 0.5, "charisma": 0.5},
    },
    "republic": {
        "description": "Elected officials govern by consensus",
        "tax_mult": 0.8, "morale_mod": 10, "build_freedom": True,
        "corruption_resist": 0.7, "military_bonus": 0.8,
        "land_policy": "free_claim",  # anyone can claim unclaimed land
        "personality": {"charisma": 0.7, "bravery": 0.3},
    },
    "theocracy": {
        "description": "Religious leaders govern in the name of the gods",
        "tax_mult": 0.9, "morale_mod": 5, "build_freedom": False,
        "corruption_resist": 0.6, "military_bonus": 0.9,
        "land_policy": "temple_grant",  # temples control land allocation
        "personality": {"wisdom": 0.7},
    },
    "tribal": {
        "description": "The strongest leads through tradition and might",
        "tax_mult": 0.5, "morale_mod": 5, "build_freedom": True,
        "corruption_resist": 0.4, "military_bonus": 1.1,
        "land_policy": "strength_claim",  # fight for land rights
        "personality": {"bravery": 0.8, "charisma": 0.2},
    },
    "merchant_republic": {
        "description": "Wealthy merchants govern through trade",
        "tax_mult": 1.2, "morale_mod": 0, "build_freedom": True,
        "corruption_resist": 0.3, "military_bonus": 0.7,
        "land_policy": "buy_sell",  # all land can be bought and sold
        "personality": {"charisma": 0.6, "intelligence": 0.6},
    },
    "tyranny": {
        "description": "Rule by fear and oppression",
        "tax_mult": 2.0, "morale_mod": -25, "build_freedom": False,
        "corruption_resist": 0.2, "military_bonus": 1.4,
        "land_policy": "ruler_only",
        "personality": {"bravery": 0.7, "charisma": 0.2, "cruelty": True},
    },
    "anarchy": {
        "description": "No formal government - everyone for themselves",
        "tax_mult": 0.0, "morale_mod": -5, "build_freedom": True,
        "corruption_resist": 0.0, "military_bonus": 0.5,
        "land_policy": "free_claim",
        "personality": {},
    },
}

# Building permission violations and penalties
BUILDING_VIOLATIONS = {
    "unauthorized_construction": {"fine": 15, "reputation_loss": 10,
                                  "description": "Built without permission"},
    "zone_violation": {"fine": 10, "reputation_loss": 5,
                       "description": "Built wrong zone type for area"},
    "trespass_building": {"fine": 25, "reputation_loss": 20,
                         "description": "Built on someone else's land"},
}

# Diplomatic statuses
ALLIED = "allied"
FRIENDLY = "friendly"
NEUTRAL = "neutral"
UNFRIENDLY = "unfriendly"
HOSTILE = "hostile"
AT_WAR = "at_war"

# Laws that can be enacted
LAWS = {
    "low_tax":    {"tax_rate": 0.05, "morale_bonus": 5, "income_mult": 0.5},
    "normal_tax": {"tax_rate": 0.10, "morale_bonus": 0, "income_mult": 1.0},
    "high_tax":   {"tax_rate": 0.20, "morale_bonus": -10, "income_mult": 2.0},
    "martial_law":{"tax_rate": 0.15, "morale_bonus": -20, "income_mult": 1.5, "guard_bonus": True},
    "festival":   {"tax_rate": 0.10, "morale_bonus": 15, "income_mult": 0.8, "duration": 30},
}

# Crime types and punishments
CRIMES = {
    "theft":     {"fine": 10, "reputation_loss": 15, "jail_time": 30},
    "assault":   {"fine": 25, "reputation_loss": 25, "jail_time": 60},
    "murder":    {"fine": 100, "reputation_loss": 50, "jail_time": 300},
    "trespass":  {"fine": 5,  "reputation_loss": 5,  "jail_time": 0},
}


class Kingdom:
    """A political entity with territory, treasury, and governance."""

    def __init__(self, name: str, castle_x: int, castle_y: int, ruler_name: str = ""):
        self.name = name
        self.castle_x = castle_x
        self.castle_y = castle_y
        self.ruler_name = ruler_name
        self.heir_name = ""

        # Territory
        self.settlements: List[str] = []  # settlement names under control
        self.territory_radius = 80  # tiles from castle

        # Treasury
        self.treasury = random.randint(100, 500)
        self.tax_rate = 0.10
        self.income_per_day = 0
        self.expenses_per_day = 0

        # Population
        self.population = 0

        # Military
        self.army_size = 0
        self.army_upkeep = 0  # gold per day
        self.guard_count = 0

        # Laws
        self.active_law = "normal_tax"

        # Governing style
        self.governing_style = "feudalism"  # default, evolves based on ruler
        self.corruption = 0.0  # 0-1, how corrupt officials are
        self.law_enforcement = 0.7  # 0-1, how well laws are enforced

        # Building permissions
        self.building_permits: List[Dict] = []  # approved building projects
        self.violations: List[Dict] = []  # recorded violations

        # Morale
        self.public_morale = 50  # 0-100

        # History
        self.events: List[str] = []

    def can_build(self, npc_name: str, npc_title: str) -> bool:
        """Check if an NPC has permission to build in this kingdom."""
        style_data = GOVERNING_STYLES.get(self.governing_style, {})
        policy = style_data.get("land_policy", "lords_grant")

        if policy == "free_claim" or policy == "buy_sell":
            return True  # anyone can build
        elif policy == "ruler_only":
            return npc_title in ("monarch", "duke")
        elif policy == "lords_grant":
            return npc_title in ("monarch", "duke", "lord", "knight")
        elif policy == "temple_grant":
            return npc_title in ("monarch",) or npc_name == self.ruler_name
        elif policy == "strength_claim":
            return True  # but may be challenged
        return False

    def try_bribe(self, amount: int, npc_charisma: int) -> Tuple[bool, str]:
        """Attempt to bribe a tax collector or official."""
        # Corruption makes bribes more likely to succeed
        base_chance = 0.2 + self.corruption * 0.5 + npc_charisma * 0.02
        if amount >= 10:
            base_chance += 0.1
        if amount >= 25:
            base_chance += 0.2

        success = random.random() < min(0.9, base_chance)
        if success:
            self.corruption = min(1.0, self.corruption + 0.02)
            return True, f"The official accepts your bribe of {amount}g."
        else:
            self.corruption = max(0, self.corruption - 0.01)
            return False, "The official refuses and reports the bribe attempt!"

    def contains(self, x: float, y: float) -> bool:
        dx = x - self.castle_x
        dy = y - self.castle_y
        return dx * dx + dy * dy <= self.territory_radius * self.territory_radius


class DiplomaticRelation:
    """Relationship between two kingdoms."""
    def __init__(self):
        self.status = NEUTRAL
        self.trust = 0  # -100 to 100
        self.trade_agreement = False
        self.war_exhaustion = 0  # 0-100, rises during war
        self.last_interaction = 0

    def update_status(self):
        if self.trust >= 60:
            self.status = ALLIED
        elif self.trust >= 30:
            self.status = FRIENDLY
        elif self.trust >= -10:
            self.status = NEUTRAL
        elif self.trust >= -40:
            self.status = UNFRIENDLY
        elif self.trust >= -70:
            self.status = HOSTILE
        # AT_WAR is set explicitly, not by trust alone


class GovernanceSystem:
    """Manages all kingdoms, diplomacy, and political events."""

    def __init__(self):
        self.kingdoms: Dict[str, Kingdom] = {}
        self.diplomacy: Dict[Tuple[str, str], DiplomaticRelation] = {}
        self.governance_timer = 0.0
        self.tax_timer = 0.0
        self.event_log: List[str] = []

    def initialize(self, structures: list, npcs: list, world=None):
        """Create kingdoms from the world plan, or fall back to castle scanning.

        When a WorldPlan is available (ChunkedWorld), kingdoms are created
        from plan.kingdoms which covers the entire world regardless of
        which chunks are loaded. Otherwise falls back to scanning loaded
        castle structures.
        """
        plan = getattr(world, 'plan', None) if world else None

        if plan and getattr(plan, 'kingdoms', None):
            self._initialize_from_plan(plan, structures, npcs)
        else:
            self._initialize_from_structures(structures, npcs)

    def _initialize_from_plan(self, plan, structures: list, npcs: list):
        """Create kingdoms from WorldPlan.kingdoms metadata."""
        for kdata in plan.kingdoms:
            kingdom = Kingdom(
                kdata["name"],
                kdata["center_x"],
                kdata["center_y"],
                kdata["ruler_name"],
            )
            kingdom.governing_style = kdata["governance_style"]
            kingdom.settlements = list(kdata.get("territory_settlements", []))
            kingdom.treasury = kdata.get("treasury", random.randint(100, 500))
            kingdom.territory_radius = 200  # large radius for planned kingdoms

            # Set race-appropriate defaults
            race = kdata.get("race", "Human")
            kingdom.race = race

            # Scale army based on settlement count
            num_settlements = len(kingdom.settlements)
            kingdom.army_size = max(5, num_settlements * 3 + random.randint(2, 10))
            kingdom.guard_count = max(2, kingdom.army_size // 2)
            kingdom.army_upkeep = kingdom.army_size * 0.5

            # Count actual military NPCs if loaded
            for npc in npcs:
                if kingdom.contains(npc.x, npc.y):
                    title = getattr(npc, 'title', 'commoner')
                    if title in ('guard', 'knight'):
                        kingdom.army_size += 1
                        kingdom.guard_count += 1

            # Morale by governance style
            style_data = GOVERNING_STYLES.get(kingdom.governing_style, {})
            kingdom.public_morale = max(0, min(100,
                50 + style_data.get("morale_mod", 0)))
            kingdom.tax_rate = 0.10 * style_data.get("tax_mult", 1.0)

            self.kingdoms[kdata["name"]] = kingdom
            kingdom.events.append(
                f"Kingdom {kdata['name']} established under {kingdom.ruler_name}")

        # Count NPC population per kingdom.
        # Build a map of settlement name -> structure position so we can
        # match NPCs that live near a kingdom's settlements.
        struct_by_name = {}
        for s in structures:
            struct_by_name[s.name] = s

        kingdom_settlement_positions = {}
        for kname, kingdom in self.kingdoms.items():
            positions = [(kingdom.castle_x, kingdom.castle_y)]
            for sname in kingdom.settlements:
                s = struct_by_name.get(sname)
                if s:
                    positions.append((s.x, s.y))
            kingdom_settlement_positions[kname] = positions

        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            # Check if NPC is near any of the kingdom's settlements
            assigned = False
            for kingdom_name, positions in kingdom_settlement_positions.items():
                kingdom = self.kingdoms[kingdom_name]
                for sx, sy in positions:
                    dist = math.sqrt((npc.x - sx) ** 2 + (npc.y - sy) ** 2)
                    if dist < 80:  # within 80 tiles of any settlement
                        kingdom.population += 1
                        assigned = True
                        break
                if assigned:
                    break
            if not assigned:
                # Fallback: check territory radius from castle
                for kingdom_name, kingdom in self.kingdoms.items():
                    if kingdom.contains(npc.x, npc.y):
                        kingdom.population += 1
                        break

        # For kingdoms with placeholder rulers ('?' or unknown), find the
        # highest-titled NPC in the territory and assign them as ruler.
        title_rank = {"monarch": 6, "duke": 5, "lord": 4, "knight": 3,
                      "captain": 3, "guard": 1, "commoner": 0}
        for kingdom_name, kingdom in self.kingdoms.items():
            if kingdom.ruler_name and kingdom.ruler_name != '?':
                # Verify the ruler actually exists as an NPC
                ruler_exists = any(n.name == kingdom.ruler_name and n.alive
                                   for n in npcs)
                if ruler_exists:
                    continue
            # Find highest-titled NPC in this kingdom
            best_npc = None
            best_rank = -1
            for npc in npcs:
                if not npc.alive or not kingdom.contains(npc.x, npc.y):
                    continue
                rank = title_rank.get(getattr(npc, 'title', 'commoner'), 0)
                if rank > best_rank:
                    best_rank = rank
                    best_npc = npc
            if best_npc:
                kingdom.ruler_name = best_npc.name
                best_npc.is_ruler = True
                best_npc.title = "monarch"
                kingdom.events.append(
                    f"{best_npc.name} assumed rule of {kingdom_name}")

        # Set up diplomatic relations using predefined affinities
        self._initialize_plan_diplomacy(plan)

    def _initialize_plan_diplomacy(self, plan):
        """Set initial diplomatic relations based on racial/cultural affinities."""
        # Predefined trust values between kingdom pairs
        # Key format: (race1, race2) -> trust value
        racial_trust = {
            ("Human", "Elf"): 40,
            ("Human", "Dwarf"): 60,
            ("Human", "Half-Orc"): -50,
            ("Human", "Goblin"): -40,
            ("Human", "Undead"): -70,
            ("Elf", "Dwarf"): 20,
            ("Elf", "Half-Orc"): -80,
            ("Elf", "Goblin"): -60,
            ("Elf", "Undead"): -70,
            ("Dwarf", "Half-Orc"): -40,
            ("Dwarf", "Goblin"): -50,
            ("Dwarf", "Undead"): -70,
            ("Half-Orc", "Goblin"): -30,
            ("Half-Orc", "Undead"): -50,
            ("Goblin", "Undead"): -40,
        }

        kingdom_names = list(self.kingdoms.keys())
        for i, k1 in enumerate(kingdom_names):
            for k2 in kingdom_names[i + 1:]:
                key = (k1, k2)
                rel = DiplomaticRelation()

                king1 = self.kingdoms[k1]
                king2 = self.kingdoms[k2]
                race1 = getattr(king1, 'race', 'Human')
                race2 = getattr(king2, 'race', 'Human')

                # Look up predefined trust (try both orderings)
                trust = racial_trust.get((race1, race2),
                        racial_trust.get((race2, race1), None))

                if trust is not None:
                    # Add some randomness around the base value
                    rel.trust = trust + random.randint(-5, 5)
                else:
                    # Same race or unknown — generally friendly
                    rel.trust = random.randint(10, 30)

                # Set trade agreements for friendly+ relations
                if rel.trust >= 20:
                    rel.trade_agreement = True

                # Declare war for extremely hostile
                if rel.trust <= -75:
                    rel.status = AT_WAR
                    rel.war_exhaustion = random.randint(0, 20)
                else:
                    rel.update_status()

                self.diplomacy[key] = rel

    def _initialize_from_structures(self, structures: list, npcs: list):
        """Legacy: create kingdoms by scanning loaded castle structures."""
        castles = [s for s in structures if s.kind == "castle"]

        for castle in castles:
            # Find the ruler NPC
            ruler = None
            for npc in npcs:
                if getattr(npc, 'is_ruler', False) and npc.dist_to_pos(castle.x, castle.y) < 20:
                    ruler = npc
                    break

            kingdom = Kingdom(
                castle.name, castle.x, castle.y,
                ruler.name if ruler else "Unknown"
            )

            # Assign nearby settlements to this kingdom
            for s in structures:
                if s.kind in ("village", "town", "city", "hamlet"):
                    dist = math.sqrt((s.x - castle.x)**2 + (s.y - castle.y)**2)
                    if dist < kingdom.territory_radius:
                        # Check if another kingdom is closer
                        closer_kingdom = False
                        for other_castle in castles:
                            if other_castle is castle:
                                continue
                            other_dist = math.sqrt((s.x - other_castle.x)**2 + (s.y - other_castle.y)**2)
                            if other_dist < dist:
                                closer_kingdom = True
                                break
                        if not closer_kingdom:
                            kingdom.settlements.append(s.name)

            # Count population and military — check near castle AND settlements
            settlement_positions = [(castle.x, castle.y)]
            for s in structures:
                if s.name in kingdom.settlements:
                    settlement_positions.append((s.x, s.y))

            for npc in npcs:
                if not npc.alive:
                    continue
                near_any = any(
                    npc.dist_to_pos(sx, sy) < 80
                    for sx, sy in settlement_positions
                )
                if near_any:
                    kingdom.population += 1
                    title = getattr(npc, 'title', 'commoner')
                    if title in ('guard', 'knight'):
                        kingdom.army_size += 1
                        kingdom.guard_count += 1

            kingdom.army_upkeep = kingdom.army_size * 0.5  # 2 gold per soldier per day

            # Find heir (duke or eldest knight family member)
            if ruler:
                for npc in npcs:
                    if (getattr(npc, 'title', '') == 'duke' and
                        npc.dist_to_pos(castle.x, castle.y) < 30):
                        kingdom.heir_name = npc.name
                        break

            self.kingdoms[castle.name] = kingdom
            kingdom.events.append(f"Kingdom {castle.name} established under {kingdom.ruler_name}")

        # Initialize diplomacy between all kingdom pairs
        kingdom_names = list(self.kingdoms.keys())
        for i, k1 in enumerate(kingdom_names):
            for k2 in kingdom_names[i+1:]:
                key = (k1, k2)
                rel = DiplomaticRelation()
                # Distance affects initial relations
                king1 = self.kingdoms[k1]
                king2 = self.kingdoms[k2]
                dist = math.sqrt((king1.castle_x - king2.castle_x)**2 +
                                (king1.castle_y - king2.castle_y)**2)
                if dist < 150:
                    rel.trust = random.randint(-20, 10)  # close = more tension
                else:
                    rel.trust = random.randint(-5, 20)
                rel.update_status()
                self.diplomacy[key] = rel

    def update(self, dt: float, npcs: list, day: int, world_market=None,
               construction=None):
        """Periodic governance updates."""
        # Tax collection every game-day
        self.tax_timer += dt
        if self.tax_timer > 60.0:  # every minute ≈ 1 game day
            self.tax_timer = 0.0
            self._collect_taxes(npcs, world_market=world_market,
                                construction=construction)

        # Political events every 3 minutes
        self.governance_timer += dt
        if self.governance_timer > 180.0:
            self.governance_timer = 0.0
            self._evolve_governing_styles(npcs)
            self._political_events(npcs, day)
            self._check_succession(npcs, day)

    def _collect_taxes(self, npcs: list, world_market=None, construction=None):
        """Collect taxes from NPCs, settlement GDP, and base income."""
        # Base income per settlement type
        SETTLEMENT_BASE_INCOME = {
            "hamlet": 5, "village": 15, "town": 40, "city": 100, "castle": 25,
        }
        # Building income bonuses (mirrors kingdom_ai.py BUILDING_INCOME_BONUSES)
        BUILDING_TAX_BONUSES = {
            "market": 0.15, "warehouse": 0.10, "granary": 0.05,
            "workshop": 0.20, "guild_hall": 0.10, "smithy": 0.05,
        }

        for name, kingdom in self.kingdoms.items():
            tax_income = 0
            taxpayers = 0

            # --- NPC personal taxes ---
            for npc in npcs:
                if not npc.alive:
                    continue
                if not kingdom.contains(npc.x, npc.y):
                    continue
                title = getattr(npc, 'title', 'commoner')
                if title in ('commoner', 'guard', 'servant'):
                    tax = kingdom.tax_rate * getattr(npc, 'npc_gold', 0) * 0.1
                    if tax > 0 and getattr(npc, 'npc_gold', 0) > tax:
                        npc.npc_gold -= tax
                        tax_income += tax
                        taxpayers += 1

            # --- Settlement GDP tax (primary income source) ---
            if world_market:
                for sname in kingdom.settlements:
                    settlement_eco = world_market.get_settlement_economy(sname)
                    if settlement_eco:
                        gdp_tax = settlement_eco.gdp * kingdom.tax_rate * 0.5
                        tax_income += gdp_tax

            # --- Base income per settlement (minimum income floor) ---
            if world_market:
                for sname in kingdom.settlements:
                    settlement_eco = world_market.get_settlement_economy(sname)
                    if settlement_eco:
                        base = SETTLEMENT_BASE_INCOME.get(settlement_eco.kind, 5)
                        tax_income += base
            else:
                # Fallback: estimate from settlement count
                tax_income += len(kingdom.settlements) * 10

            # --- Building income bonuses (Fix 4) ---
            # Additive: sum all building bonuses then apply once
            if construction and hasattr(construction, 'settlement_buildings'):
                building_bonus = 0.0
                for sname in kingdom.settlements:
                    buildings = construction.settlement_buildings.get(sname, [])
                    for btype in buildings:
                        building_bonus += BUILDING_TAX_BONUSES.get(btype, 0)
                if building_bonus > 0:
                    tax_income *= (1.0 + building_bonus)

            # --- Army upkeep: 0.5 gold/soldier/day (food/weapons from stockpiles) ---
            expenses = kingdom.army_size * 0.5

            kingdom.treasury += tax_income - expenses
            kingdom.treasury = max(0, round(kingdom.treasury, 2))
            kingdom.income_per_day = tax_income
            kingdom.expenses_per_day = expenses
            kingdom.army_upkeep = expenses

            # Morale effects from taxation
            law = LAWS.get(kingdom.active_law, LAWS["normal_tax"])
            kingdom.public_morale = max(0, min(100,
                kingdom.public_morale + law["morale_bonus"] * 0.01))

            # Bankrupt kingdom loses morale fast
            if kingdom.treasury <= 0:
                kingdom.public_morale = max(0, kingdom.public_morale - 5)

    def _evolve_governing_styles(self, npcs: list):
        """Governing styles evolve based on ruler personality and conditions."""
        for kingdom_name, kingdom in self.kingdoms.items():
            # Find ruler
            ruler = None
            for npc in npcs:
                if npc.name == kingdom.ruler_name and npc.alive:
                    ruler = npc
                    break
            if not ruler:
                # No ruler -> drift toward anarchy
                if kingdom.governing_style != "anarchy" and random.random() < 0.1:
                    kingdom.governing_style = "anarchy"
                    self.event_log.append(f"{kingdom_name} has fallen into anarchy!")
                continue

            # Ruler personality drives style evolution
            bravery = ruler.bravery
            cha = ruler.attributes.get("charisma", 5) / 10.0
            intel = ruler.attributes.get("intelligence", 5) / 10.0
            alignment = getattr(ruler, 'alignment', 'true neutral')

            # Only evolve occasionally
            if random.random() > 0.03:
                continue

            current = kingdom.governing_style
            new_style = current

            # High bravery + low charisma -> autocracy or tyranny
            if bravery > 0.7 and cha < 0.4:
                if "evil" in alignment or "chaotic" in alignment:
                    new_style = "tyranny"
                else:
                    new_style = "autocracy"

            # High charisma + high intelligence -> republic or merchant republic
            elif cha > 0.6 and intel > 0.5:
                if kingdom.treasury > 200:
                    new_style = "merchant_republic"
                else:
                    new_style = "republic"

            # Cleric/Paladin rulers -> theocracy
            elif getattr(ruler, 'char_class', '') in ('Cleric', 'Paladin', 'Monk'):
                new_style = "theocracy"

            # Barbarian/tribal rulers -> tribal
            elif getattr(ruler, 'char_class', '') in ('Barbarian', 'Ranger'):
                new_style = "tribal"

            # Low morale + high corruption -> tyranny
            elif kingdom.public_morale < 25 and kingdom.corruption > 0.5:
                new_style = "tyranny"

            # High morale + low corruption -> republic
            elif kingdom.public_morale > 75 and kingdom.corruption < 0.2:
                if random.random() < 0.3:
                    new_style = "republic"

            if new_style != current:
                old_data = GOVERNING_STYLES.get(current, {})
                new_data = GOVERNING_STYLES.get(new_style, {})
                kingdom.governing_style = new_style
                kingdom.tax_rate = 0.10 * new_data.get("tax_mult", 1.0)
                kingdom.public_morale = max(0, min(100,
                    kingdom.public_morale + new_data.get("morale_mod", 0)))
                msg = f"{kingdom_name} transitioned from {current} to {new_style}!"
                self.event_log.append(msg)
                kingdom.events.append(msg)

            # Corruption drift
            style_data = GOVERNING_STYLES.get(kingdom.governing_style, {})
            resist = style_data.get("corruption_resist", 0.5)
            if random.random() > resist:
                kingdom.corruption = min(1.0, kingdom.corruption + 0.01)
            else:
                kingdom.corruption = max(0, kingdom.corruption - 0.005)

    def _political_events(self, npcs: list, day: int):
        """Random political events between kingdoms."""
        kingdom_names = list(self.kingdoms.keys())
        if len(kingdom_names) < 2:
            return

        # Random diplomatic interaction
        k1, k2 = random.sample(kingdom_names, 2)
        key = (k1, k2) if (k1, k2) in self.diplomacy else (k2, k1)
        if key not in self.diplomacy:
            return

        rel = self.diplomacy[key]
        king1 = self.kingdoms[k1]
        king2 = self.kingdoms[k2]

        # Events based on current status
        if rel.status == AT_WAR:
            rel.war_exhaustion += random.randint(5, 15)
            if rel.war_exhaustion > 80:
                # Peace negotiations
                rel.status = HOSTILE
                rel.trust = -30
                rel.war_exhaustion = 0
                msg = f"Peace declared between {k1} and {k2} (war exhaustion)"
                self.event_log.append(msg)
                king1.events.append(msg)
                king2.events.append(msg)

        elif rel.status == HOSTILE and random.random() < 0.1:
            # Might declare war if strong enough
            if king1.army_size > king2.army_size * 1.5 and king1.treasury > 100:
                rel.status = AT_WAR
                msg = f"{k1} declares war on {k2}!"
                self.event_log.append(msg)
                king1.events.append(msg)
                king2.events.append(msg)

        elif rel.status in (NEUTRAL, FRIENDLY) and random.random() < 0.15:
            # Trade agreement
            if not rel.trade_agreement:
                rel.trade_agreement = True
                rel.trust += 10
                rel.update_status()
                msg = f"Trade agreement between {k1} and {k2}"
                self.event_log.append(msg)

        # Random trust drift
        drift = random.randint(-3, 3)
        rel.trust = max(-100, min(100, rel.trust + drift))
        rel.update_status()

    def _check_succession(self, npcs: list, day: int = 0):
        """Check if any monarch has died and handle succession."""
        for name, kingdom in self.kingdoms.items():
            if not kingdom.ruler_name:
                continue

            # Find ruler
            ruler_alive = False
            for npc in npcs:
                if npc.name == kingdom.ruler_name and npc.alive:
                    ruler_alive = True
                    break

            if not ruler_alive:
                # Succession!
                old_ruler = kingdom.ruler_name
                new_ruler = None

                # Try heir first
                if kingdom.heir_name:
                    for npc in npcs:
                        if npc.name == kingdom.heir_name and npc.alive:
                            new_ruler = npc
                            break

                # If no heir, find strongest noble in territory
                if not new_ruler:
                    candidates = []
                    for npc in npcs:
                        if not npc.alive:
                            continue
                        title = getattr(npc, 'title', 'commoner')
                        if title in ('duke', 'knight', 'lord') and kingdom.contains(npc.x, npc.y):
                            candidates.append(npc)
                    if candidates:
                        new_ruler = max(candidates, key=lambda n: n.hp + n.level * 10)

                if new_ruler:
                    kingdom.ruler_name = new_ruler.name
                    new_ruler.is_ruler = True
                    new_ruler.title = "monarch"
                    new_ruler.add_memory("politics", f"Became ruler of {name} after {old_ruler}'s death", 5)
                    from game.systems.memory import ensure_life_ledger
                    ledger = ensure_life_ledger(new_ruler)
                    ledger.record_milestone("became_ruler", f"Became ruler of {name}", day, name)
                    msg = f"{new_ruler.name} succeeds {old_ruler} as ruler of {name}!"
                    self.event_log.append(msg)
                    kingdom.events.append(msg)
                else:
                    msg = f"{name} has no ruler - the kingdom falls into chaos!"
                    self.event_log.append(msg)
                    kingdom.public_morale = max(0, kingdom.public_morale - 30)

    def get_kingdom_at(self, x: float, y: float) -> Optional[str]:
        """Get which kingdom controls a position."""
        for name, kingdom in self.kingdoms.items():
            if kingdom.contains(x, y):
                return name
        return None

    def get_diplomacy(self, k1: str, k2: str) -> Optional[DiplomaticRelation]:
        key = (k1, k2) if (k1, k2) in self.diplomacy else (k2, k1)
        return self.diplomacy.get(key)

    def get_political_report(self) -> str:
        """Get a summary of all kingdoms."""
        lines = []
        for name, k in self.kingdoms.items():
            style_desc = GOVERNING_STYLES.get(k.governing_style, {}).get("description", "")
            race_str = f", race={k.race}" if hasattr(k, 'race') else ""
            pop = getattr(k, 'population', 0)
            lines.append(
                f"{name}: ruler={k.ruler_name}, {k.governing_style}{race_str}, "
                f"pop={pop}, treasury={k.treasury:.0f}g, army={k.army_size}, "
                f"morale={k.public_morale:.0f}, corruption={k.corruption:.0%}")
        lines.append("")
        for (k1, k2), rel in self.diplomacy.items():
            lines.append(f"  {k1} <-> {k2}: {rel.status} (trust:{rel.trust:+d})")
        return "\n".join(lines)

    def get_event_log(self) -> List[str]:
        msgs = list(self.event_log)
        self.event_log.clear()
        return msgs
