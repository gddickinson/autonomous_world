"""
Capture System — any entity can capture any other entity.

Capture replaces killing as an alternative combat outcome. Instead of
reducing HP to 0, a captor can attempt to subdue and restrain a target.

Capture methods:
  GRAPPLE:    Physical restraint (STR vs STR). Works on similar-size targets.
  NET:        Thrown net (DEX check). Works on smaller targets.
  TRAP:       Pre-placed trap (INT to set, target walks into it).
  LASSO:      Rope throw (DEX + animal_handling). Good for beasts.
  MAGIC:      Hold Person/Animal spells (spell save DC).
  SURRENDER:  Target surrenders voluntarily (morale broken, HP low).
  OVERWHELM:  Multiple captors vs one target (auto-capture at 3:1 ratio).

Captive states:
  RESTRAINED: Tied/chained, can't move, can attempt escape (STR check).
  LEASHED:    Led by captor, moves with them but can't flee. Beasts/animals.
  CAGED:      In a cage/cell. Requires cage item or dungeon cell.
  SUBDUED:    Knocked out / spell-held. Temporary, will wake up.
  SURRENDERED: Gave up willingly. Cooperative but may flee if unguarded.

Post-capture options:
  - Lead/transport to a location
  - Break/train (domestication system)
  - Sell (to slavers, beast traders, or as livestock)
  - Ransom (NPCs — demand gold from their faction)
  - Conscript (force into army)
  - Eat (for beasts/livestock)
  - Sacrifice (at altar — religious/dark magic)
  - Free (release — gain reputation or make an ally)
  - Interrogate (extract information — INT check)
"""

import random
import math
from typing import Optional, Tuple, List


# ================================================================
# CAPTURE METHODS
# ================================================================

CAPTURE_METHODS = {
    "grapple": {
        "check": "strength",        # STR vs STR contest
        "dc_base": 10,
        "size_penalty": 5,           # per size category larger than captor
        "size_bonus": 3,             # per size category smaller
        "requires_item": None,
        "description": "Physically wrestle and pin the target",
    },
    "net": {
        "check": "dexterity",
        "dc_base": 12,
        "size_penalty": 3,
        "size_bonus": 2,
        "requires_item": "Net",
        "description": "Throw a net to entangle the target",
    },
    "lasso": {
        "check": "dexterity",
        "dc_base": 13,
        "size_penalty": 4,
        "size_bonus": 3,
        "requires_item": "Rope",
        "skill_bonus": "animal_handling",
        "description": "Lasso with rope — especially effective on beasts",
    },
    "trap": {
        "check": "intelligence",
        "dc_base": 10,
        "size_penalty": 5,
        "size_bonus": 0,
        "requires_item": "Trap",
        "description": "Pre-placed trap — target must walk into it",
    },
    "overwhelm": {
        "check": None,              # auto-success at 3:1 ratio
        "dc_base": 0,
        "description": "Multiple captors overwhelm a single target",
    },
    "surrender": {
        "check": None,
        "dc_base": 0,
        "description": "Target surrenders voluntarily",
    },
}


# ================================================================
# CAPTIVE STATE
# ================================================================

class CaptiveState:
    """Tracks capture status of an entity."""

    RESTRAINED = "restrained"   # tied up, can't move
    LEASHED = "leashed"         # led by captor, moves with them
    CAGED = "caged"             # in a cage or cell
    SUBDUED = "subdued"         # knocked out / spell-held (temporary)
    SURRENDERED = "surrendered" # gave up willingly

    def __init__(self):
        self.is_captured = False
        self.state = ""
        self.captor_name = ""       # who captured this entity
        self.captor_entity = None   # reference to captor (for following)
        self.escape_attempts = 0
        self.escape_cooldown = 0.0  # seconds until next escape attempt
        self.capture_day = 0        # game day of capture
        self.morale = 50            # 0=broken, 100=defiant

    def capture(self, captor_name: str, captor_entity=None,
                method: str = "grapple") -> str:
        """Mark this entity as captured."""
        self.is_captured = True
        self.captor_name = captor_name
        self.captor_entity = captor_entity

        if method == "surrender":
            self.state = self.SURRENDERED
            self.morale = 20
        elif method in ("net", "lasso", "trap"):
            self.state = self.RESTRAINED
            self.morale = 40
        elif method == "overwhelm":
            self.state = self.RESTRAINED
            self.morale = 30
        else:
            self.state = self.RESTRAINED
            self.morale = 50

        return f"Captured by {captor_name} ({self.state})"

    def attempt_escape(self, captive_strength: int, captive_dex: int,
                        guard_present: bool = True) -> Tuple[bool, str]:
        """Captive tries to escape. Returns (success, message)."""
        if not self.is_captured:
            return False, "Not captured."
        if self.escape_cooldown > 0:
            return False, f"Must wait {self.escape_cooldown:.0f}s before trying again."

        self.escape_attempts += 1
        self.escape_cooldown = 30.0  # 30 seconds between attempts

        # DC based on state
        dc = {
            self.RESTRAINED: 15,
            self.LEASHED: 12,
            self.CAGED: 20,
            self.SUBDUED: 18,
            self.SURRENDERED: 8,
        }.get(self.state, 15)

        if guard_present:
            dc += 5

        # STR or DEX check (use higher)
        str_mod = (captive_strength - 10) // 2
        dex_mod = (captive_dex - 10) // 2
        mod = max(str_mod, dex_mod)
        roll = random.randint(1, 20) + mod

        if roll >= dc:
            self.is_captured = False
            self.state = ""
            self.captor_name = ""
            self.captor_entity = None
            return True, f"Escaped! (rolled {roll} vs DC {dc})"
        else:
            self.morale = max(0, self.morale - 5)
            return False, f"Failed to escape (rolled {roll} vs DC {dc})"

    def set_leashed(self):
        """Change to leashed state (being led)."""
        if self.is_captured:
            self.state = self.LEASHED

    def set_caged(self):
        """Put in cage or dungeon cell."""
        if self.is_captured:
            self.state = self.CAGED
            self.escape_cooldown = 60.0  # harder to escape cage quickly

    def free(self) -> str:
        """Release the captive."""
        name = self.captor_name
        self.is_captured = False
        self.state = ""
        self.captor_name = ""
        self.captor_entity = None
        self.morale = min(100, self.morale + 30)
        return f"Released from captivity by {name}"

    def update(self, dt: float):
        """Tick escape cooldown and morale."""
        if self.escape_cooldown > 0:
            self.escape_cooldown = max(0, self.escape_cooldown - dt)

        # Morale slowly drops in captivity
        if self.is_captured and self.state != self.SURRENDERED:
            self.morale = max(0, self.morale - dt * 0.01)

        # Very low morale → surrender
        if self.is_captured and self.morale <= 5 and self.state != self.SURRENDERED:
            self.state = self.SURRENDERED


# ================================================================
# CAPTURE ATTEMPT RESOLUTION
# ================================================================

def attempt_capture(captor, target, method: str = "grapple",
                     allies: list = None) -> Tuple[bool, str]:
    """Attempt to capture a target entity.

    Args:
        captor: Entity doing the capturing
        target: Entity being captured
        method: Capture method (grapple, net, lasso, trap, overwhelm, surrender)
        allies: List of allies helping (for overwhelm)

    Returns:
        (success, message)
    """
    from game.systems.domestication import get_creature_size, SIZE_ORDER

    method_data = CAPTURE_METHODS.get(method, CAPTURE_METHODS["grapple"])

    # Check for required items
    req_item = method_data.get("requires_item")
    if req_item:
        inv = getattr(captor, 'inventory', getattr(captor, 'npc_inventory', []))
        has_item = any(getattr(i, 'name', str(i)) == req_item for i in inv)
        if not has_item:
            return False, f"Need {req_item} for {method} capture."

    # Check target HP — must be below 50% for most methods
    target_hp = getattr(target, 'hp', 10)
    target_max = getattr(target, 'max_hp', 10)
    if method not in ("trap", "surrender", "overwhelm") and target_hp > target_max * 0.5:
        return False, "Target must be weakened first (HP below 50%)."

    # Already captured?
    captive = getattr(target, 'captive_state', None)
    if captive and captive.is_captured:
        return False, "Target is already captured."

    # Surrender check — target gives up if morale is very low
    if method == "surrender":
        morale = getattr(target, 'morale', 50)
        if morale > 20 and target_hp > target_max * 0.2:
            return False, "Target refuses to surrender."
        # Auto-capture
        if not hasattr(target, 'captive_state'):
            target.captive_state = CaptiveState()
        msg = target.captive_state.capture(
            getattr(captor, 'name', 'Unknown'), captor, "surrender")
        return True, f"Target surrendered! {msg}"

    # Overwhelm check — 3:1 ratio auto-captures
    if method == "overwhelm":
        ally_count = len(allies) if allies else 0
        total = 1 + ally_count
        if total >= 3:
            if not hasattr(target, 'captive_state'):
                target.captive_state = CaptiveState()
            msg = target.captive_state.capture(
                getattr(captor, 'name', 'Unknown'), captor, "overwhelm")
            return True, f"Overwhelmed by {total} captors! {msg}"
        return False, f"Need at least 3 captors to overwhelm (have {total})."

    # Size check
    captor_size = get_creature_size(captor)
    target_size = get_creature_size(target)
    c_idx = SIZE_ORDER.index(captor_size) if captor_size in SIZE_ORDER else 2
    t_idx = SIZE_ORDER.index(target_size) if target_size in SIZE_ORDER else 2
    size_diff = t_idx - c_idx  # positive = target is bigger

    # Ability check
    check_attr = method_data["check"]
    if check_attr:
        scores = getattr(captor, 'ability_scores',
                        getattr(captor, 'attributes', {}))
        attr_val = scores.get(check_attr, 10) if isinstance(scores, dict) else 10
        mod = (attr_val - 10) // 2

        # Skill bonus
        skill_name = method_data.get("skill_bonus")
        if skill_name:
            skills = getattr(captor, 'skills',
                           getattr(captor, 'npc_skills', {}))
            mod += skills.get(skill_name, 0)

        # Size modifiers
        if size_diff > 0:
            mod -= size_diff * method_data.get("size_penalty", 5)
        elif size_diff < 0:
            mod += abs(size_diff) * method_data.get("size_bonus", 3)

        dc = method_data["dc_base"]
        # Target CR increases DC
        cr = getattr(target, 'cr', 0.25)
        dc += int(cr * 2)

        roll = random.randint(1, 20) + mod

        if roll >= dc:
            if not hasattr(target, 'captive_state'):
                target.captive_state = CaptiveState()
            msg = target.captive_state.capture(
                getattr(captor, 'name', 'Unknown'), captor, method)
            return True, f"Capture success! (rolled {roll} vs DC {dc}) {msg}"
        else:
            return False, f"Capture failed (rolled {roll} vs DC {dc})"

    return False, "Unknown capture method."


# ================================================================
# POST-CAPTURE OPTIONS
# ================================================================

def ransom_captive(captive, captor_gold_ref: list,
                    faction_treasury: dict = None) -> str:
    """Demand ransom for a captured NPC. Returns message."""
    name = getattr(captive, 'name', 'Unknown')
    title = getattr(captive, 'title', 'commoner')
    faction = getattr(captive, 'faction', '')

    ransom = {"commoner": 10, "guard": 25, "knight": 100,
              "lord": 500, "duke": 1000, "monarch": 5000,
              }.get(title, 20)

    if faction_treasury and faction in faction_treasury:
        available = faction_treasury[faction]
        if available >= ransom:
            faction_treasury[faction] -= ransom
            captor_gold_ref[0] += ransom
            # Free the captive
            if hasattr(captive, 'captive_state'):
                captive.captive_state.free()
            return f"Ransomed {name} ({title}) for {ransom}g!"
        else:
            return f"{faction} can't afford {ransom}g ransom for {name}."
    else:
        captor_gold_ref[0] += ransom // 2  # sell to slavers for half
        return f"Sold {name} for {ransom // 2}g (no faction to ransom)."


def interrogate_captive(captor, captive) -> str:
    """Extract information from a captive NPC."""
    int_score = getattr(captor, 'ability_scores', {}).get('intelligence', 10)
    cha_score = getattr(captor, 'ability_scores', {}).get('charisma', 10)
    mod = max((int_score - 10) // 2, (cha_score - 10) // 2)

    captive_state = getattr(captive, 'captive_state', None)
    if not captive_state or not captive_state.is_captured:
        return "Not a captive."

    # Morale affects willingness to talk
    dc = 12 if captive_state.morale < 30 else 16
    roll = random.randint(1, 20) + mod

    if roll >= dc:
        # Extract knowledge
        known = getattr(captive, 'known_info', [])
        if known:
            info = random.choice(known)
            return f"{getattr(captive, 'name', 'Captive')} reveals: '{info}'"
        memories = getattr(captive, 'memories', [])
        if memories:
            mem = random.choice(memories)
            text = mem.get('text', '') if isinstance(mem, dict) else str(mem)
            return f"{getattr(captive, 'name', 'Captive')} says: '{text[:60]}'"
        return f"{getattr(captive, 'name', 'Captive')} has nothing useful to share."
    else:
        captive_state.morale = min(100, captive_state.morale + 5)
        return f"{getattr(captive, 'name', 'Captive')} refuses to talk (rolled {roll} vs DC {dc})"
