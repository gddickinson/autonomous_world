"""
Heresy & Religious Schism: faith loss, conversion, cults, schism, and atheism.

NPCs can lose faith, convert between religions, found cults, trigger
schisms, and become atheists.  Checked every 5 game days from the
simulation loop.
"""

import random
import math
from typing import Dict, List, Optional, Tuple


# ================================================================
# CONSTANTS
# ================================================================

# How many unanswered prayers before faith starts eroding
UNANSWERED_PRAYER_THRESHOLD = 5

# Minimum followers before a cult can be recognized as a real religion
CULT_RECOGNITION_THRESHOLD = 12

# Days of god-neglect in a region before a splinter sect can form
NEGLECT_DAYS_FOR_SCHISM = 20

# Trust penalty applied to family members on conversion
CONVERSION_FAMILY_TRUST_LOSS = 25

# Minimum attribute values (1-10 scale) for founding a cult
CULT_CHARISMA_MINIMUM = 7
CULT_OPENNESS_MINIMUM = 0.6  # Big Five personality, 0-1

# How much intelligence + low trust pushes toward atheism
ATHEISM_INTELLIGENCE_MINIMUM = 7
ATHEISM_TRUST_MAXIMUM = 0.3

# Conversion base probability per check (modified by many factors)
CONVERSION_BASE_CHANCE = 0.04

# Schism base probability per neglected region per check
SCHISM_BASE_CHANCE = 0.06


# ================================================================
# CULT / SPLINTER SECT DATA
# ================================================================

class Cult:
    """A heretical cult or splinter sect."""

    __slots__ = (
        "name", "founder_name", "parent_religion", "patron_god",
        "founded_day", "followers", "settlement", "is_splinter",
        "recognized", "persecution_level",
    )

    def __init__(self, name: str, founder_name: str,
                 parent_religion: str = "",
                 patron_god: str = "",
                 settlement: str = "",
                 is_splinter: bool = False):
        self.name = name
        self.founder_name = founder_name
        self.parent_religion = parent_religion
        self.patron_god = patron_god
        self.founded_day = 0
        self.followers: List[str] = [founder_name]  # NPC names
        self.settlement = settlement
        self.is_splinter = is_splinter
        self.recognized = False  # True once follower count passes threshold
        self.persecution_level = 0  # 0=none, 1=disapproval, 2=persecution, 3=exile

    @property
    def size(self) -> int:
        return len(self.followers)


# ================================================================
# CULT NAME GENERATION
# ================================================================

_CULT_PREFIXES = [
    "The Seekers of", "The Children of", "The Order of",
    "The Awakened of", "The Covenant of", "The Disciples of",
    "The Chosen of", "The Watchers of", "The Hand of",
    "The Flame of", "The Eyes of", "The Whisper of",
]

_CULT_SUFFIXES = [
    "Eternal Truth", "Hidden Light", "the Deep",
    "the Void", "the Burning Star", "the Silent Moon",
    "Xaotl's Shadow", "the Unbroken Chain", "the Last Dawn",
    "Morwen's Veil", "the Crimson Path", "the Shattered Mirror",
]


def _generate_cult_name(patron: str = "") -> str:
    prefix = random.choice(_CULT_PREFIXES)
    if patron and random.random() < 0.4:
        return f"{prefix} {patron}"
    return f"{prefix} {random.choice(_CULT_SUFFIXES)}"


# ================================================================
# HERESY SYSTEM
# ================================================================

class HeresySystem:
    """Manages religious conversion, cults, schisms, and atheism."""

    def __init__(self):
        self.cults: List[Cult] = []
        self.atheists: set = set()  # NPC names
        self.npc_prayer_counts: Dict[str, int] = {}     # name -> total prayers
        self.npc_answered_counts: Dict[str, int] = {}   # name -> answered prayers
        self.npc_faith: Dict[str, float] = {}            # name -> faith 0-1
        self.npc_conversion_progress: Dict[str, Dict] = {}  # name -> {target_religion, progress}
        self._region_neglect: Dict[str, int] = {}         # settlement -> days neglected
        self._last_check_day: int = -1
        self.event_log: List[str] = []

    # ----------------------------------------------------------------
    # MAIN UPDATE (called every 5 game days from simulation)
    # ----------------------------------------------------------------

    def update(self, day: int, npcs: list, structures: list,
               pantheon=None, culture=None):
        """Run all heresy checks.  Should be called every 5 game days."""
        if day == self._last_check_day:
            return
        self._last_check_day = day

        # Ensure faith is initialized for all NPCs
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            name = getattr(npc, 'name', '')
            if name and name not in self.npc_faith:
                self.npc_faith[name] = 1.0  # start with full faith

        self._check_faith_erosion(npcs, pantheon)
        self._check_conversions(npcs, structures, culture)
        self._check_cult_founding(npcs, day, structures)
        self._check_cult_growth(npcs, structures)
        self._check_cult_recognition(day, culture)
        self._check_cult_persecution(npcs, structures)
        self._check_schisms(npcs, structures, pantheon, day)
        self._check_atheism(npcs)

    # ----------------------------------------------------------------
    # PRAYER TRACKING (called externally when prayers happen)
    # ----------------------------------------------------------------

    def record_prayer(self, npc_name: str, answered: bool):
        """Record a prayer event for faith tracking."""
        self.npc_prayer_counts[npc_name] = self.npc_prayer_counts.get(npc_name, 0) + 1
        if answered:
            self.npc_answered_counts[npc_name] = self.npc_answered_counts.get(npc_name, 0) + 1

    # ----------------------------------------------------------------
    # FAITH EROSION
    # ----------------------------------------------------------------

    def _check_faith_erosion(self, npcs: list, pantheon):
        """Erode faith for NPCs with many unanswered prayers or crises."""
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            name = getattr(npc, 'name', '')
            if not name or name in self.atheists:
                continue

            faith = self.npc_faith.get(name, 1.0)
            total_prayers = self.npc_prayer_counts.get(name, 0)
            answered = self.npc_answered_counts.get(name, 0)
            unanswered = total_prayers - answered

            # Unanswered prayers erode faith
            if unanswered >= UNANSWERED_PRAYER_THRESHOLD:
                erosion = 0.03 * (unanswered - UNANSWERED_PRAYER_THRESHOLD + 1)
                faith = max(0.0, faith - erosion)

            # Personal crisis without divine help
            es = getattr(npc, 'emotion_state', None)
            if es:
                sadness = es.primary.get('sadness', 0.0)
                fear = es.primary.get('fear', 0.0)
                if (sadness > 0.6 or fear > 0.6) and unanswered > 2:
                    faith = max(0.0, faith - 0.05)

            # Answered prayers restore faith
            if answered > 0 and total_prayers > 0:
                ratio = answered / total_prayers
                if ratio > 0.5:
                    faith = min(1.0, faith + 0.02)

            self.npc_faith[name] = faith

    # ----------------------------------------------------------------
    # CONVERSION
    # ----------------------------------------------------------------

    def _check_conversions(self, npcs: list, structures: list, culture):
        """Check for gradual religious conversions."""
        # Build settlement religion map
        settlement_religions: Dict[str, str] = {}
        if culture:
            settlement_religions = getattr(culture, 'settlement_religions', {})

        # Build quick NPC lookup
        npc_map = {getattr(n, 'name', ''): n for n in npcs if getattr(n, 'alive', True)}

        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            name = getattr(npc, 'name', '')
            if not name or name in self.atheists:
                continue

            current_religion = getattr(npc, 'religion', '')
            if not current_religion:
                continue

            faith = self.npc_faith.get(name, 1.0)

            # Only consider conversion if faith is weakened
            if faith > 0.6:
                continue

            # Determine dominant religion in NPC's settlement
            home_settlement = getattr(npc, 'home_settlement', '')
            dominant_religion = settlement_religions.get(home_settlement, current_religion)

            # Spouse influence
            spouse_name = getattr(npc, 'spouse', None)
            spouse_religion = ''
            if spouse_name and spouse_name in npc_map:
                spouse_religion = getattr(npc_map[spouse_name], 'religion', '')

            # Pick target religion
            target = None
            if spouse_religion and spouse_religion != current_religion:
                target = spouse_religion
            elif dominant_religion and dominant_religion != current_religion:
                target = dominant_religion

            if not target:
                continue

            # Calculate conversion probability
            chance = CONVERSION_BASE_CHANCE
            # Low faith increases chance
            chance += (1.0 - faith) * 0.1
            # Emotional desperation
            es = getattr(npc, 'emotion_state', None)
            if es:
                desperation = es.primary.get('sadness', 0) + es.primary.get('fear', 0)
                chance += desperation * 0.05
            # Spouse match bonus
            if target == spouse_religion:
                chance += 0.05

            # Gradual progress
            progress = self.npc_conversion_progress.get(name, {})
            if progress.get('target_religion') != target:
                progress = {'target_religion': target, 'progress': 0.0}

            progress['progress'] += chance
            self.npc_conversion_progress[name] = progress

            # Conversion completes at 1.0
            if progress['progress'] >= 1.0:
                old_religion = current_religion
                npc.religion = target
                self.npc_faith[name] = 0.7  # fresh convert, moderate faith
                del self.npc_conversion_progress[name]

                # Social friction: family trust loss
                self._apply_conversion_friction(npc, npc_map, old_religion)

                self.event_log.append(
                    f"[HERESY] {name} converted from {old_religion} to {target}."
                )

    def _apply_conversion_friction(self, npc, npc_map: dict, old_religion: str):
        """Apply trust penalties when an NPC converts."""
        name = getattr(npc, 'name', '')
        # Family disapproves
        relatives = set()
        spouse = getattr(npc, 'spouse', None)
        if spouse:
            relatives.add(spouse)
        for child_name in getattr(npc, 'children', []):
            relatives.add(child_name)
        parent = getattr(npc, 'parent_names', [])
        for p in parent:
            relatives.add(p)

        for rel_name in relatives:
            rel_npc = npc_map.get(rel_name)
            if not rel_npc or not getattr(rel_npc, 'alive', True):
                continue
            # Only friction if family member follows the old religion
            if getattr(rel_npc, 'religion', '') == old_religion:
                rels = getattr(npc, 'npc_relationships', {})
                current_trust = rels.get(rel_name, 0)
                rels[rel_name] = max(-100, current_trust - CONVERSION_FAMILY_TRUST_LOSS)

    # ----------------------------------------------------------------
    # CULT FOUNDING
    # ----------------------------------------------------------------

    def _check_cult_founding(self, npcs: list, day: int, structures: list):
        """Charismatic NPCs with high openness may found cults."""
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            name = getattr(npc, 'name', '')
            if not name:
                continue

            # Already a cult founder?
            if any(c.founder_name == name for c in self.cults):
                continue

            # Check attributes
            attrs = getattr(npc, 'attributes', {})
            charisma = attrs.get('charisma', 5)
            if charisma < CULT_CHARISMA_MINIMUM:
                continue

            # Check personality openness
            es = getattr(npc, 'emotion_state', None)
            personality = getattr(es, 'personality', None) if es else None
            openness = getattr(personality, 'openness', 0.5) if personality else 0.5
            if openness < CULT_OPENNESS_MINIMUM:
                continue

            # Low faith makes cult founding more likely
            faith = self.npc_faith.get(name, 1.0)
            if faith > 0.5:
                continue

            # Small random chance
            if random.random() > 0.08:
                continue

            # Determine patron and parent religion
            parent_religion = getattr(npc, 'religion', '')
            # Some cults worship dark entities
            patron = ""
            if random.random() < 0.3:
                patron = random.choice(["Xaotl", "Morwen", "the Void"])
            elif random.random() < 0.4:
                patron = random.choice(["Tharion", "Sylvana", "Verithos",
                                        "Auriel", "Lyria"])

            cult_name = _generate_cult_name(patron)
            settlement = getattr(npc, 'home_settlement', '')

            cult = Cult(
                name=cult_name,
                founder_name=name,
                parent_religion=parent_religion,
                patron_god=patron,
                settlement=settlement,
            )
            cult.founded_day = day

            # Recruit 1-2 initial followers from nearby NPCs
            for other in npcs:
                if cult.size >= 3:
                    break
                other_name = getattr(other, 'name', '')
                if other_name == name or not getattr(other, 'alive', True):
                    continue
                if not other_name:
                    continue
                # Nearby and low faith
                dist = math.sqrt((npc.x - other.x) ** 2 + (npc.y - other.y) ** 2)
                if dist > 15:
                    continue
                other_faith = self.npc_faith.get(other_name, 1.0)
                if other_faith < 0.5 and random.random() < 0.4:
                    cult.followers.append(other_name)

            self.cults.append(cult)
            self.event_log.append(
                f"[HERESY] {name} founded the cult '{cult_name}' "
                f"in {settlement or 'the wilderness'} with {cult.size} followers."
            )

    # ----------------------------------------------------------------
    # CULT GROWTH
    # ----------------------------------------------------------------

    def _check_cult_growth(self, npcs: list, structures: list):
        """Existing cults try to recruit new members."""
        npc_map = {getattr(n, 'name', ''): n for n in npcs if getattr(n, 'alive', True)}

        for cult in self.cults:
            founder = npc_map.get(cult.founder_name)
            if not founder or not getattr(founder, 'alive', True):
                continue

            # Founder charisma determines recruitment power
            charisma = getattr(founder, 'attributes', {}).get('charisma', 5)
            recruit_chance = 0.02 + charisma * 0.01

            for npc in npcs:
                name = getattr(npc, 'name', '')
                if not name or not getattr(npc, 'alive', True):
                    continue
                if name in cult.followers or name in self.atheists:
                    continue
                if name == cult.founder_name:
                    continue

                # Must be reasonably close to the cult's settlement
                dist = math.sqrt((npc.x - founder.x) ** 2 + (npc.y - founder.y) ** 2)
                if dist > 30:
                    continue

                faith = self.npc_faith.get(name, 1.0)
                if faith > 0.6:
                    continue

                if random.random() < recruit_chance * (1.0 - faith):
                    cult.followers.append(name)
                    self.event_log.append(
                        f"[HERESY] {name} joined the cult '{cult.name}'."
                    )

    # ----------------------------------------------------------------
    # CULT RECOGNITION
    # ----------------------------------------------------------------

    def _check_cult_recognition(self, day: int, culture):
        """Cults that grow large enough become recognized religions."""
        for cult in self.cults:
            if cult.recognized:
                continue
            if cult.size >= CULT_RECOGNITION_THRESHOLD:
                cult.recognized = True
                # Register as a new religion in the culture system
                if culture:
                    from game.systems.culture import RELIGIONS
                    if cult.name not in RELIGIONS:
                        RELIGIONS[cult.name] = {
                            "alignment": "chaotic neutral",
                            "values": ["freedom", "mystery", "devotion"],
                            "classes": [],
                            "blessing": "morale",
                        }
                self.event_log.append(
                    f"[HERESY] The cult '{cult.name}' has been recognized "
                    f"as a religion with {cult.size} followers!"
                )

    # ----------------------------------------------------------------
    # CULT PERSECUTION
    # ----------------------------------------------------------------

    def _check_cult_persecution(self, npcs: list, structures: list):
        """Established religions persecute unrecognized cults."""
        for cult in self.cults:
            if cult.recognized:
                cult.persecution_level = 0
                continue

            # Larger cults attract more persecution
            if cult.size <= 2:
                cult.persecution_level = 0
            elif cult.size <= 5:
                cult.persecution_level = 1  # disapproval
            elif cult.size <= 10:
                cult.persecution_level = 2  # persecution
            else:
                cult.persecution_level = 3  # exile attempts

            if cult.persecution_level >= 2:
                # Small chance of losing followers due to persecution
                if cult.followers and random.random() < 0.15:
                    lost = random.choice(cult.followers[1:]) if len(cult.followers) > 1 else None
                    if lost:
                        cult.followers.remove(lost)
                        self.event_log.append(
                            f"[HERESY] {lost} left the cult '{cult.name}' "
                            f"due to persecution."
                        )

            if cult.persecution_level >= 3:
                # Founder may be exiled (mood penalty)
                npc_map = {getattr(n, 'name', ''): n for n in npcs
                           if getattr(n, 'alive', True)}
                founder = npc_map.get(cult.founder_name)
                if founder:
                    es = getattr(founder, 'emotion_state', None)
                    if es:
                        es.primary['fear'] = min(1.0, es.primary.get('fear', 0) + 0.3)
                        es.primary['anger'] = min(1.0, es.primary.get('anger', 0) + 0.2)

    # ----------------------------------------------------------------
    # SCHISM
    # ----------------------------------------------------------------

    def _check_schisms(self, npcs: list, structures: list,
                       pantheon, day: int):
        """If a god neglects a region, followers may form a splinter sect."""
        if not pantheon:
            return

        # Build settlement -> god mapping
        from game.systems.culture import RELIGIONS
        religion_god_map = {
            "The Light": ["Lyria", "Tharion"],
            "The Old Gods": ["Sylvana", "Morwen"],
            "The Arcane Path": ["Verithos", "Xaotl"],
            "The Shadow": ["Xaotl", "Morwen"],
            "The Forge": ["Tharion", "Auriel"],
        }

        # Check each settlement for neglect
        settlement_npcs: Dict[str, List] = {}
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            home = getattr(npc, 'home_settlement', '')
            if home:
                settlement_npcs.setdefault(home, []).append(npc)

        gods = getattr(pantheon, 'gods', {})

        for settlement_name, snpcs in settlement_npcs.items():
            if len(snpcs) < 5:
                continue

            # Find the dominant religion in the settlement
            religion_counts: Dict[str, int] = {}
            for npc in snpcs:
                rel = getattr(npc, 'religion', '')
                if rel:
                    religion_counts[rel] = religion_counts.get(rel, 0) + 1

            if not religion_counts:
                continue

            dominant = max(religion_counts, key=religion_counts.get)
            god_names = religion_god_map.get(dominant, [])

            # Check if gods have performed miracles in this settlement recently
            neglected = True
            for gn in god_names:
                god = gods.get(gn)
                if not god:
                    continue
                # Check recent miracles
                for miracle in god.miracles_performed[-20:]:
                    target = miracle.get('target', '')
                    if settlement_name.lower() in str(target).lower():
                        neglected = False
                        break
                if not neglected:
                    break

            if neglected:
                days = self._region_neglect.get(settlement_name, 0) + 5
                self._region_neglect[settlement_name] = days
            else:
                self._region_neglect[settlement_name] = 0
                continue

            days = self._region_neglect.get(settlement_name, 0)
            if days < NEGLECT_DAYS_FOR_SCHISM:
                continue

            # Chance of schism
            if random.random() > SCHISM_BASE_CHANCE:
                continue

            # Already has a splinter for this religion+settlement?
            existing = any(
                c.is_splinter and c.settlement == settlement_name
                and c.parent_religion == dominant
                for c in self.cults
            )
            if existing:
                continue

            # Pick a charismatic NPC as sect leader
            candidates = [n for n in snpcs
                          if getattr(n, 'religion', '') == dominant
                          and getattr(n, 'attributes', {}).get('charisma', 5) >= 6]
            if not candidates:
                continue

            leader = random.choice(candidates)
            leader_name = getattr(leader, 'name', '')
            sect_name = f"Reformed {dominant} of {settlement_name}"

            sect = Cult(
                name=sect_name,
                founder_name=leader_name,
                parent_religion=dominant,
                patron_god=god_names[0] if god_names else "",
                settlement=settlement_name,
                is_splinter=True,
            )
            sect.founded_day = day

            # Followers: NPCs in the settlement with low faith
            for npc in snpcs:
                npc_name = getattr(npc, 'name', '')
                if npc_name == leader_name:
                    continue
                if getattr(npc, 'religion', '') != dominant:
                    continue
                f = self.npc_faith.get(npc_name, 1.0)
                if f < 0.5 and random.random() < 0.5:
                    sect.followers.append(npc_name)

            self.cults.append(sect)
            self._region_neglect[settlement_name] = 0  # reset

            self.event_log.append(
                f"[SCHISM] '{sect_name}' formed in {settlement_name} "
                f"led by {leader_name} with {sect.size} followers! "
                f"The gods have neglected this region."
            )

    # ----------------------------------------------------------------
    # ATHEISM
    # ----------------------------------------------------------------

    def _check_atheism(self, npcs: list):
        """High-intelligence, low-trust NPCs may reject all gods."""
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            name = getattr(npc, 'name', '')
            if not name or name in self.atheists:
                continue

            attrs = getattr(npc, 'attributes', {})
            intelligence = attrs.get('intelligence', 5)
            if intelligence < ATHEISM_INTELLIGENCE_MINIMUM:
                continue

            # Check trust from emotion state
            es = getattr(npc, 'emotion_state', None)
            trust = 0.5
            if es:
                trust = es.primary.get('trust', 0.5)

            if trust > ATHEISM_TRUST_MAXIMUM:
                continue

            faith = self.npc_faith.get(name, 1.0)
            if faith > 0.3:
                continue

            # Small chance per check
            if random.random() > 0.06:
                continue

            self.atheists.add(name)
            npc.religion = ""  # no religion
            self.npc_faith[name] = 0.0

            self.event_log.append(
                f"[ATHEISM] {name} has rejected all gods. "
                f"They no longer pray or attend temples."
            )

            # Nearby NPCs react based on openness
            for other in npcs:
                if other is npc or not getattr(other, 'alive', True):
                    continue
                dist = math.sqrt((npc.x - other.x) ** 2 + (npc.y - other.y) ** 2)
                if dist > 10:
                    continue
                o_es = getattr(other, 'emotion_state', None)
                if not o_es:
                    continue
                o_personality = getattr(o_es, 'personality', None)
                o_openness = getattr(o_personality, 'openness', 0.5) if o_personality else 0.5
                if o_openness > 0.6:
                    # Curiosity
                    o_es.primary['surprise'] = min(1.0, o_es.primary.get('surprise', 0) + 0.2)
                else:
                    # Disgust
                    o_es.primary['disgust'] = min(1.0, o_es.primary.get('disgust', 0) + 0.2)

    # ----------------------------------------------------------------
    # ATHEISM SPREAD (centers of learning)
    # ----------------------------------------------------------------

    def spread_atheism_from_scholars(self, npcs: list, structures: list):
        """Atheism spreads in settlements with libraries/scholars.

        Called internally during update; checks settlement intellectual
        density.
        """
        # Build settlement scholar counts
        settlement_scholars: Dict[str, int] = {}
        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            prof = getattr(npc, 'profession', '')
            if prof in ('Scholar', 'Philosopher', 'Alchemist', 'Scribe', 'Cartographer'):
                home = getattr(npc, 'home_settlement', '')
                if home:
                    settlement_scholars[home] = settlement_scholars.get(home, 0) + 1

        for settlement, count in settlement_scholars.items():
            if count < 3:
                continue
            # Small chance for each non-atheist NPC in intellectual settlements
            for npc in npcs:
                name = getattr(npc, 'name', '')
                if not name or name in self.atheists:
                    continue
                if getattr(npc, 'home_settlement', '') != settlement:
                    continue
                attrs = getattr(npc, 'attributes', {})
                intelligence = attrs.get('intelligence', 5)
                if intelligence >= 6 and self.npc_faith.get(name, 1.0) < 0.4:
                    if random.random() < 0.02:
                        self.atheists.add(name)
                        npc.religion = ""
                        self.npc_faith[name] = 0.0
                        self.event_log.append(
                            f"[ATHEISM] {name} in {settlement} became "
                            f"an atheist through scholarly discourse."
                        )

    # ----------------------------------------------------------------
    # QUERIES
    # ----------------------------------------------------------------

    def is_atheist(self, npc_name: str) -> bool:
        return npc_name in self.atheists

    def get_faith(self, npc_name: str) -> float:
        return self.npc_faith.get(npc_name, 1.0)

    def get_npc_cult(self, npc_name: str) -> Optional[Cult]:
        """Return the cult an NPC belongs to, if any."""
        for cult in self.cults:
            if npc_name in cult.followers:
                return cult
        return None

    def get_cults_in_settlement(self, settlement: str) -> List[Cult]:
        return [c for c in self.cults if c.settlement == settlement]

    def get_event_log(self) -> List[str]:
        msgs = list(self.event_log)
        self.event_log.clear()
        return msgs

    def get_summary(self) -> List[str]:
        """Return a summary of all cults and atheists."""
        lines = []
        for cult in self.cults:
            status = "recognized" if cult.recognized else "heretical"
            kind = "splinter sect" if cult.is_splinter else "cult"
            lines.append(
                f"  {cult.name} ({kind}, {status}): "
                f"{cult.size} followers, founded by {cult.founder_name}, "
                f"persecution={cult.persecution_level}"
            )
        lines.append(f"  Atheists: {len(self.atheists)}")
        return lines
