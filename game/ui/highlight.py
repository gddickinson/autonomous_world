"""Object Highlighting System — highlight specific tile types on screen.

Toggle with J key. Default highlights doors. Configurable via popup to
highlight any object category: doors, resources, furniture, terrain features.

Objects pulse with a colored glow overlay when highlighted.
"""

import pygame
import math
import time
from game.settings import *


# Object categories and their tile types
HIGHLIGHT_CATEGORIES = {
    "Doors & Entrances": {
        DOOR: "Door",
        LOCKED_DOOR: "Locked Door",
        ARCHWAY: "Archway",
        IRON_GATE: "Iron Gate",
    },
    "Resources": {
        ORE_VEIN: "Ore Vein",
        HERB_PATCH: "Herbs",
        BERRY_BUSH: "Berries",
        CLAY_PIT: "Clay",
        MUSHROOMS: "Mushrooms",
        GEM_DEPOSIT: "Gems",
        COPPER_VEIN: "Copper",
        FLAX_FIELD: "Flax",
    },
    "Furniture": {
        TABLE: "Table",
        BED: "Bed",
        CHEST: "Chest",
        BARREL: "Barrel",
        BOOKSHELF: "Bookshelf",
        THRONE: "Throne",
        ALTAR: "Altar",
    },
    "Crafting": {
        ANVIL: "Anvil",
        FORGE_FIRE: "Forge",
        FIREPLACE: "Fireplace",
    },
    "Navigation": {
        STAIRS_UP: "Stairs Up",
        STAIRS_DOWN: "Stairs Down",
        BRIDGE: "Bridge",
        ROAD: "Road",
        WELL: "Well",
    },
    "Terrain": {
        WATER: "Water",
        FARMLAND: "Farmland",
        GRAVESTONE: "Grave",
    },
}

# Colors for each category
CATEGORY_COLORS = {
    "Doors & Entrances": (255, 200, 50, 120),    # gold
    "Resources": (50, 255, 100, 100),              # green
    "Furniture": (100, 150, 255, 80),              # blue
    "Crafting": (255, 120, 50, 100),               # orange
    "Navigation": (200, 200, 255, 90),             # light blue
    "Terrain": (150, 255, 200, 70),                # teal
}


class HighlightSystem:
    """Manages object highlighting on the game screen."""

    def __init__(self):
        self.active = False
        self.selected_category = "Doors & Entrances"
        self.selected_tiles = set(HIGHLIGHT_CATEGORIES["Doors & Entrances"].keys())
        self.highlight_radius = 20  # tiles from player
        self.pulse_speed = 3.0  # pulse frequency
        self.show_picker = False  # category picker popup

    def toggle(self):
        """Toggle highlighting on/off."""
        self.active = not self.active

    def toggle_picker(self):
        """Toggle the category picker popup."""
        self.show_picker = not self.show_picker

    def set_category(self, category_name: str):
        """Set which category of objects to highlight."""
        if category_name in HIGHLIGHT_CATEGORIES:
            self.selected_category = category_name
            self.selected_tiles = set(HIGHLIGHT_CATEGORIES[category_name].keys())

    def cycle_category(self):
        """Cycle to next category."""
        cats = list(HIGHLIGHT_CATEGORIES.keys())
        idx = cats.index(self.selected_category)
        self.selected_category = cats[(idx + 1) % len(cats)]
        self.selected_tiles = set(HIGHLIGHT_CATEGORIES[self.selected_category].keys())

    def draw_highlights(self, screen, world, camera, player):
        """Draw pulsing glow on highlighted tiles within radius of player."""
        if not self.active:
            return

        ts = camera.tile_size
        pulse = (math.sin(time.time() * self.pulse_speed) + 1.0) / 2.0  # 0-1
        color = CATEGORY_COLORS.get(self.selected_category, (255, 255, 100, 100))
        alpha = int(color[3] * (0.4 + pulse * 0.6))  # pulse between 40-100% alpha
        glow_color = (color[0], color[1], color[2], alpha)

        px, py = int(player.x), int(player.y)
        r = self.highlight_radius

        # Create glow surface once per frame
        glow = pygame.Surface((ts, ts), pygame.SRCALPHA)

        count = 0
        for dy in range(-r, r + 1):
            wy = py + dy
            if wy < 0 or wy >= world.height:
                continue
            for dx in range(-r, r + 1):
                wx = px + dx
                if wx < 0 or wx >= world.width:
                    continue
                # Distance check (circular, not square)
                if dx * dx + dy * dy > r * r:
                    continue

                tile = world.tiles[wy][wx]
                if tile in self.selected_tiles:
                    sx, sy = camera.world_to_screen(float(wx), float(wy))
                    if -ts < sx < screen.get_width() + ts and -ts < sy < screen.get_height() + ts:
                        glow.fill(glow_color)
                        screen.blit(glow, (int(sx), int(sy)))
                        count += 1

        # Draw category label
        font = pygame.font.SysFont("monospace", 12)
        label = f"[J] Highlighting: {self.selected_category} ({count} found)"
        label_surf = font.render(label, True, (color[0], color[1], color[2]))
        bg = pygame.Surface((label_surf.get_width() + 10, 18), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        screen.blit(bg, (screen.get_width() // 2 - label_surf.get_width() // 2 - 5,
                         screen.get_height() - 30))
        screen.blit(label_surf, (screen.get_width() // 2 - label_surf.get_width() // 2,
                                  screen.get_height() - 28))

    def draw_picker(self, screen):
        """Draw category picker popup."""
        if not self.show_picker:
            return

        font = pygame.font.SysFont("monospace", 14)
        cats = list(HIGHLIGHT_CATEGORIES.keys())
        pw = 280
        ph = len(cats) * 24 + 40
        px = screen.get_width() // 2 - pw // 2
        py = screen.get_height() // 2 - ph // 2

        # Background
        bg = pygame.Surface((pw, ph), pygame.SRCALPHA)
        bg.fill((20, 20, 40, 230))
        screen.blit(bg, (px, py))
        pygame.draw.rect(screen, (80, 100, 140), (px, py, pw, ph), 1)

        # Title
        title = font.render("Highlight Category (J to cycle)", True, (200, 220, 255))
        screen.blit(title, (px + 10, py + 8))

        # Categories
        y = py + 32
        for cat in cats:
            color = CATEGORY_COLORS.get(cat, (200, 200, 200, 100))
            is_selected = cat == self.selected_category
            text_color = (255, 255, 100) if is_selected else (180, 180, 200)
            prefix = "> " if is_selected else "  "
            count = len(HIGHLIGHT_CATEGORIES[cat])
            label = f"{prefix}{cat} ({count} types)"
            screen.blit(font.render(label, True, text_color), (px + 10, y))
            # Color swatch
            pygame.draw.rect(screen, (color[0], color[1], color[2]),
                           (px + pw - 25, y + 3, 12, 12))
            y += 24

    def handle_key(self, key) -> bool:
        """Handle key input for highlighting. Returns True if consumed."""
        if key == pygame.K_j:
            if self.show_picker:
                self.cycle_category()
            else:
                self.toggle()
            return True
        if key == pygame.K_k:
            self.toggle_picker()
            return True
        return False
