"""
Children and Darwinian Inheritance System.

Manages the full child lifecycle:
- Pregnancy tracking (which NPC couples are expecting)
- Birth events with stat/skill/memory inheritance from parents
- Child growth and aging
- Parental care requirements (feeding, shelter)
- Orphan handling (relatives, settlement care, street urchins)
- Coming of age (child -> adult transition with profession choice)
- Family tree tracking with loyalty and grief mechanics

Most processing is event-driven (birth, death, coming-of-age) rather than
per-frame, keeping the tick lightweight.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from game.settings import NPC_SPEED, DAY_LENGTH


# ================================================================
# CONSTANTS
# ================================================================

GESTATION_DAYS = 30            # game-days until birth
COMING_OF_AGE = 16             # game-years until child becomes adult
NEGLECT_THRESHOLD_DAYS = 3     # days without food before health decline
NEGLECT_DEATH_DAYS = 7         # days without food -> child dies
CHILD_LEARNING_MULT = 2.0      # skill XP multiplier for children
CHILD_SPEED_MULT = 0.8         # children move slower
CHILD_HP_MULT = 0.5            # children have half HP
STAT_MUTATION_SIGMA = 0.15     # gaussian noise on inherited stats (fraction)
PERSONALITY_DRIFT_SIGMA = 0.1  # gaussian noise on inherited personality
STAT_MIN = 3                   # D&D-style stat floor
STAT_MAX = 18                  # D&D-style stat ceiling

# Weights for profession choice at coming-of-age
PROF_WEIGHT_PARENT = 0.40
PROF_WEIGHT_APTITUDE = 0.30
PROF_WEIGHT_SETTLEMENT = 0.30

# How many real-seconds map to one game-year for children
# Default aging: 1 year per ~5 real-minutes (matches demographics.py)
# Demographics ages 0.2 years per 60s check, so ~12 real-seconds per year.
# We do NOT age children here; demographics.py handles aging for all NPCs.

# Parent class weights for child profession (imported from population.py)
from game.systems.population import CHILD_CLASS_WEIGHTS


# ================================================================
# PREGNANCY
# ================================================================

@dataclass
class Pregnancy:
    """Tracks an active pregnancy between two NPCs."""
    mother_name: str
    father_name: str
    conception_time: float      # game_time when conceived
    due_time: float             # game_time when baby is due
    settlement_name: str        # where the birth should happen
    announced: bool = False     # whether parents have been notified


# ================================================================
# CHILD SYSTEM
# ================================================================

class ChildSystem:
    """Manages pregnancies, births, child growth, parental care, and coming of age."""

    def __init__(self):
        self.pregnancies: List[Pregnancy] = []
        self.children: List[str] = []  # names of current child NPCs
        self._pregnancy_timer = 0.0
        self._child_timer = 0.0
        self._coming_of_age_timer = 0.0
        self.event_log: List[str] = []

    # ------------------------------------------------------------------
    # Main update — called every simulation tick
    # ------------------------------------------------------------------

    def update(self, npcs: list, dt: float, game_time: float, world,
               demographics=None, population=None, world_effects=None):
        """Tick the child system.  Throttled internally for performance.

        Args:
            npcs: master NPC list (mutable — we append newborns)
            dt: real-time delta
            game_time: current game time in seconds
            world: world object (for walkability checks)
            demographics: DemographicsSystem (for family data)
            population: PopulationSystem (for settlement data)
            world_effects: WorldEffects (for settlement stores)
        """
        # Check for new pregnancies every 30 real-seconds
        self._pregnancy_timer += dt
        if self._pregnancy_timer >= 30.0:
            self._pregnancy_timer = 0.0
            self._check_new_pregnancies(npcs, game_time, demographics)

        # Advance pregnancies & deliver babies every 10 real-seconds
        self._child_timer += dt
        if self._child_timer >= 10.0:
            self._child_timer = 0.0
            self._advance_pregnancies(game_time, npcs, world, demographics,
                                      population, world_effects)
            self._update_children(npcs, dt * 10, game_time, demographics,
                                  world_effects)

        # Coming-of-age checks every 30 real-seconds
        self._coming_of_age_timer += dt
        if self._coming_of_age_timer >= 30.0:
            self._coming_of_age_timer = 0.0
            self._check_coming_of_age(npcs, game_time, demographics, population)

    # ------------------------------------------------------------------
    # Pregnancy detection
    # ------------------------------------------------------------------

    def _check_new_pregnancies(self, npcs: list, game_time: float,
                                demographics=None):
        """Detect married couples who should become pregnant."""
        # Build set of currently pregnant mothers to avoid duplicates
        pregnant_mothers = {p.mother_name for p in self.pregnancies}

        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue

            # Only adults in prime/young age can become pregnant
            age_cat = getattr(npc, 'age_category', 'prime')
            if age_cat not in ('young', 'prime'):
                continue

            # Check if NPC has a spouse via life_ledger
            ledger = getattr(npc, 'life_ledger', None)
            if not ledger:
                continue

            spouse_name = None
            for bond in getattr(ledger, 'bonds', {}).values():
                btype = bond.get('type', '') if isinstance(bond, dict) else getattr(bond, 'bond_type', '')
                if btype == 'spouse':
                    spouse_name = bond.get('name', '') if isinstance(bond, dict) else getattr(bond, 'other_name', '')
                    break

            if not spouse_name:
                continue

            # Skip if already pregnant
            if npc.name in pregnant_mothers or spouse_name in pregnant_mothers:
                continue

            # Check if spouse is alive and nearby
            spouse = None
            for other in npcs:
                if other.name == spouse_name and getattr(other, 'alive', True):
                    spouse = other
                    break
            if not spouse:
                continue

            # Only create pregnancy with small chance per check
            # (base ~2% per 30s check, boosted by food security)
            hunger = npc.needs.get('hunger', 50)
            chance = 0.02 * (hunger / 100.0)
            if random.random() > chance:
                continue

            # Determine mother/father (pick one deterministically by name sort)
            mother, father = (npc, spouse) if npc.name < spouse.name else (spouse, npc)

            # Find settlement
            settlement = (getattr(mother, 'home_settlement', '') or
                          getattr(mother, 'faction', '') or '')

            due_time = game_time + GESTATION_DAYS * DAY_LENGTH

            preg = Pregnancy(
                mother_name=mother.name,
                father_name=father.name,
                conception_time=game_time,
                due_time=due_time,
                settlement_name=settlement,
            )
            self.pregnancies.append(preg)

            # Notify parents
            mother.add_memory("family", f"Expecting a child with {father.name}!", 5)
            father.add_memory("family", f"Expecting a child with {mother.name}!", 5)
            mother.mood = min(1.0, getattr(mother, 'mood', 0) + 0.3)
            father.mood = min(1.0, getattr(father, 'mood', 0) + 0.3)

            self.event_log.append(
                f"{mother.name} and {father.name} are expecting a child!")

    # ------------------------------------------------------------------
    # Pregnancy advancement & birth
    # ------------------------------------------------------------------

    def _advance_pregnancies(self, game_time: float, npcs: list, world,
                              demographics, population, world_effects):
        """Check each pregnancy; deliver if due."""
        still_active = []
        for preg in self.pregnancies:
            if game_time < preg.due_time:
                still_active.append(preg)
                continue

            # Time to deliver!
            mother = self._find_npc(npcs, preg.mother_name)
            father = self._find_npc(npcs, preg.father_name)

            if not mother or not getattr(mother, 'alive', True):
                # Mother died during pregnancy — pregnancy lost
                self.event_log.append(
                    f"Pregnancy lost — {preg.mother_name} has died.")
                continue

            child = self._create_child(mother, father, npcs, world,
                                       preg.settlement_name, game_time,
                                       demographics, population)
            if child:
                npcs.append(child)
                self.children.append(child.name)

                # Update family data
                self._register_family(child, mother, father, npcs,
                                      demographics, game_time)

                # Joy for parents
                mother.add_memory("family",
                    f"Gave birth to {child.name}!", 5)
                mother.mood = min(1.0, getattr(mother, 'mood', 0) + 0.5)
                if father and getattr(father, 'alive', True):
                    father.add_memory("family",
                        f"My child {child.name} was born!", 5)
                    father.mood = min(1.0, getattr(father, 'mood', 0) + 0.5)

                # Record in life ledger
                from game.systems.memory import ensure_life_ledger
                m_ledger = ensure_life_ledger(mother)
                day = int(game_time / DAY_LENGTH)
                m_ledger.record_milestone("childbirth",
                    f"Gave birth to {child.name}", day,
                    preg.settlement_name)
                m_ledger.record_bond(child.name, "child", day,
                                     trust=100, notes="my child")
                if father and getattr(father, 'alive', True):
                    f_ledger = ensure_life_ledger(father)
                    f_ledger.record_milestone("childbirth",
                        f"My child {child.name} was born", day,
                        preg.settlement_name)
                    f_ledger.record_bond(child.name, "child", day,
                                         trust=100, notes="my child")

                # Update population stats
                if population and preg.settlement_name:
                    stats = population.settlements.get(preg.settlement_name)
                    if stats:
                        stats.births_today += 1
                        if hasattr(population, 'births_total'):
                            population.births_total = getattr(
                                population, 'births_total', 0) + 1

                if demographics:
                    demographics.births_total = getattr(
                        demographics, 'births_total', 0) + 1

                self.event_log.append(
                    f"{child.name} was born to {mother.name}"
                    f"{' and ' + father.name if father else ''}!")

        self.pregnancies = still_active

    # ------------------------------------------------------------------
    # Child creation with Darwinian inheritance
    # ------------------------------------------------------------------

    def _create_child(self, mother, father, npcs: list, world,
                      settlement_name: str, game_time: float,
                      demographics, population) -> Optional[object]:
        """Create a new child NPC with inherited stats, skills, and memories."""
        from game.core.npc import NPC
        from game.systems.population import CHILD_CLASS_WEIGHTS

        # --- Name ---
        name = self._generate_child_name(mother, father, npcs, population)

        # --- Race inheritance ---
        mother_race = getattr(mother, 'race', 'Human')
        if father and getattr(father, 'alive', True):
            father_race = getattr(father, 'race', 'Human')
            # Same race -> inherit; mixed -> pick one at random
            race = mother_race if mother_race == father_race else random.choice(
                [mother_race, father_race])
        else:
            race = mother_race

        # --- Class (determined at birth but mostly matters at coming-of-age) ---
        parent_class = getattr(mother, 'char_class', 'Fighter')
        weights = CHILD_CLASS_WEIGHTS.get(parent_class, {"Fighter": 20})
        if father:
            father_class = getattr(father, 'char_class', 'Fighter')
            father_weights = CHILD_CLASS_WEIGHTS.get(father_class,
                                                      {"Fighter": 20})
            # Merge weights
            for cls, w in father_weights.items():
                weights[cls] = weights.get(cls, 0) + w
        classes = list(weights.keys())
        w_vals = [weights[c] for c in classes]
        child_class = random.choices(classes, weights=w_vals, k=1)[0]

        # --- Place near mother ---
        cx = mother.x + random.uniform(-2, 2)
        cy = mother.y + random.uniform(-2, 2)

        # Create the base NPC (this gives random stats; we'll overwrite)
        child = NPC(cx, cy, name, child_class,
                    char_class=child_class, race=race, level=1)

        # --- Stat inheritance ---
        self._inherit_ability_scores(child, mother, father)

        # --- Personality inheritance ---
        self._inherit_personality(child, mother, father)

        # --- Skill inheritance ---
        self._inherit_skills(child, mother, father)

        # --- Memory inheritance ---
        self._inherit_memories(child, mother, father, game_time)

        # --- Child-specific properties ---
        child.is_child = True
        child.age = 0
        child.age_category = "child"
        child.parent_names = (mother.name,
                              father.name if father else None)
        child.growth_rate = 1.0  # configurable multiplier

        # Home
        child.home_x = mother.home_x
        child.home_y = mother.home_y
        child.home_settlement = getattr(mother, 'home_settlement', '')
        child.faction = getattr(mother, 'faction', '')

        # Weaker stats for children
        child.max_hp = max(5, int(child.max_hp * CHILD_HP_MULT))
        child.hp = child.max_hp
        child.speed = NPC_SPEED * CHILD_SPEED_MULT

        # Children can't fight
        child.npc_attack_damage = 1
        child.npc_defense = 0

        # Family bonds
        child.friends.append(mother.name)
        child.npc_relationships[mother.name] = 80
        mother.friends.append(child.name)
        mother.npc_relationships[child.name] = 80
        if father and getattr(father, 'alive', True):
            child.friends.append(father.name)
            child.npc_relationships[father.name] = 80
            father.friends.append(child.name)
            father.npc_relationships[child.name] = 80

        # Family dict for tree tracking
        child.family = {
            "mother": mother.name,
            "father": father.name if father else None,
            "children": [],
            "spouse": None,
            "siblings": [],
        }

        # Track neglect
        child._last_fed_time = game_time
        child._neglect_days = 0

        # Title
        child.title = "commoner"
        child.social_class = "child"

        return child

    # ------------------------------------------------------------------
    # Inheritance helpers
    # ------------------------------------------------------------------

    def _inherit_ability_scores(self, child, mother, father):
        """Inherit ability scores as weighted average of parents + mutation."""
        physical = ("strength", "dexterity", "constitution")
        mental = ("intelligence", "wisdom", "charisma")

        m_scores = getattr(mother, 'ability_scores', {})
        f_scores = getattr(father, 'ability_scores', {}) if father else m_scores

        new_scores = {}
        for attr in physical + mental:
            p1 = m_scores.get(attr, 10)
            p2 = f_scores.get(attr, 10)
            avg = (p1 + p2) / 2.0
            mutation = random.gauss(0, avg * STAT_MUTATION_SIGMA)
            new_scores[attr] = max(STAT_MIN, min(STAT_MAX,
                                                  int(round(avg + mutation))))

        child.ability_scores = new_scores

        # Recalculate derived attributes
        from game.data.dnd import ability_modifier
        child.attributes = {}
        for attr in ("strength", "dexterity", "constitution",
                     "intelligence", "wisdom", "charisma"):
            score = new_scores.get(attr, 10)
            child.attributes[attr] = max(1, min(10,
                                                 ability_modifier(score) + 5))
        child.attributes["perception"] = child.attributes["wisdom"]

        # Recalculate HP with new constitution
        from game.data.dnd import get_class_hp
        con_mod = ability_modifier(new_scores.get("constitution", 10))
        child.max_hp = get_class_hp(child.char_class, 1, con_mod)
        child.hp = child.max_hp

    def _inherit_personality(self, child, mother, father):
        """Blend parent personalities with random drift."""
        m_friend = getattr(mother, 'friendliness', 0.5)
        m_curio = getattr(mother, 'curiosity', 0.5)
        m_brave = getattr(mother, 'bravery', 0.5)

        if father:
            f_friend = getattr(father, 'friendliness', 0.5)
            f_curio = getattr(father, 'curiosity', 0.5)
            f_brave = getattr(father, 'bravery', 0.5)
        else:
            f_friend, f_curio, f_brave = m_friend, m_curio, m_brave

        child.friendliness = max(0.0, min(1.0,
            (m_friend + f_friend) / 2 + random.gauss(0, PERSONALITY_DRIFT_SIGMA)))
        child.curiosity = max(0.0, min(1.0,
            (m_curio + f_curio) / 2 + random.gauss(0, PERSONALITY_DRIFT_SIGMA)))
        child.bravery = max(0.0, min(1.0,
            (m_brave + f_brave) / 2 + random.gauss(0, PERSONALITY_DRIFT_SIGMA)))

        # Inherit some social traits from parents
        m_traits = set(getattr(mother, 'social_traits', []))
        f_traits = set(getattr(father, 'social_traits', []) if father else [])
        shared = list(m_traits & f_traits)
        unique = list((m_traits | f_traits) - set(shared))

        # Child gets all shared traits + randomly some unique ones
        child_traits = list(shared)
        for t in unique:
            if random.random() < 0.5:
                child_traits.append(t)

        # Ensure 2-3 traits
        if len(child_traits) < 2:
            from game.systems.social import PERSONALITY_TRAITS
            extras = [t for t in PERSONALITY_TRAITS if t not in child_traits]
            while len(child_traits) < 2 and extras:
                child_traits.append(random.choice(extras))
                extras = [t for t in extras if t not in child_traits]
        elif len(child_traits) > 3:
            child_traits = random.sample(child_traits, 3)

        child.social_traits = child_traits

    def _inherit_skills(self, child, mother, father):
        """Give child aptitude bonuses in parent professions/skills."""
        m_skills = getattr(mother, 'npc_skills', {})
        f_skills = getattr(father, 'npc_skills', {}) if father else {}

        child_skills = {}
        all_skills = set(m_skills.keys()) | set(f_skills.keys())

        for skill in all_skills:
            m_level = m_skills.get(skill, 0)
            f_level = f_skills.get(skill, 0)

            if m_level > 0 and f_level > 0:
                # Both parents share this skill: +2 aptitude
                child_skills[skill] = 2
            elif m_level > 0 or f_level > 0:
                # Only one parent has it: +1 aptitude
                child_skills[skill] = 1

        # Everyone gets basic cooking/farming
        child_skills.setdefault("cooking", 1)
        child_skills.setdefault("farming", 1)

        child.npc_skills = child_skills

    def _inherit_memories(self, child, mother, father, game_time: float):
        """Pass 1-2 key memories from each parent as founding stories."""
        import time as _time

        def _get_intense_memories(npc, count=2):
            """Select the most emotionally intense memories from an NPC."""
            memories = getattr(npc, 'memories', [])
            if not memories:
                return []
            # Sort by importance (highest first)
            scored = sorted(memories,
                           key=lambda m: m.get('importance', 0),
                           reverse=True)
            return scored[:count]

        stories = []

        mother_mems = _get_intense_memories(mother, 2)
        for mem in mother_mems:
            text = mem.get('text', '')
            if text:
                stories.append({
                    "time": _time.time(),
                    "type": "inherited_story",
                    "text": f"My mother {mother.name} told me: {text}",
                    "importance": max(1, mem.get('importance', 1) - 1),
                })

        if father and getattr(father, 'alive', True):
            father_mems = _get_intense_memories(father, 2)
            for mem in father_mems:
                text = mem.get('text', '')
                if text:
                    stories.append({
                        "time": _time.time(),
                        "type": "inherited_story",
                        "text": f"My father {father.name} told me: {text}",
                        "importance": max(1, mem.get('importance', 1) - 1),
                    })

        # Add birth memory
        stories.append({
            "time": _time.time(),
            "type": "life",
            "text": f"I was born to {mother.name}"
                    f"{' and ' + father.name if father else ''}.",
            "importance": 5,
        })

        child.memories = stories

    # ------------------------------------------------------------------
    # Child updates (care, neglect, health)
    # ------------------------------------------------------------------

    def _update_children(self, npcs: list, dt: float, game_time: float,
                         demographics, world_effects):
        """Check child welfare: feeding, neglect, health decline."""
        still_children = []
        day_seconds = DAY_LENGTH

        for child_name in self.children:
            child = self._find_npc(npcs, child_name)
            if not child or not getattr(child, 'alive', True):
                continue
            if not getattr(child, 'is_child', False):
                continue  # already came of age

            still_children.append(child_name)

            # --- Parental feeding ---
            # Check if a parent is alive and has food
            parent_names = getattr(child, 'parent_names', (None, None))
            fed = False
            for pname in parent_names:
                if not pname:
                    continue
                parent = self._find_npc(npcs, pname)
                if not parent or not getattr(parent, 'alive', True):
                    continue

                # Parent shares food with child if child is hungry
                if child.needs.get('hunger', 100) < 50:
                    if parent.has_food():
                        parent.consume_food()  # parent's food goes to child
                        child.needs['hunger'] = min(100,
                            child.needs.get('hunger', 0) + 30)
                        child._last_fed_time = game_time
                        fed = True
                        break
                    # Try settlement stores
                    settlement = getattr(child, 'home_settlement', '')
                    if settlement and world_effects:
                        stores = None
                        if hasattr(world_effects, 'get_stores_ref'):
                            stores = world_effects.get_stores_ref(settlement)
                        if stores and stores.get('food', 0) >= 1:
                            stores['food'] = max(0, stores['food'] - 1)
                            child.needs['hunger'] = min(100,
                                child.needs.get('hunger', 0) + 25)
                            child._last_fed_time = game_time
                            fed = True
                            break
                else:
                    fed = True  # not hungry, counts as fed
                    break

            # --- Neglect tracking ---
            if not fed and child.needs.get('hunger', 100) < 30:
                days_since_fed = (game_time - getattr(child, '_last_fed_time',
                                                       game_time)) / day_seconds
                child._neglect_days = days_since_fed

                if days_since_fed >= NEGLECT_DEATH_DAYS:
                    # Child dies of neglect
                    child.alive = False
                    child.hp = 0
                    self.event_log.append(
                        f"{child.name} died of neglect (no food for "
                        f"{int(days_since_fed)} days).")
                    self._trigger_grief(child, npcs)
                    continue
                elif days_since_fed >= NEGLECT_THRESHOLD_DAYS:
                    # Health declines
                    damage = 1 + int(days_since_fed - NEGLECT_THRESHOLD_DAYS)
                    child.hp = max(0, child.hp - damage)
                    if child.hp <= 0:
                        child.alive = False
                        self.event_log.append(
                            f"{child.name} died of starvation.")
                        self._trigger_grief(child, npcs)
                        continue

            # --- Orphan handling ---
            self._check_orphan(child, npcs, demographics, game_time)

        self.children = still_children

    def _check_orphan(self, child, npcs: list, demographics, game_time: float):
        """Handle orphans: find relatives or settlement care, else street urchin."""
        parent_names = getattr(child, 'parent_names', (None, None))
        has_living_parent = False
        for pname in parent_names:
            if pname:
                parent = self._find_npc(npcs, pname)
                if parent and getattr(parent, 'alive', True):
                    has_living_parent = True
                    break

        if has_living_parent:
            return  # not an orphan

        # Already tagged as orphan?
        if getattr(child, '_is_orphan', False):
            return

        child._is_orphan = True
        child.add_memory("life",
            "Both my parents have died. I am alone.", 5)

        # Try to find a relative in settlement
        if demographics:
            fid = demographics.npc_families.get(child.name)
            if fid and fid in demographics.families:
                family = demographics.families[fid]
                for member_name in family.members:
                    if member_name == child.name:
                        continue
                    guardian = self._find_npc(npcs, member_name)
                    if guardian and getattr(guardian, 'alive', True):
                        # Found a relative — they take over
                        child.parent_names = (guardian.name, None)
                        child._is_orphan = False
                        child.add_memory("family",
                            f"{guardian.name} took me in after my parents died.", 4)
                        guardian.add_memory("family",
                            f"Took in orphan {child.name}.", 4)
                        self.event_log.append(
                            f"{guardian.name} adopted orphan {child.name}.")
                        return

        # No relatives — settlement care (if settlement exists)
        settlement = getattr(child, 'home_settlement', '')
        if settlement:
            child.add_memory("life",
                f"The people of {settlement} are looking after me.", 3)
            self.event_log.append(
                f"{child.name} is now a ward of {settlement}.")
            return

        # No settlement, no relatives — street urchin
        child.profession = "Street Urchin"
        child.char_class = "Rogue"
        child.title = "commoner"
        child.add_memory("life",
            "I have no one. I must survive on my own.", 5)
        self.event_log.append(
            f"{child.name} became a street urchin.")

    # ------------------------------------------------------------------
    # Coming of age
    # ------------------------------------------------------------------

    def _check_coming_of_age(self, npcs: list, game_time: float,
                              demographics, population):
        """Transition children to adults when they reach COMING_OF_AGE."""
        aged_up = []
        for child_name in list(self.children):
            child = self._find_npc(npcs, child_name)
            if not child or not getattr(child, 'alive', True):
                aged_up.append(child_name)
                continue
            if not getattr(child, 'is_child', False):
                aged_up.append(child_name)
                continue

            age = getattr(child, 'age', 0)
            threshold = COMING_OF_AGE * getattr(child, 'growth_rate', 1.0)
            # For long-lived races, scale threshold
            max_age = getattr(child, 'max_age', 80)
            if max_age > 100:
                # Scale proportionally (e.g. elf child for longer)
                from game.systems.demographics import RACE_LIFESPAN
                human_lifespan = RACE_LIFESPAN.get('Human', 80)
                ratio = max_age / human_lifespan
                threshold = COMING_OF_AGE * ratio * getattr(child, 'growth_rate', 1.0)

            if age < threshold:
                continue

            # --- Come of age! ---
            aged_up.append(child_name)
            child.is_child = False
            child.age_category = "young"
            child.social_class = "freeman"

            # Restore adult stats
            from game.data.dnd import ability_modifier, get_class_hp
            con_mod = ability_modifier(
                child.ability_scores.get("constitution", 10))
            child.max_hp = get_class_hp(child.char_class, 1, con_mod)
            child.hp = child.max_hp
            child.speed = NPC_SPEED

            # Choose profession
            profession = self._choose_profession(child, npcs, population)
            child.profession = profession

            # Re-initialize skills with adult skill system (keeps aptitude)
            from game.systems.skills import initialize_npc_skills
            old_skills = dict(getattr(child, 'npc_skills', {}))
            initialize_npc_skills(child)
            # Add back inherited aptitude on top
            for skill, level in old_skills.items():
                current = child.npc_skills.get(skill, 0)
                child.npc_skills[skill] = max(current, level)

            # Apply physical stats
            from game.systems.physical import apply_physical_stats
            apply_physical_stats(child)

            # May leave home if high openness (curiosity)
            if getattr(child, 'curiosity', 0.5) > 0.75:
                child.add_memory("life",
                    "I feel the call of adventure. Perhaps I should explore the world.", 4)
                child.long_term_goals.append("Explore the world beyond home")

            child.add_memory("life",
                f"I have come of age and chosen to become a {profession}.", 5)
            self.event_log.append(
                f"{child.name} has come of age as a {profession}!")

            # Notify parents
            for pname in getattr(child, 'parent_names', ()):
                if pname:
                    parent = self._find_npc(npcs, pname)
                    if parent and getattr(parent, 'alive', True):
                        parent.add_memory("family",
                            f"My child {child.name} has come of age as a {profession}!", 4)

        # Remove aged-up children from tracking list
        for name in aged_up:
            if name in self.children:
                self.children.remove(name)

    def _choose_profession(self, child, npcs: list, population) -> str:
        """Choose profession based on parent profession, aptitude, and settlement needs."""
        from game.systems.population import CHILD_CLASS_WEIGHTS

        parent_names = getattr(child, 'parent_names', (None, None))
        parent_profs = []
        for pname in parent_names:
            if pname:
                parent = self._find_npc(npcs, pname)
                if parent:
                    prof = getattr(parent, 'profession', '') or getattr(parent, 'char_class', '')
                    if prof:
                        parent_profs.append(prof)

        # Build candidate list with scores
        from game.systems.npc_lifecycle import CLASS_DAILY_WAGE
        candidates = {}

        # Parent influence (40%)
        for prof in parent_profs:
            candidates[prof] = candidates.get(prof, 0) + PROF_WEIGHT_PARENT

        # Aptitude based on skills (30%)
        skills = getattr(child, 'npc_skills', {})
        # Map top skills to professions
        _skill_to_prof = {
            "swordsmanship": "Fighter", "archery": "Ranger",
            "farming": "Farmer", "smithing": "Blacksmith",
            "cooking": "Baker", "medicine": "Healer",
            "performance": "Bard", "trading": "Merchant",
            "herbalism": "Herbalist", "mining": "Miner",
            "hunting": "Hunter", "woodcraft": "Woodcutter",
            "fishing": "Fisherman", "alchemy": "Alchemist",
            "masonry": "Mason", "carpentry": "Carpenter",
        }
        for skill, level in sorted(skills.items(), key=lambda x: -x[1])[:3]:
            prof = _skill_to_prof.get(skill)
            if prof:
                candidates[prof] = candidates.get(prof, 0) + PROF_WEIGHT_APTITUDE * (level / 5.0)

        # Settlement needs (30%)
        settlement = getattr(child, 'home_settlement', '')
        if settlement and population:
            stats = population.settlements.get(settlement)
            if stats:
                # Low food -> farmer/hunter needed
                if stats.food_security < 40:
                    for p in ("Farmer", "Hunter", "Fisherman"):
                        candidates[p] = candidates.get(p, 0) + PROF_WEIGHT_SETTLEMENT
                # Low safety -> fighter/guard needed
                if stats.safety < 50:
                    for p in ("Fighter", "Ranger"):
                        candidates[p] = candidates.get(p, 0) + PROF_WEIGHT_SETTLEMENT

        # Fall back to char_class if no candidates
        if not candidates:
            return getattr(child, 'char_class', 'Fighter')

        # Weighted random choice
        profs = list(candidates.keys())
        weights = [candidates[p] for p in profs]
        return random.choices(profs, weights=weights, k=1)[0]

    # ------------------------------------------------------------------
    # Family tree management
    # ------------------------------------------------------------------

    def _register_family(self, child, mother, father, npcs: list,
                         demographics, game_time: float):
        """Register child in family structures and find siblings."""
        # Ensure family dicts exist on parents
        if not hasattr(mother, 'family') or mother.family is None:
            mother.family = {
                "mother": None, "father": None,
                "children": [], "spouse": None, "siblings": [],
            }
        mother.family.setdefault("children", []).append(child.name)

        if father and getattr(father, 'alive', True):
            if not hasattr(father, 'family') or father.family is None:
                father.family = {
                    "mother": None, "father": None,
                    "children": [], "spouse": None, "siblings": [],
                }
            father.family.setdefault("children", []).append(child.name)

        # Find siblings (other children of same parents)
        siblings = []
        for name in mother.family.get("children", []):
            if name != child.name:
                siblings.append(name)
        child.family["siblings"] = siblings

        # Update sibling lists on existing siblings
        for sib_name in siblings:
            sib = self._find_npc(npcs, sib_name)
            if sib and hasattr(sib, 'family'):
                sib.family.setdefault("siblings", [])
                if child.name not in sib.family["siblings"]:
                    sib.family["siblings"].append(child.name)
                # Siblings get trust bonus
                sib.npc_relationships[child.name] = sib.npc_relationships.get(
                    child.name, 0) + 40
                child.npc_relationships[sib_name] = child.npc_relationships.get(
                    sib_name, 0) + 40

        # Register in demographics family system
        if demographics:
            # Try to add to mother's family
            fid = demographics.npc_families.get(mother.name)
            if fid and fid in demographics.families:
                demographics.families[fid].add_member(child.name)
                demographics.npc_families[child.name] = fid
            else:
                # Create new family
                surname = "Unknown"
                for f in demographics.families.values():
                    if mother.name in f.members:
                        surname = f.surname
                        break
                new_fid = f"family_{surname}_{len(demographics.families)}"
                from game.systems.demographics import Family
                family = Family(new_fid, surname)
                family.add_member(child.name)
                family.add_member(mother.name)
                if father:
                    family.add_member(father.name)
                demographics.families[new_fid] = family
                demographics.npc_families[child.name] = new_fid

    def ensure_family_dict(self, npc):
        """Ensure an NPC has a family dict for tree tracking."""
        if not hasattr(npc, 'family') or npc.family is None:
            npc.family = {
                "mother": None,
                "father": None,
                "children": [],
                "spouse": None,
                "siblings": [],
            }
        return npc.family

    # ------------------------------------------------------------------
    # Grief and emotion
    # ------------------------------------------------------------------

    def _trigger_grief(self, dead_npc, npcs: list):
        """Trigger grief in family members when a family member dies."""
        family = getattr(dead_npc, 'family', None)
        if not family:
            return

        relatives = set()
        if family.get("mother"):
            relatives.add(family["mother"])
        if family.get("father"):
            relatives.add(family["father"])
        for sib in family.get("siblings", []):
            relatives.add(sib)
        for ch in family.get("children", []):
            relatives.add(ch)
        if family.get("spouse"):
            relatives.add(family["spouse"])

        for rel_name in relatives:
            rel = self._find_npc(npcs, rel_name)
            if rel and getattr(rel, 'alive', True):
                rel.add_memory("grief",
                    f"My family member {dead_npc.name} has died.", 5)
                rel.mood = max(-1.0, getattr(rel, 'mood', 0) - 0.6)

    def trigger_family_grief(self, dead_npc, npcs: list):
        """Public API for other systems to trigger grief on family death."""
        self._trigger_grief(dead_npc, npcs)

    # ------------------------------------------------------------------
    # Family loyalty
    # ------------------------------------------------------------------

    @staticmethod
    def family_trust_bonus(npc_a, npc_b) -> int:
        """Return trust bonus if two NPCs share family."""
        fam_a = getattr(npc_a, 'family', None)
        fam_b = getattr(npc_b, 'family', None)
        if not fam_a or not fam_b:
            return 0

        bonus = 0
        # Parent-child
        if (fam_a.get("mother") == npc_b.name or
            fam_a.get("father") == npc_b.name or
            npc_a.name in fam_b.get("children", [])):
            bonus += 30
        # Siblings
        if npc_b.name in fam_a.get("siblings", []):
            bonus += 20
        # Spouse
        if fam_a.get("spouse") == npc_b.name:
            bonus += 40
        return bonus

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_npc(npcs: list, name: str):
        """Find an NPC by name in the list."""
        if not name:
            return None
        for npc in npcs:
            if npc.name == name:
                return npc
        return None

    def _generate_child_name(self, mother, father, npcs: list,
                              population) -> str:
        """Generate a unique name for a child."""
        # Use population name pool if available
        if population and hasattr(population, '_get_next_name'):
            base_name = population._get_next_name()
        else:
            names = [
                "Aric", "Brea", "Corwin", "Delia", "Eryn", "Finn", "Gwen",
                "Hal", "Ivy", "Jace", "Kira", "Lor", "Mira", "Nico",
                "Ora", "Penn", "Ria", "Seth", "Tara", "Ulin", "Vale",
                "Wynn", "Xara", "Yael", "Zara",
            ]
            base_name = random.choice(names)

        # Ensure uniqueness
        existing = {n.name for n in npcs}
        name = base_name
        suffix = 2
        while name in existing:
            name = f"{base_name}_{suffix}"
            suffix += 1

        return name

    def get_event_log(self) -> List[str]:
        """Get and clear the event log."""
        log = list(self.event_log)
        self.event_log.clear()
        return log
