"""God Mode information dashboard, inspector, and debug tools.

Provides overlay panels for inspecting NPCs, settlements, creatures,
tiles, kingdoms, economy, and world events. Activated when player.god is True.

UI uses a floating popup panel (toggled with G) instead of a top toolbar,
so the game's status text is never obscured.
"""

import math
import pygame
from typing import Optional, List, Tuple, Dict, Any

from game.settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE, TERRAIN_COLORS,
    WHITE, BLACK, RED, GREEN, BLUE, YELLOW, ORANGE, GRAY, DARK_GRAY,
    LIGHT_GRAY, UI_BG, UI_BORDER, UI_TEXT, UI_HIGHLIGHT,
)
from game.ui.god_tweaker import ParameterTweaker
from game.ui.god_live_console import LivePythonConsole
from game.systems.hot_reload import HotReloader


# ================================================================
# COLOR PALETTE for god mode panels
# ================================================================

GOD_BG = (12, 12, 22, 230)
GOD_HEADER = (100, 180, 100)
GOD_SUBHEADER = (130, 160, 210)
GOD_DIM = (100, 100, 120)
GOD_ACCENT = (220, 200, 80)
GOD_PANEL_BG = (20, 22, 32, 240)
GOD_TAB_ACTIVE = (60, 130, 80)
GOD_TAB_INACTIVE = (45, 48, 58)
GOD_BTN_ACTIVE = (60, 130, 80)
GOD_BTN_INACTIVE = (45, 48, 58)
GOD_SELECTION_RING = (100, 255, 100)
GOD_OVERLAY_NPC = (180, 180, 255)
GOD_OVERLAY_CREATURE = (255, 180, 130)
GOD_OVERLAY_SETTLEMENT = (100, 140, 230, 80)

# Floating panel dimensions
PANEL_W = 360
PANEL_H = 540


class GodModeUI:
    """Complete God Mode interface with inspectors, dashboards, and tools.

    Uses a floating popup panel on the right side of the screen,
    toggled with the G key. Tabs switch between sections.
    """

    def __init__(self, screen: pygame.Surface, game):
        self.screen = screen
        self.game = game
        self.active = True

        # Floating panel state
        self.panel_visible = False
        self.panel_x = SCREEN_WIDTH - PANEL_W - 10
        self.panel_y = 40
        self._dragging = False
        self._drag_offset = (0, 0)

        # Tabs: settlement, npc, economy, world, timeline
        self.tabs = ["Settlement", "NPC", "Economy", "World", "Timeline"]
        self.tab_keys = ["settlement", "npc", "economy", "world", "timeline"]
        self.current_tab = 0  # index into tabs

        # Inspector sub-panels (opened by clicking entities)
        # current_panel can be: None, "settlement", "npc", "creature",
        #                       "economy", "world", "timeline", "tile"
        self.current_panel: Optional[str] = None
        self.selected_entity = None
        self.selected_tile: Optional[Tuple[int, int]] = None
        self.selected_settlement_name: Optional[str] = None
        self.tool = "inspect"
        self.show_overlay = True
        self.timeline_scroll = 0
        self.economy_scroll = 0

        # Live editing subsystems
        self.tweaker = ParameterTweaker(game)
        self.python_console = LivePythonConsole(game)
        self.hot_reloader = HotReloader()

        # Fonts
        self.font_tiny = pygame.font.SysFont("monospace", 10)
        self.font_sm = pygame.font.SysFont("monospace", 12)
        self.font_md = pygame.font.SysFont("monospace", 14)
        self.font_lg = pygame.font.SysFont("monospace", 18, bold=True)

    # ================================================================
    # PUBLIC API
    # ================================================================

    def set_panel(self, panel_name: str):
        """Toggle a dashboard panel on/off."""
        if self.current_panel == panel_name:
            self.current_panel = None
        else:
            self.current_panel = panel_name
            self.timeline_scroll = 0
            self.economy_scroll = 0
            # Sync tab to panel
            if panel_name in self.tab_keys:
                self.current_tab = self.tab_keys.index(panel_name)
            # Auto-show the panel
            if not self.panel_visible:
                self.panel_visible = True

    def set_tool(self, tool_name: str):
        """Switch the active god tool."""
        self.tool = tool_name

    def handle_click(self, mouse_x: int, mouse_y: int, button: int,
                     camera, world):
        """Handle a mouse click in god mode."""
        # Tweaker panel clicks
        if self.tweaker.visible:
            if self.tweaker.handle_click(mouse_x, mouse_y):
                return

        # Check if click is inside the floating panel
        if self.panel_visible:
            px, py = self.panel_x, self.panel_y
            if px <= mouse_x <= px + PANEL_W and py <= mouse_y <= py + PANEL_H:
                self._handle_panel_click(mouse_x - px, mouse_y - py, button)
                return

        # Convert screen coords to world tile coords
        wx, wy = camera.screen_to_world(float(mouse_x), float(mouse_y))
        tile_x, tile_y = int(wx), int(wy)

        if self.tool == "inspect":
            self._inspect_at(tile_x, tile_y, wx, wy)

    def handle_mousedown(self, mouse_x: int, mouse_y: int, button: int):
        """Handle mouse button down for dragging."""
        if not self.panel_visible or button != 1:
            return False
        # Check title bar area for drag
        px, py = self.panel_x, self.panel_y
        if px <= mouse_x <= px + PANEL_W and py <= mouse_y <= py + 28:
            self._dragging = True
            self._drag_offset = (mouse_x - px, mouse_y - py)
            return True
        return False

    def handle_mouseup(self, mouse_x: int, mouse_y: int, button: int):
        """Handle mouse button up."""
        if self._dragging:
            self._dragging = False
            return True
        return False

    def handle_mousemove(self, mouse_x: int, mouse_y: int):
        """Handle mouse motion for dragging."""
        if self._dragging:
            self.panel_x = mouse_x - self._drag_offset[0]
            self.panel_y = mouse_y - self._drag_offset[1]
            # Clamp to screen
            self.panel_x = max(0, min(SCREEN_WIDTH - PANEL_W, self.panel_x))
            self.panel_y = max(0, min(SCREEN_HEIGHT - PANEL_H, self.panel_y))
            return True
        return False

    def handle_key(self, key, unicode_char="", mods=0) -> bool:
        """Handle god-mode specific keys. Returns True if consumed."""

        # Python console intercepts ALL keys when visible
        if self.python_console.visible:
            if key == pygame.K_BACKQUOTE:
                self.python_console.toggle()
                return True
            self.python_console.handle_key(key, unicode_char, mods)
            return True

        # Parameter tweaker intercepts arrow keys when visible
        if self.tweaker.visible:
            if key == pygame.K_F6:
                self.tweaker.toggle()
                return True
            if self.tweaker.handle_key(key):
                return True

        # F6 = Parameter tweaker toggle
        if key == pygame.K_F6:
            self.tweaker.toggle()
            return True

        # F7 = Hot reload all safe modules
        if key == pygame.K_F7:
            results = self.hot_reloader.reload_all_safe()
            for mod_name, ok, msg in results:
                status = "OK" if ok else "FAIL"
                color = GREEN if ok else RED
                self.game.notifications.add(f"[{status}] {msg}", 2.0, color)
            return True

        # Tilde = Python console
        if key == pygame.K_BACKQUOTE:
            self.python_console.toggle()
            return True

        # G = Toggle floating panel
        if key == pygame.K_g:
            self.panel_visible = not self.panel_visible
            return True

        # F1-F5 = Switch tabs (and open panel if closed)
        tab_map = {
            pygame.K_F1: 0,  # Settlement
            pygame.K_F2: 1,  # NPC
            pygame.K_F3: 2,  # Economy
            pygame.K_F4: 3,  # World
            pygame.K_F5: 4,  # Timeline
        }

        if key in tab_map:
            idx = tab_map[key]
            self.current_tab = idx
            self.current_panel = self.tab_keys[idx]
            self.timeline_scroll = 0
            self.economy_scroll = 0
            if not self.panel_visible:
                self.panel_visible = True
            return True

        # Number keys = switch tools
        tool_map = {
            pygame.K_1: "inspect",
            pygame.K_2: "paint",
            pygame.K_3: "spawn",
            pygame.K_4: "build",
            pygame.K_5: "edit",
        }
        if key in tool_map:
            self.set_tool(tool_map[key])
            return True

        # Scroll in timeline/economy panels
        if self.current_panel == "timeline":
            if key == pygame.K_UP:
                self.timeline_scroll = max(0, self.timeline_scroll - 5)
                return True
            elif key == pygame.K_DOWN:
                self.timeline_scroll += 5
                return True
        if self.current_panel == "economy":
            if key == pygame.K_UP:
                self.economy_scroll = max(0, self.economy_scroll - 5)
                return True
            elif key == pygame.K_DOWN:
                self.economy_scroll += 5
                return True

        if key == pygame.K_ESCAPE:
            # Close live editing panels first
            if self.python_console.visible:
                self.python_console.visible = False
                return True
            if self.tweaker.visible:
                self.tweaker.visible = False
                return True
            if self.panel_visible:
                self.panel_visible = False
                self.current_panel = None
                self.selected_entity = None
                self.selected_settlement_name = None
                return True

        return False

    def draw(self, screen: pygame.Surface):
        """Draw all god mode overlays."""
        if not self.active:
            return
        # World overlay (NPC labels, settlement boundaries, etc.)
        if self.show_overlay:
            self._draw_world_overlay(screen)
        # Floating panel
        if self.panel_visible:
            self._draw_floating_panel(screen)
        # Coordinate readout at mouse position (always shown)
        self._draw_coord_readout(screen)
        # Live editing panels (drawn on top)
        self.tweaker.draw(screen)
        self.python_console.draw(screen)

    # ================================================================
    # COORDINATE READOUT
    # ================================================================

    def _draw_coord_readout(self, screen: pygame.Surface):
        """Draw coordinate readout at the mouse cursor position."""
        camera = self.game.camera
        mx, my = pygame.mouse.get_pos()
        wx, wy = camera.screen_to_world(float(mx), float(my))
        coord_text = f"({int(wx)}, {int(wy)})"
        coord_surf = self.font_tiny.render(coord_text, True, (160, 160, 160))
        screen.blit(coord_surf, (mx + 12, my + 2))

    # ================================================================
    # FLOATING PANEL
    # ================================================================

    def _draw_floating_panel(self, screen: pygame.Surface):
        """Draw the floating god mode panel with tabs and content."""
        px, py = self.panel_x, self.panel_y

        # Panel background
        panel_surf = pygame.Surface((PANEL_W, PANEL_H), pygame.SRCALPHA)
        panel_surf.fill(GOD_PANEL_BG)
        screen.blit(panel_surf, (px, py))

        # Border
        pygame.draw.rect(screen, (60, 120, 80), (px, py, PANEL_W, PANEL_H), 1,
                         border_radius=3)

        # Title bar (draggable)
        title_bar = pygame.Surface((PANEL_W, 28), pygame.SRCALPHA)
        title_bar.fill((30, 35, 50, 250))
        screen.blit(title_bar, (px, py))
        pygame.draw.line(screen, (60, 120, 80), (px, py + 28),
                         (px + PANEL_W, py + 28))

        # Title
        title = self.font_md.render("GOD MODE", True, GOD_ACCENT)
        screen.blit(title, (px + 8, py + 5))

        # Overlay toggle (small button in title bar)
        ov_x = px + PANEL_W - 75
        ov_color = GOD_BTN_ACTIVE if self.show_overlay else GOD_BTN_INACTIVE
        pygame.draw.rect(screen, ov_color, (ov_x, py + 4, 65, 20),
                         border_radius=3)
        ov_text = self.font_tiny.render("Overlay", True, WHITE)
        screen.blit(ov_text, (ov_x + 8, py + 8))

        # Tabs (below title bar)
        tab_y = py + 30
        tab_w = PANEL_W // len(self.tabs)
        for i, tab_name in enumerate(self.tabs):
            tx = px + i * tab_w
            active = (i == self.current_tab)
            color = GOD_TAB_ACTIVE if active else GOD_TAB_INACTIVE
            pygame.draw.rect(screen, color, (tx, tab_y, tab_w - 1, 22))
            if active:
                pygame.draw.rect(screen, (100, 200, 120),
                                 (tx, tab_y, tab_w - 1, 22), 1)
            # Tab label with F-key shortcut
            label = self.font_tiny.render(f"F{i+1} {tab_name}", True, WHITE)
            screen.blit(label, (tx + 4, tab_y + 5))

        # Tool buttons (below tabs)
        tool_y = tab_y + 24
        tools = [
            ("1", "Inspect", "inspect"),
            ("2", "Paint", "paint"),
            ("3", "Spawn", "spawn"),
            ("4", "Build", "build"),
            ("5", "Edit", "edit"),
        ]
        tool_bw = (PANEL_W - 16) // len(tools)
        for i, (key, name, tool_id) in enumerate(tools):
            bx = px + 8 + i * tool_bw
            active = (self.tool == tool_id)
            color = GOD_BTN_ACTIVE if active else GOD_BTN_INACTIVE
            pygame.draw.rect(screen, color, (bx, tool_y, tool_bw - 2, 20),
                             border_radius=2)
            if active:
                pygame.draw.rect(screen, (100, 200, 120),
                                 (bx, tool_y, tool_bw - 2, 20), 1,
                                 border_radius=2)
            btn_label = self.font_tiny.render(f"[{key}]{name}", True, WHITE)
            screen.blit(btn_label, (bx + 3, tool_y + 4))

        # Utility buttons (tweaker, reload, console) below tools
        util_y = tool_y + 22
        util_items = [
            ("[F6] Tweak", self.tweaker.visible),
            ("[F7] Reload", False),
            ("[~] Console", self.python_console.visible),
        ]
        util_bw = (PANEL_W - 16) // len(util_items)
        for i, (label, is_active) in enumerate(util_items):
            bx = px + 8 + i * util_bw
            color = GOD_BTN_ACTIVE if is_active else GOD_BTN_INACTIVE
            pygame.draw.rect(screen, color, (bx, util_y, util_bw - 2, 18),
                             border_radius=2)
            if is_active:
                pygame.draw.rect(screen, (100, 200, 120),
                                 (bx, util_y, util_bw - 2, 18), 1,
                                 border_radius=2)
            btn_label = self.font_tiny.render(label, True, WHITE)
            screen.blit(btn_label, (bx + 3, util_y + 3))

        # Separator
        sep_y = util_y + 20
        pygame.draw.line(screen, (60, 80, 70),
                         (px + 4, sep_y), (px + PANEL_W - 4, sep_y))

        # Content area
        content_y = sep_y + 2
        content_h = PANEL_H - (content_y - py) - 4

        # Draw the active tab/panel content
        self._draw_panel_content(screen, px + 4, content_y, PANEL_W - 8,
                                 content_h)

    def _handle_panel_click(self, local_x: int, local_y: int, button: int):
        """Handle click inside the floating panel (local coordinates)."""
        # Title bar overlay toggle
        if local_y < 28:
            if local_x > PANEL_W - 75:
                self.show_overlay = not self.show_overlay
            return

        # Tabs
        if 30 <= local_y < 52:
            tab_w = PANEL_W // len(self.tabs)
            idx = local_x // tab_w
            if 0 <= idx < len(self.tabs):
                self.current_tab = idx
                self.current_panel = self.tab_keys[idx]
                self.timeline_scroll = 0
                self.economy_scroll = 0
            return

        # Tool buttons
        if 54 <= local_y < 74:
            tools = ["inspect", "paint", "spawn", "build", "edit"]
            tool_bw = (PANEL_W - 16) // len(tools)
            idx = (local_x - 8) // tool_bw
            if 0 <= idx < len(tools):
                self.tool = tools[idx]
            return

        # Utility buttons
        if 76 <= local_y < 94:
            util_bw = (PANEL_W - 16) // 3
            idx = (local_x - 8) // util_bw
            if idx == 0:
                self.tweaker.toggle()
            elif idx == 1:
                results = self.hot_reloader.reload_all_safe()
                for mod_name, ok, msg in results:
                    status = "OK" if ok else "FAIL"
                    color = GREEN if ok else RED
                    self.game.notifications.add(f"[{status}] {msg}", 2.0,
                                                color)
            elif idx == 2:
                self.python_console.toggle()
            return

    # ================================================================
    # INSPECT (click detection)
    # ================================================================

    def _inspect_at(self, tile_x: int, tile_y: int,
                    world_x: float, world_y: float):
        """Inspect whatever is at the given world position."""
        game = self.game

        # 1. Check for NPC at position (within 1.5 tiles)
        best_npc = None
        best_dist = 2.0
        for npc in game.world_mgr.npcs:
            d = math.sqrt((npc.x - world_x) ** 2 + (npc.y - world_y) ** 2)
            if d < best_dist:
                best_dist = d
                best_npc = npc

        if best_npc:
            self.selected_entity = best_npc
            self.current_panel = "npc"
            self.current_tab = 1
            if not self.panel_visible:
                self.panel_visible = True
            return

        # 2. Check for creature at position
        best_creature = None
        best_dist = 2.0
        for c in game.world_mgr.creatures:
            d = math.sqrt((c.x - world_x) ** 2 + (c.y - world_y) ** 2)
            if d < best_dist:
                best_dist = d
                best_creature = c

        if best_creature:
            self.selected_entity = best_creature
            self.current_panel = "creature"
            if not self.panel_visible:
                self.panel_visible = True
            return

        # 3. Check for settlement
        structure = game.world.get_structure_at(float(tile_x), float(tile_y))
        if structure:
            self.selected_settlement_name = structure.name
            self.current_panel = "settlement"
            self.current_tab = 0
            if not self.panel_visible:
                self.panel_visible = True
            return

        # 4. Fall back to tile inspector
        self.selected_tile = (tile_x, tile_y)
        self.current_panel = "tile"
        if not self.panel_visible:
            self.panel_visible = True

    # ================================================================
    # PANEL CONTENT DISPATCHER
    # ================================================================

    def _draw_panel_content(self, screen: pygame.Surface,
                            cx: int, cy: int, cw: int, ch: int):
        """Draw content for the current tab/panel inside the floating panel."""
        # If an entity is inspected, show its inspector regardless of tab
        if self.current_panel == "npc" and self.selected_entity:
            self._draw_npc_inspector(screen, cx, cy, cw, ch)
            return
        if self.current_panel == "creature" and self.selected_entity:
            self._draw_creature_inspector(screen, cx, cy, cw, ch)
            return
        if self.current_panel == "tile" and self.selected_tile:
            self._draw_tile_inspector(screen, cx, cy, cw, ch)
            return
        if self.current_panel == "settlement" and self.selected_settlement_name:
            self._draw_settlement_inspector(screen, cx, cy, cw, ch)
            return

        # Otherwise, draw the current tab content
        dispatch = {
            0: self._draw_settlement_tab,
            1: self._draw_npc_tab,
            2: self._draw_economy_dashboard,
            3: self._draw_world_stats,
            4: self._draw_timeline,
        }
        fn = dispatch.get(self.current_tab)
        if fn:
            fn(screen, cx, cy, cw, ch)

    # ================================================================
    # TEXT PANEL HELPER (renders into a clipped region)
    # ================================================================

    def _draw_text_lines(self, screen: pygame.Surface, lines: List,
                         px: int, py: int, pw: int, ph: int,
                         scroll: int = 0):
        """Draw lines of text into a clipped region.

        Each line can be a str or a (str, color_tuple) pair.
        """
        line_h = 15

        # Clip rendering
        clip_rect = pygame.Rect(px, py, pw, ph)
        old_clip = screen.get_clip()
        screen.set_clip(clip_rect)

        y = py + 4 - scroll * line_h
        for line_data in lines:
            if isinstance(line_data, tuple):
                text, color = line_data
            else:
                text = line_data
                color = None

            if y + line_h < py:
                y += line_h
                continue
            if y > py + ph:
                break

            # Determine color from content if not specified
            if color is None:
                if text.startswith("==="):
                    color = GOD_HEADER
                    font = self.font_md
                elif text.startswith("---"):
                    color = GOD_SUBHEADER
                    font = self.font_sm
                elif text.startswith("  "):
                    color = UI_TEXT
                    font = self.font_sm
                else:
                    color = UI_TEXT
                    font = self.font_sm
            else:
                font = self.font_sm

            if text.strip():
                surf = font.render(text, True, color)
                screen.blit(surf, (px + 4, y))
            y += line_h

        screen.set_clip(old_clip)

    # ================================================================
    # TAB: SETTLEMENT (no entity selected)
    # ================================================================

    def _draw_settlement_tab(self, screen, cx, cy, cw, ch):
        """Show settlement list when no specific settlement is selected."""
        lines = [
            "=== SETTLEMENTS ===",
            "",
            "Click on a settlement to inspect it.",
            "",
        ]
        game = self.game
        for s in game.world.structures:
            if s.kind in ('hamlet', 'village', 'town', 'city', 'castle'):
                lines.append(f"  {s.name} ({s.kind})")
        self._draw_text_lines(screen, lines, cx, cy, cw, ch)

    # ================================================================
    # TAB: NPC (no entity selected)
    # ================================================================

    def _draw_npc_tab(self, screen, cx, cy, cw, ch):
        """Show NPC summary when no specific NPC is selected."""
        lines = [
            "=== NPC OVERVIEW ===",
            "",
            "Click on an NPC to inspect them.",
            "",
        ]
        game = self.game
        # Show nearby NPCs
        player = game.player
        nearby = []
        for npc in game.world_mgr.npcs:
            d = math.sqrt((npc.x - player.x)**2 + (npc.y - player.y)**2)
            if d < 30:
                nearby.append((d, npc))
        nearby.sort(key=lambda x: x[0])
        lines.append(f"--- Nearby NPCs ({len(nearby)}) ---")
        for d, npc in nearby[:20]:
            act = getattr(npc, 'current_action', '') or npc.state
            lines.append(f"  {npc.name} ({npc.profession}) - {act}")
        self._draw_text_lines(screen, lines, cx, cy, cw, ch)

    # ================================================================
    # SETTLEMENT INSPECTOR
    # ================================================================

    def _draw_settlement_inspector(self, screen, cx, cy, cw, ch):
        """Draw settlement info inside the floating panel."""
        name = self.selected_settlement_name
        if not name:
            return

        game = self.game
        sim = game.simulation

        # World effects data
        we = sim.world_effects
        stores = we.get_settlement_stores(name)
        garrison = we.get_settlement_garrison(name)
        fort = we.get_settlement_fortification(name)
        livestock = we.get_settlement_livestock(name)
        farms = we.get_settlement_farms(name)

        # Find settlement plan
        sp = None
        for s in game.world.plan.settlements:
            if s.name == name:
                sp = s
                break

        # Find the structure for position info
        structure = None
        for s in game.world.structures:
            if s.name == name:
                structure = s
                break

        lines = [
            f"=== {name} ===",
            "",
        ]

        if sp:
            lines.extend([
                f"  Type: {sp.kind.title()}",
                f"  Specialization: {sp.specialization}",
                f"  Population (plan): {sp.population}",
                f"  Region: {sp.region}",
                f"  Race: {sp.race}",
                f"  Position: ({sp.x}, {sp.y})",
                f"  Radius: {sp.radius} tiles",
            ])
        elif structure:
            lines.extend([
                f"  Type: {structure.kind.title()}",
                f"  Position: ({structure.x}, {structure.y})",
                f"  Radius: {structure.radius} tiles",
            ])

        # Trade connections
        if sp and sp.trade_connections:
            lines.append("")
            lines.append("--- Trade Connections ---")
            for conn in sp.trade_connections[:6]:
                lines.append(f"  {conn}")

        # Stores
        if stores:
            lines.append("")
            lines.append("--- Stores ---")
            for good, qty in sorted(stores.items()):
                if qty > 0:
                    bar = "#" * min(20, int(qty) // 5)
                    lines.append(f"  {good:<16s} {int(qty):>5d} {bar}")

        # Military / Garrison
        lines.append("")
        lines.append("--- Military ---")
        troops = garrison.get("troops", 0) if isinstance(garrison, dict) else 0
        kingdom = garrison.get("kingdom", "") if isinstance(garrison, dict) else ""
        fort_level = fort.get("level", 0) if isinstance(fort, dict) else 0
        lines.extend([
            f"  Garrison: {troops} troops",
            f"  Kingdom: {kingdom or 'none'}",
            f"  Fort level: {fort_level}",
        ])

        # Livestock
        if livestock:
            lines.append("")
            lines.append("--- Livestock ---")
            for animal, count in sorted(livestock.items()):
                if count > 0:
                    lines.append(f"  {animal}: {count}")

        # Farms
        if farms:
            lines.append("")
            lines.append(f"--- Farms ({len(farms)}) ---")
            for farm in farms[:5]:
                crop = farm.get("crop", "?") if isinstance(farm, dict) else "?"
                lines.append(f"  {crop}")

        # NPCs in settlement
        if structure:
            nearby_npcs = []
            for npc in game.world_mgr.npcs:
                dx = npc.x - structure.x
                dy = npc.y - structure.y
                if dx * dx + dy * dy <= (structure.radius + 5) ** 2:
                    nearby_npcs.append(npc)
            lines.append("")
            lines.append(f"--- NPCs Nearby ({len(nearby_npcs)}) ---")
            for npc in nearby_npcs[:12]:
                action = npc.current_action or npc.state
                lines.append(f"  {npc.name} ({npc.profession}) - {action}")

        # Kingdom info
        if sp:
            for k in game.world.plan.kingdoms:
                if name in k.get("territory_settlements", []):
                    lines.append("")
                    lines.append(f"--- Kingdom: {k['name']} ---")
                    lines.append(f"  Ruler: {k.get('ruler_name', '?')}")
                    lines.append(f"  Race: {k.get('race', '?')}")
                    gov_obj = sim.governance.kingdoms.get(k["name"])
                    if gov_obj:
                        lines.append(f"  Treasury: {gov_obj.treasury:.0f}g")
                        lines.append(f"  Tax rate: {gov_obj.tax_rate:.0%}")
                    break

        self._draw_text_lines(screen, lines, cx, cy, cw, ch)

    # ================================================================
    # NPC INSPECTOR
    # ================================================================

    def _draw_npc_inspector(self, screen, cx, cy, cw, ch):
        """Draw NPC character sheet inside the floating panel."""
        npc = self.selected_entity
        if npc is None or not hasattr(npc, 'name'):
            lines = [
                "=== NPC INSPECTOR ===",
                "",
                "Click on an NPC to inspect them.",
            ]
            self._draw_text_lines(screen, lines, cx, cy, cw, ch)
            return

        # Highlight selected NPC on screen
        camera = self.game.camera
        sx, sy = camera.world_to_screen(npc.x, npc.y)
        if 0 <= sx < SCREEN_WIDTH and 0 <= sy < SCREEN_HEIGHT:
            pygame.draw.circle(screen, GOD_SELECTION_RING,
                               (int(sx), int(sy)), 16, 2)

        # Header
        lines = [
            f"=== {npc.name} ===",
            f"  Race: {getattr(npc, 'race', '?')}  Class: {getattr(npc, 'char_class', '?')}",
            f"  Profession: {npc.profession}  Level: {getattr(npc, 'level', 1)}",
            f"  Title: {getattr(npc, 'title', '?')}  Faction: {getattr(npc, 'faction', '')}",
            f"  Alignment: {getattr(npc, 'alignment', '?')}",
            f"  Age: {getattr(npc, 'age', '?')} ({getattr(npc, 'age_category', '?')})",
            f"  Deity: {getattr(npc, 'deity', 'none')}",
            "",
            "--- Vitals ---",
            f"  HP: {npc.hp:.0f}/{npc.max_hp}  AC: {getattr(npc, 'armor_class', 10)}",
            f"  Gold: {getattr(npc, 'npc_gold', 0):.0f}",
            f"  Position: ({npc.x:.1f}, {npc.y:.1f})",
            f"  Consciousness: {getattr(npc, 'consciousness', 0)}",
        ]

        # Needs
        needs = getattr(npc, 'needs', {})
        if needs:
            lines.append("")
            lines.append("--- Needs ---")
            for need_name in ("hunger", "thirst", "rest", "social"):
                val = needs.get(need_name, 0)
                bar_len = int(val / 5)
                bar = "|" * bar_len + "." * (20 - bar_len)
                color = RED if val < 20 else (YELLOW if val < 40 else GREEN)
                lines.append((f"  {need_name:<8s} {val:5.0f} [{bar}]", color))

        # Ability scores
        scores = getattr(npc, 'ability_scores', {})
        if scores:
            lines.append("")
            lines.append("--- Ability Scores ---")
            for attr in ("strength", "dexterity", "constitution",
                         "intelligence", "wisdom", "charisma"):
                val = scores.get(attr, 10)
                from game.data.dnd import ability_modifier
                mod = ability_modifier(val)
                mod_str = f"+{mod}" if mod >= 0 else str(mod)
                lines.append(f"  {attr[:3].upper()}: {val} ({mod_str})")

        # Skills (top 8)
        skills = getattr(npc, 'npc_skills', {})
        if skills:
            lines.append("")
            lines.append("--- Skills (top 8) ---")
            sorted_skills = sorted(skills.items(), key=lambda x: -x[1])[:8]
            for skill, level in sorted_skills:
                label = skill.replace("_", " ").title()
                lines.append(f"  {label:<18s} {level}")

        # Personality
        lines.append("")
        lines.append("--- Personality ---")
        lines.append(f"  {getattr(npc, 'personality_desc', '?')}")
        traits = getattr(npc, 'social_traits', [])
        if traits:
            lines.append(f"  Traits: {', '.join(traits[:4])}")
        lines.append(f"  Friendliness: {getattr(npc, 'friendliness', 0):.2f}")
        lines.append(f"  Curiosity: {getattr(npc, 'curiosity', 0):.2f}")
        lines.append(f"  Bravery: {getattr(npc, 'bravery', 0):.2f}")
        lines.append(f"  Mood: {getattr(npc, 'mood', 0):.2f}")

        # Current activity
        lines.append("")
        lines.append("--- Current Activity ---")
        lines.append(f"  State: {getattr(npc, 'state', '?')}")
        lines.append(f"  Action: {getattr(npc, 'current_action', '') or 'none'}")
        lines.append(f"  Goal: {getattr(npc, 'current_goal', '') or 'none'}")
        reason = getattr(npc, 'last_decision_reason', '')
        if reason:
            lines.append(f"  Reason: {reason[:45]}")

        # Inventory
        inv = getattr(npc, 'npc_inventory', [])
        if inv:
            lines.append("")
            lines.append(f"--- Inventory ({len(inv)}) ---")
            for item in inv[:8]:
                count_str = f" x{item.count}" if getattr(item, 'stackable', False) and item.count > 1 else ""
                lines.append(f"  {item.name}{count_str}")

        # Social
        lines.append("")
        lines.append("--- Social ---")
        friends = getattr(npc, 'friends', [])
        enemies = getattr(npc, 'enemies', [])
        lines.append(f"  Player rel: {getattr(npc, 'player_relationship', 0)}")
        if friends:
            lines.append(f"  Friends: {', '.join(friends[:4])}")
        if enemies:
            lines.append(f"  Enemies: {', '.join(enemies[:4])}")

        # Party info
        party_id = getattr(npc, 'party_id', None)
        if party_id:
            lines.append(f"  Party: {party_id} ({getattr(npc, 'party_role', '?')})")

        # Spells
        spells = getattr(npc, 'known_spells', [])
        if spells:
            lines.append("")
            lines.append("--- Spells ---")
            for spell in spells[:6]:
                lines.append(f"  {spell}")

        # Memories (last 6)
        mems = getattr(npc, 'memories', [])
        if mems:
            lines.append("")
            lines.append(f"--- Memories (last 6 of {len(mems)}) ---")
            for mem in mems[-6:]:
                if isinstance(mem, dict):
                    text = mem.get('text', str(mem))[:55]
                else:
                    text = str(mem)[:55]
                lines.append(f"  {text}")

        # Long-term goals
        goals = getattr(npc, 'long_term_goals', [])
        if goals:
            lines.append("")
            lines.append("--- Long-term Goals ---")
            for g in goals[:4]:
                lines.append(f"  {g[:55]}")

        self._draw_text_lines(screen, lines, cx, cy, cw, ch)

    # ================================================================
    # CREATURE INSPECTOR
    # ================================================================

    def _draw_creature_inspector(self, screen, cx, cy, cw, ch):
        """Draw creature info inside the floating panel."""
        c = self.selected_entity
        if c is None or not hasattr(c, 'kind'):
            lines = [
                "=== CREATURE INSPECTOR ===",
                "",
                "Click on a creature to inspect it.",
            ]
            self._draw_text_lines(screen, lines, cx, cy, cw, ch)
            return

        # Highlight
        camera = self.game.camera
        sx, sy = camera.world_to_screen(c.x, c.y)
        if 0 <= sx < SCREEN_WIDTH and 0 <= sy < SCREEN_HEIGHT:
            pygame.draw.circle(screen, (255, 160, 80),
                               (int(sx), int(sy)), 14, 2)

        lines = [
            f"=== {c.kind.replace('_', ' ').title()} ===",
            "",
            f"  HP: {c.hp:.0f}/{c.max_hp}",
            f"  Damage: {getattr(c, 'damage', '?')}",
            f"  Speed: {getattr(c, 'speed', '?')}",
            f"  AC: {getattr(c, 'armor_class', 10)}",
            f"  XP value: {getattr(c, 'xp_value', '?')}",
            f"  Type: {getattr(c, 'monster_type', 'beast')}",
            f"  CR: {getattr(c, 'cr', '?')}",
            f"  Passive: {getattr(c, 'passive', False)}",
            "",
            f"  Position: ({c.x:.1f}, {c.y:.1f})",
            f"  State: {getattr(c, 'state', '?')}",
            f"  Alive: {getattr(c, 'alive', c.hp > 0)}",
        ]

        # Settlement ownership (livestock)
        home = getattr(c, 'home_settlement', None)
        if home:
            lines.append(f"  Home: {home}")

        self._draw_text_lines(screen, lines, cx, cy, cw, ch)

    # ================================================================
    # TILE INSPECTOR
    # ================================================================

    def _draw_tile_inspector(self, screen, cx, cy, cw, ch):
        """Draw tile info inside the floating panel."""
        tx, ty = self.selected_tile or (0, 0)
        if self.selected_tile is None:
            return

        world = self.game.world

        # Get terrain type
        terrain_id = -1
        try:
            terrain_id = world.tiles[ty][tx]
        except (IndexError, TypeError):
            pass

        # Terrain name lookup
        terrain_names = {v: k for k, v in vars(
            __import__('game.settings', fromlist=[''])).items()
            if isinstance(v, int) and k.isupper() and not k.startswith('_')
            and k not in ('SCREEN_WIDTH', 'SCREEN_HEIGHT', 'FPS',
                          'TILE_SIZE', 'WORLD_WIDTH', 'WORLD_HEIGHT',
                          'WORLD_WIDTH_NEW', 'WORLD_HEIGHT_NEW',
                          'CHUNK_SIZE', 'METERS_PER_TILE')}
        terrain_name = terrain_names.get(terrain_id, f"unknown ({terrain_id})")

        color = TERRAIN_COLORS.get(terrain_id, (0, 0, 0))

        lines = [
            f"=== TILE ({tx}, {ty}) ===",
            "",
            f"  Terrain: {terrain_name}",
            f"  ID: {terrain_id}",
            (f"  Color: ({color[0]}, {color[1]}, {color[2]})", color),
        ]

        # Walk cost
        from game.settings import TERRAIN_WALK_COST
        walk_cost = TERRAIN_WALK_COST.get(terrain_id, 1.0)
        passable = "yes" if walk_cost < 999 else "NO"
        lines.extend([
            f"  Walk cost: {walk_cost}",
            f"  Passable: {passable}",
        ])

        # Chunk info
        if hasattr(world, 'chunk_grid'):
            cx_chunk = tx // TILE_SIZE
            cy_chunk = ty // TILE_SIZE
            lines.append(f"  Chunk: ({cx_chunk}, {cy_chunk})")

        # Structure at tile
        structure = world.get_structure_at(float(tx), float(ty))
        if structure:
            lines.append("")
            lines.append(f"--- Structure ---")
            lines.append(f"  Name: {structure.name}")
            lines.append(f"  Kind: {structure.kind}")
            lines.append(f"  Radius: {structure.radius}")

        # NPCs/creatures on tile
        nearby_npcs = []
        for npc in self.game.world_mgr.npcs:
            if int(npc.x) == tx and int(npc.y) == ty:
                nearby_npcs.append(npc)
        if nearby_npcs:
            lines.append("")
            lines.append(f"--- NPCs on tile ---")
            for npc in nearby_npcs:
                lines.append(f"  {npc.name} ({npc.profession})")

        nearby_creatures = []
        for cr in self.game.world_mgr.creatures:
            if int(cr.x) == tx and int(cr.y) == ty:
                nearby_creatures.append(cr)
        if nearby_creatures:
            lines.append("")
            lines.append(f"--- Creatures on tile ---")
            for cr in nearby_creatures:
                lines.append(f"  {cr.kind}")

        self._draw_text_lines(screen, lines, cx, cy, cw, ch)

    # ================================================================
    # ECONOMY DASHBOARD
    # ================================================================

    def _draw_economy_dashboard(self, screen, cx, cy, cw, ch):
        """Draw economy overview inside the floating panel."""
        game = self.game

        lines = [
            "=== ECONOMY DASHBOARD ===",
            "",
        ]

        # Kingdom treasuries
        lines.append("--- Kingdoms ---")
        plan_kingdoms = getattr(game.world.plan, 'kingdoms', [])
        gov = game.simulation.governance

        for k in plan_kingdoms:
            k_name = k['name']
            kingdom_obj = gov.kingdoms.get(k_name)
            treasury = getattr(kingdom_obj, 'treasury', k.get('treasury', 0))
            tax_rate = getattr(kingdom_obj, 'tax_rate', 0.1)
            n_settlements = len(k.get('territory_settlements', []))
            ruler = k.get('ruler_name', '?')
            lines.append(f"  {k_name[:28]}")
            lines.append(
                f"    {treasury:.0f}g  tax:{tax_rate:.0%}  "
                f"{n_settlements} sett  ruler:{ruler}")

        # Totals
        lines.append("")
        lines.append("--- Population ---")
        live_npcs = len(game.world_mgr.npcs)
        dormant = game.world_mgr.dormant_npc_count
        creatures = len(game.world_mgr.creatures)
        total_gold = sum(getattr(n, 'npc_gold', 0) for n in game.world_mgr.npcs)
        player_gold = game.player.gold

        lines.extend([
            f"  Live NPCs: {live_npcs}",
            f"  Dormant NPCs: {dormant}",
            f"  Creatures: {creatures}",
            "",
            "--- Gold ---",
            f"  Player gold: {player_gold}",
            f"  NPC total gold: {total_gold:.0f}",
            f"  Kingdom treasuries: {sum(getattr(gov.kingdoms.get(k['name']), 'treasury', 0) for k in plan_kingdoms):.0f}",
        ])

        # Profession breakdown
        lines.append("")
        lines.append("--- Professions (live NPCs) ---")
        prof_counts: Dict[str, int] = {}
        for npc in game.world_mgr.npcs:
            p = getattr(npc, 'profession', '?')
            prof_counts[p] = prof_counts.get(p, 0) + 1
        for prof, count in sorted(prof_counts.items(),
                                   key=lambda x: -x[1])[:15]:
            bar = "#" * min(15, count)
            lines.append(f"  {prof:<16s} {count:>3d} {bar}")

        # Diplomacy
        diplo = getattr(gov, 'diplomacy', {})
        if diplo:
            lines.append("")
            lines.append(f"--- Diplomacy ({len(diplo)}) ---")
            for pair, rel in list(diplo.items())[:10]:
                stance = getattr(rel, 'stance', '?') if hasattr(rel, 'stance') else str(rel)
                lines.append(f"  {pair}: {stance}")

        self._draw_text_lines(screen, lines, cx, cy, cw, ch,
                              scroll=self.economy_scroll)

    # ================================================================
    # WORLD STATISTICS
    # ================================================================

    def _draw_world_stats(self, screen, cx, cy, cw, ch):
        """Draw world overview statistics inside the floating panel."""
        game = self.game
        plan = game.world.plan
        sim = game.simulation

        # Settlement kind counts
        kinds: Dict[str, int] = {}
        for sp in plan.settlements:
            kinds[sp.kind] = kinds.get(sp.kind, 0) + 1

        lines = [
            "=== WORLD STATISTICS ===",
            f"  Day: {game.time_sys.day}  {game.time_sys.time_string}",
            f"  World size: {plan.width} x {plan.height}",
            f"  Seed: {plan.seed}",
            "",
            "--- Settlements ---",
        ]
        total_settlements = 0
        for kind, count in sorted(kinds.items(), key=lambda x: -x[1]):
            lines.append(f"  {kind.title():<12s} {count}")
            total_settlements += count
        lines.append(f"  Total: {total_settlements}")

        # Regions
        regions = getattr(plan, 'regions', [])
        if regions:
            lines.append("")
            lines.append(f"--- Regions ({len(regions)}) ---")
            for r in regions[:10]:
                lines.append(f"  {r.name}")

        # Kingdoms
        lines.append("")
        lines.append(f"--- Kingdoms ({len(plan.kingdoms)}) ---")
        for k in plan.kingdoms:
            lines.append(f"  {k['name']} ({k.get('race', '?')})")

        # Diplomacy
        gov = sim.governance
        lines.append(f"  Diplomacy pairs: {len(getattr(gov, 'diplomacy', {}))}")

        # Population
        lines.append("")
        lines.append("--- Population ---")
        lines.append(f"  Live NPCs: {len(game.world_mgr.npcs)}")
        lines.append(f"  Dormant NPCs: {game.world_mgr.dormant_npc_count}")
        lines.append(f"  Creatures: {len(game.world_mgr.creatures)}")

        # Class distribution
        class_counts: Dict[str, int] = {}
        for npc in game.world_mgr.npcs:
            cc = getattr(npc, 'char_class', '?')
            class_counts[cc] = class_counts.get(cc, 0) + 1
        if class_counts:
            lines.append("")
            lines.append("--- Classes ---")
            for cls, cnt in sorted(class_counts.items(),
                                    key=lambda x: -x[1])[:10]:
                lines.append(f"  {cls:<14s} {cnt}")

        # Race distribution
        race_counts: Dict[str, int] = {}
        for npc in game.world_mgr.npcs:
            r = getattr(npc, 'race', '?')
            race_counts[r] = race_counts.get(r, 0) + 1
        if race_counts:
            lines.append("")
            lines.append("--- Races ---")
            for race, cnt in sorted(race_counts.items(),
                                     key=lambda x: -x[1])[:10]:
                lines.append(f"  {race:<14s} {cnt}")

        # World effects log summary
        we = sim.world_effects
        log = we.get_event_log()
        lines.append("")
        lines.append(f"--- Recent Events ({len(log)}) ---")
        for e in log[-8:]:
            lines.append(f"  {str(e)[:55]}")

        # Simulation event log
        sim_log = getattr(sim, 'event_log', [])
        if sim_log:
            lines.append("")
            lines.append(f"--- Sim Log (last 8 of {len(sim_log)}) ---")
            for e in sim_log[-8:]:
                lines.append(f"  {str(e)[:55]}")

        self._draw_text_lines(screen, lines, cx, cy, cw, ch)

    # ================================================================
    # TIMELINE
    # ================================================================

    def _draw_timeline(self, screen, cx, cy, cw, ch):
        """Draw scrollable event timeline inside the floating panel."""
        game = self.game
        sim = game.simulation

        # Collect events from multiple sources
        all_events: List[Tuple[str, str]] = []

        # World plan history
        history = getattr(game.world.plan, '_history', [])
        for e in history:
            all_events.append(("history", str(e)[:65]))

        # Simulation event log
        sim_log = getattr(sim, 'event_log', [])
        for e in sim_log:
            all_events.append(("sim", str(e)[:65]))

        # World effects log
        we_log = sim.world_effects.get_event_log()
        for e in we_log:
            all_events.append(("world", str(e)[:65]))

        # Dead NPCs
        dead = getattr(sim, 'dead_npcs', [])
        for d in dead:
            name = d.get('name', '?') if isinstance(d, dict) else str(d)
            cause = d.get('cause', '?') if isinstance(d, dict) else ''
            all_events.append(("death", f"{name} died: {cause}"))

        lines = [
            f"=== TIMELINE ({len(all_events)} events) ===",
            "  [Up/Down to scroll]",
            "",
        ]

        # Color-coded entries
        type_colors = {
            "history": (180, 160, 100),
            "sim": (140, 180, 220),
            "world": (160, 200, 160),
            "death": (220, 100, 100),
        }

        for etype, text in all_events:
            color = type_colors.get(etype, UI_TEXT)
            prefix = {"history": "H", "sim": "S", "world": "W",
                      "death": "X"}.get(etype, "?")
            lines.append((f"  [{prefix}] {text}", color))

        self._draw_text_lines(screen, lines, cx, cy, cw, ch,
                              scroll=self.timeline_scroll)

    # ================================================================
    # WORLD OVERLAY (drawn on the game world, not in the panel)
    # ================================================================

    def _draw_world_overlay(self, screen: pygame.Surface):
        """Draw information overlays directly on the game world."""
        camera = self.game.camera
        game = self.game

        # NPC action labels
        for npc in game.world_mgr.npcs:
            sx, sy = camera.world_to_screen(npc.x, npc.y)
            if not (-20 <= sx <= SCREEN_WIDTH + 20 and
                    -20 <= sy <= SCREEN_HEIGHT + 20):
                continue

            # Name label
            action = getattr(npc, 'current_action', '') or getattr(npc, 'state', 'idle')
            label_text = f"{npc.name}: {action}"
            label = self.font_tiny.render(label_text, True, GOD_OVERLAY_NPC)

            # Dark background for readability
            lw, lh = label.get_size()
            bg = pygame.Surface((lw + 4, lh + 2), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 140))
            screen.blit(bg, (int(sx) - lw // 2 - 2, int(sy) - 22))
            screen.blit(label, (int(sx) - lw // 2, int(sy) - 21))

            # Needs bar (tiny horizontal bars under name)
            needs = getattr(npc, 'needs', {})
            bar_y = int(sy) - 8
            bar_x = int(sx) - 16
            for need_name, color in [("hunger", (80, 180, 80)),
                                     ("thirst", (80, 130, 220)),
                                     ("rest", (200, 180, 80)),
                                     ("social", (180, 100, 180))]:
                val = needs.get(need_name, 100)
                bar_w = int(8 * val / 100)
                need_color = color if val > 20 else (220, 60, 60)
                pygame.draw.rect(screen, need_color,
                                 (bar_x, bar_y, bar_w, 2))
                bar_x += 10

        # Creature labels
        for c in game.world_mgr.creatures:
            sx, sy = camera.world_to_screen(c.x, c.y)
            if not (0 <= sx <= SCREEN_WIDTH and 0 <= sy <= SCREEN_HEIGHT):
                continue
            kind_label = c.kind.replace('_', ' ')
            hp_text = f"{kind_label} HP:{c.hp:.0f}"
            label = self.font_tiny.render(hp_text, True, GOD_OVERLAY_CREATURE)
            lw = label.get_width()
            bg = pygame.Surface((lw + 4, 12), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 120))
            screen.blit(bg, (int(sx) - lw // 2 - 2, int(sy) - 18))
            screen.blit(label, (int(sx) - lw // 2, int(sy) - 17))

        # Settlement boundaries
        for structure in game.world.structures:
            if structure.kind not in ('hamlet', 'village', 'town', 'city',
                                      'castle'):
                continue
            sx, sy = camera.world_to_screen(structure.x, structure.y)
            r = structure.radius * TILE_SIZE
            if not (-r <= sx <= SCREEN_WIDTH + r and
                    -r <= sy <= SCREEN_HEIGHT + r):
                continue

            # Circle outline
            kind_colors = {
                'hamlet': (100, 140, 100),
                'village': (100, 160, 200),
                'town': (180, 160, 100),
                'city': (200, 180, 80),
                'castle': (200, 100, 100),
            }
            circle_color = kind_colors.get(structure.kind, (100, 100, 200))
            pygame.draw.circle(screen, circle_color,
                               (int(sx), int(sy)), int(r), 1)

            # Settlement name label
            name_surf = self.font_sm.render(
                f"{structure.name} ({structure.kind})",
                True, circle_color)
            nw = name_surf.get_width()
            bg = pygame.Surface((nw + 6, 16), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 160))
            screen.blit(bg, (int(sx) - nw // 2 - 3, int(sy) - r - 18))
            screen.blit(name_surf, (int(sx) - nw // 2, int(sy) - r - 17))

        # Highlight selected tile
        if self.selected_tile and self.current_panel == "tile":
            tx, ty = self.selected_tile
            sx, sy = camera.world_to_screen(tx, ty)
            pygame.draw.rect(screen, GOD_SELECTION_RING,
                             (int(sx), int(sy), TILE_SIZE, TILE_SIZE), 2)

        # Highlight selected settlement
        if (self.selected_settlement_name and
                self.current_panel == "settlement"):
            for s in game.world.structures:
                if s.name == self.selected_settlement_name:
                    sx, sy = camera.world_to_screen(s.x, s.y)
                    r = s.radius * TILE_SIZE
                    pygame.draw.circle(screen, GOD_SELECTION_RING,
                                       (int(sx), int(sy)), int(r), 2)
                    break
