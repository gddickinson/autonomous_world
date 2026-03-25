"""Message board system for taverns and town halls.

NPCs post messages that refresh daily. Separate from the quest board —
both options appear when the player presses E near a tavern or town hall.

Message categories:
- Kingdom announcements (wars, trade routes, laws)
- Local news (threats, festivals, weather)
- Wanted posters (bounties on criminals)
- Personal ads (job offers, lost items)
"""

import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


# ================================================================
# MESSAGE CATEGORIES
# ================================================================

CAT_ANNOUNCEMENT = "announcement"
CAT_LOCAL_NEWS = "local_news"
CAT_WANTED = "wanted"
CAT_PERSONAL = "personal"

CATEGORY_LABELS = {
    CAT_ANNOUNCEMENT: "Kingdom Announcement",
    CAT_LOCAL_NEWS: "Local News",
    CAT_WANTED: "Wanted Poster",
    CAT_PERSONAL: "Personal Ad",
}

CATEGORY_COLORS = {
    CAT_ANNOUNCEMENT: (220, 180, 60),   # gold
    CAT_LOCAL_NEWS: (140, 200, 160),     # green
    CAT_WANTED: (220, 90, 70),           # red
    CAT_PERSONAL: (160, 170, 220),       # blue
}


# ================================================================
# CONTENT TEMPLATES
# ================================================================

# --- Kingdom announcements ---
ANNOUNCEMENT_TEMPLATES = [
    # War-related
    ("War Declared Against {rival}",
     "By royal decree, the Kingdom of {kingdom} declares war upon "
     "{rival}. All able-bodied citizens are called to serve."),
    ("Peace Treaty with {rival}",
     "A peace accord has been reached with {rival}. Trade and travel "
     "between our kingdoms shall resume."),
    ("Alliance Formed with {rival}",
     "An alliance of mutual defence has been signed with {rival}. "
     "May our two kingdoms prosper together."),

    # Trade
    ("New Trade Route Opened",
     "A trade route between {settlement} and {dest} has been "
     "established. Merchants may now travel under royal protection."),
    ("Trade Embargo on {rival}",
     "All trade with {rival} is hereby suspended until further notice. "
     "Violators will face imprisonment."),

    # Law and governance
    ("Tax Increase Announced",
     "By order of the crown, taxes shall increase by one-fifth to fund "
     "kingdom defences. All citizens must comply."),
    ("New Governor Appointed",
     "His Majesty has appointed a new governor for {settlement}. "
     "A ceremony will be held at the town hall."),
    ("Harvest Festival Proclaimed",
     "A week-long Harvest Festival is proclaimed in honour of a "
     "bountiful season. All citizens are welcome to attend."),
]

# --- Local news ---
LOCAL_NEWS_TEMPLATES = [
    ("Wolves Spotted Near the Forest",
     "Travellers report wolf packs hunting near the eastern woods. "
     "Livestock owners should take precautions."),
    ("Festival This Week",
     "The annual {settlement} market festival begins tomorrow! "
     "Visiting merchants will offer rare goods at special prices."),
    ("Bridge Washed Out",
     "Heavy rains have destroyed the bridge south of {settlement}. "
     "Travellers should use the ford upstream until repairs are done."),
    ("Strange Lights at the Ruins",
     "Eerie lights have been seen near the old ruins after dark. "
     "The town guard advises caution."),
    ("Merchant Caravan Arriving",
     "A large merchant caravan from {dest} is expected within the week. "
     "Rare goods and supplies will be available."),
    ("Drought Warning",
     "The wells are running low. Residents are asked to conserve water "
     "until the rains return."),
    ("Undead Sighted",
     "Shambling corpses have been spotted near the old cemetery. "
     "Stay indoors after dark."),
    ("New Mine Opened",
     "A new iron mine has opened in the hills north of {settlement}. "
     "Workers and guards are needed."),
    ("Road Bandits",
     "Bandits have been ambushing travellers on the road to {dest}. "
     "Travel in groups or hire an escort."),
    ("Good Harvest Expected",
     "Farmers report excellent growing conditions. Food prices are "
     "expected to drop this season."),
]

# --- Wanted posters ---
WANTED_TEMPLATES = [
    ("Bandit Leader — 50g Reward",
     "WANTED: The bandit leader known as '{criminal}'. Last seen on "
     "the road to {dest}. Bring proof of elimination to the guard "
     "captain. Reward: 50 gold."),
    ("Notorious Thief — 30g Reward",
     "WANTED: A thief has been breaking into homes in {settlement}. "
     "Description: hooded figure, quick on their feet. "
     "Reward: 30 gold for capture."),
    ("Wolf Pack Alpha — 25g Reward",
     "BOUNTY: A massive black wolf leads a pack terrorising farms "
     "near {settlement}. Bring its pelt as proof. Reward: 25 gold."),
    ("Escaped Prisoner — 40g Reward",
     "WANTED: An escaped prisoner from the {settlement} dungeon. "
     "Armed and dangerous. Reward: 40 gold, dead or alive."),
    ("Necromancer — 100g Reward",
     "WANTED: A rogue necromancer raising the dead near {settlement}. "
     "Extremely dangerous. Do not approach alone. Reward: 100 gold."),
]

# --- Personal ads ---
PERSONAL_TEMPLATES = [
    ("Seeking Apprentice Blacksmith",
     "Experienced smith in {settlement} seeks a strong apprentice. "
     "Room and board provided. Must be willing to work dawn to dusk."),
    ("Lost Dog — Reward 10g",
     "Missing: brown hound, answers to 'Biscuit'. Last seen near "
     "the market square. 10 gold reward for safe return."),
    ("Healer Needed",
     "The village of {settlement} urgently needs a healer or herbalist. "
     "Generous compensation and housing provided."),
    ("Scribe for Hire",
     "Literate scribe available for letters, contracts, and record-"
     "keeping. Reasonable rates. Ask at the tavern."),
    ("Rooms Available",
     "The {settlement} Inn has rooms available for long-term lodgers. "
     "Quiet, clean, meals included. Inquire within."),
    ("Guard Work Available",
     "Caravan heading to {dest} seeks guards for the journey. "
     "Pay: 20 gold upon safe arrival. Departs in two days."),
    ("Tutor Wanted",
     "Noble family seeks a tutor for their children. Knowledge of "
     "letters, numbers, and history required. Good pay."),
    ("Mushroom Buyer",
     "Alchemist in {settlement} will pay top coin for rare mushrooms "
     "from the deep forest. Bring samples to the apothecary."),
    ("Looking for Travel Companion",
     "Pilgrim heading to the Holy Shrine seeks a companion for the "
     "journey. Will share provisions. Meet at the tavern at dawn."),
]

# Criminal name pool for wanted posters
CRIMINAL_NAMES = [
    "Scarface", "The Shadow", "Iron Fang", "Red Dagger",
    "The Viper", "Blackthorn", "One-Eye", "The Wraith",
    "Cutpurse Kira", "Grimblade", "Ratcatcher", "The Fox",
]


# ================================================================
# MESSAGE DATA
# ================================================================

@dataclass
class BoardMessage:
    """A single message posted on a message board."""
    category: str
    title: str
    body: str
    poster: str = "Anonymous"
    day_posted: int = 0
    settlement: str = ""

    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS.get(self.category, "Notice")

    @property
    def color(self) -> Tuple[int, int, int]:
        return CATEGORY_COLORS.get(self.category, (180, 180, 180))


# ================================================================
# MESSAGE GENERATORS
# ================================================================

def _pick_template(templates: list, settlement: str,
                   dest: str = "", kingdom: str = "",
                   rival: str = "") -> Tuple[str, str]:
    """Pick a random template and fill placeholders."""
    title_tpl, body_tpl = random.choice(templates)
    criminal = random.choice(CRIMINAL_NAMES)
    fmt = dict(
        settlement=settlement,
        dest=dest or "a distant town",
        kingdom=kingdom or "the Kingdom",
        rival=rival or "a neighbouring realm",
        criminal=criminal,
    )
    return title_tpl.format(**fmt), body_tpl.format(**fmt)


def generate_announcement(settlement: str, kingdom: str = "",
                           nearby: List[str] = None,
                           day: int = 0) -> BoardMessage:
    """Generate a kingdom announcement message."""
    dest = random.choice(nearby) if nearby else ""
    rivals = [s for s in (nearby or []) if s != settlement]
    rival = random.choice(rivals) if rivals else ""
    title, body = _pick_template(
        ANNOUNCEMENT_TEMPLATES, settlement,
        dest=dest, kingdom=kingdom, rival=rival,
    )
    return BoardMessage(
        category=CAT_ANNOUNCEMENT, title=title, body=body,
        poster="Royal Herald", day_posted=day, settlement=settlement,
    )


def generate_local_news(settlement: str,
                        nearby: List[str] = None,
                        day: int = 0) -> BoardMessage:
    """Generate a local news message."""
    dest = random.choice(nearby) if nearby else ""
    title, body = _pick_template(
        LOCAL_NEWS_TEMPLATES, settlement, dest=dest,
    )
    return BoardMessage(
        category=CAT_LOCAL_NEWS, title=title, body=body,
        poster="Town Crier", day_posted=day, settlement=settlement,
    )


def generate_wanted(settlement: str,
                    nearby: List[str] = None,
                    day: int = 0) -> BoardMessage:
    """Generate a wanted poster."""
    dest = random.choice(nearby) if nearby else ""
    title, body = _pick_template(
        WANTED_TEMPLATES, settlement, dest=dest,
    )
    return BoardMessage(
        category=CAT_WANTED, title=title, body=body,
        poster="Guard Captain", day_posted=day, settlement=settlement,
    )


def generate_personal(settlement: str,
                      nearby: List[str] = None,
                      day: int = 0) -> BoardMessage:
    """Generate a personal ad."""
    dest = random.choice(nearby) if nearby else ""
    title, body = _pick_template(
        PERSONAL_TEMPLATES, settlement, dest=dest,
    )
    posters = ["A Local", "Concerned Citizen", "Tavern Regular",
               "An Old Farmer", "A Merchant", "A Traveller"]
    return BoardMessage(
        category=CAT_PERSONAL, title=title, body=body,
        poster=random.choice(posters), day_posted=day,
        settlement=settlement,
    )


# Generator lookup
_GENERATORS = {
    CAT_ANNOUNCEMENT: generate_announcement,
    CAT_LOCAL_NEWS: generate_local_news,
    CAT_WANTED: generate_wanted,
    CAT_PERSONAL: generate_personal,
}


# ================================================================
# MESSAGE BOARD
# ================================================================

class MessageBoard:
    """A message board at a tavern or town hall.

    Displays NPC-posted messages that refresh every game day.
    Separate from the QuestBoard (both show when player presses E).
    """

    def __init__(self, settlement_name: str,
                 kingdom: str = "",
                 nearby_settlements: List[str] = None):
        self.settlement_name = settlement_name
        self.kingdom = kingdom
        self.nearby = nearby_settlements or []
        self.messages: List[BoardMessage] = []
        self.last_refresh_day = -999
        self.max_messages = 6

    def needs_refresh(self, current_day: int) -> bool:
        return current_day != self.last_refresh_day

    def refresh(self, current_day: int):
        """Generate fresh messages for the day."""
        self.messages.clear()
        self.last_refresh_day = current_day

        # Always 1 announcement, 2 local news, 1 wanted, 2 personal
        distribution = [
            (CAT_ANNOUNCEMENT, 1),
            (CAT_LOCAL_NEWS, 2),
            (CAT_WANTED, 1),
            (CAT_PERSONAL, 2),
        ]

        for cat, count in distribution:
            gen = _GENERATORS[cat]
            for _ in range(count):
                kwargs = dict(
                    settlement=self.settlement_name,
                    nearby=self.nearby,
                    day=current_day,
                )
                if cat == CAT_ANNOUNCEMENT:
                    kwargs["kingdom"] = self.kingdom
                msg = gen(**kwargs)
                self.messages.append(msg)

        # Shuffle so order varies
        random.shuffle(self.messages)

        # Trim to max
        self.messages = self.messages[:self.max_messages]

    def get_listings(self) -> List[Dict]:
        """Get message listings for UI display."""
        listings = []
        for i, msg in enumerate(self.messages):
            listings.append({
                "index": i,
                "category": msg.category,
                "category_label": msg.category_label,
                "title": msg.title,
                "body": msg.body,
                "poster": msg.poster,
                "color": msg.color,
            })
        return listings


# ================================================================
# MESSAGE BOARD MANAGER
# ================================================================

class MessageBoardManager:
    """Manages message boards across all settlements.

    Works alongside QuestBoardManager. When the player presses E
    near a tavern or town hall, both systems can be offered.
    """

    def __init__(self):
        self.boards: Dict[str, MessageBoard] = {}

    def register_board(self, settlement_name: str,
                       kingdom: str = "",
                       nearby_settlements: List[str] = None):
        """Register a message board for a settlement."""
        if settlement_name not in self.boards:
            self.boards[settlement_name] = MessageBoard(
                settlement_name,
                kingdom=kingdom,
                nearby_settlements=nearby_settlements,
            )

    def get_board(self, settlement_name: str) -> Optional[MessageBoard]:
        return self.boards.get(settlement_name)

    def find_board_for_position(self, world, x: int, y: int
                                ) -> Optional[MessageBoard]:
        """Find a message board near the player position.

        Checks if the player is inside a tavern or town hall building
        within any settlement that has a registered board.
        """
        target_kinds = {"tavern", "civic", "town_hall", "mead_hall",
                        "chieftain_hut", "boss_hut"}

        # Chunked worlds with plan
        if hasattr(world, 'plan'):
            for sp in world.plan.settlements:
                if abs(sp.x - x) > sp.radius + 20:
                    continue
                if abs(sp.y - y) > sp.radius + 20:
                    continue
                for bld in sp.buildings:
                    bkind = bld.get('kind', '')
                    if bkind not in target_kinds:
                        continue
                    bx, by = bld['x'], bld['y']
                    bw, bh = bld['w'], bld['h']
                    if bx <= x < bx + bw and by <= y < by + bh:
                        return self.boards.get(sp.name)

        # Non-chunked worlds
        for s in getattr(world, 'structures', []):
            if s.kind in target_kinds:
                for bx, by, bw, bh in getattr(s, 'buildings', []):
                    if bx <= x < bx + bw and by <= y < by + bh:
                        return self.boards.get(s.name)

        return None

    def refresh_all(self, current_day: int):
        """Refresh all boards that need it."""
        for board in self.boards.values():
            if board.needs_refresh(current_day):
                board.refresh(current_day)

    def interact(self, settlement_name: str,
                 current_day: int = 0) -> Optional[List[Dict]]:
        """Player interacts with a message board. Returns listings."""
        board = self.boards.get(settlement_name)
        if not board:
            return None

        if board.needs_refresh(current_day):
            board.refresh(current_day)

        return board.get_listings()

    def inject_custom_message(self, settlement_name: str,
                              category: str, title: str, body: str,
                              poster: str = "Unknown",
                              day: int = 0):
        """Inject a custom message (e.g. from world events or quests).

        Useful for dynamic events — wars, trade pacts, etc. — to post
        situation-specific messages on nearby boards.
        """
        board = self.boards.get(settlement_name)
        if not board:
            return
        msg = BoardMessage(
            category=category, title=title, body=body,
            poster=poster, day_posted=day, settlement=settlement_name,
        )
        board.messages.insert(0, msg)
        # Trim overflow
        if len(board.messages) > board.max_messages:
            board.messages = board.messages[:board.max_messages]


# ================================================================
# INITIALIZATION HELPER
# ================================================================

def initialize_message_boards(world, manager: MessageBoardManager):
    """Register message boards for all settlements that have taverns
    or town halls. Mirrors the quest board initialization pattern."""
    target_kinds = {"tavern", "civic", "town_hall", "mead_hall",
                    "chieftain_hut", "boss_hut"}

    if hasattr(world, 'plan'):
        # Chunked world
        all_names = [sp.name for sp in world.plan.settlements]
        for sp in world.plan.settlements:
            has_board_building = any(
                bld.get('kind', '') in target_kinds
                for bld in sp.buildings
            )
            if has_board_building:
                nearby = [n for n in all_names if n != sp.name][:5]
                kingdom = getattr(sp, 'kingdom', '')
                manager.register_board(
                    sp.name, kingdom=kingdom,
                    nearby_settlements=nearby,
                )
    else:
        # Non-chunked
        all_names = [s.name for s in getattr(world, 'structures', [])
                     if hasattr(s, 'name')]
        for s in getattr(world, 'structures', []):
            if s.kind in target_kinds and hasattr(s, 'name'):
                nearby = [n for n in all_names if n != s.name][:5]
                kingdom = getattr(s, 'kingdom', '')
                manager.register_board(
                    s.name, kingdom=kingdom,
                    nearby_settlements=nearby,
                )
