#!/usr/bin/env python3
"""Launch Autonomous World game.

Usage:
    python play.py                # normal game with character creation
    python play.py --dev          # dev/cheat character creation screen
    python play.py --cheat        # alias for --dev
    python play.py --skip-chargen # skip character creation (defaults)
    python play.py --wizard       # high-level wizard with all spells (cheat)
    python play.py --multiplayer  # host a multiplayer game
    python play.py --ai-companion warrior  # host + spawn AI co-player
    python play.py --join HOST:PORT        # join an existing game
"""
import argparse
from game.main import Game, main
from game.config import GameConfig


def _parse_args():
    parser = argparse.ArgumentParser(description="Autonomous World")
    parser.add_argument("--dev", "--cheat", action="store_true",
                        help="Use developer character creation screen")
    parser.add_argument("--skip-chargen", action="store_true",
                        help="Skip character creation (use defaults)")
    parser.add_argument("--wizard", action="store_true",
                        help="Start as level 20 Wizard with all spells (cheat)")
    # Multiplayer flags
    parser.add_argument("--multiplayer", action="store_true",
                        help="Enable multiplayer (host server)")
    parser.add_argument("--ai-companion", metavar="TYPE",
                        choices=["explorer", "warrior", "trader", "socialite"],
                        help="Spawn AI co-player with personality "
                             "(explorer/warrior/trader/socialite)")
    parser.add_argument("--join", metavar="HOST:PORT",
                        help="Join an existing multiplayer game (e.g. 192.168.1.5:7777)")
    return parser.parse_args()


def _setup_wizard_preset():
    """Configure a high-level wizard with every spell in the game."""
    Game._skip_chargen = True
    Game._char_preset = {
        "race": "Elf",
        "char_class": "Wizard",
        "ability_scores": {
            "strength": 8,
            "dexterity": 14,
            "constitution": 16,
            "intelligence": 20,
            "wisdom": 14,
            "charisma": 10,
        },
        "level": 20,
        "gold": 5000,
        "god_mode": True,
        "extra_items": [
            "Staff of Power", "Greater Health Potion", "Greater Health Potion",
            "Scroll of Fireball", "Wand of Magic Missile",
        ],
        "all_spells": True,  # special flag: learn every spell in the game
    }


def _apply_multiplayer_flags(args, config: GameConfig):
    """Apply multiplayer CLI flags to the game config."""
    if args.ai_companion:
        # --ai-companion implies --multiplayer
        config.set("multiplayer_enabled", True)
        config.set("host_server", True)
        config.set("ai_player_enabled", True)
        config.set("ai_player_personality", args.ai_companion)
        return

    if args.join:
        # --join HOST:PORT — connect to a remote server
        host_port = args.join
        if ":" in host_port:
            host, port_str = host_port.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                port = 7777
        else:
            host = host_port
            port = 7777
        config.set("multiplayer_enabled", True)
        config.set("host_server", False)
        config.set("server_host", host)
        config.set("server_port", port)
        return

    if args.multiplayer:
        # --multiplayer — host a server
        config.set("multiplayer_enabled", True)
        config.set("host_server", True)


if __name__ == "__main__":
    args = _parse_args()
    Game._skip_chargen = args.skip_chargen
    Game._dev_chargen = args.dev

    if args.wizard:
        _setup_wizard_preset()

    # Apply multiplayer flags before Game.__init__ reads the config
    if args.multiplayer or args.ai_companion or args.join:
        config = GameConfig()
        _apply_multiplayer_flags(args, config)
        config.save()

    main()
