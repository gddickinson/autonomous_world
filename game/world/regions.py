"""
World regions - distinct geographical areas with different inhabitants,
terrain types, and settlement patterns.

Each region has:
- Dominant terrain types
- Primary race(s)
- Settlement types and names
- Monster types common to the area
- Cultural flavor
"""

import random
import math
from typing import Dict, List, Tuple, Optional


REGIONS = {
    "human_kingdoms": {
        "name": "The Heartlands",
        "terrain_bias": {"grass": 0.4, "forest": 0.2, "farmland": 0.15, "road": 0.1},
        "primary_races": ["Human", "Half-Elf"],
        "settlement_types": ["village", "town", "city"],
        "settlement_names": [
            "Millbrook", "Ashford", "Goldpeak", "Sunridge", "Highcross",
            "Thornwall", "Copperdale", "Silverbend", "Stormwatch", "Embervale",
            "Dawnspire", "Starfall", "Greymoor", "Brighthollow", "Oakshire",
        ],
        "castle_names": ["Northwatch Keep", "Stormhold Citadel", "Sunspear Castle"],
        "max_settlements": 6,
        "monsters": ["bandit", "wolf", "boar", "goblin"],
        "description": "Fertile plains and rolling hills, the heart of human civilization.",
    },
    "elven_forests": {
        "name": "The Silverwood",
        "terrain_bias": {"dense_forest": 0.5, "forest": 0.3, "grass": 0.1},
        "primary_races": ["Elf", "Half-Elf"],
        "settlement_types": ["hamlet", "village"],
        "settlement_names": [
            "Silverleaf", "Moonwhisper", "Starbloom", "Willowglen",
            "Dewlight", "Thornrose", "Mistwood", "Crystalbrook",
        ],
        "castle_names": [],
        "max_settlements": 4,
        "monsters": ["spider", "dire_wolf", "harpy"],
        "description": "Ancient forests where the elves have dwelled for millennia.",
    },
    "dwarven_highlands": {
        "name": "The Iron Peaks",
        "terrain_bias": {"mountain": 0.4, "snow": 0.2, "grass": 0.15},
        "primary_races": ["Dwarf", "Gnome"],
        "settlement_types": ["village", "town"],
        "settlement_names": [
            "Ironholt", "Stonehaven", "Deepforge", "Hammerfall",
            "Granite Hall", "Anvil's Rest", "Coppermine", "Silverdelve",
        ],
        "castle_names": ["Ironthrone Fortress"],
        "max_settlements": 3,
        "monsters": ["kobold", "ogre", "gargoyle", "troll"],
        "description": "Rugged mountains rich in ore, home to the dwarven clans.",
    },
    "orcish_badlands": {
        "name": "The Blasted Wastes",
        "terrain_bias": {"sand": 0.3, "grass": 0.2, "mountain": 0.15, "swamp": 0.1},
        "primary_races": ["Half-Orc"],
        "settlement_types": ["hamlet", "village"],
        "settlement_names": [
            "Skullcrush Camp", "Bloodfang Hold", "Ashbone Warren",
            "Ironjaw Fort", "Razormaw Den", "Blackfist Outpost",
        ],
        "castle_names": [],
        "max_settlements": 3,
        "monsters": ["orc", "gnoll", "ogre", "manticore", "wight"],
        "description": "Harsh wastelands where only the strong survive.",
    },
    "coastal_reaches": {
        "name": "The Azure Coast",
        "terrain_bias": {"sand": 0.3, "grass": 0.3, "water": 0.2},
        "primary_races": ["Human", "Halfling"],
        "settlement_types": ["village", "town"],
        "settlement_names": [
            "Tidehaven", "Saltmere", "Coral Bay", "Windport",
            "Driftwood Landing", "Pearl Cove", "Seahaven", "Storm's End",
        ],
        "castle_names": ["Dragon's Gate"],
        "max_settlements": 4,
        "monsters": ["bandit", "wolf", "ankheg"],
        "description": "Sandy shores and fishing villages along the great ocean.",
    },
    "wild_frontier": {
        "name": "The Untamed Wilds",
        "terrain_bias": {"forest": 0.3, "grass": 0.2, "swamp": 0.15, "dense_forest": 0.15},
        "primary_races": ["Human", "Half-Orc", "Tiefling"],
        "settlement_types": ["hamlet"],
        "settlement_names": [
            "Last Hope", "Ranger's Rest", "Frontier Post",
            "Shadowfen", "Nighthaven", "Fogmere",
        ],
        "castle_names": [],
        "max_settlements": 3,
        "monsters": ["owlbear", "werewolf", "bugbear", "troll", "dire_wolf", "bear"],
        "description": "Untamed wilderness at the edge of civilization.",
    },
}


def assign_regions(world_width: int, world_height: int,
                   rng: random.Random) -> Dict[str, Dict]:
    """Assign regions to areas of the world map.
    Returns dict mapping region_name -> {center_x, center_y, radius, data}."""

    assignments = {}
    used_centers = []

    region_list = list(REGIONS.items())
    rng.shuffle(region_list)

    # Place human kingdoms in center, others around edges
    cx, cy = world_width // 2, world_height // 2

    for i, (region_name, region_data) in enumerate(region_list):
        if region_name == "human_kingdoms":
            rx, ry = cx + rng.randint(-30, 30), cy + rng.randint(-30, 30)
            radius = min(world_width, world_height) // 4
        elif region_name == "coastal_reaches":
            # Place near an edge
            side = rng.choice(["top", "bottom", "left", "right"])
            if side == "top":
                rx, ry = cx + rng.randint(-50, 50), 60
            elif side == "bottom":
                rx, ry = cx + rng.randint(-50, 50), world_height - 60
            elif side == "left":
                rx, ry = 60, cy + rng.randint(-50, 50)
            else:
                rx, ry = world_width - 60, cy + rng.randint(-50, 50)
            radius = min(world_width, world_height) // 5
        else:
            # Place in remaining sectors
            angle = (2 * math.pi * i) / len(region_list)
            dist = min(world_width, world_height) * 0.3
            rx = int(cx + math.cos(angle) * dist + rng.randint(-40, 40))
            ry = int(cy + math.sin(angle) * dist + rng.randint(-40, 40))
            rx = max(50, min(world_width - 50, rx))
            ry = max(50, min(world_height - 50, ry))
            radius = min(world_width, world_height) // 5

        assignments[region_name] = {
            "center_x": rx, "center_y": ry,
            "radius": radius, "data": region_data,
        }
        used_centers.append((rx, ry))

    return assignments


def get_region_at(x: int, y: int, regions: Dict) -> Optional[str]:
    """Get which region a world position belongs to."""
    best = None
    best_dist = float('inf')

    for name, info in regions.items():
        cx, cy = info["center_x"], info["center_y"]
        dist = math.sqrt((x - cx)**2 + (y - cy)**2)
        if dist < info["radius"] and dist < best_dist:
            best = name
            best_dist = dist

    return best
