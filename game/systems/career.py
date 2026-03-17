"""
Player Career Advancement — political and military progression paths.

Two advancement tracks:

MILITARY PATH:
  Recruit → Soldier → Sergeant → Captain → Commander → General → Marshal
  - Advance through combat, quests, and leadership
  - Each rank unlocks new abilities and authority
  - Can command NPCs, lead battles, recruit troops

POLITICAL PATH:
  Outsider → Citizen → Councilor → Magistrate → Mayor → Governor → Lord → Duke → King
  - Advance through reputation, wealth, quests, and social connections
  - Each rank unlocks governance authority
  - Can set laws, collect taxes, manage settlements

Requirements for advancement scale with rank — early ranks are achievable,
later ones require significant investment in skills, reputation, and resources.
"""

import random
from typing import Dict, List, Optional, Tuple


# ================================================================
# MILITARY RANKS
# ================================================================

MILITARY_RANKS = [
    {
        "rank": "civilian",
        "title": "Civilian",
        "description": "Not enlisted in any army",
        "authority": 0,
        "requirements": {},
    },
    {
        "rank": "recruit",
        "title": "Recruit",
        "description": "Fresh enlistee, still in training",
        "authority": 1,
        "requirements": {},  # anyone can enlist
        "pay": 1,  # gold per day
    },
    {
        "rank": "soldier",
        "title": "Soldier",
        "description": "Trained fighter in the army",
        "authority": 2,
        "requirements": {"kills": 3, "level": 2, "swordsmanship": 2},
        "pay": 2,
    },
    {
        "rank": "sergeant",
        "title": "Sergeant",
        "description": "Leads a small squad of soldiers",
        "authority": 3,
        "requirements": {"kills": 10, "level": 3, "swordsmanship": 3, "leadership": 2},
        "pay": 4,
        "commands": 5,  # can lead this many soldiers
    },
    {
        "rank": "captain",
        "title": "Captain",
        "description": "Commands a company, trusted officer",
        "authority": 5,
        "requirements": {"kills": 25, "level": 5, "swordsmanship": 4, "leadership": 3, "quests": 5},
        "pay": 8,
        "commands": 20,
    },
    {
        "rank": "commander",
        "title": "Commander",
        "description": "Senior officer commanding large forces",
        "authority": 7,
        "requirements": {"kills": 50, "level": 7, "swordsmanship": 5, "leadership": 5, "quests": 10},
        "pay": 15,
        "commands": 50,
    },
    {
        "rank": "general",
        "title": "General",
        "description": "Commands an entire army",
        "authority": 9,
        "requirements": {"kills": 100, "level": 9, "leadership": 7, "quests": 20, "gold": 200},
        "pay": 25,
        "commands": 200,
    },
    {
        "rank": "marshal",
        "title": "Marshal",
        "description": "Supreme military commander, right hand of the ruler",
        "authority": 10,
        "requirements": {"kills": 200, "level": 12, "leadership": 9, "quests": 30, "gold": 500},
        "pay": 50,
        "commands": 999,
    },
]


# ================================================================
# POLITICAL RANKS
# ================================================================

POLITICAL_RANKS = [
    {
        "rank": "outsider",
        "title": "Outsider",
        "description": "A stranger with no standing in the community",
        "authority": 0,
        "requirements": {},
    },
    {
        "rank": "citizen",
        "title": "Citizen",
        "description": "A recognized member of the community",
        "authority": 1,
        "requirements": {"quests": 2, "reputation": 20},
    },
    {
        "rank": "councilor",
        "title": "Councilor",
        "description": "An advisor to local leadership",
        "authority": 3,
        "requirements": {"quests": 5, "reputation": 50, "level": 3, "persuasion": 2, "gold": 50},
    },
    {
        "rank": "magistrate",
        "title": "Magistrate",
        "description": "A judge and enforcer of laws",
        "authority": 4,
        "requirements": {"quests": 8, "reputation": 80, "level": 4, "persuasion": 3,
                        "leadership": 2, "gold": 100},
    },
    {
        "rank": "mayor",
        "title": "Mayor",
        "description": "Elected or appointed leader of a town",
        "authority": 6,
        "requirements": {"quests": 15, "reputation": 200, "level": 6, "persuasion": 4,
                        "leadership": 4, "gold": 500, "kills": 15},
        "governs": "town",
    },
    {
        "rank": "governor",
        "title": "Governor",
        "description": "Ruler of a region appointed by the crown",
        "authority": 7,
        "requirements": {"quests": 25, "reputation": 400, "level": 8, "persuasion": 6,
                        "leadership": 6, "gold": 1500, "kills": 30},
        "governs": "region",
    },
    {
        "rank": "lord",
        "title": "Lord",
        "description": "Landed noble with hereditary authority",
        "authority": 8,
        "requirements": {"quests": 40, "reputation": 700, "level": 10, "leadership": 7,
                        "persuasion": 6, "gold": 3000, "kills": 50,
                        "military_rank": "captain"},
        "governs": "territory",
    },
    {
        "rank": "duke",
        "title": "Duke",
        "description": "High noble ruling a duchy",
        "authority": 9,
        "requirements": {"quests": 60, "reputation": 1200, "level": 13, "leadership": 9,
                        "persuasion": 7, "gold": 8000, "kills": 100,
                        "military_rank": "commander"},
        "governs": "duchy",
    },
    {
        "rank": "king",
        "title": "King",
        "description": "Sovereign ruler of a kingdom",
        "authority": 10,
        "requirements": {"quests": 100, "reputation": 2500, "level": 16, "leadership": 10,
                        "persuasion": 9, "gold": 20000, "kills": 200,
                        "military_rank": "general"},
        "governs": "kingdom",
    },
]


# ================================================================
# CAREER SYSTEM
# ================================================================

class CareerSystem:
    """Manages player military and political advancement."""

    def __init__(self):
        self.military_rank_idx = 0  # index into MILITARY_RANKS
        self.political_rank_idx = 0  # index into POLITICAL_RANKS
        self.enlisted_kingdom = ""
        self.governed_settlement = ""
        self.reputation = 0  # accumulated from quests, kills, social acts
        self.troops_commanded: List[str] = []  # NPC names under player command
        self.career_log: List[str] = []
        self.duty_kills = 0  # kills by troops under command (NOT personal kills)
        self._player_army = None
        self._war_target = None

    @property
    def military_rank(self) -> dict:
        return MILITARY_RANKS[self.military_rank_idx]

    @property
    def political_rank(self) -> dict:
        return POLITICAL_RANKS[self.political_rank_idx]

    @property
    def military_title(self) -> str:
        return self.military_rank["title"]

    @property
    def political_title(self) -> str:
        return self.political_rank["title"]

    @property
    def highest_title(self) -> str:
        """Return the more prestigious title."""
        if self.military_rank["authority"] > self.political_rank["authority"]:
            return self.military_title
        return self.political_title

    def gain_reputation(self, amount: int, reason: str = ""):
        """Gain reputation from actions."""
        self.reputation += amount
        if reason:
            self.career_log.append(f"Gained {amount} reputation: {reason}")

    def enlist(self, kingdom_name: str) -> str:
        """Player enlists in a kingdom's army."""
        if self.military_rank_idx > 0:
            return f"Already enlisted as {self.military_title}"
        self.military_rank_idx = 1  # recruit
        self.enlisted_kingdom = kingdom_name
        msg = f"Enlisted in the army of {kingdom_name} as a Recruit!"
        self.career_log.append(msg)
        return msg

    def desert(self) -> str:
        """Player deserts the army. Reputation penalty."""
        if self.military_rank_idx == 0:
            return "Not enlisted in any army"
        old_rank = self.military_title
        self.military_rank_idx = 0
        self.enlisted_kingdom = ""
        self.troops_commanded.clear()
        self.reputation = max(0, self.reputation - 50)
        msg = f"Deserted from the army! Lost 50 reputation."
        self.career_log.append(msg)
        return msg

    def check_military_promotion(self, player) -> Optional[str]:
        """Check if player qualifies for military promotion."""
        if self.military_rank_idx == 0:
            return None
        next_idx = self.military_rank_idx + 1
        if next_idx >= len(MILITARY_RANKS):
            return None

        next_rank = MILITARY_RANKS[next_idx]
        reqs = next_rank["requirements"]

        if not self._meets_requirements(player, reqs):
            return None

        # Promote!
        self.military_rank_idx = next_idx
        msg = f"Promoted to {next_rank['title']}!"
        self.career_log.append(msg)
        self.gain_reputation(next_rank["authority"] * 10, "military promotion")
        return msg

    def check_political_promotion(self, player) -> Optional[str]:
        """Check if player qualifies for political advancement."""
        next_idx = self.political_rank_idx + 1
        if next_idx >= len(POLITICAL_RANKS):
            return None

        next_rank = POLITICAL_RANKS[next_idx]
        reqs = next_rank["requirements"]

        # Check reputation requirement
        if self.reputation < reqs.get("reputation", 0):
            return None

        # Check military rank requirement
        mil_req = reqs.get("military_rank")
        if mil_req:
            mil_names = [r["rank"] for r in MILITARY_RANKS]
            required_idx = mil_names.index(mil_req) if mil_req in mil_names else 0
            if self.military_rank_idx < required_idx:
                return None

        if not self._meets_requirements(player, reqs):
            return None

        # Promote!
        self.political_rank_idx = next_idx
        msg = f"Achieved rank of {next_rank['title']}!"
        self.career_log.append(msg)
        self.gain_reputation(next_rank["authority"] * 15, "political advancement")
        return msg

    def _meets_requirements(self, player, reqs: dict) -> bool:
        """Check if player meets a set of requirements.

        For military kills requirement: personal kills + duty kills
        (kills from troops under command) both count.
        """
        skills = getattr(player, 'skills', {})

        # Military kills = personal kills + kills by troops under command
        total_kills = player.kills + self.duty_kills
        if total_kills < reqs.get("kills", 0):
            return False
        if player.level < reqs.get("level", 0):
            return False
        if getattr(player, 'quests_completed', 0) < reqs.get("quests", 0):
            return False
        if player.gold < reqs.get("gold", 0):
            return False

        for skill_name in ("swordsmanship", "leadership", "persuasion",
                          "archery", "trading", "diplomacy"):
            if skill_name in reqs:
                if skills.get(skill_name, 0) < reqs[skill_name]:
                    return False

        return True

    def get_next_military_requirements(self) -> Optional[dict]:
        """Get requirements for next military promotion."""
        next_idx = self.military_rank_idx + 1
        if next_idx >= len(MILITARY_RANKS):
            return None
        return MILITARY_RANKS[next_idx]["requirements"]

    def get_next_political_requirements(self) -> Optional[dict]:
        """Get requirements for next political advancement."""
        next_idx = self.political_rank_idx + 1
        if next_idx >= len(POLITICAL_RANKS):
            return None
        reqs = dict(POLITICAL_RANKS[next_idx]["requirements"])
        reqs["reputation"] = reqs.get("reputation", 0)
        return reqs

    def get_progress_report(self, player) -> str:
        """Get a formatted progress report."""
        lines = []
        lines.append(f"Military: {self.military_title}")
        if self.enlisted_kingdom:
            lines.append(f"  Army of {self.enlisted_kingdom}")
        next_mil = self.get_next_military_requirements()
        if next_mil and self.military_rank_idx > 0:
            met = []
            unmet = []
            for k, v in next_mil.items():
                if k == "kills":
                    current = player.kills
                elif k == "level":
                    current = player.level
                elif k == "quests":
                    current = player.quests_completed
                elif k == "gold":
                    current = player.gold
                else:
                    current = player.skills.get(k, 0)
                status = f"{k}: {current}/{v}"
                if current >= v:
                    met.append(status)
                else:
                    unmet.append(status)
            next_title = MILITARY_RANKS[self.military_rank_idx + 1]["title"]
            lines.append(f"  Next: {next_title}")
            if unmet:
                lines.append(f"  Need: {', '.join(unmet)}")

        lines.append(f"\nPolitical: {self.political_title}")
        lines.append(f"  Reputation: {self.reputation}")
        if self.governed_settlement:
            lines.append(f"  Governs: {self.governed_settlement}")
        next_pol = self.get_next_political_requirements()
        if next_pol:
            unmet = []
            for k, v in next_pol.items():
                if k == "reputation":
                    current = self.reputation
                elif k == "kills":
                    current = player.kills
                elif k == "level":
                    current = player.level
                elif k == "quests":
                    current = player.quests_completed
                elif k == "gold":
                    current = player.gold
                elif k == "military_rank":
                    continue
                else:
                    current = player.skills.get(k, 0)
                if current < v:
                    unmet.append(f"{k}: {current}/{v}")
            next_title = POLITICAL_RANKS[self.political_rank_idx + 1]["title"]
            lines.append(f"  Next: {next_title}")
            if unmet:
                lines.append(f"  Need: {', '.join(unmet)}")

        return "\n".join(lines)

    def recruit_npc(self, npc_name: str) -> bool:
        """Recruit an NPC to serve under player's command."""
        max_troops = self.military_rank.get("commands", 0)
        if len(self.troops_commanded) >= max_troops:
            return False
        if npc_name not in self.troops_commanded:
            self.troops_commanded.append(npc_name)
            return True
        return False

    def on_quest_complete(self, reward_gold: int):
        """Called when player completes a quest — gain reputation."""
        rep = 5 + reward_gold // 10
        self.gain_reputation(rep, "quest completed")

    def on_kill(self, creature_name: str):
        """Called when player kills something — gain reputation for notable kills."""
        notable = {"bear": 5, "troll": 10, "ogre": 8, "dragon": 50,
                   "bandit": 3, "orc": 4, "skeleton": 2}
        for key, rep in notable.items():
            if key in creature_name.lower():
                self.gain_reputation(rep, f"killed {creature_name}")
                return
        self.gain_reputation(1, f"killed {creature_name}")

    def on_troop_kill(self, creature_name: str, count: int = 1):
        """Called when troops under command kill enemies (duty kills).

        These count toward military promotion but are separate from
        player.kills (personal kills done by the character themselves).
        """
        self.duty_kills += count
        # Reputation for commanding successful troops
        self.gain_reputation(count, f"troops killed {creature_name}")

    def on_npc_helped(self):
        """Called when player helps an NPC (healing, giving items, etc.)."""
        self.gain_reputation(2, "helped someone")

    def apply_daily_pay(self, player):
        """Apply military pay to player gold."""
        pay = self.military_rank.get("pay", 0)
        if pay > 0 and self.enlisted_kingdom:
            player.gold += pay

    # ================================================================
    # SCOUTING — reveal enemy strength before attack
    # ================================================================

    def scout_settlement(self, player, target_structure, world_npcs: list,
                          world_creatures: list = None) -> dict:
        """Scout a settlement to reveal its defenses. Requires Navigation >= 2.

        Returns dict with defender count, strength estimate, and recommendations.
        """
        skills = getattr(player, 'skills', {})
        nav_skill = skills.get("navigation", 0)
        if nav_skill < 2:
            return {"success": False,
                    "message": "Need Navigation skill >= 2 to scout."}

        # Count defenders
        defenders = [n for n in world_npcs if n.alive
                     and getattr(n, 'faction', '') == target_structure.name]
        creatures = []
        if world_creatures:
            import math
            creatures = [c for c in world_creatures if c.alive
                        and math.sqrt((c.x - target_structure.x)**2 +
                                      (c.y - target_structure.y)**2)
                        < target_structure.radius + 10]

        total_enemies = len(defenders) + len(creatures)

        # Strength estimate (with some noise based on skill)
        noise = max(0.7, 1.0 - nav_skill * 0.05)
        estimated = int(total_enemies * random.uniform(noise, 1.0 / noise))

        # Recommendation
        army = self.get_player_army()
        our_troops = len(army["soldiers"]) if army else 0
        if our_troops == 0:
            rec = "You have no army. Recruit troops first."
        elif our_troops >= total_enemies * 1.5:
            rec = "Favorable odds. Attack recommended."
        elif our_troops >= total_enemies:
            rec = "Even odds. Victory possible but costly."
        elif our_troops >= total_enemies * 0.5:
            rec = "Outnumbered. Consider recruiting more troops."
        else:
            rec = "Heavily outnumbered. Suicidal to attack now."

        # Gain XP
        player.gain_skill_xp("navigation", 1.0) if hasattr(player, 'gain_skill_xp') else None

        return {
            "success": True,
            "defenders": len(defenders),
            "creatures": len(creatures),
            "total": total_enemies,
            "estimated": estimated,
            "our_troops": our_troops,
            "recommendation": rec,
            "message": (f"Scouted {target_structure.name}: ~{estimated} enemies "
                       f"({len(defenders)} soldiers, {len(creatures)} beasts). "
                       f"{rec}"),
        }

    # ================================================================
    # MERCENARIES — hire troops at taverns bypassing command cap
    # ================================================================

    def hire_mercenaries(self, player, count: int, cost_per_merc: int = 15) -> str:
        """Hire mercenaries at taverns. Bypasses normal command limit.

        Mercenaries cost gold but don't require military rank to command.
        They fight as part of the player's army but desert after battle.
        """
        total_cost = count * cost_per_merc
        if player.gold < total_cost:
            affordable = player.gold // cost_per_merc
            if affordable <= 0:
                return f"Can't afford mercenaries. Need {cost_per_merc}g each."
            count = affordable
            total_cost = count * cost_per_merc

        player.gold -= total_cost

        # Add mercenaries as temporary troops
        for i in range(count):
            merc_name = f"Mercenary_{random.randint(1000, 9999)}"
            if merc_name not in self.troops_commanded:
                self.troops_commanded.append(merc_name)

        # Update army if it exists
        army = self.get_player_army()
        if army:
            army["soldiers"] = list(self.troops_commanded)

        self.career_log.append(f"Hired {count} mercenaries for {total_cost}g")
        return f"Hired {count} mercenaries for {total_cost}g! ({len(self.troops_commanded)} total troops)"

    # ================================================================
    # RETREAT — save remaining troops from a losing battle
    # ================================================================

    def retreat_from_battle(self) -> str:
        """Retreat mid-battle. Saves remaining troops but costs 20% extra casualties."""
        army = self.get_player_army()
        if not army:
            return "No army to retreat."

        current = len(army["soldiers"])
        extra_loss = max(1, int(current * 0.2))
        for _ in range(extra_loss):
            if army["soldiers"]:
                army["soldiers"].pop()

        army["state"] = "retreating"
        army["morale"] = max(10, army["morale"] - 25)
        self.troops_commanded = list(army["soldiers"])
        self.career_log.append(f"Retreated! Lost {extra_loss} troops in retreat.")
        return f"Retreat! Lost {extra_loss} troops. {len(army['soldiers'])} remain."

    # ================================================================
    # ALLIED REINFORCEMENTS — request aid from friendly kingdoms
    # ================================================================

    def request_reinforcements(self, governance, count_requested: int = 10) -> str:
        """Request military aid from allied kingdoms. Costs reputation.

        Allied kingdoms may send troops to join your army.
        """
        if not self.enlisted_kingdom:
            return "Not enlisted in any kingdom."

        if self.reputation < 50:
            return "Need at least 50 reputation to request aid."

        sent = 0
        for (k1, k2), rel in governance.diplomacy.items():
            if rel.status not in ("allied", "friendly"):
                continue
            # Check if our kingdom is part of this relation
            ally = k2 if k1 == self.enlisted_kingdom else (
                k1 if k2 == self.enlisted_kingdom else None)
            if not ally:
                continue

            # Allied kingdom sends troops
            ally_troops = min(count_requested - sent, random.randint(3, 8))
            for i in range(ally_troops):
                name = f"Allied_{ally[:4]}_{random.randint(100, 999)}"
                if name not in self.troops_commanded:
                    self.troops_commanded.append(name)
                    sent += 1

            if sent >= count_requested:
                break

        if sent == 0:
            return "No allied kingdoms willing to send troops."

        # Update army
        army = self.get_player_army()
        if army:
            army["soldiers"] = list(self.troops_commanded)

        self.reputation = max(0, self.reputation - 30)
        self.career_log.append(f"Received {sent} reinforcements from allies")
        return f"Received {sent} allied reinforcements! ({len(self.troops_commanded)} total troops)"

    # ================================================================
    # TRAINING EXERCISES — gain experience without real combat
    # ================================================================

    def conduct_training(self, player) -> str:
        """Conduct military training with your troops. Grants small kill credit.

        Available once per day. Trains leadership and grants duty kill credit
        equivalent to 1-3 kills based on leadership skill.
        """
        if not hasattr(self, '_last_training_day'):
            self._last_training_day = -1

        skills = getattr(player, 'skills', {})
        leadership = skills.get("leadership", 0)

        kills_credit = 1 + min(2, leadership // 3)
        self.duty_kills += kills_credit
        self.gain_reputation(kills_credit, "training exercises")

        if hasattr(player, 'gain_skill_xp'):
            player.gain_skill_xp("leadership", 0.5)
            player.gain_skill_xp("swordsmanship", 0.3)

        return f"Conducted training exercises. +{kills_credit} duty kill credit, +leadership XP."

    # ================================================================
    # ARMY COMMAND — player's personal army
    # ================================================================

    def create_army(self, player, army_name: str = "") -> Optional[dict]:
        """Create a player-commanded army. Requires Sergeant rank or higher."""
        if self.military_rank["authority"] < 3:  # Sergeant = 3 (lowered from Captain)
            return None
        if not army_name:
            army_name = f"{player.name}'s Company"
        self._player_army = {
            "name": army_name,
            "soldiers": list(self.troops_commanded),
            "morale": 70,
            "x": player.x,
            "y": player.y,
            "state": "idle",
            "wins": 0,
            "losses": 0,
        }
        self.career_log.append(f"Founded {army_name}")
        return self._player_army

    def get_player_army(self) -> Optional[dict]:
        """Get the player's army if it exists."""
        return getattr(self, '_player_army', None)

    def declare_war(self, target_kingdom: str, governance=None) -> str:
        """Declare war on another kingdom. Requires Captain rank or higher.

        If governance system is provided, sets the actual diplomatic relation
        to AT_WAR so the military system will engage.
        """
        if self.military_rank["authority"] < 5:  # Captain minimum
            return "You need at least Captain rank to lead an attack."
        if not self.troops_commanded and not self.get_player_army():
            return "You have no troops under your command."

        self._war_target = target_kingdom

        # Wire into governance diplomacy system
        if governance and self.enlisted_kingdom:
            rel = governance.get_diplomacy(self.enlisted_kingdom, target_kingdom)
            if rel:
                rel.status = "at_war"
                rel.trust = -80

        msg = f"Declared war on {target_kingdom}!"
        self.career_log.append(msg)
        self.gain_reputation(20, f"declared war on {target_kingdom}")
        return msg

    def march_army(self, target_x: float, target_y: float) -> str:
        """Order army to march to a position."""
        army = self.get_player_army()
        if not army:
            return "No army to command."
        army["target_x"] = target_x
        army["target_y"] = target_y
        army["state"] = "marching"
        return f"{army['name']} is marching to ({target_x:.0f}, {target_y:.0f})"

    def resolve_battle_lanchester(self, player, enemy_npcs: list,
                                    enemy_creatures: list = None,
                                    terrain: str = "plains",
                                    is_siege: bool = False) -> dict:
        """Resolve a full Lanchester battle between player's army and enemies.

        Uses the warfare.py BattleField system with proper unit types,
        formations, terrain, and commander bonuses.

        Args:
            player: Player entity (used for leadership skill)
            enemy_npcs: List of enemy NPC objects
            enemy_creatures: Optional list of enemy Creature objects
            terrain: Battle terrain type
            is_siege: Whether this is a siege assault

        Returns:
            dict with won, message, casualties, remaining, round_log
        """
        from game.systems.warfare import (
            BattleField, BattleArmy, TroopUnit, Commander,
            build_army_from_npcs, build_army_from_creatures,
        )

        army = self.get_player_army()
        if not army:
            return {"won": False, "message": "No army to command."}

        # Build player's army from troop NPCs
        # (For this we need NPC objects, not just names)
        player_cmd = Commander(entity=player,
                                leadership=player.skills.get("leadership", 0),
                                name=player.name)

        # Build player units — each commanded NPC becomes a small unit
        player_units = []
        soldier_count = len(army["soldiers"])
        if soldier_count > 0:
            # Group soldiers into units based on count
            infantry_count = max(1, soldier_count * 2 // 3)
            archer_count = soldier_count - infantry_count
            if infantry_count > 0:
                player_units.append(TroopUnit("infantry_sword", infantry_count))
            if archer_count > 0:
                player_units.append(TroopUnit("archer_longbow", archer_count))
        else:
            # Just the player as a lone warrior
            player_units.append(TroopUnit("infantry_sword", 1, equipment_quality=2.0))

        player_army = BattleArmy(army["name"], player_units, player_cmd,
                                  tactic="balanced")

        # Build enemy army
        enemy_units = []
        if enemy_npcs:
            # Group enemy NPCs into units
            melee = sum(1 for n in enemy_npcs if n.alive and
                       getattr(n, 'char_class', '') in ('Fighter', 'Barbarian', 'Paladin', 'Ranger'))
            ranged = sum(1 for n in enemy_npcs if n.alive and
                        getattr(n, 'char_class', '') in ('Wizard', 'Sorcerer', 'Warlock', 'Rogue'))
            support = sum(1 for n in enemy_npcs if n.alive) - melee - ranged
            if melee > 0:
                enemy_units.append(TroopUnit("infantry_sword", melee))
            if ranged > 0:
                enemy_units.append(TroopUnit("archer_longbow", ranged))
            if support > 0:
                enemy_units.append(TroopUnit("infantry_spear", support))

        if enemy_creatures:
            beast_count = sum(1 for c in enemy_creatures if c.alive)
            if beast_count > 0:
                enemy_units.append(TroopUnit("war_dire_wolf", beast_count))

        if not enemy_units:
            return {"won": True, "message": "No enemies to fight!",
                    "casualties": 0, "remaining": soldier_count}

        enemy_cmd = Commander(name="Enemy Commander", leadership=3)
        enemy_army = BattleArmy("Enemy Forces", enemy_units, enemy_cmd,
                                 is_defender=True)

        # Run the battle
        battlefield = BattleField(player_army, enemy_army,
                                   terrain=terrain, is_siege=is_siege)
        result = battlefield.resolve(max_rounds=10)

        won = result["winner"] == army["name"]
        player_casualties = result["attacker_casualties"]
        enemy_casualties = result["defender_casualties"]

        # Apply results
        if won:
            army["wins"] += 1
            army["morale"] = min(100, army["morale"] + 10)
            self.duty_kills += enemy_casualties
            self.gain_reputation(enemy_casualties * 2, "battle victory")

            # Kill enemy NPCs proportionally
            killed = 0
            for npc in enemy_npcs:
                if not npc.alive:
                    continue
                if killed < enemy_casualties:
                    npc.alive = False
                    npc.hp = 0
                    killed += 1

            # Kill enemy creatures
            for c in (enemy_creatures or []):
                if c.alive:
                    c.alive = False
        else:
            army["losses"] += 1
            army["morale"] = max(10, army["morale"] - 20)

        # Remove player casualties from troops
        to_remove = min(player_casualties, len(army["soldiers"]))
        for _ in range(to_remove):
            if army["soldiers"]:
                army["soldiers"].pop()
        self.troops_commanded = list(army["soldiers"])

        msg = (f"{'VICTORY' if won else 'DEFEAT'}! "
               f"{result['rounds']} rounds of combat. "
               f"Our casualties: {player_casualties}. "
               f"Enemy casualties: {enemy_casualties}. "
               f"Remaining: {len(army['soldiers'])} troops.")

        # Build detailed battle report
        report_lines = [f"=== Battle Report: {army['name']} vs Enemy Forces ==="]
        report_lines.append(f"Terrain: {terrain}{'  (SIEGE)' if is_siege else ''}")
        report_lines.append(f"Our forces: {soldier_count + 1} (including commander)")
        report_lines.append(f"Enemy forces: {len(enemy_npcs)} soldiers + {len(enemy_creatures or [])} beasts")
        report_lines.append("")

        for rnd in result.get("round_log", []):
            r_num = rnd.get("round", "?")
            a_sz = rnd.get("atk_size", "?")
            d_sz = rnd.get("def_size", "?")
            report_lines.append(
                f"Round {r_num}: Our troops: {a_sz} | Enemy: {d_sz}")

        report_lines.append("")
        report_lines.append(f"Result: {'VICTORY!' if won else 'DEFEAT!'}")
        report_lines.append(f"Our casualties: {player_casualties}")
        report_lines.append(f"Enemy casualties: {enemy_casualties}")
        report_lines.append(f"Troops remaining: {len(army['soldiers'])}")

        return {
            "won": won,
            "message": msg,
            "player_casualties": player_casualties,
            "enemy_casualties": enemy_casualties,
            "remaining": len(army["soldiers"]),
            "rounds": result["rounds"],
            "round_log": result.get("round_log", []),
            "report": "\n".join(report_lines),
        }

    def resolve_player_battle(self, enemy_army_size: int,
                               enemy_morale: int = 70) -> dict:
        """Simplified battle resolution (fallback when no NPC data available)."""
        army = self.get_player_army()
        if not army:
            return {"won": False, "message": "No army"}

        player_strength = len(army["soldiers"]) * (army["morale"] / 50.0)
        enemy_strength = enemy_army_size * (enemy_morale / 50.0)

        # Player leadership bonus
        player_strength *= 1.0 + self.military_rank["authority"] * 0.05

        # Random combat factor
        p_roll = random.uniform(0.7, 1.3) * player_strength
        e_roll = random.uniform(0.7, 1.3) * enemy_strength

        won = p_roll > e_roll

        if won:
            # Player wins
            player_casualties = max(0, int(len(army["soldiers"]) * 0.1))
            enemy_casualties = max(1, int(enemy_army_size * 0.4))
            army["wins"] += 1
            army["morale"] = min(100, army["morale"] + 10)

            # Remove casualties from player's troops
            for _ in range(player_casualties):
                if army["soldiers"]:
                    lost = army["soldiers"].pop()
                    if lost in self.troops_commanded:
                        self.troops_commanded.remove(lost)

            self.gain_reputation(20 + enemy_army_size, "battle victory")
            msg = (f"Victory! {army['name']} defeated {enemy_army_size} enemies. "
                   f"Lost {player_casualties} soldiers. "
                   f"Army: {len(army['soldiers'])} remaining.")
        else:
            # Player loses
            player_casualties = max(1, int(len(army["soldiers"]) * 0.4))
            enemy_casualties = max(0, int(enemy_army_size * 0.1))
            army["losses"] += 1
            army["morale"] = max(10, army["morale"] - 20)

            for _ in range(player_casualties):
                if army["soldiers"]:
                    lost = army["soldiers"].pop()
                    if lost in self.troops_commanded:
                        self.troops_commanded.remove(lost)

            self.gain_reputation(5, "survived battle")
            msg = (f"Defeat! {army['name']} was beaten by {enemy_army_size} enemies. "
                   f"Lost {player_casualties} soldiers. "
                   f"Army: {len(army['soldiers'])} remaining.")

        self.career_log.append(msg)

        return {
            "won": won,
            "message": msg,
            "player_casualties": player_casualties if won else player_casualties,
            "enemy_casualties": enemy_casualties,
            "army_remaining": len(army["soldiers"]),
        }
