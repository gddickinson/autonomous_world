"""
Siege Warfare System — fortifications, siege engines, supply chains, camps.

Settlements have fortifications (walls, towers, gates, moats) that must be
overcome with siege engines before an assault can succeed.

Armies require supply lines to maintain food. Troops must rest in camps
or occupied buildings. Post-conquest options include occupy, raze, or vassalize.

Integrates with warfare.py's Fortification class and BattleField siege mechanics.
"""

import random
import math
from typing import Dict, List, Optional, Tuple


# ================================================================
# SETTLEMENT FORTIFICATIONS
# ================================================================

# What fortifications each settlement type gets by default
SETTLEMENT_FORTIFICATIONS = {
    # Human settlements
    "hamlet":     [],  # no walls
    "village":    [("wooden_palisade", 1)],
    "town":       [("stone_wall", 1), ("gate", 1), ("tower", 2)],
    "city":       [("stone_wall", 2), ("gate", 2), ("tower", 4), ("moat", 1)],
    "castle":     [("stone_wall", 3), ("gate", 1), ("tower", 6), ("moat", 1),
                   ("boiling_oil", 2)],

    # Monster settlements
    "orc_stronghold": [("wooden_palisade", 2), ("tower", 2)],
    "goblin_warren":  [("wooden_palisade", 1), ("trench", 2)],  # traps
    "kobold_mine":    [("trench", 3)],  # elaborate trap corridors
    "bandit_camp":    [("trench", 1)],  # minimal
    "gnoll_den":      [("wooden_palisade", 1)],
    "undead_crypt":   [("stone_wall", 1), ("tower", 1)],
}


class SettlementDefenses:
    """Tracks fortification state for a settlement."""

    def __init__(self, settlement_name: str, settlement_kind: str):
        self.settlement_name = settlement_name
        self.settlement_kind = settlement_kind
        self.fortifications: List[Dict] = []
        self.garrison_size = 0  # NPC defenders inside walls
        self.archer_count = 0   # archers in towers

        # Build fortifications from template
        from game.systems.warfare import FORTIFICATION_STATS
        template = SETTLEMENT_FORTIFICATIONS.get(settlement_kind, [])
        for fort_type, count in template:
            stats = FORTIFICATION_STATS.get(fort_type, {})
            for _ in range(count):
                self.fortifications.append({
                    "type": fort_type,
                    "hp": stats.get("hp", 100),
                    "max_hp": stats.get("hp", 100),
                    "defense_bonus": stats.get("defense_bonus", 1.0),
                    "breached": False,
                })

        # Assign archers to towers
        for f in self.fortifications:
            if f["type"] == "tower":
                from game.systems.warfare import FORTIFICATION_STATS
                slots = FORTIFICATION_STATS.get("tower", {}).get("archer_slots", 5)
                self.archer_count += slots

    @property
    def total_defense_bonus(self) -> float:
        """Combined defense multiplier from all intact fortifications."""
        bonus = 1.0
        for f in self.fortifications:
            if not f["breached"]:
                bonus *= f["defense_bonus"]
        return bonus

    @property
    def is_walled(self) -> bool:
        """Does this settlement have intact walls?"""
        return any(f["type"] in ("wooden_palisade", "stone_wall")
                   and not f["breached"] for f in self.fortifications)

    @property
    def wall_hp(self) -> int:
        """Total HP of all wall sections."""
        return sum(f["hp"] for f in self.fortifications
                   if f["type"] in ("wooden_palisade", "stone_wall")
                   and not f["breached"])

    @property
    def has_moat(self) -> bool:
        return any(f["type"] == "moat" and not f["breached"]
                   for f in self.fortifications)

    def take_siege_damage(self, damage: float, target_type: str = "wall") -> str:
        """Apply siege engine damage to fortifications. Returns status message."""
        for f in self.fortifications:
            if f["breached"]:
                continue
            if target_type == "wall" and f["type"] in ("wooden_palisade", "stone_wall"):
                f["hp"] -= damage
                if f["hp"] <= 0:
                    f["breached"] = True
                    return f"{f['type']} BREACHED!"
                return f"{f['type']} takes {damage:.0f} damage ({f['hp']:.0f}/{f['max_hp']} HP)"
            elif target_type == "gate" and f["type"] == "gate":
                f["hp"] -= damage
                if f["hp"] <= 0:
                    f["breached"] = True
                    return "GATE BREACHED!"
                return f"Gate takes {damage:.0f} damage ({f['hp']:.0f}/{f['max_hp']} HP)"
            elif target_type == "tower" and f["type"] == "tower":
                f["hp"] -= damage
                if f["hp"] <= 0:
                    f["breached"] = True
                    self.archer_count = max(0, self.archer_count - 5)
                    return "Tower destroyed!"
                return f"Tower takes {damage:.0f} damage"
        return "No valid target"

    def get_report(self) -> str:
        intact = sum(1 for f in self.fortifications if not f["breached"])
        total = len(self.fortifications)
        return (f"{self.settlement_name}: {intact}/{total} fortifications intact, "
                f"defense x{self.total_defense_bonus:.1f}, "
                f"archers={self.archer_count}, "
                f"{'WALLED' if self.is_walled else 'OPEN'}")


# ================================================================
# SIEGE ENGINE
# ================================================================

SIEGE_ENGINE_TYPES = {
    "battering_ram": {
        "build_cost": 50,   # gold
        "build_time": 2,    # game days
        "crew_needed": 4,   # NPCs to operate
        "damage_per_round": 25,
        "target": "gate",   # what it attacks
        "speed": 0.3,
        "hp": 80,
        "description": "A heavy log ram for breaking gates",
    },
    "catapult": {
        "build_cost": 80,
        "build_time": 3,
        "crew_needed": 3,
        "damage_per_round": 35,
        "target": "wall",
        "speed": 0.2,
        "hp": 60,
        "description": "Hurls stones at walls",
    },
    "siege_tower": {
        "build_cost": 100,
        "build_time": 4,
        "crew_needed": 6,
        "damage_per_round": 0,  # doesn't damage walls — bypasses them
        "target": "bypass",
        "speed": 0.2,
        "hp": 100,
        "description": "Allows troops to climb over walls",
    },
    "trebuchet": {
        "build_cost": 150,
        "build_time": 5,
        "crew_needed": 5,
        "damage_per_round": 50,
        "target": "wall",
        "speed": 0.1,
        "hp": 80,
        "description": "Massive stone-thrower that devastates walls",
    },
}


class SiegeEngine:
    """A siege weapon that can be built and deployed against fortifications."""

    def __init__(self, engine_type: str, owner_army: str):
        data = SIEGE_ENGINE_TYPES.get(engine_type, SIEGE_ENGINE_TYPES["catapult"])
        self.engine_type = engine_type
        self.owner_army = owner_army
        self.hp = data["hp"]
        self.max_hp = data["hp"]
        self.crew_needed = data["crew_needed"]
        self.crew_assigned = 0
        self.damage_per_round = data["damage_per_round"]
        self.target_type = data["target"]
        self.operational = False
        self.build_progress = 0.0  # 0-1
        self.build_time_days = data["build_time"]

    @property
    def is_built(self) -> bool:
        return self.build_progress >= 1.0

    @property
    def is_crewed(self) -> bool:
        return self.crew_assigned >= self.crew_needed

    def build_tick(self, dt_days: float, workers: int = 1):
        """Advance construction. More workers = faster."""
        rate = workers / max(1, self.build_time_days)
        self.build_progress = min(1.0, self.build_progress + rate * dt_days)

    def fire(self, defenses: SettlementDefenses) -> str:
        """Fire at settlement fortifications (abstract damage). Returns result message."""
        if not self.is_built:
            return f"{self.engine_type} not yet built ({self.build_progress*100:.0f}%)"
        if not self.is_crewed:
            return f"{self.engine_type} needs {self.crew_needed - self.crew_assigned} more crew"

        if self.target_type == "bypass":
            return "Siege tower positioned — troops can bypass walls!"

        damage = self.damage_per_round * random.uniform(0.7, 1.3)
        return defenses.take_siege_damage(damage, self.target_type)

    def fire_at_world(self, world, durability_system, target_x: int, target_y: int,
                       battle_visuals=None) -> str:
        """Fire at actual world tiles, dealing siege damage to walls/gates/doors.

        This modifies the real world map — destroyed walls become rubble,
        destroyed gates become walkable floor.

        Args:
            world: World object with tiles
            durability_system: DurabilitySystem for tile HP tracking
            target_x, target_y: Tile coordinates to hit
            battle_visuals: Optional BattleVisuals for projectile effects
        """
        if not self.is_built or not self.is_crewed:
            return self.fire(None) if not self.is_built else "Not crewed"

        if self.target_type == "bypass":
            return "Siege tower — bypasses walls"

        # Create visual projectile
        if battle_visuals:
            from game.systems.battle_visuals import Projectile
            kind = "stone" if self.engine_type in ("catapult", "trebuchet") else "fire"
            proj = Projectile(self.x if hasattr(self, 'x') else target_x - 10,
                            self.y if hasattr(self, 'y') else target_y - 10,
                            float(target_x), float(target_y),
                            kind=kind, speed=4.0)
            battle_visuals.projectiles.append(proj)

        # Apply siege damage to world tile
        damage = int(self.damage_per_round * random.uniform(0.7, 1.3))
        tile = world.tiles[target_y][target_x]

        from game.systems.durability import TILE_MATERIAL
        if tile in TILE_MATERIAL:
            result = durability_system.damage_tile(
                target_x, target_y, world, damage, "siege")
            return result or f"Hit at ({target_x},{target_y}) — no effect"
        else:
            return f"Hit terrain at ({target_x},{target_y}) — no structural damage"


# ================================================================
# SUPPLY SYSTEM
# ================================================================

class ArmySupply:
    """Tracks food and supply status for an army."""

    def __init__(self, army_size: int):
        self.food = army_size * 3  # 3 days of food per soldier
        self.food_per_day = army_size * 1.0  # 1 food per soldier per day
        self.days_without_food = 0
        self.supply_wagons = 0  # each wagon carries 20 food

    def consume_daily(self, army_size: int) -> str:
        """Consume one day's food. Returns status message."""
        needed = army_size * 1.0
        if self.food >= needed:
            self.food -= needed
            self.days_without_food = 0
            days_left = self.food / max(1, needed)
            return f"Supplies: {self.food:.0f} food ({days_left:.1f} days)"
        else:
            self.food = 0
            self.days_without_food += 1
            return f"OUT OF FOOD! ({self.days_without_food} days starving)"

    def forage(self, terrain: str = "forest", foragers: int = 5) -> float:
        """Forage for food. Returns amount gathered."""
        base = {"forest": 3, "plains": 2, "farmland": 5, "settlement": 8,
                "mountain": 1, "swamp": 1, "desert": 0}.get(terrain, 1)
        gathered = base * foragers * random.uniform(0.5, 1.5)
        self.food += gathered
        return gathered

    def resupply_from_settlement(self, settlement_kind: str, gold_available: float
                                  ) -> Tuple[float, float]:
        """Buy food from a friendly settlement. Returns (food_bought, gold_spent)."""
        prices = {"city": 1.0, "town": 1.5, "village": 2.0, "hamlet": 3.0}
        price = prices.get(settlement_kind, 2.0)
        affordable = int(gold_available / price)
        bought = min(affordable, 50)  # max 50 per resupply
        cost = bought * price
        self.food += bought
        return (bought, cost)

    def get_morale_penalty(self) -> int:
        """Morale penalty from hunger."""
        if self.days_without_food == 0:
            return 0
        return min(50, self.days_without_food * 10)

    def get_desertion_count(self, army_size: int) -> int:
        """How many soldiers desert due to starvation."""
        if self.days_without_food < 3:
            return 0
        rate = min(0.2, self.days_without_food * 0.03)
        return max(0, int(army_size * rate * random.uniform(0.5, 1.5)))


# ================================================================
# ARMY CAMP
# ================================================================

class ArmyCamp:
    """A temporary camp where an army rests and resupplies."""

    def __init__(self, x: float, y: float, army_name: str):
        self.x = x
        self.y = y
        self.army_name = army_name
        self.setup_progress = 0.0  # 0-1 (takes ~1 game hour to set up)
        self.rest_bonus = 0.5      # morale recovery per rest tick
        self.defense_bonus = 1.1   # slight defensive bonus from camp
        self.occupied_buildings: List[str] = []  # building names if occupying

    @property
    def is_ready(self) -> bool:
        return self.setup_progress >= 1.0

    def setup_tick(self, dt_hours: float, workers: int = 5):
        """Advance camp setup. ~1 hour with 5 workers."""
        self.setup_progress = min(1.0, self.setup_progress + dt_hours * workers * 0.2)

    def rest_army(self, army) -> str:
        """Rest troops at camp. Restores morale and reduces fatigue."""
        if not self.is_ready:
            return f"Camp not ready ({self.setup_progress*100:.0f}%)"

        morale_gain = int(self.rest_bonus * 10)
        army.morale = min(100, army.morale + morale_gain)
        return f"Army rested. Morale: {army.morale}"


# ================================================================
# POST-CONQUEST OPTIONS
# ================================================================

class ConquestResult:
    """Handles post-conquest decisions for a defeated settlement."""

    @staticmethod
    def occupy(settlement_name: str, winner_kingdom: str,
               garrison_size: int, governance) -> str:
        """Install a garrison. Settlement changes faction."""
        # Change settlement's kingdom affiliation
        winner_k = governance.kingdoms.get(winner_kingdom)
        if winner_k:
            settlements = getattr(winner_k, 'settlements', [])
            if settlement_name not in settlements:
                settlements.append(settlement_name)
                winner_k.settlements = settlements
        return (f"Occupied {settlement_name} with {garrison_size} garrison. "
                f"Now under {winner_kingdom} control.")

    @staticmethod
    def raze(settlement_name: str, world) -> Tuple[str, int]:
        """Destroy settlement buildings. Gain resources."""
        loot = random.randint(30, 100)
        # Remove buildings from world
        for s in world.structures:
            if s.name == settlement_name:
                building_count = len(getattr(s, 'buildings', []))
                loot += building_count * 10
                s.buildings = []
                break
        return (f"Razed {settlement_name}! Gained {loot}g in salvage.", loot)

    @staticmethod
    def vassalize(settlement_name: str, winner_kingdom: str,
                  target_kingdom: str, governance) -> str:
        """Force settlement to pay tribute. Keeps some autonomy."""
        # Set up tribute relationship
        rel = governance.get_diplomacy(winner_kingdom, target_kingdom)
        if rel:
            rel.status = "hostile"  # no longer at war, but hostile
            rel.trust = -40
            rel.trade_agreement = True  # "trade" = tribute
            rel.update_status()

        return (f"Vassalized {settlement_name}. "
                f"{target_kingdom} now pays tribute to {winner_kingdom}.")

    @staticmethod
    def collect_war_spoils(settlement_name: str, governance,
                           player_gold_ref: list) -> str:
        """Loot the settlement treasury."""
        # Find settlement's kingdom
        for kname, kingdom in governance.kingdoms.items():
            if kname == settlement_name or settlement_name in getattr(kingdom, 'settlements', []):
                treasury = getattr(kingdom, 'treasury', 0)
                loot = min(treasury, random.randint(50, 200))
                kingdom.treasury = max(0, treasury - loot)
                if player_gold_ref:
                    player_gold_ref[0] += loot
                return f"Plundered {loot}g from {settlement_name}'s treasury!"
        return "Nothing to plunder."


# ================================================================
# SIEGE RESOLUTION — full siege battle with engines and defenses
# ================================================================

def resolve_siege(attacker_armies: list, defenses: SettlementDefenses,
                  siege_engines: List[SiegeEngine], defender_npcs: list,
                  defender_creatures: list, npcs: list,
                  terrain: str = "settlement") -> dict:
    """Resolve a full siege battle.

    Phase 1: Siege engines bombard fortifications
    Phase 2: Once walls breached (or bypassed), assault begins
    Phase 3: Lanchester battle with defense bonus for remaining fortifications

    Returns dict with result, casualties, and siege log.
    """
    from game.systems.warfare import (
        BattleField, BattleArmy, TroopUnit, Commander, Fortification,
    )

    siege_log = []
    total_attacker_size = sum(a.size for a in attacker_armies)
    total_defender_size = len([n for n in defender_npcs if n.alive])

    # Phase 1: Bombardment
    siege_log.append("=== PHASE 1: Bombardment ===")
    bombardment_rounds = 0
    max_bombardment = 5

    walls_intact = defenses.is_walled
    has_bypass = any(e.target_type == "bypass" and e.is_built and e.is_crewed
                     for e in siege_engines)

    if walls_intact and not has_bypass:
        # Must breach walls with siege engines
        operational_engines = [e for e in siege_engines
                              if e.is_built and e.is_crewed and e.damage_per_round > 0]
        if not operational_engines:
            siege_log.append("NO SIEGE ENGINES! Cannot breach walls!")
            siege_log.append(f"Settlement defense: {defenses.get_report()}")
            # Attempt assault anyway with massive penalty
            siege_log.append("Attempting direct assault on walls (very costly)...")

        while walls_intact and bombardment_rounds < max_bombardment and operational_engines:
            bombardment_rounds += 1
            siege_log.append(f"\n  Bombardment round {bombardment_rounds}:")
            for engine in operational_engines:
                result = engine.fire(defenses)
                siege_log.append(f"    {engine.engine_type}: {result}")

                # Defenders fire back (tower archers)
                if defenses.archer_count > 0:
                    archer_dmg = defenses.archer_count * random.uniform(1, 3)
                    engine.hp -= archer_dmg
                    if engine.hp <= 0:
                        siege_log.append(f"    {engine.engine_type} DESTROYED by tower archers!")
                        operational_engines.remove(engine)
                        break

            walls_intact = defenses.is_walled
            if not walls_intact:
                siege_log.append("  *** WALLS BREACHED! ***")

    elif has_bypass:
        siege_log.append("  Siege towers bypass walls!")
    else:
        siege_log.append("  Settlement has no walls — direct assault!")

    # Phase 2: Tower suppression (archers fire during assault)
    siege_log.append("\n=== PHASE 2: Assault ===")
    tower_casualties = 0
    if defenses.archer_count > 0 and walls_intact:
        # Archers in towers cause casualties during wall assault
        tower_casualties = int(defenses.archer_count * random.uniform(0.3, 0.8))
        siege_log.append(f"  Tower archers killed {tower_casualties} attackers during assault!")

    # Phase 3: Lanchester battle with fortification bonuses
    siege_log.append("\n=== PHASE 3: Battle ===")

    # Build attacker army
    atk_units = []
    atk_size = total_attacker_size - tower_casualties
    if atk_size > 0:
        melee = max(1, atk_size * 2 // 3)
        ranged = atk_size - melee
        atk_units.append(TroopUnit("infantry_sword", melee))
        if ranged > 0:
            atk_units.append(TroopUnit("archer_longbow", ranged))

    # Build defender army with fortification bonus
    def_units = []
    melee_def = sum(1 for n in defender_npcs if n.alive and
                    getattr(n, 'char_class', '') in
                    ('Fighter', 'Barbarian', 'Paladin', 'Ranger'))
    ranged_def = sum(1 for n in defender_npcs if n.alive) - melee_def
    if melee_def > 0:
        u = TroopUnit("infantry_spear", melee_def)
        # Defenders in fortified positions fight better
        u.equipment_quality *= defenses.total_defense_bonus
        def_units.append(u)
    if ranged_def > 0:
        u = TroopUnit("archer_crossbow", ranged_def)
        u.equipment_quality *= defenses.total_defense_bonus
        def_units.append(u)

    # Add creatures
    beast_count = sum(1 for c in defender_creatures if c.alive)
    if beast_count > 0:
        def_units.append(TroopUnit("war_dire_wolf", beast_count))

    if not atk_units:
        atk_units.append(TroopUnit("infantry_sword", 1))
    if not def_units:
        def_units.append(TroopUnit("infantry_sword", 1))

    # Build BattleField with fortifications
    fortifications = []
    for f in defenses.fortifications:
        if not f["breached"]:
            fort = Fortification(f["type"])
            fort.hp = f["hp"]
            fortifications.append(fort)

    atk_cmd = Commander(name="Attacker", leadership=5)
    def_cmd = Commander(name="Defender", leadership=3)
    atk_army = BattleArmy("Attacking Force", atk_units, atk_cmd)
    def_army = BattleArmy("Defenders", def_units, def_cmd,
                           is_defender=True, fortifications=fortifications)

    battlefield = BattleField(atk_army, def_army, terrain="settlement",
                               is_siege=True)
    battle_result = battlefield.resolve(max_rounds=8)

    siege_log.append(f"  Battle resolved in {battle_result['rounds']} rounds")
    siege_log.append(f"  Winner: {battle_result['winner']}")
    siege_log.append(f"  Attacker casualties: {battle_result['attacker_casualties'] + tower_casualties}")
    siege_log.append(f"  Defender casualties: {battle_result['defender_casualties']}")

    won = battle_result["winner"] == "Attacking Force"

    return {
        "won": won,
        "attacker_casualties": battle_result["attacker_casualties"] + tower_casualties,
        "defender_casualties": battle_result["defender_casualties"],
        "bombardment_rounds": bombardment_rounds,
        "walls_breached": not defenses.is_walled,
        "siege_log": siege_log,
        "battle_result": battle_result,
    }
