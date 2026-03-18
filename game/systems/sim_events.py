"""Simulation events — world events and spawning."""

import random
import time
from typing import List, Dict, Any
from game.core.npc import NPC
from game.core.player import Player
from game.settings import *


class WorldEvent:
    """A random event affecting the world."""
    def __init__(self, name: str, description: str, x: float, y: float,
                 radius: float, duration: float, effects: Dict[str, Any]):
        self.name = name
        self.description = description
        self.x = x
        self.y = y
        self.radius = radius
        self.duration = duration
        self.effects = effects
        self.started = time.time()
        self.announced = False

    def affects(self, entity) -> bool:
        dx = entity.x - self.x
        dy = entity.y - self.y
        return dx * dx + dy * dy <= self.radius * self.radius



class SimEventsMixin:
    """World event methods."""

    def _update_events(self, dt: float, npcs: List[NPC], player: Player):
        self.event_timer -= dt

        if self.event_timer <= 0:
            self._spawn_event(npcs)
            self.event_timer = random.uniform(30, 90)

        # Update active events
        remaining = []
        for evt in self.events:
            evt.duration -= dt
            if evt.duration > 0:
                remaining.append(evt)

                # Earthquake: destroy some built structures
                if evt.effects.get("destroy_chance") and evt.duration > 5:
                    for _ in range(2):
                        rx = int(evt.x + random.uniform(-evt.radius, evt.radius))
                        ry = int(evt.y + random.uniform(-evt.radius, evt.radius))
                        if (0 <= rx < self.world.width and 0 <= ry < self.world.height and
                            self.world.tiles[ry][rx] in (BUILT_WALL, BUILT_FLOOR)):
                            if random.random() < evt.effects["destroy_chance"]:
                                self.world.modify_tile(rx, ry, GRASS)
        self.events = remaining

    def _spawn_event(self, npcs: List[NPC]):
        template = random.choice(EVENT_TEMPLATES)
        # Place near a village
        villages = [s for s in self.world.structures if s.kind == "village"]
        if villages:
            v = random.choice(villages)
            x, y = float(v.x), float(v.y)
        else:
            x = random.uniform(20, self.world.width - 20)
            y = random.uniform(20, self.world.height - 20)

        evt = WorldEvent(
            name=template["name"],
            description=template["desc"],
            x=x, y=y,
            radius=template["radius"],
            duration=template["duration"],
            effects=dict(template["effects"]),
        )
        self.events.append(evt)
        self.event_log.append(f"EVENT: {evt.name} - {evt.description}")

        # NPCs who witness it add to known_info
        for npc in npcs:
            if npc.alive and evt.affects(npc):
                npc.known_info.append(f"{evt.name} is happening nearby")
                npc.add_memory("event", evt.description, 3)

    # ---- DAILY LIFE / ECONOMY ----

