"""Letter / Message system — NPCs send letters to the player.

NPCs with high enough relationship (> 40 affinity) may send letters
that arrive after a travel delay of 1-3 game days. Letters are picked
up at any settlement's message board.

Letter types based on NPC role:
- Friend: hints, lore, quests
- Merchant: special trade offers
- Guard: danger warnings (raid incoming)
- Quest giver: reward collection notice

The system is updated once per game tick and integrates with the
existing quest and social systems.
"""

import random
from dataclasses import dataclass, field
from typing import List, Optional, Dict


# ================================================================
# LETTER DATA
# ================================================================

@dataclass
class Letter:
    """A letter sent from an NPC to the player."""
    sender_name: str
    sender_profession: str
    sender_settlement: str
    subject: str
    body: str
    letter_type: str          # "friend", "merchant", "guard", "quest"
    sent_day: float           # game day the letter was sent
    arrival_day: float        # game day the letter arrives
    read: bool = False
    triggers_quest: bool = False
    quest_data: Optional[Dict] = None
    trade_data: Optional[Dict] = None


# ================================================================
# LETTER TEMPLATES
# ================================================================

_FRIEND_TEMPLATES = [
    ("A Discovery",
     "Dear friend,\n\nI've discovered something interesting near {location}. "
     "An old ruin that the locals seem to avoid. I think there may be "
     "treasure inside, but I dare not go alone.\n\nCome find me when "
     "you can.\n\nYours,\n{sender}"),
    ("Thinking of You",
     "Dear friend,\n\nIt has been too long since we last spoke. Life in "
     "{settlement} continues as always. The {season} air reminds me of "
     "our adventures.\n\nI hope the road treats you well.\n\n"
     "Warm regards,\n{sender}"),
    ("A Favor to Ask",
     "Dear friend,\n\nI find myself in need of help. There is a matter "
     "I cannot handle alone — nothing dangerous, I promise. Well, mostly.\n\n"
     "Please visit me in {settlement} when your travels bring you near.\n\n"
     "Gratefully,\n{sender}"),
    ("Good News",
     "Dear friend,\n\nWonderful news! I have been promoted to head "
     "{profession} in {settlement}. The first round of drinks is on me.\n\n"
     "Come celebrate with me!\n\n{sender}"),
]

_MERCHANT_TEMPLATES = [
    ("Rare Goods Available",
     "Esteemed customer,\n\nI have recently acquired some exceptional "
     "merchandise that I believe would interest you. These items won't "
     "last long on my shelves.\n\nVisit my shop in {settlement} before "
     "someone else snaps them up.\n\n{sender}, Merchant"),
    ("Special Discount",
     "Valued patron,\n\nAs one of my most trusted customers, I am offering "
     "you a special discount — 30% off any purchase for the next few days.\n\n"
     "Do not miss this opportunity.\n\n{sender}, {settlement} Market"),
    ("Supply Shortage Warning",
     "To whom it may concern,\n\nSupplies of iron and leather are running "
     "low in {settlement}. If you have any to sell, I'll pay premium prices. "
     "Come quickly.\n\n{sender}, Merchant"),
]

_GUARD_TEMPLATES = [
    ("Danger Approaches",
     "Urgent warning,\n\nOur scouts have spotted hostile forces moving "
     "toward {settlement}. We expect an attack within days.\n\n"
     "If you are nearby, your sword arm would be greatly appreciated. "
     "The garrison is undermanned.\n\n{sender}, Guard Captain"),
    ("Bandit Activity",
     "Advisory,\n\nBandits have been sighted on the roads near {settlement}. "
     "Several travelers have been robbed. Exercise caution if traveling "
     "in this area.\n\nThere may be a bounty for clearing them out.\n\n"
     "{sender}, Town Guard"),
    ("Monster Sighting",
     "Warning,\n\nA dangerous creature has been spotted near {location}. "
     "Livestock have gone missing and farmers are afraid to tend their "
     "fields.\n\nWe could use a capable adventurer.\n\n{sender}, Guard"),
]

_QUEST_TEMPLATES = [
    ("Task Complete",
     "Greetings,\n\nThe task you undertook on our behalf has been completed "
     "to our satisfaction. Your reward awaits you at {settlement}.\n\n"
     "Come collect it at your convenience.\n\n{sender}"),
    ("New Opportunity",
     "Adventurer,\n\nA new opportunity has come to our attention that "
     "requires someone of your skills. The pay is generous and the work "
     "is urgent.\n\nSeek me out in {settlement} for details.\n\n{sender}"),
]

TEMPLATES_BY_TYPE = {
    "friend": _FRIEND_TEMPLATES,
    "merchant": _MERCHANT_TEMPLATES,
    "guard": _GUARD_TEMPLATES,
    "quest": _QUEST_TEMPLATES,
}

# Professions mapped to letter types
_PROFESSION_TYPE = {
    "merchant": "merchant",
    "shopkeeper": "merchant",
    "trader": "merchant",
    "blacksmith": "merchant",
    "guard": "guard",
    "soldier": "guard",
    "knight": "guard",
    "captain": "guard",
    "innkeeper": "friend",
    "farmer": "friend",
    "priest": "friend",
    "healer": "friend",
}


def _get_letter_type(profession: str) -> str:
    """Determine letter type from NPC profession."""
    prof_lower = profession.lower()
    for key, ltype in _PROFESSION_TYPE.items():
        if key in prof_lower:
            return ltype
    # Default: friend or quest
    return random.choice(["friend", "quest"])


# ================================================================
# LETTER SYSTEM
# ================================================================

class LetterSystem:
    """Manages NPC-to-player letter sending, delivery, and reading."""

    def __init__(self):
        self.pending_letters: List[Letter] = []    # in transit
        self.delivered_letters: List[Letter] = []   # available at boards
        self._check_timer = 0.0
        self._check_interval = 30.0  # check every 30 game seconds
        self._sent_tracker: Dict[str, float] = {}  # npc_name -> last sent day

    @property
    def unread_count(self) -> int:
        """Number of unread delivered letters."""
        return sum(1 for lt in self.delivered_letters if not lt.read)

    def update(self, dt: float, current_day: float, npcs, player,
               social_system=None):
        """Called each game tick. Checks for new letters and delivers pending ones."""
        # Deliver pending letters that have arrived
        newly_delivered = []
        still_pending = []
        for letter in self.pending_letters:
            if current_day >= letter.arrival_day:
                self.delivered_letters.append(letter)
                newly_delivered.append(letter)
            else:
                still_pending.append(letter)
        self.pending_letters = still_pending

        # Periodically check if any NPC wants to send a letter
        self._check_timer -= dt
        if self._check_timer > 0:
            return newly_delivered
        self._check_timer = self._check_interval

        player_name = getattr(player, 'name', 'Player')

        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue

            # Check affinity threshold
            affinity = self._get_affinity(npc, player_name, social_system)
            if affinity <= 40:
                continue

            # Don't spam: max 1 letter per NPC per 5 game days
            last_sent = self._sent_tracker.get(npc.name, -999)
            if current_day - last_sent < 5.0:
                continue

            # 5% chance per check interval to send a letter
            if random.random() > 0.05:
                continue

            letter = self._compose_letter(npc, current_day)
            if letter:
                self.pending_letters.append(letter)
                self._sent_tracker[npc.name] = current_day

        return newly_delivered

    def _get_affinity(self, npc, player_name, social_system) -> int:
        """Get NPC's affinity toward the player."""
        if social_system:
            rel = social_system.get_rel(player_name, npc.name)
            return int(rel.trust)
        return int(getattr(npc, 'player_relationship', 0))

    def _compose_letter(self, npc, current_day: float) -> Optional[Letter]:
        """Create a letter from an NPC."""
        profession = getattr(npc, 'profession', 'citizen')
        settlement = getattr(npc, 'home_settlement', 'a nearby town')
        letter_type = _get_letter_type(profession)

        templates = TEMPLATES_BY_TYPE.get(letter_type, _FRIEND_TEMPLATES)
        subject, body_template = random.choice(templates)

        # Fill template variables
        season = random.choice(["spring", "summer", "autumn", "winter"])
        location = f"the outskirts of {settlement}"
        body = body_template.format(
            sender=npc.name,
            settlement=settlement,
            profession=profession,
            season=season,
            location=location,
        )

        # Travel delay: 1-3 game days
        delay = random.uniform(1.0, 3.0)

        # Quest-triggering letters (friend and quest types)
        triggers_quest = letter_type in ("friend", "quest") and random.random() < 0.3
        quest_data = None
        if triggers_quest:
            quest_data = {
                "type": "letter_quest",
                "giver": npc.name,
                "settlement": settlement,
                "description": f"Visit {npc.name} in {settlement}",
            }

        # Trade data for merchant letters
        trade_data = None
        if letter_type == "merchant":
            trade_data = {
                "discount": random.choice([0.1, 0.2, 0.3]),
                "settlement": settlement,
                "merchant": npc.name,
            }

        return Letter(
            sender_name=npc.name,
            sender_profession=profession,
            sender_settlement=settlement,
            subject=subject,
            body=body,
            letter_type=letter_type,
            sent_day=current_day,
            arrival_day=current_day + delay,
            triggers_quest=triggers_quest,
            quest_data=quest_data,
            trade_data=trade_data,
        )

    def read_letter(self, index: int) -> Optional[Letter]:
        """Mark a delivered letter as read and return it."""
        if 0 <= index < len(self.delivered_letters):
            letter = self.delivered_letters[index]
            letter.read = True
            return letter
        return None

    def get_letters_for_settlement(self, settlement_name: str) -> List[Letter]:
        """Get unread letters available at a specific settlement's message board.

        Letters are available at ANY settlement, not just the sender's.
        """
        return [lt for lt in self.delivered_letters if not lt.read]

    def get_all_delivered(self) -> List[Letter]:
        """Get all delivered letters (read and unread)."""
        return list(self.delivered_letters)

    def clear(self):
        """Reset the letter system."""
        self.pending_letters.clear()
        self.delivered_letters.clear()
        self._sent_tracker.clear()
        self._check_timer = 0.0
