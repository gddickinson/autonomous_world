"""
God Console - command execution for Claude Assistant and direct god-mode input.

Parses and executes text commands that modify the game state:
spawning entities, teleporting, modifying NPCs, changing weather, etc.
"""

import random
from typing import Optional


class GodConsole:
    """Parses and executes god-mode commands against the game state."""

    def __init__(self, game):
        self.game = game

    def execute(self, command_text: str) -> str:
        """Execute a command string. Returns a result message."""
        parts = command_text.strip().split()
        if not parts:
            return "Empty command."

        cmd = parts[0].lower()
        args = parts[1:]

        dispatch = {
            "spawn": self._cmd_spawn,
            "spawn_npc": self._cmd_spawn_npc,
            "teleport": self._cmd_teleport,
            "tp": self._cmd_teleport,
            "set_time_speed": self._cmd_set_time_speed,
            "give_gold": self._cmd_give_gold,
            "paint_tile": self._cmd_paint_tile,
            "kill_entity": self._cmd_kill_entity,
            "kill": self._cmd_kill_entity,
            "heal_entity": self._cmd_heal_entity,
            "heal": self._cmd_heal_entity,
            "heal_player": self._cmd_heal_player,
            "modify_npc": self._cmd_modify_npc,
            "set_weather": self._cmd_set_weather,
            "list_npcs": self._cmd_list_npcs,
            "list_kingdoms": self._cmd_list_kingdoms,
            "list_settlements": self._cmd_list_settlements,
            "inspect_npc": self._cmd_inspect_npc,
            "inspect": self._cmd_inspect_npc,
            # Live editing commands
            "set_param": self._cmd_set_param,
            "reload_module": self._cmd_reload_module,
            "exec_python": self._cmd_exec_python,
            "modify_creature_stats": self._cmd_modify_creature_stats,
            "add_item_to_game": self._cmd_add_item,
        }

        handler = dispatch.get(cmd)
        if handler:
            try:
                return handler(args)
            except Exception as e:
                return f"Error executing '{cmd}': {e}"
        return f"Unknown command: {cmd}"

    # ------------------------------------------------------------------
    # Command implementations
    # ------------------------------------------------------------------

    def _cmd_spawn(self, args) -> str:
        """spawn <creature_type> <x> <y>"""
        if len(args) < 3:
            return "Usage: spawn <creature_type> <x> <y>"
        creature_type = args[0]
        try:
            x, y = float(args[1]), float(args[2])
        except ValueError:
            return "Invalid coordinates."

        from game.settings import CREATURE_TYPES
        if creature_type not in CREATURE_TYPES:
            return f"Unknown creature type: {creature_type}. Known: {', '.join(sorted(CREATURE_TYPES.keys())[:20])}"

        from game.core.creature import Creature
        creature = Creature(creature_type, x, y)
        self.game.world_mgr.creatures.append(creature)
        return f"Spawned {creature_type} at ({x:.0f}, {y:.0f})."

    def _cmd_spawn_npc(self, args) -> str:
        """spawn_npc <name> <class> <race> <x> <y>"""
        if len(args) < 5:
            return "Usage: spawn_npc <name> <class> <race> <x> <y>"
        name = args[0]
        char_class = args[1]
        race = args[2]
        try:
            x, y = float(args[3]), float(args[4])
        except ValueError:
            return "Invalid coordinates."

        from game.core.npc import NPC
        npc = NPC(name, x, y, profession=char_class)
        npc.char_class = char_class
        npc.race = race
        self.game.world_mgr.npcs.append(npc)
        return f"Spawned NPC {name} ({race} {char_class}) at ({x:.0f}, {y:.0f})."

    def _cmd_teleport(self, args) -> str:
        """teleport <x> <y>"""
        if len(args) < 2:
            return "Usage: teleport <x> <y>"
        try:
            x, y = float(args[0]), float(args[1])
        except ValueError:
            return "Invalid coordinates."

        self.game.player.x = x
        self.game.player.y = y
        return f"Teleported player to ({x:.0f}, {y:.0f})."

    def _cmd_set_time_speed(self, args) -> str:
        """set_time_speed <multiplier>"""
        if len(args) < 1:
            return "Usage: set_time_speed <multiplier>"
        try:
            speed = float(args[0])
        except ValueError:
            return "Invalid speed value."

        if hasattr(self.game.time_sys, 'speed'):
            self.game.time_sys.speed = speed
        elif hasattr(self.game.time_sys, 'time_scale'):
            self.game.time_sys.time_scale = speed
        return f"Time speed set to {speed}x."

    def _cmd_give_gold(self, args) -> str:
        """give_gold <amount>"""
        if len(args) < 1:
            return "Usage: give_gold <amount>"
        try:
            amount = int(args[0])
        except ValueError:
            return "Invalid amount."

        self.game.player.gold += amount
        return f"Gave player {amount} gold. Total: {self.game.player.gold}."

    def _cmd_paint_tile(self, args) -> str:
        """paint_tile <x> <y> <tile_type>"""
        if len(args) < 3:
            return "Usage: paint_tile <x> <y> <tile_type>"
        try:
            x, y = int(args[0]), int(args[1])
            tile_type = int(args[2])
        except ValueError:
            return "Invalid arguments (need integers)."

        try:
            self.game.world.set_tile(x, y, tile_type)
            return f"Painted tile at ({x}, {y}) to type {tile_type}."
        except Exception as e:
            return f"Failed to paint tile: {e}"

    def _cmd_kill_entity(self, args) -> str:
        """kill_entity <name>"""
        if len(args) < 1:
            return "Usage: kill_entity <name>"
        name = " ".join(args)

        # Search NPCs
        for npc in self.game.world_mgr.npcs:
            if getattr(npc, 'name', '').lower() == name.lower():
                npc.hp = 0
                npc.alive = False
                return f"Killed NPC: {npc.name}."

        # Search creatures
        for creature in self.game.world_mgr.creatures:
            kind = getattr(creature, 'kind', '')
            if kind.lower() == name.lower():
                creature.hp = 0
                creature.alive = False
                return f"Killed creature: {kind}."

        return f"Entity '{name}' not found."

    def _cmd_heal_entity(self, args) -> str:
        """heal_entity <name>"""
        if len(args) < 1:
            return "Usage: heal_entity <name>"
        name = " ".join(args)

        for npc in self.game.world_mgr.npcs:
            if getattr(npc, 'name', '').lower() == name.lower():
                npc.hp = getattr(npc, 'max_hp', 100)
                return f"Healed NPC: {npc.name} to {npc.hp} HP."

        return f"NPC '{name}' not found."

    def _cmd_heal_player(self, args) -> str:
        """heal_player"""
        self.game.player.hp = self.game.player.max_hp
        self.game.player.energy = getattr(self.game.player, 'max_energy', 100)
        return f"Player healed to {self.game.player.hp} HP."

    def _cmd_modify_npc(self, args) -> str:
        """modify_npc <name> <field> <value>"""
        if len(args) < 3:
            return "Usage: modify_npc <name> <field> <value>"

        # Find the NPC - name might have spaces, so try progressively
        name = args[0]
        field = args[1]
        value_str = " ".join(args[2:])
        target_npc = None

        for npc in self.game.world_mgr.npcs:
            if getattr(npc, 'name', '').lower() == name.lower():
                target_npc = npc
                break

        if not target_npc:
            return f"NPC '{name}' not found."

        # Determine value type
        try:
            value = int(value_str)
        except ValueError:
            try:
                value = float(value_str)
            except ValueError:
                value = value_str

        safe_fields = {
            "hp", "max_hp", "level", "gold", "npc_gold",
            "profession", "char_class", "race", "title",
            "state", "current_action", "consciousness",
            "strength", "dexterity", "constitution",
            "intelligence", "wisdom", "charisma",
        }

        if field not in safe_fields:
            return f"Cannot modify '{field}'. Safe fields: {', '.join(sorted(safe_fields))}"

        # Handle ability scores
        if field in ("strength", "dexterity", "constitution",
                     "intelligence", "wisdom", "charisma"):
            scores = getattr(target_npc, 'ability_scores', {})
            scores[field] = value
            target_npc.ability_scores = scores
            return f"Set {target_npc.name}.ability_scores[{field}] = {value}"

        setattr(target_npc, field, value)
        return f"Set {target_npc.name}.{field} = {value}"

    def _cmd_set_weather(self, args) -> str:
        """set_weather <type>"""
        if len(args) < 1:
            return "Usage: set_weather <type> (clear, rain, storm, snow, fog)"
        weather = args[0].lower()
        valid = ("clear", "rain", "storm", "snow", "fog")
        if weather not in valid:
            return f"Invalid weather. Choose from: {', '.join(valid)}"

        we = getattr(self.game.simulation, 'world_effects', None)
        if we and hasattr(we, 'weather'):
            we.weather = weather
            return f"Weather set to {weather}."
        elif hasattr(self.game, 'weather'):
            self.game.weather = weather
            return f"Weather set to {weather}."
        return "Weather system not found, but noted."

    def _cmd_list_npcs(self, args) -> str:
        """list_npcs"""
        npcs = self.game.world_mgr.npcs
        if not npcs:
            return "No live NPCs."
        lines = [f"Live NPCs ({len(npcs)}):"]
        for npc in npcs[:30]:
            name = getattr(npc, 'name', '?')
            race = getattr(npc, 'race', '?')
            cls = getattr(npc, 'char_class', getattr(npc, 'profession', '?'))
            hp = getattr(npc, 'hp', 0)
            lines.append(f"  {name} ({race} {cls}) HP:{int(hp)} at ({npc.x:.0f},{npc.y:.0f})")
        if len(npcs) > 30:
            lines.append(f"  ... and {len(npcs) - 30} more")
        return "\n".join(lines)

    def _cmd_list_kingdoms(self, args) -> str:
        """list_kingdoms"""
        kingdoms = getattr(self.game.world.plan, 'kingdoms', [])
        if not kingdoms:
            return "No kingdoms."
        lines = [f"Kingdoms ({len(kingdoms)}):"]
        for k in kingdoms:
            if isinstance(k, dict):
                name = k.get('name', '?')
                race = k.get('race', '?')
                gov = k.get('governance_style', '?')
                settlements = k.get('territory_settlements', [])
            else:
                name = getattr(k, 'name', '?')
                race = getattr(k, 'race', '?')
                gov = getattr(k, 'governance_style', '?')
                settlements = getattr(k, 'territory_settlements', [])
            lines.append(f"  {name} ({race}, {gov}): {len(settlements)} settlements")
        return "\n".join(lines)

    def _cmd_list_settlements(self, args) -> str:
        """list_settlements"""
        settlements = getattr(self.game.world.plan, 'settlements', [])
        if not settlements:
            return "No settlements."
        lines = [f"Settlements ({len(settlements)}):"]
        for sp in settlements[:40]:
            name = getattr(sp, 'name', '?')
            kind = getattr(sp, 'kind', '?')
            x = getattr(sp, 'x', 0)
            y = getattr(sp, 'y', 0)
            lines.append(f"  {name} ({kind}) at ({x}, {y})")
        if len(settlements) > 40:
            lines.append(f"  ... and {len(settlements) - 40} more")
        return "\n".join(lines)

    def _cmd_inspect_npc(self, args) -> str:
        """inspect_npc <name>"""
        if len(args) < 1:
            return "Usage: inspect_npc <name>"
        name = " ".join(args)

        for npc in self.game.world_mgr.npcs:
            if getattr(npc, 'name', '').lower() == name.lower():
                lines = [f"=== {npc.name} ==="]
                lines.append(f"Race: {getattr(npc, 'race', '?')}")
                lines.append(f"Class: {getattr(npc, 'char_class', '?')}")
                lines.append(f"Profession: {getattr(npc, 'profession', '?')}")
                lines.append(f"Title: {getattr(npc, 'title', 'commoner')}")
                lines.append(f"Level: {getattr(npc, 'level', 1)}")
                lines.append(f"HP: {int(getattr(npc, 'hp', 0))}/{getattr(npc, 'max_hp', 0)}")
                lines.append(f"Position: ({npc.x:.0f}, {npc.y:.0f})")
                lines.append(f"State: {getattr(npc, 'state', '?')}")
                lines.append(f"Action: {getattr(npc, 'current_action', 'none')}")
                lines.append(f"Settlement: {getattr(npc, 'home_settlement', '?')}")
                lines.append(f"Consciousness: {getattr(npc, 'consciousness', 0)}")
                scores = getattr(npc, 'ability_scores', {})
                if scores:
                    lines.append(f"Abilities: " + ", ".join(
                        f"{k[:3].upper()}:{v}" for k, v in scores.items()))
                gold = getattr(npc, 'npc_gold', getattr(npc, 'gold', 0))
                lines.append(f"Gold: {gold}")
                # Memories
                memories = getattr(npc, 'memories', [])
                if memories:
                    lines.append(f"Recent memories ({len(memories)}):")
                    for m in memories[-5:]:
                        if isinstance(m, dict):
                            lines.append(f"  - {m.get('text', str(m))}")
                        else:
                            lines.append(f"  - {m}")
                return "\n".join(lines)

        return f"NPC '{name}' not found."

    # ------------------------------------------------------------------
    # Live editing commands
    # ------------------------------------------------------------------

    def _cmd_set_param(self, args) -> str:
        """set_param <name> <value>"""
        if len(args) < 2:
            return "Usage: set_param <param_name> <value>"
        param_name = args[0]
        try:
            value = float(args[1])
        except ValueError:
            return f"Invalid value: {args[1]}"

        # Use the tweaker if available
        god_ui = getattr(self.game, 'god_ui', None)
        if god_ui and hasattr(god_ui, 'tweaker'):
            result = god_ui.tweaker.set_value(param_name, value)
            if result is not None:
                return f"Set {param_name} = {result}"

        return f"Unknown parameter: {param_name}"

    def _cmd_reload_module(self, args) -> str:
        """reload_module <module_name>"""
        if len(args) < 1:
            return "Usage: reload_module <module_name>"
        module_name = args[0]

        god_ui = getattr(self.game, 'god_ui', None)
        if god_ui and hasattr(god_ui, 'hot_reloader'):
            ok, msg = god_ui.hot_reloader.reload(module_name)
            return msg

        # Fallback
        import importlib
        try:
            mod = importlib.import_module(module_name)
            importlib.reload(mod)
            return f"Reloaded {module_name}"
        except Exception as e:
            return f"Failed to reload {module_name}: {e}"

    def _cmd_exec_python(self, args) -> str:
        """exec_python <code>"""
        if not args:
            return "Usage: exec_python <python_code>"
        code = " ".join(args)

        god_ui = getattr(self.game, 'god_ui', None)
        if god_ui and hasattr(god_ui, 'python_console'):
            god_ui.python_console.execute(code)
            # Return the last output line
            if god_ui.python_console.output_lines:
                kind, text = god_ui.python_console.output_lines[-1]
                return text
            return "Executed (no output)."

        # Fallback: direct exec
        import io, contextlib
        stdout = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout):
                try:
                    result = eval(code, {"game": self.game})
                    if result is not None:
                        print(repr(result))
                except SyntaxError:
                    exec(code, {"game": self.game})
            output = stdout.getvalue().strip()
            return output if output else "Executed (no output)."
        except Exception as e:
            return f"Error: {e}"

    def _cmd_modify_creature_stats(self, args) -> str:
        """modify_creature_stats <kind> <stat> <value>"""
        if len(args) < 3:
            return "Usage: modify_creature_stats <kind> <stat> <value>"
        kind = args[0].lower()
        stat = args[1].lower()
        try:
            value = float(args[2])
            if stat in ("hp", "xp", "damage"):
                value = int(value)
        except ValueError:
            return f"Invalid value: {args[2]}"

        from game.settings import CREATURE_TYPES
        if kind not in CREATURE_TYPES:
            return f"Unknown creature type: {kind}. Known: {', '.join(sorted(CREATURE_TYPES.keys())[:15])}..."

        valid_stats = ("hp", "damage", "speed", "xp")
        if stat not in valid_stats:
            return f"Invalid stat: {stat}. Valid: {', '.join(valid_stats)}"

        old_val = CREATURE_TYPES[kind].get(stat, 0)
        CREATURE_TYPES[kind][stat] = value
        return f"Set {kind}.{stat}: {old_val} -> {value}"

    def _cmd_add_item(self, args) -> str:
        """add_item_to_game <name> <type> <value>"""
        if len(args) < 3:
            return "Usage: add_item_to_game <name> <type> <value>"
        name = args[0]
        item_type = args[1]
        try:
            value = int(args[2])
        except ValueError:
            return f"Invalid value: {args[2]}"

        try:
            from game.core.items import make_item
            item = make_item(name, item_type, value=value)
            self.game.player.inventory.append(item)
            return f"Added {name} ({item_type}, value={value}) to player inventory."
        except Exception as e:
            return f"Failed to add item: {e}"
