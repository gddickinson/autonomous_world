"""Difficulty system: multipliers for enemy damage, HP, XP/gold rewards, loot.

Reads the ``difficulty`` key from GameConfig at startup and exposes
helper functions that other systems call to scale values.
"""

from typing import Dict

# ----------------------------------------------------------------
# Difficulty multiplier tables
# ----------------------------------------------------------------

DIFFICULTY: Dict[str, Dict[str, float]] = {
    "easy": {
        "enemy_damage": 0.5,
        "enemy_hp": 0.75,
        "xp_gain": 1.5,
        "gold_gain": 1.5,
        "loot_chance": 1.3,
    },
    "normal": {
        "enemy_damage": 1.0,
        "enemy_hp": 1.0,
        "xp_gain": 1.0,
        "gold_gain": 1.0,
        "loot_chance": 1.0,
    },
    "hard": {
        "enemy_damage": 1.5,
        "enemy_hp": 1.5,
        "xp_gain": 0.8,
        "gold_gain": 0.8,
        "loot_chance": 0.7,
    },
    "brutal": {
        "enemy_damage": 2.0,
        "enemy_hp": 2.0,
        "xp_gain": 0.5,
        "gold_gain": 0.5,
        "loot_chance": 0.5,
    },
}

# ----------------------------------------------------------------
# Active difficulty state (set once at startup, readable everywhere)
# ----------------------------------------------------------------

_current_difficulty: str = "normal"
_multipliers: Dict[str, float] = dict(DIFFICULTY["normal"])


def init_difficulty(config) -> None:
    """Read difficulty from a GameConfig and cache multipliers.

    Call this once during game initialisation (e.g. in ``Game.__init__``).
    """
    global _current_difficulty, _multipliers
    diff = "normal"
    if config is not None:
        diff = config.get("difficulty", "normal")
    if diff not in DIFFICULTY:
        diff = "normal"
    _current_difficulty = diff
    _multipliers = dict(DIFFICULTY[diff])


def get_difficulty() -> str:
    """Return the current difficulty name."""
    return _current_difficulty


def get_multiplier(key: str) -> float:
    """Return a specific multiplier for the current difficulty.

    Valid keys: enemy_damage, enemy_hp, xp_gain, gold_gain, loot_chance.
    Returns 1.0 for unknown keys.
    """
    return _multipliers.get(key, 1.0)


# ----------------------------------------------------------------
# Convenience helpers called by other systems
# ----------------------------------------------------------------

def scale_enemy_damage(base_damage: int) -> int:
    """Scale damage dealt by enemies/creatures to the player."""
    return max(1, int(base_damage * _multipliers["enemy_damage"]))


def scale_enemy_hp(base_hp: int) -> int:
    """Scale creature/enemy max HP on spawn."""
    return max(1, int(base_hp * _multipliers["enemy_hp"]))


def scale_xp(base_xp: int) -> int:
    """Scale XP reward."""
    return max(1, int(base_xp * _multipliers["xp_gain"]))


def scale_gold(base_gold: int) -> int:
    """Scale gold reward."""
    return max(1, int(base_gold * _multipliers["gold_gain"]))


def scale_loot_chance(base_chance: float) -> float:
    """Scale loot drop probability (clamped to 0-1)."""
    return min(1.0, base_chance * _multipliers["loot_chance"])
