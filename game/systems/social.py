"""
Social dynamics system - Sims-inspired relationships, alliances, rivalries.

Handles:
- Relationship chemistry based on race, class, personality, alignment
- Social interactions: flirt, intimidate, joke, gossip, argue, comfort, betray
- Alliances and rivalries that form organically
- Emotional state (mood) affecting behavior
- Reputation and social standing
- Race/class affinities and tensions
"""

import random
import math
from typing import Dict, List, Optional, Tuple, Any
from game.settings import NPC_CONVERSATION_RANGE


# ================================================================
# RACIAL AFFINITIES - who naturally gets along or clashes
# ================================================================

# Positive = natural affinity, Negative = natural tension, 0 = neutral
RACIAL_AFFINITY = {
    ("Elf", "Elf"): 15,
    ("Elf", "Half-Elf"): 10,
    ("Elf", "Human"): 0,
    ("Elf", "Dwarf"): -10,         # classic rivalry
    ("Elf", "Half-Orc"): -15,
    ("Elf", "Gnome"): 5,
    ("Elf", "Tiefling"): -5,
    ("Dwarf", "Dwarf"): 20,        # strong clan bonds
    ("Dwarf", "Gnome"): 10,        # fellow crafters
    ("Dwarf", "Half-Orc"): -15,
    ("Dwarf", "Human"): 5,
    ("Dwarf", "Halfling"): 5,
    ("Dwarf", "Tiefling"): -10,
    ("Human", "Human"): 5,
    ("Human", "Half-Elf"): 5,
    ("Human", "Half-Orc"): -5,
    ("Human", "Tiefling"): -10,    # distrust
    ("Human", "Halfling"): 5,
    ("Halfling", "Halfling"): 15,
    ("Halfling", "Gnome"): 10,
    ("Half-Orc", "Half-Orc"): 10,
    ("Half-Orc", "Tiefling"): 5,   # fellow outcasts
    ("Gnome", "Gnome"): 10,
    ("Tiefling", "Tiefling"): 10,
    ("Half-Elf", "Half-Elf"): 10,
}

# ================================================================
# CLASS COMPATIBILITY - professional respect or rivalry
# ================================================================

CLASS_AFFINITY = {
    ("Fighter", "Fighter"): 5,      # mutual respect
    ("Fighter", "Barbarian"): 5,    # warriors bond
    ("Fighter", "Paladin"): 10,     # brothers in arms
    ("Fighter", "Wizard"): -5,      # brawn vs brains
    ("Wizard", "Wizard"): 5,        # academic peers
    ("Wizard", "Sorcerer"): -10,    # studied vs innate magic rivalry
    ("Wizard", "Warlock"): -5,      # distrust of dark pacts
    ("Wizard", "Druid"): 0,
    ("Cleric", "Paladin"): 15,      # divine allies
    ("Cleric", "Warlock"): -15,     # holy vs unholy
    ("Cleric", "Druid"): 5,
    ("Rogue", "Rogue"): -5,         # thieves distrust thieves
    ("Rogue", "Bard"): 10,          # kindred spirits
    ("Rogue", "Paladin"): -15,      # law vs chaos
    ("Ranger", "Druid"): 15,        # nature allies
    ("Ranger", "Ranger"): 10,
    ("Bard", "Bard"): 5,            # performers together
    ("Bard", "Monk"): -5,           # loud vs quiet
    ("Monk", "Monk"): 10,           # shared discipline
    ("Monk", "Barbarian"): -10,     # discipline vs chaos
    ("Paladin", "Warlock"): -20,    # strongest opposition
    ("Paladin", "Rogue"): -10,
    ("Barbarian", "Barbarian"): 10,
    ("Sorcerer", "Sorcerer"): 5,
    ("Warlock", "Warlock"): 5,
    ("Druid", "Druid"): 10,
}

# ================================================================
# ALIGNMENT COMPATIBILITY
# ================================================================

ALIGNMENT_AFFINITY = {
    ("lawful good", "lawful good"): 15,
    ("lawful good", "neutral good"): 10,
    ("lawful good", "chaotic good"): 0,
    ("lawful good", "lawful neutral"): 5,
    ("lawful good", "true neutral"): 0,
    ("lawful good", "chaotic neutral"): -15,
    ("neutral good", "neutral good"): 10,
    ("neutral good", "chaotic good"): 5,
    ("chaotic good", "chaotic good"): 10,
    ("chaotic good", "lawful neutral"): -10,
    ("chaotic neutral", "chaotic neutral"): 5,
    ("chaotic neutral", "lawful neutral"): -15,
    ("true neutral", "true neutral"): 5,
}

# ================================================================
# SOCIAL INTERACTION TYPES
# ================================================================

SOCIAL_INTERACTIONS = {
    "friendly_chat": {
        "trust_change": (2, 5), "mood_change": (3, 8),
        "requirement": "trust > -20",
        "description": "{a} and {b} have a friendly conversation.",
    },
    "joke": {
        "trust_change": (3, 8), "mood_change": (5, 15),
        "requirement": "charisma > 4",
        "description": "{a} tells {b} a joke.",
    },
    "gossip": {
        "trust_change": (-2, 3), "mood_change": (1, 5),
        "requirement": "trust > 0",
        "description": "{a} shares gossip with {b}.",
        "shares_info": True,
    },
    "deep_talk": {
        "trust_change": (5, 12), "mood_change": (3, 10),
        "requirement": "trust > 20 and intelligence > 5",
        "description": "{a} and {b} have a deep, meaningful conversation.",
    },
    "flirt": {
        "trust_change": (-5, 15), "mood_change": (-5, 20),
        "requirement": "charisma > 5",
        "description": "{a} flirts with {b}.",
    },
    "comfort": {
        "trust_change": (5, 10), "mood_change": (10, 25),
        "requirement": "trust > 10 and target_mood < -10",
        "description": "{a} comforts {b} who seems upset.",
    },
    "argue": {
        "trust_change": (-10, -3), "mood_change": (-15, -5),
        "requirement": "trust < 10 or mood < -10",
        "description": "{a} and {b} have a heated argument.",
    },
    "intimidate": {
        "trust_change": (-15, -5), "mood_change": (-20, -10),
        "requirement": "strength > 6 or charisma > 6",
        "description": "{a} tries to intimidate {b}.",
    },
    "trade_offer": {
        "trust_change": (1, 5), "mood_change": (0, 5),
        "requirement": "trust > -10",
        "description": "{a} proposes a trade with {b}.",
    },
    "ask_for_help": {
        "trust_change": (0, 5), "mood_change": (-3, 3),
        "requirement": "trust > 10",
        "description": "{a} asks {b} for help.",
    },
    "share_meal": {
        "trust_change": (5, 10), "mood_change": (8, 15),
        "requirement": "trust > 5 and has_food",
        "description": "{a} shares a meal with {b}.",
    },
    "spar": {
        "trust_change": (2, 8), "mood_change": (3, 10),
        "requirement": "both_combat_classes",
        "description": "{a} and {b} spar together for training.",
    },
    "study_together": {
        "trust_change": (3, 8), "mood_change": (2, 8),
        "requirement": "both_caster_classes",
        "description": "{a} and {b} study magical theory together.",
    },
    "pray_together": {
        "trust_change": (5, 10), "mood_change": (5, 12),
        "requirement": "both_divine_classes",
        "description": "{a} and {b} pray together.",
    },
    "betray": {
        "trust_change": (-30, -15), "mood_change": (-25, -10),
        "requirement": "trust < -10 and alignment_evil",
        "description": "{a} betrays {b}'s confidence.",
    },
    "challenge": {
        "trust_change": (-8, 5), "mood_change": (-5, 10),
        "requirement": "bravery > 0.6",
        "description": "{a} challenges {b} to prove their worth.",
    },
}

# ================================================================
# PERSONALITY TRAITS (Sims-inspired)
# ================================================================

PERSONALITY_TRAITS = [
    "romantic", "loner", "social_butterfly", "hothead", "peacemaker",
    "ambitious", "lazy", "generous", "greedy", "loyal",
    "treacherous", "cheerful", "gloomy", "bookworm", "adventurous",
    "cautious", "compassionate", "cruel", "honest", "deceptive",
]

# Trait compatibility: which traits attract or repel
TRAIT_AFFINITY = {
    ("romantic", "romantic"): 15,
    ("romantic", "loner"): -10,
    ("social_butterfly", "social_butterfly"): 10,
    ("social_butterfly", "loner"): -15,
    ("hothead", "peacemaker"): -10,
    ("hothead", "hothead"): -5,
    ("ambitious", "ambitious"): -5,   # competitive
    ("ambitious", "lazy"): -10,
    ("generous", "greedy"): -15,
    ("generous", "generous"): 10,
    ("loyal", "loyal"): 15,
    ("loyal", "treacherous"): -25,
    ("cheerful", "cheerful"): 10,
    ("cheerful", "gloomy"): -5,
    ("bookworm", "bookworm"): 10,
    ("adventurous", "adventurous"): 10,
    ("adventurous", "cautious"): -5,
    ("compassionate", "cruel"): -20,
    ("compassionate", "compassionate"): 15,
    ("honest", "deceptive"): -20,
    ("honest", "honest"): 15,
}


# ================================================================
# SOCIAL SYSTEM
# ================================================================

class Relationship:
    """Detailed relationship between two NPCs."""
    __slots__ = ('trust', 'mood_toward', 'interaction_count', 'last_interaction',
                 'status', 'shared_experiences', 'grudges')

    def __init__(self):
        self.trust = 0              # -100 to 100
        self.mood_toward = 0        # how they feel right now about this person
        self.interaction_count = 0
        self.last_interaction = 0.0
        self.status = "stranger"    # stranger, acquaintance, friend, close_friend, rival, enemy, ally
        self.shared_experiences = 0 # count of meaningful shared events
        self.grudges = 0            # count of negative interactions

    def update_status(self):
        """Update relationship status based on trust level."""
        if self.trust >= 60:
            self.status = "close_friend"
        elif self.trust >= 30:
            self.status = "friend"
        elif self.trust >= 10:
            self.status = "acquaintance"
        elif self.trust >= -10:
            self.status = "stranger"
        elif self.trust >= -30:
            self.status = "rival"
        else:
            self.status = "enemy"

    @property
    def label(self) -> str:
        labels = {
            "close_friend": "close friend",
            "friend": "friend",
            "acquaintance": "acquaintance",
            "stranger": "stranger",
            "rival": "rival",
            "enemy": "enemy",
            "ally": "ally",
        }
        return labels.get(self.status, self.status)


def get_affinity(key: tuple, table: dict) -> int:
    """Look up affinity in a symmetric table."""
    return table.get(key, table.get((key[1], key[0]), 0))


class SocialSystem:
    """Manages all NPC social interactions and relationship dynamics."""

    def __init__(self):
        # Detailed relationships: (npc_name, target_name) -> Relationship
        self.relationships: Dict[Tuple[str, str], Relationship] = {}
        self.social_log: List[str] = []
        self.interaction_timer = 0.0

    def get_rel(self, name_a: str, name_b: str) -> Relationship:
        """Get or create relationship between two characters."""
        key = (name_a, name_b)
        if key not in self.relationships:
            self.relationships[key] = Relationship()
        return self.relationships[key]

    def compute_initial_chemistry(self, npc_a, npc_b) -> int:
        """Calculate initial chemistry between two NPCs based on race, class, alignment, personality."""
        score = 0

        # Race affinity
        race_a = getattr(npc_a, 'race', 'Human')
        race_b = getattr(npc_b, 'race', 'Human')
        score += get_affinity((race_a, race_b), RACIAL_AFFINITY)

        # Class affinity
        class_a = getattr(npc_a, 'char_class', '')
        class_b = getattr(npc_b, 'char_class', '')
        score += get_affinity((class_a, class_b), CLASS_AFFINITY)

        # Alignment affinity (using proper system)
        from game.systems.alignment import alignment_compatibility
        align_a = getattr(npc_a, 'alignment', 'true neutral')
        align_b = getattr(npc_b, 'alignment', 'true neutral')
        score += alignment_compatibility(align_a, align_b)

        # Personality trait affinity
        traits_a = getattr(npc_a, 'social_traits', [])
        traits_b = getattr(npc_b, 'social_traits', [])
        for ta in traits_a:
            for tb in traits_b:
                score += get_affinity((ta, tb), TRAIT_AFFINITY)

        return score

    def initialize_relationships(self, npcs: list):
        """Set initial relationship chemistry between all nearby NPCs."""
        for i, npc_a in enumerate(npcs):
            if not npc_a.alive:
                continue
            for npc_b in npcs[i+1:]:
                if not npc_b.alive:
                    continue
                # Only initialize for NPCs in same village
                if npc_a.dist_to(npc_b) > 20:
                    continue

                chemistry = self.compute_initial_chemistry(npc_a, npc_b)
                rel_ab = self.get_rel(npc_a.name, npc_b.name)
                rel_ba = self.get_rel(npc_b.name, npc_a.name)
                rel_ab.trust = chemistry + random.randint(-5, 5)
                rel_ba.trust = chemistry + random.randint(-5, 5)
                rel_ab.update_status()
                rel_ba.update_status()

                # Update NPC friend/enemy lists and life ledger bonds
                if rel_ab.trust >= 20:
                    if npc_b.name not in npc_a.friends:
                        npc_a.friends.append(npc_b.name)
                        from game.systems.memory import ensure_life_ledger
                        ledger = ensure_life_ledger(npc_a)
                        ledger.record_bond(npc_b.name, "friend", 0,
                                          trust=int(rel_ab.trust))
                    if npc_a.name not in npc_b.friends:
                        npc_b.friends.append(npc_a.name)
                        from game.systems.memory import ensure_life_ledger
                        ledger = ensure_life_ledger(npc_b)
                        ledger.record_bond(npc_a.name, "friend", 0,
                                          trust=int(rel_ba.trust))
                elif rel_ab.trust <= -20:
                    if npc_b.name not in npc_a.enemies:
                        npc_a.enemies.append(npc_b.name)
                        from game.systems.memory import ensure_life_ledger
                        ledger = ensure_life_ledger(npc_a)
                        ledger.record_bond(npc_b.name, "enemy", 0,
                                          trust=int(rel_ab.trust))
                    if npc_a.name not in npc_b.enemies:
                        npc_b.enemies.append(npc_a.name)
                        from game.systems.memory import ensure_life_ledger
                        ledger = ensure_life_ledger(npc_b)
                        ledger.record_bond(npc_a.name, "enemy", 0,
                                          trust=int(rel_ba.trust))

    def update(self, dt: float, npcs: list, player):
        """Periodic social interactions between nearby NPCs."""
        self.interaction_timer -= dt
        if self.interaction_timer > 0:
            return

        self.interaction_timer = random.uniform(3.0, 8.0)

        # Find pairs of nearby NPCs and trigger social interactions
        for npc_a in npcs:
            if not npc_a.alive or npc_a.current_action in ("fighting", "sleeping", "fleeing"):
                continue
            for npc_b in npcs:
                if npc_b is npc_a or not npc_b.alive:
                    continue
                if npc_b.current_action in ("fighting", "sleeping", "fleeing"):
                    continue
                if npc_a.dist_to(npc_b) > NPC_CONVERSATION_RANGE:
                    continue

                # Random chance of interaction
                if random.random() > 0.15:
                    continue

                self._do_social_interaction(npc_a, npc_b)
                return  # One interaction per tick

    def _do_social_interaction(self, npc_a, npc_b):
        """Execute a social interaction between two NPCs."""
        rel_ab = self.get_rel(npc_a.name, npc_b.name)
        rel_ba = self.get_rel(npc_b.name, npc_a.name)

        # Choose interaction type based on relationship and personality
        interaction = self._choose_interaction(npc_a, npc_b, rel_ab)
        if not interaction:
            return

        itype = interaction
        idata = SOCIAL_INTERACTIONS[itype]

        # Calculate outcome
        trust_min, trust_max = idata["trust_change"]

        # Modify by charisma
        cha_mod = (npc_a.attributes.get("charisma", 5) - 5) * 0.5
        trust_change = random.uniform(trust_min, trust_max) + cha_mod

        # Mood effect
        mood_min, mood_max = idata["mood_change"]
        mood_change = random.uniform(mood_min, mood_max)

        # Apply
        rel_ab.trust = max(-100, min(100, rel_ab.trust + trust_change))
        rel_ba.trust = max(-100, min(100, rel_ba.trust + trust_change * 0.7))
        rel_ab.mood_toward = max(-50, min(50, rel_ab.mood_toward + mood_change))
        rel_ab.interaction_count += 1
        rel_ba.interaction_count += 1
        rel_ab.update_status()
        rel_ba.update_status()

        if trust_change < -5:
            rel_ab.grudges += 1

        if trust_change > 5:
            rel_ab.shared_experiences += 1

        # Update NPC friend/enemy lists
        if rel_ab.trust >= 20 and npc_b.name not in npc_a.friends:
            npc_a.friends.append(npc_b.name)
            if npc_b.name in npc_a.enemies:
                npc_a.enemies.remove(npc_b.name)
        elif rel_ab.trust <= -20 and npc_b.name not in npc_a.enemies:
            npc_a.enemies.append(npc_b.name)
            if npc_b.name in npc_a.friends:
                npc_a.friends.remove(npc_b.name)

        # Mirror for npc_b
        if rel_ba.trust >= 20 and npc_a.name not in npc_b.friends:
            npc_b.friends.append(npc_a.name)
        elif rel_ba.trust <= -20 and npc_a.name not in npc_b.enemies:
            npc_b.enemies.append(npc_a.name)

        # Social need boost
        npc_a.needs["social"] = min(100, npc_a.needs.get("social", 50) + abs(mood_change) * 0.5)
        npc_b.needs["social"] = min(100, npc_b.needs.get("social", 50) + abs(mood_change) * 0.3)

        # Add memories
        desc = idata["description"].format(a=npc_a.name, b=npc_b.name)
        importance = 2 if abs(trust_change) > 8 else 1
        npc_a.add_memory("social", desc, importance)
        npc_b.add_memory("social", desc, importance)

        # Share information during gossip
        if idata.get("shares_info"):
            _share_info(npc_a, npc_b)

        # --- Rich conversation effects (mirroring player conversations) ---
        # Needs-driven help: share food with hungry friends
        if rel_ab.trust > 10 and npc_b.needs.get("hunger", 50) < 30:
            if hasattr(npc_a, 'has_food') and npc_a.has_food():
                from game.core.items import FOOD_ITEMS, make_item
                for item in list(getattr(npc_a, 'npc_inventory', [])):
                    if item.name in FOOD_ITEMS:
                        npc_a.npc_remove_item(item.name)
                        npc_b.npc_add_item(make_item(item.name))
                        npc_b.needs["hunger"] = min(100, npc_b.needs["hunger"] + 25)
                        npc_a.add_memory("social", f"Shared food with hungry {npc_b.name}", 3)
                        npc_b.add_memory("social", f"{npc_a.name} gave me food when I was starving", 4)
                        rel_ba.trust = min(100, rel_ba.trust + 5)
                        break

        # Skill teaching between friends (8% chance per interaction)
        if rel_ab.trust > 15 and random.random() < 0.08:
            t_skills = getattr(npc_a, 'npc_skills', {})
            s_skills = getattr(npc_b, 'npc_skills', {})
            if t_skills:
                best = max(t_skills, key=t_skills.get)
                if t_skills[best] > s_skills.get(best, 0):
                    from game.systems.skills import gain_skill_xp
                    gain_skill_xp(npc_b, best, 1.5)
                    gain_skill_xp(npc_a, "leadership", 0.3)
                    npc_a.add_memory("teaching", f"Taught {npc_b.name} about {best}", 3)
                    npc_b.add_memory("learning", f"{npc_a.name} taught me {best}", 3)
                    rel_ba.trust = min(100, rel_ba.trust + 3)

        # NPC-NPC item trading based on needs (5% chance)
        if random.random() < 0.05:
            from game.core.items import FOOD_ITEMS, make_item
            for item in list(getattr(npc_b, 'npc_inventory', [])):
                need = False
                if item.name in FOOD_ITEMS and npc_a.needs.get("hunger", 50) < 40:
                    need = True
                elif getattr(item, 'heal', 0) > 0 and npc_a.hp < npc_a.max_hp * 0.6:
                    need = True
                if need and npc_a.npc_gold >= max(1, int(item.value * 0.7)):
                    price = max(1, int(item.value * 0.7))
                    npc_b.npc_remove_item(item.name)
                    npc_a.npc_add_item(make_item(item.name))
                    npc_a.npc_gold -= price
                    npc_b.npc_gold += price
                    npc_a.add_memory("trade", f"Bought {item.name} from {npc_b.name}", 2)
                    npc_b.add_memory("trade", f"Sold {item.name} to {npc_a.name}", 2)
                    if item.name in FOOD_ITEMS:
                        npc_a.needs["hunger"] = min(100, npc_a.needs["hunger"] + 20)
                    break

        # Emotional support: comfort sad friends
        es_b = getattr(npc_b, 'emotion_state', None)
        if es_b and rel_ab.trust > 10 and hasattr(es_b, 'primary'):
            sadness = es_b.primary.get("sadness", 0)
            if sadness > 0.4:
                es_b.primary["sadness"] = max(0, sadness - 0.15)
                npc_a.add_memory("social", f"Comforted {npc_b.name} who was feeling down", 3)
                npc_b.add_memory("social", f"{npc_a.name} comforted me when I was sad", 4)
                rel_ba.trust = min(100, rel_ba.trust + 4)
                npc_b.needs["social"] = min(100, npc_b.needs.get("social", 50) + 12)

        # Warn about dangers
        dangers = [k for k in npc_a.known_info if any(w in k.lower() for w in
                   ["danger", "monster", "bandit", "attack", "killed"])]
        if dangers and rel_ab.trust > 5 and random.random() < 0.2:
            warning = random.choice(dangers)
            if warning not in npc_b.known_info:
                npc_b.known_info.append(warning)
                npc_a.add_memory("social", f"Warned {npc_b.name} about dangers", 2)
                npc_b.add_memory("social", f"{npc_a.name} warned me: {warning[:40]}", 3)

        # Log significant interactions
        if abs(trust_change) > 5:
            outcome = "positively" if trust_change > 0 else "negatively"
            self.social_log.append(f"{desc} ({outcome}, trust now {rel_ab.trust:+.0f})")

        # NPC mood affects personality
        npc_a_mood = getattr(npc_a, 'mood', 0)
        npc_a.mood = max(-1, min(1, npc_a_mood + mood_change * 0.01))

    def _choose_interaction(self, npc_a, npc_b, rel: Relationship) -> Optional[str]:
        """Choose the most appropriate interaction type."""
        candidates = []

        class_a = getattr(npc_a, 'char_class', '')
        class_b = getattr(npc_b, 'char_class', '')
        combat_classes = {"Fighter", "Barbarian", "Paladin", "Ranger"}
        caster_classes = {"Wizard", "Sorcerer", "Warlock"}
        divine_classes = {"Cleric", "Paladin", "Druid"}
        cha_a = npc_a.attributes.get("charisma", 5)
        str_a = npc_a.attributes.get("strength", 5)
        int_a = npc_a.attributes.get("intelligence", 5)

        for itype, idata in SOCIAL_INTERACTIONS.items():
            req = idata["requirement"]

            # Check requirements
            ok = True
            if "trust > " in req:
                threshold = int(req.split("trust > ")[1].split()[0])
                if rel.trust <= threshold:
                    ok = False
            if "trust < " in req:
                threshold = int(req.split("trust < ")[1].split()[0])
                if rel.trust >= threshold:
                    ok = False
            if "charisma > " in req:
                threshold = int(req.split("charisma > ")[1].split()[0])
                if cha_a <= threshold:
                    ok = False
            if "strength > " in req:
                threshold = int(req.split("strength > ")[1].split()[0])
                if str_a <= threshold:
                    ok = False
            if "intelligence > " in req:
                threshold = int(req.split("intelligence > ")[1].split()[0])
                if int_a <= threshold:
                    ok = False
            if "bravery > " in req:
                threshold = float(req.split("bravery > ")[1].split()[0])
                if npc_a.bravery <= threshold:
                    ok = False
            if "has_food" in req and not npc_a.has_food():
                ok = False
            if "target_mood < " in req:
                if npc_b.mood >= -0.1:
                    ok = False
            if "both_combat_classes" in req:
                if class_a not in combat_classes or class_b not in combat_classes:
                    ok = False
            if "both_caster_classes" in req:
                if class_a not in caster_classes or class_b not in caster_classes:
                    ok = False
            if "both_divine_classes" in req:
                if class_a not in divine_classes or class_b not in divine_classes:
                    ok = False
            if "alignment_evil" in req:
                align = getattr(npc_a, 'alignment', '')
                if 'neutral' in align or 'good' in align:
                    ok = False

            if ok:
                # Weight by appropriateness
                weight = 10
                if rel.trust > 20 and itype in ("friendly_chat", "deep_talk", "share_meal", "joke"):
                    weight = 25
                elif rel.trust < -10 and itype in ("argue", "intimidate", "challenge"):
                    weight = 25
                elif rel.trust < -30 and itype == "betray":
                    weight = 15
                candidates.append((itype, weight))

        if not candidates:
            return "friendly_chat"  # fallback

        types, weights = zip(*candidates)
        return random.choices(types, weights=weights, k=1)[0]

    def get_relationship_summary(self, npc_name: str, limit: int = 5) -> str:
        """Get a text summary of an NPC's key relationships for LLM context."""
        rels = []
        for (a, b), rel in self.relationships.items():
            if a == npc_name and rel.interaction_count > 0:
                rels.append((b, rel))

        rels.sort(key=lambda x: abs(x[1].trust), reverse=True)

        parts = []
        for target, rel in rels[:limit]:
            parts.append(f"{target}: {rel.label} (trust:{rel.trust:+.0f})")
        return ", ".join(parts) if parts else "no established relationships"

    def get_social_log(self) -> List[str]:
        """Pop accumulated social event messages."""
        msgs = list(self.social_log)
        self.social_log.clear()
        return msgs


def _share_info(npc_a, npc_b):
    """Share known information during gossip."""
    for info in npc_a.known_info[-3:]:
        if info not in npc_b.known_info:
            npc_b.known_info.append(info)
            if len(npc_b.known_info) > 20:
                npc_b.known_info = npc_b.known_info[-20:]
    for info in npc_b.known_info[-3:]:
        if info not in npc_a.known_info:
            npc_a.known_info.append(info)
            if len(npc_a.known_info) > 20:
                npc_a.known_info = npc_a.known_info[-20:]
