"""Group conversations — 3+ NPCs talking together near the player.

When a cluster of 3+ NPCs forms within 5 tiles of each other, one may
initiate a group conversation.  Each participant contributes lines based
on their profession and personality.  If the player is within 8 tiles,
overheard snippets are generated for the existing snippet system.

Usage:
    manager = GroupConversationManager()
    # Every social tick:
    manager.try_start_conversations(npcs, player_x, player_y)
    # Every frame:
    manager.update(dt, snippet_manager, player_x, player_y)
"""

import math
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from game.core.npc import NPC
from game.systems.conversation_snippets import ConversationSnippet, SnippetManager


# ================================================================
# TOPIC POOLS
# ================================================================

TOPIC_POOLS: Dict[str, List[str]] = {
    "local_events": [
        "the festival last week",
        "the new building going up",
        "the road being repaired",
        "the recent harvest",
        "the town crier's announcement",
        "the well running low",
    ],
    "gossip": [
        "{name} was seen sneaking out at night",
        "{name} bought a fancy new cloak",
        "{name} got into a fight at the tavern",
        "someone said {name} is leaving town",
        "{name} and {name2} have been spending a lot of time together",
        "{name} owes money to half the town",
    ],
    "kingdom_politics": [
        "the king's new tax decree",
        "rumours of war in the east",
        "the lord's latest edict",
        "the trade agreement with the north",
        "whether the crown will send soldiers",
        "the succession question",
    ],
    "weather": [
        "this unseasonable cold",
        "whether rain is coming",
        "the drought hurting the crops",
        "the fog this morning",
        "the beautiful sunset yesterday",
        "the storm that blew through",
    ],
    "creature_sightings": [
        "wolves near the road at night",
        "a bear spotted by the river",
        "strange tracks in the forest",
        "a dragon flying overhead — or so they say",
        "undead wandering near the old ruins",
        "a giant spider web found in the woods",
    ],
}

ALL_TOPICS = list(TOPIC_POOLS.keys())


# ================================================================
# PROFESSION-FLAVOURED LINES
# ================================================================

_PROFESSION_LINES: Dict[str, List[str]] = {
    "Guard": [
        "I've been patrolling extra shifts lately.",
        "Keep your doors locked at night, I say.",
        "We caught a pickpocket near the market yesterday.",
    ],
    "Merchant": [
        "Prices have been wild this season.",
        "I can barely keep my shelves stocked.",
        "The trade caravans are late again.",
    ],
    "Farmer": [
        "The soil's been dry — not a good sign.",
        "My wheat should be ready next week.",
        "I lost two chickens to a fox.",
    ],
    "Blacksmith": [
        "I've been hammering swords all week.",
        "Good iron is hard to come by.",
        "Brought my forge up to temperature before dawn.",
    ],
    "Priest": [
        "We must keep faith in these times.",
        "The temple offerings have been sparse.",
        "I prayed for guidance last night.",
    ],
    "Innkeeper": [
        "Had a rowdy bunch in last night.",
        "My best ale just ran out.",
        "Travellers bring the strangest stories.",
    ],
}

_DEFAULT_LINES = [
    "Interesting times we live in.",
    "I've been thinking about that a lot.",
    "You don't say!",
    "I heard something similar.",
    "That's concerning, if true.",
    "Well, what can you do?",
    "I wonder what the elders think.",
    "Things were simpler when I was young.",
]


# ================================================================
# PERSONALITY MODIFIERS
# ================================================================

def _personality_reaction(npc: NPC) -> str:
    """Return a short reaction coloured by the NPC's personality."""
    bravery = getattr(npc, 'bravery', 0.5)
    friendliness = getattr(npc, 'friendliness', 0.5)

    if bravery > 0.7:
        return random.choice([
            "We should do something about it!",
            "I'm not afraid.",
            "Let them come — we'll be ready.",
        ])
    if bravery < 0.3:
        return random.choice([
            "That frightens me, honestly.",
            "Maybe we should stay indoors.",
            "I don't like the sound of that.",
        ])
    if friendliness > 0.7:
        return random.choice([
            "We're all in this together.",
            "Let's help each other out.",
            "I'm sure things will work out.",
        ])
    if friendliness < 0.3:
        return random.choice([
            "Not my problem.",
            "People should fend for themselves.",
            "Hmph.",
        ])
    return random.choice(_DEFAULT_LINES)


# ================================================================
# GROUP CONVERSATION STATE
# ================================================================

@dataclass
class GroupConversation:
    """An active multi-NPC conversation."""
    topic_category: str
    topic_text: str
    participants: List[NPC]
    duration: float  # total seconds
    elapsed: float = 0.0
    turn_index: int = 0  # which participant speaks next
    lines_spoken: int = 0
    max_lines: int = 0
    snippets_generated: int = 0
    finished: bool = False

    def __post_init__(self):
        self.max_lines = len(self.participants) * random.randint(1, 2)


def _pick_topic(participants: List[NPC]) -> tuple:
    """Pick a conversation topic, preferring NPC known_info when available."""
    # 40% chance to use an NPC's known_info as gossip seed
    for npc in participants:
        known = getattr(npc, 'known_info', [])
        if known and random.random() < 0.4:
            info = random.choice(known[-10:])
            if len(info) > 50:
                info = info[:47] + "..."
            return "local_events", info

    cat = random.choice(ALL_TOPICS)
    templates = TOPIC_POOLS[cat]
    template = random.choice(templates)

    # Fill in name placeholders from participants or generic names
    all_names = [p.name for p in participants]
    extra = ["someone", "a stranger", "the elder"]
    name_pool = all_names + extra
    topic = template.format(
        name=random.choice(name_pool),
        name2=random.choice(name_pool),
    )
    return cat, topic


def _npc_line(npc: NPC, topic_category: str, is_opener: bool) -> str:
    """Generate a single line for an NPC in the group conversation."""
    prof = getattr(npc, 'profession', '')

    if is_opener:
        openers = [
            f"Have you all heard about {'{topic}'}?",
            f"I wanted to talk about {'{topic}'}.",
            f"So, what do you make of {'{topic}'}?",
            f"Anyone else worried about {'{topic}'}?",
        ]
        return random.choice(openers)

    # 50% profession-specific, 30% personality reaction, 20% default
    roll = random.random()
    if roll < 0.5:
        prof_lines = _PROFESSION_LINES.get(prof, _DEFAULT_LINES)
        return random.choice(prof_lines)
    if roll < 0.8:
        return _personality_reaction(npc)
    return random.choice(_DEFAULT_LINES)


# ================================================================
# GROUP CONVERSATION MANAGER
# ================================================================

class GroupConversationManager:
    """Detects NPC clusters, starts and advances group conversations."""

    CLUSTER_RANGE = 5.0      # tiles — NPCs must be this close to cluster
    OVERHEAR_RANGE = 8.0     # tiles — player overhears if within this
    MIN_PARTICIPANTS = 3
    MAX_PARTICIPANTS = 5
    MIN_DURATION = 10.0      # seconds
    MAX_DURATION = 20.0      # seconds
    CHECK_COOLDOWN = 5.0     # seconds between cluster scans
    MAX_ACTIVE = 3           # max simultaneous group conversations

    def __init__(self):
        self.active: List[GroupConversation] = []
        self._cooldown: float = 0.0
        self._participating_names: set = set()  # names currently in a group conv

    # ----------------------------------------------------------
    # Cluster detection
    # ----------------------------------------------------------

    def _find_clusters(self, npcs: List[NPC]) -> List[List[NPC]]:
        """Find groups of 3+ NPCs within CLUSTER_RANGE of each other."""
        available = [n for n in npcs
                     if n.alive and n.name not in self._participating_names
                     and getattr(n, 'current_action', '') not in ('fighting', 'fleeing')]

        if len(available) < self.MIN_PARTICIPANTS:
            return []

        clusters: List[List[NPC]] = []
        used = set()

        for i, npc in enumerate(available):
            if id(npc) in used:
                continue
            group = [npc]
            for j, other in enumerate(available):
                if i == j or id(other) in used:
                    continue
                if len(group) >= self.MAX_PARTICIPANTS:
                    break
                dx = npc.x - other.x
                dy = npc.y - other.y
                if dx * dx + dy * dy <= self.CLUSTER_RANGE ** 2:
                    group.append(other)

            if len(group) >= self.MIN_PARTICIPANTS:
                clusters.append(group)
                for n in group:
                    used.add(id(n))

        return clusters

    # ----------------------------------------------------------
    # Start / advance / finish
    # ----------------------------------------------------------

    def try_start_conversations(self, npcs: List[NPC],
                                player_x: float, player_y: float):
        """Scan for NPC clusters and maybe start a group conversation."""
        if self._cooldown > 0:
            return
        if len(self.active) >= self.MAX_ACTIVE:
            return

        clusters = self._find_clusters(npcs)
        for group in clusters:
            if len(self.active) >= self.MAX_ACTIVE:
                break
            # 30% chance per cluster per check
            if random.random() > 0.30:
                continue

            cat, topic = _pick_topic(group)
            conv = GroupConversation(
                topic_category=cat,
                topic_text=topic,
                participants=group,
                duration=random.uniform(self.MIN_DURATION, self.MAX_DURATION),
            )
            self.active.append(conv)
            for npc in group:
                self._participating_names.add(npc.name)
            self._cooldown = self.CHECK_COOLDOWN

    def update(self, dt: float,
               snippet_manager: Optional[SnippetManager],
               player_x: float, player_y: float):
        """Advance active group conversations and generate snippets."""
        self._cooldown = max(0.0, self._cooldown - dt)

        remaining: List[GroupConversation] = []
        for conv in self.active:
            conv.elapsed += dt
            if conv.elapsed >= conv.duration or conv.lines_spoken >= conv.max_lines:
                self._finish_conversation(conv)
                continue

            # Advance: next NPC speaks roughly every 2-3 seconds
            interval = conv.duration / max(conv.max_lines, 1)
            expected_lines = int(conv.elapsed / max(interval, 0.5))
            while conv.lines_spoken < expected_lines and conv.lines_spoken < conv.max_lines:
                self._advance_turn(conv, snippet_manager, player_x, player_y)

            remaining.append(conv)

        self.active = remaining

    def _advance_turn(self, conv: GroupConversation,
                      snippet_manager: Optional[SnippetManager],
                      player_x: float, player_y: float):
        """One participant speaks a line."""
        idx = conv.turn_index % len(conv.participants)
        speaker = conv.participants[idx]
        is_opener = (conv.lines_spoken == 0)

        line = _npc_line(speaker, conv.topic_category, is_opener)
        if is_opener:
            line = line.replace("{topic}", conv.topic_text)

        conv.lines_spoken += 1
        conv.turn_index += 1

        # Memory for the speaker
        if hasattr(speaker, 'add_memory'):
            others = [p.name for p in conv.participants if p is not speaker]
            speaker.add_memory(
                "social",
                f"Group talk about {conv.topic_text[:30]} with {', '.join(others[:2])}",
                2,
            )

        # Generate snippet if player is close enough
        if snippet_manager is not None and conv.snippets_generated < 5:
            mid_x = sum(p.x for p in conv.participants) / len(conv.participants)
            mid_y = sum(p.y for p in conv.participants) / len(conv.participants)
            dx = player_x - mid_x
            dy = player_y - mid_y
            if dx * dx + dy * dy <= self.OVERHEAR_RANGE ** 2:
                # Pick a random "listener" from the other participants
                listeners = [p for p in conv.participants if p is not speaker]
                listener = random.choice(listeners) if listeners else speaker

                snippet = ConversationSnippet(
                    speaker_name=speaker.name,
                    listener_name=listener.name,
                    text=line,
                    x=mid_x,
                    y=mid_y,
                    interaction_type="group_conversation",
                )
                snippet_manager.active_snippets.append(snippet)
                snippet_manager.pending_log_entries.append(
                    f"[Group] {speaker.name}: {line}"
                )
                conv.snippets_generated += 1

    def _finish_conversation(self, conv: GroupConversation):
        """Clean up after a group conversation ends."""
        for npc in conv.participants:
            self._participating_names.discard(npc.name)
            # Social need boost
            needs = getattr(npc, 'needs', {})
            if 'social' in needs:
                needs['social'] = min(100, needs['social'] + 12)
            # Relationship boost between participants
            rels = getattr(npc, 'npc_relationships', {})
            for other in conv.participants:
                if other is not npc:
                    rels[other.name] = rels.get(other.name, 0) + 2
