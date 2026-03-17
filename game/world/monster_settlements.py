"""
Monster Settlement Generation — intelligent monster civilizations with buildings,
roads, economy, and NPC-like citizens.

Monster settlements use the same infrastructure as human settlements but with
species-appropriate architecture, governance, and culture:

- ORC STRONGHOLD: Palisade walls, great hall, fighting pits, forges, barracks
- GOBLIN WARREN: Underground tunnels, trap workshops, mushroom farms, boss chamber
- KOBOLD MINE: Mineshafts, ore processing, trap corridors, dragon shrine
- BANDIT CAMP: Hidden tents, loot storage, lookout towers, tavern
- GNOLL DEN: Bone-decorated cave, hunting trophies, pack quarters
- UNDEAD CRYPT: Necromancer tower, bone pits, ritual chambers, catacombs

Each generates real NPC citizens with monster races, appropriate classes,
and the same daily routine/economy systems as human NPCs.
"""

import random
import math
from typing import List, Dict, Tuple, Optional

from game.settings import (
    WALL, FLOOR, DOOR, TABLE, BED, CHEST, FIREPLACE, BARREL,
    STAIRS_UP, STAIRS_DOWN, WINDOW, THRONE, BOOKSHELF, ANVIL,
    FORGE_FIRE, PILLAR, CARPET, ALTAR, ARCHWAY, IRON_GATE,
    GRASS, ROAD, GRAVEL_ROAD, DIRT_TRACK,
)


# ================================================================
# MONSTER SETTLEMENT TYPES
# ================================================================

MONSTER_SETTLEMENT_TYPES = {
    "orc_stronghold": {
        "governance": "tribal",       # uses tribal governance style
        "min_population": 8,
        "max_population": 25,
        "building_types": ["great_hall", "barracks", "forge", "chieftain_hut",
                           "fighting_pit", "storage", "shaman_hut"],
        "races": ["Half-Orc", "Half-Orc", "Half-Orc", "Human"],  # weighted
        "classes": ["Fighter", "Barbarian", "Fighter", "Ranger", "Cleric"],
        "road_type": DIRT_TRACK,
        "wall_material": WALL,  # palisade
        "description": "A fortified orc stronghold with palisade walls",
        "hostile_to_humans": True,
        "can_trade": True,      # orcs trade through tribute
        "ruler_title": "warchief",
    },
    "goblin_warren": {
        "governance": "tribal",
        "min_population": 10,
        "max_population": 30,
        "building_types": ["boss_chamber", "trap_workshop", "mushroom_farm",
                           "sleeping_den", "loot_hoard", "shaman_hut"],
        "races": ["Gnome", "Halfling", "Gnome"],  # goblin proxied by gnome/halfling
        "classes": ["Rogue", "Rogue", "Ranger", "Wizard", "Fighter"],
        "road_type": DIRT_TRACK,
        "wall_material": WALL,
        "description": "A sprawling goblin warren half-underground",
        "hostile_to_humans": True,
        "can_trade": False,
        "ruler_title": "boss",
    },
    "kobold_mine": {
        "governance": "autocracy",
        "min_population": 12,
        "max_population": 20,
        "building_types": ["mine_entrance", "ore_processing", "trap_corridor",
                           "dragon_shrine", "sleeping_quarters", "storage"],
        "races": ["Gnome", "Gnome", "Halfling"],  # kobold proxied
        "classes": ["Rogue", "Fighter", "Cleric", "Ranger", "Wizard"],
        "road_type": DIRT_TRACK,
        "wall_material": WALL,
        "description": "An organized kobold mining operation",
        "hostile_to_humans": False,  # kobolds can be subservient
        "can_trade": True,
        "ruler_title": "overlord",
    },
    "bandit_camp": {
        "governance": "anarchy",
        "min_population": 5,
        "max_population": 15,
        "building_types": ["boss_tent", "loot_storage", "lookout_tower",
                           "tavern", "sleeping_tents", "stable"],
        "races": ["Human", "Half-Elf", "Human", "Tiefling"],
        "classes": ["Rogue", "Fighter", "Ranger", "Bard", "Rogue"],
        "road_type": DIRT_TRACK,
        "wall_material": WALL,
        "description": "A hidden bandit encampment",
        "hostile_to_humans": True,
        "can_trade": True,  # bandits fence stolen goods
        "ruler_title": "kingpin",
    },
    "gnoll_den": {
        "governance": "tribal",
        "min_population": 6,
        "max_population": 18,
        "building_types": ["alpha_den", "pack_quarters", "bone_altar",
                           "trophy_hall", "hunting_ground"],
        "races": ["Half-Orc", "Half-Orc"],  # gnoll proxied
        "classes": ["Barbarian", "Fighter", "Ranger", "Barbarian", "Cleric"],
        "road_type": DIRT_TRACK,
        "wall_material": WALL,
        "description": "A gnoll pack den decorated with bones",
        "hostile_to_humans": True,
        "can_trade": False,
        "ruler_title": "alpha",
    },
    "undead_crypt": {
        "governance": "tyranny",
        "min_population": 3,
        "max_population": 8,
        "building_types": ["necromancer_tower", "ritual_chamber", "bone_pit",
                           "catacombs", "library"],
        "races": ["Tiefling", "Human", "Half-Elf"],  # necromancers
        "classes": ["Wizard", "Warlock", "Cleric", "Sorcerer"],
        "road_type": DIRT_TRACK,
        "wall_material": WALL,
        "description": "A crypt controlled by intelligent undead",
        "hostile_to_humans": True,
        "can_trade": False,
        "ruler_title": "necromancer",
    },
}

# Monster settlement names by type
MONSTER_NAMES = {
    "orc_stronghold": [
        "Grak'thor Hold", "Bloodfist Keep", "Iron Tusk Fortress", "Skull Crusher Camp",
        "Warbringer's Seat", "Red Axe Stronghold", "Bonecleaver Fort", "Thunderfang Hold",
    ],
    "goblin_warren": [
        "Skittershanks Warren", "Muckhole Den", "Ratfang Tunnels", "Gloomburrow",
        "Stinkpit", "Snaggle's Domain", "Darkwriggle Caves", "Chittertrap Maze",
    ],
    "kobold_mine": [
        "Scalewing Mine", "Deepdig Warrens", "Glittervein Shaft", "Coppertooth Mine",
        "Dragonspark Dig", "Shimmerscale Tunnels", "Gemclaw Quarry",
    ],
    "bandit_camp": [
        "Cutthroat's Rest", "Shadow's Edge", "Thieves' Hollow", "The Black Camp",
        "Dagger Point", "Highwayman's Roost", "The Hideaway", "Outlaw's Refuge",
    ],
    "gnoll_den": [
        "Bonegnaw Den", "Hyena's Maw", "Fleshripper Caves", "Howlblood Lair",
        "Carrion Pit", "Deathhowl Den",
    ],
    "undead_crypt": [
        "The Black Sepulchre", "Dreadhollow Crypt", "Shadowfall Tomb",
        "The Whispering Vault", "Bonechill Catacombs", "Lich's Sanctum",
    ],
}


def generate_monster_settlements(world, rng: random.Random,
                                  monster_groups: list = None) -> list:
    """Generate monster settlements in the world based on existing monster groups.

    Places settlements near existing monster group clusters. Each settlement
    becomes a proper Structure with buildings, NPC spawns, and a road network.

    Returns list of (Structure, npc_spawn_data, kingdom_data) tuples.
    """
    from game.world.world import Structure

    results = []
    used_positions = set()

    # Map monster governance types to settlement types
    gov_to_settlement = {
        "orc": "orc_stronghold",
        "goblin": "goblin_warren",
        "kobold": "kobold_mine",
        "bandit": "bandit_camp",
        "gnoll": "gnoll_den",
        "undead": "undead_crypt",
    }

    # Collect strongest monster groups by type
    groups_by_type = {}
    if monster_groups:
        for g in monster_groups:
            if g.population < 2:  # lowered threshold for more settlements
                continue
            if g.kind not in groups_by_type:
                groups_by_type[g.kind] = []
            groups_by_type[g.kind].append(g)

    # For each monster type, create tiered settlements:
    # - Strongest group → full settlement (stronghold/warren/mine)
    # - Weaker groups → small camps (3-6 defenders, easier for early game)
    for monster_type, groups in groups_by_type.items():
        settlement_type = gov_to_settlement.get(monster_type)
        if not settlement_type:
            continue

        config = MONSTER_SETTLEMENT_TYPES[settlement_type]
        names = list(MONSTER_NAMES.get(settlement_type, [f"{monster_type} Settlement"]))
        rng.shuffle(names)

        # Sort groups by strength
        groups.sort(key=lambda g: -g.strength)

        # Top 1-2 get full settlements, next 1-2 get small camps
        num_full = min(2, len(groups), len(names))
        num_camps = min(2, max(0, len(groups) - num_full), max(0, len(names) - num_full))
        num_settlements = num_full + num_camps

        for i in range(num_settlements):
            group = groups[i]
            name = names[i] if i < len(names) else f"{monster_type.title()} Camp {i}"

            # Check position is valid
            cx, cy = int(group.base_x), int(group.base_y)
            if cx < 30 or cx > world.width - 30 or cy < 30 or cy > world.height - 30:
                continue

            # Check not too close to human settlements
            too_close = False
            for s in world.structures:
                if s.kind in ("village", "town", "city", "castle", "hamlet"):
                    d = math.sqrt((s.x - cx)**2 + (s.y - cy)**2)
                    if d < 30:
                        too_close = True
                        break
            if too_close:
                continue

            pos_key = (cx // 20, cy // 20)
            if pos_key in used_positions:
                continue
            used_positions.add(pos_key)

            # Determine settlement tier
            is_camp = i >= num_full  # later settlements are small camps

            if is_camp:
                # Small camp: 3-6 defenders, fewer buildings, easier target
                population = rng.randint(3, 6)
                radius = 6
                camp_buildings = config["building_types"][:3]  # only first 3 building types
                name = f"{monster_type.title()} Camp" if i >= len(names) else names[i]
            else:
                # Full settlement
                population = rng.randint(config["min_population"], config["max_population"])
                radius = 8 + population // 3
                camp_buildings = config["building_types"]

            # Place buildings as simple structures on the world
            buildings = _place_monster_buildings(
                world, cx, cy, radius, camp_buildings, rng)

            # Create Structure
            struct = Structure(name, settlement_type, cx, cy, radius=radius)
            struct.buildings = [(b["x"], b["y"], b["w"], b["h"]) for b in buildings]
            world.structures.append(struct)

            # Generate NPC spawn data
            npc_spawns = _generate_monster_npcs(
                cx, cy, radius, population, config, buildings, rng)

            # Road from settlement center outward
            _place_settlement_roads(world, cx, cy, radius, config["road_type"])

            # Kingdom data for governance system
            kingdom_data = {
                "name": name,
                "kind": settlement_type,
                "governance_style": config["governance"],
                "ruler_title": config["ruler_title"],
                "x": cx, "y": cy,
                "population": population,
                "hostile_to_humans": config["hostile_to_humans"],
                "can_trade": config["can_trade"],
                "monster_group": group,
            }

            results.append((struct, npc_spawns, kingdom_data))

    return results


def _place_monster_buildings(world, cx: int, cy: int, radius: int,
                              building_types: list,
                              rng: random.Random) -> list:
    """Place monster buildings around a center point."""
    buildings = []
    angles = [i * (2 * math.pi / len(building_types)) + rng.uniform(-0.3, 0.3)
              for i in range(len(building_types))]

    for i, btype in enumerate(building_types):
        # Size based on building importance
        if btype in ("great_hall", "boss_chamber", "alpha_den", "necromancer_tower",
                      "chieftain_hut", "boss_tent"):
            w, h = rng.randint(8, 12), rng.randint(8, 12)
        elif btype in ("barracks", "pack_quarters", "sleeping_den", "sleeping_quarters",
                        "sleeping_tents", "catacombs"):
            w, h = rng.randint(6, 10), rng.randint(6, 8)
        else:
            w, h = rng.randint(4, 7), rng.randint(4, 6)

        # Position around center
        dist = rng.uniform(2, radius * 0.7)
        angle = angles[i]
        bx = int(cx + math.cos(angle) * dist) - w // 2
        by = int(cy + math.sin(angle) * dist) - h // 2

        # Clamp to world
        bx = max(5, min(world.width - w - 5, bx))
        by = max(5, min(world.height - h - 5, by))

        # Place building tiles
        for ty in range(by, by + h):
            for tx in range(bx, bx + w):
                if 0 <= tx < world.width and 0 <= ty < world.height:
                    if ty == by or ty == by + h - 1 or tx == bx or tx == bx + w - 1:
                        world.tiles[ty][tx] = WALL
                    else:
                        world.tiles[ty][tx] = FLOOR

        # Door on south wall
        door_x = bx + w // 2
        door_y = by + h - 1
        if 0 <= door_x < world.width and 0 <= door_y < world.height:
            world.tiles[door_y][door_x] = DOOR

        # Place some furniture based on building type
        _furnish_monster_building(world, bx, by, w, h, btype, rng)

        buildings.append({"x": bx, "y": by, "w": w, "h": h, "type": btype})

    return buildings


def _furnish_monster_building(world, bx: int, by: int, w: int, h: int,
                               btype: str, rng: random.Random):
    """Place appropriate furniture in a monster building."""
    interior = []  # (x, y) positions for furniture

    # Collect interior floor tiles
    for ty in range(by + 1, by + h - 1):
        for tx in range(bx + 1, bx + w - 1):
            if 0 <= tx < world.width and 0 <= ty < world.height:
                if world.tiles[ty][tx] == FLOOR:
                    interior.append((tx, ty))

    if not interior:
        return

    # Furniture by building type
    furniture_map = {
        "great_hall":        [(THRONE, 1), (TABLE, 3), (FIREPLACE, 1), (BARREL, 2)],
        "chieftain_hut":     [(BED, 1), (CHEST, 2), (TABLE, 1), (FIREPLACE, 1)],
        "boss_chamber":      [(THRONE, 1), (CHEST, 3), (TABLE, 1)],
        "boss_tent":         [(BED, 1), (CHEST, 2), (TABLE, 1)],
        "alpha_den":         [(BED, 2), (CHEST, 1), (BARREL, 2)],
        "barracks":          [(BED, 4), (CHEST, 2), (TABLE, 1)],
        "pack_quarters":     [(BED, 4), (BARREL, 2)],
        "sleeping_den":      [(BED, 6), (BARREL, 1)],
        "sleeping_quarters": [(BED, 4), (CHEST, 2)],
        "sleeping_tents":    [(BED, 3), (BARREL, 1)],
        "forge":             [(ANVIL, 1), (FORGE_FIRE, 1), (BARREL, 2), (CHEST, 1)],
        "trap_workshop":     [(TABLE, 2), (CHEST, 3), (BARREL, 2)],
        "fighting_pit":      [(BARREL, 2)],
        "storage":           [(CHEST, 4), (BARREL, 4)],
        "loot_hoard":        [(CHEST, 6), (BARREL, 2)],
        "loot_storage":      [(CHEST, 4), (BARREL, 3)],
        "shaman_hut":        [(ALTAR, 1), (BOOKSHELF, 1), (BED, 1), (FIREPLACE, 1)],
        "bone_altar":        [(ALTAR, 1), (PILLAR, 2), (FIREPLACE, 1)],
        "dragon_shrine":     [(ALTAR, 1), (PILLAR, 4), (CARPET, 2)],
        "mushroom_farm":     [(BARREL, 4)],
        "mine_entrance":     [(BARREL, 2), (CHEST, 1)],
        "ore_processing":    [(ANVIL, 1), (FORGE_FIRE, 1), (CHEST, 2), (BARREL, 2)],
        "trap_corridor":     [],
        "hunting_ground":    [(BARREL, 1)],
        "trophy_hall":       [(TABLE, 2), (PILLAR, 2), (FIREPLACE, 1)],
        "necromancer_tower": [(BOOKSHELF, 3), (ALTAR, 1), (TABLE, 1), (BED, 1)],
        "ritual_chamber":    [(ALTAR, 1), (PILLAR, 4), (CARPET, 2), (FIREPLACE, 1)],
        "bone_pit":          [(BARREL, 2)],
        "catacombs":         [(BED, 4), (CHEST, 1)],
        "library":           [(BOOKSHELF, 4), (TABLE, 2)],
        "tavern":            [(TABLE, 4), (BARREL, 4), (FIREPLACE, 1), (BED, 2)],
        "stable":            [(BARREL, 3)],
        "lookout_tower":     [(BED, 1), (CHEST, 1)],
    }

    items = furniture_map.get(btype, [(BARREL, 1)])
    rng.shuffle(interior)
    idx = 0
    for tile_type, count in items:
        for _ in range(count):
            if idx >= len(interior):
                break
            tx, ty = interior[idx]
            idx += 1
            world.tiles[ty][tx] = tile_type


def _generate_monster_npcs(cx: int, cy: int, radius: int,
                            population: int, config: dict,
                            buildings: list,
                            rng: random.Random) -> list:
    """Generate NPC spawn data for monster settlement citizens."""
    spawns = []
    races = config["races"]
    classes = config["classes"]
    ruler_title = config["ruler_title"]

    for i in range(population):
        # Place near buildings
        if buildings:
            b = rng.choice(buildings)
            nx = b["x"] + rng.randint(1, b["w"] - 2)
            ny = b["y"] + rng.randint(1, b["h"] - 2)
        else:
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(2, radius * 0.8)
            nx = cx + int(math.cos(angle) * dist)
            ny = cy + int(math.sin(angle) * dist)

        race = rng.choice(races)
        char_class = rng.choice(classes)

        spawn = {
            "x": float(nx),
            "y": float(ny),
            "class": char_class,
            "race": race,
            "building": config.get("building_types", ["camp"])[0],
        }

        # First NPC is the ruler
        if i == 0:
            spawn["title"] = ruler_title
            spawn["is_ruler"] = True

        spawns.append(spawn)

    return spawns


def _place_settlement_roads(world, cx: int, cy: int, radius: int, road_tile: int):
    """Place roads within and leading out of a monster settlement."""
    # Internal roads connecting buildings
    for angle_deg in [0, 90, 180, 270]:
        angle = math.radians(angle_deg)
        for dist in range(1, radius + 5):
            rx = int(cx + math.cos(angle) * dist)
            ry = int(cy + math.sin(angle) * dist)
            if 0 <= rx < world.width and 0 <= ry < world.height:
                if world.tiles[ry][rx] in (GRASS,):
                    world.tiles[ry][rx] = road_tile
