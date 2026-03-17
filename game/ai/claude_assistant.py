"""
Claude AI Assistant for God Mode.

Allows the god-mode player to chat with Claude about the game state
and ask it to make changes via in-game commands.

Security: API key is never stored in the game directory.
Priority: env var > system keychain > ~/.autonomous_world_key
"""

import os
import json
import threading
from typing import Optional, Tuple, List, Dict, Any


# ================================================================
# API KEY MANAGEMENT
# ================================================================

def get_api_key() -> Optional[str]:
    """Get Anthropic API key from secure storage.

    Priority:
    1. Environment variable ANTHROPIC_API_KEY
    2. System keychain via keyring
    3. Local file ~/.autonomous_world_key (user home, NOT game folder)
    4. None (not configured)
    """
    # 1. Environment variable
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

    # 2. System keychain
    try:
        import keyring
        key = keyring.get_password("autonomous_world", "anthropic_api_key")
        if key:
            return key
    except Exception:
        pass

    # 3. Home directory file
    key_file = os.path.expanduser("~/.autonomous_world_key")
    if os.path.exists(key_file):
        try:
            with open(key_file) as f:
                data = json.load(f)
                return data.get("anthropic_api_key")
        except Exception:
            pass

    return None


def store_api_key(key: str) -> bool:
    """Store API key securely. Returns True on success."""
    # Try system keychain first
    try:
        import keyring
        keyring.set_password("autonomous_world", "anthropic_api_key", key)
        return True
    except Exception:
        pass

    # Fallback to home directory file with restricted permissions
    key_file = os.path.expanduser("~/.autonomous_world_key")
    try:
        with open(key_file, 'w') as f:
            json.dump({"anthropic_api_key": key}, f)
        os.chmod(key_file, 0o600)  # owner read/write only
        return True
    except Exception:
        return False


def delete_api_key() -> bool:
    """Remove stored API key."""
    removed = False
    try:
        import keyring
        keyring.delete_password("autonomous_world", "anthropic_api_key")
        removed = True
    except Exception:
        pass
    key_file = os.path.expanduser("~/.autonomous_world_key")
    if os.path.exists(key_file):
        try:
            os.remove(key_file)
            removed = True
        except Exception:
            pass
    return removed


# ================================================================
# CLAUDE ASSISTANT
# ================================================================

class ClaudeAssistant:
    """In-game Claude AI assistant for God Mode.

    Can inspect game state, answer questions about the world,
    and execute commands to modify the game.
    """

    def __init__(self, game):
        self.game = game
        self.api_key = get_api_key()
        self.available = self.api_key is not None
        self.conversation: List[Dict[str, str]] = []
        self.client = None
        self._sdk_missing = False

        if self.available:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                self._sdk_missing = True
                self.available = False

    def reconfigure(self, new_key: str) -> bool:
        """Set a new API key and reinitialize the client."""
        if not store_api_key(new_key):
            return False
        self.api_key = new_key
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
            self.available = True
            self._sdk_missing = False
            return True
        except ImportError:
            self._sdk_missing = True
            self.available = False
            return False

    @property
    def status_text(self) -> str:
        if self._sdk_missing:
            return "anthropic SDK not installed (pip install anthropic)"
        if not self.api_key:
            return "No API key configured"
        if not self.available:
            return "Not available"
        return "Ready"

    def clear_conversation(self):
        self.conversation.clear()

    # ------------------------------------------------------------------
    # Game context builder
    # ------------------------------------------------------------------

    def build_game_context(self) -> str:
        """Build a context string describing current game state."""
        game = self.game
        plan = game.world.plan
        sim = game.simulation

        context = (
            "You are an AI assistant embedded in a game called Autonomous World.\n"
            "You have full access to the game state and can help the god-mode player "
            "understand and modify the world.\n\n"
            "CURRENT GAME STATE:\n"
        )

        # Time
        context += f"- Day: {game.time_sys.day}, {game.time_sys.time_string}\n"

        # World dimensions
        context += f"- World: {game.world.width}x{game.world.height} tiles\n"

        # Player
        context += f"- Player position: ({game.player.x:.0f}, {game.player.y:.0f})\n"
        context += f"- Player HP: {int(game.player.hp)}/{game.player.max_hp}\n"
        context += f"- Player Gold: {game.player.gold}\n"
        context += f"- Player Level: {game.player.level}\n"

        # Kingdoms
        kingdoms = getattr(plan, 'kingdoms', [])
        context += f"- Kingdoms: {len(kingdoms)}\n"

        # Settlements
        settlements = getattr(plan, 'settlements', [])
        context += f"- Settlements: {len(settlements)}\n"

        # NPCs
        live_npcs = game.world_mgr.npcs
        dormant = getattr(game.world_mgr, 'dormant_npc_count', 0)
        context += f"- Live NPCs: {len(live_npcs)}\n"
        context += f"- Dormant NPCs: {dormant}\n"

        # Creatures
        creatures = game.world_mgr.creatures
        context += f"- Creatures: {len(creatures)}\n"

        # Kingdom details
        if kingdoms:
            context += "\nKINGDOMS:\n"
            for k in kingdoms:
                name = k.get('name', k) if isinstance(k, dict) else getattr(k, 'name', str(k))
                race = k.get('race', '?') if isinstance(k, dict) else getattr(k, 'race', '?')
                gov = k.get('governance_style', '?') if isinstance(k, dict) else getattr(k, 'governance_style', '?')
                t_set = k.get('territory_settlements', []) if isinstance(k, dict) else getattr(k, 'territory_settlements', [])
                context += f"- {name} ({race}, {gov}): {len(t_set)} settlements\n"

        # Settlement details (first 15)
        if settlements:
            context += "\nSETTLEMENTS:\n"
            for sp in settlements[:15]:
                name = getattr(sp, 'name', str(sp))
                kind = getattr(sp, 'kind', '?')
                sx = getattr(sp, 'x', 0)
                sy = getattr(sp, 'y', 0)
                context += f"- {name} ({kind}) at ({sx}, {sy})\n"
            if len(settlements) > 15:
                context += f"  ... and {len(settlements) - 15} more\n"

        # Nearby NPCs
        px, py = game.player.x, game.player.y
        nearby = sorted(
            live_npcs,
            key=lambda n: (n.x - px) ** 2 + (n.y - py) ** 2
        )[:10]
        if nearby:
            context += "\nNEARBY NPCs (closest 10):\n"
            for npc in nearby:
                dist = ((npc.x - px) ** 2 + (npc.y - py) ** 2) ** 0.5
                name = getattr(npc, 'name', '?')
                race = getattr(npc, 'race', '?')
                cls = getattr(npc, 'char_class', getattr(npc, 'profession', '?'))
                hp = getattr(npc, 'hp', 0)
                max_hp = getattr(npc, 'max_hp', 0)
                action = getattr(npc, 'current_action', None) or getattr(npc, 'state', '?')
                context += f"- {name} ({race} {cls}) HP:{int(hp)}/{max_hp} [{action}] dist:{dist:.0f}\n"

        # Nearby creatures
        nearby_creatures = sorted(
            creatures,
            key=lambda c: (c.x - px) ** 2 + (c.y - py) ** 2
        )[:5]
        if nearby_creatures:
            context += "\nNEARBY CREATURES (closest 5):\n"
            for c in nearby_creatures:
                dist = ((c.x - px) ** 2 + (c.y - py) ** 2) ** 0.5
                kind = getattr(c, 'kind', '?')
                hp = getattr(c, 'hp', 0)
                max_hp = getattr(c, 'max_hp', 0)
                context += f"- {kind} HP:{int(hp)}/{max_hp} dist:{dist:.0f}\n"

        # Available commands
        context += """
AVAILABLE COMMANDS (you can suggest these for the player to execute):
- spawn <creature_type> <x> <y> -- spawn a creature at position
- spawn_npc <name> <class> <race> <x> <y> -- spawn an NPC
- teleport <x> <y> -- move the player to position
- set_time_speed <multiplier> -- change simulation speed (1=normal, 5=fast)
- give_gold <amount> -- give the player gold
- paint_tile <x> <y> <tile_type> -- change a tile's terrain type
- kill_entity <name> -- kill an NPC or creature by name
- heal_entity <name> -- fully heal an NPC by name
- heal_player -- fully heal the player
- modify_npc <name> <field> <value> -- change an NPC's stat field
- set_weather <type> -- change weather (clear, rain, storm, snow, fog)
- list_npcs -- list all live NPCs
- list_kingdoms -- list all kingdoms with details
- list_settlements -- list all settlements
- inspect_npc <name> -- show detailed info about a specific NPC

LIVE EDITING COMMANDS (modify gameplay in real-time):
- set_param <name> <value> -- set a tweakable parameter (e.g. time_speed, player_damage, tax_rate, need_hunger_rate)
- reload_module <module_name> -- hot-reload a Python module (e.g. game.settings, game.systems.combat)
- exec_python <code> -- execute arbitrary Python against the live game state
- modify_creature_stats <kind> <stat> <value> -- change a creature type's base stats (hp, damage, speed, xp)
- add_item_to_game <name> <type> <value> -- add a new item type to the game

When suggesting commands, format them as:
```command
<command here>
```

You can suggest multiple commands. The player will see them as clickable buttons.

Be helpful, creative, and knowledgeable about the game's medieval fantasy setting.
Answer questions about the game world using the current state above.
Keep responses concise but informative.
"""
        return context

    # ------------------------------------------------------------------
    # Send message (synchronous, called from background thread)
    # ------------------------------------------------------------------

    def send_message(self, user_text: str) -> Tuple[str, List[str]]:
        """Send a message to Claude and get a response.

        Returns (reply_text, list_of_commands).
        """
        if not self.available or not self.client:
            if self._sdk_missing:
                return "Claude not available: pip install anthropic", []
            return "Claude not available: set API key with K.", []

        self.conversation.append({"role": "user", "content": user_text})

        try:
            context = self.build_game_context()

            # Build messages: system context + conversation history
            messages = [
                {"role": "user", "content": context},
                {"role": "assistant", "content":
                    "I understand the current game state. How can I help?"},
            ]
            messages.extend(self.conversation)

            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=messages,
            )

            reply = response.content[0].text
            self.conversation.append({"role": "assistant", "content": reply})

            # Keep conversation from growing unbounded
            if len(self.conversation) > 20:
                self.conversation = self.conversation[-16:]

            commands = self._extract_commands(reply)
            return reply, commands

        except Exception as e:
            error_msg = f"Error communicating with Claude: {e}"
            # Remove the user message we just added since it failed
            if self.conversation and self.conversation[-1]["role"] == "user":
                self.conversation.pop()
            return error_msg, []

    def send_message_async(self, user_text: str, callback):
        """Send message in background thread to avoid blocking the game loop.

        callback(reply_text, commands) is called on completion.
        """
        def _worker():
            reply, commands = self.send_message(user_text)
            callback(reply, commands)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    # ------------------------------------------------------------------
    # Command extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_commands(text: str) -> List[str]:
        """Extract ```command blocks from Claude's response."""
        commands = []
        in_block = False
        current = ""
        for line in text.split("\n"):
            stripped = line.strip()
            if stripped == "```command":
                in_block = True
                current = ""
            elif stripped == "```" and in_block:
                in_block = False
                if current.strip():
                    commands.append(current.strip())
            elif in_block:
                current += line + "\n"
        return commands
