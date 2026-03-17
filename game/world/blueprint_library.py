"""
Blueprint Library — extensive collection of historically-inspired building designs.

Architectural styles represented:
- PRIMITIVE: mud huts, lean-tos, roundhouses, pit houses
- TRIBAL: longhouses, mead halls, chieftain's lodges, totems
- ROMAN: villas, baths, temples with columns, aqueducts, forums
- GREEK: temples with peristyles, agoras, gymnasiums
- MEDIEVAL: cottages, manors, castles, cathedrals, keeps
- FEUDAL: lord's halls, serfs' hovels, guild houses, markets

Tile legend:
W=Wall F=Floor D=Door T=Table B=Bed C=Chest N=Window L=Locked
S=StairsUp s=StairsDown P=Pillar A=Altar H=Fireplace
U=LadderUp u=LadderDown K=Throne X=Bookshelf R=Barrel
V=Anvil G=ForgeFire O=Fountain Q=Carpet M=Mosaic
E=Archway I=IronGate _=Grass/Exterior
"""

from game.settings import (WALL, FLOOR, DOOR, TABLE, BED, CHEST,
                           STAIRS_UP, STAIRS_DOWN, WINDOW, LOCKED_DOOR, GRASS,
                           PILLAR, ALTAR, FIREPLACE, LADDER_UP, LADDER_DOWN,
                           THRONE, BOOKSHELF, BARREL, ANVIL, FORGE_FIRE,
                           FOUNTAIN, CARPET, MOSAIC, ARCHWAY, IRON_GATE)
from game.world.buildings import Blueprint
import random
from typing import List

# Short aliases
W=WALL; F=FLOOR; D=DOOR; T=TABLE; B=BED; C=CHEST; N=WINDOW; L=LOCKED_DOOR
S=STAIRS_UP; s=STAIRS_DOWN; P=PILLAR; A=ALTAR; H=FIREPLACE
U=LADDER_UP; u=LADDER_DOWN; K=THRONE; X=BOOKSHELF; R=BARREL
V=ANVIL; G=FORGE_FIRE; O=FOUNTAIN; Q=CARPET; M=MOSAIC; E=ARCHWAY; I=IRON_GATE
_=GRASS

# ================================================================
# PRIMITIVE DWELLINGS
# ================================================================

PRIMITIVE = [
    Blueprint("Mud Hut", "house", [
        [_, W, W, W, _],
        [W, F, F, F, W],
        [W, F, H, F, W],
        [W, F, F, F, W],
        [_, W, D, W, _],
    ], npc_count=1, description="A primitive circular mud hut with central fire."),
    Blueprint("Pit House", "house", [
        [W, W, W, W, W, W],
        [W, F, F, F, F, W],
        [W, F, H, F, F, W],
        [W, F, F, F, B, W],
        [W, W, W, D, W, W],
    ], npc_count=1, description="A semi-subterranean pit dwelling."),
    Blueprint("Lean-To", "house", [
        [W, W, W, W],
        [W, F, F, W],
        [W, F, B, W],
        [W, D, W, _],
    ], npc_count=1, description="A crude lean-to shelter against a rock face."),
    Blueprint("Roundhouse", "house", [
        [_, W, W, W, W, W, _],
        [W, F, F, F, F, F, W],
        [W, F, F, H, F, F, W],
        [W, F, F, F, F, F, W],
        [W, F, F, F, F, B, W],
        [_, W, W, D, W, W, _],
    ], npc_count=2, description="A large circular roundhouse with thatched roof."),
    Blueprint("Cave Dwelling", "house", [
        [W, W, W, W, W, W],
        [W, F, F, F, F, W],
        [W, F, H, F, B, W],
        [W, F, F, F, R, W],
        [W, W, D, W, W, W],
    ], npc_count=1, description="A natural cave made habitable."),
]

# ================================================================
# TRIBAL BUILDINGS
# ================================================================

TRIBAL = [
    Blueprint("Tribal Longhouse", "house", [
        [W, W, N, W, W, W, W, W, N, W, W, W, W],
        [W, F, F, F, F, F, F, F, F, F, F, F, W],
        [N, F, F, F, H, F, F, F, H, F, F, F, N],
        [W, F, F, F, F, F, F, F, F, F, F, F, W],
        [W, F, B, F, F, F, T, F, F, F, B, F, W],
        [W, W, W, W, W, D, W, W, W, W, W, W, W],
    ], npc_count=4, description="A long tribal dwelling with two hearths."),
    Blueprint("Chieftain's Lodge", "house", [
        [W, W, W, N, W, W, W, W, N, W, W, W],
        [W, F, F, F, F, F, F, F, F, F, F, W],
        [W, F, F, F, P, F, F, P, F, F, F, W],
        [N, F, F, F, F, H, F, F, F, F, F, N],
        [W, F, F, F, P, F, F, P, F, F, F, W],
        [W, F, F, F, F, F, F, F, F, F, F, W],
        [W, W, W, W, E, F, F, E, W, W, W, W],
        [W, B, F, C, W, F, K, W, C, F, B, W],
        [W, F, F, F, W, F, F, W, F, F, F, W],
        [W, W, W, W, W, W, D, W, W, W, W, W],
    ], npc_count=3, description="The chieftain's impressive lodge with throne."),
    Blueprint("Mead Hall", "tavern", [
        [W, W, N, W, W, W, W, W, W, N, W, W],
        [W, F, F, F, F, F, F, F, F, F, F, W],
        [N, F, F, T, F, F, F, F, T, F, F, N],
        [W, F, F, F, F, H, F, F, F, F, F, W],
        [N, F, F, T, F, F, F, F, T, F, F, N],
        [W, F, F, F, F, F, F, F, F, F, F, W],
        [W, R, F, F, F, F, F, F, F, F, R, W],
        [W, W, W, W, W, D, D, W, W, W, W, W],
    ], npc_class="Barbarian", npc_count=4, description="A great mead hall for feasting."),
    Blueprint("Shaman's Hut", "temple", [
        [_, W, W, W, W, W, _],
        [W, F, F, F, F, F, W],
        [W, F, F, A, F, F, W],
        [W, F, F, F, F, F, W],
        [W, F, H, F, X, F, W],
        [W, F, F, F, F, C, W],
        [_, W, W, D, W, W, _],
    ], npc_class="Druid", npc_count=1, description="A shaman's hut with altar and herbs."),
]

# ================================================================
# ROMAN BUILDINGS
# ================================================================

ROMAN = [
    Blueprint("Roman Villa", "house", [
        [W, W, W, W, W, W, W, W, W, W, W, W, W, W],
        [W, M, M, M, P, M, M, M, M, P, M, M, M, W],
        [W, M, M, M, F, M, M, M, M, F, M, M, M, W],
        [W, M, M, M, F, F, O, F, F, F, M, M, M, W],
        [W, P, F, F, F, F, F, F, F, F, F, F, P, W],
        [W, M, M, M, F, F, F, F, F, F, M, M, M, W],
        [W, W, D, W, W, E, F, F, E, W, W, D, W, W],
        [W, B, Q, F, W, F, F, F, F, W, F, Q, B, W],
        [W, F, Q, C, W, F, F, F, F, W, C, Q, F, W],
        [W, W, W, W, W, F, H, F, F, W, W, W, W, W],
        [_, _, _, _, W, F, F, F, F, W, _, _, _, _],
        [_, _, _, _, W, W, D, D, W, W, _, _, _, _],
    ], npc_count=4, description="A Roman villa with atrium, fountain, and mosaics."),
    Blueprint("Roman Bathhouse", "tavern", [
        [W, W, W, W, W, W, W, W, W, W],
        [W, M, M, P, M, M, P, M, M, W],
        [W, M, F, F, F, F, F, F, M, W],
        [W, P, F, F, F, F, F, F, P, W],
        [W, M, F, F, O, F, F, F, M, W],
        [W, M, F, F, F, F, F, F, M, W],
        [W, P, F, F, F, F, F, F, P, W],
        [W, W, W, E, W, W, E, W, W, W],
        [W, F, F, F, W, F, F, F, F, W],
        [W, F, H, F, W, F, F, F, F, W],
        [W, W, W, W, W, W, D, W, W, W],
    ], npc_count=2, description="A Roman-style bathhouse with heated pool."),
    Blueprint("Roman Temple", "temple", [
        [W, W, W, W, W, W, W, W, W, W, W, W],
        [W, M, M, P, M, M, M, M, P, M, M, W],
        [W, M, M, F, M, M, M, M, F, M, M, W],
        [W, M, M, F, F, F, A, F, F, M, M, W],
        [W, P, F, F, F, F, F, F, F, F, P, W],
        [W, M, M, F, F, F, F, F, F, M, M, W],
        [W, M, M, P, F, F, F, F, P, M, M, W],
        [W, W, W, W, E, F, F, E, W, W, W, W],
        [_, _, _, _, P, M, M, P, _, _, _, _],
        [_, _, _, _, P, M, M, P, _, _, _, _],
        [_, _, _, _, _, D, D, _, _, _, _, _],
    ], npc_class="Cleric", npc_count=2, description="A grand Roman temple with columns."),
]

# ================================================================
# GREEK BUILDINGS
# ================================================================

GREEK = [
    Blueprint("Greek Temple", "temple", [
        [_, P, _, P, _, P, _, P, _, P, _],
        [P, M, M, M, M, M, M, M, M, M, P],
        [_, M, W, W, W, W, W, W, W, M, _],
        [P, M, W, F, F, F, F, F, W, M, P],
        [_, M, W, F, F, A, F, F, W, M, _],
        [P, M, W, F, F, F, F, F, W, M, P],
        [_, M, W, F, F, F, F, F, W, M, _],
        [P, M, W, W, E, F, E, W, W, M, P],
        [_, M, M, M, M, M, M, M, M, M, _],
        [P, _, _, _, _, _, _, _, _, _, P],
    ], npc_class="Cleric", npc_count=2, description="A Greek peristyle temple with surrounded columns."),
    Blueprint("Greek Agora Hall", "civic", [
        [W, W, W, W, W, W, W, W, W, W, W, W, W, W],
        [W, F, F, F, P, F, F, F, F, P, F, F, F, W],
        [W, F, F, F, F, F, F, F, F, F, F, F, F, W],
        [W, F, T, F, F, F, F, F, F, F, F, T, F, W],
        [W, P, F, F, F, F, F, F, F, F, F, F, P, W],
        [W, F, F, F, F, F, O, F, F, F, F, F, F, W],
        [W, F, T, F, F, F, F, F, F, F, F, T, F, W],
        [W, P, F, F, F, F, F, F, F, F, F, F, P, W],
        [W, F, F, F, F, F, F, F, F, F, F, F, F, W],
        [W, W, W, W, E, F, F, F, F, E, W, W, W, W],
    ], npc_count=3, description="A grand meeting hall in the Greek style."),
]

# ================================================================
# MEDIEVAL COTTAGES & HOUSES
# ================================================================

MEDIEVAL_HOUSES = [
    Blueprint("Serf's Hovel", "house", [
        [W, W, W, W, W],
        [W, F, F, F, W],
        [W, F, H, B, W],
        [W, W, D, W, W],
    ], npc_count=1, description="A miserable one-room hovel."),
    Blueprint("Peasant Cottage", "house", [
        [W, W, N, W, W, W],
        [W, F, F, F, F, W],
        [N, F, F, T, F, N],
        [W, F, H, F, F, W],
        [W, W, D, W, B, W],
        [_, _, _, W, W, W],
    ], npc_count=2, description="A small thatched peasant cottage."),
    Blueprint("Craftsman's Home", "house", [
        [W, W, N, W, W, W, N, W],
        [W, F, F, F, W, F, F, W],
        [N, F, F, F, D, F, B, N],
        [W, F, T, F, W, F, C, W],
        [W, F, H, F, W, W, W, W],
        [W, W, D, W, W, _, _, _],
    ], npc_count=2, description="A craftsman's home with workshop."),
    Blueprint("Wealthy Burgher's House", "house", [
        [W, W, N, W, W, W, W, N, W, W],
        [W, F, F, F, F, W, F, F, F, W],
        [N, F, F, F, F, D, F, F, F, N],
        [W, F, T, F, F, W, F, B, C, W],
        [W, F, F, H, F, W, W, D, W, W],
        [W, W, W, D, W, W, Q, Q, F, W],
        [W, X, F, F, F, D, Q, Q, F, W],
        [W, F, F, T, F, W, F, B, C, W],
        [W, F, F, F, F, W, W, W, W, W],
        [W, W, W, W, D, W, _, _, _, _],
    ], npc_count=3, description="A wealthy burgher's fine house with library."),
    Blueprint("Timber-Frame House", "house", [
        [W, W, N, W, W, W],
        [W, F, F, F, F, W],
        [W, F, F, F, F, W],
        [W, F, T, H, F, W],
        [W, W, W, D, W, W],
        [W, B, F, F, C, W],
        [W, F, F, F, F, W],
        [W, W, W, D, W, W],
    ], npc_count=2, description="A half-timber medieval townhouse."),
]

# ================================================================
# MEDIEVAL COMMERCIAL
# ================================================================

MEDIEVAL_COMMERCIAL = [
    Blueprint("Blacksmith's Forge", "shop", [
        [W, W, W, W, W, W, W, W, W],
        [W, F, F, F, W, F, F, F, W],
        [W, F, V, F, D, F, F, F, W],
        [W, F, F, F, W, F, G, F, W],
        [W, W, W, D, W, F, F, F, W],
        [_, _, _, _, W, R, F, R, W],
        [_, _, _, _, W, W, D, W, W],
    ], npc_class="Fighter", npc_count=1, description="A forge with anvil, bellows, and fire."),
    Blueprint("Apothecary Shop", "shop", [
        [W, W, N, W, W, W],
        [W, X, F, F, X, W],
        [N, F, F, F, F, N],
        [W, F, T, F, F, W],
        [W, R, F, F, R, W],
        [W, W, W, D, W, W],
    ], npc_class="Druid", npc_count=1, description="An apothecary with potions and herbs."),
    Blueprint("Jeweler's Workshop", "shop", [
        [W, W, W, W, W, W, W],
        [W, F, F, F, F, F, W],
        [W, T, F, F, F, T, W],
        [W, W, L, W, W, W, W],
        [W, C, F, F, F, C, W],
        [W, C, F, F, F, C, W],
        [W, W, W, D, W, W, W],
    ], npc_class="Rogue", npc_count=1, description="A jeweler with locked vault."),
    Blueprint("Large Market Hall", "shop", [
        [W, W, W, W, W, W, W, W, W, W, W, W],
        [W, F, F, F, P, F, F, F, F, P, F, W],
        [W, F, T, F, F, F, F, F, F, F, T, W],
        [W, F, F, F, F, F, F, F, F, F, F, W],
        [W, P, F, F, F, F, F, F, F, F, P, W],
        [W, F, T, F, F, F, F, F, F, F, T, W],
        [W, F, F, F, P, F, F, F, F, P, F, W],
        [W, R, F, F, F, F, F, F, F, F, R, W],
        [W, W, W, W, D, D, D, D, W, W, W, W],
    ], npc_count=4, description="A grand covered market hall with pillars."),
    Blueprint("Warehouse District", "shop", [
        [W, W, W, W, W, W, W, W, W, W, W, W],
        [W, R, F, R, F, R, W, R, F, R, F, W],
        [W, F, F, F, F, F, W, F, F, F, F, W],
        [W, R, F, R, F, R, D, R, F, R, F, W],
        [W, F, F, F, F, F, W, F, F, F, F, W],
        [W, C, F, C, F, C, W, C, F, C, F, W],
        [W, W, W, D, W, W, W, W, D, W, W, W],
    ], npc_count=2, description="A warehouse complex with barrels and crates."),
]

# ================================================================
# LARGE TAVERNS & INNS
# ================================================================

TAVERNS = [
    Blueprint("Village Alehouse", "tavern", [
        [W, W, N, W, W, W],
        [W, F, F, F, F, W],
        [N, F, T, F, R, N],
        [W, F, F, T, F, W],
        [W, F, H, F, F, W],
        [W, W, W, D, W, W],
    ], npc_class="Bard", npc_count=1, description="A simple village alehouse."),
    Blueprint("Roadside Inn", "tavern", [
        [W, N, W, W, W, N, W, W, N, W],
        [W, F, F, F, F, F, F, F, F, W],
        [N, F, T, F, F, F, T, F, F, N],
        [W, F, F, F, H, F, F, F, F, W],
        [W, F, F, T, F, F, F, T, F, W],
        [W, W, W, W, E, F, E, W, W, W],
        [W, B, F, W, F, F, F, W, B, W],
        [W, F, F, D, F, F, F, D, F, W],
        [W, W, W, W, R, F, R, W, W, W],
        [_, _, _, W, T, C, F, W, _, _],
        [_, _, _, W, F, F, F, W, _, _],
        [_, _, _, W, W, D, W, W, _, _],
    ], npc_class="Bard", npc_count=3, description="A welcoming roadside inn."),
    Blueprint("Grand City Tavern", "tavern", [
        [W, N, W, W, N, W, W, N, W, W, W, N, W, W],
        [W, F, F, F, F, F, F, F, F, F, F, F, F, W],
        [N, F, T, F, F, P, F, F, P, F, F, T, F, N],
        [W, F, F, F, F, F, H, F, F, F, F, F, F, W],
        [N, F, F, T, F, F, F, F, F, F, T, F, F, N],
        [W, F, F, F, F, P, F, F, P, F, F, F, F, W],
        [W, F, F, F, F, F, F, F, F, F, F, F, R, W],
        [W, R, F, F, F, F, F, F, F, F, F, F, R, W],
        [W, W, W, E, W, W, W, W, E, W, W, W, W, W],
        [W, B, F, F, W, T, C, W, F, F, B, F, S, W],
        [W, F, F, F, D, F, F, D, F, F, F, F, F, W],
        [W, W, D, W, W, F, H, W, W, D, W, W, W, W],
        [_, _, _, _, W, F, F, W, _, _, _, _, _, _],
        [_, _, _, _, W, W, D, W, _, _, _, _, _, _],
    ], npc_class="Bard", npc_count=5, description="A grand tavern with pillared hall and many rooms."),
]

# ================================================================
# RELIGIOUS BUILDINGS
# ================================================================

TEMPLES = [
    Blueprint("Roadside Shrine", "shrine", [
        [W, W, W, W, W],
        [W, F, A, F, W],
        [W, F, F, F, W],
        [W, W, D, W, W],
    ], npc_class="Cleric", npc_count=1, description="A small roadside shrine."),
    Blueprint("Village Chapel", "temple", [
        [W, W, W, W, W, W, W, W],
        [W, F, F, F, F, F, F, W],
        [N, F, F, F, F, F, F, N],
        [W, F, F, F, F, F, F, W],
        [W, F, F, A, F, F, F, W],
        [W, W, W, W, W, D, W, W],
    ], npc_class="Cleric", npc_count=1, description="A small village chapel with altar."),
    Blueprint("Cathedral", "temple", [
        [W, W, W, W, W, W, W, W, W, W, W, W, W, W],
        [W, M, M, P, M, M, M, M, M, M, P, M, M, W],
        [W, M, M, F, M, M, M, M, M, M, F, M, M, W],
        [W, P, F, F, F, F, F, F, F, F, F, F, P, W],
        [W, M, M, F, F, F, A, F, F, F, F, M, M, W],
        [W, M, M, F, F, F, F, F, F, F, F, M, M, W],
        [W, P, F, F, F, F, F, F, F, F, F, F, P, W],
        [W, M, M, F, F, F, F, F, F, F, F, M, M, W],
        [W, M, M, P, F, F, F, F, F, F, P, M, M, W],
        [W, W, W, W, W, E, F, F, E, W, W, W, W, W],
        [W, X, F, F, W, F, F, F, F, W, F, F, X, W],
        [W, F, F, C, D, F, F, F, F, D, C, F, F, W],
        [W, W, W, W, W, F, F, F, F, W, W, W, W, W],
        [_, _, _, _, W, W, D, D, W, W, _, _, _, _],
    ], npc_class="Cleric", npc_count=4, description="A grand cathedral with nave and side chapels."),
    Blueprint("Monastery", "temple", [
        [W, W, W, W, W, W, W, W, W, W, W, W],
        [W, F, F, F, F, F, F, F, F, F, F, W],
        [N, F, F, F, P, F, F, P, F, F, F, N],
        [W, F, F, F, F, F, A, F, F, F, F, W],
        [W, F, F, F, P, F, F, P, F, F, F, W],
        [W, W, W, E, W, W, W, W, E, W, W, W],
        [W, B, F, F, W, F, F, W, F, F, B, W],
        [W, F, F, F, D, F, F, D, F, F, F, W],
        [W, B, F, F, W, F, F, W, F, F, B, W],
        [W, W, W, W, W, T, X, W, W, W, W, W],
        [_, _, _, _, W, F, F, W, _, _, _, _],
        [_, _, _, _, W, W, D, W, _, _, _, _],
    ], npc_class="Monk", npc_count=4, description="A monastery with cloister and monk's cells."),
]

# ================================================================
# MILITARY BUILDINGS
# ================================================================

MILITARY = [
    Blueprint("Guard Post", "barracks", [
        [W, W, W, W, W, W],
        [W, F, F, F, F, W],
        [W, F, F, F, F, W],
        [W, C, F, F, C, W],
        [W, W, D, W, W, W],
    ], npc_class="Fighter", npc_count=2, description="A small guard post."),
    Blueprint("Large Barracks", "barracks", [
        [W, W, N, W, W, W, W, W, W, N, W, W],
        [W, B, F, F, W, B, F, F, W, F, F, W],
        [W, F, F, F, D, F, F, F, D, F, F, W],
        [W, B, F, F, W, B, F, F, W, F, F, W],
        [W, W, W, D, W, W, W, D, W, W, W, W],
        [W, F, F, F, F, F, F, F, F, F, F, W],
        [W, F, T, F, F, H, F, F, F, T, F, W],
        [W, F, F, F, P, F, F, P, F, F, F, W],
        [W, C, F, F, F, F, F, F, F, F, C, W],
        [W, W, W, W, W, D, D, W, W, W, W, W],
    ], npc_class="Fighter", npc_count=8, description="A large barracks with bunks and armoury."),
    Blueprint("Watchtower", "tower", [
        [W, W, W, W, W, W, W],
        [W, F, F, F, F, F, W],
        [W, F, F, S, F, F, W],
        [W, F, F, F, F, F, W],
        [W, F, F, F, F, C, W],
        [W, W, W, D, W, W, W],
    ], npc_class="Fighter", npc_count=2, description="A stone watchtower."),
    Blueprint("Armory", "shop", [
        [W, W, W, W, W, W, W, W],
        [W, F, F, F, F, F, F, W],
        [W, C, F, F, F, F, C, W],
        [W, F, F, V, F, F, F, W],
        [W, C, F, F, F, F, C, W],
        [W, F, F, F, F, F, F, W],
        [W, W, W, I, I, W, W, W],
    ], npc_class="Fighter", npc_count=1, description="An armory with iron gates."),
]

# ================================================================
# INDUSTRIAL
# ================================================================

INDUSTRIAL = [
    Blueprint("Smithy with Forge", "shop", [
        [W, W, W, W, W, W, W, W, W],
        [W, F, F, F, W, F, G, F, W],
        [W, F, V, F, D, F, F, F, W],
        [W, F, F, F, W, F, R, F, W],
        [W, C, F, R, W, W, W, W, W],
        [W, W, W, D, W, _, _, _, _],
    ], npc_class="Fighter", npc_count=1, description="A blacksmith's forge with anvil and fire."),
    Blueprint("Tannery", "shop", [
        [W, W, W, W, W, W, W, W],
        [W, F, F, F, F, F, F, W],
        [N, F, F, F, F, F, F, N],
        [W, F, R, F, F, R, F, W],
        [W, F, F, T, F, F, F, W],
        [W, R, F, F, F, F, R, W],
        [W, W, W, D, D, W, W, W],
    ], npc_count=1, description="A stinking tannery."),
    Blueprint("Brewery & Distillery", "shop", [
        [W, W, N, W, W, W, W, N, W, W],
        [W, F, F, F, F, F, F, F, F, W],
        [N, F, R, R, F, F, R, R, F, N],
        [W, F, F, F, F, F, F, F, F, W],
        [W, F, F, T, F, F, T, F, F, W],
        [W, R, F, F, F, F, F, F, R, W],
        [W, W, W, W, D, D, W, W, W, W],
    ], npc_count=2, description="A brewery with fermentation vats."),
    Blueprint("Mill", "shop", [
        [W, W, W, W, W, W],
        [W, F, F, F, F, W],
        [W, F, F, F, F, W],
        [W, F, T, F, F, W],
        [W, R, F, F, R, W],
        [W, W, D, W, W, W],
    ], npc_count=1, description="A grain mill."),
]

# ================================================================
# AGRICULTURAL
# ================================================================

AGRICULTURAL = [
    Blueprint("Farmstead", "house", [
        [W, W, N, W, W, W, N, W],
        [W, F, F, F, W, F, F, W],
        [N, F, F, F, D, F, B, N],
        [W, F, T, F, W, F, C, W],
        [W, F, H, F, W, W, W, W],
        [W, W, D, W, W, _, _, _],
    ], npc_class="Druid", npc_count=2, description="A working farmstead."),
    Blueprint("Large Stable", "stable", [
        [W, W, W, W, W, W, W, W, W, W],
        [W, F, F, W, F, F, W, F, F, W],
        [W, F, F, W, F, F, W, F, F, W],
        [W, F, F, W, F, F, W, F, F, W],
        [W, W, E, W, W, E, W, W, E, W],
        [W, F, F, F, F, F, F, F, F, W],
        [W, F, F, F, F, F, F, F, C, W],
        [W, W, W, W, D, D, W, W, W, W],
    ], npc_count=1, description="A large stable with horse stalls and archways."),
    Blueprint("Barn", "stable", [
        [W, W, W, W, W, W, W, W, W, W],
        [W, F, F, F, F, F, F, F, F, W],
        [W, F, F, F, F, F, F, F, F, W],
        [W, R, F, F, F, F, F, F, R, W],
        [W, F, F, F, F, F, F, F, F, W],
        [W, W, W, W, D, D, W, W, W, W],
    ], npc_count=0, description="A large hay barn."),
    Blueprint("Granary", "shop", [
        [W, W, W, W, W, W],
        [W, R, F, F, R, W],
        [W, F, F, F, F, W],
        [W, R, F, F, R, W],
        [W, F, F, F, F, W],
        [W, W, L, W, W, W],
    ], npc_count=1, description="A secured granary."),
]

# ================================================================
# NOBLE & CASTLE BUILDINGS
# ================================================================

NOBLE = [
    Blueprint("Manor House", "house", [
        [W, W, N, W, W, W, W, W, N, W, W, W],
        [W, Q, Q, F, F, W, F, F, F, Q, Q, W],
        [N, Q, Q, F, F, D, F, F, F, Q, Q, N],
        [W, F, F, T, F, W, F, F, T, F, F, W],
        [W, F, F, H, F, W, F, F, F, F, F, W],
        [W, W, D, W, W, W, W, W, D, W, W, W],
        [W, B, Q, F, W, F, F, W, F, Q, B, W],
        [W, F, Q, C, D, F, F, D, C, Q, F, W],
        [W, W, W, W, W, F, S, W, W, W, W, W],
        [_, _, _, _, W, F, F, W, _, _, _, _],
        [_, _, _, _, W, W, D, W, _, _, _, _],
    ], npc_class="Fighter", npc_count=4, description="A lord's manor with carpeted chambers and solar."),
    Blueprint("Castle Keep", "castle", [
        [W, W, W, W, W, W, W, W, W, W, W, W, W, W, W, W],
        [W, F, F, F, P, F, F, F, F, F, F, P, F, F, F, W],
        [W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W],
        [W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W],
        [W, P, F, F, F, F, F, K, F, F, F, F, F, F, P, W],
        [W, F, F, F, F, F, F, Q, F, F, F, F, F, F, F, W],
        [W, F, F, T, F, F, F, Q, F, F, F, T, F, F, F, W],
        [W, F, F, F, F, F, F, F, F, F, F, F, F, F, F, W],
        [W, W, W, W, E, W, W, W, W, W, E, W, W, W, W, W],
        [W, B, Q, F, F, W, X, X, W, F, F, Q, B, F, S, W],
        [W, F, Q, C, F, D, F, F, D, F, C, Q, F, F, F, W],
        [W, W, W, W, W, W, F, F, W, W, W, W, W, W, W, W],
        [W, F, F, F, F, W, F, H, W, F, T, F, F, F, F, W],
        [W, F, T, F, F, D, F, F, D, F, F, F, R, R, F, W],
        [W, F, F, F, F, W, W, D, W, W, W, W, W, W, W, W],
        [W, W, W, W, W, W, _, _, _, _, _, _, _, _, _, _],
    ], npc_class="Paladin", npc_count=8, description="A massive castle keep with throne room, library, and kitchen."),
    Blueprint("Gatehouse", "castle", [
        [W, W, W, W, W, W, W, W],
        [W, F, F, F, F, F, F, W],
        [W, F, F, S, F, F, F, W],
        [W, F, F, F, F, F, C, W],
        [W, W, I, I, I, I, W, W],
        [_, _, F, F, F, F, _, _],
        [_, _, F, F, F, F, _, _],
    ], npc_class="Fighter", npc_count=3, description="A fortified gatehouse with portcullis."),
]

# ================================================================
# CIVIC
# ================================================================

CIVIC = [
    Blueprint("Town Hall", "civic", [
        [W, W, N, W, W, W, W, N, W, W],
        [W, F, F, F, P, F, F, F, F, W],
        [N, F, F, F, F, F, F, F, F, N],
        [W, F, F, T, F, F, T, F, F, W],
        [W, F, F, F, P, F, F, F, F, W],
        [W, W, W, E, W, W, E, W, W, W],
        [W, F, F, F, W, T, F, F, C, W],
        [W, F, T, F, D, F, F, X, F, W],
        [W, F, F, C, W, W, W, W, W, W],
        [W, W, W, D, W, _, _, _, _, _],
    ], npc_count=2, description="The town hall with council chamber."),
    Blueprint("Jail & Courthouse", "civic", [
        [W, W, W, W, W, W, W, W, W, W],
        [W, F, F, F, F, F, F, F, F, W],
        [W, F, F, T, F, F, T, F, F, W],
        [W, F, F, F, F, F, F, F, F, W],
        [W, W, W, D, W, W, D, W, W, W],
        [W, F, F, F, W, F, F, F, F, W],
        [W, F, T, F, W, W, I, W, W, W],
        [W, F, F, C, W, F, F, F, F, W],
        [W, W, D, W, W, F, F, F, B, W],
        [_, _, _, _, W, W, W, W, W, W],
    ], npc_class="Fighter", npc_count=3, description="A courthouse with jail cells."),
    Blueprint("Guildhall", "civic", [
        [W, W, N, W, W, W, W, W, N, W, W, W],
        [W, F, F, F, P, F, F, F, F, P, F, W],
        [N, F, F, F, F, F, F, F, F, F, F, N],
        [W, F, T, F, F, F, F, F, F, F, T, W],
        [W, P, F, F, F, F, F, F, F, F, P, W],
        [W, F, F, T, F, F, F, F, T, F, F, W],
        [W, F, F, F, F, F, F, F, F, F, F, W],
        [W, R, F, F, F, F, F, F, F, F, R, W],
        [W, W, W, W, E, D, D, E, W, W, W, W],
    ], npc_count=3, description="A large guildhall with pillared hall."),
]

# ================================================================
# MASTER LIBRARY
# ================================================================

BLUEPRINT_LIBRARY = {
    "primitive": PRIMITIVE,
    "tribal": TRIBAL,
    "roman": ROMAN,
    "greek": GREEK,
    "medieval_house": MEDIEVAL_HOUSES,
    "medieval_commercial": MEDIEVAL_COMMERCIAL,
    "tavern": TAVERNS,
    "temple": TEMPLES,
    "military": MILITARY,
    "industrial": INDUSTRIAL,
    "agricultural": AGRICULTURAL,
    "noble": NOBLE,
    "civic": CIVIC,
}

ALL_BLUEPRINTS = []
for category, blueprints in BLUEPRINT_LIBRARY.items():
    ALL_BLUEPRINTS.extend(blueprints)


def get_blueprints_for_settlement(settlement_kind: str,
                                   wealth: float = 1.0,
                                   culture: str = "medieval") -> List[Blueprint]:
    """Get blueprints appropriate for a settlement type and culture."""
    if culture == "primitive":
        base = PRIMITIVE[:]
        if settlement_kind != "hamlet":
            base += TRIBAL
        return base
    elif culture == "tribal":
        base = TRIBAL[:] + PRIMITIVE[:2]
        if settlement_kind in ("town", "city"):
            base += [TAVERNS[0]]
        return base
    elif culture == "roman":
        base = ROMAN[:] + MEDIEVAL_HOUSES[3:]
        if settlement_kind in ("town", "city"):
            base += TAVERNS + TEMPLES + CIVIC
        return base
    elif culture == "greek":
        base = GREEK[:] + MEDIEVAL_HOUSES[2:]
        if settlement_kind in ("town", "city"):
            base += TEMPLES + CIVIC
        return base

    # Default: medieval
    if settlement_kind == "hamlet":
        candidates = PRIMITIVE[:3] + MEDIEVAL_HOUSES[:2] + AGRICULTURAL[:2]
    elif settlement_kind == "village":
        candidates = MEDIEVAL_HOUSES[:3] + AGRICULTURAL + [TAVERNS[0], TEMPLES[0], INDUSTRIAL[3]]
    elif settlement_kind == "town":
        candidates = (MEDIEVAL_HOUSES + MEDIEVAL_COMMERCIAL + TAVERNS[:2] +
                     INDUSTRIAL + [TEMPLES[1], MILITARY[0], CIVIC[0]])
        if wealth > 1.2:
            candidates += NOBLE[:1] + CIVIC[1:]
    elif settlement_kind == "city":
        candidates = (MEDIEVAL_HOUSES + MEDIEVAL_COMMERCIAL + TAVERNS +
                     INDUSTRIAL + TEMPLES + MILITARY + CIVIC + NOBLE)
    elif settlement_kind == "castle":
        candidates = NOBLE + MILITARY + [TEMPLES[3], TAVERNS[1]]
    else:
        candidates = MEDIEVAL_HOUSES[:2]

    return candidates


def pick_blueprint(settlement_kind: str, wealth: float = 1.0,
                   culture: str = "medieval", rng: random.Random = None) -> Blueprint:
    if rng is None:
        rng = random.Random()
    candidates = get_blueprints_for_settlement(settlement_kind, wealth, culture)
    if not candidates:
        candidates = MEDIEVAL_HOUSES[:2]
    return rng.choice(candidates)


def library_stats() -> str:
    total = len(ALL_BLUEPRINTS)
    categories = len(BLUEPRINT_LIBRARY)
    sizes = [bp.width * bp.height for bp in ALL_BLUEPRINTS]
    has_pillar = sum(1 for bp in ALL_BLUEPRINTS
                    if any(PILLAR in row for row in bp.tiles))
    has_fireplace = sum(1 for bp in ALL_BLUEPRINTS
                       if any(FIREPLACE in row for row in bp.tiles))
    has_altar = sum(1 for bp in ALL_BLUEPRINTS
                   if any(ALTAR in row for row in bp.tiles))
    has_stairs = sum(1 for bp in ALL_BLUEPRINTS
                    if any(STAIRS_UP in row or STAIRS_DOWN in row for row in bp.tiles))
    return (f"Blueprint Library: {total} designs across {categories} categories, "
            f"sizes {min(sizes)}-{max(sizes)} tiles. "
            f"Features: {has_pillar} with pillars, {has_fireplace} with fireplaces, "
            f"{has_altar} with altars, {has_stairs} with stairs")
