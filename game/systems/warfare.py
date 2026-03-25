"""
Warfare System — tactical battle resolution with unit types, formations, and siege.

Uses modified Lanchester combat models:
- Linear law for melee (casualties ∝ strength difference)
- Square law for ranged (casualties ∝ strength ratio squared)

Unit balance follows rock-paper-scissors:
- Infantry spear beats cavalry (brace for charge)
- Cavalry beats archers (close distance quickly)
- Archers beat infantry (fire before contact)
- Siege engines beat fortifications
- Fortifications beat infantry

Battle factors: terrain, formations, flanking, morale, fatigue,
commander skill, equipment quality, veteran experience.

War economy: recruitment costs, daily upkeep, supply lines,
war taxes, plunder, siege construction.

Research sources:
- Lanchester's laws (1916) for combat attrition modeling
- Total War series morale and flanking mechanics
- Rock-paper-scissors unit balance from Age of Empires / Civilization
"""

import random
import math
from typing import Dict, List, Optional, Tuple


# ================================================================
# UNIT TYPE STATS
# ================================================================

UNIT_STATS = {
    # INFANTRY
    "infantry_sword":   {"melee": 10, "ranged": 0, "defense": 8, "hp": 20, "speed": 1.0,
                         "morale_threshold": 25, "upkeep_gold": 0.5, "upkeep_food": 0.1,
                         "recruit_cost": 5, "category": "infantry"},
    "infantry_spear":   {"melee": 8, "ranged": 0, "defense": 10, "hp": 20, "speed": 0.9,
                         "morale_threshold": 25, "upkeep_gold": 0.5, "upkeep_food": 0.1,
                         "recruit_cost": 5, "bonus_vs_cavalry": 2.0, "category": "infantry"},
    "infantry_pike":    {"melee": 7, "ranged": 0, "defense": 12, "hp": 18, "speed": 0.7,
                         "morale_threshold": 20, "upkeep_gold": 0.6, "upkeep_food": 0.1,
                         "recruit_cost": 6, "bonus_vs_cavalry": 2.5, "category": "infantry"},
    # ARCHERS
    "archer_longbow":   {"melee": 3, "ranged": 12, "defense": 4, "hp": 15, "speed": 1.0,
                         "morale_threshold": 20, "upkeep_gold": 0.6, "upkeep_food": 0.1,
                         "recruit_cost": 7, "range_factor": 1.5, "category": "archer"},
    "archer_crossbow":  {"melee": 4, "ranged": 14, "defense": 5, "hp": 15, "speed": 0.8,
                         "morale_threshold": 22, "upkeep_gold": 0.7, "upkeep_food": 0.1,
                         "recruit_cost": 8, "range_factor": 1.3, "category": "archer"},
    # CAVALRY
    "cavalry_light":    {"melee": 12, "ranged": 0, "defense": 5, "hp": 22, "speed": 2.0,
                         "morale_threshold": 20, "upkeep_gold": 1.0, "upkeep_food": 0.2,
                         "recruit_cost": 12, "charge_bonus": 1.3, "category": "cavalry"},
    "cavalry_heavy":    {"melee": 14, "ranged": 0, "defense": 10, "hp": 28, "speed": 1.5,
                         "morale_threshold": 25, "upkeep_gold": 1.5, "upkeep_food": 0.3,
                         "recruit_cost": 18, "charge_bonus": 1.6, "category": "cavalry"},
    "cavalry_mounted_archer": {"melee": 6, "ranged": 9, "defense": 4, "hp": 20, "speed": 2.2,
                         "morale_threshold": 18, "upkeep_gold": 1.2, "upkeep_food": 0.2,
                         "recruit_cost": 15, "category": "cavalry"},
    # SIEGE
    "siege_ram":        {"melee": 2, "ranged": 0, "defense": 6, "hp": 50, "speed": 0.3,
                         "morale_threshold": 30, "upkeep_gold": 0.5, "upkeep_food": 0.0,
                         "recruit_cost": 30, "structural_dmg": 25, "category": "siege"},
    "siege_catapult":   {"melee": 0, "ranged": 8, "defense": 2, "hp": 40, "speed": 0.2,
                         "morale_threshold": 30, "upkeep_gold": 0.8, "upkeep_food": 0.0,
                         "recruit_cost": 50, "structural_dmg": 35, "category": "siege"},
    "siege_trebuchet":  {"melee": 0, "ranged": 10, "defense": 2, "hp": 60, "speed": 0.1,
                         "morale_threshold": 30, "upkeep_gold": 1.0, "upkeep_food": 0.0,
                         "recruit_cost": 80, "structural_dmg": 50, "category": "siege"},
    "siege_tower":      {"melee": 0, "ranged": 0, "defense": 15, "hp": 80, "speed": 0.2,
                         "morale_threshold": 30, "upkeep_gold": 0.5, "upkeep_food": 0.0,
                         "recruit_cost": 60, "wall_bypass": True, "category": "siege"},
    # WAR BEASTS
    "war_elephant":     {"melee": 20, "ranged": 0, "defense": 8, "hp": 60, "speed": 0.8,
                         "morale_threshold": 15, "upkeep_gold": 2.0, "upkeep_food": 0.5,
                         "recruit_cost": 50, "terror": 25, "category": "beast"},
    "war_dire_wolf":    {"melee": 12, "ranged": 0, "defense": 3, "hp": 25, "speed": 2.5,
                         "morale_threshold": 15, "upkeep_gold": 0.5, "upkeep_food": 0.3,
                         "recruit_cost": 15, "terror": 10, "category": "beast"},
    "war_wyvern":       {"melee": 16, "ranged": 8, "defense": 6, "hp": 45, "speed": 3.0,
                         "morale_threshold": 10, "upkeep_gold": 3.0, "upkeep_food": 0.5,
                         "recruit_cost": 100, "terror": 35, "category": "beast"},
    # SUPPORT
    "medic":            {"melee": 2, "ranged": 0, "defense": 3, "hp": 12, "speed": 1.0,
                         "morale_threshold": 15, "upkeep_gold": 0.8, "upkeep_food": 0.1,
                         "recruit_cost": 10, "heal_per_round": 3, "category": "support"},
}


# ================================================================
# MATCHUP BONUSES — rock-paper-scissors multipliers
# ================================================================

MATCHUP_BONUS = {
    # (attacker_category, defender_category): damage_multiplier
    ("cavalry", "archer"):   1.5,   # cavalry crushes archers
    ("cavalry", "infantry"): 1.1,   # slight edge in open
    ("infantry", "cavalry"): 0.9,   # infantry struggles vs cavalry
    ("archer", "infantry"):  1.3,   # archers whittle infantry
    ("archer", "cavalry"):   0.7,   # cavalry closes distance
    ("siege", "fortification"): 2.0, # siege engines demolish walls
    ("beast", "infantry"):   1.3,   # terror + power
    ("beast", "archer"):     1.4,   # beasts charge archers
    ("beast", "cavalry"):    1.1,   # beasts are large targets but tough
}

# Spear bonus is handled via unit-specific bonus_vs_cavalry stat


# ================================================================
# TERRAIN MODIFIERS
# ================================================================

TERRAIN_MODIFIERS = {
    "plains":   {"defense": 1.0, "cavalry_attack": 1.2, "archer_attack": 1.0, "siege_attack": 1.0},
    "hills":    {"defense": 1.2, "cavalry_attack": 0.8, "archer_attack": 1.1, "siege_attack": 0.9},
    "forest":   {"defense": 1.1, "cavalry_attack": 0.6, "archer_attack": 0.8, "siege_attack": 0.7},
    "river":    {"defense": 1.0, "cavalry_attack": 0.7, "archer_attack": 1.0, "siege_attack": 0.8},
    "mountain": {"defense": 1.4, "cavalry_attack": 0.4, "archer_attack": 0.9, "siege_attack": 0.6},
    "swamp":    {"defense": 0.9, "cavalry_attack": 0.3, "archer_attack": 0.7, "siege_attack": 0.5},
    "settlement": {"defense": 1.3, "cavalry_attack": 0.8, "archer_attack": 1.0, "siege_attack": 1.0},
}


# ================================================================
# FORMATIONS
# ================================================================

FORMATIONS = {
    "shield_wall":      {"defense_mult": 1.4, "attack_mult": 0.8, "speed_mult": 0.5,
                         "requires": "infantry", "description": "Locked shields, maximum defense"},
    "wedge":            {"defense_mult": 0.8, "attack_mult": 1.3, "speed_mult": 1.2,
                         "charge_mult": 1.5, "requires": "cavalry", "description": "Pointed charge formation"},
    "skirmish_line":    {"defense_mult": 0.7, "attack_mult": 1.1, "speed_mult": 1.3,
                         "requires": "archer", "description": "Spread out, mobile shooting"},
    "siege_formation":  {"defense_mult": 1.0, "attack_mult": 1.0, "speed_mult": 0.4,
                         "siege_mult": 1.3, "requires": "siege", "description": "Engines forward, protected"},
    "defensive_circle": {"defense_mult": 1.5, "attack_mult": 0.6, "speed_mult": 0.0,
                         "requires": None, "description": "All-around defense, last stand"},
}


# ================================================================
# FORTIFICATION STATS
# ================================================================

FORTIFICATION_STATS = {
    "wooden_palisade": {"hp": 200, "defense_bonus": 1.3, "build_cost": 50},
    "stone_wall":      {"hp": 500, "defense_bonus": 1.5, "build_cost": 200},
    "gate":            {"hp": 150, "defense_bonus": 1.0, "build_cost": 30},
    "tower":           {"hp": 300, "defense_bonus": 1.4, "archer_slots": 10, "build_cost": 100,
                        "ranged_attack": 8},
    "moat":            {"hp": 9999, "defense_bonus": 1.0, "cavalry_penalty": 0.3, "build_cost": 80},
    "boiling_oil":     {"hp": 50, "defense_bonus": 1.0, "damage_per_round": 15, "build_cost": 20},
    "trench":          {"hp": 9999, "defense_bonus": 1.1, "speed_penalty": 0.5, "build_cost": 30},
}


# ================================================================
# TROOP UNIT
# ================================================================

class TroopUnit:
    """A homogeneous group of soldiers of one type."""
    __slots__ = ('unit_type', 'size', 'max_size', 'equipment_quality',
                 'morale', 'fatigue', 'experience', 'formation', 'routed')

    def __init__(self, unit_type: str, size: int, equipment_quality: float = 1.0):
        self.unit_type = unit_type
        self.size = size
        self.max_size = size
        self.equipment_quality = max(0.5, min(2.0, equipment_quality))
        self.morale = 70
        self.fatigue = 0
        self.experience = 0  # 0-10
        self.formation = None
        self.routed = False

    @property
    def stats(self) -> dict:
        return UNIT_STATS.get(self.unit_type, UNIT_STATS["infantry_sword"])

    @property
    def category(self) -> str:
        return self.stats.get("category", "infantry")

    @property
    def effectiveness(self) -> float:
        """Overall effectiveness multiplier (0-2+)."""
        morale_mult = self.morale / 50.0
        fatigue_mult = 1.0 - self.fatigue / 200.0
        vet_mult = 1.0 + self.experience * 0.05
        return morale_mult * fatigue_mult * vet_mult * self.equipment_quality

    @property
    def melee_power(self) -> float:
        return self.size * self.stats["melee"] * self.effectiveness

    @property
    def ranged_power(self) -> float:
        return self.size * self.stats["ranged"] * self.effectiveness

    @property
    def defense_rating(self) -> float:
        defense = self.size * self.stats["defense"] * self.effectiveness
        if self.formation and self.formation in FORMATIONS:
            defense *= FORMATIONS[self.formation].get("defense_mult", 1.0)
        return defense

    def take_casualties(self, count: int):
        actual = min(self.size, max(0, int(count)))
        self.size -= actual
        if self.max_size > 0:
            self.morale -= int(actual / max(1, self.max_size) * 30)
        self.morale = max(0, self.morale)
        self.check_rout()

    def check_rout(self):
        threshold = self.stats.get("morale_threshold", 25)
        if self.morale < threshold:
            # Gradual morale break: probability of rout increases as morale
            # drops further below threshold, rather than instant rout
            rout_chance = (threshold - self.morale) / max(1, threshold)
            if random.random() < rout_chance:
                self.routed = True

    def apply_fatigue(self, rounds: int = 1):
        self.fatigue = min(100, self.fatigue + rounds * 5)

    def heal_casualties(self, healed: int):
        self.size = min(self.max_size, self.size + healed)

    @property
    def alive(self) -> bool:
        return self.size > 0 and not self.routed


# ================================================================
# FORTIFICATION
# ================================================================

class Fortification:
    """A defensive structure."""
    __slots__ = ('fort_type', 'hp', 'max_hp', 'defense_bonus')

    def __init__(self, fort_type: str):
        stats = FORTIFICATION_STATS.get(fort_type, {"hp": 100, "defense_bonus": 1.0})
        self.fort_type = fort_type
        self.hp = stats["hp"]
        self.max_hp = stats["hp"]
        self.defense_bonus = stats.get("defense_bonus", 1.0)

    def take_damage(self, amount: float):
        self.hp = max(0, self.hp - amount)

    @property
    def is_breached(self) -> bool:
        return self.hp <= 0


# ================================================================
# COMMANDER
# ================================================================

class Commander:
    """Wraps an entity to extract leadership stats."""
    def __init__(self, entity=None, leadership: int = 0, name: str = ""):
        if entity:
            skills = getattr(entity, 'npc_skills', getattr(entity, 'skills', {}))
            self.leadership = skills.get('leadership', 0)
            self.name = getattr(entity, 'name', 'Commander')
        else:
            self.leadership = leadership
            self.name = name or "Commander"

    @property
    def strength_bonus(self) -> float:
        return self.leadership * 0.05

    def rally(self, units: List[TroopUnit]) -> int:
        restored = 0
        for u in units:
            if u.routed and random.random() < 0.2 + self.leadership * 0.04:
                u.routed = False
                u.morale = max(u.morale, 30)
                restored += 1
            elif not u.routed:
                u.morale = min(100, u.morale + 3 + self.leadership)
        return restored


# ================================================================
# BATTLE ARMY
# ================================================================

class BattleArmy:
    """One side of a battle."""
    def __init__(self, name: str, units: List[TroopUnit],
                 commander: Commander = None,
                 tactic: str = "balanced",
                 fortifications: List[Fortification] = None,
                 is_defender: bool = False):
        self.name = name
        self.units = units
        self.commander = commander or Commander(leadership=0, name=name)
        self.tactic = tactic  # aggressive, defensive, flanking, balanced
        self.fortifications = fortifications or []
        self.is_defender = is_defender

    @property
    def total_size(self) -> int:
        return sum(u.size for u in self.units)

    @property
    def active_units(self) -> List[TroopUnit]:
        return [u for u in self.units if u.alive]

    @property
    def total_melee(self) -> float:
        return sum(u.melee_power for u in self.active_units)

    @property
    def total_ranged(self) -> float:
        return sum(u.ranged_power for u in self.active_units)

    @property
    def total_defense(self) -> float:
        base = sum(u.defense_rating for u in self.active_units)
        for f in self.fortifications:
            if not f.is_breached:
                base *= f.defense_bonus
        return base

    def is_defeated(self) -> bool:
        return all(not u.alive for u in self.units)


# ================================================================
# BATTLE RESOLUTION
# ================================================================

class BattleField:
    """Resolves combat between two armies using modified Lanchester models."""

    def __init__(self, attacker: BattleArmy, defender: BattleArmy,
                 terrain: str = "plains", is_siege: bool = False, seed: int = None):
        self.attacker = attacker
        self.defender = defender
        self.terrain = terrain
        self.is_siege = is_siege
        self.rng = random.Random(seed) if seed else random.Random()

    def resolve(self, max_rounds: int = 10) -> dict:
        """Resolve the battle. Returns result dict."""
        round_log = []
        terrain_mod = TERRAIN_MODIFIERS.get(self.terrain, TERRAIN_MODIFIERS["plains"])

        # Tactic modifiers
        atk_tactic = self._get_tactic_mods(self.attacker.tactic)
        def_tactic = self._get_tactic_mods(self.defender.tactic)

        # Flanking (attacker chose flanking tactic and has cavalry)
        flanking = (self.attacker.tactic == "flanking" and
                   any(u.category == "cavalry" and u.alive for u in self.attacker.units))

        for round_num in range(1, max_rounds + 1):
            if self.attacker.is_defeated() or self.defender.is_defeated():
                break

            # Commander strength bonus
            atk_cmd = 1.0 + self.attacker.commander.strength_bonus
            def_cmd = 1.0 + self.defender.commander.strength_bonus

            # --- MELEE PHASE (Linear Lanchester) ---
            atk_melee = self.attacker.total_melee * atk_cmd * atk_tactic["attack"]
            def_melee = self.defender.total_melee * def_cmd * def_tactic["attack"]

            # Apply matchup bonuses
            atk_melee *= self._calc_matchup_bonus(self.attacker, self.defender)
            def_melee *= self._calc_matchup_bonus(self.defender, self.attacker)

            # Terrain modifier on cavalry
            for u in self.attacker.active_units:
                if u.category == "cavalry":
                    atk_melee *= terrain_mod.get("cavalry_attack", 1.0)
                    break

            # Flanking bonus
            if flanking:
                atk_melee *= 1.5

            # Fortification defense
            fort_def = 1.0
            for f in self.defender.fortifications:
                if not f.is_breached:
                    fort_def *= f.defense_bonus
            def_defense = self.defender.total_defense * def_tactic["defense"]

            # Linear Lanchester: casualties based on strength difference
            atk_total = atk_melee * self.rng.uniform(0.85, 1.15)
            def_total = def_melee * fort_def * self.rng.uniform(0.85, 1.15)

            if atk_total > def_total:
                diff = atk_total - def_total
                def_casualties = max(1, int(diff * 0.08))
                atk_casualties = max(0, int(def_total * 0.03))
            else:
                diff = def_total - atk_total
                atk_casualties = max(1, int(diff * 0.08))
                def_casualties = max(0, int(atk_total * 0.03))

            # --- RANGED PHASE (Square Lanchester) ---
            atk_ranged = self.attacker.total_ranged * atk_cmd * terrain_mod.get("archer_attack", 1.0)
            def_ranged = self.defender.total_ranged * def_cmd * terrain_mod.get("archer_attack", 1.0)

            if atk_ranged + def_ranged > 0:
                atk_r_sq = atk_ranged ** 2
                def_r_sq = def_ranged ** 2
                total_sq = atk_r_sq + def_r_sq + 0.01

                ranged_from_atk = int(atk_ranged * (atk_r_sq / total_sq) * 0.05)
                ranged_from_def = int(def_ranged * (def_r_sq / total_sq) * 0.05)
                def_casualties += ranged_from_atk
                atk_casualties += ranged_from_def

            # --- SIEGE PHASE ---
            if self.is_siege:
                for u in self.attacker.active_units:
                    struct_dmg = u.stats.get("structural_dmg", 0)
                    if struct_dmg > 0:
                        for f in self.defender.fortifications:
                            if not f.is_breached:
                                f.take_damage(struct_dmg * u.effectiveness)
                                break

                # Boiling oil damage to attackers
                for f in self.defender.fortifications:
                    oil_dmg = FORTIFICATION_STATS.get(f.fort_type, {}).get("damage_per_round", 0)
                    if oil_dmg > 0 and not f.is_breached:
                        atk_casualties += int(oil_dmg * 0.3)

                # Tower archer fire
                for f in self.defender.fortifications:
                    tower_atk = FORTIFICATION_STATS.get(f.fort_type, {}).get("ranged_attack", 0)
                    if tower_atk > 0 and not f.is_breached:
                        slots = FORTIFICATION_STATS[f.fort_type].get("archer_slots", 5)
                        atk_casualties += int(tower_atk * slots * 0.02)

            # --- WAR BEAST TERROR ---
            atk_terror = sum(u.stats.get("terror", 0) for u in self.attacker.active_units if u.alive)
            def_terror = sum(u.stats.get("terror", 0) for u in self.defender.active_units if u.alive)
            for u in self.defender.active_units:
                u.morale -= int(atk_terror * 0.1)
            for u in self.attacker.active_units:
                u.morale -= int(def_terror * 0.1)

            # --- MEDIC HEALING ---
            for u in self.attacker.active_units:
                heal = u.stats.get("heal_per_round", 0)
                if heal > 0:
                    # Heal other units
                    for target in self.attacker.active_units:
                        if target.size < target.max_size:
                            target.heal_casualties(heal)
                            break
            for u in self.defender.active_units:
                heal = u.stats.get("heal_per_round", 0)
                if heal > 0:
                    for target in self.defender.active_units:
                        if target.size < target.max_size:
                            target.heal_casualties(heal)
                            break

            # --- PER-ROUND CASUALTY CAP ---
            # Cap casualties at 20% of each side per round for paced battles
            # Battles should last 3-5 rounds minimum
            atk_cap = max(1, int(self.attacker.total_size * 0.20))
            def_cap = max(1, int(self.defender.total_size * 0.20))
            atk_casualties = min(atk_casualties, atk_cap)
            def_casualties = min(def_casualties, def_cap)

            # During early rounds (1-2), further reduce casualties to ensure
            # battles last at least 3 rounds
            if round_num <= 2:
                atk_casualties = max(1, atk_casualties // 2)
                def_casualties = max(1, def_casualties // 2)

            # --- DISTRIBUTE CASUALTIES ---
            self._distribute_casualties(self.attacker, atk_casualties)
            self._distribute_casualties(self.defender, def_casualties)

            # --- FATIGUE ---
            for u in self.attacker.active_units + self.defender.active_units:
                u.apply_fatigue()

            # --- COMMANDER RALLY (every 3 rounds) ---
            if round_num % 3 == 0:
                self.attacker.commander.rally(self.attacker.units)
                self.defender.commander.rally(self.defender.units)

            # --- EXPERIENCE GAIN ---
            for u in self.attacker.active_units + self.defender.active_units:
                u.experience = min(10, u.experience + 0.1)

            round_log.append({
                "round": round_num,
                "atk_size": self.attacker.total_size,
                "def_size": self.defender.total_size,
                "atk_casualties": atk_casualties,
                "def_casualties": def_casualties,
            })

        # Determine winner
        atk_remaining = self.attacker.total_size
        def_remaining = self.defender.total_size

        if self.attacker.is_defeated():
            winner, loser = self.defender, self.attacker
        elif self.defender.is_defeated():
            winner, loser = self.attacker, self.defender
        elif atk_remaining > def_remaining:
            winner, loser = self.attacker, self.defender
        else:
            winner, loser = self.defender, self.attacker

        total_atk_lost = sum(u.max_size - u.size for u in self.attacker.units)
        total_def_lost = sum(u.max_size - u.size for u in self.defender.units)

        return {
            "winner": winner.name,
            "loser": loser.name,
            "rounds": len(round_log),
            "attacker_casualties": total_atk_lost,
            "defender_casualties": total_def_lost,
            "attacker_remaining": atk_remaining,
            "defender_remaining": def_remaining,
            "fortifications_breached": sum(1 for f in self.defender.fortifications if f.is_breached),
            "round_log": round_log,
        }

    def _get_tactic_mods(self, tactic: str) -> dict:
        mods = {"attack": 1.0, "defense": 1.0}
        if tactic == "aggressive":
            mods["attack"] = 1.2; mods["defense"] = 0.8
        elif tactic == "defensive":
            mods["attack"] = 0.8; mods["defense"] = 1.2
        elif tactic == "flanking":
            mods["attack"] = 1.0; mods["defense"] = 0.9
        return mods

    def _calc_matchup_bonus(self, attacker: BattleArmy, defender: BattleArmy) -> float:
        """Calculate overall RPS matchup bonus."""
        bonus = 1.0
        for au in attacker.active_units:
            for du in defender.active_units:
                key = (au.category, du.category)
                mb = MATCHUP_BONUS.get(key, 1.0)
                if mb != 1.0:
                    weight = au.size / max(1, attacker.total_size)
                    bonus += (mb - 1.0) * weight * 0.5
                # Spear vs cavalry specific bonus
                if du.category == "cavalry" and au.stats.get("bonus_vs_cavalry", 0) > 0:
                    bonus += au.stats["bonus_vs_cavalry"] * 0.3
        return max(0.5, min(2.0, bonus))

    def _distribute_casualties(self, army: BattleArmy, total: int):
        """Distribute casualties across units proportional to exposure."""
        active = army.active_units
        if not active:
            return
        # Front-line units take more casualties
        front = [u for u in active if u.category in ("infantry", "cavalry", "beast")]
        rear = [u for u in active if u.category in ("archer", "siege", "support")]
        front_share = 0.7 if rear else 1.0

        front_cas = int(total * front_share)
        rear_cas = total - front_cas

        for group, cas in [(front, front_cas), (rear, rear_cas)]:
            if not group or cas <= 0:
                continue
            total_size = sum(u.size for u in group)
            if total_size <= 0:
                continue
            for u in group:
                share = int(cas * u.size / total_size)
                u.take_casualties(share)


# ================================================================
# WAR ECONOMY
# ================================================================

class WarEconomy:
    """Military costs integrated with kingdom treasury."""

    @staticmethod
    def recruit_unit(unit_type: str, size: int, treasury: float) -> Tuple[Optional[TroopUnit], float]:
        """Recruit a unit. Returns (unit, gold_spent) or (None, 0)."""
        stats = UNIT_STATS.get(unit_type)
        if not stats:
            return (None, 0)
        total_cost = stats["recruit_cost"] * size
        if treasury < total_cost:
            # Recruit as many as affordable
            affordable = max(1, int(treasury / stats["recruit_cost"]))
            if affordable < 1:
                return (None, 0)
            size = affordable
            total_cost = stats["recruit_cost"] * size
        return (TroopUnit(unit_type, size), total_cost)

    @staticmethod
    def daily_upkeep(units: List[TroopUnit]) -> Tuple[float, float]:
        """Calculate daily upkeep. Returns (gold_cost, food_cost)."""
        gold = sum(UNIT_STATS.get(u.unit_type, {}).get("upkeep_gold", 0.5) * u.size
                  for u in units if u.alive)
        food = sum(UNIT_STATS.get(u.unit_type, {}).get("upkeep_food", 0.1) * u.size
                  for u in units if u.alive)
        return (gold, food)

    @staticmethod
    def calculate_plunder(loser_treasury: float, winner_strength: float,
                          loser_strength: float) -> float:
        """Winner takes a portion of loser's treasury."""
        if loser_strength <= 0:
            ratio = 1.0
        else:
            ratio = min(2.0, winner_strength / max(1, loser_strength))
        pct = min(0.5, 0.1 + ratio * 0.1)
        return loser_treasury * pct


# ================================================================
# INTEGRATION HELPERS — bridge to existing systems
# ================================================================

def npc_to_unit_type(npc) -> str:
    """Map an NPC to the best unit type based on class and skills."""
    cls = getattr(npc, 'char_class', '')
    skills = getattr(npc, 'npc_skills', {})

    if skills.get("archery", 0) >= 3 or cls == "Ranger":
        return "archer_longbow"
    if skills.get("mounted_combat", 0) >= 2:
        return "cavalry_light"
    if cls in ("Cleric", "Druid") and skills.get("medicine", 0) >= 2:
        return "medic"
    if cls in ("Fighter", "Paladin", "Barbarian"):
        if skills.get("shield_work", 0) >= 3:
            return "infantry_spear"
        return "infantry_sword"
    return "infantry_sword"


def creature_to_unit_type(kind: str) -> str:
    """Map a creature kind to a unit type."""
    mapping = {
        "orc": "infantry_sword", "bugbear": "infantry_sword",
        "goblin": "archer_crossbow", "kobold": "archer_crossbow",
        "gnoll": "cavalry_light",  # fast raiders
        "bandit": "infantry_sword",
        "wolf": "war_dire_wolf", "dire_wolf": "war_dire_wolf",
        "ogre": "infantry_pike",  # big and slow
        "troll": "infantry_sword",
        "skeleton": "infantry_spear", "zombie": "infantry_sword",
        "wight": "infantry_sword",
    }
    return mapping.get(kind, "infantry_sword")


def build_army_from_npcs(name: str, npc_list: list,
                          commander_npc=None, is_defender: bool = False) -> BattleArmy:
    """Build a BattleArmy from a list of NPCs."""
    unit_groups = {}
    for npc in npc_list:
        if not npc.alive:
            continue
        utype = npc_to_unit_type(npc)
        if utype not in unit_groups:
            unit_groups[utype] = 0
        unit_groups[utype] += 1

    units = [TroopUnit(utype, count) for utype, count in unit_groups.items()]
    cmd = Commander(commander_npc) if commander_npc else Commander(leadership=0, name=name)
    return BattleArmy(name, units, cmd, is_defender=is_defender)


def build_army_from_creatures(name: str, creatures: list,
                               is_defender: bool = False) -> BattleArmy:
    """Build a BattleArmy from a list of creatures."""
    unit_groups = {}
    for c in creatures:
        if not c.alive:
            continue
        utype = creature_to_unit_type(c.kind)
        if utype not in unit_groups:
            unit_groups[utype] = 0
        unit_groups[utype] += 1

    units = [TroopUnit(utype, count, equipment_quality=0.8) for utype, count in unit_groups.items()]
    return BattleArmy(name, units, Commander(leadership=1, name=name), is_defender=is_defender)


# ================================================================
# MILITARY UNIT SYSTEM — tags individual entities as soldiers
# ================================================================

class MilitaryUnit:
    """A group of NPCs fighting as an organized military unit.

    Bridges warfare.py troop data into individual entity combat by:
    - Tagging NPCs with unit_type, formation, and commander
    - Applying formation bonuses to their combat stats
    - Coordinating movement (maintain formation spacing)
    - Morale cascade (unit breaks when enough members flee/die)
    """

    def __init__(self, name: str, unit_type: str, formation: str = None,
                 commander_name: str = ""):
        self.name = name
        self.unit_type = unit_type
        self.formation = formation
        self.commander_name = commander_name
        self.members: List = []  # list of NPC/Creature entities
        self.morale = 70
        self.routed = False

        stats = UNIT_STATS.get(unit_type, UNIT_STATS["infantry_sword"])
        self.category = stats.get("category", "infantry")
        self.base_stats = stats

    @property
    def alive_count(self) -> int:
        return sum(1 for m in self.members if m.alive)

    @property
    def size(self) -> int:
        return len(self.members)

    def add_member(self, entity):
        """Add an NPC or creature to this unit."""
        self.members.append(entity)
        # Tag entity with unit info
        entity._military_unit = self
        entity._unit_type = self.unit_type
        entity._unit_formation = self.formation

    def get_formation_mods(self) -> dict:
        """Get current formation modifiers."""
        if not self.formation or self.formation not in FORMATIONS:
            return {"defense_mult": 1.0, "attack_mult": 1.0, "speed_mult": 1.0}
        return FORMATIONS[self.formation]

    def get_matchup_bonus(self, enemy_category: str) -> float:
        """Get damage multiplier against enemy unit category."""
        key = (self.category, enemy_category)
        base = MATCHUP_BONUS.get(key, 1.0)
        # Spear vs cavalry bonus
        if enemy_category == "cavalry" and "bonus_vs_cavalry" in self.base_stats:
            base = max(base, self.base_stats["bonus_vs_cavalry"])
        return base

    def set_formation(self, formation: str):
        """Change formation and apply modifiers to all members."""
        self.formation = formation
        for m in self.members:
            m._unit_formation = formation

    def update_morale(self):
        """Update unit morale based on casualties and combat state."""
        if not self.members:
            return
        alive = self.alive_count
        total = self.size
        casualty_ratio = 1.0 - (alive / max(1, total))

        # Morale drops with casualties
        self.morale = max(0, 70 - int(casualty_ratio * 60))

        # Check rout — gradual morale break instead of instant
        threshold = self.base_stats.get("morale_threshold", 25)
        if self.morale < threshold and not self.routed:
            # Probability of rout scales with how far below threshold
            rout_chance = (threshold - self.morale) / max(1, threshold)
            if random.random() < rout_chance:
                self.routed = True
                # All surviving members flee
                for m in self.members:
                    if m.alive and hasattr(m, 'state'):
                        m.state = "fleeing"
                        if hasattr(m, 'current_action'):
                            m.current_action = "fleeing"

    def rally(self, leadership: int = 0) -> bool:
        """Commander attempts to rally a routed unit."""
        if not self.routed:
            return False
        chance = 0.2 + leadership * 0.04
        if random.random() < chance:
            self.routed = False
            self.morale = max(self.morale, 30)
            for m in self.members:
                if m.alive and hasattr(m, 'state') and m.state == "fleeing":
                    m.state = "idle"
                    if hasattr(m, 'current_action'):
                        m.current_action = ""
            return True
        return False


def apply_unit_combat_mods(attacker, target) -> Tuple[float, float]:
    """Get attack and defense multipliers from military unit system.

    Called from CombatSystem.npc_combat_tick to apply formation bonuses
    and rock-paper-scissors matchup bonuses to individual attacks.

    Returns: (attack_mult, defense_mult)
    """
    atk_mult = 1.0
    def_mult = 1.0

    atk_unit = getattr(attacker, '_military_unit', None)
    tgt_unit = getattr(target, '_military_unit', None)

    if atk_unit:
        mods = atk_unit.get_formation_mods()
        atk_mult *= mods.get("attack_mult", 1.0)

        # Matchup bonus against target's unit category
        if tgt_unit:
            atk_mult *= atk_unit.get_matchup_bonus(tgt_unit.category)

    if tgt_unit:
        mods = tgt_unit.get_formation_mods()
        def_mult *= mods.get("defense_mult", 1.0)

    return atk_mult, def_mult


def get_unit_speed_mult(entity) -> float:
    """Get speed multiplier from formation."""
    unit = getattr(entity, '_military_unit', None)
    if unit and unit.formation and unit.formation in FORMATIONS:
        return FORMATIONS[unit.formation].get("speed_mult", 1.0)
    return 1.0
