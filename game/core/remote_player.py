"""
Remote player entity for rendering on the host screen.
Mirrors the Player class interface for rendering purposes but
receives its state from network updates rather than local input.
"""

import pygame
from game.core.entity import Entity
from game.settings import TILE_SIZE


# Remote player colors by index (for distinguishing multiple players)
REMOTE_PLAYER_COLORS = [
    (100, 180, 255),   # blue
    (255, 140, 100),   # orange
    (140, 255, 140),   # green
    (255, 140, 255),   # pink
    (255, 255, 100),   # yellow
    (140, 255, 255),   # cyan
]

# AI player indicator color
AI_PLAYER_COLOR = (180, 140, 255)  # purple


class RemotePlayer(Entity):
    """Represents a remote player for rendering on the host screen.

    This is a lightweight entity that mirrors enough of the Player
    interface to be drawn by the renderer but gets its state from
    network updates.
    """

    def __init__(self, player_id: str, name: str, color_index: int = 0):
        super().__init__(0.0, 0.0)
        self.player_id = player_id
        self.name = name
        self.level = 1
        self.is_ai = False

        # Visual
        self.color_index = color_index
        self.color = REMOTE_PLAYER_COLORS[
            color_index % len(REMOTE_PLAYER_COLORS)]
        self.gait = "walk"

        # Interpolation targets
        self.target_x = 0.0
        self.target_y = 0.0
        self._lerp_speed = 8.0

        # Name tag cached surface
        self._name_surface = None
        self._name_font = None

    def update_from_network(self, x: float, y: float, hp: int = 100,
                            max_hp: int = 100, level: int = 1,
                            facing: tuple = (0, 1), gait: str = "walk",
                            is_ai: bool = False):
        """Update state from a network message."""
        self.target_x = x
        self.target_y = y
        self.hp = hp
        self.max_hp = max_hp
        self.level = level
        self.facing = facing
        self.gait = gait
        self.is_ai = is_ai
        if is_ai:
            self.color = AI_PLAYER_COLOR

    def update(self, dt: float, world=None):
        """Interpolate position toward target."""
        dx = self.target_x - self.x
        dy = self.target_y - self.y

        # Teleport if very far away
        if abs(dx) > 20 or abs(dy) > 20:
            self.x = self.target_x
            self.y = self.target_y
        else:
            factor = min(1.0, self._lerp_speed * dt)
            self.x += dx * factor
            self.y += dy * factor

    def draw(self, screen: pygame.Surface, camera, tile_size: int = TILE_SIZE):
        """Draw the remote player on screen.

        Args:
            screen: Pygame display surface.
            camera: Camera object with world_to_screen method.
            tile_size: Current tile size for scaling.
        """
        sx, sy = camera.world_to_screen(self.x, self.y)

        # Check if on screen
        sw, sh = screen.get_size()
        margin = tile_size * 2
        if sx < -margin or sx > sw + margin or sy < -margin or sy > sh + margin:
            return

        # Draw player indicator (diamond shape for remote players)
        half = max(4, tile_size // 3)
        color = self.color
        points = [
            (int(sx), int(sy - half)),       # top
            (int(sx + half), int(sy)),        # right
            (int(sx), int(sy + half)),        # bottom
            (int(sx - half), int(sy)),        # left
        ]
        pygame.draw.polygon(screen, color, points)
        pygame.draw.polygon(screen, (255, 255, 255), points, 1)

        # Direction indicator
        fx, fy = self.facing
        end_x = int(sx + fx * half * 1.5)
        end_y = int(sy + fy * half * 1.5)
        pygame.draw.line(screen, (255, 255, 255),
                         (int(sx), int(sy)), (end_x, end_y), 1)

        # Name tag above head
        self._draw_name_tag(screen, int(sx), int(sy - half - 2))

        # HP bar (if damaged)
        if self.hp < self.max_hp:
            bar_w = tile_size
            bar_h = 3
            bar_x = int(sx - bar_w // 2)
            bar_y = int(sy - half - 8)
            pygame.draw.rect(screen, (60, 60, 60),
                             (bar_x, bar_y, bar_w, bar_h))
            hp_w = max(1, int(bar_w * self.hp / max(1, self.max_hp)))
            hp_color = (50, 200, 50) if self.hp > self.max_hp * 0.5 else (200, 50, 50)
            pygame.draw.rect(screen, hp_color,
                             (bar_x, bar_y, hp_w, bar_h))

    def _draw_name_tag(self, screen: pygame.Surface, cx: int, y: int):
        """Draw the player name above their position."""
        # Lazy-init font
        if self._name_font is None:
            try:
                self._name_font = pygame.font.SysFont("monospace", 11)
            except Exception:
                self._name_font = pygame.font.Font(None, 12)

        # Cache the rendered name surface
        if self._name_surface is None:
            prefix = "[AI] " if self.is_ai else ""
            label = f"{prefix}{self.name}"
            self._name_surface = self._name_font.render(
                label, True, self.color)

        # Draw with background
        nw = self._name_surface.get_width()
        nh = self._name_surface.get_height()
        nx = cx - nw // 2
        ny = y - nh

        bg = pygame.Surface((nw + 4, nh + 2), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 140))
        screen.blit(bg, (nx - 2, ny - 1))
        screen.blit(self._name_surface, (nx, ny))

    def draw_on_minimap(self, screen: pygame.Surface,
                        minimap_x: int, minimap_y: int,
                        scale_x: float, scale_y: float):
        """Draw a dot on the minimap for this remote player."""
        mx = int(minimap_x + self.x * scale_x)
        my = int(minimap_y + self.y * scale_y)
        pygame.draw.circle(screen, self.color, (mx, my), 3)
        if self.is_ai:
            pygame.draw.circle(screen, AI_PLAYER_COLOR, (mx, my), 3, 1)
