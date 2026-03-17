"""Save / load player state to a JSON file.

Chunk tile data is persisted separately by ChunkGrid (as .npy files).
This module handles the lightweight player-specific data: position,
stats, inventory, and current floor.
"""

import json
import os
from typing import Any, Dict, Optional


def save_game(world, player, path: str = "data/savegame.json"):
    """Serialize player + minimal world state to *path* as JSON.

    Args:
        world: the ChunkedWorld (we read seed and spawn_point from it).
        player: the Player instance.
        path: destination file path (relative or absolute).
    """
    # Inventory — store item names (items are recreated via make_item)
    inventory_names = []
    for item in player.inventory:
        inventory_names.append(item.name if item else None)

    equipped_weapon_name = player.equipped_weapon.name if player.equipped_weapon else None
    equipped_armor_name = player.equipped_armor.name if player.equipped_armor else None

    data: Dict[str, Any] = {
        "version": 1,
        # World identity — so we can detect mismatched saves
        "world_seed": getattr(world, "seed", 0),
        "world_width": world.width,
        "world_height": world.height,
        # Player position
        "player_x": float(player.x),
        "player_y": float(player.y),
        "current_floor": getattr(player, "current_floor", 0),
        # Core stats
        "hp": player.hp,
        "max_hp": player.max_hp,
        "energy": getattr(player, "energy", 100),
        "max_energy": getattr(player, "max_energy", 100),
        "xp": player.xp,
        "level": player.level,
        "xp_to_next": player.xp_to_next,
        "gold": player.gold,
        "attack_damage": player.attack_damage,
        "defense": player.defense,
        # Counters
        "kills": player.kills,
        "quests_completed": player.quests_completed,
        "steps": player.steps,
        # Character identity
        "name": player.name,
        "char_class": getattr(player, "char_class", "Fighter"),
        "race": getattr(player, "race", "Human"),
        # Inventory (item names only — regenerated via make_item on load)
        "inventory": inventory_names,
        "equipped_weapon": equipped_weapon_name,
        "equipped_armor": equipped_armor_name,
        # Player mode
        "mode": getattr(player, "mode", "mortal"),
    }

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    # Atomic rename so a crash mid-write doesn't corrupt the save
    os.replace(tmp_path, path)


def load_game(path: str = "data/savegame.json") -> Optional[Dict[str, Any]]:
    """Load previously saved player state.

    Returns:
        A dict with all saved fields, or ``None`` if the file does not
        exist or is unreadable.
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, OSError):
        return None


def apply_save_to_player(player, data: Dict[str, Any]):
    """Apply loaded save data onto an existing Player instance.

    The player should already be constructed (so D&D stats, skills, etc.
    are initialized). This overwrites position, HP, inventory, etc.

    Args:
        player: a Player instance.
        data: the dict returned by ``load_game()``.
    """
    from game.core.items import make_item

    player.x = data.get("player_x", player.x)
    player.y = data.get("player_y", player.y)
    player.current_floor = data.get("current_floor", 0)

    player.hp = data.get("hp", player.hp)
    player.max_hp = data.get("max_hp", player.max_hp)
    player.energy = data.get("energy", player.energy)
    player.max_energy = data.get("max_energy", player.max_energy)
    player.xp = data.get("xp", player.xp)
    player.level = data.get("level", player.level)
    player.xp_to_next = data.get("xp_to_next", player.xp_to_next)
    player.gold = data.get("gold", player.gold)
    player.attack_damage = data.get("attack_damage", player.attack_damage)
    player.defense = data.get("defense", player.defense)

    player.kills = data.get("kills", player.kills)
    player.quests_completed = data.get("quests_completed", player.quests_completed)
    player.steps = data.get("steps", player.steps)

    player.name = data.get("name", player.name)
    player.char_class = data.get("char_class", player.char_class)
    player.race = data.get("race", player.race)

    # Rebuild inventory from item names
    inv_names = data.get("inventory", [])
    player.inventory = []
    for name in inv_names:
        if name:
            try:
                player.inventory.append(make_item(name))
            except Exception:
                pass  # skip unknown items

    # Re-equip weapon / armor by name
    eq_weapon = data.get("equipped_weapon")
    eq_armor = data.get("equipped_armor")
    player.equipped_weapon = None
    player.equipped_armor = None
    for item in player.inventory:
        if eq_weapon and item.name == eq_weapon and player.equipped_weapon is None:
            player.equipped_weapon = item
        if eq_armor and item.name == eq_armor and player.equipped_armor is None:
            player.equipped_armor = item

    # Hotbar — slot 0 gets weapon if equipped
    player.hotbar = [None] * 5
    if player.equipped_weapon:
        player.hotbar[0] = player.equipped_weapon
