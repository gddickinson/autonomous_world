"""3D scene geometry builder — converts game world tiles into 3D face lists.

Used by Renderer3D to generate geometry for the OpenGL renderer.
"""

import math
from game.settings import *

# ── Face colors ──────────────────────────────────────────────────────────

TILE_3D_COLORS = {
    WATER: (45, 100, 170),
    SHALLOW_WATER: (65, 130, 185),
    SAND: (195, 180, 140),
    GRASS: (75, 135, 65),
    FOREST: (45, 100, 40),
    DENSE_FOREST: (30, 75, 28),
    MOUNTAIN: (130, 115, 95),
    SNOW: (225, 230, 235),
    ROAD: (155, 135, 100),
    GRAVEL_ROAD: (140, 130, 112),
    DIRT_TRACK: (150, 132, 100),
    COBBLESTONE: (135, 135, 140),
    FLOOR: (150, 125, 90),
    WALL: (120, 110, 95),
    DOOR: (100, 70, 40),
    SWAMP: (65, 100, 55),
    FARMLAND: (110, 135, 55),
}

WALL_COLOR_S = (150, 135, 115)
WALL_COLOR_E = (120, 110, 95)
WALL_COLOR_N = (90, 82, 72)
WALL_COLOR_W = (105, 96, 83)

ROOF_COLORS_3D = {
    "hamlet": (155, 120, 55),
    "village": (165, 80, 42),
    "town": (100, 75, 50),
    "city": (88, 92, 105),
    "castle": (72, 74, 82),
    "temple": (130, 145, 58),
}

_INTERIOR_TILES = frozenset({
    FLOOR, TABLE, BED, CHEST, STAIRS_UP, STAIRS_DOWN,
    FIREPLACE, PILLAR, ALTAR, THRONE, BOOKSHELF, BARREL,
    ANVIL, FORGE_FIRE, FOUNTAIN, CARPET, MOSAIC, ARCHWAY,
    DOOR, WINDOW,
})

_FURN_COLORS = {
    TABLE: (130, 95, 55), BED: (110, 75, 50), CHEST: (150, 120, 40),
    BOOKSHELF: (90, 65, 40), BARREL: (120, 90, 50),
}


# ── Height map builder ──────────────────────────────────────────────────

def _build_height_map(plan):
    """Build (x,y) -> (num_floors, kind) map from world plan."""
    height_map = {}
    shaped_roof = set()
    if not plan:
        return height_map, shaped_roof

    for sp in plan.settlements:
        for bld in sp.buildings:
            bx, by = bld['x'], bld['y']
            bw, bh = bld['w'], bld['h']
            bname = bld.get('name', '')
            if 'Tower' in bname or 'Keep' in bname:
                nf = 3
            elif sp.kind in ('city', 'castle'):
                nf = 2
            else:
                nf = 1
            for dy in range(bh):
                for dx in range(bw):
                    pos = (bx + dx, by + dy)
                    height_map[pos] = (nf, sp.kind)
                    shaped_roof.add(pos)

    for loc in plan.special_locations:
        if loc.kind == 'temple':
            r = loc.radius
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if dx * dx + dy * dy <= r * r:
                        pos = (loc.x + dx, loc.y + dy)
                        height_map[pos] = (1, 'temple')
                        shaped_roof.add(pos)

    return height_map, shaped_roof


# ── Underground rendering ───────────────────────────────────────────────

def _build_underground(faces, world, tx, ty, wx, wz, player_floor):
    """Add underground geometry for a tile."""
    ug_tile = world.get_underground_tile(tx, ty, player_floor)
    if ug_tile != WALL:
        ug_color = TILE_3D_COLORS.get(ug_tile, (100, 90, 75))
        v = ((tx * 3 + ty * 7) % 5) - 2
        ugc = (max(0, min(255, ug_color[0] + v)),
               max(0, min(255, ug_color[1] + v)),
               max(0, min(255, ug_color[2] + v)))
        ug_y = -1.0
        faces.append(([(wx, ug_y, wz), (wx + 1, ug_y, wz),
                        (wx + 1, ug_y, wz + 1), (wx, ug_y, wz + 1)], ugc, True))
        if ug_tile in _FURN_COLORS:
            fc = _FURN_COLORS[ug_tile]
            faces.append(([(wx+0.15, ug_y+0.3, wz+0.15), (wx+0.85, ug_y+0.3, wz+0.15),
                            (wx+0.85, ug_y+0.3, wz+0.85), (wx+0.15, ug_y+0.3, wz+0.85)],
                           fc, True))
        elif ug_tile == STAIRS_UP:
            faces.append(([(wx+0.2, ug_y, wz+0.2), (wx+0.8, ug_y, wz+0.2),
                            (wx+0.5, ug_y+0.4, wz+0.5)], (180, 170, 50), True))
    else:
        for ndx, ndz, wc in [(0, 1, WALL_COLOR_S), (0, -1, WALL_COLOR_N),
                              (1, 0, WALL_COLOR_E), (-1, 0, WALL_COLOR_W)]:
            nt = world.get_underground_tile(tx + ndx, ty + ndz, player_floor)
            if nt != WALL:
                ug_y, ug_h = -1.0, 1.2
                if ndz == 1:
                    faces.append(([(wx, ug_y, wz+1), (wx+1, ug_y, wz+1),
                                    (wx+1, ug_y+ug_h, wz+1), (wx, ug_y+ug_h, wz+1)], wc, False))
                elif ndz == -1:
                    faces.append(([(wx+1, ug_y, wz), (wx, ug_y, wz),
                                    (wx, ug_y+ug_h, wz), (wx+1, ug_y+ug_h, wz)], wc, False))
                elif ndx == 1:
                    faces.append(([(wx+1, ug_y, wz+1), (wx+1, ug_y, wz),
                                    (wx+1, ug_y+ug_h, wz), (wx+1, ug_y+ug_h, wz+1)], wc, False))
                elif ndx == -1:
                    faces.append(([(wx, ug_y, wz), (wx, ug_y, wz+1),
                                    (wx, ug_y+ug_h, wz+1), (wx, ug_y+ug_h, wz)], wc, False))


# ── Interior (player inside building) ───────────────────────────────────

def _build_interior(faces, tile, wx, wz, height_map, player_building_rect):
    """Add interior geometry when player is inside a building."""
    fh = 0.05
    floor_c = TILE_3D_COLORS.get(tile, (150, 125, 90))
    faces.append(([(wx, fh, wz), (wx+1, fh, wz),
                    (wx+1, fh, wz+1), (wx, fh, wz+1)], floor_c, True))
    if tile in _FURN_COLORS:
        furn_h = 0.2 if tile == BED else 0.3
        fc = _FURN_COLORS[tile]
        m = 0.15
        faces.append(([(wx+m, fh+furn_h, wz+m), (wx+1-m, fh+furn_h, wz+m),
                        (wx+1-m, fh+furn_h, wz+1-m), (wx+m, fh+furn_h, wz+1-m)],
                       (min(255, fc[0]+15), min(255, fc[1]+10), min(255, fc[2]+8)), True))
    if tile == WALL:
        pbx, pby, pbw, pbh = player_building_rect
        low_h = 0.4
        tx = int(wx + (pbx + pbw / 2))  # approx world coord
        ty = int(wz + (pby + pbh / 2))
        if (tx, ty + 1) not in height_map:
            faces.append(([(wx, 0, wz+1), (wx+1, 0, wz+1),
                            (wx+1, low_h, wz+1), (wx, low_h, wz+1)], (180, 170, 155), False))
    if tile == STAIRS_UP:
        faces.append(([(wx+0.2, fh, wz+0.2), (wx+0.8, fh, wz+0.2),
                        (wx+0.5, fh+0.3, wz+0.5)], (180, 170, 50), True))
    elif tile == STAIRS_DOWN:
        faces.append(([(wx+0.2, fh, wz+0.2), (wx+0.8, fh, wz+0.2),
                        (wx+0.5, fh+0.3, wz+0.5)], (170, 60, 50), True))


# ── Exterior walls ──────────────────────────────────────────────────────

def _build_exterior_walls(faces, tile, tx, ty, wx, wz, h, num_floors,
                          height_map, has_shaped_roof):
    """Add exterior wall faces, windows, doors, and flat roof cap."""
    floor_h = 1.2
    wy = 0.0

    def _in_bld(nx, ny):
        return (nx, ny) in height_map

    is_door = tile == DOOR
    door_color = (60, 40, 25)
    door_h = floor_h * 0.8

    # South
    if not _in_bld(tx, ty + 1):
        if is_door:
            faces.append(([(wx+0.15, wy, wz+1), (wx+0.85, wy, wz+1),
                            (wx+0.85, wy+door_h, wz+1), (wx+0.15, wy+door_h, wz+1)],
                           door_color, False))
            if door_h < h:
                faces.append(([(wx, wy+door_h, wz+1), (wx+1, wy+door_h, wz+1),
                                (wx+1, wy+h, wz+1), (wx, wy+h, wz+1)], WALL_COLOR_S, False))
        else:
            faces.append(([(wx, wy, wz+1), (wx+1, wy, wz+1),
                            (wx+1, wy+h, wz+1), (wx, wy+h, wz+1)], WALL_COLOR_S, False))
            if tile == WALL and (tx + ty) % 2 == 0:
                for fl in range(num_floors):
                    wy_w = fl * floor_h + floor_h * 0.3
                    wh_w = floor_h * 0.35
                    faces.append(([(wx+0.25, wy_w, wz+1.01), (wx+0.75, wy_w, wz+1.01),
                                    (wx+0.75, wy_w+wh_w, wz+1.01), (wx+0.25, wy_w+wh_w, wz+1.01)],
                                   (100, 140, 180), True))

    # North
    if not _in_bld(tx, ty - 1):
        faces.append(([(wx+1, wy, wz), (wx, wy, wz),
                        (wx, wy+h, wz), (wx+1, wy+h, wz)], WALL_COLOR_N, False))

    # East
    if not _in_bld(tx + 1, ty):
        faces.append(([(wx+1, wy, wz+1), (wx+1, wy, wz),
                        (wx+1, wy+h, wz), (wx+1, wy+h, wz+1)], WALL_COLOR_E, False))
        if tile == WALL and (tx + ty) % 2 == 1:
            for fl in range(num_floors):
                wy_w = fl * floor_h + floor_h * 0.3
                wh_w = floor_h * 0.35
                faces.append(([(wx+1.01, wy_w, wz+0.25), (wx+1.01, wy_w, wz+0.75),
                                (wx+1.01, wy_w+wh_w, wz+0.75), (wx+1.01, wy_w+wh_w, wz+0.25)],
                               (100, 140, 180), True))

    # West
    if not _in_bld(tx - 1, ty):
        faces.append(([(wx, wy, wz), (wx, wy, wz+1),
                        (wx, wy+h, wz+1), (wx, wy+h, wz)], WALL_COLOR_W, False))

    # Flat roof cap (only if no shaped roof will cover it)
    if (tx, ty) not in has_shaped_roof:
        nf_data = height_map[(tx, ty)]
        kind = nf_data[1]
        rc = ROOF_COLORS_3D.get(kind, (140, 110, 55))
        rv = ((tx * 5 + ty * 3) % 5) - 2
        roof_c = (max(0, min(255, rc[0]+rv*3)), max(0, min(255, rc[1]+rv*2)),
                  max(0, min(255, rc[2]+rv*2)))
        faces.append(([(wx, wy+h, wz), (wx+1, wy+h, wz),
                        (wx+1, wy+h, wz+1), (wx, wy+h, wz+1)], roof_c, True))


# ── Main build function ─────────────────────────────────────────────────

def build_scene(world, px, py, radius, plan=None, player_building_rect=None,
                player_floor=0):
    """Build 3D geometry for tiles around (px, py).

    Returns list of (verts_3d, color, skip_cull) tuples.
    """
    faces = []
    ix, iy = int(px), int(py)
    height_map, has_shaped_roof = _build_height_map(plan)
    floor_h = 1.2

    for ty in range(iy - radius, iy + radius + 1):
        for tx in range(ix - radius, ix + radius + 1):
            if tx < 0 or tx >= world.width or ty < 0 or ty >= world.height:
                continue
            dx = tx - px
            dy = ty - py
            if dx * dx + dy * dy > radius * radius:
                continue

            tile = world.tiles[ty][tx]
            wx = tx - px
            wz = ty - py

            # Underground mode
            if player_floor < 0 and hasattr(world, 'underground'):
                _build_underground(faces, world, tx, ty, wx, wz, player_floor)
                continue

            color = TILE_3D_COLORS.get(tile, (100, 100, 100))

            # Ground tile (non-building)
            if (tx, ty) not in height_map:
                hv = ((tx * 7 + ty * 13) % 5) * 0.02
                v = ((tx * 3 + ty * 7) % 7) - 3
                gc = (max(0, min(255, color[0]+v*2)), max(0, min(255, color[1]+v*2)),
                      max(0, min(255, color[2]+v)))
                faces.append(([(wx, hv, wz), (wx+1, hv, wz),
                                (wx+1, hv, wz+1), (wx, hv, wz+1)], gc, True))

            # Building tile
            if (tx, ty) in height_map:
                nf, kind = height_map[(tx, ty)]
                h = nf * floor_h

                in_player_bld = False
                if player_building_rect:
                    pbx, pby, pbw, pbh = player_building_rect
                    if pbx <= tx < pbx + pbw and pby <= ty < pby + pbh:
                        in_player_bld = True

                if in_player_bld:
                    _build_interior(faces, tile, wx, wz, height_map, player_building_rect)
                else:
                    _build_exterior_walls(faces, tile, tx, ty, wx, wz, h, nf,
                                          height_map, has_shaped_roof)
                continue

            # Orphaned interior tiles
            if tile in _INTERIOR_TILES:
                continue

            # Trees
            if tile in (FOREST, DENSE_FOREST):
                trunk_c = (85, 60, 35)
                m = 0.35
                th = 0.6
                faces.append(([(wx+m, 0, wz+m), (wx+1-m, 0, wz+m),
                                (wx+1-m, th, wz+m), (wx+m, th, wz+m)], trunk_c, False))
                cx_t, cz_t = wx + 0.5, wz + 0.5
                ch = 1.8 if tile == DENSE_FOREST else 1.4
                cr = 0.55
                leaf_c = (40, 95, 35) if tile == FOREST else (28, 70, 25)
                base = [(cx_t-cr, th, cz_t-cr), (cx_t+cr, th, cz_t-cr),
                         (cx_t+cr, th, cz_t+cr), (cx_t-cr, th, cz_t+cr)]
                peak = (cx_t, ch, cz_t)
                for i in range(4):
                    j = (i + 1) % 4
                    shade = [1.0, 0.85, 0.7, 0.9][i]
                    lc = (int(leaf_c[0]*shade), int(leaf_c[1]*shade), int(leaf_c[2]*shade))
                    faces.append(([base[i], base[j], peak], lc, False))

            # Water (lowered)
            elif tile == WATER and faces:
                last_verts, last_c, last_skip = faces[-1]
                faces[-1] = ([(wx, -0.1, wz), (wx+1, -0.1, wz),
                               (wx+1, -0.1, wz+1), (wx, -0.1, wz+1)], last_c, True)

    # Pitched and conical roofs (second pass)
    from game.ui.scene_3d_roofs import build_pitched_roofs, build_conical_roofs
    if plan:
        build_pitched_roofs(faces, plan, height_map, px, py, radius, floor_h)
        build_conical_roofs(faces, plan, height_map, px, py, radius, floor_h)

    return faces
