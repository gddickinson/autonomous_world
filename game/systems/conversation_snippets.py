"""Conversation snippets — overhear NPC-NPC conversations near the player.

When two NPCs interact within 8 tiles of the player, generate a 1-line
dialog snippet and queue it for display as floating text + combat log entry.
"""

import random
import time
from typing import List, Optional, Tuple

from game.core.npc import NPC


# ================================================================
# SNIPPET TEMPLATES BY INTERACTION TYPE
# ================================================================

GOSSIP_TEMPLATES = [
    "Did you hear about {topic}?",
    "They say {topic}...",
    "I heard that {topic}.",
    "Can you believe {topic}?",
    "Word around town is {topic}.",
    "Everyone's talking about {topic}!",
    "Between you and me, {topic}.",
]

TEACHING_TEMPLATES = [
    "Let me show you how to {skill}.",
    "The trick to {skill} is patience.",
    "Watch closely -- this is how you {skill}.",
    "I learned {skill} from my mentor.",
    "You need to practice {skill} more.",
    "Here's the secret to {skill}...",
]

TRADE_TEMPLATES = [
    "I'll give you {price} gold for that {item}.",
    "How about {price} gold for the {item}?",
    "That {item} is worth at least {price} gold.",
    "I've been looking for a {item}. {price} gold?",
    "Would you take {price} gold for your {item}?",
]

FOOD_SHARING_TEMPLATES = [
    "You look hungry -- here, take this.",
    "Have some food, friend.",
    "You haven't eaten? Take this, please.",
    "No friend of mine goes hungry.",
]

COMFORT_TEMPLATES = [
    "Things will get better, I promise.",
    "I'm here for you, friend.",
    "Don't lose hope. We'll get through this.",
    "You're not alone in this.",
]

WARNING_TEMPLATES = [
    "Be careful near {location} -- it's dangerous.",
    "Stay away from {location}, I heard {threat}.",
    "Watch your back around {location}.",
    "There's trouble brewing near {location}.",
]

GREETING_TEMPLATES = [
    "Good to see you, {name}!",
    "How have you been, {name}?",
    "Ah, {name}! It's been too long.",
    "Well met, {name}.",
]


# ================================================================
# GOSSIP TOPICS (fallback if no known_info available)
# ================================================================

GENERIC_GOSSIP_TOPICS = [
    "the wolf attack last week",
    "the harvest this season",
    "the new guard captain",
    "strange lights in the ruins",
    "bandits on the north road",
    "the merchant caravan that went missing",
    "the king's latest decree",
    "the drought in the eastern farmlands",
    "the blacksmith's apprentice eloping",
    "the old well running dry",
    "the festival preparations",
    "the foreign traders at the market",
]


# ================================================================
# SNIPPET DATA CLASS
# ================================================================

class ConversationSnippet:
    """A single overheard conversation snippet for display."""
    __slots__ = ('speaker_name', 'listener_name', 'text',
                 'x', 'y', 'age', 'max_age', 'interaction_type')

    def __init__(self, speaker_name: str, listener_name: str, text: str,
                 x: float, y: float, interaction_type: str = "gossip"):
        self.speaker_name = speaker_name
        self.listener_name = listener_name
        self.text = text
        self.x = x
        self.y = y
        self.age = 0.0
        self.max_age = 3.5  # seconds visible
        self.interaction_type = interaction_type


# ================================================================
# SNIPPET GENERATION
# ================================================================

def _pick_gossip_topic(npc: NPC) -> str:
    """Pick a gossip topic from NPC known_info or use a generic one."""
    known = getattr(npc, 'known_info', [])
    if known and random.random() < 0.7:
        info = random.choice(known[-10:])
        # Trim long info strings
        if len(info) > 40:
            info = info[:37] + "..."
        return info
    return random.choice(GENERIC_GOSSIP_TOPICS)


def _pick_trade_item(npc: NPC) -> Tuple[str, int]:
    """Pick an item and price for trade snippet."""
    inv = getattr(npc, 'npc_inventory', [])
    if inv:
        item = random.choice(inv)
        price = max(1, getattr(item, 'value', 5) + random.randint(-2, 5))
        return item.name, price
    return random.choice(["bread", "herbs", "iron ore", "tools"]), random.randint(3, 15)


def generate_snippet(npc1: NPC, npc2: NPC,
                     interaction_type: str) -> Optional[ConversationSnippet]:
    """Generate a conversation snippet based on interaction type.

    Args:
        npc1: The speaking NPC.
        npc2: The listening NPC.
        interaction_type: One of 'gossip', 'teaching', 'trade',
                          'food_sharing', 'comfort', 'warning', 'greeting'.

    Returns:
        A ConversationSnippet, or None if generation fails.
    """
    text = ""
    speaker = npc1

    if interaction_type == "gossip":
        topic = _pick_gossip_topic(npc1)
        text = random.choice(GOSSIP_TEMPLATES).format(topic=topic)

    elif interaction_type == "teaching":
        skills = getattr(npc1, 'npc_skills', {})
        if skills:
            skill = max(skills, key=skills.get)
        else:
            skill = random.choice(["smithing", "farming", "cooking",
                                   "fighting", "herbalism"])
        text = random.choice(TEACHING_TEMPLATES).format(skill=skill)

    elif interaction_type == "trade":
        item_name, price = _pick_trade_item(npc2)
        text = random.choice(TRADE_TEMPLATES).format(
            item=item_name, price=price)

    elif interaction_type == "food_sharing":
        text = random.choice(FOOD_SHARING_TEMPLATES)

    elif interaction_type == "comfort":
        text = random.choice(COMFORT_TEMPLATES)

    elif interaction_type == "warning":
        known = getattr(npc1, 'known_info', [])
        dangers = [k for k in known if any(
            w in k.lower() for w in ["danger", "attack", "bandit", "wolf"])]
        if dangers:
            location = random.choice(dangers)[:25]
            threat = "danger"
        else:
            location = "the old ruins"
            threat = "monsters"
        text = random.choice(WARNING_TEMPLATES).format(
            location=location, threat=threat)

    elif interaction_type == "greeting":
        text = random.choice(GREETING_TEMPLATES).format(name=npc2.name)

    else:
        # Fallback to gossip
        topic = _pick_gossip_topic(npc1)
        text = random.choice(GOSSIP_TEMPLATES).format(topic=topic)

    if not text:
        return None

    # Place snippet at midpoint between the two NPCs
    mid_x = (npc1.x + npc2.x) / 2
    mid_y = (npc1.y + npc2.y) / 2

    return ConversationSnippet(
        speaker_name=npc1.name,
        listener_name=npc2.name,
        text=text,
        x=mid_x,
        y=mid_y,
        interaction_type=interaction_type,
    )


# ================================================================
# SNIPPET MANAGER
# ================================================================

class SnippetManager:
    """Manages overheard conversation snippets near the player.

    The simulation calls ``try_add_snippet`` when NPCs interact.
    The renderer reads ``active_snippets`` each frame.
    The main game loop feeds snippets into the combat log.
    """

    OVERHEAR_RANGE = 8.0  # tiles

    def __init__(self):
        self.active_snippets: List[ConversationSnippet] = []
        self.pending_log_entries: List[str] = []
        self._cooldown: float = 0.0  # avoid spam
        self._min_interval: float = 2.0  # seconds between snippets

    def try_add_snippet(self, npc1: NPC, npc2: NPC,
                        interaction_type: str,
                        player_x: float, player_y: float) -> bool:
        """Attempt to add a snippet if the player is close enough.

        Returns True if a snippet was added.
        """
        if self._cooldown > 0:
            return False

        # Check distance from player to the conversation midpoint
        mid_x = (npc1.x + npc2.x) / 2
        mid_y = (npc1.y + npc2.y) / 2
        dx = player_x - mid_x
        dy = player_y - mid_y
        dist = (dx * dx + dy * dy) ** 0.5

        if dist > self.OVERHEAR_RANGE:
            return False

        snippet = generate_snippet(npc1, npc2, interaction_type)
        if snippet is None:
            return False

        self.active_snippets.append(snippet)
        self._cooldown = self._min_interval

        # Queue combat log entry
        log_entry = (f"[Overheard] {snippet.speaker_name} to "
                     f"{snippet.listener_name}: {snippet.text}")
        self.pending_log_entries.append(log_entry)

        return True

    def update(self, dt: float):
        """Update snippet ages and remove expired ones."""
        self._cooldown = max(0.0, self._cooldown - dt)

        remaining = []
        for s in self.active_snippets:
            s.age += dt
            if s.age < s.max_age:
                remaining.append(s)
        self.active_snippets = remaining

    def drain_log_entries(self) -> List[str]:
        """Return and clear pending combat log entries."""
        entries = self.pending_log_entries
        self.pending_log_entries = []
        return entries
