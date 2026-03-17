"""Core entities: Player, NPC, Creature, Items."""
from game.core.entity import Entity
from game.core.items import Item, ITEMS, FOOD_ITEMS, DRINK_ITEMS, PROFESSION_STARTER, make_item
from game.core.player import Player
from game.core.npc import NPC, DialogLine
from game.core.creature import Creature
