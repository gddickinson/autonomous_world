"""
Screenshot system — capture and export game screen images.

Player use: F12 saves current screen to exports/screenshots/
Programmatic: HeadlessGame + capture functions for testing and automation.

All screenshots are saved as PNG with descriptive filenames including
timestamp and active view name.

Headless usage:
    from game.ui.screenshot import HeadlessGame
    hg = HeadlessGame(seed=12345)
    hg.capture("gameplay")           # overworld gameplay view
    hg.capture("character_sheet")    # character sheet panel
    hg.capture("inventory")          # inventory panel
    hg.capture("world_map")          # full world map at default zoom
    hg.capture("world_map", zoom=3.0, center_x=500, center_y=500)
    hg.move_player(500, 600)         # teleport player
    hg.tick(100)                     # advance 100 sim ticks
    hg.capture("gameplay")           # new location
"""

import os
import time
import random
import math
import pygame
from datetime import datetime


# Default export directory
EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "exports", "screenshots")


def _ensure_dir(path: str):
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)


def _get_active_view(game) -> str:
    """Determine which view/screen is currently active."""
    ui = getattr(game, 'ui', None)
    if ui is None:
        return "unknown"

    if getattr(ui, 'show_world_map', False):
        return "world_map"
    if getattr(ui, 'show_planet_view', False):
        return "planet_view"
    if getattr(ui, 'show_character', False):
        return "character_sheet"
    if getattr(ui, 'show_inventory', False):
        return "inventory"
    if getattr(ui, 'show_quest_log', False):
        return "quest_log"
    if getattr(ui, 'dialog_active', False):
        return "dialog"
    if getattr(ui, 'text_input_active', False):
        return "text_input"
    if getattr(ui, 'shop_active', False):
        return "shop"
    if getattr(ui, 'paused', False):
        return "pause_menu"

    # Check interior vs overworld
    player = getattr(game, 'player', None)
    if player:
        interior = getattr(player, 'interior_state', None)
        if interior and getattr(interior, 'is_inside', False):
            return "interior"

    dead = getattr(game, 'dead', False)
    if dead:
        return "death_screen"

    return "gameplay"


def _build_filename(view_name: str, prefix: str = "", suffix: str = "") -> str:
    """Build a descriptive filename for the screenshot."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    parts = []
    if prefix:
        parts.append(prefix)
    parts.append(view_name)
    parts.append(ts)
    if suffix:
        parts.append(suffix)
    return "_".join(parts) + ".png"


def capture_screenshot(screen: pygame.Surface, filename: str = None,
                       export_dir: str = None, game=None) -> str:
    """Capture the current screen to a PNG file.

    Args:
        screen: pygame surface to capture
        filename: optional explicit filename (auto-generated if None)
        export_dir: optional directory override (defaults to exports/screenshots/)
        game: optional Game instance for auto-detecting active view

    Returns:
        Full path to the saved file.
    """
    if export_dir is None:
        export_dir = EXPORT_DIR
    _ensure_dir(export_dir)

    if filename is None:
        view = _get_active_view(game) if game else "screen"
        filename = _build_filename(view)

    filepath = os.path.join(export_dir, filename)
    pygame.image.save(screen, filepath)
    return filepath


def capture_world_map(screen: pygame.Surface, world, player,
                      zoom: float = 0.5, center_x: float = None,
                      center_y: float = None,
                      export_dir: str = None) -> str:
    """Capture a world map screenshot at a specific zoom and position.

    Args:
        screen: pygame surface to render to
        world: World instance
        player: Player instance
        zoom: zoom level (0.25 = full world, 1.0 = 1:1, 4.0 = detailed)
        center_x/y: map center in world tiles (defaults to player position)
        export_dir: output directory

    Returns:
        Full path to the saved file.
    """
    from game.ui.world_map import WorldMapView, ZOOM_LEVELS

    if export_dir is None:
        export_dir = EXPORT_DIR
    _ensure_dir(export_dir)

    wm = WorldMapView()
    cx = center_x if center_x is not None else player.x
    cy = center_y if center_y is not None else player.y
    wm.open(cx, cy)

    # Find closest zoom level
    best_idx = 0
    best_diff = abs(ZOOM_LEVELS[0] - zoom)
    for i, z in enumerate(ZOOM_LEVELS):
        diff = abs(z - zoom)
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    wm.zoom_index = best_idx
    wm.zoom = ZOOM_LEVELS[best_idx]

    wm.draw(screen, world, player, world.structures)

    filename = _build_filename("world_map", suffix=f"z{wm.zoom:.2f}")
    filepath = os.path.join(export_dir, filename)
    pygame.image.save(screen, filepath)

    wm.close()
    return filepath


def capture_full_world(world, player, export_dir: str = None,
                       scale: int = 1) -> str:
    """Capture the entire world as a large image (1 pixel per tile * scale).

    Args:
        world: World instance
        player: Player instance
        export_dir: output directory
        scale: pixels per tile (1 = compact, 2 = detailed)

    Returns:
        Full path to the saved file.
    """
    from game.settings import TERRAIN_COLORS

    if export_dir is None:
        export_dir = EXPORT_DIR
    _ensure_dir(export_dir)

    w, h = world.width * scale, world.height * scale

    # Use numpy for fast rendering
    import numpy as np
    max_tile = max(TERRAIN_COLORS.keys()) + 1
    tile_array = np.array(world.tiles, dtype=np.int32)
    tile_array = np.clip(tile_array, 0, max_tile)

    rgb = np.zeros((world.height, world.width, 3), dtype=np.uint8)
    for tile_type, color in TERRAIN_COLORS.items():
        mask = tile_array == tile_type
        rgb[mask] = color

    # Mark player position
    px, py = int(player.x), int(player.y)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            nx, ny = px + dx, py + dy
            if 0 <= nx < world.width and 0 <= ny < world.height:
                rgb[ny, nx] = (80, 180, 255)

    # Mark settlements
    for s in world.structures:
        if s.kind in ("village", "town", "city", "castle", "hamlet"):
            color = {"city": (255, 220, 100), "castle": (255, 220, 100),
                     "town": (200, 200, 220), "village": (160, 200, 160),
                     "hamlet": (140, 160, 140)}.get(s.kind, (200, 200, 200))
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    nx, ny = s.x + dx, s.y + dy
                    if 0 <= nx < world.width and 0 <= ny < world.height:
                        rgb[ny, nx] = color

    # Create surface
    if scale > 1:
        rgb = np.repeat(np.repeat(rgb, scale, axis=0), scale, axis=1)

    surf = pygame.surfarray.make_surface(
        np.ascontiguousarray(rgb.transpose(1, 0, 2)))

    filename = _build_filename("full_world", suffix=f"s{scale}")
    filepath = os.path.join(export_dir, filename)
    pygame.image.save(surf, filepath)
    return filepath


def capture_gameplay_area(screen: pygame.Surface, game,
                          export_dir: str = None) -> str:
    """Force a redraw and capture the current gameplay view."""
    if export_dir is None:
        export_dir = EXPORT_DIR
    _ensure_dir(export_dir)

    # Trigger a full redraw
    if hasattr(game, '_draw'):
        game._draw()

    view = _get_active_view(game)
    filename = _build_filename(view, prefix="capture")
    filepath = os.path.join(export_dir, filename)
    pygame.image.save(screen, filepath)
    return filepath


class ScreenshotManager:
    """Manages screenshots for in-game use. Attach to Game instance."""

    def __init__(self, export_dir: str = None):
        self.export_dir = export_dir or EXPORT_DIR
        self.last_screenshot_path = ""
        self.screenshot_count = 0
        self._cooldown = 0.0  # prevent spam

    def take_screenshot(self, screen: pygame.Surface, game=None) -> str:
        """Take a screenshot. Returns filepath or empty string if on cooldown."""
        if self._cooldown > 0:
            return ""

        path = capture_screenshot(screen, export_dir=self.export_dir, game=game)
        self.last_screenshot_path = path
        self.screenshot_count += 1
        self._cooldown = 0.5  # 500ms cooldown
        return path

    def update(self, dt: float):
        """Update cooldown timer."""
        if self._cooldown > 0:
            self._cooldown = max(0, self._cooldown - dt)


# ================================================================
# HEADLESS GAME — full rendering pipeline without interactive init
# ================================================================

class HeadlessGame:
    """A headless Game instance that can render any view to screenshots.

    Sets up the complete rendering pipeline (world, renderer, UI, simulation)
    without interactive mode selection or loading screens. Ideal for automated
    testing and capturing screenshots programmatically.

    Usage:
        hg = HeadlessGame(seed=12345)
        hg.capture("gameplay")
        hg.capture("character_sheet")
        hg.capture("world_map", zoom=2.0)
        hg.move_player(500, 600)
        hg.tick(50)
        hg.capture("gameplay", suffix="after_move")
    """

    def __init__(self, seed: int = None, mode: str = "god",
                 export_dir: str = None, spawn_location: str = "mainland",
                 use_chunked: bool = False):
        """Initialize a headless game.

        Args:
            seed: world generation seed (random if None)
            mode: player mode — "mortal", "ghost", or "god"
            export_dir: screenshot output directory
            spawn_location: "mainland" or "test_island"
            use_chunked: if True, use ChunkedWorld (10,000x10,000)
        """
        os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
        os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

        if not pygame.get_init():
            pygame.init()

        from game.settings import (
            SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE,
            PLAYER_SPEED, PLAYER_MAX_HP, FPS,
        )

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.export_dir = export_dir or EXPORT_DIR
        _ensure_dir(self.export_dir)

        # Core systems
        from game.world.world import World, ChunkedWorld
        from game.world.camera import Camera
        from game.core.player import Player
        from game.ui.renderer import Renderer
        from game.ui.panels import UI
        from game.systems import TimeSystem, NotificationSystem
        from game.systems.quests import QuestSystem
        from game.systems.world_manager import WorldManager
        from game.systems.simulation import SimulationManager
        from game.systems.buildings import BuildingSystem
        from game.systems.party import PlayerParty
        from game.systems.tactical_combat import TacticalCombat
        from game.ai.llm import LLMManager
        from game.world.fov import compute_fov_set

        self.seed = seed if seed is not None else random.randint(0, 999999)
        if use_chunked:
            self.world = ChunkedWorld(seed=self.seed)
        else:
            self.world = World(seed=self.seed)
        self.camera = Camera(self.world.width, self.world.height, TILE_SIZE)
        self.renderer = Renderer(self.screen)
        self.ui = UI(self.screen)
        self.time_sys = TimeSystem()
        self.quest_sys = QuestSystem()
        self.notifications = NotificationSystem()
        self.world_mgr = WorldManager(self.world)
        self.world_mgr.initialize(random.Random(self.seed))

        # Quests
        quest_givers = random.sample(self.world_mgr.npcs,
                                      min(6, len(self.world_mgr.npcs)))
        for npc in quest_givers:
            self.quest_sys.generate_quest_for_npc(npc)
            npc.regenerate_dialog()  # rebuild tree so quest option appears

        # LLM (disabled for headless)
        self.llm = LLMManager()

        # Simulation
        self.simulation = SimulationManager(self.world_mgr, self.world,
                                             self.llm, self.time_sys)

        # Buildings — only register near spawn to avoid loading distant chunks
        self.building_sys = BuildingSystem()
        bsx, bsy = self.world.spawn_point
        if spawn_location == "test_island" and self.world.test_island_spawn:
            bsx, bsy = self.world.test_island_spawn
        for s in self.world.structures:
            if s.kind in ("village", "town", "city", "hamlet", "castle"):
                if abs(s.x - bsx) > 500 or abs(s.y - bsy) > 500:
                    continue
                for bx, by, bw, bh in s.buildings:
                    self.building_sys.register_building(
                        s.name, s.kind, bx, by, bw, bh)
        self.building_sys.assign_owners(self.world_mgr.npcs)

        # Player
        self.player_mode = mode
        self.spawn_location = spawn_location
        if spawn_location == "test_island" and self.world.test_island_spawn:
            sx, sy = self.world.test_island_spawn
        else:
            sx, sy = self.world.spawn_point
        self.player = Player(float(sx), float(sy))
        self.player.mode = mode

        if mode == "god":
            self.player.god = True
            self.player.hp = 99999
            self.player.max_hp = 99999
            self.player.speed = PLAYER_SPEED * 3
        elif mode == "ghost":
            self.player.ghost = True
            self.player.speed = PLAYER_SPEED * 2

        self.camera.x = self.player.x * TILE_SIZE - SCREEN_WIDTH // 2
        self.camera.y = self.player.y * TILE_SIZE - SCREEN_HEIGHT // 2

        # Minimap
        self.renderer.build_minimap(self.world)

        # FOV
        self.visible_tiles = None if mode == "god" else set()
        self.fov_radius = 12 if mode == "mortal" else 20

        # Party & combat
        self.party = PlayerParty()
        self.combat = TacticalCombat()

        # State
        self.dead = False
        self.nearby_npc = None
        self.location_banner = ""
        self.location_banner_timer = 0.0
        self.attack_flash_timer = 0.0
        self.examine_text = ""
        self.show_minimap = False
        self.auto_play = False
        self.auto_play_timer = 0.0

        self.screenshots = ScreenshotManager(self.export_dir)
        self.clock = pygame.time.Clock()

        self._compute_fov = compute_fov_set

        # Warm up
        self.world.reveal_around(int(self.player.x), int(self.player.y), 12)

    def tick(self, n: int = 1):
        """Advance the simulation by n ticks."""
        dt = 1.0 / 30.0
        for _ in range(n):
            self.time_sys.update(dt)
            self.world_mgr.update(dt, self.player, self.time_sys.time)
            self.simulation.update(dt, self.player)
            self.notifications.update(dt)
            self._update_fov()

    def _update_fov(self):
        """Recompute field of view — cached by player tile position."""
        px, py = int(self.player.x), int(self.player.y)
        if (px, py) == getattr(self, '_last_fov_pos', None):
            return  # player hasn't moved to a new tile; skip recompute
        self._last_fov_pos = (px, py)
        if self.player_mode == "god":
            self.visible_tiles = None
        else:
            self.visible_tiles = self._compute_fov(px, py, self.fov_radius, self.world)
        self.world.reveal_around(px, py, self.fov_radius)

    def move_player(self, x: float, y: float):
        """Teleport player to a position and update camera."""
        from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT
        self.player.x = x
        self.player.y = y
        ts = self.camera.tile_size
        self.camera.x = x * ts - SCREEN_WIDTH // 2
        self.camera.y = y * ts - SCREEN_HEIGHT // 2
        self._update_fov()

    def _draw_gameplay(self):
        """Render the full gameplay view (overworld + entities + HUD)."""
        from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT, DOOR, FPS

        self.screen.fill((10, 10, 20))

        # Update camera using active tile size
        ts = self.camera.tile_size
        self.camera.x = self.player.x * ts - SCREEN_WIDTH // 2
        self.camera.y = self.player.y * ts - SCREEN_HEIGHT // 2

        # Use active renderer (strategy or adventure)
        r = getattr(self, 'active_renderer', self.renderer)

        interior_state = getattr(self.player, 'interior_state', None)
        if interior_state and interior_state.is_inside and interior_state.current_interior:
            self.renderer.draw_interior(interior_state.current_interior,
                                        self.player, self.camera)
        else:
            r.draw_world(self.world, self.camera,
                         self.visible_tiles, self.player)
            r.draw_building_doors(self.world, self.camera, self.player)
            r.draw_structures(self.world, self.camera)
            r.draw_ground_items(self.world_mgr.ground_items, self.camera)
            r.draw_creatures(self.world_mgr.creatures, self.camera,
                             self.visible_tiles)
            r.draw_npcs(self.world_mgr.npcs, self.camera,
                        self.player, self.visible_tiles)
            r.draw_player(self.player, self.camera)
            r.draw_night_overlay(self.time_sys.darkness)

        self.ui.draw_hud(self.player, self.time_sys)
        r.draw_minimap(self.world, self.player,
                       self.world_mgr.npcs,
                       self.world_mgr.creatures,
                                    self.show_minimap)
        self.ui.draw_notifications(self.notifications.notifications)

    def capture(self, view: str = "gameplay", filename: str = None,
                suffix: str = "", **kwargs) -> str:
        """Capture a specific view to a screenshot file.

        Args:
            view: one of "gameplay", "character_sheet", "inventory",
                  "quest_log", "world_map", "planet_view", "pause_menu",
                  "hud_only", "full_world"
            filename: explicit filename (auto-generated if None)
            suffix: appended to auto-generated filename
            **kwargs: view-specific options:
                - world_map: zoom (float), center_x (float), center_y (float)

        Returns:
            Full path to the saved PNG file.
        """
        _ensure_dir(self.export_dir)

        if view == "full_world":
            return capture_full_world(self.world, self.player,
                                       self.export_dir,
                                       scale=kwargs.get("scale", 1))

        if view == "world_map":
            return capture_world_map(
                self.screen, self.world, self.player,
                zoom=kwargs.get("zoom", 0.5),
                center_x=kwargs.get("center_x"),
                center_y=kwargs.get("center_y"),
                export_dir=self.export_dir,
            )

        # For all other views, render gameplay first as background
        self._draw_gameplay()

        # Overlay the requested panel
        if view == "character_sheet":
            self.ui.show_character = True
            self.ui.draw_character_sheet(self.player)
            self.ui.show_character = False

        elif view == "inventory":
            self.ui.show_inventory = True
            self.ui.draw_inventory(self.player)
            self.ui.show_inventory = False

        elif view == "quest_log":
            self.ui.show_quest_log = True
            self.ui.draw_quest_log(self.quest_sys.active_quests)
            self.ui.show_quest_log = False

        elif view == "planet_view":
            self.ui.show_planet_view = True
            self.ui.draw_planet_view(1.0 / 60, self.time_sys)
            self.ui.show_planet_view = False

        elif view == "pause_menu":
            self.ui.paused = True
            self.ui.draw_pause_menu()
            self.ui.paused = False

        # else: "gameplay" — already drawn

        if filename is None:
            filename = _build_filename(view, suffix=suffix)

        filepath = os.path.join(self.export_dir, filename)
        pygame.image.save(self.screen, filepath)
        return filepath

    def capture_at(self, x: float, y: float, view: str = "gameplay",
                   **kwargs) -> str:
        """Move player to a location and capture a screenshot.

        Args:
            x, y: world tile coordinates
            view: view type (see capture())
            **kwargs: passed to capture()

        Returns:
            Full path to the saved PNG file.
        """
        self.move_player(x, y)
        return self.capture(view, **kwargs)

    def capture_settlement(self, settlement_name: str,
                            view: str = "gameplay", **kwargs) -> str:
        """Move player to a named settlement and capture a screenshot.

        Args:
            settlement_name: name of the settlement to visit
            view: view type (see capture())

        Returns:
            Full path to saved PNG, or empty string if settlement not found.
        """
        for s in self.world.structures:
            if s.name.lower() == settlement_name.lower():
                return self.capture_at(float(s.x), float(s.y), view, **kwargs)
        return ""

    def capture_all_views(self, prefix: str = "") -> dict:
        """Capture screenshots of all available views.

        Returns:
            Dict mapping view name to file path.
        """
        results = {}
        for view in ["gameplay", "character_sheet", "inventory",
                      "quest_log", "world_map", "pause_menu"]:
            path = self.capture(view, suffix=prefix)
            results[view] = path
        return results
