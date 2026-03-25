"""Simulation daily life — death handling, economy, daily updates."""

import random
import math
from typing import List
from game.core.npc import NPC
from game.settings import *


def _estimate_threat(attacker, witness):
    """Estimate how threatening the attacker is relative to the witness.

    Returns a ratio: > 2.0 = overwhelming, 1.0 = equal, < 0.5 = weak.
    """
    atk_level = getattr(attacker, 'level', 1)
    atk_hp = getattr(attacker, 'hp', 50)
    atk_max = getattr(attacker, 'max_hp', 50)
    wit_level = getattr(witness, 'level', 1)
    wit_hp = getattr(witness, 'hp', 50)
    # Level difference is the strongest signal
    level_ratio = atk_level / max(1, wit_level)
    # HP pool suggests toughness
    hp_ratio = atk_max / max(1, getattr(witness, 'max_hp', 50))
    # Combined threat estimate
    return (level_ratio * 0.7 + hp_ratio * 0.3)


def _count_nearby_allies(npc, npc_grid, radius=10):
    """Count alive, non-fleeing NPCs near this NPC (potential allies)."""
    count = 0
    for other in npc_grid.get_nearby(npc.x, npc.y, radius):
        if other.alive and other is not npc:
            if getattr(other, 'state', '') != 'fleeing':
                count += 1
    return count


def _trigger_flee(npc, danger_x, danger_y, flee_dist=15):
    """Make an NPC flee away from a danger location."""
    if not npc.alive:
        return
    dx = npc.x - danger_x
    dy = npc.y - danger_y
    dist = math.sqrt(dx * dx + dy * dy) or 1.0
    npc.target_x = npc.x + (dx / dist) * flee_dist
    npc.target_y = npc.y + (dy / dist) * flee_dist
    npc.current_action = "fleeing"
    npc.state = "fleeing"
    npc._action_timer = 5.0
    npc._decision_timer = 5.0


def _trigger_attack(npc, attacker):
    """Make an NPC engage the attacker in combat."""
    if not npc.alive:
        return
    npc.combat_target = attacker
    npc.current_action = "fighting"
    npc.state = "combat"
    npc._action_timer = 0.0
    npc._decision_timer = 0.0


def _trigger_call_guards(npc, attacker, npc_grid):
    """NPC calls for guards — nearby guards switch to attack the threat."""
    if not npc.alive:
        return
    npc.current_action = "calling for help"
    npc._action_timer = 2.0
    for guard in npc_grid.get_nearby(npc.x, npc.y, 20):
        if not guard.alive or guard is npc:
            continue
        prof = getattr(guard, 'profession', '').lower()
        if prof in ('guard', 'soldier', 'captain', 'knight'):
            _trigger_attack(guard, attacker)


def _trigger_surrender(npc):
    """NPC surrenders — kneels and stops fighting."""
    if not npc.alive:
        return
    npc.current_action = "surrendering"
    npc.state = "surrendered"
    npc.combat_target = None
    npc._action_timer = 10.0
    npc._decision_timer = 10.0


def _respond_to_threat(npc, attacker, npc_grid):
    """Decide how an NPC responds to witnessing violence based on threat assessment.

    Responses vary by profession, threat level, and nearby allies:
    - Overwhelming threat (god-like): flee or surrender
    - Strong threat (outnumbered): flee + call guards
    - Moderate threat (even odds): guards attack, civilians call for help
    - Weak threat (NPC is stronger): attack directly
    """
    if not npc.alive:
        return

    prof = getattr(npc, 'profession', '').lower()
    is_combatant = prof in ('guard', 'soldier', 'captain', 'knight',
                            'hunter', 'ranger', 'mercenary')
    threat = _estimate_threat(attacker, npc)
    allies = _count_nearby_allies(npc, npc_grid, 12)
    bravery = 0.5  # base
    # Combatants are braver
    if is_combatant:
        bravery += 0.3
    # More allies = braver
    bravery += min(0.3, allies * 0.05)
    # Traits affect bravery
    traits = getattr(npc, 'traits', [])
    if 'brave' in traits or 'courageous' in traits:
        bravery += 0.2
    if 'cowardly' in traits or 'timid' in traits:
        bravery -= 0.3

    if threat > 5.0:
        # Godlike entity — everyone flees or surrenders
        if bravery > 0.8 and is_combatant:
            _trigger_surrender(npc)  # brave guards surrender rather than die
        else:
            _trigger_flee(npc, attacker.x, attacker.y, 20)
    elif threat > 2.0:
        # Very strong — civilians flee, guards call for backup then fight
        if is_combatant:
            _trigger_call_guards(npc, attacker, npc_grid)
            if allies >= 3:
                _trigger_attack(npc, attacker)  # enough allies to fight
            else:
                _trigger_flee(npc, attacker.x, attacker.y)
        else:
            _trigger_flee(npc, attacker.x, attacker.y)
    elif threat > 1.0:
        # Moderate threat — guards attack, civilians call for help then flee
        if is_combatant:
            _trigger_attack(npc, attacker)
        else:
            _trigger_call_guards(npc, attacker, npc_grid)
            _trigger_flee(npc, attacker.x, attacker.y)
    else:
        # Weak threat — even civilians might fight, or at least stand ground
        if is_combatant:
            _trigger_attack(npc, attacker)
        elif bravery > 0.6 and allies >= 2:
            # Brave civilian with friends — rally and attack
            _trigger_attack(npc, attacker)
        else:
            _trigger_call_guards(npc, attacker, npc_grid)


class SimDailyMixin:
    """Daily life, death handling, and economy methods."""

    def _handle_npc_death(self, npc: NPC):
        if not npc.alive and getattr(npc, '_death_handled', False):
            return  # already processed
        npc.alive = False
        npc._death_handled = True
        # Ensure movement/action state is cleared
        npc._on_death()
        # Determine cause of death from context
        age = getattr(npc, 'age', 30)
        cause = getattr(npc, '_death_cause', None)
        if cause is None:
            if npc.needs.get("hunger", 50) <= 0:
                cause = "starvation"
            elif npc.needs.get("thirst", 50) <= 0:
                cause = "dehydration"
            elif getattr(npc, 'combat_target', None) is not None:
                cause = "combat"
            elif getattr(npc, 'current_action', '') == "fighting":
                cause = "combat"
            elif age > 70 and npc.needs.get("hunger", 50) > 0 and npc.needs.get("thirst", 50) > 0:
                cause = "old_age"
            else:
                # Check body damage for wound cause
                body = getattr(npc, 'body', None)
                if body and getattr(body, 'is_dead', False):
                    cause = "wounds"
                else:
                    cause = "wounds"
        self.dead_npcs.append({"name": npc.name, "profession": npc.profession, "cause": cause,
                               "time": self.time_sys.time_string, "age": int(age)})
        self.event_log.append(f"{npc.name} the {npc.profession} has died from {cause}.")

        # Increment population death counter for nearest settlement
        if hasattr(self, 'population'):
            nearest = self.population._nearest_settlement(npc.x, npc.y)
            if nearest and nearest in self.population.settlements:
                self.population.settlements[nearest].deaths_today += 1

        # Burial system — create grave
        if hasattr(self, 'burial'):
            self.burial.on_death(npc, cause, self.time_sys.time_string,
                                 self.time_sys.day, self.world)

        # Drop inventory on the ground
        for item in npc.npc_inventory:
            self.world_mgr.ground_items.append((npc.x + random.uniform(-0.5, 0.5),
                                                 npc.y + random.uniform(-0.5, 0.5), item))
        npc.npc_inventory.clear()

        # Drop carried goods (from goods transport system) on the ground
        if hasattr(self, 'npc_work'):
            self.npc_work.handle_carrier_death(npc, self.world)

        # Clean up command system references
        if hasattr(self, 'command_system'):
            self.command_system.fail_command(npc.name, "died")
            # Drop trade goods if merchant was carrying them
            trade_goods = getattr(npc, '_trade_goods', None)
            if trade_goods:
                # Return goods to nearest settlement stores
                _we = self.world_effects if hasattr(self, 'world_effects') else None
                settlement = (getattr(npc, 'home_settlement', None)
                              or getattr(npc, 'faction', None))
                if settlement and _we:
                    stores = _we.get_stores_ref(settlement)
                    for good, qty in trade_goods.items():
                        stores[good] = stores.get(good, 0) + qty
                npc._trade_goods = None
                npc._trade_destination = None

        # Nearby NPCs mourn — record in life ledger + ephemeral memory
        from game.systems.memory import ensure_life_ledger
        day = self.time_sys.day
        loc_struct = self.world.get_structure_at(npc.x, npc.y)
        loc_name = loc_struct.name if loc_struct else "the wilderness"

        for other in self.npc_grid.get_nearby(npc.x, npc.y, 15):
            if other.alive and other is not npc and other.dist_to(npc) < 15:
                is_close = npc.name in getattr(other, 'friends', [])
                is_family = npc.name in getattr(other, 'friends', [])  # friends list includes family

                # Determine relationship label
                rel = "friend" if is_close else "acquaintance"
                if hasattr(self, 'social'):
                    social_rel = self.social.get_rel(other.name, npc.name)
                    if social_rel.status in ("close_friend", "friend"):
                        rel = social_rel.status.replace("_", " ")
                    elif social_rel.status == "enemy":
                        rel = "rival"

                # Record in life ledger (permanent, structured)
                ledger = ensure_life_ledger(other)
                ledger.record_death(
                    npc.name, cause, day,
                    relationship=rel,
                    race=getattr(npc, 'race', ''),
                    char_class=getattr(npc, 'char_class', ''),
                    location=loc_name,
                )

                # Record bond broken if they were bonded
                if npc.name in ledger.bonds:
                    ledger.record_bond_broken(npc.name, day, f"died from {cause}")

                # Ephemeral memory — brief, will decay over time
                # Only close bonds get high-importance memory
                importance = 4 if is_close else 2
                other.add_memory("death", f"{npc.name} died from {cause}", importance)
                other.known_info.append(f"{npc.name} died from {cause}")

        # Trigger family grief via child system
        if hasattr(self, 'child_system'):
            self.child_system.trigger_family_grief(npc, self.world_mgr.npcs)

        # Combat death: nearby NPCs respond based on threat assessment
        if cause in ("combat", "wounds", "murder"):
            # Try to identify the killer
            killer = getattr(npc, 'combat_target', None) or getattr(npc, '_last_attacker', None)
            for other in self.npc_grid.get_nearby(npc.x, npc.y, 15):
                if other.alive and other is not npc:
                    if killer:
                        _respond_to_threat(other, killer, self.npc_grid)
                    else:
                        # Unknown killer — civilians flee, guards go alert
                        prof = getattr(other, 'profession', '').lower()
                        if prof in ('guard', 'soldier', 'captain', 'knight'):
                            other.current_action = "guarding"
                            other.state = "alert"
                        else:
                            _trigger_flee(other, npc.x, npc.y)

    def _handle_npc_death_from_disease(self, npc, disease_name: str):
        """Handle NPC death caused by disease (called via health system callback)."""
        if not hasattr(npc, 'alive'):
            return
        npc.alive = False
        # Ensure movement/action state is cleared
        if hasattr(npc, '_on_death'):
            npc._on_death()
        cause = f"disease ({disease_name})"
        self.dead_npcs.append({"name": npc.name, "profession": getattr(npc, 'profession', '?'),
                               "cause": cause, "time": self.time_sys.time_string})

        # Increment population death counter for nearest settlement
        if hasattr(self, 'population'):
            nearest = self.population._nearest_settlement(npc.x, npc.y)
            if nearest and nearest in self.population.settlements:
                self.population.settlements[nearest].deaths_today += 1

        # Burial system — create grave
        if hasattr(self, 'burial'):
            self.burial.on_death(npc, "disease", self.time_sys.time_string,
                                 self.time_sys.day, self.world)

        # Release soul on death
        if hasattr(self, 'souls'):
            self.souls.on_death(npc, "natural", self.time_sys.time)

        # Drop inventory on the ground
        for item in npc.npc_inventory:
            self.world_mgr.ground_items.append((npc.x + random.uniform(-0.5, 0.5),
                                                 npc.y + random.uniform(-0.5, 0.5), item))
        npc.npc_inventory.clear()

        # Clean up command system references
        if hasattr(self, 'command_system'):
            self.command_system.fail_command(npc.name, "died")

        # Trigger family grief via child system
        if hasattr(self, 'child_system'):
            self.child_system.trigger_family_grief(npc, self.world_mgr.npcs)

        # Trigger grief in nearby NPCs
        if hasattr(self, 'npc_grid'):
            from game.systems.emotions import trigger_emotion
            for other in self.npc_grid.get_nearby(npc.x, npc.y, 15):
                if other.alive and other is not npc:
                    trigger_emotion(other, "witnessed_death", intensity=0.6,
                                    target=npc.name,
                                    cause=f"{npc.name} died from {disease_name}",
                                    game_time=self.time_sys.time)
                    # Notify mental health system of witnessed death
                    if hasattr(self, 'mental_health'):
                        self.mental_health.on_death_witnessed(other)
                    # Flee from the death location (panic response)
                    _trigger_flee(other, npc.x, npc.y)

    def _remove_dead_npcs(self, npcs: List[NPC]):
        """Remove NPC entities that have been dead for over 30 seconds."""
        import time as _t
        now = _t.time()
        CORPSE_LINGER = 30.0  # seconds before removal
        to_remove = []
        for npc in npcs:
            if not npc.alive:
                death_t = getattr(npc, '_death_time', None)
                if death_t is not None and (now - death_t) >= CORPSE_LINGER:
                    # Ensure death was fully handled before removing
                    if not getattr(npc, '_death_handled', False):
                        self._handle_npc_death(npc)
                    to_remove.append(npc)
        for npc in to_remove:
            if npc in self.world_mgr.npcs:
                self.world_mgr.npcs.remove(npc)

    # ---- LLM DECISIONS ----


    def _update_daily_life(self, npcs: List[NPC], dt: float):
        """Sims-style daily routines: work, earn, spend, eat on schedule."""
        # Throttle: only run every 3rd tick to save CPU
        if not hasattr(self, '_daily_life_tick'):
            self._daily_life_tick = 0
        self._daily_life_tick += 1
        if self._daily_life_tick % 3 != 0:
            return
        dt *= 3  # compensate for skipped ticks

        time_norm = self.time_sys.normalized
        active_set = self._active_npc_set

        for npc in npcs:
            if not npc.alive:
                continue
            # Skip dormant NPCs
            if active_set is not None and npc.name not in active_set:
                continue

            # Job income is now handled ENTIRELY by NpcLifecycle._tick_income
            # which draws wages from settlement treasury (real economy).
            # No duplicate baseline wage here — removed phantom income.

            # Cache structure lookup (avoid calling 3x per NPC)
            npc_loc = self.world.get_structure_at(npc.x, npc.y) if npc.npc_gold >= 2 else None

            # Get settlement stores for real transactions
            _stores = None
            if npc_loc and hasattr(self, 'world_effects'):
                _stores = self.world_effects.get_stores_ref(npc_loc.name)

            # Buy food/water when low on supplies and near a village
            # Gold flows FROM NPC TO settlement stores (real transaction)
            if npc.npc_gold >= 5 and not npc.has_food() and npc.needs["hunger"] < 50:
                if npc_loc and npc_loc.kind in ("village", "tavern"):
                    if _stores and _stores.get("food", 0) >= 2:
                        food = make_item("Bread")
                        food.count = 2
                        npc.npc_add_item(food)
                        npc.npc_gold -= 3
                        _stores["gold"] = _stores.get("gold", 0) + 3
                        _stores["food"] = max(0, _stores.get("food", 0) - 2)

            if npc.npc_gold >= 4 and not npc.has_drink() and npc.needs["thirst"] < 50:
                if npc_loc and npc_loc.kind in ("village", "tavern"):
                    water = make_item("Water Flask")
                    water.count = 2
                    npc.npc_add_item(water)
                    npc.npc_gold -= 2
                    if _stores:
                        _stores["gold"] = _stores.get("gold", 0) + 2

            # Tavern rest: gold flows to settlement (tavern revenue)
            if time_norm > 0.75 or time_norm < 0.2:
                if npc_loc and npc_loc.kind == "tavern" and npc.npc_gold >= 2:
                    if npc.needs["rest"] < 40 and npc.current_action != "sleeping":
                        npc.npc_gold -= 2
                        if _stores:
                            _stores["gold"] = _stores.get("gold", 0) + 2
                        npc.needs["rest"] = min(100, npc.needs["rest"] + 30)
                        npc.needs["social"] = min(100, npc.needs["social"] + 10)
                        npc.add_memory("life", "Rested at the tavern", 1)

            # Leaders attract followers: NPCs with high charisma and allied NPCs
            # cause nearby allies to follow them — use spatial grid
            if (getattr(npc, 'party_role', '') == 'leader' and
                npc.attributes.get("charisma", 5) >= 7):
                # Try to recruit nearby friendly NPCs who are solo (spatial grid)
                for other in self.npc_grid.get_nearby(npc.x, npc.y, 5):
                    if (other is npc or not other.alive or
                        getattr(other, 'party_id', None)):
                        continue
                    if npc.dist_to(other) < 5:
                        rel = self.social.get_rel(npc.name, other.name)
                        if rel.trust >= 30 and random.random() < 0.001 * dt:
                            other.party_id = npc.party_id
                            other.party_role = "member"
                            npc.add_memory("leadership", f"Recruited {other.name} to party", 3)
                            other.add_memory("social", f"Joined {npc.name}'s group", 3)
                            self.event_log.append(f"{other.name} joined {npc.name}'s party!")

            # Enemies: NPCs who hate each other may fight when they meet
            # Use spatial grid instead of scanning all NPCs
            enemies = getattr(npc, 'enemies', [])
            if enemies and npc.current_action != "fighting":
                enemy_set = set(enemies)
                for other in self.npc_grid.get_nearby(npc.x, npc.y, 4):
                    if (other.name in enemy_set and other.alive and
                        npc.dist_to(other) < 4):
                        rel = self.social.get_rel(npc.name, other.name)
                        # Only fight if truly hostile and brave enough
                        if rel.trust < -40 and npc.bravery > 0.6 and random.random() < 0.005 * dt:
                            npc.combat_target = other
                            npc.current_action = "fighting"
                            npc.state = "fighting"
                            npc.add_memory("conflict", f"Attacked my enemy {other.name}", 4)
                            self.event_log.append(f"{npc.name} attacked rival {other.name}!")
                        break

            # Title-based income: rulers draw stipend FROM kingdom treasury
            title = getattr(npc, 'title', 'commoner')
            if title in ("monarch", "duke", "lord") and 0.3 < time_norm < 0.4:
                from game.systems.demographics import TITLES
                tax_income = TITLES.get(title, {}).get("tax_income", 0)
                stipend = tax_income * dt * 0.01
                if stipend > 0 and hasattr(self, 'governance'):
                    # Find the NPC's kingdom and pay from its treasury
                    kname = self.governance.get_kingdom_at(npc.x, npc.y)
                    if kname and kname in self.governance.kingdoms:
                        kingdom = self.governance.kingdoms[kname]
                        actual_stipend = min(stipend, kingdom.treasury)
                        if actual_stipend > 0:
                            kingdom.treasury -= actual_stipend
                            npc.npc_gold += actual_stipend

            # Daily costs are handled by NpcLifecycle._daily_update — removed
            # duplicate apply_daily_costs call that was double-charging NPCs.

            # Ally defense: if any ally is fighting, join them
            # Covers: family members, same faction, same settlement, party members
            if npc.current_action not in ("fighting", "fleeing", "sleeping"):
                from game.systems.allegiance import are_allies as _are_allies, should_attack as _should_atk
                nearby = self.npc_grid.get_nearby(npc.x, npc.y, 12)
                for other in nearby:
                    if (other is not npc and other.alive and
                        other.current_action == "fighting" and
                        _are_allies(npc, other)):
                        target = getattr(other, 'combat_target', None)
                        if target and getattr(target, 'alive', False) and _should_atk(npc, target):
                            # Bravery check — not everyone rushes in
                            if npc.bravery > 0.3 or (hasattr(self, 'demographics') and
                                self.demographics.are_family(npc.name, other.name)):
                                npc.combat_target = target
                                npc.current_action = "fighting"
                                npc.state = "fighting"
                                reason = "ally" if not (hasattr(self, 'demographics') and
                                    self.demographics.are_family(npc.name, other.name)) else "family"
                                npc.add_memory("combat", f"Joined {other.name} in battle ({reason})!", 4)
                                self.event_log.append(f"{npc.name} joins {other.name} to fight!")
                                break
                                self.event_log.append(f"{npc.name} joins {other.name} in battle to defend their family!")
                            break

    def _update_npc_economic_awareness(self, npcs: List[NPC]):
        """Periodically update NPC known_info with economic conditions.

        Called once per game day so NPCs organically learn about the
        economic state of their settlement.
        """
        cur_day = self.time_sys.day
        if cur_day == getattr(self, '_last_econ_awareness_day', -1):
            return
        self._last_econ_awareness_day = cur_day

        if not hasattr(self, 'world_effects'):
            return

        active_set = self._active_npc_set

        for npc in npcs:
            if not npc.alive:
                continue
            if active_set is not None and npc.name not in active_set:
                continue
            # Only update ~20% of NPCs per day to spread the cost
            if random.random() > 0.2:
                continue

            settlement = None
            home = getattr(npc, 'home_settlement', None)
            if home:
                settlement = home
            elif getattr(npc, 'faction', ''):
                settlement = npc.faction
            else:
                loc = self.world.get_structure_at(npc.x, npc.y)
                if loc:
                    settlement = loc.name

            if not settlement:
                continue

            try:
                stores = self.world_effects.get_settlement_stores(settlement)
            except Exception:
                continue

            food = stores.get('food', 50)
            gold = stores.get('gold', 50)

            # Add economic observations to known_info
            if food <= 5:
                info = f"Food crisis in {settlement}, supplies nearly gone (day {cur_day})"
                if info not in npc.known_info:
                    npc.known_info.append(info)
                    npc.add_memory("observation",
                                   f"Noticed food supplies critically low in {settlement}", 3)
            elif food > 100:
                info = f"Abundant food in {settlement} (day {cur_day})"
                if info not in npc.known_info:
                    npc.known_info.append(info)

            if gold < 10:
                info = f"Treasury nearly empty in {settlement} (day {cur_day})"
                if info not in npc.known_info:
                    npc.known_info.append(info)
                    npc.add_memory("observation",
                                   f"Heard the treasury in {settlement} is almost broke", 2)
            elif gold > 300:
                info = f"{settlement} is wealthy and thriving (day {cur_day})"
                if info not in npc.known_info:
                    npc.known_info.append(info)

            # Keep known_info bounded
            if len(npc.known_info) > 20:
                npc.known_info = npc.known_info[-20:]

    def get_event_log(self) -> List[str]:
        """Pop accumulated event messages (also persists them to event_history)."""
        msgs = list(self.event_log)
        if msgs:
            self.event_history.extend(msgs)
            # Cap persistent history at 2000 entries
            if len(self.event_history) > 2000:
                self.event_history = self.event_history[-2000:]
        self.event_log.clear()
        return msgs
