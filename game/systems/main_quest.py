"""The Awakening — 6-stage main questline tied to world history.

Uses QuestChain from quest_chains.py. Stages auto-chain, give rewards,
log to the chronicle, and culminate in a Lich Lord boss fight.
"""

import random
from typing import Optional, List, Dict

from game.systems.quest_chains import (
    QuestChain, QuestStage, StageCondition, BranchChoice,
    CONDITION_KILL, CONDITION_LOCATION, CONDITION_ITEM,
    CONDITION_TALK, CONDITION_DELIVER,
)

# ================================================================
# CONSTANTS
# ================================================================

CHAIN_ID = "the_awakening"

# Persuasion condition — used for "Rally the Kingdoms"
CONDITION_PERSUADE = "persuade"

# Lich Lord stats for the final battle
LICH_LORD_HP = 200
LICH_LORD_ATTACKS = [
    {"name": "Necrotic Bolt", "damage": (12, 22), "desc": "hurls a bolt of dark energy"},
    {"name": "Soul Drain", "damage": (8, 16), "desc": "drains your life force",
     "heal_fraction": 0.5},
    {"name": "Bone Storm", "damage": (15, 28), "desc": "summons a storm of bone shards"},
    {"name": "Death Grasp", "damage": (18, 30), "desc": "reaches out with spectral claws"},
]

STORY_TEXT = {
    "stage_1_complete": "The wanderer arrived at {settlement} from the Temple of Awakening.",
    "stage_2_start": ("{scholar} spoke of ancient evil stirring beneath the earth. "
                      "The wanderer set out to investigate the ruins."),
    "stage_2_complete": "At the ruins near {settlement}, dark magic and an underground passage were found.",
    "stage_3_complete": "The Sunstone Amulet was recovered from the dungeon depths.",
    "stage_4_complete": ("The temple confirmed a Lich Lord stirs in the Necropolis of Ash. "
                         "The kingdoms must unite or fall."),
    "stage_5_complete": "Three kingdoms pledged armies against the Lich Lord.",
    "stage_6_complete": ("The Lich Lord has been vanquished! The phylactery shattered, "
                         "ending the undead threat."),
}

# Unique reward items
SUNSTONE_AMULET = "Sunstone Amulet"
LICH_CROWN = "Crown of the Vanquished Lich"


# ================================================================
# MAIN QUESTLINE FACTORY
# ================================================================

def create_the_awakening(settlement: str = "the settlement",
                         giver: str = "Scholar Aldric") -> QuestChain:
    """Build the 6-stage Awakening quest chain.

    Stage 1 (Find Civilization) is intentionally trivial — it chains
    from the starting quest that already got the player to a settlement.
    """
    stages = [
        # ---- Stage 1: Find Civilization ----
        QuestStage(
            title="Find Civilization",
            description=(
                "You've awakened at an ancient temple with no memory. "
                f"Find the settlement of {settlement} and speak with the locals."
            ),
            condition=StageCondition(
                CONDITION_LOCATION, settlement, 1,
                f"Reach {settlement}",
            ),
            reward_gold=10, reward_xp=25,
        ),

        # ---- Stage 2: The Scholar's Warning ----
        QuestStage(
            title="The Scholar's Warning",
            description=(
                f"A scholar named {giver} in {settlement} speaks of ancient "
                "evil stirring beneath the earth. He begs you to investigate "
                "the nearby ruins before it is too late."
            ),
            condition=StageCondition(
                CONDITION_LOCATION, "ancient ruins", 1,
                "Investigate the ruins near the settlement",
            ),
            reward_gold=30, reward_xp=50,
        ),

        # ---- Stage 3: Into the Depths ----
        QuestStage(
            title="Into the Depths",
            description=(
                "The ruins conceal a dungeon filled with undead. Descend "
                "into the depths and recover the ancient artefact that "
                "the scholar described — the Sunstone Amulet."
            ),
            condition=StageCondition(
                CONDITION_ITEM, SUNSTONE_AMULET, 1,
                "Find the Sunstone Amulet in the dungeon",
            ),
            reward_gold=75, reward_xp=100,
            reward_item=SUNSTONE_AMULET,
        ),

        # ---- Stage 4: The Growing Darkness ----
        QuestStage(
            title="The Growing Darkness",
            description=(
                "Take the Sunstone Amulet to the nearest temple. The "
                "priests can decipher the runes inscribed upon it and "
                "reveal the nature of the threat."
            ),
            condition=StageCondition(
                CONDITION_LOCATION, "temple", 1,
                "Bring the Sunstone Amulet to a temple",
            ),
            reward_gold=50, reward_xp=80,
        ),

        # ---- Stage 5: Rally the Kingdoms ----
        QuestStage(
            title="Rally the Kingdoms",
            description=(
                "A Lich Lord awakens in the Necropolis of Ash. No single "
                "kingdom can stand against its undead legions. Visit the "
                "capitals of three kingdoms and convince their rulers to "
                "join an alliance. (Persuasion checks required.)"
            ),
            condition=StageCondition(
                CONDITION_PERSUADE, "kingdom_capital", 3,
                "Convince 3 kingdom rulers to ally (0/3)",
            ),
            reward_gold=150, reward_xp=200,
        ),

        # ---- Stage 6: The Final Battle ----
        QuestStage(
            title="The Final Battle",
            description=(
                "The alliance is forged. Travel to the Necropolis of Ash "
                "and confront the Lich Lord in its lair. Destroy the "
                "phylactery to end the threat once and for all."
            ),
            condition=StageCondition(
                CONDITION_KILL, "lich_lord", 1,
                "Defeat the Lich Lord",
            ),
            reward_gold=500, reward_xp=500,
            reward_item=LICH_CROWN,
        ),
    ]

    return QuestChain(
        chain_id=CHAIN_ID,
        name="The Awakening",
        stages=stages,
        settlement=settlement,
        giver_name=giver,
    )


# ================================================================
# LICH LORD BOSS
# ================================================================

class LichLord:
    """Final boss for The Awakening questline.

    HP 200, multiple attack patterns, phases at 50 % HP.
    """

    def __init__(self):
        self.name = "Lich Lord"
        self.kind = "lich_lord"
        self.hp = LICH_LORD_HP
        self.max_hp = LICH_LORD_HP
        self.alive = True
        self.phase = 1  # phase 2 triggers at <= 50 % HP
        self.turn_count = 0

    @property
    def hp_fraction(self) -> float:
        return self.hp / self.max_hp if self.max_hp > 0 else 0.0

    def choose_attack(self) -> Dict:
        """Pick an attack based on phase and randomness."""
        self.turn_count += 1

        if self.phase == 1 and self.hp_fraction <= 0.5:
            self.phase = 2  # enraged — heavier attacks unlocked

        if self.phase == 2:
            # Phase 2: prefer heavier attacks, occasionally heal
            weights = [1, 3, 2, 3]
        else:
            weights = [3, 1, 2, 1]

        attack = random.choices(LICH_LORD_ATTACKS, weights=weights, k=1)[0]
        return attack

    def take_damage(self, amount: int) -> str:
        """Apply damage to the Lich Lord, return status text."""
        self.hp = max(0, self.hp - amount)
        if self.hp <= 0:
            self.alive = False
            return "The Lich Lord crumbles! Its phylactery shatters. The undead threat is ended."
        phase_text = ""
        if self.phase == 1 and self.hp_fraction <= 0.5:
            self.phase = 2
            phase_text = " It enters a frenzied state!"
        return f"The Lich Lord reels ({self.hp}/{self.max_hp} HP).{phase_text}"

    def execute_attack(self) -> tuple:
        """Execute one boss attack. Returns (damage, heal, description)."""
        atk = self.choose_attack()
        dmg = random.randint(*atk["damage"])
        if self.phase == 2:
            dmg = int(dmg * 1.3)
        heal = 0
        if "heal_fraction" in atk and self.phase == 2:
            heal = int(dmg * atk["heal_fraction"])
            self.hp = min(self.max_hp, self.hp + heal)
        desc = f"The Lich Lord {atk['desc']}! ({dmg} damage)"
        if heal:
            desc += f", recovers {heal} HP"
        return dmg, heal, desc


# ================================================================
# MAIN QUEST MANAGER
# ================================================================

class MainQuestManager:
    """Manages the Awakening questline lifecycle."""

    def __init__(self):
        self.chain: Optional[QuestChain] = None
        self.started = False
        self.completed = False
        self.scholar_name = "Scholar Aldric"
        self.settlement_name = ""
        self.kingdoms_convinced: List[str] = []
        self.lich_lord: Optional[LichLord] = None
        self.victory = False
        self._chronicle_ref = None  # set externally

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self, settlement_name: str, scholar_name: str = "Scholar Aldric"):
        """Create and start the main questline."""
        if self.started:
            return
        self.settlement_name = settlement_name
        self.scholar_name = scholar_name
        self.chain = create_the_awakening(settlement_name, scholar_name)
        self.started = True

    def attach_chronicle(self, chronicle_sys):
        """Attach a ChronicleSystem for story logging."""
        self._chronicle_ref = chronicle_sys

    # ------------------------------------------------------------------
    # Event forwarding — mirrors QuestChainManager API
    # ------------------------------------------------------------------

    def on_reach_location(self, location: str,
                          game_day: int = 0) -> List[str]:
        """Handle player reaching a location."""
        if not self.chain or self.chain.completed:
            return []
        messages = []
        msg = self.chain.on_reach_location(location)
        if msg:
            messages.append(msg)
            self._log_stage_completion(game_day)
        return messages

    def on_collect_item(self, item_name: str,
                        game_day: int = 0) -> List[str]:
        """Handle player collecting an item."""
        if not self.chain or self.chain.completed:
            return []
        messages = []
        msg = self.chain.on_collect_item(item_name)
        if msg:
            messages.append(msg)
            self._log_stage_completion(game_day)
        return messages

    def on_talk_npc(self, npc_name: str, game_day: int = 0) -> List[str]:
        """Handle player talking to an NPC."""
        if not self.chain or self.chain.completed:
            return []
        messages = []
        msg = self.chain.on_talk_npc(npc_name)
        if msg:
            messages.append(msg)
            self._log_stage_completion(game_day)
        return messages

    def on_kill(self, creature_kind: str, game_day: int = 0) -> List[str]:
        """Handle creature kill (used for the final boss)."""
        if not self.chain or self.chain.completed:
            return []
        messages = []
        msg = self.chain.on_kill(creature_kind)
        if msg:
            messages.append(msg)
            self._log_stage_completion(game_day)
            if self.chain.completed:
                self.completed = True
                self.victory = True
        return messages

    # ------------------------------------------------------------------
    # Stage 5: Persuasion — custom logic for convincing kingdoms
    # ------------------------------------------------------------------

    def attempt_persuade_kingdom(self, kingdom_name: str, player,
                                 game_day: int = 0) -> tuple:
        """Attempt to convince a kingdom ruler to join the alliance.

        Performs a CHA-based persuasion check (DC 14).
        Returns (success: bool, message: str).
        """
        if not self.chain or self.chain.completed:
            return False, "No active main quest."

        stage = self.chain.current_stage
        if not stage or stage.title != "Rally the Kingdoms":
            return False, "You are not on the Rally the Kingdoms stage."

        if kingdom_name in self.kingdoms_convinced:
            return False, f"{kingdom_name} has already joined the alliance."

        # Persuasion check — DC 14
        from game.core.skill_checks import roll_skill_check
        success, roll_total, result_text = roll_skill_check(
            "Persuade", player, dc=14
        )

        if success:
            self.kingdoms_convinced.append(kingdom_name)
            stage.progress = len(self.kingdoms_convinced)
            msg = (
                f"[{result_text}] The ruler of {kingdom_name} is convinced! "
                f"({len(self.kingdoms_convinced)}/3 kingdoms allied)"
            )
            if stage.check_completion():
                advance_msg = self.chain._advance_stage()
                msg += f"\n{advance_msg}"
                self._log_story(game_day, "stage_5_complete")
            return True, msg
        else:
            msg = (
                f"[{result_text}] The ruler of {kingdom_name} is not "
                f"convinced. Perhaps try again later or improve your "
                f"charisma."
            )
            return False, msg

    # ------------------------------------------------------------------
    # Stage 6: Final boss fight
    # ------------------------------------------------------------------

    def spawn_lich_lord(self) -> LichLord:
        """Spawn the Lich Lord boss for the final battle."""
        self.lich_lord = LichLord()
        return self.lich_lord

    def boss_combat_round(self, player_damage: int,
                          game_day: int = 0) -> Dict:
        """Execute one round of boss combat. Returns result dict."""
        if not self.lich_lord or not self.lich_lord.alive:
            return {"boss_alive": False, "messages": ["The Lich Lord is already defeated."]}

        # Player attacks boss
        hit_desc = self.lich_lord.take_damage(player_damage)

        result = {
            "boss_hp": self.lich_lord.hp,
            "boss_max_hp": self.lich_lord.max_hp,
            "boss_alive": self.lich_lord.alive,
            "boss_hit_desc": hit_desc,
            "player_dmg_taken": 0,
            "boss_heal": 0,
            "boss_attack_desc": "",
            "messages": [hit_desc],
        }

        if not self.lich_lord.alive:
            # Boss defeated — complete the quest
            self.on_kill("lich_lord", game_day)
            result["messages"].append(
                "VICTORY! The Awakening is complete. You have saved the realm!"
            )
            self._log_story(game_day, "stage_6_complete")
            return result

        # Boss attacks player
        dmg, heal, desc = self.lich_lord.execute_attack()
        result["player_dmg_taken"] = dmg
        result["boss_heal"] = heal
        result["boss_attack_desc"] = desc
        result["boss_hp"] = self.lich_lord.hp
        result["messages"].append(desc)

        return result

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def get_status(self) -> Dict:
        """Get current main quest status for UI display."""
        if not self.chain:
            return {"active": False, "stage": 0, "title": "Not started"}

        stage = self.chain.current_stage
        return {
            "active": not self.chain.completed,
            "completed": self.chain.completed,
            "chain_name": self.chain.name,
            "stage": self.chain.current_stage_idx + 1,
            "total_stages": len(self.chain.stages),
            "stage_title": stage.title if stage else "Complete",
            "stage_desc": stage.description if stage else "",
            "progress": stage.progress_text if stage else "Done",
            "gold_earned": self.chain.total_gold_earned,
            "xp_earned": self.chain.total_xp_earned,
            "kingdoms_allied": list(self.kingdoms_convinced),
            "victory": self.victory,
        }

    def get_progress_summary(self) -> str:
        """One-line summary for HUD display."""
        if not self.chain:
            return ""
        return self.chain.progress_summary

    # ------------------------------------------------------------------
    # Chronicle / story logging
    # ------------------------------------------------------------------

    def _log_stage_completion(self, game_day: int):
        """Log story text for the just-completed stage."""
        if not self.chain:
            return
        # Stage index just advanced, so the completed stage is idx - 1
        completed_idx = self.chain.current_stage_idx - 1
        stage_keys = {
            0: "stage_1_complete",
            1: "stage_2_complete",
            2: "stage_3_complete",
            3: "stage_4_complete",
            4: "stage_5_complete",
            # stage 6 is logged in boss_combat_round
        }
        key = stage_keys.get(completed_idx)
        if key:
            self._log_story(game_day, key)
        # Log stage 2 start text when stage 1 completes
        if completed_idx == 0:
            self._log_story(game_day, "stage_2_start")

    def _log_story(self, game_day: int, story_key: str):
        """Write a story beat to the chronicle system."""
        text = STORY_TEXT.get(story_key, "")
        if not text:
            return
        text = text.format(
            settlement=self.settlement_name,
            scholar=self.scholar_name,
        )
        if self._chronicle_ref and hasattr(self._chronicle_ref, 'record'):
            importance = 3  # major event
            if story_key == "stage_6_complete":
                importance = 4  # legendary
            self._chronicle_ref.record(
                game_day=game_day,
                category="quest",
                title=f"The Awakening: {story_key.replace('_', ' ').title()}",
                description=text,
                importance=importance,
            )

    def apply_final_rewards(self, player):
        """Apply all accumulated chain rewards to the player."""
        if self.chain:
            return self.chain.apply_rewards_to_player(player)
        return ""
