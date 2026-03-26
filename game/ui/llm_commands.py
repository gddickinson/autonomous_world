"""LLM console command processing and execution.

Handles both LLM-powered interpretation and keyword fallback
for the in-game natural language console.
"""

import re
import time
from game.settings import GREEN, YELLOW, RED


# Keyword patterns for fallback (no LLM) mode
_GOTO_PATTERN = re.compile(
    r"(?:go\s+to|travel\s+to|head\s+to|walk\s+to|move\s+to)\s+(.+)",
    re.IGNORECASE,
)
_ATTACK_PATTERN = re.compile(
    r"(?:attack|fight|kill|target)\s+(?:the\s+)?(?:nearest\s+)?(.+)",
    re.IGNORECASE,
)
_CAST_PATTERN = re.compile(
    r"(?:cast|use)\s+(.+)", re.IGNORECASE
)
_TRADE_PATTERN = re.compile(
    r"(?:trade|buy|sell|shop|merchant)", re.IGNORECASE
)
_STATUS_PATTERN = re.compile(
    r"(?:status|stats|health|hp|info)\b", re.IGNORECASE
)
_AREA_PATTERN = re.compile(
    r"(?:where\s+am\s+i|this\s+area|describe|look\s+around|surroundings)",
    re.IGNORECASE,
)
_HELP_PATTERN = re.compile(r"(?:help|commands|what\s+can)", re.IGNORECASE)


def process_command(console, text: str, game):
    """Process a natural language command."""
    if game.llm.enabled:
        _process_with_llm(console, text, game)
    else:
        _process_keyword(console, text, game)


# ------------------------------------------------------------------
# LLM-powered command processing
# ------------------------------------------------------------------

def _process_with_llm(console, text: str, game):
    """Send the command to the LLM for interpretation."""
    player = game.player
    px, py = int(player.x), int(player.y)

    # Find nearby settlement
    nearby_settlement = ""
    for s in game.world.structures:
        dist = abs(s.x - px) + abs(s.y - py)
        if dist < s.radius + 5:
            nearby_settlement = s.name
            break

    # Known settlement names
    settlement_names = [s.name for s in game.world.structures[:20]]

    prompt = (
        f"You are the command interpreter for a fantasy RPG game. "
        f"The player typed: \"{text}\"\n\n"
        f"Player state: HP={int(player.hp)}/{player.max_hp}, "
        f"Energy={int(player.energy)}/{player.max_energy}, "
        f"Gold={player.gold}, Level={player.level}, "
        f"Class={player.char_class}\n"
        f"Position: ({px}, {py}), Near: {nearby_settlement or 'wilderness'}\n"
        f"Known settlements: {', '.join(settlement_names)}\n\n"
        f"Respond with EXACTLY one line in this format:\n"
        f"ACTION:goto:SettlementName\n"
        f"ACTION:attack:CreatureKind\n"
        f"ACTION:cast:SpellName\n"
        f"ACTION:trade\n"
        f"ACTION:status\n"
        f"ACTION:area_info\n"
        f"INFO:your response text here\n\n"
        f"Use ACTION for commands, INFO for questions/descriptions."
    )

    req_id = f"console_{time.time()}"
    console._pending_request_id = req_id
    game.llm.request(
        req_id, prompt,
        callback=lambda resp: _handle_llm_response(console, resp, game),
        priority=5,
    )
    console.output_lines.append(("info", "Processing..."))


def _handle_llm_response(console, response: str, game):
    """Parse and execute LLM response."""
    response = response.strip()

    if response.startswith("ACTION:"):
        action_part = response[7:]
        parts = action_part.split(":", 1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        executors = {
            "goto": lambda: do_goto(console, arg.strip(), game),
            "attack": lambda: do_attack(console, arg.strip(), game),
            "cast": lambda: do_cast(console, arg.strip(), game),
            "trade": lambda: do_trade(console, game),
            "status": lambda: do_status(console, game),
            "area_info": lambda: do_area_info(console, game),
        }
        handler = executors.get(action)
        if handler:
            handler()
        else:
            console.output_lines.append(
                ("response", f"Unknown action: {action}"))
    elif response.startswith("INFO:"):
        console.output_lines.append(("response", response[5:].strip()))
    else:
        console.output_lines.append(("response", response))


# ------------------------------------------------------------------
# Keyword fallback processing
# ------------------------------------------------------------------

def _process_keyword(console, text: str, game):
    """Simple keyword matching when no LLM is available."""
    if _HELP_PATTERN.search(text):
        do_help(console)
        return

    m = _GOTO_PATTERN.search(text)
    if m:
        do_goto(console, m.group(1).strip(), game)
        return

    m = _ATTACK_PATTERN.search(text)
    if m:
        do_attack(console, m.group(1).strip(), game)
        return

    m = _CAST_PATTERN.search(text)
    if m:
        do_cast(console, m.group(1).strip(), game)
        return

    if _TRADE_PATTERN.search(text):
        do_trade(console, game)
        return

    if _STATUS_PATTERN.search(text):
        do_status(console, game)
        return

    if _AREA_PATTERN.search(text):
        do_area_info(console, game)
        return

    console.output_lines.append((
        "error",
        "Unknown command. Type 'help' for available commands."
    ))


# ------------------------------------------------------------------
# Command executors
# ------------------------------------------------------------------

def do_goto(console, target_name: str, game):
    """Find a settlement by name and set player target."""
    best = None
    best_score = 0
    target_lower = target_name.lower()
    for s in game.world.structures:
        name_lower = s.name.lower()
        if target_lower == name_lower:
            best = s
            break
        if target_lower in name_lower or name_lower in target_lower:
            score = len(target_lower) / max(1, len(name_lower))
            if score > best_score:
                best_score = score
                best = s

    if best:
        game.player.target_x = float(best.x)
        game.player.target_y = float(best.y)
        dist = game.player.dist_to_pos(best.x, best.y)
        console.output_lines.append((
            "success",
            f"Heading to {best.name} ({dist:.0f} tiles away)"
        ))
        game.notifications.add(
            f"Heading to {best.name}", 3.0, GREEN)
    else:
        console.output_lines.append((
            "error",
            f"Could not find '{target_name}'. Try a settlement name."
        ))


def do_attack(console, target_name: str, game):
    """Find and target nearest matching creature/NPC."""
    target_lower = target_name.lower()
    best = None
    best_dist = float("inf")

    for c in game.world_mgr.creatures:
        if not getattr(c, "alive", False):
            continue
        kind = getattr(c, "kind", "").lower().replace("_", " ")
        name = getattr(c, "name", "").lower()
        if target_lower in kind or target_lower in name:
            d = game.player.dist_to(c)
            if d < best_dist:
                best_dist = d
                best = c

    for npc in game.world_mgr.npcs:
        if not getattr(npc, "alive", False):
            continue
        name = getattr(npc, "name", "").lower()
        if target_lower in name:
            d = game.player.dist_to(npc)
            if d < best_dist:
                best_dist = d
                best = npc

    if best:
        msg = game.combat.set_player_target(best)
        kind = getattr(best, "name", getattr(best, "kind", "target"))
        console.output_lines.append((
            "success", f"Targeting {kind} ({best_dist:.0f} tiles away)"
        ))
        if msg:
            game.notifications.add(msg, 2.0, RED)
    else:
        console.output_lines.append((
            "error", f"No '{target_name}' found nearby."
        ))


def do_cast(console, spell_name: str, game):
    """Activate a spell by name."""
    from game.systems.combat import CombatSystem
    normalized = spell_name.strip().lower().replace(" ", "_")
    result = CombatSystem.player_cast_spell(
        game.player, normalized,
        game.world_mgr.creatures, game.world_mgr.npcs,
    )
    if result:
        color = "success" if "damage" in result.lower() else "info"
        if "cannot" in result.lower() or "unknown" in result.lower():
            color = "error"
        console.output_lines.append((color, result))
    else:
        console.output_lines.append(
            ("error", f"Could not cast '{spell_name}'."))


def do_trade(console, game):
    """Initiate trade with nearest NPC."""
    best = None
    best_dist = float("inf")
    for npc in game.world_mgr.npcs:
        if not getattr(npc, "alive", False):
            continue
        profession = getattr(npc, "profession", "").lower()
        if ("merchant" in profession or "trader" in profession
                or "shopkeeper" in profession):
            d = game.player.dist_to(npc)
            if d < best_dist:
                best_dist = d
                best = npc

    if best and best_dist < 8:
        console.output_lines.append((
            "success",
            f"Approach {best.name} (merchant) and press E to trade."
        ))
        game.notifications.add(
            f"Merchant nearby: {best.name}", 2.0, YELLOW)
    elif best:
        console.output_lines.append((
            "info",
            f"Nearest merchant: {best.name} ({best_dist:.0f} tiles away)"
        ))
    else:
        console.output_lines.append(
            ("error", "No merchants found nearby."))


def do_status(console, game):
    """Show player stats."""
    p = game.player
    lines = [
        f"HP: {int(p.hp)}/{p.max_hp}  Energy: {int(p.energy)}/{p.max_energy}",
        f"Level {p.level} {p.char_class} ({p.race})  Gold: {p.gold}",
        f"ATK: {p.attack_damage}  DEF: {p.defense}  AC: {p.armor_class}",
        f"XP: {p.xp}/{p.xp_to_next}  Kills: {p.kills}",
    ]
    for line in lines:
        console.output_lines.append(("info", line))


def do_area_info(console, game):
    """Describe the current area."""
    p = game.player
    px, py = int(p.x), int(p.y)
    tile = game.world.tiles[py][px] if (
        0 <= py < game.world.height and 0 <= px < game.world.width
    ) else 0

    tile_names = {
        0: "Grass", 1: "Forest", 2: "Water", 3: "Sand",
        4: "Desert", 5: "Mountain", 6: "Snow", 7: "Road",
    }
    terrain = tile_names.get(tile, f"Terrain({tile})")

    near = None
    for s in game.world.structures:
        dist = abs(s.x - px) + abs(s.y - py)
        if dist < s.radius + 10:
            near = s
            break

    if near:
        console.output_lines.append((
            "info",
            f"You are near {near.name} ({near.kind}) on {terrain}."
        ))
    else:
        console.output_lines.append((
            "info", f"You are in the wilderness. Terrain: {terrain}."
        ))

    creatures_nearby = sum(
        1 for c in game.world_mgr.creatures
        if getattr(c, "alive", False) and p.dist_to(c) < 15
    )
    npcs_nearby = sum(
        1 for n in game.world_mgr.npcs
        if getattr(n, "alive", False) and p.dist_to(n) < 15
    )
    if creatures_nearby or npcs_nearby:
        console.output_lines.append((
            "info",
            f"Nearby: {npcs_nearby} NPCs, {creatures_nearby} creatures"
        ))


def do_help(console):
    """Show available commands."""
    cmds = [
        "go to [place]  - travel to a settlement",
        "attack [target] - target nearest creature/NPC",
        "cast [spell]   - cast a spell",
        "trade           - find nearest merchant",
        "status          - show your stats",
        "where am i      - describe current area",
        "help            - show this help",
    ]
    for cmd in cmds:
        console.output_lines.append(("info", cmd))
