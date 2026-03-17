"""Base Entity class for all game entities."""

import math


class Entity:
    """Base class for all game entities."""
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.hp = 100
        self.max_hp = 100
        self.alive = True
        self.facing = (0, 1)  # direction facing (dx, dy)
        self.body = None  # Body instance (set by subclass constructors)

    def dist_to(self, other) -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        return math.sqrt(dx * dx + dy * dy)

    def dist_to_pos(self, x: float, y: float) -> float:
        dx = self.x - x
        dy = self.y - y
        return math.sqrt(dx * dx + dy * dy)

    def take_damage(self, amount: int) -> int:
        actual = max(0, amount)
        self.hp = max(0, self.hp - actual)
        if self.hp <= 0:
            self.alive = False
        return actual

    def heal(self, amount: int):
        self.hp = min(self.max_hp, self.hp + amount)
