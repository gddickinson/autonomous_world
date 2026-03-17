"""Hot-Reload system for game modules.

Allows reloading Python modules at runtime without restarting the game.
Only modules in the SAFE_MODULES list can be reloaded to prevent crashes
from reloading core engine modules (renderer, main loop, etc.).
"""

import importlib
import time as _time


class HotReloader:
    """Hot-reload game modules without restarting."""

    # Modules that are safe to reload at runtime.
    # These are data/logic modules that don't hold critical engine state.
    SAFE_MODULES = [
        "game.settings",
        "game.data.ecology",
        "game.data.supply_chains",
        "game.data.pricing",
        "game.systems.npc_work",
        "game.systems.npc_lifecycle",
        "game.systems.schedules",
        "game.systems.commands",
        "game.world.specializations",
        "game.ai.prompts",
        "game.data.dnd",
        "game.systems.crafting",
        "game.systems.combat",
        "game.systems.body_damage",
        "game.systems.career",
        "game.systems.culture",
        "game.systems.ecology",
        "game.systems.demographics",
    ]

    def __init__(self):
        self.reload_count = 0
        self.last_reload = {}   # module_name -> timestamp
        self.errors = []        # recent errors

    def reload(self, module_name):
        """Reload a module. Returns (success, message)."""
        if module_name not in self.SAFE_MODULES:
            return False, f"Module '{module_name}' not in safe reload list. " \
                          f"Safe modules: {', '.join(self.SAFE_MODULES[:5])}..."

        try:
            mod = importlib.import_module(module_name)
            importlib.reload(mod)
            self.reload_count += 1
            self.last_reload[module_name] = _time.time()
            return True, f"Reloaded {module_name}"
        except Exception as e:
            msg = f"Failed to reload {module_name}: {type(e).__name__}: {e}"
            self.errors.append(msg)
            if len(self.errors) > 20:
                self.errors = self.errors[-20:]
            return False, msg

    def reload_all_safe(self):
        """Reload all safe modules. Returns list of (module_name, success, message)."""
        results = []
        for mod_name in self.SAFE_MODULES:
            ok, msg = self.reload(mod_name)
            results.append((mod_name, ok, msg))
        return results

    def reload_settings(self):
        """Convenience: reload just the settings module."""
        return self.reload("game.settings")

    def is_safe(self, module_name):
        """Check if a module is in the safe list."""
        return module_name in self.SAFE_MODULES

    def add_safe_module(self, module_name):
        """Add a module to the safe list (use with caution)."""
        if module_name not in self.SAFE_MODULES:
            self.SAFE_MODULES.append(module_name)

    @property
    def status_summary(self):
        """Return a status string."""
        return (f"Hot Reloader: {self.reload_count} reloads, "
                f"{len(self.SAFE_MODULES)} safe modules, "
                f"{len(self.errors)} errors")
