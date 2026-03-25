"""Crafting UI -- recipe browser, ingredient check, progress bar, XP rewards.
Opened with U key. Recipes grouped by category."""

import time
import pygame
from typing import Dict, List, Tuple
from game.settings import *
from game.core.items import ITEMS


RECIPE_CATEGORIES = {
    "Weapons": ["Wooden Sword", "Iron Sword", "Steel Sword", "Hunting Bow", "Staff", "Arrows"],
    "Armor": ["Leather Armor", "Chain Mail", "Plate Armor", "Bronze Shield",
              "Wooden Shield", "Iron Shield", "Boots", "Cloak", "Robe", "Leather Gloves", "Belt"],
    "Tools": ["Pickaxe", "Axe", "Hammer", "Hoe", "Fishing Rod", "Torch", "Lantern", "Lockpick",
              "Snare Trap", "Net", "Cage", "Smith's Tools", "Herbalism Kit", "Jeweler's Tools",
              "Thieves' Tools", "Healer's Kit", "Climbing Kit"],
    "Consumables": ["Health Potion", "Greater Health Potion", "Antidote", "Healing Salve",
                    "Healing Tonic", "Bandage", "Smelling Salts", "Herbal Poultice",
                    "Strength Elixir", "Speed Elixir", "Poison Vial"],
    "Food": ["Bread", "Cooked Meat", "Vegetable Stew", "Berry Pie", "Mushroom Soup",
             "Meat Pie", "Honey Cake", "Salted Fish", "Trail Rations", "Omelette",
             "Sausage", "Smoked Fish"],
    "Drinks": ["Ale", "Mead", "Wine", "Dwarven Stout", "Elven Cordial", "Water Flask"],
    "Materials": ["Iron Ingot", "Steel Ingot", "Copper Ingot", "Bronze Ingot", "Gold Bar",
                  "Planks", "Nails", "Arrowheads", "Leather", "Linen", "Rope", "Flour",
                  "Glass Pane", "Bottle", "Tanned Hide", "Wool Cloth"],
    "Building": ["Barrel", "Crate", "Cart", "Bucket", "Tent", "Candle"],
    "Jewelry": ["Ruby", "Sapphire", "Emerald", "Diamond", "Gold Ring", "Ruby Ring",
                "Sapphire Amulet", "Emerald Pendant", "Diamond Crown", "Enchanted Ring"],
    "Enchanting": ["Scroll of Healing", "Scroll of Fire", "Scroll of Ward", "Wand of Sparks",
                   "Enchanted Sword", "Enchanted Staff", "Ward Stones", "Spellbook"],
}

CATEGORY_NAMES = list(RECIPE_CATEGORIES.keys())


RECIPE_SKILL_REQUIREMENTS: Dict[str, Tuple[str, int]] = {
    "Steel Sword":           ("smithing", 3),
    "Plate Armor":           ("smithing", 5),
    "Chain Mail":             ("smithing", 4),
    "Iron Shield":           ("smithing", 3),
    "Greater Health Potion": ("alchemy", 4),
    "Strength Elixir":       ("alchemy", 5),
    "Speed Elixir":          ("alchemy", 5),
    "Invisibility Oil":      ("alchemy", 7),
    "Poison Vial":           ("alchemy", 3),
    "Enchanted Sword":       ("enchanting", 6),
    "Enchanted Staff":       ("enchanting", 5),
    "Wand of Sparks":        ("enchanting", 4),
    "Scroll of Ward":        ("enchanting", 3),
    "Diamond Crown":         ("jewelcraft", 6),
    "Enchanted Ring":        ("jewelcraft", 5),
    "Ruby Ring":             ("jewelcraft", 3),
    "Sapphire Amulet":       ("jewelcraft", 4),
    "Emerald Pendant":       ("jewelcraft", 4),
    "Dwarven Stout":         ("brewing", 3),
    "Elven Cordial":         ("brewing", 4),
    "Feast Platter":         ("cooking", 4),
    "Cart":                  ("woodcraft", 4),
    "Boat Hull":             ("shipbuilding", 5),
    "Battering Ram":         ("siege_engineering", 4),
    "Stained Glass":         ("glassblowing", 3),
}

WORKSTATION_SKILL_MAP = {
    "forge":      "smithing",
    "kitchen":    "cooking",
    "brewery":    "brewing",
    "alchemy":    "alchemy",
    "workshop":   "woodcraft",
    "loom":       "weaving",
    "jeweler":    "jewelcraft",
    "enchanter":  "enchanting",
    "pottery":    "pottery",
    "glassworks": "glassblowing",
    "tannery":    "tanning",
    "dye_house":  "dyeing",
    "cartography":"cartography",
}


class CraftingUI:
    """Player-facing crafting panel. Manages recipe browsing, crafting
    progress, and result delivery."""

    def __init__(self):
        self.active = False
        self.category_idx = 0
        self.recipe_idx = 0
        self.scroll_offset = 0
        self.crafting = False
        self.craft_start = 0.0
        self.craft_duration = 0.0
        self.craft_recipe = ""
        self.craft_message = ""
        self.craft_msg_timer = 0.0

    def toggle(self):
        self.active = not self.active
        if self.active:
            self.recipe_idx = 0
            self.scroll_offset = 0
            self.craft_message = ""

    def close(self):
        self.active = False
        self.crafting = False

    def _current_recipes(self) -> List[str]:
        """Return recipe names for the current category."""
        from game.systems.crafting import RECIPES
        cat = CATEGORY_NAMES[self.category_idx]
        candidates = RECIPE_CATEGORIES.get(cat, [])
        return [r for r in candidates if r in RECIPES]

    def _has_ingredients(self, recipe_name: str, player) -> Dict[str, Tuple[int, int]]:
        """Return {ingredient_name: (have, need)} for a recipe."""
        from game.systems.crafting import RECIPES
        _, ingredients, _, _, _ = RECIPES[recipe_name]
        result = {}
        for ing_name, ing_count in ingredients:
            have = player.count_item(ing_name)
            result[ing_name] = (have, ing_count)
        return result

    def _can_craft(self, recipe_name: str, player, workstation: str = None) -> Tuple[bool, str]:
        """Check if the player can craft a recipe right now."""
        from game.systems.crafting import RECIPES
        if recipe_name not in RECIPES:
            return False, "Unknown recipe"

        count, ingredients, tool, station, craft_time = RECIPES[recipe_name]

        # Check workstation (relaxed: allow if player has the relevant tool)
        if station and station != workstation:
            # Allow if player has the station's primary tool
            tool_for_station = {
                "forge": "Smith's Tools", "alchemy": "Herbalism Kit",
                "kitchen": None, "brewery": None, "workshop": "Hammer",
                "loom": None, "jeweler": "Jeweler's Tools",
                "enchanter": "Enchanter's Focus", "pottery": None,
                "glassworks": "Glassblower's Tools", "tannery": None,
                "dye_house": "Dye Kit", "cartography": "Cartographer's Kit",
            }
            alt_tool = tool_for_station.get(station)
            if alt_tool and player.count_item(alt_tool) > 0:
                pass  # allowed via portable tool
            elif station in (None, "kitchen", "brewery", "loom",
                             "pottery", "tannery"):
                pass  # no tool needed
            else:
                return False, f"Need {station} workstation or {alt_tool}"

        # Check required tool
        if tool and player.count_item(tool) == 0:
            return False, f"Requires {tool}"

        # Check skill requirement
        skill_req = RECIPE_SKILL_REQUIREMENTS.get(recipe_name)
        if skill_req:
            sk_name, sk_level = skill_req
            player_level = player.skills.get(sk_name, 0)
            if player_level < sk_level:
                return False, f"Requires {sk_name} level {sk_level} (you have {player_level})"

        # Check ingredients
        for ing_name, ing_count in ingredients:
            if player.count_item(ing_name) < ing_count:
                return False, f"Missing {ing_name}"

        return True, "Ready to craft"

    def start_craft(self, recipe_name: str, player):
        """Begin crafting a recipe (starts the timer)."""
        from game.systems.crafting import RECIPES
        can, reason = self._can_craft(recipe_name, player)
        if not can:
            self.craft_message = reason
            self.craft_msg_timer = 2.0
            return

        _, _, _, _, craft_time = RECIPES[recipe_name]
        # Clamp craft time for UI friendliness: 1-3 seconds
        ui_time = max(1.0, min(3.0, craft_time * 0.4))
        self.crafting = True
        self.craft_start = time.time()
        self.craft_duration = ui_time
        self.craft_recipe = recipe_name

    def update(self, dt: float, player):
        """Update crafting progress."""
        if self.craft_msg_timer > 0:
            self.craft_msg_timer -= dt
            if self.craft_msg_timer <= 0:
                self.craft_message = ""

        if not self.crafting:
            return

        elapsed = time.time() - self.craft_start
        if elapsed >= self.craft_duration:
            self._finish_craft(player)

    def _finish_craft(self, player):
        """Complete crafting and deliver results."""
        from game.systems.crafting import RECIPES, CraftingSystem
        recipe = self.craft_recipe
        self.crafting = False
        self.craft_recipe = ""

        if recipe not in RECIPES:
            return

        # Use the existing craft system to consume ingredients and produce item
        success, msg = CraftingSystem.craft(recipe, player)
        self.craft_message = msg
        self.craft_msg_timer = 3.0

        if success:
            # Award crafting XP
            _, _, _, station, craft_time = RECIPES[recipe]
            skill = WORKSTATION_SKILL_MAP.get(station, "woodcraft")
            xp_amount = 1.0 + craft_time * 0.15
            player.gain_skill_xp(skill, xp_amount)
            # Also a small amount of general XP
            player.gain_xp(max(1, int(craft_time)))

    def handle_key(self, key: int, player) -> bool:
        """Handle keyboard input for the crafting panel. Returns True if consumed."""
        if not self.active:
            return False

        if key == pygame.K_ESCAPE:
            self.close()
            return True

        if self.crafting:
            return True  # block input during crafting

        # Category switching
        if key == pygame.K_LEFT:
            self.category_idx = (self.category_idx - 1) % len(CATEGORY_NAMES)
            self.recipe_idx = 0
            self.scroll_offset = 0
            return True
        if key == pygame.K_RIGHT:
            self.category_idx = (self.category_idx + 1) % len(CATEGORY_NAMES)
            self.recipe_idx = 0
            self.scroll_offset = 0
            return True

        recipes = self._current_recipes()
        if not recipes:
            return True

        # Recipe navigation
        if key in (pygame.K_UP, pygame.K_w):
            self.recipe_idx = max(0, self.recipe_idx - 1)
            return True
        if key in (pygame.K_DOWN, pygame.K_s):
            self.recipe_idx = min(len(recipes) - 1, self.recipe_idx + 1)
            return True

        # Craft selected recipe
        if key in (pygame.K_RETURN, pygame.K_e):
            if 0 <= self.recipe_idx < len(recipes):
                self.start_craft(recipes[self.recipe_idx], player)
            return True

        return True  # consume all keys when panel is open

    def draw(self, screen: pygame.Surface, player):
        """Draw the crafting UI panel."""
        if not self.active:
            return

        from game.systems.crafting import RECIPES

        font_sm = pygame.font.SysFont("monospace", 13)
        font_md = pygame.font.SysFont("monospace", 16)
        font_lg = pygame.font.SysFont("monospace", 22)

        pw, ph = 700, 500
        px = SCREEN_WIDTH // 2 - pw // 2
        py = SCREEN_HEIGHT // 2 - ph // 2

        # Background
        bg = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bg.fill((20, 20, 35, 230))
        screen.blit(bg, (px, py))
        pygame.draw.rect(screen, (80, 120, 180), (px, py, pw, ph), 2)

        # Title
        title = font_lg.render("Crafting  [U to close]", True, (200, 220, 255))
        screen.blit(title, (px + pw // 2 - title.get_width() // 2, py + 8))

        # Category tabs
        tab_y = py + 38
        tab_x = px + 10
        for i, cat_name in enumerate(CATEGORY_NAMES):
            color = (200, 220, 255) if i == self.category_idx else (120, 120, 140)
            label = font_sm.render(cat_name, True, color)
            screen.blit(label, (tab_x, tab_y))
            if i == self.category_idx:
                pygame.draw.line(screen, (200, 220, 255),
                                 (tab_x, tab_y + 15), (tab_x + label.get_width(), tab_y + 15))
            tab_x += label.get_width() + 12
        # Arrow hints
        screen.blit(font_sm.render("<- ->", True, (100, 100, 120)),
                     (px + pw - 55, tab_y))

        # Divider
        div_y = tab_y + 22
        pygame.draw.line(screen, (60, 60, 80), (px + 5, div_y), (px + pw - 5, div_y))

        # Split: left panel (recipe list) and right panel (details)
        left_w = 250
        list_x = px + 10
        list_y = div_y + 8
        detail_x = px + left_w + 20
        detail_y = div_y + 8

        recipes = self._current_recipes()
        max_visible = 18

        # Scroll
        if self.recipe_idx < self.scroll_offset:
            self.scroll_offset = self.recipe_idx
        if self.recipe_idx >= self.scroll_offset + max_visible:
            self.scroll_offset = self.recipe_idx - max_visible + 1

        # Recipe list
        for i in range(self.scroll_offset, min(len(recipes), self.scroll_offset + max_visible)):
            rname = recipes[i]
            can, _ = self._can_craft(rname, player)
            if i == self.recipe_idx:
                # Highlight bar
                bar = pygame.Surface((left_w - 4, 18), pygame.SRCALPHA)
                bar.fill((60, 80, 120, 150))
                screen.blit(bar, (list_x - 2, list_y - 1))
                color = (255, 255, 255)
            elif can:
                color = (140, 220, 140)
            else:
                color = (140, 140, 140)

            # Show count produced
            if rname in RECIPES:
                cnt = RECIPES[rname][0]
                prefix = f"{cnt}x " if cnt > 1 else ""
            else:
                prefix = ""
            label = font_sm.render(f"{prefix}{rname}", True, color)
            screen.blit(label, (list_x, list_y))
            list_y += 20

        if not recipes:
            screen.blit(font_sm.render("No recipes in this category", True, (100, 100, 120)),
                         (list_x, list_y))

        # Vertical divider
        pygame.draw.line(screen, (60, 60, 80),
                         (px + left_w + 10, div_y + 2),
                         (px + left_w + 10, py + ph - 10))

        # Right panel: selected recipe details
        if recipes and 0 <= self.recipe_idx < len(recipes):
            sel = recipes[self.recipe_idx]
            self._draw_recipe_details(screen, font_sm, font_md,
                                      sel, player, detail_x, detail_y,
                                      pw - left_w - 30)

        # Crafting progress bar
        if self.crafting:
            self._draw_progress_bar(screen, font_md, px, py, pw, ph)

        # Status message
        if self.craft_message:
            msg_color = (140, 220, 140) if "Crafted" in self.craft_message else (220, 140, 140)
            msg_surf = font_md.render(self.craft_message, True, msg_color)
            screen.blit(msg_surf, (px + pw // 2 - msg_surf.get_width() // 2, py + ph - 28))

        # Controls hint
        hints = font_sm.render("W/S: navigate  Enter: craft  Esc: close", True, (90, 90, 110))
        screen.blit(hints, (px + 10, py + ph - 16))

    def _draw_recipe_details(self, screen, font_sm, font_md,
                             recipe_name: str, player, x: int, y: int, width: int):
        """Draw the detail panel for a selected recipe."""
        from game.systems.crafting import RECIPES

        if recipe_name not in RECIPES:
            return

        count, ingredients, tool, station, craft_time = RECIPES[recipe_name]

        # Recipe name and output
        item_data = ITEMS.get(recipe_name)
        name_label = f"{recipe_name}" + (f" x{count}" if count > 1 else "")
        screen.blit(font_md.render(name_label, True, (220, 230, 255)), (x, y))
        y += 22

        if item_data:
            # Description (truncate to fit)
            desc = item_data.description[:60]
            screen.blit(font_sm.render(desc, True, (170, 170, 190)), (x, y))
            y += 15
            # Stats line
            stats = []
            if item_data.damage > 0: stats.append(f"DMG:{item_data.damage}")
            if item_data.defense > 0: stats.append(f"DEF:{item_data.defense}")
            if item_data.heal > 0: stats.append(f"HEAL:{item_data.heal}")
            stats.append(f"Val:{item_data.value}g")
            screen.blit(font_sm.render("  ".join(stats), True, (180, 200, 160)), (x, y))
            y += 16
        y += 6

        # Ingredients
        screen.blit(font_md.render("Ingredients:", True, (200, 200, 220)), (x, y))
        y += 20
        ing_status = self._has_ingredients(recipe_name, player)
        for ing_name, (have, need) in ing_status.items():
            if have >= need:
                color = (100, 220, 100)  # green - have enough
                marker = "+"
            else:
                color = (220, 100, 100)  # red - missing
                marker = "-"
            label = f" {marker} {ing_name}: {have}/{need}"
            screen.blit(font_sm.render(label, True, color), (x + 5, y))
            y += 16
        y += 8

        # Requirements
        screen.blit(font_md.render("Requirements:", True, (200, 200, 220)), (x, y))
        y += 20

        # Tool
        if tool:
            has_tool = player.count_item(tool) > 0
            color = (100, 220, 100) if has_tool else (220, 100, 100)
            screen.blit(font_sm.render(f" Tool: {tool}", True, color), (x + 5, y))
            y += 16

        # Workstation
        if station:
            screen.blit(font_sm.render(f" Station: {station}", True, (170, 170, 190)), (x + 5, y))
            y += 16

        # Skill requirement
        skill_req = RECIPE_SKILL_REQUIREMENTS.get(recipe_name)
        if skill_req:
            sk_name, sk_level = skill_req
            player_level = player.skills.get(sk_name, 0)
            met = player_level >= sk_level
            color = (100, 220, 100) if met else (220, 100, 100)
            screen.blit(font_sm.render(
                f" Skill: {sk_name} {player_level}/{sk_level}", True, color), (x + 5, y))
            y += 16

        # Craft time
        ui_time = max(1.0, min(3.0, craft_time * 0.4))
        screen.blit(font_sm.render(f" Time: {ui_time:.1f}s", True, (150, 150, 170)), (x + 5, y))
        y += 16

        # XP reward
        skill = WORKSTATION_SKILL_MAP.get(station, "woodcraft")
        xp_amt = 1.0 + craft_time * 0.15
        screen.blit(font_sm.render(f" XP: +{xp_amt:.1f} {skill}", True, (150, 180, 150)),
                     (x + 5, y))

    def _draw_progress_bar(self, screen, font_md, px, py, pw, ph):
        """Draw the crafting progress bar overlay."""
        elapsed = time.time() - self.craft_start
        progress = min(1.0, elapsed / self.craft_duration)

        bar_w, bar_h = 300, 24
        bar_x = px + pw // 2 - bar_w // 2
        bar_y = py + ph // 2 - bar_h // 2

        # Dark backdrop
        backdrop = pygame.Surface((pw, 60), pygame.SRCALPHA)
        backdrop.fill((10, 10, 20, 200))
        screen.blit(backdrop, (px, bar_y - 18))

        # Background bar
        pygame.draw.rect(screen, (40, 40, 60), (bar_x, bar_y, bar_w, bar_h))
        # Fill bar
        fill_w = int(bar_w * progress)
        color = (80, 180, 80) if progress < 1.0 else (100, 220, 100)
        pygame.draw.rect(screen, color, (bar_x, bar_y, fill_w, bar_h))
        # Border
        pygame.draw.rect(screen, (120, 140, 180), (bar_x, bar_y, bar_w, bar_h), 1)

        # Label
        pct = int(progress * 100)
        label = font_md.render(f"Crafting {self.craft_recipe}... {pct}%", True, (220, 230, 255))
        screen.blit(label, (bar_x + bar_w // 2 - label.get_width() // 2, bar_y - 18))
