"""God Mode editing and manipulation tools.

Provides terrain painting, entity spawning, building placement,
NPC editing, transmutation, settlement creation, and a text console
for direct world manipulation in god mode.
"""

import math
import random
import pygame
from typing import Optional, List, Tuple, Dict

from game.settings import (
    # Terrain types
    WATER, SAND, GRASS, FOREST, DENSE_FOREST, MOUNTAIN, SNOW, ROAD,
    FLOOR, WALL, BRIDGE, FARMLAND, SWAMP, BUILT_WALL, BUILT_FLOOR,
    TREE_STUMP, TILLED_SOIL, TABLE, BED, CHEST, DOOR, STAIRS_UP,
    STAIRS_DOWN, WINDOW, LOCKED_DOOR, ORE_VEIN, HERB_PATCH, BERRY_BUSH,
    CLAY_PIT, MUSHROOMS, WHEAT_FIELD, VEGETABLE_PLOT, FRUIT_TREE,
    FLOWER_BED, GEM_DEPOSIT, COPPER_VEIN, FLAX_FIELD, BEEHIVE, SALT_FLAT,
    RUBBLE, SHALLOW_WATER, ROCKY_GROUND, MARSH, GRAVEL_ROAD, FALLEN_TREE,
    WELL, PILLAR, ALTAR, FIREPLACE, COBBLESTONE, STABLE_FLOOR,
    FOUNTAIN, CARPET, MOSAIC, ARCHWAY, IRON_GATE, CLIFF, GORGE,
    MOUNTAIN_PASS, DIRT_TRACK, THRONE, BOOKSHELF, BARREL, ANVIL, FORGE_FIRE,
    # Colors
    TERRAIN_COLORS, WHITE, BLACK, RED, GREEN, BLUE, YELLOW, ORANGE,
    GRAY, DARK_GRAY, LIGHT_GRAY,
    UI_BG, UI_BORDER, UI_TEXT, UI_HIGHLIGHT,
    # Display
    SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE,
    # Creature / NPC data
    CREATURE_TYPES, NPC_NAMES,
)
from game.core.creature import Creature
from game.core.npc import NPC


# ====================================================================
# A. Terrain Painter
# ====================================================================

class TerrainPainter:
    """Paint terrain tiles with the mouse."""

    PALETTE = [
        ("Water", WATER),
        ("Shallow", SHALLOW_WATER),
        ("Sand", SAND),
        ("Grass", GRASS),
        ("Forest", FOREST),
        ("Dense For", DENSE_FOREST),
        ("Mountain", MOUNTAIN),
        ("Snow", SNOW),
        ("Road", ROAD),
        ("Gravel Rd", GRAVEL_ROAD),
        ("Dirt Trk", DIRT_TRACK),
        ("Cobble", COBBLESTONE),
        ("Swamp", SWAMP),
        ("Marsh", MARSH),
        ("Farmland", FARMLAND),
        ("Wheat", WHEAT_FIELD),
        ("Veg Plot", VEGETABLE_PLOT),
        ("Tilled", TILLED_SOIL),
        ("Wall", WALL),
        ("Built Wall", BUILT_WALL),
        ("Floor", FLOOR),
        ("Built Flr", BUILT_FLOOR),
        ("Door", DOOR),
        ("Window", WINDOW),
        ("Bridge", BRIDGE),
        ("Rubble", RUBBLE),
        ("Rocky", ROCKY_GROUND),
        ("Cliff", CLIFF),
        ("Mt Pass", MOUNTAIN_PASS),
        ("Ore Vein", ORE_VEIN),
        ("Copper", COPPER_VEIN),
        ("Gem", GEM_DEPOSIT),
        ("Herb", HERB_PATCH),
        ("Berry", BERRY_BUSH),
        ("Mushroom", MUSHROOMS),
        ("Flower", FLOWER_BED),
        ("Fruit Tr", FRUIT_TREE),
        ("Flax", FLAX_FIELD),
        ("Beehive", BEEHIVE),
        ("Salt", SALT_FLAT),
        ("Clay", CLAY_PIT),
        ("Table", TABLE),
        ("Bed", BED),
        ("Chest", CHEST),
        ("Barrel", BARREL),
        ("Anvil", ANVIL),
        ("Forge", FORGE_FIRE),
        ("Fireplace", FIREPLACE),
        ("Fountain", FOUNTAIN),
        ("Well", WELL),
        ("Pillar", PILLAR),
        ("Altar", ALTAR),
        ("Throne", THRONE),
        ("Bookshelf", BOOKSHELF),
        ("Carpet", CARPET),
        ("Mosaic", MOSAIC),
        ("Archway", ARCHWAY),
        ("Iron Gate", IRON_GATE),
        ("StairsUp", STAIRS_UP),
        ("StairsDn", STAIRS_DOWN),
        ("Stable Fl", STABLE_FLOOR),
        ("Tree Stmp", TREE_STUMP),
        ("FallenTr", FALLEN_TREE),
        ("Lock Door", LOCKED_DOOR),
    ]

    def __init__(self):
        self.selected_tile_type = GRASS
        self.selected_idx = 3  # GRASS
        self.brush_size = 1  # 1, 3, 5, 7, 9
        self.palette_open = False
        self.palette_scroll = 0
        self._font = None

    def _get_font(self):
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 10)
        return self._font

    def paint(self, world, wx, wy):
        """Paint the selected tile at world coordinates using modify_tile."""
        r = self.brush_size // 2
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                tx, ty = wx + dx, wy + dy
                if 0 <= tx < world.width and 0 <= ty < world.height:
                    world.modify_tile(tx, ty, self.selected_tile_type)

    def draw_palette(self, screen):
        """Draw tile selection palette when open."""
        if not self.palette_open:
            return

        # Background panel
        panel_w = 340
        cols = 8
        visible_rows = 10
        total_rows = (len(self.PALETTE) + cols - 1) // cols
        panel_h = min(visible_rows, total_rows) * 48 + 40
        panel_x = 10
        panel_y = 80

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 20, 35, 220))
        screen.blit(bg, (panel_x, panel_y))
        pygame.draw.rect(screen, UI_BORDER, (panel_x, panel_y, panel_w, panel_h), 1)

        font = self._get_font()
        header = font.render(f"Terrain Palette (Brush: {self.brush_size}x{self.brush_size})", True, WHITE)
        screen.blit(header, (panel_x + 5, panel_y + 3))

        x_start = panel_x + 5
        y_start = panel_y + 20
        cell_w = 40
        cell_h = 48

        start_row = self.palette_scroll
        start_idx = start_row * cols

        for i in range(start_idx, min(len(self.PALETTE), start_idx + visible_rows * cols)):
            name, tile_type = self.PALETTE[i]
            row = (i - start_idx) // cols
            col = (i - start_idx) % cols
            cx = x_start + col * cell_w
            cy = y_start + row * cell_h

            color = TERRAIN_COLORS.get(tile_type, (100, 100, 100))
            rect = pygame.Rect(cx, cy, 32, 32)
            pygame.draw.rect(screen, color, rect)
            if tile_type == self.selected_tile_type:
                pygame.draw.rect(screen, WHITE, rect, 2)
            else:
                pygame.draw.rect(screen, DARK_GRAY, rect, 1)

            label = font.render(name[:7], True, LIGHT_GRAY)
            screen.blit(label, (cx, cy + 33))

    def handle_palette_click(self, mx, my):
        """Handle click on palette. Returns True if click was consumed."""
        if not self.palette_open:
            return False

        panel_x, panel_y = 10, 80
        panel_w = 340
        cols = 8
        visible_rows = 10
        panel_h = min(visible_rows, ((len(self.PALETTE) + cols - 1) // cols)) * 48 + 40

        if not (panel_x <= mx <= panel_x + panel_w and panel_y <= my <= panel_y + panel_h):
            return False

        x_start = panel_x + 5
        y_start = panel_y + 20
        cell_w = 40
        cell_h = 48

        rel_x = mx - x_start
        rel_y = my - y_start
        if rel_x < 0 or rel_y < 0:
            return True

        col = rel_x // cell_w
        row = rel_y // cell_h
        if col >= cols:
            return True

        idx = (self.palette_scroll + row) * cols + col
        if 0 <= idx < len(self.PALETTE):
            self.selected_idx = idx
            self.selected_tile_type = self.PALETTE[idx][1]
        return True

    def handle_key(self, key):
        """Handle palette key shortcuts."""
        if key == pygame.K_LEFTBRACKET:
            self.brush_size = max(1, self.brush_size - 2)
        elif key == pygame.K_RIGHTBRACKET:
            self.brush_size = min(9, self.brush_size + 2)
        elif key == pygame.K_TAB:
            self.palette_open = not self.palette_open

    def handle_scroll(self, direction):
        """Handle scroll within palette."""
        if not self.palette_open:
            return
        cols = 8
        total_rows = (len(self.PALETTE) + cols - 1) // cols
        if direction > 0:
            self.palette_scroll = max(0, self.palette_scroll - 1)
        else:
            self.palette_scroll = min(total_rows - 5, self.palette_scroll + 1)

    def get_status_text(self):
        name = self.PALETTE[self.selected_idx][0] if self.selected_idx < len(self.PALETTE) else "?"
        return f"Paint: {name} | Brush: {self.brush_size}x{self.brush_size} | [Tab] palette | [/] brush size"


# ====================================================================
# B. Entity Spawner
# ====================================================================

class EntitySpawner:
    """Spawn NPCs, creatures, and items at the mouse cursor."""

    CREATURE_LIST = sorted(CREATURE_TYPES.keys())
    NPC_CLASSES = ["Fighter", "Wizard", "Cleric", "Rogue", "Ranger", "Bard",
                   "Paladin", "Druid", "Monk", "Barbarian", "Sorcerer", "Warlock"]
    NPC_RACES = ["Human", "Elf", "Dwarf", "Half-Orc", "Halfling", "Gnome", "Tiefling"]

    def __init__(self):
        self.mode = "creature"  # creature, npc
        self.selected_creature_idx = 0
        self.selected_class_idx = 0
        self.selected_race_idx = 0
        self.spawn_level = 3
        self.list_open = False
        self.list_scroll = 0
        self._font = None

    def _get_font(self):
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 11)
        return self._font

    @property
    def selected_creature(self):
        return self.CREATURE_LIST[self.selected_creature_idx]

    @property
    def selected_class(self):
        return self.NPC_CLASSES[self.selected_class_idx]

    @property
    def selected_race(self):
        return self.NPC_RACES[self.selected_race_idx]

    def spawn(self, world_mgr, wx, wy):
        """Spawn the selected entity at world coordinates."""
        if self.mode == "creature":
            creature = Creature(float(wx), float(wy), self.selected_creature)
            creature.home_x = float(wx)
            creature.home_y = float(wy)
            creature.leash_range = 30.0
            world_mgr.creatures.append(creature)
            return f"Spawned {self.selected_creature} at ({wx},{wy})"

        elif self.mode == "npc":
            name = random.choice(NPC_NAMES) + f"_{random.randint(100, 999)}"
            profession = self.selected_class  # use class as profession fallback
            npc = NPC(float(wx), float(wy), name, profession,
                      char_class=self.selected_class, race=self.selected_race,
                      level=self.spawn_level)
            npc.home_x = float(wx)
            npc.home_y = float(wy)
            world_mgr.npcs.append(npc)
            return f"Spawned {name} ({self.selected_race} {self.selected_class} Lv{self.spawn_level})"

        return "Nothing to spawn"

    def draw_spawner_ui(self, screen):
        """Draw spawn selection panel."""
        if not self.list_open:
            return

        font = self._get_font()
        panel_x = 10
        panel_y = 80
        panel_w = 260
        line_h = 18

        if self.mode == "creature":
            items = self.CREATURE_LIST
            selected_idx = self.selected_creature_idx
            title = "CREATURES"
        else:
            items = [f"{c} ({self.selected_race})" for c in self.NPC_CLASSES]
            selected_idx = self.selected_class_idx
            title = f"NPCs - Lv{self.spawn_level} {self.selected_race}"

        visible = min(20, len(items))
        panel_h = visible * line_h + 50

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 20, 35, 220))
        screen.blit(bg, (panel_x, panel_y))
        pygame.draw.rect(screen, UI_BORDER, (panel_x, panel_y, panel_w, panel_h), 1)

        header = font.render(f"== {title} ==", True, YELLOW)
        screen.blit(header, (panel_x + 5, panel_y + 3))

        controls = font.render("[M]ode [+/-]Level [R]ace", True, GRAY)
        screen.blit(controls, (panel_x + 5, panel_y + 18))

        start = max(0, min(self.list_scroll, len(items) - visible))
        for i in range(start, min(start + visible, len(items))):
            name = items[i]
            row = i - start
            cy = panel_y + 38 + row * line_h
            color = YELLOW if i == selected_idx else UI_TEXT
            prefix = "> " if i == selected_idx else "  "
            label = font.render(f"{prefix}{name}", True, color)
            screen.blit(label, (panel_x + 5, cy))

    def handle_spawner_click(self, mx, my):
        """Handle click on spawner list. Returns True if consumed."""
        if not self.list_open:
            return False

        panel_x, panel_y = 10, 80
        panel_w = 260
        line_h = 18

        if self.mode == "creature":
            items = self.CREATURE_LIST
        else:
            items = self.NPC_CLASSES

        visible = min(20, len(items))
        panel_h = visible * line_h + 50

        if not (panel_x <= mx <= panel_x + panel_w and panel_y <= my <= panel_y + panel_h):
            return False

        rel_y = my - (panel_y + 38)
        if rel_y < 0:
            return True

        row = rel_y // line_h
        start = max(0, min(self.list_scroll, len(items) - visible))
        idx = start + row
        if 0 <= idx < len(items):
            if self.mode == "creature":
                self.selected_creature_idx = idx
            else:
                self.selected_class_idx = idx
        return True

    def handle_key(self, key):
        """Handle spawner key shortcuts."""
        if key == pygame.K_TAB:
            self.list_open = not self.list_open
        elif key == pygame.K_m:
            self.mode = "npc" if self.mode == "creature" else "creature"
        elif key == pygame.K_EQUALS or key == pygame.K_PLUS:
            self.spawn_level = min(20, self.spawn_level + 1)
        elif key == pygame.K_MINUS:
            self.spawn_level = max(1, self.spawn_level - 1)
        elif key == pygame.K_r:
            self.selected_race_idx = (self.selected_race_idx + 1) % len(self.NPC_RACES)
        elif key == pygame.K_UP:
            if self.mode == "creature":
                self.selected_creature_idx = max(0, self.selected_creature_idx - 1)
            else:
                self.selected_class_idx = max(0, self.selected_class_idx - 1)
        elif key == pygame.K_DOWN:
            if self.mode == "creature":
                self.selected_creature_idx = min(len(self.CREATURE_LIST) - 1,
                                                  self.selected_creature_idx + 1)
            else:
                self.selected_class_idx = min(len(self.NPC_CLASSES) - 1,
                                               self.selected_class_idx + 1)

    def handle_scroll(self, direction):
        """Handle scroll in spawner list."""
        if not self.list_open:
            return
        if direction > 0:
            self.list_scroll = max(0, self.list_scroll - 1)
        else:
            n = len(self.CREATURE_LIST if self.mode == "creature" else self.NPC_CLASSES)
            self.list_scroll = min(n - 10, self.list_scroll + 1)

    def get_status_text(self):
        if self.mode == "creature":
            return f"Spawn: {self.selected_creature} | [Tab] list | [M] switch to NPC"
        else:
            return (f"Spawn: {self.selected_race} {self.selected_class} Lv{self.spawn_level} | "
                    f"[Tab] list | [M] switch to creature | [R] race | [+/-] level")


# ====================================================================
# C. Building Placer
# ====================================================================

class BuildingPlacer:
    """Place building blueprints in the world."""

    def __init__(self):
        from game.world.buildings import ALL_BLUEPRINTS
        self.blueprints = list(ALL_BLUEPRINTS)
        self.selected_idx = 0
        self.preview_visible = True
        self.rotation = 0  # 0, 90, 180, 270
        self.list_open = False
        self.list_scroll = 0
        self._font = None

    def _get_font(self):
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 11)
        return self._font

    @property
    def selected_blueprint(self):
        return self._get_rotated_bp()

    def _get_rotated_bp(self):
        bp = self.blueprints[self.selected_idx]
        rotations = self.rotation // 90
        for _ in range(rotations):
            bp = bp.rotated()
        return bp

    def place(self, world, wx, wy):
        """Place the selected blueprint at world coordinates."""
        bp = self._get_rotated_bp()

        # Stamp tiles - skip GRASS tiles (exterior)
        placed = 0
        for by in range(bp.height):
            for bx in range(bp.width):
                tile = bp.tiles[by][bx]
                if tile != GRASS:
                    tx, ty = wx + bx, wy + by
                    if 0 <= tx < world.width and 0 <= ty < world.height:
                        world.modify_tile(tx, ty, tile)
                        placed += 1

        return f"Placed {bp.name} ({placed} tiles) at ({wx},{wy})"

    def draw_preview(self, screen, camera, wx, wy):
        """Draw a ghost preview of the building at cursor position."""
        if not self.preview_visible:
            return

        bp = self._get_rotated_bp()
        for by in range(bp.height):
            for bx in range(bp.width):
                tile = bp.tiles[by][bx]
                if tile == GRASS:
                    continue
                sx = (wx + bx) * TILE_SIZE - int(camera.x)
                sy = (wy + by) * TILE_SIZE - int(camera.y)

                # Skip if off-screen
                if sx < -TILE_SIZE or sx > SCREEN_WIDTH or sy < -TILE_SIZE or sy > SCREEN_HEIGHT:
                    continue

                color = TERRAIN_COLORS.get(tile, (100, 100, 100))
                surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                surf.fill((color[0], color[1], color[2], 128))
                screen.blit(surf, (sx, sy))

    def draw_blueprint_list(self, screen):
        """Draw blueprint selection panel."""
        if not self.list_open:
            return

        font = self._get_font()
        panel_x = 10
        panel_y = 80
        panel_w = 280
        line_h = 16
        visible = 25
        panel_h = visible * line_h + 35

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 20, 35, 220))
        screen.blit(bg, (panel_x, panel_y))
        pygame.draw.rect(screen, UI_BORDER, (panel_x, panel_y, panel_w, panel_h), 1)

        bp = self.blueprints[self.selected_idx]
        header = font.render(f"== BUILDINGS == Rot:{self.rotation}", True, YELLOW)
        screen.blit(header, (panel_x + 5, panel_y + 3))

        desc = font.render(f"{bp.name} ({bp.width}x{bp.height}) {bp.kind}", True, GRAY)
        screen.blit(desc, (panel_x + 5, panel_y + 17))

        start = max(0, min(self.list_scroll, len(self.blueprints) - visible))
        for i in range(start, min(start + visible, len(self.blueprints))):
            b = self.blueprints[i]
            row = i - start
            cy = panel_y + 33 + row * line_h
            color = YELLOW if i == self.selected_idx else UI_TEXT
            prefix = "> " if i == self.selected_idx else "  "
            label = font.render(f"{prefix}{b.name} ({b.width}x{b.height})", True, color)
            screen.blit(label, (panel_x + 5, cy))

    def handle_list_click(self, mx, my):
        """Handle click on blueprint list. Returns True if consumed."""
        if not self.list_open:
            return False

        panel_x, panel_y = 10, 80
        panel_w = 280
        line_h = 16
        visible = 25
        panel_h = visible * line_h + 35

        if not (panel_x <= mx <= panel_x + panel_w and panel_y <= my <= panel_y + panel_h):
            return False

        rel_y = my - (panel_y + 33)
        if rel_y < 0:
            return True

        row = rel_y // line_h
        start = max(0, min(self.list_scroll, len(self.blueprints) - visible))
        idx = start + row
        if 0 <= idx < len(self.blueprints):
            self.selected_idx = idx
        return True

    def handle_key(self, key):
        """Handle building placer key shortcuts."""
        if key == pygame.K_TAB:
            self.list_open = not self.list_open
        elif key == pygame.K_r:
            self.rotation = (self.rotation + 90) % 360
        elif key == pygame.K_p:
            self.preview_visible = not self.preview_visible
        elif key == pygame.K_UP:
            self.selected_idx = max(0, self.selected_idx - 1)
        elif key == pygame.K_DOWN:
            self.selected_idx = min(len(self.blueprints) - 1, self.selected_idx + 1)

    def handle_scroll(self, direction):
        """Handle scroll in blueprint list."""
        if not self.list_open:
            return
        if direction > 0:
            self.list_scroll = max(0, self.list_scroll - 1)
        else:
            self.list_scroll = min(len(self.blueprints) - 15, self.list_scroll + 1)

    def get_status_text(self):
        bp = self.blueprints[self.selected_idx]
        return (f"Build: {bp.name} ({bp.width}x{bp.height}) | "
                f"Rot:{self.rotation} | [Tab] list | [R] rotate | [P] preview")


# ====================================================================
# D. NPC Editor
# ====================================================================

class NPCEditor:
    """Edit any NPC's stats, skills, memories, and more."""

    EDITABLE_FIELDS = [
        ("name", str), ("race", str), ("char_class", str),
        ("profession", str), ("level", int), ("hp", float),
        ("max_hp", int), ("npc_gold", float), ("title", str),
        ("faction", str), ("alignment", str), ("age", float),
        ("friendliness", float), ("curiosity", float), ("bravery", float),
        ("mood", float), ("consciousness", int),
    ]

    def __init__(self):
        self.editing_npc: Optional[NPC] = None
        self.editing_field: Optional[str] = None
        self.editing_field_idx = 0
        self.input_text = ""
        self.input_active = False
        self.panel_open = False
        self._font = None
        self._font_small = None

    def _get_font(self):
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 12)
        return self._font

    def _get_font_small(self):
        if self._font_small is None:
            self._font_small = pygame.font.SysFont("monospace", 10)
        return self._font_small

    def start_edit(self, npc):
        """Begin editing an NPC."""
        self.editing_npc = npc
        self.panel_open = True
        self.editing_field = None
        self.input_active = False
        self.editing_field_idx = 0

    def stop_edit(self):
        """Stop editing."""
        self.editing_npc = None
        self.panel_open = False
        self.input_active = False

    def set_field(self, field, value):
        """Set a field on the editing NPC."""
        if self.editing_npc is None:
            return False
        if not hasattr(self.editing_npc, field):
            return False

        # Find the expected type
        ftype = str
        for fname, ft in self.EDITABLE_FIELDS:
            if fname == field:
                ftype = ft
                break

        try:
            converted = ftype(value)
            setattr(self.editing_npc, field, converted)
            return True
        except (ValueError, TypeError):
            return False

    def commit_edit(self):
        """Commit the current text input to the field being edited."""
        if self.editing_npc and self.editing_field and self.input_text:
            self.set_field(self.editing_field, self.input_text)
            self.input_active = False
            self.editing_field = None
            self.input_text = ""

    def add_memory(self, text, category="observation", importance=3):
        """Add a memory to the NPC."""
        if self.editing_npc is None:
            return
        self.editing_npc.add_memory(category, text, importance)

    def clear_memories(self):
        """Clear all NPC memories."""
        if self.editing_npc is None:
            return
        self.editing_npc.memories = []

    def set_skill(self, skill, level):
        """Set a skill level on the NPC."""
        if self.editing_npc is None:
            return
        if hasattr(self.editing_npc, 'npc_skills'):
            self.editing_npc.npc_skills[skill] = level

    def change_profession(self, new_profession):
        """Change the NPC's profession."""
        if self.editing_npc is None:
            return
        self.editing_npc.profession = new_profession

    def heal_npc(self):
        """Full heal the NPC."""
        if self.editing_npc is None:
            return
        self.editing_npc.hp = self.editing_npc.max_hp
        for need in self.editing_npc.needs:
            self.editing_npc.needs[need] = 100.0

    def kill_npc(self, world_mgr):
        """Kill the NPC."""
        if self.editing_npc is None:
            return
        self.editing_npc.hp = 0
        self.editing_npc.alive = False
        if self.editing_npc in world_mgr.npcs:
            world_mgr.npcs.remove(self.editing_npc)
        self.stop_edit()

    def give_gold(self, amount):
        """Give gold to the NPC."""
        if self.editing_npc is None:
            return
        self.editing_npc.npc_gold += amount

    def level_up(self):
        """Level up the NPC."""
        if self.editing_npc is None:
            return
        self.editing_npc.level += 1
        self.editing_npc.max_hp += 8
        self.editing_npc.hp = self.editing_npc.max_hp

    def transform_to_creature(self, creature_kind, world_mgr):
        """Transform this NPC into a creature (polymorph!)."""
        if self.editing_npc is None:
            return "No NPC selected"
        npc = self.editing_npc
        creature = Creature(npc.x, npc.y, creature_kind)
        creature.home_x = npc.home_x
        creature.home_y = npc.home_y
        creature.leash_range = 30.0
        world_mgr.creatures.append(creature)
        if npc in world_mgr.npcs:
            world_mgr.npcs.remove(npc)
        result = f"{npc.name} transformed into {creature_kind}!"
        self.stop_edit()
        return result

    def draw_editor(self, screen):
        """Draw NPC edit panel with editable fields."""
        if not self.editing_npc or not self.panel_open:
            return

        npc = self.editing_npc
        font = self._get_font()
        font_small = self._get_font_small()

        panel_w = 340
        panel_h = 520
        panel_x = SCREEN_WIDTH - panel_w - 10
        panel_y = 50

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 20, 35, 230))
        screen.blit(bg, (panel_x, panel_y))
        pygame.draw.rect(screen, UI_BORDER, (panel_x, panel_y, panel_w, panel_h), 1)

        # Header
        header = font.render(f"=== EDITING: {npc.name} ===", True, YELLOW)
        screen.blit(header, (panel_x + 5, panel_y + 5))

        cy = panel_y + 25

        # Editable fields
        for i, (field, ftype) in enumerate(self.EDITABLE_FIELDS):
            value = getattr(npc, field, "?")
            if isinstance(value, float):
                value = f"{value:.1f}"

            is_editing = (self.input_active and self.editing_field == field)
            is_selected = (i == self.editing_field_idx and not self.input_active)

            if is_editing:
                prefix = ">> "
                color = GREEN
                display = f"{prefix}{field}: [{self.input_text}_]"
            elif is_selected:
                prefix = "> "
                color = UI_HIGHLIGHT
                display = f"{prefix}{field}: {value}"
            else:
                prefix = "  "
                color = UI_TEXT
                display = f"{prefix}{field}: {value}"

            label = font_small.render(display, True, color)
            screen.blit(label, (panel_x + 5, cy))
            cy += 15

        cy += 5

        # Needs
        needs_header = font_small.render("--- Needs ---", True, GRAY)
        screen.blit(needs_header, (panel_x + 5, cy))
        cy += 14
        for need, val in npc.needs.items():
            color = RED if val < 20 else YELLOW if val < 50 else GREEN
            label = font_small.render(f"  {need}: {val:.0f}/100", True, color)
            screen.blit(label, (panel_x + 5, cy))
            cy += 13

        cy += 5

        # Skills (top 5)
        skills_header = font_small.render("--- Top Skills ---", True, GRAY)
        screen.blit(skills_header, (panel_x + 5, cy))
        cy += 14
        npc_skills = getattr(npc, 'npc_skills', {})
        top_skills = sorted(npc_skills.items(), key=lambda x: -x[1])[:5]
        for skill, lvl in top_skills:
            label = font_small.render(f"  {skill}: {lvl}", True, UI_TEXT)
            screen.blit(label, (panel_x + 5, cy))
            cy += 13

        cy += 5

        # Action buttons
        actions_header = font_small.render("--- Actions ---", True, GRAY)
        screen.blit(actions_header, (panel_x + 5, cy))
        cy += 14
        actions_text = [
            "[H] Heal  [K] Kill  [G] +100 Gold  [L] Level Up",
            "[C] Clear Memories  [T] Transform  [Esc] Close",
            "[Enter] Edit field  [Up/Down] Select field",
        ]
        for line in actions_text:
            label = font_small.render(line, True, GRAY)
            screen.blit(label, (panel_x + 5, cy))
            cy += 13

    def handle_key(self, key, world_mgr=None):
        """Handle editor key input. Returns status message or None."""
        if not self.editing_npc or not self.panel_open:
            return None

        if self.input_active:
            if key == pygame.K_RETURN:
                self.commit_edit()
                return f"Set {self.editing_field}"
            elif key == pygame.K_ESCAPE:
                self.input_active = False
                self.editing_field = None
                self.input_text = ""
                return None
            elif key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
                return None
            # Text input handled by text_input method below
            return None

        # Non-editing mode
        if key == pygame.K_ESCAPE:
            self.stop_edit()
            return "Editor closed"
        elif key == pygame.K_UP:
            self.editing_field_idx = max(0, self.editing_field_idx - 1)
        elif key == pygame.K_DOWN:
            self.editing_field_idx = min(len(self.EDITABLE_FIELDS) - 1,
                                         self.editing_field_idx + 1)
        elif key == pygame.K_RETURN:
            field, _ = self.EDITABLE_FIELDS[self.editing_field_idx]
            self.editing_field = field
            self.input_active = True
            self.input_text = str(getattr(self.editing_npc, field, ""))
        elif key == pygame.K_h:
            self.heal_npc()
            return f"Healed {self.editing_npc.name}"
        elif key == pygame.K_k:
            if world_mgr:
                name = self.editing_npc.name
                self.kill_npc(world_mgr)
                return f"Killed {name}"
        elif key == pygame.K_g:
            self.give_gold(100)
            return f"Gave 100 gold to {self.editing_npc.name}"
        elif key == pygame.K_l:
            self.level_up()
            return f"{self.editing_npc.name} leveled up to {self.editing_npc.level}"
        elif key == pygame.K_c:
            self.clear_memories()
            return f"Cleared memories of {self.editing_npc.name}"
        elif key == pygame.K_t:
            if world_mgr:
                return self.transform_to_creature("wolf", world_mgr)

        return None

    def handle_text_input(self, text):
        """Handle text input event for field editing."""
        if self.input_active:
            self.input_text += text

    def get_status_text(self):
        if self.editing_npc:
            return f"Editing: {self.editing_npc.name} | [Esc] close"
        return "Edit: Click on NPC to edit"


# ====================================================================
# E. Transmutation Tool
# ====================================================================

class TransmutationTool:
    """Change anything into anything else."""

    def __init__(self):
        self.source_tile = None  # last tile picked (eyedropper)
        self._font = None

    def _get_font(self):
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 11)
        return self._font

    def transmute_tile(self, world, wx, wy, new_tile):
        """Change a tile to any other tile type."""
        if 0 <= wx < world.width and 0 <= wy < world.height:
            old = world.tiles[wy][wx]
            world.modify_tile(wx, wy, new_tile)
            return f"Transmuted ({wx},{wy}): {old} -> {new_tile}"
        return "Out of bounds"

    def transmute_creature(self, world_mgr, creature, new_kind):
        """Change a creature's kind by replacing it."""
        old_kind = creature.kind
        new_creature = Creature(creature.x, creature.y, new_kind)
        new_creature.home_x = creature.home_x
        new_creature.home_y = creature.home_y
        new_creature.leash_range = creature.leash_range
        if creature in world_mgr.creatures:
            world_mgr.creatures.remove(creature)
        world_mgr.creatures.append(new_creature)
        return f"Transmuted {old_kind} -> {new_kind}"

    def mass_transmute(self, world, wx, wy, radius, old_tile, new_tile):
        """Change all tiles of one type to another in a radius."""
        count = 0
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue  # circular radius
                tx, ty = wx + dx, wy + dy
                if 0 <= tx < world.width and 0 <= ty < world.height:
                    if world.tiles[ty][tx] == old_tile:
                        world.modify_tile(tx, ty, new_tile)
                        count += 1
        return f"Transmuted {count} tiles: {old_tile} -> {new_tile}"

    def eyedropper(self, world, wx, wy):
        """Pick the tile type at a position."""
        if 0 <= wx < world.width and 0 <= wy < world.height:
            self.source_tile = world.tiles[wy][wx]
            # Find name
            for name, tile in TerrainPainter.PALETTE:
                if tile == self.source_tile:
                    return f"Picked: {name} ({self.source_tile})"
            return f"Picked: tile {self.source_tile}"
        return "Out of bounds"

    def fill_area(self, world, wx, wy, new_tile, max_tiles=500):
        """Flood fill from a position, replacing the original tile type."""
        if not (0 <= wx < world.width and 0 <= wy < world.height):
            return "Out of bounds"

        original = world.tiles[wy][wx]
        if original == new_tile:
            return "Same tile type"

        visited = set()
        queue = [(wx, wy)]
        count = 0

        while queue and count < max_tiles:
            x, y = queue.pop(0)
            if (x, y) in visited:
                continue
            if not (0 <= x < world.width and 0 <= y < world.height):
                continue
            if world.tiles[y][x] != original:
                continue

            visited.add((x, y))
            world.modify_tile(x, y, new_tile)
            count += 1

            queue.append((x + 1, y))
            queue.append((x - 1, y))
            queue.append((x, y + 1))
            queue.append((x, y - 1))

        return f"Fill: changed {count} tiles"

    def get_status_text(self):
        src = f"Source: {self.source_tile}" if self.source_tile is not None else "No source"
        return f"Transmute | {src} | Right-click: eyedropper | Left-click: apply"


# ====================================================================
# F. Settlement Creator
# ====================================================================

class SettlementCreator:
    """Create new settlements from god mode."""

    SETTLEMENT_KINDS = ["hamlet", "village", "town", "city", "castle"]

    def __init__(self):
        self.selected_kind_idx = 1  # village
        self.settlement_name = ""
        self.kingdom_name = ""
        self.input_active = False
        self.input_field = "name"  # name, kingdom
        self._font = None

    def _get_font(self):
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 11)
        return self._font

    @property
    def selected_kind(self):
        return self.SETTLEMENT_KINDS[self.selected_kind_idx]

    def create_settlement(self, world, wx, wy, name, kind):
        """Found a new settlement at the given position.

        Stamps a ring of road around the center and places some buildings.
        """
        from game.world.buildings import get_building_for_settlement, stamp_blueprint

        if not name:
            name = f"Settlement_{random.randint(100, 999)}"

        radius = {"hamlet": 8, "village": 15, "town": 25, "city": 40, "castle": 12}.get(kind, 15)
        num_buildings = {"hamlet": 3, "village": 6, "town": 12, "city": 20, "castle": 4}.get(kind, 6)

        rng = random.Random()

        # Stamp a small road ring / center
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                tx, ty = wx + dx, wy + dy
                if 0 <= tx < world.width and 0 <= ty < world.height:
                    world.modify_tile(tx, ty, COBBLESTONE)

        # Place buildings around center
        placed = 0
        attempts = 0
        while placed < num_buildings and attempts < 200:
            attempts += 1
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(4, radius * 0.8)
            bx = int(wx + math.cos(angle) * dist)
            by = int(wy + math.sin(angle) * dist)

            bp = get_building_for_settlement(kind, rng)
            if bx < 0 or by < 0 or bx + bp.width >= world.width or by + bp.height >= world.height:
                continue

            # Check overlap — simple check against building tiles
            overlap = False
            for cdy in range(bp.height):
                for cdx in range(bp.width):
                    tile = bp.tiles[cdy][cdx]
                    if tile != GRASS:
                        tx, ty_c = bx + cdx, by + cdy
                        if 0 <= tx < world.width and 0 <= ty_c < world.height:
                            existing = world.tiles[ty_c][tx]
                            if existing in (WALL, FLOOR, DOOR, TABLE, BED, CHEST,
                                            BUILT_WALL, BUILT_FLOOR, COBBLESTONE):
                                overlap = True
                                break
                    if overlap:
                        break
                if overlap:
                    break
            if overlap:
                continue

            # Stamp the building
            for cdy in range(bp.height):
                for cdx in range(bp.width):
                    tile = bp.tiles[cdy][cdx]
                    if tile != GRASS:
                        tx, ty_c = bx + cdx, by + cdy
                        if 0 <= tx < world.width and 0 <= ty_c < world.height:
                            world.modify_tile(tx, ty_c, tile)
            placed += 1

            # Add roads from building door to center
            for door_x, door_y in bp.door_pos:
                dx_abs, dy_abs = bx + door_x, by + door_y
                # Simple line of road tiles toward center
                steps = max(abs(dx_abs - wx), abs(dy_abs - wy))
                if steps > 0:
                    for s in range(steps + 1):
                        t = s / steps
                        rx = int(dx_abs + (wx - dx_abs) * t)
                        ry = int(dy_abs + (wy - dy_abs) * t)
                        if 0 <= rx < world.width and 0 <= ry < world.height:
                            existing = world.tiles[ry][rx]
                            if existing in (GRASS, SAND, DIRT_TRACK):
                                world.modify_tile(rx, ry, ROAD)

        # Add a structure to the world
        from game.world.world import Structure
        struct = Structure(name, kind, wx, wy, radius=radius)
        world.structures.append(struct)

        return f"Founded {name} ({kind}) with {placed} buildings at ({wx},{wy})"

    def draw_creator_ui(self, screen):
        """Draw settlement creation panel."""
        font = self._get_font()
        panel_x = 10
        panel_y = 80
        panel_w = 300
        panel_h = 140

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 20, 35, 220))
        screen.blit(bg, (panel_x, panel_y))
        pygame.draw.rect(screen, UI_BORDER, (panel_x, panel_y, panel_w, panel_h), 1)

        header = font.render("== FOUND SETTLEMENT ==", True, YELLOW)
        screen.blit(header, (panel_x + 5, panel_y + 5))

        kind = self.selected_kind
        kind_label = font.render(f"Kind: {kind} [K to cycle]", True, UI_TEXT)
        screen.blit(kind_label, (panel_x + 5, panel_y + 25))

        name_color = GREEN if (self.input_active and self.input_field == "name") else UI_TEXT
        name_display = self.settlement_name if self.settlement_name else "(auto)"
        name_label = font.render(f"Name: {name_display} [N to edit]", True, name_color)
        screen.blit(name_label, (panel_x + 5, panel_y + 45))

        info = font.render("Click to place settlement at cursor", True, GRAY)
        screen.blit(info, (panel_x + 5, panel_y + 75))

        controls = font.render("[K] kind  [N] name  [Click] place", True, GRAY)
        screen.blit(controls, (panel_x + 5, panel_y + 95))

    def handle_key(self, key):
        """Handle settlement creator keys."""
        if self.input_active:
            if key == pygame.K_RETURN or key == pygame.K_ESCAPE:
                self.input_active = False
                return None
            elif key == pygame.K_BACKSPACE:
                if self.input_field == "name":
                    self.settlement_name = self.settlement_name[:-1]
                return None
            return None

        if key == pygame.K_k:
            self.selected_kind_idx = (self.selected_kind_idx + 1) % len(self.SETTLEMENT_KINDS)
        elif key == pygame.K_n:
            self.input_active = True
            self.input_field = "name"
        return None

    def handle_text_input(self, text):
        """Handle text input."""
        if self.input_active:
            if self.input_field == "name":
                self.settlement_name += text

    def get_status_text(self):
        return f"Settle: {self.selected_kind} | [K] kind | [N] name | Click to place"


# ====================================================================
# G. God Console (Text Input)
# ====================================================================

class GodConsole:
    """Text command console for god mode."""

    COMMANDS = {
        "help":    "help — show all commands",
        "spawn":   "spawn <creature_kind> [count] — spawn creature(s) at cursor",
        "npc":     "npc <class> [race] [level] — spawn NPC at cursor",
        "tp":      "tp <x> <y> — teleport player",
        "time":    "time <speed> — set time speed multiplier",
        "gold":    "gold <amount> — give player gold",
        "kill":    "kill — kill entity nearest to cursor",
        "heal":    "heal — full heal entity nearest to cursor",
        "paint":   "paint <tile_name> <radius> — paint tiles around cursor",
        "fill":    "fill <tile_name> — flood fill from cursor",
        "settle":  "settle <name> <kind> — found settlement at cursor",
        "mass":    "mass <old_tile> <new_tile> <radius> — mass transmute",
        "killall": "killall <creature_kind> — kill all creatures of a kind",
        "healall": "healall — heal all NPCs",
        "day":     "day — set to daytime",
        "night":   "night — set to nighttime",
        "info":    "info — show tile/entity info at cursor",
        "clear":   "clear — clear console output",
    }

    # Map tile name strings to tile constants
    TILE_NAMES: Dict[str, int] = {}

    def __init__(self):
        self.active = False
        self.input_text = ""
        self.history: List[str] = []
        self.history_idx = -1
        self.output: List[str] = []
        self._font = None
        self._cursor_wx = 0
        self._cursor_wy = 0

        # Build tile name lookup if not done
        if not GodConsole.TILE_NAMES:
            for name, tile_type in TerrainPainter.PALETTE:
                key = name.lower().replace(" ", "_")
                GodConsole.TILE_NAMES[key] = tile_type
            # Add some aliases
            GodConsole.TILE_NAMES["water"] = WATER
            GodConsole.TILE_NAMES["grass"] = GRASS
            GodConsole.TILE_NAMES["sand"] = SAND
            GodConsole.TILE_NAMES["forest"] = FOREST
            GodConsole.TILE_NAMES["road"] = ROAD
            GodConsole.TILE_NAMES["wall"] = WALL
            GodConsole.TILE_NAMES["floor"] = FLOOR
            GodConsole.TILE_NAMES["door"] = DOOR
            GodConsole.TILE_NAMES["mountain"] = MOUNTAIN
            GodConsole.TILE_NAMES["snow"] = SNOW
            GodConsole.TILE_NAMES["cobblestone"] = COBBLESTONE
            GodConsole.TILE_NAMES["cobble"] = COBBLESTONE
            GodConsole.TILE_NAMES["rubble"] = RUBBLE
            GodConsole.TILE_NAMES["bridge"] = BRIDGE
            GodConsole.TILE_NAMES["swamp"] = SWAMP
            GodConsole.TILE_NAMES["farmland"] = FARMLAND

    def _get_font(self):
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 12)
        return self._font

    def _resolve_tile(self, name_str):
        """Resolve a tile name string to a tile constant."""
        key = name_str.lower().replace(" ", "_")
        if key in self.TILE_NAMES:
            return self.TILE_NAMES[key]
        # Try as integer
        try:
            return int(name_str)
        except ValueError:
            return None

    def set_cursor_pos(self, wx, wy):
        """Update the cursor world position for commands that use it."""
        self._cursor_wx = wx
        self._cursor_wy = wy

    def execute(self, command_text, game):
        """Execute a god console command."""
        parts = command_text.strip().split()
        if not parts:
            return

        self.history.append(command_text)
        self.history_idx = -1

        cmd = parts[0].lower()
        args = parts[1:]

        try:
            if cmd == "help":
                for name, desc in sorted(self.COMMANDS.items()):
                    self.output.append(f"  {desc}")

            elif cmd == "spawn":
                if not args:
                    self.output.append("Usage: spawn <creature_kind> [count]")
                    return
                kind = args[0].lower()
                count = int(args[1]) if len(args) > 1 else 1
                wx, wy = self._cursor_wx, self._cursor_wy
                for i in range(count):
                    offset_x = random.uniform(-3, 3) if count > 1 else 0
                    offset_y = random.uniform(-3, 3) if count > 1 else 0
                    creature = Creature(float(wx) + offset_x, float(wy) + offset_y, kind)
                    creature.home_x = float(wx) + offset_x
                    creature.home_y = float(wy) + offset_y
                    creature.leash_range = 30.0
                    game.world_mgr.creatures.append(creature)
                self.output.append(f"Spawned {count}x {kind} at ({wx},{wy})")

            elif cmd == "npc":
                if not args:
                    self.output.append("Usage: npc <class> [race] [level]")
                    return
                char_class = args[0]
                race = args[1] if len(args) > 1 else "Human"
                level = int(args[2]) if len(args) > 2 else 3
                wx, wy = self._cursor_wx, self._cursor_wy
                name = random.choice(NPC_NAMES) + f"_{random.randint(100, 999)}"
                npc = NPC(float(wx), float(wy), name, char_class,
                          char_class=char_class, race=race, level=level)
                npc.home_x = float(wx)
                npc.home_y = float(wy)
                game.world_mgr.npcs.append(npc)
                self.output.append(f"Spawned {name} ({race} {char_class} Lv{level})")

            elif cmd == "tp":
                if len(args) < 2:
                    self.output.append("Usage: tp <x> <y>")
                    return
                game.player.x = float(args[0])
                game.player.y = float(args[1])
                self.output.append(f"Teleported to ({args[0]}, {args[1]})")

            elif cmd == "gold":
                if not args:
                    self.output.append("Usage: gold <amount>")
                    return
                amount = int(args[0])
                game.player.gold += amount
                self.output.append(f"Added {amount} gold (total: {game.player.gold})")

            elif cmd == "time":
                if not args:
                    self.output.append("Usage: time <speed>")
                    return
                game.time_sys.speed = float(args[0])
                self.output.append(f"Time speed: {args[0]}x")

            elif cmd == "day":
                from game.settings import DAY_LENGTH, DAY_START
                game.time_sys.time = DAY_LENGTH * DAY_START
                self.output.append("Set to daytime")

            elif cmd == "night":
                from game.settings import DAY_LENGTH, NIGHT_START
                game.time_sys.time = DAY_LENGTH * NIGHT_START
                self.output.append("Set to nighttime")

            elif cmd == "kill":
                wx, wy = self._cursor_wx, self._cursor_wy
                killed = False
                # Check creatures
                for creature in list(game.world_mgr.creatures):
                    if abs(creature.x - wx) < 3 and abs(creature.y - wy) < 3:
                        game.world_mgr.creatures.remove(creature)
                        self.output.append(f"Killed {creature.kind} at ({creature.x:.0f},{creature.y:.0f})")
                        killed = True
                        break
                if not killed:
                    # Check NPCs
                    for npc in list(game.world_mgr.npcs):
                        if abs(npc.x - wx) < 3 and abs(npc.y - wy) < 3:
                            npc.hp = 0
                            npc.alive = False
                            game.world_mgr.npcs.remove(npc)
                            self.output.append(f"Killed {npc.name}")
                            killed = True
                            break
                if not killed:
                    self.output.append("No entity found near cursor")

            elif cmd == "heal":
                wx, wy = self._cursor_wx, self._cursor_wy
                healed = False
                for npc in game.world_mgr.npcs:
                    if abs(npc.x - wx) < 3 and abs(npc.y - wy) < 3:
                        npc.hp = npc.max_hp
                        for need in npc.needs:
                            npc.needs[need] = 100.0
                        self.output.append(f"Healed {npc.name}")
                        healed = True
                        break
                if not healed:
                    for creature in game.world_mgr.creatures:
                        if abs(creature.x - wx) < 3 and abs(creature.y - wy) < 3:
                            creature.hp = creature.max_hp
                            self.output.append(f"Healed {creature.kind}")
                            healed = True
                            break
                if not healed:
                    self.output.append("No entity found near cursor")

            elif cmd == "paint":
                if len(args) < 1:
                    self.output.append("Usage: paint <tile_name> [radius]")
                    return
                tile = self._resolve_tile(args[0])
                if tile is None:
                    self.output.append(f"Unknown tile: {args[0]}")
                    return
                radius = int(args[1]) if len(args) > 1 else 3
                wx, wy = self._cursor_wx, self._cursor_wy
                count = 0
                for dy in range(-radius, radius + 1):
                    for dx in range(-radius, radius + 1):
                        if dx * dx + dy * dy <= radius * radius:
                            tx, ty = wx + dx, wy + dy
                            if 0 <= tx < game.world.width and 0 <= ty < game.world.height:
                                game.world.modify_tile(tx, ty, tile)
                                count += 1
                self.output.append(f"Painted {count} tiles as {args[0]}")

            elif cmd == "fill":
                if not args:
                    self.output.append("Usage: fill <tile_name>")
                    return
                tile = self._resolve_tile(args[0])
                if tile is None:
                    self.output.append(f"Unknown tile: {args[0]}")
                    return
                wx, wy = self._cursor_wx, self._cursor_wy
                transmuter = TransmutationTool()
                result = transmuter.fill_area(game.world, wx, wy, tile)
                self.output.append(result)

            elif cmd == "mass":
                if len(args) < 3:
                    self.output.append("Usage: mass <old_tile> <new_tile> <radius>")
                    return
                old_tile = self._resolve_tile(args[0])
                new_tile = self._resolve_tile(args[1])
                radius = int(args[2])
                if old_tile is None or new_tile is None:
                    self.output.append("Unknown tile name")
                    return
                wx, wy = self._cursor_wx, self._cursor_wy
                transmuter = TransmutationTool()
                result = transmuter.mass_transmute(game.world, wx, wy, radius, old_tile, new_tile)
                self.output.append(result)

            elif cmd == "settle":
                if not args:
                    self.output.append("Usage: settle <name> [kind]")
                    return
                name = args[0]
                kind = args[1] if len(args) > 1 else "village"
                wx, wy = self._cursor_wx, self._cursor_wy
                creator = SettlementCreator()
                result = creator.create_settlement(game.world, wx, wy, name, kind)
                self.output.append(result)

            elif cmd == "killall":
                if not args:
                    self.output.append("Usage: killall <creature_kind>")
                    return
                kind = args[0].lower()
                killed_count = 0
                for creature in list(game.world_mgr.creatures):
                    if creature.kind == kind:
                        game.world_mgr.creatures.remove(creature)
                        killed_count += 1
                self.output.append(f"Killed {killed_count} {kind}(s)")

            elif cmd == "healall":
                count = 0
                for npc in game.world_mgr.npcs:
                    npc.hp = npc.max_hp
                    for need in npc.needs:
                        npc.needs[need] = 100.0
                    count += 1
                self.output.append(f"Healed {count} NPCs")

            elif cmd == "info":
                wx, wy = self._cursor_wx, self._cursor_wy
                if 0 <= wx < game.world.width and 0 <= wy < game.world.height:
                    tile = game.world.tiles[wy][wx]
                    tile_name = "?"
                    for name, t in TerrainPainter.PALETTE:
                        if t == tile:
                            tile_name = name
                            break
                    self.output.append(f"Tile ({wx},{wy}): {tile_name} ({tile})")

                    # Show nearby entities
                    for npc in game.world_mgr.npcs:
                        if abs(npc.x - wx) < 3 and abs(npc.y - wy) < 3:
                            self.output.append(
                                f"  NPC: {npc.name} ({npc.race} {npc.char_class} Lv{npc.level}) "
                                f"HP:{npc.hp:.0f}/{npc.max_hp}")
                    for creature in game.world_mgr.creatures:
                        if abs(creature.x - wx) < 3 and abs(creature.y - wy) < 3:
                            self.output.append(
                                f"  Creature: {creature.kind} HP:{creature.hp}/{creature.max_hp}")

            elif cmd == "clear":
                self.output.clear()

            else:
                self.output.append(f"Unknown command: {cmd}. Type 'help' for commands.")

        except Exception as e:
            self.output.append(f"Error: {e}")

        # Trim output history
        if len(self.output) > 100:
            self.output = self.output[-80:]

    def draw(self, screen):
        """Draw the console overlay."""
        if not self.active:
            return

        font = self._get_font()

        # Console background
        console_h = 300
        console_y = SCREEN_HEIGHT - console_h
        bg = pygame.Surface((SCREEN_WIDTH, console_h), pygame.SRCALPHA)
        bg.fill((10, 10, 20, 220))
        screen.blit(bg, (0, console_y))
        pygame.draw.line(screen, UI_BORDER, (0, console_y), (SCREEN_WIDTH, console_y))

        # Output lines (scrolled to bottom)
        line_h = 15
        max_lines = (console_h - 30) // line_h
        visible_output = self.output[-max_lines:]
        cy = console_y + 5
        for line in visible_output:
            color = YELLOW if line.startswith("Error") else GREEN if line.startswith("  ") else UI_TEXT
            label = font.render(line[:120], True, color)
            screen.blit(label, (10, cy))
            cy += line_h

        # Input line
        input_y = SCREEN_HEIGHT - 22
        pygame.draw.line(screen, UI_BORDER, (0, input_y - 3), (SCREEN_WIDTH, input_y - 3))
        prompt = font.render(f"> {self.input_text}_", True, GREEN)
        screen.blit(prompt, (10, input_y))

    def handle_key(self, key, game):
        """Handle console key input."""
        if not self.active:
            if key == pygame.K_BACKQUOTE:  # ~ / ` key
                self.active = True
                return True
            return False

        if key == pygame.K_BACKQUOTE or key == pygame.K_ESCAPE:
            self.active = False
            return True
        elif key == pygame.K_RETURN:
            if self.input_text.strip():
                self.output.append(f"> {self.input_text}")
                self.execute(self.input_text, game)
            self.input_text = ""
            return True
        elif key == pygame.K_BACKSPACE:
            self.input_text = self.input_text[:-1]
            return True
        elif key == pygame.K_UP:
            if self.history:
                if self.history_idx == -1:
                    self.history_idx = len(self.history) - 1
                else:
                    self.history_idx = max(0, self.history_idx - 1)
                self.input_text = self.history[self.history_idx]
            return True
        elif key == pygame.K_DOWN:
            if self.history and self.history_idx >= 0:
                self.history_idx = min(len(self.history) - 1, self.history_idx + 1)
                self.input_text = self.history[self.history_idx]
            return True

        return True  # consume all keys when console is active

    def handle_text_input(self, text):
        """Handle text input events."""
        if self.active:
            self.input_text += text


# ====================================================================
# H. Inspector Tool
# ====================================================================

class InspectorTool:
    """Inspect tiles, NPCs, and creatures at the cursor."""

    def __init__(self):
        self.info_lines: List[str] = []
        self.inspected_npc: Optional[NPC] = None
        self._font = None

    def _get_font(self):
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 11)
        return self._font

    def inspect(self, game, wx, wy):
        """Gather info about the world position."""
        self.info_lines = []
        self.inspected_npc = None

        if not (0 <= wx < game.world.width and 0 <= wy < game.world.height):
            self.info_lines = [f"Out of bounds: ({wx}, {wy})"]
            return

        # Tile info
        tile = game.world.tiles[wy][wx]
        tile_name = "?"
        for name, t in TerrainPainter.PALETTE:
            if t == tile:
                tile_name = name
                break
        walkable = game.world.is_walkable(wx, wy)
        self.info_lines.append(f"Pos: ({wx}, {wy})")
        self.info_lines.append(f"Tile: {tile_name} ({tile}) {'walkable' if walkable else 'blocked'}")

        # Structure
        struct = game.world.get_structure_at(wx, wy)
        if struct:
            self.info_lines.append(f"Structure: {struct.name} ({struct.kind})")

        # NPCs
        for npc in game.world_mgr.npcs:
            if abs(npc.x - wx) < 2 and abs(npc.y - wy) < 2:
                self.inspected_npc = npc
                self.info_lines.append(f"---")
                self.info_lines.append(f"NPC: {npc.name}")
                self.info_lines.append(f"  {npc.race} {npc.char_class} Lv{npc.level}")
                self.info_lines.append(f"  HP: {npc.hp:.0f}/{npc.max_hp} Gold: {npc.npc_gold:.0f}")
                self.info_lines.append(f"  Prof: {npc.profession} Title: {npc.title}")
                self.info_lines.append(f"  State: {npc.state} Action: {npc.current_action}")
                self.info_lines.append(f"  Mood: {npc.mood:.2f} Consciousness: {npc.consciousness}")
                if npc.faction:
                    self.info_lines.append(f"  Faction: {npc.faction}")
                break

        # Creatures
        for creature in game.world_mgr.creatures:
            if abs(creature.x - wx) < 2 and abs(creature.y - wy) < 2:
                self.info_lines.append(f"---")
                self.info_lines.append(f"Creature: {creature.kind}")
                self.info_lines.append(f"  HP: {creature.hp}/{creature.max_hp}")
                self.info_lines.append(f"  DMG: {creature.damage} SPD: {creature.speed}")
                self.info_lines.append(f"  State: {creature.state}")
                self.info_lines.append(f"  AC: {creature.armor_class} XP: {creature.xp_value}")
                break

    def draw_info(self, screen):
        """Draw inspection info panel."""
        if not self.info_lines:
            return

        font = self._get_font()
        panel_w = 300
        line_h = 15
        panel_h = len(self.info_lines) * line_h + 15
        panel_x = SCREEN_WIDTH - panel_w - 10
        panel_y = 50

        bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        bg.fill((20, 20, 35, 220))
        screen.blit(bg, (panel_x, panel_y))
        pygame.draw.rect(screen, UI_BORDER, (panel_x, panel_y, panel_w, panel_h), 1)

        cy = panel_y + 5
        for line in self.info_lines:
            color = YELLOW if line.startswith("NPC:") or line.startswith("Creature:") else UI_TEXT
            if line.startswith("---"):
                pygame.draw.line(screen, GRAY, (panel_x + 5, cy + 6), (panel_x + panel_w - 5, cy + 6))
            else:
                label = font.render(line, True, color)
                screen.blit(label, (panel_x + 5, cy))
            cy += line_h

    def get_status_text(self):
        return "Inspect: Click on tile/entity for details"


# ====================================================================
# I. GodTools - Master Container
# ====================================================================

TOOL_NAMES = ["inspect", "paint", "spawn", "build", "edit", "transmute", "settle"]
TOOL_KEYS = {
    pygame.K_1: "inspect",
    pygame.K_2: "paint",
    pygame.K_3: "spawn",
    pygame.K_4: "build",
    pygame.K_5: "edit",
    pygame.K_6: "transmute",
    pygame.K_7: "settle",
}


class GodTools:
    """Container for all god mode tools."""

    def __init__(self, game):
        self.game = game
        self.painter = TerrainPainter()
        self.spawner = EntitySpawner()
        self.builder = BuildingPlacer()
        self.editor = NPCEditor()
        self.transmuter = TransmutationTool()
        self.settlement_creator = SettlementCreator()
        self.console = GodConsole()
        self.inspector = InspectorTool()

        self.active_tool = "inspect"
        self.status_message = ""
        self.status_timer = 0.0
        self._font = None
        self._painting = False  # True while mouse held down in paint mode

    def _get_font(self):
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 12)
        return self._font

    def _set_status(self, msg):
        """Set a temporary status message."""
        if msg:
            self.status_message = msg
            self.status_timer = 3.0

    def _world_pos_from_mouse(self, mx, my, camera):
        """Convert mouse screen position to world tile coordinates."""
        wx = (mx + int(camera.x)) // TILE_SIZE
        wy = (my + int(camera.y)) // TILE_SIZE
        return wx, wy

    def handle_click(self, mx, my, button, camera):
        """Route click to active tool. Returns True if consumed."""
        wx, wy = self._world_pos_from_mouse(mx, my, camera)

        # Console eats clicks when active
        if self.console.active:
            return True

        # Check if any tool panel consumed the click
        if self.active_tool == "paint":
            if self.painter.handle_palette_click(mx, my):
                return True
        elif self.active_tool == "spawn":
            if self.spawner.handle_spawner_click(mx, my):
                return True
        elif self.active_tool == "build":
            if self.builder.handle_list_click(mx, my):
                return True

        if button == 1:  # Left click
            if self.active_tool == "inspect":
                self.inspector.inspect(self.game, wx, wy)

            elif self.active_tool == "paint":
                self.painter.paint(self.game.world, wx, wy)
                self._painting = True

            elif self.active_tool == "spawn":
                result = self.spawner.spawn(self.game.world_mgr, wx, wy)
                self._set_status(result)

            elif self.active_tool == "build":
                result = self.builder.place(self.game.world, wx, wy)
                self._set_status(result)

            elif self.active_tool == "edit":
                # Find NPC at position
                found = False
                for npc in self.game.world_mgr.npcs:
                    if abs(npc.x - wx) < 2 and abs(npc.y - wy) < 2:
                        self.editor.start_edit(npc)
                        self._set_status(f"Editing {npc.name}")
                        found = True
                        break
                if not found:
                    self._set_status("No NPC found at cursor")

            elif self.active_tool == "transmute":
                if self.transmuter.source_tile is not None:
                    result = self.transmuter.transmute_tile(
                        self.game.world, wx, wy, self.transmuter.source_tile)
                    self._set_status(result)
                else:
                    self._set_status("Right-click to pick a source tile first")

            elif self.active_tool == "settle":
                name = self.settlement_creator.settlement_name
                kind = self.settlement_creator.selected_kind
                result = self.settlement_creator.create_settlement(
                    self.game.world, wx, wy, name, kind)
                self._set_status(result)
                self.console.output.append(result)

            return True

        elif button == 3:  # Right click
            if self.active_tool == "transmute":
                result = self.transmuter.eyedropper(self.game.world, wx, wy)
                self._set_status(result)
                return True

            elif self.active_tool == "inspect":
                self.inspector.inspect(self.game, wx, wy)
                # If NPC found, open editor
                if self.inspector.inspected_npc:
                    self.active_tool = "edit"
                    self.editor.start_edit(self.inspector.inspected_npc)
                    self._set_status(f"Editing {self.inspector.inspected_npc.name}")
                return True

            elif self.active_tool == "paint":
                # Eyedropper - pick tile under cursor
                if 0 <= wx < self.game.world.width and 0 <= wy < self.game.world.height:
                    tile = self.game.world.tiles[wy][wx]
                    self.painter.selected_tile_type = tile
                    # Find the index
                    for i, (name, t) in enumerate(TerrainPainter.PALETTE):
                        if t == tile:
                            self.painter.selected_idx = i
                            self._set_status(f"Picked: {name}")
                            break
                return True

        return False

    def handle_mouse_motion(self, mx, my, camera):
        """Handle mouse drag for continuous painting."""
        if self._painting and self.active_tool == "paint":
            wx, wy = self._world_pos_from_mouse(mx, my, camera)
            self.painter.paint(self.game.world, wx, wy)

    def handle_mouse_up(self, button):
        """Handle mouse button release."""
        if button == 1:
            self._painting = False

    def handle_key(self, key, game):
        """Route key to active tool or tool selection. Returns True if consumed."""
        # Console has highest priority
        if self.console.handle_key(key, game):
            return True

        # Tool selection keys (1-7) — only when editor input not active
        if not self.editor.input_active and not self.settlement_creator.input_active:
            if key in TOOL_KEYS:
                self.active_tool = TOOL_KEYS[key]
                self._set_status(f"Tool: {self.active_tool}")
                return True

        # Route to active tool
        if self.active_tool == "paint":
            self.painter.handle_key(key)
            return True
        elif self.active_tool == "spawn":
            self.spawner.handle_key(key)
            return True
        elif self.active_tool == "build":
            self.builder.handle_key(key)
            return True
        elif self.active_tool == "edit":
            result = self.editor.handle_key(key, game.world_mgr)
            if result:
                self._set_status(result)
                self.console.output.append(result)
            return True
        elif self.active_tool == "settle":
            self.settlement_creator.handle_key(key)
            return True

        return False

    def handle_text_input(self, text):
        """Handle text input events (for typing in fields)."""
        if self.console.active:
            self.console.handle_text_input(text)
            return True

        if self.active_tool == "edit" and self.editor.input_active:
            self.editor.handle_text_input(text)
            return True

        if self.active_tool == "settle" and self.settlement_creator.input_active:
            self.settlement_creator.handle_text_input(text)
            return True

        return False

    def handle_scroll(self, direction):
        """Handle mouse scroll events."""
        if self.active_tool == "paint":
            self.painter.handle_scroll(direction)
        elif self.active_tool == "spawn":
            self.spawner.handle_scroll(direction)
        elif self.active_tool == "build":
            self.builder.handle_scroll(direction)

    def update(self, dt):
        """Update status timer."""
        if self.status_timer > 0:
            self.status_timer -= dt

        # Update console cursor position
        mx, my = pygame.mouse.get_pos()
        wx, wy = self._world_pos_from_mouse(mx, my, self.game.camera)
        self.console.set_cursor_pos(wx, wy)

    def draw(self, screen, camera):
        """Draw active tool's UI and status bar."""
        mx, my = pygame.mouse.get_pos()
        wx, wy = self._world_pos_from_mouse(mx, my, camera)

        # Tool-specific drawing
        if self.active_tool == "paint":
            self.painter.draw_palette(screen)
            # Draw brush cursor
            r = self.painter.brush_size // 2
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    sx = (wx + dx) * TILE_SIZE - int(camera.x)
                    sy = (wy + dy) * TILE_SIZE - int(camera.y)
                    color = TERRAIN_COLORS.get(self.painter.selected_tile_type, (100, 100, 100))
                    surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                    surf.fill((color[0], color[1], color[2], 100))
                    screen.blit(surf, (sx, sy))

        elif self.active_tool == "spawn":
            self.spawner.draw_spawner_ui(screen)
            # Draw spawn indicator
            sx = wx * TILE_SIZE - int(camera.x)
            sy = wy * TILE_SIZE - int(camera.y)
            pygame.draw.rect(screen, GREEN, (sx, sy, TILE_SIZE, TILE_SIZE), 1)

        elif self.active_tool == "build":
            self.builder.draw_blueprint_list(screen)
            self.builder.draw_preview(screen, camera, wx, wy)

        elif self.active_tool == "edit":
            self.editor.draw_editor(screen)

        elif self.active_tool == "inspect":
            self.inspector.draw_info(screen)

        elif self.active_tool == "settle":
            self.settlement_creator.draw_creator_ui(screen)
            # Draw settlement radius preview
            kind = self.settlement_creator.selected_kind
            radius = {"hamlet": 8, "village": 15, "town": 25, "city": 40, "castle": 12}.get(kind, 15)
            cx = wx * TILE_SIZE - int(camera.x) + TILE_SIZE // 2
            cy_s = wy * TILE_SIZE - int(camera.y) + TILE_SIZE // 2
            pygame.draw.circle(screen, (100, 200, 100, 128), (cx, cy_s),
                               radius * TILE_SIZE, 1)

        # Console overlay (always drawn on top if active)
        self.console.draw(screen)

        # Status bar at top
        self._draw_status_bar(screen, wx, wy)

    def _draw_status_bar(self, screen, wx, wy):
        """Draw the god mode status bar at the top of the screen."""
        font = self._get_font()

        bar_h = 22
        bg = pygame.Surface((SCREEN_WIDTH, bar_h), pygame.SRCALPHA)
        bg.fill((15, 15, 25, 200))
        screen.blit(bg, (0, 0))

        # Tool status text
        tool_texts = {
            "inspect": self.inspector.get_status_text(),
            "paint": self.painter.get_status_text(),
            "spawn": self.spawner.get_status_text(),
            "build": self.builder.get_status_text(),
            "edit": self.editor.get_status_text(),
            "transmute": self.transmuter.get_status_text(),
            "settle": self.settlement_creator.get_status_text(),
        }

        # Left: tool selector
        tool_selector = "  ".join(
            f"[{i+1}]{name.upper()}" if name != self.active_tool
            else f"[{i+1}]*{name.upper()}*"
            for i, name in enumerate(TOOL_NAMES)
        )
        sel_label = font.render(tool_selector, True, UI_TEXT)
        screen.blit(sel_label, (5, 3))

        # Right: coordinates and console hint
        coords = font.render(f"({wx},{wy})  [`] Console", True, GRAY)
        screen.blit(coords, (SCREEN_WIDTH - coords.get_width() - 10, 3))

        # Second line: tool-specific status or status message
        if self.status_timer > 0:
            status_text = self.status_message
            status_color = YELLOW
        else:
            status_text = tool_texts.get(self.active_tool, "")
            status_color = LIGHT_GRAY

        status_bg = pygame.Surface((SCREEN_WIDTH, 18), pygame.SRCALPHA)
        status_bg.fill((15, 15, 25, 150))
        screen.blit(status_bg, (0, bar_h))
        status_label = font.render(status_text, True, status_color)
        screen.blit(status_label, (5, bar_h + 1))
