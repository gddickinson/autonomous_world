"""
God AI Pantheon: divine beings that observe the world, answer prayers,
perform miracles, compete with each other, and petition the game creator.

Works fully rule-based without LLM. LLM enhances descriptions when available.
"""

import random
import time
from typing import Dict, List, Optional, Any


# ================================================================
# MIRACLE DEFINITIONS
# ================================================================

MIRACLES = {
    "heal": {"cost": 10, "spheres": ["love", "nature"], "effect": "restore_hp"},
    "protect": {"cost": 20, "spheres": ["war", "love"], "effect": "shield_settlement"},
    "smite": {"cost": 30, "spheres": ["war", "chaos", "death"], "effect": "damage_target"},
    "bless_harvest": {"cost": 15, "spheres": ["nature", "commerce"], "effect": "boost_crops"},
    "inspire": {"cost": 10, "spheres": ["knowledge", "love"], "effect": "boost_morale"},
    "curse": {"cost": 25, "spheres": ["death", "chaos"], "effect": "debuff_target"},
    "reveal": {"cost": 15, "spheres": ["knowledge"], "effect": "reveal_info"},
    "resurrect": {"cost": 80, "spheres": ["death", "love"], "effect": "revive_npc"},
    "plague": {"cost": 40, "spheres": ["death", "chaos"], "effect": "disease_settlement"},
    "fortune": {"cost": 10, "spheres": ["commerce", "chaos"], "effect": "grant_gold"},
}

# What events each sphere cares about
SPHERE_INTERESTS = {
    "war": ["battle", "duel", "army_move", "siege", "conquest", "military"],
    "nature": ["ecology", "season", "farming", "forest", "animal", "weather", "harvest"],
    "knowledge": ["research", "education", "discovery", "technology", "book", "library"],
    "death": ["death", "burial", "undead", "soul", "ghost", "disease", "plague"],
    "commerce": ["trade", "economy", "price", "caravan", "market", "gold", "tax"],
    "love": ["marriage", "birth", "relationship", "friendship", "festival", "social"],
    "chaos": ["battle", "death", "trade", "marriage", "disaster", "earthquake",
              "storm", "plague", "rebellion", "coup"],
}

# Prayer trigger conditions (mapped to emotion/need states)
PRAYER_TRIGGERS = {
    "fear": {"threshold": 0.6, "gods": ["war", "love", "nature"]},
    "gratitude": {"threshold": 0.5, "gods": ["love", "nature", "commerce"]},
    "desperation": {"need_below": 20, "gods": ["death", "nature", "love"]},
    "ambition": {"threshold": 0.5, "gods": ["war", "commerce", "knowledge"]},
}

# Miracle descriptions (rule-based fallbacks)
MIRACLE_DESCRIPTIONS = {
    "restore_hp": [
        "A warm light envelops {target}, mending wounds.",
        "Divine energy flows through {target}, restoring vitality.",
        "{god} breathes life back into {target}.",
    ],
    "shield_settlement": [
        "A shimmering ward rises over {target}.",
        "{god}'s protection blankets {target} in golden light.",
        "An invisible shield forms around {target}.",
    ],
    "damage_target": [
        "Divine wrath strikes {target}!",
        "{god} hurls a bolt of energy at {target}!",
        "The ground cracks beneath {target} as {god} punishes them.",
    ],
    "boost_crops": [
        "The fields around {target} burst with new growth.",
        "{god} blesses the harvest at {target}.",
        "Rain falls gently on {target}'s crops.",
    ],
    "boost_morale": [
        "A feeling of hope spreads through {target}.",
        "{god} inspires courage in the hearts at {target}.",
        "Songs echo through {target} as spirits lift.",
    ],
    "debuff_target": [
        "A dark shadow falls over {target}.",
        "{god} curses {target} with misfortune.",
        "An ill wind blows through {target}.",
    ],
    "reveal_info": [
        "Visions flash before {target}'s eyes.",
        "{god} whispers hidden truths to {target}.",
        "Knowledge floods {target}'s mind.",
    ],
    "revive_npc": [
        "{target} gasps and returns to life!",
        "{god} reaches into the underworld and pulls {target} back.",
        "Death releases its grip on {target}.",
    ],
    "disease_settlement": [
        "A foul miasma spreads through {target}.",
        "{god} unleashes pestilence upon {target}.",
        "Sickness creeps through the streets of {target}.",
    ],
    "grant_gold": [
        "A chest of gold appears before {target}.",
        "{god} rewards {target} with riches.",
        "Fortune smiles upon {target}.",
    ],
}


# ================================================================
# GOD CLASS
# ================================================================

class God:
    """A divine being in the pantheon."""

    def __init__(self, name: str, sphere: str, alignment: float,
                 personality: Dict[str, float]):
        self.name = name
        self.sphere = sphere  # "war", "nature", "knowledge", "death", "commerce", "love", "chaos"
        self.alignment = alignment  # -1.0 to 1.0 (evil to good)
        self.personality = personality  # dict of trait_name -> 0.0-1.0

        self.miracle_points = 100.0  # regenerates slowly (1/game-day)
        self.max_miracle_points = 100.0
        self.worshippers = 0  # count of devoted NPCs
        self.power = 1.0  # grows with worshippers
        self.attention: Dict[str, float] = {}  # event_type -> interest_level
        self.opinions: Dict[str, float] = {}  # npc_name/settlement_name -> opinion (-100 to 100)
        self.prayer_queue: List[Dict] = []  # pending prayers to evaluate
        self.miracles_performed: List[Dict] = []  # log of miracles
        self.petitions_to_higher_power: List[Dict] = []  # requests to the game creator
        self.relationships: Dict[str, float] = {}  # other_god_name -> relationship score


# ================================================================
# DEFAULT PANTHEON
# ================================================================

DEFAULT_PANTHEON = [
    God("Tharion", "war", 0.2, {"aggressive": 0.8, "honorable": 0.6}),
    God("Sylvana", "nature", 0.6, {"patient": 0.9, "protective": 0.7}),
    God("Verithos", "knowledge", 0.4, {"curious": 0.9, "detached": 0.6}),
    God("Morwen", "death", -0.2, {"inevitable": 0.8, "fair": 0.5}),
    God("Auriel", "commerce", 0.3, {"pragmatic": 0.8, "generous": 0.4}),
    God("Lyria", "love", 0.7, {"compassionate": 0.9, "jealous": 0.3}),
    God("Xaotl", "chaos", -0.3, {"unpredictable": 0.9, "creative": 0.7}),
]


# ================================================================
# PANTHEON SYSTEM
# ================================================================

class PantheonSystem:
    """Manages the divine pantheon: observation, prayers, miracles, petitions."""

    def __init__(self, gods: Optional[List[God]] = None,
                 llm_manager=None):
        self.gods: Dict[str, God] = {
            g.name: g for g in (gods or [God(g.name, g.sphere, g.alignment,
                                              dict(g.personality))
                                          for g in DEFAULT_PANTHEON])
        }
        self.llm = llm_manager  # may be None
        self._observation_timer = 0.0
        self._miracle_timer = 0.0
        self._petition_timer = 0.0
        self.event_log: List[str] = []

        # Initialize inter-god relationships
        god_names = list(self.gods.keys())
        for g in self.gods.values():
            for other_name in god_names:
                if other_name != g.name:
                    other = self.gods[other_name]
                    # Alignment similarity drives base relationship
                    diff = abs(g.alignment - other.alignment)
                    g.relationships[other_name] = (1.0 - diff) * 40 - 20  # -20 to 20

    # ----------------------------------------------------------------
    # MAIN UPDATE
    # ----------------------------------------------------------------

    def update(self, dt: float, game_time: float, sim_manager):
        """Main tick. Called every ~30th sim tick."""
        self._regenerate_miracle_points(dt)
        self._observe_world(dt, sim_manager)
        self._process_prayers(game_time, sim_manager)
        self._consider_interventions(game_time, sim_manager)
        self._divine_competition(dt)
        self._consider_petitions(game_time, sim_manager)

    # ----------------------------------------------------------------
    # MIRACLE POINT REGENERATION
    # ----------------------------------------------------------------

    def _regenerate_miracle_points(self, dt: float):
        """Regenerate miracle points. 1 point per game-day (~60s real)."""
        regen_rate = dt / 60.0  # 1 point per 60s of real time
        for god in self.gods.values():
            # Power scales with worshippers
            god.power = 1.0 + god.worshippers * 0.01
            god.max_miracle_points = 100.0 * god.power
            god.miracle_points = min(
                god.max_miracle_points,
                god.miracle_points + regen_rate * god.power
            )

    # ----------------------------------------------------------------
    # WORLD OBSERVATION (rule-based)
    # ----------------------------------------------------------------

    def _observe_world(self, dt: float, sim):
        """Gods watch events relevant to their sphere."""
        self._observation_timer += dt
        if self._observation_timer < 30.0:
            return
        self._observation_timer = 0.0

        # Gather recent events from the simulation event log
        recent_events = getattr(sim, 'event_history', [])
        # Only look at last 20 events to stay efficient
        recent = recent_events[-20:] if recent_events else []

        for god in self.gods.values():
            interests = SPHERE_INTERESTS.get(god.sphere, [])
            god.attention.clear()

            for event_text in recent:
                if not isinstance(event_text, str):
                    continue
                event_lower = event_text.lower()
                for interest in interests:
                    if interest in event_lower:
                        god.attention[interest] = god.attention.get(interest, 0) + 1.0
                        # Form opinions about mentioned entities
                        self._form_opinion_from_event(god, event_text)
                        break

    def _form_opinion_from_event(self, god: God, event_text: str):
        """God forms an opinion about entities mentioned in events."""
        # Simple heuristic: extract names (capitalized words) and adjust opinion
        words = event_text.split()
        positive_words = {"peace", "trade", "festival", "blessed", "victory",
                          "alliance", "harvest", "built", "healed", "saved"}
        negative_words = {"war", "death", "plague", "destroyed", "attacked",
                          "murdered", "corrupt", "famine", "siege", "betrayed"}

        is_positive = any(w.lower() in positive_words for w in words)
        is_negative = any(w.lower() in negative_words for w in words)

        # Alignment affects how god views positive/negative events
        opinion_delta = 0
        if is_positive:
            opinion_delta = 2 + god.alignment * 3  # good gods like good events more
        if is_negative:
            opinion_delta = -2 + god.alignment * -3  # good gods dislike bad events more
            # Chaos god actually likes disruption
            if god.sphere == "chaos":
                opinion_delta = abs(opinion_delta)

        if opinion_delta == 0:
            return

        # Apply opinion to capitalized words that might be names
        for word in words:
            cleaned = word.strip(",.!?:;'\"()[]")
            if cleaned and cleaned[0].isupper() and len(cleaned) > 2:
                # Skip common non-name words
                if cleaned.lower() in ("the", "and", "has", "was", "are",
                                       "for", "but", "not", "with"):
                    continue
                current = god.opinions.get(cleaned, 0)
                god.opinions[cleaned] = max(-100, min(100,
                    current + opinion_delta))

    # ----------------------------------------------------------------
    # PRAYER SYSTEM
    # ----------------------------------------------------------------

    def receive_prayer(self, npc, god_name: str, prayer_text: str,
                       intensity: float = 0.5):
        """NPC prays to a god. Queues the prayer for processing."""
        if god_name not in self.gods:
            return

        god = self.gods[god_name]
        prayer = {
            "npc_name": npc.name,
            "npc_x": npc.x,
            "npc_y": npc.y,
            "npc_hp": getattr(npc, 'hp', 100),
            "npc_max_hp": getattr(npc, 'max_hp', 100),
            "npc_gold": getattr(npc, 'npc_gold', 0),
            "npc_needs": dict(getattr(npc, 'needs', {})),
            "npc_religion": getattr(npc, 'religion', ''),
            "text": prayer_text,
            "intensity": intensity,
            "timestamp": time.time(),
        }
        god.prayer_queue.append(prayer)

        # Cap queue size to prevent unbounded growth
        if len(god.prayer_queue) > 50:
            god.prayer_queue = god.prayer_queue[-50:]

    def _process_prayers(self, game_time: float, sim):
        """Evaluate pending prayers. Gods answer ~5-10% of prayers."""
        for god in self.gods.values():
            if not god.prayer_queue:
                continue

            # Process up to 5 prayers per tick
            batch = god.prayer_queue[:5]
            god.prayer_queue = god.prayer_queue[5:]

            for prayer in batch:
                self._evaluate_prayer(god, prayer, game_time, sim)

    def _evaluate_prayer(self, god: God, prayer: Dict, game_time: float, sim):
        """Evaluate a single prayer and maybe act."""
        npc_name = prayer["npc_name"]
        text = prayer.get("text", "").lower()
        intensity = prayer.get("intensity", 0.5)

        # Calculate response probability (base 5-10%)
        prob = 0.05

        # Skip prayers from atheists
        heresy = getattr(sim, 'heresy', None) if sim else None
        if heresy and heresy.is_atheist(npc_name):
            return

        # Is this NPC a worshipper of a matching religion?
        npc_religion = prayer.get("npc_religion", "")
        if self._religion_matches_god(npc_religion, god):
            prob += 0.05

        # Does the prayer align with god's sphere?
        sphere_keywords = SPHERE_INTERESTS.get(god.sphere, [])
        if any(kw in text for kw in sphere_keywords):
            prob += 0.05

        # Does god like this NPC?
        opinion = god.opinions.get(npc_name, 0)
        prob += opinion * 0.001  # +/- 10% based on opinion

        # Prayer intensity
        prob += intensity * 0.05

        # NPC in danger? (low HP)
        hp_ratio = prayer.get("npc_hp", 100) / max(1, prayer.get("npc_max_hp", 100))
        if hp_ratio < 0.3:
            prob += 0.1

        # Clamp probability
        prob = max(0.02, min(0.30, prob))

        if random.random() > prob:
            # Prayer unanswered — record for heresy tracking
            if heresy:
                heresy.record_prayer(npc_name, answered=False)
            return  # God ignores this prayer

        # God decides to act - pick an appropriate miracle
        miracle_type = self._choose_miracle_for_prayer(god, prayer)
        if miracle_type is None:
            if heresy:
                heresy.record_prayer(npc_name, answered=False)
            return

        cost = MIRACLES[miracle_type]["cost"]
        if god.miracle_points < cost:
            if heresy:
                heresy.record_prayer(npc_name, answered=False)
            return  # Not enough power

        # Perform the miracle — prayer answered!
        if heresy:
            heresy.record_prayer(npc_name, answered=True)
        self.perform_miracle(god, miracle_type, npc_name, game_time, sim)

    def _religion_matches_god(self, religion: str, god: God) -> bool:
        """Check if an NPC's religion aligns with a god's sphere."""
        mapping = {
            "The Light": ["love", "war"],
            "The Old Gods": ["nature", "death"],
            "The Arcane Path": ["knowledge", "chaos"],
            "The Shadow": ["chaos", "death"],
            "The Forge": ["war", "commerce"],
        }
        spheres = mapping.get(religion, [])
        return god.sphere in spheres

    def _choose_miracle_for_prayer(self, god: God, prayer: Dict) -> Optional[str]:
        """Choose an appropriate miracle based on prayer context."""
        text = prayer.get("text", "").lower()
        hp_ratio = prayer.get("npc_hp", 100) / max(1, prayer.get("npc_max_hp", 100))
        needs = prayer.get("npc_needs", {})

        # Priority-ordered miracle selection
        candidates = []

        # Healing if hurt
        if hp_ratio < 0.5 and "heal" in MIRACLES:
            if god.sphere in MIRACLES["heal"]["spheres"]:
                candidates.append(("heal", 3))

        # Fortune if poor
        if prayer.get("npc_gold", 0) < 5 and "fortune" in MIRACLES:
            if god.sphere in MIRACLES["fortune"]["spheres"]:
                candidates.append(("fortune", 2))

        # Inspiration if low social/morale
        if needs.get("social", 50) < 30 and "inspire" in MIRACLES:
            if god.sphere in MIRACLES["inspire"]["spheres"]:
                candidates.append(("inspire", 2))

        # Keyword matching
        keyword_miracles = {
            "victory": "protect", "strength": "protect", "protect": "protect",
            "heal": "heal", "cure": "heal", "mend": "heal",
            "harvest": "bless_harvest", "crops": "bless_harvest", "rain": "bless_harvest",
            "wisdom": "reveal", "knowledge": "reveal", "truth": "reveal",
            "gold": "fortune", "wealth": "fortune", "coin": "fortune",
            "bless": "inspire", "hope": "inspire", "courage": "inspire",
        }
        for keyword, miracle in keyword_miracles.items():
            if keyword in text and miracle in MIRACLES:
                if god.sphere in MIRACLES[miracle]["spheres"]:
                    candidates.append((miracle, 1))

        # Fallback: any miracle this god can perform
        if not candidates:
            for m_name, m_data in MIRACLES.items():
                if god.sphere in m_data["spheres"]:
                    # Skip destructive miracles for prayers (those are for interventions)
                    if m_data["effect"] not in ("damage_target", "disease_settlement",
                                                 "debuff_target"):
                        candidates.append((m_name, 1))

        if not candidates:
            return None

        # Weight by priority
        candidates.sort(key=lambda x: -x[1])
        # Pick from top candidates with some randomness
        top = candidates[:3]
        return random.choice(top)[0]

    # ----------------------------------------------------------------
    # MIRACLE EXECUTION
    # ----------------------------------------------------------------

    def perform_miracle(self, god: God, miracle_type: str, target: str,
                        game_time: float, sim):
        """Execute a miracle. Costs miracle_points. Applies game effects."""
        if miracle_type not in MIRACLES:
            return
        miracle_data = MIRACLES[miracle_type]
        cost = miracle_data["cost"]
        effect = miracle_data["effect"]

        if god.miracle_points < cost:
            return

        god.miracle_points -= cost

        # Generate description
        description = self._get_miracle_description(god, miracle_type, target)

        # Apply game effect
        effect_applied = self._apply_miracle_effect(effect, target, god, sim)

        # Log the miracle
        miracle_record = {
            "god": god.name,
            "type": miracle_type,
            "target": target,
            "description": description,
            "effect_applied": effect_applied,
            "game_time": game_time,
            "timestamp": time.time(),
        }
        god.miracles_performed.append(miracle_record)
        # Cap log size
        if len(god.miracles_performed) > 100:
            god.miracles_performed = god.miracles_performed[-100:]

        self.event_log.append(f"[DIVINE] {description}")

        # Improve opinion of target
        current = god.opinions.get(target, 0)
        god.opinions[target] = min(100, current + 10)

    def _get_miracle_description(self, god: God, miracle_type: str,
                                  target: str) -> str:
        """Generate a miracle description. Uses LLM if available."""
        effect = MIRACLES[miracle_type]["effect"]

        # Try LLM if available and enabled
        if self.llm and getattr(self.llm, 'enabled', False):
            prompt = (
                f"In one evocative sentence, describe the god {god.name} "
                f"(sphere: {god.sphere}) performing a '{miracle_type}' miracle "
                f"on {target}. Be dramatic but brief."
            )
            result = self.llm.request(
                f"miracle_{god.name}_{target}_{time.time():.0f}",
                prompt, max_tokens=60, priority=0
            )
            if result:
                return result

        # Rule-based fallback
        templates = MIRACLE_DESCRIPTIONS.get(effect, [
            f"{god.name} intervenes on behalf of {{target}}."
        ])
        template = random.choice(templates)
        return template.format(god=god.name, target=target)

    def _apply_miracle_effect(self, effect: str, target: str, god: God,
                               sim) -> bool:
        """Apply the actual game effect of a miracle. Returns True if applied."""
        npcs = getattr(sim, 'world_mgr', None)
        if npcs:
            npcs = getattr(npcs, 'npcs', [])
        else:
            npcs = []

        if effect == "restore_hp":
            for npc in npcs:
                if npc.name == target and getattr(npc, 'alive', True):
                    heal_amount = int(npc.max_hp * 0.5)
                    npc.hp = min(npc.max_hp, npc.hp + heal_amount)
                    npc.mood = min(1.0, getattr(npc, 'mood', 0) + 0.5)
                    return True

        elif effect == "shield_settlement":
            # Boost morale of all NPCs near the target NPC
            target_npc = None
            for npc in npcs:
                if npc.name == target:
                    target_npc = npc
                    break
            if target_npc:
                for npc in npcs:
                    if not getattr(npc, 'alive', True):
                        continue
                    dx = npc.x - target_npc.x
                    dy = npc.y - target_npc.y
                    if dx * dx + dy * dy < 30 * 30:
                        npc.hp = min(npc.max_hp, npc.hp + 5)
                        npc.mood = min(1.0, getattr(npc, 'mood', 0) + 0.2)
                return True

        elif effect == "damage_target":
            for npc in npcs:
                if npc.name == target and getattr(npc, 'alive', True):
                    damage = max(5, int(npc.max_hp * 0.3))
                    npc.hp = max(0, npc.hp - damage)
                    npc.mood = max(-1.0, getattr(npc, 'mood', 0) - 0.5)
                    return True
            # Also check creatures
            creatures = getattr(getattr(sim, 'world_mgr', None), 'creatures', [])
            for c in creatures:
                if getattr(c, 'name', '') == target and getattr(c, 'alive', True):
                    c.hp = max(0, c.hp - int(c.max_hp * 0.3))
                    return True

        elif effect == "boost_crops":
            # Boost food needs of NPCs near target
            target_npc = None
            for npc in npcs:
                if npc.name == target:
                    target_npc = npc
                    break
            if target_npc:
                for npc in npcs:
                    if not getattr(npc, 'alive', True):
                        continue
                    dx = npc.x - target_npc.x
                    dy = npc.y - target_npc.y
                    if dx * dx + dy * dy < 40 * 40:
                        npc.needs["hunger"] = min(100, npc.needs.get("hunger", 50) + 30)
                return True

        elif effect == "boost_morale":
            for npc in npcs:
                if npc.name == target and getattr(npc, 'alive', True):
                    npc.mood = min(1.0, getattr(npc, 'mood', 0) + 0.6)
                    npc.needs["social"] = min(100, npc.needs.get("social", 50) + 25)
                    return True

        elif effect == "debuff_target":
            for npc in npcs:
                if npc.name == target and getattr(npc, 'alive', True):
                    npc.mood = max(-1.0, getattr(npc, 'mood', 0) - 0.4)
                    # Drain all needs slightly
                    for need in npc.needs:
                        npc.needs[need] = max(0, npc.needs[need] - 15)
                    return True

        elif effect == "reveal_info":
            for npc in npcs:
                if npc.name == target and getattr(npc, 'alive', True):
                    if hasattr(npc, 'add_memory'):
                        npc.add_memory("divine", f"{god.name} granted a vision", 4)
                    npc.mood = min(1.0, getattr(npc, 'mood', 0) + 0.3)
                    return True

        elif effect == "revive_npc":
            # Look in dead NPCs list
            dead_list = getattr(sim, 'dead_npcs', [])
            for i, dead_info in enumerate(dead_list):
                dead_name = dead_info.get("name", "") if isinstance(dead_info, dict) else ""
                if dead_name == target:
                    # Find the NPC object and revive
                    for npc in npcs:
                        if npc.name == target:
                            npc.alive = True
                            npc.hp = npc.max_hp // 2
                            npc.mood = 0.5
                            dead_list.pop(i)
                            return True
                    break

        elif effect == "disease_settlement":
            # Damage NPCs near target
            target_npc = None
            for npc in npcs:
                if npc.name == target:
                    target_npc = npc
                    break
            if target_npc:
                for npc in npcs:
                    if not getattr(npc, 'alive', True):
                        continue
                    dx = npc.x - target_npc.x
                    dy = npc.y - target_npc.y
                    if dx * dx + dy * dy < 40 * 40:
                        npc.hp = max(1, npc.hp - 5)
                        npc.mood = max(-1.0, getattr(npc, 'mood', 0) - 0.3)
                return True

        elif effect == "grant_gold":
            for npc in npcs:
                if npc.name == target and getattr(npc, 'alive', True):
                    gold = random.randint(10, 30)
                    npc.npc_gold = getattr(npc, 'npc_gold', 0) + gold
                    npc.mood = min(1.0, getattr(npc, 'mood', 0) + 0.3)
                    return True

        return False

    # ----------------------------------------------------------------
    # PROACTIVE INTERVENTIONS
    # ----------------------------------------------------------------

    def _consider_interventions(self, game_time: float, sim):
        """Gods proactively intervene when they see something they care about."""
        self._miracle_timer += 1
        if self._miracle_timer < 3:  # only every 3rd call (~90s)
            return
        self._miracle_timer = 0

        npcs = getattr(getattr(sim, 'world_mgr', None), 'npcs', [])
        if not npcs:
            return

        for god in self.gods.values():
            # Only intervene if god has enough points and is paying attention
            if god.miracle_points < 20 or not god.attention:
                continue

            # Very low chance of proactive intervention
            if random.random() > 0.10:
                continue

            # Pick intervention based on sphere
            if god.sphere == "war":
                # Find weakened warriors, smite enemies
                for npc in random.sample(npcs, min(10, len(npcs))):
                    if not getattr(npc, 'alive', True):
                        continue
                    hp_ratio = npc.hp / max(1, npc.max_hp)
                    title = getattr(npc, 'title', 'commoner')
                    if hp_ratio < 0.3 and title in ('guard', 'knight', 'captain'):
                        opinion = god.opinions.get(npc.name, 0)
                        if opinion >= -20:
                            self.perform_miracle(god, "protect", npc.name,
                                                 game_time, sim)
                            break

            elif god.sphere == "nature":
                # Bless hungry settlements
                for npc in random.sample(npcs, min(10, len(npcs))):
                    if not getattr(npc, 'alive', True):
                        continue
                    if npc.needs.get("hunger", 50) < 25:
                        self.perform_miracle(god, "bless_harvest", npc.name,
                                             game_time, sim)
                        break

            elif god.sphere == "love":
                # Heal the wounded
                for npc in random.sample(npcs, min(10, len(npcs))):
                    if not getattr(npc, 'alive', True):
                        continue
                    if npc.hp < npc.max_hp * 0.3:
                        self.perform_miracle(god, "heal", npc.name,
                                             game_time, sim)
                        break

            elif god.sphere == "commerce":
                # Grant fortune to the destitute
                for npc in random.sample(npcs, min(10, len(npcs))):
                    if not getattr(npc, 'alive', True):
                        continue
                    if getattr(npc, 'npc_gold', 0) < 3:
                        self.perform_miracle(god, "fortune", npc.name,
                                             game_time, sim)
                        break

            elif god.sphere == "knowledge":
                # Reveal info to scholars
                for npc in random.sample(npcs, min(10, len(npcs))):
                    if not getattr(npc, 'alive', True):
                        continue
                    prof = getattr(npc, 'profession', '')
                    if prof in ('Wizard', 'Scholar', 'Sage', 'Librarian'):
                        self.perform_miracle(god, "reveal", npc.name,
                                             game_time, sim)
                        break

            elif god.sphere == "chaos":
                # Random mischief
                target = random.choice(npcs)
                if getattr(target, 'alive', True):
                    miracle = random.choice(["fortune", "curse", "inspire"])
                    if miracle in MIRACLES and god.sphere in MIRACLES[miracle]["spheres"]:
                        if god.miracle_points >= MIRACLES[miracle]["cost"]:
                            self.perform_miracle(god, miracle, target.name,
                                                 game_time, sim)

            elif god.sphere == "death":
                # Curse the wicked (low opinion NPCs)
                worst = None
                worst_opinion = 0
                for name, opinion in god.opinions.items():
                    if opinion < worst_opinion:
                        worst = name
                        worst_opinion = opinion
                if worst and worst_opinion < -30:
                    self.perform_miracle(god, "curse", worst, game_time, sim)

    # ----------------------------------------------------------------
    # DIVINE COMPETITION
    # ----------------------------------------------------------------

    def _divine_competition(self, dt: float):
        """Inter-god dynamics: alliances and rivalries evolve."""
        god_list = list(self.gods.values())
        if len(god_list) < 2:
            return

        # Occasionally shift relationships
        if random.random() > 0.1:
            return

        g1, g2 = random.sample(god_list, 2)

        # Opposing alignments drift apart, similar drift together
        alignment_diff = abs(g1.alignment - g2.alignment)
        drift = random.uniform(-2, 2)
        if alignment_diff > 1.0:
            drift -= 1  # opposing alignments
        elif alignment_diff < 0.5:
            drift += 1  # similar alignments

        # Sphere conflicts
        conflicts = {
            ("war", "love"): -2,
            ("death", "love"): -2,
            ("death", "nature"): -1,
            ("chaos", "knowledge"): -1,
            ("nature", "commerce"): -1,
        }
        pair = (g1.sphere, g2.sphere)
        reverse_pair = (g2.sphere, g1.sphere)
        conflict_mod = conflicts.get(pair, conflicts.get(reverse_pair, 0))
        drift += conflict_mod

        # Worshipper competition: more worshippers = more friction
        if g1.worshippers > 20 and g2.worshippers > 20:
            drift -= 0.5

        g1.relationships[g2.name] = max(-100, min(100,
            g1.relationships.get(g2.name, 0) + drift))
        g2.relationships[g1.name] = max(-100, min(100,
            g2.relationships.get(g1.name, 0) + drift))

    # ----------------------------------------------------------------
    # PETITIONS TO HIGHER POWER
    # ----------------------------------------------------------------

    def _consider_petitions(self, game_time: float, sim):
        """Gods evaluate world state and may compose petitions to the creator."""
        self._petition_timer += 1
        if self._petition_timer < 5:  # every 5th call (~150s)
            return
        self._petition_timer = 0

        npcs = getattr(getattr(sim, 'world_mgr', None), 'npcs', [])
        governance = getattr(sim, 'governance', None)

        # Count world statistics
        alive_count = sum(1 for n in npcs if getattr(n, 'alive', True))
        dead_count = sum(1 for n in npcs if not getattr(n, 'alive', True))
        total = alive_count + dead_count
        death_ratio = dead_count / max(1, total)

        # Check kingdoms for dominance
        kingdoms = {}
        if governance:
            kingdoms = getattr(governance, 'kingdoms', {})

        dominant_kingdom = None
        if kingdoms:
            sorted_k = sorted(kingdoms.values(),
                               key=lambda k: getattr(k, 'population', 0),
                               reverse=True)
            if len(sorted_k) >= 2:
                top_pop = getattr(sorted_k[0], 'population', 0)
                second_pop = getattr(sorted_k[1], 'population', 0)
                if top_pop > second_pop * 3 and top_pop > 20:
                    dominant_kingdom = sorted_k[0].name

        # Check economy health
        avg_gold = 0
        if npcs:
            gold_total = sum(getattr(n, 'npc_gold', 0) for n in npcs
                             if getattr(n, 'alive', True))
            avg_gold = gold_total / max(1, alive_count)

        # Count days without war
        war_happening = False
        if governance:
            for rel in getattr(governance, 'diplomacy', {}).values():
                if getattr(rel, 'status', '') == 'at_war':
                    war_happening = True
                    break

        day = getattr(getattr(sim, 'time_sys', None), 'day', 0)

        # Each god evaluates based on their sphere
        for god in self.gods.values():
            petition = None

            if god.sphere == "death" and death_ratio > 0.5:
                petition = {
                    "god_name": god.name,
                    "text": "Too many souls crowd the underworld. "
                            "The living grow scarce.",
                    "suggestion": "Reduce death rate or grant more souls to "
                                  "sustain life.",
                    "urgency": min(10, int(death_ratio * 15)),
                    "timestamp": game_time,
                }

            elif god.sphere == "death" and death_ratio < 0.05 and alive_count > 50:
                petition = {
                    "god_name": god.name,
                    "text": "Death has been cheated. The natural cycle is "
                            "disrupted.",
                    "suggestion": "Allow mortality to restore balance.",
                    "urgency": 3,
                    "timestamp": game_time,
                }

            elif god.sphere == "war" and dominant_kingdom:
                petition = {
                    "god_name": god.name,
                    "text": f"The balance of power has been lost. "
                            f"{dominant_kingdom} dominates all others.",
                    "suggestion": "Weaken the dominant power or strengthen "
                                  "their rivals.",
                    "urgency": 6,
                    "timestamp": game_time,
                }

            elif god.sphere == "chaos" and not war_happening and day > 100:
                petition = {
                    "god_name": god.name,
                    "text": "Stagnation breeds rot. The world grows complacent.",
                    "suggestion": "Introduce conflict or disaster to shake "
                                  "things up.",
                    "urgency": 4,
                    "timestamp": game_time,
                }

            elif god.sphere == "commerce" and avg_gold < 5 and alive_count > 10:
                petition = {
                    "god_name": god.name,
                    "text": "Trade routes wither. The economy is broken and "
                            "the people starve for coin.",
                    "suggestion": "Inject gold or create trade opportunities.",
                    "urgency": 7,
                    "timestamp": game_time,
                }

            elif god.sphere == "nature" and alive_count < 20 and total > 30:
                petition = {
                    "god_name": god.name,
                    "text": "The world grows barren. Life fades from the land.",
                    "suggestion": "Restore ecological balance and nurture "
                                  "new growth.",
                    "urgency": 8,
                    "timestamp": game_time,
                }

            elif god.sphere == "love" and alive_count > 30:
                # Check average mood
                avg_mood = sum(getattr(n, 'mood', 0) for n in npcs
                               if getattr(n, 'alive', True)) / max(1, alive_count)
                if avg_mood < -0.3:
                    petition = {
                        "god_name": god.name,
                        "text": "The hearts of mortals are heavy with despair. "
                                "Joy has fled the world.",
                        "suggestion": "Trigger festivals or grant blessings "
                                      "to restore hope.",
                        "urgency": 5,
                        "timestamp": game_time,
                    }

            elif god.sphere == "knowledge" and alive_count > 20:
                # Petition if technology seems stagnant
                tech = getattr(sim, 'technology', None)
                if tech:
                    total_techs = len(getattr(tech, 'researched', set()))
                    if total_techs < 3 and day > 50:
                        petition = {
                            "god_name": god.name,
                            "text": "Knowledge stagnates. The mortals have "
                                    "not sought understanding.",
                            "suggestion": "Encourage research and discovery.",
                            "urgency": 4,
                            "timestamp": game_time,
                        }

            if petition is not None:
                # Use LLM to enhance petition text if available
                if self.llm and getattr(self.llm, 'enabled', False):
                    prompt = (
                        f"Rewrite this divine petition from {god.name} "
                        f"(god of {god.sphere}) in a more poetic, "
                        f"dramatic style. Keep it to 2 sentences max.\n"
                        f"Original: {petition['text']}"
                    )
                    result = self.llm.request(
                        f"petition_{god.name}_{time.time():.0f}",
                        prompt, max_tokens=80, priority=0
                    )
                    if result:
                        petition["text"] = result

                god.petitions_to_higher_power.append(petition)
                # Cap petition log
                if len(god.petitions_to_higher_power) > 20:
                    god.petitions_to_higher_power = \
                        god.petitions_to_higher_power[-20:]

                self.event_log.append(
                    f"[PETITION] {god.name}: {petition['text']}")

    # ----------------------------------------------------------------
    # NPC PRAYER TRIGGERS (called from emotion system)
    # ----------------------------------------------------------------

    def trigger_npc_prayers(self, npcs: list, game_time: float,
                            heresy=None):
        """Check if any NPCs should pray based on their emotional state.

        Called periodically from the simulation update loop.
        """
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue

            # Atheists don't pray
            npc_name = getattr(npc, 'name', '')
            if heresy and heresy.is_atheist(npc_name):
                continue

            # Very low chance per tick to avoid spam
            if random.random() > 0.02:
                continue

            prayer_text = None
            god_name = None
            intensity = 0.5

            # Fear triggers prayer
            es = getattr(npc, 'emotion_state', None)
            fear_level = 0
            if es and hasattr(es, 'primary'):
                fear_level = es.primary.get('fear', 0)
            elif es and isinstance(es, str) and es == 'afraid':
                fear_level = 0.7

            if fear_level > 0.5:
                god_name = self._pick_god_for_npc(npc, ["war", "love", "nature"])
                prayer_text = f"Grant me protection from danger"
                intensity = min(1.0, fear_level)

            # Low HP triggers prayer
            elif npc.hp < npc.max_hp * 0.3:
                god_name = self._pick_god_for_npc(npc, ["love", "nature", "death"])
                prayer_text = f"Heal my wounds, I beg you"
                intensity = 0.8

            # Desperation (low needs)
            elif any(v < 20 for v in npc.needs.values()):
                worst_need = min(npc.needs, key=npc.needs.get)
                god_name = self._pick_god_for_npc(
                    npc, ["nature", "commerce", "love"])
                prayer_text = f"I am desperate for {worst_need}"
                intensity = 0.7

            # Gratitude (high mood)
            elif getattr(npc, 'mood', 0) > 0.7:
                god_name = self._pick_god_for_npc(npc, ["love", "nature"])
                prayer_text = "Thank you for your blessings"
                intensity = 0.3

            if prayer_text and god_name:
                self.receive_prayer(npc, god_name, prayer_text, intensity)

    def _pick_god_for_npc(self, npc, preferred_spheres: List[str]) -> str:
        """Pick which god an NPC prays to based on religion and sphere."""
        # Map NPC religion to gods
        religion = getattr(npc, 'religion', '')
        religion_gods = {
            "The Light": ["Lyria", "Tharion"],
            "The Old Gods": ["Sylvana", "Morwen"],
            "The Arcane Path": ["Verithos", "Xaotl"],
            "The Shadow": ["Xaotl", "Morwen"],
            "The Forge": ["Tharion", "Auriel"],
        }

        candidates = religion_gods.get(religion, [])

        # Filter to gods that exist in our pantheon
        candidates = [n for n in candidates if n in self.gods]

        # If no religion match, pick from preferred spheres
        if not candidates:
            for god in self.gods.values():
                if god.sphere in preferred_spheres:
                    candidates.append(god.name)

        if not candidates:
            candidates = list(self.gods.keys())

        return random.choice(candidates)

    # ----------------------------------------------------------------
    # WORSHIPPER COUNTING
    # ----------------------------------------------------------------

    def count_worshippers(self, npcs: list):
        """Count how many NPCs worship each god. Called periodically."""
        # Reset counts
        for god in self.gods.values():
            god.worshippers = 0

        religion_god_map = {
            "The Light": ["Lyria", "Tharion"],
            "The Old Gods": ["Sylvana", "Morwen"],
            "The Arcane Path": ["Verithos", "Xaotl"],
            "The Shadow": ["Xaotl", "Morwen"],
            "The Forge": ["Tharion", "Auriel"],
        }

        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            religion = getattr(npc, 'religion', '')
            god_names = religion_god_map.get(religion, [])
            for gn in god_names:
                if gn in self.gods:
                    self.gods[gn].worshippers += 1

    # ----------------------------------------------------------------
    # PUBLIC API
    # ----------------------------------------------------------------

    def get_petition_log(self) -> List[Dict]:
        """Get all pending petitions from gods to the game creator."""
        petitions = []
        for god in self.gods.values():
            petitions.extend(god.petitions_to_higher_power)
        petitions.sort(key=lambda p: p.get("urgency", 0), reverse=True)
        return petitions

    def get_event_log(self) -> List[str]:
        """Get and clear recent divine events."""
        msgs = list(self.event_log)
        self.event_log.clear()
        return msgs

    def get_pantheon_report(self) -> str:
        """Get a summary of all gods for display."""
        lines = []
        for god in self.gods.values():
            alignment_str = "evil" if god.alignment < -0.3 else \
                            "neutral" if god.alignment < 0.3 else "good"
            lines.append(
                f"{god.name} ({god.sphere}, {alignment_str}): "
                f"power={god.power:.1f}, mp={god.miracle_points:.0f}/"
                f"{god.max_miracle_points:.0f}, "
                f"worshippers={god.worshippers}, "
                f"miracles={len(god.miracles_performed)}"
            )

        # Petitions summary
        petitions = self.get_petition_log()
        if petitions:
            lines.append("")
            lines.append("=== Divine Petitions ===")
            for p in petitions[:5]:
                lines.append(
                    f"  [{p['god_name']}] (urgency {p['urgency']}): "
                    f"{p['text']}")

        return "\n".join(lines)
