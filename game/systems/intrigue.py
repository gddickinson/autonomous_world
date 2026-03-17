"""
Political Intrigue — NPC power struggles, alliances, betrayals, and coups.

Ambitious NPCs don't just follow orders — they scheme for power:
- Nobles plot to seize the throne when the ruler is weak
- Military commanders build power bases for coups
- Spymasters gather intelligence and blackmail rivals
- Alliances form and shatter based on self-interest
- Assassinations, poisonings, and frame-ups
- Civil wars when pretenders challenge rulers

Alignment and personality drive behavior:
- Lawful Good: challenges unjust rulers openly, never assassinates
- Chaotic Evil: assassinates, poisons, frames rivals
- Neutral: allies with whoever is winning
- Ambitious NPCs seek power regardless of alignment
"""

import random
import math
from typing import Dict, List, Optional, Tuple


# ================================================================
# NPC AMBITION — determines who seeks power
# ================================================================

def calc_ambition(npc) -> float:
    """Calculate how power-hungry an NPC is (0.0-1.0).
    Driven by personality traits, alignment, class, and title.
    """
    ambition = 0.3  # baseline

    # Personality traits
    traits = getattr(npc, 'social_traits', [])
    if "ambitious" in traits: ambition += 0.3
    if "lazy" in traits: ambition -= 0.3
    if "generous" in traits: ambition -= 0.1
    if "greedy" in traits: ambition += 0.2
    if "brave" in traits: ambition += 0.1
    if "cautious" in traits: ambition -= 0.1

    # Class affects ambition
    cls = getattr(npc, 'char_class', '')
    class_ambition = {
        "Fighter": 0.1, "Paladin": 0.05, "Barbarian": 0.15,
        "Rogue": 0.2, "Wizard": 0.15, "Warlock": 0.25,
        "Bard": 0.1, "Cleric": 0.05, "Ranger": -0.1,
        "Druid": -0.1, "Monk": -0.2, "Sorcerer": 0.15,
    }
    ambition += class_ambition.get(cls, 0)

    # Evil alignment increases ambition
    alignment = getattr(npc, 'alignment', 'true neutral')
    if "evil" in alignment: ambition += 0.2
    if "chaotic" in alignment: ambition += 0.05

    # Already powerful = more ambitious (want to keep/extend power)
    title = getattr(npc, 'title', 'commoner')
    if title in ("duke", "lord", "knight"): ambition += 0.1
    if title == "monarch": ambition += 0.15

    # Bravery feeds ambition
    ambition += (getattr(npc, 'bravery', 0.5) - 0.5) * 0.2

    return max(0.0, min(1.0, ambition))


# ================================================================
# PLOT TYPES
# ================================================================

PLOT_TYPES = {
    "seize_throne": {
        "description": "Seize the throne by force or political maneuvering",
        "min_ambition": 0.6,
        "min_title": ["duke", "lord", "knight"],
        "risk": "high",
        "success_factors": ["military_strength", "support", "charisma"],
    },
    "assassination": {
        "description": "Eliminate a rival through covert means",
        "min_ambition": 0.7,
        "min_title": ["duke", "lord", "knight", "guard"],
        "risk": "extreme",
        "requires_evil": True,
        "success_factors": ["stealth", "deception", "poison"],
    },
    "form_faction": {
        "description": "Build a faction of loyal followers",
        "min_ambition": 0.4,
        "min_title": ["knight", "lord", "duke", "commoner"],
        "risk": "low",
        "success_factors": ["charisma", "wealth", "persuasion"],
    },
    "undermine_ruler": {
        "description": "Spread discontent to weaken the current ruler",
        "min_ambition": 0.5,
        "min_title": ["knight", "lord", "duke", "commoner"],
        "risk": "medium",
        "success_factors": ["deception", "social_connections", "charisma"],
    },
    "rebellion": {
        "description": "Raise an armed rebellion against the ruler",
        "min_ambition": 0.7,
        "min_title": ["lord", "duke"],
        "risk": "extreme",
        "requires_low_morale": True,
        "success_factors": ["military_strength", "morale", "support"],
    },
    "marriage_alliance": {
        "description": "Marry into a powerful family for political gain",
        "min_ambition": 0.3,
        "min_title": ["commoner", "knight", "lord", "duke"],
        "risk": "low",
        "success_factors": ["charisma", "wealth", "title"],
    },
    "bribery_campaign": {
        "description": "Buy loyalty from officials and guards",
        "min_ambition": 0.4,
        "min_title": ["commoner", "knight", "lord", "duke"],
        "risk": "medium",
        "success_factors": ["wealth", "deception"],
    },
}


# ================================================================
# ACTIVE PLOT
# ================================================================

class Plot:
    """An active political scheme by an NPC."""
    __slots__ = ('plotter_name', 'plot_type', 'target_name', 'target_kingdom',
                 'supporters', 'progress', 'risk_level', 'start_day',
                 'status', 'discovery_chance')

    def __init__(self, plotter_name: str, plot_type: str,
                 target_name: str, target_kingdom: str, start_day: int):
        self.plotter_name = plotter_name
        self.plot_type = plot_type
        self.target_name = target_name
        self.target_kingdom = target_kingdom
        self.supporters: List[str] = []
        self.progress = 0.0  # 0-1, completes at 1.0
        self.risk_level = PLOT_TYPES.get(plot_type, {}).get("risk", "medium")
        self.start_day = start_day
        self.status = "active"  # active, succeeded, failed, discovered
        self.discovery_chance = 0.0  # increases over time


# ================================================================
# INTRIGUE SYSTEM
# ================================================================

class IntrigueSystem:
    """Manages political plots, power struggles, and court intrigue."""

    def __init__(self):
        self.active_plots: List[Plot] = []
        self.intrigue_log: List[str] = []
        self._update_timer = 0.0
        self._plot_timer = 0.0

    def update(self, dt: float, npcs: list, governance, day: int):
        """Update political intrigue."""
        self._update_timer += dt
        self._plot_timer += dt

        # Generate new plots periodically
        if self._plot_timer >= 120.0:  # every 2 minutes
            self._plot_timer = 0.0
            self._generate_plots(npcs, governance, day)

        # Progress existing plots
        if self._update_timer >= 30.0:  # every 30 seconds
            self._update_timer = 0.0
            self._progress_plots(npcs, governance, day)

    def _generate_plots(self, npcs: list, governance, day: int):
        """Ambitious NPCs start new plots."""
        for npc in npcs:
            if not npc.alive:
                continue

            ambition = calc_ambition(npc)
            if ambition < 0.4:
                continue  # not ambitious enough to plot

            # Already plotting?
            if any(p.plotter_name == npc.name and p.status == "active"
                   for p in self.active_plots):
                continue

            # Find their kingdom or local power structure
            kingdom_name = None
            kingdom = None
            target_ruler = None
            for kname, k in governance.kingdoms.items():
                if k.contains(npc.x, npc.y):
                    kingdom_name = kname
                    kingdom = k
                    target_ruler = k.ruler_name
                    break

            # If no kingdom, look for local settlement leader
            if not kingdom_name:
                # Find the most powerful NPC nearby as a target
                from game.systems.world_manager import WorldManager
                for other in npcs:
                    if (other.alive and other.name != npc.name and
                        npc.dist_to(other) < 30):
                        other_title = getattr(other, 'title', 'commoner')
                        if other_title in ('monarch', 'duke', 'lord', 'knight'):
                            target_ruler = other.name
                            kingdom_name = "local_settlement"
                            break
                # If still no target, pick strongest nearby NPC
                if not target_ruler:
                    nearby = [n for n in npcs if n.alive and n.name != npc.name
                             and npc.dist_to(n) < 20]
                    if nearby:
                        strongest = max(nearby, key=lambda n: n.hp + n.level * 5)
                        if calc_ambition(npc) > calc_ambition(strongest) + 0.1:
                            target_ruler = strongest.name
                            kingdom_name = "local_power"

            if not target_ruler:
                continue

            # Don't plot against yourself
            if npc.name == target_ruler:
                continue

            title = getattr(npc, 'title', 'commoner')
            alignment = getattr(npc, 'alignment', 'true neutral')
            gold = getattr(npc, 'npc_gold', 0)

            # Choose plot type based on ambition, resources, and alignment
            possible_plots = []

            for ptype, pdata in PLOT_TYPES.items():
                if ambition < pdata["min_ambition"]:
                    continue
                if title not in pdata.get("min_title", ["commoner"]):
                    continue
                if pdata.get("requires_evil") and "evil" not in alignment:
                    continue
                if pdata.get("requires_low_morale") and kingdom.public_morale > 40:
                    continue
                possible_plots.append(ptype)

            if not possible_plots:
                continue

            # Random chance to actually start plotting (not everyone who can, does)
            if random.random() > ambition * 0.15:
                continue

            plot_type = random.choice(possible_plots)
            plot = Plot(npc.name, plot_type, target_ruler,
                       kingdom_name, day)

            self.active_plots.append(plot)

            npc.add_memory("politics",
                f"Began plotting to {PLOT_TYPES[plot_type]['description'].lower()}",
                3)

            self.intrigue_log.append(
                f"{npc.name} ({npc.char_class}) began plotting: {plot_type} "
                f"against {target_ruler} in {kingdom_name}")

    def _progress_plots(self, npcs: list, governance, day: int):
        """Advance or fail existing plots."""
        npc_map = {n.name: n for n in npcs if n.alive}

        for plot in list(self.active_plots):
            if plot.status != "active":
                continue

            plotter = npc_map.get(plot.plotter_name)
            if not plotter:
                plot.status = "failed"
                continue

            target = npc_map.get(plot.target_name)
            kingdom = governance.kingdoms.get(plot.target_kingdom)

            # Progress based on plotter's abilities
            cha = plotter.attributes.get("charisma", 5)
            intel = plotter.attributes.get("intelligence", 5)
            gold = getattr(plotter, 'npc_gold', 0)

            progress_rate = 0.02 + cha * 0.005 + intel * 0.003

            # Wealth helps bribery and faction-building
            if plot.plot_type in ("bribery_campaign", "form_faction"):
                progress_rate += min(0.03, gold * 0.0003)

            # Military plots need military strength
            if plot.plot_type in ("seize_throne", "rebellion"):
                skills = getattr(plotter, 'npc_skills', {})
                progress_rate += skills.get("leadership", 0) * 0.005

            # Supporters boost progress
            progress_rate += len(plot.supporters) * 0.005

            plot.progress = min(1.0, plot.progress + progress_rate)

            # Discovery risk increases over time
            plot.discovery_chance = min(0.5, plot.discovery_chance + 0.005)

            # Check if discovered
            if target and random.random() < plot.discovery_chance:
                # Target's wisdom/insight helps detect plots
                target_wis = target.attributes.get("wisdom", 5) if target else 5
                detection = random.random() < (target_wis * 0.08)

                if detection:
                    plot.status = "discovered"
                    self.intrigue_log.append(
                        f"{plot.target_name} discovered {plotter.name}'s plot: {plot.plot_type}!")

                    # Consequences
                    plotter.add_memory("politics",
                        f"My plot against {plot.target_name} was discovered!", 5)
                    if target:
                        target.add_memory("politics",
                            f"Discovered {plotter.name} plotting against me!", 5)

                    # Reputation damage
                    from game.systems.memory import ensure_life_ledger
                    ensure_life_ledger(plotter).record_crime(
                        "treason", f"Plot against {plot.target_name} discovered",
                        day, plotter.name, plot.target_name, True)

                    # Possible arrest/execution
                    if kingdom:
                        kingdom.public_morale = max(0, kingdom.public_morale - 5)
                    continue

            # Check if plot succeeds
            if plot.progress >= 1.0:
                self._execute_plot(plot, plotter, target, kingdom,
                                  governance, npcs, day)

    def _execute_plot(self, plot: Plot, plotter, target, kingdom,
                      governance, npcs: list, day: int):
        """Execute a completed plot."""
        plot_type = plot.plot_type
        success = False

        if plot_type == "seize_throne":
            # Need a real kingdom to seize
            if not kingdom:
                plot.status = "failed"
                return
            # Success depends on military strength and support
            plotter_power = (getattr(plotter, 'bravery', 0.5) * 3 +
                           len(plot.supporters) * 2 +
                           plotter.attributes.get("charisma", 5))
            target_power = 10  # base throne power
            if target:
                target_power = (target.hp / max(1, target.max_hp) * 5 +
                              target.attributes.get("charisma", 5))

            if plotter_power > target_power * 0.8:
                success = True
                if kingdom:
                    old_ruler = kingdom.ruler_name
                    kingdom.ruler_name = plotter.name
                    plotter.is_ruler = True
                    plotter.title = "monarch"
                    if target:
                        target.is_ruler = False
                        target.title = "commoner"
                        target.add_memory("politics",
                            f"Deposed by {plotter.name}!", 5)

                    plotter.add_memory("politics",
                        f"Seized the throne of {plot.target_kingdom}!", 5)

                    from game.systems.memory import ensure_life_ledger
                    ensure_life_ledger(plotter).record_milestone("seized_throne",
                        f"Seized the throne of {plot.target_kingdom} from {old_ruler}", day)

                    self.intrigue_log.append(
                        f"COUP! {plotter.name} seizes the throne of {plot.target_kingdom} "
                        f"from {old_ruler}!")
                    if kingdom:
                        kingdom.events.append(
                            f"{plotter.name} seized power in a coup!")
                        kingdom.public_morale = max(0, kingdom.public_morale - 15)

        elif plot_type == "assassination":
            if target and target.alive:
                # Stealth-based success
                skills = getattr(plotter, 'npc_skills', {})
                stealth = skills.get("stealth", 0)
                if random.random() < 0.3 + stealth * 0.07:
                    success = True
                    target.alive = False
                    target.hp = 0
                    plotter.add_memory("politics",
                        f"Arranged the death of {target.name}", 4)

                    from game.systems.memory import ensure_life_ledger
                    ensure_life_ledger(plotter).record_kill(
                        target.name, day, is_npc=True)

                    self.intrigue_log.append(
                        f"ASSASSINATION! {target.name} was killed — "
                        f"suspected: {plotter.name}")

        elif plot_type == "form_faction":
            # Always succeeds — build influence
            success = True
            # Recruit nearby NPCs as supporters
            for npc in npcs:
                if not npc.alive or npc.name == plotter.name:
                    continue
                if npc.dist_to(plotter) < 20 and len(plot.supporters) < 5:
                    if npc.name not in plot.supporters:
                        # Check if NPC would join
                        trust = 0
                        from game.systems.social import SocialSystem
                        affinity = npc.friendliness * 0.5 + calc_ambition(npc) * 0.3
                        if random.random() < affinity:
                            plot.supporters.append(npc.name)

            plotter.add_memory("politics",
                f"Built a faction of {len(plot.supporters)} supporters", 3)
            self.intrigue_log.append(
                f"{plotter.name} formed a faction with {len(plot.supporters)} supporters")

        elif plot_type == "undermine_ruler":
            if kingdom:
                success = True
                morale_hit = 5 + plotter.attributes.get("charisma", 5)
                kingdom.public_morale = max(0, kingdom.public_morale - morale_hit)
                kingdom.corruption = min(1.0, kingdom.corruption + 0.05)
                self.intrigue_log.append(
                    f"{plotter.name} undermined {plot.target_name}'s rule "
                    f"(morale -{morale_hit})")

        elif plot_type == "rebellion":
            if not kingdom:
                plot.status = "failed"
                return
            # Full armed rebellion
            rebel_strength = len(plot.supporters) * 3 + plotter.attributes.get("strength", 5)
            kingdom_strength = kingdom.army_size * 2

            if rebel_strength > kingdom_strength * 0.6:
                success = True
                if kingdom:
                    old_ruler = kingdom.ruler_name
                    kingdom.ruler_name = plotter.name
                    plotter.is_ruler = True
                    plotter.title = "monarch"
                    if target:
                        target.is_ruler = False
                        target.title = "commoner"

                    from game.systems.memory import ensure_life_ledger
                    ensure_life_ledger(plotter).record_milestone("rebellion",
                        f"Led a successful rebellion in {plot.target_kingdom}", day)

                    self.intrigue_log.append(
                        f"REBELLION! {plotter.name} overthrows {old_ruler} "
                        f"in {plot.target_kingdom}!")
                    kingdom.public_morale = max(0, kingdom.public_morale - 25)
            else:
                self.intrigue_log.append(
                    f"Failed rebellion by {plotter.name} in {plot.target_kingdom}")

        elif plot_type == "bribery_campaign":
            cost = 10 + random.randint(5, 20)
            if getattr(plotter, 'npc_gold', 0) >= cost:
                plotter.npc_gold -= cost
                success = True
                if kingdom:
                    kingdom.corruption = min(1.0, kingdom.corruption + 0.08)
                self.intrigue_log.append(
                    f"{plotter.name} spent {cost}g bribing officials")

        elif plot_type == "marriage_alliance":
            success = True
            # Find a suitable partner NPC
            for npc in npcs:
                if (npc.alive and npc.name != plotter.name and
                    npc.dist_to(plotter) < 30):
                    title = getattr(npc, 'title', 'commoner')
                    if title in ('duke', 'lord', 'knight', 'monarch'):
                        from game.systems.memory import ensure_life_ledger
                        ensure_life_ledger(plotter).record_bond(
                            npc.name, "spouse", day, trust=50,
                            notes="political marriage")
                        ensure_life_ledger(npc).record_bond(
                            plotter.name, "spouse", day, trust=50,
                            notes="political marriage")
                        self.intrigue_log.append(
                            f"Political marriage: {plotter.name} married {npc.name}")
                        break

        if success:
            plot.status = "succeeded"
        else:
            plot.status = "failed"
            plotter.add_memory("politics",
                f"Failed to {PLOT_TYPES[plot_type]['description'].lower()}", 3)

    def get_intrigue_log(self) -> List[str]:
        log = list(self.intrigue_log)
        self.intrigue_log.clear()
        return log

    def get_active_plots_report(self) -> str:
        active = [p for p in self.active_plots if p.status == "active"]
        if not active:
            return "No active plots"
        lines = []
        for p in active:
            lines.append(f"  {p.plotter_name}: {p.plot_type} vs {p.target_name} "
                        f"({p.progress*100:.0f}% complete)")
        return "\n".join(lines)
