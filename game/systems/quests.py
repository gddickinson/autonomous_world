"""Quest system: procedural quest generation, quest chains, bounty boards,
world-state consequences, and faction reputation integration.
"""

import random
import time
from typing import List, Optional, Dict, Tuple
from game.core.player import Player
from game.core.npc import NPC
from game.core.items import Item, make_item


# ================================================================
# QUEST TEMPLATES (procedural generation)
# ================================================================

QUEST_TEMPLATES = [
    {"type": "fetch",       "title": "Gather {item}",
     "desc": "We need {count} {item} for the {reason}. Can you bring them?",
     "stages": 1, "base_gold": 25, "base_xp": 20},

    {"type": "kill",        "title": "Slay the {creature}",
     "desc": "{creature}s have been terrorizing the area. Eliminate {count} of them.",
     "stages": 1, "base_gold": 35, "base_xp": 40},

    {"type": "escort",      "title": "Escort {npc} to {destination}",
     "desc": "{npc} needs safe passage to {destination}. Protect them on the road.",
     "stages": 2, "base_gold": 50, "base_xp": 45},

    {"type": "deliver",     "title": "Deliver {item} to {npc}",
     "desc": "Bring {count} {item} to {npc} in {destination}. Time is of the essence.",
     "stages": 2, "base_gold": 30, "base_xp": 25},

    {"type": "investigate",  "title": "Investigate {location}",
     "desc": "Strange things have been reported at {location}. Find out what is going on.",
     "stages": 3, "base_gold": 60, "base_xp": 50},

    {"type": "defend",      "title": "Defend {settlement} from {threat}",
     "desc": "{threat}s are marching on {settlement}! Help defend the people.",
     "stages": 2, "base_gold": 70, "base_xp": 60},

    {"type": "diplomacy",   "title": "Negotiate with {kingdom}",
     "desc": "Tensions are rising. Carry our terms to {kingdom} and seek peace.",
     "stages": 3, "base_gold": 80, "base_xp": 55},

    {"type": "bounty_hunt", "title": "Capture {criminal}",
     "desc": "{criminal} is wanted for crimes in {settlement}. Bring them to justice.",
     "stages": 2, "base_gold": 55, "base_xp": 50},
]

# Fill-in data for procedural generation
FETCH_ITEMS = ["Herbs", "Iron Ore", "Wood", "Leather", "Wheat", "Stone",
               "Flowers", "Mushrooms", "Honey", "Clay"]
FETCH_REASONS = ["village healer", "blacksmith's forge", "market stalls",
                 "construction project", "temple offering", "winter stores"]
KILL_CREATURES = ["wolf", "bear", "bandit", "spider", "goblin", "skeleton",
                  "orc", "rat", "snake", "boar"]
THREATS = ["bandits", "orcs", "goblins", "undead", "wolves", "raiders"]
CRIMINAL_NAMES = ["Blackthorn", "Red Mara", "Iron Fist Kael", "The Shadow",
                  "Scarface", "Grim Dolgan", "Whisper", "Dagger Dan"]

# Difficulty tiers
DIFFICULTY_TIERS = {
    "easy":   {"level_range": (1, 4),   "gold_mult": 1.0, "xp_mult": 1.0},
    "medium": {"level_range": (3, 7),   "gold_mult": 1.5, "xp_mult": 1.5},
    "hard":   {"level_range": (6, 12),  "gold_mult": 2.5, "xp_mult": 2.0},
    "epic":   {"level_range": (10, 20), "gold_mult": 4.0, "xp_mult": 3.0},
}

# Possible reward items by difficulty
REWARD_ITEMS = {
    "easy":   ["Health Potion", "Bread", "Herbs", "Bandage"],
    "medium": ["Greater Health Potion", "Iron Sword", "Leather Armor", "Healing Tonic"],
    "hard":   ["Steel Sword", "Iron Armor", "Chain Mail", "Strength Elixir"],
    "epic":   ["Plate Armor", "Enchanted Ring", "Diamond Crown"],
}

# Named unique items for quest chain finals
UNIQUE_ITEMS = [
    {"name": "Lightbringer", "kind": "weapon", "damage": 40, "value": 500,
     "desc": "A legendary blade that glows with holy light."},
    {"name": "Aegis of the Fallen", "kind": "armor", "defense": 18, "value": 600,
     "desc": "A shield forged from the scales of a dragon."},
    {"name": "Crown of Whispers", "kind": "armor", "defense": 5, "value": 400,
     "desc": "A circlet that lets you hear the thoughts of the weak-minded."},
    {"name": "Stormcaller", "kind": "weapon", "damage": 35, "value": 450,
     "desc": "A war hammer that crackles with lightning."},
    {"name": "Shadowcloak", "kind": "armor", "defense": 8, "value": 350,
     "desc": "A cloak that makes you nearly invisible in darkness."},
    {"name": "Frostfang", "kind": "weapon", "damage": 32, "value": 400,
     "desc": "A dagger of eternal ice that slows enemies on hit."},
]


# ================================================================
# QUEST CHAIN DEFINITIONS
# ================================================================

QUEST_CHAINS = [
    {
        "id": "ruins_chain",
        "name": "The Lost Ruins",
        "quests": [
            {"type": "investigate", "title": "Investigate the Ancient Ruins",
             "desc": "Strange lights have been seen near the old ruins. Investigate.",
             "stages": 3, "difficulty": "medium"},
            {"type": "kill", "title": "Clear the Dungeon",
             "desc": "The ruins are infested with undead. Clear them out.",
             "stages": 1, "difficulty": "hard"},
            {"type": "fetch", "title": "Recover the Lost Artifact",
             "desc": "Deep in the ruins lies a powerful artifact. Retrieve it.",
             "stages": 1, "difficulty": "hard"},
        ],
        "final_reward": "unique_item",
    },
    {
        "id": "diplomatic_chain",
        "name": "The Peace Accord",
        "quests": [
            {"type": "diplomacy", "title": "Deliver the Peace Terms",
             "desc": "Carry the peace proposal to the neighboring kingdom.",
             "stages": 3, "difficulty": "medium"},
            {"type": "escort", "title": "Escort the Ambassador",
             "desc": "The ambassador needs safe passage for negotiations.",
             "stages": 2, "difficulty": "medium"},
            {"type": "defend", "title": "Defend the Summit",
             "desc": "Assassins threaten the peace summit. Protect the delegates.",
             "stages": 2, "difficulty": "hard"},
            {"type": "diplomacy", "title": "Seal the Alliance",
             "desc": "Finalize the treaty between the kingdoms.",
             "stages": 3, "difficulty": "hard"},
        ],
        "final_reward": "title",
    },
    {
        "id": "bandit_chain",
        "name": "The Bandit Scourge",
        "quests": [
            {"type": "investigate", "title": "Track the Bandits",
             "desc": "Find the bandit hideout by following their trail.",
             "stages": 3, "difficulty": "easy"},
            {"type": "bounty_hunt", "title": "Capture the Bandit Leader",
             "desc": "The bandit leader must be brought to justice.",
             "stages": 2, "difficulty": "medium"},
            {"type": "defend", "title": "End the Bandit Threat",
             "desc": "Lead the assault on the bandit stronghold.",
             "stages": 2, "difficulty": "hard"},
        ],
        "final_reward": "land",
    },
    {
        "id": "beast_chain",
        "name": "The Great Hunt",
        "quests": [
            {"type": "kill", "title": "Thin the Wolf Packs",
             "desc": "Too many wolves roam the wilds. Reduce their numbers.",
             "stages": 1, "difficulty": "easy"},
            {"type": "investigate", "title": "Find the Alpha's Den",
             "desc": "Track the alpha predator to its lair.",
             "stages": 3, "difficulty": "medium"},
            {"type": "kill", "title": "Slay the Alpha Beast",
             "desc": "A monstrous creature leads the packs. End its reign.",
             "stages": 1, "difficulty": "hard"},
        ],
        "final_reward": "unique_item",
    },
]


# ================================================================
# QUEST CLASS
# ================================================================

class Quest:
    """A quest that can be given by an NPC or found on a bounty board."""

    def __init__(self, title: str, description: str, kind: str,
                 target: str = "", target_count: int = 1,
                 reward_gold: int = 0, reward_xp: int = 0,
                 reward_item: str = "",
                 reward_reputation: int = 0,
                 reward_title: str = "",
                 reward_land: str = "",
                 reward_unique: Optional[Dict] = None,
                 difficulty: str = "medium",
                 stages: int = 1,
                 chain_id: str = "",
                 chain_step: int = 0,
                 kingdom: str = "",
                 settlement: str = "",
                 consequence: str = ""):
        self.title = title
        self.description = description
        self.kind = kind  # "kill", "fetch", "escort", "deliver", "investigate",
                          # "defend", "diplomacy", "bounty_hunt"
        self.target = target
        self.target_count = target_count
        self.progress = 0
        self.current_stage = 0
        self.total_stages = stages
        self.completed = False
        self.turned_in = False
        self.failed = False
        self.giver_name = ""
        self.difficulty = difficulty

        # Rewards
        self.reward_gold = reward_gold
        self.reward_xp = reward_xp
        self.reward_item = reward_item
        self.reward_reputation = reward_reputation
        self.reward_title = reward_title
        self.reward_land = reward_land
        self.reward_unique = reward_unique  # dict with name, kind, damage/defense, desc

        # Chain tracking
        self.chain_id = chain_id
        self.chain_step = chain_step

        # World context
        self.kingdom = kingdom
        self.settlement = settlement
        self.consequence = consequence  # what happens on success/fail

        # Timing
        self.accepted_time = 0.0
        self.expiry_day = 0  # game day when quest expires (0 = no expiry)

    @property
    def progress_text(self) -> str:
        if self.total_stages > 1:
            return f"Stage {self.current_stage + 1}/{self.total_stages} ({self.progress}/{self.target_count})"
        return f"{self.progress}/{self.target_count}"

    def check_completion(self):
        if self.progress >= self.target_count:
            if self.current_stage < self.total_stages - 1:
                # Advance to next stage
                self.current_stage += 1
                self.progress = 0
                # Later stages may have different targets (handled externally)
            else:
                self.completed = True

    def is_chain_quest(self) -> bool:
        return bool(self.chain_id)


# ================================================================
# BOUNTY BOARD
# ================================================================

class BountyBoard:
    """A bounty board at a tavern with rotating quests."""

    def __init__(self, settlement_name: str, kingdom: str = ""):
        self.settlement = settlement_name
        self.kingdom = kingdom
        self.quests: List[Quest] = []
        self.max_quests = 5
        self.last_refresh_day = -999
        self.refresh_interval = 10  # game days between refresh

    def needs_refresh(self, current_day: int) -> bool:
        return (current_day - self.last_refresh_day) >= self.refresh_interval

    def refresh(self, current_day: int, player_level: int = 1,
                settlement_names: List[str] = None,
                kingdom_names: List[str] = None,
                npc_names: List[str] = None):
        """Generate new quests for the bounty board."""
        self.quests.clear()
        self.last_refresh_day = current_day

        if settlement_names is None:
            settlement_names = [self.settlement]
        if kingdom_names is None:
            kingdom_names = [self.kingdom] if self.kingdom else ["the realm"]
        if npc_names is None:
            npc_names = ["a traveler", "a merchant", "a scholar"]

        count = random.randint(3, self.max_quests)
        for _ in range(count):
            quest = _generate_procedural_quest(
                player_level, self.settlement, self.kingdom,
                settlement_names, kingdom_names, npc_names)
            if quest:
                self.quests.append(quest)

    def take_quest(self, index: int) -> Optional[Quest]:
        """Remove and return a quest from the board."""
        if 0 <= index < len(self.quests):
            return self.quests.pop(index)
        return None


# ================================================================
# PROCEDURAL QUEST GENERATION
# ================================================================

def _difficulty_for_level(player_level: int) -> str:
    """Pick a difficulty appropriate for the player's level."""
    if player_level <= 3:
        return random.choices(["easy", "medium"], weights=[3, 1])[0]
    elif player_level <= 7:
        return random.choices(["easy", "medium", "hard"], weights=[1, 3, 1])[0]
    elif player_level <= 12:
        return random.choices(["medium", "hard", "epic"], weights=[1, 3, 1])[0]
    else:
        return random.choices(["hard", "epic"], weights=[2, 3])[0]


def _generate_procedural_quest(player_level: int,
                                settlement: str = "",
                                kingdom: str = "",
                                settlement_names: List[str] = None,
                                kingdom_names: List[str] = None,
                                npc_names: List[str] = None) -> Optional[Quest]:
    """Generate a single procedural quest from templates."""
    template = random.choice(QUEST_TEMPLATES)
    difficulty = _difficulty_for_level(player_level)
    tier = DIFFICULTY_TIERS[difficulty]

    gold = int(template["base_gold"] * tier["gold_mult"])
    xp = int(template["base_xp"] * tier["xp_mult"])
    qtype = template["type"]
    stages = template["stages"]

    # Default fill-ins
    _settlements = settlement_names or [settlement or "the village"]
    _kingdoms = kingdom_names or [kingdom or "the realm"]
    _npcs = npc_names or ["a traveler"]
    dest = random.choice(_settlements)
    npc_name = random.choice(_npcs)

    # Build title and description
    title = template["title"]
    desc = template["desc"]
    target = ""
    target_count = 1

    if qtype == "fetch":
        item = random.choice(FETCH_ITEMS)
        reason = random.choice(FETCH_REASONS)
        target_count = random.randint(2, 5)
        title = title.format(item=item)
        desc = desc.format(item=item, count=target_count, reason=reason)
        target = item

    elif qtype == "kill":
        creature = random.choice(KILL_CREATURES)
        target_count = random.randint(1, 5)
        title = title.format(creature=creature.capitalize())
        desc = desc.format(creature=creature.capitalize(), count=target_count)
        target = creature

    elif qtype == "escort":
        title = title.format(npc=npc_name, destination=dest)
        desc = desc.format(npc=npc_name, destination=dest)
        target = dest

    elif qtype == "deliver":
        item = random.choice(FETCH_ITEMS)
        target_count = random.randint(1, 3)
        title = title.format(item=item, npc=npc_name)
        desc = desc.format(item=item, count=target_count, npc=npc_name, destination=dest)
        target = item

    elif qtype == "investigate":
        location = random.choice(_settlements)
        title = title.format(location=location)
        desc = desc.format(location=location)
        target = location
        target_count = stages  # one "clue" per stage

    elif qtype == "defend":
        threat = random.choice(THREATS)
        target_settlement = random.choice(_settlements)
        title = title.format(settlement=target_settlement, threat=threat.capitalize())
        desc = desc.format(settlement=target_settlement, threat=threat.capitalize())
        target = threat
        target_count = random.randint(3, 8)

    elif qtype == "diplomacy":
        target_kingdom = random.choice(_kingdoms)
        title = title.format(kingdom=target_kingdom)
        desc = desc.format(kingdom=target_kingdom)
        target = target_kingdom
        target_count = stages

    elif qtype == "bounty_hunt":
        criminal = random.choice(CRIMINAL_NAMES)
        target_settlement = random.choice(_settlements)
        title = title.format(criminal=criminal)
        desc = desc.format(criminal=criminal, settlement=target_settlement)
        target = criminal

    # Determine reward item
    reward_item = ""
    if random.random() < 0.4:
        reward_item = random.choice(REWARD_ITEMS.get(difficulty, REWARD_ITEMS["easy"]))

    # Reputation reward scales with difficulty
    rep_amount = {"easy": 5, "medium": 10, "hard": 15, "epic": 20}.get(difficulty, 10)

    # Consequences
    consequence = ""
    if qtype == "defend":
        consequence = "defend_settlement"
    elif qtype == "escort":
        consequence = "npc_safety"
    elif qtype == "diplomacy":
        consequence = "diplomatic"

    quest = Quest(
        title=title,
        description=desc,
        kind=qtype,
        target=target,
        target_count=target_count,
        reward_gold=gold,
        reward_xp=xp,
        reward_item=reward_item,
        reward_reputation=rep_amount,
        difficulty=difficulty,
        stages=stages,
        kingdom=kingdom,
        settlement=settlement,
        consequence=consequence,
    )
    return quest


# ================================================================
# QUEST SYSTEM (main manager)
# ================================================================

class QuestSystem:
    """Manages quests, bounty boards, quest chains, and world consequences."""

    def __init__(self):
        self.active_quests: List[Quest] = []
        self.completed_quests: List[Quest] = []
        self.failed_quests: List[Quest] = []
        self.bounty_boards: Dict[str, BountyBoard] = {}  # settlement -> board
        self.active_chains: Dict[str, int] = {}  # chain_id -> current step
        self.completed_chains: List[str] = []
        self.event_log: List[str] = []

        # Legacy templates (kept for backward compatibility with NPC quest giving)
        self.available_templates = self._create_templates()

    # ------------------------------------------------------------------
    # Legacy templates (backward compat)
    # ------------------------------------------------------------------

    def _create_templates(self) -> List[Dict]:
        return [
            {"title": "Wolf Problem", "desc": "Wolves are threatening the village. Thin their numbers.",
             "kind": "kill", "target": "wolf", "count": 3, "gold": 30, "xp": 40},
            {"title": "Bear Menace", "desc": "A bear has been spotted near the farms. Deal with it.",
             "kind": "kill", "target": "bear", "count": 1, "gold": 50, "xp": 35},
            {"title": "Bandit Cleanup", "desc": "Bandits are causing trouble. Take care of them.",
             "kind": "kill", "target": "bandit", "count": 2, "gold": 40, "xp": 50},
            {"title": "Herb Gathering", "desc": "I need medicinal herbs for my practice.",
             "kind": "fetch", "target": "Herbs", "count": 3, "gold": 25, "xp": 20},
            {"title": "Iron Delivery", "desc": "Bring me some iron ore for my forge.",
             "kind": "fetch", "target": "Iron Ore", "count": 2, "gold": 35, "xp": 25},
            {"title": "Wood Supply", "desc": "We need wood for construction. Can you help?",
             "kind": "fetch", "target": "Wood", "count": 5, "gold": 20, "xp": 15},
            {"title": "Ruins Expedition", "desc": "Explore the nearby ruins and bring back a relic.",
             "kind": "fetch", "target": "Ancient Relic", "count": 1, "gold": 80, "xp": 60,
             "reward_item": "Greater Health Potion"},
            {"title": "Spider Infestation", "desc": "Spiders are infesting the forest. Clear them out.",
             "kind": "kill", "target": "spider", "count": 4, "gold": 25, "xp": 30},
        ]

    # ------------------------------------------------------------------
    # NPC quest generation (backward-compatible + enhanced)
    # ------------------------------------------------------------------

    def generate_quest_for_npc(self, npc: NPC, player_level: int = 1,
                                settlement: str = "",
                                kingdom: str = "",
                                settlement_names: List[str] = None,
                                kingdom_names: List[str] = None,
                                npc_names: List[str] = None) -> Optional[Quest]:
        """Generate a quest appropriate for an NPC's profession.

        Uses procedural generation when possible, falls back to legacy templates.
        """
        if npc.quest is not None:
            return None

        # 60% chance to use new procedural system
        if random.random() < 0.6 and player_level > 0:
            quest = _generate_procedural_quest(
                player_level,
                settlement=settlement or getattr(npc, 'home_settlement', ''),
                kingdom=kingdom,
                settlement_names=settlement_names,
                kingdom_names=kingdom_names,
                npc_names=npc_names,
            )
            if quest:
                quest.giver_name = npc.name
                npc.quest = quest
                npc.has_quest_marker = True
                return quest

        # Fallback: legacy template system
        suitable = []
        for t in self.available_templates:
            kind = t["kind"]
            if npc.profession in ("Guard", "Ranger") and kind == "kill":
                suitable.append(t)
            elif npc.profession in ("Healer", "Scholar") and kind == "fetch":
                suitable.append(t)
            elif npc.profession in ("Blacksmith",) and t["target"] in ("Iron Ore", "Wood"):
                suitable.append(t)
            elif npc.profession == "Farmer" and t["target"] == "wolf":
                suitable.append(t)
            else:
                suitable.append(t)

        if not suitable:
            return None

        template = random.choice(suitable)
        quest = Quest(
            title=template["title"],
            description=template["desc"],
            kind=template["kind"],
            target=template["target"],
            target_count=template["count"],
            reward_gold=template["gold"],
            reward_xp=template["xp"],
            reward_item=template.get("reward_item", ""),
            reward_reputation=5,
            kingdom=kingdom,
            settlement=settlement or getattr(npc, 'home_settlement', ''),
        )
        quest.giver_name = npc.name
        npc.quest = quest
        npc.has_quest_marker = True
        return quest

    # ------------------------------------------------------------------
    # Bounty Boards
    # ------------------------------------------------------------------

    def register_bounty_board(self, settlement_name: str, kingdom: str = ""):
        """Register a bounty board at a settlement (typically a tavern)."""
        if settlement_name not in self.bounty_boards:
            self.bounty_boards[settlement_name] = BountyBoard(settlement_name, kingdom)

    def get_bounty_board(self, settlement_name: str) -> Optional[BountyBoard]:
        return self.bounty_boards.get(settlement_name)

    def refresh_bounty_boards(self, current_day: int, player_level: int = 1,
                               settlement_names: List[str] = None,
                               kingdom_names: List[str] = None,
                               npc_names: List[str] = None):
        """Refresh all bounty boards that are due for new quests."""
        for name, board in self.bounty_boards.items():
            if board.needs_refresh(current_day):
                board.refresh(current_day, player_level,
                             settlement_names, kingdom_names, npc_names)

    def interact_bounty_board(self, settlement_name: str) -> List[Dict]:
        """Get quest listings from a bounty board for UI display."""
        board = self.bounty_boards.get(settlement_name)
        if not board or not board.quests:
            return []
        listings = []
        for i, q in enumerate(board.quests):
            listings.append({
                "index": i,
                "title": q.title,
                "description": q.description,
                "difficulty": q.difficulty,
                "reward_gold": q.reward_gold,
                "reward_xp": q.reward_xp,
                "reward_item": q.reward_item,
                "type": q.kind,
            })
        return listings

    def accept_from_bounty_board(self, settlement_name: str, index: int) -> Optional[Quest]:
        """Accept a quest from a bounty board."""
        board = self.bounty_boards.get(settlement_name)
        if not board:
            return None
        quest = board.take_quest(index)
        if quest and self.accept_quest(quest):
            return quest
        # Put it back if we couldn't accept
        if quest and board:
            board.quests.insert(index, quest)
        return None

    # ------------------------------------------------------------------
    # Quest chains
    # ------------------------------------------------------------------

    def start_chain(self, chain_id: str, kingdom: str = "",
                    settlement: str = "") -> Optional[Quest]:
        """Start a quest chain if not already active or completed."""
        if chain_id in self.active_chains or chain_id in self.completed_chains:
            return None

        chain_def = None
        for c in QUEST_CHAINS:
            if c["id"] == chain_id:
                chain_def = c
                break
        if not chain_def:
            return None

        self.active_chains[chain_id] = 0
        return self._create_chain_quest(chain_def, 0, kingdom, settlement)

    def _create_chain_quest(self, chain_def: Dict, step: int,
                             kingdom: str, settlement: str) -> Optional[Quest]:
        """Create the quest for a specific step in a chain."""
        quests_defs = chain_def["quests"]
        if step >= len(quests_defs):
            return None

        qdef = quests_defs[step]
        difficulty = qdef.get("difficulty", "medium")
        tier = DIFFICULTY_TIERS[difficulty]
        base_template = None
        for t in QUEST_TEMPLATES:
            if t["type"] == qdef["type"]:
                base_template = t
                break
        base_gold = base_template["base_gold"] if base_template else 40
        base_xp = base_template["base_xp"] if base_template else 30

        gold = int(base_gold * tier["gold_mult"])
        xp = int(base_xp * tier["xp_mult"])

        # Final quest in chain gets special reward
        is_final = (step == len(quests_defs) - 1)
        reward_unique = None
        reward_title = ""
        reward_land = ""

        if is_final:
            gold = int(gold * 2)  # Double gold for chain finale
            xp = int(xp * 2)
            final_reward = chain_def.get("final_reward", "")
            if final_reward == "unique_item":
                reward_unique = random.choice(UNIQUE_ITEMS)
            elif final_reward == "title":
                reward_title = f"Champion of {kingdom or 'the Realm'}"
            elif final_reward == "land":
                reward_land = settlement or "a small estate"

        rep_amount = {"easy": 5, "medium": 10, "hard": 15, "epic": 20}.get(difficulty, 10)
        if is_final:
            rep_amount *= 2

        # Determine target/count based on quest type
        target = ""
        target_count = 1
        if qdef["type"] == "kill":
            target = random.choice(KILL_CREATURES)
            target_count = random.randint(3, 8)
        elif qdef["type"] == "fetch":
            target = random.choice(FETCH_ITEMS)
            target_count = random.randint(2, 5)
        elif qdef["type"] in ("investigate", "diplomacy"):
            target = settlement or "the area"
            target_count = qdef.get("stages", 3)
        elif qdef["type"] == "defend":
            target = random.choice(THREATS)
            target_count = random.randint(5, 10)
        elif qdef["type"] == "escort":
            target = settlement or "the destination"
        elif qdef["type"] == "bounty_hunt":
            target = random.choice(CRIMINAL_NAMES)

        quest = Quest(
            title=qdef["title"],
            description=qdef["desc"],
            kind=qdef["type"],
            target=target,
            target_count=target_count,
            reward_gold=gold,
            reward_xp=xp,
            reward_reputation=rep_amount,
            reward_title=reward_title,
            reward_land=reward_land,
            reward_unique=reward_unique,
            difficulty=difficulty,
            stages=qdef.get("stages", 1),
            chain_id=chain_def["id"],
            chain_step=step,
            kingdom=kingdom,
            settlement=settlement,
        )

        return quest

    def _advance_chain(self, quest: Quest) -> Optional[Quest]:
        """After completing a chain quest, create the next one."""
        chain_id = quest.chain_id
        if chain_id not in self.active_chains:
            return None

        chain_def = None
        for c in QUEST_CHAINS:
            if c["id"] == chain_id:
                chain_def = c
                break
        if not chain_def:
            return None

        next_step = quest.chain_step + 1
        if next_step >= len(chain_def["quests"]):
            # Chain complete
            del self.active_chains[chain_id]
            self.completed_chains.append(chain_id)
            self.event_log.append(
                f"Quest chain \"{chain_def['name']}\" completed!")
            return None

        self.active_chains[chain_id] = next_step
        next_quest = self._create_chain_quest(
            chain_def, next_step, quest.kingdom, quest.settlement)
        if next_quest:
            self.event_log.append(
                f"New quest in chain \"{chain_def['name']}\": {next_quest.title}")
        return next_quest

    # ------------------------------------------------------------------
    # Core quest management
    # ------------------------------------------------------------------

    def accept_quest(self, quest: Quest) -> bool:
        if len(self.active_quests) >= 10:
            return False
        for q in self.active_quests:
            if q.title == quest.title and not q.completed:
                return False
        quest.accepted_time = time.time()
        self.active_quests.append(quest)
        return True

    def abandon_quest(self, quest: Quest):
        """Abandon an active quest."""
        if quest in self.active_quests:
            self.active_quests.remove(quest)
            quest.failed = True
            self.failed_quests.append(quest)
            # Handle chain abandonment
            if quest.chain_id and quest.chain_id in self.active_chains:
                del self.active_chains[quest.chain_id]

    def on_kill(self, creature_kind: str):
        """Notify quest system of a creature kill."""
        kind_lower = creature_kind.lower()
        for quest in self.active_quests:
            if quest.kind == "kill" and not quest.completed:
                target_lower = quest.target.lower()
                if target_lower == kind_lower or target_lower in kind_lower:
                    quest.progress += 1
                    quest.check_completion()

    def on_collect(self, item_name: str):
        """Notify quest system of item collection."""
        name_lower = item_name.lower()
        for quest in self.active_quests:
            if quest.kind in ("fetch", "deliver") and not quest.completed:
                if quest.target.lower() == name_lower or quest.target == item_name:
                    quest.progress += 1
                    quest.check_completion()

    def on_reach_location(self, location_name: str):
        """Notify quest system that player reached a location."""
        name_lower = location_name.lower()
        for quest in self.active_quests:
            if quest.kind in ("investigate", "escort", "diplomacy") and not quest.completed:
                if quest.target.lower() == name_lower or name_lower in quest.target.lower():
                    quest.progress += 1
                    quest.check_completion()

    def on_defend_success(self, settlement_name: str):
        """Notify quest system that a settlement was defended."""
        name_lower = settlement_name.lower()
        for quest in self.active_quests:
            if quest.kind == "defend" and not quest.completed:
                if name_lower in quest.settlement.lower() or name_lower in quest.title.lower():
                    quest.progress = quest.target_count
                    quest.check_completion()

    def on_npc_interaction(self, npc_name: str):
        """Notify quest system of an NPC interaction (for bounty hunts, diplomacy)."""
        name_lower = npc_name.lower()
        for quest in self.active_quests:
            if quest.kind == "bounty_hunt" and not quest.completed:
                if name_lower in quest.target.lower():
                    quest.progress += 1
                    quest.check_completion()

    # ------------------------------------------------------------------
    # Turn in and rewards
    # ------------------------------------------------------------------

    def turn_in_quest(self, quest: Quest, player: Player,
                      faction_system=None) -> str:
        """Turn in a completed quest for rewards.

        Returns a reward description string.
        """
        if not quest.completed or quest.turned_in:
            return ""

        quest.turned_in = True
        player.gold += quest.reward_gold
        player.gain_xp(quest.reward_xp)
        player.quests_completed += 1

        reward_text = f"Quest \"{quest.title}\" complete! +{quest.reward_gold} gold, +{quest.reward_xp} XP"

        # Standard item reward
        if quest.reward_item:
            item = make_item(quest.reward_item)
            if item and player.add_item(item):
                reward_text += f", received {quest.reward_item}"

        # Unique item reward (chain finales)
        if quest.reward_unique:
            u = quest.reward_unique
            from game.settings import ITEM_WEAPON, ITEM_ARMOR
            kind = ITEM_WEAPON if u["kind"] == "weapon" else ITEM_ARMOR
            unique_item = Item(
                name=u["name"], kind=kind, value=u.get("value", 200),
                damage=u.get("damage", 0), defense=u.get("defense", 0),
                description=u.get("desc", "A legendary item."),
            )
            if player.add_item(unique_item):
                reward_text += f", received legendary: {u['name']}"

        # Reputation reward
        if quest.reward_reputation and quest.kingdom and faction_system:
            faction_system.on_quest_complete(quest.kingdom, quest.difficulty)
            reward_text += f", +{quest.reward_reputation} reputation with {quest.kingdom}"

        # Title reward
        if quest.reward_title:
            player.title = quest.reward_title
            reward_text += f", earned title: \"{quest.reward_title}\""

        # Land reward
        if quest.reward_land:
            reward_text += f", granted land: {quest.reward_land}"
            # Land ownership tracked externally (territory system)

        # World-state consequences
        self._apply_consequences(quest, success=True, faction_system=faction_system)

        # Move from active to completed
        if quest in self.active_quests:
            self.active_quests.remove(quest)
        self.completed_quests.append(quest)

        # Advance quest chain
        if quest.is_chain_quest():
            next_quest = self._advance_chain(quest)
            if next_quest:
                self.accept_quest(next_quest)
                reward_text += f"\n  -> New quest: \"{next_quest.title}\""

        self.event_log.append(reward_text)
        return reward_text

    def fail_quest(self, quest: Quest, reason: str = "expired",
                   npcs: list = None, player=None, faction_system=None):
        """Explicitly fail a quest and apply consequences.

        Args:
            reason: "expired", "abandoned", "rejected" — affects severity
            npcs: list of world NPCs (to find quest giver and apply social effects)
            player: player object (for reputation/gold penalties)
            faction_system: for faction reputation changes
        """
        quest.failed = True
        if quest in self.active_quests:
            self.active_quests.remove(quest)
        self.failed_quests.append(quest)

        # Apply world-state consequences
        self._apply_consequences(quest, success=False,
                                 faction_system=faction_system,
                                 npcs=npcs, player=player, reason=reason)

        self.event_log.append(f"Quest \"{quest.title}\" failed ({reason})!")

    def _apply_consequences(self, quest: Quest, success: bool = True,
                             faction_system=None, npcs: list = None,
                             player=None, reason: str = ""):
        """Apply world-state consequences of quest completion or failure."""
        consequence = quest.consequence

        # --- SUCCESS CONSEQUENCES ---
        if success:
            if consequence == "defend_settlement":
                if faction_system and quest.kingdom:
                    faction_system.on_defend_settlement(quest.kingdom)
                self.event_log.append(
                    f"{quest.settlement} is safe! The settlement will prosper.")
            elif consequence == "diplomatic":
                self.event_log.append(
                    f"Diplomatic success! Relations with {quest.target} improve.")
            return

        # --- FAILURE CONSEQUENCES ---
        giver = None
        if npcs and quest.giver_name:
            for npc in npcs:
                if npc.name == quest.giver_name and npc.alive:
                    giver = npc
                    break

        # Quest giver is always disappointed
        if giver:
            giver.add_memory("quest", f"The player failed my quest: {quest.title}", 4)
            rel_penalty = -5
            title = getattr(giver, 'title', 'commoner')
            is_ruler = getattr(giver, 'is_ruler', False)

            # Severity scales with NPC importance
            if is_ruler or title in ('ruler', 'king', 'queen', 'lord', 'duke'):
                rel_penalty = -20
            elif title in ('guard', 'knight', 'captain'):
                rel_penalty = -12
            elif giver.player_relationship > 30:
                rel_penalty = -8  # friends are more forgiving

            if reason == "abandoned":
                rel_penalty = int(rel_penalty * 1.5)  # abandoning is worse than expiring
                giver.add_memory("conflict",
                    f"The player abandoned my quest! Unreliable.", 5)

            giver.player_relationship = max(-100,
                giver.player_relationship + rel_penalty)

            # Emotional reaction
            es = getattr(giver, 'emotion_state', None)
            if es and hasattr(es, 'primary'):
                if reason == "abandoned":
                    es.primary["anger"] = min(1.0, es.primary.get("anger", 0) + 0.3)
                else:
                    es.primary["sadness"] = min(1.0, es.primary.get("sadness", 0) + 0.2)

            # Giver tells friends about the failure (reputation spread)
            if npcs and rel_penalty <= -10:
                for fname in getattr(giver, 'friends', [])[:5]:
                    for other in npcs:
                        if other.name == fname and other.alive:
                            other.player_relationship = max(-100,
                                other.player_relationship - 3)
                            other.add_memory("social",
                                f"{giver.name} said the player is unreliable", 2)
                            break

        # Type-specific failure consequences
        if consequence == "defend_settlement":
            self.event_log.append(
                f"{quest.settlement} suffered from the attack! Morale drops.")
            # Settlement NPCs lose morale
            if npcs:
                for npc in npcs:
                    if getattr(npc, 'home_settlement', '') == quest.settlement:
                        npc.mood = max(-1.0, getattr(npc, 'mood', 0) - 0.3)
                        npc.add_memory("crisis",
                            f"Our settlement was attacked and no one came to help", 4)

        elif consequence == "npc_safety":
            self.event_log.append(
                f"The escort failed. The traveler did not survive.")
            # The escorted NPC "dies" — mark in memories
            if npcs:
                for npc in npcs:
                    if npc.name == quest.target and npc.alive:
                        npc.hp = 0
                        npc.alive = False
                        self.event_log.append(f"{npc.name} was killed during failed escort.")
                        break

        elif consequence == "diplomatic":
            self.event_log.append(
                f"Diplomacy failed. Tensions with {quest.target} increase.")
            if faction_system and quest.kingdom:
                faction_system.on_diplomatic_failure(quest.kingdom, quest.target)

        # Player reputation penalty for failures
        if player and faction_system and quest.kingdom and reason != "expired":
            rep_loss = {"easy": 3, "medium": 5, "hard": 8, "epic": 12
                       }.get(quest.difficulty, 5)
            faction_system.adjust_reputation(quest.kingdom, -rep_loss)

        # Difficulty-scaled gold penalty for abandonment (broken contract)
        if player and reason == "abandoned":
            penalty = {"easy": 5, "medium": 15, "hard": 30, "epic": 50
                      }.get(quest.difficulty, 10)
            if player.gold >= penalty:
                player.gold -= penalty
                self.event_log.append(
                    f"Lost {penalty} gold for breaking quest contract.")

    # ------------------------------------------------------------------
    # Quest expiry / failure
    # ------------------------------------------------------------------

    def check_expiry(self, current_day: int, npcs: list = None,
                     player=None, faction_system=None):
        """Fail quests that have expired."""
        expired = []
        for quest in self.active_quests:
            if quest.expiry_day > 0 and current_day > quest.expiry_day:
                expired.append(quest)

        for quest in expired:
            self.fail_quest(quest, reason="expired",
                           npcs=npcs, player=player,
                           faction_system=faction_system)
            if quest.chain_id and quest.chain_id in self.active_chains:
                del self.active_chains[quest.chain_id]

    # ------------------------------------------------------------------
    # Update (periodic refresh, expiry checks)
    # ------------------------------------------------------------------

    def update(self, dt: float, current_day: int, player_level: int = 1,
               settlement_names: List[str] = None,
               kingdom_names: List[str] = None,
               npc_names: List[str] = None):
        """Periodic quest system update."""
        # Refresh bounty boards
        self.refresh_bounty_boards(
            current_day, player_level,
            settlement_names, kingdom_names, npc_names)

        # Check expiry
        self.check_expiry(current_day)

    # ------------------------------------------------------------------
    # Reports
    # ------------------------------------------------------------------

    def get_event_log(self) -> List[str]:
        msgs = list(self.event_log)
        self.event_log.clear()
        return msgs

    def get_quest_journal(self) -> str:
        """Get a formatted quest journal."""
        lines = ["=== Active Quests ==="]
        for q in self.active_quests:
            chain_tag = f" [{q.chain_id} {q.chain_step+1}]" if q.chain_id else ""
            lines.append(f"  [{q.difficulty.upper()}] {q.title}{chain_tag}")
            lines.append(f"    {q.description}")
            lines.append(f"    Progress: {q.progress_text}")
            rewards = f"    Rewards: {q.reward_gold}g, {q.reward_xp} XP"
            if q.reward_item:
                rewards += f", {q.reward_item}"
            if q.reward_title:
                rewards += f", title: {q.reward_title}"
            if q.reward_land:
                rewards += f", land: {q.reward_land}"
            if q.reward_unique:
                rewards += f", legendary: {q.reward_unique['name']}"
            lines.append(rewards)

        if not self.active_quests:
            lines.append("  No active quests.")

        lines.append(f"\nCompleted: {len(self.completed_quests)} | "
                     f"Failed: {len(self.failed_quests)} | "
                     f"Chains done: {len(self.completed_chains)}")
        return "\n".join(lines)
