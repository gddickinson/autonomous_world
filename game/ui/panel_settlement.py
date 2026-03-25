"""Settlement Overview panel — shows population, economy, morale at a glance.

Toggled with B key when in or near a settlement. Shows:
- Settlement name, kind, specialization
- Population count and job distribution
- Building list with types
- Kingdom treasury
- Morale/quality of life
- Trade connections
- Recent events from chronicle
"""

import math
import pygame
from typing import Optional, List, Dict
from game.settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    UI_BORDER, UI_TEXT, UI_HIGHLIGHT,
    WHITE, GRAY, YELLOW, GREEN, RED, BLUE, ORANGE,
)


# ================================================================
# COLORS
# ================================================================

HEADER_COLOR = (200, 180, 100)
SUBHEADER_COLOR = (140, 170, 220)
VALUE_COLOR = (200, 200, 200)
DIM_COLOR = (120, 120, 140)
GOOD_COLOR = (100, 200, 120)
BAD_COLOR = (220, 100, 80)
NEUTRAL_COLOR = (180, 180, 180)


def _find_player_settlement(world, player_x: float, player_y: float):
    """Find the settlement the player is in or nearest to (within radius).

    Returns a SettlementPlan or None.
    """
    if not hasattr(world, 'plan'):
        return None

    px, py = int(player_x), int(player_y)
    best = None
    best_dist = float('inf')

    for sp in world.plan.settlements:
        dx = px - sp.x
        dy = py - sp.y
        dist = math.sqrt(dx * dx + dy * dy)
        # Must be within the settlement's radius (+ some margin)
        if dist <= sp.radius + 5 and dist < best_dist:
            best = sp
            best_dist = dist

    return best


def _get_npc_job_distribution(npcs, settlement_name: str) -> Dict[str, int]:
    """Count NPCs by profession in a settlement."""
    jobs: Dict[str, int] = {}
    for npc in npcs:
        home = getattr(npc, 'home_settlement', '')
        if home == settlement_name and getattr(npc, 'alive', True):
            prof = getattr(npc, 'profession', 'Unknown')
            jobs[prof] = jobs.get(prof, 0) + 1
    return jobs


def _get_building_types(settlement) -> Dict[str, int]:
    """Count buildings by kind in a settlement."""
    types: Dict[str, int] = {}
    for bld in getattr(settlement, 'buildings', []):
        kind = bld.get('kind', bld.get('blueprint_name', 'unknown'))
        types[kind] = types.get(kind, 0) + 1
    return types


def _get_kingdom_info(world, settlement) -> Optional[Dict]:
    """Find the kingdom this settlement belongs to."""
    if not hasattr(world, 'plan'):
        return None
    for k in world.plan.kingdoms:
        territories = k.get('territory_settlements', [])
        if settlement.name in territories or k.get('capital_settlement') == settlement.name:
            return k
    return None


def _get_economy_info(world, settlement_name: str) -> Optional[object]:
    """Get economy data for a settlement if available."""
    if hasattr(world, '_economy_system'):
        econ_sys = world._economy_system
        if hasattr(econ_sys, 'get_settlement_economy'):
            return econ_sys.get_settlement_economy(settlement_name)
    return None


def _get_recent_events(chronicles, settlement_name: str, count: int = 5) -> List:
    """Get recent chronicle entries mentioning this settlement."""
    if not chronicles:
        return []
    events = []
    for entry in reversed(chronicles.entries):
        if settlement_name.lower() in entry.title.lower() or \
           settlement_name.lower() in entry.description.lower():
            events.append(entry)
            if len(events) >= count:
                break
    return events


class SettlementOverviewPanel:
    """Settlement overview panel showing vital stats at a glance."""

    def __init__(self):
        self.visible = False
        self._font_sm = None
        self._font_md = None
        self._font_lg = None
        self.scroll_offset = 0

    def _ensure_fonts(self):
        if self._font_sm is None:
            self._font_sm = pygame.font.SysFont("monospace", 13)
            self._font_md = pygame.font.SysFont("monospace", 16)
            self._font_lg = pygame.font.SysFont("monospace", 22)

    def toggle(self):
        self.visible = not self.visible
        self.scroll_offset = 0

    def scroll(self, direction: int):
        """Scroll panel content."""
        if self.visible:
            self.scroll_offset = max(0, self.scroll_offset + direction)

    def draw(self, screen: pygame.Surface, world, player, npcs,
             chronicles=None, economy_system=None):
        """Draw the settlement overview panel.

        Args:
            screen: pygame display surface
            world: game world (ChunkedWorld)
            player: player object
            npcs: list of all NPCs
            chronicles: ChronicleSystem or None
            economy_system: economy system or None
        """
        if not self.visible:
            return

        self._ensure_fonts()

        # Find the settlement the player is in
        settlement = _find_player_settlement(world, player.x, player.y)
        if not settlement:
            self._draw_no_settlement(screen)
            return

        # Panel dimensions
        pw, ph = 500, 520
        px = SCREEN_WIDTH // 2 - pw // 2
        py = SCREEN_HEIGHT // 2 - ph // 2

        # Background
        panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel_surf.fill((15, 15, 28, 225))
        screen.blit(panel_surf, (px, py))
        pygame.draw.rect(screen, UI_BORDER, (px, py, pw, ph), 2)

        # Title
        kind_str = settlement.kind.capitalize()
        spec = getattr(settlement, 'specialization', 'general')
        title = f"{settlement.name} ({kind_str})"
        title_surf = self._font_lg.render(title, True, HEADER_COLOR)
        screen.blit(title_surf, (px + 10, py + 8))

        if spec and spec != "general":
            spec_surf = self._font_sm.render(
                f"Specialization: {spec.replace('_', ' ').title()}",
                True, SUBHEADER_COLOR)
            screen.blit(spec_surf, (px + 10, py + 34))

        pygame.draw.line(screen, UI_BORDER,
                         (px + 5, py + 52), (px + pw - 5, py + 52))

        # Content area with scrolling
        y = py + 58
        col2 = px + pw // 2 + 10

        # --- LEFT COLUMN ---

        # Population
        pop_count = settlement.population
        # Count living NPCs in this settlement
        living_npcs = sum(1 for n in npcs
                          if getattr(n, 'home_settlement', '') == settlement.name
                          and getattr(n, 'alive', True))
        screen.blit(self._font_md.render("Population", True, SUBHEADER_COLOR),
                     (px + 12, y))
        y += 20
        screen.blit(self._font_sm.render(
            f"  Planned: {pop_count}  Active: {living_npcs}",
            True, VALUE_COLOR), (px + 12, y))
        y += 18

        # Job distribution
        jobs = _get_npc_job_distribution(npcs, settlement.name)
        if jobs:
            screen.blit(self._font_md.render("Jobs", True, SUBHEADER_COLOR),
                         (px + 12, y))
            y += 20
            sorted_jobs = sorted(jobs.items(), key=lambda x: -x[1])
            for job_name, count in sorted_jobs[:8]:
                screen.blit(self._font_sm.render(
                    f"  {job_name}: {count}", True, VALUE_COLOR),
                    (px + 12, y))
                y += 15
            if len(sorted_jobs) > 8:
                screen.blit(self._font_sm.render(
                    f"  ... +{len(sorted_jobs) - 8} more", True, DIM_COLOR),
                    (px + 12, y))
                y += 15
        y += 6

        # Buildings
        buildings = _get_building_types(settlement)
        if buildings:
            screen.blit(self._font_md.render("Buildings", True, SUBHEADER_COLOR),
                         (px + 12, y))
            y += 20
            sorted_bld = sorted(buildings.items(), key=lambda x: -x[1])
            for bld_name, count in sorted_bld[:6]:
                label = bld_name.replace('_', ' ').title()
                screen.blit(self._font_sm.render(
                    f"  {label}: {count}", True, VALUE_COLOR),
                    (px + 12, y))
                y += 15
            if len(sorted_bld) > 6:
                screen.blit(self._font_sm.render(
                    f"  ... +{len(sorted_bld) - 6} more", True, DIM_COLOR),
                    (px + 12, y))
                y += 15

        # --- RIGHT COLUMN ---
        ry = py + 58

        # Kingdom info
        kingdom = _get_kingdom_info(world, settlement)
        screen.blit(self._font_md.render("Kingdom", True, SUBHEADER_COLOR),
                     (col2, ry))
        ry += 20
        if kingdom:
            kname = kingdom.get('name', 'Unknown')
            ruler = kingdom.get('ruler_name', 'Unknown')
            treasury = kingdom.get('treasury', 0)
            screen.blit(self._font_sm.render(
                f"  {kname}", True, VALUE_COLOR), (col2, ry))
            ry += 15
            screen.blit(self._font_sm.render(
                f"  Ruler: {ruler}", True, VALUE_COLOR), (col2, ry))
            ry += 15
            treasury_color = GOOD_COLOR if treasury > 100 else (
                BAD_COLOR if treasury < 20 else VALUE_COLOR)
            screen.blit(self._font_sm.render(
                f"  Treasury: {treasury:.0f}g", True, treasury_color), (col2, ry))
            ry += 15
            is_capital = kingdom.get('capital_settlement') == settlement.name
            if is_capital:
                screen.blit(self._font_sm.render(
                    "  ** CAPITAL **", True, HEADER_COLOR), (col2, ry))
                ry += 15
        else:
            screen.blit(self._font_sm.render(
                "  Independent", True, DIM_COLOR), (col2, ry))
            ry += 15
        ry += 6

        # Morale / Quality of Life
        screen.blit(self._font_md.render("Morale", True, SUBHEADER_COLOR),
                     (col2, ry))
        ry += 20
        # Try to get economy/population stats
        econ = None
        if economy_system and hasattr(economy_system, 'get_settlement_economy'):
            econ = economy_system.get_settlement_economy(settlement.name)

        if econ:
            morale = getattr(econ, 'morale', getattr(econ, 'quality_of_life', 50))
            morale_color = GOOD_COLOR if morale > 60 else (
                BAD_COLOR if morale < 30 else VALUE_COLOR)
            screen.blit(self._font_sm.render(
                f"  Level: {morale:.0f}/100", True, morale_color), (col2, ry))
            ry += 15
            treasury_local = getattr(econ, 'treasury', 0)
            screen.blit(self._font_sm.render(
                f"  Local treasury: {treasury_local:.0f}g", True, VALUE_COLOR),
                (col2, ry))
            ry += 15
        else:
            # Estimate from NPC happiness
            happy_count = sum(1 for n in npcs
                              if getattr(n, 'home_settlement', '') == settlement.name
                              and getattr(n, 'alive', True)
                              and getattr(n, 'happiness', 50) > 50)
            total_local = max(1, living_npcs)
            morale_pct = int(happy_count / total_local * 100)
            morale_color = GOOD_COLOR if morale_pct > 60 else (
                BAD_COLOR if morale_pct < 30 else VALUE_COLOR)
            screen.blit(self._font_sm.render(
                f"  Happiness: {morale_pct}%", True, morale_color), (col2, ry))
            ry += 15
        ry += 6

        # Trade connections
        trade = getattr(settlement, 'trade_connections', [])
        screen.blit(self._font_md.render("Trade Routes", True, SUBHEADER_COLOR),
                     (col2, ry))
        ry += 20
        if trade:
            for tc in trade[:5]:
                screen.blit(self._font_sm.render(
                    f"  -> {tc}", True, VALUE_COLOR), (col2, ry))
                ry += 15
            if len(trade) > 5:
                screen.blit(self._font_sm.render(
                    f"  ... +{len(trade) - 5} more", True, DIM_COLOR),
                    (col2, ry))
                ry += 15
        else:
            screen.blit(self._font_sm.render(
                "  None", True, DIM_COLOR), (col2, ry))
            ry += 15
        ry += 6

        # Recent events
        events = _get_recent_events(chronicles, settlement.name)
        screen.blit(self._font_md.render("Recent Events", True, SUBHEADER_COLOR),
                     (col2, ry))
        ry += 20
        if events:
            from game.systems.chronicles import CATEGORY_COLORS
            for ev in events[:4]:
                ev_color = CATEGORY_COLORS.get(ev.category, VALUE_COLOR)
                text = ev.title if len(ev.title) <= 28 else ev.title[:25] + "..."
                screen.blit(self._font_sm.render(
                    f"  {text}", True, ev_color), (col2, ry))
                ry += 15
        else:
            screen.blit(self._font_sm.render(
                "  No recent events", True, DIM_COLOR), (col2, ry))

        # Footer hint
        hint = self._font_sm.render("[B] Close", True, DIM_COLOR)
        screen.blit(hint, (px + pw // 2 - hint.get_width() // 2, py + ph - 18))

    def _draw_no_settlement(self, screen: pygame.Surface):
        """Draw a message when player is not near a settlement."""
        self._ensure_fonts()
        pw, ph = 300, 60
        px = SCREEN_WIDTH // 2 - pw // 2
        py = SCREEN_HEIGHT // 2 - ph // 2

        panel_surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel_surf.fill((15, 15, 28, 220))
        screen.blit(panel_surf, (px, py))
        pygame.draw.rect(screen, UI_BORDER, (px, py, pw, ph), 1)

        text = self._font_md.render("Not near a settlement", True, DIM_COLOR)
        screen.blit(text, (px + pw // 2 - text.get_width() // 2, py + 10))
        hint = self._font_sm.render("[B] Close", True, DIM_COLOR)
        screen.blit(hint, (px + pw // 2 - hint.get_width() // 2, py + 35))
