"""Water rendering utilities — shore gradients, deep water, wave animation.

Provides helper functions for both 16px (strategy) and 32px (adventure)
renderers to determine water depth variants and build animated water tiles.

Enhanced features:
- Shore foam/spray effect on tiles adjacent to land
- Directional flow indicators for river-adjacent water
- Ripple effects when entities walk through shallow water
"""

import math
import time
import pygame
from game.settings import WATER, SHALLOW_WATER

# Water color variants
WATER_SHALLOW = (70, 140, 200)   # lighter, adjacent to land
WATER_NORMAL = (41, 128, 185)    # default color
WATER_DEEP = (25, 60, 130)       # all 4 neighbors are water

# Shore foam colors
FOAM_WHITE = (220, 230, 240)
FOAM_LIGHT = (180, 210, 230)

# Land terrain types (anything that isn't water)
_WATER_TYPES = {WATER, SHALLOW_WATER}


def classify_water_tile(world_tiles, x: int, y: int,
                        width: int, height: int) -> str:
    """Classify a WATER tile as 'shallow', 'normal', or 'deep'.

    - shallow: at least one cardinal neighbor is a non-water land tile
    - deep: all 4 cardinal neighbors are also water
    - normal: in between (has water neighbors but not all 4)
    """
    neighbors_water = 0
    has_land_neighbor = False
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
            tile = world_tiles[ny][nx]
            if tile in _WATER_TYPES:
                neighbors_water += 1
            else:
                has_land_neighbor = True
        else:
            # Out of bounds counts as land (shore at map edge)
            has_land_neighbor = True

    if has_land_neighbor:
        return "shallow"
    if neighbors_water >= 4:
        return "deep"
    return "normal"


def get_land_neighbor_mask(world_tiles, x: int, y: int,
                           width: int, height: int) -> int:
    """Return a bitmask of which cardinal directions have land neighbors.

    Bit 0 = north, 1 = south, 2 = west, 3 = east.
    Used for shore foam placement.
    """
    mask = 0
    for i, (dx, dy) in enumerate(((0, -1), (0, 1), (-1, 0), (1, 0))):
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
            if world_tiles[ny][nx] not in _WATER_TYPES:
                mask |= (1 << i)
        else:
            mask |= (1 << i)
    return mask


def is_deep_water(world_tiles, x: int, y: int,
                  width: int, height: int) -> bool:
    """Return True if this water tile is deep (all 4 neighbors are water).

    Used by movement system to block walking into deep ocean.
    """
    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < width and 0 <= ny < height:
            tile = world_tiles[ny][nx]
            if tile not in _WATER_TYPES:
                return False
        else:
            return False
    return True


def build_water_tile_variants(tile_size: int):
    """Build 3 base water tile surfaces (shallow, normal, deep).

    Returns dict: {'shallow': Surface, 'normal': Surface, 'deep': Surface}
    """
    variants = {}
    for label, base_color in [("shallow", WATER_SHALLOW),
                               ("normal", WATER_NORMAL),
                               ("deep", WATER_DEEP)]:
        surf = pygame.Surface((tile_size, tile_size))
        r, g, b = base_color
        surf.fill(base_color)

        if label == "shallow":
            # Lighter ripples for shallow water near shore
            for i in range(3):
                y_pos = 3 + i * (tile_size // 4)
                ripple = (min(255, r + 30), min(255, g + 25), min(255, b + 20))
                for px in range(tile_size):
                    offset = (px * 2 + i * 5) % 6
                    if offset < 3:
                        if y_pos < tile_size:
                            surf.set_at((px, y_pos), ripple)
            # Sand-colored bottom visible through shallow water
            for i in range(4):
                sx = (hash(i * 11 + 5) % (tile_size - 2)) + 1
                sy = (hash(i * 19 + 3) % (tile_size - 2)) + 1
                surf.set_at((sx, sy), (min(255, r + 40),
                                       min(255, g + 35),
                                       min(255, b + 25)))
        elif label == "normal":
            # Standard wave crests
            for i in range(3):
                y_pos = (tile_size // 5) + i * (tile_size // 4)
                wave_color = (min(255, r + 25), min(255, g + 25),
                              min(255, b + 25))
                for px in range(tile_size):
                    offset = (px * 3 + i * 7) % 4
                    if offset < 2 and y_pos < tile_size:
                        surf.set_at((px, y_pos), wave_color)
            # Sparkle highlights
            for i in range(2):
                fx = (hash(i * 19 + 3) % (tile_size - 2)) + 1
                fy = (hash(i * 23 + 7) % (tile_size - 2)) + 1
                surf.set_at((fx, fy), (min(255, r + 45),
                                       min(255, g + 45),
                                       min(255, b + 40)))
        else:
            # Deep water — darker with subtle depth variation
            for row in range(0, tile_size, 3):
                for col in range(tile_size):
                    phase = col * 0.25 + row * 0.6
                    brightness = int(6 * math.sin(phase))
                    c = (max(0, min(255, r + brightness)),
                         max(0, min(255, g + brightness)),
                         max(0, min(255, b + brightness + 3)))
                    if row < tile_size:
                        surf.set_at((col, row), c)

        variants[label] = surf
    return variants


def build_wave_frames(base_variants: dict, tile_size: int,
                      num_frames: int = 3):
    """Build animated wave frame variants for each water depth.

    Returns dict: {('shallow', frame_idx): Surface, ...}
    Each frame has slightly shifted wave highlights.
    """
    frames = {}
    for label, base_surf in base_variants.items():
        for frame in range(num_frames):
            surf = base_surf.copy()
            # Add frame-dependent wave shimmer
            for i in range(2):
                y_pos = (3 + i * (tile_size // 3) + frame * 2) % tile_size
                if label == "shallow":
                    shimmer = (min(255, WATER_SHALLOW[0] + 35),
                               min(255, WATER_SHALLOW[1] + 30),
                               min(255, WATER_SHALLOW[2] + 20))
                elif label == "deep":
                    shimmer = (min(255, WATER_DEEP[0] + 18),
                               min(255, WATER_DEEP[1] + 15),
                               min(255, WATER_DEEP[2] + 12))
                else:
                    shimmer = (min(255, WATER_NORMAL[0] + 30),
                               min(255, WATER_NORMAL[1] + 28),
                               min(255, WATER_NORMAL[2] + 22))
                for px in range(tile_size):
                    offset = (px * 2 + i * 3 + frame * 4) % 5
                    if offset < 2 and y_pos < tile_size:
                        surf.set_at((px, y_pos), shimmer)
            frames[(label, frame)] = surf
    return frames


# ================================================================
# SHORE FOAM OVERLAYS
# ================================================================

def build_shore_foam_overlays(tile_size: int, num_frames: int = 3):
    """Build foam overlay surfaces for each shore edge direction and frame.

    Returns dict: {(direction_bit, frame): Surface, ...}
    direction_bit: 0=north, 1=south, 2=west, 3=east
    """
    overlays = {}
    foam_depth = max(2, tile_size // 6)  # foam strip width in pixels

    for direction in range(4):
        for frame in range(num_frames):
            surf = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)

            for i in range(foam_depth):
                # Foam fades from bright to transparent
                alpha = int(180 * (1.0 - i / foam_depth))
                # Animate: shift the foam pattern slightly per frame
                shift = frame * 2

                for px in range(tile_size):
                    # Irregular foam pattern
                    pattern = (px * 3 + i * 7 + shift) % 5
                    if pattern < 2:
                        color = (*FOAM_WHITE, alpha)
                    elif pattern < 3:
                        color = (*FOAM_LIGHT, int(alpha * 0.6))
                    else:
                        continue

                    # Place pixel based on edge direction
                    if direction == 0:    # north edge
                        surf.set_at((px, i), color)
                    elif direction == 1:  # south edge
                        surf.set_at((px, tile_size - 1 - i), color)
                    elif direction == 2:  # west edge
                        surf.set_at((i, px), color)
                    elif direction == 3:  # east edge
                        surf.set_at((tile_size - 1 - i, px), color)

            overlays[(direction, frame)] = surf

    return overlays


# ================================================================
# FLOW INDICATORS (for river-like water currents)
# ================================================================

def build_flow_arrows(tile_size: int, num_frames: int = 3):
    """Build small directional flow indicator overlays.

    Returns dict: {(dx, dy, frame): Surface}
    where (dx, dy) is the flow direction.
    Flow is determined by looking at which direction has more water neighbors.
    """
    arrows = {}
    half = tile_size // 2

    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        for frame in range(num_frames):
            surf = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)

            # Small animated chevron/streak indicating flow direction
            offset = frame * 3
            streak_color = (100, 170, 230, 100)

            # Draw 2-3 short streaks in the flow direction
            for s in range(3):
                base_x = half + dx * (3 + s * 3) + (s * 5 + 3) % tile_size
                base_y = half + dy * (3 + s * 3) + (s * 7 + 2) % tile_size

                # Animate position along flow direction
                ax = (base_x + dx * offset) % tile_size
                ay = (base_y + dy * offset) % tile_size

                # Draw a 2-3 pixel streak
                for k in range(3):
                    px_x = (ax + dx * k) % tile_size
                    px_y = (ay + dy * k) % tile_size
                    if 0 <= px_x < tile_size and 0 <= px_y < tile_size:
                        surf.set_at((px_x, px_y), streak_color)

            arrows[(dx, dy, frame)] = surf

    return arrows


def get_flow_direction(world_tiles, x: int, y: int,
                       width: int, height: int):
    """Determine flow direction for a water tile.

    Heuristic: water flows toward the direction with fewer water neighbors
    (toward land/shore). For rivers this creates a downstream visual effect.
    Returns (dx, dy) or None if no clear flow direction.
    """
    # Count water extent in each direction
    best_dir = None
    min_water = 999

    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
        count = 0
        for step in range(1, 6):
            nx, ny = x + dx * step, y + dy * step
            if 0 <= nx < width and 0 <= ny < height:
                if world_tiles[ny][nx] in _WATER_TYPES:
                    count += 1
                else:
                    break
            else:
                break

        if count < min_water and count > 0:
            min_water = count
            best_dir = (dx, dy)

    # Only show flow for narrow water bodies (river-like)
    if min_water < 4:
        return best_dir
    return None


# ================================================================
# RIPPLE EFFECTS (when entities walk through water)
# ================================================================

class WaterRipples:
    """Manages ripple animations when entities walk through shallow water."""

    def __init__(self, max_ripples: int = 20):
        self.ripples = []  # list of active ripples
        self.max_ripples = max_ripples

    def spawn(self, world_x: float, world_y: float):
        """Spawn a ripple at world coordinates."""
        if len(self.ripples) >= self.max_ripples:
            self.ripples.pop(0)

        self.ripples.append({
            "x": world_x,
            "y": world_y,
            "t": 0.0,
            "max_t": 0.6,  # seconds
            "max_radius": 8,  # pixels
        })

    def update(self, dt: float):
        """Advance all ripple animations."""
        remaining = []
        for r in self.ripples:
            r["t"] += dt
            if r["t"] < r["max_t"]:
                remaining.append(r)
        self.ripples = remaining

    def draw(self, screen, camera):
        """Draw all active ripples."""
        for r in self.ripples:
            progress = r["t"] / r["max_t"]
            radius = int(r["max_radius"] * progress)
            if radius < 1:
                continue

            alpha = int(160 * (1.0 - progress))
            sx, sy = camera.world_to_screen(r["x"], r["y"])
            sx, sy = int(sx), int(sy)

            # Draw expanding circle (anti-aliased ring)
            if alpha > 10 and radius > 1:
                # Outer ring
                _draw_circle_alpha(
                    screen, sx, sy, radius,
                    (200, 220, 255, alpha), width=1
                )
                # Inner ring (smaller, brighter)
                if radius > 3:
                    _draw_circle_alpha(
                        screen, sx, sy, radius - 2,
                        (220, 235, 255, alpha // 2), width=1
                    )

    def check_entity_in_water(self, entity, world_tiles, width, height, dt):
        """Check if an entity is walking through shallow water; spawn ripples."""
        ex, ey = int(entity.x), int(entity.y)
        if not (0 <= ex < width and 0 <= ey < height):
            return

        tile = world_tiles[ey][ex]
        if tile not in _WATER_TYPES:
            return

        # Only spawn if entity is moving
        vx = getattr(entity, "vx", 0)
        vy = getattr(entity, "vy", 0)
        if abs(vx) < 0.1 and abs(vy) < 0.1:
            return

        # Throttle: only classify shallow water tiles
        if classify_water_tile(world_tiles, ex, ey, width, height) != "shallow":
            return

        # Spawn a ripple
        self.spawn(entity.x, entity.y)


def _draw_circle_alpha(screen, cx, cy, radius, color, width=1):
    """Draw a circle with alpha on any surface."""
    if radius < 1:
        return
    size = radius * 2 + 4
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    center = size // 2
    pygame.draw.circle(surf, color, (center, center), radius, width)
    screen.blit(surf, (cx - center, cy - center))
