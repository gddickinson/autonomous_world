"""Elemental effects renderer — fire, ice, acid, and scorch overlays.

Draws visual overlays for active elemental terrain effects including
flickering fire, frozen crystal sheen, acid bubbles, and charred scorch.
Also extends spell visual effects with additional particle types.
"""

import pygame
import random
import math


# Pre-allocated overlay surfaces (created on first use)
_fire_overlay = None
_ice_overlay = None
_acid_overlay = None
_scorch_overlay = None
_surfaces_ready = False


def _init_overlays(tile_size):
    """Create reusable overlay surfaces for each effect type."""
    global _fire_overlay, _ice_overlay, _acid_overlay, _scorch_overlay
    global _surfaces_ready

    ts = tile_size

    _fire_overlay = pygame.Surface((ts, ts), pygame.SRCALPHA)
    _ice_overlay = pygame.Surface((ts, ts), pygame.SRCALPHA)
    _acid_overlay = pygame.Surface((ts, ts), pygame.SRCALPHA)
    _scorch_overlay = pygame.Surface((ts, ts), pygame.SRCALPHA)

    # Fire: warm orange glow
    _fire_overlay.fill((220, 100, 20, 90))

    # Ice: blue-white sheen
    _ice_overlay.fill((160, 200, 240, 70))

    # Acid: green tint
    _acid_overlay.fill((80, 200, 40, 60))

    # Scorch: dark charred
    _scorch_overlay.fill((30, 25, 20, 80))

    _surfaces_ready = True


class ElementalRenderer:
    """Draws elemental terrain effects onto the game screen."""

    def __init__(self):
        self._time = 0.0
        self._fire_particles = []   # small flame particles
        self._acid_bubbles = []     # bubble positions
        self._last_tile_size = 0

    def draw(self, screen, camera, elemental_effects, dt):
        """Main draw entry — only renders effects in viewport.

        Args:
            screen: Pygame display surface.
            camera: Camera for coordinate conversion.
            elemental_effects: ElementalEffects instance.
            dt: Delta time in seconds.
        """
        global _surfaces_ready
        if not _surfaces_ready or self._last_tile_size != camera.tile_size:
            _init_overlays(camera.tile_size)
            self._last_tile_size = camera.tile_size

        self._time += dt
        ts = camera.tile_size

        # Get visible range
        x0, y0, x1, y1 = camera.get_visible_tile_range()
        effects = elemental_effects.get_effects_in_view(x0, y0, x1, y1)

        # Draw in order: scorch (bottom), frozen, acid, fires (top)
        self._draw_scorched(screen, camera, effects["scorched"], ts)
        self._draw_frozen(screen, camera, effects["frozen"], ts)
        self._draw_acid(screen, camera, effects["acid"], ts, dt)
        self._draw_fires(screen, camera, effects["fires"], ts, dt)

    def _draw_fires(self, screen, camera, fires, ts, dt):
        """Draw fire overlays with flickering effect."""
        if not fires:
            return

        for (tx, ty), data in fires.items():
            sx, sy = camera.world_to_screen(tx, ty)
            # Skip if off-screen
            if sx < -ts or sx > screen.get_width() + ts:
                continue
            if sy < -ts or sy > screen.get_height() + ts:
                continue

            intensity = data.get("intensity", 0.5)

            # Flickering alpha
            flicker = math.sin(self._time * 8 + tx * 3.7 + ty * 2.3) * 0.3 + 0.7
            alpha = int(90 * intensity * flicker)

            # Tinted fire overlay
            fire_surf = pygame.Surface((ts, ts), pygame.SRCALPHA)
            r = min(255, int(200 + 55 * flicker))
            g = min(255, int(80 + 60 * (1 - flicker)))
            fire_surf.fill((r, g, 15, alpha))
            screen.blit(fire_surf, (int(sx), int(sy)))

            # Small flame particle at random position
            if random.random() < 0.3 * intensity:
                px = sx + random.uniform(2, ts - 2)
                py = sy + random.uniform(0, ts * 0.6)
                p_size = random.randint(1, 3)
                p_color = random.choice([
                    (255, 200, 50), (255, 140, 30), (255, 80, 10),
                ])
                pygame.draw.circle(screen, p_color,
                                   (int(px), int(py)), p_size)

    def _draw_frozen(self, screen, camera, frozen, ts):
        """Draw blue-white crystal overlay on frozen tiles."""
        if not frozen:
            return

        for (tx, ty), data in frozen.items():
            sx, sy = camera.world_to_screen(tx, ty)
            if sx < -ts or sx > screen.get_width() + ts:
                continue
            if sy < -ts or sy > screen.get_height() + ts:
                continue

            remaining = data.get("remaining", 5.0)
            # Fade out as ice thaws
            fade = min(1.0, remaining / 3.0)
            alpha = int(70 * fade)

            ice_surf = pygame.Surface((ts, ts), pygame.SRCALPHA)
            ice_surf.fill((170, 210, 240, alpha))

            # Crystal sparkle dots
            if random.random() < 0.15:
                cx = random.randint(2, ts - 2)
                cy = random.randint(2, ts - 2)
                pygame.draw.circle(ice_surf, (230, 240, 255, 180),
                                   (cx, cy), 1)

            screen.blit(ice_surf, (int(sx), int(sy)))

    def _draw_acid(self, screen, camera, acid, ts, dt):
        """Draw green bubbling overlay on acid tiles."""
        if not acid:
            return

        for (tx, ty), data in acid.items():
            sx, sy = camera.world_to_screen(tx, ty)
            if sx < -ts or sx > screen.get_width() + ts:
                continue
            if sy < -ts or sy > screen.get_height() + ts:
                continue

            remaining = data.get("remaining", 5.0)
            fade = min(1.0, remaining / 4.0)
            alpha = int(55 * fade)

            acid_surf = pygame.Surface((ts, ts), pygame.SRCALPHA)
            acid_surf.fill((60, 180, 30, alpha))

            # Bubbling effect: random small circles
            if random.random() < 0.2:
                bx = random.randint(2, ts - 2)
                by = random.randint(2, ts - 2)
                br = random.randint(1, 2)
                pygame.draw.circle(acid_surf,
                                   (100, 220, 60, min(255, alpha + 60)),
                                   (bx, by), br)

            screen.blit(acid_surf, (int(sx), int(sy)))

    def _draw_scorched(self, screen, camera, scorched, ts):
        """Draw dark charred overlay on permanently scorched tiles."""
        if not scorched:
            return

        for (tx, ty) in scorched:
            sx, sy = camera.world_to_screen(tx, ty)
            if sx < -ts or sx > screen.get_width() + ts:
                continue
            if sy < -ts or sy > screen.get_height() + ts:
                continue

            screen.blit(_scorch_overlay, (int(sx), int(sy)))


# ----------------------------------------------------------
# Extended spell visual particles
# ----------------------------------------------------------

# Additional particle colors by spell school / element
SPELL_PARTICLE_COLORS = {
    "acid": [(80, 200, 40), (60, 180, 30), (100, 220, 60)],
    "nature": [(60, 180, 50), (80, 200, 70), (40, 160, 40)],
    "necromancy": [(80, 40, 120), (100, 50, 140), (60, 30, 100)],
    "enchantment": [(200, 100, 200), (180, 80, 180), (220, 120, 220)],
    "transmutation": [(220, 190, 60), (200, 170, 50), (240, 210, 80)],
}


def get_spell_particle_colors(spell_name):
    """Return particle colors for a spell based on its school/element.

    Returns a list of RGB tuples, or None if no special colors.
    """
    name = spell_name.lower()

    if "acid" in name or "poison" in name:
        return SPELL_PARTICLE_COLORS["acid"]
    if any(w in name for w in ("entangle", "vine", "bark", "nature",
                                "thorn", "plant", "druid")):
        return SPELL_PARTICLE_COLORS["nature"]
    if any(w in name for w in ("necrotic", "undead", "death", "wither",
                                "shadow", "drain", "animate")):
        return SPELL_PARTICLE_COLORS["necromancy"]
    if any(w in name for w in ("charm", "sleep", "enchant", "hold",
                                "dominate", "suggestion")):
        return SPELL_PARTICLE_COLORS["enchantment"]
    if any(w in name for w in ("polymorph", "transmut", "alter",
                                "enlarge", "reduce", "haste", "slow")):
        return SPELL_PARTICLE_COLORS["transmutation"]

    return None
