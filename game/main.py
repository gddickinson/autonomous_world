"""
Autonomous World - Main game loop.
Slim orchestrator that delegates to focused modules.
"""

import sys
import os
import random
import time
import math
import itertools

import pygame

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game.settings import *
from game.config import GameConfig
from game.world.world import World, ChunkedWorld
from game.world.camera import Camera
from game.core.player import Player
from game.core.npc import NPC
from game.core.items import make_item
from game.systems import TimeSystem, NotificationSystem
from game.systems.quests import QuestSystem
from game.systems.quest_board import QuestBoardManager
from game.systems.quest_board_init import initialize_quest_boards
from game.systems.message_board import MessageBoardManager, initialize_message_boards
from game.systems.main_quest import MainQuestManager
from game.systems.combat import CombatSystem
from game.systems.world_manager import WorldManager
from game.ui.renderer import Renderer
from game.ui.panels import UI
from game.ui.menus import MenuSystem
from game.ai.llm import LLMManager
from game.ai.prompts import Prompts
from game.systems.simulation import SimulationManager
from game.systems.chronicles import ChronicleSystem, classify_event
from game.world.fov import compute_fov_set
from game.data.db import GameDB
from game.systems.buildings import BuildingSystem
from game.systems.tactical_combat import TacticalCombat
from game.systems.party import PlayerParty
from game import actions
from game.ai.claude_assistant import ClaudeAssistant
from game.ai.god_console import GodConsole
from game.ui.claude_chat import ClaudeChatUI, APIKeyConfigUI
from game.core.remote_player import RemotePlayer
from game.systems.difficulty import init_difficulty
from game.ui.quest_tracker import QuestTracker
from game.ui.controls_overlay import ControlsOverlay
from game.ui.llm_console import LLMConsole
from game.systems.player_roads import PlayerRoadBuilder
from game.ui.water_render import WaterRipples


from game.main_dialog_results import DialogResultsMixin
from game.main_multiplayer import MultiplayerMixin
from game.systems.tutorial import TutorialSystem
from game.audio.sound_system import SoundManager


class Game(DialogResultsMixin, MultiplayerMixin):
    """Main game class - orchestrates all systems."""

    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()

        # Configuration system
        self.config = GameConfig()

        # Menu system — show title screen
        self.menus = MenuSystem(self.screen, self.clock, self.config)
        title_result = self.menus.show_title()
        if title_result is None:
            pygame.quit()
            sys.exit()

        # Read settings from config (set by menus or loaded from file)
        self.player_mode = self.config["player_mode"]
        self.spawn_location = self.config["spawn_location"]
        self.use_chunked = True

        # Character creation — show BEFORE world loads (world gen is slow)
        # God mode shows god selection instead of character creation
        self._char_data = None
        self._god_choice = None
        skip_chargen = getattr(self.__class__, '_skip_chargen', False)
        dev_chargen = getattr(self.__class__, '_dev_chargen', False)
        if self.player_mode == "god" and not skip_chargen:
            from game.ui.god_selection import show_god_selection
            god_result = show_god_selection(self.screen, self.clock)
            if god_result is None:
                pygame.quit()
                sys.exit()
            self._god_choice = god_result.get("god_name", "Verithos")
            skip_chargen = True
        if title_result == "new_game" and not skip_chargen:
            if dev_chargen:
                from game.ui.char_creation_dev import show_dev_creation
                result = show_dev_creation(self.screen, self.clock)
            else:
                from game.ui.char_creation import show_character_creation
                result = show_character_creation(self.screen, self.clock)
            if result is None:
                pygame.quit()
                sys.exit()
            self._char_data = result
            if dev_chargen and result.get("spawn_location"):
                self.spawn_location = result["spawn_location"]

        self._show_loading("Generating world...", 0.0)

        # Core systems — chunked world (uses config dimensions)
        world_w = self.config["world_width"]
        world_h = self.config["world_height"]
        seed = self.config["world_seed"]

        # Apply terrain/settlement style from config to settings flags
        import game.settings as _settings
        terrain_style = self.config.get("terrain_style", "volcanic")
        _settings.USE_NEW_TERRAIN = (terrain_style == "volcanic")
        settlement_style = self.config.get("settlement_style", "voronoi")
        _settings.USE_VORONOI_LAYOUT = (settlement_style == "voronoi")
        _settings.USE_LTP_SETTLEMENTS = (terrain_style == "volcanic")

        def _on_progress(text, frac):
            self._show_loading(text, frac)
        self.world = ChunkedWorld(world_w, world_h, seed=seed,
                                  progress_callback=_on_progress)
        self._show_loading("Generating world...", 0.25)

        self.camera = Camera(self.world.width, self.world.height, TILE_SIZE)
        self.renderer = Renderer(self.screen)
        self.renderer_adventure = None  # lazy-loaded on first use
        self.active_renderer = self.renderer  # currently active renderer
        self.view_mode = self.config["default_view"]  # "strategy", "adventure", or "3d"
        self.ui = UI(self.screen)
        from game.ui.spell_bar import SpellBar
        self.spell_bar = SpellBar(
            pygame.font.SysFont("monospace", 12),
            pygame.font.SysFont("monospace", 16),
        )
        from game.ui.targeting import TargetingSystem
        self.targeting = TargetingSystem()
        from game.systems.elemental_effects import ElementalEffects
        self.elemental = ElementalEffects()
        from game.ui.elemental_renderer import ElementalRenderer
        self.elemental_renderer = ElementalRenderer()
        self.time_sys = TimeSystem()
        self.quest_sys = QuestSystem()
        init_difficulty(self.config)
        self.quest_tracker = QuestTracker()
        self.controls_overlay = ControlsOverlay()
        self.llm_console = LLMConsole()
        self.road_builder = PlayerRoadBuilder()
        self.water_ripples = WaterRipples()
        self.notifications = NotificationSystem()
        self.world_mgr = WorldManager(self.world)

        self._show_loading("Populating world...", 0.35)
        self.world_mgr.initialize(random.Random())

        self._show_loading("Generating quests...", 0.45)
        quest_givers = random.sample(self.world_mgr.npcs, min(6, len(self.world_mgr.npcs)))
        for npc in quest_givers:
            self.quest_sys.generate_quest_for_npc(npc)
            npc.regenerate_dialog()  # rebuild tree so quest option appears

        # Quest boards at taverns
        self.quest_board_mgr = QuestBoardManager()
        initialize_quest_boards(self.world, self.quest_board_mgr)
        # Track active quest board UI state
        self.quest_board_active = False
        self.quest_board_settlement = ""
        self.quest_board_listings = []
        self.quest_board_selected = 0

        # Message boards at taverns and town halls
        self.msg_board_mgr = MessageBoardManager()
        initialize_message_boards(self.world, self.msg_board_mgr)
        self.msg_board_active = False
        self.msg_board_settlement = ""
        self.msg_board_listings = []
        self.msg_board_selected = 0
        # Board selection menu (quest board vs message board)
        self.board_menu_active = False
        self.board_menu_quest_board = None
        self.board_menu_msg_board = None
        self.board_menu_selected = 0

        # Main questline
        self.main_quest = MainQuestManager()

        # LLM
        self._show_loading("Connecting to LLM...", 0.50)
        self.llm = LLMManager()
        self.llm.start()
        self.llm_update_timer = 0.0
        actions.request_npc_greetings(self)

        # Simulation
        self._show_loading("Initializing simulation...", 0.55)
        self.simulation = SimulationManager(self.world_mgr, self.world, self.llm, self.time_sys)
        # Share quest board manager with simulation for periodic refresh
        self.simulation._quest_board_mgr = self.quest_board_mgr

        # Historical chronicle system
        self.chronicles = ChronicleSystem()
        self.main_quest.attach_chronicle(self.chronicles)

        # Wire climate model into UI for HUD weather display and world map overlay
        if hasattr(self.simulation, 'climate'):
            self.ui._climate_ref = self.simulation.climate
            self.ui.world_map_view._climate_ref = self.simulation.climate

        # Building system (ownership, locks, trespass)
        self._show_loading("Registering buildings...", 0.70)
        self.building_sys = BuildingSystem()
        _bsx, _bsy = self.world.spawn_point
        if self.spawn_location == "test_island" and self.world.test_island_spawn:
            _bsx, _bsy = self.world.test_island_spawn
        for s in self.world.structures:
            if s.kind in ("village", "town", "city", "hamlet", "castle"):
                if abs(s.x - _bsx) > 500 or abs(s.y - _bsy) > 500:
                    continue
                for bx, by, bw, bh in s.buildings:
                    self.building_sys.register_building(
                        s.name, s.kind, bx, by, bw, bh)
        self.building_sys.assign_owners(self.world_mgr.npcs)

        # Persistence
        self.db = GameDB("data/gameworld.db")

        # Player — choose spawn point based on location selection
        if self.spawn_location == "test_island" and self.world.test_island_spawn:
            sx, sy = self.world.test_island_spawn
        else:
            sx, sy = self.world.spawn_point
        # Create player with character creation data (if any)
        # Merge preset (from --wizard etc.) with char creation data
        cd = self._char_data or {}
        preset = getattr(self.__class__, '_char_preset', None)
        if preset:
            cd = {**cd, **preset}
        self.player = Player(
            float(sx), float(sy),
            char_class=cd.get("char_class", "Fighter"),
            race=cd.get("race", "Human"),
            ability_scores=cd.get("ability_scores"),
        )
        self.player.mode = self.player_mode  # "mortal", "ghost", "god"
        self.player.gold = self.config["starting_gold"]

        # Validate class setup — ensure spellcasters have mana and spells
        if self.player.is_spellcaster:
            from game.systems.magic import init_mana, auto_learn_spells_for_class
            init_mana(self.player)
            auto_learn_spells_for_class(self.player)
            if not self.player.known_spells:
                # Fallback: populate from class spell_list
                from game.data.dnd import CLASSES
                cls_data = CLASSES.get(self.player.char_class, {})
                self.player.known_spells = list(cls_data.get("spell_list", []))[:5]
        print(f"[INIT] Player created: {self.player.race} {self.player.char_class} "
              f"(spellcaster={self.player.is_spellcaster}, "
              f"spells={len(self.player.known_spells)}, "
              f"abilities={self.player.class_abilities})")

        # Apply dev-mode overrides
        if cd.get("level") and cd["level"] > 1:
            for _ in range(cd["level"] - 1):
                self.player.gain_xp(self.player.xp_to_next)
        if cd.get("gold") is not None:
            self.player.gold = cd["gold"]
        if cd.get("hp") and cd.get("max_hp"):
            self.player.max_hp = cd["max_hp"]
            self.player.hp = cd["hp"]
        if cd.get("god_mode"):
            self.player.god = True
            self.player.mode = "god"
            self.player_mode = "god"
            self.player.max_hp = 99999
            self.player.hp = 99999
            self.player.speed *= 3
        if cd.get("extra_items"):
            from game.core.items import make_item
            for item_name in cd["extra_items"]:
                try:
                    self.player.add_item(make_item(item_name))
                except Exception:
                    pass

        # Learn all spells in the game (wizard cheat mode)
        if cd.get("all_spells"):
            from game.systems.magic import SPELL_REGISTRY, SOUL_SPELLS
            all_spell_names = list(SPELL_REGISTRY.keys()) + list(SOUL_SPELLS.keys())
            self.player.known_spells = all_spell_names
            self.player.is_spellcaster = True
            self.player.max_mana = 999
            self.player.mana = 999

        # Restore saved player state if a save file exists for this seed
        if title_result == "continue":
            try:
                from game.data.save_game import load_game, apply_save_to_player
                save_data = load_game("data/savegame.json")
                if save_data and save_data.get("world_seed") == self.world.seed:
                    apply_save_to_player(self.player, save_data)
            except Exception:
                pass

        # Apply mode-specific settings
        if self.player_mode == "ghost":
            self.player.ghost = True
            self.player.speed = PLAYER_SPEED * 2  # ghosts move fast
        elif self.player_mode == "god":
            god_name = getattr(self, '_god_choice', None) or "Verithos"
            self.player.god = True
            self.player.race = "Divine"
            self.player.char_class = god_name
            self.player.name = god_name
            self.player.hp = 99999
            self.player.max_hp = 99999
            self.player.speed = PLAYER_SPEED * 3
            self.player.attack_damage = 9999
            self.player.defense = 999
            self.player.level = 99
            for ab in ("strength", "dexterity", "constitution",
                       "intelligence", "wisdom", "charisma"):
                self.player.ability_scores[ab] = 30
            from game.systems.magic import SPELL_REGISTRY, SOUL_SPELLS
            self.player.known_spells = list(SPELL_REGISTRY.keys()) + list(SOUL_SPELLS.keys())
            self.player.is_spellcaster = True
            self.player.max_mana = 999
            self.player.mana = 999
            self.player.gold = 99999
            # Store which god for game systems
            self.player._god_name = god_name
            from game.ui.god_selection import GOD_INFO
            god_info = GOD_INFO.get(god_name, {})
            self.player._god_sphere = god_info.get("sphere", "unknown")
            self.player._god_color = god_info.get("aura", (255, 220, 100))

        # God Mode UI (tweaker, console, hot-reload are created inside GodModeUI)
        if getattr(self.player, 'god', False):
            from game.ui.god_mode import GodModeUI
            self.god_ui = GodModeUI(self.screen, self)
            # Divine dashboard and intervention commands
            from game.ui.god_dashboard import GodDashboard
            from game.systems.divine_commands import DivineCommands
            self.god_dashboard = GodDashboard(self)
            self.divine_commands = DivineCommands()

        self.camera.x = self.player.x * TILE_SIZE - SCREEN_WIDTH // 2
        self.camera.y = self.player.y * TILE_SIZE - SCREEN_HEIGHT // 2

        # Minimap and renderer caches
        self._show_loading("Building minimap...", 0.85)
        self.renderer.build_minimap(self.world)
        # Pre-build renderer caches that would otherwise stall the first frame
        self._show_loading("Building render caches...", 0.90)
        self.renderer._build_roof_cache()
        self.renderer._build_building_function_cache(self.world)
        # Pre-build height map cache for 2.5D building rendering
        if hasattr(self.world, 'plan'):
            hm = {}
            for sp in self.world.plan.settlements:
                for bld in sp.buildings:
                    bx, by = bld['x'], bld['y']
                    bw, bh = bld['w'], bld['h']
                    bname = bld.get('name', '')
                    nf = 3 if any(k in bname for k in ('Tower', 'Keep', 'Castle')) \
                        else 2 if sp.kind in ('city', 'castle') else 1
                    for dy in range(bh):
                        for dx in range(bw):
                            hm[(bx + dx, by + dy)] = nf
            for loc in self.world.plan.special_locations:
                if loc.kind == 'temple':
                    r = loc.radius
                    for dy in range(-r, r + 1):
                        for dx in range(-r, r + 1):
                            if dx * dx + dy * dy <= r * r:
                                hm[(loc.x + dx, loc.y + dy)] = 1
            self.renderer._height_map_cache = hm

        # FOV
        self.visible_tiles = set()
        self.fov_radius = 12

        # Party system
        self.party = PlayerParty()

        # Tactical combat
        self.combat = TacticalCombat()

        # Screenshot system
        from game.ui.screenshot import ScreenshotManager
        self.screenshots = ScreenshotManager()

        # Game state
        self.running = True
        self.dead = False
        self.nearby_npc = None
        self.nearby_creature = None  # intelligent creature available for dialog
        self.location_banner = ""
        self.location_banner_timer = 0.0
        self.current_location = ""
        self.attack_flash_timer = 0.0
        self.examine_text = ""
        self.examine_timer = 0.0
        self.power_strike_active = False
        self.auto_play = False
        self.auto_play_timer = 0.0
        self.show_minimap = False  # off by default, toggle with N
        self.auto_save_timer = 0.0  # counts up to auto_save_interval
        self._last_player_level = 1  # audio: track level for level-up sound
        self._last_player_hp = self.player.max_hp  # audio: track HP for damage sound

        # Object highlighting system (J to toggle, K for category picker)
        from game.ui.highlight import HighlightSystem
        self.highlight = HighlightSystem()

        # Contextual help tooltips
        from game.ui.tooltips import TooltipSystem
        self.tooltip_sys = TooltipSystem(self.renderer.font_sm)

        # Claude AI assistant (God Mode only)
        self.claude_assistant = ClaudeAssistant(self)
        self.god_console = GodConsole(self)
        self.claude_chat = ClaudeChatUI(self.claude_assistant, self.god_console)
        self.api_key_config = APIKeyConfigUI()

        # Multiplayer networking
        self.net_server = None
        self.net_client = None
        self.remote_players = {}  # player_id -> RemotePlayer
        self._net_state_timer = 0.0
        self._net_state_interval = 0.1  # broadcast state 10x/sec
        self._multiplayer_chat_log = []
        self._init_multiplayer()

        # Phase 6: Player progression systems
        from game.systems.titles import initialize_title_tracker
        initialize_title_tracker(self.player)
        from game.ui.panel_combat_log import CombatLogPanel
        self.combat_log_panel = CombatLogPanel()
        from game.ui.panel_settlement import SettlementOverviewPanel
        self.settlement_panel = SettlementOverviewPanel()
        from game.ui.panel_relationships import RelationshipPanel
        self.relationship_panel = RelationshipPanel()
        from game.systems.letter_system import LetterSystem
        self.letter_system = LetterSystem()
        from game.systems.fast_travel import FastTravelUI
        self.fast_travel_ui = FastTravelUI()
        self._title_check_timer = 0.0

        # Crafting UI and Skill Tree (Phase 6)
        from game.systems.crafting_ui import CraftingUI
        self.crafting_ui = CraftingUI()
        from game.systems.skill_tree import SkillTreeUI, init_player_skill_tree
        self.skill_tree_ui = SkillTreeUI()
        init_player_skill_tree(self.player)

        # Audio system — procedural sound effects
        self.sound = SoundManager()

        self._show_loading("Ready!", 1.0)
        print("[INIT] All systems initialized, entering game loop...")

        # Reveal start
        self.world.reveal_around(int(self.player.x), int(self.player.y), 12)

        # Tutorial system — activate for mortal players on test island
        self.tutorial = None
        if self.spawn_location == "test_island" and self.player_mode == "mortal":
            self.tutorial = TutorialSystem(self.player)

        # Starting quest — guide new mortal/ghost players to nearest settlement
        if self.player_mode != "god":
            from game.systems.starting_quest import create_starting_quest
            _sq_name = create_starting_quest(self.world, self.quest_sys)
            print(f"[QUEST] Starting quest target: {_sq_name}, "
                  f"active quests: {len(self.quest_sys.active_quests)}")
            if _sq_name:
                self.notifications.add("New quest: Find Civilization", 5.0, YELLOW)
                self.notifications.add(
                    f"Head toward {_sq_name} to find people.", 6.0, (180, 200, 140))
                # Start main questline chained from the starting quest
                self.main_quest.start(_sq_name)
                self.main_quest.attach_chronicle(self.chronicles)
            else:
                # No settlement found — create a fallback exploration quest
                print("[QUEST] WARNING: No settlement found for starting quest. "
                      "Creating fallback quest.")
                from game.systems.quests import Quest
                fallback_quest = Quest(
                    title="Explore the World",
                    description=(
                        "You've awakened at an ancient temple. Explore the "
                        "surrounding area and find signs of civilization."
                    ),
                    kind="investigate",
                    target="settlement",
                    target_count=1,
                    reward_gold=10,
                    reward_xp=25,
                    difficulty="easy",
                    stages=1,
                )
                fallback_quest.giver_name = "Temple of Awakening"
                self.quest_sys.accept_quest(fallback_quest)
                self.notifications.add("New quest: Explore the World", 5.0, YELLOW)

        if self.spawn_location == "test_island":
            self.notifications.add("Welcome to the Test Island!", 5.0, YELLOW)
            self.notifications.add("A remote desert island. No NPCs or creatures here.", 6.0, (180, 160, 80))
        else:
            self.notifications.add("Welcome to the Autonomous World!", 5.0, YELLOW)
        if self.player_mode == "ghost":
            self.notifications.add("You are a GHOST. Pass through walls. Return to the temple to be reborn.", 8.0, (150, 150, 220))
        elif self.player_mode == "god":
            self.notifications.add("You are a GOD. Invincible. One-hit kills. See everything.", 8.0, (255, 220, 100))
            if self.claude_assistant.available:
                self.notifications.add("[`] Chat with Claude AI  [K] Configure API key", 6.0, (200, 200, 255))
            else:
                self.notifications.add("[K] Set API key to enable Claude AI assistant", 6.0, (200, 180, 100))
        else:
            self.notifications.add("WASD:Move  Space:Fight  E:Interact  R:Recruit  T:Talk  C:Character", 7.0, (200, 200, 210))
            self.notifications.add("B:Settlement  L:CombatLog  Y:FastTravel  H:Chronicle", 7.0, (180, 200, 200))
        if self.llm.enabled:
            self.notifications.add(f"LLM active: {self.llm.provider_name}", 4.0, GREEN)

    # _show_mode_select and _show_spawn_select replaced by MenuSystem

    def _show_loading(self, text: str, progress: float = -1):
        """Show loading screen with optional progress bar.

        Args:
            text: status message
            progress: 0.0-1.0 for determinate bar, -1 for indeterminate
        """
        self.screen.fill((10, 10, 20))

        # Title
        font = pygame.font.SysFont("monospace", 28)
        title = font.render("Autonomous World", True, UI_HIGHLIGHT)
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2,
                                  SCREEN_HEIGHT // 2 - 60))

        # Status text
        font_sm = pygame.font.SysFont("monospace", 16)
        loading = font_sm.render(text, True, GRAY)
        self.screen.blit(loading, (SCREEN_WIDTH // 2 - loading.get_width() // 2,
                                    SCREEN_HEIGHT // 2))

        # Progress bar
        bar_w = 400
        bar_h = 16
        bar_x = SCREEN_WIDTH // 2 - bar_w // 2
        bar_y = SCREEN_HEIGHT // 2 + 30

        # Background
        pygame.draw.rect(self.screen, (40, 40, 55),
                         (bar_x, bar_y, bar_w, bar_h), border_radius=4)

        if progress >= 0:
            # Determinate bar
            fill_w = max(2, int(bar_w * min(1.0, progress)))
            color = UI_HIGHLIGHT
            if progress > 0.8:
                color = (80, 180, 100)
            pygame.draw.rect(self.screen, color,
                             (bar_x, bar_y, fill_w, bar_h), border_radius=4)

            # Percentage text
            pct = font_sm.render(f"{int(progress * 100)}%", True, (200, 200, 210))
            self.screen.blit(pct, (bar_x + bar_w + 10, bar_y - 1))

        # Pump events to prevent OS "not responding"
        pygame.event.pump()
        pygame.display.flip()

    def _init_multiplayer(self):
        """Initialize multiplayer networking based on config."""
        if not self.config.get("multiplayer_enabled", False):
            return

        port = self.config.get("server_port", DEFAULT_PORT)
        max_p = self.config.get("max_players", MAX_PLAYERS)
        self.player.name = self.config.get("player_name", "Player")

        if self.config.get("host_server", True):
            # This instance is the server + host player
            from game.network.server import GameServer
            self.net_server = GameServer(port=port, max_players=max_p)
            if self.net_server.start():
                self.notifications.add(
                    f"Multiplayer server started on port {port}",
                    5.0, (100, 220, 100))
                # Spawn AI player if enabled
                if self.config.get("ai_player_enabled", False):
                    self._spawn_ai_player()
            else:
                self.notifications.add(
                    f"Failed to start server on port {port}",
                    5.0, (255, 100, 100))
                self.net_server = None
        else:
            # This instance connects to a remote server
            from game.network.client import GameClient
            host = self.config.get("server_host", "localhost")
            name = self.config.get("player_name", "Player2")
            self.net_client = GameClient()
            self.net_client.on_notification = lambda t, d, c: \
                self.notifications.add(t, d, c)
            if self.net_client.connect(host, port, name):
                self.notifications.add(
                    f"Connected to server at {host}:{port}",
                    5.0, (100, 220, 100))
            else:
                reason = self.net_client.reject_reason or self.net_client.status
                self.notifications.add(
                    f"Failed to connect: {reason}",
                    5.0, (255, 100, 100))
                self.net_client = None

    def _spawn_ai_player(self):
        """Spawn an AI companion player."""
        try:
            from game.network.ai_player import AIPlayer
            personality = self.config.get("ai_player_personality", "explorer")
            port = self.config.get("server_port", DEFAULT_PORT)
            ai = AIPlayer(
                name=f"AI-{personality.title()}",
                personality=personality,
                host="localhost",
                port=port,
            )
            if ai.connect():
                self._ai_player = ai
                # Set AI starting position near host player
                ai.x = self.player.x + random.uniform(-3, 3)
                ai.y = self.player.y + random.uniform(-3, 3)
                ai._explore_origin = (ai.x, ai.y)
                self.notifications.add(
                    f"AI companion '{ai.name}' ({personality}) joined!",
                    4.0, (180, 140, 255))
            else:
                self.notifications.add(
                    "Failed to spawn AI player.", 3.0, (255, 100, 100))
        except Exception as e:
            print(f"[NET] AI player error: {e}")
            import traceback
            traceback.print_exc()

    def _update_multiplayer(self, dt: float):
        """Process multiplayer network updates. Called from _update."""
        if self.net_server:
            # Host: process incoming messages from remote players
            for msg in self.net_server.get_pending_messages():
                self._handle_net_message(msg)

            # Broadcast state periodically
            self._net_state_timer += dt
            if self._net_state_timer >= self._net_state_interval:
                self._net_state_timer = 0.0
                self.net_server.broadcast_state(self)

            # Update remote player entities from server client data
            clients = self.net_server.get_clients()
            seen = set()
            for pid, client in clients.items():
                seen.add(pid)
                if pid not in self.remote_players:
                    idx = len(self.remote_players)
                    rp = RemotePlayer(pid, client.player_name, idx)
                    self.remote_players[pid] = rp
                rp = self.remote_players[pid]
                rp.update_from_network(
                    client.x, client.y, client.hp, client.max_hp,
                    client.level, client.facing, client.gait, client.is_ai)
                rp.name = client.player_name
                rp.update(dt)

            # Remove disconnected players
            for pid in list(self.remote_players.keys()):
                if pid not in seen:
                    del self.remote_players[pid]

        elif self.net_client:
            # Remote client: send our position, process incoming
            self.net_client.send_move(
                self.player.x, self.player.y,
                self.player.vx, self.player.vy,
                self.player.facing,
                getattr(self.player, 'current_gait', 'walk'))

            self.net_client.update(dt)

            for msg in self.net_client.get_pending_messages():
                self._handle_net_message(msg)

            # Update remote player entities from client data
            for rp_state in self.net_client.get_remote_players():
                pid = rp_state.player_id
                if pid not in self.remote_players:
                    idx = len(self.remote_players)
                    rp = RemotePlayer(pid, rp_state.name, idx)
                    self.remote_players[pid] = rp
                rp = self.remote_players[pid]
                rp.update_from_network(
                    rp_state.x, rp_state.y, rp_state.hp, rp_state.max_hp,
                    rp_state.level, rp_state.facing, rp_state.gait,
                    rp_state.is_ai)
                rp.name = rp_state.name
                rp.update(dt)

    def _handle_net_message(self, msg: dict):
        """Handle a network message in the game loop."""
        from game.network.protocol import MessageType
        msg_type = msg.get("type", "")
        data = msg.get("data", {})

        if msg_type == MessageType.PLAYER_JOIN:
            name = data.get("name", "Unknown")
            is_ai = data.get("is_ai", False)
            prefix = "[AI] " if is_ai else ""
            self.notifications.add(
                f"{prefix}{name} joined the game!", 4.0, (100, 220, 100))

        elif msg_type == MessageType.PLAYER_LEAVE:
            name = data.get("name", "Unknown")
            pid = data.get("player_id", "")
            self.notifications.add(
                f"{name} left the game.", 4.0, (220, 150, 100))
            self.remote_players.pop(pid, None)

        elif msg_type == MessageType.PLAYER_CHAT or msg_type == MessageType.CHAT_MESSAGE:
            name = data.get("name", "?")
            text = data.get("text", "")
            self._multiplayer_chat_log.append((name, text, time.time()))
            if len(self._multiplayer_chat_log) > 50:
                self._multiplayer_chat_log = self._multiplayer_chat_log[-50:]
            self.notifications.add(f"[{name}]: {text}", 5.0, (180, 220, 255))

        elif msg_type == MessageType.NOTIFICATION:
            text = data.get("text", "")
            duration = data.get("duration", 3.0)
            color = tuple(data.get("color", [220, 220, 230]))
            self.notifications.add(text, duration, color)

        elif msg_type == MessageType.GAME_EVENT:
            desc = data.get("description", "")
            if desc:
                self.notifications.add(desc, 4.0, (200, 200, 100))

    def _draw_conversation_snippets(self, dt: float):
        """Draw overheard NPC conversation snippets as floating text."""
        snippets = self.simulation._snippet_manager.active_snippets
        if not snippets:
            return
        if not hasattr(self, '_snippet_font'):
            self._snippet_font = pygame.font.SysFont("monospace", 13)
        cam = self.camera
        ts = cam.tile_size if hasattr(cam, 'tile_size') else TILE_SIZE
        for s in snippets:
            # Convert world to screen coordinates
            sx = (s.x - cam.x) * ts + SCREEN_WIDTH // 2
            sy = (s.y - cam.y) * ts + SCREEN_HEIGHT // 2
            # Float upward slowly
            sy -= s.age * 12
            # Skip if off screen
            if sx < -200 or sx > SCREEN_WIDTH + 200:
                continue
            if sy < -50 or sy > SCREEN_HEIGHT + 50:
                continue
            # Fade out in last second
            alpha = 255
            if s.age > s.max_age - 1.0:
                alpha = max(0, int(255 * (s.max_age - s.age)))
            # Render speaker name and text
            label = f"{s.speaker_name}: \"{s.text}\""
            if len(label) > 60:
                label = label[:57] + "...\""
            text_surf = self._snippet_font.render(label, True, (240, 230, 200))
            if alpha < 255:
                text_surf.set_alpha(alpha)
            # Background box for readability
            tw, th = text_surf.get_size()
            bg = pygame.Surface((tw + 8, th + 4), pygame.SRCALPHA)
            bg.fill((0, 0, 0, min(160, alpha)))
            self.screen.blit(bg, (int(sx) - tw // 2 - 4, int(sy) - th // 2 - 2))
            self.screen.blit(text_surf, (int(sx) - tw // 2, int(sy) - th // 2))

    def _draw_remote_players(self):
        """Draw all remote players on the overworld."""
        tile_size = self.camera.tile_size if hasattr(self.camera, 'tile_size') else TILE_SIZE
        for rp in self.remote_players.values():
            rp.draw(self.screen, self.camera, tile_size)

    def _draw_multiplayer_status(self):
        """Draw multiplayer connection status indicator."""
        font = self.renderer.font_sm
        if self.net_server:
            count = self.net_server.client_count
            port = self.config.get("server_port", DEFAULT_PORT)
            text = f"HOST :{port} [{count} connected]"
            color = (100, 220, 100) if count > 0 else (180, 180, 100)
        elif self.net_client:
            text = f"ONLINE [{self.net_client.status}]"
            latency = self.net_client.latency_ms
            if latency > 0:
                text += f" {latency:.0f}ms"
            color = (100, 220, 100) if self.net_client.connected else (255, 100, 100)
        else:
            return

        surf = font.render(text, True, color)
        self.screen.blit(surf, (10, SCREEN_HEIGHT - 20))

    def _draw_chat_log(self):
        """Draw recent multiplayer chat messages."""
        if not self._multiplayer_chat_log:
            return
        font = self.renderer.font_sm
        now = time.time()
        # Show messages from last 15 seconds
        recent = [(n, t, ts) for n, t, ts in self._multiplayer_chat_log
                  if now - ts < 15.0]
        if not recent:
            return
        y = SCREEN_HEIGHT - 80
        for name, text, ts in recent[-5:]:
            age = now - ts
            alpha = max(50, int(255 * (1.0 - age / 15.0)))
            msg = f"[{name}]: {text}"
            if len(msg) > 60:
                msg = msg[:57] + "..."
            surf = font.render(msg, True, (180, 220, 255))
            surf.set_alpha(alpha)
            self.screen.blit(surf, (10, y))
            y -= 14

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)
            self._handle_events()
            if not self.ui.paused and not self.dead:
                self._update(dt)
            self._draw()
        self._shutdown()

    def _shutdown(self):
        self._save_game()
        # Shutdown multiplayer
        if hasattr(self, '_ai_player') and self._ai_player:
            try:
                self._ai_player.stop()
            except Exception:
                pass
        if self.net_server:
            try:
                self.net_server.stop()
            except Exception:
                pass
        if self.net_client:
            try:
                self.net_client.disconnect()
            except Exception:
                pass
        try:
            self.db.close()
        except Exception:
            pass
        self.config.save()
        self.llm.stop()
        pygame.quit()

    # ================================================================
    # INPUT
    # ================================================================

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            # Claude chat and API key config intercept all input when visible
            if self.api_key_config.visible:
                result = self.api_key_config.handle_event(
                    event, self.claude_assistant)
                if result == "saved":
                    self.notifications.add(
                        "API key saved! Claude assistant ready.", 3.0, GREEN)
                continue
            if self.claude_chat.visible:
                result = self.claude_chat.handle_event(event)
                if result == "open_api_key_config":
                    self.api_key_config.show()
                continue

            # LLM console intercepts all input when visible
            if self.llm_console.visible:
                if event.type == pygame.KEYDOWN:
                    self.llm_console.handle_event(event)
                continue

            # Toggle LLM console with backtick (non-god mode)
            if (event.type == pygame.KEYDOWN
                    and event.key == pygame.K_BACKQUOTE
                    and not getattr(self.player, 'god', False)):
                self.llm_console.toggle()
                continue

            # God mode: Python console intercepts all input when visible
            if (hasattr(self, 'god_ui') and getattr(self.player, 'god', False)
                    and self.god_ui.python_console.visible
                    and event.type == pygame.KEYDOWN):
                # Backtick closes the console
                if event.key == pygame.K_BACKQUOTE:
                    self.god_ui.python_console.toggle()
                    continue
                self.god_ui.python_console.handle_key(
                    event.key, event.unicode, pygame.key.get_mods())
                continue

            # Open Claude chat (god mode only; F10)
            # K now opens divine kingdom commands (API key moved to Shift+K)
            if (event.type == pygame.KEYDOWN
                    and getattr(self.player, 'god', False)):
                if event.key == pygame.K_F10:
                    self.claude_chat.toggle()
                    continue
                if event.key == pygame.K_k and (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                    self.api_key_config.show()
                    continue

            if self.ui.text_input_active:
                result = self.ui.handle_text_input_event(event)
                if result == "send":
                    actions.send_player_text(self)
                elif result == "close":
                    actions.check_npc_quest(self, self.ui.dialog_npc)
                continue
            # Spell targeting: intercept mouse clicks when targeting active
            if event.type == pygame.MOUSEBUTTONDOWN and self.targeting.is_active():
                if event.button == 1:  # left click = confirm target
                    from game.systems.spell_targeting_bridge import (
                        execute_targeted_spell, execute_targeted_throw)
                    from game.ui.targeting import SPELL_TARGET, THROW_TARGET
                    result = self.targeting.handle_click(
                        event.pos[0], event.pos[1], self.camera,
                        self.world, self.world_mgr.creatures,
                        self.world_mgr.npcs, self.player)
                    if self.targeting.state == SPELL_TARGET:
                        execute_targeted_spell(
                            self, self.targeting.spell_name, result)
                    elif self.targeting.state == THROW_TARGET:
                        execute_targeted_throw(
                            self, self.targeting.throw_item, result)
                    self.targeting.cancel()
                    continue
                elif event.button == 3:  # right click = cancel
                    self.targeting.cancel()
                    self.notifications.add("Targeting cancelled.", 1.0,
                                           (180, 180, 200))
                    continue
            # Road building mode: left click places road tiles
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and self.road_builder.active):
                self.road_builder.handle_click(
                    event.pos[0], event.pos[1], self)
                continue

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mods = pygame.key.get_mods()
                shift_held = mods & pygame.KMOD_SHIFT
                ctrl_held = mods & pygame.KMOD_CTRL

                # Divine commands: Ctrl+click = smite, Shift+click = bless
                if hasattr(self, 'divine_commands') and getattr(self.player, 'god', False):
                    # Dashboard click handling
                    if self.god_dashboard.visible:
                        if self.god_dashboard.handle_click(event.pos[0], event.pos[1]):
                            continue
                    # Ctrl+click = smite
                    if ctrl_held:
                        self.divine_commands.handle_click(
                            event.pos[0], event.pos[1], event.button,
                            mods, self.camera, self)
                        continue
                    # Shift+click = bless (divine version)
                    if shift_held:
                        self.divine_commands.handle_click(
                            event.pos[0], event.pos[1], event.button,
                            mods, self.camera, self)
                        continue

                # God UI inspect: SHIFT+click (or click when no entity under cursor)
                if hasattr(self, 'god_ui') and getattr(self.player, 'god', False):
                    if shift_held:
                        # SHIFT+click always opens god inspect
                        if not self.god_ui.handle_mousedown(event.pos[0], event.pos[1], event.button):
                            self.god_ui.handle_click(event.pos[0], event.pos[1],
                                                     event.button, self.camera,
                                                     self.world)
                        continue
                    # Panel drag still works without shift
                    self.god_ui.handle_mousedown(event.pos[0], event.pos[1], event.button)

                if self.ui.show_world_map:
                    self.ui.world_map_view.handle_click(
                        event.pos[0], event.pos[1], self.world, self.player)
                # Combat targeting: left-click on entity to set as target
                elif not self.ui.dialog_active and not self.ui.paused:
                    entity = self.targeting.get_hover_entity(
                        event.pos[0], event.pos[1], self.camera,
                        self.world_mgr.creatures, self.world_mgr.npcs)
                    if entity and getattr(entity, 'alive', False):
                        msg = self.combat.set_player_target(entity)
                        if msg:
                            self.notifications.add(msg, 2.0, (220, 80, 80))
                            self.attack_flash_timer = 0.1
                    elif hasattr(self, 'god_ui') and getattr(self.player, 'god', False):
                        # No entity under cursor — fall through to god inspect
                        self.god_ui.handle_click(event.pos[0], event.pos[1],
                                                 event.button, self.camera,
                                                 self.world)
            # Right-click: deselect combat target
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if not self.targeting.is_active():
                    if self.combat.active and self.combat.player_state.target:
                        self.combat.player_state.target = None
                        self.notifications.add("Target cleared.", 1.0, (180, 180, 200))
                        if not any(c.alive and self.player.dist_to(c) < 6
                                   for c in self.world_mgr.creatures):
                            self.combat.end_combat()
            if event.type == pygame.MOUSEWHEEL:
                if self.combat_log_panel.is_showing:
                    self.combat_log_panel.scroll(event.y)
                elif self.relationship_panel.visible:
                    self.relationship_panel.scroll(-event.y)
                elif self.settlement_panel.visible:
                    self.settlement_panel.scroll(event.y)
                elif self.ui.show_world_map:
                    self.ui.world_map_view.handle_scroll(event.y)
            if event.type == pygame.KEYDOWN:
                # F12 screenshot works from any screen, even modals
                if event.key == pygame.K_F12:
                    path = self.screenshots.take_screenshot(self.screen, game=self)
                    if path:
                        fname = os.path.basename(path)
                        self.notifications.add(f"Screenshot: {fname}", 3.0, (180, 220, 180))
                else:
                    self._handle_keydown(event.key,
                                         getattr(event, 'unicode', ''),
                                         pygame.key.get_mods())
            # Mouse drag support for parameter tweaker and god panel
            if event.type == pygame.MOUSEMOTION:
                self._mouse_pos = event.pos
                # Update targeting system mouse position
                if self.targeting.is_active():
                    self.targeting.update_mouse(event.pos[0], event.pos[1])
                self.targeting.get_hover_entity(
                    event.pos[0], event.pos[1], self.camera,
                    self.world_mgr.creatures, self.world_mgr.npcs)
                if (hasattr(self, 'god_ui')
                        and getattr(self.player, 'god', False)):
                    self.god_ui.handle_mousemove(event.pos[0], event.pos[1])
                    self.god_ui.tweaker.handle_drag(event.pos[0], event.pos[1])
            if event.type == pygame.MOUSEBUTTONUP:
                if (hasattr(self, 'god_ui')
                        and getattr(self.player, 'god', False)):
                    self.god_ui.handle_mouseup(event.pos[0], event.pos[1], event.button)
                    self.god_ui.tweaker.handle_mouse_up()

    def _handle_keydown(self, key, unicode_char="", mods=0):
        # Board menu (choose quest board or message board)
        if getattr(self, 'board_menu_active', False):
            self._handle_board_menu_input(key)
            return

        # Quest board input handling
        if getattr(self, 'quest_board_active', False):
            self._handle_quest_board_input(key)
            return

        # Message board input handling
        if getattr(self, 'msg_board_active', False):
            self._handle_msg_board_input(key)
            return

        # Panel-specific input
        if self.ui.dialog_active:
            self.sound.play("menu_click")
            result = self.ui.handle_dialog_input(key)
            npc = self.ui.dialog_npc

            # Creature-specific dialog results
            from game.core.creature import Creature
            is_creature = isinstance(npc, Creature)
            if is_creature and result:
                if result == "fight":
                    self.ui.dialog_active = False
                    npc.state = "chasing"
                    npc.target = self.player
                    kind_name = npc.kind.replace('_', ' ').title()
                    self.notifications.add(
                        f"The {kind_name} attacks!", 2.0, RED)
                    return
                elif result in ("close", "leave", "flee", "goodbye"):
                    self.ui.dialog_active = False
                    return
                elif result == "paid":
                    cost = 30 if "bandit" in npc.kind else 20
                    if self.player.gold >= cost:
                        self.player.gold -= cost
                        self.notifications.add(
                            f"Paid {cost} gold toll.", 2.0, YELLOW)
                    else:
                        self.notifications.add("Not enough gold!", 1.5, RED)
                elif result == "buy_potion":
                    if self.player.gold >= 10:
                        self.player.gold -= 10
                        from game.core.items import make_item
                        potion = make_item("Health Potion")
                        if potion:
                            self.player.add_item(potion)
                        self.notifications.add(
                            "Bought a health potion for 10 gold.", 2.0, GREEN)
                    else:
                        self.notifications.add("Not enough gold!", 1.5, RED)
                elif result == "take_tribute":
                    self.player.gold += 5
                    self.notifications.add("Took 5 gold tribute.", 2.0, YELLOW)
                # Other creature dialog results just navigate normally
                return

            # Generate memories from every meaningful dialog interaction
            if npc and result and result not in ("close", "greeting", "free_text", "back"):
                self._process_dialog_result(npc, result)
            elif result == "close":
                actions.check_npc_quest(self, npc)
                actions._end_dialog(self, npc)  # restore NPC state
            return
        if self.ui.gift_active:
            given_item = self.ui.handle_gift_input(key, self.player)
            if given_item:
                npc = self.ui.gift_npc
                if npc:
                    # Gift affects relationship based on item value and NPC needs
                    rel_boost = max(3, given_item.value // 5)
                    # Extra boost if gift matches NPC's needs
                    if given_item.name in ("Bread", "Apple", "Cooked Meat") and hasattr(npc, 'needs') and npc.needs.get("hunger", 50) < 40:
                        rel_boost += 10
                        npc.needs["hunger"] = min(100, npc.needs.get("hunger", 50) + 30)
                        self.notifications.add(f"{npc.name} gratefully eats the {given_item.name}!", 3.0, GREEN)
                    elif given_item.name in ("Health Potion", "Greater Health Potion", "Herbs") and npc.hp < npc.max_hp:
                        rel_boost += 8
                        npc.heal(getattr(given_item, 'heal', 20))
                        self.notifications.add(f"{npc.name} uses the {given_item.name} gratefully!", 3.0, GREEN)
                    else:
                        self.notifications.add(f"Gave {given_item.name} to {npc.name}. They appreciate it!", 3.0, GREEN)
                    npc.player_relationship = min(100, npc.player_relationship + rel_boost)
                    npc.add_memory("social", f"The player gave me a gift: {given_item.name}. Very generous!", 4)
                    # Add to NPC inventory
                    if hasattr(npc, 'npc_inventory'):
                        npc.npc_inventory.append(given_item)
                    npc.needs["social"] = min(100, npc.needs.get("social", 50) + 15)
                    # Trigger emotion
                    if hasattr(npc, 'emotion_state') and npc.emotion_state:
                        from game.systems.emotions import trigger_emotion
                        trigger_emotion(npc, "gift_received", intensity=0.6)
            return
        if self.ui.shop_active:
            result = self.ui.handle_shop_input(key, self.player)
            if result:
                self.notifications.add(result, 2.0)
            return
        # Crafting UI panel
        if self.crafting_ui.active:
            self.crafting_ui.handle_key(key, self.player)
            return
        # Skill tree panel
        if self.skill_tree_ui.active:
            self.skill_tree_ui.handle_key(key, self.player)
            return
        if self.ui.show_inventory:
            result = self.ui.handle_inventory_input(key, self.player, self.world_mgr)
            if result:
                if isinstance(result, tuple) and result[0] == "drop":
                    item = result[1]
                    self.world_mgr.ground_items.append((
                        self.player.x + random.uniform(-0.3, 0.3),
                        self.player.y + random.uniform(-0.3, 0.3), item))
                    self.notifications.add(f"Dropped {item.name}", 2.0, ORANGE)
                else:
                    self.notifications.add(result, 2.0)
            return
        if self.ui.show_character:
            if key in (pygame.K_ESCAPE, pygame.K_c):
                self.ui.show_character = False
            return
        if self.ui.show_quest_log:
            if key in (pygame.K_ESCAPE, pygame.K_q):
                self.ui.show_quest_log = False
            return
        if self.ui.show_chronicle:
            self.ui.handle_chronicle_input(key)
            return
        if self.relationship_panel.visible:
            if key in (pygame.K_w, pygame.K_UP):
                self.relationship_panel.scroll(-1)
            elif key in (pygame.K_s, pygame.K_DOWN):
                self.relationship_panel.scroll(1)
            elif key == pygame.K_ESCAPE or (key == pygame.K_r and (mods & pygame.KMOD_SHIFT)):
                self.relationship_panel.visible = False
            return
        if self.ui.show_planet_view:
            self.ui.handle_planet_view_input(key)
            return
        if self.ui.show_world_map:
            result = self.ui.world_map_view.handle_input(key)
            if result is True:
                self.ui.show_world_map = False
            elif result and result is not False:
                # Travel result returned — execute fast travel
                from game.systems.travel import execute_travel
                self.ui.show_world_map = False
                execute_travel(self, result)
            return
        if self.dead:
            if key == pygame.K_r:
                self._respawn()
            return
        # Fast travel UI active — intercept navigation keys
        if self.fast_travel_ui.active:
            if key == pygame.K_ESCAPE:
                self.fast_travel_ui.close()
                return
            elif key in (pygame.K_w, pygame.K_UP):
                self.fast_travel_ui.navigate(-1)
                return
            elif key in (pygame.K_s, pygame.K_DOWN):
                self.fast_travel_ui.navigate(1)
                return
            elif key in (pygame.K_RETURN, pygame.K_e):
                self._execute_fast_travel()
                return
            return  # block other keys while fast travel is open

        if key == pygame.K_ESCAPE:
            if self.targeting.is_active():
                self.targeting.cancel()
                self.notifications.add("Targeting cancelled.", 1.0,
                                       (180, 180, 200))
                return
            if self.settlement_panel.visible:
                self.settlement_panel.visible = False
                return
            if self.combat_log_panel.visible:
                self.combat_log_panel.visible = False
                return
            if self.relationship_panel.visible:
                self.relationship_panel.visible = False
                return
            if self.ui.any_panel_open:
                self.ui.close_all()
            elif self.combat.active:
                self.combat.end_combat()
                self.notifications.add("Disengaged from combat.", 2.0, ORANGE)
            else:
                self._open_pause_menu()
            return
        if self.ui.paused:
            return

        # Controls overlay (? = Shift+/) — checked before other keys
        _co_evt = pygame.event.Event(
            pygame.KEYDOWN, key=key, mod=pygame.key.get_mods())
        if self.controls_overlay.handle_event(_co_evt):
            return

        # 3D camera controls (arrow keys, +/-, [/])
        if self.view_mode == "3d" and hasattr(self, 'renderer_3d') and self.renderer_3d:
            cam_keys = {
                pygame.K_LEFT: lambda: self.renderer_3d.rotate_camera(d_azimuth=-5),
                pygame.K_RIGHT: lambda: self.renderer_3d.rotate_camera(d_azimuth=5),
                pygame.K_UP: lambda: self.renderer_3d.rotate_camera(d_elevation=-5),
                pygame.K_DOWN: lambda: self.renderer_3d.rotate_camera(d_elevation=5),
                pygame.K_EQUALS: lambda: self.renderer_3d.zoom_camera(0.85),
                pygame.K_MINUS: lambda: self.renderer_3d.zoom_camera(1.15),
                pygame.K_LEFTBRACKET: lambda: self.renderer_3d.change_radius(-2),
                pygame.K_RIGHTBRACKET: lambda: self.renderer_3d.change_radius(2),
            }
            cam_handler = cam_keys.get(key)
            if cam_handler:
                cam_handler()
                return

        # Divine commands & dashboard (god mode): intercept before other handlers
        if hasattr(self, 'divine_commands') and getattr(self.player, 'god', False):
            dc = self.divine_commands
            # Dashboard toggle (TAB)
            if key == pygame.K_TAB:
                self.god_dashboard.toggle()
                return
            # Dashboard handles keys when visible
            if self.god_dashboard.visible:
                if self.god_dashboard.handle_key(key):
                    return
            # Divine command menus and keys (G, K, N, [, ], P, .)
            if dc.menu.active_menu:
                if dc.handle_key(key, mods, self):
                    return
            elif key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET,
                         pygame.K_PERIOD):
                if dc.handle_key(key, mods, self):
                    return

        # God mode panel open: god UI gets number keys for tool switching
        # God mode panel closed: spell bar gets number keys for casting
        god_panel_open = (hasattr(self, 'god_ui')
                          and getattr(self.player, 'god', False)
                          and self.god_ui.panel_visible)

        if god_panel_open:
            # God panel is open — god UI handles keys first
            if self.god_ui.handle_key(key, unicode_char, mods):
                return
            if self.spell_bar.handle_key(key, self):
                return
        else:
            # God panel closed — spell bar handles keys first
            if self.spell_bar.handle_key(key, self):
                return
            if hasattr(self, 'god_ui') and getattr(self.player, 'god', False):
                if self.god_ui.handle_key(key, unicode_char, mods):
                    return

        # Shift+J: Road building mode (before highlight so J alone = highlight)
        if key == pygame.K_j and (mods & pygame.KMOD_SHIFT):
            self.road_builder.toggle(self)
            return

        # Object highlighting (J/K keys)
        if hasattr(self, 'highlight') and self.highlight.handle_key(key):
            return

        # Shift+R: Relationship panel (before action_map so R alone = recruit)
        if key == pygame.K_r and (mods & pygame.KMOD_SHIFT):
            self.relationship_panel.toggle()
            return

        # Divine commands intercept G, K, N, P in god mode before action_map
        if hasattr(self, 'divine_commands') and getattr(self.player, 'god', False):
            dc = self.divine_commands
            if key in (pygame.K_g, pygame.K_k, pygame.K_n, pygame.K_p):
                if dc.handle_key(key, mods, self):
                    return

        # Game controls
        action_map = {
            pygame.K_e: lambda: actions.interact(self),
            pygame.K_SPACE: lambda: actions.attack(self),
            pygame.K_i: lambda: setattr(self.ui, 'show_inventory', not self.ui.show_inventory) or setattr(self.ui, 'inv_selected', 0),
            pygame.K_c: lambda: setattr(self.ui, 'show_character', not self.ui.show_character),
            pygame.K_q: lambda: setattr(self.ui, 'show_quest_log', not self.ui.show_quest_log),
            pygame.K_h: lambda: setattr(self.ui, 'show_chronicle', not self.ui.show_chronicle) or setattr(self.ui, 'chronicle_scroll', 0),
            pygame.K_t: lambda: actions.talk_free_text(self),
            pygame.K_x: lambda: actions.examine(self),
            pygame.K_g: lambda: actions.drop_item(self),
            pygame.K_F1: lambda: actions.use_ability(self, "power_strike"),
            pygame.K_F2: lambda: actions.use_ability(self, "whirlwind"),
            pygame.K_F3: lambda: actions.use_ability(self, "keen_eye"),
            pygame.K_F4: lambda: actions.use_ability(self, "charm"),
            pygame.K_F5: lambda: actions.use_ability(self, "scout"),
            pygame.K_p: lambda: self._toggle_auto_play(),
            pygame.K_v: lambda: self._toggle_view_mode(),
            pygame.K_m: lambda: setattr(self.ui, 'show_planet_view', not self.ui.show_planet_view),
            pygame.K_f: lambda: self._toggle_world_map(),
            pygame.K_n: lambda: setattr(self, 'show_minimap', not self.show_minimap),
            pygame.K_r: lambda: self._recruit_companion(),
            pygame.K_TAB: lambda: self._cycle_nearby_npc(),
            pygame.K_z: lambda: self._toggle_interior_zoom(),
            pygame.K_F6: lambda: self._cycle_overlay_mode(),
            pygame.K_F7: lambda: self.tutorial.skip() if self.tutorial else None,
            pygame.K_b: lambda: self.settlement_panel.toggle(),
            pygame.K_l: lambda: self.combat_log_panel.toggle(),
            pygame.K_y: lambda: self._open_fast_travel(),
            pygame.K_u: lambda: self.crafting_ui.toggle(),
            pygame.K_o: lambda: self.skill_tree_ui.toggle(),
            pygame.K_F8: lambda: self._toggle_sound_mute(),
            pygame.K_F9: lambda: self._toggle_music_mute(),
        }
        handler = action_map.get(key)
        if handler:
            # Audio: click sound for UI panel toggles
            _ui_keys = {pygame.K_i, pygame.K_c, pygame.K_q, pygame.K_h,
                        pygame.K_b, pygame.K_l, pygame.K_u, pygame.K_o}
            if key in _ui_keys:
                self.sound.play("menu_click")
            handler()

    def _draw_combat_ui(self):  # noqa: C901
        """Draw real-time combat HUD overlay (non-blocking)."""
        if not self.combat.active:
            return

        font_sm = self.renderer.font_sm

        # Combat log panel (bottom-right, compact)
        pw, ph = 260, 140
        px = SCREEN_WIDTH - pw - 10
        py = SCREEN_HEIGHT - ph - 60

        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((10, 10, 25, 180))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, (120, 50, 50), (px, py, pw, ph), 1)

        # Target info
        target = self.combat.player_state.target
        y = py + 4
        if target and getattr(target, 'alive', False):
            name = getattr(target, 'name', getattr(target, 'kind', '?'))
            hp = getattr(target, 'hp', 0)
            maxhp = getattr(target, 'max_hp', 1)
            self.screen.blit(font_sm.render(f"Target: {name} HP:{hp}/{maxhp}", True, RED), (px + 5, y))

            # Target HP bar
            y += 14
            bar_w = pw - 10
            pygame.draw.rect(self.screen, DARK_GRAY, (px + 5, y, bar_w, 6))
            hp_w = int(bar_w * hp / max(1, maxhp))
            pygame.draw.rect(self.screen, RED, (px + 5, y, hp_w, 6))
            y += 10

            # Highlight target on map
            tsx, tsy = self.camera.world_to_screen(target.x, target.y)
            pygame.draw.circle(self.screen, RED, (int(tsx), int(tsy)), 12, 2)
        else:
            self.screen.blit(font_sm.render("No target", True, GRAY), (px + 5, y))
            y += 14

        # Combat log (last few entries)
        y += 4
        for msg in self.combat.combat_log[-6:]:
            color = RED if "hit" in msg.lower() or "damage" in msg.lower() else \
                    (150, 150, 150) if "miss" in msg.lower() else GREEN
            text = msg[:32] if len(msg) > 32 else msg
            self.screen.blit(font_sm.render(text, True, color), (px + 5, y))
            y += 12

        # Instructions
        self.screen.blit(font_sm.render("[Space] Attack  [Esc] Disengage", True, (140, 140, 160)),
                        (px + 5, py + ph - 14))
        return

    def _draw_combat_ui_OLD(self):
        """Draw tactical combat overlay."""
        font_md = self.renderer.font_md
        font_sm = self.renderer.font_sm

        # Combat panel (right side)
        pw, ph = 280, SCREEN_HEIGHT - 20
        px = SCREEN_WIDTH - pw - 10
        py = 10
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((10, 10, 25, 220))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, (100, 50, 50), (px, py, pw, ph), 2)

        # Title
        title = font_md.render("TACTICAL COMBAT", True, RED)
        self.screen.blit(title, (px + pw // 2 - title.get_width() // 2, py + 5))

        # Turn order
        y = py + 30
        cc = self.combat.current_combatant
        for c in self.combat.turn_order:
            if not c.is_alive:
                continue
            is_current = c is cc
            color = YELLOW if is_current else (WHITE if (c.is_player or c.is_ally) else (200, 100, 100))
            marker = "> " if is_current else "  "
            side = "YOU" if c.is_player else ("ALLY" if c.is_ally else "FOE")
            text = f"{marker}{c.name} [{side}] HP:{c.entity.hp}/{c.entity.max_hp}"
            self.screen.blit(font_sm.render(text, True, color), (px + 5, y))
            y += 16

        # Current turn info
        if cc and (cc.is_player or cc.is_ally):
            y += 10
            pygame.draw.line(self.screen, (80, 80, 100), (px + 5, y), (px + pw - 5, y))
            y += 8
            self.screen.blit(font_md.render(f"{cc.name}'s Turn", True, YELLOW), (px + 10, y))
            y += 22

            # Resources
            res = []
            if cc.has_action:
                res.append("ACTION")
            if cc.has_bonus_action:
                res.append("BONUS")
            self.screen.blit(font_sm.render(f"Available: {', '.join(res) or 'None'}", True, UI_TEXT), (px + 10, y))
            y += 16
            self.screen.blit(font_sm.render(f"Movement: {cc.movement_remaining:.0f} tiles", True, UI_TEXT), (px + 10, y))
            y += 20

            # Actions
            self.screen.blit(font_sm.render("Actions:", True, UI_HIGHLIGHT), (px + 10, y))
            y += 16
            action_keys = [
                ("[1] Attack nearest", "attack"),
                ("[2] Cast spell", "spell"),
                ("[3] Dash", "dash"),
                ("[4] Dodge", "dodge"),
                ("[5] Use item", "item"),
                ("[Enter] End turn", "end"),
                ("[Esc] Flee combat", "flee"),
            ]
            for label, _ in action_keys:
                self.screen.blit(font_sm.render(label, True, (180, 180, 190)), (px + 15, y))
                y += 14

        # Combat log (bottom of panel)
        y = py + ph - 120
        pygame.draw.line(self.screen, (80, 80, 100), (px + 5, y), (px + pw - 5, y))
        y += 5
        self.screen.blit(font_sm.render("Combat Log:", True, GRAY), (px + 10, y))
        y += 14
        for msg in self.combat.combat_log[-6:]:
            color = RED if "damage" in msg.lower() or "hit" in msg.lower() else \
                    GREEN if "heal" in msg.lower() or "victory" in msg.lower() else UI_TEXT
            text = msg[:35] if len(msg) > 35 else msg
            self.screen.blit(font_sm.render(text, True, color), (px + 10, y))
            y += 13

        # Highlight current combatant on map
        if cc:
            sx, sy = self.camera.world_to_screen(cc.entity.x, cc.entity.y)
            pygame.draw.circle(self.screen, YELLOW, (int(sx), int(sy)), 18, 2)

    # Old turn-based combat handler removed - combat is now real-time

    def _cycle_overlay_mode(self):
        """Cycle entity overlay display: all -> minimal -> off -> all."""
        import game.settings as _s
        mode = getattr(self, '_overlay_mode', 0)
        mode = (mode + 1) % 3
        self._overlay_mode = mode

        if mode == 1:
            # Minimal: names + quest markers only
            _s.SHOW_NPC_NAMES = True
            _s.SHOW_NPC_ACTIONS = False
            _s.SHOW_NPC_STATUS = False
            _s.SHOW_NPC_CARGO = False
            _s.SHOW_SPEECH_BUBBLES = True
            _s.SHOW_QUEST_MARKERS = True
            _s.SHOW_CREATURE_LABELS = False
            _s.SHOW_NPC_CONVERSATIONS = False
            self.notifications.add("Overlays: MINIMAL (F6 to cycle)", 2.0, (180, 180, 220))
        elif mode == 2:
            # Off
            _s.SHOW_NPC_NAMES = False
            _s.SHOW_NPC_ACTIONS = False
            _s.SHOW_NPC_STATUS = False
            _s.SHOW_NPC_CARGO = False
            _s.SHOW_SPEECH_BUBBLES = False
            _s.SHOW_QUEST_MARKERS = False
            _s.SHOW_CREATURE_LABELS = False
            _s.SHOW_NPC_CONVERSATIONS = False
            self.notifications.add("Overlays: OFF (F6 to cycle)", 2.0, (180, 180, 220))
        else:
            # All on
            _s.SHOW_NPC_NAMES = True
            _s.SHOW_NPC_ACTIONS = True
            _s.SHOW_NPC_STATUS = True
            _s.SHOW_NPC_CARGO = True
            _s.SHOW_SPEECH_BUBBLES = True
            _s.SHOW_QUEST_MARKERS = True
            _s.SHOW_CREATURE_LABELS = True
            _s.SHOW_NPC_CONVERSATIONS = True
            self.notifications.add("Overlays: ALL (F6 to cycle)", 2.0, (180, 180, 220))

    def _toggle_view_mode(self):
        """Cycle through view modes: strategy -> adventure -> 3D -> strategy."""
        if self.view_mode == "strategy":
            # Switch to adventure mode
            if self.renderer_adventure is None:
                self.notifications.add("Loading adventure view...", 2.0, YELLOW)
                try:
                    from game.ui.renderer_adventure import AdventureRenderer
                    self.renderer_adventure = AdventureRenderer(self.screen)
                    self.renderer_adventure.build_minimap(self.world)
                except Exception as e:
                    self.notifications.add(f"Adventure view unavailable: {e}", 3.0, RED)
                    return
            self.view_mode = "adventure"
            self.active_renderer = self.renderer_adventure
            self.camera.set_tile_size(32)
            self.notifications.add("Adventure View (32px) — V to switch", 3.0, (100, 200, 255))

        elif self.view_mode == "adventure":
            # Switch to 3D OpenGL mode
            try:
                from game.ui.renderer_3d import Renderer3D
                from pygame.locals import DOUBLEBUF, OPENGL

                # Recreate display with OpenGL flags
                self.screen = pygame.display.set_mode(
                    (SCREEN_WIDTH, SCREEN_HEIGHT), DOUBLEBUF | OPENGL)
                self._update_screen_refs(self.screen)

                # Create 3D renderer
                if not hasattr(self, 'renderer_3d') or self.renderer_3d is None:
                    self.renderer_3d = Renderer3D(SCREEN_WIDTH, SCREEN_HEIGHT)
                    self.renderer_3d.set_world(self.world)
                else:
                    self.renderer_3d._init_gl()

                self.view_mode = "3d"
                self.active_renderer = self.renderer_3d

            except Exception as e:
                self.notifications.add(f"3D view unavailable: {e}", 3.0, RED)
                import traceback
                traceback.print_exc()
                return

        elif self.view_mode == "3d":
            # Switch back to strategy mode — recreate display without OpenGL
            self.screen = pygame.display.set_mode(
                (SCREEN_WIDTH, SCREEN_HEIGHT))
            self._update_screen_refs(self.screen)

            # Cleanup 3D renderer
            if hasattr(self, 'renderer_3d') and self.renderer_3d:
                self.renderer_3d.cleanup()

            self.view_mode = "strategy"
            self.active_renderer = self.renderer
            self.camera.set_tile_size(TILE_SIZE)

            # Rebuild tile caches (they reference the old screen)
            self.renderer.build_minimap(self.world)
            self.notifications.add("Strategy View (16px) — V to switch", 3.0, (200, 200, 100))

        else:
            # Fallback
            self.view_mode = "strategy"
            self.active_renderer = self.renderer
            self.camera.set_tile_size(TILE_SIZE)

    def _update_screen_refs(self, new_screen):
        """Update screen references after display mode change."""
        self.screen = new_screen
        self.renderer.screen = new_screen
        if self.renderer_adventure:
            self.renderer_adventure.screen = new_screen
        self.ui.screen = new_screen

    def _toggle_interior_zoom(self):
        """Toggle interior zoom view (64px) when inside a building."""
        interior_state = self.player.interior_state

        if interior_state.is_inside:
            # Exit interior zoom — back to overworld view
            interior_state.exit_building()
            interior_state.complete_exit()
            self.notifications.add("Exited interior view.", 1.5, (180, 180, 200))
        else:
            # Enter interior zoom — check building tracking first,
            # then fall back to searching structures and plan
            px_int, py_int = int(self.player.x), int(self.player.y)
            structure = None
            rect = self.player._current_building_rect
            bname = self.player._current_building_name
            bkind = self.player._current_building_kind

            if rect and bname:
                # Already tracked from walking in
                structure = type('S', (), {'name': bname, 'kind': bkind,
                                           'x': rect[0], 'y': rect[1]})()
            else:
                # Search structures (world + plan)
                for s in self.world.structures:
                    for bx, by, bw, bh in getattr(s, 'buildings', []):
                        if bx <= px_int < bx + bw and by <= py_int < by + bh:
                            structure = s
                            rect = (bx, by, bw, bh)
                            break
                    if structure:
                        break

                # Also check plan settlements (for chunked worlds)
                if not structure and hasattr(self.world, 'plan'):
                    for sp in self.world.plan.settlements:
                        # Quick AABB skip for distant settlements
                        if abs(sp.x - px_int) > sp.radius + 20 or abs(sp.y - py_int) > sp.radius + 20:
                            continue
                        for bld in sp.buildings:
                            bx, by = bld['x'], bld['y']
                            bw, bh = bld['w'], bld['h']
                            if bx <= px_int < bx + bw and by <= py_int < by + bh:
                                structure = type('S', (), {
                                    'name': sp.name, 'kind': sp.kind,
                                    'x': sp.x, 'y': sp.y})()
                                rect = (bx, by, bw, bh)
                                break
                        if structure:
                            break

            if structure and rect:
                tod = getattr(self.time_sys, 'normalized', 0.3)
                interior = interior_state.enter_building(
                    structure.name, structure.kind, structure.x, structure.y,
                    world=self.world, building_rect=rect,
                    npcs=self.world_mgr.npcs, time_of_day=tod)
                self.notifications.add(
                    f"Interior zoom: {structure.name} (Z to exit)",
                    2.0, (200, 200, 255))
            else:
                self.notifications.add(
                    "Not inside a building.", 1.5, (200, 150, 100))

    def _toggle_world_map(self):
        if self.ui.show_world_map:
            self.ui.world_map_view.close()
            self.ui.show_world_map = False
        else:
            self.ui.world_map_view.open(self.player.x, self.player.y)
            self.ui.show_world_map = True

    def _open_fast_travel(self):
        """Open fast travel menu if player is on a road tile."""
        from game.systems.fast_travel import is_on_road, get_reachable_settlements
        px, py = int(self.player.x), int(self.player.y)
        if not is_on_road(self.world, px, py):
            self.notifications.add("Stand on a road to fast travel. [Y]", 3.0, ORANGE)
            return
        # Get visited settlements from title tracker
        visited = set()
        if hasattr(self.player, 'title_tracker'):
            visited = self.player.title_tracker.settlements_visited
        destinations = get_reachable_settlements(
            self.world, self.player.x, self.player.y, visited)
        if not destinations:
            self.notifications.add("No visited settlements reachable by road.", 3.0, ORANGE)
            return
        self.fast_travel_ui.open(destinations)

    def _execute_fast_travel(self):
        """Execute the selected fast travel destination."""
        dest = self.fast_travel_ui.get_selected()
        if not dest:
            self.fast_travel_ui.close()
            return
        from game.systems.fast_travel import check_random_encounter, get_encounter_creatures
        self.fast_travel_ui.close()
        # Advance game time
        travel_minutes = dest["travel_minutes"]
        time_seconds = travel_minutes * 60  # game seconds
        self.time_sys.time += time_seconds
        # Random encounter check
        if check_random_encounter():
            # Spawn hostile creatures near destination
            from game.core.creature import Creature
            creatures = get_encounter_creatures(self.player.level)
            self.notifications.add("Ambushed during travel!", 4.0, RED)
            for cr_data in creatures:
                kind = cr_data["kind"]
                ox = dest["x"] + random.randint(-3, 3)
                oy = dest["y"] + random.randint(-3, 3)
                cr = Creature(float(ox), float(oy), kind)
                self.world_mgr.creatures.append(cr)
            self.combat_log_panel.add_message(
                f"Ambushed by {len(creatures)} creatures during travel!")
        # Teleport player
        self.player.x = float(dest["x"])
        self.player.y = float(dest["y"])
        self.camera.update(self.player.x, self.player.y)
        self.world.reveal_around(dest["x"], dest["y"], 12)
        self.notifications.add(
            f"Arrived at {dest['name']} ({travel_minutes:.0f} min travel).",
            4.0, GREEN)
        self.combat_log_panel.add_message(
            f"Fast traveled to {dest['name']}")

    def _open_pause_menu(self):
        """Open the in-game pause menu with options."""
        self.ui.paused = True
        result = self.menus.show_pause_menu()
        if result == "resume" or result is None:
            self.ui.paused = False
        elif result == "options":
            self.menus.show_options()
            self.ui.paused = False
        elif result == "save":
            self._save_game()
            self.notifications.add("Game saved.", 3.0, GREEN)
            self.ui.paused = False
        elif result == "load":
            self._load_game()
            self.ui.paused = False
        elif result == "quit_to_menu":
            self._save_game()
            self._shutdown()
            # Re-launch from title screen
            self.__init__()
        elif result == "quit_to_desktop":
            self._save_game()
            self.running = False
        else:
            self.ui.paused = False

    def _save_game(self):
        """Persist all game state."""
        try:
            self.db.save_all_npc_memories(self.world_mgr.npcs, self.time_sys.day)
            self.db.save_world_state("time", {"time": self.time_sys.time, "day": self.time_sys.day})
        except Exception:
            pass
        try:
            self.world.tiles.save_all_dirty()
        except Exception:
            pass
        try:
            from game.data.save_game import save_game
            save_game(self.world, self.player, "data/savegame.json")
        except Exception:
            pass

    def _load_game(self):
        """Load saved player state."""
        try:
            from game.data.save_game import load_game, apply_save_to_player
            save_data = load_game("data/savegame.json")
            if save_data:
                apply_save_to_player(self.player, save_data)
                self.notifications.add("Game loaded.", 3.0, GREEN)
            else:
                self.notifications.add("No save file found.", 3.0, RED)
        except Exception as e:
            self.notifications.add(f"Load failed: {e}", 3.0, RED)

    def _toggle_auto_play(self):
        self.auto_play = not self.auto_play
        if self.auto_play:
            self.notifications.add("AUTO-PLAY ON - Player acts autonomously (P to disable)", 4.0, YELLOW)
        else:
            self.notifications.add("AUTO-PLAY OFF - You have control", 3.0, GREEN)

    def _toggle_sound_mute(self):
        enabled = self.sound.toggle_sounds()
        if enabled:
            self.notifications.add("Sounds: ON (F8)", 2.0, GREEN)
        else:
            self.notifications.add("Sounds: OFF (F8)", 2.0, GRAY)

    def _toggle_music_mute(self):
        enabled = self.sound.toggle_music()
        if enabled:
            self.notifications.add("Music: ON (F9)", 2.0, GREEN)
        else:
            self.notifications.add("Music: OFF (F9)", 2.0, GRAY)

    def _handle_quest_board_input(self, key):
        """Handle keyboard input while quest board panel is open."""
        listings = self.quest_board_listings
        if not listings:
            self.quest_board_active = False
            return

        if key == pygame.K_UP or key == pygame.K_w:
            self.quest_board_selected = max(0, self.quest_board_selected - 1)
        elif key == pygame.K_DOWN or key == pygame.K_s:
            self.quest_board_selected = min(len(listings) - 1,
                                            self.quest_board_selected + 1)
        elif key == pygame.K_RETURN or key == pygame.K_e:
            # Accept selected quest
            idx = listings[self.quest_board_selected]["index"]
            quest = self.quest_board_mgr.accept_quest(
                self.quest_board_settlement, idx, self.quest_sys)
            if quest:
                self.notifications.add(
                    f"Quest accepted: {quest.title}", 4.0, YELLOW)
                self.quest_board_active = False
            else:
                self.notifications.add(
                    "Quest log full! (max 10)", 3.0, RED)
        elif key == pygame.K_ESCAPE or key == pygame.K_q:
            self.quest_board_active = False

    def _draw_quest_board(self):
        """Draw the quest board panel overlay."""
        listings = self.quest_board_listings
        if not listings:
            return

        screen = self.screen
        sw, sh = screen.get_size()

        # Panel dimensions
        pw, ph = min(500, sw - 40), min(420, sh - 80)
        px = (sw - pw) // 2
        py = (sh - ph) // 2

        # Background
        panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel_surf.fill((20, 15, 10, 230))
        screen.blit(panel_surf, (px, py))

        # Border
        pygame.draw.rect(screen, (160, 130, 80), (px, py, pw, ph), 2)

        # Title
        title_font = pygame.font.SysFont("monospace", 18, bold=True)
        body_font = pygame.font.SysFont("monospace", 13)
        small_font = pygame.font.SysFont("monospace", 11)

        title = title_font.render(
            f"Quest Board - {self.quest_board_settlement}", True,
            (220, 200, 140))
        screen.blit(title, (px + 10, py + 8))

        # Separator
        pygame.draw.line(screen, (120, 100, 60),
                         (px + 10, py + 32), (px + pw - 10, py + 32))

        # Quest listings
        y_off = py + 40
        for i, listing in enumerate(listings):
            selected = (i == self.quest_board_selected)
            bg_color = (60, 50, 30, 180) if selected else (30, 25, 15, 100)

            entry_h = 70
            entry_surf = pygame.Surface((pw - 20, entry_h), pygame.SRCALPHA)
            entry_surf.fill(bg_color)
            screen.blit(entry_surf, (px + 10, y_off))

            if selected:
                pygame.draw.rect(screen, (200, 170, 80),
                                 (px + 10, y_off, pw - 20, entry_h), 1)

            # Quest title
            color = (255, 220, 120) if selected else (200, 190, 150)
            t = body_font.render(listing["title"], True, color)
            screen.blit(t, (px + 16, y_off + 4))

            # Type and difficulty
            kind_colors = {
                "kill": (200, 80, 80), "fetch": (80, 180, 80),
                "deliver": (80, 140, 220), "escort": (200, 160, 60),
                "investigate": (160, 100, 200),
            }
            kind_color = kind_colors.get(listing["kind"], (180, 180, 180))
            kind_text = listing["kind"].upper()
            diff_text = listing["difficulty"].upper()
            info = small_font.render(
                f"[{kind_text}] [{diff_text}]", True, kind_color)
            screen.blit(info, (px + 16, y_off + 22))

            # Description (truncated)
            desc = listing["description"]
            if len(desc) > 60:
                desc = desc[:57] + "..."
            d = small_font.render(desc, True, (170, 170, 160))
            screen.blit(d, (px + 16, y_off + 38))

            # Rewards
            reward_text = f"Reward: {listing['reward_gold']}g, {listing['reward_xp']} XP"
            r = small_font.render(reward_text, True, (220, 200, 80))
            screen.blit(r, (px + 16, y_off + 52))

            y_off += entry_h + 4

        # Instructions
        help_y = py + ph - 22
        help_text = small_font.render(
            "[W/S] Navigate  [E/Enter] Accept  [Esc] Close", True,
            (150, 140, 110))
        screen.blit(help_text, (px + 10, help_y))

    def _handle_board_menu_input(self, key):
        """Handle input for quest-board / message-board selection menu."""
        if key == pygame.K_1:
            self.board_menu_active = False
            from game.actions import _open_quest_board
            _open_quest_board(self, self.board_menu_quest_board)
        elif key == pygame.K_2:
            self.board_menu_active = False
            from game.actions import _open_message_board
            _open_message_board(self, self.board_menu_msg_board)
        elif key == pygame.K_ESCAPE or key == pygame.K_q:
            self.board_menu_active = False

    def _handle_msg_board_input(self, key):
        """Handle keyboard input while message board panel is open."""
        listings = self.msg_board_listings
        if not listings:
            self.msg_board_active = False
            return

        if key == pygame.K_UP or key == pygame.K_w:
            self.msg_board_selected = max(0, self.msg_board_selected - 1)
        elif key == pygame.K_DOWN or key == pygame.K_s:
            self.msg_board_selected = min(len(listings) - 1,
                                          self.msg_board_selected + 1)
        elif key == pygame.K_ESCAPE or key == pygame.K_q:
            self.msg_board_active = False

    def _draw_message_board(self):
        """Draw the message board panel overlay."""
        listings = self.msg_board_listings
        if not listings:
            return

        screen = self.screen
        sw, sh = screen.get_size()

        pw, ph = min(520, sw - 40), min(460, sh - 80)
        px = (sw - pw) // 2
        py_top = (sh - ph) // 2

        # Background
        panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel_surf.fill((15, 18, 28, 230))
        screen.blit(panel_surf, (px, py_top))

        # Border
        pygame.draw.rect(screen, (100, 120, 180), (px, py_top, pw, ph), 2)

        title_font = pygame.font.SysFont("monospace", 18, bold=True)
        body_font = pygame.font.SysFont("monospace", 13)
        small_font = pygame.font.SysFont("monospace", 11)

        title = title_font.render(
            f"Message Board - {self.msg_board_settlement}", True,
            (160, 170, 220))
        screen.blit(title, (px + 10, py_top + 8))

        pygame.draw.line(screen, (80, 90, 140),
                         (px + 10, py_top + 32),
                         (px + pw - 10, py_top + 32))

        y_off = py_top + 40
        for i, listing in enumerate(listings):
            selected = (i == self.msg_board_selected)
            bg_color = (40, 45, 65, 180) if selected else (25, 28, 40, 100)

            entry_h = 62
            entry_surf = pygame.Surface((pw - 20, entry_h), pygame.SRCALPHA)
            entry_surf.fill(bg_color)
            screen.blit(entry_surf, (px + 10, y_off))

            if selected:
                pygame.draw.rect(screen, (140, 160, 220),
                                 (px + 10, y_off, pw - 20, entry_h), 1)

            # Category tag
            cat_color = listing.get("color", (180, 180, 180))
            cat_text = small_font.render(
                f"[{listing['category_label']}]", True, cat_color)
            screen.blit(cat_text, (px + 16, y_off + 4))

            # Title
            color = (230, 230, 240) if selected else (190, 190, 200)
            t = body_font.render(listing["title"], True, color)
            screen.blit(t, (px + 16, y_off + 18))

            # Body (truncated)
            body = listing["body"]
            if len(body) > 65:
                body = body[:62] + "..."
            d = small_font.render(body, True, (150, 155, 170))
            screen.blit(d, (px + 16, y_off + 35))

            # Poster
            p = small_font.render(f"- {listing['poster']}", True, (120, 120, 140))
            screen.blit(p, (px + 16, y_off + 48))

            y_off += entry_h + 3

        help_y = py_top + ph - 22
        help_text = small_font.render(
            "[W/S] Navigate  [Esc] Close", True, (120, 130, 160))
        screen.blit(help_text, (px + 10, help_y))

    def _process_dialog_result(self, npc, result: str):
        """Process a dialog choice - trigger game mechanics AND generate memories."""
        if not npc:
            return

        name = npc.name
        cc = getattr(npc, 'char_class', npc.profession)

        # === HEALING ===
        if result == "heal_done":
            heal = 20 + getattr(npc, 'level', 1) * 3
            self.player.heal(heal)
            self.notifications.add(f"{name} healed you for {heal} HP!", 3.0, GREEN)
            npc.add_memory("social", f"Healed the player's wounds", 3)
            npc.player_relationship = min(100, npc.player_relationship + 5)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 10)

        elif result == "blessing":
            self.player.heal(10)
            self.notifications.add(f"{name} blessed you! +10 HP", 2.0, GREEN)
            npc.add_memory("social", "Blessed the player with divine protection", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)

        # === LEARNING ===
        elif result == "learn_done":
            if hasattr(npc, 'npc_skills'):
                top = sorted(npc.npc_skills.items(), key=lambda x: -x[1])
                if top:
                    skill = top[0][0]
                    self.player.gain_skill_xp(skill, 2.0)
                    self.notifications.add(f"{name} taught you about {skill}!", 3.0, GREEN)
                    npc.add_memory("teaching", f"Taught the player about {skill}", 3)
                    npc.player_relationship = min(100, npc.player_relationship + 5)
                    from game.systems.skills import gain_skill_xp
                    gain_skill_xp(npc, "leadership", 0.5)

        # === QUEST ===
        elif result == "accept_quest":
            # If NPC has no formal quest, generate one from their goals/profession
            if not npc.quest:
                self.quest_sys.generate_quest_for_npc(npc)
                npc.regenerate_dialog()
            if npc.quest and not npc.quest.turned_in:
                already_have = npc.quest.title in [q.title for q in self.quest_sys.active_quests]
                if already_have:
                    self.notifications.add("You already have this quest.", 2.0, GRAY)
                elif self.quest_sys.accept_quest(npc.quest):
                    self.notifications.add(f"New quest: {npc.quest.title}", 4.0, YELLOW)
                    npc.add_memory("quest", "The player accepted a task from me", 3)
                    npc.player_relationship = min(100, npc.player_relationship + 3)
                else:
                    self.notifications.add("Quest log full! (max 10)", 3.0, RED)
            else:
                self.notifications.add("Quest accepted!", 3.0, YELLOW)
                npc.add_memory("quest", "The player accepted a task from me", 3)
                npc.player_relationship = min(100, npc.player_relationship + 3)

        elif result == "quest_complete":
            # Player claims to have finished a quest
            if npc.quest and npc.quest.completed and not npc.quest.turned_in:
                turn_in_result = self.quest_sys.turn_in_quest(npc.quest, self.player)
                if turn_in_result:
                    self.sound.play("quest_complete")
                    self.notifications.add(turn_in_result, 4.0, GREEN)
                    npc.has_quest_marker = False
                    npc.add_memory("quest", "The player completed my task! Grateful.", 5)
                    npc.player_relationship = min(100, npc.player_relationship + 10)
            else:
                self.notifications.add("You haven't completed this task yet.", 3.0, ORANGE)

        elif result == "quest_reward":
            npc.add_memory("social", "The player asked about rewards. Practical type.", 1)

        # === NPC JOB QUEST GIVERS ===
        elif result == "guard_bounty_quest":
            from game.systems.quest_board_init import generate_guard_quest
            settlement = getattr(npc, 'home_settlement', '')
            quest = generate_guard_quest(
                npc.name, settlement,
                getattr(self.player, 'level', 1))
            if self.quest_sys.accept_quest(quest):
                self.notifications.add(f"New quest: {quest.title}", 4.0, YELLOW)
                self.notifications.add(
                    f"Reward: {quest.reward_gold}g, {quest.reward_xp} XP",
                    3.0, (220, 200, 80))
                npc.add_memory("quest", "Gave the player a bounty contract", 3)
                npc.player_relationship = min(100, npc.player_relationship + 3)
            else:
                self.notifications.add("Quest log full! (max 10)", 3.0, RED)

        elif result == "merchant_delivery_quest":
            from game.systems.quest_board_init import generate_merchant_quest
            settlement = getattr(npc, 'home_settlement', '')
            # Find nearby settlements for delivery destination
            nearby = []
            if hasattr(self.world, 'plan'):
                for sp in self.world.plan.settlements:
                    if sp.name != settlement:
                        nearby.append(sp.name)
            if not nearby:
                nearby = ["a nearby town"]
            quest = generate_merchant_quest(
                npc.name, settlement, nearby,
                getattr(self.player, 'level', 1))
            if self.quest_sys.accept_quest(quest):
                self.notifications.add(f"New quest: {quest.title}", 4.0, YELLOW)
                self.notifications.add(
                    f"Reward: {quest.reward_gold}g, {quest.reward_xp} XP",
                    3.0, (220, 200, 80))
                npc.add_memory("quest", "Hired the player for a delivery", 3)
                npc.player_relationship = min(100, npc.player_relationship + 3)
            else:
                self.notifications.add("Quest log full! (max 10)", 3.0, RED)

        elif result == "scholar_investigation_quest":
            from game.systems.quest_board_init import generate_scholar_quest
            settlement = getattr(npc, 'home_settlement', '')
            quest = generate_scholar_quest(
                npc.name, settlement,
                getattr(self.player, 'level', 1))
            if self.quest_sys.accept_quest(quest):
                self.notifications.add(f"New quest: {quest.title}", 4.0, YELLOW)
                self.notifications.add(
                    f"Reward: {quest.reward_gold}g, {quest.reward_xp} XP",
                    3.0, (220, 200, 80))
                npc.add_memory("quest", "Sent the player to investigate the ruins", 3)
                npc.player_relationship = min(100, npc.player_relationship + 3)
            else:
                self.notifications.add("Quest log full! (max 10)", 3.0, RED)

        # === RECRUITMENT ===
        elif result == "recruit_offer":
            # Actually attempt to recruit the NPC
            recruited = False
            if hasattr(self, 'party'):
                recruited = self.party.try_recruit(npc)
            if recruited:
                self.notifications.add(f"{name} joins your party!", 3.0, GREEN)
                npc.add_memory("social", "I joined the player's party!", 5)
                npc.player_relationship = min(100, npc.player_relationship + 10)
            else:
                npc.add_memory("social", "The player asked me to join their party", 3)
                npc.player_relationship = min(100, npc.player_relationship + 2)
                if hasattr(self, 'party') and len(self.party.companions) >= self.party.max_companions:
                    self.notifications.add("Party is full! Dismiss someone first.", 3.0, ORANGE)
                elif npc.player_relationship < 15:
                    self.notifications.add(f"{name} doesn't trust you enough yet. (need 15+ relationship)", 3.0, ORANGE)
                else:
                    self.notifications.add(f"Press R near {name} to recruit.", 2.0, YELLOW)

        # === ABOUT SELF / PERSONAL ===
        elif result == "about_self":
            npc.add_memory("social", "Had a personal conversation with the player", 2)
            npc.player_relationship = min(100, npc.player_relationship + 2)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 8)

        elif result == "goals_detail":
            npc.add_memory("social", "Shared my goals and dreams with the player", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 5)

        elif result == "backstory" or result == "backstory_deep":
            npc.add_memory("social", "Told the player my life story. Felt good to share.", 3)
            npc.player_relationship = min(100, npc.player_relationship + 5)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 15)

        elif result == "friends_talk":
            npc.add_memory("social", "Talked about my friends with the player", 1)
            npc.player_relationship = min(100, npc.player_relationship + 2)

        elif result == "enemies_talk" or result == "enemy_story":
            npc.add_memory("social", "Confided about my enemies to the player", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)

        # === NEWS / INFORMATION ===
        elif result == "local_news" or result == "more_news":
            npc.add_memory("social", "Shared local news with the player", 1)
            npc.player_relationship = min(100, npc.player_relationship + 1)
            # Player learns what NPC knows
            for info in npc.known_info[-3:]:
                if hasattr(self, 'simulation') and hasattr(self.simulation, 'info'):
                    self.simulation.info.player_witnesses(
                        f"{name} told you: {info}", "gossip", 1, self.time_sys.day)

        elif result == "guard_report":
            npc.add_memory("duty", "Gave the player a security briefing", 2)
            npc.player_relationship = min(100, npc.player_relationship + 2)

        elif result == "kingdom_report":
            npc.add_memory("political", "Discussed the state of the kingdom with the player", 3)
            npc.player_relationship = min(100, npc.player_relationship + 3)

        # === TRADE / BARTER ===
        elif result == "barter" or result == "shop":
            npc.add_memory("trade", "The player wanted to trade with me", 1)
            # Shop UI is opened by handle_dialog_input when next_key == "shop"
            # No need to open it here (would be redundant)

        # === CLASS-SPECIFIC ===
        elif result == "bard_perform":
            npc.add_memory("social", "Performed a song for the player. Good audience!", 2)
            npc.player_relationship = min(100, npc.player_relationship + 4)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 15)
            from game.systems.skills import gain_skill_xp
            gain_skill_xp(npc, "trading", 0.5)  # performing builds charisma

        elif result == "bard_legend" or result == "great_war_story":
            npc.add_memory("social", "Told the player ancient legends", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)
            self.player.gain_skill_xp("history", 1.0)

        elif result == "magic_talk" or result == "ruin_lore":
            npc.add_memory("social", "Discussed magic and arcane theory with the player", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)

        elif result == "rogue_deal" or result == "rogue_detail" or result == "rogue_map":
            npc.add_memory("social", "Shared a secret opportunity with the player", 3)
            npc.player_relationship = min(100, npc.player_relationship + 4)

        elif result == "monk_wisdom" or result == "monk_training":
            npc.add_memory("teaching", "Shared wisdom with the player", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)

        elif result == "warlock_patron" or result == "warlock_power" or result == "warlock_cost":
            npc.add_memory("social", "Confided about my patron to the player. Risky.", 3)
            npc.player_relationship = min(100, npc.player_relationship + 5)

        elif result == "consciousness" or result == "consciousness_deep":
            npc.add_memory("philosophical", "Discussed the nature of reality with the player", 4)
            npc.player_relationship = min(100, npc.player_relationship + 5)
            npc.awareness_points += 1.0

        elif result == "help_with_goal":
            npc.add_memory("social", "The player offered to help me with my goals!", 4)
            npc.player_relationship = min(100, npc.player_relationship + 8)

        elif result == "offer_help_threat":
            npc.add_memory("social", "The player volunteered to help with local threats!", 3)
            npc.player_relationship = min(100, npc.player_relationship + 5)

        elif result == "kingdom_service":
            npc.add_memory("political", "The player offered service to the crown", 3)
            npc.player_relationship = min(100, npc.player_relationship + 5)

        elif result == "intro_friends":
            npc.add_memory("social", "Introduced the player to my friends", 2)
            npc.player_relationship = min(100, npc.player_relationship + 3)
            # Spread good reputation to friends
            for friend_name in getattr(npc, 'friends', [])[:3]:
                for other in self.world_mgr.npcs:
                    if other.name == friend_name and other.alive:
                        other.player_relationship = min(100, other.player_relationship + 3)
                        other.add_memory("social", f"{npc.name} introduced the player to me. Seems trustworthy.", 2)
                        break

        # === NEGATIVE OUTCOMES ===
        elif result == "insult":
            npc.add_memory("conflict", "The player insulted me!", 4)
            npc.player_relationship = max(-100, npc.player_relationship - 15)
            npc.mood = max(-1.0, getattr(npc, 'mood', 0) - 0.3)
            self.notifications.add(f"{name} is offended!", 3.0, RED)
            # Spread to friends
            for fname in getattr(npc, 'friends', [])[:3]:
                for other in self.world_mgr.npcs:
                    if other.name == fname and other.alive:
                        other.player_relationship = max(-100, other.player_relationship - 5)
                        other.add_memory("social", f"{name} told me the player was rude to them", 2)
                        break

        elif result == "threaten":
            npc.add_memory("conflict", "The player threatened me!", 5)
            npc.player_relationship = max(-100, npc.player_relationship - 25)
            npc.mood = max(-1.0, getattr(npc, 'mood', 0) - 0.5)
            self.notifications.add(f"{name} is afraid and angry!", 3.0, RED)
            if npc.bravery > 0.6:
                npc.combat_target = self.player
                npc.current_action = "fighting"
                npc.state = "fighting"
                self.notifications.add(f"{name} attacks you!", 3.0, RED)
            else:
                npc.flee_from(self.player.x, self.player.y)
            # All nearby NPCs turn hostile
            for other in self.world_mgr.npcs:
                if other is npc or not other.alive:
                    continue
                if self.player.dist_to(other) < 12:
                    other.player_relationship = max(-100, other.player_relationship - 10)
                    other.add_memory("witness", "Saw the player threaten someone!", 3)

        elif result == "demand_gold":
            if npc.npc_gold > 5 and npc.bravery < 0.4:
                # Coward pays up
                amount = min(10, int(npc.npc_gold * 0.5))
                npc.npc_gold -= amount
                self.player.gold += amount
                npc.add_memory("conflict", f"The player demanded {amount} gold from me. I paid out of fear.", 5)
                npc.player_relationship = max(-100, npc.player_relationship - 20)
                self.notifications.add(f"{name} reluctantly gives you {amount} gold.", 3.0, ORANGE)
            else:
                npc.add_memory("conflict", "The player tried to extort me!", 5)
                npc.player_relationship = max(-100, npc.player_relationship - 20)
                self.notifications.add(f"{name} refuses and is furious!", 3.0, RED)
                if npc.bravery > 0.5:
                    npc.combat_target = self.player
                    npc.current_action = "fighting"
                    self.notifications.add(f"{name} attacks!", 2.0, RED)

        elif result == "lie":
            # Player lied - NPC may detect it based on wisdom
            wisdom = npc.attributes.get("wisdom", 5)
            detected = random.random() < (wisdom * 0.08 + 0.2)
            if detected:
                npc.add_memory("conflict", "The player tried to deceive me. I saw through it.", 4)
                npc.player_relationship = max(-100, npc.player_relationship - 12)
                self.notifications.add(f"{name} sees through your deception!", 3.0, RED)
            else:
                npc.add_memory("social", "Spoke with the player. Seemed sincere.", 1)
                npc.player_relationship = min(100, npc.player_relationship + 1)

        elif result == "refuse_help":
            npc.add_memory("social", "Asked the player for help but they refused", 2)
            npc.player_relationship = max(-100, npc.player_relationship - 5)
            npc.mood = max(-1.0, getattr(npc, 'mood', 0) - 0.1)

        elif result == "mock_beliefs":
            npc.add_memory("conflict", "The player mocked my beliefs! Deeply hurtful.", 5)
            npc.player_relationship = max(-100, npc.player_relationship - 20)
            npc.mood = max(-1.0, getattr(npc, 'mood', 0) - 0.4)
            self.notifications.add(f"{name} is deeply offended!", 3.0, RED)

        elif result == "reject_quest":
            title = getattr(npc, 'title', 'commoner')
            is_ruler = getattr(npc, 'is_ruler', False)
            rel_penalty = -3
            emotion_hit = 0.1

            if is_ruler or title in ('ruler', 'king', 'queen', 'lord', 'duke'):
                # Refusing a ruler is a serious insult
                rel_penalty = -15
                emotion_hit = 0.4
                npc.add_memory("political",
                    "The player refused a direct request from me. Insolent!", 5)
                self.notifications.add(
                    f"{name} is displeased by your refusal! (-15 reputation)", 4.0, RED)
                # Ruler tells guards to watch you
                for other in self.world_mgr.npcs:
                    if other is npc or not other.alive:
                        continue
                    other_title = getattr(other, 'title', '')
                    if other_title in ('guard', 'knight', 'captain') and other.dist_to(npc) < 30:
                        other.player_relationship = max(-100,
                            other.player_relationship - 8)
                        other.add_memory("duty",
                            f"The ruler {name} was angered by the player. Keep watch.", 3)
            elif title in ('guard', 'captain', 'knight'):
                rel_penalty = -8
                emotion_hit = 0.25
                npc.add_memory("duty",
                    "The player refused to help with security matters", 3)
                self.notifications.add(
                    f"{name} notes your refusal. Guards will remember.", 3.0, ORANGE)
            elif npc.player_relationship > 30:
                # Rejecting a friend hurts more
                rel_penalty = -8
                emotion_hit = 0.3
                npc.add_memory("social",
                    "I asked my friend for help and they refused. Disappointing.", 4)
                self.notifications.add(
                    f"{name} is hurt by your refusal.", 3.0, ORANGE)
            else:
                npc.add_memory("social",
                    "The player turned down my request for help", 2)

            npc.player_relationship = max(-100, npc.player_relationship + rel_penalty)

            # Emotional reaction
            es = getattr(npc, 'emotion_state', None)
            if es and hasattr(es, 'primary'):
                if is_ruler or title in ('guard', 'knight', 'captain'):
                    es.primary["anger"] = min(1.0,
                        es.primary.get("anger", 0) + emotion_hit)
                else:
                    es.primary["sadness"] = min(1.0,
                        es.primary.get("sadness", 0) + emotion_hit)

        elif result == "steal_attempt":
            # Try to steal from NPC during conversation
            dex = self.player.ability_scores.get("dexterity", 10)
            from game.data.dnd import ability_modifier
            roll = random.randint(1, 20) + ability_modifier(dex)
            perception = npc.attributes.get("perception", 5)
            dc = 10 + perception

            if roll >= dc:
                # Steal succeeded
                if npc.npc_inventory:
                    stolen = npc.npc_inventory.pop(random.randint(0, len(npc.npc_inventory) - 1))
                    self.player.add_item(stolen)
                    self.notifications.add(f"Stole {stolen.name} from {name}!", 3.0, ORANGE)
                    self.player.gain_skill_xp("pickpocketing", 1.0)
                else:
                    self.notifications.add("Nothing to steal.", 2.0, GRAY)
            else:
                # Caught!
                npc.add_memory("conflict", "The player tried to steal from me!", 5)
                npc.player_relationship = max(-100, npc.player_relationship - 30)
                self.notifications.add(f"{name} caught you stealing! ({roll} vs DC {dc})", 3.0, RED)
                if npc.bravery > 0.3:
                    npc.combat_target = self.player
                    npc.current_action = "fighting"
                    self.notifications.add(f"{name} attacks!", 2.0, RED)
                # Alert guards
                for other in self.world_mgr.npcs:
                    if other is npc or not other.alive:
                        continue
                    if self.player.dist_to(other) < 15:
                        title = getattr(other, 'title', '')
                        if title in ('guard', 'knight'):
                            other.add_memory("crime", f"{name} reported the player tried to steal!", 4)
                            other.player_relationship = max(-100, other.player_relationship - 15)
                            other.combat_target = self.player
                            other.current_action = "fighting"

        # === PLAYER-ASSIGNED TASKS ===
        elif result in ("task_kill", "task_fetch", "task_scout",
                         "task_guard", "task_deliver"):
            # Check willingness
            if npc.player_relationship < 10 and result != "task_bribe_50":
                self.notifications.add(f"{name} doesn't trust you enough.", 3.0, ORANGE)
            else:
                task_kind = result.replace("task_", "")
                task_desc, target_count = {
                    "kill":    ("Hunt creatures nearby", 3),
                    "fetch":   ("Gather supplies", 5),
                    "scout":   ("Scout the surrounding area", 1),
                    "guard":   ("Guard this area", 1),
                    "deliver": ("Deliver items", 1),
                }.get(task_kind, ("Do a task", 1))
                npc.player_task = {
                    "kind": task_kind,
                    "target": task_kind,
                    "progress": 0,
                    "target_count": target_count,
                    "description": task_desc,
                    "reward_gold": 0,
                }
                npc.player_task_timer = 0.0
                npc.current_goal = f"player_task_{task_kind}"
                npc.add_memory("quest",
                    f"The player asked me to {task_desc.lower()}. I accepted.", 3)
                self.notifications.add(
                    f"{name} accepts your task: {task_desc}", 3.0, GREEN)
                npc.player_relationship = min(100, npc.player_relationship + 2)

        elif result == "task_bribe_50" or result == "task_bribe_100":
            amount = 50 if result == "task_bribe_50" else 100
            if self.player.gold >= amount:
                self.player.gold -= amount
                npc.npc_gold += amount
                npc.player_relationship = min(100, npc.player_relationship + 5)
                npc.add_memory("trade",
                    f"The player paid me {amount} gold for a job", 3)
                self.notifications.add(f"Paid {name} {amount} gold.", 2.0, YELLOW)
            else:
                self.notifications.add("Not enough gold!", 2.0, RED)

        elif result == "task_collect":
            # Player collects completed task results
            if npc.player_task and npc.player_task.get("progress", 0) >= \
                    npc.player_task.get("target_count", 1):
                task = npc.player_task
                reward = task.get("reward_gold", 0)
                kind = task.get("kind", "")
                # Give player the gathered items
                if kind == "fetch":
                    from game.core.items import make_item
                    gather_items = ["Bread", "Herbs", "Wood", "Stone", "Apple"]
                    for i in range(min(3, task["target_count"])):
                        item = make_item(random.choice(gather_items))
                        self.player.add_item(item)
                    self.notifications.add(
                        f"{name} hands over gathered supplies!", 3.0, GREEN)
                elif kind == "scout":
                    # Add knowledge to player
                    for info in npc.known_info[-3:]:
                        if hasattr(self, 'simulation') and hasattr(self.simulation, 'info'):
                            self.simulation.info.player_witnesses(
                                f"{name} scouted: {info}", "scout", 2,
                                self.time_sys.day)
                    self.notifications.add(
                        f"{name} reports scouting findings!", 3.0, GREEN)
                elif kind == "kill":
                    xp = task["target_count"] * 10
                    self.player.gain_xp(xp)
                    self.notifications.add(
                        f"{name} cleared {task['target_count']} creatures! +{xp} XP", 3.0, GREEN)

                npc.player_task = None
                npc.current_goal = ""
                npc.add_memory("quest",
                    "Completed the task the player gave me. Feels good.", 4)
                npc.player_relationship = min(100, npc.player_relationship + 5)
                self.notifications.add(
                    f"Task completed by {name}!", 3.0, GREEN)

        elif result == "task_cancel":
            if npc.player_task:
                npc.player_task = None
                npc.current_goal = ""
                npc.add_memory("social",
                    "The player cancelled my task. Waste of time.", 2)
                npc.player_relationship = max(-100, npc.player_relationship - 3)

        elif result == "task_assign":
            # Just navigating to the menu — no action needed
            pass

        elif result == "task_refuse":
            npc.add_memory("social",
                "I turned down a task from the player. Not my thing.", 1)

        # === EMOTION / NEEDS / GOSSIP / DEEP CONVERSATIONS ===
        elif result == "emotion_talk" or result == "emotion_detail":
            npc.add_memory("social", "The player asked about my feelings. Thoughtful.", 3)
            npc.player_relationship = min(100, npc.player_relationship + 4)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 15)
            # Emotional catharsis - reduce negative emotions
            es = getattr(npc, 'emotion_state', None)
            if es and hasattr(es, 'primary'):
                for neg in ("sadness", "anger", "fear"):
                    if es.primary.get(neg, 0) > 0.3:
                        es.primary[neg] = max(0, es.primary[neg] - 0.15)

        elif result == "emotion_help":
            npc.add_memory("social", "The player offered to help with my troubles", 4)
            npc.player_relationship = min(100, npc.player_relationship + 6)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 20)

        elif result == "needs_hunger":
            npc.add_memory("social", "The player noticed I was hungry and showed concern", 3)
            npc.player_relationship = min(100, npc.player_relationship + 3)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 10)

        elif result == "needs_social":
            npc.add_memory("social", "The player stopped to talk when I was lonely", 4)
            npc.player_relationship = min(100, npc.player_relationship + 5)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 25)

        elif result == "gossip" or result == "gossip_more":
            npc.add_memory("social", "Shared gossip with the player", 1)
            npc.player_relationship = min(100, npc.player_relationship + 2)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 8)
            # Player learns gossip as known_info
            if hasattr(self, 'simulation') and hasattr(self.simulation, 'info'):
                for info in npc.known_info[-2:]:
                    self.simulation.info.player_witnesses(
                        f"{name} gossiped: {info}", "gossip", 1, self.time_sys.day)

        elif result == "deep_talk" or result == "deep_bond" or result == "deep_empathy":
            npc.add_memory("social", "Had a deep personal conversation with the player. Meaningful.", 5)
            npc.player_relationship = min(100, npc.player_relationship + 6)
            npc.needs["social"] = min(100, npc.needs.get("social", 50) + 20)
            # Deep conversations may trigger emotional bonds
            es = getattr(npc, 'emotion_state', None)
            if es and hasattr(es, 'bonds'):
                es.bonds["player"] = {"emotion": "trust", "intensity": min(1.0,
                    es.bonds.get("player", {}).get("intensity", 0) + 0.2),
                    "cause": "meaningful conversation"}

        # === GIFT (handled by gift panel, but process the result key too) ===
        elif result == "gift":
            pass  # Gift panel handles this via handle_gift_input

        # === GOODBYE ===
        elif result == "goodbye":
            if npc.player_relationship > 20:
                npc.add_memory("social", "Had a pleasant conversation with the player", 1)
            elif npc.player_relationship < -10:
                npc.add_memory("social", "The player left. Good riddance.", 1)

    def _cycle_nearby_npc(self):
        """Tab cycles through nearby NPCs for targeting."""
        nearby = []
        for npc in self.world_mgr.npcs:
            if npc.alive and self.player.dist_to(npc) < 8:
                if hasattr(self, 'party') and npc in self.party.companions:
                    continue
                nearby.append(npc)
        if not nearby:
            self.notifications.add("No one nearby.", 1.5, GRAY)
            return
        # Cycle: find current nearby_npc and go to next
        if self.nearby_npc in nearby:
            idx = nearby.index(self.nearby_npc)
            self.nearby_npc = nearby[(idx + 1) % len(nearby)]
        else:
            self.nearby_npc = nearby[0]
        name = self.nearby_npc.name
        cls = f"{getattr(self.nearby_npc, 'race', '')} {getattr(self.nearby_npc, 'char_class', '')}"
        self.notifications.add(f"Selected: {name} ({cls})", 2.0, UI_HIGHLIGHT)

    def _recruit_companion(self):
        if not self.nearby_npc or not self.nearby_npc.alive:
            self.notifications.add("No NPC nearby to recruit.", 2.0, GRAY)
            return
        cha = self.player.ability_scores.get("charisma", 10)
        success, msg = self.party.try_recruit(self.nearby_npc, cha)
        color = GREEN if success else ORANGE
        self.notifications.add(msg, 3.0, color)
        if success:
            self.player.gain_skill_xp("persuasion", 1.0)

    def _start_tactical_combat(self, enemies: list):
        """Initiate tactical combat with nearby enemies."""
        allies = self.party.get_allies_for_combat()
        self.combat.start(self.player, allies, enemies, self.world)
        self.notifications.add("COMBAT! Turn-based mode activated.", 3.0, RED)

    def _respawn(self):
        self.dead = False
        self.player.hp = self.player.max_hp // 2
        self.player.energy = self.player.max_energy
        sx, sy = self.world.spawn_point
        self.player.x = float(sx)
        self.player.y = float(sy)
        lost = self.player.gold // 4
        self.player.gold -= lost
        if lost > 0:
            self.notifications.add(f"Lost {lost} gold", 3.0, RED)
        self.notifications.add("You have been revived.", 3.0)

    # ================================================================
    # UPDATE
    # ================================================================

    def _update(self, dt: float):
        # Tutorial system
        if self.tutorial and self.tutorial.active:
            self.tutorial.update(dt, self)

        # Auto-play mode: AI controls the player
        if self.auto_play:
            actions.auto_play_update(self, dt)
        else:
            # Manual player movement
            keys = pygame.key.get_pressed()
            self.player.vx = 0
            self.player.vy = 0
            _panels_block = (self.ui.any_panel_open
                             or self.settlement_panel.visible
                             or self.relationship_panel.visible
                             or self.fast_travel_ui.active
                             or self.crafting_ui.active
                             or self.skill_tree_ui.active
                             or self.llm_console.visible)
            if not _panels_block:
                if keys[pygame.K_w] or keys[pygame.K_UP]:    self.player.vy = -1
                if keys[pygame.K_s] or keys[pygame.K_DOWN]:  self.player.vy = 1
                if keys[pygame.K_a] or keys[pygame.K_LEFT]:  self.player.vx = -1
                if keys[pygame.K_d] or keys[pygame.K_RIGHT]: self.player.vx = 1

                # Speed controls: Shift=run, Ctrl=sneak, default=walk
                if keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]:
                    if keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
                        self.player.current_gait = "sprint"
                    else:
                        self.player.current_gait = "run"
                elif keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
                    self.player.current_gait = "sneak"
                elif self.player.vx != 0 or self.player.vy != 0:
                    self.player.current_gait = "jog" if (keys[pygame.K_CAPSLOCK]) else "walk"
                else:
                    self.player.current_gait = "walk"

        # Handle player movement — interior or overworld
        interior_state = getattr(self.player, 'interior_state', None)
        if interior_state and interior_state.is_inside and interior_state.current_interior:
            # Move in interior space
            interior = interior_state.current_interior
            if self.player.vx != 0 or self.player.vy != 0:
                mag = math.sqrt(self.player.vx**2 + self.player.vy**2)
                if mag > 0:
                    nx = self.player.vx / mag
                    ny = self.player.vy / mag
                    self.player.facing = (nx, ny)
                    from game.systems.physical import get_gait_speed
                    speed = get_gait_speed(self.player, self.player.current_gait) * 0.7
                    new_x = interior_state.interior_x + nx * speed * dt
                    new_y = interior_state.interior_y + ny * speed * dt
                    # Check walkability in interior
                    if interior.is_walkable(int(new_x), int(interior_state.interior_y)):
                        interior_state.interior_x = new_x
                    if interior.is_walkable(int(interior_state.interior_x), int(new_y)):
                        interior_state.interior_y = new_y

            # Update interior NPCs — they move around doing activities
            from game.systems.interiors import update_interior_npcs
            tod = getattr(self.time_sys, 'normalized', 0.3)
            update_interior_npcs(interior, dt, tod)
        else:
            if self.auto_play:
                # During autoplay, navigate_toward handles movement directly.
                # Only update cooldowns/energy/regen, not velocity-based movement.
                self.player.vx = 0
                self.player.vy = 0
            self.player.update(dt, self.world)
            self.crafting_ui.update(dt, self.player)
            self.skill_tree_ui.update(dt)

            # Underground exploration — reveal tiles around player
            if getattr(self.player, 'current_floor', 0) < 0:
                px, py = int(self.player.x), int(self.player.y)
                for dy in range(-3, 4):
                    for dx in range(-3, 4):
                        self.player._underground_explored.add((px + dx, py + dy))

        # Audio: ambient sounds (footsteps removed)
        _px_tile = int(self.player.x)
        _py_tile = int(self.player.y)
        _cur_tile = self.world.tiles[_py_tile][_px_tile]
        _tnorm = getattr(self.time_sys, 'normalized',
                         self.time_sys.time / DAY_LENGTH)
        self.sound.update_ambient(
            dt, _cur_tile, _tnorm,
            self.player.x, self.player.y, self.world)

        # Track which building the player is inside (for roof removal in 2D)
        # Only recalculate when player moves to a new tile position
        px_int, py_int = int(self.player.x), int(self.player.y)
        _last_pos = getattr(self, '_last_building_check_pos', None)
        in_building = False
        if _last_pos == (px_int, py_int):
            # Position unchanged — use cached result
            in_building = getattr(self.player, '_current_building_name', '') != ''
        elif hasattr(self.world, 'plan'):
            self._last_building_check_pos = (px_int, py_int)
            for sp in self.world.plan.settlements:
                # Quick AABB check: skip settlements far from player
                if abs(sp.x - px_int) > sp.radius + 20 or abs(sp.y - py_int) > sp.radius + 20:
                    continue
                for bld in sp.buildings:
                    bx, by = bld['x'], bld['y']
                    bw, bh = bld['w'], bld['h']
                    if bx <= px_int < bx + bw and by <= py_int < by + bh:
                        self.player._current_building_name = sp.name
                        self.player._current_building_kind = sp.kind
                        self.player._current_building_rect = (bx, by, bw, bh)
                        in_building = True
                        break
                if in_building:
                    break
        else:
            self._last_building_check_pos = (px_int, py_int)
        if not in_building:
            # Only reset floor if player is on ground level.
            # If underground, keep building tracking so the underground
            # renderer knows which building to show.
            if self.player.current_floor == 0:
                self.player._current_building_name = ""
                self.player._current_building_kind = ""
                self.player._current_building_rect = None
            # If on non-ground floor but outside building bounds,
            # force back to ground (player somehow escaped)
            elif self.player.current_floor != 0:
                self.player.current_floor = 0
                self.player._current_building_name = ""
                self.player._current_building_kind = ""
                self.player._current_building_rect = None

        # Update mount (stamina, hunger, thirst, death check)
        from game.systems.physical import update_mount
        update_mount(self.player, dt, self.world)
        # Check for mount death
        if hasattr(self.player, '_mount_died'):
            self.notifications.add(
                f"Your mount {self.player._mount_died} has died!", 5.0, RED)
            del self.player._mount_died

        # Update party companions
        self.party.update(dt, self.player, self.world)

        # Real-time combat update (runs alongside everything else - no freeze)
        if self.combat.active:
            # Snapshot damage state before update for screen shake / HP bars
            _pre_hp = {}
            if self.combat.player_state.target:
                _t = self.combat.player_state.target
                _pre_hp[id(_t)] = (getattr(_t, 'hp', 0), _t)
            self.combat.update(dt, self.player, self.party.companions,
                              self.world_mgr.creatures, self.world_mgr.npcs, self.world)
            # Detect damage dealt this frame -> visual effects
            _cfx = getattr(self.active_renderer, 'combat_fx', None)
            for eid, (old_hp, ent) in _pre_hp.items():
                new_hp = getattr(ent, 'hp', old_hp)
                dmg = old_hp - new_hp
                if dmg > 0:
                    is_kill = not getattr(ent, 'alive', True)
                    # Audio: combat hit sound
                    self.sound.play_combat_hit(
                        "melee", ent.x, ent.y,
                        self.player.x, self.player.y)
                    if is_kill:
                        self.sound.play("death_sound")
                    # New combat effects system (popups, flashes, HP bars, death)
                    if _cfx:
                        _cfx.on_damage_dealt(ent, int(dmg), is_kill=is_kill)
                    # Screen shake on big hits
                    if hasattr(self.renderer, 'trigger_screen_shake'):
                        self.renderer.trigger_screen_shake(int(dmg))
                    # Legacy HP bar (still useful as backup on strategy renderer)
                    if hasattr(self.renderer, 'mark_hp_bar_target'):
                        self.renderer.mark_hp_bar_target(ent)
            # Also mark current target for HP bar
            if self.combat.player_state.target:
                if hasattr(self.renderer, 'mark_hp_bar_target'):
                    self.renderer.mark_hp_bar_target(self.combat.player_state.target)
                if _cfx:
                    _cfx.mark_hp_bar(self.combat.player_state.target)

            # Handle kills: drops, particles, quests
            for c in self.world_mgr.creatures:
                if not c.alive and self.player.dist_to(c) < 10:
                    if hasattr(c, '_death_handled'):
                        continue
                    c._death_handled = True
                    self.renderer.spawn_hit_particles(c.x, c.y)
                    self.renderer.spawn_xp_particles(c.x, c.y)
                    # Death effect via both legacy and new system
                    if hasattr(self.renderer, 'spawn_death_effect'):
                        self.renderer.spawn_death_effect(c.x, c.y)
                    if _cfx:
                        _cfx.spawn_death_effect(c.x, c.y)
                    self.quest_sys.on_kill(c.kind)
                    # Track kill for title system
                    if hasattr(self.player, 'title_tracker'):
                        self.player.title_tracker.record_kill(c.kind)
                    self.combat_log_panel.add_message(
                        f"Killed {c.kind}! +{c.xp_value} XP")
                    # Quest trigger: defend quests when creature dies near settlement
                    for s in self.world.structures:
                        if s.kind in ("village", "town", "city", "hamlet", "castle"):
                            if abs(c.x - s.x) < 25 and abs(c.y - s.y) < 25:
                                self.quest_sys.on_defend_success(s.name)
                                break
                    drops = c.get_drops()
                    if drops:
                        self.world_mgr.drop_items(c.x, c.y, drops)

        # Drain combat visual events from CombatSystem (NPC/creature fights)
        from game.systems.combat import drain_combat_visuals
        _cfx = getattr(self.active_renderer, 'combat_fx', None)
        for evt in drain_combat_visuals():
            if _cfx is None:
                continue
            if evt["type"] == "damage":
                _cfx.on_damage_dealt(evt["target"], evt["damage"],
                                     is_kill=evt.get("is_kill", False))
            elif evt["type"] == "death":
                _cfx.spawn_death_effect(evt["x"], evt["y"])

        # Pick up pending spell visuals from player and combat system
        if hasattr(self.renderer, 'spawn_spell_effect'):
            # From magic system (via cast_spell on player)
            pending = getattr(self.player, '_pending_spell_visuals', [])
            for vis in pending:
                self.renderer.spawn_spell_effect(
                    vis["spell_name"], vis["x"], vis["y"],
                    vis.get("target_x"), vis.get("target_y"))
                # Audio: spell-specific sounds
                sname = vis["spell_name"].lower()
                if "fire" in sname or "flame" in sname:
                    self.sound.play("fireball_impact")
                elif "lightning" in sname or "shock" in sname:
                    self.sound.play("lightning")
                elif "ice" in sname or "frost" in sname:
                    self.sound.play("ice_shatter")
                else:
                    self.sound.play("spell_cast")
            if pending:
                self.player._pending_spell_visuals = []
            # From tactical combat system
            tc_pending = getattr(self.combat, '_pending_spell_visuals', [])
            for vis in tc_pending:
                self.renderer.spawn_spell_effect(
                    vis["spell_name"], vis["x"], vis["y"],
                    vis.get("target_x"), vis.get("target_y"))
            if tc_pending:
                self.combat._pending_spell_visuals = []

        if not self.player.alive:
            self.sound.play("death_sound")
            if self.player_mode == "god":
                self.player.alive = True
                self.player.hp = 99999
            elif getattr(self.player, 'ghost', False):
                # Already a ghost, check if at spawn temple to respawn
                sx, sy = self.world.spawn_point
                if self.player.dist_to_pos(sx, sy) < 3:
                    self.player.alive = True
                    self.player.ghost = False
                    self.player.hp = self.player.max_hp
                    self.player.mode = "mortal"
                    self.player_mode = "mortal"
                    self.notifications.add("You have been reborn at the Temple of Awakening!", 5.0, GREEN)
                else:
                    self.player.alive = True  # ghosts are always "alive" for movement
            else:
                # Mortal died -> become ghost
                self.player.alive = True
                self.player.ghost = True
                self.player.mode = "ghost"
                self.player_mode = "ghost"
                self.player.speed = PLAYER_SPEED * 2
                self.notifications.add("You have died and become a ghost...", 5.0, (150, 150, 220))
                self.notifications.add("Return to the Temple of Awakening (world center) to be reborn.", 8.0, (150, 150, 220))
                self.dead = False  # don't show death screen, just become ghost

        self.camera.update(self.player.x, self.player.y)
        # Divine commands update (visual effects, step-one tick handling)
        if hasattr(self, 'divine_commands'):
            self.divine_commands.update(dt)
            self.divine_commands._last_game = self
        self.time_sys.update(dt)
        # Store normalized time on world for renderer shadow calculations
        self.world._time_normalized = getattr(self.time_sys, 'normalized',
                                               self.time_sys.time / DAY_LENGTH)
        self.world_mgr.update(dt, self.player, self.time_sys.time)
        self.simulation.update(dt, self.player)

        # LLM console: poll for pending responses
        self.llm_console.update(self)

        # Road builder: auto-place while moving
        if self.road_builder.active:
            self.road_builder.handle_movement(self)

        # Water ripples: update animations and check player
        self.water_ripples.update(dt)
        self.water_ripples.check_entity_in_water(
            self.player, self.world.tiles, self.world.width, self.world.height, dt)

        # Filtered events - only show what the player can witness nearby
        all_events = self.simulation.get_event_log()
        if all_events:
            # Record notable events in the chronicle
            for msg in all_events:
                classified = classify_event(msg)
                if classified:
                    cat, title, importance = classified
                    self.chronicles.record(
                        self.time_sys.day, cat, title, msg, importance)

            visible = self.simulation.info.filter_events_for_player(
                all_events, self.player, self.world_mgr.npcs, radius=20)
            for msg, color in visible:
                self.notifications.add(msg, 4.0, color)

        # Information spreading (NPCs near player share gossip)
        self.simulation.info.update(dt, self.world_mgr.npcs, self.player,
                                    self.simulation.npc_grid, self.time_sys.day)

        # Letter system: NPC-to-player mail delivery
        _social = getattr(self.simulation, 'social', None)
        newly_delivered = self.letter_system.update(
            dt, self.time_sys.day, self.world_mgr.npcs, self.player,
            social_system=_social)
        for letter in newly_delivered:
            self.notifications.add(
                f"New letter from {letter.sender_name}: {letter.subject}",
                5.0, (220, 200, 100))
            self.combat_log_panel.add_message(
                f"Letter arrived from {letter.sender_name}", (220, 200, 100))

        # Audio: detect level-up and damage-taken
        if self.player.level > self._last_player_level:
            self.sound.play("level_up")
            self._last_player_level = self.player.level
        if self.player.hp < self._last_player_hp:
            self.sound.play("damage_taken")
        self._last_player_hp = self.player.hp

        # Phase 6: Periodic title check, combat log ingestion, settlement tracking
        self._title_check_timer += dt
        if self._title_check_timer >= 2.0:
            self._title_check_timer = 0.0
            from game.systems.titles import update_titles
            update_titles(self.player, self.notifications)
            # Track settlement visits
            if hasattr(self.player, 'title_tracker') and hasattr(self.world, 'plan'):
                px, py = int(self.player.x), int(self.player.y)
                for sp in self.world.plan.settlements:
                    if abs(sp.x - px) <= sp.radius and abs(sp.y - py) <= sp.radius:
                        self.player.title_tracker.record_settlement_visit(sp.name)
                        break
        # Ingest tactical combat log into our combat log panel
        if self.combat.active:
            self.combat_log_panel.ingest_combat_log(self.combat.combat_log)
        # Forward visible simulation events to combat log panel
        if all_events:
            for msg, color in visible:
                self.combat_log_panel.add_message(msg, color)

        # Drain overheard conversation snippets into combat log
        for entry in self.simulation._snippet_manager.drain_log_entries():
            self.combat_log_panel.add_message(entry, (200, 180, 140))

        # Exploration
        if self.player.vx != 0 or self.player.vy != 0:
            self.player.gain_skill_xp("navigation", 0.01 * dt)

        # FOV - cached by tile position to avoid recomputing every frame
        _px_fov, _py_fov = int(self.player.x), int(self.player.y)
        _fov_moved = (_px_fov, _py_fov) != getattr(self, '_last_fov_pos', None)

        if _fov_moved:
            self._last_fov_pos = (_px_fov, _py_fov)
            self.world.reveal_around(_px_fov, _py_fov, 8)

        if self.player_mode == "god":
            self.visible_tiles = None  # None = everything visible
        elif _fov_moved:
            if self.player_mode == "ghost":
                self.fov_radius = 20  # ghosts see further
                self.visible_tiles = compute_fov_set(
                    _px_fov, _py_fov, self.fov_radius, self.world)
                # Ghosts also see through walls in a small radius
                for dy in range(-8, 9):
                    for dx in range(-8, 9):
                        if dx*dx + dy*dy <= 64:
                            self.visible_tiles.add((_px_fov + dx, _py_fov + dy))
            else:
                self.visible_tiles = compute_fov_set(
                    _px_fov, _py_fov, self.fov_radius, self.world)

        # Nearby NPC — use spatial grid for efficient lookup
        self.nearby_npc = None
        best_dist = NPC_INTERACTION_RANGE
        _nearby_npcs = self.simulation.npc_grid.get_nearby(
            self.player.x, self.player.y, NPC_INTERACTION_RANGE)
        for npc in _nearby_npcs:
            if not npc.alive:
                continue
            d = self.player.dist_to(npc)
            if d < best_dist:
                best_dist = d
                self.nearby_npc = npc

        # NPC-initiated interaction — use spatial grid
        if not self.ui.any_panel_open:
            for npc in _nearby_npcs:
                if getattr(npc, 'wants_to_talk', False) and npc.alive:
                    if self.player.dist_to(npc) < NPC_CONVERSATION_RANGE + 1:
                        reason = getattr(npc, 'talk_reason', 'wants to speak with you')
                        cls_info = f"{getattr(npc, 'race', '')} {getattr(npc, 'char_class', npc.profession)}"
                        self.notifications.add(f'{npc.name} ({cls_info}): "{reason}"', 6.0, YELLOW)
                        npc.wants_to_talk = False
                        self.nearby_npc = npc
                        break

        # Nearby intelligent creature — check for dialog-capable creatures
        self.nearby_creature = None
        if not self.ui.any_panel_open:
            from game.core.creature_dialogs import is_intelligent
            _nearby_crs = self.simulation.creature_grid.get_nearby(
                self.player.x, self.player.y, NPC_INTERACTION_RANGE + 1)
            best_cr_dist = NPC_INTERACTION_RANGE + 1
            for cr in _nearby_crs:
                if not cr.alive or not is_intelligent(cr.kind):
                    continue
                d = self.player.dist_to(cr)
                if d < best_cr_dist:
                    best_cr_dist = d
                    self.nearby_creature = cr

            # Creature-initiated conversation
            for cr in _nearby_crs:
                if getattr(cr, 'wants_to_talk', False) and cr.alive:
                    if self.player.dist_to(cr) < NPC_CONVERSATION_RANGE + 1:
                        reason = getattr(cr, 'talk_reason', 'wants to speak')
                        kind_name = cr.kind.replace('_', ' ').title()
                        self.notifications.add(
                            f'{kind_name}: "{reason}"', 6.0, YELLOW)
                        cr.wants_to_talk = False
                        self.nearby_creature = cr
                        break

        # Trespass detection
        trespass_msg = self.building_sys.check_trespass(
            self.player, self.world_mgr.npcs, self.time_sys.time)
        if trespass_msg:
            self.notifications.add(trespass_msg, 4.0, RED)

        # Location banner
        structure = self.world.get_structure_at(self.player.x, self.player.y)
        loc_name = structure.name if structure else ""
        if loc_name and loc_name != self.current_location:
            self.current_location = loc_name
            self.location_banner = loc_name
            self.location_banner_timer = 3.0
            # Quest trigger: on_reach_location for investigate/escort/diplomacy
            self.quest_sys.on_reach_location(loc_name)
            # Main questline location trigger
            _game_day = int(getattr(self.time_sys, 'day', 0))
            _mq_msgs = self.main_quest.on_reach_location(loc_name, _game_day)
            for _mq_m in _mq_msgs:
                self.notifications.add(_mq_m, 6.0, (100, 200, 200))
            # Auto-turn-in starting quest (no NPC giver to talk to)
            for _q in list(self.quest_sys.active_quests):
                if (_q.title == "Find Civilization" and _q.completed
                        and not _q.turned_in):
                    _reward = self.quest_sys.turn_in_quest(_q, self.player)
                    if _reward:
                        self.notifications.add(_reward, 5.0, GREEN)
                    hint = getattr(_q, 'hint', '')
                    if hint:
                        self.notifications.add(hint, 6.0, (180, 200, 140))
        elif not loc_name:
            self.current_location = ""
        if self.location_banner_timer > 0:
            self.location_banner_timer -= dt

        # Examine timer
        if self.examine_timer > 0:
            self.examine_timer -= dt
            if self.examine_timer <= 0:
                self.examine_text = ""

        actions.update_llm(self, dt)
        self.notifications.update(dt)
        self.screenshots.update(dt)

        # Multiplayer network sync
        if self.net_server or self.net_client:
            self._update_multiplayer(dt)

        # Auto-save
        if self.config["auto_save"]:
            self.auto_save_timer += dt
            interval = self.config["auto_save_interval"] * 60  # minutes -> seconds
            if self.auto_save_timer >= interval:
                self.auto_save_timer = 0.0
                self._save_game()

        if self.attack_flash_timer > 0:
            self.attack_flash_timer -= dt

        # Elemental effects: fire spread, ice thaw, acid dissolution
        self.elemental.tick(dt, self.world)
        self.elemental.damage_entities_in_effects(
            self.world_mgr.creatures, self.world_mgr.npcs, dt)

    # ================================================================
    # DRAW
    # ================================================================

    def _draw(self):
        is_3d = self.view_mode == "3d"

        if not is_3d:
            self.screen.fill((10, 10, 20))

        # Check if player is inside a building
        interior_state = getattr(self.player, 'interior_state', None)
        if not is_3d and interior_state and interior_state.is_inside and interior_state.current_interior:
            # INTERIOR VIEW — draw the building interior instead of overworld
            self.renderer.draw_interior(interior_state.current_interior,
                                       self.player, self.camera)
            if interior_state.transitioning:
                interior_state.update_transition(1.0 / FPS)
                alpha = 255 - interior_state.transition_alpha
                if alpha > 0:
                    fade = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
                    fade.fill((0, 0, 0))
                    fade.set_alpha(alpha)
                    self.screen.blit(fade, (0, 0))
        else:
            # OVERWORLD VIEW — use active renderer
            r = self.active_renderer
            dt = self.clock.get_time() / 1000.0

            # Apply screen shake offset to camera for this frame
            _shake_dx, _shake_dy = 0, 0
            if hasattr(r, 'get_screen_shake_offset'):
                _shake_dx, _shake_dy = r.get_screen_shake_offset(dt)
                if _shake_dx or _shake_dy:
                    self.camera.x += _shake_dx
                    self.camera.y += _shake_dy

            r.draw_world(self.world, self.camera, self.visible_tiles,
                         self.player)
            r.draw_building_doors(self.world, self.camera, self.player)
            r.draw_structures(self.world, self.camera)
            # Settlement overlay effects (awnings, walls, tavern glow, farm patterns)
            if hasattr(r, 'draw_settlement_overlays'):
                r.draw_settlement_overlays(self.world, self.camera, self.player)
            if hasattr(r, 'draw_farm_overlays'):
                r.draw_farm_overlays(self.world, self.camera)
            r.draw_ground_items(self.world_mgr.ground_items, self.camera)

            # Construction scaffolding overlay
            _csys = getattr(self.simulation, 'construction', None)
            if _csys and hasattr(r, 'draw_construction_scaffolding'):
                r.draw_construction_scaffolding(_csys, self.camera)

            # Elemental terrain effects (fire, ice, acid, scorch overlays)
            self.elemental_renderer.draw(
                self.screen, self.camera, self.elemental, dt)

            r._last_dt = dt
            r.draw_creatures(self.world_mgr.creatures, self.camera, self.visible_tiles)
            r.draw_npcs(self.world_mgr.npcs, self.camera, self.player, self.visible_tiles)
            # Draw conversation partner lines between talking NPCs
            if SHOW_NPC_CONVERSATIONS and hasattr(self, 'simulation') and hasattr(r, 'draw_conversation_lines'):
                r.draw_conversation_lines(
                    self.simulation.conversations, self.camera, self.visible_tiles)
            r.draw_player(self.player, self.camera)

            # Water ripple effects (shallow water splashes)
            self.water_ripples.draw(self.screen, self.camera)

            # Enemy health bars (combat polish — legacy + new system)
            if hasattr(r, 'draw_enemy_hp_bars'):
                _all_entities = itertools.chain(self.world_mgr.creatures, self.world_mgr.npcs)
                r.draw_enemy_hp_bars(_all_entities, self.camera, dt)

            # Combat visual effects: damage popups, hit flashes, death effects, HP bars
            if hasattr(r, 'combat_fx'):
                r.combat_fx.update_and_draw(self.screen, self.camera, dt)
                r.combat_fx.draw_hp_bars(self.screen, self.camera, dt)

            # Overheard NPC conversation snippets (floating text)
            self._draw_conversation_snippets(dt)

            # Spell visual effects (combat polish)
            if hasattr(r, 'draw_spell_effects'):
                r.draw_spell_effects(self.camera, dt)

            # Draw remote multiplayer players
            if self.remote_players:
                self._draw_remote_players()

            r.draw_world_events(self.simulation.events, self.camera)
            if hasattr(r, 'draw_battle_visuals') and hasattr(self.simulation, 'battle_visuals'):
                r.draw_battle_visuals(self.simulation.battle_visuals, self.camera)
            # Draw goods transport visuals (trade caravans, ground items)
            _gt = getattr(self.simulation, 'goods_transport', None)
            if _gt and hasattr(r, 'draw_trade_caravans'):
                r.draw_trade_caravans(_gt, self.camera)
                r.draw_transport_ground_items(_gt, self.camera)
            # Draw graves and unburied bodies
            if hasattr(r, 'draw_graves') and hasattr(self.simulation, 'burial'):
                r.draw_graves(self.simulation.burial.graves, self.camera)
            r.draw_particles(self.camera, self.clock.get_time() / 1000.0, self.player)
            # Seasonal tile palette update (4 times per year)
            if hasattr(r, 'set_season') and hasattr(self.simulation, 'ecology'):
                r.set_season(self.simulation.ecology.season)
            # Bind vegetation/crop systems for per-tile color overrides
            if hasattr(r, 'set_vegetation_systems') and r._vegetation_sys is None:
                if hasattr(self.simulation, 'vegetation_sys'):
                    r.set_vegetation_systems(
                        self.simulation.vegetation_sys,
                        getattr(self.simulation, 'crop_system', None))
            # Weather visual effects (rain, snow, fog, storm)
            if hasattr(r, 'draw_weather') and hasattr(self.simulation, 'ecology'):
                _weather = self.simulation.ecology.weather
                r.draw_weather(_weather, self.camera, self.clock.get_time() / 1000.0)
            if not is_3d:  # night overlay uses pygame blit in 2D, GL in 3D
                r.draw_lighting(self.time_sys.normalized, self.camera, self.world)

            # Undo screen shake offset so camera is stable for HUD/UI
            if _shake_dx or _shake_dy:
                self.camera.x -= _shake_dx
                self.camera.y -= _shake_dy

            if not is_3d and interior_state and interior_state.transitioning:
                interior_state.update_transition(1.0 / FPS)

        # 3D mode: draw HUD via GL texture overlay
        if is_3d and hasattr(self, 'renderer_3d') and self.renderer_3d:
            # Basic stats HUD
            p = self.player
            lines = [
                f"HP: {int(p.hp)}/{p.max_hp}  Energy: {int(p.energy)}  "
                f"Gold: {p.gold}  Lv.{p.level}",
                f"FPS: {self.clock.get_fps():.0f}  "
                f"Radius: {self.renderer_3d.view_radius}  "
                f"3D View (V:switch  Arrows:camera  [/]:radius)",
            ]
            self.renderer_3d._draw_text_overlay(lines, 5, 5)
            # Time of day
            time_line = [f"Day {self.time_sys.day}  {self.time_sys._astro.get('season', 'Spring').title()}"]
            self.renderer_3d._draw_text_overlay(time_line, 5, SCREEN_HEIGHT - 25)
        elif not is_3d:
            if self.attack_flash_timer > 0:
                flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                flash.fill((255, 255, 255, int(30 * (self.attack_flash_timer / 0.15))))
                self.screen.blit(flash, (0, 0))

            self.ui.draw_hud(self.player, self.time_sys)
            self.spell_bar.draw(self.screen, self.player, self.targeting)

            # Tutorial hint overlay
            if self.tutorial and self.tutorial.active:
                self.tutorial.draw_hint(
                    self.screen, self.renderer.font_md, self.renderer.font_sm)

            # Spell/ranged targeting overlay
            if self.targeting.is_active():
                self.targeting.draw(self.screen, self.camera, self.player)

            # Mouse hover tooltip (entity name/HP when hovering)
            hover = getattr(self.targeting, 'hover_entity', None)
            if hover and getattr(hover, 'alive', False):
                mp = getattr(self, '_mouse_pos', (0, 0))
                name = getattr(hover, 'name', getattr(hover, 'kind', '?'))
                hp = getattr(hover, 'hp', 0)
                max_hp = getattr(hover, 'max_hp', 1)
                tip = f"{name} ({int(hp)}/{int(max_hp)} HP)"
                tip_surf = self.renderer.font_sm.render(tip, True, (220, 220, 230))
                tw, th = tip_surf.get_size()
                tx, ty = mp[0] + 12, mp[1] - 8
                pygame.draw.rect(self.screen, (20, 20, 35),
                                 (tx - 2, ty - 1, tw + 4, th + 2))
                self.screen.blit(tip_surf, (tx, ty))

            # Object highlighting overlay
            if hasattr(self, 'highlight'):
                self.highlight.draw_highlights(self.screen, self.world,
                                                self.camera, self.player)
                self.highlight.draw_picker(self.screen)

            self.active_renderer.draw_minimap(self.world, self.player,
                                              self.world_mgr.npcs, self.world_mgr.creatures,
                                              self.show_minimap)

        # 2D UI elements — skip in 3D mode (they use pygame.draw/blit)
        if not is_3d:
            if self.nearby_npc and not self.ui.any_panel_open:
                self.ui.draw_interaction_prompt(self.nearby_npc)

            if not self.ui.any_panel_open and not self.player.interior_state.is_inside:
                ppx, ppy = int(self.player.x), int(self.player.y)
                near_door = False
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        tx, ty = ppx + dx, ppy + dy
                        if (0 <= tx < self.world.width and 0 <= ty < self.world.height and
                            self.world.tiles[ty][tx] == DOOR):
                            structure = self.world.get_structure_at(float(tx), float(ty))
                            if structure:
                                prompt = self.active_renderer.font_sm.render(
                                    f"[E] Enter {structure.name}", True, (220, 220, 180))
                                bg = pygame.Surface((prompt.get_width() + 10, 20), pygame.SRCALPHA)
                                bg.fill((20, 20, 40, 200))
                                self.screen.blit(bg, (SCREEN_WIDTH // 2 - prompt.get_width() // 2 - 5,
                                                      SCREEN_HEIGHT - 70))
                                self.screen.blit(prompt, (SCREEN_WIDTH // 2 - prompt.get_width() // 2,
                                                         SCREEN_HEIGHT - 68))
                                near_door = True
                                break
                    if near_door:
                        break
            if self.world_mgr.ground_items and not self.ui.any_panel_open:
                self.ui.draw_pickup_prompt(self.world_mgr.ground_items,
                                           self.player.x, self.player.y)

            # Contextual help tooltips (only when no NPC prompt shown)
            if not self.nearby_npc and hasattr(self, 'tooltip_sys'):
                _bcache = getattr(self.renderer, '_building_function_cache', {})
                self.tooltip_sys.update_and_draw(
                    self.screen, self.player, self.world,
                    self.world_mgr.npcs, self.world_mgr.creatures,
                    _bcache,
                    self.clock.get_time() / 1000.0,
                    self.ui.any_panel_open,
                )

            if self.location_banner_timer > 0:
                self.ui.draw_location_banner(self.location_banner, min(1.0, self.location_banner_timer))
            if self.examine_text:
                self.ui.draw_examine(self.examine_text)

            self.ui.draw_notifications(self.notifications.notifications)
            self.ui.draw_dialog()
            self.ui.draw_text_input()
            if getattr(self, 'quest_board_active', False):
                self._draw_quest_board()
            if getattr(self, 'msg_board_active', False):
                self._draw_message_board()
            if self.ui.shop_active:
                self.ui.draw_shop(self.player)
            if self.ui.gift_active:
                self.ui.draw_gift_panel(self.player)
            self.ui.draw_inventory(self.player)
            self.ui.draw_quest_log(self.quest_sys.active_quests)
            self.ui.draw_character_sheet(self.player)
            self.crafting_ui.draw(self.screen, self.player)
            self.skill_tree_ui.draw(self.screen, self.player)
            self.ui.draw_chronicle(self.chronicles)

            # Relationship overview panel (Shift+R)
            _social = getattr(self.simulation, 'social', None)
            self.relationship_panel.draw(
                self.screen, self.player, self.world_mgr.npcs,
                social_system=_social, time_system=self.time_sys)

            # Unread letter notification (shown on HUD when letters available)
            if hasattr(self, 'letter_system') and self.letter_system.unread_count > 0:
                _lcount = self.letter_system.unread_count
                _ltext = self.renderer.font_sm.render(
                    f"[Mail: {_lcount} unread]", True, (220, 200, 100))
                _lbg = pygame.Surface((_ltext.get_width() + 8, 18), pygame.SRCALPHA)
                _lbg.fill((30, 25, 15, 200))
                self.screen.blit(_lbg, (SCREEN_WIDTH - _ltext.get_width() - 14, 100))
                self.screen.blit(_ltext, (SCREEN_WIDTH - _ltext.get_width() - 10, 101))
            self.ui.draw_planet_view(1.0 / FPS, self.time_sys)

            # Quest tracker HUD (only when no panels are open)
            if not self.ui.any_panel_open:
                self.quest_tracker.draw(
                    self.screen, self.quest_sys.active_quests,
                    self.player, self.world)

            if self.ui.show_world_map:
                self.ui.world_map_view.update_scroll(1.0 / FPS)
                self.ui.world_map_view.draw(self.screen, self.world,
                                             self.player, self.world.structures)

            if self.combat.active:
                self._draw_combat_ui()

            # Pause menu is now handled by MenuSystem (blocking modal)
            # self.ui.draw_pause_menu() is no longer used
            if self.dead:
                self.ui.draw_death_screen()

            # Road building mode overlay
            self.road_builder.draw(self.screen, self.camera, self.player)

            # Controls overlay (on top of everything)
            self.controls_overlay.draw(self.screen)

            # LLM console (on top of all game UI)
            self.llm_console.draw(self.screen)

        # Mode indicator
        if self.player_mode == "ghost":
            mode_text = self.renderer.font_md.render("GHOST MODE", True, (150, 150, 220))
            self.screen.blit(mode_text, (SCREEN_WIDTH // 2 - mode_text.get_width() // 2, 48))
            # Distance to temple
            sx, sy = self.world.spawn_point
            dist = self.player.dist_to_pos(sx, sy)
            if dist > 5:
                dist_text = self.renderer.font_sm.render(
                    f"Temple: {dist:.0f} tiles  [E at temple to respawn]", True, (130, 130, 180))
                self.screen.blit(dist_text, (SCREEN_WIDTH // 2 - dist_text.get_width() // 2, 66))
        elif self.player_mode == "god":
            # Draw god mode UI (toolbar, overlay, panels)
            if hasattr(self, 'god_ui') and self.god_ui.active:
                self.god_ui.draw(self.screen)
            else:
                mode_text = self.renderer.font_md.render("GOD MODE", True, (255, 220, 100))
                self.screen.blit(mode_text, (SCREEN_WIDTH // 2 - mode_text.get_width() // 2, 48))
            # Divine commands: effects, menus, HUD, dashboard
            if hasattr(self, 'divine_commands'):
                self.divine_commands.draw_effects(self.screen, self.camera)
                self.divine_commands.draw_hud(self.screen)
                self.divine_commands.draw_menu(self.screen)
                self.god_dashboard.draw(self.screen)
            # Claude hint (always show in god mode)
            if not self.claude_chat.visible:
                claude_hint = self.renderer.font_sm.render(
                    "[F10] Claude AI  [Shift+K] API Key  [~] Console  [F6] Tweaker  [F7] Reload", True, (160, 160, 200))
                self.screen.blit(claude_hint,
                                 (SCREEN_WIDTH - claude_hint.get_width() - 10, 50))

        # Auto-play indicator
        if self.auto_play:
            ap_text = self.renderer.font_md.render("AUTO-PLAY [P to disable]", True, YELLOW)
            ap_bg = pygame.Surface((ap_text.get_width() + 16, 24), pygame.SRCALPHA)
            ap_bg.fill((20, 20, 40, 200))
            self.screen.blit(ap_bg, (SCREEN_WIDTH // 2 - ap_text.get_width() // 2 - 8, 48))
            self.screen.blit(ap_text, (SCREEN_WIDTH // 2 - ap_text.get_width() // 2, 50))

        # Status bar
        if self.config["show_fps"]:
            fps = self.renderer.font_sm.render(f"FPS: {self.clock.get_fps():.0f}", True, GRAY)
            self.screen.blit(fps, (SCREEN_WIDTH - 80, SCREEN_HEIGHT - 20))

        llm_stats = self.llm.get_stats()
        llm_color = GREEN if llm_stats["enabled"] else GRAY
        llm_label = f"LLM: {llm_stats['provider']}"
        if llm_stats["enabled"]:
            llm_label += f" [{llm_stats['successful']}/{llm_stats['total_requests']}]"
        llm_text = self.renderer.font_sm.render(llm_label, True, llm_color)
        self.screen.blit(llm_text, (SCREEN_WIDTH - llm_text.get_width() - 10, SCREEN_HEIGHT - 35))

        # Multiplayer status and chat (drawn on top of game, below modals)
        if self.net_server or self.net_client:
            self._draw_multiplayer_status()
            self._draw_chat_log()

        # Claude chat and API key config (drawn on top of everything)
        if self.player_mode == "god":
            self.claude_chat.draw(self.screen)
            self.api_key_config.draw(self.screen)

        pygame.display.flip()


def main():
    game = Game()
    game.run()


if __name__ == "__main__":
    main()
