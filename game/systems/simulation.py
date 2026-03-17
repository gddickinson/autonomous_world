"""
Deep NPC simulation: needs, LLM-driven decisions, actions, conversations,
world modification, information spreading, and world events.
"""

import itertools
import math
import random
import re
import time
from typing import List, Optional, Dict, Tuple, Any
from game.settings import *
from game.core.npc import NPC
from game.core.creature import Creature
from game.core.player import Player
from game.core.items import Item, make_item, FOOD_ITEMS, DRINK_ITEMS
from game.ai.llm import LLMManager
from game.ai.prompts import (Prompts, mock_npc_decision, build_npc_context,
                              share_gossip, pick_contextual_topic)


# ================================
# CONVERSATIONS
# ================================

class Conversation:
    """An active conversation between two NPCs."""
    def __init__(self, npc1: NPC, npc2: NPC):
        self.npc1 = npc1
        self.npc2 = npc2
        self.timer = random.uniform(3.0, 6.0)
        self.started = time.time()
        self.info_exchanged: List[str] = []


# ================================
# WORLD EVENTS
# ================================

class WorldEvent:
    """A random event affecting the world."""
    def __init__(self, name: str, description: str, x: float, y: float,
                 radius: float, duration: float, effects: Dict[str, Any]):
        self.name = name
        self.description = description
        self.x = x
        self.y = y
        self.radius = radius
        self.duration = duration
        self.effects = effects
        self.started = time.time()
        self.announced = False

    def affects(self, entity) -> bool:
        dx = entity.x - self.x
        dy = entity.y - self.y
        return dx * dx + dy * dy <= self.radius * self.radius


EVENT_TEMPLATES = [
    {"name": "Drought", "desc": "A harsh drought grips the land. Water sources dry up and thirst grows faster.",
     "radius": 60, "duration": 120, "effects": {"thirst_mult": 2.0}},
    {"name": "Storm", "desc": "A violent storm sweeps through! Seek shelter.",
     "radius": 50, "duration": 60, "effects": {"speed_mult": 0.5, "rest_mult": 1.5}},
    {"name": "Bountiful Harvest", "desc": "The land is blessed with abundance. Crops grow faster.",
     "radius": 40, "duration": 90, "effects": {"hunger_mult": 0.5}},
    {"name": "Plague", "desc": "A sickness spreads through the area. Everyone loses health slowly.",
     "radius": 45, "duration": 80, "effects": {"plague_dps": 0.5}},
    {"name": "Festival", "desc": "A joyous festival! Everyone's spirits are lifted.",
     "radius": 30, "duration": 60, "effects": {"social_boost": 1.0}},
    {"name": "Wolf Pack", "desc": "A pack of wolves has been spotted prowling nearby.",
     "radius": 35, "duration": 90, "effects": {"danger": "wolves"}},
    {"name": "Merchant Caravan", "desc": "A traveling merchant caravan has arrived!",
     "radius": 20, "duration": 60, "effects": {"trade_bonus": True}},
    {"name": "Earthquake", "desc": "The ground shakes! Some structures may be damaged.",
     "radius": 50, "duration": 10, "effects": {"destroy_chance": 0.1}},
]


# ================================
# SIMULATION MANAGER
# ================================

class SimulationManager:
    """Orchestrates deep NPC simulation: needs, decisions, actions, events."""

    def __init__(self, world_mgr, world, llm: LLMManager, time_sys):
        self.world_mgr = world_mgr
        self.world = world
        self.llm = llm
        self.time_sys = time_sys

        self.conversations: List[Conversation] = []
        self.events: List[WorldEvent] = []
        self.event_timer = random.uniform(30, 90)
        self.dead_npcs: List[Dict] = []
        self.event_log: List[str] = []
        self.event_history: List[str] = []  # persistent log (never cleared by get_event_log)

        # For chunked worlds, limit structure scanning to near spawn
        from game.world.world import ChunkedWorld
        _is_chunked = isinstance(world, ChunkedWorld)
        if _is_chunked:
            sp = world.spawn_point
            structures = [s for s in world.structures
                          if abs(s.x - sp[0]) <= 500 and abs(s.y - sp[1]) <= 500]
        else:
            structures = world.structures

        # Social system
        from game.systems.social import SocialSystem
        self.social = SocialSystem()
        self.social.initialize_relationships(world_mgr.npcs)

        # Economy (old simple system for backward compat)
        # Register ALL settlement markets globally, not just nearby ones
        from game.systems.economy import EconomySystem
        self.economy = EconomySystem()
        all_structures = world.structures
        for s in all_structures:
            if s.kind in ("village", "town", "city", "hamlet", "castle"):
                self.economy.register_settlement(s.name, s.kind)

        # World Economy (new macro-economic simulation with trade)
        from game.systems.world_economy import WorldMarket
        self.world_market = WorldMarket()
        self.world_market.initialize(all_structures)

        # Demographics (ages, families, feudal hierarchy)
        from game.systems.demographics import DemographicsSystem
        self.demographics = DemographicsSystem()
        self.demographics.initialize(world_mgr.npcs, structures)

        # Wire demographics death callback to population counters + soul + children grief
        def _on_demo_death(npc, cause):
            if hasattr(self, 'population'):
                nearest = self.population._nearest_settlement(npc.x, npc.y)
                if nearest and nearest in self.population.settlements:
                    self.population.settlements[nearest].deaths_today += 1
            self.event_log.append(f"{npc.name} the {getattr(npc, 'profession', '?')} has died from {cause}.")
            # Release soul on death
            if hasattr(self, 'souls'):
                death_type = "natural" if cause == "old age" else "violent"
                self.souls.on_death(npc, death_type, self.time_sys.time)
            # Trigger family grief via child system
            if hasattr(self, 'child_system'):
                self.child_system.trigger_family_grief(npc, self.world_mgr.npcs)
            # Bury via burial system
            if hasattr(self, 'burial'):
                death_cat = "natural" if cause == "old age" else "disease" if cause == "plague" else cause
                self.burial.on_death(npc, death_cat, self.time_sys.time_string,
                                     self.time_sys.day, self.world)
            # Grief amplification for loved ones (social dynamics)
            if hasattr(self, 'social_dynamics'):
                _grid = self.npc_grid if hasattr(self, 'npc_grid') else None
                self.social_dynamics.on_npc_death(
                    npc, self.world_mgr.npcs, npc_grid=_grid)
        self.demographics.on_death = _on_demo_death

        # Burial system (churchyards and graves)
        from game.systems.burial import BurialSystem
        self.burial = BurialSystem()
        self.burial.initialize_churchyards(world)

        # Initialize creature needs (living system)
        from game.systems.living import initialize_creature_needs
        for creature in world_mgr.creatures:
            initialize_creature_needs(creature)

        # Apply race-specific need modifiers to NPCs
        from game.systems.living import RACE_NEED_MODS
        for npc in world_mgr.npcs:
            race = getattr(npc, 'race', 'Human')
            mods = RACE_NEED_MODS.get(race, {})
            if not hasattr(npc, 'need_multipliers'):
                npc.need_multipliers = {}
            npc.need_multipliers = {
                "hunger": mods.get("hunger", 1.0),
                "thirst": mods.get("thirst", 1.0),
                "rest": mods.get("rest", 1.0),
            }

        # Governance (kingdoms, diplomacy, taxation)
        from game.systems.governance import GovernanceSystem
        self.governance = GovernanceSystem()
        self.governance.initialize(structures, world_mgr.npcs, world)

        # Faction reputation (player standing with kingdoms)
        from game.systems.factions import FactionSystem
        self.faction_system = FactionSystem()
        self.faction_system.initialize(list(self.governance.kingdoms.keys()))

        # Quest system (procedural quests, bounty boards, chains)
        from game.systems.quests import QuestSystem
        self.quest_system = QuestSystem()
        # Register bounty boards at taverns and settlements with taverns
        for s in structures:
            if s.kind in ("tavern",):
                kingdom_name = self.governance.get_kingdom_at(s.x, s.y) or ""
                self.quest_system.register_bounty_board(s.name, kingdom_name)
            elif s.kind in ("village", "town", "city"):
                # Settlements also get boards (accessible at tavern within)
                kingdom_name = self.governance.get_kingdom_at(s.x, s.y) or ""
                self.quest_system.register_bounty_board(s.name, kingdom_name)

        # Military (armies, battles)
        from game.systems.military import MilitarySystem
        self.military = MilitarySystem()
        self.military.initialize(self.governance, world_mgr.npcs)

        # Settlement defenses — fortifications for each settlement
        from game.systems.siege import SettlementDefenses
        self.settlement_defenses: Dict = {}
        for s in structures:
            if s.kind in ("village", "town", "city", "castle", "hamlet",
                          "orc_stronghold", "goblin_warren", "kobold_mine",
                          "bandit_camp", "gnoll_den", "undead_crypt"):
                self.settlement_defenses[s.name] = SettlementDefenses(s.name, s.kind)

        # Trade (caravans, trade routes)
        from game.systems.trade import TradeSystem
        self.trade = TradeSystem()
        self.trade.initialize(structures)

        # Spatial hash grids for O(1) nearby lookups (CRITICAL for performance)
        from game.systems.spatial import SpatialGrid
        self.creature_grid = SpatialGrid(cell_size=15)
        self.npc_grid = SpatialGrid(cell_size=15)

        # Construction
        from game.systems.construction import ConstructionSystem
        self.construction = ConstructionSystem()

        # Culture & Religion
        from game.systems.culture import CultureSystem
        self.culture = CultureSystem()
        self.culture.initialize(structures, world_mgr.npcs)

        # God AI Pantheon (divine beings that observe, intervene, petition)
        from game.systems.pantheon import PantheonSystem
        self.pantheon = PantheonSystem(llm_manager=llm)
        self.pantheon.count_worshippers(world_mgr.npcs)

        # Heresy & Religious Schism (conversion, cults, schisms, atheism)
        from game.systems.heresy import HeresySystem
        self.heresy = HeresySystem()

        # Technology
        from game.systems.technology import TechSystem
        self.technology = TechSystem()
        self.technology.initialize(structures)

        # Body damage system (detailed body parts, wounds, healing)
        from game.systems.body_damage import BodyDamageSystem
        self.body_damage = BodyDamageSystem()

        # Durability (destructible objects)
        from game.systems.durability import DurabilitySystem
        self.durability = DurabilitySystem()
        # Share rubble tracker with world for pathfinding
        world._rubble_tracker = self.durability.rubble

        # Territory (land ownership, Civilization-style expansion)
        from game.systems.territory import TerritorySystem
        self.territory = TerritorySystem()
        self.territory.initialize(structures, world_mgr.npcs,
                                  world_mgr.creatures, self.governance, world)

        # Functional zones (workshops, kitchens, training grounds, etc.)
        from game.world.zones import ZoneSystem
        self.zones = ZoneSystem()
        if _is_chunked:
            self.zones.initialize(structures, world,
                                  near=world.spawn_point, radius=500)
        else:
            self.zones.initialize(structures, world)

        # Information system (replaces broadcast notifications)
        from game.systems.information import InformationSystem
        self.info = InformationSystem()

        # Generate backstories for all NPCs (uses actual world state)
        from game.systems.backstory import generate_all_backstories
        regions = getattr(world, 'regions', None)
        generate_all_backstories(world_mgr.npcs, structures, regions,
                                self.governance, self.demographics)

        # Assign home_settlement to all NPCs so the wage system can find
        # their settlement's gold stores.  Uses nearest settlement by distance.
        settlement_list = [s for s in structures
                           if s.kind in ("hamlet", "village", "town", "city", "castle")]
        for npc in world_mgr.npcs:
            if getattr(npc, 'home_settlement', None):
                continue
            best_name = None
            best_dist = float('inf')
            for s in settlement_list:
                d = math.sqrt((npc.home_x - s.x) ** 2 + (npc.home_y - s.y) ** 2)
                if d < best_dist:
                    best_dist = d
                    best_name = s.name
            if best_name and best_dist < 80:
                npc.home_settlement = best_name

        # Ecology (seasons, weather, crop growth, ecosystem)
        from game.systems.ecology import EcologySystem
        self.ecology = EcologySystem()
        self.ecology.set_world_manager(world_mgr)

        # Global Climate Model (pressure systems, temperature, precipitation)
        from game.systems.climate import ClimateModel
        _plan = getattr(world, 'plan', None)
        self.climate = ClimateModel(
            world.width, world.height,
            seed=getattr(world, 'seed', 0),
            world_plan=_plan,
        )
        self._climate_last_day = -1

        # Population dynamics (birth, migration, settlement growth)
        from game.systems.population import PopulationSystem
        self.population = PopulationSystem()
        self.population.initialize(structures, world_mgr.npcs)

        # Abstract simulation (distant settlements run as statistics)
        from game.systems.abstract_sim import AbstractSimulation
        self.abstract = AbstractSimulation()
        self.abstract.initialize(structures, world_mgr.npcs)

        # Give WorldManager a reference so dormancy can call simulate_dormant_npc
        world_mgr._abstract_sim_ref = self.abstract

        # Give WorldManager a reference to the simulation so activate_zone
        # can register new settlements in trade/economy systems
        world_mgr._simulation_ref = self

        # World effects — translates abstract sim events into tile changes
        from game.systems.world_effects import WorldEffects
        self.world_effects = WorldEffects(world)

        # Deploy initial garrisons from kingdom data
        if hasattr(world, 'plan'):
            for k in world.plan.kingdoms:
                for sname in k.get("territory_settlements", []):
                    # Capital gets more troops, border settlements too
                    troops = 3
                    if sname == k.get("capital_settlement"):
                        troops = 10
                    self.world_effects.deploy_troops(
                        k["name"], sname, troops)

        # Regional goods — replace generic stockpiles with specialized
        # goods based on kingdom, specialization, trade routes, and ruins.
        if hasattr(world, 'plan'):
            from game.systems.regional_goods import initialize_regional_goods
            initialize_regional_goods(
                world.plan, self.world_effects, self.trade, world_mgr.npcs)

        # Memory decay and compaction
        from game.systems.memory import MemoryManager
        self.memory_mgr = MemoryManager()

        # World knowledge map (shared exploration data)
        from game.systems.world_map import WorldKnowledgeMap
        self.world_map = WorldKnowledgeMap()
        self.world_map.initialize(world, structures)

        # Fire system (hearths, campfires, forges)
        from game.systems.physical import FireManager
        self.fire_mgr = FireManager()
        self.fire_mgr.initialize_settlement_fires(structures, world)

        # Banking system
        from game.systems.banking import BankingSystem
        self.banking = BankingSystem()

        # Political intrigue (NPC power struggles)
        from game.systems.intrigue import IntrigueSystem
        self.intrigue = IntrigueSystem()

        # Monster societies (intelligent creature governance)
        from game.systems.monster_society import MonsterSocietyManager
        self.monster_societies = MonsterSocietyManager()
        self.monster_societies.initialize(world_mgr.creatures, world)

        # Monster settlements — give intelligent monsters real towns with NPCs
        from game.world.monster_settlements import generate_monster_settlements
        import random as _rng_mod
        monster_results = generate_monster_settlements(
            world, _rng_mod.Random(getattr(world, 'seed', 0)),
            self.monster_societies.groups)
        for struct, npc_spawns, kingdom_data in monster_results:
            # Spawn monster NPCs
            from game.data.dnd import random_npc_class_and_race
            from game.core.npc import NPC
            name_pool = ["Grak", "Thokk", "Urzul", "Mogash", "Shagar", "Krag",
                         "Durz", "Narg", "Grish", "Bork", "Snarl", "Fang",
                         "Rotgut", "Skullcrusher", "Bonesnapper", "Gorefist",
                         "Darkfang", "Ironjaw", "Bloodaxe", "Steelclaw"]
            _rng_mod.shuffle(name_pool)
            for i, spawn in enumerate(npc_spawns):
                name = name_pool[i % len(name_pool)]
                if i >= len(name_pool):
                    name = f"{name}_{i // len(name_pool)}"
                char_class = spawn.get("class", "Fighter")
                race = spawn.get("race", "Half-Orc")
                level = _rng_mod.randint(2, 6)
                npc = NPC(spawn["x"], spawn["y"], name, char_class,
                         char_class=char_class, race=race, level=level)
                npc.home_x = spawn["x"]
                npc.home_y = spawn["y"]
                npc.faction = kingdom_data["name"]
                if spawn.get("is_ruler"):
                    npc.is_ruler = True
                    npc.title = kingdom_data["ruler_title"]
                world_mgr.npcs.append(npc)

            # Register as kingdom in governance
            if hasattr(self, 'governance'):
                from game.systems.governance import Kingdom
                # Find the ruler NPC name from the spawned NPCs
                ruler_name = ""
                for i, spawn in enumerate(npc_spawns):
                    if spawn.get("is_ruler"):
                        ruler_name = name_pool[i % len(name_pool)]
                        if i >= len(name_pool):
                            ruler_name = f"{ruler_name}_{i // len(name_pool)}"
                        break
                k = Kingdom(kingdom_data["name"], kingdom_data["x"],
                            kingdom_data["y"], ruler_name)
                k.governing_style = kingdom_data["governance_style"]
                k.population = kingdom_data["population"]
                k.territory_radius = struct.radius + 20
                self.governance.kingdoms[kingdom_data["name"]] = k

        # Establish diplomacy between monster and human kingdoms
        if hasattr(self, 'governance'):
            from game.systems.governance import DiplomaticRelation
            human_kingdoms = [k for k, v in self.governance.kingdoms.items()
                             if getattr(v, 'governing_style', '') == 'feudalism']
            for mr in monster_results:
                _, _, mkdata = mr
                mk_name = mkdata["name"]
                for hk in human_kingdoms:
                    key = (min(hk, mk_name), max(hk, mk_name))
                    if key not in self.governance.diplomacy:
                        rel = DiplomaticRelation()
                        if mkdata.get("hostile_to_humans", True):
                            rel.trust = random.randint(-70, -30)
                        else:
                            rel.trust = random.randint(-20, 10)  # tradeable species
                        if mkdata.get("can_trade", False) and rel.trust > -40:
                            rel.trade_agreement = True
                        rel.update_status()
                        self.governance.diplomacy[key] = rel

        # Social class assignment
        from game.systems.social_class import assign_social_class
        for npc in world_mgr.npcs:
            gov_style = "feudalism"  # default
            # Find NPC's kingdom governance
            if hasattr(self, 'governance'):
                for kname, kingdom in self.governance.kingdoms.items():
                    gov_style = getattr(kingdom, 'governing_style', 'feudalism')
                    break  # use first kingdom for now
            assign_social_class(npc, gov_style, "")

        # Exhaustion & Sleep system
        from game.systems.exhaustion import ExhaustionSystem
        self.exhaustion = ExhaustionSystem()
        # Initialize exhaustion tracking on all NPCs
        for npc in world_mgr.npcs:
            self.exhaustion.initialize_entity(npc)

        # Transport system (mounts, stables, coaches, caravans)
        from game.systems.transport import TransportSystem
        self.transport = TransportSystem()
        self.transport.initialize(structures,
                                   getattr(world, 'road_network', None))

        # Road maintenance
        from game.systems.roads import RoadMaintenance, RoadNetwork
        road_net = getattr(world, 'road_network', None)
        if road_net:
            self.road_maintenance = RoadMaintenance(road_net)
        else:
            self.road_maintenance = None

        # Battle visuals (projectiles, siege engines, formations)
        from game.systems.battle_visuals import BattleVisuals
        self.battle_visuals = BattleVisuals()

        # NPC Lifecycle (economics, careers, social, daily routine)
        from game.systems.npc_lifecycle import NpcLifecycle
        self.lifecycle = NpcLifecycle()

        # Children and Darwinian Inheritance System
        from game.systems.children import ChildSystem
        self.child_system = ChildSystem()

        # Emotion system (Plutchik's Wheel of Emotions)
        # Now universal: NPCs, creatures, and player all have emotions
        from game.systems.emotions import EmotionSystem
        self.emotions = EmotionSystem()
        for npc in world_mgr.npcs:
            self.emotions.initialize_npc(npc)
        for creature in world_mgr.creatures:
            self.emotions.initialize_creature(creature)

        # Social Dynamics & Joy Spreading (love, contempt, betrayal, morale)
        from game.systems.social_dynamics import SocialDynamicsSystem
        self.social_dynamics = SocialDynamicsSystem()
        self._last_morale_day = -1

        # Health system (disease, contagion, medicine)
        from game.systems.health import HealthSystem, ensure_health_attrs
        self.health = HealthSystem()
        for npc in world_mgr.npcs:
            ensure_health_attrs(npc)
        self.health.cache_settlement_kinds(world_mgr.npcs, structures)
        # Wire health death callback to main death handler
        def _on_health_death(npc, disease_name):
            self._handle_npc_death_from_disease(npc, disease_name)
        self.health.on_death = _on_health_death

        # Mental health system (depression, anxiety, PTSD, etc.)
        from game.systems.mental_health import MentalHealthSystem, ensure_mental_health_attrs
        self.mental_health = MentalHealthSystem()
        for npc in world_mgr.npcs:
            ensure_mental_health_attrs(npc)

        # NPC Work Behavior (physical job performance, goods carrying, hunting)
        from game.systems.npc_work import NpcWorkSystem, _ensure_work_state
        self.npc_work = NpcWorkSystem()
        # Wire climate reference for weather production modifiers
        if hasattr(self, 'climate'):
            self.npc_work._climate_ref = self.climate

        # Initialize work state for ALL NPCs with professions (not just active ones)
        for npc in world_mgr.npcs:
            if getattr(npc, 'profession', '') or getattr(npc, 'char_class', ''):
                _ensure_work_state(npc)

        # Goods Transport System (delivery queues, trade caravans, ground items)
        from game.systems.goods_transport import GoodsTransportManager
        self.goods_transport = GoodsTransportManager()
        # Wire the transport manager into world_effects so trade_supplies uses it
        if hasattr(self, 'world_effects'):
            self.world_effects._goods_transport = self.goods_transport

        # Hierarchical Command System (rulers -> leaders -> workers)
        from game.systems.commands import CommandSystem
        self.command_system = CommandSystem()
        # Wire command system into work system so NPCs check for orders
        self.npc_work._command_system = self.command_system

        # Soul system (metaphysical layer — souls persist across lives and saves)
        import os as _os_mod
        from game.systems.souls import SoulSystem
        self.souls = SoulSystem()
        _base = _os_mod.path.dirname(_os_mod.path.dirname(_os_mod.path.dirname(
            _os_mod.path.abspath(__file__))))
        self.souls.load(base_path=_base)
        # Assign souls to all existing NPCs and creatures
        for npc in world_mgr.npcs:
            if not hasattr(npc, 'soul_id'):
                npc.soul_id = None
            self.souls.on_birth(npc, 0.0)
        for creature in world_mgr.creatures:
            if not hasattr(creature, 'soul_id'):
                creature.soul_id = None
            if len(self.souls.pool.souls) < self.souls.pool.MAX_TRACKED_SOULS:
                self.souls.on_birth(creature, 0.0)

        # Wire population births to soul system + mental health hereditary susceptibility
        def _on_pop_birth(npc, settlement_kind):
            if not hasattr(npc, 'soul_id'):
                npc.soul_id = None
            self.souls.on_birth(npc, self.time_sys.time, settlement_kind=settlement_kind)
            # Mental health: hereditary susceptibility from parents
            if hasattr(self, 'mental_health'):
                parent_names = getattr(npc, 'parent_names', (None, None))
                parents = [n for n in self.world_mgr.npcs
                           if n.name in parent_names and n.alive]
                if parents:
                    self.mental_health.apply_hereditary_susceptibility(npc, parents)
        self.population.on_birth = _on_pop_birth

        # Undead & Soul Predation system
        from game.systems.undead import UndeadSystem
        self.undead = UndeadSystem(self.souls)
        self.undead.initialize_consecrated_zones(world)

        # AI Storyteller (RimWorld-inspired dramatic pacing)
        from game.systems.storyteller import AIStoryteller
        self.storyteller = AIStoryteller(personality="balanced")
        self._storyteller_last_day = -1

        # Rate limiting
        self._last_llm_time = 0.0
        self._llm_min_interval = 0.1  # rate limit between NPC decisions

    def update(self, dt: float, player: Player):
        """Main simulation tick."""
        self._player_ref = player
        npcs = self.world_mgr.npcs
        game_time = self.time_sys.time

        # Master tick counter for throttling subsystems
        if not hasattr(self, '_sim_tick'):
            self._sim_tick = 0
        self._sim_tick += 1

        # Reset pathfinding budget for this tick
        from game.systems.navigation import reset_pathfind_budget
        reset_pathfind_budget()

        # Rebuild spatial grids every other tick (O(n), positions don't change much per frame)
        if not hasattr(self, '_grid_tick'):
            self._grid_tick = 0
        self._grid_tick += 1
        if self._grid_tick % 3 == 0:  # rebuild every 3rd tick
            self.creature_grid.update_all(self.world_mgr.creatures)
            self.npc_grid.update_all(npcs)

        # Abstract simulation — must run BEFORE the dormant check so active_npcs is current
        if hasattr(self, 'abstract'):
            dormant_names = self.world_mgr.get_dormant_npc_names()
            self.abstract.update(dt, player.x, player.y, npcs, self.time_sys.day,
                                 dormant_npc_names=dormant_names)

            # Process world effects from abstract sim (once per game day)
            if hasattr(self, 'world_effects'):
                cur_day = self.time_sys.day
                if cur_day != getattr(self, '_last_effects_day', -1):
                    self._last_effects_day = cur_day
                    self.world_effects.process_abstract_events(self.abstract)
                    self.world_effects.daily_update(self.time_sys)
                    self.world_effects.process_events()
                    # Daily price gossip for trade-aware NPCs
                    try:
                        from game.systems.npc_work import daily_price_gossip
                        daily_price_gossip(npcs, self.world_effects)
                    except Exception:
                        pass

        # Cache active NPC set for all subsystems this tick
        self._active_npc_set = self.abstract.active_npcs if hasattr(self, 'abstract') else None

        # For dormant NPCs (far from player), simulate need decay and basic survival
        if hasattr(self, 'abstract'):
            time_mult = self.time_sys.speed
            dormant_effective_dt = min(dt * time_mult, dt * 3.0 + 1.0 / 30.0)
            for npc in npcs:
                if not npc.alive:
                    continue
                if not self.abstract.should_simulate_npc(npc):
                    # Dormant: decay needs at normal rate so they don't stay frozen
                    race_mods = getattr(npc, 'need_multipliers', {})
                    npc.needs["hunger"] = max(0, npc.needs["hunger"] - NEED_DECAY["hunger"] * dormant_effective_dt * race_mods.get("hunger", 1.0))
                    npc.needs["thirst"] = max(0, npc.needs["thirst"] - NEED_DECAY["thirst"] * dormant_effective_dt * race_mods.get("thirst", 1.0))
                    npc.needs["social"] = max(0, npc.needs["social"] - NEED_DECAY["social"] * dormant_effective_dt)
                    if npc.current_action == "sleeping":
                        npc.needs["rest"] = min(100, npc.needs["rest"] + 0.5 * dormant_effective_dt)
                    else:
                        npc.needs["rest"] = max(0, npc.needs["rest"] - NEED_DECAY["rest"] * dormant_effective_dt * race_mods.get("rest", 1.0))
                    # Stabilize: prevent death off-screen by auto-satisfying critical needs
                    for need in npc.needs:
                        if npc.needs[need] < 15:
                            npc.needs[need] = 15
                    # Auto-eat/drink if they have supplies
                    if npc.needs["hunger"] < 30 and npc.has_food():
                        npc.consume_food()
                    if npc.needs["thirst"] < 45 and npc.has_drink():
                        npc.consume_drink()
                    continue

        self._decay_needs(npcs, dt)
        self._check_critical_needs(npcs, dt)

        # Threat response (BEFORE decisions - overrides normal behavior)
        self._threat_response(npcs, dt)

        self._update_action_progress(npcs, dt, player)
        self._update_player_tasks(npcs, dt)

        # NPC Work Behavior: physical job performance, goods transport, hunting
        # Runs BEFORE _request_decisions so the work system can claim NPCs
        # whose timed actions just completed, before the schedule system
        # assigns them something else.
        _we = self.world_effects if hasattr(self, 'world_effects') else None
        _z = self.zones if hasattr(self, 'zones') else None
        _gt = self.goods_transport if hasattr(self, 'goods_transport') else None
        self.npc_work.update(dt, npcs, self.time_sys, self.world, self.world_mgr,
                             world_effects=_we, zones=_z,
                             active_set=self._active_npc_set,
                             goods_transport=_gt)

        self._request_decisions(npcs, dt, player)
        self._poll_decisions(npcs)
        self._update_conversations(dt)
        self._update_events(dt, npcs, player)
        self._npc_combat_tick(npcs, dt)

        # Body damage: wound healing, bleeding, infection
        _bd_entities = list(npcs)
        _bd_entities.append(player)
        self.body_damage.update(dt, _bd_entities)

        # Social dynamics — every 5th tick (~6x per second at 30fps)
        if self._sim_tick % 5 == 0:
            self.social.update(dt * 5, npcs, player)
            for msg in self.social.get_social_log():
                self.event_log.append(msg)

        # Daily life: jobs, economy, schedules
        self._update_daily_life(npcs, dt)

        # Update NPC economic awareness (once per day)
        self._update_npc_economic_awareness(npcs)

        # NPC Lifecycle: economics, careers, social progression
        gov = self.governance if hasattr(self, 'governance') else None
        eco = self.economy if hasattr(self, 'economy') else None
        we = self.world_effects if hasattr(self, 'world_effects') else None
        self.lifecycle.update(dt, npcs, self.time_sys, self.world, gov, eco,
                              world_effects=we)
        for msg in self.lifecycle.get_event_log():
            self.event_log.append(msg)

        # Emotion system (Plutchik's Wheel) — every 5th tick
        # Now includes creatures and player for universal emotions
        if self._sim_tick % 5 == 2:
            self.emotions.update(dt * 5, npcs, game_time,
                                 creatures=self.world_mgr.creatures,
                                 player=player)
            for msg in self.emotions.get_event_log():
                self.event_log.append(msg)

        # Social Dynamics (love, contempt, betrayal) — internally throttled (30s)
        if self._sim_tick % 5 == 2:
            _npc_grid_sd = self.npc_grid if hasattr(self, 'npc_grid') else None
            self.social_dynamics.update_social(
                dt * 5, npcs, _npc_grid_sd, game_time)
            for msg in self.social_dynamics.get_event_log():
                self.event_log.append(msg)

        # Joy Spreading — internally throttled (15s), near player only
        if self._sim_tick % 5 == 3:
            _npc_grid_joy = self.npc_grid if hasattr(self, 'npc_grid') else None
            self.social_dynamics.update_joy_spreading(
                dt * 5, npcs, _npc_grid_joy,
                player.x, player.y,
                self.world.structures)

        # Morale Cascades — once per game day per settlement
        _cur_day_morale = self.time_sys.day
        if _cur_day_morale != self._last_morale_day:
            self._last_morale_day = _cur_day_morale
            _pop = self.population if hasattr(self, 'population') else None
            self.social_dynamics.update_morale(npcs, _pop, game_time)
            for msg in self.social_dynamics.get_event_log():
                self.event_log.append(msg)

        # Health system (disease, contagion, medicine) — every 5th tick
        if self._sim_tick % 5 == 1:
            _season = getattr(self.time_sys, 'season', 'spring')
            _npc_grid = self.npc_grid if hasattr(self, 'npc_grid') else None
            _trade = self.trade if hasattr(self, 'trade') else None
            self.health.update(
                dt * 5, self.time_sys.day, _season, npcs,
                world=self.world, npc_grid=_npc_grid,
                trade_system=_trade,
                active_set=self._active_npc_set)
            for msg in self.health.get_event_log():
                self.event_log.append(msg)

        # Mental health system (depression, anxiety, PTSD, etc.) — every 5th tick
        if self._sim_tick % 5 == 1:
            self.mental_health.update(dt * 5, self.time_sys.day, npcs)
            for msg in self.mental_health.get_event_log():
                self.event_log.append(msg)

        # Memory decay and compaction — every 10th tick
        if self._sim_tick % 10 == 0:
            self.memory_mgr.update(dt * 10, npcs, self.time_sys.day)

        # Demographics (aging, mortality) — every 10th tick
        if self._sim_tick % 10 == 1:
            self.demographics.update(dt * 10, npcs, self.time_sys.day)

        # Burial system — mourning updates (every 10th tick)
        if self._sim_tick % 10 == 2 and hasattr(self, 'burial'):
            self.burial.update(dt * 10, self.time_sys.day, npcs,
                               social_system=self.social)

        # Children system (pregnancies, births, child care, coming of age) — every tick
        # (internally throttled: pregnancies every 30s, children every 10s)
        self.child_system.update(npcs, dt, game_time, self.world,
                                 demographics=self.demographics,
                                 population=self.population if hasattr(self, 'population') else None,
                                 world_effects=we)
        for msg in self.child_system.get_event_log():
            self.event_log.append(msg)

        # Soul system (ghost drift, reincarnation) — every 10th tick
        if self._sim_tick % 10 == 1:
            self.souls.update(dt * 10, game_time, npcs, self.world_mgr.creatures)

        # Undead & Soul Predation — every 10th tick (after soul system)
        if self._sim_tick % 10 == 1 and hasattr(self, 'undead'):
            self.undead.update(dt * 10, game_time, self.world_mgr.creatures,
                               npcs, self.world, time_sys=self.time_sys,
                               player=player)
            for msg in self.undead.get_event_log():
                self.event_log.append(msg)

        # Fire system — every 5th tick
        if self._sim_tick % 5 == 2:
            self.fire_mgr.update(dt * 5)

        # Economy (simple local pricing) — every 10th tick
        if self._sim_tick % 10 == 2:
            self.economy.update(dt * 10)

        # Banking (loans, deposits, insurance, bonds) — every 10th tick
        if self._sim_tick % 10 == 3:
            gov_style = "feudalism"
            if hasattr(self, 'governance'):
                for k in self.governance.kingdoms.values():
                    gov_style = getattr(k, 'governing_style', 'feudalism')
                    break
            self.banking.update(dt * 10, npcs, self.time_sys.day, gov_style)

        # World Economy (macro simulation with trade) — every 10th tick
        if self._sim_tick % 10 == 4:
            season = getattr(self.time_sys, 'season', 'spring')
            solar = getattr(self.time_sys, 'solar_intensity', 0.5)
            self.world_market.update(dt * 10, season, solar)

        # Governance (kingdoms, diplomacy, succession) — every 10th tick
        if self._sim_tick % 10 == 5:
            self.governance.update(dt * 10, npcs, self.time_sys.day)

        # Faction reputation & quest system — every 10th tick
        if self._sim_tick % 10 == 5:
            # Update player's current kingdom
            player.current_kingdom = self.governance.get_kingdom_at(
                player.x, player.y) or ""
            # Sync player's faction_system reference with simulation's
            player.faction_system = self.faction_system
            # Reputation decay
            self.faction_system.update(dt * 10)
            # Quest system: refresh bounty boards, check expiry
            _snames = [s.name for s in self.world.structures
                       if s.kind in ("village", "town", "city", "hamlet", "castle")]
            _knames = list(self.governance.kingdoms.keys())
            _nnames = [n.name for n in npcs[:50] if n.alive]
            self.quest_system.update(
                dt * 10, self.time_sys.day, player.level,
                settlement_names=_snames,
                kingdom_names=_knames,
                npc_names=_nnames)
            for msg in self.quest_system.get_event_log():
                self.event_log.append(msg)

        # Hierarchical Command System (rulers issue orders, subordinates execute)
        _we = self.world_effects if hasattr(self, 'world_effects') else None
        _creatures = self.world_mgr.creatures if hasattr(self.world_mgr, 'creatures') else []
        self.command_system.update(dt, npcs, _we, self.governance,
                                   self.time_sys, world=self.world,
                                   creatures=_creatures)
        for msg in self.command_system.get_event_log():
            self.event_log.append(msg)

        # Political intrigue (plots, coups, assassinations) — every 10th tick
        if self._sim_tick % 10 == 6:
            self.intrigue.update(dt * 10, npcs, self.governance, self.time_sys.day)
            for msg in self.intrigue.get_intrigue_log():
                self.event_log.append(msg)

        # Battle visuals (projectiles, formations, siege engines) — every tick (visual)
        self.battle_visuals.update(dt)

        # Monster societies (intelligent creature governance and raids) — every 10th tick
        if self._sim_tick % 10 == 7:
            settlements = self.world_market.settlements if hasattr(self, 'world_market') else {}
            self.monster_societies.update(dt * 10, self.time_sys.day,
                                          self.world_mgr.creatures, settlements)
            for msg in self.monster_societies.get_event_log():
                self.event_log.append(msg)
            for msg in self.governance.get_event_log():
                self.event_log.append(msg)

        # Military (army movement, battles) — every 5th tick
        if self._sim_tick % 5 == 3:
            self.military.update(dt * 5, npcs, self.governance, self.world)
            for msg in self.military.get_battle_log():
                self.event_log.append(msg)

        # Trade (caravan movement, buying/selling) — every 5th tick
        if self._sim_tick % 5 == 4:
            self.trade.update(dt * 5, self.world.structures, npcs, self.economy, self.world)
            for msg in self.trade.get_trade_log():
                self.event_log.append(msg)

        # Exhaustion & sleep — use itertools.chain to avoid list copy
        self.exhaustion.update(dt, itertools.chain(npcs, self.world_mgr.creatures), DAY_LENGTH)

        # Transport (mounts, coaches, stables) — every 5th tick
        if self._sim_tick % 5 == 0:
            self.transport.update(dt * 5, self.time_sys.time, self.world.structures, self.world)

        # Goods Transport (delivery queues, trade caravans, ground items) — every 5th tick
        if self._sim_tick % 5 == 1 and hasattr(self, 'goods_transport'):
            _we = self.world_effects if hasattr(self, 'world_effects') else None
            self.goods_transport.update(
                dt * 5, world=self.world, world_effects=_we,
                structures=self.world.structures)

        # Road maintenance — every 30th tick
        if self._sim_tick % 30 == 0 and self.road_maintenance:
            self.road_maintenance.update(dt * 30)

        # Durability (structural decay) — every 30th tick
        if self._sim_tick % 30 == 1:
            self.durability.update(dt * 30, self.world)

        # Ecology (seasons, weather, crops, regrowth) — every 10th tick
        if self._sim_tick % 10 == 8:
            self.ecology.update(dt * 10, self.time_sys.day, self.world, self.time_sys)

        # Climate model (pressure systems, disasters) — once per game day
        if hasattr(self, 'climate') and self.time_sys.day != self._climate_last_day:
            self._climate_last_day = self.time_sys.day
            self.climate.update(self.time_sys.day, self.time_sys.season)
            new_disasters = self.climate.check_disasters(self.time_sys.day)
            for d in new_disasters:
                self.event_log.append(f"[DISASTER] {d.description}")
            self.climate.apply_weather_emotions(npcs, game_time)

        # AI Storyteller — once per game day, after climate
        if hasattr(self, 'storyteller') and self.time_sys.day != self._storyteller_last_day:
            self._storyteller_last_day = self.time_sys.day
            self.storyteller.update(self.time_sys.day, self)
            for msg in self.storyteller.get_event_log():
                self.event_log.append(msg)

        # Construction (building projects) — every 10th tick
        if self._sim_tick % 10 == 9:
            self.construction.update(dt * 10, npcs, self.world)
            self.construction.auto_commission(self.governance, self.world, self.world.structures)
            for msg in self.construction.get_log():
                self.event_log.append(msg)

        # Culture (festivals, education, religion) — every 30th tick
        if self._sim_tick % 30 == 2:
            self.culture.update(dt * 30, npcs, self.world.structures, self.time_sys.day)
            for msg in self.culture.get_event_log():
                self.event_log.append(msg)

        # God AI Pantheon (divine observation, prayers, miracles, petitions) — every 30th tick
        if self._sim_tick % 30 == 5:
            if hasattr(self, 'pantheon'):
                _heresy = self.heresy if hasattr(self, 'heresy') else None
                self.pantheon.trigger_npc_prayers(npcs, game_time, _heresy)
                self.pantheon.update(dt * 30, game_time, self)
                # Recount worshippers every ~15 calls (~450s)
                if self._sim_tick % 450 == 0:
                    self.pantheon.count_worshippers(npcs)
                for msg in self.pantheon.get_event_log():
                    self.event_log.append(msg)

        # Heresy & Religious Schism — check every 5 game days
        if self._sim_tick % 30 == 6 and hasattr(self, 'heresy'):
            day = self.time_sys.day
            if day % 5 == 0:
                _culture = self.culture if hasattr(self, 'culture') else None
                _pantheon = self.pantheon if hasattr(self, 'pantheon') else None
                self.heresy.update(day, npcs, self.world.structures,
                                   _pantheon, _culture)
                for msg in self.heresy.get_event_log():
                    self.event_log.append(msg)

        # Technology (research, tech spread) — every 30th tick
        if self._sim_tick % 30 == 3:
            self.technology.update(dt * 30, npcs, self.world.structures, self.time_sys.day)
            for msg in self.technology.get_event_log():
                self.event_log.append(msg)

        # Territory (land ownership, expansion, development) — every 30th tick
        if self._sim_tick % 30 == 4:
            self.territory.update(dt * 30, npcs, self.world_mgr.creatures,
                                 self.governance, self.world, self.construction,
                                 self.creature_grid)
            for msg in self.territory.get_event_log():
                self.event_log.append(msg)

        # Creature living needs, pack behavior, flocking, and herding
        # Only process creatures near player for detailed behavior
        from game.systems.living import update_creature_needs, update_pack_behavior, update_flocking, update_herding
        active_creatures = self.creature_grid.get_nearby(player.x, player.y, 80)
        if active_creatures:
            update_pack_behavior(active_creatures, dt)
            update_flocking(active_creatures, dt, self.world)
            update_herding(active_creatures, dt, self.world, active_creatures)
        time_norm = self.time_sys.normalized
        for creature in active_creatures:
            if creature.alive:
                # Only get nearby creatures for predator interactions using spatial grid
                local_creatures = self.creature_grid.get_nearby(creature.x, creature.y, 10)
                update_creature_needs(creature, dt, time_norm, self.world, local_creatures)

        # Race-specific need modifiers are applied in _decay_needs directly.

        # Population dynamics — every 10th tick
        if self._sim_tick % 10 == 0:
            self.population.update(dt * 10, npcs, self.world_mgr.creatures, self.world, self.time_sys)
            for msg in self.population.get_population_log():
                self.event_log.append(msg)

        # Abstract simulation already ran at top of update()

        # Trim event log to prevent unbounded growth
        _MAX_EVENT_LOG = 500
        if len(self.event_log) > _MAX_EVENT_LOG:
            self.event_log = self.event_log[-_MAX_EVENT_LOG:]

    # ---- NEEDS ----

    # ---- THREAT RESPONSE ----

    def _threat_response(self, npcs: List[NPC], dt: float):
        """NPCs detect and respond to nearby threats using spatial grid."""
        threat_range = 12.0
        combat_classes = {"Fighter", "Paladin", "Barbarian", "Ranger"}
        caster_classes = {"Wizard", "Sorcerer", "Warlock", "Cleric", "Druid"}

        # Use cached active NPC set to avoid repeated should_simulate checks
        active_set = self.abstract.active_npcs if hasattr(self, 'abstract') else None
        busy_actions = frozenset(("fighting", "fleeing", "following_player"))

        for npc in npcs:
            if not npc.alive:
                continue
            if npc.current_action in busy_actions:
                continue
            # Skip dormant NPCs using cached set
            if active_set is not None and npc.name not in active_set:
                continue

            # Use spatial grid for O(1) nearby creature lookup
            nearby_creatures = self.creature_grid.get_nearby(npc.x, npc.y, threat_range)

            # Find nearest non-passive threat
            nearest_threat = None
            nearest_dist = threat_range
            for creature in nearby_creatures:
                if getattr(creature, 'passive', False):
                    continue
                d = npc.dist_to(creature)
                if d < nearest_dist:
                    nearest_dist = d
                    nearest_threat = creature

            if nearest_threat is None:
                continue

            char_class = getattr(npc, 'char_class', '')
            bravery = npc.bravery
            hp_ratio = npc.hp / max(1, npc.max_hp)

            # Response depends on class, bravery, HP, and threat CR
            threat_cr = getattr(nearest_threat, 'cr', 0.25)
            npc_level = getattr(npc, 'level', 1)
            can_handle = npc_level >= threat_cr * 2  # rough power check

            if nearest_dist < 4.0:
                # VERY CLOSE - immediate reaction needed
                if char_class in combat_classes and bravery > 0.4 and hp_ratio > 0.3 and can_handle:
                    # FIGHT - brave combat classes engage
                    npc.combat_target = nearest_threat
                    npc.current_action = "fighting"
                    npc.state = "fighting"
                    npc.add_memory("combat", f"Engaged a {nearest_threat.kind} threatening the area!", 3)

                    # Alert nearby friendly NPCs (spatial grid lookup)
                    nearby_npcs = self.npc_grid.get_nearby(npc.x, npc.y, 8)
                    for other in nearby_npcs:
                        if other is npc:
                            continue
                        other.add_memory("alert", f"{npc.name} is fighting a {nearest_threat.kind}!", 2)
                        other.known_info.append(f"{nearest_threat.kind} spotted near {npc.name}")

                elif char_class in caster_classes and bravery > 0.3 and can_handle:
                    # CAST SPELL from distance if possible
                    if getattr(npc, 'known_spells', []):
                        from game.data.dnd import SPELLS
                        for spell_name in npc.known_spells:
                            spell = SPELLS.get(spell_name, {})
                            if spell.get("damage", 0) > 0 and spell.get("range", 0) >= nearest_dist:
                                nearest_threat.take_damage(spell["damage"])
                                npc.add_memory("combat", f"Cast {spell_name} at a {nearest_threat.kind}!", 3)
                                self.event_log.append(f"{npc.name} cast {spell_name} at a {nearest_threat.kind}!")
                                npc.current_action = ""
                                break
                        else:
                            # No ranged spell - flee
                            npc.flee_from(nearest_threat.x, nearest_threat.y)
                    else:
                        npc.flee_from(nearest_threat.x, nearest_threat.y)

                else:
                    # FLEE - non-combat classes or low HP/bravery
                    npc.flee_from(nearest_threat.x, nearest_threat.y)
                    npc.add_memory("fear", f"Ran from a {nearest_threat.kind}!", 2)

                    # If at home, try to go home and "lock door"
                    home_dist = npc.dist_to_pos(npc.home_x, npc.home_y)
                    if home_dist < 15:
                        npc.target_x = npc.home_x
                        npc.target_y = npc.home_y
                        npc.current_action = "fleeing_home"

            elif nearest_dist < 8.0:
                # MEDIUM RANGE - prepare or alert
                if char_class in combat_classes and bravery > 0.5:
                    # Move to intercept
                    npc.target_x = nearest_threat.x
                    npc.target_y = nearest_threat.y
                    npc.current_action = "moving"
                    npc.current_goal = f"intercept {nearest_threat.kind}"
                    npc.state = "walking"
                    npc.state_timer = 5.0
                else:
                    # Alert: warn others and move away
                    npc.add_memory("alert", f"Spotted a {nearest_threat.kind} nearby", 2)

                    # Call for guards (spatial grid)
                    nearby_npcs = self.npc_grid.get_nearby(npc.x, npc.y, 10)
                    for other in nearby_npcs:
                        if other is npc:
                            continue
                        other_class = getattr(other, 'char_class', '')
                        if other_class in combat_classes:
                            other.target_x = nearest_threat.x
                            other.target_y = nearest_threat.y
                            other.current_action = "moving"
                            other.current_goal = f"respond to threat: {nearest_threat.kind}"
                            other.state = "walking"
                            other.state_timer = 8.0
                            other.add_memory("alert", f"{npc.name} called for help against a {nearest_threat.kind}!", 3)
                            self.event_log.append(f"{npc.name} called {other.name} to fight a {nearest_threat.kind}!")
                            break

    def _get_sleep_quality(self, npc) -> float:
        """Get sleep quality based on where the NPC is sleeping.
        Returns rest recovery rate per second."""
        x, y = int(npc.x), int(npc.y)

        # Check if on a bed tile (best rest)
        if 0 <= x < self.world.width and 0 <= y < self.world.height:
            tile = self.world.tiles[y][x]
            if tile == BED:
                return 2.5  # excellent rest in a proper bed

        # Check if inside a building (good rest)
        if hasattr(self, '_player_ref'):
            from game.systems.buildings import BuildingSystem
        loc = self.world.get_structure_at(npc.x, npc.y)
        if loc and loc.kind in ("village", "town", "city", "hamlet", "castle"):
            # Inside a settlement building
            if 0 <= x < self.world.width and 0 <= y < self.world.height:
                tile = self.world.tiles[y][x]
                if tile == FLOOR:
                    return 1.8  # decent rest indoors on floor

        # Check if near home (moderate rest)
        home_dist = npc.dist_to_pos(npc.home_x, npc.home_y)
        if home_dist < 5:
            return 1.5  # near home comfort

        # Check if on road (poor rest)
        if 0 <= x < self.world.width and 0 <= y < self.world.height:
            tile = self.world.tiles[y][x]
            if tile == ROAD:
                return 0.5  # terrible rest on the road

        # Outdoors in wilderness
        return 0.8  # poor rest outdoors

    def _get_sleep_safety(self, npc) -> bool:
        """Check if the NPC's sleeping location is safe from attacks."""
        x, y = int(npc.x), int(npc.y)

        # Inside a building with walls = safe
        if 0 <= x < self.world.width and 0 <= y < self.world.height:
            tile = self.world.tiles[y][x]
            if tile in (BED, FLOOR):
                # Check if enclosed (surrounded by walls on at least 2 sides)
                wall_count = 0
                for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.world.width and 0 <= ny < self.world.height:
                        if self.world.tiles[ny][nx] in (WALL, BUILT_WALL, LOCKED_DOOR, WINDOW):
                            wall_count += 1
                if wall_count >= 2:
                    return True  # enclosed = safe

        # Near guards = safe (spatial grid)
        nearby = self.npc_grid.get_nearby(npc.x, npc.y, 8)
        for other_npc in nearby:
            if other_npc is npc:
                continue
            if True:  # already filtered by spatial grid
                title = getattr(other_npc, 'title', '')
                char_class = getattr(other_npc, 'char_class', '')
                if title == 'guard' or char_class in ('Fighter', 'Paladin', 'Ranger'):
                    if other_npc.current_action != "sleeping":
                        return True  # guard nearby and awake

        # Outdoors = not safe
        return False

    def _decay_needs(self, npcs: List[NPC], dt: float):
        time_mult = self.time_sys.speed
        active_set = self._active_npc_set

        # Cap effective dt so needs don't drain impossibly fast at high time speeds.
        # At 100x speed, raw dt*speed would drain needs before NPCs can act.
        # Cap to equivalent of ~3x real-time decay regardless of speed setting.
        effective_dt = min(dt * time_mult, dt * 3.0 + 1.0 / 30.0)

        for npc in npcs:
            if not npc.alive:
                continue
            # Skip dormant NPCs - they're handled by abstract sim stabilizer
            if active_set is not None and npc.name not in active_set:
                continue
            # Apply active event effects
            h_mult = 1.0
            t_mult = 1.0
            r_mult = 1.0
            for evt in self.events:
                if evt.affects(npc):
                    h_mult *= evt.effects.get("hunger_mult", 1.0)
                    t_mult *= evt.effects.get("thirst_mult", 1.0)
                    r_mult *= evt.effects.get("rest_mult", 1.0)
                    # Social boost from festivals
                    if evt.effects.get("social_boost"):
                        npc.needs["social"] = min(100, npc.needs["social"] + evt.effects["social_boost"] * dt)

            # Apply race-specific need modifiers
            race_mods = getattr(npc, 'need_multipliers', {})
            race_h = race_mods.get("hunger", 1.0)
            race_t = race_mods.get("thirst", 1.0)
            race_r = race_mods.get("rest", 1.0)

            npc.needs["hunger"] = max(0, npc.needs["hunger"] - NEED_DECAY["hunger"] * effective_dt * h_mult * race_h)
            npc.needs["thirst"] = max(0, npc.needs["thirst"] - NEED_DECAY["thirst"] * effective_dt * t_mult * race_t)
            npc.needs["social"] = max(0, npc.needs["social"] - NEED_DECAY["social"] * effective_dt)

            # Rest: decays while awake, recovers while sleeping
            # Recovery rate depends on sleep quality (where they are)
            if npc.current_action == "sleeping":
                sleep_quality = self._get_sleep_quality(npc)
                npc.needs["rest"] = min(100, npc.needs["rest"] + sleep_quality * effective_dt)
                # Heal while sleeping well
                if sleep_quality > 1.0 and npc.hp < npc.max_hp:
                    npc.hp = min(npc.max_hp, npc.hp + 0.2 * dt)
            else:
                npc.needs["rest"] = max(0, npc.needs["rest"] - NEED_DECAY["rest"] * effective_dt * r_mult)

            # Sleep deprivation effects
            rest = npc.needs["rest"]
            if rest < 15:
                # Exhausted: speed penalty, can't fight well
                npc.speed = getattr(npc, '_base_speed', npc.speed) * 0.6
                if not hasattr(npc, '_base_speed'):
                    npc._base_speed = npc.speed / 0.6
                # Hallucination/confusion at very low rest
                if rest < 5 and random.random() < 0.001 * dt:
                    npc.add_memory("exhaustion", "So tired... can barely stay awake", 3)
            elif rest < 30:
                # Tired: slight speed penalty
                if hasattr(npc, '_base_speed'):
                    npc.speed = npc._base_speed * 0.85
            else:
                # Rested: restore normal speed
                if hasattr(npc, '_base_speed'):
                    npc.speed = npc._base_speed
                    del npc._base_speed

            # Force collapse if rest hits 0
            if rest <= 0 and npc.current_action != "sleeping":
                npc.current_action = "sleeping"
                npc.state = "sleeping"
                npc.state_timer = random.uniform(15, 30)
                npc.action_timer = npc.state_timer
                npc.add_memory("exhaustion", "Collapsed from exhaustion!", 4)
                # Collapse in place - vulnerable!

            # Sleeping NPCs are vulnerable to nearby threats
            if npc.current_action == "sleeping":
                sleep_safety = self._get_sleep_safety(npc)
                if not sleep_safety:
                    # Use spatial grid for O(1) nearby creature lookup
                    nearby_creatures = self.creature_grid.get_nearby(npc.x, npc.y, 3)
                    for creature in nearby_creatures:
                        if creature.alive:
                            # Creature attacks sleeping NPC!
                            dmg = getattr(creature, 'damage', 5)
                            npc.take_damage(dmg)
                            npc.current_action = ""
                            npc.state = "idle"
                            npc.needs["rest"] = min(npc.needs["rest"] + 10, 30)  # jolted awake
                            npc.add_memory("danger", f"Attacked by {creature.kind} while sleeping!", 5)
                            self.event_log.append(f"{npc.name} was attacked by a {creature.kind} while sleeping outdoors!")
                            # Fight or flee
                            if npc.bravery > 0.4:
                                npc.combat_target = creature
                                npc.current_action = "fighting"
                            else:
                                npc.flee_from(creature.x, creature.y)
                            break

            # Plague damage
            for evt in self.events:
                if evt.affects(npc) and evt.effects.get("plague_dps"):
                    npc.hp = max(0, npc.hp - evt.effects["plague_dps"] * dt)
                    if npc.hp <= 0:
                        npc.alive = False
                        if hasattr(self, 'burial'):
                            self.burial.on_death(npc, "disease",
                                                 self.time_sys.time_string,
                                                 self.time_sys.day, self.world)

    def _check_critical_needs(self, npcs: List[NPC], dt: float):
        for npc in list(npcs):
            if not npc.alive:
                continue
            # Skip dormant NPCs
            if self._active_npc_set is not None and npc.name not in self._active_npc_set:
                continue

            # Emotion trigger for hunger/thirst distress
            if npc.needs["hunger"] < 20 or npc.needs["thirst"] < 20:
                from game.systems.emotions import trigger_emotion
                trigger_emotion(npc, "went_hungry", intensity=0.4,
                                cause="starving" if npc.needs["hunger"] < 20 else "dehydrated",
                                game_time=self.time_sys.time)

            # Auto-eat/drink when getting low (survival instinct)
            # Don't interrupt timed work actions for routine eating
            is_busy = npc.action_timer > 0 and npc.current_action not in ("", "idle", "moving")
            if npc.needs["hunger"] < 45 and npc.has_food():
                eaten = npc.consume_food()
                if eaten:
                    if npc.needs["hunger"] < 20:
                        npc.add_memory("survival", f"Ate {eaten} — was starving", 3)
                    if not is_busy:
                        npc.current_action = ""
            if npc.needs["thirst"] < 45 and npc.has_drink():
                drunk = npc.consume_drink()
                if drunk:
                    if npc.needs["thirst"] < 20:
                        npc.add_memory("survival", f"Drank {drunk} — was parched", 3)
                    if not is_busy:
                        npc.current_action = ""

            # Cache structure lookup to avoid repeated calls
            _npc_loc = self.world.get_structure_at(npc.x, npc.y) if (
                npc.needs["hunger"] < 35 or not npc.has_drink() or
                npc.npc_count_item("Water Flask") < 2) else None

            # Settlement food sharing — NPCs in settlements share food with neighbors
            if npc.needs["hunger"] < 35 and not npc.has_food():
                loc = _npc_loc
                if loc and loc.kind in ("village", "town", "city", "hamlet", "castle"):
                    # Settlement provides basic food (communal supplies / market)
                    food = make_item("Bread")
                    food.count = 3
                    npc.npc_add_item(food)

            # Auto-forage when low on supplies and needs dropping
            if npc.needs["hunger"] < 50 and not npc.has_food() and npc.current_action == "":
                self._move_to_forage(npc)

            # Auto-refill water at wells/rivers/settlements
            if not npc.has_drink() or npc.npc_count_item("Water Flask") < 2:
                refilled = False
                nx, ny = int(npc.x), int(npc.y)
                # Check if NPC is in/near a settlement (settlements have wells)
                loc = _npc_loc
                if loc and loc.kind in ("village", "town", "city", "hamlet", "castle"):
                    # Settlement residents can always get water from the well
                    water = make_item("Water Flask")
                    water.count = 4
                    npc.npc_add_item(water)
                    npc.needs["thirst"] = min(100, npc.needs["thirst"] + 30)
                    refilled = True
                if not refilled:
                    # Check nearby tiles for natural water sources
                    for dx in range(-3, 4):
                        for dy in range(-3, 4):
                            tx, ty = nx + dx, ny + dy
                            if (0 <= tx < self.world.width and 0 <= ty < self.world.height and
                                self.world.tiles[ty][tx] in (WELL, WATER, SHALLOW_WATER)):
                                water = make_item("Water Flask")
                                water.count = 3
                                npc.npc_add_item(water)
                                npc.needs["thirst"] = min(100, npc.needs["thirst"] + 25)
                                refilled = True
                                break
                        if refilled:
                            break

            # Water seeking — urgent survival behavior
            non_interruptible = ("fighting", "fleeing", "seeking_water")
            if npc.needs["thirst"] < 30 and not npc.has_drink():
                if npc.current_action not in non_interruptible:
                    water = self.world.find_water_near(int(npc.x), int(npc.y), 20)
                    if water:
                        npc.target_x, npc.target_y = float(water[0]), float(water[1])
                        npc.current_action = "seeking_water"
                        npc.action_timer = 0
                        npc.state = "walking"
                    else:
                        # Desperate: drink from puddles/dew
                        npc.needs["thirst"] = min(100, npc.needs["thirst"] + 10)
                        npc.current_action = ""
            elif npc.needs["thirst"] < 50 and not npc.has_drink() and npc.current_action == "":
                water = self.world.find_water_near(int(npc.x), int(npc.y), 15)
                if water:
                    npc.target_x, npc.target_y = float(water[0]), float(water[1])
                    npc.current_action = "seeking_water"
                    npc.state = "walking"
                else:
                    self._move_to_forage(npc)

            # Seek safe rest when very tired
            if npc.needs["rest"] < 18 and npc.current_action not in ("sleeping", "fleeing", "fighting"):
                # Try to go home first (safest bed)
                home_dist = npc.dist_to_pos(npc.home_x, npc.home_y)
                if home_dist < 20:
                    # Go home and sleep
                    npc.target_x = npc.home_x
                    npc.target_y = npc.home_y
                    npc.state = "walking"
                    npc.current_action = "seeking_bed"
                    npc.current_goal = "find a safe place to sleep"
                elif npc.needs["rest"] < 10:
                    # Desperate: check nearest settlement (use cached lookup)
                    loc = _npc_loc if _npc_loc else self.world.get_structure_at(npc.x, npc.y)
                    if loc and loc.kind in ("village", "town", "city", "tavern"):
                        npc.target_x = float(loc.x)
                        npc.target_y = float(loc.y)
                        npc.state = "walking"
                        npc.current_action = "seeking_bed"
                    else:
                        # Just go home
                        npc.target_x = npc.home_x
                        npc.target_y = npc.home_y
                        npc.state = "walking"
                        npc.current_action = "seeking_bed"

            # If seeking a bed and arrived, sleep
            if npc.current_action == "seeking_bed":
                if npc.target_x is not None:
                    dist = npc.dist_to_pos(npc.target_x, npc.target_y)
                    if dist < 2:
                        npc.current_action = "sleeping"
                        npc.state = "sleeping"
                        npc.state_timer = random.uniform(15, 30)
                        npc.action_timer = npc.state_timer
                        npc.target_x = None
                        npc.target_y = None

            # Damage from starvation/dehydration (reduced to give NPCs more time)
            if npc.needs["hunger"] <= 0:
                npc.hp -= 0.3 * dt
            if npc.needs["thirst"] <= 0:
                npc.hp -= 0.5 * dt

            if npc.hp <= 0:
                self._handle_npc_death(npc)

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

    def _request_decisions(self, npcs: List[NPC], dt: float, player: Player):
        now = time.time()
        for npc in npcs:
            if not npc.alive or npc.pending_llm_decision:
                continue

            # Skip detailed AI for distant NPCs (abstraction layer)
            if self._active_npc_set is not None and npc.name not in self._active_npc_set:
                continue

            if npc.current_action in ("chopping", "mining", "building", "farming",
                                       "fishing", "sleeping", "talking", "fighting",
                                       "training", "performing", "researching", "praying",
                                       "ritual", "enchanting", "crafting_pottery",
                                       "crafting_glass", "tanning", "dyeing",
                                       "training_animal", "seeking_bed", "fleeing",
                                       "approaching_player",
                                       "carrying", "commuting", "hunting",
                                       "smithing", "guarding"):
                continue  # busy

            npc.llm_decision_timer -= dt
            if npc.llm_decision_timer > 0:
                continue

            # Determine interval based on distance to player
            dist = npc.dist_to(player)
            interval = NPC_DECISION_INTERVAL if dist < NPC_DECISION_PRIORITY_RANGE else NPC_DECISION_INTERVAL_FAR
            npc.llm_decision_timer = interval

            # Rate limit
            if now - self._last_llm_time < self._llm_min_interval:
                continue
            self._last_llm_time = now

            # Build context with rich social data — use spatial grid
            nearby_parts = []
            for other in self.npc_grid.get_nearby(npc.x, npc.y, 10):
                if other is npc or not other.alive:
                    continue
                d = npc.dist_to(other)
                if d < 10:
                    # Get detailed relationship from social system
                    social_rel = self.social.get_rel(npc.name, other.name)
                    rel_label = social_rel.label
                    trust = social_rel.trust
                    other_cls = getattr(other, 'char_class', other.profession)
                    other_race = getattr(other, 'race', '')
                    mood_word = ""
                    if getattr(other, 'mood', 0) < -0.3:
                        mood_word = ", seems upset"
                    elif getattr(other, 'mood', 0) > 0.3:
                        mood_word = ", seems happy"
                    nearby_parts.append(
                        f"- {other.name} ({other_race} {other_cls}), {d:.0f} tiles, "
                        f"{rel_label} (trust:{trust:+.0f}){mood_word}"
                    )
            # Player
            if dist < 12:
                rel = npc.player_relationship
                rel_word = "friendly" if rel > 20 else "hostile" if rel < -20 else "neutral"
                nearby_parts.append(f"- Player (adventurer), {dist:.0f} tiles, {rel_word}")
            # Creatures — use spatial grid for O(1) lookup instead of full scan
            nearby_creatures = []
            for c in self.creature_grid.get_nearby(npc.x, npc.y, 8):
                if c.alive:
                    d = npc.dist_to(c)
                    if d < 8:
                        nearby_parts.append(f"- {c.kind} (hostile creature), {d:.0f} tiles")
                        nearby_creatures.append(c.kind)

            loc = self.world.get_structure_at(npc.x, npc.y)
            loc_name = loc.name if loc else "wilderness"

            time_norm = self.time_sys.normalized
            tod = "night" if self.time_sys.is_night else "morning" if time_norm < 0.4 else "afternoon" if time_norm < 0.7 else "evening"

            nearby_npc_names = [p.split("(")[0].strip("- ").strip() for p in nearby_parts if "hostile creature" not in p]

            # Build situational context (activity, economy, events)
            npc_situation = build_npc_context(
                npc, world=self.world,
                world_effects=getattr(self, 'world_effects', None),
                governance=getattr(self, 'governance', None),
                time_sys=self.time_sys,
                event_log=self.event_log,
                economy=getattr(self, 'economy', None),
            )

            # Use LLM if enabled, otherwise mock
            if self.llm.enabled:
                prompt = Prompts.npc_decision(
                    name=npc.name, profession=npc.profession,
                    personality=npc.personality_desc + (" [" + ", ".join(getattr(npc, 'social_traits', [])) + "]" if getattr(npc, 'social_traits', None) else "") + (f", age {int(getattr(npc, 'age', 30))}, {getattr(npc, 'title', 'commoner')}" if hasattr(npc, 'age') else ""),
                    attributes=npc.attr_summary(),
                    needs=npc.needs_summary(),
                    hp_status=f"{int(npc.hp)}/{npc.max_hp}",
                    gold=npc.npc_gold,
                    inventory=npc.inventory_summary(),
                    location=loc_name,
                    nearby="\n".join(nearby_parts) if nearby_parts else "nobody nearby",
                    memories="\n".join(npc.get_recent_memories(5)) or "none",
                    current_goal=npc.current_goal,
                    known_info="; ".join(npc.known_info[-5:]) if npc.known_info else "",
                    time_of_day=tod, day=self.time_sys.day,
                    consciousness=npc.consciousness,
                    char_class=getattr(npc, 'char_class', ''),
                    race=getattr(npc, 'race', ''),
                    level=getattr(npc, 'level', 1),
                    long_term_goals=", ".join(getattr(npc, 'long_term_goals', [])),
                    current_plan="; ".join(getattr(npc, 'current_plan', [])),
                    friends=self.social.get_relationship_summary(npc.name, 5) if hasattr(self, 'social') else ", ".join(getattr(npc, 'friends', [])),
                    enemies=", ".join(getattr(npc, 'enemies', [])),
                    party_info=npc.party_id or "",
                    class_abilities=", ".join(getattr(npc, 'class_abilities', [])),
                    spells_available=", ".join(getattr(npc, 'known_spells', [])) if getattr(npc, 'is_spellcaster', False) else "",
                    alignment=getattr(npc, 'alignment', ''),
                    situation_context=npc_situation,
                )
                priority = 10 if dist < NPC_DECISION_PRIORITY_RANGE else 1
                req_id = f"decision_{npc.name}_{now:.0f}"

                def _on_decision(text, _npc=npc):
                    _npc.pending_llm_decision = False

                self.llm.request(req_id, prompt, callback=_on_decision,
                                 max_tokens=60, temperature=0.8)
                # Store req_id so we can poll
                npc._decision_req_id = req_id
                npc.pending_llm_decision = True
            else:
                # Check schedule first - gives NPCs daily routines
                from game.systems.schedules import get_scheduled_action
                scheduled = get_scheduled_action(
                    npc, self.time_sys.normalized, self.world, self.world.structures)

                if scheduled and random.random() < 0.85:  # 85% follow schedule, 15% free will
                    decision = f"{scheduled['action']} | {scheduled.get('target_x', 'nearby')} | {scheduled['reason']}"
                    if scheduled.get('target_x') is not None:
                        npc.target_x = scheduled['target_x']
                        npc.target_y = scheduled.get('target_y', npc.y)
                else:
                    decision = mock_npc_decision(
                        npc.needs, npc.has_food(), npc.has_drink(),
                        nearby_npc_names, nearby_creatures, npc.profession,
                        char_class=getattr(npc, 'char_class', npc.profession),
                        long_term_goals=getattr(npc, 'long_term_goals', []),
                        friends=getattr(npc, 'friends', []),
                        party_id=getattr(npc, 'party_id', None),
                        alignment=getattr(npc, 'alignment', 'true neutral'),
                    )
                self._apply_decision(npc, decision)

    def _poll_decisions(self, npcs: List[NPC]):
        for npc in npcs:
            if not npc.pending_llm_decision:
                continue
            req_id = getattr(npc, "_decision_req_id", None)
            if not req_id:
                continue
            result = self.llm.get_result(req_id)
            if result:
                npc.pending_llm_decision = False
                self._apply_decision(npc, result)

    def _apply_decision(self, npc: NPC, decision_text: str):
        """Parse and execute a decision string: ACTION | TARGET | REASON"""
        action, target, reason = self._parse_decision(decision_text)
        npc.last_decision_reason = reason
        self._execute_action(npc, action, target, reason)

    def _parse_decision(self, text: str) -> Tuple[str, str, str]:
        """Parse 'ACTION | TARGET | REASON' format."""
        text = text.strip().split("\n")[0]  # First line only
        parts = [p.strip() for p in text.split("|")]
        if len(parts) >= 3:
            return parts[0].upper(), parts[1], parts[2]
        elif len(parts) == 2:
            return parts[0].upper(), parts[1], ""
        else:
            # Try to extract just the action
            word = text.split()[0].upper() if text.split() else "IDLE"
            return word, "", ""

    # ---- ACTION EXECUTION ----

    def _execute_action(self, npc: NPC, action: str, target: str, reason: str):
        action = action.split()[0]  # Just the first word
        # Clear stale movement targets so timed actions don't get stuck
        # (individual actions that need movement will re-set these)
        if action not in ("MOVE_TO", "MOVE", "APPROACH_PLAYER", "FLEE"):
            npc.target_x = None
            npc.target_y = None

        if action == "EAT":
            eaten = npc.consume_food()
            if eaten:
                npc.add_memory("action", f"Ate {eaten}", 1)
                npc.current_action = ""
            else:
                npc.current_goal = "find food"
                self._move_to_forage(npc)

        elif action == "DRINK":
            drunk = npc.consume_drink()
            if drunk:
                npc.add_memory("action", f"Drank {drunk}", 1)
                npc.current_action = ""
            else:
                # Try to find water source
                water = self.world.find_water_near(int(npc.x), int(npc.y))
                if water:
                    npc.target_x, npc.target_y = float(water[0]), float(water[1])
                    npc.state = "walking"
                    npc.current_action = "seeking_water"
                    npc.current_goal = "find water"

        elif action == "SLEEP":
            npc.current_action = "sleeping"
            npc.state = "sleeping"
            npc.target_x = npc.home_x
            npc.target_y = npc.home_y
            npc.state_timer = random.uniform(10, 30)
            npc.action_timer = npc.state_timer

        elif action == "FORAGE":
            self._move_to_forage(npc)

        elif action == "CHOP_TREE":
            tree = self.world.find_nearest_tile(int(npc.x), int(npc.y), {FOREST, DENSE_FOREST}, 8)
            if tree and npc.npc_has_item("Axe"):
                npc.target_x, npc.target_y = float(tree[0]), float(tree[1])
                npc.current_action = "chopping"
                npc.action_timer = NPC_CHOP_TIME - npc.attributes.get("strength", 5) * 0.3
                npc.action_target = tree
                npc.state = "working"
            else:
                npc.current_action = ""

        elif action == "MINE_ROCK":
            rock = self.world.find_nearest_tile(int(npc.x), int(npc.y), {MOUNTAIN}, 8)
            if rock and npc.npc_has_item("Pickaxe"):
                npc.target_x, npc.target_y = float(rock[0]), float(rock[1])
                npc.current_action = "mining"
                npc.action_timer = NPC_MINE_TIME - npc.attributes.get("strength", 5) * 0.4
                npc.action_target = rock
                npc.state = "working"

        elif action == "BUILD":
            what = target.lower() if target else "floor"
            # Need wood for floor, stone for wall
            if "wall" in what and npc.npc_count_item("Stone") >= 2:
                npc.current_action = "building"
                npc.action_target = ("wall", BUILT_WALL)
                npc.action_timer = NPC_BUILD_TIME
            elif npc.npc_count_item("Wood") >= 2:
                npc.current_action = "building"
                npc.action_target = ("floor", BUILT_FLOOR)
                npc.action_timer = NPC_BUILD_TIME
            else:
                npc.current_action = ""

        elif action == "FARM":
            sub = target.lower() if target else "plant"
            if "harvest" in sub:
                farm = self.world.find_nearest_tile(int(npc.x), int(npc.y), {FARMLAND}, 6)
                if farm:
                    npc.target_x, npc.target_y = float(farm[0]), float(farm[1])
                    npc.current_action = "farming"
                    npc.action_target = "harvest"
                    npc.action_timer = NPC_FARM_TIME
            else:
                if npc.npc_has_item("Hoe") and npc.npc_has_item("Seeds"):
                    grass = self.world.find_nearest_tile(int(npc.x), int(npc.y), {GRASS}, 8)
                    if grass:
                        npc.target_x, npc.target_y = float(grass[0]), float(grass[1])
                        npc.current_action = "farming"
                        npc.action_target = "plant"
                        npc.action_timer = NPC_FARM_TIME

        elif action == "FISH":
            water = self.world.find_water_near(int(npc.x), int(npc.y), 6)
            if water and npc.npc_has_item("Fishing Rod"):
                npc.target_x, npc.target_y = float(water[0]), float(water[1])
                npc.current_action = "fishing"
                npc.action_timer = NPC_FORAGE_TIME
                npc.state = "working"

        elif action == "TALK_TO":
            self._start_talk(npc, target)

        elif action == "TRADE":
            self._start_trade(npc, target)

        elif action == "PERSUADE":
            self._start_persuade(npc, target)

        elif action == "FIGHT":
            self._start_fight(npc, target)

        elif action == "FLEE":
            npc.state = "fleeing"
            angle = random.uniform(0, 2 * math.pi)
            npc.target_x = npc.x + math.cos(angle) * 12
            npc.target_y = npc.y + math.sin(angle) * 12
            npc.state_timer = 5.0
            npc.current_action = "fleeing"

        elif action == "GIVE":
            self._give_item(npc, target)

        elif action.startswith("MOVE"):
            self._move_npc(npc, target)

        elif action == "IDLE":
            npc.current_action = "idle"
            npc.state = "idle"
            npc.state_timer = random.uniform(3, 8)

        elif action == "APPROACH_PLAYER":
            # Move toward player to initiate conversation
            npc.target_x = self._player_ref.x if hasattr(self, '_player_ref') else npc.home_x
            npc.target_y = self._player_ref.y if hasattr(self, '_player_ref') else npc.home_y
            npc.current_action = "approaching_player"
            npc.approach_reason = reason
            npc.state = "walking"
            npc.state_timer = 15.0

        elif action == "FORM_PARTY":
            other = self._find_npc(target)
            if other and other.alive and not getattr(other, 'party_id', None):
                party_id = f"party_{npc.name}_{id(npc)}"
                npc.party_id = party_id
                npc.party_role = "leader"
                other.party_id = party_id
                other.party_role = "member"
                if npc.name not in getattr(other, 'friends', []):
                    if not hasattr(other, 'friends'):
                        other.friends = []
                    other.friends.append(npc.name)
                if other.name not in getattr(npc, 'friends', []):
                    npc.friends.append(other.name)
                npc.add_memory("social", f"Formed an adventuring party with {other.name}", 4)
                other.add_memory("social", f"Joined {npc.name}'s adventuring party", 4)
                self.event_log.append(f"{npc.name} and {other.name} formed an adventuring party!")
                # Record in life ledgers
                from game.systems.memory import ensure_life_ledger
                ensure_life_ledger(npc).record_milestone(
                    "formed_party", f"Formed a party with {other.name}", self.time_sys.day)
                ensure_life_ledger(npc).record_bond(
                    other.name, "party_member", self.time_sys.day, trust=30)
                ensure_life_ledger(other).record_milestone(
                    "joined_party", f"Joined {npc.name}'s party", self.time_sys.day)
                ensure_life_ledger(other).record_bond(
                    npc.name, "party_leader", self.time_sys.day, trust=30)
                npc.current_action = ""

        elif action == "SEEK_QUEST":
            # Move to nearest castle, tavern, or village for quests
            for s in self.world.structures:
                if s.kind in ("castle", "tavern", "village"):
                    npc.target_x, npc.target_y = float(s.x), float(s.y)
                    npc.current_action = "moving"
                    npc.current_goal = "find a quest or purpose"
                    npc.state = "walking"
                    npc.state_timer = 30.0
                    break

        elif action == "CAST_SPELL":
            # Simple spell casting
            if getattr(npc, 'is_spellcaster', False) and getattr(npc, 'known_spells', []):
                spell_name = target.split(" ON ")[0].strip() if " ON " in target else target
                from game.data.dnd import SPELLS
                spell = SPELLS.get(spell_name)
                if spell and spell["level"] <= 1:
                    # Damage spell on creature (spatial grid lookup)
                    if spell.get("damage", 0) > 0:
                        spell_range = spell.get("range", 5)
                        for c in self.creature_grid.get_nearby(npc.x, npc.y, spell_range):
                            if c.alive and npc.dist_to(c) < spell_range:
                                c.take_damage(spell["damage"])
                                npc.add_memory("combat", f"Cast {spell_name} on {c.kind}", 2)
                                break
                    # Heal spell on self or ally
                    elif spell.get("damage", 0) < 0:
                        heal_amount = abs(spell["damage"])
                        npc.heal(heal_amount)
                        npc.add_memory("action", f"Cast {spell_name} to heal", 1)
            npc.current_action = ""

        elif action == "REST_AT_TAVERN":
            loc = self.world.get_structure_at(npc.x, npc.y)
            if loc and loc.kind in ("tavern", "village"):
                npc.target_x, npc.target_y = float(loc.x), float(loc.y)
            else:
                # Fall back to home
                npc.target_x, npc.target_y = npc.home_x, npc.home_y
            if npc.target_x is not None:
                npc.current_action = "moving"
                npc.current_goal = "rest at tavern"
                npc.state = "walking"
                npc.state_timer = 20.0

        elif action == "VISIT_TEMPLE":
            for s in self.world.structures:
                if s.kind in ("temple", "shrine"):
                    npc.target_x, npc.target_y = float(s.x), float(s.y)
                    npc.current_action = "moving"
                    npc.current_goal = "visit temple"
                    npc.state = "walking"
                    npc.state_timer = 20.0
                    break

        elif action == "CRAFT":
            npc.current_action = ""
            npc.add_memory("action", f"Attempted to craft {target}", 1)

        # ================================================================
        # EXPANDED SKILL-BASED ACTIONS
        # ================================================================

        elif action == "MAKE_FIRE":
            # NPC builds or tends a fire
            if npc.npc_has_item("Wood") or npc.npc_has_item("Torch"):
                fire = self.fire_mgr.get_fire_near(npc.x, npc.y, 3.0)
                if not fire:
                    fire = self.fire_mgr.create_fire(int(npc.x), int(npc.y), "campfire")
                fuel = "Wood" if npc.npc_has_item("Wood") else "Torch"
                fire.add_fuel(fuel)
                npc.npc_remove_item(fuel)
                npc.add_memory("action", "Built a fire to stay warm", 1)
                from game.systems.skills import gain_skill_xp
                gain_skill_xp(npc, "tracking", 0.5)  # survival skill
            npc.current_action = ""

        elif action == "GATHER_FIREWOOD":
            # NPC gathers wood for fuel
            tree = self.world.find_nearest_tile(int(npc.x), int(npc.y),
                                                {FOREST, DENSE_FOREST}, 10)
            if tree:
                npc.target_x, npc.target_y = float(tree[0]), float(tree[1])
                npc.current_action = "chopping"
                npc.action_timer = NPC_CHOP_TIME
                npc.action_target = tree
                npc.state = "working"
                npc.current_goal = "gather firewood"
            else:
                npc.current_action = ""

        elif action == "FETCH_WATER":
            # NPC goes to nearest well/water source and fills up supplies
            water = self.world.find_water_near(int(npc.x), int(npc.y), 20)
            if water:
                npc.target_x, npc.target_y = float(water[0]), float(water[1])
                npc.current_action = "seeking_water"
                npc.state = "walking"
                npc.current_goal = "fetch water for the settlement"
            else:
                npc.current_action = ""

        elif action == "TRAIN_COMBAT":
            from game.systems.skills import gain_skill_xp, skill_check
            zone = self._find_zone_for_npc(npc, "training_ground")
            if zone:
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "training"
                npc.action_timer = NPC_TRAIN_TIME
                # Determine which combat skill to train
                combat_skill = "swordsmanship"
                if npc.npc_skills.get("archery", 0) > npc.npc_skills.get("swordsmanship", 0):
                    combat_skill = "archery"
                elif npc.npc_skills.get("unarmed", 0) > npc.npc_skills.get("swordsmanship", 0):
                    combat_skill = "unarmed"
                npc.action_target = combat_skill
            else:
                npc.current_action = ""

        elif action == "TRAIN_ARCHERY":
            from game.systems.skills import gain_skill_xp
            zone = self._find_zone_for_npc(npc, "archery_range")
            if zone and (npc.npc_has_item("Hunting Bow") or npc.npc_has_item("Arrows")):
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "training"
                npc.action_timer = NPC_TRAIN_TIME
                npc.action_target = "archery"
            else:
                npc.current_action = ""

        elif action in ("GUARD_WALL", "GUARD_GATE", "GUARD_TOWER", "PATROL", "SCOUT"):
            # Military duty actions — move to defensive position
            npc.state = "working"
            npc.current_action = "guarding"
            npc.action_timer = random.uniform(8.0, 15.0)

            # Find the nearest appropriate position
            home_struct = None
            for s in self.world.structures:
                if s.kind in ("village", "town", "city", "castle",
                              "orc_stronghold", "goblin_warren"):
                    if abs(npc.home_x - s.x) < s.radius + 5 and abs(npc.home_y - s.y) < s.radius + 5:
                        home_struct = s
                        break

            if home_struct:
                r = home_struct.radius
                if action == "GUARD_WALL":
                    # Move to a point on the settlement perimeter (wall)
                    angle = random.uniform(0, 2 * math.pi)
                    npc.target_x = home_struct.x + math.cos(angle) * (r - 1)
                    npc.target_y = home_struct.y + math.sin(angle) * (r - 1)
                elif action == "GUARD_GATE":
                    # Move to one of the 4 gate positions (N/S/E/W)
                    gate_dir = random.choice([(0, -1), (0, 1), (-1, 0), (1, 0)])
                    npc.target_x = home_struct.x + gate_dir[0] * r
                    npc.target_y = home_struct.y + gate_dir[1] * r
                elif action == "GUARD_TOWER":
                    # Move to nearest guard tower building
                    for bx, by, bw, bh in getattr(home_struct, 'buildings', []):
                        if bw <= 5 and bh <= 5:  # small buildings are likely towers
                            npc.target_x = float(bx + bw // 2)
                            npc.target_y = float(by + bh // 2)
                            break
                    else:
                        # Fallback: perimeter position
                        angle = random.uniform(0, 2 * math.pi)
                        npc.target_x = home_struct.x + math.cos(angle) * r
                        npc.target_y = home_struct.y + math.sin(angle) * r
                elif action in ("PATROL", "SCOUT"):
                    # Walk a section of the perimeter
                    angle = random.uniform(0, 2 * math.pi)
                    npc.target_x = home_struct.x + math.cos(angle) * (r + 3)
                    npc.target_y = home_struct.y + math.sin(angle) * (r + 3)

                # Gain military skills from duty
                from game.systems.skills import gain_skill_xp
                gain_skill_xp(npc, "swordsmanship", 0.1)
                if action in ("GUARD_TOWER", "SCOUT"):
                    gain_skill_xp(npc, "archery", 0.2)
                    gain_skill_xp(npc, "navigation", 0.1)
                if action == "PATROL":
                    gain_skill_xp(npc, "navigation", 0.15)
            else:
                npc.current_action = ""

        elif action == "PERFORM":
            from game.systems.skills import skill_check, gain_skill_xp
            npc.current_action = "performing"
            npc.action_timer = NPC_PERFORM_TIME
            npc.state = "working"
            npc.action_target = "performance"
            npc.target_x = None  # perform in place
            npc.target_y = None

        elif action == "HEAL_OTHER":
            from game.systems.skills import skill_check, gain_skill_xp
            other = self._find_npc(target)
            if other and other.alive and other.hp < other.max_hp:
                has_kit = npc.npc_has_item("Healer's Kit") or npc.npc_has_item("Herbalism Kit")
                if has_kit and npc.dist_to(other) < NPC_CONVERSATION_RANGE + 2:
                    success, total, natural = skill_check(npc, "medicine", 12)
                    if success:
                        heal_amt = 10 + npc.npc_skills.get("medicine", 0) * 3
                        other.heal(heal_amt)
                        npc.add_memory("action", f"Healed {other.name} for {heal_amt} HP", 2)
                        other.add_memory("social", f"{npc.name} healed me", 2)
                        gain_skill_xp(npc, "medicine", 1.5)
                    else:
                        npc.add_memory("action", f"Failed to heal {other.name}", 1)
                        gain_skill_xp(npc, "medicine", 0.5)
                else:
                    if other and other.alive:
                        npc.target_x, npc.target_y = other.x, other.y
                        npc.state = "walking"
                        npc.current_action = "moving"
                        npc.state_timer = 10.0
                    else:
                        npc.current_action = ""
            else:
                npc.current_action = ""

        elif action == "RESEARCH":
            from game.systems.skills import skill_check, gain_skill_xp
            zone = self._find_zone_for_npc(npc, "library")
            if zone:
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "researching"
                npc.action_timer = NPC_RESEARCH_TIME
                # Pick research topic based on class
                if npc.is_spellcaster:
                    npc.action_target = "arcana"
                elif npc.char_class in ("Cleric", "Paladin"):
                    npc.action_target = "religion"
                else:
                    npc.action_target = "history"
            else:
                npc.current_action = ""

        elif action == "PRAY":
            from game.systems.skills import skill_check, gain_skill_xp
            zone = self._find_zone_for_npc(npc, "chapel")
            if zone:
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "praying"
                npc.action_timer = 4.0
                npc.action_target = "religion"
            else:
                # Can pray anywhere
                npc.state = "working"
                npc.current_action = "praying"
                npc.action_timer = 4.0
                npc.action_target = "religion"
                npc.target_x = None
                npc.target_y = None

        elif action == "PICK_LOCK":
            from game.systems.skills import skill_check, gain_skill_xp
            if npc.npc_has_item("Thieves' Tools") or npc.npc_has_item("Lockpick"):
                # Find nearby locked door
                nx, ny = int(npc.x), int(npc.y)
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        tx, ty = nx + dx, ny + dy
                        if 0 <= tx < self.world.width and 0 <= ty < self.world.height:
                            if self.world.tiles[ty][tx] == LOCKED_DOOR:
                                success, total, natural = skill_check(npc, "lockpicking", 14)
                                if success:
                                    self.world.modify_tile(tx, ty, DOOR)
                                    npc.add_memory("action", "Picked a lock successfully", 2)
                                    gain_skill_xp(npc, "lockpicking", 2.0)
                                else:
                                    npc.add_memory("action", "Failed to pick a lock", 1)
                                    gain_skill_xp(npc, "lockpicking", 0.5)
                                    # Lockpick might break
                                    if natural == 1 and npc.npc_has_item("Lockpick"):
                                        npc.npc_remove_item("Lockpick")
                                npc.current_action = ""
                                return
                npc.current_action = ""
            else:
                npc.current_action = ""

        elif action == "PICKPOCKET":
            from game.systems.skills import skill_check_contested, gain_skill_xp
            other = self._find_npc(target)
            if other and other.alive and npc.dist_to(other) < NPC_CONVERSATION_RANGE:
                won = skill_check_contested(npc, "pickpocketing", other, "insight")
                if won and other.npc_inventory:
                    stolen = random.choice(other.npc_inventory)
                    other.npc_remove_item(stolen.name)
                    npc.npc_add_item(make_item(stolen.name))
                    npc.add_memory("action", f"Stole {stolen.name} from {other.name}", 3)
                    gain_skill_xp(npc, "pickpocketing", 2.0)
                    gain_skill_xp(npc, "stealth", 0.5)
                    # Record crime in both ledgers
                    from game.systems.memory import ensure_life_ledger
                    ensure_life_ledger(npc).record_crime(
                        "theft", f"Stole {stolen.name} from {other.name}",
                        self.time_sys.day, perpetrator=npc.name, victim=other.name,
                        witnessed=False)
                elif not won:
                    # Caught!
                    npc.add_memory("action", f"Caught trying to steal from {other.name}!", 3)
                    other.add_memory("social", f"{npc.name} tried to steal from me!", 4)
                    from game.systems.memory import ensure_life_ledger
                    ensure_life_ledger(other).record_crime(
                        "theft_attempt", f"{npc.name} tried to steal from me",
                        self.time_sys.day, perpetrator=npc.name, victim=other.name,
                        witnessed=True)
                    rel = self.social.get_rel(other.name, npc.name)
                    rel.trust = max(-100, rel.trust - 30)
                    rel.update_status()
                    gain_skill_xp(npc, "pickpocketing", 0.3)
                    self.event_log.append(f"{other.name} caught {npc.name} stealing!")
            npc.current_action = ""

        elif action == "SNEAK":
            from game.systems.skills import skill_check, gain_skill_xp
            success, total, natural = skill_check(npc, "stealth", 12)
            if success:
                npc.state = "walking"
                npc.speed = NPC_SPEED * 0.6  # slower but stealthy
                npc.state_timer = 15.0
                npc.add_memory("action", "Sneaking around undetected", 1)
                gain_skill_xp(npc, "stealth", 1.0)
            else:
                gain_skill_xp(npc, "stealth", 0.3)
            npc.current_action = ""

        elif action == "SET_TRAP":
            from game.systems.skills import skill_check, gain_skill_xp
            has_materials = (npc.npc_has_item("Trap") or
                           (npc.npc_has_item("Rope") and npc.npc_count_item("Iron Ingot") >= 1))
            if has_materials:
                success, total, natural = skill_check(npc, "trap_making", 11)
                if success:
                    if npc.npc_has_item("Trap"):
                        npc.npc_remove_item("Trap")
                    else:
                        npc.npc_remove_item("Rope")
                        npc.npc_remove_item("Iron Ingot")
                    npc.add_memory("action", "Set a trap successfully", 2)
                    gain_skill_xp(npc, "trap_making", 1.5)
                else:
                    npc.add_memory("action", "Failed to set trap properly", 1)
                    gain_skill_xp(npc, "trap_making", 0.5)
            npc.current_action = ""

        elif action == "TRACK":
            from game.systems.skills import skill_check, gain_skill_xp
            success, total, natural = skill_check(npc, "tracking", 12)
            if success:
                # Find nearest creature using spatial grid
                found = False
                for c in self.creature_grid.get_nearby(npc.x, npc.y, 30):
                    if c.alive and npc.dist_to(c) < 30:
                        npc.add_memory("action", f"Tracked a {c.kind} at ({int(c.x)},{int(c.y)})", 2)
                        gain_skill_xp(npc, "tracking", 1.5)
                        found = True
                        break
                if not found:
                    npc.add_memory("action", "Found no creature tracks nearby", 1)
                    gain_skill_xp(npc, "tracking", 0.5)
            else:
                gain_skill_xp(npc, "tracking", 0.3)
            npc.current_action = ""

        elif action == "NAVIGATE":
            from game.systems.skills import skill_check, gain_skill_xp
            success, total, natural = skill_check(npc, "navigation", 10)
            if success:
                npc.speed = NPC_SPEED * 1.3  # temporary speed boost from good navigation
                npc.state_timer = 20.0
                gain_skill_xp(npc, "navigation", 1.0)
            else:
                gain_skill_xp(npc, "navigation", 0.3)
            npc.current_action = ""

        elif action == "CLIMB":
            from game.systems.skills import skill_check, gain_skill_xp
            success, total, natural = skill_check(npc, "climbing", 13)
            if success:
                npc.add_memory("action", "Scaled a difficult surface", 1)
                gain_skill_xp(npc, "climbing", 1.5)
            else:
                # Fall damage on failure
                npc.take_damage(random.randint(3, 8))
                npc.add_memory("action", "Fell while trying to climb!", 2)
                gain_skill_xp(npc, "climbing", 0.5)
            npc.current_action = ""

        elif action == "SWIM":
            from game.systems.skills import skill_check, gain_skill_xp
            success, total, natural = skill_check(npc, "swimming", 11)
            if success:
                gain_skill_xp(npc, "swimming", 1.0)
            else:
                npc.take_damage(random.randint(2, 5))
                npc.add_memory("action", "Struggled in the water", 1)
                gain_skill_xp(npc, "swimming", 0.5)
            npc.current_action = ""

        elif action == "TRAIN_ANIMAL":
            from game.systems.skills import skill_check, gain_skill_xp
            zone = self._find_zone_for_npc(npc, "stable")
            if zone:
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "training_animal"
                npc.action_timer = NPC_TRAIN_TIME
                npc.action_target = "animal_training"
            else:
                npc.current_action = ""

        elif action == "PERFORM_RITUAL":
            from game.systems.skills import skill_check, gain_skill_xp
            zone = self._find_zone_for_npc(npc, "ritual_circle")
            if zone and getattr(npc, 'is_spellcaster', False):
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "ritual"
                npc.action_timer = NPC_RITUAL_TIME
                npc.action_target = "ritual_magic"
            else:
                npc.current_action = ""

        elif action == "SET_WARD":
            from game.systems.skills import skill_check, gain_skill_xp
            if npc.npc_has_item("Ward Stones"):
                success, total, natural = skill_check(npc, "warding", 14)
                if success:
                    npc.npc_remove_item("Ward Stones")
                    npc.add_memory("action", "Set a protective ward", 3)
                    gain_skill_xp(npc, "warding", 2.0)
                else:
                    npc.add_memory("action", "Ward spell fizzled", 1)
                    gain_skill_xp(npc, "warding", 0.5)
            npc.current_action = ""

        elif action == "DIVINE":
            from game.systems.skills import skill_check, gain_skill_xp
            if npc.npc_has_item("Divination Crystal"):
                success, total, natural = skill_check(npc, "divination", 13)
                if success:
                    # Learn about a random world event or creature location
                    visions = [
                        "a storm gathering in the north",
                        "danger approaching from the east",
                        "a treasure hidden in nearby ruins",
                        "a friend in need of help",
                        "prosperity for the village",
                    ]
                    vision = random.choice(visions)
                    npc.add_memory("action", f"Divination vision: {vision}", 3)
                    npc.known_info.append(f"A vision showed {vision}")
                    gain_skill_xp(npc, "divination", 2.0)
                else:
                    npc.add_memory("action", "Divination was unclear", 1)
                    gain_skill_xp(npc, "divination", 0.5)
            npc.current_action = ""

        elif action == "ENCHANT_ITEM":
            from game.systems.skills import skill_check, gain_skill_xp
            zone = self._find_zone_for_npc(npc, "enchanting_room")
            if zone and npc.npc_has_item("Enchanter's Focus"):
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "enchanting"
                npc.action_timer = NPC_ENCHANT_TIME
                npc.action_target = "enchanting"
            else:
                npc.current_action = ""

        elif action == "MAKE_MAP":
            from game.systems.skills import skill_check, gain_skill_xp
            if npc.npc_has_item("Cartographer's Kit") and npc.npc_has_item("Ink"):
                success, total, natural = skill_check(npc, "cartography", 12)
                if success:
                    npc.npc_remove_item("Ink")
                    new_map = make_item("Regional Map")
                    npc.npc_add_item(new_map)
                    npc.add_memory("action", "Drew a regional map", 2)
                    gain_skill_xp(npc, "cartography", 2.0)
                else:
                    npc.add_memory("action", "Map drawing was inaccurate", 1)
                    gain_skill_xp(npc, "cartography", 0.5)
            npc.current_action = ""

        elif action == "CRAFT_POTTERY":
            from game.systems.skills import gain_skill_xp
            zone = self._find_zone_for_npc(npc, "pottery_studio")
            if zone and npc.npc_count_item("Clay") >= 2:
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "crafting_pottery"
                npc.action_timer = NPC_CRAFT_TIME
                npc.action_target = "pottery"
            else:
                npc.current_action = ""

        elif action == "CRAFT_GLASS":
            from game.systems.skills import gain_skill_xp
            zone = self._find_zone_for_npc(npc, "glassworks")
            if zone and npc.npc_has_item("Glassblower's Tools") and npc.npc_count_item("Sand") >= 2:
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "crafting_glass"
                npc.action_timer = NPC_CRAFT_TIME
                npc.action_target = "glassblowing"
            else:
                npc.current_action = ""

        elif action == "TAN_HIDE":
            from game.systems.skills import gain_skill_xp
            zone = self._find_zone_for_npc(npc, "tannery")
            if zone and npc.npc_has_item("Wolf Pelt"):
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "tanning"
                npc.action_timer = NPC_CRAFT_TIME
                npc.action_target = "tanning"
            else:
                npc.current_action = ""

        elif action == "DYE_CLOTH":
            from game.systems.skills import gain_skill_xp
            zone = self._find_zone_for_npc(npc, "dye_house")
            if zone and npc.npc_has_item("Dye Kit") and npc.npc_has_item("Linen"):
                npc.target_x, npc.target_y = zone.center
                npc.state = "working"
                npc.current_action = "dyeing"
                npc.action_timer = NPC_CRAFT_TIME
                npc.action_target = "dyeing"
            else:
                npc.current_action = ""

        elif action in ("JOKE_WITH", "COMFORT", "ARGUE_WITH", "INTIMIDATE",
                        "SHARE_MEAL", "FLIRT_WITH", "CHALLENGE", "SPAR_WITH"):
            # Social interactions handled by the social system
            other = self._find_npc(target)
            if other and other.alive and npc.dist_to(other) < NPC_CONVERSATION_RANGE + 2:
                action_to_social = {
                    "JOKE_WITH": "joke", "COMFORT": "comfort", "ARGUE_WITH": "argue",
                    "INTIMIDATE": "intimidate", "SHARE_MEAL": "share_meal",
                    "FLIRT_WITH": "flirt", "CHALLENGE": "challenge", "SPAR_WITH": "spar",
                }
                social_type = action_to_social.get(action, "friendly_chat")
                from game.systems.social import SOCIAL_INTERACTIONS
                idata = SOCIAL_INTERACTIONS.get(social_type, SOCIAL_INTERACTIONS["friendly_chat"])
                # Execute the social interaction
                rel_ab = self.social.get_rel(npc.name, other.name)
                rel_ba = self.social.get_rel(other.name, npc.name)
                trust_min, trust_max = idata["trust_change"]
                cha_mod = (npc.attributes.get("charisma", 5) - 5) * 0.5
                trust_change = random.uniform(trust_min, trust_max) + cha_mod
                mood_min, mood_max = idata["mood_change"]
                mood_change = random.uniform(mood_min, mood_max)

                rel_ab.trust = max(-100, min(100, rel_ab.trust + trust_change))
                rel_ba.trust = max(-100, min(100, rel_ba.trust + trust_change * 0.7))
                rel_ab.interaction_count += 1
                rel_ab.update_status()
                rel_ba.update_status()

                npc.needs["social"] = min(100, npc.needs.get("social", 50) + abs(mood_change) * 0.5)
                other.needs["social"] = min(100, other.needs.get("social", 50) + abs(mood_change) * 0.3)

                desc = idata["description"].format(a=npc.name, b=other.name)
                npc.add_memory("social", desc, 2)
                other.add_memory("social", desc, 2)
                self.event_log.append(desc)
                npc.current_action = ""
            else:
                # Not nearby - move toward them
                if other and other.alive:
                    npc.target_x, npc.target_y = other.x, other.y
                    npc.state = "walking"
                    npc.current_action = "moving"
                    npc.state_timer = 10.0
                else:
                    npc.current_action = ""

        else:
            npc.current_action = ""
            npc.state_timer = random.uniform(2, 5)

    def _move_to_forage(self, npc: NPC):
        """Move to forest to forage for food/water."""
        forest = self.world.find_nearest_tile(int(npc.x), int(npc.y), {FOREST, DENSE_FOREST}, 12)
        if forest:
            npc.target_x, npc.target_y = float(forest[0]), float(forest[1])
            npc.current_action = "foraging"
            npc.action_timer = NPC_FORAGE_TIME
            npc.state = "walking"
        else:
            npc.current_action = ""

    def _move_npc(self, npc: NPC, target: str):
        """Move to the NEAREST matching location, NPC, or direction."""
        # Check travel restrictions based on social class
        from game.systems.social_class import can_travel
        gov_style = "feudalism"
        if hasattr(self, 'governance'):
            for k in self.governance.kingdoms.values():
                gov_style = getattr(k, 'governing_style', 'feudalism')
                break
        if not can_travel(npc, gov_style):
            # Restricted — can only move near home
            if "home" not in target.lower():
                home_dist = npc.dist_to_pos(npc.home_x, npc.home_y)
                if home_dist > 20:
                    # Already far — go home instead
                    npc.target_x, npc.target_y = npc.home_x, npc.home_y
                    npc.state = "walking"
                    npc.current_action = "moving"
                    npc.state_timer = 15.0
                    return

        target_lower = target.lower().strip()

        # Find nearest matching structure
        best = None
        best_dist = float('inf')
        for s in self.world.structures:
            matches = (target_lower in s.name.lower() or target_lower in s.kind or
                      (target_lower in ("village", "town", "settlement", "nearby") and s.kind in ("village", "town", "city", "hamlet")) or
                      (target_lower in ("ruins", "dungeon") and s.kind in ("ruins", "dungeon")) or
                      (target_lower in ("tavern", "inn") and s.kind == "tavern") or
                      (target_lower in ("temple", "shrine") and s.kind in ("temple", "shrine")) or
                      (target_lower in ("castle", "fortress") and s.kind == "castle") or
                      (target_lower in ("forest", "wilderness") and s.kind in ("ruins",)))  # forests aren't structures
            if matches:
                d = npc.dist_to_pos(s.x, s.y)
                if d < best_dist:
                    best_dist = d
                    best = s

        if best:
            dest_x, dest_y = float(best.x), float(best.y)

            # For long journeys, plan supplies first
            if best_dist > 30 and hasattr(self, 'world_map'):
                from game.systems.world_map import plan_journey, prepare_for_journey
                plan = plan_journey(npc, dest_x, dest_y, self.world_map)
                if plan["supplies_needed"]:
                    # Try to prepare
                    ready = prepare_for_journey(npc, plan)
                    if not ready and not plan["should_go"]:
                        # Can't afford supplies for this journey — stay put
                        npc.current_action = ""
                        npc.add_memory("action",
                            f"Wanted to travel to {best.name} but lacked supplies", 1)
                        return

            npc.target_x, npc.target_y = dest_x, dest_y
            npc.state = "walking"
            npc.current_action = "moving"
            npc.state_timer = max(10, best_dist * 0.3)
            return

        # Try to find a named NPC nearby
        nearby_npcs = self.npc_grid.get_nearby(npc.x, npc.y, 30) if hasattr(self, 'npc_grid') else []
        for other in nearby_npcs:
            if other.name.lower() == target_lower and other.alive:
                npc.target_x, npc.target_y = other.x, other.y
                npc.state = "walking"
                npc.current_action = "moving"
                npc.state_timer = 20.0
                return

        # Direction or "home"
        if "home" in target_lower:
            npc.target_x, npc.target_y = npc.home_x, npc.home_y
        elif "north" in target_lower:
            npc.target_y = npc.y - random.uniform(5, 12)
        elif "south" in target_lower:
            npc.target_y = npc.y + random.uniform(5, 12)
        elif "east" in target_lower:
            npc.target_x = npc.x + random.uniform(5, 12)
        elif "west" in target_lower:
            npc.target_x = npc.x - random.uniform(5, 12)
        else:
            # Random wander — stay near home, don't wander into wilderness
            angle = random.uniform(0, 2 * math.pi)
            d = random.uniform(3, 8)
            # Bias toward home to prevent drift
            home_dx = npc.home_x - npc.x
            home_dy = npc.home_y - npc.y
            home_dist = math.sqrt(home_dx * home_dx + home_dy * home_dy)
            if home_dist > 15:
                # Too far from home — head back
                npc.target_x = npc.home_x + random.uniform(-3, 3)
                npc.target_y = npc.home_y + random.uniform(-3, 3)
            else:
                npc.target_x = npc.home_x + math.cos(angle) * d
                npc.target_y = npc.home_y + math.sin(angle) * d

        npc.state = "walking"
        npc.current_action = "moving"
        npc.state_timer = 20.0

    def _start_talk(self, npc: NPC, target_name: str):
        other = self._find_npc(target_name)
        if not other or not other.alive:
            npc.current_action = ""
            return
        d = npc.dist_to(other)
        if d > NPC_CONVERSATION_RANGE:
            npc.target_x, npc.target_y = other.x, other.y
            npc.state = "walking"
            npc.current_action = "moving"
            npc.state_timer = 10.0
            return

        conv = Conversation(npc, other)
        self.conversations.append(conv)
        npc.current_action = "talking"
        other.current_action = "talking"
        npc.state = "socializing"
        other.state = "socializing"
        npc.needs["social"] = min(100, npc.needs["social"] + 15)
        other.needs["social"] = min(100, other.needs["social"] + 10)

        # Generate a contextual conversation topic for the memory
        topic = pick_contextual_topic(
            npc, world=self.world,
            world_effects=getattr(self, 'world_effects', None),
            governance=getattr(self, 'governance', None),
            time_sys=self.time_sys,
            event_log=self.event_log,
            economy=getattr(self, 'economy', None),
        )
        npc.add_memory("social", f"Talked with {other.name}: \"{topic}\"", 2)
        other.add_memory("social", f"Talked with {npc.name}", 2)

        # Share gossip — NPCs exchange world knowledge and event memories
        share_gossip(npc, other, self.event_log,
                     current_day=self.time_sys.day)

        # Relationship boost
        npc.npc_relationships[other.name] = npc.npc_relationships.get(other.name, 0) + 3
        other.npc_relationships[npc.name] = other.npc_relationships.get(npc.name, 0) + 2

    def _start_trade(self, npc: NPC, target_name: str):
        other = self._find_npc(target_name)
        if not other or not other.alive:
            npc.current_action = ""
            return
        # Simple trade: NPC sells food/drink to other if other needs it
        if other.needs["hunger"] < 40 and npc.has_food() and other.npc_gold >= 3:
            for item in list(npc.npc_inventory):
                if item.name in FOOD_ITEMS:
                    npc.npc_remove_item(item.name)
                    other.npc_add_item(make_item(item.name))
                    other.npc_gold -= 3
                    npc.npc_gold += 3
                    npc.add_memory("trade", f"Sold {item.name} to {other.name}", 2)
                    other.add_memory("trade", f"Bought {item.name} from {npc.name}", 2)
                    self.event_log.append(f"{npc.name} traded {item.name} to {other.name}")
                    break
        npc.current_action = ""
        npc.needs["social"] = min(100, npc.needs["social"] + 8)

    def _start_persuade(self, npc: NPC, target_request: str):
        # Parse "name: request"
        parts = target_request.split(":", 1)
        target_name = parts[0].strip()
        request = parts[1].strip() if len(parts) > 1 else "help me"

        other = self._find_npc(target_name)
        if not other or not other.alive:
            npc.current_action = ""
            return

        # Success chance based on charisma vs intelligence and relationship
        charisma = npc.attributes.get("charisma", 5)
        intel = other.attributes.get("intelligence", 5)
        rel = npc.npc_relationships.get(other.name, 0)
        chance = 0.3 + (charisma - intel) * 0.05 + rel * 0.003
        success = random.random() < max(0.1, min(0.9, chance))

        if success:
            other.current_goal = request
            other.add_memory("persuasion", f"{npc.name} persuaded me to: {request}", 3)
            npc.add_memory("persuasion", f"Convinced {other.name} to {request}", 3)
            self.event_log.append(f"{npc.name} persuaded {other.name} to {request}")
        else:
            npc.add_memory("persuasion", f"Failed to convince {other.name}", 1)
            other.npc_relationships[npc.name] = other.npc_relationships.get(npc.name, 0) - 5
        npc.current_action = ""

    def _start_fight(self, npc: NPC, target_name: str):
        # Find target (NPC or creature) — use spatial grid for creatures
        target = self._find_npc(target_name)
        if not target:
            for c in self.creature_grid.get_nearby(npc.x, npc.y, 10):
                if c.alive and c.kind.lower() == target_name.lower() and npc.dist_to(c) < 10:
                    target = c
                    break
        if not target or not target.alive:
            npc.current_action = ""
            return

        npc.current_action = "fighting"
        npc.combat_target = target
        npc.state = "fighting"
        npc.add_memory("combat", f"Started fighting {target_name}", 3)
        self.event_log.append(f"{npc.name} engages in combat with {target_name}!")

    def _give_item(self, npc: NPC, target_str: str):
        """Give item: 'item_name TO recipient'"""
        parts = target_str.upper().split(" TO ")
        if len(parts) != 2:
            npc.current_action = ""
            return
        item_name = parts[0].strip()
        recipient_name = parts[1].strip()

        # Find matching item (case-insensitive)
        found_item = None
        for item in npc.npc_inventory:
            if item.name.upper() == item_name:
                found_item = item
                break
        if not found_item:
            npc.current_action = ""
            return

        recipient = self._find_npc(recipient_name)
        if recipient and recipient.alive:
            npc.npc_remove_item(found_item.name)
            recipient.npc_add_item(make_item(found_item.name))
            npc.add_memory("give", f"Gave {found_item.name} to {recipient.name}", 2)
            recipient.add_memory("receive", f"Received {found_item.name} from {npc.name}", 2)
            recipient.npc_relationships[npc.name] = recipient.npc_relationships.get(npc.name, 0) + 10
            self.event_log.append(f"{npc.name} gave {found_item.name} to {recipient.name}")
        npc.current_action = ""

    def _find_npc(self, name: str) -> Optional[NPC]:
        name_lower = name.lower().strip()
        for npc in self.world_mgr.npcs:
            if npc.name.lower() == name_lower:
                return npc
        return None

    def _find_zone_for_npc(self, npc: NPC, zone_type: str):
        """Find nearest zone of given type for an NPC."""
        if hasattr(self, 'zones') and self.zones:
            return self.zones.find_zone(zone_type, npc.x, npc.y, 50)
        return None

    # ---- ACTION PROGRESS ----

    def _update_action_progress(self, npcs: List[NPC], dt: float, player: Player):
        active_set = self._active_npc_set
        for npc in npcs:
            if not npc.alive:
                continue
            # Skip dormant NPCs
            if active_set is not None and npc.name not in active_set:
                continue
            npc.npc_attack_timer = max(0, npc.npc_attack_timer - dt)

            # Seeking water: if next to water, drink directly
            if npc.current_action == "seeking_water":
                wx = self.world.find_water_near(int(npc.x), int(npc.y), 2)
                if wx:
                    npc.needs["thirst"] = min(100, npc.needs["thirst"] + 40)
                    npc.add_memory("survival", "Drank from a water source", 1)
                    npc.current_action = ""
                    npc.state = "idle"

            # Approaching player
            if npc.current_action == "approaching_player":
                if hasattr(self, '_player_ref'):
                    dist = npc.dist_to(self._player_ref)
                    if dist < NPC_CONVERSATION_RANGE:
                        npc.wants_to_talk = True
                        npc.talk_reason = getattr(npc, 'approach_reason', 'wants to speak with you')
                        npc.current_action = ""
                        npc.state = "idle"
                    elif dist < 12:
                        # Keep moving toward player
                        npc.target_x = self._player_ref.x
                        npc.target_y = self._player_ref.y

            # Party members follow their leader — use spatial grid
            if getattr(npc, 'party_id', None) and getattr(npc, 'party_role', '') == "member":
                for other in self.npc_grid.get_nearby(npc.x, npc.y, 20):
                    if (getattr(other, 'party_id', None) == npc.party_id and
                        getattr(other, 'party_role', '') == "leader" and other.alive):
                        if npc.dist_to(other) > 3.0 and npc.current_action not in ("fighting", "sleeping"):
                            npc.target_x = other.x + random.uniform(-1, 1)
                            npc.target_y = other.y + random.uniform(-1, 1)
                            npc.state = "walking"
                        break

            if npc.action_timer > 0 and npc.current_action in (
                "chopping", "mining", "building", "farming", "fishing", "foraging", "sleeping",
                "training", "performing", "researching", "praying", "ritual",
                "enchanting", "crafting_pottery", "crafting_glass", "tanning", "dyeing",
                "training_animal", "smithing", "hunting", "guarding",
            ):
                # Only tick down when near the target
                at_target = True
                if npc.target_x is not None:
                    dist = npc.dist_to_pos(npc.target_x, npc.target_y)
                    if dist > 2.0:
                        at_target = False

                if at_target:
                    npc.action_timer -= dt
                    npc.action_progress = max(0, 1.0 - npc.action_timer / 8.0)

                if npc.action_timer <= 0:
                    self._complete_action(npc)

    def _update_player_tasks(self, npcs: List[NPC], dt: float):
        """Progress NPCs working on player-assigned tasks."""
        for npc in npcs:
            if not npc.alive:
                continue
            task = getattr(npc, 'player_task', None)
            if not task:
                continue
            if task.get("progress", 0) >= task.get("target_count", 1):
                # Task already done — NPC approaches player to report
                if not npc.wants_to_talk and npc.current_action != "approaching_player":
                    npc.wants_to_talk = True
                    npc.talk_reason = f"I've finished the task you gave me!"
                continue

            # Advance timer
            npc.player_task_timer = getattr(npc, 'player_task_timer', 0) + dt
            kind = task.get("kind", "")

            # Each task type progresses at different rates
            if kind == "kill":
                # NPC hunts nearby creatures every ~15 seconds of work
                if npc.player_task_timer > 15.0:
                    npc.player_task_timer = 0.0
                    # Check for nearby creatures to fight
                    for c in self.creature_grid.get_nearby(npc.x, npc.y, 15):
                        if c.alive:
                            npc.combat_target = c
                            npc.current_action = "fighting"
                            npc.state = "fighting"
                            task["progress"] = task.get("progress", 0) + 1
                            npc.add_memory("combat",
                                f"Killed a {c.kind} on the player's orders", 2)
                            c.hp = 0
                            c.alive = False
                            self.event_log.append(
                                f"{npc.name} killed a {c.kind} (player task {task['progress']}/{task['target_count']})")
                            break

            elif kind == "fetch":
                # NPC gathers items every ~10 seconds of work
                if npc.player_task_timer > 10.0:
                    npc.player_task_timer = 0.0
                    task["progress"] = task.get("progress", 0) + 1
                    # Generate an item
                    gather = random.choice(["Herbs", "Wood", "Stone", "Apple", "Bread", "Mushrooms"])
                    npc.npc_add_item(make_item(gather))
                    npc.add_memory("work",
                        f"Gathered {gather} for the player ({task['progress']}/{task['target_count']})", 1)

            elif kind == "scout":
                # Scouting takes ~20 seconds total
                if npc.player_task_timer > 20.0:
                    npc.player_task_timer = 0.0
                    task["progress"] = 1
                    # Learn something new from scouting
                    structure = self.world.get_structure_at(npc.x, npc.y)
                    loc = structure.name if structure else "the wilderness"
                    info = random.choice([
                        f"Scouted area near {loc}: seems safe",
                        f"Noticed creature tracks near {loc}",
                        f"Found a possible camp site near {loc}",
                        f"Area near {loc} has good foraging",
                        f"Spotted movement in the trees near {loc}",
                    ])
                    npc.known_info.append(info)
                    npc.add_memory("work", f"Completed scouting: {info}", 2)

            elif kind == "guard":
                # Guarding takes ~30 seconds, auto-complete
                if npc.player_task_timer > 30.0:
                    task["progress"] = 1
                    npc.add_memory("work", "Completed guard duty for the player", 2)
                else:
                    # While guarding, fight any nearby creatures
                    for c in self.creature_grid.get_nearby(npc.x, npc.y, 8):
                        if c.alive:
                            npc.combat_target = c
                            npc.current_action = "fighting"
                            npc.state = "fighting"
                            break

            elif kind == "deliver":
                # Delivery takes ~20 seconds
                if npc.player_task_timer > 20.0:
                    task["progress"] = 1
                    npc.add_memory("work", "Completed delivery for the player", 2)

    def _complete_action(self, npc: NPC):
        """Complete a timed action and gain skill XP."""
        from game.systems.skills import gain_skill_xp
        action = npc.current_action

        # Gain skill XP from completing work
        skill_map = {
            "chopping": "woodcraft", "mining": "mining", "building": "masonry",
            "farming": "farming", "fishing": "fishing", "foraging": "herbalism",
            "smithing": "smithing", "hunting": "tracking", "guarding": "swordsmanship",
        }
        if action in skill_map:
            gain_skill_xp(npc, skill_map[action], 1.0)

        if action == "chopping":
            from game.systems.skills import skill_check
            target = npc.action_target
            if target:
                tx, ty = target
                self.world.modify_tile(tx, ty, TREE_STUMP)
                success, total, natural = skill_check(npc, "woodcraft", 8)
                base_count = random.randint(1, 3)
                bonus = 1 if success else 0
                wood = make_item("Wood")
                wood.count = base_count + bonus
                npc.npc_add_item(wood)
                npc.add_memory("work", f"Chopped a tree, got {wood.count} wood", 1)
                npc.daily_builds += 1
                gain_skill_xp(npc, "woodcraft", 1.0)

        elif action == "mining":
            from game.systems.skills import skill_check
            target = npc.action_target
            if target:
                success, total, natural = skill_check(npc, "mining", 10)
                ore_chance = 0.4 + (0.1 if success else 0)
                if random.random() < ore_chance:
                    ore = make_item("Iron Ore")
                    npc.npc_add_item(ore)
                    npc.add_memory("work", "Mined iron ore", 1)
                else:
                    stone = make_item("Stone")
                    stone.count = random.randint(1, 2) + (1 if success else 0)
                    npc.npc_add_item(stone)
                    npc.add_memory("work", f"Mined {stone.count} stone", 1)
                gain_skill_xp(npc, "mining", 1.0)

        elif action == "building":
            if npc.action_target and npc.daily_builds < 10:
                what, tile_type = npc.action_target
                bx, by = int(npc.x), int(npc.y)
                # Find adjacent empty spot
                for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                    nx, ny = bx + dx, by + dy
                    if self.world.is_walkable(nx, ny) and self.world.tiles[ny][nx] == GRASS:
                        if what == "wall" and npc.npc_count_item("Stone") >= 2:
                            self.world.modify_tile(nx, ny, tile_type)
                            npc.npc_remove_item("Stone", 2)
                            npc.add_memory("build", f"Built a stone wall", 2)
                            npc.daily_builds += 1
                        elif what == "floor" and npc.npc_count_item("Wood") >= 2:
                            self.world.modify_tile(nx, ny, tile_type)
                            npc.npc_remove_item("Wood", 2)
                            npc.add_memory("build", f"Built a wooden floor", 2)
                            npc.daily_builds += 1
                        break

        elif action == "farming":
            sub = npc.action_target
            if sub == "plant":
                tx, ty = int(npc.x), int(npc.y)
                if self.world.tiles[ty][tx] == GRASS and npc.npc_has_item("Seeds"):
                    self.world.modify_tile(tx, ty, TILLED_SOIL)
                    npc.npc_remove_item("Seeds")
                    npc.add_memory("work", "Planted seeds", 1)
            elif sub == "harvest":
                tx, ty = int(npc.x), int(npc.y)
                if self.world.tiles[ty][tx] in (FARMLAND, TILLED_SOIL):
                    food = make_item(random.choice(["Bread", "Apple"]))
                    food.count = random.randint(1, 3)
                    npc.npc_add_item(food)
                    npc.add_memory("work", f"Harvested {food.count} {food.name}", 1)
                    if self.world.tiles[ty][tx] == TILLED_SOIL:
                        self.world.modify_tile(tx, ty, FARMLAND)

        elif action == "fishing":
            from game.systems.skills import skill_check
            if npc.npc_has_item("Fishing Rod"):
                success, total, natural = skill_check(npc, "fishing", 10)
                catch_chance = 0.7 + (0.15 if success else 0)
                if random.random() < catch_chance:
                    fish = make_item("Fish")
                    fish.count = 1 + (1 if success and natural >= 18 else 0)
                    npc.npc_add_item(fish)
                    npc.add_memory("work", f"Caught {fish.count} fish", 1)
                gain_skill_xp(npc, "fishing", 1.0)

        elif action == "foraging":
            # Forage in forest for food/herbs/water
            tile = self.world.tiles[int(npc.y)][int(npc.x)] if \
                0 <= int(npc.x) < self.world.width and 0 <= int(npc.y) < self.world.height else GRASS
            if tile in (FOREST, DENSE_FOREST):
                roll = random.random()
                if roll < 0.4:
                    food = make_item(random.choice(["Apple", "Herbs"]))
                    npc.npc_add_item(food)
                    npc.add_memory("forage", f"Found {food.name} in the forest", 1)
                elif roll < 0.6:
                    water = make_item("Water Flask")
                    npc.npc_add_item(water)
                    npc.add_memory("forage", "Found fresh water", 1)

        elif action == "sleeping":
            pass  # Rest recovery handled in _decay_needs

        elif action == "smithing":
            from game.systems.skills import skill_check
            success, total, natural = skill_check(npc, "smithing", 11)
            gain_skill_xp(npc, "smithing", 2.0 if success else 0.8)
            if success:
                product = random.choice(["Iron Sword", "Iron Armor", "Steel Sword"])
                item = make_item(product)
                if item:
                    npc.npc_add_item(item)
                npc.add_memory("work", f"Forged a {product}", 2)
                # Deposit to settlement stores
                if hasattr(self, 'world_effects'):
                    _loc = self.world.get_structure_at(npc.x, npc.y)
                    if _loc:
                        _st = self.world_effects.get_stores_ref(_loc.name)
                        _st["weapons"] = _st.get("weapons", 0) + 1
                        _st["tools"] = _st.get("tools", 0) + 0.5
            else:
                npc.add_memory("work", "Failed to forge a quality piece", 1)

        elif action == "guarding":
            gain_skill_xp(npc, "swordsmanship", 0.3)
            gain_skill_xp(npc, "navigation", 0.2)
            npc.add_memory("duty", "Completed a patrol shift", 1)

        elif action == "hunting":
            gain_skill_xp(npc, "tracking", 1.0)
            gain_skill_xp(npc, "archery", 0.5)
            npc.add_memory("work", "Returned from a hunt", 1)

        # ---- NEW SKILL-BASED ACTION COMPLETIONS ----

        elif action == "training":
            from game.systems.skills import skill_check
            combat_skill = npc.action_target or "swordsmanship"
            dc = 8 + npc.npc_skills.get(combat_skill, 0)
            success, total, natural = skill_check(npc, combat_skill, dc)
            gain_skill_xp(npc, combat_skill, 2.5 if success else 1.0)
            npc.add_memory("training", f"Trained {combat_skill} {'successfully' if success else 'with difficulty'}", 1)

        elif action == "performing":
            from game.systems.skills import skill_check
            success, total, natural = skill_check(npc, "performance", 10)
            gain_skill_xp(npc, "performance", 2.5 if success else 1.0)
            if success:
                # Earn gold from audience — collect tips from nearby NPCs
                base_earnings = random.randint(2, 5) + npc.npc_skills.get("performance", 0)
                actual_earnings = 0
                # Try to collect from nearby NPCs (audience)
                nearby = self.npc_grid.get_nearby(npc.x, npc.y, 8) if hasattr(self, 'npc_grid') else []
                for audience_npc in nearby:
                    if audience_npc is npc or not audience_npc.alive:
                        continue
                    tip = min(1, getattr(audience_npc, 'npc_gold', 0))
                    if tip > 0 and actual_earnings < base_earnings:
                        audience_npc.npc_gold -= tip
                        actual_earnings += tip
                # If few audience NPCs, supplement from settlement stores
                if actual_earnings < base_earnings and hasattr(self, 'world_effects'):
                    _loc = self.world.get_structure_at(npc.x, npc.y)
                    if _loc:
                        _st = self.world_effects.get_stores_ref(_loc.name)
                        supplement = min(base_earnings - actual_earnings,
                                        _st.get("gold", 0))
                        if supplement > 0:
                            _st["gold"] -= supplement
                            actual_earnings += supplement
                if actual_earnings > 0:
                    npc.npc_gold += actual_earnings
                    npc.add_memory("work", f"Performed and earned {actual_earnings} gold", 2)
                else:
                    npc.add_memory("work", "Performed but the crowd was too poor to tip", 1)
                npc.needs["social"] = min(100, npc.needs.get("social", 50) + 15)
                gain_skill_xp(npc, "persuasion", 0.5)
            else:
                npc.add_memory("work", "Performance fell flat", 1)

        elif action == "researching":
            from game.systems.skills import skill_check
            research_skill = npc.action_target or "arcana"
            success, total, natural = skill_check(npc, research_skill, 12)
            gain_skill_xp(npc, research_skill, 2.5 if success else 1.0)
            gain_skill_xp(npc, "literacy", 0.5)
            if success:
                topics = {
                    "arcana": ["a new spell formula", "ancient magical theory", "planar mechanics"],
                    "history": ["a forgotten kingdom", "an ancient battle", "a lost trade route"],
                    "religion": ["a divine prophecy", "a sacred ritual", "the nature of the gods"],
                }
                discovery = random.choice(topics.get(research_skill, ["something interesting"]))
                npc.add_memory("research", f"Researched and discovered {discovery}", 3)
                npc.known_info.append(f"Discovered {discovery} through research")

        elif action == "praying":
            from game.systems.skills import skill_check
            success, total, natural = skill_check(npc, "religion", 8)
            gain_skill_xp(npc, "religion", 2.0 if success else 0.5)
            if success:
                npc.needs["social"] = min(100, npc.needs.get("social", 50) + 10)
                deity = getattr(npc, 'deity', 'the gods')
                npc.add_memory("spiritual", f"Felt the presence of {deity} during prayer", 2)
                # Small chance of healing
                if random.random() < 0.3 and npc.hp < npc.max_hp:
                    npc.heal(5 + npc.npc_skills.get("religion", 0))

        elif action == "ritual":
            from game.systems.skills import skill_check
            success, total, natural = skill_check(npc, "ritual_magic", 15)
            gain_skill_xp(npc, "ritual_magic", 2.0 if success else 0.5)
            if success:
                # Powerful magical effect
                effects = ["warded the area against evil", "glimpsed the future",
                           "strengthened the local ley lines", "communed with nature spirits"]
                effect = random.choice(effects)
                npc.add_memory("magic", f"Completed a ritual: {effect}", 4)
                self.event_log.append(f"{npc.name} completed a magical ritual near ({int(npc.x)},{int(npc.y)})")
                gain_skill_xp(npc, "spellcraft", 1.0)
            else:
                npc.add_memory("magic", "Ritual failed - the magic dissipated", 2)

        elif action == "enchanting":
            from game.systems.skills import skill_check
            success, total, natural = skill_check(npc, "enchanting", 16)
            gain_skill_xp(npc, "enchanting", 2.0 if success else 0.5)
            if success:
                # Find a weapon or armor in inventory to enchant
                for item in npc.npc_inventory:
                    if item.kind == "weapon" and "Enchanted" not in item.name:
                        item.damage += 5
                        item.name = f"Enchanted {item.name}"
                        item.value *= 2
                        npc.add_memory("craft", f"Enchanted {item.name}", 4)
                        break
                else:
                    npc.add_memory("craft", "Practiced enchanting techniques", 1)
            else:
                npc.add_memory("craft", "Enchantment attempt fizzled", 1)

        elif action == "crafting_pottery":
            from game.systems.skills import skill_check
            if npc.npc_count_item("Clay") >= 2:
                success, total, natural = skill_check(npc, "pottery", 10)
                npc.npc_remove_item("Clay", 2)
                gain_skill_xp(npc, "pottery", 1.5 if success else 0.5)
                if success:
                    product = random.choice(["Pottery Jar", "Vase", "Pot"])
                    npc.npc_add_item(make_item(product))
                    npc.add_memory("craft", f"Made a {product}", 2)
                else:
                    npc.add_memory("craft", "Pottery cracked in the kiln", 1)

        elif action == "crafting_glass":
            from game.systems.skills import skill_check
            if npc.npc_count_item("Sand") >= 2:
                success, total, natural = skill_check(npc, "glassblowing", 12)
                npc.npc_remove_item("Sand", 2)
                gain_skill_xp(npc, "glassblowing", 1.5 if success else 0.5)
                if success:
                    product = random.choice(["Glass Pane", "Bottle"])
                    npc.npc_add_item(make_item(product))
                    npc.add_memory("craft", f"Made {product}", 2)
                else:
                    npc.add_memory("craft", "Glass shattered during blowing", 1)

        elif action == "tanning":
            from game.systems.skills import skill_check
            if npc.npc_has_item("Wolf Pelt"):
                success, total, natural = skill_check(npc, "tanning", 10)
                npc.npc_remove_item("Wolf Pelt")
                gain_skill_xp(npc, "tanning", 1.5 if success else 0.5)
                if success:
                    npc.npc_add_item(make_item("Tanned Hide"))
                    npc.add_memory("craft", "Tanned a hide into leather", 2)
                else:
                    npc.add_memory("craft", "Hide was ruined during tanning", 1)

        elif action == "dyeing":
            from game.systems.skills import skill_check
            if npc.npc_has_item("Linen") and npc.npc_has_item("Flowers"):
                success, total, natural = skill_check(npc, "dyeing", 10)
                npc.npc_remove_item("Linen")
                npc.npc_remove_item("Flowers")
                gain_skill_xp(npc, "dyeing", 1.5 if success else 0.5)
                if success:
                    npc.npc_add_item(make_item("Dyed Cloth"))
                    npc.add_memory("craft", "Dyed cloth with beautiful colors", 2)
                else:
                    npc.add_memory("craft", "Dye didn't set properly", 1)

        elif action == "training_animal":
            from game.systems.skills import skill_check
            success, total, natural = skill_check(npc, "animal_training", 13)
            gain_skill_xp(npc, "animal_training", 1.5 if success else 0.5)
            if success:
                npc.add_memory("work", "Trained an animal successfully", 2)
                gain_skill_xp(npc, "animal_care", 0.5)
            else:
                npc.add_memory("work", "Animal was stubborn today", 1)

        npc.current_action = ""
        npc.action_target = None
        npc.action_timer = 0
        npc.action_progress = 0
        npc.state = "idle"
        # Reset decision timer so NPC quickly picks next action
        npc.llm_decision_timer = random.uniform(0.5, 2.0)

    # ---- NPC COMBAT ----

    def _npc_combat_tick(self, npcs: List[NPC], dt: float):
        active_set = self._active_npc_set
        for npc in npcs:
            if not npc.alive or npc.current_action != "fighting":
                continue
            # Skip dormant NPCs
            if active_set is not None and npc.name not in active_set:
                continue
            target = npc.combat_target
            if not target or not target.alive:
                npc.current_action = ""
                npc.combat_target = None
                continue

            dist = npc.dist_to(target)
            if dist > 1.5:
                # Move toward target
                npc.target_x = target.x
                npc.target_y = target.y
                npc.state = "walking"
            elif npc.npc_attack_timer <= 0:
                # Attack (with wound infection check)
                dmg = max(1, npc.npc_attack_damage - getattr(target, 'npc_defense', 0))
                if isinstance(target, NPC) and hasattr(self, 'health'):
                    self.health.on_combat_damage(target, dmg)

                # Self-sacrifice: a loved one may intercept the blow
                actual_target = target
                if isinstance(target, NPC) and hasattr(self, 'social_dynamics'):
                    _grid = self.npc_grid if hasattr(self, 'npc_grid') else None
                    protector = self.social_dynamics.check_self_sacrifice(
                        target, npc, npcs, _grid)
                    if protector is not None:
                        actual_target = protector
                        self.event_log.append(
                            f"{protector.name} leaps in to protect "
                            f"beloved {target.name}!")

                # Use body damage system if available
                if getattr(actual_target, 'body', None) is not None and hasattr(self, 'body_damage'):
                    self.body_damage.apply_damage(actual_target, dmg,
                                                  damage_type="slash",
                                                  timestamp=self.time_sys.time)
                else:
                    actual_target.take_damage(dmg)
                npc.npc_attack_timer = 1.0

                # Trigger attack emotion on the target
                if isinstance(actual_target, NPC):
                    from game.systems.emotions import trigger_emotion
                    trigger_emotion(actual_target, "attacked", intensity=0.8,
                                    target=npc.name,
                                    cause=f"attacked by {npc.name}",
                                    game_time=self.time_sys.time)

                if not target.alive:
                    target_name = getattr(target, 'name', getattr(target, 'kind', '?'))
                    npc.add_memory("combat", f"Defeated {target_name}", 4)
                    npc.current_action = ""
                    npc.combat_target = None

                    # Emotion: winner feels triumph, nearby NPCs feel fear/sadness
                    from game.systems.emotions import trigger_emotion
                    trigger_emotion(npc, "won_fight", intensity=0.8,
                                    target=target_name,
                                    cause=f"defeated {target_name}",
                                    game_time=self.time_sys.time)
                    # Nearby NPCs witness death
                    for other in self.npc_grid.get_nearby(npc.x, npc.y, 10):
                        if other is not npc and other.alive:
                            trigger_emotion(other, "witnessed_death",
                                            intensity=0.6,
                                            target=target_name,
                                            cause=f"saw {target_name} die",
                                            game_time=self.time_sys.time)
                            # Notify mental health system
                            if hasattr(self, 'mental_health'):
                                self.mental_health.on_death_witnessed(other)

                    # Record kill in life ledger
                    from game.systems.memory import ensure_life_ledger
                    ledger = ensure_life_ledger(npc)
                    is_npc = isinstance(target, NPC)
                    ledger.record_kill(target_name, self.time_sys.day, is_npc=is_npc)

                    # If target is NPC, handle death
                    if is_npc:
                        self._handle_npc_death(target)

    # ---- CONVERSATIONS & INFO ----

    def _update_conversations(self, dt: float):
        remaining = []
        for conv in self.conversations:
            conv.timer -= dt
            if conv.timer <= 0:
                # Exchange information
                self._spread_information(conv.npc1, conv.npc2)
                conv.npc1.current_action = ""
                conv.npc2.current_action = ""
                conv.npc1.state = "idle"
                conv.npc2.state = "idle"
            else:
                remaining.append(conv)
        self.conversations = remaining

    def _spread_information(self, npc1: NPC, npc2: NPC):
        """Rich NPC-NPC conversation: exchange info, trade, teach, help, deepen bonds."""
        from game.systems.emotions import trigger_emotion
        friends1 = getattr(npc1, 'friends', [])
        friends2 = getattr(npc2, 'friends', [])
        enemies1 = getattr(npc1, 'enemies', [])
        enemies2 = getattr(npc2, 'enemies', [])
        gt = self.time_sys.time
        rel12 = npc1.npc_relationships.get(npc2.name, 0)
        rel21 = npc2.npc_relationships.get(npc1.name, 0)

        # --- Emotional response to partner ---
        if npc2.name in friends1:
            trigger_emotion(npc1, "saw_friend", intensity=0.5,
                            target=npc2.name, cause=f"talked with friend {npc2.name}",
                            game_time=gt)
        if npc1.name in friends2:
            trigger_emotion(npc2, "saw_friend", intensity=0.5,
                            target=npc1.name, cause=f"talked with friend {npc1.name}",
                            game_time=gt)
        if npc2.name in enemies1:
            trigger_emotion(npc1, "saw_enemy", intensity=0.5,
                            target=npc2.name, cause=f"encountered enemy {npc2.name}",
                            game_time=gt)
        if npc1.name in enemies2:
            trigger_emotion(npc2, "saw_enemy", intensity=0.5,
                            target=npc1.name, cause=f"encountered enemy {npc1.name}",
                            game_time=gt)

        # --- Share known_info (gossip) ---
        for info in npc1.known_info[-5:]:
            if info not in npc2.known_info:
                if random.random() < 0.5 + npc1.attributes.get("charisma", 5) * 0.05:
                    npc2.known_info.append(info)
                    if len(npc2.known_info) > 20:
                        npc2.known_info = npc2.known_info[-20:]
        for info in npc2.known_info[-5:]:
            if info not in npc1.known_info:
                if random.random() < 0.5 + npc2.attributes.get("charisma", 5) * 0.05:
                    npc1.known_info.append(info)
                    if len(npc1.known_info) > 20:
                        npc1.known_info = npc1.known_info[-20:]

        share_gossip(npc1, npc2, self.event_log,
                     current_day=self.time_sys.day)

        # --- Needs-driven help: share food with hungry friend ---
        if rel12 > 10 and npc2.needs.get("hunger", 50) < 30 and npc1.has_food():
            for item in list(npc1.npc_inventory):
                if item.name in FOOD_ITEMS:
                    npc1.npc_remove_item(item.name)
                    npc2.npc_add_item(make_item(item.name))
                    npc2.needs["hunger"] = min(100, npc2.needs["hunger"] + 25)
                    npc1.add_memory("social", f"Gave food to hungry {npc2.name}", 3)
                    npc2.add_memory("social", f"{npc1.name} shared food when I was starving", 4)
                    npc2.npc_relationships[npc1.name] = min(100, rel21 + 8)
                    trigger_emotion(npc2, "gift_received", intensity=0.5,
                                    target=npc1.name, cause=f"{npc1.name} gave me food",
                                    game_time=gt)
                    self.event_log.append(f"{npc1.name} shared food with hungry {npc2.name}")
                    break
        elif rel21 > 10 and npc1.needs.get("hunger", 50) < 30 and npc2.has_food():
            for item in list(npc2.npc_inventory):
                if item.name in FOOD_ITEMS:
                    npc2.npc_remove_item(item.name)
                    npc1.npc_add_item(make_item(item.name))
                    npc1.needs["hunger"] = min(100, npc1.needs["hunger"] + 25)
                    npc2.add_memory("social", f"Gave food to hungry {npc1.name}", 3)
                    npc1.add_memory("social", f"{npc2.name} shared food when I was starving", 4)
                    npc1.npc_relationships[npc2.name] = min(100, rel12 + 8)
                    trigger_emotion(npc1, "gift_received", intensity=0.5,
                                    target=npc2.name, cause=f"{npc2.name} gave me food",
                                    game_time=gt)
                    self.event_log.append(f"{npc2.name} shared food with hungry {npc1.name}")
                    break

        # --- Skill teaching (friends teach each other) ---
        if rel12 > 15 and random.random() < 0.08:
            self._npc_teach(npc1, npc2, gt)
        elif rel21 > 15 and random.random() < 0.08:
            self._npc_teach(npc2, npc1, gt)

        # --- Item trading (barter based on needs) ---
        if random.random() < 0.05:
            self._npc_barter(npc1, npc2, gt)

        # --- Emotional support (comfort sad friends) ---
        es2 = getattr(npc2, 'emotion_state', None)
        es1 = getattr(npc1, 'emotion_state', None)
        if es2 and rel12 > 10:
            sadness = es2.primary.get("sadness", 0) if hasattr(es2, 'primary') else 0
            if sadness > 0.4:
                es2.primary["sadness"] = max(0, sadness - 0.15)
                npc1.add_memory("social", f"Comforted {npc2.name} who was feeling down", 3)
                npc2.add_memory("social", f"{npc1.name} comforted me when I was sad", 4)
                npc2.npc_relationships[npc1.name] = min(100, rel21 + 5)
                npc2.needs["social"] = min(100, npc2.needs.get("social", 50) + 15)
        if es1 and rel21 > 10:
            sadness = es1.primary.get("sadness", 0) if hasattr(es1, 'primary') else 0
            if sadness > 0.4:
                es1.primary["sadness"] = max(0, sadness - 0.15)
                npc2.add_memory("social", f"Comforted {npc1.name} who was feeling down", 3)
                npc1.add_memory("social", f"{npc2.name} comforted me when I was sad", 4)
                npc1.npc_relationships[npc2.name] = min(100, rel12 + 5)
                npc1.needs["social"] = min(100, npc1.needs.get("social", 50) + 15)

        # --- Deep conversation (high relationship builds bonds) ---
        if rel12 > 40 and rel21 > 40 and random.random() < 0.1:
            topic = random.choice([
                "their dreams and fears",
                "life's meaning",
                "their shared experiences",
                "what they want for the future",
                "their families and loved ones",
            ])
            npc1.add_memory("social", f"Had a deep talk with {npc2.name} about {topic}", 4)
            npc2.add_memory("social", f"Had a deep talk with {npc1.name} about {topic}", 4)
            npc1.npc_relationships[npc2.name] = min(100, rel12 + 5)
            npc2.npc_relationships[npc1.name] = min(100, rel21 + 5)
            # Create emotional bond
            if es1 and hasattr(es1, 'bonds'):
                es1.bonds[npc2.name] = {"emotion": "trust",
                    "intensity": min(1.0, es1.bonds.get(npc2.name, {}).get("intensity", 0) + 0.1),
                    "cause": f"deep conversation about {topic}"}
            if es2 and hasattr(es2, 'bonds'):
                es2.bonds[npc1.name] = {"emotion": "trust",
                    "intensity": min(1.0, es2.bonds.get(npc1.name, {}).get("intensity", 0) + 0.1),
                    "cause": f"deep conversation about {topic}"}

        # --- Warning about dangers (share threat knowledge) ---
        dangers = [k for k in npc1.known_info if any(w in k.lower() for w in
                   ["danger", "monster", "bandit", "wolf", "attack", "raid", "killed"])]
        if dangers and rel12 > 5 and random.random() < 0.3:
            warning = random.choice(dangers)
            if warning not in npc2.known_info:
                npc2.known_info.append(warning)
                npc1.add_memory("social", f"Warned {npc2.name} about dangers", 2)
                npc2.add_memory("social", f"{npc1.name} warned me: {warning[:40]}", 3)
                trigger_emotion(npc2, "heard_threat", intensity=0.3,
                                cause=warning[:40], game_time=gt)

    def _npc_teach(self, teacher: NPC, student: NPC, gt: float):
        """Teacher NPC teaches their best skill to student NPC."""
        t_skills = getattr(teacher, 'npc_skills', {})
        s_skills = getattr(student, 'npc_skills', {})
        if not t_skills:
            return
        best = max(t_skills, key=t_skills.get)
        t_level = t_skills[best]
        s_level = s_skills.get(best, 0)
        if t_level <= s_level:
            return
        # Teach
        from game.systems.skills import gain_skill_xp
        gain_skill_xp(student, best, 1.5)
        gain_skill_xp(teacher, "leadership", 0.3)
        teacher.add_memory("teaching", f"Taught {student.name} about {best}", 3)
        student.add_memory("learning", f"{teacher.name} taught me about {best}", 3)
        rel = student.npc_relationships.get(teacher.name, 0)
        student.npc_relationships[teacher.name] = min(100, rel + 5)
        self.event_log.append(f"{teacher.name} taught {student.name} about {best}")

    def _npc_barter(self, npc1: NPC, npc2: NPC, gt: float):
        """NPCs trade items based on their needs and what they have."""
        from game.core.items import make_item
        inv1 = getattr(npc1, 'npc_inventory', [])
        inv2 = getattr(npc2, 'npc_inventory', [])

        # NPC1 needs something NPC2 has
        for item in list(inv2):
            need_match = False
            # Hungry NPC wants food
            if item.name in FOOD_ITEMS and npc1.needs.get("hunger", 50) < 40:
                need_match = True
            # Sick/hurt NPC wants healing items
            elif item.name in ("Health Potion", "Herbs", "Antidote") and npc1.hp < npc1.max_hp * 0.6:
                need_match = True
            # Warrior wants weapons/armor
            elif getattr(item, 'damage', 0) > 0 and getattr(npc1, 'char_class', '') in (
                    "Fighter", "Paladin", "Barbarian", "Ranger"):
                equipped = getattr(npc1, 'weapon', None)
                if not equipped or (hasattr(equipped, 'damage') and item.damage > equipped.damage):
                    need_match = True

            if need_match and npc1.npc_gold >= item.value:
                price = max(1, int(item.value * 0.7))
                if npc1.npc_gold >= price:
                    npc2.npc_remove_item(item.name)
                    npc1.npc_add_item(make_item(item.name))
                    npc1.npc_gold -= price
                    npc2.npc_gold += price
                    npc1.add_memory("trade", f"Bought {item.name} from {npc2.name} for {price}g", 2)
                    npc2.add_memory("trade", f"Sold {item.name} to {npc1.name} for {price}g", 2)
                    self.event_log.append(f"{npc1.name} bought {item.name} from {npc2.name}")
                    if item.name in FOOD_ITEMS:
                        npc1.needs["hunger"] = min(100, npc1.needs["hunger"] + 20)
                    elif getattr(item, 'heal', 0) > 0:
                        npc1.heal(item.heal)
                    return  # one trade per conversation

    # ---- WORLD EVENTS ----

    def _update_events(self, dt: float, npcs: List[NPC], player: Player):
        self.event_timer -= dt

        if self.event_timer <= 0:
            self._spawn_event(npcs)
            self.event_timer = random.uniform(30, 90)

        # Update active events
        remaining = []
        for evt in self.events:
            evt.duration -= dt
            if evt.duration > 0:
                remaining.append(evt)

                # Earthquake: destroy some built structures
                if evt.effects.get("destroy_chance") and evt.duration > 5:
                    for _ in range(2):
                        rx = int(evt.x + random.uniform(-evt.radius, evt.radius))
                        ry = int(evt.y + random.uniform(-evt.radius, evt.radius))
                        if (0 <= rx < self.world.width and 0 <= ry < self.world.height and
                            self.world.tiles[ry][rx] in (BUILT_WALL, BUILT_FLOOR)):
                            if random.random() < evt.effects["destroy_chance"]:
                                self.world.modify_tile(rx, ry, GRASS)
        self.events = remaining

    def _spawn_event(self, npcs: List[NPC]):
        template = random.choice(EVENT_TEMPLATES)
        # Place near a village
        villages = [s for s in self.world.structures if s.kind == "village"]
        if villages:
            v = random.choice(villages)
            x, y = float(v.x), float(v.y)
        else:
            x = random.uniform(20, self.world.width - 20)
            y = random.uniform(20, self.world.height - 20)

        evt = WorldEvent(
            name=template["name"],
            description=template["desc"],
            x=x, y=y,
            radius=template["radius"],
            duration=template["duration"],
            effects=dict(template["effects"]),
        )
        self.events.append(evt)
        self.event_log.append(f"EVENT: {evt.name} - {evt.description}")

        # NPCs who witness it add to known_info
        for npc in npcs:
            if npc.alive and evt.affects(npc):
                npc.known_info.append(f"{evt.name} is happening nearby")
                npc.add_memory("event", evt.description, 3)

    # ---- DAILY LIFE / ECONOMY ----

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

            # Family defense: if family member is fighting, join the fight (spatial grid)
            if hasattr(self, 'demographics'):
                fid = self.demographics.npc_families.get(npc.name)
                if fid and npc.current_action not in ("fighting", "fleeing", "sleeping"):
                    nearby = self.npc_grid.get_nearby(npc.x, npc.y, 15)
                    for other in nearby:
                        if (other.name != npc.name and
                            other.current_action == "fighting" and
                            self.demographics.are_family(npc.name, other.name)):
                            target = getattr(other, 'combat_target', None)
                            if target and getattr(target, 'alive', False):
                                npc.combat_target = target
                                npc.current_action = "fighting"
                                npc.state = "fighting"
                                npc.add_memory("family", f"Rushed to help family member {other.name}!", 4)
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
