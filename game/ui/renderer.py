"""Rendering system: world, entities, minimap, and visual effects."""

import math
import pygame
import random
from typing import List, Tuple, Optional, Dict
from game.settings import *
from game.world.world import World
from game.world.camera import Camera
from game.core.player import Player
from game.core.npc import NPC
from game.core.creature import Creature
from game.core.items import Item
from game.ui.character_anim import (
    get_anim, update_anim, draw_npc_body, draw_creature_body
)
from game.ui.mount_render import is_mounted, draw_mounted_entity
from game.ui.combat_effects import CombatEffects
from game.ui.object_sprites import (
    draw_battering_ram, draw_catapult, draw_trebuchet, draw_siege_tower,
    draw_handcart, draw_cart, draw_wagon, draw_supply_wagon,
)
from game.ui.water_render import (
    classify_water_tile, build_water_tile_variants, build_wave_frames,
    build_shore_foam_overlays, get_land_neighbor_mask,
)
from game.ui.renderer_tiles import build_tile_cache
from game.ui.sprite_loader import get_sprite_manager

# Pre-computed frozenset for terrain edge blending checks (hot path)
_NATURAL_BLEND_TYPES = frozenset((
    GRASS, SAND, FOREST, DENSE_FOREST, SNOW,
    SWAMP, WATER, MOUNTAIN, FARMLAND,
    ROCKY_GROUND, MARSH,
))


class Renderer:
    """Handles all game rendering."""

    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_sm = pygame.font.SysFont("monospace", 12)
        self.font_md = pygame.font.SysFont("monospace", 16)
        self.font_lg = pygame.font.SysFont("monospace", 22)
        self.font_xl = pygame.font.SysFont("monospace", 32)

        # Tile surface cache
        self._tile_cache = {}
        self._build_tile_cache()

        # Seasonal color system
        self._seasonal_color_cache: Dict[tuple, tuple] = {}  # (terrain_type, season) -> color
        self._seasonal_tile_cache: Dict[tuple, pygame.Surface] = {}  # (terrain_type, season) -> surface
        self._current_season: str = "summer"  # default
        self._last_season: str = "summer"
        self._build_seasonal_color_cache()
        self._build_seasonal_tile_cache("summer")

        # Vegetation and crop system references (set externally)
        self._vegetation_sys = None  # VegetationSystem
        self._crop_system = None     # CropSystem

        # Minimap surface
        self.minimap_surface: Optional[pygame.Surface] = None
        self.minimap_explored: Optional[pygame.Surface] = None

        # Night overlay
        self.night_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)

        # Particle effects
        self.particles: List[dict] = []

        self._dimmed_cache = {}
        self._dim_overlay_cache = {}
        self._consciousness_glow_cache = {}
        self._name_surf_cache = {}
        self._action_surf_cache = {}
        self._wall_grad_cache = {}

        self._action_icons = {
            "sleeping": ("z z z", (150, 150, 200)),
            "talking": ("...", (200, 200, 100)),
            "chopping": ("*chop*", (180, 140, 80)),
            "mining": ("*mine*", (160, 160, 180)),
            "building": ("*build*", (180, 160, 100)),
            "farming": ("*farm*", (100, 180, 80)),
            "fishing": ("*fish*", (100, 150, 200)),
            "foraging": ("*forage*", (120, 180, 100)),
            "fighting": ("!!!", (220, 60, 60)),
            "fleeing": ("!!!", (220, 160, 40)),
            "smithing": ("*smith*", (200, 140, 60)),
            "guarding": ("*guard*", (140, 160, 200)),
            "hunting": ("*hunt*", (160, 200, 100)),
            "carrying": ("*carry*", (180, 160, 80)),
            "commuting": ("*walk*", (140, 140, 140)),
            "trading": ("*trade*", (200, 180, 60)),
            "performing": ("*play*", (180, 120, 180)),
            "researching": ("*study*", (120, 120, 200)),
            "praying": ("*pray*", (180, 180, 140)),
            "training": ("*train*", (200, 140, 100)),
            "healing": ("*heal*", (100, 200, 140)),
            "carrying_food": ("*food*", (200, 180, 80)),
            "carrying_ore": ("*ore*", (160, 140, 120)),
            "carrying_wood": ("*wood*", (140, 100, 50)),
            "carrying_goods": ("*cargo*", (180, 160, 100)),
            "loading": ("*load*", (180, 150, 100)),
            "clearing_rubble": ("*clear*", (130, 120, 110)),
            "road_building": ("*road*", (160, 150, 120)),
            "digging": ("*dig*", (140, 120, 80)),
        }

        # === VISUAL EFFECTS STATE ===
        # Smoke particles from chimneys (blacksmith, bakery, brewery)
        self._smoke_particles: List[dict] = []
        self._smoke_timer: float = 0.0
        self._smoke_sources: List[Tuple[int, int, str]] = []  # (x, y, building_name)
        self._smoke_sources_built = False

        # Ambient birds
        self._birds: List[dict] = []
        self._bird_timer: float = 0.0

        # Floating damage numbers
        self._damage_popups: List[dict] = []

        # Weapon swing arcs
        self._swing_arcs: List[dict] = []

        # Water ripple animation frame counter
        self._ripple_frame: int = 0
        self._ripple_timer: float = 0.0

        # Water depth variant tiles (shallow/normal/deep + animation frames)
        self._water_base_variants = build_water_tile_variants(TILE_SIZE)
        self._water_wave_frames = build_wave_frames(
            self._water_base_variants, TILE_SIZE, num_frames=3)
        self._water_anim_tick: int = 0
        self._shore_foam = build_shore_foam_overlays(TILE_SIZE, num_frames=3)

        # Leaf particles in forests
        self._leaf_particles: List[dict] = []
        self._leaf_timer: float = 0.0

        # Settlement building function cache for colored roofs
        self._building_function_cache: Dict[Tuple[int, int], str] = {}
        self._building_function_built = False

        # Footstep dust tracking
        self._last_player_pos: Optional[Tuple[float, float]] = None
        self._footstep_timer: float = 0.0

        # Screen shake (combat polish)
        self._screen_shake_intensity: float = 0.0
        self._screen_shake_duration: float = 0.0
        self._screen_shake_timer: float = 0.0

        # Enemy health bars — track recently damaged/targeted creatures
        self._hp_bar_targets: Dict[int, float] = {}  # id(entity) -> timer

        # Combat visual effects (damage popups, hit flashes, death, HP bars)
        self.combat_fx = CombatEffects()

        # Spell visual effects
        self._spell_effects: List[dict] = []

        # Weather visual effects
        self._weather_particles: List[dict] = []
        self._weather_condition: str = "clear"
        self._lightning_timer: float = 0.0
        self._lightning_flash: float = 0.0  # remaining flash duration
        self._thunder_shake: float = 0.0    # remaining shake duration
        self._fog_offset: float = 0.0       # wavy fog animation

    def _get_dimmed_tile(self, tile_surf, alpha):
        key = (id(tile_surf), alpha)
        cached = self._dim_overlay_cache.get(key)
        if cached is not None:
            return cached
        dimmed = tile_surf.copy()
        dark = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        dark.fill((0, 0, 0, alpha))
        dimmed.blit(dark, (0, 0))
        self._dim_overlay_cache[key] = dimmed
        return dimmed

    def _get_dim_overlay(self, alpha):
        cached = self._dimmed_cache.get(('_overlay', alpha))
        if cached is not None:
            return cached
        s = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        s.fill((0, 0, 0, alpha))
        self._dimmed_cache[('_overlay', alpha)] = s
        return s

    def _build_tile_cache(self):
        """Pre-render tile surfaces for each terrain type.

        Delegates to renderer_tiles.build_tile_cache() — the actual tile
        generation code lives in renderer_tiles.py to keep this file smaller.
        """
        self._tile_cache = build_tile_cache(TILE_SIZE)

    def _DEAD_CODE_build_tile_cache_original(self):  # noqa: N802
        """DEAD CODE — Original tile cache builder extracted to renderer_tiles.py.
        This method is never called. Left temporarily until the next cleanup pass.
        """
        return  # Dead code removed; original tile cache lives in renderer_tiles.py

    # ================================================================
    # SEASONAL COLOR PALETTE SYSTEM
    # ================================================================

    def _build_seasonal_color_cache(self):
        """Generate seasonal color variants for terrain types.

        Maps (terrain_type, season) -> color tuple for terrain types
        that change visually with the seasons.
        """
        base = TERRAIN_COLORS

        # --- SPRING: bright greens, flowers ---
        self._seasonal_color_cache[(GRASS, "spring")] = (100, 180, 80)
        self._seasonal_color_cache[(FOREST, "spring")] = (60, 140, 55)
        self._seasonal_color_cache[(DENSE_FOREST, "spring")] = (40, 105, 38)
        self._seasonal_color_cache[(FARMLAND, "spring")] = (110, 170, 65)
        self._seasonal_color_cache[(MARSH, "spring")] = (75, 140, 75)
        self._seasonal_color_cache[(WATER, "spring")] = (45, 135, 190)
        self._seasonal_color_cache[(SHALLOW_WATER, "spring")] = (85, 160, 200)

        # --- SUMMER: deep greens, yellowing ---
        self._seasonal_color_cache[(GRASS, "summer")] = (95, 145, 60)
        self._seasonal_color_cache[(FOREST, "summer")] = (45, 110, 40)
        self._seasonal_color_cache[(DENSE_FOREST, "summer")] = (28, 75, 25)
        self._seasonal_color_cache[(FARMLAND, "summer")] = (130, 150, 55)
        self._seasonal_color_cache[(MARSH, "summer")] = (65, 105, 55)

        # --- AUTUMN: orange/red/gold forests, brown grass ---
        self._seasonal_color_cache[(GRASS, "autumn")] = (140, 130, 65)
        self._seasonal_color_cache[(FOREST, "autumn")] = (160, 95, 35)
        self._seasonal_color_cache[(DENSE_FOREST, "autumn")] = (130, 70, 25)
        self._seasonal_color_cache[(FARMLAND, "autumn")] = (150, 130, 55)
        self._seasonal_color_cache[(MARSH, "autumn")] = (95, 100, 50)
        self._seasonal_color_cache[(FRUIT_TREE, "autumn")] = (170, 90, 40)
        self._seasonal_color_cache[(HERB_PATCH, "autumn")] = (100, 110, 50)
        self._seasonal_color_cache[(FLOWER_BED, "autumn")] = (140, 100, 70)

        # --- WINTER: white/gray on grass/forest, frozen water ---
        self._seasonal_color_cache[(GRASS, "winter")] = (170, 175, 160)
        self._seasonal_color_cache[(FOREST, "winter")] = (130, 130, 120)
        self._seasonal_color_cache[(DENSE_FOREST, "winter")] = (100, 100, 90)
        self._seasonal_color_cache[(FARMLAND, "winter")] = (150, 145, 130)
        self._seasonal_color_cache[(MARSH, "winter")] = (120, 130, 120)
        self._seasonal_color_cache[(WATER, "winter")] = (100, 160, 210)
        self._seasonal_color_cache[(SHALLOW_WATER, "winter")] = (140, 180, 215)
        self._seasonal_color_cache[(FRUIT_TREE, "winter")] = (110, 105, 95)
        self._seasonal_color_cache[(HERB_PATCH, "winter")] = (130, 135, 120)

        # --- Crop tiles (WHEAT_FIELD, VEGETABLE_PLOT) seasonal variants ---
        self._seasonal_color_cache[(WHEAT_FIELD, "spring")] = (150, 165, 60)
        self._seasonal_color_cache[(WHEAT_FIELD, "summer")] = (190, 175, 65)
        self._seasonal_color_cache[(WHEAT_FIELD, "autumn")] = (200, 180, 70)
        self._seasonal_color_cache[(WHEAT_FIELD, "winter")] = (140, 135, 110)
        self._seasonal_color_cache[(VEGETABLE_PLOT, "spring")] = (75, 170, 60)
        self._seasonal_color_cache[(VEGETABLE_PLOT, "summer")] = (70, 155, 55)
        self._seasonal_color_cache[(VEGETABLE_PLOT, "autumn")] = (100, 130, 50)
        self._seasonal_color_cache[(VEGETABLE_PLOT, "winter")] = (130, 130, 110)
        self._seasonal_color_cache[(TILLED_SOIL, "spring")] = (105, 90, 55)
        self._seasonal_color_cache[(TILLED_SOIL, "summer")] = (100, 85, 50)
        self._seasonal_color_cache[(TILLED_SOIL, "autumn")] = (110, 95, 60)
        self._seasonal_color_cache[(TILLED_SOIL, "winter")] = (130, 120, 100)
        self._seasonal_color_cache[(FLOWER_BED, "winter")] = (160, 155, 145)

    def _build_seasonal_tile_cache(self, season: str):
        """Build pre-rendered tile surfaces for a given season.

        Only generates tiles for terrain types that have seasonal color
        variants. Other terrain types fall through to the default cache.
        """
        # Clear old seasonal cache
        self._seasonal_tile_cache = {}

        affected_types = set()
        for (tt, s) in self._seasonal_color_cache:
            if s == season:
                affected_types.add(tt)

        for terrain_type in affected_types:
            key = (terrain_type, season)
            color = self._seasonal_color_cache.get(key)
            if not color:
                continue

            surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
            r, g, b = color
            surf.fill(color)

            # Replicate terrain texture detail with seasonal colors
            if terrain_type == GRASS:
                # Grass blades
                for i in range(4):
                    x = (hash((i * 7 + terrain_type)) % (TILE_SIZE - 2)) + 1
                    y = (hash((i * 13 + terrain_type)) % (TILE_SIZE - 2)) + 1
                    blade_color = (max(0, r - 15), min(255, g + 10), max(0, b - 10))
                    pygame.draw.line(surf, blade_color, (x, y), (x, y + 2))
                # Spring: add flower dots
                if season == "spring":
                    flower_colors = [(220, 100, 120), (240, 220, 80), (180, 100, 220), (100, 180, 230)]
                    for i in range(2):
                        fx = (hash(i * 31 + 5) % (TILE_SIZE - 2)) + 1
                        fy = (hash(i * 37 + 9) % (TILE_SIZE - 2)) + 1
                        fc = flower_colors[hash(i * 41) % len(flower_colors)]
                        surf.set_at((fx, fy), fc)
                # Winter: add white snow speckles
                elif season == "winter":
                    for i in range(5):
                        sx = hash(i * 19 + 3) % TILE_SIZE
                        sy = hash(i * 23 + 7) % TILE_SIZE
                        pygame.draw.circle(surf, (240, 242, 248), (sx, sy), 1)

            elif terrain_type == FOREST:
                # Ground cover
                for i in range(6):
                    gx = (hash(i * 11 + 1) % (TILE_SIZE - 2)) + 1
                    gy = (hash(i * 17 + 3) % (TILE_SIZE - 2)) + 1
                    pygame.draw.circle(surf, (max(0, r - 8), min(255, g + 5), max(0, b - 3)),
                                       (gx, gy), 1)
                cx, cy = TILE_SIZE // 2, TILE_SIZE // 2
                if season == "winter":
                    # Bare tree: visible trunk, minimal canopy
                    pygame.draw.rect(surf, (75, 50, 30), (cx - 2, cy - 2, 4, 10))
                    # Sparse branches
                    pygame.draw.line(surf, (85, 60, 35), (cx, cy - 1), (cx - 4, cy - 4))
                    pygame.draw.line(surf, (85, 60, 35), (cx, cy), (cx + 4, cy - 3))
                    # Snow on branches
                    pygame.draw.circle(surf, (230, 235, 242), (cx - 3, cy - 4), 1)
                    pygame.draw.circle(surf, (230, 235, 242), (cx + 3, cy - 3), 1)
                else:
                    # Normal tree with seasonal canopy color
                    pygame.draw.rect(surf, (75, 50, 30), (cx - 2, cy + 2, 4, 7))
                    pygame.draw.circle(surf, (max(0, r - 15), g, max(0, b - 8)), (cx, cy - 2), 7)
                    pygame.draw.circle(surf, (max(0, r - 5), min(255, g + 15), max(0, b - 3)),
                                       (cx - 1, cy - 3), 6)
                    if season == "autumn":
                        # Add scattered orange/red dots on canopy
                        for i in range(3):
                            dx = (hash(i * 7 + 99) % 10) - 5 + cx
                            dy = (hash(i * 11 + 77) % 8) - 5 + cy
                            dot_c = [(200, 80, 30), (220, 160, 40), (180, 50, 30)][i % 3]
                            if 0 <= dx < TILE_SIZE and 0 <= dy < TILE_SIZE:
                                surf.set_at((dx, dy), dot_c)

            elif terrain_type == DENSE_FOREST:
                trees = [(5, 5, 5), (11, 4, 6), (8, 12, 5), (14, 11, 4)]
                if season == "winter":
                    # Bare trees with snow
                    for ox, oy, tr in trees:
                        if ox < TILE_SIZE and oy < TILE_SIZE:
                            pygame.draw.rect(surf, (55, 35, 22), (ox, oy, 2, 6))
                            pygame.draw.line(surf, (65, 45, 30), (ox, oy), (ox - 3, oy - 3))
                            pygame.draw.line(surf, (65, 45, 30), (ox + 1, oy + 1), (ox + 4, oy - 2))
                    for i in range(6):
                        sx_s = hash(i * 17 + 5) % TILE_SIZE
                        sy_s = hash(i * 23 + 9) % TILE_SIZE
                        pygame.draw.circle(surf, (235, 238, 245), (sx_s, sy_s), 1)
                else:
                    for ox, oy, tr in trees:
                        if ox < TILE_SIZE and oy < TILE_SIZE:
                            pygame.draw.rect(surf, (55, 35, 22), (ox, oy + tr, 2, 4))
                            pygame.draw.circle(surf, (max(0, r - 8), min(255, g + 8), max(0, b - 5)),
                                               (ox, oy), tr)

            elif terrain_type in (WATER, SHALLOW_WATER):
                # Frozen/shifted water
                surf.fill(color)
                if season == "winter":
                    # Ice cracks
                    for i in range(3):
                        ix = (hash(i * 13 + 1) % (TILE_SIZE - 4)) + 2
                        iy = (hash(i * 17 + 3) % (TILE_SIZE - 4)) + 2
                        pygame.draw.line(surf, (min(255, r + 20), min(255, g + 15), min(255, b + 10)),
                                         (ix, iy), (ix + 3, iy + 2))
                else:
                    # Wave pattern with seasonal tint
                    for i in range(3):
                        y_pos = 5 + i * 5
                        wave_color = (min(255, r + 25), min(255, g + 25), min(255, b + 25))
                        for px in range(TILE_SIZE):
                            offset = (px * 3 + i * 7) % 4
                            if offset < 2:
                                surf.set_at((px, y_pos), wave_color)

            elif terrain_type == FARMLAND:
                for i in range(2, TILE_SIZE - 2, 4):
                    pygame.draw.line(surf, (max(0, r - 15), max(0, g - 15), max(0, b - 10)),
                                     (i, 2), (i, TILE_SIZE - 2))
                if season == "winter":
                    for i in range(4):
                        sx_s = hash(i * 19 + 7) % TILE_SIZE
                        sy_s = hash(i * 23 + 11) % TILE_SIZE
                        surf.set_at((sx_s, sy_s), (230, 233, 238))

            elif terrain_type == MARSH:
                for i in range(4):
                    wx = (hash(i * 9 + 1) % (TILE_SIZE - 4)) + 2
                    wy = (hash(i * 15 + 3) % (TILE_SIZE - 4)) + 2
                    if season == "winter":
                        pygame.draw.circle(surf, (140, 155, 170), (wx, wy), 3)
                    else:
                        pygame.draw.circle(surf, (max(0, r - 10), max(0, g - 8), max(0, b + 10)),
                                           (wx, wy), 3)

            elif terrain_type == FRUIT_TREE:
                cx, cy = TILE_SIZE // 2, TILE_SIZE // 2
                if season == "winter":
                    pygame.draw.rect(surf, (80, 50, 30), (cx - 1, cy + TILE_SIZE // 6, 2, TILE_SIZE // 4))
                    pygame.draw.line(surf, (85, 60, 35), (cx, cy - 1), (cx - 3, cy - 4))
                    pygame.draw.line(surf, (85, 60, 35), (cx, cy), (cx + 3, cy - 3))
                elif season == "autumn":
                    pygame.draw.circle(surf, (160, 85, 35), (cx, cy - 2), TILE_SIZE // 3)
                    pygame.draw.rect(surf, (80, 50, 30), (cx - 1, cy + TILE_SIZE // 6, 2, TILE_SIZE // 4))
                    pygame.draw.circle(surf, (200, 50, 40), (cx - 2, cy - 3), max(1, TILE_SIZE // 10))
                    pygame.draw.circle(surf, (200, 50, 40), (cx + 3, cy - 1), max(1, TILE_SIZE // 10))
                else:
                    pygame.draw.circle(surf, (min(255, r + 10), min(255, g + 20), min(255, b + 10)),
                                       (cx, cy - 2), TILE_SIZE // 3)
                    pygame.draw.rect(surf, (80, 50, 30), (cx - 1, cy + TILE_SIZE // 6, 2, TILE_SIZE // 4))

            elif terrain_type == HERB_PATCH:
                for i in range(4):
                    px_h = (hash(i * 11) % (TILE_SIZE - 2)) + 1
                    py_h = TILE_SIZE // 2 + (hash(i * 17) % (TILE_SIZE // 2))
                    pygame.draw.line(surf, (max(0, r - 20), min(255, g + 10), max(0, b - 10)),
                                     (px_h, py_h), (px_h, py_h - TILE_SIZE // 4))

            elif terrain_type == FLOWER_BED:
                if season == "winter":
                    # Dead flowers, brown
                    for i in range(4):
                        fx = (hash(i * 7) % (TILE_SIZE - 4)) + 2
                        fy = (hash(i * 13) % (TILE_SIZE - 4)) + 2
                        pygame.draw.circle(surf, (130, 115, 95), (fx, fy), max(1, TILE_SIZE // 8))
                elif season == "autumn":
                    colors = [(180, 100, 50), (160, 80, 40), (140, 90, 60), (170, 120, 50)]
                    for i, fc in enumerate(colors):
                        fx = (hash(i * 7) % (TILE_SIZE - 4)) + 2
                        fy = (hash(i * 13) % (TILE_SIZE - 4)) + 2
                        pygame.draw.circle(surf, fc, (fx, fy), max(1, TILE_SIZE // 8))
                else:
                    # Spring: extra vibrant flowers
                    colors = [(230, 80, 100), (240, 230, 80), (170, 80, 220), (80, 170, 230)]
                    for i, fc in enumerate(colors):
                        fx = (hash(i * 7) % (TILE_SIZE - 4)) + 2
                        fy = (hash(i * 13) % (TILE_SIZE - 4)) + 2
                        pygame.draw.circle(surf, fc, (fx, fy), max(1, TILE_SIZE // 8))

            self._seasonal_tile_cache[(terrain_type, season)] = surf

    def set_season(self, season: str):
        """Update the current season and rebuild tile caches if needed."""
        if season == self._current_season:
            return
        self._last_season = self._current_season
        self._current_season = season
        self._build_seasonal_tile_cache(season)
        # Clear the dimmed cache so it picks up new seasonal tiles
        if hasattr(self, '_dimmed_cache'):
            self._dimmed_cache = {}

    def set_vegetation_systems(self, vegetation_sys, crop_system):
        """Bind vegetation and crop systems for color overrides."""
        self._vegetation_sys = vegetation_sys
        self._crop_system = crop_system

    def _get_vegetation_color(self, x: int, y: int):
        """Return a color override tuple from vegetation or crop systems.

        Crop system overrides take priority, then vegetation overrides.
        Returns None if no override exists.
        """
        if self._crop_system is not None:
            c = self._crop_system.color_overrides.get((x, y))
            if c is not None:
                return c
        if self._vegetation_sys is not None:
            c = self._vegetation_sys.color_overrides.get((x, y))
            if c is not None:
                return c
        return None

    def _get_veg_tint(self, color: tuple) -> pygame.Surface:
        """Return a cached SRCALPHA tint surface for vegetation overlays.

        Avoids creating a new Surface every frame for every visible tile.
        """
        if not hasattr(self, '_veg_tint_cache'):
            self._veg_tint_cache: dict = {}
        cached = self._veg_tint_cache.get(color)
        if cached is not None:
            return cached
        tint = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        tint.fill((*color, 120))
        self._veg_tint_cache[color] = tint
        return tint

    def _get_seasonal_tile(self, terrain_type: int) -> Optional[pygame.Surface]:
        """Get the seasonal variant of a tile, or None to use default."""
        key = (terrain_type, self._current_season)
        return self._seasonal_tile_cache.get(key)

    def _build_transition_cache(self, world: World):
        """Pre-render terrain transition tiles for smooth biome boundaries.
        Uses checkerboard dithering at borders between different biome types."""
        self._transition_tiles = {}  # (tile_a, tile_b) -> surface

        # Natural terrain pairs that need transitions
        transition_pairs = set()
        natural = {GRASS, FOREST, DENSE_FOREST, SAND, MOUNTAIN, SNOW, SWAMP,
                    WATER, FARMLAND, ROCKY_GROUND, MARSH}

        # Sample world edges to find which transitions exist
        step = 8
        for y in range(0, world.height - 1, step):
            for x in range(0, world.width - 1, step):
                t = world.tiles[y][x]
                if t not in natural:
                    continue
                for dx, dy in [(1, 0), (0, 1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < world.width and 0 <= ny < world.height:
                        tn = world.tiles[ny][nx]
                        if tn in natural and tn != t:
                            key = (min(t, tn), max(t, tn))
                            transition_pairs.add(key)

        # Build dithered transition tiles for each pair
        for t_a, t_b in transition_pairs:
            color_a = TERRAIN_COLORS.get(t_a, (80, 80, 80))
            color_b = TERRAIN_COLORS.get(t_b, (80, 80, 80))

            # Create 4 transition variants (for each edge direction)
            for direction in ("right", "down"):
                surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
                for py in range(TILE_SIZE):
                    for px in range(TILE_SIZE):
                        # Gradient with noise-based dithering
                        if direction == "right":
                            t = px / TILE_SIZE
                        else:
                            t = py / TILE_SIZE
                        # Add noise for natural look
                        noise = ((px * 7 + py * 13) % 5) / 10.0 - 0.25
                        t = max(0, min(1, t + noise))
                        r = int(color_a[0] * (1 - t) + color_b[0] * t)
                        g = int(color_a[1] * (1 - t) + color_b[1] * t)
                        b = int(color_a[2] * (1 - t) + color_b[2] * t)
                        surf.set_at((px, py), (r, g, b))
                self._transition_tiles[(t_a, t_b, direction)] = surf
                # Reverse direction
                self._transition_tiles[(t_b, t_a, "left" if direction == "right" else "up")] = surf

    def _build_roof_cache(self):
        """Build colored roof tiles for different structure types."""
        self._roof_cache = {}
        roof_styles = {
            "village":  (120, 90, 60),   # brown thatch
            "hamlet":   (110, 95, 55),   # straw thatch
            "town":     (140, 100, 70),  # tile roof
            "city":     (100, 100, 115), # slate roof
            "castle":   (85, 85, 95),    # stone roof
            "temple":   (230, 220, 180), # white/gold
            "tavern":   (150, 95, 55),   # warm brown
            "blacksmith": (70, 70, 75),  # dark gray
            "market":   (170, 110, 60),  # vibrant warm
            "house":    (130, 100, 65),  # earth tones
            "default":  (90, 80, 70),    # fallback gray
        }
        for kind, base in roof_styles.items():
            surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
            r, g, b = base
            surf.fill(base)
            # Horizontal line pattern (roof tiles/thatch)
            for i in range(0, TILE_SIZE, 4):
                shade = r - 12 + (i % 8)
                pygame.draw.line(surf, (max(0, shade), max(0, g - 10), max(0, b - 8)),
                                (0, i), (TILE_SIZE, i))
            # Ridge line down the middle
            pygame.draw.line(surf, (max(0, r - 25), max(0, g - 25), max(0, b - 20)),
                            (TILE_SIZE // 2, 0), (TILE_SIZE // 2, TILE_SIZE))
            self._roof_cache[kind] = surf

            # Also make dimmed version
            dimmed = surf.copy()
            dark = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            dark.fill((0, 0, 0, 140))
            dimmed.blit(dark, (0, 0))
            self._roof_cache[kind + "_dim"] = dimmed

    def _get_roof_for_tile(self, x: int, y: int, world) -> pygame.Surface:
        """Get the appropriate roof surface for a building tile based on its structure."""
        if not hasattr(self, '_roof_cache') or not self._roof_cache:
            self._build_roof_cache()

        # Find which structure this tile belongs to
        if not hasattr(self, '_tile_structure_map'):
            self._tile_structure_map = {}
            for s in world.structures:
                for bx, by, bw, bh in getattr(s, 'buildings', []):
                    for ty in range(by, by + bh):
                        for tx in range(bx, bx + bw):
                            self._tile_structure_map[(tx, ty)] = s.kind
            # Also check plan settlements (chunked worlds)
            if hasattr(world, 'plan'):
                for sp in world.plan.settlements:
                    for bld in sp.buildings:
                        bx, by = bld['x'], bld['y']
                        bw, bh = bld['w'], bld['h']
                        for ty in range(by, by + bh):
                            for tx in range(bx, bx + bw):
                                if (tx, ty) not in self._tile_structure_map:
                                    self._tile_structure_map[(tx, ty)] = sp.kind

        kind = self._tile_structure_map.get((x, y), "default")
        # Check building function cache for more specific roof colors
        bfunc = self._building_function_cache.get((x, y), "")
        if bfunc:
            func_lower = bfunc.lower()
            if "tavern" in func_lower or "inn" in func_lower:
                kind = "tavern"
            elif "temple" in func_lower or "shrine" in func_lower or "church" in func_lower:
                kind = "temple"
            elif "blacksmith" in func_lower or "forge" in func_lower or "smith" in func_lower:
                kind = "blacksmith"
            elif "market" in func_lower or "shop" in func_lower or "store" in func_lower:
                kind = "market"
            elif "house" in func_lower or "cottage" in func_lower or "hovel" in func_lower:
                kind = "house"
        return self._roof_cache.get(kind, self._roof_cache.get("default"))

    def _get_roof_dimmed(self, x: int, y: int, world) -> pygame.Surface:
        """Get dimmed roof for explored-but-not-visible tiles."""
        if not hasattr(self, '_roof_cache') or not self._roof_cache:
            self._build_roof_cache()
        if not hasattr(self, '_tile_structure_map'):
            self._get_roof_for_tile(x, y, world)  # build map
        kind = self._tile_structure_map.get((x, y), "default")
        return self._roof_cache.get(kind + "_dim", self._roof_cache.get("default_dim"))

    def build_minimap(self, world: World):
        """Build minimap surface from world data.

        For chunked worlds (>4000 tiles), uses the elevation cache
        to generate a low-res minimap without loading every chunk.
        """
        from game.world.world import ChunkedWorld

        if isinstance(world, ChunkedWorld) and world.width > 4000:
            self._build_minimap_from_plan(world)
            return

        scale = 1
        w = world.width * scale
        h = world.height * scale
        self.minimap_surface = pygame.Surface((w, h))
        self.minimap_explored = pygame.Surface((w, h), pygame.SRCALPHA)
        self.minimap_explored.fill((0, 0, 0, 200))

        for y in range(world.height):
            for x in range(world.width):
                color = TERRAIN_COLORS.get(world.tiles[y][x], (100, 100, 100))
                self.minimap_surface.set_at((x * scale, y * scale), color)

    def _build_minimap_from_plan(self, world):
        """Build minimap from elevation cache (fast, no chunk loading)."""
        plan = world.plan
        # Downsample: 1 pixel per 10 tiles
        step = plan._elev_step
        mw = plan._elev_cw
        mh = plan._elev_ch
        self.minimap_surface = pygame.Surface((mw, mh))
        self.minimap_explored = pygame.Surface((mw, mh), pygame.SRCALPHA)
        self.minimap_explored.fill((0, 0, 0, 200))

        # Color from elevation
        import numpy as np
        elev = plan._elev_cache
        for cy in range(mh):
            for cx in range(mw):
                e = elev[cy, cx]
                if e < 0.22:
                    color = TERRAIN_COLORS[WATER]
                elif e < 0.28:
                    color = TERRAIN_COLORS[SAND]
                elif e < 0.65:
                    color = TERRAIN_COLORS[GRASS]
                elif e < 0.78:
                    color = TERRAIN_COLORS[MOUNTAIN]
                else:
                    color = TERRAIN_COLORS[SNOW]
                self.minimap_surface.set_at((cx, cy), color)

        # Mark settlements
        for s in plan.settlements:
            mx = s.x // step
            my = s.y // step
            if 0 <= mx < mw and 0 <= my < mh:
                size = max(1, s.radius // step)
                color = (200, 180, 100) if s.kind == "city" else (180, 160, 90)
                for dy in range(-size, size + 1):
                    for dx in range(-size, size + 1):
                        px, py = mx + dx, my + dy
                        if 0 <= px < mw and 0 <= py < mh:
                            self.minimap_surface.set_at((px, py), color)

        # Mark roads
        for road in plan.roads:
            for wx, wy in road.waypoints:
                mx = wx // step
                my = wy // step
                if 0 <= mx < mw and 0 <= my < mh:
                    self.minimap_surface.set_at((mx, my),
                                                TERRAIN_COLORS[ROAD])

        # Store scale factor for coordinate mapping
        self._minimap_step = step

    def update_minimap_explored(self, world: World):
        """Update explored areas on minimap."""
        if self.minimap_explored is None:
            return
        from game.world.world import ChunkedWorld
        if isinstance(world, ChunkedWorld) and world.width > 4000:
            # For chunked worlds, reveal in batches from explored set
            step = getattr(self, '_minimap_step', 10)
            mw = self.minimap_explored.get_width()
            mh = self.minimap_explored.get_height()
            for (ex, ey) in world._explored_set:
                mx = ex // step
                my = ey // step
                if 0 <= mx < mw and 0 <= my < mh:
                    self.minimap_explored.set_at((mx, my), (0, 0, 0, 0))
            return

        for y in range(world.height):
            for x in range(world.width):
                if world.explored[y][x]:
                    self.minimap_explored.set_at((x, y), (0, 0, 0, 0))

    def draw_world(self, world: World, camera: Camera, visible_tiles=None,
                   player=None):
        """Draw terrain tiles with FOV, roofs on unvisited buildings, 2.5D."""
        # Advance water animation tick
        self._water_anim_tick += 1

        # Build building function cache on first draw (for colored roofs, smoke, etc.)
        if not self._building_function_built:
            self._build_building_function_cache(world)

        x0, y0, x1, y1 = camera.get_visible_tile_range()

        # Floor level
        player_floor = getattr(player, 'current_floor', 0) if player else 0
        floor_tiles = None
        if player_floor != 0 and player:
            floor_tiles = self._get_floor_overlay(player, world)
        dim_exterior = player_floor != 0

        underground_explored = set()
        if player_floor < 0 and player:
            underground_explored = getattr(player, '_underground_explored', set())

        # Determine which building the player is inside (for roof logic)
        player_building_rect = getattr(player, '_current_building_rect', None) if player else None

        # Build roof cache on first use
        if not hasattr(self, '_roof_cache') or not self._roof_cache:
            self._build_roof_cache()

        building_tiles = getattr(world, '_building_interior_tiles', set())
        interior_tiles = (FLOOR, TABLE, BED, CHEST, STAIRS_UP, STAIRS_DOWN,
                          FIREPLACE, PILLAR, ALTAR, THRONE, BOOKSHELF, BARREL,
                          ANVIL, FORGE_FIRE, FOUNTAIN, CARPET, MOSAIC, ARCHWAY)

        # Height offset — when player is on an upper/lower floor, the
        # building's current floor is drawn offset vertically to show
        # the player is physically higher/lower.
        floor_y_offset = 0  # pixels to shift building interior tiles
        pixels_per_floor = TILE_SIZE // 2  # 8px per floor at 16px tiles
        if player_floor != 0 and player_building_rect:
            floor_y_offset = -player_floor * pixels_per_floor  # negative = up

        # --- BATCH PRE-PASS for common terrain tiles ---
        # When conditions are simple (ground floor, no building rect, no
        # dim_exterior), batch-blit GRASS/FOREST/SAND/FARMLAND tiles via
        # pygame blits() to reduce per-tile Python call overhead.
        _batch_types = frozenset((GRASS, FOREST, SAND, FARMLAND))
        _batch_blit_list = []  # list of (surface, (sx, sy))
        _batched_coords = set()  # (x, y) tiles handled by batch pass

        can_batch = (player_floor == 0 and not dim_exterior
                     and not player_building_rect)
        if can_batch:
            cam_x_int = int(camera.x)
            cam_y_int = int(camera.y)
            for by in range(y0, y1):
                for bx in range(x0, x1):
                    # Only batch tiles that are in FOV (or FOV is disabled)
                    if visible_tiles is not None and (bx, by) not in visible_tiles:
                        continue
                    # Skip tiles inside buildings (need roof logic)
                    if (bx, by) in building_tiles:
                        continue
                    tile_type = world.tiles[by][bx]
                    if tile_type not in _batch_types:
                        continue
                    # Use seasonal tile, or position-based variant, or base cache
                    tile_surf = self._get_seasonal_tile(tile_type)
                    if tile_surf is None:
                        _smgr = get_sprite_manager()
                        tile_surf = _smgr.get_variant_for_position(tile_type, bx, by)
                    if tile_surf is None:
                        tile_surf = self._tile_cache.get(tile_type)
                    if tile_surf:
                        bsx = bx * TILE_SIZE - cam_x_int
                        bsy = by * TILE_SIZE - cam_y_int
                        _batch_blit_list.append((tile_surf, (bsx, bsy)))
                        _batched_coords.add((bx, by))

            if _batch_blit_list:
                self.screen.blits(_batch_blit_list, doreturn=False)

        for y in range(y0, y1):
            for x in range(x0, x1):
                # Skip tiles already handled by batch pre-pass
                if (x, y) in _batched_coords:
                    # Still need terrain blending and vegetation overlays
                    tile_type = world.tiles[y][x]
                    sx = x * TILE_SIZE - int(camera.x)
                    sy = y * TILE_SIZE - int(camera.y)
                    # Vegetation/crop color override tint (cached)
                    override_color = self._get_vegetation_color(x, y)
                    if override_color:
                        tint = self._get_veg_tint(override_color)
                        self.screen.blit(tint, (sx, sy))
                    # Terrain edge blending
                    if tile_type in (GRASS, SAND, FOREST, DENSE_FOREST, SNOW,
                                     SWAMP, WATER, MOUNTAIN, FARMLAND,
                                     ROCKY_GROUND, MARSH):
                        try:
                            self._blend_terrain_edge(world, x, y, sx, sy, tile_type)
                        except Exception:
                            pass
                    continue

                sx = x * TILE_SIZE - int(camera.x)
                sy = y * TILE_SIZE - int(camera.y)

                in_fov = visible_tiles is None or (x, y) in visible_tiles
                explored = world.explored[y][x] if 0 <= y < world.height and 0 <= x < world.width else False

                # Is this tile inside the player's current building?
                in_player_building = False
                if player_building_rect:
                    pbx, pby, pbw, pbh = player_building_rect
                    if pbx <= x < pbx + pbw and pby <= y < pby + pbh:
                        in_player_building = True

                if in_fov:
                    # Underground: show explored underground tiles, black elsewhere.
                    # Tiles can be inside a building basement OR in tunnels/caves
                    # that extend beyond building footprints.
                    if player_floor < 0:
                        has_underground = floor_tiles and (x, y) in floor_tiles
                        is_explored = (x, y) in underground_explored

                        if has_underground and is_explored:
                            # Show the underground tile
                            tile_type = floor_tiles[(x, y)]
                            tile_surf = self._tile_cache.get(tile_type)
                            if tile_surf:
                                self.screen.blit(tile_surf, (sx, sy))
                        else:
                            # No underground tile here or not explored = black
                            pygame.draw.rect(self.screen, (0, 0, 0),
                                             (sx, sy, TILE_SIZE, TILE_SIZE))
                        continue  # skip all other rendering for underground

                    # Determine tile type — use floor overlay if on non-ground floor
                    if floor_tiles and (x, y) in floor_tiles and in_player_building:
                        tile_type = floor_tiles[(x, y)]
                    else:
                        tile_type = world.tiles[y][x]

                    # --- ROOF LOGIC ---
                    if (not in_player_building and
                            tile_type in interior_tiles and
                            (x, y) in building_tiles):
                        roof = self._get_roof_for_tile(x, y, world)
                        if roof:
                            self.screen.blit(roof, (sx, sy))
                            continue

                    # --- ELEVATED FLOOR RENDERING ---
                    if in_player_building and player_floor != 0:
                        # First draw the ground floor tile (dimmed) at normal position
                        ground_tile = world.tiles[y][x]
                        gt_surf = self._tile_cache.get(ground_tile)
                        if gt_surf:
                            dimmed_gt = self._get_dimmed_tile(gt_surf, 120)
                            self.screen.blit(dimmed_gt, (sx, sy))

                        # Draw the current floor's tile at the elevated position
                        if floor_tiles and (x, y) in floor_tiles:
                            ft = floor_tiles[(x, y)]
                            ft_surf = self._tile_cache.get(ft)
                            if ft_surf:
                                self.screen.blit(ft_surf, (sx, sy + floor_y_offset))

                            # Draw connecting wall between ground and elevated floor
                            # (only on the south edge of the building)
                            if y == pby + pbh - 1 and floor_y_offset < 0:
                                wall_h = abs(floor_y_offset)
                                wall_surf = pygame.Surface((TILE_SIZE, wall_h), pygame.SRCALPHA)
                                wall_surf.fill((100, 90, 75))
                                # Slight gradient
                                for py_w in range(wall_h):
                                    shade = int(220 - py_w * 60 / max(1, wall_h))
                                    pygame.draw.line(wall_surf, (shade - 120, shade - 130, shade - 140),
                                                     (0, py_w), (TILE_SIZE - 1, py_w))
                                self.screen.blit(wall_surf,
                                                 (sx, sy + floor_y_offset + TILE_SIZE))
                        continue

                    # --- NORMAL TILE (with seasonal variant) ---
                    _is_water = False
                    try:
                        if tile_type == WATER:
                            _is_water = True
                            wclass = classify_water_tile(
                                world.tiles, x, y, world.width, world.height)
                            frame_idx = (self._water_anim_tick // 30 + x + y) % 3
                            tile_surf = self._water_wave_frames.get(
                                (wclass, frame_idx))
                            if not tile_surf:
                                tile_surf = self._water_base_variants.get(wclass)
                        else:
                            tile_surf = self._get_seasonal_tile(tile_type)
                            if tile_surf is None:
                                _smgr = get_sprite_manager()
                                tile_surf = _smgr.get_variant_for_position(
                                    tile_type, x, y)
                            if tile_surf is None:
                                tile_surf = self._tile_cache.get(tile_type)
                    except Exception:
                        tile_surf = None
                    if tile_surf:
                        self.screen.blit(tile_surf, (sx, sy))
                    else:
                        # Fallback for tile types without a cached surface
                        fallback_color = TERRAIN_COLORS.get(tile_type, (80, 80, 80))
                        pygame.draw.rect(self.screen, fallback_color,
                                         (sx, sy, TILE_SIZE, TILE_SIZE))

                    # Shore foam overlay for water tiles
                    if _is_water:
                        land_mask = get_land_neighbor_mask(
                            world.tiles, x, y, world.width, world.height)
                        if land_mask:
                            for bit in range(4):
                                if land_mask & (1 << bit):
                                    foam = self._shore_foam.get(
                                        (bit, frame_idx))
                                    if foam:
                                        self.screen.blit(foam, (sx, sy))

                    # Vegetation/crop color override tint (cached)
                    override_color = self._get_vegetation_color(x, y)
                    if override_color:
                        tint = self._get_veg_tint(override_color)
                        self.screen.blit(tint, (sx, sy))

                    # Dim exterior when on non-ground floor
                    if dim_exterior and not in_player_building:
                        self.screen.blit(self._get_dim_overlay(140), (sx, sy))

                    # Terrain edge blending for natural terrain types
                    # (skip every other tile in a checkerboard to halve cost)
                    if (tile_type in _NATURAL_BLEND_TYPES
                            and (x + y) % 2 == (self._water_anim_tick // 60) % 2):
                        try:
                            self._blend_terrain_edge(world, x, y, sx, sy, tile_type)
                        except Exception:
                            pass  # blending is cosmetic, don't crash

                elif explored:
                    # Underground: all explored surface tiles are black
                    if player_floor < 0:
                        pygame.draw.rect(self.screen, (0, 0, 0),
                                         (sx, sy, TILE_SIZE, TILE_SIZE))
                        continue

                    tile_type = world.tiles[y][x]
                    if tile_type in interior_tiles and (x, y) in building_tiles:
                        roof = self._get_roof_dimmed(x, y, world)
                        if roof:
                            self.screen.blit(roof, (sx, sy))
                            continue

                    tile_surf = self._tile_cache.get(tile_type)
                    if tile_surf:
                        dimmed = self._get_dimmed_tile(tile_surf, 140)
                        self.screen.blit(dimmed, (sx, sy))
                    else:
                        # Fallback for explored tile without cached surface
                        fallback_color = TERRAIN_COLORS.get(tile_type, (80, 80, 80))
                        fc = tuple(c // 2 for c in fallback_color)  # dimmed
                        pygame.draw.rect(self.screen, fc,
                                         (sx, sy, TILE_SIZE, TILE_SIZE))
                else:
                    pygame.draw.rect(self.screen, (5, 5, 10),
                                    (sx, sy, TILE_SIZE, TILE_SIZE))

        # 2.5D building overlay — draw upper floor walls and roofs
        self._draw_building_heights(world, camera, player, x0, y0, x1, y1)


    def _draw_building_heights(self, world, camera, player, x0, y0, x1, y1):
        """Draw 2.5D building heights using per-tile cube approach.

        Each WALL tile is treated as a cube. We draw:
        - South face: on any wall tile that has a non-wall tile to its south
        - East face: on any wall tile that has a non-wall tile to its east
        - Roof: on top of all building tiles (wall + interior), offset upward

        This naturally follows any building shape — rectangular, circular,
        L-shaped, etc.
        """
        player_rect = getattr(player, '_current_building_rect', None) if player else None
        time_norm = getattr(world, '_time_normalized', 0.35)
        building_tiles = getattr(world, '_building_interior_tiles', set())

        # Determine building heights from the tile structure map
        if not hasattr(self, '_tile_structure_map'):
            self._get_roof_for_tile(0, 0, world)  # builds the map

        # Collect all building tile positions with their height
        height_map = {}  # (x, y) -> num_floors
        if hasattr(world, 'plan'):
            for sp in world.plan.settlements:
                for bld in sp.buildings:
                    bx, by = bld['x'], bld['y']
                    bw, bh = bld['w'], bld['h']
                    bname = bld.get('name', '')
                    if 'Tower' in bname or 'Keep' in bname or 'Castle' in bname:
                        nf = 3
                    elif sp.kind in ('city', 'castle'):
                        nf = 2
                    else:
                        nf = 1
                    for dy in range(bh):
                        for dx in range(bw):
                            height_map[(bx + dx, by + dy)] = nf
            # Temples
            for loc in world.plan.special_locations:
                if loc.kind == 'temple':
                    r = loc.radius
                    for dy in range(-r, r + 1):
                        for dx in range(-r, r + 1):
                            if dx * dx + dy * dy <= r * r:
                                height_map[(loc.x + dx, loc.y + dy)] = 1

        wall_types = (WALL,)
        interior_types = (FLOOR, TABLE, BED, CHEST, STAIRS_UP, STAIRS_DOWN,
                          FIREPLACE, PILLAR, ALTAR, THRONE, BOOKSHELF, BARREL,
                          ANVIL, FORGE_FIRE, FOUNTAIN, CARPET, MOSAIC, ARCHWAY,
                          DOOR, WINDOW)
        floor_px = TILE_SIZE * 3 // 4  # height per floor in pixels

        # Wall colors
        wall_color_s = (140, 125, 105)  # south face (lit)
        wall_color_e = (110, 100, 85)   # east face (darker)

        # Roof colors by kind
        roof_colors = {
            "hamlet": (140, 100, 55), "village": (130, 75, 40),
            "town": (110, 80, 55), "city": (85, 90, 100),
            "castle": (70, 75, 85), "temple": (150, 130, 60),
        }

        # Process tiles from north to south (painter's algorithm)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if (x, y) not in height_map:
                    continue

                # Skip building the player is inside
                if player_rect:
                    pbx, pby, pbw, pbh = player_rect
                    if pbx <= x < pbx + pbw and pby <= y < pby + pbh:
                        continue

                tile = world.tiles[y][x]
                if tile not in wall_types and tile not in interior_types:
                    continue

                num_floors = height_map[(x, y)]
                wall_h = num_floors * floor_px

                sx = x * TILE_SIZE - int(camera.x)
                sy = y * TILE_SIZE - int(camera.y)

                # --- SOUTH FACE ---
                # Draw on ANY building-edge tile (not just WALL) so the
                # exterior wall aligns with the floor plan boundary.
                south_in_building = (x, y + 1) in height_map
                if not south_in_building:
                    wr, wg, wb = wall_color_s
                    wall_top = sy + TILE_SIZE
                    wall_bot = wall_top + wall_h
                    # Clamp to screen
                    draw_top = max(0, wall_top)
                    draw_bot = min(SCREEN_HEIGHT, wall_bot)
                    if draw_top < draw_bot:
                        # Single rect fill for the wall face
                        pygame.draw.rect(self.screen, (wr, wg, wb),
                                         (sx, draw_top, TILE_SIZE, draw_bot - draw_top))
                        # Gradient: darken bottom with a single overlay
                        if wall_h > 4:
                            grad_h = (draw_bot - draw_top) // 2
                            gk_s = (TILE_SIZE, grad_h, 30)
                            grad_surf = self._wall_grad_cache.get(gk_s)
                            if grad_surf is None:
                                grad_surf = pygame.Surface((TILE_SIZE, grad_h), pygame.SRCALPHA)
                                grad_surf.fill((0, 0, 0, 30))
                                self._wall_grad_cache[gk_s] = grad_surf
                            self.screen.blit(grad_surf, (sx, draw_bot - grad_h))
                        # A few accent brick lines (every 6px instead of every 3px)
                        brick_color = (max(0, wr - 18), max(0, wg - 18), max(0, wb - 15))
                        for py in range(0, wall_h, 6):
                            draw_y = wall_top + py
                            if draw_top <= draw_y < draw_bot:
                                pygame.draw.line(self.screen, brick_color,
                                                 (sx, draw_y), (sx + TILE_SIZE, draw_y))

                # --- EAST FACE ---
                east_in_building = (x + 1, y) in height_map
                if not east_in_building:
                    wr, wg, wb = wall_color_e
                    east_x = sx + TILE_SIZE
                    east_w = max(2, TILE_SIZE // 5)
                    wall_top_e = sy + TILE_SIZE
                    wall_bot_e = wall_top_e + wall_h
                    draw_top_e = max(0, wall_top_e)
                    draw_bot_e = min(SCREEN_HEIGHT, wall_bot_e)
                    if draw_top_e < draw_bot_e and 0 <= east_x < SCREEN_WIDTH:
                        # Single rect fill for east face
                        draw_w = min(east_w, SCREEN_WIDTH - east_x)
                        pygame.draw.rect(self.screen,
                                         (int(wr * 0.85), int(wg * 0.85), int(wb * 0.85)),
                                         (east_x, draw_top_e, draw_w, draw_bot_e - draw_top_e))
                        # Darken bottom half
                        if wall_h > 4:
                            grad_h = (draw_bot_e - draw_top_e) // 2
                            gk_e = (draw_w, grad_h, 25)
                            grad_surf = self._wall_grad_cache.get(gk_e)
                            if grad_surf is None:
                                grad_surf = pygame.Surface((draw_w, grad_h), pygame.SRCALPHA)
                                grad_surf.fill((0, 0, 0, 25))
                                self._wall_grad_cache[gk_e] = grad_surf
                            self.screen.blit(grad_surf, (east_x, draw_bot_e - grad_h))

                # --- FLAT ROOF TILE (drawn offset upward) ---
                kind = self._tile_structure_map.get((x, y), "default")
                # Override kind based on building function for colored roofs
                bfunc = self._building_function_cache.get((x, y), "")
                if bfunc:
                    fl = bfunc.lower()
                    if "tavern" in fl or "inn" in fl:
                        kind = "tavern"
                    elif "temple" in fl or "shrine" in fl:
                        kind = "temple"
                    elif "blacksmith" in fl or "forge" in fl or "smith" in fl:
                        kind = "blacksmith"
                    elif "market" in fl or "shop" in fl:
                        kind = "market"
                roof_y = sy - wall_h
                if -TILE_SIZE < roof_y < SCREEN_HEIGHT:
                    roof_surf = self._get_roof_tile_25d(kind, x, y)
                    self.screen.blit(roof_surf, (sx, roof_y))

        # --- PITCHED ROOF PASS ---
        # Draw pitched gable roofs on top of buildings. The gable is a
        # triangular south face + sloped ridge visible from above.
        self._draw_pitched_roofs(world, camera, player_rect, height_map,
                                 floor_px, x0, y0, x1, y1)

    def _draw_pitched_roofs(self, world, camera, player_rect, height_map,
                            floor_px, x0, y0, x1, y1):
        """Draw pitched roof shading over the flat roof tiles.

        Following the standard 3/4 perspective approach (Zelda, Stardew
        Valley, RPG Maker): the roof is already drawn as flat tiles. We
        add slope shading — south half is lit (brighter), north half is
        in shadow (darker), with a ridge line across the center. This
        creates the illusion of a pitched roof without any geometric
        projection. For circular buildings, apply radial shading instead.
        """
        buildings = []
        if hasattr(world, 'plan'):
            for sp in world.plan.settlements:
                for bld in sp.buildings:
                    bx, by = bld['x'], bld['y']
                    bw, bh = bld['w'], bld['h']
                    if bx + bw < x0 or bx > x1 or by + bh < y0 or by > y1:
                        continue
                    if player_rect and player_rect == (bx, by, bw, bh):
                        continue
                    buildings.append((bx, by, bw, bh, sp.kind, bld.get('name', '')))

            for loc in world.plan.special_locations:
                if loc.kind == 'temple':
                    r = loc.radius
                    bx, by = loc.x - r, loc.y - r
                    bw, bh = r * 2 + 1, r * 2 + 1
                    if bx + bw >= x0 and bx <= x1 and by + bh >= y0 and by <= y1:
                        if not (player_rect and player_rect == (bx, by, bw, bh)):
                            buildings.append((bx, by, bw, bh, 'temple', loc.name))

        for bx, by, bw, bh, kind, bname in buildings:
            sample_h = height_map.get((bx + 1, by + 1), 1)
            wall_h = sample_h * floor_px

            wall_w_px = bw * TILE_SIZE
            wall_h_px = bh * TILE_SIZE
            sx = bx * TILE_SIZE - int(camera.x)
            sy = by * TILE_SIZE - int(camera.y) - wall_h  # roof level

            is_circular = kind == 'temple'

            # Create a shading overlay for the pitched effect
            shade_surf = pygame.Surface((wall_w_px, wall_h_px), pygame.SRCALPHA)

            if is_circular:
                # Conical roof: darken radially from center, with south
                # side brighter (facing our viewpoint)
                cx_l = wall_w_px // 2
                cy_l = wall_h_px // 2
                max_r = min(cx_l, cy_l)
                for py in range(wall_h_px):
                    for px in range(wall_w_px):
                        dx = px - cx_l
                        dy = py - cy_l
                        dist = (dx * dx + dy * dy) ** 0.5
                        if dist > max_r + 2:
                            continue
                        # Radial: darker at edges (slope falls away)
                        r_t = min(1.0, dist / max(1, max_r))
                        # Directional: south side (dy > 0) is brighter
                        dir_t = (dy / max(1, max_r)) * 0.3
                        # Combined: center is bright, edges dark, south brighter
                        alpha = int(r_t * 80 - dir_t * 40)
                        alpha = max(0, min(120, alpha))
                        shade_surf.set_at((px, py), (0, 0, 0, alpha))
                # Highlight ring near the peak
                pygame.draw.circle(shade_surf, (255, 255, 200, 25),
                                   (cx_l, cy_l), max(3, max_r // 4), 1)
            else:
                # Gable roof: north half darkened, south half brightened,
                # ridge line across the center
                mid_y = wall_h_px // 2
                for py in range(wall_h_px):
                    if py < mid_y:
                        # North slope: in shadow (darken)
                        t = 1.0 - (py / max(1, mid_y))  # 1 at top, 0 at ridge
                        alpha = int(t * 70 + 20)
                        pygame.draw.line(shade_surf, (0, 0, 0, alpha),
                                         (0, py), (wall_w_px - 1, py))
                    else:
                        # South slope: lit (brighten slightly)
                        t = (py - mid_y) / max(1, wall_h_px - mid_y)
                        alpha = int((1.0 - t) * 25)  # brightest near ridge
                        pygame.draw.line(shade_surf, (255, 255, 220, alpha),
                                         (0, py), (wall_w_px - 1, py))

                # Ridge line
                pygame.draw.line(shade_surf, (0, 0, 0, 80),
                                 (0, mid_y), (wall_w_px - 1, mid_y), 2)
                # Subtle highlight just south of ridge
                pygame.draw.line(shade_surf, (255, 255, 200, 30),
                                 (0, mid_y + 2), (wall_w_px - 1, mid_y + 2))

            self.screen.blit(shade_surf, (sx, sy))

            # Eave shadow line at the south edge of the roof
            eave_y = sy + wall_h_px
            if 0 <= eave_y < SCREEN_HEIGHT:
                pygame.draw.line(self.screen, (40, 35, 30),
                                 (sx, eave_y), (sx + wall_w_px - 1, eave_y))

    def _get_roof_tile_25d(self, kind: str, wx: int, wy: int) -> pygame.Surface:
        """Get a pre-rendered roof tile for the 2.5D view.

        Different building types get different roof styles:
          hamlet:  thatch (straw bundles, warm golden-brown)
          village: clay tile (overlapping orange-red tiles)
          town:    wood shingle (dark brown planks)
          city:    slate (gray-blue flat stone)
          castle:  stone battlement (gray crenellations)
          temple:  copper/gold (green-gold patina)

        Each tile has per-position variation so roofs don't look uniform.
        """
        # Cache key includes kind + position hash for variation
        variant = (wx * 7 + wy * 13) % 4
        cache_key = (kind, variant)

        if not hasattr(self, '_roof_25d_cache'):
            self._roof_25d_cache = {}

        if cache_key in self._roof_25d_cache:
            return self._roof_25d_cache[cache_key]

        ts = TILE_SIZE
        surf = pygame.Surface((ts, ts))

        if kind == "hamlet":
            # THATCH — warm straw bundles
            base = (155 + variant * 5, 120 + variant * 3, 55 + variant * 4)
            surf.fill(base)
            r, g, b = base
            # Horizontal straw lines
            for py in range(0, ts, 2):
                offset = variant * 2 + (py // 2) % 3
                shade = r - 8 + (py % 4) * 2
                pygame.draw.line(surf, (max(40, shade), max(40, g - 6), max(20, b - 4)),
                                 (offset, py), (ts, py))
            # Straw bundle edges (diagonal)
            for py in range(0, ts, 5):
                pygame.draw.line(surf, (r - 20, g - 15, b - 8),
                                 (0, py), (min(ts, py + 6), 0))

        elif kind == "village":
            # CLAY TILE — overlapping curved red-orange tiles
            base = (165 + variant * 4, 75 + variant * 3, 40 + variant * 2)
            surf.fill(base)
            r, g, b = base
            # Overlapping tile rows
            tile_h = max(3, ts // 4)
            for row in range(0, ts, tile_h):
                offset = (tile_h // 2) if (row // tile_h) % 2 else 0
                # Each tile is a small rounded rectangle
                for col in range(offset - tile_h, ts + tile_h, tile_h + 1):
                    shade = r + ((col + row) % 3) * 4 - 4
                    tc = (max(40, min(255, shade)),
                          max(20, min(255, g + ((col * 3) % 5) - 2)),
                          max(15, min(255, b + ((row * 2) % 3) - 1)))
                    pygame.draw.rect(surf, tc, (col, row, tile_h, tile_h - 1))
                    # Highlight on top edge of each tile
                    pygame.draw.line(surf, (min(255, tc[0] + 15), min(255, tc[1] + 10), min(255, tc[2] + 8)),
                                     (col, row), (col + tile_h - 1, row))

        elif kind == "town":
            # WOOD SHINGLE — dark brown overlapping planks
            base = (95 + variant * 3, 70 + variant * 2, 45 + variant * 2)
            surf.fill(base)
            r, g, b = base
            plank_h = max(3, ts // 5)
            for row in range(0, ts, plank_h):
                offset = (ts // 3) if (row // plank_h) % 2 else 0
                for col in range(offset - ts // 2, ts + ts // 2, ts // 2):
                    shade = ((col + row * 3) % 7) - 3
                    pc = (max(30, r + shade * 2), max(20, g + shade), max(15, b + shade))
                    pygame.draw.rect(surf, pc, (col, row, ts // 2 - 1, plank_h - 1))
                    # Wood grain
                    pygame.draw.line(surf, (max(20, r - 12), max(15, g - 10), max(10, b - 8)),
                                     (col + 1, row + plank_h // 2),
                                     (col + ts // 2 - 2, row + plank_h // 2))

        elif kind == "city":
            # SLATE — flat gray-blue stone tiles
            base = (90 + variant * 3, 95 + variant * 2, 110 + variant * 3)
            surf.fill(base)
            r, g, b = base
            slate_h = max(2, ts // 6)
            for row in range(0, ts, slate_h):
                offset = (ts // 4) if (row // slate_h) % 2 else 0
                for col in range(offset - ts // 3, ts + ts // 3, ts // 3):
                    shade = ((col * 5 + row * 7) % 5) - 2
                    sc = (max(50, r + shade * 2), max(55, g + shade * 2), max(65, b + shade * 3))
                    pygame.draw.rect(surf, sc, (col, row, ts // 3 - 1, slate_h - 1))
            # Subtle blue sheen
            sheen = pygame.Surface((ts, ts), pygame.SRCALPHA)
            sheen.fill((100, 120, 160, 15))
            surf.blit(sheen, (0, 0))

        elif kind == "castle":
            # STONE BATTLEMENT — gray stone blocks, darker
            base = (75 + variant * 2, 75 + variant * 2, 80 + variant * 3)
            surf.fill(base)
            r, g, b = base
            block_w = max(3, ts // 3)
            block_h = max(3, ts // 3)
            for row in range(0, ts, block_h):
                offset = (block_w // 2) if (row // block_h) % 2 else 0
                for col in range(offset, ts, block_w):
                    shade = ((col + row) % 4) - 2
                    bc = (max(40, r + shade * 3), max(40, g + shade * 3), max(45, b + shade * 3))
                    pygame.draw.rect(surf, bc, (col, row, block_w - 1, block_h - 1))
            # Mortar lines
            for row in range(0, ts, block_h):
                pygame.draw.line(surf, (max(30, r - 20), max(30, g - 20), max(35, b - 18)),
                                 (0, row), (ts, row))

        elif kind == "temple":
            # WHITE/GOLD — bright stone with gold trim
            base = (210 + variant * 3, 200 + variant * 2, 170 + variant * 4)
            surf.fill(base)
            r, g, b = base
            # Gold trim pattern
            for py in range(0, ts, 4):
                pygame.draw.line(surf, (min(255, r + 10), min(255, g - 5), max(40, b - 30)),
                                 (0, py), (ts, py))
            # Gold decorative cross at center
            cx_t, cy_t = ts // 2, ts // 2
            pygame.draw.line(surf, (220, 190, 60), (cx_t - 2, cy_t), (cx_t + 2, cy_t), 1)
            pygame.draw.line(surf, (220, 190, 60), (cx_t, cy_t - 2), (cx_t, cy_t + 2), 1)
            # Subtle golden sheen
            sheen = pygame.Surface((ts, ts), pygame.SRCALPHA)
            sheen.fill((255, 240, 180, 12))
            surf.blit(sheen, (0, 0))

        elif kind == "tavern":
            # WARM BROWN — inviting reddish-brown thatch/tiles
            base = (155 + variant * 3, 90 + variant * 2, 50 + variant * 2)
            surf.fill(base)
            r, g, b = base
            # Warm tile rows
            tile_h = max(3, ts // 4)
            for row in range(0, ts, tile_h):
                offset = (tile_h // 2) if (row // tile_h) % 2 else 0
                for col in range(offset - tile_h, ts + tile_h, tile_h + 1):
                    shade = r + ((col + row) % 3) * 3 - 3
                    tc = (max(40, min(255, shade)),
                          max(20, min(255, g + ((col * 2) % 4) - 2)),
                          max(15, min(255, b + ((row) % 3) - 1)))
                    pygame.draw.rect(surf, tc, (col, row, tile_h, tile_h - 1))

        elif kind == "blacksmith":
            # DARK GRAY — sooty, dark with embers
            base = (65 + variant * 2, 62 + variant * 2, 60 + variant * 3)
            surf.fill(base)
            r, g, b = base
            # Dark shingle rows
            for row in range(0, ts, 3):
                offset = (ts // 3) if (row // 3) % 2 else 0
                for col in range(offset - ts // 2, ts + ts // 2, ts // 2):
                    shade = ((col + row * 3) % 5) - 2
                    pygame.draw.rect(surf, (max(30, r + shade), max(30, g + shade),
                                             max(30, b + shade)),
                                     (col, row, ts // 2 - 1, 2))
            # Occasional ember glow
            if variant == 0:
                surf.set_at((ts // 3, ts // 2), (200, 100, 30))
            # Soot darkening
            soot = pygame.Surface((ts, ts), pygame.SRCALPHA)
            soot.fill((0, 0, 0, 20))
            surf.blit(soot, (0, 0))

        elif kind == "market":
            # VIBRANT — colorful canvas/awning style
            base = (170 + variant * 4, 110 + variant * 3, 55 + variant * 3)
            surf.fill(base)
            r, g, b = base
            # Colorful stripe pattern (like canvas awnings)
            stripe_colors = [
                (180, 60, 50), (50, 120, 170), (180, 150, 40), (60, 140, 70),
            ]
            stripe_w = max(2, ts // 4)
            for i, sc in enumerate(stripe_colors):
                sx_s = i * stripe_w
                pygame.draw.rect(surf, sc, (sx_s, 0, stripe_w - 1, ts))
            # Semi-transparent overlay to blend
            blend = pygame.Surface((ts, ts), pygame.SRCALPHA)
            blend.fill((r, g, b, 100))
            surf.blit(blend, (0, 0))

        else:
            # DEFAULT — simple brown
            base = (120 + variant * 3, 95 + variant * 2, 65 + variant * 2)
            surf.fill(base)
            r, g, b = base
            for py in range(0, ts, 3):
                pygame.draw.line(surf, (max(40, r - 10), max(40, g - 8), max(30, b - 6)),
                                 (0, py), (ts, py))

        self._roof_25d_cache[cache_key] = surf
        return surf

    def _get_floor_overlay(self, player, world) -> dict:
        """Get tile overrides for a non-ground floor the player is on.

        Underground levels read from world.underground (the shared underground
        tile system). Upper floors read from the plan's building floor data.
        """
        floor_num = getattr(player, 'current_floor', 0)
        if floor_num == 0:
            return {}

        current_building = getattr(player, '_current_building_rect', None)

        # Underground: read from world.underground tile layer
        if floor_num < 0 and hasattr(world, 'underground'):
            level_tiles = world.underground.get(floor_num, {})
            if current_building:
                bx, by, bw, bh = current_building
                # Return all underground tiles in the building area + nearby
                # (tunnels may extend beyond building footprint)
                overlay = {}
                margin = 20  # look beyond building for tunnels
                for ty in range(by - margin, by + bh + margin):
                    for tx in range(bx - margin, bx + bw + margin):
                        if (tx, ty) in level_tiles:
                            overlay[(tx, ty)] = level_tiles[(tx, ty)]
                return overlay
            return {}

        # Upper floors: read from plan building data
        if floor_num > 0 and current_building:
            bx, by, bw, bh = current_building
            if hasattr(world, 'plan'):
                for sp in world.plan.settlements:
                    for bld in sp.buildings:
                        if (bld['x'] == bx and bld['y'] == by and
                                bld['w'] == bw and bld['h'] == bh):
                            floors = bld.get('floors', {})
                            floor_tiles = floors.get(floor_num)
                            if floor_tiles:
                                overlay = {}
                                for iy in range(min(len(floor_tiles), bh)):
                                    for ix in range(min(len(floor_tiles[iy]), bw)):
                                        overlay[(bx + ix, by + iy)] = floor_tiles[iy][ix]
                                return overlay
                            break

        return {}

        return overlay

    def _blend_terrain_edge(self, world, x: int, y: int, sx: int, sy: int,
                            tile_type: int):
        """Draw subtle edge blending where two natural terrain types meet.
        Uses semi-transparent pixels along all 4 tile edges for a softer look."""
        if not hasattr(self, '_edge_cache'):
            self._edge_cache = {}

        # Check all 4 neighbors
        neighbors = [
            (x + 1, y, "right"), (x - 1, y, "left"),
            (x, y + 1, "down"), (x, y - 1, "up"),
        ]
        natural = {GRASS, SAND, FOREST, DENSE_FOREST, SNOW, SWAMP, WATER,
                    MOUNTAIN, FARMLAND, ROCKY_GROUND, MARSH}

        blend_start = TILE_SIZE * 2 // 3  # start blending at 2/3 of tile
        blend_width = max(1, TILE_SIZE // 3)  # blend over last 1/3

        for nx, ny, direction in neighbors:
            if not (0 <= nx < world.width and 0 <= ny < world.height):
                continue
            neighbor_type = world.tiles[ny][nx]
            if neighbor_type == tile_type or neighbor_type not in natural:
                continue

            # Create a small blending overlay
            cache_key = (tile_type, neighbor_type, direction)
            if cache_key not in self._edge_cache:
                blend = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                n_color = TERRAIN_COLORS.get(neighbor_type, (80, 80, 80))

                if direction == "right":
                    for px in range(blend_start, TILE_SIZE):
                        alpha = int(((px - blend_start) / blend_width) * 80)
                        for py in range(0, TILE_SIZE, 2):
                            if (px + py) % 3 == 0:
                                blend.set_at((px, py),
                                             (n_color[0], n_color[1], n_color[2], alpha))
                elif direction == "left":
                    for px in range(0, TILE_SIZE - blend_start):
                        alpha = int(((TILE_SIZE - blend_start - px) / blend_width) * 80)
                        for py in range(0, TILE_SIZE, 2):
                            if (px + py) % 3 == 0:
                                blend.set_at((px, py),
                                             (n_color[0], n_color[1], n_color[2], alpha))
                elif direction == "down":
                    for py in range(blend_start, TILE_SIZE):
                        alpha = int(((py - blend_start) / blend_width) * 80)
                        for px in range(0, TILE_SIZE, 2):
                            if (px + py) % 3 == 0:
                                blend.set_at((px, py),
                                             (n_color[0], n_color[1], n_color[2], alpha))
                elif direction == "up":
                    for py in range(0, TILE_SIZE - blend_start):
                        alpha = int(((TILE_SIZE - blend_start - py) / blend_width) * 80)
                        for px in range(0, TILE_SIZE, 2):
                            if (px + py) % 3 == 0:
                                blend.set_at((px, py),
                                             (n_color[0], n_color[1], n_color[2], alpha))

                self._edge_cache[cache_key] = blend

            self.screen.blit(self._edge_cache[cache_key], (sx, sy))

    # ================================================================
    # INTERIOR RENDERING
    # ================================================================

    def draw_interior(self, interior, player, camera):
        """Draw an interior map with thin walls and large detailed tiles."""
        from game.systems.interiors import INTERIOR_TILE_SIZE

        ts = INTERIOR_TILE_SIZE  # 64px per tile — detailed interiors

        # Center camera on player, clamped to interior bounds
        ix = player.interior_state.interior_x
        iy = player.interior_state.interior_y
        cam_x = ix * ts - SCREEN_WIDTH // 2
        cam_y = iy * ts - SCREEN_HEIGHT // 2

        # Clamp camera so we don't show black void outside the interior
        max_cam_x = interior.width * ts - SCREEN_WIDTH
        max_cam_y = interior.height * ts - SCREEN_HEIGHT
        cam_x = max(0, min(max_cam_x, cam_x))
        cam_y = max(0, min(max_cam_y, cam_y))

        # Building-type-specific color palette
        kind = getattr(interior, 'building_kind', 'house')
        palettes = {
            "house":   {"wall": (88, 78, 65), "floor": (155, 135, 100), "bg": (18, 14, 12)},
            "tavern":  {"wall": (95, 75, 55), "floor": (160, 130, 85),  "bg": (20, 15, 10)},
            "shop":    {"wall": (90, 80, 68), "floor": (150, 128, 95),  "bg": (18, 14, 12)},
            "temple":  {"wall": (100, 95, 88), "floor": (165, 155, 138), "bg": (15, 14, 16)},
            "castle":  {"wall": (85, 82, 78), "floor": (140, 135, 125), "bg": (12, 12, 14)},
            "dungeon": {"wall": (60, 55, 50), "floor": (95, 88, 78),   "bg": (8, 6, 6)},
            "ruins":   {"wall": (65, 58, 52), "floor": (100, 90, 75),  "bg": (10, 8, 7)},
            "cave":    {"wall": (55, 50, 45), "floor": (85, 78, 68),   "bg": (6, 5, 5)},
            "blacksmith": {"wall": (80, 72, 62), "floor": (130, 115, 90), "bg": (15, 10, 8)},
        }
        pal = palettes.get(kind, palettes["house"])
        wall_col = pal["wall"]
        floor_col = pal["floor"]

        self.screen.fill(pal["bg"])

        m = ts // 8  # margin unit for furniture detail

        for y in range(interior.height):
            for x in range(interior.width):
                sx = x * ts - int(cam_x)
                sy = y * ts - int(cam_y)
                if sx < -ts or sx > SCREEN_WIDTH or sy < -ts or sy > SCREEN_HEIGHT:
                    continue

                t = interior.tiles[y][x]
                color = TERRAIN_COLORS.get(t, (50, 50, 50))

                # Base fill
                pygame.draw.rect(self.screen, color, (sx, sy, ts, ts))

                # === DETAILED TILE RENDERING AT 128px ===
                if t == WALL:
                    # Stone wall with mortar texture (palette-aware)
                    wr, wg, wb = wall_col
                    pygame.draw.rect(self.screen, wall_col, (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (max(0,wr-12), max(0,wg-12), max(0,wb-10)),
                                    (sx, sy, ts, ts), 2)
                    # Check if adjacent to floor — add shadow at base
                    for dx2, dy2 in [(0,1),(0,-1),(1,0),(-1,0)]:
                        nx2, ny2 = x+dx2, y+dy2
                        if (0 <= nx2 < interior.width and 0 <= ny2 < interior.height
                            and interior.tiles[ny2][nx2] != WALL
                            and interior.tiles[ny2][nx2] != WINDOW):
                            # Shadow on the floor tile adjacent to this wall
                            shadow = pygame.Surface((ts, 4), pygame.SRCALPHA)
                            shadow.fill((0, 0, 0, 40))
                            fsx = nx2 * ts - int(cam_x)
                            fsy = ny2 * ts - int(cam_y)
                            if dy2 == 1:  # wall is above floor
                                self.screen.blit(shadow, (fsx, fsy))
                            elif dy2 == -1:  # wall is below floor
                                self.screen.blit(shadow, (fsx, fsy + ts - 4))
                            break  # only one shadow per wall
                    # Mortar pattern
                    mortar = (max(0,wr-18), max(0,wg-18), max(0,wb-15))
                    for ly in range(sy + ts//4, sy + ts, ts//4):
                        pygame.draw.line(self.screen, mortar, (sx+2, ly), (sx+ts-2, ly))
                    for lx in range(sx + ts//3, sx + ts, ts//3):
                        pygame.draw.line(self.screen, mortar, (lx, sy+2), (lx, sy+ts//4))
                    # Stone block variation
                    for by2 in range(ts//4, ts, ts//4):
                        offset = ts//6 if (by2 // (ts//4)) % 2 else 0
                        for bx2 in range(offset, ts, ts//3):
                            shade = wr + ((bx2 + by2) % 5) * 2 - 4
                            sw2 = min(ts//3 - 2, ts - bx2 - 1)
                            if sw2 > 2:
                                pygame.draw.rect(self.screen,
                                    (max(0,min(255,shade)), max(0,min(255,wg+((bx2+by2)%3)-1)),
                                     max(0,min(255,wb+((bx2*by2)%3)-1))),
                                    (sx+bx2+1, sy+by2+1, sw2, ts//4-2))

                elif t == FLOOR:
                    # Floor with tile pattern (palette-aware)
                    fr, fg, fb = floor_col
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    grout = (max(0,fr-15), max(0,fg-15), max(0,fb-12))
                    pygame.draw.rect(self.screen, grout, (sx, sy, ts, ts), 1)
                    # Floor tile pattern
                    pygame.draw.line(self.screen, grout, (sx+ts//2, sy), (sx+ts//2, sy+ts))
                    pygame.draw.line(self.screen, grout, (sx, sy+ts//2), (sx+ts, sy+ts//2))
                    # Slight shade variation per quadrant
                    for qy in range(2):
                        for qx in range(2):
                            shade = ((qx + qy) % 2) * 4 - 2
                            qs = pygame.Surface((ts//2-2, ts//2-2), pygame.SRCALPHA)
                            if shade > 0:
                                qs.fill((255, 255, 255, shade * 3))
                            else:
                                qs.fill((0, 0, 0, abs(shade) * 3))
                            self.screen.blit(qs, (sx + qx * ts//2 + 1, sy + qy * ts//2 + 1))

                elif t == DOOR:
                    # Wooden door with frame and handle
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))  # floor behind
                    pygame.draw.rect(self.screen, (130, 95, 50), (sx+m, sy+m, ts-2*m, ts-2*m))
                    pygame.draw.rect(self.screen, (100, 70, 35), (sx+m, sy+m, ts-2*m, ts-2*m), 2)
                    # Planks
                    pygame.draw.line(self.screen, (110, 80, 40), (sx+ts//2, sy+m), (sx+ts//2, sy+ts-m))
                    # Handle
                    pygame.draw.circle(self.screen, (180, 160, 80), (sx+ts//2+m*2, sy+ts//2), m)

                elif t == WINDOW:
                    # Window with glass, frame, and daylight glow
                    wr, wg, wb = wall_col
                    pygame.draw.rect(self.screen, wall_col, (sx, sy, ts, ts))
                    # Glass pane — brighter during day
                    time_norm = getattr(player, '_time_norm', 0.5) if player else 0.5
                    if 0.22 < time_norm < 0.78:
                        glass = (150, 195, 230)  # bright daylight
                    else:
                        glass = (40, 50, 70)  # dark night
                    pygame.draw.rect(self.screen, glass, (sx+m*2, sy+m*2, ts-4*m, ts-4*m))
                    pygame.draw.rect(self.screen, (max(0,wr-10), max(0,wg-10), max(0,wb-8)),
                                    (sx+m*2, sy+m*2, ts-4*m, ts-4*m), 2)
                    # Cross bars
                    frame = (max(0,wr-5), max(0,wg-5), max(0,wb-3))
                    pygame.draw.line(self.screen, frame, (sx+ts//2,sy+m*2), (sx+ts//2,sy+ts-m*2), 2)
                    pygame.draw.line(self.screen, frame, (sx+m*2,sy+ts//2), (sx+ts-m*2,sy+ts//2), 2)
                    # Light pool on floor below window (during day)
                    if 0.22 < time_norm < 0.78:
                        glow = pygame.Surface((ts, ts//2), pygame.SRCALPHA)
                        glow.fill((255, 240, 200, 20))
                        self.screen.blit(glow, (sx, sy+ts))

                elif t == TABLE:
                    # Rectangular wooden table with items on it
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    # Table legs (shadow)
                    for lx, ly in [(m+2, m+2), (ts-m-4, m+2), (m+2, ts-m-4), (ts-m-4, ts-m-4)]:
                        pygame.draw.rect(self.screen, (90, 65, 35), (sx+lx, sy+ly, 3, 3))
                    # Table top (larger, overlapping legs)
                    tx, ty = sx+m-1, sy+m+1
                    tw, th = ts-2*m+2, ts-2*m-2
                    pygame.draw.rect(self.screen, (145, 110, 65), (tx, ty, tw, th))
                    pygame.draw.rect(self.screen, (115, 85, 48), (tx, ty, tw, th), 2)
                    # Wood grain
                    for gy in range(ty+3, ty+th-2, 4):
                        pygame.draw.line(self.screen, (130, 98, 55), (tx+2, gy), (tx+tw-2, gy))
                    # Items on table: plate and cup
                    pygame.draw.circle(self.screen, (190, 185, 175), (sx+ts//2-m, sy+ts//2), m)
                    pygame.draw.circle(self.screen, (170, 165, 155), (sx+ts//2-m, sy+ts//2), m, 1)
                    pygame.draw.rect(self.screen, (140, 100, 60), (sx+ts//2+m, sy+ts//2-2, 4, 6))

                elif t == BED:
                    # Rectangular bed with headboard, pillow and patterned blanket
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    # Bed frame — wider than tall (rectangular)
                    bx2, by2 = sx+m-2, sy+m+2
                    bw2, bh2 = ts-2*m+4, ts-2*m-2
                    pygame.draw.rect(self.screen, (85, 58, 35), (bx2, by2, bw2, bh2))
                    pygame.draw.rect(self.screen, (70, 45, 25), (bx2, by2, bw2, bh2), 2)
                    # Headboard (darker, at top)
                    pygame.draw.rect(self.screen, (75, 50, 30), (bx2, by2, bw2, 5))
                    # Mattress
                    pygame.draw.rect(self.screen, (170, 145, 115), (bx2+3, by2+6, bw2-6, bh2-9))
                    # Pillow (white/cream, at headboard end)
                    pygame.draw.rect(self.screen, (210, 205, 195), (bx2+5, by2+7, bw2//3, m*2))
                    pygame.draw.rect(self.screen, (190, 185, 175), (bx2+5, by2+7, bw2//3, m*2), 1)
                    # Blanket (colored, covers lower 2/3)
                    blanket_y = by2 + 6 + m*2 + 2
                    blanket_h = bh2 - 9 - m*2 - 2
                    pygame.draw.rect(self.screen, (120, 55, 45), (bx2+3, blanket_y, bw2-6, blanket_h))
                    # Blanket pattern lines
                    for py2 in range(blanket_y+3, blanket_y+blanket_h-1, 5):
                        pygame.draw.line(self.screen, (140, 70, 55), (bx2+5, py2), (bx2+bw2-5, py2))

                elif t == CHEST:
                    # Detailed treasure chest with rounded lid
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    cx2, cy2 = sx+m+2, sy+m+4
                    cw2, ch2 = ts-2*m-4, ts-2*m-6
                    # Body
                    pygame.draw.rect(self.screen, (155, 125, 45), (cx2, cy2+ch2//3, cw2, ch2*2//3))
                    # Lid (rounded top)
                    pygame.draw.ellipse(self.screen, (165, 135, 50), (cx2, cy2, cw2, ch2*2//3))
                    # Outline
                    pygame.draw.rect(self.screen, (110, 85, 25), (cx2, cy2+ch2//3, cw2, ch2*2//3), 2)
                    pygame.draw.ellipse(self.screen, (110, 85, 25), (cx2, cy2, cw2, ch2*2//3), 2)
                    # Metal bands
                    band_col = (180, 175, 110)
                    pygame.draw.rect(self.screen, band_col, (cx2, cy2+ch2//2, cw2, 3))
                    pygame.draw.rect(self.screen, band_col, (cx2+cw2//3, cy2+ch2//4, 3, ch2//2))
                    pygame.draw.rect(self.screen, band_col, (cx2+cw2*2//3, cy2+ch2//4, 3, ch2//2))
                    # Lock (centered, prominent)
                    pygame.draw.circle(self.screen, (200, 190, 80), (sx+ts//2, cy2+ch2//2+1), m)
                    pygame.draw.circle(self.screen, (160, 150, 50), (sx+ts//2, cy2+ch2//2+1), m, 1)

                elif t == STAIRS_UP:
                    pygame.draw.rect(self.screen, (150, 140, 125), (sx, sy, ts, ts))
                    # Steps
                    for step in range(4):
                        sy2 = sy + ts - (step+1) * ts//4
                        shade = 130 + step * 15
                        pygame.draw.rect(self.screen, (shade, shade-10, shade-20),
                                        (sx+m, sy2, ts-2*m, ts//4))
                    # Arrow
                    pts = [(sx+ts//2, sy+m), (sx+m*2, sy+ts//2), (sx+ts-m*2, sy+ts//2)]
                    pygame.draw.polygon(self.screen, (220, 220, 200), pts)

                elif t == STAIRS_DOWN:
                    pygame.draw.rect(self.screen, (100, 90, 80), (sx, sy, ts, ts))
                    for step in range(4):
                        sy2 = sy + step * ts//4
                        shade = 110 - step * 10
                        pygame.draw.rect(self.screen, (shade, shade-8, shade-15),
                                        (sx+m, sy2, ts-2*m, ts//4))
                    pts = [(sx+ts//2, sy+ts-m), (sx+m*2, sy+ts//2), (sx+ts-m*2, sy+ts//2)]
                    pygame.draw.polygon(self.screen, (170, 170, 155), pts)

                elif t == FIREPLACE:
                    pygame.draw.rect(self.screen, (80, 70, 60), (sx, sy, ts, ts))  # stone surround
                    pygame.draw.rect(self.screen, (40, 20, 10), (sx+m*2, sy+m*2, ts-4*m, ts-4*m))  # firebox
                    # Flames
                    pygame.draw.polygon(self.screen, (220, 140, 20),
                        [(sx+ts//3, sy+ts-m*2), (sx+ts//2, sy+m*3), (sx+2*ts//3, sy+ts-m*2)])
                    pygame.draw.polygon(self.screen, (240, 200, 40),
                        [(sx+ts//3+m, sy+ts-m*2), (sx+ts//2, sy+m*4), (sx+2*ts//3-m, sy+ts-m*2)])

                elif t == PILLAR:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))  # floor
                    pygame.draw.circle(self.screen, (170, 165, 155), (sx+ts//2, sy+ts//2), ts//3)
                    pygame.draw.circle(self.screen, (150, 145, 135), (sx+ts//2, sy+ts//2), ts//3, 2)

                elif t == ALTAR:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (200, 195, 180), (sx+m, sy+m*2, ts-2*m, ts-3*m))
                    pygame.draw.rect(self.screen, (170, 160, 145), (sx+m, sy+m*2, ts-2*m, ts-3*m), 2)
                    # Candles
                    pygame.draw.rect(self.screen, (240, 230, 180), (sx+m*2, sy+m, 3, m*2))
                    pygame.draw.rect(self.screen, (240, 230, 180), (sx+ts-m*2-3, sy+m, 3, m*2))

                elif t == THRONE:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (160, 130, 40), (sx+m, sy+m, ts-2*m, ts-2*m))
                    pygame.draw.rect(self.screen, (200, 170, 50), (sx+m+2, sy+m+2, ts-2*m-4, ts//2))
                    pygame.draw.rect(self.screen, (130, 100, 30), (sx+m, sy+m, ts-2*m, ts-2*m), 2)

                elif t == BOOKSHELF:
                    pygame.draw.rect(self.screen, (90, 65, 38), (sx+m, sy, ts-2*m, ts))
                    # Book spines
                    colors = [(140,40,40),(40,80,140),(40,120,60),(140,120,40),(100,50,120)]
                    bw = max(3, (ts-2*m-4) // 5)
                    for i, c in enumerate(colors):
                        pygame.draw.rect(self.screen, c, (sx+m+2+i*bw, sy+2, bw-1, ts//3-2))
                        pygame.draw.rect(self.screen, c, (sx+m+2+i*bw, sy+ts//3+2, bw-1, ts//3-2))

                elif t == BARREL:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    pygame.draw.ellipse(self.screen, (120, 85, 45), (sx+m, sy+m, ts-2*m, ts-2*m))
                    pygame.draw.ellipse(self.screen, (100, 70, 35), (sx+m, sy+m, ts-2*m, ts-2*m), 2)
                    # Bands
                    pygame.draw.ellipse(self.screen, (80, 80, 90), (sx+m+2, sy+ts//3, ts-2*m-4, ts//6), 2)

                elif t == FOUNTAIN:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    pygame.draw.circle(self.screen, (80, 140, 190), (sx+ts//2, sy+ts//2), ts//3)
                    pygame.draw.circle(self.screen, (60, 110, 160), (sx+ts//2, sy+ts//2), ts//3, 2)
                    pygame.draw.circle(self.screen, (120, 180, 220), (sx+ts//2, sy+ts//2), ts//6)

                elif t == CARPET:
                    pygame.draw.rect(self.screen, (140, 45, 45), (sx+2, sy+2, ts-4, ts-4))
                    pygame.draw.rect(self.screen, (160, 60, 40), (sx+2, sy+2, ts-4, ts-4), 1)
                    # Pattern
                    pygame.draw.rect(self.screen, (170, 80, 50), (sx+m*2, sy+m*2, ts-4*m, ts-4*m), 1)

                elif t == MOSAIC:
                    pygame.draw.rect(self.screen, (160, 145, 105), (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (145, 130, 95), (sx, sy, ts//2, ts//2))
                    pygame.draw.rect(self.screen, (145, 130, 95), (sx+ts//2, sy+ts//2, ts//2, ts//2))
                    pygame.draw.rect(self.screen, (130, 118, 88), (sx, sy, ts, ts), 1)

                elif t == ANVIL:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (90, 90, 100), (sx+m, sy+ts//3, ts-2*m, ts//2))
                    pygame.draw.rect(self.screen, (110, 110, 120), (sx+m-2, sy+ts//3-2, ts-2*m+4, m*2))

                elif t == FORGE_FIRE:
                    pygame.draw.rect(self.screen, (60, 50, 45), (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (30, 15, 10), (sx+m, sy+m, ts-2*m, ts-2*m))
                    # Hot coals
                    pygame.draw.ellipse(self.screen, (200, 80, 20), (sx+m+2, sy+ts//3, ts-2*m-4, ts//3))
                    pygame.draw.ellipse(self.screen, (240, 160, 30), (sx+ts//3, sy+ts//3+2, ts//3, ts//4))

                elif t == ARCHWAY:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))  # floor
                    # Arch pillars on sides
                    pygame.draw.rect(self.screen, (140, 130, 115), (sx, sy, m*2, ts))
                    pygame.draw.rect(self.screen, (140, 130, 115), (sx+ts-m*2, sy, m*2, ts))
                    # Arch top
                    pygame.draw.arc(self.screen, (140, 130, 115), (sx, sy-ts//3, ts, ts), 0, 3.14, 3)

                elif t == IRON_GATE:
                    pygame.draw.rect(self.screen, (60, 60, 70), (sx, sy, ts, ts))
                    # Bars
                    for gx in range(sx+m, sx+ts-m, m*2):
                        pygame.draw.line(self.screen, (90, 90, 100), (gx, sy+2), (gx, sy+ts-2), 2)
                    pygame.draw.line(self.screen, (80, 80, 90), (sx+2, sy+ts//3), (sx+ts-2, sy+ts//3), 2)
                    pygame.draw.line(self.screen, (80, 80, 90), (sx+2, sy+2*ts//3), (sx+ts-2, sy+2*ts//3), 2)

                elif t == LOCKED_DOOR:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (100, 70, 35), (sx+m, sy+m, ts-2*m, ts-2*m))
                    pygame.draw.rect(self.screen, (80, 55, 25), (sx+m, sy+m, ts-2*m, ts-2*m), 2)
                    pygame.draw.line(self.screen, (75, 50, 25), (sx+ts//2, sy+m), (sx+ts//2, sy+ts-m), 2)
                    # Lock icon
                    pygame.draw.circle(self.screen, (200, 180, 60), (sx+ts//2+m, sy+ts//2), m+1)
                    pygame.draw.circle(self.screen, (160, 140, 40), (sx+ts//2+m, sy+ts//2), m+1, 2)

        # Lighting effects — warm glow around fireplaces, forges, and candles
        light_sources = []
        for y in range(interior.height):
            for x in range(interior.width):
                t = interior.tiles[y][x]
                if t == FIREPLACE:
                    light_sources.append((x, y, (255, 160, 60), 5))
                elif t == FORGE_FIRE:
                    light_sources.append((x, y, (255, 120, 40), 4))
                elif t == ALTAR:
                    light_sources.append((x, y, (180, 180, 255), 3))
                elif t == FOUNTAIN:
                    light_sources.append((x, y, (100, 160, 220), 2))

        for lx, ly, color, radius in light_sources:
            lsx = int(lx * ts - cam_x) + ts // 2
            lsy = int(ly * ts - cam_y) + ts // 2
            glow_r = ts * radius
            glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            # Radial gradient glow
            for ring in range(glow_r, 0, -2):
                alpha = int(25 * (ring / glow_r))
                pygame.draw.circle(glow, (color[0], color[1], color[2], alpha),
                                   (glow_r, glow_r), ring)
            self.screen.blit(glow, (lsx - glow_r, lsy - glow_r))

        # Draw NPCs inside this building
        if hasattr(player, 'interior_state'):
            world_mgr = None
            # Try to find world_mgr via game reference (stored during interact)
            for attr in ('_game_ref',):
                pass  # not available here, use interior.npcs_inside
            # Draw any NPCs with interior positions
            npc_font = self.font_sm
            all_npcs = getattr(interior, '_cached_npcs', [])
            for npc in all_npcs:
                npc_ix = getattr(npc, '_interior_x', -1)
                npc_iy = getattr(npc, '_interior_y', -1)
                if npc_ix < 0 or npc_iy < 0:
                    continue
                npx = int(npc_ix * ts - cam_x)
                npy = int(npc_iy * ts - cam_y)
                if npx < -ts or npx > SCREEN_WIDTH or npy < -ts or npy > SCREEN_HEIGHT:
                    continue

                color = getattr(npc, 'color', (140, 140, 160))
                activity = getattr(npc, '_interior_activity', 'idle')
                nr = ts // 2 - m - 1

                if activity == "sleeping":
                    # Draw NPC lying down (horizontal ellipse)
                    pygame.draw.ellipse(self.screen, (30, 25, 20, 60),
                                       (npx + m, npy + ts // 2 + 2, ts - 2 * m, m * 2))
                    pygame.draw.ellipse(self.screen, color,
                                       (npx + m + 2, npy + ts // 3, ts - 2 * m - 4, ts // 3))
                    # Head to the side
                    head_col = (min(255, color[0] + 25), min(255, color[1] + 20),
                                min(255, color[2] + 10))
                    pygame.draw.circle(self.screen, head_col,
                                       (npx + m + nr // 2, npy + ts // 3 + 2), nr // 3 + 1)
                    # Zzz
                    z_surf = npc_font.render("zzz", True, (180, 180, 220))
                    self.screen.blit(z_surf, (npx + ts // 2 + 4, npy + ts // 4 - 8))
                else:
                    # Standing NPC with shadow
                    pygame.draw.ellipse(self.screen, (30, 25, 20, 80),
                                       (npx + m + 2, npy + ts - m * 2, ts - 2 * m - 4, m * 2))
                    pygame.draw.circle(self.screen, color, (npx + ts // 2, npy + ts // 2), nr)
                    pygame.draw.circle(self.screen, (max(0, color[0] - 20), max(0, color[1] - 20),
                                                      max(0, color[2] - 15)),
                                       (npx + ts // 2, npy + ts // 2), nr, 2)
                    # Head
                    head_col = (min(255, color[0] + 25), min(255, color[1] + 20),
                                min(255, color[2] + 10))
                    pygame.draw.circle(self.screen, head_col,
                                       (npx + ts // 2, npy + ts // 4), nr // 2 + 1)

                # Activity icon above head
                icon_y = npy - 6
                if activity in ("cooking", "eating"):
                    # Plate icon
                    pygame.draw.circle(self.screen, (200, 180, 140), (npx + ts // 2, icon_y), 4)
                    pygame.draw.circle(self.screen, (170, 150, 110), (npx + ts // 2, icon_y), 4, 1)
                elif activity in ("reading", "studying"):
                    # Book icon
                    pygame.draw.rect(self.screen, (100, 60, 40), (npx + ts // 2 - 4, icon_y - 3, 8, 6))
                elif activity in ("working", "smithing"):
                    # Hammer icon
                    pygame.draw.line(self.screen, (180, 180, 190),
                                    (npx + ts // 2 - 2, icon_y - 3),
                                    (npx + ts // 2 + 3, icon_y + 2), 2)
                elif activity in ("talking", "sitting"):
                    # Speech bubble
                    pygame.draw.ellipse(self.screen, WHITE,
                                       (npx + ts // 2 - 4, icon_y - 4, 8, 6))

                # Name label
                name_surf = npc_font.render(npc.name, True, WHITE)
                self.screen.blit(name_surf, (npx + ts // 2 - name_surf.get_width() // 2,
                                              npy - 14))

        # Draw player
        px = int(ix * ts - cam_x)
        py = int(iy * ts - cam_y)
        # Shadow
        pygame.draw.ellipse(self.screen, (30, 25, 20, 100),
                           (px + m, py + ts - m*2, ts - 2*m, m*2))
        # Body
        body_r = ts//2 - m
        pygame.draw.circle(self.screen, (70, 170, 70), (px + ts//2, py + ts//2), body_r)
        pygame.draw.circle(self.screen, (50, 130, 50), (px + ts//2, py + ts//2), body_r, 2)
        # Direction indicator
        fx, fy = getattr(player, 'facing', (0, -1))
        dx_f = int(fx * body_r * 0.6)
        dy_f = int(fy * body_r * 0.6)
        pygame.draw.circle(self.screen, (180, 240, 180), (px + ts//2 + dx_f, py + ts//2 + dy_f), m)

        # Header
        name = interior.building_name
        floor_str = ""
        if interior.floor_num < 0:
            floor_str = f" (Basement {abs(interior.floor_num)})"
        elif interior.floor_num > 0:
            floor_str = f" (Floor {interior.floor_num + 1})"
        label = self.font_lg.render(f"Inside: {name}{floor_str}", True, (200, 200, 220))
        bg = pygame.Surface((label.get_width() + 20, 30), pygame.SRCALPHA)
        bg.fill((15, 15, 25, 210))
        self.screen.blit(bg, (SCREEN_WIDTH // 2 - label.get_width() // 2 - 10, 6))
        self.screen.blit(label, (SCREEN_WIDTH // 2 - label.get_width() // 2, 10))

        # Controls
        hint = self.font_sm.render("[E] at door: Exit  [E] on stairs: Change floor  [WASD] Move",
                                  True, (150, 150, 170))
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 25))

    def draw_building_doors(self, world: World, camera: Camera, player):
        """Draw door indicators on buildings so players can find entrances."""
        if not player or (hasattr(player, 'interior_state') and player.interior_state.is_inside):
            return

        # Cache exterior door positions (built from visible range, not full world)
        if not hasattr(self, '_exterior_doors'):
            self._exterior_doors = []
            self._exterior_doors_scanned = set()

        # Scan visible area for new doors
        vx0, vy0, vx1, vy1 = camera.get_visible_tile_range()
        scan_key = (vx0 // 20, vy0 // 20, vx1 // 20, vy1 // 20)
        if scan_key not in self._exterior_doors_scanned:
            self._exterior_doors_scanned.add(scan_key)
            for y in range(max(0, vy0 - 2), min(world.height, vy1 + 2)):
                for x in range(max(0, vx0 - 2), min(world.width, vx1 + 2)):
                    if world.tiles[y][x] != DOOR:
                        continue
                    if (x, y) in {(dx, dy) for dx, dy in self._exterior_doors}:
                        continue
                    has_wall = False
                    has_outside = False
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx, ny = x+dx, y+dy
                        if 0 <= nx < world.width and 0 <= ny < world.height:
                            t = world.tiles[ny][nx]
                            if t == WALL: has_wall = True
                            elif t in (GRASS, ROAD, SAND, DIRT_TRACK,
                                       GRAVEL_ROAD, COBBLESTONE): has_outside = True
                    if has_wall and has_outside:
                        self._exterior_doors.append((x, y))

        # Only draw doors that are on screen
        x0, y0, x1, y1 = camera.get_visible_tile_range()
        for dx, dy in self._exterior_doors:
            if not (x0 <= dx < x1 and y0 <= dy < y1):
                continue
            sx = dx * TILE_SIZE - int(camera.x)
            sy = dy * TILE_SIZE - int(camera.y)
            pygame.draw.rect(self.screen, (160, 120, 60),
                           (sx + 2, sy + 2, TILE_SIZE - 4, TILE_SIZE - 4))
            pygame.draw.rect(self.screen, (120, 90, 40),
                           (sx + 2, sy + 2, TILE_SIZE - 4, TILE_SIZE - 4), 1)
            dist = abs(dx - player.x) + abs(dy - player.y)
            if dist < 3:
                hint = self.font_sm.render("E", True, (255, 255, 200))
                self.screen.blit(hint, (sx + 3, sy + 1))

    def draw_structures(self, world: World, camera: Camera):
        """Draw structure name labels."""
        for structure in world.structures:
            sx, sy = camera.world_to_screen(structure.x, structure.y - 1.5)
            if -100 < sx < SCREEN_WIDTH + 100 and -50 < sy < SCREEN_HEIGHT + 50:
                # Label background
                label = self.font_sm.render(structure.name, True, WHITE)
                lw, lh = label.get_size()
                bg_rect = pygame.Rect(sx - lw // 2 - 3, sy - lh // 2 - 2, lw + 6, lh + 4)
                bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                kind_colors = {
                    "village": (40, 60, 100, 180),
                    "ruins": (100, 50, 50, 180),
                    "shrine": (80, 50, 100, 180),
                }
                bg_surf.fill(kind_colors.get(structure.kind, (40, 40, 40, 180)))
                self.screen.blit(bg_surf, bg_rect)
                self.screen.blit(label, (sx - lw // 2, sy - lh // 2))

    def draw_graves(self, graves: list, camera: Camera):
        """Draw grave markers and unburied bodies on the world map."""
        for grave in graves:
            sx, sy = camera.world_to_screen(grave.x, grave.y)
            if -20 < sx < SCREEN_WIDTH + 20 and -20 < sy < SCREEN_HEIGHT + 20:
                if not grave.buried:
                    # Unburied body: small dark mound
                    body_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                    pygame.draw.ellipse(body_surf, (80, 60, 50, 180),
                                        (2, TILE_SIZE // 2 - 2, TILE_SIZE - 4, TILE_SIZE // 2))
                    # Skull marker
                    pygame.draw.circle(body_surf, (200, 195, 185, 200),
                                        (TILE_SIZE // 2, TILE_SIZE // 2 - 3), 3)
                    self.screen.blit(body_surf, (sx, sy))
                # Flowers on visited graves
                if grave.flowers > 0 and grave.buried:
                    flower_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                    for i in range(min(grave.flowers, 3)):
                        fx = 3 + i * 4
                        fy = TILE_SIZE - 4
                        pygame.draw.circle(flower_surf, (220, 100, 120, 180),
                                            (fx, fy), 2)
                        pygame.draw.line(flower_surf, (60, 140, 50, 180),
                                          (fx, fy + 2), (fx, fy + 4))
                    self.screen.blit(flower_surf, (sx, sy))

    def draw_ground_items(self, items: list, camera: Camera):
        """Draw items on the ground."""
        for gx, gy, item in items:
            sx, sy = camera.world_to_screen(gx, gy)
            if -TILE_SIZE < sx < SCREEN_WIDTH + TILE_SIZE and -TILE_SIZE < sy < SCREEN_HEIGHT + TILE_SIZE:
                # Simple colored square for items
                color = {
                    ITEM_WEAPON: YELLOW,
                    ITEM_ARMOR: LIGHT_GRAY,
                    ITEM_CONSUMABLE: GREEN,
                    ITEM_RESOURCE: ORANGE,
                    ITEM_QUEST: (200, 100, 255),
                }.get(item.kind, WHITE)

                isz = max(3, TILE_SIZE // 4)
                pygame.draw.rect(self.screen, color,
                                (int(sx) - isz, int(sy) - isz, isz * 2, isz * 2))
                pygame.draw.rect(self.screen, WHITE,
                                (int(sx) - isz, int(sy) - isz, isz * 2, isz * 2), 1)

    def draw_player(self, player: Player, camera: Camera):
        """Draw the player character with NPC-style body parts."""
        from game.ui.player_anim import draw_player_body
        sx, sy = camera.world_to_screen(player.x, player.y)

        # Offset player sprite when on a non-ground floor
        cur_floor = getattr(player, 'current_floor', 0)
        if cur_floor != 0 and getattr(player, '_current_building_rect', None):
            pixels_per_floor = TILE_SIZE // 2
            sy += -cur_floor * pixels_per_floor

        s = max(1, TILE_SIZE // 4)
        player._last_dt = getattr(self, '_last_dt', 0.016)
        if is_mounted(player):
            draw_mounted_entity(self.screen, player, int(sx), int(sy), s,
                                draw_player_body)
        else:
            draw_player_body(self.screen, player, int(sx), int(sy), s)

        # Spawn swing arc on attack (renderer-specific effect)
        attack_timer = getattr(player, 'attack_timer', 0)
        if attack_timer > PLAYER_ATTACK_COOLDOWN * 0.9:
            fx, fy = player.facing
            self.spawn_swing_arc(player.x, player.y, fx, fy)

    def draw_npcs(self, npcs: list, camera: Camera, player: Player, visible_tiles=None):
        """Draw NPCs (only if in player's field of view)."""
        # Distance culling: compute visible tile range with margin
        vx0, vy0, vx1, vy1 = camera.get_visible_tile_range()
        cull_margin = 5
        for npc in npcs:
            # Early tile-range cull before expensive world_to_screen
            if (npc.x < vx0 - cull_margin or npc.x > vx1 + cull_margin or
                    npc.y < vy0 - cull_margin or npc.y > vy1 + cull_margin):
                continue
            # FOV check
            if visible_tiles and (int(npc.x), int(npc.y)) not in visible_tiles:
                continue

            sx, sy = camera.world_to_screen(npc.x, npc.y)
            if not (-TILE_SIZE < sx < SCREEN_WIDTH + TILE_SIZE and
                    -TILE_SIZE < sy < SCREEN_HEIGHT + TILE_SIZE):
                continue

            # Animated body parts (mounted or on foot)
            s = max(1, TILE_SIZE // 4)
            bw, bh = s * 4, s * 5
            update_anim(npc, getattr(self, '_last_dt', 0.016))
            if is_mounted(npc):
                draw_mounted_entity(self.screen, npc, int(sx), int(sy), s,
                                    draw_npc_body)
            else:
                draw_npc_body(self.screen, npc, int(sx), int(sy), s)

            # Consciousness glow (cached surfaces)
            if npc.consciousness > 0:
                cache_key = npc.consciousness
                glow_surf = self._consciousness_glow_cache.get(cache_key)
                if glow_surf is None:
                    glow_color = CONSCIOUSNESS_COLORS.get(cache_key, (140, 140, 200))
                    gr = max(4, s * 3)
                    glow_surf = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
                    pygame.draw.circle(glow_surf, (*glow_color, 60), (gr, gr), gr)
                    self._consciousness_glow_cache[cache_key] = glow_surf
                gr = glow_surf.get_width() // 2
                self.screen.blit(glow_surf, (int(sx) - gr, int(sy) - bh // 2 - gr // 2))

            # Quest marker
            if SHOW_QUEST_MARKERS and npc.has_quest_marker and npc.quest and not npc.quest.turned_in:
                marker_color = YELLOW if not npc.quest.completed else GREEN
                qy = int(sy) - bh // 2 - s * 3
                pygame.draw.polygon(self.screen, marker_color, [
                    (int(sx), qy), (int(sx) - s, qy + s * 2), (int(sx) + s, qy + s * 2)])
                pygame.draw.circle(self.screen, marker_color, (int(sx), qy - max(1, s // 2)), max(1, s // 2))

            dist = player.dist_to(npc)

            # Name (when close)
            if SHOW_NPC_NAMES and dist < 6:
                cached = getattr(npc, '_name_surf', None)
                if cached is None or getattr(npc, '_name_surf_key', None) != npc.name:
                    npc._name_surf = self.font_sm.render(npc.name, True, WHITE)
                    npc._name_surf_key = npc.name
                name_surf = npc._name_surf
                self.screen.blit(name_surf,
                                (int(sx) - name_surf.get_width() // 2, int(sy) - bh // 2 - s * 2))

                # Rich NPCs: gold-tinted name (overwrites white)
                npc_gold = getattr(npc, 'npc_gold', 0)
                if npc_gold > 100:
                    gold_key = (npc.name, 'gold')
                    name_surf = self._name_surf_cache.get(gold_key)
                    if name_surf is None:
                        name_surf = self.font_sm.render(npc.name, True, (255, 215, 80))
                        self._name_surf_cache[gold_key] = name_surf
                    self.screen.blit(name_surf,
                                    (int(sx) - name_surf.get_width() // 2, int(sy) - bh // 2 - s * 2))

            # Action label
            if SHOW_NPC_ACTIONS:
                action_icons = self._action_icons
                act = getattr(npc, 'current_action', npc.state)
                if act in action_icons:
                    label, color = action_icons[act]
                    act_surf = self._action_surf_cache.get(act)
                    if act_surf is None:
                        act_surf = self.font_sm.render(label, True, color)
                        self._action_surf_cache[act] = act_surf
                    self.screen.blit(act_surf, (int(sx) + 10, int(sy) - 24))

            # Cargo indicator
            if SHOW_NPC_CARGO:
                _ws = getattr(npc, '_work_state', None)
                if _ws and getattr(_ws, 'carrying', None):
                    cargo_item = _ws.carrying.get("item", "")
                    cargo_colors = {
                        "food": (200, 180, 80), "ore": (160, 140, 120),
                        "wood": (140, 100, 50), "weapons": (180, 180, 200),
                        "tools": (160, 160, 140), "stone": (140, 140, 140),
                        "clothing": (180, 120, 160), "gold": (220, 200, 60),
                    }
                    cargo_labels = {
                        "food": "F", "ore": "O", "wood": "W",
                        "weapons": "X", "tools": "T", "stone": "S",
                        "clothing": "C", "gold": "G",
                    }
                    cc = cargo_colors.get(cargo_item, (180, 160, 100))
                    cl = cargo_labels.get(cargo_item, "?")
                    cx_pos, cy_pos = int(sx), int(sy) - bh // 2 - s * 3
                    pygame.draw.rect(self.screen, cc,
                                     (cx_pos - 4, cy_pos - 4, 8, 8))
                    pygame.draw.rect(self.screen, (40, 40, 40),
                                     (cx_pos - 4, cy_pos - 4, 8, 8), 1)
                    cargo_surf = self.font_sm.render(cl, True, (40, 40, 40))
                    self.screen.blit(cargo_surf,
                                     (cx_pos - cargo_surf.get_width() // 2,
                                      cy_pos - cargo_surf.get_height() // 2))

            # Speech bubble
            if SHOW_SPEECH_BUBBLES:
                if getattr(npc, 'wants_to_talk', False) or getattr(npc, 'current_action', '') == 'approaching_player':
                    pygame.draw.ellipse(self.screen, WHITE, (int(sx) - 10, int(sy) - 40, 20, 14))
                    pygame.draw.ellipse(self.screen, DARK_GRAY, (int(sx) - 10, int(sy) - 40, 20, 14), 1)
                    bang = self.font_sm.render("!", True, RED)
                    self.screen.blit(bang, (int(sx) - 3, int(sy) - 39))

            # NPC-NPC conversation indicator (speech bubble + partner line)
            if SHOW_NPC_CONVERSATIONS:
                _npc_act = getattr(npc, 'current_action', '')
                _npc_state = getattr(npc, 'state', '')
                if _npc_act == 'talking' or _npc_state == 'socializing':
                    # Draw small speech bubble with "..."
                    bub_x, bub_y = int(sx) + 12, int(sy) - 36
                    pygame.draw.ellipse(self.screen, (240, 240, 220),
                                        (bub_x - 12, bub_y - 6, 24, 14))
                    pygame.draw.ellipse(self.screen, (100, 100, 80),
                                        (bub_x - 12, bub_y - 6, 24, 14), 1)
                    dots = self.font_sm.render("...", True, (80, 80, 60))
                    self.screen.blit(dots, (bub_x - dots.get_width() // 2,
                                            bub_y - dots.get_height() // 2))

            # Status overlays (mood, emotions, traits, needs, party)
            if SHOW_NPC_STATUS:
                if getattr(npc, 'party_id', None):
                    party_color = (100, 200, 255) if getattr(npc, 'party_role', '') == 'leader' else (80, 160, 200)
                    pygame.draw.circle(self.screen, party_color, (int(sx) + 10, int(sy) - 16), 3)

                npc_mood = getattr(npc, 'mood', 0)
                if abs(npc_mood) > 0.2 and dist < 6:
                    mood_color = (50, 200, 50) if npc_mood > 0 else (200, 80, 50)
                    pygame.draw.circle(self.screen, mood_color, (int(sx) - 10, int(sy) - 16), 3)

                if dist < 8:
                    self._draw_npc_emotion_icon(npc, sx, sy, bh, s)

                if dist < 3:
                    traits = getattr(npc, 'social_traits', [])
                    if traits:
                        trait_text = self.font_sm.render(", ".join(traits[:2]), True, (140, 140, 160))
                        self.screen.blit(trait_text, (int(sx) - trait_text.get_width() // 2, int(sy) + 18))

                if dist < 8:
                    self._draw_npc_needs(npc, int(sx), int(sy))

    def draw_conversation_lines(self, conversations, camera: Camera,
                                visible_tiles=None):
        """Draw faint lines between NPCs that are currently in conversation."""
        for conv in conversations:
            n1, n2 = conv.npc1, conv.npc2
            if not (n1.alive and n2.alive):
                continue
            # Both must be on screen
            s1x, s1y = camera.world_to_screen(n1.x, n1.y)
            s2x, s2y = camera.world_to_screen(n2.x, n2.y)
            on1 = -TILE_SIZE < s1x < SCREEN_WIDTH + TILE_SIZE and \
                   -TILE_SIZE < s1y < SCREEN_HEIGHT + TILE_SIZE
            on2 = -TILE_SIZE < s2x < SCREEN_WIDTH + TILE_SIZE and \
                   -TILE_SIZE < s2y < SCREEN_HEIGHT + TILE_SIZE
            if not (on1 and on2):
                continue
            # FOV check
            if visible_tiles:
                if ((int(n1.x), int(n1.y)) not in visible_tiles or
                        (int(n2.x), int(n2.y)) not in visible_tiles):
                    continue
            # Draw faint line (muted color to appear subtle)
            pygame.draw.line(self.screen, (140, 140, 80),
                             (int(s1x), int(s1y) - 10),
                             (int(s2x), int(s2y) - 10), 1)

    def draw_creatures(self, creatures: list, camera: Camera, visible_tiles=None):
        """Draw creatures (only if in player's field of view)."""
        # Distance culling: compute visible tile range with margin
        vx0, vy0, vx1, vy1 = camera.get_visible_tile_range()
        cull_margin = 5
        for creature in creatures:
            if not creature.alive:
                continue

            # Early tile-range cull before expensive world_to_screen
            if (creature.x < vx0 - cull_margin or creature.x > vx1 + cull_margin or
                    creature.y < vy0 - cull_margin or creature.y > vy1 + cull_margin):
                continue

            # FOV check
            if visible_tiles and (int(creature.x), int(creature.y)) not in visible_tiles:
                continue

            sx, sy = camera.world_to_screen(creature.x, creature.y)
            if not (-TILE_SIZE < sx < SCREEN_WIDTH + TILE_SIZE and
                    -TILE_SIZE < sy < SCREEN_HEIGHT + TILE_SIZE):
                continue

            # Animated creature body
            s = max(1, TILE_SIZE // 4)
            update_anim(creature, getattr(self, '_last_dt', 0.016))
            draw_creature_body(self.screen, creature, int(sx), int(sy), s)

            # Speech bubble for intelligent creatures that want to talk
            if SHOW_SPEECH_BUBBLES and getattr(creature, 'wants_to_talk', False):
                bh = s * 5
                pygame.draw.ellipse(self.screen, WHITE,
                                    (int(sx) - 10, int(sy) - bh // 2 - 18, 20, 14))
                pygame.draw.ellipse(self.screen, DARK_GRAY,
                                    (int(sx) - 10, int(sy) - bh // 2 - 18, 20, 14), 1)
                bang = self.font_sm.render("!", True, RED)
                self.screen.blit(bang, (int(sx) - 3, int(sy) - bh // 2 - 17))

    def _draw_npc_needs(self, npc, sx: int, sy: int):
        """Draw small need indicators above NPC when they're low."""
        needs = getattr(npc, 'needs', None)
        if not needs:
            return
        bar_y = sy + 14
        bar_w = 20
        bar_h = 2
        need_colors = {"hunger": (200, 80, 80), "thirst": (80, 120, 200),
                       "rest": (200, 200, 80), "social": (200, 120, 200)}
        for need_name in ("hunger", "thirst", "rest"):
            val = needs.get(need_name, 100)
            if val < 45:
                bx = sx - bar_w // 2
                pygame.draw.rect(self.screen, (30, 30, 30), (bx, bar_y, bar_w, bar_h))
                fill = max(1, int(bar_w * val / 100))
                pygame.draw.rect(self.screen, need_colors[need_name], (bx, bar_y, fill, bar_h))
                bar_y += 3

    def draw_trade_caravans(self, goods_transport, camera: Camera):
        """Draw trade caravans using procedural vehicle sprites."""
        if not goods_transport:
            return
        _vehicle_draw = {
            "handcart": draw_handcart,
            "cart": draw_cart,
            "wagon": draw_wagon,
            "supply_wagon": draw_supply_wagon,
        }
        _goods_colors = {
            "food": (200, 180, 80), "ore": (160, 140, 120),
            "wood": (140, 100, 50), "weapons": (180, 180, 200),
            "tools": (160, 160, 140), "stone": (140, 140, 140),
        }
        cs = max(1, TILE_SIZE // 4)
        for caravan in goods_transport.trade_caravans:
            if caravan.destroyed or caravan.phase == "done":
                continue
            sx, sy = camera.world_to_screen(caravan.x, caravan.y)
            if not (-30 < sx < SCREEN_WIDTH + 30 and
                    -30 < sy < SCREEN_HEIGHT + 30):
                continue

            # Determine cargo color from primary good
            goods_color = None
            if caravan.goods:
                primary = max(caravan.goods, key=caravan.goods.get)
                goods_color = _goods_colors.get(primary, (180, 160, 100))

            draw_fn = _vehicle_draw.get(caravan.vehicle_type, draw_cart)
            draw_fn(self.screen, int(sx), int(sy), cs, goods_color=goods_color)

            # Cargo label
            total = sum(caravan.goods.values())
            if total > 0:
                goods_list = list(caravan.goods.keys())
                lbl = f"{total}x {goods_list[0][:3]}" if goods_list else ""
                lbl_surf = self.font_sm.render(lbl, True, (220, 210, 180))
                self.screen.blit(lbl_surf,
                                 (int(sx) - lbl_surf.get_width() // 2,
                                  int(sy) - cs * 5))

    def draw_transport_ground_items(self, goods_transport, camera: Camera):
        """Draw goods dropped on the ground (from transport system) as small colored diamonds."""
        if not goods_transport:
            return
        ground_colors = {
            "food": (200, 180, 80), "ore": (160, 140, 120),
            "wood": (140, 100, 50), "weapons": (180, 180, 200),
            "tools": (160, 160, 140), "stone": (140, 140, 140),
        }
        for item in goods_transport.ground_items:
            sx, sy = camera.world_to_screen(item.x, item.y)
            if not (-10 < sx < SCREEN_WIDTH + 10 and
                    -10 < sy < SCREEN_HEIGHT + 10):
                continue
            color = ground_colors.get(item.good, (180, 160, 100))
            # Small diamond shape
            pts = [(int(sx), int(sy) - 4), (int(sx) + 4, int(sy)),
                   (int(sx), int(sy) + 4), (int(sx) - 4, int(sy))]
            pygame.draw.polygon(self.screen, color, pts)
            pygame.draw.polygon(self.screen, (60, 50, 40), pts, 1)
            # Quantity label
            lbl = self.font_sm.render(f"{item.quantity}", True, color)
            self.screen.blit(lbl, (int(sx) + 5, int(sy) - 6))

    def draw_world_events(self, events: list, camera):
        """Draw world event indicators."""
        for evt in events:
            sx, sy = camera.world_to_screen(evt.x, evt.y)
            r = int(evt.radius * TILE_SIZE * 0.15)
            if -r < sx < SCREEN_WIDTH + r and -r < sy < SCREEN_HEIGHT + r:
                # Translucent circle
                event_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                color = (200, 100, 100, 25) if "Plague" in evt.name or "Drought" in evt.name else \
                        (100, 100, 200, 25) if "Storm" in evt.name else \
                        (100, 200, 100, 25) if "Harvest" in evt.name or "Festival" in evt.name else \
                        (200, 200, 100, 25)
                pygame.draw.circle(event_surf, color, (r, r), r)
                self.screen.blit(event_surf, (int(sx) - r, int(sy) - r))
                # Label
                label = self.font_sm.render(evt.name, True, WHITE)
                self.screen.blit(label, (int(sx) - label.get_width() // 2, int(sy) - r - 14))

    def draw_battle_visuals(self, battle_visuals, camera):
        """Draw projectiles, siege engines, formations, and impact flashes."""
        if not battle_visuals:
            return

        # Draw formations (colored circles for unit positions)
        for formation in battle_visuals.formations:
            for name, (wx, wy) in formation.positions.items():
                sx, sy = camera.world_to_screen(wx, wy)
                if -20 < sx < SCREEN_WIDTH + 20 and -20 < sy < SCREEN_HEIGHT + 20:
                    pygame.draw.circle(self.screen, (100, 150, 200),
                                       (int(sx), int(sy)), 3)

        # Draw siege engines using procedural sprites
        _siege_draw = {
            "battering_ram": draw_battering_ram,
            "catapult": draw_catapult,
            "trebuchet": draw_trebuchet,
            "siege_tower": draw_siege_tower,
        }
        cs = max(1, TILE_SIZE // 4)
        for se in battle_visuals.siege_engines:
            sx, sy = camera.world_to_screen(se.x, se.y)
            if -50 < sx < SCREEN_WIDTH + 50 and -50 < sy < SCREEN_HEIGHT + 50:
                draw_fn = _siege_draw.get(se.engine_type)
                if draw_fn:
                    firing = getattr(se, 'firing', False)
                    if se.engine_type == "siege_tower":
                        draw_fn(self.screen, int(sx), int(sy), cs)
                    else:
                        draw_fn(self.screen, int(sx), int(sy), cs, firing=firing)
                else:
                    # Fallback for unknown types
                    pw = se.width * TILE_SIZE
                    ph = se.height * TILE_SIZE
                    pygame.draw.rect(self.screen, se.color,
                                    (int(sx) - pw // 2, int(sy) - ph // 2, pw, ph))
                # Label
                label = self.font_sm.render(se.engine_type.replace("_", " "), True, WHITE)
                self.screen.blit(label, (int(sx) - label.get_width() // 2,
                                          int(sy) - se.height * TILE_SIZE // 2 - 12))

        # Draw mounted units (horse shape under NPC)
        for mu in battle_visuals.mounted_units:
            # Mount rendering is handled by the NPC drawer checking mount status
            pass

        # Draw projectiles
        for p in battle_visuals.projectiles:
            sx, sy = camera.world_to_screen(p.x, p.y)
            if -20 < sx < SCREEN_WIDTH + 20 and -20 < sy < SCREEN_HEIGHT + 20:
                ix, iy = int(sx), int(sy)

                # Trail
                for i, (tx, ty) in enumerate(p.trail):
                    tsx, tsy = camera.world_to_screen(tx, ty)
                    alpha = int(100 * (i + 1) / len(p.trail)) if p.trail else 100
                    trail_surf = pygame.Surface((p.size, p.size), pygame.SRCALPHA)
                    trail_surf.fill((p.color[0], p.color[1], p.color[2], alpha))
                    self.screen.blit(trail_surf, (int(tsx), int(tsy)))

                # Projectile body
                if p.kind == "arrow":
                    # Line in direction of travel
                    dx = p.target_x - p.x
                    dy = p.target_y - p.y
                    d = max(0.01, math.sqrt(dx * dx + dy * dy))
                    ex = ix + int(dx / d * 4)
                    ey = iy + int(dy / d * 4)
                    pygame.draw.line(self.screen, p.color, (ix, iy), (ex, ey), 2)
                    # Arrowhead
                    pygame.draw.circle(self.screen, (255, 220, 100), (ex, ey), 1)
                elif p.kind == "stone":
                    pygame.draw.circle(self.screen, p.color, (ix, iy), p.size)
                    pygame.draw.circle(self.screen, (100, 90, 80), (ix, iy), p.size, 1)
                elif p.kind == "fire":
                    pygame.draw.circle(self.screen, (240, 160, 40), (ix, iy), p.size)
                    pygame.draw.circle(self.screen, (255, 220, 80), (ix, iy), p.size - 1)
                else:
                    pygame.draw.circle(self.screen, p.color, (ix, iy), p.size)

        # Draw impact flashes
        for flash in battle_visuals.impact_flashes:
            sx, sy = camera.world_to_screen(flash["x"], flash["y"])
            if -20 < sx < SCREEN_WIDTH + 20 and -20 < sy < SCREEN_HEIGHT + 20:
                alpha = int(200 * (flash["timer"] / 0.3))
                size = flash["size"]
                flash_surf = pygame.Surface((size * 4, size * 4), pygame.SRCALPHA)
                c = flash["color"]
                pygame.draw.circle(flash_surf, (c[0], c[1], c[2], alpha),
                                   (size * 2, size * 2), size * 2)
                self.screen.blit(flash_surf, (int(sx) - size * 2, int(sy) - size * 2))

    def draw_night_overlay(self, darkness: float):
        """Legacy wrapper — converts darkness to normalized time, delegates to draw_lighting."""
        if darkness <= 0:
            return
        # Approximate a normalized time from darkness for smooth transitions
        if darkness >= 0.99:
            approx_time = 0.0  # midnight
        elif darkness > 0:
            approx_time = 0.75 + darkness * 0.083
        else:
            approx_time = 0.5  # noon
        self.draw_lighting(approx_time)

    def draw_lighting(self, game_time_normalized: float, camera=None, world=None):
        """Draw smooth day/night lighting overlay with gradual transitions.

        game_time_normalized: 0.0-1.0 fraction of day (from TimeSystem.normalized).
        camera / world: used for finding light-source tiles on screen.

        Lighting phases (24-hour equivalents):
          Dawn     (5:00-7:00):  warm orange tint, fading to clear
          Midday   (10:00-14:00): full brightness, no overlay
          Afternoon(7:00-10:00 & 14:00-17:00): very slight warm tint
          Dusk     (17:00-19:00): warm amber/pink tint, darkening
          Evening  (19:00-21:00): blue-grey overlay, gradually darkening
          Night    (21:00-5:00):  dark blue overlay
        """
        t = game_time_normalized  # 0.0 - 1.0

        # Convert to 24-hour fractions
        dawn_start  = 5.0 / 24.0    # 0.2083
        dawn_end    = 7.0 / 24.0    # 0.2917
        morning_end = 10.0 / 24.0   # 0.4167
        afternoon   = 14.0 / 24.0   # 0.5833
        dusk_start  = 17.0 / 24.0   # 0.7083
        dusk_end    = 19.0 / 24.0   # 0.7917
        evening_end = 21.0 / 24.0   # 0.875

        if morning_end <= t < afternoon:
            # Peak midday — full brightness, no overlay
            return

        if dawn_end <= t < morning_end:
            # Early morning — very faint warm tint fading out
            progress = (t - dawn_end) / (morning_end - dawn_end)
            alpha = int(20 * (1.0 - progress))
            if alpha <= 2:
                return
            overlay_color = (180, 140, 60, alpha)
        elif afternoon <= t < dusk_start:
            # Late afternoon — very faint warm tint building up
            progress = (t - afternoon) / (dusk_start - afternoon)
            alpha = int(18 * progress)
            if alpha <= 2:
                return
            overlay_color = (180, 130, 50, alpha)
        elif dawn_start <= t < dawn_end:
            # Dawn transition — warm orange tint fading to clear
            progress = (t - dawn_start) / (dawn_end - dawn_start)
            # Strong orange at start, fading out by dawn_end
            alpha = int(50 * (1.0 - progress) + 120 * max(0, 0.5 - progress))
            alpha = max(0, min(alpha, 110))
            # Warm orange-gold tint
            r_c = int(220 * (1.0 - progress * 0.6))
            g_c = int(140 * (1.0 - progress * 0.4))
            b_c = int(40 * (1.0 - progress))
            overlay_color = (r_c, g_c, b_c, alpha)
        elif dusk_start <= t < dusk_end:
            # Dusk transition — warm amber/pink, darkening toward evening
            progress = (t - dusk_start) / (dusk_end - dusk_start)
            alpha = int(30 + 90 * progress)
            # Amber at start, shifting to deeper pink/purple at end
            r_c = int(200 * (1.0 - progress * 0.7) + 40 * progress)
            g_c = int(110 * (1.0 - progress * 0.8))
            b_c = int(50 + 40 * progress)
            overlay_color = (r_c, g_c, b_c, alpha)
        elif dusk_end <= t < evening_end:
            # Evening — deepening blue-grey, transitioning to night
            progress = (t - dusk_end) / (evening_end - dusk_end)
            alpha = int(120 + 30 * progress)
            # Blue-grey shifting to dark blue
            r_c = int(40 * (1.0 - progress) + 10 * progress)
            g_c = int(25 * (1.0 - progress) + 10 * progress)
            b_c = int(70 * (1.0 - progress) + 50 * progress)
            overlay_color = (r_c, g_c, b_c, alpha)
        else:
            # Night — dark blue overlay
            alpha = 150
            overlay_color = (10, 10, 50, alpha)

        self.night_surface.fill(overlay_color)

        # Player light circle (always present in darkness)
        if alpha > 20:
            px_cx, px_cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            light_radius = max(60, int(200 * (1.0 - alpha / 300.0)))
            # Radial gradient cutout for player
            for rad in range(light_radius, 0, -4):
                a = int(alpha * (rad / light_radius) ** 0.5)
                pygame.draw.circle(self.night_surface,
                                   (overlay_color[0], overlay_color[1],
                                    overlay_color[2], a),
                                   (px_cx, px_cy), rad)

            # Punch light through for torches, fireplaces, and forge fires
            if camera is not None and world is not None:
                self._punch_light_sources(camera, world, overlay_color, alpha)

        self.screen.blit(self.night_surface, (0, 0))

    def _draw_night_lighting(self, darkness: float):
        """Fallback night overlay using the old darkness float (0.0-1.0)."""
        if darkness <= 0:
            return
        alpha = int(darkness * 150)
        self.night_surface.fill((10, 10, 50, alpha))

        # Player light circle
        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
        light_radius = max(60, int(200 * (1 - darkness * 0.4)))
        for r in range(light_radius, 0, -4):
            a = int(alpha * (r / light_radius) ** 0.5)
            pygame.draw.circle(self.night_surface, (10, 10, 50, a), (cx, cy), r)

        self.screen.blit(self.night_surface, (0, 0))

    def _punch_light_sources(self, camera, world, overlay_color, alpha):
        """Cut warm light circles on the night overlay for fire/torch tiles
        and building windows (taverns, homes at night).

        Dynamic flickering: each light source randomly varies its radius
        by +/- 0.5 tiles (8px) and its alpha by +/- 10 each frame,
        creating a convincing firelight effect.
        """
        x0, y0, x1, y1 = camera.get_visible_tile_range()
        light_tiles = (FIREPLACE, FORGE_FIRE)
        window_tile = WINDOW

        oc_r, oc_g, oc_b = overlay_color[0], overlay_color[1], overlay_color[2]

        # Collect light sources for additive glow pass
        fire_lights = []

        for y in range(y0, y1):
            for x in range(x0, x1):
                if not (0 <= y < world.height and 0 <= x < world.width):
                    continue
                tile = world.tiles[y][x]
                if tile in light_tiles:
                    sx = x * TILE_SIZE - int(camera.x) + TILE_SIZE // 2
                    sy = y * TILE_SIZE - int(camera.y) + TILE_SIZE // 2
                    if -80 < sx < SCREEN_WIDTH + 80 and -80 < sy < SCREEN_HEIGHT + 80:
                        # Flickering: vary radius by +/- 8px, alpha by +/- 10
                        flicker_r = random.randint(-8, 8)
                        flicker_a = random.randint(-10, 10)
                        # FORGE_FIRE burns brighter and wider
                        base_radius = 64 if tile == FORGE_FIRE else 56
                        light_r = max(24, base_radius + flicker_r)
                        adj_alpha = max(0, min(alpha, alpha + flicker_a))

                        # Punch through darkness overlay (radial gradient)
                        for rad in range(light_r, 0, -3):
                            frac = rad / light_r
                            warm_r = int(oc_r * frac + 30 * (1 - frac))
                            warm_g = int(oc_g * frac + 15 * (1 - frac))
                            warm_b = int(oc_b * frac + 5 * (1 - frac))
                            a = int(adj_alpha * frac ** 0.6)
                            pygame.draw.circle(self.night_surface,
                                               (warm_r, warm_g, warm_b, a),
                                               (sx, sy), rad)

                        # Store for additive glow pass
                        fire_lights.append((sx, sy, light_r, adj_alpha, tile))

                elif tile == window_tile:
                    bfunc = self._building_function_cache.get((x, y), "")
                    if bfunc:
                        sx = x * TILE_SIZE - int(camera.x) + TILE_SIZE // 2
                        sy = y * TILE_SIZE - int(camera.y) + TILE_SIZE // 2
                        if -30 < sx < SCREEN_WIDTH + 30 and -30 < sy < SCREEN_HEIGHT + 30:
                            for rad in range(24, 0, -3):
                                frac = rad / 24.0
                                a = int(alpha * frac ** 0.8 * 0.6)
                                pygame.draw.circle(self.night_surface,
                                                   (oc_r, oc_g, oc_b, a),
                                                   (sx, sy), rad)

        # Additive glow pass — warm orange circles blitted on top of screen
        # This makes fire sources visibly brighten the scene, not just cut darkness
        for sx, sy, light_r, adj_alpha, tile in fire_lights:
            glow_radius = light_r + 8
            glow_size = glow_radius * 2
            glow = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
            # Radial gradient: warm orange at center fading to transparent
            glow_alpha_scale = min(1.0, adj_alpha / 100.0)
            for r in range(glow_radius, 0, -3):
                frac = r / glow_radius
                ga = int(35 * frac * glow_alpha_scale)
                # Forge fires are slightly more orange-white
                if tile == FORGE_FIRE:
                    gc = (255, 210, 120, ga)
                else:
                    gc = (255, 190, 90, ga)
                pygame.draw.circle(glow, gc, (glow_radius, glow_radius), r)
            self.screen.blit(glow, (sx - glow_radius, sy - glow_radius),
                             special_flags=pygame.BLEND_ADD)

    def draw_minimap(self, world: World, player: Player, npcs: list, creatures: list,
                     show_minimap: bool = False):
        """Draw minimap in corner. Off by default — toggle with N key."""
        if not show_minimap:
            return

        if self.minimap_surface is None:
            self.build_minimap(world)

        mm_w = min(180, world.width)
        mm_h = min(180, world.height)
        mm_x = SCREEN_WIDTH - mm_w - 10
        mm_y = 10

        # Background
        bg = pygame.Surface((mm_w + 4, mm_h + 4), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        self.screen.blit(bg, (mm_x - 2, mm_y - 2))

        # Draw terrain
        scaled = pygame.transform.scale(self.minimap_surface, (mm_w, mm_h))
        self.screen.blit(scaled, (mm_x, mm_y))

        # Throttle fog update — only every 30 frames
        if not hasattr(self, '_minimap_frame'):
            self._minimap_frame = 0
        self._minimap_frame += 1
        if self._minimap_frame % 30 == 0:
            self.update_minimap_explored(world)
        if self.minimap_explored:
            fog = pygame.transform.scale(self.minimap_explored, (mm_w, mm_h))
            self.screen.blit(fog, (mm_x, mm_y))

        # Scale factors
        sx_scale = mm_w / world.width
        sy_scale = mm_h / world.height

        # Draw structures
        for s in world.structures:
            dot_x = int(mm_x + s.x * sx_scale)
            dot_y = int(mm_y + s.y * sy_scale)
            if s.kind == "village":
                pygame.draw.circle(self.screen, (255, 200, 100), (dot_x, dot_y), 3)
            elif s.kind == "ruins":
                pygame.draw.circle(self.screen, (200, 100, 100), (dot_x, dot_y), 2)

        # Draw player
        px = int(mm_x + player.x * sx_scale)
        py = int(mm_y + player.y * sy_scale)
        pygame.draw.circle(self.screen, (100, 200, 255), (px, py), 3)
        pygame.draw.circle(self.screen, WHITE, (px, py), 3, 1)

        # Border
        pygame.draw.rect(self.screen, UI_BORDER, (mm_x - 2, mm_y - 2, mm_w + 4, mm_h + 4), 1)

    def draw_particles(self, camera: Camera, dt: float, player=None):
        """Update and draw particle effects (core + ambient effects)."""
        # Cap total particles for performance
        if len(self.particles) > 100:
            self.particles = self.particles[-100:]

        # Player position for distance culling
        px = getattr(player, 'x', 0) if player else 0
        py = getattr(player, 'y', 0) if player else 0

        # --- Core particles ---
        remaining = []
        for p in self.particles:
            p["life"] -= dt
            if p["life"] <= 0:
                continue

            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += p.get("gravity", 0) * dt

            sx, sy = camera.world_to_screen(p["x"], p["y"])
            # Skip off-screen particles
            if not (-20 < sx < SCREEN_WIDTH + 20 and -20 < sy < SCREEN_HEIGHT + 20):
                remaining.append(p)
                continue

            alpha = int(255 * (p["life"] / p["max_life"]))
            color = (*p["color"], min(255, alpha))

            size = max(1, int(p["size"] * (p["life"] / p["max_life"])))
            surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, color, (size, size), size)
            self.screen.blit(surf, (int(sx) - size, int(sy) - size))

            remaining.append(p)
        self.particles = remaining

        # --- Ambient visual effects (distance-culled) ---
        self._update_smoke_particles(camera, dt, px, py)
        self._update_birds(camera, dt)
        self._update_damage_popups(camera, dt)
        self._update_swing_arcs(camera, dt)
        self._update_leaf_particles(camera, dt, px, py)
        self._update_water_ripples(camera, dt, px, py)

    # ================================================================
    # WEATHER VISUAL EFFECTS
    # ================================================================

    def draw_weather(self, weather_condition: str, camera: Camera, dt: float):
        """Draw weather visual effects: rain, snow, fog, storm.

        Call after world render, before UI.
        """
        self._weather_condition = weather_condition
        self._fog_offset += dt * 0.5  # slow animation for fog

        if weather_condition == "clear" or weather_condition == "cloudy":
            # Cloudy: slight darkening
            if weather_condition == "cloudy":
                overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                overlay.fill((30, 30, 40, 25))
                self.screen.blit(overlay, (0, 0))
            self._weather_particles.clear()
            return

        if weather_condition in ("rain", "heavy_rain"):
            self._draw_rain(weather_condition, camera, dt)
        elif weather_condition == "snow":
            self._draw_snow(camera, dt)
        elif weather_condition == "fog":
            self._draw_fog(dt)
        elif weather_condition == "storm":
            self._draw_storm(camera, dt)

    def _draw_rain(self, intensity: str, camera: Camera, dt: float):
        """Draw rain streaks and darkening overlay."""
        # Darkening overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dark_alpha = 40 if intensity == "rain" else 70
        overlay.fill((20, 20, 35, dark_alpha))
        self.screen.blit(overlay, (0, 0))

        # Spawn rain particles
        target_count = 20 if intensity == "rain" else 60
        cam_ox = camera.x * TILE_SIZE * 0.1  # slight parallax
        cam_oy = camera.y * TILE_SIZE * 0.1

        while len(self._weather_particles) < target_count:
            self._weather_particles.append({
                "x": random.uniform(0, SCREEN_WIDTH),
                "y": random.uniform(-20, 0),
                "vx": random.uniform(-1.5, -0.5),  # diagonal
                "vy": random.uniform(8.0, 14.0),
                "length": random.randint(6, 14),
                "type": "rain",
            })

        # Update and draw
        alive = []
        for p in self._weather_particles:
            if p["type"] != "rain":
                alive.append(p)
                continue
            p["x"] += (p["vx"] - cam_ox * 0.01) * dt * 60
            p["y"] += p["vy"] * dt * 60
            if p["y"] > SCREEN_HEIGHT + 10:
                # Respawn at top
                p["x"] = random.uniform(0, SCREEN_WIDTH)
                p["y"] = random.uniform(-20, 0)

            # Draw streak
            sx, sy = int(p["x"]), int(p["y"])
            ex = sx + int(p["vx"] * p["length"] * 0.3)
            ey = sy + int(p["length"])
            alpha = random.randint(100, 180)
            color = (140, 150, 180, alpha)
            streak_surf = pygame.Surface((abs(ex - sx) + 4, abs(ey - sy) + 4), pygame.SRCALPHA)
            pygame.draw.line(streak_surf, color,
                             (2, 0), (2 + ex - sx, ey - sy), 1)
            self.screen.blit(streak_surf, (min(sx, ex) - 2, min(sy, ey) - 2))
            alive.append(p)
        self._weather_particles = alive

    def _draw_snow(self, camera: Camera, dt: float):
        """Draw drifting snow particles with wobble."""
        # Light white overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((220, 225, 235, 15))
        self.screen.blit(overlay, (0, 0))

        target_count = random.randint(30, 50)
        while len(self._weather_particles) < target_count:
            self._weather_particles.append({
                "x": random.uniform(0, SCREEN_WIDTH),
                "y": random.uniform(-10, 0),
                "vx": random.uniform(-0.3, 0.3),
                "vy": random.uniform(1.0, 2.5),
                "wobble": random.uniform(0, 6.28),
                "size": random.randint(2, 4),
                "type": "snow",
            })

        alive = []
        for p in self._weather_particles:
            if p["type"] != "snow":
                alive.append(p)
                continue
            p["wobble"] += dt * 2.0
            p["x"] += (p["vx"] + math.sin(p["wobble"]) * 0.5) * dt * 60
            p["y"] += p["vy"] * dt * 60
            if p["y"] > SCREEN_HEIGHT + 10:
                p["x"] = random.uniform(0, SCREEN_WIDTH)
                p["y"] = random.uniform(-10, 0)

            sx, sy = int(p["x"]), int(p["y"])
            alpha = random.randint(160, 230)
            s = p["size"]
            snow_surf = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
            pygame.draw.circle(snow_surf, (240, 240, 250, alpha), (s, s), s)
            self.screen.blit(snow_surf, (sx - s, sy - s))
            alive.append(p)
        self._weather_particles = alive

    def _draw_fog(self, dt: float):
        """Draw semi-transparent wavy fog overlay."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        # Wavy fog using horizontal bands with varying alpha
        band_h = 40
        for band_y in range(0, SCREEN_HEIGHT, band_h):
            # Vary alpha with a sine wave for waviness
            wave = math.sin(self._fog_offset + band_y * 0.02) * 0.5 + 0.5
            alpha = int(80 + wave * 40)  # 80-120 range
            alpha = max(0, min(255, alpha))
            band_color = (200, 200, 210, alpha)
            band_rect = pygame.Rect(0, band_y, SCREEN_WIDTH, band_h)
            overlay.fill(band_color, band_rect)
        self.screen.blit(overlay, (0, 0))
        self._weather_particles.clear()

    def _draw_storm(self, camera: Camera, dt: float):
        """Draw heavy rain + lightning + screen shake."""
        # Heavy rain base
        self._draw_rain("heavy_rain", camera, dt)

        # Lightning timer
        self._lightning_timer += dt
        if self._lightning_flash > 0:
            # Flash effect
            self._lightning_flash -= dt
            flash_alpha = int(min(200, self._lightning_flash * 400))
            if flash_alpha > 0:
                flash_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                flash_surf.fill((255, 255, 255, flash_alpha))
                self.screen.blit(flash_surf, (0, 0))
        elif self._lightning_timer > random.uniform(5.0, 10.0):
            # Trigger lightning
            self._lightning_timer = 0.0
            self._lightning_flash = 0.15  # 150ms flash
            self._thunder_shake = 0.3    # 300ms shake

        # Screen shake (applied as a slight offset to final blit)
        if self._thunder_shake > 0:
            self._thunder_shake -= dt
            shake_x = random.randint(-2, 2)
            shake_y = random.randint(-1, 1)
            # Move the entire screen slightly
            temp = self.screen.copy()
            self.screen.fill((0, 0, 0))
            self.screen.blit(temp, (shake_x, shake_y))

    # ================================================================
    # BUILDING FUNCTION CACHE — maps tiles to building purpose
    # ================================================================

    def _build_building_function_cache(self, world):
        """Cache which building function each tile belongs to (tavern, temple, etc.)."""
        if self._building_function_built:
            return
        self._building_function_built = True

        if hasattr(world, 'plan'):
            for sp in world.plan.settlements:
                for bld in sp.buildings:
                    bx, by = bld['x'], bld['y']
                    bw, bh = bld['w'], bld['h']
                    bname = bld.get('name', '')
                    for ty in range(by, by + bh):
                        for tx in range(bx, bx + bw):
                            self._building_function_cache[(tx, ty)] = bname

        # Also build smoke sources list
        self._smoke_sources = []
        if hasattr(world, 'plan'):
            for sp in world.plan.settlements:
                for bld in sp.buildings:
                    bname = bld.get('name', '').lower()
                    if any(k in bname for k in ('blacksmith', 'forge', 'smith',
                                                  'baker', 'bakery', 'brew',
                                                  'kitchen', 'tavern', 'inn')):
                        # Chimney position: center-back of building
                        cx = bld['x'] + bld['w'] // 2
                        cy = bld['y']
                        self._smoke_sources.append((cx, cy, bname))

    # ================================================================
    # SMOKE PARTICLES — from blacksmith/bakery/brewery chimneys
    # ================================================================

    def _update_smoke_particles(self, camera: Camera, dt: float,
                                player_x: float = 0, player_y: float = 0):
        """Emit and draw smoke particles from chimneys."""
        self._smoke_timer += dt
        # Spawn new smoke every 0.5s (throttled for performance)
        if self._smoke_timer >= 0.5:
            self._smoke_timer = 0.0
            x0, y0, x1, y1 = camera.get_visible_tile_range()
            for sx_src, sy_src, bname in self._smoke_sources:
                # Skip sources more than 50 tiles from player
                if abs(sx_src - player_x) > 50 or abs(sy_src - player_y) > 50:
                    continue
                if x0 - 2 <= sx_src <= x1 + 2 and y0 - 2 <= sy_src <= y1 + 2:
                    # Dark smoke for blacksmith, lighter for bakery
                    if 'blacksmith' in bname or 'forge' in bname or 'smith' in bname:
                        smoke_color = (60, 55, 50)
                    else:
                        smoke_color = (160, 155, 150)
                    self._smoke_particles.append({
                        "x": sx_src + random.uniform(-0.2, 0.2),
                        "y": sy_src - 0.5,
                        "vx": random.uniform(-0.15, 0.15),
                        "vy": -random.uniform(0.5, 1.2),
                        "color": smoke_color,
                        "size": random.uniform(2, 4),
                        "life": random.uniform(1.5, 3.0),
                        "max_life": 3.0,
                    })

        # Update and draw
        alive = []
        for p in self._smoke_particles:
            p["life"] -= dt
            if p["life"] <= 0:
                continue
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            # Smoke drifts and expands
            p["vx"] += random.uniform(-0.1, 0.1) * dt
            p["size"] += dt * 1.5  # expand over time

            sx, sy = camera.world_to_screen(p["x"], p["y"])
            if -20 < sx < SCREEN_WIDTH + 20 and -20 < sy < SCREEN_HEIGHT + 20:
                alpha = int(120 * (p["life"] / p["max_life"]))
                size = max(1, int(p["size"]))
                smoke_surf = pygame.Surface((size * 2 + 2, size * 2 + 2), pygame.SRCALPHA)
                c = p["color"]
                pygame.draw.circle(smoke_surf, (c[0], c[1], c[2], alpha),
                                   (size + 1, size + 1), size)
                self.screen.blit(smoke_surf, (int(sx) - size - 1, int(sy) - size - 1))
            alive.append(p)
        self._smoke_particles = alive[-80:]  # cap at 80 particles

    # ================================================================
    # AMBIENT BIRDS — small dark dots flying across the sky
    # ================================================================

    def _update_birds(self, camera: Camera, dt: float):
        """Spawn and draw ambient birds flying in the sky."""
        self._bird_timer += dt
        # Spawn a bird every 2s (throttled)
        if self._bird_timer >= 2.0 and len(self._birds) < 5:
            self._bird_timer = 0.0
            # Random screen position, flying left-to-right or right-to-left
            direction = random.choice([-1, 1])
            start_x = -20 if direction > 0 else SCREEN_WIDTH + 20
            self._birds.append({
                "sx": float(start_x),
                "sy": random.uniform(20, SCREEN_HEIGHT * 0.3),
                "vx": direction * random.uniform(40, 80),
                "vy": random.uniform(-5, 5),
                "wing_phase": random.uniform(0, 6.28),
                "life": random.uniform(8, 15),
            })

        alive = []
        for b in self._birds:
            b["life"] -= dt
            if b["life"] <= 0:
                continue
            b["sx"] += b["vx"] * dt
            b["sy"] += b["vy"] * dt
            b["wing_phase"] += dt * 8

            bx, by = int(b["sx"]), int(b["sy"])
            if -30 < bx < SCREEN_WIDTH + 30 and -30 < by < SCREEN_HEIGHT + 30:
                # Bird body (small dark dot)
                pygame.draw.circle(self.screen, (30, 25, 20), (bx, by), 1)
                # Wings (V-shape that flaps)
                wing_off = int(math.sin(b["wing_phase"]) * 2)
                pygame.draw.line(self.screen, (30, 25, 20),
                                 (bx - 3, by + wing_off), (bx, by), 1)
                pygame.draw.line(self.screen, (30, 25, 20),
                                 (bx + 3, by + wing_off), (bx, by), 1)
            alive.append(b)
        self._birds = alive

    # ================================================================
    # DAMAGE NUMBER POPUPS — float up and fade
    # ================================================================

    def spawn_damage_popup(self, x: float, y: float, damage: int,
                           color=(255, 60, 60)):
        """Spawn a floating damage number that rises and fades."""
        self._damage_popups.append({
            "x": x, "y": y,
            "damage": damage,
            "color": color,
            "life": 1.2,
            "max_life": 1.2,
            "vy": -2.5,
        })

    def _update_damage_popups(self, camera: Camera, dt: float):
        """Draw floating damage numbers."""
        alive = []
        for p in self._damage_popups:
            p["life"] -= dt
            if p["life"] <= 0:
                continue
            p["y"] += p["vy"] * dt
            p["vy"] *= 0.96  # decelerate

            sx, sy = camera.world_to_screen(p["x"], p["y"])
            if -50 < sx < SCREEN_WIDTH + 50 and -50 < sy < SCREEN_HEIGHT + 50:
                alpha = min(255, int(255 * (p["life"] / p["max_life"])))
                # Render damage text
                txt = str(p["damage"])
                # Scale: larger for bigger hits
                font = self.font_md if p["damage"] >= 20 else self.font_sm
                text_surf = font.render(txt, True, p["color"])
                # Create alpha surface
                alpha_surf = pygame.Surface(text_surf.get_size(), pygame.SRCALPHA)
                alpha_surf.blit(text_surf, (0, 0))
                alpha_surf.set_alpha(alpha)
                self.screen.blit(alpha_surf,
                                 (int(sx) - text_surf.get_width() // 2,
                                  int(sy) - text_surf.get_height() // 2))
            alive.append(p)
        self._damage_popups = alive

    # ================================================================
    # WEAPON SWING ARCS — colored arc when attacking
    # ================================================================

    def spawn_swing_arc(self, x: float, y: float, fx: float, fy: float,
                        color=(220, 220, 100)):
        """Spawn a weapon swing arc effect."""
        self._swing_arcs.append({
            "x": x, "y": y,
            "fx": fx, "fy": fy,
            "color": color,
            "life": 0.25,
            "max_life": 0.25,
        })

    def _update_swing_arcs(self, camera: Camera, dt: float):
        """Draw weapon swing arcs."""
        alive = []
        for arc in self._swing_arcs:
            arc["life"] -= dt
            if arc["life"] <= 0:
                continue
            sx, sy = camera.world_to_screen(arc["x"], arc["y"])
            if -50 < sx < SCREEN_WIDTH + 50 and -50 < sy < SCREEN_HEIGHT + 50:
                progress = 1.0 - (arc["life"] / arc["max_life"])
                alpha = int(200 * (1.0 - progress))
                # Draw arc sweep
                base_angle = math.atan2(arc["fy"], arc["fx"])
                arc_start = base_angle - 0.8 + progress * 1.6
                arc_end = arc_start + 0.8
                radius = int(TILE_SIZE * 1.5)
                arc_surf = pygame.Surface((radius * 3, radius * 3), pygame.SRCALPHA)
                c = arc["color"]
                # Draw arc as connected line segments
                pts = []
                for i in range(8):
                    t = i / 7.0
                    a = arc_start + t * (arc_end - arc_start)
                    px = radius * 1.5 + math.cos(a) * radius
                    py = radius * 1.5 + math.sin(a) * radius
                    pts.append((int(px), int(py)))
                if len(pts) >= 2:
                    pygame.draw.lines(arc_surf, (c[0], c[1], c[2], alpha),
                                      False, pts, 2)
                self.screen.blit(arc_surf,
                                 (int(sx) - int(radius * 1.5),
                                  int(sy) - int(radius * 1.5)))
            alive.append(arc)
        self._swing_arcs = alive

    # ================================================================
    # BLOOD SPLATTER — on-hit particles
    # ================================================================

    def spawn_blood_splatter(self, x: float, y: float):
        """Spawn blood splatter particles at hit location."""
        for _ in range(6):
            angle = math.radians(random.randint(0, 360))
            speed = random.uniform(0.8, 3.0)
            self.particles.append({
                "x": x + random.uniform(-0.1, 0.1),
                "y": y + random.uniform(-0.1, 0.1),
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed - 1.5,
                "gravity": 6,
                "color": (random.randint(140, 200), 20, 20),
                "size": random.randint(1, 3),
                "life": random.uniform(0.4, 1.0),
                "max_life": 1.0,
            })

    # ================================================================
    # SHIELD BLOCK FLASH
    # ================================================================

    def spawn_shield_flash(self, x: float, y: float):
        """Spawn a bright shield block flash."""
        self.particles.append({
            "x": x, "y": y,
            "vx": 0, "vy": 0,
            "gravity": 0,
            "color": (200, 220, 255),
            "size": 8,
            "life": 0.15,
            "max_life": 0.15,
        })
        # Sparks
        for _ in range(4):
            angle = math.radians(random.randint(0, 360))
            speed = random.uniform(2, 5)
            self.particles.append({
                "x": x, "y": y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "gravity": 3,
                "color": (220, 230, 255),
                "size": 1,
                "life": random.uniform(0.1, 0.3),
                "max_life": 0.3,
            })

    # ================================================================
    # DEATH ANIMATION — entity fades to gray
    # ================================================================

    def spawn_death_effect(self, x: float, y: float):
        """Spawn death effect particles (gray dust rising)."""
        for _ in range(10):
            angle = math.radians(random.randint(0, 360))
            speed = random.uniform(0.3, 1.5)
            gray = random.randint(100, 180)
            self.particles.append({
                "x": x + random.uniform(-0.3, 0.3),
                "y": y + random.uniform(-0.3, 0.3),
                "vx": math.cos(angle) * speed,
                "vy": -random.uniform(0.5, 2.0),
                "gravity": -0.5,  # float upward
                "color": (gray, gray, gray),
                "size": random.randint(2, 4),
                "life": random.uniform(0.8, 1.5),
                "max_life": 1.5,
            })

    # ================================================================
    # LEAF PARTICLES — blowing in forest areas
    # ================================================================

    def _update_leaf_particles(self, camera: Camera, dt: float,
                               player_x: float = 0, player_y: float = 0):
        """Spawn and draw leaf particles in forest areas (season-aware).

        Spring/Summer: green leaves, normal rate.
        Autumn: orange/red/brown falling leaves, triple spawn rate.
        Winter: no new leaf spawns (bare trees).
        """
        season = self._current_season

        # Winter: no leaf spawns, just draw remaining ones
        if season != "winter":
            self._leaf_timer += dt

            # Autumn: spawn faster and more leaves
            spawn_interval = 0.35 if season == "autumn" else 1.0
            max_leaves = 40 if season == "autumn" else 15

            if self._leaf_timer >= spawn_interval and len(self._leaf_particles) < max_leaves:
                self._leaf_timer = 0.0
                sx = random.uniform(0, SCREEN_WIDTH)
                sy = random.uniform(0, SCREEN_HEIGHT * 0.6)

                # Season-dependent leaf colors
                if season == "autumn":
                    leaf_color = random.choice([
                        (200, 100, 30), (220, 160, 40), (180, 60, 30),
                        (190, 130, 40), (160, 80, 25), (210, 140, 30),
                        (170, 50, 20), (230, 180, 50),
                    ])
                elif season == "spring":
                    leaf_color = random.choice([
                        (100, 180, 60), (120, 170, 50), (90, 160, 55),
                        (110, 190, 65), (80, 150, 50),
                    ])
                else:  # summer
                    leaf_color = random.choice([
                        (80, 140, 50), (100, 150, 40), (120, 130, 30),
                        (90, 120, 45), (110, 160, 50),
                    ])

                # Autumn leaves fall faster and drift more
                vx = random.uniform(20, 55) if season == "autumn" else random.uniform(15, 40)
                vy = random.uniform(15, 35) if season == "autumn" else random.uniform(8, 20)

                self._leaf_particles.append({
                    "sx": sx, "sy": sy,
                    "vx": vx, "vy": vy,
                    "wobble_phase": random.uniform(0, 6.28),
                    "color": leaf_color,
                    "life": random.uniform(3, 6),
                    "size": random.randint(1, 3 if season == "autumn" else 2),
                })

        alive = []
        for leaf in self._leaf_particles:
            leaf["life"] -= dt
            if leaf["life"] <= 0:
                continue
            leaf["wobble_phase"] += dt * 4
            leaf["sx"] += leaf["vx"] * dt
            leaf["sy"] += leaf["vy"] * dt + math.sin(leaf["wobble_phase"]) * 0.5

            lx, ly = int(leaf["sx"]), int(leaf["sy"])
            if 0 <= lx < SCREEN_WIDTH and 0 <= ly < SCREEN_HEIGHT:
                pygame.draw.circle(self.screen, leaf["color"], (lx, ly), leaf["size"])
            alive.append(leaf)
        self._leaf_particles = alive

    # ================================================================
    # WATER RIPPLE EFFECTS — animated on water tiles
    # ================================================================

    def _update_water_ripples(self, camera: Camera, dt: float,
                              player_x: float = 0, player_y: float = 0):
        """Draw animated ripple highlights on visible water tiles."""
        self._ripple_timer += dt
        if self._ripple_timer < 0.3:
            return
        self._ripple_timer = 0.0
        self._ripple_frame += 1
        # Only draw a few ripples per frame (performance)
        x0, y0, x1, y1 = camera.get_visible_tile_range()
        count = 0
        frame = self._ripple_frame
        for y in range(y0, y1):
            for x in range(x0, x1):
                # Use hash to deterministically pick which tiles get ripples
                h = (x * 7 + y * 13 + frame) % 30
                if h != 0:
                    continue
                count += 1
                if count > 8:
                    return
                sx = x * TILE_SIZE - int(camera.x)
                sy = y * TILE_SIZE - int(camera.y)
                if 0 <= sx < SCREEN_WIDTH and 0 <= sy < SCREEN_HEIGHT:
                    # Small ripple circle
                    ripple_r = 2 + (frame % 3)
                    ripple_surf = pygame.Surface((ripple_r * 2 + 2, ripple_r * 2 + 2),
                                                  pygame.SRCALPHA)
                    pygame.draw.circle(ripple_surf, (180, 210, 240, 40),
                                       (ripple_r + 1, ripple_r + 1), ripple_r, 1)
                    self.screen.blit(ripple_surf,
                                     (sx + TILE_SIZE // 2 - ripple_r - 1,
                                      sy + TILE_SIZE // 2 - ripple_r - 1))

    # ================================================================
    # SPEECH / EMOTION ICONS above NPCs
    # ================================================================

    def _draw_npc_emotion_icon(self, npc, sx: int, sy: int, bh: int, s: int):
        """Draw emotion/interaction icons above NPC heads."""
        icon_y = int(sy) - bh // 2 - s * 4

        # Mood-based emotion icons
        npc_mood = getattr(npc, 'mood', 0)
        if npc_mood > 0.5:
            # Happy — small heart
            hx, hy = int(sx) - 3, icon_y
            pygame.draw.polygon(self.screen, (220, 80, 80), [
                (hx + 3, hy + 2), (hx, hy), (hx + 1, hy - 1),
                (hx + 3, hy + 1), (hx + 5, hy - 1), (hx + 6, hy),
            ])
        elif npc_mood < -0.5:
            # Angry — small exclamation with red tint
            pygame.draw.rect(self.screen, (220, 60, 40),
                             (int(sx) - 1, icon_y - 2, 3, 5))
            pygame.draw.rect(self.screen, (220, 60, 40),
                             (int(sx) - 1, icon_y + 4, 3, 2))

        # Trade icon when trading
        act = getattr(npc, 'current_action', '')
        if act == 'trading':
            # Gold coin icon
            pygame.draw.circle(self.screen, (220, 200, 60),
                               (int(sx) + 8, icon_y), 3)
            pygame.draw.circle(self.screen, (180, 160, 40),
                               (int(sx) + 8, icon_y), 3, 1)

        # Talking ellipsis
        if act == 'talking' or getattr(npc, '_in_conversation', False):
            # Speech bubble with dots
            bx, by = int(sx) + 8, icon_y - 2
            pygame.draw.ellipse(self.screen, (240, 240, 240),
                                (bx - 6, by - 3, 12, 8))
            pygame.draw.ellipse(self.screen, (60, 60, 60),
                                (bx - 6, by - 3, 12, 8), 1)
            # Three dots
            for i in range(3):
                pygame.draw.circle(self.screen, (60, 60, 60),
                                   (bx - 3 + i * 3, by + 1), 1)

    # ================================================================
    # FOOTSTEP DUST — when player moves on dry terrain
    # ================================================================

    def spawn_footstep_dust(self, x: float, y: float):
        """Spawn small dust cloud at player feet."""
        for _ in range(2):
            self.particles.append({
                "x": x + random.uniform(-0.2, 0.2),
                "y": y + random.uniform(0, 0.3),
                "vx": random.uniform(-0.3, 0.3),
                "vy": random.uniform(-0.3, 0),
                "gravity": 0,
                "color": (180, 160, 130),
                "size": random.randint(1, 2),
                "life": random.uniform(0.2, 0.5),
                "max_life": 0.5,
            })

    # ================================================================
    # CONSTRUCTION SCAFFOLDING — overlay for buildings under construction
    # ================================================================

    def draw_construction_scaffolding(self, construction_sys, camera):
        """Draw scaffolding overlay and progress text for active construction projects.

        Renders a semi-transparent brown cross-hatch pattern on tiles where
        construction is in progress, plus a floating progress percentage.
        """
        if construction_sys is None:
            return

        # Tile-level projects (roads, houses, walls)
        for project in construction_sys.projects:
            if project.completed:
                continue
            px, py = project.x, project.y
            sx = px * TILE_SIZE - int(camera.x)
            sy = py * TILE_SIZE - int(camera.y)

            # Determine build footprint based on project kind
            if project.kind == "wooden_house":
                w, h = 5, 4
            elif project.kind == "new_settlement":
                w, h = 8, 8
            else:
                w, h = 1, 1

            # Check if any part is visible on screen
            ex = sx + w * TILE_SIZE
            ey = sy + h * TILE_SIZE
            if ex < -TILE_SIZE or sx > SCREEN_WIDTH + TILE_SIZE:
                continue
            if ey < -TILE_SIZE or sy > SCREEN_HEIGHT + TILE_SIZE:
                continue

            # Draw scaffolding overlay on each tile in the footprint
            for dy in range(h):
                for dx in range(w):
                    tx = sx + dx * TILE_SIZE
                    ty = sy + dy * TILE_SIZE
                    if tx < -TILE_SIZE or tx > SCREEN_WIDTH:
                        continue
                    if ty < -TILE_SIZE or ty > SCREEN_HEIGHT:
                        continue
                    self._draw_scaffolding_tile(tx, ty)

            # Progress percentage floating above the construction
            pct = int(project.progress * 100)
            cx = sx + (w * TILE_SIZE) // 2
            cy = sy - 8
            pct_text = f"{pct}%"
            color = (255, 220, 100) if pct < 100 else (100, 255, 100)
            txt_surf = self.font_sm.render(pct_text, True, color)
            tw = txt_surf.get_width()
            # Background for readability
            bg = pygame.Surface((tw + 6, 14), pygame.SRCALPHA)
            bg.fill((30, 20, 10, 180))
            self.screen.blit(bg, (cx - tw // 2 - 3, cy - 1))
            self.screen.blit(txt_surf, (cx - tw // 2, cy))

    def _draw_scaffolding_tile(self, sx, sy):
        """Draw a brown cross-hatch scaffolding pattern on a single tile."""
        ts = TILE_SIZE
        # Semi-transparent brown overlay
        overlay = pygame.Surface((ts, ts), pygame.SRCALPHA)
        overlay.fill((120, 80, 40, 50))
        # Cross-hatch lines (brown wooden frame)
        line_color = (140, 95, 50, 140)
        # Diagonal lines
        pygame.draw.line(overlay, line_color, (0, 0), (ts - 1, ts - 1), 1)
        pygame.draw.line(overlay, line_color, (ts - 1, 0), (0, ts - 1), 1)
        # Border frame
        pygame.draw.rect(overlay, (100, 70, 35, 120), (0, 0, ts, ts), 1)
        # Horizontal brace at midpoint
        pygame.draw.line(overlay, line_color, (0, ts // 2), (ts - 1, ts // 2), 1)
        self.screen.blit(overlay, (sx, sy))

    # ================================================================
    # SETTLEMENT OVERLAY EFFECTS — walls, awnings, farm patterns
    # ================================================================

    def draw_settlement_overlays(self, world, camera: Camera, player=None):
        """Draw settlement-specific overlay effects: market awnings, farm rows,
        town walls/gates, flickering tavern lights, and cobblestone roads."""
        if not hasattr(world, 'plan'):
            return

        # Build function cache on first call
        if not self._building_function_built:
            self._build_building_function_cache(world)

        x0, y0, x1, y1 = camera.get_visible_tile_range()
        time_norm = getattr(world, '_time_normalized', 0.35)
        is_night = time_norm > NIGHT_START or time_norm < DAWN_START
        ticks = pygame.time.get_ticks()

        for sp in world.plan.settlements:
            # Skip if settlement is far from visible area
            if (sp.x + sp.radius < x0 or sp.x - sp.radius > x1 or
                    sp.y + sp.radius < y0 or sp.y - sp.radius > y1):
                continue

            for bld in sp.buildings:
                bx, by = bld['x'], bld['y']
                bw, bh = bld['w'], bld['h']
                bname = bld.get('name', '').lower()

                # Skip if not visible
                if bx + bw < x0 or bx > x1 or by + bh < y0 or by > y1:
                    continue

                # Inside player's building? Skip overlays
                player_rect = getattr(player, '_current_building_rect', None) if player else None
                if player_rect and player_rect == (bx, by, bw, bh):
                    continue

                # --- MARKET STALL AWNINGS ---
                if 'market' in bname or 'shop' in bname or 'stall' in bname:
                    sx = bx * TILE_SIZE - int(camera.x)
                    sy = by * TILE_SIZE - int(camera.y)
                    # Colored awning triangle on the south side
                    awning_colors = [
                        (180, 60, 50), (50, 120, 180), (180, 150, 40),
                        (50, 150, 80), (160, 80, 140),
                    ]
                    ac = awning_colors[(bx + by) % len(awning_colors)]
                    aw = bw * TILE_SIZE
                    # Triangle awning hanging off front
                    pts = [
                        (sx, sy + bh * TILE_SIZE),
                        (sx + aw, sy + bh * TILE_SIZE),
                        (sx + aw // 2, sy + bh * TILE_SIZE + 5),
                    ]
                    awning_surf = pygame.Surface((aw + 2, 8), pygame.SRCALPHA)
                    local_pts = [
                        (0, 0), (aw, 0), (aw // 2, 5),
                    ]
                    pygame.draw.polygon(awning_surf, (*ac, 180), local_pts)
                    # Stripe pattern
                    stripe_c = (min(255, ac[0] + 40), min(255, ac[1] + 40),
                                min(255, ac[2] + 40), 100)
                    for i in range(0, aw, 4):
                        if i % 8 < 4:
                            pygame.draw.line(awning_surf, stripe_c,
                                             (i, 0), (i, 5))
                    self.screen.blit(awning_surf,
                                     (sx, sy + bh * TILE_SIZE))

                # --- TAVERN / INN FLICKERING WINDOWS AT NIGHT ---
                if is_night and ('tavern' in bname or 'inn' in bname):
                    # Warm glow from windows
                    flicker = 180 + int(math.sin(ticks * 0.008 + bx) * 30)
                    glow_color = (flicker, int(flicker * 0.6), 20, 50)
                    glow_surf = pygame.Surface((bw * TILE_SIZE, bh * TILE_SIZE),
                                                pygame.SRCALPHA)
                    glow_surf.fill(glow_color)
                    sx = bx * TILE_SIZE - int(camera.x)
                    sy = by * TILE_SIZE - int(camera.y)
                    self.screen.blit(glow_surf, (sx, sy))

            # --- TOWN/CITY WALLS (not hamlets/villages) ---
            if sp.kind in ('town', 'city', 'castle'):
                self._draw_settlement_walls(sp, camera, x0, y0, x1, y1)

    def _draw_settlement_walls(self, settlement, camera: Camera,
                                x0: int, y0: int, x1: int, y1: int):
        """Draw walls/gates around towns and cities."""
        cx, cy = settlement.x, settlement.y
        r = settlement.radius
        wall_color = (120, 110, 95) if settlement.kind == 'town' else (95, 90, 85)

        # Draw wall segments around perimeter
        # Cardinal gate positions
        gate_positions = [
            (cx, cy - r), (cx, cy + r),  # north, south
            (cx - r, cy), (cx + r, cy),  # west, east
        ]

        # Draw wall tiles along perimeter (octagonal approximation)
        for angle_deg in range(0, 360, 4):
            angle = math.radians(angle_deg)
            wx = int(cx + math.cos(angle) * r)
            wy = int(cy + math.sin(angle) * r)

            if not (x0 <= wx <= x1 and y0 <= wy <= y1):
                continue

            sx = wx * TILE_SIZE - int(camera.x)
            sy = wy * TILE_SIZE - int(camera.y)

            if not (0 <= sx < SCREEN_WIDTH and 0 <= sy < SCREEN_HEIGHT):
                continue

            # Check if this is a gate position (near a cardinal point)
            is_gate = False
            for gx, gy in gate_positions:
                if abs(wx - gx) + abs(wy - gy) < 3:
                    is_gate = True
                    break

            if is_gate:
                # Gate: darker opening
                gate_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                pygame.draw.rect(gate_surf, (60, 50, 40, 160),
                                 (2, 0, TILE_SIZE - 4, TILE_SIZE))
                pygame.draw.rect(gate_surf, (*wall_color, 200),
                                 (0, 0, 2, TILE_SIZE))
                pygame.draw.rect(gate_surf, (*wall_color, 200),
                                 (TILE_SIZE - 2, 0, 2, TILE_SIZE))
                self.screen.blit(gate_surf, (sx, sy))
            else:
                # Wall segment
                wall_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                pygame.draw.rect(wall_surf, (*wall_color, 140),
                                 (0, 0, TILE_SIZE, TILE_SIZE))
                # Battlements on top
                for bx in range(0, TILE_SIZE, 4):
                    if bx % 8 < 4:
                        pygame.draw.rect(wall_surf, (*wall_color, 180),
                                         (bx, 0, 3, 3))
                self.screen.blit(wall_surf, (sx, sy))

    # ================================================================
    # FARM FIELD PATTERNS — crop rows with growth stages
    # ================================================================

    def draw_farm_overlays(self, world, camera: Camera):
        """Draw crop row patterns on farmland tiles for visual variety."""
        x0, y0, x1, y1 = camera.get_visible_tile_range()
        ticks = pygame.time.get_ticks()

        for y in range(y0, y1):
            for x in range(x0, x1):
                if 0 <= y < world.height and 0 <= x < world.width:
                    tile = world.tiles[y][x]
                    if tile not in (FARMLAND, WHEAT_FIELD, VEGETABLE_PLOT,
                                    FLAX_FIELD, TILLED_SOIL):
                        continue

                    sx = x * TILE_SIZE - int(camera.x)
                    sy = y * TILE_SIZE - int(camera.y)
                    if not (0 <= sx < SCREEN_WIDTH and 0 <= sy < SCREEN_HEIGHT):
                        continue

                    # Growth stage based on position hash (simulates different planting times)
                    stage = ((x * 17 + y * 31) % 4)  # 0-3
                    if tile == WHEAT_FIELD:
                        # Swaying wheat tops
                        sway = int(math.sin(ticks * 0.002 + x * 0.5) * 1)
                        crop_colors = [
                            (160, 140, 50), (180, 160, 60),
                            (200, 180, 70), (210, 190, 80),
                        ]
                        cc = crop_colors[stage]
                        farm_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                        for i in range(2, TILE_SIZE - 1, 3):
                            h = 3 + stage * 2
                            pygame.draw.line(farm_surf, (*cc, 120),
                                             (i + sway, TILE_SIZE - h),
                                             (i, TILE_SIZE), 1)
                        self.screen.blit(farm_surf, (sx, sy))

    # ================================================================
    # ORIGINAL PARTICLE SPAWNERS (preserved)
    # ================================================================

    def spawn_hit_particles(self, x: float, y: float, color=(255, 50, 50)):
        """Spawn particles at a hit location."""
        for _ in range(8):
            angle = math.radians(random.randint(0, 360))
            speed = random.uniform(1, 4)
            self.particles.append({
                "x": x, "y": y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed - 2,
                "gravity": 5,
                "color": color,
                "size": random.randint(2, 4),
                "life": random.uniform(0.3, 0.8),
                "max_life": 0.8,
            })
        # Also spawn blood splatter and damage popup
        self.spawn_blood_splatter(x, y)

    def spawn_xp_particles(self, x: float, y: float):
        """Spawn gold/XP particles."""
        for _ in range(5):
            self.particles.append({
                "x": x + random.uniform(-0.3, 0.3),
                "y": y + random.uniform(-0.3, 0.3),
                "vx": random.uniform(-0.5, 0.5),
                "vy": -random.uniform(1, 3),
                "gravity": 0,
                "color": (255, 220, 50),
                "size": random.randint(2, 3),
                "life": random.uniform(0.5, 1.0),
                "max_life": 1.0,
            })

    # ================================================================
    # COMBAT POLISH: SCREEN SHAKE
    # ================================================================

    def trigger_screen_shake(self, damage: int):
        """Trigger screen shake proportional to damage dealt.

        Only triggers on big hits (damage > 20). Intensity scales
        with damage, capped at a reasonable maximum.
        """
        if damage <= 20:
            return
        intensity = min(8.0, damage * 0.15)
        # Don't override a stronger shake already in progress
        if intensity > self._screen_shake_intensity:
            self._screen_shake_intensity = intensity
            self._screen_shake_duration = 0.3
            self._screen_shake_timer = 0.3

    def get_screen_shake_offset(self, dt: float) -> Tuple[int, int]:
        """Compute the current screen shake offset and decay it.

        Call once per frame in the draw loop. Returns (dx, dy) pixel offsets
        to apply to all rendering.
        """
        if self._screen_shake_timer <= 0:
            self._screen_shake_intensity = 0.0
            return (0, 0)

        self._screen_shake_timer -= dt
        # Decay intensity linearly over the duration
        progress = max(0.0, self._screen_shake_timer / self._screen_shake_duration)
        current_intensity = self._screen_shake_intensity * progress
        dx = int(random.uniform(-current_intensity, current_intensity))
        dy = int(random.uniform(-current_intensity, current_intensity))
        return (dx, dy)

    # ================================================================
    # COMBAT POLISH: ENEMY HEALTH BARS
    # ================================================================

    def mark_hp_bar_target(self, entity):
        """Mark an entity to show its HP bar for a few seconds.

        Called when the player targets or damages a creature/NPC.
        """
        self._hp_bar_targets[id(entity)] = 3.0  # show for 3 seconds

    def draw_enemy_hp_bars(self, entities: list, camera, dt: float):
        """Draw small HP bars above entities the player has targeted or damaged.

        Args:
            entities: Combined list of creatures and NPCs to consider.
            camera: Camera for world-to-screen conversion.
            dt: Delta time for decaying the display timer.
        """
        # Decay timers
        expired = []
        for eid, timer in self._hp_bar_targets.items():
            self._hp_bar_targets[eid] = timer - dt
            if self._hp_bar_targets[eid] <= 0:
                expired.append(eid)
        for eid in expired:
            del self._hp_bar_targets[eid]

        if not self._hp_bar_targets:
            return

        for entity in entities:
            if not getattr(entity, 'alive', True):
                continue
            if id(entity) not in self._hp_bar_targets:
                continue

            hp = getattr(entity, 'hp', 0)
            max_hp = getattr(entity, 'max_hp', 1)
            if max_hp <= 0:
                continue

            sx, sy = camera.world_to_screen(entity.x, entity.y)
            if not (-20 < sx < SCREEN_WIDTH + 20 and -20 < sy < SCREEN_HEIGHT + 20):
                continue

            # Draw HP bar
            bar_w = 24
            bar_h = 3
            bar_x = int(sx) - bar_w // 2
            bar_y = int(sy) - 18  # above the entity

            # Background (dark)
            pygame.draw.rect(self.screen, (30, 30, 30), (bar_x, bar_y, bar_w, bar_h))
            # HP fill (red -> yellow -> green based on ratio)
            ratio = max(0.0, min(1.0, hp / max_hp))
            if ratio > 0.6:
                bar_color = (80, 200, 80)   # green
            elif ratio > 0.3:
                bar_color = (220, 200, 50)  # yellow
            else:
                bar_color = (220, 50, 50)   # red
            fill_w = max(1, int(bar_w * ratio))
            pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, fill_w, bar_h))
            # Border
            pygame.draw.rect(self.screen, (80, 80, 80), (bar_x, bar_y, bar_w, bar_h), 1)

            # Show HP text for focused targets
            timer = self._hp_bar_targets.get(id(entity), 0)
            if timer > 2.0:  # recently targeted: show numbers
                hp_text = self.font_sm.render(f"{int(hp)}/{int(max_hp)}", True, (220, 220, 220))
                self.screen.blit(hp_text,
                                 (int(sx) - hp_text.get_width() // 2, bar_y - 12))

    # ================================================================
    # COMBAT POLISH: SPELL EFFECTS
    # ================================================================

    def spawn_spell_effect(self, spell_name: str, x: float, y: float,
                           target_x: float = None, target_y: float = None):
        """Spawn a visual spell effect at the given position.

        Args:
            spell_name: Name of the spell (fireball, ice_shard, lightning_bolt, heal, etc.)
            x, y: Origin position (caster).
            target_x, target_y: Target position (optional, for projectile effects).
        """
        tx = target_x if target_x is not None else x
        ty = target_y if target_y is not None else y

        if spell_name == "fireball":
            self._spawn_fireball_effect(tx, ty)
        elif spell_name in ("ice_shard", "ice_wall", "frost_nova"):
            self._spawn_ice_effect(tx, ty)
        elif spell_name in ("lightning_bolt", "chain_lightning"):
            self._spawn_lightning_effect(x, y, tx, ty)
        elif spell_name in ("heal", "mass_heal", "greater_heal"):
            self._spawn_heal_effect(tx, ty)
        else:
            # Generic spell effect using spell school colors
            self._spawn_generic_spell_effect(spell_name, tx, ty)

    def _spawn_fireball_effect(self, x: float, y: float):
        """Fireball: orange expanding circle + sparks."""
        self._spell_effects.append({
            "type": "fireball",
            "x": x, "y": y,
            "life": 0.8,
            "max_life": 0.8,
            "radius": 0.5,
            "max_radius": 2.5,
        })
        # Spark particles
        for _ in range(15):
            angle = math.radians(random.randint(0, 360))
            speed = random.uniform(2, 6)
            self.particles.append({
                "x": x + random.uniform(-0.3, 0.3),
                "y": y + random.uniform(-0.3, 0.3),
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "gravity": 3,
                "color": random.choice([(255, 160, 30), (255, 100, 20), (255, 200, 50)]),
                "size": random.randint(2, 4),
                "life": random.uniform(0.3, 0.7),
                "max_life": 0.7,
            })

    def _spawn_ice_effect(self, x: float, y: float):
        """Ice: blue shards radiating outward."""
        self._spell_effects.append({
            "type": "ice",
            "x": x, "y": y,
            "life": 0.6,
            "max_life": 0.6,
        })
        # Ice shard particles
        for _ in range(12):
            angle = math.radians(random.randint(0, 360))
            speed = random.uniform(2, 5)
            self.particles.append({
                "x": x,
                "y": y,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "gravity": 0,
                "color": random.choice([(150, 200, 255), (100, 180, 255), (200, 230, 255)]),
                "size": random.randint(2, 5),
                "life": random.uniform(0.4, 0.8),
                "max_life": 0.8,
            })

    def _spawn_lightning_effect(self, x: float, y: float,
                                tx: float, ty: float):
        """Lightning: bright white zigzag line from caster to target."""
        self._spell_effects.append({
            "type": "lightning",
            "x": x, "y": y,
            "tx": tx, "ty": ty,
            "life": 0.5,
            "max_life": 0.5,
            "segments": self._generate_lightning_segments(x, y, tx, ty),
        })
        # Bright flash particles at impact
        for _ in range(8):
            angle = math.radians(random.randint(0, 360))
            speed = random.uniform(1, 3)
            self.particles.append({
                "x": tx,
                "y": ty,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "gravity": 0,
                "color": random.choice([(255, 255, 200), (200, 200, 255), (255, 255, 255)]),
                "size": random.randint(2, 4),
                "life": random.uniform(0.2, 0.5),
                "max_life": 0.5,
            })

    def _generate_lightning_segments(self, x1, y1, x2, y2) -> List[Tuple[float, float]]:
        """Generate zigzag points for a lightning bolt."""
        dx = x2 - x1
        dy = y2 - y1
        dist = math.sqrt(dx * dx + dy * dy)
        if dist < 0.1:
            return [(x1, y1), (x2, y2)]

        num_segments = max(4, int(dist * 3))
        points = [(x1, y1)]
        for i in range(1, num_segments):
            t = i / num_segments
            # Point along the line with random perpendicular offset
            mx = x1 + dx * t
            my = y1 + dy * t
            # Perpendicular direction
            px = -dy / dist
            py = dx / dist
            offset = random.uniform(-0.4, 0.4)
            points.append((mx + px * offset, my + py * offset))
        points.append((x2, y2))
        return points

    def _spawn_heal_effect(self, x: float, y: float):
        """Heal: green rising particles."""
        self._spell_effects.append({
            "type": "heal",
            "x": x, "y": y,
            "life": 1.0,
            "max_life": 1.0,
        })
        # Green rising particles
        for _ in range(12):
            self.particles.append({
                "x": x + random.uniform(-0.5, 0.5),
                "y": y + random.uniform(-0.2, 0.2),
                "vx": random.uniform(-0.3, 0.3),
                "vy": -random.uniform(1.5, 3.5),
                "gravity": -0.5,  # float upward
                "color": random.choice([(80, 255, 80), (100, 230, 100), (150, 255, 150)]),
                "size": random.randint(2, 4),
                "life": random.uniform(0.5, 1.0),
                "max_life": 1.0,
            })

    def _spawn_generic_spell_effect(self, spell_name: str, x: float, y: float):
        """Generic spell effect with color based on spell name."""
        # Try to get visual info from magic system
        try:
            from game.systems.magic import get_spell_visual
            visuals = get_spell_visual(spell_name)
            color = visuals.get("color", (200, 200, 255))
            n_particles = visuals.get("particles", 8)
        except ImportError:
            color = (200, 200, 255)
            n_particles = 8

        for _ in range(n_particles):
            angle = math.radians(random.randint(0, 360))
            speed = random.uniform(1, 4)
            self.particles.append({
                "x": x + random.uniform(-0.2, 0.2),
                "y": y + random.uniform(-0.2, 0.2),
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "gravity": 1,
                "color": color,
                "size": random.randint(2, 4),
                "life": random.uniform(0.3, 0.8),
                "max_life": 0.8,
            })

    def draw_spell_effects(self, camera, dt: float):
        """Update and draw active spell effects.

        Call this in draw_particles or separately after entity rendering.
        """
        alive = []
        for effect in self._spell_effects:
            effect["life"] -= dt
            if effect["life"] <= 0:
                continue

            etype = effect["type"]
            progress = 1.0 - (effect["life"] / effect["max_life"])
            alpha_factor = max(0.0, 1.0 - progress)

            if etype == "fireball":
                self._draw_fireball_effect(effect, camera, progress, alpha_factor)
            elif etype == "ice":
                self._draw_ice_effect(effect, camera, progress, alpha_factor)
            elif etype == "lightning":
                self._draw_lightning_effect(effect, camera, progress, alpha_factor)
            elif etype == "heal":
                self._draw_heal_effect(effect, camera, progress, alpha_factor)

            alive.append(effect)
        self._spell_effects = alive

    def _draw_fireball_effect(self, effect, camera, progress, alpha_factor):
        """Draw expanding orange circle for fireball."""
        sx, sy = camera.world_to_screen(effect["x"], effect["y"])
        if not (-100 < sx < SCREEN_WIDTH + 100 and -100 < sy < SCREEN_HEIGHT + 100):
            return
        radius = effect["radius"] + (effect["max_radius"] - effect["radius"]) * progress
        screen_r = max(2, int(radius * TILE_SIZE))
        alpha = int(180 * alpha_factor)
        # Outer glow
        glow_surf = pygame.Surface((screen_r * 2 + 4, screen_r * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (255, 140, 30, alpha // 2),
                           (screen_r + 2, screen_r + 2), screen_r + 2)
        # Inner bright core
        core_r = max(1, screen_r // 2)
        pygame.draw.circle(glow_surf, (255, 200, 80, alpha),
                           (screen_r + 2, screen_r + 2), core_r)
        self.screen.blit(glow_surf, (sx - screen_r - 2, sy - screen_r - 2))

    def _draw_ice_effect(self, effect, camera, progress, alpha_factor):
        """Draw ice crystal flash at impact point."""
        sx, sy = camera.world_to_screen(effect["x"], effect["y"])
        if not (-50 < sx < SCREEN_WIDTH + 50 and -50 < sy < SCREEN_HEIGHT + 50):
            return
        alpha = int(200 * alpha_factor)
        # Draw radiating ice shards (lines from center)
        for i in range(6):
            angle = math.radians(i * 60 + progress * 30)
            length = (10 + progress * 15) * TILE_SIZE / 16
            ex = sx + math.cos(angle) * length
            ey = sy + math.sin(angle) * length
            color = (150, 200, 255, alpha)
            shard_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.line(shard_surf, color,
                             (int(sx), int(sy)), (int(ex), int(ey)), 2)
            self.screen.blit(shard_surf, (0, 0))

    def _draw_lightning_effect(self, effect, camera, progress, alpha_factor):
        """Draw zigzag lightning bolt."""
        segments = effect.get("segments", [])
        if len(segments) < 2:
            return
        alpha = int(255 * alpha_factor)
        # Convert all segment points to screen coordinates
        screen_points = []
        for wx, wy in segments:
            sx, sy = camera.world_to_screen(wx, wy)
            screen_points.append((int(sx), int(sy)))

        # Main bolt (bright white)
        if len(screen_points) >= 2:
            bolt_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.lines(bolt_surf, (255, 255, 255, alpha),
                              False, screen_points, 3)
            # Glow (wider, dimmer)
            pygame.draw.lines(bolt_surf, (150, 150, 255, alpha // 3),
                              False, screen_points, 6)
            self.screen.blit(bolt_surf, (0, 0))

    def _draw_heal_effect(self, effect, camera, progress, alpha_factor):
        """Draw gentle green glow for healing."""
        sx, sy = camera.world_to_screen(effect["x"], effect["y"])
        if not (-50 < sx < SCREEN_WIDTH + 50 and -50 < sy < SCREEN_HEIGHT + 50):
            return
        alpha = int(120 * alpha_factor)
        radius = int((8 + progress * 12) * TILE_SIZE / 16)
        glow_surf = pygame.Surface((radius * 2 + 4, radius * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (80, 255, 80, alpha),
                           (radius + 2, radius + 2), radius)
        pygame.draw.circle(glow_surf, (150, 255, 150, alpha // 2),
                           (radius + 2, radius + 2), radius + 2, 1)
        self.screen.blit(glow_surf, (sx - radius - 2, sy - radius - 2))
