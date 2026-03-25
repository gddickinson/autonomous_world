"""
Military system: armies, campaigns, command hierarchy, and battle resolution.

Command hierarchy:
  Head of State (King/Warchief) → Supreme Commander
    ├── General → commands multiple armies
    │   ├── Commander/Captain → leads one army
    │   │   ├── Sergeant → leads a unit within the army
    │   │   └── Soldiers
    │   └── Commander/Captain → leads another army
    └── General → independent theater

During war, a WarCampaign coordinates multiple armies under a supreme commander.
Each army has its own commander, troops, position, and objectives.
Armies in the same campaign can combine forces for battles, share intelligence,
and coordinate marches toward the same objective.

Battle resolution uses the Lanchester combat model from warfare.py when
armies from opposing kingdoms meet within engagement range.
"""

import random
import math
from typing import Dict, List, Optional, Tuple


class Army:
    """A military unit led by a single commander."""

    def __init__(self, name: str, kingdom: str, commander_name: str,
                 x: float, y: float):
        self.name = name
        self.kingdom = kingdom
        self.commander_name = commander_name
        self.commander_rank = "captain"
        self.commander_leadership = 3
        self.x = x
        self.y = y
        self.soldiers: List[str] = []
        self.size = 0
        self.morale = 70
        self.speed = 1.5
        self.target_x: Optional[float] = None
        self.target_y: Optional[float] = None
        self.state = "idle"  # idle, marching, fighting, retreating, camping, sieging
        self.objective = ""
        self.wins = 0
        self.losses = 0
        self.campaign_id: Optional[str] = None

        # Supply system
        from game.systems.siege import ArmySupply
        self.supply = ArmySupply(0)  # initialized with 0, updated when soldiers added

        # Siege engines
        self.siege_engines: List = []

        # Camp
        self.camp = None  # ArmyCamp when camping

        # Veterancy — battles survived
        self.battles_survived = 0

    def add_soldier(self, npc_name: str):
        if npc_name not in self.soldiers:
            self.soldiers.append(npc_name)
            self.size = len(self.soldiers)

    def remove_soldier(self, npc_name: str):
        if npc_name in self.soldiers:
            self.soldiers.remove(npc_name)
            self.size = len(self.soldiers)

    @property
    def strength(self) -> float:
        return self.size * (self.morale / 50.0)


class WarCampaign:
    """A coordinated military operation with multiple armies under unified command.

    The supreme commander (usually the head of state or highest-ranking general)
    sets the overall objective. Individual army commanders execute their orders
    while coordinating with other armies in the campaign.
    """

    def __init__(self, campaign_id: str, kingdom: str,
                 supreme_commander: str, target_kingdom: str):
        self.campaign_id = campaign_id
        self.kingdom = kingdom
        self.supreme_commander = supreme_commander  # NPC name
        self.supreme_commander_rank = "general"
        self.target_kingdom = target_kingdom
        self.army_names: List[str] = []   # names of armies in this campaign
        self.objective = ""                # "conquer", "raid", "defend", "siege"
        self.target_x: float = 0.0        # campaign objective location
        self.target_y: float = 0.0
        self.state = "planning"  # planning, marching, engaging, victory, defeat
        self.start_day = 0
        self.battles_fought = 0
        self.total_casualties = 0

    @property
    def army_count(self) -> int:
        return len(self.army_names)

    def get_combined_strength(self, armies_dict: Dict[str, "Army"]) -> float:
        """Total strength of all armies in this campaign."""
        total = 0.0
        for name in self.army_names:
            army = armies_dict.get(name)
            if army and army.size > 0:
                total += army.strength
        return total

    def get_combined_size(self, armies_dict: Dict[str, "Army"]) -> int:
        """Total soldier count across all campaign armies."""
        return sum(armies_dict[n].size for n in self.army_names
                   if n in armies_dict and armies_dict[n].size > 0)


class MilitarySystem:
    """Manages armies, campaigns, and warfare with command hierarchy."""

    def __init__(self):
        self.armies: Dict[str, Army] = {}       # army_name -> Army
        self.campaigns: Dict[str, WarCampaign] = {}  # campaign_id -> WarCampaign
        self.battles_log: List[str] = []
        self.update_timer = 0.0
        self._next_campaign_id = 1

    def initialize(self, governance, npcs: list):
        """Create armies with command hierarchy for each kingdom.

        Each kingdom gets:
        - A main army led by the ruler or highest-ranking military NPC
        - Sub-armies led by knights/captains if enough troops exist
        """
        for kingdom_name, kingdom in governance.kingdoms.items():
            # Collect all military NPCs in this kingdom
            guards = []
            knights = []
            commanders = []
            for npc in npcs:
                if not npc.alive:
                    continue
                if not kingdom.contains(npc.x, npc.y):
                    continue
                title = getattr(npc, 'title', '')
                if title == 'guard':
                    guards.append(npc)
                elif title in ('knight', 'captain', 'sergeant'):
                    knights.append(npc)
                elif title in ('lord', 'duke', 'monarch'):
                    commanders.append(npc)

            all_military = guards + knights
            if not all_military:
                continue

            # Create main army under ruler
            main_army = Army(
                f"Army of {kingdom_name}",
                kingdom_name,
                kingdom.ruler_name,
                float(kingdom.castle_x),
                float(kingdom.castle_y)
            )
            main_army.commander_rank = "general"
            main_army.commander_leadership = 5

            # If enough troops, split into sub-armies led by knights
            if len(all_military) > 8 and knights:
                # Main army gets half the guards
                main_guards = guards[:len(guards)//2]
                for npc in main_guards:
                    main_army.add_soldier(npc.name)
                for npc in knights[:2]:
                    main_army.add_soldier(npc.name)

                self.armies[kingdom_name] = main_army

                # Create sub-army for each remaining knight
                remaining_guards = guards[len(guards)//2:]
                for idx, knight in enumerate(knights[2:]):
                    sub_name = f"{knight.name}'s Company"
                    sub_army = Army(
                        sub_name, kingdom_name, knight.name,
                        float(knight.x), float(knight.y))
                    sub_army.commander_rank = getattr(knight, 'title', 'captain')
                    sub_army.commander_leadership = (
                        getattr(knight, 'npc_skills', {}).get('leadership', 2))

                    # Assign some guards to this sub-army
                    per_sub = max(2, len(remaining_guards) // max(1, len(knights) - 2))
                    for g in remaining_guards[idx*per_sub:(idx+1)*per_sub]:
                        sub_army.add_soldier(g.name)

                    if sub_army.size > 0:
                        self.armies[sub_name] = sub_army
            else:
                # Small kingdom: single army
                for npc in all_military:
                    main_army.add_soldier(npc.name)
                self.armies[kingdom_name] = main_army

    def launch_campaign(self, kingdom: str, target_kingdom: str,
                        supreme_commander: str, governance) -> Optional[WarCampaign]:
        """Launch a coordinated war campaign with all available armies.

        The supreme commander (ruler/general) orders all kingdom armies
        to converge on the target.
        """
        # Find all armies belonging to this kingdom
        kingdom_armies = [name for name, army in self.armies.items()
                         if army.kingdom == kingdom and army.size > 0
                         and army.state != "retreating"]
        if not kingdom_armies:
            return None

        target_k = governance.kingdoms.get(target_kingdom)
        if not target_k:
            return None

        campaign_id = f"campaign_{self._next_campaign_id}"
        self._next_campaign_id += 1

        campaign = WarCampaign(campaign_id, kingdom, supreme_commander,
                                target_kingdom)
        campaign.objective = "conquer"
        campaign.target_x = float(target_k.castle_x)
        campaign.target_y = float(target_k.castle_y)
        campaign.state = "marching"
        campaign.start_day = 0

        # Assign all kingdom armies to this campaign
        for army_name in kingdom_armies:
            army = self.armies[army_name]
            army.campaign_id = campaign_id
            army.target_x = campaign.target_x + random.uniform(-5, 5)
            army.target_y = campaign.target_y + random.uniform(-5, 5)
            army.state = "marching"
            army.objective = f"Join campaign against {target_kingdom}"
            campaign.army_names.append(army_name)

        self.campaigns[campaign_id] = campaign
        self.battles_log.append(
            f"WAR CAMPAIGN: {kingdom} launches campaign against {target_kingdom} "
            f"with {len(kingdom_armies)} armies under {supreme_commander}")

        return campaign

    def update(self, dt: float, npcs: list, governance, world):
        """Update military movements, campaigns, and check for battles."""
        self._world = world  # stash for terrain damage in battles
        self.update_timer += dt
        if self.update_timer < 30.0:
            return
        self.update_timer = 0.0

        # Daily supply consumption and army upkeep (every ~600s = 1 day, 30s intervals)
        day_fraction = 30.0 / 600.0  # fraction of day per update tick
        for name, army in self.armies.items():
            if army.size == 0:
                continue

            # Consume food
            army.supply.food_per_day = army.size * 1.0
            army.supply.food -= army.supply.food_per_day * day_fraction
            if army.supply.food <= 0:
                army.supply.food = 0
                army.supply.days_without_food += day_fraction
                # Starvation morale penalty
                penalty = army.supply.get_morale_penalty()
                army.morale = max(5, army.morale - penalty * day_fraction)
                # Desertion
                deserters = army.supply.get_desertion_count(army.size)
                if deserters > 0:
                    for _ in range(min(deserters, len(army.soldiers))):
                        if army.soldiers:
                            army.remove_soldier(army.soldiers[-1])
                    self.battles_log.append(
                        f"{name}: {deserters} soldiers deserted (starvation)")
            else:
                army.supply.days_without_food = 0

            # Veterancy bonus to morale
            if army.battles_survived > 0:
                army.morale = min(100, army.morale + 0.5 * day_fraction)

        # March all armies toward their objectives
        for name, army in self.armies.items():
            if army.state == "marching" and army.target_x is not None:
                dx = army.target_x - army.x
                dy = army.target_y - army.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 5:
                    army.state = "idle"
                    army.target_x = None
                    army.target_y = None
                else:
                    army.x += (dx / dist) * army.speed
                    army.y += (dy / dist) * army.speed
                    for npc in npcs:
                        if npc.name in army.soldiers and npc.alive:
                            npc.target_x = army.x + random.uniform(-3, 3)
                            npc.target_y = army.y + random.uniform(-3, 3)

        # Check for battles — combine same-kingdom armies nearby
        army_names = list(self.armies.keys())
        fought = set()
        for i, name1 in enumerate(army_names):
            if name1 in fought:
                continue
            for name2 in army_names[i+1:]:
                if name2 in fought:
                    continue
                army1 = self.armies[name1]
                army2 = self.armies[name2]
                if army1.size == 0 or army2.size == 0:
                    continue
                if army1.kingdom == army2.kingdom:
                    continue  # same side

                dist = math.sqrt((army1.x - army2.x)**2 + (army1.y - army2.y)**2)
                if dist > 15:
                    continue

                # Check if at war (check both kingdom names)
                at_war = False
                rel = governance.get_diplomacy(army1.kingdom, army2.kingdom)
                if rel and rel.status == "at_war":
                    at_war = True

                if not at_war:
                    continue

                # Combine all same-side armies nearby for the battle
                side1_armies = [army1]
                side2_armies = [army2]
                for other_name, other_army in self.armies.items():
                    if other_name in (name1, name2) or other_army.size == 0:
                        continue
                    d1 = math.sqrt((other_army.x - army1.x)**2 +
                                   (other_army.y - army1.y)**2)
                    d2 = math.sqrt((other_army.x - army2.x)**2 +
                                   (other_army.y - army2.y)**2)
                    if d1 < 20 and other_army.kingdom == army1.kingdom:
                        side1_armies.append(other_army)
                    elif d2 < 20 and other_army.kingdom == army2.kingdom:
                        side2_armies.append(other_army)

                self._resolve_combined_battle(side1_armies, side2_armies,
                                               npcs, governance)
                for a in side1_armies + side2_armies:
                    fought.add(a.name)
                break

        # Kingdoms at war: launch campaigns if not already active
        for (k1, k2), rel in governance.diplomacy.items():
            if rel.status != "at_war":
                continue

            # Check if kingdom already has an active campaign
            has_campaign_k1 = any(c.kingdom == k1 and c.state in ("marching", "engaging")
                                  for c in self.campaigns.values())
            has_campaign_k2 = any(c.kingdom == k2 and c.state in ("marching", "engaging")
                                  for c in self.campaigns.values())

            if not has_campaign_k1 and k1 in governance.kingdoms:
                ruler = governance.kingdoms[k1].ruler_name
                # Only launch if we have enough forces
                total_size = sum(a.size for a in self.armies.values()
                                if a.kingdom == k1 and a.size > 0)
                if total_size >= 3:
                    self.launch_campaign(k1, k2, ruler, governance)

            if not has_campaign_k2 and k2 in governance.kingdoms:
                ruler = governance.kingdoms[k2].ruler_name
                total_size = sum(a.size for a in self.armies.values()
                                if a.kingdom == k2 and a.size > 0)
                if total_size >= 3:
                    self.launch_campaign(k2, k1, ruler, governance)

        # Update campaign states
        for cid, campaign in list(self.campaigns.items()):
            alive_armies = [n for n in campaign.army_names
                           if n in self.armies and self.armies[n].size > 0]
            if not alive_armies:
                campaign.state = "defeat"
                self.battles_log.append(
                    f"Campaign {cid}: {campaign.kingdom}'s campaign against "
                    f"{campaign.target_kingdom} has failed — all armies destroyed")
                continue
            campaign.army_names = alive_armies

    def _resolve_combined_battle(self, side1: List[Army], side2: List[Army],
                                  npcs: list, governance):
        """Resolve a battle with multiple armies on each side.

        Combines all armies per side into a single BattleArmy for the
        Lanchester simulation, then distributes casualties back to
        individual armies proportionally.
        """
        from game.systems.warfare import (
            BattleField, BattleArmy, TroopUnit, Commander,
            npc_to_unit_type, WarEconomy,
        )

        npc_map = {n.name: n for n in npcs if n.alive}

        def _build_combined(armies: List[Army], is_defender: bool) -> Tuple[BattleArmy, int]:
            units = []
            total_soldiers = 0
            best_leadership = 0
            best_commander = "Unknown"

            for army in armies:
                soldier_npcs = [npc_map[s] for s in army.soldiers if s in npc_map]
                melee = sum(1 for n in soldier_npcs
                           if getattr(n, 'char_class', '') in
                           ('Fighter', 'Barbarian', 'Paladin', 'Ranger',
                            'Monk'))
                ranged = sum(1 for n in soldier_npcs
                            if getattr(n, 'char_class', '') in
                            ('Wizard', 'Sorcerer', 'Warlock', 'Rogue',
                             'Bard'))
                other = len(soldier_npcs) - melee - ranged
                if melee > 0:
                    units.append(TroopUnit("infantry_sword", melee))
                if ranged > 0:
                    units.append(TroopUnit("archer_longbow", ranged))
                if other > 0:
                    units.append(TroopUnit("infantry_spear", other))

                total_soldiers += army.size
                if army.commander_leadership > best_leadership:
                    best_leadership = army.commander_leadership
                    best_commander = army.commander_name

            if not units and total_soldiers > 0:
                units.append(TroopUnit("infantry_sword", total_soldiers))
            elif not units:
                units.append(TroopUnit("infantry_sword", 1))

            kingdom = armies[0].kingdom if armies else "Unknown"
            cmd = Commander(name=best_commander, leadership=best_leadership)
            combined_name = f"Forces of {kingdom}"
            if len(armies) > 1:
                combined_name += f" ({len(armies)} armies)"
            return BattleArmy(combined_name, units, cmd,
                               is_defender=is_defender), total_soldiers

        battle_army1, size1 = _build_combined(side1, False)
        battle_army2, size2 = _build_combined(side2, True)

        # Log the engagement
        s1_names = ", ".join(a.name for a in side1[:3])
        s2_names = ", ".join(a.name for a in side2[:3])
        self.battles_log.append(
            f"ENGAGEMENT: [{s1_names}] ({size1} troops) vs [{s2_names}] ({size2} troops)")

        # Run Lanchester battle
        battlefield = BattleField(battle_army1, battle_army2, terrain="plains")
        result = battlefield.resolve(max_rounds=10)

        if result["winner"] == battle_army1.name:
            winners, losers = side1, side2
        else:
            winners, losers = side2, side1

        w_casualties = result["attacker_casualties"] if winners == side1 else result["defender_casualties"]
        l_casualties = result["defender_casualties"] if winners == side1 else result["attacker_casualties"]

        # Distribute casualties proportionally across individual armies
        self._distribute_army_casualties(losers, l_casualties, npcs, death_rate=0.3)
        self._distribute_army_casualties(winners, w_casualties, npcs, death_rate=0.1)

        # Update army states
        for a in winners:
            a.wins += 1
            a.morale = min(100, a.morale + 10)
        for a in losers:
            a.losses += 1
            a.morale = max(10, a.morale - 20)
            a.state = "retreating"

        # Track duty kills for all winning commanders
        for a in winners:
            cmd_npc = npc_map.get(a.commander_name)
            if cmd_npc:
                if not hasattr(cmd_npc, 'duty_kills'):
                    cmd_npc.duty_kills = 0
                share = l_casualties // max(1, len(winners))
                cmd_npc.duty_kills += share

        # Plunder and territory
        loser_kingdom = losers[0].kingdom if losers else None
        winner_kingdom = winners[0].kingdom if winners else None
        if loser_kingdom and winner_kingdom:
            lk = governance.kingdoms.get(loser_kingdom)
            wk = governance.kingdoms.get(winner_kingdom)
            if lk and wk:
                plunder = min(getattr(lk, 'treasury', 0) * 0.3,
                             50 + result.get("attacker_remaining", 0) * 2)
                lk.treasury = max(0, getattr(lk, 'treasury', 0) - plunder)
                wk.treasury = getattr(wk, 'treasury', 0) + plunder
                if plunder > 0:
                    self.battles_log.append(
                        f"{winner_kingdom} plundered {plunder:.0f}g from {loser_kingdom}")

            # Territory transfer if loser's army is destroyed
            total_loser = sum(a.size for a in losers)
            if total_loser == 0:
                self._conquer_territory(winners[0], losers[0], governance)

        # Veterancy — surviving troops gain battle experience
        for a in winners:
            a.battles_survived += 1
            # Surviving NPCs gain XP
            for s_name in a.soldiers:
                npc = npc_map.get(s_name)
                if npc and npc.alive and hasattr(npc, 'gain_xp'):
                    npc.gain_xp(20)  # battle XP

        # Diplomatic ripple — other factions react to the battle outcome
        if winner_kingdom and loser_kingdom:
            for (dk1, dk2), drel in governance.diplomacy.items():
                # Allies of loser become more hostile to winner
                loser_rel = governance.get_diplomacy(loser_kingdom, dk1)
                if loser_rel and loser_rel.status in ("allied", "friendly"):
                    if dk1 != winner_kingdom and dk2 != winner_kingdom:
                        winner_rel = governance.get_diplomacy(winner_kingdom, dk1)
                        if not winner_rel:
                            winner_rel = governance.get_diplomacy(winner_kingdom, dk2)
                        if winner_rel:
                            winner_rel.trust = max(-100, winner_rel.trust - 15)
                            winner_rel.update_status()

                # Weak factions may bandwagon with the winner
                if (dk1 == winner_kingdom or dk2 == winner_kingdom):
                    other = dk2 if dk1 == winner_kingdom else dk1
                    other_k = governance.kingdoms.get(other)
                    winner_k_obj = governance.kingdoms.get(winner_kingdom)
                    if other_k and winner_k_obj:
                        winner_str = sum(a.size for a in self.armies.values()
                                        if a.kingdom == winner_kingdom)
                        other_str = sum(a.size for a in self.armies.values()
                                       if a.kingdom == other)
                        if winner_str > other_str * 2 and drel.status == "hostile":
                            drel.trust = min(100, drel.trust + 10)
                            drel.update_status()

        # Update campaign state
        for cid, camp in self.campaigns.items():
            if any(a.name in camp.army_names for a in winners):
                camp.battles_fought += 1
                total_loser_remaining = sum(a.size for a in losers)
                if total_loser_remaining == 0:
                    camp.state = "victory"
                    self.battles_log.append(
                        f"Campaign {cid}: VICTORY for {camp.kingdom}!")
            elif any(a.name in camp.army_names for a in losers):
                camp.battles_fought += 1
                total_winner_remaining = sum(a.size for a in winners if a.name in camp.army_names)
                if total_winner_remaining == 0:
                    camp.state = "defeat"

        rounds = result.get("rounds", 0)
        self.battles_log.append(
            f"Battle resolved in {rounds} rounds: {winner_kingdom or '?'} wins "
            f"(casualties: {w_casualties} vs {l_casualties})")

        # --- Terrain damage from battle ---
        _world = getattr(self, '_world', None)
        if _world:
            from game.systems.conflict_damage import (
                damage_farmland, damage_buildings, scorch_terrain,
                BATTLE_FARM_DAMAGE, BATTLE_BUILDING_DESTROY_CHANCE,
                _find_nearest_settlement_name,
            )
            # Use the position of the first army that engaged
            bx = side1[0].x if side1 else 0
            by = side1[0].y if side1 else 0
            farm_dmg = damage_farmland(_world, bx, by,
                                       count_range=BATTLE_FARM_DAMAGE)
            bldg_dmg = damage_buildings(_world, bx, by,
                                        destroy_chance=BATTLE_BUILDING_DESTROY_CHANCE)
            scorch = scorch_terrain(_world, bx, by, count=3)
            loc = _find_nearest_settlement_name(_world, bx, by) or f"({int(bx)},{int(by)})"
            if farm_dmg > 0:
                self.battles_log.append(
                    f"Battle devastated {farm_dmg} farmland tiles near {loc}")
            if bldg_dmg:
                self.battles_log.append(
                    f"Buildings damaged in battle near {loc}!")
            if scorch > 0:
                self.battles_log.append(
                    f"Battle fires scorched {scorch} forest tiles near {loc}")

    def _distribute_army_casualties(self, armies: List[Army], total_casualties: int,
                                     npcs: list, death_rate: float = 0.3):
        """Distribute casualties across multiple armies proportionally."""
        total_size = sum(a.size for a in armies)
        if total_size == 0:
            return

        npc_map = {n.name: n for n in npcs}
        for army in armies:
            share = max(0, int(total_casualties * army.size / max(1, total_size)))
            applied = 0
            for soldier_name in list(army.soldiers):
                if applied >= share:
                    break
                npc = npc_map.get(soldier_name)
                if npc and npc.alive:
                    npc.hp = max(1, npc.hp - random.randint(10, 30))
                    if random.random() < death_rate:
                        npc._death_cause = "combat"
                        npc.alive = False
                        npc.hp = 0
                    army.remove_soldier(soldier_name)
                    applied += 1

    def _resolve_battle(self, army1: Army, army2: Army, npcs: list, governance):
        """Resolve a battle using the full Lanchester combat model from warfare.py.

        Uses proper unit types, formations, terrain, commander bonuses, and
        rock-paper-scissors matchups for realistic battle simulation.
        """
        from game.systems.warfare import (
            BattleField, BattleArmy, TroopUnit, Commander,
            build_army_from_npcs, npc_to_unit_type, WarEconomy,
        )

        # Build proper BattleArmy objects from NPC soldier lists
        npc_map = {n.name: n for n in npcs if n.alive}

        def _build_army(army: Army, is_defender: bool) -> BattleArmy:
            soldier_npcs = [npc_map[s] for s in army.soldiers if s in npc_map]
            if not soldier_npcs:
                # Fallback: create generic infantry
                unit = TroopUnit("infantry_sword", max(1, army.size))
                cmd = Commander(name=army.commander_name, leadership=2)
                return BattleArmy(army.name, [unit], cmd, is_defender=is_defender)
            return build_army_from_npcs(army.name, soldier_npcs,
                                        npc_map.get(army.commander_name),
                                        is_defender)

        battle_army1 = _build_army(army1, is_defender=False)
        battle_army2 = _build_army(army2, is_defender=True)

        # Determine terrain from world position
        terrain = "plains"  # default
        # Could look up actual terrain from world tiles here

        # Run the full Lanchester battle simulation
        battlefield = BattleField(battle_army1, battle_army2,
                                   terrain=terrain, is_siege=False)
        result = battlefield.resolve(max_rounds=10)

        if result["winner"] == army1.name:
            winner, loser = army1, army2
        else:
            winner, loser = army2, army1

        winner_casualties = result["attacker_casualties"] if winner == army1 else result["defender_casualties"]
        loser_casualties = result["defender_casualties"] if winner == army1 else result["attacker_casualties"]

        # Apply casualties to loser
        casualties_applied = 0
        for npc in npcs:
            if casualties_applied >= loser_casualties:
                break
            if npc.name in loser.soldiers and npc.alive:
                npc.hp = max(1, npc.hp - random.randint(10, 30))
                if random.random() < 0.3:  # 30% chance of death per casualty
                    npc._death_cause = "combat"
                    npc.alive = False
                    npc.hp = 0
                loser.remove_soldier(npc.name)
                casualties_applied += 1

        # Winner takes some losses too
        w_casualties = 0
        for npc in npcs:
            if w_casualties >= winner_casualties:
                break
            if npc.name in winner.soldiers and npc.alive:
                npc.hp = max(1, npc.hp - random.randint(5, 15))
                w_casualties += 1

        winner.wins += 1
        loser.losses += 1
        loser.morale = max(10, loser.morale - 20)
        winner.morale = min(100, winner.morale + 10)
        loser.state = "retreating"

        # Track duty kills for the winning commander
        winner_commander_npc = npc_map.get(winner.commander_name)
        if winner_commander_npc:
            if not hasattr(winner_commander_npc, 'duty_kills'):
                winner_commander_npc.duty_kills = 0
            winner_commander_npc.duty_kills += casualties_applied
            winner_commander_npc.add_memory("military",
                f"Led {winner.name} to victory! {casualties_applied} enemy casualties.", 4)

        # Plunder — winner takes gold from loser's kingdom
        loser_kingdom = governance.kingdoms.get(loser.kingdom)
        winner_kingdom = governance.kingdoms.get(winner.kingdom)
        if loser_kingdom and winner_kingdom:
            from game.systems.warfare import WarEconomy
            plunder = WarEconomy.calculate_plunder(
                getattr(loser_kingdom, 'treasury', 0),
                result.get("attacker_remaining", winner.size),
                result.get("defender_remaining", loser.size))
            loser_kingdom.treasury = max(0, getattr(loser_kingdom, 'treasury', 0) - plunder)
            winner_kingdom.treasury = getattr(winner_kingdom, 'treasury', 0) + plunder
            if plunder > 0:
                self.battles_log.append(f"{winner.kingdom} plundered {plunder:.0f}g from {loser.kingdom}")

        # Territory transfer — if loser army is destroyed, winner claims territory
        if loser.size == 0 and loser_kingdom:
            self._conquer_territory(winner, loser, governance)

        # Battle log with detail from Lanchester simulation
        rounds = result.get("rounds", 0)
        msg = (f"Battle of {rounds} rounds! {winner.name} ({result.get('attacker_remaining', winner.size)} remaining) "
               f"defeats {loser.name} ({result.get('defender_remaining', loser.size)} remaining)! "
               f"Casualties: attacker={winner_casualties}, defender={loser_casualties}")
        self.battles_log.append(msg)

    def _conquer_territory(self, winner: Army, loser: Army, governance):
        """Transfer territory from defeated kingdom to victor."""
        loser_k = governance.kingdoms.get(loser.kingdom)
        winner_k = governance.kingdoms.get(winner.kingdom)
        if not loser_k or not winner_k:
            return

        # Transfer settlements from loser to winner
        loser_settlements = getattr(loser_k, 'settlements', [])
        if loser_settlements:
            transferred = loser_settlements.pop(0) if loser_settlements else None
            if transferred:
                winner_settlements = getattr(winner_k, 'settlements', [])
                winner_settlements.append(transferred)
                winner_k.settlements = winner_settlements
                self.battles_log.append(
                    f"{winner.kingdom} conquered {transferred} from {loser.kingdom}!")

        # Morale impact
        loser_k.public_morale = max(0, getattr(loser_k, 'public_morale', 50) - 30)
        winner_k.public_morale = min(100, getattr(winner_k, 'public_morale', 50) + 15)

        # Diplomatic consequences — other kingdoms react
        for (k1, k2), rel in governance.diplomacy.items():
            if k1 == winner.kingdom or k2 == winner.kingdom:
                # Neighbors become wary of the conqueror
                if rel.status not in ("at_war", "allied"):
                    rel.trust = max(-100, rel.trust - 10)
                    rel.update_status()

        self.battles_log.append(
            f"{loser.kingdom} has fallen to {winner.kingdom}!")

    def get_battle_log(self) -> List[str]:
        msgs = list(self.battles_log)
        self.battles_log.clear()
        return msgs
