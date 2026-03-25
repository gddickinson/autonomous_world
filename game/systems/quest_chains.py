"""Multi-stage quest chains with branching paths.

Provides QuestChain and QuestStage classes for quests that span multiple
stages, where completing one stage unlocks the next. Some stages offer
branch choices that determine the final outcome and rewards.

Includes three built-in quest chains:
- The Bandit Problem (3 stages, combat/diplomacy branch)
- The Missing Merchant (3 stages, combat/delivery branch)
- Ancient Secrets (4 stages, 3-way branch)
"""

import random
from typing import Dict, List, Optional, Tuple

from game.systems.quests import Quest


# ================================================================
# STAGE COMPLETION CONDITIONS
# ================================================================

CONDITION_KILL = "kill"           # Kill N creatures of a type
CONDITION_LOCATION = "location"  # Reach a specific location
CONDITION_ITEM = "item"          # Possess a specific item
CONDITION_TALK = "talk"          # Talk to a specific NPC
CONDITION_DELIVER = "deliver"    # Deliver item to NPC


class StageCondition:
    """Defines what must happen to complete a quest stage."""

    def __init__(self, kind: str, target: str = "", count: int = 1,
                 description: str = ""):
        self.kind = kind        # CONDITION_* constant
        self.target = target    # creature type, location name, item name, NPC name
        self.count = count      # how many (kills, items, etc.)
        self.description = description or f"{kind}: {target} x{count}"

    def to_dict(self) -> dict:
        return {"kind": self.kind, "target": self.target,
                "count": self.count, "description": self.description}


# ================================================================
# QUEST STAGE
# ================================================================

class QuestStage:
    """A single stage within a multi-stage quest chain."""

    def __init__(self, title: str, description: str,
                 condition: StageCondition,
                 reward_gold: int = 0, reward_xp: int = 0,
                 reward_item: str = "",
                 branch_choices: Optional[List['BranchChoice']] = None):
        self.title = title
        self.description = description
        self.condition = condition
        self.reward_gold = reward_gold
        self.reward_xp = reward_xp
        self.reward_item = reward_item
        self.progress = 0
        self.completed = False
        # If set, this stage presents a branch choice instead of
        # having a single completion condition
        self.branch_choices = branch_choices

    @property
    def is_branch(self) -> bool:
        return bool(self.branch_choices)

    @property
    def progress_text(self) -> str:
        if self.is_branch:
            return "Choose a path"
        return f"{self.progress}/{self.condition.count}"

    def check_completion(self) -> bool:
        """Check if this stage's condition is met."""
        if self.is_branch:
            return False  # Branches complete via choose_branch
        if self.progress >= self.condition.count:
            self.completed = True
        return self.completed


class BranchChoice:
    """A branching option at a quest stage."""

    def __init__(self, label: str, description: str,
                 skill_check: str = "", dc: int = 0,
                 condition: Optional[StageCondition] = None,
                 reward_gold: int = 0, reward_xp: int = 0,
                 reward_item: str = "",
                 reward_reputation: int = 0,
                 reward_knowledge: str = "",
                 outcome_text: str = ""):
        self.label = label              # e.g. "Negotiate peace"
        self.description = description  # longer description
        self.skill_check = skill_check  # "diplomacy", "combat", "" (none)
        self.dc = dc                    # difficulty class for skill check
        self.condition = condition      # optional extra condition
        self.reward_gold = reward_gold
        self.reward_xp = reward_xp
        self.reward_item = reward_item
        self.reward_reputation = reward_reputation
        self.reward_knowledge = reward_knowledge  # lore / knowledge reward
        self.outcome_text = outcome_text


# ================================================================
# QUEST CHAIN
# ================================================================

class QuestChain:
    """A multi-stage quest with linear stages and optional branching."""

    def __init__(self, chain_id: str, name: str, stages: List[QuestStage],
                 settlement: str = "", kingdom: str = "",
                 giver_name: str = ""):
        self.chain_id = chain_id
        self.name = name
        self.stages = stages
        self.current_stage_idx = 0
        self.settlement = settlement
        self.kingdom = kingdom
        self.giver_name = giver_name
        self.completed = False
        self.failed = False
        self.chosen_branch: Optional[BranchChoice] = None
        self.total_gold_earned = 0
        self.total_xp_earned = 0
        self.event_log: List[str] = []

    @property
    def current_stage(self) -> Optional[QuestStage]:
        if 0 <= self.current_stage_idx < len(self.stages):
            return self.stages[self.current_stage_idx]
        return None

    @property
    def progress_summary(self) -> str:
        stage = self.current_stage
        if not stage:
            return "Completed" if self.completed else "Failed"
        return (f"[{self.name}] Stage {self.current_stage_idx + 1}/"
                f"{len(self.stages)}: {stage.title} — {stage.progress_text}")

    # ------------------------------------------------------------------
    # Event handlers — called by the quest system
    # ------------------------------------------------------------------

    def on_kill(self, creature_kind: str) -> Optional[str]:
        """Notify of a creature kill. Returns message if stage advances."""
        stage = self.current_stage
        if not stage or stage.is_branch or stage.completed:
            return None
        if stage.condition.kind != CONDITION_KILL:
            return None
        if creature_kind.lower() == stage.condition.target.lower():
            stage.progress += 1
            if stage.check_completion():
                return self._advance_stage()
        return None

    def on_reach_location(self, location: str) -> Optional[str]:
        """Notify of reaching a location."""
        stage = self.current_stage
        if not stage or stage.is_branch or stage.completed:
            return None
        if stage.condition.kind != CONDITION_LOCATION:
            return None
        if location.lower() in stage.condition.target.lower():
            stage.progress = stage.condition.count
            if stage.check_completion():
                return self._advance_stage()
        return None

    def on_talk_npc(self, npc_name: str) -> Optional[str]:
        """Notify of talking to an NPC."""
        stage = self.current_stage
        if not stage or stage.is_branch or stage.completed:
            return None
        if stage.condition.kind != CONDITION_TALK:
            return None
        if npc_name.lower() in stage.condition.target.lower():
            stage.progress = stage.condition.count
            if stage.check_completion():
                return self._advance_stage()
        return None

    def on_collect_item(self, item_name: str) -> Optional[str]:
        """Notify of item collection."""
        stage = self.current_stage
        if not stage or stage.is_branch or stage.completed:
            return None
        if stage.condition.kind not in (CONDITION_ITEM, CONDITION_DELIVER):
            return None
        if item_name.lower() == stage.condition.target.lower():
            stage.progress += 1
            if stage.check_completion():
                return self._advance_stage()
        return None

    def choose_branch(self, branch_index: int) -> Tuple[bool, str]:
        """Choose a branch at a branching stage.

        Returns (success, message).
        """
        stage = self.current_stage
        if not stage or not stage.is_branch:
            return False, "No branch choice available."
        if branch_index < 0 or branch_index >= len(stage.branch_choices):
            return False, "Invalid branch choice."
        branch = stage.branch_choices[branch_index]
        self.chosen_branch = branch
        stage.completed = True
        msg = self._apply_branch_rewards(branch)
        # Complete the chain after branch
        self.current_stage_idx += 1
        if self.current_stage_idx >= len(self.stages):
            self.completed = True
            msg += f"\nQuest chain \"{self.name}\" complete!"
        return True, msg

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _advance_stage(self) -> str:
        """Move to the next stage, apply stage rewards."""
        stage = self.stages[self.current_stage_idx]
        msg = f"Stage complete: {stage.title}"
        # Apply stage rewards
        if stage.reward_gold > 0:
            self.total_gold_earned += stage.reward_gold
            msg += f" (+{stage.reward_gold}g)"
        if stage.reward_xp > 0:
            self.total_xp_earned += stage.reward_xp
            msg += f" (+{stage.reward_xp} XP)"
        if stage.reward_item:
            msg += f" (received {stage.reward_item})"

        self.event_log.append(msg)
        self.current_stage_idx += 1

        if self.current_stage_idx >= len(self.stages):
            self.completed = True
            msg += f"\nQuest chain \"{self.name}\" complete!"
        else:
            next_stage = self.current_stage
            if next_stage:
                if next_stage.is_branch:
                    msg += f"\n  -> Choose your path: {next_stage.title}"
                    for i, b in enumerate(next_stage.branch_choices):
                        msg += f"\n     [{i + 1}] {b.label}: {b.description}"
                else:
                    msg += f"\n  -> Next: {next_stage.title}"
        return msg

    def _apply_branch_rewards(self, branch: BranchChoice) -> str:
        """Apply rewards from a chosen branch."""
        msg = f"Chose: {branch.label}"
        if branch.reward_gold > 0:
            self.total_gold_earned += branch.reward_gold
            msg += f" (+{branch.reward_gold}g)"
        if branch.reward_xp > 0:
            self.total_xp_earned += branch.reward_xp
            msg += f" (+{branch.reward_xp} XP)"
        if branch.reward_item:
            msg += f" (received {branch.reward_item})"
        if branch.reward_reputation > 0:
            msg += f" (+{branch.reward_reputation} reputation)"
        if branch.reward_knowledge:
            msg += f" (learned: {branch.reward_knowledge})"
        if branch.outcome_text:
            msg += f"\n{branch.outcome_text}"
        self.event_log.append(msg)
        return msg

    def apply_rewards_to_player(self, player) -> str:
        """Apply accumulated chain rewards to a player object."""
        if self.total_gold_earned > 0:
            player.gold += self.total_gold_earned
        if self.total_xp_earned > 0:
            player.gain_xp(self.total_xp_earned)
        player.quests_completed += 1
        branch = self.chosen_branch
        msg = (f"Chain \"{self.name}\": +{self.total_gold_earned}g, "
               f"+{self.total_xp_earned} XP")
        if branch and branch.reward_item:
            from game.core.items import make_item
            item = make_item(branch.reward_item)
            if item and player.add_item(item):
                msg += f", received {branch.reward_item}"
        return msg


# ================================================================
# CHAIN REGISTRY AND MANAGER
# ================================================================

# Chain definitions live in quest_chain_defs.py for modularity.
# Import the factory registry from there.
from game.systems.quest_chain_defs import CHAIN_FACTORIES


class QuestChainManager:
    """Tracks active and completed quest chains.

    Works alongside the existing QuestSystem. The QuestSystem handles
    single quests and the older chain format; this manager handles
    the new multi-stage branching chains.
    """

    def __init__(self):
        self.active_chains: Dict[str, QuestChain] = {}
        self.completed_chains: Dict[str, QuestChain] = {}
        self.failed_chains: Dict[str, QuestChain] = {}

    # ------------------------------------------------------------------
    # Starting / managing chains
    # ------------------------------------------------------------------

    def start_chain(self, chain_id: str, settlement: str = "",
                    kingdom: str = "",
                    giver: str = "") -> Optional[QuestChain]:
        """Start a quest chain by ID if not already active or completed."""
        if chain_id in self.active_chains:
            return None
        if chain_id in self.completed_chains:
            return None
        factory = CHAIN_FACTORIES.get(chain_id)
        if not factory:
            return None
        chain = factory(settlement=settlement, giver=giver or "an NPC")
        chain.kingdom = kingdom
        self.active_chains[chain_id] = chain
        return chain

    def get_active_chain(self, chain_id: str) -> Optional[QuestChain]:
        return self.active_chains.get(chain_id)

    def abandon_chain(self, chain_id: str) -> bool:
        chain = self.active_chains.pop(chain_id, None)
        if chain:
            chain.failed = True
            self.failed_chains[chain_id] = chain
            return True
        return False

    # ------------------------------------------------------------------
    # Event forwarding — call these from game loop
    # ------------------------------------------------------------------

    def on_kill(self, creature_kind: str) -> List[str]:
        """Forward kill event to all active chains. Returns messages."""
        messages = []
        for chain in list(self.active_chains.values()):
            msg = chain.on_kill(creature_kind)
            if msg:
                messages.append(msg)
            self._check_chain_done(chain)
        return messages

    def on_reach_location(self, location: str) -> List[str]:
        messages = []
        for chain in list(self.active_chains.values()):
            msg = chain.on_reach_location(location)
            if msg:
                messages.append(msg)
            self._check_chain_done(chain)
        return messages

    def on_talk_npc(self, npc_name: str) -> List[str]:
        messages = []
        for chain in list(self.active_chains.values()):
            msg = chain.on_talk_npc(npc_name)
            if msg:
                messages.append(msg)
            self._check_chain_done(chain)
        return messages

    def on_collect_item(self, item_name: str) -> List[str]:
        messages = []
        for chain in list(self.active_chains.values()):
            msg = chain.on_collect_item(item_name)
            if msg:
                messages.append(msg)
            self._check_chain_done(chain)
        return messages

    def choose_branch(self, chain_id: str,
                      branch_index: int) -> Tuple[bool, str]:
        """Choose a branch for a chain at a branching stage."""
        chain = self.active_chains.get(chain_id)
        if not chain:
            return False, "No such active chain."
        ok, msg = chain.choose_branch(branch_index)
        if ok:
            self._check_chain_done(chain)
        return ok, msg

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    def get_active_summaries(self) -> List[str]:
        """Get progress summaries for all active chains."""
        return [c.progress_summary for c in self.active_chains.values()]

    def get_branch_options(self, chain_id: str) -> List[Dict]:
        """Get branch options for a chain at a branching stage."""
        chain = self.active_chains.get(chain_id)
        if not chain:
            return []
        stage = chain.current_stage
        if not stage or not stage.is_branch:
            return []
        options = []
        for i, b in enumerate(stage.branch_choices):
            options.append({
                "index": i,
                "label": b.label,
                "description": b.description,
                "skill_check": b.skill_check,
                "dc": b.dc,
            })
        return options

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_chain_done(self, chain: QuestChain):
        """Move chain from active to completed if done."""
        if chain.completed and chain.chain_id in self.active_chains:
            del self.active_chains[chain.chain_id]
            self.completed_chains[chain.chain_id] = chain
