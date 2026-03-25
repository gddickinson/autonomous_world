"""
Kingdom AI — War resolution module.

Handles active war tracking, army targeting, settlement capture,
peace treaties, and war declaration logic. Used by KingdomAI as a mixin.
"""

import random
import math
from typing import Dict, List, Optional, Tuple

from game.systems.kingdom_ai_defs import (
    WarState, WAR_DECLARATION_MIN_TREASURY, WAR_DECLARATION_ARMY_RATIO,
    PEACE_TREATY_TRIBUTE_FRACTION, WAR_MAX_DAYS,
    PEACE_EXHAUSTION_THRESHOLD, ARMY_MIN_FOR_WAR,
)


class KingdomWarMixin:
    """Mixin providing war declaration, resolution, and peace logic."""

    # ------------------------------------------------------------------
    # Expansion / war declaration
    # ------------------------------------------------------------------

    def _decide_expansion(self, kname, kingdom, priorities, governance,
                          military, game_day):
        """Consider declaring war if strong enough."""
        exp_p = priorities["expansion"]
        if exp_p < 0.15:
            return

        # Already at war?
        already_at_war = any(
            (w.attacker == kname or w.defender == kname) and not w.ended
            for w in self.wars
        )
        if already_at_war:
            return

        if kingdom.treasury < WAR_DECLARATION_MIN_TREASURY:
            return

        # Our army strength
        our_army = sum(a.size for a in military.armies.values()
                       if a.kingdom == kname and a.size > 0)
        if our_army < ARMY_MIN_FOR_WAR:
            return

        # Stockpile check
        sp = self.stockpiles.get(kname)
        if sp and (sp.food < 40 or sp.weapons < 10):
            return

        # Evaluate targets — pick weakest neighbour
        best_target = None
        best_ratio = 0.0
        for other_name, other_kingdom in governance.kingdoms.items():
            if other_name == kname:
                continue
            rel = governance.get_diplomacy(kname, other_name)
            if rel and rel.status in ("allied", "friendly"):
                continue

            other_army = sum(a.size for a in military.armies.values()
                             if a.kingdom == other_name and a.size > 0)
            other_army = max(other_army, getattr(other_kingdom, 'army_size', 0))
            if other_army == 0:
                other_army = 5

            ratio = our_army / other_army
            if ratio > WAR_DECLARATION_ARMY_RATIO and ratio > best_ratio:
                best_ratio = ratio
                best_target = other_name

        if best_target is None:
            return

        war_chance = 0.1 + exp_p * 0.3
        if random.random() > war_chance:
            return

        self._declare_war(kname, best_target, governance, military, game_day)

    def _declare_war(self, attacker: str, defender: str, governance,
                     military, game_day: int):
        """Formally declare war between two kingdoms."""
        from game.systems.governance import DiplomaticRelation, AT_WAR

        rel = governance.get_diplomacy(attacker, defender)
        if rel is None:
            rel = DiplomaticRelation()
            key = (min(attacker, defender), max(attacker, defender))
            governance.diplomacy[key] = rel
        rel.status = AT_WAR
        rel.trust = max(-100, rel.trust - 40)
        rel.war_exhaustion = 0

        war = WarState(attacker, defender, game_day)
        self.wars.append(war)

        att_k = governance.kingdoms.get(attacker)
        if att_k:
            military.launch_campaign(attacker, defender,
                                     att_k.ruler_name, governance)

        self.event_log.append(
            f"{attacker} declares war on {defender} over resource disputes!")

    # ------------------------------------------------------------------
    # War resolution (daily)
    # ------------------------------------------------------------------

    def _update_wars(self, governance, military, structures, game_day):
        """Advance active wars: check positions, captures, peace."""
        struct_map = {s.name: s for s in structures}

        for war in self.wars:
            if war.ended:
                continue

            att_k = governance.kingdoms.get(war.attacker)
            def_k = governance.kingdoms.get(war.defender)
            if not att_k or not def_k:
                war.ended = True
                continue

            war_days = game_day - war.start_day
            if war_days > WAR_MAX_DAYS:
                self._end_war(war, governance, military, reason="exhaustion")
                continue

            att_army = sum(a.size for a in military.armies.values()
                           if a.kingdom == war.attacker and a.size > 0)
            def_army = sum(a.size for a in military.armies.values()
                           if a.kingdom == war.defender and a.size > 0)

            if att_army < ARMY_MIN_FOR_WAR and def_army < ARMY_MIN_FOR_WAR:
                self._end_war(war, governance, military,
                              reason="mutual_exhaustion")
                continue
            if att_army < ARMY_MIN_FOR_WAR:
                self._end_war(war, governance, military, loser=war.attacker)
                continue
            if def_army < ARMY_MIN_FOR_WAR:
                self._end_war(war, governance, military, loser=war.defender)
                continue

            rel = governance.get_diplomacy(war.attacker, war.defender)
            if rel and rel.war_exhaustion > PEACE_EXHAUSTION_THRESHOLD:
                self._end_war(war, governance, military, reason="exhaustion")
                continue

            self._direct_armies_to_targets(war, governance, military,
                                           struct_map)
            self._check_captures(war, governance, military, struct_map)

    def _direct_armies_to_targets(self, war, governance, military, struct_map):
        """Point armies at nearest enemy border settlement."""
        for side, enemy_side in [(war.attacker, war.defender),
                                  (war.defender, war.attacker)]:
            enemy_k = governance.kingdoms.get(enemy_side)
            if not enemy_k or not enemy_k.settlements:
                continue

            for army in military.armies.values():
                if army.kingdom != side or army.size == 0:
                    continue
                if army.state == "marching" and army.target_x is not None:
                    continue

                best_dist = float('inf')
                best_x, best_y = None, None
                for sname in enemy_k.settlements:
                    struct = struct_map.get(sname)
                    if not struct:
                        continue
                    dx = struct.x - army.x
                    dy = struct.y - army.y
                    d = math.sqrt(dx * dx + dy * dy)
                    if d < best_dist:
                        best_dist = d
                        best_x = float(struct.x)
                        best_y = float(struct.y)

                if best_x is not None:
                    army.target_x = best_x + random.uniform(-3, 3)
                    army.target_y = best_y + random.uniform(-3, 3)
                    army.state = "marching"
                    army.objective = f"Attack {enemy_side}"

    def _check_captures(self, war, governance, military, struct_map):
        """Check if any army is close enough to capture an enemy settlement."""
        for side, enemy_side in [(war.attacker, war.defender),
                                  (war.defender, war.attacker)]:
            enemy_k = governance.kingdoms.get(enemy_side)
            own_k = governance.kingdoms.get(side)
            if not enemy_k or not own_k:
                continue

            for sname in list(enemy_k.settlements):
                struct = struct_map.get(sname)
                if not struct:
                    continue

                for army in military.armies.values():
                    if army.kingdom != side or army.size < 5:
                        continue
                    dx = struct.x - army.x
                    dy = struct.y - army.y
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist > 15:
                        continue

                    defenders = sum(
                        a.size for a in military.armies.values()
                        if a.kingdom == enemy_side and a.size > 0
                        and math.sqrt((a.x - struct.x)**2 +
                                      (a.y - struct.y)**2) < 20
                    )
                    if defenders > 0:
                        continue

                    enemy_k.settlements.remove(sname)
                    own_k.settlements.append(sname)
                    war.settlements_captured.append((sname, side))
                    war.battles_fought += 1

                    self.event_log.append(
                        f"{side} captures {sname} from {enemy_side}!")

                    if not enemy_k.settlements:
                        self._end_war(war, governance, military,
                                      loser=enemy_side)
                        return
                    break

    # ------------------------------------------------------------------
    # War ending
    # ------------------------------------------------------------------

    def _end_war(self, war: "WarState", governance, military,
                 loser: Optional[str] = None, reason: str = ""):
        """End a war with a peace treaty."""
        war.ended = True

        att_k = governance.kingdoms.get(war.attacker)
        def_k = governance.kingdoms.get(war.defender)

        if loser:
            war.winner = (war.defender if loser == war.attacker
                          else war.attacker)
            winner_k = att_k if war.winner == war.attacker else def_k
            loser_k = att_k if loser == war.attacker else def_k

            if loser_k and winner_k:
                tribute = int(
                    loser_k.treasury * PEACE_TREATY_TRIBUTE_FRACTION)
                loser_k.treasury -= tribute
                winner_k.treasury += tribute

                if loser_k.settlements and len(loser_k.settlements) > 1:
                    transferred = loser_k.settlements.pop()
                    winner_k.settlements.append(transferred)
                    self.event_log.append(
                        f"Peace treaty: {loser} cedes {transferred} "
                        f"and pays {tribute}g tribute to {war.winner}")
                else:
                    self.event_log.append(
                        f"Peace treaty: {loser} pays {tribute}g tribute "
                        f"to {war.winner}")

                loser_k.public_morale = max(
                    0, getattr(loser_k, 'public_morale', 50) - 20)
                winner_k.public_morale = min(
                    100, getattr(winner_k, 'public_morale', 50) + 15)
        else:
            self.event_log.append(
                f"War between {war.attacker} and {war.defender} ends "
                f"in a stalemate ({reason})")

        rel = governance.get_diplomacy(war.attacker, war.defender)
        if rel:
            rel.status = "hostile"
            rel.trust = max(-100, rel.trust + 10)
            rel.war_exhaustion = 0

        for army in military.armies.values():
            if army.kingdom in (war.attacker, war.defender):
                if army.state in ("marching", "fighting", "sieging"):
                    army.state = "idle"
                    army.target_x = None
                    army.target_y = None
