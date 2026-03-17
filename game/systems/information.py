"""
Information system: knowledge spreading, gossip, news, trade intelligence.

Instead of broadcasting all events to the player's screen, information is:
1. Known by individuals who witnessed or were involved
2. Spread through conversation as gossip/news
3. Spread by specialists (town criers, guards, merchants)
4. Valuable and tradeable
5. Used by NPCs to make decisions

The player only sees events they witness directly or hear about from NPCs.
"""

import random
import math
from typing import Dict, List, Optional, Tuple


class InfoItem:
    """A piece of information that can be known, shared, and traded."""
    __slots__ = ('text', 'category', 'importance', 'day_created', 'source',
                 'location', 'value', 'spread_count')

    def __init__(self, text: str, category: str, importance: int = 1,
                 day: int = 0, source: str = "", location: str = ""):
        self.text = text
        self.category = category  # "combat", "trade", "politics", "gossip", "law", "death", "birth"
        self.importance = importance  # 1-5
        self.day_created = day
        self.source = source
        self.location = location
        self.value = importance * 2  # gold value for trading info
        self.spread_count = 0


# Who spreads what category of information
INFO_SPREADERS = {
    "combat":   ["guard", "knight", "Fighter", "Paladin", "Ranger"],
    "trade":    ["Merchant", "Rogue", "Bard"],
    "politics": ["duke", "lord", "monarch", "Bard"],
    "gossip":   ["Bard", "Rogue", "all"],  # everyone gossips
    "law":      ["guard", "knight", "monarch", "duke"],
    "death":    ["Cleric", "all"],
    "birth":    ["all"],
    "weather":  ["Ranger", "Druid", "Farmer"],
    "monster":  ["Ranger", "guard", "Fighter"],
    "technology": ["Wizard", "Scholar", "Cleric"],
}


class InformationSystem:
    """Manages information flow through the world."""

    def __init__(self):
        # Global news feed (recent world events)
        self.world_news: List[InfoItem] = []
        # Player's known information
        self.player_known: List[InfoItem] = []
        # Debug log (all events, for development monitoring)
        self.debug_log: List[str] = []
        self.spread_timer = 0.0

    def create_event(self, text: str, category: str, importance: int,
                     day: int, source: str, location: str,
                     witnesses: List = None, npcs: List = None):
        """Create a world event. Only witnesses know about it initially."""
        info = InfoItem(text, category, importance, day, source, location)
        self.world_news.append(info)

        # Debug log always gets everything
        self.debug_log.append(f"[{category}] {text}")
        if len(self.debug_log) > 500:
            self.debug_log = self.debug_log[-250:]

        # Only witnesses learn about it
        if witnesses:
            for npc in witnesses:
                if hasattr(npc, 'known_info'):
                    if text not in npc.known_info:
                        npc.known_info.append(text)
                        if len(npc.known_info) > 30:
                            npc.known_info = npc.known_info[-30:]

        # Keep world news manageable
        if len(self.world_news) > 200:
            # Keep important news longer
            self.world_news = [n for n in self.world_news if n.importance >= 3] + \
                             self.world_news[-50:]

    def player_witnesses(self, text: str, category: str, importance: int = 1,
                         day: int = 0):
        """Player directly witnesses an event - show on screen."""
        info = InfoItem(text, category, importance, day, "witnessed", "")
        self.player_known.append(info)
        if len(self.player_known) > 100:
            self.player_known = self.player_known[-100:]

    def update(self, dt: float, npcs: list, player, spatial_grid, day: int):
        """NPCs spread information to each other through conversation."""
        self.spread_timer += dt
        if self.spread_timer < 30.0:
            return
        self.spread_timer = 0.0

        # NPCs near the player share info with player
        if spatial_grid:
            nearby = spatial_grid.get_nearby(player.x, player.y, 5)
            for npc in nearby:
                if not hasattr(npc, 'known_info') or not npc.known_info:
                    continue
                # Share one piece of info the player doesn't know
                for info_text in npc.known_info[-5:]:
                    if not any(pk.text == info_text for pk in self.player_known):
                        self.player_witnesses(
                            f"{npc.name}: \"{info_text}\"", "gossip", 1, day)
                        break

        # NPCs spread info to each other (handled by social system conversations)

    def filter_events_for_player(self, all_events: List[str], player,
                                 npcs: list, radius: float = 15) -> List[Tuple[str, Tuple]]:
        """Filter world events - player only sees what they can witness.
        Returns list of (message, color) tuples."""
        visible = []
        for event_text in all_events:
            # Debug log gets everything
            self.debug_log.append(event_text)

            # Player only sees events near them or about them
            is_nearby = False
            is_about_player = "player" in event_text.lower()

            # Check if any mentioned NPC is near player
            for npc in npcs:
                if npc.name in event_text and npc.alive:
                    if player.dist_to(npc) < radius:
                        is_nearby = True
                        break

            if is_nearby or is_about_player:
                # Determine color
                if "died" in event_text.lower() or "attack" in event_text.lower():
                    color = (220, 50, 50)
                elif "born" in event_text.lower() or "heal" in event_text.lower():
                    color = (50, 200, 50)
                elif "trade" in event_text.lower() or "caravan" in event_text.lower():
                    color = (230, 150, 40)
                elif "discover" in event_text.lower() or "learned" in event_text.lower():
                    color = (100, 140, 200)
                else:
                    color = (180, 180, 190)
                visible.append((event_text, color))

        return visible
