"""
Unified living system - all living entities (NPCs, creatures, animals) share
the same biological needs with race/species-specific parameters.

This module handles:
- Species-specific need decay rates (elves need less sleep, orcs eat more)
- Creature needs (hunger, thirst, rest) with hunting/foraging behavior
- Animal daily cycles (nocturnal vs diurnal)
- Intelligence tiers affecting decision complexity
- Den/nest/burrow creation for animals

Intelligence Tiers:
  0 = Mindless (zombies, oozes) - no needs, simple aggro
  1 = Animal (wolves, deer) - basic needs, instinct-driven
  2 = Low intelligence (goblins, kobolds) - needs + simple tool use
  3 = Intelligent (orcs, gnolls) - full needs, crafting, trading, farming
  4 = Highly intelligent (NPCs, dragons) - full simulation
"""

import random
import math
from typing import Dict, Optional


# Intelligence level by creature type
CREATURE_INTELLIGENCE = {
    # Mindless (0) - no needs
    "zombie": 0, "skeleton": 0, "shadow": 0, "ghoul": 0,
    # Animal (1) - basic needs
    "rat": 1, "wolf": 1, "bear": 1, "spider": 1, "boar": 1, "dire_wolf": 1,
    "deer": 1, "rabbit": 1, "chicken": 1, "cow": 1, "pig": 1, "sheep": 1,
    "goat": 1, "horse": 1, "elk": 1, "pheasant": 1, "fox": 1, "fish_school": 1,
    "wild_boar": 1, "giant_crab": 1, "owlbear": 1, "ankheg": 1,
    "harpy": 2, "werewolf": 2,
    # Low intelligence (2) - needs + basic planning
    "goblin": 2, "kobold": 2, "gnoll": 2, "bugbear": 2,
    # Intelligent (3) - full needs, can organize
    "orc": 3, "ogre": 3, "bandit": 3, "wight": 3, "gargoyle": 2,
    "minotaur": 2, "manticore": 2, "troll": 2,
    # Highly intelligent (4)
    "hill_giant": 3, "young_dragon": 4,
}

# Activity patterns
DIURNAL = "diurnal"     # active during day, sleeps at night (humans, most animals)
NOCTURNAL = "nocturnal"  # active at night, sleeps during day (wolves, owls, bats)
CREPUSCULAR = "crepuscular"  # active at dawn/dusk (deer, rabbits, foxes)
ALWAYS_ACTIVE = "always"  # undead, constructs

CREATURE_ACTIVITY = {
    "wolf": NOCTURNAL, "dire_wolf": NOCTURNAL, "fox": CREPUSCULAR,
    "owl": NOCTURNAL, "spider": NOCTURNAL, "bat": NOCTURNAL,
    "deer": CREPUSCULAR, "rabbit": CREPUSCULAR, "elk": CREPUSCULAR,
    "bear": DIURNAL, "boar": DIURNAL, "wild_boar": DIURNAL,
    "cow": DIURNAL, "pig": DIURNAL, "sheep": DIURNAL, "goat": DIURNAL,
    "horse": DIURNAL, "chicken": DIURNAL, "pheasant": DIURNAL,
    "goblin": NOCTURNAL, "kobold": NOCTURNAL,
    "orc": DIURNAL, "bandit": NOCTURNAL, "gnoll": NOCTURNAL,
    "zombie": ALWAYS_ACTIVE, "skeleton": ALWAYS_ACTIVE,
    "shadow": NOCTURNAL, "ghoul": NOCTURNAL, "wight": NOCTURNAL,
    "troll": NOCTURNAL, "ogre": DIURNAL,
}

# Need decay multipliers by species type
SPECIES_NEEDS = {
    # type: (hunger_mult, thirst_mult, rest_mult)
    "beast":       (1.2, 1.0, 1.0),   # animals eat more
    "humanoid":    (1.0, 1.0, 1.0),   # standard
    "undead":      (0.0, 0.0, 0.0),   # undead don't need anything
    "giant":       (2.0, 1.5, 0.8),   # giants eat a LOT
    "dragon":      (0.5, 0.3, 0.3),   # dragons are efficient
    "monstrosity": (1.0, 0.8, 0.8),
    "elemental":   (0.0, 0.0, 0.0),   # elementals don't need
    "shapechanger":(1.0, 1.0, 1.0),
}

# Race-specific need modifiers for NPCs
RACE_NEED_MODS = {
    "Human":    {"hunger": 1.0, "thirst": 1.0, "rest": 1.0},
    "Elf":      {"hunger": 0.7, "thirst": 0.8, "rest": 0.5},   # elves need less
    "Dwarf":    {"hunger": 1.2, "thirst": 1.3, "rest": 0.9},   # dwarves eat/drink more
    "Halfling": {"hunger": 1.3, "thirst": 1.0, "rest": 1.0},   # halflings love food
    "Half-Orc": {"hunger": 1.4, "thirst": 1.2, "rest": 0.8},   # orcs eat a lot, need less sleep
    "Gnome":    {"hunger": 0.8, "thirst": 0.9, "rest": 0.9},
    "Half-Elf": {"hunger": 0.9, "thirst": 0.9, "rest": 0.7},
    "Tiefling": {"hunger": 0.9, "thirst": 0.8, "rest": 1.0},
}


# Pack behavior - which creatures hunt together
PACK_HUNTERS = {
    # kind: (pack_radius, min_pack_size, max_pack_size, share_target)
    "wolf":      (15, 3, 6, True),   # wolves hunt in packs of 3-6
    "dire_wolf": (15, 2, 4, True),
    "goblin":    (12, 3, 8, True),   # goblins mob in groups
    "kobold":    (10, 4, 10, True),  # kobolds swarm
    "gnoll":     (12, 3, 5, True),   # gnoll war bands
    "orc":       (15, 3, 6, True),   # orc raiding parties
    "bandit":    (12, 2, 5, True),   # bandit gangs
    "bugbear":   (10, 2, 3, True),   # small bugbear groups
    "hyena":     (15, 3, 7, True),   # hyena packs
}


def update_pack_behavior(creatures: list, dt: float):
    """Update pack hunting - nearby pack members coordinate attacks.

    When one pack member finds prey, it alerts nearby packmates.
    Pack members converge on the same target and attack together.
    Pack bonus: +1 damage per packmate in range (flanking bonus).
    """
    # Group creatures by kind and proximity
    packs_formed = set()  # track which creatures already processed

    for creature in creatures:
        if not creature.alive or creature.kind not in PACK_HUNTERS:
            continue
        if id(creature) in packs_formed:
            continue

        pack_info = PACK_HUNTERS[creature.kind]
        pack_radius, min_size, max_size, share_target = pack_info

        # Find nearby packmates of same kind
        pack = [creature]
        for other in creatures:
            if (other is not creature and other.alive and
                other.kind == creature.kind and
                creature.dist_to(other) < pack_radius and
                len(pack) < max_size):
                pack.append(other)

        if len(pack) < min_size:
            continue  # not enough for a pack

        # Mark all as processed
        for member in pack:
            packs_formed.add(id(member))

        # Find the pack leader (highest HP)
        leader = max(pack, key=lambda c: c.hp)

        # If leader has a target, share it with the pack
        leader_target = getattr(leader, 'target', None)
        if leader_target and getattr(leader_target, 'alive', False):
            for member in pack:
                if member is not leader:
                    member.target = leader_target
                    if member.state in ("idle", "wandering", "sleeping"):
                        member.state = "chasing"

        # If any member is chasing, share that target
        elif any(m.state == "chasing" and getattr(m, 'target', None) for m in pack):
            chaser = next(m for m in pack if m.state == "chasing" and getattr(m, 'target', None))
            target = chaser.target
            for member in pack:
                if member is not chaser and member.state in ("idle", "wandering"):
                    member.target = target
                    member.state = "chasing"

        # Pack damage bonus: each packmate near the target adds +1 damage
        for member in pack:
            target = getattr(member, 'target', None)
            if target and getattr(target, 'alive', False):
                nearby_packmates = sum(1 for m in pack
                                       if m is not member and m.alive and
                                       m.dist_to(target) < 3)
                member.pack_bonus = nearby_packmates  # used in combat
            else:
                member.pack_bonus = 0


def update_flocking(creatures: list, dt: float, world):
    """Boids-style flocking with leader-following and terrain awareness.

    Three core rules (Craig Reynolds, 1986):
    1. Separation: avoid crowding packmates
    2. Alignment: steer toward average heading of pack
    3. Cohesion: move toward center of pack

    Enhanced with:
    - Leader following (pack leader sets direction)
    - Terrain avoidance (steer away from walls/water)
    - Independent action (break from flock when hunting/fleeing/sleeping)
    - Ambush positioning (use terrain to hide before attacking)
    """
    # Group creatures into flocks by kind and proximity
    processed = set()

    for creature in creatures:
        if not creature.alive or id(creature) in processed:
            continue
        # Skip creatures doing independent actions
        if creature.state in ("chasing", "attacking", "fleeing", "sleeping"):
            continue

        kind = creature.kind
        if kind not in PACK_HUNTERS:
            continue

        pack_info = PACK_HUNTERS[kind]
        pack_radius = pack_info[0]

        # Find flock members
        flock = [creature]
        for other in creatures:
            if (other is not creature and other.alive and
                other.kind == kind and id(other) not in processed and
                creature.dist_to(other) < pack_radius and
                other.state not in ("chasing", "attacking", "fleeing", "sleeping")):
                flock.append(other)
                if len(flock) >= pack_info[2]:
                    break

        if len(flock) < 2:
            continue

        for member in flock:
            processed.add(id(member))

        # Determine leader (highest HP, or one with a target)
        leader = max(flock, key=lambda c: c.hp + (50 if getattr(c, 'target', None) else 0))

        # Calculate flock center of mass
        cx = sum(m.x for m in flock) / len(flock)
        cy = sum(m.y for m in flock) / len(flock)

        # Calculate average heading
        avg_fx = sum(m.facing[0] for m in flock) / len(flock)
        avg_fy = sum(m.facing[1] for m in flock) / len(flock)

        for member in flock:
            if member is leader:
                # Leader moves independently (wander or toward target)
                if getattr(leader, 'target', None) and getattr(leader.target, 'alive', False):
                    continue  # leader is hunting, don't override
                continue

            # === BOIDS RULES ===
            sx, sy = member.x, member.y
            steer_x, steer_y = 0.0, 0.0

            # 1. SEPARATION - avoid crowding (strong force)
            for other in flock:
                if other is member:
                    continue
                dx = sx - other.x
                dy = sy - other.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 1.5 and dist > 0.01:
                    # Push away inversely proportional to distance
                    steer_x += (dx / dist) * 2.0
                    steer_y += (dy / dist) * 2.0

            # 2. ALIGNMENT - match pack heading (medium force)
            steer_x += avg_fx * 0.5
            steer_y += avg_fy * 0.5

            # 3. COHESION - move toward center (weak force)
            dx_center = cx - sx
            dy_center = cy - sy
            dist_center = math.sqrt(dx_center * dx_center + dy_center * dy_center)
            if dist_center > 2.0:
                steer_x += (dx_center / max(0.1, dist_center)) * 0.3
                steer_y += (dy_center / max(0.1, dist_center)) * 0.3

            # 4. LEADER FOLLOWING - steer toward leader (medium force)
            dx_leader = leader.x - sx
            dy_leader = leader.y - sy
            dist_leader = math.sqrt(dx_leader * dx_leader + dy_leader * dy_leader)
            if dist_leader > 3.0:
                steer_x += (dx_leader / max(0.1, dist_leader)) * 0.6
                steer_y += (dy_leader / max(0.1, dist_leader)) * 0.6

            # 5. TERRAIN AVOIDANCE - steer away from walls/water
            check_dist = 2
            ix, iy = int(sx), int(sy)
            for ddx in range(-check_dist, check_dist + 1):
                for ddy in range(-check_dist, check_dist + 1):
                    if ddx == 0 and ddy == 0:
                        continue
                    nx, ny = ix + ddx, iy + ddy
                    if 0 <= nx < world.width and 0 <= ny < world.height:
                        if not world.is_walkable(nx, ny):
                            d = math.sqrt(ddx * ddx + ddy * ddy)
                            if d > 0:
                                steer_x -= (ddx / d) * 1.5
                                steer_y -= (ddy / d) * 1.5

            # Normalize and apply steering
            mag = math.sqrt(steer_x * steer_x + steer_y * steer_y)
            if mag > 0.01:
                steer_x /= mag
                steer_y /= mag
                speed = member.speed * dt * 0.5  # slower when flocking
                new_x = sx + steer_x * speed
                new_y = sy + steer_y * speed
                if world.is_walkable(int(new_x), int(sy)):
                    member.x = new_x
                if world.is_walkable(int(sx), int(new_y)):
                    member.y = new_y
                member.facing = (steer_x, steer_y)
                member.state = "wandering"


# Herd animals - prey species that flock together for safety
HERD_ANIMALS = {
    # kind: (herd_radius, min_herd, max_herd, flee_speed_bonus)
    "deer":     (20, 3, 8,  1.3),   # deer herds, fast escape
    "elk":      (20, 3, 6,  1.2),
    "cow":      (15, 3, 10, 1.0),   # domestic herds, no speed bonus
    "sheep":    (12, 4, 12, 1.1),   # tight flocks
    "goat":     (12, 3, 8,  1.1),
    "horse":    (20, 3, 8,  1.4),   # fast herds
    "rabbit":   (8,  3, 6,  1.2),   # small warrens scatter then regroup
    "pig":      (10, 3, 6,  1.0),
    "pheasant": (10, 3, 8,  1.3),   # covey flight
    "chicken":  (8,  3, 6,  1.0),
    "fish_school": (10, 5, 15, 1.2), # tight schooling
}


def update_herding(creatures: list, dt: float, world, all_creatures: list):
    """Herding behavior for prey animals.

    Prey herds use flocking to stay together AND coordinate escape:
    1. Normal flocking (separation, alignment, cohesion) when grazing
    2. When ANY herd member spots a predator → entire herd flees together
    3. Herd flees AWAY from the predator as a group (not individually)
    4. Larger herds detect predators earlier (more eyes = safer)
    5. Speed bonus when fleeing as a herd (stampede effect)
    6. Stragglers at the edge are most vulnerable
    """
    processed = set()

    for creature in creatures:
        if not creature.alive or id(creature) in processed:
            continue
        if creature.kind not in HERD_ANIMALS:
            continue

        herd_info = HERD_ANIMALS[creature.kind]
        herd_radius, min_size, max_size, flee_bonus = herd_info

        # Find herd members
        herd = [creature]
        for other in creatures:
            if (other is not creature and other.alive and
                other.kind == creature.kind and
                id(other) not in processed and
                creature.dist_to(other) < herd_radius and
                len(herd) < max_size):
                herd.append(other)

        if len(herd) < 2:
            continue

        for m in herd:
            processed.add(id(m))

        # Herd center
        herd_cx = sum(m.x for m in herd) / len(herd)
        herd_cy = sum(m.y for m in herd) / len(herd)

        # THREAT DETECTION: scan for predators
        # Larger herds detect threats further away (more eyes)
        detection_range = 6 + len(herd) * 0.5
        nearest_threat = None
        nearest_threat_dist = detection_range

        for other in all_creatures:
            if other.kind == creature.kind or not other.alive:
                continue
            if getattr(other, 'passive', False):
                continue  # other prey aren't threats
            if other.kind in HERD_ANIMALS:
                continue  # other herd animals aren't threats

            # Check distance from herd center
            dx = other.x - herd_cx
            dy = other.y - herd_cy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < nearest_threat_dist:
                nearest_threat = other
                nearest_threat_dist = dist

        if nearest_threat is not None:
            # === HERD FLEE MODE ===
            # Calculate flee direction (away from predator, from herd center)
            flee_dx = herd_cx - nearest_threat.x
            flee_dy = herd_cy - nearest_threat.y
            flee_dist = math.sqrt(flee_dx * flee_dx + flee_dy * flee_dy)
            if flee_dist > 0.01:
                flee_nx = flee_dx / flee_dist
                flee_ny = flee_dy / flee_dist
            else:
                flee_nx = random.uniform(-1, 1)
                flee_ny = random.uniform(-1, 1)

            for member in herd:
                # Flee direction = away from predator + toward herd center
                mx = member.x
                my = member.y
                # Component 1: flee from predator
                steer_x = flee_nx * 2.0
                steer_y = flee_ny * 2.0

                # Component 2: stay with herd (cohesion during flee)
                dx_center = herd_cx - mx
                dy_center = herd_cy - my
                dist_center = math.sqrt(dx_center * dx_center + dy_center * dy_center)
                if dist_center > 3.0:
                    steer_x += (dx_center / max(0.1, dist_center)) * 0.8
                    steer_y += (dy_center / max(0.1, dist_center)) * 0.8

                # Component 3: separation (don't trample each other)
                for other in herd:
                    if other is member:
                        continue
                    odx = mx - other.x
                    ody = my - other.y
                    odist = math.sqrt(odx * odx + ody * ody)
                    if odist < 1.0 and odist > 0.01:
                        steer_x += (odx / odist) * 1.5
                        steer_y += (ody / odist) * 1.5

                # Apply with stampede speed bonus
                mag = math.sqrt(steer_x * steer_x + steer_y * steer_y)
                if mag > 0.01:
                    steer_x /= mag
                    steer_y /= mag
                    speed = member.speed * flee_bonus * dt
                    new_x = mx + steer_x * speed
                    new_y = my + steer_y * speed
                    if world.is_walkable(int(new_x), int(my)):
                        member.x = new_x
                    if world.is_walkable(int(mx), int(new_y)):
                        member.y = new_y
                    member.facing = (steer_x, steer_y)
                    member.state = "fleeing"

        else:
            # === PEACEFUL GRAZING FLOCK ===
            avg_fx = sum(m.facing[0] for m in herd) / len(herd)
            avg_fy = sum(m.facing[1] for m in herd) / len(herd)

            for member in herd:
                if member.state in ("sleeping",):
                    continue

                mx, my = member.x, member.y
                steer_x, steer_y = 0.0, 0.0

                # Separation
                for other in herd:
                    if other is member:
                        continue
                    dx = mx - other.x
                    dy = my - other.y
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < 1.2 and dist > 0.01:
                        steer_x += (dx / dist) * 1.5
                        steer_y += (dy / dist) * 1.5

                # Alignment (gentle)
                steer_x += avg_fx * 0.3
                steer_y += avg_fy * 0.3

                # Cohesion (gentle)
                dx_c = herd_cx - mx
                dy_c = herd_cy - my
                dist_c = math.sqrt(dx_c * dx_c + dy_c * dy_c)
                if dist_c > 2.5:
                    steer_x += (dx_c / max(0.1, dist_c)) * 0.4
                    steer_y += (dy_c / max(0.1, dist_c)) * 0.4

                # Gentle random wander
                steer_x += random.uniform(-0.2, 0.2)
                steer_y += random.uniform(-0.2, 0.2)

                # Terrain avoidance
                ix, iy = int(mx), int(my)
                for ddx in (-1, 0, 1):
                    for ddy in (-1, 0, 1):
                        if ddx == 0 and ddy == 0:
                            continue
                        nx, ny = ix + ddx, iy + ddy
                        if 0 <= nx < world.width and 0 <= ny < world.height:
                            if not world.is_walkable(nx, ny):
                                steer_x -= ddx * 1.0
                                steer_y -= ddy * 1.0

                mag = math.sqrt(steer_x * steer_x + steer_y * steer_y)
                if mag > 0.01:
                    steer_x /= mag
                    steer_y /= mag
                    speed = member.speed * dt * 0.3  # slow grazing speed
                    new_x = mx + steer_x * speed
                    new_y = my + steer_y * speed
                    if world.is_walkable(int(new_x), int(my)):
                        member.x = new_x
                    if world.is_walkable(int(mx), int(new_y)):
                        member.y = new_y
                    member.facing = (steer_x, steer_y)
                    member.state = "wandering"


def initialize_creature_needs(creature):
    """Give a creature biological needs based on its type and intelligence."""
    kind = creature.kind
    intel = CREATURE_INTELLIGENCE.get(kind, 1)
    monster_type = getattr(creature, 'monster_type', 'beast')
    h_mult, t_mult, r_mult = SPECIES_NEEDS.get(monster_type, (1.0, 1.0, 1.0))

    creature.intelligence = intel
    creature.activity_pattern = CREATURE_ACTIVITY.get(kind, DIURNAL)

    # Only give needs to living creatures (not undead/elementals)
    if intel >= 1 and h_mult > 0:
        creature.needs = {
            "hunger": random.uniform(60, 90),
            "thirst": random.uniform(60, 90),
            "rest": random.uniform(50, 80),
        }
        creature.need_multipliers = {"hunger": h_mult, "thirst": t_mult, "rest": r_mult}
    else:
        creature.needs = {"hunger": 100, "thirst": 100, "rest": 100}
        creature.need_multipliers = {"hunger": 0, "thirst": 0, "rest": 0}

    # Den location (animals create a home base)
    creature.den_x = creature.home_x
    creature.den_y = creature.home_y


def update_creature_needs(creature, dt: float, time_normalized: float, world, creatures_list):
    """Update creature needs and drive survival behavior."""
    if not creature.alive:
        return

    intel = getattr(creature, 'intelligence', 1)
    if intel == 0:
        return  # mindless - no needs

    needs = getattr(creature, 'needs', None)
    if not needs:
        return

    mults = getattr(creature, 'need_multipliers', {"hunger": 1, "thirst": 1, "rest": 1})

    # Decay needs
    from game.settings import NEED_DECAY
    needs["hunger"] = max(0, needs["hunger"] - NEED_DECAY["hunger"] * dt * mults["hunger"])
    needs["thirst"] = max(0, needs["thirst"] - NEED_DECAY["thirst"] * dt * mults["thirst"])

    # Rest: depends on activity pattern and time of day
    pattern = getattr(creature, 'activity_pattern', DIURNAL)
    should_sleep = _should_sleep(pattern, time_normalized)

    if should_sleep and creature.state != "chasing" and creature.state != "attacking":
        # Sleep time - rest recovers, creature goes to den
        needs["rest"] = min(100, needs["rest"] + 0.8 * dt)
        if creature.state != "sleeping":
            creature.state = "sleeping"
            # Move toward den
            den_x = getattr(creature, 'den_x', creature.home_x)
            den_y = getattr(creature, 'den_y', creature.home_y)
            if creature.dist_to_pos(den_x, den_y) > 3:
                _move_toward(creature, den_x, den_y, dt * 0.5, world)
    else:
        needs["rest"] = max(0, needs["rest"] - NEED_DECAY["rest"] * dt * mults["rest"])

    # Hunger response
    if needs["hunger"] < 30:
        _creature_seek_food(creature, dt, world, creatures_list, intel)

    # Thirst response
    if needs["thirst"] < 30:
        from game.settings import WATER
        water = world.find_water_near(int(creature.x), int(creature.y), 15)
        if water:
            _move_toward(creature, float(water[0]), float(water[1]), dt, world)
            if creature.dist_to_pos(float(water[0]), float(water[1])) < 2:
                needs["thirst"] = min(100, needs["thirst"] + 30)

    # Exhaustion collapse
    if needs["rest"] <= 0 and creature.state != "sleeping":
        creature.state = "sleeping"

    # Starvation damage
    if needs["hunger"] <= 0:
        creature.hp -= 0.3 * dt
        if creature.hp <= 0:
            creature.alive = False


def _should_sleep(pattern: str, time_norm: float) -> bool:
    """Check if creature should be sleeping based on activity pattern."""
    if pattern == ALWAYS_ACTIVE:
        return False
    elif pattern == DIURNAL:
        return time_norm > 0.78 or time_norm < 0.22  # sleep at night
    elif pattern == NOCTURNAL:
        return 0.25 < time_norm < 0.72  # sleep during day
    elif pattern == CREPUSCULAR:
        return (0.35 < time_norm < 0.65) or time_norm > 0.85  # sleep midday and late night
    return False


def _creature_seek_food(creature, dt, world, creatures_list, intel):
    """Creature tries to find food based on intelligence."""
    kind = creature.kind
    passive = getattr(creature, 'passive', False)

    if passive:
        # Herbivores: eat grass, berries, herbs
        from game.settings import GRASS, HERB_PATCH, BERRY_BUSH, FARMLAND
        food_tile = world.find_nearest_tile(int(creature.x), int(creature.y),
                                            {HERB_PATCH, BERRY_BUSH, FARMLAND}, 10)
        if food_tile:
            _move_toward(creature, float(food_tile[0]), float(food_tile[1]), dt, world)
            if creature.dist_to_pos(float(food_tile[0]), float(food_tile[1])) < 2:
                creature.needs["hunger"] = min(100, creature.needs["hunger"] + 25)
        else:
            # Graze on grass
            creature.needs["hunger"] = min(100, creature.needs["hunger"] + 5 * dt)
    else:
        # Predators: hunt other creatures or seek food
        if intel >= 2:
            # Intelligent predators might hunt passives
            for other in creatures_list:
                if (other is not creature and other.alive and
                    getattr(other, 'passive', False) and
                    creature.dist_to(other) < 8):
                    # Chase prey
                    creature.state = "chasing"
                    creature.target = other
                    _move_toward(creature, other.x, other.y, dt, world)
                    if creature.dist_to(other) < 1.5:
                        from game.systems.combat import CombatSystem
                        # Pass nearby creatures so pack hunters get their bonus
                        CombatSystem.creature_combat_tick(
                            creature, other, dt,
                            nearby_allies=creatures_list,
                        )
                        if not other.alive:
                            creature.needs["hunger"] = min(100, creature.needs["hunger"] + 40)
                            creature.state = "idle"
                    return
        # Fallback: scavenge
        creature.needs["hunger"] = min(100, creature.needs["hunger"] + 2 * dt)


def _move_toward(creature, tx, ty, dt, world):
    """Move creature toward target."""
    dx = tx - creature.x
    dy = ty - creature.y
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 0.3:
        return
    nx, ny = dx / dist, dy / dist
    speed = creature.speed * dt
    new_x = creature.x + nx * speed
    new_y = creature.y + ny * speed
    if world.is_walkable(int(new_x), int(creature.y)):
        creature.x = new_x
    if world.is_walkable(int(creature.x), int(new_y)):
        creature.y = new_y
    creature.facing = (nx, ny)
