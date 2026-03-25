"""Dynamic world events — emergent story events that fire periodically.

Phase 4 story system: political upheaval, social milestones, discoveries,
and disasters that have real gameplay effects on kingdoms, settlements,
NPCs, terrain, and economy.

Events fire every 5-15 game days, chosen by category weights.
Each event logs descriptive messages, modifies game state, and notifies
nearby NPCs so they can reference events in conversation.

Architecture:
- DynamicEvent + helpers: dynamic_events_helpers.py
- Discovery/disaster handlers: dynamic_events_world.py (mixin)
- Core system + political/social: this file
"""

import random
from typing import List, Dict, Any

from game.systems.dynamic_events_helpers import (
    DynamicEvent, CATEGORY_WEIGHTS, EVENT_CHECK_MIN_DAYS,
    EVENT_CHECK_MAX_DAYS, _weighted_choice, _random_kingdom,
    _in_kingdom, _distance, _distance_to,
)
from game.systems.dynamic_events_world import DynamicEventsWorldMixin


# ================================================================
# DYNAMIC EVENTS SYSTEM
# ================================================================

class DynamicEventsSystem(DynamicEventsWorldMixin):
    """Fires emergent story events every 5-15 game days.

    Requires references to governance, world, and NPC list.
    Call ``update(game_day, governance, world, npcs)`` once per game day.
    """

    def __init__(self):
        self.next_event_day: int = random.randint(
            EVENT_CHECK_MIN_DAYS, EVENT_CHECK_MAX_DAYS)
        self.active_events: List[DynamicEvent] = []
        self.event_history: List[DynamicEvent] = []
        self.event_log: List[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, game_day: int, governance, world, npcs: list,
               military=None):
        """Called once per game day from the simulation loop."""
        self._resolve_expired(game_day)

        if game_day >= self.next_event_day:
            self._fire_event(game_day, governance, world, npcs, military)
            self.next_event_day = game_day + random.randint(
                EVENT_CHECK_MIN_DAYS, EVENT_CHECK_MAX_DAYS)

    def get_event_log(self) -> List[str]:
        """Drain and return pending log messages."""
        log = list(self.event_log)
        self.event_log.clear()
        return log

    # ------------------------------------------------------------------
    # Event firing
    # ------------------------------------------------------------------

    def _fire_event(self, game_day: int, governance, world, npcs: list,
                    military=None):
        """Pick a category and fire a random event from it."""
        category = _weighted_choice(CATEGORY_WEIGHTS)
        handler = {
            "political": self._fire_political,
            "social": self._fire_social,
            "discovery": self._fire_discovery,   # from mixin
            "disaster": self._fire_disaster,     # from mixin
        }.get(category)
        if handler:
            handler(game_day, governance, world, npcs, military)

    # ------------------------------------------------------------------
    # POLITICAL EVENTS
    # ------------------------------------------------------------------

    def _fire_political(self, game_day, governance, world, npcs, military):
        """Fire one of: coup attempt, succession crisis, alliance proposal."""
        kingdoms = governance.kingdoms if governance else {}
        if not kingdoms:
            return
        roll = random.random()
        if roll < 0.35:
            self._coup_attempt(game_day, governance, npcs)
        elif roll < 0.65:
            self._succession_crisis(game_day, governance, npcs)
        else:
            self._alliance_proposal(game_day, governance)

    def _coup_attempt(self, game_day, governance, npcs):
        """A rival NPC challenges the kingdom ruler. 30% success."""
        kname, kingdom = _random_kingdom(governance)
        if not kname:
            return
        ruler_name = kingdom.ruler_name
        # Find a rival NPC in the kingdom
        candidates = [n for n in npcs if n.alive
                      and not getattr(n, 'is_ruler', False)
                      and getattr(n, 'bravery', 0.5) > 0.5
                      and _in_kingdom(n, kingdom)]
        if not candidates:
            return
        rival = random.choice(candidates)
        success = random.random() < 0.30

        if success:
            # Coup succeeds — new ruler
            old_ruler_npcs = [n for n in npcs if n.name == ruler_name
                              and n.alive]
            for r in old_ruler_npcs:
                r.is_ruler = False
                r.title = "commoner"
            rival.is_ruler = True
            rival.title = "monarch"
            kingdom.ruler_name = rival.name
            lost = int(kingdom.treasury * 0.2)
            kingdom.treasury = max(0, kingdom.treasury - lost)
            kingdom.public_morale = max(0, kingdom.public_morale - 15)
            desc = (f"COUP in {kname}! {rival.name} overthrew {ruler_name} "
                    f"and seized the throne. {lost}g lost from the treasury.")
            evt = DynamicEvent("political", "Coup d'Etat", desc,
                               {"ruler_changed": True, "gold_lost": lost},
                               kingdom_name=kname, game_day=game_day)
        else:
            kingdom.public_morale = max(0, kingdom.public_morale - 5)
            rival.player_relationship = max(-100,
                                            rival.player_relationship - 10)
            desc = (f"FAILED COUP in {kname}! {rival.name} attempted to "
                    f"overthrow {ruler_name} but was defeated.")
            evt = DynamicEvent("political", "Failed Coup", desc,
                               {"ruler_changed": False},
                               kingdom_name=kname, game_day=game_day)

        self._register_event(evt, npcs, kingdom)

    def _succession_crisis(self, game_day, governance, npcs):
        """Ruler dies of old age; heir found or civil war looms."""
        kname, kingdom = _random_kingdom(governance)
        if not kname:
            return
        ruler_npcs = [n for n in npcs if n.name == kingdom.ruler_name
                      and n.alive]
        if not ruler_npcs:
            return
        ruler = ruler_npcs[0]
        age = getattr(ruler, 'age', 40)
        if age < 50 and random.random() > 0.3:
            return

        # Ruler dies
        ruler.alive = False
        ruler.hp = 0
        ruler.is_ruler = False

        # Look for heir
        heir_name = kingdom.heir_name
        heir_npcs = [n for n in npcs if n.name == heir_name and n.alive] \
            if heir_name else []

        if heir_npcs:
            heir = heir_npcs[0]
            heir.is_ruler = True
            heir.title = "monarch"
            kingdom.ruler_name = heir.name
            kingdom.heir_name = ""
            desc = (f"SUCCESSION in {kname}: {ruler.name} has died. "
                    f"{heir.name} inherits the throne.")
            effects = {"ruler_died": True, "heir_found": True}
        else:
            kingdom.public_morale = max(0, kingdom.public_morale - 25)
            kingdom.treasury = max(0, kingdom.treasury - 50)
            eligible = [n for n in npcs if n.alive
                        and _in_kingdom(n, kingdom)
                        and getattr(n, 'bravery', 0.5) > 0.4]
            if eligible:
                new_ruler = max(eligible,
                                key=lambda n: getattr(n, 'bravery', 0.5))
                new_ruler.is_ruler = True
                new_ruler.title = "monarch"
                kingdom.ruler_name = new_ruler.name
                desc = (f"SUCCESSION CRISIS in {kname}: {ruler.name} died "
                        f"with no heir! {new_ruler.name} seized power amid "
                        f"civil unrest. Morale plummets.")
            else:
                kingdom.ruler_name = ""
                desc = (f"SUCCESSION CRISIS in {kname}: {ruler.name} died "
                        f"with no heir! The kingdom descends into chaos.")
            effects = {"ruler_died": True, "heir_found": False}

        evt = DynamicEvent("political", "Succession Crisis", desc,
                           effects, kingdom_name=kname, game_day=game_day)
        self._register_event(evt, npcs, kingdom)

    def _alliance_proposal(self, game_day, governance):
        """Two kingdoms may form an alliance."""
        kingdoms = governance.kingdoms
        names = list(kingdoms.keys())
        if len(names) < 2:
            return
        k1, k2 = random.sample(names, 2)
        rel = governance.get_diplomacy(k1, k2)
        if not rel:
            return
        base_chance = 0.4 + (rel.trust / 200.0)
        if random.random() < base_chance:
            rel.trust = min(100, rel.trust + 30)
            rel.update_status()
            desc = (f"ALLIANCE formed between {k1} and {k2}! "
                    f"Relations improve significantly.")
            effects = {"alliance": True, "kingdoms": [k1, k2]}
        else:
            rel.trust = min(100, rel.trust + 5)
            rel.update_status()
            desc = (f"Alliance talks between {k1} and {k2} stalled, "
                    f"but goodwill was exchanged.")
            effects = {"alliance": False, "kingdoms": [k1, k2]}

        evt = DynamicEvent("political", "Alliance Proposal", desc,
                           effects, game_day=game_day)
        self.active_events.append(evt)
        self.event_history.append(evt)
        self.event_log.append(f"STORY: {desc}")

    # ------------------------------------------------------------------
    # SOCIAL EVENTS
    # ------------------------------------------------------------------

    def _fire_social(self, game_day, governance, world, npcs, military):
        """Fire one of: wedding, elopement, festival."""
        roll = random.random()
        if roll < 0.35:
            self._wedding(game_day, npcs, world)
        elif roll < 0.60:
            self._elopement(game_day, npcs, world)
        else:
            self._festival(game_day, governance, world, npcs)

    def _wedding(self, game_day, npcs, world):
        """A courting pair gets married."""
        courting = [(n, getattr(n, 'courting_target', None))
                    for n in npcs if n.alive
                    and getattr(n, 'courting_target', None)]
        if not courting:
            return
        npc, partner_name = random.choice(courting)
        partners = [p for p in npcs if p.name == partner_name and p.alive]
        if not partners:
            return
        partner = partners[0]
        npc.courting_target = None
        partner.courting_target = None
        if hasattr(npc, 'spouse'):
            npc.spouse = partner.name
        if hasattr(partner, 'spouse'):
            partner.spouse = npc.name
        for n in npcs:
            if n.alive and _distance(n, npc) < 60:
                n.known_info.append(
                    f"{npc.name} married {partner.name}!")
                if hasattr(n, 'emotion_state'):
                    n.emotion_state.apply_emotion("joy", 0.2)

        desc = (f"WEDDING: {npc.name} and {partner.name} got married! "
                f"The settlement celebrates.")
        evt = DynamicEvent("social", "Wedding", desc,
                           {"married": [npc.name, partner.name]},
                           game_day=game_day)
        self._register_event(evt, npcs)
        self.event_log.append(f"STORY: {desc}")

    def _elopement(self, game_day, npcs, world):
        """NPC leaves settlement to join partner in another settlement."""
        courting = [(n, getattr(n, 'courting_target', None))
                    for n in npcs if n.alive
                    and getattr(n, 'courting_target', None)]
        if not courting:
            return
        npc, partner_name = random.choice(courting)
        partners = [p for p in npcs if p.name == partner_name and p.alive]
        if not partners:
            return
        partner = partners[0]
        if _distance(npc, partner) < 40:
            return
        npc.home_x = partner.home_x
        npc.home_y = partner.home_y
        npc.x = partner.x + random.uniform(-2, 2)
        npc.y = partner.y + random.uniform(-2, 2)
        npc.courting_target = None
        partner.courting_target = None

        desc = (f"ELOPEMENT: {npc.name} left home to be with "
                f"{partner.name} in a distant settlement!")
        evt = DynamicEvent("social", "Elopement", desc,
                           {"eloped": [npc.name, partner.name]},
                           game_day=game_day)
        self._register_event(evt, npcs)
        self.event_log.append(f"STORY: {desc}")

    def _festival(self, game_day, governance, world, npcs):
        """Settlement holds a festival — morale boost, gold spent."""
        structures = [s for s in world.structures
                      if s.kind in ("village", "town", "city")]
        if not structures:
            return
        settlement = random.choice(structures)
        sx, sy = float(settlement.x), float(settlement.y)

        kingdom = None
        kname = ""
        if governance:
            kname = governance.get_kingdom_at(sx, sy) or ""
            if kname:
                kingdom = governance.kingdoms.get(kname)

        gold_cost = random.randint(10, 40)
        if kingdom and kingdom.treasury >= gold_cost:
            kingdom.treasury -= gold_cost
            kingdom.public_morale = min(100, kingdom.public_morale + 10)

        boosted = 0
        for n in npcs:
            if n.alive and _distance_to(n, sx, sy) < 40:
                boosted += 1
                n.known_info.append(f"Festival in {settlement.name}!")
                if hasattr(n, 'emotion_state'):
                    n.emotion_state.apply_emotion("joy", 0.3)
                needs = getattr(n, 'needs', {})
                if "social" in needs:
                    needs["social"] = min(100, needs["social"] + 20)

        desc = (f"FESTIVAL in {settlement.name}! The townsfolk celebrate. "
                f"{boosted} citizens enjoy the festivities. "
                f"{gold_cost}g spent from the treasury.")
        evt = DynamicEvent("social", "Festival", desc,
                           {"morale_boost": 10, "gold_spent": gold_cost},
                           settlement_name=settlement.name,
                           kingdom_name=kname, game_day=game_day)
        self._register_event(evt, npcs)
        self.event_log.append(f"STORY: {desc}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_expired(self, game_day: int):
        """Mark events past their duration as resolved."""
        for evt in self.active_events:
            if (evt.duration_days > 0
                    and game_day >= evt.started_day + evt.duration_days):
                evt.resolved = True
        self.active_events = [e for e in self.active_events
                              if not e.resolved]

    def _register_event(self, evt: DynamicEvent, npcs: list,
                        kingdom=None):
        """Add event to tracking lists and notify nearby NPCs."""
        self.active_events.append(evt)
        self.event_history.append(evt)

        # Spread knowledge to NPCs in the affected kingdom
        for n in npcs:
            if not n.alive:
                continue
            if kingdom and _in_kingdom(n, kingdom):
                n.known_info.append(evt.description[:120])
