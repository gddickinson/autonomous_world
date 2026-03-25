"""Siege Commands — attacker and defender order implementations.

Split from siege_player.py for modularity. Each function takes a SiegeState
and modifies it, returning a status message.
"""

import random
from typing import Optional

# Command effect tables
COMMAND_EFFECTS = {
    # ATTACKER commands
    "catapult_fire":   {"wall_damage": 15, "defender_casualties": 2},
    "ram_gate":        {"gate_damage": 20, "attacker_casualties": 1},
    "assault_breach":  {"defender_casualties": 5, "attacker_casualties": 3},
    "rally_troops":    {"morale_boost": 15, "attacker_casualties": 0},
    # DEFENDER commands
    "repair_walls":    {"wall_repair": 10, "attacker_casualties": 0},
    "boiling_oil":     {"attacker_casualties": 6, "defender_casualties": 0},
    "archer_volley":   {"attacker_casualties": 4, "defender_casualties": 0},
    "sortie":          {"engine_damage": 25, "defender_casualties": 2,
                        "attacker_casualties": 3},
}


# ================================================================
# ATTACKER COMMANDS
# ================================================================

def cmd_catapult_fire(siege) -> str:
    """Fire catapults at walls or into the settlement."""
    if siege.catapult_hp <= 0:
        return "All catapults destroyed!"

    effect = COMMAND_EFFECTS["catapult_fire"]
    dmg = effect["wall_damage"] + random.randint(-3, 5)
    kills = effect["defender_casualties"] + random.randint(0, 2)

    if siege.walls_breached:
        kills += random.randint(1, 4)
        siege.defender_troops = max(0, siege.defender_troops - kills)
        msg = f"Catapults fire into {siege.settlement_name}! {kills} defenders fall."
    else:
        siege.wall_hp -= dmg
        siege.defender_troops = max(0, siege.defender_troops - kills)
        msg = f"Catapults strike the walls! {dmg} wall damage, {kills} defenders hit."
        if siege.wall_hp <= 0:
            siege.wall_hp = 0
            siege.walls_breached = True
            msg += " THE WALLS ARE BREACHED!"

    siege.defender_morale -= 3
    siege.messages.append(msg)
    return msg


def cmd_ram_gate(siege) -> str:
    """Use battering ram against the gate."""
    if siege.ram_hp <= 0:
        return "The battering ram is destroyed!"
    if siege.gate_breached:
        return "The gate is already breached!"

    effect = COMMAND_EFFECTS["ram_gate"]
    dmg = effect["gate_damage"] + random.randint(-5, 5)
    casualties = effect["attacker_casualties"] + random.randint(0, 2)

    siege.gate_hp -= dmg
    siege.attacker_troops = max(0, siege.attacker_troops - casualties)
    msg = f"Ram strikes the gate! {dmg} gate damage. {casualties} crew lost to arrows."

    if siege.gate_hp <= 0:
        siege.gate_hp = 0
        siege.gate_breached = True
        msg += " THE GATE IS BROKEN!"
        siege.defender_morale -= 10

    siege.messages.append(msg)
    return msg


def cmd_assault_breach(siege) -> str:
    """Send troops through a breach in walls or gate."""
    if not siege.walls_breached and not siege.gate_breached:
        return "No breach to assault! Break the walls or gate first."

    effect = COMMAND_EFFECTS["assault_breach"]
    atk_loss = effect["attacker_casualties"] + random.randint(0, 4)
    def_loss = effect["defender_casualties"] + random.randint(0, 3)

    if siege.walls_breached and siege.gate_breached:
        def_loss += random.randint(1, 3)
        atk_loss -= 1

    siege.attacker_troops = max(0, siege.attacker_troops - atk_loss)
    siege.defender_troops = max(0, siege.defender_troops - def_loss)
    siege.defender_morale -= 5

    msg = (f"Troops storm the breach! "
           f"Attackers lose {atk_loss}, defenders lose {def_loss}.")
    siege.messages.append(msg)
    return msg


def cmd_rally_troops(siege) -> str:
    """Rally retreating soldiers, boosting morale."""
    boost = COMMAND_EFFECTS["rally_troops"]["morale_boost"]
    siege.attacker_morale = min(100, siege.attacker_morale + boost)
    msg = f"You rally the troops! Attacker morale rises to {siege.attacker_morale}."
    siege.messages.append(msg)
    return msg


# ================================================================
# DEFENDER COMMANDS
# ================================================================

def cmd_repair_walls(siege) -> str:
    """Repair damaged walls."""
    if siege.wall_hp >= siege.wall_max_hp:
        return "Walls are at full strength!"

    repair = COMMAND_EFFECTS["repair_walls"]["wall_repair"]
    repair += random.randint(-2, 3)
    siege.wall_hp = min(siege.wall_max_hp, siege.wall_hp + repair)

    was_breached = siege.walls_breached
    if siege.wall_hp > 0:
        siege.walls_breached = False

    msg = f"Workers repair the walls (+{repair} HP, now {siege.wall_hp}/{siege.wall_max_hp})."
    if was_breached and not siege.walls_breached:
        msg += " Breach sealed!"
    siege.messages.append(msg)
    return msg


def cmd_boiling_oil(siege) -> str:
    """Pour boiling oil on attackers below the walls."""
    effect = COMMAND_EFFECTS["boiling_oil"]
    kills = effect["attacker_casualties"] + random.randint(0, 4)
    siege.attacker_troops = max(0, siege.attacker_troops - kills)
    siege.attacker_morale -= 5

    msg = f"Boiling oil poured on the attackers! {kills} attackers scalded!"
    siege.messages.append(msg)
    return msg


def cmd_archer_volley(siege) -> str:
    """Command archers to volley fire."""
    effect = COMMAND_EFFECTS["archer_volley"]
    kills = effect["attacker_casualties"] + random.randint(0, 3)
    siege.attacker_troops = max(0, siege.attacker_troops - kills)

    msg = f"Archers volley! {kills} attackers fall to arrows."
    siege.messages.append(msg)
    return msg


def cmd_sortie(siege) -> str:
    """Send defenders on a sortie to attack siege engines."""
    effect = COMMAND_EFFECTS["sortie"]
    atk_loss = effect["attacker_casualties"] + random.randint(0, 3)
    def_loss = effect["defender_casualties"] + random.randint(0, 2)
    eng_dmg = effect["engine_damage"] + random.randint(-5, 10)

    siege.attacker_troops = max(0, siege.attacker_troops - atk_loss)
    siege.defender_troops = max(0, siege.defender_troops - def_loss)
    siege.catapult_hp = max(0, siege.catapult_hp - eng_dmg)
    siege.attacker_morale -= 5

    msg = (f"Sortie! Defenders charge out. "
           f"Attackers lose {atk_loss}, defenders lose {def_loss}. "
           f"Siege engines take {eng_dmg} damage.")

    if siege.catapult_hp <= 0:
        msg += " All catapults destroyed!"
    siege.messages.append(msg)
    return msg
