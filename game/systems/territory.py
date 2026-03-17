"""
Territory & Land Ownership: Civilization-style land claiming, property, and expansion.

Characters and factions claim land, build on it, and defend it.
Land has value based on resources, location, and improvements.
NPCs are motivated to acquire land for farming, mining, building, and income.
Monsters claim territory for dens, hunting grounds, and expansion.
Kingdoms expand through colonization and conquest.
"""

import random
import math
from typing import Dict, List, Optional, Tuple, Set
from game.settings import *


class LandPlot:
    """A claimed piece of land."""
    __slots__ = ('x', 'y', 'radius', 'owner_name', 'owner_type', 'faction',
                 'land_use', 'value', 'income', 'improvements')

    def __init__(self, x: int, y: int, radius: int, owner_name: str,
                 owner_type: str = "npc", faction: str = ""):
        self.x = x
        self.y = y
        self.radius = radius
        self.owner_name = owner_name
        self.owner_type = owner_type  # "npc", "monster", "kingdom", "player"
        self.faction = faction
        self.land_use = "unclaimed"  # farm, mine, settlement, den, hunting_ground, forest_reserve
        self.value = 0
        self.income = 0  # gold per day from this land
        self.improvements: List[str] = []  # what's been built

    def contains(self, px: float, py: float) -> bool:
        dx = px - self.x
        dy = py - self.y
        return dx * dx + dy * dy <= self.radius * self.radius


# What NPCs want to do with land based on class
CLASS_LAND_DESIRES = {
    "Fighter":   ["settlement", "training_ground"],
    "Wizard":    ["tower", "library"],
    "Cleric":    ["temple", "settlement"],
    "Rogue":     ["hideout", "warehouse"],
    "Ranger":    ["forest_reserve", "outpost"],
    "Paladin":   ["fortress", "settlement"],
    "Barbarian": ["hunting_ground", "camp"],
    "Bard":      ["tavern", "settlement"],
    "Druid":     ["grove", "farm"],
    "Monk":      ["monastery", "garden"],
    "Sorcerer":  ["tower", "settlement"],
    "Warlock":   ["sanctum", "settlement"],
}

# Monster territory desires
MONSTER_TERRITORY = {
    "wolf":     {"type": "den", "radius": 8, "builds": False},
    "dire_wolf":{"type": "den", "radius": 10, "builds": False},
    "goblin":   {"type": "camp", "radius": 12, "builds": True},
    "orc":      {"type": "stronghold", "radius": 15, "builds": True},
    "bandit":   {"type": "hideout", "radius": 10, "builds": True},
    "ogre":     {"type": "lair", "radius": 8, "builds": False},
    "troll":    {"type": "den", "radius": 10, "builds": False},
    "kobold":   {"type": "warren", "radius": 12, "builds": True},
    "gnoll":    {"type": "camp", "radius": 12, "builds": True},
    "bugbear":  {"type": "lair", "radius": 8, "builds": False},
}

# Land value factors
TERRAIN_VALUE = {
    GRASS: 5, FOREST: 3, FARMLAND: 10, ROAD: 8,
    ORE_VEIN: 20, GEM_DEPOSIT: 50, HERB_PATCH: 8,
    BERRY_BUSH: 6, CLAY_PIT: 7, FRUIT_TREE: 7,
    WATER: 2, SAND: 1, MOUNTAIN: 1,
    COPPER_VEIN: 15, FLAX_FIELD: 6, BEEHIVE: 12, SALT_FLAT: 10,
}


class TerritorySystem:
    """Manages land ownership, claims, and territorial expansion."""

    def __init__(self):
        self.plots: List[LandPlot] = []
        self.property_market: List[Dict] = []  # plots for sale
        self.update_timer = 0.0
        self.expansion_timer = 0.0
        self.event_log: List[str] = []

    def initialize(self, structures: list, npcs: list, creatures: list,
                   governance, world):
        """Set up initial land claims."""
        # Kingdoms claim territory around castles and settlements
        for kingdom_name, kingdom in governance.kingdoms.items():
            for settlement_name in kingdom.settlements:
                for s in structures:
                    if s.name == settlement_name:
                        plot = LandPlot(s.x, s.y, s.radius + 10,
                                       kingdom_name, "kingdom", kingdom_name)
                        plot.land_use = "settlement"
                        plot.value = self._calculate_land_value(s.x, s.y, s.radius + 10, world)
                        plot.income = plot.value * 0.1
                        self.plots.append(plot)
                        break

        # NPCs near their homes claim small plots
        for npc in npcs[:100]:  # limit initial claims
            if not npc.alive:
                continue
            if random.random() < 0.3:
                plot = LandPlot(int(npc.home_x), int(npc.home_y), 3,
                               npc.name, "npc", getattr(npc, 'faction', ''))
                plot.land_use = "homestead"
                plot.value = self._calculate_land_value(int(npc.home_x), int(npc.home_y), 3, world)
                self.plots.append(plot)

        # Intelligent monsters claim territory
        from game.systems.living import CREATURE_INTELLIGENCE
        for creature in creatures:
            if not creature.alive:
                continue
            intel = CREATURE_INTELLIGENCE.get(creature.kind, 0)
            territory = MONSTER_TERRITORY.get(creature.kind)
            if intel >= 2 and territory and random.random() < 0.1:
                plot = LandPlot(int(creature.home_x), int(creature.home_y),
                               territory["radius"], creature.kind, "monster")
                plot.land_use = territory["type"]
                self.plots.append(plot)

    def update(self, dt: float, npcs: list, creatures: list,
               governance, world, construction, spatial_grid):
        """Periodic territory updates - expansion, development, disputes."""
        self.update_timer += dt
        if self.update_timer < 60.0:
            return
        self.update_timer = 0.0

        # NPC land development motivation
        self._npc_land_development(npcs, world, construction, spatial_grid, governance)

        # Kingdom expansion
        self.expansion_timer += dt
        if self.expansion_timer > 300:
            self.expansion_timer = 0
            self._kingdom_expansion(governance, world, construction)

        # Monster territory expansion
        self._monster_expansion(creatures, world)

        # Property market
        self._update_market(npcs)

        # Land income
        for plot in self.plots:
            if plot.owner_type == "kingdom":
                for name, kingdom in governance.kingdoms.items():
                    if name == plot.faction:
                        kingdom.treasury += plot.income * 0.01

    def _npc_land_development(self, npcs, world, construction, spatial_grid, governance):
        """NPCs with gold and no property seek to acquire and develop land."""
        for npc in npcs:
            if not npc.alive or getattr(npc, 'npc_gold', 0) < 20:
                continue
            if random.random() > 0.02:  # 2% chance per check
                continue

            # Already owns land?
            owns = any(p.owner_name == npc.name for p in self.plots)
            if owns:
                # Develop existing land
                plot = next(p for p in self.plots if p.owner_name == npc.name)
                self._develop_plot(npc, plot, world, construction)
                continue

            # Try to claim unclaimed land near home
            hx, hy = int(npc.home_x), int(npc.home_y)
            claimed = any(p.contains(hx, hy) for p in self.plots)
            if not claimed:
                # Check building permission from local kingdom
                has_permission = True
                for kingdom_name, kingdom in governance.kingdoms.items():
                    if kingdom.contains(hx, hy):
                        title = getattr(npc, 'title', 'commoner')
                        if not kingdom.can_build(npc.name, title):
                            has_permission = False
                            # Try to bribe?
                            if npc.npc_gold >= 15 and random.random() < 0.2:
                                cha = npc.attributes.get("charisma", 5)
                                success, msg = kingdom.try_bribe(10, cha)
                                if success:
                                    has_permission = True
                                    npc.npc_gold -= 10
                                    npc.add_memory("corruption", f"Bribed an official to build", 3)
                        break

                if has_permission:
                    char_class = getattr(npc, 'char_class', 'Fighter')
                    desires = CLASS_LAND_DESIRES.get(char_class, ["settlement"])
                    land_use = random.choice(desires)

                    plot = LandPlot(hx, hy, 4, npc.name, "npc",
                                   getattr(npc, 'faction', ''))
                    plot.land_use = land_use
                    plot.value = self._calculate_land_value(hx, hy, 4, world)
                    npc.npc_gold -= 10
                    self.plots.append(plot)
                    npc.add_memory("property", f"Claimed land for a {land_use}!", 4)
                    self.event_log.append(f"{npc.name} claimed land for a {land_use}")

            # Or buy from market
            elif self.property_market:
                listing = self.property_market[0]
                price = listing.get("price", 50)
                if npc.npc_gold >= price:
                    plot = listing["plot"]
                    plot.owner_name = npc.name
                    plot.owner_type = "npc"
                    npc.npc_gold -= price
                    self.property_market.pop(0)
                    npc.add_memory("property", f"Bought land at ({plot.x},{plot.y})", 3)

    def _develop_plot(self, npc, plot: LandPlot, world, construction):
        """NPC improves their land with buildings and infrastructure."""
        if random.random() > 0.1:
            return

        char_class = getattr(npc, 'char_class', '')

        if plot.land_use == "farm" and "irrigation" not in plot.improvements:
            # Build irrigation (convert grass to farmland)
            for dy in range(-plot.radius, plot.radius + 1):
                for dx in range(-plot.radius, plot.radius + 1):
                    nx, ny = plot.x + dx, plot.y + dy
                    if (0 <= nx < world.width and 0 <= ny < world.height and
                        world.tiles[ny][nx] == GRASS and random.random() < 0.3):
                        world.modify_tile(nx, ny, TILLED_SOIL)
            plot.improvements.append("irrigation")
            plot.income += 2
            self.event_log.append(f"{npc.name} developed farmland")

        elif plot.land_use in ("settlement", "homestead") and "fence" not in plot.improvements:
            # Build walls/fences around property
            construction.commission_project("stone_wall", plot.x + plot.radius, plot.y,
                                           npc.name, "Property fence")
            plot.improvements.append("fence")
            plot.value += 10

        elif plot.land_use == "mine" and "mineshaft" not in plot.improvements:
            plot.improvements.append("mineshaft")
            plot.income += 5
            self.event_log.append(f"{npc.name} dug a mineshaft")

    def _kingdom_expansion(self, governance, world, construction):
        """Kingdoms expand by claiming and developing new territory."""
        for kingdom_name, kingdom in governance.kingdoms.items():
            if kingdom.treasury < 100:
                continue
            if random.random() > 0.1:
                continue

            # Find unclaimed land with resources near kingdom
            best_spot = None
            best_value = 0
            for _ in range(20):
                angle = random.uniform(0, 2 * math.pi)
                dist = random.uniform(30, kingdom.territory_radius * 0.8)
                tx = int(kingdom.castle_x + math.cos(angle) * dist)
                ty = int(kingdom.castle_y + math.sin(angle) * dist)

                if not (10 < tx < world.width - 10 and 10 < ty < world.height - 10):
                    continue

                if any(p.contains(tx, ty) for p in self.plots):
                    continue  # already claimed

                value = self._calculate_land_value(tx, ty, 8, world)
                if value > best_value:
                    best_value = value
                    best_spot = (tx, ty)

            if best_spot and best_value > 20:
                plot = LandPlot(best_spot[0], best_spot[1], 8,
                               kingdom_name, "kingdom", kingdom_name)
                plot.land_use = "colony"
                plot.value = best_value
                plot.income = best_value * 0.05
                self.plots.append(plot)
                kingdom.treasury -= 50
                self.event_log.append(
                    f"{kingdom_name} established a colony at ({best_spot[0]}, {best_spot[1]})")

                # Commission road to new colony
                construction.commission_project(
                    "road_segment",
                    (kingdom.castle_x + best_spot[0]) // 2,
                    (kingdom.castle_y + best_spot[1]) // 2,
                    kingdom_name, f"Road to colony")

    def _monster_expansion(self, creatures, world):
        """Intelligent monsters expand territory and build structures."""
        from game.systems.living import CREATURE_INTELLIGENCE

        for creature in creatures:
            if not creature.alive:
                continue
            intel = CREATURE_INTELLIGENCE.get(creature.kind, 0)
            if intel < 2:
                continue
            if random.random() > 0.005:
                continue

            territory = MONSTER_TERRITORY.get(creature.kind)
            if not territory or not territory.get("builds"):
                continue

            # Already has territory?
            has_territory = any(p.owner_name == creature.kind and
                               p.contains(creature.x, creature.y)
                               for p in self.plots)
            if has_territory:
                continue

            # Claim territory and build
            ix, iy = int(creature.x), int(creature.y)
            plot = LandPlot(ix, iy, territory["radius"],
                           creature.kind, "monster")
            plot.land_use = territory["type"]
            self.plots.append(plot)

            # Build crude structures
            if territory["builds"]:
                for _ in range(random.randint(2, 4)):
                    bx = ix + random.randint(-territory["radius"]//2, territory["radius"]//2)
                    by = iy + random.randint(-territory["radius"]//2, territory["radius"]//2)
                    if (0 <= bx < world.width and 0 <= by < world.height and
                        world.tiles[by][bx] in (GRASS, FOREST)):
                        world.modify_tile(bx, by, BUILT_WALL if random.random() < 0.3 else BUILT_FLOOR)

            self.event_log.append(
                f"{creature.kind} pack established a {territory['type']} at ({ix}, {iy})")

    def _update_market(self, npcs):
        """NPCs can list property for sale."""
        if len(self.property_market) > 10:
            return

        for npc in npcs:
            if not npc.alive or random.random() > 0.001:
                continue

            # NPC with multiple plots might sell one
            owned = [p for p in self.plots if p.owner_name == npc.name]
            if len(owned) > 1:
                cheapest = min(owned, key=lambda p: p.value)
                price = max(10, int(cheapest.value * 1.5))
                self.property_market.append({"plot": cheapest, "price": price, "seller": npc.name})
                self.event_log.append(f"{npc.name} listed land for sale ({price}g)")

    def _calculate_land_value(self, cx: int, cy: int, radius: int, world) -> int:
        """Calculate land value based on terrain and resources."""
        value = 0
        count = 0
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy > radius * radius:
                    continue
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < world.width and 0 <= ny < world.height:
                    tile = world.tiles[ny][nx]
                    value += TERRAIN_VALUE.get(tile, 1)
                    count += 1
        return value // max(1, count) * count // 10

    def get_owner_at(self, x: float, y: float) -> Optional[str]:
        """Get who owns the land at a position."""
        for plot in self.plots:
            if plot.contains(x, y):
                return f"{plot.owner_name} ({plot.land_use})"
        return None

    def get_event_log(self) -> List[str]:
        msgs = list(self.event_log)
        self.event_log.clear()
        return msgs
