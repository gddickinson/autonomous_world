"""Divine Intervention Commands -- god mode powers for world manipulation.

Provides smite, bless, event triggering, kingdom commands, time control,
and entity spawning. Activated via key bindings in god mode.

Event logic and kingdom helpers live in divine_events.py.
"""

import math
import pygame
from typing import Optional, List, Tuple

from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE, YELLOW
from game.systems.divine_events import (
    notify, chronicle, get_governance, get_npcs, get_selected_settlement,
    trigger_drought, trigger_plague, trigger_festival, trigger_monster_wave,
    trigger_gold_rain, trigger_famine, trigger_inspiration, trigger_earthquake,
    kingdom_declare_war, kingdom_peace, kingdom_recruit, kingdom_fortify,
    kingdom_boost_economy, kingdom_change_gov, spawn_creature, spawn_npc,
)

TIME_SPEEDS = [0.25, 0.5, 1.0, 2.0, 5.0, 10.0]


class DivineEffect:
    """A temporary visual effect at a world position."""
    def __init__(self, x: float, y: float, text: str,
                 color: Tuple[int, ...], duration: float = 2.0,
                 flash: bool = False):
        self.x, self.y = x, y
        self.text, self.color = text, color
        self.duration = duration
        self.remaining = duration
        self.flash = flash


class DivineCommands:
    """All divine intervention powers for god mode."""

    def __init__(self):
        self.effects: List[DivineEffect] = []
        self.active_menu: Optional[str] = None
        self.target_kingdom: Optional[str] = None
        self.speed_index = 2  # 1.0x
        self.paused = False
        self._fonts_ready = False
        self._last_game = None

    def _ef(self):
        if self._fonts_ready:
            return
        self._fs = pygame.font.SysFont("monospace", 12)
        self._fm = pygame.font.SysFont("monospace", 14)
        self._fl = pygame.font.SysFont("monospace", 20, bold=True)
        self._fonts_ready = True

    # ================================================================
    # KEY HANDLING
    # ================================================================

    def handle_key(self, key, mods, game) -> bool:
        self._last_game = game
        if self.active_menu:
            return self._menu_key(key, game)
        if key == pygame.K_g:
            sett = get_selected_settlement(game)
            self._target_sett = sett
            self.active_menu = "event"
            return True
        if key == pygame.K_k:
            db = getattr(game, 'god_dashboard', None)
            kn = getattr(db, 'selected_kingdom', None) if db else None
            if not kn:
                notify(game, "Select a kingdom first (TAB).", (200, 200, 100))
                return True
            self.target_kingdom = kn
            self.active_menu = "kingdom"
            return True
        if key == pygame.K_n:
            self.active_menu = "spawn"
            return True
        if key == pygame.K_LEFTBRACKET:
            self._change_speed(-1, game)
            return True
        if key == pygame.K_RIGHTBRACKET:
            self._change_speed(1, game)
            return True
        if key == pygame.K_p:
            self.paused = not self.paused
            self._apply_speed(game)
            notify(game, f"Time {'PAUSED' if self.paused else 'RESUMED'}", YELLOW)
            return True
        if key == pygame.K_PERIOD and self.paused:
            ts = getattr(game, 'time_sys', None)
            if ts:
                ts.speed = 1.0
            return True
        return False

    def _menu_key(self, key, game) -> bool:
        if key == pygame.K_ESCAPE:
            self.active_menu = None
            return True
        m = self.active_menu
        if m == "event":
            return self._event_key(key, game)
        if m == "kingdom":
            return self._kingdom_key(key, game)
        if m == "spawn":
            return self._spawn_key(key, game)
        if m == "war_target":
            return self._war_target_key(key, game)
        if m == "gov_pick":
            return self._gov_pick_key(key, game)
        return True

    def _event_key(self, key, game) -> bool:
        sett = getattr(self, '_target_sett', None)
        emap = {
            pygame.K_1: lambda: trigger_drought(sett, game),
            pygame.K_2: lambda: trigger_plague(sett, game),
            pygame.K_3: lambda: trigger_festival(sett, game),
            pygame.K_4: lambda: trigger_monster_wave(sett, game),
            pygame.K_5: lambda: trigger_gold_rain(sett, game),
            pygame.K_6: lambda: trigger_famine(sett, game),
            pygame.K_7: lambda: trigger_inspiration(sett, game, self.effects),
            pygame.K_8: lambda: trigger_earthquake(sett, game, self.effects),
        }
        fn = emap.get(key)
        if fn:
            fn()
            self.active_menu = None
            return True
        return True

    def _kingdom_key(self, key, game) -> bool:
        kn = self.target_kingdom
        kmap = {
            pygame.K_1: lambda: setattr(self, 'active_menu', 'war_target'),
            pygame.K_2: lambda: (kingdom_peace(kn, game),
                                 setattr(self, 'active_menu', None)),
            pygame.K_3: lambda: (kingdom_recruit(kn, game),
                                 setattr(self, 'active_menu', None)),
            pygame.K_4: lambda: (kingdom_fortify(kn, game),
                                 setattr(self, 'active_menu', None)),
            pygame.K_5: lambda: (kingdom_boost_economy(kn, game),
                                 setattr(self, 'active_menu', None)),
            pygame.K_6: lambda: setattr(self, 'active_menu', 'gov_pick'),
        }
        fn = kmap.get(key)
        if fn:
            fn()
            return True
        return True

    def _war_target_key(self, key, game) -> bool:
        gov = get_governance(game)
        if not gov:
            self.active_menu = None
            return True
        others = [k for k in sorted(gov.kingdoms.keys())
                  if k != self.target_kingdom]
        idx = key - pygame.K_1
        if 0 <= idx < len(others):
            kingdom_declare_war(self.target_kingdom, others[idx], game)
            self.active_menu = None
            return True
        if key == pygame.K_ESCAPE:
            self.active_menu = "kingdom"
        return True

    def _gov_pick_key(self, key, game) -> bool:
        styles = ["feudalism", "tribal", "theocracy", "republic",
                  "autocracy", "merchant_republic"]
        idx = key - pygame.K_1
        if 0 <= idx < len(styles):
            kingdom_change_gov(self.target_kingdom, styles[idx], game)
            self.active_menu = None
            return True
        if key == pygame.K_ESCAPE:
            self.active_menu = "kingdom"
        return True

    def _spawn_key(self, key, game) -> bool:
        if key == pygame.K_1:
            spawn_creature(game)
        elif key == pygame.K_2:
            spawn_npc(game)
        elif key == pygame.K_3:
            notify(game, "Use terrain painter (F11) for buildings.", (200, 200, 100))
        elif key == pygame.K_4:
            notify(game, "Use god console (~) for settlements.", (200, 200, 100))
        self.active_menu = None
        return True

    # ================================================================
    # CLICK HANDLING (smite / bless)
    # ================================================================

    def handle_click(self, mx, my, button, mods, camera, game) -> bool:
        ctrl = mods & pygame.KMOD_CTRL
        shift = mods & pygame.KMOD_SHIFT
        if not ctrl and not shift:
            return False
        wx, wy = camera.screen_to_world(float(mx), float(my))
        entity = self._find_near(wx, wy, game)
        if ctrl and entity:
            self._smite(entity, game)
            return True
        if shift and entity:
            self._bless(entity, game)
            return True
        if ctrl:
            self.effects.append(DivineEffect(wx, wy, "DIVINE WRATH",
                                             (255, 255, 200), 1.5, True))
            notify(game, "Lightning strikes empty ground!", (200, 200, 255))
            return True
        return False

    def _smite(self, entity, game):
        self.effects.append(DivineEffect(entity.x, entity.y, "DIVINE WRATH",
                                         (255, 255, 200), 2.5, True))
        if hasattr(entity, 'hp'):
            entity.hp = 0
        if hasattr(entity, 'alive'):
            entity.alive = False
        name = getattr(entity, 'name', 'creature')
        notify(game, f"Divine wrath smites {name}!", (255, 80, 80))
        chronicle(game, f"The gods struck down {name} with lightning.", "miracle")
        # Nearby NPCs flee
        wm = getattr(game, 'world_mgr', None)
        if wm:
            for npc in getattr(wm, 'npcs', []):
                if not getattr(npc, 'alive', False):
                    continue
                dx, dy = npc.x - entity.x, npc.y - entity.y
                if dx * dx + dy * dy < 100:
                    npc.current_action = "fleeing"
                    npc.action_timer = 5.0
                    dist = max(0.1, math.sqrt(dx * dx + dy * dy))
                    npc.target_x = npc.x + (dx / dist) * 15
                    npc.target_y = npc.y + (dy / dist) * 15

    def _bless(self, entity, game):
        self.effects.append(DivineEffect(entity.x, entity.y, "BLESSED",
                                         (255, 220, 80), 2.5))
        name = getattr(entity, 'name', 'creature')
        if hasattr(entity, 'max_hp'):
            entity.hp = entity.max_hp
        if hasattr(entity, 'ability_scores'):
            for s in entity.ability_scores:
                entity.ability_scores[s] = entity.ability_scores.get(s, 10) + 5
        if hasattr(entity, 'level'):
            entity.level = getattr(entity, 'level', 1) + 1
            if hasattr(entity, 'max_hp'):
                entity.max_hp += 10
                entity.hp = entity.max_hp
        if hasattr(entity, 'gold'):
            entity.gold = getattr(entity, 'gold', 0) + 100
        if hasattr(entity, 'morale'):
            entity.morale = min(100, getattr(entity, 'morale', 50) + 30)
        notify(game, f"Divine blessing upon {name}!", (255, 220, 80))
        chronicle(game, f"The gods blessed {name} with divine favor.", "miracle")

    # ================================================================
    # TIME CONTROL
    # ================================================================

    def _change_speed(self, delta, game):
        self.speed_index = max(0, min(len(TIME_SPEEDS) - 1,
                                      self.speed_index + delta))
        self.paused = False
        self._apply_speed(game)
        notify(game, f"Time speed: {TIME_SPEEDS[self.speed_index]}x", YELLOW)

    def _apply_speed(self, game):
        ts = getattr(game, 'time_sys', None)
        if ts:
            ts.speed = 0.0 if self.paused else TIME_SPEEDS[self.speed_index]

    # ================================================================
    # UPDATE
    # ================================================================

    def update(self, dt):
        for e in self.effects:
            e.remaining -= dt
        self.effects = [e for e in self.effects if e.remaining > 0]

    # ================================================================
    # DRAWING
    # ================================================================

    def draw_effects(self, screen, camera):
        self._ef()
        for e in self.effects:
            sx = e.x * TILE_SIZE - camera.x
            sy = e.y * TILE_SIZE - camera.y
            if not (-50 < sx < SCREEN_WIDTH + 50
                    and -50 < sy < SCREEN_HEIGHT + 50):
                continue
            if e.flash and e.remaining > e.duration - 0.1:
                fl = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
                fl.fill((255, 255, 220, 120))
                screen.blit(fl, (0, 0))
                pygame.draw.line(screen, (255, 255, 200),
                                 (int(sx), 0), (int(sx), int(sy)), 3)
            alpha = min(1.0, e.remaining / 0.5)
            fy = sy - (e.duration - e.remaining) * 15
            txt = self._fl.render(e.text, True, e.color)
            txt.set_alpha(int(alpha * 255))
            screen.blit(txt, (int(sx) - txt.get_width() // 2, int(fy)))
            r = int(20 * alpha)
            if r > 0:
                glow = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
                pygame.draw.circle(glow, (*e.color[:3], int(40 * alpha)),
                                   (r * 2, r * 2), r)
                screen.blit(glow, (int(sx) - r * 2, int(fy) - r * 2))

    def draw_menu(self, screen):
        if not self.active_menu:
            return
        self._ef()
        m = self.active_menu
        if m == "event":
            self._box(screen, "TRIGGER EVENT", [
                "1: Drought", "2: Plague", "3: Festival",
                "4: Monster Wave", "5: Gold Rain (kingdom)",
                "6: Famine", "7: Divine Inspiration", "8: Earthquake",
                "", "ESC: Cancel"])
        elif m == "kingdom":
            self._box(screen, f"COMMAND: {self.target_kingdom}", [
                "1: Declare War", "2: Make Peace", "3: Recruit Soldiers",
                "4: Build Fortifications", "5: Boost Economy",
                "6: Change Governance", "", "ESC: Cancel"])
        elif m == "spawn":
            self._box(screen, "SPAWN", [
                "1: Creature", "2: NPC", "3: Building (god panel)",
                "4: Settlement (console)", "", "ESC: Cancel"])
        elif m == "war_target":
            gov = get_governance(self._last_game)
            others = [k for k in sorted(gov.kingdoms.keys())
                      if k != self.target_kingdom] if gov else []
            lines = [f"{i+1}: {k}" for i, k in enumerate(others[:9])]
            lines += ["", "ESC: Back"]
            self._box(screen, "DECLARE WAR ON...", lines)
        elif m == "gov_pick":
            styles = ["feudalism", "tribal", "theocracy", "republic",
                      "autocracy", "merchant_republic"]
            lines = [f"{i+1}: {s}" for i, s in enumerate(styles)]
            lines += ["", "ESC: Back"]
            self._box(screen, "CHANGE GOVERNANCE", lines)

    def _box(self, screen, title, lines):
        w, h = 380, 28 + len(lines) * 20
        x, y = SCREEN_WIDTH // 2 - w // 2, SCREEN_HEIGHT // 2 - h // 2
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        bg.fill((15, 15, 30, 240))
        screen.blit(bg, (x, y))
        pygame.draw.rect(screen, (220, 200, 100), (x, y, w, h), 2)
        screen.blit(self._fm.render(title, True, (220, 200, 100)), (x + 10, y + 5))
        cy = y + 26
        for ln in lines:
            if ln:
                screen.blit(self._fs.render(ln, True, (200, 200, 210)), (x + 16, cy))
            cy += 20

    def draw_hud(self, screen):
        self._ef()
        sp = TIME_SPEEDS[self.speed_index]
        st = "PAUSED" if self.paused else f"{sp}x"
        col = (255, 80, 80) if self.paused else (220, 200, 100)
        t = self._fm.render(f"Time: {st}  [/] Speed  [P] Pause", True, col)
        screen.blit(t, (SCREEN_WIDTH // 2 - t.get_width() // 2, 4))
        h = self._fs.render(
            "[TAB] Dashboard  [Ctrl+Click] Smite  [Shift+Click] Bless"
            "  [G] Events  [K] Kingdom  [N] Spawn", True, (140, 140, 160))
        screen.blit(h, (SCREEN_WIDTH // 2 - h.get_width() // 2, 22))

    # ================================================================
    # HELPERS
    # ================================================================

    def _find_near(self, wx, wy, game):
        wm = getattr(game, 'world_mgr', None)
        if not wm:
            return None
        best, bd = None, 4.0
        for npc in getattr(wm, 'npcs', []):
            if not getattr(npc, 'alive', False):
                continue
            d = math.hypot(npc.x - wx, npc.y - wy)
            if d < bd:
                best, bd = npc, d
        for cr in getattr(wm, 'creatures', []):
            if not getattr(cr, 'alive', False):
                continue
            d = math.hypot(cr.x - wx, cr.y - wy)
            if d < bd:
                best, bd = cr, d
        return best
