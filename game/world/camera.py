"""Smooth-following camera with viewport culling.

Supports variable tile sizes for strategy view (16px) vs adventure view (32px).
"""

from game.settings import *


class Camera:
    """Camera that smoothly follows a target position."""

    def __init__(self, world_width: int, world_height: int, tile_size: int = TILE_SIZE):
        self.x = 0.0
        self.y = 0.0
        self.world_w = world_width
        self.world_h = world_height
        self.tile_size = tile_size

    def set_tile_size(self, tile_size: int):
        """Change the tile size (for view mode switching).
        Preserves the world-space center point across the transition."""
        if tile_size == self.tile_size:
            return
        # Find current center in world coords
        center_wx = (self.x + SCREEN_WIDTH / 2) / self.tile_size
        center_wy = (self.y + SCREEN_HEIGHT / 2) / self.tile_size
        self.tile_size = tile_size
        # Reposition camera to keep same center
        self.x = center_wx * tile_size - SCREEN_WIDTH / 2
        self.y = center_wy * tile_size - SCREEN_HEIGHT / 2
        self._clamp()

    def _clamp(self):
        """Clamp camera to world bounds."""
        max_x = self.world_w * self.tile_size - SCREEN_WIDTH
        max_y = self.world_h * self.tile_size - SCREEN_HEIGHT
        self.x = max(0, min(max_x, self.x))
        self.y = max(0, min(max_y, self.y))

    def update(self, target_x: float, target_y: float):
        """Smoothly follow the target."""
        ts = self.tile_size
        goal_x = target_x * ts - SCREEN_WIDTH // 2
        goal_y = target_y * ts - SCREEN_HEIGHT // 2

        self.x += (goal_x - self.x) * CAMERA_LERP
        self.y += (goal_y - self.y) * CAMERA_LERP
        self._clamp()

    def world_to_screen(self, wx: float, wy: float):
        """Convert world coordinates to screen pixel coordinates."""
        ts = self.tile_size
        return (wx * ts - self.x, wy * ts - self.y)

    def screen_to_world(self, sx: float, sy: float):
        """Convert screen pixel coordinates to world coordinates."""
        ts = self.tile_size
        return ((sx + self.x) / ts, (sy + self.y) / ts)

    def get_visible_tile_range(self):
        """Get the range of tiles currently visible on screen."""
        ts = self.tile_size
        margin = 2
        x0 = max(0, int(self.x / ts) - margin)
        y0 = max(0, int(self.y / ts) - margin)
        x1 = min(self.world_w, int((self.x + SCREEN_WIDTH) / ts) + margin + 1)
        y1 = min(self.world_h, int((self.y + SCREEN_HEIGHT) / ts) + margin + 1)
        return x0, y0, x1, y1
