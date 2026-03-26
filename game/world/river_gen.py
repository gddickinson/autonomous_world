"""River network and lake generation using D8 flow accumulation.

Produces realistic drainage networks where tributaries merge into trunk
rivers that flow to the sea.  Also identifies lakes in flat high-flow areas.

Used by terrain_gen.py and world_plan.py.
"""

import math
import numpy as np

# D8 neighbour offsets and distances (shared with terrain_gen)
_D8_NBRS = [(-1, 0), (-1, 1), (0, 1), (1, 1),
            (1, 0), (1, -1), (0, -1), (-1, -1)]
_D8_DIST = [1.0, math.sqrt(2), 1.0, math.sqrt(2),
            1.0, math.sqrt(2), 1.0, math.sqrt(2)]


# ================================================================
# FLOW DIRECTION + ACCUMULATION
# ================================================================

def compute_flow_dir(elev):
    """Compute D8 flow direction for every cell (vectorized by direction)."""
    h, w = elev.shape
    flow_dir = np.full((h, w), -1, dtype=np.int8)
    best_drop = np.full((h, w), -999.0, dtype=np.float32)

    for d_idx, (dr, dc) in enumerate(_D8_NBRS):
        sr = slice(max(0, -dr), h + min(0, -dr))
        sc = slice(max(0, -dc), w + min(0, -dc))
        nr = slice(max(0, dr), h + min(0, dr))
        nc = slice(max(0, dc), w + min(0, dc))

        drop = (elev[sr, sc] - elev[nr, nc]) / _D8_DIST[d_idx]
        mask = drop > best_drop[sr, sc]
        flow_dir[sr, sc][mask] = d_idx
        best_drop[sr, sc][mask] = drop[mask]

    return flow_dir


def compute_flow_accum(elevation_grid, sea_level, flow_dir):
    """Compute flow accumulation over land cells, high-to-low.

    Uses pre-computed destination arrays to minimize per-cell overhead.
    """
    h, w = elevation_grid.shape
    land_mask = elevation_grid > sea_level
    accum = np.ones((h, w), dtype=np.int32)
    lr, lc = np.where(land_mask)
    order = np.argsort(-elevation_grid[lr, lc])
    lr, lc = lr[order], lc[order]

    # Pre-compute D8 offset arrays for vectorized neighbor lookup
    d8_dr = np.array([d[0] for d in _D8_NBRS], dtype=np.int32)
    d8_dc = np.array([d[1] for d in _D8_NBRS], dtype=np.int32)

    # Flatten for faster indexing
    accum_flat = accum.ravel()
    fd_flat = flow_dir.ravel()

    for i in range(len(lr)):
        r, c = int(lr[i]), int(lc[i])
        d = fd_flat[r * w + c]
        if d < 0:
            continue
        nr = r + d8_dr[d]
        nc = c + d8_dc[d]
        if 0 <= nr < h and 0 <= nc < w:
            accum_flat[nr * w + nc] += accum_flat[r * w + c]
    return accum


# ================================================================
# RIVER TRACING
# ================================================================

def _trace_downstream(r, c, flow_dir, elevation_grid, accum,
                      sea_level, cache_step, river_id_grid, max_steps=3000):
    """Trace a single river path downstream to sea or grid edge.

    Returns (path, mouth_flow, joined_river_id).
    If the trace merges into an existing river, joined_river_id >= 0.
    """
    h, w = elevation_grid.shape
    path = []
    cr, cc = r, c
    joined = -1
    for _ in range(max_steps):
        if not (0 <= cr < h and 0 <= cc < w):
            break
        # If we hit a cell already claimed by another river, merge
        existing = river_id_grid[cr, cc]
        if existing >= 0 and len(path) > 0:
            path.append((cc * cache_step, cr * cache_step))
            joined = int(existing)
            break
        path.append((cc * cache_step, cr * cache_step))
        river_id_grid[cr, cc] = -2  # mark as "being traced"
        if elevation_grid[cr, cc] <= sea_level:
            break
        d = flow_dir[cr, cc]
        if d < 0:
            break
        dr, dc = _D8_NBRS[d]
        cr, cc = cr + dr, cc + dc
    mouth_flow = int(accum[r, c])
    return path, mouth_flow, joined


def compute_rivers(elevation_grid, sea_level=0.22,
                   accum_threshold=100, cache_step=10):
    """Compute realistic river network with tributaries merging into trunks.

    Strategy:
    1. Compute D8 flow direction and accumulation.
    2. Find all cells above accum_threshold on land.
    3. Sort sources by accumulation DESCENDING — trace biggest rivers first.
    4. Each trace follows flow downhill to the sea (or grid edge).
    5. When a trace hits a cell already owned by another river, it JOINS
       (tributary merge) rather than stopping.
    6. Track per-river max flow for rendering width hierarchy.
    7. Filter out very short rivers (< 8 points).

    Returns list of dicts: {points, mouth, flow, rank, joined}.
      rank: 'major' (flow >= 500), 'medium' (200-500), 'stream' (< 200).
    """
    h, w = elevation_grid.shape
    land_mask = elevation_grid > sea_level
    flow_dir = compute_flow_dir(elevation_grid)
    accum = compute_flow_accum(elevation_grid, sea_level, flow_dir)

    src_r, src_c = np.where(land_mask & (accum >= accum_threshold))
    if len(src_r) == 0:
        return []

    # Sort by accumulation descending — biggest rivers traced first
    src_accum = accum[src_r, src_c]
    order = np.argsort(-src_accum)
    src_r, src_c = src_r[order], src_c[order]

    # Cap candidate sources for very large grids
    max_sources = 400
    if len(src_r) > max_sources:
        src_r, src_c = src_r[:max_sources], src_c[:max_sources]

    # river_id_grid: -1 = unclaimed, >= 0 = river index
    river_id_grid = np.full((h, w), -1, dtype=np.int32)
    rivers = []

    for si in range(len(src_r)):
        r, c = int(src_r[si]), int(src_c[si])
        if river_id_grid[r, c] >= 0:
            continue  # already part of an existing river

        path, mouth_flow, joined = _trace_downstream(
            r, c, flow_dir, elevation_grid, accum,
            sea_level, cache_step, river_id_grid)

        if len(path) < 4:
            continue

        rid = len(rivers)
        # Stamp this river's id onto the grid
        for px, py in path:
            gr, gc = py // cache_step, px // cache_step
            if 0 <= gr < h and 0 <= gc < w:
                river_id_grid[gr, gc] = rid

        # Max flow along the path for rendering
        max_flow = int(accum[r, c])
        mouth_r = path[-1][1] // cache_step
        mouth_c = path[-1][0] // cache_step
        if 0 <= mouth_r < h and 0 <= mouth_c < w:
            max_flow = max(max_flow, int(accum[mouth_r, mouth_c]))

        # Classify rank
        if max_flow >= 500:
            rank = "major"
        elif max_flow >= 200:
            rank = "medium"
        else:
            rank = "stream"

        rivers.append({
            "points": path,
            "mouth": path[-1],
            "flow": max_flow,
            "rank": rank,
            "joined": joined,
        })

    # Filter very short streams and low-flow streams at startup
    # (small streams can be added lazily during chunk generation)
    rivers = [rv for rv in rivers
              if (len(rv["points"]) >= 8 or rv["joined"] >= 0)
              and rv["flow"] >= 30]

    # Sort: major first, then medium, then streams
    rank_order = {"major": 0, "medium": 1, "stream": 2}
    rivers.sort(key=lambda rv: (rank_order.get(rv["rank"], 3), -rv["flow"]))

    # Erode coastline at river mouths
    _erode_river_mouths(elevation_grid, rivers, sea_level, cache_step)

    return rivers


def _erode_river_mouths(elevation_grid, rivers, sea_level, cache_step):
    """Lower terrain around river mouths to create estuaries."""
    h, w = elevation_grid.shape
    for rv in rivers:
        mouth = rv.get("mouth")
        flow = rv.get("flow", 0)
        if mouth is None or flow < 100:
            continue
        mx, my = int(mouth[0] / cache_step), int(mouth[1] / cache_step)
        radius = min(8, max(2, int(math.log2(max(1, flow)))))
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx, ny = mx + dx, my + dy
                if 0 <= ny < h and 0 <= nx < w:
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist <= radius:
                        erosion = (1.0 - dist / radius) * 0.08
                        elevation_grid[ny, nx] = max(
                            sea_level - 0.02,
                            elevation_grid[ny, nx] - erosion)


# ================================================================
# LAKE DETECTION
# ================================================================

def compute_lakes(elevation_grid, accum, flow_dir, sea_level=0.22,
                  cache_step=10, min_lake_cells=4, slope_threshold=0.003):
    """Identify lake locations where high flow meets very gentle slope.

    Flood-fills from seed cells (high accum + nearly flat downstream)
    to find contiguous flat-bottomed areas that would pool water.

    Returns list of dicts: {center, cells, radius}.
    """
    h, w = elevation_grid.shape
    land_mask = elevation_grid > sea_level
    lakes = []
    visited = np.zeros((h, w), dtype=np.bool_)

    for r in range(1, h - 1):
        for c in range(1, w - 1):
            if visited[r, c] or not land_mask[r, c]:
                continue
            if accum[r, c] < 200:
                continue
            d = flow_dir[r, c]
            if d < 0:
                continue
            dr, dc = _D8_NBRS[d]
            nr, nc = r + dr, c + dc
            if not (0 <= nr < h and 0 <= nc < w):
                continue
            slope = abs(elevation_grid[r, c] - elevation_grid[nr, nc])
            if slope > slope_threshold:
                continue
            # Flood-fill to find lake extent
            base_elev = float(elevation_grid[r, c])
            lake_cells = []
            stack = [(r, c)]
            while stack:
                cr, cc = stack.pop()
                if visited[cr, cc]:
                    continue
                if not (0 <= cr < h and 0 <= cc < w):
                    continue
                if not land_mask[cr, cc]:
                    continue
                if abs(elevation_grid[cr, cc] - base_elev) > 0.008:
                    continue
                visited[cr, cc] = True
                lake_cells.append((cc * cache_step, cr * cache_step))
                if len(lake_cells) > 80:
                    break  # cap lake size
                for ddr, ddc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    stack.append((cr + ddr, cc + ddc))
            if len(lake_cells) >= min_lake_cells:
                xs = [p[0] for p in lake_cells]
                ys = [p[1] for p in lake_cells]
                cx = sum(xs) // len(xs)
                cy = sum(ys) // len(ys)
                radius = max(
                    max(abs(x - cx) for x in xs),
                    max(abs(y - cy) for y in ys)
                ) + cache_step
                lakes.append({
                    "center": (cx, cy),
                    "cells": lake_cells,
                    "radius": radius,
                })
    return lakes
