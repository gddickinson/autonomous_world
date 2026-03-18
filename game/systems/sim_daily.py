"""Simulation daily life — death handling, economy, daily updates."""

import random
import math
from typing import List
from game.core.npc import NPC
from game.settings import *


class SimDailyMixin:
    """Daily life, death handling, and economy methods."""

    def _handle_npc_death(self, npc: NPC):
        npc.alive = False
        cause = "starvation" if npc.needs["hunger"] <= 0 else "dehydration" if npc.needs["thirst"] <= 0 else "wounds"
        self.dead_npcs.append({"name": npc.name, "profession": npc.profession, "cause": cause,
                               "time": self.time_sys.time_string})
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

    def _handle_npc_death_from_disease(self, npc, disease_name: str):
        """Handle NPC death caused by disease (called via health system callback)."""
        if not hasattr(npc, 'alive'):
            return
        npc.alive = False
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
