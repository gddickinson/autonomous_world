"""
Mine establishment and depletion system.

Resource extraction sites that appear when kingdoms invest in mining
settlements, produce ore daily, and eventually run dry.

Wired into the simulation daily update via MiningSystem.update().
"""

import random
from typing import Dict, List, Optional, Tuple


# Ore types and their relative values
ORE_TYPES = {
    "iron":   {"value": 2, "weapon_factor": 1.0},
    "copper": {"value": 1, "weapon_factor": 0.5},
    "gold":   {"value": 5, "weapon_factor": 0.0},
    "silver": {"value": 3, "weapon_factor": 0.0},
    "tin":    {"value": 1, "weapon_factor": 0.3},
}

# Thresholds for depletion warnings
DEPLETION_WARNING_PCT = 0.25   # warn at 25%
DEPLETION_CRITICAL_PCT = 0.10  # critical at 10%


class Mine:
    """A single mine at a settlement."""

    def __init__(self, settlement_name: str, ore_type: str,
                 ore_remaining: int, established_day: int):
        self.settlement_name = settlement_name
        self.ore_type = ore_type
        self.ore_remaining = ore_remaining
        self.ore_initial = ore_remaining
        self.established_day = established_day
        self.exhausted = False
        self._warned_low = False
        self._warned_critical = False

    @property
    def pct_remaining(self) -> float:
        if self.ore_initial <= 0:
            return 0.0
        return self.ore_remaining / self.ore_initial

    def to_dict(self) -> dict:
        return {
            "ore_remaining": self.ore_remaining,
            "ore_type": self.ore_type,
            "established_day": self.established_day,
            "ore_initial": self.ore_initial,
            "exhausted": self.exhausted,
        }

    @classmethod
    def from_dict(cls, settlement_name: str, data: dict) -> "Mine":
        mine = cls(
            settlement_name,
            data.get("ore_type", "iron"),
            data.get("ore_remaining", 0),
            data.get("established_day", 0),
        )
        mine.ore_initial = data.get("ore_initial", mine.ore_remaining)
        mine.exhausted = data.get("exhausted", False)
        return mine


class MiningSystem:
    """Manages all mines across the world.

    Call update() once per game day from the simulation loop.
    """

    def __init__(self):
        # settlement_name -> Mine
        self.mines: Dict[str, Mine] = {}
        self.event_log: List[str] = []
        self._prospecting_cooldown: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Main daily update
    # ------------------------------------------------------------------

    def update(self, game_day: int, governance, kingdom_ai,
               npcs: list, structures: list, world_plan=None):
        """Run mining simulation for one game day.

        Parameters
        ----------
        game_day : int
            Current in-game day.
        governance : GovernanceSystem
            Kingdom data.
        kingdom_ai : KingdomAI
            Stockpile data for weapon/gold production.
        npcs : list
            All NPC objects (to count miners).
        structures : list
            World structures (settlements).
        world_plan : WorldPlan, optional
            For checking terrain near settlements (prospecting).
        """
        self._extract_ore(game_day, governance, kingdom_ai, npcs, structures)
        self._check_depletions(game_day, governance, structures)
        self._prospecting(game_day, npcs, structures, world_plan)

    # ------------------------------------------------------------------
    # Establishment — called by kingdom_ai when investing in mining
    # ------------------------------------------------------------------

    def establish_mine(self, settlement_name: str, game_day: int,
                       ore_type: str = None) -> Optional[Mine]:
        """Create a new mine at a mining settlement.

        Returns the new Mine, or None if the settlement already has one.
        """
        if settlement_name in self.mines:
            existing = self.mines[settlement_name]
            if not existing.exhausted:
                return None  # already has an active mine

        if ore_type is None:
            ore_type = random.choice(list(ORE_TYPES.keys()))

        ore_amount = random.randint(500, 2000)
        mine = Mine(settlement_name, ore_type, ore_amount, game_day)
        self.mines[settlement_name] = mine

        ore_display = ore_type.capitalize()
        self.event_log.append(
            f"New {ore_display} mine established at {settlement_name}! "
            f"(estimated {ore_amount} units of ore)")
        return mine

    # ------------------------------------------------------------------
    # Daily extraction
    # ------------------------------------------------------------------

    def _extract_ore(self, game_day: int, governance, kingdom_ai,
                     npcs: list, structures: list):
        """Miners extract ore daily, adding to kingdom stockpiles."""
        struct_map = {s.name: s for s in structures}

        for sname, mine in self.mines.items():
            if mine.exhausted or mine.ore_remaining <= 0:
                continue

            # Count miners at this settlement
            miner_count = self._count_miners(sname, npcs, governance)
            if miner_count == 0:
                continue

            # Each miner extracts 1-3 ore per day
            extracted = 0
            for _ in range(miner_count):
                extracted += random.randint(1, 3)
            extracted = min(extracted, mine.ore_remaining)
            mine.ore_remaining -= extracted

            if extracted <= 0:
                continue

            # Find which kingdom owns this settlement
            kname = self._find_owning_kingdom(sname, governance)
            if not kname:
                continue

            # Apply ore to kingdom stockpiles
            ore_info = ORE_TYPES.get(mine.ore_type, {})
            weapon_factor = ore_info.get("weapon_factor", 0.0)
            value = ore_info.get("value", 1)

            sp = kingdom_ai.stockpiles.get(kname)
            if sp:
                # Ore that can make weapons goes to weapon stockpile
                sp.weapons += extracted * weapon_factor
                # All ore contributes to treasury (trade value)
                sp.gold_reserve += extracted * value * 0.1

    def _count_miners(self, settlement_name: str, npcs: list,
                      governance) -> int:
        """Count living miners associated with a settlement."""
        count = 0
        for npc in npcs:
            if not npc.alive:
                continue
            prof = getattr(npc, 'profession', '')
            if prof not in ('Miner', 'Prospector'):
                continue
            home = getattr(npc, 'home_settlement', '')
            faction = getattr(npc, 'faction', '')
            if home == settlement_name or faction == settlement_name:
                count += 1
        return count

    def _find_owning_kingdom(self, settlement_name: str,
                             governance) -> Optional[str]:
        """Find which kingdom owns a settlement."""
        for kname, kingdom in governance.kingdoms.items():
            if settlement_name in kingdom.settlements:
                return kname
        return None

    # ------------------------------------------------------------------
    # Depletion checks
    # ------------------------------------------------------------------

    def _check_depletions(self, game_day: int, governance, structures: list):
        """Check for mines running low or exhausted."""
        for sname, mine in self.mines.items():
            if mine.exhausted:
                continue

            pct = mine.pct_remaining

            # Exhaustion
            if mine.ore_remaining <= 0:
                mine.exhausted = True
                self.event_log.append(
                    f"{sname} mine exhausted — miners seek new employment")
                self._handle_exhaustion(sname, governance, structures)
                continue

            # Low warning (25%)
            if pct <= DEPLETION_WARNING_PCT and not mine._warned_low:
                mine._warned_low = True
                pct_display = int(pct * 100)
                self.event_log.append(
                    f"{sname}'s ore deposit is running low "
                    f"({pct_display}% remaining)")

            # Critical warning (10%)
            if pct <= DEPLETION_CRITICAL_PCT and not mine._warned_critical:
                mine._warned_critical = True
                pct_display = int(pct * 100)
                self.event_log.append(
                    f"{sname}'s mine is nearly depleted! "
                    f"Only {pct_display}% ore remains")

    def _handle_exhaustion(self, settlement_name: str, governance,
                           structures: list):
        """When a mine is exhausted, remove mining specialization."""
        # Find settlement in world structures and downgrade specialization
        for s in structures:
            if s.name == settlement_name:
                if getattr(s, 'specialization', '') == 'mining':
                    s.specialization = 'general'
                break

        # Reduce kingdom income from this settlement
        kname = self._find_owning_kingdom(settlement_name, governance)
        if kname and kname in governance.kingdoms:
            kingdom = governance.kingdoms[kname]
            income = getattr(kingdom, 'income_per_day', 0)
            kingdom.income_per_day = max(0, income - 5)

    # ------------------------------------------------------------------
    # Prospecting — discovery of new ore deposits
    # ------------------------------------------------------------------

    def _prospecting(self, game_day: int, npcs: list, structures: list,
                     world_plan=None):
        """Prospector NPCs have a small daily chance to discover new ore."""
        # Find all prospectors
        prospectors = [
            npc for npc in npcs
            if npc.alive and getattr(npc, 'profession', '') == 'Prospector'
        ]

        for npc in prospectors:
            # 2% daily chance per prospector
            if random.random() > 0.02:
                continue

            # Cooldown: same NPC can't discover twice within 30 days
            last_discovery = self._prospecting_cooldown.get(npc.name, -999)
            if game_day - last_discovery < 30:
                continue

            # Find nearest settlement that doesn't have an active mine
            home = getattr(npc, 'home_settlement', '')
            best_settlement = None
            best_dist = float('inf')

            for s in structures:
                sname = s.name
                # Skip settlements that already have an active mine
                if sname in self.mines and not self.mines[sname].exhausted:
                    continue

                # Check if settlement is near mountains (via specialization
                # or just proximity to the prospector)
                dist = ((npc.x - s.x) ** 2 + (npc.y - s.y) ** 2) ** 0.5
                if dist < best_dist and dist < 200:
                    best_dist = dist
                    best_settlement = s

            if best_settlement is None:
                continue

            # Check terrain if world_plan is available — prefer mountain areas
            if world_plan and hasattr(world_plan, 'height_map'):
                sx, sy = best_settlement.x, best_settlement.y
                # Check if there are mountains nearby by sampling elevations
                has_mountains = self._check_mountains_nearby(
                    sx, sy, world_plan)
                if not has_mountains:
                    # 75% chance to skip non-mountain areas
                    if random.random() < 0.75:
                        continue

            # Discovery!
            ore_type = random.choice(list(ORE_TYPES.keys()))
            mine = self.establish_mine(
                best_settlement.name, game_day, ore_type)
            if mine:
                self._prospecting_cooldown[npc.name] = game_day
                ore_display = ore_type.capitalize()
                self.event_log.append(
                    f"New {ore_display} vein discovered near "
                    f"{best_settlement.name}!")

    def _check_mountains_nearby(self, sx: int, sy: int,
                                world_plan) -> bool:
        """Check if there are mountains near a position using world_plan."""
        # Sample a few points around the settlement
        for dx in range(-50, 51, 25):
            for dy in range(-50, 51, 25):
                px, py = sx + dx, sy + dy
                if (0 <= px < world_plan.width and
                        0 <= py < world_plan.height):
                    if hasattr(world_plan, 'get_elevation'):
                        elev = world_plan.get_elevation(px, py)
                        if elev > 0.75:  # mountain threshold
                            return True
        return False

    # ------------------------------------------------------------------
    # Auto-establish mines for mining settlements at game start
    # ------------------------------------------------------------------

    def auto_establish_for_mining_settlements(self, structures: list,
                                              game_day: int = 0):
        """Create mines for settlements with 'mining' specialization.

        Called once during initialization so mining towns start with ore.
        """
        for s in structures:
            spec = getattr(s, 'specialization', 'general')
            if spec == 'mining' and s.name not in self.mines:
                self.establish_mine(s.name, game_day)

    # ------------------------------------------------------------------
    # Event log
    # ------------------------------------------------------------------

    def get_event_log(self) -> List[str]:
        """Return and clear accumulated log messages."""
        msgs = list(self.event_log)
        self.event_log.clear()
        return msgs

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize for save games."""
        return {
            sname: mine.to_dict()
            for sname, mine in self.mines.items()
        }

    def from_save(self, data: dict):
        """Load from save game data."""
        self.mines.clear()
        for sname, mine_data in data.items():
            self.mines[sname] = Mine.from_dict(sname, mine_data)
