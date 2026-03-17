"""
Party/companion system - recruit NPCs, manage party, companions follow player.
"""

import random
import math
from typing import List, Optional
from game.settings import *
from game.data.dnd import ability_modifier


class PlayerParty:
    """Manages the player's adventuring party."""

    MAX_SIZE = 4  # player + 3 companions

    def __init__(self):
        self.companions: List = []  # NPC references
        self.pending_recruit: Optional[object] = None

    @property
    def size(self) -> int:
        return 1 + len(self.companions)  # player + companions

    @property
    def is_full(self) -> bool:
        return self.size >= self.MAX_SIZE

    def can_recruit(self, npc) -> tuple:
        """Check if an NPC can be recruited. Returns (can_recruit, reason)."""
        if self.is_full:
            return False, "Your party is full (max 4)."
        if npc in self.companions:
            return False, f"{npc.name} is already in your party."
        if not npc.alive:
            return False, f"{npc.name} is dead."
        if npc.player_relationship < 10:
            return False, f"{npc.name} doesn't trust you enough (need +10 relationship)."
        return True, ""

    def try_recruit(self, npc, player_cha: int) -> tuple:
        """Attempt to recruit an NPC. Returns (success, message)."""
        can, reason = self.can_recruit(npc)
        if not can:
            return False, reason

        # CHA check: d20 + CHA mod vs DC based on NPC personality
        cha_mod = ability_modifier(player_cha)
        roll = random.randint(1, 20) + cha_mod
        dc = 12 - (npc.player_relationship // 10)  # easier with higher relationship
        dc = max(5, min(20, dc))

        if roll >= dc:
            self.add_companion(npc)
            return True, f"{npc.name} joins your party! (rolled {roll} vs DC {dc})"
        else:
            npc.player_relationship = max(-100, npc.player_relationship - 2)
            return False, f"{npc.name} declines. (rolled {roll} vs DC {dc})"

    def add_companion(self, npc):
        """Add an NPC as a companion."""
        self.companions.append(npc)
        npc.current_action = "following_player"
        npc.current_goal = "follow and fight with the player"
        npc.party_id = "player_party"
        npc.party_role = "member"
        npc.add_memory("social", "Joined the player's adventuring party!", 5)

    def remove_companion(self, npc, reason: str = "left the party"):
        """Remove a companion from the party."""
        if npc in self.companions:
            self.companions.remove(npc)
            npc.current_action = ""
            npc.current_goal = ""
            npc.party_id = None
            npc.party_role = ""
            npc.add_memory("social", f"Left the player's party: {reason}", 4)

    def dismiss(self, index: int) -> Optional[str]:
        """Dismiss companion by index. Returns name or None."""
        if 0 <= index < len(self.companions):
            npc = self.companions[index]
            name = npc.name
            self.remove_companion(npc, "dismissed by player")
            return name
        return None

    def update(self, dt: float, player, world):
        """Update companion positions - they follow the player."""
        for i, companion in enumerate(self.companions):
            if not companion.alive:
                self.remove_companion(companion, "died")
                continue

            # Follow player with offset
            angle = (2 * math.pi * (i + 1)) / (len(self.companions) + 1)
            target_x = player.x + math.cos(angle) * 2.0
            target_y = player.y + math.sin(angle) * 2.0

            dx = target_x - companion.x
            dy = target_y - companion.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist > 2.5:
                # Move toward formation position
                speed = player.speed * 1.1  # slightly faster to keep up
                nx = dx / dist
                ny = dy / dist
                move_x = nx * speed * dt
                move_y = ny * speed * dt

                new_x = companion.x + move_x
                if world.is_walkable(int(new_x), int(companion.y)):
                    companion.x = new_x

                new_y = companion.y + move_y
                if world.is_walkable(int(companion.x), int(new_y)):
                    companion.y = new_y

                companion.facing = (nx, ny)

            # Keep companion's action state
            companion.state = "walking" if dist > 2.5 else "idle"
            companion.current_action = "following_player"

    def get_allies_for_combat(self) -> list:
        """Get living companions for tactical combat."""
        return [c for c in self.companions if c.alive]

    def get_party_info(self) -> str:
        """Get party summary for UI."""
        if not self.companions:
            return "Solo"
        names = [f"{c.name} ({c.race} {c.char_class} Lv{c.level})" for c in self.companions if c.alive]
        return f"Party ({self.size}/{self.MAX_SIZE}): " + ", ".join(names)
