"""
Churchyards and Graves System — handles burial of dead NPCs.

When an NPC dies near a settlement with a temple, they are buried in the
churchyard (a few tiles near the temple). NPCs who die in the wilderness
have their bodies left where they fell. Mourner NPCs visit graves of
loved ones.
"""

import math
import random
from typing import List, Dict, Optional, Tuple


# Epitaph templates by death type
EPITAPHS = {
    "natural": [
        "Rest in peace, {name}.",
        "Here lies {name}. Gone but not forgotten.",
        "{name} — a life well lived.",
        "In loving memory of {name}.",
        "{name}, faithful {profession}, rests here.",
    ],
    "violent": [
        "Here lies {name}, taken too soon.",
        "{name} — fell in battle.",
        "Slain but not forgotten: {name}.",
        "{name} gave their life bravely.",
        "In memoriam: {name}, lost to violence.",
    ],
    "disease": [
        "{name} — claimed by plague.",
        "Rest now, {name}. The sickness has passed.",
        "Here lies {name}, taken by illness.",
        "{name} succumbed to disease. May they find peace.",
    ],
    "starvation": [
        "{name} — hunger took what life could not.",
        "Here lies {name}, who starved in lean times.",
        "{name}, lost to famine.",
    ],
    "dehydration": [
        "{name} — thirsted unto death.",
        "Here lies {name}, parched and perished.",
    ],
    "wounds": [
        "Here lies {name}, who fell to mortal wounds.",
        "{name} — scarred in life, at peace in death.",
    ],
}

# Burial type by settlement culture (can be extended with religion system)
BURIAL_TYPES = {
    "hamlet": "ground",
    "village": "ground",
    "town": "ground",
    "city": "ground",
    "castle": "ground",
}


class Grave:
    """A grave marker in the world."""

    __slots__ = ('x', 'y', 'npc_name', 'profession', 'death_time',
                 'death_day', 'death_type', 'epitaph', 'buried',
                 'burial_type', 'visited', 'flowers', 'settlement_name',
                 'age_at_death')

    def __init__(self, x: int, y: int, npc_name: str, profession: str,
                 death_time: str, death_day: int, death_type: str,
                 epitaph: str, settlement_name: str = "",
                 age_at_death: int = 0):
        self.x = x
        self.y = y
        self.npc_name = npc_name
        self.profession = profession
        self.death_time = death_time
        self.death_day = death_day
        self.death_type = death_type
        self.epitaph = epitaph
        self.buried = True  # False = body left unburied in wilderness
        self.burial_type = "ground"  # ground, cremation, sea, mass_grave
        self.visited = False  # has player visited this grave
        self.flowers = 0  # decorations placed by mourners
        self.settlement_name = settlement_name
        self.age_at_death = age_at_death


class BurialSystem:
    """Manages death, burial, churchyards, and mourning."""

    def __init__(self):
        self.graves: List[Grave] = []
        self.churchyards: Dict[str, List[Tuple[int, int]]] = {}
        # settlement_name -> list of available grave positions
        self._churchyard_next_index: Dict[str, int] = {}
        # Track mourning NPCs: npc_name -> (grave, timer)
        self._mourners: Dict[str, Tuple[Grave, float]] = {}

    def initialize_churchyards(self, world):
        """Scan settlements for temples and designate churchyard areas nearby."""
        if not hasattr(world, 'plan'):
            return

        for sp in world.plan.settlements:
            temple_pos = None
            # Find the temple building in this settlement
            for bld in sp.buildings:
                bname = bld.get('name', '').lower()
                if 'temple' in bname or 'church' in bname or 'chapel' in bname:
                    temple_pos = (bld['x'], bld['y'], bld['w'], bld['h'])
                    break

            if temple_pos is None:
                continue

            # Designate a graveyard area: 3x4 grid of plots east of the temple
            tx, ty, tw, th = temple_pos
            yard_x = tx + tw + 1  # just east of the temple
            yard_y = ty

            positions = []
            for row in range(4):
                for col in range(3):
                    gx = yard_x + col * 2  # spacing of 2 tiles between graves
                    gy = yard_y + row * 2
                    # Check that tile is walkable ground (not water, wall, etc.)
                    if (0 <= gx < world.width and 0 <= gy < world.height):
                        positions.append((gx, gy))

            if positions:
                self.churchyards[sp.name] = positions
                self._churchyard_next_index[sp.name] = 0

    def _find_nearest_churchyard(self, x: float, y: float, max_dist: float = 60.0
                                  ) -> Optional[str]:
        """Find the nearest settlement with a churchyard within max_dist tiles."""
        best_name = None
        best_dist = max_dist
        for name, positions in self.churchyards.items():
            if not positions:
                continue
            # Use first grave position as proxy for churchyard location
            cx, cy = positions[0]
            dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_name = name
        return best_name

    def _get_next_grave_pos(self, settlement_name: str) -> Optional[Tuple[int, int]]:
        """Get the next available grave position in a churchyard."""
        positions = self.churchyards.get(settlement_name, [])
        if not positions:
            return None

        idx = self._churchyard_next_index.get(settlement_name, 0)
        if idx < len(positions):
            self._churchyard_next_index[settlement_name] = idx + 1
            return positions[idx]

        # Churchyard is full — expand by adding more positions
        last_x, last_y = positions[-1]
        new_pos = (last_x + 2, last_y)
        positions.append(new_pos)
        self._churchyard_next_index[settlement_name] = len(positions)
        return new_pos

    def on_death(self, npc, death_type: str, game_time_str: str,
                 game_day: int, world) -> Optional[Grave]:
        """Handle burial of a dead NPC. Returns the created Grave or None."""
        npc_name = npc.name
        profession = getattr(npc, 'profession', 'unknown')
        age = int(getattr(npc, 'age', 30))

        # Determine if near a churchyard
        settlement_name = self._find_nearest_churchyard(npc.x, npc.y)

        # Map cause strings to epitaph categories
        death_category = death_type
        if death_category not in EPITAPHS:
            if death_category in ("wounds", "combat"):
                death_category = "violent"
            else:
                death_category = "natural"

        # Generate epitaph
        templates = EPITAPHS.get(death_category, EPITAPHS["natural"])
        epitaph = random.choice(templates).format(name=npc_name,
                                                   profession=profession)

        if settlement_name:
            # Bury in churchyard
            pos = self._get_next_grave_pos(settlement_name)
            if pos:
                gx, gy = pos
                grave = Grave(gx, gy, npc_name, profession,
                              game_time_str, game_day, death_type,
                              epitaph, settlement_name, age)
                grave.buried = True
                grave.burial_type = BURIAL_TYPES.get(
                    self._get_settlement_kind(settlement_name, world),
                    "ground")

                # Place gravestone tile on the world
                from game.settings import GRAVESTONE
                if 0 <= gy < world.height and 0 <= gx < world.width:
                    world.tiles[gy][gx] = GRAVESTONE

                self.graves.append(grave)
                return grave

        # Wilderness death — body left where they fell
        gx, gy = int(npc.x), int(npc.y)
        grave = Grave(gx, gy, npc_name, profession,
                      game_time_str, game_day, death_type,
                      epitaph, "", age)
        grave.buried = False
        grave.burial_type = "none"
        self.graves.append(grave)
        return grave

    def _get_settlement_kind(self, settlement_name: str, world) -> str:
        """Get the kind (hamlet, village, etc.) of a settlement by name."""
        if hasattr(world, 'plan'):
            for sp in world.plan.settlements:
                if sp.name == settlement_name:
                    return sp.kind
        for s in world.structures:
            if s.name == settlement_name:
                return s.kind
        return "village"

    def get_grave_at(self, x: float, y: float, radius: float = 2.0
                     ) -> Optional[Grave]:
        """Get the nearest grave within radius of a position."""
        best = None
        best_dist = radius
        for grave in self.graves:
            dist = math.sqrt((x - grave.x) ** 2 + (y - grave.y) ** 2)
            if dist < best_dist:
                best_dist = dist
                best = grave
        return best

    def get_grave_info(self, grave: Grave) -> str:
        """Get a multi-line description of a grave for the examine UI."""
        lines = []
        if grave.buried:
            marker = "Gravestone" if grave.burial_type == "ground" else "Memorial"
            lines.append(f"[{marker}]")
        else:
            lines.append("[Unburied Body]")

        lines.append(f"  {grave.npc_name}, {grave.profession}")
        if grave.age_at_death > 0:
            lines.append(f"  Age at death: {grave.age_at_death}")
        lines.append(f"  Cause: {grave.death_type}")
        lines.append(f"  {grave.epitaph}")

        if grave.settlement_name:
            lines.append(f"  Buried at: {grave.settlement_name}")
        else:
            lines.append("  Left in the wilderness")

        if grave.flowers > 0:
            lines.append(f"  Flowers: {grave.flowers}")

        return "\n".join(lines)

    def update(self, dt: float, game_day: int, npcs: list,
               social_system=None):
        """Update mourning behavior. NPCs who lost loved ones visit graves."""
        # Only run mourner logic every few seconds
        if not hasattr(self, '_mourn_timer'):
            self._mourn_timer = 0.0
        self._mourn_timer += dt
        if self._mourn_timer < 10.0:
            return
        self._mourn_timer = 0.0

        if not self.graves or social_system is None:
            return

        # Check each grave for potential mourners
        for grave in self.graves:
            if not grave.buried:
                continue
            # Find NPCs who had a relationship with the deceased
            for npc in npcs:
                if not npc.alive:
                    continue
                if npc.name in self._mourners:
                    continue  # already mourning

                # Check social relationship
                rel = social_system.get_rel(npc.name, grave.npc_name)
                affinity = getattr(rel, 'affinity', 0)

                # Only close friends/family mourn (affinity > 30)
                if affinity <= 30:
                    continue

                # Random chance to visit (don't all rush at once)
                if random.random() > 0.05:
                    continue

                # Set NPC to visit the grave
                dist = math.sqrt((npc.x - grave.x) ** 2 +
                                 (npc.y - grave.y) ** 2)
                if dist < 80:  # only if reasonably close
                    self._mourners[npc.name] = (grave, 15.0)
                    # Set NPC target to grave
                    npc.target_x = float(grave.x)
                    npc.target_y = float(grave.y)
                    npc.current_action = f"mourning {grave.npc_name}"
                    # Set sad emotion
                    npc.emotion_state = "sad"

        # Update active mourners
        to_remove = []
        for npc_name, (grave, timer) in self._mourners.items():
            timer -= dt
            if timer <= 0:
                to_remove.append(npc_name)
                # Place flowers sometimes
                if random.random() < 0.3:
                    grave.flowers += 1
                grave.visited = True
            else:
                self._mourners[npc_name] = (grave, timer)

        for name in to_remove:
            del self._mourners[name]
            # Clear mourning state from NPC
            for npc in npcs:
                if npc.name == name and npc.alive:
                    if npc.current_action and "mourning" in npc.current_action:
                        npc.current_action = None
                    break
