"""
Building ownership, door locking, trespass detection, and multi-floor system.
"""

import random
import math
from typing import Dict, List, Optional, Tuple
from game.settings import *


class BuildingInstance:
    """A placed building in the world with ownership and state."""
    __slots__ = ('name', 'kind', 'x', 'y', 'width', 'height',
                 'owner_name', 'is_public', 'locked', 'floor',
                 'upper_floor', 'occupants')

    def __init__(self, name: str, kind: str, x: int, y: int, w: int, h: int):
        self.name = name
        self.kind = kind
        self.x = x
        self.y = y
        self.width = w
        self.height = h
        self.owner_name = ""
        self.is_public = kind in ("tavern", "temple", "shop", "military", "utility")
        self.locked = kind == "house"  # houses locked by default
        self.floor = 0  # current floor (0 = ground)
        self.upper_floor = None  # 2D tile array for upper floor, if any
        self.occupants: List[str] = []  # NPC names

    def contains(self, px: float, py: float) -> bool:
        return (self.x <= px < self.x + self.width and
                self.y <= py < self.y + self.height)


class BuildingSystem:
    """Manages building ownership, access control, and trespass."""

    def __init__(self):
        self.buildings: List[BuildingInstance] = []
        self.trespass_warnings: Dict[str, float] = {}  # player warned at building

    def register_building(self, name: str, kind: str, x: int, y: int,
                          w: int, h: int, owner: str = "") -> BuildingInstance:
        bld = BuildingInstance(name, kind, x, y, w, h)
        bld.owner_name = owner
        self.buildings.append(bld)
        return bld

    def assign_owners(self, npcs: list):
        """Assign NPC owners to private buildings."""
        unassigned = [b for b in self.buildings if not b.owner_name and not b.is_public]
        available_npcs = [n for n in npcs if n.alive]
        # Pre-build set of NPCs who already own buildings (O(n) instead of O(n*m))
        owners = {b.owner_name for b in self.buildings if b.owner_name}

        for bld in unassigned:
            best_npc = None
            best_dist = float('inf')
            for npc in available_npcs:
                if npc.name in owners:
                    continue
                dx = npc.x - (bld.x + bld.width / 2)
                dy = npc.y - (bld.y + bld.height / 2)
                dist = dx * dx + dy * dy
                if dist < best_dist:
                    best_dist = dist
                    best_npc = npc

            if best_npc:
                bld.owner_name = best_npc.name
                bld.occupants.append(best_npc.name)
                owners.add(best_npc.name)

    def get_building_at(self, x: float, y: float) -> Optional[BuildingInstance]:
        for bld in self.buildings:
            if bld.contains(x, y):
                return bld
        return None

    def check_trespass(self, player, npcs: list, game_time: float) -> Optional[str]:
        """Check if player is trespassing. Returns warning message or None."""
        bld = self.get_building_at(player.x, player.y)
        if not bld:
            return None

        if bld.is_public:
            return None

        if not bld.owner_name:
            return None

        # Check if owner is nearby (within 30 tiles) and reacts
        import math
        for npc in npcs:
            if npc.name != bld.owner_name or not npc.alive:
                continue
            # Owner must be nearby to notice trespassing
            dist = math.sqrt((npc.x - player.x)**2 + (npc.y - player.y)**2)
            if dist > 30:
                continue
            if True:
                if npc.player_relationship >= 20:
                    return None  # friend, welcome
                # Trespass!
                key = bld.name
                last_warning = self.trespass_warnings.get(key, 0)
                if game_time - last_warning > 10.0:
                    self.trespass_warnings[key] = game_time
                    # Owner reacts
                    npc.player_relationship = max(-100, npc.player_relationship - 5)
                    npc.add_memory("conflict", "The player entered my home uninvited!", 4)
                    return f"{npc.name}: Hey! This is my home! Get out!"
                break

        return None

    def try_unlock_door(self, x: int, y: int, world_tiles: list,
                        player_dex: int, has_lockpick: bool) -> Tuple[bool, str]:
        """Try to unlock a locked door. Returns (success, message)."""
        if world_tiles[y][x] != LOCKED_DOOR:
            return False, ""

        bld = self.get_building_at(float(x), float(y))

        if has_lockpick:
            # Lockpicking: DC 15, roll d20 + DEX mod
            from game.data.dnd import ability_modifier
            dex_mod = ability_modifier(player_dex)
            roll = random.randint(1, 20) + dex_mod
            dc = 15

            if roll >= dc:
                world_tiles[y][x] = DOOR
                return True, f"Lock picked! (rolled {roll} vs DC {dc})"
            else:
                return False, f"Failed to pick lock (rolled {roll} vs DC {dc})"
        else:
            # Check if owner is friendly
            if bld and bld.owner_name:
                return False, f"This door is locked. It belongs to {bld.owner_name}."
            return False, "This door is locked. You need a lockpick."

    def get_building_info(self, x: float, y: float) -> str:
        """Get info about the building at position."""
        bld = self.get_building_at(x, y)
        if not bld:
            return ""
        owner = f", owned by {bld.owner_name}" if bld.owner_name else ""
        access = "public" if bld.is_public else ("locked" if bld.locked else "private")
        return f"{bld.name} ({bld.kind}, {access}{owner})"
