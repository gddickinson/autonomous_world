"""Dynamic events — discovery and disaster handlers (mixin).

Split from dynamic_events.py for file-size compliance.
The DynamicEventsSystem inherits from this mixin.
"""

import random
from typing import List

from game.systems.dynamic_events_helpers import (
    DynamicEvent, _distance_to, _destroy_tiles,
)


class DynamicEventsWorldMixin:
    """Discovery and disaster event handlers for DynamicEventsSystem."""

    # ------------------------------------------------------------------
    # DISCOVERY EVENTS
    # ------------------------------------------------------------------

    def _fire_discovery(self, game_day, governance, world, npcs, military):
        """Fire one of: artifact found, resource deposit, lost map."""
        roll = random.random()
        if roll < 0.40:
            self._artifact_found(game_day, npcs, world)
        elif roll < 0.75:
            self._resource_deposit(game_day, npcs, world)
        else:
            self._lost_map(game_day, npcs, world)

    def _artifact_found(self, game_day, npcs, world):
        """A farmer or miner discovers an ancient artifact."""
        finders = [n for n in npcs if n.alive
                   and getattr(n, 'profession', '') in
                   ("Farmer", "Miner", "Hunter", "Woodcutter", "Scholar")]
        if not finders:
            finders = [n for n in npcs if n.alive]
        if not finders:
            return
        finder = random.choice(finders)
        artifacts = [
            "a glowing crystal of unknown origin",
            "an ancient runestone with elven inscriptions",
            "a golden amulet bearing a dragon crest",
            "a sealed scroll from the Age of Legends",
            "a dwarven mechanism of intricate design",
            "a shard of dark obsidian pulsing with energy",
        ]
        artifact = random.choice(artifacts)
        finder.known_info.append(f"I found {artifact}!")
        finder.add_memory("event", f"Found {artifact}", 4)

        # Generate a quest for this NPC if they don't have one
        if hasattr(finder, 'quest') and not getattr(finder, 'quest', None):
            from game.systems.quests import Quest
            quest = Quest(
                title=f"Investigate {artifact}",
                description=f"{finder.name} found {artifact}. "
                            f"Investigate its origins.",
                kind="investigate",
                target="artifact", target_count=1,
                reward_gold=random.randint(30, 80),
                reward_xp=40,
                difficulty="medium",
            )
            finder.quest = quest

        desc = (f"DISCOVERY: {finder.name} the {finder.profession} "
                f"found {artifact} while working!")
        evt = DynamicEvent("discovery", "Ancient Artifact", desc,
                           {"finder": finder.name, "artifact": artifact},
                           game_day=game_day)
        self._register_event(evt, npcs)
        self.event_log.append(f"STORY: {desc}")

    def _resource_deposit(self, game_day, npcs, world):
        """A new resource deposit is discovered near a settlement."""
        structures = [s for s in world.structures
                      if s.kind in ("village", "town", "city", "hamlet")]
        if not structures:
            return
        settlement = random.choice(structures)
        resources = ["iron ore", "copper veins", "coal seam",
                     "clay deposit", "gemstone pocket", "marble quarry"]
        resource = random.choice(resources)

        # Boost mining/economy for nearby NPCs
        for n in npcs:
            if n.alive and _distance_to(n, settlement.x, settlement.y) < 30:
                n.known_info.append(
                    f"New {resource} found near {settlement.name}!")
                skills = getattr(n, 'npc_skills', {})
                if "mining" in skills:
                    skills["mining"] = min(100, skills["mining"] + 5)

        desc = (f"DISCOVERY: A {resource} was found near "
                f"{settlement.name}! Mining prospects improve.")
        evt = DynamicEvent("discovery", "Resource Deposit", desc,
                           {"resource": resource,
                            "settlement": settlement.name},
                           settlement_name=settlement.name,
                           game_day=game_day)
        self._register_event(evt, npcs)
        self.event_log.append(f"STORY: {desc}")

    def _lost_map(self, game_day, npcs, world):
        """A scholar finds a treasure map pointing to a dungeon."""
        scholars = [n for n in npcs if n.alive
                    and getattr(n, 'profession', '') in
                    ("Scholar", "Wizard", "Bard")]
        if not scholars:
            scholars = [n for n in npcs if n.alive]
        if not scholars:
            return
        finder = random.choice(scholars)
        locations = [
            "the Crypt of Forgotten Kings",
            "a buried temple in the eastern hills",
            "the Sunken Vaults beneath the river",
            "an abandoned dwarven mine shaft",
            "the Cavern of Whispers",
        ]
        location = random.choice(locations)
        finder.known_info.append(f"Found a map to {location}!")
        finder.add_memory("event",
                          f"Found a treasure map to {location}", 4)

        # Generate quest
        if hasattr(finder, 'quest') and not getattr(finder, 'quest', None):
            from game.systems.quests import Quest
            quest = Quest(
                title=f"Explore {location}",
                description=f"A map leads to {location}. "
                            f"Explore it and claim the treasure.",
                kind="investigate",
                target="dungeon", target_count=1,
                reward_gold=random.randint(50, 120),
                reward_xp=60,
                difficulty="hard",
            )
            finder.quest = quest

        desc = (f"DISCOVERY: {finder.name} the {finder.profession} found "
                f"a treasure map leading to {location}!")
        evt = DynamicEvent("discovery", "Lost Treasure Map", desc,
                           {"finder": finder.name, "location": location},
                           game_day=game_day)
        self._register_event(evt, npcs)
        self.event_log.append(f"STORY: {desc}")

    # ------------------------------------------------------------------
    # DISASTER EVENTS
    # ------------------------------------------------------------------

    def _fire_disaster(self, game_day, governance, world, npcs, military):
        """Fire one of: drought, plague, fire, flood."""
        roll = random.random()
        if roll < 0.30:
            self._drought(game_day, governance, world, npcs)
        elif roll < 0.55:
            self._plague(game_day, world, npcs)
        elif roll < 0.80:
            self._fire(game_day, world, npcs)
        else:
            self._flood(game_day, world, npcs)

    def _drought(self, game_day, governance, world, npcs):
        """Crop yields halved for 30 days. Food stockpile drains faster."""
        structures = [s for s in world.structures
                      if s.kind in ("village", "town", "city", "hamlet")]
        if not structures:
            return
        settlement = random.choice(structures)
        sx, sy = float(settlement.x), float(settlement.y)
        affected = 0

        for n in npcs:
            if n.alive and _distance_to(n, sx, sy) < 50:
                affected += 1
                n.known_info.append(
                    f"Drought hits {settlement.name}!")
                needs = getattr(n, 'needs', {})
                if "hunger" in needs:
                    needs["hunger"] = max(0, needs["hunger"] - 20)
                if "thirst" in needs:
                    needs["thirst"] = max(0, needs["thirst"] - 25)
                n.add_memory("event", "Suffering through a drought", 3)

        # Destroy some farmland tiles
        _destroy_tiles(world, sx, sy, 40, tile_type=11, count=8,
                       replace_with=2)  # FARMLAND -> GRASS

        # Kingdom morale hit
        kname = ""
        if governance:
            kname = governance.get_kingdom_at(sx, sy) or ""
            if kname:
                k = governance.kingdoms.get(kname)
                if k:
                    k.public_morale = max(0, k.public_morale - 10)

        desc = (f"DROUGHT strikes {settlement.name}! Crops wither. "
                f"{affected} people affected. Farmland damaged.")
        evt = DynamicEvent("disaster", "Drought", desc,
                           {"affected": affected, "duration_days": 30},
                           settlement_name=settlement.name,
                           kingdom_name=kname,
                           duration_days=30, game_day=game_day)
        self._register_event(evt, npcs)
        self.event_log.append(f"STORY: {desc}")

    def _plague(self, game_day, world, npcs):
        """10-20% of NPCs in a settlement get sick. Some may die."""
        structures = [s for s in world.structures
                      if s.kind in ("village", "town", "city")]
        if not structures:
            return
        settlement = random.choice(structures)
        sx, sy = float(settlement.x), float(settlement.y)

        nearby = [n for n in npcs if n.alive
                  and _distance_to(n, sx, sy) < 40]
        if not nearby:
            return
        sick_rate = random.uniform(0.10, 0.20)
        sick_count = max(1, int(len(nearby) * sick_rate))
        sick_npcs = random.sample(nearby, min(sick_count, len(nearby)))

        deaths = 0
        for n in sick_npcs:
            n.known_info.append(f"Plague in {settlement.name}!")
            n.add_memory("event", "Fell ill during the plague", 4)
            # 15% chance of death for each sick NPC
            if random.random() < 0.15:
                n.hp = 0
                n.alive = False
                deaths += 1
            else:
                n.hp = max(1, n.hp - random.randint(10, 30))
                needs = getattr(n, 'needs', {})
                if "rest" in needs:
                    needs["rest"] = max(0, needs["rest"] - 30)

        desc = (f"PLAGUE in {settlement.name}! {len(sick_npcs)} fell ill, "
                f"{deaths} died. The settlement mourns.")
        evt = DynamicEvent("disaster", "Plague", desc,
                           {"sick": len(sick_npcs), "deaths": deaths},
                           settlement_name=settlement.name,
                           duration_days=20, game_day=game_day)
        self._register_event(evt, npcs)
        self.event_log.append(f"STORY: {desc}")

    def _fire(self, game_day, world, npcs):
        """A building catches fire and is destroyed. Adjacent at risk."""
        from game.settings import BUILT_WALL, BUILT_FLOOR, GRASS
        structures = [s for s in world.structures
                      if s.kind in ("village", "town", "city")]
        if not structures:
            return
        settlement = random.choice(structures)
        sx, sy = float(settlement.x), float(settlement.y)

        # Destroy built tiles in a small area (simulating a building fire)
        destroyed = _destroy_tiles(world, sx, sy, radius=15,
                                   tile_type=BUILT_WALL, count=12,
                                   replace_with=GRASS)
        destroyed += _destroy_tiles(world, sx, sy, radius=15,
                                    tile_type=BUILT_FLOOR, count=8,
                                    replace_with=GRASS)

        # Notify nearby NPCs
        for n in npcs:
            if n.alive and _distance_to(n, sx, sy) < 30:
                n.known_info.append(
                    f"Fire destroyed buildings in {settlement.name}!")
                n.add_memory("event", "Witnessed a terrible fire", 3)
                if hasattr(n, 'emotion_state'):
                    n.emotion_state.apply_emotion("fear", 0.3)

        desc = (f"FIRE in {settlement.name}! {destroyed} structures "
                f"burned down. Rebuilding will take time.")
        evt = DynamicEvent("disaster", "Fire", desc,
                           {"destroyed_tiles": destroyed},
                           settlement_name=settlement.name,
                           game_day=game_day)
        self._register_event(evt, npcs)
        self.event_log.append(f"STORY: {desc}")

    def _flood(self, game_day, world, npcs):
        """River settlement loses farmland near water."""
        from game.settings import FARMLAND, SHALLOW_WATER
        structures = [s for s in world.structures
                      if s.kind in ("village", "town", "city", "hamlet")]
        if not structures:
            return
        settlement = random.choice(structures)
        sx, sy = float(settlement.x), float(settlement.y)

        # Convert farmland near water to shallow water
        flooded = 0
        radius = 35
        for _ in range(20):
            rx = int(sx + random.uniform(-radius, radius))
            ry = int(sy + random.uniform(-radius, radius))
            if (0 <= rx < world.width and 0 <= ry < world.height):
                tile = world.tiles[ry][rx]
                if tile == FARMLAND:
                    world.modify_tile(rx, ry, SHALLOW_WATER)
                    flooded += 1

        # Notify NPCs
        for n in npcs:
            if n.alive and _distance_to(n, sx, sy) < 40:
                n.known_info.append(
                    f"Floods near {settlement.name}!")
                n.add_memory("event", "Floods destroyed farmland", 3)
                needs = getattr(n, 'needs', {})
                if "hunger" in needs:
                    needs["hunger"] = max(0, needs["hunger"] - 15)

        desc = (f"FLOOD near {settlement.name}! {flooded} farmland tiles "
                f"submerged. Food production disrupted.")
        evt = DynamicEvent("disaster", "Flood", desc,
                           {"flooded_tiles": flooded},
                           settlement_name=settlement.name,
                           game_day=game_day)
        self._register_event(evt, npcs)
        self.event_log.append(f"STORY: {desc}")
