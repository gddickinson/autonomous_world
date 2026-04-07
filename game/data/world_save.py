"""Save / load complete world state to a JSON file.

Stores world plan metadata, settlement state, kingdom state,
NPC roster summary, player state, game time, world events,
and modified tiles. On load, the world is regenerated from the
saved seed (deterministic), then saved modifications are applied.
"""

import json
import os
import time as _time
from datetime import datetime
from typing import Any, Dict, List, Optional

WORLDS_DIR = "data/worlds"
LAST_PLAYED_PATH = os.path.join(WORLDS_DIR, "last_played.json")


def _ensure_worlds_dir():
    os.makedirs(WORLDS_DIR, exist_ok=True)


def _world_save_path(seed: int) -> str:
    return os.path.join(WORLDS_DIR, f"world_{seed}.json")


def _collect_world_plan(world) -> Dict[str, Any]:
    """Extract world plan metadata (seed, size, styles)."""
    cfg = {}
    try:
        from game.config import GameConfig
        cfg = GameConfig().values
    except Exception:
        pass
    return {
        "seed": world.seed, "width": world.width, "height": world.height,
        "terrain_style": cfg.get("terrain_style", "volcanic"),
        "settlement_style": cfg.get("settlement_style", "voronoi"),
        "world_gen_mode": cfg.get("world_gen_mode", "simulated"),
        "history_years": cfg.get("history_years", 500),
    }


def _collect_settlements(world) -> List[Dict[str, Any]]:
    """Snapshot current settlement data from world structures."""
    settlements = []
    for s in getattr(world, "structures", []):
        if s.kind not in ("hamlet", "village", "town", "city", "castle"):
            continue
        settlements.append({
            "name": s.name, "kind": s.kind, "x": s.x, "y": s.y,
            "radius": s.radius, "buildings_count": len(s.buildings),
        })
    return settlements


def _collect_kingdoms(game) -> List[Dict[str, Any]]:
    """Snapshot kingdom data from the governance system."""
    sim = getattr(game, "simulation", None)
    gov = getattr(sim, "governance", None) if sim else None
    if not gov:
        return []
    kingdoms = []
    for name, k in getattr(gov, "kingdoms", {}).items():
        kingdoms.append({
            "name": name,
            "ruler_name": getattr(k, "ruler_name", ""),
            "treasury": getattr(k, "treasury", 0),
            "tax_rate": getattr(k, "tax_rate", 0.10),
            "army_size": getattr(k, "army_size", 0),
            "population": getattr(k, "population", 0),
            "public_morale": getattr(k, "public_morale", 50),
            "governing_style": getattr(k, "governing_style", "feudalism"),
            "corruption": getattr(k, "corruption", 0.0),
            "law_enforcement": getattr(k, "law_enforcement", 0.7),
            "active_law": getattr(k, "active_law", "normal_tax"),
            "settlements": list(getattr(k, "settlements", [])),
            "castle_x": getattr(k, "castle_x", 0),
            "castle_y": getattr(k, "castle_y", 0),
        })
    return kingdoms


def _collect_npc_summary(game) -> Dict[str, Any]:
    """NPC roster with names, professions, and positions."""
    per_settlement: Dict[str, int] = {}
    roster = []
    # Plan roster is the authoritative source (covers all NPCs)
    plan = getattr(game, "world", None)
    plan = getattr(plan, "plan", None) if plan else None
    if plan and hasattr(plan, "npc_roster") and plan.npc_roster:
        roster = list(plan.npc_roster)
    # Also count spawned NPCs per settlement
    wm = getattr(game, "world_mgr", None)
    if wm:
        for npc in getattr(wm, "npcs", []):
            sname = getattr(npc, "home_settlement", "") or "wilderness"
            per_settlement[sname] = per_settlement.get(sname, 0) + 1
    return {"total": len(roster), "per_settlement": per_settlement, "roster": roster}


def _collect_player(player, game=None) -> Dict[str, Any]:
    """Full player state snapshot."""
    inv = [item.name if item else None for item in getattr(player, "inventory", [])]
    # If in divine realm, save the mortal world position instead
    px, py = float(player.x), float(player.y)
    dr = getattr(game, 'divine_realm', None) if game else None
    if dr and dr.in_divine_realm and dr.mortal_position:
        px, py = float(dr.mortal_position[0]), float(dr.mortal_position[1])
    # Sanity check — coordinates should be in mortal world range
    world = getattr(game, 'world', None) if game else None
    if world and (px < 10 or py < 10 or px > world.width - 10 or py > world.height - 10):
        # Player is at edge/ocean — use spawn point instead
        sp = getattr(world, 'spawn_point', (world.width // 2, world.height // 2))
        px, py = float(sp[0]), float(sp[1])
    return {
        "x": px, "y": py,
        "current_floor": getattr(player, "current_floor", 0),
        "hp": player.hp, "max_hp": player.max_hp,
        "energy": getattr(player, "energy", 100),
        "max_energy": getattr(player, "max_energy", 100),
        "xp": player.xp, "level": player.level,
        "xp_to_next": player.xp_to_next, "gold": player.gold,
        "attack_damage": player.attack_damage, "defense": player.defense,
        "kills": player.kills, "quests_completed": player.quests_completed,
        "steps": player.steps, "name": player.name,
        "char_class": getattr(player, "char_class", "Fighter"),
        "race": getattr(player, "race", "Human"),
        "mode": getattr(player, "mode", "mortal"),
        "was_in_divine_realm": bool(dr and dr.in_divine_realm),
        "inventory": inv,
        "equipped_weapon": (player.equipped_weapon.name
                           if player.equipped_weapon else None),
        "equipped_armor": (player.equipped_armor.name
                          if player.equipped_armor else None),
    }


def _collect_time(game) -> Dict[str, Any]:
    """Snapshot time system state."""
    ts = getattr(game, "time_sys", None)
    if not ts:
        return {"day": 1, "time": 0.0}
    return {
        "day": ts.day, "time": ts.time, "season": ts.season,
        "year": ts.year, "normalized": ts.normalized,
    }


def _collect_events(game) -> Dict[str, Any]:
    """Active events and recent chronicle history (last 50)."""
    result: Dict[str, Any] = {"active_events": [], "history": []}
    chron = getattr(game, "chronicles", None)
    if chron:
        for entry in getattr(chron, "entries", [])[-50:]:
            result["history"].append({
                "day": getattr(entry, "game_day", 0),
                "category": getattr(entry, "category", ""),
                "title": getattr(entry, "title", ""),
                "description": getattr(entry, "description", ""),
                "importance": getattr(entry, "importance", 1),
            })
    sim = getattr(game, "simulation", None)
    if sim:
        try:
            for ev in sim.get_event_log()[-20:]:
                result["active_events"].append(str(ev) if not isinstance(ev, str) else ev)
        except Exception:
            pass
    return result


def _collect_modified_tiles(world) -> Dict[str, int]:
    """Tiles changed from generation, stored as sparse dict "x,y" -> tile_type."""
    tiles_obj = getattr(world, "tiles", None)
    if not tiles_obj:
        return {}
    modified: Dict[str, int] = {}
    dirty_chunks = getattr(tiles_obj, "_dirty_chunks", set())
    if not dirty_chunks:
        return {}
    chunk_data = getattr(tiles_obj, "_chunks", {})
    for ckey in dirty_chunks:
        chunk = chunk_data.get(ckey)
        if chunk is None:
            continue
        mods = getattr(chunk, "_modified", None)
        if mods:
            for (x, y), tile_type in mods.items():
                modified[f"{x},{y}"] = int(tile_type)
    return modified


def _get_playtime(game) -> float:
    start = getattr(game, "_start_time", None)
    return (_time.time() - start) if start else 0.0


# ===================================================================
# PUBLIC API
# ===================================================================

def save_world_state(game, path: str = None) -> str:
    """Save complete game state. Returns the save path."""
    _ensure_worlds_dir()
    world = game.world
    seed = world.seed
    if path is None:
        path = _world_save_path(seed)

    data: Dict[str, Any] = {
        "version": 2,
        "save_date": datetime.now().isoformat(),
        "playtime_seconds": _get_playtime(game),
        "world_plan": _collect_world_plan(world),
        "settlements": _collect_settlements(world),
        "kingdoms": _collect_kingdoms(game),
        "npc_summary": _collect_npc_summary(game),
        "player": _collect_player(game.player, game),
        "game_time": _collect_time(game),
        "events": _collect_events(game),
        "modified_tiles": _collect_modified_tiles(world),
    }

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp_path, path)
    _write_last_played(seed, path)
    return path


def load_world_state(path: str) -> Optional[Dict[str, Any]]:
    """Load a saved world state. Returns dict with all data, or None."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def list_saved_worlds() -> List[Dict[str, Any]]:
    """List all saved worlds with metadata, sorted by date descending."""
    _ensure_worlds_dir()
    results: List[Dict[str, Any]] = []
    for fname in os.listdir(WORLDS_DIR):
        if not fname.startswith("world_") or not fname.endswith(".json"):
            continue
        fpath = os.path.join(WORLDS_DIR, fname)
        try:
            with open(fpath, "r") as f:
                data = json.load(f)
            wp = data.get("world_plan", {})
            pl = data.get("player", {})
            gt = data.get("game_time", {})
            results.append({
                "path": fpath, "seed": wp.get("seed", 0),
                "width": wp.get("width", 0), "height": wp.get("height", 0),
                "save_date": data.get("save_date", ""),
                "playtime_seconds": data.get("playtime_seconds", 0),
                "player_name": pl.get("name", "Unknown"),
                "player_level": pl.get("level", 1),
                "player_class": pl.get("char_class", ""),
                "day": gt.get("day", 1), "season": gt.get("season", ""),
                "settlement_count": len(data.get("settlements", [])),
            })
        except (json.JSONDecodeError, OSError, KeyError):
            continue
    results.sort(key=lambda r: r.get("save_date", ""), reverse=True)
    return results


def get_last_played_path() -> Optional[str]:
    """Return the save path of the last played world, or None."""
    if not os.path.exists(LAST_PLAYED_PATH):
        return None
    try:
        with open(LAST_PLAYED_PATH, "r") as f:
            data = json.load(f)
        path = data.get("path", "")
        if path and os.path.exists(path):
            return path
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _write_last_played(seed: int, path: str):
    """Write the last-played marker file."""
    _ensure_worlds_dir()
    marker = {"seed": seed, "path": path,
              "timestamp": datetime.now().isoformat()}
    tmp = LAST_PLAYED_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(marker, f, indent=2)
    os.replace(tmp, LAST_PLAYED_PATH)


# ===================================================================
# Apply loaded state
# ===================================================================

def restore_world_plan(plan, save_data: Dict[str, Any]):
    """Restore settlements, roads, and spawn point to a world plan from save data.

    Called BEFORE structures are built, when skip_layouts=True left
    the plan with empty settlement/road lists.
    """
    from game.world.world_plan import SettlementPlan, RoadPlan
    import random

    saved_settlements = save_data.get("settlements", [])
    if saved_settlements and not plan.settlements:
        for sd in saved_settlements:
            sp = SettlementPlan(
                name=sd["name"], kind=sd["kind"],
                x=sd["x"], y=sd["y"],
                radius=sd.get("radius", 100),
                region="restored",
                race=sd.get("race", "Human"),
                population=sd.get("buildings_count", 10),
                specialization=sd.get("specialization", "general"),
            )
            plan.settlements.append(sp)

    # Restore spawn point from player position
    pdata = save_data.get("player", {})
    if pdata.get("x") and pdata.get("y"):
        plan.spawn_point = (int(pdata["x"]), int(pdata["y"]))

    # Rebuild roads between settlements (deterministic from seed)
    if plan.settlements and not plan.roads:
        rng = random.Random(plan.seed)
        # Simple MST-like road network
        from game.world.road_pathfinder import find_road_path
        placed = [plan.settlements[0]]
        remaining = list(plan.settlements[1:])
        while remaining:
            best_dist = float('inf')
            best_pair = None
            for p in placed:
                for r in remaining:
                    d = (p.x - r.x) ** 2 + (p.y - r.y) ** 2
                    if d < best_dist:
                        best_dist = d
                        best_pair = (p, r)
            if best_pair is None:
                break
            p, r = best_pair
            remaining.remove(r)
            placed.append(r)
            waypoints = find_road_path(plan, p.x, p.y, r.x, r.y)
            road_type = "king_road" if p.kind in ("city", "castle") or r.kind in ("city", "castle") else "gravel_road"
            plan.roads.append(RoadPlan(
                start_name=p.name, end_name=r.name,
                road_type=road_type, waypoints=waypoints))

    # Restore NPC roster from save (preserves names) or rebuild if not saved
    saved_roster = save_data.get("npc_summary", {}).get("roster", [])
    if saved_roster:
        plan.npc_roster = saved_roster
    elif plan.settlements and not plan.npc_roster:
        rng = random.Random(plan.seed + 7)
        plan._build_npc_roster(rng)


def apply_loaded_state(game, save_data: Dict[str, Any]):
    """Apply saved state onto a freshly-generated game.

    The world was already regenerated from the same seed; this
    restores player position, kingdom state, time, etc.
    """
    _apply_player_state(game.player, save_data.get("player", {}))
    _apply_time_state(game, save_data.get("game_time", {}))
    _apply_kingdom_state(game, save_data.get("kingdoms", []))
    _apply_modified_tiles(game.world, save_data.get("modified_tiles", {}))
    _apply_chronicle_state(game, save_data.get("events", {}))


def _apply_player_state(player, pdata: Dict[str, Any]):
    """Restore player from saved data."""
    if not pdata:
        return
    from game.data.save_game import apply_save_to_player
    # Reformat to match save_game.py's expected keys
    compat = {
        "player_x": pdata.get("x", player.x),
        "player_y": pdata.get("y", player.y),
        "current_floor": pdata.get("current_floor", 0),
        "hp": pdata.get("hp", player.hp),
        "max_hp": pdata.get("max_hp", player.max_hp),
        "energy": pdata.get("energy", 100),
        "max_energy": pdata.get("max_energy", 100),
        "xp": pdata.get("xp", player.xp),
        "level": pdata.get("level", player.level),
        "xp_to_next": pdata.get("xp_to_next", player.xp_to_next),
        "gold": pdata.get("gold", player.gold),
        "attack_damage": pdata.get("attack_damage", player.attack_damage),
        "defense": pdata.get("defense", player.defense),
        "kills": pdata.get("kills", 0),
        "quests_completed": pdata.get("quests_completed", 0),
        "steps": pdata.get("steps", 0),
        "name": pdata.get("name", player.name),
        "char_class": pdata.get("char_class", "Fighter"),
        "race": pdata.get("race", "Human"),
        "mode": pdata.get("mode", "mortal"),
        "inventory": pdata.get("inventory", []),
        "equipped_weapon": pdata.get("equipped_weapon"),
        "equipped_armor": pdata.get("equipped_armor"),
    }
    apply_save_to_player(player, compat)


def _apply_time_state(game, tdata: Dict[str, Any]):
    """Restore time system from saved data."""
    ts = getattr(game, "time_sys", None)
    if not ts or not tdata:
        return
    ts.day = tdata.get("day", ts.day)
    ts.time = tdata.get("time", ts.time)
    ts._refresh_astro()


def _apply_kingdom_state(game, kingdoms_data: List[Dict[str, Any]]):
    """Restore kingdom state from saved data."""
    sim = getattr(game, "simulation", None)
    gov = getattr(sim, "governance", None) if sim else None
    if not gov or not kingdoms_data:
        return
    for kdata in kingdoms_data:
        k = gov.kingdoms.get(kdata.get("name", ""))
        if not k:
            continue
        for attr in ("treasury", "tax_rate", "army_size", "population",
                     "public_morale", "governing_style", "corruption",
                     "law_enforcement", "active_law", "ruler_name"):
            if attr in kdata:
                setattr(k, attr, kdata[attr])


def _apply_modified_tiles(world, tiles_data: Dict[str, int]):
    """Re-apply tile modifications from saved data."""
    tiles_obj = getattr(world, "tiles", None)
    if not tiles_obj or not tiles_data:
        return
    for key_str, tile_type in tiles_data.items():
        try:
            x, y = (int(v) for v in key_str.split(","))
            tiles_obj[y][x] = tile_type
        except (ValueError, IndexError, TypeError):
            continue


def _apply_chronicle_state(game, events_data: Dict[str, Any]):
    """Restore chronicle entries from saved data."""
    chron = getattr(game, "chronicles", None)
    if not chron or not events_data:
        return
    for entry in events_data.get("history", []):
        try:
            chron.record(
                game_day=entry.get("day", 1),
                category=entry.get("category", "discovery"),
                title=entry.get("title", ""),
                description=entry.get("description", ""),
                importance=entry.get("importance", 1),
            )
        except Exception:
            continue
