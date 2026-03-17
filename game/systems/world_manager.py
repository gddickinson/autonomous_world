"""World manager: creature spawning, NPC spawning, ground items, entity updates."""

import math
import random
import time as _time
from typing import List, Tuple, Dict, Any
from game.settings import *
from game.core.player import Player
from game.core.npc import NPC
from game.core.creature import Creature
from game.core.items import Item, make_item


class WorldManager:
    """Manages creature spawning and world events."""

    # Dormancy radii (tiles).  Hysteresis prevents flickering at the boundary.
    ACTIVE_RADIUS = 600       # dormant -> live when closer than this
    DORMANT_RADIUS = 800      # live -> dormant when farther than this
    DORMANCY_CHECK_TICKS = 30  # check every 30 ticks (~1 second at 30 fps)

    # Creatures with CR >= this threshold get dormancy tracking instead of
    # simple despawn/respawn.
    IMPORTANT_CREATURE_CR = 3

    def __init__(self, world):
        self.world = world
        self.creatures: List[Creature] = []
        self.npcs: List[NPC] = []
        self.ground_items: List[Tuple[float, float, Item]] = []
        self.spawn_timer = 0.0
        self.max_creatures = 120

        # --- Dormancy ---
        self._dormant_npcs: List[Dict[str, Any]] = []
        self._dormant_creatures: List[Dict[str, Any]] = []
        self._dormancy_tick = 0

    @staticmethod
    def _pick_biome_creature(rng: random.Random, biome_data: dict):
        """Pick a creature from biome_data using rarity tiers.

        biome_data has keys: common, uncommon, rare, weights.
        Returns a creature kind string or None.
        """
        tiers = ["common", "uncommon", "rare"]
        weights = biome_data.get("weights", [60, 30, 10])
        # Filter out empty tiers
        valid_tiers = []
        valid_weights = []
        for tier, w in zip(tiers, weights):
            creatures = biome_data.get(tier, [])
            if creatures and w > 0:
                valid_tiers.append(tier)
                valid_weights.append(w)
        if not valid_tiers:
            return None
        chosen_tier = rng.choices(valid_tiers, weights=valid_weights, k=1)[0]
        creatures = biome_data[chosen_tier]
        return rng.choice(creatures) if creatures else None

    def initialize(self, rng: random.Random):
        """Spawn initial creatures and NPCs.

        For chunked worlds (10,000+), only spawns entities near the spawn
        point to avoid triggering chunk generation across the entire map.
        Other zones are populated on demand as the player approaches.
        """
        from game.world.world import ChunkedWorld

        if isinstance(self.world, ChunkedWorld):
            self._spawn_near_player(rng, self.world.spawn_point)
        else:
            self._spawn_initial_creatures(rng)
            self._spawn_npcs(rng)

    def _spawn_initial_creatures(self, rng: random.Random):
        """Spawn creatures using biome-aware ecology data, with D&D fallback."""
        from game.data.dnd import MONSTERS, BIOME_MAP
        from game.data.ecology import (
            BIOME_CREATURES, PACK_CREATURES, NOCTURNAL_CREATURES,
            WATER_ONLY_CREATURES, SETTLEMENT_CREATURES,
        )

        # Collect ALL settlement positions for exclusion zone
        settlement_kinds = {"village", "town", "city", "hamlet", "castle", "temple"}
        settlement_positions = [(s.x, s.y, s.radius + 25)
                                for s in self.world.structures if s.kind in settlement_kinds]
        # Also exclude spawn temple area
        cx, cy = self.world.width // 2, self.world.height // 2
        settlement_positions.append((cx, cy, 40))

        # Exclude test island area entirely
        test_rect = getattr(self.world, 'test_island_rect', None)

        # Target creature count scaled by world size
        scale = (self.world.width * self.world.height) / (300 * 300)
        target_creatures = int(120 * scale)
        spawned_total = 0

        for _ in range(target_creatures * 25):
            if spawned_total >= target_creatures:
                break
            x = rng.randint(10, self.world.width - 10)
            y = rng.randint(10, self.world.height - 10)

            tile = self.world.tiles[y][x]
            biome_data = BIOME_CREATURES.get(tile)
            if not biome_data:
                continue

            # Must be far from ALL settlements
            too_close = any(
                math.sqrt((sx - x)**2 + (sy - y)**2) < exclusion_r
                for sx, sy, exclusion_r in settlement_positions
            )
            if too_close:
                continue

            # Exclude test island
            if test_rect:
                rx, ry, rw, rh = test_rect
                if rx <= x <= rx + rw and ry <= y <= ry + rh:
                    continue

            kind = self._pick_biome_creature(rng, biome_data)
            if not kind:
                continue

            # Water-only restriction
            if kind in WATER_ONLY_CREATURES and tile not in (WATER, SHALLOW_WATER):
                continue

            # Nocturnal: only 30% chance at world-gen time
            if kind in NOCTURNAL_CREATURES and rng.random() > 0.3:
                continue

            # Pack spawning
            pack_info = PACK_CREATURES.get(kind)
            pack_size = rng.randint(*pack_info) if pack_info else 1

            for i in range(pack_size):
                if spawned_total >= target_creatures:
                    break
                ox = x + rng.randint(-3, 3) if i > 0 else x
                oy = y + rng.randint(-3, 3) if i > 0 else y
                if 0 <= ox < self.world.width and 0 <= oy < self.world.height:
                    creature = Creature(float(ox), float(oy), kind)
                    self.creatures.append(creature)
                    spawned_total += 1

        # Spawn farm animals near settlements
        farm_animals = SETTLEMENT_CREATURES["common"]
        guard_animals = SETTLEMENT_CREATURES["guard"]
        for s in self.world.structures:
            if s.kind not in ("village", "town", "city", "hamlet"):
                continue
            num_farm = rng.randint(3, 8)
            for _ in range(num_farm):
                kind = rng.choice(farm_animals)
                fx = s.x + rng.randint(-s.radius, s.radius)
                fy = s.y + rng.randint(-s.radius, s.radius)
                if (0 <= fx < self.world.width and 0 <= fy < self.world.height
                        and self.world.is_walkable(fx, fy)):
                    creature = Creature(float(fx), float(fy), kind)
                    creature.home_x = float(s.x)
                    creature.home_y = float(s.y)
                    creature.leash_range = float(s.radius + 5)
                    self.creatures.append(creature)
            # Guard dogs at perimeter
            for _ in range(rng.randint(1, 2)):
                kind = rng.choice(guard_animals)
                angle = rng.uniform(0, 2 * 3.14159)
                gx = int(s.x + math.cos(angle) * s.radius * 0.9)
                gy = int(s.y + math.sin(angle) * s.radius * 0.9)
                if (0 <= gx < self.world.width and 0 <= gy < self.world.height
                        and self.world.is_walkable(gx, gy)):
                    creature = Creature(float(gx), float(gy), kind)
                    creature.home_x = float(s.x)
                    creature.home_y = float(s.y)
                    creature.leash_range = float(s.radius + 5)
                    self.creatures.append(creature)

        # Spawn undead/dungeon creatures in ruins
        ruin_monsters = [name for name, stats in MONSTERS.items()
                         if "floor" in stats.get("biomes", [])]
        for s in self.world.structures:
            if s.kind == "ruins":
                for _ in range(rng.randint(3, 6)):
                    kind = rng.choice(ruin_monsters) if ruin_monsters else "skeleton"
                    cx = s.x + rng.randint(-s.radius, s.radius)
                    cy = s.y + rng.randint(-s.radius, s.radius)
                    if self.world.is_walkable(cx, cy):
                        creature = Creature(float(cx), float(cy), kind)
                        creature.home_x = float(s.x)
                        creature.home_y = float(s.y)
                        creature.leash_range = float(s.radius + 5)
                        self.creatures.append(creature)

    def _spawn_npcs(self, rng: random.Random):
        """Spawn NPCs using building-based spawn data or fallback method."""
        from game.data.dnd import random_npc_class_and_race

        name_pool = list(NPC_NAMES) + [
            "Alara", "Brom", "Circe", "Dorian", "Elowen", "Faelen",
            "Gwynn", "Hadrian", "Isolde", "Jareth", "Kael", "Lyra",
            "Mordecai", "Niamh", "Orin", "Perrin", "Rhiannon", "Silas",
            "Talwyn", "Ulric", "Virelai", "Wynne", "Xerath", "Ysolde", "Zephyr",
            "Aethon", "Briar", "Cassian", "Delphine", "Evander", "Fiora",
            "Gideon", "Helena", "Idris", "Jorath", "Keara", "Lucien",
            "Maelis", "Nerys", "Oberon", "Phaedra", "Ravenna", "Soren",
            "Thalia", "Uriel", "Vesper", "Weylin", "Ximena", "Yoric", "Zariel",
            "Aldric", "Brynn", "Corin", "Dahlia", "Emeric", "Faye", "Gareth",
            "Hazel", "Ivo", "Juno", "Kai", "Liara", "Magnus", "Nyx",
            "Orla", "Pike", "Riven", "Selene", "Tormund", "Una", "Vex",
        ]
        rng.shuffle(name_pool)
        name_idx = 0

        # Use building-based spawn data if available
        spawn_data = getattr(self.world, 'npc_spawn_data', [])

        if spawn_data:
            # Spawn from building blueprints
            for spawn in spawn_data:
                if name_idx >= len(name_pool):
                    name_idx = 0
                name = name_pool[name_idx]
                name_idx += 1

                char_class = spawn.get("class", "")
                race = spawn.get("race", "")
                if not char_class or not race:
                    char_class, race = random_npc_class_and_race()
                if not race:
                    _, race = random_npc_class_and_race()

                level = rng.randint(1, 5)
                # Assign profession from spawn data; if missing, pick a
                # civilian profession appropriate for the nearest settlement.
                profession = spawn.get("profession", "")
                if not profession:
                    profession = self._pick_settlement_profession(
                        spawn["x"], spawn["y"], rng) or char_class
                npc = NPC(spawn["x"], spawn["y"], name, profession,
                         char_class=char_class, race=race, level=level)
                npc.home_x = spawn["x"]
                npc.home_y = spawn["y"]
                self.npcs.append(npc)
        else:
            # Fallback: spawn in structures with settlement-appropriate professions
            from game.settings import SETTLEMENT_PROFESSIONS
            for structure in self.world.structures:
                if structure.kind not in ("village", "town", "city", "hamlet", "castle"):
                    continue

                num_npcs = {"hamlet": 3, "village": 6, "town": 12, "city": 20, "castle": 8
                           }.get(structure.kind, 5)

                # Build weighted profession list for this settlement type
                prof_pool = SETTLEMENT_PROFESSIONS.get(structure.kind,
                                                        SETTLEMENT_PROFESSIONS["village"])
                weighted_profs = []
                for prof, weight in prof_pool:
                    weighted_profs.extend([prof] * weight)

                for _ in range(num_npcs):
                    if name_idx >= len(name_pool):
                        name_idx = 0
                    name = name_pool[name_idx]
                    name_idx += 1

                    char_class, race = random_npc_class_and_race()
                    level = rng.randint(1, 5)

                    # Pick a profession appropriate for this settlement
                    profession = rng.choice(weighted_profs) if weighted_profs else char_class

                    pos = self.world.find_open_pos_near(
                        structure.x, structure.y, structure.radius + 2, rng)
                    npc = NPC(float(pos[0]), float(pos[1]), name, profession,
                             char_class=char_class, race=race, level=level)
                    npc.home_x = float(pos[0])
                    npc.home_y = float(pos[1])
                    self.npcs.append(npc)

    def _pick_settlement_profession(self, x: float, y: float,
                                     rng: random.Random) -> str:
        """Return a civilian profession appropriate for the nearest settlement.

        Looks up the nearest structure (village/town/city/hamlet/castle) and
        picks a weighted-random profession from SETTLEMENT_PROFESSIONS.
        Returns empty string if no suitable settlement is nearby.
        """
        best_struct = None
        best_dist = float('inf')
        for s in self.world.structures:
            if s.kind not in ("village", "town", "city", "hamlet", "castle"):
                continue
            d = (s.x - x) ** 2 + (s.y - y) ** 2
            if d < best_dist:
                best_dist = d
                best_struct = s

        if best_struct is None:
            return ""

        prof_pool = SETTLEMENT_PROFESSIONS.get(
            best_struct.kind, SETTLEMENT_PROFESSIONS.get("village", []))
        if not prof_pool:
            return ""

        weighted = []
        for prof, weight in prof_pool:
            weighted.extend([prof] * weight)
        return rng.choice(weighted) if weighted else ""

    def _spawn_near_player(self, rng: random.Random, spawn_point):
        """Spawn NPCs and creatures only near a position (for chunked worlds).

        Populates settlements within ZONE_RADIUS of the spawn point.
        Other zones are populated later via activate_zone().
        """
        from game.data.dnd import random_npc_class_and_race, MONSTERS, BIOME_MAP

        px, py = spawn_point
        zone_radius = 500  # tiles — roughly 2-3 chunk radius

        # Track which settlements have been populated
        self._populated_settlements = set()

        # Spawn NPCs from npc_spawn_data for nearby settlements
        spawn_data = getattr(self.world, 'npc_spawn_data', [])
        name_pool = list(NPC_NAMES) + [
            "Alara", "Brom", "Circe", "Dorian", "Elowen", "Faelen",
            "Gwynn", "Hadrian", "Isolde", "Jareth", "Kael", "Lyra",
        ]
        rng.shuffle(name_pool)
        name_idx = 0

        for spawn in spawn_data:
            sx, sy = spawn["x"], spawn["y"]
            if abs(sx - px) > zone_radius or abs(sy - py) > zone_radius:
                continue

            if name_idx >= len(name_pool):
                name_idx = 0
            name = spawn.get("name", name_pool[name_idx])
            name_idx += 1

            char_class = spawn.get("class", "")
            race = spawn.get("race", "")
            if not char_class or not race:
                char_class, race = random_npc_class_and_race()

            level = rng.randint(1, 5)
            profession = spawn.get("profession", "")
            if not profession:
                profession = self._pick_settlement_profession(
                    float(sx), float(sy), rng) or char_class
            npc = NPC(float(sx), float(sy), name, profession,
                     char_class=char_class, race=race, level=level)
            npc.home_x = float(sx)
            npc.home_y = float(sy)
            self.npcs.append(npc)

        # Track populated settlements
        for s in self.world.structures:
            if s.kind in ("village", "town", "city", "hamlet", "castle"):
                if abs(s.x - px) <= zone_radius and abs(s.y - py) <= zone_radius:
                    self._populated_settlements.add(s.name)

        # --- Biome-aware creature spawning using ecology data ---
        from game.data.ecology import (
            BIOME_CREATURES, PACK_CREATURES, NOCTURNAL_CREATURES,
            WATER_ONLY_CREATURES, SETTLEMENT_CREATURES,
        )

        settlement_positions = [(s.x, s.y, s.radius + 25)
                                for s in self.world.structures
                                if s.kind in ("village", "town", "city",
                                              "hamlet", "castle", "temple")
                                and abs(s.x - px) <= zone_radius
                                and abs(s.y - py) <= zone_radius]

        # Spawn creatures by sampling random positions and looking up biome
        target_creatures = 80  # target population for initial zone
        spawned_total = 0
        for _ in range(target_creatures * 25):
            if spawned_total >= target_creatures:
                break
            x = rng.randint(max(10, px - zone_radius),
                            min(self.world.width - 10, px + zone_radius))
            y = rng.randint(max(10, py - zone_radius),
                            min(self.world.height - 10, py + zone_radius))

            tile = self.world.tiles[y][x]
            biome_data = BIOME_CREATURES.get(tile)
            if not biome_data:
                continue

            # Must be far from settlements (wild creatures)
            too_close = any(
                math.sqrt((sx - x)**2 + (sy - y)**2) < excl
                for sx, sy, excl in settlement_positions
            )
            if too_close:
                continue

            # Pick rarity tier
            kind = self._pick_biome_creature(rng, biome_data)
            if not kind:
                continue

            # Water-only creatures need water tile
            if kind in WATER_ONLY_CREATURES and tile not in (WATER, SHALLOW_WATER):
                continue

            # Skip nocturnal creatures during initial spawn (they spawn at night)
            if kind in NOCTURNAL_CREATURES:
                if rng.random() > 0.3:  # still allow some to exist at startup
                    continue

            # Pack spawning
            pack_info = PACK_CREATURES.get(kind)
            pack_size = rng.randint(*pack_info) if pack_info else 1

            for i in range(pack_size):
                if spawned_total >= target_creatures:
                    break
                ox = x + rng.randint(-3, 3) if i > 0 else x
                oy = y + rng.randint(-3, 3) if i > 0 else y
                if not self.world.is_walkable(ox, oy):
                    ox, oy = x, y
                creature = Creature(float(ox), float(oy), kind)
                self.creatures.append(creature)
                spawned_total += 1

        # --- Spawn farm animals near settlements ---
        farm_animals = SETTLEMENT_CREATURES["common"]
        guard_animals = SETTLEMENT_CREATURES["guard"]
        for s in self.world.structures:
            if s.kind not in ("village", "town", "city", "hamlet"):
                continue
            if abs(s.x - px) > zone_radius or abs(s.y - py) > zone_radius:
                continue
            # Spawn 3-8 farm animals inside settlement radius
            num_farm = rng.randint(3, 8)
            for _ in range(num_farm):
                kind = rng.choice(farm_animals)
                fx = s.x + rng.randint(-s.radius, s.radius)
                fy = s.y + rng.randint(-s.radius, s.radius)
                if self.world.is_walkable(fx, fy):
                    creature = Creature(float(fx), float(fy), kind)
                    creature.home_x = float(s.x)
                    creature.home_y = float(s.y)
                    creature.leash_range = float(s.radius + 5)
                    self.creatures.append(creature)
            # Spawn 1-2 guard dogs at perimeter
            for _ in range(rng.randint(1, 2)):
                kind = rng.choice(guard_animals)
                angle = rng.uniform(0, 2 * 3.14159)
                gx = int(s.x + math.cos(angle) * s.radius * 0.9)
                gy = int(s.y + math.sin(angle) * s.radius * 0.9)
                if self.world.is_walkable(gx, gy):
                    creature = Creature(float(gx), float(gy), kind)
                    creature.home_x = float(s.x)
                    creature.home_y = float(s.y)
                    creature.leash_range = float(s.radius + 5)
                    self.creatures.append(creature)

        # Spawn undead in nearby ruins
        ruin_monsters = [n for n, s in MONSTERS.items()
                         if "floor" in s.get("biomes", [])]
        for s in self.world.structures:
            if s.kind == "ruins":
                if abs(s.x - px) > zone_radius or abs(s.y - py) > zone_radius:
                    continue
                for _ in range(rng.randint(3, 6)):
                    kind = rng.choice(ruin_monsters) if ruin_monsters else "skeleton"
                    cx = s.x + rng.randint(-s.radius, s.radius)
                    cy = s.y + rng.randint(-s.radius, s.radius)
                    if self.world.is_walkable(cx, cy):
                        creature = Creature(float(cx), float(cy), kind)
                        creature.home_x = float(s.x)
                        creature.home_y = float(s.y)
                        creature.leash_range = float(s.radius + 5)
                        self.creatures.append(creature)

    def _check_zone_activation(self, player):
        """Check if the player has moved into an unpopulated zone and activate it."""
        if not hasattr(self, '_last_zone_check'):
            self._last_zone_check = (player.x, player.y)

        dx = player.x - self._last_zone_check[0]
        dy = player.y - self._last_zone_check[1]
        if dx * dx + dy * dy < 200 * 200:  # check every 200 tiles of movement
            return

        self._last_zone_check = (player.x, player.y)

        # Preload chunks around the player
        if hasattr(self.world.tiles, 'preload_around'):
            self.world.tiles.preload_around(player.x, player.y, radius_chunks=2)

        # Update building interior tiles near player
        if hasattr(self.world, 'update_building_interiors_near'):
            self.world.update_building_interiors_near(player.x, player.y)

        # Activate NPCs and creatures in new zone
        self.activate_zone(player.x, player.y)

    def activate_zone(self, cx: float, cy: float, rng: random.Random = None):
        """Populate a zone around (cx, cy) that hasn't been populated yet.

        Called when the player moves into a new area of the chunked world.
        """
        if rng is None:
            rng = random.Random()

        if not hasattr(self, '_populated_settlements'):
            self._populated_settlements = set()

        zone_radius = 500
        spawn_data = getattr(self.world, 'npc_spawn_data', [])

        for spawn in spawn_data:
            sx, sy = spawn["x"], spawn["y"]
            if abs(sx - cx) > zone_radius or abs(sy - cy) > zone_radius:
                continue
            # Check if this settlement was already populated
            settlement_name = spawn.get("building", "")
            # Use position as key to avoid duplicates
            key = (int(sx), int(sy))
            if key in self._populated_settlements:
                continue
            self._populated_settlements.add(key)

            from game.data.dnd import random_npc_class_and_race
            char_class = spawn.get("class", "")
            race = spawn.get("race", "")
            if not char_class or not race:
                char_class, race = random_npc_class_and_race()

            name = spawn.get("name", f"NPC_{rng.randint(1000,9999)}")
            level = rng.randint(1, 5)
            profession = spawn.get("profession", "")
            if not profession:
                profession = self._pick_settlement_profession(
                    float(sx), float(sy), rng) or char_class
            npc = NPC(float(sx), float(sy), name, profession,
                     char_class=char_class, race=race, level=level)
            npc.home_x = float(sx)
            npc.home_y = float(sy)
            self.npcs.append(npc)

            # Generate backstory for newly activated NPCs so they have
            # memories, known_info, and personality from the start.
            try:
                from game.systems.backstory import generate_backstory
                from game.world.regions import get_region_at
                regions = getattr(self.world, 'regions', None)
                region_name = ""
                if regions:
                    region_name = get_region_at(int(sx), int(sy), regions) or ""
                generate_backstory(npc, self.world.structures, region_name)
            except Exception:
                pass  # backstory is nice-to-have, don't crash zone activation

        # Register newly-activated settlements in the trade and economy
        # systems so caravans can route to them.
        sim = getattr(self, '_simulation_ref', None)
        if sim is not None:
            known_settlements = set()
            for r in sim.trade.trade_routes:
                known_settlements.add(r[0])
                known_settlements.add(r[1])
            new_structures = []
            for s in self.world.structures:
                if s.kind not in ("village", "town", "city"):
                    continue
                if abs(s.x - cx) > zone_radius or abs(s.y - cy) > zone_radius:
                    continue
                if s.name not in known_settlements:
                    new_structures.append(s)
            if new_structures:
                sim.trade.register_new_settlements(new_structures)
            # Also register in economy system
            if hasattr(sim, 'economy'):
                for s in self.world.structures:
                    if s.kind in ("village", "town", "city", "hamlet", "castle"):
                        if abs(s.x - cx) <= zone_radius and abs(s.y - cy) <= zone_radius:
                            sim.economy.register_settlement(s.name, s.kind)

    # ------------------------------------------------------------------
    # Dormancy: NPC serialisation / deserialisation
    # ------------------------------------------------------------------

    def _serialise_npc(self, npc: NPC) -> Dict[str, Any]:
        """Snapshot a live NPC into a plain dict for dormant storage."""
        inv = []
        for it in npc.npc_inventory:
            inv.append({"name": it.name, "count": getattr(it, "count", 1)})

        return {
            "name": npc.name,
            "x": npc.x,
            "y": npc.y,
            "home_x": npc.home_x,
            "home_y": npc.home_y,
            "race": npc.race,
            "char_class": npc.char_class,
            "profession": npc.profession,
            "level": npc.level,
            "hp": npc.hp,
            "max_hp": npc.max_hp,
            "gold": npc.npc_gold,
            "inventory": inv,
            "memories": list(npc.memories),
            "known_info": list(npc.known_info),
            "needs": dict(npc.needs),
            "friendliness": npc.friendliness,
            "curiosity": npc.curiosity,
            "bravery": npc.bravery,
            "mood": npc.mood,
            "player_relationship": npc.player_relationship,
            "npc_relationships": dict(npc.npc_relationships),
            "friends": list(npc.friends),
            "enemies": list(npc.enemies),
            "faction": npc.faction,
            "title": npc.title,
            "alignment": npc.alignment,
            "social_class": npc.social_class,
            "dormant_since": _time.time(),
        }

    def _deserialise_npc(self, data: Dict[str, Any]) -> NPC:
        """Recreate a live NPC from a dormant snapshot."""
        npc = NPC(
            float(data["x"]), float(data["y"]),
            data["name"], data["profession"],
            char_class=data["char_class"],
            race=data["race"],
            level=data["level"],
        )
        npc.home_x = float(data["home_x"])
        npc.home_y = float(data["home_y"])
        npc.hp = data["hp"]
        npc.max_hp = data["max_hp"]
        npc.npc_gold = data["gold"]

        # Restore inventory
        npc.npc_inventory = []
        for it_data in data.get("inventory", []):
            it = make_item(it_data["name"])
            it.count = it_data.get("count", 1)
            npc.npc_inventory.append(it)

        # Restore personality & memories
        npc.memories = data.get("memories", [])
        npc.known_info = data.get("known_info", [])
        npc.needs = data.get("needs", npc.needs)
        npc.friendliness = data.get("friendliness", npc.friendliness)
        npc.curiosity = data.get("curiosity", npc.curiosity)
        npc.bravery = data.get("bravery", npc.bravery)
        npc.mood = data.get("mood", npc.mood)
        npc.player_relationship = data.get("player_relationship", 0)
        npc.npc_relationships = data.get("npc_relationships", {})
        npc.friends = data.get("friends", [])
        npc.enemies = data.get("enemies", [])
        npc.faction = data.get("faction", "")
        npc.title = data.get("title", "commoner")
        npc.alignment = data.get("alignment", "true neutral")
        npc.social_class = data.get("social_class", "freeman")
        return npc

    def _make_npc_dormant(self, npc: NPC):
        """Serialise an NPC, remove from live list, add to dormant list."""
        data = self._serialise_npc(npc)
        self._dormant_npcs.append(data)
        if npc in self.npcs:
            self.npcs.remove(npc)

    def _make_npc_live(self, data: Dict[str, Any], abstract_sim=None):
        """Recreate an NPC from dormant data, applying any abstract-sim changes."""
        # Let abstract_sim apply offline adventures before we materialise
        if abstract_sim is not None:
            elapsed_sec = _time.time() - data.get("dormant_since", _time.time())
            # Rough conversion: 1 real second = ~1 game day for dormant adventures
            days = max(0, int(elapsed_sec / 60))  # 1 real minute ≈ 1 game day
            if days > 0:
                rng = random.Random(hash(data["name"]) ^ int(elapsed_sec))
                abstract_sim.simulate_dormant_npc(data, days, rng)

        npc = self._deserialise_npc(data)
        self.npcs.append(npc)
        if data in self._dormant_npcs:
            self._dormant_npcs.remove(data)
        return npc

    # ------------------------------------------------------------------
    # Dormancy: Creature serialisation / deserialisation
    # ------------------------------------------------------------------

    def _is_important_creature(self, creature: Creature) -> bool:
        """Return True if a creature warrants dormancy tracking."""
        cr = getattr(creature, "cr", 0)
        domesticated = (hasattr(creature, "domestication")
                        and getattr(creature.domestication, "status", "") == "domesticated")
        return cr >= self.IMPORTANT_CREATURE_CR or domesticated

    def _serialise_creature(self, creature: Creature) -> Dict[str, Any]:
        """Snapshot an important creature for dormant storage."""
        return {
            "kind": creature.kind,
            "x": creature.x,
            "y": creature.y,
            "home_x": creature.home_x,
            "home_y": creature.home_y,
            "hp": creature.hp,
            "max_hp": creature.max_hp,
            "cr": getattr(creature, "cr", 0),
            "leash_range": creature.leash_range,
            "domestication_status": (
                getattr(creature.domestication, "status", "wild")
                if hasattr(creature, "domestication") else "wild"
            ),
            "domestication_trust": (
                getattr(creature.domestication, "trust", 0)
                if hasattr(creature, "domestication") else 0
            ),
            "dormant_since": _time.time(),
        }

    def _deserialise_creature(self, data: Dict[str, Any]) -> Creature:
        """Recreate an important creature from dormant data."""
        c = Creature(float(data["x"]), float(data["y"]), data["kind"])
        c.home_x = float(data["home_x"])
        c.home_y = float(data["home_y"])
        c.hp = data["hp"]
        c.max_hp = data["max_hp"]
        c.leash_range = data.get("leash_range", 15.0)
        # Restore domestication if applicable
        if hasattr(c, "domestication") and data.get("domestication_status", "wild") != "wild":
            c.domestication.status = data["domestication_status"]
            c.domestication.trust = data.get("domestication_trust", 0)
        return c

    def _make_creature_dormant(self, creature: Creature):
        """Serialise an important creature and remove from live list."""
        data = self._serialise_creature(creature)
        self._dormant_creatures.append(data)
        if creature in self.creatures:
            self.creatures.remove(creature)

    def _make_creature_live(self, data: Dict[str, Any]):
        """Recreate an important creature from dormant data."""
        creature = self._deserialise_creature(data)
        self.creatures.append(creature)
        if data in self._dormant_creatures:
            self._dormant_creatures.remove(data)
        return creature

    # ------------------------------------------------------------------
    # Main dormancy check (called from update)
    # ------------------------------------------------------------------

    def _check_npc_dormancy(self, player, abstract_sim=None):
        """Move distant NPCs to dormant state, activate nearby dormant NPCs.

        Uses hysteresis (ACTIVE_RADIUS < DORMANT_RADIUS) to prevent entities
        flickering between states when near the boundary.
        """
        px, py = player.x, player.y

        # --- Live NPCs that have moved too far -> dormant ---
        for npc in list(self.npcs):
            if not npc.alive:
                continue
            dx = npc.x - px
            dy = npc.y - py
            dist_sq = dx * dx + dy * dy
            if dist_sq > self.DORMANT_RADIUS * self.DORMANT_RADIUS:
                self._make_npc_dormant(npc)

        # --- Dormant NPCs that are now close -> live ---
        for dnpc in list(self._dormant_npcs):
            dx = dnpc["x"] - px
            dy = dnpc["y"] - py
            dist_sq = dx * dx + dy * dy
            if dist_sq < self.ACTIVE_RADIUS * self.ACTIVE_RADIUS:
                self._make_npc_live(dnpc, abstract_sim=abstract_sim)

    def _check_creature_dormancy(self, player):
        """Dormancy for important creatures; regular creatures just despawn."""
        px, py = player.x, player.y

        # --- Live creatures that are too far ---
        for creature in list(self.creatures):
            if not creature.alive:
                continue
            dx = creature.x - px
            dy = creature.y - py
            dist_sq = dx * dx + dy * dy
            if dist_sq > self.DORMANT_RADIUS * self.DORMANT_RADIUS:
                if self._is_important_creature(creature):
                    self._make_creature_dormant(creature)
                else:
                    # Regular creature — just remove; it will respawn naturally
                    self.creatures.remove(creature)

        # --- Dormant important creatures that are now close -> live ---
        for dc in list(self._dormant_creatures):
            dx = dc["x"] - px
            dy = dc["y"] - py
            dist_sq = dx * dx + dy * dy
            if dist_sq < self.ACTIVE_RADIUS * self.ACTIVE_RADIUS:
                self._make_creature_live(dc)

    # ------------------------------------------------------------------
    # Dormancy stats (for debugging / UI)
    # ------------------------------------------------------------------

    @property
    def dormant_npc_count(self) -> int:
        return len(self._dormant_npcs)

    @property
    def dormant_creature_count(self) -> int:
        return len(self._dormant_creatures)

    def get_dormant_npc_names(self) -> List[str]:
        """Return names of all dormant NPCs (for UI / debug)."""
        return [d["name"] for d in self._dormant_npcs]

    # ------------------------------------------------------------------
    # Update loop
    # ------------------------------------------------------------------

    def update(self, dt: float, player: Player, game_time: float):
        """Update all world entities."""
        # Zone activation for chunked worlds — populate new areas as player moves
        from game.world.world import ChunkedWorld
        if isinstance(self.world, ChunkedWorld):
            self._check_zone_activation(player)

        # --- Dormancy check (every DORMANCY_CHECK_TICKS ticks) ---
        self._dormancy_tick += 1
        if self._dormancy_tick >= self.DORMANCY_CHECK_TICKS:
            self._dormancy_tick = 0
            # Grab abstract_sim reference if the simulation layer has one
            abstract_sim = getattr(self, '_abstract_sim_ref', None)
            self._check_npc_dormancy(player, abstract_sim=abstract_sim)
            self._check_creature_dormancy(player)

        # Update creatures
        alive_creatures = []
        for creature in self.creatures:
            if creature.alive:
                creature.update(dt, self.world, player, self.creatures)
                alive_creatures.append(creature)
            else:
                creature.respawn_timer += dt
                if creature.respawn_timer >= creature.respawn_time:
                    # Respawn at home location
                    creature.x = creature.home_x
                    creature.y = creature.home_y
                    creature.hp = creature.max_hp
                    creature.alive = True
                    creature.state = "idle"
                    creature.respawn_timer = 0
                    alive_creatures.append(creature)
                else:
                    alive_creatures.append(creature)
        self.creatures = alive_creatures

        # Update NPCs
        for npc in self.npcs:
            npc.update(dt, self.world, game_time)

    def drop_items(self, x: float, y: float, items: List[Item]):
        """Drop items on the ground."""
        for item in items:
            offset_x = random.uniform(-0.3, 0.3)
            offset_y = random.uniform(-0.3, 0.3)
            self.ground_items.append((x + offset_x, y + offset_y, item))

    def pickup_nearby_items(self, player: Player) -> List[str]:
        """Pick up items near the player."""
        messages = []
        remaining = []
        for gx, gy, item in self.ground_items:
            dist = math.sqrt((player.x - gx)**2 + (player.y - gy)**2)
            if dist < 1.5:
                if player.add_item(item):
                    count_str = f" x{item.count}" if item.stackable and item.count > 1 else ""
                    messages.append(f"Picked up {item.name}{count_str}")
                else:
                    remaining.append((gx, gy, item))
                    messages.append("Inventory full!")
            else:
                remaining.append((gx, gy, item))
        self.ground_items = remaining
        return messages
