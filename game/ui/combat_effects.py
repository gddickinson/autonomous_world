"""Combat visual effects: damage popups, HP bars, hit flashes, death effects.

Provides a CombatEffects helper class that both Renderer and AdventureRenderer
use. Each renderer holds a CombatEffects instance and delegates to it for
combat-related drawing.
"""

import math
import random
import pygame
from typing import List, Dict, Optional, Tuple
from game.settings import SCREEN_WIDTH, SCREEN_HEIGHT, TILE_SIZE


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

class DamagePopup:
    """Floating damage number that rises and fades out."""
    __slots__ = ('x', 'y', 'value', 'color', 'age', 'max_age', 'vy')

    def __init__(self, x: float, y: float, value: int,
                 color: Tuple[int, int, int] = (255, 60, 60)):
        self.x = x
        self.y = y
        self.value = value
        self.color = color
        self.age = 0.0
        self.max_age = 1.0  # seconds
        self.vy = -2.8  # tiles per second upward


class HitFlash:
    """Brief colored overlay on a hit target (2-3 frames)."""
    __slots__ = ('entity_id', 'x', 'y', 'age', 'max_age', 'color')

    def __init__(self, entity_id: int, x: float, y: float,
                 color: Tuple[int, int, int] = (255, 255, 255)):
        self.entity_id = entity_id
        self.x = x
        self.y = y
        self.age = 0.0
        self.max_age = 0.12  # ~3 frames at 30fps
        self.color = color


class DeathEffect:
    """Red flash + particle burst at death location."""
    __slots__ = ('x', 'y', 'age', 'max_age', 'particles', 'flash_age')

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.age = 0.0
        self.max_age = 0.8  # total duration
        self.flash_age = 0.15  # red flash duration
        # Scatter particles: small red/grey dots
        self.particles: List[dict] = []
        for _ in range(5):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(1.5, 4.0)
            gray = random.randint(80, 180)
            is_red = random.random() < 0.6
            color = (random.randint(160, 220), 30, 30) if is_red else (gray, gray, gray)
            self.particles.append({
                "x": 0.0, "y": 0.0,
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed - 1.5,
                "color": color,
                "size": random.randint(2, 4),
            })


# ---------------------------------------------------------------------------
# CombatEffects — the main manager drawn by each renderer
# ---------------------------------------------------------------------------

class CombatEffects:
    """Manages all combat visual effects. One instance per renderer."""

    def __init__(self):
        self.damage_popups: List[DamagePopup] = []
        self.hit_flashes: List[HitFlash] = []
        self.death_effects: List[DeathEffect] = []
        # HP bar targets: entity id -> (timer_remaining, entity_ref)
        self.hp_bar_targets: Dict[int, Tuple[float, object]] = {}
        # Font (lazy init)
        self._font_sm: Optional[pygame.font.Font] = None
        self._font_md: Optional[pygame.font.Font] = None
        self._font_dmg: Optional[pygame.font.Font] = None

    def _ensure_fonts(self):
        if self._font_sm is None:
            self._font_sm = pygame.font.SysFont("monospace", 12)
            self._font_md = pygame.font.SysFont("monospace", 16)
            self._font_dmg = pygame.font.SysFont("monospace", 18, bold=True)

    # ------------------------------------------------------------------
    # Spawning methods (called from game logic)
    # ------------------------------------------------------------------

    def spawn_damage_popup(self, x: float, y: float, value: int,
                           color: Tuple[int, int, int] = (255, 60, 60)):
        """Create a floating damage number. Red for damage, green for heals."""
        # Jitter position slightly so overlapping hits don't stack
        jx = x + random.uniform(-0.2, 0.2)
        jy = y + random.uniform(-0.15, 0.05)
        self.damage_popups.append(DamagePopup(jx, jy, value, color))

    def spawn_hit_flash(self, entity, color: Tuple[int, int, int] = (255, 255, 255)):
        """Flash the target entity white/red briefly."""
        eid = id(entity)
        # Don't stack flashes on the same entity
        for f in self.hit_flashes:
            if f.entity_id == eid:
                f.age = 0.0
                f.color = color
                return
        self.hit_flashes.append(
            HitFlash(eid, entity.x, entity.y, color))

    def spawn_death_effect(self, x: float, y: float):
        """Red flash + particle scatter at death position."""
        self.death_effects.append(DeathEffect(x, y))

    def mark_hp_bar(self, entity):
        """Mark an entity to show HP bar for a few seconds."""
        self.hp_bar_targets[id(entity)] = (3.0, entity)

    # ------------------------------------------------------------------
    # Full combat event: damage dealt to a target
    # ------------------------------------------------------------------

    def on_damage_dealt(self, target, damage: int, is_kill: bool = False):
        """Called when any damage is dealt to a target entity.

        Spawns damage popup, hit flash, HP bar, and death effect if killed.
        """
        if damage <= 0:
            return
        tx = getattr(target, 'x', 0)
        ty = getattr(target, 'y', 0)

        # Damage popup (red)
        self.spawn_damage_popup(tx, ty, damage, (255, 60, 60))

        # Hit flash (white fading to red)
        self.spawn_hit_flash(target, (255, 200, 200))

        # Mark for HP bar display
        self.mark_hp_bar(target)

        # Death effect
        if is_kill:
            self.spawn_death_effect(tx, ty)

    def on_heal(self, target, amount: int):
        """Called when healing occurs — green popup."""
        tx = getattr(target, 'x', 0)
        ty = getattr(target, 'y', 0)
        self.spawn_damage_popup(tx, ty, amount, (60, 220, 60))

    # ------------------------------------------------------------------
    # Update + draw (called once per frame by the renderer)
    # ------------------------------------------------------------------

    def update_and_draw(self, screen: pygame.Surface, camera, dt: float):
        """Update all combat effects and draw them."""
        self._ensure_fonts()
        self._draw_damage_popups(screen, camera, dt)
        self._draw_hit_flashes(screen, camera, dt)
        self._draw_death_effects(screen, camera, dt)

    def draw_hp_bars(self, screen: pygame.Surface, camera, dt: float,
                     entities=None):
        """Draw HP bars above damaged entities.

        Args:
            entities: Optional iterable of entities. If None, uses stored refs.
        """
        self._ensure_fonts()
        self._draw_enemy_hp_bars(screen, camera, dt)

    # ------------------------------------------------------------------
    # Internal drawing
    # ------------------------------------------------------------------

    def _draw_damage_popups(self, screen: pygame.Surface, camera, dt: float):
        alive = []
        for p in self.damage_popups:
            p.age += dt
            if p.age >= p.max_age:
                continue

            # Float upward, decelerating
            p.y += p.vy * dt
            p.vy *= 0.95

            sx, sy = camera.world_to_screen(p.x, p.y)
            if not (-50 < sx < SCREEN_WIDTH + 50 and
                    -50 < sy < SCREEN_HEIGHT + 50):
                alive.append(p)
                continue

            # Fade out
            progress = p.age / p.max_age
            alpha = int(255 * (1.0 - progress))

            # Scale text: big hits get bigger font
            font = self._font_dmg if p.value >= 15 else self._font_sm
            txt = str(p.value)

            text_surf = font.render(txt, True, p.color)
            alpha_surf = pygame.Surface(text_surf.get_size(), pygame.SRCALPHA)
            alpha_surf.blit(text_surf, (0, 0))
            alpha_surf.set_alpha(alpha)

            # Drop shadow for readability
            shadow_surf = font.render(txt, True, (0, 0, 0))
            shadow_alpha = pygame.Surface(shadow_surf.get_size(), pygame.SRCALPHA)
            shadow_alpha.blit(shadow_surf, (0, 0))
            shadow_alpha.set_alpha(max(0, alpha - 60))
            screen.blit(shadow_alpha,
                        (int(sx) - text_surf.get_width() // 2 + 1,
                         int(sy) - text_surf.get_height() // 2 + 1))

            screen.blit(alpha_surf,
                        (int(sx) - text_surf.get_width() // 2,
                         int(sy) - text_surf.get_height() // 2))
            alive.append(p)

        self.damage_popups = alive

    def _draw_hit_flashes(self, screen: pygame.Surface, camera, dt: float):
        alive = []
        for f in self.hit_flashes:
            f.age += dt
            if f.age >= f.max_age:
                continue

            sx, sy = camera.world_to_screen(f.x, f.y)
            if not (-30 < sx < SCREEN_WIDTH + 30 and
                    -30 < sy < SCREEN_HEIGHT + 30):
                alive.append(f)
                continue

            # Flash overlay: starts bright, fades quickly
            progress = f.age / f.max_age
            alpha = int(180 * (1.0 - progress))

            # Draw a colored rectangle overlay at entity position
            tile = TILE_SIZE
            flash_w = tile
            flash_h = int(tile * 1.4)
            flash_surf = pygame.Surface((flash_w, flash_h), pygame.SRCALPHA)

            # Color shifts from white toward red as it fades
            r = f.color[0]
            g = max(0, int(f.color[1] * (1.0 - progress * 0.8)))
            b = max(0, int(f.color[2] * (1.0 - progress * 0.8)))
            flash_surf.fill((r, g, b, alpha))

            screen.blit(flash_surf,
                        (int(sx) - flash_w // 2,
                         int(sy) - flash_h // 2))
            alive.append(f)

        self.hit_flashes = alive

    def _draw_death_effects(self, screen: pygame.Surface, camera, dt: float):
        alive = []
        for d in self.death_effects:
            d.age += dt
            if d.age >= d.max_age:
                continue

            sx, sy = camera.world_to_screen(d.x, d.y)
            if not (-50 < sx < SCREEN_WIDTH + 50 and
                    -50 < sy < SCREEN_HEIGHT + 50):
                alive.append(d)
                continue

            # Phase 1: Red flash (first 0.15s)
            if d.age < d.flash_age:
                flash_progress = d.age / d.flash_age
                flash_alpha = int(200 * (1.0 - flash_progress))
                tile = TILE_SIZE
                flash_surf = pygame.Surface((tile * 2, tile * 2), pygame.SRCALPHA)
                flash_surf.fill((220, 30, 30, flash_alpha))
                screen.blit(flash_surf,
                            (int(sx) - tile, int(sy) - tile))

            # Phase 2: Particle scatter (entire duration)
            particle_progress = d.age / d.max_age
            for p in d.particles:
                px = sx + p["vx"] * d.age * TILE_SIZE * 0.4
                py = sy + p["vy"] * d.age * TILE_SIZE * 0.4

                alpha = int(255 * (1.0 - particle_progress))
                size = max(1, int(p["size"] * (1.0 - particle_progress * 0.5)))

                c = p["color"]
                dot_surf = pygame.Surface((size * 2, size * 2), pygame.SRCALPHA)
                pygame.draw.circle(dot_surf, (c[0], c[1], c[2], alpha),
                                   (size, size), size)
                screen.blit(dot_surf, (int(px) - size, int(py) - size))

            alive.append(d)

        self.death_effects = alive

    def _draw_enemy_hp_bars(self, screen: pygame.Surface, camera, dt: float):
        """Draw HP bars above entities that have been damaged recently."""
        expired = []
        for eid, (timer, entity) in self.hp_bar_targets.items():
            new_timer = timer - dt
            if new_timer <= 0:
                expired.append(eid)
                continue
            self.hp_bar_targets[eid] = (new_timer, entity)

            if not getattr(entity, 'alive', True):
                expired.append(eid)
                continue

            hp = getattr(entity, 'hp', 0)
            max_hp = getattr(entity, 'max_hp', 1)
            if max_hp <= 0:
                continue

            sx, sy = camera.world_to_screen(entity.x, entity.y)
            if not (-20 < sx < SCREEN_WIDTH + 20 and
                    -20 < sy < SCREEN_HEIGHT + 20):
                continue

            # Bar dimensions
            bar_w = 28
            bar_h = 4
            bar_x = int(sx) - bar_w // 2
            bar_y = int(sy) - 20  # above entity

            # Background
            pygame.draw.rect(screen, (20, 20, 20),
                             (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2))

            # HP fill: green -> yellow -> red
            ratio = max(0.0, min(1.0, hp / max_hp))
            if ratio > 0.6:
                bar_color = (70, 200, 70)
            elif ratio > 0.3:
                bar_color = (220, 200, 50)
            else:
                bar_color = (220, 50, 50)

            fill_w = max(1, int(bar_w * ratio))
            pygame.draw.rect(screen, bar_color,
                             (bar_x, bar_y, fill_w, bar_h))
            # Border
            pygame.draw.rect(screen, (100, 100, 100),
                             (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2), 1)

            # HP text for recently targeted entities
            if new_timer > 2.0:
                hp_txt = f"{int(hp)}/{int(max_hp)}"
                txt_surf = self._font_sm.render(hp_txt, True, (220, 220, 220))
                screen.blit(txt_surf,
                            (int(sx) - txt_surf.get_width() // 2,
                             bar_y - 13))

        for eid in expired:
            self.hp_bar_targets.pop(eid, None)
