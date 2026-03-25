"""Divine event triggers and kingdom commands -- helper for divine_commands.py.

Contains the event trigger functions, kingdom manipulation functions,
and spawn helpers used by DivineCommands.
"""

import random
import math
from typing import Optional

from game.settings import CREATURE_TYPES


def notify(game, text, color):
    notes = getattr(game, 'notifications', None)
    if notes:
        notes.add(text, 3.0, color)


def chronicle(game, text, category="miracle"):
    chron = getattr(game, 'chronicles', None)
    if chron and hasattr(chron, 'add_entry'):
        day = getattr(getattr(game, 'time_sys', None), 'day', 0)
        chron.add_entry(text, category, day)


def get_governance(game):
    sim = getattr(game, 'simulation', None)
    return getattr(sim, 'governance', None) if sim else None


def get_npcs(game):
    wm = getattr(game, 'world_mgr', None)
    return getattr(wm, 'npcs', []) if wm else []


def get_selected_settlement(game):
    """Find a selected settlement from god_ui or nearest to player."""
    god_ui = getattr(game, 'god_ui', None)
    if god_ui:
        sname = getattr(god_ui, 'selected_settlement_name', None)
        if sname:
            world = getattr(game, 'world', None)
            if world:
                for s in getattr(world, 'structures', []):
                    if getattr(s, 'name', '') == sname:
                        return s
    player = getattr(game, 'player', None)
    world = getattr(game, 'world', None)
    if player and world:
        best, best_d = None, 9999
        for s in getattr(world, 'structures', []):
            d = math.hypot(s.x - player.x, s.y - player.y)
            if d < best_d:
                best, best_d = s, d
        return best
    return None


def sett_pos(settlement, game):
    """Get (x, y, radius) for a settlement or player position."""
    if settlement:
        return (getattr(settlement, 'x', 0), getattr(settlement, 'y', 0),
                getattr(settlement, 'radius', 30))
    player = getattr(game, 'player', None)
    return (player.x, player.y, 30) if player else (0, 0, 30)


def add_world_event(game, name, desc, x, y, radius, duration, effects):
    sim = getattr(game, 'simulation', None)
    if not sim:
        return
    from game.systems.sim_events import WorldEvent
    day = getattr(getattr(game, 'time_sys', None), 'day', 0)
    evt = WorldEvent(name, desc, x, y, radius, duration, effects, day)
    sim.events.append(evt)
    sim.event_log.append(f"[Divine] {name}: {desc}")


# ================================================================
# EVENT TRIGGERS
# ================================================================

def trigger_drought(sett, game):
    x, y, r = sett_pos(sett, game)
    add_world_event(game, "Drought", "Divine drought scorches the land.",
                    x, y, r, 120.0, {"thirst_mult": 2.0})
    notify(game, "Drought strikes!", (220, 140, 40))


def trigger_plague(sett, game):
    x, y, r = sett_pos(sett, game)
    add_world_event(game, "Plague", "A divine plague sweeps through.",
                    x, y, r, 80.0, {"plague_dps": 0.5})
    notify(game, "Plague unleashed!", (220, 80, 60))


def trigger_festival(sett, game):
    x, y, r = sett_pos(sett, game)
    add_world_event(game, "Festival", "The gods decree a grand festival!",
                    x, y, r, 60.0, {"social_boost": 1.0})
    notify(game, "Festival decreed!", (80, 200, 120))


def trigger_monster_wave(sett, game):
    x, y, _ = sett_pos(sett, game)
    wm = getattr(game, 'world_mgr', None)
    if wm:
        from game.core.creature import Creature
        hostile = [ct for ct in CREATURE_TYPES
                   if CREATURE_TYPES[ct].get("hostile", False)]
        if not hostile:
            hostile = list(CREATURE_TYPES.keys())[:3]
        for _ in range(10):
            kind = random.choice(hostile)
            cr = Creature(kind, x + random.uniform(-8, 8),
                          y + random.uniform(-8, 8))
            cr.hostile = True
            wm.creatures.append(cr)
    notify(game, "A wave of monsters descends!", (255, 80, 80))
    chronicle(game, "The gods unleashed a monster wave.", "disaster")


def trigger_gold_rain(sett, game):
    gov = get_governance(game)
    dashboard = getattr(game, 'god_dashboard', None)
    kname = getattr(dashboard, 'selected_kingdom', None) if dashboard else None
    if gov and kname and kname in gov.kingdoms:
        gov.kingdoms[kname].treasury += 500
        notify(game, f"500 gold rained upon {kname}!", (255, 220, 80))
        chronicle(game, f"Divine gold rained upon {kname}.", "miracle")
    else:
        notify(game, "Select a kingdom first (TAB).", (200, 200, 100))


def trigger_famine(sett, game):
    x, y, r = sett_pos(sett, game)
    add_world_event(game, "Famine", "The gods decree famine.",
                    x, y, r, 100.0, {"hunger_mult": 2.0})
    gov = get_governance(game)
    if gov:
        for kn, k in gov.kingdoms.items():
            if k.contains(x, y):
                k.treasury = max(0, k.treasury - k.treasury // 4)
                break
    notify(game, "Famine strikes!", (220, 140, 40))


def trigger_inspiration(sett, game, effects_list):
    x, y, _ = sett_pos(sett, game)
    from game.systems.divine_commands import DivineEffect
    effects_list.append(DivineEffect(x, y, "DIVINE INSPIRATION",
                                     (200, 220, 255), 3.0))
    count = 0
    for npc in get_npcs(game):
        if not getattr(npc, 'alive', False):
            continue
        if (npc.x - x) ** 2 + (npc.y - y) ** 2 < 900:
            if hasattr(npc, 'morale'):
                npc.morale = min(100, getattr(npc, 'morale', 50) + 10)
            count += 1
    notify(game, f"Divine inspiration! {count} NPCs inspired.", (200, 220, 255))


def trigger_earthquake(sett, game, effects_list):
    x, y, r = sett_pos(sett, game)
    from game.systems.divine_commands import DivineEffect
    effects_list.append(DivineEffect(x, y, "EARTHQUAKE",
                                     (180, 100, 50), 2.0, flash=True))
    add_world_event(game, "Earthquake", "The earth shakes by divine command!",
                    x, y, max(r, 30), 10.0, {"destroy_chance": 0.3})
    notify(game, "Earthquake!", (180, 100, 50))
    chronicle(game, "The gods shook the earth.", "disaster")


# ================================================================
# KINGDOM COMMANDS
# ================================================================

def kingdom_declare_war(attacker, defender, game):
    gov = get_governance(game)
    if not gov:
        return
    from game.systems.governance import DiplomaticRelation
    key = tuple(sorted([attacker, defender]))
    if key not in gov.diplomacy:
        gov.diplomacy[key] = DiplomaticRelation()
    gov.diplomacy[key].status = 5
    gov.diplomacy[key].trust = -80
    notify(game, f"{attacker} declares war on {defender}!", (255, 60, 60))
    chronicle(game, f"By divine decree, {attacker} declared war on {defender}.", "war")


def kingdom_peace(kname, game):
    gov = get_governance(game)
    if not gov:
        return
    ended = 0
    for (k1, k2), rel in gov.diplomacy.items():
        if kname in (k1, k2) and getattr(rel, 'status', 0) == 5:
            rel.status = 2
            rel.trust = 0
            rel.war_exhaustion = 0
            other = k2 if k1 == kname else k1
            chronicle(game, f"Gods enforced peace between {kname} and {other}.", "peace")
            ended += 1
    notify(game, f"Peace enforced for {kname} ({ended} wars ended).", (100, 220, 100))


def kingdom_recruit(kname, game):
    gov = get_governance(game)
    if not gov or kname not in gov.kingdoms:
        return
    k = gov.kingdoms[kname]
    cost = min(k.treasury, 200)
    soldiers = cost // 5
    k.treasury -= cost
    k.army_size += soldiers
    notify(game, f"{kname} recruited {soldiers} soldiers ({cost}g).", (180, 180, 220))


def kingdom_fortify(kname, game):
    gov = get_governance(game)
    if not gov or kname not in gov.kingdoms:
        return
    k = gov.kingdoms[kname]
    cost = min(k.treasury, 300)
    k.treasury -= cost
    notify(game, f"{kname} built fortifications ({cost}g).", (80, 130, 220))
    chronicle(game, f"{kname} erected divine fortifications.", "construction")


def kingdom_boost_economy(kname, game):
    gov = get_governance(game)
    if not gov or kname not in gov.kingdoms:
        return
    k = gov.kingdoms[kname]
    k.treasury += 200
    k.income_per_day = getattr(k, 'income_per_day', 0) + 5
    notify(game, f"{kname} economy boosted (+200g, +5/day).", (200, 180, 80))


def kingdom_change_gov(kname, style, game):
    gov = get_governance(game)
    if not gov or kname not in gov.kingdoms:
        return
    gov.kingdoms[kname].governing_style = style
    notify(game, f"{kname} now governed by {style}!", (180, 140, 200))
    chronicle(game, f"Gods changed {kname}'s governance to {style}.", "political")


# ================================================================
# SPAWN HELPERS
# ================================================================

def spawn_creature(game):
    player = getattr(game, 'player', None)
    wm = getattr(game, 'world_mgr', None)
    if not player or not wm:
        return
    from game.core.creature import Creature
    kind = random.choice(list(CREATURE_TYPES.keys()))
    cx = player.x + random.uniform(-5, 5)
    cy = player.y + random.uniform(-5, 5)
    wm.creatures.append(Creature(kind, cx, cy))
    notify(game, f"Spawned {kind}", (180, 180, 255))


def spawn_npc(game):
    player = getattr(game, 'player', None)
    wm = getattr(game, 'world_mgr', None)
    if not player or not wm:
        return
    from game.core.npc import NPC
    from game.settings import NPC_NAMES
    name = random.choice(NPC_NAMES) if NPC_NAMES else "Divine Servant"
    npc = NPC(name, player.x + random.uniform(-3, 3),
              player.y + random.uniform(-3, 3))
    npc.profession = random.choice(
        ["guard", "farmer", "merchant", "blacksmith", "priest",
         "miner", "hunter", "scholar"])
    wm.npcs.append(npc)
    notify(game, f"Spawned {name} the {npc.profession}", (180, 220, 180))
