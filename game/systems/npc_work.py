"""
NPC Work Behavior System - Makes NPCs physically perform their jobs.

NPCs navigate to profession-appropriate workplaces, perform visible work actions,
carry produced goods back to settlements, and hunters go out to find prey.

This replaces the old "stand in place and set current_action" with actual
purposeful movement: farmers walk to fields, blacksmiths go to forges,
guards patrol walls, hunters track creatures in the wilderness.

Production is material-aware: crafters consume raw materials from settlement
stores and produce finished goods.  If materials are missing the crafter idles
until a gatherer delivers what is needed.
"""

import math
import random
from typing import Optional, Tuple, List, Dict, Any

from game.settings import (
    FARMLAND, WHEAT_FIELD, TILLED_SOIL, ANVIL, FORGE_FIRE, ALTAR,
    BOOKSHELF, FOREST, DENSE_FOREST, GRASS, ROAD, FLOOR, WELL,
    NPC_SPEED, SHALLOW_WATER, WATER, HERB_PATCH, BERRY_BUSH, MUSHROOMS,
    ORE_VEIN, GEM_DEPOSIT, COPPER_VEIN, MOUNTAIN, ROCKY_GROUND,
    TABLE, BARREL, FIREPLACE, CHEST, WALL, BUILT_WALL, STABLE_FLOOR,
    BEEHIVE, CLAY_PIT, FLAX_FIELD, RUBBLE, DIRT_TRACK,
)

from game.data.supply_chains import (
    SUPPLY_CHAINS, RAW_MATERIAL_SOURCES, FOREIGN_TRADE_GOODS,
    PROFESSION_CRAFTS, PROFESSION_GATHERS, GOLD_SOURCES,
)

from game.systems.storage import (
    ensure_npc_home_storage, find_nearest_storage,
    PROFESSION_TOOLS,
)


# ================================================================
# PROFESSION WORKPLACE TILES
# ================================================================

# Maps profession/class to tile types they should work at
PROFESSION_WORKPLACES = {
    # Original / D&D classes
    "Farmer":     [FARMLAND, WHEAT_FIELD, TILLED_SOIL],
    "Fighter":    [ROAD, GRASS],       # patrol routes
    "Guard":      [ROAD, GRASS],       # patrol routes
    "Blacksmith": [ANVIL, FORGE_FIRE],
    "Merchant":   [FLOOR],             # market stall area
    "Cleric":     [ALTAR],
    "Paladin":    [ALTAR],
    "Wizard":     [BOOKSHELF],
    "Sorcerer":   [BOOKSHELF],
    "Warlock":    [BOOKSHELF],
    "Scholar":    [BOOKSHELF],
    "Ranger":     [FOREST, DENSE_FOREST],  # hunting grounds
    "Druid":      [FOREST, DENSE_FOREST],
    "Bard":       [FLOOR],             # tavern/marketplace
    "Innkeeper":  [FLOOR, TABLE, BARREL],
    "Fisher":     [],                   # handled specially (water)
    "Miner":      [ORE_VEIN, COPPER_VEIN, GEM_DEPOSIT],
    "Healer":     [FLOOR, TABLE],
    "Monk":       [ALTAR],
    "Barbarian":  [GRASS, ROAD],       # training area
    "Rogue":      [ROAD, FLOOR],       # prowling

    # === Primary Production ===
    "Fisherman":  [],                   # handled specially (water)
    "Hunter":     [FOREST, DENSE_FOREST],  # hunting grounds
    "Herbalist":  [HERB_PATCH, BERRY_BUSH, MUSHROOMS],
    "Woodcutter": [FOREST, DENSE_FOREST],
    "Shepherd":   [GRASS],              # near livestock
    "Beekeeper":  [BEEHIVE],
    "Prospector": [MOUNTAIN, ROCKY_GROUND],

    # === Crafting/Manufacturing ===
    "Armourer":   [ANVIL, FORGE_FIRE],
    "Carpenter":  [TABLE],
    "Cooper":     [TABLE],
    "Wheelwright":[TABLE],
    "Shipbuilder":[TABLE],              # near water ideally
    "Tanner":     [BARREL],
    "Weaver":     [TABLE],
    "Potter":     [TABLE, CLAY_PIT],
    "Baker":      [FIREPLACE],
    "Brewer":     [BARREL],
    "Alchemist":  [TABLE, BOOKSHELF],
    "Jeweler":    [TABLE],
    "Glassblower":[FORGE_FIRE, TABLE],

    # === Services ===
    "Cook":       [FIREPLACE],
    "Servant":    [FLOOR],
    "Shop Assistant": [CHEST, TABLE],
    "Banker":     [TABLE, CHEST],
    "Barber":     [TABLE],

    # === Administrative/Leadership ===
    "Captain":    [ROAD, GRASS],       # patrol like guards but command
    "Tax Collector": [FLOOR],
    "Steward":    [TABLE, CHEST],
    "Scribe":     [BOOKSHELF, TABLE],
    "Diplomat":   [FLOOR],              # travels between settlements
    "Advisor":    [BOOKSHELF, TABLE],

    # === Skilled/Professional ===
    "Mason":      [WALL, BUILT_WALL, ROCKY_GROUND],
    "Animal Trainer": [STABLE_FLOOR, GRASS],
    "Stablemaster":   [STABLE_FLOOR],
    "Cartographer":   [TABLE, BOOKSHELF],

    # === Construction/Labor ===
    "Builder":    [GRASS, ROAD],        # builds new structures
    "Cleaner":    [FLOOR],
    "Gravedigger":[GRASS],
    "Porter":     [FLOOR, ROAD, GRASS],
    "Laborer":    [ROAD, GRASS, FLOOR, RUBBLE, DIRT_TRACK, TILLED_SOIL],
}

# Work actions displayed per profession when at workplace
PROFESSION_WORK_ACTIONS = {
    # Original / D&D classes
    "Farmer":     "farming",
    "Fighter":    "guarding",
    "Guard":      "guarding",
    "Blacksmith": "smithing",
    "Merchant":   "trading",
    "Cleric":     "praying",
    "Paladin":    "praying",
    "Wizard":     "researching",
    "Sorcerer":   "researching",
    "Warlock":    "researching",
    "Scholar":    "researching",
    "Ranger":     "hunting",
    "Druid":      "foraging",
    "Bard":       "performing",
    "Innkeeper":  "innkeeping",
    "Fisher":     "fishing",
    "Miner":      "mining",
    "Healer":     "healing",
    "Monk":       "praying",
    "Barbarian":  "training",
    "Rogue":      "working",

    # === Primary Production ===
    "Fisherman":  "fishing",
    "Hunter":     "hunting",
    "Herbalist":  "foraging",
    "Woodcutter": "chopping",
    "Shepherd":   "herding",
    "Beekeeper":  "beekeeping",
    "Prospector": "prospecting",

    # === Crafting/Manufacturing ===
    "Armourer":   "smithing",
    "Carpenter":  "carpentry",
    "Cooper":     "coopering",
    "Wheelwright":"carpentry",
    "Shipbuilder":"shipbuilding",
    "Tanner":     "tanning",
    "Weaver":     "weaving",
    "Potter":     "crafting_pottery",
    "Baker":      "baking",
    "Brewer":     "brewing",
    "Alchemist":  "alchemy",
    "Jeweler":    "jeweling",
    "Glassblower":"crafting_glass",

    # === Services ===
    "Cook":       "cooking",
    "Servant":    "cleaning",
    "Shop Assistant": "trading",
    "Banker":     "accounting",
    "Barber":     "barbering",

    # === Administrative/Leadership ===
    "Captain":    "commanding",
    "Tax Collector": "collecting",
    "Steward":    "administering",
    "Scribe":     "writing",
    "Diplomat":   "negotiating",
    "Advisor":    "advising",

    # === Skilled/Professional ===
    "Mason":      "masonry",
    "Animal Trainer": "training_animal",
    "Stablemaster":   "herding",
    "Cartographer":   "mapping",

    # === Construction/Labor ===
    "Builder":    "building",
    "Cleaner":    "cleaning",
    "Gravedigger":"digging",
    "Porter":     "carrying",
    "Laborer":    "working",

    # Laborer sub-tasks (set dynamically by _assign_labourer_task)
    "Laborer:carrier":       "carrying_goods",
    "Laborer:loader":        "loading",
    "Laborer:digger":        "digging",
    "Laborer:rubble_clearer":"clearing_rubble",
    "Laborer:road_builder":  "road_building",
    "Laborer:harvest_helper":"farming",
    "Laborer:general":       "working",
}

# Pre-computed set of all work actions for fast membership testing
_ALL_WORK_ACTIONS = frozenset(PROFESSION_WORK_ACTIONS.values()) | frozenset({
    "carrying", "commuting", "escorting", "collecting",
    "administering", "trading"})

# ================================================================
# PROFESSION PRODUCTION — what each profession produces per work cycle
# ================================================================

# How much food/goods each profession produces per completed work cycle
PROFESSION_PRODUCTION = {
    # Primary Production
    "Farmer":     {"item": "food", "quantity": 3},
    "Fisher":     {"item": "food", "quantity": 2},
    "Fisherman":  {"item": "food", "quantity": 2},
    "Ranger":     {"item": "food", "quantity": 2},  # from hunting
    "Hunter":     {"item": "food", "quantity": 2},
    "Druid":      {"item": "food", "quantity": 1},
    "Herbalist":  {"item": "herbs", "quantity": 2},
    "Woodcutter": {"item": "wood", "quantity": 3},
    "Miner":      {"item": "ore", "quantity": 2},
    "Shepherd":   {"item": "wool", "quantity": 1},
    "Beekeeper":  {"item": "food", "quantity": 1},
    "Prospector": {"item": "ore", "quantity": 1},

    # Crafting — these CONSUME raw materials and PRODUCE finished goods
    "Blacksmith": {"item": "weapons", "quantity": 1},
    "Armourer":   {"item": "armour", "quantity": 1},
    "Carpenter":  {"item": "tools", "quantity": 1},
    "Cooper":     {"item": "tools", "quantity": 1},
    "Wheelwright":{"item": "tools", "quantity": 1},
    "Tanner":     {"item": "leather", "quantity": 1},
    "Weaver":     {"item": "clothing", "quantity": 1},
    "Potter":     {"item": "tools", "quantity": 1},
    "Baker":      {"item": "food", "quantity": 2},
    "Brewer":     {"item": "ale", "quantity": 1},
    "Alchemist":  {"item": "potions", "quantity": 1},
    "Cook":       {"item": "food", "quantity": 2},
    "Shipbuilder":{"item": "tools", "quantity": 1},
    "Jeweler":    {"item": "gold", "quantity": 1},   # sells jewelry
    "Glassblower":{"item": "tools", "quantity": 1},

    # Services that generate gold for the settlement
    "Merchant":   {"item": "gold", "quantity": 2},
    "Innkeeper":  {"item": "gold", "quantity": 1},
    "Barber":     {"item": "gold", "quantity": 1},
    "Banker":     {"item": "gold", "quantity": 2},

    # Administrative — no direct production but keep settlement running
    "Mason":      {"item": "stone", "quantity": 2},

    # Laborers — produce food when helping at farms, or stone when working
    "Laborer":    {"item": "food", "quantity": 1},
    "Porter":     {"item": "food", "quantity": 1},
}

# ================================================================
# RESOURCE CONSUMPTION — what crafters consume to produce goods
# ================================================================

# Maps profession to {input_resource: amount_consumed} per work cycle.
# If the settlement lacks inputs, the crafter produces nothing.
PROFESSION_CONSUMPTION = {
    "Blacksmith":  {"ore": 1},
    "Armourer":    {"ore": 2},
    "Carpenter":   {"wood": 2},
    "Cooper":      {"wood": 1},
    "Wheelwright": {"wood": 2},
    "Shipbuilder": {"wood": 3},
    "Tanner":      {"leather": 0},   # gets hides from hunters directly (free input)
    "Weaver":      {"wool": 1},
    "Potter":      {},                 # clay is effectively free from clay pits
    "Baker":       {"food": 1},        # consumes raw food, produces better food
    "Brewer":      {"food": 1},        # consumes grain → ale
    "Alchemist":   {"herbs": 1},
    "Cook":        {"food": 1},        # consumes raw → produces prepared meals
    "Jeweler":     {"ore": 1},         # consumes gold/gems
    "Glassblower": {},                  # sand is effectively free
}

# Professions that carry goods back to settlement after work
CARRIER_PROFESSIONS = {
    "Farmer", "Fisher", "Fisherman", "Ranger", "Hunter", "Druid", "Miner",
    "Herbalist", "Woodcutter", "Shepherd", "Beekeeper", "Prospector", "Mason",
    "Laborer", "Porter",
}

# Professions that patrol (use patrol state machine)
PATROL_PROFESSIONS = {"Guard", "Fighter", "Paladin", "Barbarian", "Captain"}

# Professions that hunt (use hunting state machine)
HUNTING_PROFESSIONS = {"Ranger", "Hunter"}

# Huntable creature types (passive prey)
HUNTABLE_CREATURES = {"deer", "rabbit", "boar", "elk", "chicken", "cow", "pig", "goat", "sheep"}


# ================================================================
# NPC WORK STATE
# ================================================================

class NpcWorkState:
    """Tracks an NPC's current work behavior state machine."""

    # States
    IDLE = "idle"
    GOING_TO_WORK = "going_to_work"
    WORKING = "working"
    HUNTING_SEEKING = "hunting_seeking"
    HUNTING_CHASING = "hunting_chasing"
    CARRYING_GOODS = "carrying_goods"
    DELIVERING = "delivering"
    PATROLLING = "patrolling"
    # Labourer-specific states
    LABOURER_PICKUP = "labourer_pickup"     # walking to pick up goods
    LABOURER_DELIVER = "labourer_deliver"   # carrying goods to destination
    LABOURER_TASK = "labourer_task"         # performing a labourer task (rubble clearing, road building)
    # Storage-aware states
    FETCHING_MATERIALS = "fetching_materials"  # walking to storage to pick up craft inputs
    DEPOSITING_GOODS = "depositing_goods"      # walking to storage to deposit finished goods
    FETCHING_TOOLS = "fetching_tools"          # going home to pick up work tools

    __slots__ = (
        'state', 'work_target_x', 'work_target_y',
        'work_timer', 'carrying', 'patrol_angle',
        'hunt_target', 'delivery_target_x', 'delivery_target_y',
        '_last_work_check',
        # Goods transport fields
        'carry_capacity', 'delivery_request_id',
        'labourer_task_type',
        # Storage-aware fields
        'storage_target_x', 'storage_target_y',
        'pending_materials',  # materials still needed: {good: qty}
        'has_tools',          # True once the NPC picked up their tools
    )

    def __init__(self):
        self.state = self.IDLE
        self.work_target_x: Optional[float] = None
        self.work_target_y: Optional[float] = None
        self.work_timer: float = 0.0
        self.carrying: Optional[Dict[str, Any]] = None  # {"item": "food", "quantity": 3}
        self.patrol_angle: float = 0.0
        self.hunt_target = None  # reference to creature being hunted
        self.delivery_target_x: Optional[float] = None
        self.delivery_target_y: Optional[float] = None
        self._last_work_check: float = 0.0
        # Goods transport
        self.carry_capacity: int = 5
        self.delivery_request_id: Optional[int] = None
        self.labourer_task_type: Optional[str] = None  # "clearing_rubble", "road_building", etc.
        # Storage-aware navigation
        self.storage_target_x: Optional[float] = None
        self.storage_target_y: Optional[float] = None
        self.pending_materials: Optional[Dict[str, int]] = None
        self.has_tools: bool = False


def _ensure_work_state(npc) -> NpcWorkState:
    """Get or create the work state for an NPC."""
    if not hasattr(npc, '_work_state'):
        npc._work_state = NpcWorkState()
    return npc._work_state


# ================================================================
# MAIN UPDATE - Called from simulation.py
# ================================================================

class NpcWorkSystem:
    """Manages profession-based NPC work behavior."""

    def __init__(self):
        self._work_tick = 0
        self._command_system = None  # set by SimulationManager after construction

    def update(self, dt: float, npcs: list, time_sys, world, world_mgr,
               world_effects=None, zones=None, active_set=None,
               goods_transport=None):
        """Update all NPC work behaviors.

        Called from SimulationManager.update() every tick.
        Only runs during work hours (roughly 7am-5pm).
        """
        self._work_tick += 1
        if self._work_tick % 2 != 0:
            return  # run every other tick for performance
        dt *= 2  # compensate
        self._goods_transport = goods_transport
        self._cached_world_effects = world_effects  # for command execution

        time_norm = getattr(time_sys, 'normalized', 0.5)

        # Work hours: 0.28 (7am) to 0.68 (5pm)
        is_work_time = 0.28 < time_norm < 0.68

        for npc in npcs:
            if not getattr(npc, 'alive', True):
                continue
            # Skip dormant NPCs (far from player)
            if active_set is not None and npc.name not in active_set:
                continue

            ws = _ensure_work_state(npc)

            if not is_work_time:
                # Outside work hours - reset work state
                if ws.state not in (NpcWorkState.IDLE, NpcWorkState.CARRYING_GOODS,
                                    NpcWorkState.DELIVERING):
                    # Let NPCs finish deliveries even after hours
                    if ws.state in (NpcWorkState.CARRYING_GOODS, NpcWorkState.DELIVERING):
                        self._update_delivery(npc, ws, dt, world, world_effects)
                    else:
                        ws.state = NpcWorkState.IDLE
                        ws.work_target_x = None
                        ws.work_target_y = None
                elif ws.state in (NpcWorkState.CARRYING_GOODS, NpcWorkState.DELIVERING):
                    self._update_delivery(npc, ws, dt, world, world_effects)
                continue

            # Skip NPCs doing urgent things (fighting, fleeing, sleeping, etc.)
            if npc.current_action in ("fighting", "fleeing", "sleeping",
                                       "approaching_player", "talking",
                                       "seeking_bed", "seeking_water"):
                ws.state = NpcWorkState.IDLE
                continue

            # Skip NPCs already doing productive schedule-driven work
            # (these are handled by _execute_action + _complete_action)
            if npc.current_action in ("chopping", "building",
                                       "ritual", "enchanting",
                                       "crafting_pottery", "crafting_glass",
                                       "tanning", "dyeing", "training_animal",
                                       "escorting"):
                continue

            # If the work system already has this NPC in a non-idle state,
            # don't let the schedule system override it.
            if ws.state != NpcWorkState.IDLE and npc.current_action in _ALL_WORK_ACTIONS:
                pass  # fall through to state machine update

            # Run the work state machine
            self._update_work(npc, ws, dt, world, world_mgr, world_effects, zones)

    def _update_work(self, npc, ws: NpcWorkState, dt: float, world,
                     world_mgr, world_effects, zones):
        """State machine for NPC work behavior."""
        profession = self._get_work_profession(npc)

        if ws.state == NpcWorkState.IDLE:
            self._start_work(npc, ws, profession, world, world_mgr, zones)

        elif ws.state == NpcWorkState.GOING_TO_WORK:
            self._update_going_to_work(npc, ws, dt, profession, world)

        elif ws.state == NpcWorkState.WORKING:
            self._update_working(npc, ws, dt, profession, world, world_effects)

        elif ws.state == NpcWorkState.HUNTING_SEEKING:
            self._update_hunting_seek(npc, ws, dt, world, world_mgr)

        elif ws.state == NpcWorkState.HUNTING_CHASING:
            self._update_hunting_chase(npc, ws, dt, world, world_mgr)

        elif ws.state == NpcWorkState.CARRYING_GOODS:
            self._update_carrying(npc, ws, dt, world, world_effects)

        elif ws.state == NpcWorkState.DELIVERING:
            self._update_delivery(npc, ws, dt, world, world_effects)

        elif ws.state == NpcWorkState.PATROLLING:
            self._update_patrol(npc, ws, dt, world)

        # Labourer-specific states
        elif ws.state == NpcWorkState.LABOURER_PICKUP:
            self._update_labourer_pickup(npc, ws, dt, world, world_effects)

        elif ws.state == NpcWorkState.LABOURER_DELIVER:
            self._update_labourer_deliver(npc, ws, dt, world, world_effects)

        elif ws.state == NpcWorkState.LABOURER_TASK:
            self._update_labourer_task(npc, ws, dt, world, world_effects)

        # Storage-aware states
        elif ws.state == NpcWorkState.FETCHING_MATERIALS:
            self._update_fetching_materials(npc, ws, dt, world, world_effects)

        elif ws.state == NpcWorkState.DEPOSITING_GOODS:
            self._update_depositing_goods(npc, ws, dt, world, world_effects)

        elif ws.state == NpcWorkState.FETCHING_TOOLS:
            self._update_fetching_tools(npc, ws, dt, world, world_effects)

    def _get_work_profession(self, npc) -> str:
        """Determine the NPC's working profession."""
        # Title overrides: guards patrol regardless of class
        title = getattr(npc, 'title', 'commoner')
        if title in ('guard', 'sergeant'):
            return 'Guard'
        if title in ('captain', 'knight'):
            return 'Captain'

        # Use profession first, fall back to char_class
        profession = getattr(npc, 'profession', '')
        if profession in PROFESSION_WORKPLACES:
            return profession
        char_class = getattr(npc, 'char_class', 'Fighter')
        if char_class in PROFESSION_WORKPLACES:
            return char_class
        return 'Laborer'  # default to general labor

    # ================================================================
    # STATE: Start work
    # ================================================================

    def _start_work(self, npc, ws: NpcWorkState, profession: str,
                    world, world_mgr, zones):
        """Find a workplace and start heading there."""
        # --- Check for hierarchical commands from superiors ---
        cmd_sys = self._command_system
        if cmd_sys is not None:
            cmd = cmd_sys.get_command(npc.name)
            if cmd and cmd.status in ("accepted", "in_progress"):
                from game.systems.commands import CommandSystem
                _we = getattr(world_mgr, '_world_effects_ref', None)
                # Try to resolve world_effects from the simulation layer
                if _we is None:
                    _we = getattr(self, '_cached_world_effects', None)
                handled = CommandSystem.execute_command(
                    npc, cmd, world_effects=_we, world=world)
                if handled:
                    # Command took over -- set a work timer so we re-check
                    ws.state = NpcWorkState.WORKING
                    ws.work_timer = getattr(npc, 'action_timer', 30.0)
                    return
                else:
                    # Command completed instantly (e.g. profession change)
                    cmd_sys.complete_command(npc.name)

        # --- Handle merchant trade deliveries in progress ---
        trade_dest = getattr(npc, '_trade_destination', None)
        trade_goods = getattr(npc, '_trade_goods', None)
        if trade_dest and trade_goods:
            self._continue_merchant_trade(npc, ws, trade_dest, trade_goods,
                                          world, world_mgr)
            return

        # --- Tool fetch: NPC goes home to pick up tools once per day ---
        if not ws.has_tools and profession in PROFESSION_TOOLS:
            ws.state = NpcWorkState.FETCHING_TOOLS
            npc.current_action = "going_home_for_tools"
            return

        # --- Crafters: fetch raw materials from storage before going to work ---
        if profession in PROFESSION_CONSUMPTION:
            we = self._cached_world_effects
            if we and self._try_start_fetching_materials(
                    npc, ws, profession, world, we):
                return

        # Labourers and Porters: assign task based on settlement needs
        if profession in ("Laborer", "Porter"):
            self._assign_labourer_task(npc, ws, profession, world,
                                       world_mgr, zones)
            return

        # Hunters and Rangers go hunting
        if profession in HUNTING_PROFESSIONS and random.random() < 0.6:
            self._start_hunting(npc, ws, world, world_mgr)
            return

        # Guards, Fighters, Captains patrol
        if profession in PATROL_PROFESSIONS:
            self._start_patrol(npc, ws, world)
            return

        # Try to find workplace via zones first (more accurate)
        target = None
        if zones:
            zone_type = self._profession_to_zone(profession)
            if zone_type:
                zone = zones.find_zone(zone_type, npc.x, npc.y, 50)
                if zone:
                    target = zone.center

        # Fall back to tile-based workplace finding
        if target is None:
            workplace_tiles = PROFESSION_WORKPLACES.get(profession, [])
            if workplace_tiles:
                tile_target = world.find_nearest_tile(
                    int(npc.x), int(npc.y), set(workplace_tiles), max_radius=25)
                if tile_target:
                    # For tiles that block movement (ANVIL, FORGE_FIRE, ALTAR, BOOKSHELF),
                    # target an adjacent walkable tile instead
                    tx, ty = tile_target
                    from game.settings import TERRAIN_WALK_COST
                    tile_type = world.tiles[ty][tx]
                    walk_cost = TERRAIN_WALK_COST.get(tile_type, 1.0)
                    if walk_cost >= 999:
                        # Find walkable neighbor
                        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1),
                                       (1, 1), (-1, 1), (1, -1), (-1, -1)]:
                            nx, ny = tx + dx, ty + dy
                            if (0 <= nx < world.width and 0 <= ny < world.height
                                    and world.is_walkable(nx, ny, ignore_buildings=True)):
                                target = (float(nx), float(ny))
                                break
                    else:
                        target = (float(tx), float(ty))

            # Fisher/Fisherman special case: find water
            if target is None and profession in ('Fisher', 'Fisherman'):
                water = world.find_water_near(int(npc.x), int(npc.y), 20)
                if water:
                    target = (float(water[0]), float(water[1]))

        if target is None:
            # Can't find workplace - just work at home area
            ws.state = NpcWorkState.WORKING
            ws.work_timer = random.uniform(15.0, 30.0)
            work_action = PROFESSION_WORK_ACTIONS.get(profession, "working")
            npc.current_action = work_action
            npc.state = "working"
            return

        ws.work_target_x, ws.work_target_y = target
        ws.state = NpcWorkState.GOING_TO_WORK
        npc.target_x = ws.work_target_x
        npc.target_y = ws.work_target_y
        npc.state = "walking"
        npc.current_action = "commuting"

    def _profession_to_zone(self, profession: str) -> Optional[str]:
        """Map profession to zone type."""
        zone_map = {
            "Blacksmith": "smithy",
            "Armourer":   "smithy",
            "Wizard": "library",
            "Scholar": "library",
            "Sorcerer": "library",
            "Warlock": "library",
            "Scribe": "library",
            "Cartographer": "library",
            "Advisor": "library",
            "Cleric": "chapel",
            "Monk": "chapel",
            "Paladin": "chapel",
            "Bard": "tavern",
            "Innkeeper": "tavern",
            "Cook": "tavern",
            "Baker": "tavern",
            "Brewer": "tavern",
            "Barber": "tavern",
            "Healer": "infirmary",
            "Alchemist": "infirmary",
            "Farmer": "farm",
            "Shepherd": "farm",
            "Beekeeper": "farm",
            "Carpenter": "workshop",
            "Cooper": "workshop",
            "Wheelwright": "workshop",
            "Tanner": "tannery",
            "Weaver": "workshop",
            "Potter": "workshop",
            "Stablemaster": "stable",
            "Animal Trainer": "stable",
            "Merchant": "market",
            "Shop Assistant": "market",
            "Banker": "market",
        }
        return zone_map.get(profession)

    # ================================================================
    # STATE: Going to work
    # ================================================================

    def _update_going_to_work(self, npc, ws: NpcWorkState, dt: float,
                               profession: str, world):
        """NPC is walking to workplace. Check if arrived."""
        if ws.work_target_x is None:
            ws.state = NpcWorkState.IDLE
            return

        dx = npc.x - ws.work_target_x
        dy = npc.y - ws.work_target_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 2.0:
            # Arrived at workplace - start working
            ws.state = NpcWorkState.WORKING
            ws.work_timer = random.uniform(20.0, 45.0)  # work for 20-45 seconds
            work_action = PROFESSION_WORK_ACTIONS.get(profession, "working")
            npc.current_action = work_action
            npc.state = "working"
            npc.action_timer = ws.work_timer
            npc.target_x = None
            npc.target_y = None

            # Set action target for farming (used by _complete_action)
            if profession == "Farmer":
                npc.action_target = random.choice(["harvest", "plant"])
                npc.current_action = "farming"
            elif profession in ("Fisher", "Fisherman"):
                npc.current_action = "fishing"
            elif profession == "Miner":
                npc.current_action = "mining"
            elif profession == "Woodcutter":
                npc.current_action = "chopping"
            elif profession == "Herbalist":
                npc.current_action = "foraging"
        else:
            # Keep navigating - make sure movement target is set
            if npc.target_x is None:
                npc.target_x = ws.work_target_x
                npc.target_y = ws.work_target_y
                npc.state = "walking"

    # ================================================================
    # STATE: Working at workplace
    # ================================================================

    def _update_working(self, npc, ws: NpcWorkState, dt: float,
                        profession: str, world, world_effects):
        """NPC is at their workplace performing work.

        For timed actions (farming, mining, smithing, etc.), the existing
        _update_action_progress / _complete_action pipeline in simulation.py
        handles the timer countdown and completion.  When those clear
        npc.current_action to "", we detect it here and transition to
        the goods-carrying phase.

        For non-timed actions (generic 'working', 'trading', 'healing'),
        we manage our own work_timer.
        """
        # Actions whose timer is managed by simulation._update_action_progress
        sim_timed = {"farming", "mining", "fishing", "smithing",
                     "performing", "researching", "praying", "training",
                     "foraging", "guarding", "hunting", "chopping",
                     "building", "crafting_pottery", "tanning",
                     "training_animal"}

        # Command-driven actions (timer-managed but complete the command on finish)
        cmd_actions = {"collecting", "administering", "escorting"}

        if npc.current_action in sim_timed:
            # Still working -- simulation system is ticking the timer
            return

        if npc.current_action in cmd_actions:
            # Command-driven work -- tick our timer
            ws.work_timer -= dt
            if ws.work_timer > 0:
                return
            # Timer expired -- complete the command
            cmd_sys = self._command_system
            if cmd_sys:
                cmd_sys.complete_command(npc.name)
            ws.state = NpcWorkState.IDLE
            npc.current_action = ""
            return

        # If current_action was cleared (completed by sim system) or is idle,
        # the work cycle is done -- transition to production/delivery
        if npc.current_action in ("", "idle"):
            ws.work_timer = 0  # force completion below

        # For non-sim-timed actions, tick our own timer
        ws.work_timer -= dt

        if ws.work_timer <= 0:
            # Work cycle complete - check resource consumption for crafters
            production = PROFESSION_PRODUCTION.get(profession)
            consumption = PROFESSION_CONSUMPTION.get(profession)

            # --- Material-aware crafting (new system) ---
            # If this profession has entries in SUPPLY_CHAINS, try the
            # recipe-based system first — it consumes real ingredients
            # from settlement stores and deposits finished goods.
            settlement = self._get_npc_settlement_name(npc, world)
            if (profession in PROFESSION_CRAFTS and settlement
                    and world_effects):
                crafted = do_crafting_work(npc, world_effects, settlement)
                if crafted:
                    # Successfully produced via supply-chain recipes
                    ws.state = NpcWorkState.IDLE
                    npc.current_action = ""
                    return
                # else: no materials — fall through to legacy check

            # --- Legacy production path (abstract resource categories) ---
            can_produce = True
            if production and consumption and world_effects:
                if settlement:
                    stores = world_effects.get_stores_ref(settlement)
                    # Check if settlement has required inputs
                    for resource, amount in consumption.items():
                        if amount > 0 and stores.get(resource, 0) < amount:
                            can_produce = False
                            break
                    # Consume inputs
                    if can_produce:
                        for resource, amount in consumption.items():
                            if amount > 0:
                                stores[resource] = max(0, stores.get(resource, 0) - amount)

            if not can_produce:
                # No raw materials — crafter idles
                ws.state = NpcWorkState.IDLE
                npc.current_action = "waiting_materials"
                npc.add_memory("work", f"Cannot work — settlement lacks raw materials", 1)
                return

            if production:
                # ANY NPC can carry goods -- universal carrying.
                # Porters/Labourers carry more; others carry what they can.
                from game.systems.commands import _npc_carry_capacity
                gt = getattr(self, '_goods_transport', None)
                if gt:
                    cap = gt.get_carry_capacity(npc)
                else:
                    cap = _npc_carry_capacity(npc)
                base_qty = production["quantity"] + random.randint(0, 1)

                # Apply weather modifier to production output
                try:
                    from game.systems.climate import get_weather_modifier_for_profession
                    _climate_ref = getattr(self, '_climate_ref', None)
                    weather_mult = get_weather_modifier_for_profession(
                        _climate_ref, npc.x, npc.y, profession)
                    base_qty = max(1, int(base_qty * weather_mult))
                except Exception:
                    pass

                qty = min(base_qty, cap)

                # If NPC is at the settlement already (within 5 tiles of home),
                # deposit directly rather than walking.
                dx = npc.x - npc.home_x
                dy = npc.y - npc.home_y
                at_home = math.sqrt(dx * dx + dy * dy) < 5.0

                if at_home:
                    # Deposit directly to settlement stores
                    if settlement and world_effects:
                        stores = world_effects.get_stores_ref(settlement)
                        item = production["item"]
                        stores[item] = stores.get(item, 0) + qty
                    ws.state = NpcWorkState.IDLE
                    npc.current_action = ""
                else:
                    # Carry goods back to settlement
                    ws.carrying = {
                        "item": production["item"],
                        "quantity": qty,
                    }
                    ws.carry_capacity = cap
                    ws.state = NpcWorkState.CARRYING_GOODS
                    npc.current_action = "carrying"
                    self._set_delivery_target(npc, ws, world)
            else:
                # No production - start another cycle
                ws.state = NpcWorkState.IDLE
                npc.current_action = ""

    # ================================================================
    # STATE: Carrying goods back to settlement
    # ================================================================

    def _update_carrying(self, npc, ws: NpcWorkState, dt: float,
                         world, world_effects):
        """NPC is carrying goods back to settlement."""
        if ws.delivery_target_x is None:
            self._set_delivery_target(npc, ws, world)
            if ws.delivery_target_x is None:
                # Can't find delivery point - just deposit
                self._deposit_goods(npc, ws, world, world_effects)
                return

        # Apply carry speed penalty
        gt = getattr(self, '_goods_transport', None)
        if gt:
            npc._carry_speed_mult = gt.get_carry_speed_mult(npc)
        else:
            npc._carry_speed_mult = 0.7

        # Set action based on what's being carried
        if ws.carrying:
            item = ws.carrying.get("item", "")
            _carry_act = {
                "food": "carrying_food", "ore": "carrying_ore",
                "wood": "carrying_wood",
            }
            npc.current_action = _carry_act.get(item, "carrying")

        dx = npc.x - ws.delivery_target_x
        dy = npc.y - ws.delivery_target_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 3.0:
            # Arrived at delivery point
            ws.state = NpcWorkState.DELIVERING
            self._deposit_goods(npc, ws, world, world_effects)
            npc._carry_speed_mult = 1.0
        else:
            # Keep walking
            if npc.target_x is None or npc.state != "walking":
                npc.target_x = ws.delivery_target_x
                npc.target_y = ws.delivery_target_y
                npc.state = "walking"

    def _update_delivery(self, npc, ws: NpcWorkState, dt: float,
                         world, world_effects):
        """NPC is at settlement depositing goods."""
        if ws.carrying:
            self._deposit_goods(npc, ws, world, world_effects)
        ws.state = NpcWorkState.IDLE
        npc.current_action = ""
        ws.delivery_target_x = None
        ws.delivery_target_y = None

    def _deposit_goods(self, npc, ws: NpcWorkState, world, world_effects):
        """Deposit carried goods into the correct physical storage building."""
        if not ws.carrying:
            return

        settlement = self._get_npc_settlement_name(npc, world)
        if settlement and world_effects and hasattr(world_effects, 'get_stores_ref'):
            item = ws.carrying["item"]
            qty = ws.carrying["quantity"]

            # Try physical storage deposit (routes to correct building)
            if hasattr(world_effects, 'get_settlement_storage'):
                storage = world_effects.get_settlement_storage(settlement)
                stored = storage.deposit(item, qty)
                if stored < qty:
                    # Overflow — deposit remainder via fallback
                    remainder = qty - stored
                    stores = world_effects.get_stores_ref(settlement)
                    stores[item] = stores.get(item, 0) + remainder
            else:
                stores = world_effects.get_stores_ref(settlement)
                stores[item] = stores.get(item, 0) + qty

            npc.add_memory("work",
                           f"Delivered {qty} {item} to {settlement}", 1)

            # Deposit any raw material extras (e.g. pelts from hunting)
            raw_deposits = ws.carrying.get("_raw_deposits")
            if raw_deposits:
                for mat_name, mat_qty in raw_deposits.items():
                    if hasattr(world_effects, 'get_settlement_storage'):
                        storage = world_effects.get_settlement_storage(settlement)
                        storage.deposit(mat_name, mat_qty)
                    else:
                        stores = world_effects.get_stores_ref(settlement)
                        stores[mat_name] = stores.get(mat_name, 0) + mat_qty

        # Complete delivery request if this was a transport job
        gt = getattr(self, '_goods_transport', None)
        if gt and ws.delivery_request_id is not None:
            gt.complete_delivery(ws.delivery_request_id)
            ws.delivery_request_id = None

        # Also give NPC some food for their work (payment in kind)
        if ws.carrying["item"] == "food":
            from game.core.items import make_item
            food = make_item(random.choice(["Bread", "Apple"]))
            if food:
                npc.npc_add_item(food)

        npc._carry_speed_mult = 1.0
        ws.carrying = None

    def _set_delivery_target(self, npc, ws: NpcWorkState, world):
        """Find the correct storage building for goods delivery.

        Uses the physical storage system to route NPCs to the right
        building (granary for food, warehouse for materials, etc.).
        Falls back to settlement center if no storage found.
        """
        # Default to home position
        ws.delivery_target_x = npc.home_x
        ws.delivery_target_y = npc.home_y

        # Try to find the correct storage building for what we're carrying
        we = self._cached_world_effects
        if ws.carrying and we and hasattr(we, 'find_storage_location'):
            settlement = self._get_npc_settlement_name(npc, world)
            if settlement:
                item = ws.carrying.get("item", "")
                loc = we.find_storage_location(
                    settlement, item, npc.x, npc.y, need_space=True)
                if loc:
                    ws.delivery_target_x = float(loc.x)
                    ws.delivery_target_y = float(loc.y)
                    return

        # Fallback: try the actual settlement structure center
        struct = world.get_structure_at(npc.home_x, npc.home_y)
        if struct:
            ws.delivery_target_x = float(struct.x)
            ws.delivery_target_y = float(struct.y)

    # ================================================================
    # Storage-aware NPC movement: fetch materials, deposit goods, get tools
    # ================================================================

    def _update_fetching_materials(self, npc, ws: NpcWorkState, dt: float,
                                    world, world_effects):
        """NPC is walking to a storage building to pick up craft inputs."""
        if ws.storage_target_x is None or ws.pending_materials is None:
            ws.state = NpcWorkState.GOING_TO_WORK
            return

        dx = npc.x - ws.storage_target_x
        dy = npc.y - ws.storage_target_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 3.0:
            # Arrived at storage — withdraw materials
            settlement = self._get_npc_settlement_name(npc, world)
            if settlement and world_effects and hasattr(world_effects, 'get_settlement_storage'):
                storage = world_effects.get_settlement_storage(settlement)
                for good, qty in list(ws.pending_materials.items()):
                    actual, _ = storage.withdraw(good, qty)
                    if actual >= qty:
                        del ws.pending_materials[good]
                    elif actual > 0:
                        ws.pending_materials[good] -= actual

            npc.current_action = "carrying_materials"
            # If all materials fetched, go to work
            if not ws.pending_materials:
                ws.pending_materials = None
                ws.storage_target_x = None
                ws.storage_target_y = None
                ws.state = NpcWorkState.GOING_TO_WORK
            else:
                # Still need more materials — find next storage
                self._find_next_material_storage(npc, ws, world, world_effects)
        else:
            # Keep walking
            if npc.target_x is None or npc.state != "walking":
                npc.target_x = ws.storage_target_x
                npc.target_y = ws.storage_target_y
                npc.state = "walking"
            npc.current_action = "going_to_storage"

    def _find_next_material_storage(self, npc, ws: NpcWorkState,
                                     world, world_effects):
        """Find the next storage building that has a needed material."""
        if not ws.pending_materials:
            ws.state = NpcWorkState.GOING_TO_WORK
            return

        settlement = self._get_npc_settlement_name(npc, world)
        if not settlement or not world_effects:
            ws.state = NpcWorkState.GOING_TO_WORK
            return

        if not hasattr(world_effects, 'find_storage_location'):
            ws.state = NpcWorkState.GOING_TO_WORK
            return

        for good in ws.pending_materials:
            loc = world_effects.find_storage_location(
                settlement, good, npc.x, npc.y, need_stock=True)
            if loc:
                ws.storage_target_x = float(loc.x)
                ws.storage_target_y = float(loc.y)
                return

        # No storage has what we need — go to work anyway (will idle)
        ws.pending_materials = None
        ws.storage_target_x = None
        ws.storage_target_y = None
        ws.state = NpcWorkState.GOING_TO_WORK

    def _update_depositing_goods(self, npc, ws: NpcWorkState, dt: float,
                                  world, world_effects):
        """NPC is walking to the correct storage building to deposit goods."""
        if ws.storage_target_x is None:
            # No target set — fall back to normal delivery
            if ws.carrying:
                self._set_delivery_target(npc, ws, world)
                ws.state = NpcWorkState.CARRYING_GOODS
            else:
                ws.state = NpcWorkState.IDLE
            return

        dx = npc.x - ws.storage_target_x
        dy = npc.y - ws.storage_target_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 3.0:
            # Arrived — deposit
            self._deposit_goods(npc, ws, world, world_effects)
            ws.storage_target_x = None
            ws.storage_target_y = None
            ws.state = NpcWorkState.IDLE
            npc.current_action = ""
        else:
            if npc.target_x is None or npc.state != "walking":
                npc.target_x = ws.storage_target_x
                npc.target_y = ws.storage_target_y
                npc.state = "walking"
            npc.current_action = "carrying_to_storage"

    def _update_fetching_tools(self, npc, ws: NpcWorkState, dt: float,
                                world, world_effects):
        """NPC walks home to pick up their work tools before heading to work."""
        home_x = getattr(npc, 'home_x', None)
        home_y = getattr(npc, 'home_y', None)
        if home_x is None or home_y is None:
            ws.has_tools = True
            ws.state = NpcWorkState.IDLE
            return

        dx = npc.x - home_x
        dy = npc.y - home_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 3.0:
            # Arrived home — pick up tools
            hs = ensure_npc_home_storage(npc)
            ws.has_tools = True
            prof = self._get_work_profession(npc)
            tool = PROFESSION_TOOLS.get(prof)
            if tool and tool not in hs.tools:
                hs.add_tool(tool)
            npc.add_memory("work", f"Picked up tools from home", 1)
            ws.state = NpcWorkState.IDLE
            npc.current_action = ""
        else:
            if npc.target_x is None or npc.state != "walking":
                npc.target_x = home_x
                npc.target_y = home_y
                npc.state = "walking"
            npc.current_action = "going_home_for_tools"

    def _try_start_fetching_materials(self, npc, ws: NpcWorkState,
                                       profession: str, world,
                                       world_effects) -> bool:
        """If the crafter needs materials, start walking to get them.

        Returns True if we set up a fetch trip (caller should return).
        Returns False if no fetch needed or no storage system available.
        """
        if not world_effects or not hasattr(world_effects, 'find_storage_location'):
            return False

        consumption = PROFESSION_CONSUMPTION.get(profession)
        if not consumption:
            return False

        settlement = self._get_npc_settlement_name(npc, world)
        if not settlement:
            return False

        # Check what materials are needed
        needed = {}
        for resource, amount in consumption.items():
            if amount > 0:
                needed[resource] = amount

        if not needed:
            return False

        # Find storage for the first needed resource
        for good in needed:
            loc = world_effects.find_storage_location(
                settlement, good, npc.x, npc.y, need_stock=True)
            if loc:
                ws.pending_materials = dict(needed)
                ws.storage_target_x = float(loc.x)
                ws.storage_target_y = float(loc.y)
                ws.state = NpcWorkState.FETCHING_MATERIALS
                npc.current_action = "going_to_storage"
                return True

        return False  # no storage found — fall through to legacy

    # ================================================================
    # Merchant trade delivery (command-driven)
    # ================================================================

    def _continue_merchant_trade(self, npc, ws: NpcWorkState,
                                  trade_dest: str, trade_goods: dict,
                                  world, world_mgr):
        """Merchant is carrying trade goods to another settlement.
        Find the destination structure and walk there; on arrival deposit."""
        # Find destination structure
        target = None
        for struct in world.structures:
            if struct.name == trade_dest:
                target = struct
                break

        if target is None:
            # Can't find destination -- abort trade, return goods to home
            home = self._get_npc_settlement_name(npc, world)
            we = self._cached_world_effects
            if home and we and trade_goods:
                stores = we.get_stores_ref(home)
                for good, qty in trade_goods.items():
                    stores[good] = stores.get(good, 0) + qty
            npc._trade_goods = None
            npc._trade_destination = None
            npc.current_action = ""
            ws.state = NpcWorkState.IDLE
            return

        dx = npc.x - target.x
        dy = npc.y - target.y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 4.0:
            # Arrived -- sell goods through the market price board
            we = self._cached_world_effects
            if we:
                total_revenue = 0
                for good, qty in trade_goods.items():
                    sold = we.market_sell(trade_dest, npc, good, qty)
                    if sold < qty:
                        # Market couldn't buy it all; deposit remainder
                        remainder = qty - sold
                        stores = we.get_stores_ref(trade_dest)
                        stores[good] = stores.get(good, 0) + remainder
                    board = we.get_price_board(trade_dest)
                    total_revenue += sold * board.get_price(good)
                npc.add_memory(
                    "trade",
                    f"Sold goods in {trade_dest} for ~{total_revenue}g", 3)
            npc._trade_goods = None
            npc._trade_destination = None
            npc._trade_sell_price = None
            npc.current_action = ""
            ws.state = NpcWorkState.IDLE
            # Complete the command if there was one
            cmd_sys = self._command_system
            if cmd_sys:
                cmd_sys.complete_command(npc.name)
        else:
            # Keep walking
            npc.target_x = float(target.x)
            npc.target_y = float(target.y)
            npc.state = "walking"
            npc.current_action = "trading"
            # Apply carry speed penalty
            from game.systems.commands import _npc_carry_capacity
            cap = _npc_carry_capacity(npc)
            total_carried = sum(trade_goods.values())
            if total_carried > cap:
                npc._carry_speed_mult = 0.6  # overloaded
            elif total_carried > cap // 2:
                npc._carry_speed_mult = 0.8
            else:
                npc._carry_speed_mult = 0.9
            ws.state = NpcWorkState.GOING_TO_WORK
            ws.work_target_x = float(target.x)
            ws.work_target_y = float(target.y)

    # ================================================================
    # STATE: Patrol (Guards, Fighters)
    # ================================================================

    def _start_patrol(self, npc, ws: NpcWorkState, world):
        """Start a patrol route around settlement perimeter."""
        ws.state = NpcWorkState.PATROLLING
        ws.patrol_angle = random.uniform(0, 2 * math.pi)
        self._set_next_patrol_point(npc, ws, world)
        npc.current_action = "guarding"
        npc.state = "walking"

    def _update_patrol(self, npc, ws: NpcWorkState, dt: float, world):
        """Move along patrol route."""
        if ws.work_target_x is None:
            self._set_next_patrol_point(npc, ws, world)
            return

        dx = npc.x - ws.work_target_x
        dy = npc.y - ws.work_target_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 2.0:
            # Reached patrol point - pause briefly then move to next
            ws.work_timer -= dt
            if ws.work_timer <= 0:
                # Advance patrol angle
                ws.patrol_angle += random.uniform(0.8, 1.5)
                if ws.patrol_angle > 2 * math.pi:
                    ws.patrol_angle -= 2 * math.pi
                self._set_next_patrol_point(npc, ws, world)
        else:
            # Keep walking
            if npc.target_x is None or npc.state != "walking":
                npc.target_x = ws.work_target_x
                npc.target_y = ws.work_target_y
                npc.state = "walking"
                npc.current_action = "guarding"

    def _set_next_patrol_point(self, npc, ws: NpcWorkState, world):
        """Set the next point on the patrol route."""
        # Find home settlement
        home_struct = None
        for s in world.structures:
            if (s.kind in ("village", "town", "city", "castle",
                           "orc_stronghold", "goblin_warren") and
                abs(npc.home_x - s.x) < s.radius + 10 and
                abs(npc.home_y - s.y) < s.radius + 10):
                home_struct = s
                break

        if home_struct:
            r = home_struct.radius
            # Patrol around the perimeter
            px = home_struct.x + math.cos(ws.patrol_angle) * (r - 1)
            py = home_struct.y + math.sin(ws.patrol_angle) * (r - 1)
            ws.work_target_x = float(px)
            ws.work_target_y = float(py)
        else:
            # No settlement found - patrol around home
            px = npc.home_x + math.cos(ws.patrol_angle) * 8
            py = npc.home_y + math.sin(ws.patrol_angle) * 8
            ws.work_target_x = px
            ws.work_target_y = py

        npc.target_x = ws.work_target_x
        npc.target_y = ws.work_target_y
        npc.state = "walking"
        npc.current_action = "guarding"
        ws.work_timer = random.uniform(3.0, 8.0)  # pause at each point

    # ================================================================
    # STATE: Hunting (Rangers)
    # ================================================================

    def _start_hunting(self, npc, ws: NpcWorkState, world, world_mgr):
        """Start hunting - move into wilderness to find prey."""
        ws.state = NpcWorkState.HUNTING_SEEKING
        ws.hunt_target = None

        # Move away from settlement into wilderness
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(15, 30)
        tx = npc.home_x + math.cos(angle) * dist
        ty = npc.home_y + math.sin(angle) * dist

        # Clamp to world bounds
        tx = max(1, min(world.width - 2, tx))
        ty = max(1, min(world.height - 2, ty))

        ws.work_target_x = tx
        ws.work_target_y = ty
        npc.target_x = tx
        npc.target_y = ty
        npc.state = "walking"
        npc.current_action = "hunting"

    def _update_hunting_seek(self, npc, ws: NpcWorkState, dt: float,
                              world, world_mgr):
        """Seeking prey in the wilderness."""
        # Check for nearby passive creatures
        best_creature = None
        best_dist = 20.0  # detection range

        for creature in world_mgr.creatures:
            if not creature.alive:
                continue
            if not getattr(creature, 'passive', False):
                continue
            if creature.kind not in HUNTABLE_CREATURES:
                continue

            d = math.sqrt((npc.x - creature.x) ** 2 + (npc.y - creature.y) ** 2)
            if d < best_dist:
                best_dist = d
                best_creature = creature

        if best_creature:
            # Found prey - chase it
            ws.state = NpcWorkState.HUNTING_CHASING
            ws.hunt_target = best_creature
            npc.target_x = best_creature.x
            npc.target_y = best_creature.y
            npc.state = "walking"
            npc.current_action = "hunting"
            npc.current_gait = "jog"
            return

        # Check if reached search area
        if ws.work_target_x is not None:
            dx = npc.x - ws.work_target_x
            dy = npc.y - ws.work_target_y
            if math.sqrt(dx * dx + dy * dy) < 3.0:
                # Search area reached, try new direction
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(8, 15)
                tx = npc.x + math.cos(angle) * dist
                ty = npc.y + math.sin(angle) * dist
                tx = max(1, min(world.width - 2, tx))
                ty = max(1, min(world.height - 2, ty))
                ws.work_target_x = tx
                ws.work_target_y = ty
                npc.target_x = tx
                npc.target_y = ty

        # Timeout - give up and return with what we have
        ws.work_timer += dt
        if ws.work_timer > 60.0:
            # No prey found - return empty-handed
            ws.state = NpcWorkState.IDLE
            npc.target_x = npc.home_x
            npc.target_y = npc.home_y
            npc.state = "walking"
            npc.current_action = ""
            ws.work_timer = 0.0

    def _update_hunting_chase(self, npc, ws: NpcWorkState, dt: float,
                               world, world_mgr):
        """Chasing prey creature."""
        prey = ws.hunt_target
        if prey is None or not getattr(prey, 'alive', False):
            # Prey is dead or gone
            if prey and not prey.alive:
                # Killed it! Pick up food + raw materials
                ws.carrying = {"item": "food", "quantity": random.randint(2, 4)}
                npc.add_memory("hunting",
                               f"Killed a {prey.kind} while hunting", 2)
                npc.current_action = "carrying"

                # Also pick up raw meat for NPC's own inventory
                from game.core.items import make_item
                meat = make_item("Raw Meat")
                if meat:
                    meat.count = random.randint(1, 2)
                    npc.npc_add_item(meat)

                # Deposit raw hunting materials to settlement stores
                # (pelts from wolves/bears, feathers from birds, etc.)
                prey_kind = getattr(prey, 'kind', '')
                _hunt_deposits = {}
                # All animals yield Raw Meat for the settlement
                _hunt_deposits["Raw Meat"] = random.randint(1, 3)
                # Pelts from furred creatures
                if prey_kind in ("wolf", "dire_wolf", "bear",
                                 "mountain_lion", "fox"):
                    _hunt_deposits["Wolf Pelt"] = 1
                # Feathers from birds
                if prey_kind in ("chicken", "hawk", "eagle",
                                 "crow", "owl"):
                    _hunt_deposits["Feathers"] = random.randint(1, 3)
                # Leather from large animals
                if prey_kind in ("deer", "elk", "boar", "wild_boar",
                                 "cow", "pig"):
                    _hunt_deposits["Wolf Pelt"] = 1  # used as hide
                # Store the deposits for delivery
                ws.carrying["_raw_deposits"] = _hunt_deposits

                # Head back to settlement
                ws.state = NpcWorkState.CARRYING_GOODS
                self._set_delivery_target(npc, ws, world)
                npc.current_gait = "walk"
            else:
                # Lost the prey
                ws.state = NpcWorkState.HUNTING_SEEKING
                ws.hunt_target = None
            return

        # Update chase target position
        d = math.sqrt((npc.x - prey.x) ** 2 + (npc.y - prey.y) ** 2)

        if d < 1.5:
            # In melee range - attack
            npc.combat_target = prey
            npc.current_action = "fighting"
            npc.state = "fighting"
            # Let combat system handle the actual damage
        else:
            # Keep chasing
            npc.target_x = prey.x
            npc.target_y = prey.y
            npc.state = "walking"
            npc.current_action = "hunting"

    # ================================================================
    # LABORER / PORTER — task assignment and execution
    # ================================================================

    def _assign_labourer_task(self, npc, ws: NpcWorkState, profession: str,
                              world, world_mgr, zones):
        """Assign a labourer task based on settlement needs.

        Priority:
        1. Clear rubble (after war/disaster)
        2. Carry goods (pending delivery requests)
        3. Help with construction (dig/prepare tiles)
        4. Road maintenance (repair damaged roads)
        5. Pick up ground items
        6. General labor (default work)
        """
        settlement = self._get_npc_settlement_name(npc, world)
        gt = getattr(self, '_goods_transport', None)

        # --- Priority 1: Clear rubble ---
        rubble_pos = self._find_rubble_near(npc, world)
        if rubble_pos:
            tx, ty = rubble_pos
            ws.state = NpcWorkState.LABOURER_TASK
            ws.labourer_task_type = "clearing_rubble"
            ws.work_target_x = float(tx)
            ws.work_target_y = float(ty)
            ws.work_timer = random.uniform(8.0, 15.0)
            npc.target_x = float(tx)
            npc.target_y = float(ty)
            npc.state = "walking"
            npc.current_action = "clearing_rubble"
            return

        # --- Priority 2: Carry goods (from delivery queue) ---
        if gt and settlement:
            pending = gt.get_pending_deliveries(settlement)
            if pending:
                req = pending[0]
                cap = gt.get_carry_capacity(npc)
                req_assigned = gt.assign_delivery(req.id, npc.name)
                if req_assigned:
                    ws.state = NpcWorkState.LABOURER_PICKUP
                    ws.delivery_request_id = req.id
                    ws.carry_capacity = cap
                    ws.work_target_x = req.from_x
                    ws.work_target_y = req.from_y
                    ws.delivery_target_x = req.to_x
                    ws.delivery_target_y = req.to_y
                    npc.target_x = req.from_x
                    npc.target_y = req.from_y
                    npc.state = "walking"
                    npc.current_action = "commuting"
                    return

        # --- Priority 3: Pick up ground items ---
        if gt:
            nearby_items = gt.find_ground_items_near(npc.x, npc.y, 20.0)
            if nearby_items:
                idx, gitem = nearby_items[0]
                ws.state = NpcWorkState.LABOURER_PICKUP
                ws.work_target_x = gitem.x
                ws.work_target_y = gitem.y
                # We'll pick up at arrival; set delivery to settlement center
                struct = world.get_structure_at(npc.home_x, npc.home_y)
                ws.delivery_target_x = float(struct.x) if struct else npc.home_x
                ws.delivery_target_y = float(struct.y) if struct else npc.home_y
                npc.target_x = gitem.x
                npc.target_y = gitem.y
                npc.state = "walking"
                npc.current_action = "commuting"
                return

        # --- Priority 4: Road building ---
        road_pos = self._find_road_work_near(npc, world)
        if road_pos and random.random() < 0.3:
            tx, ty = road_pos
            ws.state = NpcWorkState.LABOURER_TASK
            ws.labourer_task_type = "road_building"
            ws.work_target_x = float(tx)
            ws.work_target_y = float(ty)
            ws.work_timer = random.uniform(10.0, 20.0)
            npc.target_x = float(tx)
            npc.target_y = float(ty)
            npc.state = "walking"
            npc.current_action = "road_building"
            return

        # --- Priority 5: Help at farms during harvest (seasonal) ---
        # Check nearby farms for harvest help
        farm_pos = self._find_farm_help_near(npc, world)
        if farm_pos and random.random() < 0.4:
            tx, ty = farm_pos
            ws.state = NpcWorkState.GOING_TO_WORK
            ws.work_target_x = float(tx)
            ws.work_target_y = float(ty)
            ws.work_timer = random.uniform(15.0, 30.0)
            npc.target_x = float(tx)
            npc.target_y = float(ty)
            npc.state = "walking"
            npc.current_action = "commuting"
            return

        # --- Default: General labor ---
        # Walk around settlement doing maintenance
        ws.state = NpcWorkState.WORKING
        ws.work_timer = random.uniform(15.0, 30.0)
        npc.current_action = "working"
        npc.state = "working"
        # Wander within settlement
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(3, 10)
        ws.work_target_x = npc.home_x + math.cos(angle) * dist
        ws.work_target_y = npc.home_y + math.sin(angle) * dist

    def _update_labourer_pickup(self, npc, ws: NpcWorkState, dt: float,
                                world, world_effects):
        """Labourer walking to pick up goods for delivery."""
        if ws.work_target_x is None:
            ws.state = NpcWorkState.IDLE
            return

        dx = npc.x - ws.work_target_x
        dy = npc.y - ws.work_target_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 3.0:
            # Arrived at pickup point
            gt = getattr(self, '_goods_transport', None)
            settlement = self._get_npc_settlement_name(npc, world)

            # Try to pick up from delivery request
            if gt and ws.delivery_request_id is not None:
                # Find the request to know what to carry
                for queue in gt.delivery_queues.values():
                    for req in queue:
                        if req.id == ws.delivery_request_id:
                            # Remove goods from settlement stores
                            if settlement and world_effects:
                                stores = world_effects.get_stores_ref(settlement)
                                available = stores.get(req.good, 0)
                                qty = min(req.quantity, available, ws.carry_capacity)
                                if qty > 0:
                                    stores[req.good] = max(0, available - qty)
                                    ws.carrying = {
                                        "item": req.good,
                                        "quantity": qty,
                                    }
                                    # Mark goods as in transit
                                    gt.in_transit[req.id] = {
                                        "good": req.good,
                                        "quantity": qty,
                                        "carrier_name": npc.name,
                                    }
                                else:
                                    # No goods available — cancel
                                    gt.cancel_delivery(ws.delivery_request_id)
                                    ws.delivery_request_id = None
                                    ws.state = NpcWorkState.IDLE
                                    npc.current_action = ""
                                    return
                            break

            # Also check for ground items at this location
            if gt and ws.carrying is None:
                nearby = gt.find_ground_items_near(npc.x, npc.y, 3.0)
                if nearby:
                    idx, gitem = nearby[0]
                    picked = gt.pickup_ground_item(idx)
                    if picked:
                        ws.carrying = {
                            "item": picked.good,
                            "quantity": min(picked.quantity, ws.carry_capacity),
                        }
                        # If we couldn't carry everything, drop remainder
                        leftover = picked.quantity - ws.carry_capacity
                        if leftover > 0:
                            gt.drop_goods(picked.good, leftover,
                                          picked.x, picked.y)

            if ws.carrying:
                # Start delivering
                ws.state = NpcWorkState.LABOURER_DELIVER
                npc.target_x = ws.delivery_target_x
                npc.target_y = ws.delivery_target_y
                npc.state = "walking"
                item = ws.carrying.get("item", "")
                _carry_act = {
                    "food": "carrying_food", "ore": "carrying_ore",
                    "wood": "carrying_wood",
                }
                npc.current_action = _carry_act.get(item, "carrying")
                npc._carry_speed_mult = 0.7
            else:
                # Nothing to pick up
                ws.state = NpcWorkState.IDLE
                npc.current_action = ""
                ws.delivery_request_id = None
        else:
            # Keep walking to pickup point
            if npc.target_x is None or npc.state != "walking":
                npc.target_x = ws.work_target_x
                npc.target_y = ws.work_target_y
                npc.state = "walking"

    def _update_labourer_deliver(self, npc, ws: NpcWorkState, dt: float,
                                 world, world_effects):
        """Labourer carrying goods to delivery destination."""
        if ws.delivery_target_x is None or ws.carrying is None:
            ws.state = NpcWorkState.IDLE
            npc.current_action = ""
            npc._carry_speed_mult = 1.0
            return

        # Apply carry speed
        gt = getattr(self, '_goods_transport', None)
        if gt:
            npc._carry_speed_mult = gt.get_carry_speed_mult(npc)

        dx = npc.x - ws.delivery_target_x
        dy = npc.y - ws.delivery_target_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < 3.0:
            # Deposit goods
            self._deposit_goods(npc, ws, world, world_effects)
            ws.state = NpcWorkState.IDLE
            npc.current_action = ""
            ws.delivery_target_x = None
            ws.delivery_target_y = None
            npc._carry_speed_mult = 1.0
        else:
            if npc.target_x is None or npc.state != "walking":
                npc.target_x = ws.delivery_target_x
                npc.target_y = ws.delivery_target_y
                npc.state = "walking"

    def _update_labourer_task(self, npc, ws: NpcWorkState, dt: float,
                              world, world_effects):
        """Labourer performing a tile-modification task."""
        if ws.work_target_x is None:
            ws.state = NpcWorkState.IDLE
            return

        dx = npc.x - ws.work_target_x
        dy = npc.y - ws.work_target_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist > 2.0:
            # Still walking to work site
            if npc.target_x is None or npc.state != "walking":
                npc.target_x = ws.work_target_x
                npc.target_y = ws.work_target_y
                npc.state = "walking"
            return

        # At work site — tick the timer
        npc.state = "working"
        npc.target_x = None
        npc.target_y = None
        ws.work_timer -= dt

        if ws.work_timer <= 0:
            tx = int(ws.work_target_x)
            ty = int(ws.work_target_y)

            if ws.labourer_task_type == "clearing_rubble":
                # Convert RUBBLE to GRASS
                if (0 <= tx < world.width and 0 <= ty < world.height
                        and world.tiles[ty][tx] == RUBBLE):
                    world.tiles[ty][tx] = GRASS
                    npc.add_memory("work", "Cleared rubble", 1)
                npc.current_action = "clearing_rubble"

            elif ws.labourer_task_type == "road_building":
                # Convert DIRT_TRACK or GRASS on paths to ROAD
                if (0 <= tx < world.width and 0 <= ty < world.height
                        and world.tiles[ty][tx] in (DIRT_TRACK, GRASS)):
                    world.tiles[ty][tx] = ROAD
                    npc.add_memory("work", "Built a section of road", 1)
                    # Consume stone from settlement if available
                    settlement = self._get_npc_settlement_name(npc, world)
                    if settlement and world_effects:
                        stores = world_effects.get_stores_ref(settlement)
                        if stores.get("stone", 0) > 0:
                            stores["stone"] = max(0, stores["stone"] - 1)

            elif ws.labourer_task_type == "digging":
                # Convert GRASS to TILLED_SOIL for farm preparation
                if (0 <= tx < world.width and 0 <= ty < world.height
                        and world.tiles[ty][tx] == GRASS):
                    world.tiles[ty][tx] = TILLED_SOIL
                    npc.add_memory("work", "Prepared soil for farming", 1)

            # Task complete, go idle
            ws.state = NpcWorkState.IDLE
            ws.labourer_task_type = None
            npc.current_action = ""

    def _find_rubble_near(self, npc, world, radius: int = 20) -> Optional[Tuple[int, int]]:
        """Find nearest RUBBLE tile within radius."""
        nx, ny = int(npc.x), int(npc.y)
        best = None
        best_dist = radius * radius + 1
        for dy in range(-radius, radius + 1, 2):  # step 2 for perf
            for dx in range(-radius, radius + 1, 2):
                tx, ty = nx + dx, ny + dy
                if (0 <= tx < world.width and 0 <= ty < world.height
                        and world.tiles[ty][tx] == RUBBLE):
                    d2 = dx * dx + dy * dy
                    if d2 < best_dist:
                        best_dist = d2
                        best = (tx, ty)
        return best

    def _find_road_work_near(self, npc, world, radius: int = 15) -> Optional[Tuple[int, int]]:
        """Find a DIRT_TRACK tile near settlement that could become ROAD."""
        nx, ny = int(npc.x), int(npc.y)
        candidates = []
        for dy in range(-radius, radius + 1, 3):
            for dx in range(-radius, radius + 1, 3):
                tx, ty = nx + dx, ny + dy
                if (0 <= tx < world.width and 0 <= ty < world.height
                        and world.tiles[ty][tx] == DIRT_TRACK):
                    # Check if it's near a road (connecting path)
                    for adj_dx, adj_dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                        ax, ay = tx + adj_dx, ty + adj_dy
                        if (0 <= ax < world.width and 0 <= ay < world.height
                                and world.tiles[ay][ax] == ROAD):
                            candidates.append((tx, ty))
                            break
        if candidates:
            return random.choice(candidates)
        return None

    def _find_farm_help_near(self, npc, world, radius: int = 20) -> Optional[Tuple[int, int]]:
        """Find farmland tile where a harvest helper could work."""
        nx, ny = int(npc.x), int(npc.y)
        farm_tiles = []
        for dy in range(-radius, radius + 1, 3):
            for dx in range(-radius, radius + 1, 3):
                tx, ty = nx + dx, ny + dy
                if (0 <= tx < world.width and 0 <= ty < world.height
                        and world.tiles[ty][tx] in (WHEAT_FIELD, FARMLAND)):
                    farm_tiles.append((tx, ty))
        if farm_tiles:
            return random.choice(farm_tiles)
        return None

    # ================================================================
    # CARRIER DEATH — drop goods on ground
    # ================================================================

    def handle_carrier_death(self, npc, world):
        """Called when an NPC dies while carrying goods.

        Drops carried goods on the ground as GroundItems.
        """
        ws = getattr(npc, '_work_state', None)
        if ws is None or ws.carrying is None:
            return

        gt = getattr(self, '_goods_transport', None)
        if gt:
            gt.drop_goods(
                ws.carrying["item"],
                ws.carrying["quantity"],
                npc.x, npc.y)
            # Cancel any active delivery request
            if ws.delivery_request_id is not None:
                gt.cancel_delivery(ws.delivery_request_id)
                ws.delivery_request_id = None

        ws.carrying = None
        npc._carry_speed_mult = 1.0

    # ================================================================
    # HELPERS
    # ================================================================

    def _get_npc_settlement_name(self, npc, world) -> Optional[str]:
        """Find the settlement an NPC belongs to."""
        home_settlement = getattr(npc, 'home_settlement', None)
        if home_settlement:
            return home_settlement
        faction = getattr(npc, 'faction', None)
        if faction:
            return faction
        if world and hasattr(world, 'get_structure_at'):
            s = world.get_structure_at(npc.home_x, npc.home_y)
            if s:
                return s.name
        return None


# ================================================================
# PROFESSION HIRING / FIRING / PROMOTION
# ================================================================

# Profession promotion paths: {(from_profession, to_profession): {requirements}}
PROFESSION_PROMOTIONS = {
    ("Guard", "Captain"):          {"swordsmanship": 5, "leadership": 3, "level": 5},
    ("Farmer", "Steward"):         {"farming": 5, "literacy": 2, "level": 4},
    ("Merchant", "Banker"):        {"trading": 4, "literacy": 4, "level": 4},
    ("Fisher", "Fisherman"):       {"fishing": 3, "level": 2},
    ("Fisherman", "Shipbuilder"):  {"fishing": 4, "woodcraft": 3, "level": 5},
    ("Laborer", "Builder"):        {"masonry": 2, "level": 2},
    ("Builder", "Mason"):          {"masonry": 4, "level": 4},
    ("Laborer", "Porter"):         {"level": 2},
    ("Servant", "Cook"):           {"cooking": 3, "level": 2},
    ("Cook", "Innkeeper"):         {"cooking": 4, "trading": 2, "level": 4},
    ("Woodcutter", "Carpenter"):   {"woodcraft": 4, "level": 3},
    ("Carpenter", "Wheelwright"):  {"woodcraft": 5, "level": 5},
    ("Miner", "Prospector"):       {"mining": 4, "navigation": 2, "level": 4},
    ("Herbalist", "Alchemist"):    {"herbalism": 4, "alchemy": 2, "literacy": 2, "level": 4},
    ("Healer", "Alchemist"):       {"herbalism": 3, "alchemy": 3, "level": 5},
    ("Shepherd", "Animal Trainer"):{"animal_care": 4, "animal_training": 2, "level": 3},
    ("Scribe", "Advisor"):         {"literacy": 5, "leadership": 2, "level": 5},
    ("Scribe", "Cartographer"):    {"literacy": 4, "cartography": 3, "level": 4},
    ("Shop Assistant", "Merchant"):{"trading": 4, "persuasion": 3, "level": 3},
    ("Cleaner", "Servant"):        {"level": 2},
    ("Porter", "Stablemaster"):    {"animal_care": 3, "level": 3},
    ("Tanner", "Armourer"):        {"leatherwork": 4, "smithing": 2, "level": 4},
    ("Blacksmith", "Jeweler"):     {"smithing": 4, "jeweling": 2, "level": 4},
    ("Potter", "Glassblower"):     {"pottery": 4, "level": 4},
}

# Skill XP map: which skill gets XP for each work action
WORK_ACTION_SKILL_XP = {
    "farming":         ("farming", 0.3),
    "fishing":         ("fishing", 0.3),
    "mining":          ("mining", 0.3),
    "smithing":        ("smithing", 0.3),
    "chopping":        ("woodcraft", 0.3),
    "foraging":        ("herbalism", 0.3),
    "hunting":         ("hunting", 0.3),
    "trading":         ("trading", 0.3),
    "performing":      ("performance", 0.3),
    "researching":     ("arcana", 0.2),
    "praying":         ("religion", 0.2),
    "healing":         ("medicine", 0.3),
    "cooking":         ("cooking", 0.3),
    "baking":          ("cooking", 0.3),
    "brewing":         ("brewing", 0.3),
    "tanning":         ("tanning", 0.3),
    "weaving":         ("weaving", 0.3),
    "carpentry":       ("woodcraft", 0.3),
    "coopering":       ("woodcraft", 0.2),
    "alchemy":         ("alchemy", 0.3),
    "crafting_pottery":("pottery", 0.3),
    "masonry":         ("masonry", 0.3),
    "herding":         ("animal_care", 0.3),
    "training_animal": ("animal_training", 0.3),
    "guarding":        ("swordsmanship", 0.1),
    "commanding":      ("leadership", 0.3),
    "writing":         ("literacy", 0.2),
    "mapping":         ("cartography", 0.3),
    "accounting":      ("accountancy", 0.3),
    "collecting":      ("intimidation", 0.1),
    "building":        ("masonry", 0.2),
    "prospecting":     ("mining", 0.2),
    "beekeeping":      ("animal_care", 0.2),
    "shipbuilding":    ("shipbuilding", 0.3),
    "barbering":       ("persuasion", 0.1),
    "negotiating":     ("persuasion", 0.3),
    "advising":        ("leadership", 0.2),
    "innkeeping":      ("cooking", 0.1),
    "cleaning":        ("cooking", 0.05),
    "digging":         ("masonry", 0.1),
    "jeweling":        ("jeweling", 0.3),
    "crafting_glass":  ("glassblowing", 0.3),
    "waiting_materials": None,  # no XP when idle
}


def try_profession_promotion(npc) -> Optional[str]:
    """Check if NPC qualifies for a profession promotion based on skills.

    Returns a message string if promoted, None otherwise.
    """
    current = getattr(npc, 'profession', '')
    skills = getattr(npc, 'npc_skills', {})
    level = getattr(npc, 'level', 1)

    for (from_prof, to_prof), reqs in PROFESSION_PROMOTIONS.items():
        if current != from_prof:
            continue

        meets = True
        for key, val in reqs.items():
            if key == "level":
                if level < val:
                    meets = False
                    break
            else:
                # It's a skill requirement
                if skills.get(key, 0) < val:
                    meets = False
                    break

        if meets and random.random() < 0.05:  # 5% daily chance when qualified
            npc.profession = to_prof
            npc.add_memory("career",
                           f"Promoted from {from_prof} to {to_prof}!", 4)
            return f"{npc.name} promoted: {from_prof} -> {to_prof}"

    return None


def try_hire_unemployed(npc, settlement_kind: str = "village") -> Optional[str]:
    """Assign an unemployed/Laborer NPC to an available job based on skills.

    Returns a message string if hired, None otherwise.
    """
    current = getattr(npc, 'profession', '')
    if current not in ('Laborer', '', 'Fighter'):
        return None

    skills = getattr(npc, 'npc_skills', {})

    # Score each possible profession by skill match
    skill_jobs = {
        "Farmer":      [("farming", 2)],
        "Fisherman":   [("fishing", 2)],
        "Woodcutter":  [("woodcraft", 2)],
        "Miner":       [("mining", 2)],
        "Herbalist":   [("herbalism", 2)],
        "Shepherd":    [("animal_care", 2)],
        "Baker":       [("cooking", 3)],
        "Cook":        [("cooking", 2)],
        "Guard":       [("swordsmanship", 2)],
        "Builder":     [("masonry", 2)],
        "Cleaner":     [],
        "Porter":      [],
        "Servant":     [],
    }

    best_prof = None
    best_score = -1

    for prof, skill_reqs in skill_jobs.items():
        score = 0
        for sk, weight in skill_reqs:
            score += skills.get(sk, 0) * weight
        # Random jitter to avoid everyone getting the same job
        score += random.uniform(0, 2)
        if score > best_score:
            best_score = score
            best_prof = prof

    if best_prof:
        npc.profession = best_prof
        npc.add_memory("career", f"Hired as {best_prof}", 3)
        return f"{npc.name} hired as {best_prof}"
    return None


def fire_npc(npc, reason: str = "dismissed") -> str:
    """Remove NPC from their current job. They become a Laborer."""
    old_prof = getattr(npc, 'profession', 'Laborer')
    npc.profession = "Laborer"
    npc.add_memory("career", f"Lost job as {old_prof}: {reason}", 4)
    return f"{npc.name} fired from {old_prof}: {reason}"


def grant_work_skill_xp(npc):
    """Grant skill XP based on the NPC's current work action.

    Called periodically (e.g. from lifecycle or work system) to let
    NPCs improve at their jobs over time.
    """
    action = getattr(npc, 'current_action', '')
    xp_info = WORK_ACTION_SKILL_XP.get(action)
    if xp_info:
        from game.systems.skills import gain_skill_xp
        skill_name, xp_amount = xp_info
        gain_skill_xp(npc, skill_name, xp_amount)


# ================================================================
# MATERIAL-AWARE CRAFTING
# ================================================================

def do_crafting_work(npc, world_effects, settlement_name: str) -> bool:
    """Crafter consumes materials from settlement stores, produces goods.

    Picks the best item this NPC's profession can craft from available
    materials and the RECIPES table, consumes the ingredients from
    settlement stores, and deposits the finished product.

    Returns True if something was crafted, False if materials lacking.
    """
    from game.systems.crafting import RECIPES

    profession = getattr(npc, 'profession', '')
    craftable = PROFESSION_CRAFTS.get(profession, [])
    if not craftable:
        return False

    stores = world_effects.get_stores_ref(settlement_name)

    # Try each item this profession can make (shuffle for variety)
    order = list(craftable)
    random.shuffle(order)

    for item_name in order:
        recipe = RECIPES.get(item_name)
        if recipe is None:
            continue

        result_count, ingredients, tool_needed, workstation, craft_time = recipe

        # Check if all ingredients are available in stores
        can_make = True
        for ing_name, ing_amount in ingredients:
            if stores.get(ing_name, 0) < ing_amount:
                can_make = False
                break

        if not can_make:
            continue

        # Consume ingredients from stores
        for ing_name, ing_amount in ingredients:
            stores[ing_name] = stores.get(ing_name, 0) - ing_amount

        # Produce the finished item
        stores[item_name] = stores.get(item_name, 0) + result_count

        npc.add_memory("work",
                       f"Crafted {result_count}x {item_name} for {settlement_name}", 1)
        return True

    # No craftable items had enough materials
    return False


def do_gathering_deposit(npc, world_effects, settlement_name: str,
                         gathered_items: Dict[str, int]):
    """Deposit gathered raw materials into settlement stores.

    Called when a gatherer (Farmer, Miner, Woodcutter, etc.) completes
    a gathering cycle and delivers goods.
    """
    stores = world_effects.get_stores_ref(settlement_name)
    for item_name, qty in gathered_items.items():
        stores[item_name] = stores.get(item_name, 0) + qty


# ================================================================
# PRICE GOSSIP — NPCs learn about local prices
# ================================================================

def inject_price_gossip(npc, world_effects, settlement_name: str):
    """Give an NPC a memory about local prices so they can discuss them.

    Called once per day for NPCs whose profession involves trade
    (Merchants, Innkeepers, Shopkeepers) or randomly for others.
    """
    if not world_effects or not settlement_name:
        return
    try:
        topics = world_effects.get_price_gossip(settlement_name)
    except Exception:
        return
    if topics:
        topic = topics[random.randint(0, len(topics) - 1)]
        npc.add_memory("economy", topic, 1)


def daily_price_gossip(npcs: list, world_effects):
    """Run once per day: give trade-aware NPCs price gossip memories."""
    if not world_effects:
        return
    trade_professions = {"Merchant", "Trader", "Innkeeper", "Banker",
                         "Shop Assistant", "Barber"}
    for npc in npcs:
        if not getattr(npc, 'alive', True):
            continue
        profession = getattr(npc, 'profession', '')
        settlement = getattr(npc, 'home_settlement', None)
        if not settlement:
            settlement = getattr(npc, 'faction', None)
        if not settlement:
            continue

        if profession in trade_professions:
            inject_price_gossip(npc, world_effects, settlement)
        elif random.random() < 0.1:
            # 10% chance for non-trade NPCs to notice prices
            inject_price_gossip(npc, world_effects, settlement)


# ================================================================
# FOREIGN TRADE / CARAVAN SYSTEM
# ================================================================

class CaravanSystem:
    """Manages foreign merchant caravans that bring trade goods.

    Caravans arrive at towns/cities periodically, selling foreign luxury
    goods and buying local surplus.  This is the only source for items
    in FOREIGN_TRADE_GOODS.
    """

    def __init__(self):
        self._next_caravan_day: Dict[str, int] = {}  # settlement -> next arrival day
        self._active_caravans: List[Dict] = []

    def daily_update(self, time_sys, world_effects, settlements):
        """Check for caravan arrivals.  Called once per game-day.

        Parameters
        ----------
        time_sys : object with .day attribute
        world_effects : WorldEffects instance
        settlements : iterable of settlement plan objects (with .name, .kind)
        """
        current_day = getattr(time_sys, 'day', 0)
        rng = random.Random(current_day * 31337)

        for sp in settlements:
            # Caravans only visit towns and cities
            kind = getattr(sp, 'kind', 'hamlet')
            if kind not in ('town', 'city'):
                continue

            name = sp.name
            next_day = self._next_caravan_day.get(name, 0)

            if current_day >= next_day:
                # Caravan arrives!
                self._caravan_arrives(name, kind, world_effects, rng)
                # Schedule next: towns every 10-20 days, cities every 5-12
                if kind == 'city':
                    interval = rng.randint(5, 12)
                else:
                    interval = rng.randint(10, 20)
                self._next_caravan_day[name] = current_day + interval

    def _caravan_arrives(self, settlement_name: str, kind: str,
                         world_effects, rng: random.Random):
        """A foreign caravan arrives at a settlement.

        It sells foreign goods (added to stores) and buys local surplus
        (removed from stores, gold added).
        """
        stores = world_effects.get_stores_ref(settlement_name)

        # --- Sell foreign goods ---
        # Pick 2-4 random foreign goods to offer
        goods_list = list(FOREIGN_TRADE_GOODS.items())
        rng.shuffle(goods_list)
        num_goods = rng.randint(2, min(4, len(goods_list)))

        for trade_name, trade_info in goods_list[:num_goods]:
            price = trade_info["base_price"]
            # Can the settlement afford it?
            if stores.get("gold", 0) >= price:
                qty = rng.randint(1, 3)
                total_cost = price * qty
                if stores.get("gold", 0) >= total_cost:
                    stores["gold"] -= total_cost
                    stores[trade_name] = stores.get(trade_name, 0) + qty

        # --- Buy local surplus (exports) ---
        exportable = {
            "Wood": 3, "Iron Ore": 5, "Wheat": 2, "Leather": 6,
            "Ale": 4, "Wine": 6, "Linen": 4, "Iron Ingot": 8,
            "Herbs": 3, "Honey": 4, "Salt": 2, "Wool": 3,
            "Cheese": 3, "Planks": 2, "Rope": 3,
        }
        for item_name, gold_per_unit in exportable.items():
            stock = stores.get(item_name, 0)
            # Only buy surplus beyond a reserve of 10
            surplus = stock - 10
            if surplus > 0:
                sell_qty = min(surplus, rng.randint(1, 5))
                stores[item_name] -= sell_qty
                stores["gold"] = stores.get("gold", 0) + sell_qty * gold_per_unit

    def get_active_caravans(self) -> List[Dict]:
        return list(self._active_caravans)


# Singleton for easy import
_caravan_system = CaravanSystem()


def get_caravan_system() -> CaravanSystem:
    """Return the global CaravanSystem singleton."""
    return _caravan_system
