"""
Body part and damage type system.

Every entity (NPC, Creature, Player) can have a Body composed of BodyParts.
Damage is applied to specific body parts, creating Wounds that bleed, get
infected, and heal over time.  Damaged body parts impose activity modifiers
(speed, combat, work, crafting).

Equipment durability is also tracked here: weapons lose durability on hit,
armor absorbs damage but degrades, and shields block hits to specific parts.
"""

import random
from typing import Dict, List, Optional


# ================================================================
# DAMAGE TYPE PROPERTIES
# ================================================================

DAMAGE_TYPES: Dict[str, dict] = {
    "blunt":   {"bleed": False, "infection_risk": 0.05, "heal_days": 30,
                "armor_factor": 0.5},
    "slash":   {"bleed": True,  "infection_risk": 0.1,  "heal_days": 15,
                "armor_factor": 0.7},
    "pierce":  {"bleed": True,  "infection_risk": 0.15, "heal_days": 20,
                "armor_factor": 0.4},
    "fire":    {"bleed": False, "infection_risk": 0.2,  "heal_days": 45,
                "armor_factor": 0.3, "scar": True},
    "acid":    {"bleed": False, "infection_risk": 0.25, "heal_days": 50,
                "armor_factor": 0.1, "scar": True},
    "frost":   {"bleed": False, "infection_risk": 0.1,  "heal_days": 25,
                "armor_factor": 0.6},
    "poison":  {"bleed": False, "infection_risk": 0.0,  "heal_days": 10,
                "armor_factor": 0.0, "systemic": True},
    "necrotic": {"bleed": False, "infection_risk": 0.0, "heal_days": 999,
                 "armor_factor": 0.0, "divine_only": True},
}

# Body-part targeting weights when no specific part is given.
# torso 40%, left_arm / right_arm 15% each, left_leg / right_leg 10% each,
# head 10%.
_HUMANOID_TARGET_WEIGHTS: Dict[str, float] = {
    "head": 0.10,
    "torso": 0.40,
    "left_arm": 0.15,
    "right_arm": 0.15,
    "left_leg": 0.10,
    "right_leg": 0.10,
}

_QUADRUPED_TARGET_WEIGHTS: Dict[str, float] = {
    "head": 0.10,
    "torso": 0.40,
    "front_left": 0.15,
    "front_right": 0.15,
    "rear_left": 0.10,
    "rear_right": 0.10,
}

# Armor degradation rate per damage type (higher = degrades faster).
_ARMOR_DEGRADE_RATE: Dict[str, float] = {
    "blunt": 0.8,
    "slash": 1.0,
    "pierce": 0.6,
    "fire": 1.5,
    "acid": 2.0,
    "frost": 0.4,
    "poison": 0.0,
    "necrotic": 0.0,
}


# ================================================================
# WOUND
# ================================================================

class Wound:
    """A single wound on a body part."""
    __slots__ = ("damage_type", "severity", "bleeding", "infected",
                 "healing_progress", "timestamp")

    def __init__(self, damage_type: str, severity: float, timestamp: float = 0.0):
        self.damage_type = damage_type
        self.severity = max(0.0, min(1.0, severity))
        self.bleeding = damage_type in ("slash", "pierce")
        self.infected = False
        self.healing_progress = 0.0  # 0..1 — reaches 1.0 => healed
        self.timestamp = timestamp


# ================================================================
# BODY PART
# ================================================================

class BodyPart:
    """A single body part with HP, status, and wound list."""
    __slots__ = ("name", "hp", "max_hp", "status", "wounds")

    def __init__(self, name: str, max_hp: int):
        self.name = name
        self.hp = max_hp
        self.max_hp = max_hp
        self.status: str = "healthy"  # healthy, injured, broken, severed, burned
        self.wounds: List[Wound] = []

    def _update_status(self):
        """Recalculate status from remaining HP."""
        ratio = self.hp / self.max_hp if self.max_hp > 0 else 0.0
        if ratio <= 0:
            self.status = "severed"
        elif ratio <= 0.20:
            self.status = "broken"
        elif ratio <= 0.50:
            self.status = "injured"
        else:
            # Check for burn status from fire/acid wounds
            for w in self.wounds:
                if w.damage_type in ("fire", "acid") and w.severity > 0.3:
                    self.status = "burned"
                    return
            self.status = "healthy"


# ================================================================
# BODY — attached to each entity
# ================================================================

# Base part HP templates (before scaling to entity max_hp).
_HUMANOID_PARTS = {
    "head":      30,
    "torso":     50,
    "left_arm":  25,
    "right_arm": 25,
    "left_leg":  30,
    "right_leg": 30,
}

_QUADRUPED_PARTS = {
    "head":        25,
    "torso":       60,
    "front_left":  20,
    "front_right": 20,
    "rear_left":   20,
    "rear_right":  20,
}

_BASE_TOTAL_HP = {
    "humanoid":  sum(_HUMANOID_PARTS.values()),   # 190
    "quadruped": sum(_QUADRUPED_PARTS.values()),   # 165
}


class Body:
    """Collection of body parts for an entity."""

    __slots__ = ("parts", "entity_type")

    def __init__(self, entity_type: str = "humanoid", scale_hp: int = 0):
        """Create a body.

        Parameters
        ----------
        entity_type : str
            ``"humanoid"`` or ``"quadruped"``.
        scale_hp : int
            If > 0, scale all part HPs proportionally so that the total
            equals *scale_hp*.  If 0, use the default template values.
        """
        self.entity_type = entity_type

        if entity_type == "quadruped":
            template = _QUADRUPED_PARTS
        else:
            template = _HUMANOID_PARTS

        base_total = _BASE_TOTAL_HP.get(entity_type, _BASE_TOTAL_HP["humanoid"])
        factor = (scale_hp / base_total) if scale_hp > 0 else 1.0

        self.parts: Dict[str, BodyPart] = {}
        for name, base_hp in template.items():
            hp = max(1, int(base_hp * factor))
            self.parts[name] = BodyPart(name, hp)

    # ---------- aggregate properties ----------

    @property
    def total_hp(self) -> int:
        return sum(p.hp for p in self.parts.values())

    @property
    def max_total_hp(self) -> int:
        return sum(p.max_hp for p in self.parts.values())

    @property
    def is_dead(self) -> bool:
        head = self.parts.get("head")
        torso = self.parts.get("torso")
        if head and head.hp <= 0:
            return True
        if torso and torso.hp <= 0:
            return True
        return False

    # ---------- activity modifiers ----------

    def get_activity_modifiers(self) -> Dict[str, float]:
        """Return activity->multiplier dict based on body state."""
        return get_activity_modifiers(self)


# ================================================================
# ACTIVITY MODIFIERS  (standalone function, also used by Body method)
# ================================================================

def get_activity_modifiers(body: Body) -> Dict[str, float]:
    """Return dict of activity -> modifier based on body state.

    All values are multipliers (1.0 = no penalty).
    """
    mods: Dict[str, float] = {}

    # Arms
    arm_names = (["left_arm", "right_arm"] if body.entity_type == "humanoid"
                 else ["front_left", "front_right"])
    for arm in arm_names:
        p = body.parts.get(arm)
        if p and p.status in ("broken", "severed"):
            mods["combat"] = mods.get("combat", 1.0) * 0.5
            mods["craft"] = mods.get("craft", 1.0) * 0.5
            mods["carry"] = mods.get("carry", 1.0) * 0.5
        elif p and p.status == "injured":
            mods["combat"] = mods.get("combat", 1.0) * 0.8
            mods["craft"] = mods.get("craft", 1.0) * 0.8

    # Legs
    leg_names = (["left_leg", "right_leg"] if body.entity_type == "humanoid"
                 else ["rear_left", "rear_right"])
    for leg in leg_names:
        p = body.parts.get(leg)
        if p and p.status in ("broken", "severed"):
            mods["speed"] = mods.get("speed", 1.0) * 0.5
        elif p and p.status == "injured":
            mods["speed"] = mods.get("speed", 1.0) * 0.8

    # Head
    head = body.parts.get("head")
    if head and head.status == "injured":
        mods["study"] = mods.get("study", 1.0) * 0.5
        mods["combat"] = mods.get("combat", 1.0) * 0.7
    elif head and head.status in ("broken",):
        mods["study"] = mods.get("study", 1.0) * 0.2
        mods["combat"] = mods.get("combat", 1.0) * 0.4

    # Torso
    torso = body.parts.get("torso")
    if torso and torso.status == "injured":
        mods["work"] = mods.get("work", 1.0) * 0.7
        mods["exhaustion_rate"] = mods.get("exhaustion_rate", 1.0) * 2.0
    elif torso and torso.status in ("broken",):
        mods["work"] = mods.get("work", 1.0) * 0.3
        mods["exhaustion_rate"] = mods.get("exhaustion_rate", 1.0) * 3.0

    return mods


# ================================================================
# EQUIPMENT DURABILITY helpers
# ================================================================

def degrade_weapon(entity, amount: int = 1):
    """Reduce equipped weapon durability.  Breaks at 0."""
    weapon = getattr(entity, 'equipped_weapon', None)
    if weapon is None:
        return
    dur = getattr(weapon, 'durability', None)
    if dur is None:
        return  # item has no durability tracking
    weapon.durability = max(0, dur - amount)
    if weapon.durability <= 0:
        weapon.name = f"Broken {weapon.name}"
        weapon.damage = 0


def degrade_armor(entity, damage_type: str, amount: int = 1):
    """Reduce equipped armor durability based on damage type."""
    armor = getattr(entity, 'equipped_armor', None)
    if armor is None:
        return
    dur = getattr(armor, 'durability', None)
    if dur is None:
        return
    rate = _ARMOR_DEGRADE_RATE.get(damage_type, 1.0)
    loss = max(1, int(amount * rate))
    armor.durability = max(0, dur - loss)
    if armor.durability <= 0:
        armor.name = f"Broken {armor.name}"
        armor.defense = 0


def repair_equipment(item, amount: int = 20):
    """Restore durability to an item (used by blacksmiths)."""
    max_dur = getattr(item, 'max_durability', 100)
    cur = getattr(item, 'durability', max_dur)
    item.durability = min(max_dur, cur + amount)
    # Remove "Broken" prefix if repaired above 0
    if item.durability > 0 and item.name.startswith("Broken "):
        item.name = item.name[7:]


# ================================================================
# BODY DAMAGE SYSTEM
# ================================================================

class BodyDamageSystem:
    """Manages body-level damage, wound healing, infection, and modifiers."""

    def __init__(self):
        self._heal_timer = 0.0
        self._heal_interval = 60.0  # process healing every 60 game-seconds

    # ----------------------------------------------------------
    # apply_damage — the main entry point for hurting an entity
    # ----------------------------------------------------------

    def apply_damage(self, entity, amount: int, damage_type: str = "blunt",
                     target_part: Optional[str] = None,
                     timestamp: float = 0.0) -> int:
        """Apply damage to an entity's body.

        If the entity has no ``body`` attribute (or it is None), falls back
        to the simple ``entity.take_damage(amount)`` path for backward
        compatibility.

        Returns the actual damage dealt.
        """
        body: Optional[Body] = getattr(entity, 'body', None)
        if body is None:
            return entity.take_damage(amount)

        # --- resolve target part ---
        part = self._pick_target_part(body, target_part)
        if part is None:
            return entity.take_damage(amount)

        # --- armor reduction ---
        dt_props = DAMAGE_TYPES.get(damage_type, DAMAGE_TYPES["blunt"])
        armor_factor = dt_props["armor_factor"]
        armor_def = 0
        equipped_armor = getattr(entity, 'equipped_armor', None)
        if equipped_armor is not None:
            armor_def = getattr(equipped_armor, 'defense', 0)
        reduction = int(armor_def * armor_factor)
        actual = max(1, amount - reduction)

        # Degrade armor
        if armor_def > 0:
            degrade_armor(entity, damage_type)

        # --- apply to part ---
        part.hp = max(0, part.hp - actual)
        severity = min(1.0, actual / part.max_hp) if part.max_hp > 0 else 1.0
        wound = Wound(damage_type, severity, timestamp=timestamp)

        # Infection chance
        if random.random() < dt_props["infection_risk"]:
            wound.infected = True

        part.wounds.append(wound)
        part._update_status()

        # --- sync entity-level HP from body ---
        entity.hp = body.total_hp
        if body.is_dead:
            entity.hp = 0
            entity.alive = False

        return actual

    # ----------------------------------------------------------
    # update — called every tick from the simulation loop
    # ----------------------------------------------------------

    def update(self, dt: float, entities):
        """Heal wounds over time, progress infections, drain bleeding."""
        self._heal_timer += dt
        if self._heal_timer < self._heal_interval:
            return
        self._heal_timer -= self._heal_interval
        elapsed_days = self._heal_interval / 86400.0  # game-seconds to days

        for entity in entities:
            body: Optional[Body] = getattr(entity, 'body', None)
            if body is None or not getattr(entity, 'alive', False):
                continue

            is_resting = getattr(entity, 'state', '') == "sleeping"
            has_healer = getattr(entity, '_healer_nearby', False)
            heal_mult = 1.0
            if is_resting:
                heal_mult *= 2.0
            if has_healer:
                heal_mult *= 2.0

            for part in body.parts.values():
                healed_wounds: List[int] = []
                for idx, wound in enumerate(part.wounds):
                    # --- bleeding ---
                    if wound.bleeding and wound.healing_progress < 0.3:
                        bleed_dmg = max(1, int(wound.severity * 2))
                        part.hp = max(0, part.hp - bleed_dmg)

                    # --- infection progression ---
                    if wound.infected and wound.healing_progress < 0.5:
                        # 10% chance of sepsis per in-game day
                        if random.random() < 0.10 * elapsed_days:
                            # Sepsis: heavy torso damage
                            torso = body.parts.get("torso")
                            if torso and torso is not part:
                                torso.hp = max(0, torso.hp - 5)
                                torso._update_status()

                    # --- healing ---
                    dt_props = DAMAGE_TYPES.get(wound.damage_type,
                                                DAMAGE_TYPES["blunt"])
                    heal_days = dt_props["heal_days"]
                    if dt_props.get("divine_only"):
                        # Necrotic wounds don't heal naturally
                        continue
                    progress_per_day = 1.0 / max(1, heal_days)
                    wound.healing_progress += progress_per_day * elapsed_days * heal_mult
                    wound.healing_progress = min(1.0, wound.healing_progress)

                    # Stop bleeding once partly healed
                    if wound.bleeding and wound.healing_progress >= 0.3:
                        wound.bleeding = False

                    # Clear infection once more than half healed
                    if wound.infected and wound.healing_progress >= 0.5:
                        wound.infected = False

                    if wound.healing_progress >= 1.0:
                        healed_wounds.append(idx)
                        # Restore a fraction of max_hp
                        restore = max(1, int(part.max_hp * wound.severity * 0.5))
                        part.hp = min(part.max_hp, part.hp + restore)

                # Remove fully healed wounds (iterate in reverse)
                for idx in reversed(healed_wounds):
                    part.wounds.pop(idx)

                part._update_status()

            # Sync entity HP
            entity.hp = body.total_hp
            if body.is_dead:
                entity.hp = 0
                entity.alive = False

    # ----------------------------------------------------------
    # modifier helpers — query body state for gameplay effects
    # ----------------------------------------------------------

    def get_speed_modifier(self, entity) -> float:
        """Movement speed multiplier based on leg damage."""
        body: Optional[Body] = getattr(entity, 'body', None)
        if body is None:
            return 1.0
        mods = body.get_activity_modifiers()
        return mods.get("speed", 1.0)

    def get_work_modifier(self, entity) -> float:
        """Work capability multiplier based on arm/torso damage."""
        body: Optional[Body] = getattr(entity, 'body', None)
        if body is None:
            return 1.0
        mods = body.get_activity_modifiers()
        work = mods.get("work", 1.0)
        craft = mods.get("craft", 1.0)
        return min(work, craft)

    def get_combat_modifier(self, entity) -> float:
        """Combat effectiveness multiplier based on arm/head damage."""
        body: Optional[Body] = getattr(entity, 'body', None)
        if body is None:
            return 1.0
        mods = body.get_activity_modifiers()
        return mods.get("combat", 1.0)

    # ----------------------------------------------------------
    # internals
    # ----------------------------------------------------------

    @staticmethod
    def _pick_target_part(body: Body,
                          target_part: Optional[str]) -> Optional[BodyPart]:
        """Choose which body part gets hit."""
        if target_part and target_part in body.parts:
            return body.parts[target_part]

        # Weighted random pick
        if body.entity_type == "quadruped":
            weights = _QUADRUPED_TARGET_WEIGHTS
        else:
            weights = _HUMANOID_TARGET_WEIGHTS

        # Filter to parts that aren't already severed
        candidates = []
        cum_weights = []
        total = 0.0
        for name, w in weights.items():
            p = body.parts.get(name)
            if p and p.status != "severed":
                candidates.append(p)
                total += w
                cum_weights.append(total)
        if not candidates:
            return None

        r = random.random() * total
        for i, cw in enumerate(cum_weights):
            if r <= cw:
                return candidates[i]
        return candidates[-1]


# ================================================================
# CONVENIENCE: attach a Body to an entity
# ================================================================

def ensure_body(entity) -> Body:
    """Ensure *entity* has a ``body`` attribute and return it.

    - NPCs / Players → humanoid
    - Creatures → quadruped for beasts, humanoid for humanoids
    """
    body = getattr(entity, 'body', None)
    if body is not None:
        return body

    from game.core.npc import NPC
    from game.core.player import Player
    from game.core.creature import Creature

    max_hp = getattr(entity, 'max_hp', 100)

    if isinstance(entity, (NPC, Player)):
        body = Body("humanoid", scale_hp=max_hp)
    elif isinstance(entity, Creature):
        monster_type = getattr(entity, 'monster_type', 'beast')
        if monster_type in ("humanoid", "undead", "fiend"):
            body = Body("humanoid", scale_hp=max_hp)
        else:
            body = Body("quadruped", scale_hp=max_hp)
    else:
        body = Body("humanoid", scale_hp=max_hp)

    entity.body = body
    # Keep entity.hp in sync
    entity.hp = body.total_hp
    return body
