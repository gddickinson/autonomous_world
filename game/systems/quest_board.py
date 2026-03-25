"""Tavern quest board system — context-aware quest generation for taverns.

Quests refresh every 7 game days. Players interact via E key near a tavern.
Reputation-gated quests require certain faction ranks.
"""

import random
from typing import List, Optional, Dict

from game.systems.quests import Quest

# Minimum faction rank index required for each quest type.
# See faction_ranks.py RANKS: 0=Outsider, 1=Citizen, 2=Trusted, 3=Honored, 4=Noble
QUEST_RANK_REQUIREMENTS = {
    "bounty": 0,          # anyone can take bounty quests
    "gather": 0,          # anyone can gather
    "escort": 1,          # Citizen+ (trusted with responsibility)
    "delivery": 2,        # Trusted+ (diplomatic access to allied kingdoms)
    "investigation": 3,   # Honored+ (dangerous ruins)
    "kingdom_special": 4, # Noble+ (kingdom-specific special quests)
}

# Bounty targets by threat type
BOUNTY_TARGETS = {
    "wolves": {"creature": "wolf", "desc": "Wolves have been attacking livestock",
               "count_range": (2, 5)},
    "bandits": {"creature": "bandit", "desc": "Bandits are raiding travelers on the roads",
                "count_range": (2, 4)},
    "undead": {"creature": "skeleton", "desc": "The dead walk near the old ruins",
               "count_range": (3, 6)},
    "spiders": {"creature": "spider", "desc": "Giant spiders infest the nearby woods",
                "count_range": (3, 5)},
    "goblins": {"creature": "goblin", "desc": "Goblins have been spotted near the settlement",
                "count_range": (3, 6)},
    "orcs": {"creature": "orc", "desc": "An orc war band threatens the region",
             "count_range": (2, 4)},
    "bears": {"creature": "bear", "desc": "A dangerous bear prowls near the farms",
              "count_range": (1, 2)},
}

# Gather quest items by terrain
GATHER_BY_TERRAIN = {
    "forest": [("Herbs", "medicinal herbs from the forest"),
               ("Wood", "timber for construction"),
               ("Mushrooms", "edible mushrooms from the undergrowth")],
    "mountain": [("Iron Ore", "iron ore from the mountain slopes"),
                 ("Stone", "quality stone for building")],
    "plains": [("Wheat", "wheat from the wild fields"),
               ("Flowers", "rare flowers for the healer")],
    "swamp": [("Herbs", "rare swamp herbs for potions"),
              ("Mushrooms", "rare fungus from the marshes")],
    "desert": [("Stone", "sandstone blocks"),
               ("Clay", "clay from the dry riverbed")],
}

# Delivery items
DELIVERY_ITEMS = [
    ("sealed letter", "an urgent message"),
    ("medicine bundle", "healing supplies"),
    ("trade goods", "merchant wares"),
    ("iron tools", "blacksmith equipment"),
    ("provisions", "food supplies"),
    ("tax records", "official documents"),
]

# Investigation flavors
INVESTIGATION_FLAVORS = [
    ("strange lights", "Eerie lights have been seen at {location} after dark."),
    ("disappearances", "People have gone missing near {location}."),
    ("ancient power", "An ancient power stirs within {location}."),
    ("odd sounds", "Unnatural sounds echo from {location} at night."),
    ("dark ritual", "Signs of dark rituals have been found near {location}."),
]

# Escort NPC types
ESCORT_NPCS = [
    "a merchant", "a scholar", "a healer", "a diplomat",
    "a pilgrim", "a courier", "a surveyor", "a refugee",
]


# ================================================================
# QUEST GENERATORS
# ================================================================

def generate_bounty_quest(settlement_name: str, player_level: int = 1,
                          threat_type: str = "") -> Quest:
    """Generate a bounty quest to kill nearby threats."""
    if not threat_type or threat_type not in BOUNTY_TARGETS:
        threat_type = random.choice(list(BOUNTY_TARGETS.keys()))

    info = BOUNTY_TARGETS[threat_type]
    count = random.randint(*info["count_range"])

    # Scale with player level
    level_mult = 1.0 + (player_level - 1) * 0.15
    base_gold = random.randint(15, 50)
    gold = int(base_gold * level_mult)
    xp = int(gold * 0.8)

    difficulty = "easy" if player_level <= 3 else "medium" if player_level <= 7 else "hard"

    title = f"Bounty: Slay {count} {info['creature'].capitalize()}s"
    if count == 1:
        title = f"Bounty: Slay the {info['creature'].capitalize()}"

    desc = (f"{info['desc']} near {settlement_name}. "
            f"Eliminate {count} of them and report back to claim your reward.")

    return Quest(
        title=title,
        description=desc,
        kind="kill",
        target=info["creature"],
        target_count=count,
        reward_gold=gold,
        reward_xp=xp,
        difficulty=difficulty,
        settlement=settlement_name,
    )


def generate_delivery_quest(settlement_name: str, dest_settlement: str,
                            player_level: int = 1) -> Quest:
    """Generate a delivery quest to another settlement."""
    item_name, item_desc = random.choice(DELIVERY_ITEMS)
    level_mult = 1.0 + (player_level - 1) * 0.1
    gold = int(random.randint(10, 30) * level_mult)
    xp = int(gold * 1.2)

    title = f"Deliver {item_name.capitalize()} to {dest_settlement}"
    desc = (f"Carry {item_desc} from {settlement_name} to {dest_settlement}. "
            f"The recipient is expecting the delivery. Travel safely.")

    return Quest(
        title=title,
        description=desc,
        kind="deliver",
        target=dest_settlement,
        target_count=1,
        reward_gold=gold,
        reward_xp=xp,
        difficulty="easy" if player_level <= 4 else "medium",
        settlement=settlement_name,
    )


def generate_escort_quest(settlement_name: str, dest_settlement: str,
                          player_level: int = 1) -> Quest:
    """Generate an escort quest to protect a traveler."""
    npc_type = random.choice(ESCORT_NPCS)
    level_mult = 1.0 + (player_level - 1) * 0.12
    gold = int(random.randint(20, 40) * level_mult)
    xp = int(gold * 1.0)

    title = f"Escort {npc_type} to {dest_settlement}"
    desc = (f"Protect {npc_type} traveling from {settlement_name} "
            f"to {dest_settlement}. The roads are dangerous — bandits "
            f"and wild beasts lurk along the way.")

    return Quest(
        title=title,
        description=desc,
        kind="escort",
        target=dest_settlement,
        target_count=1,
        reward_gold=gold,
        reward_xp=xp,
        difficulty="medium" if player_level <= 5 else "hard",
        settlement=settlement_name,
        consequence="npc_safety",
    )


def generate_gather_quest(settlement_name: str, terrain_type: str = "",
                          player_level: int = 1) -> Quest:
    """Generate a gathering quest based on nearby terrain."""
    terrain = terrain_type if terrain_type in GATHER_BY_TERRAIN else "forest"
    item_name, item_flavor = random.choice(GATHER_BY_TERRAIN[terrain])
    count = random.randint(2, 5)

    level_mult = 1.0 + (player_level - 1) * 0.1
    gold = int(random.randint(10, 25) * level_mult)
    xp = int(gold * 0.7)

    title = f"Gather {count} {item_name}"
    desc = (f"The people of {settlement_name} need {item_flavor}. "
            f"Collect {count} {item_name} and bring them back.")

    return Quest(
        title=title,
        description=desc,
        kind="fetch",
        target=item_name,
        target_count=count,
        reward_gold=gold,
        reward_xp=xp,
        difficulty="easy",
        settlement=settlement_name,
    )


def generate_investigation_quest(settlement_name: str,
                                 location_name: str = "",
                                 player_level: int = 1) -> Quest:
    """Generate an investigation quest about nearby ruins or mystery."""
    if not location_name:
        location_name = f"the ruins near {settlement_name}"

    flavor_name, flavor_desc = random.choice(INVESTIGATION_FLAVORS)
    desc_text = flavor_desc.format(location=location_name)

    level_mult = 1.0 + (player_level - 1) * 0.15
    gold = int(random.randint(15, 35) * level_mult)
    xp = int(gold * 1.5)

    title = f"Investigate {flavor_name} at {location_name}"
    desc = (f"{desc_text} Travel there, search for clues, "
            f"and report your findings.")

    # Rare chance of artifact reward for high-level investigation quests
    reward_item = ""
    if player_level >= 6 and random.random() < 0.15:
        reward_item = random.choice(["Amulet of the Sea", "Staff of the Archmage"])

    return Quest(
        title=title,
        description=desc,
        kind="investigate",
        target=location_name,
        target_count=3,
        reward_gold=gold,
        reward_xp=xp,
        reward_item=reward_item,
        difficulty="medium" if player_level <= 5 else "hard",
        settlement=settlement_name,
    )


# ================================================================
# QUEST BOARD CLASS
# ================================================================

class QuestBoard:
    """A quest board at a tavern that generates context-appropriate quests.

    Attributes:
        settlement_name: The settlement this board belongs to.
        quests: Currently posted quests.
        last_refresh_day: Game day of last quest refresh.
        refresh_interval: Days between quest refreshes (default 7).
    """

    def __init__(self, settlement_name: str,
                 nearby_settlements: List[str] = None,
                 terrain_context: Dict[str, int] = None,
                 threats: List[str] = None,
                 kingdom: str = ""):
        self.settlement_name = settlement_name
        self.nearby_settlements = nearby_settlements or []
        self.terrain_context = terrain_context or {}
        self.threats = threats or []
        self.kingdom = kingdom
        self.quests: List[Quest] = []
        self.last_refresh_day = -999
        self.refresh_interval = 7
        self.max_quests = 4

    def needs_refresh(self, current_day: int) -> bool:
        """Check if the board needs new quests."""
        return (current_day - self.last_refresh_day) >= self.refresh_interval

    def refresh(self, current_day: int, player_level: int = 1,
                player_rank_index: int = 0):
        """Generate quests filtered by player rank (see QUEST_RANK_REQUIREMENTS)."""
        self.quests.clear()
        self.last_refresh_day = current_day
        count = random.randint(2, self.max_quests)
        dominant_terrain = "forest"
        if self.terrain_context:
            dominant_terrain = max(self.terrain_context,
                                  key=self.terrain_context.get)

        # Build generator pool filtered by rank
        generators = []
        threat = random.choice(self.threats) if self.threats else ""
        _rr = QUEST_RANK_REQUIREMENTS
        if player_rank_index >= _rr.get("bounty", 0):
            generators.append(("bounty", 3))
        if self.nearby_settlements:
            if player_rank_index >= _rr.get("delivery", 0):
                generators.append(("delivery", 2))
            if player_rank_index >= _rr.get("escort", 0):
                generators.append(("escort", 2))
        if player_rank_index >= _rr.get("gather", 0):
            generators.append(("gather", 2))
        if player_rank_index >= _rr.get("investigation", 0):
            generators.append(("investigation", 1))
        if player_rank_index >= _rr.get("kingdom_special", 4) and self.kingdom:
            generators.append(("kingdom_special", 1))
        if not generators:
            generators.append(("bounty", 3))
            generators.append(("gather", 2))

        used_types = set()
        for _ in range(count):
            weighted = []
            for gtype, weight in generators:
                if gtype in used_types:
                    weighted.append((gtype, max(1, weight - 2)))
                else:
                    weighted.append((gtype, weight))
            types, weights = zip(*weighted)
            chosen = random.choices(types, weights=weights, k=1)[0]
            used_types.add(chosen)
            quest = self._generate_quest(chosen, player_level,
                                         dominant_terrain, threat)
            if quest:
                self.quests.append(quest)

    def _generate_quest(self, quest_type: str, player_level: int,
                        terrain: str, threat: str) -> Optional[Quest]:
        """Generate a single quest of the given type."""
        name = self.settlement_name

        if quest_type == "bounty":
            return generate_bounty_quest(name, player_level, threat)

        elif quest_type == "delivery":
            if self.nearby_settlements:
                dest = random.choice(self.nearby_settlements)
                return generate_delivery_quest(name, dest, player_level)

        elif quest_type == "escort":
            if self.nearby_settlements:
                dest = random.choice(self.nearby_settlements)
                return generate_escort_quest(name, dest, player_level)

        elif quest_type == "gather":
            return generate_gather_quest(name, terrain, player_level)

        elif quest_type == "investigation":
            return generate_investigation_quest(name,
                                                player_level=player_level)

        elif quest_type == "kingdom_special":
            from game.systems.quest_board_init import generate_kingdom_special_quest
            return generate_kingdom_special_quest(
                name, kingdom=self.kingdom,
                player_level=player_level)

        # Fallback to bounty
        return generate_bounty_quest(name, player_level)

    def take_quest(self, index: int) -> Optional[Quest]:
        """Remove and return a quest from the board."""
        if 0 <= index < len(self.quests):
            return self.quests.pop(index)
        return None

    def get_listings(self) -> List[Dict]:
        """Get quest listings for UI display."""
        listings = []
        for i, q in enumerate(self.quests):
            listing = {
                "index": i,
                "title": q.title,
                "description": q.description,
                "difficulty": q.difficulty,
                "reward_gold": q.reward_gold,
                "reward_xp": q.reward_xp,
                "kind": q.kind,
            }
            # Add reward_item if present
            if getattr(q, 'reward_item', ''):
                listing["reward_item"] = q.reward_item
            listings.append(listing)
        return listings


# ================================================================
# QUEST BOARD MANAGER
# ================================================================

class QuestBoardManager:
    """Manages all quest boards across settlements.

    Created once during game initialization, holds all tavern quest boards,
    and handles refresh logic and player interaction.
    """

    def __init__(self):
        self.boards: Dict[str, QuestBoard] = {}

    def register_board(self, settlement_name: str,
                       nearby_settlements: List[str] = None,
                       terrain_context: Dict[str, int] = None,
                       threats: List[str] = None,
                       kingdom: str = ""):
        """Register a quest board for a settlement's tavern."""
        if settlement_name not in self.boards:
            self.boards[settlement_name] = QuestBoard(
                settlement_name,
                nearby_settlements=nearby_settlements,
                terrain_context=terrain_context,
                threats=threats,
                kingdom=kingdom,
            )

    def get_board(self, settlement_name: str) -> Optional[QuestBoard]:
        """Get the quest board for a settlement."""
        return self.boards.get(settlement_name)

    def find_board_for_position(self, world, x: int, y: int
                                ) -> Optional[QuestBoard]:
        """Find which settlement's quest board the player is near.

        Checks if the player is inside a tavern building within any
        settlement that has a registered board.
        """
        # Check plan settlements (chunked worlds)
        if hasattr(world, 'plan'):
            for sp in world.plan.settlements:
                if abs(sp.x - x) > sp.radius + 20:
                    continue
                if abs(sp.y - y) > sp.radius + 20:
                    continue
                # Check if player is inside a tavern building
                for bld in sp.buildings:
                    bkind = bld.get('kind', '')
                    if bkind != 'tavern':
                        continue
                    bx, by = bld['x'], bld['y']
                    bw, bh = bld['w'], bld['h']
                    if bx <= x < bx + bw and by <= y < by + bh:
                        return self.boards.get(sp.name)

        # Check world structures (non-chunked)
        for s in getattr(world, 'structures', []):
            if s.kind == 'tavern':
                # Check if player is within the structure
                for bx, by, bw, bh in getattr(s, 'buildings', []):
                    if bx <= x < bx + bw and by <= y < by + bh:
                        # Find parent settlement name
                        return self.boards.get(s.name)

        return None

    def refresh_all(self, current_day: int, player_level: int = 1,
                    rank_system=None):
        """Refresh all boards that are due."""
        for board in self.boards.values():
            if board.needs_refresh(current_day):
                rank_idx = 0
                if rank_system and board.kingdom:
                    rank_idx = rank_system.get_rank_index(board.kingdom)
                board.refresh(current_day, player_level, rank_idx)

    def interact(self, settlement_name: str, quest_sys,
                 player_level: int = 1, current_day: int = 0,
                 rank_system=None) -> Optional[List[Dict]]:
        """Player interacts with a quest board. Returns listings or None."""
        board = self.boards.get(settlement_name)
        if not board:
            return None

        if board.needs_refresh(current_day):
            rank_idx = 0
            if rank_system and board.kingdom:
                rank_idx = rank_system.get_rank_index(board.kingdom)
            board.refresh(current_day, player_level, rank_idx)

        if not board.quests:
            return []

        return board.get_listings()

    def accept_quest(self, settlement_name: str, index: int,
                     quest_sys) -> Optional[Quest]:
        """Accept a quest from a board and add to quest system.

        Returns the accepted Quest or None.
        """
        board = self.boards.get(settlement_name)
        if not board:
            return None

        quest = board.take_quest(index)
        if not quest:
            return None

        if quest_sys.accept_quest(quest):
            return quest

        # Put it back if we couldn't accept
        board.quests.insert(index, quest)
        return None


