"""
Deep NPC simulation — orchestrator.

Split into focused modules (see sim_interface.py for map):
- sim_combat.py: threat response, combat ticking
- sim_needs.py: need decay, sleep, critical needs
- sim_conversations.py: NPC-NPC talking, trading, teaching
- sim_decisions.py: LLM-driven decision making
- sim_actions.py: action execution, progress, completion
- sim_events.py: world events
- sim_daily.py: daily life, death, economy

Each module defines a mixin class that SimulationManager inherits from.
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

# Import mixin classes
from game.systems.sim_combat import SimCombatMixin
from game.systems.sim_needs import SimNeedsMixin
from game.systems.sim_conversations import SimConversationsMixin, Conversation
from game.systems.sim_decisions import SimDecisionsMixin
from game.systems.sim_actions import SimActionsMixin
from game.systems.sim_events import SimEventsMixin, WorldEvent
from game.systems.sim_daily import SimDailyMixin


# ================================
# CONVERSATIONS
# ================================

class Conversation:
    """An active conversation between two NPCs."""
    def __init__(self, npc1: NPC, npc2: NPC):
        self.npc1 = npc1
        self.npc2 = npc2
        self.timer = random.uniform(3.0, 6.0)
        self.started = 0.0  # elapsed game-time; tracked via dt
        self.info_exchanged: List[str] = []


# ================================
# WORLD EVENTS
# ================================

class WorldEvent:
    """A random event affecting the world.
    Duration is tracked in game-time seconds (scaled by time_speed via dt).
    """
    def __init__(self, name: str, description: str, x: float, y: float,
                 radius: float, duration: float, effects: Dict[str, Any],
                 game_day: int = 0):
        self.name = name
        self.description = description
        self.x = x
        self.y = y
        self.radius = radius
        self.duration = duration
        self.effects = effects
        self.started_day = game_day  # game day when event started
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

class SimulationManager(SimCombatMixin, SimNeedsMixin, SimConversationsMixin,
                        SimDecisionsMixin, SimActionsMixin, SimEventsMixin,
                        SimDailyMixin):
    """Orchestrates deep NPC simulation via mixins.

    See sim_interface.py for which methods live in which file.
    """

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

        # Deep ecosystem: creature biological needs, vegetation, ecosystem loops
        from game.systems.creature_needs import CreatureNeedsSystem
        from game.systems.vegetation import VegetationSystem
        from game.systems.ecosystem import EcosystemManager
        self.creature_needs = CreatureNeedsSystem()
        self.vegetation_sys = VegetationSystem()
        self.ecosystem_mgr = EcosystemManager()
        self.creature_needs.set_vegetation(self.vegetation_sys)

        # Crop system (seasonal growth cycles with visual feedback)
        from game.systems.crop_system import CropSystem
        self.crop_system = CropSystem()
        self._crop_last_day = -1

        # Forest regrowth (cleared tiles slowly regenerate)
        from game.systems.forest_regrowth import ForestRegrowthSystem
        self.forest_regrowth = ForestRegrowthSystem()
        self._regrowth_last_day = -1

        # Global Climate Model (pressure systems, temperature, precipitation)
        from game.systems.climate import ClimateModel
        _plan = getattr(world, 'plan', None)
        self.climate = ClimateModel(
            world.width, world.height,
            seed=getattr(world, 'seed', 0),
            world_plan=_plan,
        )
        self._climate_last_day = -1
        self._trade_last_day = -1
        self._construction_last_day = -1

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

        # Dynamic world events (emergent story system — Phase 4)
        from game.systems.dynamic_events import DynamicEventsSystem
        self.dynamic_events = DynamicEventsSystem()

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

        # Kingdom Strategic AI (governance-driven military/economic decisions)
        from game.systems.kingdom_ai import KingdomAI
        self.kingdom_ai = KingdomAI()
        self._kingdom_ai_last_day = -1

        # Mining system (mine establishment, extraction, depletion)
        from game.systems.mining_system import MiningSystem
        self.mining = MiningSystem()
        self.mining.auto_establish_for_mining_settlements(
            world.structures, 0)
        self._mining_last_day = -1

        # Conversation snippet manager (overhear NPC-NPC conversations)
        from game.systems.conversation_snippets import SnippetManager
        self._snippet_manager = SnippetManager()

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
                    # Stabilize dormant NPCs: floor of 20 so off-screen NPCs
                    # never starve. Only active (on-screen) NPCs face real
                    # needs pressure. Well-supplied settlements get even higher.
                    dormant_floor = 20
                    if hasattr(self, 'abstract'):
                        # NPCs in well-supplied settlements get a higher floor
                        for sa in getattr(self.abstract, 'settlements', {}).values():
                            if (abs(npc.home_x - sa.x) < 30
                                    and abs(npc.home_y - sa.y) < 30
                                    and sa.food_supply > 40):
                                dormant_floor = 35
                                break
                    for need in npc.needs:
                        if npc.needs[need] < dormant_floor:
                            npc.needs[need] = dormant_floor
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
        # Intelligent creature approach checks
        nearby_creatures = self.creature_grid.get_nearby(
            player.x, player.y, 10)
        self._check_creature_approaches(nearby_creatures, dt, player)
        self._update_conversations(dt)
        self._snippet_manager.update(dt)
        self._update_events(dt, npcs, player)
        self._npc_combat_tick(npcs, dt)

        # Remove dead NPC entities after 30 seconds
        if self._sim_tick % 30 == 0:
            self._remove_dead_npcs(npcs)

        # Body damage: wound healing, bleeding, infection
        _bd_entities = list(npcs)
        _bd_entities.append(player)
        self.body_damage.update(dt, _bd_entities)

        # Social dynamics — every 5th tick (~6x per second at 30fps)
        if self._sim_tick % 5 == 0:
            self.social.update(dt * 5, npcs, player, npc_grid=self.npc_grid)
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
            _wm = self.world_market if hasattr(self, 'world_market') else None
            _cs = self.construction if hasattr(self, 'construction') else None
            self.governance.update(dt * 10, npcs, self.time_sys.day,
                                   world_market=_wm, construction=_cs)

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
            # Refresh tavern quest boards
            if hasattr(self, '_quest_board_mgr'):
                self._quest_board_mgr.refresh_all(
                    self.time_sys.day, player.level)

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

        # Passive trade (daily road-based gold transfer) — once per game day
        if self.time_sys.day != self._trade_last_day:
            self._trade_last_day = self.time_sys.day
            self.trade.passive_trade(self.world.structures, self.governance)
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

        # Creature biological needs (hunger, thirst) — every tick (lightweight)
        self.creature_needs.update(
            self.world_mgr.creatures, self.world, dt,
            creature_grid=self.creature_grid)

        # Vegetation dynamics (tile recovery) — every tick (round-robin, 50 tiles)
        self.vegetation_sys.update(dt, self.world, self.time_sys)

        # Crop system visual updates — every tick (lightweight round-robin)
        self.crop_system.update_visuals_tick()

        # Crop system daily update — once per game day
        if self.time_sys.day != self._crop_last_day:
            self._crop_last_day = self.time_sys.day
            _we = self.world_effects if hasattr(self, 'world_effects') else None
            self.crop_system.update(
                self.time_sys.day, self.time_sys.season,
                self.world, world_effects=_we)

        # Forest regrowth — once per game day
        if self.time_sys.day != self._regrowth_last_day:
            self._regrowth_last_day = self.time_sys.day
            self.forest_regrowth.update(self.time_sys.day, self.world)

        # Ecosystem feedback loops — internally throttled to ~5 seconds
        _we = self.world_effects if hasattr(self, 'world_effects') else None
        self.ecosystem_mgr.update(
            dt, self.world, self.world_mgr.creatures, npcs,
            self.time_sys, vegetation=self.vegetation_sys,
            creature_grid=self.creature_grid, npc_grid=self.npc_grid,
            world_effects=_we, event_log=self.event_log)

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

        # Dynamic world events (emergent stories) — once per game day
        if hasattr(self, 'dynamic_events') and self.time_sys.day != getattr(self, '_dynamic_events_last_day', -1):
            self._dynamic_events_last_day = self.time_sys.day
            _mil = self.military if hasattr(self, 'military') else None
            self.dynamic_events.update(
                self.time_sys.day, self.governance, self.world, npcs, _mil)
            for msg in self.dynamic_events.get_event_log():
                self.event_log.append(msg)

        # Kingdom Strategic AI — once per game day, after storyteller
        if hasattr(self, 'kingdom_ai') and self.time_sys.day != self._kingdom_ai_last_day:
            self._kingdom_ai_last_day = self.time_sys.day
            self.kingdom_ai.update(
                self.time_sys.day, self.governance, self.military,
                self.construction, self.world.structures, npcs)
            for msg in self.kingdom_ai.get_event_log():
                self.event_log.append(msg)

        # Construction (building projects) — every 10th tick
        if self._sim_tick % 10 == 9:
            self.construction.update(dt * 10, npcs, self.world)
            self.construction.auto_commission(self.governance, self.world, self.world.structures)
            for msg in self.construction.get_log():
                self.event_log.append(msg)

        # Settlement building construction (daily commissioning + progress)
        if self.time_sys.day != self._construction_last_day:
            self._construction_last_day = self.time_sys.day
            self.construction.advance_building_projects(self.world.structures)
            self.construction.auto_commission_buildings(
                self.governance, self.world.structures)
            # Road construction between growing settlements
            _wp = getattr(self.world, 'plan', None)
            self.construction.check_road_construction(
                self.governance, self.world.structures, _wp)
            self.construction.advance_road_projects(self.world, _wp)
            for msg in self.construction.get_log():
                self.event_log.append(msg)

        # Mining system — once per game day, after kingdom AI
        if hasattr(self, 'mining') and self.time_sys.day != self._mining_last_day:
            self._mining_last_day = self.time_sys.day
            _wp = getattr(self.world, 'plan', None)
            self.mining.update(
                self.time_sys.day, self.governance, self.kingdom_ai,
                npcs, self.world.structures, _wp)
            for msg in self.mining.get_event_log():
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


    # All remaining methods are in mixin modules:
    # sim_combat.py, sim_needs.py, sim_conversations.py,
    # sim_decisions.py, sim_actions.py, sim_events.py, sim_daily.py
    # See sim_interface.py for the complete method map.
