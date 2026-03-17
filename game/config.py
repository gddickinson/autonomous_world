"""
Persistent game configuration system.
Loads/saves from data/config.json. Missing keys get default values.
"""

import json
import os

DEFAULT_CONFIG = {
    # World Generation
    "world_width": 10000,
    "world_height": 10000,
    "world_seed": None,         # None = random
    "world_gen_mode": "simulated", # "simulated" (history sim, default) or "planned" (fast)
    "history_years": 500,       # years of history to simulate (if simulated mode)

    # Gameplay
    "player_mode": "mortal",    # mortal, ghost, god
    "spawn_location": "mainland",  # mainland, test_island
    "difficulty": "normal",     # easy, normal, hard, brutal
    "auto_save": True,
    "auto_save_interval": 5,    # minutes

    # Graphics
    "screen_width": 1280,
    "screen_height": 800,
    "default_view": "strategy", # strategy, adventure, 3d
    "show_fps": False,
    "tile_size": 16,

    # Audio
    "music_volume": 0.5,
    "sfx_volume": 0.7,
    "music_enabled": True,

    # Simulation
    "time_speed": 1.0,          # game time multiplier
    "max_npcs_active": 200,
    "view_radius_3d": 20,
    "npc_decision_interval": 8.0,
    "llm_enabled": True,
    "llm_provider": "ollama",

    # Economy
    "starting_gold": 20,
    "tax_rate_default": 0.10,
    "trade_frequency": 10,      # days between foreign caravans

    # Combat
    "friendly_fire": False,
    "permadeath": True,
    "combat_difficulty": 1.0,   # multiplier on creature damage

    # Gods / Pantheon
    "gods_enabled": True,
    "gods_llm_enhanced": False,

    # Debug
    "show_debug_info": False,
    "show_npc_actions": True,
    "show_settlement_stores": False,

    # Multiplayer
    "multiplayer_enabled": False,
    "host_server": True,          # True = this instance hosts, False = connect to remote
    "server_host": "localhost",   # address to connect to (when not hosting)
    "server_port": 7777,
    "max_players": 2,
    "player_name": "Player",
    "ai_player_enabled": False,   # spawn an AI companion automatically
    "ai_player_personality": "explorer",  # explorer, warrior, trader, socialite
}

# Metadata for the options menus: describes valid choices for each key.
# Format: key -> (display_name, list_of_(label, value) pairs)
# Keys not listed here are not shown in menus (internal only).
CONFIG_OPTIONS = {
    # -- New Game settings --
    "world_width": ("World Size", [
        ("Small (2000)", 2000),
        ("Medium (5000)", 5000),
        ("Large (10000)", 10000),
        ("Huge (20000)", 20000),
    ]),
    "world_gen_mode": ("World Gen", [
        ("Planned (fast)", "planned"),
        ("Simulated History (slow)", "simulated"),
    ]),
    "history_years": ("History Length", [
        ("100 years", 100),
        ("300 years", 300),
        ("500 years", 500),
        ("1000 years", 1000),
    ]),
    "player_mode": ("Player Mode", [
        ("Mortal", "mortal"),
        ("Ghost", "ghost"),
        ("God", "god"),
    ]),
    "spawn_location": ("Spawn", [
        ("Mainland", "mainland"),
        ("Test Island", "test_island"),
    ]),
    "difficulty": ("Difficulty", [
        ("Easy", "easy"),
        ("Normal", "normal"),
        ("Hard", "hard"),
        ("Brutal", "brutal"),
    ]),

    # -- Graphics --
    "screen_width": ("Resolution", [
        ("1024x768", 1024),
        ("1280x800", 1280),
        ("1440x900", 1440),
        ("1920x1080", 1920),
    ]),
    "default_view": ("Default View", [
        ("Strategy (16px)", "strategy"),
        ("Adventure (32px)", "adventure"),
        ("3D", "3d"),
    ]),
    "show_fps": ("Show FPS", [
        ("Off", False),
        ("On", True),
    ]),
    "tile_size": ("Tile Size", [
        ("12px", 12),
        ("16px", 16),
        ("20px", 20),
        ("24px", 24),
    ]),

    # -- Gameplay --
    "time_speed": ("Time Speed", [
        ("0.5x (slow)", 0.5),
        ("1x (normal)", 1.0),
        ("2x (fast)", 2.0),
        ("4x (very fast)", 4.0),
    ]),
    "permadeath": ("Permadeath", [
        ("Off", False),
        ("On", True),
    ]),
    "combat_difficulty": ("Combat Difficulty", [
        ("0.5x (easy)", 0.5),
        ("1.0x (normal)", 1.0),
        ("1.5x (hard)", 1.5),
        ("2.0x (brutal)", 2.0),
    ]),
    "auto_save": ("Auto-Save", [
        ("Off", False),
        ("On", True),
    ]),
    "auto_save_interval": ("Auto-Save Interval", [
        ("1 min", 1),
        ("3 min", 3),
        ("5 min", 5),
        ("10 min", 10),
    ]),
    "friendly_fire": ("Friendly Fire", [
        ("Off", False),
        ("On", True),
    ]),

    # -- Simulation --
    "max_npcs_active": ("Max Active NPCs", [
        ("50", 50),
        ("100", 100),
        ("200", 200),
        ("400", 400),
    ]),
    "npc_decision_interval": ("NPC Decision Rate", [
        ("4s (fast)", 4.0),
        ("8s (normal)", 8.0),
        ("12s (slow)", 12.0),
        ("20s (minimal)", 20.0),
    ]),
    "llm_enabled": ("LLM Enabled", [
        ("Off", False),
        ("On", True),
    ]),
    "llm_provider": ("LLM Provider", [
        ("Ollama (local)", "ollama"),
        ("OpenAI", "openai"),
        ("Anthropic", "anthropic"),
    ]),
    "view_radius_3d": ("3D View Radius", [
        ("12 tiles", 12),
        ("16 tiles", 16),
        ("20 tiles", 20),
        ("28 tiles", 28),
    ]),

    # -- Economy --
    "starting_gold": ("Starting Gold", [
        ("0", 0),
        ("10", 10),
        ("20", 20),
        ("50", 50),
        ("100", 100),
    ]),
    "tax_rate_default": ("Tax Rate", [
        ("5%", 0.05),
        ("10%", 0.10),
        ("15%", 0.15),
        ("20%", 0.20),
    ]),
    "trade_frequency": ("Trade Frequency", [
        ("5 days", 5),
        ("10 days", 10),
        ("20 days", 20),
        ("30 days", 30),
    ]),

    # -- Audio --
    "music_volume": ("Music Volume", [
        ("Off", 0.0),
        ("25%", 0.25),
        ("50%", 0.5),
        ("75%", 0.75),
        ("100%", 1.0),
    ]),
    "sfx_volume": ("SFX Volume", [
        ("Off", 0.0),
        ("25%", 0.25),
        ("50%", 0.5),
        ("75%", 0.75),
        ("100%", 1.0),
    ]),
    "music_enabled": ("Music Enabled", [
        ("Off", False),
        ("On", True),
    ]),

    # -- Gods --
    "gods_enabled": ("Gods Enabled", [
        ("Off", False),
        ("On", True),
    ]),
    "gods_llm_enhanced": ("Gods LLM Enhanced", [
        ("Off", False),
        ("On", True),
    ]),

    # -- Debug --
    "show_debug_info": ("Debug Info", [
        ("Off", False),
        ("On", True),
    ]),
    "show_npc_actions": ("NPC Action Labels", [
        ("Off", False),
        ("On", True),
    ]),
    "show_settlement_stores": ("Settlement Stores", [
        ("Off", False),
        ("On", True),
    ]),

    # -- Multiplayer --
    "multiplayer_enabled": ("Multiplayer", [
        ("Off", False),
        ("On", True),
    ]),
    "host_server": ("Host/Join", [
        ("Host Game", True),
        ("Join Game", False),
    ]),
    "server_port": ("Port", [
        ("7777", 7777),
        ("7778", 7778),
        ("8888", 8888),
        ("9999", 9999),
    ]),
    "max_players": ("Max Players", [
        ("2", 2),
        ("3", 3),
        ("4", 4),
    ]),
    "ai_player_enabled": ("AI Companion", [
        ("Off", False),
        ("On", True),
    ]),
    "ai_player_personality": ("AI Personality", [
        ("Explorer", "explorer"),
        ("Warrior", "warrior"),
        ("Trader", "trader"),
        ("Socialite", "socialite"),
    ]),
}

# Resolution pairs: screen_width -> screen_height
RESOLUTION_MAP = {
    1024: 768,
    1280: 800,
    1440: 900,
    1920: 1080,
}

# Which config keys belong to which options tab
OPTIONS_TABS = {
    "Graphics": ["screen_width", "default_view", "show_fps", "tile_size"],
    "Gameplay": ["difficulty", "time_speed", "permadeath", "combat_difficulty",
                 "friendly_fire", "auto_save", "auto_save_interval"],
    "Simulation": ["max_npcs_active", "npc_decision_interval", "llm_enabled",
                   "llm_provider", "view_radius_3d",
                   "gods_enabled", "gods_llm_enhanced"],
    "Economy": ["starting_gold", "tax_rate_default", "trade_frequency"],
    "Audio": ["music_volume", "sfx_volume", "music_enabled"],
    "Debug": ["show_debug_info", "show_npc_actions", "show_settlement_stores"],
    "Multiplayer": ["multiplayer_enabled", "host_server", "server_port",
                    "max_players", "ai_player_enabled", "ai_player_personality"],
}

# Which config keys appear in the New Game setup screen
NEW_GAME_KEYS = [
    "world_width", "world_gen_mode", "history_years",
    "player_mode", "spawn_location", "difficulty",
]


class GameConfig:
    """Persistent game configuration with JSON file backing."""

    def __init__(self, path="data/config.json"):
        self.path = path
        self.values = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        """Load config from file, keeping defaults for missing keys."""
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r") as f:
                stored = json.load(f)
            for k, v in stored.items():
                if k in self.values:
                    self.values[k] = v
        except (json.JSONDecodeError, IOError, OSError):
            pass

    def save(self):
        """Save current config to file."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        try:
            with open(self.path, "w") as f:
                json.dump(self.values, f, indent=2, default=str)
        except (IOError, OSError):
            pass

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value

    def __getitem__(self, key):
        return self.values[key]

    def __setitem__(self, key, value):
        self.values[key] = value

    def __contains__(self, key):
        return key in self.values

    def reset_to_defaults(self):
        """Reset all values to defaults."""
        self.values = dict(DEFAULT_CONFIG)

    def get_option_index(self, key):
        """Return the index of the current value within CONFIG_OPTIONS choices."""
        if key not in CONFIG_OPTIONS:
            return 0
        _, choices = CONFIG_OPTIONS[key]
        current = self.values.get(key)
        for i, (_, val) in enumerate(choices):
            if val == current:
                return i
        return 0

    def cycle_option(self, key, direction=1):
        """Cycle an option left (-1) or right (+1) through its choices."""
        if key not in CONFIG_OPTIONS:
            return
        _, choices = CONFIG_OPTIONS[key]
        idx = self.get_option_index(key)
        idx = (idx + direction) % len(choices)
        self.values[key] = choices[idx][1]
        # Sync screen_height when screen_width changes
        if key == "screen_width":
            self.values["screen_height"] = RESOLUTION_MAP.get(
                self.values["screen_width"], 800)

    def get_option_label(self, key):
        """Return the human-readable label for the current value."""
        if key not in CONFIG_OPTIONS:
            return str(self.values.get(key, "?"))
        _, choices = CONFIG_OPTIONS[key]
        idx = self.get_option_index(key)
        return choices[idx][0]
