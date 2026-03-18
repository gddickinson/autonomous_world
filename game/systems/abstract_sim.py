"""
Abstract simulation layer for distant settlements.

Near the player: full NPC-level simulation (movement, AI, combat, dialog)
Far from player: settlement-level statistics (population, wealth, military)

This is how games like Crusader Kings and Dwarf Fortress handle large worlds.
Detailed where you look, statistical everywhere else.
"""

import random
import math
from typing import Dict, List, Optional
from game.settings import *


class SettlementAbstract:
    """Abstract representation of a distant settlement.
    Updated with simple equations instead of per-NPC simulation."""

    def __init__(self, name: str, kind: str, x: int, y: int):
        self.name = name
        self.kind = kind
        self.x = x
        self.y = y

        # Population
        self.population = 0
        self.max_population = {"hamlet": 10, "village": 25, "town": 60,
                               "city": 120, "castle": 40}.get(kind, 15)

        # Economy
        self.wealth = 0.0  # total gold
        self.food_supply = 50.0  # 0-100
        self.production_rate = 1.0  # goods produced per tick

        # Military
        self.military_strength = 0  # number of fighters
        self.fortification = {"hamlet": 0, "village": 1, "town": 3,
                              "city": 5, "castle": 8}.get(kind, 0)

        # Faction
        self.faction = ""
        self.ruler = ""

        # Morale
        self.morale = 50.0  # 0-100

        # NPCs that belong here (tracked for when player arrives)
        self.npc_names: List[str] = []

    def update_abstract(self, dt: float, day: int):
        """Simple statistical update for distant settlements."""
        time_scale = dt * 0.01  # slow down abstract sim

        # Food production based on settlement type
        food_prod = {"hamlet": 2, "village": 3, "town": 2, "city": 1, "castle": 1}.get(self.kind, 1)
        self.food_supply += food_prod * time_scale
        self.food_supply -= self.population * 0.1 * time_scale  # consumption
        self.food_supply = max(0, min(100, self.food_supply))

        # Wealth generation
        income = self.population * 0.05 * time_scale
        expenses = self.population * 0.03 * time_scale
        self.wealth += income - expenses
        self.wealth = max(0, self.wealth)

        # Population growth/decline
        if self.food_supply > 60 and self.population < self.max_population:
            if random.random() < 0.001 * time_scale:
                self.population += 1
        elif self.food_supply < 20 and self.population > 2:
            if random.random() < 0.002 * time_scale:
                self.population -= 1

        # Morale
        food_morale = (self.food_supply - 50) * 0.5
        wealth_morale = min(20, self.wealth * 0.1)
        self.morale = max(0, min(100, 50 + food_morale + wealth_morale))

        # Military strength (proportion of population that are fighters)
        self.military_strength = max(0, int(self.population * 0.2))


class AbstractSimulation:
    """Manages the abstraction layer - decides what gets full vs abstract sim."""

    DETAIL_RADIUS = 60     # tiles - full simulation radius around player
    ABSTRACT_RADIUS = 200  # tiles - abstract simulation beyond this

    def __init__(self):
        self.abstracts: Dict[str, SettlementAbstract] = {}
        self.active_zone_center = (0, 0)
        self.active_npcs: set = set()   # NPC names currently in detailed sim
        self.dormant_npcs: set = set()  # NPC names in abstract sim

    def initialize(self, structures: list, npcs: list):
        """Set up abstract representations for all settlements."""
        for s in structures:
            if s.kind in ("hamlet", "village", "town", "city", "castle"):
                abstract = SettlementAbstract(s.name, s.kind, s.x, s.y)
                self.abstracts[s.name] = abstract

        # Assign NPCs to settlements
        for npc in npcs:
            nearest = self._nearest_settlement(npc.x, npc.y)
            if nearest and nearest in self.abstracts:
                self.abstracts[nearest].npc_names.append(npc.name)
                self.abstracts[nearest].population += 1

    def update(self, dt: float, player_x: float, player_y: float,
               npcs: list, day: int, dormant_npc_names: list = None):
        """Update abstraction layer - detail near player, abstract far away.

        *dormant_npc_names*: optional list of names from WorldManager's dormant
        store so the report includes them.
        """
        self.active_zone_center = (player_x, player_y)

        # Categorize settlements (squared distance avoids sqrt)
        abstract_r_sq = self.ABSTRACT_RADIUS ** 2
        for name, abstract in self.abstracts.items():
            dx = abstract.x - player_x
            dy = abstract.y - player_y
            if dx * dx + dy * dy > abstract_r_sq:
                abstract.update_abstract(dt, day)

        # Decide which live NPCs should be active vs dormant (for detailed sim)
        new_active = set()
        new_dormant = set()
        detail_r_sq = self.DETAIL_RADIUS ** 2

        for npc in npcs:
            if not npc.alive:
                continue
            dx = npc.x - player_x
            dy = npc.y - player_y
            if dx * dx + dy * dy < detail_r_sq:
                new_active.add(npc.name)
            else:
                new_dormant.add(npc.name)

        # Include WorldManager-dormant NPCs in the dormant count
        if dormant_npc_names:
            new_dormant.update(dormant_npc_names)

        self.active_npcs = new_active
        self.dormant_npcs = new_dormant

    def should_simulate_npc(self, npc) -> bool:
        """Check if an NPC should get full simulation this frame."""
        return npc.name in self.active_npcs

    def get_settlement_abstract(self, name: str) -> Optional[SettlementAbstract]:
        return self.abstracts.get(name)

    def get_world_report(self) -> str:
        """Get a summary of all settlements for display."""
        lines = ["=== WORLD STATUS ==="]
        total_pop = 0
        for name, a in sorted(self.abstracts.items(), key=lambda x: -x[1].population):
            total_pop += a.population
            status = "active" if any(
                n in self.active_npcs for n in a.npc_names) else "abstract"
            lines.append(
                f"  {name} ({a.kind}): pop={a.population} "
                f"food={a.food_supply:.0f} wealth={a.wealth:.0f} "
                f"mil={a.military_strength} morale={a.morale:.0f} [{status}]")
        lines.append(f"  Total population: {total_pop}")
        lines.append(f"  Active NPCs: {len(self.active_npcs)}")
        lines.append(f"  Dormant NPCs: {len(self.dormant_npcs)}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Dormant NPC adventures
    # ------------------------------------------------------------------

    # Event tables: (event_type, weight)
    _DORMANT_EVENTS = [
        ("work", 35),
        ("fight", 15),
        ("travel", 10),
        ("social", 20),
        ("find_item", 10),
        ("marry", 2),
        ("train", 8),
        ("discovery", 5),
    ]

    # Pre-compute cumulative weights once
    _DORMANT_EVENT_TYPES = [e[0] for e in _DORMANT_EVENTS]
    _DORMANT_EVENT_WEIGHTS = [e[1] for e in _DORMANT_EVENTS]

    # --- Contextual data tables for richer dormant events ---

    _ENEMY_TYPES = [
        "a pack of wolves", "a bandit gang", "a wild boar",
        "a group of goblins", "a giant spider", "an angry bear",
        "a rogue mercenary", "a skeletal warrior", "a marauding orc",
        "a cave troll",
    ]

    _FIGHT_OUTCOMES = [
        ("won decisively", 0, 0.2),      # (text, hp_loss, mood_change)
        ("won but took wounds", 4, 0.1),
        ("barely survived", 7, -0.1),
        ("was forced to flee", 3, -0.2),
    ]

    _WORK_TEMPLATES = {
        "blacksmith": [
            "Forged {item} at the smithy",
            "Repaired armor for the town guard",
            "Hammered out horseshoes all day",
        ],
        "farmer": [
            "Tended the fields outside {settlement}",
            "Hauled grain to the storehouse",
            "Mended fences around the pasture",
        ],
        "merchant": [
            "Sold goods at the {settlement} market",
            "Negotiated a trade deal worth {gold} gold",
            "Inventoried the shop stock",
        ],
        "guard": [
            "Stood watch at the {settlement} gate",
            "Patrolled the settlement perimeter",
            "Escorted a caravan to the outskirts",
        ],
        "healer": [
            "Treated a sick villager in {settlement}",
            "Gathered medicinal herbs nearby",
            "Prepared healing poultices",
        ],
        "bard": [
            "Performed at the {settlement} tavern",
            "Composed a new ballad",
            "Entertained travelers for coin",
        ],
        "scholar": [
            "Studied old texts in {settlement}",
            "Copied manuscripts at the library",
            "Debated philosophy with a visiting sage",
        ],
        "default": [
            "Worked hard in {settlement}",
            "Earned a day's wages",
            "Helped with chores around {settlement}",
        ],
    }

    _SOCIAL_TEMPLATES_POSITIVE = [
        "Had a good conversation with {other_npc}",
        "Shared a meal with {other_npc}",
        "Helped {other_npc} with a task",
        "Laughed with {other_npc} at the tavern",
        "Played dice with {other_npc}",
        "Traded stories with {other_npc} by the fire",
    ]

    _SOCIAL_TEMPLATES_NEGATIVE = [
        "Had a heated argument with {other_npc}",
        "Was insulted by {other_npc}",
        "Had a falling out with {other_npc}",
        "Got into a shouting match with {other_npc}",
    ]

    _DISCOVERY_TEMPLATES = [
        "Discovered an old ruin near {settlement}",
        "Found ancient markings on a stone outside {settlement}",
        "Heard a legend about a hidden treasure beneath {settlement}",
        "Stumbled upon a forgotten shrine in the wilderness",
        "Found a mysterious map fragment while exploring",
        "Learned of an old prophecy from a traveling sage",
        "Discovered a hidden cave entrance near {settlement}",
        "Found a strange artifact buried in the {settlement} fields",
    ]

    _SPOUSE_NAMES_MALE = [
        "Aldric", "Beren", "Cedric", "Dorin", "Edric", "Falk",
        "Gareth", "Henrik", "Ismund", "Jorik", "Kael", "Leoric",
    ]
    _SPOUSE_NAMES_FEMALE = [
        "Alara", "Brynn", "Celeste", "Dara", "Elara", "Freya",
        "Gwen", "Hilda", "Iris", "Jora", "Kira", "Liana",
    ]

    _TRAINING_TEMPLATES = [
        "Practiced swordplay at the {settlement} training grounds",
        "Drilled combat forms until exhaustion",
        "Sparred with a fellow warrior in {settlement}",
        "Trained archery at the range",
        "Studied defensive techniques with a veteran",
        "Ran laps around the {settlement} walls for endurance",
    ]

    # --- Memory importance levels ---
    _IMPORTANCE = {
        "work": 1,
        "fight": 3,
        "travel": 2,
        "social": 2,
        "find_item": 2,
        "marry": 5,
        "train": 1,
        "discovery": 3,
    }

    # Categories that map to the live NPC memory "type" field
    _MEMORY_CATEGORY = {
        "work": "work",
        "fight": "conflict",
        "travel": "life",
        "social": "social",
        "find_item": "life",
        "marry": "family",
        "train": "work",
        "discovery": "life",
    }

    def simulate_dormant_npc(self, npc_data: dict, days_elapsed: int,
                             rng: random.Random) -> dict:
        """Apply statistical adventures to a dormant NPC.

        Called when a dormant NPC is about to become live again.
        *npc_data* is mutated in place and also returned.

        Generates rich, contextual memories in the standard format:
        {"text": str, "category": str, "importance": int, "day": int}
        """
        npc_name = npc_data.get("name", "Unknown")
        profession = npc_data.get("profession", "")
        char_class = npc_data.get("char_class", "")
        npc_x = npc_data.get("x", 0)
        npc_y = npc_data.get("y", 0)

        # Determine the NPC's home settlement
        home_settlement = self._nearest_settlement(npc_x, npc_y)
        if not home_settlement:
            home_settlement = "the settlement"

        # Collect all dormant NPC names for social events
        dormant_npc_pool = list(self.dormant_npcs - {npc_name})

        events_log: list = npc_data.setdefault("dormant_events", [])

        # Track the starting day for memory day stamps
        # Use a rough current_day estimate (we don't have time_sys here)
        base_day = npc_data.get("_last_sim_day", 0)

        for day_offset in range(min(days_elapsed, 30)):
            current_day = base_day + day_offset

            # 15% chance of *something* happening each day
            if rng.random() > 0.15:
                continue

            event = rng.choices(self._DORMANT_EVENT_TYPES,
                                weights=self._DORMANT_EVENT_WEIGHTS, k=1)[0]

            importance = self._IMPORTANCE.get(event, 2)
            category = self._MEMORY_CATEGORY.get(event, "life")
            text = ""

            if event == "work":
                earned = rng.randint(1, 5)
                npc_data["gold"] = npc_data.get("gold", 0) + earned

                # Pick profession-appropriate work description
                work_key = (profession or char_class or "default").lower()
                templates = self._WORK_TEMPLATES.get(
                    work_key, self._WORK_TEMPLATES["default"])
                template = rng.choice(templates)
                text = template.format(
                    settlement=home_settlement,
                    gold=earned,
                    item=rng.choice(["a sword", "a shield", "nails",
                                     "a plowshare", "an axe head"]),
                )
                events_log.append(text)

            elif event == "fight":
                enemy = rng.choice(self._ENEMY_TYPES)
                outcome_text, hp_loss, mood_change = rng.choice(
                    self._FIGHT_OUTCOMES)

                npc_data["hp"] = max(
                    1, npc_data.get("hp", 10) - hp_loss)
                npc_data["mood"] = max(
                    -1.0, min(1.0, npc_data.get("mood", 0) + mood_change))

                text = f"Fought {enemy} near {home_settlement} and {outcome_text}"
                if hp_loss > 0:
                    text += f" (lost {hp_loss} HP)"
                events_log.append(text)
                importance = 3 if hp_loss >= 5 else 2

            elif event == "travel":
                settlements = list(self.abstracts.values())
                if settlements:
                    dest = rng.choice(settlements)
                    npc_data["x"] = float(dest.x + rng.randint(-5, 5))
                    npc_data["y"] = float(dest.y + rng.randint(-5, 5))
                    npc_data["home_x"] = npc_data["x"]
                    npc_data["home_y"] = npc_data["y"]
                    text = (f"Traveled from {home_settlement} to {dest.name}")
                    # Update the home settlement for future events this batch
                    home_settlement = dest.name
                else:
                    text = "Went on a journey through the wilderness"
                events_log.append(text)

            elif event == "social":
                # Pick a specific NPC name if we have dormant NPCs
                if dormant_npc_pool:
                    other_npc = rng.choice(dormant_npc_pool)
                else:
                    other_npc = rng.choice([
                        "a traveler", "a merchant", "a scholar",
                        "a farmer", "a guard", "a bard",
                    ])

                if rng.random() < 0.7:
                    template = rng.choice(self._SOCIAL_TEMPLATES_POSITIVE)
                    text = template.format(other_npc=other_npc)
                    npc_data["mood"] = min(
                        1.0, npc_data.get("mood", 0) + 0.1)
                    # Track friendship
                    friends = npc_data.setdefault("friends", [])
                    if (other_npc not in friends
                            and other_npc not in (
                                "a traveler", "a merchant", "a scholar",
                                "a farmer", "a guard", "a bard")
                            and len(friends) < 10):
                        friends.append(other_npc)
                else:
                    template = rng.choice(self._SOCIAL_TEMPLATES_NEGATIVE)
                    text = template.format(other_npc=other_npc)
                    npc_data["mood"] = max(
                        -1.0, npc_data.get("mood", 0) - 0.1)
                events_log.append(text)

            elif event == "find_item":
                found_items = [
                    "Health Potion", "Bread", "Herbs", "Iron Ore",
                    "Gold Nugget", "Cooked Meat", "Old Coin",
                    "Silver Ring", "Mysterious Scroll",
                ]
                item_name = rng.choice(found_items)
                inv = npc_data.setdefault("inventory", [])
                for it in inv:
                    if it["name"] == item_name:
                        it["count"] = it.get("count", 1) + 1
                        break
                else:
                    inv.append({"name": item_name, "count": 1})

                text = (f"Found a {item_name} while "
                        f"{'exploring near ' + home_settlement if rng.random() < 0.6 else 'out on the road'}")
                events_log.append(text)

            elif event == "marry":
                if not npc_data.get("married"):
                    npc_data["married"] = True

                    # Pick a proper spouse name
                    if rng.random() < 0.5:
                        spouse_name = rng.choice(self._SPOUSE_NAMES_MALE)
                    else:
                        spouse_name = rng.choice(self._SPOUSE_NAMES_FEMALE)

                    # Avoid marrying yourself
                    if spouse_name == npc_name:
                        spouse_name = rng.choice(self._SPOUSE_NAMES_FEMALE)

                    npc_data["spouse"] = spouse_name
                    npc_data["mood"] = min(
                        1.0, npc_data.get("mood", 0) + 0.3)

                    text = f"Married {spouse_name} in {home_settlement}"
                    events_log.append(text)
                    importance = 5
                else:
                    # Already married -- skip, try a social event instead
                    text = f"Celebrated an anniversary with {npc_data.get('spouse', 'spouse')}"
                    events_log.append(text)
                    importance = 2
                    category = "family"

            elif event == "train":
                npc_data["hp"] = min(
                    npc_data.get("max_hp", 20),
                    npc_data.get("hp", 10) + rng.randint(1, 3),
                )
                template = rng.choice(self._TRAINING_TEMPLATES)
                text = template.format(settlement=home_settlement)
                events_log.append(text)

            elif event == "discovery":
                template = rng.choice(self._DISCOVERY_TEMPLATES)
                text = template.format(settlement=home_settlement)
                events_log.append(text)
                importance = 3

            # Nothing generated (e.g. marry skipped) -- guard
            if not text:
                continue

        # Store the last simulated day for future calls
        npc_data["_last_sim_day"] = base_day + min(days_elapsed, 30)

        # --- Inject dormant events into NPC memories in standard format ---
        memories = npc_data.setdefault("memories", [])
        start_day = base_day
        for idx, evt_text in enumerate(events_log):
            # Estimate which day this event occurred on
            mem_day = start_day + idx
            memories.append({
                "text": evt_text,
                "type": self._guess_category(evt_text),
                "category": self._guess_category(evt_text),
                "importance": self._guess_importance(evt_text),
                "day": mem_day,
                "time": 0.0,  # compat with live NPC time field
            })

        # Compact memories if they've grown too large
        compact_dormant_memories(npc_data, max_memories=NPC_MAX_MEMORIES)

        return npc_data

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _nearest_settlement(self, x: float, y: float) -> Optional[str]:
        best = None
        best_dist = float('inf')
        for name, a in self.abstracts.items():
            d = math.sqrt((x - a.x)**2 + (y - a.y)**2)
            if d < best_dist and d < 50:
                best_dist = d
                best = name
        return best

    @staticmethod
    def _guess_category(text: str) -> str:
        """Infer memory category from event text for legacy events."""
        tl = text.lower()
        if any(w in tl for w in ("fought", "fight", "attack", "wolf",
                                  "bandit", "goblin", "spider", "fled")):
            return "conflict"
        if any(w in tl for w in ("married", "spouse", "anniversary", "child",
                                  "born")):
            return "family"
        if any(w in tl for w in ("friend", "conversation", "shared",
                                  "laughed", "argument", "insult",
                                  "shouting")):
            return "social"
        if any(w in tl for w in ("traveled", "journey", "road")):
            return "life"
        if any(w in tl for w in ("discovered", "found", "legend",
                                  "prophecy", "artifact", "ruin",
                                  "shrine", "cave", "map")):
            return "life"
        if any(w in tl for w in ("forge", "smithy", "field", "sold",
                                  "guard", "watch", "work", "earned",
                                  "trained", "practiced", "sparred",
                                  "drilled")):
            return "work"
        return "life"

    @staticmethod
    def _guess_importance(text: str) -> int:
        """Infer memory importance from event text."""
        tl = text.lower()
        if any(w in tl for w in ("married", "died", "killed", "born")):
            return 5
        if any(w in tl for w in ("fought", "discovered", "traveled",
                                  "artifact", "prophecy")):
            return 3
        if any(w in tl for w in ("friend", "argument")):
            return 2
        return 1


# ======================================================================
# Memory Decay & Compaction for Dormant NPCs  (Part 2B / 2C)
# ======================================================================

# Categories whose memories should never be dropped during compaction
_PROTECTED_CATEGORIES = {"family", "conflict"}
_PROTECTED_KEYWORDS = {"married", "died", "killed", "born", "battle",
                        "spouse", "child"}


def _is_important_memory(mem: dict) -> bool:
    """Return True if this memory should be preserved during compaction."""
    if mem.get("importance", 0) >= 4:
        return True
    cat = mem.get("category", mem.get("type", ""))
    if cat in _PROTECTED_CATEGORIES:
        return True
    text = mem.get("text", "").lower()
    if any(kw in text for kw in _PROTECTED_KEYWORDS):
        return True
    return False


def _memories_are_similar(a: dict, b: dict) -> bool:
    """Two memories are similar if same category and within 3 days."""
    cat_a = a.get("category", a.get("type", ""))
    cat_b = b.get("category", b.get("type", ""))
    if cat_a != cat_b:
        return False
    day_a = a.get("day", 0)
    day_b = b.get("day", 0)
    return abs(day_a - day_b) <= 3


_SUMMARY_TEMPLATES = {
    "work": "Spent several days working in {settlement}",
    "social": "Had several good conversations this week",
    "conflict": "Was involved in multiple skirmishes recently",
    "life": "Had an eventful few days",
    "family": "Spent time with family",
}


def _fade_memory(mem: dict) -> dict:
    """Make an old memory vaguer (decay details)."""
    text = mem.get("text", "")
    # Strip specific numbers
    import re
    text = re.sub(r'\d+ gold', 'some gold', text)
    text = re.sub(r'\d+ HP', 'some health', text)
    text = re.sub(r'lost \d+', 'lost some', text)
    mem["text"] = text
    # Reduce importance slightly (but never below 1)
    mem["importance"] = max(1, mem.get("importance", 1) - 1)
    return mem


def compact_dormant_memories(npc_data: dict,
                             max_memories: int = NPC_MAX_MEMORIES):
    """Compact and decay dormant NPC memories.

    1. Fade old memories (details become vaguer).
    2. Group similar memories (same category within 3 days) into summaries.
    3. Drop oldest low-importance memories beyond the cap.
    4. Preserve important memories (marriage, death, major battles).

    The result is stored back in npc_data["memories"].
    """
    memories: list = npc_data.get("memories", [])
    if len(memories) <= max_memories:
        return  # nothing to do

    # --- Step 1: Fade old memories ---
    # Memories older than 20 days from the most recent get faded
    if memories:
        latest_day = max(m.get("day", m.get("time", 0)) for m in memories)
        for mem in memories:
            mem_day = mem.get("day", mem.get("time", 0))
            age = latest_day - mem_day
            if age > 20 and not _is_important_memory(mem):
                _fade_memory(mem)

    # --- Step 2: Group similar memories ---
    # Sort by day then category for grouping
    memories.sort(key=lambda m: (m.get("day", m.get("time", 0)),
                                 m.get("category", m.get("type", ""))))

    compacted: List[dict] = []
    i = 0
    while i < len(memories):
        mem = memories[i]

        # Don't compact important memories
        if _is_important_memory(mem):
            compacted.append(mem)
            i += 1
            continue

        # Collect a group of similar consecutive memories
        group = [mem]
        j = i + 1
        while j < len(memories) and len(group) < 5:
            candidate = memories[j]
            if (_memories_are_similar(mem, candidate)
                    and not _is_important_memory(candidate)):
                group.append(candidate)
                j += 1
            else:
                break

        if len(group) >= 3:
            # Merge into a summary
            cat = mem.get("category", mem.get("type", "life"))
            summary_text = _SUMMARY_TEMPLATES.get(cat, "Had an eventful few days")

            # Try to extract settlement name from one of the memories
            for g in group:
                gt = g.get("text", "")
                # Find settlement reference: "in <Name>" or "to <Name>"
                for prefix in (" in ", " to ", " near "):
                    idx = gt.find(prefix)
                    if idx >= 0:
                        settlement_name = gt[idx + len(prefix):].split(",")[0].split(".")[0].strip()
                        if settlement_name and settlement_name[0].isupper():
                            summary_text = summary_text.format(
                                settlement=settlement_name)
                            break
                else:
                    continue
                break
            else:
                # No settlement found -- remove placeholder
                summary_text = summary_text.replace(" in {settlement}", "")
                summary_text = summary_text.replace("{settlement}", "nearby")

            avg_day = sum(g.get("day", 0) for g in group) // len(group)
            max_importance = max(g.get("importance", 1) for g in group)
            compacted.append({
                "text": summary_text,
                "type": cat,
                "category": cat,
                "importance": min(max_importance, 3),
                "day": avg_day,
                "time": 0.0,
            })
            i = j
        else:
            # Not enough to group -- keep individually
            for g in group:
                compacted.append(g)
            i = j

    memories = compacted

    # --- Step 3: Drop oldest low-importance memories beyond the cap ---
    if len(memories) > max_memories:
        # Separate important from non-important
        important = [m for m in memories if _is_important_memory(m)]
        normal = [m for m in memories if not _is_important_memory(m)]

        # Sort normal by (importance ASC, day ASC) so least important / oldest first
        normal.sort(key=lambda m: (m.get("importance", 0),
                                   m.get("day", m.get("time", 0))))

        # Keep as many normal memories as we have room for
        room = max_memories - len(important)
        if room > 0:
            normal = normal[-room:]  # keep the most recent/important
        else:
            normal = []

        memories = important + normal

    # Final sort by day for clean ordering
    memories.sort(key=lambda m: m.get("day", m.get("time", 0)))

    npc_data["memories"] = memories
