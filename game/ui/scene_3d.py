"""3D scene geometry builder — converts game world tiles into 3D face lists.

Used by Renderer3D to generate geometry for the OpenGL renderer.
Imported from the prototype test_3d_scene.py and cleaned up.
"""

import math
from game.settings import *

# Face colors
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

# Import build_scene from test prototype
from test_3d_scene import build_scene
