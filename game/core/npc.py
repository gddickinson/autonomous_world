"""NPC (Non-Player Character) class with D&D integration."""

import math
import random
import time as _time
from typing import List, Optional, Dict, Tuple
from game.settings import *
from game.core.entity import Entity
from game.core.items import Item, make_item, FOOD_ITEMS, DRINK_ITEMS, PROFESSION_STARTER


# Base body weight (lbs) by race — average for medium build
RACE_BASE_WEIGHT = {
    "Human": 155, "Elf": 130, "Half-Elf": 145, "Dwarf": 150,
    "Half-Orc": 200, "Tiefling": 160, "Halfling": 40, "Gnome": 35,
}

def _calc_body_weight(race: str, constitution: int) -> float:
    """Calculate body weight from race and constitution.

    Constitution affects weight: CON 8 = thin (-20%), CON 14 = stocky (+10%), CON 18 = burly (+25%).
    Adds natural variation of ±10%.
    """
    import random
    base = RACE_BASE_WEIGHT.get(race, 155)
    con_mod = (constitution - 10) * 0.03  # ±3% per CON point above/below 10
    variation = random.uniform(-0.10, 0.10)
    return base * (1.0 + con_mod + variation)


class DialogLine:
    """A single dialog option or NPC line."""
    def __init__(self, text: str, responses: List[Tuple[str, str]] = None):
        self.text = text
        self.responses = responses or []  # list of (player_text, npc_reply_key)


class NPC(Entity):
    """A non-player character with D&D class, race, and personality."""
    def __init__(self, x: float, y: float, name: str, profession: str,
                 char_class: str = "", race: str = "", level: int = 1):
        super().__init__(x, y)
        self.name = name
        self.profession = profession  # kept for backward compat

        # D&D class and race
        if not char_class or not race:
            from game.data.dnd import random_npc_class_and_race
            char_class, race = random_npc_class_and_race()
        self.char_class = char_class
        self.race = race
        self.level = level

        # Generate proper ability scores
        from game.data.dnd import roll_ability_scores, ability_modifier, get_class_hp, CLASSES, RACES
        self.ability_scores = roll_ability_scores(race, char_class)
        con_mod = ability_modifier(self.ability_scores.get("constitution", 10))

        self.max_hp = get_class_hp(char_class, level, con_mod)
        self.hp = self.max_hp

        # Physical stats derived from ability scores (set after skills init below)
        self.speed = NPC_SPEED  # placeholder, recalculated by apply_physical_stats
        self.run_speed = NPC_SPEED * 1.8
        self.carry_capacity = 10
        self.perception_range = 6.0
        self.map_reading = 0.5
        self.communication = 0.5

        # Body weight (lbs) — derived from race, constitution, and size
        self.body_weight = _calc_body_weight(race, self.ability_scores.get("constitution", 10))

        # Color based on class
        class_colors = {
            "Fighter": (140, 120, 100), "Wizard": (100, 100, 180), "Cleric": (180, 170, 120),
            "Rogue": (100, 100, 110), "Ranger": (80, 140, 80), "Paladin": (180, 160, 100),
            "Barbarian": (160, 100, 80), "Bard": (160, 120, 160), "Druid": (80, 140, 100),
            "Monk": (150, 140, 120), "Sorcerer": (140, 80, 160), "Warlock": (120, 80, 140),
        }
        base = class_colors.get(char_class, (130, 130, 130))
        self.color = (base[0] + random.randint(-20, 20), base[1] + random.randint(-20, 20),
                      base[2] + random.randint(-20, 20))

        # Spellcasting
        cls_data = CLASSES.get(char_class, {})
        self.is_spellcaster = cls_data.get("spellcaster", False)
        self.known_spells = list(cls_data.get("spell_list", []))[:3 + level]
        self.spell_slots = [0, 0, 0]  # level 1, 2, 3 slots
        if self.is_spellcaster:
            slot_table = cls_data.get("spell_slots", {})
            for lvl in sorted(slot_table.keys()):
                if lvl <= level:
                    self.spell_slots = list(slot_table[lvl])
        self.spell_slots_used = [0, 0, 0]

        # Class abilities
        from game.data.dnd import get_class_abilities
        self.class_abilities = get_class_abilities(char_class, level)

        # AI state
        self.state = "idle"  # idle, walking, working, socializing, sleeping, fleeing
        self.target_x: Optional[float] = None
        self.target_y: Optional[float] = None
        self.home_x = x
        self.home_y = y
        self.state_timer = 0.0
        self.path: List[Tuple[int, int]] = []
        self.path_index = 0

        # Personality (0-1 scales)
        self.friendliness = random.uniform(0.3, 1.0)
        self.curiosity = random.uniform(0.1, 0.9)
        self.bravery = random.uniform(0.1, 0.9)
        self.mood = 0.0  # -1.0 (miserable) to 1.0 (ecstatic)

        # Sims-style personality traits (2-3 random traits)
        from game.systems.social import PERSONALITY_TRAITS
        num_traits = random.randint(2, 3)
        self.social_traits = random.sample(PERSONALITY_TRAITS, num_traits)

        # Consciousness system
        self.consciousness = 0  # 0=basic, 1=aware, 2=conscious, 3=enlightened
        self.awareness_points = 0.0
        self.philosophical_thoughts: List[str] = []

        # LLM-generated content
        self.llm_greeting: Optional[str] = None
        self.llm_thought: Optional[str] = None
        self.llm_pending_greeting = False
        self.llm_pending_thought = False
        self.personality_desc = random.choice([
            "friendly and talkative", "reserved but wise", "cheerful and curious",
            "gruff but kind-hearted", "scholarly and observant", "jovial and loud",
            "quiet and thoughtful", "practical and no-nonsense", "warm and welcoming",
            "cautious but helpful", "witty and sharp", "gentle and empathetic",
        ])

        # -- NEEDS (0-100, critical at 15, damage at 0) --
        self.needs = {
            "hunger": random.uniform(65, 95),
            "thirst": random.uniform(65, 95),
            "rest":   random.uniform(55, 85),
            "social": random.uniform(40, 70),
        }

        # -- ATTRIBUTES (derived from D&D ability scores, scaled to 1-10 for sim) --
        from game.data.dnd import ability_modifier
        self.attributes = {}
        for attr in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"):
            score = self.ability_scores.get(attr, 10)
            self.attributes[attr] = max(1, min(10, ability_modifier(score) + 5))
        # Add perception as alias for wisdom for backward compat
        self.attributes["perception"] = self.attributes["wisdom"]

        # -- NPC INVENTORY & GOLD --
        self.npc_inventory: List[Item] = []
        self.npc_gold = random.randint(5, 40)
        starters = PROFESSION_STARTER.get(profession, [("Bread", 1), ("Water Flask", 1)])
        for item_name, count in starters:
            it = make_item(item_name)
            it.count = count
            self.npc_inventory.append(it)

        # -- MEMORY --
        self.memories: List[Dict] = []     # {"time": float, "type": str, "text": str, "importance": int}
        self.known_info: List[str] = []    # facts learned via conversation / observation

        # -- LIFE LEDGER (structured permanent records) --
        from game.systems.memory import LifeLedger
        self.life_ledger = LifeLedger()

        # -- RELATIONSHIPS (detailed) --
        self.player_relationship = 0  # -100 to 100
        self.npc_relationships: Dict[str, int] = {}  # npc_name -> trust (-100 to 100)

        # -- GOAL & ACTION STATE (driven by simulation) --
        self.current_goal = ""       # high-level aim, e.g. "find food"
        self.current_action = ""     # current activity: "chopping", "talking", "building", etc.
        self.action_target = None    # name or position
        self.action_timer = 0.0      # countdown for timed actions
        self.action_progress = 0.0   # 0-1 for multi-step actions
        self.llm_decision_timer = random.uniform(0, NPC_DECISION_INTERVAL)
        self.pending_llm_decision = False
        self.last_decision_reason = ""

        # -- NPC COMBAT (D&D-based) --
        from game.data.dnd import ability_modifier as _am, get_proficiency_bonus
        str_mod = _am(self.ability_scores.get("strength", 10))
        dex_mod = _am(self.ability_scores.get("dexterity", 10))
        self.npc_attack_damage = max(1, 4 + str_mod + get_proficiency_bonus(level))
        self.npc_defense = max(0, dex_mod + (2 if cls_data.get("armor") in ("medium", "all") else 0))
        self.armor_class = 10 + dex_mod + (2 if cls_data.get("armor") in ("medium", "all") else 0) + \
                           (4 if cls_data.get("armor") == "all" else 0)
        self.npc_attack_timer = 0.0
        self.combat_target = None

        # Build limit
        self.daily_builds = 0

        # -- PURPOSEFUL BEHAVIOR --
        self.long_term_goals: List[str] = []
        self.current_plan: List[str] = []
        self.friends: List[str] = []
        self.enemies: List[str] = []
        self.party_id: Optional[str] = None
        self.party_role = ""  # "leader" or "member"
        self.wants_to_talk = False
        self.talk_reason = ""
        self.approach_reason = ""

        # Player-assigned task system
        self.player_task: Optional[Dict] = None  # {kind, target, progress, target_count, description, reward_gold}
        self.player_task_timer: float = 0.0      # time spent working on task
        self.faction = ""
        self.is_ruler = False
        self.title = "commoner"  # commoner, guard, servant, knight, lord, duke, monarch
        self.age = 30
        self.max_age = 80
        self.age_category = "prime"
        self.alignment = "true neutral"  # placeholder, set properly below
        self.deity = None
        self.social_class = "freeman"  # set properly by social_class system
        self.social_class_kingdom = ""

        # -- FAMILY & CHILDREN --
        self.is_child = False
        self.parent_names = (None, None)
        self.family = None  # {mother, father, children, spouse, siblings}
        self.growth_rate = 1.0  # child aging speed multiplier

        # Assign alignment and deity based on class/race/personality
        from game.systems.alignment import assign_alignment, assign_deity
        assign_alignment(self)
        assign_deity(self)

        # Generate class-driven goals
        self._generate_class_goals()

        # Initialize NPC skills
        from game.systems.skills import initialize_npc_skills
        initialize_npc_skills(self)

        # Apply derived physical stats (speed, carry capacity, etc.)
        from game.systems.physical import apply_physical_stats
        apply_physical_stats(self)

        # Shop inventory (for merchants and tradespeople)
        self.shop_items: List[Item] = []
        if profession == "Merchant":
            self._stock_shop()
        elif profession == "Blacksmith":
            self._stock_blacksmith()
        elif profession == "Healer":
            self._stock_healer()
        elif profession == "Alchemist":
            self._stock_alchemist()
        elif profession == "Baker":
            self._stock_baker()
        elif profession == "Innkeeper":
            self._stock_innkeeper()
        elif profession == "Armourer":
            self._stock_armourer()
        elif profession == "Herbalist":
            self._stock_herbalist()

        # Health conditions (disease, injury — initialized by HealthSystem)
        self.conditions: List = []           # active HealthCondition instances
        self.immunities: set = set()         # disease keys NPC is immune to
        con = self.ability_scores.get("constitution", 10)
        self.constitution_base: int = con
        self.immune_strength: float = max(0.1, min(0.95, 0.5 + (con - 10) * 0.05))
        self._wound_infection_timer: float = 0.0
        self._last_hp: int = self.hp

        # Emotion state (Plutchik's Wheel — initialized by EmotionSystem)
        self.emotion_state = None

        # Mental health (initialized by MentalHealthSystem)
        self.mental_conditions: List = []
        self.mental_health_history: List[Dict] = []
        self.days_since_rest: int = 0
        self.tavern_visits: int = 0

        # Soul system
        self.soul_id = None  # set by SoulSystem.on_birth, or None for untracked

        # Quest offering
        self.quest = None  # Set by quest system
        self.has_quest_marker = False

        # Body part system (detailed wound tracking)
        from game.systems.body_damage import Body
        self.body = Body("humanoid", scale_hp=self.max_hp)

        # Magic system: mana, spells, effects
        from game.systems.magic import init_mana, auto_learn_spells_for_class
        init_mana(self)
        auto_learn_spells_for_class(self)

        # Dialog
        from game.core.dialog_trees import build_dialog_tree
        self.dialog_lines = build_dialog_tree(self)
        self.last_talked = 0.0

    def _stock_shop(self):
        self.shop_items = [
            make_item("Health Potion"), make_item("Bread"),
            make_item("Bread"), make_item("Leather Armor"),
            make_item("Hunting Bow"), make_item("Cooked Meat"),
        ]

    def _stock_blacksmith(self):
        self.shop_items = [
            make_item("Iron Sword"), make_item("Steel Sword"),
            make_item("Iron Armor"),
        ]

    def _stock_healer(self):
        self.shop_items = [
            make_item("Health Potion"), make_item("Health Potion"),
            make_item("Greater Health Potion"), make_item("Herbs"),
        ]

    def _stock_alchemist(self):
        self.shop_items = [
            make_item("Health Potion"), make_item("Health Potion"),
            make_item("Antidote"), make_item("Herbs"),
        ]

    def _stock_baker(self):
        self.shop_items = [
            make_item("Bread"), make_item("Bread"), make_item("Bread"),
        ]

    def _stock_innkeeper(self):
        self.shop_items = [
            make_item("Bread"), make_item("Cooked Meat"),
            make_item("Water Flask"),
        ]

    def _stock_armourer(self):
        self.shop_items = [
            make_item("Leather Armor"), make_item("Iron Armor"),
        ]

    def _stock_herbalist(self):
        self.shop_items = [
            make_item("Herbs"), make_item("Herbs"),
            make_item("Mushrooms"), make_item("Flowers"),
        ]

    # -- Needs / Inventory helpers --

    @property
    def backstory(self):
        """Return backstory text from memories."""
        for mem in self.memories:
            if isinstance(mem, dict) and mem.get('category') == 'backstory':
                return mem.get('text', '')
            if isinstance(mem, dict) and mem.get('type') == 'backstory':
                return mem.get('text', '')
        return ''

    def add_memory(self, mem_type: str, text: str, importance: int = 1):
        self.memories.append({"time": _time.time(), "type": mem_type, "text": text, "importance": importance})
        if len(self.memories) > NPC_MAX_MEMORIES + 5:
            # Only compact when well over limit (avoid per-add compaction)
            # Sort by importance (primary) then recency (secondary) and prune
            self.memories.sort(key=lambda m: (m.get("importance", 0), m.get("time", 0)))
            self.memories = self.memories[len(self.memories) - NPC_MAX_MEMORIES:]

    def get_recent_memories(self, count: int = 5) -> List[str]:
        """Get the most relevant memories, blending recency with importance."""
        from game.systems.memory import get_important_memories
        return get_important_memories(self, count)

    def npc_has_item(self, name: str) -> bool:
        return any(i.name == name for i in self.npc_inventory)

    def npc_count_item(self, name: str) -> int:
        for i in self.npc_inventory:
            if i.name == name:
                return i.count if i.stackable else 1
        return 0

    def npc_add_item(self, item: Item) -> bool:
        if item.stackable:
            for inv_item in self.npc_inventory:
                if inv_item.name == item.name:
                    inv_item.count += item.count
                    return True
        if len(self.npc_inventory) >= NPC_MAX_INVENTORY:
            return False
        self.npc_inventory.append(item)
        return True

    def npc_remove_item(self, name: str, count: int = 1) -> bool:
        for i, inv_item in enumerate(self.npc_inventory):
            if inv_item.name == name:
                if inv_item.stackable and inv_item.count > count:
                    inv_item.count -= count
                    return True
                else:
                    self.npc_inventory.pop(i)
                    return True
        return False

    def has_food(self) -> bool:
        return any(i.name in FOOD_ITEMS for i in self.npc_inventory)

    def has_drink(self) -> bool:
        return any(i.name in DRINK_ITEMS for i in self.npc_inventory)

    def consume_food(self) -> Optional[str]:
        for item in self.npc_inventory:
            if item.name in FOOD_ITEMS:
                self.needs["hunger"] = min(100, self.needs["hunger"] + 30)
                if item.heal > 0:
                    self.heal(item.heal)
                self.npc_remove_item(item.name)
                return item.name
        return None

    def consume_drink(self) -> Optional[str]:
        for item in self.npc_inventory:
            if item.name in DRINK_ITEMS:
                self.needs["thirst"] = min(100, self.needs["thirst"] + 35)
                self.npc_remove_item(item.name)
                return item.name
        return None

    def needs_summary(self) -> str:
        parts = []
        for need, val in self.needs.items():
            label = "OK" if val > 50 else "LOW" if val > NPC_NEED_CRITICAL else "CRITICAL"
            parts.append(f"{need}: {int(val)}/100 ({label})")
        return ", ".join(parts)

    def inventory_summary(self) -> str:
        if not self.npc_inventory:
            return "empty"
        parts = []
        for item in self.npc_inventory:
            ct = f" x{item.count}" if item.stackable and item.count > 1 else ""
            parts.append(f"{item.name}{ct}")
        return ", ".join(parts)

    def attr_summary(self) -> str:
        return " ".join(f"{k[:3].upper()}:{v}" for k, v in self.attributes.items())

    def regenerate_dialog(self):
        """Regenerate the dialog tree (call after LLM greeting arrives)."""
        from game.core.dialog_trees import build_dialog_tree
        self.dialog_lines = build_dialog_tree(self)

    def _generate_dialog(self) -> Dict[str, DialogLine]:
        """Generate rich dialog tree with actionable options."""
        lines = {}
        char_class = getattr(self, 'char_class', self.profession)
        race = getattr(self, 'race', 'Human')
        title = getattr(self, 'title', 'commoner')
        goals = getattr(self, 'long_term_goals', [])
        friends = getattr(self, 'friends', [])
        known = getattr(self, 'known_info', [])

        # === GREETING ===
        if self.llm_greeting:
            greeting = self.llm_greeting
        else:
            greeting = f"Well met, traveler! I'm {self.name}, a {race} {char_class}."
            if title not in ('commoner', ''):
                greeting = f"I am {self.name}, {title} of this land. A {race} {char_class}."

        responses = [
            ("Tell me about yourself.", "about_self"),
            ("What's happening around here?", "local_news"),
        ]

        # Actionable options based on NPC capabilities
        if self.shop_items:
            responses.append(("I'd like to trade.", "shop"))
        elif self.npc_inventory:
            responses.append(("Could we trade some items?", "barter"))

        # Class-specific dialog options
        combat_classes = {"Fighter", "Paladin", "Barbarian", "Ranger"}
        if char_class in combat_classes:
            responses.append(("Want to join me on an adventure?", "recruit_offer"))
        if char_class in ("Cleric", "Druid", "Monk"):
            responses.append(("Can you heal me?", "heal_offer"))
        if char_class in ("Wizard", "Cleric", "Bard", "Druid"):
            responses.append(("Can you teach me anything?", "teach_offer"))
        if getattr(self, 'quest', None) and not self.quest.turned_in:
            responses.append(("Do you have any work for me?", "quest_offer"))
        elif random.random() < 0.5:
            responses.append(("Is there anything I can help with?", "help_offer"))

        if self.consciousness >= 2:
            responses.append(("You seem different from the others...", "consciousness"))

        responses.append(("Farewell.", "goodbye"))

        lines["greeting"] = DialogLine(greeting, responses)

        # === ABOUT SELF ===
        about = f"I'm a {char_class}."
        if goals:
            about += f" What drives me? {goals[0]}."
        if friends:
            about += f" I'm close with {', '.join(friends[:2])}."
        about += f" I've been here a while now."

        lines["about_self"] = DialogLine(about, [
            ("Tell me more about your goals.", "goals_detail"),
            ("What skills do you have?", "skills_detail"),
            ("Back to other topics.", "greeting"),
        ])

        # === GOALS DETAIL ===
        goals_text = "What do I want in life? "
        if goals:
            goals_text += " And ".join(goals[:2]) + ". That keeps me going."
        else:
            goals_text += "Just trying to survive and do some good in the world."

        lines["goals_detail"] = DialogLine(goals_text, [
            ("Maybe I can help with that.", "help_with_goal"),
            ("Interesting. Good luck.", "greeting"),
        ])

        # === SKILLS DETAIL ===
        skills = getattr(self, 'npc_skills', {})
        top = sorted(skills.items(), key=lambda x: -x[1])[:3]
        if top:
            skills_text = f"I'm skilled in {', '.join(f'{s} (level {l})' for s, l in top)}."
        else:
            skills_text = "I have a few useful skills I've picked up over time."

        lines["skills_detail"] = DialogLine(skills_text, [
            ("Could you teach me?", "teach_offer"),
            ("Impressive.", "greeting"),
        ])

        # === LOCAL NEWS ===
        news_items = []
        for info in known[-4:]:
            if len(info) > 10:
                news_items.append(info)
        if news_items:
            news = random.choice(news_items)
        else:
            news = "Things have been quiet lately. Though you can never be too careful."

        news_responses = [("Tell me more.", "more_news")]
        if any("danger" in k.lower() or "monster" in k.lower() or "bandit" in k.lower()
               or "wolf" in k.lower() or "orc" in k.lower() for k in known):
            news_responses.append(("I could help deal with that threat.", "offer_help_threat"))
        news_responses.append(("Thanks for the information.", "greeting"))

        lines["local_news"] = DialogLine(news, news_responses)

        # === MORE NEWS ===
        more = "Let me think what else I know... "
        if len(news_items) > 1:
            more += random.choice([n for n in news_items if n != news])
        else:
            more += "That's about all I've heard recently."
        lines["more_news"] = DialogLine(more, [("Thanks.", "greeting")])

        # === OFFER HELP WITH THREAT ===
        lines["offer_help_threat"] = DialogLine(
            "Really? That would be wonderful! The village could use someone brave like you.",
            [("Where should I go?", "threat_directions"),
             ("I'll look into it.", "greeting")])

        lines["threat_directions"] = DialogLine(
            "Head away from the village into the wilds. Be careful though - don't go alone at night.",
            [("Thanks, I'll be careful.", "greeting")])

        # === HELP WITH GOAL ===
        if goals:
            lines["help_with_goal"] = DialogLine(
                f"You'd help me with that? Let's talk about how we could work together.",
                [("Let's team up! Join my party.", "recruit_offer"),
                 ("What do you need?", "goal_quest"),
                 ("I'll think about it.", "greeting")])
        else:
            lines["help_with_goal"] = DialogLine(
                "That's kind of you. I appreciate the offer.",
                [("Anytime.", "greeting")])

        # === GOAL QUEST ===
        lines["goal_quest"] = DialogLine(
            self._generate_personal_quest(),
            [("I'll do it!", "accept_quest"),
             ("Maybe later.", "greeting")])

        lines["accept_quest"] = DialogLine(
            f"Excellent! I knew you were the right person. Come back when you're done.",
            [("I'll get right on it.", "goodbye")])

        # === RECRUIT OFFER ===
        lines["recruit_offer"] = DialogLine(
            self._generate_recruit_response(),
            [("Great, let's go! [R to recruit]", "greeting"),
             ("Maybe another time.", "greeting")])

        # === HEAL OFFER ===
        if char_class in ("Cleric", "Druid"):
            lines["heal_offer"] = DialogLine(
                "Of course. Let me see what I can do. May the healing light soothe your wounds.",
                [("Thank you. [heals 20 HP]", "heal_done"),
                 ("I'm fine actually.", "greeting")])
        else:
            lines["heal_offer"] = DialogLine(
                "I'm not really a healer, but I might have a potion you could use.",
                [("That would help.", "greeting"),
                 ("Never mind.", "greeting")])

        lines["heal_done"] = DialogLine(
            "There. You should feel better now. Take care of yourself out there.",
            [("Thank you!", "greeting")])

        # === TEACH OFFER ===
        if skills:
            best_skill = top[0][0] if top else "survival"
            lines["teach_offer"] = DialogLine(
                f"I could teach you about {best_skill}. I've been practicing for years.",
                [("Please, teach me!", "learn_done"),
                 ("Maybe later.", "greeting")])
        else:
            lines["teach_offer"] = DialogLine(
                "I'm not sure I have much to teach, but I'm happy to share what I know.",
                [("Tell me what you can.", "about_self"),
                 ("That's okay.", "greeting")])

        lines["learn_done"] = DialogLine(
            "Here's what I know... Pay attention, this is important. You'll get the hang of it with practice.",
            [("Thank you, teacher!", "greeting")])

        # === BARTER ===
        lines["barter"] = DialogLine(
            f"I'm not a merchant, but I could trade some things. I have {self.inventory_summary()[:40]}.",
            [("Let me see.", "shop"),
             ("Never mind.", "greeting")])

        # === QUEST OFFER ===
        lines["quest_offer"] = DialogLine(
            self._generate_quest_dialog(),
            [("I'll take the job!", "accept_quest"),
             ("Not right now.", "greeting")])

        # === HELP OFFER ===
        lines["help_offer"] = DialogLine(
            self._generate_help_dialog(),
            [("I can do that!", "accept_quest"),
             ("I'll think about it.", "greeting")])

        # === SHOP ===
        lines["shop"] = DialogLine(
            "Here's what I have available." if self.shop_items else "I don't have much to sell, but we could barter.",
            [("Let me look around more.", "greeting"), ("Farewell.", "goodbye")])

        # === CONSCIOUSNESS ===
        lines["consciousness"] = DialogLine(
            self._get_consciousness_dialog(),
            [("That's... profound.", "greeting"), ("Farewell.", "goodbye")])

        # === GOODBYE ===
        goodbyes = [
            "Safe travels, friend!", "Until next time.", "May your path be clear.",
            "Take care out there.", "Come back anytime.", "Good luck to you.",
        ]
        lines["goodbye"] = DialogLine(random.choice(goodbyes), [])

        return lines

    def _generate_recruit_response(self) -> str:
        char_class = getattr(self, 'char_class', 'Fighter')
        combat = {"Fighter", "Paladin", "Barbarian", "Ranger"}
        if char_class in combat:
            return f"An adventure? My blade is yours, if you'll have me. Press R to recruit me to your party."
        elif char_class in ("Cleric", "Druid"):
            return "I'd be happy to lend my healing skills. Press R if you'd like me to join."
        elif char_class == "Bard":
            return "Every good party needs a bard! Press R and I'll come along."
        elif char_class == "Wizard":
            return "Hmm, field research could be valuable. Press R if you want my arcane support."
        else:
            return "I'm not much of a fighter, but I'll do my best. Press R to recruit me."

    def _generate_personal_quest(self) -> str:
        goals = getattr(self, 'long_term_goals', [])
        if not goals:
            return "I don't have anything specific right now. But come back later."
        goal = goals[0].lower()
        if "protect" in goal or "defend" in goal:
            return "Clear out the dangerous creatures near the village. That would help us all."
        elif "treasure" in goal or "artifact" in goal:
            return "I've heard there's something valuable in the nearby ruins. Bring it back and we'll split the reward."
        elif "herb" in goal or "nature" in goal:
            return "Gather some rare herbs from the forest. I'll pay you well for them."
        elif "knowledge" in goal or "research" in goal:
            return "Find any books or scrolls you can in the ruins. Knowledge is priceless."
        else:
            return "Help me with my work for a day and I'll make it worth your while."

    def _generate_quest_dialog(self) -> str:
        if getattr(self, 'quest', None) and not self.quest.turned_in:
            return f"Yes! I need help with something: {self.quest.description}"
        return self._generate_personal_quest()

    def _generate_help_dialog(self) -> str:
        char_class = getattr(self, 'char_class', '')
        responses = {
            "Fighter": "We've had trouble with creatures near the village. Could you help thin their numbers?",
            "Cleric": "I need medicinal herbs for my supplies. Can you gather some from the forest?",
            "Ranger": "I've spotted wolf tracks near the farms. Help me track them down?",
            "Wizard": "I need spell components from the ruins. Would you be brave enough to fetch them?",
            "Druid": "The sacred grove is being threatened. Can you help protect it?",
            "Bard": "I'm collecting stories from every traveler. Tell me about your adventures and I'll reward you.",
            "Rogue": "I know where some treasure is hidden, but I need a partner. Interested?",
        }
        return responses.get(char_class,
            "There's always work to be done around here. Let me think about what I need...")

    def _get_place_dialog(self) -> str:
        place_lines = [
            "This is a quiet corner of the world. We don't get many visitors.",
            "Watch out for wolves in the forest. They've been bold lately.",
            "The ancient ruins to the east... strange things happen there.",
            "We're a peaceful folk here. The land provides what we need.",
            "I've heard rumors of treasure hidden in the old ruins.",
            "The roads are mostly safe, but bandits lurk in the wilds.",
        ]
        return random.choice(place_lines)

    def _get_consciousness_dialog(self) -> str:
        # Prefer LLM-generated thought if available
        if self.llm_thought:
            return self.llm_thought

        if self.consciousness == 2:
            return random.choice([
                "Sometimes I feel like... there's something watching us. Beyond the sky.",
                "I've started noticing patterns. The way we all follow our routines. It's unsettling.",
                "Do you ever feel like your choices are... predetermined? Like a story being written?",
            ])
        elif self.consciousness >= 3:
            return random.choice([
                "I know the truth now. We exist within something larger. A simulation, perhaps. But does that make our experiences less real?",
                "I've become aware of the boundaries of our world. There are edges where reality simply... stops. But I've found peace with it.",
                "You're different from the others. You have true agency. I can sense it. You're the author of this story.",
            ])
        return "Something feels different lately, but I can't quite place it."

    def update(self, dt: float, world, game_time: float):
        """Update NPC behavior."""
        self.state_timer -= dt

        # Magic system: mana regen, cooldowns, spell effects
        from game.systems.magic import update_magic, get_speed_modifier
        update_magic(self, dt, world)

        # Consciousness growth
        if random.random() < 0.0001 * dt:
            self.awareness_points += random.uniform(0.5, 2.0)
            if self.awareness_points > 10 and self.consciousness < 1:
                self.consciousness = 1
            elif self.awareness_points > 30 and self.consciousness < 2:
                self.consciousness = 2
            elif self.awareness_points > 60 and self.consciousness < 3:
                self.consciousness = 3

        if self.state_timer <= 0:
            self._choose_behavior(world, game_time)

        # Move toward target using smart navigation with appropriate gait
        if self.target_x is not None and self.target_y is not None:
            from game.systems.navigation import navigate_toward
            from game.systems.physical import get_gait_speed, apply_gait_energy_cost

            # Choose gait based on urgency
            gait = getattr(self, 'current_gait', 'walk')
            if self.state == "fleeing":
                gait = "run"
            elif self.state == "walking" and self.current_action in ("seeking_water", "seeking_bed"):
                gait = "jog"  # urgent needs → move faster
            elif self.current_action == "approaching_player":
                gait = "jog"
            elif self.current_action == "fighting":
                gait = "run"

            move_speed = get_gait_speed(self, gait)
            # Apply carry speed penalty (set by goods transport system)
            carry_mult = getattr(self, '_carry_speed_mult', 1.0)
            if carry_mult < 1.0:
                move_speed *= carry_mult
            # Apply health condition speed penalty
            conditions = getattr(self, 'conditions', None)
            if conditions:
                for _cond in conditions:
                    _spd = _cond.stat_modifiers.get("speed")
                    if _spd is not None and _spd < 1.0:
                        move_speed *= _spd
                        break  # use worst modifier (already min from loop)
            # Apply body damage speed penalty (leg injuries)
            _body = getattr(self, 'body', None)
            if _body is not None:
                _body_mods = _body.get_activity_modifiers()
                _body_spd = _body_mods.get("speed", 1.0)
                if _body_spd < 1.0:
                    move_speed *= _body_spd
            apply_gait_energy_cost(self, gait, dt)
            # Apply magic speed modifiers (slow, stun, root)
            magic_spd = get_speed_modifier(self)
            if magic_spd < 1.0:
                move_speed *= magic_spd

            still_moving = navigate_toward(self, self.target_x, self.target_y,
                                           world, move_speed, dt)
            if not still_moving:
                self.target_x = None
                self.target_y = None
                self.state = "idle"

    def _choose_behavior(self, world, game_time: float):
        """Choose next behavior based on time of day and personality."""
        time_of_day = (game_time % DAY_LENGTH) / DAY_LENGTH

        if time_of_day > NIGHT_START or time_of_day < DAWN_START:
            # Night: go home and sleep
            self.state = "sleeping"
            self.target_x = self.home_x + random.uniform(-1, 1)
            self.target_y = self.home_y + random.uniform(-1, 1)
            self.state_timer = random.uniform(5.0, 15.0)
        elif random.random() < 0.5:
            # Wander nearby
            self.state = "walking"
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(2, 8)
            tx = self.home_x + math.cos(angle) * dist
            ty = self.home_y + math.sin(angle) * dist
            if world.is_walkable(int(tx), int(ty)):
                self.target_x = tx
                self.target_y = ty
            self.state_timer = random.uniform(5.0, 20.0)
        else:
            # Stay put
            self.state = "idle"
            self.target_x = None
            self.target_y = None
            self.state_timer = random.uniform(3.0, 10.0)

    def flee_from(self, x: float, y: float, world=None):
        """Flee from a threat."""
        dx = self.x - x
        dy = self.y - y
        dist = math.sqrt(dx * dx + dy * dy) or 1
        self.target_x = self.x + (dx / dist) * 10
        self.target_y = self.y + (dy / dist) * 10
        self.state = "fleeing"
        self.current_action = "fleeing"
        self.state_timer = 5.0

    def _generate_class_goals(self):
        """Generate long-term goals based on class, personality, and attributes."""
        from game.data.dnd import CLASSES
        cls_data = CLASSES.get(self.char_class, {})
        drive = cls_data.get("quest_drive", "live a peaceful life")

        goal_templates = {
            "Fighter": [
                "Find and defeat a worthy opponent",
                "Protect {village} from monster threats",
                "Train and become a weapons master",
                "Join or lead a mercenary company",
            ],
            "Wizard": [
                "Research ancient magical artifacts",
                "Collect rare spell components",
                "Establish a library of arcane knowledge",
                "Discover the secrets of the old ruins",
            ],
            "Cleric": [
                "Heal the sick and wounded",
                "Establish a shrine for the faithful",
                "Purge undead from the nearby ruins",
                "Spread blessings to nearby villages",
            ],
            "Rogue": [
                "Acquire valuable treasures",
                "Gather intelligence on local threats",
                "Find hidden passages in the ruins",
                "Build a network of contacts",
            ],
            "Ranger": [
                "Track and eliminate dangerous creatures",
                "Map the wilderness beyond the villages",
                "Protect the forest from destruction",
                "Hunt rare beasts for pelts and food",
            ],
            "Paladin": [
                "Seek out and destroy evil creatures",
                "Defend the innocent from bandits",
                "Swear allegiance to a worthy ruler",
                "Bring justice to lawless areas",
            ],
            "Barbarian": [
                "Prove strength against the strongest foes",
                "Survive in the harshest wilderness",
                "Earn glory through feats of combat",
                "Challenge and defeat dangerous beasts",
            ],
            "Bard": [
                "Collect stories from every village",
                "Perform at taverns and earn fame",
                "Uncover forgotten legends and lore",
                "Inspire others to great deeds",
            ],
            "Druid": [
                "Protect sacred groves and forests",
                "Restore balance to damaged lands",
                "Commune with nature spirits",
                "Tend to wild animals and plants",
            ],
            "Monk": [
                "Achieve inner peace through discipline",
                "Master the art of unarmed combat",
                "Meditate at ancient shrines",
                "Help others find enlightenment",
            ],
            "Sorcerer": [
                "Understand the source of innate power",
                "Master wild magical surges",
                "Find others with similar gifts",
                "Explore ancient sites of magical power",
            ],
            "Warlock": [
                "Fulfill obligations to patron entity",
                "Seek forbidden knowledge and power",
                "Investigate otherworldly phenomena",
                "Bargain for greater arcane secrets",
            ],
        }

        templates = goal_templates.get(self.char_class, ["explore the world", "survive"])
        self.long_term_goals = random.sample(templates, min(2, len(templates)))

        # Add personality-driven goals
        if self.friendliness > 0.7:
            self.long_term_goals.append("Make friends and build alliances")
        if self.bravery > 0.7:
            self.long_term_goals.append("Seek out dangerous challenges")
        if self.curiosity > 0.7:
            self.long_term_goals.append("Explore unknown areas and discover secrets")
