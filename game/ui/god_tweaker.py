"""Parameter Tweaker panel for God Mode.

Provides real-time slider-based adjustment of game parameters
without requiring a restart or code reload.
"""

import pygame
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT


class ParameterTweaker:
    """Adjust game parameters live with sliders."""

    # Parameters that can be tweaked without code reload.
    # Each spec can contain:
    #   attr     - dot-separated attribute path on game object
    #   module   - game submodule name + var/dict/key
    #   config   - key in game.config
    #   custom   - name dispatched to _handle_custom
    #   class_attr - "ClassName.ATTR" on an imported class
    TWEAKABLE = {
        "Simulation": {
            "time_speed": {
                "min": 0.1, "max": 200, "step": 0.5,
                "attr": "time_sys.speed",
            },
            "npc_decision_interval": {
                "min": 1, "max": 30, "step": 1,
                "module": "settings", "var": "NPC_DECISION_INTERVAL",
            },
            "need_hunger_rate": {
                "min": 0.01, "max": 1.0, "step": 0.01,
                "module": "settings", "dict": "NEED_DECAY", "key": "hunger",
            },
            "need_thirst_rate": {
                "min": 0.01, "max": 1.0, "step": 0.01,
                "module": "settings", "dict": "NEED_DECAY", "key": "thirst",
            },
            "need_rest_rate": {
                "min": 0.01, "max": 1.0, "step": 0.01,
                "module": "settings", "dict": "NEED_DECAY", "key": "rest",
            },
        },
        "Combat": {
            "player_damage": {
                "min": 1, "max": 100, "step": 1,
                "attr": "player.attack_damage",
            },
            "player_speed": {
                "min": 1, "max": 20, "step": 0.5,
                "attr": "player.speed",
            },
            "creature_chase_range": {
                "min": 1, "max": 20, "step": 1,
                "module": "settings", "var": "CREATURE_CHASE_RANGE",
            },
        },
        "Economy": {
            "tax_rate": {
                "min": 0, "max": 0.5, "step": 0.01,
                "custom": "kingdoms_tax",
            },
            "trade_frequency": {
                "min": 1, "max": 30, "step": 1,
                "config": "trade_frequency",
            },
            "starting_gold": {
                "min": 0, "max": 1000, "step": 10,
                "config": "starting_gold",
            },
        },
        "World": {
            "view_radius_fov": {
                "min": 4, "max": 30, "step": 1,
                "attr": "fov_radius",
            },
            "max_creatures": {
                "min": 10, "max": 500, "step": 10,
                "attr": "world_mgr.max_creatures",
            },
            "dormancy_radius": {
                "min": 200, "max": 2000, "step": 100,
                "class_attr": "WorldManager.DORMANT_RADIUS",
            },
        },
    }

    def __init__(self, game):
        self.game = game
        self.visible = False
        self.current_tab = "Simulation"
        self.values = {}  # cached current values
        self.selected_param = None  # name of param being dragged
        self.dragging = False
        self._load_current_values()

    # ------------------------------------------------------------------
    # Value read/write
    # ------------------------------------------------------------------

    def _load_current_values(self):
        """Read current values from game objects."""
        for tab, params in self.TWEAKABLE.items():
            for name, spec in params.items():
                self.values[name] = self._read_value(spec)

    def _read_value(self, spec):
        """Read a value from the game using the spec."""
        if "attr" in spec:
            parts = spec["attr"].split(".")
            obj = self.game
            for p in parts:
                obj = getattr(obj, p, None)
                if obj is None:
                    return spec.get("min", 0)
            return obj
        elif "module" in spec:
            import importlib
            try:
                mod = importlib.import_module(f"game.{spec['module']}")
            except ImportError:
                return spec.get("min", 0)
            if "dict" in spec:
                d = getattr(mod, spec["dict"], {})
                return d.get(spec["key"], spec.get("min", 0))
            return getattr(mod, spec["var"], spec.get("min", 0))
        elif "config" in spec:
            return self.game.config.get(spec["config"], spec.get("min", 0))
        elif "class_attr" in spec:
            cls_name, attr_name = spec["class_attr"].split(".")
            try:
                from game.systems.world_manager import WorldManager
                classes = {"WorldManager": WorldManager}
                cls = classes.get(cls_name)
                if cls:
                    return getattr(cls, attr_name, spec.get("min", 0))
            except ImportError:
                pass
            return spec.get("min", 0)
        elif "custom" in spec:
            return self._read_custom(spec["custom"])
        return spec.get("min", 0)

    def _read_custom(self, name):
        """Read a custom parameter value."""
        if name == "kingdoms_tax":
            gov = getattr(getattr(self.game, 'simulation', None), 'governance', None)
            if gov and hasattr(gov, 'kingdoms'):
                for k_name, kingdom in gov.kingdoms.items():
                    return getattr(kingdom, 'tax_rate', 0.10)
            return 0.10
        return 0

    def _write_value(self, spec, value):
        """Write a value to the game."""
        if "attr" in spec:
            parts = spec["attr"].split(".")
            obj = self.game
            for p in parts[:-1]:
                obj = getattr(obj, p, None)
                if obj is None:
                    return
            setattr(obj, parts[-1], value)
        elif "module" in spec:
            import importlib
            try:
                mod = importlib.import_module(f"game.{spec['module']}")
            except ImportError:
                return
            if "dict" in spec:
                d = getattr(mod, spec["dict"], None)
                if d is not None:
                    d[spec["key"]] = value
            else:
                setattr(mod, spec["var"], value)
        elif "config" in spec:
            self.game.config[spec["config"]] = value
        elif "class_attr" in spec:
            cls_name, attr_name = spec["class_attr"].split(".")
            try:
                from game.systems.world_manager import WorldManager
                classes = {"WorldManager": WorldManager}
                cls = classes.get(cls_name)
                if cls:
                    setattr(cls, attr_name, value)
            except ImportError:
                pass
        elif "custom" in spec:
            self._handle_custom(spec["custom"], value)

    def _handle_custom(self, name, value):
        """Handle special parameter changes."""
        if name == "kingdoms_tax":
            gov = getattr(getattr(self.game, 'simulation', None), 'governance', None)
            if gov and hasattr(gov, 'kingdoms'):
                for k_name, kingdom in gov.kingdoms.items():
                    kingdom.tax_rate = value

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def adjust(self, param_name, delta):
        """Adjust a parameter by delta steps. Returns new value or None."""
        for tab, params in self.TWEAKABLE.items():
            if param_name in params:
                spec = params[param_name]
                current = self.values.get(param_name, spec["min"])
                new_val = max(spec["min"], min(spec["max"], current + delta * spec["step"]))
                # Round to avoid float drift
                if spec["step"] >= 1:
                    new_val = round(new_val, 1)
                else:
                    new_val = round(new_val, 4)
                self.values[param_name] = new_val
                self._write_value(spec, new_val)
                return new_val
        return None

    def set_value(self, param_name, value):
        """Set a parameter to an exact value. Returns clamped value or None."""
        for tab, params in self.TWEAKABLE.items():
            if param_name in params:
                spec = params[param_name]
                clamped = max(spec["min"], min(spec["max"], value))
                self.values[param_name] = clamped
                self._write_value(spec, clamped)
                return clamped
        return None

    def toggle(self):
        """Toggle visibility."""
        self.visible = not self.visible
        if self.visible:
            self._load_current_values()

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def handle_key(self, key):
        """Handle keyboard input when tweaker is visible. Returns True if consumed."""
        if not self.visible:
            return False

        tab_names = list(self.TWEAKABLE.keys())

        # Tab switching with Tab key
        if key == pygame.K_TAB:
            idx = tab_names.index(self.current_tab)
            self.current_tab = tab_names[(idx + 1) % len(tab_names)]
            self.selected_param = None
            return True

        params = self.TWEAKABLE.get(self.current_tab, {})
        param_names = list(params.keys())

        if not param_names:
            return False

        # Select parameter with up/down
        if key == pygame.K_UP:
            if self.selected_param is None:
                self.selected_param = param_names[0]
            else:
                idx = param_names.index(self.selected_param) if self.selected_param in param_names else 0
                self.selected_param = param_names[max(0, idx - 1)]
            return True
        if key == pygame.K_DOWN:
            if self.selected_param is None:
                self.selected_param = param_names[0]
            else:
                idx = param_names.index(self.selected_param) if self.selected_param in param_names else 0
                self.selected_param = param_names[min(len(param_names) - 1, idx + 1)]
            return True

        # Adjust with left/right
        if key == pygame.K_LEFT and self.selected_param:
            self.adjust(self.selected_param, -1)
            return True
        if key == pygame.K_RIGHT and self.selected_param:
            self.adjust(self.selected_param, 1)
            return True

        return False

    def handle_click(self, mx, my):
        """Handle mouse click on the tweaker panel. Returns True if consumed."""
        if not self.visible:
            return False

        panel_w = 350
        panel_x = 5

        # Check if click is within panel bounds
        if mx < panel_x or mx > panel_x + panel_w:
            return False
        if my < 50 or my > SCREEN_HEIGHT - 10:
            return False

        # Tab buttons
        tab_names = list(self.TWEAKABLE.keys())
        tx = 10
        if 55 <= my <= 73:
            for tab in tab_names:
                if tx <= mx <= tx + 70:
                    self.current_tab = tab
                    self.selected_param = None
                    return True
                tx += 75
            return True

        # Parameter sliders
        y = 80
        params = self.TWEAKABLE.get(self.current_tab, {})
        for name, spec in params.items():
            slider_y = y + 14
            if slider_y - 4 <= my <= slider_y + 12:
                # Calculate value from click position
                bar_x = 10
                bar_w = panel_w - 80
                frac = max(0, min(1, (mx - bar_x) / bar_w))
                value = spec["min"] + frac * (spec["max"] - spec["min"])
                # Snap to step
                steps = round((value - spec["min"]) / spec["step"])
                value = spec["min"] + steps * spec["step"]
                value = max(spec["min"], min(spec["max"], value))
                if spec["step"] >= 1:
                    value = round(value, 1)
                else:
                    value = round(value, 4)
                self.values[name] = value
                self._write_value(spec, value)
                self.selected_param = name
                self.dragging = True
                return True
            y += 32

        return True  # click was in panel area

    def handle_drag(self, mx, my):
        """Handle mouse drag on a slider."""
        if not self.visible or not self.dragging or not self.selected_param:
            return False

        panel_w = 350
        bar_x = 10
        bar_w = panel_w - 80

        for tab, params in self.TWEAKABLE.items():
            if self.selected_param in params:
                spec = params[self.selected_param]
                frac = max(0, min(1, (mx - bar_x) / bar_w))
                value = spec["min"] + frac * (spec["max"] - spec["min"])
                steps = round((value - spec["min"]) / spec["step"])
                value = spec["min"] + steps * spec["step"]
                value = max(spec["min"], min(spec["max"], value))
                if spec["step"] >= 1:
                    value = round(value, 1)
                else:
                    value = round(value, 4)
                self.values[self.selected_param] = value
                self._write_value(spec, value)
                return True
        return False

    def handle_mouse_up(self):
        """Stop dragging."""
        self.dragging = False

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, screen):
        """Draw the parameter tweaker panel."""
        if not self.visible:
            return

        panel_w = 350
        panel_h = SCREEN_HEIGHT - 60
        panel_x = 5
        panel_y = 50

        # Background
        surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        surf.fill((15, 15, 30, 230))
        screen.blit(surf, (panel_x, panel_y))
        pygame.draw.rect(screen, (60, 80, 120), (panel_x, panel_y, panel_w, panel_h), 1)

        font = pygame.font.SysFont("monospace", 13)
        font_sm = pygame.font.SysFont("monospace", 11)

        # Title
        title = font.render("PARAMETER TWEAKER [F6]", True, (220, 200, 80))
        screen.blit(title, (panel_x + 8, panel_y + 5))

        # Tab buttons
        x = panel_x + 5
        y = panel_y + 25
        for tab in self.TWEAKABLE:
            active = tab == self.current_tab
            color = (100, 150, 200) if active else (60, 60, 80)
            pygame.draw.rect(screen, color, (x, y, 70, 18), border_radius=3)
            label = font_sm.render(tab[:8], True, (220, 220, 240))
            screen.blit(label, (x + 3, y + 2))
            x += 75

        # Parameters for current tab
        y = panel_y + 50
        params = self.TWEAKABLE.get(self.current_tab, {})
        for name, spec in params.items():
            value = self.values.get(name, 0)
            is_selected = name == self.selected_param

            # Highlight selected
            if is_selected:
                hl = pygame.Surface((panel_w - 4, 30), pygame.SRCALPHA)
                hl.fill((40, 60, 100, 80))
                screen.blit(hl, (panel_x + 2, y - 2))

            # Label
            label_color = (240, 240, 255) if is_selected else (200, 200, 220)
            screen.blit(font_sm.render(name, True, label_color), (panel_x + 8, y))

            # Slider bar
            bar_x = panel_x + 8
            bar_y = y + 14
            bar_w = panel_w - 80
            bar_h = 8
            pygame.draw.rect(screen, (40, 40, 60), (bar_x, bar_y, bar_w, bar_h))

            # Fill based on value
            range_val = spec["max"] - spec["min"]
            frac = (value - spec["min"]) / max(0.001, range_val)
            fill_w = int(bar_w * frac)
            bar_color = (80, 180, 100) if is_selected else (80, 140, 200)
            pygame.draw.rect(screen, bar_color, (bar_x, bar_y, fill_w, bar_h))

            # Slider handle
            handle_x = bar_x + fill_w - 2
            pygame.draw.rect(screen, (220, 220, 240), (handle_x, bar_y - 2, 4, bar_h + 4))

            # Value label
            if isinstance(value, float) and spec["step"] < 1:
                val_str = f"{value:.3f}"
            elif isinstance(value, float):
                val_str = f"{value:.1f}"
            else:
                val_str = str(value)
            screen.blit(font_sm.render(val_str, True, (180, 220, 180)),
                        (bar_x + bar_w + 5, bar_y - 2))

            y += 32

        # Instructions
        instr_y = panel_y + panel_h - 40
        screen.blit(font_sm.render("Tab=switch  Up/Down=select  L/R=adjust",
                                   True, (120, 120, 150)),
                    (panel_x + 8, instr_y))
        screen.blit(font_sm.render("Click sliders to set directly",
                                   True, (120, 120, 150)),
                    (panel_x + 8, instr_y + 14))
