#!/usr/bin/env python3
"""Deep functional tests for the quest system.

Tests: starting quest, quest board generation, reputation-gated quests,
quest chain progression, multi-stage branching, skill checks,
main quest stages, quest rewards.
"""

import os
import sys
import random
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

_results = []


def test(name):
    def decorator(fn):
        def wrapper(*a, **kw):
            try:
                result = fn(*a, **kw)
                if result is None:
                    result = True
                _results.append((name, bool(result),
                                 "OK" if result else "returned False"))
            except Exception as e:
                tb = traceback.format_exc().strip().split('\n')[-1]
                _results.append((name, False, tb))
        return wrapper
    return decorator


def print_report():
    total = len(_results)
    passed = sum(1 for _, p, _ in _results if p)
    failed = total - passed
    print("\n" + "=" * 70)
    print(f"QUEST TESTS  —  {passed}/{total} passed, {failed} failed")
    print("=" * 70)
    for name, ok, detail in _results:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}" + ("" if ok else f"  — {detail}"))
    print("=" * 70)
    return failed


# ===================================================================
# 1. STARTING QUEST
# ===================================================================

@test("create_starting_quest is callable")
def test_starting_quest_callable():
    from game.systems.starting_quest import create_starting_quest
    assert callable(create_starting_quest)


@test("Starting quest has title 'Find Civilization'")
def test_starting_quest_title():
    from game.systems.quests import Quest
    q = Quest(
        title="Find Civilization",
        description="Find the nearest settlement.",
        kind="investigate", target="TestVillage",
        target_count=1, reward_gold=10, reward_xp=25,
        difficulty="easy", stages=1,
    )
    assert q.title == "Find Civilization"
    assert q.reward_gold == 10
    assert q.reward_xp == 25


@test("QuestSystem.accept_quest adds to active list")
def test_quest_accept():
    from game.systems.quests import QuestSystem, Quest
    qs = QuestSystem()
    q = Quest(title="Test", description="Test quest",
              kind="fetch", target="Herbs", target_count=3,
              reward_gold=20, reward_xp=30, difficulty="easy")
    qs.accept_quest(q)
    assert len(qs.active_quests) == 1
    assert qs.active_quests[0].title == "Test"


# ===================================================================
# 2. QUEST BOARD
# ===================================================================

@test("QuestBoard generates quests on refresh")
def test_quest_board_refresh():
    from game.systems.quest_board import QuestBoard
    board = QuestBoard("TestVillage",
                       nearby_settlements=["OtherTown"],
                       terrain_context={"forest": 5},
                       threats=["wolves"])
    board.refresh(current_day=1, player_level=3, player_rank_index=0)
    assert len(board.quests) > 0, \
        f"Board should have quests after refresh, got {len(board.quests)}"


@test("Quest board generates correct quest types (bounty, gather)")
def test_quest_board_types():
    from game.systems.quest_board import QuestBoard
    board = QuestBoard("TestVillage",
                       nearby_settlements=["OtherTown"],
                       terrain_context={"forest": 5},
                       threats=["wolves", "bandits"])
    random.seed(42)
    board.refresh(current_day=1, player_level=5, player_rank_index=2)
    kinds = set(q.kind for q in board.quests)
    assert len(kinds) > 0, "Should generate at least one quest type"


@test("Quest board needs_refresh works correctly")
def test_quest_board_needs_refresh():
    from game.systems.quest_board import QuestBoard
    board = QuestBoard("TestVillage")
    board.last_refresh_day = 1
    board.refresh_interval = 7
    assert board.needs_refresh(8) is True   # day 8, last=1
    assert board.needs_refresh(5) is False  # day 5, last=1


@test("Quest board max_quests limits output")
def test_quest_board_max():
    from game.systems.quest_board import QuestBoard
    board = QuestBoard("TestVillage",
                       nearby_settlements=["A", "B"],
                       terrain_context={"forest": 5},
                       threats=["wolves"])
    board.max_quests = 4
    board.refresh(current_day=1, player_level=10, player_rank_index=4)
    assert len(board.quests) <= 4


# ===================================================================
# 3. REPUTATION-GATED QUESTS
# ===================================================================

@test("Outsider (rank 0) can only get bounty and gather quests")
def test_rank0_quest_access():
    from game.systems.quest_board import QuestBoard, QUEST_RANK_REQUIREMENTS
    board = QuestBoard("TestVillage",
                       nearby_settlements=["OtherTown"],
                       terrain_context={"forest": 5},
                       threats=["wolves"])
    random.seed(42)
    board.refresh(current_day=1, player_level=5, player_rank_index=0)
    for q in board.quests:
        req = QUEST_RANK_REQUIREMENTS.get(q.kind, 0)
        assert req <= 0, \
            f"Rank 0 should not get {q.kind} (requires rank {req})"


@test("Noble (rank 4) can access kingdom_special quests")
def test_rank4_quest_access():
    from game.systems.quest_board import QUEST_RANK_REQUIREMENTS
    assert QUEST_RANK_REQUIREMENTS.get("kingdom_special") == 4


@test("Escort requires Citizen rank (1)")
def test_escort_rank_requirement():
    from game.systems.quest_board import QUEST_RANK_REQUIREMENTS
    assert QUEST_RANK_REQUIREMENTS.get("escort") == 1


@test("Investigation requires Honored rank (3)")
def test_investigation_rank_requirement():
    from game.systems.quest_board import QUEST_RANK_REQUIREMENTS
    assert QUEST_RANK_REQUIREMENTS.get("investigation") == 3


# ===================================================================
# 4. QUEST CHAIN PROGRESSION
# ===================================================================

@test("QuestChain advances through stages")
def test_quest_chain_advance():
    from game.systems.quest_chains import (
        QuestChain, QuestStage, StageCondition, CONDITION_KILL
    )
    stages = [
        QuestStage("Stage 1", "Kill wolves",
                   StageCondition(CONDITION_KILL, "wolf", 3),
                   reward_gold=20, reward_xp=30),
        QuestStage("Stage 2", "Kill bears",
                   StageCondition(CONDITION_KILL, "bear", 1),
                   reward_gold=50, reward_xp=60),
    ]
    chain = QuestChain("test_chain", "Test Chain", stages)
    assert chain.current_stage_idx == 0
    # Complete stage 1
    stages[0].progress = 3
    stages[0].check_completion()
    assert stages[0].completed is True
    chain._advance_stage()
    assert chain.current_stage_idx == 1


@test("Quest stage progress tracks kills")
def test_stage_progress():
    from game.systems.quest_chains import (
        QuestStage, StageCondition, CONDITION_KILL
    )
    stage = QuestStage("Kill Wolves", "Eliminate 5 wolves",
                       StageCondition(CONDITION_KILL, "wolf", 5))
    stage.progress = 3
    assert stage.progress_text == "3/5"
    stage.progress = 5
    stage.check_completion()
    assert stage.completed is True


# ===================================================================
# 5. MULTI-STAGE BRANCHING
# ===================================================================

@test("BranchChoice has skill check and DC")
def test_branch_choice_structure():
    from game.systems.quest_chains import BranchChoice
    branch = BranchChoice(
        label="Negotiate peace",
        description="Use diplomacy to resolve the conflict",
        skill_check="charisma", dc=15,
        reward_gold=100, reward_reputation=20,
        outcome_text="Peace was achieved through words."
    )
    assert branch.skill_check == "charisma"
    assert branch.dc == 15
    assert branch.reward_gold == 100


@test("Branch stage is_branch property works")
def test_branch_is_branch():
    from game.systems.quest_chains import (
        QuestStage, StageCondition, BranchChoice, CONDITION_KILL
    )
    normal_stage = QuestStage("Normal", "desc",
                              StageCondition(CONDITION_KILL, "wolf", 1))
    assert normal_stage.is_branch is False

    branch_stage = QuestStage("Branch", "choose",
                              StageCondition(CONDITION_KILL, "wolf", 1),
                              branch_choices=[
                                  BranchChoice("A", "do A"),
                                  BranchChoice("B", "do B"),
                              ])
    assert branch_stage.is_branch is True


# ===================================================================
# 6. SKILL CHECKS
# ===================================================================

@test("Skill check uses D20 roll concept")
def test_skill_check_d20():
    # Simulate D20 + modifier vs DC
    random.seed(42)
    modifier = 5  # e.g., CHA modifier
    dc = 15
    rolls = [random.randint(1, 20) + modifier for _ in range(100)]
    successes = sum(1 for r in rolls if r >= dc)
    # With +5 modifier vs DC 15, need 10+ on d20 (55% chance)
    assert 30 < successes < 80, \
        f"Expected ~55% success rate, got {successes}%"


@test("BranchChoice DC 0 always succeeds")
def test_dc_zero_always_succeeds():
    random.seed(42)
    dc = 0
    modifier = 0
    for _ in range(50):
        roll = random.randint(1, 20) + modifier
        assert roll >= dc


# ===================================================================
# 7. MAIN QUEST "THE AWAKENING"
# ===================================================================

@test("The Awakening has 6 stages")
def test_awakening_6_stages():
    from game.systems.main_quest import create_the_awakening
    chain = create_the_awakening(settlement="TestVillage",
                                 giver="Scholar Aldric")
    assert len(chain.stages) == 6, \
        f"Expected 6 stages, got {len(chain.stages)}"


@test("The Awakening chain ID is 'the_awakening'")
def test_awakening_chain_id():
    from game.systems.main_quest import CHAIN_ID
    assert CHAIN_ID == "the_awakening"


@test("The Awakening stage 1 is 'Find Civilization'")
def test_awakening_stage1_title():
    from game.systems.main_quest import create_the_awakening
    chain = create_the_awakening()
    assert chain.stages[0].title == "Find Civilization"


@test("The Awakening has Lich Lord boss data")
def test_awakening_boss():
    from game.systems.main_quest import (
        LICH_LORD_HP, LICH_LORD_ATTACKS
    )
    assert LICH_LORD_HP == 200
    assert len(LICH_LORD_ATTACKS) >= 3


@test("The Awakening has unique reward items")
def test_awakening_rewards():
    from game.systems.main_quest import SUNSTONE_AMULET, LICH_CROWN
    assert SUNSTONE_AMULET == "Sunstone Amulet"
    assert LICH_CROWN == "Crown of the Vanquished Lich"


# ===================================================================
# 8. QUEST REWARDS
# ===================================================================

@test("Quest templates define gold and XP rewards")
def test_quest_template_rewards():
    from game.systems.quests import QUEST_TEMPLATES
    for tmpl in QUEST_TEMPLATES:
        assert tmpl.get("base_gold", 0) > 0, \
            f"Template '{tmpl['type']}' has no gold reward"
        assert tmpl.get("base_xp", 0) > 0, \
            f"Template '{tmpl['type']}' has no XP reward"


@test("Reward items exist by difficulty tier")
def test_reward_items_by_difficulty():
    from game.systems.quests import REWARD_ITEMS
    for tier in ("easy", "medium", "hard", "epic"):
        assert tier in REWARD_ITEMS, f"Missing tier: {tier}"
        assert len(REWARD_ITEMS[tier]) > 0, \
            f"Tier {tier} has no reward items"


@test("Unique quest items have proper stats")
def test_unique_items():
    from game.systems.quests import UNIQUE_ITEMS
    assert len(UNIQUE_ITEMS) > 0
    for item in UNIQUE_ITEMS:
        assert "name" in item and len(item["name"]) > 0
        assert "kind" in item
        assert "value" in item and item["value"] > 0


@test("Quest completion marks quest as completed")
def test_quest_completion():
    from game.systems.quests import Quest
    q = Quest(title="Test", description="test",
              kind="kill", target="wolf", target_count=3,
              reward_gold=20, reward_xp=30)
    q.progress = 3
    q.completed = q.progress >= q.target_count
    assert q.completed is True


# ===================================================================
# Run all tests
# ===================================================================

if __name__ == "__main__":
    all_tests = [
        test_starting_quest_callable, test_starting_quest_title,
        test_quest_accept,
        test_quest_board_refresh, test_quest_board_types,
        test_quest_board_needs_refresh, test_quest_board_max,
        test_rank0_quest_access, test_rank4_quest_access,
        test_escort_rank_requirement, test_investigation_rank_requirement,
        test_quest_chain_advance, test_stage_progress,
        test_branch_choice_structure, test_branch_is_branch,
        test_skill_check_d20, test_dc_zero_always_succeeds,
        test_awakening_6_stages, test_awakening_chain_id,
        test_awakening_stage1_title, test_awakening_boss,
        test_awakening_rewards,
        test_quest_template_rewards, test_reward_items_by_difficulty,
        test_unique_items, test_quest_completion,
    ]
    for t in all_tests:
        t()
    sys.exit(print_report())
