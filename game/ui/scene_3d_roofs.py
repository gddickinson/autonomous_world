"""3D pitched and conical roof geometry for scene_3d.py."""

import math
from game.ui.scene_3d import (
    WALL_COLOR_S, WALL_COLOR_N, ROOF_COLORS_3D,
)


def build_pitched_roofs(faces, plan, height_map, px, py, radius, floor_h):
    """Add pitched gable roofs for rectangular buildings."""
    for sp in plan.settlements:
        for bld in sp.buildings:
            bx, by = bld['x'], bld['y']
            bw, bh = bld['w'], bld['h']

            if abs(bx + bw / 2 - px) > radius or abs(by + bh / 2 - py) > radius:
                continue

            nf_data = height_map.get((bx + 1, by + 1))
            if not nf_data:
                continue
            num_f, kind = nf_data
            h = num_f * floor_h
            roof_rise = min(bw, bh) * 0.4

            rc = ROOF_COLORS_3D.get(kind, (140, 110, 55))

            ox_r = bx - px
            oz_r = by - py
            mid_x = ox_r + bw / 2.0

            # West slope
            faces.append(([
                (ox_r, h, oz_r), (ox_r, h, oz_r + bh),
                (mid_x, h + roof_rise, oz_r + bh), (mid_x, h + roof_rise, oz_r),
            ], (max(0, rc[0] - 15), max(0, rc[1] - 12), max(0, rc[2] - 10)), False))

            # East slope
            faces.append(([
                (ox_r + bw, h, oz_r + bh), (ox_r + bw, h, oz_r),
                (mid_x, h + roof_rise, oz_r), (mid_x, h + roof_rise, oz_r + bh),
            ], (min(255, rc[0] + 10), min(255, rc[1] + 8), min(255, rc[2] + 5)), False))

            # South gable
            faces.append(([
                (ox_r, h, oz_r + bh), (ox_r + bw, h, oz_r + bh),
                (mid_x, h + roof_rise, oz_r + bh),
            ], WALL_COLOR_S, False))

            # North gable
            faces.append(([
                (ox_r + bw, h, oz_r), (ox_r, h, oz_r),
                (mid_x, h + roof_rise, oz_r),
            ], WALL_COLOR_N, False))


def build_conical_roofs(faces, plan, height_map, px, py, radius, floor_h):
    """Add conical roofs for temple/circular buildings."""
    for loc in plan.special_locations:
        if loc.kind != 'temple':
            continue
        if abs(loc.x - px) > radius or abs(loc.y - py) > radius:
            continue
        nf_data = height_map.get((loc.x, loc.y))
        if not nf_data:
            continue
        num_f, kind = nf_data
        h = num_f * floor_h
        r = loc.radius
        cone_h = r * 0.5
        c_x = loc.x - px + 0.5
        c_z = loc.y - py + 0.5
        cone_r = r + 0.5
        rc = ROOF_COLORS_3D.get(kind, (130, 145, 58))
        peak = (c_x, h + cone_h, c_z)
        segs = 16

        for i in range(segs):
            a1 = 2 * math.pi * i / segs
            a2 = 2 * math.pi * (i + 1) / segs
            p1 = (c_x + cone_r * math.cos(a1), h, c_z + cone_r * math.sin(a1))
            p2 = (c_x + cone_r * math.cos(a2), h, c_z + cone_r * math.sin(a2))
            shade = 0.75 + 0.25 * math.sin(a1 + 0.5)
            fc = (int(rc[0] * shade), int(rc[1] * shade), int(rc[2] * shade))
            faces.append(([p1, p2, peak], fc, False))

        # Base cap
        base_pts = []
        for i in range(segs):
            a = 2 * math.pi * i / segs
            base_pts.append((c_x + cone_r * math.cos(a), h,
                              c_z + cone_r * math.sin(a)))
        faces.append((list(reversed(base_pts)), rc, True))
