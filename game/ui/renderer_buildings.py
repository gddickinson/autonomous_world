"""Building and interior rendering — roofs, doors, interiors, graves."""

import pygame
import random
import math
from game.settings import *


class RendererBuildingsMixin:

    """Mixin — see parent class for context."""

    def _build_roof_cache(self):
        """Build colored roof tiles for different structure types."""
        self._roof_cache = {}
        roof_styles = {
            "village":  (120, 90, 60),   # brown thatch
            "hamlet":   (110, 95, 55),   # straw thatch
            "town":     (140, 100, 70),  # tile roof
            "city":     (100, 100, 115), # slate roof
            "castle":   (85, 85, 95),    # stone roof
            "temple":   (230, 220, 180), # white/gold
            "tavern":   (150, 95, 55),   # warm brown
            "blacksmith": (70, 70, 75),  # dark gray
            "market":   (170, 110, 60),  # vibrant warm
            "house":    (130, 100, 65),  # earth tones
            "default":  (90, 80, 70),    # fallback gray
        }
        for kind, base in roof_styles.items():
            surf = pygame.Surface((TILE_SIZE, TILE_SIZE))
            r, g, b = base
            surf.fill(base)
            # Horizontal line pattern (roof tiles/thatch)
            for i in range(0, TILE_SIZE, 4):
                shade = r - 12 + (i % 8)
                pygame.draw.line(surf, (max(0, shade), max(0, g - 10), max(0, b - 8)),
                                (0, i), (TILE_SIZE, i))
            # Ridge line down the middle
            pygame.draw.line(surf, (max(0, r - 25), max(0, g - 25), max(0, b - 20)),
                            (TILE_SIZE // 2, 0), (TILE_SIZE // 2, TILE_SIZE))
            self._roof_cache[kind] = surf

            # Also make dimmed version
            dimmed = surf.copy()
            dark = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
            dark.fill((0, 0, 0, 140))
            dimmed.blit(dark, (0, 0))
            self._roof_cache[kind + "_dim"] = dimmed

    def _get_roof_for_tile(self, x: int, y: int, world) -> pygame.Surface:
        """Get the appropriate roof surface for a building tile based on its structure."""
        if not hasattr(self, '_roof_cache') or not self._roof_cache:
            self._build_roof_cache()

        # Find which structure this tile belongs to
        if not hasattr(self, '_tile_structure_map'):
            self._tile_structure_map = {}
            for s in world.structures:
                for bx, by, bw, bh in getattr(s, 'buildings', []):
                    for ty in range(by, by + bh):
                        for tx in range(bx, bx + bw):
                            self._tile_structure_map[(tx, ty)] = s.kind
            # Also check plan settlements (chunked worlds)
            if hasattr(world, 'plan'):
                for sp in world.plan.settlements:
                    for bld in sp.buildings:
                        bx, by = bld['x'], bld['y']
                        bw, bh = bld['w'], bld['h']
                        for ty in range(by, by + bh):
                            for tx in range(bx, bx + bw):
                                if (tx, ty) not in self._tile_structure_map:
                                    self._tile_structure_map[(tx, ty)] = sp.kind

        kind = self._tile_structure_map.get((x, y), "default")
        # Check building function cache for more specific roof colors
        bfunc = self._building_function_cache.get((x, y), "")
        if bfunc:
            func_lower = bfunc.lower()
            if "tavern" in func_lower or "inn" in func_lower:
                kind = "tavern"
            elif "temple" in func_lower or "shrine" in func_lower or "church" in func_lower:
                kind = "temple"
            elif "blacksmith" in func_lower or "forge" in func_lower or "smith" in func_lower:
                kind = "blacksmith"
            elif "market" in func_lower or "shop" in func_lower or "store" in func_lower:
                kind = "market"
            elif "house" in func_lower or "cottage" in func_lower or "hovel" in func_lower:
                kind = "house"
        return self._roof_cache.get(kind, self._roof_cache.get("default"))

    def _get_roof_dimmed(self, x: int, y: int, world) -> pygame.Surface:
        """Get dimmed roof for explored-but-not-visible tiles."""
        if not hasattr(self, '_roof_cache') or not self._roof_cache:
            self._build_roof_cache()
        if not hasattr(self, '_tile_structure_map'):
            self._get_roof_for_tile(x, y, world)  # build map
        kind = self._tile_structure_map.get((x, y), "default")
        return self._roof_cache.get(kind + "_dim", self._roof_cache.get("default_dim"))

    def _draw_building_heights(self, world, camera, player, x0, y0, x1, y1):
        """Draw 2.5D building heights using per-tile cube approach.

        Each WALL tile is treated as a cube. We draw:
        - South face: on any wall tile that has a non-wall tile to its south
        - East face: on any wall tile that has a non-wall tile to its east
        - Roof: on top of all building tiles (wall + interior), offset upward

        This naturally follows any building shape — rectangular, circular,
        L-shaped, etc.
        """
        player_rect = getattr(player, '_current_building_rect', None) if player else None
        time_norm = getattr(world, '_time_normalized', 0.35)
        building_tiles = getattr(world, '_building_interior_tiles', set())

        # Determine building heights from the tile structure map
        if not hasattr(self, '_tile_structure_map'):
            self._get_roof_for_tile(0, 0, world)  # builds the map

        # Collect all building tile positions with their height
        height_map = {}  # (x, y) -> num_floors
        if hasattr(world, 'plan'):
            for sp in world.plan.settlements:
                for bld in sp.buildings:
                    bx, by = bld['x'], bld['y']
                    bw, bh = bld['w'], bld['h']
                    bname = bld.get('name', '')
                    if 'Tower' in bname or 'Keep' in bname or 'Castle' in bname:
                        nf = 3
                    elif sp.kind in ('city', 'castle'):
                        nf = 2
                    else:
                        nf = 1
                    for dy in range(bh):
                        for dx in range(bw):
                            height_map[(bx + dx, by + dy)] = nf
            # Temples
            for loc in world.plan.special_locations:
                if loc.kind == 'temple':
                    r = loc.radius
                    for dy in range(-r, r + 1):
                        for dx in range(-r, r + 1):
                            if dx * dx + dy * dy <= r * r:
                                height_map[(loc.x + dx, loc.y + dy)] = 1

        wall_types = (WALL,)
        interior_types = (FLOOR, TABLE, BED, CHEST, STAIRS_UP, STAIRS_DOWN,
                          FIREPLACE, PILLAR, ALTAR, THRONE, BOOKSHELF, BARREL,
                          ANVIL, FORGE_FIRE, FOUNTAIN, CARPET, MOSAIC, ARCHWAY,
                          DOOR, WINDOW)
        floor_px = TILE_SIZE * 3 // 4  # height per floor in pixels

        # Wall colors
        wall_color_s = (140, 125, 105)  # south face (lit)
        wall_color_e = (110, 100, 85)   # east face (darker)

        # Roof colors by kind
        roof_colors = {
            "hamlet": (140, 100, 55), "village": (130, 75, 40),
            "town": (110, 80, 55), "city": (85, 90, 100),
            "castle": (70, 75, 85), "temple": (150, 130, 60),
        }

        # Process tiles from north to south (painter's algorithm)
        for y in range(y0, y1):
            for x in range(x0, x1):
                if (x, y) not in height_map:
                    continue

                # Skip building the player is inside
                if player_rect:
                    pbx, pby, pbw, pbh = player_rect
                    if pbx <= x < pbx + pbw and pby <= y < pby + pbh:
                        continue

                tile = world.tiles[y][x]
                if tile not in wall_types and tile not in interior_types:
                    continue

                num_floors = height_map[(x, y)]
                wall_h = num_floors * floor_px

                sx = x * TILE_SIZE - int(camera.x)
                sy = y * TILE_SIZE - int(camera.y)

                # --- SOUTH FACE ---
                # Draw on ANY building-edge tile (not just WALL) so the
                # exterior wall aligns with the floor plan boundary.
                south_in_building = (x, y + 1) in height_map
                if not south_in_building:
                    wr, wg, wb = wall_color_s
                    wall_top = sy + TILE_SIZE
                    wall_bot = wall_top + wall_h
                    # Clamp to screen
                    draw_top = max(0, wall_top)
                    draw_bot = min(SCREEN_HEIGHT, wall_bot)
                    if draw_top < draw_bot:
                        # Single rect fill for the wall face
                        pygame.draw.rect(self.screen, (wr, wg, wb),
                                         (sx, draw_top, TILE_SIZE, draw_bot - draw_top))
                        # Gradient: darken bottom with a single overlay
                        if wall_h > 4:
                            grad_h = (draw_bot - draw_top) // 2
                            grad_surf = pygame.Surface((TILE_SIZE, grad_h), pygame.SRCALPHA)
                            grad_surf.fill((0, 0, 0, 30))
                            self.screen.blit(grad_surf, (sx, draw_bot - grad_h))
                        # A few accent brick lines (every 6px instead of every 3px)
                        brick_color = (max(0, wr - 18), max(0, wg - 18), max(0, wb - 15))
                        for py in range(0, wall_h, 6):
                            draw_y = wall_top + py
                            if draw_top <= draw_y < draw_bot:
                                pygame.draw.line(self.screen, brick_color,
                                                 (sx, draw_y), (sx + TILE_SIZE, draw_y))

                # --- EAST FACE ---
                east_in_building = (x + 1, y) in height_map
                if not east_in_building:
                    wr, wg, wb = wall_color_e
                    east_x = sx + TILE_SIZE
                    east_w = max(2, TILE_SIZE // 5)
                    wall_top_e = sy + TILE_SIZE
                    wall_bot_e = wall_top_e + wall_h
                    draw_top_e = max(0, wall_top_e)
                    draw_bot_e = min(SCREEN_HEIGHT, wall_bot_e)
                    if draw_top_e < draw_bot_e and 0 <= east_x < SCREEN_WIDTH:
                        # Single rect fill for east face
                        draw_w = min(east_w, SCREEN_WIDTH - east_x)
                        pygame.draw.rect(self.screen,
                                         (int(wr * 0.85), int(wg * 0.85), int(wb * 0.85)),
                                         (east_x, draw_top_e, draw_w, draw_bot_e - draw_top_e))
                        # Darken bottom half
                        if wall_h > 4:
                            grad_h = (draw_bot_e - draw_top_e) // 2
                            grad_surf = pygame.Surface((draw_w, grad_h), pygame.SRCALPHA)
                            grad_surf.fill((0, 0, 0, 25))
                            self.screen.blit(grad_surf, (east_x, draw_bot_e - grad_h))

                # --- FLAT ROOF TILE (drawn offset upward) ---
                kind = self._tile_structure_map.get((x, y), "default")
                # Override kind based on building function for colored roofs
                bfunc = self._building_function_cache.get((x, y), "")
                if bfunc:
                    fl = bfunc.lower()
                    if "tavern" in fl or "inn" in fl:
                        kind = "tavern"
                    elif "temple" in fl or "shrine" in fl:
                        kind = "temple"
                    elif "blacksmith" in fl or "forge" in fl or "smith" in fl:
                        kind = "blacksmith"
                    elif "market" in fl or "shop" in fl:
                        kind = "market"
                roof_y = sy - wall_h
                if -TILE_SIZE < roof_y < SCREEN_HEIGHT:
                    roof_surf = self._get_roof_tile_25d(kind, x, y)
                    self.screen.blit(roof_surf, (sx, roof_y))

        # --- PITCHED ROOF PASS ---
        # Draw pitched gable roofs on top of buildings. The gable is a
        # triangular south face + sloped ridge visible from above.
        self._draw_pitched_roofs(world, camera, player_rect, height_map,
                                 floor_px, x0, y0, x1, y1)

    def _draw_pitched_roofs(self, world, camera, player_rect, height_map,
                            floor_px, x0, y0, x1, y1):
        """Draw pitched roof shading over the flat roof tiles.

        Following the standard 3/4 perspective approach (Zelda, Stardew
        Valley, RPG Maker): the roof is already drawn as flat tiles. We
        add slope shading — south half is lit (brighter), north half is
        in shadow (darker), with a ridge line across the center. This
        creates the illusion of a pitched roof without any geometric
        projection. For circular buildings, apply radial shading instead.
        """
        buildings = []
        if hasattr(world, 'plan'):
            for sp in world.plan.settlements:
                for bld in sp.buildings:
                    bx, by = bld['x'], bld['y']
                    bw, bh = bld['w'], bld['h']
                    if bx + bw < x0 or bx > x1 or by + bh < y0 or by > y1:
                        continue
                    if player_rect and player_rect == (bx, by, bw, bh):
                        continue
                    buildings.append((bx, by, bw, bh, sp.kind, bld.get('name', '')))

            for loc in world.plan.special_locations:
                if loc.kind == 'temple':
                    r = loc.radius
                    bx, by = loc.x - r, loc.y - r
                    bw, bh = r * 2 + 1, r * 2 + 1
                    if bx + bw >= x0 and bx <= x1 and by + bh >= y0 and by <= y1:
                        if not (player_rect and player_rect == (bx, by, bw, bh)):
                            buildings.append((bx, by, bw, bh, 'temple', loc.name))

        for bx, by, bw, bh, kind, bname in buildings:
            sample_h = height_map.get((bx + 1, by + 1), 1)
            wall_h = sample_h * floor_px

            wall_w_px = bw * TILE_SIZE
            wall_h_px = bh * TILE_SIZE
            sx = bx * TILE_SIZE - int(camera.x)
            sy = by * TILE_SIZE - int(camera.y) - wall_h  # roof level

            is_circular = kind == 'temple'

            # Create a shading overlay for the pitched effect
            shade_surf = pygame.Surface((wall_w_px, wall_h_px), pygame.SRCALPHA)

            if is_circular:
                # Conical roof: darken radially from center, with south
                # side brighter (facing our viewpoint)
                cx_l = wall_w_px // 2
                cy_l = wall_h_px // 2
                max_r = min(cx_l, cy_l)
                for py in range(wall_h_px):
                    for px in range(wall_w_px):
                        dx = px - cx_l
                        dy = py - cy_l
                        dist = (dx * dx + dy * dy) ** 0.5
                        if dist > max_r + 2:
                            continue
                        # Radial: darker at edges (slope falls away)
                        r_t = min(1.0, dist / max(1, max_r))
                        # Directional: south side (dy > 0) is brighter
                        dir_t = (dy / max(1, max_r)) * 0.3
                        # Combined: center is bright, edges dark, south brighter
                        alpha = int(r_t * 80 - dir_t * 40)
                        alpha = max(0, min(120, alpha))
                        shade_surf.set_at((px, py), (0, 0, 0, alpha))
                # Highlight ring near the peak
                pygame.draw.circle(shade_surf, (255, 255, 200, 25),
                                   (cx_l, cy_l), max(3, max_r // 4), 1)
            else:
                # Gable roof: north half darkened, south half brightened,
                # ridge line across the center
                mid_y = wall_h_px // 2
                for py in range(wall_h_px):
                    if py < mid_y:
                        # North slope: in shadow (darken)
                        t = 1.0 - (py / max(1, mid_y))  # 1 at top, 0 at ridge
                        alpha = int(t * 70 + 20)
                        pygame.draw.line(shade_surf, (0, 0, 0, alpha),
                                         (0, py), (wall_w_px - 1, py))
                    else:
                        # South slope: lit (brighten slightly)
                        t = (py - mid_y) / max(1, wall_h_px - mid_y)
                        alpha = int((1.0 - t) * 25)  # brightest near ridge
                        pygame.draw.line(shade_surf, (255, 255, 220, alpha),
                                         (0, py), (wall_w_px - 1, py))

                # Ridge line
                pygame.draw.line(shade_surf, (0, 0, 0, 80),
                                 (0, mid_y), (wall_w_px - 1, mid_y), 2)
                # Subtle highlight just south of ridge
                pygame.draw.line(shade_surf, (255, 255, 200, 30),
                                 (0, mid_y + 2), (wall_w_px - 1, mid_y + 2))

            self.screen.blit(shade_surf, (sx, sy))

            # Eave shadow line at the south edge of the roof
            eave_y = sy + wall_h_px
            if 0 <= eave_y < SCREEN_HEIGHT:
                pygame.draw.line(self.screen, (40, 35, 30),
                                 (sx, eave_y), (sx + wall_w_px - 1, eave_y))

    def _get_roof_tile_25d(self, kind: str, wx: int, wy: int) -> pygame.Surface:
        """Get a pre-rendered roof tile for the 2.5D view.

        Different building types get different roof styles:
          hamlet:  thatch (straw bundles, warm golden-brown)
          village: clay tile (overlapping orange-red tiles)
          town:    wood shingle (dark brown planks)
          city:    slate (gray-blue flat stone)
          castle:  stone battlement (gray crenellations)
          temple:  copper/gold (green-gold patina)

        Each tile has per-position variation so roofs don't look uniform.
        """
        # Cache key includes kind + position hash for variation
        variant = (wx * 7 + wy * 13) % 4
        cache_key = (kind, variant)

        if not hasattr(self, '_roof_25d_cache'):
            self._roof_25d_cache = {}

        if cache_key in self._roof_25d_cache:
            return self._roof_25d_cache[cache_key]

        ts = TILE_SIZE
        surf = pygame.Surface((ts, ts))

        if kind == "hamlet":
            # THATCH — warm straw bundles
            base = (155 + variant * 5, 120 + variant * 3, 55 + variant * 4)
            surf.fill(base)
            r, g, b = base
            # Horizontal straw lines
            for py in range(0, ts, 2):
                offset = variant * 2 + (py // 2) % 3
                shade = r - 8 + (py % 4) * 2
                pygame.draw.line(surf, (max(40, shade), max(40, g - 6), max(20, b - 4)),
                                 (offset, py), (ts, py))
            # Straw bundle edges (diagonal)
            for py in range(0, ts, 5):
                pygame.draw.line(surf, (r - 20, g - 15, b - 8),
                                 (0, py), (min(ts, py + 6), 0))

        elif kind == "village":
            # CLAY TILE — overlapping curved red-orange tiles
            base = (165 + variant * 4, 75 + variant * 3, 40 + variant * 2)
            surf.fill(base)
            r, g, b = base
            # Overlapping tile rows
            tile_h = max(3, ts // 4)
            for row in range(0, ts, tile_h):
                offset = (tile_h // 2) if (row // tile_h) % 2 else 0
                # Each tile is a small rounded rectangle
                for col in range(offset - tile_h, ts + tile_h, tile_h + 1):
                    shade = r + ((col + row) % 3) * 4 - 4
                    tc = (max(40, min(255, shade)),
                          max(20, min(255, g + ((col * 3) % 5) - 2)),
                          max(15, min(255, b + ((row * 2) % 3) - 1)))
                    pygame.draw.rect(surf, tc, (col, row, tile_h, tile_h - 1))
                    # Highlight on top edge of each tile
                    pygame.draw.line(surf, (min(255, tc[0] + 15), min(255, tc[1] + 10), min(255, tc[2] + 8)),
                                     (col, row), (col + tile_h - 1, row))

        elif kind == "town":
            # WOOD SHINGLE — dark brown overlapping planks
            base = (95 + variant * 3, 70 + variant * 2, 45 + variant * 2)
            surf.fill(base)
            r, g, b = base
            plank_h = max(3, ts // 5)
            for row in range(0, ts, plank_h):
                offset = (ts // 3) if (row // plank_h) % 2 else 0
                for col in range(offset - ts // 2, ts + ts // 2, ts // 2):
                    shade = ((col + row * 3) % 7) - 3
                    pc = (max(30, r + shade * 2), max(20, g + shade), max(15, b + shade))
                    pygame.draw.rect(surf, pc, (col, row, ts // 2 - 1, plank_h - 1))
                    # Wood grain
                    pygame.draw.line(surf, (max(20, r - 12), max(15, g - 10), max(10, b - 8)),
                                     (col + 1, row + plank_h // 2),
                                     (col + ts // 2 - 2, row + plank_h // 2))

        elif kind == "city":
            # SLATE — flat gray-blue stone tiles
            base = (90 + variant * 3, 95 + variant * 2, 110 + variant * 3)
            surf.fill(base)
            r, g, b = base
            slate_h = max(2, ts // 6)
            for row in range(0, ts, slate_h):
                offset = (ts // 4) if (row // slate_h) % 2 else 0
                for col in range(offset - ts // 3, ts + ts // 3, ts // 3):
                    shade = ((col * 5 + row * 7) % 5) - 2
                    sc = (max(50, r + shade * 2), max(55, g + shade * 2), max(65, b + shade * 3))
                    pygame.draw.rect(surf, sc, (col, row, ts // 3 - 1, slate_h - 1))
            # Subtle blue sheen
            sheen = pygame.Surface((ts, ts), pygame.SRCALPHA)
            sheen.fill((100, 120, 160, 15))
            surf.blit(sheen, (0, 0))

        elif kind == "castle":
            # STONE BATTLEMENT — gray stone blocks, darker
            base = (75 + variant * 2, 75 + variant * 2, 80 + variant * 3)
            surf.fill(base)
            r, g, b = base
            block_w = max(3, ts // 3)
            block_h = max(3, ts // 3)
            for row in range(0, ts, block_h):
                offset = (block_w // 2) if (row // block_h) % 2 else 0
                for col in range(offset, ts, block_w):
                    shade = ((col + row) % 4) - 2
                    bc = (max(40, r + shade * 3), max(40, g + shade * 3), max(45, b + shade * 3))
                    pygame.draw.rect(surf, bc, (col, row, block_w - 1, block_h - 1))
            # Mortar lines
            for row in range(0, ts, block_h):
                pygame.draw.line(surf, (max(30, r - 20), max(30, g - 20), max(35, b - 18)),
                                 (0, row), (ts, row))

        elif kind == "temple":
            # WHITE/GOLD — bright stone with gold trim
            base = (210 + variant * 3, 200 + variant * 2, 170 + variant * 4)
            surf.fill(base)
            r, g, b = base
            # Gold trim pattern
            for py in range(0, ts, 4):
                pygame.draw.line(surf, (min(255, r + 10), min(255, g - 5), max(40, b - 30)),
                                 (0, py), (ts, py))
            # Gold decorative cross at center
            cx_t, cy_t = ts // 2, ts // 2
            pygame.draw.line(surf, (220, 190, 60), (cx_t - 2, cy_t), (cx_t + 2, cy_t), 1)
            pygame.draw.line(surf, (220, 190, 60), (cx_t, cy_t - 2), (cx_t, cy_t + 2), 1)
            # Subtle golden sheen
            sheen = pygame.Surface((ts, ts), pygame.SRCALPHA)
            sheen.fill((255, 240, 180, 12))
            surf.blit(sheen, (0, 0))

        elif kind == "tavern":
            # WARM BROWN — inviting reddish-brown thatch/tiles
            base = (155 + variant * 3, 90 + variant * 2, 50 + variant * 2)
            surf.fill(base)
            r, g, b = base
            # Warm tile rows
            tile_h = max(3, ts // 4)
            for row in range(0, ts, tile_h):
                offset = (tile_h // 2) if (row // tile_h) % 2 else 0
                for col in range(offset - tile_h, ts + tile_h, tile_h + 1):
                    shade = r + ((col + row) % 3) * 3 - 3
                    tc = (max(40, min(255, shade)),
                          max(20, min(255, g + ((col * 2) % 4) - 2)),
                          max(15, min(255, b + ((row) % 3) - 1)))
                    pygame.draw.rect(surf, tc, (col, row, tile_h, tile_h - 1))

        elif kind == "blacksmith":
            # DARK GRAY — sooty, dark with embers
            base = (65 + variant * 2, 62 + variant * 2, 60 + variant * 3)
            surf.fill(base)
            r, g, b = base
            # Dark shingle rows
            for row in range(0, ts, 3):
                offset = (ts // 3) if (row // 3) % 2 else 0
                for col in range(offset - ts // 2, ts + ts // 2, ts // 2):
                    shade = ((col + row * 3) % 5) - 2
                    pygame.draw.rect(surf, (max(30, r + shade), max(30, g + shade),
                                             max(30, b + shade)),
                                     (col, row, ts // 2 - 1, 2))
            # Occasional ember glow
            if variant == 0:
                surf.set_at((ts // 3, ts // 2), (200, 100, 30))
            # Soot darkening
            soot = pygame.Surface((ts, ts), pygame.SRCALPHA)
            soot.fill((0, 0, 0, 20))
            surf.blit(soot, (0, 0))

        elif kind == "market":
            # VIBRANT — colorful canvas/awning style
            base = (170 + variant * 4, 110 + variant * 3, 55 + variant * 3)
            surf.fill(base)
            r, g, b = base
            # Colorful stripe pattern (like canvas awnings)
            stripe_colors = [
                (180, 60, 50), (50, 120, 170), (180, 150, 40), (60, 140, 70),
            ]
            stripe_w = max(2, ts // 4)
            for i, sc in enumerate(stripe_colors):
                sx_s = i * stripe_w
                pygame.draw.rect(surf, sc, (sx_s, 0, stripe_w - 1, ts))
            # Semi-transparent overlay to blend
            blend = pygame.Surface((ts, ts), pygame.SRCALPHA)
            blend.fill((r, g, b, 100))
            surf.blit(blend, (0, 0))

        else:
            # DEFAULT — simple brown
            base = (120 + variant * 3, 95 + variant * 2, 65 + variant * 2)
            surf.fill(base)
            r, g, b = base
            for py in range(0, ts, 3):
                pygame.draw.line(surf, (max(40, r - 10), max(40, g - 8), max(30, b - 6)),
                                 (0, py), (ts, py))

        self._roof_25d_cache[cache_key] = surf
        return surf

    def _get_floor_overlay(self, player, world) -> dict:
        """Get tile overrides for a non-ground floor the player is on.

        Underground levels read from world.underground (the shared underground
        tile system). Upper floors read from the plan's building floor data.
        """
        floor_num = getattr(player, 'current_floor', 0)
        if floor_num == 0:
            return {}

        current_building = getattr(player, '_current_building_rect', None)

        # Underground: read from world.underground tile layer
        if floor_num < 0 and hasattr(world, 'underground'):
            level_tiles = world.underground.get(floor_num, {})
            if current_building:
                bx, by, bw, bh = current_building
                # Return all underground tiles in the building area + nearby
                # (tunnels may extend beyond building footprint)
                overlay = {}
                margin = 20  # look beyond building for tunnels
                for ty in range(by - margin, by + bh + margin):
                    for tx in range(bx - margin, bx + bw + margin):
                        if (tx, ty) in level_tiles:
                            overlay[(tx, ty)] = level_tiles[(tx, ty)]
                return overlay
            return {}

        # Upper floors: read from plan building data
        if floor_num > 0 and current_building:
            bx, by, bw, bh = current_building
            if hasattr(world, 'plan'):
                for sp in world.plan.settlements:
                    for bld in sp.buildings:
                        if (bld['x'] == bx and bld['y'] == by and
                                bld['w'] == bw and bld['h'] == bh):
                            floors = bld.get('floors', {})
                            floor_tiles = floors.get(floor_num)
                            if floor_tiles:
                                overlay = {}
                                for iy in range(min(len(floor_tiles), bh)):
                                    for ix in range(min(len(floor_tiles[iy]), bw)):
                                        overlay[(bx + ix, by + iy)] = floor_tiles[iy][ix]
                                return overlay
                            break

        return {}

        return overlay

    def _blend_terrain_edge(self, world, x: int, y: int, sx: int, sy: int,
                            tile_type: int):
        """Draw subtle edge blending where two natural terrain types meet.
        Uses semi-transparent pixels along the tile edges for a softer look."""
        if not hasattr(self, '_edge_cache'):
            self._edge_cache = {}

        # Check 4 neighbors
        neighbors = [(x + 1, y, "right"), (x, y + 1, "down")]
        natural = {GRASS, SAND, FOREST, DENSE_FOREST, SNOW, SWAMP, WATER,
                    MOUNTAIN, FARMLAND, ROCKY_GROUND, MARSH}

        for nx, ny, direction in neighbors:
            if not (0 <= nx < world.width and 0 <= ny < world.height):
                continue
            neighbor_type = world.tiles[ny][nx]
            if neighbor_type == tile_type or neighbor_type not in natural:
                continue

            # Create a small blending overlay
            cache_key = (tile_type, neighbor_type, direction)
            if cache_key not in self._edge_cache:
                blend = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                n_color = TERRAIN_COLORS.get(neighbor_type, (80, 80, 80))

                if direction == "right":
                    # Blend right edge: neighbor color fades in from right
                    for px in range(TILE_SIZE * 2 // 3, TILE_SIZE):
                        alpha = int(((px - TILE_SIZE * 2 // 3) / (TILE_SIZE // 3)) * 80)
                        # Dither pattern
                        for py in range(0, TILE_SIZE, 2):
                            if (px + py) % 3 == 0:
                                blend.set_at((px, py),
                                             (n_color[0], n_color[1], n_color[2], alpha))
                elif direction == "down":
                    for py in range(TILE_SIZE * 2 // 3, TILE_SIZE):
                        alpha = int(((py - TILE_SIZE * 2 // 3) / (TILE_SIZE // 3)) * 80)
                        for px in range(0, TILE_SIZE, 2):
                            if (px + py) % 3 == 0:
                                blend.set_at((px, py),
                                             (n_color[0], n_color[1], n_color[2], alpha))

                self._edge_cache[cache_key] = blend

            self.screen.blit(self._edge_cache[cache_key], (sx, sy))

    # ================================================================
    # INTERIOR RENDERING
    # ================================================================

    def draw_interior(self, interior, player, camera):
        """Draw an interior map with thin walls and large detailed tiles."""
        from game.systems.interiors import INTERIOR_TILE_SIZE

        ts = INTERIOR_TILE_SIZE  # 64px per tile — detailed interiors

        # Center camera on player, clamped to interior bounds
        ix = player.interior_state.interior_x
        iy = player.interior_state.interior_y
        cam_x = ix * ts - SCREEN_WIDTH // 2
        cam_y = iy * ts - SCREEN_HEIGHT // 2

        # Clamp camera so we don't show black void outside the interior
        max_cam_x = interior.width * ts - SCREEN_WIDTH
        max_cam_y = interior.height * ts - SCREEN_HEIGHT
        cam_x = max(0, min(max_cam_x, cam_x))
        cam_y = max(0, min(max_cam_y, cam_y))

        # Building-type-specific color palette
        kind = getattr(interior, 'building_kind', 'house')
        palettes = {
            "house":   {"wall": (88, 78, 65), "floor": (155, 135, 100), "bg": (18, 14, 12)},
            "tavern":  {"wall": (95, 75, 55), "floor": (160, 130, 85),  "bg": (20, 15, 10)},
            "shop":    {"wall": (90, 80, 68), "floor": (150, 128, 95),  "bg": (18, 14, 12)},
            "temple":  {"wall": (100, 95, 88), "floor": (165, 155, 138), "bg": (15, 14, 16)},
            "castle":  {"wall": (85, 82, 78), "floor": (140, 135, 125), "bg": (12, 12, 14)},
            "dungeon": {"wall": (60, 55, 50), "floor": (95, 88, 78),   "bg": (8, 6, 6)},
            "ruins":   {"wall": (65, 58, 52), "floor": (100, 90, 75),  "bg": (10, 8, 7)},
            "cave":    {"wall": (55, 50, 45), "floor": (85, 78, 68),   "bg": (6, 5, 5)},
            "blacksmith": {"wall": (80, 72, 62), "floor": (130, 115, 90), "bg": (15, 10, 8)},
        }
        pal = palettes.get(kind, palettes["house"])
        wall_col = pal["wall"]
        floor_col = pal["floor"]

        self.screen.fill(pal["bg"])

        m = ts // 8  # margin unit for furniture detail

        for y in range(interior.height):
            for x in range(interior.width):
                sx = x * ts - int(cam_x)
                sy = y * ts - int(cam_y)
                if sx < -ts or sx > SCREEN_WIDTH or sy < -ts or sy > SCREEN_HEIGHT:
                    continue

                t = interior.tiles[y][x]
                color = TERRAIN_COLORS.get(t, (50, 50, 50))

                # Base fill
                pygame.draw.rect(self.screen, color, (sx, sy, ts, ts))

                # === DETAILED TILE RENDERING AT 128px ===
                if t == WALL:
                    # Stone wall with mortar texture (palette-aware)
                    wr, wg, wb = wall_col
                    pygame.draw.rect(self.screen, wall_col, (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (max(0,wr-12), max(0,wg-12), max(0,wb-10)),
                                    (sx, sy, ts, ts), 2)
                    # Check if adjacent to floor — add shadow at base
                    for dx2, dy2 in [(0,1),(0,-1),(1,0),(-1,0)]:
                        nx2, ny2 = x+dx2, y+dy2
                        if (0 <= nx2 < interior.width and 0 <= ny2 < interior.height
                            and interior.tiles[ny2][nx2] != WALL
                            and interior.tiles[ny2][nx2] != WINDOW):
                            # Shadow on the floor tile adjacent to this wall
                            shadow = pygame.Surface((ts, 4), pygame.SRCALPHA)
                            shadow.fill((0, 0, 0, 40))
                            fsx = nx2 * ts - int(cam_x)
                            fsy = ny2 * ts - int(cam_y)
                            if dy2 == 1:  # wall is above floor
                                self.screen.blit(shadow, (fsx, fsy))
                            elif dy2 == -1:  # wall is below floor
                                self.screen.blit(shadow, (fsx, fsy + ts - 4))
                            break  # only one shadow per wall
                    # Mortar pattern
                    mortar = (max(0,wr-18), max(0,wg-18), max(0,wb-15))
                    for ly in range(sy + ts//4, sy + ts, ts//4):
                        pygame.draw.line(self.screen, mortar, (sx+2, ly), (sx+ts-2, ly))
                    for lx in range(sx + ts//3, sx + ts, ts//3):
                        pygame.draw.line(self.screen, mortar, (lx, sy+2), (lx, sy+ts//4))
                    # Stone block variation
                    for by2 in range(ts//4, ts, ts//4):
                        offset = ts//6 if (by2 // (ts//4)) % 2 else 0
                        for bx2 in range(offset, ts, ts//3):
                            shade = wr + ((bx2 + by2) % 5) * 2 - 4
                            sw2 = min(ts//3 - 2, ts - bx2 - 1)
                            if sw2 > 2:
                                pygame.draw.rect(self.screen,
                                    (max(0,min(255,shade)), max(0,min(255,wg+((bx2+by2)%3)-1)),
                                     max(0,min(255,wb+((bx2*by2)%3)-1))),
                                    (sx+bx2+1, sy+by2+1, sw2, ts//4-2))

                elif t == FLOOR:
                    # Floor with tile pattern (palette-aware)
                    fr, fg, fb = floor_col
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    grout = (max(0,fr-15), max(0,fg-15), max(0,fb-12))
                    pygame.draw.rect(self.screen, grout, (sx, sy, ts, ts), 1)
                    # Floor tile pattern
                    pygame.draw.line(self.screen, grout, (sx+ts//2, sy), (sx+ts//2, sy+ts))
                    pygame.draw.line(self.screen, grout, (sx, sy+ts//2), (sx+ts, sy+ts//2))
                    # Slight shade variation per quadrant
                    for qy in range(2):
                        for qx in range(2):
                            shade = ((qx + qy) % 2) * 4 - 2
                            qs = pygame.Surface((ts//2-2, ts//2-2), pygame.SRCALPHA)
                            if shade > 0:
                                qs.fill((255, 255, 255, shade * 3))
                            else:
                                qs.fill((0, 0, 0, abs(shade) * 3))
                            self.screen.blit(qs, (sx + qx * ts//2 + 1, sy + qy * ts//2 + 1))

                elif t == DOOR:
                    # Wooden door with frame and handle
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))  # floor behind
                    pygame.draw.rect(self.screen, (130, 95, 50), (sx+m, sy+m, ts-2*m, ts-2*m))
                    pygame.draw.rect(self.screen, (100, 70, 35), (sx+m, sy+m, ts-2*m, ts-2*m), 2)
                    # Planks
                    pygame.draw.line(self.screen, (110, 80, 40), (sx+ts//2, sy+m), (sx+ts//2, sy+ts-m))
                    # Handle
                    pygame.draw.circle(self.screen, (180, 160, 80), (sx+ts//2+m*2, sy+ts//2), m)

                elif t == WINDOW:
                    # Window with glass, frame, and daylight glow
                    wr, wg, wb = wall_col
                    pygame.draw.rect(self.screen, wall_col, (sx, sy, ts, ts))
                    # Glass pane — brighter during day
                    time_norm = getattr(player, '_time_norm', 0.5) if player else 0.5
                    if 0.22 < time_norm < 0.78:
                        glass = (150, 195, 230)  # bright daylight
                    else:
                        glass = (40, 50, 70)  # dark night
                    pygame.draw.rect(self.screen, glass, (sx+m*2, sy+m*2, ts-4*m, ts-4*m))
                    pygame.draw.rect(self.screen, (max(0,wr-10), max(0,wg-10), max(0,wb-8)),
                                    (sx+m*2, sy+m*2, ts-4*m, ts-4*m), 2)
                    # Cross bars
                    frame = (max(0,wr-5), max(0,wg-5), max(0,wb-3))
                    pygame.draw.line(self.screen, frame, (sx+ts//2,sy+m*2), (sx+ts//2,sy+ts-m*2), 2)
                    pygame.draw.line(self.screen, frame, (sx+m*2,sy+ts//2), (sx+ts-m*2,sy+ts//2), 2)
                    # Light pool on floor below window (during day)
                    if 0.22 < time_norm < 0.78:
                        glow = pygame.Surface((ts, ts//2), pygame.SRCALPHA)
                        glow.fill((255, 240, 200, 20))
                        self.screen.blit(glow, (sx, sy+ts))

                elif t == TABLE:
                    # Rectangular wooden table with items on it
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    # Table legs (shadow)
                    for lx, ly in [(m+2, m+2), (ts-m-4, m+2), (m+2, ts-m-4), (ts-m-4, ts-m-4)]:
                        pygame.draw.rect(self.screen, (90, 65, 35), (sx+lx, sy+ly, 3, 3))
                    # Table top (larger, overlapping legs)
                    tx, ty = sx+m-1, sy+m+1
                    tw, th = ts-2*m+2, ts-2*m-2
                    pygame.draw.rect(self.screen, (145, 110, 65), (tx, ty, tw, th))
                    pygame.draw.rect(self.screen, (115, 85, 48), (tx, ty, tw, th), 2)
                    # Wood grain
                    for gy in range(ty+3, ty+th-2, 4):
                        pygame.draw.line(self.screen, (130, 98, 55), (tx+2, gy), (tx+tw-2, gy))
                    # Items on table: plate and cup
                    pygame.draw.circle(self.screen, (190, 185, 175), (sx+ts//2-m, sy+ts//2), m)
                    pygame.draw.circle(self.screen, (170, 165, 155), (sx+ts//2-m, sy+ts//2), m, 1)
                    pygame.draw.rect(self.screen, (140, 100, 60), (sx+ts//2+m, sy+ts//2-2, 4, 6))

                elif t == BED:
                    # Rectangular bed with headboard, pillow and patterned blanket
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    # Bed frame — wider than tall (rectangular)
                    bx2, by2 = sx+m-2, sy+m+2
                    bw2, bh2 = ts-2*m+4, ts-2*m-2
                    pygame.draw.rect(self.screen, (85, 58, 35), (bx2, by2, bw2, bh2))
                    pygame.draw.rect(self.screen, (70, 45, 25), (bx2, by2, bw2, bh2), 2)
                    # Headboard (darker, at top)
                    pygame.draw.rect(self.screen, (75, 50, 30), (bx2, by2, bw2, 5))
                    # Mattress
                    pygame.draw.rect(self.screen, (170, 145, 115), (bx2+3, by2+6, bw2-6, bh2-9))
                    # Pillow (white/cream, at headboard end)
                    pygame.draw.rect(self.screen, (210, 205, 195), (bx2+5, by2+7, bw2//3, m*2))
                    pygame.draw.rect(self.screen, (190, 185, 175), (bx2+5, by2+7, bw2//3, m*2), 1)
                    # Blanket (colored, covers lower 2/3)
                    blanket_y = by2 + 6 + m*2 + 2
                    blanket_h = bh2 - 9 - m*2 - 2
                    pygame.draw.rect(self.screen, (120, 55, 45), (bx2+3, blanket_y, bw2-6, blanket_h))
                    # Blanket pattern lines
                    for py2 in range(blanket_y+3, blanket_y+blanket_h-1, 5):
                        pygame.draw.line(self.screen, (140, 70, 55), (bx2+5, py2), (bx2+bw2-5, py2))

                elif t == CHEST:
                    # Detailed treasure chest with rounded lid
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    cx2, cy2 = sx+m+2, sy+m+4
                    cw2, ch2 = ts-2*m-4, ts-2*m-6
                    # Body
                    pygame.draw.rect(self.screen, (155, 125, 45), (cx2, cy2+ch2//3, cw2, ch2*2//3))
                    # Lid (rounded top)
                    pygame.draw.ellipse(self.screen, (165, 135, 50), (cx2, cy2, cw2, ch2*2//3))
                    # Outline
                    pygame.draw.rect(self.screen, (110, 85, 25), (cx2, cy2+ch2//3, cw2, ch2*2//3), 2)
                    pygame.draw.ellipse(self.screen, (110, 85, 25), (cx2, cy2, cw2, ch2*2//3), 2)
                    # Metal bands
                    band_col = (180, 175, 110)
                    pygame.draw.rect(self.screen, band_col, (cx2, cy2+ch2//2, cw2, 3))
                    pygame.draw.rect(self.screen, band_col, (cx2+cw2//3, cy2+ch2//4, 3, ch2//2))
                    pygame.draw.rect(self.screen, band_col, (cx2+cw2*2//3, cy2+ch2//4, 3, ch2//2))
                    # Lock (centered, prominent)
                    pygame.draw.circle(self.screen, (200, 190, 80), (sx+ts//2, cy2+ch2//2+1), m)
                    pygame.draw.circle(self.screen, (160, 150, 50), (sx+ts//2, cy2+ch2//2+1), m, 1)

                elif t == STAIRS_UP:
                    pygame.draw.rect(self.screen, (150, 140, 125), (sx, sy, ts, ts))
                    # Steps
                    for step in range(4):
                        sy2 = sy + ts - (step+1) * ts//4
                        shade = 130 + step * 15
                        pygame.draw.rect(self.screen, (shade, shade-10, shade-20),
                                        (sx+m, sy2, ts-2*m, ts//4))
                    # Arrow
                    pts = [(sx+ts//2, sy+m), (sx+m*2, sy+ts//2), (sx+ts-m*2, sy+ts//2)]
                    pygame.draw.polygon(self.screen, (220, 220, 200), pts)

                elif t == STAIRS_DOWN:
                    pygame.draw.rect(self.screen, (100, 90, 80), (sx, sy, ts, ts))
                    for step in range(4):
                        sy2 = sy + step * ts//4
                        shade = 110 - step * 10
                        pygame.draw.rect(self.screen, (shade, shade-8, shade-15),
                                        (sx+m, sy2, ts-2*m, ts//4))
                    pts = [(sx+ts//2, sy+ts-m), (sx+m*2, sy+ts//2), (sx+ts-m*2, sy+ts//2)]
                    pygame.draw.polygon(self.screen, (170, 170, 155), pts)

                elif t == FIREPLACE:
                    pygame.draw.rect(self.screen, (80, 70, 60), (sx, sy, ts, ts))  # stone surround
                    pygame.draw.rect(self.screen, (40, 20, 10), (sx+m*2, sy+m*2, ts-4*m, ts-4*m))  # firebox
                    # Flames
                    pygame.draw.polygon(self.screen, (220, 140, 20),
                        [(sx+ts//3, sy+ts-m*2), (sx+ts//2, sy+m*3), (sx+2*ts//3, sy+ts-m*2)])
                    pygame.draw.polygon(self.screen, (240, 200, 40),
                        [(sx+ts//3+m, sy+ts-m*2), (sx+ts//2, sy+m*4), (sx+2*ts//3-m, sy+ts-m*2)])

                elif t == PILLAR:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))  # floor
                    pygame.draw.circle(self.screen, (170, 165, 155), (sx+ts//2, sy+ts//2), ts//3)
                    pygame.draw.circle(self.screen, (150, 145, 135), (sx+ts//2, sy+ts//2), ts//3, 2)

                elif t == ALTAR:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (200, 195, 180), (sx+m, sy+m*2, ts-2*m, ts-3*m))
                    pygame.draw.rect(self.screen, (170, 160, 145), (sx+m, sy+m*2, ts-2*m, ts-3*m), 2)
                    # Candles
                    pygame.draw.rect(self.screen, (240, 230, 180), (sx+m*2, sy+m, 3, m*2))
                    pygame.draw.rect(self.screen, (240, 230, 180), (sx+ts-m*2-3, sy+m, 3, m*2))

                elif t == THRONE:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (160, 130, 40), (sx+m, sy+m, ts-2*m, ts-2*m))
                    pygame.draw.rect(self.screen, (200, 170, 50), (sx+m+2, sy+m+2, ts-2*m-4, ts//2))
                    pygame.draw.rect(self.screen, (130, 100, 30), (sx+m, sy+m, ts-2*m, ts-2*m), 2)

                elif t == BOOKSHELF:
                    pygame.draw.rect(self.screen, (90, 65, 38), (sx+m, sy, ts-2*m, ts))
                    # Book spines
                    colors = [(140,40,40),(40,80,140),(40,120,60),(140,120,40),(100,50,120)]
                    bw = max(3, (ts-2*m-4) // 5)
                    for i, c in enumerate(colors):
                        pygame.draw.rect(self.screen, c, (sx+m+2+i*bw, sy+2, bw-1, ts//3-2))
                        pygame.draw.rect(self.screen, c, (sx+m+2+i*bw, sy+ts//3+2, bw-1, ts//3-2))

                elif t == BARREL:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    pygame.draw.ellipse(self.screen, (120, 85, 45), (sx+m, sy+m, ts-2*m, ts-2*m))
                    pygame.draw.ellipse(self.screen, (100, 70, 35), (sx+m, sy+m, ts-2*m, ts-2*m), 2)
                    # Bands
                    pygame.draw.ellipse(self.screen, (80, 80, 90), (sx+m+2, sy+ts//3, ts-2*m-4, ts//6), 2)

                elif t == FOUNTAIN:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    pygame.draw.circle(self.screen, (80, 140, 190), (sx+ts//2, sy+ts//2), ts//3)
                    pygame.draw.circle(self.screen, (60, 110, 160), (sx+ts//2, sy+ts//2), ts//3, 2)
                    pygame.draw.circle(self.screen, (120, 180, 220), (sx+ts//2, sy+ts//2), ts//6)

                elif t == CARPET:
                    pygame.draw.rect(self.screen, (140, 45, 45), (sx+2, sy+2, ts-4, ts-4))
                    pygame.draw.rect(self.screen, (160, 60, 40), (sx+2, sy+2, ts-4, ts-4), 1)
                    # Pattern
                    pygame.draw.rect(self.screen, (170, 80, 50), (sx+m*2, sy+m*2, ts-4*m, ts-4*m), 1)

                elif t == MOSAIC:
                    pygame.draw.rect(self.screen, (160, 145, 105), (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (145, 130, 95), (sx, sy, ts//2, ts//2))
                    pygame.draw.rect(self.screen, (145, 130, 95), (sx+ts//2, sy+ts//2, ts//2, ts//2))
                    pygame.draw.rect(self.screen, (130, 118, 88), (sx, sy, ts, ts), 1)

                elif t == ANVIL:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (90, 90, 100), (sx+m, sy+ts//3, ts-2*m, ts//2))
                    pygame.draw.rect(self.screen, (110, 110, 120), (sx+m-2, sy+ts//3-2, ts-2*m+4, m*2))

                elif t == FORGE_FIRE:
                    pygame.draw.rect(self.screen, (60, 50, 45), (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (30, 15, 10), (sx+m, sy+m, ts-2*m, ts-2*m))
                    # Hot coals
                    pygame.draw.ellipse(self.screen, (200, 80, 20), (sx+m+2, sy+ts//3, ts-2*m-4, ts//3))
                    pygame.draw.ellipse(self.screen, (240, 160, 30), (sx+ts//3, sy+ts//3+2, ts//3, ts//4))

                elif t == ARCHWAY:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))  # floor
                    # Arch pillars on sides
                    pygame.draw.rect(self.screen, (140, 130, 115), (sx, sy, m*2, ts))
                    pygame.draw.rect(self.screen, (140, 130, 115), (sx+ts-m*2, sy, m*2, ts))
                    # Arch top
                    pygame.draw.arc(self.screen, (140, 130, 115), (sx, sy-ts//3, ts, ts), 0, 3.14, 3)

                elif t == IRON_GATE:
                    pygame.draw.rect(self.screen, (60, 60, 70), (sx, sy, ts, ts))
                    # Bars
                    for gx in range(sx+m, sx+ts-m, m*2):
                        pygame.draw.line(self.screen, (90, 90, 100), (gx, sy+2), (gx, sy+ts-2), 2)
                    pygame.draw.line(self.screen, (80, 80, 90), (sx+2, sy+ts//3), (sx+ts-2, sy+ts//3), 2)
                    pygame.draw.line(self.screen, (80, 80, 90), (sx+2, sy+2*ts//3), (sx+ts-2, sy+2*ts//3), 2)

                elif t == LOCKED_DOOR:
                    pygame.draw.rect(self.screen, floor_col, (sx, sy, ts, ts))
                    pygame.draw.rect(self.screen, (100, 70, 35), (sx+m, sy+m, ts-2*m, ts-2*m))
                    pygame.draw.rect(self.screen, (80, 55, 25), (sx+m, sy+m, ts-2*m, ts-2*m), 2)
                    pygame.draw.line(self.screen, (75, 50, 25), (sx+ts//2, sy+m), (sx+ts//2, sy+ts-m), 2)
                    # Lock icon
                    pygame.draw.circle(self.screen, (200, 180, 60), (sx+ts//2+m, sy+ts//2), m+1)
                    pygame.draw.circle(self.screen, (160, 140, 40), (sx+ts//2+m, sy+ts//2), m+1, 2)

        # Lighting effects — warm glow around fireplaces, forges, and candles
        light_sources = []
        for y in range(interior.height):
            for x in range(interior.width):
                t = interior.tiles[y][x]
                if t == FIREPLACE:
                    light_sources.append((x, y, (255, 160, 60), 5))
                elif t == FORGE_FIRE:
                    light_sources.append((x, y, (255, 120, 40), 4))
                elif t == ALTAR:
                    light_sources.append((x, y, (180, 180, 255), 3))
                elif t == FOUNTAIN:
                    light_sources.append((x, y, (100, 160, 220), 2))

        for lx, ly, color, radius in light_sources:
            lsx = int(lx * ts - cam_x) + ts // 2
            lsy = int(ly * ts - cam_y) + ts // 2
            glow_r = ts * radius
            glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            # Radial gradient glow
            for ring in range(glow_r, 0, -2):
                alpha = int(25 * (ring / glow_r))
                pygame.draw.circle(glow, (color[0], color[1], color[2], alpha),
                                   (glow_r, glow_r), ring)
            self.screen.blit(glow, (lsx - glow_r, lsy - glow_r))

        # Draw NPCs inside this building
        if hasattr(player, 'interior_state'):
            world_mgr = None
            # Try to find world_mgr via game reference (stored during interact)
            for attr in ('_game_ref',):
                pass  # not available here, use interior.npcs_inside
            # Draw any NPCs with interior positions
            npc_font = self.font_sm
            all_npcs = getattr(interior, '_cached_npcs', [])
            for npc in all_npcs:
                npc_ix = getattr(npc, '_interior_x', -1)
                npc_iy = getattr(npc, '_interior_y', -1)
                if npc_ix < 0 or npc_iy < 0:
                    continue
                npx = int(npc_ix * ts - cam_x)
                npy = int(npc_iy * ts - cam_y)
                if npx < -ts or npx > SCREEN_WIDTH or npy < -ts or npy > SCREEN_HEIGHT:
                    continue

                color = getattr(npc, 'color', (140, 140, 160))
                activity = getattr(npc, '_interior_activity', 'idle')
                nr = ts // 2 - m - 1

                if activity == "sleeping":
                    # Draw NPC lying down (horizontal ellipse)
                    pygame.draw.ellipse(self.screen, (30, 25, 20, 60),
                                       (npx + m, npy + ts // 2 + 2, ts - 2 * m, m * 2))
                    pygame.draw.ellipse(self.screen, color,
                                       (npx + m + 2, npy + ts // 3, ts - 2 * m - 4, ts // 3))
                    # Head to the side
                    head_col = (min(255, color[0] + 25), min(255, color[1] + 20),
                                min(255, color[2] + 10))
                    pygame.draw.circle(self.screen, head_col,
                                       (npx + m + nr // 2, npy + ts // 3 + 2), nr // 3 + 1)
                    # Zzz
                    z_surf = npc_font.render("zzz", True, (180, 180, 220))
                    self.screen.blit(z_surf, (npx + ts // 2 + 4, npy + ts // 4 - 8))
                else:
                    # Standing NPC with shadow
                    pygame.draw.ellipse(self.screen, (30, 25, 20, 80),
                                       (npx + m + 2, npy + ts - m * 2, ts - 2 * m - 4, m * 2))
                    pygame.draw.circle(self.screen, color, (npx + ts // 2, npy + ts // 2), nr)
                    pygame.draw.circle(self.screen, (max(0, color[0] - 20), max(0, color[1] - 20),
                                                      max(0, color[2] - 15)),
                                       (npx + ts // 2, npy + ts // 2), nr, 2)
                    # Head
                    head_col = (min(255, color[0] + 25), min(255, color[1] + 20),
                                min(255, color[2] + 10))
                    pygame.draw.circle(self.screen, head_col,
                                       (npx + ts // 2, npy + ts // 4), nr // 2 + 1)

                # Activity icon above head
                icon_y = npy - 6
                if activity in ("cooking", "eating"):
                    # Plate icon
                    pygame.draw.circle(self.screen, (200, 180, 140), (npx + ts // 2, icon_y), 4)
                    pygame.draw.circle(self.screen, (170, 150, 110), (npx + ts // 2, icon_y), 4, 1)
                elif activity in ("reading", "studying"):
                    # Book icon
                    pygame.draw.rect(self.screen, (100, 60, 40), (npx + ts // 2 - 4, icon_y - 3, 8, 6))
                elif activity in ("working", "smithing"):
                    # Hammer icon
                    pygame.draw.line(self.screen, (180, 180, 190),
                                    (npx + ts // 2 - 2, icon_y - 3),
                                    (npx + ts // 2 + 3, icon_y + 2), 2)
                elif activity in ("talking", "sitting"):
                    # Speech bubble
                    pygame.draw.ellipse(self.screen, WHITE,
                                       (npx + ts // 2 - 4, icon_y - 4, 8, 6))

                # Name label
                name_surf = npc_font.render(npc.name, True, WHITE)
                self.screen.blit(name_surf, (npx + ts // 2 - name_surf.get_width() // 2,
                                              npy - 14))

        # Draw player
        px = int(ix * ts - cam_x)
        py = int(iy * ts - cam_y)
        # Shadow
        pygame.draw.ellipse(self.screen, (30, 25, 20, 100),
                           (px + m, py + ts - m*2, ts - 2*m, m*2))
        # Body
        body_r = ts//2 - m
        pygame.draw.circle(self.screen, (70, 170, 70), (px + ts//2, py + ts//2), body_r)
        pygame.draw.circle(self.screen, (50, 130, 50), (px + ts//2, py + ts//2), body_r, 2)
        # Direction indicator
        fx, fy = getattr(player, 'facing', (0, -1))
        dx_f = int(fx * body_r * 0.6)
        dy_f = int(fy * body_r * 0.6)
        pygame.draw.circle(self.screen, (180, 240, 180), (px + ts//2 + dx_f, py + ts//2 + dy_f), m)

        # Header
        name = interior.building_name
        floor_str = ""
        if interior.floor_num < 0:
            floor_str = f" (Basement {abs(interior.floor_num)})"
        elif interior.floor_num > 0:
            floor_str = f" (Floor {interior.floor_num + 1})"
        label = self.font_lg.render(f"Inside: {name}{floor_str}", True, (200, 200, 220))
        bg = pygame.Surface((label.get_width() + 20, 30), pygame.SRCALPHA)
        bg.fill((15, 15, 25, 210))
        self.screen.blit(bg, (SCREEN_WIDTH // 2 - label.get_width() // 2 - 10, 6))
        self.screen.blit(label, (SCREEN_WIDTH // 2 - label.get_width() // 2, 10))

        # Controls
        hint = self.font_sm.render("[E] at door: Exit  [E] on stairs: Change floor  [WASD] Move",
                                  True, (150, 150, 170))
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, SCREEN_HEIGHT - 25))

    def draw_building_doors(self, world: World, camera: Camera, player):
        """Draw door indicators on buildings so players can find entrances."""
        if not player or (hasattr(player, 'interior_state') and player.interior_state.is_inside):
            return

        # Cache exterior door positions (built from visible range, not full world)
        if not hasattr(self, '_exterior_doors'):
            self._exterior_doors = []
            self._exterior_doors_scanned = set()

        # Scan visible area for new doors
        vx0, vy0, vx1, vy1 = camera.get_visible_tile_range()
        scan_key = (vx0 // 20, vy0 // 20, vx1 // 20, vy1 // 20)
        if scan_key not in self._exterior_doors_scanned:
            self._exterior_doors_scanned.add(scan_key)
            for y in range(max(0, vy0 - 2), min(world.height, vy1 + 2)):
                for x in range(max(0, vx0 - 2), min(world.width, vx1 + 2)):
                    if world.tiles[y][x] != DOOR:
                        continue
                    if (x, y) in {(dx, dy) for dx, dy in self._exterior_doors}:
                        continue
                    has_wall = False
                    has_outside = False
                    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nx, ny = x+dx, y+dy
                        if 0 <= nx < world.width and 0 <= ny < world.height:
                            t = world.tiles[ny][nx]
                            if t == WALL: has_wall = True
                            elif t in (GRASS, ROAD, SAND, DIRT_TRACK,
                                       GRAVEL_ROAD, COBBLESTONE): has_outside = True
                    if has_wall and has_outside:
                        self._exterior_doors.append((x, y))

        # Only draw doors that are on screen
        x0, y0, x1, y1 = camera.get_visible_tile_range()
        for dx, dy in self._exterior_doors:
            if not (x0 <= dx < x1 and y0 <= dy < y1):
                continue
            sx = dx * TILE_SIZE - int(camera.x)
            sy = dy * TILE_SIZE - int(camera.y)
            pygame.draw.rect(self.screen, (160, 120, 60),
                           (sx + 2, sy + 2, TILE_SIZE - 4, TILE_SIZE - 4))
            pygame.draw.rect(self.screen, (120, 90, 40),
                           (sx + 2, sy + 2, TILE_SIZE - 4, TILE_SIZE - 4), 1)
            dist = abs(dx - player.x) + abs(dy - player.y)
            if dist < 3:
                hint = self.font_sm.render("E", True, (255, 255, 200))
                self.screen.blit(hint, (sx + 3, sy + 1))

    def draw_structures(self, world: World, camera: Camera):
        """Draw structure name labels."""
        for structure in world.structures:
            sx, sy = camera.world_to_screen(structure.x, structure.y - 1.5)
            if -100 < sx < SCREEN_WIDTH + 100 and -50 < sy < SCREEN_HEIGHT + 50:
                # Label background
                label = self.font_sm.render(structure.name, True, WHITE)
                lw, lh = label.get_size()
                bg_rect = pygame.Rect(sx - lw // 2 - 3, sy - lh // 2 - 2, lw + 6, lh + 4)
                bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
                kind_colors = {
                    "village": (40, 60, 100, 180),
                    "ruins": (100, 50, 50, 180),
                    "shrine": (80, 50, 100, 180),
                }
                bg_surf.fill(kind_colors.get(structure.kind, (40, 40, 40, 180)))
                self.screen.blit(bg_surf, bg_rect)
                self.screen.blit(label, (sx - lw // 2, sy - lh // 2))

    def draw_graves(self, graves: list, camera: Camera):
        """Draw grave markers and unburied bodies on the world map."""
        for grave in graves:
            sx, sy = camera.world_to_screen(grave.x, grave.y)
            if -20 < sx < SCREEN_WIDTH + 20 and -20 < sy < SCREEN_HEIGHT + 20:
                if not grave.buried:
                    # Unburied body: small dark mound
                    body_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                    pygame.draw.ellipse(body_surf, (80, 60, 50, 180),
                                        (2, TILE_SIZE // 2 - 2, TILE_SIZE - 4, TILE_SIZE // 2))
                    # Skull marker
                    pygame.draw.circle(body_surf, (200, 195, 185, 200),
                                        (TILE_SIZE // 2, TILE_SIZE // 2 - 3), 3)
                    self.screen.blit(body_surf, (sx, sy))
                # Flowers on visited graves
                if grave.flowers > 0 and grave.buried:
                    flower_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                    for i in range(min(grave.flowers, 3)):
                        fx = 3 + i * 4
                        fy = TILE_SIZE - 4
                        pygame.draw.circle(flower_surf, (220, 100, 120, 180),
                                            (fx, fy), 2)
                        pygame.draw.line(flower_surf, (60, 140, 50, 180),
                                          (fx, fy + 2), (fx, fy + 4))
                    self.screen.blit(flower_surf, (sx, sy))


