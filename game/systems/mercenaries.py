"""Mercenary Companies — hireable combat companions from taverns.

Four mercenary company types:
- Swords for Hire (fighters) — balanced melee damage and HP
- Shadow Guild (rogues) — high damage, low HP, flanking bonus
- War Mages (casters) — ranged spell damage, fragile
- Iron Shield (defenders) — high defense, low damage, taunt

Hired at taverns for gold. Contract lasts 30 game days.
Mercenaries follow the player, fight alongside them, and can die permanently.
"""

import math
import random
from typing import List, Dict, Optional, Tuple


# ================================================================
# COMPANY DEFINITIONS
# ================================================================

MERCENARY_COMPANIES = {
    "swords_for_hire": {
        "name": "Swords for Hire",
        "role": "fighter",
        "base_cost": 80,
        "hp": 60,
        "attack": 10,
        "defense": 6,
        "speed": 2.0,
        "attack_range": 1.5,
        "damage_type": "slash",
        "contract_days": 30,
        "description": "Veteran swordsmen. Balanced fighters, reliable in a scrap.",
        "size_range": (2, 5),
    },
    "shadow_guild": {
        "name": "Shadow Guild",
        "role": "rogue",
        "base_cost": 120,
        "hp": 35,
        "attack": 14,
        "defense": 3,
        "speed": 2.8,
        "attack_range": 1.5,
        "damage_type": "pierce",
        "contract_days": 30,
        "description": "Assassins and cutthroats. Deadly but fragile.",
        "size_range": (1, 3),
    },
    "war_mages": {
        "name": "War Mages",
        "role": "caster",
        "base_cost": 200,
        "hp": 30,
        "attack": 16,
        "defense": 2,
        "speed": 1.8,
        "attack_range": 7.0,
        "damage_type": "fire",
        "contract_days": 30,
        "description": "Battle mages who rain fire on your enemies. Expensive.",
        "size_range": (1, 2),
    },
    "iron_shield": {
        "name": "Iron Shield",
        "role": "defender",
        "base_cost": 50,
        "hp": 80,
        "attack": 5,
        "defense": 12,
        "speed": 1.5,
        "attack_range": 1.5,
        "damage_type": "blunt",
        "contract_days": 30,
        "description": "Heavy-armored shield bearers. They take hits so you don't.",
        "size_range": (3, 6),
    },
}


# ================================================================
# MERCENARY UNIT
# ================================================================

class Mercenary:
    """A single mercenary combatant that follows and fights for the player."""

    def __init__(self, name: str, company_type: str):
        info = MERCENARY_COMPANIES[company_type]
        self.name = name
        self.company_type = company_type
        self.role = info["role"]
        self.alive = True
        self.hp = info["hp"]
        self.max_hp = info["hp"]
        self.attack_damage = info["attack"]
        self.defense = info["defense"]
        self.speed = info["speed"]
        self.attack_range = info["attack_range"]
        self.damage_type = info["damage_type"]
        self.x = 0.0
        self.y = 0.0
        self.attack_timer = 0.0
        self.combat_target = None
        self.facing = (0.0, -1.0)

    def take_damage(self, amount: int):
        """Take damage, die if HP reaches 0."""
        actual = max(1, amount - self.defense)
        self.hp -= actual
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
        return actual

    def heal(self, amount: int):
        """Heal HP up to max."""
        self.hp = min(self.max_hp, self.hp + amount)

    def dist_to(self, other) -> float:
        """Distance to another entity."""
        dx = self.x - getattr(other, 'x', 0)
        dy = self.y - getattr(other, 'y', 0)
        return math.sqrt(dx * dx + dy * dy)

    @property
    def status(self) -> str:
        """Short status string."""
        pct = self.hp / max(1, self.max_hp)
        if not self.alive:
            return "DEAD"
        if pct < 0.25:
            return "critical"
        if pct < 0.5:
            return "wounded"
        return "healthy"


# ================================================================
# MERCENARY NAME GENERATOR
# ================================================================

_MERC_FIRST = [
    "Gareth", "Bryn", "Theron", "Kael", "Dorin", "Vash", "Seren",
    "Mira", "Torval", "Haldor", "Nyx", "Renna", "Cael", "Orla",
    "Fenwick", "Zara", "Brin", "Aldric", "Lysara", "Tarn",
]
_MERC_TITLES = {
    "fighter": ["the Bold", "Ironarm", "Shieldbreaker", "the Steady"],
    "rogue": ["the Shadow", "Quickblade", "Silentfoot", "the Unseen"],
    "caster": ["Flamecaller", "the Wise", "Stormhand", "Sparkfinger"],
    "defender": ["the Wall", "Ironback", "Shieldbearer", "the Stalwart"],
}


def _generate_merc_name(role: str) -> str:
    """Generate a random mercenary name."""
    first = random.choice(_MERC_FIRST)
    title = random.choice(_MERC_TITLES.get(role, ["the Hired"]))
    return f"{first} {title}"


# ================================================================
# MERCENARY COMPANY (hired group)
# ================================================================

class MercenaryCompany:
    """A hired group of mercenaries under contract."""

    def __init__(self, company_type: str, size: int, hire_day: float):
        info = MERCENARY_COMPANIES[company_type]
        self.company_type = company_type
        self.company_name = info["name"]
        self.contract_days = info["contract_days"]
        self.hire_day = hire_day
        self.cost = self._calc_cost(company_type, size)

        self.members: List[Mercenary] = []
        for _ in range(size):
            name = _generate_merc_name(info["role"])
            self.members.append(Mercenary(name, company_type))

    @staticmethod
    def _calc_cost(company_type: str, size: int) -> int:
        """Calculate hire cost based on type and group size."""
        base = MERCENARY_COMPANIES[company_type]["base_cost"]
        return int(base * size * random.uniform(0.8, 1.2))

    @property
    def alive_members(self) -> List[Mercenary]:
        return [m for m in self.members if m.alive]

    @property
    def alive_count(self) -> int:
        return len(self.alive_members)

    def is_expired(self, current_day: float) -> bool:
        """Has the contract expired?"""
        return (current_day - self.hire_day) >= self.contract_days

    def days_remaining(self, current_day: float) -> float:
        """Days left on contract."""
        return max(0, self.contract_days - (current_day - self.hire_day))

    def renew(self, current_day: float) -> int:
        """Renew contract. Returns cost."""
        cost = self._calc_cost(self.company_type, self.alive_count)
        self.hire_day = current_day
        self.cost = cost
        return cost


# ================================================================
# MERCENARY MANAGER — top-level controller
# ================================================================

class MercenaryManager:
    """Manages all hired mercenary companies for the player."""

    def __init__(self):
        self.companies: List[MercenaryCompany] = []

    def hire(self, company_type: str, player, current_day: float) -> str:
        """Hire a mercenary company. Returns status message."""
        if company_type not in MERCENARY_COMPANIES:
            return f"Unknown company type: {company_type}"

        info = MERCENARY_COMPANIES[company_type]
        size = random.randint(*info["size_range"])
        cost = MercenaryCompany._calc_cost(company_type, size)

        gold = getattr(player, 'gold', 0)
        if gold < cost:
            return (f"The {info['name']} want {cost}g for {size} fighters. "
                    f"You only have {gold}g.")

        player.gold -= cost
        company = MercenaryCompany(company_type, size, current_day)
        self.companies.append(company)

        names = ", ".join(m.name for m in company.members)
        return (f"Hired {info['name']} ({size} fighters) for {cost}g! "
                f"Contract: {info['contract_days']} days. Members: {names}")

    def update(self, dt: float, player, enemies: list,
               current_day: float) -> List[str]:
        """Update all mercenaries: follow player, fight enemies, expire contracts.

        Returns list of status messages.
        """
        messages: List[str] = []

        # Remove expired contracts
        expired = [c for c in self.companies if c.is_expired(current_day)]
        for comp in expired:
            alive = comp.alive_count
            if alive > 0:
                messages.append(
                    f"{comp.company_name} contract expired. "
                    f"{alive} mercenaries depart.")
        self.companies = [c for c in self.companies
                          if not c.is_expired(current_day)]

        # Update each mercenary
        px = getattr(player, 'x', 0.0)
        py = getattr(player, 'y', 0.0)

        for company in self.companies:
            for merc in company.alive_members:
                msg = self._update_merc(merc, dt, px, py, enemies)
                if msg:
                    messages.append(msg)

        return messages

    def _update_merc(self, merc: Mercenary, dt: float,
                     px: float, py: float,
                     enemies: list) -> Optional[str]:
        """Update a single mercenary: follow player or fight."""
        if not merc.alive:
            return None

        # Attack timer cooldown
        if merc.attack_timer > 0:
            merc.attack_timer -= dt

        # Find nearest enemy within engagement range (12 tiles from player)
        best_enemy = None
        best_dist = 12.0
        for ent in enemies:
            if not getattr(ent, 'alive', True):
                continue
            dist = merc.dist_to(ent)
            if dist < best_dist:
                best_dist = dist
                best_enemy = ent

        if best_enemy is not None:
            merc.combat_target = best_enemy
            return self._fight(merc, best_enemy, dt)
        else:
            merc.combat_target = None
            # Follow the player
            self._follow_player(merc, dt, px, py)
            return None

    def _follow_player(self, merc: Mercenary, dt: float,
                       px: float, py: float):
        """Move mercenary toward player, maintaining formation distance."""
        dx = px - merc.x
        dy = py - merc.y
        dist = math.sqrt(dx * dx + dy * dy)

        # Stay 2-4 tiles from player
        if dist > 4.0:
            d = dist or 1
            move = min(merc.speed * dt, dist - 2.0)
            merc.x += (dx / d) * move
            merc.y += (dy / d) * move
            merc.facing = (dx / d, dy / d)

    def _fight(self, merc: Mercenary, enemy, dt: float) -> Optional[str]:
        """Mercenary engages an enemy. Returns message on hit."""
        dist = merc.dist_to(enemy)
        is_ranged = merc.attack_range > 3.0

        # Ranged kiting
        if is_ranged and dist < merc.attack_range * 0.4:
            dx = merc.x - getattr(enemy, 'x', 0)
            dy = merc.y - getattr(enemy, 'y', 0)
            d = math.sqrt(dx * dx + dy * dy) or 1
            merc.x += (dx / d) * merc.speed * dt
            merc.y += (dy / d) * merc.speed * dt
            return None

        # Move closer if out of range
        if dist > merc.attack_range:
            dx = getattr(enemy, 'x', 0) - merc.x
            dy = getattr(enemy, 'y', 0) - merc.y
            d = dist or 1
            move = min(merc.speed * dt, dist - merc.attack_range * 0.8)
            merc.x += (dx / d) * move
            merc.y += (dy / d) * move
            merc.facing = (dx / d, dy / d)
            return None

        # Attack
        if merc.attack_timer > 0:
            return None

        merc.attack_timer = 1.0
        damage = merc.attack_damage + random.randint(-2, 2)
        damage = max(1, damage)

        # Rogue flanking bonus
        if merc.role == "rogue":
            if hasattr(enemy, 'facing'):
                tx, ty = getattr(enemy, 'facing', (0, 1))
                dx = merc.x - getattr(enemy, 'x', 0)
                dy = merc.y - getattr(enemy, 'y', 0)
                d = math.sqrt(dx * dx + dy * dy) or 1
                dot = tx * (dx / d) + ty * (dy / d)
                if dot < -0.3:
                    damage = int(damage * 1.8)

        # Defender taunt: enemies prefer attacking defenders
        if merc.role == "defender":
            enemy._last_attacker = merc

        # Apply damage
        target_name = getattr(enemy, 'name', getattr(enemy, 'kind', 'enemy'))

        if hasattr(enemy, 'take_damage'):
            enemy.take_damage(damage)

        from game.systems.combat import _emit_damage
        _emit_damage(enemy, damage,
                     is_kill=not getattr(enemy, 'alive', True))

        if not getattr(enemy, 'alive', True):
            return f"{merc.name} slew {target_name}! ({damage} dmg)"
        return None

    def get_all_mercenaries(self) -> List[Mercenary]:
        """Return all living mercenaries across all companies."""
        result = []
        for comp in self.companies:
            result.extend(comp.alive_members)
        return result

    def get_status(self, current_day: float) -> List[str]:
        """Get status lines for all companies."""
        lines = []
        for comp in self.companies:
            alive = comp.alive_count
            total = len(comp.members)
            days = comp.days_remaining(current_day)
            lines.append(
                f"{comp.company_name}: {alive}/{total} alive, "
                f"{days:.0f} days remaining"
            )
            for m in comp.members:
                status = m.status
                lines.append(f"  {m.name} [{status}] HP:{m.hp}/{m.max_hp}")
        return lines

    @property
    def total_alive(self) -> int:
        return sum(c.alive_count for c in self.companies)


# ================================================================
# TAVERN DIALOG INTEGRATION
# ================================================================

def get_mercenary_dialog_options(npc, player, merc_manager: Optional['MercenaryManager'] = None
                                 ) -> List[Tuple[str, str]]:
    """Return dialog options for hiring mercenaries at a tavern.

    Should be called from dialog_trees.py for innkeeper/tavern NPCs.
    """
    prof = getattr(npc, 'profession', '')
    if prof.lower() not in ('innkeeper', 'barkeep', 'tavern_keeper'):
        return []

    options = [("I'm looking to hire fighters.", "merc_hire_menu")]
    if merc_manager and merc_manager.total_alive > 0:
        options.append(("How are my mercenaries doing?", "merc_status"))
    return options


def build_mercenary_hire_dialog() -> Dict[str, any]:
    """Build dialog lines for the mercenary hiring menu."""
    lines = {}
    responses = []
    for key, info in MERCENARY_COMPANIES.items():
        lo, hi = info["size_range"]
        cost_lo = int(info["base_cost"] * lo * 0.8)
        cost_hi = int(info["base_cost"] * hi * 1.2)
        text = (f"Hire {info['name']} ({lo}-{hi} fighters, "
                f"{cost_lo}-{cost_hi}g) — {info['description']}")
        responses.append((text, f"merc_hire_{key}"))
    responses.append(("Never mind.", "goodbye"))
    return {
        "text": ("Several groups of sellswords are drinking here. "
                 "Who catches your eye?"),
        "responses": responses,
    }
