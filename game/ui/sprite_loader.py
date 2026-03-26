"""Sprite/Asset loader — loads sprite sheets and provides frame lookup.

Since we don't have external image files, all sprites are generated
programmatically using pygame drawing with high detail (dithering,
sub-pixel color variation, natural patterns).

The SpriteManager serves as the central registry that caches all
generated sprites for reuse across the rendering pipeline.
"""

import pygame
import random
from typing import Dict, Optional, Tuple, List


class SpriteSheet:
    """Load a sprite sheet image and extract individual frames.

    Can work with either a loaded image file or a programmatically
    generated surface arranged in a grid layout.
    """

    def __init__(self, path_or_surface, frame_width: int, frame_height: int):
        """Initialize sprite sheet.

        Args:
            path_or_surface: file path string or pygame.Surface
            frame_width: width of each frame in pixels
            frame_height: height of each frame in pixels
        """
        if isinstance(path_or_surface, str):
            self.image = pygame.image.load(path_or_surface).convert_alpha()
        else:
            self.image = path_or_surface
        self.frame_w = frame_width
        self.frame_h = frame_height
        self._cache: Dict[Tuple[int, int], pygame.Surface] = {}

    @property
    def cols(self) -> int:
        return self.image.get_width() // self.frame_w

    @property
    def rows(self) -> int:
        return self.image.get_height() // self.frame_h

    def get_frame(self, col: int, row: int) -> pygame.Surface:
        """Get a specific frame by grid position (cached)."""
        key = (col, row)
        if key not in self._cache:
            rect = pygame.Rect(
                col * self.frame_w, row * self.frame_h,
                self.frame_w, self.frame_h
            )
            surf = pygame.Surface((self.frame_w, self.frame_h), pygame.SRCALPHA)
            surf.blit(self.image, (0, 0), rect)
            self._cache[key] = surf
        return self._cache[key]

    def get_all_frames(self) -> List[pygame.Surface]:
        """Get all frames as a flat list (left-to-right, top-to-bottom)."""
        frames = []
        for r in range(self.rows):
            for c in range(self.cols):
                frames.append(self.get_frame(c, r))
        return frames


class SpriteManager:
    """Central sprite registry — loads and caches sprites.

    Generates detailed procedural pixel-art sprites for terrain tiles,
    item icons, and other game elements. All sprites are cached after
    first generation.
    """

    def __init__(self):
        self._terrain_cache: Dict[Tuple[str, int], pygame.Surface] = {}
        self._terrain_sheets: Dict[str, SpriteSheet] = {}
        self._item_cache: Dict[str, pygame.Surface] = {}
        self._initialized = False

    def initialize(self, tile_size: int = 16):
        """Generate all procedural sprite sheets.

        Args:
            tile_size: base tile size (16 for strategy, 32 for adventure)
        """
        if self._initialized:
            return
        self.tile_size = tile_size
        self._build_terrain_sprites(tile_size)
        self._initialized = True

    def _build_terrain_sprites(self, ts: int):
        """Generate terrain tile sprite sheets with variants."""
        from game.ui.terrain_sprites import generate_all_terrain_sheets
        self._terrain_sheets = generate_all_terrain_sheets(ts)

    def get_terrain_tile(self, tile_type: int, variant: int = 0) -> Optional[pygame.Surface]:
        """Get a terrain tile sprite with rotation variant.

        Args:
            tile_type: terrain type constant (e.g. GRASS, WATER)
            variant: variant index (0-3 for most tiles, 0-3 for water animation)

        Returns:
            pygame.Surface or None if no sprite exists for this type.
        """
        key = (tile_type, variant)
        if key in self._terrain_cache:
            return self._terrain_cache[key]

        sheet = self._terrain_sheets.get(tile_type)
        if sheet is None:
            return None

        # Clamp variant to available columns
        col = variant % sheet.cols
        surf = sheet.get_frame(col, 0)
        self._terrain_cache[key] = surf
        return surf

    def get_terrain_variants(self, tile_type: int) -> List[pygame.Surface]:
        """Get all variants for a terrain type."""
        sheet = self._terrain_sheets.get(tile_type)
        if sheet is None:
            return []
        return sheet.get_all_frames()

    def get_item_icon(self, item_name: str) -> Optional[pygame.Surface]:
        """Get an item icon sprite (16x16).

        Args:
            item_name: name of the item

        Returns:
            pygame.Surface or None if no icon exists.
        """
        if item_name in self._item_cache:
            return self._item_cache[item_name]
        # Item icons can be added later
        return None

    def get_variant_for_position(self, tile_type: int, x: int, y: int) -> pygame.Surface:
        """Get a deterministic variant based on world position.

        Uses a hash of (x, y) to pick a consistent variant so the
        same tile always shows the same variant.
        """
        sheet = self._terrain_sheets.get(tile_type)
        if sheet is None:
            return None
        num_variants = sheet.cols
        variant = (x * 7 + y * 13 + tile_type * 3) % num_variants
        return self.get_terrain_tile(tile_type, variant)


# Module-level singleton
_manager: Optional[SpriteManager] = None


def get_sprite_manager() -> SpriteManager:
    """Get or create the global SpriteManager singleton."""
    global _manager
    if _manager is None:
        _manager = SpriteManager()
    return _manager
