"""Siege Gameplay — player participation in kingdom siege battles.

When the player is near a besieged settlement during a kingdom war,
they can join as attacker or defender and issue orders that affect
the siege outcome.

Attacker commands:
  1 - Direct catapult fire at walls
  2 - Order battering ram to breach gate
  3 - Send troops to assault a breach
  4 - Rally retreating soldiers

Defender commands:
  1 - Repair damaged walls
  2 - Pour boiling oil on attackers
  3 - Command archers to volley
  4 - Sortie: send defenders out to attack siege engines

Siege resolves over multiple rounds. Player commands shift the balance.
Command implementations live in siege_commands.py.
"""

import math
import random
from typing import Dict, List, Optional, Tuple

from game.systems.siege_commands import (
    cmd_catapult_fire, cmd_ram_gate, cmd_assault_breach, cmd_rally_troops,
    cmd_repair_walls, cmd_boiling_oil, cmd_archer_volley, cmd_sortie,
)


# ================================================================
# SIEGE CONSTANTS
# ================================================================

SIEGE_JOIN_RANGE = 30.0       # tiles from settlement center to join
ROUND_DURATION = 10.0         # seconds per siege round
MAX_ROUNDS = 20               # siege ends after this many rounds
PLAYER_ORDER_COOLDOWN = 3.0   # seconds between player orders


# ================================================================
# SIEGE STATE
# ================================================================

class SiegeState:
    """Tracks the current state of a player-participated siege."""

    def __init__(self, settlement_name: str, settlement_pos: Tuple[float, float],
                 attacker_kingdom: str, defender_kingdom: str,
                 attacker_troops: int, defender_troops: int,
                 wall_hp: int = 100, gate_hp: int = 80):
        self.settlement_name = settlement_name
        self.settlement_x, self.settlement_y = settlement_pos
        self.attacker_kingdom = attacker_kingdom
        self.defender_kingdom = defender_kingdom

        # Forces
        self.attacker_troops = attacker_troops
        self.defender_troops = defender_troops
        self.attacker_max = attacker_troops
        self.defender_max = defender_troops

        # Fortifications
        self.wall_hp = wall_hp
        self.wall_max_hp = wall_hp
        self.gate_hp = gate_hp
        self.gate_max_hp = gate_hp
        self.walls_breached = False
        self.gate_breached = False

        # Siege engines (attacker side)
        self.catapults = max(1, attacker_troops // 30)
        self.rams = 1
        self.catapult_hp = 50 * self.catapults
        self.ram_hp = 80

        # Battle state
        self.round_num = 0
        self.round_timer = ROUND_DURATION
        self.attacker_morale = 80
        self.defender_morale = 90
        self.active = True
        self.player_side: Optional[str] = None  # "attacker" or "defender"
        self.order_cooldown = 0.0

        # Log
        self.messages: List[str] = []
        self.result: Optional[str] = None  # "attacker_wins" / "defender_wins"

    @property
    def attacker_strength(self) -> float:
        """Attacker combat strength ratio (0-1)."""
        return self.attacker_troops / max(1, self.attacker_max)

    @property
    def defender_strength(self) -> float:
        """Defender combat strength ratio (0-1)."""
        return self.defender_troops / max(1, self.defender_max)


# ================================================================
# SIEGE MANAGER — player-facing siege gameplay
# ================================================================

class PlayerSiegeManager:
    """Manages player participation in siege battles."""

    def __init__(self):
        self.active_siege: Optional[SiegeState] = None

    def can_join_siege(self, player, wars: list,
                       settlements: dict) -> Optional[dict]:
        """Check if the player is near a besieged settlement.

        Returns siege info dict or None.
        """
        if self.active_siege is not None and self.active_siege.active:
            return None  # already in a siege

        px = getattr(player, 'x', 0)
        py = getattr(player, 'y', 0)

        for war in wars:
            if getattr(war, 'ended', True):
                continue
            target = getattr(war, 'target_settlement', None)
            if target is None:
                continue

            sett = settlements.get(target)
            if sett is None:
                continue

            sx = getattr(sett, 'x', getattr(sett, 'center_x', 0))
            sy = getattr(sett, 'y', getattr(sett, 'center_y', 0))
            dist = math.sqrt((px - sx) ** 2 + (py - sy) ** 2)

            if dist <= SIEGE_JOIN_RANGE:
                return {
                    "settlement": target,
                    "pos": (sx, sy),
                    "attacker": getattr(war, 'attacker', 'unknown'),
                    "defender": getattr(war, 'defender', 'unknown'),
                    "attacker_troops": getattr(war, 'attacker_army_size', 50),
                    "defender_troops": getattr(war, 'defender_army_size', 30),
                    "wall_hp": self._get_wall_hp(sett),
                }
        return None

    def _get_wall_hp(self, settlement) -> int:
        """Get wall HP from settlement defenses."""
        defenses = getattr(settlement, 'defenses', None)
        if defenses and hasattr(defenses, 'wall_hp'):
            return max(20, defenses.wall_hp)
        kind = getattr(settlement, 'kind', 'village')
        defaults = {"hamlet": 0, "village": 40, "town": 80,
                    "city": 150, "castle": 200}
        return defaults.get(kind, 60)

    def start_siege(self, siege_info: dict, side: str) -> str:
        """Player joins the siege on the given side."""
        if side not in ("attacker", "defender"):
            return "Choose 'attacker' or 'defender'."

        wall_hp = siege_info.get("wall_hp", 80)
        self.active_siege = SiegeState(
            settlement_name=siege_info["settlement"],
            settlement_pos=siege_info["pos"],
            attacker_kingdom=siege_info["attacker"],
            defender_kingdom=siege_info["defender"],
            attacker_troops=siege_info.get("attacker_troops", 50),
            defender_troops=siege_info.get("defender_troops", 30),
            wall_hp=wall_hp,
            gate_hp=max(20, wall_hp // 2),
        )
        self.active_siege.player_side = side

        side_name = (siege_info["attacker"] if side == "attacker"
                     else siege_info["defender"])
        msg = (f"You join the siege of {siege_info['settlement']} "
               f"as {side} ({side_name})!\n"
               f"Attackers: {self.active_siege.attacker_troops} troops, "
               f"{self.active_siege.catapults} catapults, "
               f"{self.active_siege.rams} ram\n"
               f"Defenders: {self.active_siege.defender_troops} troops, "
               f"walls {wall_hp} HP\n"
               f"Press 1-4 to issue orders.")
        self.active_siege.messages.append(msg)
        return msg

    def issue_order(self, order_num: int) -> str:
        """Player issues an order (1-4). Returns result message."""
        siege = self.active_siege
        if siege is None or not siege.active:
            return "No active siege."

        if siege.order_cooldown > 0:
            return f"Wait {siege.order_cooldown:.1f}s before next order."

        siege.order_cooldown = PLAYER_ORDER_COOLDOWN

        if siege.player_side == "attacker":
            return self._attacker_order(order_num)
        else:
            return self._defender_order(order_num)

    def _attacker_order(self, num: int) -> str:
        """Dispatch attacker command to siege_commands module."""
        s = self.active_siege
        if num == 1:
            return cmd_catapult_fire(s)
        elif num == 2:
            return cmd_ram_gate(s)
        elif num == 3:
            return cmd_assault_breach(s)
        elif num == 4:
            return cmd_rally_troops(s)
        return "Invalid order. Press 1-4."

    def _defender_order(self, num: int) -> str:
        """Dispatch defender command to siege_commands module."""
        s = self.active_siege
        if num == 1:
            return cmd_repair_walls(s)
        elif num == 2:
            return cmd_boiling_oil(s)
        elif num == 3:
            return cmd_archer_volley(s)
        elif num == 4:
            return cmd_sortie(s)
        return "Invalid order. Press 1-4."

    # ================================================================
    # ROUND RESOLUTION
    # ================================================================

    def update(self, dt: float) -> List[str]:
        """Advance the siege. Called each frame. Returns new messages."""
        siege = self.active_siege
        if siege is None or not siege.active:
            return []

        messages = []

        # Order cooldown
        if siege.order_cooldown > 0:
            siege.order_cooldown = max(0, siege.order_cooldown - dt)

        # Round timer
        siege.round_timer -= dt
        if siege.round_timer <= 0:
            siege.round_timer = ROUND_DURATION
            siege.round_num += 1
            messages.extend(self._resolve_round())

        return messages

    def _resolve_round(self) -> List[str]:
        """Resolve one siege round — background attrition + morale."""
        siege = self.active_siege
        msgs = [f"--- Round {siege.round_num} ---"]

        # Defenders on walls shoot at attackers
        if not siege.walls_breached:
            arrow_kills = random.randint(1, 3)
            siege.attacker_troops = max(0, siege.attacker_troops - arrow_kills)

        # Attackers skirmish through breaches
        if siege.walls_breached or siege.gate_breached:
            skirmish_atk = random.randint(1, 3)
            skirmish_def = random.randint(2, 5)
            siege.attacker_troops = max(0, siege.attacker_troops - skirmish_atk)
            siege.defender_troops = max(0, siege.defender_troops - skirmish_def)

        # Morale decay based on strength
        if siege.attacker_strength < 0.3:
            siege.attacker_morale -= 10
        elif siege.attacker_strength < 0.5:
            siege.attacker_morale -= 3

        if siege.defender_strength < 0.3:
            siege.defender_morale -= 10
        elif siege.defender_strength < 0.5:
            siege.defender_morale -= 3

        if siege.walls_breached and siege.gate_breached:
            siege.defender_morale -= 5

        # Status line
        msgs.append(
            f"ATK: {siege.attacker_troops} (morale {siege.attacker_morale}) | "
            f"DEF: {siege.defender_troops} (morale {siege.defender_morale}) | "
            f"Walls: {siege.wall_hp}/{siege.wall_max_hp} "
            f"Gate: {siege.gate_hp}/{siege.gate_max_hp}"
        )

        result = self._check_victory()
        if result:
            msgs.append(result)

        siege.messages.extend(msgs)
        return msgs

    def _check_victory(self) -> Optional[str]:
        """Check if the siege has been won or lost."""
        siege = self.active_siege
        if siege is None:
            return None

        if siege.defender_troops <= 0 or siege.defender_morale <= 0:
            siege.active = False
            siege.result = "attacker_wins"
            return (f"{siege.attacker_kingdom} captures "
                    f"{siege.settlement_name}! Defenders routed.")

        if siege.attacker_troops <= 0 or siege.attacker_morale <= 0:
            siege.active = False
            siege.result = "defender_wins"
            return (f"{siege.defender_kingdom} repels the siege of "
                    f"{siege.settlement_name}! Attackers retreat.")

        if siege.round_num >= MAX_ROUNDS:
            siege.active = False
            siege.result = "defender_wins"
            return (f"Siege of {siege.settlement_name} fails after "
                    f"{MAX_ROUNDS} rounds. Attackers withdraw.")

        return None

    def get_command_prompt(self) -> Optional[str]:
        """Return the command prompt showing available orders."""
        siege = self.active_siege
        if siege is None or not siege.active:
            return None

        header = (f"[SIEGE: {siege.settlement_name}] "
                  f"ATK:{siege.attacker_troops} DEF:{siege.defender_troops} "
                  f"Walls:{siege.wall_hp} Gate:{siege.gate_hp}")

        if siege.player_side == "attacker":
            return (header + "\n"
                    "  1-Catapult  2-Ram Gate  3-Assault Breach  4-Rally")
        else:
            return (header + "\n"
                    "  1-Repair Walls  2-Boiling Oil  "
                    "3-Archer Volley  4-Sortie")

    def leave_siege(self) -> str:
        """Player leaves the siege."""
        if self.active_siege is None:
            return "Not in a siege."
        name = self.active_siege.settlement_name
        self.active_siege = None
        return f"You withdraw from the siege of {name}."

    @property
    def is_active(self) -> bool:
        return (self.active_siege is not None
                and self.active_siege.active)
