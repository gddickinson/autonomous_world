"""God Mode Dashboard -- comprehensive world overview panel.

Toggled with TAB key when in god mode. Shows kingdom overview,
population stats, world stats, and a scrolling event feed.
"""

import pygame
from typing import Optional, List, Tuple, Dict

from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT

# Colors
DASH_BG = (10, 10, 20, 235)
DASH_BORDER = (60, 60, 80)
DASH_HEADER = (220, 200, 100)
DASH_TEXT = (200, 200, 210)
DASH_DIM = (120, 120, 140)
DASH_ACCENT = (180, 220, 100)
GOV_COLORS = {
    "feudalism": (80, 130, 220), "tribal": (200, 80, 80),
    "theocracy": (220, 200, 80), "republic": (80, 200, 100),
    "autocracy": (180, 80, 200), "merchant_republic": (200, 180, 80),
}
EVT_COLORS = {
    "war": (220, 80, 60), "trade": (200, 180, 80),
    "construction": (80, 130, 220), "social": (80, 200, 120),
    "disaster": (220, 140, 40), "death": (160, 120, 120),
}
MARGIN = 8
LEFT_W = 380


class GodDashboard:
    """Full-screen dashboard for god mode."""

    def __init__(self, game):
        self.game = game
        self.visible = False
        self.selected_kingdom: Optional[str] = None
        self.kingdom_scroll = 0
        self.event_scroll = 0
        self._fonts_ready = False

    def _ef(self):
        if self._fonts_ready:
            return
        self._ft = pygame.font.SysFont("monospace", 10)
        self._fs = pygame.font.SysFont("monospace", 12)
        self._fm = pygame.font.SysFont("monospace", 14)
        self._fl = pygame.font.SysFont("monospace", 18, bold=True)
        self._fonts_ready = True

    def toggle(self):
        self.visible = not self.visible

    def handle_key(self, key) -> bool:
        if not self.visible:
            return False
        if key in (pygame.K_TAB, pygame.K_ESCAPE):
            self.visible = False
            return True
        if key == pygame.K_UP:
            self.kingdom_scroll = max(0, self.kingdom_scroll - 1)
            return True
        if key == pygame.K_DOWN:
            self.kingdom_scroll += 1
            return True
        if key == pygame.K_PAGEUP:
            self.event_scroll = max(0, self.event_scroll - 5)
            return True
        if key == pygame.K_PAGEDOWN:
            self.event_scroll += 5
            return True
        return False

    def handle_click(self, mx: int, my: int) -> bool:
        if not self.visible:
            return False
        ly = MARGIN + 58
        if MARGIN <= mx <= MARGIN + LEFT_W and ly <= my:
            idx = (my - ly) // 72 + self.kingdom_scroll
            knames = self._kingdoms()
            if 0 <= idx < len(knames):
                k = knames[idx]
                self.selected_kingdom = None if self.selected_kingdom == k else k
            return True
        return True

    # Drawing
    def draw(self, screen: pygame.Surface):
        if not self.visible:
            return
        self._ef()
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill(DASH_BG)
        screen.blit(overlay, (0, 0))
        self._draw_title(screen)
        ty = MARGIN + 34
        by = SCREEN_HEIGHT - 148
        rx = MARGIN + LEFT_W + MARGIN
        rw = SCREEN_WIDTH - rx - MARGIN
        kh = by - ty - MARGIN
        if self.selected_kingdom:
            kh = kh // 2
        self._draw_kingdoms(screen, MARGIN, ty, LEFT_W, kh)
        if self.selected_kingdom:
            self._draw_kingdom_detail(screen, MARGIN, ty + kh + MARGIN, LEFT_W, kh - MARGIN)
        trh = (by - ty - MARGIN) // 2
        self._draw_population(screen, rx, ty, rw, trh)
        self._draw_world(screen, rx, ty + trh + MARGIN, rw, by - ty - trh - 2 * MARGIN)
        self._draw_events(screen, MARGIN, by, SCREEN_WIDTH - 2 * MARGIN, 140)

    def _draw_title(self, s):
        t = self._fl.render("DIVINE DASHBOARD", True, DASH_HEADER)
        s.blit(t, (SCREEN_WIDTH // 2 - t.get_width() // 2, MARGIN + 2))
        h = self._fs.render("[TAB] Close  [Up/Dn] Scroll  [PgUp/Dn] Events", True, DASH_DIM)
        s.blit(h, (SCREEN_WIDTH // 2 - h.get_width() // 2, MARGIN + 20))

    def _draw_kingdoms(self, s, x, y, w, h):
        self._panel(s, x, y, w, h)
        s.blit(self._fm.render("KINGDOMS", True, DASH_HEADER), (x + 8, y + 4))
        knames = self._kingdoms()
        if not knames:
            s.blit(self._fs.render("No kingdoms found", True, DASH_DIM), (x + 8, y + 28))
            return
        gov = self._gov()
        wars = self._wars()
        rh, cy = 72, y + 24
        vis = max(1, (h - 24) // rh)
        for i in range(self.kingdom_scroll, min(len(knames), self.kingdom_scroll + vis)):
            kn = knames[i]
            k = gov.kingdoms.get(kn) if gov else None
            if not k:
                cy += rh
                continue
            gs = getattr(k, 'governing_style', 'feudalism')
            gc = GOV_COLORS.get(gs, (100, 100, 100))
            bg = pygame.Surface((w - 4, rh - 2), pygame.SRCALPHA)
            bg.fill((gc[0] // 4, gc[1] // 4, gc[2] // 4, 180))
            s.blit(bg, (x + 2, cy))
            at_war = any(kn in wr for wr in wars)
            if at_war:
                pygame.draw.rect(s, (220, 60, 60), (x + 2, cy, w - 4, rh - 2), 2)
            if self.selected_kingdom == kn:
                pygame.draw.rect(s, (220, 220, 100), (x + 2, cy, w - 4, rh - 2), 2)
            s.blit(self._fm.render(kn, True, gc), (x + 8, cy + 2))
            rul = getattr(k, 'ruler_name', '?')
            s.blit(self._fs.render(f"Ruler: {rul}  [{gs}]", True, DASH_TEXT), (x + 8, cy + 18))
            tr = getattr(k, 'treasury', 0)
            ar = getattr(k, 'army_size', 0)
            mo = getattr(k, 'public_morale', 50)
            po = getattr(k, 'population', 0)
            inc = getattr(k, 'income_per_day', 0)
            exp = getattr(k, 'expenses_per_day', 0)
            net = inc - exp
            # Treasury bar (proportional, max 1000)
            bar_w = min(w - 80, max(1, int((w - 80) * min(1.0, tr / 1000))))
            pygame.draw.rect(s, (40, 40, 50), (x + 70, cy + 36, w - 80, 8))
            tc = (80, 180, 80) if net >= 0 else (200, 80, 60)
            pygame.draw.rect(s, tc, (x + 70, cy + 36, bar_w, 8))
            s.blit(self._fs.render(f"Gold:{tr:.0f}", True, DASH_TEXT), (x + 8, cy + 34))
            net_c = (100, 220, 100) if net >= 0 else (220, 80, 60)
            net_s = f"+{net:.0f}" if net >= 0 else f"{net:.0f}"
            s.blit(self._ft.render(f"Inc:{inc:.0f} Exp:{exp:.0f} Net:{net_s}/day", True, net_c), (x + 8, cy + 48))
            s.blit(self._ft.render(f"Army:{ar} Pop:{po} Morale:{mo:.0f} Sett:{len(getattr(k, 'settlements', []))}", True, DASH_DIM), (x + 8, cy + 58))
            if at_war:
                s.blit(self._fs.render("AT WAR", True, (255, 80, 80)), (x + w - 70, cy + 4))
            cy += rh

    def _draw_population(self, s, x, y, w, h):
        self._panel(s, x, y, w, h)
        s.blit(self._fm.render("POPULATION", True, DASH_HEADER), (x + 8, y + 4))
        cy = y + 24
        npcs = self._npcs()
        alive = [n for n in npcs if getattr(n, 'alive', True)]
        dead = self._dead_count()
        dorm = sum(1 for n in npcs if getattr(n, 'dormant', False))
        self._t(s, f"Alive: {len(alive)}  Dead: {dead}  Dormant: {dorm}", x + 8, cy, DASH_TEXT)
        cy += 18
        self._t(s, "Job Distribution:", x + 8, cy, DASH_ACCENT)
        cy += 14
        jobs: Dict[str, int] = {}
        for n in alive:
            p = getattr(n, 'profession', 'unknown')
            jobs[p] = jobs.get(p, 0) + 1
        col, cw = 0, w // 2 - 12
        for job, cnt in sorted(jobs.items(), key=lambda x: -x[1])[:16]:
            self._t(s, f"{job}: {cnt}", x + 8 + col * cw, cy, DASH_DIM)
            col += 1
            if col >= 2:
                col, cy = 0, cy + 13
            if cy > y + h - 20:
                break
        sim = getattr(self.game, 'simulation', None)
        evts = getattr(sim, 'events', []) if sim else []
        self._t(s, f"Active Events: {len(evts)}", x + 8, y + h - 18, DASH_ACCENT)

    def _draw_world(self, s, x, y, w, h):
        self._panel(s, x, y, w, h)
        s.blit(self._fm.render("WORLD", True, DASH_HEADER), (x + 8, y + 4))
        cy = y + 24
        ts = getattr(self.game, 'time_sys', None)
        if ts:
            d, sn, yr, sp = getattr(ts, 'day', 0), getattr(ts, 'season', '?'), getattr(ts, 'year', 1), getattr(ts, 'speed', 1.0)
            self._t(s, f"Day {d}  {sn.capitalize()}  Year {yr}  Speed: {sp}x", x + 8, cy, DASH_TEXT)
            cy += 18
        world = getattr(self.game, 'world', None)
        if world:
            cts: Dict[str, int] = {}
            for st in getattr(world, 'structures', []):
                k = getattr(st, 'kind', '?')
                cts[k] = cts.get(k, 0) + 1
            self._t(s, "Settlements: " + ", ".join(f"{k}:{v}" for k, v in sorted(cts.items())), x + 8, cy, DASH_TEXT)
            cy += 16
        wars = self._wars()
        self._t(s, f"Active Wars: {len(wars)}", x + 8, cy, (220, 80, 60) if wars else DASH_DIM)
        cy += 16
        sim = getattr(self.game, 'simulation', None)
        gt = getattr(sim, 'goods_transport', None) if sim else None
        self._t(s, f"Caravans: {len(getattr(gt, 'active_journeys', [])) if gt else 0}", x + 8, cy, DASH_DIM)
        cy += 16
        bs = getattr(self.game, 'building_sys', None)
        self._t(s, f"Construction: {len(getattr(bs, 'active_projects', [])) if bs else 0}", x + 8, cy, DASH_DIM)
        cy += 16
        # Kingdom economic summary
        g = self._gov()
        if g:
            total_gold = sum(getattr(k, 'treasury', 0) for k in g.kingdoms.values())
            total_income = sum(getattr(k, 'income_per_day', 0) for k in g.kingdoms.values())
            total_armies = sum(getattr(k, 'army_size', 0) for k in g.kingdoms.values())
            self._t(s, f"World Gold: {total_gold:.0f}  Income: {total_income:.0f}/day  Armies: {total_armies}", x + 8, cy, DASH_ACCENT)
            cy += 16
        # Stockpile summary from kingdom AI
        sim = getattr(self.game, 'simulation', None)
        kai = getattr(sim, 'kingdom_ai', None) if sim else None
        if kai and hasattr(kai, 'stockpiles'):
            total_food = sum(sp.food for sp in kai.stockpiles.values())
            total_weapons = sum(sp.weapons for sp in kai.stockpiles.values())
            fc = (80, 200, 80) if total_food > 100 else (220, 160, 40) if total_food > 30 else (220, 60, 60)
            wc = (80, 200, 80) if total_weapons > 50 else (220, 160, 40) if total_weapons > 15 else (220, 60, 60)
            self._t(s, f"Food: {total_food:.0f}", x + 8, cy, fc)
            self._t(s, f"Weapons: {total_weapons:.0f}", x + w // 2, cy, wc)

    def _draw_kingdom_detail(self, s, x, y, w, h):
        """Draw detailed info for the selected kingdom."""
        if not self.selected_kingdom:
            return
        g = self._gov()
        if not g:
            return
        k = g.kingdoms.get(self.selected_kingdom)
        if not k:
            return
        self._panel(s, x, y, w, h)
        gs = getattr(k, 'governing_style', '?')
        gc = GOV_COLORS.get(gs, (150, 150, 150))
        s.blit(self._fm.render(f">> {self.selected_kingdom} <<", True, gc), (x + 8, y + 4))
        cy = y + 22
        # Economic breakdown
        inc = getattr(k, 'income_per_day', 0)
        exp = getattr(k, 'expenses_per_day', 0)
        self._t(s, f"Treasury: {getattr(k, 'treasury', 0):.0f}g", x + 8, cy, DASH_TEXT); cy += 14
        self._t(s, f"Daily Income: {inc:.0f}g  (base + tax + trade)", x + 8, cy, (100, 220, 100)); cy += 14
        self._t(s, f"Daily Expenses: {exp:.0f}g  (army + redistribution)", x + 8, cy, (220, 100, 100)); cy += 14
        # Army
        ar = getattr(k, 'army_size', 0)
        up = ar * 0.5
        self._t(s, f"Army: {ar} soldiers  Upkeep: {up:.0f}g/day", x + 8, cy, DASH_TEXT); cy += 14
        # Settlements
        setts = getattr(k, 'settlements', [])
        self._t(s, f"Settlements ({len(setts)}):", x + 8, cy, DASH_ACCENT); cy += 14
        for sn in setts[:6]:
            self._t(s, f"  {sn}", x + 8, cy, DASH_DIM); cy += 12
        if len(setts) > 6:
            self._t(s, f"  ...and {len(setts)-6} more", x + 8, cy, DASH_DIM); cy += 12
        # Stockpiles
        sim = getattr(self.game, 'simulation', None)
        kai = getattr(sim, 'kingdom_ai', None) if sim else None
        if kai and hasattr(kai, 'stockpiles'):
            sp = kai.stockpiles.get(self.selected_kingdom)
            if sp:
                cy += 4
                self._t(s, f"Food: {sp.food:.0f}  Weapons: {sp.weapons:.0f}  Reserve: {sp.gold_reserve:.0f}g", x + 8, cy, DASH_TEXT)

    def _draw_events(self, s, x, y, w, h):
        self._panel(s, x, y, w, h)
        s.blit(self._fm.render("EVENT FEED", True, DASH_HEADER), (x + 8, y + 4))
        log = self._event_log()
        if not log:
            self._t(s, "No events yet...", x + 8, y + 24, DASH_DIM)
            return
        cy, ml = y + 22, (h - 26) // 14
        st = max(0, len(log) - ml - self.event_scroll)
        for i in range(st, min(len(log), st + ml)):
            txt = log[i][:100]
            self._t(s, txt, x + 8, cy, self._evt_color(log[i]))
            cy += 14

    # Data helpers
    def _gov(self):
        sim = getattr(self.game, 'simulation', None)
        return getattr(sim, 'governance', None) if sim else None

    def _kingdoms(self) -> List[str]:
        g = self._gov()
        return sorted(g.kingdoms.keys()) if g else []

    def _npcs(self):
        wm = getattr(self.game, 'world_mgr', None)
        return getattr(wm, 'npcs', []) if wm else []

    def _dead_count(self) -> int:
        sim = getattr(self.game, 'simulation', None)
        return len(getattr(sim, 'dead_npcs', [])) if sim else 0

    def _wars(self) -> List[Tuple[str, str]]:
        g = self._gov()
        if not g:
            return []
        w = []
        for (k1, k2), rel in getattr(g, 'diplomacy', {}).items():
            if getattr(rel, 'status', 0) == 5:
                w.append((k1, k2))
        sim = getattr(self.game, 'simulation', None)
        kai = getattr(sim, 'kingdom_ai', None) if sim else None
        if kai:
            for ws in getattr(kai, 'wars', []):
                p = (getattr(ws, 'attacker', ''), getattr(ws, 'defender', ''))
                if p not in w:
                    w.append(p)
        return w

    def _event_log(self) -> List[str]:
        result = []
        sim = getattr(self.game, 'simulation', None)
        if sim:
            result.extend(getattr(sim, 'event_log', [])[-25:])
            result.extend(getattr(sim, 'event_history', [])[-25:])
        chron = getattr(self.game, 'chronicles', None)
        if chron:
            for e in getattr(chron, 'entries', [])[-25:]:
                t = getattr(e, 'text', str(e))
                if t not in result:
                    result.append(t)
        seen, uniq = set(), []
        for r in result:
            if r not in seen:
                seen.add(r)
                uniq.append(r)
        return uniq[-50:]

    def _evt_color(self, text: str) -> Tuple[int, int, int]:
        tl = text.lower()
        for kw, col in [("war", "war"), ("attack", "war"), ("battle", "war"),
                         ("trade", "trade"), ("merchant", "trade"),
                         ("build", "construction"), ("construct", "construction"),
                         ("drought", "disaster"), ("plague", "disaster"),
                         ("famine", "disaster"), ("earthquake", "disaster"),
                         ("died", "death"), ("killed", "death"),
                         ("festival", "social"), ("peace", "social")]:
            if kw in tl:
                return EVT_COLORS.get(col, DASH_DIM)
        return DASH_DIM

    # Utility
    def _panel(self, s, x, y, w, h):
        p = pygame.Surface((w, h), pygame.SRCALPHA)
        p.fill((15, 15, 30, 220))
        s.blit(p, (x, y))
        pygame.draw.rect(s, DASH_BORDER, (x, y, w, h), 1)

    def _t(self, s, text, x, y, color):
        s.blit(self._fs.render(str(text), True, color), (x, y))
